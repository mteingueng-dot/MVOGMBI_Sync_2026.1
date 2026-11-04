"""7e vague de l'application web : rubriques Articles et Stock, fonctions qui travaillent sur le catalogue Clover :
pertes et démarque (comme fenetre_pertes), promotions (paquet3), étiquettes de prix (etiquettes), prix et marges
(prix_marges), coûts Clover depuis Sage (couts_clover). Recherche d'articles commune ; écritures dans Clover
seulement après confirmation, mêmes règles et mêmes droits par action.
"""

from __future__ import annotations

import time
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from .pages import Contexte, Fonction, argent, csrf, page, tableau
from .pages_compta import _message, _point_vente, action_permise
from .serveur import Reponse, echapper as e

LIMITE = 60  # articles affichés par recherche


def _catalogue(ctx: Contexte, pv=None) -> list[dict]:
    from ..cache_lectures import inventaire_clover

    return [a for a in inventaire_clover(ctx.racine, pv) if a.get("name")]


def _chercher(articles: list[dict], texte: str) -> list[dict]:
    from ..correspondance import normaliser

    mots = normaliser(texte).split()
    if not mots:
        return []
    trouves = [a for a in articles if all(m in normaliser(f"{a.get('name', '')} {a.get('code') or ''} "
                                                          f"{a.get('sku') or ''}") for m in mots)]
    return sorted(trouves, key=lambda a: a.get("name", "").casefold())[:LIMITE]


def _prix(a: dict) -> Decimal:
    return Decimal(int(a.get("price") or 0)) / 100


def _recherche(ctx: Contexte, choix_pv: str = "") -> str:
    return (f"<form class='ligne' method='get'>{choix_pv}<div><label>Chercher un article Clover</label><input name='q' "
            f"value='{e(ctx.req.query.get('q', ''))}' size='30' autofocus></div><button class='second'>Chercher</button>"
            "</form>")


def _client(ctx: Contexte, pv=None):
    from ..points_vente import client

    return client(ctx.racine, pv)


