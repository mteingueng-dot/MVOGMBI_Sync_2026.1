"""Modèles PDF dessinés directement (bibliothèque fpdf2), sans Edge (demande du propriétaire du 2026-11-03 : « il faut
bien reformater les modèles ») : constat du même jour, Edge s'arrête sans rien écrire dans l'application ouverte.

- `document_commercial` : devis, commandes, bons de livraison / réception / retour, factures, avoirs, bons de
  commande fournisseur, documents de stock. En-tête (logo, entreprise lue dans Clover, filet vert / rouge / jaune),
  cadre du document (type, n°, date), blocs client ou fournisseur et informations (origine, dépôt, remarque), tableau
  des lignes (description sur plusieurs lignes, montants à droite), totaux (sous-total, TPS, TVQ, total) et pied de
  page (page n / total).
- `tableau` : tout tableau exporté en PDF (mêmes en-tête et pied, en-têtes verts, une ligne sur deux teintée,
  colonnes de chiffres à droite, largeur selon le contenu, à l'horizontale au-delà de 7 colonnes).
"""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from fpdf import FPDF

VERT, VERT_FONCE, ROUGE, JAUNE = (31, 122, 58), (19, 119, 45), (215, 38, 61), (242, 183, 5)
GRIS, GRIS_CLAIR, TEINTE = (107, 122, 112), (226, 232, 228), (244, 249, 245)
POLICES = (Path(r"C:\Windows\Fonts\arial.ttf"), Path(r"C:\Windows\Fonts\arialbd.ttf"))
NOMBRE = re.compile(r"^-?[\d\s\u00a0\u202f]+([.,]\d+)?\s*(\$|%)?$")


def argent(v) -> str:
    if v in (None, ""):
        return ""
    return f"{Decimal(str(v)):,.2f} $".replace(",", "\u202f").replace(".", ",")


def quantite(v) -> str:
    q = Decimal(str(v or 0)).normalize()
    return f"{q:f}".replace(".", ",")


def _propre(texte) -> str:
    """Texte sans pictogrammes (absents de la police) ni espaces doubles."""
    texte = re.sub(r"[\U00010000-\U0010FFFF\u2600-\u27BF\uFE0F]", "", str(texte if texte is not None else ""))
    return " ".join(texte.split())


