"""4e vague de l'application web : rubrique Comptabilité, saisies (demande du propriétaire du 2026-11-03 : « lance
toutes les vagues à la suite »). Contrôle de la caisse (comptage du soir, écarts par jour, dépôts d'espèces), petite
caisse et dépenses (saisie, reçu joint, comptes, saisie dans Sage). Mêmes règles et mêmes droits par action que les
fenêtres Windows (fenetre_caisse, fenetres_gestion2).
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from .consultations import Section, sections_html
from .pages import Contexte, Fonction, argent, csrf, page
from .serveur import Reponse, echapper as e


def action_permise(ctx: Contexte, action: str) -> bool:
    """Action sensible d'une fenêtre (utilisateurs.ACTIONS_FENETRES) non retirée au profil."""
    return ctx.u.est_admin or action not in ctx.reg.refusees(ctx.u)


def refus(action: str) -> str:
    return f"<p class='erreur'>Votre profil n'a pas le droit « {e(action)} ».</p>"


def _message(ok: str = "", erreur: str = "") -> str:
    return (f"<p class='ok'>{e(ok)}</p>" if ok else "") + (f"<p class='erreur'>{e(erreur)}</p>" if erreur else "")


def _jour(texte: str, defaut: date) -> date:
    try:
        return date.fromisoformat(texte)
    except (TypeError, ValueError):
        return defaut


def _point_vente(ctx: Contexte):
    """Point de vente choisi (?pv=code) parmi ceux du profil ; None = n° 1 (fichiers de donnees/)."""
    from ..points_vente import permis

    points = permis(ctx.config, ctx.reg.points_vente_permis(ctx.u))
    code = ctx.req.query.get("pv") or ctx.req.champ("pv")
    choisi = next((p for p in points if str(p.code) == code), points[0] if points else None)
    principal = choisi is None or str(choisi.code) == "1"
    choix = ""
    if len(points) > 1:
        options = "".join(f"<option value='{e(p.code)}'{' selected' if p is choisi else ''}>{e(p.libelle)}</option>"
                          for p in points)
        choix = f"<div><label>Point de vente</label><select name='pv'>{options}</select></div>"
    return (None if principal else choisi), choix, (choisi.code if choisi else "1")


# --------------------------------------------------------------------------------------------- caisse
def _attendus(ctx: Contexte, debut: date, fin: date, pv):
    from .. import caisse as ca
    from ..points_vente import cache_clover, client
    from ..statistiques_clover import lire

    return ca.attendus(lire(client(ctx.racine, pv), debut, fin, cache_clover(ctx.racine, pv)))


