"""États de base des statistiques Clover enrichis comme les analyses (demande du propriétaire du 2026-11-09 :
« développe tous les états ») : pour chaque état (Par jour, Par heure, Par article, Par employé…), des cartes
chiffrées, des constats en clair comparés à la période d'avant et deux graphiques de plus, tirés du tableau de l'état
lui-même (statistiques_clover.statistiques) et du même état sur la période de comparaison. Rien n'est relu dans
Clover. Mêmes formes que analyses_clover (RapportGestion : cartes, note, graphiques) : Windows et le web les
affichent avec les mêmes fonctions."""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from .analyses_clover import _argent, _d, _graphe, _k, _nb, _note, _pc, _signe, _t
from .rapports_gestion import RapportGestion

ZERO = Decimal("0")
SANS_CLIENT = ("Sans client", "No customer")
# états enrichis (les autres : accueil, aperçus, liste d'articles, péremption, prévisions ont déjà leur page)
ETATS = ("Rapport des ventes", "Par jour", "Par jour de la semaine", "Par heure", "Jour × heure", "Par employé",
         "Par article", "Par catégorie", "Bénéfices", "Par mode de paiement", "Par type de carte",
         "Par mode de saisie de la carte", "Par appareil", "Par client", "Rabais", "Commandes", "Paiements",
         "Remboursements")


def _col(entetes, nom):
    return entetes.index(nom) if nom in entetes else None


def _v(x) -> Decimal:
    try:
        return Decimal(str(x)) if x not in (None, "") else ZERO
    except ArithmeticError:
        return ZERO


def _variation(actuel, avant) -> Decimal | None:
    return _pc(actuel - avant, avant) if avant else None


def _comparer(constats, libelle, actuel, avant, argent=True, inverse=False):
    """Constat de variation d'un total avec la période d'avant (≥ 5 % : bon / attention ; `inverse` : une hausse
    est à surveiller, rabais par exemple)."""
    var = _variation(actuel, avant)
    if var is None:
        return
    texte = _argent(actuel) if argent else _nb(actuel, 0)
    texte0 = _argent(avant) if argent else _nb(avant, 0)
    haut, bas = ("attention", "bon") if inverse else ("bon", "attention")
    if var >= 5:
        constats.append(_k(haut, "{l} : {a} contre {b} la période d'avant ({p} %).", l=_t(libelle), a=texte, b=texte0,
                           p="+" + _nb(var)))
    elif var <= -5:
        constats.append(_k(bas, "{l} : {a} contre {b} la période d'avant ({p} %).", l=_t(libelle), a=texte,
                           b=texte0, p=_nb(var)))
    else:
        constats.append(_k("info", "{l} : {a}, stable par rapport à la période d'avant ({b}).", l=_t(libelle), a=texte,
                           b=texte0))


# --------------------------------------------------------------------------------------------- temps
def _jours(entetes, lignes, avant, r, constats):
    """Par jour / Rapport des ventes : une ligne par date."""
    i_n = _col(entetes, "Ventes nettes")
    i_c = _col(entetes, "Commandes")
    jours = [l for l in lignes if _v(l[i_n]) > 0]
    total = sum((_v(l[i_n]) for l in lignes), ZERO)
    total0 = sum((_v(l[i_n]) for l in (avant[1] if avant else [])), ZERO)
    commandes = sum(int(_v(l[i_c])) for l in lignes)
    moyenne = total / len(jours) if jours else ZERO
    meilleur = max(jours, key=lambda l: _v(l[i_n]), default=None)
    faible = min(jours, key=lambda l: _v(l[i_n]), default=None)
    r.cartes = [("Jours avec des ventes", "n", len(jours)), ("Ventes nettes", "$", _d(total)),
                ("Ventes moyennes par jour", "$", _d(moyenne)),
                ("Commandes par jour", "n", _d(Decimal(commandes) / len(jours), "0.1") if jours else 0),
                ("Meilleur jour", "t", f"{meilleur[0]} ({_argent(_v(meilleur[i_n]))})" if meilleur else "—"),
                ("Jour le plus faible", "t", f"{faible[0]} ({_argent(_v(faible[i_n]))})" if faible else "—")]
    _comparer(constats, "Ventes nettes", total, total0)
    if meilleur and moyenne:
        constats.append(_k("info", "Meilleur jour : {j} ({v}, {p} % de plus qu'un jour moyen).", j=meilleur[0],
                           v=_argent(_v(meilleur[i_n])), p=_nb(_pc(_v(meilleur[i_n]) - moyenne, moyenne), 0)))
    faibles = [l for l in jours if moyenne and _v(l[i_n]) < moyenne / 2]
    if faibles:
        constats.append(_k("attention", "{n} jour(s) font moins de la moitié d'un jour moyen, dont le {j} ({v}) : "
                                        "fermeture, panne ou météo ?", n=len(faibles),
                           j=min(faibles, key=lambda l: _v(l[i_n]))[0], v=_argent(_v(faible[i_n]))))
    etiquettes = [str(l[0])[8:10] + "/" + str(l[0])[5:7] for l in lignes]
    i_p = _col(entetes, "Panier moyen")
    paniers = [(_d(_v(l[i_n]) / int(_v(l[i_c]))) if int(_v(l[i_c])) else ZERO) for l in lignes] if i_p is None \
        else [_v(l[i_p]) for l in lignes]
    r.graphiques = [_graphe("courbes", "Commandes par jour", "", etiquettes, [("Commandes", [_v(l[i_c]) for l in lignes])]),
                    _graphe("courbes", "Panier moyen par jour", "$", etiquettes, [("Panier moyen", paniers)])]