class ModelePDF(FPDF):
    def __init__(self, titre: str, paysage: bool = False, racine: Path | None = None):
        super().__init__(orientation="L" if paysage else "P", unit="mm", format="Letter")
        self.titre_document = titre
        self.racine = racine
        self.set_margins(14, 14, 14)
        self.set_auto_page_break(True, 18)
        self.alias_nb_pages()
        if all(p.exists() for p in POLICES):
            self.add_font("Arial", "", str(POLICES[0]))
            self.add_font("Arial", "B", str(POLICES[1]))
            self.police = "Arial"
        else:
            self.police = "Helvetica"
        self.set_title(titre)
        self.set_creator("MVOGMBI_Sync")

    def ecrire(self, texte) -> str:
        texte = _propre(texte)
        return texte if self.police == "Arial" else texte.encode("latin-1", "replace").decode("latin-1")

    def police_(self, taille: float = 9, gras: bool = False, couleur=(31, 45, 36)) -> None:
        self.set_font(self.police, "B" if gras else "", taille)
        self.set_text_color(*couleur)

    # ------------------------------------------------------------------ en-tête et pied de chaque page
    def header(self) -> None:
        from .design import LOGO
        from .entreprise import Entreprise, lire

        largeur = self.w - self.l_margin - self.r_margin
        tiers = largeur / 3
        y0 = 8
        for i, couleur in enumerate((VERT, ROUGE, JAUNE)):  # filet aux couleurs du marché
            self.set_fill_color(*couleur)
            self.rect(self.l_margin + i * tiers, y0, tiers, 1.4, "F")
        try:
            info = lire(self.racine) if self.racine else Entreprise()
        except Exception:
            info = Entreprise()
        x = self.l_margin
        if Path(LOGO).exists():
            self.image(str(LOGO), x=x, y=y0 + 4, h=16)
            x += 20
        self.set_xy(x, y0 + 4)
        self.police_(12, True, VERT_FONCE)
        self.cell(0, 6, self.ecrire(info.nom), new_x="LMARGIN", new_y="NEXT")
        self.police_(8, False, GRIS)
        for ligne in (info.adresse, info.ville,
                      " • ".join(x for x in (f"Tél. {info.telephone}" if info.telephone else "", info.site) if x)):
            if ligne:
                self.set_x(x)
                self.cell(0, 3.8, self.ecrire(ligne), new_x="LMARGIN", new_y="NEXT")
        self.set_y(y0 + 24)

    def footer(self) -> None:
        self.set_y(-12)
        self.set_draw_color(*GRIS_CLAIR)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.police_(7, False, GRIS)
        self.cell(0, 6, self.ecrire(f"{self.titre_document} — imprimé le {datetime.now():%Y-%m-%d %H:%M}"), align="L")
        self.set_x(self.l_margin)
        self.cell(0, 6, f"Page {self.page_no()} / {{nb}}", align="R")

    # ------------------------------------------------------------------ éléments
    def cadre_titre(self, type_document: str, numero: str, jour: str, etat: str = "") -> None:
        """Cadre à droite : type du document en grand, n°, date (et état)."""
        largeur = 78
        x = self.w - self.r_margin - largeur
        y = 10
        self.set_xy(x, y)
        self.set_fill_color(*VERT)
        taille = 13
        self.police_(taille, True, (255, 255, 255))
        while taille > 8 and self.get_string_width(self.ecrire(type_document.upper())) > largeur - 4:
            taille -= 0.5  # titre long (« FACTURE D'AVOIR FOURNISSEUR ») : jamais collé aux bords du cadre
            self.police_(taille, True, (255, 255, 255))
        self.cell(largeur, 9, self.ecrire(type_document.upper()), align="C", fill=True, new_x="LEFT", new_y="NEXT")
        self.set_draw_color(*VERT)
        lignes = [("N°", numero), ("Date", jour)] + ([("État", etat)] if etat else [])
        for libelle, valeur in lignes:
            self.set_x(x)
            self.police_(8, False, GRIS)
            self.cell(22, 6, self.ecrire(libelle), border="LB")
            self.police_(10, True)
            self.cell(largeur - 22, 6, self.ecrire(valeur), border="RB", align="R", new_x="LEFT", new_y="NEXT")
        self.set_y(max(self.get_y(), 34) + 4)

    def blocs(self, gauche: tuple[str, list[str]], droite: tuple[str, list[str]]) -> None:
        """Deux blocs côte à côte (client / fournisseur, informations)."""
        largeur = (self.w - self.l_margin - self.r_margin - 6) / 2
        y = self.get_y()
        hauteur = 0
        for rang, (titre, lignes) in enumerate((gauche, droite)):
            x = self.l_margin + rang * (largeur + 6)
            self.set_xy(x, y)
            self.set_fill_color(*TEINTE)
            self.police_(7.5, True, VERT_FONCE)
            self.cell(largeur, 5.5, self.ecrire(titre.upper()), fill=True, new_x="LEFT", new_y="NEXT")
            for ligne in [l for l in lignes if l]:
                self.set_x(x)
                self.police_(9, ligne is lignes[0])
                self.multi_cell(largeur, 4.6, self.ecrire(ligne), new_x="LEFT", new_y="NEXT")
            hauteur = max(hauteur, self.get_y() - y)
        self.set_y(y + hauteur + 5)

    def entetes(self, colonnes: list[tuple[str, float, str]]) -> None:
        self.set_fill_color(*VERT)
        self.police_(8.5, True, (255, 255, 255))
        for texte, largeur, align in colonnes:
            self.cell(largeur, 7, self.ecrire(texte), fill=True, align=align)
        self.ln(7)

    def ligne_tableau(self, colonnes: list[tuple[str, float, str]], valeurs: list[str], rang: int,
                      taille: float = 8.5) -> None:
        """Une ligne : hauteur selon la cellule la plus longue (texte sur plusieurs lignes), une sur deux teintée."""
        self.police_(taille)
        hauteur_ligne = 4.6
        nb = max(len(self.multi_cell(l - 2, hauteur_ligne, self.ecrire(v), dry_run=True, output="LINES") or [""])
                 for (_t, l, _a), v in zip(colonnes, valeurs))
        hauteur = nb * hauteur_ligne + 2
        if self.get_y() + hauteur > self.page_break_trigger:
            self.add_page()
            self.entetes(colonnes)
            self.police_(taille)
        y, x = self.get_y(), self.l_margin
        if rang % 2:
            self.set_fill_color(*TEINTE)
            self.rect(x, y, sum(l for _t, l, _a in colonnes), hauteur, "F")
        for (_t, largeur, align), valeur in zip(colonnes, valeurs):
            self.set_xy(x + 1, y + 1)
            self.multi_cell(largeur - 2, hauteur_ligne, self.ecrire(valeur), align=align)
            x += largeur
        self.set_draw_color(*GRIS_CLAIR)
        self.line(self.l_margin, y + hauteur, self.l_margin + sum(l for _t, l, _a in colonnes), y + hauteur)
        self.set_xy(self.l_margin, y + hauteur)

    def totaux(self, lignes: list[tuple[str, str]], final: tuple[str, str]) -> None:
        largeur = 80
        x = self.w - self.r_margin - largeur
        if self.get_y() + 8 * (len(lignes) + 1) > self.page_break_trigger:
            self.add_page()
        self.ln(3)
        for libelle, valeur in lignes:
            self.set_x(x)
            self.police_(9, False, GRIS)
            self.cell(largeur - 35, 6, self.ecrire(libelle))
            self.police_(9.5)
            self.cell(35, 6, self.ecrire(valeur), align="R", new_x="LMARGIN", new_y="NEXT")
        self.set_x(x)
        self.set_fill_color(*VERT)
        self.police_(11, True, (255, 255, 255))
        self.cell(largeur - 35, 8, self.ecrire(final[0]), fill=True)
        self.cell(35, 8, self.ecrire(final[1]), fill=True, align="R", new_x="LMARGIN", new_y="NEXT")