# --------------------------------------------------------------------------------------------- pertes
def pertes(ctx: Contexte) -> Reponse:
    from .. import pertes as pe
    from . import taches

    pv, choix_pv, code = _point_vente(ctx)
    message = ""
    try:
        articles = _catalogue(ctx, pv)
    except (Exception, SystemExit) as erreur:  # noqa: BLE001
        ctx.app.noter(f"Pertes : {erreur!r}")
        return Reponse(corps=page(ctx, "Pertes et démarque", _message(erreur="Clover ne répond pas pour l'instant.")))
    if ctx.req.methode == "POST":
        action_nom = "Sortir des pertes du stock"
        if not action_permise(ctx, action_nom):
            message = _message(erreur=f"Votre profil n'a pas le droit « {action_nom} ».")
        else:
            try:
                from ..couts_sage import charger, correspondance

                par_id = {a["id"]: a for a in articles}
                liens = correspondance(ctx.racine, pv)
                try:
                    couts = charger(ctx.racine, ctx.config)
                except (Exception, SystemExit):  # noqa: BLE001 — Sage illisible : coût Clover
                    couts = {}
                lignes = []
                for ident, quantite in zip(ctx.req.champs("id"), ctx.req.champs("quantite")):
                    if quantite.strip() and ident in par_id:
                        q = Decimal(quantite.replace(",", "."))
                        if q > 0:
                            lignes.append(pe.ligne(par_id[ident], q, liens, couts))
                from ..points_vente import permis as pv_permis

                choisi = next((p for p in pv_permis(ctx.config, None) if str(p.code) == str(code)), None)
                with ctx.app.ecriture:
                    p = pe.nouvelle(pe.Registre(ctx.racine), ctx.req.champ("jour"), ctx.req.champ("motif"), lignes,
                                    choisi.depot_sage if choisi and pv else "", ctx.u.nom, ctx.req.champ("remarque"),
                                    str(code) if pv else "")

                def sortir(journal):
                    fait = pe.appliquer(ctx.racine, ctx.config, p.numero)
                    return [f"{fait.numero} : {len(fait.lignes)} ligne(s), valeur au coût {argent(fait.valeur)}."] + \
                        fait.messages

                return taches.lancer(ctx, f"Perte {p.numero} sortie du stock", sortir, "/pertes")
            except (ValueError, InvalidOperation) as erreur:
                message = _message(erreur=str(erreur) or "Quantité invalide.")
    trouves = _chercher(articles, ctx.req.query.get("q", ""))
    lignes = [[e(a.get("name", "")), e(a.get("code") or a.get("sku") or ""), argent(_prix(a)),
               e(str((a.get("itemStock") or {}).get("quantity", ""))),
               f"<input type='hidden' name='id' value='{e(a['id'])}'><input name='quantite' size='5' "
               "inputmode='decimal'>"] for a in trouves]
    motifs = "".join(f"<option>{e(m)}</option>" for m in pe.MOTIFS)
    registre = pe.Registre(ctx.racine)
    faites = [[e(p.numero), e(p.jour), e(p.motif), len(p.lignes), argent(p.valeur), e(p.document), e(p.auteur)]
              for p in sorted(registre.pertes, key=lambda p: p.jour, reverse=True)[:50]]
    corps = (message + _recherche(ctx, choix_pv)
             + (f"<form method='post' class='carte'>{csrf(ctx)}<input type='hidden' name='pv' value='{e(code)}'>"
                + tableau(["Article", "Code", "Prix", "Stock", "Quantité perdue"], lignes, {2, 3})
                + f"<div class='ligne'><div><label>Date</label><input type='date' name='jour' value='{date.today()}'>"
                  f"</div><div><label>Motif</label><select name='motif'>{motifs}</select></div><div><label>Remarque"
                  "</label><input name='remarque' size='30'></div></div><div class='boutons'><button>Déclarer la perte"
                  "</button></div><p class='note'>Le stock Clover diminue tout de suite ; un document de stock « Sortie »"
                  " est préparé pour Sage (Stock > Liste des documents de stock).</p></form>" if trouves else
                "<p class='note'>Cherchez les articles perdus, indiquez les quantités, puis « Déclarer la perte ».</p>")
             + "<h2>Pertes déclarées</h2>"
             + tableau(["N°", "Date", "Motif", "Lignes", "Valeur au coût", "Document Sage", "Par"],
                       [[l[0], l[1], l[2], str(l[3]), l[4], l[5], l[6]] for l in faites], {3, 4}))
    return Reponse(corps=page(ctx, "Pertes et démarque", corps))


