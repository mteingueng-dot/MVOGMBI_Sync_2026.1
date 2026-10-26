"""Fabrique le manuel d'utilisation illustré : documentation/Manuel_MVOGMBI_Sync.html puis .pdf (Microsoft Edge).

Les captures d'écran sont dans documentation/captures/ (prises sur une copie des données de l'application). Le mode
opératoire, les règles et la FAQ viennent de mvogmbi_sync/aide.py : le manuel reste identique à l'aide intégrée.

    python documentation/creer_manuel.py
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

from mvogmbi_sync.aide import COPYRIGHT, EDITEUR, FAQ, GUIDE, VERSION  # noqa: E402

CAPTURES = ICI / "captures"
LOGO = RACINE / "mvogmbi_sync" / "ressources" / "logo.png"
SORTIE_HTML = ICI / "Manuel_MVOGMBI_Sync.html"
SORTIE_PDF = ICI / "Manuel_MVOGMBI_Sync.pdf"
EDGE = [Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe")]

e = html.escape


def figure(nom: str, legende: str) -> str:
    chemin = CAPTURES / f"{nom}.png"
    if not chemin.exists():
        return f"<p class='manque'>[capture « {e(nom)} » absente]</p>"
    return (f"<figure><img src='captures/{nom}.png' alt='{e(legende)}'>"
            f"<figcaption>{e(legende)}</figcaption></figure>")


def blocs(liste, debut: str) -> str:
    """Section de l'aide dont le sous-titre commence par `debut`, jusqu'au sous-titre suivant, en HTML."""
    sortie, actif, ouvert = [], False, None
    for genre, texte in liste:
        if genre == "sous_titre":
            if actif:
                break
            if texte.startswith(debut):
                actif = True
                sortie.append(f"<h3>{e(texte)}</h3>")
            continue
        if not actif:
            continue
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
    for genre, texte in FAQ["fr"][1:]:
        if genre == "sous_titre":
            sortie.append(f"<h3>{e(texte)}</h3>")
        elif genre == "question":
            sortie.append(f"<p class='question'>{e(texte)}</p>")
        elif genre == "reponse":
            sortie.append(f"<p class='reponse'>{e(texte)}</p>")
    return "\n".join(sortie)


def courriel_exemple() -> str:
    """Compte rendu de nuit fictif, rendu exactement comme le courriel envoyé."""
    from mvogmbi_sync.automatique import AUCUNE_VENTE, IMPORTEE, CompteRendu, EtatJour
    from mvogmbi_sync.courriel import html_compte_rendu

    cr = CompteRendu(fichier="MARCHE.SAI", derniere_avant=date(2026, 10, 21),
                     periode=(date(2026, 10, 22), date(2026, 10, 22)))
    cr.jours = [EtatJour(date(2026, 10, 22), IMPORTEE, "", 143, Decimal("2108.98"), Decimal("55.95"),
                         Decimal("2164.93"))]
    cr.encaissements = ["Dépôt du 2026-10-23 : 1 842,10 $ au compte 1055 (Vente 2026-10-22)"]
    cr.paiements = ["2026-10-22 : 632,36 $ à Transport Exemple, facture 15 (virement CA0000000)"]
    cr.lignes = ["01:00:19 Lecture de Sage (MARCHE.SAI)…", "01:00:54 Import de 1 facture(s)…",
                 "01:00:56 1 facture(s) importée(s) et vérifiée(s) dans Sage.", "01:02:10 1 dépôt(s) encaissé(s).",
                 "01:03:30 1 paiement(s) fournisseur(s) saisi(s) dans Sage."]
    del AUCUNE_VENTE
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

CHAPITRES = [
    ("presentation", "Présentation"), ("installation", "Installation et premier lancement"),
    ("interface", "Découvrir l'interface"), ("configuration", "Configuration (pages 1 à 4)"),
    ("correspondance", "Correspondance des articles (page 5)"), ("tableau", "Tableau de bord et traitement de nuit"),
    ("encaissements", "Encaissements des dépôts Clover (page 7)"),
    ("fournisseurs", "Factures fournisseurs (page 8)"), ("paiements", "Paiements fournisseurs (page 9)"),
    ("rapprochement", "Rapprochement bancaire (page 10)"), ("mode", "Mode opératoire"), ("regles", "Règles de gestion"), ("faq", "Questions fréquentes et dépannage"),
]


def titre(numero: int) -> str:
    cle, texte = CHAPITRES[numero - 1]
    return (f"<h1 id='{cle}'><span class='num'>{numero}</span>{e(texte)}</h1>"
            "<div class='filet-titre'><span style='width:60px;background:#f6b81a'></span>"
            "<span style='width:18px;background:#d7263d'></span></div>")


def contenu() -> str:
    g = GUIDE["fr"]
    parties = []
    # ------------------------------------------------------------------ couverture et sommaire
    parties.append(f"""
