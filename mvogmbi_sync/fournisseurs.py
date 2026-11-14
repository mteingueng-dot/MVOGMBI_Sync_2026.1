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
import re
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
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
IMPORTEE = "Importée"  # dans Sage et, sauf case décochée, dans Clover (avant le 2026-11-01 : « Importée dans Sage »)
ANCIEN_IMPORTEE = "Importée dans Sage"
DEJA_DANS_SAGE = "Déjà dans Sage"  # saisie à la main entre-temps : archivée et retirée de la liste (2026-10-28)
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
    taxe: str = ""                  # « GQ », « G » (TPS), « Q » (TVQ), « » ; vide + taxable = « GQ » (taxes.py)

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
    depot: str = ""                  # dépôt (emplacement Sage) qui reçoit la marchandise ; vide = par défaut
    # stock Clover mis à jour à l'import (demande du propriétaire du 2026-11-09 : « la case dans chaque facture, pas
    # sur l'ensemble : on traite deux factures ensemble, une met le stock dans Clover et l'autre pas »)
    maj_clover: bool = True
    # note de crédit du fournisseur (titre « CREDIT » / « NOTE DE CRÉDIT », règle du propriétaire du 2026-11-11) :
    # quantités et montants négatifs, importée comme une facture d'achat négative ; le stock Clover diminue
    note_credit: bool = False
    credit_verifie: bool = False     # titre du document déjà contrôlé (factures lues avant la règle des notes de crédit)

    @property
    def somme_lignes(self) -> Decimal:
        return sum((l.montant for l in self.lignes), ZERO)

    def signer(self, credit: bool | None = None) -> None:
        """Note de crédit : quantités, montants, taxes et total négatifs (prix unitaire positif), qu'ils aient été lus
        ou saisis en positif. `credit` = nouvel état de la case « Note de crédit » : la décocher sur une note de crédit
        remet tout en positif (jamais fait d'office : une vraie facture peut avoir une ligne négative)."""
        avant = self.note_credit
        if credit is not None:
            self.note_credit = bool(credit)
        if self.note_credit:
            changer = lambda v: None if v is None else -abs(v)  # noqa: E731
        elif avant:
            changer = lambda v: None if v is None else abs(v)  # noqa: E731
        else:
            return
        for l in self.lignes:
            l.quantite, l.montant, l.prix = changer(l.quantite), changer(l.montant), abs(l.prix)
        self.sous_total, self.total = changer(self.sous_total), changer(self.total)
        self.tps, self.tvq = changer(self.tps), changer(self.tvq)

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
        d = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        return cls(**{**d, "lignes": lignes, "sous_total": dec(d.get("sous_total")), "tps": dec(d.get("tps")) or ZERO,
                      "tvq": dec(d.get("tvq")) or ZERO, "total": dec(d.get("total"))})


def empreinte(chemin: Path) -> str:
    return hashlib.sha1(Path(chemin).read_bytes(), usedforsecurity=False).hexdigest()[:16]


