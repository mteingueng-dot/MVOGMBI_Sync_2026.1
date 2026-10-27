"""Récupération des ventes par l'API REST Clover (v3) et cumul par article.

Règles de calcul, alignées sur le rapport « Ventes d'articles » de Clover :
- ventes brutes = prix unitaire x quantité (+ modificateurs) ;
- rabais = rabais de ligne + part des rabais de commande, répartie au prorata ;
- remboursements = montant des lignes marquées remboursées.
Ces règles sont à valider en comparant avec un export Clover de la même journée.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date, timedelta
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
            reponse = self._get(chemin, {**params, "limit": limite, "offset": decalage})
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
        """id d'article Clover -> nom de sa première catégorie (lu une fois par exécution)."""
        if getattr(self, "_categories", None) is not None:
            return self._categories
        resultat: dict[str, str] = {}
        for article in self._pages("items", {"expand": "categories"}):
            cats = (article.get("categories") or {}).get("elements") or []
            if cats:
                resultat[article["id"]] = cats[0].get("name", SANS_CATEGORIE)
        self._categories = resultat
        return resultat

    def article(self, id_article: str) -> dict | None:
        """Un article Clover par son identifiant, même s'il a été supprimé du catalogue depuis."""
        reponse = self.session.get(self._url(f"items/{id_article}"), params={"expand": "categories"}, timeout=30)
        return reponse.json() if reponse.ok else None

    def articles(self) -> list[dict]:
        """Catalogue Clover (articles actifs comptés comme recettes), avec leurs catégories."""
        return [
            a for a in self._pages("items", {"expand": "categories"})
            if not a.get("deleted") and a.get("isRevenue") is not False
        ]

    EXPANSION_COMMANDE = "lineItems,lineItems.discounts,lineItems.modifications,lineItems.taxRates,discounts,payments"

    def _get(self, chemin: str, params: dict | None = None, session: requests.Session | None = None) -> requests.Response:
        """GET avec quelques nouvelles tentatives si Clover limite le débit (429) ou a une erreur passagère."""
        for tentative in range(8):
            reponse = (session or self.session).get(self._url(chemin), params=params, timeout=60)
            if reponse.status_code not in (429, 500, 502, 503, 504):
                return reponse
            time.sleep(min(2 ** tentative, 60))
        return reponse

    def commandes(self, debut: date, fin: date, expansion: str | None = None,
                  paiements: list[dict] | None = None) -> Iterator[dict]:
        """Commandes payées pendant la période.

        Comme le rapport Clover, une vente est datée de son paiement, pas de la création de la commande
        (une commande ouverte le 17 et payée le 19 compte pour le 19). On part donc des paiements de la
        période — le filtre par date des paiements fonctionne aussi au-delà de 90 jours, contrairement à
        celui des commandes — puis on charge les commandes et on garde celles dont le premier paiement
        réussi tombe dans la période.

        Rapidité (mesurée : une journée en 1 à 4 s au lieu de 21 s, mêmes montants, à toutes les dates) : les
        commandes sont lues par paquets de 1000, liste filtrée par `clientCreatedTime` (ce filtre fonctionne aussi
        au-delà de 90 jours, contrairement à `createdTime`), 7 jours de marge pour les commandes ouvertes avant ;
        celles qui manqueraient sont lues une par une, 6 à la fois. `paiements` : déjà lus.
        """
        expansion = expansion or self.EXPANSION_COMMANDE
        t0, t1 = en_millisecondes(debut, fin, self.config.fuseau_horaire)
        if paiements is None:
            paiements = list(self._pages("payments", {"filter": [f"createdTime>={t0}", f"createdTime<{t1}"]}))
        ids = list(dict.fromkeys(i for p in paiements if (i := (p.get("order") or {}).get("id"))))
        trouvees: dict[str, dict] = {}
        filtre = [f"clientCreatedTime>={t0 - 7 * 86_400_000}", f"clientCreatedTime<{t1}"]
        voulues = set(ids)
        for commande in self._pages("orders", {"filter": filtre, "expand": expansion}):
            # liste : collections imbriquées limitées ; une commande très longue est relue seule
            if commande["id"] in voulues and len((commande.get("lineItems") or {}).get("elements") or []) < 100:
                trouvees[commande["id"]] = commande
        trouvees.update(self.charger_commandes([i for i in ids if i not in trouvees], expansion))
        for id_commande in ids:
            commande = trouvees.get(id_commande)
            moment = moment_paiement(commande) if commande else None
            if moment is not None and t0 <= moment < t1:
                yield commande

    def charger_commandes(self, ids: list[str], expansion: str) -> dict[str, dict]:
        """Commandes par identifiant, 6 requêtes à la fois (Clover accepte 16 requêtes par seconde)."""
        if not ids:
            return {}
        local = threading.local()

        def une(id_commande: str):
            if not hasattr(local, "session"):
                local.session = requests.Session()
                local.session.headers.update(self.session.headers)
            reponse = self._get(f"orders/{id_commande}", {"expand": expansion}, local.session)
            reponse.raise_for_status()
            return id_commande, reponse.json()

        with ThreadPoolExecutor(max_workers=6) as groupe:
            return dict(groupe.map(une, ids))

    def rapport(self, debut: date, fin: date) -> RapportVentes:
        categories = self.categories_par_article()
        commandes = list(self.commandes(debut, fin))
        lignes = [l for c in commandes for l in lignes_commande(c, categories)]
        hors = [l for c in commandes for l in lignes_hors_recettes(c, categories)]
        return RapportVentes(debut=debut, fin=fin, source="API Clover",
                             lignes=cumuler(lignes), hors_recettes=cumuler(hors))


