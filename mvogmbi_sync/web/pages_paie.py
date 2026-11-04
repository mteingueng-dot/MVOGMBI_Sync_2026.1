"""Pages web de la rubrique Paie (1re vague de « toutes les fonctions selon le rôle », demande du propriétaire du
2026-11-03) : planning mensuel, employés et NIP, détail et corrections d'une feuille de temps, jours fériés et
congés, mes paies et bulletins (lus dans Sage).

Mêmes registres que l'application de bureau (paie_temps, planning, conges) et mêmes droits (titre de l'entrée du
menu) ; un profil limité ne voit que l'employé relié à son compte.
"""

from __future__ import annotations

import time
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

from .pages import (JOURS, Contexte, Fonction, _choisir_employe, _reference, argent, csrf, heures,
                    page, sans_employe, tableau)
from .serveur import Reponse, echapper as e, redirection

DUREE_PAIES = 300  # s : paies lues dans Sage gardées 5 min


def _message(ok: str = "", erreur: str = "") -> str:
    return (f"<p class='ok'>{e(ok)}</p>" if ok else "") + (f"<p class='erreur'>{e(erreur)}</p>" if erreur else "")


def _employe_visible(ctx: Contexte, registre, ident: str):
    return next((x for x in ctx.employes_visibles(registre) if x.id == ident), None)


def _date(texte: str) -> date:
    try:
        return date.fromisoformat(texte.strip())
    except ValueError:
        raise ValueError("Date au format AAAA-MM-JJ.") from None


def _decimal(texte: str) -> Decimal:
    try:
        return Decimal((texte or "0").replace(",", ".").strip())
    except InvalidOperation:
        raise ValueError("Nombre invalide.") from None


