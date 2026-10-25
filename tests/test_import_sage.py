from datetime import date
from decimal import Decimal as D

from mvogmbi_sync.facture import preparer_facture
from mvogmbi_sync.import_sage import ConfigImport, TableCorrespondance, ecrire_imp, nom_fichier, preparer_import
from mvogmbi_sync.models import LigneVente, RapportVentes
from mvogmbi_sync.periodes import TypePeriode

J = date(2026, 10, 17)


def facture_test():
    rapport = RapportVentes(J, J, "api", [
        LigneVente("Féculents", "Igname Blanc (YAM) en lb", D("13.38"), ventes_brutes=D("53.37"), id_article="A1"),
        LigneVente("Féculents", "Igname blanc en spécial", D("5.41"), ventes_brutes=D("15.08"), id_article="A2"),
        LigneVente("Mèches", "MECHE X-PRESSION 3X 1 52''", D("4"), ventes_brutes=D("43.96"), taxable=True,
                   id_article="M1"),
        LigneVente("Divers", "Ancien nom", D("1"), ventes_brutes=D("3.99"), id_article="R1"),  # renommé depuis
        LigneVente("Divers", "Inconnu", D("1"), ventes_brutes=D("1.00"), id_article="X9"),
    ])
    return preparer_facture(rapport, TypePeriode.JOUR)


def table():
    return TableCorrespondance(
        par_id={"A1": "B0000094", "A2": "B0000094", "M1": "1001003021", "R1": "C00001039"},
        par_nom={},
    )


def test_regroupement_et_correspondance_par_identifiant():
    imp = preparer_import(facture_test(), table())
    lignes = {l.numero_sage: l for l in imp.lignes}
    igname = lignes["B0000094"]  # deux articles Clover -> un article Sage
    assert (igname.quantite, igname.montant) == (D("18.790"), D("68.45"))
    assert lignes["C00001039"].montant == D("3.99")  # retrouvé par l'ID malgré le changement de nom
    assert imp.non_reliees == ["Inconnu (1.000 x, 1.00 $)"]


def test_taxes_gq():
    imp = preparer_import(facture_test(), table())
    meche = next(l for l in imp.lignes if l.numero_sage == "1001003021")
    assert meche.taxes() == [("TPS/TVH", D("5.00"), D("2.20")), ("TVQ", D("9.975"), D("4.39"))]
    assert imp.total == imp.sous_total + D("6.59")


def test_fichier_imp(tmp_path):
    imp = preparer_import(facture_test(), table())
    chemin = ecrire_imp(imp, tmp_path / nom_fichier(imp.facture.numero), ConfigImport())
    assert chemin.name == "Vente_2026-10-17.IMP"
    brut = chemin.read_bytes()
    assert b"\r\r\n" not in brut
    lignes = brut.decode("cp1252").split("\r\n")
    assert lignes[:6] == ["<Version>", '"12001","1"', "</Version>", "", "<SalInvoice>", '"Vente Hebdomadaire"']
    assert lignes[6] == f'"3","Vente 2026-10-17","","10-17-2026","0","","{imp.total}","0.00"'
    assert '"1001003021","4.0000","10.9900","43.96","TPS/TVH","0","1","5.00","2.20","TVQ","0","1","9.975","4.39"' in lignes
    assert lignes[-2:] == ["</SalInvoice>", ""]
    assert len(lignes) == 7 + 3 + 2  # en-tête, 3 lignes de détail, fin


def test_numero_en_troisieme_position(tmp_path):
    imp = preparer_import(facture_test(), table())
    chemin = ecrire_imp(imp, tmp_path / "f.IMP", ConfigImport(position_numero=3))
    assert '"3","","Vente 2026-10-17","10-17-2026"' in chemin.read_text(encoding="cp1252")
