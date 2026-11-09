"""Analyses décisionnelles des ventes Clover (demande du propriétaire du 2026-11-08 : « un rapport BI complet en tout
point », « pas de redondance avec ce qui est en place, ajoute cela dans l'existant »).

Chaque analyse complète une rubrique existante des statistiques Clover (Activités de vente, Rapports, Articles,
Employés, Clients) et n'y répète aucun état déjà présent : elle rend un `rapports_gestion.RapportGestion` (cartes,
graphique, répartition, tableau exportable, constats) affiché par la même page que les rapports de gestion.

Toutes les analyses partent des données déjà lues pour la période choisie et sa période de comparaison, filtres
globaux appliqués (`statistiques_clover.filtrer`) : aucune lecture de plus dans Clover.

- Activités de vente > Anomalies et alertes : jours atypiques (écart-type du même jour de la semaine), commandes
  inhabituelles (au-delà de Q3 + 3 × IQR), rabais de 50 % ou plus, prix inhabituels pour un article, commandes à 0 $.
- Rapports > Tendance et saisonnalité : moyenne mobile 7 jours, droite de tendance (moindres carrés), indice
  saisonnier par jour de la semaine, variabilité, semaines comparées, projection des 30 prochains jours.
- Rapports > Analyse de la variation : écart avec la période de comparaison décomposé en effet nombre de commandes et
  effet panier, contribution de chaque catégorie, article et employé.
- Rapports > Analyse des paniers : répartition des commandes par montant et par nombre d'articles, médiane, 90e centile.
- Rapports > Concentration des ventes : courbes de Lorenz, indice de Gini, indice de Herfindahl (HHI), dépendance
  aux premiers éléments, pour les articles, catégories, clients, employés, heures, jours et modes de paiement.
- Articles > Matrice des articles : popularité × rentabilité (très vendus et rentables, très vendus mais peu rentables, peu vendus mais rentables, peu vendus et peu rentables), classes
  20/80 (mêmes règles que l'onglet Articles 20/80) croisées avec la régularité de la demande (X / Y / Z), conseil.
- Articles > Articles achetés ensemble : paires d'articles et de catégories (support, confiance, lift).
- Employés > Performance des employés : articles par commande, prix moyen, taux de rabais et de remboursement,
  heures actives, ventes par heure active, indice de panier, clients identifiés, variation.
- Clients > Segmentation RFM : récence, fréquence, montant notés de 1 à 5, segments et action suggérée.
- Clients > Fidélité et rétention : clients retenus, nouveaux et perdus par rapport à la période de comparaison,
  taux de rétention, intervalle entre deux achats.
- Finances > Analyse de la marge : écart du bénéfice brut (CUMP Sage) décomposé en effet prix, effet volume, effet
  mix et articles nouveaux ou arrêtés.
- Articles > Portefeuille des catégories : part des ventes × croissance (étoiles, vaches à lait, prometteuses, en
  recul), marge de chaque catégorie.
- Employés > Achalandage et effectifs : commandes par jour de la semaine et par heure contre les employés actifs,
  créneaux sous tension et créneaux calmes, heures d'ouverture peu achalandées.
- Rapports > Rythme et objectif : objectif de la période (budget des ventes, sinon la période de comparaison),
  réalisé à date, projection de fin de période et ventes à faire par jour restant.
"""

from __future__ import annotations

import math
import unicodedata
import re
import statistics as st
from collections import Counter, defaultdict
from datetime import date, timedelta
from decimal import Decimal
from itertools import combinations

from .rapports_gestion import RapportGestion

ZERO = Decimal(0)
JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
SEUIL_CUMP_DOUTEUX = 5          # comme statistiques_clover : CUMP Sage aberrant ignoré
PART_A, PART_B = 0.20, 0.50      # classes 20/80 (règle du propriétaire du 2026-10-29, comme analyse_articles)
LIGNES_MAX_PAIRES = 60           # commande de plus de 60 articles différents : ignorée pour les paires (coût n²)


def _t(texte: str, **valeurs) -> str:
    from .langues import t

    return t(texte, **valeurs)


def _d(x, motif: str = "0.01") -> Decimal:
    try:
        return Decimal(str(x)).quantize(Decimal(motif))
    except Exception:  # noqa: BLE001 — NaN, infini
        return ZERO


def _pc(partie, total, motif: str = "0.1") -> Decimal:
    return _d(Decimal(str(partie)) * 100 / Decimal(str(total)), motif) if total else ZERO


def _argent(v) -> str:
    return f"{Decimal(str(v)):,.2f} $".replace(",", " ").replace(".", ",")


def _nb(v, decimales: int = 1) -> str:
    return f"{float(v):.{decimales}f}".replace(".", ",")


def _quantile(valeurs: list[float], p: float) -> float:
    if not valeurs:
        return 0.0
    v = sorted(valeurs)
    k = (len(v) - 1) * p
    bas, haut = math.floor(k), math.ceil(k)
    return v[bas] + (v[haut] - v[bas]) * (k - bas)


def _commandes(donnees):
    from .statistiques_clover import preparer

    return preparer(donnees) if donnees is not None else []


MOT_DIRECTION = "direction"   # rabais nommé « Direction » dans Clover


def mises_a_part(ctx) -> dict[str, str]:
    """{identifiant de commande: motif} des commandes dont le rabais va dans l'état « Rabais Direction et
    administrateurs » (demande du propriétaire du 2026-11-08) : rabais nommé « Direction » (commande ou ligne), ou
    commande enregistrée par un compte administrateur de Clover (rôle ADMIN ou propriétaire)."""
    donnees = ctx.get("donnees")
    if donnees is None:
        return {}
    if "_mises_a_part" in ctx:
        return ctx["_mises_a_part"]
    admins = getattr(donnees, "administrateurs", set()) or set()
    employes = getattr(donnees, "employes", {}) or {}
    motifs = {}
    for o in donnees.commandes:
        noms = [x.get("name") or "" for x in (o.get("discounts") or {}).get("elements", [])]
        for li in (o.get("lineItems") or {}).get("elements", []):
            noms += [x.get("name") or "" for x in (li.get("discounts") or {}).get("elements", [])]
        direction = any(MOT_DIRECTION in n.casefold() for n in noms)
        employe = employes.get((o.get("employee") or {}).get("id", ""), "")
        admin = bool(employe) and employe in admins
        if direction or admin:
            motifs[o["id"]] = ("Rabais Direction et compte administrateur" if direction and admin else
                               "Rabais Direction" if direction else "Compte administrateur")
    ctx["_mises_a_part"] = motifs
    return motifs


def _jours(du: date, au: date) -> list[date]:
    fin = min(au, date.today())
    return [du + timedelta(days=i) for i in range((fin - du).days + 1)] if fin >= du else []


def noms_periodes(ctx) -> tuple[str, str]:
    """Libellés des deux courbes comparées, avec leurs dates (« 01/11 → 08/11 » et « 01/10 → 08/10 ») au lieu de
    « période choisie » / « période de comparaison » (question du propriétaire du 2026-11-08)."""
    def nom(du, au):
        return f"{du:%d/%m}" if du == au else f"{du:%d/%m} → {au:%d/%m}"
    return nom(ctx["du"], ctx["au"]), _t("comparaison : {p}", p=nom(ctx["du2"], ctx["au2"]))


def _etiquette(j: date) -> str:
    return f"{j.day:02d}/{j.month:02d}"


# Niveau de chaque constat (demande du propriétaire du 2026-11-08 : « toutes les mesures possibles pour une bonne prise
# de décision par les dirigeants ») : une marque en tête du texte que l'affichage colore (vert, orange, rouge, gris).
MARQUES = {"bon": "✔ ", "attention": "⚠ ", "alerte": "✖ ", "info": "ℹ "}
NIVEAUX = {  # niveau des constats dont le sens ne dépend pas des chiffres
    "Plus forte hausse : {n} ({e}).": "bon", "Plus forte baisse : {n} ({e}).": "attention",
    "{p} % des commandes n'ont qu'un article : piste de ventes complémentaires (voir « Articles achetés ensemble »).":
        "attention",
    "Dépendance à un employé : {p} % des ventes passent par le même vendeur.": "attention",
    "{n} commande(s) avec un rabais de 50 % ou plus : à vérifier avec les employés.": "alerte",
    "{n} ligne(s) vendue(s) à un prix inhabituel : prix saisi à la main ou erreur de prix ?": "attention",
    "Aucune anomalie dans la période.": "bon",
    "Coûts Sage absents : groupe « Coût inconnu » (Sage ne répond pas ou articles non reliés).": "attention",
    "{n} article(s) très vendus mais peu rentables : le premier moyen d'augmenter le bénéfice.": "attention",
    "{n} article(s) peu vendus et peu rentables : {v} de ventes seulement.": "attention",
    "{p} % des clients qui prennent « {a} » prennent aussi « {b} » ({l} fois plus que le hasard) : placer ces articles côte à côte ou en "
    "offre groupée.": "bon",
    "Meilleur changement : {a} ({p} → {q}), {v} de ventes par jour en plus.": "bon",
    "Changement le plus coûteux : {a} ({p} → {q}), {v} de ventes par jour.": "alerte",
    "{n} accorde {p} % de rabais, plus du double de la moyenne ({m} %).": "alerte",
    "Écart de panier : {h} ({a}) contre {b} ({c}).": "attention",
    "Seules {p} % des ventes sont rattachées à un client : demander le client à la caisse rendrait cette analyse plus "
    "complète.": "attention",
    "{n} client(s) à risque ({v} de ventes) : à relancer en priorité.": "alerte",
}


def _k(niveau: str | None, texte: str, **valeurs) -> str:
    """Constat traduit, précédé de la marque de son niveau (`NIVEAUX` si `niveau` est None)."""
    return MARQUES[niveau or NIVEAUX.get(texte, "info")] + _t(texte, **valeurs)


def niveau_constat(ligne: str) -> tuple[str, str]:
    """(niveau, texte sans marque) d'une ligne de constat, pour l'affichage en couleur."""
    ligne = ligne.strip()
    for niveau, marque in MARQUES.items():
        if ligne.startswith(marque.strip()):
            return niveau, ligne[len(marque.strip()):].strip()
    return "info", ligne.lstrip("• ").strip()


def _note(constats: list[str]) -> str:
    return "\n".join(c if c[:1] in "✔⚠✖ℹ" else "• " + c for c in constats if c)


# --------------------------------------------------------------------------------------------- variation
def variation(c, avant, ctx) -> RapportGestion:
    v1, v0 = sum((x.nettes for x in c), ZERO), sum((x.nettes for x in avant), ZERO)
    n1, n0 = len(c), len(avant)
    p1, p0 = (v1 / n1 if n1 else ZERO), (v0 / n0 if n0 else ZERO)
    effet_volume = _d((n1 - n0) * p0)            # commandes en plus ou en moins au panier d'avant
    effet_panier = _d((p1 - p0) * n1)            # panier plus ou moins gros sur les commandes d'aujourd'hui
    ecart = v1 - v0
    r = RapportGestion(note="")
    r.cartes = [("Ventes nettes", "$", v1), ("Période de comparaison", "$", v0), ("Écart", "$", _d(ecart)),
                ("Variation", "%", _pc(ecart, v0) if v0 else ZERO), ("Effet du nombre de ventes", "$", effet_volume),
                ("Effet du montant moyen par vente", "$", effet_panier)]

    def par(cle_ligne=None, cle_commande=None, liste=None):
        cumul = defaultdict(lambda: [ZERO, ZERO])
        for rang, cmds in ((0, c), (1, avant)):
            for x in cmds:
                if cle_commande:
                    cumul[cle_commande(x)][rang] += x.nettes
                else:
                    for l in x.lignes:
                        cumul[cle_ligne(l)][rang] += l.ventes_nettes
        return cumul

    lignes = []
    dims = [("Catégorie", par(cle_ligne=lambda l: l.categorie)), ("Article", par(cle_ligne=lambda l: l.nom)),
            ("Employé", par(cle_commande=lambda x: x.employe))]
    categories = dims[0][1]
    for nom_dim, cumul in dims:
        elements = sorted(cumul.items(), key=lambda kv: -abs(kv[1][0] - kv[1][1]))
        if nom_dim == "Article":
            elements = elements[:40]  # les 40 articles qui ont le plus bougé
        for nom, (a, b) in elements:
            lignes.append([_t(nom_dim), nom, _d(a), _d(b), _d(a - b), _pc(a - b, b) if b else None,
                           _pc(a - b, abs(v0)) if v0 else None])
    r.entetes = ["Niveau", "Élément", "Ventes nettes", "Période de comparaison", "Écart", "Variation %",
                 "Part de l'écart total (points de %)"]
    r.lignes = lignes
    # cumul jour par jour : période choisie contre période de comparaison (même rang de jour)
    du, au, du2, au2 = ctx["du"], ctx["au"], ctx["du2"], ctx["au2"]
    j1 = _jours(du, au)
    par_jour1, par_jour0 = defaultdict(Decimal), defaultdict(Decimal)
    for x in c:
        par_jour1[x.moment.date()] += x.nettes
    for x in avant:
        par_jour0[x.moment.date()] += x.nettes
    j0 = [du2 + timedelta(days=i) for i in range((au2 - du2).days + 1)]
    cumul1, cumul0, s1, s0 = [], [], ZERO, ZERO
    for i, j in enumerate(j1):
        s1 += par_jour1.get(j, ZERO)
        s0 += par_jour0.get(j0[i], ZERO) if i < len(j0) else ZERO
        cumul1.append(s1)
        cumul0.append(s0)
    r.titre_evolution = "Ventes nettes cumulées jour après jour, comparées à la période précédente"
    r.etiquettes = [_etiquette(j) for j in j1]
    r.series = list(zip(noms_periodes(ctx), (cumul1, cumul0)))
    r.titre_repartition = "Catégories qui expliquent l'écart"
    r.genre_repartition = "classement"
    r.repartition = [(("▲ " if a >= b else "▼ ") + nom, abs(_d(a - b)))
                     for nom, (a, b) in sorted(categories.items(), key=lambda kv: -abs(kv[1][0] - kv[1][1]))[:8]]
    constats = []
    if v0:
        constats.append(_k("bon" if ecart >= 0 else "alerte" if ecart < -v0 * Decimal("0.05") else "attention",
                           "Les ventes nettes {sens} de {p} % ({e}) par rapport à la période de comparaison.",
                           sens=_t("augmentent") if ecart >= 0 else _t("baissent"), p=_nb(abs(_pc(ecart, v0))),
                           e=_argent(ecart)))
        constats.append(_k("bon" if effet_panier >= 0 and effet_volume >= 0 else "attention",
                           "Effet nombre de commandes : {v} ({n0} → {n1} commandes) ; effet panier moyen : {p} "
                           "({a} → {b}).", v=_argent(effet_volume), n0=n0, n1=n1, p=_argent(effet_panier),
                           a=_argent(_d(p0)), b=_argent(_d(p1))))
        hausses = [(n, a - b) for n, (a, b) in categories.items() if a - b > 0]
        baisses = [(n, a - b) for n, (a, b) in categories.items() if a - b < 0]
        if hausses:
            n, e = max(hausses, key=lambda x: x[1])
            constats.append(_k(None, "Plus forte hausse : {n} ({e}).", n=n, e=_argent(e)))
        if baisses:
            n, e = min(baisses, key=lambda x: x[1])
            constats.append(_k(None, "Plus forte baisse : {n} ({e}).", n=n, e=_argent(e)))
    else:
        constats.append(_k(None, "Aucune vente dans la période de comparaison : écart non calculable."))
    r.note = _note(constats)
    return r


# --------------------------------------------------------------------------------------------- tendance
def tendance(c, avant, ctx) -> RapportGestion:
    jours = _jours(ctx["du"], ctx["au"])
    par_jour = defaultdict(Decimal)
    cmd_jour = defaultdict(int)
    for x in c:
        par_jour[x.moment.date()] += x.nettes
        cmd_jour[x.moment.date()] += 1
    ouverts = [j for j in jours if j in par_jour]
    valeurs = [float(par_jour[j]) for j in ouverts]
    r = RapportGestion()
    moyenne = st.mean(valeurs) if valeurs else 0.0
    ecart_type = st.pstdev(valeurs) if len(valeurs) > 1 else 0.0
    # droite de tendance (moindres carrés) sur les jours ouverts, x = rang du jour dans la période
    pente, origine = 0.0, moyenne
    if len(ouverts) >= 3:
        xs = [(j - jours[0]).days for j in ouverts]
        mx = st.mean(xs)
        sxx = sum((x - mx) ** 2 for x in xs)
        if sxx:
            pente = sum((x - mx) * (y - moyenne) for x, y in zip(xs, valeurs)) / sxx
            origine = moyenne - pente * mx
    # indice saisonnier : moyenne du jour de la semaine / moyenne des jours ouverts × 100
    par_jds = defaultdict(list)
    for j in ouverts:
        par_jds[j.weekday()].append(float(par_jour[j]))
    indices = {k: (st.mean(v) / moyenne * 100 if moyenne else 0.0) for k, v in par_jds.items()}
    # projection des 30 prochains jours : tendance × indice du jour de la semaine (jours ouverts habituels)
    projection = 0.0
    if ouverts:
        dernier = (ouverts[-1] - jours[0]).days
        taux_ouverture = {k: len(v) / max(1, sum(1 for j in jours if j.weekday() == k)) for k, v in par_jds.items()}
        for k in range(1, 31):
            j = ouverts[-1] + timedelta(days=k)
            base = max(0.0, origine + pente * (dernier + k)) if len(ouverts) >= 3 else moyenne
            projection += base * indices.get(j.weekday(), 0.0) / 100 * taux_ouverture.get(j.weekday(), 0.0)
    cv = ecart_type / moyenne * 100 if moyenne else 0.0
    meilleur = max(ouverts, key=lambda j: par_jour[j]) if ouverts else None
    pire = min(ouverts, key=lambda j: par_jour[j]) if ouverts else None
    r.cartes = [("Moyenne par jour ouvert", "$", _d(moyenne)), ("Hausse ou baisse par semaine", "$", _d(pente * 7)),
                ("Écart d'un jour à l'autre", "%", _d(cv, "0.1")),
                ("Projection des 30 prochains jours", "$", _d(projection))]
    if meilleur:
        r.cartes.append(("Meilleur jour", "t", f"{meilleur} ({_argent(par_jour[meilleur])})"))
        r.cartes.append(("Jour le plus faible", "t", f"{pire} ({_argent(par_jour[pire])})"))
    mobile = []
    for i, j in enumerate(jours):
        fenetre = jours[max(0, i - 6):i + 1]
        mobile.append(_d(sum((par_jour.get(x, ZERO) for x in fenetre), ZERO) / len(fenetre)))
    r.titre_evolution = "Ventes nettes, moyenne des 7 derniers jours et direction"
    r.etiquettes = [_etiquette(j) for j in jours]
    r.series = [("Ventes nettes", [par_jour.get(j, ZERO) for j in jours]), ("Moyenne des 7 derniers jours", mobile)]
    if len(ouverts) >= 3:
        r.series.append(("Direction générale", [_d(max(0.0, origine + pente * i)) for i in range(len(jours))]))
    r.titre_repartition = "Force de chaque jour de la semaine (100 = jour moyen)"
    r.genre_repartition = "classement"
    r.argent_repartition = False
    r.repartition = [(_t(JOURS[k]), _d(v, "0.1")) for k, v in sorted(indices.items(), key=lambda kv: -kv[1])]
    # semaines (lundi → dimanche)
    semaines = defaultdict(lambda: [set(), 0, ZERO])
    for j in ouverts:
        lundi = j - timedelta(days=j.weekday())
        s = semaines[lundi]
        s[0].add(j)
        s[1] += cmd_jour[j]
        s[2] += par_jour[j]
    lignes, precedente, historique, jours_avant = [], None, [], 0
    for lundi in sorted(semaines):
        jours_s, cmds, ventes = semaines[lundi]
        historique.append(ventes)
        mm4 = sum(historique[-4:], ZERO) / len(historique[-4:])
        iso = lundi.isocalendar()
        lignes.append([f"{iso[0]}-S{iso[1]:02d}", str(lundi), str(lundi + timedelta(days=6)), len(jours_s), cmds,
                       _d(ventes), _d(ventes / cmds) if cmds else ZERO,
                       # semaine incomplète (début ou fin de la période) : pas de variation trompeuse
                       _pc(ventes - precedente, precedente) if precedente and len(jours_s) == jours_avant else None,
                       _d(mm4)])
        precedente, jours_avant = ventes, len(jours_s)
    r.entetes = ["Semaine", "Du", "Au", "Jours de vente", "Commandes", "Ventes nettes", "Panier moyen",
                 "Variation sur la semaine précédente %", "Moyenne des 4 dernières semaines"]
    r.lignes = lignes
    constats = []
    if len(ouverts) >= 3 and moyenne:
        sens = _t("hausse") if pente > 0 else _t("baisse")
        constats.append(_k("bon" if pente > 0 else "attention", "Tendance à la {s} : {p} par semaine ({q} % de la moyenne par jour).", s=sens,
                           p=_argent(_d(pente * 7)), q=_nb(abs(pente * 7 / moyenne * 100))))
    if indices:
        fort = max(indices, key=indices.get)
        faible = min(indices, key=indices.get)
        constats.append(_k(None, "Le {j} vend {p} % au-dessus de la moyenne ; le {k}, {q} % en dessous.", j=_t(JOURS[fort]),
                           p=_nb(indices[fort] - 100, 0), k=_t(JOURS[faible]), q=_nb(100 - indices[faible], 0)))
    if moyenne:
        constats.append(_k("attention" if cv >= 40 else "info", "Les ventes varient {n}ment d'un jour à l'autre (écart moyen de {cv} %).",
                           n=_t("faible") if cv < 20 else _t("moyenne") if cv < 40 else _t("forte"), cv=_nb(cv, 0)))
    if len(ouverts) < 14:
        constats.append(_k(None, "Choisissez au moins 4 semaines pour une tendance fiable."))
    r.note = _note(constats)
    return r


# --------------------------------------------------------------------------------------------- paniers
TRANCHES_MONTANT = [(0, 10), (10, 25), (25, 50), (50, 100), (100, 200), (200, None)]
TRANCHES_ARTICLES = [(1, 1), (2, 2), (3, 5), (6, 10), (11, None)]


def paniers(c, avant, ctx) -> RapportGestion:
    total = sum((x.nettes for x in c), ZERO)
    montants = [float(x.nettes) for x in c]
    nombres = [len(x.lignes) for x in c]
    r = RapportGestion()
    r.unite_evolution = ""
    gros = sum((x.nettes for x in c if x.nettes >= 100), ZERO)
    un_seul = sum(1 for n in nombres if n == 1)
    r.cartes = [("Panier typique (médian)", "$", _d(_quantile(montants, 0.5))),
                ("Gros panier (10 % les plus gros)", "$", _d(_quantile(montants, 0.9))),
                ("Articles par panier (typique)", "n", _d(_quantile(nombres, 0.5), "0.1")),
                ("Paniers d'un seul article", "%", _pc(un_seul, len(c))),
                ("Part des ventes des paniers de 100 $ et plus", "%", _pc(gros, total))]
    lignes, etiquettes, nb_cmd, parts = [], [], [], []

    def tranche(nom_type, libelle, choisies):
        n = len(choisies)
        v = sum((x.nettes for x in choisies), ZERO)
        art = sum(len(x.lignes) for x in choisies)
        lignes.append([_t(nom_type), libelle, n, _pc(n, len(c)), _d(v), _pc(v, total), _d(v / n) if n else ZERO,
                       _d(Decimal(art) / n, "0.1") if n else ZERO])
        return n, v

    for bas, haut in TRANCHES_MONTANT:
        libelle = f"{bas} $ – {haut} $" if haut else f"{bas} $ {_t('et plus')}"
        n, v = tranche("Montant", libelle, [x for x in c if x.nettes >= bas and (haut is None or x.nettes < haut)])
        etiquettes.append(libelle)
        nb_cmd.append(n)
        parts.append((libelle, v))
    for bas, haut in TRANCHES_ARTICLES:
        libelle = (str(bas) if haut == bas else f"{bas} – {haut}" if haut else f"{bas} {_t('et plus')}") + " " + _t(
            "article(s)")
        tranche("Nombre d'articles", libelle, [x for x in c if len(x.lignes) >= bas and (haut is None or len(x.lignes) <= haut)])
    r.entetes = ["Répartition", "Tranche", "Commandes", "% des commandes", "Ventes nettes", "% des ventes",
                 "Panier moyen", "Articles par panier"]
    r.lignes = lignes
    r.titre_evolution = "Nombre de commandes par montant du panier"
    r.genre_evolution = "barres"
    r.etiquettes = etiquettes
    r.series = [("Commandes", nb_cmd)]
    r.titre_repartition = "Ventes nettes par montant du panier"
    r.repartition = parts
    constats = []
    if c:
        mediane, moyenne = _quantile(montants, 0.5), float(total) / len(c)
        constats.append(_k(None, "La moitié des paniers font moins de {m} ; le panier moyen ({p}) est tiré par les gros "
                           "paniers.", m=_argent(_d(mediane)), p=_argent(_d(moyenne))) if moyenne > mediane * 1.2
                        else _t("Panier typique {m}, proche du panier moyen {p} : paniers semblables.",
                                m=_argent(_d(mediane)), p=_argent(_d(moyenne))))
        constats.append(_k(None, "{p} % des commandes n'ont qu'un article : piste de ventes complémentaires (voir « Articles "
                           "achetés ensemble »).", p=_nb(_pc(un_seul, len(c)), 0)))
        if avant:
            m0 = _quantile([float(x.nettes) for x in avant], 0.5)
            if m0:
                constats.append(_k("bon" if mediane >= m0 else "attention",
                                   "Panier typique de la période de comparaison : {m} ({v} %).", m=_argent(_d(m0)),
                                   v=("+" if mediane >= m0 else "") + _nb((mediane - m0) / m0 * 100)))
    r.note = _note(constats)
    return r


# --------------------------------------------------------------------------------------------- concentration
def _gini(valeurs: list[float]) -> float:
    v = sorted(x for x in valeurs if x > 0)
    n, s = len(v), sum(v)
    if n < 2 or not s:
        return 0.0
    return sum((2 * (i + 1) - n - 1) * x for i, x in enumerate(v)) / (n * s)


def _lorenz(valeurs: list[float], pas: int = 20) -> list[Decimal]:
    """% cumulé des ventes détenu par les x % premiers éléments (les plus gros d'abord), x = 0, 5, …, 100 %."""
    v = sorted((x for x in valeurs if x > 0), reverse=True)
    total, n = sum(v), len(v)
    if not n or not total:
        return [ZERO] * (pas + 1)
    sortie = []
    for k in range(pas + 1):
        m = round(n * k / pas)
        sortie.append(_d(sum(v[:m]) / total * 100, "0.1"))
    return sortie


def concentration(c, avant, ctx) -> RapportGestion:
    donnees = ctx.get("donnees")
    dims: dict[str, dict] = {"Articles": defaultdict(float), "Catégories": defaultdict(float),
                             "Clients identifiés": defaultdict(float), "Employés": defaultdict(float),
                             "Heures": defaultdict(float), "Jours de la semaine": defaultdict(float),
                             "Jours": defaultdict(float), "Modes de paiement": defaultdict(float)}
    for x in c:
        for l in x.lignes:
            dims["Articles"][l.nom] += float(l.ventes_nettes)
            dims["Catégories"][l.categorie] += float(l.ventes_nettes)
        if x.client != "Sans client":
            dims["Clients identifiés"][x.client] += float(x.nettes)
        dims["Employés"][x.employe] += float(x.nettes)
        dims["Heures"][x.moment.hour] += float(x.nettes)
        dims["Jours de la semaine"][x.moment.weekday()] += float(x.nettes)
        dims["Jours"][x.moment.date()] += float(x.nettes)
    if donnees is not None:
        for p in donnees.paiements:
            if p.get("result") == "SUCCESS":
                dims["Modes de paiement"][(p.get("tender") or {}).get("label", "?")] += (p.get("amount") or 0) / 100
    lignes, gini_articles, hhi_articles = [], 0.0, 0.0
    for nom, d in dims.items():
        v = sorted((x for x in d.values() if x > 0), reverse=True)
        total = sum(v)
        if not v or not total:
            continue
        parts = [x / total for x in v]
        hhi = sum(p * p for p in parts) * 10000
        cumul, pour_80 = 0.0, len(v)
        for i, p in enumerate(parts):
            cumul += p
            if cumul >= 0.8:
                pour_80 = i + 1
                break
        g = _gini(v)
        if nom == "Articles":
            gini_articles, hhi_articles = g, hhi
        niveau = _t("Faible") if hhi < 1500 else _t("Modérée") if hhi < 2500 else _t("Forte")
        lignes.append([_t(nom), len(v), _d(parts[0] * 100, "0.1"), _d(sum(parts[:3]) * 100, "0.1"),
                       _d(sum(parts[:10]) * 100, "0.1"), pour_80, _pc(pour_80, len(v)), _d(g, "0.001"),
                       _d(hhi, "1"), niveau])
    r = RapportGestion()
    r.unite_evolution = "%"
    r.entetes = ["Dimension", "Éléments", "Part du 1er %", "Part des 3 premiers %", "Part des 10 premiers %",
                 "Éléments pour 80 % des ventes", "% des éléments pour 80 %", "Inégalité (0 = égal, 1 = un seul)", "Dépendance (0 à 10 000)",
                 "Niveau de dépendance"]
    r.lignes = lignes
    art = dict((l[0], l) for l in lignes).get(_t("Articles"))
    clients = dims["Clients identifiés"]
    total_c = sum(float(x.nettes) for x in c)
    r.cartes = [("Inégalité des ventes entre articles (0 à 1)", "t", _nb(gini_articles, 2)),
                ("Part des 10 meilleurs articles", "%", art[4] if art else ZERO),
                ("Articles pour 80 % des ventes", "n", art[5] if art else 0),
                ("Part du meilleur client identifié", "%", _pc(max(clients.values()), total_c) if clients else ZERO),
                ("Part du meilleur jour", "%", _pc(max(dims["Jours"].values()), total_c) if dims["Jours"] else ZERO)]
    r.titre_evolution = "Part des ventes faite par les premiers (en % du nombre)"
    r.etiquettes = [f"{k * 5} %" for k in range(21)]
    r.series = [("Articles", _lorenz(list(dims["Articles"].values()))),
                ("Catégories", _lorenz(list(dims["Catégories"].values()))),
                ("Répartition égale", [_d(k * 5) for k in range(21)])]
    if clients:
        r.series.insert(2, ("Clients identifiés", _lorenz(list(clients.values()))))
    r.titre_repartition = "Poids des articles dans les ventes"
    v = sorted(dims["Articles"].values(), reverse=True)
    r.repartition = [(_t("10 premiers articles"), _d(sum(v[:10]))), (_t("Articles 11 à 50"), _d(sum(v[10:50]))),
                     (_t("Articles 51 à 200"), _d(sum(v[50:200]))), (_t("Les autres"), _d(sum(v[200:])))]
    constats = []
    if art:
        constats.append(_k(None, "{n} articles sur {t} ({p} %) font 80 % des ventes ; inégalité {g} (0 = ventes égales, "
                           "1 = un seul article).", n=art[5], t=art[1], p=_nb(art[6]), g=_nb(gini_articles, 2)))
        constats.append(_k("attention" if hhi_articles >= 2500 else "bon", "Dépendance aux meilleurs articles {n} (indice {h} : moins de 1 500 = faible, plus de 2 500 = "
                           "forte).", n=art[9].lower(), h=_nb(hhi_articles, 0)))
    for l in lignes:
        if l[0] == _t("Employés") and l[2] >= 60:
            constats.append(_k(None, "Dépendance à un employé : {p} % des ventes passent par le même vendeur.", p=_nb(l[2])))
    r.note = _note(constats)
    return r


# --------------------------------------------------------------------------------------------- anomalies
def anomalies(c, avant, ctx) -> RapportGestion:
    jours = _jours(ctx["du"], ctx["au"])
    par_jour = defaultdict(Decimal)
    for x in c:
        par_jour[x.moment.date()] += x.nettes
    ouverts = [j for j in jours if j in par_jour and j < date.today()]  # la journée en cours n'est pas finie
    par_jds = defaultdict(list)
    for j in ouverts:
        par_jds[j.weekday()].append(float(par_jour[j]))
    tous = [float(par_jour[j]) for j in ouverts]
    lignes, attendu = [], {}
    for j in ouverts:
        echantillon = par_jds[j.weekday()] if len(par_jds[j.weekday()]) >= 4 else tous
        if len(echantillon) < 4:
            continue
        m, s = st.mean(echantillon), st.pstdev(echantillon)
        attendu[j] = m
        if s and abs(float(par_jour[j]) - m) / s >= 2:
            z = (float(par_jour[j]) - m) / s
            lignes.append([_t("Jour atypique"), str(j), _t(JOURS[j.weekday()]),
                           _t("Ventes très hautes") if z > 0 else _t("Ventes très basses"), _d(par_jour[j]), _d(m),
                           _d(float(par_jour[j]) - m), _d(z, "0.1")])
    montants = [float(x.nettes) for x in c]
    q1, q3 = _quantile(montants, 0.25), _quantile(montants, 0.75)
    seuil = max(q3 + 3 * (q3 - q1), _quantile(montants, 0.99))  # au plus 1 % des commandes
    prix = defaultdict(list)
    for x in c:
        for l in x.lignes:
            if l.quantite_vendue > 0 and l.ventes_brutes > 0:
                prix[l.nom].append(float(l.ventes_brutes / l.quantite_vendue))
    prix_median = {k: _quantile(v, 0.5) for k, v in prix.items() if len(v) >= 5}
    ids = {}  # (date et heure, n°) -> identifiant Clover : un clic sur le n° ouvre la vraie facture
    a_part = mises_a_part(ctx)  # rabais Direction et administrateurs : dans leur propre état
    for x in c:
        quand = f"{x.moment:%Y-%m-%d %H:%M}"
        ids[(quand, x.numero)] = x.id
        brut = sum((l.ventes_brutes for l in x.lignes), ZERO)
        rabais = -sum((l.rabais for l in x.lignes), ZERO)
        if len(c) >= 20 and float(x.nettes) > seuil > 0:
            lignes.append([_t("Commande inhabituelle"), quand, x.numero, _t("Montant très élevé ({e})", e=x.employe),
                           x.nettes, _d(_quantile(montants, 0.5)), _d(float(x.nettes) - _quantile(montants, 0.5)), None])
        if brut > 0 and rabais / brut >= Decimal("0.5") and x.id not in a_part:
            lignes.append([_t("Rabais de 50 % ou plus"), quand, x.numero, _t("Rabais de {p} % ({e})",
                                                                           p=_nb(_pc(rabais, brut), 0), e=x.employe),
                           x.nettes, _d(brut), _d(-rabais), None])
        if x.lignes and x.nettes <= 0 and not (brut > 0 and rabais / brut >= Decimal("0.5")) \
                and x.id not in a_part:
            lignes.append([_t("Commande à 0 $ ou négative"), quand, x.numero, x.employe, x.nettes, _d(brut),
                           _d(x.nettes - brut), None])
        for l in x.lignes:
            m = prix_median.get(l.nom)
            if m and l.quantite_vendue > 0 and l.ventes_brutes > 0:
                pu = float(l.ventes_brutes / l.quantite_vendue)
                if abs(pu - m) / m >= 0.4:
                    lignes.append([_t("Prix inhabituel"), quand, x.numero, f"{l.nom} ({x.employe})", _d(pu), _d(m),
                                   _d(pu - m), None])
    lignes.sort(key=lambda l: l[1], reverse=True)
    r = RapportGestion()
    r.ids_commandes = [ids.get((l[1], l[2]), "") for l in lignes]
    r.entetes = ["Type", "Date", "Commande ou jour", "Détail", "Montant", "Attendu", "Écart", "Écart inhabituel (fois l'écart normal)"]
    r.lignes = lignes
    compte = defaultdict(int)
    for l in lignes:
        compte[l[0]] += 1
    r.cartes = [("Anomalies relevées", "n", len(lignes)), ("Jours inhabituels", "n", compte[_t("Jour atypique")]),
                ("Commandes inhabituelles", "n", compte[_t("Commande inhabituelle")]),
                ("Rabais de 50 % ou plus", "n", compte[_t("Rabais de 50 % ou plus")]),
                ("Prix inhabituels", "n", compte[_t("Prix inhabituel")])]
    r.titre_evolution = "Ventes nettes par jour et ventes attendues (moyenne du même jour de la semaine)"
    r.etiquettes = [_etiquette(j) for j in jours]
    r.series = [("Ventes nettes", [par_jour.get(j, ZERO) for j in jours]),
                ("Ventes attendues", [_d(attendu.get(j, 0)) for j in jours])]
    r.titre_repartition = "Anomalies par type"
    r.argent_repartition = False
    r.repartition = [(k, Decimal(v)) for k, v in sorted(compte.items(), key=lambda kv: -kv[1])]
    constats = [_k(None, "Jour inhabituel : ventes très loin de celles du même jour de la semaine (au moins 4 "
                   "semaines) ; commande inhabituelle : bien plus grosse que presque toutes les autres ; prix inhabituel : "
                   "à 40 % ou plus du prix habituel de l'article (5 ventes au moins).")]
    if a_part:
        constats.append(_k(None, "Les rabais « Direction » et ceux des comptes administrateurs sont dans l'état "
                           "« Rabais Direction et administrateurs » ({n} commande(s)).",
                           n=sum(1 for x in c if x.id in a_part)))
    if compte[_t("Rabais de 50 % ou plus")]:
        constats.append(_k(None, "{n} commande(s) avec un rabais de 50 % ou plus : à vérifier avec les employés.",
                           n=compte[_t("Rabais de 50 % ou plus")]))
    if compte[_t("Prix inhabituel")]:
        constats.append(_k(None, "{n} ligne(s) vendue(s) à un prix inhabituel : prix saisi à la main ou erreur de prix ?",
                           n=compte[_t("Prix inhabituel")]))
    if not lignes:
        constats.append(_k(None, "Aucune anomalie dans la période."))
    r.note = _note(constats)
    return r


