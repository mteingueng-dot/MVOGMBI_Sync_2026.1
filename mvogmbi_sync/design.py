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
            # droit « Supprimer » du profil (demande du propriétaire du 2026-10-30) : tous les boutons Supprimer / 🗑
            if est_suppression(self.cget("text")) and not action_permise(self, "Supprimer"):
                return
            _auditer(self, self.cget("text"))
            self._commande()


def _auditer(widget, texte: str) -> None:
    """Table d'audit (audit.py) : bouton cliqué et fenêtre où il se trouve."""
    try:
        from . import audit

        fenetre, w = "", widget
        while w is not None:
            if isinstance(w, FenetreOutil) or isinstance(w, tk.Toplevel):
                fenetre = w.title() if callable(getattr(w, "title", None)) else ""
                break
            w = w.master
        audit.noter(None, " ".join(str(texte).split()), fenetre or "Fenêtre principale")
    except Exception:
        pass


def est_suppression(texte: str) -> bool:
    """Bouton qui supprime : « 🗑 », « Supprimer… » ou « Delete… »."""
    from .langues import t

    texte = (texte or "").strip()
    return "🗑" in texte or any(mot in texte for mot in ("Supprimer", "Delete", t("Supprimer")))


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


def apres_frappe(widget, fonction, delai: int = 60):
    """Gestionnaire de <KeyRelease> qui lance `fonction` une seule fois, `delai` ms après la dernière touche : le
    tableau n'est plus refait à chaque lettre (la frappe reste fluide)."""
    attente = {"id": None}

    def gerer(evenement=None):
        if evenement is not None and getattr(evenement, "keysym", "") in ("Return", "Down", "Up", "Tab"):
            return
        if attente["id"]:
            widget.after_cancel(attente["id"])
        attente["id"] = widget.after(delai, fonction)

    return gerer


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
        self._normalisees = None  # préparées au premier besoin, une seule fois

    def _correspondances(self, tout: bool = False) -> list[str]:
        from .correspondance import normaliser

        texte = normaliser(self.variable.get())
        if tout or not texte:
            return self.valeurs
        if getattr(self, "_normalisees", None) is None:
            self._normalisees = [normaliser(v) for v in self.valeurs]
        mots = texte.split()
        return [v for v, n in zip(self.valeurs, self._normalisees) if all(m in n for m in mots)]

    def _frappe(self, evenement) -> None:
        if evenement.keysym in ("Up", "Down", "Return", "Escape", "Tab"):
            return
        if getattr(self, "_attente", None):  # la liste suit la frappe sans la ralentir
            self.after_cancel(self._attente)
        self._attente = self.after(50, self.afficher)

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
        self.liste.insert("end", *choix[:500])  # 500 au plus : la frappe affine
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
    # image transparente : seul le dessin pâli est posé, le fond de la page reste visible (aucun carré)
    image = logo.convert("RGBA")
    image.putalpha(masque)
    return ImageTk.PhotoImage(image)


def poser_filigrane(page, image, coin: str = "se", marge: int = 16) -> tk.Label:
    """Pose le logo pâli dans un coin de la page, derrière tous les autres éléments."""
    etiquette = tk.Label(page, image=image, borderwidth=0, background=fond_de(page))
    positions = {"se": (1.0, 1.0, -marge, -marge), "ne": (1.0, 0.0, -marge, marge)}
    relx, rely, x, y = positions[coin]
    etiquette.place(relx=relx, rely=rely, x=x, y=y, anchor=coin)
    etiquette.lower()
    return etiquette


# --------------------------------------------------------------------------------------------- tableaux et pages
ENTETE_TABLEAU = "#1f7a3a"   # vert des en-têtes de colonnes
RAYURE = "#f4f8f5"           # une ligne sur deux
SELECTION = "#cfe9d7"        # ligne choisie


