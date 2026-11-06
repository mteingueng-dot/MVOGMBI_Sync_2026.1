# MVOGMBI_Sync — Document d'architecture

Version 1.0.2 (6 novembre 2026) — Marché MVOG-MBI Sherbrooke.

MVOGMBI_Sync relie la caisse **Clover** à la comptabilité **Sage 50 Comptabilité Édition canadienne** :

- facturation des ventes ;
- encaissement des dépôts ;
- factures et paiements fournisseurs ;
- rapprochement bancaire Desjardins et Banque Nationale ;
- rapports et statistiques ;
- gestion des articles, des stocks, des ventes et des achats comme dans Sage, avec la chaîne des documents (devis, commande, livraison, facture, retours) ;
- comptabilité (caisse, dépenses, plan comptable, taxes, remises, budget) ;
- agence RIA (états de compte, envois et versements, commissions) ;
- paie (pointage, planning, feuilles de temps, chèques de paie dans Sage, bulletins) ;
- plusieurs sites : dépôts (emplacements de Sage) avec ou sans Clover ;
- utilisateurs, profils, droits par fonction et audit des actions.

L'application est écrite en Python 3.13, a une interface tkinter et une application web identique, et tourne sur le serveur SERVDCSAGE, à côté de Sage 50 (version 2.14.2). Elle n'utilise aucun service d'IA ni d'API externe autre que Clover : c'est le choix du propriétaire.

Ce document décrit les composants, les données, les intégrations et les principaux flux. Les règles d'affaires sont réunies dans `documentation/REGLES_AFFAIRES.md` (codes RG-…) ; le fichier `CLAUDE.md` garde le détail technique de chaque règle. Le manuel d'utilisation (`documentation/creer_manuel.py`) décrit l'usage au quotidien ; le guide de l'administrateur (`documentation/GUIDE_ADMINISTRATEUR.md`) l'installation, la configuration, l'exploitation et le dépannage.

---

## 1. Vue d'ensemble