# --------------------------------------------------------------------------------------------- matrice des articles
QUADRANTS = {
    "Très vendu et rentable": "Garder toujours en stock et mettre en avant",
    "Très vendu, peu rentable": "Se vend beaucoup mais rapporte peu : augmenter un peu le prix de vente ou négocier le prix d'achat",
    "Peu vendu mais rentable": "Rentable mais peu vendu : mieux exposer, promouvoir",
    "Peu vendu, peu rentable": "Peu vendu et peu rentable : réduire le stock ou retirer",
    "Coût inconnu": "Relier l'article à Sage pour connaître sa marge",
}


def matrice(c, avant, ctx) -> RapportGestion:
    couts = ctx.get("couts") or {}
    jours = sorted({x.moment.date() for x in c})
    # régularité mesurée par semaine dès 4 semaines (la demande d'un jour à l'autre varie trop), sinon par jour
    par_semaine = len(jours) >= 2 and (jours[-1] - jours[0]).days >= 27
    if par_semaine:
        jours = sorted({j - timedelta(days=j.weekday()) for j in jours})
    articles = defaultdict(lambda: {"cat": "", "qte": ZERO, "vendue": ZERO, "brut": ZERO, "nettes": ZERO, "id": "",
                                    "par_jour": defaultdict(float)})
    for x in c:
        for l in x.lignes:
            a = articles[l.nom]
            a["cat"], a["id"] = l.categorie, l.id_article or a["id"]
            a["qte"] += l.quantite_nette
            a["vendue"] += l.quantite_vendue
            a["brut"] += l.ventes_brutes
            a["nettes"] += l.ventes_nettes
            j = x.moment.date()
            a["par_jour"][j - timedelta(days=j.weekday()) if par_semaine else j] += float(l.quantite_nette)
    total = sum((a["nettes"] for a in articles.values()), ZERO)
    ordre = sorted(articles.items(), key=lambda kv: -kv[1]["nettes"])
    n = len(ordre)
    total_qte = sum((max(ZERO, a["qte"]) for a in articles.values()), ZERO)
    # rentabilité : bénéfice par unité (CUMP Sage) comparé à la moyenne pondérée des articles au coût connu
    for _nom, a in ordre:
        a["benefice"] = None
        numero_cump = couts.get(a["id"])
        if numero_cump and numero_cump[1] is not None and a["vendue"] and a["qte"] > 0:
            prix = a["brut"] / a["vendue"]
            cump = Decimal(str(numero_cump[1]))
            if not (prix and cump > SEUIL_CUMP_DOUTEUX * prix):
                a["benefice"] = a["nettes"] - a["qte"] * cump
    avec_cout = [a for _n, a in ordre if a["benefice"] is not None and a["qte"] > 0]
    qte_cout = sum((a["qte"] for a in avec_cout), ZERO)
    marge_moyenne = sum((a["benefice"] for a in avec_cout), ZERO) / qte_cout if qte_cout else None
    seuil_popularite = Decimal("0.7") / n if n else ZERO  # règle du « menu engineering » : 70 % de la part égale
    lignes, compte, ventes_quadrant, matrice_compte = [], defaultdict(int), defaultdict(Decimal), defaultdict(int)
    for rang, (nom, a) in enumerate(ordre, 1):
        classe = "A" if rang <= max(1, math.ceil(n * PART_A)) else "B" if rang <= math.ceil(n * PART_B) else "C"
        quantites = [a["par_jour"].get(j, 0.0) for j in jours]
        moyenne = st.mean(quantites) if quantites else 0.0
        cv = st.pstdev(quantites) / moyenne if moyenne > 0 and len(quantites) > 1 else None
        regularite = ("X" if cv is not None and cv <= 0.5 else "Y" if cv is not None and cv <= 1.0 else "Z")
        populaire = total_qte and max(ZERO, a["qte"]) / total_qte >= seuil_popularite
        if a["benefice"] is None or marge_moyenne is None:
            quadrant = "Coût inconnu"
        else:
            rentable = a["benefice"] / a["qte"] >= marge_moyenne
            quadrant = ("Très vendu et rentable" if populaire and rentable else "Très vendu, peu rentable" if populaire else
                        "Peu vendu mais rentable" if rentable else "Peu vendu, peu rentable")
        compte[quadrant] += 1
        ventes_quadrant[quadrant] += a["nettes"]
        matrice_compte[classe + regularite] += 1
        conseil = _t(QUADRANTS[quadrant])
        if classe + regularite == "AX":
            conseil += " — " + _t("réassort automatique (demande régulière)")
        elif classe == "C" and regularite == "Z":
            conseil += " — " + _t("commander seulement à la demande")
        marge = _pc(a["benefice"], a["nettes"]) if a["benefice"] is not None and a["nettes"] else None
        lignes.append([nom, a["cat"], _d(a["qte"], "0.001"), _d(a["nettes"]), _pc(a["nettes"], total), classe,
                       sum(1 for q in quantites if q), _d(cv, "0.01") if cv is not None else None, regularite,
                       _d(a["benefice"]) if a["benefice"] is not None else None, marge, _t(quadrant), conseil])
    r = RapportGestion()
    r.unite_evolution = ""
    r.entetes = ["Article", "Catégorie", "Quantité nette", "Ventes nettes", "% des ventes", "Classe 20/80",
                 "Semaines de vente" if par_semaine else "Jours de vente", "Irrégularité des ventes", "Régularité (X régulier, Y variable, Z irrégulier)", "Bénéfice", "Marge %",
                 "Groupe", "Conseil"]
    r.lignes = lignes
    r.cartes = [("Articles analysés", "n", n), ("Très vendus et rentables", "n", compte["Très vendu et rentable"]),
                ("Très vendus, peu rentables", "n", compte["Très vendu, peu rentable"]), ("Peu vendus mais rentables", "n", compte["Peu vendu mais rentable"]),
                ("Peu vendus, peu rentables", "n", compte["Peu vendu, peu rentable"]), ("Ventes régulières (X)", "n",
                                                             sum(v for k, v in matrice_compte.items() if k[1] == "X"))]
    cases = [a + b for a in "ABC" for b in "XYZ"]
    r.titre_evolution = "Articles par classe 20/80 et régularité des ventes"
    r.genre_evolution = "barres"
    r.etiquettes = cases
    r.series = [("Articles", [matrice_compte.get(k, 0) for k in cases])]
    r.titre_repartition = "Ventes nettes par groupe"
    r.repartition = [(_t(k), _d(v)) for k, v in sorted(ventes_quadrant.items(), key=lambda kv: -kv[1])]
    constats = [_k(None, "Popularité : part des quantités vendues d'au moins 70 % de la part égale ; rentabilité : bénéfice "
                   "par unité (coût moyen de Sage) au moins égal à la moyenne. X : ventes régulières (irrégularité "
                   "≤ 0,5), Y : variable (≤ 1), Z : irrégulière ; mesurée {p}.",
                   p=_t("semaine par semaine") if par_semaine else _t("jour par jour"))]
    if not couts:
        constats.append(_k(None, "Coûts Sage absents : groupe « Coût inconnu » (Sage ne répond pas ou articles non "
                           "reliés)."))
    if compte["Très vendu, peu rentable"]:
        constats.append(_k(None, "{n} article(s) très vendus mais peu rentables : le premier moyen d'augmenter le bénéfice.",
                           n=compte["Très vendu, peu rentable"]))
    if compte["Peu vendu, peu rentable"]:
        constats.append(_k(None, "{n} article(s) peu vendus et peu rentables : {v} de ventes seulement.", n=compte["Peu vendu, peu rentable"],
                           v=_argent(ventes_quadrant["Peu vendu, peu rentable"])))
    r.note = _note(constats)
    return r


# --------------------------------------------------------------------------------------------- associations
def associations(c, avant, ctx) -> RapportGestion:
    n = len(c)
    seuls = defaultdict(int)
    paires = defaultdict(int)
    cat_seules = defaultdict(int)
    cat_paires = defaultdict(int)
    categorie = {}
    nb_categories = defaultdict(int)
    plusieurs = 0
    for x in c:
        noms = sorted({l.nom for l in x.lignes})
        cats = sorted({l.categorie for l in x.lignes})
        for l in x.lignes:
            categorie[l.nom] = l.categorie
        nb_categories[min(len(cats), 5)] += 1
        if len(noms) > 1:
            plusieurs += 1
        for a in noms:
            seuls[a] += 1
        for a in cats:
            cat_seules[a] += 1
        if 1 < len(noms) <= LIGNES_MAX_PAIRES:
            for a, b in combinations(noms, 2):
                paires[(a, b)] += 1
        for a, b in combinations(cats, 2):
            cat_paires[(a, b)] += 1
    minimum = max(3, math.ceil(n * 0.002))

    def ligne(niveau, a, b, ab, na, nb_):
        lift = (ab * n) / (na * nb_) if na and nb_ else 0
        return [_t(niveau), a, b, ab, _pc(ab, n, "0.01"), _pc(ab, na), _pc(ab, nb_), _d(lift, "0.01"),
                f"{categorie.get(a, '')} / {categorie.get(b, '')}" if niveau == "Articles" else ""]

    articles = [ligne("Articles", a, b, ab, seuls[a], seuls[b]) for (a, b), ab in paires.items() if ab >= minimum]
    articles.sort(key=lambda l: (-l[3], -l[7]))
    cats = [ligne("Catégories", a, b, ab, cat_seules[a], cat_seules[b]) for (a, b), ab in cat_paires.items()
            if ab >= minimum]
    cats.sort(key=lambda l: (-l[3], -l[7]))
    r = RapportGestion()
    r.unite_evolution = ""
    r.entetes = ["Niveau", "Article ou catégorie A", "Article ou catégorie B", "Commandes ensemble", "% des commandes",
                 "Clients de A qui prennent B %", "Clients de B qui prennent A %", "Affinité (fois le hasard)", "Catégories"]
    r.lignes = articles[:300] + cats[:100]
    fortes = [l for l in articles if l[7] >= 2]
    meilleure = max(articles, key=lambda l: (l[7] * min(l[3], 20)), default=None)
    r.cartes = [("Commandes de plusieurs articles", "%", _pc(plusieurs, n)), ("Paires fréquentes", "n", len(articles)),
                ("Paires 2 fois plus fréquentes que le hasard", "n", len(fortes)),
                ("Association la plus forte", "t", f"{meilleure[1]} + {meilleure[2]}" if meilleure else "—")]
    r.titre_evolution = "Commandes selon le nombre de catégories différentes"
    r.genre_evolution = "barres"
    r.etiquettes = ["1", "2", "3", "4", _t("5 et plus")]
    r.series = [("Commandes", [nb_categories.get(k, 0) for k in range(1, 6)])]
    r.titre_repartition = "Paires achetées le plus souvent ensemble"
    r.genre_repartition = "classement"
    r.argent_repartition = False
    r.repartition = [(f"{l[1]} + {l[2]}", Decimal(l[3])) for l in articles[:8]]
    constats = [_k(None, "Seules les paires vues dans au moins {m} commandes sont gardées. « Clients de A qui prennent B » : part des "
                   "commandes avec A qui ont aussi B ; affinité plus grande que 1 : achetés ensemble plus souvent que le hasard.",
                   m=minimum)]
    if meilleure:
        constats.append(_k(None, "{p} % des clients qui prennent « {a} » prennent aussi « {b} » ({l} fois plus que le hasard) : placer ces "
                           "articles côte à côte ou en offre groupée.", p=_nb(meilleure[5], 0), a=meilleure[1],
                           b=meilleure[2], l=_nb(meilleure[7], 1)))
    r.note = _note(constats)
    return r


# --------------------------------------------------------------------------------------------- employés
def employes(c, avant, ctx) -> RapportGestion:
    total = sum((x.nettes for x in c), ZERO)
    e = defaultdict(lambda: {"cmd": 0, "nettes": ZERO, "brut": ZERO, "rabais": ZERO, "remb": ZERO, "art": 0,
                             "qte": ZERO, "heures": set(), "clients": 0, "par_jour": defaultdict(Decimal),
                             "a_part": ZERO})
    a_part = mises_a_part(ctx)
    for x in c:
        g = e[x.employe]
        g["cmd"] += 1
        g["nettes"] += x.nettes
        g["art"] += len(x.lignes)
        g["heures"].add((x.moment.date(), x.moment.hour))
        g["clients"] += x.client != "Sans client"
        g["par_jour"][x.moment.date()] += x.nettes
        for l in x.lignes:
            g["brut"] += l.ventes_brutes
            if x.id in a_part:  # rabais Direction ou d'un administrateur : compté à part
                g["a_part"] += l.rabais
            else:
                g["rabais"] += l.rabais
            g["remb"] += l.remboursements
            g["qte"] += l.quantite_nette
    avant_e = defaultdict(Decimal)
    for x in avant:
        avant_e[x.employe] += x.nettes
    panier_global = total / len(c) if c else ZERO
    lignes = []
    for nom, g in sorted(e.items(), key=lambda kv: -kv[1]["nettes"]):
        heures = len(g["heures"])
        panier = g["nettes"] / g["cmd"] if g["cmd"] else ZERO
        lignes.append([nom, g["cmd"], _d(g["nettes"]), _pc(g["nettes"], total), _d(panier),
                       _d(Decimal(g["art"]) / g["cmd"], "0.1") if g["cmd"] else ZERO,
                       _d(g["nettes"] / g["qte"]) if g["qte"] else ZERO, _pc(-g["rabais"], g["brut"], "0.01"),
                       _pc(-g["remb"], g["brut"], "0.01"), heures, _d(g["nettes"] / heures) if heures else ZERO,
                       _d(Decimal(g["cmd"]) / heures, "0.1") if heures else ZERO,
                       _d(panier / panier_global * 100, "1") if panier_global else ZERO, _pc(g["clients"], g["cmd"]),
                       _pc(g["nettes"] - avant_e[nom], avant_e[nom]) if avant_e.get(nom) else None,
                       _d(-g["a_part"])])
    r = RapportGestion()
    r.entetes = ["Employé", "Commandes", "Ventes nettes", "% des ventes", "Panier moyen", "Articles par commande",
                 "Prix moyen d'un article", "Taux de rabais % (hors Direction et administrateurs)",
                 "Taux de remboursement %", "Heures actives", "Ventes par heure active", "Commandes par heure active",
                 "Indice de panier (100 = moyenne)", "Commandes avec client %", "Variation %",
                 "Rabais Direction et administrateurs"]
    r.lignes = lignes
    toutes_heures = sum(l[9] for l in lignes)
    r.cartes = [("Employés actifs", "n", len(lignes)),
                ("Ventes par heure active", "$", _d(total / toutes_heures) if toutes_heures else ZERO)]
    if lignes:
        r.cartes.append(("Meilleur panier moyen", "t", max(lignes, key=lambda l: l[4])[0]))
        r.cartes.append(("Meilleures ventes par heure", "t", max(lignes, key=lambda l: l[10])[0]))
        r.cartes.append(("Plus fort taux de rabais", "t", max(lignes, key=lambda l: l[7])[0]))
    jours = _jours(ctx["du"], ctx["au"])
    r.titre_evolution = "Ventes nettes par jour des principaux vendeurs"
    r.etiquettes = [_etiquette(j) for j in jours]
    r.series = [(nom, [e[nom]["par_jour"].get(j, ZERO) for j in jours]) for nom in [l[0] for l in lignes[:4]]]
    r.titre_repartition = "Ventes nettes par heure active"
    r.genre_repartition = "classement"
    r.repartition = [(l[0], l[10]) for l in sorted(lignes, key=lambda l: -l[10])[:8]]
    constats = [_k(None, "Heure active : heure où l'employé a enregistré au moins une vente (mesure de l'activité, pas des "
                   "heures payées). Indice de panier : panier moyen de l'employé / panier moyen du magasin × 100.")]
    if len(lignes) > 1:
        rabais_moyen = _pc(-sum((g["rabais"] for g in e.values()), ZERO), sum((g["brut"] for g in e.values()), ZERO),
                           "0.01")
        for l in lignes:
            if rabais_moyen and l[7] > rabais_moyen * 2 and l[1] >= 10:
                constats.append(_k(None, "{n} accorde {p} % de rabais, plus du double de la moyenne ({m} %).", n=l[0],
                                   p=_nb(l[7], 1), m=_nb(rabais_moyen, 1)))
        haut, bas = max(lignes, key=lambda l: l[4]), min(lignes, key=lambda l: l[4])
        if bas[4]:
            constats.append(_k(None, "Écart de panier : {h} ({a}) contre {b} ({c}).", h=haut[0], a=_argent(haut[4]),
                               b=bas[0], c=_argent(bas[4])))
    r.note = _note(constats)
    return r


# --------------------------------------------------------------------------------------------- rabais Direction
def rabais_direction(c, avant, ctx) -> RapportGestion:
    """Rabais « Direction » et rabais des comptes administrateurs, à part des rabais du personnel : ils ne comptent
    ni dans les anomalies, ni dans le taux de rabais des employés, ni dans la décision « Encadrer les rabais »."""
    a_part = mises_a_part(ctx)
    jours = _jours(ctx["du"], ctx["au"])
    lignes, ids, par_jour, par_employe, par_motif = [], [], defaultdict(Decimal), defaultdict(Decimal), defaultdict(int)
    total_rabais = direction = ZERO
    for x in sorted(c, key=lambda x: x.moment, reverse=True):
        brut = sum((l.ventes_brutes for l in x.lignes), ZERO)
        rabais = -sum((l.rabais for l in x.lignes), ZERO)
        total_rabais += rabais
        motif = a_part.get(x.id)
        if not motif or rabais <= 0:
            continue
        par_jour[x.moment.date()] += rabais
        par_employe[x.employe] += rabais
        par_motif[motif] += 1
        if "Direction" in motif:
            direction += rabais
        lignes.append([_t(motif), f"{x.moment:%Y-%m-%d %H:%M}", x.numero, x.employe, _d(brut), _d(rabais),
                       x.nettes, _pc(rabais, brut) if brut else None])
        ids.append(x.id)
    total = sum((l[5] for l in lignes), ZERO)
    r = RapportGestion()
    r.ids_commandes = ids
    r.entetes = ["Type", "Date", "Commande ou jour", "Employé", "Ventes brutes", "Rabais", "Ventes nettes",
                 "Rabais %"]
    r.lignes = lignes
    r.cartes = [("Rabais mis à part", "$", _d(total)), ("Commandes", "n", len(lignes)),
                ("Rabais Direction", "$", _d(direction)), ("Rabais des administrateurs", "$", _d(total - direction)),
                ("Part de tous les rabais", "%", _pc(total, total_rabais) if total_rabais else ZERO)]
    r.titre_evolution = "Rabais Direction et administrateurs par jour"
    r.etiquettes = [_etiquette(j) for j in jours]
    r.series = [("Rabais", [_d(par_jour.get(j, ZERO)) for j in jours])]
    r.genre_evolution = "barres"
    r.titre_repartition = "Rabais par employé"
    r.genre_repartition = "classement"
    r.repartition = [(n, _d(v)) for n, v in sorted(par_employe.items(), key=lambda kv: -kv[1])[:8]]
    constats = [_k(None, "Rabais nommés « Direction » dans Clover et commandes enregistrées par un compte "
                   "administrateur (rôle ADMIN ou propriétaire) : suivis ici, à part des rabais du personnel (anomalies, "
                   "taux de rabais des employés, décisions).")]
    if lignes:
        constats.append(_k("attention" if total_rabais and total * 3 > total_rabais else None,
                           "{v} de rabais mis à part sur {n} commande(s), soit {p} % de tous les rabais de la "
                           "période.", v=_argent(total), n=len(lignes), p=_nb(_pc(total, total_rabais) if total_rabais
                                                                              else 0)))
    else:
        constats.append(_k("bon", "Aucun rabais Direction ni rabais d'un compte administrateur dans la période."))
    r.note = _note(constats)
    return r


# --------------------------------------------------------------------------------------------- marge
def _cump(couts: dict, ident: str, prix) -> Decimal | None:
    """CUMP Sage de l'article (None : inconnu ou aberrant, plus de 5 fois le prix de vente)."""
    valeur = couts.get(ident)
    if not valeur or valeur[1] is None:
        return None
    cout = Decimal(str(valeur[1]))
    return None if prix and cout > SEUIL_CUMP_DOUTEUX * Decimal(str(prix)) else cout


def _par_article(cmds) -> dict:
    articles = defaultdict(lambda: {"nom": "", "cat": "", "qte": ZERO, "vendue": ZERO, "brut": ZERO, "nettes": ZERO,
                                    "jours": defaultdict(lambda: [ZERO, ZERO])})
    for x in cmds:
        for l in x.lignes:
            a = articles[l.id_article or l.nom]
            a["nom"], a["cat"] = l.nom, l.categorie
            a["qte"] += l.quantite_nette
            a["vendue"] += l.quantite_vendue
            a["brut"] += l.ventes_brutes
            a["nettes"] += l.ventes_nettes
            jour = a["jours"][x.moment.date()]
            jour[0] += l.ventes_nettes
            jour[1] += l.quantite_nette
    return articles


def marge(c, avant, ctx) -> RapportGestion:
    """Écart du bénéfice brut avec la période de comparaison, décomposé (« pont de marge ») :
    - effet prix = quantités d'aujourd'hui × variation du prix net moyen (rabais compris) ;
    - effet des quantités = variation des quantités totales × bénéfice moyen par unité d'avant ;
    - effet mix = changement de la composition des ventes (plus ou moins d'articles rentables) ;
    - articles nouveaux ou arrêtés = bénéfice des articles vendus dans une seule des deux périodes.
    Le coût est le CUMP actuel de Sage pour les deux périodes (seul coût connu) : l'effet du coût d'achat n'est pas
    séparé."""
    couts = ctx.get("couts") or {}
    a1, a0 = _par_article(c), _par_article(avant)
    cump = {}
    for k in set(a1) | set(a0):
        g = a1.get(k) or a0.get(k)
        cump[k] = _cump(couts, k, g["brut"] / g["vendue"] if g["vendue"] else ZERO)

    def benefice(g, k):
        return g["nettes"] - g["qte"] * cump[k]

    continus = [k for k in a1 if k in a0 and cump[k] is not None and a1[k]["qte"] > 0 and a0[k]["qte"] > 0]
    b1 = sum((benefice(g, k) for k, g in a1.items() if cump[k] is not None), ZERO)
    b0 = sum((benefice(g, k) for k, g in a0.items() if cump[k] is not None), ZERO)
    v1 = sum((g["nettes"] for k, g in a1.items() if cump[k] is not None), ZERO)
    v0 = sum((g["nettes"] for k, g in a0.items() if cump[k] is not None), ZERO)
    total1 = sum((g["nettes"] for g in a1.values()), ZERO)
    q1 = sum((a1[k]["qte"] for k in continus), ZERO)
    q0 = sum((a0[k]["qte"] for k in continus), ZERO)
    moyen0 = sum((benefice(a0[k], k) for k in continus), ZERO) / q0 if q0 else ZERO
    effet_prix = effet_quantite = ZERO
    for k in continus:
        p1, p0 = a1[k]["nettes"] / a1[k]["qte"], a0[k]["nettes"] / a0[k]["qte"]
        effet_prix += a1[k]["qte"] * (p1 - p0)
        effet_quantite += (a1[k]["qte"] - a0[k]["qte"]) * (p0 - cump[k])
    effet_volume = (q1 - q0) * moyen0
    effet_mix = effet_quantite - effet_volume
    ecart = b1 - b0
    autres = ecart - effet_prix - effet_quantite  # articles vendus dans une seule des deux périodes
    marge1, marge0 = _pc(b1, v1) if v1 else ZERO, _pc(b0, v0) if v0 else ZERO
    r = RapportGestion()
    r.cartes = [("Bénéfice brut", "$", _d(b1)), ("Période de comparaison", "$", _d(b0)),
                ("Écart du bénéfice", "$", _d(ecart)), ("Marge brute", "%", marge1),
                ("Marge de la comparaison", "%", marge0), ("Effet des prix", "$", _d(effet_prix)),
                ("Effet des quantités", "$", _d(effet_volume)), ("Effet du choix des articles", "$", _d(effet_mix)),
                ("Articles nouveaux ou arrêtés", "$", _d(autres)),
                ("Ventes au coût connu", "%", _pc(v1, total1) if total1 else ZERO)]
    lignes = []
    for k in set(a1) | set(a0):
        if cump[k] is None:
            continue
        g1, g0 = a1.get(k), a0.get(k)
        n1, n0 = (benefice(g1, k) if g1 else ZERO), (benefice(g0, k) if g0 else ZERO)
        prix1 = g1["nettes"] / g1["qte"] if g1 and g1["qte"] > 0 else None
        prix0 = g0["nettes"] / g0["qte"] if g0 and g0["qte"] > 0 else None
        e_prix = g1["qte"] * (prix1 - prix0) if k in continus else None
        e_qte = (g1["qte"] - g0["qte"]) * (prix0 - cump[k]) if k in continus else None
        g = g1 or g0
        lignes.append([g["nom"], g["cat"], _d(g1["qte"] if g1 else ZERO, "0.001"),
                       _d(g0["qte"] if g0 else ZERO, "0.001"), _d(prix1) if prix1 is not None else None,
                       _d(prix0) if prix0 is not None else None, _d(cump[k]), _d(n1), _d(n0), _d(n1 - n0),
                       _d(e_prix) if e_prix is not None else None, _d(e_qte) if e_qte is not None else None,
                       _pc(n1, g1["nettes"]) if g1 and g1["nettes"] else None])
    lignes.sort(key=lambda l: -abs(l[9]))
    r.entetes = ["Article", "Catégorie", "Quantité nette", "Quantité (comparaison)", "Prix net moyen",
                 "Prix net (comparaison)", "Coût moyen (Sage)", "Bénéfice", "Bénéfice (comparaison)", "Écart", "Effet des prix",
                 "Effet des quantités vendues", "Marge %"]
    r.lignes = lignes
    # bénéfice cumulé jour par jour : période choisie contre comparaison (même rang de jour)
    du, au, du2, au2 = ctx["du"], ctx["au"], ctx["du2"], ctx["au2"]
    j1, j0 = _jours(du, au), _jours(du2, au2)

    def par_jour(articles):
        jours = defaultdict(Decimal)
        for k, g in articles.items():
            if cump[k] is not None:
                for j, (nettes, qte) in g["jours"].items():
                    jours[j] += nettes - qte * cump[k]
        return jours

    p1, p0 = par_jour(a1), par_jour(a0)
    s1 = s0 = ZERO
    cumul1, cumul0 = [], []
    for i, j in enumerate(j1):
        s1 += p1.get(j, ZERO)
        s0 += p0.get(j0[i], ZERO) if i < len(j0) else ZERO
        cumul1.append(_d(s1))
        cumul0.append(_d(s0))
    r.titre_evolution = "Bénéfice brut cumulé jour après jour, comparé à la période précédente"
    r.etiquettes = [_etiquette(j) for j in j1]
    r.series = list(zip(noms_periodes(ctx), (cumul1, cumul0)))
    r.titre_repartition = "Ce qui explique l'écart du bénéfice"
    r.genre_repartition = "classement"
    r.repartition = [_signe(_t(n), v) for n, v in (("Effet des prix", effet_prix), ("Effet des quantités", effet_volume),
                                                   ("Effet du choix des articles", effet_mix), ("Articles nouveaux ou arrêtés", autres))
                     if v]
    constats = [_k(None, "Explication du bénéfice : effet des prix = quantités vendues × variation du prix net (rabais compris) ; "
                   "effet des quantités = variation des quantités × bénéfice moyen par unité d'avant ; effet du choix des articles = plus ou "
                   "moins d'articles rentables dans les ventes. Coût = coût moyen actuel de Sage pour les deux périodes.")]
    if not couts:
        constats.append(_k("attention", "Coûts Sage absents : bénéfice et marge non calculables (Sage ne répond pas "
                                        "ou articles non reliés)."))
    elif v1:
        baisse = marge0 - marge1
        constats.append(_k("bon" if baisse <= 0 else "alerte" if baisse > 1 else "attention",
                           "Marge brute de {m} % contre {n} % dans la période de comparaison ; bénéfice brut {b} "
                           "({e}).", m=_nb(marge1), n=_nb(marge0), b=_argent(b1), e=_argent(ecart)))
        effets = [("Effet des prix", effet_prix), ("Effet des quantités", effet_volume), ("Effet du choix des articles", effet_mix)]
        nom, v = min(effets, key=lambda x: x[1])
        if v < 0:
            constats.append(_k("attention", "Principal frein : {n} ({v}).", n=_t(nom), v=_argent(v)))
        nom, v = max(effets, key=lambda x: x[1])
        if v > 0:
            constats.append(_k("bon", "Principal moteur : {n} ({v}).", n=_t(nom), v=_argent(v)))
        couverture = _pc(v1, total1) if total1 else ZERO
        if couverture < 80:
            constats.append(_k("attention", "Seules {p} % des ventes ont un coût connu dans Sage : relier les articles "
                                            "(Articles > Correspondance) pour une marge complète.", p=_nb(couverture, 0)))
    r.note = _note(constats)
    return r


# --------------------------------------------------------------------------------------------- portefeuille
CONSEILS_CATEGORIES = {
    "Étoile": "Investir : stock, espace et visibilité",
    "Vache à lait": "Protéger la marge et la disponibilité, sans trop investir",
    "Prometteuse": "Développer : tester, promouvoir, élargir l'offre",
    "En recul": "Réduire l'espace ou relancer l'offre",
}


def portefeuille(c, avant, ctx) -> RapportGestion:
    """Catégories classées par part des ventes (au-dessus ou au-dessous de la part moyenne) et par croissance
    (au-dessus ou au-dessous de la croissance du magasin) : étoile, vache à lait, prometteuse, en recul."""
    couts = ctx.get("couts") or {}
    jours = _jours(ctx["du"], ctx["au"])
    par_semaine = len(jours) >= 28
    cat = defaultdict(lambda: {"v1": ZERO, "v0": ZERO, "articles": set(), "benefice": ZERO, "connu": ZERO,
                               "temps": defaultdict(Decimal)})
    for rang, cmds in ((1, c), (0, avant)):
        for x in cmds:
            j = x.moment.date()
            for l in x.lignes:
                g = cat[l.categorie]
                if not rang:
                    g["v0"] += l.ventes_nettes
                    continue
                g["v1"] += l.ventes_nettes
                g["articles"].add(l.nom)
                g["temps"][j - timedelta(days=j.weekday()) if par_semaine else j] += l.ventes_nettes
                cout = _cump(couts, l.id_article, l.ventes_brutes / l.quantite_vendue if l.quantite_vendue else 0)
                if cout is not None:
                    g["benefice"] += l.ventes_nettes - l.quantite_nette * cout
                    g["connu"] += l.ventes_nettes
    total1 = sum((g["v1"] for g in cat.values()), ZERO)
    total0 = sum((g["v0"] for g in cat.values()), ZERO)
    croissance_magasin = _pc(total1 - total0, total0) if total0 else ZERO
    actives = [n for n, g in cat.items() if g["v1"] > 0]
    part_moyenne = Decimal(100) / len(actives) if actives else ZERO
    lignes, compte, ventes_q = [], Counter(), defaultdict(Decimal)
    for nom, g in sorted(cat.items(), key=lambda kv: -kv[1]["v1"]):
        part = _pc(g["v1"], total1) if total1 else ZERO
        croissance = _pc(g["v1"] - g["v0"], g["v0"]) if g["v0"] else None
        forte = g["v1"] > 0 and part >= part_moyenne
        croit = g["v1"] > 0 and (croissance is None or croissance >= croissance_magasin)
        quadrant = ("Étoile" if forte and croit else "Vache à lait" if forte else "Prometteuse" if croit else
                    "En recul")
        compte[quadrant] += 1
        ventes_q[quadrant] += max(ZERO, g["v1"])
        lignes.append([nom, _d(g["v1"]), part, _d(g["v0"]), croissance,
                       _d(croissance - croissance_magasin, "0.1") if croissance is not None else None,
                       len(g["articles"]), _d(g["benefice"]) if g["connu"] else None,
                       _pc(g["benefice"], g["connu"]) if g["connu"] else None, _t(quadrant),
                       _t(CONSEILS_CATEGORIES[quadrant])])
    r = RapportGestion()
    r.entetes = ["Catégorie", "Ventes nettes", "Part des ventes %", "Période de comparaison", "Croissance %",
                 "Croissance au-dessus du magasin (points de %)", "Articles vendus", "Bénéfice", "Marge %",
                 "Groupe", "Conseil"]
    r.lignes = lignes
    r.cartes = [("Catégories", "n", len(actives)), ("Étoiles", "n", compte["Étoile"]),
                ("Vaches à lait", "n", compte["Vache à lait"]), ("Prometteuses", "n", compte["Prometteuse"]),
                ("En recul", "n", compte["En recul"]), ("Croissance du magasin", "%", croissance_magasin)]
    temps = sorted({k for g in cat.values() for k in g["temps"]}) if par_semaine else jours
    r.titre_evolution = ("Ventes nettes par semaine des principales catégories" if par_semaine else
                         "Ventes nettes par jour des principales catégories")
    r.etiquettes = [_etiquette(k) for k in temps]
    r.series = [(l[0], [_d(cat[l[0]]["temps"].get(k, ZERO)) for k in temps]) for l in lignes[:5] if l[1] > 0]
    r.titre_repartition = "Ventes nettes par groupe"
    r.repartition = [(_t(q), _d(v)) for q, v in sorted(ventes_q.items(), key=lambda kv: -kv[1]) if v]
    constats = [_k(None, "Part forte : au moins la part moyenne d'une catégorie ({m} %) ; croissance forte : au moins "
                   "la croissance du magasin ({c} %). Étoile : forte et en croissance ; vache à lait : forte, croissance "
                   "faible ; prometteuse : petite mais en croissance ; en recul : petite et en perte de vitesse.",
                   m=_nb(part_moyenne), c=_nb(croissance_magasin))]
    etoiles = [l for l in lignes if l[9] == _t("Étoile")]
    if etoiles:
        constats.append(_k("bon", "Étoiles : {e}.", e=", ".join(l[0] for l in etoiles[:5])))
    prometteuses = [l for l in lignes if l[9] == _t("Prometteuse") and l[4] is not None]
    if prometteuses:
        meilleure = max(prometteuses, key=lambda l: l[4])
        constats.append(_k("bon", "Catégorie prometteuse la plus dynamique : {n} (+{p} %).", n=meilleure[0],
                           p=_nb(meilleure[4])))
    vaches = [l for l in lignes if l[9] == _t("Vache à lait") and l[4] is not None and l[4] < 0]
    for l in vaches[:3]:
        constats.append(_k("attention", "{n} pèse {p} % des ventes mais recule de {q} % : à surveiller.", n=l[0],
                           p=_nb(l[2]), q=_nb(abs(l[4]))))
    r.note = _note(constats)
    return r


