"""7e vague de l'application web : rubriques Articles et Stock, fonctions qui travaillent sur le catalogue Clover :
pertes et démarque (comme fenetre_pertes), promotions (paquet3), étiquettes de prix (etiquettes), prix et marges
(prix_marges), coûts Clover depuis Sage (couts_clover). Recherche d'articles commune ; écritures dans Clover
seulement après confirmation, mêmes règles et mêmes droits par action.
"""

from __future__ import annotations

import time
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from .consultations import Section, tableau_section
from .pages import Contexte, Fonction, argent, csrf, page, tableau
from .pages_compta import _message, _point_vente, action_permise
from .serveur import Reponse, echapper as e

LIMITE = 60  # articles affichés par recherche


def _catalogue(ctx: Contexte, pv=None) -> list[dict]:
    """Catalogue Clover ; Clover injoignable : vide (les tableaux restent affichés) et la page le signale."""
    from ..cache_lectures import inventaire_clover

    try:
        return [a for a in inventaire_clover(ctx.racine, pv) if a.get("name")]
    except (Exception, SystemExit) as erreur:  # noqa: BLE001
        ctx.app.noter(f"Clover injoignable : {erreur!r}")
        ctx.absents.add("Clover")
        return []


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
    """Comme fenetre_pertes.FenetrePertes, 3 onglets : « Déclarer une perte » (date, motif *, point de vente, remarque ;
    article + quantité, « ➕ Ajouter la ligne » / « ✔ Mettre à jour la ligne », « ✖ Retirer la ligne », « ⏰ Ajouter les
    produits périmés en stock », total, « ✔ Enregistrer et sortir du stock »), « Pertes déclarées » (Ouvrir, Modifier,
    Supprimer, « ↻ Refaire la sortie du stock Clover ») et « Rapport des pertes » (du … au …, par motif / catégorie /
    article / mois, part des ventes nettes). Les lignes en cours voyagent dans le formulaire (champs cachés)."""
    from .. import pertes as pe
    from .pages_rapports_web import onglets
    from . import taches

    onglet = ctx.req.query.get("onglet") or ctx.req.champ("onglet") or "declarer"
    if onglet == "liste":
        return _pertes_liste(ctx)
    if onglet == "rapport":
        return _pertes_rapport(ctx)
    pv, choix_pv, code = _point_vente(ctx)
    try:
        articles = _catalogue(ctx, pv)
    except (Exception, SystemExit) as erreur:  # noqa: BLE001
        ctx.app.noter(f"Pertes : {erreur!r}")
        return Reponse(corps=page(ctx, "Pertes et démarque", onglets("Déclarer une perte", ctx)
                                  + _message(erreur=f"✘ {erreur}")))
    from ..couts_sage import charger, correspondance

    liens = correspondance(ctx.racine, pv)
    try:
        couts = charger(ctx.racine, ctx.config)  # CUMP du jour (gardé), sinon lu dans Sage
    except (Exception, SystemExit):  # noqa: BLE001 — Sage illisible : coût Clover
        couts = {}
    par_cle = {f"{a.get('name', '')} — {a.get('code') or a.get('sku') or a['id'][:6]}": a for a in articles}
    par_id = {a["id"]: a for a in articles}
    lignes = []  # (id Clover, quantité) des lignes en cours
    for ident, q in zip(ctx.req.champs("lid"), ctx.req.champs("lq")):
        if ident in par_id:
            try:
                lignes.append((ident, Decimal(q)))
            except InvalidOperation:
                pass
    v = {k: (ctx.req.champ(k) if ctx.req.methode == "POST" else ctx.req.query.get(k, "")) for k in
         ("jour", "motif", "remarque", "article", "quantite", "edition")}
    v["jour"] = v["jour"] or date.today().isoformat()
    v["motif"] = v["motif"] or pe.MOTIFS[0]
    v["quantite"] = v["quantite"] or "1"
    edition = int(v["edition"]) if v["edition"].isdigit() else None
    message = etat = ""
    action = ctx.req.champ("action") if ctx.req.methode == "POST" else ""
    if action in ("Ajouter la ligne", "Mettre à jour la ligne"):
        a = par_cle.get(v["article"].strip())
        try:
            quantite = Decimal(v["quantite"].replace(",", ".").strip())
            if quantite <= 0:
                raise InvalidOperation
        except InvalidOperation:
            quantite = None
        if not a:
            etat = "✘ Choisissez un article de la liste."
        elif quantite is None:
            etat = "✘ Quantité invalide."
        else:
            if edition is not None and edition < len(lignes):
                lignes[edition] = (a["id"], quantite)
            else:
                lignes.append((a["id"], quantite))
            if pe.ligne(a, quantite, liens, couts).source_cout == "Coût inconnu":
                etat = "⚠ Coût inconnu : la valeur de cette ligne est 0."
            v["article"], v["quantite"], edition = "", "1", None
    elif action.startswith("Reprendre ") and action[10:].isdigit() and int(action[10:]) < len(lignes):
        edition = int(action[10:])
        ident, q = lignes[edition]
        v["article"] = next((k for k, a in par_cle.items() if a["id"] == ident), "")
        v["quantite"] = f"{q.normalize():f}".replace(".", ",")
    elif action == "Retirer la ligne":
        rang = ctx.req.champ("rang")
        if rang.isdigit() and int(rang) < len(lignes):
            del lignes[int(rang)]
        edition = None
    elif action == "Ajouter les produits périmés en stock":
        from ..peremption import lire_date

        deja, n = {x for x, _q in lignes}, 0
        for a in articles:
            jour = lire_date(a.get("sku"))
            stock = Decimal(str((a.get("itemStock") or {}).get("quantity") or 0))
            if jour and jour < date.today() and stock > 0 and a["id"] not in deja:
                lignes.append((a["id"], stock))
                n += 1
        v["motif"] = "Périmé"
        etat = f"{n} produit(s) périmé(s) en stock ajouté(s) : vérifiez les quantités."
    elif action == "Enregistrer et sortir du stock":
        action_nom = "Sortir des pertes du stock"
        try:
            date.fromisoformat(v["jour"].strip())
        except ValueError:
            etat = "✘ Date au format AAAA-MM-JJ."
        else:
            if not action_permise(ctx, action_nom):
                message = _message(erreur=f"Votre profil n'a pas le droit « {action_nom} ».")
            elif not lignes:
                etat = "✘ Ajoutez au moins un article."
            else:
                from ..points_vente import permis as pv_permis

                choisi = next((x for x in pv_permis(ctx.config, None) if str(x.code) == str(code)), None)
                try:
                    with ctx.app.ecriture:
                        perte = pe.nouvelle(pe.Registre(ctx.racine), v["jour"].strip(), v["motif"],
                                            [pe.ligne(par_id[x], q, liens, couts) for x, q in lignes],
                                            choisi.depot_sage if choisi and pv else "", ctx.u.nom,
                                            v["remarque"].strip(), str(code) if pv else "")
                except ValueError as erreur:
                    etat = f"✘ {erreur}"
                else:
                    def sortir(journal):
                        fait = pe.appliquer(ctx.racine, ctx.config, perte.numero)
                        return [f"{fait.numero} — {argent(fait.valeur)}"] + fait.messages

                    return taches.lancer(ctx, f"Perte {perte.numero} sortie du stock", sortir, "/pertes?onglet=liste")
    objets = [pe.ligne(par_id[x], q, liens, couts) for x, q in lignes]
    rangees = [[f"<input type='radio' name='rang' value='{n}'{' checked' if n == edition else ''}>",
                f"<button class='lien' name='action' value='Reprendre {n}'>{e(l.nom)}</button>",
                e(l.numero_sage or "Non relié"), f"{Decimal(l.quantite).normalize():f}".replace(".", ","),
                argent(Decimal(l.cout)), e(l.source_cout), argent(l.valeur)] for n, l in enumerate(objets)]
    total = f"{len(objets)} ligne(s) — valeur au coût {argent(sum((l.valeur for l in objets), pe.ZERO))}"
    caches = "".join(f"<input type='hidden' name='lid' value='{e(x)}'><input type='hidden' name='lq' value='{q}'>"
                     for x, q in lignes)
    motifs = "".join(f"<option{' selected' if m == v['motif'] else ''}>{e(m)}</option>" for m in pe.MOTIFS)
    liste = "<datalist id='articles'>" + "".join(f"<option value='{e(k)}'>" for k in sorted(par_cle, key=str.casefold)) \
        + "</datalist>"
    corps = (onglets("Déclarer une perte", ctx) + message
             + f"<form method='post' class='carte'>{csrf(ctx)}{caches}<input type='hidden' name='pv' value='{e(code)}'>"
             + (f"<input type='hidden' name='edition' value='{edition}'>" if edition is not None else "")
             + f"<div class='ligne'><div><label>Date</label><input type='date' name='jour' value='{e(v['jour'])}'></div>"
               f"<div><label>Motif *</label><select name='motif'>{motifs}</select></div>{choix_pv}<div><label>"
               f"Remarque</label><input name='remarque' value='{e(v['remarque'])}' size='28'></div></div>"
               f"<div class='ligne'><div class='large'><label>Article</label><input name='article' list='articles' "
               f"value='{e(v['article'])}' size='48'>{liste}</div><div><label>Quantité</label><input name='quantite' "
               f"value='{e(v['quantite'])}' size='8'></div><button name='action' value='"
             + ("Mettre à jour la ligne'>✔ Mettre à jour la ligne" if edition is not None else
                "Ajouter la ligne'>➕ Ajouter la ligne")
             + "</button><button class='second' name='action' value='Retirer la ligne'>✖ Retirer la ligne</button>"
               "<button class='second' name='action' value='Ajouter les produits périmés en stock'>⏰ Ajouter les "
               "produits périmés en stock</button></div>"
             + tableau_section(Section("Lignes de la perte", ["", "Article", "N° Sage", "Quantité", "Coût unitaire",
                                                              "Coût d'après", "Valeur au coût"], rangees,
                                       html=set(range(7))))
             + f"<div class='ligne'><strong>{e(total)}</strong><button class='a-droite' name='action' "
               "value='Enregistrer et sortir du stock'>✔ Enregistrer et sortir du stock</button></div>"
             + (f"<p class='note'>{e(etat)}</p>" if etat else
                f"<p class='note'>{len(par_cle)} articles Clover ; coût = CUMP de Sage s'il est relié, sinon coût "
                "Clover. Cliquez sur un article de la liste pour le reprendre dans les champs.</p>")
             + "</form>")
    return Reponse(corps=page(ctx, "Pertes et démarque", corps))