def depuis_lecture(lue: FactureLue, chemin: Path) -> Facture:
    f = Facture(fichier=Path(chemin).name, empreinte=empreinte(chemin), fournisseur_lu=lue.fournisseur,
                numero=lue.numero, date_facture=lue.date_facture.isoformat() if lue.date_facture else "",
                sous_total=lue.sous_total, tps=lue.tps, tvq=lue.tvq, total=lue.total, modele=lue.modele,
                remarques=list(lue.remarques), note_credit=getattr(lue, "note_credit", False), credit_verifie=True)
    f.lignes = [Ligne(l.description, l.quantite, l.prix, l.montant, l.code, l.taxable, l.nature,
                      taxe=getattr(l, "taxe", "")) for l in lue.lignes]
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

    def _lire_disque(self) -> list[Facture]:
        factures = [Facture.depuis_dict(d) for d in json.loads(self.chemin.read_text(encoding="utf-8"))]
        for f in factures:
            if f.etat == ANCIEN_IMPORTEE:
                f.etat = IMPORTEE
        return factures

    def _date_disque(self) -> float:
        try:
            return self.chemin.stat().st_mtime_ns
        except OSError:
            return 0

    def charger(self) -> None:
        self.factures = self._lire_disque() if self.chemin.exists() else []
        self._lues = {f.fichier: json.dumps(f.en_dict(), sort_keys=True) for f in self.factures}
        self._date = self._date_disque()
        credits = self._reconnaitre_credits()
        if credits or any(f.etat == IMPORTEE for f in self.factures):  # importées d'avant : rangées aux archives
            try:
                self.enregistrer()
            except OSError:
                pass

    def _reconnaitre_credits(self) -> int:
        """Une seule fois par facture lue avant la règle des notes de crédit (2026-11-11) : document intitulé
        « CREDIT » / « NOTE DE CRÉDIT » -> relu en note de crédit ; les articles Sage déjà reliés sont gardés."""
        a_voir = [f for f in self.factures if not f.credit_verifie and f.etat in (A_VERIFIER, A_SAISIR, PRETE)]
        if not a_voir:
            return 0
        from .factures_fournisseurs import est_note_credit, texte_pdf

        nombre = 0
        for f in a_voir:
            f.credit_verifie = True
            chemin = self.chemin_fichier(f)
            try:
                if chemin.suffix.lower() != ".pdf" or not chemin.is_file() or not est_note_credit(texte_pdf(chemin)):
                    continue
                neuve = lire_facture(chemin)
            except Exception:  # noqa: BLE001 — fichier illisible : la facture reste telle quelle
                continue
            reliees = {l.cle: l for l in f.lignes if l.numero_sage}
            for l in neuve.lignes:
                ancienne = reliees.get(l.cle)
                if ancienne:
                    l.numero_sage, l.description_sage = ancienne.numero_sage, ancienne.description_sage
                    l.facteur, l.confirme = ancienne.facteur, ancienne.confirme
            if neuve.lignes:
                f.lignes = neuve.lignes
                f.sous_total, f.tps, f.tvq, f.total = neuve.sous_total, neuve.tps, neuve.tvq, neuve.total
            f.numero = f.numero or neuve.numero
            f.date_facture = f.date_facture or neuve.date_facture
            f.remarques = list(dict.fromkeys(f.remarques + neuve.remarques))
            f.signer(credit=True)
            if f.etat == A_SAISIR and f.lignes:
                f.etat = A_VERIFIER
            if f.etat == PRETE:
                f.etat = A_VERIFIER  # à revoir : montants passés en négatif
            nombre += 1
        return nombre

    def change_ailleurs(self) -> bool:
        """Le fichier a-t-il été écrit par une autre plateforme (web, Windows, nuit) depuis la lecture ?"""
        return self._date_disque() != getattr(self, "_date", None)

    def enregistrer(self) -> None:
        """Écrit la liste. Mêmes données pour le web, Windows et la nuit (demande du propriétaire du 2026-11-05 :
        « les deux plateformes doivent avoir le même statut en temps réel ») : si une autre a écrit entre-temps,
        seules les factures modifiées, ajoutées ou retirées ICI remplacent celles du disque (jamais d'écrasement
        d'un import fait ailleurs)."""
        # archivées : plus à traiter ; une facture importée passe dans « Factures fournisseurs archivées » (demande du
        # propriétaire du 2026-11-08 : « les factures importées ne doivent plus figurer dans la liste »)
        self.factures = [f for f in self.factures
                         if f.etat != DEJA_DANS_SAGE and not (f.etat == IMPORTEE and ranger_importee(self.donnees.parent, f))]
        self.donnees.mkdir(parents=True, exist_ok=True)
        lues = getattr(self, "_lues", {})
        if self.chemin.exists() and self.change_ailleurs():
            locales = {f.fichier: f for f in self.factures}
            changees = {n for n, f in locales.items()
                        if lues.get(n) != json.dumps(f.en_dict(), sort_keys=True)}
            retirees = set(lues) - set(locales)
            fusion = []
            for f in self._lire_disque():
                if f.fichier in retirees or f.etat == DEJA_DANS_SAGE:
                    continue
                if f.etat == IMPORTEE and ranger_importee(self.donnees.parent, f):
                    continue  # importée ailleurs : aux archives
                ici = locales.get(f.fichier)
                if f.fichier in changees and not (f.etat == IMPORTEE and ici.etat != IMPORTEE):
                    fusion.append(ici)  # importée ailleurs : jamais ramenée à « Prête à importer »
                else:
                    fusion.append(f)
            vues = {f.fichier for f in fusion}
            # ajoutées ici (une facture lue au départ et disparue du disque a été archivée ou supprimée ailleurs)
            fusion += [f for n, f in locales.items() if n in changees and n not in vues and n not in lues]
            # les objets gardés en mémoire suivent la fusion (même état partout)
            self.factures[:] = fusion
        provisoire = self.chemin.with_suffix(".tmp")
        provisoire.write_text(json.dumps([f.en_dict() for f in self.factures], ensure_ascii=False, indent=1),
                              encoding="utf-8")
        provisoire.replace(self.chemin)
        self._lues = {f.fichier: json.dumps(f.en_dict(), sort_keys=True) for f in self.factures}
        self._date = self._date_disque()

    def nouveaux_fichiers(self) -> list[Path]:
        self.dossier.mkdir(parents=True, exist_ok=True)
        connues = {f.empreinte for f in self.factures}
        return [p for p in sorted(self.dossier.iterdir())
                if p.is_file() and p.suffix.lower() in EXTENSIONS and empreinte(p) not in connues]

    def chemin_fichier(self, facture: Facture) -> Path:
        return self.dossier / facture.fichier

    def supprimer(self, facture: Facture) -> Path | None:
        """Facture supprimée de la liste (doublon, erreur…) ; son fichier est rangé dans « supprimees » (copie
        gardée, jamais relu ni retéléchargé : la mémoire du courriel retient son empreinte)."""
        return self.ecarter(facture, "supprimees")

    def ecarter(self, facture: Facture, sous_dossier: str = "ecartees") -> Path | None:
        """Retire la facture de la liste à traiter ; son fichier est rangé dans « ecartees » (rien n'est détruit).

        Pour la traiter plus tard : remettre le fichier dans le dossier des factures, puis « Actualiser ».
        """
        cible = None
        source = self.chemin_fichier(facture)
        if source.exists():
            dossier = self.dossier / sous_dossier
            dossier.mkdir(parents=True, exist_ok=True)
            cible = dossier / source.name
            numero = 2
            while cible.exists():
                cible = dossier / f"{source.stem} ({numero}){source.suffix}"
                numero += 1
            source.replace(cible)
        self.factures.remove(facture)
        self.enregistrer()
        return cible


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