# --------------------------------------------------------------------------------------------- achalandage
def achalandage(c, avant, ctx) -> RapportGestion:
    """Commandes de chaque créneau (jour de la semaine × heure), en moyenne par jour ouvert, contre les employés qui
    y ont enregistré des ventes : créneaux sous tension (beaucoup de commandes par employé) et créneaux calmes
    (plusieurs employés pour peu de commandes)."""
    ouverts = Counter(j.weekday() for j in {x.moment.date() for x in c})
    creneaux = defaultdict(lambda: {"jours": set(), "cmd": 0, "ventes": ZERO, "presences": defaultdict(set)})
    for x in c:
        j = x.moment.date()
        g = creneaux[(j.weekday(), x.moment.hour)]
        g["jours"].add(j)
        g["cmd"] += 1
        g["ventes"] += x.nettes
        g["presences"][j].add(x.employe)
    mesures = {}
    for k, g in creneaux.items():
        presences = sum(len(v) for v in g["presences"].values())
        mesures[k] = {"jours": len(g["jours"]), "cmd_jour": g["cmd"] / max(1, ouverts[k[0]]),
                      "ventes_jour": g["ventes"] / max(1, ouverts[k[0]]),
                      "employes": presences / len(g["jours"]), "par_employe": g["cmd"] / presences,
                      "panier": g["ventes"] / g["cmd"]}
    charges = [m["par_employe"] for m in mesures.values()]
    volumes = [m["cmd_jour"] for m in mesures.values()]
    q1, charge_mediane = _quantile(charges, 0.25), _quantile(charges, 0.5)
    volume_q3 = _quantile(volumes, 0.75)
    lignes, tension, calmes = [], [], []
    for (jds, heure), m in sorted(mesures.items()):
        # sous tension : au moins 1,5 fois la charge médiane par employé, dans le quart des heures les plus achalandées
        if len(mesures) >= 8 and m["par_employe"] >= 1.5 * charge_mediane and m["cmd_jour"] >= volume_q3:
            diagnostic = "Chargée"
            tension.append((jds, heure, m))
        elif m["employes"] >= 1.5 and m["par_employe"] <= q1:
            diagnostic = "Calme"
            calmes.append((jds, heure, m))
        else:
            diagnostic = "Normal"
        lignes.append([_t(JOURS[jds]), f"{heure} h", m["jours"], _d(m["cmd_jour"], "0.1"), _d(m["ventes_jour"]),
                       _d(m["employes"], "0.1"), _d(m["par_employe"], "0.1"), _d(m["panier"]), _t(diagnostic)])
    r = RapportGestion()
    r.entetes = ["Jour", "Heure", "Jours observés", "Commandes par jour", "Ventes nettes par jour", "Employés actifs",
                 "Commandes par employé", "Panier moyen", "Diagnostic"]
    r.lignes = lignes
    pointe = max(mesures.items(), key=lambda kv: kv[1]["cmd_jour"]) if mesures else None
    heures_ouvertes = sum(len(g["jours"]) for g in creneaux.values())
    presences = sum(sum(len(v) for v in g["presences"].values()) for g in creneaux.values())
    r.cartes = [("Heure de pointe", "t", f"{_t(JOURS[pointe[0][0]])} {pointe[0][1]} h" if pointe else "—"),
                ("Commandes par heure ouverte", "n", _d(Decimal(len(c)) / heures_ouvertes, "0.1")
                 if heures_ouvertes else ZERO),
                ("Employés actifs par heure", "n", _d(Decimal(presences) / heures_ouvertes, "0.1")
                 if heures_ouvertes else ZERO),
                ("Heures chargées", "n", len(tension)), ("Heures calmes", "n", len(calmes))]
    heures = sorted({h for _j, h in mesures})
    jours_ouverts = sum(ouverts.values()) or 1
    par_heure = defaultdict(lambda: [0, 0])
    for (_j, h), g in creneaux.items():
        par_heure[h][0] += g["cmd"]
        par_heure[h][1] += sum(len(v) for v in g["presences"].values())
    r.titre_evolution = "Commandes par heure et employés actifs (moyenne par jour ouvert)"
    r.genre_evolution = "barres"
    r.unite_evolution = ""
    r.etiquettes = [f"{h} h" for h in heures]
    r.series = [("Commandes", [_d(Decimal(par_heure[h][0]) / jours_ouverts, "0.1") for h in heures]),
                ("Employés actifs", [_d(Decimal(par_heure[h][1]) / jours_ouverts, "0.1") for h in heures])]
    r.titre_repartition = "Heures les plus chargées par employé"
    r.genre_repartition = "classement"
    r.argent_repartition = False
    r.repartition = [(f"{_t(JOURS[j])} {h} h", _d(m["par_employe"], "0.1"))
                     for (j, h), m in sorted(mesures.items(), key=lambda kv: -kv[1]["par_employe"])[:8]]
    constats = [_k(None, "Employé actif : employé qui a enregistré au moins une vente dans l'heure (un employé présent "
                   "sans vente n'est pas compté). Sous tension : au moins 1,5 fois la charge habituelle par employé, "
                   "dans le quart des heures les plus achalandées ; calme : 1,5 employé actif ou plus pour peu de commandes chacun.")]
    if pointe:
        constats.append(_k(None, "Heure de pointe : {j} {h} h, {n} commandes en moyenne.", j=_t(JOURS[pointe[0][0]]),
                           h=pointe[0][1], n=_nb(pointe[1]["cmd_jour"])))
    if tension:
        constats.append(_k("attention", "{n} créneau(x) sous tension : {c}. Renforcer la caisse à ces heures.",
                           n=len(tension), c=", ".join(f"{_t(JOURS[j])} {h} h" for j, h, _m in
                                                       sorted(tension, key=lambda x: -x[2]["par_employe"])[:6])))
    if calmes:
        constats.append(_k("attention", "{n} créneau(x) calme(s) avec plusieurs employés : {c}. Prévoir d'autres "
                                        "tâches (mise en rayon, inventaire) ou alléger l'horaire.",
                           n=len(calmes), c=", ".join(f"{_t(JOURS[j])} {h} h" for j, h, _m in calmes[:6])))
    if not tension and not calmes and mesures:
        constats.append(_k("bon", "Effectifs en accord avec l'achalandage : aucun créneau sous tension ni calme."))
    # heures d'ouverture : première et dernière heure de chaque jour qui vendent moins du quart d'une heure moyenne
    faibles = []
    for jds in sorted({j for j, _h in mesures}):
        heures_j = sorted(h for j, h in mesures if j == jds)
        moyenne_h = sum((mesures[(jds, h)]["ventes_jour"] for h in heures_j), ZERO) / len(heures_j)
        for h in {heures_j[0], heures_j[-1]}:
            if len(heures_j) >= 4 and mesures[(jds, h)]["ventes_jour"] < moyenne_h / 4:
                faibles.append((jds, h, mesures[(jds, h)]["ventes_jour"], moyenne_h))
    for jds, h, _v, _m in faibles:  # diagnostic dans le tableau
        for l in lignes:
            if l[0] == _t(JOURS[jds]) and l[1] == f"{h} h" and l[8] == _t("Normal"):
                l[8] = _t("Heure d'ouverture peu achalandée")
    r.heures_faibles = faibles
    if faibles:
        constats.append(_k("attention", "{n} heure(s) d'ouverture ou de fermeture vendent moins du quart d'une heure "
                                        "moyenne : {c}.", n=len(faibles),
                           c=", ".join(f"{_t(JOURS[j])} {h} h ({_argent(_d(v))})" for j, h, v, _m in faibles[:6])))
    r.note = _note(constats)
    return r


# --------------------------------------------------------------------------------------------- rythme et objectif
def _objectif_budget(racine, du: date, au: date) -> Decimal | None:
    """Ventes prévues au budget (Comptabilité > Budget et écarts) pour la période, au prorata des jours de chaque
    mois ; None si aucun mois de la période n'a de budget des ventes."""
    if not racine:
        return None
    try:
        from .budget import Budget, POSTES

        budget = Budget(racine)
    except Exception:  # noqa: BLE001 — budget illisible : objectif = période de comparaison
        return None
    total, trouve = ZERO, False
    for j in _jours(du, au):
        valeur = budget.mois(j.year, j.month).get(POSTES[0], ZERO)
        if valeur:
            trouve = True
            prochain = (j.replace(day=28) + timedelta(days=4)).replace(day=1)
            total += valeur / (prochain - j.replace(day=1)).days
    return _d(total) if trouve else None


