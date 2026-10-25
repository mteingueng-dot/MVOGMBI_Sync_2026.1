"""Correspondance entre les articles Clover et les numéros d'articles Sage.

Rapprochement automatique, dans l'ordre :
1. code-barres Clover identique à un numéro d'article Sage ;
2. nom Clover identique à une description Sage (accents, casse et ponctuation ignorés) ;
3. nom le plus ressemblant (les formats « 1kg » / « 2kg » doivent concorder), à confirmer.

Le résultat est un fichier Excel que le propriétaire vérifie : il corrige le numéro Sage si besoin
et inscrit « Confirmé » dans la colonne Statut. Les lignes confirmées sont conservées telles quelles
quand le fichier est régénéré (nouveaux articles Clover, nouvelle liste Sage).
"""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import openpyxl
from openpyxl.styles import Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation
from rapidfuzz import fuzz, process

from .articles_sage import ArticleSage

CONFIRME = "Confirmé"
AUTOMATIQUE = "Automatique"
A_CONFIRMER = "À confirmer"
AUCUN = "Aucun"
STATUTS = [CONFIRME, AUTOMATIQUE, A_CONFIRMER, AUCUN]
VALIDATIONS = {CONFIRME.lower(), "confirme", "ok", "oui"}  # saisies acceptées comme « Confirmé »

SEUIL_SUGGESTION = 60  # en dessous, aucune proposition

ENTETES = [
    "Statut", "Nom Clover", "Catégorie Clover", "Ventes 30 j ($)", "N° article Sage",
    "Description Sage", "Compte revenus", "Méthode", "Confiance (%)", "Autres suggestions",
    "Code Clover", "ID Clover",
]
COULEURS = {
    CONFIRME: "C6EFCE", AUTOMATIQUE: "DDEBF7", A_CONFIRMER: "FFEB9C", AUCUN: "FFC7CE",
}


def normaliser(texte: str) -> str:
    texte = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode().lower()
    texte = re.sub(r"(\d),(\d)", r"\1.\2", texte)  # 1,8kg -> 1.8kg
    texte = re.sub(r"([a-z])(\d)", r"\1 \2", texte)  # meme1kg -> meme 1kg
    texte = re.sub(r"(\d)\s+(kg|g|lb|lbs|l|ml|oz|pcs|p)\b", r"\1\2", texte)  # 500 g -> 500g
    return " ".join(re.sub(r"[^a-z0-9.]+", " ", texte).split())


def _formats(texte_normalise: str) -> set[str]:
    """Jetons contenant un chiffre (formats, tailles) : « 500g », « 1.8kg », « 24x330ml »."""
    return {t for t in texte_normalise.split() if any(c.isdigit() for c in t)}


def _score(a: str, b: str, **_) -> float:
    """Ressemblance 0-100 ; pénalité si les formats (chiffres) diffèrent."""
    score = fuzz.token_sort_ratio(a, b)
    fa, fb = _formats(a), _formats(b)
    if fa != fb:
        score *= 0.8 if (fa and fb) else 0.9
    return score


@dataclass
class ArticleClover:
    id: str
    nom: str
    categorie: str = ""
    code: str = ""
    ventes_30j: Decimal = Decimal("0")


@dataclass
class Correspondance:
    statut: str
    nom_clover: str
    categorie_clover: str
    ventes_30j: Decimal
    numero_sage: str
    description_sage: str
    compte_revenus: str
    methode: str
    confiance: int
    suggestions: str
    code_clover: str
    id_clover: str


def conflit_format(nom_clover: str, description_sage: str) -> bool:
    """Deux formats différents = deux articles différents (« 1kg » et « 500g », « 6-36 » et « 7-36 »)."""
    fa, fb = _formats(normaliser(nom_clover)), _formats(normaliser(description_sage))
    return bool(fa and fb and fa != fb)


