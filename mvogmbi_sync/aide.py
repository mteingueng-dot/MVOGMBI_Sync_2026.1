"""Contenu des pages « Accueil / À propos », « Guide de configuration » et « Aide / FAQ », en français et en anglais.

Chaque page est une liste de blocs (type, texte) : titre, sous_titre, para, puce, etape, note, question, reponse.
"""

from __future__ import annotations

VERSION = "1.9.0"
EDITEUR = "Concept Informatique inc."
COPYRIGHT = f"© 2026 {EDITEUR}"

ACCUEIL = {
    "fr": [
        ("titre", "Bienvenue dans MVOGMBI_Sync"),
        ("para", "MVOGMBI_Sync relie le point de vente Clover du Marché MVOG-MBI Sherbrooke à la comptabilité "
                 "Sage 50. Chaque nuit, les ventes de la veille sont transformées automatiquement en facture de "
                 "vente dans Sage, sans aucune saisie manuelle."),
        ("sous_titre", "Comment ça fonctionne"),
        ("etape", "1. Chaque nuit à l'heure choisie (1 h par défaut), l'application lit dans Sage la dernière "
                  "facture « Vente AAAA-MM-JJ » déjà importée."),
        ("etape", "2. Elle récupère dans Clover les ventes de chaque jour suivant, jusqu'à hier : un jour manqué "
                  "est rattrapé automatiquement."),
        ("etape", "3. Elle relie chaque article Clover à son numéro d'article Sage (correspondance des articles)."),
        ("etape", "4. Elle prépare pour le client « Vente Hebdomadaire » une facture par jour du lundi au jeudi "
                  "et une seule pour le vendredi, le samedi et le dimanche : une ligne par article, montant = ventes "
                  "nettes Clover, taxes TPS + TVQ (code GQ) pour les articles taxés."),
        ("etape", "5. Elle importe les factures dans Sage, vérifie chacune d'elles, encaisse les dépôts Clover sur "
                  "les factures (Sage ouvert par le robot, hors écran) et vous envoie un compte rendu par courriel."),
        ("sous_titre", "Contrôles de sécurité"),
        ("puce", "Jamais deux fois la même facture : une date déjà présente dans Sage est ignorée."),
        ("puce", "Arrêt au premier jour qui pose problème (article non relié, compte manquant…) ; ce jour est "
                 "repris la nuit suivante, une fois le problème corrigé, sans trou dans la suite des factures."),
        ("puce", "Deux formats différents (ex. 500 g et 1 kg) ne sont jamais confondus."),
        ("puce", "Le total de chaque facture est égal aux ventes nettes Clover de la journée."),
        ("puce", "Les mots de passe et le jeton Clover sont gardés dans le coffre-fort de Windows."),
        ("sous_titre", "Pour commencer"),
        ("para", "Suivez la liste « Mise en route » ci-dessus : chaque étape passe au vert quand elle est faite. "
                 "Le « Guide de configuration » décrit chaque étape en détail (Clover, Sage 50, courriel, "
                 "automatisation, correspondance, mise en production) ; « Aide / FAQ » répond aux questions courantes."),
        ("sous_titre", "À propos"),
        ("para", f"MVOGMBI_Sync version {VERSION} — Marché MVOG-MBI Sherbrooke, épicerie africaine & caribéenne."),
        ("para", "Logiciels reliés : Clover (point de vente) et Sage 50 Comptabilité, Édition canadienne."),
        ("para", f"Conçu et développé par {EDITEUR}"),
        ("para", f"{COPYRIGHT} — Tous droits réservés."),
    ],
    "en": [
        ("titre", "Welcome to MVOGMBI_Sync"),
        ("para", "MVOGMBI_Sync connects the Clover point of sale of Marché MVOG-MBI Sherbrooke to the Sage 50 "
                 "accounting software. Every night, the previous day's sales are automatically turned into a "
                 "sales invoice in Sage, with no manual entry."),
        ("sous_titre", "How it works"),
        ("etape", "1. Every night at the chosen time (1 a.m. by default), the application reads in Sage the last "
                  "“Vente YYYY-MM-DD” invoice already imported."),
        ("etape", "2. It retrieves from Clover the sales of each following day, up to yesterday: a missed day is "
                  "caught up automatically."),
        ("etape", "3. It links each Clover item to its Sage item number (item mapping)."),
        ("etape", "4. For the “Vente Hebdomadaire” customer it prepares one invoice per day from Monday to "
                  "Thursday and a single one for Friday, Saturday and Sunday: one line per item, amount = Clover net "
                  "sales, GST + QST (code GQ) for taxable items."),
        ("etape", "5. It imports the invoices into Sage, checks each one, records the Clover deposits on the "
                  "invoices (Sage opened by the robot, off screen) and emails you a report."),
        ("sous_titre", "Safety checks"),
        ("puce", "Never the same invoice twice: a date already in Sage is skipped."),
        ("puce", "Stops at the first day with a problem (unlinked item, missing account…); that day is resumed "
                 "the following night once fixed, with no gap in the invoice sequence."),
        ("puce", "Two different sizes (e.g. 500 g and 1 kg) are never mixed up."),
        ("puce", "Each invoice total equals the day's Clover net sales."),
        ("puce", "Passwords and the Clover token are kept in the Windows vault."),
        ("sous_titre", "Getting started"),
        ("para", "Follow the “Getting started” checklist above: each step turns green once done. The "
                 "“Setup guide” describes every step in detail (Clover, Sage 50, email, automation, item mapping, "
                 "going live); “Help / FAQ” answers common questions."),
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
        ("question", "L'ordinateur doit-il rester allumé la nuit ?"),
        ("reponse", "Oui. À l'heure du traitement, l'ordinateur doit être allumé et votre session Windows ouverte "
                    "(elle peut être verrouillée). Sage 50 peut être fermé : l'application ouvre le fichier "
                    "elle-même. Si l'ordinateur était éteint, les jours manqués sont rattrapés la nuit suivante."),
        ("question", "Que se passe-t-il si un jour est « Bloqué » ?"),
        ("reponse", "Le courriel indique la raison (ex. article Clover non relié à Sage, article Sage sans compte "
                    "de produits). Corrigez-la ; le traitement reprendra automatiquement ce jour-là la nuit "
                    "suivante. Vous pouvez aussi cliquer sur « Lancer maintenant » dans le Tableau de bord."),
        ("question", "Un nouvel article a été créé dans Clover : que faire ?"),
        ("reponse", "S'il porte exactement le même nom qu'un article Sage, il est relié automatiquement. Sinon, "
                    "ouvrez l'onglet « Correspondance des articles », filtre « À traiter », choisissez l'article "
                    "Sage et cliquez sur « Confirmer », puis « Enregistrer les modifications ». S'il n'existe pas "
                    "dans Sage, créez-le d'abord dans Sage (avec son compte de produits)."),
        ("question", "Pourquoi l'application refuse-t-elle de relier 500 g et 1 kg ?"),
        ("reponse", "Deux formats différents sont deux articles différents : les relier fausserait l'inventaire. "
                    "Créez dans Sage un article par format."),
        ("question", "« Article Sage sans compte de produits » : comment corriger ?"),
        ("reponse", "Dans Sage, ouvrez l'article, onglet « Associé », et choisissez le compte de produits 40xx qui "
                    "correspond au compte d'actif 15xx (ex. 1514 Stock - Épices → 4014 Produit des Ventes - Épices)."),
        ("question", "Où sont mes mots de passe ?"),
        ("reponse", "Dans le coffre-fort de Windows (Gestionnaire d'identification), jamais dans un fichier. Pour "
                    "les changer, tapez le nouveau mot de passe dans l'onglet concerné puis « Enregistrer la "
                    "configuration ». « •••• » signifie qu'un mot de passe est déjà enregistré."),
        ("question", "Mon jeton Clover a changé ou a expiré."),
        ("reponse", "Créez un nouveau jeton dans Clover (Compte et configuration > Jetons API, droits en lecture), "
                    "collez-le dans l'onglet Clover, enregistrez, puis « Tester la connexion à Clover »."),
        ("question", "Je ne reçois pas les courriels."),
        ("reponse", "Vérifiez l'onglet Courriel et cliquez sur « Envoyer un courriel de test ». Avec Gmail ou "
                    "Outlook, un « mot de passe d'application » est souvent nécessaire. Regardez aussi le dossier "
                    "des courriels indésirables."),
        ("question", "Comment rattraper une période ancienne (plusieurs mois) ?"),
        ("reponse", "Réglez le « Premier jour à importer » dans l'onglet Sage 50 si Sage ne contient encore aucune "
                    "facture journalière, puis lancez le traitement : il importe les factures jusqu'à hier (une par jour, une par fin de semaine)."),
        ("question", "Les taxes de Sage diffèrent de quelques cents de celles de Clover."),
        ("reponse", "C'est normal : Clover arrondit les taxes commande par commande, Sage les calcule sur la "
                    "facture. Le montant des ventes (hors taxes) est, lui, identique au cent près."),
        ("question", "Où trouver les journaux ?"),
        ("reponse", "Bouton « Dossier des données » du Tableau de bord : journal_automatique.log (chaque "
                    "traitement), journal_imports.csv (chaque facture), sauvegardes de la correspondance."),
        ("question", "« Sage refuse l'utilisateur mvogmbi_sync » au test de Sage."),
        ("reponse", "Le mot de passe de lecture enregistré n'est pas celui de l'utilisateur dans CE fichier "
                    "d'entreprise (chaque fichier, et chaque copie, a ses propres utilisateurs). Ouvrez le fichier "
                    "dans Sage avec sysadmin, Configuration > Définir les utilisateurs, vérifiez mvogmbi_sync et son "
                    "mot de passe, puis retapez le même mot de passe dans l'onglet Sage 50."),
        ("question", "« 535 Incorrect authentication data » au courriel de test."),
        ("reponse", "Le serveur de courriel refuse l'utilisateur ou le mot de passe. L'utilisateur est en général "
                    "l'adresse complète (ex. notification@marchemvogmbi.com). Vérifiez le mot de passe en ouvrant le "
                    "webmail ; après plusieurs refus, le serveur peut faire patienter quelques minutes (« timed out »)."),
        ("question", "Après une réinstallation, tous les articles sont « à confirmer »."),
        ("reponse", "Le dossier de données de la nouvelle installation est vide. Page Automatisation > « Reprendre "
                    "une configuration existante… », choisissez l'ancien dossier : la correspondance validée, le "
                    "journal des imports et la configuration sont recopiés."),
        ("question", "Faut-il laisser la session Windows ouverte la nuit ?"),
        ("reponse", "Elle doit être ouverte (vous connecté), mais elle peut être verrouillée : le robot travaille sur "
                    "un bureau Windows caché. Sage doit être fermé à l'heure du traitement (l'import exige le mode "
                    "mono-utilisateur)."),
        ("question", "Une fenêtre « Sage 50 - Password » ou « Import Summary » s'affiche-t-elle ?"),
        ("reponse", "Non : l'application pilote l'outil d'import de Sage de façon invisible. Si vous lancez "
                    "vous-même un fichier .IMP (double-clic), ses fenêtres apparaissent normalement : elles ne "
                    "viennent pas de MVOGMBI_Sync."),
        ("question", "Pourquoi le dépôt ne couvre-t-il pas toute la facture ?"),
        ("reponse", "Le dépôt Clover ne contient que les ventes par carte (crédit et débit). La part payée en "
                    "espèces reste due sur la facture jusqu'à son propre encaissement."),
        ("question", "Comment désinstaller ?"),
        ("reponse", "Paramètres Windows > Applications > MVOGMBI_Sync > Désinstaller. La tâche planifiée est "
                    "retirée ; vos données et votre configuration restent dans le dossier d'installation."),
    ],
    "en": [
        ("titre", "Help / Frequently asked questions"),
        ("question", "Must the computer stay on at night?"),
        ("reponse", "Yes. At run time the computer must be on and your Windows session open (it may be locked). "
                    "Sage 50 may be closed: the application opens the file itself. If the computer was off, missed "
                    "days are caught up the following night."),
        ("question", "What happens if a day is “Blocked”?"),
        ("reponse", "The email gives the reason (e.g. Clover item not linked to Sage, Sage item without a revenue "
                    "account). Fix it; the run will resume that day automatically the following night. You can "
                    "also click “Run now” in the Dashboard."),
        ("question", "A new item was created in Clover: what should I do?"),
        ("reponse", "If it has exactly the same name as a Sage item, it is linked automatically. Otherwise open the "
                    "“Item mapping” tab, filter “To handle”, choose the Sage item and click “Confirm”, then “Save "
                    "changes”. If it does not exist in Sage, create it in Sage first (with its revenue account)."),
        ("question", "Why does the application refuse to link 500 g and 1 kg?"),
        ("reponse", "Two different sizes are two different items: linking them would distort the inventory. "
                    "Create one Sage item per size."),
        ("question", "“Sage item without a revenue account”: how do I fix it?"),
        ("reponse", "In Sage, open the item, “Linked” tab, and choose the 40xx revenue account matching the 15xx "
                    "asset account (e.g. 1514 Stock - Spices → 4014 Sales - Spices)."),
        ("question", "Where are my passwords?"),
        ("reponse", "In the Windows vault (Credential Manager), never in a file. To change them, type the new "
                    "password in the relevant tab then “Save configuration”. “••••” means a password is already "
                    "saved."),
        ("question", "My Clover token changed or expired."),
        ("reponse", "Create a new token in Clover (Account & Setup > API Tokens, read permissions), paste it in the "
                    "Clover tab, save, then “Test the Clover connection”."),
        ("question", "I don't receive the emails."),
        ("reponse", "Check the Email tab and click “Send a test email”. With Gmail or Outlook, an “app password” is "
                    "often required. Also check the junk folder."),
        ("question", "How do I catch up an old period (several months)?"),
        ("reponse", "Set the “First day to import” in the Sage 50 tab if Sage does not yet contain any daily "
                    "invoice, then start the run: it imports the invoices up to yesterday (one per day, one per weekend)."),
        ("question", "Sage taxes differ by a few cents from Clover's."),
        ("reponse", "This is normal: Clover rounds taxes order by order, Sage computes them on the invoice. The "
                    "sales amount (before taxes) is identical to the cent."),
        ("question", "Where are the logs?"),
        ("reponse", "“Data folder” button in the Dashboard: journal_automatique.log (each run), journal_imports.csv "
                    "(each invoice), mapping backups."),
        ("question", "“Sage rejects the mvogmbi_sync user” when testing Sage."),
        ("reponse", "The saved read password is not the user's password in THIS company file (each file, and each "
                    "copy, has its own users). Open the file in Sage as sysadmin, Setup > Set Up Users, check "
                    "mvogmbi_sync and its password, then type the same password in the Sage 50 tab."),
        ("question", "“535 Incorrect authentication data” with the test email."),
        ("reponse", "The mail server rejects the user or password. The user is usually the full address (e.g. "
                    "notification@marchemvogmbi.com). Check the password by opening the webmail; after several "
                    "rejections the server may make you wait a few minutes (“timed out”)."),
        ("question", "After a reinstall, every item is “to confirm”."),
        ("reponse", "The new installation's data folder is empty. Automation page > “Import an existing "
                    "configuration…”, choose the former folder: the validated mapping, the import log and the "
                    "configuration are copied."),
        ("question", "Must the Windows session stay open at night?"),
        ("reponse", "It must be open (you signed in), but it may be locked: the robot works on a hidden Windows "
                    "desktop. Sage must be closed at run time (the import requires single-user mode)."),
        ("question", "Does a “Sage 50 - Password” or “Import Summary” window appear?"),
        ("reponse", "No: the application drives Sage's import tool invisibly. If you open an .IMP file yourself "
                    "(double-click), its windows appear normally: they do not come from MVOGMBI_Sync."),
        ("question", "Why does the deposit not cover the whole invoice?"),
        ("reponse", "The Clover deposit only contains card sales (credit and debit). The part paid in cash stays "
                    "due on the invoice until it is received separately."),
        ("question", "How do I uninstall?"),
        ("reponse", "Windows Settings > Apps > MVOGMBI_Sync > Uninstall. The scheduled task is removed; your data "
                    "and configuration stay in the installation folder."),
    ],
}