def fin_naturelle(du: date, au: date, aujourd_hui: date) -> date:
    """Fin de la période en cours : mois, semaine (lundi → dimanche) ou année entière quand la période choisie
    s'arrête à aujourd'hui ; sinon `au`."""
    if au < aujourd_hui:
        return au
    if du.day == 1 and du.month == 1 and (au - du).days > 31:
        return du.replace(month=12, day=31)
    if du.day == 1 and (du.year, du.month) == (au.year, au.month):
        return (du.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    if du.weekday() == 0 and (au - du).days < 7:
        return du + timedelta(days=6)
    return au


def rythme(c, avant, ctx) -> RapportGestion:
    """Où en est la période choisie : objectif (budget des ventes au prorata des jours, sinon les ventes de la période
    de comparaison), réalisé jusqu'à aujourd'hui, projection de la fin de période (moyenne de chaque jour de la semaine
    déjà vu, sinon celle de la comparaison) et ventes à faire par jour restant pour atteindre l'objectif."""
    du, au = ctx["du"], ctx["au"]
    aujourd_hui = ctx.get("aujourd_hui") or date.today()
    au = fin_naturelle(du, au, aujourd_hui)  # « Ce mois-ci » s'arrête à aujourd'hui : on vise la fin du mois
    jours = [du + timedelta(days=i) for i in range((au - du).days + 1)]  # jours à venir compris (pas _jours)
    par_jour, avant_jour = defaultdict(Decimal), defaultdict(Decimal)
    for x in c:
        par_jour[x.moment.date()] += x.nettes
    for x in avant:
        avant_jour[x.moment.date()] += x.nettes
    budget = _objectif_budget(ctx.get("racine"), du, au)
    source = "Budget des ventes" if budget is not None else "Rythme de la période de comparaison"
    passes = [j for j in jours if j < aujourd_hui]          # journées terminées
    restants = [j for j in jours if j >= aujourd_hui]       # aujourd'hui (en cours) et jours à venir
    realise = sum((par_jour.get(j, ZERO) for j in jours), ZERO)

    def moyennes(valeurs: dict, liste) -> dict:
        groupes = defaultdict(list)
        for j in liste:
            groupes[j.weekday()].append(valeurs.get(j, ZERO))
        return {k: sum(v, ZERO) / len(v) for k, v in groupes.items()}

    moy = moyennes(par_jour, passes)
    moy_avant = moyennes(avant_jour, _jours(ctx["du2"], ctx["au2"]))
    # sans budget : ventes moyennes de chaque jour de la semaine dans la comparaison, sur toute la période
    objectif = budget if budget is not None else _d(sum((moy_avant.get(j.weekday(), ZERO) for j in jours), ZERO))
    prevu = {}
    for j in restants:
        base = moy.get(j.weekday(), moy_avant.get(j.weekday(), ZERO))
        deja = par_jour.get(j, ZERO) if j == aujourd_hui else ZERO
        prevu[j] = max(deja, base)  # la journée en cours compte au moins ce qui est déjà vendu
    projection = sum((par_jour.get(j, ZERO) for j in passes), ZERO) + sum(prevu.values(), ZERO)
    reste = objectif - sum((par_jour.get(j, ZERO) for j in passes), ZERO)
    requis = reste / len(restants) if restants else ZERO
    moyenne_jour = sum((par_jour.get(j, ZERO) for j in passes), ZERO) / len(passes) if passes else ZERO
    atteinte = _pc(realise, objectif) if objectif else ZERO
    atteinte_proj = _pc(projection, objectif) if objectif else ZERO
    r = RapportGestion()
    r.cartes = [("Objectif", "$", _d(objectif)), ("Réalisé", "$", _d(realise)), ("Atteinte de l'objectif", "%", atteinte),
                ("Projection de fin de période", "$", _d(projection)), ("Atteinte projetée", "%", atteinte_proj),
                ("Moyenne par jour", "$", _d(moyenne_jour)),
                ("À faire par jour restant", "$", _d(max(ZERO, requis)) if restants else ZERO),
                ("Jours restants", "n", len(restants))]
    # objectif cumulé : réparti comme les ventes de la comparaison jour de la semaine par jour de la semaine
    poids = [moy_avant.get(j.weekday(), ZERO) for j in jours]
    somme_poids = sum(poids, ZERO)
    lignes, cumul, cumul_obj, serie, serie_obj = [], ZERO, ZERO, [], []
    for j, w in zip(jours, poids):
        part = objectif * w / somme_poids if somme_poids else objectif / len(jours)
        valeur = par_jour.get(j, ZERO) if j < aujourd_hui else prevu.get(j, ZERO)
        cumul += valeur
        cumul_obj += part
        serie.append(_d(cumul))
        serie_obj.append(_d(cumul_obj))
        etat = ("Réalisé" if j < aujourd_hui else "En cours (projection)" if j == aujourd_hui else "Projection")
        lignes.append([j.isoformat(), _t(JOURS[j.weekday()]), _t(etat), _d(valeur), _d(part), _d(cumul),
                       _d(cumul_obj), _d(cumul - cumul_obj)])
    r.entetes = ["Date", "Jour", "État", "Ventes nettes", "Objectif du jour", "Ventes cumulées", "Objectif cumulé",
                 "Écart cumulé"]
    r.lignes = lignes
    r.titre_evolution = "Ventes cumulées (réalisé puis projection) et objectif"
    r.etiquettes = [_etiquette(j) for j in jours]
    r.series = [("Réalisé et projection", serie), ("Objectif", serie_obj)]
    r.titre_repartition = "Ventes moyennes par jour de la semaine"
    r.genre_repartition = "classement"
    r.repartition = [(_t(JOURS[k]), _d(v)) for k, v in sorted((moy or moy_avant).items(), key=lambda kv: -kv[1])]
    constats = [_k(None, "Objectif : {s} ({v}). Projection : jours restants estimés par la moyenne du même jour de la "
                   "semaine déjà vu dans la période (sinon dans la comparaison).", s=_t(source), v=_argent(objectif))]
    if not restants:
        constats.append(_k("bon" if atteinte >= 100 else "alerte" if atteinte < 95 else "attention",
                           "Période terminée : objectif atteint à {p} % ({r} sur {o}).", p=_nb(atteinte),
                           r=_argent(realise), o=_argent(objectif)))
    elif objectif:
        constats.append(_k("bon" if atteinte_proj >= 100 else "alerte" if atteinte_proj < 95 else "attention",
                           "Au rythme actuel, la période finirait à {v}, soit {p} % de l'objectif.",
                           v=_argent(projection), p=_nb(atteinte_proj)))
        if requis > moyenne_jour and moyenne_jour:
            constats.append(_k("attention", "Il faut {r} par jour sur les {n} jour(s) restant(s), contre {m} en "
                                            "moyenne jusqu'ici (+{p} %).", r=_argent(requis), n=len(restants),
                               m=_argent(moyenne_jour), p=_nb(_pc(requis - moyenne_jour, moyenne_jour))))
        elif restants:
            constats.append(_k("bon", "Il suffit de {r} par jour sur les {n} jour(s) restant(s) ({m} en moyenne "
                                      "jusqu'ici).", r=_argent(max(ZERO, requis)), n=len(restants),
                               m=_argent(moyenne_jour)))
    r.note = _note(constats)
    return r


# --------------------------------------------------------------------------------------------- remboursements
def remboursements(c, avant, ctx) -> RapportGestion:
    """Remboursements de la période : montant, part des ventes, articles et employés qui remboursent le plus,
    commandes remboursées (un clic ouvre la facture Clover), comparés à la période d'avant."""
    def total(cmds):
        remb = -sum((l.remboursements for x in cmds for l in x.lignes), ZERO)
        brut = sum((l.ventes_brutes for x in cmds for l in x.lignes), ZERO)
        return remb, brut

    remb, brut = total(c)
    remb0, brut0 = total(avant)
    taux, taux0 = (_pc(remb, brut, "0.01") if brut else ZERO), (_pc(remb0, brut0, "0.01") if brut0 else ZERO)
    articles = defaultdict(lambda: [ZERO, set(), ZERO])
    employes_ = defaultdict(lambda: [ZERO, set(), ZERO])
    par_jour, commandes = defaultdict(Decimal), []
    for x in c:
        r_cmd = ZERO
        for l in x.lignes:
            articles[l.nom][2] += l.ventes_brutes
            employes_[x.employe][2] += l.ventes_brutes
            if l.remboursements:
                articles[l.nom][0] -= l.remboursements
                articles[l.nom][1].add(x.id)
                employes_[x.employe][0] -= l.remboursements
                employes_[x.employe][1].add(x.id)
                r_cmd -= l.remboursements
        if r_cmd:
            par_jour[x.moment.date()] += r_cmd
            commandes.append((x, r_cmd, sum((l.ventes_brutes for l in x.lignes), ZERO)))
    r = RapportGestion()
    r.cartes = [("Montant remboursé", "$", _d(remb)), ("Commandes remboursées", "n", len(commandes)),
                ("Part des ventes remboursée", "%", taux), ("Part remboursée la période d'avant", "%", taux0),
                ("Montant remboursé la période d'avant", "$", _d(remb0))]
    lignes, ids = [], []
    for nom, (m, cmds, b) in sorted(articles.items(), key=lambda kv: -kv[1][0]):
        if m:
            lignes.append([_t("Article"), nom, _d(m), len(cmds), _d(b), _pc(m, b, "0.1") if b else None])
            ids.append("")
    for nom, (m, cmds, b) in sorted(employes_.items(), key=lambda kv: -kv[1][0]):
        if m:
            lignes.append([_t("Employé"), nom, _d(m), len(cmds), _d(b), _pc(m, b, "0.1") if b else None])
            ids.append("")
    for x, m, b in sorted(commandes, key=lambda t_: -t_[1])[:100]:
        lignes.append([_t("Commande"), f"{x.numero} ({x.moment:%Y-%m-%d %H:%M}, {x.employe})", _d(m), 1, _d(b),
                       _pc(m, b, "0.1") if b else None])
        ids.append(x.id)
    r.entetes = ["Niveau", "Concerné", "Montant remboursé", "Commandes", "Ventes brutes", "Part remboursée %"]
    r.lignes, r.ids_commandes = lignes, ids
    jours = _jours(ctx["du"], ctx["au"])
    r.titre_evolution = "Montant remboursé par jour"
    r.genre_evolution = "barres"
    r.etiquettes = [_etiquette(j) for j in jours]
    r.series = [("Montant remboursé", [_d(par_jour.get(j, ZERO)) for j in jours])]
    r.titre_repartition = "Articles les plus remboursés"
    r.genre_repartition = "classement"
    r.repartition = [(n, _d(v[0])) for n, v in sorted(articles.items(), key=lambda kv: -kv[1][0])[:8] if v[0]]
    constats = []
    if not remb:
        constats.append(_k("bon", "Aucun remboursement dans la période."))
    else:
        constats.append(_k("bon" if taux <= max(taux0, Decimal(1)) else "attention",
                           "{v} remboursés sur {n} commande(s), soit {p} % des ventes (période d'avant : {q} %).",
                           v=_argent(remb), n=len(commandes), p=_nb(taux, 2), q=_nb(taux0, 2)))
        moyen = taux
        for nom, (m, cmds, b) in employes_.items():
            if b and len(cmds) >= 3 and moyen and _pc(m, b, "0.01") > moyen * 2:
                constats.append(_k("attention", "{n} rembourse {p} % de ses ventes, plus du double de la moyenne "
                                                "({m} %).", n=nom, p=_nb(_pc(m, b, "0.01"), 2), m=_nb(moyen, 2)))
        premier = max(articles.items(), key=lambda kv: kv[1][0])
        constats.append(_k(None, "Article le plus remboursé : {a} ({v}).", a=premier[0], v=_argent(premier[1][0])))
    r.note = _note(constats)
    return r


# --------------------------------------------------------------------------------------------- espèces et cartes
def _genre_paiement(modes: str) -> str:
    noms = [m.strip().casefold() for m in (modes or "").split(",") if m.strip()]
    especes = [m for m in noms if "esp" in m or "cash" in m]
    if especes and len(especes) == len(noms):
        return "Espèces"
    if especes:
        return "Espèces et carte"
    return "Carte ou autre" if noms else "Inconnu"


def especes(c, avant, ctx) -> RapportGestion:
    """Part des ventes payées en espèces et par carte, jour par jour, heure par heure et selon le jour de la semaine :
    savoir quand l'argent comptant arrive (dépôts, fond de caisse) et si l'usage des espèces baisse."""
    def part(cmds):
        cash = sum((x.encaisse for x in cmds if _genre_paiement(x.modes) == "Espèces"), ZERO)
        tout = sum((x.encaisse for x in cmds), ZERO)
        return cash, tout

    cash, tout = part(c)
    cash0, tout0 = part(avant)
    p1, p0 = (_pc(cash, tout) if tout else ZERO), (_pc(cash0, tout0) if tout0 else ZERO)
    n_cash = [x for x in c if _genre_paiement(x.modes) == "Espèces"]
    n_carte = [x for x in c if _genre_paiement(x.modes) == "Carte ou autre"]
    jours = _jours(ctx["du"], ctx["au"])
    par_jour = defaultdict(lambda: defaultdict(Decimal))
    par_heure, par_jds, modes = defaultdict(lambda: [ZERO, ZERO]), defaultdict(list), defaultdict(Decimal)
    for x in c:
        g = _genre_paiement(x.modes)
        par_jour[x.moment.date()][g] += x.encaisse
        par_jour[x.moment.date()]["n"] += g == "Espèces"
        par_heure[x.moment.hour][0 if g == "Espèces" else 1] += x.encaisse
        for m in (x.modes or "?").split(","):
            modes[m.strip() or "?"] += x.encaisse / max(1, len((x.modes or "?").split(",")))
    lignes = []
    for j in jours:
        v = par_jour.get(j, {})
        e_, c_, m_ = v.get("Espèces", ZERO), v.get("Carte ou autre", ZERO), v.get("Espèces et carte", ZERO)
        jour_tout = e_ + c_ + m_ + v.get("Inconnu", ZERO)
        if jour_tout:
            par_jds[j.weekday()].append(e_)
        lignes.append([j.isoformat(), _t(JOURS[j.weekday()]), _d(e_), _d(c_), _d(m_),
                       _pc(e_, jour_tout) if jour_tout else None, int(v.get("n", 0))])
    r = RapportGestion()
    r.cartes = [("Payé en espèces", "$", _d(cash)), ("Part des espèces", "%", p1),
                ("Part des espèces la période d'avant", "%", p0),
                ("Panier moyen en espèces", "$", _d(sum((x.encaisse for x in n_cash), ZERO) / len(n_cash))
                 if n_cash else ZERO),
                ("Panier moyen par carte", "$", _d(sum((x.encaisse for x in n_carte), ZERO) / len(n_carte))
                 if n_carte else ZERO),
                ("Commandes payées en espèces", "n", len(n_cash))]
    r.entetes = ["Date", "Jour", "Espèces", "Carte ou autre", "Espèces et carte", "Part des espèces %",
                 "Commandes en espèces"]
    r.lignes = list(reversed(lignes))
    r.titre_evolution = "Espèces et cartes par jour"
    r.etiquettes = [_etiquette(j) for j in jours]
    r.series = [("Espèces", [l[2] for l in lignes]), ("Carte ou autre", [l[3] for l in lignes])]
    r.titre_repartition = "Montant encaissé par mode de paiement"
    r.repartition = [(n, _d(v)) for n, v in sorted(modes.items(), key=lambda kv: -kv[1])]
    r.heures_especes = {h: v for h, v in par_heure.items()}
    r.jds_especes = {k: sum(v, ZERO) / len(v) for k, v in par_jds.items()}
    constats = []
    if tout:
        constats.append(_k("info", "{p} % de l'argent encaissé arrive en espèces ({v}) ; période d'avant : {q} %.",
                           p=_nb(p1), v=_argent(cash), q=_nb(p0)))
        if r.jds_especes:
            fort = max(r.jds_especes, key=r.jds_especes.get)
            constats.append(_k(None, "Les espèces arrivent surtout le {j} ({v} en moyenne) : prévoir le fond de caisse et "
                                     "le dépôt en conséquence.", j=_t(JOURS[fort]), v=_argent(_d(r.jds_especes[fort]))))
        if n_cash and n_carte:
            pc_, pk = (sum((x.encaisse for x in n_cash), ZERO) / len(n_cash),
                       sum((x.encaisse for x in n_carte), ZERO) / len(n_carte))
            constats.append(_k(None, "Panier moyen : {a} en espèces contre {b} par carte.", a=_argent(_d(pc_)),
                               b=_argent(_d(pk))))
    else:
        constats.append(_k(None, "Aucun paiement lu pour la période."))
    r.note = _note(constats)
    return r


# --------------------------------------------------------------------------------------------- nouveaux articles
def nouveaux_articles(c, avant, ctx) -> RapportGestion:
    """Articles vendus dans la période mais pas dans la période d'avant (nouveaux ou revenus) : première vente, ventes
    par jour depuis, rang parmi tous les articles et démarrage (bon, moyen, lent) comparé à un article habituel."""
    avant_ids = {l.id_article or l.nom for x in avant for l in x.lignes}
    # période d'avant sans ventes ou presque (ex. « Cette année » : Clover commence en 2026) : les articles vendus dans les 4
    # premières semaines de la période servent de référence
    jours_avant, jours_c = {x.moment.date() for x in avant}, {x.moment.date() for x in c}
    debut_seul = not avant_ids or len(jours_avant) < len(jours_c) / 4  # période d'avant presque vide
    if debut_seul:
        limite = ctx["du"] + timedelta(days=27)
        avant_ids = {l.id_article or l.nom for x in c if x.moment.date() <= limite for l in x.lignes}
    au = min(ctx["au"], date.today())
    tous = defaultdict(lambda: {"nom": "", "cat": "", "qte": ZERO, "nettes": ZERO, "premier": None, "cmds": set(),
                                "jours": defaultdict(Decimal)})
    for x in c:
        j = x.moment.date()
        for l in x.lignes:
            a = tous[l.id_article or l.nom]
            a["nom"], a["cat"] = l.nom, l.categorie
            a["qte"] += l.quantite_nette
            a["nettes"] += l.ventes_nettes
            a["cmds"].add(x.id)
            a["jours"][j] += l.ventes_nettes
            a["premier"] = j if a["premier"] is None or j < a["premier"] else a["premier"]
    jours_periode = max(1, (au - ctx["du"]).days + 1)
    habituels = sorted(float(a["nettes"]) / jours_periode for k, a in tous.items() if k in avant_ids)
    reference = _quantile(habituels, 0.5) if habituels else 0.0
    rangs = {k: i + 1 for i, (k, _a) in enumerate(sorted(tous.items(), key=lambda kv: -kv[1]["nettes"]))}
    total = sum((a["nettes"] for a in tous.values()), ZERO)
    lignes, par_jour = [], defaultdict(Decimal)
    compte = Counter()
    for k, a in sorted(tous.items(), key=lambda kv: -kv[1]["nettes"]):
        if k in avant_ids:
            continue
        jours_en_vente = max(1, (au - a["premier"]).days + 1)
        par_j = a["nettes"] / jours_en_vente
        if reference and float(par_j) >= reference:
            demarrage = "Bon départ"
        elif reference and float(par_j) < reference / 4:
            demarrage = "Démarrage lent"
        else:
            demarrage = "Départ moyen"
        compte[demarrage] += 1
        for j, v in a["jours"].items():
            par_jour[j] += v
        lignes.append([a["nom"], a["cat"], a["premier"].isoformat(), jours_en_vente, _d(a["qte"], "0.001"),
                       _d(a["nettes"]), _d(par_j), len(a["cmds"]), f"{rangs[k]} / {len(tous)}", _t(demarrage)])
    ventes_n = sum((l[5] for l in lignes), ZERO)
    r = RapportGestion()
    r.entetes = ["Article", "Catégorie", "Première vente", "Jours en vente", "Quantité nette", "Ventes nettes",
                 "Ventes par jour", "Commandes", "Rang parmi tous les articles", "Démarrage"]
    r.lignes = lignes
    r.cartes = [("Nouveaux articles", "n", len(lignes)), ("Ventes des nouveaux articles", "$", _d(ventes_n)),
                ("Part des ventes", "%", _pc(ventes_n, total) if total else ZERO),
                ("Bons départs", "n", compte["Bon départ"]), ("Démarrages lents", "n", compte["Démarrage lent"])]
    jours = _jours(ctx["du"], ctx["au"])
    r.titre_evolution = "Ventes des nouveaux articles par jour"
    r.genre_evolution = "barres"
    r.etiquettes = [_etiquette(j) for j in jours]
    r.series = [("Ventes nettes", [_d(par_jour.get(j, ZERO)) for j in jours])]
    r.titre_repartition = "Nouveaux articles qui vendent le plus"
    r.genre_repartition = "classement"
    r.repartition = [(l[0], l[5]) for l in lignes[:8]]
    constats = [_k(None, "Nouvel article : vendu dans la période mais pas dans la période d'avant (article nouveau ou "
                   "revenu). Démarrage comparé à un article habituel ({v} de ventes par jour) : bon départ = autant "
                   "ou plus, lent = moins du quart.", v=_argent(_d(reference)))]
    if debut_seul:
        constats.append(_k(None, "Trop peu de ventes dans la période d'avant : un nouvel article est ici un article qui ne "
                                 "s'est pas vendu pendant les 4 premières semaines de la période."))
    if lignes:
        constats.append(_k("info", "{n} nouvel(aux) article(s) : {v} de ventes, {p} % du total.", n=len(lignes),
                           v=_argent(ventes_n), p=_nb(_pc(ventes_n, total) if total else 0)))
        meilleur = max(lignes, key=lambda l: l[6])
        constats.append(_k("bon", "Meilleur départ : {a} ({v} par jour, rang {r}).", a=meilleur[0],
                           v=_argent(meilleur[6]), r=meilleur[8]))
        if compte["Démarrage lent"]:
            constats.append(_k("attention", "{n} nouvel(aux) article(s) démarrent lentement : mieux les exposer, les "
                                            "faire goûter, ou ne pas les recommander.", n=compte["Démarrage lent"]))
    else:
        constats.append(_k(None, "Aucun nouvel article dans la période."))
    r.note = _note(constats)
    return r


# --------------------------------------------------------------------------------------------- jours fériés
def _feries(du: date, au: date) -> list[tuple[date, str]]:
    from .conges import jours_feries

    vus = {}
    for annee in range(du.year, au.year + 1):
        for choix in ("vendredi", "lundi"):  # Vendredi saint et lundi de Pâques : les deux comptent pour un marché
            for j, nom in jours_feries(annee, choix):
                vus[j] = nom
    return sorted((j, n) for j, n in vus.items() if du <= j <= au)


def feries(c, avant, ctx) -> RapportGestion:
    """Ventes des jours fériés et de leur veille, comparées à un jour normal du même jour de la semaine (moyenne des
    autres jours ouverts de la période et de la période d'avant) : prévoir le personnel et le stock."""
    par_jour, cmds = defaultdict(Decimal), Counter()
    for x in list(c) + list(avant):
        par_jour[x.moment.date()] += x.nettes
        cmds[x.moment.date()] += 1
    feries_ = _feries(ctx["du"], ctx["au"])
    speciaux = {j for j, _n in feries_} | {j - timedelta(days=1) for j, _n in feries_}
    normaux = defaultdict(list)
    for j, v in par_jour.items():
        if j not in speciaux and v > 0:
            normaux[j.weekday()].append(v)
    normal = {k: sum(v, ZERO) / len(v) for k, v in normaux.items()}

    def ecart(j):
        base = normal.get(j.weekday())
        return _pc(par_jour.get(j, ZERO) - base, base) if base else None

    lignes, effets, effets_veille = [], [], []
    for j, nom in feries_:
        veille = j - timedelta(days=1)
        e_j, e_v = ecart(j), ecart(veille)
        if j <= date.today():
            if e_j is not None:
                effets.append(e_j)
            if e_v is not None:
                effets_veille.append(e_v)
        lignes.append([j.isoformat(), _t(nom), _t(JOURS[j.weekday()]),
                       _d(par_jour.get(j, ZERO)) if j <= date.today() else None,
                       _d(normal.get(j.weekday(), ZERO)), e_j if j <= date.today() else None, cmds.get(j, 0),
                       _d(par_jour.get(veille, ZERO)) if veille <= date.today() else None,
                       e_v if veille <= date.today() else None])
    r = RapportGestion()
    r.entetes = ["Date", "Jour férié", "Jour", "Ventes nettes", "Jour normal (même jour de la semaine)", "Écart %",
                 "Commandes", "Veille : ventes nettes", "Veille : écart %"]
    r.lignes = lignes
    moyen = sum(effets, ZERO) / len(effets) if effets else None
    moyen_v = sum(effets_veille, ZERO) / len(effets_veille) if effets_veille else None
    r.cartes = [("Jours fériés dans la période", "n", len(feries_)),
                ("Effet moyen d'un jour férié", "%", _d(moyen, "0.1") if moyen is not None else ZERO),
                ("Effet moyen de la veille", "%", _d(moyen_v, "0.1") if moyen_v is not None else ZERO)]
    r.titre_evolution = "Jours fériés : ventes du jour et d'un jour normal"
    r.genre_evolution = "barres"
    r.etiquettes = [f"{l[0][8:10]}/{l[0][5:7]}" for l in lignes]
    r.series = [("Jour férié", [l[3] or ZERO for l in lignes]), ("Jour normal", [l[4] for l in lignes])]
    r.titre_repartition = "Veilles de jours fériés : ventes de la veille"
    r.genre_repartition = "classement"
    r.repartition = [(f"{l[1]} ({l[0][8:10]}/{l[0][5:7]})", l[7]) for l in lignes if l[7]]
    constats = [_k(None, "Jour normal : moyenne des ventes du même jour de la semaine, hors jours fériés et veilles, "
                   "sur la période et la période d'avant. Choisissez « Cette année » pour voir tous les jours fériés.")]
    if not feries_:
        constats.append(_k(None, "Aucun jour férié dans la période."))
    if moyen is not None:
        constats.append(_k("info", "Un jour férié vend en moyenne {p} % {s} qu'un jour normal.", p=_nb(abs(moyen)),
                           s=_t("de plus") if moyen >= 0 else _t("de moins")))
    if moyen_v is not None:
        constats.append(_k("attention" if moyen_v >= 20 else "info",
                           "La veille d'un jour férié vend en moyenne {p} % {s} qu'un jour normal{c}.",
                           p=_nb(abs(moyen_v)), s=_t("de plus") if moyen_v >= 0 else _t("de moins"),
                           c=_t(" : prévoir du personnel et du stock") if moyen_v >= 20 else ""))
    a_venir = [l for l in lignes if l[3] is None]
    if a_venir:
        constats.append(_k("info", "Prochain jour férié : {n} le {d}.", n=a_venir[0][1], d=a_venir[0][0]))
    r.note = _note(constats)
    return r


# --------------------------------------------------------------------------------------------- taxes et pourboires
def taxes_pourboires(c, avant, ctx) -> RapportGestion:
    """Taxes (TPS + TVQ) perçues par Clover et pourboires : jour par jour, par employé, comparés à la période d'avant ;
    taux de taxe moyen (part des ventes taxables) et pourboire moyen."""
    def somme(cmds, champ):
        return sum((getattr(x, champ) for x in cmds), ZERO)

    taxes, taxes0 = somme(c, "taxes"), somme(avant, "taxes")
    pourb, pourb0 = somme(c, "pourboires"), somme(avant, "pourboires")
    nettes = somme(c, "nettes")
    avec_pourboire = [x for x in c if x.pourboires > 0]
    jours = _jours(ctx["du"], ctx["au"])
    par_jour = defaultdict(lambda: [ZERO, ZERO, ZERO, 0])
    par_employe = defaultdict(lambda: [ZERO, 0, ZERO, 0])
    for x in c:
        j = par_jour[x.moment.date()]
        j[0] += x.nettes
        j[1] += x.taxes
        j[2] += x.pourboires
        j[3] += 1
        e_ = par_employe[x.employe]
        e_[0] += x.pourboires
        e_[1] += x.pourboires > 0
        e_[2] += x.nettes
        e_[3] += 1
    r = RapportGestion()
    r.cartes = [("Taxes perçues", "$", _d(taxes)), ("Taxes perçues la période d'avant", "$", _d(taxes0)),
                ("Taxes en % des ventes", "%", _pc(taxes, nettes, "0.01") if nettes else ZERO),
                ("Pourboires", "$", _d(pourb)), ("Pourboires la période d'avant", "$", _d(pourb0)),
                ("Commandes avec pourboire", "n", len(avec_pourboire)),
                ("Pourboire moyen", "$", _d(pourb / len(avec_pourboire)) if avec_pourboire else ZERO)]
    lignes = []
    for j in reversed(jours):
        v = par_jour.get(j)
        if v:
            lignes.append([j.isoformat(), _t(JOURS[j.weekday()]), _d(v[0]), _d(v[1]),
                           _pc(v[1], v[0], "0.01") if v[0] else None, _d(v[2]), v[3]])
    r.entetes = ["Date", "Jour", "Ventes nettes", "Taxes perçues", "Taxes en % des ventes", "Pourboires",
                 "Commandes"]
    r.lignes = lignes
    r.titre_evolution = "Taxes et pourboires par jour"
    r.genre_evolution = "barres"
    r.etiquettes = [_etiquette(j) for j in jours]
    r.series = [("Taxes perçues", [_d(par_jour[j][1]) if j in par_jour else ZERO for j in jours]),
                ("Pourboires", [_d(par_jour[j][2]) if j in par_jour else ZERO for j in jours])]
    r.titre_repartition = "Pourboires par employé"
    r.genre_repartition = "classement"
    r.repartition = [(n, _d(v[0])) for n, v in sorted(par_employe.items(), key=lambda kv: -kv[1][0]) if v[0]][:8]
    r.pourboires_employes = {n: v for n, v in par_employe.items()}
    constats = [_k("info", "{t} de taxes perçues ({p} % des ventes nettes) ; période d'avant : {u}.", t=_argent(taxes),
                   p=_nb(_pc(taxes, nettes, "0.01") if nettes else 0, 2), u=_argent(taxes0)),
                _k(None, "Les taxes perçues par Clover servent de contrôle à la déclaration de TPS / TVQ "
                         "(Comptabilité > Déclaration TPS/TVQ) ; les taxes de Sage sont calculées sur la facture du jour.")]
    if pourb:
        constats.append(_k("info", "{p} de pourboires sur {n} commande(s), {m} en moyenne.", p=_argent(pourb),
                           n=len(avec_pourboire), m=_argent(_d(pourb / len(avec_pourboire)))))
    else:
        constats.append(_k(None, "Aucun pourboire dans la période."))
    r.note = _note(constats)
    return r


# --------------------------------------------------------------------------------------------- quand on gagne le plus
def gains_horaires(c, avant, ctx) -> RapportGestion:
    """Bénéfice brut (coût moyen de Sage) par jour de la semaine et par heure, en moyenne par jour ouvert ; sans coûts,
    les ventes nettes. Montre les moments qui rapportent le plus et ceux qui rapportent peu."""
    couts = ctx.get("couts") or {}
    ouverts = Counter(j.weekday() for j in {x.moment.date() for x in c})
    gains = defaultdict(lambda: [ZERO, ZERO, 0])  # (jour, heure) -> ventes, bénéfice, commandes
    connus = ZERO
    for x in c:
        g = gains[(x.moment.weekday(), x.moment.hour)]
        g[0] += x.nettes
        g[2] += 1
        for l in x.lignes:
            cout = _cump(couts, l.id_article, l.ventes_brutes / l.quantite_vendue if l.quantite_vendue else 0)
            if cout is not None:
                g[1] += l.ventes_nettes - l.quantite_nette * cout
                connus += l.ventes_nettes
    total = sum((g[0] for g in gains.values()), ZERO)
    avec_couts = bool(couts) and total and connus / total >= Decimal("0.5")
    mesure = "Bénéfice brut" if avec_couts else "Ventes nettes"
    lignes = []
    for (jds, h), (v, b, n) in sorted(gains.items()):
        jours_o = max(1, ouverts[jds])
        valeur = b if avec_couts else v
        lignes.append([_t(JOURS[jds]), f"{h} h", _d(v / jours_o), _d(b / jours_o) if avec_couts else None,
                       _pc(b, v) if avec_couts and v else None, _d(Decimal(n) / jours_o, "0.1"), _d(valeur / jours_o)])
    r = RapportGestion()
    r.entetes = ["Jour", "Heure", "Ventes nettes par jour", "Bénéfice brut par jour", "Marge %", "Commandes par jour",
                 "Rapporte par jour"]
    r.lignes = lignes
    meilleur = max(lignes, key=lambda l: l[6]) if lignes else None
    par_jds = defaultdict(Decimal)
    for (jds, _h), (v, b, _n) in gains.items():
        par_jds[jds] += (b if avec_couts else v) / max(1, ouverts[jds])
    heures = sorted({h for _j, h in gains})
    par_h = defaultdict(Decimal)
    jours_total = max(1, sum(ouverts.values()))
    for (_j, h), (v, b, _n) in gains.items():
        par_h[h] += (b if avec_couts else v) / jours_total
    r.cartes = [("Mesure", "t", _t(mesure)),
                ("Moment qui rapporte le plus", "t", f"{meilleur[0]} {meilleur[1]}" if meilleur else "—"),
                ("Jour qui rapporte le plus", "t", _t(JOURS[max(par_jds, key=par_jds.get)]) if par_jds else "—"),
                ("Heure qui rapporte le plus", "t", f"{max(par_h, key=par_h.get)} h" if par_h else "—")]
    r.titre_evolution = ("Bénéfice brut moyen selon l'heure" if avec_couts else "Ventes nettes moyennes selon l'heure")
    r.genre_evolution = "barres"
    r.etiquettes = [f"{h} h" for h in heures]
    r.series = [(_t(mesure), [_d(par_h[h]) for h in heures])]
    r.titre_repartition = ("Bénéfice brut moyen selon le jour" if avec_couts else "Ventes nettes moyennes selon le jour")
    r.genre_repartition = "classement"
    r.repartition = [(_t(JOURS[k]), _d(par_jds[k])) for k in sorted(par_jds, key=lambda k: -par_jds[k])]
    constats = [_k(None, "Moyenne par jour ouvert de chaque jour de la semaine ; « rapporte » = bénéfice brut au coût "
                   "moyen de Sage quand au moins la moitié des ventes a un coût connu, sinon les ventes nettes.")]
    if meilleur:
        constats.append(_k("bon", "Le moment qui rapporte le plus : {j} {h} ({v} en moyenne).", j=meilleur[0],
                           h=meilleur[1], v=_argent(meilleur[6])))
        faibles = [l for l in lignes if l[6] < meilleur[6] / 10]
        if faibles:
            constats.append(_k("info", "{n} moment(s) rapportent moins du dixième du meilleur : {c}.", n=len(faibles),
                               c=", ".join(f"{l[0]} {l[1]}" for l in sorted(faibles, key=lambda l: l[6])[:6])))
    r.note = _note(constats)
    return r


# --------------------------------------------------------------------------------------------- articles qui baissent
def articles_baisse(c, avant, ctx) -> RapportGestion:
    """Articles importants (les 20 % qui vendent le plus) dont les ventes baissent semaine après semaine : pente de
    la droite des ventes hebdomadaires, comparée à la moyenne. Il faut au moins 4 semaines."""
    du, au = ctx["du"], min(ctx["au"], date.today())
    # blocs de 7 jours comptés depuis la fin de la période (un mois en compte 4, même s'il commence un mercredi)
    semaines = []
    debut_bloc = au - timedelta(days=6)
    while debut_bloc >= du:
        semaines.insert(0, debut_bloc)
        debut_bloc -= timedelta(days=7)
    semaines_art = defaultdict(lambda: defaultdict(Decimal))
    cats, totaux = {}, defaultdict(Decimal)
    for x in c:
        j = x.moment.date()
        bloc = next((b for b in reversed(semaines) if b <= j), None)
        for l in x.lignes:
            if bloc is not None:
                semaines_art[l.nom][bloc] += l.ventes_nettes
            cats[l.nom] = l.categorie
            totaux[l.nom] += l.ventes_nettes
    ordre = sorted(totaux, key=lambda n: -totaux[n])
    importants = ordre[:max(1, math.ceil(len(ordre) * PART_A))]
    lignes = []
    if len(semaines) >= 4:
        xs = list(range(len(semaines)))
        mx = st.mean(xs)
        sxx = sum((x_ - mx) ** 2 for x_ in xs)
        for nom in importants:
            ys = [float(semaines_art[nom].get(s_, ZERO)) for s_ in semaines]
            moy = st.mean(ys)
            # article vendu régulièrement (presque chaque semaine, 25 $ par semaine en moyenne) : une vente isolée
            # n'est pas une baisse
            if moy < 25 or sum(1 for y in ys if y > 0) < len(ys) - 1:
                continue
            pente = sum((x_ - mx) * (y - moy) for x_, y in zip(xs, ys)) / sxx
            baisse = max(-100.0, pente / moy * 100)  # % de la moyenne perdu chaque semaine
            debut, fin = st.mean(ys[:2]), st.mean(ys[-2:])
            if baisse <= -5 and fin < debut:
                lignes.append([nom, cats.get(nom, ""), _d(totaux[nom]), _d(debut), _d(fin), _d(baisse, "0.1"),
                               _d(pente), _t("Forte baisse") if baisse <= -15 else _t("Baisse")])
    lignes.sort(key=lambda l: l[5])
    r = RapportGestion()
    r.entetes = ["Article", "Catégorie", "Ventes nettes", "Ventes par semaine au début", "Ventes par semaine à la fin",
                 "Baisse par semaine %", "Baisse par semaine", "Niveau"]
    r.lignes = lignes
    r.cartes = [("Articles importants suivis", "n", len(importants)), ("Articles qui baissent", "n", len(lignes)),
                ("Fortes baisses", "n", sum(1 for l in lignes if l[7] == _t("Forte baisse"))),
                ("Semaines comparées", "n", len(semaines))]
    r.titre_evolution = "Ventes par semaine des articles qui baissent le plus"
    r.etiquettes = [_etiquette(s_) for s_ in semaines]
    r.series = [(l[0], [_d(semaines_art[l[0]].get(s_, ZERO)) for s_ in semaines]) for l in lignes[:4]]
    r.titre_repartition = "Baisse par semaine (en % des ventes moyennes)"
    r.genre_repartition = "classement"
    r.argent_repartition = False
    r.repartition = [(l[0], abs(l[5])) for l in lignes[:8]]
    constats = [_k(None, "Articles importants : les 20 % qui vendent le plus dans la période, vendus presque chaque "
                   "semaine (25 $ par semaine au moins). Baisse : la droite des ventes semaine par semaine perd au "
                   "moins 5 % de la moyenne chaque semaine ; forte : 15 % ou plus.")]
    if len(semaines) < 4:
        constats.append(_k(None, "Choisissez au moins 4 semaines (par exemple « 30 derniers jours » ou un mois)."))
    elif lignes:
        constats.append(_k("attention", "{n} article(s) important(s) baissent semaine après semaine ; le plus touché : "
                                        "{a} ({p} % par semaine).", n=len(lignes), a=lignes[0][0],
                           p=_nb(abs(lignes[0][5]))))
    else:
        constats.append(_k("bon", "Aucun article important ne baisse de façon régulière."))
    r.note = _note(constats)
    return r


# --------------------------------------------------------------------------------------------- catégories selon le jour
def categories_jour(c, avant, ctx) -> RapportGestion:
    """Ventes moyennes de chaque catégorie selon le jour de la semaine (par jour ouvert) : commander et préparer le
    bon stock pour le bon jour (produits frais surtout)."""
    ouverts = Counter(j.weekday() for j in {x.moment.date() for x in c})
    cat_jds = defaultdict(lambda: defaultdict(Decimal))
    totaux = defaultdict(Decimal)
    for x in c:
        k = x.moment.weekday()
        for l in x.lignes:
            cat_jds[l.categorie][k] += l.ventes_nettes
            totaux[l.categorie] += l.ventes_nettes
    jds = [k for k in range(7) if ouverts[k]]
    lignes = []
    for cat in sorted(totaux, key=lambda n: -totaux[n]):
        moyennes = [cat_jds[cat][k] / ouverts[k] for k in jds]
        moyenne = sum(moyennes, ZERO) / len(moyennes) if moyennes else ZERO
        fort = jds[max(range(len(jds)), key=lambda i: moyennes[i])] if jds else 0
        lignes.append([cat] + [_d(v) for v in moyennes] + [_t(JOURS[fort]),
                                                            _d(moyennes[jds.index(fort)] / moyenne * 100, "1")
                                                            if moyenne else None])
    r = RapportGestion()
    r.entetes = ["Catégorie"] + [_t(JOURS[k]) for k in jds] + ["Meilleur jour", "Indice du meilleur jour (100 = moyenne)"]
    r.lignes = lignes
    r.cartes = [("Catégories", "n", len(lignes)), ("Jours ouverts dans la période", "n", sum(ouverts.values()))]
    r.titre_evolution = "Ventes moyennes des principales catégories selon le jour"
    r.genre_evolution = "barres"
    r.etiquettes = [_t(JOURS[k]) for k in jds]
    r.series = [(l[0], l[1:1 + len(jds)]) for l in lignes[:4]]
    r.titre_repartition = "Catégories les plus liées à un jour (indice du meilleur jour)"
    r.genre_repartition = "classement"
    r.argent_repartition = False
    r.repartition = [(f"{l[0]} ({l[-2]})", l[-1]) for l in sorted(lignes[:20], key=lambda l: -(l[-1] or 0))[:8]
                     if l[-1]]
    constats = [_k(None, "Ventes moyennes par jour ouvert de chaque jour de la semaine ; indice = meilleur jour / jour "
                   "moyen × 100 (200 = deux fois plus ce jour-là).")]
    marques = [l for l in lignes[:20] if (l[-1] or 0) >= 150]
    for l in marques[:5]:
        constats.append(_k("info", "{c} se vend surtout le {j} (indice {i}) : prévoir plus de stock la veille.",
                           c=l[0], j=l[-2], i=_nb(l[-1], 0)))
    r.note = _note(constats)
    return r


# --------------------------------------------------------------------------------------------- achalandage prévu
def achalandage_prevu(c, avant, ctx) -> RapportGestion:
    """Commandes attendues la semaine prochaine, par jour et par heure : moyenne des 4 dernières semaines (période
    choisie et période d'avant), et employés conseillés pour garder la charge habituelle par employé."""
    toutes = list(c) + list(avant)
    if not toutes:
        r = RapportGestion(note=_note([_k(None, "Aucune vente pour calculer la prévision.")]))
        r.cartes = [("Commandes prévues la semaine prochaine", "n", 0)]
        r.entetes = ["Jour", "Heure", "Commandes prévues", "Employés conseillés"]
        return r
    fin = max(x.moment.date() for x in toutes)
    debut = fin - timedelta(days=27)
    recentes = [x for x in toutes if debut <= x.moment.date() <= fin]
    jours_vus = Counter(j.weekday() for j in {x.moment.date() for x in recentes})
    creneaux = defaultdict(int)
    presences = defaultdict(set)
    for x in recentes:
        k = (x.moment.weekday(), x.moment.hour)
        creneaux[k] += 1
        presences[(x.moment.date(), x.moment.hour)].add(x.employe)
    # charge habituelle d'un employé : médiane des commandes par employé actif et par heure
    charges = []
    for (j, h), emp in presences.items():
        n = sum(1 for x in recentes if x.moment.date() == j and x.moment.hour == h)
        charges.append(n / max(1, len(emp)))
    charge = max(1.0, _quantile(charges, 0.5))
    lundi = fin + timedelta(days=7 - fin.weekday())
    lignes, par_jour = [], defaultdict(Decimal)
    for (jds, h), n in sorted(creneaux.items()):
        prevu = Decimal(n) / max(1, jours_vus[jds])
        employes_ = max(1, math.ceil(float(prevu) / charge))
        jour = lundi + timedelta(days=jds)
        par_jour[jour] += prevu
        lignes.append([f"{jour.isoformat()} ({_t(JOURS[jds])})", f"{h} h", _d(prevu, "0.1"), employes_])
    r = RapportGestion()
    r.entetes = ["Jour", "Heure", "Commandes prévues", "Employés conseillés"]
    r.lignes = lignes
    total = sum(par_jour.values(), ZERO)
    pointe = max(lignes, key=lambda l: l[2]) if lignes else None
    r.cartes = [("Commandes prévues la semaine prochaine", "n", _d(total, "1")),
                ("Charge habituelle d'un employé (commandes par heure)", "n", _d(charge, "0.1")),
                ("Heure la plus chargée prévue", "t", f"{pointe[0]} {pointe[1]}" if pointe else "—"),
                ("Employés au plus fort", "n", max((l[3] for l in lignes), default=0))]
    jours = [lundi + timedelta(days=k) for k in range(7)]
    r.titre_evolution = "Commandes prévues par jour la semaine prochaine"
    r.genre_evolution = "barres"
    r.unite_evolution = ""
    r.etiquettes = [f"{_t(JOURS[j.weekday()])[:3]} {j:%d/%m}" for j in jours]
    r.series = [("Commandes prévues", [_d(par_jour.get(j, ZERO), "0.1") for j in jours])]
    r.titre_repartition = "Heures les plus chargées prévues"
    r.genre_repartition = "classement"
    r.argent_repartition = False
    r.repartition = [(f"{l[0][:10]} {l[1]}", l[2]) for l in sorted(lignes, key=lambda l: -l[2])[:8]]
    constats = [_k(None, "Pour la semaine qui vient, choisissez « 30 derniers jours » ou « Ce mois-ci » : la "
                   "prévision part de la fin de la période choisie."),
                _k(None, "Prévision : moyenne des commandes du même jour et de la même heure sur les 4 dernières "
                   "semaines ({d} au {f}). Employés conseillés : commandes prévues / charge habituelle d'un employé "
                   "({c} commandes par heure), arrondi au-dessus.", d=debut, f=fin, c=_nb(charge))]
    if pointe:
        constats.append(_k("info", "Semaine du {l} : {n} commandes prévues ; plus forte heure : {p} ({v} commandes, "
                                   "{e} employé(s)).", l=lundi, n=_nb(total, 0), p=f"{pointe[0]} {pointe[1]}",
                           v=_nb(pointe[2]), e=pointe[3]))
    r.note = _note(constats)
    return r


# --------------------------------------------------------------------------------------------- valeur des clients
def valeur_clients(c, avant, ctx) -> RapportGestion:
    """Ce que rapporte chaque client identifié : dépense par mois de présence (du premier au dernier achat de la
    période), valeur sur un an au même rythme, visites par mois ; les clients qui valent le plus."""
    clients = defaultdict(lambda: {"cmd": 0, "nettes": ZERO, "premier": None, "dernier": None})
    for x in list(avant) + list(c):
        if x.client == "Sans client":
            continue
        g = clients[x.client]
        j = x.moment.date()
        g["cmd"] += 1
        g["nettes"] += x.nettes
        g["premier"] = min(g["premier"] or j, j)
        g["dernier"] = max(g["dernier"] or j, j)
    fin = min(ctx["au"], date.today())
    lignes = []
    for nom, g in clients.items():
        mois = max(1.0, ((fin - g["premier"]).days + 1) / 30.4)
        par_mois = g["nettes"] / Decimal(str(mois))
        lignes.append([nom, g["cmd"], _d(g["nettes"]), _d(g["nettes"] / g["cmd"]), _d(Decimal(g["cmd"]) /
                                                                                     Decimal(str(mois)), "0.1"),
                       _d(par_mois), _d(par_mois * 12), g["premier"].isoformat(), g["dernier"].isoformat()])
    lignes.sort(key=lambda l: -l[6])
    total_an = sum((l[6] for l in lignes), ZERO)
    r = RapportGestion()
    r.entetes = ["Client", "Commandes", "Ventes nettes", "Panier moyen", "Visites par mois", "Dépense par mois",
                 "Valeur sur un an", "Premier achat", "Dernier achat"]
    r.lignes = lignes
    dix = sum((l[6] for l in lignes[:10]), ZERO)
    r.cartes = [("Clients identifiés", "n", len(lignes)),
                ("Valeur moyenne d'un client sur un an", "$", _d(total_an / len(lignes)) if lignes else ZERO),
                ("Valeur sur un an des 10 meilleurs", "$", _d(dix)),
                ("Part des 10 meilleurs", "%", _pc(dix, total_an) if total_an else ZERO)]
    tranches = [(0, 50), (50, 200), (200, 500), (500, 1000), (1000, None)]
    r.titre_evolution = "Clients selon leur valeur sur un an"
    r.genre_evolution = "barres"
    r.unite_evolution = ""
    r.etiquettes = [f"{a} $ à {b} $" if b else f"{a} $ et plus" for a, b in tranches]
    r.series = [("Clients", [Decimal(sum(1 for l in lignes if l[6] >= a and (b is None or l[6] < b)))
                             for a, b in tranches])]
    r.titre_repartition = "Les clients qui valent le plus (sur un an)"
    r.genre_repartition = "classement"
    r.repartition = [(l[0], l[6]) for l in lignes[:8]]
    constats = [_k(None, "Valeur sur un an = dépense par mois de présence (du premier achat connu à la fin de la "
                   "période, période d'avant comprise) × 12 ; seuls les clients identifiés à la caisse sont comptés.")]
    if lignes:
        constats.append(_k("info", "Les 10 meilleurs clients valent {v} par an, {p} % de la valeur de tous les clients "
                                   "identifiés.", v=_argent(dix), p=_nb(_pc(dix, total_an) if total_an else 0)))
    else:
        constats.append(_k(None, "Aucun client identifié dans la période."))
    r.note = _note(constats)
    return r


# --------------------------------------------------------------------------------------------- seuil de rentabilité
def seuil_rentabilite(c, avant, ctx) -> RapportGestion:
    """Ventes nécessaires pour couvrir les frais du mois (poste « Autres charges » du budget) avec la marge brute
    réelle de la période (coût moyen de Sage) : par mois et par jour ouvert, comparées aux ventes réelles."""
    couts = ctx.get("couts") or {}
    nettes = connues = benefice = ZERO
    par_jour = defaultdict(Decimal)
    for x in c:
        par_jour[x.moment.date()] += x.nettes
        for l in x.lignes:
            nettes += l.ventes_nettes
            cout = _cump(couts, l.id_article, l.ventes_brutes / l.quantite_vendue if l.quantite_vendue else 0)
            if cout is not None:
                connues += l.ventes_nettes
                benefice += l.ventes_nettes - l.quantite_nette * cout
    marge = benefice / connues if connues else None
    du, au = ctx["du"], min(ctx["au"], date.today())
    charges_mois, mois_vus = ZERO, set()
    if ctx.get("racine"):
        try:
            from .budget import POSTES, Budget

            budget = Budget(ctx["racine"])
            for j in _jours(du, au):
                if (j.year, j.month) not in mois_vus:
                    mois_vus.add((j.year, j.month))
                    charges_mois += budget.mois(j.year, j.month).get(POSTES[2], ZERO)
        except Exception:  # noqa: BLE001 — budget illisible
            charges_mois = ZERO
    charges_mois = charges_mois / len(mois_vus) if mois_vus else ZERO
    jours_ouverts = len([j for j, v in par_jour.items() if v > 0])
    ouverts_par_mois = Decimal(jours_ouverts) / max(1, len({(j.year, j.month) for j in par_jour})) if par_jour else 0
    seuil_mois = charges_mois / marge if marge and charges_mois else None
    seuil_jour = seuil_mois / ouverts_par_mois if seuil_mois and ouverts_par_mois else None
    moyenne_jour = sum(par_jour.values(), ZERO) / jours_ouverts if jours_ouverts else ZERO
    r = RapportGestion()
    r.cartes = [("Marge brute réelle", "%", _d(marge * 100, "0.1") if marge is not None else ZERO),
                ("Frais du mois (budget)", "$", _d(charges_mois)),
                ("Ventes nécessaires par mois", "$", _d(seuil_mois) if seuil_mois else ZERO),
                ("Ventes nécessaires par jour ouvert", "$", _d(seuil_jour) if seuil_jour else ZERO),
                ("Ventes moyennes par jour ouvert", "$", _d(moyenne_jour)),
                ("Jours au-dessus du seuil", "n", sum(1 for v in par_jour.values() if seuil_jour and v >= seuil_jour))]
    jours = _jours(du, au)
    r.titre_evolution = "Ventes par jour et ventes nécessaires pour couvrir les frais"
    r.etiquettes = [_etiquette(j) for j in jours]
    r.series = [("Ventes nettes", [_d(par_jour.get(j, ZERO)) for j in jours])]
    if seuil_jour:
        r.series.append(("Ventes nécessaires", [_d(seuil_jour)] * len(jours)))
    r.titre_repartition = "Jours au-dessus et au-dessous du seuil"
    r.genre_repartition = "anneau"
    r.argent_repartition = False
    if seuil_jour:
        dessus = sum(1 for v in par_jour.values() if v >= seuil_jour)
        r.repartition = [(_t("Au-dessus du seuil"), Decimal(dessus)),
                         (_t("Au-dessous du seuil"), Decimal(len(par_jour) - dessus))]
    r.entetes = ["Date", "Jour", "Ventes nettes", "Ventes nécessaires", "Écart", "Couvre les frais"]
    r.lignes = [[j.isoformat(), _t(JOURS[j.weekday()]), _d(par_jour[j]), _d(seuil_jour) if seuil_jour else None,
                 _d(par_jour[j] - seuil_jour) if seuil_jour else None,
                 (_t("Oui") if par_jour[j] >= seuil_jour else _t("Non")) if seuil_jour else "—"]
                for j in sorted(par_jour, reverse=True)]
    constats = [_k(None, "Seuil de rentabilité : ventes dont la marge brute couvre les autres frais du mois (loyer, "
                   "salaires, etc.) saisis dans Comptabilité > Budget et écarts (poste « Autres charges »).")]
    if marge is None:
        constats.append(_k("attention", "Coûts Sage absents : marge inconnue, seuil non calculable."))
    elif not charges_mois:
        constats.append(_k("attention", "Aucun montant « Autres charges » au budget de la période : saisissez-le dans "
                                        "Comptabilité > Budget et écarts pour connaître le seuil."))
    else:
        constats.append(_k("bon" if moyenne_jour >= seuil_jour else "alerte",
                           "Il faut {s} de ventes par jour ouvert pour couvrir {f} de frais par mois avec une marge de "
                           "{m} % ; le magasin fait {v} en moyenne.", s=_argent(_d(seuil_jour)),
                           f=_argent(_d(charges_mois)), m=_nb(marge * 100), v=_argent(_d(moyenne_jour))))
    r.note = _note(constats)
    return r


# --------------------------------------------------------------------------------------------- quantités prévues
def quantites_prevues(c, avant, ctx) -> RapportGestion:
    """Quantités à prévoir pour chaque article important, jour par jour la semaine qui suit la période : moyenne du
    même jour de la semaine sur les 4 dernières semaines. Pour préparer les commandes de produits frais."""
    toutes = list(c) + list(avant)
    r = RapportGestion()
    r.entetes = ["Article", "Catégorie"] + [_t(j) for j in JOURS] + ["Total de la semaine"]
    if not toutes:
        r.note = _note([_k(None, "Aucune vente pour calculer la prévision.")])
        r.cartes = [("Articles prévus", "n", 0)]
        return r
    fin = max(x.moment.date() for x in toutes)
    debut = fin - timedelta(days=27)
    jours_vus = Counter(j.weekday() for j in {x.moment.date() for x in toutes if debut <= x.moment.date() <= fin})
    qte = defaultdict(lambda: defaultdict(Decimal))
    ventes, cats = defaultdict(Decimal), {}
    for x in toutes:
        if not debut <= x.moment.date() <= fin:
            continue
        for l in x.lignes:
            qte[l.nom][x.moment.weekday()] += l.quantite_nette
            ventes[l.nom] += l.ventes_nettes
            cats[l.nom] = l.categorie
    ordre = sorted(ventes, key=lambda n: -ventes[n])
    importants = ordre[:max(1, math.ceil(len(ordre) * PART_A))]
    lignes, par_jour = [], defaultdict(Decimal)
    for nom in importants:
        prevues = [qte[nom][k] / jours_vus[k] if jours_vus[k] else ZERO for k in range(7)]
        for k, v in enumerate(prevues):
            par_jour[k] += v
        lignes.append([nom, cats[nom]] + [_d(v, "0.1") for v in prevues] + [_d(sum(prevues, ZERO), "0.1")])
    lundi = fin + timedelta(days=7 - fin.weekday())
    r.lignes = lignes
    r.cartes = [("Articles prévus", "n", len(lignes)), ("Semaine du", "t", lundi.isoformat()),
                ("Semaines utilisées", "n", 4)]
    r.titre_evolution = "Quantités prévues par jour (articles importants)"
    r.genre_evolution = "barres"
    r.unite_evolution = ""
    r.etiquettes = [_t(j) for j in JOURS]
    r.series = [(_t("Quantités prévues"), [_d(par_jour[k], "0.1") for k in range(7)])]
    r.titre_repartition = "Articles à prévoir en plus grande quantité (semaine)"
    r.genre_repartition = "classement"
    r.argent_repartition = False
    r.repartition = [(l[0], l[-1]) for l in sorted(lignes, key=lambda l: -l[-1])[:8]]
    constats = [_k(None, "Quantité prévue = moyenne vendue le même jour de la semaine sur les 4 semaines du {d} au {f} "
                   "(articles importants : les 20 % qui vendent le plus). Pour la semaine qui vient, choisissez "
                   "« 30 derniers jours ».", d=debut, f=fin),
                _k("info", "Semaine du {l} : quantités prévues pour {n} article(s) ; exportez le tableau pour préparer "
                           "les commandes.", l=lundi, n=len(lignes))]
    r.note = _note(constats)
    return r


# --------------------------------------------------------------------------------------------- jour du mois
TRANCHES_MOIS = [(1, 5, "du 1er au 5"), (6, 10, "du 6 au 10"), (11, 15, "du 11 au 15"), (16, 20, "du 16 au 20"),
                 (21, 25, "du 21 au 25"), (26, 31, "du 26 à la fin du mois")]
JOURS_MOIS_COMPLET = 20     # mois retenu par « Articles de saison » : au moins 20 jours ouverts
MOIS_NOMS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
             "novembre", "décembre"]


def _nom_mois(annee: int, mois: int) -> str:
    return f"{_t(MOIS_NOMS[mois - 1])} {annee}"


def jour_du_mois(c, avant, ctx) -> RapportGestion:
    """Ventes selon le jour du mois (début, milieu, fin : jours de paie et d'allocations), corrigées du jour de la
    semaine : indice 100 = un jour normal du même jour de la semaine (période choisie et période d'avant réunies)."""
    ventes, nb = defaultdict(Decimal), Counter()
    for x in list(c) + list(avant):
        ventes[x.moment.date()] += x.nettes
        nb[x.moment.date()] += 1
    jours = sorted(j for j, v in ventes.items() if v > 0)
    par_jds = defaultdict(list)
    for j in jours:
        par_jds[j.weekday()].append(ventes[j])
    normal = {k: sum(v, ZERO) / len(v) for k, v in par_jds.items()}
    indice = {j: ventes[j] * 100 / normal[j.weekday()] for j in jours if normal.get(j.weekday())}
    lignes = []
    for a, b, nom in TRANCHES_MOIS:
        js = [j for j in jours if a <= j.day <= b and j in indice]
        if not js:
            lignes.append([_t(nom), 0, ZERO, None, ZERO, ZERO])
            continue
        v, n = sum((ventes[j] for j in js), ZERO), sum(nb[j] for j in js)
        lignes.append([_t(nom), len(js), _d(v / len(js)), _d(sum((indice[j] for j in js), ZERO) / len(js), "1"),
                       _d(Decimal(n) / len(js), "0.1"), _d(v / n) if n else ZERO])
    r = RapportGestion()
    r.entetes = ["Jours du mois", "Jours ouverts", "Ventes moyennes par jour", "Indice (100 = jour normal)",
                 "Commandes moyennes par jour", "Panier moyen"]
    r.lignes = lignes
    notees = [l for l in lignes if l[3] is not None]
    fort = max(notees, key=lambda l: l[3]) if notees else None
    faible = min(notees, key=lambda l: l[3]) if notees else None
    r.cartes = [("Jours analysés", "n", len(jours)),
                ("Meilleur moment du mois", "t", fort[0] if fort else "—"),
                ("Indice du meilleur moment", "n", fort[3] if fort else ZERO),
                ("Moment le plus faible du mois", "t", faible[0] if faible else "—"),
                ("Indice du moment le plus faible", "n", faible[3] if faible else ZERO)]
    par_quantieme = defaultdict(list)
    for j, v in indice.items():
        par_quantieme[j.day].append(v)
    quantiemes = sorted(par_quantieme)
    r.titre_evolution = "Indice des ventes selon le jour du mois (100 = jour normal)"
    r.genre_evolution = "barres"
    r.unite_evolution = ""
    r.etiquettes = [str(q) for q in quantiemes]
    r.series = [(_t("Indice (100 = jour normal)"),
                 [_d(sum(par_quantieme[q], ZERO) / len(par_quantieme[q]), "1") for q in quantiemes])]
    r.titre_repartition = "Ventes moyennes par jour selon le moment du mois"
    r.genre_repartition = "classement"
    r.repartition = [(l[0], l[2]) for l in lignes if l[1]]
    constats = [_k(None, "Indice : ventes du jour comparées à un jour normal du même jour de la semaine (100 = normal, "
                   "120 = 20 % de plus) ; la période choisie et la période d'avant sont réunies.")]
    if len(jours) < 40:
        constats.append(_k("info", "Seulement {n} jours analysés : choisissez une période de 2 mois ou plus pour un "
                                   "résultat fiable.", n=len(jours)))
    if fort and fort[3] >= 110:
        constats.append(_k("info", "Les jours {t} du mois vendent {p} % de plus qu'un jour normal : prévoir stock et "
                                   "personnel.", t=fort[0], p=_nb(fort[3] - 100, 0)))
    if faible and faible[3] <= 92:
        constats.append(_k("info", "Les jours {t} du mois vendent {p} % de moins qu'un jour normal : bon moment pour une "
                                   "promotion.", t=faible[0], p=_nb(100 - faible[3], 0)))
    if fort and faible and fort[3] < 110 and faible[3] > 92:
        constats.append(_k("bon", "Ventes régulières tout au long du mois : aucun moment du mois ne s'écarte de plus de "
                                  "10 % d'un jour normal."))
    r.note = _note(constats)
    return r


