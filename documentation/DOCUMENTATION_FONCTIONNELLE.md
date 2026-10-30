# MVOGMBI_Sync — Documentation fonctionnelle

Version 1.0.0 (30 octobre 2026) — Marché MVOG-MBI Sherbrooke. Éditeur : Concept Informatique inc.

Ce document décrit **ce que fait** l'application et **selon quelles règles**, pour le propriétaire, le comptable et les personnes qui l'utilisent. Le fonctionnement interne est dans le document d'architecture ; le mode d'emploi pas à pas est dans le manuel d'utilisation.

---

## 1. Objet et périmètre

Le marché encaisse ses ventes avec **Clover** (caisse et terminal de paiement) et tient sa comptabilité dans **Sage 50 Comptabilité Édition canadienne**. Les deux ne communiquent pas. MVOGMBI_Sync fait le lien, sans ressaisie :

| Besoin | Réponse de l'application |
|---|---|
| Passer les ventes de la caisse en comptabilité | Une facture de vente par jour (une seule pour la fin de semaine), une ligne par article, importée la nuit |
| Encaisser les dépôts bancaires | Dépôts Clover, virements Interac et dépôts d'espèces appliqués sur les factures |
| Traiter les factures des fournisseurs | Lecture des PDF (courriel ou dossier), correspondance des articles, import dans Sage, mise à jour du stock Clover |
| Payer les fournisseurs | Avis de virement Interac lus et rapprochés des factures, paiement saisi dans Sage |
| Contrôler la banque | Relevés Desjardins rapprochés du compte de dépôt de Sage |
| Piloter le commerce | Statistiques comme Clover, bénéfices au coût moyen Sage, prévisions, articles 20/80, péremption |
| Gérer comme dans Sage | Listes, fiches et documents de vente, d'achat et de stock, créations dans Sage et dans Clover |
| Tenir la paie | Pointage par NIP, planning, feuilles de temps, chèques de paie dans Sage, bulletins par courriel |
| Contrôler l'accès | Comptes, profils et droits fonction par fonction |

Hors périmètre : la comptabilité générale elle-même (Sage reste la référence), la banque en ligne (relevés chargés à la main), le calcul des retenues de paie (fait par Sage Paie).

---

## 2. Acteurs et profils

| Acteur | Rôle | Profil de départ |
|---|---|---|
| Propriétaire / gérant | Configure, valide la correspondance, approuve, consulte tout | Administrateur |
| Comptable | Factures fournisseurs, paiements, rapprochement, comptabilité, paie | Comptable |
| Employé de caisse | Facturation des ventes, pointage, son horaire | Employé |
| Traitement de nuit | Tâche planifiée Windows, sans connexion | — |

Règles d'accès :

- L'**Administrateur** a toujours tout et gère les utilisateurs ; il en reste toujours au moins un actif.
- Chaque profil reçoit ses **fonctions une à une** (arbre du menu) : cocher « Liste des articles » donne cette liste seulement, pas toute la rubrique Articles.
- Des **actions dans les fenêtres** se retirent à part (traiter la paie, restaurer une sauvegarde, saisir les dépenses…), ainsi que **« Supprimer des éléments »** et **« Exporter les données »**.
- Un profil peut être limité à certains **points de vente**.
- Mot de passe d'au moins 6 caractères, jamais gardé en clair ; écran verrouillé après 5 minutes sans activité.

---

## 3. Fonctions par rubrique du menu

### 3.1 Accueil

- « Mise en route » en 10 étapes, chacune cochée quand elle est faite.
- Résumé de la journée, courbe d'évolution des ventes, alertes.

### 3.2 Administration

| Fonction | Ce qu'elle fait |
|---|---|
| Clover | Identifiant marchand, jeton d'accès (gardé dans le coffre-fort Windows), points de vente |
| Sage 50 | Fichier de l'entreprise, utilisateur de lecture, client des ventes, dépôts |
| Courriel | Envoi du compte rendu, boîte des avis de paiement et des factures |
| Automatisation | Heure du traitement de nuit, date de départ, encaissements automatiques, « Lancer maintenant » |
| Sauvegarde des données | Archive chaque nuit, conservation 14 jours / 8 semaines / 12 mois, restauration |
| Journal des opérations | Qui a fait quoi, filtres par date, source et texte |
| Tableau du gérant | Page pour téléphone mise à jour chaque nuit |
| Utilisateurs | Comptes, profils, fonctions permises, droits |

### 3.3 Articles

