from decimal import Decimal

from mvogmbi_sync import prix_marges as pm
from mvogmbi_sync.couts_sage import CoutSage
from mvogmbi_sync.previsions import VenteArticle


def test_arrondir():
    assert pm.arrondir(Decimal("7.12"), ",49 / ,99") == Decimal("7.49")
    assert pm.arrondir(Decimal("7.60"), ",49 / ,99") == Decimal("7.99")
    assert pm.arrondir(Decimal("7.995"), ",49 / ,99") == Decimal("8.49")
    assert pm.arrondir(Decimal("7.12"), ",99") == Decimal("7.99")
    assert pm.arrondir(Decimal("7.121"), "Au cent") == Decimal("7.13")


def cout(n, c):
    return CoutSage(n, n, Decimal(c), Decimal(1), Decimal(c))


def test_analyser_etats_et_prix_propose():
    articles = [
        {"id": "A", "name": "Pâte 3 kg", "price": 2499, "cost": 1000},   # CUMP 22 : marge 12 % -> 29,49
        {"id": "B", "name": "Safou", "price": 2851},                     # CUMP 20 : 30 % -> correct
        {"id": "C", "name": "Jus", "price": 699},                        # CUMP 6,87 -> 9,49 : hausse > 30 %
        {"id": "D", "name": "Plantain", "price": 128},                   # CUMP aberrant
        {"id": "E", "name": "Divers", "price": 0, "priceType": "VARIABLE"},
        {"id": "F", "name": "Sel", "price": 199, "cost": 180},           # pas de lien : coût Clover
        {"id": "G", "name": "Sans coût", "price": 500},                  # non vendu : écarté
    ]
    liens = {"A": "P1", "B": "S1", "C": "J1", "D": "B190", "E": "X1"}
    couts = {"P1": cout("P1", 22), "S1": cout("S1", 20), "J1": cout("J1", "6.87"), "B190": cout("B190", 900)}
    ventes = {"A": VenteArticle("Pâte", "", Decimal(10), Decimal(250)), "E": VenteArticle("Divers", "", Decimal(1),
                                                                                         Decimal(5))}
    lignes, correctes = pm.analyser(articles, liens, couts, ventes, 25, ",49 / ,99")
    par = {l.id_clover: l for l in lignes}
    assert correctes == 1 and "B" not in par and "G" not in par
    assert par["A"].nouveau == Decimal("29.49") and par["A"].etat == pm.SOUS_MARGE and par["A"].marge == Decimal("12.0")
    assert par["A"].effet == Decimal("45.00") and par["A"].cochee_par_defaut
    assert par["C"].etat == pm.A_VERIFIER and par["C"].permis and not par["C"].cochee_par_defaut
    assert par["D"].etat == pm.ABERRANT and not par["D"].permis
    assert par["E"].etat == pm.VARIABLE
    assert par["F"].source_cout == "Coût Clover" and par["F"].nouveau == Decimal("2.49")
    assert lignes[0].id_clover == "A"
