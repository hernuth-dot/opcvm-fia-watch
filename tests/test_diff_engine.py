"""Tests de la logique de diff, sans dependance a GECO ou au reseau."""
import sqlite3
from pathlib import Path

import pytest

from src import db
from src.diff_engine import apply_snapshot
from src.geco_scraper import GecoFundRow


@pytest.fixture()
def conn(tmp_path: Path) -> sqlite3.Connection:
    with db.connect(tmp_path / "test.db") as c:
        yield c


def test_first_snapshot_creates_all_funds(conn: sqlite3.Connection) -> None:
    snapshot = [
        GecoFundRow(code_amf="A1", denomination="Fonds Alpha", type_fonds="OPCVM"),
        GecoFundRow(code_amf="B1", denomination="Fonds Beta", type_fonds="FIA"),
    ]
    n_creations, n_disparitions = apply_snapshot(conn, snapshot)

    assert n_creations == 2
    assert n_disparitions == 0
    assert len(db.get_active_funds(conn)) == 2


def test_missing_fund_is_marked_radie(conn: sqlite3.Connection) -> None:
    apply_snapshot(conn, [
        GecoFundRow(code_amf="A1", denomination="Fonds Alpha", type_fonds="OPCVM"),
        GecoFundRow(code_amf="B1", denomination="Fonds Beta", type_fonds="FIA"),
    ])

    n_creations, n_disparitions = apply_snapshot(conn, [
        GecoFundRow(code_amf="A1", denomination="Fonds Alpha", type_fonds="OPCVM"),
    ])

    assert n_creations == 0
    assert n_disparitions == 1
    active = db.get_active_funds(conn)
    assert "B1" not in active
    assert "A1" in active


def test_new_fund_in_later_snapshot_is_a_creation(conn: sqlite3.Connection) -> None:
    apply_snapshot(conn, [GecoFundRow(code_amf="A1", denomination="Fonds Alpha", type_fonds="OPCVM")])

    n_creations, n_disparitions = apply_snapshot(conn, [
        GecoFundRow(code_amf="A1", denomination="Fonds Alpha", type_fonds="OPCVM"),
        GecoFundRow(code_amf="C1", denomination="Fonds Gamma", type_fonds="FIA"),
    ])

    assert n_creations == 1
    assert n_disparitions == 0


def test_events_are_recorded_and_can_be_marked_notified(conn: sqlite3.Connection) -> None:
    apply_snapshot(conn, [GecoFundRow(code_amf="A1", denomination="Fonds Alpha", type_fonds="OPCVM")])

    unnotified = db.get_unnotified_events(conn)
    assert len(unnotified) == 1
    assert unnotified[0]["event_type"] == "creation"

    db.mark_events_notified(conn, [unnotified[0]["id"]])
    assert db.get_unnotified_events(conn) == []
