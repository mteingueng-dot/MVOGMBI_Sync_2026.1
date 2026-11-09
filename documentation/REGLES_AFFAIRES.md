# MVOGMBI_Sync — Règles d'affaires

Version 1.0.20 (7 novembre 2026) — Marché MVOG-MBI Sherbrooke.

Ce document réunit **toutes les règles d'affaires** appliquées par l'application, module par module : ce qui est calculé, ce qui est permis, ce qui est refusé et pourquoi. Il complète la documentation fonctionnelle (ce que fait l'application) et le document d'architecture (comment elle est construite).

Chaque règle porte un code `RG-<module>-<n°>`. Sauf mention contraire, une règle a été fixée ou validée par le propriétaire du marché. Aucune donnée réelle (montant, nom, numéro de pièce) n'apparaît ici : les exemples sont fictifs.

---

## 1. Principes généraux

| Code | Règle |
|---|---|
| RG-GEN-01 | **Sage 50 reste la référence comptable.** L'application prépare, saisit et vérifie ; elle ne remplace jamais un état de Sage. |
| RG-GEN-02 | **Rien n'est fait deux fois.** Chaque écriture, facture, paiement, mise à jour de stock ou envoi porte une clé (numéro, date, source) ; une opération déjà présente dans Sage, dans Clover ou dans un journal de l'application est sautée. |
| RG-GEN-03 | **Tout ce qui est écrit est vérifié.** Après une saisie dans Sage, l'application relit la base de Sage (facture, écriture, solde, stock) ; seule cette relecture fait foi. Un outil qui répond « succès » sans changement visible est un échec. |
| RG-GEN-04 | **Les essais se font sur la copie d'essai** du fichier d'entreprise. Le vrai fichier n'est que lu tant qu'une fonction n'est pas validée sur la copie. |
| RG-GEN-05 | **Clover est en production** : un essai d'écriture dans Clover se fait sur un article ou un employé d'essai caché, supprimé ensuite. |
| RG-GEN-06 | **Aucun service externe d'intelligence artificielle** n'est utilisé ; la lecture des PDF numérisés passe par l'OCR intégré à Windows. |
| RG-GEN-07 | **Les secrets** (jeton Clover, mots de passe de Sage et des boîtes de courriel) sont gardés dans le coffre-fort de Windows, jamais dans un fichier. |
| RG-GEN-08 | **Le NAS d'un employé n'est jamais gardé** par l'application, ni écrit sur un document qu'elle produit. |
| RG-GEN-09 | **Montants en décimal exact**, arrondis au cent seulement à l'affichage ou à la saisie ; quantités au millième ; prix unitaires à 4 décimales. |
| RG-GEN-10 | **Fuseau horaire** : America/Toronto pour toutes les dates de Clover. |
| RG-GEN-11 | **Textes affichés et courriels** : l'application ne parle jamais de « robot » ni de fenêtres cachées ; elle dit « l'application ouvre Sage elle-même ». |
| RG-GEN-12 | **Tableaux datés** : la date la plus récente en haut ; exceptions : prévisions et péremption (dates futures, la plus proche d'abord) et graphiques (chronologiques). |

---

## 2. Sage 50 : règles d'utilisation

| Code | Règle |
|---|---|
| RG-SAGE-01 | **Import** (`Sage_SA_import`) : l'entreprise est ouverte en mono-utilisateur ; Sage doit donc être fermé partout. |
| RG-SAGE-02 | **Saisies dans les fenêtres de Sage** (encaissements, paiements, journal général, stock, fiches) : multi-utilisateur. Exception : rendre un compte ou un article inactif, que Sage n'accepte qu'en mono-utilisateur. |
| RG-SAGE-03 | Sage fermé, **l'application ouvre Sage elle-même** pour une saisie, puis le referme proprement (jamais d'arrêt forcé). Sage ouvert par la personne : l'application refuse les saisies qui demanderaient de l'ouvrir à sa place et le dit. |
| RG-SAGE-04 | Une **lecture automatique** n'ouvre jamais Sage : elle passe par la base si elle est disponible, sinon elle attend un geste de la personne. |
| RG-SAGE-05 | La connexion à la base est **relâchée** dès que la personne lance Sage ou qu'un import en a besoin (sinon « d'autres utilisateurs travaillent avec cette entreprise »). |
| RG-SAGE-06 | Les **questions de Sage** reçoivent une réponse prudente : « Non » à une erreur d'import, « Oui » seulement aux confirmations connues (date antérieure, comptes de taxe associés, suppression demandée) ; toute autre question arrête l'opération. |
| RG-SAGE-07 | Un compte saisi dans l'application (dépenses, RIA, catégories, fiches) **doit exister dans le plan comptable** de Sage et recevoir des écritures (ni en-tête, ni total, ni inactif). |
| RG-SAGE-09 | **Entreprise partagée** : le partage n'est jamais arrêté ; quand l'outil d'import refuse l'entreprise partagée, l'import passe par l'**Assistant d'importation des transactions** de Sage (ouvert en mono-utilisateur par l'application) ; le fichier est retenu et passe ensuite directement par l'assistant. |
| RG-SAGE-10 | **Sage lié à l'application Windows** (règle du propriétaire du 6 novembre 2026) : Sage s'ouvre quand on ouvre l'application Windows MVOGMBI_Sync (après la connexion), en **multi-utilisateur**, et se ferme quand on la ferme ; **si l'application n'est pas ouverte, Sage reste fermé**. Le serveur web ne garde jamais Sage ouvert : ses saisies utilisent le Sage de l'application Windows s'il est ouvert, sinon ouvrent Sage le temps de la saisie. L'import (mono-utilisateur), la nuit (0 h - 6 h) et le traitement de nuit le referment d'abord. Une saisie en cours est toujours terminée avant que Sage se referme ; une application arrêtée brutalement referme quand même Sage (le gardien la surveille). `[sage] garder_ouvert = false` : plus jamais gardé ouvert. |
| RG-SAGE-10b | Le Sage ouvert par l'application (pour la journée, ou pour une saisie) n'est **jamais pris pour le Sage d'une personne**, même pendant son ouverture : il ne bloque aucune saisie. |
| RG-SAGE-10c | Tant que le Sage de la journée est ouvert **ou en train de s'ouvrir**, aucune lecture ne passe par l'outil d'import (il prendrait l'entreprise pour lui seul). Une saisie ou un import lancé pendant l'ouverture **attend** qu'elle soit finie. |
| RG-SAGE-10e | **Le Sage d'une personne passe d'abord** : Sage n'ouvre une entreprise partagée qu'une fois par ordinateur ; dès qu'une personne lance Sage sur le serveur (n'importe quelle session), le Sage de la journée se referme en quelques secondes et ne se rouvre que 5 minutes après la fermeture du dernier Sage d'une personne. |
| RG-SAGE-10f | Un **Sage resté seul** sur le bureau de l'application (programme qui le gardait arrêté) est reconnu et **refermé proprement**, jamais arrêté de force ; une mise à jour de l'application referme d'abord le Sage de la journée. |
| RG-SAGE-10g | À la fermeture d'un Sage de l'application, une **proposition de sauvegarde** reçoit « Non » (l'application fait ses propres sauvegardes), une **confirmation de fermeture** « Oui », la question « Cette entreprise a été fermée suite à une période d'inactivité. Voulez-vous la réouvrir ? » « Non » et l'avertissement « … un autre utilisateur traitait aussi une transaction … » « OK » ; Sage ferme l'entreprise après une période d'inactivité : le Sage gardé ouvert est alors refermé, puis rouvert neuf au besoin ; toute autre question n'est jamais répondue d'office, son texte est noté. Un Sage d'une autre origine n'est jamais arrêté de force. |
| RG-SAGE-10d | Une ouverture du Sage de la journée qui échoue est **réessayée 10 minutes plus tard**, jamais à chaque minute ; la raison est notée. |
| RG-SAGE-08 | Sage tient chaque compte dans son **sens normal** (débit positif pour actif et charge, crédit positif pour passif et produit) ; l'application lit les soldes sans changer le signe. |

---

## 3. Ventes Clover et facturation dans Sage

| Code | Règle |
|---|---|
| RG-VEN-01 | Une vente est **datée de son premier paiement réussi**, pas de la création de la commande. |
| RG-VEN-02 | **Ventes nettes = ventes brutes + rabais + remboursements** (rabais et remboursements négatifs, comme dans Clover). |
| RG-VEN-03 | Les **pourcentages de rabais** d'une commande s'additionnent, plafonnés à 100 % ; un rabais de commande est réparti sur les lignes au prorata. |
| RG-VEN-04 | **Une facture par jour du lundi au jeudi ; une seule facture du vendredi au dimanche** (« Vente AAAA-MM-JJ/JJ », datée du dimanche, préparée après le dimanche), pour encaisser d'un coup le dépôt du lundi. |
| RG-VEN-05 | Un samedi ou un dimanche choisi remonte au vendredi ; une fin de semaine **en partie facturée est bloquée** (jamais de deuxième facture partielle). |
| RG-VEN-06 | Numéro de facture : « Vente AAAA-MM-JJ », « Vente AAAA-MM-JJ/JJ », « Vente Snn-AAAA » (semaine), « Vente Mois AAAA » ; 20 caractères au plus. |
| RG-VEN-07 | **Une ligne par article Sage** ; montant de ligne = ventes nettes Clover de l'article ; prix unitaire = ventes nettes / quantité nette (4 décimales) ; total = ventes nettes Clover. |
| RG-VEN-08 | Client « Vente Hebdomadaire » (un client par point de vente) ; mode « Payer plus tard » ; code de taxe « GQ » sur les lignes taxées dans Clover ; date = dernier jour de la période. |
| RG-VEN-09 | Les taxes recalculées par Sage peuvent différer de quelques cents de celles encaissées par Clover (arrondis par commande, remboursements) ; l'écart est signalé, jamais forcé. |
| RG-VEN-10 | Une facture est **refusée** s'il reste des points à vérifier, si un article n'a pas de compte de produits, si la facture existe déjà dans Sage ou si le doublon ne peut pas être vérifié. |
| RG-VEN-11 | Article « non-recette » dans Clover : non facturé, signalé, jamais bloquant ; aucun signalement si le catalogue le compte aujourd'hui comme recette. |
| RG-VEN-12 | Une facture Sage dont la date n'est pas le dernier jour de son numéro est **ignorée et signalée** (elle ne couvre pas les jours qu'elle prétend couvrir). |

