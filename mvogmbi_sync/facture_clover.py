"""Facture Clover d'une commande, pour vérification (demande du propriétaire du 2026-11-08 : « en cliquant sur le numéro
de la facture dans l'anomalie, celle-ci ouvre la vraie facture pour vérification »).

Lecture seule : la commande est relue dans Clover au moment du clic (articles, rabais, remboursements, paiements,
client, employé), dans le point de vente qui la connaît. Les montants nets des lignes sont calculés comme les
factures Sage et les statistiques (`api_clover.lignes_commande`). Les chiffres de la carte ne sont jamais repris
(seuls le type de carte et le mode de saisie).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

ZERO = Decimal(0)
EXPANSION = ("lineItems,lineItems.discounts,lineItems.modifications,lineItems.taxRates,discounts,payments,"
             "payments.tender,payments.cardTransaction,customers,employee,refunds,device")


@dataclass
class FactureClover:
    id: str
    numero: str
    moment: str
    employe: str
    client: str
    appareil: str
    etat: str
    point_vente: str = ""
    lignes: list[list] = field(default_factory=list)       # article, catégorie, qté, prix, brut, rabais, remb., net, taxe
    rabais_commande: list[list] = field(default_factory=list)  # nom, montant ou %
    paiements: list[list] = field(default_factory=list)    # date, mode, carte, saisie, montant, taxes, pourboire, résultat
    remboursements: list[list] = field(default_factory=list)  # date, montant, taxes
    totaux: list[tuple[str, Decimal]] = field(default_factory=list)
    note: str = ""


ENTETES_LIGNES = ["Article", "Catégorie", "Quantité", "Prix unitaire", "Ventes brutes", "Rabais", "Remboursements",
                  "Ventes nettes", "Taxes"]
ENTETES_PAIEMENTS = ["Date et heure", "Mode de paiement", "Carte", "Saisie", "Montant", "Taxes", "Pourboire",
                     "Résultat"]
ENTETES_REMBOURSEMENTS = ["Date et heure", "Montant", "Taxes"]


def lire(racine, id_commande: str, points=None) -> FactureClover:
    """Commande relue dans Clover : essayée dans chaque point de vente donné (le n° 1 si aucun) jusqu'à la trouver."""
    from .points_vente import client

    erreurs = []
    for pv in (points or [None]):
        try:
            connexion = client(racine, pv)
            commande = connexion.charger_commandes([id_commande], EXPANSION).get(id_commande)
        except Exception as erreur:  # noqa: BLE001 — commande inconnue de ce point de vente (404) : suivant
            erreurs.append(str(erreur))
            continue
        if commande:
            try:
                categories = connexion.categories_par_article()
            except Exception:  # noqa: BLE001 — catégories illisibles : « Non catégorisé(e) »
                categories = {}
            return detail(commande, getattr(pv, "libelle", "") if pv else "", categories=categories)
    raise LookupError("Commande introuvable dans Clover" + (f" ({erreurs[-1]})" if erreurs else "") + ".")


def detail(o: dict, point_vente: str = "", fuseau: str = "America/Toronto",
           categories: dict | None = None) -> FactureClover:
    """Facture lisible d'une commande Clover (dict renvoyé par l'API, développée par `EXPANSION`)."""
    from .api_clover import _cents, lignes_commande, moment_paiement
    from .statistiques_clover import CARTES, SAISIES

    zone = ZoneInfo(fuseau)

    def quand(ms) -> str:
        return f"{datetime.fromtimestamp(ms / 1000, zone):%Y-%m-%d %H:%M}" if ms else ""

    employe = (o.get("employee") or {}).get("name") or ""
    clients = []
    for c in (o.get("customers") or {}).get("elements") or []:
        nom = " ".join(x for x in (c.get("firstName"), c.get("lastName")) if x)
        clients.append(nom or c.get("id", ""))
    f = FactureClover(id=o["id"], numero=str(o.get("title") or o["id"]),
                      moment=quand(moment_paiement(o) or o.get("createdTime")), employe=employe or "—",
                      client=", ".join(clients) or "Sans client", appareil=(o.get("device") or {}).get("name") or "",
                      etat=str(o.get("paymentState") or o.get("state") or ""), point_vente=point_vente)
    articles = (o.get("lineItems") or {}).get("elements") or []
    taxes_par_nom = {}
    for a in articles:
        taux = [t.get("name", "") for t in (a.get("taxRates") or {}).get("elements") or []
                if t.get("name") and t.get("name") != "NO_TAX_APPLIED"]
        taxes_par_nom.setdefault(a.get("name", ""), ", ".join(taux) or "Aucune")
    for l in lignes_commande(o, categories or {}):
        prix = (l.ventes_brutes / l.quantite_vendue).quantize(Decimal("0.01")) if l.quantite_vendue else ZERO
        f.lignes.append([l.nom, l.categorie, f"{l.quantite_nette.normalize():f}".replace(".", ","), prix, l.ventes_brutes, l.rabais,
                         l.remboursements, l.ventes_nettes, taxes_par_nom.get(l.nom, "")])
    for r in (o.get("discounts") or {}).get("elements") or []:
        valeur = f"{r['percentage']} %" if r.get("percentage") is not None else _cents(r.get("amount"))
        f.rabais_commande.append([r.get("name") or "Rabais de commande", valeur])
    for p in sorted((o.get("payments") or {}).get("elements") or [], key=lambda p: p.get("createdTime", 0)):
        carte = p.get("cardTransaction") or {}
        f.paiements.append([quand(p.get("createdTime")), (p.get("tender") or {}).get("label", ""),
                            CARTES.get(carte.get("cardType"), carte.get("cardType") or ""),
                            SAISIES.get(carte.get("entryType"), carte.get("entryType") or ""), _cents(p.get("amount")),
                            _cents(p.get("taxAmount")), _cents(p.get("tipAmount")),
                            "Réussi" if p.get("result") == "SUCCESS" else str(p.get("result") or "")])
    for r in (o.get("refunds") or {}).get("elements") or []:
        f.remboursements.append([quand(r.get("createdTime")), -_cents(r.get("amount")), -_cents(r.get("taxAmount"))])
    brut = sum((l[4] for l in f.lignes), ZERO)
    rabais = sum((l[5] for l in f.lignes), ZERO)
    remb = sum((l[6] for l in f.lignes), ZERO)
    nettes = sum((l[7] for l in f.lignes), ZERO)
    reussis = [p for p in f.paiements if p[7] == "Réussi"]
    f.totaux = [("Ventes brutes", brut), ("Rabais", rabais), ("Remboursements", remb), ("Ventes nettes", nettes),
                ("Taxes payées", sum((p[5] for p in reussis), ZERO)),
                ("Pourboires", sum((p[6] for p in reussis), ZERO)),
                ("Montant payé", sum((p[4] for p in reussis), ZERO)),
                ("Total de la commande (Clover)", _cents(o.get("total")))]
    if brut and -rabais >= brut / 2:
        f.note = "Rabais de 50 % ou plus sur cette commande."
    return f