def caisse(ctx: Contexte) -> Reponse:
    from .. import caisse as ca

    pv, choix_pv, code_pv = _point_vente(ctx)
    jour = _jour(ctx.req.query.get("jour") or ctx.req.champ("jour"), date.today())
    registre = ca.Registre(ctx.racine, pv)
    message = ""
    if ctx.req.methode == "POST":
        action = "Enregistrer un comptage de caisse"
        if not action_permise(ctx, action):
            message = refus(action)
        else:
            try:
                coupures = {k: int(ctx.req.champ("c" + k).strip()) for k in ca.COUPURES
                            if ctx.req.champ("c" + k).strip()}
                if any(n < 0 for n in coupures.values()):
                    raise ValueError
                compte = ca.total_coupures(coupures)
                fond = Decimal(ctx.req.champ("fond").replace(",", ".").replace("$", "").strip() or 0).quantize(ca.CENT)
                if fond > compte:
                    raise ValueError("Le fond laissé dépasse le montant compté.")
                if registre.comptage(jour) and not ctx.req.champ("remplacer"):
                    raise ValueError(f"Un comptage existe déjà pour le {jour} : cochez « Remplacer le comptage ».")
                with ctx.app.ecriture:
                    ca.Registre(ctx.racine, pv).noter(ca.Comptage(jour.isoformat(), str(compte), str(fond), coupures,
                                                                  ctx.u.nom, remarque=ctx.req.champ("remarque")))
                message = _message(f"Comptage du {jour} enregistré.")
                registre = ca.Registre(ctx.racine, pv)
            except (ValueError, InvalidOperation) as erreur:
                message = _message(erreur=str(erreur) if str(erreur) else "Nombres entiers seulement pour les coupures.")
    c = registre.comptage(jour)
    try:
        a = _attendus(ctx, jour, jour, pv).get(jour) or ca.Attendu(jour)
        fond_matin = ca.fond_du_matin(registre, jour, ctx.config)
        prevu = fond_matin + a.net
        attendu = (f"<div class='cartes'><div class='carte'><div class='t'>Fond du matin</div><div class='v'>"
                   f"{argent(fond_matin)}</div></div><div class='carte'><div class='t'>Ventes en espèces</div>"
                   f"<div class='v'>{argent(a.ventes)}</div><div class='d'>{a.paiements} paiement(s)</div></div>"
                   f"<div class='carte'><div class='t'>Remboursements</div><div class='v'>−{argent(a.remboursements)}"
                   f"</div></div><div class='carte'><div class='t'>Argent remis sur carte</div><div class='v'>"
                   f"−{argent(a.remis)}</div></div><div class='carte'><div class='t'>Attendu dans le tiroir</div>"
                   f"<div class='v'>{argent(prevu)}</div></div></div>")
        if a.par_employe:
            attendu += "<p class='note'>Espèces par employé : " + " ; ".join(
                f"{e(n)} {argent(m)}" for n, m in sorted(a.par_employe.items(), key=lambda x: -x[1])) + "</p>"
        if c:
            ecart = Decimal(c.compte) - prevu
            classe = "ok" if abs(ecart) < Decimal("0.01") else ("erreur" if abs(ecart) > ca.SEUIL_ECART else "")
            attendu += (f"<p class='{classe}'>Compté : {argent(Decimal(c.compte))} · Écart : "
                        f"{'+' if ecart > 0 else ''}{argent(ecart)} · À déposer : {argent(c.a_deposer)} "
                        f"(par {e(c.par)} le {e(c.le[:16].replace('T', ' '))})</p>")
    except (Exception, SystemExit) as erreur:  # noqa: BLE001 — Clover injoignable
        ctx.app.noter(f"Caisse : {erreur!r}")
        attendu = "<p class='erreur'>Clover ne répond pas : l'attendu ne peut pas être calculé.</p>"
    cases = "".join(f"<div><label>{k.replace('.', ',')} $</label><input name='c{k}' inputmode='numeric' size='4' "
                    f"value='{e((c.coupures if c else {}).get(k, ''))}'></div>" for k in ca.COUPURES)
    fond = str(c.fond).replace(".", ",") if c else str(ca.fond_de_caisse(ctx.config)).replace(".", ",")
    from .pages_rapports_web import onglets

    corps = (onglets("Comptage du soir", ctx) + message + f"<form class='ligne' method='get'>{choix_pv}<div><label>Journée</label><input type='date' "
             f"name='jour' value='{jour}'></div><button class='second'>Afficher</button></form>" + attendu
             + f"<form method='post' class='carte'>{csrf(ctx)}<input type='hidden' name='jour' value='{jour}'>"
               f"<input type='hidden' name='pv' value='{e(code_pv)}'><h2>Comptage du soir (nombre de billets et "
               f"pièces)</h2><div class='ligne'>{cases}</div><div class='ligne'><div><label>Fond laissé pour demain"
               f"</label><input name='fond' value='{e(fond)}' size='8'></div><div><label>Remarque</label><input "
               f"name='remarque' value='{e(c.remarque if c else '')}' size='30'></div></div>"
             + ("<p><label><input type='checkbox' name='remplacer' value='1'> Remplacer le comptage déjà enregistré"
                "</label></p>" if c else "")
             + "<div class='boutons'><button name='action' value='Enregistrer'>Enregistrer le comptage</button></div>"
               "</form>")
    return Reponse(corps=page(ctx, "Contrôle de la caisse", corps))


