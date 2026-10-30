from datetime import date
from decimal import Decimal as D

from mvogmbi_sync import bons_commande as bc
from mvogmbi_sync import depenses as dp
from mvogmbi_sync import langues
from mvogmbi_sync import pertes as pe
from mvogmbi_sync import rapports_gestion as rg
from mvogmbi_sync import retours as rt

DU, AU = date(2026, 10, 1), date(2026, 10, 31)


def test_evolution_par_jour_puis_par_mois():
    etiquettes, valeurs = rg.evolution({date(2026, 10, 2): D(5)}, date(2026, 10, 1), date(2026, 10, 3))
    assert etiquettes == ["01/10", "02/10", "03/10"] and valeurs == [0, D(5), 0]
    etiquettes, valeurs = rg.evolution({date(2026, 8, 3): D(2), date(2026, 8, 20): D(3), date(2026, 10, 1): D(4)},
                                       date(2026, 7, 1), date(2026, 10, 31))
    assert etiquettes == ["07/2026", "08/2026", "09/2026", "10/2026"] and valeurs == [0, D(5), 0, D(4)]


def test_rapports_des_registres(tmp_path):
    (tmp_path / "donnees").mkdir()
    registre = pe.Registre(tmp_path)
    pe.nouvelle(registre, "2026-10-06", "Périmé", [pe.LignePerte("i1", "Riz", "2", "1.50", categorie="Riz")])
    pe.nouvelle(registre, "2026-11-02", "Vol ou disparition", [pe.LignePerte("i2", "Huile", "1", "9.00")])  # hors période
    r = rg.calculer("g_pertes", tmp_path, DU, AU, {"ventes_par_jour": {date(2026, 10, 6): D("300")}})
    assert dict((c[0], c[2]) for c in r.cartes)["Valeur des pertes"] == D("3.00")
    assert dict((c[0], c[2]) for c in r.cartes)["Part des ventes nettes"] == D("1.0")
    assert r.repartition == [("Périmé", D("3.00"))] and len(r.lignes) == 1 and len(r.etiquettes) == 31

    depenses = dp.Registre(tmp_path)
    depenses.ajouter(dp.Depense("", "2026-10-05", "Quincaillerie", "Ampoules", "11.50", "GQ", "5700", dp.PETITE_CAISSE))
    r = rg.calculer("g_depenses", tmp_path, DU, AU, {})
    cartes = dict((c[0], c[2]) for c in r.cartes)
    assert cartes["Dépenses (taxes comprises)"] == D("11.50") and cartes["Taxes à récupérer"] == D("1.50")
    assert r.repartition == [("5700", D("10.00"))]

    rt.Registre(tmp_path).ajouter("Fournisseur A", "F-1", "2026-10-08", [rt.LigneRetour("A1", "Article", "2", "1.25")])
    r = rg.calculer("g_retours", tmp_path, DU, AU, {})
    assert dict((c[0], c[2]) for c in r.cartes)["Montant des retours"] == D("2.50")

    bons = bc.Registre(tmp_path)
    bons.bons.append(bc.Bon("BC-0001", "Fournisseur A", "2026-10-09", [bc.LigneBon("A1", "Article", "2", "3", "6.00")]))
    bons.enregistrer()
    r = rg.calculer("g_bons", tmp_path, DU, AU, {})
    cartes = dict((c[0], c[2]) for c in r.cartes)
    assert cartes["Montant commandé"] == D("6.00") and cartes["En attente"] == 1

    r = rg.calculer("g_caisse", tmp_path, DU, AU, {})  # sans ventes Clover lues : expliqué, pas d'erreur
    assert r.note and not r.lignes
    for _libelle, cle, _f in rg.ETATS:  # chaque rapport se calcule, même sans donnée
        rg.calculer(cle, tmp_path, DU, AU, {"config": {}})


def test_textes_des_rapports_traduits():
    assert [x for x in rg.TEXTES if x not in langues.EN] == []
    assert {l for l, _c, _f in rg.ETATS} <= set(rg.TEXTES)
