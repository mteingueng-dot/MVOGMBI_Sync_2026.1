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


class ChampDate(tk.Frame):
    """Champ date AAAA-MM-JJ avec un bouton 📅 qui ouvre un calendrier cliquable (aucune bibliothèque externe)."""

    def __init__(self, parent, variable: tk.StringVar, largeur: int = 11, fond: str | None = None):
        fond = fond or fond_de(parent)
        super().__init__(parent, background=fond)
        self.variable = variable
        ttk.Entry(self, textvariable=variable, width=largeur).pack(side="left")
        bouton = tk.Label(self, text="📅", font=("Segoe UI Emoji", 11), background=fond, cursor="hand2", padx=4)
        bouton.pack(side="left")
        bouton.bind("<Button-1>", lambda _e: self.ouvrir())
        self.fenetre = None

    def ouvrir(self) -> None:
        import calendar
        from datetime import date

        from .langues import courante

        if self.fenetre and self.fenetre.winfo_exists():
            self.fenetre.destroy()
            return
        try:
            choisie = date.fromisoformat(self.variable.get().strip())
        except ValueError:
            choisie = date.today()
        mois_noms = (["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
                      "novembre", "décembre"] if courante() == "fr" else list(calendar.month_name)[1:])
        jours_noms = ["L", "M", "M", "J", "V", "S", "D"] if courante() == "fr" else ["M", "T", "W", "T", "F", "S", "S"]
        etat = {"annee": choisie.year, "mois": choisie.month}
        fenetre = self.fenetre = tk.Toplevel(self)
        fenetre.overrideredirect(True)
        fenetre.configure(background=BORDURE)
        fenetre.geometry(f"+{self.winfo_rootx()}+{self.winfo_rooty() + self.winfo_height() + 2}")
        cadre = tk.Frame(fenetre, background=CARTE, padx=8, pady=6)
        cadre.pack(padx=1, pady=1)
        entete = tk.Frame(cadre, background=VERT)
        entete.pack(fill="x")
        titre = tk.Label(entete, background=VERT, foreground="white", font=("Segoe UI Semibold", 10))
        grille = tk.Frame(cadre, background=CARTE)
        grille.pack(pady=(4, 0))

        def changer(delta: int) -> None:
            mois = etat["mois"] + delta
            etat["annee"] += (mois - 1) // 12
            etat["mois"] = (mois - 1) % 12 + 1
            dessiner()

        def choisir(jour: date) -> None:
            self.variable.set(jour.isoformat())
            fenetre.destroy()

        def dessiner() -> None:
            titre.configure(text=f"{mois_noms[etat['mois'] - 1].capitalize()} {etat['annee']}")
            for enfant in grille.winfo_children():
                enfant.destroy()
            for colonne, nom in enumerate(jours_noms):
                tk.Label(grille, text=nom, width=3, background=CARTE, foreground=TEXTE_DOUX,
                         font=("Segoe UI", 8, "bold")).grid(row=0, column=colonne)
            aujourd_hui = date.today()
            for rang, semaine in enumerate(calendar.Calendar().monthdatescalendar(etat["annee"], etat["mois"]), start=1):
                for colonne, jour in enumerate(semaine):
                    dans_mois = jour.month == etat["mois"]
                    couleur, encre = (VERT, "white") if jour == choisie else (
                        (VERT_PALE, VERT_FONCE) if jour == aujourd_hui else (CARTE, TEXTE if dans_mois else "#b5bfb8"))
                    case = tk.Label(grille, text=str(jour.day), width=3, background=couleur, foreground=encre,
                                    font=("Segoe UI", 9, "bold" if jour == choisie else "normal"), cursor="hand2", pady=2)
                    case.grid(row=rang, column=colonne, padx=1, pady=1)
                    case.bind("<Button-1>", lambda _e, j=jour: choisir(j))
                    case.bind("<Enter>", lambda _e, c=case, j=jour: c.configure(background=JAUNE) if j != choisie else None)
                    case.bind("<Leave>", lambda _e, c=case, f=couleur: c.configure(background=f))

        for texte, delta, cote in (("‹", -1, "left"), ("›", 1, "right")):
            fleche = tk.Label(entete, text=texte, background=VERT, foreground="white", font=("Segoe UI Semibold", 13),
                              cursor="hand2", padx=8)
            fleche.pack(side=cote)
            fleche.bind("<Button-1>", lambda _e, d=delta: changer(d))
        titre.pack(side="left", expand=True)
        pied = tk.Label(cadre, text="Aujourd'hui" if courante() == "fr" else "Today", background=CARTE,
                        foreground=VERT_FONCE, font=("Segoe UI", 9, "underline"), cursor="hand2")
        pied.pack(pady=(4, 0))
        pied.bind("<Button-1>", lambda _e: choisir(date.today()))
        fenetre.bind("<Escape>", lambda _e: fenetre.destroy())
        fenetre.attributes("-topmost", True)
        # un clic ailleurs dans l'application referme le calendrier
        racine = self.winfo_toplevel()
        identifiant = racine.bind("<Button-1>", lambda e: None if str(e.widget).startswith(str(fenetre))
                                  else fenetre.destroy(), add="+")
        fenetre.bind("<Destroy>", lambda e: racine.unbind("<Button-1>", identifiant) if e.widget is fenetre else None)
        dessiner()