# --------------------------------------------------------------------------------------------- articles de saison
def articles_saison(c, avant, ctx) -> RapportGestion:
    """Articles dont les ventes changent selon le mois (fruits de saison, fêtes, rentrée) : ventes par jour ouvert de
    chaque mois, mois le plus fort et le plus faible, indice de saison ; articles à préparer pour le mois qui vient."""
    jours_mois = defaultdict(set)
    ventes, cats, total = defaultdict(lambda: defaultdict(Decimal)), {}, defaultdict(Decimal)
    for x in list(c) + list(avant):
        m = (x.moment.year, x.moment.month)
        jours_mois[m].add(x.moment.date())
        for l in x.lignes:
            ventes[l.nom][m] += l.ventes_nettes
            total[l.nom] += l.ventes_nettes
            if l.nom not in cats or (l.categorie and m >= cats[l.nom][0]):  # catégorie des ventes les plus récentes
                cats[l.nom] = (m, l.categorie)
    cats = {n: cat for n, (_m, cat) in cats.items()}
    # mois presque complets seulement (un mois commencé fausserait l'indice)
    mois = sorted(m for m, js in jours_mois.items() if len(js) >= JOURS_MOIS_COMPLET)
    ordre = [n for n in sorted(total, key=lambda n: -total[n]) if total[n] > 0]
    importants = ordre[:max(1, math.ceil(len(ordre) * PART_B))] if ordre else []
    aujourd_hui = ctx.get("aujourd_hui") or date.today()
    prochain = aujourd_hui.month % 12 + 1  # le mois qui suit aujourd'hui, quelle que soit la période choisie
    lignes, r = [], RapportGestion()
    r.prochains = []
    for nom in importants if mois else []:
        par_jour = [ventes[nom][m] / len(jours_mois[m]) for m in mois]
        moyenne = sum(par_jour, ZERO) / len(par_jour)
        if moyenne <= 0:
            continue
        i_fort = max(range(len(mois)), key=lambda i: par_jour[i])
        i_faible = min(range(len(mois)), key=lambda i: par_jour[i])
        indice = _d(par_jour[i_fort] / moyenne * 100, "1")
        # vendu presque tous les mois (un article renommé ou arrêté n'est pas « de saison ») et assez vendu au meilleur
        # mois pour compter
        presence = sum(1 for v in par_jour if v > 0) / len(mois)
        profil = ("À confirmer (moins de 3 mois)" if len(mois) < 3 else
                  "Article de saison" if indice >= 150 and presence >= 0.75 and par_jour[i_fort] >= 10 else
                  "Vendu certains mois seulement" if presence < 0.75 else "Régulier")
        lignes.append([nom, cats[nom], _nom_mois(*mois[i_fort]), _d(par_jour[i_fort]), _d(moyenne),
                       _nom_mois(*mois[i_faible]), _d(par_jour[i_faible]), indice, _t(profil)])
        if profil == "Article de saison" and mois[i_fort][1] == prochain:
            r.prochains.append(lignes[-1])
    ordre_profils = [_t("Article de saison"), _t("Régulier"), _t("À confirmer (moins de 3 mois)")]
    lignes.sort(key=lambda l: (ordre_profils.index(l[8]) if l[8] in ordre_profils else 3, -l[7]))
    r.prochains.sort(key=lambda l: -l[3])
    r.entetes = ["Article", "Catégorie", "Mois le plus fort", "Ventes par jour (mois le plus fort)",
                 "Ventes par jour (moyenne des mois)", "Mois le plus faible", "Ventes par jour (mois le plus faible)",
                 "Indice de saison (100 = régulier)", "Profil"]
    r.lignes = lignes
    saison = [l for l in lignes if l[8] == _t("Article de saison")]
    r.cartes = [("Mois analysés", "n", len(mois)), ("Articles de saison", "n", len(saison)),
                ("Articles réguliers", "n", sum(1 for l in lignes if l[8] == _t("Régulier"))),
                ("À préparer le mois prochain", "n", len(r.prochains))]
    r.titre_evolution = "Ventes par jour ouvert de chaque mois (tout le magasin)"
    r.genre_evolution = "barres"
    r.etiquettes = [_nom_mois(*m) for m in mois]
    par_mois = defaultdict(Decimal)
    for x in list(c) + list(avant):
        par_mois[(x.moment.year, x.moment.month)] += x.nettes
    r.series = [(_t("Ventes nettes par jour ouvert"), [_d(par_mois[m] / len(jours_mois[m])) for m in mois])]
    r.titre_repartition = "Articles les plus saisonniers (indice de saison)"
    r.genre_repartition = "classement"
    r.argent_repartition = False
    r.repartition = [(f"{l[0]} ({l[2]})", l[7]) for l in (saison or lignes)[:8]]
    constats = [_k(None, "Indice de saison : ventes par jour du mois le plus fort / moyenne de tous les mois × 100 (150 "
                   "= 50 % de plus au meilleur mois). Seuls les mois d'au moins 20 jours ouverts comptent ; choisissez "
                   "« Cette année » pour voir toutes les saisons.")]
    if len(mois) < 3:
        constats.append(_k("info", "Seulement {n} mois complets : choisissez une période d'au moins 3 mois pour "
                                   "reconnaître les articles de saison.", n=len(mois)))
    elif saison:
        constats.append(_k("info", "{n} article(s) de saison parmi les plus vendus : commander plus avant leur meilleur "
                                   "mois et moins ensuite.", n=len(saison)))
    else:
        constats.append(_k("bon", "Aucun article important ne dépend d'une saison : ventes stables d'un mois à "
                                  "l'autre."))
    if r.prochains:
        constats.append(_k("attention", "À préparer pour {m} : {a}.", m=_t(MOIS_NOMS[prochain - 1]),
                           a=", ".join(l[0] for l in r.prochains[:5])))
    r.mois_prochain = _t(MOIS_NOMS[prochain - 1])
    r.note = _note(constats)
    return r


# --------------------------------------------------------------------------------------------- ventes au poids
def ventes_poids(c, avant, ctx) -> RapportGestion:
    """Articles vendus au poids (quantité non entière : kg, lb) : part des ventes, quantité moyenne par commande et
    prix moyen au poids comparé à la période d'avant (une hausse du prix au poids se voit ici)."""
    au_poids = {l.nom for x in list(c) + list(avant) for l in x.lignes if l.quantite_nette % 1}

    def cumul(cmds):
        g = defaultdict(lambda: {"cmd": 0, "qte": ZERO, "ventes": ZERO, "cat": ""})
        for x in cmds:
            for l in x.lignes:
                if l.nom in au_poids:
                    s = g[l.nom]
                    s["cmd"] += 1
                    s["qte"] += l.quantite_nette
                    s["ventes"] += l.ventes_nettes
                    s["cat"] = l.categorie
        return g

    g1, g0 = cumul(c), cumul(avant)
    total = sum((x.nettes for x in c), ZERO)
    poids = sum((s["ventes"] for s in g1.values()), ZERO)
    avec = sum(1 for x in c if any(l.nom in au_poids for l in x.lignes))
    lignes = []
    for nom, s in sorted(g1.items(), key=lambda kv: -kv[1]["ventes"]):
        prix = s["ventes"] / s["qte"] if s["qte"] else ZERO
        s0 = g0.get(nom)
        prix0 = s0["ventes"] / s0["qte"] if s0 and s0["qte"] else None
        lignes.append([nom, s["cat"], s["cmd"], _d(s["qte"], "0.001"), _d(s["qte"] / s["cmd"], "0.001"), _d(prix),
                       _d(prix0) if prix0 is not None else None,
                       _pc(prix - prix0, prix0) if prix0 else None, _d(s["ventes"]), _pc(s["ventes"], total)])
    r = RapportGestion()
    r.entetes = ["Article", "Catégorie", "Commandes", "Quantité vendue (poids)", "Quantité moyenne par commande",
                 "Prix moyen par unité de poids", "Prix moyen avant", "Écart de prix %", "Ventes nettes",
                 "Part des ventes %"]
    r.lignes = lignes
    r.cartes = [("Ventes au poids", "$", _d(poids)), ("Part des ventes au poids", "%", _pc(poids, total)),
                ("Articles vendus au poids", "n", len(lignes)),
                ("Commandes avec un article au poids", "%", _pc(avec, len(c)))]
    jours = _jours(ctx["du"], ctx["au"])
    par_jour, tous = defaultdict(Decimal), defaultdict(Decimal)
    for x in c:
        tous[x.moment.date()] += x.nettes
        par_jour[x.moment.date()] += sum((l.ventes_nettes for l in x.lignes if l.nom in au_poids), ZERO)
    r.titre_evolution = "Ventes au poids par jour"
    r.etiquettes = [_etiquette(j) for j in jours]
    r.series = [(_t("Ventes au poids"), [_d(par_jour.get(j, ZERO)) for j in jours])]
    r.titre_repartition = "Articles au poids qui vendent le plus"
    r.genre_repartition = "classement"
    r.repartition = [(l[0], l[8]) for l in lignes[:8]]
    constats = [_k(None, "Article vendu au poids : au moins une vente avec une quantité non entière (kg, lb) ; prix moyen "
                   "= ventes nettes / quantité vendue.")]
    if not lignes:
        constats.append(_k("info", "Aucun article vendu au poids dans la période."))
    else:
        constats.append(_k("info", "Les articles au poids font {p} % des ventes et se trouvent dans {q} % des "
                                   "commandes.", p=_nb(_pc(poids, total)), q=_nb(_pc(avec, len(c)))))
    hausses = sorted((l for l in lignes[:30] if l[7] is not None and l[7] >= 10), key=lambda l: -l[7])
    for l in hausses[:3]:
        constats.append(_k("attention", "{n} : le prix moyen au poids passe de {a} à {b} ({p} %) : vérifier le prix "
                                        "affiché et la balance.", n=l[0], a=_argent(l[6]), b=_argent(l[5]),
                           p=_nb(l[7])))
    baisses = sorted((l for l in lignes[:30] if l[7] is not None and l[7] <= -10), key=lambda l: l[7])
    for l in baisses[:3]:
        constats.append(_k("attention", "{n} : le prix moyen au poids baisse de {a} à {b} ({p} %) : rabais ou prix mal "
                                        "saisi ?", n=l[0], a=_argent(l[6]), b=_argent(l[5]), p=_nb(l[7])))
    r.hausses_prix = hausses
    r.note = _note(constats)
    return r


# --------------------------------------------------------------------------------------------- ruptures probables
def ruptures(c, avant, ctx) -> RapportGestion:
    """Articles vendus presque chaque jour qui ne se vendent plus pendant plusieurs jours ouverts de suite : rupture
    de stock probable (le stock Clover n'est pas fiable : réceptions pas toujours saisies). Une absence compte quand
    son risque d'arriver par hasard est sous 2 % (présence p : (1 − p)^k < 0,02, 3 jours au moins). Ventes perdues
    estimées = jours d'absence × ventes moyennes d'un jour ouvert hors absence."""
    hier = (ctx.get("aujourd_hui") or date.today()) - timedelta(days=1)
    au = min(ctx["au"], hier)
    ouverts = sorted({x.moment.date() for x in c if x.moment.date() <= au})
    ventes = defaultdict(lambda: defaultdict(Decimal))
    cats, totaux = {}, defaultdict(Decimal)
    for x in c:
        j = x.moment.date()
        if j > au:
            continue
        for l in x.lignes:
            if l.ventes_nettes > 0:
                ventes[l.nom][j] += l.ventes_nettes
            cats[l.nom] = l.categorie
            totaux[l.nom] += l.ventes_nettes
    ordre = [n for n in sorted(totaux, key=lambda n: -totaux[n]) if totaux[n] > 0]
    suivis = ordre[:max(1, math.ceil(len(ordre) * PART_B))]
    lignes, absents_jour, reguliers = [], defaultdict(int), 0
    if len(ouverts) >= 15:
        tous_ouverts = ouverts
        for nom in suivis:
            jours_vente = ventes[nom]
            # compté depuis sa 1re vente de la période : un article lancé en cours de route n'a pas « manqué » avant
            ouverts = [j for j in tous_ouverts if j >= min(jours_vente)] if jours_vente else []
            if len(ouverts) < 15:
                continue
            p = sum(1 for j in ouverts if j in jours_vente) / len(ouverts)
            if p < 0.7:
                continue
            reguliers += 1
            seuil = 3 if p >= 1 else max(3, math.ceil(math.log(0.02) / math.log(1 - p)))
            absences, debut = [], None
            for k, j in enumerate(ouverts):
                if j in jours_vente:
                    if debut is not None and k - debut >= seuil:
                        absences.append((debut, k - 1))
                    debut = None
                elif debut is None:
                    debut = k
            if debut is not None and len(ouverts) - debut >= seuil:
                absences.append((debut, len(ouverts) - 1))
            if not absences:
                continue
            jours_abs = sum(b - a + 1 for a, b in absences)
            reste = len(ouverts) - jours_abs
            moyenne = sum(jours_vente.values(), ZERO) / reste if reste else ZERO
            for a, b in absences:
                for k in range(a, b + 1):
                    absents_jour[ouverts[k]] += 1
            a, b = max(absences, key=lambda ab: ab[1] - ab[0])
            en_cours = absences[-1][1] == len(ouverts) - 1
            if en_cours:
                a, b = absences[-1]
            lignes.append([nom, cats.get(nom, ""), _pc(p, 1), _d(moyenne), b - a + 1, ouverts[a].isoformat(),
                           ouverts[b].isoformat(), _t("Oui") if en_cours else _t("Non"), jours_abs,
                           _d(moyenne * jours_abs)])
        ouverts = tous_ouverts
    lignes.sort(key=lambda l: (l[7] != _t("Oui"), -l[9]))
    perdues = sum((l[9] for l in lignes), ZERO)
    en_cours = [l for l in lignes if l[7] == _t("Oui")]
    total = sum((x.nettes for x in c), ZERO)
    r = RapportGestion()
    r.entetes = ["Article", "Catégorie", "Jours de vente %", "Ventes moyennes par jour", "Plus longue absence (jours)",
                 "Absence du", "Absence au", "Absence en cours", "Jours sans vente", "Ventes perdues estimées"]
    r.lignes = lignes
    r.cartes = [("Articles réguliers suivis", "n", reguliers), ("Ruptures probables", "n", len(lignes)),
                ("Ruptures en cours", "n", len(en_cours)), ("Ventes perdues estimées", "$", _d(perdues)),
                ("Part des ventes perdues", "%", _pc(perdues, total + perdues))]
    r.titre_evolution = "Articles réguliers sans vente, par jour"
    r.genre_evolution = "barres"
    r.unite_evolution = ""
    r.etiquettes = [_etiquette(j) for j in ouverts]
    r.series = [(_t("Articles sans vente"), [Decimal(absents_jour.get(j, 0)) for j in ouverts])]
    r.titre_repartition = "Ventes perdues estimées par article"
    r.genre_repartition = "classement"
    r.repartition = [(l[0], l[9]) for l in sorted(lignes, key=lambda l: -l[9])[:8]]
    constats = [_k(None, "Rupture probable : article vendu au moins 7 jours ouverts sur 10 (parmi ceux qui font la "
                   "moitié des ventes) qui ne se vend pas pendant assez de jours ouverts de suite pour que ce soit "
                   "presque sûrement un manque de stock (3 jours au moins). La journée en cours n'est pas comptée.")]
    if len(ouverts) < 15:
        constats.append(_k(None, "Choisissez une période d'au moins 15 jours ouverts (par exemple « 30 derniers jours »)."))
    elif not lignes:
        constats.append(_k("bon", "Aucune rupture probable : les articles réguliers se sont vendus sans interruption."))
    else:
        constats.append(_k("attention", "{n} article(s) régulier(s) ont manqué ; environ {v} de ventes perdues "
                                        "({p} % des ventes).", n=len(lignes), v=_argent(_d(perdues)),
                           p=_nb(_pc(perdues, total + perdues))))
        if en_cours:
            constats.append(_k("alerte", "{n} article(s) ne se vendent plus depuis plusieurs jours, dont {a} depuis "
                                          "le {d} : vérifier le stock et commander.", n=len(en_cours), a=en_cours[0][0],
                               d=en_cours[0][5]))
    r.note = _note(constats)
    return r


# --------------------------------------------------------------------------------------------- articles d'appel
def articles_appel(c, avant, ctx) -> RapportGestion:
    """Articles qui font venir les clients : commandes qui les contiennent nettement plus grosses que le panier moyen
    (le client achète autre chose en plus) ; à l'inverse, achats rapides (article souvent acheté seul). Parmi les 20 %
    d'articles présents dans le plus de commandes, 20 commandes au moins."""
    n = len(c)
    total = sum((x.nettes for x in c), ZERO)
    panier = total / n if n else ZERO
    g = defaultdict(lambda: {"cmd": 0, "seul": 0, "paniers": ZERO, "propre": ZERO, "articles": 0, "cat": ""})
    for x in c:
        noms = {l.nom for l in x.lignes}
        for nom in noms:
            s_ = g[nom]
            s_["cmd"] += 1
            s_["seul"] += len(noms) == 1
            s_["paniers"] += x.nettes
            s_["articles"] += len(noms)
        for l in x.lignes:
            g[l.nom]["propre"] += l.ventes_nettes
            g[l.nom]["cat"] = l.categorie
    ordre = sorted(g, key=lambda k: -g[k]["cmd"])
    # sacs, consignes : moins de 1 $ par commande, pas des articles qui font venir
    suivis = [k for k in ordre[:max(30, math.ceil(len(ordre) * PART_A))]
              if g[k]["cmd"] >= 20 and g[k]["propre"] / g[k]["cmd"] >= 1]
    lignes = []
    for nom in suivis:
        s_ = g[nom]
        moyen = s_["paniers"] / s_["cmd"]
        autres = (s_["paniers"] - s_["propre"]) / s_["cmd"]
        seul = _pc(s_["seul"], s_["cmd"])
        indice = _pc(moyen, panier, "0.1") if panier else ZERO
        if panier and autres >= panier * Decimal("1.75") and seul < 15:
            profil = _t("Article d'appel")
        elif seul >= 40:
            profil = _t("Achat rapide")
        else:
            profil = _t("Courant")
        lignes.append([nom, s_["cat"], s_["cmd"], _pc(s_["cmd"], n), _d(moyen), indice,
                       _d(Decimal(s_["articles"]) / s_["cmd"], "0.1"), seul, _d(autres),
                       _d(s_["paniers"] - s_["propre"]), profil])
    rang = {_t("Article d'appel"): 0, _t("Achat rapide"): 1, _t("Courant"): 2}
    lignes.sort(key=lambda l: (rang[l[10]], -l[9]))
    appel = [l for l in lignes if l[10] == _t("Article d'appel")]
    rapides = [l for l in lignes if l[10] == _t("Achat rapide")]
    r = RapportGestion()
    r.entetes = ["Article", "Catégorie", "Commandes", "% des commandes", "Panier moyen avec l'article",
                 "Indice du panier (100 = panier moyen)", "Articles différents par commande", "Acheté seul %",
                 "Autres achats par commande", "Autres achats entraînés", "Profil"]
    r.lignes = lignes
    r.cartes = [("Articles suivis", "n", len(lignes)), ("Articles d'appel", "n", len(appel)),
                ("Achats rapides", "n", len(rapides)), ("Panier moyen", "$", _d(panier))]
    noms_appel = {l[0] for l in appel}
    jours = _jours(ctx["du"], ctx["au"])
    avec, sans = defaultdict(lambda: [ZERO, 0]), defaultdict(lambda: [ZERO, 0])
    for x in c:
        cible = avec if any(l.nom in noms_appel for l in x.lignes) else sans
        cible[x.moment.date()][0] += x.nettes
        cible[x.moment.date()][1] += 1

    def moyenne(t, j):
        v, k = t.get(j, (ZERO, 0))
        return _d(v / k) if k else ZERO

    r.titre_evolution = "Panier moyen par jour : commandes avec un article d'appel et autres commandes"
    r.etiquettes = [_etiquette(j) for j in jours]
    r.series = [(_t("Avec un article d'appel"), [moyenne(avec, j) for j in jours]),
                (_t("Autres commandes"), [moyenne(sans, j) for j in jours])]
    r.titre_repartition = "Autres achats entraînés par l'article"
    r.genre_repartition = "classement"
    r.repartition = [(l[0], l[9]) for l in sorted(lignes, key=lambda l: -l[9])[:8]]
    constats = [_k(None, "Article d'appel : ses clients achètent en plus, à côté de lui, au moins 1,75 fois le panier "
                   "moyen et il est presque toujours acheté avec autre chose (moins de 15 % seul). Achat rapide : acheté "
                   "seul dans 40 % des commandes ou plus. Articles suivis : les 20 % présents dans le plus de commandes, "
                   "20 commandes au moins, 1 $ au moins par commande (sacs et consignes écartés).")]
    if not lignes:
        constats.append(_k("info", "Pas assez de commandes dans la période pour cette analyse."))
    if appel:
        constats.append(_k("info", "{n} article(s) d'appel, dont {a} : les clients qui le prennent dépensent {v} en "
                                   "moyenne ({i} % du panier moyen). Ne jamais en manquer ; prudence sur leur prix.",
                           n=len(appel), a=appel[0][0], v=_argent(appel[0][4]), i=_nb(appel[0][5], 0)))
    if rapides:
        constats.append(_k("info", "{n} achat(s) rapide(s), dont {a} (acheté seul {p} % du temps) : le placer près de "
                                   "la caisse ou proposer un 2e article.", n=len(rapides), a=rapides[0][0],
                           p=_nb(rapides[0][7], 0)))
    r.appel = appel
    r.note = _note(constats)
    return r


# --------------------------------------------------------------------------------------------- compléments manqués
def complements(c, avant, ctx) -> RapportGestion:
    """Ventes complémentaires manquées : pour chaque article, l'article que ses clients prennent le plus souvent avec
    lui (au moins 30 % de ses commandes, 2 fois plus que le hasard, 10 commandes ensemble) ; commandes où le
    complément manque et gain possible si 1 client sur 4 qui l'oublie le prenait (prix moyen du complément)."""
    n = len(c)
    nb, ventes, cats = defaultdict(int), defaultdict(Decimal), {}
    paires = defaultdict(int)
    jours_sans = defaultdict(lambda: defaultdict(int))
    contenus = []
    for x in c:
        noms = {l.nom for l in x.lignes}
        for l in x.lignes:
            ventes[l.nom] += l.ventes_nettes
            cats[l.nom] = l.categorie
        for a in noms:
            nb[a] += 1
        if 1 < len(noms) <= LIGNES_MAX_PAIRES:
            for a, b in combinations(sorted(noms), 2):
                paires[(a, b)] += 1
        contenus.append((x.moment.date(), noms))
    minimum = max(10, min(25, math.ceil(n * 0.002)))  # plafonné : sur un an, 0,2 % ne garderait presque rien
    meilleurs = {}
    for (a, b), ab in paires.items():
        if ab < minimum:
            continue
        for x_, y_ in ((a, b), (b, a)):
            conf = ab / nb[x_]
            lift = ab * n / (nb[x_] * nb[y_])
            # consignes, sacs : moins de 1 $ par commande, pas un complément à proposer
            if (conf >= 0.3 and lift >= 2 and ventes[y_] / nb[y_] >= 1
                    and (x_ not in meilleurs or conf > meilleurs[x_][1])):
                meilleurs[x_] = (y_, conf, lift, ab)
    lignes = []
    for a, (b, conf, lift, ab) in meilleurs.items():
        prix_b = ventes[b] / nb[b]
        sans = nb[a] - ab
        lignes.append([a, b, cats.get(a, ""), nb[a], _pc(ab, nb[a]), _d(lift, "0.1"), sans, _d(prix_b),
                       _d(prix_b * sans / 4)])
    lignes.sort(key=lambda l: -l[8])
    for j, noms in contenus:
        for l in lignes[:30]:
            if l[0] in noms and l[1] not in noms:
                jours_sans[j][l[0]] += 1
    gain = sum((l[8] for l in lignes), ZERO)
    r = RapportGestion()
    r.entetes = ["Article acheté", "Complément habituel", "Catégorie", "Commandes avec l'article",
                 "Avec le complément %", "Affinité (fois le hasard)", "Commandes sans le complément",
                 "Prix moyen du complément", "Gain possible (1 client sur 4)"]
    r.lignes = lignes
    r.cartes = [("Articles avec un complément habituel", "n", len(lignes)),
                ("Commandes sans le complément", "n", sum(l[6] for l in lignes)),
                ("Gain possible (1 client sur 4)", "$", _d(gain)),
                ("Plus gros gain possible", "t", f"{lignes[0][0]} + {lignes[0][1]}" if lignes else "—")]
    jours = _jours(ctx["du"], ctx["au"])
    r.titre_evolution = "Commandes sans le complément habituel, par jour (30 premiers articles)"
    r.genre_evolution = "barres"
    r.unite_evolution = ""
    r.etiquettes = [_etiquette(j) for j in jours]
    r.series = [(_t("Commandes sans le complément"), [Decimal(sum(jours_sans[j].values())) for j in jours])]
    r.titre_repartition = "Gain possible par article"
    r.genre_repartition = "classement"
    r.repartition = [(f"{l[0]} + {l[1]}", l[8]) for l in lignes[:8]]
    constats = [_k(None, "Complément habituel : l'article que les clients d'un article prennent le plus souvent avec "
                   "lui (au moins 30 % de ses commandes, 2 fois plus que le hasard, {m} commandes ensemble au moins ; "
                   "consignes et sacs écartés). Gain possible : commandes sans le complément × son prix moyen, si 1 client sur 4 qui l'oublie le "
                   "prenait.", m=minimum)]
    if not lignes:
        constats.append(_k("info", "Aucun complément habituel assez fréquent dans la période."))
    else:
        l = lignes[0]
        constats.append(_k("info", "{p} % des clients qui prennent « {a} » prennent aussi « {b} » ; {s} commandes "
                                   "l'ont oublié. Le proposer à la caisse rapporterait environ {g}.",
                           p=_nb(l[4], 0), a=l[0], b=l[1], s=l[6], g=_argent(l[8])))
        constats.append(_k("info", "En tout, environ {g} de ventes de plus si un client sur quatre prenait le "
                                   "complément qu'il oublie.", g=_argent(_d(gain))))
    r.note = _note(constats)
    return r


# --------------------------------------------------------------------------------------------- prix selon le format
_FORMAT = re.compile(r"(?:(\d+)\s*[x×]\s*)?(\d+(?:[.,]\d+)?)\s*(kg|kgs|g|gr|lb|lbs|ml|cl|l|litres?)\b", re.I)
_UNITES = {"kg": 1000, "kgs": 1000, "g": 1, "gr": 1, "lb": 453.592, "lbs": 453.592, "ml": 1, "cl": 10, "l": 1000,
           "litre": 1000, "litres": 1000}


def format_article(nom: str):
    """(produit sans le format, taille en g ou en ml, « kg » ou « L ») d'après le nom (« Attieke 1kg Sun »,
    « Jus 6x330ml ») ; None si le nom n'a pas de format chiffré (article vendu au poids « en lb »)."""
    m = None
    for m in _FORMAT.finditer(nom):
        pass
    if not m:
        return None
    nombre = float(m.group(2).replace(",", "."))
    unite = m.group(3).lower()
    taille = nombre * _UNITES[unite] * (int(m.group(1)) if m.group(1) else 1)
    if taille <= 0:
        return None
    base = _FORMAT.sub(" ", nom)
    base = unicodedata.normalize("NFKD", base).encode("ascii", "ignore").decode().lower()
    base = " ".join(re.sub(r"[^a-z0-9]+", " ", base).split())
    return base, taille, "L" if unite in ("ml", "cl", "l", "litre", "litres") else "kg"


def prix_format(c, avant, ctx) -> RapportGestion:
    """Produits vendus en plusieurs formats (même nom, format chiffré différent) : prix affiché moyen (ventes avant
    rabais / quantité) ramené au kg ou au litre ; un format plus grand doit coûter moins cher (ou autant) au kg qu'un
    plus petit. Écart de plus de 2 % = prix à vérifier."""
    g = defaultdict(lambda: {"qte": ZERO, "brut": ZERO, "cat": ""})
    for x in c:
        for l in x.lignes:
            if l.quantite_vendue > 0 and l.ventes_brutes > 0:
                s_ = g[l.nom]
                s_["qte"] += l.quantite_vendue
                s_["brut"] += l.ventes_brutes
                s_["cat"] = l.categorie
    produits = defaultdict(list)
    for nom, s_ in g.items():
        f = format_article(nom)
        if f and s_["qte"] >= 3:
            base, taille, unite = f
            produits[(base, unite)].append((taille, nom, s_))
    lignes, incoherents, graphe = [], [], None
    for (base, unite), formats in produits.items():
        if len({t for t, _n, _s in formats}) < 2:
            continue
        formats.sort(key=lambda f: (f[0], f[1]))
        petit = None
        groupe, probleme = [], False
        for taille, nom, s_ in formats:
            prix = s_["brut"] / s_["qte"]
            au_kg = prix / Decimal(str(taille)) * 1000
            if petit is None:
                petit = au_kg
            ecart = _pc(au_kg - petit, petit) if petit else ZERO
            plus_cher = any(au_kg > p_ * Decimal("1.02") for t_, p_ in groupe if t_ < taille)
            probleme |= plus_cher
            groupe.append((taille, au_kg))
            taille_txt = (_nb(Decimal(str(taille)) / 1000, 2) if taille >= 1000 else _nb(Decimal(str(taille)), 0)) + \
                (" " + ("kg" if unite == "kg" else "L") if taille >= 1000 else " " + ("g" if unite == "kg" else "ml"))
            lignes.append([base, nom, s_["cat"], taille_txt, _d(s_["qte"], "0.001"), _d(prix), _d(au_kg),
                           _t("au kg") if unite == "kg" else _t("au litre"), ecart,
                           _t("Plus cher qu'un format plus petit") if plus_cher else _t("Correct")])
        if probleme:
            incoherents.append(base)
            u_txt = _t("au kg") if unite == "kg" else _t("au litre")
            pire = max(l[8] for l in lignes if l[0] == base and l[7] == u_txt)
            if graphe is None or pire > graphe[2]:
                choix = [l for l in lignes if l[0] == base and l[7] == u_txt]
                graphe = (_FORMAT.sub("", choix[0][1]).strip(), [(l[3], l[6]) for l in choix], pire)
    pire = {b: max(l[8] for l in lignes if l[0] == b) for b in incoherents}
    ordre = {b: k for k, b in enumerate(sorted(incoherents, key=lambda b: -pire[b]))}
    lignes.sort(key=lambda l: (ordre.get(l[0], len(ordre)), l[0]))
    mal = [l for l in lignes if l[9] == _t("Plus cher qu'un format plus petit")]
    r = RapportGestion()
    r.entetes = ["Produit", "Article", "Catégorie", "Format", "Quantité vendue", "Prix moyen affiché",
                 "Prix au kg ou au litre", "Unité", "Écart avec le plus petit format %", "Contrôle"]
    r.lignes = lignes
    r.cartes = [("Produits en plusieurs formats", "n", len({l[0] for l in lignes})), ("Formats suivis", "n", len(lignes)),
                ("Produits aux prix incohérents", "n", len(incoherents)), ("Formats à vérifier", "n", len(mal))]
    if graphe:
        r.titre_evolution = _t("Prix au kg ou au litre selon le format : {a}", a=graphe[0])
        r.genre_evolution = "barres"
        r.etiquettes = [f for f, _v in graphe[1]]
        r.series = [(_t("Prix au kg ou au litre"), [v for _f, v in graphe[1]])]
    else:
        r.titre_evolution = "Prix au kg ou au litre selon le format"
    r.titre_repartition = "Formats plus chers au kg qu'un format plus petit (écart %)"
    r.genre_repartition = "classement"
    r.argent_repartition = False
    r.repartition = [(l[1], l[8]) for l in sorted(mal, key=lambda l: -l[8])[:8]]
    constats = [_k(None, "Format : taille lue dans le nom de l'article (« 1kg », « 500g », « 6x330ml ») ; prix moyen "
                   "affiché = ventes avant rabais / quantité ; un format plus grand doit coûter au kg (ou au litre) au "
                   "plus 2 % de plus qu'un format plus petit du même produit.")]
    if not lignes:
        constats.append(_k("info", "Aucun produit vendu en plusieurs formats dans la période."))
    elif mal:
        constats.append(_k("attention", "{n} format(s) coûtent plus cher au kg qu'un format plus petit du même produit, "
                                        "dont {a} : les clients ont intérêt à acheter le petit format. Revoir le prix.",
                           n=len(mal), a=mal[0][1]))
    else:
        constats.append(_k("bon", "Les grands formats sont tous moins chers au kg que les petits."))
    r.mal = mal
    r.note = _note(constats)
    return r


# --------------------------------------------------------------------------------------------- tranches de prix
TRANCHES_PRIX = ((0, 2, "Moins de 2 $"), (2, 5, "2 à 5 $"), (5, 10, "5 à 10 $"), (10, 20, "10 à 20 $"),
                 (20, 50, "20 à 50 $"), (50, 10 ** 9, "50 $ et plus"))


def _tranche_prix(prix) -> str:
    return next(n for a, b, n in TRANCHES_PRIX if a <= prix < b)


def tranches_prix(c, avant, ctx) -> RapportGestion:
    """Ventes selon le prix affiché d'un article (ventes avant rabais / quantité, prix d'une unité ou d'une livre) :
    nombre d'articles, quantités et ventes de chaque tranche, comparées à la période d'avant."""
    def cumul(cmds):
        art = defaultdict(lambda: [ZERO, ZERO, ZERO])  # quantité, brut, net
        for x in cmds:
            for l in x.lignes:
                if l.quantite_vendue > 0 and l.ventes_brutes > 0:
                    a = art[l.nom]
                    a[0] += l.quantite_vendue
                    a[1] += l.ventes_brutes
                    a[2] += l.ventes_nettes
        g = {n: {"art": 0, "qte": ZERO, "net": ZERO} for _a, _b, n in TRANCHES_PRIX}
        for q, brut, net in art.values():
            t_ = g[_tranche_prix(brut / q)]
            t_["art"] += 1
            t_["qte"] += q
            t_["net"] += net
        return g

    g1, g0 = cumul(c), cumul(avant)
    total = sum((t_["net"] for t_ in g1.values()), ZERO)
    total0 = sum((t_["net"] for t_ in g0.values()), ZERO)
    qte = sum((t_["qte"] for t_ in g1.values()), ZERO)
    lignes = []
    for _a, _b, n in TRANCHES_PRIX:
        t_, t0 = g1[n], g0[n]
        lignes.append([_t(n), t_["art"], _d(t_["qte"], "0.001"), _d(t_["net"]), _pc(t_["net"], total) if total else ZERO,
                       _d(t0["net"]), _pc(t_["net"] - t0["net"], t0["net"]) if t0["net"] else None,
                       _d(t_["net"] / t_["qte"]) if t_["qte"] else ZERO])
    meilleure = max(lignes, key=lambda l: l[3])
    moins5 = sum((g1[n]["net"] for _a, b, n in TRANCHES_PRIX if b <= 5), ZERO)
    r = RapportGestion()
    r.entetes = ["Tranche de prix", "Articles", "Quantité vendue", "Ventes nettes", "Part des ventes %",
                 "Ventes nettes avant", "Variation %", "Ventes nettes par unité"]
    r.lignes = lignes
    r.cartes = [("Articles vendus", "n", sum(l[1] for l in lignes)),
                ("Prix moyen d'une unité vendue", "$", _d(total / qte) if qte else 0),
                ("Tranche qui vend le plus", "t", meilleure[0]),
                ("Part des articles à moins de 5 $", "%", _pc(moins5, total) if total else 0)]
    r.titre_evolution = "Ventes nettes par tranche de prix : période et période d'avant"
    r.genre_evolution = "barres"
    r.etiquettes = [l[0] for l in lignes]
    r.series = [(_t("Période choisie"), [l[3] for l in lignes]), (_t("Période d'avant"), [l[5] for l in lignes])]
    r.titre_repartition = "Articles différents par tranche de prix"
    r.genre_repartition = "anneau"
    r.argent_repartition = False
    r.repartition = [(l[0], Decimal(l[1])) for l in lignes if l[1]]
    constats = [_k(None, "Tranche de prix : prix affiché d'une unité (ou d'une livre pour un article au poids) = ventes "
                   "avant rabais / quantité vendue, sur la période.")]
    if total:
        constats.append(_k("info", "La tranche « {t} » fait le plus de ventes ({p} %) ; les articles à moins de 5 $ "
                                   "font {q} % des ventes.", t=meilleure[0], p=_nb(meilleure[4]),
                           q=_nb(_pc(moins5, total))))
        variees = [l for l in lignes if l[6] is not None and l[5] >= total0 * Decimal("0.05")]
        if variees:
            haut, bas = max(variees, key=lambda l: l[6]), min(variees, key=lambda l: l[6])
            if haut[6] >= 10:
                constats.append(_k("bon", "Tranche en hausse : « {t} » ({p} %).", t=haut[0], p="+" + _nb(haut[6])))
            if bas[6] <= -10:
                constats.append(_k("attention", "Tranche en baisse : « {t} » ({p} %) : vérifier l'offre et les prix de "
                                                "ces articles.", t=bas[0], p=_nb(bas[6])))
            r.baisse = bas if bas[6] <= -15 else None
    r.note = _note(constats)
    return r