# --------------------------------------------------------------------------------------------- planning
def planning(ctx: Contexte) -> Reponse:
    """Comme fenetre_planning.FenetrePlanning : ◀ mois ▶ (publié / non publié), grille des employés × jours du mois
    (quart de chaque jour, heures du mois), employés choisis (cases) puis « Horaire des employés choisis » (jours de
    la semaine, période, début, fin, pause non payée, ou repos), « Reprendre le mois précédent », « Publier le mois »."""
    from .. import paie_temps as pt
    from .. import planning as pl
    from ..fenetre_planning import _mois_suivant
    from .consultations import Section, tableau_section

    registre = pt.Registre(ctx.racine)
    employes = ctx.employes_visibles(registre)
    if not employes:
        return Reponse(corps=page(ctx, "Planning mensuel", sans_employe(ctx)))
    mois = ctx.req.query.get("mois") or ctx.req.champ("mois") or f"{date.today():%Y-%m}"
    try:
        premier = date.fromisoformat(mois + "-01")
    except ValueError:
        premier = date.today().replace(day=1)
    mois = f"{premier:%Y-%m}"
    ids = {x.id for x in employes}
    choisis = [i for i in (ctx.req.champs("employe") or [ctx.req.query.get("employe", "")]) if i in ids]
    message = ""
    if ctx.req.methode == "POST":
        action = ctx.req.champ("action")
        try:
            with ctx.app.ecriture:
                plan = pl.Planning(ctx.racine)
                if action == "Publier le mois":
                    plan.publier(mois)
                    message = _message(f"Planning de {mois} publié : chaque employé voit son horaire.")
                elif action == "Reprendre le mois précédent":
                    avant = _mois_suivant(mois, -1)
                    n = plan.copier_mois(avant, mois, sorted(ids))
                    message = _message(f"{n} quart(s) repris de {avant}.")
                else:
                    if not choisis:
                        raise ValueError("Cochez au moins un employé dans la grille.")
                    du, au = _date(ctx.req.champ("du")), _date(ctx.req.champ("au"))
                    if au < du:
                        raise ValueError("La date de fin précède la date de début.")
                    semaine = {int(j) for j in ctx.req.champs("jours")} or set(range(7))
                    jours = [du + timedelta(days=k) for k in range((au - du).days + 1)
                             if (du + timedelta(days=k)).weekday() in semaine]
                    quart = None if action == "Repos" else pl.Quart(ctx.req.champ("debut"), ctx.req.champ("fin"),
                                                                    int(ctx.req.champ("pause") or 0))
                    for ident in choisis:
                        plan.definir(ident, jours, quart)
                    message = _message(f"{len(jours)} jour(s) mis à jour pour {len(choisis)} employé(s).")
        except (ValueError, pl.ErreurPlanning) as erreur:
            message = _message(erreur=str(erreur))
    plan = pl.Planning(ctx.racine)
    jours = pl.jours_du_mois(mois)
    publie = plan.publies.get(mois)
    libelle = f"Planning de {mois}" + (f"  ✔ publié le {publie[:10]}" if publie else "  ● non publié")
    entetes = ["", "Employé"] + [f"{pl.JOURS[j.weekday()]} {j:%d}" for j in jours] + ["Heures"]
    lignes = []
    for x in employes:
        quarts = [plan.quart(mois, x.id, j) for j in jours]
        case = (f"<input type='checkbox' name='employe' value='{e(x.id)}'{' checked' if x.id in choisis else ''} "
                f"aria-label='{e(x.nom)}'>")
        lignes.append([case, x.nom] + [q.texte().replace(" min)", ")") if q else "" for q in quarts]
                      + [f"{plan.heures(mois, x.id):.2f}".replace(".", ",")])
    cases = "".join(f"<label><input type='checkbox' name='jours' value='{k}'> {j}</label> " for k, j in enumerate(JOURS))
    fin_mois = jours[-1]
    barre = (f"<div class='barre-onglet'><a class='ouvrir' href='?mois={_mois_suivant(mois, -1)}'>◀</a><strong "
             f"class='periode'>{e(libelle)}</strong><a class='ouvrir' href='?mois={_mois_suivant(mois, 1)}'>▶</a></div>")
    corps = (message + barre + f"<form method='post'>{csrf(ctx)}<input type='hidden' name='mois' value='{mois}'>"
             "<p class='note'>Cochez un ou plusieurs employés, puis « Horaire des employés choisis » : jours de la "
             "semaine, période, heures de début et de fin, pause non payée, ou repos. « Publier le mois » : chaque "
             "employé voit son horaire (« Paie > Mon horaire » et poste de pointage).</p>"
             + tableau_section(Section(libelle, entetes, lignes, html={0}))
             + "<div class='carte'><h2>🕑 Horaire des employés choisis</h2><div class='ligne'>"
               f"<div><label>Du</label><input type='date' name='du' value='{premier}'></div>"
               f"<div><label>Au</label><input type='date' name='au' value='{fin_mois}'></div>"
               "<div><label>Début</label><input name='debut' placeholder='8:00' size='6'></div>"
               "<div><label>Fin</label><input name='fin' placeholder='16:30' size='6'></div>"
               "<div><label>Pause non payée (min)</label><input name='pause' value='30' size='4'></div></div>"
               f"<p class='note'>Jours de la semaine (aucun coché = tous) : {cases}</p><div class='boutons'><button "
               "name='action' value='Définir'>Enregistrer l'horaire</button><button class='second' name='action' "
               "value='Repos'>Mettre en repos</button></div></div><div class='boutons'><button class='second' "
               "name='action' value='Reprendre le mois précédent'>📋 Reprendre le mois précédent</button><button "
               "name='action' value='Publier le mois'>📣 Publier le mois</button></div></form>")
    return Reponse(corps=page(ctx, "Planning mensuel", corps))


