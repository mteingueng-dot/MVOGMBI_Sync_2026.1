from datetime import date
from decimal import Decimal as D

from mvogmbi_sync.api_clover import lignes_commande
from mvogmbi_sync.export_clover import montant
from mvogmbi_sync.models import LigneVente, cumuler
from mvogmbi_sync.periodes import TypePeriode, bornes, en_millisecondes


def test_montant_format_clover():
    assert montant("53\xa0972,17\xa0$") == D("53972.17")
    assert montant("-31,04\xa0$") == D("-31.04")
    assert montant("10544.14") == D("10544.14")
    assert montant("-") == D("0")
    assert montant(5) == D("5")


def test_bornes_periodes():
    jeudi = date(2026, 1, 15)
    assert bornes(TypePeriode.JOUR, jeudi) == (jeudi, jeudi)
    assert bornes(TypePeriode.SEMAINE, jeudi) == (date(2026, 1, 12), date(2026, 1, 18))
    assert bornes(TypePeriode.MOIS, jeudi) == (date(2026, 1, 1), date(2026, 1, 31))
    assert bornes(TypePeriode.MOIS, date(2028, 2, 10)) == (date(2028, 2, 1), date(2028, 2, 29))


def test_journee_en_heure_locale():
    t0, t1 = en_millisecondes(date(2026, 1, 15), date(2026, 1, 15), "America/Toronto")
    assert t1 - t0 == 24 * 3600 * 1000
    assert t0 == 1768453200000  # 2026-01-15 00:00 HNE (UTC-5)


def test_cumul_par_article():
    lignes = cumuler([
        LigneVente("Riz", "Riz 5kg", D("1"), ventes_brutes=D("10")),
        LigneVente("Riz", "Riz 5kg", D("2"), ventes_brutes=D("20"), rabais=D("-3")),
    ])
    assert len(lignes) == 1
    assert lignes[0].quantite_nette == D("3")
    assert lignes[0].ventes_nettes == D("27")
    assert lignes[0].prix_unitaire_net == D("9.0000")


def test_commande_clover_rabais_et_poids():
    commande = {
        "paymentState": "PAID",
        "lineItems": {"elements": [
            {"name": "Sardines Titus 125g", "price": 199, "item": {"id": "A"},
             "discounts": {"elements": [{"amount": -19}]}},
            {"name": "Viande de chèvre", "price": 1500, "unitQty": 1500, "item": {"id": "B"}},
        ]},
        "discounts": {"elements": [{"percentage": 10}]},
    }
    lignes = lignes_commande(commande, {"A": "Divers", "B": "Viandes & Volailles"})
    sardines, chevre = lignes
    assert sardines.ventes_brutes == D("1.99") and chevre.ventes_brutes == D("22.50")
    assert chevre.quantite_vendue == D("1.5")
    # 10 % de (1.80 + 22.50) = 2.43, réparti au prorata
    assert sardines.rabais + chevre.rabais == D("-0.19") + D("-2.43")
    assert sardines.categorie == "Divers"


def test_commande_non_payee_ignoree():
    assert lignes_commande({"paymentState": "OPEN", "lineItems": {"elements": [{"price": 100}]}}, {}) == []


def test_comparaison_detecte_les_ecarts():
    from mvogmbi_sync.comparaison import comparer
    from mvogmbi_sync.models import RapportVentes

    j = date(2026, 10, 23)
    export = RapportVentes(j, j, "export", [
        LigneVente("Riz", "Riz 5kg", D("2"), ventes_brutes=D("20")),
        LigneVente("Divers", "Milo 400g", D("1"), ventes_brutes=D("7.99")),
    ])
    api = RapportVentes(j, j, "api", [
        LigneVente("Non catégorisé(e)", "riz  5KG", D("2"), ventes_brutes=D("20")),
        LigneVente("Divers", "Milo 400g", D("1"), ventes_brutes=D("7.99"), rabais=D("-0.80")),
    ])
    ecarts = comparer(export, api)
    assert [e.nom for e in ecarts] == ["Milo 400g"]
