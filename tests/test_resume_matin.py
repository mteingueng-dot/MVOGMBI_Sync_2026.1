from datetime import date, datetime
from decimal import Decimal

from mvogmbi_sync import resume_matin as rm
from mvogmbi_sync.automatique import CompteRendu
from mvogmbi_sync.courriel import html_compte_rendu, texte_compte_rendu
from mvogmbi_sync.couts_sage import CoutSage
from mvogmbi_sync.previsions import VenteArticle


class Base:
    def requete(self, _sql, _p=None):
        return [{"lId": 1, "dtDate": datetime(2026, 10, 1), "nNetDay": 30, "s": 100},   # échue le 31/10
                {"lId": 2, "dtDate": datetime(2026, 9, 1), "nNetDay": 30, "s": 50},     # en retard
                {"lId": 3, "dtDate": datetime(2026, 10, 25), "nNetDay": 30, "s": 70},   # plus tard
                {"lId": 4, "dtDate": datetime(2026, 10, 1), "nNetDay": 0, "s": 0}]      # payée


def test_factures_a_payer():
    assert rm.factures_a_payer(Base(), date(2026, 10, 29)) == (Decimal("150.00"), 2, 1)


def test_marge_du_jour_ignore_couts_inconnus_et_douteux():
    ventes = {"A": VenteArticle("A", "", Decimal(10), Decimal(100)), "B": VenteArticle("B", "", Decimal(1), Decimal(5)),
              "C": VenteArticle("C", "", Decimal(2), Decimal(4))}
    couts = {"S1": CoutSage("S1", "", Decimal(7), Decimal(1), Decimal(7)),
             "S3": CoutSage("S3", "", Decimal(900), Decimal(1), Decimal(900))}
    assert rm.marge_du_jour(ventes, {"A": "S1", "C": "S3"}, couts) == Decimal("30.0")


def test_resume_dans_le_courriel():
    r = rm.ResumeMatin(date(2026, 10, 28), Decimal("3412"), Decimal("3160"), Decimal("31.2"), Decimal("18950"),
                       Decimal("4210"), 3, 1, ["Bobolo"], 11, ["Riz (15/11)"])
    assert r.variation == 8
    cr = CompteRendu()
    cr.resume = r
    texte = texte_compte_rendu(cr)
    assert texte.startswith("Résumé du 2026-10-28") and "3 412,00 $ (+8 %" in texte and "Bobolo" in texte
    assert "Ventes d&#x27;hier" in html_compte_rendu(cr) and "Bobolo" in html_compte_rendu(cr)
