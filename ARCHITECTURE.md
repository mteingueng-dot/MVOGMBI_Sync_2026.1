# MVOGMBI_Sync — Document d'architecture

Version 1.9.26 — Marché MVOG-MBI Sherbrooke.

MVOGMBI_Sync relie la caisse **Clover** à la comptabilité **Sage 50 Comptabilité Édition canadienne** :

- facturation des ventes ;
- encaissement des dépôts ;
- factures et paiements fournisseurs ;
- rapprochement bancaire Desjardins ;
- rapports et statistiques.

L'application est écrite en Python 3.13, a une interface tkinter et tourne sur le poste Windows du marché. Elle n'utilise aucun service d'IA ni d'API externe autre que Clover : c'est le choix du propriétaire.

Ce document décrit les composants, les données, les intégrations et les principaux flux. Le fichier `CLAUDE.md` détaille les règles de gestion. Le manuel d'utilisation (`documentation/creer_manuel.py`) décrit l'usage au quotidien.

---

## 1. Vue d'ensemble

```mermaid
flowchart LR
    subgraph Externes["Sources externes"]
        CL["Clover<br/>API REST v3"]
        BX["Boîte courriel<br/>IMAP : avis Interac"]
        DJ["Relevés Desjardins<br/>PDF AccèsD"]
        FF["Factures fournisseurs<br/>PDF et photos"]
    end
    subgraph Poste["Poste Windows du marché"]
        UI["Interface tkinter<br/>interface.py + pages"]
        CLI["Ligne de commande<br/>python -m mvogmbi_sync"]
        NUIT["Traitement de nuit<br/>automatique.py"]
        COEUR["Cœur métier<br/>facture, encaissements,<br/>fournisseurs, rapprochement,<br/>rapports, statistiques"]
        DON[("donnees/<br/>registres JSON, caches,<br/>correspondance Excel, journaux")]
        COF[("Coffre-fort Windows<br/>keyring MVOGMBI_Sync")]
    end
    subgraph Sage["Sage 50 CA"]
        MY[("Base MySQL locale<br/>port 13540, base simply")]
        IMP["Sage_SA_import.exe<br/>fichiers .IMP"]
        FEN["Fenêtres de Sage<br/>Encaissements, Paiements,<br/>Journal général"]
    end
    SMTP["Serveur SMTP<br/>compte rendu"]
    TS["Planificateur de tâches<br/>Windows"]

    CL --> COEUR
    BX --> COEUR
    DJ --> COEUR
    FF --> COEUR
    UI --> COEUR
    CLI --> COEUR
    TS --> NUIT --> COEUR
    COEUR <--> DON
    COEUR --> COF
    COEUR -- "lecture seule" --> MY
    COEUR -- "factures de vente et d'achat" --> IMP --> MY
    COEUR -- "messages Windows" --> FEN --> MY
    NUIT --> SMTP
```

Principes :

| Principe | Mise en œuvre |
|---|---|
| Sage fait foi | Après chaque écriture, l'application relit Sage pour vérifier : présence de la facture dans `tcustr`, baisse du solde, écriture au compte 1055. `Sage_SA_import.exe` renvoie 0 même en cas d'échec. |
| Jamais deux fois | Les doublons sont détectés avant chaque import ou saisie : n° de facture, source, date et montant. En cas de doute, l'application refuse, sauf avec `--forcer`. |
| Le propriétaire confirme | La correspondance des articles, les virements proposés et les mouvements de banque passent par un état « Confirmé » avant toute écriture automatique. |
| Lecture seule par défaut | L'utilisateur MySQL `mvogmbi_sync` de Sage n'a que des droits de consultation. |
| Secrets hors des fichiers | Jeton Clover et mots de passe Sage, courriel et boîte : coffre-fort Windows (`coffre.py`). |
| Essais sur copie | Tout nouveau format est validé sur `MVOGMBI_ESSAI.SAI` avant le vrai fichier d'entreprise. |

