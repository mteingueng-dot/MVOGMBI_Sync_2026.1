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
from .consultations import Section, tableau_section
from .pages_compta import action_permise
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
    from .consultations import lire_ou_vide, Section, tableau_section

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
BOUTONS_EMPLOYES = [("importer", "⬇ Importer les employés de Clover"), ("ajouter", "➕ Ajouter"),
                    ("modifier", "✎ Modifier"), ("supprimer", "🗑 Supprimer"), ("nip", "🔑 Définir le NIP"),
                    ("relier", "🔗 Relier à un compte…"), ("sage", "🔗 Lier aux employés Sage…"),
                    ("courriel", "✉ Courriel…"), ("adresse", "🏠 Adresse…"), ("basculer", "⏻ Activer / désactiver")]


def employes(ctx: Contexte) -> Reponse:
    """Comme fenetre_feuilles_temps.FenetreEmployes : barre de boutons, ligne d'explication, tableau Employé / NIP /
    Actif / Employé Clover / Employé Sage / Courriel / Compte de l'application ; l'action choisie s'ouvre sous la liste
    (à la place des petites fenêtres de saisie de Windows)."""
    from .. import paie_temps as pt
    from ..courriel import adresses_invalides
    from . import taches

    registre = pt.Registre(ctx.racine)
    choisi = ctx.req.query.get("id") or ctx.req.champ("id")
    op = ctx.req.query.get("op") or ""
    message = ""
    if ctx.req.methode == "POST":
        action = ctx.req.champ("action")
        if not ctx.voit_tous():
            message = _message(erreur="Votre profil ne permet pas de modifier les employés.")
        elif action == "importer":
            def importer(journal):
                from ..points_vente import client

                with ctx.app.ecriture:
                    reg = pt.Registre(ctx.racine)
                    n = reg.importer_clover(list(client(ctx.racine)._pages("employees", {})))
                    reg.enregistrer()
                return [f"{n} employé(s) ajouté(s) depuis Clover. Définissez leur NIP."]

            return taches.lancer(ctx, "Employés de Clover", importer, "/employes")
        else:
            try:
                with ctx.app.ecriture:
                    reg = pt.Registre(ctx.racine)
                    x = reg.employe(choisi) if choisi else None
                    if action == "ajouter":
                        x = reg.ajouter(ctx.req.champ("nom"))
                        choisi = x.id
                    elif x is None:
                        raise ValueError("Choisissez un employé dans la liste.")
                    elif action == "modifier":
                        reg.renommer(x.id, ctx.req.champ("nom"))
                    elif action == "supprimer":
                        if not action_permise(ctx, "Supprimer"):
                            raise ValueError("Votre profil n'a pas le droit « Supprimer ».")
                        reg.supprimer(x.id)
                        choisi = ""
                    elif action == "nip":
                        if ctx.req.champ("nip") != ctx.req.champ("nip2"):
                            raise ValueError("Les deux NIP sont différents.")
                        reg.definir_nip(x.id, ctx.req.champ("nip"))
                    elif action == "relier":
                        compte = ctx.req.champ("compte")
                        if compte and ctx.reg.trouver(compte) is None:
                            raise ValueError("Compte inconnu.")
                        x.compte = compte
                    elif action == "sage":
                        x.numero_sage = ctx.req.champ("numero_sage").strip()
                    elif action == "courriel":
                        adresse = ctx.req.champ("courriel").strip()
                        if adresse and adresses_invalides(adresse):
                            raise ValueError("Adresse de courriel invalide.")
                        x.courriel = adresse
                    elif action == "adresse":
                        x.adresse = " | ".join(v.strip() for v in ctx.req.champ("adresse").split("|") if v.strip())
                    elif action == "basculer":
                        x.actif = not x.actif
                    reg.enregistrer()
                message = _message("Enregistré.")
                op = ""
            except (ValueError, pt.ErreurPointage) as erreur:
                message = _message(erreur=str(erreur))
        registre = pt.Registre(ctx.racine)
    liste = (sorted(registre.employes, key=lambda x: (not x.actif, x.nom.casefold())) if ctx.voit_tous()
             else ctx.employes_visibles(registre))
    lignes = [[f"<input type='radio' name='id' value='{e(x.id)}'{' checked' if x.id == choisi else ''}>", e(x.nom),
               "Défini" if x.nip else "<span class='erreur-texte'>À définir</span>", "Oui" if x.actif else "Non",
               "Oui" if x.clover else "", e(x.numero_sage), e(x.courriel), e(x.compte)] for x in liste]
    boutons = "".join(f"<button class='second' name='op' value='{k}'>{e(t)}</button>" for k, t in BOUTONS_EMPLOYES)
    corps = (message
             + (f"<form method='get'><div class='barre-onglet'>{boutons}</div>" if ctx.voit_tous() else "<form>")
             + "<p class='note'>Le NIP (4 à 6 chiffres) n'est jamais gardé : seule son empreinte l'est. Un employé sans "
               "NIP apparaît au poste de pointage, mais ne peut pas pointer.</p>"
             + tableau_section(Section("Employés et NIP", ["", "Employé", "NIP", "Actif", "Employé Clover",
                                                           "Employé Sage", "Courriel", "Compte de l'application"],
                                       lignes, html=set(range(8))))
             + "</form>" + _action_employe(ctx, registre, op, choisi))
    return Reponse(corps=page(ctx, "Employés et NIP", corps))


