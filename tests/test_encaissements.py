from datetime import date, datetime
from decimal import Decimal as D

from mvogmbi_sync.encaissements import (A_SAISIR, A_VENIR, APPLIQUE, ECART, SANS_FACTURE, date_depot, evaluer,
                                        numero_compte_sage, regrouper)


def test_date_de_depot():
    # lundi à jeudi : le lendemain
    assert date_depot(date(2026, 5, 18)) == date(2026, 5, 19)  # lundi -> mardi
    assert date_depot(date(2026, 5, 21)) == date(2026, 5, 22)  # jeudi -> vendredi
    # vendredi, samedi, dimanche : le lundi suivant
    for jour in (22, 23, 24):
        assert date_depot(date(2026, 5, jour)) == date(2026, 5, 25)


def test_regroupement_fin_de_semaine():
    lots = {date(2026, 5, 21): D("1722.89"), date(2026, 5, 22): D("3909.13"), date(2026, 5, 23): D("4166.37"),
            date(2026, 5, 24): D("2504.08"), date(2026, 5, 25): D("1198.00"), date(2026, 5, 26): D("0")}
    depots = regrouper(lots)
    assert [d.date for d in depots] == [date(2026, 5, 22), date(2026, 5, 25), date(2026, 5, 26)]
    assert depots[1].montant == D("10579.58")  # dépôt du lundi = ventes par carte de vendredi à dimanche
    assert [l.facture for l in depots[1].lignes] == ["Vente 2026-05-22", "Vente 2026-05-23", "Vente 2026-05-24"]


def test_compte_sage():
    assert numero_compte_sage("1055") == 10550000
    assert numero_compte_sage(10550000) == 10550000


def test_etats_selon_sage():
    lots = {date(2026, 5, 18): D("1942.95"), date(2026, 5, 19): D("1446.41"), date(2026, 5, 20): D("2560.81"),
            date(2026, 10, 25): D("100.00"), date(2026, 5, 21): D("1722.89")}
    depots = regrouper(lots)
    etat_sage = {
        "Vente 2026-05-18": {"du": D("139.16"), "encaisse": {date(2026, 5, 19): D("1942.95")}},
        "Vente 2026-05-19": {"du": D("1588.43"), "encaisse": {}},
        "Vente 2026-05-20": {"du": D("2640.56"), "encaisse": {date(2026, 5, 21): D("100.00")}},
        "Vente 2026-10-25": {"du": D("150.00"), "encaisse": {}},
    }
    evaluer(depots, etat_sage, aujourdhui=date(2026, 10, 25))
    etats = {d.date: d.etat for d in depots}
    assert etats[date(2026, 5, 19)] == APPLIQUE
    assert etats[date(2026, 5, 20)] == A_SAISIR
    assert etats[date(2026, 5, 21)] == ECART
    assert etats[date(2026, 5, 22)] == SANS_FACTURE  # facture du 21 pas encore importée
    assert etats[date(2026, 10, 26)] == A_VENIR
