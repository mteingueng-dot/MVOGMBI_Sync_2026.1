"""Prévisions (page Rapports, menu « Prévisions » des statistiques Clover) — demande du propriétaire du 2026-10-27.

- Prévision des ventes : pour chaque jour à venir, moyenne des ventes nettes du même jour de la semaine sur les
  4 dernières semaines, corrigée de la tendance (4 dernières semaines / 4 semaines d'avant, bornée de 0,8 à 1,2).
- Articles à commander (formule du propriétaire) : stock restant − quantité vendue pendant les N derniers jours
  (14 par défaut, choisi dans la liste « Horizon ») ; si le résultat est inférieur ou égal à 0, l'article est à
  commander. Seuls les articles vendus pendant ces N jours et dont Clover suit le stock sont examinés (sinon tout
  article à stock nul serait « à commander »). Quantité suggérée = de quoi couvrir de nouveau N jours de ventes ; un stock négatif dans Clover (réceptions de
  marchandise non saisies dans Clover) compte pour 0 dans la quantité suggérée, sans changer la formule.
- Prévision des achats : pour l'horizon choisi, besoin = rythme de vente des 28 derniers jours × nombre de jours ;
  à acheter = besoin − stock (si positif) ; coût = coût de l'article dans Clover s'il est renseigné.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from .statistiques_clover import JOURS, DonneesClover, preparer

ZERO = Decimal(0)
SEMAINES = 4
A_COMMANDER, SUFFISANT = "À commander", "Stock suffisant"


def ventes_par_jour(d: DonneesClover) -> dict[date, Decimal]:
    jours: dict[date, Decimal] = defaultdict(Decimal)
    for c in preparer(d):
        jours[c.moment.date()] += c.nettes
    return jours


def tendance(historique: dict[date, Decimal], aujourdhui: date) -> Decimal:
    recent = sum((historique.get(aujourdhui - timedelta(days=i), ZERO) for i in range(1, 29)), ZERO)
    avant = sum((historique.get(aujourdhui - timedelta(days=i), ZERO) for i in range(29, 57)), ZERO)
    if not avant or not recent:
        return Decimal(1)
    return min(Decimal("1.2"), max(Decimal("0.8"), recent / avant)).quantize(Decimal("0.001"))


def prevoir_ventes(historique: dict[date, Decimal], aujourdhui: date, horizon: int) -> list[list]:
    """[date, jour, prévision, même jour la semaine dernière, moyenne des 4 mêmes jours] pour chaque jour à venir
    (à partir d'aujourd'hui inclus)."""
    facteur = tendance(historique, aujourdhui)
    lignes = []
    for i in range(horizon):
        jour = aujourdhui + timedelta(days=i)
        passes = [historique.get(jour - timedelta(days=7 * k), ZERO) for k in range(1, SEMAINES + 1)
                  if jour - timedelta(days=7 * k) < aujourdhui]
        moyenne = (sum(passes, ZERO) / len(passes)).quantize(Decimal("0.01")) if passes else ZERO
        lignes.append([jour.isoformat(), JOURS[jour.weekday()], (moyenne * facteur).quantize(Decimal("0.01")),
                       historique.get(jour - timedelta(days=7), ZERO).quantize(Decimal("0.01"))
                       if jour - timedelta(days=7) < aujourdhui else None, moyenne])
    return lignes


@dataclass
class VenteArticle:
    nom: str
    categorie: str = ""
    quantite: Decimal = ZERO
    nettes: Decimal = ZERO
    derniere: date | None = None
    jours: set = field(default_factory=set)


def ventes_par_article(d: DonneesClover, depuis: date, jusqua: date) -> dict[str, VenteArticle]:
    """Quantités et ventes nettes par article Clover (identifiant) entre deux dates incluses."""
    resultat: dict[str, VenteArticle] = {}
    for c in preparer(d):
        jour = c.moment.date()
        if not depuis <= jour <= jusqua:
            continue
        for l in c.lignes:
            cle = l.id_article or l.nom
            v = resultat.setdefault(cle, VenteArticle(l.nom, l.categorie))
            v.quantite += l.quantite_nette
            v.nettes += l.ventes_nettes
            v.derniere = max(v.derniere or jour, jour)
            v.jours.add(jour)
    return resultat


def _stock(article: dict) -> Decimal | None:
    quantite = (article.get("itemStock") or {}).get("quantity")
    return None if quantite is None else Decimal(str(quantite)).quantize(Decimal("0.001")).normalize()


def _cout(article: dict) -> Decimal | None:
    cout = article.get("cost")
    return Decimal(int(cout)) / 100 if cout else None


def articles_a_commander(ventes_14j: dict[str, VenteArticle], articles: list[dict]) -> list[list]:
    """Formule du propriétaire : stock − vendu 14 jours <= 0 -> à commander (articles vendus, stock suivi)."""
    par_id = {a["id"]: a for a in articles if not a.get("deleted")}
    lignes = []
    for cle, v in ventes_14j.items():
        article = par_id.get(cle)
        stock = _stock(article) if article else None
        if stock is None or v.quantite <= 0:
            continue
        resultat = stock - v.quantite
        suggere = max(ZERO, v.quantite - max(stock, ZERO)).quantize(Decimal("0.001")).normalize()
        cout = _cout(article)
        lignes.append([v.nom, v.categorie, v.quantite.normalize(), stock, resultat.normalize(),
                       A_COMMANDER if resultat <= 0 else SUFFISANT, suggere,
                       (suggere * cout).quantize(Decimal("0.01")) if cout and suggere else None,
                       v.derniere.isoformat() if v.derniere else ""])
    return sorted(lignes, key=lambda l: (l[5] != A_COMMANDER, l[4]))


def prevoir_achats(ventes_28j: dict[str, VenteArticle], articles: list[dict], horizon: int) -> list[list]:
    """Besoin sur l'horizon (rythme des 28 derniers jours), à acheter = besoin − stock, coût estimé."""
    par_id = {a["id"]: a for a in articles if not a.get("deleted")}
    lignes = []
    for cle, v in ventes_28j.items():
        if v.quantite <= 0:
            continue
        article = par_id.get(cle)
        stock = _stock(article) if article else None
        besoin = (v.quantite * horizon / 28).quantize(Decimal("0.001"))
        acheter = max(ZERO, besoin - max(stock or ZERO, ZERO)).quantize(Decimal("0.001"))  # stock négatif = 0
        if not acheter:
            continue
        cout = _cout(article) if article else None
        lignes.append([v.nom, v.categorie, v.quantite.normalize(), besoin.normalize(),
                       "" if stock is None else stock, acheter.normalize(), cout,
                       (acheter * cout).quantize(Decimal("0.01")) if cout else None])
    return sorted(lignes, key=lambda l: -(l[7] or ZERO))
