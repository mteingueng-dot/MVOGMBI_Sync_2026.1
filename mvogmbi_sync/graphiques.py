"""Graphiques simples dessinés sur un tk.Canvas (aucune bibliothèque de plus) : barres verticales avec une série de
comparaison (comme le tableau de bord de Clover : aujourd'hui / mardi dernier) et barres horizontales (classements).
Redessinés à chaque changement de taille."""

from __future__ import annotations

import tkinter as tk
from decimal import Decimal

from .design import BORDURE, CARTE, TEXTE, TEXTE_DOUX

BLEU = "#0b8fd8"         # série principale (bleu Clover)
BLEU_PALE = "#9fd3f2"    # série de comparaison
POLICE = ("Segoe UI", 9)


def _court(valeur: float) -> str:
    """« 1,2 k$ », « 250 $ » pour les axes."""
    if abs(valeur) >= 1000:
        return f"{valeur / 1000:.1f} k$".replace(".", ",")
    return f"{valeur:.0f} $"


def _arrondi_haut(valeur: float) -> float:
    if valeur <= 0:
        return 1
    puissance = 10 ** (len(str(int(valeur))) - 1)
    for pas in (1, 2, 2.5, 5, 10):
        if valeur <= pas * puissance:
            return pas * puissance
    return 10 * puissance