def _periodique(entetes, lignes, avant, r, constats, nom):
    """Par jour de la semaine / Par heure."""
    i_n, i_c, i_p = _col(entetes, "Ventes nettes"), _col(entetes, "Commandes"), _col(entetes, "Panier moyen")
    total = sum((_v(l[i_n]) for l in lignes), ZERO)
    # une heure presque vide (ouverture, fermeture) n'est pas « la plus faible » : 1 % des ventes au moins
    actifs = [l for l in lignes if _v(l[i_n]) > 0 and (not total or _v(l[i_n]) >= total / 100)]
    meilleur = max(actifs, key=lambda l: _v(l[i_n]), default=None)
    faible = min(actifs, key=lambda l: _v(l[i_n]), default=None)
    panier = max(actifs, key=lambda l: _v(l[i_p]), default=None)
    jour = nom == "Par jour de la semaine"
    mot = "Jour" if jour else "Heure"
    trois = sum(sorted((_v(l[i_n]) for l in actifs), reverse=True)[:3], ZERO)
    r.cartes = [("Jour le plus fort" if jour else "Heure la plus forte", "t", str(meilleur[0]) if meilleur else "—"),
                ("Jour le plus faible" if jour else "Heure la plus faible", "t", str(faible[0]) if faible else "—"),
                ("Écart entre le plus fort et le plus faible", "%",
                 _pc(_v(meilleur[i_n]) - _v(faible[i_n]), _v(faible[i_n])) if meilleur and _v(faible[i_n]) else 0),
                ("Part des 3 plus forts", "%", _pc(trois, total)),
                ("Panier moyen le plus élevé", "t", f"{panier[0]} ({_argent(_v(panier[i_p]))})" if panier else "—")]
    if meilleur:
        constats.append(_k("info", "Jour le plus fort : {a} ({p} % des ventes) ; le plus faible : {b} ({q} %)." if jour
                           else "Heure la plus forte : {a} ({p} % des ventes) ; la plus faible : {b} ({q} %).",
                           a=meilleur[0], p=_nb(_pc(_v(meilleur[i_n]), total)), b=faible[0],
                           q=_nb(_pc(_v(faible[i_n]), total))))
    if avant and avant[1]:
        par0 = {l[0]: _v(l[i_n]) for l in avant[1]}
        ecarts = [(l[0], _variation(_v(l[i_n]), par0.get(l[0], ZERO))) for l in actifs]
        ecarts = [(n, v) for n, v in ecarts if v is not None]
        if ecarts:
            haut, bas = max(ecarts, key=lambda x: x[1]), min(ecarts, key=lambda x: x[1])
            if haut[1] >= 10:
                constats.append(_k("bon", "Plus forte hausse : {n} ({p} % par rapport à la période d'avant).", n=haut[0],
                                   p="+" + _nb(haut[1])))
            if bas[1] <= -10:
                constats.append(_k("attention", "Plus forte baisse : {n} ({p} % par rapport à la période d'avant).",
                                   n=bas[0], p=_nb(bas[1])))
    etiquettes = [str(l[0]) for l in lignes]
    r.graphiques = [_graphe("barres", "Commandes par jour de la semaine" if jour else "Commandes par heure", "",
                            etiquettes, [("Commandes", [_v(l[i_c]) for l in lignes])]),
                    _graphe("barres", "Panier moyen par jour de la semaine" if jour else "Panier moyen par heure", "$",
                            etiquettes,
                            [("Panier moyen", [_v(l[i_p]) for l in lignes])])]


