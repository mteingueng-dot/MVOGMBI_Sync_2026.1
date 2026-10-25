# MVOGMBI_Sync_2026.1

Synchronisation des ventes du point de vente **Clover** vers **Sage 50 Comptabilité, Édition canadienne** pour le Marché MVOG-MBI Sherbrooke.

Objectif : créer automatiquement, dans Sage 50, la facture de vente du client « Vente hebdomadaire » avec une ligne par article vendu (quantités et montants cumulés), à partir des ventes Clover d'un jour, d'une semaine ou d'un mois.

## État d'avancement

Le plan détaillé, étape par étape, est dans [TACHES.md](TACHES.md).

- [x] Cumul des ventes par article : jour, semaine (lundi → dimanche) ou mois
- [x] Lecture d'un export Excel Clover « Ventes d'articles »
- [x] Lecture directe par l'API Clover (à valider avec un vrai jeton)
- [x] Correspondance des articles Clover ↔ numéros d'articles Sage (proposition automatique, validation dans Excel)
- [ ] Génération du fichier d'import Sage 50 (`.IMP`, facture de vente)
- [ ] Protection contre l'import d'une même période en double, lancement automatique

## Installation

```bash
python -m pip install -r requirements.txt
```

Pour l'API Clover : copier `config.example.toml` en `config.toml` et y inscrire l'identifiant marchand et le jeton API. `config.toml` n'est jamais publié sur GitHub.

## Utilisation

```bash
# Une journée, depuis l'API Clover
python -m mvogmbi_sync rapport --periode jour --date 2026-01-15

# Une semaine, avec un cumul séparé par jour
python -m mvogmbi_sync rapport --periode semaine --date 2026-01-15 --par-jour

# Un mois, depuis un export Excel Clover
python -m mvogmbi_sync rapport --periode mois --date 2026-01-01 --export "Ventes Janvier 2026.xlsx"
```

```bash
# Correspondance des articles Clover -> Sage (fichier donnees/correspondance_articles.xlsx)
python -m mvogmbi_sync correspondance --sage "E:\Article.txt"
```

Le résultat s'affiche à l'écran et un fichier Excel de vérification est créé dans `sortie/`.

## Tests

```bash
python -m pytest
```

## Programme d'installation (Windows)

Fabrication (PyInstaller + Inno Setup) :

```bash
installation\fabriquer.cmd
```

Produit `dist\Installer_MVOGMBI_Sync_1.0.0.exe`, qui installe pour l'utilisateur courant (sans droits
d'administrateur) dans `%LOCALAPPDATA%\Programs\MVOGMBI_Sync` :

- `MVOGMBI_Sync.exe` : application de configuration et de suivi (onglets Clover, Sage 50, Courriel,
  Automatisation, Tableau de bord) ;
- `MVOGMBI_Sync_console.exe` : moteur lancé chaque nuit par la tâche planifiée (`auto`).

La configuration (`config.toml`) et les données (`donnees\`) sont dans le dossier d'installation ; les
secrets (jeton Clover, mots de passe) dans le coffre-fort de Windows. La désinstallation retire la tâche
planifiée et conserve les données.

## Traitement automatique

```bash
python -m mvogmbi_sync auto              # de la dernière facture « Vente AAAA-MM-JJ » dans Sage jusqu'à hier
python -m mvogmbi_sync auto --simulation # tout préparer et vérifier, sans importer
python -m mvogmbi_sync planifier --heure 01:00
python -m mvogmbi_sync interface
```

---

© 2026 Concept Informatique inc. Tous droits réservés.
