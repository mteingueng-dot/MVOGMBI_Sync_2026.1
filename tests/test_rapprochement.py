from datetime import date
from decimal import Decimal as D

from mvogmbi_sync.rapprochement import (A_SAISIR, CONFIRME, RAPPROCHE, MouvementBanque, MouvementSage, Releve, _date_ligne,
                                        _montant, motif, rapprocher, resume)


def banque(jour, montant, description="", rang=0):
    return MouvementBanque(jour, description, D(montant), releve="R.pdf", rang=rang)


def test_montants_et_dates_du_releve():
    assert _montant("1 842,10") == D("1842.10")
    assert _montant("1,842.10") == D("1842.10")
    assert _montant("35,00-") == D("-35.00")
    assert _date_ligne("02 SEP", date(2026, 9, 30)) == date(2026, 9, 2)
    assert _date_ligne("2026-09-02", None) == date(2026, 9, 2)
    assert _date_ligne("30 DÉC", date(2027, 1, 31)) == date(2026, 12, 30)  # relevé de janvier
    assert _date_ligne("Dépôt", date(2026, 9, 30)) is None


def test_controle_des_soldes():
    r = Releve("R.pdf", solde_ouverture=D("1000.00"), solde_fermeture=D("1500.00"),
               mouvements=[banque("2026-09-02", "700.00"), banque("2026-09-03", "-200.00", rang=1)])
    assert r.controles() == []
    r.solde_fermeture = D("1600.00")
    assert "solde calculé" in r.controles()[0]


def test_rapprochement_simple_groupe_et_absent():
    b = [banque("2026-09-02", "1842.10", "DEPOT CLOVER"), banque("2026-09-08", "3000.00", "DEPOT CLOVER", 1),
         banque("2026-09-10", "-12.95", "FRAIS MENSUELS", 2), banque("2026-09-11", "-632.36", "VIREMENT INTERAC", 3)]
    s = [MouvementSage(1, "2026-09-01", "20251240", "Vente Hebdomadaire", D("1842.10")),
         MouvementSage(2, "2026-09-07", "1", "Vente Hebdomadaire", D("1800.00")),   # fin de semaine : 2 écritures
         MouvementSage(3, "2026-09-07", "2", "Vente Hebdomadaire", D("1200.00")),
         MouvementSage(4, "2026-09-10", "Comptant", "QBS Transport", D("-632.36")),
         MouvementSage(5, "2026-09-29", "Comptant", "Chèque pas encore passé", D("-100.00"))]
    rapprocher(b, s)
    assert [m.etat for m in b] == [RAPPROCHE, RAPPROCHE, A_SAISIR, RAPPROCHE]
    assert b[1].sage == [2, 3] and b[3].sage == [4]
    assert [x.ident for x in s if not x.rapproche] == [5]
    chiffres = resume(b, s, D("5000.00"), D("4912.95"))
    assert chiffres["absents"] == D("-12.95") and chiffres["circulation"] == D("-100.00")
    assert chiffres["non_explique"] == D("0.00")     # écart 87,05 = −12,95 absent de Sage + 100,00 pas encore à la banque


def test_decision_conservee_et_motif():
    b = [banque("2026-09-10", "-12.95", "FRAIS MENSUELS")]
    b[0].etat, b[0].compte = CONFIRME, "5450"
    rapprocher(b, [MouvementSage(9, "2026-09-10", "x", "y", D("-12.95"))])
    assert b[0].etat == CONFIRME                     # un choix du propriétaire n'est pas défait
    assert motif("FRAIS MENS. 09/2026") == motif("FRAIS MENS. 10/2026")
