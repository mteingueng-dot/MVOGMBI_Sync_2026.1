"""Statistiques Clover de l'application web, identiques à l'onglet « Statistiques Clover » de la page Rapports
(page_rapports.PageRapports) : barre de période (PERIODES, période personnalisée), filtres globaux (Article, Client,
Employé, Catégorie, Mode de paiement), menu des états à gauche (NAVIGATION, une section ouverte), accueil (8 cartes
avec variation, évolution des ventes, montant perçu, catégories, meilleurs articles), aperçu des ventes (4 graphiques),
aperçu financier (KPI), chaque état avec son graphique (GRAPHIQUES_ETATS, TITRES_GRAPHIQUES) et son tableau,
« Détail par jour », liste d'articles, évolution par année, prévisions, péremption, rapports de gestion.
Mêmes fonctions de calcul (statistiques_clover, previsions, peremption, rapports_gestion) ; graphiques en SVG
(graphiques_svg, traduction de graphiques.py).
"""

from __future__ import annotations

import time
from datetime import date, datetime, timedelta
from decimal import Decimal
from urllib.parse import urlencode

from ..page_rapports import (A_COMMANDER_TEXTE, FILTRES_PEREMPTION, GRAPHIQUES_ETATS, HORIZONS, NAVIGATION, PREVISIONS,
                             TITRES_GRAPHIQUES)
from .consultations import Section, tableau_section
from .graphiques_svg import BLEU, BLEU_PALE, PALETTE, Graphique
from .pages import Contexte, Fonction, argent, page
from .serveur import Reponse, echapper as e

INDICATEURS = (("Ventes brutes", "Ventes brutes (articles)", True),
               ("Ventes nettes", "Ventes nettes (articles)", True), ("Commandes", "Commandes payées", False),
               ("Panier moyen", "Panier moyen", True), ("Montant perçu", "Montant encaissé (paiements)", True),
               ("Taxes", "Taxes encaissées", True), ("Rabais", "Rabais", True),
               ("Remboursements", "Remboursements (articles)", True))
FILTRES = ("Article", "Client", "Employé", "Catégorie", "Mode de paiement")
DUREE = 300           # s : périodes terminées gardées
DUREE_JOUR = 60       # s : journée en cours relue chaque minute (comme l'application Windows)


def montant(v) -> str:
    return argent(v)


# --------------------------------------------------------------------------------------------- données
def _garder(ctx: Contexte, cle, duree, fonction):
    gardee = ctx.app.memoire.get(cle)
    if gardee and time.time() - gardee[0] < duree:
        return gardee[1]
    valeur = fonction()
    ctx.app.memoire[cle] = (time.time(), valeur)
    return valeur


def _points(ctx: Contexte) -> list:
    """Points de vente permis ; filtre « Point de vente » (Tout = tous, comme la liste à choix multiples de Windows)."""
    from ..points_vente import permis

    points = permis(ctx.config, ctx.reg.points_vente_permis(ctx.u))
    choisi = ctx.req.query.get("Point de vente", "")
    return [p for p in points if p.libelle == choisi] or points if choisi else points


def _brut(ctx: Contexte, du: date, au: date, nom_periode: str) -> dict:
    """Comme PageRapports.calculer_statistiques : période et comparaison lues (tous les points de vente permis),
    coûts Sage du jour, statistiques complètes (sans filtre) calculées une fois."""
    from .. import statistiques_clover as sc
    from ..points_vente import cache_clover, client

    def lire():
        du2, au2, libelle = sc.comparaison(du, au, nom_periode)
        parts, avant = [], []
        for pv in _points(ctx) or [None]:
            c, cache = client(ctx.racine, pv), cache_clover(ctx.racine, pv)
            parts.append(sc.lire(c, du, au, cache))
            avant.append(sc.lire(c, du2, au2, cache))
        donnees, autres = sc.fusionner(parts), sc.fusionner(avant)
        try:
            from ..couts_sage import charger, cout_par_clover

            couts = cout_par_clover(ctx.racine, charger(ctx.racine, ctx.config, ouvrir=False, secours=True))
        except (Exception, SystemExit):  # noqa: BLE001 — Sage illisible : pas de bénéfices
            couts = {}
        return {"donnees": donnees, "autres": autres, "couts": couts, "du": du, "au": au, "du2": du2, "au2": au2,
                "libelle": libelle, "completes": sc.statistiques(donnees, couts)}

    cle = ("stats_brut", du, au, nom_periode, ctx.req.query.get("Point de vente", ""))
    return _garder(ctx, cle, DUREE_JOUR if au >= date.today() else DUREE, lire)


def _calculer(b: dict, f: dict) -> dict:
    """Comme PageRapports._calculer : période et comparaison avec les filtres globaux."""
    from .. import statistiques_clover as sc

    cle = tuple(sorted(f.items()))
    memoire = b.setdefault("_par_filtres", {})
    if cle not in memoire:
        donnees, autres = sc.filtrer(b["donnees"], f), sc.filtrer(b["autres"], f)
        memoire[cle] = {"vues": sc.statistiques(donnees, b["couts"]) if f else b["completes"],
                        "avant": sc.resume_rapide(autres), "libelle": b["libelle"],
                        "series": sc.series(donnees, b["du"], b["au"]), "series_avant": sc.series(autres, b["du2"],
                                                                                                   b["au2"]),
                        "moyens": sc.montants_par_moyen(donnees), "du": b["du"], "au": b["au"], "du2": b["du2"],
                        "filtres": f}
    return memoire[cle]


# --------------------------------------------------------------------------------------------- rendu
def _graph(g: Graphique) -> str:
    return f"<div class='carte-graph'>{g.svg()}</div>"


def _cartes(r: dict) -> str:
    actuel, avant = dict(r["vues"]["Résumé"][1]), dict(r["avant"]["Résumé"][1])
    html = ""
    for titre, cle, est_argent in INDICATEURS:
        v, w = actuel.get(cle, 0), avant.get(cle, 0)
        if titre in ("Rabais", "Remboursements"):
            v, w = abs(v), abs(w)
        valeur = montant(v) if est_argent else str(v)
        ecart, classe = "—", "neutre"
        if w and v is not None:
            variation = (Decimal(str(v)) - Decimal(str(w))) * 100 / abs(Decimal(str(w)))
            hausse = variation >= 0
            bon = hausse if titre not in ("Rabais", "Remboursements") else not hausse
            ecart = ("↑ " if hausse else "↓ ") + f"{abs(variation):.1f} %".replace(".", ",")
            classe = "bon" if bon else "mauvais"
        html += (f"<div class='carte-stat'><div class='t'>{e(titre)}</div><div class='l'><span class='v'>{e(valeur)}"
                 f"</span><span class='ecart {classe}'>{e(ecart)}</span></div></div>")
    return f"<div class='cartes-stats'>{html}</div>"