def _chaleur(entetes, lignes, avant, r, constats):
    heures = entetes[1:-1]
    cases = [(l[0], h, _v(v)) for l in lignes for h, v in zip(heures, l[1:-1]) if _v(v) > 0]
    total = sum((c[2] for c in cases), ZERO)
    meilleur = max(cases, key=lambda c: c[2], default=None)
    faible = min(cases, key=lambda c: c[2], default=None)
    par_heure = defaultdict(Decimal)
    for _j, h, v in cases:
        par_heure[h] += v
    r.cartes = [("Heures avec des ventes", "n", len(cases)),
                ("Meilleure heure de la semaine", "t", f"{meilleur[0]} {meilleur[1]}" if meilleur else "—"),
                ("Ventes de la meilleure heure", "$", _d(meilleur[2]) if meilleur else 0),
                ("Heure la plus faible", "t", f"{faible[0]} {faible[1]}" if faible else "—")]
    if meilleur:
        constats.append(_k("info", "La meilleure heure est le {j} à {h} ({v}) ; la plus faible, le {a} à {b} ({w}).",
                           j=meilleur[0], h=meilleur[1], v=_argent(meilleur[2]), a=faible[0], b=faible[1],
                           w=_argent(faible[2])))
        dix = sum(sorted((c[2] for c in cases), reverse=True)[:10], ZERO)
        constats.append(_k("info", "Les 10 meilleures heures de la semaine font {p} % des ventes.",
                           p=_nb(_pc(dix, total))))
    r.graphiques = [_graphe("barres", "Ventes nettes par jour de la semaine", "$", [str(l[0]) for l in lignes],
                            [("Ventes nettes", [_v(l[-1]) for l in lignes])]),
                    _graphe("barres", "Ventes nettes par heure", "$", list(heures),
                            [("Ventes nettes", [_d(par_heure.get(h, ZERO)) for h in heures])])]