def _cents(valeur) -> Decimal:
    return Decimal(int(valeur or 0)) / CENT


def _arrondi(valeur: Decimal) -> Decimal:
    return valeur.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _rabais(remises: list[dict], base: Decimal) -> Decimal:
    """Total (négatif) d'une liste de rabais Clover sur `base`.

    Comme Clover : les pourcentages s'additionnent (99 % + 10 % = 109 %, plafonné à 100 %),
    les rabais en montant s'ajoutent, et le rabais ne peut pas dépasser le montant de départ.
    """
    pourcentage = sum((Decimal(str(r["percentage"])) for r in remises if r.get("percentage") is not None), Decimal("0"))
    montants = sum((_cents(r["amount"]) for r in remises if r.get("amount") is not None), Decimal("0"))  # négatifs
    rabais = -base * min(pourcentage, CENT) / CENT + montants
    return max(rabais, -base)


def moment_paiement(commande: dict) -> int | None:
    """Heure (ms) du premier paiement réussi ; à défaut, création de la commande si elle est marquée payée."""
    paiements = (commande.get("payments") or {}).get("elements") or []
    moments = [p["createdTime"] for p in paiements if p.get("result") == "SUCCESS" and p.get("createdTime")]
    if moments:
        return min(moments)
    if commande.get("paymentState") in ETATS_PAYES:
        return commande.get("createdTime")
    return None


def est_payee(commande: dict) -> bool:
    """Commande encaissée : au moins un paiement réussi (Clover laisse souvent paymentState à OPEN)."""
    paiements = (commande.get("payments") or {}).get("elements") or []
    if any(p.get("result") == "SUCCESS" for p in paiements):
        return True
    return commande.get("paymentState") in ETATS_PAYES


def lignes_hors_recettes(commande: dict, categories: dict[str, str]) -> list[LigneVente]:
    """Articles payés mais marqués « non-recette » dans Clover (absents du rapport « Ventes d'articles »)."""
    if not est_payee(commande):
        return []
    resultat = []
    for a in (commande.get("lineItems") or {}).get("elements") or []:
        if a.get("isRevenue") is False and not a.get("refunded"):
            quantite = Decimal(a["unitQty"]) / 1000 if a.get("unitQty") else Decimal("1")
            resultat.append(LigneVente(
                categorie=categories.get((a.get("item") or {}).get("id"), SANS_CATEGORIE),
                nom=(a.get("name") or "").strip(),
                quantite_vendue=quantite,
                ventes_brutes=_arrondi(_cents(a.get("price")) * quantite),
            ))
    return resultat


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
        taux = (a.get("taxRates") or {}).get("elements") or []
        ligne = LigneVente(
            categorie=categories.get(item_id, SANS_CATEGORIE),
            nom=(a.get("name") or "Article personnalisé").strip(),
            quantite_vendue=quantite,
            ventes_brutes=_arrondi(brut),
            rabais=_arrondi(rabais),
            taxable=any(int(t.get("rate") or 0) > 0 for t in taux),
            id_article=item_id or "",
        )
        if a.get("refunded"):
            ligne.quantite_remboursee = quantite
            ligne.remboursements = -_arrondi(brut + rabais)
        lignes.append((ligne, brut + rabais))

    # Rabais de commande répartis au prorata du montant de chaque ligne.
    base_commande = sum((m for _, m in lignes), Decimal("0"))
    rabais_commande = _arrondi(_rabais((commande.get("discounts") or {}).get("elements") or [], base_commande))
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