GUIDE = {
    "fr": [
        ("titre", "Guide de configuration"),
        ("para", "Ce guide décrit, étape par étape, la mise en service complète de MVOGMBI_Sync : de la première "
                 "installation jusqu'à l'import automatique de chaque nuit dans le vrai fichier d'entreprise."),
        ("sous_titre", "Avant de commencer"),
        ("puce", "Un ordinateur Windows qui reste allumé la nuit, avec Sage 50 Comptabilité 2026 installé."),
        ("puce", "L'accès administrateur au compte Clover du marché."),
        ("puce", "Le mot de passe de l'utilisateur sysadmin de Sage."),
        ("puce", "Une adresse courriel d'envoi (ex. notification@marchemvogmbi.com) et son mot de passe."),
        ("note", "Conseil : faites tous les essais sur une COPIE du fichier d'entreprise (Sage : Fichier > "
                 "Enregistrer une copie). Le vrai fichier n'est choisi qu'à l'étape « Mise en production »."),

        ("sous_titre", "Étape 1 — Clover"),
        ("etape", "1. Connectez-vous au tableau de bord Clover (www.clover.com). L'identifiant marchand (13 "
                  "caractères) est dans l'adresse de la page, après « /m/ »."),
        ("etape", "2. Compte et configuration > Jetons API > Créer un jeton. Donnez-lui un nom (ex. MVOGMBI_Sync) et "
                  "les droits en LECTURE : Commandes, Inventaire, Paiements, Marchand."),
        ("etape", "3. Dans l'onglet « 1. Clover », collez l'identifiant marchand et le jeton, puis cliquez sur "
                  "« Tester la connexion à Clover » : le nom du marché doit s'afficher."),

        ("sous_titre", "Étape 2 — Sage 50"),
        ("etape", "1. Utilisateur de lecture. Ouvrez le fichier dans Sage avec sysadmin : Configuration > Définir "
                  "les utilisateurs > Ajouter. Nom : mvogmbi_sync, avec un mot de passe. Droits : « Vue » sur "
                  "Stocks & Services et sur Clients & Ventes ; « Droits d'accès aux produits tiers » : "
                  "Consultation seule."),
        ("etape", "2. Fiche du client « Vente Hebdomadaire » : onglet Importer/Exporter, cochez « Ce client utilise "
                  "mes n° d'articles »."),
        ("etape", "3. Comptes des articles : chaque article doit avoir un compte de produits. Règle du marché : "
                  "compte d'actif 15xx → produits 40xx et coût des marchandises 50xx (ex. 1514 → 4014 / 5014)."),
        ("etape", "4. Dans l'onglet « 2. Sage 50 » : choisissez le fichier d'entreprise (.SAI), l'utilisateur "
                  "mvogmbi_sync et son mot de passe, puis le mot de passe de sysadmin (demandé par l'outil d'import)."),
        ("etape", "5. « Premier jour à importer » : utilisé seulement si Sage ne contient encore aucune facture "
                  "« Vente AAAA-MM-JJ »."),
        ("etape", "6. Fermez Sage et cliquez sur « Tester l'accès à Sage » : le nombre d'articles, la dernière "
                  "facture et l'état du client s'affichent. Aucune fenêtre de Sage n'apparaît."),
        ("note", "Chaque fichier d'entreprise (et chaque copie) a ses propres utilisateurs : l'utilisateur "
                 "mvogmbi_sync doit exister, avec le même mot de passe, dans le fichier choisi."),

        ("sous_titre", "Étape 3 — Courriel"),
        ("para", "Le compte rendu de chaque nuit (factures importées, jours bloqués, raisons) est envoyé par courriel."),
        ("puce", "Hébergement cPanel (ex. marchemvogmbi.com) : serveur mail.marchemvogmbi.com, port 465, sécurité "
                 "ssl ; utilisateur = adresse complète."),
        ("puce", "Gmail : smtp.gmail.com, port 587, starttls ; mot de passe d'application (Compte Google > "
                 "Sécurité > Mots de passe des applications)."),
        ("puce", "Outlook / Microsoft 365 : smtp.office365.com, port 587, starttls."),
        ("etape", "Renseignez l'expéditeur, le ou les destinataires et, au besoin, d'« Autres destinataires » (en copie), "
                  "séparés par des virgules ; enregistrez, puis « Envoyer un courriel de test »."),

        ("sous_titre", "Étape 4 — Automatisation"),
        ("etape", "1. Choisissez l'heure du traitement (1 h par défaut) et cliquez sur « Installer la tâche "
                  "planifiée »."),
        ("etape", "2. Paramètres Windows > Système > Alimentation : mise en veille « Jamais » sur secteur. La "
                  "session Windows doit rester ouverte (elle peut être verrouillée)."),
        ("etape", "3. « État de la tâche » confirme l'installation et la prochaine exécution."),

        ("sous_titre", "Étape 5 — Correspondance des articles"),
        ("para", "Chaque article Clover doit être relié à un numéro d'article Sage. La page « Correspondance » "
                 "affiche les statuts :"),
        ("puce", "Automatique : même nom ou même code-barres dans Sage, relié sans intervention."),
        ("puce", "Confirmé : relié par vous ; conservé à chaque mise à jour."),
        ("puce", "À confirmer : une proposition existe ; vérifiez-la puis « Accepter la proposition »."),
        ("puce", "À créer dans Sage : aucun article Sage au bon format ; créez-le dans Sage, puis « Mettre à jour "
                 "depuis Clover et Sage »."),
        ("etape", "Pour relier : sélectionnez l'article, cherchez l'article Sage, « Confirmer l'article choisi », "
                  "puis « Enregistrer les modifications »."),
        ("note", "Règle du marché : deux formats différents (500 g / 1 kg, 6-36 / 7-36) sont deux articles "
                 "différents ; l'application refuse de les relier."),

        ("sous_titre", "Étape 6 — Premier traitement"),
        ("etape", "1. Tableau de bord > « Simulation (sans import) » : les factures sont préparées mais pas "
                  "importées ; lisez les points à corriger."),
        ("etape", "2. Corrigez-les (articles à relier, comptes manquants), puis « Lancer maintenant »."),
        ("etape", "3. Dans Sage, ouvrez une facture « Vente AAAA-MM-JJ » du client « Vente Hebdomadaire » et "
                  "comparez son total aux ventes nettes du jour dans Clover."),

        ("sous_titre", "Mise en production (vrai fichier d'entreprise)"),
        ("etape", "1. Dans le vrai fichier : créez l'utilisateur mvogmbi_sync, cochez la case du client "
                  "« Vente Hebdomadaire » et vérifiez les comptes des articles (étape 2)."),
        ("etape", "2. Onglet « 2. Sage 50 » : choisissez le vrai fichier .SAI, puis « Tester l'accès à Sage »."),
        ("etape", "3. Vérifiez le « Premier jour à importer » et faites une simulation avant la première nuit."),

        ("sous_titre", "Encaissements des dépôts Clover"),
        ("para", "Clover dépose dans le compte Desjardins (1055) les ventes encaissées moins les espèces : c'est "
                 "le lot de cartes que Clover ferme chaque soir. Ventes du lundi au jeudi : déposées le lendemain ; "
                 "ventes du vendredi, samedi et dimanche : déposées ensemble le lundi."),
        ("etape", "1. Page « 7. Encaissements » : choisissez la période de ventes, puis « Calculer les dépôts »."),
        ("etape", "2. Pour chaque dépôt « À saisir dans Sage », le cadre du bas indique quoi saisir : dans Sage, "
                  "Encaissements, Payé par « Comptant », Reçu de « Vente Hebdomadaire », Dépôt 1055, date du dépôt, "
                  "montant reçu sur chaque facture, puis « Traiter »."),
        ("etape", "3. Recalculez : le dépôt passe à « Appliqué ». Le solde restant sur la facture correspond aux "
                  "ventes en espèces."),
        ("etape", "Automatique : chaque nuit, après l'import des factures, le robot ouvre Sage sur un bureau "
                  "Windows caché (rien à l'écran, même session verrouillée), encaisse chaque dépôt, vérifie le total "
                  "avant « Traiter », contrôle chaque encaissement dans la base, puis referme Sage. Le bouton "
                  "« Encaisser dans Sage » fait la même chose à la demande (Sage fermé)."),
        ("puce", "Réglage : page Sage 50, « Encaisser à partir des ventes du » ; les dépôts des ventes antérieures "
                 "ne sont jamais touchés. Un dépôt supérieur au solde dû de la facture n'est jamais saisi."),
        ("note", "Sage ne permet pas d'importer un encaissement : l'application calcule les montants, les saisit "
                 "par robot ou vous guide, puis vérifie le résultat. Un jour férié peut décaler un dépôt d'un jour."),

        ("sous_titre", "Routine quotidienne"),
        ("puce", "Le matin, lisez le courriel : « succès » ou la liste des points à corriger."),
        ("puce", "Un jour bloqué est repris automatiquement la nuit suivante, une fois corrigé."),
        ("puce", "Les factures sont en « Payer plus tard » : page « 7. Encaissements » pour y appliquer les dépôts."),

        ("sous_titre", "Règles de facturation"),
        ("puce", "Client « Vente Hebdomadaire » : une facture par jour du lundi au jeudi (« Vente AAAA-MM-JJ », "
                 "datée du jour des ventes) et une seule du vendredi au dimanche (« Vente AAAA-MM-JJ/JJ », datée du "
                 "dimanche), encaissée d'un coup par le dépôt du lundi."),
        ("puce", "Une ligne par article : montant = ventes nettes Clover (après rabais et remboursements) ; prix "
                 "unitaire = montant / quantité."),
        ("puce", "Articles taxés dans Clover : code de taxe GQ (TPS 5 % + TVQ 9,975 %)."),
        ("puce", "Une vente est datée de son premier paiement réussi."),

        ("sous_titre", "Fichiers et sauvegarde"),
        ("puce", "Dossier des données (bouton du Tableau de bord) : correspondance_articles.xlsx, "
                 "journal_imports.csv, journal_automatique.log et sauvegardes de la correspondance."),
        ("puce", "Sauvegardez ce dossier régulièrement : la correspondance validée représente votre travail."),
        ("puce", "Les mots de passe sont dans le coffre-fort de Windows, jamais dans un fichier."),
        ("puce", "Nouvel ordinateur ou réinstallation : Automatisation > « Reprendre une configuration existante… »."),

        ("sous_titre", "Dépannage"),
        ("puce", "« Sage refuse l'utilisateur » : mot de passe différent dans ce fichier d'entreprise (étape 2)."),
        ("puce", "« Article Clover non relié » : page Correspondance (étape 5)."),
        ("puce", "« Article Sage sans compte de produits » : fiche de l'article dans Sage, onglet Associé."),
        ("puce", "« Ce client utilise mes n° articles » non coché : fiche du client, onglet Importer/Exporter."),
        ("puce", "« 535 Incorrect authentication data » : utilisateur ou mot de passe du courriel (étape 3)."),
        ("puce", "Rien la nuit : ordinateur en veille ou session fermée ; « État de la tâche » (étape 4)."),
    ],
    "en": [
        ("titre", "Setup guide"),
        ("para", "This guide describes, step by step, the complete setup of MVOGMBI_Sync: from the first "
                 "installation to the nightly automatic import into the real company file."),
        ("sous_titre", "Before you start"),
        ("puce", "A Windows computer that stays on at night, with Sage 50 Accounting 2026 installed."),
        ("puce", "Administrator access to the market's Clover account."),
        ("puce", "The password of Sage's sysadmin user."),
        ("puce", "A sending email address (e.g. notification@marchemvogmbi.com) and its password."),
        ("note", "Tip: do all your trials on a COPY of the company file (Sage: File > Save a Copy). The real file "
                 "is only chosen at the “Going live” step."),

        ("sous_titre", "Step 1 — Clover"),
        ("etape", "1. Sign in to the Clover dashboard (www.clover.com). The merchant ID (13 characters) is in the "
                  "page address, after “/m/”."),
        ("etape", "2. Account & Setup > API Tokens > Create token. Give it a name (e.g. MVOGMBI_Sync) and READ "
                  "permissions: Orders, Inventory, Payments, Merchant."),
        ("etape", "3. In the “1. Clover” tab, paste the merchant ID and the token, then click “Test the Clover "
                  "connection”: the market's name must appear."),

        ("sous_titre", "Step 2 — Sage 50"),
        ("etape", "1. Read-only user. Open the file in Sage as sysadmin: Setup > Set Up Users > Add. Name: "
                  "mvogmbi_sync, with a password. Rights: “View” on Inventory & Services and on Receivables; "
                  "“Third-party product access rights”: Read only."),
        ("etape", "2. “Vente Hebdomadaire” customer record: Import/Export tab, check “This customer uses my item "
                  "numbers”."),
        ("etape", "3. Item accounts: every item needs a revenue account. Market rule: asset account 15xx → "
                  "revenue 40xx and cost of goods 50xx (e.g. 1514 → 4014 / 5014)."),
        ("etape", "4. In the “2. Sage 50” tab: choose the company file (.SAI), the mvogmbi_sync user and its "
                  "password, then the sysadmin password (asked by the import tool)."),
        ("etape", "5. “First day to import”: only used if Sage does not yet contain any “Vente YYYY-MM-DD” "
                  "invoice."),
        ("etape", "6. Close Sage and click “Test Sage access”: the number of items, the last invoice and the "
                  "customer status appear. No Sage window shows up."),
        ("note", "Each company file (and each copy) has its own users: the mvogmbi_sync user must exist, with the "
                 "same password, in the chosen file."),

        ("sous_titre", "Step 3 — Email"),
        ("para", "The nightly report (imported invoices, blocked days, reasons) is sent by email."),
        ("puce", "cPanel hosting (e.g. marchemvogmbi.com): server mail.marchemvogmbi.com, port 465, security ssl; "
                 "user = full address."),
        ("puce", "Gmail: smtp.gmail.com, port 587, starttls; app password (Google Account > Security > App "
                 "passwords)."),
        ("puce", "Outlook / Microsoft 365: smtp.office365.com, port 587, starttls."),
        ("etape", "Fill in the sender, the recipient(s) and, if needed, “Other recipients” (in copy), "
                  "separated by commas; save, then “Send a test email”."),

        ("sous_titre", "Step 4 — Automation"),
        ("etape", "1. Choose the run time (1 a.m. by default) and click “Install the scheduled task”."),
        ("etape", "2. Windows Settings > System > Power: sleep “Never” when plugged in. The Windows session must "
                  "stay open (it may be locked)."),
        ("etape", "3. “Task status” confirms the installation and the next run."),

        ("sous_titre", "Step 5 — Item mapping"),
        ("para", "Each Clover item must be linked to a Sage item number. The “Item mapping” page shows the "
                 "statuses:"),
        ("puce", "Automatic: same name or same barcode in Sage, linked with no action."),
        ("puce", "Confirmed: linked by you; kept at every update."),
        ("puce", "To confirm: a suggestion exists; check it then “Accept the suggestion”."),
        ("puce", "To create in Sage: no Sage item with the right size; create it in Sage, then “Update from "
                 "Clover and Sage”."),
        ("etape", "To link: select the item, search the Sage item, “Confirm the chosen item”, then “Save "
                  "changes”."),
        ("note", "Market rule: two different sizes (500 g / 1 kg, 6-36 / 7-36) are two different items; the "
                 "application refuses to link them."),

        ("sous_titre", "Step 6 — First run"),
        ("etape", "1. Dashboard > “Simulation (no import)”: invoices are prepared but not imported; read the "
                  "points to fix."),
        ("etape", "2. Fix them (items to link, missing accounts), then “Run now”."),
        ("etape", "3. In Sage, open a “Vente YYYY-MM-DD” invoice of the “Vente Hebdomadaire” customer and compare "
                  "its total with the day's net sales in Clover."),

        ("sous_titre", "Going live (real company file)"),
        ("etape", "1. In the real file: create the mvogmbi_sync user, check the “Vente Hebdomadaire” customer box "
                  "and check the item accounts (step 2)."),
        ("etape", "2. “2. Sage 50” tab: choose the real .SAI file, then “Test Sage access”."),
        ("etape", "3. Check the “First day to import” and run a simulation before the first night."),

        ("sous_titre", "Receipts for Clover deposits"),
        ("para", "Clover deposits into the Desjardins account (1055) the sales collected minus cash: this is the "
                 "card batch Clover closes every evening. Monday to Thursday sales: deposited the next day; Friday, "
                 "Saturday and Sunday sales: deposited together on Monday."),
        ("etape", "1. “7. Receipts” page: choose the sales period, then “Calculate deposits”."),
        ("etape", "2. For each deposit “To enter in Sage”, the bottom panel shows what to enter: in Sage, Receipts, "
                  "Paid by “Cash”, From “Vente Hebdomadaire”, Deposit to 1055, deposit date, amount received on each "
                  "invoice, then “Process”."),
        ("etape", "3. Recalculate: the deposit turns to “Applied”. The balance left on the invoice is the cash "
                  "sales."),
        ("etape", "Automatic: every night, after importing the invoices, the robot opens Sage on a hidden Windows "
                  "desktop (nothing on screen, even with the session locked), records each deposit, checks the total "
                  "before “Process”, verifies each receipt in the database, then closes Sage. The “Record in Sage” "
                  "button does the same on demand (Sage closed)."),
        ("puce", "Setting: Sage 50 page, “Record receipts from sales of”; deposits for earlier sales are never "
                 "touched. A deposit larger than the invoice balance is never entered."),
        ("note", "Sage cannot import a receipt: the application calculates the amounts, enters them with the "
                 "robot or guides you, then checks the result. A public holiday may shift a deposit by one day."),

        ("sous_titre", "Daily routine"),
        ("puce", "In the morning, read the email: “success” or the list of points to fix."),
        ("puce", "A blocked day is resumed automatically the following night, once fixed."),
        ("puce", "Invoices are “Pay later”: “7. Receipts” page to apply the deposits to them."),

        ("sous_titre", "Invoicing rules"),
        ("puce", "Customer “Vente Hebdomadaire”: one invoice per day from Monday to Thursday (“Vente "
                 "YYYY-MM-DD”, dated on the sales day) and a single one from Friday to Sunday (“Vente YYYY-MM-DD/DD”, "
                 "dated on Sunday), paid at once by the Monday deposit."),
        ("puce", "One line per item: amount = Clover net sales (after discounts and refunds); unit price = "
                 "amount / quantity."),
        ("puce", "Items taxed in Clover: tax code GQ (GST 5% + QST 9.975%)."),
        ("puce", "A sale is dated by its first successful payment."),

        ("sous_titre", "Files and backup"),
        ("puce", "Data folder (Dashboard button): correspondance_articles.xlsx, journal_imports.csv, "
                 "journal_automatique.log and mapping backups."),
        ("puce", "Back up this folder regularly: the validated mapping is your work."),
        ("puce", "Passwords are in the Windows vault, never in a file."),
        ("puce", "New computer or reinstall: Automation > “Import an existing configuration…”."),

        ("sous_titre", "Troubleshooting"),
        ("puce", "“Sage rejects the user”: different password in this company file (step 2)."),
        ("puce", "“Clover item not linked”: Item mapping page (step 5)."),
        ("puce", "“Sage item without a revenue account”: item record in Sage, Linked tab."),
        ("puce", "“This customer uses my item numbers” unchecked: customer record, Import/Export tab."),
        ("puce", "“535 Incorrect authentication data”: email user or password (step 3)."),
        ("puce", "Nothing at night: computer asleep or session closed; “Task status” (step 4)."),
    ],
}
