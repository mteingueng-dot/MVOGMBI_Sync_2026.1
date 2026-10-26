from datetime import date
from decimal import Decimal as D

from mvogmbi_sync.automatique import CompteRendu
from mvogmbi_sync.courriel import sujet_compte_rendu
from mvogmbi_sync.robot_paiements import payer


class FenetreFactice:
    """Remplace la fenêtre Paiements de Sage : note les saisies, total = dernier montant tapé."""

    def __init__(self):
        self.saisies, self.montant, self.traitee = [], D(0), False

    def choisir(self, ident, valeur):
        return valeur

    def regler_date(self, jour):
        self.jour = jour

    def saisir_ligne(self, ligne, montant):
        self.saisies.append((ligne, montant))
        self.montant = montant

    def total(self):
        return self.montant

    def traiter(self, resultat):
        self.traitee = True
        return True

    def effacer(self, fournisseur):
        pass


ORDRE = ["NC-1", "A1", "A2"]  # note de crédit comprise : elle occupe une ligne de la grille


def test_paiement_partiel_sur_la_bonne_ligne():
    f = FenetreFactice()
    r = payer(f, "Fournisseur", "A2", D("10.00"), date(2026, 10, 20), ORDRE, D("210.00"), "1055")
    assert r.traite and f.saisies == [(2, D("10.00"))] and f.jour == "2026-10-20"


def test_refus_si_plus_que_le_solde_ou_facture_absente():
    f = FenetreFactice()
    assert not payer(f, "Fournisseur", "A2", D("215.00"), date(2026, 10, 20), ORDRE, D("210.00"), "1055").traite
    assert not payer(f, "Fournisseur", "A9", D("5.00"), date(2026, 10, 20), ORDRE, D("210.00"), "1055").traite
    assert f.saisies == [] and not f.traitee


def test_sujet_du_courriel_avec_paiements():
    cr = CompteRendu(seulement_paiements=True)
    cr.paiements = ["2026-10-20 : 10,00 $ à Fournisseur, facture A2"]
    assert "1 paiement(s) fournisseur(s) saisi(s)" in sujet_compte_rendu(cr)