---

## 2. Composants

### 2.1 Points d'entrée

| Point d'entrée | Rôle |
|---|---|
| `MVOGMBI_Sync.exe` (`installation/lanceur_interface.py`) | Interface : connexion, puis les pages 1 à 11. |
| `MVOGMBI_Sync_console.exe` (`installation/lanceur_console.py`) | Ligne de commande et tâche planifiée (`lancer_traitement.cmd`). |
| `python -m mvogmbi_sync <commande>` (`__main__.py`) | `facture`, `importer`, `auto`, `encaissements`, `correspondance`, `verifier-comptes`, `verifier-sage`, `rapport`, `planifier`, `langue`, `interface`. Commandes internes : `encaisser-bureau`, `payer-bureau`, `journal-bureau`. |

### 2.2 Modules

```mermaid
flowchart TB
    subgraph Présentation
        interface["interface.py<br/>fenêtre, menu, verrouillage"]
        connexion["connexion.py<br/>connexion, Verrou"]
        pages["page_correspondance · page_encaissements<br/>page_fournisseurs · page_paiements<br/>page_rapprochement · page_rapports<br/>page_utilisateurs"]
        design["design.py · graphiques.py<br/>export_tableau.py · aide.py · langues.py"]
    end
    subgraph Métier
        ventes["models · periodes · facture<br/>correspondance · verification_comptes"]
        enc["encaissements"]
        four["factures_fournisseurs · fournisseurs<br/>import_achats · paiements_fournisseurs"]
        rap["rapprochement"]
        stats["rapports · statistiques_clover<br/>couts_sage · previsions · peremption"]
        nuit["automatique · courriel · planification"]
    end
    subgraph Intégration
        clover["api_clover · export_clover"]
        sagel["base_sage · articles_sage"]
        sagei["import_sage · sage_auto"]
        robots["sage_bureau · robot_encaissements<br/>robot_paiements · robot_journal"]
        autres["paiements_courriel IMAP · ocr_windows<br/>coffre · utilisateurs"]
    end
    interface --> connexion
    interface --> pages --> design
    pages --> ventes & enc & four & rap & stats
    nuit --> ventes & enc & four & stats
    ventes --> clover & sagel & sagei
    enc --> clover & sagel & robots
    four --> sagel & sagei & robots & autres
    rap --> sagel & robots
    stats --> clover & sagel
```

| Couche | Modules | Responsabilité |
|---|---|---|
| Présentation | `interface.py` | Fenêtre principale, menu des pages selon le profil, verrouillage après inactivité, tâches de fond. |
| | `connexion.py` | Connexion, création du premier administrateur, fenêtre `Verrou`. |
| | `page_*.py` | Une page par module. |
| | `graphiques.py` | Graphiques sur `tk.Canvas` (barres, courbes, anneau, classement, carte de chaleur, infobulles, export PDF/PNG). |
| | `export_tableau.py` | Export Excel, CSV et PDF (HTML imprimé par Edge sans fenêtre). |
| | `design.py` | Couleurs, boutons, tableaux. |
| | `aide.py`, `langues.py` | Aide et FAQ en français et en anglais ; traduction. |
| Métier | `facture.py`, `periodes.py`, `models.py` | Factures de vente : une par jour du lundi au jeudi, une pour la fin de semaine. |
| | `correspondance.py`, `verification_comptes.py` | Articles Clover → Sage ; comptes 15xx → 40xx / 50xx. |
| | `encaissements.py` | Dépôts Clover (lots), espèces (Interac, dépôts au guichet) → encaissements sur les factures. |
| | `factures_fournisseurs.py`, `fournisseurs.py`, `import_achats.py` | Lecture des factures fournisseurs, registre, import `<PurInvoice>`. |
| | `paiements_fournisseurs.py` | Avis Interac → factures fournisseurs → paiements. |
| | `rapprochement.py` | Relevé Desjardins ↔ écritures du compte 1055. |
| | `rapports.py` | Suivi des ventes et recherches dans l'historique Sage. |
| | `statistiques_clover.py`, `couts_sage.py`, `previsions.py`, `peremption.py` | Statistiques Clover, bénéfices au CUMP Sage, prévisions, péremption. |
| | `automatique.py`, `courriel.py`, `planification.py` | Traitement de nuit, compte rendu, tâche planifiée. |
| Intégration | `api_clover.py`, `export_clover.py` | API REST Clover v3 (parallélisée) ; export Excel Clover. |
| | `base_sage.py`, `articles_sage.py` | Lecture MySQL de Sage, même quand Sage est fermé (`lire_pendant_connexion`). |
| | `import_sage.py`, `sage_auto.py` | Fichier `.IMP` `<SalInvoice>` ; pilotage de `Sage_SA_import.exe`. |
| | `sage_bureau.py`, `robot_*.py` | Ouverture de Sage sur un bureau Windows séparé et saisie dans ses fenêtres par messages Windows. |
| | `paiements_courriel.py`, `ocr_windows.py` | IMAP en lecture seule ; OCR intégré à Windows. |
| | `coffre.py`, `utilisateurs.py` | Coffre-fort Windows ; comptes et profils, avec mots de passe hachés. |

