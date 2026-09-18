"""Comparaison d'un nouveau snapshot GECO avec l'etat connu en base.

Detecte deux types d'evenements :
- 'creation'    : un code_amf present dans le snapshot mais jamais vu (ou
                  precedemment radie) en base.
- 'disparition' : un fonds actif en base mais absent du nouveau snapshot ->
                  on le marque radie.

Une seule execution avec un snapshot vide/partiel (ex: probleme reseau
ponctuel sur GECO) ne doit pas generer une avalanche de fausses
'disparitions' : voir le garde-fou `min_snapshot_ratio` dans run_check.py qui
saute la comparaison si le nouveau snapshot est anormalement plus petit que
l'etat connu.
"""
from __future__ import annotations

import sqlite3

from . import db
from .geco_scraper import GecoFundRow


def apply_snapshot(conn: sqlite3.Connection, snapshot: list[GecoFundRow]) -> tuple[int, int]:
    """Applique un nouveau snapshot GECO a la base et enregistre les evenements.

    Retourne (nb_creations, nb_disparitions).
    """
    now = db.now_iso()
    active_before = db.get_active_funds(conn)
    seen_codes: set[str] = set()

    n_creations = 0
    for row in snapshot:
        seen_codes.add(row.code_amf)
        is_new = row.code_amf not in active_before
        db.upsert_seen(
            conn,
            db.FundSnapshotRow(code_amf=row.code_amf, denomination=row.denomination, type_fonds=row.type_fonds),
            seen_at=now,
        )
        if is_new:
            n_creations += 1
            db.record_event(
                conn,
                db.Event(
                    code_amf=row.code_amf,
                    denomination=row.denomination,
                    type_fonds=row.type_fonds,
                    event_type="creation",
                    detected_at=now,
                    source="geco",
                ),
            )

    n_disparitions = 0
    for code_amf, row in active_before.items():
        if code_amf in seen_codes:
            continue
        db.mark_radie(conn, code_amf, radiation_at=now)
        n_disparitions += 1
        db.record_event(
            conn,
            db.Event(
                code_amf=code_amf,
                denomination=row["denomination"],
                type_fonds=row["type_fonds"],
                event_type="disparition",
                detected_at=now,
                source="geco",
            ),
        )

    return n_creations, n_disparitions
