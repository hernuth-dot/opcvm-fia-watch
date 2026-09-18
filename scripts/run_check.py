#!/usr/bin/env python3
"""Point d'entree unique : a lancer manuellement ou via cron/GitHub Actions.

Etapes :
  1. Scrape GECO -> snapshot complet des OPC actifs.
  2. Compare au snapshot precedent (base SQLite) -> detecte creations/disparitions.
  3. Lit le flux RSS AMF (best-effort) -> alertes complementaires a verifier a la main.
  4. Regenere le dashboard HTML statique (docs/index.html).
  5. Envoie un email si au moins un evenement nouveau a ete detecte.

Usage :
  python scripts/run_check.py                 # execution normale
  python scripts/run_check.py --dump-html      # + sauvegarde data/debug_geco.html
                                                  (utile pour ajuster les
                                                  selecteurs de geco_scraper.py)
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import db, diff_engine, notifier, report, rss_source  # noqa: E402
from src.config import settings  # noqa: E402
from src.geco_scraper import scrape_geco  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("run_check")

# Garde-fou : si le nouveau snapshot GECO contient moins de X% du nombre de
# fonds actifs connus, on suppose un incident (scraping casse, page vide,
# blocage reseau) plutot qu'une vague massive de radiations, et on n'applique
# pas le diff pour eviter de fausses alertes en cascade.
MIN_SNAPSHOT_RATIO = 0.5


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump-html", action="store_true", help="Sauvegarde le HTML brut de GECO pour debug")
    args = parser.parse_args()

    dump_path = str(settings.database_path.parent / "debug_geco.html") if args.dump_html else None

    with db.connect(settings.database_path) as conn:
        active_before = db.get_active_funds(conn)

        try:
            snapshot = scrape_geco(settings.geco_url, dump_html_path=dump_path)
        except Exception:
            logger.exception("Echec du scraping GECO, execution annulee pour cette fois.")
            snapshot = []

        n_creations = n_disparitions = 0
        if snapshot and (not active_before or len(snapshot) >= len(active_before) * MIN_SNAPSHOT_RATIO):
            n_creations, n_disparitions = diff_engine.apply_snapshot(conn, snapshot)
        elif active_before and snapshot:
            logger.warning(
                "Snapshot GECO suspect (%d recus vs %d connus) : diff ignore par securite.",
                len(snapshot), len(active_before),
            )

        try:
            rss_entries = rss_source.fetch_relevant_entries(settings.amf_rss_url)
        except Exception:
            logger.exception("Echec de la lecture du flux RSS AMF (non bloquant).")
            rss_entries = []

        new_rss_alerts = []
        for entry in rss_entries:
            if db.insert_rss_alert(conn, entry["guid"], entry["title"], entry["link"], entry["published"]):
                new_rss_alerts.append(entry)

        report.generate_report(conn, settings.report_output_path)

        unnotified_events = db.get_unnotified_events(conn)
        unnotified_rss = db.get_unnotified_rss_alerts(conn)

        if unnotified_events or unnotified_rss:
            creations = [dict(e) for e in unnotified_events if e["event_type"] == "creation"]
            disparitions = [dict(e) for e in unnotified_events if e["event_type"] == "disparition"]
            rss_dicts = [dict(a) for a in unnotified_rss]

            body = notifier.build_email_body(creations, disparitions, rss_dicts)
            try:
                notifier.send_email(settings, subject="[OPCVM/FIA] Nouveaux mouvements detectes", body=body)
                db.mark_events_notified(conn, [e["id"] for e in unnotified_events])
                db.mark_rss_alerts_notified(conn, [a["id"] for a in unnotified_rss])
            except Exception:
                logger.exception("Echec de l'envoi de l'email (les evenements resteront 'non notifies').")

        logger.info(
            "Termine : %d creation(s), %d disparition(s), %d alerte(s) RSS nouvelle(s).",
            n_creations, n_disparitions, len(new_rss_alerts),
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
