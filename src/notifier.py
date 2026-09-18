"""Envoi d'un email recapitulatif via SMTP generique.

Fonctionne avec n'importe quel relais SMTP (Brevo/Sendinblue en gratuit
jusqu'a 300 emails/jour, Gmail avec un mot de passe d'application, un
relais interne...). Voir .env.example pour les variables a renseigner.
"""
from __future__ import annotations

import logging
import smtplib
from email.mime.text import MIMEText

from .config import Settings

logger = logging.getLogger(__name__)


def build_email_body(creation_events: list[dict], disparition_events: list[dict], rss_alerts: list[dict]) -> str:
    lines = ["Mouvements detectes sur les OPCVM / FIA (place de Paris) :", ""]

    if creation_events:
        lines.append(f"Nouveaux fonds ({len(creation_events)}) :")
        for e in creation_events:
            lines.append(f"  - [{e['type_fonds']}] {e['denomination']} (code AMF : {e['code_amf']})")
        lines.append("")

    if disparition_events:
        lines.append(f"Fonds disparus / radies ({len(disparition_events)}) :")
        for e in disparition_events:
            lines.append(f"  - [{e['type_fonds']}] {e['denomination']} (code AMF : {e['code_amf']})")
        lines.append("")

    if rss_alerts:
        lines.append(f"Decisions AMF signalees par RSS a verifier manuellement ({len(rss_alerts)}) :")
        for a in rss_alerts:
            lines.append(f"  - {a['title']} -> {a['link']}")
        lines.append("")

    lines.append("(Genere automatiquement - voir le dashboard pour l'historique complet.)")
    return "\n".join(lines)


def send_email(settings: Settings, subject: str, body: str) -> None:
    if not settings.smtp_host or not settings.email_to:
        logger.info("Config SMTP incomplete, email non envoye (voir .env).")
        return

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = settings.email_from
    msg["To"] = ", ".join(settings.email_to)

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
        server.starttls()
        if settings.smtp_user:
            server.login(settings.smtp_user, settings.smtp_password)
        server.sendmail(settings.email_from, settings.email_to, msg.as_string())

    logger.info("Email envoye a %s", settings.email_to)
