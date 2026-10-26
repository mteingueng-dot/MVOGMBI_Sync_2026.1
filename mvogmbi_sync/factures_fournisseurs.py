"""Lecture des factures fournisseurs (PDF) : fournisseur, n°, date, lignes, taxes et total.

Lecture locale d'abord (texte des PDF numériques, un modèle par fournisseur connu, puis un modèle générique) ;
la lecture est jugée fiable seulement si la somme des lignes, les taxes et le total concordent (au cent près).
Les PDF numérisés et les photos imprimées passent par l'OCR de Windows (module `ocr_windows`) ; les factures
manuscrites se saisissent dans la page.

Les montants sont lus aussi bien au format anglais (1,573.85) que français (1 200,00).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

ZERO = Decimal("0")
TOLERANCE = Decimal("0.02")

MOIS = {"jan": 1, "janv": 1, "janvier": 1, "fév": 2, "fev": 2, "févr": 2, "février": 2, "feb": 2, "mar": 3, "mars": 3,
        "avr": 4, "avril": 4, "apr": 4, "mai": 5, "may": 5, "juin": 6, "jun": 6, "juil": 7, "juillet": 7, "jul": 7,
        "août": 8, "aout": 8, "aug": 8, "sep": 9, "sept": 9, "septembre": 9, "oct": 10, "octobre": 10, "nov": 11,
        "novembre": 11, "déc": 12, "dec": 12, "décembre": 12}


@dataclass
class LigneFournisseur:
    description: str
    quantite: Decimal
    prix: Decimal
    montant: Decimal
    code: str = ""                 # code de l'article chez le fournisseur
    taxable: bool = False
    nature: str = "article"        # « article » ou « frais » (consigne, transport…)


@dataclass
class FactureLue:
    fichier: str
    fournisseur: str = ""
    numero: str = ""
    date_facture: date | None = None
    lignes: list[LigneFournisseur] = field(default_factory=list)
    sous_total: Decimal | None = None
    tps: Decimal = ZERO
    tvq: Decimal = ZERO
    total: Decimal | None = None
    modele: str = ""               # modèle de lecture utilisé (ou « IA »)
    remarques: list[str] = field(default_factory=list)

    @property
    def somme_lignes(self) -> Decimal:
        return sum((l.montant for l in self.lignes), ZERO)

    def controles(self) -> list[str]:
        """Écarts qui empêchent de considérer la lecture comme fiable (liste vide = facture cohérente)."""
        problemes = []
        if not self.fournisseur:
            problemes.append("fournisseur non lu")
        if not self.numero:
            problemes.append("n° de facture non lu")
        if not self.date_facture:
            problemes.append("date non lue")
        if not self.lignes:
            problemes.append("aucune ligne lue")
        if self.sous_total is not None and abs(self.somme_lignes - self.sous_total) > TOLERANCE:
            problemes.append(f"somme des lignes {self.somme_lignes} ≠ sous-total {self.sous_total}")
        if self.total is None:
            problemes.append("total non lu")
        else:
            base = self.sous_total if self.sous_total is not None else self.somme_lignes
            if abs(base + self.tps + self.tvq - self.total) > TOLERANCE:
                problemes.append(f"sous-total {base} + taxes {self.tps + self.tvq} ≠ total {self.total}")
        for l in self.lignes:
            if l.quantite and abs(l.quantite * l.prix - l.montant) > TOLERANCE + Decimal("0.01") * l.quantite:
                problemes.append(f"ligne « {l.description} » : {l.quantite} × {l.prix} ≠ {l.montant}")
        return problemes

    @property
    def fiable(self) -> bool:
        return not self.controles()


# --------------------------------------------------------------------------------------------- outils de lecture
def montant(texte: str) -> Decimal:
    """« $1,751.20 », « 1 200,00 $ », « 27.800$ », « -2.35$ » -> Decimal."""
    t = texte.replace("$", "").replace(" ", "").replace("\xa0", "").replace(" ", "").replace("CAD", "").strip()
    if "," in t and "." in t:
        t = t.replace(",", "")  # 1,573.85
    elif "," in t:
        entier, _, decimales = t.rpartition(",")
        t = f"{entier.replace(',', '')}.{decimales}" if len(decimales) in (1, 2, 3) else t.replace(",", "")
    try:
        return Decimal(t)
    except InvalidOperation:
        raise ValueError(f"montant illisible : {texte!r}")


def lire_date(texte: str) -> date | None:
    t = texte.strip().lower().replace(".", "")
    for motif, ordre in ((r"(\d{4})-(\d{1,2})-(\d{1,2})", "amj"), (r"(\d{1,2})[-/](\d{1,2})[-/](\d{4})", "jma")):
        m = re.search(motif, t)
        if m:
            a, b, c = (int(x) for x in m.groups())
            annee, mois, jour = (a, b, c) if ordre == "amj" else (c, b, a)
            try:
                return date(annee, mois, jour)
            except ValueError:
                pass
    m = re.search(r"(\d{1,2})[\s-]+([a-zéû]+)[\s-]+(\d{4})", t)  # 22-oct-2026, 10 sept 2026
    if m and m.group(2) in MOIS:
        return date(int(m.group(3)), MOIS[m.group(2)], int(m.group(1)))
    m = re.search(r"([a-zéû]+)\s+(\d{1,2}),?\s+(\d{4})", t)  # août 20, 2026
    if m and m.group(1) in MOIS:
        return date(int(m.group(3)), MOIS[m.group(1)], int(m.group(2)))
    return None


def chercher(motif: str, texte: str, groupe: int = 1, drapeaux=re.IGNORECASE) -> str:
    m = re.search(motif, texte, drapeaux)
    return m.group(groupe).strip() if m else ""


def texte_pdf(chemin: Path) -> str:
    import pdfplumber

    with pdfplumber.open(chemin) as pdf:
        # dedupe_chars : certains PDF écrivent les titres en gras en superposant 2 à 4 fois chaque lettre
        return "\n".join((page.dedupe_chars().extract_text() or "") for page in pdf.pages)


NOMBRE = r"-?\$?\s?[\d\s.,]*\d(?:[.,]\d{1,3})?\s?\$?"


# --------------------------------------------------------------------------------------------- modèles par fournisseur
def _produits_des_champs(texte: str, f: FactureLue) -> None:
    f.fournisseur = "Produits des Champs"
    f.numero = chercher(r"FACTURE No\s*:\s*(\d+)", texte)
    f.date_facture = lire_date(chercher(r"Date Facture\s*:\s*([\d-]+)", texte))
    lignes = texte.splitlines()
    for i, ligne in enumerate(lignes):
        # « 113 Colombina … 12 un 12 un 27.800$ Ca 27.80$ » ; au poids : « 1109 … 5 kg 5.00 kg 113.050$ Ca 113.05$ »
        m = re.match(r"^(\d+) (.+?) ([\d.]+) (?:un|kg) ([\d.]+) (?:un|kg) ([\d.,]+)\$ (\w+) ([\d.,]+)\$(TX)?$", ligne)
        if not m:
            continue
        code, description, _, _, prix, unite, total, taxe = m.groups()
        suite = re.match(rf"^{code} (\d+) {unite}\s*(\d*)\s*{unite}$", lignes[i + 1]) if i + 1 < len(lignes) else None
        expedie = Decimal(suite.group(2)) if suite and suite.group(2) else ZERO
        if not expedie and montant(prix):  # pas de ligne de caisses : quantité = total / prix
            expedie = (montant(total) / montant(prix)).quantize(Decimal("0.001"))
        if montant(total) == 0:
            f.remarques.append(f"{code} {description} : non livré (0 caisse expédiée), ignoré.")
            continue
        f.lignes.append(LigneFournisseur(description, expedie, montant(prix), montant(total), code, bool(taxe)))
    # « Sous-total :non taxable » est en fait le total des marchandises ; les consignes sont déjà dans les lignes
    marchandises = chercher(r"Sous-total\s*:non taxable\s*:\s*([\d.,]+)\$", texte)
    consignes = chercher(r"Consignes\s*:\s*([\d.,]+)\$", texte)
    if marchandises:
        f.sous_total = montant(marchandises) + montant(consignes or "0")
        if consignes:
            f.remarques.append(f"consignes {consignes} $ comprises dans les lignes")
    f.tps = montant(chercher(r"^TPS ([\d.,]+)\$", texte, drapeaux=re.M) or "0")
    f.tvq = montant(chercher(r"TVQ ([\d.,]+)\$\s*$", texte, drapeaux=re.M) or "0")
    total = chercher(r"Total à payer\s*:\s*CAD\s*([\d.,]+)\$", texte)
    f.total = montant(total) if total else None


def _labatt(texte: str, f: FactureLue) -> None:
    f.fournisseur = "La Brasserie Labatt Limitée"
    f.numero = chercher(r"N[º°o]\s*:\s*(\d+)\s+Référence", texte)
    f.date_facture = lire_date(chercher(r"Référence:\s*\d+\s+Date:\s*([\d/]+)", texte))
    lignes = texte.splitlines()
    courant = None
    for ligne in lignes:
        m = re.match(r"^Achat (\d+) (.+?) (\d+) (PC|CS|UN|BT|CAN) ([\d.,]+)\$ ([\d.,]+)\$$", ligne)
        if m:
            courant = {"code": m.group(1), "description": m.group(2), "quantite": Decimal(m.group(3))}
            continue
        m = re.match(r"^([\d.,]+)\$ ([\d.,]+)\$(T?) ([\d.,]+)\$ ([\d.,]+)\$$", ligne)
        if m and courant:
            prix, total, taxe, _, consigne = m.groups()
            f.lignes.append(LigneFournisseur(courant["description"], courant["quantite"], montant(prix), montant(total),
                                             courant["code"], taxe == "T"))
            if montant(consigne):
                f.lignes.append(LigneFournisseur(f"Consigne {courant['description']}", courant["quantite"],
                                                 montant(consigne) / courant["quantite"], montant(consigne),
                                                 courant["code"], False, "frais"))
            courant = None
    avant_taxes = chercher(r"Sous-Total Avant Taxes:\s*([\d.,]+)\$", texte)
    consigne = chercher(r"Total Dépôt / Consigne:\s*([\d.,]+)\$", texte)
    f.sous_total = montant(avant_taxes) + montant(consigne or "0") if avant_taxes else None
    f.tps = montant(chercher(r"GST:\s*[\d.,]+%\s*([\d.,]+)\$", texte) or "0")
    f.tvq = montant(chercher(r"QST:\s*[\d.,]+%\s*([\d.,]+)\$", texte) or "0")
    total = chercher(r"^Total:\s*([\d.,]+)\$", texte, drapeaux=re.M)
    f.total = montant(total) if total else None


def _amr(texte: str, f: FactureLue) -> None:
    f.fournisseur = "A.M.R. Cash and Carry Inc."
    f.numero = chercher(r"Facture #:\s*(\S+)", texte)
    f.date_facture = lire_date(chercher(r"^Date:\s*(.+)$", texte, drapeaux=re.M | re.I))
    for ligne in texte.splitlines():
        m = re.match(r"^(\d{3,}) (\d+(?:\.\d+)?) (.+?) \$([\d.,]+) \$([\d.,]+)$", ligne)
        if m:
            code, qte, description, prix, total = m.groups()
            f.lignes.append(LigneFournisseur(description, Decimal(qte), montant(prix), montant(total), code))
    f.sous_total = montant(chercher(r"SOUS-TOTAL:\s*\$([\d.,]+)", texte) or "0") or None
    f.tps = montant(chercher(r"%TPS \([^)]*\)\s*\$([\d.,]+)", texte) or "0")
    f.tvq = montant(chercher(r"%TVQ \([^)]*\)\s*\$([\d.,]+)", texte) or "0")
    total = chercher(r"^TOTAL:\s*\$([\d.,]+)", texte, drapeaux=re.M)
    f.total = montant(total) if total else None


def _basmex(texte: str, f: FactureLue) -> None:
    f.fournisseur = "Basmex"
    f.numero = chercher(r"N° facture:\s*(\S+)", texte)
    f.date_facture = lire_date(chercher(r"^Date:\s*(\S+)", texte, drapeaux=re.M))
    for ligne in texte.splitlines():
        m = re.match(r"^(\d+(?:[.,]\d+)?) ([A-Z]{1,4}\d+\S*) (.+?) ([\d.,]+) ([\d.,]+)(?: (G|Q|GQ|T))?$", ligne)
        if m:
            qte, code, description, prix, total, taxe = m.groups()
            f.lignes.append(LigneFournisseur(description, montant(qte), montant(prix), montant(total), code, bool(taxe)))
    f.sous_total = montant(chercher(r"Sous-total:\s*([\d.,]+)", texte) or "0") or None
    f.tps = montant(chercher(r"TPS[^\n]*?:\s*([\d.,]+)\s*$", texte, drapeaux=re.M) or "0") \
        if re.search(r"^TPS\s*:", texte, re.M) else ZERO
    f.tvq = montant(chercher(r"^TVQ\s*:\s*([\d.,]+)", texte, drapeaux=re.M) or "0")
    total = chercher(r"Montant total\s*([\d.,]+)", texte)
    f.total = montant(total) if total else None


def _al_raji(texte: str, f: FactureLue) -> None:
    f.fournisseur = "Les Aliments Al-Raji"
    f.numero = chercher(r"N° de Facture:\s*(\S+)", texte)
    f.date_facture = lire_date(chercher(r"Date du Facture:\s*(\S+)", texte))
    for ligne in texte.splitlines():
        m = re.match(r"^\d+\. (.+?) (\d+(?:,\d+)?) ([\d\s]+,\d{2}) \$ ([\d\s]+,\d{2}) \$ (\w+)$", ligne)
        if m:
            description, qte, prix, total, taxe = m.groups()
            if montant(total) == 0:
                f.remarques.append(f"{description} : ligne à 0,00 $ (gratuité), ignorée.")
                continue
            f.lignes.append(LigneFournisseur(description, montant(qte), montant(prix), montant(total), "",
                                             taxe.lower() not in ("exonéré", "exonere", "exempt")))
    total = chercher(r"^Total ([\d\s]+,\d{2}) \$", texte, drapeaux=re.M)
    f.total = montant(total) if total else None
    f.sous_total = f.total


def _11983938(texte: str, f: FactureLue) -> None:
    f.fournisseur = "11983938 Canada Inc"
    f.numero = chercher(r"N° de facture:\s*(\S+)", texte)
    f.date_facture = lire_date(chercher(r"Date:\s*(.+)$", texte, drapeaux=re.M))
    for ligne in texte.splitlines():
        m = re.match(r"^(\d+(?:[.,]\d+)?) (.+?) ([\d.,]+)\$ ([\d.,]+)\$$", ligne)
        if m:
            qte, description, prix, total = m.groups()
            f.lignes.append(LigneFournisseur(description, montant(qte), montant(prix), montant(total)))
    total = chercher(r"^Total ([\d.,]+)\$", texte, drapeaux=re.M)
    f.total = montant(total) if total else None
    f.sous_total = f.total


def _mer_de_la_guinee(texte: str, f: FactureLue) -> None:
    f.fournisseur = "Mer de la Guinée inc."
    f.numero = chercher(r"INVOICE N[º°o]\s*(\S+)", texte)
    f.date_facture = lire_date(chercher(r"DATE\s+([\d/]+)", texte))
    dans_lignes = False
    for ligne in texte.splitlines():
        if ligne.startswith("DESCRIPTION"):
            dans_lignes = True
            continue
        if not dans_lignes:
            continue
        m = re.match(r"^(.+?) (\d+(?:[.,]\d+)?) ([\d.,]+) ([\d.,]+)$", ligne)
        if m and not ligne.startswith(("PAIEMENT", "TOTAL", "SOUS")):
            description, qte, prix, total = m.groups()
            f.lignes.append(LigneFournisseur(description, montant(qte), montant(prix), montant(total)))
        elif re.match(r"^\(.+\)$", ligne) and f.lignes:  # précision sur la ligne précédente : « (poisson raie) »
            f.lignes[-1].description += f" {ligne}"
        elif ligne.startswith(("PAIEMENT", "$")):
            dans_lignes = False
    f.sous_total = f.somme_lignes or None
    f.total = f.sous_total
    paiement = chercher(r"^PAIEMENT ([\d.,]+)", texte, drapeaux=re.M)
    solde = chercher(r"^\$([\d.,]+)\s*\n\s*SOLDE", texte, drapeaux=re.M)
    if paiement:
        f.remarques.append(f"acompte déjà payé : {paiement} $ ; solde à payer : {solde or '?'} $")


def _generique(texte: str, f: FactureLue) -> None:
    """Dernier recours : lignes « quantité description prix total » et mots-clés usuels des totaux."""
    f.numero = f.numero or chercher(r"(?:facture|invoice)\s*(?:n[°ºo]|#|no)\s*[:.]?\s*([A-Z0-9-]+)", texte)
    f.date_facture = f.date_facture or lire_date(chercher(r"date[^:\n]*:\s*([^\n]+)", texte))
    for ligne in texte.splitlines():
        m = re.match(r"^(\d+(?:[.,]\d+)?) (.+?) \$?([\d\s.,]+\d)\s?\$? \$?([\d\s.,]+\d)\s?\$?$", ligne)
        if m:
            try:
                qte, prix, total = montant(m.group(1)), montant(m.group(3)), montant(m.group(4))
            except ValueError:
                continue
            if qte and abs(qte * prix - total) <= TOLERANCE:
                f.lignes.append(LigneFournisseur(m.group(2), qte, prix, total))
    total = chercher(r"(?:total à payer|montant total|grand total|total)\s*:?\s*\$?\s*([\d\s.,]+\d)", texte)
    f.total = montant(total) if total else None


MODELES = [
    ("Produits des Champs", re.compile(r"Produits des Champs", re.I), _produits_des_champs),
    ("Labatt", re.compile(r"Brasserie Labatt", re.I), _labatt),
    ("A.M.R.", re.compile(r"A\.M\.R\. CASH AND CARRY", re.I), _amr),
    ("Basmex", re.compile(r"basmex", re.I), _basmex),
    ("Al-Raji", re.compile(r"ALIMENTS AL-RAJI", re.I), _al_raji),
    ("11983938 Canada", re.compile(r"11983938 Canada", re.I), _11983938),
    ("Mer de la Guinée", re.compile(r"Mer de la Guin[ée]e", re.I), _mer_de_la_guinee),
]


def facteur_propose(description: str) -> Decimal | None:
    """Unités contenues dans l'unité facturée, d'après la désignation du fournisseur (à confirmer par le propriétaire).

    « 12/276 g » -> 12 ; « 36 x 190g » -> 36 ; « 4X6 0,330 L » -> 24 ; « (15 x 1.5 kg) » -> 15 ; « 6/5 Lb » -> 6.
    Rien de reconnaissable -> None (1 pour 1 par défaut, à vérifier).
    """
    t = description.lower()
    m = re.search(r"(\d+)\s*x\s*(\d+)\s+\d", t)  # 4X6 0,330 L : 4 paquets de 6
    if m:
        return Decimal(int(m.group(1)) * int(m.group(2)))
    m = re.search(r"(\d+)\s*[/x]\s*\d+(?:[.,]\d+)?\s*(?:/\s*\d+(?:[.,]\d+)?\s*)?(?:g|kg|ml|l|lb|lbs|oz)\b", t)
    if m:
        return Decimal(m.group(1))
    m = re.search(r"\b(\d+)\s*x\s*(\d+)\b", t)  # 1X12
    if m:
        return Decimal(int(m.group(1)) * int(m.group(2)))
    return None


def convertir(ligne: LigneFournisseur, facteur: Decimal) -> tuple[Decimal, Decimal]:
    """Quantité et prix unitaire dans l'unité de Sage ; le montant de la ligne reste celui de la facture."""
    quantite = (ligne.quantite * facteur).quantize(Decimal("0.001"))
    prix = (ligne.montant / quantite).quantize(Decimal("0.0001")) if quantite else ZERO
    return quantite, prix


def lire_texte(texte: str, fichier: str = "") -> FactureLue:
    facture = FactureLue(fichier)
    for nom, motif, lecteur in MODELES:
        if motif.search(texte):
            facture.modele = nom
            lecteur(texte, facture)
            return facture
    facture.modele = "générique"
    _generique(texte, facture)
    return facture


def lire_fichier(chemin: Path) -> FactureLue:
    """Lecture locale d'une facture ; une photo ou un PDF sans texte renvoie une facture vide (à lire par l'IA)."""
    chemin = Path(chemin)
    if chemin.suffix.lower() != ".pdf":
        facture = FactureLue(chemin.name, modele="photo")
        facture.remarques.append("photo : lue par l'OCR de Windows si elle est imprimée, sinon à saisir")
        return facture
    texte = texte_pdf(chemin)
    if len(texte.strip()) < 40:
        facture = FactureLue(chemin.name, modele="PDF numérisé")
        facture.remarques.append("PDF numérisé : lu par l'OCR de Windows")
        return facture
    return lire_texte(texte, chemin.name)