<div class="couverture">
  <img src="../mvogmbi_sync/ressources/logo.png" alt="Logo">
  <div class="grand">Manuel d'utilisation</div>
  <div class="sous">MVOGMBI_Sync — Clover → Sage 50</div>
  <div class="filet"><span style="width:90px;background:#1a9b3c"></span><span style="width:60px;background:#f6b81a">
  </span><span style="width:24px;background:#d7263d"></span></div>
  <div class="sous" style="font-size:12pt">Marché MVOG-MBI Sherbrooke — épicerie africaine &amp; caribéenne</div>
  <div class="infos">Version {VERSION} — {date.today():%Y-%m-%d}<br>Conçu et développé par {e(EDITEUR)}<br>
  {e(COPYRIGHT)} — Tous droits réservés.</div>
</div>
<div class="toc"><h2 style="font-size:18pt">Sommaire</h2><ol>
{''.join(f"<li><span>{i}</span>{e(t)}</li>" for i, (_, t) in enumerate(CHAPITRES, 1))}
</ol></div>""")

    # ------------------------------------------------------------------ 1. Présentation
    parties.append(titre(1) + """
<p>MVOGMBI_Sync relie le point de vente <b>Clover</b> du Marché MVOG-MBI Sherbrooke à la comptabilité
<b>Sage 50 Comptabilité, Édition canadienne</b>. L'application travaille seule chaque nuit et vous envoie un compte
rendu par courriel le matin. Elle couvre quatre domaines :</p>
<table class="simple">
<tr><th>Domaine</th><th>Ce que fait l'application</th><th>Page</th></tr>
<tr><td><b>Ventes</b></td><td>Les ventes Clover de chaque jour deviennent une facture de vente dans Sage (client
« Vente Hebdomadaire »), une ligne par article.</td><td>5, 6</td></tr>
<tr><td><b>Encaissements</b></td><td>Les dépôts Clover arrivés au compte Desjardins (1055) sont appliqués sur ces
factures.</td><td>7</td></tr>
<tr><td><b>Factures fournisseurs</b></td><td>Les factures reçues (PDF, scans, photos) sont lues, reliées aux articles
Sage et importées comme factures d'achat.</td><td>8</td></tr>
<tr><td><b>Paiements fournisseurs</b></td><td>Les avis de virement Interac reçus par courriel sont reliés aux factures
et saisis comme paiements dans Sage.</td><td>9</td></tr>
</table>
<h2>Le traitement de chaque nuit</h2>
<ol class="etapes">
<li>À 1 h (heure réglable), l'application lit dans Sage la dernière facture « Vente AAAA-MM-JJ ».</li>
<li>Elle récupère dans Clover les ventes de chaque jour suivant, jusqu'à hier.</li>
<li>Elle prépare et importe les factures, puis vérifie chacune d'elles dans Sage.</li>
<li>Elle encaisse les dépôts Clover et saisit les paiements fournisseurs que vous avez confirmés.</li>
<li>Elle vous envoie un compte rendu par courriel.</li>
</ol>
<div class="note">💡 Sage doit être <b>fermé</b> pendant la nuit : l'application l'ouvre elle-même, sans rien
afficher, puis le referme. L'ordinateur doit rester allumé et la session Windows ouverte (elle peut être
verrouillée).</div>
<h2>Contrôles de sécurité</h2>
<ul>
<li>Jamais deux fois la même facture ou le même paiement : ce qui existe déjà dans Sage est ignoré.</li>
<li>Arrêt au premier jour qui pose problème ; il est repris la nuit suivante, une fois corrigé.</li>
<li>Deux formats différents (500 g et 1 kg) ne sont jamais confondus.</li>
<li>Rien n'est saisi sans contrôle du total, et chaque saisie est vérifiée ensuite dans Sage.</li>
<li>Les mots de passe sont gardés dans le coffre-fort de Windows, jamais dans un fichier.</li>
</ul>""")

    # ------------------------------------------------------------------ 2. Installation
    parties.append(titre(2) + """
