# MVOGMBI_Sync — Plan et rapport de tests

Version 1.0.20 (7 novembre 2026) — Marché MVOG-MBI Sherbrooke.

---

## 1. Stratégie

| Niveau | Quoi | Où | Quand |
|---|---|---|---|
| Tests automatiques | Règles de calcul, formats d'import, droits, registres | `tests/` (pytest), sans Clover ni Sage | À chaque changement, avant chaque installateur |
| Tests d'intégration | Lectures et écritures réelles | Clover réel (articles et employés d'essai cachés, supprimés ensuite) ; Sage sur la **copie** `MVOGMBI_ESSAI.SAI` | À chaque fonction qui écrit dans Clover ou Sage |
| Recette | Parcours complets par profil | Application installée, copie d'essai | Avant une livraison |
| Essais réels | Écritures dans le **vrai** fichier, à la demande expresse du propriétaire | Serveur, session du propriétaire, Sage 2027 ; résultats relus dans la base | Après validation sur la copie (depuis le 6 novembre 2026) |
| Exploitation | Traitement de nuit réel | Journal `journal_automatique.log`, compte rendu par courriel | Chaque nuit |

Règles :

- Aucun essai d'écriture dans le **vrai** fichier de l'entreprise sans la demande expresse du propriétaire ; chaque fonction y passe d'abord par la copie d'essai.
- Chaque écriture d'essai est **relue dans la base** (Sage) ou dans l'API (Clover) ; le message du programme ne suffit jamais.
- Un essai sur le serveur se lance dans la session ouverte du propriétaire (tâche temporaire supprimée ensuite), jamais en session 0.
- Dans Clover (production), écriture seulement sur des éléments d'essai cachés, supprimés à la fin.
- Un défaut trouvé reçoit un test automatique quand c'est possible.

---

## 2. Environnement

| Élément | Valeur |
|---|---|
| Poste | Windows 11, session ouverte (verrouillée possible) |
| Python | 3.13, pytest |
| Sage | Poste : Sage 50 Comptabilité Supérieur 2026 ; serveur : Sage 50 2027 (le vrai fichier y est converti) ; service « Gestionnaire de connexion de base de données » démarré |
| Serveur | SERVDCSAGE : application, serveur web, traitement de nuit et Sage sur la même machine ; essais lancés à distance dans la session ouverte |
| Fichiers Sage | Vrai fichier (lecture seulement), copie d'essai `MVOGMBI_ESSAI.SAI` (lecture et écriture) |
| Clover | Compte marchand réel, jeton avec lecture, inventaire et employés en écriture |
| Commande | `python -m pytest` |

---

## 3. Tests automatiques — 315 tests