| Fonction | Règles principales |
|---|---|
| Liste des articles / Articles Clover | Caractéristiques Clover et Sage côte à côte ; comptes, coût moyen (CUMP), stock |
| Créer un article | **Stock** : créé dans Clover et dans Sage en une fois, prix de vente proposé = coût + 40 %, date de péremption obligatoire dans l'UGS. **Service** : créé dans **Sage seulement**, jamais dans Clover ; n° « S… », compte de charges obligatoire, compte de produits facultatif |
| Documents de stock | Entrée ou sortie, **toujours depuis un dépôt** rattaché à un point de vente |
| Transferts entre magasins | Sage d'abord (transfert entre emplacements), puis stocks Clover des deux points de vente |
| Pertes et démarque | Motif obligatoire (périmé, abîmé, vol…), coût au CUMP, sortie de stock Sage puis Clover, taux de perte |
| Étiquettes de prix | Feuilles Avery 5160 avec code-barres Code 128, prix au poids |
| Promotions | Prix promotionnel appliqué le 1er jour, prix normal remis après — jamais par-dessus un prix changé entre-temps |
| Inventaire / inventaire tournant | Fichier à remplir, quantités comptées saisies dans Clover et dans Sage ; catégories réparties sur 8 semaines |
| Correspondance | Lien article Clover → numéro Sage ; « Confirmé » par le propriétaire ; **deux formats différents = deux articles différents** |
| Coûts Clover depuis Sage / Prix et marges | Coût Clover = CUMP Sage ; prix proposé selon la marge minimale ; valeurs aberrantes jamais appliquées |

### 3.4 Vente

| Fonction | Règles principales |
|---|---|
| Ventes Clover → factures Sage | Voir 4.1 |
| Clients, documents de vente | Listes et fiches lues dans Sage ; création de clients dans Sage |
| Factures de vente, commandes clients | Saisies dans l'application, importées dans Sage ; une commande devient une facture |
| Clients professionnels et relances | Factures échues, lettre de relance envoyée au seul client |

### 3.5 Fournisseur

| Fonction | Règles principales |
|---|---|
| Factures fournisseurs | Lues dans les PDF (texte ou OCR Windows), totaux contrôlés ; Qté Sage = Qté × Facteur ; Prix Sage = Montant / Qté Sage ; n° de facture obligatoire ; doublons refusés |
| Bons de commande | Proposés d'après les ventes et le stock (couvrir 7 à 28 jours), un bon par fournisseur, comparés à la facture reçue |
| Retours fournisseurs | Facture d'achat négative importée, stock Clover diminué |
| Factures archivées | PDF, détail et Excel classés par année |

### 3.6 Comptabilité

| Fonction | Règles principales |
|---|---|
| Encaissements | Voir 4.2 |
| Paiements fournisseurs | Avis Interac rapprochés, confirmés par le propriétaire, saisis dans Sage ; jamais plus que le solde dû |
| Rapprochement bancaire | Relevé Desjardins comparé au compte 1055 ; écart expliqué ligne par ligne |
| Contrôle de la caisse | Espèces attendues (fond + ventes en espèces − remboursements − remises) contre comptage par coupures ; alerte au-delà de 5 $ |
| Petite caisse et dépenses | Dépense avec reçu, TPS / TVQ séparées dans les bons comptes, écriture dans Sage |
| Âge des comptes, déclaration TPS/TVQ, prévision de trésorerie, budget, clôture du mois | Lus dans Sage, comparés aux taxes Clover et au budget |

### 3.7 Paie

| Fonction | Règles principales |
|---|---|
| Pointage | Au magasin, par NIP de 4 à 6 chiffres ; arrivée, pause, départ ; 5 erreurs = blocage d'une minute |
| Planning mensuel / Mon horaire | Quarts par employé ; chacun voit son horaire publié |
| Feuilles de temps | Présence − pauses ; heures supplémentaires au-delà de 40 h par semaine ; une feuille changée revient « À approuver » |
| Employés | Créés dans Clover et dans Sage Paie, courriel obligatoire pour le bulletin ; le NAS n'est jamais gardé |
| Jours fériés et congés | Normes du travail du Québec : indemnité = 1/20 des 4 semaines précédentes, vacances 4 % / 6 % |
| Traitement de la paie | Heures **approuvées** de l'application → chèques de paie dans Sage ; bulletins imprimés ou envoyés, un destinataire par bulletin |
| Retenues et remises | Montants à remettre par organisme, échéance le 15 du mois suivant, alerte de retard |
| Fin d'emploi, concordance T4 / RL-1, coût de la main-d'œuvre | Préparés d'après les paies de Sage et les heures pointées |

### 3.8 État

