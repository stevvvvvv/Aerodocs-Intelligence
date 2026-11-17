# Données

## Corpus de démonstration (fictif)

`data/demo/` est généré par `backend/scripts/make_demo_pdfs.py`. L'avion (« AD-200 »), le composant, les valeurs et les références sont **inventés**, et chaque page porte la mention *FICTITIOUS DEMO DOCUMENT – NOT FOR OPERATIONAL USE*. Le corpus est conçu pour exercer chaque fonctionnalité de façon contrôlée :

| Fichier | Rôle |
|---|---|
| AMM-32-11_RevA.pdf | Révision remplacée (intervalle 600 FH, couple 85 N.m) |
| AMM-32-11_RevB.pdf | Révision en vigueur (500 FH, 90 N.m, nouvelle section 3.3) : versions et diff |
| SB-32-014.pdf | Bulletin de service qui impose 400 FH : contradiction avec la révision B |
| AMM-29-10_RevC.pdf | Autre système (hydraulique), sert de distracteur pour la recherche |

## Documentation publique EASA

Toutes ces publications sont téléchargeables gratuitement sur easa.europa.eu. Vérifiez les conditions d'utilisation de chaque document avant de le redistribuer : seuls les scripts sont versionnés dans ce dépôt, pas les PDF (voir `.gitignore`).

| Document | Intérêt pour le projet |
|---|---|
| Easy Access Rules for Continuing Airworthiness (Regulation (EU) No 1321/2014) : révisions de juillet 2024 et de septembre 2025 | Part-M, Part-145, Part-CAMO, Part-66. Plus de 1 000 pages, plusieurs révisions publiques : idéal pour tester les versions |
| Easy Access Rules for Initial Airworthiness (Regulation (EU) No 748/2012) | Part-21, certification |
| Easy Access Rules for Additional Airworthiness Specifications (Part-26) | Corpus plus court, utile pour itérer vite |
| Consignes de navigabilité (ad.easa.europa.eu) | Documents courts liés à un composant : le cas d'usage « conditions de maintenance d'un composant » |

Procédure :

1. Téléchargez les PDF depuis la bibliothèque documentaire EASA (Document Library, puis Easy Access Rules) et placez-les dans `data/raw/`.
2. Créez `data/raw/manifest.json` (le format est indiqué en tête de `backend/scripts/import_folder.py`), avec la même `family` pour toutes les révisions d'un même document et la date de publication indiquée par EASA.
3. `python backend/scripts/import_folder.py data/raw --api http://localhost:8000`

Ordre de grandeur : un EAR de 1 265 pages produit plusieurs milliers de passages : avec e5-small sur CPU, l'import d'une révision prend plusieurs minutes.
