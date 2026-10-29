"""Produits inactifs et articles 80/20 (demande du propriétaire du 2026-10-29), rubrique État.

Deux sources au choix (Clover par défaut, demande du propriétaire) :
- Clover : articles du catalogue (stock itemStock, coût Clover : valeur = stock × coût), ventes nettes des commandes
  payées (mêmes règles que les factures, jours terminés gardés dans donnees/cache_clover) ; la dernière vente est
  cherchée sur les 365 derniers jours (aucun achat dans Clover) ;
- Sage (lecture seule) : articles de stock actifs (tinvent, bService = 0, bInactive = 0), stock et valeur du
stock de la fiche (somme de tinvbyln.dInStock et dCostStk, tous emplacements), ventes = lignes de factures de vente
(titrline du journal 8, sans écarts de coût ni écritures corrigées), achats = journal 7.

- Produits inactifs : articles sans vente depuis N jours (30, 60, 90…) ou jamais vendus, avec la date de la dernière
  vente et du dernier achat, le stock et sa valeur (argent immobilisé).
- Articles 80/20 (Pareto) : ventes de la période par article, du plus vendu au moins vendu, part et part cumulée du
  chiffre d'affaires ; classe A = articles qui font les premiers 80 %, B = jusqu'à 95 %, C = le reste ; stock actuel,
  valeur du stock et couverture (jours de vente que le stock permet au rythme de la période).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from .articles_sage import reparer_texte

CENT = Decimal("0.01")
SEUILS_INACTIVITE = (30, 60, 90, 120, 180, 365)  # jours sans vente proposés
SEUIL_A, SEUIL_B = Decimal(80), Decimal(95)       # parts cumulées du chiffre d'affaires des classes A et B
SEUIL_CUMP_DOUTEUX = Decimal(5)                    # CUMP > 5 × prix de vente moyen : valeur du stock douteuse
JOURS_CLOVER = 365                                 # ventes Clover lues pour trouver la dernière vente
JAMAIS_SAGE, JAMAIS_CLOVER = "Jamais vendu", "Aucune vente en 365 jours"


@dataclass
class ArticleSage:
    numero: str
    nom: str
    categorie: str
    quantite: Decimal = Decimal(0)
    valeur: Decimal = Decimal(0)
    derniere_vente: date | None = None
    dernier_achat: date | None = None
    cout: Decimal | None = None  # coût unitaire connu (Clover) ; sinon CUMP = valeur / quantité (Sage)
    catalogue: bool = True       # faux : vendu sous un ID absent du catalogue Clover (supprimé ou renommé)

    @property
    def cump(self) -> Decimal | None:
        if self.cout is not None:
            return self.cout
        return (self.valeur / self.quantite).quantize(Decimal("0.0001")) if self.quantite > 0 and self.valeur > 0 \
            else None


def _jour(valeur) -> date | None:
    if valeur is None:
        return None
    return valeur.date() if isinstance(valeur, datetime) else valeur


def _qte(valeur) -> Decimal:
    return Decimal(str(valeur or 0)).quantize(Decimal("0.001")).normalize()


def lire_articles(base, categories: dict[str, str] | None = None) -> dict[str, ArticleSage]:
    """Articles de stock actifs de Sage avec stock, valeur, dernière vente et dernier achat (2 requêtes).
    `categories` : compte « 1517 » -> catégorie (table des comptes par catégorie), sinon nom du compte d'actif."""
    from .rapports import nom_categorie

    categories = categories or {}
    comptes = {r["lId"]: r["sName"] or "" for r in base.requete("SELECT lId, sName FROM taccount")}
    lignes = base.requete(
        "SELECT i.lId, TRIM(i.sPartCode) n, TRIM(i.sName) nom, i.lAcNAsset, COALESCE(SUM(y.dInStock), 0) q, "
        "COALESCE(SUM(y.dCostStk), 0) v FROM tinvent i LEFT JOIN tinvbyln y ON y.lInventId = i.lId "
        "WHERE i.bService = 0 AND i.bInactive = 0 GROUP BY i.lId, i.sPartCode, i.sName, i.lAcNAsset")
    dates = {r["a"]: r for r in base.requete(
        "SELECT l.lInventId a, MAX(CASE WHEN r.nJournal = 8 THEN r.dtJournal END) vente, "
        "MAX(CASE WHEN r.nJournal = 7 THEN r.dtJournal END) achat FROM titrline l JOIN titrec r ON r.lId = l.lITRecId "
        "WHERE r.nJournal IN (7, 8) AND l.bVarLine = 0 AND r.bReversed = 0 AND r.bReversal = 0 GROUP BY l.lInventId")}
    resultat = {}
    for l in lignes:
        compte = l["lAcNAsset"]
        d = dates.get(l["lId"], {})
        resultat[l["n"]] = ArticleSage(
            numero=l["n"], nom=reparer_texte(l["nom"] or ""),
            categorie=categories.get(str(compte or "")[:4]) or nom_categorie(comptes.get(compte, "")) or "Sans catégorie",
            quantite=_qte(l["q"]), valeur=Decimal(str(l["v"] or 0)).quantize(CENT),
            derniere_vente=_jour(d.get("vente")), dernier_achat=_jour(d.get("achat")))
    return resultat