# --------------------------------------------------------------------------------------------- promotions
def promotions(ctx: Contexte) -> Reponse:
    from .. import paquet3 as p3
    from . import taches

    pv, choix_pv, code = _point_vente(ctx)
    message = ""
    if ctx.req.methode == "POST":
        action = ctx.req.champ("action")
        action_nom = "Changer les prix Clover (promotions)"
        try:
            if action != "Ajouter" and not action_permise(ctx, action_nom):
                raise ValueError(f"Votre profil n'a pas le droit « {action_nom} ».")
            if action == "Ajouter":
                articles = {a["id"]: a for a in _catalogue(ctx, pv)}
                a = articles.get(ctx.req.champ("id"))
                if a is None:
                    raise ValueError("Choisissez l'article.")
                prix = Decimal(ctx.req.champ("prix").replace(",", ".").replace("$", "").strip())
                with ctx.app.ecriture:
                    p = p3.Promotions(ctx.racine).ajouter(a["id"], a.get("name", ""), prix,
                                                          date.fromisoformat(ctx.req.champ("du")),
                                                          date.fromisoformat(ctx.req.champ("au")), ctx.u.nom,
                                                          str(code) if pv else "")
                message = _message(f"Promotion {p.numero} prévue.")
            elif action == "Appliquer maintenant":
                def appliquer(journal):
                    return p3.appliquer_promotions(ctx.racine, _client(ctx, pv), code=str(code) if pv else None) or \
                        ["Rien à changer aujourd'hui."]

                return taches.lancer(ctx, "Application des promotions", appliquer, "/promotions")
            elif action == "Annuler":
                numero = ctx.req.champ("numero")

                def annuler(journal):
                    return p3.annuler_promotion(ctx.racine, numero, _client(ctx, pv))

                return taches.lancer(ctx, f"Annulation de la promotion {numero}", annuler, "/promotions")
        except (ValueError, InvalidOperation) as erreur:
            message = _message(erreur=str(erreur) or "Prix ou date invalide.")
        except (Exception, SystemExit) as erreur:  # noqa: BLE001 — Clover injoignable
            message = _message(erreur=f"Clover : {erreur}")
    liste = p3.Promotions(ctx.racine).liste
    lignes = []
    for p in sorted(liste, key=lambda p: p.du, reverse=True):
        bouton = (f"<form method='post'>{csrf(ctx)}<input type='hidden' name='numero' value='{e(p.numero)}'>"
                  "<button class='second' name='action' value='Annuler'>Annuler</button></form>"
                  if p.etat in (p3.PREVUE, p3.EN_COURS) else "")
        lignes.append([e(p.numero), e(p.nom), argent(Decimal(p.prix_promo)),
                       argent(Decimal(p.prix_normal)) if p.prix_normal else "", e(p.du), e(p.au), e(p.etat), bouton])
    choix = ""
    try:
        trouves = _chercher(_catalogue(ctx, pv), ctx.req.query.get("q", ""))
    except (Exception, SystemExit):  # noqa: BLE001
        trouves = []
    if trouves:
        options = "".join(f"<option value='{e(a['id'])}'>{e(a.get('name', ''))} — {argent(_prix(a))}</option>"
                          for a in trouves)
        choix = (f"<form method='post' class='carte'>{csrf(ctx)}<input type='hidden' name='pv' value='{e(code)}'>"
                 f"<div class='ligne'><div><label>Article</label><select name='id'>{options}</select></div><div><label>"
                 "Prix promotionnel</label><input name='prix' size='8' required></div><div><label>Du</label><input "
                 f"type='date' name='du' value='{date.today()}' required></div><div><label>Au</label><input type='date' "
                 f"name='au' value='{date.today() + timedelta(days=6)}' required></div></div><div class='boutons'>"
                 "<button name='action' value='Ajouter'>Prévoir la promotion</button></div></form>")
    corps = (message + _recherche(ctx, choix_pv) + choix
             + tableau(["N°", "Article", "Prix promo", "Prix normal", "Du", "Au", "État", ""], lignes, {2, 3})
             + f"<form method='post' class='boutons'>{csrf(ctx)}<input type='hidden' name='pv' value='{e(code)}'>"
               "<button class='second' name='action' value='Appliquer maintenant'>Appliquer maintenant</button></form>"
               "<p class='note'>Chaque nuit : le 1er jour, le prix normal est lu puis le prix promo posé dans Clover ; "
               "après le dernier jour, le prix normal revient (seulement si le prix est encore le prix promo).</p>")
    return Reponse(corps=page(ctx, "Promotions", corps))


# --------------------------------------------------------------------------------------------- étiquettes
def etiquettes(ctx: Contexte) -> Reponse:
    from .. import etiquettes as et

    pv, choix_pv, code = _point_vente(ctx)
    try:
        articles = _catalogue(ctx, pv)
    except (Exception, SystemExit):  # noqa: BLE001
        return Reponse(corps=page(ctx, "Étiquettes de prix", _message(erreur="Clover ne répond pas pour l'instant.")))
    if ctx.req.methode == "POST":
        if not action_permise(ctx, "Imprimer des étiquettes"):
            return Reponse(corps=page(ctx, "Étiquettes de prix", _message(
                erreur="Votre profil n'a pas le droit « Imprimer des étiquettes ».")))
        par_id = {a["id"]: a for a in articles}
        choisis = [et.depuis_article(par_id[i]) for i in ctx.req.champs("id") if i in par_id]
        if choisis:
            return Reponse(corps=et.page(choisis, imprimer=False), style_en_ligne=True)
    depuis = ctx.req.query.get("depuis", "")
    if depuis:
        changes = et.prix_changes(ctx.racine, depuis)
        trouves = [a for a in articles if a["id"] in changes]
    else:
        trouves = _chercher(articles, ctx.req.query.get("q", ""))
    lignes = [[f"<input type='checkbox' name='id' value='{e(a['id'])}' checked>", e(a.get("name", "")),
               e(a.get("code") or a.get("sku") or ""), argent(_prix(a))] for a in trouves]
    corps = (_recherche(ctx, choix_pv)
             + f"<form class='ligne' method='get'><div><label>Ou : prix changés depuis</label><input type='date' "
               f"name='depuis' value='{e(depuis)}'></div><button class='second'>Afficher</button></form>"
             + (f"<form method='post'>{csrf(ctx)}" + tableau(["", "Article", "Code", "Prix"], lignes, {3})
                + "<div class='boutons'><button>Préparer les étiquettes</button></div></form>" if lignes else "")
             + "<p class='note'>Feuille Avery 5160 / 8160 (3 × 10) ; impression par le navigateur (Ctrl+P).</p>")
    return Reponse(corps=page(ctx, "Étiquettes de prix", corps))