---

## 3. Données

```mermaid
flowchart LR
    subgraph Racine["Dossier de l'application (RACINE)"]
        CFG["config.toml<br/>réglages, sans secret"]
        subgraph donnees["donnees/ (jamais publié)"]
            CORR["correspondance_articles.xlsx"]
            REGF["factures_fournisseurs.json<br/>+ dossier des PDF"]
            REGP["paiements_fournisseurs.json"]
            REL["releves_desjardins/releves.json"]
            CACHE["cache_clover/AAAA-MM-JJ.json<br/>couts_sage.json"]
            USR["utilisateurs.json"]
            JRN["journal_imports.csv<br/>journal_automatique.log<br/>journal_connexions.log"]
        end
        SORT["sortie/factures/*.IMP + détail Excel"]
    end
```

| Donnée | Format | Écrite par | Lue par |
|---|---|---|---|
| Réglages | `config.toml` | page Configuration | tous les modules |
| Secrets | coffre-fort Windows | pages Clover, Sage, Courriel | `coffre.py` |
| Correspondance Clover → Sage | Excel (« Confirmé » par le propriétaire) | `correspondance.py` | facture, coûts, statistiques |
| Registres fournisseurs, paiements, relevés | JSON | pages 8, 9, 10 | traitement de nuit, rapports |
| Ventes Clover par jour | JSON, cache, plus mémoire vive | `statistiques_clover.py` | statistiques, prévisions |
| CUMP Sage | JSON, renouvelé chaque jour | `couts_sage.py` | bénéfices, liste d'articles |
| Utilisateurs | JSON, empreintes PBKDF2 | `utilisateurs.py` | connexion, verrou |
| Journaux | CSV, texte | import, nuit, connexion | tableau de bord, courriel |

Tables Sage lues :

| Table | Contenu |
|---|---|
| `tcustr`, `tcustrdt` | Factures et encaissements clients |
| `tvendor`, `tventr`, `tventrdt` | Fournisseurs, factures et paiements |
| `tinvent`, `tinvlot` | Articles, coûts et stock |
| `tjentact`, `tjourent`, `taccount` | Écritures et comptes |
| `ttaxauth` | Taxes |

---

## 4. Flux principaux

### 4.1 Traitement de nuit (`automatique.lancer`)

