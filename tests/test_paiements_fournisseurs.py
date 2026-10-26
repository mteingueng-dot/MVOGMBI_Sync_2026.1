from decimal import Decimal as D

from mvogmbi_sync.paiements_courriel import AvisPaiement
from mvogmbi_sync.paiements_fournisseurs import (A_RELIER, DEJA, PROPOSE, FactureOuverte, Paiement, proposer_fournisseur,
                                                 rapprocher, repartir)

# Noms inventés, à l'image des avis réels (aucune vraie donnée dans le dépôt public)
FOURNISSEURS = ["A.B.C Cash and Carry Inc.", "Abir Sherbrooke", "La Maison KOLA T.A. Fruits Inc.", "Les Aliments AL-ZED",
                "Marche AL-ZED", "QXT Transport", "Mer du Golfe inc."]


def test_proposition_du_fournisseur():
    assert proposer_fournisseur("A.B.C. PAYEZ-EMPORTEZ 3/A.B.C. C", FOURNISSEURS, {}) == "A.B.C Cash and Carry Inc."
    assert proposer_fournisseur("Khalid Kola Fruits", FOURNISSEURS, {}) == "La Maison KOLA T.A. Fruits Inc."
    assert proposer_fournisseur("AL-ZED FOODS INC. LES ALIMENTS", FOURNISSEURS, {}) == "Les Aliments AL-ZED"
    assert proposer_fournisseur("Rodrigue Exemple Transport", FOURNISSEURS, {}) == ""   # « transport » ne suffit pas
    assert proposer_fournisseur("JEAN EXEMPLE", FOURNISSEURS, {"jean exemple": "Mer du Golfe inc."}) == "Mer du Golfe inc."


def avis(montant, message, beneficiaire="AL-ZED FOODS INC. LES ALIMENTS", jour="2026-10-14"):
    return AvisPaiement("<id>", jour, jour, D(montant), beneficiaire, "REF", message)


def test_rapprochement_facture_et_deja_saisi():
    ouvertes = [FactureOuverte("Les Aliments AL-ZED", "FA-1264", "2026-09-30", D("812.80")),
                FactureOuverte("Les Aliments AL-ZED", "1346", "2026-10-10", D("1100.00"))]
    p = Paiement(avis("812.80", "Facture#1264"))
    rapprocher(p, FOURNISSEURS, {}, ouvertes, set())
    assert (p.etat, p.facture, p.remarque) == (PROPOSE, "FA-1264", "")
    sans_numero = Paiement(avis("1100.00", "merci"))
    rapprocher(sans_numero, FOURNISSEURS, {}, ouvertes, set())
    assert sans_numero.facture == "1346"                                     # seule facture au même montant
    deja = Paiement(avis("812.80", "Facture#1264"))
    rapprocher(deja, FOURNISSEURS, {}, ouvertes, {("Les Aliments AL-ZED", "2026-10-14", D("812.80"))})
    assert deja.etat == DEJA
    inconnu = Paiement(avis("50.00", "pret", beneficiaire="JEAN EXEMPLE"))
    rapprocher(inconnu, FOURNISSEURS, {}, ouvertes, set())
    assert inconnu.etat == A_RELIER


def test_repartition_sur_plusieurs_factures():
    a = FactureOuverte("Les Aliments AL-ZED", "1264", "2026-09-01", D("905.00"))
    b = FactureOuverte("Les Aliments AL-ZED", "FA-1346", "2026-09-20", D("210.00"))
    c = FactureOuverte("Les Aliments AL-ZED", "1400", "2026-10-01", D("50.00"))
    parts = repartir(D("910.00"), [c, b, a])                     # ordre de sélection quelconque : plus ancienne d'abord
    assert [(f.numero, m) for f, m in parts] == [("1264", D("905.00")), ("FA-1346", D("5.00"))]
    try:
        repartir(D("2000.00"), [a, b])
        assert False
    except ValueError:
        pass
    p = Paiement(avis("910.00", "Factures 1264, 1346"))
    rapprocher(p, FOURNISSEURS, {}, [a, b, c], set())
    assert p.etat == PROPOSE and p.facture == "1264 + FA-1346"
    assert p.lignes() == [("1264", D("905.00"), D("905.00")), ("FA-1346", D("5.00"), D("210.00"))]
    copie = Paiement.depuis_dict(p.en_dict())
    assert copie.lignes() == p.lignes()
