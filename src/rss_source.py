"""Lecture du/des flux RSS de l'AMF pour capter les decisions (agrements,
retraits d'agrement) au plus pres de leur publication.

Ce module est complementaire au scraping GECO (src/geco_scraper.py) :
- GECO donne l'etat exhaustif "photo" a un instant donne (source de verite).
- Le RSS donne un signal plus rapide, mais son contenu texte libre ne
  garantit pas de contenir un code AMF/ISIN exploitable directement -> les
  entrees sont stockees telles quelles (rss_alerts) pour un rappel par email,
  a lire par un humain, plutot que d'etre fusionnees automatiquement avec la
  table `funds`.

L'URL exacte du flux (AMF_RSS_URL) doit etre recuperee manuellement sur
https://bdif.amf-france.org/En-plus/Abonnements-et-flux-RSS : cherche le flux
qui correspond aux decisions relatives aux OPCVM/FIA et colle son URL dans
.env. Si aucun flux ne cible precisement ce sujet, le flux general des
actualites reglementaires (https://www.amf-france.org/fr/flux-rss/display/31)
est un point de depart raisonnable, filtre ici par mots-cles.
"""
from __future__ import annotations

import logging

import feedparser

logger = logging.getLogger(__name__)

KEYWORDS = ("opcvm", "fia", "agrément", "agrement", "radiation", "retrait", "fonds")


def fetch_relevant_entries(feed_url: str) -> list[dict]:
    if not feed_url:
        logger.info("AMF_RSS_URL non configure, etape RSS ignoree.")
        return []

    parsed = feedparser.parse(feed_url)
    if parsed.bozo:
        logger.warning("Flux RSS %s : erreur de parsing (%s)", feed_url, parsed.bozo_exception)

    entries = []
    for entry in parsed.entries:
        title = getattr(entry, "title", "")
        summary = getattr(entry, "summary", "")
        haystack = f"{title} {summary}".lower()
        if any(kw in haystack for kw in KEYWORDS):
            entries.append(
                {
                    "guid": getattr(entry, "id", None) or getattr(entry, "link", title),
                    "title": title,
                    "link": getattr(entry, "link", ""),
                    "published": getattr(entry, "published", ""),
                }
            )
    logger.info("RSS : %d entrees pertinentes sur %d au total", len(entries), len(parsed.entries))
    return entries