```mermaid
flowchart LR
    subgraph Externes["Sources externes"]
        CL["Clover<br/>API REST v3"]
        BX["Boîte courriel<br/>IMAP : avis Interac,<br/>factures, états RIA"]
        DJ["Relevés Desjardins et BNC<br/>PDF"]
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
        IMP["Sage_SA_import.exe<br/>ou Assistant d'importation<br/>fichiers .IMP"]
        FEN["Fenêtres de Sage<br/>Encaissements, Paiements, Journal,<br/>stock, fiches, plan comptable, paie"]
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
    GOUV["Sites de l'ARC et de<br/>Revenu Québec<br/>formulaires T4 / RL-1"] --> COEUR
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
| `MVOGMBI_Sync.exe` (`installation/lanceur_interface.py`) | Interface : connexion, puis le menu en rubriques (Administration, Articles, Stock, Vente, Fournisseur, Comptabilité, RIA, Paie, État). |
| `MVOGMBI_Sync_console.exe` (`installation/lanceur_console.py`) | Ligne de commande et tâche planifiée (`lancer_traitement.cmd`). |
| `MVOGMBI_Sync_Serveur.exe` (`installation/lanceur_serveur.py`, = commande `web`) | Serveur de l'application web (`mvogmbi_sync/web/`) sur SERVDCSAGE (le serveur de Sage), atteint par Tailscale ; tâche planifiée « MVOGMBI_Sync Web » posée par `installer_web.ps1`. |
| `MVOGMBI_Sync_Client.exe` (`installation/lanceur_client.py`, `web/client.py`) | Client des postes (1.2.0), un seul fichier, bibliothèque standard seulement : garde l'adresse du serveur (`%APPDATA%\MVOGMBI_Sync_Client\client.json`), vérifie l'en-tête `Server: MVOGMBI_Sync`, ouvre l'application dans une fenêtre Edge en mode application (profil à part). Téléphones : navigateur. |
| `serveur.json` (à côté de `MVOGMBI_Sync_Client.exe`) | Serveur où envoie le client : écrit par « Administration > Automatisation > Serveur de l'application » (`serveur_appli.fichier_client`), recopié d'office dans `{app}\client` ; noms reconnus `app.marchemvogmbi.com` (DNS -> adresse Tailscale du serveur). |
| `python -m mvogmbi_sync <commande>` (`__main__.py`) | `facture`, `importer`, `auto`, `encaissements`, `correspondance`, `verifier-comptes`, `verifier-sage`, `rapport`, `planifier`, `langue`, `interface`. `inventaire`, `pointage`, `essai-pdf`, `web`. Commandes internes (l'application ouvre Sage elle-même) : `encaisser-bureau`, `payer-bureau`, `journal-bureau`, `depenses-bureau`, `inventaire-bureau`, `transfert-bureau`, `creer-articles-bureau`, `fiches-articles-bureau`, `tiers-bureau`, `comptes-bureau`, `paie-bureau`, `prix-sage-bureau`, `import-assistant-bureau`, `garder-sage`. |

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
        rap["rapprochement · ria · ria_etats"]
        gest["documents · chaine_documents<br/>plan_comptable · audit · feuillets"]
        stats["rapports · statistiques_clover<br/>couts_sage · previsions · peremption<br/>analyse_articles · onglets_articles"]
        nuit["automatique · courriel · planification"]
    end
    subgraph Intégration
        clover["api_clover · export_clover"]
        sagel["base_sage · articles_sage"]
        sagei["import_sage · sage_auto"]
        robots["sage_bureau · robot_encaissements<br/>robot_paiements · robot_journal<br/>robot_comptes · robot_fiches_articles · robot_paie"]
        autres["paiements_courriel IMAP · ocr_windows<br/>coffre · utilisateurs"]
    end
    interface --> connexion
    interface --> pages --> design
    pages --> ventes & enc & four & rap & stats & gest
    gest --> sagel & sagei & robots
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
| | `export_tableau.py`, `pdf_documents.py` | Liste « Exporter » : Excel, CSV, PDF et impression ; droit d'exporter par profil. Les PDF des tableaux et des documents (bons, factures, commandes) sont dessinés par fpdf2 (`pdf_documents` : en-tête logo + entreprise, filet vert / rouge / jaune, colonnes ajustées au contenu) ; Edge ne sert plus qu'aux pages HTML, avec une création de secours. |
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
| | `rapprochement.py` | Relevés Desjardins (`lire_releve_desjardins`) et BNC (`lire_releve_bnc`, banque reconnue par `banque_du_texte`) ↔ écritures du compte Sage de la banque ; comptes bancaires (`CompteBancaire`, `comptes_bancaires` : Desjardins 1055, BNC 1060, puis `[[comptes_bancaires]]`), un registre de relevés par compte (`releves_<code>/`, `ranger_releve`). |
| | `depots.py` | Dépôts : points de vente + « Emplacement par défaut » + `[sage] depots_sans_clover` ; filtres (`choisis`, `garde`) ; après l'import d'une facture, transfert « DP <n° de facture> » vers ou depuis son dépôt (`apres_import`). |
| | `impression_fournisseur.py` | Bon de réception (sans prix, quantité ajoutée dans Clover) et facture complète d'une facture fournisseur. |
| | `rapports.py` | Suivi des ventes et recherches dans l'historique Sage. |
| | `statistiques_clover.py`, `couts_sage.py`, `previsions.py`, `peremption.py` | Statistiques Clover, bénéfices au CUMP Sage, prévisions, péremption. |
| | `bons_commande.py`, `fenetre_bons_commande.py` | Fournisseur > Bons de commande : articles à commander, fournisseur et prix du dernier achat Sage, un bon PDF par fournisseur, comparaison avec la facture reçue. |
| | `prix_marges.py`, `fenetre_prix_marges.py` | Articles > Prix et marges : marge au CUMP Sage, prix proposé arrondi, mise à jour des prix Clover cochés. |
| | `paie_temps.py`, `fenetre_pointage.py`, `fenetre_feuilles_temps.py` | Paie : poste de pointage par NIP (commande `pointage`, raccourci « Pointage des employés »), feuilles de temps de 14 jours, heures supplémentaires, corrections avec motif, approbation, employés et NIP (empreintes seulement). |
| | `retenues.py` | Paie > Retenues à la source : retenues et cotisations du mois par compte de passif de Sage, versements, total à remettre par organisme (Revenu Québec, ARC, CNESST), échéance du 15. |
| | `sauvegarde.py`, `fenetre_sauvegarde.py` | Administration > Sauvegarde des données : archive vérifiée de donnees/ chaque nuit (OneDrive par défaut), conservation 14 j / 8 sem. / 12 mois, restauration. |
| | `caisse.py`, `fenetre_caisse.py` | Comptabilité > Contrôle de la caisse : espèces attendues d'après Clover, comptage du soir par coupures, écarts, dépôts d'espèces contre relevés Desjardins. |
| | `pertes.py`, `fenetre_pertes.py` | Articles > Pertes et démarque : déclaration valorisée au coût, sortie du stock Clover et document de stock Sage, rapport par motif / catégorie / article / mois en % des ventes. |
| | `conges.py`, `fenetre_conges.py` | Paie > Jours fériés et congés : jours fériés du Québec, indemnité (1/20 des 4 semaines), congés et soldes (vacances 4 % / 6 %, 2 jours de maladie payés), heures ajoutées à la paie. |
| | `retenues.py` (suivi) | Comptabilité > Suivi des remises : remises des retenues par mois et par organisme (à temps, en retard, à remettre), alertes au résumé du matin. |
| | `depenses.py`, `fin_emploi.py`, `journal_operations.py`, `fenetres_gestion2.py` | Petite caisse et dépenses (écriture du journal général dans Sage), fin d'emploi et préparation du RE, concordance T4 / RL-1, journal des opérations. |
| | `retours.py`, `etiquettes.py`, `budget.py`, `fenetres_gestion3.py` | Retours fournisseurs (facture d'achat négative), étiquettes de prix Code 128, budget et écarts, coût de la main-d'œuvre. |
| | `paquet3.py`, `fenetres_gestion4.py` | Inventaire tournant, promotions datées dans Clover, relances des clients professionnels, tableau du gérant pour le téléphone. |
| | `paie.py`, `fenetre_paie.py` | Paie > Traitement de la paie : heures planifiées (planning) et réalisées (pointages de l'application), récapitulatif par employé et par semaine, heures validées (feuilles approuvées) à saisir dans la paie de Sage, paies de Sage (écritures du module Paie : brut, retenues par sorte, net, cotisations de l'employeur) et relevé de paie imprimé ou en PDF avec le total de l'année ; lien employé Clover -> employé Sage (« Employés et NIP » > « Lier aux employés Sage… ») ; création d'un employé dans l'application, Clover et Sage Paie (« Ajouter ») ; `robot_paie.py` : fiche employé et chèque de paie remplis dans Sage (commande interne `paie-bureau`). |
| | `comptabilite.py`, `fenetre_comptabilite.py` | Comptabilité : âge des comptes, déclaration TPS/TVQ, prévision de trésorerie, clôture du mois et état des résultats (lecture seule de Sage). |
| | `listes_sage.py`, `documents.py`, `fenetre_saisie.py`, `fenetre_gestion.py` | Gestion des ventes, achats et stocks (menus comme Sage) : listes des clients, fournisseurs, documents de vente, d'achat et de stock, articles, livre d'inventaire ; commandes clients, factures de vente (.IMP SalInvoice), documents de stock (ajustements), factures d'achat et bons saisis. |
| | `cache_lectures.py` | Mémoire des lectures de Sage et du catalogue Clover (quelques minutes, partagée, vidée après chaque écriture, préchargée au démarrage si Sage répond). |
| | `robot_tiers.py` | Création de clients et de fournisseurs dans Sage : fiche « Enregistrements des clients / fournisseurs » remplie, « utilise mes numéros d'articles » cochée, vérifiée dans la base (commande interne `tiers-bureau` si Sage est fermé). |
| | `fiches.py` | Fiches ouvertes par double-clic (client, fournisseur, article, document de vente, d'achat ou de stock), lues dans Sage. |
| | `planning.py`, `fenetre_planning.py` | Paie > Planning mensuel du gérant, publication, « Mon horaire » de l'employé (compte relié) et au poste de pointage. |
| | `manuel.py` | Manuel d'utilisation du profil : chapitres des pages permises seulement, renumérotés, PDF par Edge dans donnees/manuels/. |
| | `resume_matin.py` | Résumé du matin en tête du courriel de nuit (ventes, marge, banque, factures à payer, ruptures, péremption). |
| | `analyse_articles.py`, `onglets_articles.py` | État > Produits inactifs (sans vente depuis N jours) et Articles 80/20 (classes A/B/C, stock et sa valeur) ; source Clover ou Sage. |
| | `ria.py`, `ria_etats.py`, `fenetre_ria.py` | RIA : mouvements RIA des relevés, surplus des dépôts d'espèces, commissions ; états de compte RIA (PDF lus et recontrôlés, reçus par courriel) transformés en opérations (envois, versements en espèces) puis saisies au journal général. |
| | `chaine_documents.py`, `fenetre_chaine.py` | Chaîne des documents de vente (DV, CC, PL, BL, RC, FV, FRC) et d'achat (PC, BC, BR, FA, RT, FRT) : transformer, importer les factures, Clover mis à jour par les factures, annuler un document de stock par son inverse. |
| | `plan_comptable.py`, `robot_comptes.py`, `fenetre_plan_comptable.py` | Plan comptable de Sage : lecture, création, modification, inactivation, suppression ; contrôle des comptes saisis dans l'application. |
| | `robot_fiches_articles.py`, `fenetre_fiches_articles.py` | Liste des articles : modifier (description, inactif) ou supprimer un article dans Sage, puis renommer ou supprimer les articles Clover reliés. |
| | `audit.py`, `fenetre_audit.py` | Audit des actions : une ligne par bouton, entrée du menu et connexion, chaînée par empreinte SHA-256. |
| | `feuillets.py`, `calendrier_paie.py` | T4 et RL-1 sur les formulaires officiels (téléchargés des sites de l'ARC et de Revenu Québec, contrôlés) ; calendrier des paies aux 14 jours. |
| | `automatique.py`, `courriel.py`, `planification.py` | Traitement de nuit, compte rendu, tâche planifiée ; envoi réessayé 3 fois, copie cachée au propriétaire des courriels personnels. |
| Intégration | `api_clover.py`, `export_clover.py` | API REST Clover v3 (parallélisée) ; export Excel Clover. |
| | `base_sage.py`, `articles_sage.py` | Lecture MySQL de Sage, même quand Sage est fermé (`lire_pendant_connexion`). |
| | `import_sage.py`, `sage_auto.py` | Fichier `.IMP` `<SalInvoice>` ; pilotage de `Sage_SA_import.exe` (`executer_outil`), puis de l'assistant si l'outil refuse l'entreprise partagée (`executer`, fichier noté dans `entreprises_partagees.json`). |
| | `robot_import_assistant.py` | « Assistant d'importation des transactions » de Sage : menu Fichier > Importer/Exporter repéré par son texte (OCR de Windows), type de transaction, fichier, résumé lu ; Sage gardé ouvert pendant le résumé pour vérifier la facture (commande interne `import-assistant-bureau`). |
| | `sage_bureau.py`, `robot_*.py` | Ouverture de Sage sur un bureau Windows séparé et saisie dans ses fenêtres par messages Windows. |
| | `paiements_courriel.py`, `ocr_windows.py` | IMAP en lecture seule ; OCR intégré à Windows. |
| | `coffre.py`, `utilisateurs.py` | Coffre-fort Windows ; comptes et profils, avec mots de passe hachés. |
| | `pointage_wifi.py` | Pointage seulement depuis le Wi-Fi du magasin : réseau de l'appareil lu dans Tailscale (`tailscale status`, sinon `tailscale ping`) comparé aux adresses publiques du magasin ; postes du magasin toujours permis. |
| | `prix_sage.py`, `robot_prix_sage.py` | Prix de vente régulier de Sage depuis Clover : comparaison, liste à cocher, écriture dans la fiche article (onglet des prix, case Régulier), vérifiée dans tinvprc. |
| | `serveur_appli.py` | Serveur de l'application ([serveur] et [web] de `config.toml`) : ordinateur, adresse Tailscale, adresse locale, nom tapé dans le client, port ; fichier `serveur.json` du client. |
| Web | `web/serveur.py`, `web/pages.py`, `web/menu.py`, `web/accueil.py` | Serveur HTTP sans bibliothèque, sessions, sécurité, menu et accueil identiques à Windows ; `page()` donne aux pages de l'application leur en-tête (`entete_page`) et aux fenêtres de travail leur bandeau « ✖ Fermer ». |
| | `web/style_windows.py`, `web/export_web.py`, `web/a_cocher.py` | Allure des fenêtres Windows ; « ⬇ Exporter ▾ » de chaque tableau ; liste à cocher commune (`FenetreACocher`). |
| | `web/pages_*.py`, `web/consultations*.py` | Une page par entrée du menu (76), mêmes calculs que les fenêtres ; `pages_dossiers.py` (contenu des dossiers du serveur, choix d'un fichier ou d'un dossier) ; `pages_fiches.py` (nouveau client / fournisseur, modifier ou supprimer un article dans Sage et Clover). |
| | `web/graphiques_svg.py`, `web/taches.py`, `web/client.py` | Graphiques de `graphiques.py` en SVG ; travaux longs dans un fil (un seul dans Sage à la fois) ; client des postes. |
| | `web/filtres.py` | Filtre à choix multiples sans script (dépôts : cases, « Tout sélectionner »). |

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
            REL["releves_desjardins/, releves_bnc/…<br/>un dossier par compte bancaire"]
            CACHE["cache_clover/AAAA-MM-JJ.json<br/>couts_sage.json"]
            USR["utilisateurs.json<br/>audit.jsonl"]
            RIA["ria.json<br/>etats_ria/etats.json"]
            DOCS["documents.json<br/>pertes, promotions, paie…"]
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
| Audit | `audit.jsonl`, une ligne par action, chaînée | `audit.py` | Administration > Audit des actions |
| RIA | `ria.json` (opérations, comptes), `etats_ria/` (PDF et lecture) | `ria.py`, `ria_etats.py` | RIA, journal général |
| Documents de l'application | `documents.json` + PDF | `documents.py`, `chaine_documents.py` | listes, import Sage |

Tables Sage lues :

| Table | Contenu |
|---|---|
| `tcustr`, `tcustrdt` | Factures et encaissements clients |
| `tvendor`, `tventr`, `tventrdt` | Fournisseurs, factures et paiements |
| `tinvent`, `tinvlot` | Articles, coûts et stock |
| `tinvloc`, `tinvbyln` | Dépôts (emplacements d'inventaire), stock et valeur par dépôt |
| `tjentact`, `tjourent`, `taccount` | Écritures et comptes |
| `ttaxauth` | Taxes |
| `tpydet`, `tpydet1`, `tpydet2`, `tcomppy5`, `temp` | Paies (brut, gains, retenues), libellés, employés (jamais le NAS) |
| `titrec`, `titrline` | Mouvements d'articles (ventes, achats, ajustements, transferts) ; `titrec.bTrfLoc` distingue un transfert d'un ajustement du journal 14, `titrline.lInvLocId` donne le dépôt de chaque ligne |

---

## 4. Flux principaux

### 4.1 Traitement de nuit (`automatique.lancer`)

```mermaid
flowchart LR
  subgraph S1 ["Préparation et import"]
    direction TB
    A(["Tâche planifiée Windows, ex. 1 h"]) --> B{"Verrou<br/>traitement.verrou<br/>de moins de 6 h ?"}
    B -- oui --> Z1["Exécution annulée,<br/>notée au journal"]
    B -- non --> C["Étape 1 : Lecture de Sage (une fois)<br/>factures de chaque point de vente,<br/>articles, comptes, clients, dépôts"]
    C --> D["Étape 2 : Pour chaque point de vente :<br/>correspondance de ses articles Clover"]
    D --> E["Étape 3 : Préparation des jours manquants<br/>lun.–jeu. : 1 facture par jour<br/>ven.–dim. : 1 facture"]
    E --> F{"Jour bloqué ?<br/>article non relié,<br/>compte manquant"}
    F -- oui --> G["Jour ou fin de semaine mis de côté,<br/>repris la nuit suivante ;<br/>les étapes suivantes continuent"]
    F -- non --> H["Étape 4 : Import par lots<br/>.IMP → Sage_SA_import.exe"]
    H --> I["Vérification dans tcustr"]
  end
  subgraph S2 ["Suite de la nuit"]
    direction TB
    J["Étape 5 : Encaissements<br/>ventes importées cette nuit seulement"]
    J --> K["Étape 6 : Paiements fournisseurs<br/>« Confirmé » seulement"]
    K --> K2["Factures fournisseurs et avis Interac du courriel<br/>factures « Prête à importer » importées"]
    K2 --> K3["États RIA du courriel<br/>opérations saisies au journal<br/>si les comptes sont renseignés"]
    K3 --> L["Promotions, préchauffage du cache<br/>résumé du matin, tableau du gérant"]
    L --> L2["Sauvegarde des données"]
    L2 --> M["Journal<br/>+ courriel avec pièces jointes Excel"]
  end
  S1 --> S2
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

