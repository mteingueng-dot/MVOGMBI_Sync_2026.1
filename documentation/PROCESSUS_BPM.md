# MVOGMBI_Sync — Processus métier (BPM)

Version 1.0.0 (30 octobre 2026) — Marché MVOG-MBI Sherbrooke.

Notation : chaque couloir est un acteur ou un système ; ( ) = début ou fin, [ ] = activité, { } = décision, flèches = enchaînement. Les processus sont ceux en service.

---

## 1. De la vente à l'encaissement (order-to-cash)

```mermaid
flowchart TB
    subgraph CLI["Client"]
        A1([Achat en caisse])
    end
    subgraph CLO["Clover"]
        B1[Commande et paiement]
        B2[Lot de cartes fermé le soir]
    end
    subgraph APP["MVOGMBI_Sync — nuit"]
        C1[Lire les ventes du jour]
        C2{Articles reliés<br/>et comptes complets ?}
        C3[Préparer la facture<br/>une ligne par article]
        C4[Signaler le jour bloqué]
        C5[Rapprocher dépôt et facture]
        C6[Compte rendu par courriel]
    end
    subgraph SAGE["Sage 50"]
        D1[Facture « Vente AAAA-MM-JJ »<br/>import mono-utilisateur]
        D2[Encaissement « Comptant »<br/>saisie multi-utilisateur]
    end
    subgraph BQ["Desjardins"]
        E1[Dépôt Clover au 1055]
    end
    subgraph GER["Gérant"]
        F1[Relier l'article ou<br/>corriger le compte]
        F2([Ventes comptabilisées<br/>et encaissées])
    end
    A1 --> B1 --> C1 --> C2
    C2 -- oui --> C3 --> D1
    C2 -- non --> C4 --> F1 --> C1
    B1 --> B2 --> E1 --> C5
    D1 --> C5 --> D2 --> C6 --> F2
```

---

## 2. De l'achat au paiement (procure-to-pay)

```mermaid
flowchart TB
    subgraph APPA["MVOGMBI_Sync"]
        A1([Stock bas selon les ventes])
        A2[Bon de commande proposé<br/>un par fournisseur]
        A5[Lire la facture PDF<br/>contrôle des totaux]
        A6{Lignes reliées<br/>et sans doublon ?}
        A7[Importer la facture d'achat]
        A8[Stock et coût Clover]
        A10[Rapprocher l'avis Interac]
    end
    subgraph GERA["Gérant / comptable"]
        B1[Envoyer le bon]
        B2[Relier les articles,<br/>facteur, taxes]
        B3[Payer par Interac]
        B4[Confirmer le paiement]
    end
    subgraph FOU["Fournisseur"]
        C1[Livrer et facturer<br/>PDF par courriel]
        C2[Recevoir le virement]
    end
    subgraph SAGEA["Sage 50"]
        D1[Facture d'achat<br/>import mono-utilisateur]
        D2[Paiement « Comptant »<br/>saisie multi-utilisateur]
        D3([Facture payée])
    end
    A1 --> A2 --> B1 --> C1 --> A5 --> A6
    A6 -- non --> B2 --> A6
    A6 -- oui --> A7 --> D1 --> A8
    D1 --> B3 --> C2
    B3 --> A10 --> B4 --> D2 --> D3
```

---

## 3. Paie

```mermaid
flowchart TB
    subgraph EMP["Employé"]
        A1([Pointer arrivée, pause, départ<br/>par NIP])
        A2[Consulter son horaire]
        A3([Recevoir son bulletin])
    end
    subgraph GERP["Gérant"]
        B1[Publier le planning]
        B2{Feuille correcte ?}
        B3[Corriger avec motif]
        B4[Approuver]
        B5[Traiter la paie]
    end
    subgraph APPP["MVOGMBI_Sync"]
        C1[Calculer présence, pauses,<br/>heures supplémentaires]
        C2[Ajouter fériés et congés payés]
        C3[Bulletins PDF]
        C4[Suivi des remises]
    end
    subgraph SAGEP["Sage Paie"]
        D1[Chèques de paie<br/>retenues calculées]
    end
    B1 --> A2
    A1 --> C1 --> B2
    B2 -- non --> B3 --> C1
    B2 -- oui --> B4 --> C2 --> B5 --> D1 --> C3 --> A3
    D1 --> C4
```

---

## 4. Rapprochement bancaire mensuel

```mermaid
flowchart TB
    subgraph BQR["Desjardins"]
        A1([Relevé PDF du mois])
    end
    subgraph COM["Comptable"]
        B1[Charger le relevé]
        B4[Expliquer : encaissement<br/>ou paiement manuel]
        B6([Mois rapproché])
    end
    subgraph APPR["MVOGMBI_Sync"]
        C1[Lire les mouvements<br/>et vérifier chaque solde]
        C2[Associer aux écritures du 1055<br/>même montant, −7 à +3 jours]
        C3{Écart non expliqué ?}
        C4[Écriture de journal proposée]
    end
    subgraph SAGER["Sage 50"]
        D1[Écriture saisie<br/>multi-utilisateur]
    end
    A1 --> B1 --> C1 --> C2 --> C3
    C3 -- "absent de Sage" --> C4 --> D1 --> C2
    C3 -- "à expliquer" --> B4 --> C2
    C3 -- "0,00 $" --> B6
```

---

## 5. Gestion des stocks entre points de vente

```mermaid
flowchart TB
    subgraph GERS["Gérant"]
        A1([Besoin de marchandise<br/>dans un autre magasin])
        A2[Saisir le transfert]
    end
    subgraph APPS["MVOGMBI_Sync"]
        B1{Dépôts différents,<br/>quantités > 0 ?}
        B3[Stocks Clover :<br/>départ − / arrivée +]
        B4([Transfert terminé])
    end
    subgraph SAGES["Sage 50"]
        C1[Transfert entre emplacements<br/>multi-utilisateur]
    end
    A1 --> A2 --> B1
    B1 -- non --> A2
    B1 -- oui --> C1 --> B3 --> B4
```