# --------------------------------------------------------------------------------------------- dimensions
def _dimension(entetes, lignes, avant, r, constats, nom_col, val_col, mot, unite="$", inverse=False, exclure=()):
    """État par élément (employé, article, catégorie, appareil, client, mode de paiement…) : part du premier,
    concentration, hausses et baisses par rapport à la période d'avant."""
    i_v = _col(entetes, val_col)
    i_k = _col(entetes, nom_col)
    if i_v is None or i_k is None:
        return
    vals = [(str(l[i_k]), abs(_v(l[i_v])) if inverse else _v(l[i_v])) for l in lignes if str(l[i_k]) not in exclure]
    total = sum((v for _n, v in vals), ZERO)
    tri = sorted(vals, key=lambda x: -x[1])
    dix = sum((v for _n, v in tri[:10]), ZERO)
    premier = tri[0] if tri else None
    avant_par = {}
    if avant and avant[1] is not None:
        j_v, j_k = _col(avant[0], val_col), _col(avant[0], nom_col)
        if j_v is not None and j_k is not None:
            avant_par = {str(l[j_k]): abs(_v(l[j_v])) if inverse else _v(l[j_v]) for l in avant[1]
                         if str(l[j_k]) not in exclure}
    total0 = sum(avant_par.values(), ZERO)
    fmt = _argent if unite == "$" else (lambda x: _nb(x, 0))
    r.cartes = [(f"{mot} dans la période", "n", len([v for _n, v in vals if v > 0])),
                ("Total", unite if unite == "$" else "n", _d(total) if unite == "$" else int(total)),
                ("Le premier", "t", premier[0] if premier else "—"),
                ("Part du premier", "%", _pc(premier[1], total) if premier and total else 0)]
    if len(vals) > 10:
        r.cartes.append(("Part des 10 premiers", "%", _pc(dix, total) if total else 0))
    if total0:
        r.cartes.append(("Variation des rabais" if inverse else "Variation", "%", _variation(total, total0)))
        _comparer(constats, "Total", total, total0, unite == "$", inverse)
    if premier and total and len(vals) > 1:
        constats.append(_k("info", "« {n} » fait {p} % du total ; les 10 premiers en font {q} %." if len(vals) > 10
                           else "« {n} » fait {p} % du total.", n=premier[0], p=_nb(_pc(premier[1], total)),
                           q=_nb(_pc(dix, total))))
    variations = []
    if avant_par:
        nouveaux = [n for n, v in vals if v and n not in avant_par]
        perdus = [n for n, v in avant_par.items() if v and n not in {x for x, y in vals if y}]
        for n, v in vals:
            v0 = avant_par.get(n)
            if v0:
                variations.append((n, v - v0))
        variations.sort(key=lambda x: -x[1])
        if variations and variations[0][1] > 0 and len(vals) > 1:
            constats.append(_k("attention" if inverse else "bon", "Plus forte hausse : {n} ({e}).",
                               n=variations[0][0], e="+" + fmt(variations[0][1])))
        if variations and variations[-1][1] < 0 and len(vals) > 1:
            constats.append(_k("bon" if inverse else "attention", "Plus forte baisse : {n} ({e}).",
                               n=variations[-1][0], e=fmt(variations[-1][1])))
        if nouveaux and len(lignes) > 3:
            constats.append(_k("info", "{n} nouveau(x) par rapport à la période d'avant, dont « {a} ».",
                               n=len(nouveaux), a=nouveaux[0]))
        if perdus and len(lignes) > 3:
            constats.append(_k("attention", "{n} présent(s) la période d'avant mais plus maintenant, dont « {a} ».",
                               n=len(perdus), a=perdus[0]))
    r.graphiques = [
        _graphe("classement", "Plus fortes hausses et baisses par rapport à la période d'avant", unite,
                elements=[_signe(n, e) for n, e in (variations[:4] + sorted((x for x in variations[-4:] if x[1] < 0),
                                                                            key=lambda x: x[1])) if e]),
        _graphe("anneau", "Part de chacun", unite, elements=[(n, v) for n, v in tri if v > 0])]
    return [x for x in tri if x[1] > 0]


def _employes(entetes, lignes, avant, r, constats):
    _dimension(entetes, lignes, avant, r, constats, "Employé", "Ventes nettes", "Employés")
    i_p, i_r = _col(entetes, "Panier moyen"), _col(entetes, "Rabais")
    if lignes:
        haut = max(lignes, key=lambda l: _v(l[i_p]))
        constats.append(_k("info", "Panier moyen le plus élevé : {n} ({v}).", n=haut[0], v=_argent(_v(haut[i_p]))))
    if i_r is not None:
        rab = sorted(((str(l[0]), abs(_v(l[i_r]))) for l in lignes), key=lambda x: -x[1])
        r.graphiques[1] = _graphe("classement", "Panier moyen par employé", "$",
                                  elements=sorted(((str(l[0]), _v(l[i_p])) for l in lignes), key=lambda x: -x[1])[:8])
        if rab and rab[0][1]:
            r.graphiques.append(_graphe("classement", "Rabais accordés par employé", "$", elements=rab[:8]))
            r.graphiques.append(_graphe("classement", "Commandes par employé", "",
                                        elements=sorted(((str(l[0]), _v(l[1])) for l in lignes),
                                                        key=lambda x: -x[1])[:8]))


def _articles(entetes, lignes, avant, r, constats):
    tri = _dimension(entetes, lignes, avant, r, constats, "Article", "Ventes nettes", "Articles")
    i_r, i_b, i_c, i_n = (_col(entetes, n) for n in ("Rabais", "Ventes brutes", "Catégorie", "Ventes nettes"))
    if i_c is not None:  # 1 000 articles dans un anneau : illisible, la part par catégorie à la place
        par_cat = defaultdict(Decimal)
        for l in lignes:
            par_cat[str(l[i_c])] += _v(l[i_n])
        r.graphiques[1] = _graphe("anneau", "Ventes nettes par catégorie", "$",
                                  elements=sorted(((k, v) for k, v in par_cat.items() if v > 0), key=lambda kv: -kv[1]))
    if i_r is not None and i_b is not None:
        rab = sorted(((str(l[0]), abs(_v(l[i_r])), _v(l[i_b])) for l in lignes), key=lambda x: -x[1])
        if rab and rab[0][1]:
            constats.append(_k("info", "Article le plus remisé : {n} ({v} de rabais).", n=rab[0][0],
                               v=_argent(rab[0][1])))
        r.graphiques.append(_graphe("classement", "Articles les plus remisés", "$",
                                    elements=[(n, v) for n, v, _b in rab[:8] if v]))
    if tri:
        n80, cumul, total = 0, ZERO, sum((v for _n, v in tri), ZERO)
        for _n, v in tri:
            cumul += v
            n80 += 1
            if total and cumul >= total * Decimal("0.8"):
                break
        r.cartes.append(("Articles qui font 80 % des ventes", "n", n80))
        constats.append(_k("info", "{n} article(s) sur {t} font 80 % des ventes.", n=n80, t=len(tri)))