_TAILLE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(kg|kgs|g|gr|lb|lbs|ml|cl|l|litres?|oz)\b", re.I)
_EN_G_OU_ML = {"kg": 1000, "kgs": 1000, "g": 1, "gr": 1, "lb": 453.592, "lbs": 453.592, "oz": 28.3495,
               "ml": 1, "cl": 10, "l": 1000, "litre": 1000, "litres": 1000}


def taille_unite(texte: str) -> tuple[float, str] | None:
    """Taille d'une unité (en g ou en ml) d'après la désignation : la dernière taille écrite, sans le nombre
    d'unités de la caisse (« 6/5 Lb » -> 5 lb, « 12x170g » -> 170 g, « 4X6 0,330 L » -> 330 ml)."""
    trouve = list(_TAILLE.finditer(texte or ""))
    if not trouve:
        return None
    m = trouve[-1]
    unite = m.group(2).lower()
    valeur = float(m.group(1).replace(",", ".")) * _EN_G_OU_ML[unite]
    return (valeur, "volume" if unite in ("ml", "cl", "l", "litre", "litres") else "masse") if valeur else None


def conflit_format_achat(description_fournisseur: str, description_sage: str) -> bool:
    """Formats d'achat différents (demande du propriétaire du 2026-11-09 : « les articles de la facture du
    fournisseur, je dois les relier à mes articles ») : le fournisseur vend souvent à la caisse (« 6/5 Lb » = 6 sacs
    de 5 lb, le facteur fait la conversion) ; seule la taille d'une unité compte (3 % d'écart permis : 5 lb = 2,27 kg).
    Sans taille d'un côté : pas de conflit."""
    a, b = taille_unite(description_fournisseur), taille_unite(description_sage)
    if not a or not b:
        return False
    if a[1] != b[1]:
        return True
    return abs(a[0] - b[0]) > max(a[0], b[0]) * 0.03


def article_saisi(numero: str, description: str, articles):
    """Article Sage tapé directement dans la carte de la ligne (demande du propriétaire du 2026-11-10 : « saisir
    directement le code de l'article avec assistant et la désignation aussi ») : n° exact (majuscules ignorées, ou
    « n° — description » de l'assistant), sinon désignation identique (normalisée) d'un seul article."""
    numero = (numero or "").split(" — ")[0].strip().upper()
    if numero:
        a = next((x for x in articles if x.numero.strip().upper() == numero), None)
        if a is not None:
            return a
    cle = normaliser(description or "")
    if cle:
        trouves = [x for x in articles if normaliser(x.description) == cle]
        if len(trouves) == 1:
            return trouves[0]
    return None


_AU_POIDS = re.compile(r"\ben\s*(lb|lbs|livres?|kg)\b", re.I)