Un dépôt d'espèces supérieur aux espèces dues garde son surplus en « Part RIA à confirmer » (`repartir_especes`). `ria.py` (`donnees/ria.json`) note la part confirmée, retirée du dépôt au calcul suivant ; `journal_sur_bureau_cache` saisit aussi les opérations de RIA (`mouvements_a_saisir`), avec le n° « RI-0001 » comme source.

Les états de compte RIA (`ria_etats.py`) deviennent des opérations une seule fois chacune : envoi « MT Send » = débit espèces / crédit RIA ; versement ou remboursement en espèces = débit RIA / crédit espèces ; un versement payé par virement Interac (même montant au relevé, à 3 jours près) est laissé à la banque ; les règlements ACH et dépôts restent des mouvements de banque.

### 4.4 Factures et paiements fournisseurs

```mermaid
flowchart TD
    P0["Pièce jointe d'un courriel<br/>boîte IMAP, lecture seule,<br/>une seule fois"] --> P1
    P1["PDF ou photo déposé<br/>page 8"] --> P2{"PDF numérique ?"}
    PH["Photos prises au téléphone<br/>/photo-facture, une par page"] --> PHP["un PDF"] --> P4
    P2 -- oui --> P3["pdfplumber<br/>+ modèle du fournisseur"]
    P2 -- non --> P4["OCR intégré à Windows"]
    P3 & P4 --> P5["Contrôle des totaux<br/>doublon : n° avec ou sans préfixe"]
    P5 --> P6["Articles Sage + facteur<br/>mémoire par fournisseur<br/>Qté Sage = Qté × Facteur"]
    P6 --> P7["import_achats : PurInvoice<br/>→ Sage_SA_import.exe<br/>(assistant si entreprise partagée)<br/>→ vérification"]
    P7 --> P7b["Transfert DP vers le dépôt<br/>de la facture"]
    P7b --> P8["Clover : stock + Qté Sage reçue<br/>coût = nouveau prix d'achat"]
    P8 --> P9["Courriel de compte rendu<br/>bon de réception imprimable"]
    N1["Article absent<br/>« Créer l'article »"] --> N2["Sage : fiche de stock<br/>comptes de la catégorie"]
    N2 --> N3["Clover : article, catégorie,<br/>taxes, UGS = péremption"]
    N3 --> N4["Correspondance « Confirmé »"]
    N4 -.-> P6
```