def _categories(entetes, lignes, avant, r, constats):
    _dimension(entetes, lignes, avant, r, constats, "Catégorie", "Ventes nettes", "Catégories")
    i_a = _col(entetes, "Articles différents")
    i_n = _col(entetes, "Ventes nettes")
    if i_a is not None:
        par_article = sorted(((str(l[0]), _d(_v(l[i_n]) / int(_v(l[i_a])))) for l in lignes if int(_v(l[i_a]))),
                             key=lambda x: -x[1])
        r.graphiques.append(_graphe("classement", "Articles différents par catégorie", "",
                                    elements=sorted(((str(l[0]), _v(l[i_a])) for l in lignes), key=lambda x: -x[1])[:8]))
        r.graphiques.append(_graphe("classement", "Ventes moyennes par article de la catégorie", "$",
                                    elements=par_article[:8]))


def _benefices(entetes, lignes, avant, r, constats):
    i_v, i_c, i_b, i_m = (_col(entetes, n) for n in ("Ventes nettes", "Coût des ventes", "Bénéfice", "Marge %"))
    connus = [l for l in lignes if l[i_c] not in (None, "")]
    ventes = sum((_v(l[i_v]) for l in connus), ZERO)
    benef = sum((_v(l[i_b]) for l in connus), ZERO)
    negatifs = [l for l in connus if _v(l[i_b]) < 0]
    r.cartes = [("Articles au coût connu", "n", len(connus)), ("Bénéfice", "$", _d(benef)),
                ("Marge brute", "%", _pc(benef, ventes) if ventes else 0), ("Articles vendus à perte", "n", len(negatifs)),
                ("Articles sans coût Sage", "n", len(lignes) - len(connus))]
    if ventes:
        constats.append(_k("info", "Marge brute des articles au coût connu : {p} % ({b} de bénéfice).",
                           p=_nb(_pc(benef, ventes)), b=_argent(benef)))
    if negatifs:
        pire = min(negatifs, key=lambda l: _v(l[i_b]))
        constats.append(_k("alerte", "{n} article(s) vendus à perte, dont {a} ({b}) : vérifier le prix ou le coût Sage.",
                           n=len(negatifs), a=pire[0], b=_argent(_v(pire[i_b]))))
    if len(lignes) > len(connus):
        constats.append(_k("attention", "{n} article(s) sans coût dans Sage : leur bénéfice n'est pas compté.",
                           n=len(lignes) - len(connus)))
    par_cat = defaultdict(Decimal)
    for l in connus:
        par_cat[str(l[1])] += _v(l[i_b])
    r.graphiques = [_graphe("classement", "Marges les plus faibles (%)", "%",
                            elements=[(str(l[0]), _v(l[i_m])) for l in sorted(connus, key=lambda l: _v(l[i_m]))[:8]]),
                    _graphe("anneau", "Bénéfice par catégorie", "$",
                            elements=sorted(((k, v) for k, v in par_cat.items() if v > 0), key=lambda kv: -kv[1]))]


def _paiements_par(entetes, lignes, avant, r, constats, nom, mot):
    _dimension(entetes, lignes, avant, r, constats, entetes[0], "Montant", mot)
    i_m, i_p = _col(entetes, "Moyenne"), _col(entetes, "Paiements")
    if i_m is not None:
        r.graphiques[1] = _graphe("anneau", "Nombre de paiements", "", elements=[(str(l[0]), _v(l[i_p])) for l in lignes])
        r.graphiques.append(_graphe("classement", "Montant moyen d'un paiement", "$",
                                    elements=sorted(((str(l[0]), _v(l[i_m])) for l in lignes), key=lambda x: -x[1])))


