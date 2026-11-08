"""Graphiques de l'application web : traduction ligne à ligne de graphiques.py (tk.Canvas) en SVG, pour que les
graphiques soient identiques à ceux de l'application Windows (demande du propriétaire du 2026-11-03 : « identiques en
tout point, graphiques et fonctions »). Mêmes calculs (axe `_arrondi_haut`, graduations, moyenne pointillée rouge,
point le plus haut, valeurs sur les barres, aire sous la courbe, anneau avec « Autres », carte de chaleur), mêmes
couleurs et polices. L'infobulle au survol est la bulle native du navigateur (<title>), sans script.
"""

from __future__ import annotations

import math
from decimal import Decimal
from html import escape

from ..graphiques import AIRE, BLEU, BLEU_PALE, PALETTE, _arrondi_haut, _court, _degrade, format_argent

TEXTE, TEXTE_DOUX, CARTE, BORDURE = "#1f2d24", "#5f6f66", "#ffffff", "#e2e8e4"
POLICE = "font-family:'Segoe UI',Arial,sans-serif;font-size:12px"


def _t(x, y, texte, ancre="start", couleur=TEXTE_DOUX, taille=12, gras=False, base="middle", longueur=None) -> str:
    poids = ";font-weight:600" if gras else ""
    ajuste = f" textLength='{longueur:.1f}' lengthAdjust='spacingAndGlyphs'" if longueur else ""
    return (f"<text x='{x:.1f}' y='{y:.1f}' text-anchor='{ancre}' dominant-baseline='{base}' fill='{couleur}'{ajuste} "
            f"style=\"font-family:'Segoe UI',Arial,sans-serif;font-size:{taille}px{poids}\">{escape(str(texte))}</text>")


def texte_entier(texte: str, place: float, taille: int = 12) -> tuple[float, float | None]:
    """Texte toujours entier (« les textes doivent être bien visibles ») : (taille de police, longueur imposée ou
    None). La police baisse jusqu'à 10 px ; si le texte dépasse encore, il est resserré dans la place disponible."""
    largeur = len(texte) * 6.8 * taille / 12
    if largeur <= place:
        return taille, None
    taille = max(10.0, taille * place / largeur)
    largeur = len(texte) * 6.8 * taille / 12
    return taille, (place if largeur > place else None)


def _ancre(code: str) -> tuple[str, str]:
    """Ancre Tk (« e », « w », « n », « s », « sw »…) -> (text-anchor, dominant-baseline)."""
    h = "end" if "e" in code else "start" if "w" in code else "middle"
    v = "text-after-edge" if "s" in code else "text-before-edge" if "n" in code else "middle"
    return h, v


