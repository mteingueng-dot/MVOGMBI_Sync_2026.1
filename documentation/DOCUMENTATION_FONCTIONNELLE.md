# MVOGMBI_Sync — Documentation fonctionnelle

Version 1.0.20 (7 novembre 2026) — Marché MVOG-MBI Sherbrooke. Éditeur : Concept Informatique inc.

Ce document décrit **ce que fait** l'application, **écran par écran**, et **selon quelles règles**, pour le propriétaire, le comptable et les personnes qui l'utilisent. Il entre dans le détail : champs, états, contrôles, cas particuliers, messages. Le détail de chaque règle, avec son code (RG-…), est dans le document des **règles d'affaires** ; le fonctionnement interne est dans le document d'**architecture** ; le mode d'emploi pas à pas, avec captures, est dans le **manuel d'utilisation** ; l'installation, la configuration et le dépannage sont dans le **guide de l'administrateur**.

---

## 1. Objet et périmètre

Le marché encaisse ses ventes avec **Clover** (caisse et terminal de paiement) et tient sa comptabilité dans **Sage 50 Comptabilité Édition canadienne**. Les deux ne communiquent pas : sans l'application, chaque vente, chaque dépôt, chaque facture de fournisseur devrait être ressaisi à la main. MVOGMBI_Sync fait le lien, sans ressaisie, et ajoute la gestion qui manque aux deux logiciels.

