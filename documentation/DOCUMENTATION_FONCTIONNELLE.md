# MVOGMBI_Sync — Documentation fonctionnelle

Version 1.0.18 (6 novembre 2026) — Marché MVOG-MBI Sherbrooke. Éditeur : Concept Informatique inc.

Ce document décrit **ce que fait** l'application et **selon quelles règles**, pour le propriétaire, le comptable et les personnes qui l'utilisent. Le détail de chaque règle, avec son code, est dans le document des règles d'affaires ; le fonctionnement interne est dans le document d'architecture ; le mode d'emploi pas à pas est dans le manuel d'utilisation ; l'installation, la configuration et le dépannage sont dans le guide de l'administrateur.

---

## 1. Objet et périmètre

Le marché encaisse ses ventes avec **Clover** (caisse et terminal de paiement) et tient sa comptabilité dans **Sage 50 Comptabilité Édition canadienne**. Les deux ne communiquent pas. MVOGMBI_Sync fait le lien, sans ressaisie :

| Besoin | Réponse de l'application |
|---|---|
| Passer les ventes de la caisse en comptabilité | Une facture de vente par jour (une seule pour la fin de semaine), une ligne par article, importée la nuit |
| Encaisser les dépôts bancaires | Dépôts Clover, virements Interac et dépôts d'espèces appliqués sur les factures |
| Traiter les factures des fournisseurs | Lecture des PDF (courriel, dossier ou photo prise au téléphone), correspondance des articles, import dans Sage (aussi la nuit), mise à jour du stock Clover |
| Payer les fournisseurs | Avis de virement Interac lus et rapprochés des factures, paiement saisi dans Sage |
| Contrôler la banque | Relevés Desjardins et Banque Nationale (BNC) rapprochés du compte Sage de chaque banque ; autres comptes bancaires ajoutés dans la configuration |
| Travailler sur plusieurs sites | Dépôts (emplacements de Sage), avec ou sans Clover : factures, stock, employés, planning et états par dépôt |
| Tenir l'agence RIA | États de compte RIA lus, envois et versements passés dans Sage, commissions reconnues |
| Piloter le commerce | Statistiques comme Clover, bénéfices au coût moyen Sage, prévisions, articles 20/80, péremption, rapports de gestion |
| Gérer comme dans Sage | Listes, fiches, chaîne des documents de vente et d'achat, documents de stock, plan comptable ; créations, modifications et suppressions dans Sage et dans Clover |
| Tenir la paie | Pointage par NIP, planning, feuilles de temps, chèques de paie dans Sage, bulletins, T4 et RL-1 officiels |
| Contrôler l'accès | Comptes, profils, droits fonction par fonction, audit des actions |
| Travailler à distance | Application web identique à l'application Windows (76 entrées du menu), sur PC, tablette et téléphone, par Tailscale ; client des postes ; Bureau à distance pour l'application complète |

Hors périmètre : la comptabilité générale elle-même (Sage reste la référence), la banque en ligne (relevés chargés à la main), le calcul des retenues de paie (fait par Sage Paie).

---

## 2. Acteurs et profils

| Acteur | Rôle | Profil de départ |
|---|---|---|
| Propriétaire / gérant | Configure, valide la correspondance, approuve, consulte tout | Administrateur |
| Gérant | Planning, feuilles de temps, voit tous les employés | Gérant |
| Comptable | Factures fournisseurs, paiements, rapprochement, comptabilité, RIA, paie | Comptable |
| Employé de caisse | Facturation des ventes, pointage, ses heures, son horaire et ses paies | Employé |
| Traitement de nuit | Tâche planifiée Windows, sans connexion | — |

Règles d'accès :

