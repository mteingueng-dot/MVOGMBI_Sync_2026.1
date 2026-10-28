from datetime import date
from decimal import Decimal as D

from mvogmbi_sync.api_clover import lignes_commande
from mvogmbi_sync.export_clover import montant
from mvogmbi_sync.models import LigneVente, cumuler
from mvogmbi_sync.periodes import TypePeriode, bornes, en_millisecondes


def test_montant_format_clover():
    assert montant("53\xa0972,17\xa0$") == D("53972.17")
    assert montant("-31,04\xa0$") == D("-31.04")
    assert montant("10544.14") == D("10544.14")
    assert montant("-") == D("0")
    assert montant(5) == D("5")


def test_bornes_periodes():
    jeudi = date(2026, 1, 15)
    assert bornes(TypePeriode.JOUR, jeudi) == (jeudi, jeudi)
    assert bornes(TypePeriode.SEMAINE, jeudi) == (date(2026, 1, 12), date(2026, 1, 18))
    assert bornes(TypePeriode.MOIS, jeudi) == (date(2026, 1, 1), date(2026, 1, 31))
    assert bornes(TypePeriode.MOIS, date(2028, 2, 10)) == (date(2028, 2, 1), date(2028, 2, 29))


def test_journee_en_heure_locale():
    t0, t1 = en_millisecondes(date(2026, 1, 15), date(2026, 1, 15), "America/Toronto")
    assert t1 - t0 == 24 * 3600 * 1000
    assert t0 == 1768453200000  # 2026-01-15 00:00 HNE (UTC-5)


def test_cumul_par_article():
    lignes = cumuler([
        LigneVente("Riz", "Riz 5kg", D("1"), ventes_brutes=D("10")),
        LigneVente("Riz", "Riz 5kg", D("2"), ventes_brutes=D("20"), rabais=D("-3")),
    ])
    assert len(lignes) == 1
    assert lignes[0].quantite_nette == D("3")
    assert lignes[0].ventes_nettes == D("27")
    assert lignes[0].prix_unitaire_net == D("9.0000")


def test_commande_clover_rabais_et_poids():
    commande = {
        "paymentState": "PAID",
        "lineItems": {"elements": [
            {"name": "Sardines Titus 125g", "price": 199, "item": {"id": "A"},
             "discounts": {"elements": [{"amount": -19}]}},
            {"name": "Viande de chèvre", "price": 1500, "unitQty": 1500, "item": {"id": "B"}},
        ]},
        "discounts": {"elements": [{"percentage": 10}]},
    }
    lignes = lignes_commande(commande, {"A": "Divers", "B": "Viandes & Volailles"})
    sardines, chevre = lignes
    assert sardines.ventes_brutes == D("1.99") and chevre.ventes_brutes == D("22.50")
    assert chevre.quantite_vendue == D("1.5")
    # 10 % de (1.80 + 22.50) = 2.43, réparti au prorata
    assert sardines.rabais + chevre.rabais == D("-0.19") + D("-2.43")
    assert sardines.categorie == "Divers"


def test_commande_non_payee_ignoree():
    assert lignes_commande({"paymentState": "OPEN", "lineItems": {"elements": [{"price": 100}]}}, {}) == []


def test_commande_payee_malgre_paymentstate_open():
    commande = {
        "paymentState": "OPEN", "state": "locked",
        "payments": {"elements": [{"result": "SUCCESS", "amount": 100}]},
        "lineItems": {"elements": [{"name": "Milo 400g", "price": 799}]},
    }
    assert lignes_commande(commande, {})[0].ventes_brutes == D("7.99")


def test_comparaison_detecte_les_ecarts():
    from mvogmbi_sync.comparaison import comparer
    from mvogmbi_sync.models import RapportVentes

    j = date(2026, 10, 23)
    export = RapportVentes(j, j, "export", [
        LigneVente("Riz", "Riz 5kg", D("2"), ventes_brutes=D("20")),
        LigneVente("Divers", "Milo 400g", D("1"), ventes_brutes=D("7.99")),
    ])
    api = RapportVentes(j, j, "api", [
        LigneVente("Non catégorisé(e)", "riz  5KG", D("2"), ventes_brutes=D("20")),
        LigneVente("Divers", "Milo 400g", D("1"), ventes_brutes=D("7.99"), rabais=D("-0.80")),
    ])
    ecarts = comparer(export, api)
    assert [e.nom for e in ecarts] == ["Milo 400g"]