# --------------------------------------------------------------------------------------------- employés et NIP
def employes(ctx: Contexte) -> Reponse:
    from .. import paie_temps as pt

    message = ""
    if ctx.req.methode == "POST" and ctx.req.champ("action") == "Ajouter":
        try:
            with ctx.app.ecriture:
                registre = pt.Registre(ctx.racine)
                nouveau = registre.ajouter(ctx.req.champ("nom"))
                registre.enregistrer()
            return redirection(f"/employe?id={nouveau.id}")
        except pt.ErreurPointage as erreur:
            message = _message(erreur=str(erreur))
    registre = pt.Registre(ctx.racine)
    visibles = ctx.employes_visibles(registre) if not ctx.voit_tous() else sorted(
        registre.employes, key=lambda x: (not x.actif, x.nom.casefold()))
    lignes = [[f"<a href='/employe?id={e(x.id)}'>{e(x.nom)}</a>", "Actif" if x.actif else "Inactif",
               "Oui" if x.nip else "<span class='erreur'>À créer</span>", e(x.compte or "—"),
               e(x.courriel or "—"), e(x.numero_sage or "—")] for x in visibles]
    corps = (message + tableau(["Employé", "État", "NIP", "Compte relié", "Courriel", "Employé Sage"], lignes)
             + (f"<form method='post' class='ligne'>{csrf(ctx)}<div><label for='nom'>Nouvel employé</label>"
                "<input id='nom' name='nom' required></div><button name='action' value='Ajouter'>Ajouter</button>"
                "</form><p class='note'>Ajouté ici dans l'application seulement ; la création dans Clover et dans "
                "Sage Paie se fait dans l'application Windows (« Paie > Employés et NIP » > « Ajouter »).</p>"
                if ctx.voit_tous() else ""))
    return Reponse(corps=page(ctx, "Employés et NIP", corps))


def fiche_employe(ctx: Contexte) -> Reponse:
    from .. import conges as co
    from .. import paie_temps as pt

    registre = pt.Registre(ctx.racine)
    employe = _employe_visible(ctx, registre, ctx.req.query.get("id") or ctx.req.champ("id"))
    if employe is None:
        return Reponse(404, page(ctx, "Employé", "<p>Employé introuvable.</p>"))
    message = ""
    if ctx.req.methode == "POST":
        action = ctx.req.champ("action")
        try:
            with ctx.app.ecriture:
                registre = pt.Registre(ctx.racine)
                x = registre.employe(employe.id)
                if action == "Renommer":
                    registre.renommer(x.id, ctx.req.champ("nom"))
                elif action == "Changer le NIP":
                    registre.definir_nip(x.id, ctx.req.champ("nip"))
                elif action == "Relier":
                    compte = ctx.req.champ("compte")
                    if compte and ctx.reg.trouver(compte) is None:
                        raise ValueError("Compte inconnu.")
                    x.compte = compte
                elif action == "Courriel":
                    courriel = ctx.req.champ("courriel").strip()
                    if courriel and ("@" not in courriel or " " in courriel):
                        raise ValueError("Adresse de courriel invalide.")
                    x.courriel = courriel
                elif action in ("Désactiver", "Réactiver"):
                    x.actif = action == "Réactiver"
                elif action == "Date d'embauche":
                    conges = co.Registre(ctx.racine)
                    conges.embauches[x.id] = _date(ctx.req.champ("embauche")).isoformat()
                    conges.enregistrer()
                registre.enregistrer()
                employe = x
            message = _message("Enregistré.")
        except (ValueError, pt.ErreurPointage) as erreur:
            message = _message(erreur=str(erreur))
    embauche = co.Registre(ctx.racine).embauches.get(employe.id, "")
    comptes = "<option value=''>— aucun —</option>" + "".join(
        f"<option{' selected' if u.nom == employe.compte else ''}>{e(u.nom)}</option>" for u in ctx.reg.utilisateurs)

    def forme(contenu: str, action: str, classe: str = "") -> str:
        return (f"<form method='post' class='ligne'>{csrf(ctx)}<input type='hidden' name='id' value='{e(employe.id)}'>"
                f"{contenu}<button class='{classe}' name='action' value='{e(action)}'>{e(action)}</button></form>")

    corps = (message + f"<p><a href='/employes'>◀ Employés</a></p>"
             + forme(f"<div><label>Nom</label><input name='nom' value='{e(employe.nom)}' required></div>", "Renommer")
             + forme("<div><label>Nouveau NIP (4 à 6 chiffres)</label><input name='nip' type='password' "
                     "inputmode='numeric' pattern='[0-9]{4,6}' autocomplete='off' required></div>", "Changer le NIP")
             + forme(f"<div><label>Compte de l'application relié</label><select name='compte'>{comptes}</select></div>",
                     "Relier")
             + forme(f"<div><label>Courriel (bulletins de paie)</label><input name='courriel' type='email' "
                     f"value='{e(employe.courriel)}'></div>", "Courriel")
             + forme(f"<div><label>Date d'embauche</label><input name='embauche' type='date' value='{e(embauche)}' "
                     "required></div>", "Date d'embauche")
             + forme(f"<p>État : <strong>{'Actif' if employe.actif else 'Inactif'}</strong></p>",
                     "Désactiver" if employe.actif else "Réactiver", "second"))
    return Reponse(corps=page(ctx, employe.nom, corps))


