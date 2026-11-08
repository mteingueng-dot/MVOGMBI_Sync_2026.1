"""5e vague de l'application web : rubrique Vente. « Ventes Clover → factures Sage » (Tableau de bord : lancer le
traitement, simulation, charger une période ; même commande `auto` que l'application Windows, sortie suivie en direct)
et « Clients professionnels et relances » (lettre de rappel imprimée ou envoyée au seul client).
"""

from __future__ import annotations

import os
import subprocess
import time
from datetime import date, timedelta

from .consultations import lire_ou_vide, Section, sections_html
from .pages import Contexte, Fonction, argent, csrf, page, permis as permis_page
from .pages_compta import _message, action_permise
from .serveur import Reponse, echapper as e

LANCER = "Lancer le traitement maintenant"


def _code_points(ctx: Contexte, choix: str) -> str:
    from ..points_vente import TOUS, permis

    points = permis(ctx.config, ctx.reg.points_vente_permis(ctx.u))
    if choix and any(str(p.code) == choix for p in points):
        return choix
    return TOUS if ctx.reg.points_vente_permis(ctx.u) is None else ",".join(str(p.code) for p in points)


def _auto(ctx: Contexte, code: str, simulation: bool, depuis: date | None, jusqua: date | None):
    def travail(journal):
        from ..__main__ import commande_moteur, fermer_bases
        from ..traitements import env_enfant

        fermer_bases()  # base gardée relâchée : le traitement importe dans Sage
        commande = commande_moteur() + ["auto", "--point-de-vente", code]
        if simulation:
            commande.append("--simulation")
        if depuis:
            commande += ["--depuis", depuis.isoformat()]
        if jusqua:
            commande += ["--jusqua", jusqua.isoformat()]
        processus = subprocess.Popen(commande, cwd=ctx.racine, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     text=True, encoding="utf-8", errors="replace",
                                     env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1",
                                              **env_enfant("Web")},
                                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        for ligne in processus.stdout:
            journal(ligne.rstrip())
        return "Traitement réussi." if processus.wait() == 0 else \
            "Traitement terminé avec des points à corriger (voir le déroulement)."
    return travail


