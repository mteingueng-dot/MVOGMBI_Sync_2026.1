# MVOGMBI_Sync — Workflows d'utilisation

Version 2.15.0 (4 novembre 2026) — Marché MVOG-MBI Sherbrooke.

Chaque workflow suit l'ordre réel des écrans. Les noms entre guillemets sont ceux du menu (« Rubrique > Fonction »).

---

## 1. Mise en route (une fois)

```mermaid
flowchart TD
    A([Installer MVOGMBI_Sync]) --> B["Créer le compte administrateur<br/>(premier lancement)"]
    B --> C["Administration > Clover<br/>identifiant marchand, jeton"]
    C --> D["Administration > Sage 50<br/>fichier d'entreprise, utilisateur mvogmbi_sync"]
    D --> E["Articles > Correspondance<br/>confirmer les liens Clover → Sage"]
    E --> F["Administration > Courriel<br/>compte rendu, boîte des avis"]
    F --> F2["Comptabilité > Comptes RIA<br/>comptes RIA, commissions, espèces"]
    F2 --> G["Administration > Automatisation<br/>heure de nuit, date de départ"]
    G --> G2["Administration > Automatisation<br/>serveur de l'application, Wi-Fi du magasin"]
    G2 --> H["Administration > Utilisateurs<br/>comptes et fonctions permises"]
    H --> I([Mise en route : 10 étapes cochées])
```

---

## 2. Journée type du gérant

```mermaid
flowchart TD
    A([Matin]) --> B["Lire le courriel du traitement de nuit<br/>(résumé : ventes, marge, alertes)"]
    B --> C{"Problème signalé ?"}
    C -- "article non relié" --> D["Articles > Correspondance<br/>relier puis confirmer"]
    C -- "compte manquant" --> E["Vente > Ventes Clover → factures Sage<br/>Corriger les comptes dans Sage"]
    C -- non --> F["Accueil : vérifier les étapes"]
    D --> G["Charger la période<br/>(le jour bloqué est refait)"]
    E --> G
    G --> F
    F --> H["Comptabilité > Contrôle de la caisse<br/>comptage du soir"]
    H --> I([Fin de journée])
```

---

## 3. Facture fournisseur reçue

```mermaid
flowchart TD
    A([Facture PDF reçue]) --> B{"Par courriel ?"}
    B -- oui --> C["Lue automatiquement<br/>(la nuit ou « Lire le courriel »)<br/>prête = importée la nuit"]
    B -- non --> D["Fournisseur > Factures fournisseurs<br/>Ajouter des factures…"]
    C --> E["Vérifier les lignes : article Sage, facteur, taxes"]
    D --> E
    E --> F{"Article inconnu ?"}
    F -- oui --> G["Créer l'article (Clover + Sage)"]
    F -- non --> H["État : Prête à importer"]
    G --> H
    H --> I["Importer cette facture<br/>(Sage fermé)"]
    I --> J["Stock et coût Clover mis à jour"]
    J --> K([Facture archivée])
```

---

## 4. Paiement d'un fournisseur

```mermaid
flowchart TD
    A([Virement Interac envoyé]) --> B["Avis lu dans la boîte"]
    B --> C["Comptabilité > Paiements fournisseurs<br/>rapprochement proposé"]
    C --> D{"Bonne facture ?"}
    D -- non --> E["Choisir les factures (Ctrl + clic)"]
    D -- oui --> F["Confirmer"]
    E --> F
    F --> G["Payer dans Sage<br/>(ou la nuit)"]
    G --> H([Solde de la facture diminué])
```

---

## 5. Fin de mois