def _clients(entetes, lignes, avant, r, constats, ctx):
    i_k, i_n, i_c, i_p = (_col(entetes, n) for n in ("Client", "Ventes nettes", "Commandes", "Panier moyen"))
    total_tout = sum((_v(l[i_n]) for l in lignes), ZERO)
    lignes = [l for l in lignes if str(l[i_k]) not in SANS_CLIENT]
    _dimension(entetes, lignes, avant, r, constats, "Client", "Ventes nettes", "Clients", exclure=SANS_CLIENT)
    avant_noms = {str(l[0]) for l in (avant[1] if avant else [])}
    nouveaux = [l for l in lignes if str(l[i_k]) not in avant_noms] if avant_noms else []
    fideles = [l for l in lignes if int(_v(l[i_c])) >= 3]
    identifie = sum((_v(l[i_n]) for l in lignes), ZERO)
    r.cartes += [("Ventes avec un client identifié", "%", _pc(identifie, total_tout) if total_tout else 0),
                 ("Clients venus 3 fois ou plus", "n", len(fideles))]
    if lignes:
        constats.append(_k("attention" if total_tout and _pc(identifie, total_tout) < 10 else "info",
                           "Seulement {p} % des ventes ont un client identifié ({n} client(s)) : demander le nom ou le "
                           "téléphone à la caisse permettrait de suivre les clients fidèles."
                           if total_tout and _pc(identifie, total_tout) < 10
                           else "{p} % des ventes ont un client identifié ({n} client(s)).",
                           p=_nb(_pc(identifie, total_tout) if total_tout else ZERO),
                           n=sum(1 for l in lignes if _v(l[i_n]) > 0)))
        if fideles:
            constats.append(_k("info", "{b} client(s) sont venus 3 fois ou plus dans la période.", b=len(fideles)))
    r.graphiques[1] = _graphe("classement", "Panier moyen des meilleurs clients", "$",
                              elements=[(str(l[0]), _v(l[i_p])) for l in lignes[:8]])
    r.graphiques.append(_graphe("classement", "Clients venus le plus souvent", "",
                                elements=sorted(((str(l[0]), _v(l[i_c])) for l in lignes), key=lambda x: -x[1])[:8]))


def _rabais(entetes, lignes, avant, r, constats, ctx):
    _dimension(entetes, lignes, avant, r, constats, "Rabais", "Montant", "Rabais", inverse=True)
    i_u, i_m = _col(entetes, "Utilisations"), _col(entetes, "Montant")
    brut = ctx.get("ventes_brutes") or ZERO
    total = sum((abs(_v(l[i_m])) for l in lignes), ZERO)
    r.cartes.append(("Utilisations", "n", sum(int(_v(l[i_u])) for l in lignes)))
    if brut:
        r.cartes.append(("Part des ventes brutes", "%", _pc(total, brut)))
        constats.append(_k("attention" if _pc(total, brut) >= 5 else "info",
                           "Les rabais représentent {p} % des ventes brutes.", p=_nb(_pc(total, brut))))
    r.graphiques[1] = _graphe("classement", "Rabais les plus utilisés", "",
                              elements=sorted(((str(l[0]), _v(l[i_u])) for l in lignes), key=lambda x: -x[1])[:8])
    r.graphiques.append(_graphe("classement", "Montant moyen d'un rabais", "$",
                                elements=sorted(((str(l[0]), _d(abs(_v(l[i_m])) / int(_v(l[i_u]))))
                                                 for l in lignes if int(_v(l[i_u]))), key=lambda x: -x[1])[:8]))