def lire_ventes(base, du: date, au: date) -> dict[str, tuple[Decimal, Decimal]]:
    """N° Sage -> (quantité vendue, ventes) des factures de vente de la période."""
    lignes = base.requete(
        "SELECT TRIM(i.sPartCode) n, SUM(l.dQty) q, SUM(l.dAmt) m FROM titrline l "
        "JOIN titrec r ON r.lId = l.lITRecId JOIN tinvent i ON i.lId = l.lInventId "
        "WHERE r.nJournal = 8 AND l.bVarLine = 0 AND r.bReversed = 0 AND r.bReversal = 0 "
        "AND r.dtJournal >= %s AND r.dtJournal < DATE_ADD(%s, INTERVAL 1 DAY) GROUP BY i.sPartCode",
        (du.isoformat(), au.isoformat()))
    return {l["n"]: (_qte(l["q"]), Decimal(str(l["m"] or 0)).quantize(CENT)) for l in lignes}


def articles_clover(items: list[dict], ventes: dict) -> dict[str, ArticleSage]:
    """Catalogue Clover (expand=categories,itemStock) -> articles par ID Clover ; `ventes` : ID -> VenteArticle
    (previsions.ventes_par_article) pour la date de la dernière vente. Valeur du stock = stock (> 0) × coût Clover.
    Un article vendu mais absent du catalogue (supprimé ou renommé) est ajouté avec un stock de 0."""
    resultat = {}
    for a in items:
        if a.get("deleted"):
            continue
        stock = (a.get("itemStock") or {}).get("quantity")
        quantite = _qte(stock) if stock is not None else Decimal(0)
        cout = Decimal(int(a["cost"])) / 100 if a.get("cost") else None
        categories = [c.get("name", "") for c in (a.get("categories") or {}).get("elements") or []]
        v = ventes.get(a["id"])
        resultat[a["id"]] = ArticleSage(
            numero=a["id"], nom=(a.get("name") or "").strip(), categorie=", ".join(c for c in categories if c)
            or "Sans catégorie", quantite=quantite,
            valeur=(quantite * cout).quantize(CENT) if cout and quantite > 0 else Decimal(0),
            derniere_vente=v.derniere if v else None, cout=cout)
    for cle, v in ventes.items():
        if cle not in resultat:
            resultat[cle] = ArticleSage(numero=cle, nom=v.nom, categorie=v.categorie or "Sans catégorie",
                                        derniere_vente=v.derniere, catalogue=False)
    return resultat


def ventes_clover(ventes: dict) -> dict[str, tuple[Decimal, Decimal]]:
    """ID -> VenteArticle -> ID -> (quantité nette, ventes nettes), comme lire_ventes."""
    return {cle: (v.quantite.quantize(Decimal("0.001")).normalize(), v.nettes.quantize(CENT))
            for cle, v in ventes.items()}


# --------------------------------------------------------------------------------------------- produits inactifs
def tranche(jours: int | None, jamais: str = JAMAIS_SAGE) -> str:
    """Tranche d'inactivité : « 30 à 59 jours », …, « 365 jours et plus », « Jamais vendu »."""
    if jours is None:
        return jamais
    bornes = SEUILS_INACTIVITE
    for bas, haut in zip(bornes, bornes[1:]):
        if bas <= jours < haut:
            return f"{bas} à {haut - 1} jours"
    return f"{bornes[-1]} jours et plus" if jours >= bornes[-1] else f"Moins de {bornes[0]} jours"


ENTETES_INACTIFS = ["N° Sage", "Article", "Catégorie", "Dernière vente", "Jours sans vente", "Tranche",
                    "Dernier achat", "Stock", "CUMP", "Valeur du stock"]


