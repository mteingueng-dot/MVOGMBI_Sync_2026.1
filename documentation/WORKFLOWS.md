# MVOGMBI_Sync — Workflows d'utilisation

Version 1.0.0 (9 novembre 2026) — Marché MVOG-MBI Sherbrooke.

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
    F --> F2["RIA > Comptes RIA<br/>comptes RIA, commissions, espèces"]
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
    B -- non --> D["RIA > États de compte RIA<br/>Importer des états…"]
    C --> E["Contrôle : solde recalculé ligne par ligne"]
    D --> E
    E --> F["Traiter dans Sage"]
    F --> G{"Comptes RIA renseignés ?"}
    G -- non --> H["RIA > Comptes RIA"] --> F
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

## 8 quater. Facture photographiée au téléphone

```mermaid
flowchart TD
    A([Facture papier reçue]) --> B["Fournisseur > Factures fournisseurs<br/>📷 Photographier une facture"]
    B --> C["Prendre la page en photo"]
    C --> D{Autre page ?}
    D -->|oui| E["➕ Ajouter la page"] --> C
    D -->|non| F["✔ Terminer la facture"]
    F --> G["Un PDF, lu par l'OCR de Windows"]
    G --> H([Facture dans la liste, comme au workflow 3])
```

## 8 quinquies. Importer plusieurs factures fournisseurs dans leur dépôt

```mermaid
flowchart TD
    A([Factures « Prête à importer »]) --> B["Choisir le Dépôt de chaque facture"]
    B --> C["Cocher les factures<br/>(☑ Cocher les factures prêtes)"]
    C --> D["☑ Importer les factures cochées"]
    D --> E{Entreprise partagée ?}
    E -->|non| F["Outil d'import"]
    E -->|oui| G["Assistant d'importation de Sage"]
    F & G --> H["Vérifiée dans Sage"]
    H --> I["Transfert vers le dépôt"]
    I --> J["Stock Clover du point de vente"]
    J --> K["Courriel de compte rendu"]
    K --> L([🖨 Bon de réception / Facture avec prix])
```

## 8 sexies. Rapprocher un compte BNC

```mermaid
flowchart TD
    A([Relevé PDF BNC]) --> B["Comptabilité > Rapprochement bancaire<br/>Charger"]
    B --> C["Banque reconnue : rangé dans le compte BNC"]
    C --> D["Liste « Banque » : BNC"]
    D --> E["Comparé au compte Sage 1060"]
    E --> F["Confirmer les comptes des mouvements absents"]
    F --> G([Saisir dans Sage])
    H([Nouveau compte bancaire]) --> I["Administration > Sage 50<br/>4. Comptes bancaires : Ajouter"]
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

## 8 septies. Valider les feuilles de temps (gérant)

```mermaid
flowchart TD
    A([Fin de la période de 14 jours]) --> B["Paie > Feuilles de temps<br/>📋 Suivi des périodes"]
    B --> C["Double-clic sur la période « À approuver »"]
    C --> D{Anomalies ?}
    D -->|oui| E["Corriger les pointages<br/>(motif obligatoire)"] --> D
    D -->|non| F["Approuver les feuilles sans anomalie"]
    F --> G([Traitement de la paie])
    H([Période non approuvée]) -.-> I["Rappel en rouge<br/>au courriel du matin"]
```

## 8 octies. Encaisser les dépôts en retard

```mermaid
flowchart TD
    A([Dépôts Clover pas encore encaissés]) --> B["Comptabilité > Encaissements<br/>Ventes du … au … , Calculer"]
    B --> C{État du dépôt}
    C -->|À saisir dans Sage| D["Encaisser dans Sage"]
    C -->|Déjà au compte de dépôt ?| E["Vérifier dans Sage :<br/>le montant exact est déjà au 1055<br/>par une autre écriture"]
    E -->|c'est bien ce dépôt| F([Rien à faire])
    E -->|autre écriture| G["Encaisser à la main dans Sage"]
    C -->|Part RIA à confirmer| H["RIA > Opérations RIA<br/>confirmer le surplus"]
    D --> I{"Sage de la journée prêt ?"}
    I -->|en ouverture, 2 à 3 min| J["La saisie attend<br/>la fin de l'ouverture"] --> K
    I -->|oui| K["Fenêtre Encaissements :<br/>montant dans « Montant reçu »,<br/>total contrôlé, Traiter"]
    K --> L["Solde de chaque facture<br/>vérifié dans Sage"]
    L --> M([Dépôt « Appliqué »])
    K -->|échec| N["« NON encaissé » + raison<br/>fenêtre remise à zéro"]
    N --> O([Dépôt suivant saisi])
    N --> P["Vérifier dans Sage<br/>puis relancer"]
