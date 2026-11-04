"""Mise en page de l'application web identique à l'application Windows (demande du propriétaire du 2026-11-03 :
« l'application web doit être exactement comme ceci », capture de l'accueil) : bandeau vert avec le logo, le nom du
marché et les deux lignes d'explication, liseré vert / rouge / jaune ; menu de gauche (« MENU », Accueil, rubriques,
Guide de configuration, Aide / FAQ, Manuel d'utilisation (PDF), puis la personne connectée, « Changer mon mot de
passe », « Se déconnecter », la langue, la version) ; accueil = carte « Mise en route » (les dix étapes, ✔ / ●,
« Ouvrir ») et texte « Bienvenue dans MVOGMBI_Sync » (aide.ACCUEIL) avec le logo pâli.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .serveur import Reponse, echapper as e

LOGO = Path(__file__).resolve().parent.parent / "ressources" / "logo.png"
# mêmes étapes que l'application Windows (interface.Application.ETAPES) : (page, n°, titre, description)
ETAPES = ((1, "1", "Clover", "Identifiant marchand et jeton API"),
          (2, "2", "Sage 50", "Fichier d'entreprise et mots de passe"),
          (3, "3", "Courriel", "Compte rendu après chaque nuit"),
          (4, "4", "Automatisation", "Tâche planifiée installée"),
          (5, "5", "Correspondance", "Articles Clover reliés à Sage"),
          (6, "6", "Premier import", "Une facture importée dans Sage"),
          (7, "7", "Encaissements", "Dépôts appliqués sur les factures"),
          (8, "8", "Factures fournisseurs", "Factures d'achat importées dans Sage"),
          (9, "9", "Paiements fournisseurs", "Boîte des avis de paiement reliée"),
          (10, "10", "Rapprochement bancaire", "Relevés Desjardins chargés"))


def entete() -> str:
    return ("<header class='bandeau'><a class='logo' href='/'><img src='/logo.png' alt='MVOG-MBI'></a><div>"
            "<div class='nom'>Marché MVOG-MBI Sherbrooke</div>"
            "<div class='sous'>Synchronisation des ventes Clover → Sage 50</div>"
            "<div class='expl'>Chaque nuit, les ventes Clover sont importées dans Sage 50 : une facture par jour, une "
            "pour la fin de semaine.</div></div></header><div class='filet'></div>")


def pied_menu(ctx) -> str:
    from ..aide import COPYRIGHT, VERSION

    return (f"<div class='personne'><div class='qui'>👤&nbsp; {e(ctx.u.nom)}</div><div class='profil'>"
            f"{e(ctx.u.profil)}</div><a href='/mot-de-passe'>Changer mon mot de passe</a>"
            f"<form method='post' action='/deconnexion'><input type='hidden' name='csrf' value='{e(ctx.session.csrf)}'>"
            "<button class='lien-texte' type='submit'>Se déconnecter</button></form></div>"
            "<div class='langue'>🌐 Langue / Language<div class='choix'>Français</div></div>"
            f"<div class='version'>MVOGMBI_Sync {e(VERSION)}<br>{e(COPYRIGHT)}<br>Tous droits réservés.</div>")


# --------------------------------------------------------------------------------------------- mise en route
def _registre(racine: Path, nom: str, etats, texte: str) -> tuple[bool, str]:
    chemin = racine / "donnees" / nom
    try:
        elements = json.loads(chemin.read_text(encoding="utf-8")) if chemin.exists() else []
    except (OSError, ValueError):
        return False, ""
    if isinstance(elements, dict):
        elements = next((v for v in elements.values() if isinstance(v, list)), list(elements.values()))
    n = sum(1 for x in elements if isinstance(x, dict) and x.get("etat") in etats)
    return n > 0, texte.format(n=n) if n else ""


def etats_etapes(racine: Path, config: dict) -> dict[int, tuple[bool, str]]:
    """Même calcul que l'application Windows (Application._etat_etapes)."""
    from .. import coffre

    def present(nom) -> bool:
        try:
            return coffre.present(nom)
        except Exception:  # noqa: BLE001 — coffre illisible : étape non faite
            return False

    c = config
    etats = {1: (bool(c.get("clover", {}).get("merchant_id")) and present(coffre.CLOVER_JETON), ""),
             3: (bool(c.get("courriel", {}).get("serveur") and c["courriel"].get("destinataires"))
                 and present(coffre.COURRIEL), "")}
    try:
        from .. import planification

        etats[4] = ("non installée" not in planification.etat(), "")
    except Exception:  # noqa: BLE001
        etats[4] = (False, "")
    fichier = c.get("sage_import", {}).get("fichier_entreprise", "")
    sage_ok = bool(fichier) and Path(fichier).is_file() and present(coffre.SAGE_LECTURE) and present(coffre.SAGE_IMPORT)
    etats[2] = (sage_ok, Path(fichier).name if sage_ok else "")
    etats[5] = ((racine / "donnees" / "correspondance_articles.xlsx").exists(), "")
    journal, derniere = racine / "donnees" / "journal_imports.csv", ""
    if journal.exists():
        lignes = [l for l in journal.read_text(encoding="utf-8-sig").splitlines()[1:] if ";importée" in l]
        derniere = lignes[-1].split(";")[1] if lignes else ""
    etats[6] = (bool(derniere), derniere)
    enc = c.get("encaissements", {})
    log = racine / "donnees" / "journal_automatique.log"
    encaisse = log.exists() and bool(re.search(r"[1-9]\d* dépôt\(s\) encaissé",
                                               log.read_text(encoding="utf-8", errors="replace")))
    etats[7] = (bool(enc.get("date_depart")) and encaisse,
                f"Depuis le {enc['date_depart']}" if enc.get("date_depart") and encaisse else "")
    etats[8] = _registre(racine, "factures_fournisseurs.json", ("Importée", "Importée dans Sage"),
                         "{n} facture(s) importée(s)")
    b = c.get("boite_paiements", {})
    boite = bool(b.get("serveur") and b.get("utilisateur")) and present(coffre.BOITE_PAIEMENTS)
    saisis = _registre(racine, "paiements_fournisseurs.json", ("Saisi dans Sage", "Déjà dans Sage"),
                       "{n} paiement(s) saisi(s)")[1]
    etats[9] = (boite, saisis if boite else "")
    dossier = racine / "donnees" / "releves_desjardins"
    releves = len(list(dossier.glob("*.pdf"))) if dossier.is_dir() else 0
    etats[10] = (releves > 0, f"{releves} relevé(s) chargé(s)" if releves else "")
    return etats


