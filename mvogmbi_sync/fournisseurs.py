"""Factures fournisseurs : registre des factures déposées, correspondance des articles, contrôles avant import.

Fichiers (dans donnees/, jamais publiés) :
- factures_fournisseurs/            : dossier où le propriétaire dépose les PDF et photos ;
- factures_fournisseurs.json       : registre des factures lues et corrigées (une entrée par fichier, clé = empreinte) ;
- correspondance_fournisseurs.json : mémoire de la correspondance, par fournisseur Sage :
  articles (code fournisseur, sinon désignation normalisée) -> n° article Sage + facteur de conditionnement,
  et noms lus sur les factures -> fournisseur Sage ;
- fournisseurs_sage.csv            : copie locale de la liste des fournisseurs Sage.

Conditionnement : quantité Sage = quantité facturée × facteur ; prix Sage = montant / quantité Sage ; le montant de
chaque ligne reste celui de la facture. Règle du propriétaire : deux formats différents = deux articles différents.
"""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path

from rapidfuzz import fuzz, process

from .correspondance import conflit_format, normaliser
from .factures_fournisseurs import TOLERANCE, ZERO, FactureLue, LigneFournisseur, convertir, facteur_propose

EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp"}

# États d'une facture
A_VERIFIER = "À vérifier"
A_SAISIR = "À saisir (photo)"
PRETE = "Prête à importer"
IMPORTEE = "Importée dans Sage"
ETATS = [A_SAISIR, A_VERIFIER, PRETE, IMPORTEE]


@dataclass
class Ligne:
    description: str
    quantite: Decimal
    prix: Decimal
    montant: Decimal
    code: str = ""
    taxable: bool = False
    nature: str = "article"
    numero_sage: str = ""
    description_sage: str = ""
    facteur: Decimal = Decimal(1)
    confirme: bool = False          # correspondance confirmée par le propriétaire (mémorisée)

    @property
    def cle(self) -> str:
        return self.code.strip() or normaliser(self.description)

    def en_sage(self) -> tuple[Decimal, Decimal]:
        return convertir(LigneFournisseur(self.description, self.quantite, self.prix, self.montant), self.facteur)


@dataclass
class Facture:
    fichier: str
    empreinte: str
    fournisseur_lu: str = ""
    fournisseur_sage: str = ""
    numero: str = ""
    date_facture: str = ""          # AAAA-MM-JJ
    lignes: list[Ligne] = field(default_factory=list)
    sous_total: Decimal | None = None
    tps: Decimal = ZERO
    tvq: Decimal = ZERO
    total: Decimal | None = None
    modele: str = ""
    remarques: list[str] = field(default_factory=list)
    etat: str = A_VERIFIER

    @property
    def somme_lignes(self) -> Decimal:
        return sum((l.montant for l in self.lignes), ZERO)

    def controles(self, fournisseurs_sage: set[str] | None = None, deja_dans_sage: bool = False) -> list[str]:
        """Points qui empêchent l'import (liste vide = facture prête)."""
        p = []
        if not self.fournisseur_sage:
            p.append("fournisseur Sage à choisir")
        elif fournisseurs_sage is not None and self.fournisseur_sage not in fournisseurs_sage:
            p.append(f"fournisseur « {self.fournisseur_sage} » absent de Sage")
        if not self.numero:
            p.append("n° de facture manquant")
        try:
            date.fromisoformat(self.date_facture)
        except ValueError:
            p.append("date manquante ou invalide (AAAA-MM-JJ)")
        if not self.lignes:
            p.append("aucune ligne")
        if self.total is None:
            p.append("total manquant")
        else:
            base = self.sous_total if self.sous_total is not None else self.somme_lignes
            if abs(self.somme_lignes - base) > TOLERANCE:
                p.append(f"somme des lignes {self.somme_lignes} ≠ sous-total {base}")
            if abs(base + self.tps + self.tvq - self.total) > TOLERANCE:
                p.append(f"sous-total {base} + taxes {self.tps + self.tvq} ≠ total {self.total}")
        for l in self.lignes:
            if l.nature == "article" and not l.numero_sage:
                p.append(f"article Sage à choisir : {l.description}")
            elif l.nature == "article" and not l.confirme:
                p.append(f"correspondance à confirmer : {l.description}")
            if l.facteur <= 0:
                p.append(f"facteur invalide : {l.description}")
        if deja_dans_sage:
            p.append(f"facture n° {self.numero} déjà dans Sage pour ce fournisseur")
        return p

    # ------------------------------------------------------------ sérialisation
    def en_dict(self) -> dict:
        d = asdict(self)
        return json.loads(json.dumps(d, default=str))

    @classmethod
    def depuis_dict(cls, d: dict) -> "Facture":
        dec = lambda v: None if v in (None, "", "None") else Decimal(str(v))  # noqa: E731
        lignes = [Ligne(**{**l, "quantite": Decimal(l["quantite"]), "prix": Decimal(l["prix"]),
                           "montant": Decimal(l["montant"]), "facteur": Decimal(l.get("facteur", 1))})
                  for l in d.get("lignes", [])]
        return cls(**{**d, "lignes": lignes, "sous_total": dec(d.get("sous_total")), "tps": dec(d.get("tps")) or ZERO,
                      "tvq": dec(d.get("tvq")) or ZERO, "total": dec(d.get("total"))})