def tableau_ventes(ctx: Contexte) -> Reponse:
    from ..points_vente import permis
    from . import taches
    from .accueil import etats_etapes

    message = ""
    if ctx.req.methode == "POST":
        action = ctx.req.champ("action")
        code = _code_points(ctx, ctx.req.champ("pv"))
        if action != "Simulation" and not action_permise(ctx, LANCER):
            message = _message(erreur=f"Votre profil n'a pas le droit « {LANCER} ».")
        elif action == "Simulation":
            return taches.lancer(ctx, "Simulation (sans import)", _auto(ctx, code, True, None, None), "/ventes-sage", noter=False)
        elif action == "Lancer":
            return taches.lancer(ctx, "Traitement des ventes", _auto(ctx, code, False, None, None), "/ventes-sage", noter=False,
                                 sage=True)
        elif action == "Charger la période":
            try:
                du, au = date.fromisoformat(ctx.req.champ("du")), date.fromisoformat(ctx.req.champ("au"))
                if not du <= au < date.today():
                    raise ValueError
            except ValueError:
                message = _message(erreur="Vérifiez les dates : du ≤ au, au plus tard hier.")
            else:
                return taches.lancer(ctx, f"Ventes du {du} au {au}", _auto(ctx, code, False, du, au), "/ventes-sage", noter=False,
                                     sage=True)
    if ctx.req.query.get("excel"):  # « 📗 Excel » : le fichier de correspondance
        chemin = ctx.racine / "donnees" / "correspondance_articles.xlsx"
        if chemin.exists() and ctx.reg.peut_exporter(ctx.u):
            return Reponse(corps=chemin.read_bytes(),
                           type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           entetes={"Content-Disposition": "attachment; filename=\"correspondance_articles.xlsx\""})
    try:
        from .. import planification

        installee = "non installée" not in planification.etat()
    except Exception:  # noqa: BLE001
        installee = False
    derniere = etats_etapes(ctx.racine, ctx.config).get(6, (False, ""))[1] or "aucune"
    journal = ctx.racine / "donnees" / "journal_automatique.log"
    texte = journal.read_text(encoding="utf-8", errors="replace") if journal.exists() else ""
    execution = texte.split("===== ")[-1] if texte else ""
    problemes = execution.count("PROBLÈME") + execution.count("ERREUR")
    points = permis(ctx.config, ctx.reg.points_vente_permis(ctx.u))
    options = "<option value=''>Tous les points de vente</option>" + "".join(
        f"<option value='{e(p.code)}'>{e(p.libelle)}</option>" for p in points)
    hier = date.today() - timedelta(days=1)
    cartes = "".join(  # comme Application.actualiser_tableau : filet de couleur, icône, titre, valeur
        f"<div class='carte-bord {couleur}'><span class='ic'>{icone}</span><div><div class='t'>{e(titre)}</div>"
        f"<div class='v'>{e(valeur)}</div></div></div>"
        for icone, titre, valeur, couleur in (
            ("🧾", "Dernière facture importée", derniere, "vert"),
            ("⏰", "Tâche planifiée", "installée" if installee else "NON installée", "vert" if installee else "jaune"),
            ("⚠", "Points à corriger (dernier traitement)", str(problemes), "rouge" if problemes else "vert")))

    def classe(ligne: str) -> str:  # couleurs de Application._ecrire
        if any(m in ligne for m in ("ERREUR", "PROBLÈME", "✘", "échec", "Échec")):
            return "erreur"
        if any(m in ligne for m in ("⚠", "bloqu", "à vérifier", "Attention")):
            return "attention"
        return "ok" if any(m in ligne for m in ("✔", "importée", "OK", "terminé")) else ""

    sortie = "".join(f"<span class='{classe(l)}'>{e(l)}</span>\n" for l in texte.splitlines()[-60:])
    excel = ("<a class='ouvrir' href='/ventes-sage?excel=1'>📗 Excel</a>" if ctx.reg.peut_exporter(ctx.u) else "")
    if permis_page(ctx.reg, ctx.u, Fonction("", "utilisateurs", "utilisateurs", None, "", "", page_entiere=True)):
        excel += "<a class='ouvrir' href='/dossier-donnees'>📁 Dossier des données</a>"  # tout donnees/
    from .pages_admin import _titre

    corps = (_titre("Tableau de bord") + message + f"<div class='cartes-bord'>{cartes}</div>"
             + f"<form method='post'>{csrf(ctx)}<div class='barre-onglet'><div><label>Point de vente :</label>"
               f"<select name='pv'>{options}</select></div></div><div class='barre-onglet'><button name='action' "
               "value='Lancer'>▶ Lancer maintenant</button><button class='accent' name='action' value='Simulation'>"
               f"🧪 Simulation (sans import)</button>{excel}<a class='ouvrir' href='/comptes-categories'>🧾 Corriger "
               "les comptes dans Sage…</a><a class='ouvrir a-droite' href='/ventes-sage'>⟳</a></div>"
               "<div class='barre-onglet'><div><label>Charger une date ou une période : du</label><input type='date' "
               f"name='du' value='{hier}'></div><div><label>au</label><input type='date' name='au' value='{hier}' "
               f"max='{hier}'></div><button class='second' name='action' value='Charger la période'>📥 Charger la "
               "période</button></div></form>"
             + f"<pre class='sortie'>{sortie or 'Aucun traitement pour l’instant.'}</pre>"
             + "<p class='note'>Les jours déjà facturés sont sautés ; vendredi, samedi et dimanche forment une seule "
               "facture. Sage doit être fermé sur le serveur.</p>")
    return Reponse(corps=page(ctx, "Ventes Clover → factures Sage", corps))


# --------------------------------------------------------------------------------------------- relances
def _clients(ctx: Contexte, forcer: bool = False):
    from .. import paquet3 as p3
    from ..__main__ import lire_sage
    from ..facture import CLIENT
    from ..points_vente import points_de_vente

    gardee = ctx.app.memoire.get("clients_pro")
    if gardee and not forcer and time.time() - gardee[0] < 300:
        return gardee[1]
    exclus = {CLIENT} | {p.client_sage for p in points_de_vente(ctx.config)}
    clients = lire_ou_vide(ctx, lambda b: p3.clients_pro(b, date.today(), exclus))
    if "Sage" not in ctx.absents:
        ctx.app.memoire["clients_pro"] = (time.time(), clients)
    return clients