def chemin_libre(chemin: Path) -> Path:
    """`chemin`, ou « … (2).pdf », « … (3).pdf » s'il est ouvert dans un lecteur de PDF (fichier verrouillé :
    « Permission denied », constat du 2026-11-03) : le PDF est toujours écrit."""
    chemin = Path(chemin)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    for rang in range(1, 50):
        essai = chemin if rang == 1 else chemin.with_name(f"{chemin.stem} ({rang}){chemin.suffix}")
        try:
            if essai.exists():
                with open(essai, "r+b"):
                    pass  # ouvrable en écriture : pas verrouillé
            return essai
        except PermissionError:
            continue
    return chemin.with_name(f"{chemin.stem} {datetime.now():%H%M%S}{chemin.suffix}")


# --------------------------------------------------------------------------------------------- documents
def document_commercial(chemin: Path, racine: Path | None, type_document: str, numero: str, jour: str,
                        tiers_titre: str, tiers: list[str], infos: list[str], lignes: list[dict],
                        avec_taxes: bool = True, etat: str = "", remarque: str = "", libelle_prix: str = "Prix",
                        signe: int = 1) -> Path:
    """`lignes` : [{"numero", "description", "quantite", "prix", "montant", "taxe"}] (Decimal ou texte)."""
    from . import taxes as tx

    pdf = ModelePDF(f"{type_document} {numero}", racine=racine)
    pdf.add_page()
    pdf.cadre_titre(type_document, numero, jour, etat)
    pdf.blocs((tiers_titre, tiers), ("Informations", infos))
    largeur = pdf.w - pdf.l_margin - pdf.r_margin
    colonnes = [("N° article", 28, "L"), ("Description", 0, "L"), ("Quantité", 20, "R"), (libelle_prix, 26, "R")] + (
        [("Taxes", 24, "C")] if avec_taxes else []) + [("Montant", 28, "R")]
    reste = largeur - sum(l for _t, l, _a in colonnes)
    colonnes = [(t, l or reste, a) for t, l, a in colonnes]
    pdf.entetes(colonnes)
    sous_total, tps, tvq = Decimal(0), Decimal(0), Decimal(0)
    for rang, l in enumerate(lignes):
        montant = Decimal(str(l["montant"])) * signe
        code = l.get("taxe") or ""
        sous_total += montant
        if avec_taxes and code:
            g, q = tx.montants(montant, code)
            tps, tvq = tps + g, tvq + q
        valeurs = [l["numero"], l["description"], quantite(Decimal(str(l["quantite"])) * signe), argent(l["prix"])] + (
            [tx.libelle(code) if code else "—"] if avec_taxes else []) + [argent(montant)]
        pdf.ligne_tableau(colonnes, valeurs, rang)
    if avec_taxes:
        pdf.totaux([("Sous-total", argent(sous_total)), ("TPS (5 %)", argent(tps)), ("TVQ (9,975 %)", argent(tvq))],
                   ("Total", argent(sous_total + tps + tvq)))
    else:
        pdf.totaux([], ("Total", argent(sous_total)))
    if remarque:
        pdf.ln(4)
        pdf.police_(8.5, True, VERT_FONCE)
        pdf.cell(0, 5, "Remarque", new_x="LMARGIN", new_y="NEXT")
        pdf.police_(9)
        pdf.multi_cell(0, 4.6, pdf.ecrire(remarque))
    chemin = chemin_libre(chemin)
    pdf.output(str(chemin))
    return chemin