```

## 8 nonies. Lundi matin : décider avec le Reporting

```mermaid
flowchart TD
    A["Courriel du matin :<br/>décisions de la semaine"] --> B["État > Reporting<br/>Accueil > Synthèse et décisions"]
    B --> C{"Priorité 1 ?"}
    C -- oui --> D["Ouvrir l'analyse citée<br/>(ex. Ruptures probables)"]
    D --> E["Détail : filtrer<br/>par catégorie ou groupe"]
    E --> F["Agir : commander,<br/>changer un prix, relancer"]
    C -- non --> G["Points positifs<br/>et priorités 2 et 3"]
    F --> H["Exporter ou PDF<br/>de la page"]
```

1. Lire les décisions du courriel du matin. Les priorités 1 sont en rouge, avec les 5 premiers éléments concernés.
2. Ouvrir État > Reporting et choisir la période (par exemple « 30 derniers jours »). Ouvrir ensuite Accueil > Synthèse et décisions.
3. Pour chaque décision, ouvrir l'analyse citée et lire ses trois sous-pages : Résumé (cartes et constats), Graphiques, Détail.
4. Dans le Détail, filtrer par texte ou par groupe. Un clic sur un n° de commande ouvre la facture Clover.
5. Agir (bon de commande, prix, promotion, horaire), puis comparer la semaine suivante.

## 8 decies. Relier les lignes d'une facture fournisseur

1. Fournisseur > Factures fournisseurs : ouvrir la facture. Les articles Sage sont proposés tout de suite.
2. Si les propositions sont justes, cliquer « Confirmer toutes les propositions ». Sinon :
   - choisir la ligne ;
   - chercher l'article Sage (l'assistant de saisie propose les articles pendant la frappe) ;
   - cliquer « Relier et confirmer ».

   La ligne suivante à relier s'ouvre d'elle-même.
3. Vérifier le facteur (une caisse en unités, un poids dans l'unité de Sage) et les taxes de chaque ligne (« F P » et « TX » sont lus).
4. Cocher ou décocher « Mettre à jour le stock Clover » pour cette facture seulement.
5. Cliquer « Importer cette facture », ou cocher plusieurs factures prêtes puis cliquer « Importer les factures cochées ». La facture importée passe aux archives.

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
    M([Employé parti ou absent]) --> N["Administration > Utilisateurs<br/>choisir le compte, Activer / désactiver"]
    N --> O([Connexion refusée, sessions fermées]) --> P["Activer / désactiver<br/>à son retour"]
    J([Compte verrouillé après 3 essais faux]) --> K["Administration > Utilisateurs<br/>nouveau mot de passe"] --> L([Compte rouvert])
```

---

## 10. Contrôle de la caisse du soir

```mermaid
flowchart TD
    A([Fermeture du magasin]) --> B["Comptabilité > Contrôle de la caisse<br/>point de vente, date du jour"]
    B --> C["Espèces attendues lues dans Clover<br/>fond + espèces − remboursements − retraits"]
    C --> D["Compter le tiroir par coupures"]
    D --> E{"Écart de plus de 5 $ ?"}
    E -- oui --> F["Recompter ;<br/>voir les espèces par employé"]
    F --> G["Enregistrer le comptage<br/>(l'ancien reste dans l'historique)"]
    E -- non --> G
    G --> H["Fond laissé pour demain<br/>à déposer = compté − fond"]
    H --> I["Dépôt au guichet"]
    I --> J([Le relevé suivant le rapproche<br/>onglet « Dépôts d'espèces »])
    G -.-> K([Alerte au courriel du matin<br/>si non compté ou écart])
```

---

## 11. Déclarer une perte

```mermaid
flowchart TD
    A([Produit abîmé, périmé, volé…]) --> B["Stock > Pertes et démarque<br/>Déclarer une perte"]
    B --> C["Motif, dépôt, date"]
    C --> D["Lignes : articles du catalogue Clover<br/>ou « Ajouter les produits périmés en stock »"]
    D --> E["Coût : CUMP Sage, sinon coût Clover"]
    E --> F["Valider"]
    F --> G["Stock Clover diminué ligne par ligne"]
    F --> H["Document de stock « Sortie »<br/>passé dans Sage"]
    G & H --> I([Rapport des pertes et taux de perte])
    I -.-> J["Erreur ? Ouvrir, Modifier<br/>ou Supprimer = annulation"]
```

---

## 12. Transfert entre magasins

```mermaid
flowchart TD
    A([Marchandise envoyée<br/>à un autre magasin]) --> B["Stock > Transferts entre magasins<br/>Ajouter"]
    B --> C["Point de vente de départ et d'arrivée<br/>(dépôts différents)"]
    C --> D["Lignes : article, quantité<br/>stock Sage départ / arrivée affiché"]
    D --> E["Enregistrer (Brouillon)"]
    E --> F["🖨 Bon de transfert<br/>accompagne la marchandise"]
    F --> G["Transférer"]
    G --> H["Sage : transfert entre emplacements<br/>lots de 7 lignes, vérifié"]
    H --> I{"Jeton Clover des deux magasins ?"}
    I -- oui --> J["Clover : départ − qté, arrivée + qté"]
    I -- non --> K["« À compléter »<br/>Clover fait plus tard"]
    J --> L([Terminé])
```