def _accueil(r: dict) -> str:
    etiquettes, valeurs = r["series"]
    _, valeurs_avant = r["series_avant"]
    valeurs_avant = (valeurs_avant + [0] * len(valeurs))[:len(valeurs)]
    nom = ("Aujourd'hui" if r["du"] == r["au"] == date.today() else
           (str(r["du"]) if r["du"] == r["au"] else "Période choisie"))
    g = Graphique(560, 170, "Ventes nettes par heure" if r["du"] == r["au"] else "Évolution des ventes nettes")
    if r["du"] == r["au"]:
        g.barres(etiquettes, [(nom, valeurs, BLEU), (r["libelle"].capitalize(), valeurs_avant, BLEU_PALE)],
                 "Aucune vente")
    else:
        legende_avant = r["libelle"].capitalize()
        if r["du2"].year != r["du"].year and r["du"].year == r["au"].year:
            nom, legende_avant = str(r["du"].year), str(r["du2"].year)
        g.courbes(etiquettes, [(nom, valeurs, BLEU, False), (legende_avant, valeurs_avant, BLEU_PALE, True)],
                  "Aucune vente")
    moyens = Graphique(260, 200, "Montant perçu").anneau([(k, v) for k, v in r["moyens"]], "Aucun paiement",
                                                         format_valeur=montant)
    categories = Graphique(190, 190, "Ventes par catégorie").anneau(
        [(l[0], l[2]) for l in r["vues"]["Par catégorie"][1]], "Aucune vente", format_valeur=montant)
    articles = Graphique(190, 190, "Meilleurs articles").classement(
        [(l[0], l[6]) for l in r["vues"]["Par article"][1][:8]], vide="Aucune vente", format_valeur=montant)
    return (_cartes(r) + _graph(g) + "<div class='grille3'>" + _graph(moyens) + _graph(categories) + _graph(articles)
            + "</div>")


def _apercu(r: dict) -> str:
    v = r["vues"]
    resume = dict(v["Résumé"][1])
    brutes, nettes = resume["Ventes brutes (articles)"], resume["Ventes nettes (articles)"]
    texte = (f"Ventes brutes {montant(brutes)}   •   rabais {montant(resume['Rabais'])}   •   remboursements "
             f"{montant(resume['Remboursements (articles)'])}   •   ventes nettes {montant(nettes)}   •   "
             f"{resume['Commandes payées']} commande(s), panier moyen {montant(resume['Panier moyen'])}")
    lignes = v["Rapport des ventes"][1]
    etiquettes = [l[0][8:10] + "/" + l[0][5:7] if len(l[0]) == 10 else l[0] for l in lignes]
    evolution = Graphique(550, 200, "Ventes brutes et nettes")
    if len(lignes) > 1 and len(lignes[0][0]) == 10:
        evolution.courbes(etiquettes, [("Ventes brutes", [l[3] for l in lignes], BLEU_PALE, False),
                                       ("Ventes nettes", [l[6] for l in lignes], BLEU, False)], "Aucune vente")
    else:
        evolution.barres(etiquettes, [("Ventes brutes", [l[3] for l in lignes], BLEU_PALE),
                                      ("Ventes nettes", [l[6] for l in lignes], BLEU)], "Aucune vente")
    composition = Graphique(550, 200, "Des ventes brutes aux ventes nettes").anneau(
        [("Ventes nettes", nettes), ("Rabais", abs(resume["Rabais"])),
         ("Remboursements", abs(resume["Remboursements (articles)"]))], "Aucune vente", format_valeur=montant)
    semaine = v["Par jour de la semaine"][1]
    g_semaine = Graphique(550, 200, "Ventes par jour de la semaine").barres(
        [l[0][:3] for l in semaine], [("Ventes nettes", [l[2] for l in semaine], BLEU)], "Aucune vente")
    heures = v["Par heure"][1]
    g_heure = Graphique(550, 200, "Ventes par heure").barres(
        [l[0].replace(" h", "h") for l in heures], [("Ventes nettes", [l[2] for l in heures], BLEU)], "Aucune vente")
    return (f"<h2 class='titre-etat'>Aperçu des ventes</h2><p>{e(texte)}</p><div class='grille2'>" + _graph(evolution)
            + _graph(composition) + _graph(g_semaine) + _graph(g_heure) + "</div>")


def _kpi(r: dict) -> str:
    from ..statistiques_clover import kpis

    html = ""
    for titre, genre, valeur in kpis(r["vues"], r["moyens"]):
        texte = (montant(valeur) if genre == "$" else f"{valeur} %".replace(".", ",") if genre == "%"
                 else str(valeur).replace(".", ",") if genre == "n" else str(valeur))
        classe = " benefice" if titre.startswith("Bénéfice") else (" texte" if genre == "t" else "")
        html += f"<div class='kpi'><div class='t'>{e(titre)}</div><div class='v{classe}'>{e(texte)}</div></div>"
    return f"<div class='kpis'>{html}</div>"


