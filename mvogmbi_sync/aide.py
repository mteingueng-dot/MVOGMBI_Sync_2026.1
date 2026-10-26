"""Contenu des pages « Accueil / À propos », « Guide de configuration » et « Aide / FAQ », en français et en anglais.

Chaque page est une liste de blocs (type, texte) : titre, sous_titre, para, puce, etape, note, question, reponse.
Les deux langues ont exactement la même suite de blocs (vérifié par les tests).
"""

from __future__ import annotations

VERSION = "1.9.5"
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
        ("etape", "1. À l'heure choisie (1 h par défaut), l'application lit dans Sage la dernière facture "
                  "« Vente AAAA-MM-JJ » déjà importée."),
        ("etape", "2. Elle récupère dans Clover les ventes de chaque jour suivant, jusqu'à hier : un jour manqué "
                  "est rattrapé automatiquement."),
        ("etape", "3. Elle relie chaque article Clover à son numéro d'article Sage (correspondance des articles)."),
        ("etape", "4. Elle prépare une facture par jour du lundi au jeudi et une seule pour le vendredi, le samedi "
                  "et le dimanche : une ligne par article, montant = ventes nettes Clover, taxes TPS + TVQ (code GQ) "
                  "pour les articles taxés."),
        ("etape", "5. Elle importe les factures dans Sage, vérifie chacune d'elles, puis encaisse les dépôts Clover "
                  "et saisit les paiements fournisseurs que vous avez confirmés."),
        ("etape", "6. Elle vous envoie un compte rendu par courriel : succès, ou liste des points à corriger."),
        ("sous_titre", "Contrôles de sécurité"),
        ("puce", "Jamais deux fois la même facture : une date ou un numéro déjà présent dans Sage est ignoré."),
        ("puce", "Arrêt au premier jour qui pose problème (article non relié, compte manquant…) ; ce jour est "
                 "repris la nuit suivante, une fois le problème corrigé, sans trou dans la suite des factures."),
        ("puce", "Deux formats différents (ex. 500 g et 1 kg) ne sont jamais confondus."),
        ("puce", "Le total de chaque facture est égal aux ventes nettes Clover de la journée."),
        ("puce", "Rien n'est saisi sans contrôle du total, et chaque saisie est vérifiée ensuite dans Sage."),
        ("puce", "Les mots de passe et le jeton Clover sont gardés dans le coffre-fort de Windows."),
        ("sous_titre", "Pour commencer"),
        ("para", "Suivez la liste « Mise en route » ci-dessus : chaque étape passe au vert quand elle est faite. "
                 "Le « Guide de configuration » décrit chaque étape et le mode opératoire au quotidien ; « Aide / FAQ » "
                 "répond aux questions courantes. Le manuel d'utilisation illustré (PDF) est dans le menu Démarrer, "
                 "dossier MVOGMBI_Sync."),
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
        ("etape", "2. It retrieves from Clover the sales of each following day, up to yesterday: a missed day is "
                  "caught up automatically."),
        ("etape", "3. It links each Clover item to its Sage item number (item mapping)."),
        ("etape", "4. It prepares one invoice per day from Monday to Thursday and a single one for Friday, Saturday "
                  "and Sunday: one line per item, amount = Clover net sales, GST + QST (code GQ) for taxable items."),
        ("etape", "5. It imports the invoices into Sage, checks each one, then records the Clover deposits and "
                  "enters the supplier payments you have confirmed."),
        ("etape", "6. It emails you a report: success, or the list of points to fix."),
        ("sous_titre", "Safety checks"),
        ("puce", "Never the same invoice twice: a date or number already in Sage is skipped."),
        ("puce", "Stops at the first day with a problem (unlinked item, missing account…); that day is resumed "
                 "the following night once fixed, with no gap in the invoice sequence."),
        ("puce", "Two different sizes (e.g. 500 g and 1 kg) are never mixed up."),
        ("puce", "Each invoice total equals the day's Clover net sales."),
        ("puce", "Nothing is entered without checking the total, and every entry is then verified in Sage."),
        ("puce", "Passwords and the Clover token are kept in the Windows vault."),
        ("sous_titre", "Getting started"),
        ("para", "Follow the “Getting started” checklist above: each step turns green once done. The “Setup guide” "
                 "describes every step and the daily operating procedure; “Help / FAQ” answers common questions. "
                 "The illustrated user manual (PDF) is in the Start menu, MVOGMBI_Sync folder."),
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
        ("question", "Un nouvel article a été créé dans Clover : que faire ?"),
        ("reponse", "S'il porte exactement le même nom qu'un article Sage, il est relié automatiquement. Sinon, "
                    "ouvrez la page « 5. Correspondance », filtre « À traiter », choisissez l'article Sage et cliquez "
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
        ("reponse", "Page « 9. Paiements fournisseurs » : « Actualiser » lit les avis Interac reçus depuis la date "
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
        ("question", "A new item was created in Clover: what should I do?"),
        ("reponse", "If it has exactly the same name as a Sage item, it is linked automatically. Otherwise open the "
                    "“5. Item mapping” page, filter “To handle”, choose the Sage item and click “Confirm the chosen "
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
        ("reponse", "Page “9. Supplier payments”: “Refresh” reads the Interac notices received since the chosen "
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
        ("etape", "3. Page « 1. Clover » : collez l'identifiant marchand et le jeton, puis cliquez sur « Tester la "
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
        ("etape", "4. Page « 2. Sage 50 » : choisissez le fichier d'entreprise (.SAI), l'utilisateur mvogmbi_sync et "
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
        ("para", "Chaque article Clover doit être relié à un numéro d'article Sage. La page « 5. Correspondance » "
                 "affiche les statuts :"),
        ("puce", "Automatique : même nom ou même code-barres dans Sage, relié sans intervention."),
        ("puce", "Confirmé : relié par vous ; conservé à chaque mise à jour."),
        ("puce", "À confirmer : une proposition existe ; vérifiez-la puis « Accepter la proposition »."),
        ("puce", "Aucun : aucun article Sage au bon format ; créez-le dans Sage, puis « Mettre à jour depuis Clover "
                 "et Sage »."),
        ("etape", "Pour relier : sélectionnez l'article, cherchez l'article Sage, « Confirmer l'article choisi », "
                  "puis « Enregistrer les modifications »."),
        ("note", "Règle du marché : deux formats différents (500 g / 1 kg, 6-36 / 7-36) sont deux articles "
                 "différents ; l'application refuse de les relier."),

        ("sous_titre", "Étape 6 — Premier traitement"),
        ("etape", "1. Tableau de bord > « Simulation (sans import) » : les factures sont préparées mais pas "
                  "importées ; lisez les points à corriger."),
        ("etape", "2. Corrigez-les (articles à relier, comptes manquants), fermez Sage, puis « Lancer maintenant »."),
        ("etape", "3. Dans Sage, ouvrez une facture « Vente AAAA-MM-JJ » du client « Vente Hebdomadaire » et "
                  "comparez son total aux ventes nettes du jour dans Clover."),

        ("sous_titre", "Mise en production (vrai fichier d'entreprise)"),
        ("etape", "1. Dans le vrai fichier : créez l'utilisateur mvogmbi_sync, cochez la case du client "
                  "« Vente Hebdomadaire » (et des fournisseurs) et vérifiez les comptes des articles (étape 2)."),
        ("etape", "2. Page « 2. Sage 50 » : choisissez le vrai fichier .SAI, puis « Tester l'accès à Sage »."),
        ("etape", "3. Vérifiez le « Premier jour à importer » et faites une simulation avant la première nuit."),

        ("sous_titre", "Encaissements des dépôts Clover (page 7)"),
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

        ("sous_titre", "Factures fournisseurs (page 8)"),
        ("etape", "1. « Ajouter des factures… » copie les PDF ou photos dans le dossier des factures (vous pouvez "
                  "aussi les y déposer, puis « Actualiser »). Chaque facture est lue : fournisseur, n°, date, lignes "
                  "et totaux."),
        ("etape", "2. Vérifiez le fournisseur Sage (recherche rapide), le n° et la date ; les totaux sont contrôlés "
                  "(sous-total + TPS + TVQ = total)."),
        ("etape", "3. Pour chaque ligne : choisissez l'article Sage (« Relier et confirmer ») et le facteur de "
                  "conditionnement. Qté Sage = Qté × Facteur ; Prix Sage = Montant / Qté Sage. Entrée applique et "
                  "passe à la ligne suivante ; après la dernière, une nouvelle ligne est créée."),
        ("etape", "4. « Enregistrer la facture » : elle passe à « Prête à importer » quand tout est relié et cohérent."),
        ("etape", "5. Fermez Sage, puis « Importer dans Sage » : chaque facture est importée comme facture d'achat "
                  "et vérifiée ; elle passe à « Importée ». Une facture déjà dans Sage est refusée."),
        ("note", "« Écarter » met de côté une facture qui ne doit pas être traitée. Les choix d'articles et de "
                 "facteurs sont retenus pour chaque fournisseur."),

        ("sous_titre", "Paiements fournisseurs (page 9)"),
        ("etape", "1. Choisissez la date « Lire depuis le », puis « Actualiser » : les avis de virement Interac "
                  "reçus depuis cette date sont lus, ainsi que les factures impayées de Sage. Tous les virements non "
                  "encore traités s'affichent."),
        ("etape", "2. Pour chaque virement : vérifiez le fournisseur Sage proposé (retenu pour les prochains "
                  "virements du même bénéficiaire), sélectionnez la ou les factures payées (Ctrl+clic pour "
                  "plusieurs), puis « Confirmer le paiement »."),
        ("etape", "3. Les paiements confirmés sont saisis dans Sage la nuit (compte 1055, « Comptant », à la date "
                  "du virement), ou tout de suite avec « Payer dans Sage » (Sage fermé). Chacun passe à « Saisi dans "
                  "Sage » après vérification du solde des factures."),
        ("note", "Un paiement partiel est accepté. « Ignorer » écarte un virement qui ne concerne pas un "
                 "fournisseur ; « Déjà dans Sage » signale un paiement déjà saisi à la main."),

        ("sous_titre", "Rapprochement bancaire (page 10)"),
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

        ("sous_titre", "Mode opératoire — chaque matin"),
        ("etape", "1. Lisez le courriel de la nuit : « succès », ou la liste des points à corriger."),
        ("etape", "2. Un jour bloqué : corrigez la cause (article à relier, compte manquant…) ; il sera repris la "
                  "nuit suivante, ou tout de suite avec « Lancer maintenant » (Sage fermé)."),
        ("etape", "3. Page 9 : « Actualiser », puis confirmez les nouveaux virements aux fournisseurs."),
        ("etape", "4. Page 8 : ajoutez les factures fournisseurs reçues, vérifiez-les et enregistrez-les."),
        ("etape", "5. Avant de quitter le soir : fermez Sage, pour que le traitement de nuit puisse importer et saisir."),

        ("sous_titre", "Mode opératoire — chaque semaine"),
        ("etape", "1. Page 7 : « Calculer les dépôts » sur la semaine passée ; tous les dépôts doivent être "
                  "« Appliqué ». Les écarts sont à regarder avec le relevé Desjardins."),
        ("etape", "2. Page 5 : filtre « À traiter » : reliez les nouveaux articles Clover."),
        ("etape", "3. Page 8 : importez dans Sage les factures « Prêtes à importer » (Sage fermé)."),
        ("etape", "4. Sauvegardez le dossier des données (bouton du Tableau de bord)."),

        ("sous_titre", "Mode opératoire — chaque mois"),
        ("etape", "1. Page 10 : chargez le relevé Desjardins du mois, « Actualiser », choisissez le compte des "
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
        ("etape", "3. “1. Clover” page: paste the merchant ID and the token, then click “Test the Clover "
                  "connection”: the market's name must appear."),

        ("sous_titre", "Step 2 — Sage 50"),
        ("etape", "1. Read-only user. Open the file in Sage as sysadmin: Setup > Set Up Users > Add. Name: "
                  "mvogmbi_sync, with a password. Rights: “View” on Inventory & Services, Receivables and Payables; "
                  "“Third-party product access rights”: Read only."),
        ("etape", "2. “Vente Hebdomadaire” customer record: Import/Export tab, check “This customer uses my item "
                  "numbers”. Do the same on the record of each supplier whose invoices you import."),
        ("etape", "3. Item accounts: every item needs a revenue account. Market rule: asset account 15xx → "
                  "revenue 40xx and cost of goods 50xx (e.g. 1514 → 4014 / 5014)."),
        ("etape", "4. “2. Sage 50” page: choose the company file (.SAI), the mvogmbi_sync user and its password, "
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
        ("para", "Each Clover item must be linked to a Sage item number. The “5. Item mapping” page shows the "
                 "statuses:"),
        ("puce", "Automatic: same name or same barcode in Sage, linked with no action."),
        ("puce", "Confirmed: linked by you; kept at every update."),
        ("puce", "To confirm: a suggestion exists; check it then “Accept the suggestion”."),
        ("puce", "None: no Sage item with the right size; create it in Sage, then “Update from Clover and Sage”."),
        ("etape", "To link: select the item, search the Sage item, “Confirm the chosen item”, then “Save "
                  "changes”."),
        ("note", "Market rule: two different sizes (500 g / 1 kg, 6-36 / 7-36) are two different items; the "
                 "application refuses to link them."),

        ("sous_titre", "Step 6 — First run"),
        ("etape", "1. Dashboard > “Simulation (no import)”: invoices are prepared but not imported; read the "
                  "points to fix."),
        ("etape", "2. Fix them (items to link, missing accounts), close Sage, then “Run now”."),
        ("etape", "3. In Sage, open a “Vente YYYY-MM-DD” invoice of the “Vente Hebdomadaire” customer and compare "
                  "its total with the day's net sales in Clover."),

        ("sous_titre", "Going live (real company file)"),
        ("etape", "1. In the real file: create the mvogmbi_sync user, check the “Vente Hebdomadaire” customer box "
                  "(and the suppliers') and check the item accounts (step 2)."),
        ("etape", "2. “2. Sage 50” page: choose the real .SAI file, then “Test Sage access”."),
        ("etape", "3. Check the “First day to import” and run a simulation before the first night."),

        ("sous_titre", "Receipts for Clover deposits (page 7)"),
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

        ("sous_titre", "Supplier invoices (page 8)"),
        ("etape", "1. “Add invoices…” copies the PDFs or photos into the invoice folder (you can also drop them "
                  "there, then “Refresh”). Each invoice is read: supplier, number, date, lines and totals."),
        ("etape", "2. Check the Sage supplier (quick search), the number and the date; totals are checked "
                  "(subtotal + GST + QST = total)."),
        ("etape", "3. For each line: choose the Sage item (“Link and confirm”) and the packaging factor. Sage qty = "
                  "Qty × Factor; Sage price = Amount / Sage qty. Enter applies and moves to the next line; after the "
                  "last one, a new line is created."),
        ("etape", "4. “Save the invoice”: it becomes “Ready to import” once everything is linked and consistent."),
        ("etape", "5. Close Sage, then “Import into Sage”: each invoice is imported as a purchase invoice and "
                  "verified; it becomes “Imported”. An invoice already in Sage is refused."),
        ("note", "“Set aside” puts aside an invoice that must not be processed. Item and factor choices are "
                 "remembered for each supplier."),

        ("sous_titre", "Supplier payments (page 9)"),
        ("etape", "1. Choose the “Read since” date, then “Refresh”: the Interac transfer notices received since that "
                  "date are read, along with the unpaid invoices in Sage. All transfers not yet processed are shown."),
        ("etape", "2. For each transfer: check the suggested Sage supplier (remembered for the next transfers to the "
                  "same payee), select the paid invoice(s) (Ctrl+click for several), then “Confirm payment”."),
        ("etape", "3. Confirmed payments are entered in Sage at night (account 1055, “Cash”, at the transfer date), "
                  "or right away with “Pay in Sage” (Sage closed). Each becomes “Entered in Sage” after the invoice "
                  "balances are verified."),
        ("note", "A partial payment is accepted. “Ignore” sets aside a transfer that is not for a supplier; "
                 "“Already in Sage” flags a payment already entered by hand."),

        ("sous_titre", "Bank reconciliation (page 10)"),
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

        ("sous_titre", "Operating procedure — every morning"),
        ("etape", "1. Read the nightly email: “success”, or the list of points to fix."),
        ("etape", "2. A blocked day: fix the cause (item to link, missing account…); it is resumed the following "
                  "night, or right away with “Run now” (Sage closed)."),
        ("etape", "3. Page 9: “Refresh”, then confirm the new transfers to suppliers."),
        ("etape", "4. Page 8: add the supplier invoices received, check them and save them."),
        ("etape", "5. Before leaving in the evening: close Sage, so the nightly run can import and enter."),

        ("sous_titre", "Operating procedure — every week"),
        ("etape", "1. Page 7: “Calculate deposits” for the past week; every deposit must be “Applied”. Check "
                  "differences against the Desjardins statement."),
        ("etape", "2. Page 5: “To handle” filter: link the new Clover items."),
        ("etape", "3. Page 8: import into Sage the invoices “Ready to import” (Sage closed)."),
        ("etape", "4. Back up the data folder (Dashboard button)."),

        ("sous_titre", "Operating procedure — every month"),
        ("etape", "1. Page 10: load the month's Desjardins statement, “Refresh”, choose the account of the "
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
