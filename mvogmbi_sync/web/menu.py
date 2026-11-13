"""Menu de l'application web = menu de l'application Windows (demande du propriétaire du 2026-11-03 : « on doit
avoir le même affichage et fonctionnalité dans le client ») : mêmes rubriques, mêmes entrées, dans le même ordre
(interface.MENU_GROUPES), et mêmes droits par profil. Une entrée déjà refaite en page web s'ouvre ici ; les autres
mènent à une page qui renvoie à l'application complète (client MVOGMBI_Sync > « Application complète (Bureau à
distance) ») en attendant leur page web.
"""

from __future__ import annotations

from urllib.parse import quote

from ..utilisateurs import PAGES, UTILISATEURS
from .serveur import echapper as e

# pages de l'application Windows (index de interface.py) : icône et libellé du menu
PAGES_MENU = {0: ("🏠", "Accueil"), 1: ("🛒", "Clover"), 2: ("📒", "Sage 50"), 3: ("📧", "Courriel"),
              4: ("⏰", "Automatisation"), 5: ("🔗", "Correspondance"), 6: ("📊", "Ventes Clover → factures Sage"),
              7: ("💰", "Encaissements"), 8: ("🧾", "Factures fournisseurs"), 9: ("💸", "Paiements fournisseurs"),
              10: ("🏦", "Rapprochement"), 11: ("📊", "Rapports"), 12: ("📘", "Guide de configuration"),
              13: ("❓", "Aide / FAQ"), 14: ("👥", "Utilisateurs")}
# entrées déjà en page web (titre de l'entrée du menu -> adresse)
WEB = {"Accueil": "/", "Pointage des employés": "/pointage", "Mes heures et mes paies": "/mes-heures",
       "Feuilles de temps": "/feuilles", "Planning mensuel": "/planning", "Mon horaire": "/horaire",
       "Employés et NIP": "/employes", "Jours fériés et congés": "/conges", "Reporting": "/statistiques",
       "Tableau du gérant (téléphone)": "/tableau", "Guide de configuration": "/aide?page=guide",
       "Aide / FAQ": "/aide?page=faq"}
TOUJOURS = {"Mes heures et mes paies", "Guide de configuration", "Aide / FAQ"}


def adresse_entree(titre: str) -> str:
    """Page web d'une entrée du menu (consultations comprises), sinon renvoi à l'application complète."""
    from .pages import MODULES

    if titre in WEB:
        return WEB[titre]
    for nom in MODULES:
        adresse = getattr(__import__(f"mvogmbi_sync.web.{nom}", fromlist=["WEB"]), "WEB", {}).get(titre)
        if adresse:
            return adresse
    return "/complete?f=" + quote(titre)


def cle_page(index: int) -> str:
    return PAGES[index] if index < len(PAGES) else UTILISATEURS


def groupes() -> list:
    from ..interface import MENU_GROUPES

    return MENU_GROUPES


def entrees(reg, u) -> list[tuple[str, str, list[tuple[str, str, str]]]]:
    """[(rubrique, icône, [(icône, titre, adresse)])] permises au compte, dans l'ordre du menu Windows."""
    from .pages import Fonction, permis

    resultat = []
    for nom, icone, elements in groupes():
        lignes = []
        for el in elements:
            if isinstance(el, int):
                ic, titre = PAGES_MENU.get(el, ("•", cle_page(el)))
                f = Fonction("", cle_page(el), cle_page(el), None, ic, "")
                if el == 14:
                    ok = u.est_admin
                else:
                    fonctions = reg.permises(u)
                    ok = u.est_admin or titre in TOUJOURS or (cle_page(el) in fonctions if fonctions is not None
                                                             else cle_page(el) in reg.pages(u))
            else:
                ic, titre, page = el[0], el[1], el[2]
                f = Fonction("", titre, cle_page(page), None, ic, "")
                ok = titre in TOUJOURS or permis(reg, u, f)
            if ok:
                lignes.append((ic, titre, adresse_entree(titre)))
        if lignes:
            resultat.append((nom, icone, lignes))
    return resultat


