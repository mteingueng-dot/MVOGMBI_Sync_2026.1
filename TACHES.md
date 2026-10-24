# Liste des tâches — MVOGMBI_Sync_2026.1

Objectif : à partir des ventes Clover d'un jour, d'une semaine ou d'un mois, créer dans Sage 50 (Édition canadienne 2026.2) la facture de vente du client « Vente hebdomadaire », une ligne par article vendu.

Légende : **[Vous]** = action à faire par le propriétaire · **[Claude]** = développement · **[Ensemble]** = vérification commune.
On coche une case (`[x]`) quand la tâche est terminée et vérifiée.

---

## Étape 0 — Fondations ✅

- [x] [Claude] Créer le projet et le dépôt GitHub `MVOGMBI_Sync_2026.1`
- [x] [Claude] Cumul des ventes par article : jour, semaine (lundi → dimanche), mois
- [x] [Claude] Lecture d'un export Excel Clover « Ventes d'articles »
- [x] [Claude] Rapport Excel de vérification dans `sortie/`
- [x] [Ensemble] Essai sur janvier 2026 : 52 452,91 $ de ventes nettes (écart de 0,09 $ expliqué par l'arrondi du total Clover)

## Étape 1 — Connexion à Clover

- [x] [Vous] Créer un jeton API dans Clover (*Compte et configuration > Jetons API*), droits en lecture : Commandes, Inventaire, Paiements
- [x] [Vous] Copier `config.example.toml` en `config.toml` et y inscrire l'identifiant marchand et le jeton (ne jamais les envoyer dans le chat)
- [x] [Claude] Tester la récupération des commandes d'une journée par l'API
- [x] [Vous] Remplacer le jeton Clover (l'actuel a été communiqué dans le chat)
- [x] [Vous] Fournir l'export Clover journalier « Ventes d'articles » de cette même journée
- [x] [Ensemble] Comparer API et export, article par article, jusqu'à concordance au cent près
- [x] [Claude] Ajuster les règles : commandes payées, articles au poids, rabais de commande, remboursements (23 oct. 2026 : concordance parfaite, 155 articles, 3 139,39 $)
- [x] [Ensemble] Confirmer sur une 2e journée : 19 oct. 2026 concordant (111 articles, 1 390,42 $) après 2 corrections : vente datée au paiement, rabais successifs
- [x] [Vous] Fournir l'export d'un samedi chargé : 17 oct. 2026 concordant (220 articles, 4 127,62 $) après correction : pourcentages de rabais additionnés comme Clover
- [ ] [Vous] Supprimer l'ancien jeton Clover (toujours actif)
- [ ] [Claude] Contourner la limite Clover de 90 jours pour les mois anciens (repli sur l'export Excel)

## Étape 2 — Informations de Sage 50

- [x] [Vous] Exporter la liste des articles d'inventaire de Sage (*Rapports > Inventaire et services > Liste des articles*) en Excel ou CSV
- [x] [Vous] Envoyer une capture d'écran du formulaire « Facture de vente »
- [x] [Vous] Capture d'une facture « Vente hebdomadaire » remplie (client, quelques lignes, taxes)
- [x] [Vous] Codes de taxe : « GQ » pour les articles taxables (repérés par les taxes Clover), vide sinon
- [x] [Vous] Mode « Payer plus tard » (dépôts bancaires appliqués ensuite) ; numéros « Vente 2026-10-23 », « Vente S43-2026 », « Vente Octobre 2026 »
- [ ] [Vous] Indiquer le compte de revenus pour les « Articles personnalisés » et les articles absents de l'inventaire

## Étape 3 — Correspondance des articles Clover ↔ Sage

- [x] [Claude] Générer automatiquement la table de correspondance : 2 119 automatiques (84 %), 371 à confirmer, 36 sans proposition (`python -m mvogmbi_sync correspondance`)
- [ ] [Vous] Vérifier et corriger les correspondances douteuses dans le fichier Excel produit
- [ ] [Claude] Signaler à chaque exécution les nouveaux articles Clover sans correspondance
- [ ] [Ensemble] Décider du traitement des articles inconnus (bloquer, ou ligne sur un compte de revenus)

## Étape 4 — Fichier d'import Sage 50 (.IMP)

- [ ] [Claude] Obtenir la spécification officielle du format `<SalInvoice>` (base de connaissances Sage / « Dev-Import.pdf » du SDK)
- [x] [Ensemble] Règle de prix : montant de ligne = ventes nettes, prix unitaire = ventes nettes / quantité nette (vérifié : total facture = ventes nettes les 19 et 23 oct.)
- [x] [Claude] Préparer la facture : client, date, numéro, une ligne par article, code de taxe GQ (19 et 23 oct. vérifiés)
- [ ] [Vous] Corriger dans Clover l'article « Colombina Bon Bon Bum Fresa 408g » marqué « non-recette »
- [ ] [Vous] Faire une **copie de sauvegarde** du fichier d'entreprise Sage pour les essais
- [ ] [Ensemble] Importer une journée dans la copie (*Fichier > Importer/Exporter > Importer des transactions*)
- [ ] [Ensemble] Vérifier la facture importée : quantités, montants, taxes, total, inventaire
- [ ] [Claude] Corriger jusqu'à un import sans erreur ni avertissement
- [ ] [Ensemble] Répéter l'essai sur une semaine et sur un mois

## Étape 5 — Contrôles et sécurité

- [ ] [Claude] Journal des périodes déjà importées, pour empêcher un import en double
- [ ] [Claude] Rapport de rapprochement : total Clover vs total de la facture, écarts signalés
- [ ] [Claude] Messages d'erreur clairs (jeton expiré, Clover inaccessible, article inconnu…)
- [ ] [Claude] Archivage de chaque fichier `.IMP` et rapport produits

## Étape 6 — Interface simple

- [ ] [Claude] Petite fenêtre : choisir jour / semaine / mois et la date, voir l'aperçu, générer le fichier
- [ ] [Claude] Raccourci sur le bureau pour lancer l'application
- [ ] [Vous] Essayer l'interface et donner vos remarques

## Étape 7 — Automatisation

- [ ] [Ensemble] Choisir le rythme (chaque soir, chaque lundi, fin de mois) et l'heure
- [ ] [Claude] Planifier l'exécution avec le Planificateur de tâches Windows
- [ ] [Claude] Avertissement (courriel ou notification) en cas de problème

## Étape 8 — Mise en service

- [ ] [Claude] Guide d'utilisation en français
- [ ] [Ensemble] Période de rodage (2 à 4 semaines) : import automatique + contrôle manuel en parallèle
- [ ] [Vous] Valider le passage définitif à l'application

## Étape 9 — Évolution possible (plus tard)

- [ ] [Ensemble] Évaluer l'intégration directe dans Sage par le SDK Sage 50 (sans import manuel)