def caisse_ecarts(ctx: Contexte) -> Reponse:
    from .. import caisse as ca

    from .pages_rapports_web import onglets

    pv, choix_pv, _code = _point_vente(ctx)
    vue = "depots" if ctx.req.query.get("vue") == "depots" else "ecarts"
    fin = _jour(ctx.req.query.get("au"), date.today())
    debut = _jour(ctx.req.query.get("du"), fin - timedelta(days=13))
    corps = (onglets("Dépôts d'espèces" if vue == "depots" else "Écarts par jour", ctx)
             + f"<form class='ligne' method='get'><input type='hidden' name='vue' value='{vue}'>{choix_pv}<div><label>Du</label><input type='date' name='du' "
             f"value='{debut}'></div><div><label>Au</label><input type='date' name='au' value='{fin}'></div>"
             "<button class='second'>Afficher</button></form>")
    try:
        attendu = _attendus(ctx, debut, fin, pv)
        lignes = ca.lignes_jours(attendu, ca.Registre(ctx.racine, pv), debut, fin, ctx.config)
        sections = [Section(f"Écarts par jour du {debut} au {fin}", ca.ENTETES_JOURS, list(reversed(lignes)),
                            f"Écart signalé au-delà de {argent(ca.SEUIL_ECART)}.")]
        if pv is None:  # dépôts au guichet des relevés : point de vente n° 1 seulement
            depots = ca.depots_especes(ctx.racine, debut, fin)
            b = ca.bilan_depots(lignes, depots)
            par_jour: dict = {}
            for jour, montant, _r in depots:
                par_jour[jour] = par_jour.get(jour, ca.ZERO) + montant
            a_deposer = {l[0]: l[8] for l in lignes}
            cumul, tableau = ca.ZERO, []
            for j in sorted({l[0] for l in lignes} | set(par_jour)):
                ad = a_deposer.get(j, "")
                dep = par_jour.get(j, ca.ZERO)
                cumul += dep - (ad if isinstance(ad, Decimal) else ca.ZERO)
                tableau.append([j, ad, dep or "", cumul])
            sections.append(Section("Dépôts d'espèces", ["Date", "À déposer", "Déposé au guichet", "Écart cumulé"],
                                    list(reversed(tableau)),
                                    f"À déposer : {argent(b['a_deposer'])} ; déposé : {argent(b['depose'])} ; écart : "
                                    f"{argent(b['ecart'])}" + (f" ; {b['non_comptes']} jour(s) non comptés"
                                                               if b["non_comptes"] else "")))
        if vue == "depots" and pv is not None:
            corps += "<p class='note'>Dépôts d'espèces au guichet : point de vente n° 1 seulement.</p>"
        corps += sections_html(sections[1:] if vue == "depots" else sections[:1])
    except (Exception, SystemExit) as erreur:  # noqa: BLE001
        ctx.app.noter(f"Caisse écarts : {erreur!r}")
        corps += "<p class='erreur'>Clover ne répond pas sur le serveur pour l'instant.</p>"
    return Reponse(corps=page(ctx, "Contrôle de la caisse : écarts", corps))


