# MVOGMBI_Sync — Workflows d'utilisation

Version 1.0.0 (30 octobre 2026) — Marché MVOG-MBI Sherbrooke.

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
    F --> G["Administration > Automatisation<br/>heure de nuit, date de départ"]
    G --> H["Administration > Utilisateurs<br/>comptes et fonctions permises"]
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
    B -- oui --> C["Lue automatiquement<br/>(la nuit ou « Lire le courriel »)"]
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

---

## 8. Inventaire

```mermaid
flowchart TD
    A([Inventaire]) --> B{"Complet ou tournant ?"}
    B -- complet --> C["Articles > Inventaire Clover et Sage<br/>Exporter"]
    B -- tournant --> D["Articles > Inventaire tournant<br/>catégories de la semaine"]
    C --> E["Compter, remplir « Quantité comptée »"]
    D --> E
    E --> F["Saisir l'inventaire compté"]
    F --> G["Clover : stock réglé<br/>Sage : ajustement par dépôt"]
    G --> H([Rapport : écarts et coût])
```

---

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
```
