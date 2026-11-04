"""5e vague de l'application web : rubrique Vente. « Ventes Clover → factures Sage » (Tableau de bord : lancer le
traitement, simulation, charger une période ; même commande `auto` que l'application Windows, sortie suivie en direct)
et « Clients professionnels et relances » (lettre de rappel imprimée ou envoyée au seul client).
"""

from __future__ import annotations

import os
import subprocess
import time
from datetime import date, timedelta

from .consultations import Section, sections_html
from .pages import Contexte, Fonction, argent, csrf, page
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
                                     env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"},
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
            return taches.lancer(ctx, "Simulation (sans import)", _auto(ctx, code, True, None, None), "/ventes-sage")
        elif action == "Lancer":
            return taches.lancer(ctx, "Traitement des ventes", _auto(ctx, code, False, None, None), "/ventes-sage",
                                 sage=True)
        elif action == "Charger la période":
            try:
                du, au = date.fromisoformat(ctx.req.champ("du")), date.fromisoformat(ctx.req.champ("au"))
                if not du <= au < date.today():
                    raise ValueError
            except ValueError:
                message = _message(erreur="Vérifiez les dates : du ≤ au, au plus tard hier.")
            else:
                return taches.lancer(ctx, f"Ventes du {du} au {au}", _auto(ctx, code, False, du, au), "/ventes-sage",
                                     sage=True)
    try:
        from .. import planification

        installee = "non installée" not in planification.etat()
    except Exception:  # noqa: BLE001
        installee = False
    derniere = etats_etapes(ctx.racine, ctx.config).get(6, (False, ""))[1] or "aucune"
    journal = ctx.racine / "donnees" / "journal_automatique.log"
    execution = journal.read_text(encoding="utf-8", errors="replace").split("===== ")[-1] if journal.exists() else ""
    problemes = execution.count("PROBLÈME") + execution.count("ERREUR")
    points = permis(ctx.config, ctx.reg.points_vente_permis(ctx.u))
    options = "<option value=''>Tous les points de vente</option>" + "".join(
        f"<option value='{e(p.code)}'>{e(p.libelle)}</option>" for p in points)
    hier = date.today() - timedelta(days=1)
    corps = (message
             + f"<div class='cartes'><div class='carte'><div class='t'>Dernière facture importée</div><div class='v'>"
               f"{e(derniere)}</div></div><div class='carte'><div class='t'>Tâche planifiée</div><div class='v'>"
               f"{'installée' if installee else 'NON installée'}</div></div><div class='carte'><div class='t'>Points "
               f"à corriger (dernière nuit)</div><div class='v {'baisse' if problemes else ''}'>{problemes}</div></div>"
               "</div>"
             + f"<form method='post' class='carte'>{csrf(ctx)}<div class='ligne'><div><label>Point de vente</label>"
               f"<select name='pv'>{options}</select></div></div><div class='boutons'><button name='action' "
               "value='Lancer'>▶ Lancer maintenant</button><button class='second' name='action' value='Simulation'>"
               "🧪 Simulation (sans import)</button></div><h2>Charger une date ou une période</h2><div class='ligne'>"
               f"<div><label>Du</label><input type='date' name='du' value='{hier}'></div><div><label>Au</label>"
               f"<input type='date' name='au' value='{hier}' max='{hier}'></div><button class='second' name='action' "
               "value='Charger la période'>Charger la période</button></div><p class='note'>Les jours déjà facturés "
               "sont sautés ; vendredi, samedi et dimanche forment une seule facture. Sage doit être fermé sur le "
               "serveur.</p></form>"
             + (f"<h2>Dernière exécution</h2><div class='carte'><pre class='resultat'>{e(execution[-6000:])}</pre></div>"
                if execution else ""))
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
    clients = lire_sage(ctx.config, lambda b: p3.clients_pro(b, date.today(), exclus), ouvrir=False)
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
        return Reponse(corps=page(ctx, "Clients professionnels et relances", _message(
            erreur="Lecture impossible : Sage ne répond pas sur le serveur pour l'instant.")))
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
    lignes = [[c.nom, c.courriel, len(c.factures), c.solde, c.echu, c.plus_30, c.limite or "",
               "Oui" if c.depasse else "", dernieres.get(c.nom, "")] for c in clients]
    echus = [c for c in clients if c.echu]
    choix = "".join(f"<option>{e(c.nom)}</option>" for c in echus)
    corps = (message + "<p><a href='?actualiser=1'>⟳ Actualiser</a></p>"
             + sections_html([Section("Clients avec des factures ouvertes", [
                 "Client", "Courriel", "Factures", "Solde", "Échu", "Plus de 30 jours", "Limite de crédit",
                 "Dépassement", "Dernière relance"], lignes)])
             + (f"<form method='post' class='ligne' target='_self'>{csrf(ctx)}<div><label>Client</label><select "
                f"name='client'>{choix}</select></div><button name='action' value='Imprimer' formaction='/relance-lettre' "
                "formmethod='get' class='second'>Lettre de rappel (imprimer)</button><button name='action' "
                "value='Envoyer'>Envoyer le rappel par courriel</button></form>" if echus else
                "<p>Aucune facture échue.</p>"))
    return Reponse(corps=page(ctx, "Clients professionnels et relances", corps))


def lettre(ctx: Contexte) -> Reponse:
    from .. import paquet3 as p3
    from ..export_tableau import page_html

    c = next((x for x in (ctx.app.memoire.get("clients_pro") or (0, []))[1] if x.nom == ctx.req.query.get("client")),
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