# --------------------------------------------------------------------------------------------- prix et marges
def prix_marges(ctx: Contexte) -> Reponse:
    from .. import prix_marges as pm
    from . import taches

    try:
        marge = int(ctx.req.query.get("marge") or ctx.req.champ("marge") or 25)
    except ValueError:
        marge = 25
    mode = ctx.req.query.get("arrondi") or ctx.req.champ("arrondi") or pm.ARRONDIS[0]
    cle = "prix_marges"
    gardee = ctx.app.memoire.get(cle)
    try:
        donnees = gardee[1] if gardee and time.time() - gardee[0] < 600 and not ctx.req.query.get("relire") else None
        if donnees is None:
            donnees = pm.lire_donnees(ctx.racine, ctx.config)
            ctx.app.memoire[cle] = (time.time(), donnees)
    except (Exception, SystemExit) as erreur:  # noqa: BLE001
        ctx.app.noter(f"Prix et marges : {erreur!r}")
        return Reponse(corps=page(ctx, "Prix et marges", _message(erreur="Clover ou Sage ne répond pas pour "
                                                                         "l'instant.")))
    lignes, bonnes = pm.analyser(donnees["articles"], donnees["liens"], donnees["couts"], donnees["ventes"], marge, mode)
    message = ""
    if ctx.req.methode == "POST":
        action_nom = "Changer les prix Clover (promotions)"
        choisis = [lignes[int(k)] for k in ctx.req.champs("choix") if k.isdigit() and int(k) < len(lignes)
                   and lignes[int(k)].permis]
        if not action_permise(ctx, action_nom):
            message = _message(erreur=f"Votre profil n'a pas le droit « {action_nom} ».")
        elif not choisis:
            message = _message(erreur="Cochez au moins un article.")
        else:
            def appliquer(journal):
                resultats = pm.appliquer(ctx.racine, choisis)
                ctx.app.memoire.pop(cle, None)
                return [f"{l.nom} : {argent(l.prix)} → {argent(l.nouveau)}" + (f" ✘ {err}" if err else "")
                        for l, err in resultats]

            return taches.lancer(ctx, f"Nouveaux prix dans Clover ({len(choisis)})", appliquer, "/prix-marges")
    rangees = [[f"<input type='checkbox' name='choix' value='{k}'{' checked' if l.cochee_par_defaut else ''}>"
                if l.permis else "", e(l.nom), e(l.categorie), e(l.numero_sage),
                argent(l.cout) if l.cout is not None else "", e(l.source_cout), argent(l.prix) if l.prix else "",
                f"{l.marge} %".replace(".", ",") if l.marge is not None else "",
                argent(l.nouveau) if l.nouveau else "", f"{l.marge_apres} %".replace(".", ",") if l.marge_apres
                is not None else "", argent(l.effet) if l.effet is not None else "", e(l.etat), e(l.note)]
               for k, l in enumerate(lignes)]
    marges = "".join(f"<option{' selected' if m == marge else ''}>{m}</option>" for m in pm.MARGES)
    arrondis = "".join(f"<option{' selected' if a == mode else ''}>{e(a)}</option>" for a in pm.ARRONDIS)
    corps = (message + f"<form class='ligne' method='get'><div><label>Marge minimale (%)</label><select name='marge'>"
             f"{marges}</select></div><div><label>Arrondi</label><select name='arrondi'>{arrondis}</select></div>"
             "<button class='second'>Recalculer</button><a class='ouvrir' href='?relire=1'>Relire Clover et Sage</a>"
             f"</form><p class='note'>{bonnes} article(s) déjà à la bonne marge. Coût = CUMP de Sage, sinon coût Clover ;"
             " effet = (nouveau − prix) × quantité vendue en 90 jours.</p>"
             + f"<form method='post'>{csrf(ctx)}<input type='hidden' name='marge' value='{marge}'><input type='hidden' "
               f"name='arrondi' value='{e(mode)}'>"
             + tableau(["", "Article", "Catégorie", "N° Sage", "Coût", "Source", "Prix", "Marge", "Nouveau prix",
                        "Marge après", "Effet 90 j", "État", "Note"], rangees, {4, 6, 7, 8, 9, 10})
             + "<div class='boutons'><button>Écrire les nouveaux prix dans Clover</button></div></form>")
    return Reponse(corps=page(ctx, "Prix et marges", corps))


