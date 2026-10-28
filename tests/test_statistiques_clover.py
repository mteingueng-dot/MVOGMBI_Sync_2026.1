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


def test_benefices_et_kpi_avec_le_cump_sage():
    from mvogmbi_sync.statistiques_clover import kpis

    d = DonneesClover(commandes=[commande("A", 1000), commande("B", 2000)],
                      paiements=[paiement("A", 900, "VISA", "EMV_CONTACTLESS"), paiement("B", 1800, mode="Espèces")],
                      employes={"E1": "Alice"}, categories={"I1": "Fruits & Légumes"})
    vues = statistiques(d, {"I1": ("B0000192", D("0.50"))})
    resume = dict(vues["Résumé"][1])
    assert resume["Coût des ventes (CUMP Sage)"] == D("1.00") and resume["Bénéfice brut"] == D("26.00")
    assert resume["Marge brute (%)"] == D("96.3")
    assert vues["Bénéfices"][1][0][:7] == ["Plantain", "Fruits & Légumes", D("2"), D("27.00"), D("0.50"), D("1.00"),
                                          D("26.00")]
    indicateurs = {titre: valeur for titre, _, valeur in kpis(vues, [("Carte", D("9.00")), ("Espèces", D("18.00"))])}
    assert indicateurs["Bénéfice brut"] == D("26.00") and indicateurs["Part payée en espèces"] == D("66.7")
    assert "Coût des ventes (CUMP Sage)" not in dict(statistiques(d)["Résumé"][1])  # sans coûts : pas de bénéfice


def test_filtres_globaux():
    from mvogmbi_sync.statistiques_clover import filtrer

    d = DonneesClover(commandes=[commande("A", 1000, client="C1"), commande("B", 2000, employe="E2")],
                      paiements=[paiement("A", 900), paiement("B", 1800)],
                      employes={"E1": "Alice", "E2": "Bruno"}, clients={"C1": "Jean Exemple"},
                      categories={"I1": "Fruits & Légumes"})
    assert dict(statistiques(filtrer(d, {"Employé": "Bruno"}))["Résumé"][1])["Commandes payées"] == 1
    assert [c["id"] for c in filtrer(d, {"Client": "jean exemple"}).commandes] == ["A"]
    assert len(filtrer(d, {"Catégorie": "Fruits & Légumes", "Article": "Plantain"}).commandes) == 2
    assert filtrer(d, {"Article": "Riz"}).commandes == [] and filtrer(d, {}) is d
    assert len(filtrer(d, {"Employé": "Bruno"}).paiements) == 1  # les paiements suivent les commandes


def test_filtre_mode_de_paiement():
    from mvogmbi_sync.statistiques_clover import filtrer

    d = DonneesClover(commandes=[commande("A", 1000), commande("B", 2000)],
                      paiements=[paiement("A", 900, mode="Espèces"), paiement("B", 1000, mode="Espèces"),
                                 paiement("B", 800)],
                      employes={"E1": "Alice"}, clients={}, categories={})
    f = filtrer(d, {"Mode de paiement": "espèces"})
    assert [c["id"] for c in f.commandes] == ["A", "B"] and sum(p["amount"] for p in f.paiements) == 1900
    f = filtrer(d, {"Mode de paiement": "Carte de crédit"})
    assert [c["id"] for c in f.commandes] == ["B"] and [p["amount"] for p in f.paiements] == [800]
