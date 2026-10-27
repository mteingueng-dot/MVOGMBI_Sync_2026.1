from datetime import date
from decimal import Decimal as D

from mvogmbi_sync import encaissements, rapprochement
from mvogmbi_sync.encaissements import A_SAISIR, APPLIQUE, A_VERIFIER, RegistreEncaissementsManuels, depots_manuels


def test_registre_remplace_le_meme_mouvement(tmp_path):
    r = RegistreEncaissementsManuels(tmp_path)
    r.ajouter("R1.pdf|4", date(2026, 2, 5), D("209.00"), "Vente 2026-02-04", "Interac JEAN EXEMPLE")
    r.ajouter("R1.pdf|4", date(2026, 2, 5), D("200.00"), "Vente 2026-02-05", "Interac JEAN EXEMPLE")
    r.enregistrer()
    relu = RegistreEncaissementsManuels(tmp_path)
    assert relu.cles() == {"R1.pdf|4"} and relu.trouver("R1.pdf|4")["facture"] == "Vente 2026-02-05"


def test_depots_manuels_a_saisir_puis_appliques(tmp_path, monkeypatch):
    r = RegistreEncaissementsManuels(tmp_path)
    r.ajouter("R1.pdf|4", date(2026, 2, 5), D("209.00"), "Vente 2026-02-04", "Interac JEAN EXEMPLE")
    r.ajouter("R1.pdf|9", date(2026, 2, 6), D("50.00"), "Vente 2026-01-31", "Dépôt d'espèces")
    r.enregistrer()
    etat = {"Vente 2026-02-04": {"du": D("500.00"), "recus": {}}}
    monkeypatch.setattr(rapprochement, "factures_ventes", lambda base, client: {"Vente 2026-02-04": date(2026, 2, 4)})
    monkeypatch.setattr(encaissements, "etat_factures_sage", lambda base, client, compte, factures: etat)
    depots = depots_manuels(tmp_path, None, "Vente Hebdomadaire", 10550000, date(2026, 2, 1), date(2026, 2, 28))
    assert [(d.etat, d.date, d.montant) for d in depots] == [(A_SAISIR, date(2026, 2, 5), D("209.00")),
                                                            (A_VERIFIER, date(2026, 2, 6), D("50.00"))]
    assert depots[0].origine == "Manuel — Interac JEAN EXEMPLE" and depots[0].lignes[0].montant_du == D("500.00")
    etat["Vente 2026-02-04"]["recus"] = {date(2026, 2, 5): [D("209.00")]}
    assert depots_manuels(tmp_path, None, "Vente Hebdomadaire", 10550000, date(2026, 2, 1),
                          date(2026, 2, 28))[0].etat == APPLIQUE
