"""Chargement centralise de la configuration (variables d'environnement)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")


def _split_emails(raw: str) -> list[str]:
    return [e.strip() for e in raw.split(",") if e.strip()]


@dataclass(frozen=True)
class Settings:
    geco_url: str = field(default_factory=lambda: os.getenv(
        "GECO_URL", "https://geco.amf-france.org/liste-des-produits-d-epargne"
    ))
    amf_rss_url: str = field(default_factory=lambda: os.getenv("AMF_RSS_URL", ""))

    database_path: Path = field(default_factory=lambda: ROOT_DIR / os.getenv(
        "DATABASE_PATH", "data/funds.db"
    ))

    smtp_host: str = field(default_factory=lambda: os.getenv("SMTP_HOST", ""))
    smtp_port: int = field(default_factory=lambda: int(os.getenv("SMTP_PORT", "587")))
    smtp_user: str = field(default_factory=lambda: os.getenv("SMTP_USER", ""))
    smtp_password: str = field(default_factory=lambda: os.getenv("SMTP_PASSWORD", ""))
    email_from: str = field(default_factory=lambda: os.getenv("EMAIL_FROM", ""))
    email_to: list[str] = field(default_factory=lambda: _split_emails(os.getenv("EMAIL_TO", "")))

    report_output_path: Path = field(default_factory=lambda: ROOT_DIR / os.getenv(
        "REPORT_OUTPUT_PATH", "docs/index.html"
    ))


settings = Settings()