# --------------------------------------------------------------------------------------------- contribution à l'écart
def contribution(c, avant, ctx) -> RapportGestion:
    """Écart des ventes nettes avec la période d'avant expliqué en dollars par catégorie, puis par article (les 10
    qui font le plus monter et les 10 qui font le plus baisser)."""
    def cumul(cmds, cle):
        g = defaultdict(Decimal)
        for x in cmds:
            for l in x.lignes:
                g[cle(l)] += l.ventes_nettes
        return g

    cat1, cat0 = cumul(c, lambda l: l.categorie), cumul(avant, lambda l: l.categorie)
    art1, art0 = cumul(c, lambda l: l.nom), cumul(avant, lambda l: l.nom)
    categorie = {l.nom: l.categorie for x in list(avant) + list(c) for l in x.lignes}
    total1, total0 = sum(cat1.values(), ZERO), sum(cat0.values(), ZERO)
    ecart = total1 - total0
    base = sum((abs(cat1.get(k, ZERO) - cat0.get(k, ZERO)) for k in set(cat1) | set(cat0)), ZERO)

    def ligne(niveau, nom, cat, v1, v0):
        e_ = v1 - v0
        return [_t(niveau), nom, cat, _d(v0), _d(v1), _d(e_), _pc(e_, base) if base else ZERO,
                _pc(e_, v0) if v0 else None]

    cats = sorted((ligne("Catégories", k, "", cat1.get(k, ZERO), cat0.get(k, ZERO)) for k in set(cat1) | set(cat0)),
                  key=lambda l: -l[5])
    ecarts_art = sorted(((k, art1.get(k, ZERO) - art0.get(k, ZERO)) for k in set(art1) | set(art0)),
                        key=lambda kv: -kv[1])
    hausses = [k for k, e_ in ecarts_art[:10] if e_ > 0]
    baisses = [k for k, e_ in reversed(ecarts_art[-10:]) if e_ < 0]
    arts = [ligne("Articles", k, categorie.get(k, ""), art1.get(k, ZERO), art0.get(k, ZERO)) for k in hausses + baisses]
    r = RapportGestion()
    r.entetes = ["Niveau", "Catégorie ou article", "Catégorie", "Ventes nettes avant", "Ventes nettes",
                 "Écart", "Part des écarts %", "Variation %"]
    r.lignes = cats + arts
    monte = [l for l in cats if l[5] > 0]
    baisse = [l for l in cats if l[5] < 0]
    r.cartes = [("Écart des ventes nettes", "$", _d(ecart)), ("Variation", "%", _pc(ecart, total0) if total0 else 0),
                ("Catégories en hausse", "n", len(monte)), ("Catégories en baisse", "n", len(baisse)),
                ("Fait le plus monter", "t", monte[0][1] if monte else "—"),
                ("Fait le plus baisser", "t", baisse[-1][1] if baisse else "—")]
    r.titre_evolution = "Écart des ventes nettes par catégorie (en $)"
    r.genre_evolution = "barres"
    choisies = (monte[:6] + baisse[-6:])
    r.etiquettes = [l[1] for l in choisies]
    r.series = [(_t("Écart"), [l[5] for l in choisies])]
    r.titre_repartition = "Articles qui font le plus monter ou baisser les ventes"
    r.genre_repartition = "classement"
    r.repartition = [_signe(l[1], l[5]) for l in (arts[:4] + arts[len(hausses):len(hausses) + 4])]
    constats = [_k(None, "Écart : ventes nettes de la période moins celles de la période d'avant. Part des écarts : "
                   "poids de chaque catégorie dans l'ensemble des hausses et des baisses.")]
    if not total0:
        constats.append(_k("info", "Pas de ventes dans la période d'avant : rien à comparer."))
    else:
        constats.append(_k("bon" if ecart >= 0 else "attention", "Les ventes nettes {s} de {v} ({p} %).",
                           s=_t("montent") if ecart >= 0 else _t("baissent"), v=_argent(abs(_d(ecart))),
                           p=_nb(_pc(ecart, total0))))
        if monte:
            constats.append(_k("bon", "« {c} » fait le plus monter les ventes ({v}).", c=monte[0][1],
                               v="+" + _argent(monte[0][5])))
        if baisse:
            constats.append(_k("attention", "« {c} » fait le plus baisser les ventes ({v}).", c=baisse[-1][1],
                               v=_argent(baisse[-1][5])))
        if arts and baisses:
            pire = next(l for l in arts if l[1] == baisses[0])
            constats.append(_k("attention", "Article qui fait le plus baisser les ventes : « {a} » ({v}).", a=pire[1],
                               v=_argent(pire[5])))
    r.freins = [l for l in baisse if base and abs(l[5]) >= base * Decimal("0.15")] if ecart < 0 else []
    r.note = _note(constats)
    return r


# --------------------------------------------------------------------------------------------- effet des rabais
def effet_rabais(c, avant, ctx) -> RapportGestion:
    """Les rabais font-ils acheter plus ? Commandes avec un rabais (hors rabais Direction et comptes administrateurs,
    mis à part) contre commandes sans rabais : panier moyen après rabais, articles par commande, rabais moyen ; puis
    chaque rabais par son nom."""
    a_part = mises_a_part(ctx)
    noms = {}
    donnees = ctx.get("donnees")
    for o in (donnees.commandes if donnees is not None else []):
        n_ = [x.get("name") or "" for x in (o.get("discounts") or {}).get("elements", [])]
        for li in (o.get("lineItems") or {}).get("elements", []):
            n_ += [x.get("name") or "" for x in (li.get("discounts") or {}).get("elements", [])]
        n_ = sorted({x.strip() for x in n_ if x.strip()})
        if n_:
            noms[o["id"]] = n_[0] if len(n_) == 1 else _t("Plusieurs rabais")
    groupes = {"avec": [], "sans": []}
    par_nom = defaultdict(lambda: [0, ZERO, ZERO])  # commandes, rabais, ventes nettes
    jours_avec, jours_tous = defaultdict(int), defaultdict(int)
    for x in c:
        if x.id in a_part:
            continue
        rabais = -sum((l.rabais for l in x.lignes), ZERO)
        jours_tous[x.moment.date()] += 1
        if rabais > 0:
            groupes["avec"].append((x, rabais))
            jours_avec[x.moment.date()] += 1
            s_ = par_nom[noms.get(x.id, _t("Rabais sans nom"))]
            s_[0] += 1
            s_[1] += rabais
            s_[2] += x.nettes
        else:
            groupes["sans"].append((x, ZERO))

    def resume(g):
        n_ = len(g)
        if not n_:
            return 0, ZERO, ZERO, ZERO
        return (n_, _d(sum((x.nettes for x, _r in g), ZERO) / n_), _d(sum((r_ for _x, r_ in g), ZERO) / n_),
                _d(Decimal(sum(len({l.nom for l in x.lignes}) for x, _r in g)) / n_, "0.1"))

    total = len(groupes["avec"]) + len(groupes["sans"])
    av, sa = resume(groupes["avec"]), resume(groupes["sans"])
    lignes = [[_t("Commandes avec un rabais"), av[0], _pc(av[0], total) if total else ZERO, av[1], av[2], av[3]],
              [_t("Commandes sans rabais"), sa[0], _pc(sa[0], total) if total else ZERO, sa[1], sa[2], sa[3]]]
    for nom, (n_, rab, net) in sorted(par_nom.items(), key=lambda kv: -kv[1][1]):
        lignes.append([nom, n_, _pc(n_, total) if total else ZERO, _d(net / n_), _d(rab / n_), None])
    rabais_total = sum((r_ for _x, r_ in groupes["avec"]), ZERO)
    ventes = sum((x.nettes for x, _r in groupes["avec"] + groupes["sans"]), ZERO)
    r = RapportGestion()
    r.entetes = ["Commandes ou rabais", "Commandes", "% des commandes", "Panier moyen après rabais",
                 "Rabais moyen par commande", "Articles différents par commande"]
    r.lignes = lignes
    r.cartes = [("Commandes avec un rabais", "%", _pc(av[0], total) if total else 0),
                ("Panier avec rabais", "$", av[1]), ("Panier sans rabais", "$", sa[1]),
                ("Rabais moyen par commande", "$", av[2]),
                ("Rabais accordés (hors Direction)", "$", _d(rabais_total))]
    jours = _jours(ctx["du"], ctx["au"])
    r.titre_evolution = "Part des commandes avec un rabais, par jour (%)"
    r.genre_evolution = "barres"
    r.unite_evolution = "%"
    r.etiquettes = [_etiquette(j) for j in jours]
    r.series = [(_t("Commandes avec un rabais"), [_pc(jours_avec.get(j, 0), jours_tous[j]) if jours_tous.get(j)
                                                  else ZERO for j in jours])]
    r.titre_repartition = "Rabais accordés par nom de rabais"
    r.genre_repartition = "classement"
    r.repartition = [(nom, _d(rab)) for nom, (_n, rab, _v) in sorted(par_nom.items(), key=lambda kv: -kv[1][1])[:8]]
    constats = [_k(None, "Effet des rabais : commandes avec au moins un rabais (de ligne ou de commande) comparées aux "
                   "commandes sans rabais ; les rabais Direction et les commandes des comptes administrateurs sont "
                   "dans leur propre état.")]
    if not av[0]:
        constats.append(_k("info", "Aucun rabais accordé dans la période (hors Direction et administrateurs)."))
    elif sa[0]:
        if av[1] > sa[1]:
            constats.append(_k("bon", "Les commandes avec un rabais valent {a} contre {b} sans rabais, après le rabais "
                                      "({c} de rabais en moyenne) : les rabais accompagnent de plus gros achats.",
                               a=_argent(av[1]), b=_argent(sa[1]), c=_argent(av[2])))
        else:
            constats.append(_k("attention", "Les commandes avec un rabais valent {a} contre {b} sans rabais, après le "
                                            "rabais : les rabais ne font pas acheter plus.", a=_argent(av[1]),
                               b=_argent(sa[1])))
        constats.append(_k("info", "{p} % des commandes ont un rabais ; les rabais représentent {q} % des ventes.",
                           p=_nb(_pc(av[0], total)), q=_nb(_pc(rabais_total, ventes + rabais_total))))
    r.inefficace = bool(av[0] and sa[0] and av[1] <= sa[1] and ventes and rabais_total >= ventes / 100)
    r.note = _note(constats)
    return r


# --------------------------------------------------------------------------------------------- assortiment
def assortiment(c, avant, ctx) -> RapportGestion:
    """Productivité de l'assortiment par catégorie : articles vendus, ventes par article, nombre d'articles qui font
    80 % des ventes de la catégorie, références qui se vendent à peine (2 commandes ou moins dans la période) ;
    nombre d'articles différents vendus chaque semaine."""
    g = defaultdict(lambda: defaultdict(lambda: [ZERO, 0]))  # catégorie -> article -> [ventes, commandes]
    for x in c:
        vus = set()
        for l in x.lignes:
            a = g[l.categorie][l.nom]
            a[0] += l.ventes_nettes
            if l.nom not in vus:
                a[1] += 1
                vus.add(l.nom)
    avant_g = defaultdict(set)
    for x in avant:
        for l in x.lignes:
            avant_g[l.categorie].add(l.nom)
    total = sum((v[0] for arts in g.values() for v in arts.values()), ZERO)
    lignes = []
    for cat, arts in g.items():
        ventes = sum((v[0] for v in arts.values()), ZERO)
        if ventes <= 0:
            continue
        tri = sorted((v[0] for v in arts.values()), reverse=True)
        cumul, n80 = ZERO, 0
        for v in tri:
            cumul += v
            n80 += 1
            if cumul >= ventes * Decimal("0.8"):
                break
        faibles = [n for n, v in arts.items() if v[1] <= 2]
        part_faibles = _pc(len(faibles), len(arts))
        lignes.append([cat, len(arts), len(avant_g.get(cat, set())), _d(ventes), _pc(ventes, total),
                       _d(ventes / len(arts)), n80, _pc(n80, len(arts)), len(faibles), part_faibles,
                       _d(sum((arts[n][0] for n in faibles), ZERO))])
    lignes.sort(key=lambda l: -l[3])
    # semaines (blocs de 7 jours depuis la fin) : articles différents vendus
    au = min(ctx["au"], date.today())
    blocs = []
    debut = au - timedelta(days=6)
    while debut >= ctx["du"]:
        blocs.insert(0, debut)
        debut -= timedelta(days=7)
    par_bloc = defaultdict(set)
    for x in c:
        j = x.moment.date()
        b = next((b_ for b_ in reversed(blocs) if b_ <= j), None)
        if b is not None:
            par_bloc[b].update(l.nom for l in x.lignes)
    actifs = sum(l[1] for l in lignes)
    faibles = sum(l[8] for l in lignes)
    a_alleger = [l for l in lignes if l[1] >= 15 and l[9] >= 70]
    r = RapportGestion()
    r.entetes = ["Catégorie", "Articles vendus", "Articles vendus avant", "Ventes nettes", "Part des ventes %",
                 "Ventes par article", "Articles pour 80 % des ventes", "Part des articles pour 80 % %",
                 "Articles peu vendus (2 commandes ou moins)", "Part des articles peu vendus %",
                 "Ventes des articles peu vendus"]
    r.lignes = lignes
    r.cartes = [("Articles vendus", "n", actifs), ("Catégories", "n", len(lignes)),
                ("Articles peu vendus", "n", faibles), ("Part des articles peu vendus", "%", _pc(faibles, actifs)),
                ("Catégories à alléger", "n", len(a_alleger))]
    r.titre_evolution = "Articles différents vendus par semaine"
    r.genre_evolution = "barres"
    r.unite_evolution = ""
    r.etiquettes = [_etiquette(b) for b in blocs]
    r.series = [(_t("Articles différents"), [Decimal(len(par_bloc.get(b, ()))) for b in blocs])]
    r.titre_repartition = "Ventes par article selon la catégorie"
    r.genre_repartition = "classement"
    r.repartition = [(l[0], l[5]) for l in sorted(lignes, key=lambda l: -l[5])[:8]]
    constats = [_k(None, "Article peu vendu : 2 commandes ou moins dans la période. Catégorie à alléger : au moins 15 "
                   "articles vendus dont 70 % ou plus se vendent à peine (place en rayon, stock dormant, péremption).")]
    if lignes:
        constats.append(_k("info", "{n} article(s) différents vendus ; {f} ({p} %) se vendent à peine et font {v} de "
                                   "ventes.", n=actifs, f=faibles, p=_nb(_pc(faibles, actifs)),
                           v=_argent(sum((l[10] for l in lignes), ZERO))))
        meilleure = max(lignes, key=lambda l: l[5])
        constats.append(_k("bon", "Catégorie la plus productive : « {c} » ({v} par article vendu).", c=meilleure[0],
                           v=_argent(meilleure[5])))
    for l in sorted(a_alleger, key=lambda l: -l[9])[:3]:
        constats.append(_k("attention", "« {c} » : {f} de ses {n} articles se vendent à peine ({p} %) : réduire les "
                                        "références ou les mettre en avant.", c=l[0], f=l[8], n=l[1], p=_nb(l[9], 0)))
    r.alleger = a_alleger
    r.note = _note(constats)
    return r


# --------------------------------------------------------------------------------------------- prix et volume
def prix_volume(c, avant, ctx) -> RapportGestion:
    """Indice des prix (Laspeyres) des articles vendus dans les deux périodes : prix affiché moyen (ventes avant
    rabais / quantité) de maintenant appliqué aux quantités d'avant ; la croissance des ventes est séparée en effet
    des prix et effet du volume (croissance « hors hausse des prix »)."""
    def cumul(cmds):
        g = defaultdict(lambda: [ZERO, ZERO, ""])  # quantité, brut, catégorie
        for x in cmds:
            for l in x.lignes:
                if l.quantite_vendue > 0 and l.ventes_brutes > 0:
                    a = g[l.nom]
                    a[0] += l.quantite_vendue
                    a[1] += l.ventes_brutes
                    a[2] = l.categorie
        return g

    g1, g0 = cumul(c), cumul(avant)
    communs = [n for n in g1 if n in g0]
    lignes, par_cat = [], defaultdict(lambda: [ZERO, ZERO])
    base = sum((g0[n][1] for n in communs), ZERO)
    for n in communs:
        q0, b0, _cat = g0[n]
        q1, b1, cat = g1[n]
        p0, p1 = b0 / q0, b1 / q1
        par_cat[cat][0] += p1 * q0
        par_cat[cat][1] += b0
        lignes.append([n, cat, _d(p0), _d(p1), _pc(p1 - p0, p0), _d(q0, "0.001"), _d(q1, "0.001"),
                       _pc(b0, base) if base else ZERO])
    panier_courant = sum((g1[n][1] / g1[n][0] * g0[n][0] for n in communs), ZERO)
    indice = _d(panier_courant * 100 / base, "0.1") if base else Decimal(100)
    v1 = sum((x.nettes for x in c), ZERO)
    v0 = sum((x.nettes for x in avant), ZERO)
    croissance = _pc(v1 - v0, v0) if v0 else ZERO
    volume = _d(((v1 / v0) / (indice / 100) - 1) * 100, "0.1") if v0 and indice else ZERO
    plus = [l for l in lignes if l[4] >= 2]
    moins = [l for l in lignes if l[4] <= -2]
    lignes.sort(key=lambda l: -(abs(l[4]) * l[7]))
    cats = sorted(((cat, _d(v[0] * 100 / v[1] - 100, "0.1")) for cat, v in par_cat.items() if v[1] > 0),
                  key=lambda kv: -kv[1])
    r = RapportGestion()
    r.entetes = ["Article", "Catégorie", "Prix moyen avant", "Prix moyen maintenant", "Variation du prix %",
                 "Quantité avant", "Quantité maintenant", "Poids dans l'indice %"]
    r.lignes = lignes
    r.cartes = [("Indice des prix (100 = période d'avant)", "n", indice), ("Hausse des prix", "%", _d(indice - 100, "0.1")),
                ("Croissance des ventes", "%", croissance), ("Croissance en volume (hors prix)", "%", volume),
                ("Articles plus chers", "n", len(plus)), ("Articles moins chers", "n", len(moins))]
    r.titre_evolution = "Croissance des ventes : effet des prix et effet du volume (%)"
    r.genre_evolution = "barres"
    r.unite_evolution = "%"
    r.etiquettes = [_t("Ventes"), _t("Prix"), _t("Volume")]
    r.series = [(_t("Variation"), [croissance, _d(indice - 100, "0.1"), volume])]
    r.titre_repartition = "Hausse des prix par catégorie (%)"
    r.genre_repartition = "classement"
    r.argent_repartition = False
    r.repartition = [_signe(cat, v) for cat, v in cats[:4] + [x for x in cats[-4:] if x not in cats[:4]] if v]
    constats = [_k(None, "Indice des prix : prix affichés moyens d'aujourd'hui appliqués aux quantités vendues la "
                   "période d'avant, pour les articles vendus dans les deux périodes (100 = mêmes prix). Croissance en "
                   "volume : croissance des ventes sans la hausse des prix.")]
    if not communs:
        constats.append(_k("info", "Aucun article vendu dans les deux périodes : rien à comparer."))
    else:
        constats.append(_k("info", "Les prix ont varié de {p} % ; les ventes de {v} %, soit {q} % en volume.",
                           p=_nb(indice - 100), v=_nb(croissance), q=_nb(volume)))
        if volume <= -3 and indice >= 103:
            constats.append(_k("attention", "Les ventes tiennent grâce aux prix : on vend {q} % de marchandise en moins."
                               , q=_nb(abs(volume))))
        elif volume >= 3:
            constats.append(_k("bon", "On vend plus de marchandise : +{q} % en volume, au-delà de l'effet des prix.",
                               q=_nb(volume)))
    r.volume_en_baisse = bool(communs and volume <= -3 and indice >= 103)
    r.note = _note(constats)
    return r


# --------------------------------------------------------------------------------------------- clients
SEGMENTS = {
    "Champions": "Récompenser, demander un avis, offres en avant-première",
    "Fidèles": "Programme de fidélité, ventes complémentaires",
    "Nouveaux": "Accueil, faire revenir dans les 2 semaines",
    "Prometteurs": "Offre pour une 2e ou 3e visite",
    "À surveiller": "Offre ciblée avant qu'ils ne décrochent",
    "À risque": "Relancer : ils achetaient souvent mais ne viennent plus",
    "En sommeil": "Offre de retour",
    "Perdus": "Relance unique, sinon ne pas insister",
}