---

## 4. Correspondance des articles Clover → Sage

| Code | Règle |
|---|---|
| RG-COR-01 | Rapprochement proposé par code-barres, puis nom identique, puis ressemblance ; **le propriétaire confirme**. Une ligne « Confirmé » est gardée à chaque mise à jour (clé : ID Clover). |
| RG-COR-02 | **Deux formats différents sont deux articles différents** (« 1kg » / « 500g ») : la correspondance ne propose jamais deux formats différents ; sans article Sage au bon format → « À créer dans Sage ». |
| RG-COR-03 | Une liaison **confirmée par le propriétaire** malgré un format différent est valide, appliquée et jamais annulée. |
| RG-COR-04 | La facture relie d'abord par **ID Clover** (le nom vendu a pu changer), puis par nom. |
| RG-COR-05 | Article **renommé ou supprimé dans Clover** : la vente garde l'ancien ID ; la ligne est notée « à relier » et l'article Clover actuel le plus ressemblant (même format) est proposé, « À confirmer ». |
| RG-COR-06 | Un montant vendu sans article (« Article personnalisé ») va sur l'article Sage prévu à cet effet. |

---

## 5. Encaissements des ventes

| Code | Règle |
|---|---|
| RG-ENC-01 | **Dépôt Clover = encaissé − espèces = lot de cartes** fermé chaque soir ; ventes du lundi au jeudi déposées le lendemain, du vendredi au dimanche ensemble le lundi. |
| RG-ENC-02 | L'encaissement est **daté du dépôt**, payé par « Comptant » au compte de dépôt, appliqué sur la facture qui couvre le lot (une seule ligne pour la facture de fin de semaine). |
| RG-ENC-03 | Aucun dépôt antérieur à la date de départ configurée n'est touché. |
| RG-ENC-04 | Le **total saisi est contrôlé avant « Traiter »** ; après, la baisse du solde de chaque facture est vérifiée. |
| RG-ENC-05 | La nuit, seules les ventes **importées pendant l'exécution** sont encaissées ; un jour bloqué ne l'est jamais. |
| RG-ENC-06 | **Virements Interac reçus et dépôts d'espèces au guichet font partie des espèces des ventes** : jamais d'écriture de journal ; Interac → facture qui couvre le jour du virement ; dépôt d'espèces → factures dont il reste des espèces, la plus ancienne d'abord ; sinon « à répartir à la main ». |
| RG-ENC-07 | Un lot Clover le même jour qu'un encaissement d'espèces n'est appliqué que si son montant exact est dans Sage. |
| RG-ENC-08 | Un **encaissement manuel** noté au rapprochement retire ce mouvement de la répartition automatique. |
| RG-ENC-09 | La part d'un dépôt d'espèces **au-delà des ventes** est une part RIA : rien n'est encaissé avant sa confirmation (voir section 8). |
| RG-ENC-10 | Un lot de cartes dont le **montant exact est déjà au compte de dépôt** par une autre écriture (3 jours avant à 7 jours après le dépôt) passe à « Déjà au compte de dépôt ? » : jamais encaissé d'office, pour ne pas compter la banque deux fois. |
| RG-ENC-11 | La saisie d'un montant dans la fenêtre Encaissements se fait toujours dans la colonne « Montant reçu », quelle que soit la taille de la fenêtre de Sage ; une cellule ouverte ailleurs est refermée **sans rien taper**. |
| RG-ENC-12 | **Un encaissement qui échoue ne bloque pas les suivants** (demande du propriétaire du 7 novembre 2026) : il est noté « NON encaissé » avec la raison (et une photo), les questions restées ouvertes sont refermées, la saisie est effacée et le dépôt suivant est saisi. Seule une fenêtre Encaissements impossible à rouvrir arrête la saisie ; les dépôts restants sont alors notés « non tenté ». Même règle pour les paiements fournisseurs. |
| RG-ENC-13 | **Le montant tapé est relu avant d'être validé** (constat du 7 novembre 2026 sur le vrai fichier) : juste après un encaissement traité, Sage propose le montant dû dans la cellule « Montant reçu » pendant que l'application tape ; la cellule est sélectionnée en entier avant la saisie, puis relue, et retapée (3 essais) tant qu'elle ne contient pas le montant du dépôt. Le contrôle du total avant « Traiter » reste le garde-fou. |
| RG-ENC-14 | **Jamais de Tab pour passer d'une cellule à l'autre** dans la grille des encaissements : Sage remplit d'office le « Montant reçu » de chaque cellule traversée. La grille défile, l'application clique dans la bonne cellule, tape, puis un seul Tab valide. |
| RG-ENC-15 | **Questions de Sage pendant un encaissement** : « date antérieure à la date de session » → Oui ; conseil de Sage (« compte chèques à découvert ») → fermé et noté ; fenêtre « Traitement… » → attendue (120 s au plus), jamais touchée ; « un autre utilisateur traitait aussi une transaction » → OK ; toute autre question → Non, le dépôt est noté et le suivant est saisi. |
| RG-ENC-16 | **Ordre de la grille** : les factures en souffrance du client apparaissent triées par date puis par n° interne, comme dans la base ; l'ordre est relu dans Sage avant chaque dépôt (une facture payée en entier disparaît de la grille). |
| RG-ENC-17 | Un dépôt couvre au plus le **solde dû** de chaque facture : un dépôt plus grand n'est pas saisi (« déjà encaissée autrement ? »), une facture absente de la grille non plus (déjà payée ou mal datée). |
| RG-ENC-18 | Un **rattrapage** d'encaissements se fait par mois de dépôt (une ouverture de Sage par mois) ; les dépôts « Déjà au compte de dépôt ? » et « Espèces à répartir à la main » n'y sont jamais saisis d'office. |

---

## 6. Rapprochement bancaire

| Code | Règle |
|---|---|
| RG-RAP-01 | Chaque **solde imprimé** du relevé est recalculé ligne par ligne ; un écart arrête la lecture. |
| RG-RAP-02 | Un mouvement est rapproché d'une écriture Sage **du même montant, datée de 7 jours avant à 3 jours après**, sinon d'une somme de 2 ou 3 écritures. |
| RG-RAP-03 | Les écritures corrigées (annulées et leurs contre-passations) sont exclues. |
| RG-RAP-04 | Écart = écart d'ouverture + mouvements absents de Sage − écritures en circulation ; le but est « 0,00 non expliqué ». |
| RG-RAP-05 | Un mouvement relié à une écriture d'avant le début de la période compte comme absent (il est déjà dans l'écart d'ouverture). |
| RG-RAP-06 | **Dépôt salaire** (« PAYjjmmaaaa ») : relié aux paies de Sage du même montant jusqu'à 120 jours plus tôt, la même référence-date d'abord ; sinon « Paie absente de Sage » (à corriger dans la paie, jamais par une écriture de journal). |
| RG-RAP-08 | **Banque reconnue à la lecture** : un relevé Desjardins ou Banque Nationale (BNC) est lu selon sa banque et rangé dans le compte bancaire de cette banque (et de son n° de compte quand la banque en a plusieurs) ; il est rapproché du compte Sage de ce compte (Desjardins 1055, BNC 1060 par défaut). |
| RG-RAP-09 | **Relevé BNC** : le sens de chaque mouvement (débit / crédit) se déduit de la variation du solde imprimé ; les totaux « TRANSACTIONS DÉBIT / CRÉDIT » du relevé doivent être retrouvés ; la facturation détaillée est ignorée. |
| RG-RAP-10 | **Comptes bancaires** : d'autres comptes s'ajoutent dans « Administration > Sage 50 » (banque, format du relevé, compte Sage, n° de compte) ; dans une écriture de journal, seul le compte de banque du mouvement est refusé comme contrepartie (un virement d'une banque à l'autre est permis). Encaissements, caisse et RIA restent sur Desjardins. |
| RG-RAP-07 | Un mouvement absent de Sage devient une écriture de journal général seulement après **décision** de la personne (compte choisi) ; source « Relevé AAAA-MM-JJ », vérifiée par source + date + montant. |
| RG-RAP-11 | **Espèces des ventes** : un virement Interac reçu (« VRW Virement Interac de ») ou un dépôt d'espèces au guichet (« DGA Dépôt au GA ») est marqué « À encaisser sur les ventes » : il n'est jamais une écriture de journal (il passe par les encaissements). |
| RG-RAP-12 | Un relevé chargé deux fois n'est gardé qu'une fois ; « Supprimer le relevé » le range à part (jamais effacé), ses décisions avec lui. |
| RG-RAP-13 | Mouvements à rapprocher dans l'ordre : même montant à la date la plus proche d'abord ; une écriture Sage ne sert qu'à un seul mouvement. |

