# MVOGMBI_Sync — Diagramme de projet

Version 1.0.0 (30 octobre 2026) — Marché MVOG-MBI Sherbrooke. 97 versions livrées en 7 jours, chacune avec son installateur.

---

## 1. Planning réalisé (Gantt)

```mermaid
gantt
    title MVOGMBI_Sync — réalisation
    dateFormat YYYY-MM-DD
    axisFormat %d %b
    section Ventes vers Sage
    Connexion Clover, cumul des ventes          :done, a1, 2026-10-24, 1d
    Correspondance des articles                 :done, a2, 2026-10-24, 1d
    Fichier d'import et import Sage             :done, a3, 2026-10-24, 1d
    Traitement de nuit, interface, installateur :done, a4, 2026-10-25, 1d
    section Banque et fournisseurs
    Encaissements et saisie dans Sage           :done, b1, 2026-10-25, 2d
    Factures fournisseurs (PDF, OCR, import)    :done, b2, 2026-10-26, 1d
    Paiements fournisseurs (Interac)            :done, b3, 2026-10-26, 1d
    Rapprochement bancaire Desjardins           :done, b4, 2026-10-26, 1d
    section Pilotage
    Rapports et statistiques Clover             :done, c1, 2026-10-27, 1d
    Bénéfices, KPI, prévisions, péremption      :done, c2, 2026-10-27, 1d
    Produits inactifs, articles 20/80           :done, c3, 2026-10-29, 1d
    section Gestion
    Points de vente, création d'articles        :done, d1, 2026-10-28, 1d
    Inventaire, transferts, menu en rubriques   :done, d2, 2026-10-28, 1d
    Gestion commerciale et comptabilité         :done, d3, 2026-10-29, 1d
    Caisse, pertes, dépenses, promotions        :done, d4, 2026-10-29, 1d
    section Paie
    Pointage, planning, feuilles de temps       :done, e1, 2026-10-29, 1d
    Paie dans Sage, bulletins, congés           :done, e2, 2026-10-29, 1d
    section Sécurité et qualité
    Utilisateurs, profils, verrouillage         :done, f1, 2026-10-26, 2d
    Droits par fonction, droit Supprimer        :done, f2, 2026-10-30, 1d
    Sage multi-utilisateur, temps réel          :done, f3, 2026-10-30, 1d
    Test complet, version 1.0, documentation    :done, f4, 2026-10-30, 1d
    section Suite
    Plusieurs points de vente réels             :g1, 2026-11-02, 5d
    Remises de retenues réelles                 :g2, 2026-11-15, 1d
```

---

## 2. Découpage du produit

```mermaid
mindmap
  root((MVOGMBI_Sync))
    Ventes
      Factures journalières
      Fin de semaine
      Points de vente
      Encaissements
    Articles
      Correspondance
      Création Clover + Sage
      Inventaire et transferts
      Pertes, étiquettes, promotions
      Prix et marges
    Fournisseurs
      Factures PDF et courriel
      Bons de commande
      Paiements Interac
      Retours
    Comptabilité
      Rapprochement Desjardins
      Caisse et dépenses
      TPS TVQ, budget, clôture
    Paie
      Pointage NIP
      Planning, feuilles de temps
      Chèques Sage, bulletins
      Congés, remises
    Pilotage
      Statistiques Clover
      Bénéfices au CUMP
      Prévisions, 20/80
      Résumé du matin
    Socle
      Traitement de nuit
      Pilotage de Sage
      Utilisateurs et droits
      Sauvegarde
```

---

## 3. Jalons

| Date | Jalon | Version |
|---|---|---|
| 24 oct. 2026 | Premier import automatique réussi dans Sage | étape 4 |
| 25 oct. 2026 | Traitement de nuit, installateur Windows | 1.3.0 |
| 26 oct. 2026 | Encaissements la nuit, fournisseurs, rapprochement | 1.7.0 à 1.9.11 |
| 27 oct. 2026 | Statistiques et rapports comme Clover | 1.9.12 à 1.9.29 |
| 28 oct. 2026 | Points de vente, articles, inventaire, transferts | 1.10 à 1.22 |
| 29 oct. 2026 | Gestion commerciale, comptabilité, paie | 1.23 à 1.45 |
| 30 oct. 2026 | Droits par fonction, multi-utilisateur, temps réel, test complet | 1.46.3 |
| 30 oct. 2026 | **Version 1.0.0** : numérotation remise à zéro, documentation complète | 1.0.0 |

---

## 4. Organisation

| Rôle | Responsabilité |
|---|---|
| Propriétaire du marché | Besoins, règles de gestion, validations (« vas-y », confirmations), essais réels |
| Développement | Code, tests, installateurs, documentation |
| Copie d'essai Sage | Tous les essais d'écriture avant le vrai fichier |

Méthode : une demande → une version livrée avec son installateur, ses tests et sa documentation ; règles du propriétaire notées dans le projet et appliquées partout.

---

## 5. Risques suivis

| Risque | Mesure |
|---|---|
| Sage sans API ouverte | Import par l'outil officiel, saisies par les fenêtres de Sage, vérification dans la base |
| Écriture dans le vrai fichier par erreur | Fichier d'import distinct (copie d'essai) tant que non validé |
| Double import, double encaissement | Contrôle de présence avant et après chaque écriture |
| Service de connexion de Sage arrêté | Message clair ; lecture de secours |
| Données réelles dans le dépôt public | `.gitignore`, contrôle avant chaque envoi |