---

## 13. Promotion

```mermaid
flowchart TD
    A([Prix réduit pour une période]) --> B["Articles > Promotions<br/>Ajouter"]
    B --> C["Article, prix promo, du / au,<br/>point de vente"]
    C --> D{"Chevauche une autre promotion ?"}
    D -- oui --> E([Refusée])
    D -- non --> F["Enregistrée « Prévue »"]
    F --> G["1er jour, la nuit :<br/>prix normal lu, prix promo appliqué"]
    G --> H["Lendemain du dernier jour :<br/>prix encore = promo ?"]
    H -- oui --> I["Prix normal remis"]
    H -- non --> J["Laissé tel quel, noté"]
    I & J --> K([Effet : ventes pendant contre avant])
    F -.-> L["Annuler : prévue = annulée,<br/>en cours = prix normal remis tout de suite"]
```

---

## 14. Nouvel employé

```mermaid
flowchart TD
    A([Embauche]) --> B["Paie > Employés et NIP<br/>Nouvel employé"]
    B --> C["Nom, surnom, rôle Clover,<br/>courriel, NIP du poste"]
    C --> D["Créé dans Clover"]
    D --> E{"Créer dans Sage Paie ?"}
    E -- oui --> F["Adresse, naissance, embauche,<br/>NAS tapé une fois (jamais gardé), taux"]
    F --> G["Fiche employé créée dans Sage"]
    E -- non --> H["Lier aux employés Sage plus tard"]
    G & H --> I["Dépôt principal ;<br/>« Relier à un compte… » (connexion)"]
    I --> J["Planning : quarts du mois, publier"]
    J --> K([Pointe au magasin avec son NIP])
```

---

## 15. Relier les articles vendus (correspondance)

```mermaid
flowchart TD
    A(["Courriel : jour bloqué,<br/>article non relié"]) --> B["Articles > Correspondance<br/>Mettre à jour depuis Clover et Sage"]
    B --> C["Afficher : à confirmer / non reliés /<br/>supprimés ou renommés dans Clover"]
    C --> D["Choisir l'article Clover"]
    D --> E{"Proposition juste ?"}
    E -- oui --> F["Accepter la proposition"]
    E -- non --> G["Chercher l'article Sage"]
    G --> H{"Même format ?"}
    H -- oui --> I["Confirmer l'article choisi"]
    H -- non --> J["Confirmer quand même<br/>(ou créer l'article dans Sage)"]
    F & I & J --> K["Enregistré tout de suite"]
    K --> L([Charger la période :<br/>le jour bloqué est facturé])
```

---

## 16. Mettre à jour l'application

```mermaid
flowchart TD
    A([Nouvelle version livrée]) --> B["Prévenir : serveur web<br/>arrêté quelques secondes"]
    B --> C["Sur le serveur, session ouverte :<br/>Installer_MVOGMBI_Sync_x.y.z.exe"]
    C --> D["L'installateur arrête le serveur web<br/>et ferme le Sage de la journée"]
    D --> E["Fichiers copiés ;<br/>config.toml et donnees/ gardés"]
    E --> F["Serveur web relancé"]
    F --> G["Rouvrir l'application Windows<br/>(Sage de la journée rouvert)"]
    G --> H["Contrôles : version au bas du menu,<br/>Tester l'accès à Sage, page web"]
    H --> I{"Client changé ?"}
    I -- oui --> J["Installer le client sur les postes"]
    I -- non --> K([Terminé])
    J --> K
```

---

## 17. Restaurer une sauvegarde

```mermaid
flowchart TD
    A([Données perdues ou abîmées]) --> B["Fermer l'application partout<br/>(Windows et web)"]
    B --> C["Administration > Sauvegarde des données<br/>choisir l'archive"]
    C --> D["Restaurer"]
    D --> E["État actuel sauvegardé d'abord<br/>dans « avant_restauration »"]
    E --> F["Archive vérifiée, donnees/<br/>et config.toml remis"]
    F --> G{"Autre ordinateur ?"}
    G -- oui --> H["Retaper les mots de passe<br/>(coffre-fort propre à la machine)"]
    G -- non --> I([Rouvrir l'application])
    H --> I
```

---

## 18. Rattraper une période de ventes

```mermaid
flowchart TD
    A([Jours sans facture<br/>ex. reprise après une panne]) --> B["Vente > Ventes Clover → factures Sage<br/>période du … au …"]
    B --> C["Charger la période"]
    C --> D["Jours déjà facturés sautés ;<br/>fin de semaine en partie facturée bloquée"]
    D --> E["Factures préparées, contrôlées"]
    E --> F{"Jour bloqué ?"}
    F -- oui --> G["Relier l'article / corriger le compte,<br/>puis recharger"]
    F -- non --> H["Import par lots de 25<br/>(~20 min par lot), vérifié"]
    H --> I["Comptabilité > Encaissements<br/>mois par mois"]
    I --> J([Factures encaissées])
```
