"""4e vague de l'application web : rubrique Comptabilité, saisies (demande du propriétaire du 2026-11-03 : « lance
toutes les vagues à la suite »). Contrôle de la caisse (comptage du soir, écarts par jour, dépôts d'espèces), petite
caisse et dépenses (saisie, reçu joint, comptes, saisie dans Sage). Mêmes règles et mêmes droits par action que les
fenêtres Windows (fenetre_caisse, fenetres_gestion2).
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .consultations import Section, sections_html, tableau_section
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
    if points:  # toujours affiché, comme ChoixPointVente de Windows (même avec un seul point de vente)
        options = "".join(f"<option value='{e(p.code)}'{' selected' if p is choisi else ''}>{e(p.libelle)}</option>"
                          for p in points)
        choix = f"<div><label>Point de vente :</label><select name='pv'>{options}</select></div>"
    return (None if principal else choisi), choix, (choisi.code if choisi else "1")


# --------------------------------------------------------------------------------------------- caisse
def _attendus(ctx: Contexte, debut: date, fin: date, pv):
    from .. import caisse as ca
    from ..points_vente import cache_clover, client
    from ..statistiques_clover import lire

    return ca.attendus(lire(client(ctx.racine, pv), debut, fin, cache_clover(ctx.racine, pv)))


def caisse(ctx: Contexte) -> Reponse:
    """Comme fenetre_caisse.FenetreCaisse, onglet « Comptage du soir » : point de vente au-dessus des onglets ;
    « Journée » + « 🔄 Actualiser » ; à gauche le cadre « Espèces attendues (Clover) » (texte de `calculer`), à droite
    « Comptage du tiroir » (coupures sur 2 colonnes, fond laissé pour demain, remarque, Compté / Écart / À déposer en
    couleur, « ✔ Enregistrer le comptage ») ; ligne d'état en bas."""
    from .. import caisse as ca
    from .pages_rapports_web import onglets

    pv, choix_pv, code_pv = _point_vente(ctx)
    jour = _jour(ctx.req.query.get("jour") or ctx.req.champ("jour"), date.today())
    registre = ca.Registre(ctx.racine, pv)
    message = ""
    saisi = None  # coupures tapées (après un refus, elles restent dans les champs)
    if ctx.req.methode == "POST":
        saisi = {k: ctx.req.champ("c" + k).strip() for k in ca.COUPURES}
        action = "Enregistrer un comptage de caisse"
        if not action_permise(ctx, action):
            message = refus(action)
        else:
            try:
                coupures = {k: int(v) for k, v in saisi.items() if v}
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
                saisi = None
            except (ValueError, InvalidOperation) as erreur:
                message = _message(erreur=str(erreur) if str(erreur) else "Nombres entiers seulement pour les coupures.")
    c = registre.comptage(jour)
    valeurs = saisi if saisi is not None else {k: str((c.coupures if c else {}).get(k, "")) for k in ca.COUPURES}
    fond_texte = (ctx.req.champ("fond") if saisi is not None else
                  str(c.fond if c else ca.fond_de_caisse(ctx.config))).replace(".", ",")
    remarque = ctx.req.champ("remarque") if saisi is not None else (c.remarque if c else "")
    try:
        a = _attendus(ctx, jour, jour, pv).get(jour) or ca.Attendu(jour)
    except (Exception, SystemExit) as erreur:  # noqa: BLE001 — Clover injoignable : attendu à zéro, signalé
        ctx.app.noter(f"Caisse : {erreur!r}")
        ctx.absents.add("Clover")
        a = ca.Attendu(jour)
    fond_matin = ca.fond_du_matin(registre, jour, ctx.config)
    prevu = fond_matin + a.net
    lignes = [f"Fond du matin : {argent(fond_matin)}", f"Ventes en espèces : {argent(a.ventes)} ({a.paiements} "
              "paiements)", f"Remboursements en espèces : −{argent(a.remboursements)}",
              f"Argent remis sur carte : −{argent(a.remis)}", "", f"Attendu dans le tiroir : {argent(prevu)}", ""]
    if a.par_employe:
        lignes.append("Espèces encaissées par employé :")
        lignes += [f"   • {n} : {argent(m)}" for n, m in sorted(a.par_employe.items(), key=lambda x: -x[1])]
    try:  # Compté / Écart / À déposer, comme FenetreCaisse.calculer
        compte = ca.total_coupures({k: v for k, v in valeurs.items() if v})
        fond = Decimal(fond_texte.replace(",", ".").replace("$", "").strip() or 0)
        ecart = compte - prevu
        classe = ("resultat-vert" if abs(ecart) < Decimal("0.01") else
                  "resultat-rouge" if abs(ecart) > ca.SEUIL_ECART else "resultat-jaune")
        resultat = (f"<div class='{classe}'>Compté : {argent(compte)}   Écart : {'+' if ecart > 0 else ''}"
                    f"{argent(ecart)}\nÀ déposer : {argent(compte - fond)}</div>")
    except (Exception, ValueError) as erreur:  # noqa: BLE001
        resultat = f"<div class='resultat-rouge'>✘ {e(str(erreur))}</div>"
    cases = ""
    for rang in range(5):  # 2 colonnes : 100 … 5 $ puis 2 $ … 0,05 $
        for k in (ca.COUPURES[rang], ca.COUPURES[rang + 5]):
            libelle = f"{Decimal(k):.2f} $".replace(".", ",") if Decimal(k) < 1 else f"{k} $"
            cases += (f"<label for='c{k}'>{libelle}</label><input id='c{k}' name='c{k}' inputmode='numeric' size='6' "
                      f"value='{e(valeurs.get(k, ''))}'>")
    etat = (f"Comptage déjà enregistré par {c.par} le {c.le[:16].replace('T', ' ')}." if c else
            "Comptez le tiroir à la fermeture, puis « Enregistrer le comptage ».")
    corps = (f"<form class='barre-onglet' method='get'>{choix_pv}<input type='hidden' name='jour' value='{jour}'>"
             "<button class='second'>Afficher</button></form>" if choix_pv else "")
    corps += (message + onglets("Comptage du soir", ctx) + "<div class='onglet-corps'>"
              f"<form class='barre-onglet' method='get'><input type='hidden' name='pv' value='{e(code_pv)}'><div>"
              f"<label>Journée</label><input type='date' name='jour' value='{jour}'></div><button>🔄 Actualiser</button>"
              "</form><div class='colonnes'><fieldset class='groupe'><legend>Espèces attendues (Clover)</legend>"
              f"<div class='texte-fixe'>{e(chr(10).join(lignes))}</div></fieldset>"
              f"<form method='post'>{csrf(ctx)}<input type='hidden' name='jour' value='{jour}'><input type='hidden' "
              f"name='pv' value='{e(code_pv)}'><fieldset class='groupe'><legend>Comptage du tiroir</legend>"
              f"<div class='grille-coupures'>{cases}</div><div class='grille-champs'><label>Fond laissé pour demain"
              f"</label><input name='fond' value='{e(fond_texte)}' size='10'><label>Remarque</label><input "
              f"name='remarque' value='{e(remarque)}' size='30'></div>{resultat}"
              + ("<p><label><input type='checkbox' name='remplacer' value='1'> Remplacer le comptage déjà enregistré"
                 "</label></p>" if c else "")
              + "<button name='action' value='Enregistrer'>✔ Enregistrer le comptage</button></fieldset></form></div>"
              f"<div class='ligne-etat'>{e(etat)}</div></div>")
    return Reponse(corps=page(ctx, "Contrôle de la caisse", corps))