def _pertes_liste(ctx: Contexte) -> Reponse:
    from .. import pertes as pe
    from ..points_vente import points_de_vente
    from .pages_rapports_web import onglets
    from . import taches

    message = ""
    pertes_ = pe.Registre(ctx.racine).pertes
    choisi = ctx.req.champ("perte") or ctx.req.query.get("perte", "")
    if ctx.req.methode == "POST":
        action = ctx.req.champ("action")
        p = next((x for x in pertes_ if x.numero == choisi), None)
        if p is None and action != "Ouvrir":
            message = _message(erreur="Choisissez une perte dans la liste.")
        elif action in ("Supprimer", "Modifier"):
            if not action_permise(ctx, "Supprimer"):
                message = _message(erreur="Votre profil n'a pas le droit « Supprimer ».")
            elif pe.est_annulee(p):
                message = _message(erreur=f"{p.numero} est déjà annulée.")
            else:
                modifier = action == "Modifier"

                def annuler(journal):
                    fait = pe.annuler(ctx.racine, ctx.config, p.numero, ctx.u.nom)
                    return fait.messages[-6:]

                retour = "/pertes?onglet=liste"
                if modifier:  # lignes reprises dans « Déclarer une perte »
                    from urllib.parse import urlencode

                    retour = "/pertes?" + urlencode([("jour", p.jour), ("motif", p.motif), ("remarque", p.remarque)]
                                                    + [(k, val) for l in p.lignes for k, val in
                                                       (("lid", l.id_clover), ("lq", str(l.quantite)))])
                return taches.lancer(ctx, f"Annulation de la perte {p.numero}", annuler, retour)
        elif action == "Refaire la sortie du stock Clover":
            def refaire(journal):
                fait = pe.appliquer(ctx.racine, ctx.config, p.numero)
                return [f"{fait.numero} — {argent(fait.valeur)}"] + fait.messages

            return taches.lancer(ctx, f"Sortie du stock Clover de {p.numero}", refaire, "/pertes?onglet=liste")
    noms = {x.code: x.libelle for x in points_de_vente(ctx.config)}
    lignes = [[f"<input type='radio' name='perte' value='{e(p.numero)}'{' checked' if p.numero == choisi else ''}>",
               e(p.jour), f"<a href='?onglet=liste&amp;perte={e(p.numero)}'>{e(p.numero)}</a>",
               e(noms.get(p.point_vente or "1", p.point_vente or "1")), e(p.motif), str(len(p.lignes)),
               argent(p.valeur), e(p.document), "Annulée" if pe.est_annulee(p) else "Déclarée", e(p.auteur),
               e(" ; ".join(m for m in p.messages if m != pe.ANNULEE))]
              for p in sorted(pertes_, key=lambda p: (p.jour, p.numero), reverse=True)]
    corps = (onglets("Pertes déclarées", ctx) + message
             + f"<form method='post'>{csrf(ctx)}<input type='hidden' name='onglet' value='liste'>"
               "<div class='barre-onglet'><a class='ouvrir' href='?onglet=liste'>🔄 Actualiser</a><button class='second' "
               "name='action' value='Ouvrir'>📂 Ouvrir</button><button class='second' name='action' value='Modifier'>✎ "
               "Modifier</button><button class='danger' name='action' value='Supprimer'>🗑 Supprimer</button><button "
               "class='second' name='action' value='Refaire la sortie du stock Clover'>↻ Refaire la sortie du stock "
               "Clover</button></div>"
             + tableau_section(Section("Pertes déclarées", ["", "Date", "N°", "Point de vente", "Motif", "Lignes",
                                                            "Valeur au coût", "Document de stock", "État",
                                                            "Déclarée par", "Messages"], lignes, html=set(range(11))))
             + "</form>")
    p = next((x for x in pertes_ if x.numero == choisi), None)
    if p is not None:  # « Ouvrir » : pièce de la perte
        infos = (f"Date : {p.jour}    Motif : {p.motif}    Dépôt : {p.depot or '—'}    Document de stock : "
                 f"{p.document or '—'}    Déclarée par : {p.auteur}" + (f"\nRemarque : {p.remarque}" if p.remarque else ""))
        corps += ("<div class='carte'>" + f"<h2>Perte {e(p.numero)}</h2><pre class='saisie'>{e(infos)}</pre>"
                  + tableau_section(Section(f"Lignes de {p.numero}", ["Article", "N° Sage", "Quantité",
                                                                     "Coût unitaire", "Valeur au coût", "Clover"],
                                            [[l.nom, l.numero_sage or "Non relié",
                                              f"{Decimal(l.quantite).normalize():f}", argent(Decimal(l.cout)),
                                              argent(l.valeur), "✔" if l.clover_fait else ""] for l in p.lignes]))
                  + f"<p class='note'>{e(chr(10).join(m for m in p.messages if m != pe.ANNULEE))}</p></div>")
    return Reponse(corps=page(ctx, "Pertes et démarque", corps))