def empreinte(chemin: Path) -> str:
    return hashlib.sha1(Path(chemin).read_bytes()).hexdigest()[:16]


def depuis_lecture(lue: FactureLue, chemin: Path) -> Facture:
    f = Facture(fichier=Path(chemin).name, empreinte=empreinte(chemin), fournisseur_lu=lue.fournisseur,
                numero=lue.numero, date_facture=lue.date_facture.isoformat() if lue.date_facture else "",
                sous_total=lue.sous_total, tps=lue.tps, tvq=lue.tvq, total=lue.total, modele=lue.modele,
                remarques=list(lue.remarques))
    f.lignes = [Ligne(l.description, l.quantite, l.prix, l.montant, l.code, l.taxable, l.nature) for l in lue.lignes]
    if lue.modele == "photo":
        f.etat = A_SAISIR
    return f


def lire_facture(chemin: Path) -> Facture:
    """Lecture locale complète : texte du PDF, sinon OCR de Windows (PDF numérisé ou photo imprimée)."""
    from .factures_fournisseurs import lire_fichier, lire_texte

    lue = lire_fichier(chemin)
    if not lue.lignes and lue.modele in ("PDF numérisé", "photo"):
        try:
            from .ocr_windows import texte_image, texte_pdf_numerise

            texte = texte_pdf_numerise(chemin) if Path(chemin).suffix.lower() == ".pdf" else texte_image(chemin)
            lue_ocr = lire_texte(texte, Path(chemin).name)
            lue_ocr.remarques.append("lu par l'OCR de Windows : vérifiez chaque ligne")
            if lue_ocr.lignes or lue.modele == "PDF numérisé":
                lue_ocr.modele = f"OCR ({lue_ocr.modele})"
                lue = lue_ocr
        except Exception as exc:  # l'OCR peut manquer (langue absente) : la facture se saisit à la main
            lue.remarques.append(f"OCR impossible : {exc}")
    facture = depuis_lecture(lue, chemin)
    if facture.etat != A_SAISIR and not facture.lignes:
        facture.etat = A_SAISIR
    return facture


# --------------------------------------------------------------------------------------------- registre
class Registre:
    def __init__(self, racine: Path):
        self.donnees = Path(racine) / "donnees"
        self.dossier = self.donnees / "factures_fournisseurs"
        self.chemin = self.donnees / "factures_fournisseurs.json"
        self.factures: list[Facture] = []
        self.charger()

    def charger(self) -> None:
        if self.chemin.exists():
            self.factures = [Facture.depuis_dict(d) for d in json.loads(self.chemin.read_text(encoding="utf-8"))]

    def enregistrer(self) -> None:
        self.donnees.mkdir(parents=True, exist_ok=True)
        provisoire = self.chemin.with_suffix(".tmp")
        provisoire.write_text(json.dumps([f.en_dict() for f in self.factures], ensure_ascii=False, indent=1),
                              encoding="utf-8")
        provisoire.replace(self.chemin)

    def nouveaux_fichiers(self) -> list[Path]:
        self.dossier.mkdir(parents=True, exist_ok=True)
        connues = {f.empreinte for f in self.factures}
        return [p for p in sorted(self.dossier.iterdir())
                if p.is_file() and p.suffix.lower() in EXTENSIONS and empreinte(p) not in connues]

    def chemin_fichier(self, facture: Facture) -> Path:
        return self.dossier / facture.fichier