# --------------------------------------------------------------------------------------------- tableaux
def tableau(chemin: Path, racine: Path | None, titre: str, entetes: list[str], lignes: list[list],
            sous_titre: str = "") -> Path:
    """Tableau exporté : largeur des colonnes selon leur contenu, chiffres à droite, à l'horizontale > 7 colonnes."""
    pdf = ModelePDF(titre, paysage=len(entetes) > 7, racine=racine)
    pdf.add_page()
    pdf.police_(15, True, VERT_FONCE)
    pdf.cell(0, 8, pdf.ecrire(titre), new_x="LMARGIN", new_y="NEXT")
    if sous_titre:
        pdf.police_(9, False, GRIS)
        pdf.multi_cell(0, 4.5, pdf.ecrire(sous_titre))
    pdf.ln(3)
    textes = [[_propre(v) for v in l] for l in lignes]
    nombres = [all(not v or NOMBRE.match(v) for v in col) and any(col)
               for col in zip(*textes)] if textes else [False] * len(entetes)
    pdf.police_(8.5)
    poids = []
    for i, e in enumerate(entetes):
        valeurs = [l[i] for l in textes[:200] if i < len(l)]
        echantillon = sorted([len(e)] + [len(v) for v in valeurs])
        long = echantillon[int(len(echantillon) * 0.9) - 1 if len(echantillon) > 1 else 0]
        mot = max([len(m) for v in valeurs + [e] for m in v.split()] or [4])  # jamais un mot coupé en deux
        poids.append(max(4, mot + 1, min(45, long)))
    largeur = pdf.w - pdf.l_margin - pdf.r_margin
    colonnes = [(e, largeur * p / sum(poids), "R" if n else "L") for e, p, n in zip(entetes, poids, nombres)]
    pdf.entetes(colonnes)
    for rang, l in enumerate(textes):
        pdf.ligne_tableau(colonnes, (l + [""] * len(entetes))[:len(entetes)], rang, 8)
    chemin = chemin_libre(chemin)
    pdf.output(str(chemin))
    return chemin


# --------------------------------------------------------------------------------------------- bons sans prix
def bon_sans_prix(chemin: Path, racine: Path | None, type_document: str, numero: str, jour: str, tiers_titre: str,
                  tiers: list[str], infos: list[str], lignes: list[dict], colonne_quantite: str = "Quantité",
                  colonnes_vides: tuple[str, ...] = ("Observation",), signatures: tuple[str, ...] = (),
                  etat: str = "", remarque: str = "", note: str = "") -> Path:
    """Bon de préparation, de livraison, de réception ou de retour (demande du propriétaire du 2026-11-05 : « des
    modèles d'impression pour chaque type de document en vente et achat ; le bon de livraison est en vente et le
    bon de réception en achat ») : SANS PRIX, article et quantité, colonnes vides à remplir à la main
    (observation, quantité contrôlée…), lignes de signature. `lignes` : [{"numero", "description", "quantite"}]."""
    pdf = ModelePDF(f"{type_document} {numero}", racine=racine)
    pdf.add_page()
    pdf.cadre_titre(type_document, numero, jour, etat)
    pdf.blocs((tiers_titre, tiers), ("Informations", infos))
    largeur = pdf.w - pdf.l_margin - pdf.r_margin
    vides = [(c, 46 if c.lower().startswith(("observ", "motif")) else 24, "L") for c in colonnes_vides]
    colonnes = [("N° article", 30, "L"), ("Article", 0, "L"), (colonne_quantite, 24, "R")] + vides
    reste = largeur - sum(l for _t, l, _a in colonnes)
    colonnes = [(t, l or reste, a) for t, l, a in colonnes]
    pdf.entetes(colonnes)
    total = Decimal(0)
    for rang, l in enumerate(lignes):
        q = Decimal(str(l.get("quantite") or 0))
        total += q
        pdf.ligne_tableau(colonnes, [l.get("numero") or "—", l.get("description") or "", quantite(q)]
                          + [""] * len(vides), rang, 9)
    pdf.ln(3)
    pdf.police_(9, True, VERT_FONCE)
    pdf.cell(0, 5, pdf.ecrire(f"{len(lignes)} ligne(s) — quantité totale : {quantite(total)}"),
             new_x="LMARGIN", new_y="NEXT")
    if note:
        pdf.police_(8.5, False, GRIS)
        pdf.multi_cell(0, 4.4, pdf.ecrire(note))
    if remarque:
        pdf.ln(3)
        pdf.police_(8.5, True, VERT_FONCE)
        pdf.cell(0, 5, "Remarque", new_x="LMARGIN", new_y="NEXT")
        pdf.police_(9)
        pdf.multi_cell(0, 4.6, pdf.ecrire(remarque))
    if signatures:
        pdf.ln(12)
        pdf.police_(9.5, True, VERT_FONCE)
        part = largeur / len(signatures)
        for s in signatures:
            pdf.cell(part, 6, pdf.ecrire(f"{s} : ______________________"))
        pdf.ln(9)
        for _s in signatures:
            pdf.cell(part, 6, pdf.ecrire("Date : ____________________"))
        pdf.ln(6)
    chemin = chemin_libre(chemin)
    pdf.output(str(chemin))
    return chemin