def styler(style: ttk.Style) -> None:
    """Styles communs : tableaux (en-têtes verts, lignes hautes, rayures, sélection), cadres en cartes."""
    try:  # en-tête dessiné par les éléments du thème « default » : couleurs libres (Sun Valley impose des images)
        style.element_create("Entete.cell", "from", "default", "Treeheading.cell")
        style.element_create("Entete.border", "from", "default", "Treeheading.border")
    except tk.TclError:
        pass
    style.layout("Treeview.Heading", [
        ("Entete.cell", {"sticky": "nswe"}),
        ("Entete.border", {"sticky": "nswe", "children": [
            ("Treeheading.padding", {"sticky": "nswe", "children": [
                ("Treeheading.image", {"side": "right", "sticky": ""}),
                ("Treeheading.text", {"sticky": "we"})]})]})])
    style.configure("Treeview.Heading", background=ENTETE_TABLEAU, foreground="#ffffff", relief="flat",
                    borderwidth=0, font=("Segoe UI Semibold", 9), padding=(8, 7))
    style.map("Treeview.Heading", background=[("active", VERT_FONCE)], foreground=[("active", "#ffffff")])
    style.configure("Treeview", rowheight=30, font=("Segoe UI", 10), background=CARTE, fieldbackground=CARTE,
                    foreground=TEXTE, borderwidth=0)
    style.map("Treeview", background=[("selected", SELECTION)], foreground=[("selected", TEXTE)])
    racine = style.master
    if racine is not None:
        _couleurs_listes(racine)
        # Sun Valley repeint toutes les listes en bleu (tk_setPalette) quand le thème s'applique : on repasse après
        # <<ThemeChanged>> arrive à CHAQUE élément de l'écran (459 fois au démarrage, 5,6 s perdues, mesuré le
        # 2026-10-30) : un seul passage, 50 ms après le dernier
        attente = {"id": None}

        def plus_tard(_e=None):
            if attente["id"] is not None:
                racine.after_cancel(attente["id"])
            attente["id"] = racine.after(50, lambda: (attente.update(id=None), _couleurs_listes(racine)))

        racine.bind("<<ThemeChanged>>", plus_tard, add="+")
    style.configure("TLabelframe", background=CARTE, bordercolor=BORDURE, relief="solid", borderwidth=1)
    style.configure("TLabelframe.Label", background=CARTE, foreground=VERT_FONCE, font=("Segoe UI Semibold", 10))


COULEURS_LISTES = (("selectBackground", SELECTION), ("selectForeground", TEXTE), ("relief", "flat"),
                   ("borderWidth", 0), ("highlightThickness", 1), ("highlightBackground", BORDURE),
                   ("highlightColor", VERT), ("background", CARTE), ("foreground", TEXTE))


def _couleurs_listes(racine) -> None:
    """Listes (tk.Listbox) aux couleurs des tableaux : nouvelles (base d'options) et existantes."""
    for option, valeur in COULEURS_LISTES + (("activeStyle", "none"),):
        racine.option_add(f"*Listbox.{option}", valeur)
    a_voir = [racine]
    while a_voir:
        w = a_voir.pop()
        a_voir.extend(w.winfo_children())
        if w.winfo_class() == "Listbox" and str(w.cget("selectbackground")) != VERT:  # recherche rapide : vert plein
            w.configure(**{o.lower(): v for o, v in COULEURS_LISTES})


def rayer(tableau: ttk.Treeview) -> None:
    """Une ligne sur deux légèrement teintée (sauf les lignes déjà colorées par leur état)."""
    tableau.tag_configure("rayure", background=RAYURE)
    colorees = set()
    for ligne in tableau.get_children():
        tags = [t for t in tableau.item(ligne, "tags") if t != "rayure"]
        colorees.update(t for t in tags if tableau.tag_configure(t, "background"))
    for i, ligne in enumerate(tableau.get_children()):
        tags = [t for t in tableau.item(ligne, "tags") if t != "rayure"]
        if i % 2 and not any(t in colorees for t in tags):
            tags.append("rayure")
        tableau.item(ligne, tags=tags)


