# MVOGMBI_Sync — Notes de version

Version 1.0.14 (13 novembre 2026) — Marché MVOG-MBI Sherbrooke. Éditeur : Concept Informatique inc.

Ces notes résument ce que chaque version a apporté. Le numéro a été remis à **1.0.0** à trois reprises, à la demande du propriétaire, pour marquer une étape :

| Remise à 1.0.0 | Série précédente |
|---|---|
| 30 octobre 2026 | 1.0.0 → 1.46.3 |
| 5 novembre 2026 | 1.0.0 → 2.24.2 |
| 9 novembre 2026 | 1.0.0 → 1.0.44 |

Chaque version a son installateur, et l'historique complet reste dans Git. Les installateurs des séries terminées sont rangés dans `dist/Archives`, un sous-dossier par série. Ce document ne contient aucune donnée réelle.

---

## Version 1.0.14 (13 novembre 2026)

- **Analyse SonarQube complète du code** (63 484 lignes, Python, JavaScript, PowerShell), complétée par Bandit et pip-audit : 7 bugs et 11 vulnérabilités relevés, tous corrigés ou examinés ; résultat final 0 bug, 0 vulnérabilité, notes A en sécurité, fiabilité et maintenabilité ; aucune bibliothèque vulnérable. Rapport : `ANALYSE_SECURITE.md`.
  - contrôles de dates et d'heures qui ne reposent plus sur `assert` (ils disparaissaient avec Python optimisé) ;
  - identifiants des factures saisies tirés au hasard (uuid) au lieu d'un SHA-1 ;
  - expressions régulières en temps linéaire (exports CSV, PDF, adresses courriel) et avis Interac lus sur 20 000 caractères au plus : un texte piégé ne peut plus bloquer l'application ;
  - script `installation\analyse_sonarqube.ps1` pour refaire l'analyse ; règle RG-SEC-15.
