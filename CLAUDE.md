# MVOGMBI_Sync_2026.1

Application Python (3.13) qui récupère les ventes Clover (API REST v3 ou export Excel « Ventes d'articles ») et prépare leur import dans Sage 50 Comptabilité Édition canadienne 2026.2 sous forme de facture de vente au client « Vente hebdomadaire », une ligne par article, cumulée sur un jour, une semaine (lundi → dimanche) ou un mois.

Projet sans aucun lien avec le site conceptinformatique. L'utilisateur, propriétaire du Marché MVOG-MBI Sherbrooke, communique en français : répondre et nommer le code en français.

## Commandes

- `python -m pytest` : tests
- `python -m mvogmbi_sync rapport --periode jour|semaine|mois --date AAAA-MM-JJ [--par-jour] [--export fichier.xlsx]`

## Structure

- `mvogmbi_sync/models.py` : `LigneVente`, `RapportVentes`, `cumuler()` ; montants en `Decimal`, rabais et remboursements négatifs comme dans Clover. Ventes nettes = brutes + rabais + remboursements.
- `mvogmbi_sync/periodes.py` : bornes des périodes et conversion en millisecondes (fuseau America/Toronto).
- `mvogmbi_sync/export_clover.py` : lecture de l'export Excel Clover (montants au format « 1 234,56 $ »).
- `mvogmbi_sync/api_clover.py` : client API Clover et transformation des commandes en lignes (prix en cents, `unitQty` en millièmes, rabais de commande répartis au prorata).
- `mvogmbi_sync/facture.py` : lignes de la facture Sage (quantité nette au millième, prix à 4 décimales, montant = net) et anomalies.
- `mvogmbi_sync/sortie_excel.py` : rapport Excel de vérification dans `sortie/`.

## Points d'attention

- **Règle de facturation (fixée par le propriétaire)** : montant de ligne = ventes nettes Clover de l'article ; prix unitaire = ventes nettes / quantité nette (4 décimales) ; total facture = ventes nettes Clover. Voir `mvogmbi_sync/facture.py`.
- Facture générée : client « Vente Hebdomadaire », mode « Payer plus tard » (dépôts appliqués ensuite), code de taxe « GQ » (TPS 5 % + TVQ 9,975 %) pour les lignes taxées dans Clover (`lineItems.taxRates`), datée du dernier jour de la période, numéro « Vente 2026-10-23 » / « Vente S43-2026 » / « Vente Octobre 2026 », quantités au millième (Sage accepte 4 décimales).
- Les taxes Sage (calculées sur le net) diffèrent légèrement des taxes encaissées par Clover : arrondis au cent par commande, taxes d'articles remboursés, articles « non-recette » (signalés en anomalie).
- Facture Sage existante (« Vente Mars 2025 », 2025-03-31) : client « Vente Hebdomadaire », quantités à 2 décimales, prix à 4 décimales, colonne Taxe vide (TPS/TVQ à 0), compte de revenus par article (ex. 4016 Féculents, 4017 Fruits & Légumes, 4013 Divers), emplacement « Emplacement par défaut », facture marquée PAYÉ.

- Le total affiché par Clover est calculé avant arrondi : la somme des lignes peut différer de quelques cents (janvier 2026 : 52 452,91 $ en lignes contre 52 453,00 $ au total Clover).
- Règles validées contre les exports Clover (17, 19 et 23 oct. 2026, au cent près) : une vente est datée de son premier paiement réussi (pas de la création de la commande) ; les pourcentages de rabais d'une commande s'additionnent (99 % + 10 % = 100 % max) ; `paymentState` reste souvent OPEN.
- Liste des articles Sage : export texte cp1252 (`E:\Article.txt`, en-tête `33101,3,Inventory`), colonnes : numéro, description, type, unité, prix, prix, compte d'actif, compte de revenus, compte CPV, compte d'écart, description 2, unité de vente.
- Sage 50 CA n'a pas d'API ouverte : l'import passera par un fichier `.IMP` (`<SalInvoice>`), à tester uniquement sur une copie du fichier d'entreprise.
- Ne jamais committer `config.toml` (jeton Clover), ni les exports ou rapports de ventes (`*.xlsx`, `sortie/`).
