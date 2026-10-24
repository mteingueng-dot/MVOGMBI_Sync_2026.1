"""Récupération des ventes par l'API REST Clover (v3) et cumul par article.

Règles de calcul, alignées sur le rapport « Ventes d'articles » de Clover :
- ventes brutes = prix unitaire x quantité (+ modificateurs) ;
- rabais = rabais de ligne + part des rabais de commande, répartie au prorata ;
- remboursements = montant des lignes marquées remboursées.
Ces règles sont à valider en comparant avec un export Clover de la même journée.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

import requests

from .models import LigneVente, RapportVentes, cumuler
from .periodes import en_millisecondes

CENT = Decimal("100")
SANS_CATEGORIE = "Non catégorisé(e)"
ETATS_PAYES = {"PAID", "PARTIALLY_REFUNDED", "REFUNDED"}


@dataclass
class ConfigClover:
    merchant_id: str
    api_token: str
    base_url: str = "https://api.clover.com"
    fuseau_horaire: str = "America/Toronto"


class ClientClover:
    def __init__(self, config: ConfigClover, session: requests.Session | None = None):
        if not config.merchant_id or not config.api_token:
            raise ValueError("merchant_id et api_token doivent être renseignés dans config.toml")
        self.config = config
        self.session = session or requests.Session()
        self.session.headers["Authorization"] = f"Bearer {config.api_token}"

    def _url(self, chemin: str) -> str:
        return f"{self.config.base_url}/v3/merchants/{self.config.merchant_id}/{chemin}"

    def _pages(self, chemin: str, params: dict) -> Iterator[dict]:
        limite, decalage = 1000, 0
        while True:
            reponse = self.session.get(
                self._url(chemin), params={**params, "limit": limite, "offset": decalage}, timeout=60
            )
            reponse.raise_for_status()
            elements = reponse.json().get("elements", [])
            yield from elements
            if len(elements) < limite:
                return
            decalage += limite

    def marchand(self) -> dict:
        """Informations du marchand : sert à vérifier que l'identifiant et le jeton sont valides."""
        reponse = self.session.get(f"{self.config.base_url}/v3/merchants/{self.config.merchant_id}", timeout=30)
        reponse.raise_for_status()
        return reponse.json()

    def categories_par_article(self) -> dict[str, str]:
        """id d'article Clover -> nom de sa première catégorie."""
        resultat: dict[str, str] = {}
        for article in self._pages("items", {"expand": "categories"}):
            cats = (article.get("categories") or {}).get("elements") or []
            if cats:
                resultat[article["id"]] = cats[0].get("name", SANS_CATEGORIE)
        return resultat

    def commandes(self, debut: date, fin: date) -> Iterator[dict]:
        t0, t1 = en_millisecondes(debut, fin, self.config.fuseau_horaire)
        params = {
            "filter": [f"createdTime>={t0}", f"createdTime<{t1}"],
            "expand": "lineItems,lineItems.discounts,lineItems.modifications,discounts,payments",
        }
        yield from self._pages("orders", params)

    def rapport(self, debut: date, fin: date) -> RapportVentes:
        categories = self.categories_par_article()
        lignes = [l for c in self.commandes(debut, fin) for l in lignes_commande(c, categories)]
        return RapportVentes(debut=debut, fin=fin, source="API Clover", lignes=cumuler(lignes))


def _cents(valeur) -> Decimal:
    return Decimal(int(valeur or 0)) / CENT


def _arrondi(valeur: Decimal) -> Decimal:
    return valeur.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _rabais(remises: list[dict], base: Decimal) -> Decimal:
    """Total (négatif) d'une liste de rabais Clover, en montant ou en pourcentage de `base`."""
    total = Decimal("0")
    for r in remises:
        if r.get("amount") is not None:
            total += _cents(r["amount"])  # déjà négatif dans Clover
        elif r.get("percentage") is not None:
            total -= base * Decimal(str(r["percentage"])) / CENT
    return total


def est_payee(commande: dict) -> bool:
    """Commande encaissée : au moins un paiement réussi (Clover laisse souvent paymentState à OPEN)."""
    paiements = (commande.get("payments") or {}).get("elements") or []
    if any(p.get("result") == "SUCCESS" for p in paiements):
        return True
    return commande.get("paymentState") in ETATS_PAYES


def lignes_commande(commande: dict, categories: dict[str, str]) -> list[LigneVente]:
    """Transforme une commande Clover en lignes de vente (une par article de la commande)."""
    if not est_payee(commande):
        return []

    articles = (commande.get("lineItems") or {}).get("elements") or []
    lignes: list[tuple[LigneVente, Decimal]] = []
    for a in articles:
        if a.get("isRevenue") is False or a.get("exchanged"):
            continue
        quantite = Decimal(a["unitQty"]) / 1000 if a.get("unitQty") else Decimal("1")
        modifs = (a.get("modifications") or {}).get("elements") or []
        brut = _cents(a.get("price")) * quantite + sum((_cents(m.get("amount")) for m in modifs), Decimal("0"))
        rabais = _rabais((a.get("discounts") or {}).get("elements") or [], brut)
        item_id = (a.get("item") or {}).get("id")
        ligne = LigneVente(
            categorie=categories.get(item_id, SANS_CATEGORIE),
            nom=(a.get("name") or "Article personnalisé").strip(),
            quantite_vendue=quantite,
            ventes_brutes=_arrondi(brut),
            rabais=_arrondi(rabais),
        )
        if a.get("refunded"):
            ligne.quantite_remboursee = quantite
            ligne.remboursements = -_arrondi(brut + rabais)
        lignes.append((ligne, brut + rabais))

    # Rabais de commande répartis au prorata du montant de chaque ligne.
    base_commande = sum((m for _, m in lignes), Decimal("0"))
    rabais_commande = _rabais((commande.get("discounts") or {}).get("elements") or [], base_commande)
    if rabais_commande and base_commande:
        reparti = Decimal("0")
        for i, (ligne, m) in enumerate(lignes):
            part = (
                rabais_commande - reparti
                if i == len(lignes) - 1
                else _arrondi(rabais_commande * m / base_commande)
            )
            reparti += part
            ligne.rabais += part
    return [l for l, _ in lignes]