# --------------------------------------------------------------------------------------------- listes
def _commandes(entetes, lignes, avant, r, constats):
    i_n, i_a, i_m, i_e = (_col(entetes, n) for n in ("Ventes nettes", "Articles", "Mode(s) de paiement", "Employé"))
    montants = sorted(_v(l[i_n]) for l in lignes)
    total = sum(montants, ZERO)
    mediane = montants[len(montants) // 2] if montants else ZERO
    grosse = max(lignes, key=lambda l: _v(l[i_n]), default=None)
    n0 = len(avant[1]) if avant and avant[1] else 0
    r.cartes = [("Commandes", "n", len(lignes)), ("Panier moyen", "$", _d(total / len(lignes)) if lignes else 0),
                ("Panier médian", "$", _d(mediane)),
                ("Articles par commande", "n", _d(Decimal(sum(int(_v(l[i_a])) for l in lignes)) / len(lignes), "0.1")
                 if lignes else 0),
                ("Plus grosse commande", "$", _d(_v(grosse[i_n])) if grosse else 0)]
    if n0:
        r.cartes.append(("Variation", "%", _variation(Decimal(len(lignes)), Decimal(n0))))
        _comparer(constats, "Commandes", Decimal(len(lignes)), Decimal(n0), argent=False)
    if lignes:
        constats.append(_k("info", "La moitié des commandes font moins de {m} ; le panier moyen ({p}) est tiré vers le "
                                   "haut par les grosses commandes.", m=_argent(mediane), p=_argent(total / len(lignes)))
                        if total / len(lignes) > mediane * Decimal("1.2") else
                        _k("info", "Panier médian {m}, proche du panier moyen.", m=_argent(mediane)))
    tranches = [("1", 1, 1), ("2", 2, 2), ("3-4", 3, 4), ("5-9", 5, 9), ("10+", 10, 10 ** 6)]
    par_t = [Decimal(sum(1 for l in lignes if a <= int(_v(l[i_a])) <= b)) for _n, a, b in tranches]
    modes = defaultdict(int)
    for l in lignes:
        modes[str(l[i_m]) or "—"] += 1
    r.graphiques = [_graphe("barres", "Commandes selon le nombre d'articles", "", [n for n, _a, _b in tranches],
                            [("Commandes", par_t)]),
                    _graphe("anneau", "Commandes par mode de paiement", "",
                            elements=sorted(((k, Decimal(v)) for k, v in modes.items()), key=lambda kv: -kv[1])[:6])]
    if i_e is not None:
        par_e = defaultdict(int)
        for l in lignes:
            par_e[str(l[i_e]) or "—"] += 1
        r.graphiques.append(_graphe("classement", "Commandes par employé", "",
                                    elements=sorted(((k, Decimal(v)) for k, v in par_e.items()), key=lambda kv: -kv[1])[:8]))


def _liste_paiements(entetes, lignes, avant, r, constats):
    i_m, i_mode, i_e, i_r = (_col(entetes, n) for n in ("Montant", "Mode de paiement", "Employé", "Remise en argent"))
    total = sum((_v(l[i_m]) for l in lignes), ZERO)
    par_mode = defaultdict(Decimal)
    for l in lignes:
        par_mode[str(l[i_mode]) or "—"] += _v(l[i_m])
    remise = sum((_v(l[i_r]) for l in lignes), ZERO) if i_r is not None else ZERO
    principal = max(par_mode.items(), key=lambda kv: kv[1], default=None)
    r.cartes = [("Paiements", "n", len(lignes)), ("Montant", "$", _d(total)),
                ("Paiement moyen", "$", _d(total / len(lignes)) if lignes else 0),
                ("Mode principal", "t", principal[0] if principal else "—"), ("Remises en argent", "$", _d(remise))]
    if principal and total:
        constats.append(_k("info", "« {m} » représente {p} % des montants payés.", m=principal[0],
                           p=_nb(_pc(principal[1], total))))
    if remise:
        constats.append(_k("info", "{v} remis en argent aux clients (retrait à la caisse).", v=_argent(remise)))
    par_e = defaultdict(Decimal)
    for l in lignes:
        par_e[str(l[i_e]) or "—"] += _v(l[i_m])
    r.graphiques = [_graphe("anneau", "Montant par mode de paiement", "$",
                            elements=sorted(par_mode.items(), key=lambda kv: -kv[1])),
                    _graphe("classement", "Montant encaissé par employé", "$",
                            elements=sorted(par_e.items(), key=lambda kv: -kv[1])[:8])]


def _remboursements(entetes, lignes, avant, r, constats, ctx):
    i_m, i_e = _col(entetes, "Montant"), _col(entetes, "Employé")
    total = sum((abs(_v(l[i_m])) for l in lignes), ZERO)
    nettes = ctx.get("ventes_nettes") or ZERO
    n0 = len(avant[1]) if avant and avant[1] else 0
    r.cartes = [("Nombre de remboursements", "n", len(lignes)), ("Montant remboursé", "$", _d(total)),
                ("Remboursement moyen", "$", _d(total / len(lignes)) if lignes else 0),
                ("Part des ventes", "%", _pc(total, nettes) if nettes else 0)]
    if not lignes:
        constats.append(_k("bon", "Aucun remboursement dans la période."))
    else:
        constats.append(_k("attention" if nettes and _pc(total, nettes) >= 2 else "info",
                           "{n} remboursement(s) pour {v} ({p} % des ventes) ; la période d'avant : {m}.",
                           n=len(lignes), v=_argent(total), p=_nb(_pc(total, nettes) if nettes else ZERO), m=n0))
    par_e, par_j = defaultdict(Decimal), defaultdict(Decimal)
    for l in lignes:
        par_e[str(l[i_e]) or "—"] += abs(_v(l[i_m]))
        par_j[str(l[0])[:10]] += abs(_v(l[i_m]))
    r.graphiques = [_graphe("classement", "Montant remboursé par employé", "$",
                            elements=sorted(par_e.items(), key=lambda kv: -kv[1])[:8]),
                    _graphe("barres", "Montant remboursé par jour", "$", [j[8:10] + "/" + j[5:7] for j in sorted(par_j)],
                            [("Montant remboursé", [par_j[j] for j in sorted(par_j)])])]


# --------------------------------------------------------------------------------------------- entrée
def enrichir(nom: str, vues: dict, vues_avant: dict | None = None, ctx: dict | None = None) -> RapportGestion | None:
    """Cartes, constats et graphiques de plus de l'état `nom` ; None si l'état n'est pas enrichi ou vide."""
    if nom not in ETATS or nom not in vues:
        return None
    ctx = dict(ctx or {})
    entetes, lignes = vues[nom]
    avant = (vues_avant or {}).get(nom)
    resume = dict(vues.get("Résumé", ([], []))[1]) if "Résumé" in vues else {}
    ctx.setdefault("ventes_brutes", _v(resume.get("Ventes brutes (articles)") or resume.get("Ventes brutes")))
    ctx.setdefault("ventes_nettes", _v(resume.get("Ventes nettes (articles)") or resume.get("Ventes nettes")))
    r = RapportGestion()
    constats: list[str] = []
    try:
        if nom in ("Par jour", "Rapport des ventes"):
            _jours(entetes, lignes, avant, r, constats)
        elif nom in ("Par jour de la semaine", "Par heure"):
            _periodique(entetes, lignes, avant, r, constats, nom)
        elif nom == "Jour × heure":
            _chaleur(entetes, lignes, avant, r, constats)
        elif nom == "Par employé":
            _employes(entetes, lignes, avant, r, constats)
        elif nom == "Par article":
            _articles(entetes, lignes, avant, r, constats)
        elif nom == "Par catégorie":
            _categories(entetes, lignes, avant, r, constats)
        elif nom == "Bénéfices":
            _benefices(entetes, lignes, avant, r, constats)
        elif nom == "Par mode de paiement":
            _paiements_par(entetes, lignes, avant, r, constats, nom, "Modes de paiement")
        elif nom == "Par type de carte":
            _paiements_par(entetes, lignes, avant, r, constats, nom, "Types de carte")
        elif nom == "Par mode de saisie de la carte":
            _paiements_par(entetes, lignes, avant, r, constats, nom, "Modes de saisie")
        elif nom == "Par appareil":
            _dimension(entetes, lignes, avant, r, constats, "Appareil", "Ventes nettes", "Appareils")
            if len(lignes) == 1:
                constats.append(_k("info", "Un seul appareil a servi à encaisser pendant la période."))
        elif nom == "Par client":
            _clients(entetes, lignes, avant, r, constats, ctx)
        elif nom == "Rabais":
            _rabais(entetes, lignes, avant, r, constats, ctx)
        elif nom == "Commandes":
            _commandes(entetes, lignes, avant, r, constats)
        elif nom == "Paiements":
            _liste_paiements(entetes, lignes, avant, r, constats)
        elif nom == "Remboursements":
            _remboursements(entetes, lignes, avant, r, constats, ctx)
    except (ArithmeticError, IndexError, TypeError, ValueError):  # un état mal formé ne doit jamais bloquer la page
        return None
    if not lignes and nom != "Remboursements":
        return None
    r.note = _note(constats)
    r.graphiques = [g for g in r.graphiques if g["elements"] or any(v for _n, vs in g["series"] for v in vs)][:4]
    return r
