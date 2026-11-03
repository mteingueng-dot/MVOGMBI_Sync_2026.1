from datetime import date
from decimal import Decimal as D

import pytest

from mvogmbi_sync import ria
from mvogmbi_sync.encaissements import A_RIA, A_SAISIR, APPLIQUE, Depot, repartir_especes
from mvogmbi_sync.rapprochement import A_ENCAISSER, MouvementBanque

ESPECES = "DGA Dépôt au GA / CDS CARREFOUR DE L'ESTRIE"


def banque(jour, montant, description, rang=0):
    return MouvementBanque(jour, description, D(montant), releve="R.pdf", rang=rang)


def depot(jour, montant, rang=0):
    m = banque(jour, montant, ESPECES, rang)
    m.etat = A_ENCAISSER
    return m


FACTURES = {"Vente 2026-10-19": date(2026, 10, 19), "Vente 2026-10-20": date(2026, 10, 20)}
DUS = {"Vente 2026-10-19": D("200.00"), "Vente 2026-10-20": D("300.00")}


def test_depot_cumule_sur_plusieurs_jours_sans_surplus():
    d = repartir_especes([depot("2026-10-21", "500.00")], FACTURES, DUS, [])[0]
    assert d.etat == A_SAISIR and d.ria == 0
    assert [(l.facture, l.montant) for l in d.lignes] == [("Vente 2026-10-19", D("200.00")),
                                                          ("Vente 2026-10-20", D("300.00"))]


def test_surplus_attend_la_confirmation_puis_le_reste_s_encaisse():
    m = depot("2026-10-21", "1500.00")
    d = repartir_especes([m], FACTURES, DUS, [])[0]
    assert d.etat == A_RIA and d.ria == D("1000.00")  # rien à encaisser avant la confirmation
    assert not [l for l in d.lignes if l.etat == A_SAISIR]
    d = repartir_especes([m], FACTURES, DUS, [], {m.cle: D("1000.00")})[0]
    assert d.etat == A_SAISIR and d.ria == 0 and d.montant == D("500.00")


def test_depot_entierement_pour_ria():
    m = depot("2026-10-21", "400.00")
    d = repartir_especes([m], FACTURES, DUS, [], {m.cle: D("400.00")})[0]
    assert d.etat == APPLIQUE and d.ria == 0


def test_reconnaissance_des_mouvements_ria():
    assert ria.est_ria(banque("2026-10-01", "100", "DI Dépôt direct / RIA TELECOMMINICATIONS OF CANA"))
    assert not ria.est_ria(banque("2026-10-01", "-0.01", "DT Fonds manquants RIA"))
    assert not ria.est_ria(banque("2026-10-01", "100", "VARIATION DE PRIX"))
    assert ria.genre(banque("2026-10-01", "-100", "RA Retrait direct entreprise / RIA")) == ria.RETRAIT
    assert ria.genre(banque("2026-10-01", "-100", "VNW Virement Interac à / Paiement RIA")) == ria.INTERAC
    m = banque("2026-10-01", "100", "DI Dépôt direct / RIA")
    assert ria.genre(m) == ria.DEPOT and ria.genre(m, [m.cle]) == ria.COMMISSION


def test_registre_operations_et_ecritures(tmp_path):
    r = ria.Registre(tmp_path)
    assert "Compte RIA (bilan)" in r.comptes_manquants()
    r.comptes.update(ria="2600", commissions="4100")
    o = r.ajouter("2026-10-21", ria.SURPLUS, D("1000.00"), "dépôt", "R.pdf|0")
    p = r.ajouter("2026-10-22", ria.ESPECES, D("200.00"))
    assert (o.numero, p.numero) == ("RI-0001", "RI-0002")
    with pytest.raises(ValueError):
        r.ajouter("2026-10-21", ria.SURPLUS, D("5.00"), "", "R.pdf|0")  # un dépôt ne se partage qu'une fois
    r.enregistrer()
    r = ria.Registre(tmp_path)
    assert r.parts_depots() == {"R.pdf|0": D("1000.00")}
    surplus, especes = r.mouvements_a_saisir()
    assert (surplus.montant, surplus.compte, surplus.source_sage) == (D("1000.00"), "2600", "RI-0001")
    assert especes.montant == D("-200.00") and especes.compte_contre == "1050"  # Dr RIA / Cr espèces
    especes.sage = [77]
    r.noter_saisie(especes, True)
    assert r.operations[1].etat == ria.SAISIE and r.operations[1].ecriture == 77
    with pytest.raises(ValueError):
        r.supprimer("RI-0002")
    assert len(r.mouvements_a_saisir()) == 1


def test_bilan_entrees_et_sorties_s_annulent(tmp_path):
    r = ria.Registre(tmp_path)
    r.ajouter("2026-10-21", ria.SURPLUS, D("1000.00"))
    retrait = banque("2026-10-23", "-1000.00", "RA Retrait direct entreprise / RIA")
    paiement = banque("2026-10-24", "-300.00", "VNW Virement Interac à / Paiement RIA", 1)
    verse = banque("2026-10-25", "300.00", "DI Dépôt direct / RIA", 2)
    commission = banque("2026-10-31", "85.00", "DI Dépôt direct / RIA", 3)
    r.commissions.append(commission.cle)
    attendu = Depot(date(2026, 10, 22), ria=D("50.00"), remarque="surplus")
    lignes, bilan = r.lignes([retrait, paiement, verse, commission], [attendu], date(2026, 10, 1), date(2026, 10, 31))
    assert bilan.commissions == D("85.00") and bilan.solde == D("50.00")
    assert lignes[0]["date"] == "2026-10-31" and len(lignes) == 6
