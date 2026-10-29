from decimal import Decimal

from mvogmbi_sync import bons_commande as bc
from mvogmbi_sync import taxes as tx
from mvogmbi_sync.fournisseurs import Facture, Ligne
from mvogmbi_sync.import_achats import bloc_achat
from mvogmbi_sync.import_sage import LigneImport
from mvogmbi_sync.previsions import VenteArticle


def test_codes_et_montants_de_taxe():
    assert tx.code({"taxable": True}) == "GQ" and tx.code({"taxable": False}) == ""
    assert tx.code({"taxe": "Q", "taxable": True}) == "Q"
    assert tx.montants(Decimal(100), "G") == (Decimal("5.00"), Decimal(0))
    assert tx.montants(Decimal(100), "Q") == (Decimal(0), Decimal("9.98"))
    assert tx.code_du_libelle("TVQ seulement") == "Q" and tx.code_du_libelle("Aucune") == ""
    assert [n for n, _a, _m in LigneImport("A", Decimal(1), Decimal(100), True, codes="G").taxes()] == ["TPS/TVH"]


def test_facture_achat_une_seule_taxe():
    f = Facture("f", "x", fournisseur_sage="F", numero="9", date_facture="2026-10-29", tps=Decimal("5.00"),
                tvq=Decimal("4.99"), total=Decimal("159.99"), lignes=[
                    Ligne("A", Decimal(1), Decimal(100), Decimal(100), numero_sage="A1", taxable=True, taxe="G"),
                    Ligne("B", Decimal(1), Decimal(50), Decimal(50), numero_sage="B1", taxable=True, taxe="Q")])
    lignes = bloc_achat(f)
    assert '"TPS/TVH","0","1","5.00","5.00"' in lignes[3] and "TVQ" not in lignes[3]
    assert '"TVQ","0","1","9.975","4.99"' in lignes[4] and "TPS" not in lignes[4]


def test_bon_en_unites_du_fournisseur():
    articles = [{"id": "A", "name": "Riz 5 kg", "itemStock": {"quantity": 0}}]
    ventes = {"A": VenteArticle("Riz", "", Decimal(25), Decimal(0))}
    achats = {"R1": {"fournisseur": "F", "prix": Decimal("12.50"), "date": "2026-10-01", "nom": "Riz"}}
    p = bc.proposer(ventes, articles, {"A": "R1"}, achats, {}, {("F", "R1"): Decimal(10)})[0]
    assert (p.quantite, p.prix, p.facteur) == (Decimal(3), Decimal("125.0000"), Decimal(10))  # 25 / 10 -> 3 caisses
    bon = bc.Bon("BC-1", "F", "2026-10-29", [bc.LigneBon("R1", "Riz", "3", "125", "375.00", "10")])
    facture = Facture("f", "x", fournisseur_sage="F", numero="1", date_facture="2026-10-30", lignes=[
        Ligne("Caisse riz", Decimal(3), Decimal(125), Decimal(375), numero_sage="R1", facteur=Decimal(10))])
    assert bc.comparer(bon, facture)[1]  # 30 unités Sage commandées et facturées au même prix
