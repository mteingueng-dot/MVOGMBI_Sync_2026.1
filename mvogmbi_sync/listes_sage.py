"""Listes lues dans Sage, comme les menus de gestion de Sage (demande du propriétaire du 2026-10-29) — lecture seule.

Clients et fournisseurs (solde dû, factures ouvertes, dernière facture, chiffre des 12 derniers mois), documents de
vente et d'achat (factures, notes de crédit, encaissements et paiements), documents de stock (ajustements journal
12, transferts journal 14), liste des articles Sage (stock, CUMP, valeur, catégorie, lien Clover) et livre
d'inventaire (quantité et valeur par article et par catégorie à une date : stock actuel moins les mouvements
postérieurs ; valeur au CUMP actuel).
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from .articles_sage import reparer_texte

CENT = Decimal("0.01")


def _d(v) -> Decimal:
    return Decimal(str(v or 0)).quantize(CENT)


def _q(v) -> Decimal:
    return Decimal(str(v or 0)).quantize(Decimal("0.001")).normalize()


def _jour(v) -> str:
    return (v.date() if hasattr(v, "date") else v).isoformat() if v else ""


# --------------------------------------------------------------------------------------------- tiers
def tiers(base, cote: str, aujourdhui: date | None = None) -> tuple[list[str], list[list]]:
    """Clients (« clients ») ou fournisseurs (« fournisseurs ») : solde dû, factures ouvertes, dernière facture,
    montant facturé des 12 derniers mois ; actifs et inactifs."""
    aujourdhui = aujourdhui or date.today()
    if cote == "clients":
        table, tr, dt, cle, lien = "tcustomr", "tcustr", "tcustrdt", "lCusId", "lCusTrId"
    else:
        table, tr, dt, cle, lien = "tvendor", "tventr", "tventrdt", "lVenId", "lVenTrId"
    noms = {r["lId"]: (reparer_texte(r["n"] or ""), r["i"]) for r in base.requete(
        f"SELECT lId, TRIM(sName) n, bInactive i FROM {table}")}
    soldes = base.requete(
        f"SELECT t.{cle} c, t.lId f, t.dtDate d, SUM(x.dAmount) s FROM {tr} t JOIN {dt} x ON x.{lien} = t.lId "
        f"WHERE t.nTranType = 0 AND x.bReversed = 0 GROUP BY t.{cle}, t.lId, t.dtDate")
    debut = (aujourdhui - timedelta(days=365)).isoformat()
    infos: dict[int, dict] = defaultdict(lambda: {"solde": Decimal(0), "ouvertes": 0, "derniere": "",
                                                  "annee": Decimal(0)})
    for l in soldes:
        i, s, jour = infos[l["c"]], _d(l["s"]), _jour(l["d"])
        i["derniere"] = max(i["derniere"], jour)
        if s > 0:
            i["solde"] += s
            i["ouvertes"] += 1
    for l in base.requete(
            f"SELECT t.{cle} c, SUM(x.dAmount) s FROM {tr} t JOIN {dt} x ON x.{lien} = t.lId WHERE t.nTranType = 0 "
            f"AND x.nTranType = 0 AND x.bReversed = 0 AND t.dtDate >= %s GROUP BY t.{cle}", (debut,)):
        infos[l["c"]]["annee"] = _d(l["s"])
    lignes = [[nom, "Inactif" if inactif else "Actif", infos[i]["solde"], infos[i]["ouvertes"], infos[i]["derniere"],
               infos[i]["annee"]] for i, (nom, inactif) in noms.items()]
    lignes.sort(key=lambda l: (-l[2], l[0].casefold()))
    titre = "Client" if cote == "clients" else "Fournisseur"
    return [titre, "État", "Montant dû", "Factures ouvertes", "Dernière facture", "Facturé 12 mois"], lignes


# --------------------------------------------------------------------------------------------- documents
TYPES_VENTE = {0: "Facture", 1: "Encaissement", 2: "Escompte / ajustement"}
TYPES_ACHAT = {0: "Facture", 1: "Paiement", 2: "Payée comptant", 3: "Dépôt / avance", 8: "Note de crédit"}


def documents(base, cote: str, du: date, au: date) -> tuple[list[str], list[list]]:
    """Documents de vente (factures, encaissements) ou d'achat (factures, paiements, notes de crédit) de la période,
    le plus récent en haut ; solde restant de chaque facture."""
    if cote == "ventes":
        sql = ("SELECT x.dtDate d, x.nTranType y, TRIM(t.sSource) f, TRIM(x.sSource) p, x.dAmount m, TRIM(c.sName) n, "
               "t.lId id FROM tcustrdt x JOIN tcustr t ON t.lId = x.lCusTrId JOIN tcustomr c ON c.lId = t.lCusId "
               "WHERE x.bReversed = 0 AND x.dtDate >= %s AND x.dtDate <= %s")
        soldes_sql = "SELECT lCusTrId id, SUM(dAmount) s FROM tcustrdt WHERE bReversed = 0 GROUP BY lCusTrId"
        types, tiers_ = TYPES_VENTE, "Client"
    else:
        sql = ("SELECT x.dtDate d, x.nTranType y, TRIM(t.sSource) f, TRIM(x.sSource) p, x.dAmount m, TRIM(v.sName) n, "
               "t.lId id FROM tventrdt x JOIN tventr t ON t.lId = x.lVenTrId JOIN tvendor v ON v.lId = t.lVenId "
               "WHERE x.bReversed = 0 AND x.dtDate >= %s AND x.dtDate <= %s")
        soldes_sql = "SELECT lVenTrId id, SUM(dAmount) s FROM tventrdt WHERE bReversed = 0 GROUP BY lVenTrId"
        types, tiers_ = TYPES_ACHAT, "Fournisseur"
    soldes = {r["id"]: _d(r["s"]) for r in base.requete(soldes_sql)}
    lignes = []
    for l in base.requete(sql, (du.isoformat(), au.isoformat())):
        facture = l["y"] == 0
        solde = soldes.get(l["id"], Decimal(0)) if facture else None
        lignes.append([_jour(l["d"]), types.get(l["y"], f"Type {l['y']}"), l["f"] or "",
                       "" if (l["p"] or "") == (l["f"] or "") else (l["p"] or ""), reparer_texte(l["n"] or ""),
                       _d(l["m"]), solde, ("Payée" if solde is not None and solde <= 0 else
                                          "Ouverte" if solde is not None else "")])
    lignes.sort(key=lambda l: (l[0], l[2]), reverse=True)
    return ["Date", "Type", "Facture", "Pièce", tiers_, "Montant", "Reste dû", "État"], lignes


def commandes_sage(base) -> tuple[list[str], list[list]]:
    """Commandes clients de Sage (si la fonction est activée dans Sage)."""
    lignes = [[_jour(l["d"]), l["n"] or "", reparer_texte(l["c"] or ""), _jour(l["l"])] for l in base.requete(
        "SELECT o.dtSODate d, TRIM(o.sSONum) n, TRIM(o.sName) c, o.dtShipDate l FROM tsalordr o")]
    return ["Date", "Commande", "Client", "Livraison"], sorted(lignes, reverse=True)


TYPES_STOCK = {12: "Ajustement d'inventaire", 14: "Transfert entre emplacements"}


def documents_stock(base, du: date, au: date) -> tuple[list[str], list[list]]:
    """Ajustements (journal 12) et transferts (journal 14) de Sage : un document par saisie."""
    lignes = base.requete(
        "SELECT r.lId id, r.dtJournal d, r.nJournal j, TRIM(r.sSource1) s, COUNT(l.nLineNum) n, SUM(l.dQty) q, "
        "SUM(l.dAmt) m FROM titrec r JOIN titrline l ON l.lITRecId = r.lId WHERE r.nJournal IN (12, 14) "
        "AND l.bVarLine = 0 AND r.bReversed = 0 AND r.bReversal = 0 AND r.dtJournal >= %s AND r.dtJournal <= %s "
        "GROUP BY r.lId, r.dtJournal, r.nJournal, r.sSource1", (du.isoformat(), au.isoformat()))
    resultat = [[_jour(l["d"]), TYPES_STOCK.get(l["j"], f"Journal {l['j']}"), l["s"] or "", int(l["n"] or 0),
                 _q(l["q"]) if l["j"] == 12 else None, _d(l["m"]) if l["j"] == 12 else None] for l in lignes]
    resultat.sort(key=lambda l: (l[0], l[2]), reverse=True)
    return ["Date", "Type", "Source", "Lignes", "Quantité (+ entrée / − sortie)", "Montant"], resultat


# --------------------------------------------------------------------------------------------- articles
def articles(base, categories: dict[str, str] | None = None, liens: dict[str, list[str]] | None = None
             ) -> tuple[list[str], list[list]]:
    """Articles Sage : type, actif, catégorie, stock, CUMP, valeur, comptes, articles Clover reliés."""
    from .rapports import nom_categorie

    categories, liens = categories or {}, liens or {}
    comptes = {r["lId"]: r["sName"] or "" for r in base.requete("SELECT lId, sName FROM taccount")}
    lignes = []
    for l in base.requete(
            "SELECT TRIM(i.sPartCode) n, TRIM(i.sName) nom, i.bService s, i.bInactive a, i.lAcNAsset ac, "
            "i.lAcNRev r, i.lAcNExp x, COALESCE(SUM(y.dInStock), 0) q, COALESCE(SUM(y.dCostStk), 0) v FROM tinvent i "
            "LEFT JOIN tinvbyln y ON y.lInventId = i.lId GROUP BY i.lId, i.sPartCode, i.sName, i.bService, "
            "i.bInactive, i.lAcNAsset, i.lAcNRev, i.lAcNExp"):
        quantite, valeur = _q(l["q"]), _d(l["v"])
        compte = l["ac"] or l["r"] or l["x"]  # un service n'a souvent qu'un compte de charges
        lignes.append([l["n"], reparer_texte(l["nom"] or ""), "Service" if l["s"] else "Stock",
                       "Inactif" if l["a"] else "Actif",
                       categories.get(str(compte or "")[:4]) or nom_categorie(comptes.get(compte, "")),
                       None if l["s"] else quantite,
                       (valeur / quantite).quantize(Decimal("0.0001")) if quantite > 0 and valeur > 0 else None,
                       None if l["s"] else valeur, str(l["ac"] or "")[:4], str(l["r"] or "")[:4],
                       str(l["x"] or "")[:4], ", ".join(liens.get(l["n"], []))])
    lignes.sort(key=lambda l: l[0].casefold())
    return ["N° Sage", "Description", "Type", "État", "Catégorie", "Stock", "CUMP", "Valeur du stock",
            "Compte d'actif", "Compte de produits", "Compte de charges / CMV", "Articles Clover"], lignes


def livre_inventaire(base, au: date, categories: dict[str, str] | None = None) -> tuple[list[str], list[list], dict]:
    """Quantité à la date (stock actuel moins les entrées et plus les sorties postérieures) et valeur au CUMP actuel,
    par article puis total de chaque catégorie ; articles de stock actifs ou ayant du stock."""
    from .analyse_articles import lire_articles

    actuels = lire_articles(base, categories or {})
    apres = defaultdict(Decimal)
    for l in base.requete(
            "SELECT TRIM(i.sPartCode) n, r.nJournal j, SUM(l.dQty) q FROM titrline l JOIN titrec r ON r.lId = "
            "l.lITRecId JOIN tinvent i ON i.lId = l.lInventId WHERE r.nJournal IN (7, 8, 12, 17) AND l.bVarLine = 0 "
            "AND r.bReversed = 0 AND r.bReversal = 0 AND r.dtJournal > %s GROUP BY i.sPartCode, r.nJournal",
            (au.isoformat(),)):
        q = Decimal(str(l["q"] or 0))
        apres[l["n"]] += q if l["j"] in (7, 12) else -q   # entrées après la date : à retirer du stock actuel
    par_categorie: dict[str, list] = defaultdict(list)
    for a in actuels.values():
        quantite = (a.quantite - apres.get(a.numero, Decimal(0))).quantize(Decimal("0.001")).normalize()
        if quantite == 0:
            continue
        cump = a.cump
        valeur = (quantite * cump).quantize(CENT) if cump and quantite > 0 else Decimal(0)
        par_categorie[a.categorie].append([a.categorie, a.numero, a.nom, quantite, cump, valeur])
    lignes, total = [], Decimal(0)
    for categorie in sorted(par_categorie, key=str.casefold):
        groupe = sorted(par_categorie[categorie], key=lambda l: l[1].casefold())
        sous_total = sum((l[5] for l in groupe), Decimal(0))
        lignes += groupe + [[categorie, "", "Total de la catégorie", None, None, sous_total]]
        total += sous_total
    lignes.append(["", "", "Total général", None, None, total])
    return (["Catégorie", "N° Sage", "Article", "Quantité", "CUMP", "Valeur"], lignes,
            {"total": total, "articles": sum(len(g) for g in par_categorie.values()),
             "negatifs": sum(1 for g in par_categorie.values() for l in g if l[3] < 0)})