def _pertes_rapport(ctx: Contexte) -> Reponse:
    from .. import pertes as pe
    from .pages_rapports_web import onglets

    def jour(cle, defaut):
        try:
            return date.fromisoformat(ctx.req.query.get(cle, ""))
        except ValueError:
            return defaut

    debut, fin = jour("du", date.today().replace(day=1)), jour("au", date.today())
    par = ctx.req.query.get("par") or "Motif"
    options = "".join(f"<option{' selected' if k == par else ''}>{e(k)}</option>" for k in pe.REGROUPEMENTS)
    corps = (onglets("Rapport des pertes", ctx)
             + "<form method='get' class='barre-onglet'><input type='hidden' name='onglet' value='rapport'><div><label>"
               f"Du</label><input type='date' name='du' value='{debut}'></div><div><label>au</label><input type='date' "
               f"name='au' value='{fin}'></div><div><label>Par</label><select name='par'>{options}</select></div>"
               "<input type='hidden' name='afficher' value='1'><button>🔍 Afficher</button></form>")
    if not ctx.req.query.get("afficher"):
        return Reponse(corps=page(ctx, "Pertes et démarque", corps + "<p class='note'>Choisissez la période puis "
                                                                     "« Afficher ».</p>"))
    cle = pe.REGROUPEMENTS.get(par, "motif")
    lignes, total = pe.rapport(pe.Registre(ctx.racine).pertes, debut, fin, cle)
    try:
        from ..points_vente import client
        from ..previsions import ventes_par_article_rapide

        ventes = ventes_par_article_rapide(client(ctx.racine), debut, min(fin, date.today()),
                                           ctx.racine / "donnees" / "cache_clover")
        nettes = sum((x.nettes for x in ventes.values()), pe.ZERO)
    except (Exception, SystemExit):  # noqa: BLE001
        nettes = pe.ZERO
    etat = (f"Pertes au coût : {argent(total)} ; ventes nettes : {argent(nettes)} ; pertes = {pe.taux(total, nettes)} des "
            "ventes.")
    corps += (f"<p class='note'>{e(etat)}</p>"
              + tableau_section(Section("Rapport des pertes", pe.ENTETES_RAPPORT, lignes)))
    return Reponse(corps=page(ctx, "Pertes et démarque", corps))


# --------------------------------------------------------------------------------------------- promotions
def promotions(ctx: Contexte) -> Reponse:
    """Comme fenetres_gestion4.FenetrePromotions : point de vente, Article (« nom — prix $ »), Prix promotionnel, Du …
    au …, « ➕ Ajouter » ; « ▶ Appliquer maintenant », « 📈 Calculer l'effet », « ✖ Annuler la promotion » (cochée) ;
    tableau Du, au, N°, point de vente, article, prix normal / promo, état, quantité et ventes avant -> pendant."""
    from .. import paquet3 as p3
    from . import taches

    pv, choix_pv, code = _point_vente(ctx)
    action_nom = "Changer les prix Clover (promotions)"
    try:
        catalogue = _catalogue(ctx, pv)
    except (Exception, SystemExit):  # noqa: BLE001
        catalogue = []
    articles = {f"{a.get('name', '')} — {Decimal(int(a.get('price') or 0)) / 100} $": a for a in catalogue}
    v = {k: ctx.req.champ(k) for k in ("article", "prix", "du", "au")}
    v["du"] = v["du"] or date.today().isoformat()
    v["au"] = v["au"] or (date.today() + timedelta(days=6)).isoformat()
    etat = "Le traitement de nuit met le prix promotionnel le premier jour et remet le prix normal après le dernier jour."
    erreur = False
    if ctx.req.methode == "POST":
        action = ctx.req.champ("action")
        if not action_permise(ctx, action_nom):
            etat, erreur = f"✘ Votre profil n'a pas le droit « {action_nom} ».", True
        elif action == "Ajouter":
            a = articles.get(v["article"].strip())
            try:
                prix = Decimal(v["prix"].replace(",", ".").replace("$", "").strip())
                if not a:
                    raise ValueError("Choisissez un article de la liste.")
                with ctx.app.ecriture:
                    promo = p3.Promotions(ctx.racine).ajouter(a["id"], a.get("name", ""), prix,
                                                              date.fromisoformat(v["du"]), date.fromisoformat(v["au"]),
                                                              ctx.u.nom, str(code) if pv else "")
                etat = f"✔ {promo.numero} prévue."
                v["article"] = v["prix"] = ""
            except (InvalidOperation, ValueError, TypeError) as exc:
                etat, erreur = "✘ " + (str(exc) if str(exc) and "Decimal" not in str(exc) else
                                       "Prix promotionnel invalide."), True
        elif action == "Appliquer maintenant":
            def appliquer(journal):
                return p3.appliquer_promotions(ctx.racine, _client(ctx, pv), code=str(code) if pv else "1") or \
                    ["Rien à faire aujourd'hui."]

            return taches.lancer(ctx, "Mise à jour des prix dans Clover", appliquer, "/promotions")
        elif action == "Annuler la promotion":
            numero = ctx.req.champ("numero")
            promo = next((x for x in p3.Promotions(ctx.racine).liste if x.numero == numero), None)
            if promo is None:
                etat, erreur = "✘ Cochez la promotion à annuler dans le tableau.", True
            elif promo.etat not in (p3.PREVUE, p3.EN_COURS):
                etat, erreur = f"✘ {promo.numero} est déjà terminée ou annulée.", True
            else:
                def annuler(journal):
                    from ..points_vente import client as client_de, point_de_vente

                    return p3.annuler_promotion(ctx.racine, numero, client_de(ctx.racine, point_de_vente(
                        ctx.config, promo.point_vente or None)))

                return taches.lancer(ctx, f"Annulation de la promotion {numero}", annuler, "/promotions")
    liste = sorted(p3.Promotions(ctx.racine).liste, key=lambda x: x.du, reverse=True)
    effets = (ctx.app.memoire.get("effets_promotions") or (0, {}))[1]
    if ctx.req.query.get("effet"):
        effets = _effets_promotions(ctx, liste)
        ctx.app.memoire["effets_promotions"] = (time.time(), effets)
        etat = "Effet = ventes pendant la promotion contre la même durée juste avant."
    lignes = []
    for x in liste:
        ef = effets.get(x.numero)
        lignes.append([f"<input type='radio' name='numero' value='{e(x.numero)}'>", e(x.du), e(x.au), e(x.numero),
                       e(x.point_vente or "1"), e(x.nom), argent(Decimal(x.prix_normal)) if x.prix_normal else "",
                       argent(Decimal(x.prix_promo)), e(x.etat), e(f"{ef[1]} -> {ef[0]}") if ef else "",
                       e(argent(ef[3]) + " -> " + argent(ef[2])) if ef else "", e(" ; ".join(x.messages[-2:]))])
    liste_a = "<datalist id='articles'>" + "".join(f"<option value='{e(k)}'>" for k in sorted(articles, key=str.casefold)) \
        + "</datalist>"
    corps = (f"<form method='post'>{csrf(ctx)}<input type='hidden' name='pv' value='{e(code)}'>"
             f"<div class='barre-onglet'>{choix_pv}<div class='large'><label>Article</label><input name='article' "
             f"list='articles' value='{e(v['article'])}' size='40'>{liste_a}</div><div><label>Prix promotionnel</label>"
             f"<input name='prix' value='{e(v['prix'])}' size='8'></div><div><label>Du</label><input type='date' "
             f"name='du' value='{e(v['du'])}'></div><div><label>au</label><input type='date' name='au' "
             f"value='{e(v['au'])}'></div><button name='action' value='Ajouter'>➕ Ajouter</button></div>"
             "<div class='barre-onglet'><button class='second' name='action' value='Appliquer maintenant'>▶ Appliquer "
             "maintenant</button><a class='ouvrir' href='/promotions?effet=1'>📈 Calculer l'effet</a><button "
             "class='danger' name='action' value='Annuler la promotion'>✖ Annuler la promotion</button></div>"
             f"<p class='{'erreur-texte' if erreur else 'note'}'>{e(etat)}</p>"
             + tableau_section(Section("Promotions", ["", "Du", "au", "N°", "Point de vente", "Article", "Prix normal",
                                                      "Prix promo", "État", "Quantité (avant -> pendant)",
                                                      "Ventes (avant -> pendant)", "Messages"], lignes,
                                       html=set(range(12))))
             + "</form>")
    return Reponse(corps=page(ctx, "Promotions", corps))