---

## 7. Fournisseurs : factures, paiements, retours, bons de commande

### 7.1 Factures fournisseurs

| Code | Règle |
|---|---|
| RG-FRN-01 | **Qté Sage = Qté fournisseur × Facteur ; Montant = Qté × Prix fournisseur ; Prix Sage = Montant / Qté Sage.** Montant et Qté Sage sont calculés, non saisis. |
| RG-FRN-02 | Le facteur et l'article Sage choisis sont **mémorisés par fournisseur** et reproposés. |
| RG-FRN-03 | Le **total de la facture lue doit être retrouvé** (lignes + taxes) avant qu'elle soit « Prête à importer ». |
| RG-FRN-04 | Le **n° de facture du fournisseur est obligatoire** ; un doublon est reconnu même avec un préfixe (« FA-104202 » = « 104202 »). |
| RG-FRN-05 | Une facture « Prête à importer » **déjà dans Sage** (même fournisseur, même numéro) est archivée « Déjà dans Sage » et retirée de la liste. |
| RG-FRN-06 | Taxes par ligne (GQ, G, Q, aucune) ; l'écart d'arrondi au cent va sur la dernière ligne qui porte chaque taxe. |
| RG-FRN-07 | Prérequis : la fiche du fournisseur « utilise mes numéros d'articles ». |
| RG-FRN-08 | Après l'import vérifié : **stock Clover = stock + Qté Sage, coût Clover = Montant / Qté Sage** pour les articles reliés (jamais deux fois ; plusieurs articles Clover sur un n° Sage → coût seulement). La case « Mettre aussi à jour Clover » permet de ne toucher que Sage. |
| RG-FRN-09 | Factures reçues par courriel : boîte lue **sans marquer les messages comme lus** ; pièces jointes des expéditeurs ou textes configurés ; jamais un avis Interac ; jamais deux fois le même fichier (empreinte). |
| RG-FRN-10 | La nuit, les factures « Prête à importer » sont importées (réglable) ; les autres attendent la personne. |
| RG-FRN-11 | Une facture importée est archivée par année (PDF, données, Excel). |
| RG-FRN-12 | **Plusieurs factures cochées** s'importent en une fois ; seules les « Prête à importer » partent, les autres sont signalées. |
| RG-FRN-13 | **Facture photographiée** : chaque photo est une page (15 au plus), sens corrigé ; « Terminer la facture » en fait un PDF lu par l'OCR de Windows et ajouté à la liste ; les photos restent sur le serveur, jamais dans la page. |
| RG-FRN-14 | **Même état partout** : une facture importée ou archivée depuis le web l'est aussi dans Windows, et inversement ; une facture « Importée » n'est jamais ramenée à un autre état. |
| RG-FRN-15 | Un **courriel de compte rendu** suit chaque import de factures fournisseurs fait à la demande (mêmes destinataires que la nuit). |
| RG-FRN-16 | Un article Clover relié qui n'existe plus (supprimé ou recréé) est écarté de la mise à jour du stock avec un message ; la mise à jour Clover se **refait** sans ajouter deux fois une ligne déjà faite. |
| RG-FRN-17 | **Impressions** : « Bon de réception » sans prix (quantité Sage, quantité ajoutée dans Clover, observation, signature) et « Facture (avec prix) » à joindre à la facture du fournisseur. |
| RG-FRN-18 | Le **dépôt** de la facture reçoit la marchandise : import dans l'emplacement par défaut puis transfert vers le dépôt (voir RG-DEP-02) ; stock Clover du point de vente du dépôt, rien pour un dépôt sans Clover. |

### 7.2 Paiements fournisseurs

| Code | Règle |
|---|---|
| RG-PAY-01 | Les avis de virement Interac sont **proposés** contre les factures ouvertes ; le propriétaire **confirme** ; seuls les paiements « Confirmé » sont saisis. |
| RG-PAY-02 | Paiement partiel accepté, **jamais plus que le solde**. |
| RG-PAY-03 | Un virement peut payer plusieurs factures du même fournisseur : **de la plus ancienne à la plus récente**, seule la dernière en partie. |
| RG-PAY-04 | Un virement déjà saisi à la main dans Sage passe à « Déjà dans Sage ». |
| RG-PAY-05 | Vérification par la baisse du solde de chaque facture. |
| RG-PAY-06 | **Un paiement en échec ne bloque pas les suivants** (comme RG-ENC-12) ; fenêtre Paiements rouverte au besoin, paiements restants « non tenté » si elle ne peut pas l'être. |
| RG-PAY-07 | Les avis sont lus **depuis la date choisie** (même réglage que la boîte des avis) ; un avis déjà traité n'est jamais relu comme nouveau. |

### 7.3 Bons de commande et retours

| Code | Règle |
|---|---|
| RG-BC-01 | **À commander = stock − vendu sur N jours ≤ 0** (N = « Couvrir », 14 jours par défaut) ; quantité = vendu − stock positif, arrondie à l'unité supérieure. |
| RG-BC-02 | Fournisseur et prix proposés = **dernier achat** de l'article ; quantités en unités du fournisseur (quantité Sage / facteur, arrondie au-dessus). |
| RG-BC-03 | Un article sans lien Sage ou jamais acheté est montré mais non cochable. |
| RG-BC-04 | **Un bon par fournisseur** ; il se compare à la facture du même fournisseur datée du bon ou après, en unités Sage, à 2 % près. |
| RG-BC-05 | Un bon ne se modifie ou ne se supprime que dans l'état « Créé ». |
| RG-RET-01 | **Retour fournisseur = facture d'achat aux quantités et montants négatifs**, n° « R-<n° de la facture d'origine> » ; lignes reprises de la facture d'origine ; le stock Clover baisse après l'import vérifié ; jamais deux fois. |

---

## 8. RIA (transferts d'argent)

Le marché est agent RIA : il reçoit des espèces pour des envois, verse des espèces aux bénéficiaires et touche une commission mensuelle (son seul revenu RIA).

| Code | Règle |
|---|---|
| RG-RIA-00 | Toutes les fonctions RIA sont dans la rubrique **RIA** du menu : Opérations RIA, États de compte RIA, Comptes RIA (demande du propriétaire du 6 novembre 2026). |
| RG-RIA-01 | **Envoi reçu en espèces** (« MT Send ») : débit espèces / crédit compte RIA (dû à RIA). |
| RG-RIA-02 | **Versement ou remboursement payé en espèces** (« MT Payout », « MT Refund ») : débit compte RIA / crédit espèces. |
| RG-RIA-03 | Un versement **payé par virement Interac** (même montant au relevé de banque, à 3 jours près) n'a pas d'écriture d'état : la banque l'a déjà. |
| RG-RIA-04 | Règlements de RIA (ACH) et dépôts : mouvements de **banque**, traités par le rapprochement. |
| RG-RIA-05 | **Surplus d'un dépôt d'espèces** au-delà des ventes : part RIA à confirmer ; quand les états RIA sont traités, le surplus va aux espèces. |
| RG-RIA-06 | **Commission** : le dépôt égal à la commission payée de l'état (dans les 12 jours) est marqué « Commission » d'office. |
| RG-RIA-07 | Chaque ligne d'état devient une opération **une seule fois** (clé : agence, date, référence, activité) ; sous-totaux et totaux ignorés ; une ligne répétée sur plusieurs pages n'est comptée qu'une fois. |
| RG-RIA-08 | Chaque état est **recontrôlé** : solde courant recalculé ligne par ligne, totaux des débits et crédits contre le résumé ; un écart est noté en remarque. |
| RG-RIA-09 | Rien n'est saisi dans Sage tant que les **comptes RIA, commissions et espèces** ne sont pas renseignés (RIA > Comptes RIA). |
| RG-RIA-10 | Les états reçus par courriel sont lus la nuit, puis traités dans Sage si les comptes sont renseignés. |

---

## 9. Articles

