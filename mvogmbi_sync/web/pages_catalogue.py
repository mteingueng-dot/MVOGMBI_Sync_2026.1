"""7e vague de l'application web (suite) : Articles Clover (liste, UGS qui ne sont pas des dates effacées),
correspondance Clover -> Sage (modifier une ligne, confirmer, mettre à jour), créer un article dans Clover et Sage,
inventaire Clover et Sage (fichier à remplir, saisie du fichier compté), inventaire tournant, transferts entre
magasins. Mêmes fonctions que les fenêtres Windows ; travaux longs en arrière-plan.
"""

from __future__ import annotations

import csv
import time
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import quote

from .consultations import Section, tableau_section
from .pages import Contexte, Fonction, argent, csrf, page, tableau
from .pages_compta import _message, action_permise
from .serveur import Reponse, echapper as e, redirection

LIMITE = 300


def _telecharger(chemin: Path, nom: str = "") -> Reponse:
    pdf = Path(chemin).suffix.lower() == ".pdf"
    return Reponse(corps=Path(chemin).read_bytes(),
                   type="application/pdf" if pdf else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                   entetes={"Content-Disposition": f"attachment; filename=\"{nom or Path(chemin).name}\""})


# --------------------------------------------------------------------------------------------- articles Clover
def articles_clover(ctx: Contexte) -> Reponse:
    """Comme fenetre_articles_clover.FenetreArticlesClover : « Rechercher : », Catégorie, Type de prix, Stock,
    « ✖ Réinitialiser les filtres », « 🔄 Actualiser », « 🧹 Effacer les UGS qui ne sont pas des dates… » (liste à
    cocher, puis UGS vidée dans Clover et notée dans donnees/journal_ugs_effacees.csv) ; mêmes 9 colonnes
    (`ligne_article`), tri par colonne, quantité négative en rouge, « n article(s) affiché(s) sur m »."""
    from .. import cache_lectures
    from ..correspondance import normaliser
    from ..creation_articles import TYPES_PRIX
    from ..fenetre_articles_clover import COLONNES, STOCKS, TOUS, _texte, ligne_article
    from ..peremption import lire_date
    from . import taches

    if ctx.req.query.get("actualiser"):
        cache_lectures.vider("clover:inventaire")
    try:
        articles = cache_lectures.inventaire_clover(ctx.racine)
    except (Exception, SystemExit) as erreur:  # noqa: BLE001 — tableau vide avec ses colonnes
        ctx.app.noter(f"Articles Clover : {erreur!r}")
        articles = []
        ctx.absents.add("Clover")
    ugs_mode = bool(ctx.req.query.get("ugs") or ctx.req.champ("ugs"))
    message = ""
    if ctx.req.methode == "POST":
        choisis = [a for a in articles if a["id"] in set(ctx.req.champs("id"))]
        if not choisis:
            message = _message(erreur="Cochez au moins un article.")
        else:
            def effacer(journal):
                from ..points_vente import client

                c = client(ctx.racine)
                chemin = ctx.racine / "donnees" / "journal_ugs_effacees.csv"
                chemin.parent.mkdir(parents=True, exist_ok=True)
                nouveau = not chemin.exists()
                erreurs = []
                with chemin.open("a", newline="", encoding="utf-8-sig") as f:
                    ecrivain = csv.writer(f, delimiter=";")
                    if nouveau:
                        ecrivain.writerow(["Date", "ID Clover", "Article", "UGS effacée"])
                    for n, a in enumerate(choisis, 1):
                        try:
                            c.regler_ugs(a["id"], "")
                            ecrivain.writerow([datetime.now().isoformat(timespec="seconds"), a["id"], a.get("name"),
                                               a.get("sku")])
                        except Exception as exc:  # noqa: BLE001
                            erreurs.append(f"{a.get('name')} : {exc}")
                        journal(f"{n} / {len(choisis)}")
                cache_lectures.vider("clover:inventaire")
                return [f"{len(choisis) - len(erreurs)} UGS effacée(s) dans Clover."] + erreurs[:15]

            return taches.lancer(ctx, f"UGS effacées ({len(choisis)})", effacer, "/articles-clover")
    if ugs_mode:  # FenetreACocher « UGS qui ne sont pas des dates »
        noms = {a.get("id"): (a.get("name") or "").strip() for a in articles}
        lignes = [[f"<input type='checkbox' name='id' value='{e(a['id'])}' checked>", e(a["id"]), e(noms[a["id"]]),
                   e((a.get("sku") or "").strip())]
                  for a in sorted(articles, key=lambda a: noms.get(a.get("id"), "").casefold())
                  if (a.get("sku") or "").strip() and lire_date(a.get("sku")) is None]
        corps = (message + f"<p class='note'>{len(lignes)} article(s) Clover ont une UGS qui n'est pas une date "
                 "(JJ/MM/AAAA). Ces articles ont dans Clover une UGS qui n'est pas une date de péremption. Cochez celles "
                 "à effacer, puis lancez : l'UGS est vidée dans Clover ; chaque UGS effacée est notée dans "
                 "donnees/journal_ugs_effacees.csv.</p>"
                 f"<form method='post'>{csrf(ctx)}<input type='hidden' name='ugs' value='1'>"
                 + tableau_section(Section("UGS qui ne sont pas des dates", ["", "ID Clover", "Article", "UGS actuelle"],
                                           lignes, html=set(range(4))), limite=5000)
                 + "<div class='boutons'><button>Effacer dans Clover</button><a class='ouvrir' href='/articles-clover'>"
                   "◀ Retour à la liste</a></div></form>")
        return Reponse(corps=page(ctx, "Articles Clover", corps))
    rangees = [ligne_article(a, TYPES_PRIX) for a in articles]
    q, categorie = ctx.req.query.get("q", ""), ctx.req.query.get("categorie", "").strip()
    type_prix, stock = ctx.req.query.get("type_prix") or TOUS, ctx.req.query.get("stock") or STOCKS[0]
    try:
        colonne = min(max(int(ctx.req.query.get("tri", "1")), 0), len(COLONNES) - 1)
    except ValueError:
        colonne = 1
    inverse = ctx.req.query.get("ordre") == "desc"
    mots = normaliser(q).split()
    gardees = []
    for l in rangees:  # comme FenetreArticlesClover._gardees
        if mots and not all(m in normaliser(" ".join(_texte(v) for v in l)) for m in mots):
            continue
        if categorie and categorie.casefold() not in [c.strip().casefold() for c in l[8].split(",")]:
            continue
        if type_prix != TOUS and l[3] != type_prix:
            continue
        x = l[7]
        if (stock == STOCKS[1] and not (x is not None and x > 0)) or (stock == STOCKS[2] and x != 0) or (
                stock == STOCKS[3] and not (x is not None and x < 0)) or (stock == STOCKS[4] and x is not None):
            continue
        gardees.append(l)
    vides = {2: Decimal("-1e18"), 7: Decimal("-1e18"), 6: date.min}
    gardees.sort(key=lambda l: (l[colonne] if l[colonne] is not None else vides[colonne]) if colonne in vides
                 else str(l[colonne]).casefold(), reverse=inverse)
    categories = sorted({c.strip() for l in rangees for c in l[8].split(",") if c.strip()}, key=str.casefold)
    liste_cat = "<datalist id='categories'>" + "".join(f"<option value='{e(c)}'>" for c in categories) + "</datalist>"
    types = "".join(f"<option{' selected' if v == type_prix else ''}>{e(v)}</option>"
                    for v in [TOUS] + list(TYPES_PRIX.values()))
    stocks = "".join(f"<option{' selected' if v == stock else ''}>{e(v)}</option>" for v in STOCKS)
    tris = "".join(f"<option value='{n}'{' selected' if n == colonne else ''}>{e(titre)}</option>"
                   for n, (_c, titre, _l) in enumerate(COLONNES))
    barre = (f"<form method='get' class='barre-onglet'><div><label>Rechercher :</label><input name='q' value='{e(q)}' "
             f"size='26'></div><div><label>Catégorie</label><input name='categorie' list='categories' "
             f"value='{e(categorie)}' size='20'>{liste_cat}</div><div><label>Type de prix</label><select "
             f"name='type_prix'>{types}</select></div><div><label>Stock</label><select name='stock'>{stocks}</select>"
             f"</div><div><label>Trier par</label><select name='tri'>{tris}</select></div><div><label><input "
             f"type='checkbox' name='ordre' value='desc'{' checked' if inverse else ''}> décroissant</label></div>"
             "<button class='second'>Afficher</button><a class='ouvrir' href='/articles-clover'>✖ Réinitialiser les "
             "filtres</a><a class='ouvrir' href='/articles-clover?actualiser=1'>🔄 Actualiser</a><a class='ouvrir' "
             "href='/articles-clover?ugs=1'>🧹 Effacer les UGS qui ne sont pas des dates…</a></form>")
    lignes = [[e(_texte(v)) for v in l] for l in gardees]
    classes = ["negatif" if l[7] is not None and l[7] < 0 else "" for l in gardees]
    corps = (message + barre
             + tableau_section(Section("Articles Clover", [titre for _c, titre, _l in COLONNES], lignes,
                                       classes=classes, html=set(range(9)),
                                       note=f"{len(gardees)} article(s) affiché(s) sur {len(rangees)}"), limite=5000))
    return Reponse(corps=page(ctx, "Articles Clover", corps))


