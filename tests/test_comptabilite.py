from datetime import date
from decimal import Decimal

from mvogmbi_sync import comptabilite as cp


def facture(tiers, solde, retard):
    return cp.FactureOuverte(tiers, "n", date(2026, 9, 1), date(2026, 10, 1), Decimal(solde), retard)


def test_tranches_et_age_par_tiers():
    assert [cp.tranche(j) for j in (-3, 0, 1, 30, 31, 61, 91)] == [
        "À échoir", "À échoir", "1 à 30 jours", "1 à 30 jours", "31 à 60 jours", "61 à 90 jours", "Plus de 90 jours"]
    lignes = cp.age_par_tiers([facture("B", 100, -2), facture("A", 50, 45), facture("A", 20, 100)])
    assert lignes[0] == ["A", 2, Decimal(70), 0, 0, Decimal(50), 0, Decimal(20)]
    assert lignes[-1][:3] == ["Total", 3, Decimal(170)]


def test_nature_des_comptes_de_taxes():
    assert cp.nature_taxe("TPS/TVH perçue sur les ventes") == ("TPS/TVH", "Perçue sur les ventes")
    assert cp.nature_taxe("TVQ payée sur les achats") == ("TVQ", "Payée sur les achats (CTI / RTI)")
    assert cp.nature_taxe("TVQ à remettre (Remboursement)") is None
    assert cp.nature_taxe("Stock - Riz") is None


class Base:
    def requete(self, sql, _p=None):
        if "FROM taccount" in sql:
            return [{"lId": 23100000, "sName": "TPS/TVH perçue sur les ventes"},
                    {"lId": 23150000, "sName": "TPS/TVH payée sur les achats"},
                    {"lId": 23350000, "sName": "TPS/TVH à remettre (Remboursement)"},
                    {"lId": 23400000, "sName": "TVQ perçue sur les ventes"}]
        # sens normal du compte (passif) : perçue positive, payée négative
        return [{"c": 23100000, "s": 413.04}, {"c": 23150000, "s": -603.33}, {"c": 23400000, "s": 824.15}]


def test_declaration_taxes():
    lignes = cp.declaration_taxes(Base(), date(2026, 9, 1), date(2026, 9, 30))
    nets = {l[0]: l[3] for l in lignes if l[1].startswith("Net")}
    assert nets == {"TPS/TVH": Decimal("-190.29"), "TVQ": Decimal("824.15")}
    assert not any("remettre (R" in l[2] for l in lignes)


def test_prevision_tresorerie():
    factures = [facture("A", 300, 5), cp.FactureOuverte("B", "n", date(2026, 10, 1), date(2026, 11, 10),
                                                         Decimal(200), -12)]
    lignes = cp.prevoir_tresorerie(Decimal(1000), [Decimal(500)] * 4, factures, Decimal(100), date(2026, 10, 29))
    assert [l[-1] for l in lignes] == [Decimal(1100), Decimal(1300), Decimal(1700), Decimal(2100)]
    assert lignes[0][3] == Decimal(300) and lignes[1][3] == Decimal(200)