| Code | Règle |
|---|---|
| RG-ART-01 | **Création** : Clover (nom, prix, type de prix, taxes, catégorie, coût, UGS) et Sage (n°, description, comptes) ; prix Clover proposé = achat + 40 %. |
| RG-ART-02 | **L'UGS Clover porte la date de péremption** (JJ/MM/AAAA), obligatoire à la création. |
| RG-ART-03 | **N° Sage = préfixe de la catégorie + suivant libre** ; comptes (actif, produits, CMV, écart) = ceux de la catégorie ; écart vide = CMV. |
| RG-ART-04 | Règle des comptes : **actif 15xx → produits 40xx → CMV 50xx** de la même famille ; une incohérence est signalée, un compte de produits manquant bloque l'import. |
| RG-ART-05 | Catégorie d'un article : celle qui s'accorde avec le plus de ses comptes (un point par compte) + un point pour la catégorie Clover de ses articles reliés ; égalité = rien proposé. |
| RG-ART-06 | **Un service** (n° commençant par S) se crée **dans Sage seulement, jamais dans Clover** ; comptes Produits (facultatif) et Charges. |
| RG-ART-07 | **Modifier un article** : description et état inactif dans Sage ; l'article Clover relié est renommé si la personne le demande. |
| RG-ART-08 | **Supprimer un article** : supprimé de Sage, puis les articles Clover reliés. Sage **refuse** de supprimer un article encore en stock : il est alors rendu inactif dans Sage et l'article Clover est **gardé**. |
| RG-ART-09 | **Coût Clover = CUMP Sage** pour les lignes cochées ; jamais de valeur aberrante : CUMP absent, > 5 × prix de vente ou < 5 % du prix → non cochable ; à vérifier (décoché) : CUMP ≥ prix, plus de 3 fois d'écart avec le coût Clover, n° Sage relié à plusieurs articles Clover. |
| RG-ART-10 | **CUMP** = somme des valeurs / somme des quantités des lots, sinon dernier coût unitaire ; un CUMP > 5 × prix de vente moyen est douteux et écarté des calculs. |
| RG-ART-11 | **Prix et marges** : prix proposé = coût / (1 − marge minimale) arrondi vers le haut (,49 / ,99) ; marge minimale unique pour le magasin (25 % par défaut) ; une hausse de plus de 30 % est « à vérifier ». |
| RG-ART-12 | **Promotion** : au premier jour, prix normal lu dans Clover puis prix promo appliqué ; à la fin, prix normal remis **seulement si le prix est encore le prix promo** ; deux promotions du même article ne se chevauchent pas. |
| RG-ART-13 | **Annuler une promotion** : prévue → annulée ; en cours → prix normal remis tout de suite (même condition que RG-ART-12) ; terminée ou annulée → refus. |
| RG-ART-14 | **Péremption** : rouge à un mois ou moins (ou périmé), jaune de 1 à 3 mois. |
| RG-ART-15 | Effacer une UGS qui n'est pas une date : liste à cocher, chaque effacement journalisé. |
| RG-ART-16 | **Prix de vente Sage depuis Clover** (« Articles > Prix de vente Sage depuis Clover ») : le prix de vente régulier de Sage prend le prix de l'article Clover relié (Confirmé ou Automatique) ; prix différent coché, plusieurs prix Clover sur un même n° Sage décochés (le plus élevé proposé), prix variable ou absent non cochable ; écrit dans la fiche de Sage (l'application ouvre Sage elle-même), vérifié, journalisé (`journal_prix_sage.csv`) ; droit « Changer les prix de vente dans Sage ». |

---

## 10. Stock

| Code | Règle |
|---|---|
| RG-STK-01 | **Tout document de stock part d'un dépôt** rattaché à un point de vente ; dépôt obligatoire. |
| RG-STK-02 | **Seules les factures touchent le stock** dans la chaîne des documents (devis, commandes, livraisons et réceptions ne le changent pas). |
| RG-STK-03 | Un document de stock passé met à jour **Sage puis Clover** ; un article relié à plusieurs articles Clover n'est pas touché dans Clover (à corriger à la main). |
| RG-STK-04 | **Annuler un document passé = document inverse** passé dans Sage et Clover ; l'original passe « Annulé » ; modifier = annuler + nouveau document. |
| RG-STK-05 | **Transfert** entre points de vente : deux dépôts différents, quantités > 0 ; Sage d'abord, puis Clover (départ −, arrivée +) ; un lot déjà dans Sage n'est jamais refait ; un stock négatif au départ est signalé. |
| RG-STK-06 | **Inventaire** : stocks relus juste avant la saisie ; Clover = quantité comptée ; Sage = somme des quantités comptées de son n° ; entrée au CUMP (sinon coût Clover, signalé) ; écart recalculé avant chaque lot pour reprendre sans double compte. |
| RG-STK-07 | **Inventaire tournant** : les catégories sont réparties sur le cycle (8 semaines par défaut) ; la semaine ISO donne les catégories à compter. |
| RG-STK-08 | **Perte** : coût = CUMP Sage de l'article relié, sinon coût Clover, sinon inconnu (valeur 0, signalé) ; motif obligatoire ; sortie de stock Sage puis Clover, une seule fois ; une perte annulée sort du rapport. |
| RG-STK-09 | **Taux de perte** = pertes au coût / ventes nettes Clover de la période. |
| RG-STK-10 | **Livre d'inventaire** à une date = stock actuel − mouvements postérieurs, valorisé au CUMP actuel ; pour des dépôts choisis : stock de ces dépôts moins leurs mouvements postérieurs, transferts compris. |
| RG-STK-11 | **Type d'un mouvement de Sage** : dans le journal des ajustements, seul l'indicateur de transfert de Sage dit qu'il s'agit d'un transfert ; les autres sont des entrées / sorties d'un dépôt ; une écriture sans quantité (écart de coût après une vente) n'est pas un document. |
| RG-STK-12 | **Documents de stock imprimés** : « Mouvement d'entrée » (Reçu par / Vérifié par), « Mouvement de sortie » (motif, Sorti par / Approuvé par), « Bon de transfert » (quantité reçue et observation à remplir, Expédié par / Reçu par), « Écart d'inventaire » (théorique, compté, écart, valeur, en plus / en moins / net, Compté par / Approuvé par) ; coût « CUMP » quand il est celui de Sage. |

---

## 11. Documents de vente et d'achat

| Code | Règle |
|---|---|
| RG-DOC-01 | Chaîne de vente : devis → commande → préparation / livraison → facture ; retour client → facture de retour (FRC). Chaîne d'achat : demande de prix → bon de commande → réception → facture ; retour → facture de retour (FRT). |
| RG-DOC-02 | **Transformer** reprend les lignes, le tiers et le dépôt ; l'original passe « Transformé » ; une facture garde son état. |
| RG-DOC-03 | Les commandes clients restent dans l'application (la fonction Commandes clients n'est pas activée dans Sage) ; « Facturer la commande » produit la facture. |
| RG-DOC-04 | Facture de vente et facture de retour client importées dans Sage ; la facture de retour a des quantités et montants négatifs. |
| RG-DOC-05 | Un document déjà dans Sage ou déjà facturé ne se modifie ni ne se supprime dans l'application ; supprimer une facture de l'application rouvre sa commande. |
| RG-DOC-07 | **Un modèle d'impression par type** : les documents de préparation, de livraison, de retour client, de réception et de retour fournisseur s'impriment **sans prix** (colonnes à remplir, signatures) ; les autres avec prix et taxes, et leurs mentions (devis valable 30 jours…). Le bon de livraison est un document de vente, le bon de réception un document d'achat. |
| RG-DOC-06 | Clients et fournisseurs se **créent** depuis l'application (fiche Sage remplie et vérifiée) ; un n° de taxe hors format n'est jamais forcé. |

---

## 12. Comptabilité

| Code | Règle |
|---|---|
| RG-CPT-01 | **Contrôle de la caisse** : attendu = fond du matin + paiements en espèces − remboursements en espèces − remises en argent sur carte ; écart = compté − attendu ; seuil d'alerte 5 $ ; à déposer = compté − fond laissé. |
| RG-CPT-02 | Fond du matin = fond laissé au dernier comptage, sinon le fond configuré. Un recomptage garde l'ancien comptage dans l'historique. |
| RG-CPT-03 | **Dépense** : TTC ventilé en HT, TPS 5 %, TVQ 9,975 % selon le code de taxe, l'arrondi va à la TVQ ; payée par petite caisse, carte de crédit ou employé à rembourser ; écriture de journal général « Dépense DP-nnnn », une seule fois. |
| RG-CPT-04 | Les comptes de taxe d'une dépense sont ceux de Sage pour la TPS / TVQ payées ; un compte de taxe qui n'en est pas un bloque la saisie. |
| RG-CPT-05 | **Âge des comptes** : échéance = date + délai de paiement de la fiche ; tranches courant / 30 / 60 / 90 jours et plus. |
| RG-CPT-06 | **Déclaration TPS/TVQ** : taxes perçues − taxes payées ± régularisations, contrôlées contre les taxes Clover. |
| RG-CPT-07 | **Prévision de trésorerie** sur 4 semaines : solde du compte de dépôt + encaissements attendus − factures fournisseurs à échéance. |
| RG-CPT-08 | **Budget** : réel = état des résultats de Sage ; écart et cumul depuis janvier ; proposition = an dernier × (1 + croissance). |
| RG-CPT-09 | **Clôture du mois** : contrôles (factures non encaissées, relevés non rapprochés, documents non passés) et état des résultats comparé au mois précédent et au même mois de l'an dernier. |
| RG-CPT-10 | **Plan comptable** : seuls les comptes de groupe et de sous-groupe reçoivent des écritures ; création, modification, inactivation et suppression vérifiées dans Sage. |
| RG-CPT-11 | **Espèces attendues** : seuls les paiements en espèces **réussis** comptent ; le jour est celui du paiement au fuseau de Clover ; un pourboire en espèces est attendu dans le tiroir. |
| RG-CPT-12 | **À déposer** = compté − fond laissé pour le lendemain ; l'écart cumulé des dépôts d'espèces se lit contre les dépôts au guichet du relevé. |
| RG-CPT-13 | **Écriture de dépense** : la ligne au **crédit** (moyen de paiement) est saisie en premier, Sage propose ensuite le reste au débit ; source « Dépense DP-nnnn », vérifiée par source et date, jamais deux fois. |
| RG-CPT-14 | Les calculs lourds de la comptabilité (TPS/TVQ, trésorerie, retenues, suivi des remises, clôture) ne se lancent que sur demande (« Calculer », « Vérifier ») ; le mois terminé est proposé par défaut pour les retenues et la clôture. |

---

## 13. Paie