| Besoin | Réponse de l'application |
|---|---|
| Passer les ventes de la caisse en comptabilité | Une facture de vente par jour du lundi au jeudi, une seule pour la fin de semaine, une ligne par article Sage, importée la nuit et vérifiée dans Sage |
| Encaisser les dépôts bancaires | Lots de cartes Clover, virements Interac et dépôts d'espèces appliqués sur les factures, dans la fenêtre Encaissements de Sage |
| Traiter les factures des fournisseurs | Lecture des PDF (courriel, dossier, ou photos prises au téléphone), correspondance des articles, import dans Sage (aussi la nuit), mise à jour du stock et du coût dans Clover |
| Payer les fournisseurs | Avis de virement Interac lus dans la boîte de courriel, rapprochés des factures, confirmés par le propriétaire, saisis dans Sage |
| Contrôler la banque | Relevés Desjardins et Banque Nationale (BNC) rapprochés du compte Sage de chaque banque, écart expliqué ligne par ligne |
| Travailler sur plusieurs sites | Dépôts (emplacements d'inventaire de Sage), avec ou sans Clover : factures, stock, employés, planning et états par dépôt |
| Tenir l'agence RIA | États de compte RIA lus, envois et versements passés dans Sage, commissions reconnues |
| Piloter le commerce | Statistiques comme Clover, bénéfices au coût moyen Sage, prévisions, articles 20/80, produits inactifs, péremption, rapports de gestion |
| Gérer comme dans Sage | Listes, fiches, chaîne des documents de vente et d'achat, documents de stock, plan comptable ; créations, modifications et suppressions dans Sage et dans Clover |
| Tenir la paie | Pointage par NIP, planning, feuilles de temps, chèques de paie dans Sage, bulletins, jours fériés et congés, T4 et RL-1 officiels |
| Contrôler l'accès | Comptes, profils, droits fonction par fonction, verrouillage, audit des actions |
| Travailler à distance | Application web identique à l'application Windows (76 entrées du menu), sur PC, tablette et téléphone, par Tailscale ; client des postes ; Bureau à distance pour l'application complète |

**Hors périmètre** : la comptabilité générale elle-même (Sage reste la référence et le seul livre officiel), la banque en ligne (les relevés sont chargés à la main en PDF), le calcul des retenues de paie (fait par Sage Paie), la caisse elle-même (Clover). L'application ne modifie **jamais les paramètres** de Sage ni de Clover ; elle n'écrit que des transactions et des fiches, comme une personne le ferait.

### 1.1 Les trois façons d'utiliser l'application

| Forme | Pour qui | Particularités |
|---|---|---|
| Application Windows | Propriétaire et comptable, sur le serveur (session ouverte ou Bureau à distance) | Toutes les fonctions ; ouvre Sage pour la journée ; seule à pouvoir lancer les saisies quand le traitement de nuit est absent |
| Application web | Tout le monde, depuis un PC, une tablette ou un téléphone relié par Tailscale | Mêmes menus, mêmes écrans, mêmes droits ; aucun script dans la page (sécurité) ; travaux longs suivis sur une page qui se rafraîchit |
| Traitement de nuit | Tâche planifiée Windows du serveur | Sans connexion ni fenêtre ; enchaîne factures, encaissements, paiements, sauvegarde, compte rendu |

Le **client des postes** (`MVOGMBI_Sync_Client.exe`) ouvre directement l'application web dans une fenêtre Edge sans barre d'adresse ; il propose aussi l'application complète par Bureau à distance (deux personnes à la fois au plus sur le serveur, sans licences RDS).

---

## 2. Acteurs, profils et sécurité

### 2.1 Acteurs

| Acteur | Rôle | Profil de départ |
|---|---|---|
| Propriétaire | Configure, valide la correspondance, confirme les paiements, approuve, consulte tout | Administrateur |
| Gérant | Planning, feuilles de temps, voit tous les employés, caisse, pertes | Gérant |
| Comptable | Factures fournisseurs, paiements, rapprochement, comptabilité, RIA, paie | Comptable |
| Employé de caisse | Pointage, son horaire, ses heures et ses paies, tableau de bord | Employé |
| Traitement de nuit | Tâche planifiée Windows, sans connexion | — |

### 2.2 Profils et droits

- L'**Administrateur** a toujours tout, y compris la page « Utilisateurs » ; ce profil ne se modifie pas. Il reste toujours au moins un administrateur actif : le dernier ne peut être ni désactivé, ni supprimé, ni rétrogradé.
- Chaque profil reçoit ses **fonctions une à une** dans un arbre qui reprend le menu : cocher une rubrique coche toutes ses fonctions (☑), en décocher une partie la montre à moitié cochée (◩). Cocher « Liste des articles » donne cette liste seulement, pas toute la rubrique Articles.
- Des **actions dans les fenêtres** se retirent à part : traiter la paie, restaurer une sauvegarde, saisir les dépenses, modifier les articles dans Sage et Clover, modifier le plan comptable, changer les prix de vente dans Sage, lancer le traitement maintenant…
- Quatre **droits** généraux : « Exporter les données » (Excel, CSV, PDF, impression), « Supprimer des éléments » (tout bouton 🗑 ou « Supprimer », et la touche Suppr des listes), « Lancer maintenant », « Voir tous les employés ».
- Un profil peut être limité à certains **points de vente** : listes, statistiques et filtres n'en montrent alors que ceux-là.
- Un **login limité** (Employé) ne voit que **ses** heures, paies, bulletins, feuillets et statistiques ; le filtre Employé des statistiques est verrouillé sur lui.
- Les mêmes comptes, profils et droits servent dans l'application Windows et dans l'application web ; une page non permise est **absente du menu** et refusée si on y va par son adresse.

### 2.3 Mots de passe, verrouillage et sessions

| Règle | Application Windows | Application web |
|---|---|---|
| Mot de passe | 6 caractères au moins ; empreinte PBKDF2-SHA256 salée, jamais le mot de passe | Mot de passe **à part**, 12 caractères au moins avec minuscule, majuscule, chiffre et caractère spécial, différent du mot de passe Windows |
| Première connexion | Premier lancement = création du compte administrateur | Connexion avec le mot de passe Windows, puis création obligatoire du mot de passe web (toute page renvoie à « Créer mon mot de passe web ») |
| Erreurs | 3 mots de passe faux de suite = compte verrouillé ; l'administrateur le rouvre en donnant un nouveau mot de passe ; le dernier administrateur actif n'est que bloqué 15 minutes | 10 échecs en 10 minutes par adresse = refus temporaire |
| Inactivité | Après 5 minutes sans souris ni clavier, fenêtres cachées et écran de verrouillage ; les traitements en cours **continuent** ; au déverrouillage on revient exactement où l'on était, fenêtres à part comprises | Après 5 minutes sans activité, la page passe d'elle-même à la connexion ; après la reconnexion, retour à **la même page** ; un travail en cours se retrouve |
| Désactivation | Un compte se désactive sans être supprimé ; une fenêtre ouverte sur ce compte se verrouille au contrôle suivant (10 s) | Sessions du compte fermées |

### 2.4 Audit

Chaque action est notée dans un journal d'audit qu'on ne réécrit jamais : moment, poste, utilisateur, fenêtre, action, détail. Sont notés : chaque bouton cliqué, chaque entrée du menu, chaque connexion, refus et verrouillage, chaque export, l'ouverture de l'application. Chaque ligne porte l'empreinte de la précédente : une ligne modifiée ou retirée est repérée par « Vérifier » (page « Administration > Audit des actions »). Jamais de mot de passe ni de NAS dans l'audit.

---

## 3. Fonctions par rubrique du menu

Le menu de gauche est rangé en rubriques ; une seule rubrique est ouverte à la fois (celle de la page affichée). « Guide de configuration », « Aide / FAQ » et « Manuel d'utilisation (PDF) » sont en bas, hors des rubriques ; le manuel ouvert est celui **du profil** (chapitres non permis retirés).

### 3.1 Accueil

- **Mise en route** en 10 étapes, une par page de configuration ; chaque étape est cochée ✔ (vert) quand elle est faite, ● (jaune) sinon, avec un bouton « Ouvrir ». Compteur « n étape(s) sur 10 ». Exemples de contrôle : étape 7 = un dépôt encaissé au journal, 8 = une facture « Importée dans Sage », 9 = boîte des avis et mot de passe, 10 = un relevé chargé.
- **Bienvenue** : présentation de l'application, logo du marché en filigrane qui ne défile pas.

### 3.2 Administration

#### Clover

| Champ | Règle |
|---|---|
| Identifiant marchand | 13 lettres ou chiffres, obligatoire |
| Jeton d'accès | Gardé dans le coffre-fort de Windows, jamais réaffiché ; obligatoire seulement s'il n'y est pas déjà |
| Points de vente | Liste : n° 1 = le magasin principal (section Clover), autres = code, nom, identifiant marchand, client Sage, dépôt Sage, préfixe des factures (5 caractères au plus), actif ; chacun avec son propre jeton ; « 🔌 Tester ce point de vente » |

Droits du jeton Clover nécessaires : lecture partout ; écriture « Inventaire » (stock, coûts, prix, création d'articles) et « Employés » (création d'employés). Un jeton sans écriture donne « 401 » à la première écriture.

#### Sage 50

- Fichier de l'entreprise (`.SAI`, bouton « Parcourir… »), utilisateur de lecture `mvogmbi_sync` (mot de passe dans le coffre-fort), client des ventes (« Vente Hebdomadaire »), « 📒 Tester l'accès à Sage ».
- **Dépôts sans Clover** (« Entrepôt; Réserve ») : emplacements Sage qui reçoivent des factures sans point de vente.
- Carte **Paie** : première paie de l'année et délai de paiement (15 jours) ; donnent toutes les périodes de 14 jours.
- Carte **Comptes bancaires (rapprochement)** : Desjardins (compte de dépôt 1055) et BNC (1060) d'office, puis autres comptes (code, nom, format du relevé « desjardins » ou « bnc », compte Sage, n° de compte, actif) ; « Ajouter un compte bancaire… », « Retirer le compte choisi ».

#### Courriel

| Carte | Contenu |
|---|---|
| 1. Envoi | Serveur SMTP, port (465 = SSL, 587 = STARTTLS), adresse d'envoi, mot de passe (coffre-fort), destinataires du compte rendu |
| 2. Essai | Envoi d'un courriel d'essai à l'adresse choisie ; copie cachée (Cci) de chaque courriel personnel |
| 3. Boîte des avis de paiement | Serveur IMAP, adresse, mot de passe, date de départ ; lue en **lecture seule** (les messages restent non lus) |
| 4. Factures reçues par courriel | Expéditeurs, textes à chercher (« ; » entre les textes), date de départ, import la nuit |
| 5. États RIA | Boîte, expéditeurs, date de départ |

#### Automatisation

- Heure du traitement de nuit, **date de départ** (aucun jour antérieur n'est facturé), encaissements automatiques, factures par lot (25), « Installer », « Retirer », « État » de la tâche planifiée, « ▶ Lancer maintenant » (droit à part).
- Carte **Serveur de l'application** : ordinateur, adresse Tailscale, adresse locale, nom tapé dans le client (`app.marchemvogmbi.com`), port (443 = HTTPS sans port), certificat et clé, « Fichier du client (serveur.json) ».
- Carte **Wi-Fi du magasin (pointage)** : nom du Wi-Fi, adresses publiques du magasin, postes de pointage, minutes hors Wi-Fi avant la pause automatique (5). La page web montre le réseau de l'appareil qui l'ouvre, pour relever l'adresse depuis le magasin.
- « Créer un raccourci sur le Bureau », « Reprendre une configuration existante… ».

#### Autres pages d'administration

| Fonction | Ce qu'elle fait |
|---|---|
| Sauvegarde des données | Archive `.zip` du dossier des données et de la configuration, chaque nuit et à la demande ; vérifiée après écriture ; conservation : la dernière de chacun des 14 derniers jours, des 8 dernières semaines et des 12 derniers mois ; restauration après une sauvegarde de l'état actuel ; alerte si la dernière a plus de 2 jours |
| Journal des opérations | Tous les journaux et registres de l'application réunis : filtres par date, source, texte |
| Audit des actions | Voir 2.4 |
| Tableau du gérant | Page pour téléphone (résumé du matin + problèmes), écrite chaque nuit ; « Mettre à jour maintenant » |
| Utilisateurs | Comptes (ajouter, profil, nouveau mot de passe, mot de passe web défini / à créer, activer / désactiver, supprimer, déverrouiller), profils (arbre des fonctions, actions, droits, points de vente permis) |

### 3.3 Articles

#### Liste des articles (Sage)

Colonnes : n° Sage, description, comptes d'actif, de produits et de charges (CMV), CUMP, stock, valeur, prix de vente régulier, articles Clover reliés. Filtre **Dépôt** : stock et valeur des seuls dépôts choisis. Double-clic = **fiche** (prix, stock par emplacement, derniers mouvements).

- **Modifier** : description et case « Article inactif » écrites dans la fiche Sage ; l'article Clover relié peut être renommé en même temps.
- **Supprimer** : de Sage d'abord ; si Sage refuse (« encore des quantités en stock »), l'article est rendu **inactif** et l'article Clover est gardé ; Clover n'est supprimé que si Sage a supprimé.

#### Articles Clover

Catalogue complet : ID Clover, nom, prix, type de prix (fixe, variable, au poids), unité, code produit, **date de péremption** (lue dans l'UGS), quantité, catégories. Recherche, filtres catégorie / type de prix / stock, tri par colonne, stock négatif en rouge. « Effacer les UGS qui ne sont pas des dates… » : liste à cocher, puis UGS vidée dans Clover, journal des UGS effacées.

#### Créer un article

| Type | Où | Règles |
|---|---|---|
| Stock | Clover **et** Sage, en une fois | Prix de vente proposé = coût d'achat + 40 % ; type de prix ; taxes (défaut Clover, TPS + TVQ, une seule, aucune) ; catégorie ; **date de péremption obligatoire** (JJ/MM/AAAA) dans l'UGS ; stock de départ ; n° Sage = préfixe de la catégorie + n° libre suivant (ex. « C0001161 ») ; comptes d'actif, de produits, de CMV et d'écart tirés de la table « Comptes Sage par catégorie » (écart vide = CMV) |
| Service | **Sage seulement**, jamais Clover | N° commençant par « S » ; compte de charges obligatoire, compte de produits facultatif ; la case « Créer dans Clover » est décochée et grisée |

L'article créé est relié « Confirmé » dans la correspondance et noté au journal des articles créés. « Comptes par catégorie… » ouvre la table pour choisir une catégorie : ses comptes doivent être complets.

#### Correspondance Clover → Sage

Chaque article Clover vendu doit être relié à un n° d'article Sage. L'application propose ; le propriétaire décide.

| Méthode de proposition | Règle |
|---|---|
| Code-barres | Même code dans les deux |
| Nom identique | Après normalisation (majuscules, accents, espaces) |
| Ressemblance | Score de ressemblance, pénalisé si les formats chiffrés diffèrent |
| Supprimé ou renommé dans Clover | Ancien article vendu absent du catalogue : l'article Clover actuel le plus ressemblant, au même format, et son n° Sage, « À confirmer » |

États : Confirmé (par le propriétaire), Automatique (sûr), À confirmer, À créer dans Sage, Non relié. **Deux formats différents = deux articles différents** (« 1kg » / « 500g », « 6-36 » / « 7-36 ») : jamais proposé ; mais une liaison confirmée par le propriétaire malgré l'écart (« Confirmer quand même ? ») est valide et n'est jamais annulée. Une liaison confirmée est gardée à chaque mise à jour (clé : ID Clover). Filtres : à confirmer, non reliés, plusieurs formats sur un article Sage, supprimés ou renommés dans Clover. Chaque décision est enregistrée tout de suite ; copie de sécurité une fois par heure.

#### Comptes Sage par catégorie

Table catégorie Clover → préfixe de n° et comptes Sage (actif 15xx, produits 40xx, CMV 50xx, écart). Règle du propriétaire : **15xx (actif) → 40xx (produits) / 50xx (CMV)**. « Proposer depuis Sage » : comptes les plus fréquents des articles reliés. « Articles Sage à corriger… » : articles dont un compte diffère de la table (catégorie de l'article = celle qui s'accorde avec le plus de ses comptes, + 1 point pour la catégorie Clover ; égalité = non proposé), cochés puis corrigés dans la fiche Sage. Un compte saisi est contrôlé dans le plan comptable (absent, inactif, en-tête ou total = refusé).

#### Coûts, prix et marges

| Fonction | Règles |
|---|---|
| Coûts Clover depuis Sage | Coût Clover = CUMP Sage pour les lignes cochées. Jamais de valeur aberrante : CUMP absent, plus de 5 fois le prix, moins de 5 % du prix = non cochable. À vérifier (décoché) : CUMP supérieur ou égal au prix, plus de 3 fois d'écart avec le coût Clover, n° Sage relié à plusieurs articles Clover |
| Prix et marges | Coût = CUMP Sage, sinon coût Clover ; marge minimale (15 à 50 %, 25 par défaut) ; prix proposé = coût / (1 − marge) arrondi vers le haut (,49 / ,99, ,99 ou au cent) ; états : sous la marge minimale (coché), à vérifier (hausse de plus de 30 %, plusieurs articles, aucun prix), coût aberrant, coût inconnu, prix variable ; effet estimé = (nouveau prix − prix) × quantité vendue en 90 jours |
| Prix de vente Sage depuis Clover | Prix « Régulier » de Sage remplacé par le prix Clover des articles reliés Confirmé / Automatique ; états : Différent (coché), Identique, Plusieurs prix Clover (le plus élevé proposé, décoché), Prix variable, Sans prix Clover, Absent de Sage ; vérifié dans Sage ; journal des prix changés |

#### Étiquettes et promotions

- **Étiquettes de prix** : nom, prix (« / lb » pour un prix au poids), code-barres Code 128 ; feuilles Avery 5160 / 8160 (3 × 10) ou imprimante à tickets (une étiquette par ticket) ; articles choisis ou dont le prix a changé depuis une date.
- **Promotions** (« PR-0001 ») : article, prix promotionnel, du / au, point de vente ; deux promotions qui se chevauchent sont refusées. Le 1er jour, le prix normal est lu dans Clover puis le prix promo appliqué ; après le dernier jour, le prix normal est remis **seulement si** le prix est encore le prix promo (un prix changé entre-temps n'est jamais écrasé). Une promotion en cours peut être **annulée**. Effet = ventes pendant la promotion contre la même durée juste avant.

### 3.4 Stock

| Fonction | Règles principales |
|---|---|
| Documents de stock | Entrée, sortie, ajustement, **toujours depuis un dépôt** ; passés dans Sage (fenêtre « Ajustements des Stocks & Transferts ») puis dans Clover ; un document passé ne se modifie pas : il s'**annule par son inverse** (passé dans Sage et Clover, original « Annulé ») ; colonne et filtre Dépôt (« départ → arrivée » pour un transfert) ; imprimés « Mouvement d'entrée » / « Mouvement de sortie » (coût unitaire, valeur, CUMP, motif, signatures) |
| Transferts entre magasins (« TR-0001 ») | Deux points de vente différents, deux dépôts différents, quantités positives ; Sage d'abord (transfert entre emplacements, lots de 7 lignes « TR-0001 », « TR-0001-2 », jamais refaits), puis stocks Clover (départ − quantité, arrivée + quantité) ; états Brouillon / Fait dans Sage / À compléter / Terminé ; jeton absent = « À compléter », jamais bloquant ; Sage accepte un stock négatif au départ (avertissement jaune) ; « Bon de transfert » imprimé avec quantité reçue et signatures à remplir |
| Pertes et démarque (« PE-0001 ») | Motif obligatoire (périmé, abîmé, vol, don, consommation interne, erreur de réception, autre), dépôt, lignes du catalogue Clover ; coût = CUMP Sage, sinon coût Clover, sinon inconnu (valeur 0, signalé) ; sortie de stock Sage (document « DS ») puis stock Clover diminué ligne par ligne, jamais deux fois ; « Ajouter les produits périmés en stock » ; une perte s'ouvre, se modifie (annulation + reprise) ou s'annule ; rapport par motif, catégorie, article, mois ; taux = pertes au coût / ventes nettes |
| Inventaire | 1. Exporter : une ligne par article relié, puis Clover seul, puis Sage seul ; quantités Clover et Sage, écart, CUMP, colonne jaune « Quantité comptée ». 2. Compter. 3. Saisir : stocks relus juste avant ; Clover = quantité comptée de la ligne, Sage = somme des lignes de son n° ; entrée en stock au CUMP ; rapport avant / après et « Écart d'inventaire » imprimé (théorique, compté, écart, valeur, plus / moins / net, signatures) |
| Inventaire tournant | Catégories Clover réparties sur 8 semaines (ordre alphabétique) ; la feuille de la semaine ne contient que ses catégories, saisie ensuite comme un inventaire |
| Livre d'inventaire | Stock et valeur à une date passée = stock actuel − mouvements postérieurs (transferts compris), au CUMP actuel, totaux par catégorie, filtre Dépôt |

### 3.5 Vente

#### Ventes Clover → factures Sage (Tableau de bord)

- Point de vente, date ou période, « Charger la période » : chaque jour sans facture est préparé ; les jours déjà facturés sont sautés ; un samedi ou dimanche choisi remonte au vendredi ; une fin de semaine en partie facturée est bloquée (jamais de 2e facture partielle).
- Cartes à filet de couleur : ventes, factures, à vérifier ; sortie du traitement en couleur ; « Détail (Excel) » de la facture.
- « 🧾 Corriger les comptes dans Sage… » : ouvre les articles sans compte (« Compte manquant (import bloqué) ») cochés et en premier.
- Règles de facturation : voir 4.1.

#### Clients, documents de vente, relances

| Fonction | Règles principales |
|---|---|
| Clients | Liste lue dans Sage (montant dû, factures ouvertes, dernière facture, facturé 12 mois), fiche ; « Ajouter » crée le client dans Sage (nom, contact, adresse, téléphones, courriel, site, compte de produits, « utilise mes n° d'articles ») |
| Documents de vente | Types comme Sage : devis (DV, valable 30 jours), commande (CC), préparation (PL), bon de livraison (BL, **sans prix**), retour client (RC), avoir (AV), facture (FV), facture de retour (FRC, quantités et montants négatifs), facture d'avoir (FAV). « Transformer » reprend lignes, client et dépôt, l'original passe « Transformé ». Seules les factures touchent le stock : importées dans Sage, puis stock Clover du point de vente du dépôt ; jamais deux fois |
| Commandes clients | Gardées dans l'application (la fonction Commandes clients n'est pas activée dans Sage) ; « Facturer la commande » crée la facture |
| Clients professionnels et relances | Factures ouvertes des clients autres que les ventes Clover ; échu, plus de 30 jours, dépassement de la limite de crédit en rose ; lettre de relance imprimée ou envoyée au **seul client** ; relances notées |

### 3.6 Fournisseur

#### Factures fournisseurs

Une page : liste à gauche (état en couleur, case à cocher), facture choisie au centre, ligne choisie en carte d'édition.

| Étape | Règles |
|---|---|
| Arrivée | PDF déposé, reçu par courriel (pièces jointes des expéditeurs ou des courriels qui contiennent les textes réglés, jamais Interac ; chaque fichier une seule fois, reconnu par son empreinte), ou **photographié au téléphone** (une photo par page, 15 au plus, un PDF à la fin) |
| Lecture | PDF numérique : un modèle par fournisseur ; PDF numérisé ou photo : OCR intégré à Windows (aucune IA, aucun service externe) ; contrôle des totaux |
| Contrôles | N° de facture obligatoire ; doublon refusé même avec un préfixe (« FA-104202 » = « 104202 ») ; facture déjà dans Sage = archivée « Déjà dans Sage » sans 2e import |
| Lignes | Code, désignation, taxes (GQ / G / Q / aucune), Qté, Prix fournisseur ; **Qté Sage = Qté × Facteur** ; **Montant = Qté × Prix fournisseur** ; **Prix Sage = Montant / Qté Sage** (Montant et Qté Sage calculés, non saisissables) ; article Sage cherché par ressemblance, « (autre format) » signalé ; « Relier et confirmer » mémorisé par fournisseur (article + facteur) |
| Dépôt | Liste « Dépôt » de l'en-tête : la facture s'importe dans l'emplacement par défaut puis un transfert la place dans son dépôt |
| Import | « Importer cette facture » (si « Prête à importer »), « ☑ Importer les factures cochées », « Importer toutes les factures prêtes » ; aussi la nuit ; vérifiée dans Sage ; puis stock Clover = stock + Qté Sage, coût Clover = montant / Qté Sage (articles reliés ; plusieurs articles Clover = coût seulement) ; compte rendu par courriel ; facture archivée |
| Impressions | « 🖨 Bon de réception » (sans prix, Qté Sage et Qté Clover ajoutée, observation, signature) et « 🖨 Facture (avec prix) » |
| Reprise | « 🔁 Refaire la mise à jour Clover » d'une facture « Importée » (lignes déjà ajoutées écartées) |

Les saisies s'**enregistrent d'elles-mêmes** 0,7 s après la dernière frappe, au changement de ligne, de facture ou de page. Le même registre sert à Windows et au web : une facture importée d'un côté est archivée de l'autre, **en temps réel** (liste relue toutes les 3 s).

États d'une facture : À saisir, À saisir (photo), À relier, Prête à importer, Importée, Déjà dans Sage, Écartée, Supprimée.

#### Documents d'achat, bons de commande, retours

| Fonction | Règles principales |
|---|---|
| Documents d'achat | Demande de prix (PC) → bon de commande (BC) → bon de réception (BR, **sans prix**) → facture (FA, n° du fournisseur obligatoire) ; retour (RT) → facture de retour (FRT) ; avoir (AVF), facture d'avoir (FAF) |
| Bons de commande (« BC-0001 ») | Proposés d'après les ventes et le stock : quantité = vendu sur N jours (« Couvrir » 7 à 28, 14 par défaut) − stock positif, arrondie à l'unité au-dessus, regroupée par n° Sage ; fournisseur et prix = dernier achat ; un bon par fournisseur **en unités du fournisseur** (quantité Sage / facteur, prix Sage × facteur) ; PDF ; comparés à la facture reçue (unités Sage, 2 % de tolérance) ; « Marquer reçu » |
| Retours fournisseurs (« R-<n° de facture> ») | Lignes reprises de la facture d'origine ; facture d'achat **négative** importée dans Sage, vérifiée ; stock Clover diminué ; jamais deux fois |
| Factures archivées | PDF, détail JSON et Excel classés par année ; « Voir la facture », « Détail (Excel) » |

Prérequis Sage : fiche fournisseur avec « utilise mes numéros d'articles » cochée.

### 3.7 Comptabilité

| Fonction | Règles principales |
|---|---|
| Encaissements | Voir 4.2 |
| Paiements fournisseurs | Voir 4.3 |
| Rapprochement bancaire | Voir 4.4 |
| Contrôle de la caisse | Espèces attendues = fond du matin (fond laissé au dernier comptage, sinon 200 $) + paiements en espèces réussis (montant + pourboire) − remboursements de ces paiements − retraits d'argent sur carte ; comptage du soir par coupures ; écart = compté − attendu, alerte au-delà de 5 $ ; à déposer = compté − fond laissé ; onglets Comptage du soir, Écarts par jour, Dépôts d'espèces (écart cumulé avec les dépôts au guichet du relevé) ; un comptage par point de vente |
| Petite caisse et dépenses (« DP-0001 ») | Date, fournisseur, montant TTC, code de taxe (TPS 5 %, TVQ 9,975 %, l'arrondi va à la TVQ), compte de charge, payé par petite caisse / carte de crédit / employé à rembourser, reçu joint ; écriture de journal dans Sage (crédit en 1re ligne), vérifiée, jamais deux fois ; comptes de taxe contrôlés (une TPS / TVQ mal reliée bloque la saisie) |
| Plan comptable | Comptes lus dans Sage (en-têtes et totaux en vert) ; Ajouter, Modifier (description, inactif), Supprimer, écrits dans Sage ; droit « Modifier le plan comptable » |
| Âge des comptes | Factures ouvertes clients et fournisseurs par tranche d'échéance (date + délai de la fiche) |
| Déclaration TPS / TVQ | Taxes perçues, payées, régularisations, d'après les comptes de Sage ; contrôle avec les taxes encaissées par Clover |
| Prévision de trésorerie | 4 semaines : solde, encaissements attendus, factures à payer |
| Budget et écarts | Budget mensuel (ventes, CMV, autres charges) contre réel ; « Proposer d'après l'an dernier » × croissance |
| Clôture du mois | Contrôles, puis état des résultats (produits 4xxx, CMV 50xx, charges 51xx-59xx) comparé au mois précédent et au même mois l'an dernier |

Les calculs de la comptabilité se font sur demande (« 🔍 Calculer », « 🔍 Vérifier ») : la zone reste vide et titrée avant.

### 3.8 RIA

| Fonction | Règles principales |
|---|---|
| Opérations RIA (« RI-0001 ») | Mouvements RIA des relevés, surplus de dépôts d'espèces, paiements en espèces, commissions, opérations venues des états ; 6 cartes de totaux ; « Saisir dans Sage » écrit les écritures de journal ; le compte RIA de bilan revient à zéro, seules les commissions sont un revenu |
| États de compte RIA | États importés à la main ou reçus par courriel (aussi la nuit) ; soldes, envois, versements, frais, commissions payées et courues ; solde recontrôlé ligne par ligne ; « 📒 Traiter dans Sage » crée les opérations (voir 4.5) |
| Comptes RIA | Comptes RIA, commissions, espèces ; chacun doit exister dans le plan comptable |

### 3.9 Paie

| Fonction | Règles principales |
|---|---|
| Pointage | Poste du magasin (plein écran, sans connexion) ou téléphone sur le Wi-Fi du magasin ; nom → NIP (4 à 6 chiffres, pavé ou clavier) → actions permises (arrivée, début / fin de pause, départ) ; « NIP à créer » si absent ; 5 NIP faux = blocage d'une minute ; retour à la liste après 12 s ; les chiffres du pavé restent sur le serveur, jamais dans la page |
| Pause hors Wi-Fi | Un téléphone qui a servi à pointer et quitte le Wi-Fi **5 minutes de suite** met l'employé en pause, à l'heure du départ ; son retour termine la pause ; une pause pointée par l'employé n'est jamais terminée par l'application ; le départ arrête le suivi |
| Planning mensuel | Quarts (début, fin, après minuit possible, pause non payée) par employé et par jour ; repos ; publier / non publié ; « Reprendre le mois précédent » ; « Horaire des employés choisis… » (lundi à vendredi, 08:00-16:00 par défaut) ; **une cédule par dépôt** (filtre Dépôt, quart ailleurs marqué « @dépôt ») |
| Mon horaire | Mois publiés seulement, cartes et tableau par semaine ; aussi au poste de pointage après le NIP |
| Feuilles de temps | Présence = arrivée … départ − pauses, comptée au jour de l'arrivée ; départ pendant une pause termine la pause ; heures supplémentaires au-delà de 40 h par semaine ; anomalies (départ manquant, pause non terminée, pointage sans arrivée) bloquent l'approbation ; **approuvées par le gérant seulement** ; une feuille changée après approbation revient « À approuver » ; corrections par nouveau pointage ou annulation, **motif obligatoire**, jamais d'effacement ; « Suivi des périodes » (en cours + 12 précédentes : En cours, À approuver, Approuvée, Envoyée à Sage, Aucune heure) ; rappel en rouge au courriel du matin |
| Employés et NIP | Créés dans Clover (nom, surnom, rôle, courriel) puis dans Sage Paie (adresse, naissance, embauche, impôt du Québec, 26 périodes, taux régulier et supplémentaire) ; courriel obligatoire pour recevoir le bulletin ; dépôt principal ; lien avec l'employé Sage (« Lier aux employés Sage… ») ; relié à un compte de connexion ; le **NAS n'est jamais gardé** ni réaffiché |
| Jours fériés et congés | Fériés du Québec (Vendredi saint ou lundi de Pâques au choix, Patriotes, 24 juin, 1er juillet déplacés si dimanche…) ; indemnité = 1/20 des heures normales des 4 semaines complètes précédentes ; congés (vacances, maladie ou famille payé / non payé, sans solde), un par jour ; vacances 2 semaines / 4 % avant 3 ans, 3 semaines / 6 % ensuite ; 2 jours de maladie payés après 3 mois |
| Calendrier de paie | Paies aux 14 jours à partir de la première paie de l'année ; prochaine paie en vert |
| Traitement de la paie | Heures **approuvées** de l'application (normales + fériés + congés payés en heures régulières, supplémentaires à part) → chèques de paie dans Sage, n° « PAYjjmmaaaa » (comme le dépôt de salaire Desjardins) ; **jamais pour une période à venir** ; un employé et une période une seule fois ; bulletins imprimés, en PDF ou envoyés par courriel, **un destinataire par bulletin, jamais de copie** |
| Paies dans Sage | Détail lu dans les tables de paie de Sage : brut, heures, gains par type, retenues (AE, RPC, RRQ, RQAP, impôts), vacances dues, cumul de l'année |
| Retenues et remises | À remettre par organisme (Revenu Québec, ARC, CNESST) chaque mois, échéance le 15 du mois suivant ; suivi : remis à temps, remis en retard, à remettre, EN RETARD, rien à remettre ; alerte au courriel du matin |
| T4 et Relevé 1 | Formulaires **officiels** téléchargés des sites de l'ARC et de Revenu Québec (recontrôlés tous les 7 jours, gardés seulement si les cases sont aux positions connues), remplis d'après les paies de Sage ; imprimés, en PDF ou envoyés à chacun ; **NAS jamais écrit** |
| Fin d'emploi | Heures assurables des 53 dernières semaines, rémunération des 27 dernières paies, codes de motif du relevé d'emploi ; « Désactiver l'employé » |
| Concordance de fin d'année | Par employé : paies, heures pointées, brut, retenues, net, contrôle |
| Coût de la main-d'œuvre | Par jour : ventes, heures pointées et planifiées, coût (taux moyen × charges sociales), part des ventes ; par dépôt |
| Mes heures et mes paies | La paie réduite à l'employé connecté |

### 3.10 État

| Fonction | Contenu |
|---|---|
| Suivi des ventes | Facture par facture, **tous les points de vente** : date de traitement, journée, statut, HT, taxes, TTC, commentaire, solde dû dans Sage, état du rapprochement ; couleurs bloquée / à encaisser / à rapprocher ; filtre Dépôt |
| Recherche dans l'historique | Client, fournisseur, vente, encaissement, paiement, article (plage « du n° … au n° … »), catégorie, employé ; par article ou par catégorie ; aucun filtre = tout ; « Réinitialiser les filtres » |
| Statistiques Clover | Voir 3.11 |
| Produits inactifs | Source Clover (par défaut) ou Sage ; seuil 30 à 365 jours ou saisi ; tri par valeur du stock puis temps sans vente ; « Seulement les articles en stock » ; cartes des totaux |
| Articles 20/80 | Classe A = les 20 % d'articles qui vendent le plus, B = jusqu'à 50 %, C = le reste ; part du chiffre d'affaires des 20 % ; couverture du stock en jours ; coût douteux hors des totaux |

### 3.11 Statistiques Clover

Lecture seule de Clover, jour par jour ; une vente est datée de son premier paiement réussi, comme la facturation (les ventes nettes des statistiques égalent celles de la facture).

- **Période** comme Clover : aujourd'hui, hier, cette semaine, semaine dernière, ce mois, mois dernier, cette année, personnalisée ; comparaison avec la période d'avant (un jour = même jour la semaine dernière) ; « Journée en cours : actualiser chaque minute ».
- **Filtres globaux** à choix multiples : Article, Client, Employé, Catégorie, Mode de paiement, Point de vente ; recalcul sans relire Clover.
- **Menu des états**, rangé comme Clover : Accueil (8 cartes avec variation bon / mauvais, évolution, montant perçu, catégories, meilleurs articles), Activités de vente, Rapports (aperçu des ventes en 4 graphiques, rapport des ventes par jour ou par heure : brutes, rabais, remboursements, nettes, taxes, pourboires, perçu), Finances (aperçu financier de 28 indicateurs, bénéfices au CUMP), Articles (liste d'articles, péremption), Employés, Clients, Prévisions, Gestion.
- **Vues** : résumé, par jour, jour de semaine, heure, jour × heure (carte de chaleur), employé, mode de paiement, type de carte, mode de saisie, appareil, client, article, catégorie, commandes, paiements, rabais, remboursements, évolution par année ; « Détail par jour ».
- **Graphiques** : courbe avec aire, moyenne pointillée, point le plus haut ; barres avec valeurs ; anneau (5 parts + « Autres ») ; classement ; infobulles au survol ; axe arrondi (5 % au-dessus du maximum, graduations rondes).
- **Bénéfices** : CUMP Sage de l'article relié ; CUMP plus de 5 fois le prix moyen = douteux, écarté.
- **Prévisions** : ventes (même jour sur 4 semaines × tendance bornée 0,8-1,2), achats, articles à commander (stock − vendu sur l'horizon ≤ 0 ; horizon 7 à 90 jours, 14 par défaut).
- **Péremption** : rouge = périmé ou dans moins d'un mois, jaune = 1 à 3 mois.
- **Gestion** : pertes, caisse, dépenses, main-d'œuvre, promotions, retours, bons de commande : cartes, évolution (par jour jusqu'à 62 jours, sinon par mois), répartition, rapport.
- **Analyses décisionnelles** (version 1.0.22), rangées dans les rubriques existantes sans répéter un état déjà présent ; chacune : cartes à feux de couleur, constats en bandeaux colorés (rouge à agir, orange à surveiller, vert bon, gris information), quatre graphiques, tableau exportable, selon la période et les filtres, sans relire Clover ; page qui défile ; sur le téléphone, menu des états en onglets défilants et rapport sur une colonne :
  - *Accueil > Synthèse et décisions* : cartes clés à feux de couleur, décisions à prendre classées par priorité (haute, moyenne, basse) avec la raison et l'endroit où vérifier, points positifs, 6 graphiques ; tableau des décisions exportable ;
  - *Activités de vente > Anomalies et alertes* : jours atypiques (plus de 2 écarts-types du même jour de la semaine), commandes inhabituelles (au-delà de Q3 + 3 × écart interquartile et du 99e centile), rabais de 50 % ou plus, prix à 40 % ou plus du prix médian de l'article, commandes à 0 $ ;
  - *Rapports > Tendance et saisonnalité* : moyenne mobile 7 jours, droite de tendance, indice saisonnier par jour de la semaine, variabilité, semaines comparées (semaine incomplète sans variation), projection des 30 prochains jours ;
  - *Rapports > Analyse de la variation* : écart avec la comparaison = effet nombre de commandes + effet panier moyen ; contribution des catégories, des 40 articles qui bougent le plus et des employés ;
  - *Rapports > Analyse des paniers* : commandes et ventes par tranche de montant et par nombre d'articles, panier médian, 90e centile ;
  - *Rapports > Concentration des ventes* : courbes de concentration, indices de Gini et HHI, part des 1, 3 et 10 premiers, éléments pour 80 % des ventes, pour les articles, catégories, clients, employés, heures, jours et modes de paiement ;
  - *Articles > Matrice des articles* : popularité × rentabilité au CUMP Sage (vedette, locomotive, énigme, poids mort), classe 20/80 × régularité X / Y / Z (par semaine dès 4 semaines), conseil ;
  - *Articles > Articles achetés ensemble* : paires d'articles et de catégories (support, confiance, lift ; au moins 3 commandes ou 0,2 %) ;
  - *Articles > Prix et sensibilité au prix* : changements de prix durables (3 % ou plus, prix stable avant et après) repérés dans les ventes, quantités et ventes par jour d'ouverture avant / après sur le même nombre de jours (28 au plus), élasticité et lecture (peu sensible, sensible, très sensible) ;
  - *Employés > Performance des employés* : articles par commande, prix moyen, taux de rabais et de remboursement, heures actives, ventes par heure active, indice de panier, clients identifiés, variation ;
  - *Clients > Segmentation RFM* : récence, fréquence, montant de 1 à 5 (égalités = même note), 8 segments et action suggérée ;
  - *Clients > Fidélité et rétention* : clients retenus, nouveaux, perdus, taux de rétention, jours entre deux achats ;
  - *Clients > Cohortes de clients* : clients identifiés groupés par mois du premier achat (période et comparaison), part qui revient 1, 2, 3… mois plus tard.
- « 📕 PDF de la page » : graphiques et tableau complet, période et filtres en sous-titre.

### 3.12 Exports et impressions

Chaque tableau a « ⬇ Exporter ▾ » (le plus à droite de sa barre) et un clic droit : Excel (montants en nombres, codes et dates en texte), CSV (« ; », UTF-8), PDF (à l'horizontale au-delà de 7 colonnes), « 🖨 Imprimer… ». En-tête des impressions et PDF : logo, nom, adresse, téléphone et site du marché lus dans Clover, filet vert / rouge / jaune, titre du document au centre, date à droite. Les tableaux datés montrent la date la plus récente en haut, sauf les dates à venir (prévisions, péremption) qui restent chronologiques. Droit « Exporter » requis ; chaque export est noté à l'audit.

Dans l'application web, un texte de plus de 45 caractères dans une cellule est coupé (« … ») et se lit en entier au survol, pour que les montants et les états restent visibles.

---

## 4. Règles de gestion principales

Les règles complètes, codées par module, sont dans le document **Règles d'affaires**.

### 4.1 Facturation des ventes

1. Une vente est datée de son **premier paiement réussi**, pas de la création de la commande ; l'état de paiement Clover « OPEN » ne compte pas.
2. **Une facture par jour du lundi au jeudi, une seule du vendredi au dimanche**, datée du dimanche et préparée après le dimanche, pour encaisser d'un coup le dépôt du lundi.
3. Numéros : « Vente 2026-10-23 » (jour), « Vente 2026-10-23/25 » (vendredi-dimanche), « Vente 2026-10-25 » (bloc d'un seul jour), « Vente S43-2026 » (semaine), « Vente Octobre 2026 » (mois) ; 20 caractères au plus ; préfixe propre à chaque point de vente (« V2 2026-10-23 »).
4. Une ligne par article Sage : montant = **ventes nettes** Clover de l'article (brutes + rabais + remboursements, rabais et remboursements négatifs) ; prix unitaire = ventes nettes / quantité nette, à 4 décimales ; quantité au millième ; total de la facture = ventes nettes. Les pourcentages de rabais d'une commande s'additionnent (100 % au plus) ; les rabais de commande sont répartis au prorata des lignes.
5. Code de taxe « GQ » (TPS 5 % + TVQ 9,975 %) pour les lignes taxées dans Clover ; les taxes de Sage, calculées sur le net, peuvent différer de quelques cents de celles de Clover (arrondis par commande, articles remboursés).
6. Client « Vente Hebdomadaire » (un client par point de vente), mode « Payer plus tard », emplacement par défaut puis transfert vers le dépôt du point de vente.
7. Une facture **n'est jamais importée deux fois** : présence vérifiée dans Sage (n° de facture pour ce client) avant et après l'import ; Sage seul fait foi.
8. Un jour incomplet est **bloqué et signalé**, les autres jours continuent : article vendu non relié (noté dans « articles à relier »), article sans compte de produits, dépôt absent de Sage. Un article « non-recette » dans Clover n'est pas facturé, sans bloquer.
9. Une facture Sage dont la date n'est pas le dernier jour de son numéro (ex. datée de l'année d'avant) est ignorée et signalée.
10. La nuit : tous les jours sans facture depuis la date de départ jusqu'à hier, du plus ancien au plus récent (les trous d'abord), par lots de 25 factures dans un seul fichier d'import.

### 4.2 Encaissements

1. **Dépôt Clover** = encaissé − espèces = lot de cartes fermé chaque soir ; ventes du lundi au jeudi déposées le lendemain, du vendredi au dimanche ensemble le lundi.
2. Encaissement daté du dépôt, « Payé par : Comptant », déposé au compte de dépôt (1055), appliqué sur la facture du jour, ou une seule ligne sur la facture de fin de semaine.
3. **Virements Interac** reçus : sur la facture qui couvre le jour du virement. **Dépôts d'espèces** au guichet : sur les factures de la période qui ont encore des espèces dues (solde dû − lots Clover pas encore encaissés), la plus ancienne d'abord, 14 jours en arrière au plus. Un encaissement par mouvement, daté du mouvement. Sinon « Espèces à répartir à la main ».
4. Dépôt d'espèces supérieur aux espèces dues, même cumulé : le surplus est la **part de RIA à confirmer** ; rien n'est encaissé avant sa confirmation.
5. Un **encaissement manuel** noté au rapprochement (facture + montant) est retiré de la répartition automatique.
6. Un dépôt n'est **jamais saisi deux fois** : chaque dépôt est d'abord cherché dans Sage (compte 1055) ; après « Traiter », la **baisse du solde** de chaque facture fait foi, même si Sage a posé une question.
7. Un lot de cartes dont le **montant exact est déjà au compte de dépôt** par une autre écriture (3 jours avant à 7 jours après) passe à « Déjà au compte de dépôt ? » : à vérifier, jamais encaissé d'office.
8. **Rien n'est saisi** quand le dépôt dépasse le solde dû de la facture (« déjà encaissée autrement ? ») ou quand Sage ne propose pas la facture (déjà payée, ou date fausse).
9. **Un dépôt en échec ne bloque pas les suivants** : il est noté « NON encaissé » avec la raison et une photo de la fenêtre ; les questions restées ouvertes sont refermées, la fenêtre rouverte au besoin, la saisie effacée, et le dépôt suivant est saisi ; si la fenêtre ne peut pas être rouverte, les dépôts restants sont notés « Non tenté ».
10. **Saisie contrôlée** : le montant est tapé dans la cellule « Montant reçu » (jamais avec Tab entre les cellules : Sage y mettrait le montant dû), relu et retapé au besoin ; le total affiché doit égaler le dépôt, sinon tout est effacé et refait (3 essais) ; jamais de « Traiter » sur un total faux.
11. Questions de Sage : « date antérieure à la date de session » → Oui ; conseil (« compte à découvert ») → fermé et noté ; la fenêtre « Traitement… » est attendue, jamais touchée ; autre question → Non, dépôt noté.
12. La nuit, seuls les dépôts des ventes **importées pendant la nuit** sont encaissés (jamais un jour bloqué) ; les dépôts en retard se font par « Encaisser dans Sage » de la page Encaissements, mois par mois si nécessaire.

États d'un dépôt : Appliqué, À saisir dans Sage, Déjà au compte de dépôt ?, Part RIA à confirmer, Espèces à répartir à la main, Facture pas encore dans Sage, NON encaissé, Non tenté.

### 4.3 Paiements fournisseurs

1. Les avis de virement Interac sont lus dans la boîte des avis (lecture seule) depuis la date choisie ; le fournisseur et les factures sont proposés (n° cités dans le message, montants).
2. **Le propriétaire confirme** chaque paiement (« Confirmer ») ; rien n'est saisi sans confirmation ; « Ignorer », « Remettre à relier ».
3. Un virement peut payer **plusieurs factures** du même fournisseur : de la plus ancienne à la plus récente, seule la dernière en partie ; une ligne par facture, un seul « Traiter ».
4. Paiement partiel accepté, **jamais plus que le solde**.
5. Saisie dans la fenêtre Paiements de Sage (« Payer les factures d'achat », Comptant, compte 1055), vérifiée par la baisse du solde. Un paiement en échec ne bloque pas les suivants.
6. Un virement confirmé déjà saisi à la main dans Sage passe à « Déjà dans Sage ».

### 4.4 Rapprochement bancaire

1. Relevé PDF chargé : la **banque est reconnue** à la lecture (Desjardins ou BNC) et le relevé rangé dans le compte de sa banque (et de son n° de compte).
2. Lecture : Desjardins par colonnes Frais / Retrait / Dépôt / Solde ; BNC par lignes « MM JJ description montant solde », débit ou crédit d'après la variation du solde. **Chaque solde imprimé est revérifié** ; le relevé est refusé s'il ne balance pas.
3. Comparé aux écritures du compte Sage de la banque (écritures corrigées exclues) ; même montant, date Sage de 7 jours avant à 3 jours après, sinon somme de 2 ou 3 écritures.
4. Écart = écart d'ouverture + absents de Sage − en circulation ; période du / au, soldes d'ouverture et de fermeture suivis ligne par ligne.
5. Mouvements reconnus : dépôts Clover, virements Interac et dépôts d'espèces (= espèces des ventes, jamais d'écriture de journal), dépôts de salaire (« PAYjjmmaaaa », reliés aux paies de Sage du même montant, 120 jours au plus), commissions RIA.
6. Mouvement absent de Sage : compte de contrepartie choisi puis « Confirmer » ; « Saisir dans Sage » écrit une écriture de journal général par mouvement (source « Relevé AAAA-MM-JJ »), vérifiée. Un virement entre deux comptes de banque est permis ; seul le compte du mouvement est refusé comme contrepartie.
7. « Encaissement manuel » et « Paiement fournisseur manuel » : notés pour que les pages Encaissements et Paiements en tiennent compte.

### 4.5 RIA

1. Envoi reçu en espèces (« MT Send ») : débit espèces, crédit compte RIA.
2. Versement ou remboursement payé en espèces (« MT Payout », « Refund ») : débit compte RIA, crédit espèces ; payé par virement Interac (même montant au relevé, 3 jours près) : rien à écrire, la banque l'a déjà.
3. Règlements de RIA (« ACH ») et dépôts : mouvements de banque.
4. Commission : le dépôt Desjardins égal à la commission payée (12 jours près) est reconnu d'office.
5. Chaque ligne d'état ne devient une opération qu'**une fois** ; rien n'est écrit dans Sage tant que les comptes RIA ne sont pas renseignés.

### 4.6 Sage

- **Import** (factures de vente, d'achat, de retour) : Sage fermé, **mono-utilisateur**. L'entreprise étant **partagée**, l'outil d'import la refuse : l'application passe par l'**Assistant d'importation des transactions** de Sage, sans arrêter le partage. Le fichier est retenu : ses imports suivants passent directement par l'assistant.
- **Saisies** dans les fenêtres de Sage (encaissements, paiements, journal, stock, transferts, fiches, plan comptable, prix, paie) : **multi-utilisateur**, la personne peut garder Sage ouvert. Exception : rendre un compte ou un article inactif, que Sage n'accepte qu'en mono-utilisateur.
- **Sage lié à l'application Windows** : de 6 h à minuit, tant que l'application Windows est ouverte, elle garde Sage ouvert en multi-utilisateur, sans fenêtre visible ; fermée, Sage se ferme et reste fermé. Chaque saisie l'emprunte (prête en moins d'une seconde au lieu d'environ 2 minutes) ; un import le libère d'abord ; la nuit il est refermé. Le serveur web n'ouvre jamais ce Sage : ses saisies l'empruntent s'il est ouvert, sinon ouvrent Sage le temps de la saisie.
- Le **Sage d'une personne passe toujours d'abord** : celui de l'application se ferme en quelques secondes et ne se rouvre que 5 minutes après la fermeture du sien (Sage n'ouvre une entreprise partagée qu'une fois par ordinateur).
- Un Sage resté ouvert sans l'application (après une mise à jour, un arrêt brutal) est **refermé de lui-même**, ses questions comprises (sauvegarde → Non, quitter → Oui, entreprise fermée pour inactivité → Non, enregistrement occupé → OK). Sage ferme une entreprise partagée inactive : l'application le voit et rouvre Sage au besoin.
- Chaque écriture est **vérifiée dans la base de Sage** après coup ; la base fait foi.
- L'application prend d'elle-même la **version de Sage la plus récente** installée (2026, 2027…).
- Tout essai se fait d'abord sur une **copie** du fichier d'entreprise ; l'application ne modifie jamais les paramètres de Sage.

### 4.7 Dépôts et sites

1. Un **dépôt** est un emplacement d'inventaire de Sage : celui d'un point de vente Clover, l'« Emplacement par défaut » ou un dépôt sans Clover (entrepôt, réserve).
2. Une facture (vente, achat, retour) s'importe dans l'emplacement par défaut, puis un **transfert** « DP <n° de facture> » la place dans son dépôt : vente et retour fournisseur = du dépôt vers le défaut, achat = du défaut vers le dépôt ; jamais refait ; un échec laisse la facture importée et signale le transfert « à refaire ».
3. Clover n'est mis à jour que pour un dépôt qui a un point de vente.
4. Chaque employé a un dépôt principal ; un quart peut être dans un autre dépôt ; les heures d'un jour comptent au dépôt du quart, sinon au dépôt principal.
5. Les états se filtrent sur un ou plusieurs dépôts, ou « Tout sélectionner » : documents de stock, livre d'inventaire, liste des articles, main-d'œuvre, suivi des ventes, planning, feuilles de temps.

### 4.8 Données et confidentialité

- Secrets (jeton Clover, mots de passe Sage et courriel) dans le **coffre-fort de Windows** uniquement, jamais réaffichés.
- Aucune intelligence artificielle ni service externe pour lire les factures : OCR intégré à Windows.
- Les boîtes de courriel sont lues sans marquer les messages comme lus.
- Clover : jamais les chiffres d'une carte (seuls le type de carte et le mode de saisie sont gardés).
- Paie : NAS jamais gardé, jamais écrit ; un bulletin va à son seul destinataire.
- Données du marché dans le dossier `donnees/`, sauvegardé chaque nuit ; jamais publiées.

---

## 5. Traitement de nuit

Chaque nuit, sans intervention, dans la session Windows du serveur (verrouillée possible). Le Sage gardé ouvert pour la journée est refermé d'abord ; un verrou empêche deux traitements en même temps. Chaque étape est indépendante : une étape en échec est notée au compte rendu et les suivantes se font.

| Étape | Ce qui est fait |
|---|---|
| 1 | Factures fournisseurs reçues par courriel copiées et lues ; avis de paiement lus ; factures « Prête à importer » importées ; factures déjà dans Sage archivées |
| 2 | États de compte RIA reçus lus ; opérations saisies dans Sage si les comptes sont renseignés |
| 3 | Ventes Clover lues pour chaque jour sans facture, du plus ancien au plus récent, pour chaque point de vente |
| 4 | Factures préparées, contrôlées, importées par lots de 25 (assistant si l'entreprise est partagée), vérifiées, puis transférées dans le dépôt de leur point de vente |
| 5 | Dépôts des ventes importées pendant la nuit encaissés |
| 6 | Paiements fournisseurs « Confirmé » saisis |
| 7 | Promotions appliquées ou terminées, statistiques des 7 derniers jours préchauffées, tableau du gérant écrit |
| 8 | Données sauvegardées |
| 9 | Compte rendu par courriel : résumé du matin et une pièce jointe Excel par module |

**Résumé du matin** : ventes d'hier contre le même jour la semaine d'avant, marge des articles au CUMP connu, solde du compte de dépôt, factures à payer d'ici 7 jours (retards compris), ruptures parmi les articles A, articles à commander, produits périmés en stock ; en rouge : retenues en retard, caisse d'hier non comptée ou écart de plus de 5 $, feuilles de temps à approuver ; en bleu : jours fériés et congés des 7 prochains jours.

---

## 6. Données gérées

| Donnée | Source de vérité | Gardée dans l'application |
|---|---|---|
| Ventes, articles, stocks Clover, employés | Clover | jours terminés en cache, catalogue |
| Factures, encaissements, comptes, articles et stocks Sage | Sage | lectures gardées quelques minutes |
| Correspondance Clover → Sage | Application (validée par le propriétaire) | `correspondance_articles.xlsx` (et une par point de vente) |
| Factures fournisseurs lues, bons de commande, documents | Application, puis Sage | registres JSON, PDF, impressions, archives par année |
| Relevés bancaires | Banque (PDF chargé à la main) | un dossier par compte (`releves_<code>/`) |
| Dépôts | Sage (emplacements) + réglage « dépôts sans Clover » | `config.toml` |
| États et opérations RIA | RIA (états), application (opérations), puis Sage | `ria.json`, `etats_ria/` |
| Pointages, feuilles de temps, planning, congés | Application | registres JSON (jamais effacés, corrections ajoutées) |
| Comptes, droits et audit | Application | `utilisateurs.json` (empreintes), `audit.jsonl` (chaîné) |
| Historique des ventes facturées | Application + Sage | `historique_ventes.csv`, `journal_imports.csv` |

---

## 7. Contraintes et prérequis

- Un serveur Windows qui a Sage 50 ET MVOGMBI_Sync (traitement de nuit, serveur web) ; réglé dans « Administration > Automatisation », rien n'est écrit dans le programme.
- Tailscale sur le serveur et sur chaque appareil qui utilise l'application web (postes, téléphones) ; nom `app.marchemvogmbi.com` (DNS) vers l'adresse Tailscale du serveur ; HTTPS par un certificat renouvelé (relu chaque heure).
- Pointage : appareils sur le Wi-Fi du magasin (adresse publique du magasin réglée), ou postes du magasin listés.
- Windows 10 ou 11, Sage 50 CA 2026 ou plus récent ; Microsoft Edge ou Chrome pour les pages HTML (fiches de paie, PDF de la page des statistiques) ; les autres PDF sont créés par l'application.
- Service « Sage 50 Gestionnaire de connexion de base de données » démarré (multi-utilisateur, lecture de la base).
- Utilisateur Sage `mvogmbi_sync` avec « Accès par des tiers » (consultation, modules Stocks & Services, Clients & Ventes, Paie) et le même mot de passe dans chaque fichier d'entreprise.
- Fiches Sage : client « Vente Hebdomadaire » et fournisseurs avec « utilise mes numéros d'articles » ; chaque article a un compte de produits.
- Jeton Clover avec les droits de lecture, et d'écriture pour l'inventaire et les employés.
- Accès Internet pour Clover, les courriels et le téléchargement des formulaires T4 / RL-1.
- Session Windows ouverte la nuit (verrouillée possible) : Sage ne s'ouvre pas en session 0.

---

## 8. Messages fréquents

| Message | Sens | Que faire |
|---|---|---|
| « Sage ne répond pas » (page web) | Base de Sage injoignable | Tableaux vides affichés ; réessayer dans 45 s ; vérifier le service de Sage |
| « Sage s'ouvre pour les saisies de la journée » | Le Sage de la journée s'ouvre (2 à 3 minutes) | Attendre ; une saisie lancée attend d'elle-même |
| « Fermez Sage : l'application l'ouvre elle-même » | Un Sage ouvert par une personne occupe l'entreprise | Fermer ce Sage, relancer |
| « Compte manquant (import bloqué) » | Article de la facture sans compte de produits | « Corriger les comptes dans Sage… » |
| « NON encaissé : dépôt supérieur au solde dû » | Une partie de la facture déjà encaissée | Vérifier la facture dans Sage, relancer |
| « … n'est pas dans la liste des factures en souffrance » | Facture payée ou mal datée dans Sage | Corriger la facture, relancer |
| « Déjà au compte de dépôt ? » | Le montant est déjà au 1055 par une autre écriture | Vérifier dans Sage ; si c'est ce dépôt, rien à faire |
| « Espèces à répartir à la main » | Mouvement d'espèces sans facture qui en attend | Encaissement manuel au rapprochement |
| « Article Clover introuvable (supprimé ou recréé) » | Article relié renommé dans Clover | Relier le nouvel article, puis « Refaire la mise à jour Clover » |

---

## 9. Glossaire

| Terme | Sens |
|---|---|
| Assistant d'importation | Fonction de Sage « Fichier > Importer/Exporter > Importer des transactions », utilisée quand l'entreprise est partagée |
| BNC | Banque Nationale du Canada ; relevés lus comme ceux de Desjardins |
| Bon de réception / bon de livraison | Document sans prix : réception d'un achat / livraison d'une vente |
| Correspondance | Lien entre un article Clover et un numéro d'article Sage |
| CUMP | Coût unitaire moyen pondéré du stock dans Sage |
| Dépôt (stock) | Emplacement d'inventaire Sage : d'un point de vente, par défaut, ou sans Clover |
| Dépôt (banque) | Versement Clover sur le compte Desjardins |
| Entreprise partagée | Fichier Sage ouvert par plusieurs postes ; l'outil d'import le refuse |
| Facteur | Nombre d'unités Sage dans une unité du fournisseur |
| FRC / FRT | Facture de retour client / fournisseur (quantités et montants négatifs) |
| Lot Clover | Paiements par carte fermés chaque soir et déposés ensemble |
| Mono / multi-utilisateur | Ouverture exclusive de l'entreprise Sage (import), ou partagée (saisies) |
| Non-recette | Article Clover qui n'est pas compté comme une vente (non facturé) |
| RIA | Service de transfert d'argent dont le marché est agent ; « MT Send » = envoi, « MT Payout » = versement |
| Sage de la journée | Sage gardé ouvert par l'application Windows pour que les saisies commencent tout de suite |
| serveur.json | Fichier du client des postes : nom tapé (app.marchemvogmbi.com) → adresse du serveur |
| Tailscale | Réseau privé chiffré entre le serveur, les postes et les téléphones |
| UGS | Code d'article Clover (SKU) ; sert à noter la date de péremption |
