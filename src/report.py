"""Generation d'un dashboard HTML statique (publiable via GitHub Pages)."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from . import db

_TEMPLATE = """<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>Suivi OPCVM / FIA - Place de Paris</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  :root {{ color-scheme: light dark; }}
  body {{ font-family: system-ui, -apple-system, sans-serif; max-width: 900px; margin: 2rem auto; padding: 0 1rem; line-height: 1.5; }}
  h1 {{ font-size: 1.4rem; }}
  .stats {{ display: flex; gap: 1.5rem; margin: 1.5rem 0; }}
  .stat {{ background: color-mix(in srgb, currentColor 6%, transparent); border-radius: 8px; padding: 0.75rem 1.25rem; }}
  .stat b {{ display: block; font-size: 1.6rem; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 1rem; }}
  th, td {{ text-align: left; padding: 0.4rem 0.6rem; border-bottom: 1px solid color-mix(in srgb, currentColor 15%, transparent); font-size: 0.92rem; }}
  .creation {{ color: #1a7f37; }}
  .disparition {{ color: #b42318; }}
  footer {{ margin-top: 2rem; font-size: 0.8rem; opacity: 0.7; }}
</style>
</head>
<body>
  <h1>Suivi des OPCVM et FIA - Place de Paris</h1>
  <div class="stats">
    <div class="stat"><b>{n_opcvm}</b>OPCVM actifs</div>
    <div class="stat"><b>{n_fia}</b>FIA actifs</div>
    <div class="stat"><b>{n_events}</b>mouvements enregistres</div>
  </div>
  <h2>Derniers mouvements</h2>
  <table>
    <thead><tr><th>Date detection</th><th>Type</th><th>Fonds</th><th>Code AMF</th><th>Source</th></tr></thead>
    <tbody>
      {rows}
    </tbody>
  </table>
  <footer>Genere automatiquement - source : base GECO (AMF) et flux RSS AMF. Derniere execution : {generated_at}.</footer>
</body>
</html>
"""

_ROW_TEMPLATE = (
    '<tr><td>{detected_at}</td>'
    '<td class="{event_type}">{event_label}</td>'
    '<td>{denomination}</td><td>{code_amf}</td><td>{source}</td></tr>'
)


def _event_label(event_type: str) -> str:
    return "Creation" if event_type == "creation" else "Disparition"


def generate_report(conn: sqlite3.Connection, output_path: Path) -> None:
    counts = db.count_active_funds_by_type(conn)
    events = db.get_recent_events(conn, limit=200)

    rows_html = "\n      ".join(
        _ROW_TEMPLATE.format(
            detected_at=row["detected_at"],
            event_type=row["event_type"],
            event_label=_event_label(row["event_type"]),
            denomination=row["denomination"],
            code_amf=row["code_amf"],
            source=row["source"],
        )
        for row in events
    ) or "<tr><td colspan=\"5\">Aucun mouvement enregistre pour le moment.</td></tr>"

    html = _TEMPLATE.format(
        n_opcvm=counts.get("OPCVM", 0),
        n_fia=counts.get("FIA", 0),
        n_events=len(events),
        rows=rows_html,
        generated_at=db.now_iso(),
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