def _effets_promotions(ctx: Contexte, liste) -> dict:
    """Comme FenetrePromotions.calculer_effet."""
    from .. import paquet3 as p3
    from ..points_vente import cache_clover, client as client_de, point_de_vente
    from ..previsions import ventes_par_article_rapide

    effets = {}
    for x in liste:
        if x.etat not in (p3.EN_COURS, p3.TERMINEE):
            continue
        try:
            pv = point_de_vente(ctx.config, x.point_vente or None)
            client, cache = client_de(ctx.racine, pv), cache_clover(ctx.racine, pv)
            du, au = date.fromisoformat(x.du), min(date.fromisoformat(x.au), date.today())
            duree = (au - du).days + 1
            pendant = ventes_par_article_rapide(client, du, au, cache)
            avant = ventes_par_article_rapide(client, du - timedelta(days=duree), du - timedelta(days=1), cache)
            effets[x.numero] = p3.effet(x, pendant, avant)
        except (Exception, SystemExit) as erreur:  # noqa: BLE001
            ctx.app.noter(f"Effet de {x.numero} : {erreur!r}")
    return effets


# --------------------------------------------------------------------------------------------- étiquettes
def etiquettes(ctx: Contexte) -> Reponse:
    """Comme fenetres_gestion3.FenetreEtiquettes : point de vente, Article, Nombre, « ➕ Ajouter », « Prix changés
    depuis » + « 🏷 Ajouter ces articles », Format (ticket 80 / 58 mm, feuille Avery), « 🖨 Imprimer les étiquettes »,
    « 🗑 Vider la liste » ; liste Article, Prix, Unité, Code. Les étiquettes choisies voyagent dans le formulaire.
    Le serveur n'a pas les imprimantes du poste : les formats de ticket proposés sont 80 et 58 mm."""
    from .. import etiquettes as et

    pv, choix_pv, code = _point_vente(ctx)
    try:
        catalogue = _catalogue(ctx, pv)
    except (Exception, SystemExit) as erreur:  # noqa: BLE001
        return Reponse(corps=page(ctx, "Étiquettes de prix", _message(erreur=f"✘ {erreur}")))
    articles = {f"{a.get('name', '')} — {a.get('code') or a.get('sku') or a['id'][:6]}": a for a in catalogue
                if not a.get("hidden")}
    par_id = {a["id"]: a for a in catalogue}
    choisis = [x for x in ctx.req.champs("eid") if x in par_id]
    formats = et.formats(imprimantes=[])
    format_ = ctx.req.champ("format") or next(iter(formats))
    depuis = ctx.req.champ("depuis") or (date.today() - timedelta(days=7)).isoformat()
    etat = ("Une étiquette par ticket sur l'imprimante de caisse (largeur de son rouleau), ou feuilles Avery 5160 : "
            "nom, prix, code-barres du code produit.")
    if ctx.req.methode == "POST":
        action = ctx.req.champ("action")
        if action == "Ajouter":
            a = articles.get(ctx.req.champ("article").strip())
            try:
                n = max(1, min(300, int(ctx.req.champ("nombre") or "1")))
            except ValueError:
                n = 1
            if a:
                choisis += [a["id"]] * n
            else:
                etat = "✘ Choisissez un article de la liste."
        elif action == "Ajouter ces articles":
            ids = et.prix_changes(ctx.racine, depuis.strip())
            choisis += [a["id"] for a in articles.values() if a["id"] in ids]
        elif action == "Vider la liste":
            choisis = []
        elif action == "Imprimer les étiquettes":
            if not action_permise(ctx, "Imprimer des étiquettes"):
                etat = "✘ Votre profil n'a pas le droit « Imprimer des étiquettes »."
            elif choisis:
                return Reponse(corps=et.page([et.depuis_article(par_id[x]) for x in choisis], imprimer=False,
                                             largeur_ticket=formats.get(format_)), style_en_ligne=True)
    lignes = []
    for x in choisis:
        t_ = et.depuis_article(par_id[x])
        lignes.append([t_.nom, argent(t_.prix), t_.unite, t_.code])
    caches = "".join(f"<input type='hidden' name='eid' value='{e(x)}'>" for x in choisis)
    liste = "<datalist id='articles'>" + "".join(f"<option value='{e(k)}'>" for k in sorted(articles, key=str.casefold)) \
        + "</datalist>"
    options = "".join(f"<option{' selected' if k == format_ else ''}>{e(k)}</option>" for k in formats)
    corps = (f"<form method='post'>{csrf(ctx)}{caches}<input type='hidden' name='pv' value='{e(code)}'>"
             f"<div class='barre-onglet'>{choix_pv}<div class='large'><label>Article</label><input name='article' "
             f"list='articles' size='44'>{liste}</div><div><label>Nombre</label><input name='nombre' value='1' size='4'>"
             "</div><button name='action' value='Ajouter'>➕ Ajouter</button><div><label>Prix changés depuis</label>"
             f"<input type='date' name='depuis' value='{e(depuis)}'></div><button class='second' name='action' "
             "value='Ajouter ces articles'>🏷 Ajouter ces articles</button></div>"
             f"<div class='barre-onglet'><div><label>Format</label><select name='format'>{options}</select></div>"
             "<button name='action' value='Imprimer les étiquettes' formtarget='_blank'>🖨 Imprimer les étiquettes"
             "</button><button class='second' name='action' value='Vider la liste'>🗑 Vider la liste</button></div>"
             f"<p class='note'>{e(etat)} {len(choisis)} étiquette(s).</p>"
             + tableau_section(Section("Étiquettes", ["Article", "Prix", "Unité", "Code"], lignes))
             + "</form><p class='note'>« Imprimer » ouvre la page des étiquettes : imprimez-la avec Ctrl+P.</p>")
    return Reponse(corps=page(ctx, "Étiquettes de prix", corps))


# --------------------------------------------------------------------------------------------- prix et marges
def _montant(v) -> str:
    return "" if v is None else f"{v:,.2f} $".replace(",", " ").replace(".", ",")


def _pourcent(v) -> str:
    return "" if v is None else f"{v} %".replace(".", ",")


