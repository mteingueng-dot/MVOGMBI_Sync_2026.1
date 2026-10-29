from datetime import datetime
from decimal import Decimal

import pytest

from mvogmbi_sync import bons_commande as bc
from mvogmbi_sync import documents as dc
from mvogmbi_sync import paie_temps as pt
from mvogmbi_sync.utilisateurs import ADMIN, ErreurUtilisateur, Registre, Utilisateur


def test_fonctions_refusees_par_profil(tmp_path):
    r = Registre(tmp_path)
    r.definir_fonctions("Comptable", ["Prix et marges", "Saisir une facture de vente"])
    r.enregistrer()
    relu = Registre(tmp_path)
    comptable = Utilisateur("Paul", "Comptable", "", "")
    admin = Utilisateur("Admin", ADMIN, "", "")
    assert relu.refusees(comptable) == {"Prix et marges", "Saisir une facture de vente"}
    assert relu.refusees(admin) == set()
    with pytest.raises(ErreurUtilisateur):
        relu.definir_fonctions(ADMIN, ["Prix et marges"])


def test_documents_modifier_supprimer(tmp_path):
    r = dc.Registre(tmp_path)
    cmd = r.ajouter(dc.COMMANDE, "Client A", "2026-10-29", [dc.LigneDocument("A1", "Riz", "2", "10")])
    r.modifier(cmd.numero, "Client B", "2026-10-30", [dc.LigneDocument("A1", "Riz", "3", "10")], "urgent")
    relu = dc.Registre(tmp_path).document(cmd.numero)
    assert (relu.tiers, relu.sous_total, relu.remarque) == ("Client B", Decimal(30), "urgent")
    facture = dc.Registre(tmp_path).facturer(cmd.numero)
    with pytest.raises(ValueError):  # commande facturée : figée
        dc.Registre(tmp_path).modifier(cmd.numero, "Client B", "2026-10-30", [dc.LigneDocument("A1", "Riz", "1", "1")])
    dc.Registre(tmp_path).supprimer(facture.numero)  # facture pas encore dans Sage : la commande se rouvre
    relu = dc.Registre(tmp_path)
    assert relu.document(cmd.numero).etat == dc.OUVERTE and not relu.document(cmd.numero).lien
    f2 = relu.ajouter(dc.FACTURE, "Client A", "2026-10-29", [dc.LigneDocument("A1", "Riz", "1", "1")])
    f2.etat = dc.IMPORTEE
    relu.enregistrer()
    with pytest.raises(ValueError):
        dc.Registre(tmp_path).supprimer(f2.numero)


def test_bons_et_employes(tmp_path, monkeypatch):
    monkeypatch.setattr(bc, "ecrire_pdf_bon", lambda racine, bon: tmp_path / f"{bon.numero}.pdf")
    bon = bc.creer_bons(tmp_path, [bc.Proposition("R1", "Riz", "", Decimal(0), Decimal(0), Decimal(2), "A",
                                                  Decimal(5))])[0]
    bc.modifier_bon(tmp_path, bon.numero, "B", "2026-11-01", [bc.LigneBon("S1", "Sel", "4", "1", "4.00")])
    relu = bc.Registre(tmp_path).bons[0]
    assert (relu.fournisseur, relu.total) == ("B", Decimal(4))
    bc.supprimer_bon(tmp_path, bon.numero)
    assert bc.Registre(tmp_path).bons == []
    r = pt.Registre(tmp_path)
    a, b = r.ajouter("Employé A"), r.ajouter("Employé B")
    r.renommer(a.id, "Employé A2")
    with pytest.raises(pt.ErreurPointage):
        r.renommer(b.id, "employé a2")
    r.pointer(a.id, pt.ARRIVEE, datetime(2026, 10, 29, 8))
    with pytest.raises(pt.ErreurPointage):
        r.supprimer(a.id)  # a pointé : à désactiver
    r.supprimer(b.id)
    assert [e.nom for e in r.employes] == ["Employé A2"]