def _graphique_etat(nom: str, lignes: list[list], vues: dict, extra: dict) -> str:
    """Comme PageRapports._graphique_etat."""
    if nom == "prev_ventes" and extra.get("historique") is not None:
        historique = extra["historique"]
        jours = sorted(historique)[-28:]
        etiquettes = [f"{j.day:02d}/{j.month:02d}" for j in jours] + [l[0][8:10] + "/" + l[0][5:7] for l in lignes]
        reels = [historique[j] for j in jours] + [None] * len(lignes)
        prevus = [None] * (len(jours) - 1) + [historique[jours[-1]] if jours else None] + [l[2] for l in lignes]
        return _graph(Graphique(1100, 170, "Ventes nettes : 28 derniers jours et prévision").courbes(
            etiquettes, [("Ventes réelles", reels, BLEU, False), ("Prévision", prevus, "#f6b81a", True)],
            "Aucune vente"))
    if nom == "evolution_annees" and extra.get("series_annees"):
        etiquettes, series = extra["series_annees"]
        return _graph(Graphique(1100, 170, "Ventes nettes par jour, année par année").courbes(
            etiquettes, [(str(a), v, PALETTE[k % len(PALETTE)], k > 0) for k, (a, v) in enumerate(series.items())],
            "Aucune vente"))
    if nom == "prev_commande":
        compte: dict[str, int] = {}
        for l in lignes:
            compte[l[5]] = compte.get(l[5], 0) + 1
        return _graph(Graphique(1100, 170, f"Articles vendus en {extra.get('horizon', 14)} jours").anneau(
            [(k, Decimal(v)) for k, v in compte.items()], "Aucune vente", format_valeur=lambda v: f"{v:.0f}"))
    if nom == "Rapport des ventes" and lignes:
        etiquettes = [l[0][8:10] + "/" + l[0][5:7] if len(l[0]) == 10 else l[0] for l in lignes]
        return _graph(Graphique(1100, 170, "Ventes brutes et nettes").barres(
            etiquettes, [("Ventes brutes", [l[3] for l in lignes], BLEU_PALE),
                         ("Ventes nettes", [l[6] for l in lignes], BLEU)], "Aucune vente"))
    if nom == "Jour × heure" and lignes:
        entetes = vues[nom][0]
        return _graph(Graphique(1100, 240, TITRES_GRAPHIQUES[nom]).chaleur(
            [l[0][:3] for l in lignes], [x.replace(" h", "h") for x in entetes[1:-1]], [l[1:-1] for l in lignes],
            "Aucune vente"))
    genre = GRAPHIQUES_ETATS.get(nom)
    if not genre or not lignes:
        return ""
    type_, i_nom, i_val = genre
    valeurs = [(str(l[i_nom]), abs(l[i_val]) if isinstance(l[i_val], Decimal) else Decimal(l[i_val] or 0))
               for l in lignes]
    g = Graphique(1100, 170, TITRES_GRAPHIQUES.get(nom, "Les 8 premiers"))
    if type_ == "courbe":
        g.courbes([v[0][8:10] + "/" + v[0][5:7] for v in valeurs], [("Ventes nettes", [v[1] for v in valeurs], BLEU,
                                                                      False)], "Aucune vente")
    elif type_ == "barres":
        g.barres([v[0] for v in valeurs], [("Ventes nettes", [v[1] for v in valeurs], BLEU)], "Aucune vente")
    elif type_ == "anneau":
        g.anneau(valeurs, "Aucune vente", format_valeur=montant)
    else:
        g.classement(sorted(valeurs, key=lambda v: -v[1])[:8], vide="Aucune vente", format_valeur=montant,
                     couleur=BLEU_PALE if nom == "Rabais" else BLEU)
    return _graph(g)


# --------------------------------------------------------------------------------------------- états particuliers
def _liste_articles(ctx: Contexte) -> tuple[list[str], list[list], str]:
    from ..couts_sage import charger, correspondance
    from ..points_vente import client
    from ..statistiques_clover import SEUIL_CUMP_DOUTEUX

    def lire():
        articles = [a for a in client(ctx.racine)._pages("items", {"expand": "categories,itemStock"})
                    if not a.get("deleted")]
        try:
            couts = charger(ctx.racine, ctx.config, ouvrir=False, secours=True)
        except (Exception, SystemExit):  # noqa: BLE001
            couts = {}
        return articles, couts, correspondance(ctx.racine)

    articles, couts, lien = _garder(ctx, ("liste_articles",), 600, lire)
    types = {"FIXED": "Fixe", "VARIABLE": "Variable", "PER_UNIT": "Au poids / à l'unité"}
    lignes = []
    for a in sorted(articles, key=lambda x: (x.get("name") or "").casefold()):
        prix = Decimal(int(a.get("price") or 0)) / 100
        numero = lien.get(a["id"], "")
        cout = couts.get(numero)
        cump = cout.cump if cout else None
        stock = (a.get("itemStock") or {}).get("quantity")
        categories = (a.get("categories") or {}).get("elements") or []
        lignes.append([(a.get("name") or "").strip(), categories[0].get("name", "") if categories else "",
                       (a.get("code") or "").strip(), (a.get("sku") or "").strip(), prix,
                       types.get(a.get("priceType"), a.get("priceType") or "") + (f" ({a['unitName']})" if a.get(
                           "unitName") else ""), Decimal(int(a["cost"])) / 100 if a.get("cost") else None,
                       None if stock is None else Decimal(str(stock)).normalize(), numero, cump,
                       ((prix - cump) * 100 / prix).quantize(Decimal("0.1")) if cump is not None and prix else None,
                       cout.quantite.normalize() if cout else None, cout.valeur if cout else None,
                       "Oui" if a.get("defaultTaxRates") else "Non", "Caché" if a.get("hidden") else "Visible",
                       "CUMP douteux (à vérifier dans Sage)" if cump and prix and cump > SEUIL_CUMP_DOUTEUX * prix
                       else ""])
    relies = sum(1 for l in lignes if l[8])
    note = (f"{len(lignes)} article(s) Clover, dont {relies} relié(s) à un article Sage "
            f"({sum(1 for l in lignes if l[9] is not None)} avec un CUMP). Marge sur prix = (prix de vente − CUMP Sage) "
            "/ prix de vente.")
    return (["Article", "Catégorie", "Code-barres", "SKU", "Prix de vente", "Type de prix", "Coût Clover",
             "Stock Clover", "N° Sage", "CUMP Sage", "Marge sur prix %", "Stock Sage", "Valeur du stock Sage",
             "Taxable", "Affichage", "Contrôle"], lignes, note)