| Domaine | Fichiers | Tests |
|---|---|---|
| Ventes, factures et import Sage | test_calculs, test_import_sage, test_automatique_jours, test_peremption_periodes, test_verification_comptes | 33 |
| Correspondance et création d'articles | test_correspondance, test_creation_articles | 21 |
| Encaissements, espèces, rapprochement | test_encaissements, test_encaissements_manuels, test_especes_salaires, test_rapprochement | 21 |
| Fournisseurs (factures, courriel, paiements, bons, taxes) | test_factures_fournisseurs, test_factures_courriel, test_page_fournisseurs, test_paiements_courriel, test_paiements_fournisseurs, test_robot_paiements, test_bons_commande, test_taxes_facteurs, test_robot_tiers | 30 |
| Stocks (inventaire, transferts, pertes, prix) | test_inventaire, test_transferts, test_pertes, test_prix_marges, test_planning_documents | 16 |
| Statistiques, rapports, prévisions | test_statistiques_clover, test_rapports, test_previsions, test_analyse_articles, test_resume_matin | 21 |
| Comptabilité et caisse | test_comptabilite, test_caisse, test_retenues | 9 |
| Paie | test_paie, test_paie_temps, test_conges | 14 |
| Fonctions de gestion (paquets 1 à 3) | test_paquet1, test_paquet2, test_paquet3 | 10 |
| Utilisateurs et droits | test_utilisateurs, test_droits_fenetres, test_droits_modifications | 10 |
| Points de vente | test_points_vente | 6 |
| Courriel, export, sauvegarde | test_courriel, test_export_tableau, test_sauvegarde | 15 |
| Langues et manuel | test_langues, test_manuel | 6 |
| RIA (opérations, surplus, commissions) | test_ria | 6 |
| Versions 1.0.1 à 1.0.7 : états RIA, chaîne des documents, plan comptable, audit, PDF, T4 / RL-1, paie | test_version_1_0_4, test_version_1_0_7, test_chaine_documents, test_paie_nouveautes | 25 |
| Versions 1.0.9 et 1.0.10 : états RIA traités, articles modifiés ou supprimés, promotions annulées, courriel réessayé, menu RIA | test_version_1_0_9 | 8 |
| Tests ajoutés aux fichiers existants depuis la 1.0.0 | divers | 4 |
| Application web (connexion, droits, sécurité, pointage, Wi-Fi et pause automatique, paie, documents, exports, serveur de l'application, client) | test_web | 25 |
| Autres tests ajoutés depuis la 1.0.11 | divers | 1 |
| Dépôts (filtres, transferts après import, documents de stock, main-d'œuvre, rapports de gestion, suivi des ventes) | test_depots | 9 |
| Ajouts des versions 2.17 à 2.24 (mot de passe web, feuilles de temps, relevés BNC, client, photo de facture, état partagé des factures) | test_web, test_paie_temps, test_rapprochement, test_page_fournisseurs | 5 |
| Ajouts des versions 1.0.1 à 1.0.7 (imports internes, port 465, « Déjà au compte de dépôt ? », rapidité web, Sage de la journée et son ouverture, grille des encaissements, textes longs des tableaux, aide sans paramètre) | test_imports_internes, test_courriel, test_encaissements, test_rapidite_web, test_sage_journee, test_web | 10 |
| Version 1.0.8 : le Sage d'une personne passe d'abord | test_sage_journee | 1 |
| Version 1.0.9 : Sage orphelin, pause de l'installateur | test_sage_journee | 2 |
| Version 1.0.10 : le serveur web n'ouvre jamais Sage | test_sage_journee | 1 |
| Version 1.0.11 : réponses aux questions de Sage à la fermeture | test_sage_journee | 1 |
| Version 1.0.12 : entreprise fermée pour inactivité, avertissement d'enregistrement occupé | test_sage_journee | 1 |
| Version 1.0.14 : aucun outil d'import quand un Sage tourne | test_sage_journee | 1 |
| Version 1.0.18 : reconnexion web à la même page, adresse de retour sûre | test_web | 1 |
| Version 1.0.19 : un encaissement en échec ne bloque pas les suivants | test_encaissements | 1 |
| Version 1.0.20 : montant reçu relu avant d'être validé | test_encaissements | 1 |
| **Total** | 60 fichiers | **315** |

Résultat du 7 novembre 2026 (version 1.0.20) : **315 réussis** (1 min 50), compilation de tout le code sans aucun avertissement (`python -W error::SyntaxWarning -m compileall`).

Résultat du 6 novembre 2026 (version 1.0.7) : **305 réussis**, y compris les 2 tests de fenêtres Tk ; compilation de tout le code sans aucun avertissement (`python -W error::SyntaxWarning -m compileall`).

Résultat du 5 novembre 2026 (version 1.0.0) : 292 réussis, 1 sauté (export d'image sans écran disponible), 2 tests de fenêtres Tk lancés à part.

Note : par moments, un test qui ouvre une fenêtre Tk échoue avec « Can't find a usable tk.tcl / init.tcl » ; Windows refuse un instant la lecture des fichiers de Tcl (antivirus). Le test passe à l'exécution suivante : ce n'est pas un défaut de l'application.

---

## 4. Tests d'intégration et de recette

### 4.1 Clover

| N° | Scénario | Attendu | Résultat |
|---|---|---|---|
| C1 | Connexion et commandes d'hier | Nom du marchand, nombre de commandes | Réussi |
| C2 | Rapport et facture d'un jour | Même total net dans les deux | Réussi (au cent près) |
| C3 | Concordance API / export Clover (17, 19 et 23 oct.) | Aucun écart | Réussi |
| C4 | Article d'essai caché : création, prix, coût, stock, UGS, suppression | Chaque valeur relue identique ; article supprimé | Réussi |
| C5 | Employé d'essai : création puis suppression | Créé puis absent | Réussi |
| C6 | Refus passager de Clover (429) | Nouvel essai automatique | Réussi |

### 4.2 Lecture de Sage

| N° | Scénario | Attendu | Résultat |
|---|---|---|---|
| L1 | Sage ouvert sur le vrai fichier et la copie en même temps | Chaque fichier lu sur sa base | Réussi |
| L2 | Sage fermé, vrai fichier et copie | 1re lecture ~10 s, suivantes immédiates | Réussi |
| L3 | Outil d'import refusé | Sage ouvert par l'application (multi-utilisateur), lecture, fermeture | Réussi (81 s la 1re fois) |
| L4 | Entreprise partagée (vrai fichier) | Question « entreprise partagée » répondue | Réussi |
| L5 | Erreur dans une lecture (requête fautive, faute de calcul) | Erreur affichée tout de suite, sans réouverture | Réussi |
| L6 | Base gardée par un autre programme, import demandé | Base relâchée, import fait | Réussi (3,5 s) |
| L7 | Préchargement au démarrage, Sage fermé | Listes ensuite en moins d'une seconde | Réussi (0,1 à 0,4 s) |
| L8 | Démarrage de l'application | Sage jamais ouvert sans action de la personne | Réussi |

### 4.3 Écriture dans Sage (copie d'essai)

| N° | Scénario | Mode | Résultat |
|---|---|---|---|
| S1 | Import d'une facture de vente, puis 2e import | mono-utilisateur | Importée ; doublon refusé |
| S2 | Commande client → facture → import | mono-utilisateur | Réussi |
| S3 | Facture fournisseur et retour (facture négative) | mono-utilisateur | Réussi |
| S4 | Encaissements de dépôts | multi-utilisateur | Appliqués ; déjà appliqué = non refait |
| S5 | Paiement fournisseur (plusieurs factures) | multi-utilisateur | Réussi |
| S6 | Écriture de journal (relevé, dépense avec TPS/TVQ) | multi-utilisateur | Réussi ; question des comptes de taxe répondue |
| S7 | Document de stock : entrée puis sortie depuis un dépôt | multi-utilisateur | Réussi, stock revenu au départ |
| S8 | Transfert entre dépôts, aller puis retour | multi-utilisateur | Réussi, stock revenu au départ |
| S9 | Inventaire compté (ajustement) | multi-utilisateur | Réussi |
| S10 | Création d'article de stock, de service, de client, de fournisseur | multi-utilisateur | Réussi |
| S11 | Correction des comptes d'articles | multi-utilisateur | Réussi |
| S12 | Employé et chèque de paie (heures normales et supplémentaires) | multi-utilisateur | Réussi |
| S13 | Facture de vente puis facture de retour client (quantités négatives) | mono-utilisateur | Réussi, stock revenu au départ |
| S14 | Compte du plan comptable : créé, renommé, rendu inactif, supprimé | multi, mono pour l'inactif | Réussi |
| S15 | Client et fournisseur avec compte de produits / de charges | multi-utilisateur | Réussi |
| S16 | Article : renommé puis remis, service rendu inactif puis supprimé, suppression d'un article en stock | multi, mono pour l'inactif | Réussi ; suppression refusée par Sage (stock) |
| S17 | Prix de vente régulier Sage depuis Clover : 0 → 2,49 → 0 | multi-utilisateur | Réussi (vérifié dans la base) |
| S18 | Assistant d'importation : factures de vente (3) et facture d'achat, puis réimport | mono-utilisateur | Réussi ; réimport refusé « numéro existe déjà » |
| S19 | Transferts après import (dépôt) : achat puis vente, stocks revenus au départ | Sage fermé | Réussi (environ 2 min 45 par transfert) |
| S20 | Vrai fichier partagé (serveur) : 2 factures fournisseurs par l'assistant, stock et coût Clover | mono-utilisateur | Réussi le 5 novembre 2026 |
| S21 | Sage de la journée : ouvert en arrière-plan, 2 saisies qui l'empruntent, puis libéré pour un import par l'assistant | multi, puis mono pour l'import | Réussi : prêt en 0,2 s, saisies en 11 à 13 s, libéré en 30 s, « ESSAI ASSIST 5 » importée |
| S22 | Course reproduite : lectures toutes les 5 s et saisie lancée pendant l'ouverture du Sage de la journée | multi-utilisateur | Réussi : outil d'import jamais lancé, Sage jamais pris pour celui d'une personne, saisie qui attend puis emprunte Sage (fenêtre Encaissements en 7 s) |
| S24 | Sage de la journée rendu orphelin (gardien arrêté comme par l'installateur, Sage jamais touché) | multi-utilisateur | Réussi : reconnu orphelin, jamais pris pour le Sage d'une personne, refermé proprement en 12 s |
| S25 | Application Windows arrêtée brutalement pendant que son Sage est ouvert | multi-utilisateur | Réussi : Sage refermé proprement 10 s après, aucun orphelin |
| S26 | **Vrai fichier (serveur)** : encaissement d'un dépôt réel (2026-01-06, 1 020,36 $ sur « Vente 2026-01-05 ») lancé à distance dans la session de l'administrateur | multi-utilisateur | **Enregistré** (solde 1 102,81 -> 82,45 $) ; question de Sage après « Traiter » mal comprise : corrigé en 1.0.13 |
| S27 | **Vrai fichier (serveur, Sage 2027, 1.0.19)** : dépôts en retard encaissés mois par mois (un lot par mois, une ouverture de Sage chacun), avril à novembre 2026 | multi-utilisateur | **229 encaissés en ~2 h**, 2 à vérifier (dépôt > solde dû ; facture absente des factures en souffrance) : notés, les dépôts suivants saisis |
| S28 | Cellule « Montant reçu » relue avant validation (1.0.20) | multi-utilisateur | Test automatique ; à confirmer au prochain encaissement réel (plus de « Essai 1 : total affiché ») |
| S23 | Fenêtre Encaissements : cellule « Montant reçu » avec la grille normale (791 points) et réduite à la taille du serveur (641 × 96) | multi-utilisateur | Réussi : x = 696 puis 559, bonne colonne, rien de traité |

### 4.4 Profils et droits

| N° | Scénario | Attendu | Résultat |
|---|---|---|---|
| P1 | Administrateur | Tout le menu, page Utilisateurs | Réussi |
| P2 | Comptable | Tout sauf Administration | Réussi |
| P3 | Employé | Facturation des ventes, pointage, son horaire ; pas d'export | Réussi |
| P4 | Profil par fonction : « Liste des articles » seule | Rien d'autre dans la rubrique Articles | Réussi |
| P5 | Onglets des Rapports | Seuls les onglets permis visibles | Réussi |
| P6 | « Supprimer des éléments » retiré | Boutons Supprimer / 🗑 et touche Suppr refusés | Réussi |
| P7 | Action de fenêtre retirée (traiter la paie) | Fenêtre ouverte, action refusée avec message | Réussi |

### 4.5 Traitement de nuit

| N° | Scénario | Attendu | Résultat |
|---|---|---|---|
| N1 | Simulation sur une période déjà facturée | « Rien à importer » | Réussi |
| N2 | Jour bloqué (article non relié) | Signalé, les autres jours continuent | Réussi |
| N3 | Nuit réelle sur la copie d'essai | Factures importées, dépôts encaissés, courriel | Réussi |

### 4.6 Lectures de documents

| N° | Scénario | Attendu | Résultat |
|---|---|---|---|
| D1 | 43 états de compte RIA réels | Tous lus, soldes recontrôlés sans remarque | Réussi (114 opérations) |
| D2 | Formulaires T4 et RL-1 téléchargés des sites officiels | Cases aux coordonnées connues | Réussi (fichiers identiques à ceux de l'application) |
| D3 | PDF des documents et des tableaux dans l'application ouverte | Créés sans Edge, PDF ouvert = nouveau nom | Réussi |
| D4 | Relevé BNC réel (50 mouvements) | Chaque solde revérifié, totaux débit / crédit retrouvés | Réussi |
| D5 | Les 17 types de documents et les 4 documents de stock imprimés | Modèle de chaque type, sans prix là où il le faut | Réussi (contrôle visuel) |
| D6 | Photo de facture envoyée au serveur | PDF, OCR, facture « À saisir (photo) » | Réussi (copie) |

---

### 4.7 Application web (versions 1.1 à 2.24)

| Essai | Résultat |
|---|---|
| Tour des 76 entrées du menu et de 18 écrans de détail sur une copie (vrai Clover, Sage absent) | toutes en 200, aucune erreur |
| Audit des libellés : boutons et cases des 52 fenêtres Windows cherchés dans les pages web | écarts corrigés (2.13.0) |
| Comparaison côte à côte : photo de chaque fenêtre Windows et de la page web à la même taille | dispositions alignées (2.14.0, 2.14.1) |
| Sage absent du serveur | pages affichées, tableaux vides avec leurs colonnes, bandeau |
| Jeton anti-falsification dans une adresse | jamais (formulaires séparés + filet du serveur) |
| DNS `app.marchemvogmbi.com` | adresse Tailscale du serveur |
| Rapidité : 64 pages du menu, 2e tour | 3,8 s (60 ms par page), au lieu de 62,8 s |
| Même facture ouverte dans Windows et sur le web | état identique, jamais ramenée avant « Importée » |
| Rapidité (1.0.3) : 64 pages, 1er passage | 2,8 s au lieu de 70,5 s, aucune page au-dessus de 0,3 s |
| Largeur des tableaux (1.0.6) : 66 pages mesurées dans Chrome sans fenêtre (largeur du tableau / largeur de sa zone) | plus aucun tableau poussé hors de sa zone par un texte long ; 4 tableaux à beaucoup de colonnes défilent à l'horizontale |
| Tour complet (1.0.7) : 124 adresses (menu, onglets, 18 états des statistiques, calculs, rapprochement, encaissements) | toutes en 200, aucune erreur au journal (après correction de /aide) |

## 5. Défauts trouvés et corrigés lors des campagnes

| Défaut | Cause | Correction |
|---|---|---|
| Lecture de Sage fermé refusée après redémarrage | Service de connexion de Sage arrêté ; mot de passe différent dans le vrai fichier | Service démarré, mot de passe aligné ; Sage ouvert par l'application en secours |
| Ouverture du vrai fichier bloquée sans fin | Question « entreprise partagée » sans réponse | Réponse automatique selon le mode |
| Documents de stock et transferts impossibles Sage fermé | Clic sur le libellé du menu ignoré | Clic sur le cadre du libellé |
| Taxes des dépenses dans les comptes de retenues | « payer » contenait « paye » | Comptes lus dans la table des taxes de Sage |
| Dépense refusée par Sage | Question des comptes de taxe associés | Réponse « Oui » |
| 88 s pour une erreur de lecture | Toute erreur relançait l'ouverture | Seules les erreurs de connexion le font |
| Article Clover « introuvable » par moments | Refus passager 429 non réessayé | Nouvel essai |
| Ouverture de Sage au démarrage | Lecture automatique d'une page | Jamais sans action de la personne |
| PDF non créés dans l'application ouverte | Edge s'arrête sans rien écrire | PDF dessinés par l'application (fpdf2) |
| Sage resté ouvert après « Compte inactif » | Question modale de Sage bloquait l'envoi des clics | Mono-utilisateur pour l'inactif, clics sans attente |
| États RIA avec remarques | Lignes ACH, sous-totaux, total à 2 montants | Lecture revue (0 remarque sur 43 états) |
| Bulletin non envoyé (« timed out ») | Port 465 réglé en « starttls » : le serveur attend SSL dès la connexion (constat du 2026-11-06) | Port 465 toujours en SSL ; 3 essais, délai plus long à chaque fois |
| PDF de page (bulletin, rappel) faits par la création de secours | Edge avec une mise à jour en attente ne produit rien sans fenêtre | Chrome essayé après Edge |
| Titre long du cadre (« FACTURE D'AVOIR FOURNISSEUR ») collé aux bords | Police fixe | Police réduite jusqu'à ce que le titre tienne |
| Nuit du 2026-11-06 : ni courriel, ni archivage, ni journal après l'import de 221 factures | Import faux (`Registre` au lieu de `RegistrePaiements`) dans la lecture des avis Interac, hors de toute protection | Nom corrigé ; chaque étape de fin de nuit protégée ; test de tous les imports internes |
| Encaissements : « La cellule Montant reçu ne s'est pas ouverte » (vrai fichier, 221 factures ouvertes) | Grille remplie lentement, clic trop tôt | Clic répété jusqu'à 20 s, photo de la fenêtre dans donnees/diagnostic_encaissements/ |
| Import refusé sur le serveur | Entreprise partagée refusée par l'outil d'import | Assistant d'importation de Sage |
| Assistant introuvable | Menu de Sage à une autre position sur le serveur | Menu repéré par son texte (OCR), photos de diagnostic |
| Abandon après 20 s à l'ouverture de Sage | Écran « Lancement de Sage 50… » pris pour une erreur | Écrans de chargement écartés, 60 s |
| Factures importées restées « Prête à importer » (web, nuit) | Registre non enregistré après l'import | Enregistré dans tous les cas |
| Déconnexion juste après la connexion web | L'icône du site menait à la page de connexion, qui effaçait la session | Icône publique |
| Ajustements du journal 14 pris pour des transferts | Type déduit du journal | Indicateur de transfert de Sage |
| Pages web lentes (3 s) | Recherche de Sage refaite à chaque page | Échec retenu 45 s, base gardée prête |
| Encaissements sur le serveur : 0 dépôt sur 364, « La cellule Montant reçu ne s'est pas ouverte » | Grille plus petite sur le serveur (~640 points, 4 lignes) : clic fixe à x = 692 hors de la grille | Position en proportion de la largeur réelle, lignes lues sur la hauteur, cellule hors colonne refusée (1.0.4) |
| « Fermez Sage sur le serveur » alors que personne n'avait ouvert Sage | Sage de la journée en ouverture pris pour celui d'une personne ; son ouverture refusée parce que l'outil d'import (surveillance du web) prenait l'entreprise | Marque d'ouverture, plus d'outil d'import pendant la journée, saisies qui attendent la fin de l'ouverture (1.0.5) |
| Programme qui ouvre le Sage de la journée bloqué 15 min | Il attendait sa propre marque d'ouverture (trouvé à l'essai S22) | Jamais d'attente de soi-même (1.0.5) |
| Page Rapprochement : Entrée, Sortie, État hors de la zone | Une description très longue élargissait la colonne | Textes longs coupés, texte complet au survol (1.0.6) |
| « Cette entreprise partagée est déjà ouverte » quand le propriétaire ouvre Sage sur le serveur (vrai fichier) | Sage n'ouvre l'entreprise qu'une fois par ordinateur ; le Sage de la journée la tenait dans la même session | Le Sage d'une personne passe d'abord : Sage de la journée refermé en quelques secondes, rouvert 5 min après (1.0.8) |
| Après l'installation de la 1.0.8 : « Fermez Sage » à l'encaissement, Sage impossible à ouvrir (vrai fichier) | L'installation a coupé le gardien pendant la fermeture de Sage ; marque effacée avant la fermeture ; Sage seul sur le bureau caché | Sage du bureau caché toujours celui de l'application, orphelin refermé proprement, installateur qui referme Sage d'abord (1.0.9) |
| Sage resté seul (vrai fichier) qui ne se referme pas ; encaissement : 0 sur 43 | Fenêtre « Sage 50 - Confirmation » sans réponse (texte WinForms non lu) ; deux programmes refermaient le même Sage ; l'encaissement lançait quand même un 2e Sage | Textes WinForms lus (WM_GETTEXT), sauvegarde -> Non, fermeture -> Oui, un seul programme à la fois, saisie arrêtée avec un message clair (1.0.11) |
| Encaissement réel dit « NON encaissé » alors qu'il est dans Sage | Question de Sage après l'enregistrement, texte illisible (GetWindowText) | Texte lu par WM_GETTEXT, photo, la base fait foi (1.0.13) |
| « Un autre utilisateur utilise actuellement cette entreprise » au lancement d'une saisie (vrai fichier) | La surveillance du web relançait l'outil d'import pendant le lancement de Sage (Sage du bureau caché non compté depuis 1.0.9) | `sage_tourne` : aucun outil d'import tant qu'un Sage tourne ou se lance (1.0.14) |
| Encaissements réels : au 1er essai de chaque dépôt après un « Traiter », total affiché = solde dû (~30 s perdues par dépôt) | Sage remplissait la cellule du montant dû après les premiers caractères tapés | Cellule sélectionnée en entier, relue et retapée avant le Tab (1.0.20) |
| `/aide` sans « ?page= » : aucune réponse | Paramètre lu sans valeur par défaut, et la page d'erreur plantait aussi | Valeur par défaut, page d'erreur de secours (1.0.7) |
| Avertissement « invalid escape sequence » (lanceur du serveur web) | « \M » dans un nom de verrou | Chaîne brute (1.0.7) |

---

## 6. Recette avant livraison

1. `python -m pytest` : tout réussi.
2. Lecture des deux fichiers, Sage ouvert puis fermé.
3. Import et doublon sur la copie d'essai.
4. Une saisie multi-utilisateur (document de stock entrée / sortie).
5. Profils Administrateur, Comptable, Employé : menus attendus.
6. Clover : article d'essai caché créé, modifié, supprimé.
7. Fabrication de l'installateur (`installation/fabriquer.cmd`) : manuels et documents refaits.
8. Application web : tour de toutes les pages sur une copie, tout en 200.
9. Contrôle du dépôt public : aucune donnée réelle (noms, courriels, identifiants, montants de clients).

## 7. Reste à tester

- **Correction 1.0.20** (montant reçu relu avant validation) : à confirmer au prochain encaissement réel ; attendu : plus de « Essai 1 : total affiché … ».
- **Deux dépôts à vérifier** après le rattrapage du 7 novembre : un dépôt supérieur au solde dû de sa facture ; une facture absente des factures en souffrance (date de l'année d'avant). À corriger dans Sage, puis relancer.
- **26 dépôts « Espèces à répartir à la main »** : encaissements manuels au rapprochement.
- Paiements fournisseurs sur le vrai fichier : après confirmation du propriétaire.
- Traitement de nuit complet sur SERVDCSAGE avec la 1.0.20 (factures, encaissements des ventes importées, compte rendu).
- Transferts vers un dépôt sur le vrai fichier (dès qu'un deuxième dépôt sera créé dans Sage).
- Relevés BNC de plusieurs mois et écritures saisies au compte 1060.
- Pointage depuis le Wi-Fi du magasin (adresse publique du magasin à relever sur place) et pause automatique d'un téléphone qui sort du Wi-Fi.
- Plusieurs points de vente réels (dès qu'un deuxième sera configuré).
- Remises de retenues réelles.
- Promotions et envoi des bulletins de paie sur des données réelles.
- Écritures RIA : dès que les comptes RIA et commissions seront créés dans Sage.
- Renommage et suppression d'un article Clover depuis la liste des articles (même écriture que le prix, déjà validée).

## 8. Matrice de couverture

| Fonction | Tests automatiques | Copie d'essai | Vrai fichier / production |
|---|---|---|---|
| Facture de vente (jour, fin de semaine) | ✔ | ✔ | ✔ (221 factures, nuit du 6 novembre) |
| Encaissements | ✔ | ✔ | ✔ (229 dépôts, 7 novembre) |
| Paiements fournisseurs | ✔ | ✔ | à faire (confirmation du propriétaire) |
| Factures fournisseurs (assistant d'importation) | ✔ | ✔ | ✔ (Sage 2027) |
| Stock et coût Clover après achat | ✔ | ✔ (article d'essai) | ✔ |
| Rapprochement Desjardins / BNC | ✔ | ✔ | lecture ✔ ; écritures à faire |
| Journal général, dépenses | ✔ | ✔ | à faire |
| Documents de stock, inventaire, transferts | ✔ | ✔ | à faire (un seul dépôt réel) |
| Création d'articles, clients, fournisseurs, comptes | ✔ | ✔ | à faire |
| Prix de vente Sage depuis Clover | ✔ | ✔ | à faire |
| Paie (chèques, bulletins, T4 / RL-1) | ✔ | ✔ | lecture ✔ ; chèques à faire |
| Sage de la journée, Sage orphelin, questions de Sage | ✔ | ✔ | ✔ |
| Application web (76 pages) | ✔ | ✔ (tour complet) | ✔ (serveur) |
| Statistiques Clover | ✔ | — | ✔ (lecture seule) |
