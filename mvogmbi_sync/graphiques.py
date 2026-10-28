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


def format_argent(valeur) -> str:
    """« 1 234,56 $ » pour les infobulles."""
    return f"{float(valeur):,.2f} $".replace(",", " ").replace(".", ",")


def _court(valeur: float) -> str:
    """« 1,2 k$ », « 250 $ » pour les axes."""
    if abs(valeur) >= 1000:
        return f"{valeur / 1000:.1f} k$".replace(".", ",")
    return f"{valeur:.0f} $"


def _arrondi_haut(valeur: float) -> float:
    """Haut de l'axe vertical : juste au-dessus de la plus grande valeur (5 % de marge pour son étiquette), avec
    4 graduations rondes et serrées (513 -> 600 : 150, 300, 450, 600 ; et non 1 000), pour que le graphique occupe
    toute sa hauteur."""
    if valeur <= 0:
        return 1
    import math

    graduation = valeur * 1.05 / 4  # 4 graduations rondes jusqu'au haut de l'axe
    puissance = 10 ** math.floor(math.log10(graduation))
    for pas in (1, 1.2, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10):
        if graduation <= pas * puissance:
            return 4 * pas * puissance
    return 40 * puissance


class Graphique(tk.Canvas):
    """Canvas qui garde ses données et se redessine à la bonne taille."""

    def __init__(self, parent, hauteur: int = 200, titre: str = ""):
        super().__init__(parent, height=hauteur, background=CARTE, highlightthickness=1,
                         highlightbackground=BORDURE)
        self.titre = titre
        self._dessin = None
        self._survol = None   # positions et valeurs des points, pour l'infobulle
        self.bind("<Configure>", lambda _e: self.redessiner())
        self.bind("<Motion>", self._bulle)
        self.bind("<Leave>", lambda _e: self.delete("bulle"))
        self.bind("<Button-3>", self._menu_export)

    def _menu_export(self, evenement) -> None:
        """Clic droit : le graphique en PDF ou en image."""
        from .langues import t

        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="📕  " + t("Exporter le graphique en PDF…"), command=lambda: self.exporter("pdf"))
        menu.add_command(label="🖼  " + t("Enregistrer le graphique en image (PNG)…"),
                         command=lambda: self.exporter("png"))
        menu.tk_popup(evenement.x_root, evenement.y_root)

    def exporter(self, format_: str = "pdf") -> None:
        from .export_tableau import demander_et_ecrire, ecrire_pdf, image_widget
        from .langues import t

        self.delete("bulle")
        nom = self.titre or t("Graphique")
        image = image_widget(self)
        demander_et_ecrire(self, nom, format_, lambda chemin: image.save(chemin) if format_ == "png"
                           else ecrire_pdf(chemin, nom, [], [], [image]))

    def _bulle(self, evenement) -> None:
        """Infobulle au survol : repère vertical, étiquette du point (date, heure…) et valeur de chaque série."""
        self.delete("bulle")
        s = self._survol
        if not s:
            return
        if s.get("zones") is not None:  # anneau, classement, carte de chaleur : zone survolée
            for test, lignes in s["zones"]:
                if test(evenement.x, evenement.y):
                    self._dessiner_bulle(evenement.x, evenement.y, lignes)
                    return
            return
        if not s["xs"]:
            return
        i = min(range(len(s["xs"])), key=lambda k: abs(s["xs"][k] - evenement.x))
        if abs(s["xs"][i] - evenement.x) > max(12, s["pas"]):
            return
        x = s["xs"][i]
        self.create_line(x, s["haut"], x, s["bas"], fill="#9aa5a0", dash=(2, 2), tags="bulle")
        lignes = [(s["etiquettes"][i], TEXTE, None)] + [
            (f"{nom} : {format_argent(vs[i])}", TEXTE, couleur) for nom, vs, couleur in s["series"]
            if i < len(vs) and vs[i] is not None]
        self._dessiner_bulle(x, evenement.y, lignes)

    def _dessiner_bulle(self, x: float, y_souris: float, lignes: list[tuple[str, str, str | None]]) -> None:
        largeur_bulle = max(7.2 * len(texte) for texte, _, _ in lignes) + 30
        hauteur_bulle = 18 * len(lignes) + 10
        bx = x + 12 if x + 12 + largeur_bulle < self.winfo_width() else x - 12 - largeur_bulle
        by = max(4, min(y_souris - hauteur_bulle / 2, self.winfo_height() - hauteur_bulle - 4))
        self.create_rectangle(bx + 2, by + 2, bx + largeur_bulle + 2, by + hauteur_bulle + 2, fill="#d9dedb",
                              outline="", tags="bulle")
        self.create_rectangle(bx, by, bx + largeur_bulle, by + hauteur_bulle, fill="white", outline=BORDURE,
                              tags="bulle")
        for k, (texte, encre, couleur) in enumerate(lignes):
            y = by + 14 + 18 * k
            if couleur:
                self.create_rectangle(bx + 10, y - 4, bx + 18, y + 4, fill=couleur, outline="", tags="bulle")
            self.create_text(bx + (24 if couleur else 10), y, text=texte, anchor="w", tags="bulle",
                             font=("Segoe UI Semibold", 9) if not couleur else POLICE, fill=encre)

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
        self._survol = None
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
            self._survol = {"xs": [gauche + pas * (i + 0.5) for i in range(len(etiquettes))], "pas": pas / 2,
                            "haut": haut, "bas": hauteur - bas, "etiquettes": etiquettes,
                            "series": [(nom, vs, couleur) for nom, vs, couleur in series]}
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
            premiere = [float(v or 0) for v in series[0][1]]
            if len(etiquettes) <= 14 and len(series) == 1:  # peu de barres : la valeur au-dessus de chacune
                for i, v in enumerate(premiere):
                    if v > 0:
                        y0 = hauteur - bas - zone_h * v / maximum
                        self.create_text(gauche + pas * (i + 0.5), y0 - 7, text=_court(v), font=("Segoe UI", 8),
                                         fill=TEXTE)
            self._moyenne(premiere, gauche, largeur - droite, hauteur - bas, zone_h, maximum)

        self._dessin = dessiner
        self.redessiner()

    def _moyenne(self, valeurs: list[float], x0: float, x1: float, bas_y: float, zone_h: float, maximum: float) -> None:
        """Ligne pointillée de la moyenne (valeurs non nulles), avec son montant à droite."""
        utiles = [v for v in valeurs if v]
        if len(utiles) < 3:
            return
        moyenne = sum(utiles) / len(utiles)
        y = bas_y - zone_h * moyenne / maximum
        self.create_line(x0, y, x1, y, fill="#d7263d", dash=(6, 4))
        self.create_text(x1 - 4, y - 8, text=f"moy. {_court(moyenne)}", anchor="e", font=("Segoe UI", 8),
                         fill="#d7263d")

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
            total = sum(float(v) for _, v in elements) or 1
            self._survol = {"zones": [
                ((lambda x, y, y0=haut + i * ligne: y0 <= y < y0 + ligne),
                 [(nom, TEXTE, None), ((format_valeur(v) if format_valeur else str(v))
                                       + f" — {100 * float(v) / total:.1f} % du total", TEXTE, couleur)])
                for i, (nom, v) in enumerate(elements)]}

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
            zones = []
            for i, (nom, v) in enumerate(parts):
                etendue = 360 * v / total
                zones.append(((lambda x, y, d=debut, e=etendue: _dans_part(x, y, cx, cy, rayon, rayon * 0.58, d, e)),
                              [(nom, TEXTE, None), ((format_valeur(Decimal(str(round(v, 2)))) if format_valeur
                                                     else f"{v:.0f}") + f" — {100 * v / total:.1f} %", TEXTE,
                                                    PALETTE[i % len(PALETTE)])]))
                if etendue >= 1:  # une part plus fine : Tk peindrait un cercle entier
                    self.create_arc(cx - rayon, cy - rayon, cx + rayon, cy + rayon, start=debut,
                                    extent=-min(etendue, 359.9), fill=PALETTE[i % len(PALETTE)], outline=CARTE, width=2)
                debut -= etendue
            self._survol = {"zones": zones}
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
            self._survol = {"xs": [gauche + pas * i for i in range(n)], "pas": pas / 2, "haut": haut,
                            "bas": hauteur - bas, "etiquettes": etiquettes,
                            "series": [(nom, vs, couleur) for nom, vs, couleur, _ in series]}
            place = max(len(e) for e in etiquettes) * 6.5 + 12
            saut = max(1, -(-n // max(1, int(zone_l // place))))
            for i, etiquette in enumerate(etiquettes):
                if i % saut == 0:
                    self.create_text(gauche + pas * i, hauteur - bas + 12, text=etiquette, font=POLICE, fill=TEXTE_DOUX)
            principale = [(gauche + pas * i, hauteur - bas - zone_h * float(v) / maximum)
                          for i, v in enumerate(series[0][1]) if v is not None]
            if len(principale) > 1:  # aire sous la courbe principale
                self.create_polygon(principale[0][0], hauteur - bas, *[c for p in principale for c in p],
                                    principale[-1][0], hauteur - bas, fill=AIRE, outline="", smooth=False)
            self._moyenne([float(v) for v in series[0][1] if v is not None], gauche, largeur - droite, hauteur - bas,
                          zone_h, maximum)
            for _, vs, couleur, pointilles in series:
                points = [(gauche + pas * i, hauteur - bas - zone_h * float(v) / maximum)
                          for i, v in enumerate(vs) if v is not None]
                if len(points) > 1:
                    self.create_line(*[c for p in points for c in p], fill=couleur, width=2, smooth=True,
                                     dash=(5, 3) if pointilles else None)
                for px, py in points if len(points) <= 40 else []:
                    self.create_oval(px - 2, py - 2, px + 2, py + 2, fill=couleur, outline=couleur)
            valeurs_1 = [(i, float(v)) for i, v in enumerate(series[0][1]) if v is not None]
            if valeurs_1:  # point le plus haut de la série principale
                i, v = max(valeurs_1, key=lambda x: x[1])
                px, py = gauche + pas * i, hauteur - bas - zone_h * v / maximum
                self.create_oval(px - 4, py - 4, px + 4, py + 4, fill="white", outline=series[0][2], width=2)
                self.create_text(px, py - 12, text=f"max {_court(v)} ({etiquettes[i]})", font=("Segoe UI Semibold", 8),
                                 fill=TEXTE, anchor="s" if py > haut + 30 else "n")

        self._dessin = dessiner
        self.redessiner()

    # ------------------------------------------------------------------ carte de chaleur (jour × heure)
    def chaleur(self, lignes: list[str], colonnes: list[str], valeurs: list[list], vide: str = "") -> None:
        """Grille colorée (du blanc au bleu foncé) : une case par ligne × colonne, infobulle au survol."""
        def dessiner(largeur, hauteur):
            plat = [float(v or 0) for rang in valeurs for v in rang]
            if not plat or not any(plat):
                self.create_text(largeur / 2, hauteur / 2, text=vide, fill=TEXTE_DOUX, font=POLICE)
                return
            maximum = max(plat)
            gauche, haut, bas, droite = 80, 40, 24, 12
            l_case = (largeur - gauche - droite) / len(colonnes)
            h_case = (hauteur - haut - bas) / len(lignes)
            zones = []
            for r_, nom_ligne in enumerate(lignes):
                y0 = haut + r_ * h_case
                self.create_text(gauche - 8, y0 + h_case / 2, text=nom_ligne, anchor="e", font=POLICE, fill=TEXTE)
                for c_, nom_col in enumerate(colonnes):
                    v = float(valeurs[r_][c_] or 0)
                    x0 = gauche + c_ * l_case
                    self.create_rectangle(x0 + 1, y0 + 1, x0 + l_case - 1, y0 + h_case - 1,
                                          fill=_degrade(v / maximum), outline="")
                    if v and l_case > 34 and h_case > 16:
                        self.create_text(x0 + l_case / 2, y0 + h_case / 2, text=_court(v).replace(" $", ""),
                                         font=("Segoe UI", 7), fill="white" if v / maximum > 0.55 else TEXTE)
                    zones.append(((lambda x, y, a=x0, b=y0: a <= x < a + l_case and b <= y < b + h_case),
                                  [(f"{nom_ligne} {nom_col}", TEXTE, None),
                                   (format_argent(v), TEXTE, _degrade(v / maximum))]))
            for c_, nom_col in enumerate(colonnes):
                if len(colonnes) <= 24 or c_ % 2 == 0:
                    self.create_text(gauche + (c_ + 0.5) * l_case, hauteur - bas + 10, text=nom_col, font=POLICE,
                                     fill=TEXTE_DOUX)
            self._survol = {"zones": zones}

        self._dessin = dessiner
        self.redessiner()


AIRE = "#e1f1fb"  # fond sous la courbe principale


def _degrade(part: float) -> str:
    """Blanc (0) -> bleu Clover (1)."""
    part = max(0.0, min(1.0, part))
    debut, fin = (247, 251, 255), (11, 102, 170)
    return "#%02x%02x%02x" % tuple(int(a + (b - a) * part) for a, b in zip(debut, fin))


def _dans_part(x: float, y: float, cx: float, cy: float, rayon: float, interieur: float, debut: float,
               etendue: float) -> bool:
    """Le point (x, y) est-il dans la part d'anneau qui part de `debut` (degrés) sur `etendue` (sens horaire) ?"""
    import math

    distance = math.hypot(x - cx, y - cy)
    if not interieur <= distance <= rayon:
        return False
    angle = math.degrees(math.atan2(cy - y, x - cx)) % 360
    ecart = (debut - angle) % 360
    return ecart <= etendue


PALETTE = ["#0b8fd8", "#1a9b3c", "#f6b81a", "#d7263d", "#7b5ea7", "#9aa5a0"]