def prix_marges(ctx: Contexte) -> Reponse:
    """Comme fenetre_prix_marges.ouvrir (FenetreACocher + « Marge minimale » et « Arrondi ») : articles Clover sous la
    marge minimale, prix proposé coché, « Mettre à jour les prix dans Clover »."""
    from .. import prix_marges as pm
    from .a_cocher import choisies, page_a_cocher
    from . import taches

    q = ctx.req.query
    try:
        marge = int(q.get("marge") or ctx.req.champ("marge") or 25)
    except ValueError:
        marge = 25
    mode = q.get("arrondi") or ctx.req.champ("arrondi") or pm.ARRONDIS[0]
    cle = "prix_marges"
    gardee = ctx.app.memoire.get(cle)
    try:  # changer la marge ou l'arrondi recalcule sans relire Clover ni Sage (comme Windows)
        donnees = gardee[1] if gardee and time.time() - gardee[0] < 600 and not q.get("actualiser") else None
        if donnees is None:
            donnees = pm.lire_donnees(ctx.racine, ctx.config)
            ctx.app.memoire[cle] = (time.time(), donnees)
    except (Exception, SystemExit) as erreur:  # noqa: BLE001 — tableau vide avec ses colonnes
        ctx.app.noter(f"Prix et marges : {erreur!r}")
        donnees = {"articles": [], "liens": {}, "couts": {}, "ventes": {}}
        ctx.absents.update({"Clover", "Sage"})
    lignes, correctes = pm.analyser(donnees["articles"], donnees["liens"], donnees["couts"], donnees["ventes"], marge,
                                    mode)
    if ctx.req.methode == "POST" and ctx.req.champ("action") == "lancer":
        action_nom = "Changer les prix Clover (promotions)"
        retenues = choisies(ctx, lignes)
        if not action_permise(ctx, action_nom):
            return Reponse(corps=page(ctx, "Prix et marges", _message(
                erreur=f"Votre profil n'a pas le droit « {action_nom} ».")))
        if not retenues:
            return Reponse(corps=page(ctx, "Prix et marges", _message(erreur="Cochez au moins une ligne.")))

        def appliquer(journal):
            resultats = pm.appliquer(ctx.racine, retenues)
            ctx.app.memoire.pop(cle, None)
            erreurs = [(l, err) for l, err in resultats if err]
            return ([f"{len(resultats) - len(erreurs)} prix mis à jour dans Clover (journal : "
                     "donnees/journal_prix_clover.csv)."]
                    + [f"Non mis à jour : {l.nom} : {err}" for l, err in erreurs[:15]])

        return taches.lancer(ctx, f"Nouveaux prix dans Clover ({len(retenues)})", appliquer,
                             f"/prix-marges?marge={marge}&arrondi={mode}")
    sous = [l for l in lignes if l.etat == pm.SOUS_MARGE]
    effet = sum((l.effet or 0 for l in sous), 0)
    resume = (f"{len(sous)} article(s) sous {marge} % de marge (proposés cochés), "
              f"{sum(1 for l in lignes if l.etat == pm.A_VERIFIER)} à vérifier, {correctes} à la bonne marge. Effet "
              f"estimé des lignes proposées sur {pm.JOURS_VENTES} jours de ventes : {_montant(effet)}. Coût = CUMP de "
              "Sage (sinon coût Clover) ; rien ne change dans Clover sans votre clic.")
    marges = "".join(f"<option{' selected' if m_ == marge else ''}>{m_}</option>" for m_ in pm.MARGES)
    arrondis = "".join(f"<option{' selected' if a_ == mode else ''}>{e(a_)}</option>" for a_ in pm.ARRONDIS)
    reglages = (f"<div><label>Marge minimale</label><select name='marge'>{marges}</select> %</div><div><label>Arrondi"
                f"</label><select name='arrondi'>{arrondis}</select></div>")
    corps = page_a_cocher(
        ctx, "/prix-marges",
        "Articles Clover dont la marge (prix Clover − coût) est sous la marge minimale choisie, avec le prix proposé "
        "(coût / (1 − marge), arrondi). Cochez les prix à changer, puis « Mettre à jour les prix dans Clover ».",
        ["Article Clover", "Catégorie", "N° Sage", "Coût", "Source du coût", "Prix Clover", "Marge", "Prix proposé",
         "Marge après", "Vendu 90 j", "Effet 90 j", "État", "Remarque"], lignes,
        lambda l: (l.nom, l.categorie, l.numero_sage, _montant(l.cout), l.source_cout or "", _montant(l.prix),
                   _pourcent(l.marge), _montant(l.nouveau), _pourcent(l.marge_apres),
                   f"{l.vendu.normalize():f}".replace(".", ",") if l.vendu else "", _montant(l.effet), l.etat,
                   l.note or ""),
        resume, "Mettre à jour les prix dans Clover", reglages, {"marge": marge, "arrondi": mode})
    return Reponse(corps=page(ctx, "Prix et marges", corps))


# --------------------------------------------------------------------------------------------- coûts Clover
def couts_clover(ctx: Contexte) -> Reponse:
    """Comme fenetre_couts.FenetreCoutsClover : le CUMP de Sage remplace le coût Clover des lignes cochées ; jamais de
    valeur aberrante (non cochable)."""
    from .. import couts_clover as cc
    from .a_cocher import choisies, page_a_cocher
    from . import taches

    cle = "couts_clover"
    gardee = ctx.app.memoire.get(cle)
    try:
        if gardee and time.time() - gardee[0] < 600 and not ctx.req.query.get("actualiser"):
            propositions, a_jour = gardee[1]
        else:
            propositions, a_jour = cc.lire(ctx.racine, ctx.config)
            ctx.app.memoire[cle] = (time.time(), (propositions, a_jour))
    except (Exception, SystemExit) as erreur:  # noqa: BLE001 — tableau vide avec ses colonnes
        ctx.app.noter(f"Coûts Clover : {erreur!r}")
        propositions, a_jour = [], 0
        ctx.absents.update({"Clover", "Sage"})
    if ctx.req.methode == "POST" and ctx.req.champ("action") == "lancer":
        retenues = choisies(ctx, propositions)
        if not retenues:
            return Reponse(corps=page(ctx, "Coûts Clover depuis Sage", _message(erreur="Cochez au moins une ligne.")))

        def appliquer(journal):
            resultats = cc.appliquer(ctx.racine, retenues)
            ctx.app.memoire.pop(cle, None)
            erreurs = [f"{x.nom} : {err}" for x, err in resultats if err]
            return [f"{len(resultats) - len(erreurs)} coût(s) Clover mis à jour."] + erreurs[:15]

        return taches.lancer(ctx, f"Coûts Clover mis à jour ({len(retenues)})", appliquer, "/couts-clover")

    def valeurs(x):
        ecart = "" if x.cump is None or x.cout_clover is None else f"{x.cump - x.cout_clover:+.2f}".replace(".", ",")
        marge = "" if not x.prix or x.cump is None else f"{(x.prix - x.cump) / x.prix * 100:.0f} %"
        return (x.nom, x.numero_sage, _montant(x.prix), _montant(x.cout_clover), _montant(x.cump), ecart, marge, x.etat,
                x.note or "")

    corps = page_a_cocher(
        ctx, "/couts-clover",
        "Le coût moyen (CUMP) de l'article dans Sage remplace le coût Clover. Cochez les lignes à mettre à jour, puis "
        "lancez la mise à jour. Jamais de valeur aberrante : CUMP absent, plus de 5 fois le prix de vente ou sous 5 % "
        "du prix.",
        ["Article Clover", "N° Sage", "Prix de vente", "Coût Clover", "Coût Sage (CUMP)", "Écart", "Marge", "État",
         "Remarque"], propositions, valeurs,
        f"{len(propositions)} article(s) proposé(s), {a_jour} déjà au coût Sage. Les valeurs aberrantes (grisées) ne "
        "peuvent pas être cochées.", "Mettre à jour les coûts Clover")
    return Reponse(corps=page(ctx, "Coûts Clover depuis Sage", corps))