def mise_en_route(ctx) -> str:
    from .menu import PAGES_MENU, adresse_entree, cle_page

    permises = ctx.reg.pages(ctx.u)
    etapes = [x for x in ETAPES if ctx.u.est_admin or cle_page(x[0]) in permises]
    if not etapes:
        return ""
    etats = etats_etapes(ctx.racine, ctx.config)
    faites = sum(1 for p, *_ in etapes if etats.get(p, (False, ""))[0])
    cases = ""
    for page, numero, titre, description in etapes:
        fait, precision = etats.get(page, (False, ""))
        cases += (f"<div class='etape'><span class='{'fait' if fait else 'afaire'}'>{'✔' if fait else '●'}</span>"
                  f"<div><div class='t'>{numero}. {e(titre)}</div><div class='d'>{e(precision or description)}</div>"
                  f"</div><a class='ouvrir' href='{e(adresse_entree(PAGES_MENU[page][1]))}'>Ouvrir</a></div>")
    return ("<section class='mise-en-route'><h2><span class='coche'>✓</span> Mise en route</h2>"
            "<p class='note'>Dix étapes, une par page, pour une gestion entièrement automatique. Chaque étape passe au "
            "vert (✔) quand elle est faite.</p>"
            f"<p class='progres'>{faites} étape(s) sur {len(etapes)} terminée(s)</p>"
            f"<div class='etapes'>{cases}</div></section>")


def bienvenue() -> str:
    from ..aide import ACCUEIL

    html = ""
    puces = []

    def fermer():
        nonlocal html, puces
        if puces:
            html += "<ul>" + "".join(f"<li>{e(p)}</li>" for p in puces) + "</ul>"
            puces = []

    for bloc in ACCUEIL["fr"]:
        genre, texte = bloc[0], str(bloc[-1])
        if genre == "puce":
            puces.append(texte)
            continue
        fermer()
        if genre == "titre":
            html += f"<h1>{e(texte)}</h1>"
        elif genre == "sous_titre":
            html += f"<h2>{e(texte)}</h2>"
        elif genre == "etape":
            html += f"<p><strong>{e(bloc[1]) if len(bloc) > 2 else '•'}</strong> {e(texte)}</p>"
        else:
            html += f"<p>{e(texte)}</p>"
    fermer()
    return f"<section class='bienvenue'>{html}</section>"


def page_accueil(ctx) -> Reponse:
    from .pages import _document
    from .menu import barre

    return Reponse(corps=_document("Accueil", mise_en_route(ctx) + bienvenue(), ctx, barre(ctx)))


def logo(_app, _req) -> Reponse:
    return Reponse(corps=LOGO.read_bytes(), type="image/png", entetes={"Cache-Control": "max-age=86400"})


