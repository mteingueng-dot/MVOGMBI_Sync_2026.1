from datetime import date
from decimal import Decimal as D
from types import SimpleNamespace

from mvogmbi_sync import documents as dc
from mvogmbi_sync import pertes as pe


class CloverFactice:
    def __init__(self):
        self.stocks = {"I1": D("10"), "I2": D("4")}
        self.ecritures = []

    def stock(self, ident):
        return self.stocks[ident]

    def regler_stock(self, ident, quantite):
        self.ecritures.append((ident, quantite))
        self.stocks[ident] = quantite


def test_perte_cout_document_sage_et_stock_clover_une_seule_fois(tmp_path):
    articles = {"I1": {"id": "I1", "name": "Plantain", "cost": 150, "categories": {"elements": [{"name": "Fruits"}]}},
                "I2": {"id": "I2", "name": "Igname", "cost": 0}}
    liens = {"I1": "B0000190"}
    couts = {"B0000190": SimpleNamespace(cump=D("1.2000"))}
    l1 = pe.ligne(articles["I1"], D("3"), liens, couts)
    l2 = pe.ligne(articles["I2"], D("1"), liens, couts)
    assert (l1.source_cout, l1.valeur, l1.categorie) == ("CUMP Sage", D("3.60"), "Fruits")
    assert (l2.source_cout, l2.valeur, l2.numero_sage) == ("Coût inconnu", D("0.00"), "")
    registre = pe.Registre(tmp_path)
    p = pe.nouvelle(registre, "2026-10-29", "Périmé", [l1, l2], "Emplacement par défaut", "gérant")
    assert p.numero == "PE-0001"
    clover = CloverFactice()
    fait = pe.appliquer(tmp_path, {}, p.numero, client=clover)
    assert clover.stocks == {"I1": D("7"), "I2": D("3")}
    doc = dc.Registre(tmp_path).document(fait.document)
    assert doc.sens == dc.SORTIE and doc.depot == "Emplacement par défaut"
    assert [(l.numero_sage, l.quantite) for l in doc.lignes] == [("B0000190", "3")]  # seulement l'article relié
    pe.appliquer(tmp_path, {}, p.numero, client=clover)  # reprise : rien n'est refait
    assert len(clover.ecritures) == 2 and len(dc.Registre(tmp_path).documents) == 1


def test_rapport_et_taux(tmp_path):
    registre = pe.Registre(tmp_path)
    a = pe.LignePerte("I1", "Plantain", "3", "1.20", categorie="Fruits")
    b = pe.LignePerte("I2", "Riz", "1", "10", categorie="Riz")
    pe.nouvelle(registre, "2026-10-05", "Périmé", [a], auteur="x")
    pe.nouvelle(registre, "2026-10-20", "Vol ou disparition", [b], auteur="x")
    pe.nouvelle(registre, "2026-09-30", "Périmé", [b], auteur="x")  # hors période
    lignes, total = pe.rapport(registre.pertes, date(2026, 10, 1), date(2026, 10, 31), "motif")
    assert total == D("13.60") and [l[0] for l in lignes] == ["Vol ou disparition", "Périmé"]
    assert pe.taux(total, D("1360")) == "1,00 %" and pe.taux(total, D(0)) == "—"