# --------------------------------------------------------------------------------------------- comptes par catégorie
def comptes_categories(ctx: Contexte) -> Reponse:
    """Comme fenetre_article.FenetreCategories : table catégorie Clover -> préfixe et comptes Sage (actif, produits,
    CMV, écart = CMV) ; ligne choisie modifiée dans la carte (Appliquer, ➕, 🗑) ; « Proposer depuis Sage » ;
    « 🔎 Articles Sage à corriger… » (articles dont les comptes ne suivent pas la table, cochés puis corrigés dans
    Sage) ; « Enregistrer » vérifie les comptes dans le plan comptable."""
    from ..creation_articles import ComptesCategorie, TableCategories
    from .consultations import Section, tableau_section
    from . import taches

    table = TableCategories(ctx.racine)
    choisi = ctx.req.champ("categorie") or ctx.req.query.get("categorie", "")
    op = ctx.req.query.get("op", "")
    selection = bool(ctx.req.query.get("selection") or ctx.req.champ("selection"))  # ouverte par « Créer un article »
    message = ""
    if ctx.req.methode == "POST":
        action = ctx.req.champ("action")
        try:
            if action == "Valider la sélection":
                c_ = table.lignes.get(choisi)
                if c_ is None:
                    raise ValueError("Choisissez la catégorie de l'article.")
                if c_.problemes():
                    raise ValueError(f"Comptes de « {choisi} » incomplets : " + " ; ".join(c_.problemes())
                                     + ". Complétez-les puis « Appliquer ».")
                from urllib.parse import quote

                from .serveur import redirection

                return redirection(f"/creer-article?reprendre=1&categorie={quote(choisi)}")
            if action == "Proposer depuis Sage":
                def proposer(journal):
                    from ..fenetre_article import proposer_depuis_sage

                    propositions = proposer_depuis_sage(ctx.racine)
                    with ctx.app.ecriture:
                        t_ = TableCategories(ctx.racine)
                        n = 0
                        for nom, c in propositions.items():
                            actuel = t_.lignes.get(nom)
                            if actuel is None or actuel.problemes():  # jamais une ligne déjà complète
                                t_.lignes[nom] = c
                                n += 1
                        t_.enregistrer()
                    return [f"{n} catégorie(s) proposée(s) : vérifiez-les dans la table."]

                return taches.lancer(ctx, "Comptes proposés depuis Sage", proposer, "/comptes-categories")
            if action == "Corriger dans Sage":
                return _corriger_comptes(ctx)
            with ctx.app.ecriture:
                table = TableCategories(ctx.racine)
                if action == "➕":
                    nom = ctx.req.champ("nouvelle").strip()
                    if not nom:
                        raise ValueError("Tapez le nom de la catégorie Clover.")
                    if nom in table.lignes:
                        raise ValueError(f"« {nom} » est déjà dans la table.")
                    table.lignes[nom] = ComptesCategorie(nom)
                    choisi = nom
                elif action == "🗑":
                    if not action_permise(ctx, "Supprimer"):
                        raise ValueError("Votre profil n'a pas le droit « Supprimer ».")
                    table.lignes.pop(choisi, None)
                    choisi = ""
                elif action == "Appliquer":
                    if choisi not in table.lignes:
                        raise ValueError("Choisissez une catégorie dans la liste.")
                    table.lignes[choisi] = ComptesCategorie(choisi, *(ctx.req.champ(k).strip() for k in
                                                                       ("prefixe", "actif", "produits", "cmv", "ecart")))
                if action in ("Appliquer", "Enregistrer", "➕", "🗑"):
                    from ..plan_comptable import comptes_connus, problemes

                    numeros = {getattr(l, c, "") for l in table.lignes.values()
                               for c in ("actif", "produits", "cmv", "ecart")}
                    erreurs = problemes(numeros, comptes_connus(ctx.racine, ctx.config))
                    if erreurs:  # comptes de la table : présents dans le plan comptable (règle du 2026-11-01)
                        raise ValueError("⚠ " + " ; ".join(erreurs[:4]) + (" …" if len(erreurs) > 4 else ""))
                    table.enregistrer()
                    message = _message("✔ Table enregistrée.")
        except ValueError as erreur:
            message = _message(erreur=str(erreur))
        table = TableCategories(ctx.racine)
    lignes = [[f"<input type='radio' name='categorie' value='{e(nom)}'{' checked' if nom == choisi else ''}>", e(nom),
               e(c.prefixe), e(c.actif), e(c.produits), e(c.cmv), e(c.ecart)]
              for nom, c in sorted(table.lignes.items(), key=lambda x: x[0].lower())]
    classes = ["etat-ecart" if c.problemes() else "" for _n, c in sorted(table.lignes.items(),
                                                                         key=lambda x: x[0].lower())]
    c = table.lignes.get(choisi)
    edition = ""
    if c is not None:
        edition = (f"<strong class='periode'>{e(c.categorie)}</strong>" + "".join(
            f"<div><label>{lib}</label><input name='{k}' value='{e(getattr(c, k))}' size='{6 if k == 'prefixe' else 8}'>"
            "</div>" for k, lib in (("prefixe", "Préfixe"), ("actif", "Actif"), ("produits", "Produits"),
                                    ("cmv", "CMV"), ("ecart", "Écart")))
            + "<button class='second' name='action' value='Appliquer'>Appliquer</button>")
    choix_html = ("<input type='hidden' name='selection' value='1'><div class='ligne-etat'>Choisissez la catégorie de "
                  "l'article (« Valider la sélection »). Comptes modifiables : « Appliquer » avant de valider.</div>"
                  if selection else "")
    valider = ("<div class='barre-onglet'><span class='a-droite'><a class='ouvrir' href='/creer-article?reprendre=1'>"
               "✖ Fermer</a> <button name='action' value='Valider la sélection'>✔ Valider la sélection</button></span>"
               "</div>" if selection else "")
    corps = (message + f"<form method='post'>{csrf(ctx)}{choix_html}"
             + tableau_section(Section("Comptes Sage par catégorie Clover", ["", "Catégorie", "Préfixe", "Actif",
                                                                            "Produits", "CMV", "Écart"], lignes,
                                       classes=classes, html=set(range(7))))
             + f"<div class='barre-onglet'>{edition}<button class='second' name='action' value='Choisir'>"
               "Modifier la catégorie cochée</button><div><label>Nouvelle catégorie</label><input name='nouvelle' "
               "size='18'></div><button class='second' name='action' value='➕'>➕</button><button class='danger' "
               "name='action' value='🗑'>🗑</button></div>"
               "<p class='note'>Règle : actif 15xx -> produits 40xx / CMV 50xx ; écart = CMV. En rose : comptes "
               "incomplets.</p><div class='barre-onglet'><button class='second' name='action' value='Proposer depuis "
               "Sage'>Proposer depuis Sage</button><a class='ouvrir' href='/comptes-categories?op=verifier'>🔎 Articles "
               "Sage à corriger…</a><button class='a-droite' name='action' value='Enregistrer'>Enregistrer</button>"
               "</div>" + valider + "</form>"
             + (_articles_a_corriger(ctx) if op == "verifier" else ""))
    return Reponse(corps=page(ctx, "Comptes Sage par catégorie", corps))


def _articles_a_corriger(ctx: Contexte) -> str:
    """Comme fenetre_couts.FenetreComptesSage : articles dont un compte diffère de la table, « Compte manquant
    (import bloqué) » d'abord et coché."""
    from ..correspondance import lire_correspondances
    from ..creation_articles import TableCategories, comptes_a_corriger
    from ..fenetre_couts import COMPTE_MANQUANT, LigneComptes
    from .consultations import Section, lire_ou_vide, tableau_section

    try:
        articles = lire_ou_vide(ctx, lambda b: b.requete(
            "SELECT sPartCode, sName, lAcNAsset, lAcNRev, lAcNExp, lAcNVar FROM tinvent WHERE bService = 0"))
        corrections, inconnus = comptes_a_corriger(
            articles, TableCategories(ctx.racine),
            lire_correspondances(ctx.racine / "donnees" / "correspondance_articles.xlsx"))
    except (Exception, SystemExit) as erreur:  # noqa: BLE001
        ctx.app.noter(f"Comptes à corriger : {erreur!r}")
        corrections, inconnus = [], 0
    lignes_c = sorted((LigneComptes(c) for c in corrections), key=lambda l: l.etat != COMPTE_MANQUANT)
    lignes = [[f"<input type='checkbox' name='numero' value='{e(l.c.numero)}'{' checked' if l.cochee_par_defaut else ''}>",
               e(l.c.numero), e(l.c.description), e(l.c.categorie), e(l.c.source),
               e(" / ".join(x or "—" for x in l.c.actuel)), e(" / ".join(l.c.attendu)), e(", ".join(l.c.changements)),
               e(l.etat)] for l in lignes_c]
    return (f"<form method='post' class='carte'>{csrf(ctx)}<h2>Comptes Sage à corriger</h2><p class='note'>"
            f"{len(corrections)} article(s) Sage dont les comptes ne suivent pas la table ; {inconnus} sans catégorie "
            "reconnue. Un changement du compte d'actif est proposé décoché. Cochez les lignes à corriger, puis lancez "
            "la correction : l'application ouvre Sage elle-même s'il est fermé.</p>"
            + tableau_section(Section("Articles Sage à corriger", ["", "N° Sage", "Description Sage", "Catégorie",
                                                                  "Selon", "Comptes actuels", "Comptes de la table",
                                                                  "À changer", "État"], lignes,
                                      classes=["etat-ecart" if l.etat == COMPTE_MANQUANT else "" for l in lignes_c],
                                      html=set(range(9))))
            + "<div class='barre-onglet'><button name='action' value='Corriger dans Sage'>▶ Corriger dans Sage"
              "</button></div></form>")