def barre(ctx) -> str:
    """Menu de gauche (sur téléphone : en haut, replié) ; rubrique de la page affichée ouverte."""
    chemin = ctx.req.chemin + (f"?page={ctx.req.query.get('page', 'faq')}" if ctx.req.chemin == "/aide" else "")
    actuel = ctx.req.query.get("f", "") if ctx.req.chemin == "/complete" else ""
    html = ""
    for nom, icone, lignes in entrees(ctx.reg, ctx.u):
        liens = ""
        ouvert = False
        for ic, titre, adresse in lignes:
            actif = adresse == chemin or (actuel and titre == actuel)
            ouvert = ouvert or actif
            classe = ("actif " if actif else "") + ("" if not adresse.startswith("/complete") else "ailleurs")
            liens += f"<a class='{classe}' href='{e(adresse)}'>{ic}&nbsp; {e(titre)}</a>"
        if not nom:
            html += f"<div class='seul'>{liens}</div>"
        else:
            html += (f"<details{' open' if ouvert else ''}><summary>▸ {icone}&nbsp; {e(nom)}</summary>"
                     f"{liens}</details>")
    from .accueil import pied_menu

    html = ("<div class='titre-menu'>MENU</div>" + html
            + "<div class='seul'><a href='/manuel.pdf'>📖&nbsp; Manuel d'utilisation (PDF)</a></div>")
    # deux fois le même menu, sans script : ouvert à gauche sur PC, replié derrière « ☰ Menu » sur téléphone
    return (f"<nav class='menu large'>{html}{pied_menu(ctx)}</nav>"
            f"<nav class='menu etroit'><details class='tout'><summary>☰ Menu</summary>{html}{pied_menu(ctx)}"
            "</details></nav>")


STYLE_MENU = """
.cadre { display: flex; align-items: flex-start; min-height: calc(100vh - 54px); }
nav.menu { width: 318px; flex: none; background: var(--menu); border-right: 1px solid var(--bord); padding: 10px 8px;
           position: sticky; top: 0; max-height: 100vh; overflow-y: auto; }
nav.menu summary { cursor: pointer; padding: 7px 10px; font-weight: 700; border-radius: 8px; list-style: none; }
nav.menu summary::-webkit-details-marker { display: none; }
nav.menu summary { font-weight: 500; }
nav.menu.etroit { display: none; }
nav.menu a { display: block; padding: 6px 12px 6px 26px; border-radius: 8px; color: var(--texte); text-decoration: none;
             font-size: 15px; border-left: 4px solid transparent; }
nav.menu .seul a { padding-left: 12px; font-weight: 600; }
nav.menu a:hover, nav.menu summary:hover { background: var(--menu-survol); }
nav.menu a.actif { background: var(--menu-actif); border-left-color: var(--vert-vif); font-weight: 500; }
nav.menu a.ailleurs { color: var(--gris); }
.cadre main { flex: 1; min-width: 0; margin: 0; max-width: none; padding: 20px 24px; background: var(--fond-page); }
/* PC : la fenêtre ne défile jamais (demande du propriétaire du 2026-11-12) : bandeau fixe, menu et page défilent
   chacun dans leur cadre ; la liste principale remplit la hauteur (/filtres.js remplirListe) */
@media (min-width: 821px) {
  body:has(> .cadre) { height: 100vh; display: flex; flex-direction: column; overflow: hidden; }
  body:has(> .cadre) > :not(.cadre) { flex: none; }
  body:has(> .cadre) > .cadre { flex: 1; min-height: 0; align-items: stretch; }
  .cadre nav.menu.large { position: static; max-height: none; overflow-y: auto; }
  .cadre main { overflow: auto; }
}
@media (max-width: 820px) {
  .cadre { display: block; }
  nav.menu { width: auto; position: static; max-height: none; border-right: 0; border-bottom: 1px solid var(--bord); }
  nav.menu.large { display: none; }
  nav.menu.etroit { display: block; padding: 6px 8px; }
}
"""