# --------------------------------------------------------------------------------------------- correspondance
def _chemin_correspondance(ctx: Contexte, pv=None) -> Path:
    from ..points_vente import fichier_correspondance

    return fichier_correspondance(ctx.racine, pv)


SUPPRIMES = "Supprimés ou renommés dans Clover"
FILTRES_CORRESPONDANCE = ["À traiter (À confirmer + Aucun)", SUPPRIMES, "Tous", "Confirmé", "Automatique",
                          "À confirmer", "Aucun"]
COULEURS_CORRESPONDANCE = {"Confirmé": "etat-applique", "À confirmer": "etat-a-saisir", "Aucun": "etat-ecart"}


def correspondance(ctx: Contexte) -> Reponse:
    """Comme page_correspondance.PageCorrespondance : point de vente, « Afficher : », « Rechercher : », « ⟳ Mettre à
    jour depuis Clover et Sage », raccourcis (Créer un article, Inventaire, Coûts Clover, Comptes Sage par catégorie,
    Transferts), compteurs, tableau coloré ; « Article sélectionné » (`?id=`) : informations, recherche d'article Sage,
    « ✔ Confirmer l'article choisi », « Accepter la proposition », « Retirer la confirmation », « 🆕 Créer l'article
    dans Sage ». Dans le navigateur, chaque décision est enregistrée tout de suite (copie de sécurité comme
    « Enregistrer les modifications »)."""
    from .. import correspondance as co
    from .pages_compta import _point_vente
    from . import taches

    pv, choix_pv, code = _point_vente(ctx)
    chemin = _chemin_correspondance(ctx, pv)
    filtre = ctx.req.query.get("filtre") or ctx.req.champ("filtre") or FILTRES_CORRESPONDANCE[0]
    q = ctx.req.query.get("q") if "q" in ctx.req.query else ctx.req.champ("q")
    ident = ctx.req.query.get("id") or ctx.req.champ("id")
    message = ""
    if ctx.req.methode == "POST":
        action = ctx.req.champ("action")
        if action == "Mettre à jour depuis Clover et Sage":
            def mettre_a_jour(journal):
                import os
                import subprocess

                from ..__main__ import commande_moteur

                commande = commande_moteur() + ["correspondance"] + (["--point-de-vente", str(code)] if pv else [])
                processus = subprocess.Popen(commande, cwd=ctx.racine, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                             text=True, encoding="utf-8", errors="replace",
                                             env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                for ligne in processus.stdout:
                    journal(ligne.rstrip())
                return "Correspondance mise à jour." if processus.wait() == 0 else "Mise à jour impossible."

            return taches.lancer(ctx, "Mise à jour de la correspondance", mettre_a_jour,
                                 f"/correspondance?pv={code}&filtre={filtre}")
        if action == "Enregistrer les modifications":  # chaque décision est déjà enregistrée en cliquant
            message = _message("✔ Correspondance enregistrée (chaque décision l'est dès son clic).")
        elif action in ("Confirmer l'article choisi", "Confirmer quand même", "Accepter la proposition",
                      "Retirer la confirmation"):
            message = _decider_correspondance(ctx, chemin, ident, action)
    lignes_c = co.lire_correspondances(chemin)
    from .pages_fournisseurs import _listes

    _noms, articles = _listes(ctx.racine)
    texte = co.normaliser(q or "")
    lien = f"pv={e(code)}&amp;filtre={e(filtre)}&amp;q={e(q or '')}"
    lignes, classes = [], []
    for c in lignes_c:
        if filtre.startswith("À traiter") and c.statut not in (co.A_CONFIRMER, co.AUCUN):
            continue
        if filtre in (co.CONFIRME, co.AUTOMATIQUE, co.A_CONFIRMER, co.AUCUN) and c.statut != filtre:
            continue
        if filtre == SUPPRIMES and c.methode not in (co.RENOMME, co.PERSONNALISE):
            continue
        if texte and texte not in co.normaliser(f"{c.nom_clover} {c.numero_sage} {c.description_sage}"):
            continue
        nom = c.nom_clover + ("  (supprimé de Clover)" if c.methode == co.RENOMME else "")
        lignes.append([e(c.statut), f"<a href='?{lien}&amp;id={e(c.id_clover)}'>{e(nom)}</a>"
                       + (" ◀" if c.id_clover == ident else ""), e(c.categorie_clover),
                       f"{c.ventes_30j:,.2f}".replace(",", " ").replace(".", ",") if c.ventes_30j else "",
                       e(c.numero_sage), e(c.description_sage)])
        classes.append(COULEURS_CORRESPONDANCE.get(c.statut, ""))
    compte = {s_: sum(1 for c in lignes_c if c.statut == s_) for s_ in (co.CONFIRME, co.AUTOMATIQUE, co.A_CONFIRMER,
                                                                         co.AUCUN)}
    compteurs = (f"{len(lignes_c)} articles Clover — Confirmé : {compte[co.CONFIRME]}   Automatique : "
                 f"{compte[co.AUTOMATIQUE]}   À confirmer : {compte[co.A_CONFIRMER]}   Aucun : {compte[co.AUCUN]}   •   "
                 f"affichés : {len(lignes)}" + ("" if articles else "   •   liste Sage absente : cliquez sur « Mettre "
                                                                    "à jour »"))
    options = "".join(f"<option{' selected' if f == filtre else ''}>{e(f)}</option>" for f in FILTRES_CORRESPONDANCE)
    barre = (f"<form method='get' class='barre-onglet'>{choix_pv}<div><label>Afficher :</label><select name='filtre'>"
             f"{options}</select></div><div><label>Rechercher :</label><input name='q' value='{e(q or '')}' size='20'>"
             "</div><button class='second'>Afficher</button></form>"
             f"<form method='post' class='barre-onglet'>{csrf(ctx)}<input type='hidden' name='pv' value='{e(code)}'>"
             f"<input type='hidden' name='filtre' value='{e(filtre)}'><button name='action' value='Mettre à jour depuis "
             "Clover et Sage'>⟳ Mettre à jour depuis Clover et Sage</button><a class='ouvrir' "
             f"href='?{lien}'>Recharger</a><a class='ouvrir' href='/creer-article'>🆕 Créer un article</a><a "
             "class='ouvrir' href='/inventaire'>📦 Inventaire</a><a class='ouvrir' href='/couts-clover'>💲 Coûts Clover "
             "depuis Sage</a><a class='ouvrir' href='/comptes-categories'>🧾 Comptes Sage par catégorie</a><a "
             "class='ouvrir' href='/transferts'>🔁 Transferts entre points de vente</a></form>")
    corps = ("<p class='sous-titre'>🔗 Correspondance des articles — chaque article Clover relié à son article Sage</p>"
             + message + barre + f"<p class='note'>{e(compteurs)}</p>"
             + tableau_section(Section("Correspondance des articles", ["Statut", "Article Clover", "Catégorie",
                                                                       "Ventes 30 j", "N° article Sage",
                                                                       "Description Sage"],
                                       lignes, classes=classes, html=set(range(6))), limite=3000)
             + _article_selectionne(ctx, lignes_c, ident, articles, code, filtre, q))
    return Reponse(corps=page(ctx, "Correspondance", corps))


def _article_selectionne(ctx: Contexte, lignes_c, ident, articles, code, filtre, q) -> str:
    from .. import correspondance as co

    c = next((x for x in lignes_c if x.id_clover == ident), None)
    if c is None:
        return ("<div class='carte'><h2>Article sélectionné</h2><p>Sélectionnez un article dans le tableau.</p><div "
                "class='ligne'><div class='large'><label>Chercher un article Sage :</label><input size='40' disabled>"
                "</div></div><div class='fiche-bas'><div class='factures'></div><div class='boutons-colonne'><button "
                "disabled>✔ Confirmer l'article choisi</button><button class='second' disabled>Accepter la proposition"
                "</button><button class='danger' disabled>Retirer la confirmation</button><button class='second' "
                "disabled>🆕 Créer l'article dans Sage</button><button class='accent' disabled>💾 Enregistrer les "
                "modifications</button></div></div></div>")  # comme la fenêtre Windows avant le choix d'une ligne
    recherche = ctx.req.query.get("recherche") if "recherche" in ctx.req.query else (
        c.description_sage if c.methode == co.RENOMME and c.description_sage else c.nom_clover)
    resultats = []
    texte = co.normaliser(recherche or "")
    if texte and articles:
        from rapidfuzz import fuzz, process

        normalises = [co.normaliser(f"{a.description} {a.numero}") for a in articles]
        for _, _score, n in process.extract(texte, normalises, scorer=fuzz.token_set_ratio, limit=15):
            a = articles[n]
            alerte = "  (autre format)" if co.conflit_format(c.nom_clover, a.description) else ""
            resultats.append(f"<label class='facture'><input type='radio' name='numero' value='{e(a.numero)}'"
                             f"{' checked' if not resultats else ''}> <code>{e(a.numero):<16} {e(a.description)}  ["
                             f"{e(a.compte_revenus or 'sans compte')}]{e(alerte)}</code></label>")
    info = (f"Clover : {c.nom_clover}   (catégorie {c.categorie_clover or '—'}, ID {c.id_clover})\nSage : "
            f"{c.numero_sage or '—'} {c.description_sage}   •   statut {c.statut}, méthode {c.methode or '—'}"
            + (f"\nAutres suggestions : {c.suggestions}" if c.suggestions else ""))
    cache = (f"{csrf(ctx)}<input type='hidden' name='pv' value='{e(code)}'><input type='hidden' name='filtre' "
             f"value='{e(filtre)}'><input type='hidden' name='q' value='{e(q or '')}'><input type='hidden' name='id' "
             f"value='{e(c.id_clover)}'>")
    creer = ("" if c.id_clover.startswith("nom:") else
             f"<a class='ouvrir' href='/creer-article?nom={quote(c.nom_clover)}&amp;id_clover={quote(c.id_clover)}"
             f"&amp;categorie={quote(c.categorie_clover or '')}'>🆕 Créer l'article dans Sage</a>")
    return (f"<div class='carte'><h2>Article sélectionné</h2><pre class='saisie'>{e(info)}</pre>"
            f"<form method='get' class='ligne'><input type='hidden' name='pv' value='{e(code)}'><input type='hidden' "
            f"name='filtre' value='{e(filtre)}'><input type='hidden' name='q' value='{e(q or '')}'><input type='hidden' "
            f"name='id' value='{e(c.id_clover)}'><div class='large'><label>Chercher un article Sage :</label><input "
            f"name='recherche' value='{e(recherche or '')}' size='40'></div><button class='second'>Chercher</button>"
            f"</form><form method='post' class='fiche-bas'>{cache}<div class='factures'>"
            + ("".join(resultats) or "<p class='note'>Aucun article Sage : tapez quelques lettres.</p>")
            + "</div><div class='boutons-colonne'><button name='action' value=\"Confirmer l'article choisi\">✔ Confirmer "
              "l'article choisi</button><button class='second' name='action' value='Accepter la proposition'>Accepter "
              "la proposition</button><button class='danger' name='action' value='Retirer la confirmation'>Retirer la "
              f"confirmation</button>{creer}<button class='accent' name='action' value='Enregistrer les "
              "modifications'>💾 Enregistrer les modifications</button></div></form></div>")


def _decider_correspondance(ctx: Contexte, chemin: Path, ident: str, action: str) -> str:
    """Comme PageCorrespondance.confirmer / accepter / retirer, puis enregistrer (copie de sécurité d'abord)."""
    import shutil
    from datetime import datetime

    from .. import correspondance as co
    from .pages_fournisseurs import _listes

    with ctx.app.ecriture:
        lignes_c = co.lire_correspondances(chemin)
        c = next((x for x in lignes_c if x.id_clover == ident), None)
        if c is None:
            return _message(erreur="Sélectionnez un article dans le tableau, puis un article Sage dans la liste.")
        avertissement = ""
        if action in ("Confirmer l'article choisi", "Confirmer quand même"):
            _noms, articles = _listes(ctx.racine)
            a = next((x for x in articles if x.numero == ctx.req.champ("numero")), None)
            if a is None:
                return _message(erreur="Sélectionnez un article dans le tableau, puis un article Sage dans la liste.")
            if co.conflit_format(c.nom_clover, a.description) and action != "Confirmer quand même":
                return (f"<form method='post' class='erreur'>{csrf(ctx)}"
                        + "".join(f"<input type='hidden' name='{k}' value='{e(ctx.req.champ(k))}'>"
                                  for k in ("pv", "filtre", "q", "id", "numero"))
                        + f"« {e(c.nom_clover)} » et « {e(a.description)} » n'ont pas le même format. Deux formats "
                          "différents sont deux articles différents. <button name='action' value='Confirmer quand "
                          "même'>Confirmer quand même</button></form>")
            if not a.compte_revenus:
                avertissement = (f"L'article Sage {a.numero} n'a pas de compte de produits : l'import sera bloqué tant "
                                 "qu'il n'est pas complété dans Sage.")
            c.statut = co.CONFIRME
            c.numero_sage, c.description_sage, c.compte_revenus = a.numero, a.description, a.compte_revenus
        elif action == "Accepter la proposition":
            if not c.numero_sage:
                return _message(erreur="Aucune proposition pour cet article : choisissez un article Sage dans la liste.")
            c.statut = co.CONFIRME
        else:
            c.statut = co.A_CONFIRMER
        c.methode = "Manuel (application)"
        try:
            if chemin.exists():  # une copie de sécurité par heure (Windows : une par « Enregistrer »)
                copie = chemin.parent / "sauvegardes" / f"{chemin.stem}_{datetime.now():%Y%m%d-%H}.xlsx"
                if not copie.exists():
                    copie.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(chemin, copie)
            co.ecrire_correspondance(lignes_c, chemin)
        except PermissionError:
            return _message(erreur="Le fichier de correspondance est ouvert dans Excel : fermez-le puis réessayez.")
    return _message(f"{c.nom_clover} : {c.statut} (enregistré).", avertissement)


def correspondance_ligne(ctx: Contexte) -> Reponse:
    """Ancienne adresse d'une ligne : la carte « Article sélectionné » est sous la liste."""
    from .. import correspondance as co

    lignes = co.lire_correspondances(_chemin_correspondance(ctx))
    try:
        ident = lignes[int(ctx.req.query.get("i", ""))].id_clover
    except (ValueError, IndexError):
        ident = ""
    return redirection(f"/correspondance?filtre=Tous&id={quote(ident)}")


# --------------------------------------------------------------------------------------------- créer un article
def creer_article(ctx: Contexte) -> Reponse:
    from .. import creation_articles as ca
    from ..points_vente import client
    from . import taches
    from .consultations import sage

    try:
        cle = ("clover_categories",)
        gardee = ctx.app.memoire.get(cle)
        if gardee and time.time() - gardee[0] < 600:
            categories, taux = gardee[1]
        else:
            c = client(ctx.racine)
            categories, taux = c.categories(), c.taux_taxes()
            ctx.app.memoire[cle] = (time.time(), (categories, taux))
    except (Exception, SystemExit):  # noqa: BLE001
        categories, taux = [], []
    try:
        from ..bons_commande import descriptions_sage

        numeros_sage = set(sage(ctx, descriptions_sage, ("descriptions",)))
    except (Exception, SystemExit):  # noqa: BLE001
        numeros_sage = set()
    choix_taxes = ca.choix_taxes(taux) if taux else {ca.TAXES_DEFAUT: None}
    table = ca.TableCategories(ctx.racine)
    v = {k: ctx.req.champ(k).strip() for k in ("nature", "nom", "cout", "prix", "peremption", "categorie", "type_prix",
                                                "unite", "taxes", "code", "stock", "numero", "description",
                                                "charges", "produits", "id_clover", "actif", "cmv", "ecart")}
    cle_saisie = ("creer_article", ctx.session.jeton)
    if ctx.req.methode == "POST" and ctx.req.champ("action") == "Comptes par catégorie":
        # « Comptes par catégorie… » : la table s'ouvre en mode choix ; « Valider la sélection » revient ici
        ctx.app.memoire[cle_saisie] = dict(v)
        from .serveur import redirection

        return redirection(f"/comptes-categories?selection=1&categorie={quote(v['categorie'])}")
    if ctx.req.methode == "GET" and ctx.req.query.get("reprendre"):  # retour de la table des catégories
        v.update(ctx.app.memoire.get(cle_saisie) or {})
        if ctx.req.query.get("categorie"):
            v["categorie"], v["numero"] = ctx.req.query["categorie"], ""
    elif ctx.req.methode == "GET":  # « 🆕 Créer l'article » d'une facture fournisseur ou de la correspondance
        for k in ("nom", "cout", "categorie", "id_clover"):
            v[k] = v[k] or ctx.req.query.get(k, "")
    existant = bool(v["id_clover"])  # article Clover existant : fiche Sage seulement, puis liaison « Confirmé »
    message = ""
    if ctx.req.methode == "POST" and ctx.req.champ("action") == "Créer":
        try:
            service = v["nature"] == "Service"
            cout = Decimal((v["cout"] or "0").replace(",", "."))
            prix = Decimal(v["prix"].replace(",", ".")) if v["prix"] else ca.prix_vente(cout)
            cat = next((x for x in categories if x.get("name") == v["categorie"]), {})
            a = ca.NouvelArticle(v["nom"], cout, prix, ca.lire_date(v["peremption"]) if v["peremption"] else None,
                                 v["categorie"], cat.get("id", ""), v["type_prix"] or "FIXED", v["unite"],
                                 choix_taxes.get(v["taxes"]), v["code"], Decimal((v["stock"] or "0").replace(",", ".")),
                                 v["numero"], v["description"] or v["nom"],
                                 ca.ComptesCategorie(v["categorie"], "", v["actif"], v["produits"], v["cmv"], v["ecart"])
                                 if any(v[k] for k in ("actif", "produits", "cmv")) else table.pour(v["categorie"]),
                                 creer_sage=bool(ctx.req.champ("sage")), creer_clover=bool(ctx.req.champ("clover")) and
                                 not service and not existant, service=service, compte_charges=v["charges"],
                                 compte_produits=v["produits"])
            if existant:
                a.id_clover = v["id_clover"]
            problemes = a.problemes(numeros_sage or None)
            if not (a.creer_sage or a.creer_clover):
                problemes.append("cochez « Créer dans Clover » ou « Créer dans Sage »")
            if problemes:
                raise ValueError("À corriger : " + " ; ".join(problemes))

            def creer(journal):
                etapes = []
                try:
                    if a.creer_sage:
                        journal("Création dans Sage (l'application ouvre Sage elle-même si besoin)…")
                        (r,) = ca.creer_dans_sage(ctx.racine, ctx.config, [a.article_sage()])
                        if not r["cree"]:
                            raise RuntimeError("Sage : article non créé — " + " ; ".join(m for m in r["messages"] if m))
                        etapes.append(f"Sage : article {a.numero_sage} créé")
                    if a.creer_clover:
                        ca.creer_dans_clover(client(ctx.racine), a)
                        etapes.append("Clover : article créé")
                    if a.id_clover and a.numero_sage:
                        ca.relier_correspondance(_chemin_correspondance(ctx), a)
                        etapes.append("Correspondance : reliés (Confirmé)")
                    ca.noter(ctx.racine, a, " ; ".join(etapes))
                except Exception as exc:
                    ca.noter(ctx.racine, a, " ; ".join(etapes + [f"ERREUR : {exc}"]))
                    raise RuntimeError(" ; ".join(etapes + [str(exc)])) from exc
                return etapes

            return taches.lancer(ctx, f"Création de l'article {a.nom}", creer, "/creer-article", sage=a.creer_sage)
        except (ValueError, InvalidOperation) as erreur:
            message = _message(erreur=str(erreur) or "Nombre invalide.")
    # proposition du n° Sage d'après la catégorie (préfixe de la table)
    if v["categorie"] and not v["numero"]:
        comptes = table.pour(v["categorie"])
        v["numero"] = ca.prochain_numero(numeros_sage, "S" if v["nature"] == "Service" else
                                         (comptes.prefixe if comptes else ca.PREFIXE_DEFAUT))
    options_cat = "".join(f"<option{' selected' if x.get('name') == v['categorie'] else ''}>{e(x.get('name', ''))}"
                          "</option>" for x in categories)
    options_taxes = "".join(f"<option{' selected' if k == v['taxes'] else ''}>{e(k)}</option>" for k in choix_taxes)
    options_prix = "".join(f"<option value='{k}'{' selected' if k == v['type_prix'] else ''}>{e(n)}</option>"
                           for k, n in ca.TYPES_PRIX.items())
    nature = "".join(f"<option{' selected' if n == v['nature'] else ''}>{n}</option>" for n in ("Stock", "Service"))

    def champ(nom, libelle, taille=12, type_="text"):
        return (f"<div><label>{libelle}</label><input type='{type_}' name='{nom}' value='{e(v[nom])}' size='{taille}'>"
                "</div>")

    comptes = table.pour(v["categorie"]) if v["categorie"] else None
    service = v["nature"] == "Service"
    if comptes and not service:  # comptes et préfixe de la catégorie choisie (modifiables, comme dans Windows)
        for cle in ("actif", "produits", "cmv", "ecart"):
            v[cle] = v[cle] or getattr(comptes, cle, "") or ""
    v["stock"] = v["stock"] or "0"

    def ligne(libelle, champ_html, obligatoire=False):
        return f"<label>{e(libelle)}{' *' if obligatoire else ''}</label><div>{champ_html}</div>"

    def entree(nom, taille=12, type_="text"):
        return f"<input type='{type_}' name='{nom}' value='{e(v[nom])}' size='{taille}'>"

    natures = "".join(f"<label class='case'><input type='radio' name='nature' value='{n}'"
                      f"{' checked' if (n == 'Service') == service else ''}> {n}</label>" for n in ("Stock", "Service"))
    if service:
        comptes_html = (ligne("Compte de charges", entree("charges", 8), True)
                        + ligne("Compte de produits (facultatif)", entree("produits", 8)))
    else:
        comptes_html = "".join(ligne(lib, entree(cle, 20), oblig) for cle, lib, oblig in (
            ("actif", "Compte d'actif (15xx)", True), ("produits", "Compte de produits (40xx)", True),
            ("cmv", "Compte CMV (50xx)", True), ("ecart", "Compte d'écart", False)))
    existant = bool(v["id_clover"])
    clover_cadre = ("<fieldset class='groupe'><legend>Clover</legend><div class='grille-champs'>"
                    + ligne("Nom", entree("nom", 38), True) + ligne("Prix d'achat (coût)", entree("cout"), True)
                    + ligne("Prix de vente (achat + 40 %)", entree("prix"), True)
                    + ligne("Type de prix", f"<select name='type_prix'>{options_prix}</select> Unité "
                                            + entree("unite", 6), True)
                    + ligne("Taxes et frais", f"<select name='taxes'>{options_taxes}</select>")
                    + ligne("Catégorie", f"<select name='categorie'><option></option>{options_cat}</select>", True)
                    + ligne("Code du produit (facultatif)", entree("code", 20))
                    + ligne("UGS = date de péremption", entree("peremption", 12, "date"), True)
                    + ligne("Stock", entree("stock", 10))
                    + "</div><p class='note'>Couleur : aucune • groupes de modificateurs : aucun</p>"
                    + "<label class='case'><input type='checkbox' name='clover' value='1'"
                    + ("" if existant or service else " checked") + (" disabled" if existant or service else "")
                    + "> Créer dans Clover</label></fieldset>")
    sage_cadre = ("<fieldset class='groupe'><legend>Sage 50</legend><div class='grille-champs'>"
                  + ligne("Type", natures, True) + ligne("N° d'article", entree("numero", 20), True)
                  + ligne("Description", entree("description", 34), True) + comptes_html + "</div>"
                  + ("<p class='note'>Service : n° commençant par S, créé dans Sage seulement.</p>" if service else
                     "<p class='note'>Comptes et préfixe du n° viennent de la catégorie Clover.</p>")
                  + "<p><button class='second' name='action' value='Comptes par catégorie'>Comptes par catégorie…"
                    "</button></p>"
                  "<label class='case'><input type='checkbox' name='sage' value='1' checked> Créer dans Sage</label>"
                  "</fieldset>")
    corps = (message + f"<form method='post'>{csrf(ctx)}"
             + (f"<input type='hidden' name='id_clover' value='{e(v['id_clover'])}'><p class='note'>Article Clover "
                f"existant (ID {e(v['id_clover'])}) : seule sa fiche Sage est créée, puis il est relié (Confirmé).</p>"
                if existant else "")
             + f"<div class='colonnes'>{clover_cadre}{sage_cadre}</div>"
             + "<div class='barre-onglet'><button class='second' name='action' value='Proposer'>Reprendre les comptes "
               "de la catégorie</button><span class='a-droite'><button name='action' value='Créer'>🆕 Créer "
               "l'article</button> <a class='ouvrir' href='/correspondance'>✖ Fermer</a></span></div></form>"
             + "<div class='ligne-etat'>Un service se crée dans Sage seulement (n° commençant par S) ; « Proposer le n° "
               "Sage » prend le préfixe de la catégorie.</div>")
    return Reponse(corps=page(ctx, "Créer un article", corps))


# --------------------------------------------------------------------------------------------- inventaire
def inventaire(ctx: Contexte) -> Reponse:
    from .. import inventaire as inv
    from . import taches

    dossier = ctx.racine / "sortie" / "inventaire"
    if ctx.req.methode == "POST":
        action = ctx.req.champ("action")
        if action == "Préparer":
            def exporter(journal):
                journal("Lecture du stock Clover et Sage…")
                lignes = inv.lire(ctx.racine, ctx.config)
                chemin = inv.ecrire(lignes, dossier / inv.nom_fichier("Inventaire"))
                return [f"{len(lignes)} ligne(s) : fichier {chemin.name} prêt (liste ci-dessous)."]

            return taches.lancer(ctx, "Fichier d'inventaire Clover et Sage", exporter, "/inventaire")
        if action == "Saisir" and "fichier" in ctx.req.fichiers:
            nom, contenu = ctx.req.fichiers["fichier"]
            if not nom.lower().endswith(".xlsx"):
                return Reponse(corps=page(ctx, "Inventaire Clover et Sage", _message(
                    erreur="Envoyez le fichier Excel (.xlsx) rempli.")))
            dossier.mkdir(parents=True, exist_ok=True)
            chemin = dossier / f"Compte_{datetime.now():%Y%m%d_%H%M%S}.xlsx"
            chemin.write_bytes(contenu)

            def saisir(journal):
                saisie, rapport = inv.saisir(ctx.racine, ctx.config, chemin, journal)
                pdf = rapport.with_suffix(".pdf")
                return [f"Saisie faite : rapport {rapport.name}"
                        + (f" et écart d'inventaire {pdf.name}" if pdf.exists() else "") + " (📂 Dossier)."]

            return taches.lancer(ctx, "Saisie de l'inventaire compté", saisir, "/inventaire", sage=True)
    corps = ("<div class='texte-fixe'>1. Exportez l'inventaire : un fichier Excel avec, pour chaque article, code et "
             "description Clover et Sage, quantité Clover, quantité Sage et l'écart.\n2. Comptez, puis inscrivez les "
             "quantités dans la colonne jaune « Quantité comptée » (laissez vide les articles non comptés).\n3. « Saisir "
             "l'inventaire compté » : le stock Clover et le stock Sage deviennent la quantité comptée ; un rapport donne "
             "le coût de l'ajustement.</div>"
             + f"<form method='post' enctype='multipart/form-data' class='barre-onglet'>{csrf(ctx)}<button "
               "name='action' value='Préparer'>⬇ Exporter l'inventaire</button><input type='file' name='fichier' "
               "accept='.xlsx'><button class='accent' name='action' value='Saisir'>📦 Saisir l'inventaire compté…"
               "</button><a class='ouvrir' href='/dossier-inventaire'>📂 Dossier</a></form>")
    return Reponse(corps=page(ctx, "Inventaire Clover et Sage", corps))


def inventaire_fichier(ctx: Contexte) -> Reponse:
    chemin = ctx.racine / "sortie" / "inventaire" / Path(ctx.req.query.get("f", "")).name
    if not chemin.exists() or chemin.suffix.lower() not in (".xlsx", ".pdf"):
        return Reponse(404, page(ctx, "Inventaire", "<p>Fichier introuvable.</p>"))
    return _telecharger(chemin)


def inventaire_tournant(ctx: Contexte) -> Reponse:
    from .. import paquet3 as p3
    from . import taches

    if ctx.req.methode == "POST":
        def feuille(journal):
            chemin, categories, n = p3.feuille_tournante(ctx.racine, ctx.config, date.today())
            cible = ctx.racine / "sortie" / "inventaire" / chemin.name
            if chemin.resolve() != cible.resolve():
                cible.parent.mkdir(parents=True, exist_ok=True)
                cible.write_bytes(chemin.read_bytes())
            return [f"{n} ligne(s), catégories de la semaine : {', '.join(categories)}.",
                    f"Fichier {cible.name} : Stock > Inventaire Clover et Sage."]

        return taches.lancer(ctx, "Feuille de l'inventaire tournant", feuille, "/inventaire")
    semaines = int(ctx.config.get("inventaire", {}).get("semaines_cycle", 8))
    from ..cache_lectures import inventaire_clover

    try:
        articles = inventaire_clover(ctx.racine)
    except (Exception, SystemExit) as erreur:  # noqa: BLE001 — tableau vide avec ses colonnes
        ctx.app.noter(f"Inventaire tournant : {erreur!r}")
        ctx.absents.add("Clover")
        articles = []
    categories = [((a.get("categories") or {}).get("elements") or [{}])[0].get("name", "") for a in articles]
    plan = p3.plan_tournant(categories, semaines) if articles else [[] for _ in range(semaines)]
    actuelle = p3.semaine_du_cycle(date.today(), semaines)
    lignes = [[("▶ " if i_ == actuelle else "") + str(i_ + 1), ", ".join(c)] for i_, c in enumerate(plan)]
    corps = (f"<form method='post' class='barre-onglet'>{csrf(ctx)}<button>📋 Feuille de comptage de la semaine"
             "</button></form><p class='note'>Chaque semaine, on compte quelques catégories ; toutes le sont une fois "
             f"par cycle ([inventaire] semaines_cycle, {semaines}). La feuille remplie se saisit dans Stock > Inventaire "
             "Clover et Sage (« Saisir »).</p>"
             + tableau_section(Section("Plan du cycle", ["Semaine du cycle", "Catégories à compter"], lignes,
                                       classes=["etat-applique" if i_ == actuelle else "" for i_ in range(len(plan))])))
    return Reponse(corps=page(ctx, "Inventaire tournant", corps))


# --------------------------------------------------------------------------------------------- transferts
def transferts(ctx: Contexte) -> Reponse:
    """Comme fenetre_transferts.FenetreTransferts : explication, « ➕ Nouveau transfert », « 🗑 Supprimer », liste des
    transferts (gris : terminé, rose : à compléter) ; cadre « Transfert » : n°, date, de, vers, note ; article Sage +
    quantité, « ➕ Ajouter la ligne », « 🗑 Retirer la ligne » ; lignes avec le stock Sage au départ et à l'arrivée
    (jaune : stock insuffisant) ; « 💾 Enregistrer », « ▶ Transférer (Sage puis Clover) »."""
    from .. import transferts as tr
    from ..points_vente import points_de_vente
    from .consultations import lire_ou_vide
    from .pages_fournisseurs import _listes
    from . import taches

    points = {str(x.code): x for x in points_de_vente(ctx.config, actifs=True)}
    registre = tr.Registre(ctx.racine)
    _noms, articles = _listes(ctx.racine)
    par_cle = {f"{a.numero} — {a.description}": a for a in articles}
    numero = ctx.req.champ("numero") or ctx.req.query.get("numero", "")
    courant = registre.trouver(numero) if numero else None
    message, etat = "", ""
    # lignes du formulaire : reprises du formulaire envoyé, sinon du transfert choisi
    if ctx.req.methode == "POST":
        lignes = []
        for n, d, q in zip(ctx.req.champs("lid"), ctx.req.champs("ldesc"), ctx.req.champs("lq")):
            try:
                lignes.append(tr.LigneTransfert(n, d, Decimal(q)))
            except InvalidOperation:
                pass
        v = {k: ctx.req.champ(k) for k in ("jour", "de", "vers", "note")}
    else:
        lignes = list(courant.lignes) if courant else []
        codes = list(points)
        v = {"jour": courant.jour if courant else date.today().isoformat(),
             "de": courant.de if courant else (codes[0] if codes else ""),
             "vers": courant.vers if courant else (codes[1] if len(codes) > 1 else ""),
             "note": courant.note if courant else ""}
    if not numero:
        numero = registre.nouveau_numero()
    if ctx.req.methode == "POST":
        action = ctx.req.champ("action")
        try:
            if action == "Ajouter la ligne":
                a = par_cle.get(ctx.req.champ("article").strip())
                q = Decimal(ctx.req.champ("quantite").replace(",", ".").strip() or "0")
                if a is None:
                    raise ValueError("Choisissez l'article Sage dans la liste.")
                if q <= 0:
                    raise ValueError("Quantité invalide.")
                lignes.append(tr.LigneTransfert(a.numero, a.description, q))
            elif action == "Retirer la ligne":
                rang = ctx.req.champ("rang")
                if rang.isdigit() and int(rang) < len(lignes):
                    del lignes[int(rang)]
            elif action in ("Enregistrer", "Transférer"):
                with ctx.app.ecriture:
                    reg = tr.Registre(ctx.racine)
                    t_ = reg.trouver(numero) or tr.Transfert(numero, v["jour"], v["de"], v["vers"])
                    if t_.etat != tr.BROUILLON and action == "Enregistrer":
                        raise ValueError(f"{t_.numero} est déjà passé ({t_.etat}) : il ne se modifie plus.")
                    if t_.etat == tr.BROUILLON:
                        t_.jour, t_.de, t_.vers, t_.note, t_.lignes = v["jour"], v["de"], v["vers"], v["note"], lignes
                        problemes = t_.problemes(points)
                        if problemes:
                            raise ValueError("À corriger : " + " ; ".join(problemes))
                        reg.garder(t_)
                if action == "Transférer":
                    def transferer(journal):
                        fait = tr.transferer(ctx.racine, ctx.config, numero, journal)
                        return [f"{fait.numero} : {fait.etat}"] + fait.messages

                    return taches.lancer(ctx, f"Transfert {numero}", transferer, f"/transferts?numero={numero}",
                                         sage=True)
                message = _message(f"✔ {numero} enregistré.")
            elif action == "Bon de transfert":  # modèle des documents de stock (2026-11-05)
                t_ = registre.trouver(ctx.req.champ("choisi") or numero)
                if t_ is None:
                    raise ValueError("Choisissez d'abord un transfert enregistré dans la liste.")
                chemin = tr.ecrire_pdf(ctx.racine, ctx.config, t_)
                return Reponse(corps=chemin.read_bytes(), type="application/pdf",
                               entetes={"Content-Disposition": f"inline; filename=\"{chemin.name}\""})
            elif action == "Supprimer":
                if not action_permise(ctx, "Supprimer"):
                    raise ValueError("Votre profil n'a pas le droit « Supprimer ».")
                with ctx.app.ecriture:
                    tr.Registre(ctx.racine).supprimer(ctx.req.champ("choisi") or numero)
                message = _message("Transfert supprimé.")
                numero, lignes = tr.Registre(ctx.racine).nouveau_numero(), []
        except (ValueError, InvalidOperation) as erreur:
            message = _message(erreur=str(erreur) or "Quantité invalide.")
        registre = tr.Registre(ctx.racine)
    # stocks Sage de chaque ligne, au départ et à l'arrivée
    stocks = {}
    if lignes:
        stocks = lire_ou_vide(ctx, lambda b: tr.stocks_par_depot(b, [l.numero for l in lignes]))
    depot_de = points[v["de"]].depot_sage if v["de"] in points else ""
    depot_vers = points[v["vers"]].depot_sage if v["vers"] in points else ""

    def stock(n, depot):
        q = (stocks.get(n) or {}).get(depot or "Primary location for all")
        return q

    rangees, classes = [], []
    for k, l in enumerate(lignes):
        q_de, q_vers = stock(l.numero, depot_de), stock(l.numero, depot_vers)
        rangees.append([f"<input type='radio' name='rang' value='{k}'>", e(l.numero), e(l.description),
                        f"{l.quantite.normalize():f}".replace(".", ","),
                        "" if q_de is None else f"{q_de.normalize():f}".replace(".", ","),
                        "" if q_vers is None else f"{q_vers.normalize():f}".replace(".", ",")])
        classes.append("etat-a-saisir" if q_de is not None and q_de < l.quantite else "")
    liste, couleurs = [], []
    for t_ in sorted(registre.transferts, key=lambda x: (x.jour, x.numero), reverse=True):
        nom = {c: x.nom for c, x in points.items()}
        liste.append([f"<input type='radio' name='choisi' value='{e(t_.numero)}'{' checked' if t_.numero == numero else ''}>",
                      f"<a href='/transferts?numero={e(t_.numero)}'>{e(t_.numero)}</a>", e(t_.jour),
                      e(f"{t_.de} — {nom.get(t_.de, '?')}"), e(f"{t_.vers} — {nom.get(t_.vers, '?')}"),
                      str(len(t_.lignes)), f"{t_.total_quantite.normalize():f}".replace(".", ","), e(t_.etat),
                      e(" ; ".join(t_.messages))])
        couleurs.append("termine" if t_.etat == tr.TERMINE else ("etat-ecart" if t_.etat == tr.A_COMPLETER else ""))
    options = {k: "".join(f"<option value='{e(c)}'{' selected' if c == v[k] else ''}>{e(x.libelle)}</option>"
                          for c, x in points.items()) for k in ("de", "vers")}
    caches = "".join(f"<input type='hidden' name='lid' value='{e(l.numero)}'><input type='hidden' name='ldesc' "
                     f"value='{e(l.description)}'><input type='hidden' name='lq' value='{l.quantite}'>" for l in lignes)
    liste_a = "<datalist id='articles-sage'>" + "".join(f"<option value='{e(k)}'>" for k in par_cle) + "</datalist>"
    if len(points) < 2:
        etat = ("Il faut au moins deux points de vente actifs (« Administration > Clover », carte « Points de vente »), "
                "chacun avec son dépôt Sage.")
    corps = (message + "<p class='note'>Des articles passent d'un point de vente à l'autre : dans Sage, transfert entre "
             "les deux dépôts (même valeur, sans vente) ; dans Clover, stock diminué au départ et augmenté à l'arrivée. "
             "Sage d'abord (vérifié), Clover ensuite ; un transfert n'est jamais fait deux fois.</p>"
             + f"<form method='post'>{csrf(ctx)}<div class='barre-onglet'><a class='ouvrir' href='/transferts'>➕ "
               "Nouveau transfert</a><button class='second' name='action' value='Supprimer'>🗑 Supprimer</button>"
               "<button class='second' name='action' value='Bon de transfert' formtarget='_blank'>🖨 Bon de transfert"
               "</button></div>"
             + tableau_section(Section("Transferts", ["", "N°", "Date", "De", "Vers", "Articles", "Quantité", "État",
                                                     "Remarques"], liste, classes=couleurs, html=set(range(9))))
             + "</form>"
             + f"<form method='post'>{csrf(ctx)}<input type='hidden' name='numero' value='{e(numero)}'>{caches}"
               f"<fieldset class='groupe'><legend>Transfert</legend><div class='barre-onglet'><strong class='periode'>"
               f"{e(numero)}</strong><div><label>Date</label><input type='date' name='jour' value='{e(v['jour'])}'>"
               f"</div><div><label>De</label><select name='de'>{options['de']}</select></div><div><label>Vers</label>"
               f"<select name='vers'>{options['vers']}</select></div><div><label>Note</label><input name='note' "
               f"value='{e(v['note'])}' size='30'></div></div><div class='barre-onglet'><div class='large'><label>"
               f"Article Sage</label><input name='article' list='articles-sage' size='44'>{liste_a}</div><div><label>"
               "Quantité</label><input name='quantite' size='9'></div><button class='second' name='action' "
               "value='Ajouter la ligne'>➕ Ajouter la ligne</button><button class='second' name='action' "
               "value='Retirer la ligne'>🗑 Retirer la ligne</button></div>"
             + tableau_section(Section("Lignes du transfert", ["", "N° Sage", "Description", "Quantité",
                                                              "Stock Sage au départ", "Stock Sage à l'arrivée"],
                                       rangees, classes=classes, html=set(range(6))))
             + "<div class='barre-onglet'><button class='second' name='action' value='Enregistrer'>💾 Enregistrer"
               "</button><button name='action' value='Transférer'>▶ Transférer (Sage puis Clover)</button></div>"
               "</fieldset></form>"
             + (f"<div class='ligne-etat erreur-texte'>{e(etat)}</div>" if etat else ""))
    return Reponse(corps=page(ctx, "Transferts entre magasins", corps))


FONCTIONS = [
    Fonction("/articles-clover", "Articles Clover", "correspondance", articles_clover, "📄", "Articles", menu=False),
    Fonction("/correspondance", "correspondance", "correspondance", correspondance, "🔗", "Articles", menu=False,
             page_entiere=True),
    Fonction("/correspondance-ligne", "correspondance", "correspondance", correspondance_ligne, "🔗", "Articles",
             menu=False, page_entiere=True),
    Fonction("/creer-article", "Créer un article", "correspondance", creer_article, "🆕", "Articles", menu=False),
    Fonction("/inventaire", "Inventaire Clover et Sage", "correspondance", inventaire, "📋", "Stock", menu=False),
    Fonction("/inventaire-fichier", "Inventaire Clover et Sage", "correspondance", inventaire_fichier, "📋", "Stock",
             menu=False),
    Fonction("/inventaire-tournant", "Inventaire tournant", "correspondance", inventaire_tournant, "🔄", "Stock",
             menu=False),
    Fonction("/transferts", "Transferts entre magasins", "correspondance", transferts, "🔁", "Stock", menu=False),
]
WEB = {"Articles Clover": "/articles-clover", "Correspondance": "/correspondance", "Créer un article": "/creer-article",
       "Inventaire Clover et Sage": "/inventaire", "Inventaire tournant": "/inventaire-tournant",
       "Transferts entre magasins": "/transferts"}
