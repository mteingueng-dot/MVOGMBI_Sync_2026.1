"""Export de n'importe quel tableau de l'interface (ttk.Treeview) en Excel (.xlsx) ou en CSV.

Ce qui est exporté = ce qui est affiché (filtre et recherche compris), colonnes dans l'ordre de l'écran ; les
lignes enfants (dépôt -> factures de la page Encaissements) sont décalées sous leur parent. Excel : montants
convertis en nombres (« 1 234,56 $ », « 1,234.56 », « -5.95 ») ; codes, dates et numéros restent du texte.
CSV : séparateur « ; » et UTF-8 avec BOM, comme l'attend Excel en français.
"""

from __future__ import annotations

import csv
import os
import re
import tkinter as tk
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .langues import t

MONTANT = re.compile(r"^-?\d{1,3}(?:[   ,]\d{3})*(?:[.,]\d+)?$|^-?\d+[.,]\d+$")


def contenu(tableau: ttk.Treeview) -> tuple[list[str], list[list[str]]]:
    """(en-têtes, lignes) du tableau tel qu'il est affiché."""
    colonnes = list(tableau["displaycolumns"])
    if colonnes in (["#all"], [], ("#all",)):
        colonnes = list(tableau["columns"])
    arbre = "tree" in str(tableau["show"])
    entetes = ([tableau.heading("#0", "text")] if arbre else []) + [tableau.heading(c, "text") for c in colonnes]
    lignes: list[list[str]] = []

    def parcourir(parent: str, niveau: int) -> None:
        for ligne in tableau.get_children(parent):
            valeurs = [str(tableau.set(ligne, c)) for c in colonnes]
            if arbre:
                valeurs.insert(0, "    " * niveau + str(tableau.item(ligne, "text")))
            lignes.append(valeurs)
            parcourir(ligne, niveau + 1)

    parcourir("", 0)
    return entetes, lignes


def nombre(texte: str) -> Decimal | None:
    """« 1 234,56 $ » -> 1234.56 ; None si ce n'est pas un montant (code, date, n° de facture)."""
    s = texte.replace("$", "").strip()
    if not MONTANT.match(s):
        return None
    if "," in s and "." in s:
        s = s.replace(",", "")           # 1,234.56
    elif "," in s:
        entier, _, decimales = s.rpartition(",")
        s = entier.replace(",", "") + "." + decimales if len(decimales) != 3 else s.replace(",", "")
    s = re.sub(r"[   ]", "", s)
    if "." not in s and texte.strip().lstrip("-")[:1] == "0" and len(s.lstrip("-")) > 1:
        return None                      # code-barres « 0123456 » : du texte
    if "." not in s and "$" not in texte:
        return None                      # entier sans $ : numéro ou quantité entière laissés tels quels
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def ecrire_csv(chemin: Path, entetes: list[str], lignes: list[list[str]]) -> None:
    with open(chemin, "w", newline="", encoding="utf-8-sig") as f:
        sortie = csv.writer(f, delimiter=";")
        sortie.writerow(entetes)
        sortie.writerows([v.strip() for v in l] for l in lignes)


def ecrire_excel(chemin: Path, titre: str, entetes: list[str], lignes: list[list[str]]) -> None:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    classeur = Workbook()
    feuille = classeur.active
    feuille.title = re.sub(r"[\\/*?:\[\]]", "-", titre)[:31] or "Tableau"
    feuille.append(entetes)
    for cellule in feuille[1]:
        cellule.font = Font(bold=True, color="FFFFFF")
        cellule.fill = PatternFill("solid", fgColor="1F7A3A")
        cellule.alignment = Alignment(vertical="center")
    for valeurs in lignes:
        rangee = []
        for v in valeurs:
            n = nombre(v)
            rangee.append(float(n) if n is not None else v.rstrip())
        feuille.append(rangee)
        for cellule, v in zip(feuille[feuille.max_row], valeurs):
            n = nombre(v)
            if n is not None:
                decimales = -n.as_tuple().exponent if n.as_tuple().exponent < 0 else 0
                cellule.number_format = "#,##0" + ("." + "0" * decimales if decimales else "")
    for i, entete in enumerate(entetes, 1):
        largeur = max([len(str(entete))] + [len(l[i - 1]) for l in lignes if i - 1 < len(l)])
        feuille.column_dimensions[get_column_letter(i)].width = min(60, largeur + 2)
    feuille.freeze_panes = "A2"
    feuille.auto_filter.ref = feuille.dimensions
    classeur.save(chemin)


def exporter(tableau: ttk.Treeview, nom: str, format_: str = "xlsx") -> None:
    """Demande où enregistrer puis écrit le fichier ; propose de l'ouvrir."""
    entetes, lignes = contenu(tableau)
    if not lignes:
        messagebox.showinfo(nom, t("Le tableau est vide : rien à exporter."), parent=tableau)
        return
    types = {"xlsx": ("Excel", "*.xlsx"), "csv": ("CSV", "*.csv")}
    autre = "csv" if format_ == "xlsx" else "xlsx"
    chemin = filedialog.asksaveasfilename(parent=tableau, defaultextension="." + format_,
                                          initialfile=f"{nom} {date.today().isoformat()}.{format_}",
                                          filetypes=[types[format_], types[autre]])
    if not chemin:
        return
    chemin = Path(chemin)
    try:
        if chemin.suffix.lower() == ".csv":
            ecrire_csv(chemin, entetes, lignes)
        else:
            ecrire_excel(chemin.with_suffix(".xlsx"), nom, entetes, lignes)
            chemin = chemin.with_suffix(".xlsx")
    except PermissionError:
        messagebox.showerror(nom, t("Fichier ouvert dans Excel : fermez-le puis recommencez."), parent=tableau)
        return
    if messagebox.askyesno(nom, t("{n} ligne(s) exportée(s) dans {fichier}.\n\nOuvrir le fichier ?",
                                  n=len(lignes), fichier=chemin.name), parent=tableau):
        os.startfile(chemin)


def menu(tableau: ttk.Treeview, nom: str) -> tk.Menu:
    m = tk.Menu(tableau, tearoff=0)
    m.add_command(label="📗  " + t("Exporter en Excel (.xlsx)…"), command=lambda: exporter(tableau, nom, "xlsx"))
    m.add_command(label="📄  " + t("Exporter en CSV (.csv)…"), command=lambda: exporter(tableau, nom, "csv"))
    return m


def rendre_exportable(tableau: ttk.Treeview, nom: str) -> None:
    """Clic droit sur le tableau : Exporter en Excel / en CSV."""
    tableau._nom_export = nom
    tableau.bind("<Button-3>", lambda e: menu(tableau, nom).tk_popup(e.x_root, e.y_root), add="+")


def bouton_exporter(parent, tableau: ttk.Treeview, nom: str, **options):
    """Bouton « Exporter » qui propose Excel ou CSV ; rend aussi le tableau exportable par clic droit."""
    from .design import Bouton

    rendre_exportable(tableau, nom)
    bouton = None

    def ouvrir() -> None:
        menu(tableau, nom).tk_popup(bouton.winfo_rootx(), bouton.winfo_rooty() + bouton.winfo_height())

    bouton = Bouton(parent, "⬇  " + t("Exporter"), ouvrir, "secondaire", **options)
    return bouton
