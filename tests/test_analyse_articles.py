from datetime import date
from decimal import Decimal

from mvogmbi_sync import analyse_articles as aa
from mvogmbi_sync.previsions import VenteArticle


def article(n, jours=None, quantite=0, valeur=0, categorie="Riz"):
    vente = None if jours is None else date(2026, 10, 29) - __import__("datetime").timedelta(days=jours)
    return aa.ArticleSage(n, f"Article {n}", categorie, Decimal(quantite), Decimal(valeur), vente)


def test_inactifs_seuil_tri_et_tranches():
    articles = {a.numero: a for a in (article("A", 10, 5, 50), article("B", 45, 2, 20), article("C", 400, 0, 0),
                                      article("D", None, 3, 90), article("E", 75, 1, 5, "Huile"))}
    lignes, resume = aa.produits_inactifs(articles, 30, date(2026, 10, 29))
    assert [l[0] for l in lignes] == ["D", "B", "E", "C"]  # valeur du stock, puis temps sans vente
    assert lignes[0][3] == "Jamais vendu" and lignes[0][4] == ""
    assert lignes[1][5] == "30 à 59 jours" and lignes[3][5] == "365 jours et plus"
    assert resume["valeur"] == Decimal(115) and resume["jamais"] == 1
    lignes, _ = aa.produits_inactifs(articles, 60, date(2026, 10, 29), avec_stock=True)
    assert [l[0] for l in lignes] == ["D", "E"]
    lignes, _ = aa.produits_inactifs(articles, 30, date(2026, 10, 29), categorie="huile")
    assert [l[0] for l in lignes] == ["E"]


def test_pareto_classes_et_couverture():
    articles = {"X": aa.ArticleSage("X", "X", "Riz", Decimal(30), Decimal(60)),
                "Y": aa.ArticleSage("Y", "Y", "Riz", Decimal(0), Decimal(0)),
                "Z": aa.ArticleSage("Z", "Z", "Riz", Decimal(10), Decimal(10 ** 6))}
    ventes = {"X": (Decimal(30), Decimal(700)), "Y": (Decimal(10), Decimal(200)), "Z": (Decimal(10), Decimal(100)),
              "W": (Decimal(1), Decimal(0))}
    lignes, resume = aa.pareto(articles, ventes, 30)
    assert [(l[2], l[1]) for l in lignes] == [("X", "A"), ("Y", "A"), ("Z", "B")]  # Y : 70 % avant -> A ; Z : 90 % -> B
    assert lignes[0][13] == 30 and lignes[1][14] == "Rupture"   # 30 en stock pour 1 vendu par jour
    assert lignes[2][14].startswith("Valeur du stock douteuse") and resume["douteux"] == 1
    assert resume["A"] == 2 and resume["ventes_A"] == Decimal(900) and resume["valeur"] == Decimal(60)


def test_articles_clover():
    items = [{"id": "I1", "name": "Riz 5 kg", "cost": 1250, "itemStock": {"quantity": 4},
              "categories": {"elements": [{"name": "Riz"}]}},
             {"id": "I2", "name": "Sel", "deleted": True}]
    ventes = {"I1": VenteArticle("Riz 5 kg", "Riz", Decimal(2), Decimal("30.00"), date(2026, 10, 1)),
              "OLD": VenteArticle("Ancien", "", Decimal(1), Decimal("5.00"), date(2026, 9, 1))}
    articles = aa.articles_clover(items, ventes)
    assert set(articles) == {"I1", "OLD"}
    assert articles["I1"].valeur == Decimal("50.00") and articles["I1"].cump == Decimal("12.5")
    assert articles["I1"].derniere_vente == date(2026, 10, 1) and not articles["OLD"].catalogue
    lignes, _ = aa.produits_inactifs(articles, 1, date(2026, 10, 29))
    assert [l[0] for l in lignes] == ["I1"]  # l'ancien ID n'est plus un produit à vendre
    assert aa.ventes_clover(ventes)["I1"] == (Decimal(2), Decimal("30.00"))