def _annees(ctx: Contexte, b: dict, f: dict) -> tuple[list[str], list[list], str, tuple]:
    from .. import statistiques_clover as sc
    from ..points_vente import client

    def lire():
        annees = {b["du"].year: b["donnees"]}
        c = client(ctx.racine)
        for k in (1, 2):
            try:
                du, au = b["du"].replace(year=b["du"].year - k), b["au"].replace(year=b["au"].year - k)
            except ValueError:
                du, au = b["du"].replace(year=b["du"].year - k, day=28), b["au"].replace(year=b["au"].year - k, day=28)
            annees[b["du"].year - k] = sc.lire(c, du, au, ctx.racine / "donnees" / "cache_clover")
        return annees

    donnees = _garder(ctx, ("annees", b["du"], b["au"]), DUREE, lire)
    etiquettes, series = sc.evolution_par_annee({a: sc.filtrer(d, f) for a, d in donnees.items()}, b["du"], b["au"])
    annees = list(series)
    lignes = []
    for i, jour in enumerate(etiquettes):
        valeurs = [series[a][i] for a in annees]
        ecart = (None if len(valeurs) < 2 or not valeurs[1] or valeurs[0] is None else
                 ((valeurs[0] - valeurs[1]) * 100 / valeurs[1]).quantize(Decimal("0.1")))
        lignes.append([jour] + valeurs + [ecart])
    totaux = {a: sum((v or 0 for v in series[a]), Decimal(0)) for a in annees}
    return (["Date"] + [str(a) for a in annees] + [f"% {annees[0]} / {annees[1]}" if len(annees) > 1 else "%"], lignes,
            "   •   ".join(f"{a} : {montant(v)}" for a, v in totaux.items()), (etiquettes, series))


def _previsions(ctx: Contexte, nom: str, horizon: int) -> tuple[list[str], list[list], str, dict]:
    from .. import previsions as pr
    from ..points_vente import client
    from ..statistiques_clover import lire

    jours = max(56, horizon)

    def lire_donnees():
        c = client(ctx.racine)
        a = date.today()
        donnees = lire(c, a - timedelta(days=jours), a - timedelta(days=1), ctx.racine / "donnees" / "cache_clover")
        return {"donnees": donnees, "articles": list(c._pages("items", {"expand": "categories,itemStock"})),
                "aujourdhui": a, "historique": pr.ventes_par_jour(donnees)}

    r = _garder(ctx, ("previsions", jours, date.today()), 3600, lire_donnees)
    a, d = r["aujourdhui"], r["donnees"]
    if nom == "prev_ventes":
        ventes = pr.prevoir_ventes(r["historique"], a, horizon)
        return (["Date", "Jour", "Prévision", "Même jour la semaine dernière", "Moyenne des 4 mêmes jours"], ventes,
                f"Total prévu sur {horizon} jours : {montant(sum((l[2] for l in ventes), Decimal(0)))} (même jour de la "
                "semaine sur 4 semaines, tendance des 4 dernières semaines).", {"historique": r["historique"]})
    if nom == "prev_commande":
        lignes = pr.articles_a_commander(pr.ventes_par_article(d, a - timedelta(days=horizon), a - timedelta(days=1)),
                                         r["articles"])
        n = sum(1 for l in lignes if l[5] == A_COMMANDER_TEXTE)
        return (["Article", "Catégorie", f"Vendu {horizon} jours", "Stock", "Stock − vendu", "État",
                 "Quantité suggérée", "Coût estimé", "Dernière vente"], lignes,
                f"{n} article(s) à commander : stock restant − quantité vendue les {horizon} derniers jours ≤ 0 "
                "(articles vendus dont Clover suit le stock).", {"horizon": horizon})
    achats = pr.prevoir_achats(pr.ventes_par_article(d, a - timedelta(days=28), a - timedelta(days=1)), r["articles"],
                               horizon)
    return (["Article", "Catégorie", "Vendu 28 jours", f"Besoin {horizon} jours", "Stock", "À acheter",
             "Coût unitaire", "Montant estimé"], achats,
            f"Achats estimés sur {horizon} jours : {montant(sum((l[7] or Decimal(0) for l in achats), Decimal(0)))} "
            "(rythme de vente des 28 derniers jours, stock et coût des articles dans Clover).", {})


def _peremption(ctx: Contexte, q: dict) -> str:
    from ..peremption import NEUTRE, ORANGE, PERIME, ROUGE, articles_peremption
    from ..points_vente import client

    articles = _garder(ctx, ("peremption",), 600, lambda: list(client(ctx.racine)._pages(
        "items", {"expand": "categories,itemStock"})))
    resultat = articles_peremption(articles)
    filtre = q.get("filtre_peremption") or FILTRES_PEREMPTION[0]
    garder = {"Bientôt périmés (3 mois ou moins)": (PERIME, ROUGE, ORANGE), "Périmés": (PERIME,),
              "Un mois ou moins": (PERIME, ROUGE), "De 1 à 3 mois": (ORANGE,), "Plus de 3 mois": (NEUTRE,),
              "Tous": (PERIME, ROUGE, ORANGE, NEUTRE)}.get(filtre, (PERIME, ROUGE, ORANGE))
    texte = (q.get("recherche") or "").strip().casefold()
    lignes = [p for p in resultat if p.etat in garder and (not q.get("en_stock") or (p.stock or 0) > 0)
              and (not texte or texte in (p.nom + " " + p.categorie).casefold())]
    couleurs = {PERIME: "rouge", ROUGE: "rouge", ORANGE: "orange", NEUTRE: "neutre"}
    rangees = "".join(
        f"<tr class='pe-{couleurs.get(p.etat, 'neutre')}'><td>{e(p.nom)}</td><td>{e(p.categorie)}</td><td>"
        f"{p.peremption.isoformat()}</td><td class='n'>{p.jours}</td><td>{e(p.etat)}</td><td class='n'>"
        f"{'' if p.stock is None else e(f'{p.stock:f}'.replace('.', ','))}</td><td class='n'>{argent(p.prix)}</td>"
        f"<td>{e(p.sku)}</td></tr>" for p in lignes)
    options = "".join(f"<option{' selected' if x == filtre else ''}>{e(x)}</option>" for x in FILTRES_PEREMPTION)
    cache = "".join(f"<input type='hidden' name='{k}' value='{e(v)}'>" for k, v in q.items()
                    if k in ("periode", "du", "au", "vue", "section"))
    return (f"<h2 class='titre-etat'>Péremption</h2><form class='ligne' method='get'>{cache}<div><label>Afficher"
            f"</label><select name='filtre_peremption'>{options}</select></div><div><label>Rechercher</label><input "
            f"name='recherche' value='{e(q.get('recherche', ''))}'></div><div><label><input type='checkbox' "
            f"name='en_stock' value='1'{' checked' if q.get('en_stock') else ''}> Seulement les articles en stock</label>"
            "</div><button class='second'>Afficher</button></form><p class='legende-pe'><span class='pe-rouge'>   </span>"
            " Un mois ou moins (ou périmé)  <span class='pe-orange'>   </span> De 1 à 3 mois  <span class='pe-neutre'>"
            "   </span> Plus de 3 mois</p><h2>Articles et dates de péremption (champ SKU de Clover)</h2><div "
            "class='defile'><table><tr><th>Article</th><th>Catégorie</th><th>Date de péremption</th><th class='n'>"
            "Jours restants</th><th>État</th><th class='n'>Stock</th><th class='n'>Prix</th><th>SKU</th></tr>"
            f"{rangees}</table></div><p class='note'>{len(lignes)} article(s) sur {len(articles)}.</p>")