- L'**Administrateur** a toujours tout et gère les utilisateurs ; il en reste toujours au moins un actif.
- Chaque profil reçoit ses **fonctions une à une** (arbre du menu) : cocher « Liste des articles » donne cette liste seulement, pas toute la rubrique Articles.
- Des **actions dans les fenêtres** se retirent à part (traiter la paie, restaurer une sauvegarde, saisir les dépenses, modifier les articles dans Sage et Clover, modifier le plan comptable…), ainsi que **« Supprimer des éléments »** et **« Exporter les données »**.
- Un profil peut être limité à certains **points de vente** ; le profil Employé ne voit que **ses** heures, paies et feuillets.
- Les mêmes comptes, profils et droits servent dans l'application Windows et dans l'application web.
- Application web : mot de passe à part, 12 caractères au moins avec minuscule, majuscule, chiffre et caractère spécial, créé à la 1re connexion web.
- Mot de passe d'au moins 6 caractères, jamais gardé en clair ; **3 essais faux = compte verrouillé** ; écran verrouillé après 5 minutes sans activité (application web : déconnexion après 5 minutes sans activité).
- Un compte se **désactive** sans être supprimé (employé parti ou absent) ; ses sessions se ferment.
- Chaque action est notée à l'**audit** (qui, quand, sur quel poste, dans quelle fenêtre).

---

## 3. Fonctions par rubrique du menu

### 3.1 Accueil

- « Mise en route » en 10 étapes, chacune cochée quand elle est faite.
- Résumé de la journée, courbe d'évolution des ventes, alertes.

### 3.2 Administration

| Fonction | Ce qu'elle fait |
|---|---|
| Clover | Identifiant marchand, jeton d'accès (gardé dans le coffre-fort Windows), points de vente |
| Sage 50 | Fichier de l'entreprise, utilisateur de lecture, client des ventes, dépôts sans Clover (entrepôt, réserve…) ; carte « Paie » (première paie de l'année, délai de paiement) ; carte « Comptes bancaires (rapprochement) » (Desjardins, BNC et autres comptes : banque, format du relevé, compte Sage, n° de compte) |
| Courriel | Envoi du compte rendu et copie cachée (Cci) ; boîte des avis de paiement et des factures ; boîte des états RIA |
| Automatisation | Heure du traitement de nuit, date de départ, encaissements automatiques, « Lancer maintenant » ; carte « Serveur de l'application » (ordinateur, adresse Tailscale, adresse locale, nom tapé dans le client, port, certificat et clé HTTPS, fichier `serveur.json` du client) ; carte « Wi-Fi du magasin (pointage) » (nom du Wi-Fi, adresses du magasin, postes du magasin) |
| Sauvegarde des données | Archive chaque nuit, conservation 14 jours / 8 semaines / 12 mois, restauration |
| Journal des opérations | Ce qui a été fait, filtres par date, source et texte |
| Audit des actions | Chaque bouton, entrée du menu et connexion ; lignes chaînées, une modification est repérée |
| Tableau du gérant | Page pour téléphone mise à jour chaque nuit |
| Utilisateurs | Comptes (ajouter, changer le profil, nouveau mot de passe, activer / désactiver, supprimer), profils, fonctions permises, droits, déverrouillage |

### 3.3 Articles

| Fonction | Règles principales |
|---|---|
| Liste des articles | Caractéristiques Clover et Sage côte à côte ; comptes, coût moyen (CUMP), stock ; filtre **Dépôt** (stock et valeur des dépôts choisis). **Modifier** : description et inactif dans Sage, article Clover relié renommé. **Supprimer** : de Sage puis de Clover ; si Sage refuse (article encore en stock), l'article est rendu inactif et l'article Clover gardé |
| Articles Clover | Catalogue Clover, date de péremption lue dans l'UGS, UGS qui ne sont pas des dates effacées sur confirmation |
| Créer un article | **Stock** : créé dans Clover et dans Sage en une fois, prix de vente proposé = coût + 40 %, date de péremption obligatoire dans l'UGS. **Service** : créé dans **Sage seulement**, jamais dans Clover ; n° « S… », compte de charges obligatoire, compte de produits facultatif |
| Étiquettes de prix | Feuilles Avery 5160 ou imprimante à tickets, code-barres Code 128, prix au poids |
| Promotions | Prix promotionnel appliqué le 1er jour, prix normal remis après — jamais par-dessus un prix changé entre-temps ; une promotion en cours peut être **annulée** (prix normal remis tout de suite) |
| Correspondance | Lien article Clover → numéro Sage ; « Confirmé » par le propriétaire ; **deux formats différents = deux articles différents** |
| Coûts Clover depuis Sage / Prix et marges | Coût Clover = CUMP Sage ; prix proposé selon la marge minimale ; valeurs aberrantes jamais appliquées |
| Prix de vente Sage depuis Clover | Prix de vente régulier de Sage remplacé par le prix Clover des articles reliés, lignes cochées, vérifié dans Sage |

