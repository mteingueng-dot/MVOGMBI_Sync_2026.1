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
- Articles > Matrice des articles : popularité × rentabilité (vedettes, locomotives, énigmes, poids morts), classes
  20/80 (mêmes règles que l'onglet Articles 20/80) croisées avec la régularité de la demande (X / Y / Z), conseil.
- Articles > Articles achetés ensemble : paires d'articles et de catégories (support, confiance, lift).
- Employés > Performance des employés : articles par commande, prix moyen, taux de rabais et de remboursement,
  heures actives, ventes par heure active, indice de panier, clients identifiés, variation.
- Clients > Segmentation RFM : récence, fréquence, montant notés de 1 à 5, segments et action suggérée.
- Clients > Fidélité et rétention : clients retenus, nouveaux et perdus par rapport à la période de comparaison,
  taux de rétention, intervalle entre deux achats.
"""

from __future__ import annotations

import math
import statistics as st
from collections import defaultdict
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


def _jours(du: date, au: date) -> list[date]:
    fin = min(au, date.today())
    return [du + timedelta(days=i) for i in range((fin - du).days + 1)] if fin >= du else []


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
    "Coûts Sage absents : quadrants « Coût inconnu » (Sage ne répond pas ou articles non reliés).": "attention",
    "{n} locomotive(s) : articles très vendus à faible marge, premier levier de bénéfice.": "attention",
    "{n} poids mort(s) : {v} de ventes seulement.": "attention",
    "{p} % des clients qui prennent « {a} » prennent aussi « {b} » (lift {l}) : placer ces articles côte à côte ou en "
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
                ("Variation", "%", _pc(ecart, v0) if v0 else ZERO), ("Effet nombre de commandes", "$", effet_volume),
                ("Effet panier moyen", "$", effet_panier)]

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
                 "Contribution (points de %)"]
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
    r.titre_evolution = "Ventes nettes cumulées : période choisie et comparaison"
    r.etiquettes = [_etiquette(j) for j in j1]
    r.series = [("Période choisie", cumul1), ("Période de comparaison", cumul0)]
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
    r.cartes = [("Moyenne par jour ouvert", "$", _d(moyenne)), ("Tendance par semaine", "$", _d(pente * 7)),
                ("Variabilité (coefficient de variation)", "%", _d(cv, "0.1")),
                ("Projection des 30 prochains jours", "$", _d(projection))]
    if meilleur:
        r.cartes.append(("Meilleur jour", "t", f"{meilleur} ({_argent(par_jour[meilleur])})"))
        r.cartes.append(("Jour le plus faible", "t", f"{pire} ({_argent(par_jour[pire])})"))
    mobile = []
    for i, j in enumerate(jours):
        fenetre = jours[max(0, i - 6):i + 1]
        mobile.append(_d(sum((par_jour.get(x, ZERO) for x in fenetre), ZERO) / len(fenetre)))
    r.titre_evolution = "Ventes nettes, moyenne mobile 7 jours et tendance"
    r.etiquettes = [_etiquette(j) for j in jours]
    r.series = [("Ventes nettes", [par_jour.get(j, ZERO) for j in jours]), ("Moyenne mobile 7 jours", mobile)]
    if len(ouverts) >= 3:
        r.series.append(("Tendance", [_d(max(0.0, origine + pente * i)) for i in range(len(jours))]))
    r.titre_repartition = "Indice saisonnier par jour de la semaine (100 = moyenne)"
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
                 "Variation sur la semaine précédente %", "Moyenne mobile 4 semaines"]
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
        constats.append(_k("attention" if cv >= 40 else "info", "Variabilité {n} : coefficient de variation de {cv} %.",
                           n=_t("faible") if cv < 20 else _t("moyenne") if cv < 40 else _t("forte"), cv=_nb(cv, 0)))
    if len(ouverts) < 14:
        constats.append(_k(None, "Choisissez au moins 4 semaines pour une tendance et des indices fiables."))
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
    r.cartes = [("Panier médian", "$", _d(_quantile(montants, 0.5))),
                ("Panier du 90e centile", "$", _d(_quantile(montants, 0.9))),
                ("Articles par panier (médiane)", "n", _d(_quantile(nombres, 0.5), "0.1")),
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
                        else _t("Panier médian {m}, proche du panier moyen {p} : paniers homogènes.",
                                m=_argent(_d(mediane)), p=_argent(_d(moyenne))))
        constats.append(_k(None, "{p} % des commandes n'ont qu'un article : piste de ventes complémentaires (voir « Articles "
                           "achetés ensemble »).", p=_nb(_pc(un_seul, len(c)), 0)))
        if avant:
            m0 = _quantile([float(x.nettes) for x in avant], 0.5)
            if m0:
                constats.append(_k("bon" if mediane >= m0 else "attention",
                                   "Panier médian de la période de comparaison : {m} ({v} %).", m=_argent(_d(m0)),
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
                 "Éléments pour 80 % des ventes", "% des éléments pour 80 %", "Indice de Gini", "Indice HHI",
                 "Concentration"]
    r.lignes = lignes
    art = dict((l[0], l) for l in lignes).get(_t("Articles"))
    clients = dims["Clients identifiés"]
    total_c = sum(float(x.nettes) for x in c)
    r.cartes = [("Indice de Gini des articles", "t", _nb(gini_articles, 2)),
                ("Part des 10 meilleurs articles", "%", art[4] if art else ZERO),
                ("Articles pour 80 % des ventes", "n", art[5] if art else 0),
                ("Part du meilleur client identifié", "%", _pc(max(clients.values()), total_c) if clients else ZERO),
                ("Part du meilleur jour", "%", _pc(max(dims["Jours"].values()), total_c) if dims["Jours"] else ZERO)]
    r.titre_evolution = "Courbes de concentration (% des ventes détenu par les x % premiers)"
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
        constats.append(_k(None, "{n} articles sur {t} ({p} %) font 80 % des ventes ; indice de Gini {g} (0 = ventes égales, "
                           "1 = un seul article).", n=art[5], t=art[1], p=_nb(art[6]), g=_nb(gini_articles, 2)))
        constats.append(_k("attention" if hhi_articles >= 2500 else "bon", "Concentration des articles {n} (HHI {h} : moins de 1 500 = faible, plus de 2 500 = "
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
    for x in c:
        quand = f"{x.moment:%Y-%m-%d %H:%M}"
        ids[(quand, x.numero)] = x.id
        brut = sum((l.ventes_brutes for l in x.lignes), ZERO)
        rabais = -sum((l.rabais for l in x.lignes), ZERO)
        if len(c) >= 20 and float(x.nettes) > seuil > 0:
            lignes.append([_t("Commande inhabituelle"), quand, x.numero, _t("Montant très élevé ({e})", e=x.employe),
                           x.nettes, _d(_quantile(montants, 0.5)), _d(float(x.nettes) - _quantile(montants, 0.5)), None])
        if brut > 0 and rabais / brut >= Decimal("0.5"):
            lignes.append([_t("Rabais de 50 % ou plus"), quand, x.numero, _t("Rabais de {p} % ({e})",
                                                                           p=_nb(_pc(rabais, brut), 0), e=x.employe),
                           x.nettes, _d(brut), _d(-rabais), None])
        if x.lignes and x.nettes <= 0 and not (brut > 0 and rabais / brut >= Decimal("0.5")):
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
    r.entetes = ["Type", "Date", "Commande ou jour", "Détail", "Montant", "Attendu", "Écart", "Écart-type (z)"]
    r.lignes = lignes
    compte = defaultdict(int)
    for l in lignes:
        compte[l[0]] += 1
    r.cartes = [("Anomalies relevées", "n", len(lignes)), ("Jours atypiques", "n", compte[_t("Jour atypique")]),
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
    constats = [_k(None, "Jour atypique : à plus de 2 écarts-types de la moyenne du même jour de la semaine (au moins 4 "
                   "semaines) ; commande inhabituelle : au-delà de Q3 + 3 × l'écart interquartile et du 99e centile ; prix inhabituel : "
                   "à 40 % ou plus du prix médian de l'article (5 ventes au moins).")]
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
    "Vedette": "Garder toujours en stock et mettre en avant",
    "Locomotive": "Populaire mais peu rentable : revoir le prix ou le coût d'achat",
    "Énigme": "Rentable mais peu vendu : mieux exposer, promouvoir",
    "Poids mort": "Peu vendu et peu rentable : réduire le stock ou retirer",
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
            quadrant = ("Vedette" if populaire and rentable else "Locomotive" if populaire else
                        "Énigme" if rentable else "Poids mort")
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
                 "Semaines de vente" if par_semaine else "Jours de vente", "Coefficient de variation", "Régularité (X / Y / Z)", "Bénéfice", "Marge %",
                 "Quadrant", "Conseil"]
    r.lignes = lignes
    r.cartes = [("Articles analysés", "n", n), ("Vedettes", "n", compte["Vedette"]),
                ("Locomotives", "n", compte["Locomotive"]), ("Énigmes", "n", compte["Énigme"]),
                ("Poids morts", "n", compte["Poids mort"]), ("Demande régulière (X)", "n",
                                                             sum(v for k, v in matrice_compte.items() if k[1] == "X"))]
    cases = [a + b for a in "ABC" for b in "XYZ"]
    r.titre_evolution = "Articles par classe 20/80 et régularité de la demande"
    r.genre_evolution = "barres"
    r.etiquettes = cases
    r.series = [("Articles", [matrice_compte.get(k, 0) for k in cases])]
    r.titre_repartition = "Ventes nettes par quadrant"
    r.repartition = [(_t(k), _d(v)) for k, v in sorted(ventes_quadrant.items(), key=lambda kv: -kv[1])]
    constats = [_k(None, "Popularité : part des quantités vendues d'au moins 70 % de la part égale ; rentabilité : bénéfice "
                   "par unité (CUMP Sage) au moins égal à la moyenne. X : demande régulière (coefficient de variation "
                   "≤ 0,5), Y : variable (≤ 1), Z : irrégulière ; mesurée {p}.",
                   p=_t("semaine par semaine") if par_semaine else _t("jour par jour"))]
    if not couts:
        constats.append(_k(None, "Coûts Sage absents : quadrants « Coût inconnu » (Sage ne répond pas ou articles non "
                           "reliés)."))
    if compte["Locomotive"]:
        constats.append(_k(None, "{n} locomotive(s) : articles très vendus à faible marge, premier levier de bénéfice.",
                           n=compte["Locomotive"]))
    if compte["Poids mort"]:
        constats.append(_k(None, "{n} poids mort(s) : {v} de ventes seulement.", n=compte["Poids mort"],
                           v=_argent(ventes_quadrant["Poids mort"])))
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
                 "Confiance A → B %", "Confiance B → A %", "Lift", "Catégories"]
    r.lignes = articles[:300] + cats[:100]
    fortes = [l for l in articles if l[7] >= 2]
    meilleure = max(articles, key=lambda l: (l[7] * min(l[3], 20)), default=None)
    r.cartes = [("Commandes de plusieurs articles", "%", _pc(plusieurs, n)), ("Paires fréquentes", "n", len(articles)),
                ("Paires à lift ≥ 2", "n", len(fortes)),
                ("Association la plus forte", "t", f"{meilleure[1]} + {meilleure[2]}" if meilleure else "—")]
    r.titre_evolution = "Commandes selon le nombre de catégories différentes"
    r.genre_evolution = "barres"
    r.etiquettes = ["1", "2", "3", "4", _t("5 et plus")]
    r.series = [("Commandes", [nb_categories.get(k, 0) for k in range(1, 6)])]
    r.titre_repartition = "Paires achetées le plus souvent ensemble"
    r.genre_repartition = "classement"
    r.argent_repartition = False
    r.repartition = [(f"{l[1]} + {l[2]}", Decimal(l[3])) for l in articles[:8]]
    constats = [_k(None, "Seules les paires vues dans au moins {m} commandes sont gardées. Confiance A → B : part des "
                   "commandes avec A qui ont aussi B ; lift > 1 : achetés ensemble plus souvent que le hasard.",
                   m=minimum)]
    if meilleure:
        constats.append(_k(None, "{p} % des clients qui prennent « {a} » prennent aussi « {b} » (lift {l}) : placer ces "
                           "articles côte à côte ou en offre groupée.", p=_nb(meilleure[5], 0), a=meilleure[1],
                           b=meilleure[2], l=_nb(meilleure[7], 1)))
    r.note = _note(constats)
    return r


# --------------------------------------------------------------------------------------------- employés
def employes(c, avant, ctx) -> RapportGestion:
    total = sum((x.nettes for x in c), ZERO)
    e = defaultdict(lambda: {"cmd": 0, "nettes": ZERO, "brut": ZERO, "rabais": ZERO, "remb": ZERO, "art": 0,
                             "qte": ZERO, "heures": set(), "clients": 0, "par_jour": defaultdict(Decimal)})
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
                       _pc(g["nettes"] - avant_e[nom], avant_e[nom]) if avant_e.get(nom) else None])
    r = RapportGestion()
    r.entetes = ["Employé", "Commandes", "Ventes nettes", "% des ventes", "Panier moyen", "Articles par commande",
                 "Prix moyen d'un article", "Taux de rabais %", "Taux de remboursement %", "Heures actives",
                 "Ventes par heure active", "Commandes par heure active", "Indice de panier (100 = moyenne)",
                 "Commandes avec client %", "Variation %"]
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
    r.entetes = ["Client", "Segment", "Récence (1-5)", "Fréquence (1-5)", "Montant (1-5)", "Score RFM",
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
    r.titre_repartition = "Ventes nettes par segment"
    r.repartition = [(_t(k), _d(v)) for k, v in sorted(ventes_seg.items(), key=lambda kv: -kv[1])]
    constats = [_k(None, "Récence, fréquence et montant notés de 1 à 5 (5 = meilleur) parmi les clients identifiés de la "
                   "période ; choisissez une longue période (6 à 12 mois) pour une segmentation fiable.")]
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
        constats.append(_k(None, "Un client revient en moyenne tous les {j} jours (médiane).",
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
                 "Quantité par jour avant", "Quantité par jour après", "Variation des quantités %", "Élasticité",
                 "Ventes nettes par jour avant", "Ventes nettes par jour après", "Effet sur les ventes %",
                 "Jours comparés", "Lecture"]
    r.lignes = lignes
    hausses = [l for l in lignes if l[5] > 0]
    elasticites = [float(l[9]) for l in lignes if l[9] is not None]
    effet = sum((l[11] - l[10] for l in lignes), ZERO)
    r.cartes = [("Changements de prix", "n", len(lignes)), ("Hausses", "n", len(hausses)),
                ("Baisses", "n", len(lignes) - len(hausses)),
                ("Élasticité médiane", "t", _nb(st.median(elasticites), 2) if elasticites else "—"),
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
                   "Élasticité −1 : une hausse de 10 % fait perdre 10 % des quantités. Une rupture de stock, la saison ou "
                   "une promotion peuvent aussi jouer : à lire avec prudence.")]
    if elasticites:
        constats.append(_k(None, "Élasticité médiane {e} : {s}.", e=_nb(st.median(elasticites), 2),
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
        r.entetes, r.cartes = ["Mois du premier achat"], [("Cohortes", "n", 0)]
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
    r.cartes = [("Cohortes", "n", len(groupes)), ("Clients suivis", "n", len(achats)),
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
    choisies = [("a_variation", "Ventes nettes"), ("a_variation", "Variation"), ("a_tendance", "Tendance par semaine"),
                ("a_tendance", "Projection des 30 prochains jours"), ("a_paniers", "Panier médian"),
                ("a_anomalies", "Anomalies relevées"), ("a_matrice", "Locomotives"), ("a_fidelite", "Taux de rétention")]
    if not ctx.get("couts"):
        choisies.remove(("a_matrice", "Locomotives"))  # sans coûts Sage, aucune locomotive ne peut être reconnue
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
    r.entetes = ["Priorité", "Décision à prendre", "Pourquoi", "Où regarder"]
    r.lignes = [[_t(PRIORITES[p]), _t(decision), raison, _t(section) + " > " + _t(libelle)]
                for p, decision, raison, section, libelle in sorted(_decisions(sous), key=lambda x: x[0])]
    nb = {n: sum(1 for x in constats if x[1] == n) for n in ("alerte", "attention", "bon")}
    entete = _t("{a} point(s) à agir, {s} à surveiller, {b} point(s) positif(s) ; {d} décision(s) proposée(s).",
                a=nb["alerte"], s=nb["attention"], b=nb["bon"], d=len(r.lignes))
    # lecture de la direction : les décisions d'abord (couleur = priorité), puis les points positifs ; le détail de
    # chaque constat reste dans son analyse
    couleur_priorite = {1: "alerte", 2: "attention", 3: "info"}
    decisions = [MARQUES[couleur_priorite[p]] + _t("Décision : {d} — {r}", d=_t(d), r=raison)
                 for p, d, raison, _s, _l in sorted(_decisions(sous), key=lambda x: x[0])]
    positifs = [MARQUES["bon"] + texte for _o, n, texte in constats if n == "bon"]
    r.note = _note([MARQUES["info"] + entete] + decisions + positifs)
    return r


PRIORITES = {1: "1 — Haute", 2: "2 — Moyenne", 3: "3 — Basse"}


def _carte(r, titre, defaut=None):
    return next((v for t_, _g, v in r.cartes if t_ == titre), defaut)


def _decisions(sous: dict) -> list[tuple]:
    """Décisions proposées à la direction : (priorité, décision, pourquoi, section, analyse)."""
    vide = RapportGestion()
    sortie = []

    def ajouter(priorite, decision, raison, cle):
        libelle, _c_, _f, section, _a = next(a for a in ANALYSES if a[1] == cle)
        sortie.append((priorite, decision, raison, section, libelle))

    var = sous.get("a_variation", vide)
    variation_ = _carte(var, "Variation")
    if variation_ is not None and variation_ < -5:
        baisses = [l for l in var.lignes if l[0] == _t("Catégorie") and l[4] < 0]
        cible = baisses[0][1] if baisses else ""
        ajouter(1, "Agir sur la baisse des ventes", _t("Ventes nettes {v} % ; plus forte baisse : {c}.",
                                                       v=_nb(variation_), c=cible), "a_variation")
    effet_panier = _carte(var, "Effet panier moyen")
    if effet_panier is not None and effet_panier < 0:
        ajouter(2, "Relever le panier moyen (ventes complémentaires, offres groupées)",
                _t("Le panier plus petit coûte {v}.", v=_argent(effet_panier)), "a_variation")
    ano = sous.get("a_anomalies", vide)
    if (_carte(ano, "Rabais de 50 % ou plus") or 0) > 0:
        ajouter(1, "Contrôler les rabais de 50 % et plus avec les employés concernés",
                _t("{n} commande(s) à fort rabais.", n=_carte(ano, "Rabais de 50 % ou plus")), "a_anomalies")
    if (_carte(ano, "Prix inhabituels") or 0) > 0:
        ajouter(2, "Vérifier les prix dans Clover (prix saisis à la main ou erronés)",
                _t("{n} ligne(s) à un prix inhabituel.", n=_carte(ano, "Prix inhabituels")), "a_anomalies")
    tend = sous.get("a_tendance", vide)
    if (_carte(tend, "Tendance par semaine") or 0) < 0:
        ajouter(2, "Préparer un plan pour inverser la tendance",
                _t("Ventes en baisse de {v} par semaine.", v=_argent(abs(_carte(tend, "Tendance par semaine")))),
                "a_tendance")
    if tend.repartition:
        faible = tend.repartition[-1]
        if faible[1] < 80:
            ajouter(3, _t("Animer le {j} (promotion, dégustation)", j=faible[0]),
                    _t("Jour le plus faible : indice {i} (100 = moyenne).", i=_nb(faible[1], 0)), "a_tendance")
    mat = sous.get("a_matrice", vide)
    if (_carte(mat, "Locomotives") or 0) > 0:
        ajouter(1, "Revoir le prix ou le coût d'achat des locomotives",
                _t("{n} article(s) très vendus à faible marge.", n=_carte(mat, "Locomotives")), "a_matrice")
    if (_carte(mat, "Poids morts") or 0) > 0:
        ajouter(3, "Réduire le stock ou retirer les poids morts",
                _t("{n} article(s) peu vendus et peu rentables.", n=_carte(mat, "Poids morts")), "a_matrice")
    ass = sous.get("a_associations", vide)
    meilleure = _carte(ass, "Association la plus forte")
    if meilleure and meilleure != "—":
        ajouter(3, _t("Placer côte à côte ou grouper : {p}", p=meilleure),
                _t("Articles achetés ensemble bien plus souvent que le hasard."), "a_associations")
    prix_ = sous.get("a_prix", vide)
    couteux = [l for l in prix_.lignes if l[11] < l[10] and l[5] > 0]
    if couteux:
        pire = min(couteux, key=lambda l: l[11] - l[10])
        ajouter(2, _t("Revoir la hausse de prix de {a}", a=pire[0]),
                _t("{v} de ventes par jour depuis la hausse.", v=_argent(pire[11] - pire[10])), "a_prix")
    emp = sous.get("a_employes", vide)
    if emp.lignes:  # employés qui accordent plus du double du taux de rabais moyen (10 commandes au moins)
        brut = sum((l[2] for l in emp.lignes), ZERO)
        moyen = (sum((l[2] * l[7] for l in emp.lignes), ZERO) / brut) if brut else ZERO
        trop = [l for l in emp.lignes if moyen and l[7] > moyen * 2 and l[1] >= 10]
        if trop:
            ajouter(1, "Encadrer les rabais accordés", _t("{n} employé(s) au-delà du double du taux moyen ({m} %) : {e}.",
                                                          n=len(trop), m=_nb(moyen), e=", ".join(
                                                              f"{l[0]} ({_nb(l[7])} %)" for l in trop)), "a_employes")
    con = sous.get("a_concentration", vide)
    for l in con.lignes:
        if l[0] == _t("Employés") and l[2] >= 60:
            ajouter(2, "Former un deuxième vendeur principal", _t("{p} % des ventes passent par un seul employé.",
                                                                 p=_nb(l[2])), "a_concentration")
    rfm_ = sous.get("a_rfm", vide)
    if (_carte(rfm_, "À risque") or 0) > 0:
        ajouter(2, "Relancer les clients à risque", _t("{n} client(s) qui achetaient souvent ne viennent plus.",
                                                       n=_carte(rfm_, "À risque")), "a_rfm")
    part = _carte(rfm_, "Part des ventes avec un client")
    if part is not None and part < 30:
        ajouter(2, "Demander le client à la caisse (fidélité, relances)",
                _t("Seules {p} % des ventes sont rattachées à un client.", p=_nb(part, 0)), "a_rfm")
    fid = sous.get("a_fidelite", vide)
    retention = _carte(fid, "Taux de rétention")
    if retention is not None and retention < 30 and _carte(fid, "Clients perdus"):
        ajouter(2, "Faire revenir les clients perdus (offre de retour)",
                _t("Rétention de {p} % ; {n} client(s) perdus.", p=_nb(retention, 0), n=_carte(fid, "Clients perdus")),
                "a_fidelite")
    pan = sous.get("a_paniers", vide)
    if (_carte(pan, "Paniers d'un seul article") or 0) >= 30:
        ajouter(3, "Proposer un 2e article à la caisse", _t("{p} % des paniers n'ont qu'un article.",
                                                            p=_nb(_carte(pan, "Paniers d'un seul article"), 0)),
                "a_paniers")
    return sortie


# état (couleur) d'une carte selon son titre et sa valeur : None = neutre
ETATS_CARTES = {
    "Variation": lambda v: "bon" if v >= 0 else "alerte", "Écart": lambda v: "bon" if v >= 0 else "alerte",
    "Effet nombre de commandes": lambda v: "bon" if v >= 0 else "attention",
    "Effet panier moyen": lambda v: "bon" if v >= 0 else "attention",
    "Tendance par semaine": lambda v: "bon" if v >= 0 else "attention",
    "Effet sur les ventes par jour": lambda v: "bon" if v >= 0 else "attention",
    "Anomalies relevées": lambda v: "attention" if v else "bon",
    "Rabais de 50 % ou plus": lambda v: "alerte" if v else "bon",
    "Prix inhabituels": lambda v: "attention" if v else "bon",
    "Commandes inhabituelles": lambda v: "attention" if v else None,
    "Jours atypiques": lambda v: "attention" if v else None,
    "Locomotives": lambda v: "attention" if v else None, "Poids morts": lambda v: "attention" if v else None,
    "Vedettes": lambda v: "bon" if v else None, "À risque": lambda v: "alerte" if v else "bon",
    "Champions": lambda v: "bon" if v else None, "Clients perdus": lambda v: "attention" if v else "bon",
    "Taux de rétention": lambda v: "bon" if v >= 30 else "attention",
    "Paniers d'un seul article": lambda v: "attention" if v >= 30 else "bon",
    "Part des ventes avec un client": lambda v: "attention" if v < 30 else "bon",
    "Reviennent le mois suivant": lambda v: "bon" if v >= 20 else "attention",
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
DEFINITIONS = ("Jour atypique :", "Popularité :", "Seules les paires", "Heure active :", "Récence, fréquence",
               "Retenu :", "Changement de prix :", "Chaque ligne suit", "Choisissez au moins")


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
    locomotives = [l for l in r.lignes if l[11] == _t("Locomotive")][:8]
    if locomotives:
        second = _graphe("classement", "Locomotives à revoir en priorité (ventes nettes)",
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
            _graphe("classement", "Paires au lift le plus fort", "", elements=[(f"{l[1]} + {l[2]}", l[7]) for l in lift])]


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
    return [_graphe("barres", "Clients par segment", "", etiquettes=ordre, series=[("Clients", [nb[k] for k in ordre])]),
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


SUPPLEMENTS = {"a_variation": _sup_variation, "a_tendance": _sup_tendance, "a_paniers": _sup_paniers,
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
    ("Anomalies et alertes", "a_anomalies", anomalies, "Activités de vente", "Remboursements"),
    ("Tendance et saisonnalité", "a_tendance", tendance, "Rapports", "evolution_annees"),
    ("Analyse de la variation", "a_variation", variation, "Rapports", "a_tendance"),
    ("Analyse des paniers", "a_paniers", paniers, "Rapports", "Jour × heure"),
    ("Concentration des ventes", "a_concentration", concentration, "Rapports", "a_paniers"),
    ("Matrice des articles", "a_matrice", matrice, "Articles", "Par catégorie"),
    ("Articles achetés ensemble", "a_associations", associations, "Articles", "a_matrice"),
    ("Prix et sensibilité au prix", "a_prix", prix, "Articles", "a_associations"),
    ("Performance des employés", "a_employes", employes, "Employés", "Par employé"),
    ("Segmentation RFM", "a_rfm", rfm, "Clients", "Par client"),
    ("Fidélité et rétention", "a_fidelite", fidelite, "Clients", "a_rfm"),
    ("Cohortes de clients", "a_cohortes", cohortes, "Clients", "a_fidelite"),
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


def calculer(cle: str, donnees, autres, couts: dict, du: date, au: date, du2: date, au2: date):
    """Analyse `cle` sur les données (déjà filtrées) de la période et de sa comparaison."""
    fonction = next(f for _l, c, f, *_ in ANALYSES if c == cle)
    ctx = {"du": du, "au": au, "du2": du2, "au2": au2, "couts": couts or {}, "donnees": donnees}
    return _completer(cle, fonction(_commandes(donnees), _commandes(autres), ctx))