# --------------------------------------------------------------------------------------------- feuille de temps
def feuille_detail(ctx: Contexte) -> Reponse:
    from .. import paie_temps as pt

    registre = pt.Registre(ctx.racine)
    employe = _employe_visible(ctx, registre, ctx.req.query.get("employe") or ctx.req.champ("employe"))
    if employe is None:
        return Reponse(404, page(ctx, "Feuille de temps", "<p>Employé introuvable.</p>"))
    try:
        debut = pt.debut_periode(_date(ctx.req.query.get("debut") or ctx.req.champ("debut")), _reference(ctx.racine))
    except ValueError:
        debut = pt.debut_periode(date.today(), _reference(ctx.racine))
    message = ""
    if ctx.req.methode == "POST":
        motif = ctx.req.champ("motif")
        try:
            with ctx.app.ecriture:
                registre = pt.Registre(ctx.racine)
                if ctx.req.champ("action") == "Annuler":
                    ident = ctx.req.champ("pointage")
                    if not any(p.id == ident and p.employe == employe.id for p in registre.pointages):
                        raise ValueError("Pointage introuvable.")
                    registre.annuler(ident, ctx.u.nom, motif)
                    message = _message("Pointage annulé.")
                else:
                    moment = datetime.fromisoformat(f"{_date(ctx.req.champ('jour'))}T{ctx.req.champ('heure')}")
                    registre.corriger(employe.id, ctx.req.champ("type"), moment, ctx.u.nom, motif)
                    message = _message("Pointage ajouté.")
        except (ValueError, pt.ErreurPointage) as erreur:
            message = _message(erreur=str(erreur))
    fin = debut + timedelta(days=pt.JOURS_PERIODE)
    f = pt.feuille(registre, employe, debut)
    lignes = []
    for p in registre.valides(employe.id):
        if not debut.isoformat() <= p.moment[:10] < fin.isoformat():
            continue
        annuler = (f"<form method='post' class='ligne'>{csrf(ctx)}<input type='hidden' name='employe' "
                   f"value='{e(employe.id)}'><input type='hidden' name='debut' value='{debut}'><input type='hidden' "
                   f"name='pointage' value='{e(p.id)}'><input name='motif' placeholder='Motif' required size='12'>"
                   "<button class='second' name='action' value='Annuler'>Annuler</button></form>")
        lignes.append([f"{JOURS[p.quand.weekday()]} {p.quand:%d/%m %H:%M}", e(p.type),
                       e(p.source + (f" ({p.auteur} : {p.motif})" if p.source == "Correction" else "")), annuler])
    types = "".join(f"<option>{e(t)}</option>" for t in pt.TYPES)
    corps = (message + f"<p><a href='/feuilles?debut={debut}'>◀ Feuilles de temps</a></p>"
             f"<h2>Du {debut:%d/%m} au {(fin - timedelta(days=1)):%d/%m/%Y} · normales {heures(f.normales)} h · "
             f"supp. {heures(f.supplementaires)} h · <span class='etat'>{e(f.etat)}</span></h2>"
             + ("<ul>" + "".join(f"<li class='erreur'>{e(a)}</li>" for a in f.anomalies) + "</ul>" if f.anomalies else "")
             + tableau(["Moment", "Pointage", "Source", ""], lignes)
             + f"<form method='post' class='carte'>{csrf(ctx)}<input type='hidden' name='employe' value='{e(employe.id)}'>"
               f"<input type='hidden' name='debut' value='{debut}'><h2>Ajouter un pointage</h2><div class='ligne'>"
               f"<div><label>Type</label><select name='type'>{types}</select></div>"
               f"<div><label>Jour</label><input type='date' name='jour' value='{debut}' required></div>"
               "<div><label>Heure</label><input type='time' name='heure' required></div>"
               "<div><label>Motif</label><input name='motif' required></div></div><div class='boutons'>"
               "<button name='action' value='Ajouter'>Ajouter le pointage</button></div></form>"
               "<p class='note'>Une correction ne remplace jamais un pointage : elle s'ajoute, avec votre nom et le "
               "motif ; une feuille corrigée revient « À approuver ».</p>")
    return Reponse(corps=page(ctx, f"Feuille de {employe.nom}", corps))