```mermaid
flowchart TD
    A([Relevé Desjardins PDF]) --> B["Comptabilité > Rapprochement<br/>Charger le relevé"]
    B --> C{"Écart non expliqué ?"}
    C -- "mouvement absent de Sage" --> D["Saisir dans Sage<br/>(écriture de journal)"]
    C -- "encaissement manuel" --> E["Encaissement manuel"]
    C -- "0,00 $" --> F["Comptabilité > Déclaration TPS/TVQ"]
    D --> C
    E --> C
    F --> G["Comptabilité > Clôture du mois<br/>contrôles et état des résultats"]
    G --> H["Paie > Suivi des remises"]
    H --> I([Mois fermé])
```

---

## 6. Paie toutes les deux semaines

```mermaid
flowchart TD
    A([Employés pointent par NIP]) --> B["Paie > Feuilles de temps<br/>corriger, approuver"]
    B --> C["Paie > Jours fériés et congés"]
    C --> D["Paie > Traitement de la paie<br/>onglet Heures validées"]
    D --> E["Traiter la paie dans Sage<br/>(chèques datés, n° PAYjjmmaaaa)"]
    E --> F["Onglet Paies dans Sage :<br/>paies traitées sélectionnées"]
    F --> G{"Bulletins"}
    G -- imprimer --> H["Imprimer tous les bulletins"]
    G -- courriel --> I["Envoyer les bulletins<br/>(un destinataire chacun)"]
    H --> J([Paie terminée])
    I --> J
```

---

## 6 bis. Dépôt d'espèces et RIA

```mermaid
flowchart TD
    A[Relevé chargé] --> B{Dépôt supérieur aux espèces dues ?}
    B -- Non --> C[Encaissement sur les ventes]
    B -- Oui --> D[Part RIA à confirmer]
    D --> E[RIA > Opérations RIA : Confirmer le surplus]
    E --> F[Saisir dans Sage : banque au débit, compte RIA au crédit]
    F --> C
    G[Retrait, dépôt ou paiement RIA du relevé] --> H[Saisir dans Sage]
    I[Commission de fin de mois] --> J[Marquer Commission] --> H
```

## 6 ter. États de compte RIA

```mermaid
flowchart TD
    A([État de compte RIA PDF]) --> B{"Reçu par courriel ?"}
    B -- oui --> C["Lu la nuit<br/>ou « Lire le courriel »"]
    B -- non --> D["Comptabilité > États de compte RIA<br/>Importer des états…"]
    C --> E["Contrôle : solde recalculé ligne par ligne"]
    D --> E
    E --> F["Traiter dans Sage"]
    F --> G{"Comptes RIA renseignés ?"}
    G -- non --> H["Comptabilité > Comptes RIA"] --> F
    G -- oui --> I["Envois : espèces → RIA<br/>Versements en espèces : RIA → espèces<br/>Versements Interac : laissés à la banque"]
    I --> J["RIA > Opérations RIA<br/>Saisir dans Sage"]
    J --> K([Écritures vérifiées dans Sage])
```

## 7. Nouvel article

```mermaid
flowchart TD
    A([Nouveau produit]) --> B["Articles > Créer un article"]
    B --> C{"Stock ou service ?"}
    C -- stock --> D["Catégorie → n° et comptes proposés<br/>(Comptes par catégorie…)"]
    C -- service --> E["N° « S… », comptes de produits et de charges"]
    D --> F["Prix = coût + 40 %, date de péremption"]
    F --> G["Créer : Sage puis Clover"]
    G --> H([Lien « Confirmé » dans la correspondance])
    E --> I["Créer : Sage seulement<br/>(jamais dans Clover)"]
    I --> J([Service disponible dans Sage])
```

## 7 bis. Modifier ou supprimer un article

```mermaid
flowchart TD
    A(["Articles > Liste des articles"]) --> B{"Action"}
    B -- Modifier --> C["Description, inactif,<br/>renommer aussi dans Clover"]
    C --> D["Enregistrer dans Sage<br/>(Sage fermé : l'application l'ouvre elle-même)"]
    D --> E([Vérifié dans Sage, Clover renommé])
    B -- Supprimer --> F["Confirmer"]
    F --> G{"Sage accepte ?"}
    G -- oui --> H([Supprimé de Sage puis de Clover])
    G -- "non : encore en stock" --> I([Rendu inactif dans Sage,<br/>article Clover gardé])
```

