"""Acces SQLite : etat courant des fonds + journal des evenements detectes.

Schema volontairement simple (deux tables) : suffisant pour un usage a trois
associes, sans serveur de base de donnees a maintenir.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator

SCHEMA = """
CREATE TABLE IF NOT EXISTS funds (
    code_amf        TEXT PRIMARY KEY,   -- code AMF ou ISIN, cle stable du fonds
    denomination    TEXT NOT NULL,
    type_fonds      TEXT NOT NULL,      -- 'OPCVM' ou 'FIA'
    statut          TEXT NOT NULL,      -- 'actif' ou 'radie'
    first_seen      TEXT NOT NULL,      -- ISO 8601, premiere apparition detectee
    last_seen       TEXT NOT NULL,      -- ISO 8601, derniere fois vu actif
    date_radiation  TEXT                -- ISO 8601, quand le statut est passe a 'radie'
);

CREATE TABLE IF NOT EXISTS events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    code_amf    TEXT NOT NULL,
    denomination TEXT NOT NULL,
    type_fonds  TEXT NOT NULL,
    event_type  TEXT NOT NULL,          -- 'creation' ou 'disparition'
    detected_at TEXT NOT NULL,          -- ISO 8601
    source      TEXT NOT NULL,          -- 'geco' ou 'rss'
    notified    INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS rss_alerts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    guid        TEXT UNIQUE NOT NULL,
    title       TEXT NOT NULL,
    link        TEXT,
    published   TEXT,
    detected_at TEXT NOT NULL,
    notified    INTEGER NOT NULL DEFAULT 0
);
"""


@dataclass(frozen=True)
class FundSnapshotRow:
    code_amf: str
    denomination: str
    type_fonds: str  # 'OPCVM' ou 'FIA'


@dataclass(frozen=True)
class Event:
    code_amf: str
    denomination: str
    type_fonds: str
    event_type: str  # 'creation' ou 'disparition'
    detected_at: str
    source: str


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def connect(db_path: Path) -> Iterator[sqlite3.Connection]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


def get_active_funds(conn: sqlite3.Connection) -> dict[str, sqlite3.Row]:
    rows = conn.execute("SELECT * FROM funds WHERE statut = 'actif'").fetchall()
    return {row["code_amf"]: row for row in rows}


def upsert_seen(conn: sqlite3.Connection, fund: FundSnapshotRow, seen_at: str) -> None:
    conn.execute(
        """
        INSERT INTO funds (code_amf, denomination, type_fonds, statut, first_seen, last_seen)
        VALUES (?, ?, ?, 'actif', ?, ?)
        ON CONFLICT(code_amf) DO UPDATE SET
            denomination = excluded.denomination,
            statut = 'actif',
            last_seen = excluded.last_seen,
            date_radiation = NULL
        """,
        (fund.code_amf, fund.denomination, fund.type_fonds, seen_at, seen_at),
    )


def mark_radie(conn: sqlite3.Connection, code_amf: str, radiation_at: str) -> None:
    conn.execute(
        "UPDATE funds SET statut = 'radie', date_radiation = ? WHERE code_amf = ?",
        (radiation_at, code_amf),
    )


def record_event(conn: sqlite3.Connection, event: Event) -> None:
    conn.execute(
        """
        INSERT INTO events (code_amf, denomination, type_fonds, event_type, detected_at, source)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            event.code_amf,
            event.denomination,
            event.type_fonds,
            event.event_type,
            event.detected_at,
            event.source,
        ),
    )


def get_unnotified_events(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM events WHERE notified = 0 ORDER BY detected_at ASC"
    ).fetchall()


def mark_events_notified(conn: sqlite3.Connection, event_ids: Iterable[int]) -> None:
    conn.executemany("UPDATE events SET notified = 1 WHERE id = ?", [(i,) for i in event_ids])


def get_recent_events(conn: sqlite3.Connection, limit: int = 200) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM events ORDER BY detected_at DESC LIMIT ?", (limit,)
    ).fetchall()


def count_active_funds_by_type(conn: sqlite3.Connection) -> dict[str, int]:
    rows = conn.execute(
        "SELECT type_fonds, COUNT(*) AS n FROM funds WHERE statut = 'actif' GROUP BY type_fonds"
    ).fetchall()
    return {row["type_fonds"]: row["n"] for row in rows}


def insert_rss_alert(conn: sqlite3.Connection, guid: str, title: str, link: str, published: str) -> bool:
    """Retourne True si l'alerte est nouvelle (pas deja vue)."""
    try:
        conn.execute(
            "INSERT INTO rss_alerts (guid, title, link, published, detected_at) VALUES (?, ?, ?, ?, ?)",
            (guid, title, link, published, now_iso()),
        )
        return True
    except sqlite3.IntegrityError:
        return False  # deja connue (meme guid)


def get_unnotified_rss_alerts(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM rss_alerts WHERE notified = 0 ORDER BY detected_at ASC"
    ).fetchall()


def mark_rss_alerts_notified(conn: sqlite3.Connection, alert_ids: Iterable[int]) -> None:
    conn.executemany("UPDATE rss_alerts SET notified = 1 WHERE id = ?", [(i,) for i in alert_ids])