# --------------------------------------------------------------------------------------------- congés
def conges(ctx: Contexte) -> Reponse:
    from .. import conges as co
    from .. import paie_temps as pt
    from .. import planning as pl

    registre = pt.Registre(ctx.racine)
    visibles = ctx.employes_visibles(registre)
    noms = {x.id: x.nom for x in registre.employes}
    message = ""
    if ctx.req.methode == "POST":
        try:
            with ctx.app.ecriture:
                reg_conges = co.Registre(ctx.racine)
                if ctx.req.champ("action") == "Supprimer":
                    ident = ctx.req.champ("conge")
                    if not any(c.id == ident and c.employe in {x.id for x in visibles} for c in reg_conges.conges):
                        raise ValueError("Congé introuvable.")
                    reg_conges.supprimer(ident)
                    message = _message("Congé supprimé.")
                else:
                    employe = _employe_visible(ctx, registre, ctx.req.champ("employe"))
                    if employe is None:
                        raise ValueError("Choisissez l'employé.")
                    plan = pl.Planning(ctx.racine)
                    travailles = ((lambda j: plan.quart(f"{j:%Y-%m}", employe.id, j) is not None)
                                  if ctx.req.champ("planifies") else None)
                    ajoutes = reg_conges.ajouter(employe.id, _date(ctx.req.champ("du")), _date(ctx.req.champ("au")),
                                                 ctx.req.champ("type"), _decimal(ctx.req.champ("heures")), ctx.u.nom,
                                                 ctx.req.champ("remarque"), jours_travailles=travailles)
                    message = _message(f"{len(ajoutes)} jour(s) de congé ajouté(s).")
        except ValueError as erreur:
            message = _message(erreur=str(erreur))
    annee = date.today().year
    reg_conges = co.Registre(ctx.racine)
    feries = []
    for jour, nom in co.jours_feries(annee, reg_conges.paques):
        passe = jour <= date.today()
        indemnites = " ; ".join(f"{e(x.nom)} : {heures(co.indemnite_heures(registre, x, jour))} h" for x in visibles
                                ) if passe else ""
        feries.append([f"{jour:%d/%m/%Y}", e(nom), "Passé" if passe else "À venir", indemnites])
    ids = {x.id for x in visibles}
    lignes = []
    for c in sorted((c for c in reg_conges.conges if c.employe in ids and c.jour[:4] == str(annee)),
                    key=lambda c: c.jour, reverse=True):
        supprimer = (f"<form method='post'>{csrf(ctx)}<input type='hidden' name='conge' value='{e(c.id)}'>"
                     "<button class='second' name='action' value='Supprimer'>Supprimer</button></form>")
        lignes.append([e(c.jour), e(noms.get(c.employe, c.employe)), e(c.type), heures(Decimal(c.heures)),
                       e(c.remarque), supprimer])
    soldes = []
    for x in visibles:
        s = co.solde(reg_conges, x, date.today())
        soldes.append([e(x.nom), e(s.service), f"{s.vacances_semaines} sem. ({e(s.vacances_taux)})",
                       str(s.vacances_prises), f"{s.maladie_payes_pris} / {s.maladie_payes_dus}", str(s.maladie_pris),
                       e(" ; ".join(s.remarques))])
    options = "".join(f"<option value='{e(x.id)}'>{e(x.nom)}</option>" for x in visibles)
    types = "".join(f"<option>{e(t)}</option>" for t in co.TYPES)
    forme = (f"<form method='post' class='carte'>{csrf(ctx)}<h2>Ajouter un congé</h2><div class='ligne'>"
             f"<div><label>Employé</label><select name='employe'>{options}</select></div>"
             f"<div><label>Type</label><select name='type'>{types}</select></div>"
             f"<div><label>Du</label><input type='date' name='du' required></div>"
             f"<div><label>Au</label><input type='date' name='au' required></div>"
             "<div><label>Heures payées / jour</label><input name='heures' value='8' size='4'></div>"
             "<div><label>Remarque</label><input name='remarque'></div></div>"
             "<p><label><input type='checkbox' name='planifies' value='1' checked> Seulement les jours planifiés</label>"
             "</p><div class='boutons'><button name='action' value='Ajouter'>Ajouter le congé</button></div></form>")
    corps = (message + forme + f"<h2>Congés {annee}</h2>"
             + tableau(["Jour", "Employé", "Type", "Heures", "Remarque", ""], lignes, {3})
             + "<h2>Soldes</h2>" + tableau(["Employé", "Service", "Vacances dues", "Vacances prises",
                                             "Maladie payée (prise / due)", "Absences maladie", "Remarques"], soldes)
             + f"<h2>Jours fériés {annee}</h2>" + tableau(["Date", "Jour férié", "État", "Indemnité"], feries))
    return Reponse(corps=page(ctx, "Jours fériés et congés", corps))


