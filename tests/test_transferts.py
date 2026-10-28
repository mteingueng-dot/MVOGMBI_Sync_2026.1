from decimal import Decimal as D

import pytest

from mvogmbi_sync import transferts as tr
from mvogmbi_sync.points_vente import PointDeVente
from mvogmbi_sync.robot_transferts import lots

POINTS = {"1": PointDeVente("1", "Principal", "M1"), "2": PointDeVente("2", "Magasin 2", "M2", "Vente M2", "Magasin 2",
                                                                         "V2")}


def transfert(**k):
    return tr.Transfert("TR-0001", "2026-10-28", "1", "2", [tr.LigneTransfert("C1", "Riz", D(3))], **k)


def test_controles_du_transfert():
    assert transfert().problemes(POINTS) == []
    t = transfert()
    t.vers = "1"
    assert t.problemes(POINTS) == ["le point de vente d'arrivée doit être différent du départ"]
    t = transfert()
    t.lignes = [tr.LigneTransfert("C1", "Riz", D(0))]
    assert t.problemes(POINTS) == ["C1 : quantité à transférer > 0"]
    meme_depot = {**POINTS, "2": PointDeVente("2", "Magasin 2", "M2", depot_sage="Emplacement par défaut")}
    assert transfert().problemes(meme_depot) == ["les deux points de vente ont le même dépôt Sage"]


def test_registre_numeros_et_suppression(tmp_path):
    r = tr.Registre(tmp_path)
    assert r.nouveau_numero() == "TR-0001"
    r.garder(transfert())
    r = tr.Registre(tmp_path)
    assert r.nouveau_numero() == "TR-0002" and r.trouver("TR-0001").lignes[0].quantite == D(3)
    t = r.trouver("TR-0001")
    t.sage = True
    r.garder(t)
    with pytest.raises(ValueError):  # déjà fait dans Sage : jamais supprimé
        r.supprimer("TR-0001")


class FauxClover:
    def __init__(self, stocks):
        self.stocks = stocks

    def stock(self, i):
        return self.stocks[i]

    def regler_stock(self, i, q):
        self.stocks[i] = q


def test_stock_clover_depart_et_arrivee_une_seule_fois():
    t = transfert()
    t.lignes.append(tr.LigneTransfert("C2", "Huile", D(1)))
    clients = {"1": FauxClover({"a1": D(10)}), "2": FauxClover({"b1": D(-2), "b2": D(0), "b3": D(0)})}
    liens = {"1": {"C1": ["a1"]}, "2": {"C1": ["b1"], "C2": ["b2", "b3"]}}
    messages = tr.appliquer_clover(t, clients, liens)
    assert clients["1"].stocks["a1"] == D(7) and clients["2"].stocks["b1"] == D(1)
    assert messages == ["Clover 1 : C2 non relié — stock à corriger à la main",
                        "Clover 2 : C2 relié à plusieurs articles — stock à corriger à la main"]
    assert not tr.faits_clover(t)
    tr.appliquer_clover(t, clients, liens)  # reprise : C1 n'est jamais refait
    assert clients["1"].stocks["a1"] == D(7) and clients["2"].stocks["b1"] == D(1)


def test_lots_de_sept_lignes():
    l = lots("TR-0001", [(f"C{i}", D(1)) for i in range(9)])
    assert [(x.source, len(x.lignes)) for x in l] == [("TR-0001", 7), ("TR-0001-2", 2)]
