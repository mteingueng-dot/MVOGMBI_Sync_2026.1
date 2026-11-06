# MVOGMBI_Sync — Règles d'affaires

Version 1.0.2 (6 novembre 2026) — Marché MVOG-MBI Sherbrooke.

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
| RG-SAGE-10 | **Sage ouvert pour la journée** : au démarrage de l'application (serveur web ou fenêtre Windows), Sage s'ouvre en **multi-utilisateur** (les employés travaillent en même temps, chacun dans sa session Bureau à distance) et reste ouvert jusqu'à la fermeture de l'application ; les saisies l'utilisent tel quel. L'import (mono-utilisateur), la nuit (0 h - 6 h) et le traitement de nuit le referment d'abord, comme avant ; il se rouvre ensuite de lui-même. Un seul Sage gardé par serveur ; `[sage] garder_ouvert = false` revient à l'ancien fonctionnement. |
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
| RG-RIA-01 | **Envoi reçu en espèces** (« MT Send ») : débit espèces / crédit compte RIA (dû à RIA). |
| RG-RIA-02 | **Versement ou remboursement payé en espèces** (« MT Payout », « MT Refund ») : débit compte RIA / crédit espèces. |
| RG-RIA-03 | Un versement **payé par virement Interac** (même montant au relevé de banque, à 3 jours près) n'a pas d'écriture d'état : la banque l'a déjà. |
| RG-RIA-04 | Règlements de RIA (ACH) et dépôts : mouvements de **banque**, traités par le rapprochement. |
| RG-RIA-05 | **Surplus d'un dépôt d'espèces** au-delà des ventes : part RIA à confirmer ; quand les états RIA sont traités, le surplus va aux espèces. |
| RG-RIA-06 | **Commission** : le dépôt égal à la commission payée de l'état (dans les 12 jours) est marqué « Commission » d'office. |
| RG-RIA-07 | Chaque ligne d'état devient une opération **une seule fois** (clé : agence, date, référence, activité) ; sous-totaux et totaux ignorés ; une ligne répétée sur plusieurs pages n'est comptée qu'une fois. |
| RG-RIA-08 | Chaque état est **recontrôlé** : solde courant recalculé ligne par ligne, totaux des débits et crédits contre le résumé ; un écart est noté en remarque. |
| RG-RIA-09 | Rien n'est saisi dans Sage tant que les **comptes RIA, commissions et espèces** ne sont pas renseignés (Comptabilité > Comptes RIA). |
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

---

## 13. Paie

| Code | Règle |
|---|---|
| RG-PAI-00 | **Pointage seulement au magasin** : depuis un poste du magasin listé, ou un appareil connecté au **Wi-Fi du magasin** (réseau lu dans Tailscale, comparé aux adresses publiques du magasin) ; ailleurs, le pointage est refusé avec le nom du Wi-Fi à utiliser. |
| RG-PAI-00b | **Pause automatique hors du Wi-Fi** : un employé qui a pointé depuis son téléphone et dont le téléphone quitte le Wi-Fi du magasin **5 minutes de suite** (réglable, 0 = jamais) est mis en pause à l'heure où il est parti ; la pause se termine quand le téléphone revient sur le Wi-Fi. Ces pointages portent l'auteur « Automatique » et leur motif ; une pause pointée par l'employé n'est jamais terminée par l'application. |
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
| RG-SEC-04 | **Verrouillage après 5 minutes sans activité** ; les traitements en cours continuent. |
| RG-SEC-05 | **Droits par fonction** : chaque entrée du menu est cochée ou non pour le profil ; une page non permise est absente du menu et refusée. |
| RG-SEC-06 | **Droits par action** dans les fenêtres (supprimer, exporter, saisir dans Sage, changer les prix, modifier les articles, traiter la paie…) donnés séparément. |
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
| RG-WEB-07 | Changer de serveur : reprendre `config.toml` et `donnees/`, retaper les mots de passe (coffre-fort propre à chaque machine), régler le serveur, relancer `installer_web.ps1` et la tâche planifiée ; retirer tâche et serveur web de l'ancien serveur (jamais deux traitements de nuit). |
