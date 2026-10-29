"""Contenu des pages « Accueil / À propos », « Guide de configuration » et « Aide / FAQ », en français et en anglais.

Chaque page est une liste de blocs (type, texte) : titre, sous_titre, para, puce, etape, note, question, reponse.
Les deux langues ont exactement la même suite de blocs (vérifié par les tests).
"""

from __future__ import annotations

VERSION = "1.22.3"
EDITEUR = "Concept Informatique inc."
COPYRIGHT = f"© 2026 {EDITEUR}"

ACCUEIL = {
    "fr": [
        ("titre", "Bienvenue dans MVOGMBI_Sync"),
        ("para", "MVOGMBI_Sync relie le point de vente Clover du Marché MVOG-MBI Sherbrooke à la comptabilité "
                 "Sage 50. Les ventes, les dépôts bancaires, les factures et les paiements des fournisseurs arrivent "
                 "dans Sage presque sans saisie manuelle."),
        ("sous_titre", "Ce que fait l'application"),
        ("puce", "Ventes : chaque nuit, les ventes Clover deviennent des factures de vente dans Sage (client "
                 "« Vente Hebdomadaire »)."),
        ("puce", "Encaissements : les dépôts Clover du compte Desjardins sont appliqués sur ces factures."),
        ("puce", "Factures fournisseurs : les factures PDF ou photos sont lues, reliées aux articles Sage et "
                 "importées comme factures d'achat."),
        ("puce", "Paiements fournisseurs : les avis de virement Interac reçus par courriel sont reliés aux factures "
                 "et saisis dans Sage."),
        ("puce", "Rapprochement bancaire : les relevés Desjardins sont rapprochés du compte 1055 ; ce qui manque est "
                 "enregistré dans Sage après votre confirmation."),
        ("sous_titre", "Comment ça fonctionne chaque nuit"),
        ("etape", "1. À l'heure choisie (1 h par défaut), l'application lit dans Sage les factures « Vente "
                  "AAAA-MM-JJ » déjà importées et repère chaque jour sans facture depuis la date de départ."),
        ("etape", "2. Elle récupère dans Clover les ventes de ces jours, du plus ancien au plus récent : un jour "
                  "manqué (même au milieu de la période) est rattrapé en premier."),
        ("etape", "3. Elle relie chaque article Clover à son numéro d'article Sage (correspondance des articles)."),
        ("etape", "4. Elle prépare une facture par jour du lundi au jeudi et une seule pour le vendredi, le samedi "
                  "et le dimanche : une ligne par article, montant = ventes nettes Clover, taxes TPS + TVQ (code GQ) "
                  "pour les articles taxés."),
        ("etape", "5. Elle importe les factures dans Sage, vérifie chacune d'elles, puis encaisse les dépôts des "
                  "seules ventes importées pendant ce traitement et saisit les paiements fournisseurs que vous avez "
                  "confirmés."),
        ("etape", "6. Elle vous envoie un compte rendu par courriel : succès, ou liste des points à corriger, avec "
                  "le journal en pièces jointes Excel (Ventes, Encaissements, Paiements fournisseurs, Journal)."),
        ("sous_titre", "Contrôles de sécurité"),
        ("puce", "Jamais deux fois la même facture : une date ou un numéro déjà présent dans Sage est ignoré."),
        ("puce", "Un jour qui pose problème (article non relié, compte manquant…) est bloqué seul, ainsi que "
                 "son encaissement ; pour une vente de fin de semaine, c'est toute la fin de semaine. Les autres "
                 "jours continuent ; le jour bloqué est repris en priorité la nuit suivante, une fois corrigé."),
        ("puce", "Une ancienne facture dont le numéro ne correspond pas à sa date dans Sage (ex. « Vente "
                 "2026-06-07 » datée du 2025-06-07) est signalée et ignorée."),
        ("puce", "Deux formats différents (ex. 500 g et 1 kg) ne sont jamais confondus."),
        ("puce", "Le total de chaque facture est égal aux ventes nettes Clover de la journée."),
        ("puce", "Rien n'est saisi sans contrôle du total, et chaque saisie est vérifiée ensuite dans Sage."),
        ("puce", "Les mots de passe et le jeton Clover sont gardés dans le coffre-fort de Windows."),
        ("sous_titre", "Pour commencer"),
        ("para", "Suivez la liste « Mise en route » ci-dessus : chaque étape passe au vert quand elle est faite. "
                 "Le « Guide de configuration » décrit chaque étape et le mode opératoire au quotidien ; « Aide / FAQ » "
                 "répond aux questions courantes. Le manuel d'utilisation illustré (PDF) est dans le menu Démarrer, "
                 "dossier MVOGMBI_Sync, avec le document d'architecture (composants, données et diagrammes de "
                 "flux)."),
        ("sous_titre", "À propos"),
        ("para", f"MVOGMBI_Sync version {VERSION} — Marché MVOG-MBI Sherbrooke, épicerie africaine & caribéenne."),
        ("para", "Logiciels reliés : Clover (point de vente) et Sage 50 Comptabilité, Édition canadienne."),
        ("para", f"Conçu et développé par {EDITEUR}"),
        ("para", f"{COPYRIGHT} — Tous droits réservés."),
    ],
    "en": [
        ("titre", "Welcome to MVOGMBI_Sync"),
        ("para", "MVOGMBI_Sync connects the Clover point of sale of Marché MVOG-MBI Sherbrooke to the Sage 50 "
                 "accounting software. Sales, bank deposits, supplier invoices and supplier payments reach Sage with "
                 "almost no manual entry."),
        ("sous_titre", "What the application does"),
        ("puce", "Sales: every night, Clover sales become sales invoices in Sage (customer “Vente Hebdomadaire”)."),
        ("puce", "Receipts: the Clover deposits in the Desjardins account are applied to these invoices."),
        ("puce", "Supplier invoices: PDF or photo invoices are read, linked to Sage items and imported as purchase "
                 "invoices."),
        ("puce", "Supplier payments: the Interac transfer notices received by email are linked to the invoices and "
                 "entered in Sage."),
        ("puce", "Bank reconciliation: Desjardins statements are reconciled with account 1055; what is missing is "
                 "recorded in Sage after your confirmation."),
        ("sous_titre", "How it works every night"),
        ("etape", "1. At the chosen time (1 a.m. by default), the application reads in Sage the last "
                  "“Vente YYYY-MM-DD” invoice already imported."),
        ("etape", "2. It retrieves from Clover the sales of every day without an invoice since the start date, "
                  "oldest first: a missed day (even in the middle of the period) is caught up first."),
        ("etape", "3. It links each Clover item to its Sage item number (item mapping)."),
        ("etape", "4. It prepares one invoice per day from Monday to Thursday and a single one for Friday, Saturday "
                  "and Sunday: one line per item, amount = Clover net sales, GST + QST (code GQ) for taxable items."),
        ("etape", "5. It imports the invoices into Sage, checks each one, then records the deposits of the sales "
                  "imported during this run only and enters the supplier payments you have confirmed."),
        ("etape", "6. It emails you a report: success, or the list of points to fix, with the log as Excel "
                  "attachments (Sales, Receipts, Supplier payments, Log)."),
        ("sous_titre", "Safety checks"),
        ("puce", "Never the same invoice twice: a date or number already in Sage is skipped."),
        ("puce", "A day with a problem (unlinked item, missing account…) is blocked alone, with its receipt; for a "
                 "weekend sale, the whole weekend. The other days continue; the blocked day is retried first the "
                 "following night, once fixed."),
        ("puce", "An old invoice whose number does not match its date in Sage (e.g. “Vente 2026-06-07” dated "
                 "2025-06-07) is reported and ignored."),
        ("puce", "Two different sizes (e.g. 500 g and 1 kg) are never mixed up."),
        ("puce", "Each invoice total equals the day's Clover net sales."),
        ("puce", "Nothing is entered without checking the total, and every entry is then verified in Sage."),
        ("puce", "Passwords and the Clover token are kept in the Windows vault."),
        ("sous_titre", "Getting started"),
        ("para", "Follow the “Getting started” checklist above: each step turns green once done. The “Setup guide” "
                 "describes every step and the daily operating procedure; “Help / FAQ” answers common questions. "
                 "The illustrated user manual (PDF) is in the Start menu, MVOGMBI_Sync folder, with the architecture "
                 "document (components, data and flow diagrams)."),
        ("sous_titre", "About"),
        ("para", f"MVOGMBI_Sync version {VERSION} — Marché MVOG-MBI Sherbrooke, African & Caribbean grocery."),
        ("para", "Connected software: Clover (point of sale) and Sage 50 Accounting, Canadian Edition."),
        ("para", f"Designed and developed by {EDITEUR}"),
        ("para", f"{COPYRIGHT} — All rights reserved."),
    ],
}

