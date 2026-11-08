# MVOGMBI_Sync — Processus métier (BPM)

Version 1.0.20 (7 novembre 2026) — Marché MVOG-MBI Sherbrooke.

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
        C7{Montant déjà au 1055<br/>par une autre écriture ?}
        C6[Compte rendu par courriel]
        C8[Dépôt en échec noté,<br/>dépôt suivant saisi]
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
        F3[Vérifier « Déjà au compte<br/>de dépôt ? »]
    end
    A1 --> B1 --> C1 --> C2
    C2 -- oui --> C3 --> D1
    C2 -- non --> C4 --> F1 --> C1
    B1 --> B2 --> E1 --> C5
    D1 --> C5 --> C7
    C7 -- non --> D2 --> C6 --> F2
    C7 -- oui --> F3 --> F2
    D2 -. échec .-> C8 --> C6
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
        A1([Pointer arrivée, pause, départ<br/>par NIP, sur le Wi-Fi du magasin])
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

## 4 bis. Transferts d'argent RIA

```mermaid
flowchart TB
    subgraph CLR["Client RIA"]
        A1([Envoie ou reçoit de l'argent])
    end
    subgraph MAR["Marché (comptoir)"]
        B1[Reçoit les espèces d'un envoi<br/>ou paie un versement]
        B2[Dépose les espèces à la banque]
    end
    subgraph RIA["RIA"]
        C1[État de compte<br/>par courriel]
        C2[Règlement ACH<br/>et commission mensuelle]
    end
    subgraph APPRIA["MVOGMBI_Sync"]
        D1[Lire et recontrôler l'état]
        D2{Versement payé<br/>par Interac ?}
        D3[Opération : envoi<br/>espèces → RIA]
        D4[Opération : versement<br/>RIA → espèces]
        D5[Surplus du dépôt d'espèces<br/>et commission reconnus]
    end
    subgraph SAGERIA["Sage 50"]
        E1([Écritures de journal<br/>multi-utilisateur, vérifiées])
    end
    A1 --> B1 --> C1 --> D1 --> D2
    D2 -- non --> D4 --> E1
    D2 -- oui --> E1
    D1 --> D3 --> E1
    B1 --> B2 --> D5 --> E1
    C2 --> D5
```

## 4 ter. Chaîne des documents de vente et d'achat

```mermaid
flowchart TB
    subgraph CLI2["Client / fournisseur"]
        A1([Demande ou commande])
    end
    subgraph APPD["MVOGMBI_Sync"]
        B1[Devis ou demande de prix]
        B2[Commande / bon de commande]
        B3[Livraison / réception]
        B4[Facture]
        B5[Clover : stock mis à jour<br/>une seule fois]
    end
    subgraph SAGED["Sage 50"]
        C1[Import de la facture<br/>mono-utilisateur, vérifiée]
    end
    A1 --> B1 -- Transformer --> B2 -- Transformer --> B3 -- Transformer --> B4 --> C1 --> B5
```

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


---

## 6. Réception chez un fournisseur dans un dépôt

```mermaid
flowchart TB
    subgraph Magasin["Magasin / dépôt"]
        A([Livraison reçue]) --> B["Photo ou PDF de la facture"]
        L["Bon de réception signé<br/>joint à la facture"]
    end
    subgraph Bureau["Bureau (gérant, comptable)"]
        C["Lignes, articles Sage, facteur<br/>dépôt de la facture"] --> D["Prête à importer"]
        D --> E["Importer (cochées)"]
    end
    subgraph Application
        F["Import dans Sage<br/>outil ou assistant"] --> G["Transfert vers le dépôt"]
        G --> H["Stock et coût Clover"]
        H --> I["Courriel de compte rendu"]
    end
    B --> C
    E --> F
    I --> L
```

---

## 7. Espèces : du tiroir à la banque

```mermaid
flowchart TB
    subgraph CAI["Caissier"]
        A1([Ventes en espèces])
    end
    subgraph GERC["Gérant"]
        B1[Compter le tiroir<br/>par coupures]
        B2{Écart de plus de 5 $ ?}
        B3[Recompter, expliquer]
        B4[Déposer au guichet]
    end
    subgraph CLOC["Clover"]
        C1[Paiements en espèces,<br/>remboursements, retraits]
    end
    subgraph APPC["MVOGMBI_Sync"]
        D1[Espèces attendues]
        D2[Écart, à déposer]
        D3[Dépôt du relevé réparti<br/>sur les factures]
        D4{Surplus au-delà<br/>des ventes ?}
        D5[Part RIA à confirmer]
    end
    subgraph SAGEC["Sage 50"]
        E1[Encaissements<br/>sur les factures]
    end
    A1 --> C1 --> D1 --> B1 --> D2 --> B2
    B2 -- oui --> B3 --> D2
    B2 -- non --> B4 --> D3 --> D4
    D4 -- non --> E1
    D4 -- oui --> D5 --> E1
```

---

## 8. Pertes et démarque

```mermaid
flowchart TB
    subgraph MAG["Magasin"]
        A1([Produit périmé,<br/>abîmé ou volé])
    end
    subgraph GERD["Gérant"]
        B1[Déclarer la perte<br/>motif, dépôt, lignes]
        B2[Analyser le rapport]
    end
    subgraph APPD["MVOGMBI_Sync"]
        C1[Valoriser au CUMP Sage<br/>sinon coût Clover]
        C2[Taux de perte<br/>= pertes / ventes nettes]
    end
    subgraph CLOD["Clover"]
        D1[Stock diminué]
    end
    subgraph SAGED["Sage 50"]
        E1[Document de stock<br/>« Sortie »]
    end
    A1 --> B1 --> C1
    C1 --> D1
    C1 --> E1
    D1 & E1 --> C2 --> B2
```

---

## 9. De l'embauche au premier bulletin

```mermaid
flowchart TB
    subgraph PRO["Propriétaire / gérant"]
        A1([Embauche])
        A2[Créer l'employé<br/>NIP, courriel, dépôt]
        A3[Publier le planning]
        A4[Approuver la feuille]
    end
    subgraph EMPL["Employé"]
        B1[Pointer au magasin]
        B2([Recevoir son bulletin<br/>par courriel])
    end
    subgraph CLOE["Clover"]
        C1[Fiche employé]
    end
    subgraph SAGEE["Sage Paie"]
        D1[Fiche employé<br/>taux, impôt, périodes]
        D2[Chèque de paie<br/>PAYjjmmaaaa]
    end
    subgraph APPE["MVOGMBI_Sync"]
        E1[Feuille de temps<br/>de la période]
        E2[Bulletin PDF<br/>un destinataire]
    end
    A1 --> A2 --> C1 & D1
    A2 --> A3 --> B1 --> E1 --> A4 --> D2 --> E2 --> B2
```
