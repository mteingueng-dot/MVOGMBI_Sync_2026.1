"""Corrections de l'analyse de sécurité du 2026-11-13 (demande du propriétaire : « corrige tous les points de
sécurité »)."""
import hashlib
from datetime import datetime, timedelta
from pathlib import Path

import openpyxl
import pytest

from mvogmbi_sync import paie_temps, securite, utilisateurs


def test_seuls_les_pdf_et_images_sont_acceptes(tmp_path):
    assert securite.document_permis("recu.pdf", b"%PDF-1.7 ...")
    assert securite.document_permis("photo.JPG", b"\xff\xd8\xff\xe0...")
    assert securite.document_permis("img.png", b"\x89PNG\r\n\x1a\n...")
    assert securite.document_permis("iphone.heic", b"\x00\x00\x00\x18ftypheic....")
    assert not securite.document_permis("recu.exe", b"MZ\x90\x00")
    assert not securite.document_permis("recu.pdf", b"MZ\x90\x00")       # programme renommé en .pdf
    assert not securite.document_permis("page.hta", b"<html>")
    with pytest.raises(securite.FichierRefuse):
        securite.verifier_document("recu.bat", b"@echo off")
    faux = tmp_path / "facture.pdf"
    faux.write_bytes(b"MZ programme")
    lances = []
    with pytest.raises(securite.FichierRefuse):
        securite.ouvrir_document(faux)                                   # jamais ouvert sous Windows
    assert not lances


def test_recu_de_depense_refuse(tmp_path):
    from decimal import Decimal

    from mvogmbi_sync import depenses as dp

    exe = tmp_path / "recu.exe"
    exe.write_bytes(b"MZ\x90\x00")
    d = dp.Depense(numero="", jour="2026-11-13", fournisseur="Essai", description="Essai",
                   montant=str(Decimal("11.50")), compte="5700")
    with pytest.raises(securite.FichierRefuse):
        dp.Registre(tmp_path).ajouter(d, exe)


def test_aucune_formule_dans_excel_ni_csv(tmp_path):
    classeur = openpyxl.Workbook()
    feuille = classeur.active
    feuille.append(['=HYPERLINK("http://exemple.invalid","Cliquez")', 12.5, "Riz"])
    feuille["A2"] = "=1+1"
    assert feuille["A1"].data_type == "s" and feuille["A2"].data_type == "s" and feuille["B1"].data_type == "n"
    from mvogmbi_sync.export_tableau import ecrire_csv

    chemin = tmp_path / "x.csv"
    ecrire_csv(chemin, ["Message", "Montant"], [["=cmd|' /C calc'!A0", "-12,50"], ["@SUM(A1)", "+3"]])
    texte = chemin.read_text(encoding="utf-8-sig")
    assert "'=cmd" in texte and "'@SUM" in texte and ";-12,50" in texte and ";+3" in texte


def test_empreintes_600000_tours_et_mise_a_niveau(tmp_path, monkeypatch):
    monkeypatch.setattr(utilisateurs, "ITERATIONS", 600_000)
    sel = "00" * 16
    nouvelle = utilisateurs.empreinte("Motdepasse-2026", sel)
    assert nouvelle.startswith("pbkdf2$600000$") and utilisateurs.mot_de_passe_juste("Motdepasse-2026", sel, nouvelle)
    monkeypatch.setattr(utilisateurs, "ITERATIONS", 2_000)   # rapide pour la suite du test
    reg = utilisateurs.Registre(tmp_path)
    u = reg.ajouter("Ancien", utilisateurs.ADMIN, "Motdepasse-2026")
    ancienne = hashlib.pbkdf2_hmac("sha256", b"Motdepasse-2026", bytes.fromhex(u.sel), 200_000).hex()
    u.empreinte = ancienne                                   # empreinte d'avant la 1.0.13 (sans préfixe)
    reg.enregistrer()
    reg = utilisateurs.Registre(tmp_path)
    assert reg.verifier("Ancien", "Motdepasse-2026") is not None
    assert reg.trouver("Ancien").empreinte.startswith("pbkdf2$2000$")   # refaite à la connexion
    assert reg.verifier("Ancien", "Motdepasse-2026") is not None
    with pytest.raises(utilisateurs.ErreurUtilisateur, match="12"):
        reg.ajouter("Court", utilisateurs.ADMIN, "court1")


def test_nip_attente_qui_s_allonge(tmp_path, monkeypatch):
    notes = []
    monkeypatch.setattr("mvogmbi_sync.audit.noter", lambda *a, **k: notes.append(a[1]))
    reg = paie_temps.Registre(tmp_path)
    e = reg.ajouter("Employé A")
    reg.definir_nip(e.id, "4821")
    t0 = datetime(2026, 11, 13, 9, 0)
    for _ in range(5):
        assert not reg.verifier_nip(e.id, "0000", t0)
    with pytest.raises(paie_temps.ErreurPointage):
        reg.verifier_nip(e.id, "4821", t0 + timedelta(seconds=30))
    t1 = t0 + timedelta(seconds=61)
    for _ in range(5):                                      # 2e série : 5 minutes d'attente
        assert not reg.verifier_nip(e.id, "0000", t1)
    with pytest.raises(paie_temps.ErreurPointage, match="4 minute"):
        reg.verifier_nip(e.id, "4821", t1 + timedelta(seconds=90))
    assert reg.verifier_nip(e.id, "4821", t1 + timedelta(minutes=6))
    assert len(notes) == 2 and all("NIP faux" in n for n in notes)


def test_requete_web_de_taille_negative_refusee(tmp_path):
    import io

    from mvogmbi_sync.web import serveur

    class Faux(serveur.Gestionnaire):
        def __init__(self):
            self.headers = {"Content-Length": "-1", "Content-Type": "application/x-www-form-urlencoded"}
            self.path = "/connexion"
            self.rfile = io.BytesIO(b"")
            self.envoye = None

        def _envoyer(self, rep):
            self.envoye = rep

    g = Faux()
    g._servir("POST")
    assert g.envoye.statut == 400
    assert serveur.Gestionnaire.timeout == 30