FAQ = {
    "fr": [
        ("titre", "Aide / Questions fréquentes"),
        ("sous_titre", "Fonctionnement général"),
        ("question", "L'ordinateur doit-il rester allumé la nuit ?"),
        ("reponse", "Oui. À l'heure du traitement, l'ordinateur doit être allumé et votre session Windows ouverte "
                    "(elle peut être verrouillée). Si l'ordinateur était éteint, les jours manqués sont rattrapés la "
                    "nuit suivante."),
        ("question", "Sage doit-il être ouvert ou fermé ?"),
        ("reponse", "Fermé. L'import et les saisies exigent que personne ne soit dans le fichier d'entreprise : "
                    "l'application ouvre Sage elle-même, sans rien afficher, puis le referme. Si Sage est ouvert à "
                    "l'heure du traitement, l'import échoue et il est repris la nuit suivante."),
        ("question", "Une fenêtre de Sage (mot de passe, résumé d'import) va-t-elle s'afficher ?"),
        ("reponse", "Non : tout se fait sans affichage. Si vous ouvrez vous-même un fichier .IMP (double-clic), ses "
                    "fenêtres apparaissent normalement : elles ne viennent pas de MVOGMBI_Sync."),
        ("question", "Où sont mes mots de passe ?"),
        ("reponse", "Dans le coffre-fort de Windows (Gestionnaire d'identification), jamais dans un fichier. Pour "
                    "les changer, tapez le nouveau mot de passe dans la page concernée puis « Enregistrer la "
                    "configuration ». « •••• » signifie qu'un mot de passe est déjà enregistré."),
        ("question", "Où trouver les journaux ?"),
        ("reponse", "Bouton « Dossier des données » du Tableau de bord : journal_automatique.log (chaque "
                    "traitement), journal_imports.csv (chaque facture), sauvegardes de la correspondance."),
        ("sous_titre", "Ventes et correspondance"),
        ("question", "Que se passe-t-il si un jour est « Bloqué » ?"),
        ("reponse", "Le courriel indique la raison (ex. article Clover non relié à Sage, article Sage sans compte "
                    "de produits). Corrigez-la ; le traitement reprendra automatiquement ce jour-là la nuit "
                    "suivante. Vous pouvez aussi cliquer sur « Lancer maintenant » dans le Tableau de bord."),
        ("question", "Un article renommé ou supprimé dans Clover bloque d'anciennes ventes."),
        ("reponse", "Dans Clover, renommer un article en crée souvent un nouveau : les ventes d'avant gardent l'ancien "
                    "article et l'ancien nom. Page « Articles > Correspondance » : « Mettre à jour depuis Clover et Sage », "
                    "puis le filtre « Supprimés ou renommés dans Clover ». Chaque ancien article y figure avec, quand "
                    "il est trouvé, le nouveau nom Clover et son article Sage proposés (« Autres suggestions ») : "
                    "« Accepter la proposition » s'ils sont bons, sinon choisissez l'article Sage, puis « Enregistrer "
                    "les modifications ». Les jours bloqués sont repris au traitement suivant. Les montants saisis à "
                    "la caisse sans article (« Article personnalisé ») se relient de la même façon."),
        ("question", "Un nouvel article a été créé dans Clover : que faire ?"),
        ("reponse", "S'il porte exactement le même nom qu'un article Sage, il est relié automatiquement. Sinon, "
                    "ouvrez la page « Articles > Correspondance », filtre « À traiter », choisissez l'article Sage et cliquez "
                    "sur « Confirmer l'article choisi », puis « Enregistrer les modifications ». S'il n'existe pas "
                    "dans Sage, créez-le d'abord dans Sage (avec son compte de produits)."),
        ("question", "Pourquoi l'application refuse-t-elle de relier 500 g et 1 kg ?"),
        ("reponse", "Deux formats différents sont deux articles différents : les relier fausserait l'inventaire. "
                    "Créez dans Sage un article par format."),
        ("question", "« Article Sage sans compte de produits » : comment corriger ?"),
        ("reponse", "Dans Sage, ouvrez l'article, onglet « Associé », et choisissez le compte de produits 40xx qui "
                    "correspond au compte d'actif 15xx (ex. 1514 Stock - Épices → 4014 Produit des Ventes - Épices)."),
        ("question", "Comment rattraper une période ancienne (plusieurs mois) ?"),
        ("reponse", "Réglez le « Premier jour à importer » dans la page Sage 50 si Sage ne contient encore aucune "
                    "facture journalière, puis lancez le traitement : il importe les factures jusqu'à hier (une par "
                    "jour, une par fin de semaine)."),
        ("question", "Les taxes de Sage diffèrent de quelques cents de celles de Clover."),
        ("reponse", "C'est normal : Clover arrondit les taxes commande par commande, Sage les calcule sur la "
                    "facture. Le montant des ventes (hors taxes) est, lui, identique au cent près."),
        ("sous_titre", "Encaissements"),
        ("question", "Pourquoi le dépôt ne couvre-t-il pas toute la facture ?"),
        ("reponse", "Le dépôt Clover ne contient que les ventes par carte (crédit et débit). La part payée en "
                    "espèces reste due sur la facture jusqu'à son propre encaissement."),
        ("question", "Un dépôt reste « À saisir dans Sage » : pourquoi ?"),
        ("reponse", "La facture correspondante n'est pas encore dans Sage, ou le dépôt dépasse le solde dû "
                    "(déjà encaissé autrement). Vérifiez la facture, puis recalculez ; un jour férié peut aussi "
                    "décaler un dépôt d'un jour."),
        ("sous_titre", "Factures fournisseurs"),
        ("question", "Les factures arrivent par courriel : faut-il les enregistrer à la main ?"),
        ("reponse", "Non. Page « Administration > Courriel », carte « Factures fournisseurs reçues par courriel » : indiquez les "
                    "expéditeurs (ou laissez vide : tout courriel dont le sujet ou la pièce jointe parle de facture) "
                    "et la date de départ. Page « Fournisseur > Factures fournisseurs », « 📧 Lire le courriel » copie les PDF et photos joints puis les "
                    "lit ; le traitement de nuit le fait aussi. La boîte est celle des avis Interac, en lecture "
                    "seule ; chaque pièce jointe n'est prise qu'une fois. Une pièce jointe qui n'est pas une facture "
                    "de marchandises s'écarte (« Écarter »)."),
        ("question", "Comment créer un nouvel article dans Clover et dans Sage ?"),
        ("reponse", "Page « Fournisseur > Factures fournisseurs », ligne de la facture : « 🆕 Créer l'article » (prix d'achat = prix Sage de la ligne), ou "
                    "« Articles > Créer un article » (les deux) et « Créer l'article dans Sage » (article Clover "
                    "existant). Clover : nom, prix = prix d'achat + 40 % (modifiable), type de prix, taxes, catégorie, "
                    "coût, code du produit facultatif, UGS = date de péremption (obligatoire), stock. Sage : n° "
                    "proposé (préfixe de la catégorie + numéro suivant), description et comptes de la table « Comptes "
                    "par catégorie… » (proposée à partir des articles déjà reliés). L'application crée la fiche dans "
                    "Sage (Sage ouvert sur le bon fichier, sinon elle l'ouvre elle-même), puis l'article dans Clover, "
                    "et les relie (« Confirmé »). Le jeton Clover doit avoir le droit « Inventaire » en écriture."),
        ("question", "Comment faire l'inventaire dans Clover et Sage en même temps ?"),
        ("reponse", "« Articles > Inventaire Clover et Sage » : « Exporter l'inventaire » écrit un fichier Excel (code et description "
                    "Clover et Sage, quantité Clover, quantité Sage, écart, coût unitaire). Inscrivez les quantités "
                    "comptées dans la colonne jaune, puis « Saisir l'inventaire compté » : le stock Clover et le stock "
                    "Sage deviennent la quantité comptée (ajustement d'inventaire dans Sage, vérifié dans la base). Le "
                    "rapport de saisie (sortie/inventaire) donne, par article, le stock avant et après et le coût de "
                    "l'ajustement (variation de la valeur du stock dans Sage), avec le total des plus, des moins et le "
                    "coût net. Les stocks sont relus juste avant la saisie : un article qui a bougé depuis l'export "
                    "est quand même ramené à la quantité comptée."),
        ("question", "Où voir la liste des articles Clover et leurs dates de péremption ?"),
        ("reponse", "« Articles > Articles Clover » : ID Clover, nom, prix, type de prix, unité de prix, code produit, "
                    "date de péremption, quantité et catégories ; recherche, filtres (catégorie, type de prix, stock), "
                    "tri par colonne et export. La date de péremption est l'UGS de Clover lue comme une date "
                    "(JJ/MM/AAAA) ; une UGS qui n'est pas une date n'est pas affichée. « Effacer les UGS qui ne sont "
                    "pas des dates… » les liste ; cochez celles à vider dans Clover (chaque UGS effacée est notée dans "
                    "donnees/journal_ugs_effacees.csv)."),
        ("question", "Comment imprimer un tableau ?"),
        ("reponse", "Liste « ⬇ Exporter ▾ » de la page (ou clic droit sur le tableau) : « 🖨 Imprimer… ». Le tableau "
                    "complet (toutes ses lignes) s'ouvre dans le navigateur avec la boîte d'impression de Windows : "
                    "choix de l'imprimante, aperçu, orientation. La même liste exporte en Excel, CSV ou PDF. "
                    "L'impression et les PDF portent un en-tête : logo, nom, adresse, téléphone et site web de "
                    "l'entreprise (lus dans Clover une fois par jour), titre du document, date. Pour changer ces "
                    "informations, modifiez-les dans Clover (Compte et configuration > Informations sur "
                    "l'entreprise)."),
        ("question", "Qui peut exporter des données ?"),
        ("reponse", "C'est un droit du profil (« Administration > Utilisateurs », case « Exporter les données »). "
                    "Sans ce droit, les boutons « Exporter », « Excel » et « PDF de la page », le clic droit "
                    "d'export des tableaux et l'export des graphiques disparaissent ou sont refusés. Par défaut : "
                    "l'administrateur et le comptable peuvent exporter, l'employé non."),
        ("question", "Comment voir les statistiques jour par jour ?"),
        ("reponse", "« État > Statistiques Clover » : sur les vues par article, catégorie, employé, client, mode de "
                    "paiement, carte, appareil et bénéfices, cochez « Détail par jour » : une ligne par jour, avec la "
                    "date en premier (le jour le plus récent en haut). « État > Recherche dans l'historique » : "
                    "« Par : Article par jour » ou « Catégorie par jour » pour les statistiques client, fournisseur "
                    "et employé. Changer de type de recherche garde le client, le fournisseur ou l'employé choisi, la "
                    "plage d'articles, la catégorie et la période ; « Réinitialiser les filtres » les vide."),
        ("question", "Comment transférer des articles d'un point de vente à l'autre ?"),
        ("reponse", "« Articles > Transferts entre magasins » : « Nouveau transfert », point de vente de départ "
                    "et d'arrivée, date, puis les articles Sage et leurs quantités (le stock Sage des deux dépôts "
                    "s'affiche ; en jaune : stock de départ insuffisant). « Transférer » : dans Sage, transfert entre "
                    "les deux dépôts (même valeur, sans vente), vérifié dans la base ; dans Clover, stock diminué au "
                    "départ et augmenté à l'arrivée (articles reliés dans la correspondance de chaque point de vente). "
                    "Un transfert n'est jamais fait deux fois ; « À compléter » : relancez-le après correction."),
        ("question", "Où voir les statistiques d'un client, d'un fournisseur ou d'un employé ?"),
        ("reponse", "« État > Recherche dans l'historique » : « Statistiques client » (ventes de Sage), "
                    "« Statistiques fournisseur » (achats moins retours dans Sage) ou « Statistiques employé » (ventes "
                    "Clover), puis « Par : Article » ou « Catégorie ». Période et plage d'articles (du n° … au n° …) "
                    "facultatives. Recherche « Article » avec « au » : chaque article de la plage à la suite de "
                    "l'autre, avec son total."),
        ("question", "Comment prendre les factures d'un fournisseur qui n'écrit jamais « facture » ?"),
        ("reponse", "Page « Administration > Courriel », carte « Factures fournisseurs reçues par courriel », champ « Textes dans le courriel » : "
                    "par exemple « 11983938 Canada Inc Brisk ». Les pièces jointes de tout courriel qui contient l'un "
                    "de ces textes (sujet, expéditeur, message ou nom du fichier) sont prises ; plusieurs textes "
                    "séparés par des points-virgules."),
        ("question", "Comment mettre les coûts Clover au coût moyen de Sage ?"),
        ("reponse", "« Articles > Coûts Clover depuis Sage » : pour chaque article Clover relié, la fenêtre montre le "
                    "prix de vente, le coût Clover et le coût moyen (CUMP) de Sage. Cochez les lignes à mettre à jour, "
                    "puis « Mettre à jour les coûts Clover » : le coût Sage remplace le coût Clover. Jamais de valeur "
                    "aberrante : un CUMP absent, plus de 5 fois le prix de vente ou sous 5 % du prix ne peut pas être "
                    "coché ; un CUMP égal ou supérieur au prix, très loin du coût Clover ou partagé par plusieurs "
                    "articles Clover est proposé décoché (à vérifier)."),
        ("question", "Comment corriger les comptes des articles dans Sage ?"),
        ("reponse", "« Comptabilité > Comptes Sage par catégorie » : la table donne, pour chaque catégorie Clover, les "
                    "comptes d'actif, de produits, de CMV et d'écart (écart = CMV). « Articles Sage à corriger… » "
                    "liste les articles de Sage dont un compte diffère de la table (catégorie des articles Clover "
                    "reliés, sinon celle du compte d'actif). Cochez les lignes puis « Corriger dans Sage » : "
                    "l'application change les comptes dans la fiche de chaque article et vérifie le résultat dans "
                    "Sage. Un changement du compte d'actif est proposé décoché : à décider."),
        ("question", "Que fait « Importer » dans Clover ?"),
        ("reponse", "Après l'import vérifié dans Sage, pour chaque article de la facture : stock Clover = stock "
                    "actuel + Qté Sage reçue, et coût Clover = nouveau prix d'achat (Prix Sage). L'article Clover est "
                    "celui relié à la page « Articles > Correspondance » ; un n° Sage relié à plusieurs articles Clover reçoit le coût, mais son "
                    "stock est à répartir à la main. Une facture n'est jamais ajoutée deux fois au stock "
                    "(journal_stock_clover.csv)."),
        ("question", "Une facture prête à importer a déjà été saisie dans Sage à la main."),
        ("reponse", "Elle est archivée (« Fournisseur > Factures fournisseurs archivées ») et retirée de la liste de la "
                    "page « Fournisseur > Factures fournisseurs », sans import : même fournisseur et même n°, avec ou sans préfixe (« FA-2581353 »). "
                    "Le contrôle se fait à l'import, avec « Fournisseurs et articles Sage » et pendant le traitement "
                    "de nuit."),
        ("question", "La facture n'est pas lue (photo, scan, écriture à la main) : que faire ?"),
        ("reponse", "Les PDF numériques sont lus directement ; les scans et photos passent par la reconnaissance de "
                    "texte de Windows. Si la lecture est incomplète, complétez l'en-tête et les lignes à la main "
                    "(bouton ➕ pour ajouter une ligne) : l'application garde votre saisie."),
        ("question", "Le fournisseur vend au carton, nous vendons à l'unité : comment faire ?"),
        ("reponse", "Indiquez le « Facteur » de la ligne (ex. 12 unités par carton). Qté Sage = Qté × Facteur ; "
                    "Montant = Qté × Prix fournisseur ; Prix Sage = Montant / Qté Sage. Le facteur est retenu pour "
                    "ce fournisseur et cet article."),
        ("question", "L'import d'une facture fournisseur est refusé."),
        ("reponse", "Lisez le message : fiche du fournisseur sans la case « Ce fournisseur utilise mes n° "
                    "d'articles » (onglet Importer/Exporter), article Sage sans compte d'actif, facture déjà présente "
                    "dans Sage (même avec un préfixe « FA- »), ou Sage ouvert."),
        ("question", "Comment retirer une facture qui ne doit pas être traitée ?"),
        ("reponse", "Sélectionnez-la puis « Écarter » (ou touche Suppr) : le fichier est déplacé dans le dossier "
                    "« ecartees » et ne réapparaît plus."),
        ("sous_titre", "Paiements fournisseurs"),
        ("question", "Comment les paiements aux fournisseurs arrivent-ils dans Sage ?"),
        ("reponse", "Page « Comptabilité > Paiements fournisseur » : « Actualiser » lit les avis Interac reçus depuis la date "
                    "choisie et propose le fournisseur et la facture. Vous confirmez chaque virement. Les paiements "
                    "confirmés sont saisis (compte 1055, « Comptant », à la date du virement) la nuit, ou tout de "
                    "suite avec « Payer dans Sage » (Sage fermé)."),
        ("question", "Un virement paie plusieurs factures, ou seulement une partie d'une facture."),
        ("reponse", "Sélectionnez plusieurs factures avec Ctrl+clic : le virement est réparti de la plus ancienne "
                    "à la plus récente, seule la dernière pouvant être payée en partie. Un paiement partiel d'une "
                    "seule facture est accepté. Un virement plus grand que le solde des factures choisies est refusé."),
        ("question", "Un virement est « Déjà dans Sage » : qu'est-ce que cela veut dire ?"),
        ("reponse", "Un paiement du même montant, le même jour, au même fournisseur existe déjà dans Sage (saisi à "
                    "la main par exemple) : il n'est pas saisi une deuxième fois."),
        ("question", "Le virement n'est pas pour un fournisseur (remboursement, prêt…)."),
        ("reponse", "Cliquez sur « Ignorer (pas un fournisseur) » : il ne sera plus proposé."),
        ("sous_titre", "Rapprochement bancaire"),
        ("question", "L'« écart d'ouverture » n'est pas nul : pourquoi ?"),
        ("reponse", "Au début de la période, le solde du compte 1055 dans Sage était déjà différent de celui de la "
                    "banque : des mouvements plus anciens manquent dans Sage. Chargez aussi les relevés précédents."),
        ("question", "Un mouvement reste « Absent de Sage » alors qu'il est dans Sage."),
        ("reponse", "Le montant ou la date diffère (plus de 7 jours avant ou 3 jours après) : corrigez l'écriture dans "
                    "Sage, ou cliquez sur « Ignorer » si elle est juste."),
        ("question", "Un virement Interac reçu ou un dépôt au guichet est « À encaisser sur les ventes »."),
        ("reponse", "C'est de l'argent des ventes (espèces) : il ne devient pas une écriture de journal. La page « Comptabilité > Encaissements » "
                    "l'encaisse sur la facture de vente (Interac : la vente du jour du virement ; dépôt d'espèces : les "
                    "factures dont il reste des espèces à encaisser, de la plus ancienne à la plus récente)."),
        ("question", "Un dépôt de salaire est « Paie absente de Sage »."),
        ("reponse", "Les salaires sont reliés aux paies de Sage (source « PAY… ») du même montant, même versés plusieurs "
                    "semaines plus tard. Aucune paie de ce montant : saisissez ou corrigez la paie dans le module Paie "
                    "de Sage (un cent d'écart suffit à l'empêcher), puis « Actualiser »."),
        ("question", "Comment exporter un tableau en Excel, en CSV ou en PDF ?"),
        ("reponse", "Bouton « ⬇ Exporter » au-dessus du tableau (pages Correspondance, Encaissements, Factures et "
                    "Paiements fournisseurs, Rapprochement, Rapports), ou clic droit sur n'importe quel tableau : "
                    "« Exporter en Excel », « Exporter en CSV » ou « Exporter en PDF ». Ce qui est affiché est exporté "
                    "(filtre et recherche compris) ; le CSV utilise le séparateur « ; » d'Excel en français ; le PDF "
                    "(fait par Microsoft Edge) est prêt à imprimer, à l'horizontale pour les tableaux larges."),
        ("question", "Comment exporter un graphique ou toute une page de statistiques en PDF ?"),
        ("reponse", "Clic droit sur le graphique : « Exporter le graphique en PDF… » ou « Enregistrer le graphique en "
                    "image (PNG)… ». Bouton « 📕 PDF de la page » en haut des statistiques Clover : la page affichée "
                    "(Accueil, Aperçu des ventes, Aperçu financier ou un état) avec ses indicateurs, ses graphiques et "
                    "son tableau complet, la période et les filtres en sous-titre."),

        ("sous_titre", "Plusieurs points de vente"),
        ("question", "Comment ajouter un autre point de vente Clover ?"),
        ("reponse", "Page « Administration > Clover », carte « Points de vente » : « Ajouter un point de vente », puis son nom, son "
                    "identifiant marchand Clover, son jeton API, son client Sage, son dépôt Sage (emplacement "
                    "d'inventaire) et le préfixe de ses factures (ex. « V2 » : « V2 2026-10-23/25 »). Chaque point de "
                    "vente a ses factures, son client et sa correspondance d'articles (« Articles > Correspondance », liste « Point de "
                    "vente »). Le point de vente n° 1 garde ses réglages : factures « Vente … », client « Vente "
                    "Hebdomadaire ». Les ventes vont dans les mêmes comptes de produits et les dépôts bancaires dans "
                    "le même compte 1055. Dans Sage, créez d'abord le client (« Ce client utilise mes n° articles » "
                    "coché) et le dépôt."),
        ("question", "Comment traiter un seul point de vente, ou tous ?"),
        ("reponse", "Tableau de bord, liste « Point de vente » : « Tous les points de vente » les traite à la suite, "
                    "chacun dans son dépôt Sage ; sinon, seul celui choisi. Le traitement de nuit les traite tous. "
                    "Pages 5 et 7 : choisissez le point de vente en haut de la page."),
        ("note", "Tant que l'import dans un autre dépôt que « Emplacement par défaut » n'a pas été validé par un essai "
                 "sur la copie du fichier d'entreprise, les factures d'un point de vente rangé dans un autre dépôt "
                 "restent bloquées (message au compte rendu)."),

        ("sous_titre", "Utilisateurs et accès"),
        ("question", "Comment donner accès à l'application à un employé ?"),
        ("reponse", "Connecté en administrateur, page « Utilisateurs » : nom, profil, mot de passe, puis « Ajouter ». "
                    "Profils de départ : Administrateur (tout, y compris la configuration et les utilisateurs), "
                    "Comptable (pages 5 à 10), Employé (Accueil et Tableau de bord). À droite, choisissez un profil, "
                    "cochez ses pages puis « Enregistrer les accès » : une page non cochée disparaît du menu à la "
                    "prochaine connexion. « ➕ » crée un nouveau profil."),
        ("question", "Comment limiter un profil à certains points de vente ?"),
        ("reponse", "Page « Utilisateurs », à droite, « Points de vente permis » : décochez « Tous les points de "
                    "vente », cochez un ou plusieurs points de vente, puis « Enregistrer les accès ». Les personnes "
                    "de ce profil ne voient et ne traitent que ceux-là (Tableau de bord, pages 5 et 7). "
                    "L'administrateur les voit toujours tous."),
        ("question", "Un utilisateur a oublié son mot de passe."),
        ("reponse", "Un administrateur choisit le compte puis « Nouveau mot de passe ». Chacun peut changer le sien "
                    "en bas du menu (« Changer mon mot de passe »). Si le seul administrateur a oublié le sien : "
                    "fermez l'application et supprimez donnees\\utilisateurs.json ; au lancement suivant, le compte "
                    "administrateur est recréé (la configuration et les données restent). Gardez donc la session "
                    "Windows protégée par son propre mot de passe."),
        ("question", "L'application se verrouille toute seule."),
        ("reponse", "Après 5 minutes sans souris ni clavier, la fenêtre se cache : votre mot de passe la rouvre "
                    "(« Déverrouiller »), ou « Changer d'utilisateur » ramène à la connexion. Les traitements en cours "
                    "continuent. Délai réglable dans config.toml : [general] verrouillage_minutes (0 = jamais)."),
        ("question", "Le traitement de nuit a-t-il besoin d'une connexion ?"),
        ("reponse", "Non : la tâche planifiée travaille sans ouvrir de session dans l'application. La connexion protège "
                    "les pages de l'application ; les mots de passe ne sont jamais gardés, seulement une empreinte "
                    "chiffrée, et chaque connexion est notée dans donnees\\journal_connexions.log."),

        ("sous_titre", "Courriel et installation"),
        ("question", "Je ne reçois pas les courriels."),
        ("reponse", "Vérifiez la page Courriel et cliquez sur « Envoyer un courriel de test ». Avec Gmail ou "
                    "Outlook, un « mot de passe d'application » est souvent nécessaire. Regardez aussi le dossier "
                    "des courriels indésirables."),
        ("question", "« 535 Incorrect authentication data » au courriel de test."),
        ("reponse", "Le serveur de courriel refuse l'utilisateur ou le mot de passe. L'utilisateur est en général "
                    "l'adresse complète (ex. notification@marchemvogmbi.com). Vérifiez le mot de passe en ouvrant le "
                    "webmail ; après plusieurs refus, le serveur peut faire patienter quelques minutes."),
        ("question", "« Sage refuse l'utilisateur mvogmbi_sync » au test de Sage."),
        ("reponse", "Le mot de passe de lecture enregistré n'est pas celui de l'utilisateur dans CE fichier "
                    "d'entreprise (chaque fichier, et chaque copie, a ses propres utilisateurs). Ouvrez le fichier "
                    "dans Sage avec sysadmin, Configuration > Définir les utilisateurs, vérifiez mvogmbi_sync et son "
                    "mot de passe, puis retapez le même mot de passe dans la page Sage 50."),
        ("question", "Mon jeton Clover a changé ou a expiré."),
        ("reponse", "Créez un nouveau jeton dans Clover (Compte et configuration > Jetons API, droits en lecture), "
                    "collez-le dans la page Clover, enregistrez, puis « Tester la connexion à Clover »."),
        ("question", "Après une réinstallation, tous les articles sont « à confirmer »."),
        ("reponse", "Le dossier de données de la nouvelle installation est vide. Page Automatisation > « Reprendre "
                    "une configuration existante… », choisissez l'ancien dossier : la correspondance validée, le "
                    "journal des imports et la configuration sont recopiés."),
        ("question", "Comment désinstaller ?"),
        ("reponse", "Paramètres Windows > Applications > MVOGMBI_Sync > Désinstaller. La tâche planifiée est "
                    "retirée ; vos données et votre configuration restent dans le dossier d'installation."),
    ],
    "en": [
        ("titre", "Help / Frequently asked questions"),
        ("sous_titre", "General"),
        ("question", "Must the computer stay on at night?"),
        ("reponse", "Yes. At run time the computer must be on and your Windows session open (it may be locked). "
                    "If the computer was off, missed days are caught up the following night."),
        ("question", "Should Sage be open or closed?"),
        ("reponse", "Closed. Imports and entries require nobody to be in the company file: the application opens "
                    "Sage itself, without showing anything, then closes it. If Sage is open at run time, the import "
                    "fails and is resumed the following night."),
        ("question", "Will a Sage window (password, import summary) appear?"),
        ("reponse", "No: everything happens without display. If you open an .IMP file yourself (double-click), its "
                    "windows appear normally: they do not come from MVOGMBI_Sync."),
        ("question", "Where are my passwords?"),
        ("reponse", "In the Windows vault (Credential Manager), never in a file. To change them, type the new "
                    "password in the relevant page then “Save configuration”. “••••” means a password is already "
                    "saved."),
        ("question", "Where are the logs?"),
        ("reponse", "“Data folder” button in the Dashboard: journal_automatique.log (each run), journal_imports.csv "
                    "(each invoice), mapping backups."),
        ("sous_titre", "Sales and item mapping"),
        ("question", "What happens if a day is “Blocked”?"),
        ("reponse", "The email gives the reason (e.g. Clover item not linked to Sage, Sage item without a revenue "
                    "account). Fix it; the run will resume that day automatically the following night. You can "
                    "also click “Run now” in the Dashboard."),
        ("question", "An item renamed or deleted in Clover blocks older sales."),
        ("reponse", "In Clover, renaming an item often creates a new one: earlier sales keep the old item and old "
                    "name. Item mapping page (5): “Update from Clover and Sage”, then the “Deleted or renamed in "
                    "Clover” filter. Each old item is listed with, when found, the new Clover name and its Sage item "
                    "proposed (“Other suggestions”): “Accept the suggestion” if they are right, otherwise choose the "
                    "Sage item, then “Save changes”. Blocked days are resumed by the next run. Amounts keyed at the "
                    "register without an item (“Article personnalisé”) are linked the same way."),
        ("question", "A new item was created in Clover: what should I do?"),
        ("reponse", "If it has exactly the same name as a Sage item, it is linked automatically. Otherwise open the "
                    "“Items > Mapping” page, filter “To handle”, choose the Sage item and click “Confirm the chosen "
                    "item”, then “Save changes”. If it does not exist in Sage, create it in Sage first (with its "
                    "revenue account)."),
        ("question", "Why does the application refuse to link 500 g and 1 kg?"),
        ("reponse", "Two different sizes are two different items: linking them would distort the inventory. "
                    "Create one Sage item per size."),
        ("question", "“Sage item without a revenue account”: how do I fix it?"),
        ("reponse", "In Sage, open the item, “Linked” tab, and choose the 40xx revenue account matching the 15xx "
                    "asset account (e.g. 1514 Stock - Spices → 4014 Sales - Spices)."),
        ("question", "How do I catch up an old period (several months)?"),
        ("reponse", "Set the “First day to import” in the Sage 50 page if Sage does not yet contain any daily "
                    "invoice, then start the run: it imports the invoices up to yesterday (one per day, one per "
                    "weekend)."),
        ("question", "Sage taxes differ by a few cents from Clover's."),
        ("reponse", "This is normal: Clover rounds taxes order by order, Sage computes them on the invoice. The "
                    "sales amount (before taxes) is identical to the cent."),
        ("sous_titre", "Receipts"),
        ("question", "Why does the deposit not cover the whole invoice?"),
        ("reponse", "The Clover deposit only contains card sales (credit and debit). The part paid in cash stays "
                    "due on the invoice until it is received separately."),
        ("question", "A deposit stays “To enter in Sage”: why?"),
        ("reponse", "The matching invoice is not in Sage yet, or the deposit exceeds the balance due (already "
                    "received another way). Check the invoice, then recalculate; a public holiday may also shift a "
                    "deposit by one day."),
        ("sous_titre", "Supplier invoices"),
        ("question", "Invoices arrive by email: do I have to save them by hand?"),
        ("reponse", "No. “Administration > Email” page, “Supplier invoices received by email” card: enter the senders (or leave "
                    "empty: any email whose subject or attachment mentions an invoice) and the start date. “Supplier > Supplier invoices”, "
                    "“📧 Read email” copies the attached PDFs and photos, then reads them; the night run does it too. "
                    "The mailbox is the one of the Interac notices, read only; each attachment is taken only once. An "
                    "attachment that is not a goods invoice is set aside (“Set aside”)."),
        ("question", "How do I create a new item in Clover and in Sage?"),
        ("reponse", "“Supplier > Supplier invoices”, invoice line: “🆕 Create the item” (purchase price = Sage price of the line), or “Items > Mapping”: "
                    "“🆕 Create an item” (both) and “Create the item in Sage” (existing Clover item). Clover: name, "
                    "price = purchase price + 40% (can be changed), price type, taxes, category, cost, optional "
                    "product code, SKU = expiry date (required), stock. Sage: suggested number (category prefix + "
                    "next number), description and accounts from the “Accounts by category…” table (suggested from "
                    "the items already linked). The application creates the record in Sage (Sage open on the right "
                    "file, otherwise it opens Sage itself), then the item in Clover, and links them (“Confirmed”). "
                    "The Clover token needs the “Inventory” write permission."),
        ("question", "How do I take the inventory in Clover and Sage at the same time?"),
        ("reponse", "“Items > Clover and Sage inventory”: “Export the inventory” writes an Excel file (Clover and Sage code and "
                    "description, Clover quantity, Sage quantity, difference, unit cost). Enter the counted quantities "
                    "in the yellow column, then “Enter the counted inventory”: the Clover stock and the Sage stock "
                    "become the counted quantity (inventory adjustment in Sage, checked in the database). The entry "
                    "report (sortie/inventaire) gives, for each item, the stock before and after and the adjustment "
                    "cost (change of the stock value in Sage), with the total gains, losses and net cost. Stocks are "
                    "read again just before the entry: an item that changed since the export is still brought to the "
                    "counted quantity."),
        ("question", "Where do I see the list of Clover items and their expiry dates?"),
        ("reponse", "“Items > Clover items”: Clover ID, name, price, price type, price unit, product code, expiry "
                    "date, quantity and categories; search, filters (category, price type, stock), sorting by column "
                    "and export. The expiry date is the Clover SKU read as a date (DD/MM/YYYY); a SKU that is not a "
                    "date is not shown. “Clear SKUs that are not dates…” lists them; check those to empty in Clover "
                    "(each cleared SKU is noted in donnees/journal_ugs_effacees.csv)."),
        ("question", "How do I print a table?"),
        ("reponse", "The page's “⬇ Export ▾” list (or right-click on the table): “🖨 Print…”. The complete table (all "
                    "its rows) opens in the browser with the Windows print dialog: printer, preview, orientation. "
                    "The same list exports to Excel, CSV or PDF. Prints and PDFs carry a header: logo, name, address, "
                    "phone and website of the business (read from Clover once a day), document title, date. To "
                    "change this information, edit it in Clover (Account & Setup > Business Information)."),
        ("question", "Who can export data?"),
        ("reponse", "It is a profile right (“Administration > Users”, “Export data” box). Without it, the “Export”, "
                    "“Excel” and “PDF of the page” buttons, the right-click export of tables and the export of charts "
                    "disappear or are refused. By default: the administrator and the accountant can export, the "
                    "employee cannot."),
        ("question", "How do I see the statistics day by day?"),
        ("reponse", "“Reports > Clover statistics”: on the views by item, category, employee, customer, payment "
                    "method, card, device and profits, check “Detail by day”: one row per day, with the date first "
                    "(most recent day at the top). “Reports > Search the history”: “By: Item by day” or “Category by "
                    "day” for customer, supplier and employee statistics. Changing the search type keeps the chosen "
                    "customer, supplier or employee, the item range, the category and the period; “Reset the "
                    "filters” empties them."),
        ("question", "How do I transfer items from one point of sale to another?"),
        ("reponse", "“Items > Transfers between stores”: “New transfer”, origin and destination point of "
                    "sale, date, then the Sage items and their quantities (the Sage stock of both locations is shown; "
                    "yellow: origin stock too low). “Transfer”: in Sage, a transfer between the two locations (same "
                    "value, no sale), checked in the database; in Clover, stock decreased at the origin and increased "
                    "at the destination (items linked in each point of sale's matching). A transfer is never done "
                    "twice; “To complete”: run it again after fixing."),
        ("question", "Where do I see the statistics of a customer, a supplier or an employee?"),
        ("reponse", "“Reports > Search the history”: “Customer statistics” (Sage sales), “Supplier statistics” "
                    "(Sage purchases minus returns) or “Employee statistics” (Clover sales), then “By: Item” or "
                    "“Category”. Period and item range (from no. … to no. …) are optional. “Item” search with “to”: "
                    "each item of the range one after the other, with its total."),
        ("question", "How do I take the invoices of a supplier who never writes “invoice”?"),
        ("reponse", "“Administration > Email”, “Supplier invoices received by email” card, “Texts in the email” field: for example "
                    "“11983938 Canada Inc Brisk”. The attachments of any email that contains one of these texts "
                    "(subject, sender, message or file name) are taken; several texts separated by semicolons."),
        ("question", "How do I set the Clover costs to the Sage average cost?"),
        ("reponse", "“Items > Clover costs from Sage”: for each linked Clover item, the window shows the selling "
                    "price, the Clover cost and the Sage average cost. Check the rows to update, then “Update the "
                    "Clover costs”: the Sage cost replaces the Clover cost. Never an outlier value: no average cost, "
                    "more than 5 times the selling price or under 5% of the price cannot be checked; an average cost "
                    "equal to or above the price, very far from the Clover cost or shared by several Clover items is "
                    "offered unchecked (to check)."),
        ("question", "How do I correct the item accounts in Sage?"),
        ("reponse", "“Accounting > Sage accounts by category”: the table gives, for each Clover category, the asset, "
                    "revenue, COGS and variance accounts (variance = COGS). “Sage items to correct…” lists the Sage "
                    "items with an account that differs from the table (category of the linked Clover items, "
                    "otherwise that of the asset account). Check the rows then “Correct in Sage”: the application "
                    "changes the accounts in each item record and checks the result in Sage. A change of the asset "
                    "account is offered unchecked: your decision."),
        ("question", "What does “Import” do in Clover?"),
        ("reponse", "After the import is verified in Sage, for each item of the invoice: Clover stock = current stock + "
                    "Sage quantity received, and Clover cost = new purchase price (Sage price). The Clover item is the "
                    "one linked on the “Items > Mapping” page; a Sage number linked to several Clover items gets the cost, but its stock "
                    "must be split by hand. An invoice is never added twice to the stock (journal_stock_clover.csv)."),
        ("question", "An invoice ready to import was already entered in Sage by hand."),
        ("reponse", "It is archived (“Supplier > Archived supplier invoices”) and removed from the “Supplier > Supplier invoices” page list, without "
                    "import: same supplier and same number, with or without prefix (“FA-2581353”). The check is made "
                    "at import, with “Sage suppliers and items” and during the night run."),
        ("question", "The invoice is not read (photo, scan, handwriting): what should I do?"),
        ("reponse", "Digital PDFs are read directly; scans and photos go through Windows text recognition. If the "
                    "reading is incomplete, complete the header and lines by hand (➕ button to add a line): the "
                    "application keeps your entry."),
        ("question", "The supplier sells by the case, we sell by the unit: how?"),
        ("reponse", "Enter the line's “Factor” (e.g. 12 units per case). Sage qty = Qty × Factor; Amount = Qty × "
                    "Supplier price; Sage price = Amount / Sage qty. The factor is remembered for this supplier and "
                    "item."),
        ("question", "A supplier invoice import is refused."),
        ("reponse", "Read the message: supplier record without “This vendor uses my item numbers” (Import/Export "
                    "tab), Sage item without an asset account, invoice already in Sage (even with an “FA-” prefix), "
                    "or Sage open."),
        ("question", "How do I remove an invoice that must not be processed?"),
        ("reponse", "Select it then “Set aside” (or the Delete key): the file is moved to the “ecartees” folder and "
                    "does not come back."),
        ("sous_titre", "Supplier payments"),
        ("question", "How do supplier payments get into Sage?"),
        ("reponse", "Page “Accounting > Supplier payments”: “Refresh” reads the Interac notices received since the chosen "
                    "date and suggests the supplier and invoice. You confirm each transfer. Confirmed payments are "
                    "entered (account 1055, “Cash”, at the transfer date) at night, or right away with “Pay in "
                    "Sage” (Sage closed)."),
        ("question", "A transfer pays several invoices, or only part of an invoice."),
        ("reponse", "Select several invoices with Ctrl+click: the transfer is split from the oldest to the most "
                    "recent, only the last one may be partly paid. A partial payment of a single invoice is accepted. "
                    "A transfer larger than the balance of the chosen invoices is refused."),
        ("question", "A transfer is “Already in Sage”: what does it mean?"),
        ("reponse", "A payment of the same amount, on the same day, to the same supplier already exists in Sage "
                    "(entered by hand, for example): it is not entered a second time."),
        ("question", "The transfer is not for a supplier (refund, loan…)."),
        ("reponse", "Click “Ignore (not a supplier)”: it will no longer be suggested."),
        ("sous_titre", "Bank reconciliation"),
        ("question", "The “opening difference” is not zero: why?"),
        ("reponse", "At the start of the period, the balance of account 1055 in Sage already differed from the bank's: "
                    "older transactions are missing from Sage. Load the previous statements too."),
        ("question", "A transaction stays “Missing from Sage” although it is in Sage."),
        ("reponse", "The amount or the date differs (more than 7 days before or 3 days after): fix the entry in Sage, "
                    "or click “Ignore” if it is correct."),
        ("question", "An Interac transfer received or an ATM deposit is “To receive on the sales”."),
        ("reponse", "It is sales money (cash): it does not become a journal entry. “Accounting > Receipts” records it on the sales "
                    "invoice (Interac: the sale of the transfer day; cash deposit: the invoices with cash still to "
                    "receive, oldest first)."),
        ("question", "A salary deposit is “Payroll missing from Sage”."),
        ("reponse", "Salaries are linked to the Sage payroll entries (source “PAY…”) of the same amount, even when "
                    "paid several weeks later. No payroll of that amount: enter or correct it in the Sage Payroll "
                    "module (one cent of difference is enough to prevent it), then “Refresh”."),
        ("question", "How do I export a table to Excel, CSV or PDF?"),
        ("reponse", "“⬇ Export” button above the table (Item mapping, Receipts, Supplier invoices and payments, "
                    "Reconciliation, Reports pages), or right-click any table: “Export to Excel”, “Export to CSV” or "
                    "“Export to PDF”. What is shown is exported (filter and search included); the CSV uses the “;” "
                    "separator of French Excel; the PDF (made by Microsoft Edge) is ready to print, in landscape for "
                    "wide tables."),
        ("question", "How do I export a chart or a whole statistics page to PDF?"),
        ("reponse", "Right-click the chart: “Export the chart to PDF…” or “Save the chart as an image (PNG)…”. The "
                    "“📕 Page PDF” button at the top of the Clover statistics: the page shown (Home, Sales overview, "
                    "Financial overview or a report) with its indicators, charts and full table, the period and filters "
                    "as subtitle."),

        ("sous_titre", "Several points of sale"),
        ("question", "How do I add another Clover point of sale?"),
        ("reponse", "“Administration > Clover” page, “Points of sale” card: “Add a point of sale”, then its name, Clover merchant "
                    "ID, API token, Sage customer, Sage warehouse (inventory location) and invoice prefix (e.g. "
                    "“V2”: “V2 2026-10-23/25”). Each point of sale has its own invoices, customer and item mapping "
                    "(“Items > Mapping”, “Point of sale” list). Point of sale no. 1 keeps its settings: “Vente …” invoices, "
                    "“Vente Hebdomadaire” customer. Sales go to the same revenue accounts and bank deposits to the "
                    "same 1055 account. In Sage, first create the customer (“This customer uses my item numbers” "
                    "ticked) and the warehouse."),
        ("question", "How do I process a single point of sale, or all of them?"),
        ("reponse", "Dashboard, “Point of sale” list: “All points of sale” processes them one after the other, each "
                    "in its Sage warehouse; otherwise only the one chosen. The night run processes them all. Pages 5 "
                    "and 7: choose the point of sale at the top of the page."),
        ("note", "Until importing into a warehouse other than “Emplacement par défaut” has been validated by a test "
                 "on the copy of the company file, the invoices of a point of sale stored in another warehouse stay "
                 "blocked (message in the report)."),

        ("sous_titre", "Users and access"),
        ("question", "How do I give an employee access to the application?"),
        ("reponse", "Signed in as administrator, “Users” page: name, profile, password, then “Add”. Starting "
                    "profiles: Administrator (everything, including setup and users), Accountant (pages 5 to 10), "
                    "Employee (Home and Dashboard). On the right, choose a profile, tick its pages, then “Save "
                    "access”: an unticked page disappears from the menu at the next sign-in. “➕” creates a new "
                    "profile."),
        ("question", "How do I limit a profile to some points of sale?"),
        ("reponse", "“Users” page, on the right, “Allowed points of sale”: untick “All points of sale”, tick one or "
                    "more points of sale, then “Save access”. People with this profile only see and process those "
                    "(Dashboard, pages 5 and 7). The administrator always sees them all."),
        ("question", "A user forgot their password."),
        ("reponse", "An administrator selects the account, then “New password”. Everyone can change their own at the "
                    "bottom of the menu (“Change my password”). If the only administrator forgot theirs: close the "
                    "application and delete donnees\\utilisateurs.json; at the next start, the administrator account "
                    "is created again (setup and data are kept). So keep the Windows session protected by its own "
                    "password."),
        ("question", "The application locks itself."),
        ("reponse", "After 5 minutes without mouse or keyboard, the window hides: your password reopens it "
                    "(“Unlock”), or “Switch user” goes back to sign-in. Running jobs continue. Delay set in "
                    "config.toml: [general] verrouillage_minutes (0 = never)."),
        ("question", "Does the nightly run need a sign-in?"),
        ("reponse", "No: the scheduled task works without signing in to the application. Signing in protects the "
                    "application pages; passwords are never kept, only an encrypted fingerprint, and every sign-in is "
                    "logged in donnees\\journal_connexions.log."),

        ("sous_titre", "Email and installation"),
        ("question", "I don't receive the emails."),
        ("reponse", "Check the Email page and click “Send a test email”. With Gmail or Outlook, an “app password” "
                    "is often required. Also check the junk folder."),
        ("question", "“535 Incorrect authentication data” with the test email."),
        ("reponse", "The mail server rejects the user or password. The user is usually the full address (e.g. "
                    "notification@marchemvogmbi.com). Check the password by opening the webmail; after several "
                    "rejections the server may make you wait a few minutes."),
        ("question", "“Sage rejects the mvogmbi_sync user” when testing Sage."),
        ("reponse", "The saved read password is not the user's password in THIS company file (each file, and each "
                    "copy, has its own users). Open the file in Sage as sysadmin, Setup > Set Up Users, check "
                    "mvogmbi_sync and its password, then type the same password in the Sage 50 page."),
        ("question", "My Clover token changed or expired."),
        ("reponse", "Create a new token in Clover (Account & Setup > API Tokens, read permissions), paste it in the "
                    "Clover page, save, then “Test the Clover connection”."),
        ("question", "After a reinstall, every item is “to confirm”."),
        ("reponse", "The new installation's data folder is empty. Automation page > “Import an existing "
                    "configuration…”, choose the former folder: the validated mapping, the import log and the "
                    "configuration are copied."),
        ("question", "How do I uninstall?"),
        ("reponse", "Windows Settings > Apps > MVOGMBI_Sync > Uninstall. The scheduled task is removed; your data "
                    "and configuration stay in the installation folder."),
    ],
}