```mermaid
flowchart TD
    A(["Tâche planifiée Windows, ex. 1 h"]) --> B{"Verrou<br/>traitement.verrou<br/>de moins de 6 h ?"}
    B -- oui --> Z1["Exécution annulée,<br/>notée au journal"]
    B -- non --> C["1. Lecture de Sage<br/>dernières factures « Vente … »,<br/>articles, comptes, client"]
    C --> D["2. Correspondance<br/>nouveaux articles Clover"]
    D --> E["3. Préparation des jours manquants<br/>lun.–jeu. : 1 facture par jour<br/>ven.–dim. : 1 facture"]
    E --> F{"Jour bloqué ?<br/>article non relié,<br/>compte manquant"}
    F -- oui --> G["Jour ou fin de semaine mis de côté,<br/>repris la nuit suivante"]
    F -- non --> H["4. Import par lots<br/>.IMP → Sage_SA_import.exe"]
    H --> I["Vérification dans tcustr"]
    I --> J["5. Encaissements<br/>ventes importées cette nuit seulement"]
    J --> K["6. Paiements fournisseurs<br/>« Confirmé » seulement"]
    G --> K
    K --> L["Préchauffage du cache<br/>statistiques des 7 derniers jours"]
    L --> M["Journal<br/>+ courriel avec pièces jointes Excel"]
```

### 4.2 Facturation des ventes (Clover → Sage)

```mermaid
sequenceDiagram
    participant P as Application
    participant C as API Clover
    participant X as Correspondance
    participant S as Sage MySQL
    participant I as Sage_SA_import.exe
    P->>C: commandes de la période (clientCreatedTime, 6 en parallèle)
    C-->>P: commandes, lignes, rabais, remboursements, paiements
    P->>P: cumul par article (ventes nettes, quantité au millième)
    P->>X: article Clover → n° Sage (ID Clover, puis nom)
    P->>S: facture déjà présente ? comptes de produits ?
    alt point à vérifier ou doublon
        P-->>P: refus, l'anomalie est signalée
    else prête
        P->>P: écrire Vente_….IMP (SalInvoice, taxes GQ, payer plus tard)
        P->>I: Sage_SA_import.exe fichier.IMP entreprise.SAI
        I->>S: facture de vente
        P->>S: relecture de tcustr : facture présente ?
    end
```

Règle : montant de ligne = ventes nettes Clover de l'article ; prix = montant ÷ quantité nette (4 décimales) ; total = ventes nettes.

### 4.3 Encaissements

```mermaid
flowchart TD
    L["Lots Clover<br/>fermés à 21 h 32"] --> D["Dépôt attendu<br/>= encaissé − espèces"]
    R["Relevé Desjardins<br/>page 10"] --> E["Espèces des ventes<br/>Interac reçus, dépôts au guichet"]
    D --> A["Affectation<br/>lun.–jeu. : facture du jour<br/>ven.–dim. : facture de fin de semaine"]
    E --> A2["Interac : facture du jour<br/>Guichet : factures avec espèces dues,<br/>la plus ancienne d'abord"]
    A & A2 --> V{"Déjà dans Sage ?<br/>tcustrdt, compte 1055"}
    V -- non --> W["Saisie dans la fenêtre Encaissements<br/>Comptant, date du dépôt,<br/>contrôle du total avant Traiter"]
    W --> Y["Vérification :<br/>baisse du solde de la facture"]
    V -- oui --> OK["Appliqué"]
```

### 4.4 Factures et paiements fournisseurs

```mermaid
flowchart TD
    P1["PDF ou photo déposé<br/>page 8"] --> P2{"PDF numérique ?"}
    P2 -- oui --> P3["pdfplumber<br/>+ modèle du fournisseur"]
    P2 -- non --> P4["OCR intégré à Windows"]
    P3 & P4 --> P5["Contrôle des totaux<br/>doublon : n° avec ou sans préfixe"]
    P5 --> P6["Articles Sage + facteur<br/>mémoire par fournisseur<br/>Qté Sage = Qté × Facteur"]
    P6 --> P7["import_achats : PurInvoice<br/>→ Sage_SA_import.exe → vérification"]
    M1["Avis Interac<br/>boîte IMAP, lecture seule"] --> M2["Rapprochement proposé<br/>fournisseur, montant, n° cités"]
    M2 --> M3["Confirmé par le propriétaire<br/>page 9"]
    M3 --> M4["Répartition : plus ancienne d'abord,<br/>jamais plus que le solde"]
    M4 --> M5["Fenêtre Paiements de Sage<br/>une ligne par facture, un seul Traiter"]
    M5 --> M6["Vérification : baisse du solde"]
    P7 -.-> M2
```