| Code | Règle |
|---|---|
| RG-PAI-00 | **Pointage seulement au magasin** : depuis un poste du magasin listé, ou un appareil connecté au **Wi-Fi du magasin** (réseau lu dans Tailscale, comparé aux adresses publiques du magasin) ; ailleurs, le pointage est refusé avec le nom du Wi-Fi à utiliser. |
| RG-PAI-00b | **Pause automatique hors du Wi-Fi** : un employé qui a pointé depuis son téléphone et dont le téléphone quitte le Wi-Fi du magasin **5 minutes de suite** (réglable, 0 = jamais) est mis en pause à l'heure où il est parti ; la pause se termine quand le téléphone revient sur le Wi-Fi. Ces pointages portent l'auteur « Automatique » et leur motif ; une pause pointée par l'employé n'est jamais terminée par l'application. |
| RG-PAI-00c | **Administrateur** (règle du propriétaire du 2026-11-08) : la restriction au Wi-Fi du magasin ne vaut que pour les profils autres qu'Administrateur ; un administrateur ouvre le pointage de partout. Un pointage fait hors du Wi-Fi du magasin ne lance jamais le suivi de la pause automatique, et arrête un suivi en cours de cet employé. |
| RG-PAI-01 | **Pointage par NIP** (4 à 6 chiffres, unique) ; 5 essais faux = 1 minute de blocage ; le NIP n'est gardé que sous forme d'empreinte. |
| RG-PAI-02 | Un pointage n'est **jamais effacé** : une correction est un nouveau pointage ou une annulation, avec auteur et motif obligatoires. |
| RG-PAI-03 | **Présence** = arrivée … départ − pauses pointées (non payées), comptée au jour de l'arrivée ; un départ pendant une pause termine la pause. |
| RG-PAI-04 | **Heures supplémentaires** au-delà de 40 heures par semaine (dimanche-samedi). |
| RG-PAI-05 | **Paie aux 2 semaines** ; période de 14 jours à partir de la référence ; une paie n'est jamais dans le futur (période terminée, chèques datés d'aujourd'hui au plus tard). |
| RG-PAI-06b | **Les feuilles de temps sont approuvées par le gérant seulement** (pas d'approbation par l'employé), aux deux semaines ; le « Suivi des périodes » montre les 12 dernières périodes et la période en cours ; une période terminée non approuvée est rappelée au courriel du matin. |
| RG-PAI-06 | Une feuille avec anomalie (départ manquant, pause non terminée, pointage sans arrivée) **ne s'approuve pas** ; une feuille changée après approbation revient « À approuver ». |
| RG-PAI-07 | **Le calcul de la paie est fait par Sage Paie** : l'application envoie les heures approuvées (normales, supplémentaires, fériés, congés payés) ; une paie n'est jamais envoyée deux fois pour le même employé et la même période. |
| RG-PAI-08 | **Dépôt salaire Desjardins** : tous les chèques d'une paie portent le n° « PAYjjmmaaaa » de la date des chèques. |
| RG-PAI-09 | **Jour férié** : indemnité = 1/20 des heures normales (40 h au plus par semaine) des 4 semaines complètes avant la semaine du férié ; Vendredi saint ou lundi de Pâques au choix ; 24 juin et 1er juillet reportés au lundi s'ils tombent un dimanche. |
| RG-PAI-10 | **Vacances** : 2 semaines / 4 % avant 3 ans de service, 3 semaines / 6 % ensuite (année du 1er mai au 30 avril) ; **maladie ou famille** : 2 jours payés après 3 mois, 10 jours au total. |
| RG-PAI-11 | **Retenues à remettre** : retenues et cotisations du mois, échéance le 15 du mois suivant ; « Remis à temps », « Remis en retard », « À remettre », « EN RETARD » ; les vacances à payer ne se remettent pas. |
| RG-PAI-12 | **Bulletin de paie et T4 / RL-1** : chaque employé reçoit **son** document, à un seul destinataire visible ; un renvoi est signalé avant confirmation ; T4 et RL-1 sur les formulaires officiels, NAS jamais écrit. |
| RG-PAI-13 | **Relevé d'emploi** : heures assurables des 53 dernières semaines (présences pointées), rémunération assurable des 27 dernières paies ; l'employé peut ensuite être désactivé. |
| RG-PAI-14 | **Coût de la main-d'œuvre** = heures × taux moyen × (1 + charges sociales), comparé aux ventes du jour ; aucun taux individuel gardé. |
| RG-PAI-15 | Un employé créé dans l'application est créé **d'abord dans Clover**, puis relié ; Clover refuse → création dans l'application seulement si la personne accepte. |
| RG-PAI-17 | **Une cédule par dépôt** : chaque employé a un dépôt principal ; un quart sans dépôt est au dépôt principal ; les heures d'un jour comptent au dépôt du quart du jour, sinon au dépôt principal. |
| RG-PAI-16 | Un profil limité (employé) ne voit **que ses propres** heures, horaire, paies et feuillets. |

---

## 14. Statistiques, rapports et analyses

