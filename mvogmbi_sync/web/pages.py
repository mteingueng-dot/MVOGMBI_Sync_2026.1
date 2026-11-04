"""Pages de l'application web (1re étape, 2026-11-03) : employés (horaire, heures, pointage), gérant (feuilles de
temps, tableau du gérant), statistiques Clover ; les autres fonctions viendront par étapes.

Droits : chaque page porte le titre de l'entrée du menu de l'application de bureau qui lui correspond ; elle est
permise exactement comme cette entrée (accès par fonction, sinon page du profil et fonctions retirées). Un profil
limité à son employé (utilisateurs.LIMITES_DEFAUT) ne voit que l'employé relié à son compte.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Callable

from .serveur import Reponse, echapper as e, redirection, temoin_session

NOM_APPLICATION = "MVOGMBI_Sync"
DUREE_MEMOIRE = 300  # s : statistiques Clover gardées 5 min
JOURS = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]


@dataclass
class Fonction:
    chemin: str
    titre: str          # titre de l'entrée du menu de l'application de bureau (droits)
    page: str | None    # clé de page (utilisateurs.PAGES) de cette entrée
    gestionnaire: Callable
    icone: str
    rubrique: str
    toujours: bool = False  # permise à toute personne connectée
    menu: bool = True       # tuile de l'accueil (faux : page de détail)
    page_entiere: bool = False  # entrée du menu = page Windows entière : permise par sa clé de page (au_menu)


@dataclass
class Contexte:
    app: object
    req: object
    reg: object
    u: object
    session: object
    absents: set = field(default_factory=set)  # « Sage », « Clover » : sources qui n'ont pas répondu (tableaux vides)

    @property
    def racine(self):
        return self.app.racine

    @property
    def config(self) -> dict:
        return self.app.config

    def voit_tous(self) -> bool:
        return self.reg.voit_tous_employes(self.u)

    def employe(self, registre=None):
        """Employé de la paie relié au compte connecté (« Employés et NIP » > « Relier à un compte… »)."""
        from .. import paie_temps as pt

        registre = registre or pt.Registre(self.racine)
        return next((x for x in registre.employes if x.compte and x.compte.casefold() == self.u.nom.casefold()), None)

    def employes_visibles(self, registre) -> list:
        if self.voit_tous():
            return registre.actifs()
        moi = self.employe(registre)
        return [moi] if moi else []


def permis(reg, u, f: Fonction) -> bool:
    if f.toujours or u.est_admin:
        return True
    fonctions = reg.permises(u)
    if fonctions is not None:
        return (f.page in fonctions) if f.page_entiere else (f.titre in fonctions)
    return (f.page in reg.pages(u)) and f.titre not in reg.refusees(u)


# --------------------------------------------------------------------------------------------- gabarit
STYLE = """
:root { --vert: #13772d; --vert-pale: #e8f4ec; --rouge: #c8102e; --jaune: #f2b705; --texte: #1f2d24;
        --gris: #6b7a70; --fond: #fafafa; --carte: #ffffff; --bord: #e2e8e4;
        --menu: #eef4f0; --menu-survol: #e2ede6; --menu-actif: #d3eadb; --vert-vif: #1a9b3c;
        --fond-page: #f3f5f4; }
@media (prefers-color-scheme: dark) {
  :root { --vert: #4cc26d; --vert-pale: #1d3325; --texte: #e6efe8; --gris: #9fb0a5; --fond: #121814;
          --carte: #1a221d; --bord: #2c3a31; --menu: #17201a; --menu-survol: #1f2b23; --menu-actif: #24402d; --fond-page: #121814; }
}
* { box-sizing: border-box; }
body { margin: 0; font-family: -apple-system, "Segoe UI", Roboto, sans-serif; background: var(--fond);
       color: var(--texte); font-size: 16px; line-height: 1.4; }
.filet { height: 4px; background: linear-gradient(90deg, var(--vert) 0 34%, var(--rouge) 34% 67%, var(--jaune) 67%); }
main { max-width: 960px; margin: 0 auto; padding: 16px; }
h1 { font-size: 22px; margin: 4px 0 14px; color: var(--vert); }
h1.titre-page { color: var(--vert-vif); font-weight: 600; }
h2 { font-size: 17px; margin: 22px 0 8px; }
.tuiles { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 10px; }
.tuile { display: block; background: var(--carte); border: 1px solid var(--bord); border-radius: 12px; padding: 14px;
         color: var(--texte); text-decoration: none; min-height: 84px; }
.tuile .ic { font-size: 24px; display: block; margin-bottom: 6px; }
.tuile:hover { border-color: var(--vert); }
.cartes { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 10px; }
.carte { background: var(--carte); border: 1px solid var(--bord); border-radius: 12px; padding: 12px; }
.carte .t { color: var(--gris); font-size: 13px; } .carte .v { font-size: 22px; font-weight: 700; }
.carte .d { font-size: 13px; } .hausse { color: var(--vert); } .baisse { color: var(--rouge); }
.defile { overflow-x: auto; background: var(--carte); border: 1px solid var(--bord); border-radius: 12px; }
table { border-collapse: collapse; width: 100%; font-size: 14px; }
th { background: var(--vert); color: #fff; text-align: left; padding: 8px; white-space: nowrap; }
td { padding: 7px 8px; border-top: 1px solid var(--bord); vertical-align: top; }
tr:nth-child(even) td { background: var(--vert-pale); }
td.n, th.n { text-align: right; white-space: nowrap; }
progress { width: 100%; min-width: 80px; height: 12px; accent-color: var(--vert); }
.ligne { display: flex; gap: 8px; flex-wrap: wrap; align-items: end; margin-bottom: 12px; }
label { display: block; font-size: 14px; color: var(--gris); margin-bottom: 3px; }
input, select { font: inherit; padding: 9px 10px; border: 1px solid var(--bord); border-radius: 8px;
                background: var(--carte); color: var(--texte); max-width: 100%; }
button { font: inherit; padding: 9px 16px; border: 0; border-radius: 8px; background: var(--vert); color: #fff;
         cursor: pointer; font-weight: 600; }
button.second { background: var(--carte); color: var(--vert); border: 1px solid var(--vert); }
button.lien { background: none; color: #fff; padding: 0; font-weight: 600; }
form.carte { margin: 14px 0; } form.carte h2 { margin-top: 0; }
.ligne label input { width: auto; }
.boutons { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 12px; }
.boutons button { min-width: 140px; padding: 14px 18px; font-size: 18px; }
.boite { max-width: 380px; margin: 40px auto; background: var(--carte); border: 1px solid var(--bord);
         border-radius: 14px; padding: 22px; }
.boite input { width: 100%; margin-bottom: 12px; }
.boite button { width: 100%; }
.erreur { color: var(--rouge); font-weight: 600; } .ok { color: var(--vert); font-weight: 600; }
.note { color: var(--gris); font-size: 14px; }
.etat { font-size: 13px; padding: 2px 8px; border-radius: 10px; background: var(--vert-pale); white-space: nowrap; }
nav.periodes a { margin-right: 12px; }
a { color: var(--vert); }
.aide h2 { color: var(--vert); } .aide .q { font-weight: 700; margin: 16px 0 4px; } .aide .note { font-style: italic; }
"""


def _entete(ctx: Contexte | None) -> str:
    from .accueil import entete

    return entete()


def _document(titre: str, corps: str, ctx: Contexte | None = None, menu: str = "") -> str:
    contenu = f"<div class='cadre'>{menu}<main>{corps}</main></div>" if menu else f"<main>{corps}</main>"
    return (f"<!doctype html><html lang='fr'><head><meta charset='utf-8'>"
            f"<meta name='viewport' content='width=device-width, initial-scale=1'>"
            f"<meta name='robots' content='noindex'><title>{e(titre)} · {NOM_APPLICATION}</title>"
            f"<link rel='stylesheet' href='/style.css'></head><body>{_entete(ctx)}{contenu}</body></html>")


def page(ctx: Contexte, titre: str, corps: str) -> str:
    """Page avec le menu de gauche de l'application Windows (menu.py)."""
    from .menu import barre

    absents = sorted(getattr(ctx, "absents", ()) or ())
    alerte = ("<p class='alerte-source'>⚠ " + e(" et ".join(absents)) + " ne répond pas sur le serveur pour l'instant : "
              "les tableaux sont affichés vides, ils se rempliront dès que la connexion sera faite.</p>") if absents else ""
    fermer = "" if titre == "Accueil" else "<a class='fermer' href='/'>✖ Fermer</a>"  # bandeau des fenêtres de travail
    return _document(titre, f"<div class='entete-outil'><h1 class='titre-page'>{e(titre)}</h1>{fermer}</div>{alerte}"
                            f"<div class='zone-outil'>{corps}</div>", ctx, barre(ctx))


def page_simple(titre: str, message: str) -> str:
    return _document(titre, f"<div class='boite'><h1>{e(titre)}</h1><p>{e(message)}</p>"
                            f"<p><a href='/'>Retour à l'accueil</a></p></div>")


def csrf(ctx: Contexte) -> str:
    return f"<input type='hidden' name='csrf' value='{e(ctx.session.csrf)}'>"


def tableau(entete: list[str], lignes: list[list], numeriques: set[int] = frozenset()) -> str:
    th = "".join(f"<th class='{'n' if i in numeriques else ''}'>{e(c)}</th>" for i, c in enumerate(entete))
    corps = "".join("<tr>" + "".join(f"<td class='{'n' if i in numeriques else ''}'>{c}</td>"
                                     for i, c in enumerate(ligne)) + "</tr>" for ligne in lignes)
    return f"<div class='defile'><table><tr>{th}</tr>{corps}</table></div>"


def argent(v) -> str:
    if v is None:
        return "—"
    signe = "-" if v < 0 else ""
    entier, _, dec = f"{abs(Decimal(v)):.2f}".partition(".")
    groupes = []
    while len(entier) > 3:
        groupes.insert(0, entier[-3:])
        entier = entier[:-3]
    return f"{signe}{' '.join([entier] + groupes)},{dec} $"


def heures(v) -> str:
    return f"{Decimal(v):.2f}".replace(".", ",")


# --------------------------------------------------------------------------------------------- connexion
def connexion(app, req) -> Reponse:
    from ..utilisateurs import Registre

    message = ""
    if req.methode == "POST":
        reg = Registre(app.racine)
        if app.adresse_bloquee(req.adresse):
            message = "Trop d'essais depuis cet appareil : réessayez dans 10 minutes."
        elif not reg.existe():
            message = "Aucun compte : créez d'abord le compte administrateur dans l'application Windows."
        else:
            with app.ecriture:
                u = reg.verifier(req.champ("nom"), req.champ("mot_de_passe"))
            if u is not None:
                s = app.sessions.creer(u.nom)
                return Reponse(303, "", entetes={"Location": "/", "Set-Cookie": temoin_session(s.jeton, app.https)})
            app.echec(req.adresse)
            trouve = reg.trouver(req.champ("nom"))
            message = ("Compte verrouillé : demandez à un administrateur un nouveau mot de passe."
                       if trouve is not None and reg.bloque(trouve) else "Nom ou mot de passe incorrect.")
    corps = (f"<div class='boite'><h1>Connexion</h1>"
             + (f"<p class='erreur'>{e(message)}</p>" if message else "")
             + "<form method='post' action='/connexion'>"
               "<label for='nom'>Nom d'utilisateur</label><input id='nom' name='nom' autocomplete='username' required>"
               "<label for='mdp'>Mot de passe</label><input id='mdp' name='mot_de_passe' type='password' "
               "autocomplete='current-password' required><button type='submit'>Se connecter</button></form>"
               "<p class='note'>Même nom et même mot de passe que l'application MVOGMBI_Sync.</p></div>")
    entetes = {"Set-Cookie": temoin_session("", app.https, effacer=True)} if req.methode == "GET" else {}
    return Reponse(200, _document("Connexion", corps), entetes=entetes)


# --------------------------------------------------------------------------------------------- accueil
def accueil(ctx: Contexte) -> Reponse:
    par_rubrique: dict[str, list[Fonction]] = {}
    for f in toutes():
        if f.chemin != "/" and f.menu and permis(ctx.reg, ctx.u, f):
            par_rubrique.setdefault(f.rubrique, []).append(f)
    corps = ""
    for rubrique, liste in par_rubrique.items():
        tuiles = "".join(f"<a class='tuile' href='{f.chemin}'><span class='ic'>{f.icone}</span>{e(f.titre)}</a>"
                         for f in liste)
        corps += f"<h2>{e(rubrique)}</h2><div class='tuiles'>{tuiles}</div>"
    corps += ("<p class='note'>Les autres fonctions (comptabilité, fournisseurs, articles, administration) arrivent "
              "ici par étapes. D'ici là : application complète par le client MVOGMBI_Sync, bouton « Application "
              "complète (Bureau à distance) ».</p>")
    return Reponse(corps=page(ctx, f"Bonjour {ctx.u.nom}", corps))


# --------------------------------------------------------------------------------------------- employés
def _choisir_employe(ctx: Contexte, registre):
    """Employé affiché : le sien ; un gérant peut en choisir un autre (?employe=)."""
    visibles = ctx.employes_visibles(registre)
    voulu = ctx.req.query.get("employe", "")
    choisi = next((x for x in visibles if x.id == voulu), None) or ctx.employe(registre)
    if choisi is None or choisi not in visibles:
        choisi = visibles[0] if visibles and ctx.voit_tous() else None
    if not ctx.voit_tous() or len(visibles) < 2:
        return choisi, ""
    options = "".join(f"<option value='{e(x.id)}'{' selected' if choisi and x.id == choisi.id else ''}>{e(x.nom)}"
                      f"</option>" for x in visibles)
    return choisi, (f"<form class='ligne' method='get'><div><label for='employe'>Employé</label><select id='employe' "
                    f"name='employe'>{options}</select></div><button class='second' type='submit'>Afficher</button>"
                    f"</form>")


SANS_EMPLOYE = ("<p class='erreur'>Votre compte n'est relié à aucun employé.</p><p class='note'>Demandez au gérant : "
                "« Paie > Employés et NIP » > « Relier à un compte… » dans l'application.</p>")


def sans_employe(ctx: Contexte) -> str:
    """Aucun employé à montrer : compte non relié (profil limité), ou aucun employé encore (gérant)."""
    if ctx.voit_tous():
        return ("<p>Aucun employé pour l'instant.</p><p class='note'>Ajoutez-les dans « Paie > Employés et NIP » "
                "(ou importez-les de Clover dans l'application complète).</p>")
    return SANS_EMPLOYE


def mon_horaire(ctx: Contexte) -> Reponse:
    """Comme fenetre_planning.FenetreMonHoraire : horaire publié des 5 semaines à partir d'aujourd'hui, cartes
    (prochain quart, heures sur 5 semaines, jours de travail), tableau regroupé par semaine (dimanche à samedi)."""
    from .. import paie_temps as pt
    from .. import planning as pl
    from ..fenetre_planning import ENTETES_HORAIRE, lignes_horaire, semaines_horaire
    from .consultations import Section, tableau_section

    registre = pt.Registre(ctx.racine)
    employe, choix = _choisir_employe(ctx, registre)
    if employe is None:
        return Reponse(corps=page(ctx, "Mon horaire", "<p class='note'>Votre compte n'est relié à aucun employé : "
                                                      "demandez au gérant de le relier dans « Paie > Employés et NIP »."
                                                      "</p>"))
    lignes, semaines = semaines_horaire(lignes_horaire(pl.Planning(ctx.racine), employe.id, date.today()))
    travailles = [l for l in lignes if l[-1] == "quart"]
    prochain = f"{travailles[0][0]}  {travailles[0][1]}" if travailles else "Aucun quart publié"
    total = sum(semaines, Decimal(0))
    cartes = "".join(f"<div class='carte-total'><div class='t'>{titre}</div><div class='v'>{e(valeur)}</div></div>"
                     for titre, valeur in (("Prochain quart", prochain),
                                           ("Heures sur 5 semaines", f"{total:.2f} h".replace(".", ",")),
                                           ("Jours de travail", str(len(travailles)))))
    classes = {"repos": "termine", "semaine": "total", "quart": ""}
    corps = (choix + f"<p class='note'>Horaire publié de {e(employe.nom)}, 5 semaines à partir d'aujourd'hui.</p>"
             f"<div class='cartes-trois'>{cartes}</div>"
             + tableau_section(Section("Mon horaire", ENTETES_HORAIRE, [l[:-1] for l in lignes],
                                       classes=[classes.get(l[-1], "") for l in lignes])))
    return Reponse(corps=page(ctx, f"Horaire de {employe.nom}" if ctx.voit_tous() else "Mon horaire", corps))


def _reference(racine) -> date:
    from ..fenetre_pointage import reference

    return reference(racine)


def mes_heures(ctx: Contexte) -> Reponse:
    """« Mes heures et mes paies » : la fenêtre de la paie (fenetre_paie.FenetrePaie) réduite à l'employé relié au
    compte : période de paie, heures planifiées et réalisées (par semaine ou par jour), feuille de temps, puis ses
    paies et bulletins."""
    from .. import paie as pa
    from .. import paie_temps as pt
    from ..fenetre_paie import VUES
    from ..planning import Planning
    from .consultations import Section, tableau_section

    registre = pt.Registre(ctx.racine)
    employe, choix = _choisir_employe(ctx, registre)
    if employe is None:
        return Reponse(corps=page(ctx, "Mes heures et mes paies", sans_employe(ctx)))
    reference = _reference(ctx.racine)
    actuelle = pt.debut_periode(date.today(), reference)
    periodes = [actuelle - timedelta(days=pt.JOURS_PERIODE * i) for i in range(13)]
    try:
        debut = pt.debut_periode(date.fromisoformat(ctx.req.query.get("periode", "")), reference)
    except ValueError:
        debut = actuelle
    fin = debut + timedelta(days=pt.JOURS_PERIODE - 1)
    vue = ctx.req.query.get("vue") if ctx.req.query.get("vue") in VUES else VUES[0]
    f = pt.feuille(registre, employe, debut)
    planning = Planning(ctx.racine)
    if vue == VUES[1]:
        lignes = [[l[0], l[1], l[2], pa.heures(l[3]), pa.heures(l[4]), l[5]] for l in pa.jours([f], planning)]
        section = Section(f"Heures par jour du {debut} au {fin}", pa.ENTETES_JOURS, lignes)
    else:
        section = Section(f"Heures par semaine du {debut} au {fin}", pa.ENTETES_SEMAINES,
                          [[l.debut, l.fin, l.employe, pa.heures(l.planifiees), pa.heures(l.realisees), l.ecart, l.etat]
                           for l in pa.semaines([f], planning)])
    options = "".join(f"<option value='{x}'{' selected' if x == debut else ''}>{x} au "
                      f"{x + timedelta(days=pt.JOURS_PERIODE - 1)}</option>" for x in periodes)
    vues = "".join(f"<option{' selected' if x == vue else ''}>{e(x)}</option>" for x in VUES)
    cartes = "".join(f"<div class='carte-total'><div class='t'>{t_}</div><div class='v'>{v_}</div></div>"
                     for t_, v_ in (("Heures normales", heures(f.normales)),
                                    ("Heures supplémentaires", heures(f.supplementaires)),
                                    ("Feuille de temps", e(f.etat))))
    corps = (choix + "<nav class='onglets'><a class='onglet actif' href='#'>Heures planifiées et réalisées</a>"
             f"<a class='onglet' href='/paies?employe={e(employe.id)}'>Paies dans Sage</a></nav><div class='onglet-corps'>"
             f"<form class='barre-onglet' method='get'><input type='hidden' name='employe' value='{e(employe.id)}'>"
             f"<div><label>Période de paie</label><select name='periode'>{options}</select></div><div><label>Affichage"
             f"</label><select name='vue'>{vues}</select></div><button class='second'>Afficher</button></form>"
             f"<div class='cartes-trois'>{cartes}</div>" + tableau_section(section)
             + ("<p class='erreur-texte'>À corriger par le gérant : " + e(" ; ".join(f.anomalies)) + "</p>"
                if f.anomalies else "")
             + "<div class='ligne-etat'>Heures réalisées = pointages ; heures planifiées = planning mensuel.</div></div>")
    titre = f"Heures et paies de {employe.nom}" if ctx.voit_tous() else "Mes heures et mes paies"
    return Reponse(corps=page(ctx, titre, corps))


def _poste_permis(ctx: Contexte) -> bool:
    """Le pointage se fait au magasin (règle du propriétaire) : seulement depuis les adresses de [web]
    postes_pointage (adresses ou débuts d'adresse, ex. « 100.101.7.12 » ou « 192.168.1. »)."""
    postes = ctx.config.get("web", {}).get("postes_pointage", [])
    if isinstance(postes, str):
        postes = [p for p in postes.replace(";", ",").split(",")]
    return any(p.strip() and ctx.req.adresse.startswith(p.strip()) for p in postes)


RETOUR_POSTE = 12  # secondes avant le retour à la liste des noms (fenetre_pointage.RETOUR_ACCUEIL_MS)
JOURS_LONGS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]


def pointage(ctx: Contexte) -> Reponse:
    """Comme fenetre_pointage.PostePointage, en 3 étapes : « Touchez votre nom » (grille, présent / en pause / NIP à
    créer), « Tapez votre NIP » (pavé ; les chiffres restent sur le serveur, jamais dans la page), puis les actions
    permises (Départ en rouge), le résumé du jour et de la semaine, « 📅 Mon horaire », « ◀ Retour ». Retour à la
    liste après 12 s. Seulement depuis un poste du magasin ([web] postes_pointage)."""
    import time

    from .. import paie_temps as pt

    if not _poste_permis(ctx):
        return Reponse(corps=page(ctx, "Pointage", "<p class='erreur'>Le pointage se fait seulement depuis un poste du "
                                                   "magasin.</p><p class='note'>Adresse de cet appareil : "
                                                   f"{e(ctx.req.adresse)}. Le gérant ajoute les postes du magasin "
                                                   "dans config.toml, [web] postes_pointage.</p>"))
    registre = pt.Registre(ctx.racine)
    employes = registre.actifs()
    par_id = {x.id: x for x in employes}
    cle = ("poste", ctx.session.jeton)  # étape en cours de ce poste : {employe, nip, verifie, quand}
    etat = ctx.app.memoire.get(cle) or {}
    if etat and time.time() - etat.get("quand", 0) > RETOUR_POSTE * 5:
        etat = {}
    message, classe = "", "ok-texte"
    action = ctx.req.champ("action") if ctx.req.methode == "POST" else ""
    choisi = ctx.req.query.get("employe", "")
    if action == "Retour" or ctx.req.query.get("retour"):
        etat = {}
    elif choisi in par_id and not action:
        if not par_id[choisi].nip:
            message, classe = (f"{par_id[choisi].nom} n'a pas encore de NIP : le gérant le crée dans « Paie > Employés et "
                               "NIP »."), "erreur-texte"
            etat = {}
        else:
            etat = {"employe": choisi, "nip": "", "verifie": False}
    elif action.startswith("touche:") and etat.get("employe") in par_id and not etat.get("verifie"):
        touche = action[7:]
        if touche == "✖":
            etat["nip"] = ""
        elif touche == "✔":
            try:
                registre._echecs = dict(ctx.app.echecs_nip)
                bon = registre.verifier_nip(etat["employe"], etat["nip"])
                ctx.app.echecs_nip.update(registre._echecs)
                if bon:
                    etat["verifie"] = True
                else:
                    message, classe = "NIP incorrect.", "erreur-texte"
            except pt.ErreurPointage as erreur:
                message, classe = str(erreur), "erreur-texte"
            etat["nip"] = ""
        elif touche.isdigit() and len(etat["nip"]) < 6:
            etat["nip"] += touche
    elif action == "NIP" and etat.get("employe") in par_id:  # NIP tapé au clavier, puis Entrée
        etat["nip"] = "".join(c for c in ctx.req.champ("nip") if c.isdigit())[:6]
        try:
            registre._echecs = dict(ctx.app.echecs_nip)
            bon = registre.verifier_nip(etat["employe"], etat["nip"])
            ctx.app.echecs_nip.update(registre._echecs)
            etat["verifie"] = bool(bon)
            if not bon:
                message, classe = "NIP incorrect.", "erreur-texte"
        except pt.ErreurPointage as erreur:
            message, classe = str(erreur), "erreur-texte"
        etat["nip"] = ""
    elif action.startswith("pointer:") and etat.get("verifie") and etat.get("employe") in par_id:
        try:
            with ctx.app.ecriture:
                registre = pt.Registre(ctx.racine)
                pointe = registre.pointer(etat["employe"], action[8:])
            message = f"{par_id[etat['employe']].nom} : {pointe.type} à {pointe.quand:%H:%M} — merci !"
            etat = {}
        except pt.ErreurPointage as erreur:
            message, classe = str(erreur), "erreur-texte"
    etat["quand"] = time.time()
    ctx.app.memoire[cle] = etat
    maintenant = datetime.now()
    entete = (f"<div class='poste-haut'><span class='horloge'>{JOURS_LONGS[maintenant.weekday()].capitalize()} "
              f"{maintenant:%d/%m/%Y  %H:%M}</span><span class='note'>Pointage des employés</span></div>"
              + (f"<p class='{classe} poste-message'>{e(message)}</p>" if message else ""))
    employe = par_id.get(etat.get("employe", ""))
    if employe is None:  # étape 1 : le nom
        registre = pt.Registre(ctx.racine)
        cases = ""
        for x in employes:
            present = registre.etat_actuel(x.id)
            sous = ("● présent" if present in (pt.ARRIVEE, pt.FIN_PAUSE) else "● en pause" if present == pt.PAUSE
                    else "NIP à créer" if not x.nip else "")
            cases += (f"<a class='poste-nom' href='/pointage?employe={e(x.id)}'>{e(x.nom)}"
                      + (f"<span>{e(sous)}</span>" if sous else "") + "</a>")
        corps = (entete + "<h2>Touchez votre nom</h2>"
                 + (f"<div class='poste-grille'>{cases}</div>" if cases else
                    "<p class='note'>Aucun employé à afficher.</p>"))
        return Reponse(corps=page(ctx, "Pointage", corps))
    retour = f"<meta http-equiv='refresh' content='{RETOUR_POSTE};url=/pointage?retour=1'>"
    if not etat.get("verifie"):  # étape 2 : le NIP
        touches = "".join(f"<button class='poste-touche' name='action' value='touche:{x}'>{x}</button>"
                          for x in ["1", "2", "3", "4", "5", "6", "7", "8", "9", "✖", "0", "✔"])
        corps = (retour + entete + f"<div class='poste-centre'><div class='poste-employe'>{e(employe.nom)}</div>"
                 "<p class='note'>Tapez votre NIP</p>"
                 f"<div class='poste-nip'>{'●' * len(etat.get('nip', '')) or '&nbsp;'}</div>"
                 f"<form method='post'>{csrf(ctx)}<div class='poste-pave'>{touches}</div></form>"
                 f"<form method='post' class='barre-onglet'>{csrf(ctx)}<input name='nip' type='password' "
                 "inputmode='numeric' autocomplete='off' size='8' placeholder='ou au clavier' autofocus><button "
                 "class='second' name='action' value='NIP'>Entrée</button><button class='second' name='action' "
                 "value='Retour' formnovalidate>◀ Retour</button></form></div>")
        return Reponse(corps=page(ctx, "Pointage", corps))
    # étape 3 : les actions permises
    registre = pt.Registre(ctx.racine)
    if ctx.req.query.get("horaire"):
        from .. import planning as pl
        from ..fenetre_planning import lignes_horaire

        lignes = lignes_horaire(pl.Planning(ctx.racine), employe.id, date.today())
        texte = "\n".join(f"{l[1]} {l[0][8:]}/{l[0][5:7]}   " + (f"{l[2]} – {l[3]}" if l[3] else l[2])
                          for l in lignes) or "Aucun horaire publié."
        corps = (retour + entete + f"<div class='poste-centre'><div class='poste-employe'>Horaire de {e(employe.nom)}"
                 f"</div><pre class='texte-fixe'>{e(texte)}</pre><form method='post'>{csrf(ctx)}<button "
                 "class='second' name='action' value='Retour'>◀ Retour</button></form></div>")
        return Reponse(corps=page(ctx, "Pointage", corps))
    boutons = "".join(f"<button class='{'danger' if a == pt.DEPART else ''} poste-action' name='action' "
                      f"value='pointer:{e(a)}'>{e(a)}</button>" for a in registre.actions_permises(employe.id))
    aujourdhui = date.today()
    pointes = [x for x in registre.valides(employe.id) if x.moment[:10] == aujourdhui.isoformat()]
    feuille = pt.feuille(registre, employe, pt.debut_periode(aujourdhui, _reference(ctx.racine)))
    semaine = feuille.semaines[0 if aujourdhui < feuille.debut + timedelta(days=7) else 1]
    resume = (f"Aujourd'hui : {', '.join(f'{x.type} {x.quand:%H:%M}' for x in pointes) or '—'}\n"
              f"Cette semaine : {str(semaine).replace('.', ',')} h")
    corps = (retour + entete + f"<div class='poste-centre'><div class='poste-employe'>{e(employe.nom)}</div>"
             f"<form method='post'>{csrf(ctx)}<div class='poste-actions'>{boutons}</div></form>"
             f"<p class='texte-fixe note'>{e(resume)}</p><form method='post' class='barre-onglet poste-bas'>{csrf(ctx)}"
             "<a class='ouvrir' href='/pointage?horaire=1'>📅 Mon horaire</a><button class='second' name='action' "
             "value='Retour'>◀ Retour</button></form></div>")
    return Reponse(corps=page(ctx, "Pointage", corps))


# --------------------------------------------------------------------------------------------- gérant
def feuilles(ctx: Contexte) -> Reponse:
    """Comme fenetre_feuilles_temps.FenetreFeuilles : ◀ ▶ entre les périodes, « Approuver les feuilles sans anomalie »,
    tableau des 14 jours + semaines, normales, supplémentaires, état, anomalies ; lignes colorées (rose : anomalie,
    jaune : pointage corrigé, vert : approuvée) ; clic sur un employé = ses pointages (corrections)."""
    from .. import paie_temps as pt
    from ..fenetre_feuilles_temps import JOURS_COURTS
    from .consultations import Section, tableau_section

    reference = _reference(ctx.racine)
    try:
        debut = pt.debut_periode(date.fromisoformat(ctx.req.query.get("debut") or ctx.req.champ("debut")), reference)
    except ValueError:
        debut = pt.debut_periode(date.today(), reference)
    visibles = {x.id for x in ctx.employes_visibles(pt.Registre(ctx.racine))}
    message = ""
    if ctx.req.methode == "POST":
        if not ctx.voit_tous():
            message = "<p class='erreur'>Votre profil ne permet pas d'approuver les feuilles de temps.</p>"
        else:
            choisis = set(ctx.req.champs("approuver"))
            approuvees = 0
            with ctx.app.ecriture:
                registre = pt.Registre(ctx.racine)
                for f in pt.feuilles(registre, debut):
                    if (f.employe.id in visibles and f.etat == pt.A_APPROUVER and not f.anomalies and f.total > 0
                            and (not choisis or f.employe.id in choisis)):
                        pt.approuver(registre, f, ctx.u.nom)
                        approuvees += 1
            message = (f"<p class='ok'>{approuvees} feuille(s) approuvée(s).</p>" if approuvees else
                       "<p class='erreur'>Aucune feuille à approuver (sans anomalie et avec des heures).</p>")
    liste = [f for f in pt.feuilles(pt.Registre(ctx.racine), debut) if f.employe.id in visibles]
    fin = debut + timedelta(days=pt.JOURS_PERIODE - 1)
    jours = [debut + timedelta(days=i) for i in range(pt.JOURS_PERIODE)]

    def h(v) -> str:
        return "" if not v else f"{v:.2f}".replace(".", ",")

    entetes = (["Employé"] + [f"{JOURS_COURTS[j.weekday()]} {j:%d}" for j in jours]
               + ["Semaine 1", "Semaine 2", "Normales", "Supplémentaires", "État", "Anomalies"])
    lignes = [[f"<a href='/feuille?employe={e(f.employe.id)}&debut={debut}'>{e(f.employe.nom)}</a>"]
              + [h(x) for x in f.jours] + [h(f.semaines[0]), h(f.semaines[1]), h(f.normales), h(f.supplementaires),
                                            f.etat, " ; ".join(f.anomalies)] for f in liste]
    classes = ["ligne-anomalie" if f.anomalies else "ligne-approuvee" if f.etat != pt.A_APPROUVER else
               ("ligne-corrigee" if f.corrigee else "") for f in liste]
    total = sum((f.total for f in liste), pt.Decimal(0))
    etat = (f"{len(liste)} employé(s), {h(total) or '0'} h dont {h(sum((f.supplementaires for f in liste), pt.Decimal(0))) or '0'}"
            f" h supplémentaires — à approuver : {sum(1 for f in liste if f.etat == pt.A_APPROUVER and not f.anomalies)}, "
            f"approuvées : {sum(1 for f in liste if f.etat != pt.A_APPROUVER)}, avec anomalies : "
            f"{sum(1 for f in liste if f.anomalies)}. Rose : anomalie à corriger ; jaune : pointage corrigé par le gérant ;"
            " vert : approuvée. Heures supplémentaires au-delà de 40 h par semaine ; pauses pointées non payées.")
    avant, apres = debut - timedelta(days=pt.JOURS_PERIODE), debut + timedelta(days=pt.JOURS_PERIODE)
    barre = (f"<form method='post' class='barre-onglet'>{csrf(ctx)}<input type='hidden' name='debut' value='{debut}'>"
             f"<a class='ouvrir' href='?debut={avant}'>◀</a><strong class='periode'>Période de paie du {debut} au {fin}"
             f"</strong><a class='ouvrir' href='?debut={apres}'>▶</a><button name='action' value='Approuver'>✔ Approuver "
             "les feuilles sans anomalie</button><a class='ouvrir' href='/employes'>👥 Employés et NIP…</a></form>")
    tableau_html = tableau_section(Section(f"Période de paie du {debut} au {fin}", entetes, lignes, classes=classes,
                                           html={0}))
    corps = (message + barre + f"<p class='note'>{e(etat)}</p>" + tableau_html
             + "<p class='note'>Cliquez sur un employé pour ses pointages et les corrections (« Pointages de "
               "l'employé… »).</p>")
    return Reponse(corps=page(ctx, "Feuilles de temps", corps))


def tableau_gerant(ctx: Contexte) -> Reponse:
    from ..paquet3 import dossier_tableau

    chemin = dossier_tableau(ctx.racine, ctx.config) / "tableau_du_gerant.html"
    if not chemin.exists():
        return Reponse(corps=page(ctx, "Tableau du gérant", "<p>Le tableau est écrit chaque nuit par le traitement "
                                                            "automatique : il n'existe pas encore.</p>"))
    return Reponse(corps=chemin.read_text(encoding="utf-8"), style_en_ligne=True)


# --------------------------------------------------------------------------------------------- statistiques
def _lire_clover(ctx: Contexte, du: date, au: date):
    """Ventes Clover de la période (point de vente n° 1), gardées DUREE_MEMOIRE secondes."""
    from .. import statistiques_clover as sc
    from ..points_vente import cache_clover, client

    cle = (du, au)
    gardee = ctx.app.memoire.get(cle)
    if gardee and time.time() - gardee[0] < DUREE_MEMOIRE:
        return gardee[1]
    d = sc.lire(client(ctx.racine), du, au, cache=cache_clover(ctx.racine))
    ctx.app.memoire[cle] = (time.time(), d)
    return d


def _valeurs(d) -> dict[str, object]:
    from .. import statistiques_clover as sc

    return {nom: valeur for nom, valeur in sc.resume_rapide(d)["Résumé"][1]}


def statistiques(ctx: Contexte) -> Reponse:
    from .. import statistiques_clover as sc

    nom = ctx.req.query.get("periode", "Aujourd'hui")
    if nom not in sc.PERIODES:
        nom = "Aujourd'hui"
    du, au = sc.periode(nom)
    cdu, cau, libelle = sc.comparaison(du, au, nom)
    filtres = {}
    if not ctx.voit_tous():  # statistiques verrouillées sur l'employé de ce compte (règle du 2026-10-30)
        moi = ctx.employe()
        if moi is None:
            return Reponse(corps=page(ctx, "Statistiques", sans_employe(ctx)))
        filtres = {"Employé": moi.nom}
    options = "".join(f"<option{' selected' if p == nom else ''}>{e(p)}</option>" for p in sc.PERIODES)
    corps = (f"<form class='ligne' method='get'><div><label for='periode'>Période</label><select id='periode' "
             f"name='periode'>{options}</select></div><button class='second' type='submit'>Afficher</button></form>")
    try:
        d = sc.filtrer(_lire_clover(ctx, du, au), filtres)
        avant = sc.filtrer(_lire_clover(ctx, cdu, cau), filtres)
    except (Exception, SystemExit) as erreur:  # noqa: BLE001 — Clover injoignable : message clair
        ctx.app.noter(f"Clover : {erreur!r}")
        return Reponse(corps=page(ctx, "Statistiques", corps + "<p class='erreur'>Clover ne répond pas : réessayez "
                                                               "dans un moment.</p>"))
    ici, la = _valeurs(d), _valeurs(avant)
    cartes = ""
    for cle, est_argent in (("Ventes nettes (articles)", True), ("Commandes payées", False),
                            ("Panier moyen", True), ("Taxes encaissées", True), ("Rabais", True),
                            ("Remboursements (articles)", True)):
        v, w = ici.get(cle), la.get(cle)
        texte = argent(v) if est_argent else f"{v}"
        variation = ""
        if isinstance(v, (int, Decimal)) and isinstance(w, (int, Decimal)) and v > 0 and w > 0:  # pas les rabais
            pct = (Decimal(v) - Decimal(w)) / abs(Decimal(w)) * 100
            variation = (f"<div class='d {'hausse' if pct >= 0 else 'baisse'}'>{'▲' if pct >= 0 else '▼'} "
                         f"{abs(pct):.1f} % vs {e(libelle)}</div>").replace(".", ",")
        cartes += f"<div class='carte'><div class='t'>{e(cle)}</div><div class='v'>{texte}</div>{variation}</div>"
    corps += f"<p class='note'>Du {du:%d/%m/%Y} au {au:%d/%m/%Y}</p><div class='cartes'>{cartes}</div>"
    etiquettes, valeurs = sc.series(d, du, au)
    plus_haut = max((v for v in valeurs), default=Decimal(0)) or Decimal(1)
    lignes = [[e(x), f"<progress max='100' value='{int(v / plus_haut * 100)}'></progress>", argent(v)]
              for x, v in zip(etiquettes, valeurs) if v]
    if lignes:
        corps += f"<h2>Ventes nettes par {'heure' if du == au else 'jour'}</h2>" + tableau(
            ["Heure" if du == au else "Jour", "", "Ventes nettes"], lignes, {2})
    return Reponse(corps=page(ctx, "Statistiques des ventes", corps))


# --------------------------------------------------------------------------------------------- aide et renvoi
def aide(ctx: Contexte) -> Reponse:
    """Guide de configuration et FAQ : mêmes textes que l'application Windows (aide.py)."""
    from .. import aide as textes

    guide = ctx.req.query.get("page") == "guide"
    blocs = (textes.GUIDE if guide else textes.FAQ)["fr"]
    corps, titre = "", "Guide de configuration" if guide else "Aide / FAQ"
    for bloc in blocs:
        genre, texte = bloc[0], str(bloc[-1])
        if genre == "titre":
            titre = texte
        elif genre == "sous_titre":
            corps += f"<h2>{e(texte)}</h2>"
        elif genre == "question":
            corps += f"<p class='q'>{e(texte)}</p>"
        elif genre == "puce":
            corps += f"<ul><li>{e(texte)}</li></ul>"
        elif genre == "etape":
            corps += f"<p><strong>{e(bloc[1]) if len(bloc) > 2 else '•'}</strong> {e(texte)}</p>"
        else:
            corps += f"<p class='{'note' if genre == 'note' else ''}'>{e(texte)}</p>"
    return Reponse(corps=page(ctx, titre, f"<div class='aide'>{corps}</div>"))


def complete(ctx: Contexte) -> Reponse:
    """Entrée du menu pas encore refaite en page web : renvoi à l'application complète."""
    from .menu import entrees

    titre = ctx.req.query.get("f", "")
    permises = {t for _n, _i, lignes in entrees(ctx.reg, ctx.u) for _ic, t, _a in lignes}
    if titre not in permises:
        return Reponse(403, page(ctx, "Accès refusé", "<p>Votre profil n'a pas accès à cette fonction.</p>"))
    corps = (f"<div class='carte'><p>« {e(titre)} » s'ouvre pour l'instant dans l'<strong>application complète</strong>, "
             "avec le même affichage et les mêmes droits que sur le poste du bureau :</p><ol>"
             "<li>fermez cette fenêtre ;</li><li>relancez le <strong>client MVOGMBI_Sync</strong> ;</li>"
             "<li>cliquez sur <strong>« Application complète (Bureau à distance) »</strong>, puis ouvrez MVOGMBI_Sync "
             "avec votre nom et votre mot de passe.</li></ol><p class='note'>Cette fonction arrive ici, en page web, "
             "par étapes (rubrique Paie faite).</p></div>")
    return Reponse(corps=page(ctx, titre, corps))


# --------------------------------------------------------------------------------------------- compte
def mot_de_passe(ctx: Contexte) -> Reponse:
    from ..utilisateurs import ErreurUtilisateur, Registre

    message = ""
    if ctx.req.methode == "POST":
        nouveau = ctx.req.champ("nouveau")
        if nouveau != ctx.req.champ("confirmation"):
            message = "<p class='erreur'>La confirmation ne correspond pas.</p>"
        else:
            with ctx.app.ecriture:
                reg = Registre(ctx.racine)
                if reg.verifier(ctx.u.nom, ctx.req.champ("actuel")) is None:
                    message = "<p class='erreur'>Mot de passe actuel incorrect.</p>"
                else:
                    try:
                        reg.changer_mot_de_passe(ctx.u.nom, nouveau)
                        reg.enregistrer()
                        ctx.app.sessions.fermer_compte(ctx.u.nom)
                        return redirection("/connexion")
                    except ErreurUtilisateur as erreur:
                        message = f"<p class='erreur'>{e(erreur)}</p>"
    corps = (message + f"<form method='post' class='boite'>{csrf(ctx)}"
             "<label for='a'>Mot de passe actuel</label><input id='a' name='actuel' type='password' "
             "autocomplete='current-password' required><label for='n'>Nouveau mot de passe (6 caractères ou plus)"
             "</label><input id='n' name='nouveau' type='password' autocomplete='new-password' minlength='6' required>"
             "<label for='c'>Confirmation</label><input id='c' name='confirmation' type='password' "
             "autocomplete='new-password' required><button type='submit' name='action' value='Changer'>Changer le mot "
             "de passe</button></form><p class='note'>Toutes vos sessions se ferment : reconnectez-vous ensuite.</p>")
    return Reponse(corps=page(ctx, "Changer mon mot de passe", corps))


# --------------------------------------------------------------------------------------------- aiguillage
FONCTIONS = [
    Fonction("/", "Accueil", "accueil", lambda ctx: __import__("mvogmbi_sync.web.accueil", fromlist=["x"]
                                                              ).page_accueil(ctx), "🏠", "", toujours=True),
    Fonction("/manuel.pdf", "Manuel d'utilisation", None, lambda ctx: __import__(
        "mvogmbi_sync.web.accueil", fromlist=["x"]).manuel(ctx), "📖", "", toujours=True, menu=False),
    Fonction("/pointage", "Pointage des employés", "accueil", pointage, "⏱", "Paie"),
    Fonction("/horaire", "Mon horaire", "accueil", mon_horaire, "🗓", "Paie"),
    Fonction("/mes-heures", "Mes heures et mes paies", "accueil", mes_heures, "💵", "Paie", toujours=True),
    Fonction("/feuilles", "Feuilles de temps", "paiements", feuilles, "🗂", "Paie"),
    Fonction("/tableau", "Tableau du gérant (téléphone)", "automatisation", tableau_gerant, "📱", "Gérant"),
    Fonction("/mot-de-passe", "Changer mon mot de passe", None, mot_de_passe, "🔑", "Mon compte", toujours=True),
    Fonction("/aide", "Aide / FAQ", None, aide, "❓", "", toujours=True, menu=False),
    Fonction("/complete", "Application complète", None, complete, "🖥", "", toujours=True, menu=False),
]


# modules de pages des vagues (chacun : FONCTIONS, et WEB = titre de l'entrée du menu -> adresse)
MODULES = ["pages_paie", "consultations", "pages_compta", "pages_tresorerie", "pages_rapprochement", "pages_ria",
           "pages_ventes", "pages_documents", "pages_fournisseurs",
           "pages_achats", "pages_articles",
           "pages_catalogue", "pages_admin", "pages_traitement_paie",
           "pages_statistiques", "pages_rapports_web"]

_TOUTES: list[Fonction] = []


def toutes() -> list[Fonction]:
    """Pages de base + pages des modules des vagues, chargées au premier besoin (pas d'import circulaire : un module
    de pages importe celui-ci)."""
    if not _TOUTES:
        from . import taches

        liste = list(FONCTIONS)
        for nom in MODULES:
            liste += __import__(f"mvogmbi_sync.web.{nom}", fromlist=["FONCTIONS"]).FONCTIONS
        liste.append(Fonction("/tache", "Travail en cours", None, taches.page_tache, "⏳", "", toujours=True,
                              menu=False))
        _TOUTES.extend(liste)
    return _TOUTES


def trouver(chemin: str) -> Fonction | None:
    return next((f for f in toutes() if f.chemin == chemin), None)