Inventaire, transferts, coûts et comptes :

```mermaid
flowchart TD
    I1["Inventaire exporté<br/>Clover + Sage, un fichier"] --> I2["Quantités comptées<br/>colonne jaune"]
    I2 --> I3["Clover : stock = compté<br/>Sage : ajustement d'inventaire"]
    I3 --> I4["Rapport : coût de l'ajustement<br/>variation de la valeur Sage"]
    X1["Transfert saisi<br/>départ, arrivée, articles"] --> X2["Sage : transfert<br/>entre les deux dépôts"]
    X2 --> X3["Clover : stock − au départ<br/>+ à l'arrivée"]
    K1["Coût moyen Sage<br/>et coût Clover"] --> K2["Lignes cochées<br/>sans valeur aberrante"]
    K2 --> K3["Clover : coût = coût moyen Sage"]
    T1["Table catégorie -> comptes<br/>écart = CMV"] --> T2["Articles Sage à corriger<br/>lignes cochées"]
    T2 --> T3["Sage : comptes changés<br/>dans la fiche, vérifiés"]
```

Paiements des fournisseurs (après l'import de leurs factures) :

```mermaid
flowchart LR
    M1["Avis Interac<br/>boîte IMAP, lecture seule"] --> M2["Rapprochement proposé<br/>fournisseur, montant, n° cités"]
    M2 --> M3["Confirmé par le propriétaire<br/>page 9"]
    M3 --> M4["Répartition : plus ancienne d'abord,<br/>jamais plus que le solde"]
    M4 --> M5["Fenêtre Paiements de Sage<br/>une ligne par facture, un seul Traiter"]
    M5 --> M6["Vérification : baisse du solde"]
```

### 4.5 Rapprochement bancaire

```mermaid
flowchart TD
    R1["Relevé PDF Desjardins"] --> R2["Lecture par colonnes<br/>Frais, Retrait, Dépôt, Solde<br/>chaque solde revérifié"]
    R1b["Relevé PDF BNC"] --> R2b["Lignes MM JJ description montant solde<br/>sens d'après la variation du solde<br/>contrôle des totaux débit / crédit"]
    R2b --> R3
    S1["Sage : tjentact + tjourent<br/>compte de la banque (1055, 1060…)"] --> R3
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

### 4.7 bis Application web (version 1.1.0)

Serveur HTTP de Python (`http.server`, aucune bibliothèque de plus) dans `mvogmbi_sync/web/` : `serveur.py`
(sessions, sécurité, aiguillage) et `pages.py` (pages HTML, sans script). Mêmes comptes, profils et droits par
fonction que l'application Windows (`utilisateurs.Registre`) ; chaque page porte le titre de l'entrée du menu qui
lui correspond. Mêmes fichiers de `donnees/` : le serveur web et l'application de bureau doivent donc tourner sur le
même ordinateur (SERVDCSAGE, avec Sage et le traitement de nuit).

```mermaid
flowchart LR
    T[Téléphone / PC<br/>navigateur] -->|Tailscale, chiffré| W[Serveur web<br/>SERVDCSAGE:8765]
    W --> U[utilisateurs.json<br/>profils et droits]
    W --> P[pointages, feuilles,<br/>planning]
    W --> C[Clover<br/>lecture seule]
    W --> TG[tableau du gérant<br/>écrit la nuit]
```

| Page | Entrée du menu (droit) | Contenu |
|---|---|---|
| `/` | — | fonctions permises au profil |
| `/pointage` | Pointage des employés | NIP ; seulement depuis les adresses de `[web] postes_pointage` |
| `/horaire` | Mon horaire | 5 semaines publiées ; le gérant choisit l'employé |
| `/mes-heures` | Mes heures et mes paies | période en cours et précédente |
| `/feuilles` | Feuilles de temps | approbation des feuilles sans anomalie |
| `/statistiques` | Statistiques Clover | cartes avec variation, ventes par heure ou par jour ; employé limité : ses ventes |
| `/tableau` | Tableau du gérant (téléphone) | page écrite chaque nuit |
| `/mot-de-passe` | — | ferme toutes les sessions du compte |

Mot de passe web à part (2.17.0) : `Utilisateur.sel_web` / `empreinte_web` (PBKDF2), `Registre.verifier_web` (mot de passe web s'il existe, sinon celui de l'application puis création obligatoire : `Session.creer_web`, toute page renvoie à `/mot-de-passe`), `probleme_mot_de_passe_web` (12 caractères, minuscule, majuscule, chiffre, caractère spécial, différent du mot de passe Windows).

Sécurité : témoin de session HttpOnly + SameSite=Strict (Secure en HTTPS), 5 min d'inactivité (la page passe d'elle-même à la connexion), 12 h au plus ;
jeton anti-falsification sur chaque formulaire et refus des envois d'une autre origine ; politique de contenu sans
script ni cadre ; 3 mots de passe faux = compte verrouillé (règle de l'application), 10 échecs en 10 min = adresse
refusée 10 min ; pare-feu ouvert sur la carte Tailscale seulement ; audit de chaque page et action (fenêtre « Web »),
journal `donnees/journal_web.log`.

Depuis la version 2.0.0, toutes les entrées du menu (76) ont leur page web, avec le même affichage que
l'application Windows (bandeau, menu de gauche en rubriques, Mise en route). Les pages sont réparties en modules
(`pages.MODULES` : paie, consultations, comptabilité, trésorerie, rapprochement, RIA, ventes, documents,
fournisseurs, achats, articles, catalogue, administration, traitement de la paie) qui appellent les mêmes fonctions de
calcul que les fenêtres. Les traitements longs (saisies dans Sage, imports, lectures de boîtes de courriel) passent
par `web/taches.py` : un fil par travail, une seule saisie dans Sage à la fois, page de suivi rafraîchie sans script.

```mermaid
flowchart LR
    N[Navigateur] -->|formulaire| P[Page web]
    P -->|lecture| C[Clover / Sage / donnees]
    P -->|travail long| T[taches.py<br/>un fil]
    T -->|commande interne| S[Sage ouvert<br/>par l'application]
    T --> J[/tache : suivi<br/>rafraîchi seul/]
```

#### Interface identique à Windows (versions 2.1 à 2.14)

Les 76 entrées du menu ont été comparées côte à côte (photo de chaque fenêtre Windows et de la page web à la même
taille) et alignées : mêmes boutons, même ordre, même position, mêmes couleurs d'état.

| Fenêtre Windows | Équivalent web |
|---|---|
| Page de l'application (`entete_page` : icône, titre souligné, sous-titre) | même en-tête, sans bandeau « Fermer » |
| Fenêtre de travail (`Application.nouvel_outil`) | titre de la fenêtre + « ✖ Fermer » |
| Ligne de tableau choisie d'un clic | bouton radio caché, chaque cellule l'étiquette (`ligne_cliquable`) |
| `bouton_exporter` placé à droite (`placer_a_droite`) | « ⬇ Exporter ▾ » dans la barre de boutons du tableau |
| Fenêtre de saisie à part (`DialogueEmploye`, `DialogueTiers`, `DialogueHoraire`…) | carte ouverte sous la liste |
| Carte du bas vide avant le choix d'une ligne | mêmes champs et boutons, inactifs |
| Calcul seulement au bouton (« Calculer », « Vérifier ») | `Consultation.attente` : zones vides titrées avant le clic |
| Dossier ouvert dans l'Explorateur | contenu du dossier du serveur, fichiers téléchargés (`pages_dossiers.py`) |
| Copier dans le presse-papiers | texte seul affiché (pas de script dans la page) |

Restent différents, à cause du navigateur sans script : un bouton « Afficher » ou « Choisir » là où Windows réagit au
choix d'une liste, les dates au format du navigateur et les petites fenêtres de saisie ouvertes dans la page.

#### Déploiement et configuration du serveur (version 2.14.2)

Sage 50, MVOGMBI_Sync, son serveur web et le traitement de nuit sont sur le même ordinateur : depuis le
4 novembre 2026, **SERVDCSAGE** (réseau local 192.168.2.62, Tailscale 100.99.52.28). Le nom
`app.marchemvogmbi.com` (DNS chez WHC) mène à son adresse Tailscale ; HTTPS sur le port 443 avec un certificat Let's Encrypt validé par le DNS (`installation/certificat_https.ps1`, win-acme ; [web] certificat / cle), relu par le serveur à chaque renouvellement. Aucune adresse n'est écrite dans le programme :
tout se règle dans « Administration > Automatisation > Serveur de l'application ».

```mermaid
flowchart LR
    CFG[config.toml<br/>serveur et web] --> W[Serveur web<br/>adresse Tailscale:8765]
    CFG -->|Fichier du client| J[serveur.json]
    J --> CL[MVOGMBI_Sync_Client.exe<br/>sur chaque poste]
    CL -->|https://app.marchemvogmbi.com| DNS[DNS WHC]
    DNS -->|100.99.52.28| W
    CL -->|Bureau à distance| RDP[Application Windows<br/>sur le serveur]
```

#### Pointage sur le Wi-Fi du magasin (version 2.14.2)

Les appareils joignent le serveur par Tailscale : le serveur voit leur adresse 100.x, pas leur Wi-Fi. Tailscale sait
par quelle adresse il joint l'appareil : c'est l'adresse publique de la connexion Internet du réseau où il se trouve.

```mermaid
flowchart LR
    TEL[Téléphone de l'employé<br/>Wi-Fi du magasin] -->|Tailscale 100.x| W[Serveur web /pointage]
    W --> PW[pointage_wifi.autorise]
    PW -->|poste listé| OK([Pointage permis])
    PW -->|tailscale status / ping| R[adresse du réseau<br/>de l'appareil]
    R -->|= adresse du magasin| OK
    R -->|autre réseau ou inconnue| NON([Refusé : « connectez-vous<br/>au Wi-Fi du magasin »])
```

Pause automatique (version 2.15.0) : le téléphone qui a servi à pointer est suivi (`donnees/pointage_telephones.json`) tant que l'employé est au travail. Le serveur web contrôle chaque minute (`pointage_wifi.controler`) : 5 minutes de suite hors du Wi-Fi du magasin (réglage `[pointage] pause_hors_wifi_minutes`) = « Début de pause » à l'heure du départ (`Registre.pointer_auto`, auteur « Automatique ») ; retour sur le Wi-Fi = « Fin de pause ». Un départ arrête le suivi.

#### Rapidité de l'application web (version 2.22.0)

Une lecture de Sage qui échoue est retenue 45 s (`_ECHECS_LECTURE`) : les pages suivantes s'affichent tout de suite avec le bandeau « Sage ne répond pas ». Tant que quelqu'un a utilisé le site dans les 15 dernières minutes, un fil du serveur (`_garder_sage_pret`) garde la base ouverte (`SELECT 1` toutes les 45 s), jamais la nuit ni pendant un travail Sage. Feuille de style et logo sont gardés par le navigateur. Mesure sur une copie : 64 pages du menu en 3,8 s au 2e tour (60 ms par page) au lieu de 62,8 s.

#### Même état dans Windows et sur le web (version 2.23.1)

Le registre des factures fournisseurs retient ce qu'il a lu ; s'il a changé sur le disque entre-temps (autre plateforme), `enregistrer` fusionne : seules les factures modifiées ici remplacent celles du disque, et une facture « Importée » n'est jamais ramenée à un autre état. La page Windows relit le registre toutes les 3 s s'il a changé.

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

### 4.9 Dépôts (plusieurs sites)

Un dépôt est un emplacement d'inventaire de Sage (`tinvloc`) : celui d'un point de vente Clover, l'« Emplacement par défaut », ou un dépôt sans Clover (`[sage] depots_sans_clover`). Le fichier `.IMP` n'a pas de champ d'emplacement : la facture entre dans l'emplacement par défaut, puis un transfert la place dans son dépôt.

```mermaid
flowchart LR
    F["Facture<br/>vente, achat, retour<br/>dépôt choisi"] --> I["Import .IMP<br/>Emplacement par défaut"]
    I --> V{"Facture présente<br/>dans Sage ?"}
    V -- oui --> T["Transfert entre emplacements<br/>source DP n° de facture<br/>vente : dépôt → défaut<br/>achat : défaut → dépôt"]
    T --> C{"Dépôt avec<br/>point de vente ?"}
    C -- oui --> CL["Stock Clover<br/>du point de vente"]
    C -- non --> FIN([Terminé])
    T -. échec .-> R["Signalé « à refaire »<br/>la facture reste importée"]
```

| Où | Effet du dépôt |
|---|---|
| Factures fournisseurs, documents FV / FRC, retours, traitement de nuit | dépôt de la facture (`depots.apres_import`) |
| Employés, planning, feuilles de temps | dépôt principal de l'employé (`Employe.depot`), dépôt du quart (`Quart.depot`) : une cédule par dépôt |
| Documents de stock, livre d'inventaire, liste des articles | colonne et filtre Dépôt lus dans Sage (`titrline.lInvLocId`, `tinvbyln`) |
| Main-d'œuvre, suivi des ventes, rapports de gestion | heures et ventes des dépôts / points de vente choisis |

Filtres : Windows `design.filtre_depots` (liste à choix multiples), web `web/filtres.filtre_depots` (cases, « Tout sélectionner », sans script).

---

## 5. Pilotage de Sage

Sage 50 CA n'a pas d'API ouverte. L'application passe par trois voies :

| Voie | Utilisée pour | Sage | Vérification |
|---|---|---|---|
| MySQL en lecture seule (`base_sage.py`) | Tout ce qui se lit | ouvert ; sinon base ouverte par l'outil d'import ; refusée : Sage ouvert par l'application (`garder-sage`) | — |
| `Sage_SA_import.exe` (`sage_auto.py`) | Factures de vente `<SalInvoice>` et d'achat `<PurInvoice>` (retours compris) | fermé, **mono-utilisateur** (accès exclusif) | présence dans `tcustr` / `tventr` |
| Assistant d'importation de Sage (`robot_import_assistant.py`) | Mêmes fichiers `.IMP`, quand l'outil refuse une **entreprise partagée** (« You cannot use this utility to import transactions into a shared company ») | ouvert par l'application en **mono-utilisateur** ; menu repéré par son texte (OCR de Windows) | résumé de Sage lu, facture retrouvée dans la base pendant le résumé |
| Fenêtres de Sage (`sage_bureau.py` + `robot_*.py`) | Encaissements, paiements, journal général, dépenses, documents de stock, inventaire, transferts, articles, clients, fournisseurs, employés, paie | lancé par l'application sur un bureau Windows séparé, **multi-utilisateur** ; fonctionne session verrouillée | baisse des soldes, écriture présente, stock relu |

Règles d'ouverture de Sage :

- **Mono-utilisateur pour l'import, multi-utilisateur pour les saisies et la lecture** (règle du propriétaire). Le multi-utilisateur exige le service Windows « Sage 50 Gestionnaire de connexion de base de données ».
- Le fichier réel est une **entreprise partagée** : Sage demande comment l'ouvrir ; `SessionSage._repondre_entreprise_partagee` répond selon la règle. Le partage n'est jamais arrêté (choix du propriétaire) : les imports passent par l'assistant d'importation.
- L'écran « Lancement de Sage 50. Veuillez patienter… » n'est pas un message d'erreur : l'application attend jusqu'à 60 s avant de juger un message. Sage déjà ouvert sur un autre fichier dans la même session Windows : erreur tout de suite.
- Diagnostic de l'assistant : photos de la fenêtre et des menus dans `donnees/diagnostic_assistant/`, citées dans le message d'erreur.
- Sur le bureau séparé, une page du menu de gauche s'ouvre par le **cadre** de son libellé (`robot_articles.afficher_page`), une tâche par le cadre de son libellé (`cible_tache`) ; un clic sur le libellé seul est ignoré.
- Sage refuse l'accès MySQL des applications tant que l'entreprise n'est pas ouverte par Sage ou par l'outil d'import : l'utilisateur `mvogmbi_sync` (« Accès par des tiers ») doit exister avec le même mot de passe dans chaque fichier d'entreprise.

### 5.1 Base gardée ouverte

```mermaid
flowchart TD
    L["lire_sage(fonction)"] --> O{"Sage ouvert ?"}
    O -- oui --> Q["requête directe<br/>(connexion réutilisée)"]
    O -- non --> G{"base déjà gardée ?"}
    G -- oui --> Q
    G -- non --> I["outil d'import : base ouverte<br/>sur sa fenêtre de mot de passe (~10 s)"]
    I -- "refusée" --> S["Sage ouvert par l'application<br/>(bureau séparé, multi-utilisateur)"]
    I -- "acceptée" --> K["base gardée 10 min<br/>après la dernière lecture"]
    S --> K
    K --> Q
    K -. "la personne lance Sage<br/>ou un autre programme doit importer" .-> R["base relâchée<br/>(marque base_gardee.pid,<br/>signal liberer_base.signal)"]
```

- Une erreur de la fonction de lecture (calcul, requête fautive) remonte tout de suite ; seules les erreurs de connexion déclenchent un autre moyen d'ouverture.
- Une lecture automatique (démarrage, préchargement) n'ouvre jamais Sage lui-même (`ouvrir=False`, `OUVERTURE_SAGE`).

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
| Comptes | `utilisateurs.json` : empreintes de mots de passe (PBKDF2), profils ; journal des connexions ; 3 mots de passe faux = compte verrouillé (le dernier administrateur n'est bloqué que 15 min). |
| Audit | `audit.jsonl` : chaque action (bouton, menu, connexion), poste et utilisateur ; chaque ligne porte l'empreinte de la précédente, une modification est repérée. |
| Droits | Par profil : fonctions du menu permises une à une (`fonctions_permises` : « Liste des articles » sans le reste de la rubrique), actions refusées dans les fenêtres (`fonctions_refusees` : traiter la paie, restaurer une sauvegarde…), « Supprimer des éléments » (tous les boutons Supprimer / 🗑 et la touche Suppr), « Exporter les données », points de vente permis. L'administrateur a tout. |
| Verrouillage | Après `[general] verrouillage_minutes` (5 par défaut ; 0 = jamais) sans activité. La fenêtre est cachée et le mot de passe est redemandé. Web : déconnexion après `[web] inactivite_minutes` (5). |
| Application web | Mot de passe web à part (12 caractères, minuscule, majuscule, chiffre, caractère spécial) ; HTTPS (certificat Let's Encrypt) ; serveur sur la carte Tailscale seulement ; un compte désactivé perd ses sessions. |
| Sage | Utilisateur MySQL en consultation seule ; imports et saisies uniquement après contrôle des doublons. |
| Banque | Relevés chargés à la main : aucune connexion à AccèsD. |
| Courriel | IMAP en lecture seule ; SMTP pour le compte rendu ; documents personnels à un seul destinataire visible, copie cachée au propriétaire. |
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
    SETUP --> POSTE["Serveur SERVDCSAGE (avec Sage) :<br/>%LOCALAPPDATA%/Programs/MVOGMBI_Sync<br/>raccourcis, manuels, tâche planifiée,<br/>serveur web (installer_web.ps1)"]
    POSTE -->|serveur.json| CLIENT["Postes : Installer_MVOGMBI_Sync_Client_x.y.z.exe<br/>(sans droits d'administrateur)"]
```

- `installation/fabriquer.cmd` enchaîne tout et produit deux installateurs : `Installer_MVOGMBI_Sync_x.y.z.exe` (serveur) et `Installer_MVOGMBI_Sync_Client_x.y.z.exe` (postes, avec `serveur.json` écrit d'après `config.toml`). Chaque livraison a son propre numéro de version : `aide.VERSION`, `version_info.txt`, `MVOGMBI_Sync.iss` et `MVOGMBI_Sync_Client.iss`. Numérotation remise à 1.0.0 le 5 novembre 2026 (après la 2.24.2) ; les anciens installateurs sont dans `dist/Archives`.
- Le serveur web (`MVOGMBI_Sync_Serveur.exe`) tourne sans fenêtre, une seule copie à la fois (verrou nommé), démarré par le dossier Démarrage ; ses erreurs vont dans `donnees/journal_web.log`.
- RACINE est le dossier de l'exe ; la variable `MVOGMBI_RACINE` en force un autre.
- Mise en service sur un serveur : installer, reprendre `config.toml` et `donnees/` (« Reprendre une configuration existante… »), retaper les mots de passe (coffre-fort propre à chaque machine), régler « Serveur de l'application », lancer `installer_web.ps1` (il remet `[web] adresse` à l'adresse Tailscale de la machine) et la tâche planifiée ; sur l'ancien serveur, retirer la tâche et le serveur web.
- Tests : `tests/`, 295 tests automatiques sans accès à Clover ni à Sage. Les essais réels se font sur la copie `MVOGMBI_ESSAI.SAI` (voir `documentation/PLAN_DE_TEST.md`).
- Documents : `documentation/creer_documents.py` produit les PDF de l'architecture, du guide de l'administrateur, de la documentation fonctionnelle, des règles d'affaires, du plan de test, du projet, des workflows et des processus métier ; `creer_presentation.js` (Node.js, pptxgenjs) la présentation PowerPoint ; `creer_manuel.py` les manuels.

---

## 8. Performances

| Opération | Moyen | Ordre de grandeur |
|---|---|---|
| Commandes Clover d'une période | liste filtrée par `clientCreatedTime`, commandes manquantes 6 en parallèle | secondes par jour |
| Statistiques d'une année | blocs de 31 jours, 3 en parallèle, cache par jour | 49 s à froid, quelques secondes ensuite |
| Filtres globaux | recalcul en mémoire, sans relire Clover | environ 1 s |
| Recherches dans l'historique Sage | historique gardé 10 min | 0,3 s après la première |
| Ouverture des statistiques le matin | cache des 7 derniers jours préchauffé la nuit | immédiat |
| Requêtes Sage | index utilisés (pas de TRIM dans les conditions), connexion réutilisée | 0,01 à 0,6 s |
| 1re lecture, Sage fermé | outil d'import, puis base gardée 10 min | ~10 s, puis immédiat |
| Listes Sage au démarrage | préchargement en arrière-plan (clients, fournisseurs, articles) | 0,1 à 0,4 s au clic |
| Ventes par article sur 365 jours | résumés par jour sur disque | 0,3 s (4,6 s au 1er appel du jour) |
| Page de l'application web | base gardée prête, échec de Sage retenu 45 s, style en cache | 60 ms (2e tour des 64 pages : 3,8 s) |
| Import par l'assistant d'importation | Sage ouvert par l'application, menu repéré par son texte | 1 min 40 à 1 min 45 par fichier |
| Transfert vers le dépôt après un import | fenêtre « Ajustements des Stocks & Transferts », Sage fermé | environ 2 min 45 |
| Lecture des boîtes de courriel | en-têtes de tous les messages en une demande, messages déjà lus sautés | une demande au lieu d'une par message |