# --------------------------------------------------------------------------------------------- mes paies
def _paies_annee(ctx: Contexte, annee: int):
    """Paies de Sage de l'année (jusqu'à aujourd'hui), gardées DUREE_PAIES secondes ; Sage n'est jamais ouvert par
    une page web (lecture par la base, ou par l'outil d'import si Sage est fermé)."""
    from .. import paie as pa
    from ..__main__ import lire_sage

    cle = ("paies", annee)
    gardee = ctx.app.memoire.get(cle)
    if gardee and time.time() - gardee[0] < DUREE_PAIES:
        return gardee[1]
    fin = min(date(annee, 12, 31), date.today())
    paies = lire_sage(ctx.config, lambda b: pa.paies_sage(b, date(annee, 1, 1), fin), ouvrir=False)
    ctx.app.memoire[cle] = (time.time(), paies)
    return paies


def _paies_permises(ctx: Contexte, registre, employe) -> bool:
    """Chacun voit ses paies ; celles d'un autre employé : droit « Traitement de la paie » seulement."""
    from .pages import permis

    moi = ctx.employe(registre)
    return (moi is not None and moi.id == employe.id) or permis(ctx.reg, ctx.u, TRAITEMENT_PAIE)


def _paies_de(ctx: Contexte, registre, employe, annee: int) -> list:
    from .. import paie as pa

    if not _paies_permises(ctx, registre, employe):
        raise PermissionError("Paies d'un autre employé : droit « Traitement de la paie » requis.")
    return [p for p in _paies_annee(ctx, annee)
            if (x := pa.employe_de(p, registre.employes)) is not None and x.id == employe.id]


def mes_paies(ctx: Contexte) -> Reponse:
    from .. import paie_temps as pt

    registre = pt.Registre(ctx.racine)
    employe, choix = _choisir_employe(ctx, registre)
    if employe is None:
        return Reponse(corps=page(ctx, "Mes paies", sans_employe(ctx)))
    try:
        annee = int(ctx.req.query.get("annee") or date.today().year)
    except ValueError:
        annee = date.today().year
    try:
        paies = _paies_de(ctx, registre, employe, annee)
    except PermissionError as erreur:
        return Reponse(403, page(ctx, "Mes paies", choix + f"<p class='erreur'>{e(erreur)}</p>"))
    except (Exception, SystemExit) as erreur:  # noqa: BLE001 — Sage absent ou fermé : message clair
        ctx.app.noter(f"Paies Sage : {erreur!r}")
        return Reponse(corps=page(ctx, "Mes paies", choix + "<p class='erreur'>Les paies se lisent dans Sage, qui ne "
                                                            "répond pas sur le serveur pour l'instant.</p>"))
    lignes = [[f"<a href='/bulletin?employe={e(employe.id)}&annee={annee}&paie={p.ident}'>{p.jour:%d/%m/%Y}</a>",
               argent(p.brut), argent(p.total_retenues), argent(p.net)] for p in sorted(paies, key=lambda p: p.jour,
                                                                                      reverse=True)]
    annees = " ".join(f"<a href='?employe={e(employe.id)}&annee={a}'>{a}</a>" for a in (annee - 1, annee + 1)
                      if a <= date.today().year)
    corps = (choix + f"<p class='note'>Autres années : {annees}</p><h2>Paies {annee}</h2>"
             + (tableau(["Paie du", "Brut", "Retenues", "Net"], lignes, {1, 2, 3}) if lignes
                else "<p>Aucune paie dans Sage pour cette année.</p>")
             + "<p class='note'>Cliquez sur une date pour le bulletin de paie (imprimable depuis le navigateur).</p>")
    return Reponse(corps=page(ctx, f"Paies de {employe.nom}" if ctx.voit_tous() else "Mes paies", corps))