def facteur_achat(description_fournisseur: str, description_sage: str) -> Decimal | None:
    """Facteur proposé pour un article Sage vendu au poids (« … en Lb », « … en kg ») : poids d'une unité
    facturée (unités de la caisse × poids de l'unité) dans l'unité de Sage (« Ailes de dinde 10kg » -> 22,046 lb,
    « 6/5 Lb » -> 30 lb) ; sinon le nombre d'unités de la caisse (factures_fournisseurs.facteur_propose)."""
    from .factures_fournisseurs import facteur_propose

    m = _AU_POIDS.search(description_sage or "")
    taille = taille_unite(description_fournisseur)
    if m and taille and taille[1] == "masse":
        unite = 1000.0 if m.group(1).lower() == "kg" else 453.592
        nombre = facteur_propose(description_fournisseur) or Decimal(1)
        return (nombre * Decimal(str(taille[0] / unite))).quantize(Decimal("0.001"))
    return facteur_propose(description_fournisseur)


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
            # parmi les 8 plus ressemblants dont l'unité a la même taille (la caisse ne compte pas) ; le nom entier
            # doit aussi se ressembler (« Okra » n'est pas « Shana Okra Whole 300g ») ; à égalité, le plus proche
            # sur le nom entier (« Light Lime » avant « Light Double Lime »)
            nom = normaliser(l.description)
            candidats = []
            for _n, score, k in process.extract(nom, normalises, scorer=fuzz.token_set_ratio, limit=8):
                entier = fuzz.token_sort_ratio(nom, normalises[k])
                if score >= 80 and entier >= 40 and not conflit_format_achat(l.description,
                                                                             articles_sage[k].description):
                    candidats.append((score, entier, k))
            if candidats:
                a = articles_sage[max(candidats)[2]]
                l.numero_sage, l.description_sage = a.numero, a.description
                if l.facteur == 1 or l.facteur == (facteur_propose(l.description) or 1):  # pas changé à la main
                    l.facteur = facteur_achat(l.description, a.description) or l.facteur
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


# --------------------------------------------------------------------------------------------- archives
ARCHIVES = Path("archives") / "factures_fournisseurs"


def nom_archive(facture: Facture) -> str:
    """« 2026-08-20 Nourriture D'afrique n° 14402 » (caractères interdits par Windows remplacés)."""
    texte = f"{facture.date_facture or 'sans date'} {facture.fournisseur_sage or facture.fournisseur_lu} n° {facture.numero}"
    return re.sub(r'[\\/:*?"<>|]+', "-", texte).strip()[:150]


def archiver(racine: Path, facture: Facture) -> Path:
    """Facture importée gardée pour consultation (donnees/archives/factures_fournisseurs/AAAA/) : copie du PDF ou
    de la photo, détail complet en JSON (en-tête, lignes, articles Sage, facteurs) et feuille Excel lisible.
    Renvoie le fichier JSON ; refaire l'archive d'une facture la remplace."""
    import shutil

    from .export_tableau import ecrire_excel

    dossier = Path(racine) / "donnees" / ARCHIVES / (facture.date_facture[:4] or "sans date")
    dossier.mkdir(parents=True, exist_ok=True)
    base = dossier / nom_archive(facture)
    source = Path(racine) / "donnees" / "factures_fournisseurs" / facture.fichier
    if source.exists():
        shutil.copy2(source, base.with_name(base.name + source.suffix.lower()))
    donnees = facture.en_dict()
    donnees["archivee_le"] = datetime.now().isoformat(timespec="seconds")
    donnees["fichier_archive"] = base.name + source.suffix.lower() if source.exists() else ""
    chemin = base.with_name(base.name + ".json")
    chemin.write_text(json.dumps(donnees, ensure_ascii=False, indent=1), encoding="utf-8")
    entetes = ["Description", "Code", "Qté", "Prix fournisseur", "Montant", "N° Sage", "Article Sage", "Facteur",
               "Qté Sage"]
    lignes = [[l.description, l.code, str(l.quantite), str(l.prix), str(l.montant), l.numero_sage, l.description_sage,
               str(l.facteur), str((l.quantite * l.facteur).quantize(Decimal("0.0001")))] for l in facture.lignes]
    lignes += [[], ["Fournisseur Sage", facture.fournisseur_sage], ["N° de facture", facture.numero],
               ["Date", facture.date_facture], ["Sous-total", str(facture.sous_total or "")],
               ["TPS", str(facture.tps)], ["TVQ", str(facture.tvq)], ["Total", str(facture.total or "")],
               ["Fichier d'origine", facture.fichier]]
    ecrire_excel(base.with_name(base.name + ".xlsx"), "Facture", entetes, lignes)
    return chemin


def chemin_archive(racine: Path, facture: Facture) -> Path:
    return (Path(racine) / "donnees" / ARCHIVES / (facture.date_facture[:4] or "sans date")
            / (nom_archive(facture) + ".json"))


