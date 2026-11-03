"""Chaîne des documents de vente et d'achat (demande du propriétaire du 2026-11-01)."""
from datetime import date
from decimal import Decimal as D

import pytest

from mvogmbi_sync import bons_commande as bc
from mvogmbi_sync import documents as dc
from mvogmbi_sync.chaine_documents import annuler_stock, transformer_achat


def ligne(n="C0001", q="2", p="3.50"):
    return dc.LigneDocument(n, "Riz", q, p, taxe="GQ", taxable=True)


def test_vente_bc_bl_fa_rc_frc_et_tracabilite(tmp_path):
    r = dc.Registre(tmp_path)
    cc = r.ajouter(dc.COMMANDE, "Client A", "2026-11-01", [ligne()], depot="Dépôt 2")
    bl = r.transformer(cc.numero, dc.LIVRAISON, "2026-11-02")
    fa = dc.Registre(tmp_path).transformer(bl.numero, dc.FACTURE, "2026-11-03")
    r = dc.Registre(tmp_path)
    assert (cc.numero[:2], bl.numero[:2], fa.numero[:2]) == ("CC", "BL", "FV")
    assert r.chaine(fa.numero) == [cc.numero, bl.numero]       # la facture retrouve la commande et la livraison
    assert r.document(cc.numero).etat == dc.TRANSFORME and r.document(fa.numero).depot == "Dépôt 2"
    assert r.document(fa.numero).etat == dc.BROUILLON           # seule la facture touchera le stock (import)
    rc = r.transformer(fa.numero, dc.RETOUR)
    frc = dc.Registre(tmp_path).transformer(rc.numero, dc.FACTURE_RETOUR)
    assert frc.numero.startswith("FRC") and dc.Registre(tmp_path).chaine(frc.numero)[-2:] == [fa.numero, rc.numero]
    with pytest.raises(ValueError):
        dc.Registre(tmp_path).transformer(cc.numero, dc.FACTURE_RETOUR)


def test_facture_de_retour_negative_dans_le_fichier_sage(tmp_path, monkeypatch):
    r = dc.Registre(tmp_path)
    frc = r.ajouter(dc.FACTURE_RETOUR, "Client A", "2026-11-03", [ligne()])
    vus = {}

    def ecrire(imps, chemin, _config):
        vus["lignes"] = [(l.quantite, l.montant) for i in imps for l in i.lignes]
        return chemin

    monkeypatch.setattr("mvogmbi_sync.import_sage.ecrire_imp", ecrire)
    monkeypatch.setattr("mvogmbi_sync.__main__.config_import", lambda c: None)
    dc.ecrire_imp([frc], tmp_path / "x.IMP", {})
    assert vus["lignes"] == [(D("-2"), D("-7.00"))]


def test_achat_bc_br_puis_facture_prete_a_importer(tmp_path):
    bons = bc.creer_bons(tmp_path, [bc.Proposition("C0001", "Riz", "", D(0), D(0), D(3), "Fourn A", D("12.00"),
                                                   facteur=D(12))], date(2026, 11, 1))
    numero_bc = bons[0].numero
    br = transformer_achat(tmp_path, ("bc", numero_bc), dc.RECEPTION, "2026-11-02")
    doc = dc.Registre(tmp_path).document(br)
    assert br.startswith("BR") and doc.origine == numero_bc and doc.facteurs == {"C0001": "12"}
    assert bc.Registre(tmp_path).bons[0].etat == bc.RECU
    with pytest.raises(ValueError):  # n° de facture du fournisseur obligatoire
        transformer_achat(tmp_path, ("doc", br), dc.FACTURE_ACHAT, "2026-11-03")
    transformer_achat(tmp_path, ("doc", br), dc.FACTURE_ACHAT, "2026-11-03", numero_facture="F-777")
    from mvogmbi_sync.fournisseurs import Registre

    f = Registre(tmp_path).factures[-1]
    assert (f.numero, f.fournisseur_sage, f.lignes[0].facteur) == ("F-777", "Fourn A", D(12))
    assert f.lignes[0].en_sage()[0] == D(36)  # 3 caisses × 12 = 36 unités Sage
    assert any(numero_bc in r and br in r for r in f.remarques)
    assert dc.Registre(tmp_path).document(br).etat == dc.TRANSFORME


def test_document_de_stock_non_passe_annule_par_suppression(tmp_path):
    r = dc.Registre(tmp_path)
    d = r.ajouter(dc.STOCK, "", "2026-11-01", [ligne()], sens=dc.SORTIE)
    annuler_stock(tmp_path, {}, d.numero)
    assert dc.Registre(tmp_path).documents == []


def test_saisie_ligne_reprise_et_modifiee():
    pytest.importorskip("tkinter")
    import tkinter as tk

    from mvogmbi_sync.fenetre_saisie import SaisieDocument

    try:
        racine = tk.Tk()
    except tk.TclError:
        pytest.skip("Tk indisponible")
    racine.withdraw()
    try:
        f = SaisieDocument(racine, "Essai", {"C0001": ("Riz", D("3.50"))}, lambda e, l: "ok",
                           facteurs=lambda fo, n: D(12))
        f.article.set("C0001 — Riz")
        f._article_choisi()
        f.quantite.set("2")
        assert f.qte_sage.get() == "24"                 # Qté Sage = Qté × Facteur
        f.qte_sage.set("30")
        assert f.facteur.get() == "15"                  # Qté Sage tapée : facteur recalculé
        f.ajouter()
        f.arbre.selection_set("0")
        f._reprendre_ligne()                           # clic sur la ligne : elle revient dans les champs
        assert f.quantite.get() == "2" and f._edition == 0
        f.quantite.set("4")
        f.ajouter()                                     # Entrée : la ligne est mise à jour, pas ajoutée
        assert len(f.lignes) == 1 and f.lignes[0]["quantite"] == D(4)
    finally:
        racine.destroy()