class Graphique:
    """Même interface que graphiques.Graphique : `barres`, `classement`, `anneau`, `courbes`, `chaleur`, puis
    `svg()` rend le dessin à la largeur et à la hauteur données (le SVG s'étire à la largeur de sa carte)."""

    unite = "$"  # « $ » (montants), « % » ou « » (nombres) : axes, étiquettes et infobulles

    def _court(self, v: float) -> str:
        if self.unite == "$":
            return _court(v)
        suffixe = " %" if self.unite == "%" else ""
        if abs(v) >= 1000:
            return f"{v / 1000:.1f} k".replace(".", ",") + suffixe
        return (f"{v:.0f}" if v == int(v) or abs(v) >= 10 else f"{v:.1f}".replace(".", ",")) + suffixe

    def _argent(self, v) -> str:
        if self.unite == "$":
            return format_argent(v)
        texte = f"{float(v):,.1f}".replace(",", " ").replace(".", ",")
        return texte.removesuffix(",0") + (" %" if self.unite == "%" else "")

    def __init__(self, largeur: int = 1000, hauteur: int = 200, titre: str = ""):
        self.largeur, self.hauteur, self.titre = largeur, hauteur, titre
        self._dessin = None
        self.elements: list[str] = []

    # ---------------------------------------------------------------- outils (comme le Canvas)
    def ligne(self, *points, couleur="#000", epaisseur=1, pointilles=None) -> None:
        coords = " ".join(f"{points[i]:.1f},{points[i + 1]:.1f}" for i in range(0, len(points), 2))
        dash = f" stroke-dasharray='{','.join(map(str, pointilles))}'" if pointilles else ""
        self.elements.append(f"<polyline points='{coords}' fill='none' stroke='{couleur}' stroke-width='{epaisseur}'"
                             f"{dash} stroke-linejoin='round' stroke-linecap='round'/>")

    def rect(self, x0, y0, x1, y1, couleur, contour="none", infobulle: str = "") -> None:
        titre = f"<title>{escape(infobulle)}</title>" if infobulle else ""
        self.elements.append(f"<rect x='{min(x0, x1):.1f}' y='{min(y0, y1):.1f}' width='{abs(x1 - x0):.1f}' "
                             f"height='{abs(y1 - y0):.1f}' fill='{couleur}' stroke='{contour}'>{titre}</rect>")

    def texte(self, x, y, texte, ancre="", couleur=TEXTE, taille=12, gras=False, longueur=None) -> None:
        h, v = _ancre(ancre) if ancre else ("middle", "middle")
        self.elements.append(_t(x, y, texte, h, couleur, taille, gras, v, longueur))

    def ovale(self, x0, y0, x1, y1, couleur, contour=None, epaisseur=1) -> None:
        self.elements.append(f"<ellipse cx='{(x0 + x1) / 2:.1f}' cy='{(y0 + y1) / 2:.1f}' rx='{(x1 - x0) / 2:.1f}' "
                             f"ry='{(y1 - y0) / 2:.1f}' fill='{couleur}' stroke='{contour or couleur}' "
                             f"stroke-width='{epaisseur}'/>")

    def zone(self, x0, y0, x1, y1, infobulle: str) -> None:
        """Zone de survol invisible (infobulle d'un point de courbe ou d'une colonne de barres)."""
        self.elements.append(f"<rect x='{x0:.1f}' y='{y0:.1f}' width='{max(1, x1 - x0):.1f}' height='{y1 - y0:.1f}' "
                             f"fill='transparent'><title>{escape(infobulle)}</title></rect>")

    # ---------------------------------------------------------------- rendu
    def svg(self, classe: str = "graphique") -> str:
        self.elements = []
        largeur, hauteur = self.largeur, self.hauteur
        if self.titre:
            self.elements.append(_t(12, 10, self.titre, "start", TEXTE, 14, True, "text-before-edge"))
        if self._dessin:
            self._dessin(largeur, hauteur)
        return (f"<svg class='{classe}' viewBox='0 0 {largeur} {hauteur}' preserveAspectRatio='xMidYMid meet' "
                f"role='img' aria-label='{escape(self.titre)}' xmlns='http://www.w3.org/2000/svg'>"
                f"<rect width='{largeur}' height='{hauteur}' fill='{CARTE}' stroke='{BORDURE}'/>"
                + "".join(self.elements) + "</svg>")

    def _legende(self, largeur: int, elements: list[tuple[str, str, bool]], ligne: bool = False) -> int:
        fin_titre = 12 + 8.2 * len(self.titre) + 16 if self.titre else 0
        largeurs = [7.5 * len(nom) + (32 if ligne else 24) for nom, _, _ in elements]
        y, haut = 19, 44
        x = largeur - 14 - sum(largeurs)
        if x < fin_titre:
            x, y, haut = 12, 38, 60
        for (nom, couleur, pointilles), l in zip(elements, largeurs):
            if ligne:
                self.ligne(x, y, x + 16, y, couleur=couleur, epaisseur=2, pointilles=(4, 3) if pointilles else None)
                self.texte(x + 20, y, nom, "w", TEXTE)
            else:
                self.rect(x, y - 5, x + 10, y + 5, couleur, couleur)
                self.texte(x + 14, y, nom, "w", TEXTE)
            x += l
        return haut

    def _vide(self, largeur, hauteur, vide) -> None:
        self.texte(largeur / 2, hauteur / 2, vide, "", TEXTE_DOUX)

    # ---------------------------------------------------------------- barres verticales
    def barres(self, etiquettes: list[str], series: list[tuple[str, list, str]], vide: str = "") -> "Graphique":
        def dessiner(largeur, hauteur):
            bas, gauche, droite = 30, 52, 12
            valeurs = [float(v or 0) for _, vs, _ in series for v in vs]
            if not etiquettes or not any(valeurs):
                return self._vide(largeur, hauteur, vide)
            haut = self._legende(largeur, [(nom, couleur, False) for nom, _, couleur in series])
            maximum = _arrondi_haut(max(valeurs))
            zone_h = hauteur - haut - bas
            for i in range(5):
                y = hauteur - bas - zone_h * i / 4
                self.ligne(gauche, y, largeur - droite, y, couleur="#eef1ef")
                self.texte(gauche - 6, y, self._court(maximum * i / 4), "e", TEXTE_DOUX)
            pas = (largeur - gauche - droite) / len(etiquettes)
            largeur_barre = max(2, min(26, pas * 0.8 / len(series)))
            place = max(len(e) for e in etiquettes) * 6.5 + 12
            saut = max(1, -(-len(etiquettes) // max(1, int((largeur - gauche - droite) // place))))
            for i, etiquette in enumerate(etiquettes):
                centre = gauche + pas * (i + 0.5)
                for k, (_, vs, couleur) in enumerate(series):
                    v = float(vs[i] or 0) if i < len(vs) else 0
                    if v <= 0:
                        continue
                    x0 = centre - largeur_barre * len(series) / 2 + k * largeur_barre
                    y0 = hauteur - bas - zone_h * v / maximum
                    self.rect(x0, y0, x0 + largeur_barre - 1, hauteur - bas, couleur)
                if i % saut == 0:
                    self.texte(centre, hauteur - bas + 12, etiquette, "", TEXTE_DOUX)
            premiere = [float(v or 0) for v in series[0][1]]
            if len(etiquettes) <= 14 and len(series) == 1:
                for i, v in enumerate(premiere):
                    if v > 0:
                        y0 = hauteur - bas - zone_h * v / maximum
                        self.texte(gauche + pas * (i + 0.5), y0 - 7, self._court(v), "", TEXTE, 11)
            self._moyenne(premiere, gauche, largeur - droite, hauteur - bas, zone_h, maximum)
            for i, etiquette in enumerate(etiquettes):  # infobulle de chaque colonne
                lignes = [etiquette] + [f"{nom} : {self._argent(vs[i])}" for nom, vs, _ in series
                                        if i < len(vs) and vs[i] is not None]
                self.zone(gauche + pas * i, haut, gauche + pas * (i + 1), hauteur - bas, "\n".join(lignes))

        self._dessin = dessiner
        return self

    def _moyenne(self, valeurs, x0, x1, bas_y, zone_h, maximum) -> None:
        utiles = [v for v in valeurs if v]
        if len(utiles) < 3:
            return
        moyenne = sum(utiles) / len(utiles)
        y = bas_y - zone_h * moyenne / maximum
        self.ligne(x0, y, x1, y, couleur="#d7263d", pointilles=(6, 4))
        self.texte(x1 - 4, y - 8, f"moy. {self._court(moyenne)}", "e", "#d7263d", 11)

    # ---------------------------------------------------------------- classement
    def classement(self, elements: list[tuple[str, Decimal]], couleur: str = BLEU, vide: str = "",
                   format_valeur=None) -> "Graphique":
        def dessiner(largeur, hauteur):
            haut, gauche_max = 38, 0.42
            if not elements:
                return self._vide(largeur, hauteur, vide)
            maximum = max(float(v) for _, v in elements) or 1
            total = sum(float(v) for _, v in elements) or 1
            ligne = min(22, (hauteur - haut - 6) / len(elements))
            # colonne des noms élargie pour les noms longs (jusqu'à 58 % de la largeur)
            plus_long = max(len(str(n)) for n, _ in elements) * 6.8 + 22
            debut_barre = min(largeur * 0.58, max(largeur * gauche_max, plus_long))
            fin_barre = largeur - 78
            for i, (nom, valeur) in enumerate(elements):
                y = haut + i * ligne
                taille, longueur = texte_entier(str(nom), debut_barre - 20)
                self.texte(10, y + ligne / 2, nom, "w", TEXTE, taille, longueur=longueur)
                x1 = debut_barre + (fin_barre - debut_barre) * max(float(valeur), 0) / maximum
                valeur_txt = format_valeur(valeur) if format_valeur else str(valeur)
                self.rect(debut_barre, y + 3, max(x1, debut_barre + 1), y + ligne - 3, couleur)
                self.texte(fin_barre + 6, y + ligne / 2, valeur_txt, "w", TEXTE_DOUX)
                self.zone(0, y, largeur, y + ligne, f"{nom}\n{valeur_txt} — {100 * float(valeur) / total:.1f} % du "
                                                    "total".replace(".", ","))

        self._dessin = dessiner
        return self

    # ---------------------------------------------------------------- anneau
    def anneau(self, elements: list[tuple[str, Decimal]], vide: str = "", format_valeur=None) -> "Graphique":
        def dessiner(largeur, hauteur):
            parts = [(n, float(v)) for n, v in elements if float(v) > 0]
            total = sum(v for _, v in parts)
            if not total:
                return self._vide(largeur, hauteur, vide)
            parts.sort(key=lambda x: -x[1])
            if len(parts) > 6:
                parts = parts[:5] + [("Autres", sum(v for _, v in parts[5:]))]
            rayon = max(20, min((hauteur - 56) / 2, largeur * 0.15))
            cx, cy = 18 + rayon, 36 + (hauteur - 36) / 2
            interieur = rayon * 0.58
            debut = 90.0
            for i, (nom, v) in enumerate(parts):
                etendue = min(360 * v / total, 359.99)
                couleur = PALETTE[i % len(PALETTE)]
                valeur_txt = format_valeur(Decimal(str(round(v, 2)))) if format_valeur else f"{v:.0f}"
                self.elements.append(_part(cx, cy, rayon, interieur, debut, etendue, couleur,
                                           f"{nom}\n{valeur_txt} — {100 * v / total:.1f} %"))
                debut -= etendue
            x = cx + rayon + 18
            self.texte(x, 42, format_valeur(Decimal(str(round(total, 2)))) if format_valeur else f"{total:.0f}", "w",
                       TEXTE, 13, True)
            ligne = min(21, (hauteur - 66) / max(1, len(parts)))
            for i, (nom, v) in enumerate(parts):
                y = 66 + i * ligne
                self.rect(x, y - 5, x + 10, y + 5, PALETTE[i % len(PALETTE)])
                texte = f"{nom} {100 * v / total:.0f} %"
                taille, longueur = texte_entier(texte, largeur - x - 26)
                self.texte(x + 16, y, texte, "w", TEXTE, taille, longueur=longueur)

        self._dessin = dessiner
        return self

    # ---------------------------------------------------------------- courbes
    def courbes(self, etiquettes: list[str], series: list[tuple[str, list, str, bool]], vide: str = "") -> "Graphique":
        def dessiner(largeur, hauteur):
            bas, gauche, droite = 30, 52, 14
            valeurs = [float(v) for _, vs, _, _ in series for v in vs if v is not None]
            if not etiquettes or not any(valeurs):
                return self._vide(largeur, hauteur, vide)
            haut = self._legende(largeur, [(nom, couleur, p) for nom, _, couleur, p in series], ligne=True)
            maximum = _arrondi_haut(max(valeurs))
            zone_h, zone_l = hauteur - haut - bas, largeur - gauche - droite
            for i in range(5):
                y = hauteur - bas - zone_h * i / 4
                self.ligne(gauche, y, largeur - droite, y, couleur="#eef1ef")
                self.texte(gauche - 6, y, self._court(maximum * i / 4), "e", TEXTE_DOUX)
            n = len(etiquettes)
            pas = zone_l / max(1, n - 1)
            place = max(len(e) for e in etiquettes) * 6.5 + 12
            saut = max(1, -(-n // max(1, int(zone_l // place))))
            for i, etiquette in enumerate(etiquettes):
                if i % saut == 0:
                    self.texte(gauche + pas * i, hauteur - bas + 12, etiquette, "", TEXTE_DOUX)
            principale = [(gauche + pas * i, hauteur - bas - zone_h * float(v) / maximum)
                          for i, v in enumerate(series[0][1]) if v is not None]
            if len(principale) > 1:
                points = [(principale[0][0], hauteur - bas)] + principale + [(principale[-1][0], hauteur - bas)]
                self.elements.append("<polygon points='" + " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
                                     + f"' fill='{AIRE}' stroke='none'/>")
            self._moyenne([float(v) for v in series[0][1] if v is not None], gauche, largeur - droite, hauteur - bas,
                          zone_h, maximum)
            for _, vs, couleur, pointilles in series:
                points = [(gauche + pas * i, hauteur - bas - zone_h * float(v) / maximum)
                          for i, v in enumerate(vs) if v is not None]
                if len(points) > 1:
                    self.elements.append(f"<path d='{_lisse(points)}' fill='none' stroke='{couleur}' stroke-width='2'"
                                         + (" stroke-dasharray='5,3'" if pointilles else "") + "/>")
                for px, py in points if len(points) <= 40 else []:
                    self.ovale(px - 2, py - 2, px + 2, py + 2, couleur)
            valeurs_1 = [(i, float(v)) for i, v in enumerate(series[0][1]) if v is not None]
            if valeurs_1:
                i, v = max(valeurs_1, key=lambda x: x[1])
                px, py = gauche + pas * i, hauteur - bas - zone_h * v / maximum
                self.ovale(px - 4, py - 4, px + 4, py + 4, "white", series[0][2], 2)
                vertical = "s" if py > haut + 30 else "n"
                cote = "w" if px < gauche + 90 else "e" if px > largeur - 90 else ""
                decale = 6 if cote == "w" else -6 if cote == "e" else 0
                self.texte(px + decale, py - 12 if vertical == "s" else py + 12, f"max {self._court(v)} ({etiquettes[i]})",
                           vertical + cote, TEXTE, 11, True)
            for i, etiquette in enumerate(etiquettes):  # infobulle de chaque point
                lignes = [etiquette] + [f"{nom} : {self._argent(vs[i])}" for nom, vs, _c, _p in series
                                        if i < len(vs) and vs[i] is not None]
                self.zone(gauche + pas * (i - 0.5), haut, gauche + pas * (i + 0.5), hauteur - bas, "\n".join(lignes))

        self._dessin = dessiner
        return self

    # ---------------------------------------------------------------- carte de chaleur
    def chaleur(self, lignes: list[str], colonnes: list[str], valeurs: list[list], vide: str = "") -> "Graphique":
        def dessiner(largeur, hauteur):
            plat = [float(v or 0) for rang in valeurs for v in rang]
            if not plat or not any(plat):
                return self._vide(largeur, hauteur, vide)
            maximum = max(plat)
            gauche, haut, bas, droite = 80, 40, 24, 12
            l_case = (largeur - gauche - droite) / len(colonnes)
            h_case = (hauteur - haut - bas) / len(lignes)
            for r_, nom_ligne in enumerate(lignes):
                y0 = haut + r_ * h_case
                self.texte(gauche - 8, y0 + h_case / 2, nom_ligne, "e", TEXTE)
                for c_, nom_col in enumerate(colonnes):
                    v = float(valeurs[r_][c_] or 0)
                    x0 = gauche + c_ * l_case
                    self.rect(x0 + 1, y0 + 1, x0 + l_case - 1, y0 + h_case - 1, _degrade(v / maximum),
                              infobulle=f"{nom_ligne} {nom_col}\n{self._argent(v)}")
                    if v and l_case > 34 and h_case > 16:
                        self.texte(x0 + l_case / 2, y0 + h_case / 2, self._court(v).replace(" $", ""), "",
                                   "white" if v / maximum > 0.55 else TEXTE, 10)
            for c_, nom_col in enumerate(colonnes):
                if len(colonnes) <= 24 or c_ % 2 == 0:
                    self.texte(gauche + (c_ + 0.5) * l_case, hauteur - bas + 10, nom_col, "", TEXTE_DOUX)

        self._dessin = dessiner
        return self


def _part(cx, cy, rayon, interieur, debut, etendue, couleur, infobulle) -> str:
    """Part d'anneau de `debut` (degrés, sens trigonométrique comme Tk) sur `etendue` degrés dans le sens horaire."""
    def point(r, angle):
        a = math.radians(angle)
        return cx + r * math.cos(a), cy - r * math.sin(a)

    fin = debut - etendue
    x0, y0 = point(rayon, debut)
    x1, y1 = point(rayon, fin)
    x2, y2 = point(interieur, fin)
    x3, y3 = point(interieur, debut)
    grand = 1 if etendue > 180 else 0
    d = (f"M{x0:.2f},{y0:.2f} A{rayon:.2f},{rayon:.2f} 0 {grand} 1 {x1:.2f},{y1:.2f} L{x2:.2f},{y2:.2f} "
         f"A{interieur:.2f},{interieur:.2f} 0 {grand} 0 {x3:.2f},{y3:.2f} Z")
    return (f"<path d='{d}' fill='{couleur}' stroke='{CARTE}' stroke-width='2'><title>{escape(infobulle)}</title>"
            "</path>")


def _lisse(points: list[tuple[float, float]]) -> str:
    """Courbe lissée passant près des points (comme `smooth=True` de Tk : B-spline quadratique par les milieux)."""
    if len(points) < 3:
        return "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in points)
    d = [f"M{points[0][0]:.1f},{points[0][1]:.1f}"]
    for i in range(1, len(points) - 1):
        mx, my = (points[i][0] + points[i + 1][0]) / 2, (points[i][1] + points[i + 1][1]) / 2
        if i == len(points) - 2:
            mx, my = points[i + 1]
        d.append(f"Q{points[i][0]:.1f},{points[i][1]:.1f} {mx:.1f},{my:.1f}")
    return " ".join(d)


__all__ = ["Graphique", "BLEU", "BLEU_PALE", "PALETTE"]
