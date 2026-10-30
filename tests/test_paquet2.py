from datetime import date
from decimal import Decimal as D

from mvogmbi_sync import budget as bu
from mvogmbi_sync import etiquettes as et
from mvogmbi_sync import retours as rt


def test_retour_facture_negative(tmp_path):
    r = rt.Registre(tmp_path).ajouter("ESSAI FOURNISSEUR 1", "104202", "2026-11-30",
                                      [rt.LigneRetour("A1", "Riz", "2", "10.00", "GQ"),
                                       rt.LigneRetour("A2", "Huile", "1", "5.00", "")], "abîmé", "x")
    assert r.numero == "R-104202"
    f = r.facture()
    assert [l.quantite for l in f.lignes] == [D("-2"), D("-1")] and f.sous_total == D("-25.00")
    assert f.tps == D("-1.00") and f.tvq == D("-2.00") and f.total == D("-28.00")
    deux = rt.Registre(tmp_path).ajouter("ESSAI FOURNISSEUR 1", "104202", "2026-12-01",
                                         [rt.LigneRetour("A1", "Riz", "1", "10.00")])
    assert deux.numero != r.numero


def test_etiquettes_code_barres():
    assert et.code128("A")[-1] == et.ARRET and et.code128("A")[-2] == (104 + 33) % 103
    svg = et.svg_code_barres("12345")
    assert svg.startswith("<svg") and svg.count("<rect") == 3 * len(et.code128("12345")) + 1  # l'arrêt a 4 barres
    e = et.depuis_article({"name": "Plantain", "price": 249, "priceType": "PER_UNIT", "unitName": "lb", "code": "123"})
    assert (e.prix, e.unite, e.code) == (D("2.49"), "lb", "123")
    page = et.page([e] * 31, imprimer=False)
    assert page.count("class='e'") == 31 and "2,49 $ / lb" in page


def test_budget_et_main_oeuvre(tmp_path):
    b = bu.Budget(tmp_path)
    b.definir(2026, 10, {"Produits (ventes)": D("100000"), "Coût des marchandises vendues": D("70000"),
                         "Autres charges": D("20000")})
    assert bu.Budget(tmp_path).mois(2026, 10)["Produits (ventes)"] == D("100000.00")
    reel = {"Produits (ventes)": D("110000"), "Coût des marchandises vendues": D("75000"), "Autres charges": D("20000")}
    lignes = bu.ecarts(reel, bu.Budget(tmp_path).mois(2026, 10), reel, bu.Budget(tmp_path).mois(2026, 10))
    assert lignes[0][3] == D("10000") and lignes[0][4] == "+10,0 %" and lignes[-1][1] == D("15000")
    assert bu.proposer({"Produits (ventes)": D("1000")}, D("5")) == {"Produits (ventes)": D("1050")}
    j = date(2026, 10, 28)
    l = bu.main_oeuvre({j: D("1000")}, {j: D("20")}, {j: D("24")}, j, j, D("18"), D("15"))
    assert l == [["2026-10-28", D("1000.00"), D("20"), D("24"), D("414.00"), "41,4 %"]]