### 4.5 Rapprochement bancaire

```mermaid
flowchart TD
    R1["Relevé PDF Desjardins"] --> R2["Lecture par colonnes<br/>Frais, Retrait, Dépôt, Solde<br/>chaque solde revérifié"]
    S1["Sage : tjentact + tjourent<br/>compte 1055"] --> R3
    R2 --> R3{"Même montant,<br/>date de −7 à +3 jours,<br/>ou somme de 2–3 écritures"}
    R3 -- trouvé --> R4["Rapproché"]
    R3 -- "Interac reçu ou guichet" --> R5["À encaisser sur les ventes<br/>voir 4.3"]
    R3 -- "salaire" --> R6["Relié aux paies Sage<br/>sinon Paie absente"]
    R3 -- "frais, prélèvement" --> R7["Écriture de journal<br/>fenêtre Journal général,<br/>source « Relevé AAAA-MM-JJ »"]
    R4 & R5 & R6 & R7 --> R8["Écart = ouverture + absents − en circulation"]
```

### 4.6 Rapports et statistiques Clover

```mermaid
flowchart TD
    Q["Période choisie<br/>+ filtres : article, client,<br/>employé, catégorie"] --> M{"Jours en mémoire<br/>ou dans le cache ?"}
    M -- oui --> P["Préparation, mémorisée"]
    M -- non --> F["Lecture Clover<br/>blocs de 31 jours, 3 en parallèle"] --> C[("cache_clover/AAAA-MM-JJ.json")] --> P
    K[("couts_sage.json<br/>CUMP du jour")] --> P
    P --> V["États : Accueil, Aperçu des ventes, Rapport des ventes,<br/>Évolution par année, Carte de chaleur, Bénéfices,<br/>Aperçu financier (KPI), Articles, Employés, Clients"]
    P --> PR["Prévisions et péremption"]
    V --> G["Tableaux : date la plus récente en haut<br/>Graphiques : infobulles, axe ajusté"]
    G --> X["Exports : Excel, CSV, PDF du tableau,<br/>PDF de la page, PDF ou PNG d'un graphique"]
```

### 4.7 Connexion, profils et verrouillage

```mermaid
stateDiagram-v2
    [*] --> Connexion
    Connexion --> CréationAdmin: premier lancement
    CréationAdmin --> Ouverte
    Connexion --> Ouverte: nom + mot de passe valides
    Ouverte --> Verrouillée: 5 min sans souris ni clavier
    Verrouillée --> Ouverte: mot de passe de la personne connectée
    Verrouillée --> Connexion: changer d'utilisateur
    Ouverte --> [*]: fermeture
    note right of Ouverte
        Pages visibles selon le profil
        Administrateur, Comptable, Employé
        Les traitements en cours continuent
    end note
```

---

## 5. Pilotage de Sage

Sage 50 CA n'a pas d'API ouverte. L'application passe par trois voies :

| Voie | Utilisée pour | Sage | Vérification |
|---|---|---|---|
| MySQL en lecture seule (`base_sage.py`) | Tout ce qui se lit | ouvert, ou base ouverte par l'outil d'import pendant la fenêtre de mot de passe | — |
| `Sage_SA_import.exe` (`sage_auto.py`) | Factures de vente `<SalInvoice>` et d'achat `<PurInvoice>` | fermé (accès exclusif) | présence dans `tcustr` / `tventr` |
| Fenêtres de Sage (`sage_bureau.py` + `robot_*.py`) | Encaissements, paiements, journal général (non importables) | lancé par l'application sur un bureau Windows séparé ; fonctionne session verrouillée | baisse des soldes, écriture au 1055 |