def ranger_importee(racine: Path, facture: Facture) -> bool:
    """Facture importée : archivée (si ce n'est déjà fait à l'import) puis son fichier d'origine retiré du dossier
    des factures (une copie est dans l'archive ; sinon il serait relu comme une nouvelle facture). Vrai si elle peut
    quitter la liste."""
    try:
        if not chemin_archive(racine, facture).exists():
            archiver(racine, facture)
        source = Path(racine) / "donnees" / "factures_fournisseurs" / facture.fichier
        if facture.fichier and source.exists():
            source.unlink()
        return True
    except OSError:
        return False  # archive impossible pour l'instant : la facture reste dans la liste


def archiver_deja_dans_sage(racine: Path, facture: Facture, numero_sage: str) -> Path:
    """Règle du propriétaire (2026-10-28) : une facture prête à importer qui est déjà dans Sage (saisie à la main)
    est archivée et retirée de la liste des factures à traiter. Le fichier d'origine passe dans l'archive (copie
    gardée) ; la facture disparaît du registre au prochain enregistrement."""
    facture.etat = DEJA_DANS_SAGE
    facture.remarques = list(dict.fromkeys(facture.remarques + [f"déjà dans Sage (n° « {numero_sage} ») : archivée "
                                                                 f"le {date.today()} sans import"]))
    chemin = archiver(racine, facture)
    source = Path(racine) / "donnees" / "factures_fournisseurs" / facture.fichier
    if source.exists():
        source.unlink()  # copie gardée dans l'archive
    return chemin


def deja_dans_sage_fichiers(base, factures: list[Facture]) -> dict[str, str]:
    from .import_achats import deja_dans_sage

    return deja_dans_sage(base, factures)


def archiver_pretes_deja_dans_sage(racine: Path, base, registre: "Registre | None" = None) -> list[Facture]:
    """Archive les factures « Prête à importer » déjà présentes dans Sage ; renvoie les factures archivées."""
    from .import_achats import deja_dans_sage

    registre = registre or Registre(racine)
    pretes = [f for f in registre.factures if f.etat == PRETE]
    trouvees = deja_dans_sage(base, pretes)
    archivees = []
    for f in pretes:
        if f.fichier in trouvees:
            archiver_deja_dans_sage(racine, f, trouvees[f.fichier])
            archivees.append(f)
    if archivees:
        registre.enregistrer()
    return archivees


def refaire_clover_archive(racine: Path, config_toml: dict, archive: dict) -> list[str]:
    """« 🔁 Refaire la mise à jour Clover » d'une facture archivée (demande du propriétaire du 2026-11-08 : l'action
    passe sur la page des archives, puisque les factures importées quittent la liste) : stock et coût Clover des
    lignes pas encore faites ; le journal du stock Clover écarte les lignes déjà ajoutées."""
    from .import_achats import mettre_a_jour_clover

    facture = Facture.depuis_dict({k: v for k, v in archive.items() if k not in ("chemin", "archivee_le",
                                                                                 "fichier_archive")})
    if facture.etat != IMPORTEE:
        return [f"{facture.numero} : facture archivée sans import par l'application ({facture.etat}) : Clover n'a "
                "pas à être mis à jour."]
    return [f"{x} : {texte}" for x, texte in mettre_a_jour_clover(racine, config_toml, [facture],
                                                                   {facture.fichier: ""}).items()]


def nombre_archives(racine: Path) -> int:
    """Nombre de factures dans « Factures fournisseurs archivées » (résumé de la liste)."""
    return sum(1 for _ in (Path(racine) / "donnees" / ARCHIVES).glob("*/*.json"))


def archives(racine: Path) -> list[dict]:
    """Toutes les factures archivées (les plus récentes d'abord) ; « chemin » = fichier JSON."""
    resultat = []
    for chemin in (Path(racine) / "donnees" / ARCHIVES).glob("*/*.json"):
        try:
            d = json.loads(chemin.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        d["chemin"] = str(chemin)
        resultat.append(d)
    return sorted(resultat, key=lambda d: (d.get("date_facture", ""), d.get("numero", "")), reverse=True)


def archiver_importees(racine: Path) -> int:
    """Archive les factures importées qui ne le sont pas encore (factures d'avant les archives) ; renvoie leur nombre."""
    registre = Registre(racine)
    deja = {(d.get("fournisseur_sage"), d.get("numero")) for d in archives(racine)}
    nouvelles = [f for f in registre.factures if f.etat == IMPORTEE and (f.fournisseur_sage, f.numero) not in deja]
    for f in nouvelles:
        archiver(racine, f)
    return len(nouvelles)