| Code | Règle |
|---|---|
| RG-STA-01 | Les statistiques suivent **les mêmes règles que la facturation** (RG-VEN-01 à 03) : leurs ventes nettes égalent les factures. |
| RG-STA-02 | Comparaison par défaut : un jour → même jour de la semaine précédente ; sinon période précédente de même durée, ou l'an dernier. |
| RG-STA-03 | **Bénéfice** = ventes nettes − quantité × CUMP Sage de l'article relié ; marge = bénéfice / ventes ; un CUMP douteux est écarté. |
| RG-STA-04 | **Articles 20/80** : classe A = les 20 % d'articles qui vendent le plus, B jusqu'à 50 %, C le reste ; couverture = stock / vente moyenne par jour. |
| RG-STA-05 | **Produits inactifs** : aucune vente depuis le seuil choisi (30 à 365 jours) ; tri par valeur du stock puis temps sans vente ; un article absent du catalogue est écarté. |
| RG-STA-06 | **Prévision des ventes** = moyenne du même jour de semaine sur 4 semaines × tendance des 4 dernières semaines (bornée de 0,8 à 1,2). |
| RG-STA-07 | **Articles à commander** : stock − vendu sur l'horizon ≤ 0 ; un stock négatif compte pour 0 dans la quantité suggérée. |
| RG-STA-08 | **Résumé du matin** (courriel) : ventes d'hier comparées au même jour la semaine passée, marge, solde bancaire, factures à payer d'ici 7 jours, ruptures des articles A, péremption, alertes (retenues, caisse non comptée ou écart > 5 $) ; chaque partie est indépendante. |
| RG-STA-09 | Les paiements par carte ne gardent que le type de carte et le mode de saisie, **jamais les chiffres de la carte**. |
| RG-STA-10 | Un jour **terminé** lu dans Clover est gardé et n'est plus relu ; la journée en cours est relue (chaque minute si demandé, sinon toutes les 5 minutes). |
| RG-STA-11 | **Filtres** : client et employé gardent les commandes entières ; article et catégorie gardent seulement leurs lignes ; les paiements sont comptés pour la part des lignes gardées ; « Mode de paiement » garde les commandes payées au moins en partie ainsi, avec ces paiements seulement. |
| RG-STA-12 | **Axe des graphiques** : 5 % au-dessus de la plus grande valeur, 4 graduations rondes (paliers 1, 1,2, 1,5, 2, 2,5, 3, 4, 5, 6, 8) ; moyenne en pointillé rouge ; valeurs écrites sur les barres s'il y en a 14 au plus. |
| RG-STA-13 | **Rapport des ventes** : brutes, rabais, remboursements, nettes, taxes, pourboires, perçu, par jour ou par heure ; les articles supprimés et les cartes-cadeaux, absents de l'API Clover, ne figurent pas. |
| RG-STA-14 | **Analyses décisionnelles** : rangées dans les rubriques existantes, jamais en double d'un état déjà présent ; calculées sur les ventes déjà lues de la période et de sa comparaison, filtres globaux appliqués, sans relire Clover. |
| RG-STA-15 | **Variation** : écart = effet nombre de commandes ((commandes − commandes d'avant) × panier d'avant) + effet panier ((panier − panier d'avant) × commandes). |
| RG-STA-16 | **Anomalies** : jour atypique à 2 écarts-types ou plus de la moyenne du même jour de la semaine (4 semaines au moins, journée en cours exclue) ; commande au-delà de Q3 + 3 × l'écart interquartile et du 99e centile ; rabais de 50 % ou plus ; prix à 40 % ou plus du prix médian de l'article (5 ventes au moins) ; une commande à 100 % de rabais n'est notée qu'une fois. |
| RG-STA-17 | **Matrice des articles** : populaire = part des quantités ≥ 70 % de la part égale ; rentable = bénéfice par unité (CUMP Sage, CUMP aberrant écarté) ≥ moyenne pondérée ; classes 20/80 comme l'onglet Articles 20/80 ; régularité X (coefficient de variation ≤ 0,5), Y (≤ 1), Z, mesurée par semaine dès 4 semaines. |
| RG-STA-18 | **RFM** : notes de 1 à 5 par quintile parmi les clients identifiés, valeurs égales = même note ; segments d'après la récence et la fréquence. **Fidélité** : retenu = client des deux périodes, nouveau = de la période seulement, perdu = de la comparaison seulement. |
| RG-STA-19 | **Prix et sensibilité** : changement de prix = prix unitaire brut du jour à 3 % ou plus du prix des 14 jours de vente d'avant, 80 % des jours avant et après à 2 % de leur prix ; au moins 5 jours de vente de chaque côté et 20 unités en tout ; comparaison sur le même nombre de jours d'ouverture (28 au plus) ; élasticité = variation des quantités % / variation du prix %. |
| RG-STA-20 | **Cohortes** : client identifié rangé au mois de son premier achat dans la période et sa comparaison ; « Mois +k » = part de la cohorte qui achète k mois plus tard. **Synthèse et décisions** : décisions proposées d'après les résultats des analyses (baisse des ventes de plus de 5 %, rabais de 50 % et plus, employés au-delà du double du taux moyen de rabais, locomotives, rétention sous 30 %, ventes rattachées à un client sous 30 %, paniers d'un seul article à 30 % ou plus…), triées par priorité ; une analyse en échec n'empêche pas les autres. Couleurs : rouge à agir, orange à surveiller, vert bon, gris information ; même feu sur les cartes (`etat_carte`). |
| RG-STA-21 | **Facture d'une commande** : le n° d'une commande Clover (anomalies, Commandes, Transactions, Remboursements) ouvre sa facture relue dans Clover au moment du clic (point de vente qui la connaît) ; lecture seule ; jamais les chiffres de la carte ; un login limité à un employé ne voit que ses commandes. N° retrouvé par (jour, n°), sinon par n° unique dans la période ou par la référence de commande d'un remboursement. |
| RG-STA-22 | **Décisions du courriel du matin** : synthèse des 28 derniers jours (jusqu'à hier) contre les 28 jours d'avant, sur les ventes Clover déjà lues par le résumé du matin ; coûts Sage gardés en mémoire (sans ouvrir Sage) ; au plus 8 décisions, de la priorité haute à la basse ; un échec est noté « Non calculé » sans empêcher le reste du courriel. |
| RG-STA-23 | **Éléments concernés par une décision** : chaque décision liste les éléments qui la déclenchent, du plus important au moins important (baisse : catégories puis articles par écart ; locomotives : ventes décroissantes ; poids morts : ventes croissantes ; paires : lift × commandes ; clients perdus : ventes de la comparaison) ; 50 au plus dans le tableau, la liste complète restant dans l'analyse ; une commande ouvre sa facture Clover. |
| RG-STA-24 | **Opérations journalières** : la liste vient de Sage (ventes tcustr, encaissements tcustrdt, achats et paiements tventrdt, écritures annulées exclues) ; « Traité le » vient des journaux de l'application (journal_imports.csv pour les ventes importées, journal_operations_traitees.csv écrit à chaque achat importé, encaissement et paiement vérifiés) ; une opération sans trace = saisie directement dans Sage. ◀ / ▶ : période précédente / suivante de même longueur (mois et années entiers gardés). |
| RG-STA-25 | **Récapitulatif des traitements** : chaque traitement est noté une seule fois à sa fin (début, fin, durée, origine Nuit / Application / Web, personne, résultat) ; un traitement lancé dans un autre n'est pas noté une 2e fois ; les traitements de nuit d'avant le registre sont repris du journal du traitement automatique ; le registre ne bloque jamais le travail. |
| RG-STA-26 | **Rabais Direction et administrateurs** (règle du propriétaire du 2026-11-08) : une commande dont un rabais (commande ou ligne) est nommé « Direction », ou enregistrée par un employé Clover au rôle ADMIN ou propriétaire, va dans l'état « Rabais Direction et administrateurs » ; elle n'est ni une anomalie « rabais de 50 % ou plus » ni « commande à 0 $ », son rabais ne compte pas dans le taux de rabais de l'employé (colonne à part) ni dans la décision « Encadrer les rabais accordés ». Rôles relus dans Clover au plus toutes les 6 heures. |
| RG-STA-27 | **Pont de marge** : bénéfice brut = ventes nettes − quantité nette × CUMP actuel de Sage (même coût pour les deux périodes ; CUMP absent ou de plus de 5 fois le prix : article écarté). Pour les articles vendus dans les deux périodes : effet prix = quantité d'aujourd'hui × variation du prix net moyen ; effet quantité = variation de quantité × bénéfice unitaire d'avant, partagé en effet volume (variation des quantités totales × bénéfice moyen d'avant) et effet mix (le reste). Les autres articles forment « articles nouveaux ou arrêtés ». Marge en baisse de plus d'un point : décision « Protéger la marge brute » (priorité 1). |
| RG-STA-28 | **Portefeuille des catégories** : part forte = au moins la part moyenne (100 % / nombre de catégories vendues) ; croissance forte = au moins la croissance du magasin (catégorie absente de la comparaison : en croissance). Étoile = forte et en croissance ; vache à lait = forte, croissance faible ; prometteuse = petite, en croissance ; en recul = petite, croissance faible. |
| RG-STA-29 | **Achalandage et effectifs** : créneau = jour de la semaine × heure ; commandes par jour = commandes du créneau / jours ouverts de ce jour de la semaine ; employé actif = employé qui a enregistré une vente dans l'heure. Sous tension : au moins 1,5 fois la charge médiane par employé et dans le quart des créneaux les plus achalandés (8 créneaux au moins) ; calme : 1,5 employé actif ou plus et charge dans le quart le plus bas. |
| RG-STA-30 | **Rythme et objectif** : une période qui s'arrête aujourd'hui vise sa fin naturelle (mois, semaine lundi → dimanche, année). Objectif = budget des ventes (poste « Produits (ventes) ») au prorata des jours de chaque mois ; sans budget, somme sur la période des ventes moyennes de chaque jour de la semaine dans la comparaison. Projection = réalisé des journées terminées + pour chaque jour restant la moyenne du même jour de la semaine déjà vu dans la période (sinon dans la comparaison), la journée en cours comptant au moins ce qui est vendu. À faire par jour = (objectif − réalisé des journées terminées) / jours restants. Projection sous 95 % : décision « Rattraper l'objectif de la période » (priorité 1). |
| RG-STA-31 | **Heures d'ouverture peu achalandées** : pour chaque jour de la semaine ouvert au moins 4 heures, la première et la dernière heure dont les ventes moyennes sont sous le quart d'une heure moyenne de ce jour sont signalées (décision de priorité 3). |
| RG-STA-32 | **Remboursements à surveiller** : remboursé = ventes brutes nettes de rabais des lignes remboursées dans Clover ; part = remboursé / ventes brutes ; un employé (3 commandes remboursées au moins) qui rembourse plus du double de la moyenne est signalé ; décision quand la part dépasse 2 % et 1,5 fois celle de la période d'avant. |
| RG-STA-33 | **Espèces et cartes** : une commande est « Espèces » si tous ses paiements sont en espèces, « Espèces et carte » si une partie l'est, sinon « Carte ou autre » ; montants = montant encaissé (pourboires exclus). |
| RG-STA-34 | **Nouveaux articles** : vendu dans la période mais pas dans la période d'avant (si celle-ci a moins du quart des jours de vente : pas vendu pendant les 4 premières semaines de la période) ; ventes par jour depuis la première vente comparées à la médiane des autres articles : bon départ (au moins autant), lent (moins du quart). |
| RG-STA-35 | **Jours fériés** : jours fériés du Québec (Vendredi saint et lundi de Pâques compris) ; jour normal = moyenne des jours ouverts du même jour de la semaine hors jours fériés et veilles, période et période d'avant ; décision quand la veille vend en moyenne 20 % de plus et qu'un jour férié est à venir. |
| RG-STA-36 | **Articles qui baissent** : blocs de 7 jours comptés depuis la fin de la période (4 au moins) ; articles parmi les 20 % qui vendent le plus, vendus au moins chaque semaine sauf une et 25 $ par semaine en moyenne ; baisse = pente de la droite des ventes hebdomadaires ≤ −5 % de la moyenne (forte : ≤ −15 %, décision de priorité 2). |
| RG-STA-37 | **Seuil de rentabilité** : ventes nécessaires par mois = « Autres charges » du budget / marge brute réelle (coût moyen de Sage) ; par jour = / jours ouverts par mois ; décision de priorité 1 quand la moyenne par jour ouvert est sous le seuil. |
| RG-STA-38 | **Prévisions de la semaine** : moyenne du même jour de la semaine (et de la même heure) sur les 4 semaines qui finissent avec la période ; employés conseillés = commandes prévues / médiane des commandes par employé actif et par heure, arrondi au-dessus. |
| RG-STA-39 | **Ventes selon le jour du mois** : indice d'un jour = ses ventes / ventes moyennes du même jour de la semaine (période choisie et période d'avant réunies) × 100 ; moyenne par tranche (1-5, 6-10, 11-15, 16-20, 21-25, 26 à la fin) ; décision de priorité 3 quand la meilleure tranche dépasse 110 sur 40 jours ou plus. |
| RG-STA-40 | **Articles de saison** : mois d'au moins 20 jours ouverts ; articles qui font la première moitié des ventes ; indice de saison = ventes par jour du meilleur mois / moyenne des mois × 100 ; « Article de saison » si l'indice atteint 150, l'article est vendu au moins 3 mois sur 4 et fait 10 $ par jour au meilleur mois (3 mois au moins) ; décision de priorité 2 pour ceux dont le meilleur mois est le mois qui suit aujourd'hui. |
| RG-STA-41 | **Ventes au poids** : article vendu au moins une fois en quantité non entière ; prix moyen au poids = ventes nettes / quantité ; écart de prix de 10 % ou plus avec la période d'avant signalé (décision de priorité 3 pour les hausses : prix affiché et balance). |
| RG-STA-42 | **Ruptures probables** : article parmi ceux qui font la moitié des ventes, vendu au moins 7 jours ouverts sur 10 depuis sa 1re vente de la période ; absence = jours ouverts de suite sans vente dont le risque par hasard est sous 2 % ((1 − présence)^jours < 0,02, 3 jours au moins) ; journée en cours exclue ; ventes perdues estimées = jours d'absence × ventes moyennes d'un jour ouvert hors absence ; absence qui dure encore = décision de priorité 1 (vérifier le stock, commander). |
| RG-STA-43 | **Articles d'appel** : parmi les 20 % d'articles présents dans le plus de commandes (30 au moins), 20 commandes et 1 $ par commande au moins (sacs, consignes écartés) ; article d'appel = autres achats de ses commandes >= 1,75 × panier moyen et acheté seul moins de 15 % du temps ; achat rapide = acheté seul 40 % du temps ou plus ; article d'appel en rupture en cours = décision de priorité 1. |
| RG-STA-44 | **Ventes complémentaires manquées** : complément habituel d'un article = article pris dans au moins 30 % de ses commandes, 2 fois plus que le hasard, au moins 10 à 25 commandes ensemble (0,2 % des commandes, plafonné à 25) ; consignes et sacs (moins de 1 $ par commande) écartés ; gain possible = commandes sans le complément × prix moyen du complément / 4 ; décision de priorité 3 au-delà de 100 $. |
| RG-STA-45 | **Prix selon le format** : format lu dans le nom (« 1kg », « 500g », « 2,26kg », « 6x330ml », lb = 453,592 g) ; même produit = nom sans le format, sans accents ni ponctuation ; prix moyen affiché = ventes avant rabais / quantité (3 unités vendues au moins) ; prix au kg ou au litre ; un format plus grand plus cher de plus de 2 % au kg qu'un format plus petit = à vérifier (décision de priorité 2). |
| RG-STA-46 | **États enrichis** : les 18 états de base des statistiques (Rapport des ventes, Par jour, Par jour de la semaine, Par heure, Jour × heure, Par employé, Par article, Par catégorie, Bénéfices, Modes de paiement, Types de carte, Saisie des cartes, Appareils, Clients, Rabais, Commandes, Transactions, Remboursements) ont des cartes, des constats et des graphiques de plus calculés sur leur propre tableau et le même état de la période de comparaison (rien n'est relu dans Clover) ; sous-pages Résumé / Graphiques / Détail (Windows et web) ; chercher ou « Détail par jour » ouvre le Détail ; variation de 5 % ou plus signalée (hausse bonne, sauf rabais) ; « Sans client » écarté des clients ; heure ou jour le plus faible parmi ceux qui font 1 % des ventes ou plus. |

---

## 15. Points de vente

| Code | Règle |
|---|---|
| RG-PDV-01 | **Chaque point de vente = un dépôt Sage, un client Sage, un préfixe de facture** ; mêmes comptes de produits ; dépôts bancaires dans le même compte. |
| RG-PDV-02 | **Une facture par point de vente et par jour** (même règle de fin de semaine). |
| RG-PDV-03 | La facture d'un point de vente dont le dépôt n'est pas l'emplacement par défaut s'importe puis se transfère dans ce dépôt ; seul un dépôt absent de Sage bloque l'import. |
| RG-PDV-04 | Espèces, Interac et dépôts manuels des relevés : point de vente n° 1 seulement. |
| RG-PDV-05 | Un profil peut être limité à certains points de vente. |
| RG-PDV-06 | Le **suivi des ventes** couvre tous les points de vente visibles (colonne et filtre Dépôt) ; les **rapports de gestion** des statistiques suivent le filtre « Point de vente » (caisse : tiroir du point de vente s'il est seul choisi). |

### 15.1 Dépôts

| Code | Règle |
|---|---|
| RG-DEP-01 | **Dépôts** = emplacements de Sage : ceux des points de vente, l'« Emplacement par défaut » et les dépôts sans Clover réglés dans « Administration > Sage 50 ». Le dépôt principal est l'emplacement par défaut. |
| RG-DEP-02 | **Import puis transfert** : une facture s'importe dans l'emplacement par défaut puis un transfert « DP <n° de facture> » la place dans son dépôt (vente, facture de retour client, retour fournisseur : du dépôt vers le défaut ; achat : du défaut vers le dépôt ; quantité négative = autre sens) ; jamais refait ; un échec du transfert laisse la facture importée et le signale « à refaire ». |
| RG-DEP-03 | Clover n'est touché que pour un dépôt qui a un point de vente. |
| RG-DEP-04 | **Filtre Dépôt** : un, plusieurs ou tous les dépôts (« Tout sélectionner ») ; aucun dépôt choisi = tous. |

---

## 16. Utilisateurs, droits et sécurité

| Code | Règle |
|---|---|
| RG-SEC-01 | **Toujours au moins un administrateur actif** ; l'administrateur voit tout et gère les utilisateurs. |
| RG-SEC-01b | **Activer / désactiver un compte** (« Administration > Utilisateurs ») : un compte désactivé ne se connecte plus, ni à l'application Windows ni à l'application web ; ses sessions web se ferment et une fenêtre Windows ouverte avec ce compte se verrouille dans les 10 secondes ; jamais son propre compte, toujours un administrateur actif ; chaque changement est noté (journal des connexions, audit). |
| RG-SEC-02b | **Mot de passe web à part** : l'application web a son propre mot de passe, d'au moins **12 caractères avec une minuscule, une majuscule, un chiffre et un caractère spécial**, différent de celui de l'application Windows ; à la 1re connexion web (avec le mot de passe Windows), il est créé avant toute autre page ; ensuite seul lui ouvre l'application web ; l'administrateur peut le définir ou l'effacer (colonne « Mot de passe web » d'« Administration > Utilisateurs »). |
| RG-SEC-02 | Mot de passe gardé sous forme d'empreinte salée, jamais en clair. |
| RG-SEC-03 | **3 mots de passe faux de suite = compte verrouillé** ; l'administrateur le rouvre avec un nouveau mot de passe ; le dernier administrateur n'est que bloqué 15 minutes. |
| RG-SEC-04 | **Verrouillage après 5 minutes sans activité** ; **le traitement en cours continue** et, au déverrouillage, tout revient **où l'on en était** (fenêtre principale et fenêtres à part cachées puis remontrées, rien n'est fermé ; demande du propriétaire du 6 novembre 2026). |
| RG-SEC-05 | **Droits par fonction** : chaque entrée du menu est cochée ou non pour le profil ; une page non permise est absente du menu et refusée. |
| RG-SEC-06 | **Droits par action** dans les fenêtres (supprimer, exporter, saisir dans Sage, changer les prix, modifier les articles, traiter la paie…) donnés séparément. |
| RG-SEC-04c | **Application web : la reconnexion reprend à la page où l'on était** (adresse de retour gardée par la page qui expire et par la redirection vers la connexion ; seulement une adresse du site) ; les travaux en cours (« Encaisser dans Sage »…) continuent sur le serveur et se retrouvent après la reconnexion. |
| RG-SEC-07 | Le profil Employé **n'exporte pas** par défaut. |
| RG-SEC-04b | **Application web : déconnexion après 5 minutes sans activité** ; la page passe d'elle-même à la connexion. |
| RG-SEC-08 | **Audit** : chaque bouton cliqué, entrée du menu, connexion et refus est noté (moment, poste, utilisateur, fenêtre, action) ; chaque ligne porte l'empreinte de la précédente : une ligne changée est repérée ; jamais de mot de passe ni de NAS. |
| RG-SEC-09 | Une entrée du menu renommée garde le droit donné sous son ancien nom (exemple : l'ancienne entrée RIA de Comptabilité donne accès aux trois entrées RIA). |

---

## 17. Courriels

| Code | Règle |
|---|---|
| RG-COU-01 | Les boîtes de réception sont lues **en lecture seule** : aucun message n'est marqué comme lu ni déplacé. |
| RG-COU-02 | Un message déjà lu (identifiant connu) n'est jamais retéléchargé. |
| RG-COU-03 | Un document personnel (bulletin, T4 / RL-1, relance client) part à **un seul destinataire visible** ; une copie cachée va au propriétaire ; jamais pour les comptes rendus du traitement de nuit. |
| RG-COU-04 | L'envoi est **réessayé 3 fois** si le serveur ne répond pas ; une erreur de mot de passe ou d'adresse ne l'est pas. |
| RG-COU-05 | Le compte rendu de nuit est envoyé avec une pièce jointe Excel par module. |

---

## 18. Traitement de nuit

Ordre des étapes :

1. Factures fournisseurs reçues par courriel, avis de paiement Interac, archivage des factures déjà dans Sage, import des factures prêtes.
2. États de compte RIA reçus, puis saisis dans Sage si les comptes sont renseignés.
3. Facturation des ventes : **tous les jours sans facture**, depuis la date de départ jusqu'à hier, **du plus ancien au plus récent** (les trous d'abord), par lots de 25 factures ; un jour bloqué n'arrête pas les autres.
4. Encaissement des dépôts des ventes importées pendant l'exécution.
5. Paiements fournisseurs confirmés.
6. Promotions du jour, statistiques préchauffées, résumé du matin, tableau du gérant.
7. Sauvegarde des données.

| Code | Règle |
|---|---|
| RG-NUI-01 | Un seul traitement à la fois (verrou). |
| RG-NUI-02 | Chaque étape est indépendante : un échec est noté au compte rendu et les étapes suivantes continuent. |
| RG-NUI-03 | La session Windows doit être ouverte (verrouillée possible). |
| RG-NUI-04 | **Jours à facturer** : tous les jours sans facture « Vente AAAA-MM-JJ » depuis la date de départ jusqu'à hier, du plus ancien au plus récent ; une facture de Sage dont la date n'est pas le dernier jour de son numéro est ignorée et signalée. |
| RG-NUI-05 | Un **jour bloqué** (ou toute sa fin de semaine) n'arrête pas les autres ; il est repris la nuit suivante. |
| RG-NUI-06 | Import par **lots** de 25 factures (un fichier et une ouverture de Sage par lot) ; durées de chaque lot notées au journal. |
| RG-NUI-07 | Le Sage gardé ouvert pour la journée est refermé avant la nuit (minuit) ; la nuit ouvre et ferme Sage pour chacun de ses travaux. |
| RG-NUI-08 | Le **compte rendu** part même si une étape a échoué ; il porte une pièce jointe Excel par module et les alertes en rouge. |

---

## 19. Sauvegarde

| Code | Règle |
|---|---|
| RG-SAV-01 | Archive des données et de la configuration, **vérifiée** (contenu et nombre de fichiers) avant d'être retenue. |
| RG-SAV-02 | Conservation : la dernière de chacun des 14 derniers jours, 8 dernières semaines et 12 derniers mois ; jamais la plus récente. |
| RG-SAV-03 | Une sauvegarde sur le même disque que l'application est signalée ; plus de 2 jours sans sauvegarde = alerte. |
| RG-SAV-04 | **Restaurer** sauvegarde d'abord l'état actuel. |

---

## 20. Exports et documents imprimés

| Code | Règle |
|---|---|
| RG-EXP-01 | Tout tableau s'exporte en Excel, CSV ou PDF, ou s'imprime, selon le droit d'exporter du profil. |
| RG-EXP-02 | En Excel, les montants sont des nombres ; codes et dates restent du texte. |
| RG-EXP-03 | En-tête des documents : logo et coordonnées de l'entreprise lus dans Clover. |
| RG-EXP-04 | Un PDF déjà ouvert dans le lecteur n'est pas écrasé : un nouveau nom est pris. |
| RG-EXP-05 | Les documents imprimés portent l'en-tête de l'entreprise, le filet vert / rouge / jaune, « page n / total », et les signatures prévues par leur modèle. |

## 21. Application web et déploiement

| Code | Règle |
|---|---|
| RG-WEB-01 | **L'application web est identique à l'application Windows** : mêmes entrées du menu, mêmes boutons au même endroit, mêmes calculs, mêmes droits ; seules diffèrent les contraintes du navigateur sans script (bouton « Afficher », dates, petites fenêtres ouvertes dans la page). |
| RG-WEB-02 | **Tout sur un même serveur** : Sage 50, MVOGMBI_Sync, son serveur web et le traitement de nuit (les saisies dans Sage exigent Sage sur la même machine). Depuis le 4 novembre 2026 : SERVDCSAGE. |
| RG-WEB-03 | **Aucune adresse écrite dans le programme** : le serveur (ordinateur, adresse Tailscale, adresse locale, nom tapé, port) se règle dans « Administration > Automatisation » ; le client des postes lit `serveur.json`. |
| RG-WEB-04 | Le serveur web n'écoute que sur la carte Tailscale (pare-feu) ; jamais ouvert sur Internet ni sur le réseau local. |
| RG-WEB-04b | **HTTPS sans port** : https://app.marchemvogmbi.com, port 443, certificat Let's Encrypt validé par le DNS chez WHC (`certificat_https.ps1`, win-acme) ; renouvelé tous les 60 jours, relu par le serveur sans redémarrage. |
| RG-WEB-05 | Sage ne répond pas : les pages s'affichent quand même, tableaux vides avec leurs colonnes, et un bandeau le signale. |
| RG-WEB-06 | Un seul travail dans Sage à la fois ; le jeton anti-falsification ne paraît jamais dans une adresse. |
| RG-WEB-08 | **Le client des postes ouvre directement l'application web** (Edge en mode application), même si le serveur ne répond pas encore ; la fenêtre de réglage seulement par le raccourci « adresse du serveur ». Installateur du client sans droits d'administrateur. |
| RG-WEB-09 | Le **serveur web** tourne sans fenêtre, une seule copie à la fois, démarré à l'ouverture de session. |
| RG-WEB-10 | Dans un tableau web, un texte de plus de 45 caractères est **coupé** (« … ») et se lit en entier au survol : les montants et les états d'une ligne restent toujours visibles ; une cellule avec un champ ou un bouton n'est jamais coupée. |
| RG-WEB-07 | Changer de serveur : reprendre `config.toml` et `donnees/`, retaper les mots de passe (coffre-fort propre à chaque machine), régler le serveur, relancer `installer_web.ps1` et la tâche planifiée ; retirer tâche et serveur web de l'ancien serveur (jamais deux traitements de nuit). |

---

## 22. Exemples chiffrés

Exemples **fictifs** qui montrent l'application des règles de bout en bout.

### 22.1 Facture d'une fin de semaine (RG-VEN-02, 04, 07)

Ventes Clover de l'article « Pomme rouge en lb » du vendredi au dimanche :

| Jour | Quantité | Ventes brutes | Rabais | Remboursements | Ventes nettes |
|---|---|---|---|---|---|
| Vendredi | 12,500 lb | 37,50 $ | −1,25 $ | 0,00 $ | 36,25 $ |
| Samedi | 20,000 lb | 60,00 $ | 0,00 $ | −3,00 $ (1 lb) | 57,00 $ |
| Dimanche | 8,250 lb | 24,75 $ | 0,00 $ | 0,00 $ | 24,75 $ |
| **Total** | **39,750 lb nets** | | | | **118,00 $** |

Une seule facture « Vente 2026-10-23/25 » datée du dimanche ; ligne de l'article : quantité 39,750, prix unitaire = 118,00 / 39,750 = **2,9686** $ (4 décimales), montant **118,00 $**. Le total de la facture égale les ventes nettes Clover des trois jours.

### 22.2 Encaissement d'un dépôt (RG-ENC-01, 02, 06)

Facture « Vente 2026-10-23/25 » : 3 000,00 $ TTC. Lot de cartes du vendredi 1 200,00 $, du samedi 900,00 $, du dimanche 500,00 $ ; espèces 400,00 $.

- Dépôt du lundi = 1 200,00 + 900,00 + 500,00 = **2 600,00 $** : un encaissement daté du lundi, une seule ligne sur la facture de fin de semaine.
- Solde dû après : 400,00 $ = les espèces.
- Mardi, dépôt d'espèces au guichet de 650,00 $ : 400,00 $ vont sur cette facture (la plus ancienne avec des espèces dues), 250,00 $ sur la facture suivante qui a encore des espèces dues ; s'il n'y en a plus, les 250,00 $ restent « Part RIA à confirmer ».

### 22.3 Ligne de facture fournisseur (RG-FRN-01)

Facture : 3 caisses de bananes à 24,00 $ la caisse ; une caisse = 18 kg (facteur 18) ; l'article Sage est vendu au kg.

- Montant = 3 × 24,00 = **72,00 $**
- Qté Sage = 3 × 18 = **54 kg**
- Prix Sage = 72,00 / 54 = **1,3333 $ / kg**
- Après l'import : stock Clover + 54, coût Clover = 1,3333 $.

### 22.4 Prix proposé (RG-ART-11)

Coût (CUMP) 2,10 $, marge minimale 25 % : 2,10 / (1 − 0,25) = 2,80 $ ; arrondi « ,49 / ,99 » vers le haut = **2,99 $**. Si 120 unités ont été vendues en 90 jours au prix actuel de 2,49 $, effet estimé = (2,99 − 2,49) × 120 = **60,00 $**.

### 22.5 Indemnité de jour férié (RG-PAI-09)

Heures normales des 4 semaines complètes avant la semaine du férié : 38, 40, 35 et 40 heures (une semaine de 44 h compte pour 40) = 153 heures. Indemnité = 153 / 20 = **7,65 heures**, payées en heures « Régulières ».

### 22.6 Heures supplémentaires (RG-PAI-03, 04)

Semaine du dimanche au samedi : 5 jours de 8 h 30 de présence avec 30 minutes de pause pointée chacun = 5 × 8 h = 40 h, plus un samedi de 6 h sans pause = **46 h** : 40 h normales, **6 h supplémentaires**.

### 22.7 Contrôle de la caisse (RG-CPT-01, 02)

Fond du matin 200,00 $ ; paiements en espèces 845,30 $ (pourboires compris) ; remboursement en espèces 12,00 $ ; retrait d'argent sur carte 40,00 $.

- Attendu = 200,00 + 845,30 − 12,00 − 40,00 = **993,30 $**
- Compté 988,05 $ : écart = **−5,25 $** → alerte (au-delà de 5 $).
- Fond laissé 200,00 $ : à déposer = 988,05 − 200,00 = **788,05 $**.

### 22.8 Articles 20/80 (RG-STA-04)

Catalogue de 1 000 articles vendus sur la période : les 200 articles qui vendent le plus (rang 1 à 200) sont la classe **A**, les rangs 201 à 500 la classe **B**, les 500 autres la classe **C**. Si les 200 articles A font 760 000 $ de ventes sur 1 000 000 $, le résumé affiche « les 20 % d'articles font 76 % des ventes ».

### 22.9 Dépense de petite caisse (RG-CPT-03, 13)

Reçu de 23,00 $ TTC avec TPS et TVQ (code GQ) : HT = 23,00 / 1,14975 = 20,00 $ ; TPS = 1,00 $ ; TVQ = 23,00 − 20,00 − 1,00 = 2,00 $ (l'arrondi va à la TVQ). Écriture : crédit petite caisse 23,00 $ (1re ligne), débit charge 20,00 $, débit TPS payée 1,00 $, débit TVQ payée 2,00 $.