```mermaid
sequenceDiagram
    participant N as Traitement de nuit
    participant B as sage_bureau
    participant S as Sage50Accounting.exe
    participant R as robot_encaissements
    participant DB as MySQL Sage
    N->>B: commande interne encaisser-bureau
    B->>S: lancement sur le bureau « MVOGMBI_Robot »
    B->>S: Ouvrir un fichier → mot de passe (coffre-fort)
    B->>S: icône Encaissements
    R->>S: client, date, montants (messages Windows, jamais Tab)
    R->>S: contrôle du total puis Traiter
    R->>DB: tcustrdt : encaissement présent ?
    B->>S: fermeture de Sage
```

---

## 6. Sécurité

| Sujet | Mesure |
|---|---|
| Secrets | Coffre-fort Windows (keyring `MVOGMBI_Sync`) : `clover_jeton`, `sage_lecture`, `sage_import`, `courriel`, boîte des paiements. Jamais dans `config.toml` ni dans le dépôt. |
| Comptes | `utilisateurs.json` : empreintes de mots de passe, profils et pages permises ; journal des connexions. |
| Verrouillage | Après `[general] verrouillage_minutes` (5 par défaut ; 0 = jamais) sans activité. La fenêtre est cachée et le mot de passe est redemandé. |
| Sage | Utilisateur MySQL en consultation seule ; imports et saisies uniquement après contrôle des doublons. |
| Banque | Relevés chargés à la main : aucune connexion à AccèsD. |
| Courriel | IMAP en lecture seule ; SMTP pour le compte rendu. |
| Dépôt public | `.gitignore` : `config.toml`, `donnees/`, `sortie/`, `*.xlsx`, `*.IMP`, `*.SAI`, captures et manuels contenant des données réelles. |

---

## 7. Fabrication et déploiement

```mermaid
flowchart TD
    SRC["Sources Python<br/>mvogmbi_sync/"] --> T["python -m pytest"]
    T --> PY["PyInstaller<br/>MVOGMBI_Sync.spec :<br/>2 exe dans un dossier"]
    DOC["documentation/<br/>captures → manuels fr/en<br/>architecture PDF"] --> INNO
    PY --> INNO["Inno Setup<br/>MVOGMBI_Sync.iss"]
    INNO --> SETUP["dist/Installer_MVOGMBI_Sync_x.y.z.exe"]
    SETUP --> POSTE["Poste du marché :<br/>%LOCALAPPDATA%/Programs/MVOGMBI_Sync<br/>raccourcis, manuels, tâche planifiée"]
```

- `installation/fabriquer.cmd` enchaîne tout. Chaque livraison a son propre numéro de version : `aide.VERSION`, `version_info.txt` et `MVOGMBI_Sync.iss`.
- RACINE est le dossier de l'exe ; la variable `MVOGMBI_RACINE` en force un autre.
- Tests : `tests/`, environ 110 tests sans accès à Clover ni à Sage. Les essais réels se font sur la copie `MVOGMBI_ESSAI.SAI`.

---

## 8. Performances

| Opération | Moyen | Ordre de grandeur |
|---|---|---|
| Commandes Clover d'une période | liste filtrée par `clientCreatedTime`, commandes manquantes 6 en parallèle | secondes par jour |
| Statistiques d'une année | blocs de 31 jours, 3 en parallèle, cache par jour | 49 s à froid, quelques secondes ensuite |
| Filtres globaux | recalcul en mémoire, sans relire Clover | environ 1 s |
| Recherches dans l'historique Sage | historique gardé 10 min | 0,3 s après la première |
| Ouverture des statistiques le matin | cache des 7 derniers jours préchauffé la nuit | immédiat |