def produits_inactifs(articles: dict[str, ArticleSage], jours: int, aujourdhui: date, avec_stock: bool = False,
                      categorie: str = "", jamais: str = JAMAIS_SAGE) -> tuple[list[list], dict]:
    """Articles sans vente depuis au moins `jours` jours, ou jamais vendus ; la plus grande valeur de stock en haut
    (argent immobilisé), puis le plus long temps sans vente. `avec_stock` : seulement les articles en stock."""
    retenus = []
    for a in articles.values():
        if not a.catalogue:  # ancien article supprimé ou renommé dans Clover : plus à vendre
            continue
        if categorie and a.categorie.casefold() != categorie.casefold():
            continue
        if avec_stock and a.quantite <= 0:
            continue
        sans_vente = None if a.derniere_vente is None else max(0, (aujourdhui - a.derniere_vente).days)
        if sans_vente is not None and sans_vente < jours:
            continue
        retenus.append((a, sans_vente))
    retenus.sort(key=lambda x: (-max(x[0].valeur, Decimal(0)), -(x[1] if x[1] is not None else 10 ** 6), x[0].numero))
    lignes = [[a.numero, a.nom, a.categorie, a.derniere_vente.isoformat() if a.derniere_vente else jamais,
               "" if j is None else j, tranche(j, jamais), a.dernier_achat.isoformat() if a.dernier_achat else "",
               a.quantite, a.cump, a.valeur] for a, j in retenus]
    resume = {"articles": len(retenus), "jamais": sum(1 for _a, j in retenus if j is None),
              "en_stock": sum(1 for a, _j in retenus if a.quantite > 0),
              "valeur": sum((a.valeur for a, _j in retenus if a.valeur > 0), Decimal(0)),
              "tranches": {}}
    for _a, j in retenus:
        resume["tranches"][tranche(j, jamais)] = resume["tranches"].get(tranche(j, jamais), 0) + 1
    return lignes, resume


# --------------------------------------------------------------------------------------------- articles 80/20
ENTETES_PARETO = ["Rang", "Classe", "N° Sage", "Article", "Catégorie", "Quantité vendue", "Ventes", "Part (%)",
                  "Cumul (%)", "Prix moyen", "Stock", "CUMP", "Valeur du stock", "Couverture (jours)", "Contrôle"]


def pareto(articles: dict[str, ArticleSage], ventes: dict[str, tuple[Decimal, Decimal]], jours_periode: int,
           categorie: str = "") -> tuple[list[list], dict]:
    """Classement 80/20 des articles vendus sur la période (ventes > 0) : rang, classe A/B/C, part et part cumulée
    du chiffre d'affaires, stock actuel et sa valeur, couverture en jours. Valeur de stock douteuse (CUMP > 5 × prix
    de vente moyen) : signalée et hors des totaux."""
    vendus = []
    for numero, (quantite, montant) in ventes.items():
        a = articles.get(numero) or ArticleSage(numero, numero, "Sans catégorie")
        if montant <= 0 or (categorie and a.categorie.casefold() != categorie.casefold()):
            continue
        vendus.append((a, quantite, montant))
    vendus.sort(key=lambda x: (-x[2], x[0].numero))
    total = sum((m for _a, _q, m in vendus), Decimal(0))
    lignes, cumul, resume = [], Decimal(0), {"articles": len(vendus), "ventes": total, "A": 0, "ventes_A": Decimal(0),
                                              "valeur_A": Decimal(0), "valeur": Decimal(0), "douteux": 0}
    for rang, (a, quantite, montant) in enumerate(vendus, 1):
        avant = cumul
        cumul += montant
        part = (montant / total * 100) if total else Decimal(0)
        # un article est en A tant que les ventes cumulées AVANT lui n'ont pas atteint 80 % (le 1er est toujours A)
        classe = "A" if avant / total * 100 < SEUIL_A else ("B" if avant / total * 100 < SEUIL_B else "C")
        prix = (montant / quantite).quantize(CENT) if quantite > 0 else None
        douteux = bool(a.cump and prix and a.cump > SEUIL_CUMP_DOUTEUX * prix)
        par_jour = quantite / jours_periode if jours_periode > 0 else Decimal(0)
        couverture = int(a.quantite / par_jour) if a.quantite > 0 and par_jour > 0 else 0
        controle = "Valeur du stock douteuse (coût > 5 × prix)" if douteux else (
            "Supprimé ou renommé dans Clover" if not a.catalogue else ("Rupture" if a.quantite <= 0 else ""))
        lignes.append([rang, classe, a.numero, a.nom, a.categorie, quantite, montant, part.quantize(Decimal("0.1")),
                       (cumul / total * 100).quantize(Decimal("0.1")), prix, a.quantite, a.cump, a.valeur, couverture,
                       controle])
        if douteux:
            resume["douteux"] += 1
            continue
        if a.valeur > 0:
            resume["valeur"] += a.valeur
        if classe == "A":
            resume["valeur_A"] += max(a.valeur, Decimal(0))
    a_seuls = [l for l in lignes if l[1] == "A"]
    resume["A"] = len(a_seuls)
    resume["ventes_A"] = sum((l[6] for l in a_seuls), Decimal(0))
    return lignes, resume


def categories(racine: Path) -> dict[str, str]:
    from .rapports import categories_par_compte

    try:
        return categories_par_compte(racine)
    except Exception:
        return {}
