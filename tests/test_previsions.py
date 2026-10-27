from datetime import date, timedelta
from decimal import Decimal as D

from mvogmbi_sync.previsions import (A_COMMANDER, SUFFISANT, VenteArticle, articles_a_commander, prevoir_achats,
                                     prevoir_ventes, tendance)

AUJOURDHUI = date(2026, 10, 27)


def test_formule_articles_a_commander():
    ventes = {"A": VenteArticle("Plantain", "Fruits", D("30"), D("45")), "B": VenteArticle("Riz", "Grains", D("5"), D("50")),
              "C": VenteArticle("Sans suivi", "Divers", D("2"), D("4")), "D": VenteArticle("Exact", "Divers", D("8"), D("8"))}
    articles = [{"id": "A", "itemStock": {"quantity": 12.0}, "cost": 100}, {"id": "B", "itemStock": {"quantity": 20.0}},
                {"id": "C"}, {"id": "D", "itemStock": {"quantity": 8.0}}]
    lignes = articles_a_commander(ventes, articles)
    assert [(l[0], l[4], l[5], l[6]) for l in lignes] == [("Plantain", D("-18"), A_COMMANDER, D("18")),
                                                         ("Exact", D("0"), A_COMMANDER, D("0")),
                                                         ("Riz", D("15"), SUFFISANT, D("0"))]
    assert lignes[0][7] == D("18.00")  # 18 x 1,00 $ de coût ; « Sans suivi » (stock non suivi) écarté


def test_prevision_meme_jour_et_tendance():
    historique = {AUJOURDHUI - timedelta(days=i): D("100") for i in range(1, 57)}
    for k in range(1, 9):  # les mardis des 8 semaines : 200 $
        historique[AUJOURDHUI - timedelta(days=7 * k)] = D("200")
    assert tendance(historique, AUJOURDHUI) == D("1")
    lignes = prevoir_ventes(historique, AUJOURDHUI, 7)
    assert lignes[0][:3] == ["2026-10-27", "mardi", D("200.00")] and lignes[1][2] == D("100.00")


def test_prevision_achats():
    ventes = {"A": VenteArticle("Plantain", "Fruits", D("28"), D("42"))}
    (ligne,) = prevoir_achats(ventes, [{"id": "A", "itemStock": {"quantity": 4.0}, "cost": 150}], 14)
    assert ligne[3] == D("14") and ligne[5] == D("10") and ligne[7] == D("15.00")


def test_stock_negatif_compte_pour_zero_dans_la_suggestion():
    ventes = {"A": VenteArticle("Cube Maggi", "Divers", D("80"), D("40"))}
    (ligne,) = articles_a_commander(ventes, [{"id": "A", "itemStock": {"quantity": -2571.0}}])
    assert ligne[4] == D("-2651") and ligne[5] == A_COMMANDER and ligne[6] == D("80")