def _action_employe(ctx: Contexte, registre, op: str, choisi: str) -> str:
    """Petite fenêtre de saisie de Windows, ouverte sous la liste."""
    if not op:
        return ""
    x = registre.employe(choisi) if choisi else None
    if op not in ("importer", "ajouter") and x is None:
        return "<p class='erreur-texte'>Choisissez un employé dans la liste.</p>"

    def forme(titre: str, contenu: str, bouton: str, classe: str = "") -> str:
        return (f"<form method='post' class='carte'>{csrf(ctx)}<input type='hidden' name='id' value='{e(choisi)}'>"
                f"<h2>{e(titre)}</h2><div class='ligne'>{contenu}<button class='{classe}' name='action' "
                f"value='{op}'>{e(bouton)}</button></div></form>")

    if op == "importer":
        return forme("Importer les employés de Clover", "<p>Les employés de Clover absents de la liste sont ajoutés "
                                                        "(sans NIP).</p>", "⬇ Importer")
    if op == "ajouter":
        return forme("Ajouter un employé", "<div><label>Nom de l'employé :</label><input name='nom' size='30' "
                                           "required></div>", "➕ Ajouter") + (
            "<p class='note'>Ajouté ici dans l'application. La création dans Clover et dans Sage Paie (NAS, taux) se "
            "fait dans l'application Windows (« Ajouter » de cette fenêtre).</p>")
    if op == "modifier":
        return forme(f"Modifier {x.nom}", f"<div><label>Nom de l'employé :</label><input name='nom' "
                                         f"value='{e(x.nom)}' size='30' required></div>", "✔ Enregistrer")
    if op == "supprimer":
        return forme(f"Supprimer {x.nom} ?", "<p>Un employé qui a des pointages ne peut pas être supprimé : "
                                             "désactivez-le.</p>", "🗑 Supprimer", "danger")
    if op == "nip":
        return forme(f"NIP de {x.nom}", "<div><label>Nouveau NIP (4 à 6 chiffres) :</label><input name='nip' "
                                       "type='password' inputmode='numeric' pattern='[0-9]{4,6}' autocomplete='off' "
                                       "required></div><div><label>Encore une fois :</label><input name='nip2' "
                                       "type='password' inputmode='numeric' autocomplete='off' required></div>",
                     "🔑 Définir le NIP")
    if op == "relier":
        comptes = "<option value=''>— aucun —</option>" + "".join(
            f"<option{' selected' if u.nom == x.compte else ''}>{e(u.nom)}</option>" for u in ctx.reg.utilisateurs)
        return forme(f"Relier {x.nom} à un compte", f"<div><label>Compte de l'application :</label><select "
                                                    f"name='compte'>{comptes}</select></div>", "🔗 Relier")
    if op == "sage":
        return forme(f"Lier {x.nom} à l'employé Sage", "<div><label>Nom de l'employé tel que Sage l'écrit :</label>"
                                                       f"<input name='numero_sage' value='{e(x.numero_sage)}' "
                                                       "size='30'></div>", "🔗 Lier")
    if op == "courriel":
        return forme(f"Courriel de {x.nom} (bulletins de paie)", f"<div><label>Courriel :</label><input "
                                                                 f"name='courriel' type='email' value='{e(x.courriel)}' "
                                                                 "size='30'></div>", "✉ Enregistrer")
    if op == "adresse":
        return forme(f"Adresse de {x.nom} (T4 et RL-1)", "<div class='large'><label>Lignes séparées par « | » :"
                                                         f"</label><input name='adresse' value='{e(x.adresse)}' "
                                                         "size='60'></div>", "🏠 Enregistrer")
    if op == "basculer":
        return forme(f"{x.nom} : {'actif' if x.actif else 'inactif'}", "",
                     "⏻ Désactiver" if x.actif else "⏻ Activer")
    return ""


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
    """Comme fenetre_conges.FenetreConges, 3 onglets : « Jours fériés » (année, Pâques : Vendredi saint / Lundi de
    Pâques, indemnité par employé), « Congés » (Employé *, Du … au, Type *, Heures payées par jour, Seulement les jours
    planifiés, « ➕ Ajouter le congé », « 🗑 Supprimer ») et « Soldes par employé » (« 📅 Date d'embauche… »)."""
    from .. import conges as co
    from .. import paie_temps as pt
    from .. import planning as pl
    from .pages_rapports_web import onglets

    registre = pt.Registre(ctx.racine)
    visibles = ctx.employes_visibles(registre)
    noms = {x.id: x.nom for x in visibles}
    onglet = ctx.req.query.get("onglet") or ctx.req.champ("onglet") or "feries"
    message = ""
    if ctx.req.methode == "POST":
        action = ctx.req.champ("action")
        try:
            with ctx.app.ecriture:
                reg_conges = co.Registre(ctx.racine)
                if action == "Supprimer":
                    if not action_permise(ctx, "Supprimer"):
                        raise ValueError("Votre profil n'a pas le droit « Supprimer ».")
                    ident = ctx.req.champ("conge")
                    c = next((c for c in reg_conges.conges if c.id == ident and c.employe in noms), None)
                    if c is None:
                        raise ValueError("Choisissez un congé dans la liste.")
                    reg_conges.supprimer(ident)
                    message = _message(f"Congé du {c.jour} supprimé.")
                elif action == "Date d'embauche":
                    x = _employe_visible(ctx, registre, ctx.req.champ("employe"))
                    if x is None:
                        raise ValueError("Choisissez un employé dans la liste.")
                    reg_conges.embauches[x.id] = _date(ctx.req.champ("embauche")).isoformat()
                    reg_conges.enregistrer()
                    message = _message("✔ Date d'embauche enregistrée.")
                elif action == "Ajouter le congé":
                    employe = _employe_visible(ctx, registre, ctx.req.champ("employe"))
                    if employe is None:
                        raise ValueError("Choisissez l'employé.")
                    plan = pl.Planning(ctx.racine)
                    travailles = ((lambda j: plan.quart(f"{j:%Y-%m}", employe.id, j) is not None)
                                  if ctx.req.champ("planifies") else None)
                    ajoutes = reg_conges.ajouter(employe.id, _date(ctx.req.champ("du")), _date(ctx.req.champ("au")),
                                                 ctx.req.champ("type"), _decimal(ctx.req.champ("heures")), ctx.u.nom,
                                                 ctx.req.champ("remarque"), jours_travailles=travailles)
                    message = (_message(f"✔ {len(ajoutes)} jour(s) de congé ajouté(s).") if ajoutes else _message(
                        erreur="⚠ Aucun jour ajouté : aucun quart planifié dans la période (décochez « Seulement les "
                               "jours planifiés »)."))
        except ValueError as erreur:
            message = _message(erreur=str(erreur) or "Dates AAAA-MM-JJ et heures en chiffres.")
    reg_conges = co.Registre(ctx.racine)
    if onglet == "conges":
        corps = _onglet_conges(ctx, reg_conges, visibles, noms)
    elif onglet == "soldes":
        corps = _onglet_soldes(ctx, reg_conges, visibles)
    else:
        if ctx.req.query.get("paques") in ("vendredi", "lundi") and ctx.voit_tous():
            with ctx.app.ecriture:
                reg_conges.paques = ctx.req.query["paques"]
                reg_conges.enregistrer()
        try:
            annee = int(ctx.req.query.get("annee") or date.today().year)
        except ValueError:
            annee = date.today().year
        lignes = []
        for jour, nom in co.jours_feries(annee, reg_conges.paques):
            passe = jour <= date.today()
            indemnites = (" ; ".join(f"{x.nom} : {heures(co.indemnite_heures(registre, x, jour))}" for x in visibles)
                          if passe else "")
            lignes.append([jour.isoformat(), nom, "Passé" if passe else "À venir", indemnites])
        annees = "".join(f"<option{' selected' if a == annee else ''}>{a}</option>"
                         for a in (date.today().year - 1, date.today().year, date.today().year + 1))
        paques = "".join(f"<option value='{k}'{' selected' if k == reg_conges.paques else ''}>{v}</option>"
                         for k, v in (("vendredi", "Vendredi saint"), ("lundi", "Lundi de Pâques")))
        corps = ("<form method='get' class='barre-onglet'><input type='hidden' name='onglet' value='feries'><div><label>"
                 f"Année</label><select name='annee'>{annees}</select></div><div><label>Pâques : jour férié</label>"
                 f"<select name='paques'>{paques}</select></div><button class='second'>Afficher</button></form>"
                 + tableau_section(Section("Jours fériés", ["Date", "Jour férié", "État", "Indemnité par employé"],
                                           lignes))
                 + "<div class='ligne-etat'>Indemnité = 1/20 des heures normales pointées pendant les 4 semaines "
                   "complètes avant la semaine du jour férié (heures supplémentaires exclues) ; elle s'ajoute aux heures "
                   "validées de la période de paie.</div>")
    actif = {"conges": "Congés", "soldes": "Soldes par employé"}.get(onglet, "Jours fériés")
    return Reponse(corps=page(ctx, "Jours fériés et congés", message + onglets(actif, ctx)
                              + f"<div class='onglet-corps'>{corps}</div>"))


