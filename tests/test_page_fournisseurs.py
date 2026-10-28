import tkinter as tk
from decimal import Decimal as D

import pytest

from mvogmbi_sync.fournisseurs import Facture, Ligne, Registre
from mvogmbi_sync.page_fournisseurs import PageFournisseurs


@pytest.fixture
def page(tmp_path, monkeypatch):
    try:
        racine = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"pas d'affichage : {exc}")
    monkeypatch.setattr(PageFournisseurs, "mettre_a_jour_sage", lambda self: None)
    registre = Registre(tmp_path)
    registre.factures.append(Facture("a.pdf", "e1", fournisseur_lu="Grossiste", numero="14402", date_facture="2026-10-27",
                                     lignes=[Ligne("Riz 25 lb", D(2), D("30"), D("60.00"))], total=D("60.00")))
    registre.factures.append(Facture("b.pdf", "e2", numero="9"))
    registre.enregistrer()
    p = PageFournisseurs(racine, tmp_path, "Essai")
    yield p, tmp_path
    racine.destroy()


def test_saisies_enregistrees_au_fur_et_a_mesure(page):
    p, racine = page
    p.liste.selection_set("0")
    p.choisir_facture()
    p.v["numero"].set("14402-B")  # en-tête : enregistré peu après la frappe
    p.sauvegarder_auto()
    assert Registre(racine).factures[0].numero == "14402-B"

    p.lignes.selection_set("0")
    p.choisir_ligne()
    p.l["quantite"].set("3")
    p.l["prix"].set("12,5,")  # erreur de frappe : rien n'est perdu ni signalé
    p.sauvegarder_auto()
    assert Registre(racine).factures[0].lignes[0].quantite == D(2)
    p.l["prix"].set("12,50")
    p.liste.selection_set("1")  # changer de facture garde la saisie de la précédente
    p.choisir_facture()
    ligne = Registre(racine).factures[0].lignes[0]
    assert (ligne.quantite, ligne.prix, ligne.montant) == (D(3), D("12.50"), D("37.50"))
    assert Registre(racine).factures[1].numero == "9"  # l'autre facture n'a pas reçu la saisie