def test_lecture_export_csv(tmp_path):
    from mvogmbi_sync.export_clover import lire_export

    contenu = (
        "\ufeffVentes d'articles\r\n"
        '"ven. 23 oct. 2026, 00 h 00  - ven. 23 oct. 2026, 23 h 59 "\r\n'
        "\r\n"
        "Catégorie,Catégorie / Article,Ventes brutes,Ventes nettes,Nom du modificateur,"
        "Qté de modificateurs vendus,Ventes brutes de modificateurs,Vendu(e),Rabais,Remboursements\r\n"
        'Total,,"60,92 $","49,93 $",,0,"0,00 $",12,"0,00 $","-10,99 $"\r\n'
        'Mèches & Accessoires,,"54,95 $","43,96 $",,0,"0,00 $",5,"0,00 $","-10,99 $"\r\n'
        ',MECHE X-PRESSION,"54,95 $","43,96 $",,0,"0,00 $",5,"0,00 $","-10,99 $"\r\n'
        'Fruits & Légumes,,"5,97 $","5,97 $",,0,"0,00 $",7,"0,00 $","0,00 $"\r\n'
        ',Tomates en lb,"5,97 $","5,97 $",,0,"0,00 $",3.00,"0,00 $","0,00 $"\r\n'
    ).replace("$", "\xa0$")
    fichier = tmp_path / "ventes.csv"
    fichier.write_text(contenu, encoding="utf-8", newline="")
    rapport = lire_export(fichier)
    assert (rapport.debut, rapport.fin) == (date(2026, 10, 23), date(2026, 10, 23))
    assert {l.nom: l.categorie for l in rapport.lignes} == {
        "MECHE X-PRESSION": "Mèches & Accessoires", "Tomates en lb": "Fruits & Légumes"}
    assert rapport.total_net == D("49.93")


def test_rabais_commande_arrondi_au_cent():
    commande = {
        "payments": {"elements": [{"result": "SUCCESS"}]},
        "lineItems": {"elements": [{"name": "Igname en lb", "price": 399, "unitQty": 11005}]},
        "discounts": {"elements": [{"percentage": 11.45}]},
    }
    (igname,) = lignes_commande(commande, {})
    assert igname.rabais == igname.rabais.quantize(D("0.01"))


def test_rabais_pourcentages_additionnes_comme_clover():
    # Commande du 17 oct. 2026 : « Direction » 99 % + 10 % -> total 0 $ dans Clover
    commande = {
        "payments": {"elements": [{"result": "SUCCESS", "amount": 0}]},
        "lineItems": {"elements": [
            {"name": "Creme Lissante ORS", "price": 1499},
            {"name": "Gombo en lb", "price": 525, "unitQty": 1935},
        ]},
        "discounts": {"elements": [{"percentage": 99}, {"percentage": 10}]},
    }
    creme, gombo = lignes_commande(commande, {})
    assert (creme.ventes_nettes, gombo.ventes_nettes) == (D("0"), D("0"))


def test_rabais_successifs_ne_depassent_pas_le_montant():
    commande = {
        "payments": {"elements": [{"result": "SUCCESS", "amount": 0}]},
        "lineItems": {"elements": [{"name": "Robb", "price": 299}]},
        "discounts": {"elements": [{"percentage": 100}, {"percentage": 99}]},
    }
    (robb,) = lignes_commande(commande, {})
    assert robb.ventes_nettes == D("0")


def test_vente_datee_au_paiement():
    from mvogmbi_sync.api_clover import moment_paiement

    commande = {"createdTime": 100, "payments": {"elements": [
        {"result": "FAIL", "createdTime": 150}, {"result": "SUCCESS", "createdTime": 300}]}}
    assert moment_paiement(commande) == 300
    assert moment_paiement({"createdTime": 100, "paymentState": "OPEN"}) is None


def test_facture_montant_net_et_prix_unitaire():
    from mvogmbi_sync.facture import preparer_facture
    from mvogmbi_sync.models import RapportVentes

    j = date(2026, 10, 19)
    rapport = RapportVentes(j, j, "api", [
        # Sardines : 11 x 4.49 = 49.39 $ brut, rabais -24.75 $ -> net 24.64 $
        LigneVente("Divers", "Sada sardines", D("11"), ventes_brutes=D("49.39"), rabais=D("-24.75")),
        # Mèche : 9 vendues, 1 remboursée
        LigneVente("Mèches", "MECHE X", D("9"), D("1"), ventes_brutes=D("98.91"), remboursements=D("-10.99")),
        LigneVente("Fruits", "Gombo en lb", D("3.835"), ventes_brutes=D("20.14")),
        LigneVente("Non catégorisé(e)", "Robb", D("1"), ventes_brutes=D("2.99"), rabais=D("-2.99")),
    ])
    facture = preparer_facture(rapport, TypePeriode.JOUR)
    lignes = {l.nom: l for l in facture.lignes}
    assert lignes["Sada sardines"].montant == D("24.64")
    assert lignes["Sada sardines"].prix_unitaire == D("2.2400")
    assert (lignes["MECHE X"].quantite, lignes["MECHE X"].prix_unitaire) == (D("8.000"), D("10.9900"))
    assert lignes["Gombo en lb"].quantite == D("3.835")
    assert lignes["Gombo en lb"].prix_unitaire == D("5.2516")
    assert lignes["Robb"].prix_unitaire == D("0")
    assert facture.total == rapport.total_net
    assert all(abs(l.ecart_arrondi) <= D("0.01") for l in facture.lignes)