def _onglet_conges(ctx: Contexte, reg_conges, visibles, noms) -> str:
    from .. import conges as co

    options = "<option value=''></option>" + "".join(f"<option value='{e(x.id)}'>{e(x.nom)}</option>" for x in visibles)
    types = "".join(f"<option>{e(t)}</option>" for t in co.TYPES)
    liste = sorted((c for c in reg_conges.conges if c.employe in noms), key=lambda c: c.jour, reverse=True)
    lignes = [[f"<input type='radio' name='conge' value='{e(c.id)}'>", e(c.jour), e(noms.get(c.employe, c.employe)),
               e(c.type), heures(Decimal(c.heures)), e(c.auteur), e(c.remarque)] for c in liste]
    aujourdhui = date.today().isoformat()
    return (f"<form method='post'>{csrf(ctx)}<input type='hidden' name='onglet' value='conges'>"
            f"<div class='barre-onglet'><div><label>Employé *</label><select name='employe'>{options}</select></div>"
            f"<div><label>Du</label><input type='date' name='du' value='{aujourdhui}'></div><div><label>au</label>"
            f"<input type='date' name='au' value='{aujourdhui}'></div><div><label>Type *</label><select name='type'>"
            f"{types}</select></div><div><label>Heures payées par jour</label><input name='heures' value='8' size='4'>"
            "</div><div><label>Remarque</label><input name='remarque' size='18'></div><div><label><input "
            "type='checkbox' name='planifies' value='1' checked> Seulement les jours planifiés</label></div>"
            "<button name='action' value='Ajouter le congé'>➕ Ajouter le congé</button><button class='danger' "
            "name='action' value='Supprimer'>🗑 Supprimer</button></div>"
            "<p class='note'>Congé payé : l'indemnité (heures par jour) est payée avec la paie de la période. Maladie "
            "ou famille : 2 jours payés par année après 3 mois de service, 10 jours au total.</p>"
            + tableau_section(Section("Congés", ["", "Date", "Employé", "Type", "Heures payées", "Saisi par",
                                                 "Remarque"], lignes, html=set(range(7))))
            + "</form>")