- **Tests stables** : les tests qui ouvrent une fenêtre Windows (Tk) échouaient parfois au hasard (fichiers de Tcl tenus un instant par l'antivirus) ; la création de la fenêtre est réessayée (`tests/conftest.py`) : 25 passages de suite réussis, machine chargée.

## Version 1.0.13 (13 novembre 2026)

- **Sécurité** (analyse complète de l'application) :
  - reçus de dépense, factures fournisseurs et états RIA : seuls les PDF et les images sont acceptés, reconnus par leur contenu, et un fichier reçu n'est jamais ouvert sous Windows s'il n'en est pas un ;
  - exports Excel et CSV : un texte venu de l'extérieur (message Interac, nom Clover, ligne de facture) n'est plus jamais pris pour une formule ;
  - mots de passe de l'application Windows : 12 caractères au moins ; empreintes renforcées (600 000 tours), les anciennes refaites à la connexion suivante ;
  - pointage : l'attente après des NIP faux s'allonge (1, 5, 30 puis 120 minutes) et chaque série est notée à l'audit ;
  - serveur web : requêtes invalides refusées, connexions inactives fermées après 30 s, partages réseau refusés dans « Parcourir… » et « Reprendre une configuration ».

## Version 1.0.12 (13 novembre 2026)

- **Correctif web** : les pages web pouvaient afficher « Sage ne répond pas sur le serveur pour l'instant » toute la journée alors que « Tester l'accès à Sage » réussissait. Après un premier échec (Sage fermé), la surveillance du serveur web retombait sur son propre échec noté 20 secondes plus tôt et ne réessayait plus jamais de lire Sage. Elle réessaie maintenant vraiment toutes les 20 secondes ; le message ne répète plus « Sage ne répond pas » plusieurs fois.

## Version 1.0.11 (13 novembre 2026)

- **Documentation refaite** : tous les documents (architecture, documentation fonctionnelle, guide de l'administrateur, règles d'affaires, plan de test, projet, workflows, processus, catalogue des rapports, présentation des services) mis à la version 1.0.11 avec les nouveautés des versions 1.0.1 à 1.0.10 : toutes les banques du Canada, notes de crédit et retours dans Clover, article Sage tapé dans la ligne, nouveau logo, fenêtre web fixe ; PDF, versions Word, manuels d'utilisation (captures refaites avec le nouveau logo) et présentation PowerPoint régénérés. 386 tests automatiques.

## Version 1.0.10 (12 novembre 2026)

- **Relevés PDF des autres banques d'après leurs modèles** : modèle publié par RBC (« Votre relevé de compte » : apostrophe typographique, montants « ,15 », solde de clôture, pied « 1 de 2 ») et par UNI (colonnes Frais / Retrait / Dépôt / Solde, frais remboursés, comptes d'épargne et prêts qui suivent ignorés, notes dans la marge, période « 03-01 à 03-31 2023 ») lus et revérifiés ligne par ligne ; mises en page de TD (date après les montants, « STARTING BALANCE »), Scotia (« $271.49 »), BMO (« Amounts deducted / added ») et Tangerine (colonne « Amount » signée) prises en charge. Le sens de chaque montant est confirmé par le solde imprimé.
- **Neo Financial** et **KOHO** ajoutées à la liste des banques (CIBC, Simplii, Scotia et BMO y étaient déjà).

## Version 1.0.9 (12 novembre 2026)

- **Fenêtre web fixe sur PC** : au-delà de 820 px de large, la page ne défile plus dans son ensemble ; le menu et la liste principale défilent chacun dans leur cadre, et la liste prend toute la hauteur de la fenêtre (au chargement et quand la fenêtre change de taille).

## Version 1.0.8 (12 novembre 2026)

- **Nouveau logo carré** « Marché MVOG-MBI Sherbrooke, le carrefour des cultures » dans l'application, sur le site web et dans les documents ; l'emblème (Afrique, feuille d'érable, M, panier) sert d'icône ; filigrane de l'accueil sans fond blanc.

## Version 1.0.7 (12 novembre 2026)

- **Toutes les banques du Canada** : rapprochement, encaissements et paiements ne sont plus limités à Desjardins et à la Banque Nationale. Relevés en OFX / QFX / QBO (téléchargement offert par toutes les banques), en CSV (en-tête français ou anglais, ou sans en-tête, sens des montants contrôlé par le solde) ou en PDF dont l'en-tête nomme ses colonnes (« Withdrawals / Deposits / Balance »). Banque du compte de dépôt des ventes au choix (Administration > Sage 50), comptes ajoutés de n'importe quelle banque ou caisse ; un relevé chargé va dans le compte dont le n° y figure, sinon dans celui de sa banque. Virements Interac reçus, dépôts au guichet et dépôts de paie reconnus en français et en anglais ; avis Interac en anglais lus pour les paiements fournisseurs.

## Version 1.0.6 (11 novembre 2026)

- **Notes de crédit des fournisseurs** : un document intitulé « CREDIT » ou « NOTE DE CRÉDIT » est reconnu à la lecture (case « Note de crédit », Windows et web) ; quantités et montants en négatif ; importé dans Sage en crédit ; le stock Clover diminue, le coût ne change pas. Les notes de crédit déjà dans la liste sont relues d'elles-mêmes.

---

## Version 1.0.5 (10 novembre 2026)

- **Retours fournisseurs** : un retour importé dans Sage retire maintenant les quantités du stock Clover des articles reliés (avant, le stock Clover ne bougeait pas) ; le coût Clover n'est jamais changé par un retour.

---

## Version 1.0.4 (10 novembre 2026)

- **Correctif web** : les pages « Rapprochement » et « Mes paies » pouvaient s'arrêter sur une erreur en lisant Sage (fonction de lecture non importée). Défaut trouvé par une vérification automatique du code.

---

## Version 1.0.3 (10 novembre 2026)

- **Factures fournisseurs** : n° et désignation de l'article Sage tapés directement dans la ligne, avec liste de propositions ; la page web ne se déconnecte plus pendant la saisie ; une ligne n'est plus reliée par erreur à l'article de la ligne précédente.

---

## Version 1.0.2 (10 novembre 2026)

- **Documentation installée avec l'application** : documents PDF et Word (.docx) à la version en service, chacun avec sa page d'accueil et son sommaire ; manuel d'utilisation et présentation PowerPoint refaits.

---

## Version 1.0.1 (9 novembre 2026)

- **Factures fournisseurs en deux onglets**, sous Windows et sur le web : « 📋 Liste des factures » (filtres Afficher, Fichier, Fournisseur, N° de facture ; cases à cocher et imports) et « ✏ Saisie de la facture » (liste déroulante « Facture à traiter », ◀ ▶, enregistrement automatique).
- **Documentation mise à jour** : captures d'écran du manuel refaites avec la version en service (Reporting, Synthèse et décisions, Articles rentables ou non, Opérations journalières, factures fournisseurs en onglets) ; **page d'accueil** en tête de chaque document ; chaque document fourni aussi au **format Word** (.docx).

---

## Version 1.0.0 (9 novembre 2026)

Point de départ de la nouvelle série, qui reprend tout ce qui est décrit ci-dessous. Il comprend :

- la synchronisation Clover → Sage 50 la nuit ;
- les encaissements ;
- les fournisseurs ;
- le rapprochement Desjardins et BNC ;
- la paie ;
- les stocks multi-dépôts ;
- la comptabilité ;
- l'agence RIA ;
- l'application web identique à Windows ;
- le **Reporting** avec 18 états enrichis, 44 analyses décisionnelles et 7 rapports de gestion.

369 tests automatiques réussis.

---

## Série du 5 au 9 novembre 2026 (anciennes 1.0.0 à 1.0.44)

### Reporting et aide à la décision

| Version | Apport |
|---|---|
| 1.0.22 | Analyses décisionnelles dans les statistiques Clover : anomalies, tendance, variation, paniers, concentration, matrice des articles, achats associés, employés, groupes de clients, fidélité |
| 1.0.23 | La facture Clover s'ouvre depuis tout n° de commande ; textes des graphiques jamais tronqués |
| 1.0.24 | Décisions de la direction dans le courriel du matin ; PDF complet des analyses |
| 1.0.25 | Opérations journalières (ventes, achats, encaissements, paiements : quand et par qui) ; récapitulatif des traitements ; éléments concernés sous chaque décision ; rabais Direction et administrateurs mis à part |
| 1.0.26 | Pourquoi le bénéfice change (pont de marge), catégories qui montent ou baissent, achalandage et personnel |
| 1.0.27 – 1.0.28 | Rythme et objectif ; sous-pages Résumé / Graphiques / Détail ; mots simples à la place du jargon ; polices uniformes ; remboursements à surveiller ; espèces et cartes |
| 1.0.29 | Nouveaux articles, jours fériés |
| 1.0.30 – 1.0.32 | Taxes et pourboires, quand le magasin gagne le plus, seuil de rentabilité, articles qui baissent, catégories selon le jour, valeur des clients, achalandage prévu, quantités prévues, jour du mois, articles de saison, ventes au poids, ruptures probables, articles d'appel |
| 1.0.33 – 1.0.34 | Ventes complémentaires manquées, prix selon le format |
| 1.0.35 | Les 18 états de base ont leurs sous-pages Résumé / Graphiques / Détail comparées à la période d'avant |
| 1.0.36 | Tranches de prix, ce qui fait monter ou baisser les ventes, effet des rabais |
| 1.0.37 | Rapports à la taille de la fenêtre, titres « Détail : … », graphiques interactifs |
| 1.0.39 | « Statistiques Clover » devient « Reporting » ; évolution par jour et par mois côte à côte ; ruban horizontal des états |
| 1.0.40 – 1.0.43 | Productivité de l'assortiment, prix et volume, articles qui se remplacent, articles qui montent ; filtres du Détail |
| 1.0.44 | Mêmes filtres (texte + groupe) dans le Détail de chaque état |

### Factures fournisseurs

| Version | Apport |
|---|---|
| 1.0.16 – 1.0.17 | Import par l'assistant de Sage validé sur le vrai fichier partagé (Sage 2027) ; factures déjà dans Sage archivées sans deuxième import |
| 1.0.28 | Les factures importées quittent la liste pour les archives ; « Refaire la mise à jour Clover » depuis les archives ; assistant de saisie de l'article Sage |
| 1.0.29 – 1.0.30 | Liste et saisie côte à côte sur grand écran ; filtres Fichier, Fournisseur, N° de facture gardés ; touche Entrée qui valide la ligne sans jamais supprimer |
| 1.0.38 | Lignes taxées « F P » (A.M.R.) et « TX » lues ; articles proposés même quand le fournisseur vend à la caisse ; facteur proposé pour les articles au poids ; passage à la ligne suivante à relier ; « Confirmer toutes les propositions » ; case « Mettre à jour le stock Clover » sur chaque facture |

### Sage 50 et encaissements

| Version | Apport |
|---|---|
| 1.0.3 – 1.0.5 | Sage ouvert pour les saisies de la journée ; contrôle « Déjà au compte de dépôt ? » ; pages web instantanées |
| 1.0.4 | Colonne « Montant reçu » trouvée selon la taille réelle de la grille de Sage |
| 1.0.8 – 1.0.12 | Le Sage d'une personne passe d'abord ; Sage orphelin refermé ; réponses aux questions de Sage à la fermeture ; entreprise fermée pour inactivité |
| 1.0.13 – 1.0.15 | Encaissements réels validés (Sage 2027) ; fenêtre « Traitement… » attendue sans jamais être touchée |
| 1.0.19 | Un encaissement ou un paiement en échec ne bloque plus les suivants (229 dépôts en retard encaissés le 7 novembre) |
| 1.0.20 | Montant reçu relu dans la cellule avant d'être validé |

### Web, sécurité, ergonomie

| Version | Apport |
|---|---|
| 1.0.6 | Textes longs coupés dans les tableaux (texte complet au survol) ; rubrique RIA |
| 1.0.18 | Verrouillage pour inactivité : les traitements continuent, la reconnexion revient à la même page |
| 1.0.21 | Web toujours en thème clair, lisible sur les téléphones en mode sombre |
| 1.0.23 | Pointage hors Wi-Fi permis aux administrateurs seulement |
| 1.0.28 – 1.0.39 | Filtres automatiques sur tout le web (sans bouton « Afficher ») ; bandeau « Chargement… » |
| 1.0.39 | Suivi des ventes : statut « Remplacée » pour une facture d'un jour couverte par la facture de fin de semaine |

### Documentation

| Version | Apport |
|---|---|
| 1.0.1 – 1.0.2 | Guide de l'administrateur ; PDF lisibles (diagrammes à la bonne échelle) |
| 1.0.7, 1.0.20 | Documentation complète mise à jour |
| 1.0.0 (9 nov.) | Catalogue des rapports, notes de version, présentation des services, présentation PowerPoint détaillée |

---

## Séries précédentes (résumé)

- **Série 2.x (30 octobre – 5 novembre 2026)**, dans l'ordre :
  - application web : connexion, pages identiques à Windows, export, HTTPS, client Windows ;
  - serveur SERVDCSAGE ;
  - pointage sur le Wi-Fi ;
  - mot de passe web distinct ;
  - prix de vente Sage depuis Clover ;
  - dépôts multi-sites ;
  - assistant d'importation pour l'entreprise partagée ;
  - relevés BNC et comptes bancaires ;
  - modèles d'impression de tous les documents.
- **Première série (26 – 30 octobre 2026)** :
  - facturation de nuit, encaissements, factures et paiements fournisseurs ;
  - rapprochement Desjardins ;
  - statistiques Clover ;
  - utilisateurs et droits ;
  - gestion commerciale (bons de commande, prix et marges) ;
  - paie complète avec Sage Paie ;
  - plusieurs points de vente ;
  - transferts ;
  - inventaire ;
  - RIA ;
  - sauvegarde ;
  - caisse ;
  - pertes ;
  - congés ;
  - documents de vente, d'achat et de stock comme Sage.