# --------------------------------------------------------------------------------------------- dépenses
def depenses(ctx: Contexte) -> Reponse:
    from .. import depenses as dp
    from . import taches

    message = ""
    if ctx.req.methode == "POST":
        action = ctx.req.champ("action")
        try:
            if action == "Ajouter":
                montant = Decimal(ctx.req.champ("montant").replace(",", ".").replace("$", "").replace(" ", "") or 0)
                d = dp.Depense("", ctx.req.champ("jour"), ctx.req.champ("fournisseur").strip(),
                               ctx.req.champ("description").strip(), str(montant.quantize(Decimal("0.01"))),
                               ctx.req.champ("taxe"), ctx.req.champ("compte").strip(), ctx.req.champ("moyen"),
                               auteur=ctx.u.nom)
                recu = None
                if "recu" in ctx.req.fichiers:
                    import tempfile
                    from pathlib import Path

                    nom, contenu = ctx.req.fichiers["recu"]
                    dossier = Path(tempfile.mkdtemp())
                    recu = dossier / ("recu" + Path(nom).suffix.lower())
                    recu.write_bytes(contenu)
                with ctx.app.ecriture:
                    d = dp.Registre(ctx.racine).ajouter(d, recu)
                message = _message(f"Dépense {d.numero} ajoutée ({argent(Decimal(d.montant))}).")
            elif action == "Comptes":
                with ctx.app.ecriture:
                    r = dp.Registre(ctx.racine)
                    for cle in dp.COMPTES:
                        valeur = ctx.req.champ("compte_" + cle).strip()
                        if valeur:
                            r.comptes[cle] = valeur
                    r.enregistrer()
                message = _message("Comptes enregistrés.")
            elif action == "Saisir dans Sage":
                nom_action = "Saisir les dépenses dans Sage"
                if not action_permise(ctx, nom_action):
                    raise ValueError(f"Votre profil n'a pas le droit « {nom_action} ».")
                r = dp.Registre(ctx.racine)
                a_faire = [d for d in r.depenses if d.etat == dp.A_SAISIR]
                if not a_faire:
                    raise ValueError("Aucune dépense à saisir dans Sage.")
                manquants = r.comptes_manquants(a_faire)
                if manquants:
                    raise ValueError("Comptes Sage à choisir d'abord : " + ", ".join(manquants))

                def travail(journal):
                    b = taches.executer_sage(ctx.racine, ["depenses-bureau"], journal)
                    return (b.get("saisies", []) + ["✘ " + x for x in b.get("a_verifier", [])]
                            + (["✘ " + b["erreur"]] if b.get("erreur") else [])) or ["Rien n'a été saisi."]

                return taches.lancer(ctx, f"Saisie de {len(a_faire)} dépense(s)", travail, "/depenses", sage=True)
        except (ValueError, InvalidOperation) as erreur:
            message = _message(erreur=str(erreur) or "Montant invalide.")
        except Exception as erreur:  # noqa: BLE001 — plan comptable : compte absent, inactif…
            message = _message(erreur=str(erreur))
    r = dp.Registre(ctx.racine)
    lignes = [[d.numero, d.jour, d.fournisseur, d.description, Decimal(d.montant), d.taxe, d.compte, d.moyen, d.etat,
               d.ecriture or ""] for d in sorted(r.depenses, key=lambda d: d.jour, reverse=True)]
    a_saisir = sum(1 for d in r.depenses if d.etat == dp.A_SAISIR)
    moyens = "".join(f"<option>{e(m)}</option>" for m in dp.MOYENS + [dp.APPRO])
    taxes = "".join(f"<option>{t}</option>" for t in ("GQ", "G", "Q", ""))
    comptes = "".join(f"<div><label>{e(libelle)}</label><input name='compte_{cle}' value='{e(r.comptes.get(cle, ''))}' "
                      "size='6'></div>" for cle, libelle in dp.COMPTES.items())
    corps = (message
             + f"<div class='cartes'><div class='carte'><div class='t'>Solde de la petite caisse</div><div class='v'>"
               f"{argent(r.solde_petite_caisse())}</div></div><div class='carte'><div class='t'>À saisir dans Sage"
               f"</div><div class='v'>{a_saisir}</div></div></div>"
             + f"<form method='post' enctype='multipart/form-data' class='carte'>{csrf(ctx)}<h2>Nouvelle dépense</h2>"
               f"<div class='ligne'><div><label>Date</label><input type='date' name='jour' value='{date.today()}' "
               "required></div><div><label>Fournisseur</label><input name='fournisseur' required></div><div><label>"
               "Description</label><input name='description'></div><div><label>Montant TTC</label><input "
               "name='montant' size='8' required></div><div><label>Taxes</label><select name='taxe'>"
               f"{taxes}</select></div><div><label>Compte de charge</label><input name='compte' size='6' "
               f"placeholder='5450'></div><div><label>Payée par</label><select name='moyen'>{moyens}</select></div>"
               "<div><label>Reçu (photo ou PDF)</label><input type='file' name='recu' accept='image/*,.pdf'></div>"
               "</div><div class='boutons'><button name='action' value='Ajouter'>Ajouter la dépense</button></div>"
               "</form>"
             + f"<form method='post' class='boutons'>{csrf(ctx)}<button name='action' value='Saisir dans Sage'>Saisir "
               f"les {a_saisir} dépense(s) dans Sage</button></form>"
             + sections_html([Section("Dépenses", ["N°", "Date", "Fournisseur", "Description", "Montant", "Taxes",
                                                    "Compte", "Payée par", "État", "Écriture"], lignes)])
             + f"<form method='post' class='carte'>{csrf(ctx)}<h2>Comptes Sage des dépenses</h2>"
               f"<div class='ligne'>{comptes}</div><div class='boutons'><button class='second' name='action' "
               "value='Comptes'>Enregistrer les comptes</button></div></form>")
    return Reponse(corps=page(ctx, "Petite caisse et dépenses", corps))


FONCTIONS = [
    Fonction("/caisse", "Contrôle de la caisse", "paiements", caisse, "💵", "Comptabilité", menu=False),
    Fonction("/caisse-ecarts", "Contrôle de la caisse", "paiements", caisse_ecarts, "💵", "Comptabilité", menu=False),
    Fonction("/depenses", "Petite caisse et dépenses", "paiements", depenses, "🧾", "Comptabilité", menu=False),
]
WEB = {"Contrôle de la caisse": "/caisse", "Petite caisse et dépenses": "/depenses"}
