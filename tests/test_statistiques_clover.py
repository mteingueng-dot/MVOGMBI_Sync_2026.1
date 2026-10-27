from datetime import datetime
from decimal import Decimal as D
from zoneinfo import ZoneInfo

from mvogmbi_sync.statistiques_clover import VUES, DonneesClover, statistiques

# samedi 2026-10-24 15:30 (heure de Toronto)
MOMENT = int(datetime(2026, 10, 24, 15, 30, tzinfo=ZoneInfo("America/Toronto")).timestamp() * 1000)


def commande(identifiant, prix, client=None, employe="E1"):
    return {"id": identifiant, "title": identifiant, "createdTime": MOMENT, "employee": {"id": employe},
            "device": {"id": "D1"}, "customers": {"elements": [{"id": client}] if client else []},
            "payments": {"elements": [{"result": "SUCCESS", "createdTime": MOMENT}]},
            "lineItems": {"elements": [{"name": "Plantain", "price": prix, "item": {"id": "I1"},
                                        "discounts": {"elements": [{"name": "Rabais 10%", "percentage": 10}]}}]}}


def paiement(commande_id, montant, carte=None, saisie=None, mode="Carte de crédit"):
    return {"result": "SUCCESS", "createdTime": MOMENT, "order": {"id": commande_id}, "amount": montant,
            "taxAmount": 0, "tipAmount": 0, "tender": {"label": mode}, "employee": {"id": "E1"},
            "cardTransaction": {"cardType": carte, "entryType": saisie}}


def test_toutes_les_vues():
    d = DonneesClover(commandes=[commande("A", 1000, client="C1"), commande("B", 2000, employe="E2")],
                      paiements=[paiement("A", 900, "VISA", "EMV_CONTACTLESS"), paiement("B", 1800, mode="Espèces")],
                      employes={"E1": "Alice", "E2": "Bruno"}, clients={"C1": "Jean Exemple"},
                      appareils={"D1": "Station Duo"}, categories={"I1": "Fruits & Légumes"})
    vues = statistiques(d)
    assert list(vues) == VUES
    resume = dict(vues["Résumé"][1])
    assert resume["Commandes payées"] == 2 and resume["Ventes nettes (articles)"] == D("27.00")  # 10 % de rabais
    assert vues["Par jour de la semaine"][1][0][:3] == ["samedi", 2, D("27.00")]
    assert vues["Par heure"][1][0][0] == "15 h"
    assert [l[0] for l in vues["Par employé"][1]] == ["Bruno", "Alice"]  # du plus gros au plus petit
    assert vues["Par client"][1][0][0] == "Jean Exemple" and vues["Par client"][1][-1][0] == "Sans client"
    assert {l[0] for l in vues["Par type de carte"][1]} == {"Visa", "Sans carte (Espèces)"}
    assert vues["Par mode de saisie de la carte"][1][-1][0] == "Sans contact"
    assert vues["Par article"][1][0][:3] == ["Plantain", "Fruits & Légumes", D("2")]
    assert vues["Rabais"][1] == [["Rabais 10%", 2, D("-3.00")]]
