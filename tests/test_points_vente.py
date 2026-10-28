from datetime import date
from decimal import Decimal as D

import pytest

from mvogmbi_sync.points_vente import (DEPOT_DEFAUT, PRINCIPAL, choisir, permis, points_de_vente,
                                       problemes_configuration)

CONFIG = {
    "clover": {"merchant_id": "AAAAAAAAAAAAA"},
    "points_vente": [
        {"code": "2", "nom": "Magasin 2", "merchant_id": "BBBBBBBBBBBBB", "client_sage": "Vente Magasin 2",
         "depot_sage": "Magasin 2", "prefixe": "V2"},
        {"code": "3", "nom": "Kiosque", "merchant_id": "CCCCCCCCCCCCC", "client_sage": "Vente Kiosque",
         "prefixe": "V3", "actif": False},
    ],
}


def test_point_de_vente_principal_inchange_sans_configuration():
    (p,) = points_de_vente({"clover": {"merchant_id": "AAAAAAAAAAAAA"}})
    assert (p.code, p.client_sage, p.prefixe, p.depot_sage, p.cle_jeton) == (
        PRINCIPAL, "Vente Hebdomadaire", "Vente", DEPOT_DEFAUT, "clover_jeton")
    assert p.principal and p.depot_par_defaut


def test_choisir_un_plusieurs_ou_tous(tmp_path):
    assert [p.code for p in choisir(CONFIG, "tous")] == ["1", "2"]  # le n° 3 est inactif
    assert [p.code for p in choisir(CONFIG, None)] == ["1", "2"]
    assert [p.code for p in choisir(CONFIG, "3,1")] == ["3", "1"]
    with pytest.raises(ValueError):
        choisir(CONFIG, "9")
    p2 = choisir(CONFIG, "2")[0]
    assert p2.cle_jeton == "clover_jeton_2" and not p2.depot_par_defaut
    assert p2.fichier(tmp_path, "correspondance_articles.xlsx") == tmp_path / "points_vente" / "2" / \
        "correspondance_articles.xlsx"
    assert choisir(CONFIG, "1")[0].fichier(tmp_path, "x.csv") == tmp_path / "x.csv"
    assert [p.code for p in permis(CONFIG, {"2", "3"})] == ["2"]
    assert [p.code for p in permis(CONFIG, None)] == ["1", "2"]


def test_configuration_incoherente_signalee():
    config = {"clover": {"merchant_id": "A"}, "points_vente": [
        {"code": "2", "merchant_id": "B", "client_sage": "Vente Hebdomadaire", "prefixe": "Vente"},
        {"code": "3", "merchant_id": "C", "client_sage": "Vente 3", "prefixe": "Trop long"}]}
    texte = " | ".join(problemes_configuration(points_de_vente(config)))
    assert "même préfixe" in texte and "même client Sage" in texte and "Trop long" in texte
    assert problemes_configuration(points_de_vente(CONFIG)) == []


def test_facture_au_prefixe_et_au_client_du_point_de_vente():
    from mvogmbi_sync.facture import jours_facture, numero_facture, preparer_facture
    from mvogmbi_sync.models import LigneVente, RapportVentes
    from mvogmbi_sync.periodes import TypePeriode

    p2 = choisir(CONFIG, "2")[0]
    vendredi, dimanche = date(2026, 10, 23), date(2026, 10, 25)
    ligne = LigneVente("Fruits", "Mangue", D("2"), D("6.00"), id_article="M1")
    facture = preparer_facture(RapportVentes(vendredi, dimanche, "api", lignes=[ligne]), TypePeriode.FIN_DE_SEMAINE, p2)
    assert (facture.numero, facture.client, facture.depot) == ("V2 2026-10-23/25", "Vente Magasin 2", "Magasin 2")
    assert len(numero_facture(TypePeriode.MOIS, date(2026, 9, 1), prefixe="Vente")) <= 20
    assert jours_facture("V2 2026-10-23/25", "V2") == [vendredi, date(2026, 10, 24), dimanche]
    assert jours_facture("V2 2026-10-23/25") == []  # pas une facture du n° 1


def test_encaissement_sur_les_factures_du_point_de_vente():
    from mvogmbi_sync.encaissements import factures_fin_de_semaine, regrouper

    depots = regrouper({date(2026, 10, 22): D("100"), date(2026, 10, 23): D("50"), date(2026, 10, 25): D("30")}, "V2")
    factures_fin_de_semaine(depots, {"V2 2026-10-22", "V2 2026-10-23/25"}, "V2")
    assert [[l.facture for l in d.lignes] for d in depots] == [["V2 2026-10-22"], ["V2 2026-10-23/25"]]
    assert depots[1].lignes[0].montant == D("80")


def test_profil_limite_a_certains_points_de_vente(tmp_path):
    from mvogmbi_sync.utilisateurs import ADMIN, ErreurUtilisateur, Registre

    r = Registre(tmp_path)
    admin = r.ajouter("Patron", ADMIN, "secret123")
    caissier = r.ajouter("Caissier", "Employé", "secret123")
    assert r.points_vente_permis(caissier) is None  # sans réglage : tous
    r.definir_points_vente("Employé", ["2"])
    with pytest.raises(ErreurUtilisateur):
        r.definir_points_vente("Employé", [])
    with pytest.raises(ErreurUtilisateur):
        r.definir_points_vente(ADMIN, ["1"])
    r.enregistrer()
    relu = Registre(tmp_path)
    assert relu.points_vente_permis(relu.trouver("Caissier")) == {"2"}
    assert relu.points_vente_permis(relu.trouver("Patron")) is None
    relu.definir_points_vente("Employé", None)
    assert relu.points_vente_permis(relu.trouver("Caissier")) is None
    assert admin.est_admin
