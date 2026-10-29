from datetime import date
from decimal import Decimal

import pytest

from mvogmbi_sync import documents as dc
from mvogmbi_sync import planning as pl


def test_heures_et_quarts():
    assert pl.lire_heure("8") == "08:00" and pl.lire_heure("8h30") == "08:30" and pl.lire_heure("17:45") == "17:45"
    with pytest.raises(pl.ErreurPlanning):
        pl.lire_heure("25:00")
    assert pl.Quart("08:00", "16:30", 30).heures == Decimal(8)
    assert pl.Quart("22:00", "06:00").heures == Decimal(8)  # après minuit


def test_planning_definir_copier_publier(tmp_path):
    p = pl.Planning(tmp_path)
    lundis = [j for j in pl.jours_du_mois("2026-11") if j.weekday() == 0]
    p.definir("e1", lundis, pl.Quart("8", "16", 30))
    p.definir("e1", [lundis[1]], None)  # repos
    relu = pl.Planning(tmp_path)
    assert relu.heures("2026-11", "e1") == Decimal("30.00")  # 4 des 5 lundis × 7,5 h
    assert relu.horaire_employe("e1", date(2026, 11, 1), 10) == []  # non publié : rien pour l'employé
    relu.publier("2026-11")
    horaire = dict(relu.horaire_employe("e1", date(2026, 11, 1), 10))
    assert horaire[date(2026, 11, 2)].debut == "08:00" and horaire[date(2026, 11, 9)] is None
    assert relu.copier_mois("2026-11", "2026-12", ["e1"]) == 4  # 4 lundis en décembre 2026
    with pytest.raises(pl.ErreurPlanning):
        relu.definir("e1", [date(2026, 12, 1)], pl.Quart("8", "9", 90))


def test_commande_facturee_et_imp(tmp_path):
    r = dc.Registre(tmp_path)
    with pytest.raises(ValueError):
        r.ajouter(dc.COMMANDE, "", "2026-10-29", [dc.LigneDocument("A1", "Riz", "2", "10")])
    cmd = r.ajouter(dc.COMMANDE, "Client A", "2026-10-29", [dc.LigneDocument("A1", "Riz", "2", "10", True),
                                                             dc.LigneDocument("B2", "Sel", "1", "3")])
    assert cmd.numero == "CC-0001" and cmd.sous_total == Decimal(23) and cmd.taxes == Decimal("3.00")
    facture = dc.Registre(tmp_path).facturer("CC-0001")
    relu = dc.Registre(tmp_path)
    assert facture.numero == "FV-0001" and relu.document("CC-0001").etat == dc.FACTUREE
    with pytest.raises(ValueError):
        relu.facturer("CC-0001")
    chemin = dc.ecrire_imp([relu.document("FV-0001")], tmp_path / "f.IMP", {})
    texte = chemin.read_bytes().decode("cp1252")
    assert '<SalInvoice>\r\n"Client A"' in texte and '"A1","2.0000","10.0000","20.00"' in texte
    assert texte.count('"0","1"') == 2  # TPS et TVQ sur la ligne taxable seulement
