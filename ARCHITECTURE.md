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
        pages["page_correspondance · page_encaissements<br/>page_fournisseurs · page_paiements<br/>page_rapprochement · page_rapports<br/>page_utilisateurs · page_points_vente"]
        design["design.py · graphiques.py<br/>export_tableau.py · entreprise.py · aide.py · langues.py"]
    end
    subgraph Métier
        ventes["models · periodes · facture<br/>correspondance · verification_comptes<br/>points_vente"]
        enc["encaissements"]
        four["factures_fournisseurs · fournisseurs<br/>factures_courriel · import_achats<br/>paiements_fournisseurs"]
        rap["rapprochement"]
        stats["rapports · statistiques_clover<br/>couts_sage · previsions · peremption<br/>analyse_articles · onglets_articles"]
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
| | `export_tableau.py` | Liste « Exporter » : Excel, CSV, PDF (HTML imprimé par Edge sans fenêtre) et impression ; en-tête aux couleurs du marché ; droit d'exporter par profil. |
| | `entreprise.py` | Nom, adresse, téléphone et site web de l'entreprise lus dans Clover (une fois par jour) pour l'en-tête des impressions. |
| | `design.py` | Couleurs, boutons, tableaux. |
| | `aide.py`, `langues.py` | Aide et FAQ en français et en anglais ; traduction. |
| Métier | `facture.py`, `periodes.py`, `models.py` | Factures de vente : une par jour du lundi au jeudi, une pour la fin de semaine. |
| | `correspondance.py`, `verification_comptes.py` | Articles Clover → Sage ; comptes 15xx → 40xx / 50xx. |
| | `encaissements.py` | Dépôts Clover (lots), espèces (Interac, dépôts au guichet) → encaissements sur les factures. |
| | `factures_fournisseurs.py`, `fournisseurs.py`, `import_achats.py` | Lecture des factures fournisseurs, registre, import `<PurInvoice>`. |
| | `creation_articles.py`, `stock_clover.py` | Nouvel article dans Clover et Sage (comptes par catégorie) ; stock et coût Clover après l'import d'une facture fournisseur. |
| | `inventaire.py` | Inventaire Clover + Sage en un fichier ; saisie de l'inventaire compté dans les deux ; rapport du coût de l'ajustement. |
| | `fenetre_articles_clover.py` | Liste des articles Clover (date de péremption lue dans l'UGS ; UGS qui ne sont pas des dates effacées dans Clover après confirmation). |
| | `transferts.py`, `robot_transferts.py`, `fenetre_transferts.py` | Transferts de marchandises entre points de vente : transfert entre les deux dépôts Sage, puis stock Clover des deux marchands. |
| | `couts_clover.py`, `fenetre_couts.py`, `fenetre_cocher.py` | Coûts Clover remplacés par le coût moyen Sage (lignes cochées, sans valeur aberrante) ; comptes des articles Sage corrigés d'après la table catégorie -> comptes. |
| | `paiements_fournisseurs.py` | Avis Interac → factures fournisseurs → paiements. |
| | `rapprochement.py` | Relevé Desjardins ↔ écritures du compte 1055. |
| | `rapports.py` | Suivi des ventes et recherches dans l'historique Sage. |
| | `statistiques_clover.py`, `couts_sage.py`, `previsions.py`, `peremption.py` | Statistiques Clover, bénéfices au CUMP Sage, prévisions, péremption. |
| | `bons_commande.py`, `fenetre_bons_commande.py` | Fournisseur > Bons de commande : articles à commander, fournisseur et prix du dernier achat Sage, un bon PDF par fournisseur, comparaison avec la facture reçue. |
| | `prix_marges.py`, `fenetre_prix_marges.py` | Articles > Prix et marges : marge au CUMP Sage, prix proposé arrondi, mise à jour des prix Clover cochés. |
| | `paie_temps.py`, `fenetre_pointage.py`, `fenetre_feuilles_temps.py` | Paie : poste de pointage par NIP (commande `pointage`, raccourci « Pointage des employés »), feuilles de temps de 14 jours, heures supplémentaires, corrections avec motif, approbation, employés et NIP (empreintes seulement). |
| | `retenues.py` | Paie > Retenues à la source : retenues et cotisations du mois par compte de passif de Sage, versements, total à remettre par organisme (Revenu Québec, ARC, CNESST), échéance du 15. |
| | `comptabilite.py`, `fenetre_comptabilite.py` | Comptabilité : âge des comptes, déclaration TPS/TVQ, prévision de trésorerie, clôture du mois et état des résultats (lecture seule de Sage). |
| | `listes_sage.py`, `documents.py`, `fenetre_saisie.py`, `fenetre_gestion.py` | Gestion des ventes, achats et stocks (menus comme Sage) : listes des clients, fournisseurs, documents de vente, d'achat et de stock, articles, livre d'inventaire ; commandes clients, factures de vente (.IMP SalInvoice), documents de stock (ajustements), factures d'achat et bons saisis. |
| | `planning.py`, `fenetre_planning.py` | Paie > Planning mensuel du gérant, publication, « Mon horaire » de l'employé (compte relié) et au poste de pointage. |
| | `manuel.py` | Manuel d'utilisation du profil : chapitres des pages permises seulement, renumérotés, PDF par Edge dans donnees/manuels/. |
| | `resume_matin.py` | Résumé du matin en tête du courriel de nuit (ventes, marge, banque, factures à payer, ruptures, péremption). |
| | `analyse_articles.py`, `onglets_articles.py` | État > Produits inactifs (sans vente depuis N jours) et Articles 80/20 (classes A/B/C, stock et sa valeur) ; source Clover ou Sage. |
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
            CORR["correspondance_articles.xlsx<br/>points_vente/&lt;code&gt;/ (autres points de vente)"]
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
| `tinvloc` | Dépôts (emplacements d'inventaire) |
| `tjentact`, `tjourent`, `taccount` | Écritures et comptes |
| `ttaxauth` | Taxes |

---

## 4. Flux principaux

### 4.1 Traitement de nuit (`automatique.lancer`)

```mermaid
flowchart TD
    A(["Tâche planifiée Windows, ex. 1 h"]) --> B{"Verrou<br/>traitement.verrou<br/>de moins de 6 h ?"}
    B -- oui --> Z1["Exécution annulée,<br/>notée au journal"]
    B -- non --> C["1. Lecture de Sage (une fois)<br/>factures de chaque point de vente,<br/>articles, comptes, clients, dépôts"]
    C --> D["2. Pour chaque point de vente :<br/>correspondance de ses articles Clover"]
    D --> E["3. Préparation des jours manquants<br/>lun.–jeu. : 1 facture par jour<br/>ven.–dim. : 1 facture"]
    E --> F{"Jour bloqué ?<br/>article non relié,<br/>compte manquant"}
    F -- oui --> G["Jour ou fin de semaine mis de côté,<br/>repris la nuit suivante"]
    F -- non --> H["4. Import par lots<br/>.IMP → Sage_SA_import.exe"]
    H --> I["Vérification dans tcustr"]
    I --> J["5. Encaissements<br/>ventes importées cette nuit seulement"]
    J --> K["6. Paiements fournisseurs<br/>« Confirmé » seulement"]
    G --> K
    K --> K2["Factures fournisseurs du courriel<br/>copiées et lues pour la page 8"]
    K2 --> L["Préchauffage du cache<br/>statistiques des 7 derniers jours"]
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
    P0["Pièce jointe d'un courriel<br/>boîte IMAP, lecture seule,<br/>une seule fois"] --> P1
    P1["PDF ou photo déposé<br/>page 8"] --> P2{"PDF numérique ?"}
    P2 -- oui --> P3["pdfplumber<br/>+ modèle du fournisseur"]
    P2 -- non --> P4["OCR intégré à Windows"]
    P3 & P4 --> P5["Contrôle des totaux<br/>doublon : n° avec ou sans préfixe"]
    P5 --> P6["Articles Sage + facteur<br/>mémoire par fournisseur<br/>Qté Sage = Qté × Facteur"]
    P6 --> P7["import_achats : PurInvoice<br/>→ Sage_SA_import.exe → vérification"]
    P7 --> P8["Clover : stock + Qté Sage reçue<br/>coût = nouveau prix d'achat"]
    N1["Article absent<br/>« Créer l'article »"] --> N2["Sage : fiche de stock<br/>comptes de la catégorie"]
    N2 --> N3["Clover : article, catégorie,<br/>taxes, UGS = péremption"]
    N3 --> N4["Correspondance « Confirmé »"]
    N4 -.-> P6
    I1["Inventaire exporté<br/>Clover + Sage, un fichier"] --> I2["Quantités comptées<br/>colonne jaune"]
    I2 --> I3["Clover : stock = compté<br/>Sage : ajustement d'inventaire"]
    I3 --> I4["Rapport : coût de l'ajustement<br/>variation de la valeur Sage"]
    X1["Transfert saisi<br/>départ, arrivée, articles"] --> X2["Sage : transfert<br/>entre les deux dépôts"]
    X2 --> X3["Clover : stock − au départ<br/>+ à l'arrivée"]
    K1["Coût moyen Sage<br/>et coût Clover"] --> K2["Lignes cochées<br/>sans valeur aberrante"]
    K2 --> K3["Clover : coût = coût moyen Sage"]
    T1["Table catégorie -> comptes<br/>écart = CMV"] --> T2["Articles Sage à corriger<br/>lignes cochées"]
    T2 --> T3["Sage : comptes changés<br/>dans la fiche, vérifiés"]
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
        Pages et points de vente visibles selon le profil
        Administrateur, Comptable, Employé
        Les traitements en cours continuent
    end note
```

### 4.8 Plusieurs points de vente

Chaque point de vente Clover (identifiant marchand et jeton) est un dépôt Sage, avec son client et ses factures. Le n° 1 garde ses réglages d'origine.

```mermaid
flowchart LR
    subgraph Clover
        M1["Point de vente n° 1<br/>section [clover]"]
        M2["Point de vente n° 2<br/>[[points_vente]] code 2"]
    end
    subgraph Application
        CH{"Point de vente choisi<br/>un, plusieurs (profil) ou tous"}
        F1["Factures « Vente 2026-10-23/25 »<br/>correspondance donnees/"]
        F2["Factures « V2 2026-10-23/25 »<br/>correspondance donnees/points_vente/2/"]
        BL{"Dépôt autre que<br/>« Emplacement par défaut »<br/>et import non validé ?"}
    end
    subgraph Sage
        C1["Client « Vente Hebdomadaire »<br/>Emplacement par défaut"]
        C2["Client « Vente Magasin 2 »<br/>dépôt « Magasin 2 »"]
        B["Compte 1055<br/>mêmes comptes de produits"]
    end
    M1 --> CH
    M2 --> CH
    CH --> F1 --> C1
    CH --> F2 --> BL
    BL -- non --> C2
    BL -- oui --> X["Bloqué, signalé<br/>au compte rendu"]
    C1 --> B
    C2 --> B
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
