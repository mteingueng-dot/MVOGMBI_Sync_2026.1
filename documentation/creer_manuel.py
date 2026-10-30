"""Fabrique le manuel d'utilisation illustré, en français et en anglais : documentation/Manuel_MVOGMBI_Sync.pdf et
documentation/User_Manual_MVOGMBI_Sync.pdf (HTML puis PDF par Microsoft Edge).

Les captures d'écran sont dans documentation/captures/ (français) et documentation/captures/en/ (anglais, sinon
les captures françaises), prises sur une copie des données de l'application. Le mode opératoire, les règles et la
FAQ viennent de mvogmbi_sync/aide.py (mêmes blocs en fr et en en) : le manuel reste identique à l'aide intégrée.

    python documentation/creer_manuel.py [fr|en]      (sans argument : les deux)
"""

from __future__ import annotations

import html
import subprocess
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

ICI = Path(__file__).resolve().parent
RACINE = ICI.parent
sys.path.insert(0, str(RACINE))

from mvogmbi_sync import langues  # noqa: E402
from mvogmbi_sync.aide import COPYRIGHT, EDITEUR, FAQ, GUIDE, VERSION  # noqa: E402

CAPTURES = ICI / "captures"
LOGO = RACINE / "mvogmbi_sync" / "ressources" / "logo.png"
SORTIES = {"fr": "Manuel_MVOGMBI_Sync", "en": "User_Manual_MVOGMBI_Sync"}
EDGE = [Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe")]

e = html.escape
LANGUE = "fr"  # langue du manuel en cours de fabrication


def x(fr: str, en: str) -> str:
    """Texte du manuel dans la langue en cours."""
    return en if LANGUE == "en" else fr


def figure(nom: str, legende: str) -> str:
    for dossier, src in ((CAPTURES / LANGUE, f"captures/{LANGUE}/{nom}.png"), (CAPTURES, f"captures/{nom}.png")):
        if LANGUE != "fr" or dossier == CAPTURES:
            if (dossier / f"{nom}.png").exists():
                return (f"<figure><img src='{src}' alt='{e(legende)}'>"
                        f"<figcaption>{e(legende)}</figcaption></figure>")
    return f"<p class='manque'>[{e(nom)}]</p>"


def blocs(debut: str) -> str:
    """Section de l'aide dont le sous-titre FRANÇAIS commence par `debut`, prise dans la langue en cours (même rang
    de sous-titre : les deux langues ont la même structure de blocs), jusqu'au sous-titre suivant, en HTML."""
    rangs = [i for i, (genre, _) in enumerate(GUIDE["fr"]) if genre == "sous_titre"]
    rang = next(k for k, i in enumerate(rangs) if GUIDE["fr"][i][1].startswith(debut))
    liste = GUIDE[LANGUE]
    cible = [i for i, (genre, _) in enumerate(liste) if genre == "sous_titre"][rang]
    sortie, ouvert = [f"<h3>{e(liste[cible][1])}</h3>"], None
    for genre, texte in liste[cible + 1:]:
        if genre == "sous_titre":
            break
        if genre in ("puce", "etape"):
            balise = "ul" if genre == "puce" else "ol class='etapes'"
            if ouvert != genre:
                if ouvert:
                    sortie.append("</ul>" if ouvert == "puce" else "</ol>")
                sortie.append(f"<{balise}>")
                ouvert = genre
            texte_li = texte.split(". ", 1)[1] if genre == "etape" and texte[:2].strip(". ").isdigit() else texte
            sortie.append(f"<li>{e(texte_li)}</li>")
            continue
        if ouvert:
            sortie.append("</ul>" if ouvert == "puce" else "</ol>")
            ouvert = None
        if genre == "para":
            sortie.append(f"<p>{e(texte)}</p>")
        elif genre == "note":
            sortie.append(f"<div class='note'>💡 {e(texte)}</div>")
    if ouvert:
        sortie.append("</ul>" if ouvert == "puce" else "</ol>")
    return "\n".join(sortie)


def faq() -> str:
    sortie = []
    for genre, texte in FAQ[LANGUE][1:]:
        if genre == "sous_titre":
            sortie.append(f"<h3>{e(texte)}</h3>")
        elif genre == "question":
            sortie.append(f"<p class='question'>{e(texte)}</p>")
        elif genre == "reponse":
            sortie.append(f"<p class='reponse'>{e(texte)}</p>")
    return "\n".join(sortie)


def courriel_exemple() -> str:
    """Compte rendu de nuit fictif, rendu exactement comme le courriel envoyé."""
    from mvogmbi_sync.automatique import IMPORTEE, CompteRendu, EtatJour
    from mvogmbi_sync.courriel import html_compte_rendu

    cr = CompteRendu(fichier="MARCHE.SAI", derniere_avant=date(2026, 10, 21),
                     periode=(date(2026, 10, 22), date(2026, 10, 22)))
    cr.jours = [EtatJour(date(2026, 10, 22), IMPORTEE, "", 143, Decimal("2108.98"), Decimal("55.95"),
                         Decimal("2164.93"))]
    cr.encaissements = [x("Dépôt du 2026-10-23 : 1 842,10 $ au compte 1055 (Vente 2026-10-22)",
                          "Deposit of 2026-10-23: $1,842.10 to account 1055 (Vente 2026-10-22)")]
    cr.paiements = [x("2026-10-22 : 632,36 $ à Transport Exemple, facture 15 (virement CA0000000)",
                      "2026-10-22: $632.36 to Transport Exemple, invoice 15 (transfer CA0000000)")]
    cr.lignes = [x("01:00:19 Lecture de Sage (MARCHE.SAI)…", "01:00:19 Reading Sage (MARCHE.SAI)…"),
                 x("01:00:54 Import de 1 facture(s)…", "01:00:54 Importing 1 invoice(s)…"),
                 x("01:00:56 1 facture(s) importée(s) et vérifiée(s) dans Sage.",
                   "01:00:56 1 invoice(s) imported and verified in Sage."),
                 x("01:02:10 1 dépôt(s) encaissé(s).", "01:02:10 1 deposit(s) recorded."),
                 x("01:03:30 1 paiement(s) fournisseur(s) saisi(s) dans Sage.",
                   "01:03:30 1 supplier payment(s) entered in Sage.")]
    return html_compte_rendu(cr)


STYLE = """
@page { size: Letter; margin: 16mm 15mm 18mm 15mm; }
:root { --vert: #1a9b3c; --vert-fonce: #13772d; --pale: #e8f5ec; --jaune: #f6b81a; --rouge: #d7263d;
        --texte: #1f2d24; --doux: #6b7a70; --bord: #e2e8e4; }
* { box-sizing: border-box; }
body { font-family: 'Segoe UI', Arial, sans-serif; color: var(--texte); font-size: 10.5pt; line-height: 1.5;
       margin: 0; background: #fff; }
.couverture { height: 235mm; display: flex; flex-direction: column; justify-content: center; align-items: center;
              text-align: center; page-break-after: always; border-top: 10px solid var(--vert); }
.couverture img { width: 150px; margin-bottom: 26px; }
.couverture .grand { font-size: 30pt; font-weight: 700; color: var(--vert-fonce); }
.couverture .sous { font-size: 14pt; color: var(--doux); margin-top: 8px; }
.couverture .filet { display: flex; gap: 6px; margin: 22px 0; }
.couverture .filet span { height: 6px; border-radius: 3px; }
.couverture .infos { margin-top: 40px; font-size: 10pt; color: var(--doux); }
h1 { font-size: 20pt; color: var(--vert-fonce); margin: 0 0 4px; page-break-before: always; padding-top: 2px; }
h1 .num { display: inline-block; background: var(--vert); color: #fff; border-radius: 6px; padding: 0 10px;
          margin-right: 10px; font-size: 16pt; }
.filet-titre { display: flex; gap: 5px; margin: 6px 0 16px; }
.filet-titre span { height: 4px; border-radius: 2px; }
h2 { font-size: 13.5pt; color: var(--vert-fonce); margin: 20px 0 6px; }
h3 { font-size: 11.5pt; color: var(--texte); margin: 16px 0 4px; }
p { margin: 6px 0; }
ul, ol { margin: 6px 0 8px; padding-left: 22px; }
li { margin: 3px 0; }
ol.etapes { counter-reset: e; list-style: none; padding-left: 0; }
ol.etapes > li { counter-increment: e; position: relative; padding-left: 34px; margin: 7px 0; }
ol.etapes > li::before { content: counter(e); position: absolute; left: 0; top: 1px; width: 22px; height: 22px;
                         border-radius: 50%; background: var(--vert); color: #fff; font-weight: 600; font-size: 9pt;
                         display: flex; align-items: center; justify-content: center; }
figure { margin: 12px 0 16px; page-break-inside: avoid; }
figure img { width: 100%; border: 1px solid var(--bord); border-radius: 6px; box-shadow: 0 2px 10px rgba(0,0,0,.08); }
figcaption { font-size: 9pt; color: var(--doux); text-align: center; margin-top: 5px; font-style: italic; }
.note { background: #fff8e1; border-left: 4px solid var(--jaune); padding: 8px 12px; border-radius: 4px; margin: 10px 0;
        page-break-inside: avoid; }
.attention { background: #fdecee; border-left: 4px solid var(--rouge); padding: 8px 12px; border-radius: 4px;
             margin: 10px 0; page-break-inside: avoid; }
table.simple { width: 100%; border-collapse: collapse; margin: 8px 0 12px; font-size: 9.5pt; page-break-inside: avoid; }
table.simple th { background: #1f7a3a; color: #fff; text-align: left; padding: 6px 8px; font-weight: 600; }
table.simple td { padding: 6px 8px; border-bottom: 1px solid var(--bord); vertical-align: top; }
table.simple tr:nth-child(even) td { background: #f4f8f5; }
.pastille { display: inline-block; padding: 1px 8px; border-radius: 10px; font-size: 9pt; font-weight: 600; }
.p-jaune { background: #fff4d6; } .p-bleu { background: #eaf2fb; } .p-vert { background: #e6f4ea; }
.p-rouge { background: #fde2e4; } .p-gris { background: #eef1ef; color: #6b7a70; }
.toc { page-break-after: always; }
.toc ol { list-style: none; padding: 0; }
.toc li { display: flex; border-bottom: 1px dotted #c9d3cc; padding: 6px 0; font-size: 11pt; }
.toc li span { color: var(--vert); font-weight: 700; width: 34px; }
.courriel { border: 1px solid var(--bord); border-radius: 6px; padding: 14px 18px; background: #fff;
            box-shadow: 0 2px 10px rgba(0,0,0,.06); page-break-inside: avoid; font-size: 9.5pt; }
.courriel h2 { font-size: 13pt; margin-top: 0; }
.question { font-weight: 600; margin: 12px 0 2px; color: var(--vert-fonce); page-break-after: avoid; }
.reponse { margin: 0 0 8px; }
.pied { text-align: center; color: var(--doux); font-size: 9pt; margin-top: 30px; }
.manque { color: var(--rouge); }
"""

# chapitres : (clé, titre fr, titre en, pages concernées) ; pages = index des pages de interface.py (le manuel du
# profil ne garde que les chapitres dont une page est permise ; aucune page = chapitre pour tous)
CHAPITRES = [
    ("presentation", "Présentation", "Overview", ()),
    ("installation", "Installation et premier lancement", "Installation and first start", ()),
    ("interface", "Découvrir l'interface", "Getting to know the interface", ()),
    ("configuration", "Configuration (Administration)", "Setup (Administration)", (1, 2, 3, 4)),
    ("correspondance", "Correspondance des articles (Articles > Correspondance)", "Item mapping (Items > Mapping)", (5,)),
    ("tableau", "Tableau de bord et traitement de nuit", "Dashboard and nightly run", (6,)),
    ("encaissements", "Encaissements des dépôts Clover (Comptabilité > Encaissements)", "Receipts for Clover deposits (Accounting > Receipts)", (7,)),
    ("fournisseurs", "Factures fournisseurs (Fournisseur > Factures fournisseurs)", "Supplier invoices (Supplier > Supplier invoices)", (8,)),
    ("paiements", "Paiements fournisseurs (Comptabilité > Paiements fournisseur)", "Supplier payments (Accounting > Supplier payments)", (9,)),
    ("rapprochement", "Rapprochement bancaire (Comptabilité > Rapprochement)", "Bank reconciliation (Accounting > Reconciliation)", (10,)),
    ("rapports", "Rapports et recherches (État)", "Reports and searches (Reports)", (11,)),
    ("gestion", "Gestion des ventes, des achats et des stocks", "Sales, purchasing and stock management", (5, 7, 8)),
    ("commercial", "Gestion commerciale (bons de commande, prix et marges)", "Business management (purchase orders, prices and margins)", (5, 8)),
    ("comptabilite", "Comptabilité (âge des comptes, taxes, trésorerie, clôture)", "Accounting (aging, taxes, cash flow, month-end)", (10,)),
    ("paie", "Paie (pointage, feuilles de temps, retenues à la source)", "Payroll (time clock, timesheets, source deductions)", (9, 10)),
    ("paie2", "Paie dans Sage, congés, fin d'emploi et main-d'œuvre", "Payroll in Sage, leave, end of employment and labour cost", (9, 10)),
    ("tresorerie", "Caisse, dépenses, remises et budget", "Cash, expenses, remittances and budget", (9, 10)),
    ("magasin", "Pertes, retours, étiquettes, promotions et inventaire tournant", "Losses, returns, labels, promotions and cycle count", (5, 8)),
    ("securite", "Sauvegarde, journal des opérations et tableau du gérant", "Backup, operations log and manager dashboard", (4, 14)),
    ("mode", "Mode opératoire", "Operating procedure", ()),
    ("regles", "Règles de gestion", "Business rules", ()),
    ("faq", "Questions fréquentes et dépannage", "Frequently asked questions and troubleshooting", ()),
]


def titre(cle: str) -> str:
    numero = next(i for i, c in enumerate(CHAPITRES, 1) if c[0] == cle)
    _cle, fr, en, _pages = CHAPITRES[numero - 1]
    return (f"<h1 id='{cle}'><span class='num'>{numero}</span>{e(x(fr, en))}</h1>"
            "<div class='filet-titre'><span style='width:60px;background:#f6b81a'></span>"
            "<span style='width:18px;background:#d7263d'></span></div>")


def contenu() -> str:
    parties = []
    # ------------------------------------------------------------------ couverture et sommaire
    parties.append(f"""
<div class="couverture">
  <img src="../mvogmbi_sync/ressources/logo.png" alt="Logo">
  <div class="grand">{x("Manuel d'utilisation", "User manual")}</div>
  <div class="sous">MVOGMBI_Sync — Clover → Sage 50</div>
  <div class="filet"><span style="width:90px;background:#1a9b3c"></span><span style="width:60px;background:#f6b81a">
  </span><span style="width:24px;background:#d7263d"></span></div>
  <div class="sous" style="font-size:12pt">{x("Marché MVOG-MBI Sherbrooke — épicerie africaine &amp; caribéenne",
                                               "Marché MVOG-MBI Sherbrooke — African &amp; Caribbean grocery")}</div>
  <div class="infos">Version {VERSION} — {date.today():%Y-%m-%d}<br>{x("Conçu et développé par", "Designed and developed by")}
  {e(EDITEUR)}<br>{e(COPYRIGHT)} — {x("Tous droits réservés.", "All rights reserved.")}</div>
</div>
<div class="toc"><h2 style="font-size:18pt">{x("Sommaire", "Contents")}</h2><ol>
{''.join(f"<li data-pages='{','.join(map(str, pages))}'><span>{i}</span>{e(x(fr, en))}</li>"
         for i, (_, fr, en, pages) in enumerate(CHAPITRES, 1))}
</ol></div>""")

    # ------------------------------------------------------------------ 1. Présentation
    parties.append(titre("presentation") + x("""
<p>MVOGMBI_Sync relie le point de vente <b>Clover</b> du Marché MVOG-MBI Sherbrooke à la comptabilité
<b>Sage 50 Comptabilité, Édition canadienne</b>. L'application travaille seule chaque nuit et vous envoie un compte
rendu par courriel le matin. Elle couvre cinq domaines :</p>
<table class="simple">
<tr><th>Domaine</th><th>Ce que fait l'application</th><th>Page</th></tr>
<tr><td><b>Ventes</b></td><td>Les ventes Clover deviennent une facture de vente dans Sage (client « Vente
Hebdomadaire »), une ligne par article : une facture par jour du lundi au jeudi, une seule du vendredi au
dimanche.</td><td>5, 6</td></tr>
<tr><td><b>Encaissements</b></td><td>Les dépôts Clover, virements Interac reçus et dépôts d'espèces arrivés au compte
Desjardins (1055) sont appliqués sur ces factures.</td><td>7</td></tr>
<tr><td><b>Factures fournisseurs</b></td><td>Les factures reçues (PDF, scans, photos) sont lues, reliées aux articles
Sage et importées comme factures d'achat.</td><td>8</td></tr>
<tr><td><b>Paiements fournisseurs</b></td><td>Les avis de virement Interac reçus par courriel sont reliés aux factures
et saisis comme paiements dans Sage.</td><td>9</td></tr>
<tr><td><b>Rapprochement bancaire</b></td><td>Les relevés Desjardins sont rapprochés du compte 1055 ; ce qui manque
est saisi dans Sage après votre confirmation.</td><td>10</td></tr>
</table>
<h2>Le traitement de chaque nuit</h2>
<ol class="etapes">
<li>À 1 h (heure réglable), l'application lit dans Sage la dernière facture « Vente AAAA-MM-JJ ».</li>
<li>Elle récupère dans Clover les ventes de chaque jour suivant, jusqu'à hier.</li>
<li>Elle prépare et importe les factures, puis vérifie chacune d'elles dans Sage.</li>
<li>Elle encaisse les dépôts et saisit les paiements fournisseurs que vous avez confirmés.</li>
<li>Elle vous envoie un compte rendu par courriel.</li>
</ol>
<div class="note">💡 Sage doit être <b>fermé</b> pendant la nuit : l'application l'ouvre elle-même, sans rien
afficher, puis le referme. L'ordinateur doit rester allumé et la session Windows ouverte (elle peut être
verrouillée).</div>
<h2>Contrôles de sécurité</h2>
<ul>
<li>Jamais deux fois la même facture ou le même paiement : ce qui existe déjà dans Sage est ignoré.</li>
<li>Un jour qui pose problème est bloqué seul (toute la fin de semaine pour le vendredi, le samedi ou le dimanche),
avec son encaissement ; les autres jours continuent et le jour bloqué est repris en priorité la nuit suivante.</li>
<li>Deux formats différents (500 g et 1 kg) ne sont jamais confondus.</li>
<li>Rien n'est saisi sans contrôle du total, et chaque saisie est vérifiée ensuite dans Sage.</li>
<li>Les mots de passe sont gardés dans le coffre-fort de Windows, jamais dans un fichier.</li>
</ul>""", """
<p>MVOGMBI_Sync connects the <b>Clover</b> point of sale of Marché MVOG-MBI Sherbrooke to the
<b>Sage 50 Accounting, Canadian Edition</b> books. The application works on its own every night and emails you a
report in the morning. It covers five areas:</p>
<table class="simple">
<tr><th>Area</th><th>What the application does</th><th>Page</th></tr>
<tr><td><b>Sales</b></td><td>Clover sales become a sales invoice in Sage (customer “Vente Hebdomadaire”), one line
per item: one invoice per day from Monday to Thursday, a single one from Friday to Sunday.</td><td>5, 6</td></tr>
<tr><td><b>Receipts</b></td><td>Clover deposits, Interac transfers received and cash deposits arriving in the
Desjardins account (1055) are applied to these invoices.</td><td>7</td></tr>
<tr><td><b>Supplier invoices</b></td><td>Invoices received (PDF, scans, photos) are read, linked to the Sage items and
imported as purchase invoices.</td><td>8</td></tr>
<tr><td><b>Supplier payments</b></td><td>Interac transfer notices received by email are linked to the invoices and
entered as payments in Sage.</td><td>9</td></tr>
<tr><td><b>Bank reconciliation</b></td><td>Desjardins statements are reconciled with account 1055; what is missing is
entered in Sage once you confirm it.</td><td>10</td></tr>
</table>
<h2>The nightly run</h2>
<ol class="etapes">
<li>At 1 a.m. (adjustable), the application reads the last “Vente YYYY-MM-DD” invoice in Sage.</li>
<li>It fetches from Clover the sales of each following day, up to yesterday.</li>
<li>It prepares and imports the invoices, then checks each one in Sage.</li>
<li>It records the deposits and enters the supplier payments you have confirmed.</li>
<li>It emails you a report.</li>
</ol>
<div class="note">💡 Sage must be <b>closed</b> at night: the application opens it by itself, without showing
anything, then closes it. The computer must stay on and the Windows session open (it may be locked).</div>
<h2>Safety checks</h2>
<ul>
<li>Never the same invoice or payment twice: what already exists in Sage is skipped.</li>
<li>A day with a problem is blocked alone (the whole weekend for Friday, Saturday or Sunday), with its receipt;
the other days continue and the blocked day is retried first the next night.</li>
<li>Two different sizes (500 g and 1 kg) are never mixed up.</li>
<li>Nothing is entered without checking the total, and every entry is then verified in Sage.</li>
<li>Passwords are kept in the Windows vault, never in a file.</li>
</ul>"""))

    # ------------------------------------------------------------------ 2. Installation
    parties.append(titre("installation") + x("""
<ol class="etapes">
<li>Lancez <b>Installer_MVOGMBI_Sync_x.y.z.exe</b> (aucun droit d'administrateur n'est demandé). Chaque version a son
propre fichier d'installation ; une mise à jour conserve votre configuration et vos données.</li>
<li>Choisissez la langue de l'installation, puis celle de l'application (français ou anglais, modifiable ensuite).</li>
<li>À la dernière page, cochez au besoin « Créer un raccourci sur le Bureau » et « Ouvrir MVOGMBI_Sync ».</li>
<li>L'application s'installe dans <code>%LOCALAPPDATA%\\Programs\\MVOGMBI_Sync</code>. Le menu Démarrer contient
l'application, ce manuel, le journal du traitement et la désinstallation.</li>
</ol>
<div class="note">💡 Nouvel ordinateur ou réinstallation : « Administration > Automatisation », bouton « Reprendre une
configuration existante… », puis choisissez l'ancien dossier : la correspondance validée, les journaux et la
configuration sont recopiés.</div>""", """
<ol class="etapes">
<li>Run <b>Installer_MVOGMBI_Sync_x.y.z.exe</b> (no administrator rights needed). Each version has its own setup
file; an update keeps your configuration and data.</li>
<li>Choose the setup language, then the application language (French or English, can be changed later).</li>
<li>On the last page, tick “Create a desktop shortcut” and “Open MVOGMBI_Sync” if you wish.</li>
<li>The application is installed in <code>%LOCALAPPDATA%\\Programs\\MVOGMBI_Sync</code>. The Start menu holds the
application, this manual, the run log and the uninstaller.</li>
</ol>
<div class="note">💡 New computer or reinstall: “Administration > Automation”, button “Import an existing configuration…”, then
choose the old folder: the validated item mapping, the logs and the configuration are copied over.</div>"""))

    # ------------------------------------------------------------------ 3. Interface
    parties.append(titre("interface") + figure("00_accueil", x("Page d'accueil : liste « Mise en route » et présentation",
                                                     "Home page: “Getting started” list and overview")) + x("""
<ul>
<li><b>Bandeau vert</b> : nom du marché et rôle de l'application.</li>
<li><b>Menu de gauche</b> : les pages de travail, numérotées dans l'ordre de la mise en service. Une coche verte ✔
indique une étape terminée, un point jaune ● une étape à faire.</li>
<li><b>Mise en route</b> : les dix étapes de la mise en service, une par page, avec le nombre d'étapes terminées ;
« Ouvrir » mène directement à la page concernée.</li>
<li><b>Langue / Language</b> : français ou anglais, en bas du menu.</li>
<li><b>Enregistrer la configuration</b> : en bas à droite, à cliquer après toute modification des pages 1 à 4.</li>
<li><b>Exporter</b> : chaque tableau s'exporte en Excel ou en CSV (bouton « ⬇ Exporter » ou clic droit).</li>
</ul>
<h2>Connexion, utilisateurs et accès</h2>
<p>Chacun ouvre l'application avec son <b>nom</b> et son <b>mot de passe</b>. Au tout premier lancement, l'application
demande de créer le compte <b>administrateur</b>. En bas du menu : le nom de la personne connectée, « Changer mon mot de
passe » et « Se déconnecter ».</p>
<table class="simple"><tr><th>Profil</th><th>Pages visibles</th></tr>
<tr><td><b>Administrateur</b></td><td>Toutes, y compris la configuration (pages 1 à 4) et la page « Utilisateurs ».</td></tr>
<tr><td><b>Comptable</b></td><td>Accueil, pages 5 à 10, Guide et FAQ.</td></tr>
<tr><td><b>Employé</b></td><td>Accueil, Tableau de bord, Guide et FAQ.</td></tr></table>
""" + figure("13_utilisateurs", "Page Utilisateurs (administrateur) : comptes, profils et fonctions permises")
                   + """
<p>L'administrateur ajoute les comptes, change leur profil ou leur mot de passe, les désactive, et décide des pages
de chaque profil (une page non cochée disparaît du menu). Il crée aussi d'autres profils (« ➕ »). Il reste toujours au
moins un administrateur actif. Les mots de passe ne sont jamais conservés, seulement une empreinte chiffrée.</p>""", """
<ul>
<li><b>Green banner</b>: market name and role of the application.</li>
<li><b>Left menu</b>: the work pages, numbered in setup order. A green tick ✔ marks a completed step, a yellow dot ●
a step still to do.</li>
<li><b>Getting started</b>: the ten setup steps, one per page, with the number of completed steps; “Open” goes
straight to the page.</li>
<li><b>Langue / Language</b>: French or English, at the bottom of the menu.</li>
<li><b>Save configuration</b>: bottom right, to click after any change on pages 1 to 4.</li>
<li><b>Export</b>: every table can be exported to Excel or CSV (“⬇ Export” button or right-click).</li>
</ul>
<h2>Sign-in, users and access</h2>
<p>Everyone opens the application with their <b>name</b> and <b>password</b>. On the very first start, the
application asks to create the <b>administrator</b> account. At the bottom of the menu: the name of the person signed
in, “Change my password” and “Sign out”.</p>
<table class="simple"><tr><th>Profile</th><th>Visible pages</th></tr>
<tr><td><b>Administrator</b></td><td>All, including setup (pages 1 to 4) and the “Users” page.</td></tr>
<tr><td><b>Accountant</b></td><td>Home, pages 5 to 10, Guide and FAQ.</td></tr>
<tr><td><b>Employee</b></td><td>Home, Dashboard, Guide and FAQ.</td></tr></table>
""" + figure("13_utilisateurs", "Users page (administrator): accounts, profiles and visible pages")
                   + """
<p>The administrator adds accounts, changes their profile or password, disables them, and decides which pages each
profile sees (an unticked page disappears from the menu). They can also create other profiles (“➕”). At least one
active administrator always remains. Passwords are never kept, only an encrypted fingerprint.</p>"""))

    # ------------------------------------------------------------------ 4. Configuration
    parties.append(titre("configuration") + blocs("Avant de commencer") + "<h2>" + x("Administration > Clover",
"Administration > Clover") + "</h2>"
                   + figure("01_clover", x("Administration > Clover : identifiant marchand et jeton API",
                                           "Administration > Clover: merchant ID and API token"))
                   + blocs("Étape 1") + "<h2>Administration > Sage 50</h2>"
                   + figure("02_sage", x("Administration > Sage 50 : fichier d'entreprise, comptes et utilisateurs",
                                         "Administration > Sage 50: company file, accounts and users"))
                   + blocs("Étape 2") + "<h2>" + x("Administration > Courriel",
"Administration > Email") + "</h2>"
                   + figure("03_courriel", x("Administration > Courriel : compte rendu et boîte des avis de paiement",
                                             "Administration > Email: report and payment notice mailbox"))
                   + blocs("Étape 3") + "<h2>" + x("Administration > Automatisation",
"Administration > Automation") + "</h2>"
                   + figure("04_automatisation", x("Administration > Automatisation : tâche planifiée de la nuit",
                                                   "Administration > Automation: nightly scheduled task"))
                   + blocs("Étape 4") + blocs("Mise en production"))

    # ------------------------------------------------------------------ 5. Correspondance
    parties.append(titre("correspondance") + figure("05_correspondance", x("Articles > Correspondance des articles Clover et Sage",
                                                            "Items > Mapping of Clover and Sage items"))
                   + blocs("Étape 5") + x("""
<table class="simple"><tr><th>Statut</th><th>Signification</th><th>Action</th></tr>
<tr><td><span class="pastille p-vert">Confirmé</span></td><td>Relié par vous</td><td>Aucune</td></tr>
<tr><td><span class="pastille p-gris">Automatique</span></td><td>Même nom ou même code-barres</td><td>Aucune</td></tr>
<tr><td><span class="pastille p-jaune">À confirmer</span></td><td>Une proposition existe</td>
<td>Vérifier, puis « Accepter la proposition »</td></tr>
<tr><td><span class="pastille p-rouge">Aucun</span></td><td>Pas d'article Sage au bon format</td>
<td>Créer l'article dans Sage, puis « Mettre à jour depuis Clover et Sage »</td></tr></table>""", """
<table class="simple"><tr><th>Status</th><th>Meaning</th><th>Action</th></tr>
<tr><td><span class="pastille p-vert">Confirmed</span></td><td>Linked by you</td><td>None</td></tr>
<tr><td><span class="pastille p-gris">Automatic</span></td><td>Same name or same barcode</td><td>None</td></tr>
<tr><td><span class="pastille p-jaune">To confirm</span></td><td>A suggestion exists</td>
<td>Check, then “Accept the suggestion”</td></tr>
<tr><td><span class="pastille p-rouge">None</span></td><td>No Sage item of the right size</td>
<td>Create the item in Sage, then “Update from Clover and Sage”</td></tr></table>"""))

    # ------------------------------------------------------------------ 6. Tableau de bord
    parties.append(titre("tableau") + figure("06_tableau_de_bord", x("Vente > Ventes Clover → factures Sage — Tableau de bord : dernier import, tâche, journal",
                                                             "Sales > Clover sales → Sage invoices — Dashboard: last import, task, log"))
                   + x("""
<ul>
<li><b>Dernière facture importée</b>, état de la <b>tâche planifiée</b> et nombre de <b>points à corriger</b>.</li>
<li><b>Lancer maintenant</b> : exécute tout de suite le traitement de la nuit (Sage fermé).</li>
<li><b>Simulation (sans import)</b> : prépare les factures sans rien importer, pour lire les points à corriger.</li>
<li><b>Charger une date ou une période</b> : importe les ventes des jours choisis (jours déjà dans Sage sautés ; une
fin de semaine commence toujours le vendredi).</li>
<li><b>Excel</b> : rapport des ventes ; <b>Dossier des données</b> : journaux, correspondance et sauvegardes.</li>
</ul>""", """
<ul>
<li><b>Last imported invoice</b>, status of the <b>scheduled task</b> and number of <b>issues to fix</b>.</li>
<li><b>Run now</b>: runs the nightly processing right away (Sage closed).</li>
<li><b>Simulation (no import)</b>: prepares the invoices without importing anything, to read the issues to fix.</li>
<li><b>Load a date or a period</b>: imports the sales of the chosen days (days already in Sage are skipped; a
weekend always starts on Friday).</li>
<li><b>Excel</b>: sales report; <b>Data folder</b>: logs, item mapping and backups.</li>
</ul>""") + blocs("Étape 6") + "<h2>" + x("Le courriel du matin", "The morning email") + "</h2><p>"
                   + x("Après chaque traitement, un compte rendu est envoyé aux destinataires de la page Courriel. "
                       "Exemple (données fictives) :",
                       "After each run, a report is sent to the recipients of the Email page. Example (fictitious "
                       "data):")
                   + "</p><div class='courriel'>" + courriel_exemple() + "</div>")

    # ------------------------------------------------------------------ 7. Encaissements
    parties.append(titre("encaissements") + figure("07_encaissements", x("Comptabilité > Encaissements des dépôts Clover",
                                                           "Accounting > Receipts for Clover deposits"))
                   + blocs("Encaissements des dépôts Clover") + x("""
<table class="simple"><tr><th>État</th><th>Signification</th></tr>
<tr><td><span class="pastille p-vert">Appliqué</span></td><td>Le dépôt est encaissé sur la facture dans Sage.</td></tr>
<tr><td><span class="pastille p-jaune">À saisir dans Sage</span></td><td>Sera encaissé la nuit, ou avec « Encaisser dans
Sage ».</td></tr>
<tr><td><span class="pastille p-rouge">Écart</span></td><td>Un montant différent est déjà saisi dans Sage : à vérifier.
</td></tr>
<tr><td><span class="pastille p-rouge">Espèces à répartir à la main</span></td><td>Virement Interac ou dépôt d'espèces
qui ne trouve pas sa facture : à encaisser vous-même dans Sage.</td></tr>
<tr><td><span class="pastille p-gris">Sans facture / À venir</span></td><td>La facture n'est pas encore dans Sage, ou le
dépôt n'est pas encore arrivé.</td></tr></table>""", """
<table class="simple"><tr><th>Status</th><th>Meaning</th></tr>
<tr><td><span class="pastille p-vert">Applied</span></td><td>The deposit is recorded on the invoice in Sage.</td></tr>
<tr><td><span class="pastille p-jaune">To enter in Sage</span></td><td>Will be recorded at night, or with “Record in
Sage”.</td></tr>
<tr><td><span class="pastille p-rouge">Difference</span></td><td>A different amount is already entered in Sage: to
check.</td></tr>
<tr><td><span class="pastille p-rouge">Cash to allocate manually</span></td><td>Interac transfer or cash deposit that
finds no invoice: record it yourself in Sage.</td></tr>
<tr><td><span class="pastille p-gris">No invoice / Upcoming</span></td><td>The invoice is not in Sage yet, or the
deposit has not arrived yet.</td></tr></table>"""))

    # ------------------------------------------------------------------ 8. Factures fournisseurs
    parties.append(titre("fournisseurs") + figure("08_factures_fournisseurs", x("Fournisseur > Factures fournisseurs — Liste des factures fournisseurs",
                                                                   "Supplier > Supplier invoices — List of supplier invoices"))
                   + blocs("Factures fournisseurs")
                   + figure("08b_facture_detail", x("Fournisseur > Factures fournisseurs — Une facture ouverte : en-tête, lignes et article Sage",
                                                    "Supplier > Supplier invoices — An open invoice: header, lines and Sage item"))
                   + x("""
<h3>Calcul des quantités et des prix</h3>
<table class="simple"><tr><th>Champ</th><th>Calcul</th><th>Exemple</th></tr>
<tr><td>Montant</td><td>Qté × Prix fournisseur</td><td>3 sacs × 60,00 $ = 180,00 $</td></tr>
<tr><td>Qté Sage</td><td>Qté × Facteur</td><td>3 × 4,54 kg = 13,63 kg</td></tr>
<tr><td>Prix Sage</td><td>Montant / Qté Sage</td><td>180,00 $ / 13,63 = 13,2062 $ le kg</td></tr></table>
<div class="note">💡 Montant et Qté Sage sont calculés (en gris) : seuls Qté, Prix fournisseur et Facteur se
saisissent. La touche Entrée applique la ligne et passe à la suivante.</div>""", """
<h3>Quantity and price calculation</h3>
<table class="simple"><tr><th>Field</th><th>Calculation</th><th>Example</th></tr>
<tr><td>Amount</td><td>Qty × Supplier price</td><td>3 bags × $60.00 = $180.00</td></tr>
<tr><td>Sage qty</td><td>Qty × Factor</td><td>3 × 4.54 kg = 13.63 kg</td></tr>
<tr><td>Sage price</td><td>Amount / Sage qty</td><td>$180.00 / 13.63 = $13.2062 per kg</td></tr></table>
<div class="note">💡 Amount and Sage qty are calculated (in grey): only Qty, Supplier price and Factor are typed. The
Enter key applies the line and moves to the next one.</div>"""))

    # ------------------------------------------------------------------ 9. Paiements fournisseurs
    parties.append(titre("paiements") + figure("09_paiements", x("Comptabilité > Paiements fournisseur — Virements Interac reliés aux factures fournisseurs",
                                                       "Accounting > Supplier payments — Interac transfers linked to supplier invoices"))
                   + blocs("Paiements fournisseurs") + x("""
<table class="simple"><tr><th>État</th><th>Signification</th></tr>
<tr><td><span class="pastille p-jaune">À relier</span></td><td>Fournisseur ou facture à choisir.</td></tr>
<tr><td><span class="pastille p-bleu">Proposé</span></td><td>Fournisseur et facture proposés : à vérifier puis
confirmer.</td></tr>
<tr><td><span class="pastille p-vert">Confirmé (à saisir)</span></td><td>Sera saisi la nuit, ou avec « Payer dans
Sage ».</td></tr>
<tr><td><span class="pastille p-gris">Saisi dans Sage / Déjà dans Sage</span></td><td>Terminé.</td></tr>
<tr><td><span class="pastille p-gris">Ignoré</span></td><td>Pas un fournisseur (remboursement, prêt…).</td></tr>
<tr><td><span class="pastille p-rouge">Annulé / expiré</span></td><td>Virement annulé ou non réclamé : rien à saisir.
</td></tr></table>
<h3>Un virement pour plusieurs factures</h3>
<p>Sélectionnez les factures avec <b>Ctrl+clic</b>, puis « Confirmer le paiement ». Le montant est réparti de la plus
ancienne à la plus récente ; seule la dernière peut être payée en partie. Exemple : un virement de 910,00 $ sur deux
factures de 905,00 $ et 210,00 $ paie 905,00 $ sur la première et 5,00 $ sur la seconde.</p>""", """
<table class="simple"><tr><th>Status</th><th>Meaning</th></tr>
<tr><td><span class="pastille p-jaune">To link</span></td><td>Supplier or invoice to choose.</td></tr>
<tr><td><span class="pastille p-bleu">Suggested</span></td><td>Supplier and invoice suggested: check, then
confirm.</td></tr>
<tr><td><span class="pastille p-vert">Confirmed (to enter)</span></td><td>Will be entered at night, or with “Pay in
Sage”.</td></tr>
<tr><td><span class="pastille p-gris">Entered in Sage / Already in Sage</span></td><td>Done.</td></tr>
<tr><td><span class="pastille p-gris">Ignored</span></td><td>Not a supplier (refund, loan…).</td></tr>
<tr><td><span class="pastille p-rouge">Cancelled / expired</span></td><td>Transfer cancelled or not claimed: nothing to
enter.</td></tr></table>
<h3>One transfer for several invoices</h3>
<p>Select the invoices with <b>Ctrl+click</b>, then “Confirm payment”. The amount is spread from the oldest to the
newest; only the last one can be partly paid. Example: a $910.00 transfer on two invoices of $905.00 and $210.00 pays
$905.00 on the first and $5.00 on the second.</p>"""))

    # ------------------------------------------------------------------ 10. Rapprochement bancaire
    parties.append(titre("rapprochement") + figure("10_rapprochement", x("Comptabilité > Rapprochement — Relevés Desjardins rapprochés du compte 1055",
                                                            "Accounting > Reconciliation — Desjardins statements reconciled with account 1055"))
                   + blocs("Rapprochement bancaire") + x("""
<table class="simple"><tr><th>Chiffre</th><th>Signification</th></tr>
<tr><td>Solde du relevé</td><td>Solde de fermeture du dernier relevé chargé.</td></tr>
<tr><td>Solde Sage (1055)</td><td>Solde du compte 1055 dans Sage à la même date.</td></tr>
<tr><td>Écart d'ouverture</td><td>Différence déjà présente au début de la période (relevés précédents à charger).</td></tr>
<tr><td>Écart non expliqué</td><td>Doit être 0,00 $ : sinon un montant est mal saisi d'un côté ou de l'autre.</td></tr>
</table>""", """
<table class="simple"><tr><th>Figure</th><th>Meaning</th></tr>
<tr><td>Statement balance</td><td>Closing balance of the last statement loaded.</td></tr>
<tr><td>Sage balance (1055)</td><td>Balance of account 1055 in Sage on the same date.</td></tr>
<tr><td>Opening difference</td><td>Difference already present at the start of the period (earlier statements to
load).</td></tr>
<tr><td>Unexplained difference</td><td>Must be $0.00: otherwise an amount is wrongly entered on one side or the
other.</td></tr></table>"""))

    # ------------------------------------------------------------------ 11. Mode opératoire
    parties.append(titre("rapports") + figure("14_rapports", x("État > Suivi des ventes : suivi complet de chaque vente",
                                                        "Reports > Sales tracking: complete tracking of each sale"))
                   + figure("15_statistiques", x("État > Statistiques Clover : cartes, courbes, anneaux et menu des "
                                                 "états, comme le tableau de bord de Clover",
                                                 "Reports > Clover statistics: cards, curves, rings and the report "
                                                 "menu, like the Clover dashboard"))
                   + blocs("Rapports (menu")
                   + figure("16_apercu_ventes", x("Aperçu des ventes : courbes, anneaux et classements, infobulle au "
                                                  "survol", "Sales overview: curves, rings and rankings, tooltip on "
                                                  "hover"))
                   + figure("17_apercu_financier", x("Aperçu financier : les indicateurs (KPI) de la période",
                                                     "Financial overview: the period's indicators (KPI)"))
                   + figure("18_carte_chaleur", x("Carte de chaleur : ventes par jour de la semaine et par heure",
                                                  "Heat map: sales by weekday and hour"))
                   + figure("19_benefices", x("Bénéfices : ventes nettes Clover moins quantité × CUMP Sage",
                                              "Profits: Clover net sales minus quantity × Sage average cost"))
                   + figure("20_liste_articles", x("Liste d'articles : caractéristiques Clover, n° et CUMP Sage, marge",
                                                   "Item list: Clover details, Sage number and average cost, margin"))
                   + figure("21_previsions", x("Prévisions : ventes des prochains jours",
                                               "Forecasts: sales of the coming days"))
                   + "<div class='note'>💡 " + x("Clic droit sur un graphique : PDF ou image PNG. Bouton « 📕 PDF de "
                                                   "la page » : la page entière (indicateurs, graphiques, tableau).",
                                                   "Right-click a chart: PDF or PNG image. “📕 Page PDF” button: the "
                                                   "whole page (indicators, charts, table).") + "</div>")

    parties.append(titre("gestion") + "<p>" + x(
        "Les menus Vente, Fournisseur et Articles reprennent la gestion commerciale de Sage : listes lues dans Sage, "
        "interrogations de compte et saisies de documents.", "The Sales, Supplier and Items menus follow Sage's "
        "business management: lists read from Sage, account inquiries and document entry.") + "</p>"
        + questions("Comment sont rangés les menus", "Comment fonctionnent les listes", "Comment saisir une facture"))
    parties.append(titre("commercial") + "<p>" + x(
        "Deux outils pour acheter au bon moment et vendre au bon prix ; rien n'est envoyé ni changé sans votre clic.",
        "Two tools to buy at the right time and sell at the right price; nothing is sent or changed without your "
        "click.") + "</p>" + questions("Comment préparer mes commandes", "Comment vérifier mes marges",
                                       "Que contient le résumé du matin"))
    parties.append(titre("comptabilite") + "<p>" + x(
        "Ces états sont lus dans Sage (lecture seule) ; ils aident à suivre l'argent dû, les taxes et la trésorerie, "
        "et à clôturer chaque mois.", "These reports are read from Sage (read only); they help follow money owed, "
        "taxes and cash, and close each month.") + "</p>" + questions("Quelles fonctions de comptabilité"))
    parties.append(titre("paie") + "<p>" + x(
        "Les employés pointent au magasin avec leur NIP ; le gérant corrige et approuve les feuilles de temps ; Sage "
        "Paie calcule la paie et les retenues ; l'application présente les retenues à remettre.",
        "Employees clock in at the store with their PIN; the manager corrects and approves the timesheets; Sage "
        "Payroll calculates pay and deductions; the application shows the deductions to remit.") + "</p>"
        + questions("Comment les employés pointent", "Comment préparer le planning", "Comment préparer la paie",
                    "Où voir les retenues"))
    parties.append(titre("paie2") + "<p>" + x(
        "De la feuille de temps approuvée au bulletin envoyé à chaque employé : l'application ouvre Sage elle-même et "
        "vérifie chaque paie.", "From the approved timesheet to the pay stub sent to each employee: the application "
        "opens Sage itself and checks each pay.") + "</p>"
        + figure("22_traitement_paie", x("Paie > Traitement de la paie", "Payroll > Payroll processing"))
        + questions("Comment traiter la paie dans Sage", "Comment créer un employé", "Comment gérer les jours fériés",
                    "Comment préparer une fin d'emploi", "Comment suivre le coût de la main-d'œuvre")
        + figure("23_conges", x("Paie > Jours fériés et congés", "Payroll > Holidays and leave")))
    parties.append(titre("tresorerie") + "<p>" + x(
        "Suivre l'argent au jour le jour : tiroir-caisse, petite caisse, remises aux gouvernements et budget.",
        "Follow money day by day: cash drawer, petty cash, government remittances and budget.") + "</p>"
        + figure("24_caisse", x("Comptabilité > Contrôle de la caisse", "Accounting > Cash control"))
        + questions("Comment contrôler la caisse", "Comment noter les dépenses", "Comment suivre les remises",
                    "Comment relancer les clients")
        + figure("25_depenses", x("Comptabilité > Petite caisse et dépenses", "Accounting > Petty cash and expenses")))
    parties.append(titre("magasin") + "<p>" + x(
        "Garder un stock juste et des prix à jour dans Clover et dans Sage, pour chaque point de vente.",
        "Keep accurate stock and up-to-date prices in Clover and Sage, for each point of sale.") + "</p>"
        + figure("26_pertes", x("Articles > Pertes et démarque", "Items > Losses and shrinkage"))
        + questions("Comment déclarer des pertes", "Comment faire un retour", "Comment imprimer des étiquettes",
                    "Comment programmer une promotion", "Comment faire l'inventaire tournant",
                    "Comment ces outils fonctionnent")
        + figure("27_promotions", x("Articles > Promotions", "Items > Promotions"))
        + figure("28_etiquettes", x("Articles > Étiquettes de prix", "Items > Price labels")))
    parties.append(titre("securite") + "<p>" + x(
        "Vos données sont copiées chaque nuit ; chaque opération est notée ; le résumé du jour vous suit sur le "
        "téléphone.", "Your data is copied every night; every operation is logged; the daily summary follows you on "
        "your phone.") + "</p>"
        + figure("29_sauvegarde", x("Administration > Sauvegarde des données", "Administration > Data backup"))
        + questions("Comment mes données sont-elles sauvegardées", "Où voir qui a fait quoi",
                    "Comment voir le tableau du gérant")
        + figure("30_journal", x("Administration > Journal des opérations", "Administration > Operations log")))
    parties.append(titre("mode") + "<p>" + x("Les gestes à faire, au bon rythme, pour que tout reste à jour dans Sage.",
                                         "What to do, and when, to keep everything up to date in Sage.") + "</p>"
                   + blocs("Mode opératoire — chaque matin") + blocs("Mode opératoire — chaque semaine")
                   + blocs("Mode opératoire — chaque mois")
                   + "<div class='attention'>⚠️ " + x("Fermez Sage chaque soir avant de partir : sinon l'import de la "
                                                      "nuit échoue (il est repris la nuit suivante).",
                                                      "Close Sage every evening before leaving: otherwise the nightly "
                                                      "import fails (it is retried the next night).") + "</div>")

    # ------------------------------------------------------------------ 12. Règles
    parties.append(titre("regles") + blocs("Règles de facturation") + x("""
<h3>Encaissements et paiements</h3>
<ul>
<li>Dépôt Clover = ventes encaissées moins les espèces ; ventes du lundi au jeudi déposées le lendemain, du vendredi
au dimanche déposées ensemble le lundi.</li>
<li>Virements Interac reçus et dépôts d'espèces au guichet : espèces des ventes, encaissés sur la facture du jour.</li>
<li>Encaissement daté du dépôt, « Payé par : Comptant », compte 1055 (Desjardins).</li>
<li>Paiement fournisseur daté du virement, « Comptant », compte 1055 ; paiement partiel accepté, jamais plus que le
solde des factures choisies.</li>
</ul>
<h3>Factures fournisseurs</h3>
<ul>
<li>Qté Sage = Qté × Facteur ; Montant = Qté × Prix fournisseur ; Prix Sage = Montant / Qté Sage.</li>
<li>Deux formats différents sont deux articles différents.</li>
<li>Une facture déjà présente dans Sage (même n°, même avec un préfixe « FA- ») n'est jamais importée deux fois.</li>
</ul>""", """
<h3>Receipts and payments</h3>
<ul>
<li>Clover deposit = sales received minus cash; Monday-to-Thursday sales are deposited the next day, Friday-to-Sunday
sales together on Monday.</li>
<li>Interac transfers received and ATM cash deposits: sales cash, recorded on the invoice of the day.</li>
<li>Receipt dated on the deposit, “Paid by: Cash”, account 1055 (Desjardins).</li>
<li>Supplier payment dated on the transfer, “Cash”, account 1055; partial payment accepted, never more than the balance
of the chosen invoices.</li>
</ul>
<h3>Supplier invoices</h3>
<ul>
<li>Sage qty = Qty × Factor; Amount = Qty × Supplier price; Sage price = Amount / Sage qty.</li>
<li>Two different sizes are two different items.</li>
<li>An invoice already in Sage (same number, even with an “FA-” prefix) is never imported twice.</li>
</ul>""") + blocs("Fichiers et sauvegarde"))

    # ------------------------------------------------------------------ 13. FAQ
    parties.append(titre("faq") + faq() + blocs("Dépannage")
                   + f"<p class='pied'>MVOGMBI_Sync {VERSION} — {e(COPYRIGHT)} — "
                     f"{x('Tous droits réservés.', 'All rights reserved.')}</p>")
    # chaque chapitre dans une section qui porte ses pages (manuel du profil : mvogmbi_sync/manuel.py)
    sections = [parties[0]]
    for partie in parties[1:]:
        cle = partie[partie.index("<h1 id='") + 8:].split("'", 1)[0]
        pages = next(c[3] for c in CHAPITRES if c[0] == cle)
        sections.append(f"<section class='chapitre' data-pages='{','.join(map(str, pages))}'>{partie}</section>")
    return "\n".join(sections)


def questions(*debuts: str) -> str:
    """Questions et réponses de la FAQ dont la question FRANÇAISE commence par l'un des `debuts`, dans la langue
    en cours (même rang : les deux langues ont la même structure)."""
    sortie = []
    for i, (genre, texte) in enumerate(FAQ["fr"]):
        if genre == "question" and any(texte.startswith(d) for d in debuts):
            sortie.append(f"<p class='question'>{e(FAQ[LANGUE][i][1])}</p>"
                          f"<p class='reponse'>{e(FAQ[LANGUE][i + 1][1])}</p>")
    return "\n".join(sortie)


def fabriquer(langue: str = "fr") -> Path:
    global LANGUE
    LANGUE = langue
    langues.definir(langue)  # courriel d'exemple dans la langue du manuel
    sortie_html = ICI / f"{SORTIES[langue]}.html"
    sortie_pdf = ICI / f"{SORTIES[langue]}.pdf"
    page = (f"<!doctype html><html lang='{langue}'><head><meta charset='utf-8'><title>"
            f"{x("Manuel d'utilisation", 'User manual')} — MVOGMBI_Sync {VERSION}</title><style>{STYLE}</style>"
            f"</head><body>{contenu()}</body></html>")
    sortie_html.write_text(page, encoding="utf-8")
    edge = next((p for p in EDGE if p.exists()), None)
    if not edge:
        print("Microsoft Edge introuvable : seul le HTML est produit.")
        return sortie_html
    subprocess.run([str(edge), "--headless", "--disable-gpu", "--no-pdf-header-footer",
                    f"--print-to-pdf={sortie_pdf}", sortie_html.as_uri()], check=True, timeout=180,
                   capture_output=True)
    return sortie_pdf


if __name__ == "__main__":
    for code in sys.argv[1:] or ["fr", "en"]:
        print(fabriquer(code))