<ol class="etapes">
<li>Lancez <b>Installer_MVOGMBI_Sync_x.y.z.exe</b> (aucun droit d'administrateur n'est demandé). Chaque version a son
propre fichier d'installation ; une mise à jour conserve votre configuration et vos données.</li>
<li>Choisissez la langue de l'installation, puis celle de l'application (français ou anglais, modifiable ensuite).</li>
<li>À la dernière page, cochez au besoin « Créer un raccourci sur le Bureau » et « Ouvrir MVOGMBI_Sync ».</li>
<li>L'application s'installe dans <code>%LOCALAPPDATA%\\Programs\\MVOGMBI_Sync</code>. Le menu Démarrer contient
l'application, ce manuel, le journal du traitement et la désinstallation.</li>
</ol>
<div class="note">💡 Nouvel ordinateur ou réinstallation : page « 4. Automatisation », bouton « Reprendre une
configuration existante… », puis choisissez l'ancien dossier : la correspondance validée, les journaux et la
configuration sont recopiés.</div>""")

    # ------------------------------------------------------------------ 3. Interface
    parties.append(titre(3) + figure("00_accueil", "Page d'accueil : liste « Mise en route » et présentation") + """
<ul>
<li><b>Bandeau vert</b> : nom du marché et rôle de l'application.</li>
<li><b>Menu de gauche</b> : les pages de travail, numérotées dans l'ordre de la mise en service. Une coche verte
indique une étape terminée, un point jaune une étape à faire.</li>
<li><b>Mise en route</b> : les six étapes de la mise en service ; « Ouvrir » mène directement à la page concernée.</li>
<li><b>Langue / Language</b> : français ou anglais, en bas du menu.</li>
<li><b>Enregistrer la configuration</b> : en bas à droite, à cliquer après toute modification des pages 1 à 4.</li>
</ul>""")

    # ------------------------------------------------------------------ 4. Configuration
    parties.append(titre(4) + blocs(g, "Avant de commencer") + "<h2>Page 1 — Clover</h2>"
                   + figure("01_clover", "Page 1 — Clover : identifiant marchand et jeton API")
                   + blocs(g, "Étape 1") + "<h2>Page 2 — Sage 50</h2>"
                   + figure("02_sage", "Page 2 — Sage 50 : fichier d'entreprise, comptes et utilisateurs")
                   + blocs(g, "Étape 2") + "<h2>Page 3 — Courriel</h2>"
                   + figure("03_courriel", "Page 3 — Courriel : compte rendu et boîte des avis de paiement")
                   + blocs(g, "Étape 3") + "<h2>Page 4 — Automatisation</h2>"
                   + figure("04_automatisation", "Page 4 — Automatisation : tâche planifiée de la nuit")
                   + blocs(g, "Étape 4") + blocs(g, "Mise en production"))

    # ------------------------------------------------------------------ 5. Correspondance
    parties.append(titre(5) + figure("05_correspondance", "Page 5 — Correspondance des articles Clover et Sage")
                   + blocs(g, "Étape 5") + """
