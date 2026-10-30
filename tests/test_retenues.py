from datetime import date
from decimal import Decimal

from mvogmbi_sync import retenues as rt


def test_organisme_des_comptes():
    assert rt.organisme("RRQ à payer") == rt.RQ
    assert rt.organisme("Québec à payer") == rt.RQ
    assert rt.organisme("RQAP à payer") == rt.RQ
    assert rt.organisme("Impôt fédéral à payer") == rt.ARC
    assert rt.organisme("Assurance-emploi à payer") == rt.ARC
    assert rt.organisme("CNESST à payer") == rt.CNESST
    assert rt.organisme("Vacances à payer") == rt.VACANCES
    assert rt.organisme("Total - Ministre des Finances Qué.") is None


class Base:
    def requete(self, sql, _p=None):
        if "FROM taccount" in sql:
            return [{"lId": 22000000, "sName": "RRQ à payer", "dYtcLY": 100},
                    {"lId": 21900000, "sName": "Impôt fédéral à payer", "dYtcLY": 0},
                    {"lId": 21700000, "sName": "Vacances à payer", "dYtcLY": 0},
                    {"lId": 54100000, "sName": "Salaires & traitements", "dYtcLY": 0}]
        if "DISTINCT" in sql:
            return [{"c": c} for c in (22000000, 21900000, 21700000, 54100000, 10550000)]
        return [{"c": 22000000, "paie": 0, "avant": 1, "s": 50},      # avant le mois
                {"c": 22000000, "paie": 1, "avant": 0, "s": 80},      # retenues du mois
                {"c": 22000000, "paie": 0, "avant": 0, "s": -150},    # versement à Revenu Québec
                {"c": 21900000, "paie": 1, "avant": 0, "s": 40},
                {"c": 21700000, "paie": 1, "avant": 0, "s": 30},
                {"c": 54100000, "paie": 1, "avant": 0, "s": 1000}]


def test_etat_du_mois():
    lignes, info = rt.etat(Base(), 2026, 9)
    rrq = next(l for l in lignes if l[1].startswith("2200"))
    assert rrq[2:] == [Decimal(150), Decimal(80), Decimal(150), Decimal(80), Decimal(80)]
    assert info["a_remettre"] == {rt.ARC: Decimal(40), rt.RQ: Decimal(80)}  # vacances jamais remises
    assert info["salaires"] == Decimal(1000) and info["echeance"] == date(2026, 10, 15)


def test_suivi_des_remises():
    from datetime import date
    from decimal import Decimal as D

    from mvogmbi_sync import retenues as re_

    ech = date(2026, 10, 15)
    assert re_.etat_remise(D("500"), [(date(2026, 10, 10), D("500"))], ech, date(2026, 10, 29))[:1] == (re_.REMIS,)
    assert re_.etat_remise(D("500"), [(date(2026, 10, 10), D("200")), (date(2026, 10, 20), D("300"))], ech,
                           date(2026, 10, 29)) == (re_.REMIS_EN_RETARD, D("500"), date(2026, 10, 20))
    assert re_.etat_remise(D("500"), [], ech, date(2026, 10, 12))[0] == re_.A_REMETTRE
    assert re_.etat_remise(D("500"), [(date(2026, 10, 10), D("100"))], ech, date(2026, 10, 16))[0] == re_.EN_RETARD
    assert re_.etat_remise(D("0"), [], ech, date(2026, 10, 16))[0] == re_.RIEN
    lignes = [["2026-09", re_.RQ, D("500"), D(0), "", "2026-10-15", re_.A_REMETTRE],
              ["2026-08", re_.ARC, D("300"), D(0), "", "2026-09-15", re_.EN_RETARD],
              ["2026-09", re_.ARC, D("200"), D(200), "2026-10-01", "2026-10-15", re_.REMIS]]
    a = re_.alertes(lignes, date(2026, 10, 12))
    assert len(a) == 2 and "EN RETARD" in a[0] + a[1]
    assert re_.alertes(lignes[:1], date(2026, 10, 1)) == []   # échéance dans plus de 5 jours : pas encore d'alerte