### 3.4 Stock

| Fonction | Règles principales |
|---|---|
| Documents de stock | Entrée, sortie, ajustement, **toujours depuis un dépôt** ; passés dans Sage puis Clover ; un document passé s'annule par son inverse ; colonne et filtre **Dépôt** (lu dans Sage, « départ → arrivée » pour un transfert) ; imprimés « Mouvement d'entrée » / « Mouvement de sortie » |
| Transferts entre magasins | Sage d'abord (transfert entre emplacements), puis stocks Clover des deux points de vente ; « Bon de transfert » imprimé (quantité reçue et signatures à remplir) |
| Pertes et démarque | Motif obligatoire (périmé, abîmé, vol…), coût au CUMP, sortie de stock Sage puis Clover, taux de perte ; une perte s'ouvre, se modifie ou s'annule |
| Inventaire / inventaire tournant | Fichier à remplir, quantités comptées saisies dans Clover et dans Sage ; « Écart d'inventaire » imprimé (théorique, compté, écart, valeur) ; catégories réparties sur 8 semaines |
| Livre d'inventaire | Stock et valeur à une date, par catégorie et par dépôt |

### 3.5 Vente

| Fonction | Règles principales |
|---|---|
| Ventes Clover → factures Sage | Voir 4.1 |
| Clients | Liste et fiches lues dans Sage ; création de clients dans Sage (compte de produits, « mes n° d'articles ») |
| Documents de vente | Chaîne **devis → commande → préparation / livraison → facture**, retour client → facture de retour ; « Transformer » reprend les lignes ; seules les factures touchent le stock, Sage puis Clover ; un modèle d'impression par type (bon de préparation et **bon de livraison sans prix**, devis valable 30 jours…) ; la facture se passe dans le dépôt choisi |
| Clients professionnels et relances | Factures échues, lettre de relance envoyée au seul client |

### 3.6 Fournisseur

| Fonction | Règles principales |
|---|---|
| Factures fournisseurs | Lues dans les PDF (texte ou OCR Windows) ou **photographiées depuis le téléphone** (une photo par page, un PDF) ; totaux contrôlés ; Qté Sage = Qté × Facteur ; Prix Sage = Montant / Qté Sage ; n° de facture obligatoire ; doublons refusés ; **dépôt** de réception ; plusieurs factures **cochées** importées en une fois ; les factures prêtes sont aussi importées la nuit ; compte rendu par courriel après un import ; même état en temps réel dans Windows et sur le web ; « Bon de réception » (sans prix) et « Facture (avec prix) » imprimés ; « Refaire la mise à jour Clover » |
| Documents d'achat | Chaîne **demande de prix → bon de commande → réception → facture**, retour → facture de retour ; **bon de réception sans prix** |
| Bons de commande | Proposés d'après les ventes et le stock (couvrir 7 à 28 jours), un bon par fournisseur en unités du fournisseur, comparés à la facture reçue |
| Retours fournisseurs | Facture d'achat négative importée, stock Clover diminué |
| Factures archivées | PDF, détail et Excel classés par année |

### 3.7 Comptabilité

| Fonction | Règles principales |
|---|---|
| Encaissements | Voir 4.2 |
| Paiements fournisseurs | Avis Interac rapprochés, confirmés par le propriétaire, saisis dans Sage ; jamais plus que le solde dû |
| Rapprochement bancaire | Relevé **Desjardins ou BNC** (banque reconnue à la lecture, rangé dans son compte) comparé au compte Sage de cette banque ; liste « Banque » ; écart expliqué ligne par ligne ; un virement entre deux comptes de banque est permis |
| Contrôle de la caisse | Espèces attendues (fond + ventes en espèces − remboursements − remises) contre comptage par coupures ; alerte au-delà de 5 $ |
| Petite caisse et dépenses | Dépense avec reçu, TPS / TVQ séparées dans les bons comptes, écriture dans Sage |
| Plan comptable | Comptes de Sage lus, créés, modifiés, rendus inactifs ou supprimés depuis l'application |
| Âge des comptes, déclaration TPS/TVQ, prévision de trésorerie, budget, clôture du mois | Lus dans Sage, comparés aux taxes Clover et au budget |

### 3.8 RIA

| Fonction | Règles principales |
|---|---|
| Opérations RIA | Mouvements RIA des relevés, surplus de dépôts d'espèces, paiements en espèces, commissions et opérations venues des états ; « Saisir dans Sage » écrit les écritures de journal ; le compte RIA de bilan revient à zéro, seules les commissions sont un revenu |
| États de compte RIA | États RIA importés à la main ou par courriel, recontrôlés ligne par ligne ; « Traiter dans Sage » crée les opérations (voir 4.3) |
| Comptes RIA | Comptes RIA, commissions et espèces ; chacun doit exister dans le plan comptable |

### 3.9 Paie

| Fonction | Règles principales |
|---|---|
| Pointage | Au magasin, par NIP de 4 à 6 chiffres ; arrivée, pause, départ ; 5 erreurs = blocage d'une minute |
| Planning mensuel / Mon horaire | Quarts par employé ; **une cédule par dépôt** (filtre Dépôt, quart dans un autre dépôt marqué « @dépôt ») ; chacun voit son horaire publié |
| Feuilles de temps | Présence − pauses ; heures supplémentaires au-delà de 40 h par semaine ; **approuvées par le gérant seulement** ; une feuille changée revient « À approuver » ; « Suivi des périodes » (en cours, à approuver, approuvée, envoyée à Sage) et rappel au courriel du matin ; filtre Dépôt |
| Employés | Créés dans Clover et dans Sage Paie, courriel obligatoire pour le bulletin ; **dépôt principal** de chacun ; le NAS n'est jamais gardé |
| Jours fériés et congés | Normes du travail du Québec : indemnité = 1/20 des 4 semaines précédentes, vacances 4 % / 6 % |
| Calendrier de paie | Paies aux 14 jours à partir de la première paie de l'année (réglée dans Administration > Sage 50) |
| Traitement de la paie | Heures **approuvées** de l'application → chèques de paie dans Sage, jamais pour une période à venir ; bulletins imprimés ou envoyés, un destinataire par bulletin |
| Retenues et remises | Montants à remettre par organisme, échéance le 15 du mois suivant, alerte de retard |
| T4 et Relevé 1 | Formulaires officiels téléchargés des sites de l'ARC et de Revenu Québec, remplis d'après les paies de Sage ; imprimés pour un, plusieurs ou tous, ou envoyés à chacun ; NAS jamais écrit |
| Fin d'emploi, concordance, coût de la main-d'œuvre | Préparés d'après les paies de Sage et les heures pointées |

### 3.10 État

Suivi des ventes facture par facture (**tous les points de vente**, colonne et filtre Dépôt), recherche dans l'historique Sage (client, fournisseur, article, catégorie), statistiques comme Clover (aperçu, rapports, finances, articles, employés, clients, prévisions), produits inactifs, articles 20/80. Les filtres acceptent **plusieurs valeurs** (articles, catégories, employés…) et un ou plusieurs **points de vente**.

Section **« Gestion »** des statistiques : un rapport par fonction de gestion (pertes et démarque, contrôle de la caisse, petite caisse et dépenses, main-d'œuvre, promotions, retours fournisseurs, bons de commande). Ils suivent le filtre « Point de vente » (pertes, promotions, retours, caisse et main-d'œuvre du point de vente choisi). Pour la période choisie, chacun présente des **cartes d'indicateurs**, un **graphique d'évolution** (par jour jusqu'à 62 jours, sinon par mois), une **carte graphique de répartition** (par motif, compte, employé, fournisseur ou état) et le **rapport détaillé** exportable. Chaque tableau s'exporte (si le profil le permet) en Excel, CSV, PDF ou s'imprime avec l'en-tête de l'entreprise.

Dans l'application web, chaque tableau garde ses cellules sur une ligne, comme dans Windows : un texte de plus de 45 caractères est coupé (« … ») et se lit en entier en passant la souris dessus, pour que les montants et les états restent toujours visibles.

---

## 4. Règles de gestion principales

Les règles complètes, codées par module, sont dans le document **Règles d'affaires**. Les principales :

### 4.1 Facturation des ventes

1. Une vente est datée de son **premier paiement réussi**, pas de la création de la commande.
2. **Une facture par jour du lundi au jeudi, une seule du vendredi au dimanche** (« Vente AAAA-MM-JJ/JJ »), datée du dimanche.
3. Une ligne par article Sage : montant = ventes nettes Clover ; prix = ventes nettes / quantité nette (4 décimales) ; total = ventes nettes.
4. Code de taxe « GQ » (TPS 5 % + TVQ 9,975 %) pour les lignes taxées dans Clover.
5. Client « Vente Hebdomadaire », mode « Payer plus tard » ; un client et un préfixe par point de vente.
6. Une facture **n'est jamais importée deux fois** ; un jour incomplet (article non relié, compte manquant) est bloqué et signalé, les autres jours continuent.

### 4.2 Encaissements

1. Dépôt Clover = encaissements par carte du lot du soir ; ventes du lundi au jeudi déposées le lendemain, fin de semaine déposée le lundi.
2. Encaissement daté du dépôt, « Payé par : Comptant », appliqué sur la facture du jour ou de la fin de semaine.
3. Virements Interac et dépôts d'espèces du relevé : répartis sur les factures qui ont encore des espèces dues.
4. Dépôt d'espèces supérieur aux espèces dues, même cumulé sur plusieurs journées : les factures sont couvertes de la plus ancienne à la plus récente, le surplus est la part de RIA à confirmer ; rien n'est encaissé avant sa confirmation.
5. Un dépôt n'est jamais saisi deux fois ; le solde dû de la facture est vérifié après chaque saisie.
6. Un lot de cartes dont le **montant exact est déjà au compte de dépôt** par une autre écriture Sage (3 jours avant à 7 jours après le dépôt) passe à « Déjà au compte de dépôt ? » : il est à vérifier et n'est jamais encaissé d'office, pour ne pas compter la banque deux fois.

### 4.3 RIA

1. Envoi reçu en espèces : débit espèces, crédit compte RIA.
2. Versement ou remboursement payé en espèces : débit compte RIA, crédit espèces ; payé par virement Interac : rien à écrire, la banque l'a déjà.
3. Règlements de RIA et dépôts : traités comme mouvements de banque.
4. Commission : le dépôt du montant de la commission payée est reconnu d'office.
5. Chaque ligne d'état ne devient une opération qu'une fois ; rien n'est écrit dans Sage tant que les comptes RIA ne sont pas renseignés.

### 4.4 Sage

- **Import** (factures de vente et d'achat) : Sage fermé, **mono-utilisateur**. L'entreprise est **partagée** : l'outil d'import la refuse, l'application passe alors par l'**Assistant d'importation des transactions** de Sage, sans arrêter le partage.
- **Saisies** (encaissements, paiements, journal, stock, fiches, plan comptable, paie) : **multi-utilisateur**, la personne peut garder Sage ouvert. Exception : rendre un compte ou un article inactif, que Sage n'accepte qu'en mono-utilisateur.
- **Sage lié à l'application Windows** : de 6 h à minuit, tant que l'application Windows est ouverte, elle garde Sage ouvert en multi-utilisateur (fermée : Sage reste fermé) ; chaque saisie l'utilise tel quel (prête en moins d'une seconde au lieu d'environ 2 minutes d'ouverture). Un import le referme d'abord, puis il se rouvre de lui-même. La nuit, Sage est refermé et le traitement de nuit fonctionne comme avant. Une personne qui ouvre Sage sur le serveur passe d'abord : le Sage de la journée lui laisse la place en quelques secondes et se rouvre 5 minutes après la fermeture de son Sage. Réglage `[sage] garder_ouvert = false` : ancien fonctionnement.
- Chaque écriture est **vérifiée dans la base de Sage** après coup.
- Tout essai se fait d'abord sur une **copie** du fichier d'entreprise.
- L'application ne modifie jamais les paramètres de Sage.

### 4.5 Dépôts et sites

1. Un **dépôt** est un emplacement d'inventaire de Sage : celui d'un point de vente Clover, l'« Emplacement par défaut » ou un dépôt sans Clover (entrepôt, réserve).
2. Une facture (vente, achat, retour) s'importe dans l'emplacement par défaut, puis un **transfert** « DP <n° de facture> » la place dans son dépôt : vente et retour fournisseur = du dépôt vers le défaut, achat = du défaut vers le dépôt ; jamais refait. Si le transfert échoue, la facture reste importée et le transfert est signalé « à refaire ».
3. Clover n'est mis à jour que pour un dépôt qui a un point de vente.
4. Chaque employé a un dépôt principal ; un quart peut être dans un autre dépôt.
5. Les états (documents de stock, livre d'inventaire, liste des articles, main-d'œuvre, suivi des ventes) se filtrent sur un ou plusieurs dépôts, ou « Tout sélectionner ».

### 4.6 Données et confidentialité

- Secrets (jeton Clover, mots de passe Sage et courriel) dans le coffre-fort de Windows uniquement.
- Aucune intelligence artificielle ni service externe pour lire les factures : OCR intégré à Windows.
- Les boîtes de courriel sont lues sans marquer les messages comme lus.
- Données du marché dans le dossier `donnees/`, sauvegardé chaque nuit ; jamais publiées.

---

## 5. Traitement de nuit

Chaque nuit, sans intervention (le Sage gardé ouvert pour la journée est refermé d'abord) :

1. Factures fournisseurs et avis de paiement reçus par courriel lus ; factures « Prête à importer » importées dans Sage.
2. États de compte RIA reçus lus ; opérations saisies dans Sage si les comptes sont renseignés.
3. Ventes Clover lues pour chaque jour sans facture, du plus ancien au plus récent.
4. Factures préparées, contrôlées, importées dans Sage par lots (par l'assistant d'importation si l'entreprise est partagée), puis transférées dans le dépôt de leur point de vente.
5. Dépôts des ventes importées encaissés.
6. Paiements fournisseurs confirmés saisis.
7. Promotions appliquées, statistiques préchauffées, tableau du gérant écrit.
8. Données sauvegardées.
9. Compte rendu par courriel : résumé du matin (ventes, marge, solde, factures à payer, ruptures, péremption, alertes) et une pièce jointe Excel par module.

---

## 6. Données gérées

| Donnée | Source de vérité | Gardée dans l'application |
|---|---|---|
| Ventes, articles, stocks Clover, employés | Clover | caches par jour, catalogue |
| Factures, encaissements, comptes, articles et stocks Sage | Sage | lectures gardées quelques minutes |
| Correspondance Clover → Sage | Application (validée par le propriétaire) | `correspondance_articles.xlsx` |
| Factures fournisseurs lues, bons de commande, documents | Application, puis Sage | registres JSON, PDF, impressions |
| Relevés bancaires | Banque (PDF chargé à la main) | un dossier par compte (`releves_<code>/`) |
| Dépôts | Sage (emplacements) + réglage « dépôts sans Clover » | `config.toml` |
| États et opérations RIA | RIA (états), application (opérations), puis Sage | `ria.json`, `etats_ria/` |
| Pointages, feuilles de temps, planning, congés | Application | registres JSON (jamais effacés) |
| Comptes, droits et audit | Application | `utilisateurs.json` (empreintes), `audit.jsonl` |

---

## 7. Contraintes et prérequis

- Un serveur Windows qui a Sage 50 ET MVOGMBI_Sync (traitement de nuit, serveur web) : SERVDCSAGE depuis le 4 novembre 2026 ; réglé dans « Administration > Automatisation », rien n'est écrit dans le programme.
- Tailscale sur le serveur et sur chaque appareil qui utilise l'application web (postes, téléphones) ; nom `app.marchemvogmbi.com` (DNS) vers l'adresse Tailscale du serveur.
- Pointage : appareils sur le Wi-Fi du magasin (adresse publique du magasin réglée), ou postes du magasin listés ; un téléphone qui a servi à pointer et quitte le Wi-Fi 5 minutes de suite met l'employé en pause, reprise à son retour.
- Windows 10 ou 11, Sage 50 CA 2026 installé ; Microsoft Edge pour les pages HTML (fiches de paie, PDF de la page des statistiques) ; les autres PDF sont créés par l'application.
- Service « Sage 50 Gestionnaire de connexion de base de données » démarré (multi-utilisateur).
- Utilisateur Sage `mvogmbi_sync` avec « Accès par des tiers » et le même mot de passe dans chaque fichier d'entreprise.
- Fiches Sage : client « Vente Hebdomadaire » et fournisseurs avec « utilise mes numéros d'articles » ; chaque article a un compte de produits.
- Jeton Clover avec les droits de lecture, et d'écriture pour l'inventaire et les employés.
- Accès Internet pour Clover, les courriels et le téléchargement des formulaires T4 / RL-1.
- Session Windows ouverte la nuit (verrouillée possible).

---

## 8. Glossaire

| Terme | Sens |
|---|---|
| CUMP | Coût unitaire moyen pondéré du stock dans Sage |
| Correspondance | Lien entre un article Clover et un numéro d'article Sage |
| Assistant d'importation | Fonction de Sage « Fichier > Importer/Exporter > Importer des transactions », utilisée quand l'entreprise est partagée |
| BNC | Banque Nationale du Canada ; relevés lus comme ceux de Desjardins |
| Bon de réception / bon de livraison | Document sans prix : réception d'un achat / livraison d'une vente |
| Dépôt (stock) | Emplacement d'inventaire Sage : d'un point de vente, par défaut, ou sans Clover |
| Dépôt (banque) | Versement Clover sur le compte Desjardins |
| Entreprise partagée | Fichier Sage ouvert par plusieurs postes ; l'outil d'import le refuse |
| Facteur | Nombre d'unités Sage dans une unité du fournisseur |
| FRC / FRT | Facture de retour client / fournisseur (quantités et montants négatifs) |
| Lot Clover | Paiements par carte fermés chaque soir et déposés ensemble |
| Mono / multi-utilisateur | Ouverture exclusive de l'entreprise Sage (import), ou partagée (saisies) |
| Non-recette | Article Clover qui n'est pas compté comme une vente (non facturé) |
| serveur.json | Fichier du client des postes : nom tapé (app.marchemvogmbi.com) -> adresse du serveur |
| Tailscale | Réseau privé chiffré entre le serveur, les postes et les téléphones |
| RIA | Service de transfert d'argent dont le marché est agent ; « MT Send » = envoi, « MT Payout » = versement |
| UGS | Code d'article Clover (SKU) ; sert à noter la date de péremption |