def caisse_ecarts(ctx: Contexte) -> Reponse:
    from .. import caisse as ca

    from .pages_rapports_web import onglets

    pv, choix_pv, _code = _point_vente(ctx)
    vue = "depots" if ctx.req.query.get("vue") == "depots" else "ecarts"
    fin = _jour(ctx.req.query.get("au"), date.today())
    debut = _jour(ctx.req.query.get("du"), fin - timedelta(days=13))
    corps = (onglets("Dépôts d'espèces" if vue == "depots" else "Écarts par jour", ctx)
             + "<div class='onglet-corps'>"
             + f"<form class='barre-onglet' method='get'><input type='hidden' name='vue' value='{vue}'>{choix_pv}<div>"
               f"<label>Du</label><input type='date' name='du' value='{debut}'></div><div><label>au</label><input "
               f"type='date' name='au' value='{fin}'></div><button>🔍 Afficher</button></form>")
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
    return Reponse(corps=page(ctx, "Contrôle de la caisse", corps + "</div>"))


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
    liste = sorted(r.depenses, key=lambda d: (d.jour, d.numero), reverse=True)
    choisi = ctx.req.query.get("numero", "")
    if ctx.req.query.get("op") == "recu":  # « 👁 Voir le reçu » de la dépense cochée
        d = next((x for x in liste if x.numero == choisi), None)
        chemin = (ctx.racine / "donnees" / "recus" / Path(d.recu).name) if d is not None and d.recu else None
        if chemin is not None and chemin.exists():
            types = {".pdf": "application/pdf", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}
            return Reponse(corps=chemin.read_bytes(), type=types.get(chemin.suffix.lower(), "application/octet-stream"),
                           entetes={"Content-Disposition": "inline"})
        message += _message(erreur="Choisissez une dépense qui a un reçu.")
    from ..taxes import CHOIX

    lignes = [[f"<input type='radio' name='numero' value='{e(d.numero)}'{' checked' if d.numero == choisi else ''}>",
               e(d.jour), e(d.numero), e(d.fournisseur), e(d.description), argent(Decimal(d.montant)), e(d.taxe or "—"),
               e(d.compte), e(d.moyen), "📎" if d.recu else "", e(d.etat + (f" n° {d.ecriture}" if d.ecriture else ""))]
              for d in liste]
    manquants = r.comptes_manquants([d for d in r.depenses if d.etat == dp.A_SAISIR])
    etat = f"Solde de la petite caisse : {argent(r.solde_petite_caisse())}" + (
        " — ⚠ Comptes Sage à choisir : " + ", ".join(manquants) if manquants else "")
    moyens = "".join(f"<option>{e(m)}</option>" for m in dp.MOYENS + [dp.APPRO])
    taxes = "".join(f"<option value='{k}'{' selected' if k == 'GQ' else ''}>{e(v)}</option>" for k, v in CHOIX.items())
    comptes = "".join(f"<div><label>{e(libelle)}</label><input name='compte_{cle}' value='{e(r.comptes.get(cle, ''))}' "
                      "size='6'></div>" for cle, libelle in dp.COMPTES.items())
    corps = (message
             + f"<form method='post' enctype='multipart/form-data'>{csrf(ctx)}<div class='barre-onglet'>"
               f"<div><label>Date</label><input type='date' name='jour' value='{date.today()}' required></div>"
               "<div><label>Fournisseur</label><input name='fournisseur' size='18' required></div><div><label>"
               "Description</label><input name='description' size='22'></div><div><label>Montant payé (taxes "
               "comprises)</label><input name='montant' size='9' required></div><div><label>Compte de charge</label>"
               f"<input name='compte' size='6'></div><div><label>Taxes</label><select name='taxe'>{taxes}</select></div>"
               f"<div><label>Payée par</label><select name='moyen'>{moyens}</select></div><div><label>📎 Reçu…</label>"
               "<input type='file' name='recu' accept='image/*,.pdf'></div><button name='action' value='Ajouter'>➕ "
               "Ajouter</button></div></form>"
             + f"<form method='post'>{csrf(ctx)}<div class='barre-onglet'><button name='action' value='Saisir dans "
               "Sage'>🧾 Saisir dans Sage</button><a class='ouvrir' href='/depenses?op=comptes'>🔢 Comptes Sage…</a>"
               "<button class='second' formmethod='get' name='op' value='recu' form='liste-depenses'>👁 Voir le reçu"
               f"</button></div></form><p class='{'erreur-texte' if manquants else 'note'}'>{e(etat)}</p>"
             + "<form method='get' id='liste-depenses'>"
             + tableau_section(Section("Dépenses", ["", "Date", "N°", "Fournisseur", "Description", "Montant", "Taxes",
                                                   "Compte", "Payée par", "Reçu", "État"], lignes, html=set(range(11))))
             + "</form>"
             + (f"<form method='post' class='carte'>{csrf(ctx)}<h2>Comptes Sage des dépenses</h2>"
                f"<div class='ligne'>{comptes}</div><div class='boutons'><button name='action' value='Comptes'>"
                "✔ Enregistrer les comptes</button></div></form>" if ctx.req.query.get("op") == "comptes"
                else ""))
    return Reponse(corps=page(ctx, "Petite caisse et dépenses", corps))


FONCTIONS = [
    Fonction("/caisse", "Contrôle de la caisse", "paiements", caisse, "💵", "Comptabilité", menu=False),
    Fonction("/caisse-ecarts", "Contrôle de la caisse", "paiements", caisse_ecarts, "💵", "Comptabilité", menu=False),
    Fonction("/depenses", "Petite caisse et dépenses", "paiements", depenses, "🧾", "Comptabilité", menu=False),
]
WEB = {"Contrôle de la caisse": "/caisse", "Petite caisse et dépenses": "/depenses"}