def _analyse(b: dict, cle: str, filtres: dict):
    """Analyse décisionnelle (analyses_clover) : comme PageRapports._afficher_analyse, gardée par filtres."""
    from .. import statistiques_clover as sc
    from ..analyses_clover import calculer

    memoire = b.setdefault("_analyses", {})
    cle_m = (cle, tuple(sorted(filtres.items())))
    if cle_m not in memoire:
        donnees, autres = ((sc.filtrer(b["donnees"], filtres), sc.filtrer(b["autres"], filtres)) if filtres
                           else (b["donnees"], b["autres"]))
        memoire[cle_m] = calculer(cle, donnees, autres, b["couts"], b["du"], b["au"], b["du2"], b["au2"])
    return memoire[cle_m]


def _gestion(ctx: Contexte, cle: str, b: dict | None, du: date, au: date, filtres: dict | None = None) -> str:
    from ..analyses_clover import ANALYSES, CLES as CLES_ANALYSES
    from ..rapports_gestion import ETATS, calculer

    libelle = next((l for l, c, *_r in ETATS + ANALYSES if c == cle), cle)
    if cle in CLES_ANALYSES:
        if not b:
            return f"<h2 class='titre-etat'>{e(libelle)}</h2><p class='erreur'>Clover ne répond pas pour l'instant.</p>"
        return _rendu_rapport(libelle, _analyse(b, cle, filtres or {}))
    contexte = {"ventes_par_jour": {}, "donnees": None, "config": ctx.config}
    if ctx.req.query.get("Point de vente", ""):
        contexte["points_vente"] = _points(ctx)  # filtre « Point de vente » = ses dépôts
    if b:
        contexte["donnees"] = b.get("donnees")
        for l in b.get("completes", {}).get("Par jour", ([], []))[1]:
            try:
                contexte["ventes_par_jour"][date.fromisoformat(str(l[0])[:10])] = Decimal(str(l[3]))
            except (ValueError, IndexError, ArithmeticError):
                pass
    return _rendu_rapport(libelle, calculer(cle, ctx.racine, du, au, contexte))


def _rendu_rapport(libelle: str, r) -> str:
    """Rapport de gestion ou analyse : cartes, évolution, répartition, constats, tableau (comme _remplir_gestion)."""
    from ..analyses_clover import etat_carte, niveau_constat

    cartes = ""
    for titre, genre, valeur in r.cartes:  # feu de couleur comme les cartes de Windows
        texte = (montant(valeur) if genre == "$" else f"{valeur} %".replace(".", ",") if genre == "%"
                 else f"{valeur} h".replace(".", ",") if genre == "h"
                 else str(valeur).replace(".", ",") if genre == "n" else str(valeur))
        etat = etat_carte(titre, valeur)
        if titre in ("Variation", "Écart") and etat in ("bon", "alerte"):
            texte = ("▲ " if etat == "bon" else "▼ ") + texte
        classe = "v texte" if genre == "t" else "v benefice grand"
        cartes += (f"<div class='kpi{' etat-' + etat if etat else ''}'><div class='t'>{e(titre)}</div>"
                   f"<div class='{classe}'>{e(texte)}</div></div>")
    lignes_note = (r.note or "").splitlines()
    if any(l[:1] in "✔⚠✖ℹ" for l in lignes_note):  # constats des analyses : un bandeau coloré chacun
        icones = {"alerte": "✖", "attention": "⚠", "bon": "✔", "info": "ℹ"}
        note = "<div class='constats'>" + "".join(
            f"<div class='constat {n}'><span class='i'>{icones[n]}</span>{e(texte)}</div>"
            for n, texte in (niveau_constat(l) for l in lignes_note)) + "</div>"
    else:
        note = f"<p class='note'>{'<br>'.join(e(x) for x in lignes_note)}</p>" if r.note else ""
    vide = "Aucune donnée pour la période"
    couleurs = [BLEU, "#f6b81a", *PALETTE]
    evolution = Graphique(480, 210, r.titre_evolution)
    evolution.unite = r.unite_evolution
    if len(r.etiquettes) <= 1 or r.genre_evolution == "barres":
        evolution.barres(r.etiquettes, [(n, v, couleurs[k]) for k, (n, v) in enumerate(r.series)], vide)
    else:
        evolution.courbes(r.etiquettes, [(n, v, couleurs[k], k > 0) for k, (n, v) in enumerate(r.series)], vide)
    format_ = montant if r.argent_repartition else (lambda v: f"{v:.0f}" if v == int(v) else f"{v:.1f}")
    repartition = Graphique(480, 210, r.titre_repartition)
    if r.genre_repartition == "anneau":
        repartition.anneau(r.repartition, vide, format_valeur=format_)
    else:
        repartition.classement(r.repartition, vide=vide, format_valeur=format_, couleur=BLEU_PALE)
    sup = ""
    for d in getattr(r, "graphiques", []) or []:  # graphiques de plus (analyses décisionnelles), deux par rangée
        sup += _graph(_graphe_sup(d, vide))
    if sup:
        sup = f"<div class='grille2'>{sup}</div>"
    # les chiffres d'abord, puis les constats (comme Windows)
    return (f"<h2 class='titre-etat'>{e(libelle)}</h2>" + f"<div class='kpis ligne-kpi'>{cartes}</div>" + note
            + f"<div class='grille2'>{_graph(evolution)}{_graph(repartition)}"
            "</div>" + sup + tableau_section(Section("Rapport détaillé", r.entetes, r.lignes)))