def _corriger_comptes(ctx: Contexte):
    from ..creation_articles import TableCategories, comptes_a_corriger, creer_dans_sage
    from ..correspondance import lire_correspondances
    from ..robot_articles import ArticleACreer
    from .consultations import lire_ou_vide
    from . import taches

    numeros = set(ctx.req.champs("numero"))
    if not numeros:
        return Reponse(corps=page(ctx, "Comptes Sage par catégorie", _message(erreur="Cochez au moins une ligne.")))

    def corriger(journal):
        articles = lire_ou_vide(ctx, lambda b: b.requete(
            "SELECT sPartCode, sName, lAcNAsset, lAcNRev, lAcNExp, lAcNVar FROM tinvent WHERE bService = 0"))
        corrections, _inconnus = comptes_a_corriger(
            articles, TableCategories(ctx.racine),
            lire_correspondances(ctx.racine / "donnees" / "correspondance_articles.xlsx"))
        choisies = [ArticleACreer(c.numero, c.description, *c.attendu) for c in corrections if c.numero in numeros]
        resultats = creer_dans_sage(ctx.racine, ctx.config, choisies, comptes=True)
        erreurs = [f"{r['numero']} : {' ; '.join(m for m in r['messages'] if m)}" for r in resultats if not r["cree"]]
        return [f"{len(resultats) - len(erreurs)} article(s) corrigé(s) dans Sage."] + erreurs[:15]

    return taches.lancer(ctx, f"Correction des comptes de {len(numeros)} article(s)", corriger,
                         "/comptes-categories?op=verifier", sage=True)


# --------------------------------------------------------------------------------------------- plan comptable
def plan_comptable(ctx: Contexte) -> Reponse:
    """Comme fenetre_plan_comptable.FenetrePlanComptable : « Rechercher : », « 🔄 Actualiser », « ➕ Ajouter »,
    « ✎ Modifier », « 🗑 Supprimer » ; tableau N° / Compte / Type / Classe / État (en vert : en-têtes et totaux, gris :
    inactifs). Les changements passent dans Sage (robot_comptes, l'application ouvre Sage elle-même)."""
    from .. import plan_comptable as pc
    from .consultations import Section, tableau_section
    from . import taches

    action_nom = "Modifier le plan comptable"
    q = ctx.req.query
    texte = (q.get("texte") or ctx.req.champ("texte")).strip()
    choisi = ctx.req.champ("numero") or q.get("numero", "")
    op = ctx.req.champ("op") or q.get("op", "")
    message = ""
    try:
        comptes = sorted(pc.comptes_connus(ctx.racine, ctx.config, forcer=bool(q.get("actualiser"))).values(),
                         key=lambda c: int(c.numero))
    except (Exception, SystemExit) as erreur:  # noqa: BLE001
        ctx.app.noter(f"Plan comptable : {erreur!r}")
        comptes = []
    if not comptes:
        ctx.absents.add("Sage")
    action = ctx.req.champ("action") if ctx.req.methode == "POST" else ""
    if action in ("Créer dans Sage", "Enregistrer dans Sage", "Supprimer de Sage"):
        from ..robot_comptes import DemandeCompte, appliquer

        try:
            if not action_permise(ctx, action_nom):
                raise ValueError(f"Votre profil n'a pas le droit « {action_nom} ».")
            if action == "Créer dans Sage":
                numero, nom = ctx.req.champ("nouveau").strip(), " ".join(ctx.req.champ("nom").split())
                if not numero.isdigit() or not nom:
                    raise ValueError("N° (chiffres) et description obligatoires.")
                if any(c.numero == numero for c in comptes):
                    raise ValueError(f"Le compte {numero} existe déjà.")
                demandes = [DemandeCompte("creer", numero, nom, "L" if ctx.req.champ("type") == "L" else "R")]
            else:
                c = next((x for x in comptes if x.numero == choisi), None)
                if c is None:
                    raise ValueError("Choisissez un compte dans la liste.")
                if action == "Supprimer de Sage":
                    if not action_permise(ctx, "Supprimer"):
                        raise ValueError("Votre profil n'a pas le droit « Supprimer ».")
                    demandes = [DemandeCompte("supprimer", c.numero)]
                else:
                    nom = " ".join(ctx.req.champ("nom").split())
                    inactif = bool(ctx.req.champ("inactif"))
                    demande = DemandeCompte("modifier", c.numero, nom if nom and nom != c.nom else "",
                                            inactif=inactif if inactif != c.inactif else None)
                    if not demande.nom and demande.inactif is None:
                        raise ValueError("Rien n'a changé.")
                    demandes = [demande]

            def travail(journal):
                resultats = appliquer(ctx.racine, ctx.config, demandes)
                pc.comptes_connus(ctx.racine, ctx.config, forcer=True)
                return [f"{r['numero']} : " + ("fait" if r["fait"] else "✘ " + " ; ".join(r["messages"]))
                        for r in resultats]

            return taches.lancer(ctx, f"Plan comptable : {demandes[0].numero}", travail, "/plan-comptable", sage=True)
        except ValueError as erreur:
            message = _message(erreur=str(erreur))
    mot = texte.casefold()
    visibles = [c for c in comptes if not mot or mot in f"{c.numero} {c.nom}".casefold()]
    lignes = [[f"<input type='radio' name='numero' value='{e(c.numero)}'{' checked' if c.numero == choisi else ''}>",
               e(c.numero), e(c.nom), e(pc.TYPES.get(c.type, c.type)), e(c.classe), "Inactif" if c.inactif else "Actif"]
              for c in visibles]
    classes = ["total" if c.type not in pc.DETAIL else ("termine" if c.inactif else "") for c in visibles]
    bas = ""
    c = next((x for x in comptes if x.numero == choisi), None)
    if op == "ajouter":
        bas = (f"<form method='post' class='carte'>{csrf(ctx)}<h2>Nouveau compte</h2><div class='ligne'><div><label>N° "
               "de compte *</label><input name='nouveau' size='10'></div><div class='large'><label>Description *"
               "</label><input name='nom' size='36'></div><div><label>Type</label><select name='type'><option "
               "value='R'>Compte de groupe</option><option value='L'>Compte de sous-groupe</option></select></div>"
               "<button name='action' value='Créer dans Sage'>✔ Créer dans Sage</button></div><p class='note'>Le n° "
               "doit tomber dans la bonne section de Sage (ex. 5xxx entre l'en-tête et le total des charges).</p>"
               "</form>")
    elif op in ("modifier", "supprimer"):
        if c is None:
            bas = "<p class='erreur-texte'>Choisissez un compte dans la liste.</p>"
        elif op == "modifier":
            bas = (f"<form method='post' class='carte'>{csrf(ctx)}<input type='hidden' name='numero' "
                   f"value='{e(c.numero)}'><h2>Compte {e(c.numero)}</h2><div class='ligne'><div class='large'><label>"
                   f"Description du compte</label><input name='nom' value='{e(c.nom)}' size='40'></div><label "
                   f"class='case'><input type='checkbox' name='inactif' value='1'{' checked' if c.inactif else ''}> "
                   "Compte inactif</label><button name='action' value='Enregistrer dans Sage'>✔ Enregistrer dans Sage"
                   "</button></div></form>")
        else:
            bas = (f"<form method='post' class='carte'>{csrf(ctx)}<input type='hidden' name='numero' "
                   f"value='{e(c.numero)}'><p>Supprimer le compte {e(c.numero)} ({e(c.nom)}) de Sage ? Sage refuse un "
                   "compte qui a des écritures ou un solde.</p><button class='danger' name='action' value='Supprimer de "
                   "Sage'>🗑 Supprimer de Sage</button></form>")
    corps = (message + f"<form method='post'>{csrf(ctx)}<div class='barre-onglet'><div><label>Rechercher :</label>"
             f"<input name='texte' value='{e(texte)}' size='26'></div><button class='second' name='op' value=''>🔍"
             "</button><a class='ouvrir' href='/plan-comptable?actualiser=1'>🔄 Actualiser</a><button name='op' "
             "value='ajouter'>➕ Ajouter</button><button class='second' name='op' value='modifier'>✎ Modifier</button>"
             "<button class='danger' name='op' value='supprimer'>🗑 Supprimer</button></div>"
             f"<p class='note'>{len(visibles)} compte(s). En vert : en-têtes et totaux (aucune écriture). Ajouter, "
             "modifier ou supprimer : l'application ouvre Sage elle-même (Sage fermé sur le serveur).</p>"
             + tableau_section(Section("Plan comptable", ["", "N°", "Compte", "Type", "Classe", "État"], lignes,
                                       classes=classes, html=set(range(6))), limite=5000)
             + "</form>" + bas)
    return Reponse(corps=page(ctx, "Plan comptable", corps))