def _onglet_soldes(ctx: Contexte, reg_conges, visibles) -> str:
    from .. import conges as co

    choisi = ctx.req.query.get("employe", "")
    lignes = []
    for x in visibles:
        sd = co.solde(reg_conges, x, date.today())
        lignes.append([f"<input type='radio' name='employe' value='{e(x.id)}'{' checked' if x.id == choisi else ''}>",
                       e(x.nom), e(reg_conges.embauches.get(x.id, "")), e(sd.service), str(sd.vacances_semaines),
                       e(sd.vacances_taux), str(sd.vacances_prises), str(sd.maladie_payes_dus - sd.maladie_payes_pris),
                       f"{sd.maladie_pris}/{co.JOURS_MALADIE_TOTAL}", e(" ; ".join(sd.remarques))])
    x = next((v for v in visibles if v.id == choisi), None)
    forme = ""
    if ctx.req.query.get("op") == "embauche":
        forme = ("<p class='erreur-texte'>Choisissez un employé dans la liste.</p>" if x is None else
                 f"<form method='post' class='carte'>{csrf(ctx)}<input type='hidden' name='onglet' value='soldes'>"
                 f"<input type='hidden' name='employe' value='{e(x.id)}'><div class='ligne'><div><label>Date "
                 f"d'embauche de {e(x.nom)} :</label><input type='date' name='embauche' "
                 f"value='{e(reg_conges.embauches.get(x.id, ''))}' required></div><button name='action' "
                 "value=\"Date d'embauche\">✔ Enregistrer</button></div></form>")
    return ("<form method='get'><input type='hidden' name='onglet' value='soldes'><div class='barre-onglet'><button "
            "class='second' name='op' value='embauche'>📅 Date d'embauche…</button></div>"
            + tableau_section(Section("Soldes de congés", ["", "Employé", "Embauché le", "Service",
                                                           "Semaines de vacances", "Indemnité de vacances",
                                                           "Jours de vacances pris", "Jours de maladie payés restants",
                                                           "Absences maladie ou famille", "À vérifier"], lignes,
                                      html=set(range(10))))
            + "</form>" + forme)


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
    paies = lire_ou_vide(ctx, lambda b: pa.paies_sage(b, date(annee, 1, 1), fin))
    if "Sage" not in ctx.absents:
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