def rapprocher(clover: list[ArticleClover], sage: list[ArticleSage],
               confirmes: dict[str, Correspondance] | None = None) -> list[Correspondance]:
    confirmes = confirmes or {}
    par_numero = {a.numero.lower(): a for a in sage}
    par_nom: dict[str, list[ArticleSage]] = defaultdict(list)
    for a in sage:
        par_nom[normaliser(a.description)].append(a)
    noms_sage = list(par_nom)

    def rechercher(nom_clover: str) -> tuple[str, ArticleSage | None, str, int, str]:
        """Article Sage ressemblant, au même format ; sinon article à créer dans Sage."""
        nom = normaliser(nom_clover)
        identiques = par_nom.get(nom, [])
        if len(identiques) == 1:
            return AUTOMATIQUE, identiques[0], "Nom identique", 100, ""
        candidats = process.extract(nom, noms_sage, scorer=_score, limit=15)
        compatibles = [c for c in candidats if not conflit_format(nom_clover, par_nom[c[0]][0].description)]
        decrire = lambda c: f"{par_nom[c[0]][0].numero} — {par_nom[c[0]][0].description} ({c[1]:.0f} %)"
        if compatibles and compatibles[0][1] >= SEUIL_SUGGESTION:
            autres = " | ".join(decrire(c) for c in compatibles[1:3] if c[1] >= SEUIL_SUGGESTION)
            return A_CONFIRMER, par_nom[compatibles[0][0]][0], "Nom ressemblant", round(compatibles[0][1]), autres
        proches = [c for c in candidats if c[1] >= SEUIL_SUGGESTION][:3]
        if proches:
            return (AUCUN, None, "À créer dans Sage (aucun article à ce format)", 0,
                    "Autres formats existants : " + " | ".join(decrire(c) for c in proches))
        return AUCUN, None, "À créer dans Sage (aucun article ressemblant)", 0, ""

    resultat = []
    for article in clover:
        def ligne(statut, sage_choisi, methode, confiance, suggestions="", numero=""):
            return Correspondance(
                statut, article.nom, article.categorie, article.ventes_30j,
                sage_choisi.numero if sage_choisi else numero, sage_choisi.description if sage_choisi else "",
                sage_choisi.compte_revenus if sage_choisi else "", methode, confiance, suggestions,
                article.code, article.id,
            )

        deja = confirmes.get(article.id)
        if deja is not None:
            choisi = par_numero.get(deja.numero_sage.lower())
            if choisi is None:
                resultat.append(ligne(A_CONFIRMER, None, "Numéro absent de la liste Sage (réexporter la liste)", 0,
                                      numero=deja.numero_sage))
            elif conflit_format(article.nom, choisi.description):
                statut, sage_choisi, methode, confiance, autres = rechercher(article.nom)
                resultat.append(ligne(statut, sage_choisi, methode, confiance,
                                      f"Confirmation annulée ({choisi.numero} — {choisi.description} : autre format). "
                                      + autres))
            else:
                resultat.append(ligne(CONFIRME, choisi, deja.methode or "Manuel", 100))
            continue

        if article.code and article.code.lower() in par_numero:
            choisi = par_numero[article.code.lower()]
            if not conflit_format(article.nom, choisi.description):
                resultat.append(ligne(AUTOMATIQUE, choisi, "Code-barres", 100))
                continue

        identiques = par_nom.get(normaliser(article.nom), [])
        if len(identiques) > 1:
            autres = " | ".join(f"{a.numero} — {a.description}" for a in identiques[1:])
            resultat.append(ligne(A_CONFIRMER, identiques[0], "Nom identique (plusieurs articles Sage)", 90, autres))
            continue

        resultat.append(ligne(*rechercher(article.nom)))

    _signaler_formats_regroupes(resultat)
    ordre = {CONFIRME: 3, AUTOMATIQUE: 2, A_CONFIRMER: 0, AUCUN: 1}
    resultat.sort(key=lambda c: (ordre[c.statut], -c.ventes_30j, c.nom_clover.lower()))
    return resultat


def _signaler_formats_regroupes(resultat: list[Correspondance]) -> None:
    """Plusieurs formats Clover (« Matembele 500g », « Matembele 1kg ») sur un même article Sage sans format :
    ce sont des articles différents, à séparer dans Sage."""
    par_numero: dict[str, list[Correspondance]] = defaultdict(list)
    for c in resultat:
        if c.numero_sage and c.description_sage:
            par_numero[c.numero_sage.lower()].append(c)
    for groupe in par_numero.values():
        formats = {frozenset(_formats(normaliser(c.nom_clover))) for c in groupe}
        if len({f for f in formats if f}) > 1:
            for c in groupe:
                if c.statut in (CONFIRME, AUTOMATIQUE):
                    c.statut = A_CONFIRMER
                c.methode = "Plusieurs formats Clover sur un seul article Sage : créer un article par format"


def lire_a_relier(chemin: Path) -> list[tuple[str, str, str]]:
    """Articles vendus à relier : « ID Clover;nom[;n° article Sage] » (séparateur ; ou ,).

    Le propriétaire peut inscrire le numéro Sage en 3e colonne (par exemple dans Excel) : la correspondance
    est alors considérée comme confirmée.
    """
    import csv

    if not chemin.exists():
        return []
    brut = chemin.read_bytes()
    try:
        texte = brut.decode("utf-8-sig")
    except UnicodeDecodeError:
        texte = brut.decode("cp1252")
    separateur = ";" if texte.count(";") >= texte.count(",") else ","
    resultat = []
    for r in csv.reader(texte.splitlines(), delimiter=separateur):
        if r and r[0].strip():
            resultat.append((r[0].strip(), (r[1] if len(r) > 1 else "").strip(), (r[2] if len(r) > 2 else "").strip()))
    return resultat


