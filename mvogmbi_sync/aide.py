"""Contenu des pages « Accueil / À propos » et « Aide / FAQ », en français et en anglais.

Chaque page est une liste de blocs (type, texte) : titre, sous_titre, para, puce, etape, question, reponse.
"""

from __future__ import annotations

VERSION = "1.2.2"
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
        ("etape", "4. Elle prépare une facture par jour pour le client « Vente Hebdomadaire » : une ligne par "
                  "article, montant = ventes nettes Clover, taxes TPS + TVQ (code GQ) pour les articles taxés."),
        ("etape", "5. Elle importe les factures dans Sage, vérifie chacune d'elles et vous envoie un compte rendu "
                  "par courriel."),
        ("sous_titre", "Contrôles de sécurité"),
        ("puce", "Jamais deux fois la même facture : une date déjà présente dans Sage est ignorée."),
        ("puce", "Arrêt au premier jour qui pose problème (article non relié, compte manquant…) ; ce jour est "
                 "repris la nuit suivante, une fois le problème corrigé, sans trou dans la suite des factures."),
        ("puce", "Deux formats différents (ex. 500 g et 1 kg) ne sont jamais confondus."),
        ("puce", "Le total de chaque facture est égal aux ventes nettes Clover de la journée."),
        ("puce", "Les mots de passe et le jeton Clover sont gardés dans le coffre-fort de Windows."),
        ("sous_titre", "Pour commencer"),
        ("para", "Remplissez les onglets 1 à 4 (Clover, Sage 50, Courriel, Automatisation), testez chaque "
                 "connexion, installez la tâche planifiée, puis suivez les résultats dans le Tableau de bord. "
                 "Consultez l'onglet Aide / FAQ pour les questions courantes."),
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
        ("etape", "4. It prepares one invoice per day for the “Vente Hebdomadaire” customer: one line per item, "
                  "amount = Clover net sales, GST + QST (code GQ) for taxable items."),
        ("etape", "5. It imports the invoices into Sage, checks each one and emails you a report."),
        ("sous_titre", "Safety checks"),
        ("puce", "Never the same invoice twice: a date already in Sage is skipped."),
        ("puce", "Stops at the first day with a problem (unlinked item, missing account…); that day is resumed "
                 "the following night once fixed, with no gap in the invoice sequence."),
        ("puce", "Two different sizes (e.g. 500 g and 1 kg) are never mixed up."),
        ("puce", "Each invoice total equals the day's Clover net sales."),
        ("puce", "Passwords and the Clover token are kept in the Windows vault."),
        ("sous_titre", "Getting started"),
        ("para", "Fill in tabs 1 to 4 (Clover, Sage 50, Email, Automation), test each connection, install the "
                 "scheduled task, then follow the results in the Dashboard. See the Help / FAQ tab for common "
                 "questions."),
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
                    "facture journalière, puis lancez le traitement : il importe une facture par jour jusqu'à hier."),
        ("question", "Les taxes de Sage diffèrent de quelques cents de celles de Clover."),
        ("reponse", "C'est normal : Clover arrondit les taxes commande par commande, Sage les calcule sur la "
                    "facture. Le montant des ventes (hors taxes) est, lui, identique au cent près."),
        ("question", "Où trouver les journaux ?"),
        ("reponse", "Bouton « Dossier des données » du Tableau de bord : journal_automatique.log (chaque "
                    "traitement), journal_imports.csv (chaque facture), sauvegardes de la correspondance."),
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
                    "invoice, then start the run: it imports one invoice per day up to yesterday."),
        ("question", "Sage taxes differ by a few cents from Clover's."),
        ("reponse", "This is normal: Clover rounds taxes order by order, Sage computes them on the invoice. The "
                    "sales amount (before taxes) is identical to the cent."),
        ("question", "Where are the logs?"),
        ("reponse", "“Data folder” button in the Dashboard: journal_automatique.log (each run), journal_imports.csv "
                    "(each invoice), mapping backups."),
        ("question", "How do I uninstall?"),
        ("reponse", "Windows Settings > Apps > MVOGMBI_Sync > Uninstall. The scheduled task is removed; your data "
                    "and configuration stay in the installation folder."),
    ],
}
