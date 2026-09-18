# Suivi OPCVM / FIA - Place de Paris

Détecte automatiquement la création et la disparition (radiation) des OPCVM
et FIA de droit français, et prévient les associés par email + un dashboard
web statique.

## Comment ça marche

1. **`src/geco_scraper.py`** parcourt la [base GECO de l'AMF](https://geco.amf-france.org/liste-des-produits-d-epargne),
   qui liste tous les OPC (OPCVM et FIA) et sert de photo de référence.
2. **`src/rss_source.py`** lit en complément le flux RSS des décisions AMF
   (agréments/retraits), pour un signal plus rapide - à vérifier à la main
   car le texte libre du RSS ne contient pas toujours un code exploitable
   automatiquement.
3. **`src/diff_engine.py`** compare le nouveau relevé GECO à l'état stocké en
   base SQLite (`data/funds.db`) : un fonds inconnu jusqu'ici = une
   *création* ; un fonds actif qui disparaît du relevé = une *disparition*.
4. **`src/notifier.py`** envoie un email récapitulatif s'il y a du nouveau.
5. **`src/report.py`** régénère `docs/index.html`, un dashboard statique
   consultable (historique des mouvements, compteurs par type de fonds).
6. **`.github/workflows/check.yml`** exécute tout ça automatiquement toutes
   les 4 heures via GitHub Actions (gratuit), et republie le dashboard sur
   GitHub Pages.

## ⚠️ Ce qui reste à finaliser avant la première utilisation réelle

Ce projet a été structuré sans accès réseau complet au site GECO depuis
l'environnement où il a été rédigé - les sélecteurs CSS dans
`src/geco_scraper.py` sont une hypothèse de structure de tableau HTML
classique, **pas une vérification directe du vrai site**. Avant de compter
sur les résultats :

1. Lance `python scripts/run_check.py --dump-html` depuis un poste avec un
   accès internet normal.
2. Ouvre `data/debug_geco.html` et repère la vraie structure du tableau de
   résultats (ou l'appel réseau XHR/JSON sous-jacent si GECO en utilise un -
   souvent plus simple et plus robuste qu'un scraping HTML).
3. Ajuste les constantes `SELECTOR_*` en haut de `src/geco_scraper.py` en
   conséquence, et vérifie s'il y a une pagination à gérer.
4. Récupère l'URL exacte du flux RSS pertinent sur
   [bdif.amf-france.org/En-plus/Abonnements-et-flux-RSS](https://bdif.amf-france.org/En-plus/Abonnements-et-flux-RSS)
   et renseigne-la dans `.env` (`AMF_RSS_URL`).

Avant d'automatiser la collecte, vérifie aussi les conditions d'utilisation
du site GECO et reste raisonnable sur la fréquence des requêtes - c'est un
service public, pas une API pensée pour être interrogée en boucle.

## Installation locale

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
cp .env.example .env   # puis remplis les valeurs (voir ci-dessous)
python scripts/run_check.py
```

## Configuration (`.env`)

Voir `.env.example` pour la liste complète. Les points importants :

- `AMF_RSS_URL` : URL du flux RSS AMF pertinent (voir ci-dessus).
- `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASSWORD` : un relais SMTP
  quelconque. [Brevo](https://www.brevo.com) offre 300 emails/jour gratuits
  et un relais SMTP standard ; un compte Gmail avec un
  [mot de passe d'application](https://support.google.com/accounts/answer/185833)
  fonctionne aussi pour démarrer.
- `EMAIL_TO` : les adresses des trois associés, séparées par des virgules.

## Automatisation gratuite avec GitHub Actions

1. Dans les paramètres du dépôt GitHub (`Settings > Secrets and variables >
   Actions`), ajoute en **secrets** : `SMTP_HOST`, `SMTP_USER`,
   `SMTP_PASSWORD`, et en **variables** : `AMF_RSS_URL`, `EMAIL_FROM`,
   `EMAIL_TO`, `SMTP_PORT`.
2. Active GitHub Pages (`Settings > Pages`) en pointant sur le dossier
   `docs/` de la branche par défaut - c'est là que vit le dashboard généré.
3. Le workflow `.github/workflows/check.yml` tourne ensuite tout seul toutes
   les 4 heures, et peut aussi être lancé à la main depuis l'onglet
   *Actions* (`workflow_dispatch`).

## Tests

```bash
python -m pytest tests/ -q
```

Les tests couvrent la logique de détection création/disparition
(`src/diff_engine.py`) sans dépendre du réseau ni de GECO.

## Limites à garder en tête

- L'AMF publie ses décisions par lots, pas en flux continu : on parle de
  quasi temps réel (toutes les quelques heures), pas d'instantané.
- Un incident réseau ponctuel sur GECO ne doit pas se traduire par une
  fausse vague de "disparitions" - `scripts/run_check.py` ignore le diff si
  le nouveau relevé est anormalement plus petit que l'état connu
  (`MIN_SNAPSHOT_RATIO`), mais reste prudent sur les alertes des premiers
  jours d'utilisation.
- Le scraping GECO est par nature fragile face à une refonte du site AMF :
  si `run_check.py` se mette à échouer, `data/debug_geco.html` (option
  `--dump-html`) est le premier réflexe pour comprendre ce qui a changé.