def lire_correspondances(chemin: Path) -> list[Correspondance]:
    """Toutes les lignes du fichier de correspondance (pour l'affichage et la modification dans l'application)."""
    if not chemin.exists():
        return []
    feuille = openpyxl.load_workbook(chemin, read_only=True, data_only=True)["Correspondance"]
    lignes = feuille.iter_rows(values_only=True)
    entete = list(next(lignes))
    i = {nom: entete.index(nom) for nom in ENTETES}
    texte = lambda r, nom: str(r[i[nom]] or "").strip()
    resultat = []
    for r in lignes:
        if not any(r):
            continue
        statut = texte(r, "Statut")
        if statut.lower() in VALIDATIONS:
            statut = CONFIRME
        resultat.append(Correspondance(
            statut or AUCUN, texte(r, "Nom Clover"), texte(r, "Catégorie Clover"),
            Decimal(str(r[i["Ventes 30 j ($)"]] or 0)), texte(r, "N° article Sage"), texte(r, "Description Sage"),
            texte(r, "Compte revenus"), texte(r, "Méthode"), int(r[i["Confiance (%)"]] or 0),
            texte(r, "Autres suggestions"), texte(r, "Code Clover"), texte(r, "ID Clover"),
        ))
    return resultat


def lire_confirmes(chemin: Path) -> dict[str, Correspondance]:
    """Lignes marquées « Confirmé » dans un fichier de correspondance existant, par ID Clover."""
    if not chemin.exists():
        return {}
    feuille = openpyxl.load_workbook(chemin, read_only=True, data_only=True)["Correspondance"]
    lignes = feuille.iter_rows(values_only=True)
    entete = list(next(lignes))
    i = {nom: entete.index(nom) for nom in ENTETES}
    confirmes = {}
    for r in lignes:
        if str(r[i["Statut"]] or "").strip().lower() in VALIDATIONS and r[i["ID Clover"]]:
            confirmes[str(r[i["ID Clover"]])] = Correspondance(
                CONFIRME, str(r[i["Nom Clover"]] or ""), "", Decimal("0"),
                str(r[i["N° article Sage"]] or "").strip(), "", "", str(r[i["Méthode"]] or ""), 100, "",
                "", str(r[i["ID Clover"]]),
            )
    return confirmes


def ecrire_correspondance(correspondances: list[Correspondance], chemin: Path) -> Path:
    classeur = openpyxl.Workbook()
    feuille = classeur.active
    feuille.title = "Correspondance"
    feuille.append(ENTETES)
    for cellule in feuille[1]:
        cellule.font = Font(bold=True)
    for c in correspondances:
        feuille.append([
            c.statut, c.nom_clover, c.categorie_clover, float(c.ventes_30j), c.numero_sage, c.description_sage,
            c.compte_revenus, c.methode, c.confiance, c.suggestions, c.code_clover, c.id_clover,
        ])
        feuille.cell(feuille.max_row, 1).fill = PatternFill("solid", fgColor=COULEURS[c.statut])
    validation = DataValidation(type="list", formula1='"' + ",".join(STATUTS) + '"', allow_blank=False)
    feuille.add_data_validation(validation)
    validation.add(f"A2:A{max(feuille.max_row, 2)}")
    for colonne, largeur in zip("ABCDEFGHIJKL", (13, 45, 20, 13, 18, 45, 14, 26, 12, 70, 16, 16)):
        feuille.column_dimensions[colonne].width = largeur
    for cellule in feuille["D"][1:]:
        cellule.number_format = '#,##0.00 "$"'
    feuille.freeze_panes = "C2"
    feuille.auto_filter.ref = feuille.dimensions

    aide = classeur.create_sheet("Mode d'emploi")
    for texte in [
        "Correspondance des articles Clover -> numéros d'articles Sage",
        "",
        "Statut « Automatique » (bleu) : code-barres ou nom identique. À vérifier rapidement si vous le souhaitez.",
        "Statut « À confirmer » (jaune) : proposition par ressemblance des noms. Vérifiez le numéro Sage.",
        "Statut « Aucun » (rouge) : aucun article Sage ressemblant. Inscrivez le numéro Sage à la main.",
        "",
        "Pour valider une ligne : corrigez si besoin « N° article Sage », puis choisissez « Confirmé » dans Statut.",
        "Les lignes « Confirmé » sont conservées quand le fichier est régénéré.",
        "Commencez par les articles les plus vendus (colonne « Ventes 30 j »).",
        "« Autres suggestions » liste d'autres articles Sage possibles (numéro — description).",
    ]:
        aide.append([texte])
    aide.column_dimensions["A"].width = 110

    chemin.parent.mkdir(parents=True, exist_ok=True)
    classeur.save(chemin)
    return chemin