## 7 ter. Chaîne des documents

```mermaid
flowchart LR
    subgraph Vente
        DV[Devis] --> CC[Commande] --> BL[Livraison] --> FV[Facture]
        RC[Retour client] --> FRC[Facture de retour]
    end
    subgraph Achat
        PC[Demande de prix] --> BC[Bon de commande] --> BR[Réception] --> FA[Facture fournisseur]
        RT[Retour] --> FRT[Facture de retour]
    end
    FV --> S[(Import dans Sage<br/>puis stock Clover)]
    FRC --> S
    FA --> S
    FRT --> S
```

« Transformer » reprend les lignes, le client ou fournisseur et le dépôt ; seules les factures touchent le stock.

---

## 8. Inventaire

```mermaid
flowchart TD
    A([Inventaire]) --> B{"Complet ou tournant ?"}
    B -- complet --> C["Stock > Inventaire Clover et Sage<br/>Exporter"]
    B -- tournant --> D["Stock > Inventaire tournant<br/>catégories de la semaine"]
    C --> E["Compter, remplir « Quantité comptée »"]
    D --> E
    E --> F["Saisir l'inventaire compté"]
    F --> G["Clover : stock réglé<br/>Sage : ajustement par dépôt"]
    G --> H([Rapport : écarts et coût])
```

---

## 8 bis. Installer sur un serveur et déployer les postes

```mermaid
flowchart TD
    A([Serveur avec Sage 50<br/>ex. SERVDCSAGE]) --> B["Installer MVOGMBI_Sync<br/>(Bureau à distance)"]
    B --> C["Reprendre config.toml et donnees/<br/>Administration > Automatisation"]
    C --> D["Retaper les mots de passe<br/>Clover, Sage, courriel"]
    D --> E["Administration > Automatisation<br/>Serveur de l'application"]
    E --> F["Wi-Fi du magasin (pointage)"]
    F --> G["installer_web.ps1 + tâche planifiée"]
    G --> H["Fichier du client (serveur.json)"]
    H --> I["Postes : MVOGMBI_Sync_Client.exe<br/>+ serveur.json ; Tailscale"]
    I --> J([app.marchemvogmbi.com])
    G --> K["Ancien serveur : retirer tâche<br/>et serveur web"]
```

## 8 ter. Pointer au magasin

```mermaid
flowchart TD
    A([Employé au magasin]) --> B{Sur le Wi-Fi du magasin<br/>ou poste du magasin ?}
    B -->|non| C["Refusé : « connectez-vous<br/>au Wi-Fi du magasin »"] --> B
    B -->|oui| D["Paie > Pointage des employés<br/>toucher son nom"]
    D --> E["Taper son NIP"]
    E --> F["Arrivée / Pause / Fin de pause / Départ"]
    F --> G([Retour à la liste après 12 s])
    F --> H{Téléphone hors du Wi-Fi<br/>5 min de suite ?}
    H -->|oui| I[Pause automatique<br/>à l'heure du départ]
    I --> J{De retour sur le Wi-Fi ?}
    J -->|oui| K[Fin de pause automatique]
```

## 9. Droits d'un profil

```mermaid
flowchart TD
    A([Administrateur]) --> B["Administration > Utilisateurs"]
    B --> C["Choisir ou créer le profil"]
    C --> D["Cocher les fonctions une à une<br/>(une rubrique coche tout)"]
    D --> E["Actions dans les fenêtres"]
    E --> F["Droits : Exporter, Supprimer des éléments"]
    F --> G["Points de vente permis"]
    G --> H["Enregistrer les accès"]
    H --> I([Appliqué à la prochaine connexion])
    J([Compte verrouillé après 3 essais faux]) --> K["Administration > Utilisateurs<br/>nouveau mot de passe"] --> L([Compte rouvert])
```
