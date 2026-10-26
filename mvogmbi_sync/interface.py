"""Interface graphique d'installation et de suivi de MVOGMBI_Sync (tkinter, incluse avec Python).

Pages : Accueil (mise en route), Clover, Sage, Courriel, Automatisation, Correspondance des articles,
Tableau de bord, Guide de configuration, Aide / FAQ.
Langues : français et anglais (sélecteur dans le menu, enregistré dans config.toml [general] langue).
Les secrets (jeton Clover, mots de passe) vont dans le coffre-fort de Windows, jamais dans config.toml.
"""

from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
import tomllib
from datetime import date
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from . import coffre, langues
from .design import (BORDURE, CARTE, FOND, ICONE, ID_APPLICATION, JAUNE, LOGO, MENU_ACTIF, MENU_FOND, MENU_SURVOL, ROUGE, TEXTE,
                     TEXTE_DOUX, VERT, VERT_FONCE, Bouton, fond_de, image_filigrane)
from .langues import t

TITRE = "MVOGMBI_Sync — Clover → Sage 50"
MASQUE = "••••••••"  # affiché quand un secret est déjà enregistré dans le coffre

# Index des pages (ordre du menu)
ACCUEIL, CLOVER, SAGE, COURRIEL, AUTOMATISATION, CORRESPONDANCE, TABLEAU, GUIDE, FAQ = range(9)


# --------------------------------------------------------------------------------------------- configuration
def lire_config(chemin: Path) -> dict:
    return tomllib.loads(chemin.read_text(encoding="utf-8")) if chemin.exists() else {}