# --------------------------------------------------------------------------------------------- coûts Clover
def couts_clover(ctx: Contexte) -> Reponse:
    from .. import couts_clover as cc
    from . import taches

    cle = "couts_clover"
    gardee = ctx.app.memoire.get(cle)
    try:
        if gardee and time.time() - gardee[0] < 600 and not ctx.req.query.get("relire"):
            propositions, bons = gardee[1]
        else:
            propositions, bons = cc.lire(ctx.racine, ctx.config)
            ctx.app.memoire[cle] = (time.time(), (propositions, bons))
    except (Exception, SystemExit) as erreur:  # noqa: BLE001
        ctx.app.noter(f"Coûts Clover : {erreur!r}")
        return Reponse(corps=page(ctx, "Coûts Clover depuis Sage", _message(erreur="Clover ou Sage ne répond pas.")))
    message = ""
    if ctx.req.methode == "POST":
        choisis = [propositions[int(k)] for k in ctx.req.champs("choix") if k.isdigit() and int(k) < len(propositions)
                   and propositions[int(k)].permis]
        if not choisis:
            message = _message(erreur="Cochez au moins un article.")
        else:
            def appliquer(journal):
                resultats = cc.appliquer(ctx.racine, choisis)
                ctx.app.memoire.pop(cle, None)
                return [f"{p.nom} : coût {argent(p.cump)}" + (f" ✘ {err}" if err else "") for p, err in resultats]

            return taches.lancer(ctx, f"Coûts Clover mis à jour ({len(choisis)})", appliquer, "/couts-clover")
    rangees = [[f"<input type='checkbox' name='choix' value='{k}'{' checked' if p.cochee_par_defaut else ''}>"
                if p.permis else "", e(p.nom), e(p.numero_sage), argent(p.prix) if p.prix is not None else "",
                argent(p.cout_clover) if p.cout_clover is not None else "", argent(p.cump) if p.cump is not None else "",
                e(p.etat), e(p.note)] for k, p in enumerate(propositions)]
    corps = (message + f"<p class='note'>{bons} article(s) ont déjà le bon coût. <a href='?relire=1'>Relire</a></p>"
             + f"<form method='post'>{csrf(ctx)}"
             + tableau(["", "Article Clover", "N° Sage", "Prix", "Coût Clover", "CUMP Sage", "État", "Note"], rangees,
                       {3, 4, 5})
             + "<div class='boutons'><button>Mettre le CUMP de Sage comme coût Clover</button></div></form>"
               "<p class='note'>Jamais de valeur aberrante (CUMP absent, plus de 5 × le prix, moins de 5 % du prix).</p>")
    return Reponse(corps=page(ctx, "Coûts Clover depuis Sage", corps))


FONCTIONS = [
    Fonction("/pertes", "Pertes et démarque", "correspondance", pertes, "🗑", "Stock", menu=False),
    Fonction("/promotions", "Promotions", "correspondance", promotions, "🏷", "Articles", menu=False),
    Fonction("/etiquettes", "Étiquettes de prix", "correspondance", etiquettes, "🏷", "Articles", menu=False),
    Fonction("/prix-marges", "Prix et marges", "correspondance", prix_marges, "💹", "Articles", menu=False),
    Fonction("/couts-clover", "Coûts Clover depuis Sage", "correspondance", couts_clover, "💲", "Articles", menu=False),
]
WEB = {"Pertes et démarque": "/pertes", "Promotions": "/promotions", "Étiquettes de prix": "/etiquettes",
       "Prix et marges": "/prix-marges", "Coûts Clover depuis Sage": "/couts-clover"}