# --------------------------------------------------------------------------------------------- budget
def budget(ctx: Contexte) -> Reponse:
    """Comme l'onglet « Budget et écarts » de fenetre_comptabilite : Mois, montant de chaque poste, « ✔ Enregistrer le
    budget », « Croissance (%) » + « 💡 Proposer d'après l'an dernier », « 🔍 Comparer au réel » (réel lu dans Sage :
    produits 4xxx, CMV 50xx, autres charges 51xx-59xx)."""
    from .. import comptabilite as cp
    from ..budget import ENTETES_BUDGET, POSTES, Budget, ecarts, proposer, reel
    from ..fenetre_comptabilite import _mois_proposes
    from .consultations import Section, lire_ou_vide, tableau_section
    from .pages_rapports_web import onglets

    mois_choix = _mois_proposes()
    mois_texte = ctx.req.champ("mois") or ctx.req.query.get("mois") or mois_choix[1]
    try:
        annee, mois = (int(x) for x in mois_texte.split("-"))
    except ValueError:
        annee, mois = (int(x) for x in mois_choix[1].split("-"))
        mois_texte = mois_choix[1]
    registre = Budget(ctx.racine)
    valeurs = {x: str(v).replace(".", ",") if v else "" for x, v in registre.mois(annee, mois).items()}
    croissance = ctx.req.champ("croissance") or "5"
    action = ctx.req.champ("action") if ctx.req.methode == "POST" else ""
    etat = "Réel lu dans Sage (produits 4xxx, CMV 50xx, autres charges 51xx-59xx)."
    resultat = ("<h2 class='titre-zone'>Budget et écarts</h2><div class='defile'><table><tr><td class='vide'>"
                "</td></tr></table></div>")  # zone vide avant « Comparer au réel », comme Windows
    if action == "Enregistrer le budget":
        if not action_permise(ctx, "Enregistrer le budget"):
            etat = "✘ Votre profil n'a pas le droit « Enregistrer le budget »."
        else:
            try:
                nouveaux = {x: Decimal(ctx.req.champ(f"poste{k}").replace(" ", "").replace(",", ".") or 0)
                            for k, x in enumerate(POSTES)}
                with ctx.app.ecriture:
                    Budget(ctx.racine).definir(annee, mois, nouveaux)
                valeurs = {x: str(v).replace(".", ",") if v else "" for x, v in nouveaux.items()}
                etat = f"✔ Budget de {mois_texte} enregistré."
            except InvalidOperation:
                etat = "✘ Montants en chiffres."
    elif action == "Proposer d'après l'an dernier":
        try:
            taux = Decimal(croissance.replace(",", "."))
        except InvalidOperation:
            taux = Decimal(0)
        lignes = lire_ou_vide(ctx, lambda b: cp.etat_resultats(b, annee, mois))
        valeurs = {x: str(v).replace(".", ",") for x, v in proposer(reel(lignes, 3), taux).items()}
        etat = f"Proposé d'après {annee - 1}-{mois:02d} : vérifiez puis « Enregistrer le budget »."
    if action == "Comparer au réel" or ctx.req.query.get("comparer"):
        reels = lire_ou_vide(ctx, lambda b: [reel(cp.etat_resultats(b, annee, m)) for m in range(1, mois + 1)])
        budget_ = Budget(ctx.racine)
        cumul_r = {x: sum((r[x] for r in reels), Decimal(0)) for x in POSTES}
        cumul_b = {x: sum((budget_.mois(annee, m)[x] for m in range(1, mois + 1)), Decimal(0)) for x in POSTES}
        resultat = tableau_section(Section(f"Budget et écarts de {mois_texte}", ENTETES_BUDGET,
                                           ecarts(reels[-1] if reels else {x: Decimal(0) for x in POSTES},
                                                  budget_.mois(annee, mois), cumul_r, cumul_b),
                                           "Écart = réel − budget ; depuis janvier = cumul de l'année."))
    options = "".join(f"<option{' selected' if x == mois_texte else ''}>{x}</option>" for x in mois_choix)
    postes = "".join(f"<div><label>{e(x)}</label><input name='poste{k}' value='{e(valeurs.get(x, ''))}' size='10'>"
                     "</div>" for k, x in enumerate(POSTES))
    corps = (onglets("Budget et écarts", ctx) + "<div class='onglet-corps'>"
             + f"<form method='post'>{csrf(ctx)}<div class='barre-onglet'><div><label>Mois</label><select name='mois'>"
               f"{options}</select></div>{postes}<button class='second' name='action' value='Enregistrer le budget'>✔ "
               "Enregistrer le budget</button><div><label>Croissance (%)</label><input name='croissance' "
               f"value='{e(croissance)}' size='5'></div><button class='second' name='action' value=\"Proposer d'après "
               "l'an dernier\">💡 Proposer d'après l'an dernier</button><button name='action' value='Comparer au "
               "réel'>🔍 Comparer au réel</button></div></form>"
             + f"<p class='{'erreur-texte' if etat.startswith('✘') else 'note'}'>{e(etat)}</p>" + resultat + "</div>")
    return Reponse(corps=page(ctx, "Comptabilité", corps))


FONCTIONS = [
    Fonction("/pertes", "Pertes et démarque", "correspondance", pertes, "🗑", "Stock", menu=False),
    Fonction("/promotions", "Promotions", "correspondance", promotions, "🏷", "Articles", menu=False),
    Fonction("/etiquettes", "Étiquettes de prix", "correspondance", etiquettes, "🏷", "Articles", menu=False),
    Fonction("/prix-marges", "Prix et marges", "correspondance", prix_marges, "💹", "Articles", menu=False),
    Fonction("/couts-clover", "Coûts Clover depuis Sage", "correspondance", couts_clover, "💲", "Articles", menu=False),
    Fonction("/comptes-categories", "Comptes Sage par catégorie", "correspondance", comptes_categories, "🧾",
             "Comptabilité", menu=False),
    Fonction("/plan-comptable", "Plan comptable", "rapprochement", plan_comptable, "📒", "Comptabilité", menu=False),
    Fonction("/budget", "Budget et écarts", "rapprochement", budget, "📐", "Comptabilité", menu=False),
]
WEB = {"Pertes et démarque": "/pertes", "Promotions": "/promotions", "Étiquettes de prix": "/etiquettes",
       "Prix et marges": "/prix-marges", "Coûts Clover depuis Sage": "/couts-clover",
       "Comptes Sage par catégorie": "/comptes-categories", "Plan comptable": "/plan-comptable",
       "Budget et écarts": "/budget"}