def relances(ctx: Contexte) -> Reponse:
    from .. import paquet3 as p3
    from . import taches

    message = ""
    try:
        clients = _clients(ctx, forcer=bool(ctx.req.query.get("actualiser")))
    except (Exception, SystemExit) as erreur:  # noqa: BLE001
        ctx.app.noter(f"Relances : {erreur!r}")
        ctx.absents.add("Sage")
        clients = []
    if ctx.req.methode == "POST":
        c = next((x for x in clients if x.nom == ctx.req.champ("client")), None)
        if c is None or not c.echu:
            message = _message(erreur="Ce client n'a aucune facture échue.")
        elif ctx.req.champ("action") == "Envoyer":
            action = "Envoyer une relance par courriel"
            if not action_permise(ctx, action):
                message = _message(erreur=f"Votre profil n'a pas le droit « {action} ».")
            elif not c.courriel:
                message = _message(erreur=f"{c.nom} n'a pas de courriel dans sa fiche Sage.")
            else:
                def envoyer(journal):
                    import tempfile
                    from pathlib import Path

                    from ..courriel import envoyer_a
                    from ..export_tableau import page_html, pdf_depuis_html

                    entetes, lignes, sous = p3.lettre_relance(c, date.today())
                    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as dossier:
                        pdf = Path(dossier) / "rappel.pdf"
                        pdf_depuis_html(page_html("Rappel de paiement", entetes, lignes, sous_titre=sous), pdf)
                        envoyer_a(ctx.config, c.courriel, f"Rappel de paiement — {c.nom}",
                                  f"Bonjour,\n\nSauf erreur de notre part, des factures sont échues ({argent(c.echu)}). "
                                  "Vous trouverez le détail ci-joint.\n\nMerci de votre attention.\n",
                                  [("Rappel de paiement.pdf", pdf.read_bytes())])
                    p3.noter_relance(ctx.racine, c.nom, c.echu, "courriel")
                    return f"Rappel envoyé à {c.nom} ({c.courriel})."

                return taches.lancer(ctx, f"Rappel de paiement à {c.nom}", envoyer, "/relances")
    dernieres = p3.derniere_relance(ctx.racine)
    choisi = ctx.req.champ("client")
    lignes = [[f"<input type='radio' name='client' value='{e(c.nom)}'{' checked' if c.nom == choisi else ''}>",
               e(c.nom), e(c.courriel), str(len(c.factures)), argent(c.solde), argent(c.echu), argent(c.plus_30),
               argent(c.limite) if c.limite else "", "Oui" if c.depasse else "", e(dernieres.get(c.nom, ""))]
              for c in clients]
    classes = ["etat-ecart" if c.plus_30 or c.depasse else "" for c in clients]
    from .consultations import tableau_section

    corps = (message + f"<form method='post'>{csrf(ctx)}<div class='barre-onglet'><a class='ouvrir' "
             "href='/relances?actualiser=1'>🔍 Lire dans Sage</a><button class='second' name='action' value='Imprimer' "
             "formaction='/relance-lettre' formtarget='_blank'>🖨 Imprimer la lettre de relance"
             "</button><button class='second' name='action' value='Envoyer'>✉ Envoyer la relance par courriel…</button>"
             "</div><p class='note'>Factures ouvertes des clients de Sage (hors ventes Clover), limite de crédit et "
             "retards. En rose : plus de 30 jours ou limite de crédit dépassée.</p>"
             + tableau_section(Section("Clients professionnels", ["", "Client", "Courriel", "Factures", "Solde", "Échu",
                                                                  "Plus de 30 jours", "Limite de crédit", "Dépassement",
                                                                  "Dernière relance"], lignes, classes=classes,
                                       html=set(range(10))))
             + f"</form><div class='ligne-etat'>{len(clients)} client(s) avec des factures ouvertes.</div>")
    return Reponse(corps=page(ctx, "Clients professionnels et relances", corps))


def lettre(ctx: Contexte) -> Reponse:
    from .. import paquet3 as p3
    from ..export_tableau import page_html

    c = next((x for x in (ctx.app.memoire.get("clients_pro") or (0, []))[1] if x.nom == (ctx.req.query.get("client") or ctx.req.champ("client"))),
             None)
    if c is None or not c.echu:
        return Reponse(404, page(ctx, "Rappel de paiement", "<p>Client introuvable : actualisez la liste.</p>"))
    entetes, lignes, sous = p3.lettre_relance(c, date.today())
    p3.noter_relance(ctx.racine, c.nom, c.echu, "imprimée")
    return Reponse(corps=page_html("Rappel de paiement", entetes, lignes, sous_titre=sous), style_en_ligne=True)


FONCTIONS = [
    Fonction("/ventes-sage", "Ventes Clover → factures Sage", "tableau", tableau_ventes, "📊", "Vente", menu=False, page_entiere=True),
    Fonction("/relances", "Clients professionnels et relances", "rapprochement", relances, "📨", "Vente", menu=False),
    Fonction("/relance-lettre", "Clients professionnels et relances", "rapprochement", lettre, "📨", "Vente",
             menu=False),
]
WEB = {"Ventes Clover → factures Sage": "/ventes-sage", "Clients professionnels et relances": "/relances"}