# --------------------------------------------------------------------------------------------- correspondance
class MemoireCorrespondance:
    def __init__(self, racine: Path):
        self.chemin = Path(racine) / "donnees" / "correspondance_fournisseurs.json"
        self.donnees = {"fournisseurs": {}, "articles": {}}
        if self.chemin.exists():
            self.donnees.update(json.loads(self.chemin.read_text(encoding="utf-8")))

    def enregistrer(self) -> None:
        self.chemin.parent.mkdir(parents=True, exist_ok=True)
        self.chemin.write_text(json.dumps(self.donnees, ensure_ascii=False, indent=1), encoding="utf-8")

    # noms lus sur les factures -> fournisseur Sage
    def fournisseur(self, nom_lu: str) -> str:
        return self.donnees["fournisseurs"].get(normaliser(nom_lu), "")

    def retenir_fournisseur(self, nom_lu: str, fournisseur_sage: str) -> None:
        if nom_lu:
            self.donnees["fournisseurs"][normaliser(nom_lu)] = fournisseur_sage

    # articles du fournisseur -> article Sage + facteur
    def article(self, fournisseur_sage: str, cle: str) -> dict | None:
        return self.donnees["articles"].get(fournisseur_sage, {}).get(cle)

    def retenir_article(self, fournisseur_sage: str, ligne: Ligne) -> None:
        if not ligne.cle:  # ligne sans code ni désignation : rien à mémoriser
            return
        self.donnees["articles"].setdefault(fournisseur_sage, {})[ligne.cle] = {
            "numero_sage": ligne.numero_sage, "description_sage": ligne.description_sage,
            "facteur": str(ligne.facteur), "description_fournisseur": ligne.description}


def proposer_fournisseur(nom_lu: str, fournisseurs_sage: list[str]) -> str:
    if not nom_lu or not fournisseurs_sage:
        return ""
    normalises = [normaliser(n) for n in fournisseurs_sage]
    meilleur = process.extractOne(normaliser(nom_lu), normalises, scorer=fuzz.token_set_ratio)
    return fournisseurs_sage[meilleur[2]] if meilleur and meilleur[1] >= 80 else ""


def completer(facture: Facture, memoire: MemoireCorrespondance, fournisseurs_sage: list[str], articles_sage: list) -> None:
    """Fournisseur et articles : d'abord la mémoire (confirmé), sinon une proposition à confirmer."""
    if not facture.fournisseur_sage:
        facture.fournisseur_sage = memoire.fournisseur(facture.fournisseur_lu) \
            or proposer_fournisseur(facture.fournisseur_lu, fournisseurs_sage)
    normalises = [normaliser(f"{a.description} {a.numero}") for a in articles_sage]
    for l in facture.lignes:
        if l.nature != "article" or l.confirme:
            continue
        connu = memoire.article(facture.fournisseur_sage, l.cle) if facture.fournisseur_sage else None
        if connu:
            l.numero_sage, l.description_sage = connu["numero_sage"], connu["description_sage"]
            l.facteur, l.confirme = Decimal(connu["facteur"]), True
            continue
        if not l.numero_sage and normalises:
            meilleur = process.extractOne(normaliser(l.description), normalises, scorer=fuzz.token_set_ratio)
            if meilleur and meilleur[1] >= 85 and not conflit_format(l.description, articles_sage[meilleur[2]].description):
                a = articles_sage[meilleur[2]]
                l.numero_sage, l.description_sage = a.numero, a.description
        if l.facteur == 1:
            l.facteur = facteur_propose(l.description) or Decimal(1)


def etat_apres_controle(facture: Facture, problemes: list[str]) -> str:
    if facture.etat == IMPORTEE:
        return IMPORTEE
    if not facture.lignes and facture.etat == A_SAISIR:
        return A_SAISIR
    return PRETE if not problemes else A_VERIFIER


# --------------------------------------------------------------------------------------------- fournisseurs Sage
def lire_copie_fournisseurs(racine: Path) -> list[str]:
    chemin = Path(racine) / "donnees" / "fournisseurs_sage.csv"
    if not chemin.exists():
        return []
    with chemin.open(encoding="utf-8-sig", newline="") as f:
        return [l[0] for l in csv.reader(f, delimiter=";") if l and l[0]]


def ecrire_copie_fournisseurs(racine: Path, noms: list[str]) -> None:
    chemin = Path(racine) / "donnees" / "fournisseurs_sage.csv"
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with chemin.open("w", encoding="utf-8-sig", newline="") as f:
        csv.writer(f, delimiter=";").writerows([[n] for n in noms])


def fournisseurs_actifs(base) -> list[str]:
    return [l["sName"].strip() for l in base.requete("SELECT sName FROM tvendor WHERE bInactive = 0 ORDER BY sName")
            if l["sName"] and l["sName"].strip(" .")]


def facture_existe(base, fournisseur_sage: str, numero: str) -> bool:
    lignes = base.requete("SELECT COUNT(*) n FROM tventr t JOIN tvendor v ON v.lId = t.lVenId "
                          "WHERE v.sName = %s AND TRIM(t.sSource) = %s", (fournisseur_sage, numero.strip()))
    return bool(lignes and lignes[0]["n"])