def _graphe_sup(d: dict, vide: str) -> Graphique:
    """Comme page_rapports.dessiner_graphe : graphique de plus d'une analyse."""
    g = Graphique(480, 210, d["titre"])
    g.unite = unite = d.get("unite", "$")
    format_ = (montant if unite == "$" else (lambda v: f"{v} %".replace(".", ",")) if unite == "%"
               else (lambda v: f"{v:.0f}" if v == int(v) else f"{v:.2f}".replace(".", ",")))
    couleurs = [BLEU, "#f6b81a", *PALETTE]
    elements = [(str(n), v) for n, v in d.get("elements", [])]
    series = d.get("series", [])
    if d["genre"] == "anneau":
        g.anneau(elements, vide, format_valeur=format_)
    elif d["genre"] == "classement":
        g.classement(elements, vide=vide, format_valeur=format_, couleur=BLEU_PALE)
    elif d["genre"] == "courbes" and len(d.get("etiquettes", [])) > 1:
        g.courbes(d["etiquettes"], [(n, v, couleurs[k], k > 0) for k, (n, v) in enumerate(series)], vide)
    else:
        g.barres(d.get("etiquettes", []), [(n, v, couleurs[k]) for k, (n, v) in enumerate(series)], vide)
    return g


# --------------------------------------------------------------------------------------------- page
def _navigation(q: dict, vue: str, section: str, limite: bool) -> str:
    html = "<nav class='nav-stats'>"
    for icone, nom, etats in NAVIGATION:
        if nom == "Gestion" and limite:
            continue
        ouverte = nom == section
        premier = etats[0][1]
        lien = "?" + urlencode({**q, "vue": premier, "section": nom})
        actif_seul = ouverte and len(etats) == 1 and vue == premier
        html += (f"<a class='nav-section{' ouverte' if ouverte and len(etats) > 1 else ''}"
                 f"{' actif' if actif_seul else ''}' href='{e(lien)}'>{icone}&nbsp;&nbsp; {e(nom)}</a>")
        if ouverte and len(etats) > 1:
            for libelle, cle in etats:
                lien = "?" + urlencode({**q, "vue": cle, "section": nom})
                html += f"<a class='nav-etat{' actif' if cle == vue else ''}' href='{e(lien)}'>{e(libelle)}</a>"
    return html + "</nav>"


def statistiques(ctx: Contexte) -> Reponse:
    from .. import statistiques_clover as sc
    from ..analyses_clover import CLES as CLES_ANALYSES
    from ..rapports_gestion import CLES as CLES_GESTION

    q = {k: v for k, v in ctx.req.query.items() if v != ""}
    nom_periode = q.get("periode", "Aujourd'hui")
    if nom_periode == "Personnalisée":
        try:
            du, au = date.fromisoformat(q.get("du", "")), date.fromisoformat(q.get("au", ""))
            if du > au:
                raise ValueError
        except ValueError:
            nom_periode = "Aujourd'hui"
    if nom_periode != "Personnalisée":
        if nom_periode not in sc.PERIODES:
            nom_periode = "Aujourd'hui"
        du, au = sc.periode(nom_periode)
    vue = q.get("vue", "accueil")
    section = q.get("section") or next((n for _i, n, etats in NAVIGATION for _l, c in etats if c == vue), "Accueil")
    filtres = {nom: q[nom] for nom in FILTRES if q.get(nom)}
    limite = not ctx.voit_tous()
    if limite:  # login limité : statistiques verrouillées sur son employé
        moi = ctx.employe()
        filtres["Employé"] = moi.nom if moi else "—"
    # barre de période et filtres (comme la barre de l'onglet Windows)
    periodes = "".join(f"<option{' selected' if p == nom_periode else ''}>{e(p)}</option>"
                       for p in sc.PERIODES + ["Personnalisée"])
    cache = "".join(f"<input type='hidden' name='{k}' value='{e(q[k])}'>" for k in ("vue", "section") if k in q)
    # « Journée en cours : actualiser chaque minute » (cochée par défaut, comme Windows) : rechargement par balise meta
    auto = q.get("auto", "1") == "1"
    pdf = ("" if not ctx.reg.peut_exporter(ctx.u) else
           f"<a class='ouvrir' href='?{e(urlencode({**q, 'pdf': '1'}))}'>📕 PDF de la page</a>")
    barre = (f"<form class='barre-stats' method='get'>{cache}<div class='barre-onglet'><div><label>Période</label><select "
             f"name='periode'>{periodes}</select></div><div><label>Du</label><input type='date' name='du' value='{du}'>"
             f"</div><div><label>Au</label><input type='date' name='au' value='{au}'></div><button name='actualiser' "
             "value='1'>🔄 Actualiser</button><input type='hidden' name='auto' value='0'><label class='case'><input "
             f"type='checkbox' name='auto' value='1'{' checked' if auto else ''}> Journée en cours : actualiser chaque "
             f"minute</label>{pdf}</div><div class='barre-onglet'><strong>Filtrer :</strong>")
    message = ""
    try:
        b = _brut(ctx, du, au, nom_periode)
        r = _calculer(b, filtres)
        completes = b["completes"]
        from ..points_vente import permis as permis_pv

        libelles = [p.libelle for p in permis_pv(ctx.config, ctx.reg.points_vente_permis(ctx.u))]
        pv = q.get("Point de vente", "")
        barre += ("<div><label>Point de vente</label><select name='Point de vente'><option value=''>Tout</option>"
                  + "".join(f"<option{' selected' if x == pv else ''}>{e(x)}</option>" for x in libelles)
                  + "</select></div>")
        for nom, vue_filtre in (("Article", "Par article"), ("Client", "Par client"), ("Employé", "Par employé"),
                                ("Catégorie", "Par catégorie"), ("Mode de paiement", "Par mode de paiement")):
            valeurs = sorted({str(l[0]) for l in completes[vue_filtre][1]} - {"Sans client"}, key=str.casefold)
            fixe = limite and nom == "Employé"
            barre += (f"<div><label>{e(nom)}</label><input name='{e(nom)}' list='f-{e(nom)}' size='14' value='"
                      f"{e(filtres.get(nom, ''))}'{' readonly' if fixe else ''}><datalist id='f-{e(nom)}'>"
                      + "".join(f"<option value='{e(v)}'>" for v in valeurs) + "</datalist></div>")
    except (Exception, SystemExit) as erreur:  # noqa: BLE001 — Clover injoignable
        ctx.app.noter(f"Statistiques : {erreur!r}")
        b, r = None, None
        message = "<p class='erreur'>Clover ne répond pas pour l'instant.</p>"
    effacer = urlencode({k: v for k, v in q.items() if k not in FILTRES and k != "Point de vente"})
    barre += ("<button>✔ Appliquer</button>" + ("" if limite else f"<a class='ouvrir' href='?{e(effacer)}'>✖ Effacer</a>")
              + "</div></form>")
    etat = ""
    if r:
        etat = (f"<p class='note'>Mis à jour à {datetime.now():%H:%M} — variations par rapport à {e(r['libelle'])}."
                + (f"   •   filtres : {e(', '.join(f'{k} = {v}' for k, v in filtres.items()))}" if filtres else "")
                + (" La journée en cours est relue chaque minute (actualisez la page)." if au >= date.today() else "")
                + "</p>")
    contenu = ""
    try:
        if vue in CLES_GESTION and not limite:
            contenu = _gestion(ctx, vue, b, du, au)
        elif vue in CLES_ANALYSES:
            contenu = _gestion(ctx, vue, b, du, au, filtres)
        elif vue == "peremption":
            contenu = _peremption(ctx, q)
        elif r is None:
            contenu = ""
        elif vue == "accueil":
            contenu = _accueil(r)
        elif vue == "apercu":
            contenu = _apercu(r)
        else:
            contenu = _etat(ctx, vue, q, b, r, filtres)
    except (Exception, SystemExit) as erreur:  # noqa: BLE001
        ctx.app.noter(f"Statistiques ({vue}) : {erreur!r}")
        contenu = "<p class='erreur'>Cet état ne peut pas être calculé pour l'instant (Clover ou Sage ne répond pas)."
    q_nav = {k: v for k, v in q.items() if k not in ("vue", "section")}
    from .pages_rapports_web import onglets

    if q.get("pdf") and ctx.reg.peut_exporter(ctx.u):  # PageRapports.pdf_page : état affiché, période et filtres
        return _pdf_page(ctx, vue, du, au, filtres, etat + contenu)
    corps = (onglets("Statistiques Clover", ctx) + barre + message + etat + "<div class='corps-stats'>" + _navigation(q_nav, vue, section, limite)
             + f"<div class='contenu-stats'>{contenu}</div></div>")
    html = page(ctx, "Statistiques Clover", corps)
    if auto and au >= date.today():
        html = html.replace("<head>", "<head><meta http-equiv='refresh' content='60'>", 1)
    return Reponse(corps=html)


