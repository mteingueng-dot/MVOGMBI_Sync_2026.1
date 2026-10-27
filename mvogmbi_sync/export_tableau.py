"""Export de n'importe quel tableau de l'interface (ttk.Treeview) en Excel (.xlsx), en CSV ou en PDF.

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


EDGE = [Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe")]


def ecrire_pdf(chemin: Path, titre: str, entetes: list[str], lignes: list[list[str]]) -> None:
    """PDF du tableau (page HTML imprimée par Microsoft Edge sans fenêtre, comme le manuel : aucune bibliothèque
    de plus) : en-tête du marché, titre, date, en-têtes verts, une ligne sur deux teintée, montants à droite,
    page à l'horizontale au-delà de 7 colonnes."""
    import html
    import subprocess
    import tempfile
    from datetime import datetime

    edge = next((e for e in EDGE if e.exists()), None)
    if not edge:
        raise RuntimeError(t("Microsoft Edge introuvable : l'export PDF en a besoin."))
    e = html.escape
    entier = re.compile(r"^-?\d[\d\s ]*([.,]\d+)?( %)?$")  # nombres, quantités, pourcentages : à droite
    nombres = [any(nombre(l[i]) is not None or entier.match(str(l[i]).strip()) for l in lignes[:50] if i < len(l))
               for i in range(len(entetes))]
    corps = "".join(
        "<tr>" + "".join(f"<td class='{'n' if nombres[i] else ''}'>{e(str(v).strip())}</td>"
                         for i, v in enumerate(l)) + "</tr>" for l in lignes)
    page = f"""<!doctype html><html lang='fr'><head><meta charset='utf-8'><style>
@page {{ size: Letter {'landscape' if len(entetes) > 7 else 'portrait'}; margin: 12mm 10mm; }}
body {{ font-family: 'Segoe UI', Arial, sans-serif; font-size: 8.5pt; color: #1f2d24; margin: 0; }}
.bandeau {{ border-top: 6px solid #1a9b3c; padding-top: 6px; display: flex; justify-content: space-between; }}
.marche {{ color: #13772d; font-weight: 600; font-size: 10pt; }}
.date {{ color: #6b7a70; font-size: 8pt; }}
h1 {{ font-size: 14pt; color: #13772d; margin: 8px 0 2px; }}
.sous {{ color: #6b7a70; margin-bottom: 8px; }}
table {{ width: 100%; border-collapse: collapse; }}
thead {{ display: table-header-group; }}
th {{ background: #1f7a3a; color: #fff; text-align: left; padding: 4px 5px; font-weight: 600; }}
td {{ padding: 3px 5px; border-bottom: 1px solid #e2e8e4; vertical-align: top; }}
td.n {{ text-align: right; white-space: nowrap; }}
tr:nth-child(even) td {{ background: #f4f8f5; }}
tr {{ page-break-inside: avoid; }}
</style></head><body>
<div class='bandeau'><span class='marche'>Marché MVOG-MBI Sherbrooke — MVOGMBI_Sync</span>
<span class='date'>{datetime.now():%Y-%m-%d %H:%M}</span></div>
<h1>{e(titre)}</h1><div class='sous'>{e(t("{n} ligne(s)", n=len(lignes)))}</div>
<table><thead><tr>{"".join(f"<th>{e(str(x))}</th>" for x in entetes)}</tr></thead><tbody>{corps}</tbody></table>
</body></html>"""
    with tempfile.TemporaryDirectory() as dossier:
        source = Path(dossier) / "tableau.html"
        source.write_text(page, encoding="utf-8")
        subprocess.run([str(edge), "--headless", "--disable-gpu", "--no-pdf-header-footer",
                        f"--print-to-pdf={chemin}", source.as_uri()], check=True, timeout=120, capture_output=True)
    if not Path(chemin).exists():
        raise RuntimeError(t("Le PDF n'a pas pu être créé."))


def exporter(tableau: ttk.Treeview, nom: str, format_: str = "xlsx") -> None:
    """Demande où enregistrer puis écrit le fichier ; propose de l'ouvrir."""
    entetes, lignes = contenu(tableau)
    if not lignes:
        messagebox.showinfo(nom, t("Le tableau est vide : rien à exporter."), parent=tableau)
        return
    types = {"xlsx": ("Excel", "*.xlsx"), "csv": ("CSV", "*.csv"), "pdf": ("PDF", "*.pdf")}
    chemin = filedialog.asksaveasfilename(parent=tableau, defaultextension="." + format_,
                                          initialfile=f"{nom} {date.today().isoformat()}.{format_}",
                                          filetypes=[types[format_]] + [v for k, v in types.items() if k != format_])
    if not chemin:
        return
    chemin = Path(chemin)
    try:
        if chemin.suffix.lower() == ".csv":
            ecrire_csv(chemin, entetes, lignes)
        elif chemin.suffix.lower() == ".pdf":
            tableau.configure(cursor="watch")
            tableau.update_idletasks()
            try:
                ecrire_pdf(chemin, nom, entetes, lignes)
            finally:
                tableau.configure(cursor="")
        else:
            ecrire_excel(chemin.with_suffix(".xlsx"), nom, entetes, lignes)
            chemin = chemin.with_suffix(".xlsx")
    except PermissionError:
        messagebox.showerror(nom, t("Fichier ouvert dans Excel : fermez-le puis recommencez."), parent=tableau)
        return
    except Exception as exc:  # PDF : Edge absent ou en échec
        messagebox.showerror(nom, str(exc), parent=tableau)
        return
    if messagebox.askyesno(nom, t("{n} ligne(s) exportée(s) dans {fichier}.\n\nOuvrir le fichier ?",
                                  n=len(lignes), fichier=chemin.name), parent=tableau):
        os.startfile(chemin)


def menu(tableau: ttk.Treeview, nom: str) -> tk.Menu:
    m = tk.Menu(tableau, tearoff=0)
    m.add_command(label="📗  " + t("Exporter en Excel (.xlsx)…"), command=lambda: exporter(tableau, nom, "xlsx"))
    m.add_command(label="📄  " + t("Exporter en CSV (.csv)…"), command=lambda: exporter(tableau, nom, "csv"))
    m.add_command(label="📕  " + t("Exporter en PDF (.pdf)…"), command=lambda: exporter(tableau, nom, "pdf"))
    return m


def rendre_exportable(tableau: ttk.Treeview, nom: str) -> None:
    """Clic droit sur le tableau : Exporter en Excel / en CSV / en PDF."""
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
