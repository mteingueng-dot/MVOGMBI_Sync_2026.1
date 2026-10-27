import csv
import tkinter as tk
from decimal import Decimal as D
from tkinter import ttk

import pytest
from openpyxl import load_workbook

from mvogmbi_sync.export_tableau import contenu, ecrire_csv, ecrire_excel, nombre


def test_montants_reconnus_codes_laisses_en_texte():
    assert nombre("1 234,56 $") == D("1234.56")
    assert nombre("1,234.56") == D("1234.56")
    assert nombre("-5.95") == D("-5.95")
    assert nombre("12.345") == D("12.345")
    assert nombre("8 271,38 $") == D("8271.38")
    assert nombre("2026-10-22") is None
    assert nombre("0123456789") is None      # code-barres
    assert nombre("4023") is None            # n° de compte
    assert nombre("Vente 2026-10-23/25") is None


@pytest.fixture
def tableau():
    try:
        racine = tk.Tk()
    except tk.TclError:
        pytest.skip("pas d'affichage")
    arbre = ttk.Treeview(racine, columns=("montant", "etat"), show="tree headings")
    arbre.heading("#0", text="Dépôt")
    arbre.heading("montant", text="Montant")
    arbre.heading("etat", text="État")
    depot = arbre.insert("", "end", text="2026-10-26", values=("8,271.38", "À saisir"))
    arbre.insert(depot, "end", text="Vente 2026-10-23/25", values=("8,271.38", "À saisir"))
    yield arbre
    racine.destroy()


def test_export_excel_et_csv(tableau, tmp_path):
    entetes, lignes = contenu(tableau)
    assert entetes == ["Dépôt", "Montant", "État"]
    assert lignes == [["2026-10-26", "8,271.38", "À saisir"], ["    Vente 2026-10-23/25", "8,271.38", "À saisir"]]
    ecrire_excel(tmp_path / "t.xlsx", "Encaissements", entetes, lignes)
    feuille = load_workbook(tmp_path / "t.xlsx").active
    assert feuille.title == "Encaissements" and feuille["B2"].value == 8271.38 and feuille["A2"].value == "2026-10-26"
    ecrire_csv(tmp_path / "t.csv", entetes, lignes)
    with open(tmp_path / "t.csv", encoding="utf-8-sig", newline="") as f:
        assert list(csv.reader(f, delimiter=";"))[2] == ["Vente 2026-10-23/25", "8,271.38", "À saisir"]


def test_export_pdf(tmp_path):
    from mvogmbi_sync.export_tableau import EDGE, ecrire_pdf

    if not any(e.exists() for e in EDGE):
        pytest.skip("Microsoft Edge absent")
    lignes = [["2026-10-26", "lundi", "8 271,38 $", "Appliqué"]] * 60
    ecrire_pdf(tmp_path / "t.pdf", "Encaissements", ["Date", "Jour", "Montant", "État"], lignes)
    assert (tmp_path / "t.pdf").read_bytes()[:5] == b"%PDF-"
