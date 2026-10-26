"""Éléments visuels communs de l'interface : couleurs du Marché MVOG-MBI, boutons arrondis, filigrane du logo.

Les boutons sont des étiquettes portant une image arrondie dessinée par Pillow (tkinter ne sait pas arrondir
les coins) : une image par état (normal, survol), fondue sur la couleur du parent pour des bords nets.
"""

from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont
from pathlib import Path
from tkinter import ttk

# Couleurs du marché : vert, rouge, jaune
VERT = "#1a9b3c"
VERT_FONCE = "#13772d"
VERT_PALE = "#e8f5ec"
ROUGE = "#d7263d"
ROUGE_FONCE = "#a81d2f"
JAUNE = "#f6b81a"
JAUNE_FONCE = "#dfa20c"
TEXTE = "#1f2d24"
TEXTE_DOUX = "#6b7a70"
FOND = "#fafafa"
CARTE = "#ffffff"
BORDURE = "#e2e8e4"
MENU_FOND = "#eef4f0"
MENU_SURVOL = "#e2ede6"
MENU_ACTIF = "#d3eadb"

LOGO = Path(__file__).resolve().parent / "ressources" / "logo.png"
ICONE = Path(__file__).resolve().parent / "ressources" / "MVOGMBI_Sync.ico"  # chariot
ID_APPLICATION = "ConceptInformatique.MVOGMBI_Sync"  # regroupe la fenêtre et ses raccourcis dans la barre des tâches

# genre -> (fond, fond au survol, texte, bordure)
GENRES = {
    "principal": (VERT, VERT_FONCE, "#ffffff", None),
    "secondaire": ("#ffffff", VERT_PALE, VERT_FONCE, "#b9d9c3"),
    "danger": (ROUGE, ROUGE_FONCE, "#ffffff", None),
    "accent": (JAUNE, JAUNE_FONCE, "#3a2a00", None),
}


def fond_de(widget) -> str:
    """Couleur de fond d'un widget tk ou ttk."""
    try:
        return str(widget.cget("background"))
    except tk.TclError:
        style = ""
        try:
            style = str(widget.cget("style"))
        except tk.TclError:
            pass
        return ttk.Style(widget).lookup(style or widget.winfo_class(), "background") or FOND


def _image_arrondie(largeur: int, hauteur: int, couleur: str, bordure: str | None, fond: str):
    from PIL import Image, ImageDraw, ImageTk

    echelle = 4  # dessin agrandi puis réduit : bords lissés
    grande = Image.new("RGB", (largeur * echelle, hauteur * echelle), fond)
    dessin = ImageDraw.Draw(grande)
    rayon = min(hauteur // 2, 9) * echelle
    dessin.rounded_rectangle((0, 0, largeur * echelle - 1, hauteur * echelle - 1), radius=rayon, fill=couleur,
                             outline=bordure, width=(echelle if bordure else 0))
    return ImageTk.PhotoImage(grande.resize((largeur, hauteur), Image.LANCZOS))


class Bouton(tk.Label):
    """Bouton arrondi aux couleurs du marché : principal (vert), secondaire (blanc), danger (rouge), accent (jaune)."""

    def __init__(self, parent, texte: str, commande, genre: str = "principal", fond: str | None = None,
                 petit: bool = False, largeur: int | None = None):
        couleur, survol, encre, bordure = GENRES[genre]
        fond = fond or fond_de(parent)
        police = tkfont.Font(family="Segoe UI Semibold", size=9 if petit else 10)
        l = largeur or police.measure(texte) + (26 if petit else 36)
        h = police.metrics("linespace") + (10 if petit else 16)
        try:
            self._images = (_image_arrondie(l, h, couleur, bordure, fond), _image_arrondie(l, h, survol, bordure, fond))
            options = dict(image=self._images[0], compound="center")
        except Exception:  # sans Pillow : bouton plat
            self._images = None
            options = dict(background=couleur, padx=16, pady=6)
        super().__init__(parent, text=texte, font=police, foreground=encre, cursor="hand2", borderwidth=0,
                         **{"background": fond, **options})
        self._commande = commande
        self._couleurs = (couleur, survol)
        self.bind("<Enter>", lambda _e: self._etat(1))
        self.bind("<Leave>", lambda _e: self._etat(0))
        self.bind("<ButtonRelease-1>", self._clic)

    def _etat(self, survol: int) -> None:
        if self._images:
            self.configure(image=self._images[survol])
        else:
            self.configure(background=self._couleurs[survol])

    def _clic(self, evenement) -> None:
        if 0 <= evenement.x < self.winfo_width() and 0 <= evenement.y < self.winfo_height() and self._commande:
            self._commande()


def image_filigrane(taille: int, fond: str, opacite: float = 0.10):
    """Logo pâli (fond blanc rendu transparent) fondu sur la couleur `fond`, pour le fond des pages."""
    from PIL import Image, ImageTk

    logo = Image.open(LOGO).convert("RGB")
    logo.thumbnail((taille, taille), Image.LANCZOS)
    gris = logo.convert("L")
    # opacité proportionnelle à la densité du trait : le fond clair du logo disparaît sans laisser de cadre
    masque = gris.point(lambda v: 0 if v > 200 else int(255 * opacite * min(1.0, (205 - v) / 80)))
    image = Image.new("RGB", logo.size, fond)
    image.paste(logo, mask=masque)
    return ImageTk.PhotoImage(image)


def poser_filigrane(page, image, coin: str = "se", marge: int = 16) -> tk.Label:
    """Pose le logo pâli dans un coin de la page, derrière tous les autres éléments."""
    etiquette = tk.Label(page, image=image, borderwidth=0, background=fond_de(page))
    positions = {"se": (1.0, 1.0, -marge, -marge), "ne": (1.0, 0.0, -marge, marge)}
    relx, rely, x, y = positions[coin]
    etiquette.place(relx=relx, rely=rely, x=x, y=y, anchor=coin)
    etiquette.lower()
    return etiquette