def _valeur_toml(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    texte = str(v)
    if "'" not in texte and "\n" not in texte:
        return f"'{texte}'"  # chaîne littérale : les « \\ » des chemins Windows restent tels quels
    return '"' + texte.replace("\\", "\\\\").replace('"', '\\"') + '"'


def ecrire_config(chemin: Path, config: dict) -> None:
    lignes = ["# Configuration de MVOGMBI_Sync (modifiée par l'application de configuration).",
              "# Les secrets sont dans le coffre-fort de Windows, pas dans ce fichier.", ""]
    for section, valeurs in config.items():
        lignes.append(f"[{section}]")
        for cle, valeur in valeurs.items():
            lignes.append(f"{cle} = {_valeur_toml(valeur)}")
        lignes.append("")
    chemin.write_text("\n".join(lignes), encoding="utf-8")


# --------------------------------------------------------------------------------------------- application
class Application(tk.Tk):
    def __init__(self, racine: Path):
        super().__init__()
        self.racine = racine
        self.relancer = False
        self.chemin_config = racine / "config.toml"
        self.config_toml = lire_config(self.chemin_config)
        langues.depuis_config(self.config_toml)
        self.file_messages: queue.Queue = queue.Queue()
        self.title(TITRE)
        largeur = min(1220, self.winfo_screenwidth() - 60)
        hauteur = min(860, self.winfo_screenheight() - 110)  # la fenêtre reste au-dessus de la barre des tâches
        self.geometry(f"{largeur}x{hauteur}+{max(0, (self.winfo_screenwidth() - largeur) // 2)}+20")
        self.minsize(920, 620)
        self.configure(background=FOND)
        try:  # thème moderne « Sun Valley » (style Windows 11)
            import sv_ttk
            sv_ttk.set_theme("light")
        except Exception:
            pass
        self._styles()
        self._images = self._charger_images()
        if ICONE.exists():  # icône .ico multi-tailles : nette dans la barre des tâches
            self.iconbitmap(default=str(ICONE))
        elif self._images:
            self.iconphoto(True, self._images["icone"])
        self._tache_installee = False

        self._bandeau()
        corps = tk.Frame(self, background=FOND)
        corps.pack(fill="both", expand=True)
        self.menu = tk.Frame(corps, background=MENU_FOND, width=240)
        self.menu.pack(side="left", fill="y")
        self.menu.pack_propagate(False)
        contenu = ttk.Frame(corps, padding=(20, 14, 20, 10))
        contenu.pack(side="left", fill="both", expand=True)

        bas = ttk.Frame(contenu, padding=(0, 10, 0, 0))
        bas.pack(side="bottom", fill="x")
        Bouton(bas, "💾  " + t("Enregistrer la configuration"), self.enregistrer).pack(side="right")
        self.etat = ttk.Label(bas, text="", foreground=TEXTE_DOUX)
        self.etat.pack(side="left")
        self.onglets = ttk.Notebook(contenu, style="Pages.TNotebook")
        self.onglets.pack(fill="both", expand=True)
        self.vars: dict[str, tk.Variable] = {}
        self._pages: list[tuple[str, str]] = []
        self._onglet_accueil()
        self._onglet_clover()
        self._onglet_sage()
        self._onglet_courriel()
        self._onglet_automatisation()
        self._onglet_correspondance()
        self._onglet_tableau()
        self._onglet_texte(t("Guide de configuration"), "guide", "📘")
        self._onglet_texte(t("Aide / FAQ"), "faq", "❓")
        self._construire_menu()

        self._attente = self.after(200, self._relayer_messages)
        self.actualiser_tableau()
        self.aller(ACCUEIL)

    # ---------------------------------------------------------------- apparence
    def _styles(self) -> None:
        style = ttk.Style(self)
        style.layout("Pages.TNotebook.Tab", [])  # onglets masqués : navigation par le menu latéral
        style.configure("Pages.TNotebook", borderwidth=0, padding=0)
        style.configure("Aide.TLabel", foreground=TEXTE_DOUX)
        style.configure("Carte.TFrame", background=CARTE)
        style.configure("Carte.TLabel", background=CARTE, foreground=TEXTE)
        style.configure("CarteAide.TLabel", background=CARTE, foreground=TEXTE_DOUX, font=("Segoe UI", 9))
        style.configure("Carte.TCheckbutton", background=CARTE)

    def _charger_images(self) -> dict:
        """Logo (en-tête), icône de la fenêtre et filigranes ; rien si l'image est introuvable."""
        try:
            from PIL import Image, ImageTk

            logo = Image.open(LOGO).convert("RGBA")
            entete = logo.copy()
            entete.thumbnail((84, 84), Image.LANCZOS)
            largeur, hauteur = logo.size
            icone = logo.crop((0, 0, largeur, int(hauteur * 0.76)))
            icone.thumbnail((64, 64), Image.LANCZOS)
            fond_page = fond_de(ttk.Frame(self))
            return {"entete": ImageTk.PhotoImage(entete), "icone": ImageTk.PhotoImage(icone),
                    "filigrane": image_filigrane(330, fond_page, 0.09),
                    "filigrane_texte": image_filigrane(250, CARTE, 0.11)}
        except Exception:
            return {}

    def _bandeau(self) -> None:
        bandeau = tk.Frame(self, background=VERT)
        bandeau.pack(fill="x")
        if self._images:
            carte = tk.Frame(bandeau, background="white", padx=6, pady=4)
            carte.pack(side="left", padx=(18, 16), pady=12)
            tk.Label(carte, image=self._images["entete"], background="white", borderwidth=0).pack()
        textes = tk.Frame(bandeau, background=VERT)
        textes.pack(side="left", fill="x", expand=True, pady=12)
        tk.Label(textes, text=t("Marché MVOG-MBI Sherbrooke"), font=("Segoe UI Semibold", 20), foreground="white",
                 background=VERT).pack(anchor="w")
        tk.Label(textes, text=t("Synchronisation des ventes Clover → Sage 50"), font=("Segoe UI", 12, "bold"),
                 foreground="#eaf7ee", background=VERT).pack(anchor="w")
        tk.Label(textes, text=t("Chaque nuit, les ventes Clover sont importées dans Sage 50 : une facture par jour."),
                 font=("Segoe UI", 10), foreground="#cdebd6", background=VERT).pack(anchor="w")
        lisere = tk.Frame(self, height=5, background=FOND)
        lisere.pack(fill="x")
        for couleur in (VERT_FONCE, ROUGE, JAUNE):
            tk.Frame(lisere, height=5, background=couleur).pack(side="left", fill="x", expand=True)

    def _construire_menu(self) -> None:
        tk.Label(self.menu, text="MENU", font=("Segoe UI", 8, "bold"), foreground="#7d8b81",
                 background=MENU_FOND).pack(anchor="w", padx=22, pady=(16, 6))
        self.boutons_menu, self.barres_menu, self.pastilles_menu = [], [], []
        for index, (icone, titre) in enumerate(self._pages):
            ligne = tk.Frame(self.menu, background=MENU_FOND)
            ligne.pack(fill="x", padx=(8, 10), pady=1)
            barre = tk.Frame(ligne, width=4, background=MENU_FOND)
            barre.pack(side="left", fill="y")
            bouton = tk.Label(ligne, text=f"{icone}   {titre}", anchor="w", font=("Segoe UI", 10),
                              background=MENU_FOND, foreground=TEXTE, padx=16, pady=9, cursor="hand2")
            bouton.pack(side="left", fill="x", expand=True)
            pastille = tk.Label(ligne, text="", font=("Segoe UI", 9), background=MENU_FOND, padx=6)
            pastille.place(relx=1.0, rely=0.5, anchor="e")
            for element in (bouton, pastille):
                element.bind("<Button-1>", lambda _e, i=index: self.aller(i))
                element.bind("<Enter>", lambda _e, i=index: self._survol_menu(i, True))
                element.bind("<Leave>", lambda _e, i=index: self._survol_menu(i, False))
            self.boutons_menu.append(bouton)
            self.barres_menu.append(barre)
            self.pastilles_menu.append(pastille)
        self._actif = None
        bas = tk.Frame(self.menu, background=MENU_FOND)
        bas.pack(side="bottom", fill="x", padx=16, pady=14)
        tk.Label(bas, text="🌐  Langue / Language", font=("Segoe UI", 9), foreground="#5a6b60",
                 background=MENU_FOND).pack(anchor="w")
        self.langue = tk.StringVar(value=langues.LANGUES[langues.courante()])
        selecteur = ttk.Combobox(bas, textvariable=self.langue, values=list(langues.LANGUES.values()),
                                 state="readonly", width=18)
        selecteur.pack(anchor="w", pady=(4, 10), fill="x")
        selecteur.bind("<<ComboboxSelected>>", lambda _e: self.changer_langue())
        from .aide import COPYRIGHT, VERSION
        for texte in (f"MVOGMBI_Sync {VERSION}", COPYRIGHT, t("Tous droits réservés.")):
            tk.Label(bas, text=texte, font=("Segoe UI", 8), foreground="#8a978e", background=MENU_FOND).pack(anchor="w")

    def _survol_menu(self, index: int, survol: bool) -> None:
        if self.boutons_menu[index] is self._actif:
            return
        couleur = MENU_SURVOL if survol else MENU_FOND
        self.boutons_menu[index].configure(background=couleur)
        self.pastilles_menu[index].configure(background=couleur)

    def aller(self, index: int) -> None:
        self.onglets.select(index)
        for i, bouton in enumerate(self.boutons_menu):
            actif = i == index
            fond = MENU_ACTIF if actif else MENU_FOND
            bouton.configure(background=fond, foreground=VERT_FONCE if actif else TEXTE,
                             font=("Segoe UI Semibold", 10) if actif else ("Segoe UI", 10))
            self.pastilles_menu[i].configure(background=fond)
            self.barres_menu[i].configure(background=JAUNE if actif else MENU_FOND)
        self._actif = self.boutons_menu[index]

    def changer_langue(self) -> None:
        code = next(c for c, nom in langues.LANGUES.items() if nom == self.langue.get())
        if code == langues.courante():
            return
        self.config_toml.setdefault("general", {})["langue"] = code
        ecrire_config(self.chemin_config, self.config_toml)
        self.relancer = True  # la fenêtre est reconstruite dans la nouvelle langue
        self.destroy()

    # ---------------------------------------------------------------- outils d'interface
    def _var(self, cle: str, valeur, type_=tk.StringVar) -> tk.Variable:
        self.vars[cle] = type_(value=valeur)
        return self.vars[cle]

    def _champ(self, parent, ligne: int, libelle: str, cle: str, valeur="", secret: str | None = None,
               aide: str = "", parcourir: tuple | None = None):
        sur_carte = fond_de(parent) == CARTE
        ttk.Label(parent, text=libelle, style="Carte.TLabel" if sur_carte else "TLabel").grid(
            row=ligne, column=0, sticky="w", pady=4, padx=(0, 14))
        if secret:
            valeur = MASQUE if coffre.present(secret) else ""
        champ = ttk.Entry(parent, textvariable=self._var(cle, valeur), width=52, show="•" if secret else "")
        champ.grid(row=ligne, column=1, sticky="we", pady=4)
        if secret:
            # Le masque « •••••••• » n'est pas le mot de passe : il s'efface dès qu'on entre dans le champ,
            # sinon ce qu'on tape s'ajoute à lui ; il revient si le champ est laissé vide.
            variable = self.vars[cle]

            def entree(_evt, variable=variable):
                if variable.get() == MASQUE:
                    variable.set("")

            def sortie(_evt, variable=variable, secret=secret):
                if not variable.get() and coffre.present(secret):
                    variable.set(MASQUE)

            champ.bind("<FocusIn>", entree, add="+")
            champ.bind("<FocusOut>", sortie, add="+")
        if parcourir:
            Bouton(parent, t("Parcourir…"), lambda: self._parcourir(cle, *parcourir), "secondaire", petit=True).grid(
                row=ligne, column=2, padx=(8, 0))
        if aide:
            tk.Label(parent, text=aide, font=("Segoe UI", 9), foreground=TEXTE_DOUX, background=fond_de(parent),
                     wraplength=620, justify="left").grid(row=ligne + 1, column=1, sticky="w", pady=(0, 6))
        parent.columnconfigure(1, weight=1)
        return champ

    def _parcourir(self, cle: str, titre: str, types: list) -> None:
        chemin = filedialog.askopenfilename(title=titre, filetypes=types)
        if chemin:
            self.vars[cle].set(str(Path(chemin)))

    def _cadre(self, titre: str, icone: str = "•", filigrane: bool = True) -> ttk.Frame:
        """Page défilante (barre de défilement et molette seulement si le contenu dépasse la fenêtre),
        avec le logo pâli en bas à droite ; renvoie le cadre où placer le contenu."""
        exterieur = ttk.Frame(self.onglets)
        self.onglets.add(exterieur, text=titre)
        self._pages.append((icone, titre))
        toile = tk.Canvas(exterieur, background=fond_de(exterieur), highlightthickness=0, borderwidth=0)
        barre = ttk.Scrollbar(exterieur, orient="vertical", command=toile.yview)
        toile.configure(yscrollcommand=barre.set)
        toile.pack(side="left", fill="both", expand=True)
        logo = toile.create_image(0, 0, image=self._images["filigrane"], anchor="se") \
            if filigrane and self._images else None
        cadre = ttk.Frame(toile, padding=(4, 4))
        fenetre = toile.create_window(0, 0, window=cadre, anchor="nw")
        cadre.columnconfigure(0, weight=1)

        def ajuster(_evt=None):
            largeur, visible, contenu = toile.winfo_width(), toile.winfo_height(), cadre.winfo_reqheight()
            toile.itemconfigure(fenetre, width=largeur)
            toile.configure(scrollregion=(0, 0, largeur, max(contenu, visible)))
            if logo:
                toile.coords(logo, largeur - 16, max(contenu, visible) - 16)
            if contenu > visible and not barre.winfo_ismapped():
                barre.pack(side="right", fill="y", before=toile)
            elif contenu <= visible and barre.winfo_ismapped():
                barre.pack_forget()
                toile.yview_moveto(0)

        def molette(evt):
            if cadre.winfo_reqheight() > toile.winfo_height():
                toile.yview_scroll(-evt.delta // 120, "units")

        toile.bind("<Configure>", ajuster)
        cadre.bind("<Configure>", ajuster)
        exterieur.bind("<Enter>", lambda _e: self.bind_all("<MouseWheel>", molette))
        exterieur.bind("<Leave>", lambda _e: self.unbind_all("<MouseWheel>"))
        return cadre

    def _titre(self, parent, texte: str, sous_titre: str = "") -> tk.Frame:
        fond = fond_de(parent)
        bloc = tk.Frame(parent, background=fond)
        tk.Label(bloc, text=texte, font=("Segoe UI Semibold", 17), foreground=VERT_FONCE, background=fond).pack(anchor="w")
        souligne = tk.Frame(bloc, background=fond)
        souligne.pack(anchor="w", pady=(4, 0))
        for couleur, largeur in ((JAUNE, 46), (ROUGE, 14)):
            tk.Frame(souligne, width=largeur, height=4, background=couleur).pack(side="left", padx=(0, 4))
        if sous_titre:
            tk.Label(bloc, text=sous_titre, font=("Segoe UI", 10), foreground=TEXTE_DOUX, background=fond,
                     wraplength=760, justify="left").pack(anchor="w", pady=(8, 0))
        bloc.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 14))
        return bloc

    def _carte(self, parent, ligne: int, titre: str, numero: str = "", description: str = "",
               couleur: str = VERT) -> ttk.Frame:
        """Carte blanche à bordure fine, avec pastille numérotée et titre ; renvoie la zone des champs."""
        cadre = tk.Frame(parent, background=CARTE, highlightthickness=1, highlightbackground=BORDURE)
        cadre.grid(row=ligne, column=0, columnspan=3, sticky="we", pady=(0, 12))
        tk.Frame(cadre, width=4, background=couleur).pack(side="left", fill="y")
        interieur = tk.Frame(cadre, background=CARTE)
        interieur.pack(side="left", fill="both", expand=True)
        entete = tk.Frame(interieur, background=CARTE)
        entete.pack(fill="x", padx=16, pady=(12, 2))
        if numero:
            tk.Label(entete, text=numero, font=("Segoe UI Semibold", 9), foreground="white", background=couleur,
                     width=3, pady=1).pack(side="left", padx=(0, 10))
        tk.Label(entete, text=titre, font=("Segoe UI Semibold", 12), foreground=TEXTE, background=CARTE).pack(side="left")
        if description:
            tk.Label(interieur, text=description, font=("Segoe UI", 9), foreground=TEXTE_DOUX, background=CARTE,
                     wraplength=760, justify="left").pack(anchor="w", padx=16)
        zone = ttk.Frame(interieur, style="Carte.TFrame", padding=(16, 8, 16, 14))
        zone.pack(fill="x")
        zone.columnconfigure(1, weight=1)
        return zone

    def _sortie(self, parent, hauteur=6) -> tk.Text:
        zone = tk.Text(parent, height=hauteur, wrap="word", font=("Cascadia Mono", 9), relief="flat",
                       background="#f6f8f7", foreground="#24332a", borderwidth=0, padx=10, pady=8,
                       highlightthickness=1, highlightbackground="#dfe6e1", highlightcolor=VERT)
        zone.tag_configure("ok", foreground=VERT_FONCE)
        zone.tag_configure("erreur", foreground=ROUGE)
        zone.tag_configure("attention", foreground="#9a6a00")
        zone.tag_configure("date", foreground="#8a978e")
        return zone

    @staticmethod
    def _ecrire(zone: tk.Text, texte: str) -> None:
        """Ajoute une ligne colorée selon son contenu (succès, problème, information)."""
        bas = texte.lower()
        if texte.startswith("✘") or any(m in texte for m in ("PROBLÈME", "ERREUR", "PROBLEM", "ERROR")) \
                or "bloqu" in bas or "blocked" in bas or "refus" in bas:
            etiquette = "erreur"
        elif texte.startswith("✔") or "importée" in bas or "imported" in bas or "réussi" in bas:
            etiquette = "ok"
        elif "(info)" in bas or "à confirmer" in bas or "to confirm" in bas or "attention" in bas:
            etiquette = "attention"
        else:
            etiquette = ""
        if len(texte) > 9 and texte[2] == ":" and texte[5] == ":" and texte[8] == " ":  # « 19:38:46 … »
            zone.insert("end", texte[:9], "date")
            zone.insert("end", texte[9:] + "\n", etiquette)
        else:
            zone.insert("end", texte + "\n", etiquette)

    def _tache(self, titre: str, fonction, zone: tk.Text | None = None) -> None:
        """Exécute une action longue en arrière-plan ; ses messages s'affichent dans `zone`."""
        self.etat.config(text=f"{titre}…")

        def travail():
            try:
                resultat = fonction()
                self.file_messages.put((zone, f"✔ {titre} : {resultat or t('terminé')}"))
            except Exception as exc:
                self.file_messages.put((zone, f"✘ {titre} : {exc}"))
            self.file_messages.put((None, ""))

        threading.Thread(target=travail, daemon=True).start()

    def _relayer_messages(self) -> None:
        try:
            while True:
                zone, texte = self.file_messages.get_nowait()
                if zone is None:
                    self.etat.config(text=texte)
                    self.actualiser_tableau()
                else:
                    self._ecrire(zone, texte)
                    zone.see("end")
        except queue.Empty:
            pass
        self._attente = self.after(200, self._relayer_messages)

    def destroy(self) -> None:
        try:
            self.after_cancel(self._attente)
        except Exception:
            pass
        super().destroy()

    # ---------------------------------------------------------------- pages de texte
    def _zone_document(self, parent, blocs) -> tk.Text:
        """Texte mis en forme (titres, étapes, notes) ; le logo pâli occupe la marge de droite."""
        marge = 290 if self._images else 26
        zone = tk.Text(parent, wrap="word", relief="flat", background=CARTE, borderwidth=0, highlightthickness=1,
                       highlightbackground=BORDURE, padx=28, pady=20, font=("Segoe UI", 10), cursor="arrow",
                       spacing1=2, spacing3=2)
        zone.tag_configure("marge", rmargin=marge)
        zone.tag_configure("titre", font=("Segoe UI Semibold", 20), foreground=VERT, spacing3=12)
        zone.tag_configure("sous_titre", font=("Segoe UI Semibold", 13), foreground=VERT_FONCE, spacing1=18,
                           spacing3=6)
        zone.tag_configure("para", spacing3=6)
        zone.tag_configure("etape", lmargin1=14, lmargin2=32, spacing3=5)
        zone.tag_configure("puce", lmargin1=14, lmargin2=30, spacing3=3)
        zone.tag_configure("note", lmargin1=14, lmargin2=34, foreground="#8a5a00", spacing1=8, spacing3=10,
                           font=("Segoe UI Semibold", 10))
        zone.tag_configure("question", font=("Segoe UI Semibold", 11), foreground=VERT_FONCE, spacing1=14)
        zone.tag_configure("reponse", lmargin1=14, lmargin2=14, spacing3=4)
        for type_bloc, texte in blocs:
            prefixe = {"puce": "•  ", "question": "Q.  ", "note": "💡  "}.get(type_bloc, "")
            zone.insert("end", prefixe + texte + "\n", (type_bloc, "marge"))
        zone.configure(state="disabled")
        if self._images:
            logo = tk.Label(zone, image=self._images["filigrane_texte"], background=CARTE, borderwidth=0,
                            cursor="arrow")
            logo.place(relx=1.0, rely=0.0, x=-24, y=24, anchor="ne")
        return zone

    def _onglet_texte(self, titre_onglet: str, page: str, icone: str) -> None:
        from .aide import FAQ as TEXTE_FAQ
        from .aide import GUIDE as TEXTE_GUIDE

        blocs = (TEXTE_GUIDE if page == "guide" else TEXTE_FAQ)[langues.courante()]
        cadre = ttk.Frame(self.onglets, padding=(4, 4))
        self.onglets.add(cadre, text=titre_onglet)
        self._pages.append((icone, titre_onglet))
        zone = self._zone_document(cadre, blocs)
        defilement = ttk.Scrollbar(cadre, orient="vertical", command=zone.yview)
        zone.configure(yscrollcommand=defilement.set)
        defilement.pack(side="right", fill="y")
        zone.pack(side="left", fill="both", expand=True)

    # ---------------------------------------------------------------- Accueil : mise en route
    ETAPES = (
        (CLOVER, "1", "Clover", "Identifiant marchand et jeton API"),
        (SAGE, "2", "Sage 50", "Fichier d'entreprise et mots de passe"),
        (COURRIEL, "3", "Courriel", "Compte rendu après chaque nuit"),
        (AUTOMATISATION, "4", "Automatisation", "Tâche planifiée installée"),
        (CORRESPONDANCE, "5", "Correspondance", "Articles Clover reliés à Sage"),
        (TABLEAU, "6", "Premier import", "Une facture importée dans Sage"),
    )

    def _onglet_accueil(self) -> None:
        from .aide import ACCUEIL as TEXTE_ACCUEIL

        cadre = ttk.Frame(self.onglets, padding=(4, 4))
        self.onglets.add(cadre, text=t("Accueil"))
        self._pages.append(("🏠", t("Accueil")))
        cadre.columnconfigure(0, weight=1)
        cadre.rowconfigure(1, weight=1)
        carte = self._carte(cadre, 0, t("Mise en route"), "✓",
                            t("Six étapes pour une synchronisation entièrement automatique. Chaque étape passe au "
                              "vert quand elle est faite."))
        self.lignes_etapes = {}
        for n, (page, numero, titre, description) in enumerate(self.ETAPES):
            case = tk.Frame(carte, background=CARTE)
            case.grid(row=n // 3, column=n % 3, sticky="we", padx=(0, 18), pady=6)
            carte.columnconfigure(n % 3, weight=1)
            etat = tk.Label(case, text="●", font=("Segoe UI", 14), foreground=JAUNE, background=CARTE)
            etat.grid(row=0, column=0, rowspan=2, padx=(0, 8))
            tk.Label(case, text=f"{numero}. {t(titre)}", font=("Segoe UI Semibold", 10), foreground=TEXTE,
                     background=CARTE).grid(row=0, column=1, sticky="w")
            detail = tk.Label(case, text=t(description), font=("Segoe UI", 9), foreground=TEXTE_DOUX,
                              background=CARTE)
            detail.grid(row=1, column=1, sticky="w")
            Bouton(case, t("Ouvrir"), lambda p=page: self.aller(p), "secondaire", fond=CARTE, petit=True).grid(
                row=0, column=2, rowspan=2, padx=(10, 0))
            case.columnconfigure(1, weight=1)
            self.lignes_etapes[page] = (etat, detail, t(description))
        zone = self._zone_document(cadre, TEXTE_ACCUEIL[langues.courante()])
        zone.grid(row=1, column=0, sticky="nsew")
        defilement = ttk.Scrollbar(cadre, orient="vertical", command=zone.yview)
        zone.configure(yscrollcommand=defilement.set)
        defilement.grid(row=1, column=1, sticky="ns")

    def _etat_etapes(self) -> dict[int, tuple[bool, str]]:
        """Pour chaque étape de mise en route : (faite, précision)."""
        c = self.config_toml
        etats = {
            CLOVER: (bool(c.get("clover", {}).get("merchant_id")) and coffre.present(coffre.CLOVER_JETON), ""),
            COURRIEL: (bool(c.get("courriel", {}).get("serveur") and c["courriel"].get("destinataires"))
                       and coffre.present(coffre.COURRIEL), ""),
            AUTOMATISATION: (self._tache_installee, ""),
        }
        fichier = c.get("sage_import", {}).get("fichier_entreprise", "")
        sage_ok = bool(fichier) and Path(fichier).is_file() and coffre.present(coffre.SAGE_LECTURE) \
            and coffre.present(coffre.SAGE_IMPORT)
        etats[SAGE] = (sage_ok, Path(fichier).name if sage_ok else "")
        correspondance = self.racine / "donnees" / "correspondance_articles.xlsx"
        etats[CORRESPONDANCE] = (correspondance.exists(), "")
        journal = self.racine / "donnees" / "journal_imports.csv"
        derniere = ""
        if journal.exists():
            lignes = [l for l in journal.read_text(encoding="utf-8-sig").splitlines()[1:] if ";importée" in l]
            if lignes:
                derniere = lignes[-1].split(";")[1]
        etats[TABLEAU] = (bool(derniere), derniere)
        return etats

    def _maj_etapes(self) -> None:
        etats = self._etat_etapes()
        for page, (faite, precision) in etats.items():
            etat, detail, description = self.lignes_etapes[page]
            etat.configure(text="✔" if faite else "●", foreground=VERT if faite else JAUNE)
            detail.configure(text=precision or description)
            if page in (CLOVER, SAGE, COURRIEL, AUTOMATISATION) and hasattr(self, "pastilles_menu"):
                self.pastilles_menu[page].configure(text="✔" if faite else "●", foreground=VERT if faite else JAUNE)
        return None

    # ---------------------------------------------------------------- pages de configuration
    def _onglet_clover(self) -> None:
        c = self.config_toml.get("clover", {})
        f = self._cadre(t("1. Clover"), "🛒")
        self._titre(f, t("Accès à votre compte Clover (lecture des ventes)"),
                    t("L'application lit les ventes payées dans Clover ; elle n'y modifie jamais rien."))
        carte = self._carte(f, 1, t("Identifiants Clover"), "1")
        self._champ(carte, 0, t("Identifiant marchand"), "clover.merchant_id", c.get("merchant_id", ""),
                    aide=t("13 caractères, visibles dans l'adresse du tableau de bord Clover après « /m/ »."))
        self._champ(carte, 2, t("Jeton API"), "secret.clover", secret=coffre.CLOVER_JETON,
                    aide=t("Clover > Compte et configuration > Jetons API (droits en lecture). "
                           "Laissez « •••• » pour conserver le jeton enregistré."))
        Bouton(carte, "🔌  " + t("Tester la connexion à Clover"), self.tester_clover).grid(
            row=4, column=1, sticky="w", pady=(6, 8))
        self.sortie_clover = self._sortie(carte, 4)
        self.sortie_clover.grid(row=5, column=0, columnspan=3, sticky="we")

    def _onglet_sage(self) -> None:
        b, i, a = (self.config_toml.get(s, {}) for s in ("sage_base", "sage_import", "automatique"))
        f = self._cadre(t("2. Sage 50"), "📒")
        self._titre(f, t("Fichier d'entreprise et comptes Sage"))
        types = [(t("Fichier d'entreprise Sage"), "*.SAI"), (t("Tous les fichiers"), "*.*")]
        fichier = self._carte(f, 1, t("Fichier d'entreprise"), "1")
        self._champ(fichier, 0, t("Fichier d'entreprise (.SAI)"), "sage.fichier", i.get("fichier_entreprise", ""),
                    aide=t("Le fichier dans lequel les factures sont importées. Pour les essais : une COPIE."),
                    parcourir=(t("Fichier d'entreprise Sage"), types))
        self._champ(fichier, 2, t("Premier jour à importer"), "auto.date_depart",
                    a.get("date_depart", date.today().isoformat()),
                    aide=t("AAAA-MM-JJ. Utilisé seulement si Sage ne contient encore aucune facture « Vente AAAA-MM-JJ »."))
        comptes = self._carte(f, 2, t("Utilisateurs Sage"), "2")
        self._champ(comptes, 0, t("Utilisateur Sage (lecture)"), "sage.utilisateur", b.get("utilisateur", "mvogmbi_sync"),
                    aide=t("Utilisateur avec « Droits d'accès aux produits tiers : Consultation seule » "
                           "et accès Vue aux modules Stocks & Services et Clients & Ventes."))
        self._champ(comptes, 2, t("Mot de passe (lecture)"), "secret.sage_lecture", secret=coffre.SAGE_LECTURE)
        self._champ(comptes, 3, t("Mot de passe Sage pour l'import"), "secret.sage_import", secret=coffre.SAGE_IMPORT,
                    aide=t("Mot de passe demandé par la fenêtre « Sage 50 - Password » de l'import (utilisateur sysadmin)."))
        Bouton(comptes, "📒  " + t("Tester l'accès à Sage"), self.tester_sage).grid(row=5, column=1, sticky="w",
                                                                                    pady=(6, 8))
        self.sortie_sage = self._sortie(comptes, 4)
        self.sortie_sage.grid(row=6, column=0, columnspan=3, sticky="we")

    def _onglet_courriel(self) -> None:
        c = self.config_toml.get("courriel", {})
        f = self._cadre(t("3. Courriel"), "📧")
        self._titre(f, t("Alertes par courriel"))
        serveur = self._carte(f, 1, t("Serveur d'envoi"), "1")
        self._champ(serveur, 0, t("Serveur d'envoi (SMTP)"), "courriel.serveur", c.get("serveur", ""),
                    aide=t("Ex. smtp.office365.com (Outlook) ou smtp.gmail.com (Gmail : mot de passe d'application)."))
        self._champ(serveur, 2, t("Port"), "courriel.port", str(c.get("port", 587)))
        ttk.Label(serveur, text=t("Sécurité"), style="Carte.TLabel").grid(row=3, column=0, sticky="w", pady=4)
        ttk.Combobox(serveur, textvariable=self._var("courriel.securite", c.get("securite", "starttls")),
                     values=["starttls", "ssl", "aucune"], state="readonly", width=12).grid(row=3, column=1, sticky="w")
        self._champ(serveur, 4, t("Utilisateur"), "courriel.utilisateur", c.get("utilisateur", ""))
        self._champ(serveur, 5, t("Mot de passe"), "secret.courriel", secret=coffre.COURRIEL)
        envoi = self._carte(f, 2, t("Envoi du compte rendu"), "2")
        self._champ(envoi, 0, t("Expéditeur"), "courriel.expediteur", c.get("expediteur", ""))
        self._champ(envoi, 1, t("Destinataire(s)"), "courriel.destinataires", c.get("destinataires", ""),
                    aide=t("Une ou plusieurs adresses séparées par des virgules."))
        self._champ(envoi, 4, t("Copie (CC)"), "courriel.copie", c.get("copie", ""),
                    aide=t("Facultatif : autres personnes à informer, adresses séparées par des virgules "
                           "(ex. comptable@exemple.com, gerant@exemple.com)."))
        ttk.Checkbutton(envoi, text=t("Envoyer le compte rendu après chaque traitement, y compris en cas de succès "
                                      "(dates traitées et leur état)"), style="Carte.TCheckbutton",
                        variable=self._var("courriel.envoyer_si_succes", bool(c.get("envoyer_si_succes", True)),
                                           tk.BooleanVar)).grid(row=6, column=1, sticky="w", pady=6)
        Bouton(envoi, "✉  " + t("Envoyer un courriel de test"), self.tester_courriel).grid(
            row=7, column=1, sticky="w", pady=(6, 8))
        self.sortie_courriel = self._sortie(envoi, 3)
        self.sortie_courriel.grid(row=8, column=0, columnspan=3, sticky="we")

    def _onglet_automatisation(self) -> None:
        a = self.config_toml.get("automatique", {})
        f = self._cadre(t("4. Automatisation"), "⏰")
        self._titre(f, t("Traitement automatique quotidien"))
        tache = self._carte(f, 1, t("Tâche planifiée"), "1")
        self._champ(tache, 0, t("Heure du traitement"), "auto.heure", a.get("heure", "01:00"),
                    aide=t("HH:MM. L'ordinateur doit être allumé et la session Windows ouverte ; Sage peut être fermé."))
        boutons = tk.Frame(tache, background=CARTE)
        boutons.grid(row=2, column=1, sticky="w", pady=(6, 8))
        Bouton(boutons, "⏰  " + t("Installer la tâche planifiée"), self.installer_tache).pack(side="left")
        Bouton(boutons, t("Retirer la tâche"), self.retirer_tache, "danger").pack(side="left", padx=8)
        Bouton(boutons, t("État de la tâche"), self.etat_tache, "secondaire").pack(side="left")
        self.sortie_auto = self._sortie(tache, 6)
        self.sortie_auto.grid(row=3, column=0, columnspan=3, sticky="we")
        outils = self._carte(f, 2, t("Outils"), "2", couleur=JAUNE)
        ligne = tk.Frame(outils, background=CARTE)
        ligne.grid(row=0, column=0, columnspan=3, sticky="w")
        Bouton(ligne, t("Créer un raccourci sur le Bureau"), self.raccourci, "secondaire").pack(side="left")
        Bouton(ligne, t("Reprendre une configuration existante…"), self.reprendre, "secondaire").pack(side="left",
                                                                                                    padx=8)
        tk.Label(outils, text=t("Copie config.toml, la correspondance des articles et les articles à relier depuis un "
                                "autre dossier (ex. le dossier du projet). Les mots de passe restent dans le coffre-fort."),
                 font=("Segoe UI", 9), foreground=TEXTE_DOUX, background=CARTE, wraplength=640,
                 justify="left").grid(row=1, column=0, columnspan=3, sticky="w", pady=(6, 0))

    def _onglet_correspondance(self) -> None:
        from .page_correspondance import PageCorrespondance

        self.page_correspondance = PageCorrespondance(self.onglets, self.racine, TITRE)
        self.onglets.add(self.page_correspondance, text=t("5. Correspondance des articles"))
        self._pages.append(("🔗", t("5. Correspondance")))

    def _onglet_tableau(self) -> None:
        f = self._cadre(t("6. Tableau de bord"), "📊")
        self._titre(f, t("6. Tableau de bord")[3:])
        self.cartes = tk.Frame(f, background=fond_de(f))
        self.cartes.grid(row=1, column=0, columnspan=3, sticky="we", pady=(0, 14))
        haut = ttk.Frame(f)
        haut.grid(row=2, column=0, columnspan=3, sticky="we")
        Bouton(haut, "▶  " + t("Lancer maintenant"), lambda: self.lancer(False)).pack(side="left")
        Bouton(haut, "🧪  " + t("Simulation (sans import)"), lambda: self.lancer(True), "accent").pack(side="left", padx=8)
        Bouton(haut, "📗  Excel", lambda: self.ouvrir(self.racine / "donnees" / "correspondance_articles.xlsx"),
               "secondaire").pack(side="left")
        Bouton(haut, "📁  " + t("Dossier des données"), lambda: self.ouvrir(self.racine / "donnees"),
               "secondaire").pack(side="left", padx=8)
        Bouton(haut, "⟳", self.actualiser_tableau, "secondaire", largeur=40).pack(side="right")
        self.sortie_tableau = self._sortie(f, 18)
        self.sortie_tableau.grid(row=3, column=0, columnspan=3, sticky="we", pady=(14, 0))

    # ---------------------------------------------------------------- actions
    def enregistrer(self) -> bool:
        v = {k: var.get() for k, var in self.vars.items()}
        heure = str(v["auto.heure"]).strip()
        try:
            date.fromisoformat(str(v["auto.date_depart"]).strip())
            h, m = heure.split(":")
            assert 0 <= int(h) < 24 and 0 <= int(m) < 60
            int(str(v["courriel.port"]).strip() or 587)
        except (ValueError, AssertionError):
            messagebox.showerror(TITRE, t("Vérifiez la date (AAAA-MM-JJ), l'heure (HH:MM) et le port du courriel."))
            return False
        from .courriel import adresses, adresses_invalides

        invalides = adresses_invalides(v["courriel.destinataires"]) + adresses_invalides(v["courriel.copie"])
        if invalides:
            messagebox.showerror(TITRE, t("Adresse(s) courriel invalide(s) : {liste}", liste=", ".join(invalides)))
            return False
        c = self.config_toml
        c.setdefault("clover", {}).update(merchant_id=str(v["clover.merchant_id"]).strip())
        c["clover"].setdefault("base_url", "https://api.clover.com")
        c["clover"].pop("api_token", None)
        c.setdefault("general", {}).setdefault("fuseau_horaire", "America/Toronto")
        c["general"]["langue"] = langues.courante()
        fichier = str(v["sage.fichier"]).strip()
        c.setdefault("sage_base", {}).update(utilisateur=str(v["sage.utilisateur"]).strip(), fichier_entreprise=fichier)
        c["sage_base"].pop("mot_de_passe", None)
        c["sage_base"].setdefault("port", 13540)
        c.setdefault("sage_import", {}).update(fichier_entreprise=fichier)
        for cle, defaut in (("version", "12001"), ("pays", "1"), ("position_numero", 3)):
            c["sage_import"].setdefault(cle, defaut)
        c.setdefault("automatique", {}).update(date_depart=str(v["auto.date_depart"]).strip(), heure=heure)
        c["automatique"].setdefault("delai_import", 3600)
        c.setdefault("courriel", {}).update(
            serveur=str(v["courriel.serveur"]).strip(), port=int(str(v["courriel.port"]).strip() or 587),
            securite=v["courriel.securite"], utilisateur=str(v["courriel.utilisateur"]).strip(),
            expediteur=str(v["courriel.expediteur"]).strip(),
            destinataires=", ".join(adresses(v["courriel.destinataires"])), copie=", ".join(adresses(v["courriel.copie"])),
            envoyer_si_succes=bool(v["courriel.envoyer_si_succes"]))
        for cle_var, cle_coffre in (("secret.clover", coffre.CLOVER_JETON), ("secret.sage_lecture", coffre.SAGE_LECTURE),
                                    ("secret.sage_import", coffre.SAGE_IMPORT), ("secret.courriel", coffre.COURRIEL)):
            valeur = str(v[cle_var])
            if valeur.startswith(MASQUE):  # tapé à la suite du masque : seul l'ajout est le mot de passe
                valeur = valeur[len(MASQUE):]
            if valeur:
                coffre.ecrire(cle_coffre, valeur)
                self.vars[cle_var].set(MASQUE)
        ecrire_config(self.chemin_config, c)
        self.etat.config(text=t("Configuration enregistrée."))
        self._maj_etapes()
        return True

    def tester_clover(self) -> None:
        if not self.enregistrer():
            return

        def test():
            from .__main__ import charger_config
            from .api_clover import ClientClover

            client = ClientClover(charger_config(self.chemin_config))
            return t("connecté à « {nom} »", nom=client.marchand().get("name", "?"))

        self._tache(t("Test Clover"), test, self.sortie_clover)

    def tester_sage(self) -> None:
        if not self.enregistrer():
            return

        def test():
            from .__main__ import executable_import, ouvrir_base_sage
            from .automatique import lire_etat_sage
            from .facture import CLIENT
            from .sage_auto import lire_pendant_connexion

            config = lire_config(self.chemin_config)
            fichier = Path(config["sage_import"]["fichier_entreprise"])
            if not fichier.is_file():
                raise RuntimeError(t("fichier introuvable : {fichier}", fichier=fichier))

            def lecture():
                with ouvrir_base_sage(config, fichier) as base:
                    return lire_etat_sage(base, CLIENT)

            try:
                etat = lecture()
                mode = t("Sage ouvert")
            except PermissionError:
                raise
            except Exception:
                exe = executable_import()
                if not exe:
                    raise RuntimeError("Sage_SA_import.exe ?")
                etat = lire_pendant_connexion(exe, fichier, lecture)
                mode = t("Sage fermé : base ouverte puis refermée automatiquement")
            client = "OK" if etat.client_configure else t(
                "À RÉGLER : cocher « Ce client utilise mes n° articles » dans la fiche du client")
            sans_compte = sum(1 for a in etat.articles if not a.compte_revenus and a.type == "Inventory")
            return t("{mode}. {n} articles. Dernière facture journalière : {derniere}. Client « {client} » : {etat}. "
                     "Articles sans compte de produits : {sans}.", mode=mode, n=len(etat.articles),
                     derniere=etat.derniere_date or t("aucune"), client=CLIENT, etat=client, sans=sans_compte)

        self._tache(t("Test Sage"), test, self.sortie_sage)

    def tester_courriel(self) -> None:
        if not self.enregistrer():
            return

        def test():
            from .courriel import envoyer

            envoyer(lire_config(self.chemin_config), t("MVOGMBI_Sync : courriel de test"),
                    t("Ce courriel confirme que les alertes de MVOGMBI_Sync sont bien configurées."))
            return t("courriel envoyé")

        self._tache(t("Courriel de test"), test, self.sortie_courriel)

    def installer_tache(self) -> None:
        if not self.enregistrer():
            return
        from . import planification

        heure = str(self.vars["auto.heure"].get()).strip()
        self._tache(t("Installation de la tâche"), lambda: planification.installer(self.racine, heure), self.sortie_auto)

    def retirer_tache(self) -> None:
        from . import planification

        if messagebox.askyesno(TITRE, t("Retirer la tâche planifiée ? Les ventes ne seront plus importées automatiquement.")):
            self._tache(t("Retrait de la tâche"), planification.retirer, self.sortie_auto)

    def etat_tache(self) -> None:
        from . import planification

        self._tache(t("État de la tâche"), planification.etat, self.sortie_auto)

    def raccourci(self) -> None:
        bureau = Path(os.environ.get("USERPROFILE", "~")).expanduser() / "Desktop"
        cible = (str(Path(sys.executable).resolve()) if getattr(sys, "frozen", False)
                 else str(Path(sys.executable).with_name("pythonw.exe")))
        arguments = "" if getattr(sys, "frozen", False) else "-m mvogmbi_sync interface"
        script = (f'$s=(New-Object -ComObject WScript.Shell).CreateShortcut("{bureau / "MVOGMBI_Sync.lnk"}");'
                  f'$s.TargetPath="{cible}";$s.Arguments="{arguments}";$s.WorkingDirectory="{self.racine}";$s.Save()')
        self._tache(t("Raccourci sur le Bureau"),
                    lambda: subprocess.run(["powershell", "-NoProfile", "-Command", script], check=True) and t("créé"),
                    self.sortie_auto)

    def reprendre(self) -> None:
        import shutil

        dossier = filedialog.askdirectory(title=t("Dossier contenant config.toml (et le sous-dossier donnees)"))
        if not dossier:
            return
        source = Path(dossier)
        copies = []
        if (source / "config.toml").exists():
            ancienne = lire_config(source / "config.toml")
            # Secrets encore en clair dans l'ancienne configuration : transférés dans le coffre-fort
            jeton = ancienne.get("clover", {}).pop("api_token", "")
            mdp = ancienne.get("sage_base", {}).pop("mot_de_passe", "")
            if jeton and not coffre.present(coffre.CLOVER_JETON):
                coffre.ecrire(coffre.CLOVER_JETON, jeton)
            if mdp and not coffre.present(coffre.SAGE_LECTURE):
                coffre.ecrire(coffre.SAGE_LECTURE, mdp)
            ecrire_config(self.chemin_config, ancienne)
            copies.append("config.toml")
        for nom in ("correspondance_articles.xlsx", "articles_a_relier.csv", "journal_imports.csv", "articles_sage.csv"):
            if (source / "donnees" / nom).exists():
                (self.racine / "donnees").mkdir(parents=True, exist_ok=True)
                shutil.copy2(source / "donnees" / nom, self.racine / "donnees" / nom)
                copies.append(nom)
        if not copies:
            messagebox.showwarning(TITRE, t("Aucun fichier de configuration trouvé dans ce dossier."))
            return
        messagebox.showinfo(TITRE, t("Repris : {fichiers}.\nL'application va se fermer : rouvrez-la.",
                                     fichiers=", ".join(copies)))
        self.destroy()

    def lancer(self, simulation: bool) -> None:
        if not self.enregistrer():
            return
        if not simulation and not messagebox.askyesno(
                TITRE, t("Lancer le traitement maintenant ? Les factures manquantes seront importées dans Sage.")):
            return
        zone = self.sortie_tableau
        zone.delete("1.0", "end")

        def traitement():
            from .__main__ import commande_moteur

            commande = commande_moteur() + ["auto"]
            if simulation:
                commande.append("--simulation")
            processus = subprocess.Popen(commande, cwd=self.racine, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                         text=True, encoding="utf-8", errors="replace",
                                         env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"},
                                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            for ligne in processus.stdout:
                self.file_messages.put((zone, ligne.rstrip()))
            return t("réussi") if processus.wait() == 0 else t("terminé avec des points à corriger (voir ci-dessus)")

        self._tache(t("Simulation") if simulation else t("Traitement"), traitement, zone)

    def ouvrir(self, chemin: Path) -> None:
        if chemin.exists():
            os.startfile(chemin)
        else:
            messagebox.showinfo(TITRE, t("Introuvable pour l'instant : {chemin}", chemin=chemin))

    def actualiser_tableau(self) -> None:
        from . import planification

        try:
            self._tache_installee = "non installée" not in planification.etat()
            tache = t("installée") if self._tache_installee else t("NON installée")
        except Exception:
            tache = "?"
        derniere = self._etat_etapes()[TABLEAU][1] or t("aucune")
        problemes = 0
        journal_auto = self.racine / "donnees" / "journal_automatique.log"
        if journal_auto.exists():
            execution = journal_auto.read_text(encoding="utf-8").split("===== ")[-1]
            problemes = execution.count("PROBLÈME") + execution.count("ERREUR")
        for enfant in self.cartes.winfo_children():
            enfant.destroy()
        for icone, titre, valeur, couleur in (
                ("🧾", t("Dernière facture importée"), derniere, VERT),
                ("⏰", t("Tâche planifiée"), tache, VERT if self._tache_installee else JAUNE),
                ("⚠", t("Points à corriger (dernier traitement)"), str(problemes), ROUGE if problemes else VERT)):
            carte = tk.Frame(self.cartes, background=CARTE, highlightthickness=1, highlightbackground=BORDURE)
            carte.pack(side="left", fill="x", expand=True, padx=(0, 12))
            tk.Frame(carte, height=4, background=couleur).pack(fill="x")
            ligne = tk.Frame(carte, background=CARTE)
            ligne.pack(fill="x", padx=14, pady=(10, 12))
            tk.Label(ligne, text=icone, font=("Segoe UI Emoji", 20), foreground=couleur, background=CARTE).pack(
                side="left", padx=(0, 12))
            textes = tk.Frame(ligne, background=CARTE)
            textes.pack(side="left", fill="x")
            tk.Label(textes, text=titre, font=("Segoe UI", 9), foreground=TEXTE_DOUX, background=CARTE,
                     anchor="w").pack(fill="x")
            tk.Label(textes, text=valeur, font=("Segoe UI Semibold", 15), foreground=TEXTE, background=CARTE,
                     anchor="w").pack(fill="x")
        if journal_auto.exists() and not self.sortie_tableau.get("1.0", "end").strip():
            for ligne in journal_auto.read_text(encoding="utf-8").splitlines()[-60:]:
                self._ecrire(self.sortie_tableau, ligne)
            self.sortie_tableau.see("end")
        self._maj_etapes()


def lancer_interface(racine: Path) -> None:
    (racine / "donnees").mkdir(parents=True, exist_ok=True)
    try:  # affichage net sur les écrans à mise à l'échelle (125 %, 150 %…)
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
        # identité propre dans la barre des tâches (sinon l'icône générique de Python ou de Windows)
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(ID_APPLICATION)
    except Exception:
        pass
    while True:  # un changement de langue reconstruit la fenêtre
        application = Application(racine)
        application.mainloop()
        if not application.relancer:
            break
