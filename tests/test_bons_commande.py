from datetime import date
from decimal import Decimal

from mvogmbi_sync import bons_commande as bc
from mvogmbi_sync.fournisseurs import Facture, Ligne
from mvogmbi_sync.previsions import VenteArticle


def vente(q):
    return VenteArticle("x", "", Decimal(q), Decimal(0))


def test_proposer_regroupe_par_article_sage_et_dernier_achat():
    articles = [{"id": "A", "name": "Riz 5 kg", "itemStock": {"quantity": 2}},
                {"id": "B", "name": "Riz 5 kg promo", "itemStock": {"quantity": -3}},
                {"id": "C", "name": "Sel", "itemStock": {"quantity": 50}},
                {"id": "D", "name": "Huile", "itemStock": {"quantity": 0}},
                {"id": "E", "name": "Mil", "itemStock": {"quantity": 1}},
                {"id": "F", "name": "Sans suivi"}]
    ventes = {"A": vente("6.5"), "B": vente(4), "C": vente(10), "D": vente(3), "E": vente(2), "F": vente(9)}
    liens = {"A": "R001", "B": "R001", "C": "S001", "E": "M001"}
    achats = {"R001": {"fournisseur": "Fournisseur A", "prix": Decimal("12.5"), "date": "2026-10-01", "nom": "Riz"}}
    lignes = bc.proposer(ventes, articles, liens, achats, {"R001": "Riz 5 kg", "M001": "Mil 1 kg"})
    par = {p.numero_sage or p.articles_clover: p for p in lignes}
    riz = par["R001"]  # stock 2 − 3 = −1, vendu 10,5 : à commander 10,5 -> 11
    assert riz.quantite == 11 and riz.montant == Decimal("137.50") and riz.permis
    assert riz.articles_clover == "Riz 5 kg, Riz 5 kg promo"
    assert "S001" not in par and "Sans suivi" not in par    # stock suffisant ; stock non suivi
    assert par["M001"].etat == bc.SANS_FOURNISSEUR and not par["M001"].permis
    assert par["Huile"].etat == bc.SANS_LIEN
    assert lignes[0] is riz


def test_creer_bons_un_par_fournisseur(tmp_path, monkeypatch):
    monkeypatch.setattr(bc, "ecrire_pdf_bon", lambda racine, bon: tmp_path / f"{bon.numero}.pdf")
    p = [bc.Proposition("R001", "Riz", "Riz", Decimal(0), Decimal(5), Decimal(5), "A", Decimal(10)),
         bc.Proposition("S001", "Sel", "Sel", Decimal(0), Decimal(2), Decimal(2), "B", Decimal(3)),
         bc.Proposition("H001", "Huile", "Huile", Decimal(0), Decimal(2), Decimal(2), "A", Decimal("4.5")),
         bc.Proposition("", "Mil", "Mil", Decimal(0), Decimal(1), Decimal(1), etat=bc.SANS_LIEN)]
    bons = bc.creer_bons(tmp_path, p, date(2026, 10, 29))
    assert [(b.numero, b.fournisseur, b.total) for b in bons] == [("BC-0001", "A", Decimal("59.00")),
                                                                  ("BC-0002", "B", Decimal("6.00"))]
    assert [l.numero_sage for l in bons[0].lignes] == ["H001", "R001"]
    assert bc.Registre(tmp_path).prochain_numero() == "BC-0003"


def test_comparer_bon_et_facture():
    bon = bc.Bon("BC-0001", "A", "2026-10-29", [bc.LigneBon("R001", "Riz", "10", "12.5", "125.00"),
                                               bc.LigneBon("H001", "Huile", "4", "3", "12.00"),
                                               bc.LigneBon("S001", "Sel", "2", "1", "2.00")])
    facture = Facture("f.pdf", "x", fournisseur_sage="A", numero="99", date_facture="2026-10-30", lignes=[
        Ligne("Riz carton", Decimal(5), Decimal(25), Decimal(125), numero_sage="R001", facteur=Decimal(2)),
        Ligne("Huile", Decimal(4), Decimal("3.5"), Decimal(14), numero_sage="H001"),
        Ligne("Mil", Decimal(1), Decimal(7), Decimal(7), numero_sage="M001")])
    lignes, conforme = bc.comparer(bon, facture)
    assert [l[-1] for l in lignes] == ["Conforme", "Prix différent", "Non livré", "Non commandé"]
    assert not conforme and lignes[0][3] == 10