def test_facture_signale_montant_sans_quantite():
    from mvogmbi_sync.facture import preparer_facture
    from mvogmbi_sync.models import RapportVentes

    j = date(2026, 10, 19)
    rapport = RapportVentes(j, j, "api", [LigneVente("X", "Remb. ancien", D("1"), D("1"), ventes_brutes=D("5"))])
    facture = preparer_facture(rapport, TypePeriode.JOUR)
    assert facture.lignes == [] and len(facture.anomalies) == 1


def test_numeros_de_facture():
    from mvogmbi_sync.facture import numero_facture

    assert numero_facture(TypePeriode.JOUR, date(2026, 10, 23)) == "Vente 2026-10-23"
    assert numero_facture(TypePeriode.SEMAINE, date(2026, 10, 19)) == "Vente S43-2026"
    assert numero_facture(TypePeriode.MOIS, date(2026, 10, 1)) == "Vente Octobre 2026"


def test_facture_code_taxe_et_taxes():
    from mvogmbi_sync.facture import preparer_facture
    from mvogmbi_sync.models import RapportVentes

    j = date(2026, 10, 23)
    rapport = RapportVentes(j, j, "api", [
        LigneVente("Mèches", "MECHE AFRO KINKY CURLY 1B", D("1"), ventes_brutes=D("899.00"), taxable=True),
        LigneVente("Riz", "Riz 5kg", D("1"), ventes_brutes=D("20.00"), taxable=False),
    ])
    facture = preparer_facture(rapport, TypePeriode.JOUR)
    codes = {l.nom: l.code_taxe for l in facture.lignes}
    assert codes == {"MECHE AFRO KINKY CURLY 1B": "GQ", "Riz 5kg": ""}
    # Mêmes montants que la facture Sage de démonstration : TPS 44,95 $, TVQ 89,68 $
    assert (facture.tps, facture.tvq) == (D("44.95"), D("89.68"))
    assert facture.sous_total == D("919.00") and facture.total == D("1053.63")
    assert (facture.client, facture.mode_paiement) == ("Vente Hebdomadaire", "Payer plus tard")


def test_cumul_separe_taxable_et_non_taxable():
    lignes = cumuler([
        LigneVente("Divers", "Savon", D("1"), ventes_brutes=D("5"), taxable=True),
        LigneVente("Divers", "Savon", D("1"), ventes_brutes=D("5"), taxable=False),
    ])
    assert len(lignes) == 2


def test_article_non_recette_signale():
    from mvogmbi_sync.api_clover import lignes_hors_recettes
    from mvogmbi_sync.facture import preparer_facture
    from mvogmbi_sync.models import RapportVentes

    commande = {
        "payments": {"elements": [{"result": "SUCCESS"}]},
        "lineItems": {"elements": [
            {"name": "Colombina Bon Bon Bum Fresa 408g", "price": 399, "isRevenue": False},
            {"name": "Plantain Jaune en lb", "price": 129},
        ]},
    }
    assert [l.nom for l in lignes_commande(commande, {})] == ["Plantain Jaune en lb"]
    hors = lignes_hors_recettes(commande, {})
    assert [(l.nom, l.ventes_brutes) for l in hors] == [("Colombina Bon Bon Bum Fresa 408g", D("3.99"))]
    j = date(2026, 10, 19)
    facture = preparer_facture(RapportVentes(j, j, "api", hors_recettes=hors), TypePeriode.JOUR)
    # Avertissement seulement : Clover exclut lui-même cet article de ses ventes, la facture reste exacte.
    assert facture.anomalies == [] and "non-recette" in facture.avertissements[0]


def test_non_recette_article_corrige_depuis():
    from mvogmbi_sync.api_clover import lignes_hors_recettes
    from mvogmbi_sync.facture import preparer_facture
    from mvogmbi_sync.models import RapportVentes

    commande = {
        "payments": {"elements": [{"result": "SUCCESS"}]},
        "lineItems": {"elements": [
            {"name": "Colombina Bon Bon Bum Fresa 408g", "price": 399, "isRevenue": False, "item": {"id": "T1"}},
        ]},
    }
    # règle gardée : toujours non facturé, même si l'article est aujourd'hui une recette dans Clover
    assert lignes_commande(commande, {}) == []
    hors = lignes_hors_recettes(commande, {})
    j = date(2026, 5, 31)
    facture = preparer_facture(RapportVentes(j, j, "api", hors_recettes=hors, recettes_actuelles={"T1"}),
                               TypePeriode.JOUR)
    assert facture.lignes == [] and facture.avertissements == []
