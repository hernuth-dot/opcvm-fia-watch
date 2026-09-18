"""Scraper de la base GECO (liste publique des OPC agrees par l'AMF).

IMPORTANT - a faire avant la premiere utilisation reelle :
GECO (https://geco.amf-france.org) est un site dynamique (rendu cote client).
Cette version n'a pas pu etre validee contre le vrai DOM du site depuis cet
environnement (acces reseau restreint dans ce sandbox), donc les selecteurs
CSS ci-dessous sont une hypothese raisonnable basee sur la structure typique
d'un tableau de resultats de recherche, PAS une verification directe.

Pour finaliser ce module :
  1. Lance `python scripts/run_check.py --dump-html` depuis une machine avec
     un acces internet normal (ton poste, ou le runner GitHub Actions).
  2. Ouvre data/debug_geco.html dans un navigateur ou un editeur, repere le
     vrai tableau de resultats et corrige les selecteurs SELECTOR_* ci-dessous.
  3. Verifie aussi s'il existe une pagination a gerer (voir _iter_pages).

Alternative si le scraping s'avere trop fragile : inspecter l'onglet Reseau
du navigateur pendant une recherche sur GECO peut reveler un appel XHR/JSON
interne plus simple a interroger que le HTML rendu.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)

# --- Selecteurs a confirmer/ajuster (voir note ci-dessus) ---
SELECTOR_RESULT_ROW = "table tbody tr"
SELECTOR_CELL_CODE = "td:nth-child(1)"
SELECTOR_CELL_NAME = "td:nth-child(2)"
SELECTOR_CELL_TYPE = "td:nth-child(3)"
SELECTOR_NEXT_PAGE = "a[rel='next'], .pagination .next"

NAV_TIMEOUT_MS = 45_000


@dataclass(frozen=True)
class GecoFundRow:
    code_amf: str
    denomination: str
    type_fonds: str  # normalise en 'OPCVM' ou 'FIA'


def _normalize_type(raw_type: str) -> str:
    raw = raw_type.upper()
    if "FIA" in raw:
        return "FIA"
    return "OPCVM"


def scrape_geco(url: str, dump_html_path: str | None = None, max_pages: int = 500) -> list[GecoFundRow]:
    """Parcourt la liste des OPC sur GECO et retourne un snapshot complet.

    max_pages est un garde-fou pour eviter une boucle infinie si la
    pagination ne se termine pas comme prevu.
    """
    results: list[GecoFundRow] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, timeout=NAV_TIMEOUT_MS, wait_until="networkidle")

        if dump_html_path:
            with open(dump_html_path, "w", encoding="utf-8") as f:
                f.write(page.content())
            logger.info("HTML de debug ecrit dans %s", dump_html_path)

        for page_index in range(max_pages):
            rows = page.query_selector_all(SELECTOR_RESULT_ROW)
            if not rows:
                logger.warning("Aucune ligne trouvee avec le selecteur %s (page %d)", SELECTOR_RESULT_ROW, page_index)
                break

            for row in rows:
                code_el = row.query_selector(SELECTOR_CELL_CODE)
                name_el = row.query_selector(SELECTOR_CELL_NAME)
                type_el = row.query_selector(SELECTOR_CELL_TYPE)
                if not (code_el and name_el):
                    continue
                code = code_el.inner_text().strip()
                name = name_el.inner_text().strip()
                type_raw = type_el.inner_text().strip() if type_el else ""
                if not code:
                    continue
                results.append(GecoFundRow(code_amf=code, denomination=name, type_fonds=_normalize_type(type_raw)))

            next_btn = page.query_selector(SELECTOR_NEXT_PAGE)
            if not next_btn or not next_btn.is_enabled():
                break
            next_btn.click()
            page.wait_for_load_state("networkidle", timeout=NAV_TIMEOUT_MS)

        browser.close()

    logger.info("GECO : %d fonds recuperes", len(results))
    return results