class Rangee(tk.Frame):
    """Rangée de boutons et de champs qui passe à la ligne quand la fenêtre est trop étroite : tout reste visible,
    quelle que soit la largeur (demande du propriétaire du 2026-10-28). Les éléments sont créés avec la rangée pour
    parent puis ajoutés dans l'ordre par `ajouter` ; `groupe()` garde ensemble un libellé et son champ."""

    def __init__(self, parent, ecart_lignes: int = 6):
        super().__init__(parent, background=fond_de(parent), height=1)
        self.ecart_lignes = ecart_lignes
        self.elements: list[tuple[tk.Widget, int]] = []
        self._largeur = 0
        self.bind("<Configure>", lambda _e: self._disposer())

    def groupe(self) -> tk.Frame:
        return tk.Frame(self, background=fond_de(self))

    def ajouter(self, widget, espace: int = 8):
        self.elements.append((widget, espace))
        widget.bind("<Configure>", lambda _e: self._plus_tard(), add="+")  # texte changé : largeur changée
        self._plus_tard()
        return widget

    def montrer(self, widget, visible: bool) -> None:
        """Affiche ou cache un élément de la rangée (les suivants se resserrent)."""
        widget._cache_rangee = not visible
        if not visible:
            widget.place_forget()
        self._plus_tard()

    def _plus_tard(self) -> None:
        if not getattr(self, "_prevu", False):
            self._prevu = True
            self.after_idle(self._disposer)

    def _disposer(self) -> None:
        self._prevu = False
        largeur = self.winfo_width()
        if largeur <= 1:
            return
        lignes, ligne, x = [], [], 0
        for w, espace in self.elements:
            if not w.winfo_exists() or getattr(w, "_cache_rangee", False):
                continue
            l = w.winfo_reqwidth()
            if ligne and x + l > largeur:
                lignes.append(ligne)
                ligne, x = [], 0
            ligne.append((w, x))
            x += l + espace
        if ligne:
            lignes.append(ligne)
        y = 0
        for ligne in lignes:
            hauteur = max(w.winfo_reqheight() for w, _ in ligne)
            for w, x in ligne:
                w.place(x=x, y=y + (hauteur - w.winfo_reqheight()) // 2)
            y += hauteur + self.ecart_lignes
        total = max(1, y - self.ecart_lignes)
        if int(self.cget("height")) != total:
            self.configure(height=total)


def defilement(tableau: ttk.Treeview) -> ttk.Scrollbar:
    """Barre de défilement verticale à droite d'un tableau déjà placé seul (pack) dans son cadre ; placée avant
    lui pour rester visible même si ses colonnes sont plus larges que le cadre."""
    barre = ttk.Scrollbar(tableau.master, orient="vertical", command=tableau.yview)
    tableau.configure(yscrollcommand=barre.set)
    barre.pack(side="right", fill="y", before=tableau)
    return barre


def cadre_tableau(parent) -> tk.Frame:
    """Cadre blanc à bordure fine qui accueille un tableau et sa barre de défilement."""
    return tk.Frame(parent, background=CARTE, highlightthickness=1, highlightbackground=BORDURE)


def entete_page(parent, icone: str, titre: str, sous_titre: str = "") -> tk.Frame:
    """Titre compact d'une page de travail : icône, titre vert, filet jaune et rouge, explication en gris."""
    fond = fond_de(parent)
    bloc = tk.Frame(parent, background=fond)
    ligne = tk.Frame(bloc, background=fond)
    ligne.pack(fill="x")
    tk.Label(ligne, text=icone, font=("Segoe UI Emoji", 15), background=fond).pack(side="left", padx=(0, 8))
    tk.Label(ligne, text=titre, font=("Segoe UI Semibold", 15), foreground=VERT_FONCE, background=fond).pack(side="left")
    if sous_titre:
        tk.Label(ligne, text="—  " + sous_titre, font=("Segoe UI", 9), foreground=TEXTE_DOUX, background=fond,
                 anchor="w").pack(side="left", padx=(10, 0), fill="x", expand=True)
    filet = tk.Frame(bloc, background=fond)
    filet.pack(anchor="w", pady=(3, 8))
    for couleur, largeur in ((JAUNE, 46), (ROUGE, 14)):
        tk.Frame(filet, width=largeur, height=3, background=couleur).pack(side="left", padx=(0, 4))
    return bloc



class FenetreOutil(tk.Frame):
    """Fenêtre de travail (liste, fiche, outil) affichée DANS la fenêtre principale de l'application, sous un
    bandeau avec son titre et « ✖ Fermer » / « ◀ Retour » (demande du propriétaire du 2026-10-29). Hors de
    l'application (outils, essais), elle s'ouvre dans une fenêtre à part. Les appels propres aux fenêtres de Windows
    (title, geometry, transient…) restent possibles : ils sont transmis à la fenêtre à part, ou ignorés."""

    def __init__(self, parent, a_part: bool = False, **options):
        """a_part : fenêtre à part même dans l'application (choix demandé depuis une fenêtre de création)."""
        self._racine = parent.nametowidget(".")
        self._seule = None
        self._titre = ""
        if hasattr(self._racine, "nouvel_outil") and not a_part:
            conteneur = self._racine.nouvel_outil(self)
        else:
            self._seule = conteneur = tk.Toplevel(parent)
        super().__init__(conteneur, **options)
        tk.Frame.pack(self, fill="both", expand=True)

    def title(self, texte=None):
        if texte is None:
            return self._titre
        self._titre = texte
        if self._seule is not None:
            self._seule.title(texte)
        elif hasattr(self._racine, "titre_outil"):
            self._racine.titre_outil(self, texte)
        return ""

    def _fenetre(self, nom, *arguments, **options):
        return getattr(self._seule, nom)(*arguments, **options) if self._seule is not None else ""

    def geometry(self, *a, **k):
        return self._fenetre("geometry", *a, **k)

    def minsize(self, *a, **k):
        return self._fenetre("minsize", *a, **k)

    def transient(self, *a, **k):
        return self._fenetre("transient", *a, **k)

    def resizable(self, *a, **k):
        return self._fenetre("resizable", *a, **k)

    def protocol(self, *a, **k):
        return self._fenetre("protocol", *a, **k)

    def attributes(self, *a, **k):
        return self._fenetre("attributes", *a, **k)

    def grab_set(self):
        return self._fenetre("grab_set")

    def destroy(self):
        seule, racine = self._seule, self._racine
        super().destroy()
        if seule is not None:
            if seule.winfo_exists():
                seule.destroy()
        elif hasattr(racine, "_outil_detruit"):
            racine._outil_detruit(self)


def dans_application(parent, fenetre, empiler: bool = True):
    """Compatibilité : une FenetreOutil s'affiche déjà d'elle-même dans la fenêtre principale."""
    return fenetre


def employes_visibles(widget, employes: list) -> list:
    """Employés que le login peut voir : tous (administrateur, gérant, hors application) ; sinon le sien seulement
    (règle du propriétaire du 2026-10-30), aucun si son compte n'est relié à aucun employé."""
    app = widget.nametowidget(".")
    if not hasattr(app, "limite_employe") or not app.limite_employe():
        return list(employes)
    moi = app.employe_connecte()
    return [e for e in employes if moi is not None and e.id == moi.id]


def login_limite(widget) -> bool:
    app = widget.nametowidget(".")
    return hasattr(app, "limite_employe") and app.limite_employe()


SEPARATEUR_CHOIX = " | "


def choix_multiples(texte: str) -> list[str]:
    """Valeurs d'un filtre ChoixMultiple (« A | B ») ; liste vide = tout."""
    return [v.strip() for v in str(texte or "").split(SEPARATEUR_CHOIX.strip()) if v.strip()]


class ChoixMultiple(tk.Frame):
    """Filtre à choix multiples (demande du propriétaire du 2026-11-01) : champ qui résume le choix (« Tout »,
    « Riz », « 3 choisis ») ; un clic ouvre la liste à cocher avec recherche, « Tout sélectionner » et « Tout
    désélectionner ». La liste se referme dès qu'on clique ailleurs (aucun filtre ne reste ouvert). `variable`
    reçoit les valeurs jointes par « | » (vide = tout) ; `au_choix` est appelé après « OK »."""

    def __init__(self, parent, variable: tk.StringVar, valeurs=(), largeur: int = 16, au_choix=None):
        super().__init__(parent, background=fond_de(parent))
        self.variable, self.valeurs, self.au_choix = variable, list(valeurs), au_choix
        self.affiche = tk.StringVar()
        self.champ = ttk.Entry(self, textvariable=self.affiche, width=largeur, state="readonly", cursor="hand2")
        self.champ.pack(side="left")
        fleche = tk.Label(self, text="▾", background=fond_de(parent), cursor="hand2")
        fleche.pack(side="left")
        for w in (self.champ, fleche):
            w.bind("<Button-1>", lambda _e: self.ouvrir())
        self.variable.trace_add("write", lambda *_: self._resumer())
        self.liste = None
        self.actif = True
        self._resumer()

    def configurer_valeurs(self, valeurs) -> None:
        self.valeurs = list(valeurs)

    def desactiver(self) -> None:
        self.actif = False
        self.champ.state(["disabled"])

    def _resumer(self) -> None:
        from .langues import t

        choisis = choix_multiples(self.variable.get())
        self.affiche.set(t("Tout") if not choisis else choisis[0] if len(choisis) == 1
                         else t("{n} choisis", n=len(choisis)))

    def ouvrir(self) -> None:
        from .langues import t

        if not self.actif or (self.liste is not None and self.liste.winfo_exists()):
            return
        choisis = set(choix_multiples(self.variable.get()))
        self.coches = {v: tk.BooleanVar(value=v in choisis) for v in self.valeurs}
        haut = tk.Toplevel(self)
        self.liste = haut
        haut.overrideredirect(True)
        haut.configure(background=BORDURE, padx=1, pady=1)
        x, y = self.champ.winfo_rootx(), self.champ.winfo_rooty() + self.champ.winfo_height() + 2
        haut.geometry(f"+{x}+{y}")
        cadre = tk.Frame(haut, background=CARTE, padx=8, pady=6)
        cadre.pack(fill="both", expand=True)
        recherche = tk.StringVar()
        champ = ttk.Entry(cadre, textvariable=recherche, width=32)
        champ.pack(fill="x")
        boutons = tk.Frame(cadre, background=CARTE)
        boutons.pack(fill="x", pady=4)
        toile = tk.Canvas(cadre, background=CARTE, highlightthickness=0, width=280, height=240)
        barre = ttk.Scrollbar(cadre, orient="vertical", command=toile.yview)
        toile.configure(yscrollcommand=barre.set)
        barre.pack(side="right", fill="y")
        toile.pack(side="left", fill="both", expand=True)
        zone = tk.Frame(toile, background=CARTE)
        toile.create_window((0, 0), window=zone, anchor="nw")
        zone.bind("<Configure>", lambda _e: toile.configure(scrollregion=toile.bbox("all")))
        toile.bind("<MouseWheel>", lambda e: toile.yview_scroll(-e.delta // 120, "units"))

        def montrer(*_):
            for enfant in zone.winfo_children():
                enfant.destroy()
            texte = recherche.get().strip().casefold()
            for v in self.valeurs:
                if not texte or texte in v.casefold():
                    case = ttk.Checkbutton(zone, text=v, variable=self.coches[v])
                    case.pack(anchor="w")
                    case.bind("<MouseWheel>", lambda e: toile.yview_scroll(-e.delta // 120, "units"))

        def tout(etat: bool) -> None:
            texte = recherche.get().strip().casefold()
            for v, var in self.coches.items():
                if not texte or texte in v.casefold():
                    var.set(etat)

        tk.Button(boutons, text=t("Tout sélectionner"), relief="flat", background="#e8f3ea",
                  command=lambda: tout(True)).pack(side="left")
        tk.Button(boutons, text=t("Tout désélectionner"), relief="flat", background="#f3e8e8",
                  command=lambda: tout(False)).pack(side="left", padx=4)
        recherche.trace_add("write", montrer)
        montrer()
        bas = tk.Frame(haut, background=CARTE, padx=8, pady=6)
        bas.pack(fill="x")

        def valider() -> None:
            choisis = [v for v in self.valeurs if self.coches[v].get()]
            # tout coché = aucun filtre
            self.variable.set("" if len(choisis) == len(self.valeurs) else SEPARATEUR_CHOIX.join(choisis))
            self.fermer()
            if self.au_choix:
                self.au_choix()

        tk.Button(bas, text="✔ OK", relief="flat", background="#1f7a3a", foreground="white",
                  command=valider).pack(side="right")
        tk.Button(bas, text=t("Annuler"), relief="flat", command=self.fermer).pack(side="right", padx=4)
        haut.bind("<Escape>", lambda _e: self.fermer())
        haut.bind("<Return>", lambda _e: valider())
        champ.focus_set()
        # clic ailleurs dans l'application : la liste se referme sans rien changer
        self._liaison = self.winfo_toplevel().bind("<Button-1>", lambda e: self._clic_ailleurs(e), add="+")

    def _clic_ailleurs(self, evenement) -> None:
        if self.liste is None or not self.liste.winfo_exists():
            return
        w = evenement.widget
        while w is not None:
            if w is self.liste or w is self:
                return
            w = getattr(w, "master", None)
        self.fermer()

    def fermer(self) -> None:
        if self.liste is not None and self.liste.winfo_exists():
            self.liste.destroy()
        self.liste = None


def montant_saisi(texte) -> "Decimal":
    """Montant tapé dans un champ : « 12,50 », « 12.50 $ », « 1 234,56 » (espaces normales ou insécables).
    ValueError « Montant invalide. » sinon (jamais le message technique de decimal)."""
    from decimal import Decimal, InvalidOperation

    propre = str(texte or "").replace("$", "").replace("\u00a0", "").replace("\u202f", "").replace(" ", "").strip()
    if propre.count(",") == 1 and "." not in propre:
        propre = propre.replace(",", ".")
    elif "," in propre and "." in propre:  # « 1,234.56 »
        propre = propre.replace(",", "")
    try:
        valeur = Decimal(propre)
    except InvalidOperation:
        raise ValueError("Montant invalide.") from None
    if not valeur.is_finite():
        raise ValueError("Montant invalide.")
    return valeur


def action_permise(widget, action: str) -> bool:
    """Action sensible d'une fenêtre (utilisateurs.ACTIONS_FENETRES) : permise au profil de la personne connectée ?
    Sinon un message l'explique. Hors de l'application (outils, essais) : toujours permise."""
    from tkinter import messagebox

    from .langues import t

    app = widget.nametowidget(".")
    if not hasattr(app, "permis_fenetre") or app.permis_fenetre(action):
        return True
    messagebox.showwarning(t("Accès refusé"), t("Votre profil ne permet pas : {a}.", a=t(action)), parent=widget)
    return False


def filtre_depots(parent, racine, au_choix=None, largeur: int = 18):
    """Filtre « Dépôt » des états (demande du propriétaire du 2026-11-05) : ChoixMultiple des dépôts, « Tout
    sélectionner » = tous. Renvoie (widget, variable) ; `depots_choisis(variable)` -> liste ou None (tous)."""
    import tomllib
    from pathlib import Path

    from .depots import noms

    try:
        valeurs = noms(tomllib.loads((Path(racine) / "config.toml").read_text(encoding="utf-8")))
    except (OSError, ValueError):
        valeurs = []
    variable = tk.StringVar()
    return ChoixMultiple(parent, variable, valeurs, largeur=largeur, au_choix=au_choix), variable


def depots_choisis(variable) -> list[str] | None:
    choisis = choix_multiples(variable.get())
    return choisis or None
