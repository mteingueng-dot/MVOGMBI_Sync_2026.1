from datetime import date

from mvogmbi_sync.peremption import NEUTRE, ORANGE, PERIME, ROUGE, articles_peremption, lire_date
from mvogmbi_sync.statistiques_clover import comparaison, periode

AUJOURDHUI = date(2026, 10, 27)  # un mardi


def test_dates_du_sku():
    assert lire_date("25/05/2028") == date(2028, 5, 25)
    assert lire_date("07-05-2027") == date(2027, 5, 7)
    assert lire_date("31/12/27") == date(2027, 12, 31)
    assert lire_date("2027-03-11") == date(2027, 3, 11)
    for ignore in ("", None, "628250012345", "31/02/2027", "2027/0312", "12"):
        assert lire_date(ignore) is None


def test_trois_couleurs_triees_et_sku_ignores():
    articles = [{"name": "Lointain", "sku": "15/06/2027", "price": 499},
                {"name": "Deux mois", "sku": "27/12/2026", "itemStock": {"quantity": 4.0}},
                {"name": "Trois semaines", "sku": "17/11/2026"},
                {"name": "Périmé", "sku": "01/10/2026"},
                {"name": "Code-barres", "sku": "628250012345"}, {"name": "Vide", "sku": ""},
                {"name": "Supprimé", "sku": "01/11/2026", "deleted": True}]
    resultat = articles_peremption(articles, AUJOURDHUI)
    assert [(p.nom, p.etat, p.couleur) for p in resultat] == [
        ("Périmé", PERIME, "rouge"), ("Trois semaines", ROUGE, "rouge"), ("Deux mois", ORANGE, "orange"),
        ("Lointain", NEUTRE, "neutre")]
    assert resultat[1].jours == 21 and str(resultat[2].stock) == "4"


def test_periodes_comme_clover():
    assert periode("Aujourd'hui", AUJOURDHUI) == (AUJOURDHUI, AUJOURDHUI)
    assert periode("Cette semaine", AUJOURDHUI) == (date(2026, 10, 26), AUJOURDHUI)
    assert periode("Mois dernier", AUJOURDHUI) == (date(2026, 9, 1), date(2026, 9, 30))
    assert comparaison(AUJOURDHUI, AUJOURDHUI) == (date(2026, 10, 20), date(2026, 10, 20), "mardi dernier")
    assert comparaison(date(2026, 10, 1), AUJOURDHUI, "Ce mois-ci") == (date(2026, 9, 1), date(2026, 9, 27),
                                                                         "le mois dernier")
    assert comparaison(date(2026, 10, 1), date(2026, 10, 10))[:2] == (date(2026, 9, 21), date(2026, 9, 30))