def _scores(valeurs: dict, inverse: bool = False) -> dict:
    """Note de 1 à 5 par quintile (5 = meilleur ; `inverse` : la plus petite valeur est la meilleure) ; des valeurs
    égales ont la même note (un client venu une fois n'est jamais « fréquent » parce qu'il a beaucoup dépensé)."""
    n = len(valeurs)
    tries = sorted(valeurs.values(), reverse=inverse)
    rang_premier = {}
    for i, v in enumerate(tries):
        rang_premier.setdefault(v, i)  # nombre de valeurs moins bonnes que v
    return {k: min(5, 1 + rang_premier[v] * 5 // n) for k, v in valeurs.items()} if n else {}


def _segment(r: int, f: int) -> str:
    if r >= 4 and f >= 4:
        return "Champions"
    if f >= 4 or (r >= 3 and f >= 3):
        return "Fidèles"
    if r >= 4 and f <= 1:
        return "Nouveaux"
    if r >= 3:
        return "Prometteurs"
    if f >= 3:
        return "À risque"
    if r == 2 and f == 2:
        return "À surveiller"
    if r == 2 or f == 2:
        return "En sommeil"
    return "Perdus"


def rfm(c, avant, ctx) -> RapportGestion:
    fin = min(ctx["au"], date.today())
    clients = defaultdict(lambda: {"cmd": 0, "nettes": ZERO, "dernier": None, "premier": None})
    anonymes = ZERO
    for x in c:
        if x.client == "Sans client":
            anonymes += x.nettes
            continue
        g = clients[x.client]
        g["cmd"] += 1
        g["nettes"] += x.nettes
        j = x.moment.date()
        g["dernier"] = max(g["dernier"] or j, j)
        g["premier"] = min(g["premier"] or j, j)
    recence = {k: (fin - g["dernier"]).days for k, g in clients.items()}
    sr = _scores(recence, inverse=True)
    sf = _scores({k: g["cmd"] for k, g in clients.items()})
    sm = _scores({k: g["nettes"] for k, g in clients.items()})
    lignes, nb_seg, ventes_seg = [], defaultdict(int), defaultdict(Decimal)
    for k, g in sorted(clients.items(), key=lambda kv: -kv[1]["nettes"]):
        seg = _segment(sr[k], sf[k])
        nb_seg[seg] += 1
        ventes_seg[seg] += g["nettes"]
        lignes.append([k, _t(seg), sr[k], sf[k], sm[k], f"{sr[k]}{sf[k]}{sm[k]}", str(g["premier"]), str(g["dernier"]),
                       recence[k], g["cmd"], _d(g["nettes"]), _d(g["nettes"] / g["cmd"]), _t(SEGMENTS[seg])])
    total = sum((g["nettes"] for g in clients.values()), ZERO)
    r = RapportGestion()
    r.unite_evolution = ""
    r.entetes = ["Client", "Groupe de clients", "Achat récent (1-5)", "Achète souvent (1-5)", "Dépense (1-5)", "Note du client (récent, fréquent, montant)",
                 "Premier achat", "Dernier achat", "Jours depuis", "Commandes", "Ventes nettes", "Panier moyen",
                 "Action suggérée"]
    r.lignes = lignes
    r.cartes = [("Clients identifiés", "n", len(clients)),
                ("Part des ventes avec un client", "%", _pc(total, total + anonymes)),
                ("Champions", "n", nb_seg["Champions"]), ("À risque", "n", nb_seg["À risque"]),
                ("Valeur moyenne d'un client", "$", _d(total / len(clients)) if clients else ZERO),
                ("Commandes par client", "n", _d(Decimal(sum(g["cmd"] for g in clients.values())) / len(clients), "0.1")
                 if clients else ZERO)]
    tranches = [(1, 1), (2, 2), (3, 5), (6, 10), (11, None)]
    r.titre_evolution = "Clients selon le nombre de commandes"
    r.genre_evolution = "barres"
    r.etiquettes = [str(a) if a == b else f"{a} – {b}" if b else f"{a} {_t('et plus')}" for a, b in tranches]
    r.series = [("Clients", [sum(1 for g in clients.values() if g["cmd"] >= a and (b is None or g["cmd"] <= b))
                             for a, b in tranches])]
    r.titre_repartition = "Ventes nettes par groupe de clients"
    r.repartition = [(_t(k), _d(v)) for k, v in sorted(ventes_seg.items(), key=lambda kv: -kv[1])]
    constats = [_k(None, "Chaque client est noté de 1 à 5 (5 = meilleur) sur l'achat récent, la fréquence et la dépense, parmi les clients identifiés de la "
                   "période ; choisissez une longue période (6 à 12 mois) pour des groupes fiables.")]
    if total + anonymes:
        constats.append(_k(None, "Seules {p} % des ventes sont rattachées à un client : demander le client à la caisse "
                           "rendrait cette analyse plus complète.", p=_nb(_pc(total, total + anonymes), 0))
                        if total / (total + anonymes) < Decimal("0.3") else "")
    if nb_seg["À risque"]:
        constats.append(_k(None, "{n} client(s) à risque ({v} de ventes) : à relancer en priorité.", n=nb_seg["À risque"],
                           v=_argent(ventes_seg["À risque"])))
    r.note = _note(constats)
    return r


def fidelite(c, avant, ctx) -> RapportGestion:
    def cumul(cmds):
        d = defaultdict(lambda: {"cmd": 0, "nettes": ZERO, "dates": []})
        for x in cmds:
            if x.client != "Sans client":
                g = d[x.client]
                g["cmd"] += 1
                g["nettes"] += x.nettes
                g["dates"].append(x.moment.date())
        return d

    maintenant, precedent = cumul(c), cumul(avant)
    retenus = set(maintenant) & set(precedent)
    nouveaux = set(maintenant) - set(precedent)
    perdus = set(precedent) - set(maintenant)
    intervalles = []
    for g in maintenant.values():
        dates = sorted(set(g["dates"]))
        intervalles += [(b - a).days for a, b in zip(dates, dates[1:])]
    ventes_retenus = sum((maintenant[k]["nettes"] for k in retenus), ZERO)
    ventes_nouveaux = sum((maintenant[k]["nettes"] for k in nouveaux), ZERO)
    ventes_perdues = sum((precedent[k]["nettes"] for k in perdus), ZERO)
    total = ventes_retenus + ventes_nouveaux
    r = RapportGestion()
    r.unite_evolution = ""
    r.cartes = [("Clients identifiés", "n", len(maintenant)),
                ("Taux de rétention", "%", _pc(len(retenus), len(precedent))),
                ("Clients retenus", "n", len(retenus)), ("Nouveaux clients", "n", len(nouveaux)),
                ("Clients perdus", "n", len(perdus)),
                ("Jours entre deux achats (médiane)", "n", _d(_quantile(intervalles, 0.5), "0.1"))]
    lignes = []
    statut = {**{k: "Retenu" for k in retenus}, **{k: "Nouveau" for k in nouveaux}, **{k: "Perdu" for k in perdus}}
    for k in sorted(statut, key=lambda k: (-(maintenant[k]["nettes"] if k in maintenant else ZERO),
                                           -(precedent[k]["nettes"] if k in precedent else ZERO))):
        a = maintenant.get(k, {"cmd": 0, "nettes": ZERO, "dates": []})
        b = precedent.get(k, {"cmd": 0, "nettes": ZERO, "dates": []})
        dernier = max(a["dates"] or b["dates"])
        lignes.append([k, _t(statut[k]), a["cmd"], _d(a["nettes"]), b["cmd"], _d(b["nettes"]),
                       _d(a["nettes"] - b["nettes"]), str(dernier)])
    r.entetes = ["Client", "Statut", "Commandes", "Ventes nettes", "Commandes (comparaison)",
                 "Ventes nettes (comparaison)", "Écart", "Dernier achat"]
    r.lignes = lignes
    # par jour : clients déjà venus (avant dans la période ou dans la comparaison) et premières visites
    deja = set(precedent)
    jours = _jours(ctx["du"], ctx["au"])
    revenus_j, premiers_j = defaultdict(int), defaultdict(int)
    for x in sorted(c, key=lambda x: x.moment):
        if x.client == "Sans client":
            continue
        j = x.moment.date()
        if x.client in deja:
            revenus_j[j] += 1
        else:
            premiers_j[j] += 1
            deja.add(x.client)
    r.titre_evolution = "Visites de clients identifiés : déjà venus et premières visites"
    r.etiquettes = [_etiquette(j) for j in jours]
    r.series = [("Clients déjà venus", [revenus_j.get(j, 0) for j in jours]),
                ("Premières visites", [premiers_j.get(j, 0) for j in jours])]
    r.titre_repartition = "Clients retenus, nouveaux et perdus"
    r.argent_repartition = False
    r.repartition = [(_t("Retenus"), Decimal(len(retenus))), (_t("Nouveaux"), Decimal(len(nouveaux))),
                     (_t("Perdus"), Decimal(len(perdus)))]
    constats = [_k(None, "Retenu : client venu dans la période choisie et dans la période de comparaison ; nouveau : "
                   "seulement dans la période choisie ; perdu : seulement dans la période de comparaison.")]
    if precedent:
        constats.append(_k("bon" if len(retenus) * 100 >= 30 * len(precedent) else "attention",
                           "{p} % des clients de la période de comparaison sont revenus.",
                           p=_nb(_pc(len(retenus), len(precedent)), 0)))
    if total:
        constats.append(_k(None, "Clients retenus : {p} % des ventes des clients identifiés ; ventes des clients perdus "
                           "dans la comparaison : {v}.", p=_nb(_pc(ventes_retenus, total), 0), v=_argent(ventes_perdues)))
    if intervalles:
        constats.append(_k(None, "Un client revient en général tous les {j} jours.",
                           j=_nb(_quantile(intervalles, 0.5), 0)))
    r.note = _note(constats)
    return r


# --------------------------------------------------------------------------------------------- prix
SEUIL_CHANGEMENT_PRIX = 0.03   # un prix qui bouge de 3 % ou plus et le reste = changement de prix
JOURS_MIN_PRIX = 5             # jours de vente au moins avant et après le changement
QUANTITE_MIN_PRIX = 20         # unités vendues au moins sur les deux périodes comparées


def _lecture_elasticite(e: float | None) -> str:
    if e is None:
        return "Effet non mesurable"
    if e > 0:
        return "Ventes dans le même sens que le prix"
    if e > -0.5:
        return "Peu sensible au prix"
    if e > -1.5:
        return "Sensible au prix"
    return "Très sensible au prix"


def prix(c, avant, ctx) -> RapportGestion:
    """Changements de prix repérés dans les ventes (prix unitaire brut du jour) et effet sur les quantités : quantité
    par jour d'ouverture avant et après (même nombre de jours de chaque côté, 28 au plus), élasticité = variation
    des quantités en % / variation du prix en %. Prix variables (prix qui bouge sans cesse) écartés."""
    ouverts = sorted({x.moment.date() for x in c})
    par_article = defaultdict(lambda: {"cat": "", "jours": defaultdict(lambda: [0.0, 0.0, 0.0])})
    for x in c:
        j = x.moment.date()
        for l in x.lignes:
            if l.quantite_vendue > 0 and l.ventes_brutes > 0:
                a = par_article[l.nom]
                a["cat"] = l.categorie
                g = a["jours"][j]
                g[0] += float(l.ventes_brutes)
                g[1] += float(l.quantite_vendue)
                g[2] += float(l.ventes_nettes)
    lignes, semaines_h, semaines_b, lectures = [], defaultdict(int), defaultdict(int), defaultdict(int)
    for nom, a in par_article.items():
        jours = sorted(a["jours"])
        if len(jours) < 2 * JOURS_MIN_PRIX:
            continue
        niveaux = [round(a["jours"][j][0] / a["jours"][j][1], 2) for j in jours]
        # dernier changement durable : le prix du jour s'écarte de 3 % du prix d'avant, et les jours suivants restent
        # à 2 % du nouveau prix (80 % d'entre eux au moins)
        coupure = None
        for k in range(len(jours) - JOURS_MIN_PRIX, JOURS_MIN_PRIX - 1, -1):
            avant_p = st.median(niveaux[max(0, k - 14):k])
            apres_p = st.median(niveaux[k:k + 14])
            if not avant_p or abs(apres_p - avant_p) / avant_p < SEUIL_CHANGEMENT_PRIX:
                continue
            stables_apres = sum(1 for v in niveaux[k:] if abs(v - apres_p) <= 0.02 * apres_p) / len(niveaux[k:])
            stables_avant = sum(1 for v in niveaux[max(0, k - 14):k] if abs(v - avant_p) <= 0.02 * avant_p) / len(
                niveaux[max(0, k - 14):k])
            if stables_apres >= 0.8 and stables_avant >= 0.8:
                while k > 1 and abs(niveaux[k - 1] - apres_p) <= 0.02 * apres_p:
                    k -= 1  # premier jour au nouveau prix
                coupure = k
                break
        if coupure is None:
            continue
        jour = jours[coupure]
        rang = ouverts.index(jour)
        n = min(28, rang, len(ouverts) - rang)
        if n < JOURS_MIN_PRIX:
            continue
        fen_avant, fen_apres = ouverts[rang - n:rang], ouverts[rang:rang + n]

        def somme(fenetre, i):
            return sum(a["jours"][j][i] for j in fenetre if j in a["jours"])

        brut_av, q_av, net_av = somme(fen_avant, 0), somme(fen_avant, 1), somme(fen_avant, 2)
        brut_ap, q_ap, net_ap = somme(fen_apres, 0), somme(fen_apres, 1), somme(fen_apres, 2)
        jours_av = sum(1 for j in fen_avant if j in a["jours"])
        jours_ap = sum(1 for j in fen_apres if j in a["jours"])
        if jours_av < JOURS_MIN_PRIX or jours_ap < JOURS_MIN_PRIX or q_av + q_ap < QUANTITE_MIN_PRIX:
            continue  # trop peu de ventes de part et d'autre pour mesurer un effet
        p_av, p_ap = brut_av / q_av, brut_ap / q_ap
        dp = (p_ap - p_av) / p_av
        if abs(dp) < SEUIL_CHANGEMENT_PRIX:
            continue  # prix moyen des deux périodes presque égal : pas un vrai changement
        dq = (q_ap - q_av) / q_av
        e = dq / dp
        lecture = _lecture_elasticite(e)
        lectures[lecture] += 1
        lundi = jour - timedelta(days=jour.weekday())
        (semaines_h if dp > 0 else semaines_b)[lundi] += 1
        lignes.append([nom, a["cat"], str(jour), _d(p_av), _d(p_ap), _d(dp * 100, "0.1"), _d(q_av / n, "0.001"),
                       _d(q_ap / n, "0.001"), _d(dq * 100, "0.1"), _d(e, "0.01") if e is not None else None,
                       _d(net_av / n), _d(net_ap / n), _pc(net_ap - net_av, net_av) if net_av else None, n,
                       _t(lecture)])
    lignes.sort(key=lambda l: l[2], reverse=True)
    r = RapportGestion()
    r.entetes = ["Article", "Catégorie", "Date du changement", "Prix avant", "Prix après", "Variation du prix %",
                 "Quantité par jour avant", "Quantité par jour après", "Variation des quantités %", "Sensibilité au prix",
                 "Ventes nettes par jour avant", "Ventes nettes par jour après", "Effet sur les ventes %",
                 "Jours comparés", "Lecture"]
    r.lignes = lignes
    hausses = [l for l in lignes if l[5] > 0]
    elasticites = [float(l[9]) for l in lignes if l[9] is not None]
    effet = sum((l[11] - l[10] for l in lignes), ZERO)
    r.cartes = [("Changements de prix", "n", len(lignes)), ("Hausses", "n", len(hausses)),
                ("Baisses", "n", len(lignes) - len(hausses)),
                ("Sensibilité au prix (typique)", "t", _nb(st.median(elasticites), 2) if elasticites else "—"),
                ("Effet sur les ventes par jour", "$", _d(effet))]
    jours = _jours(ctx["du"], ctx["au"])
    lundis = sorted({j - timedelta(days=j.weekday()) for j in jours})
    r.titre_evolution = "Changements de prix par semaine"
    r.genre_evolution = "barres"
    r.unite_evolution = ""
    r.etiquettes = [_etiquette(l) for l in lundis]
    r.series = [("Hausses", [semaines_h.get(l, 0) for l in lundis]), ("Baisses", [semaines_b.get(l, 0) for l in lundis])]
    r.titre_repartition = "Sensibilité au prix des articles"
    r.argent_repartition = False
    r.repartition = [(_t(k), Decimal(v)) for k, v in sorted(lectures.items(), key=lambda kv: -kv[1])]
    constats = [_k(None, "Changement de prix : le prix unitaire du jour s'écarte d'au moins 3 % et reste stable ensuite ; "
                   "quantités comparées sur le même nombre de jours d'ouverture avant et après (28 au plus). "
                   "Sensibilité −1 : une hausse de prix de 10 % fait perdre 10 % des quantités vendues. Une rupture de stock, la saison ou "
                   "une promotion peuvent aussi jouer : à lire avec prudence.")]
    if elasticites:
        constats.append(_k(None, "Sensibilité au prix typique {e} : {s}.", e=_nb(st.median(elasticites), 2),
                           s=_t(_lecture_elasticite(st.median(elasticites))).lower()))
    if lignes:
        meilleur = max(lignes, key=lambda l: l[11] - l[10])
        pire = min(lignes, key=lambda l: l[11] - l[10])
        if meilleur[11] > meilleur[10]:
            constats.append(_k(None, "Meilleur changement : {a} ({p} → {q}), {v} de ventes par jour en plus.", a=meilleur[0],
                               p=_argent(meilleur[3]), q=_argent(meilleur[4]), v=_argent(meilleur[11] - meilleur[10])))
        if pire[11] < pire[10]:
            constats.append(_k(None, "Changement le plus coûteux : {a} ({p} → {q}), {v} de ventes par jour.", a=pire[0],
                               p=_argent(pire[3]), q=_argent(pire[4]), v=_argent(pire[11] - pire[10])))
    else:
        constats.append(_k(None, "Aucun changement de prix durable dans la période : choisissez une période plus longue."))
    r.note = _note(constats)
    return r


# --------------------------------------------------------------------------------------------- cohortes
def cohortes(c, avant, ctx) -> RapportGestion:
    """Clients identifiés regroupés par mois de leur premier achat (dans la période et sa comparaison) : part de
    chaque groupe qui revient acheter 1, 2, 3… mois plus tard."""
    achats = defaultdict(set)
    ventes = defaultdict(Decimal)
    for x in list(avant) + list(c):
        if x.client != "Sans client":
            j = x.moment.date()
            achats[x.client].add((j.year, j.month))
            ventes[x.client] += x.nettes
    mois_tous = sorted({m for v in achats.values() for m in v})
    if not mois_tous:
        r = RapportGestion(note=_note([_t("Aucun client identifié dans la période.")]))
        r.entetes, r.cartes = ["Mois du premier achat"], [("Mois suivis", "n", 0)]
        return r
    rang_mois = {m: i for i, m in enumerate(mois_tous)}
    groupes = defaultdict(list)
    for client, mois in achats.items():
        groupes[min(mois)].append(client)
    largeur = len(mois_tous)
    lignes, moyennes = [], defaultdict(list)
    for m in sorted(groupes):
        clients = groupes[m]
        rangee = [f"{m[0]}-{m[1]:02d}", len(clients), _d(sum((ventes[k] for k in clients), ZERO) / len(clients))]
        for k in range(1, largeur):
            cible = rang_mois[m] + k
            if cible >= largeur:
                rangee.append(None)
                continue
            revenus = sum(1 for cl in clients if mois_tous[cible] in achats[cl])
            rangee.append(_pc(revenus, len(clients)))
            moyennes[k].append((revenus, len(clients)))
        lignes.append(rangee)
    r = RapportGestion()
    r.unite_evolution = "%"
    r.entetes = ["Mois du premier achat", "Nouveaux clients", "Ventes nettes par client"] + [
        _t("Mois +{k} %", k=k) for k in range(1, largeur)]
    r.lignes = lignes
    courbe = [_pc(sum(a for a, _b in moyennes[k]), sum(b for _a, b in moyennes[k])) for k in range(1, largeur)]
    r.cartes = [("Mois suivis", "n", len(groupes)), ("Clients suivis", "n", len(achats)),
                ("Reviennent le mois suivant", "%", courbe[0] if courbe else ZERO),
                ("Reviennent 2 mois plus tard", "%", courbe[1] if len(courbe) > 1 else ZERO)]
    r.titre_evolution = "Part des clients qui reviennent, mois après le premier achat"
    r.etiquettes = [_t("Mois +{k}", k=k) for k in range(1, largeur)]
    r.series = [("Clients qui reviennent", courbe)]
    if len(r.etiquettes) <= 1:
        r.genre_evolution = "barres"
    r.titre_repartition = "Nouveaux clients par mois"
    r.genre_repartition = "classement"
    r.argent_repartition = False
    r.repartition = [(l[0], Decimal(l[1])) for l in lignes[-8:]]
    constats = [_k(None, "Chaque ligne suit les clients identifiés dont le premier achat (dans la période choisie et sa "
                   "comparaison) tombe ce mois-là ; « Mois +1 % » : part d'entre eux revenus le mois suivant. "
                   "Choisissez au moins 6 mois.")]
    if courbe:
        constats.append(_k(None, "{p} % des nouveaux clients reviennent le mois suivant.", p=_nb(courbe[0], 0)))
    r.note = _note(constats)
    return r


# --------------------------------------------------------------------------------------------- synthèse
def synthese(c, avant, ctx) -> RapportGestion:
    """Synthèse pour la direction : cartes à feux de couleur, constats triés (à agir, à surveiller, bon) et liste
    priorisée des décisions à prendre, avec l'endroit où les vérifier."""
    resultats = {}
    for libelle, cle, fonction, section, _apres in ANALYSES:
        if cle == "a_synthese":
            continue
        try:
            resultats[cle] = (libelle, section, _completer(cle, fonction(c, avant, ctx)))
        except Exception as erreur:  # noqa: BLE001 — une analyse en échec n'empêche pas les autres
            resultats[cle] = (libelle, section,
                              RapportGestion(note=MARQUES["attention"] + _t("Analyse impossible : {e}", e=erreur)))
    sous = {cle: res[2] for cle, res in resultats.items()}
    ordre = {"alerte": 0, "attention": 1, "bon": 2}
    constats = []
    for cle, (libelle, section, r) in resultats.items():
        for ligne in (r.note or "").splitlines():
            niveau, texte = niveau_constat(ligne)
            if niveau != "info" and texte:  # les définitions et précisions restent dans leur analyse
                constats.append((ordre[niveau], niveau, texte))
    constats.sort(key=lambda x: x[0])
    cartes = {}
    for cle, (_l, _s, r) in resultats.items():
        for titre, genre, valeur in r.cartes:
            cartes[(cle, titre)] = (titre, genre, valeur)
    choisies = [("a_variation", "Ventes nettes"), ("a_variation", "Variation"), ("a_rythme", "Atteinte projetée"), ("a_tendance", "Hausse ou baisse par semaine"),
                ("a_tendance", "Projection des 30 prochains jours"), ("a_paniers", "Panier typique (médian)"),
                ("a_anomalies", "Anomalies relevées"), ("a_matrice", "Très vendus, peu rentables"), ("a_fidelite", "Taux de rétention"),
                ("a_marge", "Marge brute"), ("a_achalandage", "Heures chargées")]
    if not ctx.get("couts"):  # sans coûts Sage, ni rentabilité ni marge
        choisies.remove(("a_matrice", "Très vendus, peu rentables"))
        choisies.remove(("a_marge", "Marge brute"))
    r = RapportGestion()
    r.cartes = [cartes[k] for k in choisies if k in cartes]
    vide = RapportGestion()
    tendance_r, variation_r = sous.get("a_tendance", vide), sous.get("a_variation", vide)
    r.titre_evolution, r.etiquettes, r.series = tendance_r.titre_evolution, tendance_r.etiquettes, tendance_r.series
    r.titre_repartition, r.genre_repartition, r.repartition = (variation_r.titre_repartition, "classement",
                                                               variation_r.repartition)
    r.graphiques = [g for g in (
        _principal(sous.get("a_paniers", vide)), _repartition(sous.get("a_anomalies", vide)),
        _repartition(sous.get("a_associations", vide)), _repartition(sous.get("a_fidelite", vide)))
        if g["titre"] and (g["elements"] or any(v for _n, vs in g["series"] for v in vs))]
    # chaque décision, puis la liste de ce qu'elle concerne (articles, clients, employés, commandes) : demande du
    # propriétaire du 2026-11-08 « je veux avoir la liste des articles concernés dans les décisions »
    toutes = sorted(_decisions(sous), key=lambda x: x[0])
    r.decisions = toutes  # (priorité, décision, pourquoi, section, analyse, éléments) : courriel du matin
    r.entetes = ["Priorité", "Décision à prendre", "Concerné", "Détail", "Où regarder"]
    r.lignes, r.ids_commandes = [], []
    for p, decision, raison, section, libelle, elements in toutes:
        r.lignes.append([_t(PRIORITES[p]), _t(decision),
                         _t("{n} élément(s)", n=len(elements)) if elements else "—", raison,
                         _t(section) + " > " + _t(libelle)])
        r.ids_commandes.append("")
        for nom, detail, ident in elements[:MAX_CONCERNES]:
            r.lignes.append(["", "", nom, detail, ""])
            r.ids_commandes.append(ident or "")
        if len(elements) > MAX_CONCERNES:
            r.lignes.append(["", "", _t("… et {n} autre(s)", n=len(elements) - MAX_CONCERNES),
                             _t("Liste complète : {o}", o=_t(section) + " > " + _t(libelle)), ""])
            r.ids_commandes.append("")
    nb = {n: sum(1 for x in constats if x[1] == n) for n in ("alerte", "attention", "bon")}
    entete = _t("{a} point(s) à agir, {s} à surveiller, {b} point(s) positif(s) ; {d} décision(s) proposée(s).",
                a=nb["alerte"], s=nb["attention"], b=nb["bon"], d=len(toutes))
    # lecture de la direction : les décisions d'abord (couleur = priorité) avec les premiers éléments concernés, puis
    # les points positifs ; le détail de chaque constat reste dans son analyse
    couleur_priorite = {1: "alerte", 2: "attention", 3: "info"}
    decisions = [MARQUES[couleur_priorite[p]] + _t("Décision : {d} — {r}", d=_t(d), r=raison) + resume_concernes(el)
                 for p, d, raison, _s, _l, el in toutes]
    positifs = [MARQUES["bon"] + texte for _o, n, texte in constats if n == "bon"]
    r.note = _note([MARQUES["info"] + entete] + decisions + positifs)
    return r


PRIORITES = {1: "1 — Haute", 2: "2 — Moyenne", 3: "3 — Basse"}
MAX_CONCERNES = 50      # éléments concernés listés sous une décision (la liste complète reste dans son analyse)
NOMS_DANS_LE_RESUME = 5  # éléments cités dans le bandeau de la décision et dans le courriel du matin


def resume_concernes(elements) -> str:
    """« Concernés : A, B, C, D, E et 17 autre(s). » (bandeau de la décision, courriel du matin)."""
    if not elements:
        return ""
    noms = ", ".join(n for n, _d_, _i in elements[:NOMS_DANS_LE_RESUME])
    reste = len(elements) - NOMS_DANS_LE_RESUME
    return " " + (_t("Concernés : {n} et {r} autre(s).", n=noms, r=reste) if reste > 0
                  else _t("Concernés : {n}.", n=noms))


def _pourcent(v) -> str:
    return "—" if v is None else _nb(v) + " %"


def _carte(r, titre, defaut=None):
    return next((v for t_, _g, v in r.cartes if t_ == titre), defaut)


def _decisions(sous: dict) -> list[tuple]:
    """Décisions proposées à la direction : (priorité, décision, pourquoi, section, analyse, éléments concernés) ;
    éléments = [(nom, détail, identifiant de commande Clover ou "")], du plus important au moins important."""
    vide = RapportGestion()
    sortie = []

    def ajouter(priorite, decision, raison, cle, elements=()):
        libelle, _c_, _f, section, _a = next(a for a in ANALYSES if a[1] == cle)
        sortie.append((priorite, decision, raison, section, libelle, list(elements)))

    var = sous.get("a_variation", vide)
    variation_ = _carte(var, "Variation")
    if variation_ is not None and variation_ < -5:
        baisses = sorted((l for l in var.lignes if l[0] == _t("Catégorie") and l[4] < 0), key=lambda l: l[4])
        cible = baisses[0][1] if baisses else ""
        articles_b = sorted((l for l in var.lignes if l[0] == _t("Article") and l[4] < 0), key=lambda l: l[4])
        ajouter(1, "Agir sur la baisse des ventes", _t("Ventes nettes {v} % ; plus forte baisse : {c}.",
                                                       v=_nb(variation_), c=cible), "a_variation",
                [(l[1], _t("{t} : écart {e} ({p}) ; {a} contre {b}", t=l[0], e=_argent(l[4]), p=_pourcent(l[5]),
                           a=_argent(l[2]), b=_argent(l[3])), "") for l in baisses + articles_b])
    effet_panier = _carte(var, "Effet du montant moyen par vente")
    if effet_panier is not None and effet_panier < 0:
        ajouter(2, "Relever le panier moyen (ventes complémentaires, offres groupées)",
                _t("Le panier plus petit coûte {v}.", v=_argent(effet_panier)), "a_variation")
    ano = sous.get("a_anomalies", vide)
    ids_ano = list(ano.ids_commandes) + [""] * len(ano.lignes)

    def anomalies_de(type_):
        return [(l, ids_ano[i]) for i, l in enumerate(ano.lignes) if l[0] == _t(type_)]

    if (_carte(ano, "Rabais de 50 % ou plus") or 0) > 0:
        ajouter(1, "Contrôler les rabais de 50 % et plus avec les employés concernés",
                _t("{n} commande(s) à fort rabais.", n=_carte(ano, "Rabais de 50 % ou plus")), "a_anomalies",
                [(l[2], _t("{q} — {d} ; payé {m} sur {b}", q=l[1], d=l[3], m=_argent(l[4]), b=_argent(l[5])), i)
                 for l, i in anomalies_de("Rabais de 50 % ou plus")])
    if (_carte(ano, "Prix inhabituels") or 0) > 0:
        ajouter(2, "Vérifier les prix dans Clover (prix saisis à la main ou erronés)",
                _t("{n} ligne(s) à un prix inhabituel.", n=_carte(ano, "Prix inhabituels")), "a_anomalies",
                [(l[2], _t("{q} — {d} : {m} au lieu de {b}", q=l[1], d=l[3], m=_argent(l[4]), b=_argent(l[5])), i)
                 for l, i in anomalies_de("Prix inhabituel")])
    ryt = sous.get("a_rythme", vide)
    projetee, restants = _carte(ryt, "Atteinte projetée"), _carte(ryt, "Jours restants") or 0
    if restants and projetee is not None and _carte(ryt, "Objectif") and projetee < 95:
        ajouter(1, "Rattraper l'objectif de la période",
                _t("Projection à {p} % de l'objectif ; il faut {r} par jour sur {n} jour(s).", p=_nb(projetee),
                   r=_argent(_carte(ryt, "À faire par jour restant")), n=restants), "a_rythme",
                [(f"{l[0]} ({l[1]})", _t("Prévu {v} ; objectif du jour {o}", v=_argent(l[3]), o=_argent(l[4])), "")
                 for l in ryt.lignes if l[2] != _t("Réalisé")])
    tend = sous.get("a_tendance", vide)
    if (_carte(tend, "Hausse ou baisse par semaine") or 0) < 0:
        ajouter(2, "Préparer un plan pour inverser la tendance",
                _t("Ventes en baisse de {v} par semaine.", v=_argent(abs(_carte(tend, "Hausse ou baisse par semaine")))),
                "a_tendance")
    if tend.repartition:
        faible = tend.repartition[-1]
        if faible[1] < 80:
            ajouter(3, _t("Animer le {j} (promotion, dégustation)", j=faible[0]),
                    _t("Jour le plus faible : indice {i} (100 = moyenne).", i=_nb(faible[1], 0)), "a_tendance")
    mat = sous.get("a_matrice", vide)

    def articles_du_quadrant(quadrant, croissant=False):
        lignes = [l for l in mat.lignes if l[11] == _t(quadrant)]
        lignes.sort(key=lambda l: l[3], reverse=not croissant)
        return [(l[0], _t("{c} ; ventes {v} ({q} vendus) ; bénéfice {b} ; marge {m}", c=l[1], v=_argent(l[3]),
                          q=_nb(l[2], 0), b=_argent(l[9]) if l[9] is not None else "—", m=_pourcent(l[10])), "")
                for l in lignes]

    if (_carte(mat, "Très vendus, peu rentables") or 0) > 0:
        ajouter(1, "Augmenter le prix de vente ou négocier le prix d'achat des articles très vendus mais peu rentables",
                _t("{n} article(s) se vendent beaucoup mais rapportent peu par unité.", n=_carte(mat, "Très vendus, peu rentables")), "a_matrice",
                articles_du_quadrant("Très vendu, peu rentable"))
    if (_carte(mat, "Peu vendus, peu rentables") or 0) > 0:
        ajouter(3, "Réduire le stock ou retirer les articles peu vendus et peu rentables",
                _t("{n} article(s) peu vendus et peu rentables.", n=_carte(mat, "Peu vendus, peu rentables")), "a_matrice",
                articles_du_quadrant("Peu vendu, peu rentable", croissant=True))
    ass = sous.get("a_associations", vide)
    meilleure = _carte(ass, "Association la plus forte")
    if meilleure and meilleure != "—":
        paires = sorted((l for l in ass.lignes if l[0] == _t("Articles") and l[7] >= 2),
                        key=lambda l: -(l[7] * min(l[3], 20)))
        ajouter(3, _t("Placer côte à côte ou grouper : {p}", p=meilleure),
                _t("Articles achetés ensemble bien plus souvent que le hasard."), "a_associations",
                [(f"{l[1]} + {l[2]}", _t("{n} commande(s) ensemble ; {l} fois plus que le hasard ; {c}", n=l[3], l=_nb(l[7], 1),
                                         c=l[8]), "") for l in paires])
    prix_ = sous.get("a_prix", vide)
    couteux = sorted((l for l in prix_.lignes if l[11] < l[10] and l[5] > 0), key=lambda l: l[11] - l[10])
    if couteux:
        pire = couteux[0]
        ajouter(2, _t("Revoir la hausse de prix de {a}", a=pire[0]),
                _t("{v} de ventes par jour depuis la hausse.", v=_argent(pire[11] - pire[10])), "a_prix",
                [(l[0], _t("{j} : prix {a} → {b} ; ventes par jour {c} → {d}", j=l[2], a=_argent(l[3]),
                           b=_argent(l[4]), c=_argent(l[10]), d=_argent(l[11])), "") for l in couteux])
    emp = sous.get("a_employes", vide)
    # employés qui accordent plus du double du taux de rabais moyen (10 commandes au moins) ; rabais Direction et
    # comptes administrateurs exclus (état « Rabais Direction et administrateurs », règle du 2026-11-08)
    if emp.lignes:
        brut = sum((l[2] for l in emp.lignes), ZERO)
        moyen = (sum((l[2] * l[7] for l in emp.lignes), ZERO) / brut) if brut else ZERO
        trop = [l for l in emp.lignes if moyen and l[7] > moyen * 2 and l[1] >= 10]
        if trop:
            ajouter(1, "Encadrer les rabais accordés", _t("{n} employé(s) au-delà du double du taux moyen ({m} %) : {e}.",
                                                          n=len(trop), m=_nb(moyen), e=", ".join(
                                                              f"{l[0]} ({_nb(l[7])} %)" for l in trop)), "a_employes",
                    [(l[0], _t("Taux de rabais {t} ; {c} commande(s) ; ventes {v}", t=_pourcent(l[7]), c=l[1],
                               v=_argent(l[2])), "") for l in sorted(trop, key=lambda l: -l[7])])
    con = sous.get("a_concentration", vide)
    for l in con.lignes:
        if l[0] == _t("Employés") and l[2] >= 60:
            ajouter(2, "Former un deuxième vendeur principal", _t("{p} % des ventes passent par un seul employé.",
                                                                 p=_nb(l[2])), "a_concentration",
                    [(x[0], _t("{p} des ventes ; {c} commande(s)", p=_pourcent(x[3]), c=x[1]), "")
                     for x in sorted(emp.lignes, key=lambda x: -x[3])])
    rfm_ = sous.get("a_rfm", vide)

    def clients_du_segment(segment):
        return [(l[0], _t("Dernier achat {d} (il y a {j} jours) ; {c} commande(s) ; {v}", d=l[7], j=l[8], c=l[9],
                          v=_argent(l[10])), "") for l in rfm_.lignes if l[1] == _t(segment)]

    if (_carte(rfm_, "À risque") or 0) > 0:
        ajouter(2, "Relancer les clients à risque", _t("{n} client(s) qui achetaient souvent ne viennent plus.",
                                                       n=_carte(rfm_, "À risque")), "a_rfm",
                clients_du_segment("À risque"))
    part = _carte(rfm_, "Part des ventes avec un client")
    if part is not None and part < 30:
        ajouter(2, "Demander le client à la caisse (fidélité, relances)",
                _t("Seules {p} % des ventes sont rattachées à un client.", p=_nb(part, 0)), "a_rfm",
                [(x[0], _t("{p} des commandes avec un client ; {c} commande(s)", p=_pourcent(x[13]), c=x[1]), "")
                 for x in sorted(emp.lignes, key=lambda x: (x[13], -x[1]))])
    fid = sous.get("a_fidelite", vide)
    retention = _carte(fid, "Taux de rétention")
    if retention is not None and retention < 30 and _carte(fid, "Clients perdus"):
        perdus = sorted((l for l in fid.lignes if l[1] == _t("Perdu")), key=lambda l: -l[5])
        ajouter(2, "Faire revenir les clients perdus (offre de retour)",
                _t("Rétention de {p} % ; {n} client(s) perdus.", p=_nb(retention, 0), n=_carte(fid, "Clients perdus")),
                "a_fidelite",
                [(l[0], _t("Dernier achat {d} ; {c} commande(s), {v} dans la période de comparaison", d=l[7], c=l[4],
                           v=_argent(l[5])), "") for l in perdus])
    seu = sous.get("a_seuil", vide)
    s_jour, moy_jour = _carte(seu, "Ventes nécessaires par jour ouvert"), _carte(seu, "Ventes moyennes par jour ouvert")
    if s_jour and moy_jour is not None and moy_jour < s_jour:
        ajouter(1, "Les ventes ne couvrent pas les frais : augmenter les ventes ou la marge, ou réduire les frais",
                _t("Il faut {s} par jour ouvert ; le magasin fait {v}.", s=_argent(s_jour), v=_argent(moy_jour)),
                "a_seuil")
    sai = sous.get("a_saison", vide)
    if getattr(sai, "prochains", None):
        ajouter(2, _t("Préparer les articles de saison de {m} (commande, place en rayon)", m=sai.mois_prochain),
                _t("{n} article(s) importants vendent le plus en {m}.", n=len(sai.prochains), m=sai.mois_prochain),
                "a_saison", [(l[0], _t("{c} ; indice de saison {i} ; {v} par jour au meilleur mois", c=l[1],
                                       i=_nb(l[7], 0), v=_argent(l[3])), "") for l in sai.prochains])
    jdm = sous.get("a_jour_mois", vide)
    fort_jdm = _carte(jdm, "Indice du meilleur moment")
    if fort_jdm is not None and fort_jdm >= 110 and (_carte(jdm, "Jours analysés") or 0) >= 40:
        ajouter(3, _t("Prévoir plus de stock et de personnel les jours {t} du mois",
                      t=_carte(jdm, "Meilleur moment du mois")),
                _t("Ces jours vendent {p} % de plus qu'un jour normal.", p=_nb(fort_jdm - 100, 0)), "a_jour_mois")
    poi = sous.get("a_poids", vide)
    if getattr(poi, "hausses_prix", None):
        ajouter(3, "Vérifier les prix au poids qui augmentent (prix affiché, balance)",
                _t("{n} article(s) au poids coûtent 10 % ou plus qu'avant.", n=len(poi.hausses_prix)), "a_poids",
                [(l[0], _t("{a} → {b} ({p} %)", a=_argent(l[6]), b=_argent(l[5]), p=_nb(l[7])), "")
                 for l in poi.hausses_prix])
    rup = sous.get("a_ruptures", vide)
    rup_cours = [l for l in rup.lignes if l[7] == _t("Oui")]
    if rup_cours:
        ajouter(1, "Vérifier le stock et commander les articles réguliers qui ne se vendent plus",
                _t("{n} article(s) vendus presque chaque jour ne se vendent plus depuis plusieurs jours : rupture "
                   "probable.", n=len(rup_cours)), "a_ruptures",
                [(l[0], _t("{c} ; sans vente depuis le {d} ; {v} par jour d'habitude", c=l[1], d=l[5],
                           v=_argent(l[3])), "") for l in rup_cours])
    app = sous.get("a_appel", vide)
    if getattr(app, "appel", None) and rup_cours:
        noms_appel = {l[0] for l in app.appel}
        manquants = [l for l in rup_cours if l[0] in noms_appel]
        if manquants:
            ajouter(1, "Remettre en stock d'abord les articles d'appel qui manquent",
                    _t("{n} article(s) qui font venir les clients ne se vendent plus : chaque jour coûte aussi les "
                       "autres achats de ces clients.", n=len(manquants)), "a_appel",
                    [(l[0], _t("sans vente depuis le {d}", d=l[5]), "") for l in manquants])
    com = sous.get("a_complements", vide)
    if com.lignes and _carte(com, "Gain possible (1 client sur 4)", 0) >= 100:
        ajouter(3, "Proposer à la caisse le complément habituel des articles achetés",
                _t("Environ {g} de ventes de plus si un client sur quatre prenait le complément qu'il oublie.",
                   g=_argent(_carte(com, "Gain possible (1 client sur 4)"))), "a_complements",
                [(f"{l[0]} + {l[1]}", _t("{p} % le prennent déjà ; {s} commandes sans ; gain possible {g}",
                                         p=_nb(l[4], 0), s=l[6], g=_argent(l[8])), "") for l in com.lignes])
    pfo = sous.get("a_prix_format", vide)
    if getattr(pfo, "mal", None):
        ajouter(2, "Revoir les prix des grands formats plus chers au kg que les petits",
                _t("{n} format(s) coûtent plus cher au kg (ou au litre) qu'un format plus petit du même produit.",
                   n=len(pfo.mal)), "a_prix_format",
                [(l[1], _t("{f} : {v} {u}, {p} % de plus que le plus petit format", f=l[3], v=_argent(l[6]), u=l[7],
                           p=_nb(l[8])), "") for l in pfo.mal])
    tra = sous.get("a_tranches", vide)
    if getattr(tra, "baisse", None):
        l = tra.baisse
        ajouter(3, _t("Revoir l'offre des articles de la tranche « {t} »", t=l[0]),
                _t("Leurs ventes baissent de {p} % par rapport à la période d'avant.", p=_nb(abs(l[6]))), "a_tranches")
    con = sous.get("a_contribution", vide)
    if getattr(con, "freins", None):
        ajouter(2, "Comprendre la baisse des catégories qui freinent les ventes",
                _t("{n} catégorie(s) expliquent à elles seules une grande part de la baisse des ventes.",
                   n=len(con.freins)), "a_contribution",
                [(l[1], _t("{v} par rapport à la période d'avant", v=_argent(l[5])), "") for l in con.freins])
    efr = sous.get("a_effet_rabais", vide)
    if getattr(efr, "inefficace", False):
        ajouter(3, "Revoir les rabais qui ne font pas acheter plus",
                _t("Les commandes avec un rabais ne sont pas plus grosses que les autres, après le rabais."),
                "a_effet_rabais", [(l[0], _t("{n} commande(s) ; {r} de rabais en moyenne", n=l[1], r=_argent(l[4])), "")
                                   for l in efr.lignes[2:]])
    aso = sous.get("a_assortiment", vide)
    if getattr(aso, "alleger", None):
        ajouter(3, "Alléger les catégories encombrées de références peu vendues",
                _t("{n} catégorie(s) ont 70 % ou plus d'articles qui se vendent à peine.", n=len(aso.alleger)),
                "a_assortiment", [(l[0], _t("{f} article(s) peu vendus sur {n} ; {v} de ventes", f=l[8], n=l[1],
                                            v=_argent(l[10])), "") for l in aso.alleger])
    pvo = sous.get("a_prix_volume", vide)
    if getattr(pvo, "volume_en_baisse", False):
        ajouter(2, "Regagner du volume : les ventes ne tiennent que grâce aux hausses de prix",
                _t("Prix {p} % ; volume {q} %.", p=_nb(_carte(pvo, "Hausse des prix")),
                   q=_nb(_carte(pvo, "Croissance en volume (hors prix)"))), "a_prix_volume",
                [(l[0], _t("{a} → {b} ({p} %)", a=_argent(l[2]), b=_argent(l[3]), p=_nb(l[4])), "")
                 for l in pvo.lignes if l[4] >= 5][:50])
    bai = sous.get("a_baisse", vide)
    fortes = [l for l in bai.lignes if l[7] == _t("Forte baisse")]
    if fortes:
        ajouter(2, "Comprendre la baisse des articles importants (prix, rupture, concurrence, qualité)",
                _t("{n} article(s) parmi les plus vendus perdent 15 % ou plus de leurs ventes chaque semaine.",
                   n=len(fortes)), "a_baisse",
                [(l[0], _t("{c} ; {a} par semaine au début, {b} à la fin ; {p} % par semaine", c=l[1],
                           a=_argent(l[3]), b=_argent(l[4]), p=_nb(l[5])), "") for l in bai.lignes])
    nou = sous.get("a_nouveaux", vide)
    lents = [l for l in nou.lignes if l[9] == _t("Démarrage lent") and l[3] >= 14]
    if len(lents) >= 3:
        ajouter(3, "Mettre en avant ou ne plus recommander les nouveaux articles qui démarrent lentement",
                _t("{n} nouvel(aux) article(s) vendent peu depuis plus de 2 semaines.", n=len(lents)), "a_nouveaux",
                [(l[0], _t("{c} ; première vente {d} ; {v} par jour", c=l[1], d=l[2], v=_argent(l[6])), "")
                 for l in sorted(lents, key=lambda l: l[6])])
    fer = sous.get("a_feries", vide)
    veille = _carte(fer, "Effet moyen de la veille")
    a_venir = [l for l in fer.lignes if l[3] is None]
    if veille is not None and veille >= 20 and a_venir:
        ajouter(2, _t("Prévoir personnel et stock la veille du prochain jour férié ({n}, {d})", n=a_venir[0][1],
                      d=a_venir[0][0]),
                _t("La veille d'un jour férié vend {p} % de plus qu'un jour normal.", p=_nb(veille)), "a_feries")
    rem = sous.get("a_remboursements", vide)
    t1, t0 = _carte(rem, "Part des ventes remboursée"), _carte(rem, "Part remboursée la période d'avant")
    if t1 is not None and t1 > 2 and (not t0 or t1 > t0 * Decimal("1.5")):
        ajouter(2, "Vérifier les remboursements avec les employés",
                _t("{p} % des ventes remboursées (période d'avant : {q} %).", p=_nb(t1, 2), q=_nb(t0 or 0, 2)),
                "a_remboursements",
                [(l[1], _t("{n} : {v} remboursés ; {p} de ses ventes", n=l[0], v=_argent(l[2]), p=_pourcent(l[5])),
                  "") for l in rem.lignes if l[0] in (_t("Employé"), _t("Article"))])
    mar = sous.get("a_marge", vide)
    m1, m0 = _carte(mar, "Marge brute"), _carte(mar, "Marge de la comparaison")
    if mar.lignes and m1 is not None and m0 and m0 - m1 > 1:
        pertes = [l for l in mar.lignes if l[9] < 0]
        ajouter(1, "Protéger la marge brute", _t("Marge de {a} % contre {b} % ; effet prix {p}, effet mix {x}.",
                                                 a=_nb(m1), b=_nb(m0), p=_argent(_carte(mar, "Effet des prix")),
                                                 x=_argent(_carte(mar, "Effet du choix des articles"))), "a_marge",
                [(l[0], _t("{c} ; bénéfice {a} contre {b} ; prix net {p} → {q} ; marge {m}", c=l[1], a=_argent(l[7]),
                           b=_argent(l[8]), p=_argent(l[5]) if l[5] is not None else "—",
                           q=_argent(l[4]) if l[4] is not None else "—", m=_pourcent(l[12])), "") for l in pertes])
    por = sous.get("a_portefeuille", vide)
    prometteuses = sorted((l for l in por.lignes if l[9] == _t("Prometteuse") and l[4] is not None),
                          key=lambda l: -l[4])
    if prometteuses:
        ajouter(3, "Développer les catégories prometteuses (espace, promotion)",
                _t("{n} catégorie(s) petites mais en croissance.", n=len(prometteuses)), "a_portefeuille",
                [(l[0], _t("Croissance {c} ; {p} des ventes ; {v}", c=_pourcent(l[4]), p=_pourcent(l[2]),
                           v=_argent(l[1])), "") for l in prometteuses])
    ach = sous.get("a_achalandage", vide)
    tension = [l for l in ach.lignes if l[8] == _t("Chargée")]
    if tension:
        ajouter(2, "Renforcer l'équipe aux heures de pointe",
                _t("{n} créneau(x) avec beaucoup de commandes par employé.", n=len(tension)), "a_achalandage",
                [(f"{l[0]} {l[1]}", _t("{c} commandes par jour ; {e} employé(s) actif(s) ; {p} commandes par "
                                       "employé", c=_nb(l[3]), e=_nb(l[5]), p=_nb(l[6])), "")
                 for l in sorted(tension, key=lambda l: -l[6])])
    faibles = getattr(ach, "heures_faibles", [])
    if faibles:
        ajouter(3, "Revoir les heures d'ouverture peu achalandées",
                _t("{n} heure(s) d'ouverture ou de fermeture à moins du quart d'une heure moyenne.", n=len(faibles)),
                "a_achalandage",
                [(f"{_t(JOURS[j])} {h} h", _t("{v} de ventes par jour contre {m} pour une heure moyenne", v=_argent(_d(v)),
                                             m=_argent(_d(m))), "") for j, h, v, m in sorted(faibles, key=lambda x: x[2])])
    calmes = [l for l in ach.lignes if l[8] == _t("Calme")]
    if calmes:
        ajouter(3, "Alléger l'équipe ou planifier d'autres tâches aux heures calmes",
                _t("{n} créneau(x) avec plusieurs employés pour peu de commandes.", n=len(calmes)), "a_achalandage",
                [(f"{l[0]} {l[1]}", _t("{c} commandes par jour ; {e} employé(s) actif(s)", c=_nb(l[3]),
                                       e=_nb(l[5])), "") for l in sorted(calmes, key=lambda l: l[6])])
    pan = sous.get("a_paniers", vide)
    if (_carte(pan, "Paniers d'un seul article") or 0) >= 30:
        ajouter(3, "Proposer un 2e article à la caisse", _t("{p} % des paniers n'ont qu'un article.",
                                                            p=_nb(_carte(pan, "Paniers d'un seul article"), 0)),
                "a_paniers")
    return sortie


# état (couleur) d'une carte selon son titre et sa valeur : None = neutre
ETATS_CARTES = {
    "Variation": lambda v: "bon" if v >= 0 else "alerte", "Écart": lambda v: "bon" if v >= 0 else "alerte",
    "Effet du nombre de ventes": lambda v: "bon" if v >= 0 else "attention",
    "Effet du montant moyen par vente": lambda v: "bon" if v >= 0 else "attention",
    "Hausse ou baisse par semaine": lambda v: "bon" if v >= 0 else "attention",
    "Effet sur les ventes par jour": lambda v: "bon" if v >= 0 else "attention",
    "Anomalies relevées": lambda v: "attention" if v else "bon",
    "Rabais de 50 % ou plus": lambda v: "alerte" if v else "bon",
    "Prix inhabituels": lambda v: "attention" if v else "bon",
    "Commandes inhabituelles": lambda v: "attention" if v else None,
    "Jours inhabituels": lambda v: "attention" if v else None,
    "Très vendus, peu rentables": lambda v: "attention" if v else None, "Peu vendus, peu rentables": lambda v: "attention" if v else None,
    "Très vendus et rentables": lambda v: "bon" if v else None, "À risque": lambda v: "alerte" if v else "bon",
    "Champions": lambda v: "bon" if v else None, "Clients perdus": lambda v: "attention" if v else "bon",
    "Taux de rétention": lambda v: "bon" if v >= 30 else "attention",
    "Paniers d'un seul article": lambda v: "attention" if v >= 30 else "bon",
    "Part des ventes avec un client": lambda v: "attention" if v < 30 else "bon",
    "Reviennent le mois suivant": lambda v: "bon" if v >= 20 else "attention",
    "Écart du bénéfice": lambda v: "bon" if v >= 0 else "alerte",
    "Effet des prix": lambda v: "bon" if v >= 0 else "attention", "Effet des quantités": lambda v: "bon" if v >= 0 else "attention",
    "Effet du choix des articles": lambda v: "bon" if v >= 0 else "attention",
    "Ventes au coût connu": lambda v: "bon" if v >= 80 else "attention",
    "Étoiles": lambda v: "bon" if v else None, "En recul": lambda v: "attention" if v else "bon",
    "Croissance du magasin": lambda v: "bon" if v >= 0 else "alerte",
    "Part des ventes remboursée": lambda v: "bon" if v <= 1 else "attention" if v <= 3 else "alerte",
    "Bons départs": lambda v: "bon" if v else None, "Démarrages lents": lambda v: "attention" if v else "bon",
    "Articles qui baissent": lambda v: "attention" if v else "bon", "Fortes baisses": lambda v: "alerte" if v else "bon",
    "Part des 10 meilleurs": lambda v: "attention" if v >= 50 else None,
    "Heures chargées": lambda v: "attention" if v else "bon",
    "Heures calmes": lambda v: "attention" if v else "bon",
    "Atteinte projetée": lambda v: "bon" if v >= 100 else "alerte" if v < 95 else "attention",
}


def etat_carte(titre: str, valeur) -> str | None:
    """« bon », « attention », « alerte » ou None (affichage : couleur de la carte)."""
    regle = ETATS_CARTES.get(titre)
    if regle is None or not isinstance(valeur, (int, float, Decimal)):
        return None
    try:
        return regle(valeur)
    except Exception:  # noqa: BLE001
        return None


# début des constats qui sont des définitions (pas repris dans la synthèse)
DEFINITIONS = ("Jour inhabituel :", "Popularité :", "Seules les paires", "Heure active :", "Chaque client est noté",
               "Retenu :", "Changement de prix :", "Chaque ligne suit", "Choisissez au moins", "Explication du bénéfice :",
               "Part forte :", "Employé actif :", "Objectif :", "Nouvel article :",
               "Jour normal :", "Moyenne par jour ouvert de chaque jour", "Articles importants :", "Ventes moyennes par jour "
               "ouvert", "Prévision :", "Les taxes perçues par Clover",
               "Valeur sur un an =", "Seuil de rentabilité :", "Quantité prévue =", "Pour la semaine qui vient",
               "Indice : ventes du jour", "Indice de saison :", "Article vendu au poids :", "Rupture probable :", "Article d'appel :", "Complément habituel :", "En tout, environ", "Format : taille lue", "Tranche de prix : prix affiché", "Écart : ventes nettes de la période", "Effet des rabais : commandes", "Article peu vendu : 2 commandes", "Indice des prix : prix affichés")


# --------------------------------------------------------------------------------------------- graphiques de plus
# Demande du propriétaire du 2026-11-08 : « ne laisse pas trop de vides dans les rapports, il faut compléter par des
# graphiques » : chaque analyse a une 2e rangée de deux graphiques, tirés de son propre tableau.
def _graphe(genre: str, titre: str, unite: str = "$", etiquettes=None, series=None, elements=None) -> dict:
    return {"genre": genre, "titre": titre, "unite": unite, "etiquettes": list(etiquettes or []),
            "series": list(series or []), "elements": list(elements or [])}


def _signe(nom: str, ecart) -> tuple[str, Decimal]:
    return (("▲ " if ecart >= 0 else "▼ ") + str(nom), abs(_d(ecart)))


def _sup_variation(r):
    emp = [l for l in r.lignes if l[0] == _t("Employé")]
    art = [l for l in r.lignes if l[0] == _t("Article")]
    return [_graphe("classement", "Employés : écart avec la comparaison", elements=[_signe(l[1], l[4]) for l in emp[:8]]),
            _graphe("classement", "Articles qui expliquent l'écart", elements=[_signe(l[1], l[4]) for l in art[:8]])]


def _sup_tendance(r):
    lignes = r.lignes
    etiquettes = [l[1][8:10] + "/" + l[1][5:7] for l in lignes]
    return [_graphe("barres", "Ventes nettes par semaine", etiquettes=etiquettes,
                    series=[("Ventes nettes", [l[5] for l in lignes])]),
            _graphe("courbes", "Panier moyen par semaine", etiquettes=etiquettes,
                    series=[("Panier moyen", [l[6] for l in lignes])])]


def _sup_paniers(r):
    nb = [l for l in r.lignes if l[0] == _t("Nombre d'articles")]
    montant = [l for l in r.lignes if l[0] == _t("Montant")]
    return [_graphe("barres", "Commandes par nombre d'articles", "", etiquettes=[l[1] for l in nb],
                    series=[("Commandes", [l[2] for l in nb])]),
            _graphe("barres", "Articles par panier selon le montant", "", etiquettes=[l[1] for l in montant],
                    series=[("Articles par panier", [l[7] for l in montant])])]


def _sup_concentration(r):
    return [_graphe("barres", "Part des 10 premiers éléments par dimension", "%", etiquettes=[l[0] for l in r.lignes],
                    series=[("Part des 10 premiers %", [l[4] for l in r.lignes])]),
            _graphe("barres", "Éléments qui font 80 % des ventes (en % du total)", "%",
                    etiquettes=[l[0] for l in r.lignes], series=[("% des éléments pour 80 %", [l[6] for l in r.lignes])])]


def _sup_anomalies(r):
    par_mois, par_jds = defaultdict(int), defaultdict(int)
    for l in r.lignes:
        try:
            j = date.fromisoformat(str(l[1])[:10])
        except ValueError:
            continue
        par_mois[f"{j.month:02d}/{j.year}"] += 1
        par_jds[j.weekday()] += 1
    mois = sorted(par_mois, key=lambda m: (m[3:], m[:2]))
    return [_graphe("barres", "Anomalies par mois", "", etiquettes=mois, series=[("Anomalies", [par_mois[m] for m in mois])]),
            _graphe("barres", "Anomalies par jour de la semaine", "", etiquettes=[_t(JOURS[k])[:3] for k in range(7)],
                    series=[("Anomalies", [par_jds.get(k, 0) for k in range(7)])])]


def _sup_matrice(r):
    par_classe = defaultdict(Decimal)
    for l in r.lignes:
        par_classe[_t("Classe {c}", c=l[5])] += l[3]
    locomotives = [l for l in r.lignes if l[11] == _t("Très vendu, peu rentable")][:8]
    if locomotives:
        second = _graphe("classement", "Très vendus mais peu rentables, à revoir en priorité",
                         elements=[(l[0], l[3]) for l in locomotives])
    else:
        irreguliers = [l for l in r.lignes if l[5] == "A" and l[8] == "Z"][:8]
        second = _graphe("classement", "Gros vendeurs à demande irrégulière (ventes nettes)",
                         elements=[(l[0], l[3]) for l in irreguliers])
    return [_graphe("anneau", "Ventes nettes par classe 20/80", elements=sorted(par_classe.items())), second]


def _sup_associations(r):
    cats = [l for l in r.lignes if l[0] == _t("Catégories")][:8]
    lift = sorted((l for l in r.lignes if l[0] == _t("Articles")), key=lambda l: -l[7])[:8]
    return [_graphe("classement", "Catégories achetées le plus souvent ensemble", "",
                    elements=[(f"{l[1]} + {l[2]}", Decimal(l[3])) for l in cats]),
            _graphe("classement", "Paires les plus liées", "", elements=[(f"{l[1]} + {l[2]}", l[7]) for l in lift])]


def _sup_prix(r):
    effets = sorted(r.lignes, key=lambda l: -abs(l[11] - l[10]))[:8]
    prix_ = sorted(r.lignes, key=lambda l: -abs(l[5]))[:8]
    return [_graphe("classement", "Effet du changement sur les ventes par jour",
                    elements=[_signe(l[0], l[11] - l[10]) for l in effets]),
            _graphe("classement", "Plus fortes variations de prix (%)", "%",
                    elements=[(("▲ " if l[5] >= 0 else "▼ ") + l[0], abs(l[5])) for l in prix_])]


def _sup_employes(r):
    lignes = r.lignes[:10]
    return [_graphe("barres", "Panier moyen par employé", etiquettes=[l[0].split()[0] for l in lignes],
                    series=[("Panier moyen", [l[4] for l in lignes])]),
            _graphe("classement", "Taux de rabais par employé (%)", "%",
                    elements=[(l[0], l[7]) for l in sorted(r.lignes, key=lambda l: -l[7])[:8]])]


def _sup_rfm(r):
    nb = defaultdict(int)
    for l in r.lignes:
        nb[l[1]] += 1
    ordre = sorted(nb, key=lambda k: -nb[k])
    return [_graphe("barres", "Clients par groupe", "", etiquettes=ordre, series=[("Clients", [nb[k] for k in ordre])]),
            _graphe("classement", "Meilleurs clients (ventes nettes)", elements=[(l[0], l[10]) for l in r.lignes[:8]])]


def _sup_fidelite(r):
    ventes = defaultdict(Decimal)
    for l in r.lignes:
        if l[1] != _t("Perdu"):
            ventes[l[1]] += l[3]
    perdus = sorted((l for l in r.lignes if l[1] == _t("Perdu")), key=lambda l: -l[5])[:8]
    return [_graphe("anneau", "Ventes nettes des clients retenus et nouveaux", elements=list(ventes.items())),
            _graphe("classement", "Clients perdus qui achetaient le plus (comparaison)",
                    elements=[(l[0], l[5]) for l in perdus])]


def _sup_cohortes(r):
    lignes = r.lignes
    return [_graphe("barres", "Ventes nettes par client selon le mois du premier achat",
                    etiquettes=[l[0] for l in lignes], series=[("Ventes nettes par client", [l[2] for l in lignes])]),
            _graphe("courbes", "Part qui revient le mois suivant, par mois du premier achat", "%",
                    etiquettes=[l[0] for l in lignes if len(l) > 3 and l[3] is not None],
                    series=[("Mois +1 %", [l[3] for l in lignes if len(l) > 3 and l[3] is not None])])]


def _principal(r, unite=None) -> dict:
    """Le graphique d'évolution d'une analyse, sous forme de graphique de plus (synthèse)."""
    genre = "barres" if r.genre_evolution == "barres" or len(r.etiquettes) <= 1 else "courbes"
    return _graphe(genre, r.titre_evolution, unite if unite is not None else r.unite_evolution, r.etiquettes, r.series)


def _repartition(r) -> dict:
    return _graphe(r.genre_repartition, r.titre_repartition, "$" if r.argent_repartition else "",
                   elements=r.repartition)


def _sup_rabais_direction(r):
    par_type, par_cmd = defaultdict(Decimal), []
    for l in r.lignes:
        par_type[l[0]] += l[5]
        par_cmd.append((f"{l[2]} ({l[3]})", l[5]))
    return [_graphe("anneau", "Rabais mis à part par type", elements=sorted(par_type.items(), key=lambda kv: -kv[1])),
            _graphe("classement", "Plus forts rabais mis à part", elements=sorted(par_cmd, key=lambda x: -x[1])[:8])]


def _sup_marge(r):
    par_cat = defaultdict(lambda: [ZERO, ZERO, ZERO])
    for l in r.lignes:
        g = par_cat[l[1]]
        g[0] += l[9]
        g[1] += l[7]
        g[2] += (l[4] or ZERO) * l[2] if l[4] is not None else ZERO
    ecarts = sorted(par_cat.items(), key=lambda kv: -abs(kv[1][0]))[:8]
    marges = sorted(((n, _pc(g[1], g[2])) for n, g in par_cat.items() if g[2] > 0), key=lambda x: -x[1])[:8]
    return [_graphe("classement", "Catégories : écart du bénéfice", elements=[_signe(n, g[0]) for n, g in ecarts]),
            _graphe("classement", "Marge brute par catégorie", "%", elements=marges)]


def _sup_portefeuille(r):
    croissance = [l for l in r.lignes if l[4] is not None]
    marges = [l for l in r.lignes if l[8] is not None]
    return [_graphe("classement", "Croissance des catégories", "%",
                    elements=[_signe(l[0], l[4]) for l in sorted(croissance, key=lambda l: -abs(l[4]))[:8]]),
            _graphe("classement", "Marge brute par catégorie", "%",
                    elements=[(l[0], l[8]) for l in sorted(marges, key=lambda l: -l[8])[:8]])]


def _sup_achalandage(r):
    par_jour = defaultdict(Decimal)
    for l in r.lignes:
        par_jour[l[0]] += l[3]
    ordre = [_t(j) for j in JOURS if _t(j) in par_jour]
    calmes = [(f"{l[0]} {l[1]}", l[5]) for l in r.lignes if l[8] == _t("Calme")]
    return [_graphe("barres", "Commandes par jour de la semaine (moyenne par jour ouvert)", "", etiquettes=ordre,
                    series=[("Commandes", [par_jour[j] for j in ordre])]),
            _graphe("classement", "Heures calmes : employés actifs", "",
                    elements=sorted(calmes, key=lambda x: -x[1])[:8])]


def _sup_rythme(r):
    lignes = r.lignes
    return [_graphe("barres", "Ventes par jour : réalisé ou prévu et objectif du jour", etiquettes=[l[0][8:10] + "/" + l[0][5:7] for l in lignes],
                    series=[("Ventes nettes", [l[3] for l in lignes]), ("Objectif du jour", [l[4] for l in lignes])]),
            _graphe("courbes", "Écart cumulé avec l'objectif", etiquettes=[l[0][8:10] + "/" + l[0][5:7] for l in lignes],
                    series=[("Écart cumulé", [l[7] for l in lignes])])]


def _sup_remboursements(r):
    employes_ = [(l[1], l[2]) for l in r.lignes if l[0] == _t("Employé")][:8]
    parts = sorted(((l[1], l[5]) for l in r.lignes if l[0] == _t("Article") and l[5] is not None and l[3] >= 2),
                   key=lambda x: -x[1])[:8]
    return [_graphe("classement", "Montant remboursé par employé", elements=employes_),
            _graphe("classement", "Articles remboursés le plus souvent (part de leurs ventes)", "%", elements=parts)]


def _sup_especes(r):
    heures = sorted(getattr(r, "heures_especes", {}))
    jds = [k for k in range(7) if k in getattr(r, "jds_especes", {})]
    return [_graphe("barres", "Espèces et cartes selon l'heure", etiquettes=[f"{h} h" for h in heures],
                    series=[("Espèces", [_d(r.heures_especes[h][0]) for h in heures]),
                            ("Carte ou autre", [_d(r.heures_especes[h][1]) for h in heures])]),
            _graphe("barres", "Espèces moyennes selon le jour de la semaine", etiquettes=[_t(JOURS[k]) for k in jds],
                    series=[("Espèces", [_d(r.jds_especes[k]) for k in jds])])]


def _sup_nouveaux(r):
    par_cat = defaultdict(int)
    for l in r.lignes:
        par_cat[l[1]] += 1
    return [_graphe("classement", "Nouveaux articles : ventes par jour depuis leur première vente",
                    elements=[(l[0], l[6]) for l in sorted(r.lignes, key=lambda l: -l[6])[:8]]),
            _graphe("anneau", "Nouveaux articles par catégorie", "",
                    elements=[(k, Decimal(v)) for k, v in sorted(par_cat.items(), key=lambda kv: -kv[1])])]


def _sup_feries(r):
    effets = [(l[1], abs(l[5])) for l in r.lignes if l[5] is not None]
    return [_graphe("classement", "Écart des jours fériés avec un jour normal (%)", "%",
                    elements=[(("▲ " if l[5] >= 0 else "▼ ") + l[1], abs(l[5])) for l in r.lignes
                              if l[5] is not None]),
            _graphe("classement", "Écart des veilles avec un jour normal (%)", "%",
                    elements=[(("▲ " if l[8] >= 0 else "▼ ") + l[1], abs(l[8])) for l in r.lignes
                              if l[8] is not None])] if effets or any(l[8] is not None for l in r.lignes) else []


def _sup_taxes(r):
    emp = getattr(r, "pourboires_employes", {})
    return [_graphe("barres", "Taxes en % des ventes par jour", "%",
                    etiquettes=[l[0][8:10] + "/" + l[0][5:7] for l in reversed(r.lignes)],
                    series=[("Taxes en % des ventes", [l[4] or ZERO for l in reversed(r.lignes)])]),
            _graphe("classement", "Commandes avec pourboire par employé", "",
                    elements=sorted(((n, Decimal(v[1])) for n, v in emp.items() if v[1]), key=lambda x: -x[1])[:8])]


def _sup_gains(r):
    lignes = sorted(r.lignes, key=lambda l: -l[6])
    return [_graphe("classement", "Les 8 moments qui rapportent le plus", elements=[(f"{l[0]} {l[1]}", l[6])
                                                                                   for l in lignes[:8]]),
            _graphe("classement", "Les 8 moments qui rapportent le moins", elements=[(f"{l[0]} {l[1]}", l[6])
                                                                                    for l in lignes[-8:][::-1]])]


def _sup_baisse(r):
    par_cat = defaultdict(int)
    for l in r.lignes:
        par_cat[l[1]] += 1
    return [_graphe("classement", "Ventes par semaine : début et fin", elements=[(l[0], l[4]) for l in r.lignes[:8]]),
            _graphe("anneau", "Articles qui baissent par catégorie", "",
                    elements=[(k, Decimal(v)) for k, v in sorted(par_cat.items(), key=lambda kv: -kv[1])])]


def _sup_categories_jour(r):
    n = len(r.entetes) - 3
    totaux = [(r.entetes[1 + k], sum((l[1 + k] for l in r.lignes), ZERO)) for k in range(n)]
    return [_graphe("barres", "Ventes moyennes de tout le magasin selon le jour", etiquettes=[t_ for t_, _v in totaux],
                    series=[("Ventes nettes", [v for _t_, v in totaux])]),
            _graphe("classement", "Catégories qui vendent le plus (moyenne par jour)",
                    elements=[(l[0], sum(l[1:1 + n], ZERO) / max(1, n)) for l in r.lignes[:8]])]


def _sup_prevu(r):
    par_heure = defaultdict(Decimal)
    for l in r.lignes:
        par_heure[l[1]] += l[2]
    heures = sorted(par_heure, key=lambda h: int(h.split()[0]))
    employes_ = defaultdict(int)
    for l in r.lignes:
        employes_[l[0][:10]] = max(employes_[l[0][:10]], l[3])
    return [_graphe("barres", "Commandes prévues selon l'heure (toute la semaine)", "", etiquettes=heures,
                    series=[("Commandes prévues", [par_heure[h] for h in heures])]),
            _graphe("barres", "Employés conseillés au plus fort de chaque jour", "",
                    etiquettes=[j[8:10] + "/" + j[5:7] for j in employes_],
                    series=[("Employés", [Decimal(v) for v in employes_.values()])])]


def _sup_valeur(r):
    return [_graphe("classement", "Clients qui viennent le plus souvent (visites par mois)", "",
                    elements=[(l[0], l[4]) for l in sorted(r.lignes, key=lambda l: -l[4])[:8]]),
            _graphe("classement", "Plus gros paniers des clients identifiés",
                    elements=[(l[0], l[3]) for l in sorted(r.lignes, key=lambda l: -l[3])[:8]])]


def _sup_seuil(r):
    ecarts = [l for l in r.lignes if l[4] is not None]
    return [_graphe("classement", "Jours les plus au-dessus du seuil",
                    elements=[(f"{l[0]} ({l[1]})", l[4]) for l in sorted(ecarts, key=lambda l: -l[4])[:8] if l[4] > 0]),
            _graphe("classement", "Jours les plus au-dessous du seuil",
                    elements=[(f"{l[0]} ({l[1]})", -l[4]) for l in sorted(ecarts, key=lambda l: l[4])[:8] if l[4] < 0])]


def _sup_quantites(r):
    par_cat = defaultdict(Decimal)
    for l in r.lignes:
        par_cat[l[1]] += l[-1]
    return [_graphe("anneau", "Quantités prévues par catégorie", "",
                    elements=sorted(par_cat.items(), key=lambda kv: -kv[1])),
            _graphe("classement", "Articles à prévoir surtout le samedi", "",
                    elements=[(l[0], l[7]) for l in sorted(r.lignes, key=lambda l: -l[7])[:8]])]


def _sup_jour_mois(r):
    lignes = [l for l in r.lignes if l[1]]
    return [_graphe("barres", "Commandes moyennes par jour selon le moment du mois", "",
                    etiquettes=[l[0] for l in lignes], series=[("Commandes moyennes par jour", [l[4] for l in lignes])]),
            _graphe("barres", "Panier moyen selon le moment du mois", etiquettes=[l[0] for l in lignes],
                    series=[("Panier moyen", [l[5] for l in lignes])])]


def _sup_saison(r):
    saison = [l for l in r.lignes if l[8] == _t("Article de saison")] or r.lignes
    par_cat, par_mois = defaultdict(int), defaultdict(int)
    for l in saison:
        par_cat[l[1]] += 1
        par_mois[l[2]] += 1
    return [_graphe("anneau", "Articles de saison par catégorie", "",
                    elements=[(k, Decimal(v)) for k, v in sorted(par_cat.items(), key=lambda kv: -kv[1])]),
            _graphe("classement", "Meilleur mois des articles de saison (nombre d'articles)", "",
                    elements=[(k, Decimal(v)) for k, v in sorted(par_mois.items(), key=lambda kv: -kv[1])[:8]])]


def _sup_poids(r):
    return [_graphe("classement", "Quantité moyenne par commande (poids)", "",
                    elements=[(l[0], l[4]) for l in sorted(r.lignes[:30], key=lambda l: -l[4])[:8]]),
            _graphe("classement", "Écart du prix moyen au poids avec la période d'avant (%)", "%",
                    elements=[_signe(l[0], l[7]) for l in sorted((l for l in r.lignes[:30] if l[7] is not None),
                                                                 key=lambda l: -abs(l[7]))[:8] if l[7]])]


def _sup_ruptures(r):
    par_cat = defaultdict(Decimal)
    for l in r.lignes:
        par_cat[l[1]] += l[9]
    return [_graphe("classement", "Plus longue absence (jours ouverts)", "",
                    elements=[(l[0], Decimal(l[4])) for l in sorted(r.lignes, key=lambda l: -l[4])[:8]]),
            _graphe("anneau", "Ventes perdues estimées par catégorie",
                    elements=sorted(par_cat.items(), key=lambda kv: -kv[1]))]


def _sup_appel(r):
    par_cat = defaultdict(int)
    for l in r.lignes:
        par_cat[l[10]] += 1
    return [_graphe("classement", "Articles achetés seuls le plus souvent (%)", "%",
                    elements=[(l[0], l[7]) for l in sorted(r.lignes, key=lambda l: -l[7])[:8]]),
            _graphe("anneau", "Articles suivis par profil", "",
                    elements=[(k, Decimal(v)) for k, v in sorted(par_cat.items(), key=lambda kv: -kv[1])])]


def _sup_complements(r):
    par_cat = defaultdict(Decimal)
    for l in r.lignes:
        par_cat[l[2]] += l[8]
    return [_graphe("classement", "Clients qui prennent le complément (%)", "%",
                    elements=[(f"{l[0]} + {l[1]}", l[4]) for l in sorted(r.lignes[:30], key=lambda l: -l[4])[:8]]),
            _graphe("anneau", "Gain possible par catégorie",
                    elements=sorted(par_cat.items(), key=lambda kv: -kv[1]))]


def _sup_prix_format(r):
    par_cat = defaultdict(int)
    for l in r.mal:
        par_cat[l[2]] += 1
    produits = defaultdict(list)
    for l in r.lignes:
        produits[l[0]].append(l[6])
    econ = sorted(((p_, (max(v) - min(v)) / max(v) * 100) for p_, v in produits.items() if max(v) > 0),
                  key=lambda kv: -kv[1])[:8]
    return [_graphe("classement", "Écart entre le format le plus cher et le moins cher au kg (%)", "%",
                    elements=[(p_, _d(e, "0.1")) for p_, e in econ]),
            _graphe("anneau", "Formats à vérifier par catégorie", "",
                    elements=[(k, Decimal(v)) for k, v in sorted(par_cat.items(), key=lambda kv: -kv[1])])]


def _sup_tranches(r):
    return [_graphe("barres", "Quantité vendue par tranche de prix", "", [l[0] for l in r.lignes],
                    [("Quantité vendue", [l[2] for l in r.lignes])]),
            _graphe("classement", "Variation des ventes par tranche de prix (%)", "%",
                    elements=[_signe(l[0], l[6]) for l in r.lignes if l[6] is not None])]


def _sup_contribution(r):
    cats = [l for l in r.lignes if l[0] == _t("Catégories")]
    return [_graphe("classement", "Variation des ventes par catégorie (%)", "%",
                    elements=[_signe(l[1], l[7]) for l in sorted((l for l in cats if l[7] is not None and l[3] > 0),
                                                                 key=lambda l: -abs(l[7]))[:8]]),
            _graphe("anneau", "Ventes nettes par catégorie", "$",
                    elements=sorted(((l[1], l[4]) for l in cats if l[4] > 0), key=lambda kv: -kv[1]))]


def _sup_effet_rabais(r):
    noms = r.lignes[2:]
    return [_graphe("classement", "Panier moyen après rabais selon le rabais", "$",
                    elements=[(l[0], l[3]) for l in r.lignes[:2]] + [(l[0], l[3]) for l in noms[:6]]),
            _graphe("classement", "Rabais moyen par commande selon le rabais", "$",
                    elements=sorted(((l[0], l[4]) for l in noms), key=lambda kv: -kv[1])[:8])]


def _sup_assortiment(r):
    return [_graphe("classement", "Part des articles peu vendus par catégorie (%)", "%",
                    elements=[(l[0], l[9]) for l in sorted((l for l in r.lignes if l[1] >= 5),
                                                           key=lambda l: -l[9])[:8]]),
            _graphe("classement", "Articles vendus par catégorie", "",
                    elements=[(l[0], Decimal(l[1])) for l in sorted(r.lignes, key=lambda l: -l[1])[:8]])]


def _sup_prix_volume(r):
    return [_graphe("classement", "Articles dont le prix a le plus changé (%)", "%",
                    elements=[_signe(l[0], l[4]) for l in r.lignes[:8] if l[4]]),
            _graphe("anneau", "Articles plus chers, moins chers ou au même prix", "",
                    elements=[(n, Decimal(v)) for n, v in ((_t("Plus chers"), sum(1 for l in r.lignes if l[4] >= 2)),
                                                           (_t("Moins chers"), sum(1 for l in r.lignes if l[4] <= -2)),
                                                           (_t("Même prix"), sum(1 for l in r.lignes if -2 < l[4] < 2)))
                              if v])]


SUPPLEMENTS = {"a_prix_volume": _sup_prix_volume, "a_assortiment": _sup_assortiment, "a_effet_rabais": _sup_effet_rabais, "a_contribution": _sup_contribution, "a_tranches": _sup_tranches, "a_prix_format": _sup_prix_format, "a_complements": _sup_complements, "a_appel": _sup_appel, "a_ruptures": _sup_ruptures, "a_jour_mois": _sup_jour_mois, "a_saison": _sup_saison, "a_poids": _sup_poids, "a_valeur": _sup_valeur, "a_seuil": _sup_seuil, "a_quantites": _sup_quantites, "a_taxes": _sup_taxes, "a_gains": _sup_gains, "a_baisse": _sup_baisse,
               "a_categories_jour": _sup_categories_jour, "a_prevu": _sup_prevu, "a_nouveaux": _sup_nouveaux, "a_feries": _sup_feries, "a_remboursements": _sup_remboursements, "a_especes": _sup_especes, "a_rythme": _sup_rythme, "a_marge": _sup_marge, "a_portefeuille": _sup_portefeuille, "a_achalandage": _sup_achalandage,
               "a_rabais_direction": _sup_rabais_direction, "a_variation": _sup_variation, "a_tendance": _sup_tendance, "a_paniers": _sup_paniers,
               "a_concentration": _sup_concentration, "a_anomalies": _sup_anomalies, "a_matrice": _sup_matrice,
               "a_associations": _sup_associations, "a_prix": _sup_prix, "a_employes": _sup_employes,
               "a_rfm": _sup_rfm, "a_fidelite": _sup_fidelite, "a_cohortes": _sup_cohortes}


def _completer(cle: str, r):
    """Ajoute les graphiques de plus de l'analyse (un graphique sans données est laissé de côté)."""
    try:
        graphes = SUPPLEMENTS[cle](r) if cle in SUPPLEMENTS else []
    except Exception:  # noqa: BLE001 — un graphique de plus ne doit jamais empêcher le rapport
        graphes = []
    r.graphiques += [g for g in graphes if g["elements"] or any(v for _n, vs in g["series"] for v in vs)]
    return r


# --------------------------------------------------------------------------------------------- liste
# (libellé, clé, fonction, section des statistiques où l'analyse est rangée, après quel état)
ANALYSES = [
    ("Synthèse et décisions", "a_synthese", synthese, "Accueil", "accueil"),
    ("Ventes inhabituelles à vérifier", "a_anomalies", anomalies, "Activités de vente", "Remboursements"),
    ("Remboursements à surveiller", "a_remboursements", remboursements, "Activités de vente", "a_anomalies"),
    ("Tendance des ventes", "a_tendance", tendance, "Rapports", "evolution_annees"),
    ("Pourquoi les ventes changent", "a_variation", variation, "Rapports", "a_tendance"),
    ("Ce qui fait monter ou baisser les ventes", "a_contribution", contribution, "Rapports", "a_variation"),
    ("Prix et volume", "a_prix_volume", prix_volume, "Rapports", "a_contribution"),
    ("Rythme et objectif", "a_rythme", rythme, "Rapports", "a_variation"),
    ("Jours fériés", "a_feries", feries, "Rapports", "a_rythme"),
    ("Ventes selon le jour du mois", "a_jour_mois", jour_du_mois, "Rapports", "a_feries"),
    ("Taille des paniers", "a_paniers", paniers, "Rapports", "Jour × heure"),
    ("Dépendance aux meilleurs", "a_concentration", concentration, "Rapports", "a_paniers"),
    ("Pourquoi le bénéfice change", "a_marge", marge, "Finances", "Résumé"),
    ("Espèces et cartes", "a_especes", especes, "Finances", "Par mode de paiement"),
    ("Taxes et pourboires", "a_taxes", taxes_pourboires, "Finances", "a_especes"),
    ("Quand le magasin gagne le plus", "a_gains", gains_horaires, "Finances", "a_marge"),
    ("Seuil de rentabilité", "a_seuil", seuil_rentabilite, "Finances", "a_gains"),
    ("Articles rentables ou non", "a_matrice", matrice, "Articles", "Par catégorie"),
    ("Catégories qui montent ou baissent", "a_portefeuille", portefeuille, "Articles", "Par catégorie"),
    ("Articles achetés ensemble", "a_associations", associations, "Articles", "a_matrice"),
    ("Effet des changements de prix", "a_prix", prix, "Articles", "a_associations"),
    ("Nouveaux articles", "a_nouveaux", nouveaux_articles, "Articles", "a_prix"),
    ("Articles qui baissent", "a_baisse", articles_baisse, "Articles", "a_nouveaux"),
    ("Catégories selon le jour", "a_categories_jour", categories_jour, "Articles", "a_baisse"),
    ("Articles de saison", "a_saison", articles_saison, "Articles", "a_categories_jour"),
    ("Ventes au poids", "a_poids", ventes_poids, "Articles", "a_saison"),
    ("Prix selon le format", "a_prix_format", prix_format, "Articles", "a_poids"),
    ("Ventes par tranche de prix", "a_tranches", tranches_prix, "Articles", "a_prix_format"),
    ("Productivité de l'assortiment", "a_assortiment", assortiment, "Articles", "a_tranches"),
    ("Ruptures probables", "a_ruptures", ruptures, "Articles", "a_baisse"),
    ("Articles d'appel", "a_appel", articles_appel, "Articles", "a_associations"),
    ("Ventes complémentaires manquées", "a_complements", complements, "Articles", "a_appel"),
    ("Achalandage prévu", "a_prevu", achalandage_prevu, "Prévisions", "prev_ventes"),
    ("Quantités prévues par article", "a_quantites", quantites_prevues, "Prévisions", "a_prevu"),
    ("Performance des employés", "a_employes", employes, "Employés", "Par employé"),
    ("Achalandage et personnel", "a_achalandage", achalandage, "Employés", "a_employes"),
    ("Rabais Direction et administrateurs", "a_rabais_direction", rabais_direction, "Rapports", "Rabais"),
    ("Effet des rabais", "a_effet_rabais", effet_rabais, "Rapports", "a_rabais_direction"),
    ("Groupes de clients", "a_rfm", rfm, "Clients", "Par client"),
    ("Clients qui reviennent", "a_fidelite", fidelite, "Clients", "a_rfm"),
    ("Valeur des clients", "a_valeur", valeur_clients, "Clients", "a_fidelite"),
    ("Retour des nouveaux clients", "a_cohortes", cohortes, "Clients", "a_fidelite"),
]
CLES = {cle for _l, cle, *_ in ANALYSES}


def inserer(navigation: list) -> list:
    """Range chaque analyse dans sa section existante, juste après l'état indiqué (aucune section nouvelle)."""
    sections = [(icone, nom, list(etats)) for icone, nom, etats in navigation]
    for libelle, cle, _f, section, apres in ANALYSES:
        for _i, nom, etats in sections:
            if nom == section:
                rang = next((k + 1 for k, (_l, c) in enumerate(etats) if c == apres), len(etats))
                etats.insert(rang, (libelle, cle))
    return sections


def calculer(cle: str, donnees, autres, couts: dict, du: date, au: date, du2: date, au2: date, racine=None,
             aujourd_hui: date | None = None):
    """Analyse `cle` sur les données (déjà filtrées) de la période et de sa comparaison ; `racine` : dossier de
    l'application (budget des ventes de « Rythme et objectif »)."""
    fonction = next(f for _l, c, f, *_ in ANALYSES if c == cle)
    ctx = {"du": du, "au": au, "du2": du2, "au2": au2, "couts": couts or {}, "donnees": donnees, "racine": racine,
           "aujourd_hui": aujourd_hui}
    return _completer(cle, fonction(_commandes(donnees), _commandes(autres), ctx))