class ChampRecherche(tk.Frame):
    """Champ de saisie avec recherche rapide : la liste des choix correspondants s'affiche dessous pendant la frappe.

    Flèches haut/bas pour parcourir, Entrée ou clic pour choisir, Échap pour fermer ; « ▾ » montre toute la liste.
    """

    def __init__(self, parent, variable: tk.StringVar, valeurs, largeur: int = 34, au_choix=None):
        fond = fond_de(parent)
        super().__init__(parent, background=fond)
        self.variable, self.valeurs, self.au_choix = variable, list(valeurs), au_choix
        self.champ = ttk.Entry(self, textvariable=variable, width=largeur)
        self.champ.pack(side="left")
        fleche = tk.Label(self, text="▾", background=fond, foreground=TEXTE_DOUX, font=("Segoe UI", 11),
                          cursor="hand2", padx=4)
        fleche.pack(side="left")
        fleche.bind("<Button-1>", lambda _e: self.afficher(tout=True))
        self.champ.bind("<KeyRelease>", self._frappe)
        self.champ.bind("<Down>", lambda _e: self._deplacer(1))
        self.champ.bind("<Up>", lambda _e: self._deplacer(-1))
        self.champ.bind("<Return>", lambda _e: self._valider())
        self.champ.bind("<Escape>", lambda _e: self.fermer())
        self.champ.bind("<FocusOut>", lambda _e: self.after(200, self._fermer_si_ailleurs))
        self.popup = None
        self.liste = None

    def configurer_valeurs(self, valeurs) -> None:
        self.valeurs = list(valeurs)

    def _correspondances(self, tout: bool = False) -> list[str]:
        from .correspondance import normaliser

        texte = normaliser(self.variable.get())
        if tout or not texte:
            return self.valeurs
        mots = texte.split()
        return [v for v in self.valeurs if all(m in normaliser(v) for m in mots)]

    def _frappe(self, evenement) -> None:
        if evenement.keysym in ("Up", "Down", "Return", "Escape", "Tab"):
            return
        self.afficher()

    def afficher(self, tout: bool = False) -> None:
        choix = self._correspondances(tout)
        if not choix:
            self.fermer()
            return
        if not self.popup or not self.popup.winfo_exists():
            self.popup = tk.Toplevel(self)
            self.popup.overrideredirect(True)
            self.popup.attributes("-topmost", True)
            self.popup.configure(background=BORDURE)
            self.liste = tk.Listbox(self.popup, height=8, activestyle="none", font=("Segoe UI", 10), borderwidth=0,
                                    highlightthickness=0, selectbackground=VERT, selectforeground="white")
            self.liste.pack(padx=1, pady=1, fill="both", expand=True)
            self.liste.bind("<ButtonRelease-1>", lambda _e: self._valider())
        self.popup.geometry(f"{self.champ.winfo_width() + 24}x{min(8, len(choix)) * 22 + 4}"
                            f"+{self.champ.winfo_rootx()}+{self.champ.winfo_rooty() + self.champ.winfo_height()}")
        self.liste.delete(0, "end")
        for v in choix:
            self.liste.insert("end", v)
        self.liste.selection_clear(0, "end")
        self.liste.selection_set(0)

    def _deplacer(self, pas: int) -> str:
        if not self.popup or not self.popup.winfo_exists():
            self.afficher(tout=not self.variable.get().strip())
            return "break"
        actuel = (self.liste.curselection() or (0,))[0]
        nouveau = max(0, min(self.liste.size() - 1, actuel + pas))
        self.liste.selection_clear(0, "end")
        self.liste.selection_set(nouveau)
        self.liste.see(nouveau)
        return "break"

    def _valider(self) -> str:
        if self.popup and self.popup.winfo_exists() and self.liste.curselection():
            self.variable.set(self.liste.get(self.liste.curselection()[0]))
            self.champ.icursor("end")
            if self.au_choix:
                self.au_choix(self.variable.get())
        self.fermer()
        return "break"

    def _fermer_si_ailleurs(self) -> None:
        focus = self.focus_get()
        if focus is not self.champ and (not self.liste or focus is not self.liste):
            self.fermer()

    def fermer(self) -> None:
        if self.popup and self.popup.winfo_exists():
            self.popup.destroy()
        self.popup = None


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