Suivi des ventes facture par facture, recherche dans l'historique Sage (client, fournisseur, article, catégorie), statistiques comme Clover (aperçu, rapports, finances, articles, employés, clients, prévisions), produits inactifs, articles 20/80.

Section **« Gestion »** des statistiques : un rapport par fonction de gestion (pertes et démarque, contrôle de la caisse, petite caisse et dépenses, main-d'œuvre, promotions, retours fournisseurs, bons de commande). Pour la période choisie, chacun présente des **cartes d'indicateurs**, un **graphique d'évolution** (par jour jusqu'à 62 jours, sinon par mois), une **carte graphique de répartition** (par motif, compte, employé, fournisseur ou état) et le **rapport détaillé** exportable. Chaque tableau s'exporte (si le profil le permet) en Excel, CSV, PDF ou s'imprime avec l'en-tête de l'entreprise.

---

## 4. Règles de gestion principales

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
4. Un dépôt n'est jamais saisi deux fois ; le solde dû de la facture est vérifié après chaque saisie.

### 4.3 Sage

- **Import** (factures de vente et d'achat) : Sage fermé, **mono-utilisateur**.
- **Saisies** (encaissements, paiements, journal, stock, fiches, paie) : **multi-utilisateur**, la personne peut garder Sage ouvert.
- Tout essai se fait d'abord sur une **copie** du fichier d'entreprise.
- L'application ne modifie jamais les paramètres de Sage.

### 4.4 Données et confidentialité

- Secrets (jeton Clover, mots de passe Sage et courriel) dans le coffre-fort de Windows uniquement.
- Aucune intelligence artificielle ni service externe pour lire les factures : OCR intégré à Windows.
- Données du marché dans le dossier `donnees/`, sauvegardé chaque nuit ; jamais publiées.

---

## 5. Traitement de nuit

Chaque nuit, sans intervention :

1. Ventes Clover lues pour chaque jour sans facture, du plus ancien au plus récent.
2. Factures préparées, contrôlées, importées dans Sage par lots.
3. Dépôts des ventes importées encaissés.
4. Paiements fournisseurs confirmés saisis.
5. Factures fournisseurs reçues par courriel copiées et lues.
6. Promotions appliquées, statistiques préchauffées, tableau du gérant écrit.
7. Données sauvegardées.
8. Compte rendu par courriel : résumé du matin (ventes, marge, solde, factures à payer, ruptures, péremption, alertes) et une pièce jointe Excel par module.

---

## 6. Données gérées

| Donnée | Source de vérité | Gardée dans l'application |
|---|---|---|
| Ventes, articles, stocks Clover, employés | Clover | caches par jour, catalogue |
| Factures, encaissements, comptes, articles et stocks Sage | Sage | lectures gardées quelques minutes |
| Correspondance Clover → Sage | Application (validée par le propriétaire) | `correspondance_articles.xlsx` |
| Factures fournisseurs lues, bons de commande, documents | Application, puis Sage | registres JSON, PDF |
| Pointages, feuilles de temps, planning, congés | Application | registres JSON (jamais effacés) |
| Comptes et droits | Application | `utilisateurs.json` (empreintes) |

---

## 7. Contraintes et prérequis

- Windows 10 ou 11, Sage 50 CA 2026 installé, Microsoft Edge (PDF).
- Service « Sage 50 Gestionnaire de connexion de base de données » démarré (multi-utilisateur).
- Utilisateur Sage `mvogmbi_sync` avec « Accès par des tiers » et le même mot de passe dans chaque fichier d'entreprise.
- Fiches Sage : client « Vente Hebdomadaire » et fournisseurs avec « utilise mes numéros d'articles » ; chaque article a un compte de produits.
- Jeton Clover avec les droits de lecture, et d'écriture pour l'inventaire et les employés.
- Session Windows ouverte la nuit (verrouillée possible).

---

## 8. Glossaire

| Terme | Sens |
|---|---|
| CUMP | Coût unitaire moyen pondéré du stock dans Sage |
| Correspondance | Lien entre un article Clover et un numéro d'article Sage |
| Dépôt (stock) | Emplacement d'inventaire Sage rattaché à un point de vente |
| Dépôt (banque) | Versement Clover sur le compte Desjardins 1055 |
| Facteur | Nombre d'unités Sage dans une unité du fournisseur |
| Lot Clover | Paiements par carte fermés chaque soir et déposés ensemble |
| Mono / multi-utilisateur | Ouverture exclusive de l'entreprise Sage (import), ou partagée (saisies) |
| Non-recette | Article Clover qui n'est pas compté comme une vente (non facturé) |
| UGS | Code d'article Clover (SKU) ; sert à noter la date de péremption |