GUIDE = {
    "fr": [
        ("titre", "Guide de configuration et mode opératoire"),
        ("para", "Ce guide décrit la mise en service complète de MVOGMBI_Sync, puis le mode opératoire au "
                 "quotidien : ventes, encaissements, factures et paiements des fournisseurs."),
        ("sous_titre", "Avant de commencer"),
        ("puce", "Un ordinateur Windows qui reste allumé la nuit, avec Sage 50 Comptabilité 2026 installé."),
        ("puce", "L'accès administrateur au compte Clover du marché."),
        ("puce", "Le mot de passe de l'utilisateur sysadmin de Sage."),
        ("puce", "Une adresse courriel d'envoi (ex. notification@marchemvogmbi.com) et son mot de passe, ainsi que "
                 "la boîte qui reçoit les avis de virement Interac (ex. contact@marchemvogmbi.com)."),
        ("note", "Conseil : faites tous les essais sur une COPIE du fichier d'entreprise (Sage : Fichier > "
                 "Enregistrer une copie). Le vrai fichier n'est choisi qu'à l'étape « Mise en production »."),

        ("sous_titre", "Étape 1 — Clover"),
        ("etape", "1. Connectez-vous au tableau de bord Clover (www.clover.com). L'identifiant marchand (13 "
                  "caractères) est dans l'adresse de la page, après « /m/ »."),
        ("etape", "2. Compte et configuration > Jetons API > Créer un jeton. Donnez-lui un nom (ex. MVOGMBI_Sync) et "
                  "les droits en LECTURE : Commandes, Inventaire, Paiements, Marchand."),
        ("etape", "3. Page « Administration > Clover » : collez l'identifiant marchand et le jeton, puis cliquez sur « Tester la "
                  "connexion à Clover » : le nom du marché doit s'afficher."),

        ("sous_titre", "Étape 2 — Sage 50"),
        ("etape", "1. Utilisateur de lecture. Ouvrez le fichier dans Sage avec sysadmin : Configuration > Définir "
                  "les utilisateurs > Ajouter. Nom : mvogmbi_sync, avec un mot de passe. Droits : « Vue » sur "
                  "Stocks & Services, Clients & Ventes et Fournisseurs & Achats ; « Droits d'accès aux produits "
                  "tiers » : Consultation seule."),
        ("etape", "2. Fiche du client « Vente Hebdomadaire » : onglet Importer/Exporter, cochez « Ce client utilise "
                  "mes n° d'articles ». Faites de même sur la fiche de chaque fournisseur dont vous importez les "
                  "factures."),
        ("etape", "3. Comptes des articles : chaque article doit avoir un compte de produits. Règle du marché : "
                  "compte d'actif 15xx → produits 40xx et coût des marchandises 50xx (ex. 1514 → 4014 / 5014)."),
        ("etape", "4. Page « Administration > Sage 50 » : choisissez le fichier d'entreprise (.SAI), l'utilisateur mvogmbi_sync et "
                  "son mot de passe, puis le mot de passe de sysadmin (utilisé pour l'import)."),
        ("etape", "5. « Premier jour à importer » : utilisé seulement si Sage ne contient encore aucune facture "
                  "« Vente AAAA-MM-JJ ». « Compte de dépôt des encaissements » : 1055 (Desjardins). « Encaisser à "
                  "partir des ventes du » : les dépôts plus anciens ne sont jamais touchés."),
        ("etape", "6. Fermez Sage et cliquez sur « Tester l'accès à Sage » : le nombre d'articles, la dernière "
                  "facture et l'état du client s'affichent. Aucune fenêtre de Sage n'apparaît."),
        ("note", "Chaque fichier d'entreprise (et chaque copie) a ses propres utilisateurs : l'utilisateur "
                 "mvogmbi_sync doit exister, avec le même mot de passe, dans le fichier choisi."),

        ("sous_titre", "Étape 3 — Courriel"),
        ("para", "Le compte rendu de chaque traitement est envoyé par courriel ; la même page règle la boîte où "
                 "arrivent les avis de virement Interac."),
        ("puce", "Hébergement cPanel (ex. marchemvogmbi.com) : serveur mail.marchemvogmbi.com, port 465, sécurité "
                 "ssl ; utilisateur = adresse complète."),
        ("puce", "Gmail : smtp.gmail.com, port 587, starttls ; mot de passe d'application (Compte Google > "
                 "Sécurité > Mots de passe des applications)."),
        ("puce", "Outlook / Microsoft 365 : smtp.office365.com, port 587, starttls."),
        ("etape", "1. Renseignez l'expéditeur, le ou les destinataires et, au besoin, d'« Autres destinataires » "
                  "(en copie), séparés par des virgules ; enregistrez, puis « Envoyer un courriel de test »."),
        ("etape", "2. Carte « Avis de paiement » : serveur (ex. mail.marchemvogmbi.com), adresse de la boîte "
                  "(ex. contact@marchemvogmbi.com), son mot de passe et la date à partir de laquelle lire les avis. "
                  "La boîte est lue sans rien modifier : les courriels restent non lus."),

        ("sous_titre", "Étape 4 — Automatisation"),
        ("etape", "1. Choisissez l'heure du traitement (1 h par défaut) et cliquez sur « Installer la tâche "
                  "planifiée »."),
        ("etape", "2. Paramètres Windows > Système > Alimentation : mise en veille « Jamais » sur secteur. La "
                  "session Windows doit rester ouverte (elle peut être verrouillée)."),
        ("etape", "3. « État de la tâche » confirme l'installation et la prochaine exécution."),

        ("sous_titre", "Étape 5 — Correspondance des articles"),
        ("para", "Chaque article Clover doit être relié à un numéro d'article Sage. La page « Articles > Correspondance » "
                 "affiche les statuts :"),
        ("puce", "Automatique : même nom ou même code-barres dans Sage, relié sans intervention."),
        ("puce", "Confirmé : relié par vous ; conservé à chaque mise à jour."),
        ("puce", "À confirmer : une proposition existe ; vérifiez-la puis « Accepter la proposition »."),
        ("puce", "Aucun : aucun article Sage au bon format ; créez-le dans Sage, puis « Mettre à jour depuis Clover "
                 "et Sage »."),
        ("etape", "Pour relier : sélectionnez l'article, cherchez l'article Sage, « Confirmer l'article choisi », "
                  "puis « Enregistrer les modifications »."),
        ("note", "Règle du marché : deux formats différents (500 g / 1 kg, 6-36 / 7-36) sont deux articles "
                 "différents ; l'application ne les propose jamais. Une liaison que vous confirmez vous-même "
                 "(« Confirmer quand même ? », par exemple un ancien nom mal écrit dans Clover) est toujours "
                 "appliquée."),

        ("sous_titre", "Étape 6 — Premier traitement"),
        ("etape", "1. Tableau de bord > « Simulation (sans import) » : les factures sont préparées mais pas "
                  "importées ; lisez les points à corriger."),
        ("etape", "2. Corrigez-les (articles à relier, comptes manquants), fermez Sage, puis « Lancer maintenant »."),
        ("etape", "3. Dans Sage, ouvrez une facture « Vente AAAA-MM-JJ » du client « Vente Hebdomadaire » et "
                  "comparez son total aux ventes nettes du jour dans Clover."),
        ("note", "Rattrapage : « Charger une date ou une période » (du … au …) puis « Charger la période » importe les "
                 "ventes de ces jours (Sage fermé). Les jours déjà facturés sont sautés ; vendredi, samedi et dimanche "
                 "forment toujours une seule facture « Vente AAAA-MM-JJ/JJ », car le dépôt du lundi couvre les trois "
                 "jours. Une fin de semaine déjà facturée en partie est signalée, jamais complétée par une 2e facture."),

        ("sous_titre", "Mise en production (vrai fichier d'entreprise)"),
        ("etape", "1. Dans le vrai fichier : créez l'utilisateur mvogmbi_sync, cochez la case du client "
                  "« Vente Hebdomadaire » (et des fournisseurs) et vérifiez les comptes des articles (étape 2)."),
        ("etape", "2. Page « Administration > Sage 50 » : choisissez le vrai fichier .SAI, puis « Tester l'accès à Sage »."),
        ("etape", "3. Vérifiez le « Premier jour à importer » et faites une simulation avant la première nuit."),

        ("sous_titre", "Encaissements des dépôts Clover (menu « Comptabilité »)"),
        ("para", "Clover dépose dans le compte Desjardins (1055) les ventes encaissées moins les espèces : c'est "
                 "le lot de cartes que Clover ferme chaque soir. Ventes du lundi au jeudi : déposées le lendemain ; "
                 "ventes du vendredi, samedi et dimanche : déposées ensemble le lundi."),
        ("etape", "1. Choisissez la période de ventes, puis « Calculer les dépôts » : chaque dépôt et son état dans "
                  "Sage s'affichent (Appliqué, À saisir dans Sage, Écart…)."),
        ("etape", "2. Chaque nuit, après l'import des factures, les dépôts « À saisir » sont encaissés dans Sage : "
                  "Payé par « Comptant », dépôt au compte 1055, à la date du dépôt, total contrôlé avant validation "
                  "puis vérifié dans Sage."),
        ("etape", "3. À la demande : fermez Sage et cliquez sur « Encaisser dans Sage ». Un courriel récapitule "
                  "les encaissements."),
        ("note", "Un dépôt supérieur au solde dû de la facture n'est jamais saisi. Le solde restant sur une facture "
                 "correspond aux ventes en espèces."),
        ("para", "Espèces des ventes : les virements Interac reçus et les dépôts d'espèces au guichet des relevés "
                 "Desjardins chargés à la page « Comptabilité > Rapprochement » sont aussi vérifiés et encaissés (un encaissement par mouvement, "
                 "« Comptant », compte 1055). Interac : sur la facture du jour du virement. Dépôt d'espèces : sur les "
                 "factures dont il reste des espèces (solde dû moins les dépôts Clover à venir), de la plus ancienne à "
                 "la plus récente. Un mouvement qui ne trouve pas sa place est marqué « Espèces à répartir à la main »."),

        ("sous_titre", "Factures fournisseurs (menu « Fournisseur »)"),
        ("etape", "1. « Ajouter des factures… » copie les PDF ou photos dans le dossier des factures (vous pouvez "
                  "aussi les y déposer, puis « Actualiser »), et « 📧 Lire le courriel » y copie les factures jointes "
                  "aux courriels (« Administration > Courriel », carte 4). Chaque facture est lue : fournisseur, n°, date, lignes et "
                  "totaux."),
        ("etape", "2. Vérifiez le fournisseur Sage (recherche rapide), le n° et la date ; les totaux sont contrôlés "
                  "(sous-total + TPS + TVQ = total)."),
        ("etape", "3. Pour chaque ligne : choisissez l'article Sage (« Relier et confirmer ») et le facteur de "
                  "conditionnement. Qté Sage = Qté × Facteur ; Prix Sage = Montant / Qté Sage. Entrée applique et "
                  "passe à la ligne suivante ; après la dernière, une nouvelle ligne est créée."),
        ("etape", "4. Chaque saisie est enregistrée automatiquement, au fur et à mesure (en-tête, lignes, articles "
                  "reliés ; aussi en changeant de facture ou de page) : la facture passe à « Prête à importer » quand "
                  "tout est relié et cohérent. « Enregistrer la facture » reste disponible."),
        ("etape", "5. Fermez Sage, puis « Importer cette facture » (la facture ouverte seulement) ou « Importer "
                  "toutes les factures prêtes » : chaque facture est importée comme facture d'achat et vérifiée ; "
                  "elle passe à « Importée ». Une facture déjà dans Sage est refusée."),
        ("note", "« Écarter » met de côté une facture qui ne doit pas être traitée. Les choix d'articles et de "
                 "facteurs sont retenus pour chaque fournisseur."),

        ("sous_titre", "Paiements fournisseurs (menu « Comptabilité »)"),
        ("etape", "1. Choisissez la date « Lire depuis le », puis « Actualiser » : les avis de virement Interac "
                  "reçus depuis cette date sont lus, ainsi que les factures impayées de Sage. Tous les virements non "
                  "encore traités s'affichent. La date « au » limite l'affichage entre deux dates. Seuls les avis "
                  "présents dans la boîte de courriel peuvent être lus : un avis supprimé ou envoyé à une autre "
                  "adresse n'apparaît pas."),
        ("etape", "2. Pour chaque virement : vérifiez le fournisseur Sage proposé (retenu pour les prochains "
                  "virements du même bénéficiaire), sélectionnez la ou les factures payées (Ctrl+clic pour "
                  "plusieurs), puis « Confirmer le paiement »."),
        ("etape", "3. Les paiements confirmés sont saisis dans Sage la nuit (compte 1055, « Comptant », à la date "
                  "du virement), ou tout de suite avec « Payer dans Sage » (Sage fermé). Chacun passe à « Saisi dans "
                  "Sage » après vérification du solde des factures."),
        ("note", "Un paiement partiel est accepté. « Ignorer » écarte un virement qui ne concerne pas un "
                 "fournisseur ; « Déjà dans Sage » signale un paiement déjà saisi à la main."),

        ("sous_titre", "Rapprochement bancaire (menu « Comptabilité »)"),
        ("para", "« Encaissement manuel » (entrée d'argent choisie) : choisissez la facture de vente et le montant ; "
                 "l'encaissement est noté à la page « Comptabilité > Encaissements » et saisi dans Sage par « Encaisser dans Sage ». « Paiement "
                 "fournisseur manuel » (sortie d'argent choisie) : le mouvement est ajouté à la page « Comptabilité > Paiements fournisseur », où l'on choisit "
                 "le fournisseur et la facture, puis « Payer dans Sage »."),
        ("etape", "1. Téléchargez le relevé de compte PDF dans AccèsD (compte 1055, folio 321147), puis « Charger des "
                  "relevés… ». Chaque relevé est contrôlé : solde d'ouverture + dépôts − retraits = solde de fermeture."),
        ("etape", "2. « Actualiser » : chaque mouvement de banque est relié à son écriture Sage du compte 1055 (même "
                  "montant, date proche, ou somme de 2 ou 3 écritures, ex. dépôt de la fin de semaine)."),
        ("etape", "3. Pour chaque mouvement « Absent de Sage » (frais bancaires, prélèvements, virements…) : choisissez "
                  "le compte Sage, puis « Confirmer le compte » ; le choix est retenu pour les mouvements semblables. "
                  "« Ignorer » écarte un mouvement."),
        ("etape", "4. Fermez Sage, puis « Saisir dans Sage » : chaque mouvement confirmé devient une écriture de journal "
                  "(source « Relevé AAAA-MM-JJ »), vérifiée ensuite dans Sage."),
        ("etape", "5. « Rapport Excel » : soldes, écart d'ouverture, mouvements absents, écritures pas encore passées à la "
                  "banque ; l'« écart non expliqué » doit être 0,00 $."),
        ("note", "Les écritures corrigées dans Sage (original et contrepassation « CORR ») s'annulent : elles sont "
                 "ignorées. « Supprimer le relevé » met le fichier de côté (dossier « supprimes »)."),
        ("note", "« Période du … au … » (📅 calendrier) : rapproche seulement les mouvements et les écritures de ces "
                 "dates, avec les soldes du début et de la fin de la période ; « Toute la période des relevés » revient "
                 "à l'ensemble des relevés chargés."),
        ("note", "Virements Interac reçus et dépôts au guichet : « À encaisser sur les ventes », encaissés à la page « Comptabilité > Encaissements ». "
                 "Dépôts de salaire : reliés aux paies de Sage, sinon « Paie absente de Sage » (à corriger dans le "
                 "module Paie)."),

        ("sous_titre", "Rapports (menu « État »)"),
        ("puce", "Suivi des ventes : une ligne par facture de vente — date de traitement, journée(s), statut "
                 "(importée, bloquée, échec), montants HT, taxes et TTC, commentaire, état de l'encaissement (solde dû "
                 "dans Sage) et état du rapprochement (encaissements retrouvés sur les relevés chargés à la page « Comptabilité > Rapprochement »)."),
        ("puce", "Recherche dans l'historique de Sage : par client (factures et encaissements), fournisseur "
                 "(factures, paiements, notes de crédit, avec le solde dû), vente, encaissement, paiement, ou article "
                 "(ventes, achats, retours et ajustements, avec le cumul), sur une période au choix."),
        ("puce", "Factures fournisseurs archivées : chaque facture importée est gardée (copie du PDF, détail des "
                 "lignes en Excel) dans donnees\\archives\\factures_fournisseurs ; recherche par fournisseur, n°, "
                 "date ou article."),
        ("puce", "Statistiques Clover, comme le tableau de bord de Clover : bouton « 📅 Aujourd'hui » (hier, cette "
                 "semaine, semaine dernière, ce mois-ci, mois dernier, 30 derniers jours, cette année, période "
                 "personnalisée), indicateurs avec leur variation (aujourd'hui par rapport au même jour la semaine "
                 "dernière), graphiques des ventes par heure ou par jour, du montant perçu, des meilleurs articles et "
                 "des employés. La journée en cours se met à jour toutes les 5 minutes. Le menu de gauche mène à "
                 "chaque état, rangé comme dans Clover : Activités de vente (commandes, transactions, remboursements), "
                 "Rapports (dans l'ordre de Clover : aperçu des ventes en graphiques, rapport des ventes par jour avec "
                 "ventes brutes et nettes, ventes d'articles, ventes par employé, modes de paiement, rabais), Finances, "
                 "Articles (liste d'articles avec les caractéristiques Clover, le n° et le CUMP Sage et la marge ; "
                 "péremption), Employés, Clients. Bénéfices : ventes nettes Clover moins quantité × CUMP de l'article "
                 "dans Sage (un CUMP plus de 5 fois le prix de vente est jugé douteux et écarté). Aperçu financier : "
                 "28 indicateurs (KPI). Filtres globaux (article, client, employé, catégorie) appliqués à tous les "
                 "états, sans relire Clover. Évolution par année : ventes par jour de la période, une courbe par année. "
                 "Carte de chaleur : ventes par jour de la semaine et par heure. Graphiques enrichis : titre, aire sous "
                 "la courbe, ligne de la moyenne, point le plus haut, valeurs sur les barres ; au survol d'une courbe, "
                 "d'une barre, d'une part d'anneau, d'une ligne de classement ou d'une case, une infobulle donne le "
                 "détail. Chaque tableau a son titre. Chaque état a une recherche "
                 "et son graphique (courbe d'évolution, barres, anneau ou classement). L'axe vertical s'arrête juste "
                 "au-dessus de la plus grande valeur. Les tableaux datés montrent la date la plus récente en haut "
                 "(sauf les prévisions et la péremption, tournées vers l'avenir). Export PDF : « 📕 PDF de la page » "
                 "(cartes d'indicateurs, graphiques et tableau complet, avec la période et les filtres) ; clic droit "
                 "sur un graphique : « Exporter le graphique en PDF » ou « Enregistrer le graphique en image (PNG) »."),
        ("puce", "Prévisions : ventes des prochains jours (même jour de la semaine sur 4 semaines, corrigé de la "
                 "tendance), achats à prévoir (rythme de vente des 28 derniers jours, stock et coût Clover) et articles "
                 "à commander : stock restant − quantité vendue les N derniers jours ≤ 0 (N choisi dans la liste « Horizon », "
                 "14 par défaut ; articles vendus dont Clover suit le stock ; un stock négatif compte pour 0 dans la "
                 "quantité suggérée)."),
        ("puce", "Péremption : la date saisie dans le champ SKU des articles Clover (JJ/MM/AAAA) ; triés de la plus "
                 "proche à la plus lointaine ; fond rouge à un mois ou moins (ou périmé), jaune de 1 à 3 mois, neutre "
                 "au-delà. Les SKU vides ou qui ne sont pas une date sont ignorés."),
        ("puce", "Tableaux des statistiques : pour la période choisie, résumé, ventes par jour, jour de la semaine, heure, "
                 "employé, mode de paiement, type de carte, mode de saisie de la carte, appareil, client, article, "
                 "catégorie, ainsi que la liste des commandes, des paiements, des rabais et des remboursements. Chaque "
                 "jour lu dans Clover est gardé : une période déjà calculée s'affiche ensuite tout de suite."),
        ("note", "Chaque tableau s'exporte en Excel ou en CSV (« ⬇ Exporter »)."),
        ("sous_titre", "Mode opératoire — chaque matin"),
        ("etape", "1. Lisez le courriel de la nuit : « succès », ou la liste des points à corriger."),
        ("etape", "2. Un jour bloqué : corrigez la cause (article à relier, compte manquant…) ; il sera repris la "
                  "nuit suivante, ou tout de suite avec « Lancer maintenant » (Sage fermé)."),
        ("etape", "3. Page « Comptabilité > Paiements fournisseur » : « Actualiser », puis confirmez les nouveaux virements aux fournisseurs."),
        ("etape", "4. Page « Fournisseur > Factures fournisseurs » : ajoutez les factures fournisseurs reçues, vérifiez-les et enregistrez-les."),
        ("etape", "5. Avant de quitter le soir : fermez Sage, pour que le traitement de nuit puisse importer et saisir."),

        ("sous_titre", "Mode opératoire — chaque semaine"),
        ("etape", "1. Page « Comptabilité > Encaissements » : « Calculer les dépôts » sur la semaine passée ; tous les dépôts doivent être "
                  "« Appliqué ». Les écarts sont à regarder avec le relevé Desjardins."),
        ("etape", "2. Page « Articles > Correspondance » : filtre « À traiter » : reliez les nouveaux articles Clover."),
        ("etape", "3. Page « Fournisseur > Factures fournisseurs » : importez dans Sage les factures « Prêtes à importer » (Sage fermé)."),
        ("etape", "4. Sauvegardez le dossier des données (bouton du Tableau de bord)."),

        ("sous_titre", "Mode opératoire — chaque mois"),
        ("etape", "1. Page « Comptabilité > Rapprochement » : chargez le relevé Desjardins du mois, « Actualiser », choisissez le compte des "
                  "mouvements absents de Sage, puis « Saisir dans Sage » ; l'écart non expliqué doit être nul."),
        ("etape", "2. Vérifiez qu'il ne reste aucun virement « À relier » ni facture « À vérifier »."),
        ("etape", "3. Comparez le total des ventes du mois dans Sage avec le rapport des ventes Clover."),

        ("sous_titre", "Règles de facturation"),
        ("puce", "Client « Vente Hebdomadaire » : une facture par jour du lundi au jeudi (« Vente AAAA-MM-JJ », "
                 "datée du jour des ventes) et une seule du vendredi au dimanche (« Vente AAAA-MM-JJ/JJ », datée du "
                 "dimanche), encaissée d'un coup par le dépôt du lundi."),
        ("puce", "Une ligne par article : montant = ventes nettes Clover (après rabais et remboursements) ; prix "
                 "unitaire = montant / quantité."),
        ("puce", "Articles taxés dans Clover : code de taxe GQ (TPS 5 % + TVQ 9,975 %)."),
        ("puce", "Une vente est datée de son premier paiement réussi."),

        ("sous_titre", "Fichiers et sauvegarde"),
        ("puce", "Dossier des données (bouton du Tableau de bord) : correspondance des articles, factures et "
                 "paiements des fournisseurs, journaux et sauvegardes."),
        ("puce", "Sauvegardez ce dossier régulièrement : la correspondance validée représente votre travail."),
        ("puce", "Les mots de passe sont dans le coffre-fort de Windows, jamais dans un fichier."),
        ("puce", "Nouvel ordinateur ou réinstallation : Automatisation > « Reprendre une configuration existante… »."),

        ("sous_titre", "Dépannage"),
        ("puce", "« Sage refuse l'utilisateur » : mot de passe différent dans ce fichier d'entreprise (étape 2)."),
        ("puce", "« Article Clover non relié » : page Correspondance (étape 5)."),
        ("puce", "« Article Sage sans compte de produits » : fiche de l'article dans Sage, onglet Associé."),
        ("puce", "« Ce client utilise mes n° articles » non coché : fiche du client ou du fournisseur, onglet "
                 "Importer/Exporter."),
        ("puce", "« Sage est ouvert » : fermez Sage, puis relancez."),
        ("puce", "« 535 Incorrect authentication data » : utilisateur ou mot de passe du courriel (étape 3)."),
        ("puce", "Rien la nuit : ordinateur en veille ou session fermée ; « État de la tâche » (étape 4)."),
    ],
    "en": [
        ("titre", "Setup guide and operating procedure"),
        ("para", "This guide describes the complete setup of MVOGMBI_Sync, then the daily operating procedure: "
                 "sales, receipts, supplier invoices and payments."),
        ("sous_titre", "Before you start"),
        ("puce", "A Windows computer that stays on at night, with Sage 50 Accounting 2026 installed."),
        ("puce", "Administrator access to the market's Clover account."),
        ("puce", "The password of Sage's sysadmin user."),
        ("puce", "A sending email address (e.g. notification@marchemvogmbi.com) and its password, and the mailbox "
                 "that receives the Interac transfer notices (e.g. contact@marchemvogmbi.com)."),
        ("note", "Tip: do all your trials on a COPY of the company file (Sage: File > Save a Copy). The real file "
                 "is only chosen at the “Going live” step."),

        ("sous_titre", "Step 1 — Clover"),
        ("etape", "1. Sign in to the Clover dashboard (www.clover.com). The merchant ID (13 characters) is in the "
                  "page address, after “/m/”."),
        ("etape", "2. Account & Setup > API Tokens > Create token. Give it a name (e.g. MVOGMBI_Sync) and READ "
                  "permissions: Orders, Inventory, Payments, Merchant."),
        ("etape", "3. “Administration > Clover” page: paste the merchant ID and the token, then click “Test the Clover "
                  "connection”: the market's name must appear."),

        ("sous_titre", "Step 2 — Sage 50"),
        ("etape", "1. Read-only user. Open the file in Sage as sysadmin: Setup > Set Up Users > Add. Name: "
                  "mvogmbi_sync, with a password. Rights: “View” on Inventory & Services, Receivables and Payables; "
                  "“Third-party product access rights”: Read only."),
        ("etape", "2. “Vente Hebdomadaire” customer record: Import/Export tab, check “This customer uses my item "
                  "numbers”. Do the same on the record of each supplier whose invoices you import."),
        ("etape", "3. Item accounts: every item needs a revenue account. Market rule: asset account 15xx → "
                  "revenue 40xx and cost of goods 50xx (e.g. 1514 → 4014 / 5014)."),
        ("etape", "4. “Administration > Sage 50” page: choose the company file (.SAI), the mvogmbi_sync user and its password, "
                  "then the sysadmin password (used for the import)."),
        ("etape", "5. “First day to import”: only used if Sage does not yet contain any “Vente YYYY-MM-DD” invoice. "
                  "“Receipt deposit account”: 1055 (Desjardins). “Record receipts from sales of”: older deposits "
                  "are never touched."),
        ("etape", "6. Close Sage and click “Test Sage access”: the number of items, the last invoice and the "
                  "customer status appear. No Sage window shows up."),
        ("note", "Each company file (and each copy) has its own users: the mvogmbi_sync user must exist, with the "
                 "same password, in the chosen file."),

        ("sous_titre", "Step 3 — Email"),
        ("para", "The report of each run is sent by email; the same page sets the mailbox receiving the Interac "
                 "transfer notices."),
        ("puce", "cPanel hosting (e.g. marchemvogmbi.com): server mail.marchemvogmbi.com, port 465, security ssl; "
                 "user = full address."),
        ("puce", "Gmail: smtp.gmail.com, port 587, starttls; app password (Google Account > Security > App "
                 "passwords)."),
        ("puce", "Outlook / Microsoft 365: smtp.office365.com, port 587, starttls."),
        ("etape", "1. Fill in the sender, the recipient(s) and, if needed, “Other recipients” (in copy), separated "
                  "by commas; save, then “Send a test email”."),
        ("etape", "2. “Payment notices” card: server (e.g. mail.marchemvogmbi.com), mailbox address (e.g. "
                  "contact@marchemvogmbi.com), its password and the date from which to read notices. The mailbox is "
                  "read without changing anything: emails stay unread."),

        ("sous_titre", "Step 4 — Automation"),
        ("etape", "1. Choose the run time (1 a.m. by default) and click “Install the scheduled task”."),
        ("etape", "2. Windows Settings > System > Power: sleep “Never” when plugged in. The Windows session must "
                  "stay open (it may be locked)."),
        ("etape", "3. “Task status” confirms the installation and the next run."),

        ("sous_titre", "Step 5 — Item mapping"),
        ("para", "Each Clover item must be linked to a Sage item number. The “Items > Mapping” page shows the "
                 "statuses:"),
        ("puce", "Automatic: same name or same barcode in Sage, linked with no action."),
        ("puce", "Confirmed: linked by you; kept at every update."),
        ("puce", "To confirm: a suggestion exists; check it then “Accept the suggestion”."),
        ("puce", "None: no Sage item with the right size; create it in Sage, then “Update from Clover and Sage”."),
        ("etape", "To link: select the item, search the Sage item, “Confirm the chosen item”, then “Save "
                  "changes”."),
        ("note", "Market rule: two different sizes (500 g / 1 kg, 6-36 / 7-36) are two different items; the "
                 "application never suggests them. A link you confirm yourself (“Confirm anyway?”, for example "
                 "an old misspelled name in Clover) is always applied."),

        ("sous_titre", "Step 6 — First run"),
        ("etape", "1. Dashboard > “Simulation (no import)”: invoices are prepared but not imported; read the "
                  "points to fix."),
        ("etape", "2. Fix them (items to link, missing accounts), close Sage, then “Run now”."),
        ("etape", "3. In Sage, open a “Vente YYYY-MM-DD” invoice of the “Vente Hebdomadaire” customer and compare "
                  "its total with the day's net sales in Clover."),
        ("note", "Catching up: “Load a date or a period” (from … to …) then “Load the period” imports the sales of "
                 "those days (Sage closed). Days already invoiced are skipped; Friday, Saturday and Sunday always make "
                 "a single “Vente YYYY-MM-DD/DD” invoice, since Monday's deposit covers the three days. A weekend "
                 "already partly invoiced is flagged, never completed with a 2nd invoice."),

        ("sous_titre", "Going live (real company file)"),
        ("etape", "1. In the real file: create the mvogmbi_sync user, check the “Vente Hebdomadaire” customer box "
                  "(and the suppliers') and check the item accounts (step 2)."),
        ("etape", "2. “Administration > Sage 50” page: choose the real .SAI file, then “Test Sage access”."),
        ("etape", "3. Check the “First day to import” and run a simulation before the first night."),

        ("sous_titre", "Receipts for Clover deposits (“Accounting” menu)"),
        ("para", "Clover deposits into the Desjardins account (1055) the sales collected minus cash: this is the "
                 "card batch Clover closes every evening. Monday to Thursday sales: deposited the next day; Friday, "
                 "Saturday and Sunday sales: deposited together on Monday."),
        ("etape", "1. Choose the sales period, then “Calculate deposits”: each deposit and its status in Sage are "
                  "shown (Applied, To enter in Sage, Difference…)."),
        ("etape", "2. Every night, after importing the invoices, the deposits “To enter” are recorded in Sage: Paid "
                  "by “Cash”, deposit to account 1055, at the deposit date, total checked before processing then "
                  "verified in Sage."),
        ("etape", "3. On demand: close Sage and click “Record in Sage”. An email summarizes the receipts."),
        ("note", "A deposit larger than the invoice balance is never entered. The balance left on an invoice is the "
                 "cash sales."),
        ("para", "Sales cash: the Interac transfers received and the ATM cash deposits of the Desjardins statements "
                 "loaded on the “Accounting > Reconciliation” page are also checked and recorded (one receipt per transaction, “Cash”, account 1055). "
                 "Interac: on the invoice of the transfer day. Cash deposit: on the invoices with cash left (balance "
                 "due minus the upcoming Clover deposits), oldest first. A transaction that does not fit is marked "
                 "“Cash to allocate manually”."),

        ("sous_titre", "Supplier invoices (“Supplier” menu)"),
        ("etape", "1. “Add invoices…” copies the PDFs or photos into the invoice folder (you can also drop them "
                  "there, then “Refresh”), and “📧 Read email” copies there the invoices attached to emails (“Administration > Email”, "
                  "card 4). Each invoice is read: supplier, number, date, lines and totals."),
        ("etape", "2. Check the Sage supplier (quick search), the number and the date; totals are checked "
                  "(subtotal + GST + QST = total)."),
        ("etape", "3. For each line: choose the Sage item (“Link and confirm”) and the packaging factor. Sage qty = "
                  "Qty × Factor; Sage price = Amount / Sage qty. Enter applies and moves to the next line; after the "
                  "last one, a new line is created."),
        ("etape", "4. Every entry is saved automatically as you go (header, lines, linked items; also when you "
                  "change invoice or page): the invoice becomes “Ready to import” once everything is linked and "
                  "consistent. “Save the invoice” is still available."),
        ("etape", "5. Close Sage, then “Import this invoice” (the open invoice only) or “Import all ready "
                  "invoices”: each invoice is imported as a purchase invoice and verified; it becomes “Imported”. An "
                  "invoice already in Sage is refused."),
        ("note", "“Set aside” puts aside an invoice that must not be processed. Item and factor choices are "
                 "remembered for each supplier."),

        ("sous_titre", "Supplier payments (“Accounting” menu)"),
        ("etape", "1. Choose the “Read since” date, then “Refresh”: the Interac transfer notices received since that "
                  "date are read, along with the unpaid invoices in Sage. All transfers not yet processed are shown. "
                  "The “to” date limits the display between two dates. Only notices still in the mailbox can be "
                  "read: a deleted notice, or one sent to another address, does not appear."),
        ("etape", "2. For each transfer: check the suggested Sage supplier (remembered for the next transfers to the "
                  "same payee), select the paid invoice(s) (Ctrl+click for several), then “Confirm payment”."),
        ("etape", "3. Confirmed payments are entered in Sage at night (account 1055, “Cash”, at the transfer date), "
                  "or right away with “Pay in Sage” (Sage closed). Each becomes “Entered in Sage” after the invoice "
                  "balances are verified."),
        ("note", "A partial payment is accepted. “Ignore” sets aside a transfer that is not for a supplier; "
                 "“Already in Sage” flags a payment already entered by hand."),

        ("sous_titre", "Bank reconciliation (“Accounting” menu)"),
        ("para", "“Manual receipt” (selected incoming amount): choose the sales invoice and the amount; the receipt "
                 "is noted on the “Accounting > Receipts” page and entered in Sage with “Record in Sage”. “Manual supplier payment” (selected "
                 "outgoing amount): the transaction is added to the “Accounting > Supplier payments” page, where you choose the supplier and the invoice, "
                 "then “Pay in Sage”."),
        ("etape", "1. Download the PDF account statement from AccèsD (account 1055, folio 321147), then “Load "
                  "statements…”. Each statement is checked: opening balance + deposits − withdrawals = closing balance."),
        ("etape", "2. “Refresh”: each bank transaction is linked to its Sage entry in account 1055 (same amount, close "
                  "date, or sum of 2 or 3 entries, e.g. the weekend deposit)."),
        ("etape", "3. For each transaction “Missing from Sage” (bank charges, debits, transfers…): choose the Sage "
                  "account, then “Confirm account”; the choice is remembered for similar transactions. “Ignore” sets a "
                  "transaction aside."),
        ("etape", "4. Close Sage, then “Enter in Sage”: each confirmed transaction becomes a journal entry (source "
                  "“Relevé YYYY-MM-DD”), then verified in Sage."),
        ("etape", "5. “Excel report”: balances, opening difference, missing transactions, entries not yet at the bank; "
                  "the “unexplained difference” must be $0.00."),
        ("note", "Entries corrected in Sage (original and “CORR” reversal) cancel out: they are ignored. “Delete "
                 "statement” sets the file aside (“supprimes” folder)."),
        ("note", "“Period from … to …” (📅 calendar): reconciles only the transactions and entries of those dates, "
                 "with the balances at the start and end of the period; “Whole statement period” goes back to all the "
                 "loaded statements."),
        ("note", "Interac transfers received and ATM deposits: “To receive on the sales”, recorded on the “Accounting > Receipts” page. Salary "
                 "deposits: linked to the Sage payroll, otherwise “Payroll missing from Sage” (to fix in the Payroll "
                 "module)."),

        ("sous_titre", "Reports (“Reports” menu)"),
        ("puce", "Sales tracking: one line per sales invoice — processing date, day(s), status (imported, blocked, "
                 "failed), amounts before tax, taxes and including tax, comment, receipt status (balance due in Sage) "
                 "and reconciliation status (receipts found on the statements loaded on the “Accounting > Reconciliation” page)."),
        ("puce", "Sage history search: by customer (invoices and receipts), supplier (invoices, payments, credit notes, "
                 "with the balance due), sale, receipt, payment, or item (sales, purchases, returns and adjustments, "
                 "with the running total), over any period."),
        ("puce", "Archived supplier invoices: each imported invoice is kept (PDF copy, line details in Excel) in "
                 "donnees\\archives\\factures_fournisseurs; search by supplier, number, date or item."),
        ("puce", "Clover statistics, like the Clover dashboard: “📅 Today” button (yesterday, this week, last week, "
                 "this month, last month, last 30 days, this year, custom period), indicators with their change "
                 "(today compared with the same day last week), charts of sales by hour or by day, amount collected, "
                 "top items and employees. The current day refreshes every 5 minutes. The left menu leads to each "
                 "report, arranged as in Clover: Sales activity (orders, transactions, refunds), Reports (in Clover's "
                 "order: sales overview in charts, daily sales report with gross and net sales, item sales, sales by "
                 "employee, payment methods, discounts), Finances (financial overview with 28 KPIs), Items (item "
                 "list with Clover details, Sage number, Sage average cost and margin), Profits (Clover net sales minus "
                 "quantity × Sage average cost; a cost over 5 times the selling price is deemed doubtful), global "
                 "filters (item, customer, employee, category) applied to every report, year-over-year trend (one "
                 "curve per year), heat map (sales by weekday and hour), richer charts (title, area under the curve, "
                 "average line, highest point, values on bars) with tooltips on curves, bars, ring slices, ranking "
                 "rows and heat map cells, a title on every table, "
                 "Items (including expiry), Employees, Customers. Each report has a search box and its chart (trend "
                 "line, bars, ring or ranking). The vertical axis stops just above the largest value. Dated tables "
                 "show the most recent date first (except forecasts and expiry, which look ahead). PDF export: "
                 "“📕 Page PDF” (indicator cards, charts and full table, with the period and filters); right-click a "
                 "chart: “Export the chart to PDF” or “Save the chart as an image (PNG)”."),
        ("puce", "Forecasts: sales of the coming days (same weekday over 4 weeks, adjusted for the trend), purchases "
                 "to plan (sales pace of the last 28 days, Clover stock and cost) and items to order: remaining stock "
                 "− quantity sold in the last N days ≤ 0 (N chosen in the “Horizon” list, 14 by default; "
                 "items sold whose stock Clover tracks; a negative stock "
                 "counts as 0 in the suggested quantity)."),
        ("puce", "Expiry: the date typed in the SKU field of the Clover items (DD/MM/YYYY); sorted from the nearest; "
                 "red background at one month or less (or expired), yellow from 1 to 3 months, neutral beyond. Empty "
                 "or non-date SKUs are ignored."),
        ("puce", "Statistics tables: for the chosen period, summary, sales by day, weekday, hour, employee, payment "
                 "method, card type, card entry mode, device, customer, item, category, plus the list of orders, "
                 "payments, discounts and refunds. Each day read from Clover is kept: a period already calculated "
                 "then shows right away."),
        ("note", "Every table can be exported to Excel or CSV (“⬇ Export”)."),
        ("sous_titre", "Operating procedure — every morning"),
        ("etape", "1. Read the nightly email: “success”, or the list of points to fix."),
        ("etape", "2. A blocked day: fix the cause (item to link, missing account…); it is resumed the following "
                  "night, or right away with “Run now” (Sage closed)."),
        ("etape", "3. “Accounting > Supplier payments”: “Refresh”, then confirm the new transfers to suppliers."),
        ("etape", "4. “Supplier > Supplier invoices”: add the supplier invoices received, check them and save them."),
        ("etape", "5. Before leaving in the evening: close Sage, so the nightly run can import and enter."),

        ("sous_titre", "Operating procedure — every week"),
        ("etape", "1. “Accounting > Receipts”: “Calculate deposits” for the past week; every deposit must be “Applied”. Check "
                  "differences against the Desjardins statement."),
        ("etape", "2. “Items > Mapping”: “To handle” filter: link the new Clover items."),
        ("etape", "3. “Supplier > Supplier invoices”: import into Sage the invoices “Ready to import” (Sage closed)."),
        ("etape", "4. Back up the data folder (Dashboard button)."),

        ("sous_titre", "Operating procedure — every month"),
        ("etape", "1. “Accounting > Reconciliation”: load the month's Desjardins statement, “Refresh”, choose the account of the "
                  "transactions missing from Sage, then “Enter in Sage”; the unexplained difference must be zero."),
        ("etape", "2. Check that no transfer is left “To link” and no invoice “To check”."),
        ("etape", "3. Compare the month's sales total in Sage with the Clover sales report."),

        ("sous_titre", "Invoicing rules"),
        ("puce", "Customer “Vente Hebdomadaire”: one invoice per day from Monday to Thursday (“Vente "
                 "YYYY-MM-DD”, dated on the sales day) and a single one from Friday to Sunday (“Vente YYYY-MM-DD/DD”, "
                 "dated on Sunday), paid at once by the Monday deposit."),
        ("puce", "One line per item: amount = Clover net sales (after discounts and refunds); unit price = "
                 "amount / quantity."),
        ("puce", "Items taxed in Clover: tax code GQ (GST 5% + QST 9.975%)."),
        ("puce", "A sale is dated by its first successful payment."),

        ("sous_titre", "Files and backup"),
        ("puce", "Data folder (Dashboard button): item mapping, supplier invoices and payments, logs and backups."),
        ("puce", "Back up this folder regularly: the validated mapping is your work."),
        ("puce", "Passwords are in the Windows vault, never in a file."),
        ("puce", "New computer or reinstall: Automation > “Import an existing configuration…”."),

        ("sous_titre", "Troubleshooting"),
        ("puce", "“Sage rejects the user”: different password in this company file (step 2)."),
        ("puce", "“Clover item not linked”: Item mapping page (step 5)."),
        ("puce", "“Sage item without a revenue account”: item record in Sage, Linked tab."),
        ("puce", "“This customer uses my item numbers” unchecked: customer or supplier record, Import/Export tab."),
        ("puce", "“Sage is open”: close Sage, then run again."),
        ("puce", "“535 Incorrect authentication data”: email user or password (step 3)."),
        ("puce", "Nothing at night: computer asleep or session closed; “Task status” (step 4)."),
    ],
}