<table class="simple"><tr><th>Statut</th><th>Signification</th><th>Action</th></tr>
<tr><td><span class="pastille p-vert">Confirmé</span></td><td>Relié par vous</td><td>Aucune</td></tr>
<tr><td><span class="pastille p-gris">Automatique</span></td><td>Même nom ou même code-barres</td><td>Aucune</td></tr>
<tr><td><span class="pastille p-jaune">À confirmer</span></td><td>Une proposition existe</td>
<td>Vérifier, puis « Accepter la proposition »</td></tr>
<tr><td><span class="pastille p-rouge">Aucun</span></td><td>Pas d'article Sage au bon format</td>
<td>Créer l'article dans Sage, puis « Mettre à jour depuis Clover et Sage »</td></tr></table>""")

    # ------------------------------------------------------------------ 6. Tableau de bord
    parties.append(titre(6) + figure("06_tableau_de_bord", "Page 6 — Tableau de bord : dernier import, tâche, journal")
                   + """
<ul>
<li><b>Dernière facture importée</b>, état de la <b>tâche planifiée</b> et nombre de <b>points à corriger</b>.</li>
<li><b>Lancer maintenant</b> : exécute tout de suite le traitement de la nuit (Sage fermé).</li>
<li><b>Simulation (sans import)</b> : prépare les factures sans rien importer, pour lire les points à corriger.</li>
<li><b>Excel</b> : rapport des ventes ; <b>Dossier des données</b> : journaux, correspondance et sauvegardes.</li>
</ul>""" + blocs(g, "Étape 6") + """
<h2>Le courriel du matin</h2>
<p>Après chaque traitement, un compte rendu est envoyé aux destinataires de la page Courriel. Exemple (données
fictives) :</p>
<div class="courriel">""" + courriel_exemple() + "</div>")

    # ------------------------------------------------------------------ 7. Encaissements
    parties.append(titre(7) + figure("07_encaissements", "Page 7 — Encaissements des dépôts Clover")
                   + blocs(g, "Encaissements des dépôts Clover") + """
<table class="simple"><tr><th>État</th><th>Signification</th></tr>
<tr><td><span class="pastille p-vert">Appliqué</span></td><td>Le dépôt est encaissé sur la facture dans Sage.</td></tr>
<tr><td><span class="pastille p-jaune">À saisir dans Sage</span></td><td>Sera encaissé la nuit, ou avec « Encaisser dans
Sage ».</td></tr>
<tr><td><span class="pastille p-rouge">Écart</span></td><td>Un montant différent est déjà saisi dans Sage : à vérifier.
</td></tr>
<tr><td><span class="pastille p-gris">Sans facture / À venir</span></td><td>La facture n'est pas encore dans Sage, ou le
dépôt n'est pas encore arrivé.</td></tr></table>""")

    # ------------------------------------------------------------------ 8. Factures fournisseurs
    parties.append(titre(8) + figure("08_factures_fournisseurs", "Page 8 — Liste des factures fournisseurs")
                   + blocs(g, "Factures fournisseurs")
                   + figure("08b_facture_detail", "Page 8 — Une facture ouverte : en-tête, lignes et article Sage")
                   + """
<h3>Calcul des quantités et des prix</h3>
<table class="simple"><tr><th>Champ</th><th>Calcul</th><th>Exemple</th></tr>
<tr><td>Montant</td><td>Qté × Prix fournisseur</td><td>3 sacs × 60,00 $ = 180,00 $</td></tr>
<tr><td>Qté Sage</td><td>Qté × Facteur</td><td>3 × 4,54 kg = 13,63 kg</td></tr>
<tr><td>Prix Sage</td><td>Montant / Qté Sage</td><td>180,00 $ / 13,63 = 13,2062 $ le kg</td></tr></table>
<div class="note">💡 Montant et Qté Sage sont calculés (en gris) : seuls Qté, Prix fournisseur et Facteur se
saisissent. La touche Entrée applique la ligne et passe à la suivante.</div>""")

    # ------------------------------------------------------------------ 9. Paiements fournisseurs
    parties.append(titre(9) + figure("09_paiements", "Page 9 — Virements Interac reliés aux factures fournisseurs")
                   + blocs(g, "Paiements fournisseurs") + """
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
factures de 905,00 $ et 210,00 $ paie 905,00 $ sur la première et 5,00 $ sur la seconde.</p>""")

    # ------------------------------------------------------------------ 10. Rapprochement bancaire
    parties.append(titre(10) + figure("10_rapprochement", "Page 10 — Relevés Desjardins rapprochés du compte 1055")
                   + blocs(g, "Rapprochement bancaire") + """
<table class="simple"><tr><th>Chiffre</th><th>Signification</th></tr>
<tr><td>Solde du relevé</td><td>Solde de fermeture du dernier relevé chargé.</td></tr>
<tr><td>Solde Sage (1055)</td><td>Solde du compte 1055 dans Sage à la même date.</td></tr>
<tr><td>Écart d'ouverture</td><td>Différence déjà présente au début de la période (relevés précédents à charger).</td></tr>
<tr><td>Écart non expliqué</td><td>Doit être 0,00 $ : sinon un montant est mal saisi d'un côté ou de l'autre.</td></tr>
</table>""")

    # ------------------------------------------------------------------ 11. Mode opératoire
    parties.append(titre(11) + "<p>Les gestes à faire, au bon rythme, pour que tout reste à jour dans Sage.</p>"
                   + blocs(g, "Mode opératoire — chaque matin") + blocs(g, "Mode opératoire — chaque semaine")
                   + blocs(g, "Mode opératoire — chaque mois")
                   + "<div class='attention'>⚠️ Fermez Sage chaque soir avant de partir : sinon l'import de la nuit "
                     "échoue (il est repris la nuit suivante).</div>")

    # ------------------------------------------------------------------ 12. Règles
    parties.append(titre(12) + blocs(g, "Règles de facturation") + """
<h3>Encaissements et paiements</h3>
<ul>
<li>Dépôt Clover = ventes encaissées moins les espèces ; ventes du lundi au jeudi déposées le lendemain, du vendredi
au dimanche déposées ensemble le lundi.</li>
<li>Encaissement daté du dépôt, « Payé par : Comptant », compte 1055 (Desjardins).</li>
<li>Paiement fournisseur daté du virement, « Comptant », compte 1055 ; paiement partiel accepté, jamais plus que le
solde des factures choisies.</li>
</ul>
<h3>Factures fournisseurs</h3>
<ul>
<li>Qté Sage = Qté × Facteur ; Montant = Qté × Prix fournisseur ; Prix Sage = Montant / Qté Sage.</li>
<li>Deux formats différents sont deux articles différents.</li>
<li>Une facture déjà présente dans Sage (même n°, même avec un préfixe « FA- ») n'est jamais importée deux fois.</li>
</ul>""" + blocs(g, "Fichiers et sauvegarde"))

    # ------------------------------------------------------------------ 13. FAQ
    parties.append(titre(13) + faq() + blocs(g, "Dépannage")
                   + f"<p class='pied'>MVOGMBI_Sync {VERSION} — {e(COPYRIGHT)} — Tous droits réservés.</p>")
    return "\n".join(parties)


def fabriquer() -> Path:
    page = (f"<!doctype html><html lang='fr'><head><meta charset='utf-8'><title>Manuel d'utilisation — "
            f"MVOGMBI_Sync {VERSION}</title><style>{STYLE}</style></head><body>{contenu()}</body></html>")
    SORTIE_HTML.write_text(page, encoding="utf-8")
    edge = next((p for p in EDGE if p.exists()), None)
    if not edge:
        print("Microsoft Edge introuvable : seul le HTML est produit.")
        return SORTIE_HTML
    subprocess.run([str(edge), "--headless", "--disable-gpu", "--no-pdf-header-footer",
                    f"--print-to-pdf={SORTIE_PDF}", SORTIE_HTML.as_uri()], check=True, timeout=180,
                   capture_output=True)
    return SORTIE_PDF


if __name__ == "__main__":
    print(fabriquer())
