"""Impression d'une facture fournisseur importée (demande du propriétaire du 2026-11-05 : « une fois les factures
importées, je dois pouvoir imprimer les articles entrés en machine sous un modèle de bon de réception sans les prix,
juste article, quantité Sage, quantité Clover, une colonne observation ; d'autre part imprimer la facture complète
pour la joindre à la facture du fournisseur et archiver le dossier manuellement ») :

- `bon_reception` : n° et article Sage, quantité Sage, quantité Clover (journal du stock Clover : ce qui a vraiment
  été ajouté ; « — » si rien n'a été ajouté), colonne « Observation » vide à remplir à la main, signatures ;
- `facture_complete` : lignes avec quantités, prix et montants en unités Sage, taxes, total, n° du fournisseur.
PDF par pdf_documents (fpdf2, en-tête de l'entreprise Clover), dans donnees/impressions_fournisseurs/.
"""

from __future__ import annotations

import csv
from datetime import date
from decimal import Decimal
from pathlib import Path

from .pdf_documents import GRIS, VERT_FONCE, ModelePDF, argent, chemin_libre, document_commercial, quantite


def _dossier(racine: Path) -> Path:
    dossier = Path(racine) / "donnees" / "impressions_fournisseurs"
    dossier.mkdir(parents=True, exist_ok=True)
    return dossier


def _nom(facture, genre: str) -> str:
    propre = "".join(c if c.isalnum() or c in "-_" else "_" for c in f"{facture.fournisseur_sage}_{facture.numero}")
    return f"{genre}_{propre[:60]}.pdf"


def quantites_clover(racine: Path, facture) -> dict[str, Decimal]:
    """Quantité ajoutée au stock Clover par n° Sage pour cette facture (journal du stock Clover)."""
    chemin = Path(racine) / "donnees" / "journal_stock_clover.csv"
    resultat: dict[str, Decimal] = {}
    if not chemin.exists():
        return resultat
    with open(chemin, encoding="utf-8-sig", newline="") as f:
        for ligne in csv.DictReader(f, delimiter=";"):
            if ligne.get("Fournisseur") == facture.fournisseur_sage and ligne.get("Facture") == facture.numero:
                try:
                    resultat[ligne["N° Sage"]] = resultat.get(ligne["N° Sage"], Decimal(0)) + Decimal(
                        str(ligne.get("Quantité ajoutée") or 0).replace(",", "."))
                except ArithmeticError:
                    continue
    return resultat


def bon_reception(racine: Path, facture) -> Path:
    """Bon de réception SANS PRIX de la facture : article, quantité Sage, quantité Clover, observation."""
    clover = quantites_clover(racine, facture)
    pdf = ModelePDF(f"Bon de réception {facture.numero}", racine=racine)
    pdf.add_page()
    pdf.cadre_titre("Bon de réception", facture.numero, facture.date_facture or date.today().isoformat(),
                    facture.etat)
    infos = [f"Facture du fournisseur : {facture.numero}", f"Dépôt : {facture.depot or 'Emplacement par défaut'}",
             f"Imprimé le {date.today().isoformat()}", f"Fichier : {facture.fichier}"]
    pdf.blocs(("Fournisseur", [facture.fournisseur_sage or facture.fournisseur_lu or "—"]), ("Informations", infos))
    largeur = pdf.w - pdf.l_margin - pdf.r_margin
    colonnes = [("N° Sage", 30, "L"), ("Article", 0, "L"), ("Qté Sage", 22, "R"), ("Qté Clover", 22, "R"),
                ("Observation", 52, "L")]
    reste = largeur - sum(l for _t, l, _a in colonnes)
    colonnes = [(t, l or reste, a) for t, l, a in colonnes]
    pdf.entetes(colonnes)
    rang = 0
    for l in facture.lignes:
        if l.nature != "article" and not l.numero_sage:
            continue
        qte_sage = l.en_sage()[0]
        qte_clover = clover.get(l.numero_sage)
        pdf.ligne_tableau(colonnes, [l.numero_sage or "—", l.description_sage or l.description, quantite(qte_sage),
                                     quantite(qte_clover) if qte_clover is not None else "—", ""], rang, 9)
        rang += 1
    pdf.ln(10)
    pdf.police_(9, False, GRIS)
    pdf.multi_cell(0, 4.6, pdf.ecrire("« — » en Qté Clover : rien n'a été ajouté au stock Clover pour cet article "
                                      "(article non relié, ou mise à jour de Clover décochée)."))
    pdf.ln(10)
    pdf.police_(9.5, True, VERT_FONCE)
    moitie = largeur / 2
    pdf.cell(moitie, 6, pdf.ecrire("Reçu par : ______________________________"))
    pdf.cell(moitie, 6, pdf.ecrire("Date : ____________________"), new_x="LMARGIN", new_y="NEXT")
    chemin = chemin_libre(_dossier(racine) / _nom(facture, "Bon_de_reception"))
    pdf.output(str(chemin))
    return chemin


def facture_complete(racine: Path, facture) -> Path:
    """Facture complète AVEC PRIX (unités Sage), à joindre à la facture du fournisseur."""
    from .taxes import code as code_ligne

    lignes = []
    for l in facture.lignes:
        qte, prix = l.en_sage()
        lignes.append({"numero": l.numero_sage or l.code or "—", "description": l.description_sage or l.description,
                       "quantite": qte, "prix": prix, "montant": l.montant, "taxe": code_ligne(l)})
    infos = [f"Facture du fournisseur : {facture.numero}", f"Dépôt : {facture.depot or 'Emplacement par défaut'}",
             f"Fichier : {facture.fichier}"]
    if facture.total is not None:
        infos.append(f"Total de la facture du fournisseur : {argent(facture.total)}")
    return document_commercial(_dossier(racine) / _nom(facture, "Facture"), racine, "Facture fournisseur",
                               facture.numero, facture.date_facture or "", "Fournisseur",
                               [facture.fournisseur_sage or facture.fournisseur_lu or "—"], infos, lignes,
                               avec_taxes=True, etat=facture.etat, libelle_prix="Prix Sage")