class Graphique(tk.Canvas):
    """Canvas qui garde ses données et se redessine à la bonne taille."""

    def __init__(self, parent, hauteur: int = 200, titre: str = ""):
        super().__init__(parent, height=hauteur, background=CARTE, highlightthickness=1,
                         highlightbackground=BORDURE)
        self.titre = titre
        self._dessin = None
        self.bind("<Configure>", lambda _e: self.redessiner())

    def _legende(self, largeur: int, elements: list[tuple[str, str, bool]], ligne: bool = False) -> int:
        """Légende à droite du titre, ou sous le titre si la place manque ; renvoie le haut de la zone de dessin."""
        fin_titre = 12 + 8.2 * len(self.titre) + 16 if self.titre else 0
        largeurs = [7.5 * len(nom) + (32 if ligne else 24) for nom, _, _ in elements]
        y, haut = 19, 44
        x = largeur - 14 - sum(largeurs)
        if x < fin_titre:  # pas la place à côté du titre : en dessous
            x, y, haut = 12, 38, 60
        for (nom, couleur, pointilles), l in zip(elements, largeurs):
            if ligne:
                self.create_line(x, y, x + 16, y, fill=couleur, width=2, dash=(4, 3) if pointilles else None)
                self.create_text(x + 20, y, text=nom, anchor="w", font=POLICE, fill=TEXTE)
            else:
                self.create_rectangle(x, y - 5, x + 10, y + 5, fill=couleur, outline=couleur)
                self.create_text(x + 14, y, text=nom, anchor="w", font=POLICE, fill=TEXTE)
            x += l
        return haut

    def redessiner(self) -> None:
        self.delete("all")
        largeur, hauteur = self.winfo_width(), self.winfo_height()
        if self.titre:
            self.create_text(12, 10, text=self.titre, anchor="nw", font=("Segoe UI Semibold", 11), fill=TEXTE)
        if self._dessin and largeur > 50:
            self._dessin(largeur, hauteur)

    # ------------------------------------------------------------------ barres verticales (2 séries)
    def barres(self, etiquettes: list[str], series: list[tuple[str, list, str]], vide: str = "") -> None:
        """`series` : [(nom, valeurs, couleur)] — la 1re est la période choisie, la 2e la comparaison."""
        def dessiner(largeur, hauteur):
            bas, gauche, droite = 30, 52, 12
            valeurs = [float(v or 0) for _, vs, _ in series for v in vs]
            if not etiquettes or not any(valeurs):
                self.create_text(largeur / 2, hauteur / 2, text=vide, fill=TEXTE_DOUX, font=POLICE)
                return
            haut = self._legende(largeur, [(nom, couleur, False) for nom, _, couleur in series])
            maximum = _arrondi_haut(max(valeurs))
            zone_h = hauteur - haut - bas
            for i in range(5):  # graduations
                y = bas_y = hauteur - bas - zone_h * i / 4
                self.create_line(gauche, y, largeur - droite, y, fill="#eef1ef")
                self.create_text(gauche - 6, bas_y, text=_court(maximum * i / 4), anchor="e", font=POLICE,
                                 fill=TEXTE_DOUX)
            pas = (largeur - gauche - droite) / len(etiquettes)
            largeur_barre = max(2, min(26, pas * 0.8 / len(series)))
            place = max(len(e) for e in etiquettes) * 6.5 + 12  # largeur d'une étiquette
            saut = max(1, -(-len(etiquettes) // max(1, int((largeur - gauche - droite) // place))))
            for i, etiquette in enumerate(etiquettes):
                centre = gauche + pas * (i + 0.5)
                for k, (_, vs, couleur) in enumerate(series):
                    v = float(vs[i] or 0)
                    if v <= 0:
                        continue
                    x0 = centre - largeur_barre * len(series) / 2 + k * largeur_barre
                    y0 = hauteur - bas - zone_h * v / maximum
                    self.create_rectangle(x0, y0, x0 + largeur_barre - 1, hauteur - bas, fill=couleur, outline="")
                if i % saut == 0:
                    self.create_text(centre, hauteur - bas + 12, text=etiquette, font=POLICE, fill=TEXTE_DOUX)

        self._dessin = dessiner
        self.redessiner()

    # ------------------------------------------------------------------ barres horizontales (classement)
    def classement(self, elements: list[tuple[str, Decimal]], couleur: str = BLEU, vide: str = "",
                   format_valeur=None) -> None:
        def dessiner(largeur, hauteur):
            haut, gauche_max = 38, 0.42
            if not elements:
                self.create_text(largeur / 2, hauteur / 2, text=vide, fill=TEXTE_DOUX, font=POLICE)
                return
            maximum = max(float(v) for _, v in elements) or 1
            ligne = min(22, (hauteur - haut - 6) / len(elements))
            debut_barre = largeur * gauche_max
            fin_barre = largeur - 78
            for i, (nom, valeur) in enumerate(elements):
                y = haut + i * ligne
                place = max(8, int((debut_barre - 16) / 6.8))  # caractères qui tiennent avant la barre
                texte = nom if len(nom) <= place else nom[:place - 1] + "…"
                self.create_text(10, y + ligne / 2, text=texte, anchor="w", font=POLICE, fill=TEXTE)
                x1 = debut_barre + (fin_barre - debut_barre) * max(float(valeur), 0) / maximum
                self.create_rectangle(debut_barre, y + 3, max(x1, debut_barre + 1), y + ligne - 3, fill=couleur,
                                      outline="")
                self.create_text(fin_barre + 6, y + ligne / 2, anchor="w", font=POLICE, fill=TEXTE_DOUX,
                                 text=format_valeur(valeur) if format_valeur else str(valeur))

        self._dessin = dessiner
        self.redessiner()

    # ------------------------------------------------------------------ anneau (répartition)
    def anneau(self, elements: list[tuple[str, Decimal]], vide: str = "", format_valeur=None) -> None:
        """Anneau des parts (les plus grandes d'abord, le reste regroupé en « Autres ») avec sa légende."""
        def dessiner(largeur, hauteur):
            parts = [(n, float(v)) for n, v in elements if float(v) > 0]
            total = sum(v for _, v in parts)
            if not total:
                self.create_text(largeur / 2, hauteur / 2, text=vide, fill=TEXTE_DOUX, font=POLICE)
                return
            parts.sort(key=lambda x: -x[1])
            if len(parts) > 6:
                parts = parts[:5] + [("Autres", sum(v for _, v in parts[5:]))]
            rayon = max(20, min((hauteur - 56) / 2, largeur * 0.15))
            cx, cy = 18 + rayon, 36 + (hauteur - 36) / 2
            debut = 90.0
            for i, (nom, v) in enumerate(parts):
                etendue = 360 * v / total
                if etendue >= 1:  # une part plus fine : Tk peindrait un cercle entier
                    self.create_arc(cx - rayon, cy - rayon, cx + rayon, cy + rayon, start=debut,
                                    extent=-min(etendue, 359.9), fill=PALETTE[i % len(PALETTE)], outline=CARTE, width=2)
                debut -= etendue
            interieur = rayon * 0.58
            self.create_oval(cx - interieur, cy - interieur, cx + interieur, cy + interieur, fill=CARTE, outline=CARTE)
            x = cx + rayon + 18
            # total en tête de la légende (dans l'anneau, il chevaucherait le dessin)
            self.create_text(x, 42, text=(format_valeur(Decimal(str(round(total, 2)))) if format_valeur
                                          else f"{total:.0f}"), anchor="w", font=("Segoe UI Semibold", 10), fill=TEXTE)
            ligne = min(21, (hauteur - 66) / max(1, len(parts)))
            for i, (nom, v) in enumerate(parts):
                y = 66 + i * ligne
                self.create_rectangle(x, y - 5, x + 10, y + 5, fill=PALETTE[i % len(PALETTE)], outline="")
                pourcent = f" {100 * v / total:.0f} %"
                place = max(4, int((largeur - x - 22) / 6.8) - len(pourcent))  # nom raccourci, puis la part
                texte = (nom if len(nom) <= place else nom[:place - 1] + "…") + pourcent
                self.create_text(x + 16, y, text=texte, anchor="w", font=POLICE, fill=TEXTE)

        self._dessin = dessiner
        self.redessiner()

    # ------------------------------------------------------------------ courbes d'évolution
    def courbes(self, etiquettes: list[str], series: list[tuple[str, list, str, bool]], vide: str = "") -> None:
        """`series` : [(nom, valeurs (None = pas de point), couleur, pointillés)] sur les mêmes étiquettes."""
        def dessiner(largeur, hauteur):
            bas, gauche, droite = 30, 52, 14
            valeurs = [float(v) for _, vs, _, _ in series for v in vs if v is not None]
            if not etiquettes or not any(valeurs):
                self.create_text(largeur / 2, hauteur / 2, text=vide, fill=TEXTE_DOUX, font=POLICE)
                return
            haut = self._legende(largeur, [(nom, couleur, p) for nom, _, couleur, p in series], ligne=True)
            maximum = _arrondi_haut(max(valeurs))
            zone_h, zone_l = hauteur - haut - bas, largeur - gauche - droite
            for i in range(5):
                y = hauteur - bas - zone_h * i / 4
                self.create_line(gauche, y, largeur - droite, y, fill="#eef1ef")
                self.create_text(gauche - 6, y, text=_court(maximum * i / 4), anchor="e", font=POLICE, fill=TEXTE_DOUX)
            n = len(etiquettes)
            pas = zone_l / max(1, n - 1)
            place = max(len(e) for e in etiquettes) * 6.5 + 12
            saut = max(1, -(-n // max(1, int(zone_l // place))))
            for i, etiquette in enumerate(etiquettes):
                if i % saut == 0:
                    self.create_text(gauche + pas * i, hauteur - bas + 12, text=etiquette, font=POLICE, fill=TEXTE_DOUX)
            for _, vs, couleur, pointilles in series:
                points = [(gauche + pas * i, hauteur - bas - zone_h * float(v) / maximum)
                          for i, v in enumerate(vs) if v is not None]
                if len(points) > 1:
                    self.create_line(*[c for p in points for c in p], fill=couleur, width=2, smooth=True,
                                     dash=(5, 3) if pointilles else None)
                for px, py in points if len(points) <= 40 else []:
                    self.create_oval(px - 2, py - 2, px + 2, py + 2, fill=couleur, outline=couleur)

        self._dessin = dessiner
        self.redessiner()


PALETTE = ["#0b8fd8", "#1a9b3c", "#f6b81a", "#d7263d", "#7b5ea7", "#9aa5a0"]