def _pdf_page(ctx: Contexte, vue: str, du, au, filtres: dict, contenu: str) -> Reponse:
    """« 📕 PDF de la page » : graphiques (SVG) et tableaux de l'état, période et filtres en sous-titre, en-tête de
    l'entreprise ; mis en page par Edge (export_tableau.pdf_depuis_html), comme Windows."""
    import tempfile
    from pathlib import Path
    from urllib.parse import quote

    from .. import export_tableau
    from ..export_tableau import entete_html, pdf_depuis_html
    from .export_web import STYLE_EXPORT
    from .pages import STYLE
    from .style_windows import STYLE_WINDOWS

    libelle = next((l for _i, _s, etats in NAVIGATION for l, c in etats if c == vue), vue)
    titre = f"Statistiques Clover — {libelle}"
    sous_titre = f"Du {du} au {au}" + (" · " + ", ".join(f"{k} = {v}" for k, v in filtres.items()) if filtres else "")
    export_tableau.RACINE_ENTETE = export_tableau.RACINE_ENTETE or ctx.racine
    try:
        tete = entete_html() + f"<h1>{e(titre)}</h1>"
    except Exception:  # noqa: BLE001 — sans en-tête Clover
        tete = f"<h1>{e(titre)}</h1>"
    html = (f"<!doctype html><html lang='fr'><head><meta charset='utf-8'><title>{e(titre)}</title><style>{STYLE}"
            f"{STYLE_STATS}{STYLE_WINDOWS}{STYLE_EXPORT} .menu-export {{ display: none; }} body {{ background: #fff; }}"
            f"</style></head><body>{tete}<p class='note'>{e(sous_titre)}</p>{contenu}</body></html>")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as dossier:
        chemin = Path(dossier) / "page.pdf"
        pdf_depuis_html(html, chemin)
        octets = chemin.read_bytes()
    return Reponse(corps=octets, type="application/pdf",
                   entetes={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(titre + '.pdf')}"})


def _etat(ctx: Contexte, vue: str, q: dict, b: dict, r: dict, filtres: dict) -> str:
    from .. import statistiques_clover as sc

    libelle = next((l for _i, _s, etats in NAVIGATION for l, c in etats if c == vue), vue)
    extra: dict = {}
    note = ""
    try:
        horizon = int(q.get("horizon") or 14)
    except ValueError:
        horizon = 14
    if vue == "liste_articles":
        entetes, lignes, note = _liste_articles(ctx)
    elif vue == "evolution_annees":
        entetes, lignes, note, extra["series_annees"] = _annees(ctx, b, filtres)
    elif vue in PREVISIONS:
        entetes, lignes, note, extra = _previsions(ctx, vue, horizon)
    elif vue in r["vues"]:
        entetes, lignes = r["vues"][vue]
        if vue in sc.VUES_PAR_JOUR and q.get("par_jour"):
            entetes, lignes = sc.detail_par_jour(sc.filtrer(b["donnees"], filtres), vue, b.get("couts"))
    else:
        return f"<h2 class='titre-etat'>{e(libelle)}</h2><p>Aucune donnée.</p>"
    graph = _graphique_etat(vue, r["vues"][vue][1] if vue in sc.VUES_PAR_JOUR and q.get("par_jour") else lignes,
                            r["vues"], extra)
    texte = (q.get("recherche") or "").strip().casefold()
    if texte:
        lignes = [l for l in lignes if any(texte in str(v).casefold() for v in l)]
    if vue not in PREVISIONS:
        lignes = list(reversed(lignes)) if vue in ("Par jour", "Commandes", "Paiements", "Remboursements") else lignes
    cache = "".join(f"<input type='hidden' name='{k}' value='{e(v)}'>" for k, v in q.items()
                    if k not in ("recherche", "par_jour", "horizon"))
    options = ""
    if vue in sc.VUES_PAR_JOUR:
        options += (f"<div><label><input type='checkbox' name='par_jour' value='1'"
                    f"{' checked' if q.get('par_jour') else ''}> Détail par jour</label></div>")
    if vue in PREVISIONS:
        options += ("<div><label>Horizon</label><select name='horizon'>" + "".join(
            f"<option value='{h}'{' selected' if h == horizon else ''}>{h} jours</option>" for h in HORIZONS)
            + "</select></div>")
    corps = (f"<h2 class='titre-etat'>{e(libelle)}</h2><form class='ligne' method='get'>{cache}<div><label>Rechercher"
             f"</label><input name='recherche' value='{e(q.get('recherche', ''))}'></div>{options}<button "
             "class='second'>Afficher</button></form>" + (f"<p class='note'>{e(note)}</p>" if note else ""))
    if vue == "Résumé":  # aperçu financier : les indicateurs en cartes
        return corps + _kpi(r)
    titre = f"Tableau : {libelle} — {len(lignes)} ligne(s)"
    return corps + graph + tableau_section(Section(titre, entetes, lignes), limite=3000)


STYLE_STATS = """
.barre-stats { display: flex; flex-wrap: wrap; gap: 8px; align-items: end; margin-bottom: 6px; }
.corps-stats { display: flex; gap: 12px; align-items: flex-start; }
nav.nav-stats { width: 210px; flex: none; background: var(--menu); border: 1px solid var(--bord); padding: 6px 6px; }
nav.nav-stats a { display: block; text-decoration: none; color: var(--texte); border-radius: 6px; }
.nav-section { padding: 6px 12px; font-size: 14px; margin-top: 2px; }
.nav-section.ouverte { background: var(--menu-survol); font-weight: 600; }
.nav-etat { padding: 5px 12px 5px 34px; font-size: 13px; }
nav.nav-stats a.actif { background: var(--menu-actif); color: var(--vert); font-weight: 600; }
nav.nav-stats a:hover { background: var(--menu-survol); }
.contenu-stats { flex: 1; min-width: 0; }
.cartes-stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; margin-bottom: 8px; }
.carte-stat { background: var(--carte); border: 1px solid var(--bord); padding: 6px 10px; }
.carte-stat .t { font-size: 13px; color: var(--texte); }
.carte-stat .l { display: flex; justify-content: space-between; align-items: baseline; }
.carte-stat .v { font-size: 20px; font-weight: 600; }
.carte-stat .ecart { font-size: 13px; font-weight: 600; }
.ecart.bon { color: #1b7f3b; } .ecart.mauvais { color: #d7263d; } .ecart.neutre { color: var(--gris); }
.carte-graph { margin-top: 8px; } .carte-graph svg { width: 100%; height: auto; display: block; }
.grille2 { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.grille3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px; }
.kpis { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; margin-top: 6px; }
.kpis.ligne-kpi { grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); }
.kpi { background: var(--carte); border: 1px solid #e2e8e4; padding: 5px 8px; }
.kpi .t { font-size: 12px; color: var(--gris); } .kpi .v { font-size: 16px; font-weight: 600; }
.kpi .v.benefice { color: var(--vert); } .kpi .v.texte { font-size: 12px; } .kpi .v.grand { font-size: 20px; }
.titre-etat { color: var(--vert); font-size: 17px; margin: 0 0 6px; }
tr.total td { font-weight: 600; background: #e8f3ea !important; }
.pe-rouge, tr.pe-rouge td { background: #f8c9cf !important; } .pe-orange, tr.pe-orange td { background: #ffe3a8 !important; }
.pe-neutre, tr.pe-neutre td { background: #eef1ef !important; }
.legende-pe span { display: inline-block; width: 18px; border: 1px solid #999; margin-left: 10px; }
/* analyses décisionnelles : cartes à feu de couleur et constats en bandeaux colorés */
.kpi.etat-bon { border-top: 4px solid #1b7f3b; } .kpi.etat-bon .v { color: #1b7f3b; }
.kpi.etat-attention { border-top: 4px solid #e0a100; } .kpi.etat-attention .v { color: #b77f00; }
.kpi.etat-alerte { border-top: 4px solid #d7263d; } .kpi.etat-alerte .v { color: #d7263d; }
.kpis.ligne-kpi .kpi { border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,.06); padding: 8px 10px; }
.constats { margin: 8px 0; display: grid; gap: 4px; }
.constat { padding: 6px 10px 6px 8px; border-left: 5px solid #8a9690; background: #eef1ef; border-radius: 4px;
  font-size: 13px; line-height: 1.35; }
.constat .i { font-weight: 700; margin-right: 8px; }
.constat.alerte { border-color: #d7263d; background: #fde2e4; } .constat.alerte .i { color: #d7263d; }
.constat.attention { border-color: #e0a100; background: #fff4d6; } .constat.attention .i { color: #b77f00; }
.constat.bon { border-color: #1b7f3b; background: #e6f4ea; } .constat.bon .i { color: #1b7f3b; }
.carte-graph { border-radius: 8px; }
@media (max-width: 820px) {
  .corps-stats { display: block; } nav.nav-stats { width: auto; margin-bottom: 8px; }
  /* téléphone : le menu des états devient une ligne d'onglets qui défile, le rapport vient tout de suite */
  nav.nav-stats { display: flex; overflow-x: auto; white-space: nowrap; gap: 4px; padding: 4px;
    -webkit-overflow-scrolling: touch; }
  nav.nav-stats a { flex: none; border: 1px solid var(--bord); background: var(--carte); padding: 6px 10px !important; }
  nav.nav-stats a.nav-section.ouverte { background: var(--menu-actif); }
  .kpis.ligne-kpi { grid-template-columns: 1fr 1fr; } .kpi .v.grand { font-size: 18px; }
  .constat { font-size: 14px; }
  .cartes-stats, .kpis { grid-template-columns: 1fr 1fr; } .grille2, .grille3 { grid-template-columns: 1fr; }
}
"""

FONCTIONS = [Fonction("/statistiques", "Statistiques Clover", "rapports", statistiques, "📊", "État", menu=False)]
