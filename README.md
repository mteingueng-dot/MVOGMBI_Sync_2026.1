# MVOGMBI_Sync_2026.1

Application qui relie la caisse **Clover** à **Sage 50 Comptabilité, Édition canadienne** pour le Marché MVOG-MBI Sherbrooke : ventes facturées dans Sage chaque nuit, encaissements, factures et paiements fournisseurs, rapprochement bancaire, articles et stocks, comptabilité, agence RIA, paie, Reporting décisionnel. Application Windows (tkinter) et application web identique, sur un même serveur que Sage.

Version en service : **1.0.14** (13 novembre 2026).

## Fonctions principales

- **Ventes → Sage** : une facture de vente par jour du lundi au jeudi, une pour la fin de semaine (client « Vente Hebdomadaire », une ligne par article Sage), importée la nuit et vérifiée dans Sage.
- **Encaissements** : lots de cartes Clover, virements Interac et dépôts d'espèces appliqués sur les factures dans la fenêtre Encaissements de Sage.
- **Fournisseurs** : factures PDF, photos ou courriels lus (OCR de Windows, sans IA ni service externe), articles reliés, import dans Sage, stock et coût Clover ; notes de crédit et retours ; paiements rapprochés des avis Interac.
- **Rapprochement bancaire** de toutes les banques et caisses du Canada : relevés PDF, OFX / QFX / QBO ou CSV.
- **Articles et stocks** : correspondance Clover ↔ Sage, création d'articles dans les deux, inventaire, transferts entre dépôts, pertes, promotions, prix et marges, chaîne des documents de vente et d'achat.
- **Comptabilité** : caisse, dépenses, plan comptable, TPS / TVQ, budget, clôture, remises de retenues ; agence **RIA**.
- **Paie** : pointage par NIP (Wi-Fi du magasin), planning, feuilles de temps, chèques de paie dans Sage, bulletins, T4 / RL-1.
- **Reporting** : 18 états enrichis, 44 analyses décisionnelles, synthèse et décisions, courriel du matin.
- **Sécurité** : comptes, profils, droits par fonction, verrouillage, audit chaîné ; secrets dans le coffre-fort de Windows ; code analysé par SonarQube (0 bug, 0 vulnérabilité, notes A).

## Documentation

| Document | Contenu |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Composants, données, flux, pilotage de Sage, sécurité, déploiement |
| [documentation/DOCUMENTATION_FONCTIONNELLE.md](documentation/DOCUMENTATION_FONCTIONNELLE.md) | Ce que fait l'application, écran par écran |
| [documentation/GUIDE_ADMINISTRATEUR.md](documentation/GUIDE_ADMINISTRATEUR.md) | Installation, configuration, exploitation, dépannage |
| [documentation/REGLES_AFFAIRES.md](documentation/REGLES_AFFAIRES.md) | Règles d'affaires (codes RG-…) |
| [documentation/WORKFLOWS.md](documentation/WORKFLOWS.md), [documentation/PROCESSUS_BPM.md](documentation/PROCESSUS_BPM.md) | Parcours d'utilisation et processus métier |
| [documentation/CATALOGUE_REPORTING.md](documentation/CATALOGUE_REPORTING.md) | Tous les rapports du Reporting |
| [documentation/PLAN_DE_TEST.md](documentation/PLAN_DE_TEST.md) | Stratégie, tests automatiques, essais, couverture |
| [documentation/PROJET.md](documentation/PROJET.md), [documentation/NOTES_DE_VERSION.md](documentation/NOTES_DE_VERSION.md) | Planning, jalons, risques ; notes de chaque version |
| [documentation/ANALYSE_SECURITE.md](documentation/ANALYSE_SECURITE.md) | Analyse de sécurité du code (SonarQube, Bandit, pip-audit) et corrections |
| [documentation/PRESENTATION_SERVICES.md](documentation/PRESENTATION_SERVICES.md) | Présentation des services remise au client |

Les PDF, les versions Word, les manuels d'utilisation (français et anglais) et la présentation PowerPoint sont produits par `installation\fabriquer.cmd` et installés avec l'application.

## Développement

```bash
python -m pip install -r requirements.txt
python -m pytest
powershell -ExecutionPolicy Bypass -File installation\analyse_sonarqube.ps1   # analyse SonarQube (Docker)
```

Copier `config.example.toml` en `config.toml` (jamais publié). Les secrets (jeton Clover, mots de passe) vont dans le coffre-fort de Windows par les pages d'administration.

Commandes utiles (`python -m mvogmbi_sync …`) :

```bash
python -m mvogmbi_sync interface                                   # application Windows
python -m mvogmbi_sync web --port 8765                             # application web
python -m mvogmbi_sync auto --depuis 2026-11-01 --jusqua 2026-11-12  # ventes d'une période vers Sage
python -m mvogmbi_sync facture --periode jour --date 2026-11-12    # fichier d'import Sage seulement
python -m mvogmbi_sync encaissements --du 2026-11-01 --au 2026-11-12
python -m mvogmbi_sync correspondance                              # articles Clover -> Sage
```

## Fabrication et installation

```bash
installation\fabriquer.cmd
```

Produit `dist\Installer_MVOGMBI_Sync_x.y.z.exe` (serveur : application Windows, console du traitement de nuit, serveur web, documents) et `dist\Installer_MVOGMBI_Sync_Client_x.y.z.exe` (postes, sans droits d'administrateur). Voir le guide de l'administrateur pour la mise en service.

Ne jamais publier `config.toml`, `donnees/`, `sortie/`, les exports Excel ni les relevés bancaires.

---

© 2026 Concept Informatique inc. Tous droits réservés.