def manuel(ctx) -> Reponse:
    """Manuel d'utilisation du profil (mêmes chapitres que dans l'application Windows)."""
    from ..manuel import manuel_du_profil
    from .menu import cle_page
    from .pages import page

    permises = None if ctx.u.est_admin else {i for i in range(15) if cle_page(i) in ctx.reg.pages(ctx.u)}
    try:
        chemin = manuel_du_profil(ctx.racine, permises, ctx.u.profil, "fr")
    except Exception as erreur:  # noqa: BLE001
        ctx.app.noter(f"Manuel : {erreur!r}")
        chemin = None
    if chemin is None:
        return Reponse(404, page(ctx, "Manuel d'utilisation", "<p>Le manuel d'utilisation est introuvable sur le "
                                                               "serveur.</p>"))
    return Reponse(corps=Path(chemin).read_bytes(), type="application/pdf",
                   entetes={"Content-Disposition": "inline; filename=Manuel_MVOGMBI_Sync.pdf"})


STYLE_ACCUEIL = """
header.bandeau { background: var(--vert-vif); color: #fff; display: flex; align-items: center; gap: 18px;
                 padding: 12px 18px; }
header.bandeau .logo { background: #fff; padding: 4px 6px; display: block; line-height: 0; }
header.bandeau .logo img { height: 78px; width: auto; }
header.bandeau .nom { font-size: 27px; font-weight: 600; }
header.bandeau .sous { font-size: 16px; font-weight: 700; color: #eaf7ee; margin-top: 2px; }
header.bandeau .expl { font-size: 13px; color: #cdebd6; margin-top: 4px; }
.filet { height: 5px; background: linear-gradient(90deg, var(--vert) 0 33.3%, var(--rouge) 33.3% 66.6%,
         var(--jaune) 66.6%); }
nav.menu .titre-menu { font-size: 11px; font-weight: 700; color: var(--gris); letter-spacing: .08em; padding: 6px 12px 8px; }
nav.menu .personne { border-top: 1px solid var(--bord); margin-top: 18px; padding: 12px 12px 6px; font-size: 14px; }
nav.menu .personne .qui { font-weight: 600; }
nav.menu .personne .profil { color: var(--gris); font-size: 13px; padding-left: 22px; margin-bottom: 4px; }
nav.menu .personne a, nav.menu .personne .lien-texte { display: inline; padding: 0 0 0 22px; border: 0; font-size: 13px;
       color: var(--vert); text-decoration: underline; background: none; font-weight: 400; cursor: pointer; }
nav.menu .personne form { margin: 4px 0 0; }
nav.menu .langue { font-size: 13px; color: var(--gris); padding: 8px 12px; }
nav.menu .langue .choix { margin-top: 6px; background: var(--carte); border: 1px solid var(--bord); border-radius: 6px;
       padding: 7px 10px; color: var(--texte); }
nav.menu .version { font-size: 12px; color: var(--gris); padding: 8px 12px; line-height: 1.6; }
section.mise-en-route, section.bienvenue { background: var(--carte); border: 1px solid var(--bord); padding: 14px 22px;
       margin-bottom: 14px; }
section.mise-en-route { border-left: 4px solid var(--vert-vif); }
section.mise-en-route h2 { margin: 4px 0 8px; font-size: 17px; font-weight: 600; }
.coche { display: inline-block; background: var(--vert-vif); color: #fff; width: 24px; height: 22px; text-align: center;
         margin-right: 10px; font-size: 14px; }
.progres { color: var(--vert); font-size: 13px; font-weight: 600; }
.etapes { display: grid; grid-template-columns: repeat(2, 1fr); grid-auto-flow: column; grid-template-rows: repeat(5, auto);
          column-gap: 24px; row-gap: 8px; }
.etape { display: flex; align-items: center; gap: 12px; }
.etape > div { flex: 1; } .etape .t { font-weight: 600; font-size: 14px; } .etape .d { color: var(--gris); font-size: 13px; }
.etape .fait { color: var(--vert-vif); font-size: 20px; font-weight: 700; width: 22px; text-align: center; }
.etape .afaire { color: var(--jaune); font-size: 18px; width: 22px; text-align: center; }
a.ouvrir { border: 1px solid #b9c7be; border-radius: 14px; padding: 4px 12px; font-size: 13px; color: var(--vert);
           text-decoration: none; font-weight: 600; background: var(--carte); }
a.ouvrir:hover { border-color: var(--vert); }
section.bienvenue { background-image: url('/logo.png'); background-repeat: no-repeat; background-position: right 40px top 40px;
                    background-size: 200px auto; }
section.bienvenue::before { content: ""; }
section.bienvenue h1 { font-size: 28px; color: var(--vert-vif); font-weight: 600; }
section.bienvenue h2 { color: var(--vert); font-size: 19px; font-weight: 600; margin-top: 24px; }
section.bienvenue p, section.bienvenue ul { max-width: 620px; font-size: 14px; }
@media (max-width: 820px) {
  header.bandeau .logo img { height: 48px; } header.bandeau .nom { font-size: 19px; }
  header.bandeau .expl { display: none; }
  .etapes { grid-template-columns: 1fr; grid-auto-flow: row; grid-template-rows: none; }
  section.bienvenue { background-image: none; }
}
"""
