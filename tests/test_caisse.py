from datetime import date, datetime
from decimal import Decimal as D
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from mvogmbi_sync import caisse as ca

ZONE = ZoneInfo("America/Toronto")
ESP = {"labelKey": ca.ESPECES, "label": "Espèces"}
CARTE = {"labelKey": "com.clover.tender.credit_card", "label": "Carte de crédit"}


def _ms(jour, heure):
    return int(datetime(jour.year, jour.month, jour.day, heure, tzinfo=ZONE).timestamp() * 1000)


def test_especes_attendues_et_ecart(tmp_path):
    j = date(2026, 10, 28)
    d = SimpleNamespace(fuseau="America/Toronto", employes={"E1": "Ana"}, appareils={"A1": "Caisse"}, paiements=[
        {"id": "p1", "result": "SUCCESS", "tender": ESP, "amount": 1500, "tipAmount": 100, "createdTime": _ms(j, 10),
         "employee": {"id": "E1"}, "device": {"id": "A1"}},
        {"id": "p2", "result": "SUCCESS", "tender": CARTE, "amount": 5000, "cashbackAmount": 2000,
         "createdTime": _ms(j, 11)},
        {"id": "p3", "result": "FAIL", "tender": ESP, "amount": 9999, "createdTime": _ms(j, 12)},
        {"id": "p4", "result": "SUCCESS", "tender": ESP, "amount": 800, "createdTime": _ms(j, 23)},
    ], remboursements=[{"payment": {"id": "p4"}, "amount": 300, "createdTime": _ms(j, 23)}])
    a = ca.attendus(d)[j]
    assert (a.ventes, a.remboursements, a.remis, a.paiements) == (D("24.00"), D("3.00"), D("20.00"), 2)
    assert a.net == D("1.00") and a.par_employe["Ana"] == D("16.00")
    registre = ca.Registre(tmp_path)
    config = {"caisse": {"fond": "200"}}
    assert ca.fond_du_matin(registre, j, config) == D("200.00")
    coupures = {"100": 2, "1": 1}
    assert ca.total_coupures(coupures) == D("201.00")
    registre.noter(ca.Comptage(j.isoformat(), "201.00", "200.00", coupures, "gérant"))
    ligne = ca.lignes_jours({j: a}, ca.Registre(tmp_path), j, j, config)[0]
    assert ligne[5] == D("201.00") and ligne[7] == D("0.00") and ligne[8] == D("1.00")
    # le lendemain commence avec le fond laissé la veille
    assert ca.fond_du_matin(ca.Registre(tmp_path), date(2026, 10, 29), config) == D("200.00")


def test_recomptage_garde_l_historique_et_bilan_depots(tmp_path):
    registre = ca.Registre(tmp_path)
    registre.noter(ca.Comptage("2026-10-28", "450.00", "200.00", {}, "a"))
    registre.noter(ca.Comptage("2026-10-28", "455.00", "200.00", {}, "b"))
    r = ca.Registre(tmp_path)
    assert r.comptage(date(2026, 10, 28)).compte == "455.00" and len(r.historique) == 1
    lignes = [["2026-10-28", D(0), D(0), D(0), D(200), D(455), D(455), D(0), D("255.00"), "b"],
              ["2026-10-29", D(0), D(0), D(0), D(200), D(300), "", "", "", "Non compté"]]
    b = ca.bilan_depots(lignes, [("2026-10-30", D("250.00"), "releve.pdf")])
    assert b == {"a_deposer": D("255.00"), "depose": D("250.00"), "ecart": D("-5.00"), "non_comptes": 1}