# --------------------------------------------------------------------------------------------- documents de stock
def _notes_et_signatures(pdf: ModelePDF, note: str, remarque: str, signatures: tuple[str, ...]) -> None:
    largeur = pdf.w - pdf.l_margin - pdf.r_margin
    if note:
        pdf.police_(8.5, False, GRIS)
        pdf.multi_cell(0, 4.4, pdf.ecrire(note))
    if remarque:
        pdf.ln(3)
        pdf.police_(8.5, True, VERT_FONCE)
        pdf.cell(0, 5, "Remarque", new_x="LMARGIN", new_y="NEXT")
        pdf.police_(9)
        pdf.multi_cell(0, 4.6, pdf.ecrire(remarque))
    if signatures:
        if pdf.get_y() + 30 > pdf.page_break_trigger:
            pdf.add_page()
        pdf.ln(12)
        pdf.police_(9.5, True, VERT_FONCE)
        part = largeur / len(signatures)
        for s in signatures:
            pdf.cell(part, 6, pdf.ecrire(f"{s} : ______________________"))
        pdf.ln(9)
        for _s in signatures:
            pdf.cell(part, 6, pdf.ecrire("Date : ____________________"))
        pdf.ln(6)


def document_stock(chemin: Path, racine: Path | None, type_document: str, numero: str, jour: str,
                   gauche: tuple[str, list[str]], droite: tuple[str, list[str]],
                   colonnes: list[tuple[str, float, str]], lignes: list[list[str]], resume: list[str] = (),
                   totaux: list[tuple[str, str]] = (), final: tuple[str, str] | None = None,
                   signatures: tuple[str, ...] = (), etat: str = "", remarque: str = "", note: str = "") -> Path:
    """Mouvement d'entrée, mouvement de sortie, bon de transfert, écart d'inventaire (demande du propriétaire du
    2026-11-05 : « il y a aussi les modèles pour les documents de stocks »). `colonnes` : (titre, largeur en mm
    (0 = le reste), alignement) ; `lignes` : valeurs déjà mises en forme ; `resume` : lignes en gras sous le tableau ;
    `totaux` / `final` : cadre des totaux à droite (valeurs)."""
    pdf = ModelePDF(f"{type_document} {numero}", racine=racine)
    pdf.add_page()
    pdf.cadre_titre(type_document, numero, jour, etat)
    pdf.blocs(gauche, droite)
    largeur = pdf.w - pdf.l_margin - pdf.r_margin
    reste = largeur - sum(l for _t, l, _a in colonnes)
    colonnes = [(t, l or reste, a) for t, l, a in colonnes]
    pdf.entetes(colonnes)
    for rang, valeurs in enumerate(lignes):
        pdf.ligne_tableau(colonnes, [str(v) for v in valeurs], rang, 9)
    pdf.ln(3)
    for texte in resume:
        pdf.police_(9, True, VERT_FONCE)
        pdf.cell(0, 5, pdf.ecrire(texte), new_x="LMARGIN", new_y="NEXT")
    if final:
        pdf.totaux(list(totaux), final)
        pdf.ln(2)
    _notes_et_signatures(pdf, note, remarque, signatures)
    chemin = chemin_libre(chemin)
    pdf.output(str(chemin))
    return chemin
