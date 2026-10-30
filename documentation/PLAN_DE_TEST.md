# MVOGMBI_Sync — Plan et rapport de tests

Version 1.0.0 (30 octobre 2026) — Marché MVOG-MBI Sherbrooke.

---

## 1. Stratégie

| Niveau | Quoi | Où | Quand |
|---|---|---|---|
| Tests automatiques | Règles de calcul, formats d'import, droits, registres | `tests/` (pytest), sans Clover ni Sage | À chaque changement, avant chaque installateur |
| Tests d'intégration | Lectures et écritures réelles | Clover réel (articles et employés d'essai cachés, supprimés ensuite) ; Sage sur la **copie** `MVOGMBI_ESSAI.SAI` | À chaque fonction qui écrit dans Clover ou Sage |
| Recette | Parcours complets par profil | Application installée, copie d'essai | Avant une livraison |
| Exploitation | Traitement de nuit réel | Journal `journal_automatique.log`, compte rendu par courriel | Chaque nuit |

Règles :

- Aucun essai d'écriture dans le **vrai** fichier de l'entreprise.
- Dans Clover (production), écriture seulement sur des éléments d'essai cachés, supprimés à la fin.
- Un défaut trouvé reçoit un test automatique quand c'est possible.

---

## 2. Environnement

| Élément | Valeur |
|---|---|
| Poste | Windows 11, session ouverte (verrouillée possible) |
| Python | 3.13, pytest |
| Sage | Sage 50 Comptabilité Supérieur 2026 ; service « Gestionnaire de connexion de base de données » démarré |
| Fichiers Sage | Vrai fichier (lecture seulement), copie d'essai `MVOGMBI_ESSAI.SAI` (lecture et écriture) |
| Clover | Compte marchand réel, jeton avec lecture, inventaire et employés en écriture |
| Commande | `python -m pytest` |

---

## 3. Tests automatiques — 212 tests

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
| **Total** | 48 fichiers | **212** |

Résultat du 30 octobre 2026 : **212 réussis**.

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

---

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

---

## 6. Recette avant livraison

1. `python -m pytest` : tout réussi.
2. Lecture des deux fichiers, Sage ouvert puis fermé.
3. Import et doublon sur la copie d'essai.
4. Une saisie multi-utilisateur (document de stock entrée / sortie).
5. Profils Administrateur, Comptable, Employé : menus attendus.
6. Clover : article d'essai caché créé, modifié, supprimé.
7. Fabrication de l'installateur (`installation/fabriquer.cmd`) : manuels et documents refaits.
8. Contrôle du dépôt public : aucune donnée réelle (noms, courriels, identifiants, montants de clients).

## 7. Reste à tester

- Plusieurs points de vente réels (dès qu'un deuxième sera configuré).
- Remises de retenues réelles (pas encore payées au 30 octobre 2026).
- Promotions et envoi des bulletins de paie sur des données réelles.