def bulletin(ctx: Contexte) -> Reponse:
    from .. import paie_temps as pt

    registre = pt.Registre(ctx.racine)
    employe = _employe_visible(ctx, registre, ctx.req.query.get("employe", ""))
    if employe is None:
        return Reponse(404, page(ctx, "Bulletin de paie", "<p>Employé introuvable.</p>"))
    try:
        annee = int(ctx.req.query.get("annee", ""))
        paies = _paies_de(ctx, registre, employe, annee)
        paie = next(p for p in paies if str(p.ident) == ctx.req.query.get("paie"))
    except PermissionError as erreur:
        return Reponse(403, page(ctx, "Bulletin de paie", f"<p class='erreur'>{e(erreur)}</p>"))
    except (ValueError, StopIteration):
        return Reponse(404, page(ctx, "Bulletin de paie", "<p>Paie introuvable.</p>"))
    return Reponse(corps=fiche_html(ctx, registre, employe, paie, paies), style_en_ligne=True)


def fiche_html(ctx: Contexte, registre, employe, paie, paies) -> str:
    """Fiche de paie (comme FenetrePaie._fiche) : heures de la feuille de la période payée, montants de Sage."""
    from .. import paie as pa
    from .. import paie_temps as pt
    from ..calendrier_paie import Calendrier

    feuille = pa.feuille_de_la_paie(registre, employe, paie.jour, _reference(ctx.racine)) if employe else None
    prevue = next((p for p in Calendrier(ctx.racine).paies(paie.jour.year) if p.jour == paie.jour), None)
    if employe and prevue:
        feuille = pt.feuille(registre, employe, prevue.debut)
        feuille = feuille if feuille.total else None
    extras = (pa.ZERO, pa.ZERO)
    if feuille is not None:
        extras = pa.extras_periode(ctx.racine, [feuille]).get(employe.id, extras)
    periode = f"{prevue.debut:%Y-%m-%d} à {prevue.fin:%Y-%m-%d}" if prevue else ""
    return pa.fiche_de_paie(paie, pa.cumul_annee(paies, paie), feuille, extras, periode)


TRAITEMENT_PAIE = Fonction("", "Traitement de la paie", "rapprochement", None, "", "", menu=False)

FONCTIONS = [
    Fonction("/planning", "Planning mensuel", "paiements", planning, "📅", "Paie"),
    Fonction("/employes", "Employés et NIP", "paiements", employes, "👥", "Paie"),
    Fonction("/employe", "Employés et NIP", "paiements", fiche_employe, "👥", "Paie", menu=False),
    Fonction("/feuille", "Feuilles de temps", "paiements", feuille_detail, "🗂", "Paie", menu=False),
    Fonction("/conges", "Jours fériés et congés", "paiements", conges, "🏖", "Paie"),
    Fonction("/paies", "Mes heures et mes paies", "accueil", mes_paies, "💵", "Paie", toujours=True, menu=False),
    Fonction("/bulletin", "Mes heures et mes paies", "accueil", bulletin, "💵", "Paie", toujours=True, menu=False),
]
