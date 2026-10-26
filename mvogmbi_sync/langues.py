"""Langues de l'application (français par défaut, anglais).

Le texte français sert de clé : t("Enregistrer") renvoie « Save » en anglais. Un texte sans traduction
reste en français. La langue est enregistrée dans config.toml : [general] langue = "fr" | "en".
"""

from __future__ import annotations

LANGUES = {"fr": "Français", "en": "English"}
_courante = "fr"


def definir(code: str | None) -> None:
    global _courante
    _courante = code if code in LANGUES else "fr"


def courante() -> str:
    return _courante


def depuis_config(config_toml: dict) -> str:
    definir(config_toml.get("general", {}).get("langue", "fr"))
    return _courante


def t(texte: str, **valeurs) -> str:
    traduit = EN.get(texte, texte) if _courante == "en" else texte
    return traduit.format(**valeurs) if valeurs else traduit


def jours_semaine() -> list[str]:
    if _courante == "en":
        return ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    return ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]


EN: dict[str, str] = {
    # ------------------------------------------------------------------ mise en route, guide, design
    "Guide de configuration": "Setup guide",
    "Mise en route": "Getting started",
    "Six étapes pour une synchronisation entièrement automatique. Chaque étape passe au vert quand elle est faite.":
        "Six steps to a fully automatic synchronization. Each step turns green once done.",
    "Ouvrir": "Open",
    "Clover": "Clover", "Sage 50": "Sage 50", "Courriel": "Email", "Automatisation": "Automation",
    "Correspondance": "Item mapping", "Premier import": "First import",
    "Identifiant marchand et jeton API": "Merchant ID and API token",
    "Fichier d'entreprise et mots de passe": "Company file and passwords",
    "Compte rendu après chaque nuit": "Report after each night",
    "Tâche planifiée installée": "Scheduled task installed",
    "Articles Clover reliés à Sage": "Clover items linked to Sage",
    "Une facture importée dans Sage": "One invoice imported into Sage",
    "L'application lit les ventes payées dans Clover ; elle n'y modifie jamais rien.":
        "The application reads paid sales in Clover; it never changes anything there.",
    "Identifiants Clover": "Clover credentials",
    "Fichier d'entreprise": "Company file",
    "Utilisateurs Sage": "Sage users",
    "Serveur d'envoi": "Outgoing server",
    "Envoi du compte rendu": "Sending the report",
    "Outils": "Tools",
    # ------------------------------------------------------------------ factures fournisseurs
    '   •   liste des fournisseurs Sage absente : cliquez sur « Fournisseurs et articles Sage »': '   •   Sage supplier list missing: click “Sage suppliers and items”',
    '8. Factures fournisseurs': '8. Supplier invoices',
    'Factures impayées de ce fournisseur dans Sage (Ctrl+clic : plusieurs factures pour un même virement) :': 'Unpaid invoices of this supplier in Sage (Ctrl+click: several invoices for one transfer):',
    "Le virement ({m} $) dépasse le solde des factures choisies ({s} $) : choisissez d'autres factures (Ctrl+clic).": 'The transfer (${m}) exceeds the balance of the chosen invoices (${s}): choose other invoices (Ctrl+click).',
    '  (partiel, solde {s} $)': '  (partial, balance ${s})',
    'Répartir le virement de {m} $ ainsi ?\n\n{detail}': 'Split the ${m} transfer this way?\n\n{detail}',
    '\n\n{n} facture(s) choisie(s) inutile(s) : non payée(s).': '\n\n{n} chosen invoice(s) not needed: not paid.',
    'virement réparti sur {n} factures': 'transfer split over {n} invoices',
    'Lire depuis le': 'Read since',
    'Date invalide (AAAA-MM-JJ).': 'Invalid date (YYYY-MM-DD).',
    'saisi entre-temps dans Sage': 'entered in Sage in the meantime',
    '(cliquez sur « Actualiser » pour charger les factures impayées)': '(click “Refresh” to load unpaid invoices)',
    'Payer dans Sage': 'Pay in Sage',
    'Le virement ({m} $) dépasse le solde de la facture ({s} $) : saisissez-le à la main dans Sage (plusieurs factures), puis « Ignorer ».': 'The transfer (${m}) exceeds the invoice balance (${s}): enter it manually in Sage (several invoices), then “Ignore”.',
    'paiement partiel : virement {m} $, solde {s} $': 'partial payment: transfer ${m}, balance ${s}',
    "Aucun paiement « Confirmé (à saisir) » : confirmez d'abord les virements.": 'No “Confirmed (to enter)” payment: confirm the transfers first.',
    "Fermez Sage : le robot l'ouvre lui-même, hors écran, pour saisir les paiements.": 'Close Sage: the robot opens it itself, off screen, to enter the payments.',
    "Saisir {n} paiement(s) dans Sage (compte 1055, Comptant) ?\n\n{liste}\n\nLe robot ouvre Sage hors écran ; n'ouvrez pas Sage pendant ce temps.": 'Enter {n} payment(s) in Sage (account 1055, Cash)?\n\n{liste}\n\nThe robot opens Sage off screen; do not open Sage meanwhile.',
    'Saisie des paiements dans Sage par le robot…': 'The robot is entering the payments in Sage…',
    '{ok} paiement(s) saisi(s) sur {n}.': '{ok} payment(s) entered out of {n}.',
    ' — {n} paiement(s) fournisseur(s)': ' — {n} supplier payment(s)',
    'MVOGMBI_Sync : paiements fournisseurs — {n} point(s) à vérifier': 'MVOGMBI_Sync: supplier payments — {n} item(s) to check',
    'MVOGMBI_Sync : {n} paiement(s) fournisseur(s) saisi(s)': 'MVOGMBI_Sync: {n} supplier payment(s) entered',
    'Paiements fournisseurs saisis dans Sage :': 'Supplier payments entered in Sage:',
    '9. Paiements fournisseurs': '9. Supplier payments',
    'Lire la boîte et Sage': 'Read mailbox and Sage',
    'À traiter': 'To process',
    'Bénéficiaire': 'Payee',
    'Message': 'Message',
    'Facture': 'Invoice',
    'Solde dû': 'Balance due',
    'Sélectionnez un virement dans la liste.': 'Select a transfer in the list.',
    'Factures impayées de ce fournisseur dans Sage :': 'Unpaid invoices of this supplier in Sage:',
    'Confirmer le paiement': 'Confirm payment',
    'Ignorer (pas un fournisseur)': 'Ignore (not a supplier)',
    'Remettre à relier': 'Back to link',
    'Lecture de la boîte de courriel et des factures impayées dans Sage…': 'Reading the mailbox and unpaid invoices in Sage…',
    'Réglez la boîte des avis de paiement (page Courriel).': 'Set up the payment notice mailbox (Email page).',
    '{n} nouvel(s) avis lu(s)': '{n} new notice(s) read',
    '{n} virement(s) — à relier : {r}, proposés : {p}, confirmés : {c}, déjà dans Sage : {d}, ignorés : {i}, annulés/expirés : {x}': '{n} transfer(s) — to link: {r}, suggested: {p}, confirmed: {c}, already in Sage: {d}, ignored: {i}, cancelled/expired: {x}',
    'Virement Interac du {d} : {m} $ à {b}   •   réf. {r}\nMessage : « {msg} »': 'Interac transfer of {d}: ${m} to {b}   •   ref. {r}\nMessage: “{msg}”',
    '(cliquez sur « Lire la boîte et Sage » pour charger les factures impayées)': '(click “Read mailbox and Sage” to load unpaid invoices)',
    'Choisissez le fournisseur Sage, puis la facture payée dans la liste.': 'Choose the Sage supplier, then the paid invoice in the list.',
    'Le virement ({m} $) dépasse le solde de la facture ({s} $). Confirmer quand même ?': 'The transfer (${m}) exceeds the invoice balance (${s}). Confirm anyway?',
    'paiement partiel ou écart : virement {m} $, solde {s} $': 'partial payment or difference: transfer ${m}, balance ${s}',
    'ignoré par le propriétaire': 'ignored by the owner',
    'Proposé': 'Suggested',
    'Confirmé (à saisir)': 'Confirmed (to enter)',
    'Déjà dans Sage': 'Already in Sage',
    'Saisi dans Sage': 'Entered in Sage',
    'Ignoré': 'Ignored',
    'Annulé / expiré': 'Cancelled / expired',
    "Avis de paiement (lecture de la boîte)": "Payment notices (mailbox reading)",
    "Boîte où arrivent les avis Interac de Desjardins : l'application les lit (sans les marquer comme lus) pour "
    "enregistrer les paiements aux fournisseurs.":
        "Mailbox receiving Desjardins Interac notices: the application reads them (without marking them read) to "
        "record supplier payments.",
    "Serveur (IMAP)": "Server (IMAP)",
    "Adresse": "Address",
    "Lire les avis à partir du": "Read notices from",
    "Importer dans Sage": "Import into Sage",
    "Aucune facture « Prête à importer ». Reliez tous les articles et enregistrez la facture pour qu'elle le devienne.":
        "No invoice “Ready to import”. Link all items and save the invoice to make it ready.",
    "Fermez Sage : l'import exige le mode mono-utilisateur (personne d'autre dans le fichier d'entreprise).":
        "Close Sage: the import requires single-user mode (nobody else in the company file).",
    "Importer {n} facture(s) dans Sage ?\n\n{liste}": "Import {n} invoice(s) into Sage?\n\n{liste}",
    "Import dans Sage en cours (contrôles, import, vérification)…": "Importing into Sage (checks, import, verification)…",
    "Écarter": "Set aside",
    "aucune nouvelle facture": "no new invoice",
    "Choisissez d'abord la facture à écarter dans la liste.": "First choose the invoice to set aside in the list.",
    "Écarter la facture « {f} » ?\n\nElle ne sera plus dans la liste à traiter. Son fichier est rangé dans le "
    "sous-dossier « ecartees » : remettez-le dans le dossier des factures pour la traiter plus tard.":
        "Set aside the invoice “{f}”?\n\nIt will no longer be in the list to process. Its file is moved to the "
        "“ecartees” subfolder: put it back in the invoice folder to process it later.",
    "Prix fournisseur": "Supplier price",
    "Prix Sage": "Sage price",
    "Le facteur doit être supérieur à 0.": "The factor must be greater than 0.",
    "Dans Sage : {q} × {p} $ = {m} $ (prix Sage = montant / quantité Sage)":
        "In Sage: {q} × ${p} = ${m} (Sage price = amount / Sage quantity)",
    "Choisissez le fournisseur dans la liste des fournisseurs Sage.": "Choose the supplier from the Sage supplier list.",
    "Ajouter des factures…": "Add invoices…",
    "Factures fournisseurs à ajouter": "Supplier invoices to add",
    "Factures (PDF, photos)": "Invoices (PDF, photos)",
    "Fichiers ignorés (format non accepté) : {f}": "Files skipped (format not accepted): {f}",
    'Appliquer': 'Apply',
    'Article Sage :': 'Sage item:',
    'Aucune nouvelle facture dans le dossier :\n{d}': 'No new invoice in the folder:\n{d}',
    'Choisissez une ligne de la facture, puis un article Sage dans la liste.': 'Choose an invoice line, then a Sage item in the list.',
    'Confirmer la proposition': 'Confirm the suggestion',
    'Confirmée': 'Confirmed',
    'Dans Sage : {q} × {p} $ = {m} $ (conditionnement × {f})': 'In Sage: {q} × ${p} = ${m} (pack × {f})',
    'Dossier des factures': 'Invoice folder',
    'Enregistrer la facture': 'Save invoice',
    'Facture cohérente et entièrement reliée : prête à importer.': 'Consistent, fully linked invoice: ready to import.',
    'Fournisseur Sage': 'Sage supplier',
    'Fournisseurs et articles Sage': 'Sage suppliers and items',
    'Frais': 'Charges',
    "Lecture de {n} facture(s) (l'OCR prend quelques secondes par page)…": 'Reading {n} invoice(s) (OCR takes a few seconds per page)…',
    'Lecture des fournisseurs et des articles dans Sage…': 'Reading suppliers and items in Sage…',
    'Les formats semblent différents (« {f} » / « {s} »). Deux formats différents sont deux articles différents. Relier quand même (conditionnement différent) ?': 'The sizes look different (“{f}” / “{s}”). Two different sizes are two different items. Link anyway (different packaging)?',
    'Lire les nouvelles factures': 'Read new invoices',
    'Lu sur la facture : {f}   •   lecture : {m}': 'Read on the invoice: {f}   •   reading: {m}',
    'Nombre invalide : {v}': 'Invalid number: {v}',
    'Nouvelle ligne': 'New line',
    'Proposée': 'Suggested',
    'Relier et confirmer': 'Link and confirm',
    'Supprimer la ligne « {d} » ?': 'Delete line “{d}”?',
    'Taxable': 'Taxable',
    'Toutes': 'All',
    'Voir la facture': 'View invoice',
    '{n} facture(s) — à saisir : {s}, à vérifier : {v}, prêtes : {p}, importées : {i}': '{n} invoice(s) — to enter: {s}, to check: {v}, ready: {p}, imported: {i}',
    'À relier': 'To link',
    'Fichier': 'File',
    'N°': 'No.',
    'Code': 'Code',
    'Désignation du fournisseur': 'Supplier description',
    'Qté': 'Qty',
    'Prix': 'Price',
    'N° Sage': 'Sage no.',
    'Désignation Sage': 'Sage description',
    'Facteur': 'Factor',
    'Qté Sage': 'Sage qty',
    'N° de facture': 'Invoice no.',
    'TPS': 'GST',
    'TVQ': 'QST',
    'Désignation': 'Description',
    'À vérifier': 'To check',
    'À saisir (photo)': 'To enter (photo)',
    'Prête à importer': 'Ready to import',
    'Importée dans Sage': 'Imported into Sage',
    " — {n} dépôt(s) encaissé(s)": " — {n} deposit(s) recorded",
    "MVOGMBI_Sync : encaissements — {n} point(s) à vérifier": "MVOGMBI_Sync: receipts — {n} point(s) to check",
    "MVOGMBI_Sync : encaissements": "MVOGMBI_Sync: receipts",
    "Encaissements des dépôts Clover (compte Desjardins) :": "Receipts of Clover deposits (Desjardins account):",
    "Encaisser à partir des ventes du": "Record receipts from sales of",
    "AAAA-MM-JJ. Les dépôts des ventes antérieures ne sont jamais encaissés par le robot.":
        "YYYY-MM-DD. Deposits for earlier sales are never recorded by the robot.",
    "Fermez Sage : le robot l'ouvre lui-même, hors écran, pour encaisser les dépôts.":
        "Close Sage: the robot opens it itself, off screen, to record the deposits.",
    "Encaisser {n} dépôt(s) ({total}) dans Sage ? Le robot ouvre Sage hors écran ; n'ouvrez pas Sage pendant ce temps.":
        "Record {n} deposit(s) ({total}) in Sage? The robot opens Sage off screen; do not open Sage meanwhile.",
    # ------------------------------------------------------------------ encaissements
    "7. Encaissements": "7. Receipts",
    "Compte de dépôt des encaissements": "Receipts deposit account",
    "Compte de banque Sage où Clover dépose les ventes par carte (1055 = Compte Desjardins).":
        "Sage bank account where Clover deposits card sales (1055 = Desjardins account).",
    "Ventes du": "Sales from", "au": "to",
    "Calculer les dépôts": "Calculate deposits",
    "Cliquez sur « Calculer les dépôts » : lots de cartes Clover et état dans Sage.":
        "Click “Calculate deposits”: Clover card batches and status in Sage.",
    "Montant": "Amount", "Montant dû (Sage)": "Amount due (Sage)",
    "Date du dépôt / facture": "Deposit date / invoice",
    "Saisie dans Sage (Encaissements)": "Entry in Sage (Receipts)",
    "Copier": "Copy",
    "Sélectionnez un dépôt dans le tableau.": "Select a deposit in the table.",
    "Vérifiez les dates (AAAA-MM-JJ).": "Check the dates (YYYY-MM-DD).",
    "Calcul en cours : lots de cartes Clover, puis lecture de Sage…": "Calculating: Clover card batches, then reading Sage…",
    "{n} dépôt(s), {total} au total — {a} à saisir dans Sage, {ok} déjà appliqué(s).":
        "{n} deposit(s), {total} in total — {a} to enter in Sage, {ok} already applied.",
    "Encaissements > Payé par : Comptant ; Reçu de : {client}": "Receipts > Paid by: Cash; From: {client}",
    "Dépôt : {compte} (compte Desjardins)": "Deposit to: {compte} (Desjardins account)",
    "Date : {date}": "Date: {date}",
    "Montant reçu, facture par facture :": "Amount received, invoice by invoice:",
    "Total du dépôt : {total}": "Deposit total: {total}",
    "Puis « Traiter ». L'état passera à « Appliqué » au prochain calcul.":
        "Then “Process”. The status will turn to “Applied” at the next calculation.",
    "Calculez d'abord les dépôts.": "Calculate the deposits first.",
    "Fichier ouvert dans Excel : fermez-le puis recommencez.": "File open in Excel: close it and try again.",
    "Appliqué": "Applied", "À saisir dans Sage": "To enter in Sage",
    "Encaisser dans Sage": "Record in Sage",
    "Aucun dépôt « À saisir dans Sage » : calculez d'abord les dépôts.":
        "No deposit “To enter in Sage”: calculate the deposits first.",
    "Ouvrez Sage sur le fichier d'entreprise, puis la fenêtre Clients & Ventes > Encaissements, et recommencez.":
        "Open Sage on the company file, then the Receivables > Receipts window, and try again.",
    "Encaisser {n} dépôt(s) ({total}) dans Sage ? N'utilisez pas Sage pendant la saisie.":
        "Record {n} deposit(s) ({total}) in Sage? Do not use Sage during the entry.",
    "Saisie des encaissements dans Sage en cours…": "Recording receipts in Sage…",
    "{ok} dépôt(s) encaissé(s) sur {n}.": "{ok} deposit(s) recorded out of {n}.",
    "Montant différent dans Sage": "Different amount in Sage",
    "Facture pas encore dans Sage": "Invoice not yet in Sage", "Dépôt à venir": "Upcoming deposit",
    "Autres destinataires": "Other recipients",
    "Facultatif : autres personnes à informer, adresses séparées par des virgules "
    "(ex. comptable@exemple.com, gerant@exemple.com).":
        "Optional: other people to inform, addresses separated by commas "
        "(e.g. accountant@example.com, manager@example.com).",
    "Adresse(s) courriel invalide(s) : {liste}": "Invalid email address(es): {liste}",
    # ------------------------------------------------------------------ en-tête, général
    "Marché MVOG-MBI Sherbrooke": "Marché MVOG-MBI Sherbrooke",
    "Synchronisation des ventes Clover → Sage 50": "Clover → Sage 50 sales synchronization",
    "Chaque nuit, les ventes Clover sont importées dans Sage 50 : une facture par jour, une pour la fin de semaine.":
        "Every night, Clover sales are imported into Sage 50: one invoice per day, one for the weekend.",
    "Langue": "Language",
    "Tous droits réservés.": "All rights reserved.",
    "Enregistrer la configuration": "Save configuration",
    "Configuration enregistrée.": "Configuration saved.",
    "Parcourir…": "Browse…",
    "terminé": "done",
    # ------------------------------------------------------------------ onglets
    "Accueil": "Home",
    "1. Clover": "1. Clover",
    "2. Sage 50": "2. Sage 50",
    "3. Courriel": "3. Email",
    "4. Automatisation": "4. Automation",
    "5. Correspondance des articles": "5. Item mapping",
    "5. Correspondance": "5. Item mapping",
    "6. Tableau de bord": "6. Dashboard",
    "Aide / FAQ": "Help / FAQ",
    # ------------------------------------------------------------------ Clover
    "Accès à votre compte Clover (lecture des ventes)": "Access to your Clover account (sales reading)",
    "Identifiant marchand": "Merchant ID",
    "13 caractères, visibles dans l'adresse du tableau de bord Clover après « /m/ ».":
        "13 characters, shown in the Clover dashboard address after “/m/”.",
    "Jeton API": "API token",
    "Clover > Compte et configuration > Jetons API (droits en lecture). Laissez « •••• » pour conserver le jeton enregistré.":
        "Clover > Account & Setup > API Tokens (read permissions). Leave “••••” to keep the saved token.",
    "Tester la connexion à Clover": "Test the Clover connection",
    "Test Clover": "Clover test",
    "connecté à « {nom} »": "connected to “{nom}”",
    # ------------------------------------------------------------------ Sage
    "Fichier d'entreprise et comptes Sage": "Sage company file and accounts",
    "Fichier d'entreprise Sage": "Sage company file",
    "Tous les fichiers": "All files",
    "Fichier d'entreprise (.SAI)": "Company file (.SAI)",
    "Le fichier dans lequel les factures sont importées. Pour les essais : une COPIE.":
        "The file the invoices are imported into. For testing: a COPY.",
    "Utilisateur Sage (lecture)": "Sage user (read)",
    "Utilisateur avec « Droits d'accès aux produits tiers : Consultation seule » et accès Vue aux modules Stocks & Services et Clients & Ventes.":
        "User with “Third-party product access rights: Read only” and View access to the Inventory & Services "
        "and Customers & Sales modules.",
    "Mot de passe (lecture)": "Password (read)",
    "Mot de passe Sage pour l'import": "Sage password for importing",
    "Mot de passe demandé par la fenêtre « Sage 50 - Password » de l'import (utilisateur sysadmin).":
        "Password requested by the “Sage 50 - Password” import window (sysadmin user).",
    "Premier jour à importer": "First day to import",
    "AAAA-MM-JJ. Utilisé seulement si Sage ne contient encore aucune facture « Vente AAAA-MM-JJ ».":
        "YYYY-MM-DD. Used only if Sage does not yet contain any “Vente YYYY-MM-DD” invoice.",
    "Tester l'accès à Sage": "Test Sage access",
    "Test Sage": "Sage test",
    "fichier introuvable : {fichier}": "file not found: {fichier}",
    "Sage ouvert": "Sage open",
    "Sage fermé : base ouverte puis refermée automatiquement": "Sage closed: database opened then closed automatically",
    "À RÉGLER : cocher « Ce client utilise mes n° articles » dans la fiche du client":
        "TO FIX: check “This customer uses my item numbers” in the customer record",
    "{mode}. {n} articles. Dernière facture journalière : {derniere}. Client « {client} » : {etat}. Articles sans compte de produits : {sans}.":
        "{mode}. {n} items. Last daily invoice: {derniere}. Customer “{client}”: {etat}. Items without a revenue account: {sans}.",
    "aucune": "none",
    # ------------------------------------------------------------------ Courriel
    "Alertes par courriel": "Email reports",
    "Serveur d'envoi (SMTP)": "Outgoing server (SMTP)",
    "Ex. smtp.office365.com (Outlook) ou smtp.gmail.com (Gmail : mot de passe d'application).":
        "E.g. smtp.office365.com (Outlook) or smtp.gmail.com (Gmail: app password).",
    "Port": "Port",
    "Sécurité": "Security",
    "Utilisateur": "User",
    "Mot de passe": "Password",
    "Expéditeur": "Sender",
    "Destinataire(s)": "Recipient(s)",
    "Une ou plusieurs adresses séparées par des virgules.": "One or more addresses separated by commas.",
    "Envoyer le compte rendu après chaque traitement, y compris en cas de succès (dates traitées et leur état)":
        "Send the report after every run, including on success (processed dates and their status)",
    "Envoyer un courriel de test": "Send a test email",
    "Courriel de test": "Test email",
    "MVOGMBI_Sync : courriel de test": "MVOGMBI_Sync: test email",
    "Ce courriel confirme que les alertes de MVOGMBI_Sync sont bien configurées.":
        "This email confirms that MVOGMBI_Sync reports are correctly configured.",
    "courriel envoyé": "email sent",
    # ------------------------------------------------------------------ Automatisation
    "Traitement automatique quotidien": "Daily automatic run",
    "Heure du traitement": "Run time",
    "HH:MM. L'ordinateur doit être allumé et la session Windows ouverte ; Sage peut être fermé.":
        "HH:MM. The computer must be on and the Windows session open; Sage may be closed.",
    "Installer la tâche planifiée": "Install the scheduled task",
    "Retirer la tâche": "Remove the task",
    "État de la tâche": "Task status",
    "Créer un raccourci sur le Bureau": "Create a desktop shortcut",
    "Reprendre une configuration existante…": "Import an existing configuration…",
    "Copie config.toml, la correspondance des articles et les articles à relier depuis un autre dossier (ex. le dossier du projet). Les mots de passe restent dans le coffre-fort.":
        "Copies config.toml, the item mapping and the items to link from another folder (e.g. the project "
        "folder). Passwords stay in the Windows vault.",
    "Installation de la tâche": "Installing the task",
    "Retrait de la tâche": "Removing the task",
    "Retirer la tâche planifiée ? Les ventes ne seront plus importées automatiquement.":
        "Remove the scheduled task? Sales will no longer be imported automatically.",
    "Raccourci sur le Bureau": "Desktop shortcut",
    "créé": "created",
    "Dossier contenant config.toml (et le sous-dossier donnees)": "Folder containing config.toml (and the donnees subfolder)",
    "Aucun fichier de configuration trouvé dans ce dossier.": "No configuration file found in this folder.",
    "Repris : {fichiers}.\nL'application va se fermer : rouvrez-la.": "Imported: {fichiers}.\nThe application will close: reopen it.",
    # ------------------------------------------------------------------ Tableau de bord
    "Lancer maintenant": "Run now",
    "Simulation (sans import)": "Simulation (no import)",
    "Ouvrir la correspondance des articles": "Open the item mapping",
    "Dossier des données": "Data folder",
    "Actualiser": "Refresh",
    "Lancer le traitement maintenant ? Les factures manquantes seront importées dans Sage.":
        "Run now? Missing invoices will be imported into Sage.",
    "Simulation": "Simulation",
    "Traitement": "Run",
    "réussi": "successful",
    "terminé avec des points à corriger (voir ci-dessus)": "finished with items to fix (see above)",
    "Introuvable pour l'instant : {chemin}": "Not found yet: {chemin}",
    "Dernière facture importée : {derniere}     •     Tâche planifiée : {tache}":
        "Last imported invoice: {derniere}     •     Scheduled task: {tache}",
    "installée": "installed",
    "Dernière facture importée": "Last imported invoice",
    "Tâche planifiée": "Scheduled task",
    "Points à corriger (dernier traitement)": "Items to fix (last run)",
    "NON installée": "NOT installed",
    "Vérifiez la date (AAAA-MM-JJ), l'heure (HH:MM) et le port du courriel.":
        "Check the date (YYYY-MM-DD), the time (HH:MM) and the email port.",
    # ------------------------------------------------------------------ Correspondance
    "Afficher :": "Show:",
    "Rechercher :": "Search:",
    "À traiter (À confirmer + Aucun)": "To handle (To confirm + None)",
    "Tous": "All",
    "Confirmé": "Confirmed",
    "Automatique": "Automatic",
    "À confirmer": "To confirm",
    "Aucun": "None",
    "Mettre à jour depuis Clover et Sage": "Update from Clover and Sage",
    "Recharger": "Reload",
    "Statut": "Status",
    "Article Clover": "Clover item",
    "Catégorie": "Category",
    "Ventes 30 j": "30-day sales",
    "N° article Sage": "Sage item no.",
    "Description Sage": "Sage description",
    "Article sélectionné": "Selected item",
    "Sélectionnez un article dans le tableau.": "Select an item in the table.",
    "Chercher un article Sage :": "Find a Sage item:",
    "Confirmer l'article choisi": "Confirm the chosen item",
    "Accepter la proposition": "Accept the suggestion",
    "Retirer la confirmation": "Remove the confirmation",
    "Enregistrer les modifications": "Save changes",
    "Abandonner les modifications non enregistrées ?": "Discard unsaved changes?",
    "{n} articles Clover — Confirmé : {c}   Automatique : {a}   À confirmer : {q}   Aucun : {z}   •   affichés : {v}":
        "{n} Clover items — Confirmed: {c}   Automatic: {a}   To confirm: {q}   None: {z}   •   shown: {v}",
    "   •   MODIFICATIONS NON ENREGISTRÉES": "   •   UNSAVED CHANGES",
    "   •   liste Sage absente : cliquez sur « Mettre à jour »": "   •   Sage list missing: click “Update”",
    "Clover : {nom}   (catégorie {cat}, ID {id})\nSage : {num} {desc}   •   statut {statut}, méthode {methode}":
        "Clover: {nom}   (category {cat}, ID {id})\nSage: {num} {desc}   •   status {statut}, method {methode}",
    "\nAutres suggestions : {s}": "\nOther suggestions: {s}",
    "  (autre format)": "  (different size)",
    "sans compte": "no account",
    "Sélectionnez un article dans le tableau, puis un article Sage dans la liste.":
        "Select an item in the table, then a Sage item in the list.",
    "« {a} » et « {b} » n'ont pas le même format.\nDeux formats différents sont deux articles différents. Confirmer quand même ?":
        "“{a}” and “{b}” are not the same size.\nTwo different sizes are two different items. Confirm anyway?",
    "L'article Sage {num} n'a pas de compte de produits : l'import sera bloqué tant qu'il n'est pas complété dans Sage.":
        "Sage item {num} has no revenue account: imports will be blocked until it is completed in Sage.",
    "Aucune proposition pour cet article : choisissez un article Sage dans la liste.":
        "No suggestion for this item: choose a Sage item in the list.",
    "Aucune modification à enregistrer.": "No changes to save.",
    "Le fichier de correspondance est ouvert dans Excel : fermez-le puis réessayez.":
        "The mapping file is open in Excel: close it and try again.",
    "Correspondance enregistrée (copie de sécurité de l'ancienne version faite).":
        "Mapping saved (backup of the previous version made).",
    "Enregistrez d'abord vos modifications.": "Save your changes first.",
    "Mise à jour en cours (lecture de Clover et de Sage, quelques minutes)…":
        "Updating (reading Clover and Sage, a few minutes)…",
    "Correspondance mise à jour.\n\n{resume}": "Mapping updated.\n\n{resume}",
    "Mise à jour impossible.\n\n{resume}": "Update failed.\n\n{resume}",
    "Manuel (application)": "Manual (application)",
    # ------------------------------------------------------------------ états des dates (courriel)
    "Facture importée": "Invoice imported",
    "Facture prête (simulation)": "Invoice ready (simulation)",
    "Aucune vente": "No sales",
    "Facture déjà présente dans Sage": "Invoice already in Sage",
    "Bloquée": "Blocked",
    "Reportée à la prochaine exécution": "Postponed to the next run",
    "Échec de l'import": "Import failed",
    # ------------------------------------------------------------------ courriel de compte rendu
    "SIMULATION — ": "SIMULATION — ",
    "MVOGMBI_Sync : ERREUR du traitement automatique": "MVOGMBI_Sync: automatic run ERROR",
    "MVOGMBI_Sync : {n} point(s) à corriger — {i} facture(s) importée(s)":
        "MVOGMBI_Sync: {n} item(s) to fix — {i} invoice(s) imported",
    "MVOGMBI_Sync : Sage est à jour (dernière facture : {d})": "MVOGMBI_Sync: Sage is up to date (last invoice: {d})",
    "MVOGMBI_Sync : {n} facture(s) prête(s) {periode}": "MVOGMBI_Sync: {n} invoice(s) ready {periode}",
    "MVOGMBI_Sync : succès — {n} facture(s) importée(s) {periode}": "MVOGMBI_Sync: success — {n} invoice(s) imported {periode}",
    "du {d} au {f}": "from {d} to {f}",
    "du {d}": "for {d}",
    "Traitement du {d}": "Run of {d}",
    " (SIMULATION : aucun import)": " (SIMULATION: no import)",
    "Fichier Sage : {f}": "Sage file: {f}",
    "Dernière facture journalière avant le traitement : {d}": "Last daily invoice before the run: {d}",
    "Période traitée : du {d} au {f}": "Processed period: from {d} to {f}",
    "Période traitée : aucune (Sage était déjà à jour)": "Processed period: none (Sage was already up to date)",
    "Dates traitées :": "Processed dates:",
    " — {l} lignes, sous-total {s}, taxes {t}, total {total}": " — {l} lines, subtotal {s}, taxes {t}, total {total}",
    "Total importé : {n} facture(s), {total} taxes comprises": "Total imported: {n} invoice(s), {total} including taxes",
    "À corriger (le traitement reprendra automatiquement la nuit suivante) :":
        "To fix (the run will resume automatically the following night):",
    "Erreur :": "Error:",
    "Déroulement :": "Run log:",
    "Date": "Date", "Jour": "Day", "État": "Status", "Lignes": "Lines", "Sous-total": "Subtotal",
    "Taxes": "Taxes", "Total": "Total", "Détail": "Details",
    "À corriger": "To fix",
    "Le traitement reprendra automatiquement la nuit suivante.": "The run will resume automatically the following night.",
    "Erreur": "Error",
    "Déroulement détaillé": "Detailed log",
    "Période traitée : ": "Processed period: ",
    "du <b>{d}</b> au <b>{f}</b>": "from <b>{d}</b> to <b>{f}</b>",
    "aucune (Sage était déjà à jour)": "none (Sage was already up to date)",
    " — <b>SIMULATION</b> : aucun import": " — <b>SIMULATION</b>: no import",
}
