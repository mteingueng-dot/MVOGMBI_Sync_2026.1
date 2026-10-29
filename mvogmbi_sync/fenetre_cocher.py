"""Fenêtre « liste à cocher » : les lignes proposées sont affichées, la personne coche celles à traiter puis lance le
traitement (coûts Clover depuis Sage, comptes Sage par catégorie). Une ligne non permise (valeur aberrante, rien à
faire) reste visible, grisée, et ne peut pas être cochée."""

from __future__ import annotations

import threading
import tkinter as tk
from tkinter import messagebox, ttk

from .design import CARTE, ROUGE, TEXTE_DOUX, VERT_FONCE, Bouton, Rangee, apres_frappe, cadre_tableau, rayer
from .export_tableau import bouton_exporter
from .langues import t

COCHE, VIDE = "☑", "☐"
TOUS = "Tous"


class FenetreACocher(tk.Toplevel):
    """`colonnes` : [(titre, largeur)] ; `valeurs(ligne)` -> tuple affiché ; chaque ligne a `permis`,
    `cochee_par_defaut` et `etat`. `lire()` -> (lignes, résumé) et `traiter(lignes, progression)` -> texte du bilan
    sont lancés dans un fil (jamais dans la fenêtre)."""

    def __init__(self, parent, titre: str, explication: str, colonnes, valeurs, lire, traiter, action: str,
                 confirmation: str, etat_initial: str | None = None, ajouts=None):
        super().__init__(parent)
        self.valeurs, self.lire, self.traiter = valeurs, lire, traiter
        self.confirmation = confirmation
        self.lignes, self.cochees, self.en_cours, self.bilan = [], set(), False, ""
        self.etat_initial = etat_initial  # filtre « Afficher » au premier chargement (s'il a des lignes)
        self.title(titre)
        self.configure(background=CARTE, padx=14, pady=10)
        self.transient(parent)
        self.geometry("1150x640")
        self.minsize(560, 380)
        tk.Label(self, text=explication, background=CARTE, foreground=TEXTE_DOUX, justify="left", anchor="w",
                 wraplength=1100).pack(fill="x")
        barre = Rangee(self)
        barre.pack(fill="x", pady=8)
        groupe = barre.ajouter(barre.groupe(), 12)
        tk.Label(groupe, text=t("Afficher :"), background=CARTE).pack(side="left")
        self.filtre = tk.StringVar(value=t(TOUS))
        self.liste_filtre = ttk.Combobox(groupe, textvariable=self.filtre, state="readonly", width=26)
        self.liste_filtre.pack(side="left", padx=(4, 0))
        self.liste_filtre.bind("<<ComboboxSelected>>", lambda _e: self.afficher())
        groupe = barre.ajouter(barre.groupe(), 12)
        tk.Label(groupe, text=t("Rechercher :"), background=CARTE).pack(side="left")
        self.recherche = tk.StringVar()
        champ = ttk.Entry(groupe, textvariable=self.recherche, width=22)
        champ.pack(side="left", padx=(4, 0))
        champ.bind("<KeyRelease>", apres_frappe(champ, self.afficher))
        barre.ajouter(Bouton(barre, COCHE + "  " + t("Tout cocher"), lambda: self.tout(True), "secondaire",
                             fond=CARTE, petit=True))
        barre.ajouter(Bouton(barre, VIDE + "  " + t("Tout décocher"), lambda: self.tout(False), "secondaire",
                             fond=CARTE, petit=True))
        barre.ajouter(Bouton(barre, "🔄  " + t("Actualiser"), self.charger, "secondaire", fond=CARTE, petit=True))
        if ajouts:  # réglages propres à la fenêtre (ex. horizon des bons de commande), avant le tableau
            ajouts(self, barre)
        cadre = cadre_tableau(self)
        cadre.pack(fill="both", expand=True)
        cles = ["coche"] + [f"c{i}" for i in range(len(colonnes))]
        self.arbre = ttk.Treeview(cadre, columns=cles, show="headings", selectmode="extended")
        self.arbre.heading("coche", text="✔")
        self.arbre.column("coche", width=34, anchor="center", stretch=False)
        for cle, (titre_col, largeur) in zip(cles[1:], colonnes):
            self.arbre.heading(cle, text=t(titre_col))
            self.arbre.column(cle, width=largeur, anchor="w", stretch=largeur >= 200)
        self.arbre.tag_configure("bloquee", foreground="#9a9a9a")
        self.arbre.tag_configure("cochee", foreground=VERT_FONCE)
        defilement = ttk.Scrollbar(cadre, orient="vertical", command=self.arbre.yview)
        horizontal = ttk.Scrollbar(cadre, orient="horizontal", command=self.arbre.xview)
        self.arbre.configure(yscrollcommand=defilement.set, xscrollcommand=horizontal.set)
        horizontal.pack(side="bottom", fill="x")
        defilement.pack(side="right", fill="y")  # avant le tableau : toujours visible, même s'il est large
        self.arbre.pack(side="left", fill="both", expand=True)
        self.arbre.bind("<Button-1>", self._clic)
        self.arbre.bind("<space>", lambda _e: self._basculer(self.arbre.selection()))
        bas = Rangee(self)
        bas.pack(fill="x", pady=(8, 0))
        self.compteur = bas.ajouter(tk.Label(bas, text="", background=CARTE, font=("Segoe UI Semibold", 10)), 16)
        self.bouton = bas.ajouter(Bouton(bas, "▶  " + action, self.lancer, fond=CARTE))
        bas.ajouter(bouton_exporter(bas, self.arbre, titre))
        self.etat = tk.Label(self, text="", background=CARTE, foreground=TEXTE_DOUX, anchor="w", justify="left",
                             wraplength=1100)
        self.etat.pack(fill="x", pady=(6, 0))
        self.charger()

    # ------------------------------------------------------------------ données
    def _fil(self, travail, fin) -> None:
        def executer():
            try:
                resultat, erreur = travail(), ""
            except Exception as exc:
                resultat, erreur = None, str(exc)
            self.after(0, lambda: fin(resultat, erreur))

        threading.Thread(target=executer, daemon=True).start()

    def charger(self) -> None:
        if self.en_cours:
            return
        self.en_cours = True
        self.etat.configure(text=t("Lecture de Clover et de Sage…"), foreground=TEXTE_DOUX)
        self._fil(self.lire, self._charge)

    def _charge(self, resultat, erreur: str) -> None:
        self.en_cours = False
        if not self.winfo_exists():
            return
        if erreur:
            self.etat.configure(text="✘ " + erreur, foreground=ROUGE)
            return
        self.lignes, resume = resultat
        self.cochees = {i for i, l in enumerate(self.lignes) if l.permis and l.cochee_par_defaut}
        etats = sorted({l.etat for l in self.lignes})
        self.liste_filtre.configure(values=[t(TOUS)] + [t(e) for e in etats])
        self.filtre.set(t(self.etat_initial) if self.etat_initial in etats else t(TOUS))
        self.etat_initial = None
        self.etat.configure(text=resume + ("\n✔ " + self.bilan if self.bilan else ""),
                            foreground=VERT_FONCE if self.bilan else TEXTE_DOUX)
        self.afficher()

    def afficher(self) -> None:
        self.arbre.delete(*self.arbre.get_children())
        filtre, texte = self.filtre.get(), self.recherche.get().strip().casefold()
        for i, l in enumerate(self.lignes):
            if filtre != t(TOUS) and t(l.etat) != filtre:
                continue
            valeurs = self.valeurs(l)
            if texte and texte not in " ".join(str(v) for v in valeurs).casefold():
                continue
            self.arbre.insert("", "end", iid=str(i), values=(self._coche(i),) + tuple(valeurs),
                              tags=self._tags(i))
        rayer(self.arbre)
        self._compter()

    def _coche(self, i: int) -> str:
        return COCHE if i in self.cochees else ("" if not self.lignes[i].permis else VIDE)

    def _tags(self, i: int) -> tuple:
        return ("bloquee",) if not self.lignes[i].permis else (("cochee",) if i in self.cochees else ())

    def _compter(self) -> None:
        self.compteur.configure(text=t("{n} ligne(s) cochée(s) sur {m}", n=len(self.cochees), m=len(self.lignes)))

    # ------------------------------------------------------------------ cases
    def _clic(self, evenement) -> None:
        if self.arbre.identify_column(evenement.x) == "#1" and self.arbre.identify_region(evenement.x, evenement.y) == "cell":
            ligne = self.arbre.identify_row(evenement.y)
            if ligne:
                self._basculer([ligne])
                return "break"

    def _basculer(self, iids) -> None:
        iids = [i for i in iids if self.lignes[int(i)].permis]
        cocher = any(int(i) not in self.cochees for i in iids)
        for iid in iids:
            (self.cochees.add if cocher else self.cochees.discard)(int(iid))
            self.arbre.set(iid, "coche", self._coche(int(iid)))
            garde = [g for g in self.arbre.item(iid, "tags") if g == "rayure"]
            self.arbre.item(iid, tags=tuple(garde) + self._tags(int(iid)))
        self._compter()

    def tout(self, cocher: bool) -> None:
        """Coche ou décoche les lignes affichées (filtre et recherche respectés)."""
        iids = self.arbre.get_children()
        for iid in iids:
            if self.lignes[int(iid)].permis:
                (self.cochees.add if cocher else self.cochees.discard)(int(iid))
        self.afficher()

    # ------------------------------------------------------------------ traitement
    def lancer(self) -> None:
        if self.en_cours:
            return
        choisies = [self.lignes[i] for i in sorted(self.cochees) if self.lignes[i].permis]
        if not choisies:
            messagebox.showinfo(self.title(), t("Cochez au moins une ligne."), parent=self)
            return
        if not messagebox.askyesno(self.title(), self.confirmation.format(n=len(choisies)), parent=self):
            return
        self.en_cours = True

        def progression(fait: int, total: int) -> None:
            self.after(0, lambda: self.etat.configure(text=t("{n} / {m} traitée(s)…", n=fait, m=total),
                                                      foreground=TEXTE_DOUX))

        self.etat.configure(text=t("Traitement en cours…"), foreground=TEXTE_DOUX)
        self._fil(lambda: self.traiter(choisies, progression), self._fin)

    def _fin(self, bilan, erreur: str) -> None:
        self.en_cours = False
        if not self.winfo_exists():
            return
        if erreur:
            self.etat.configure(text="✘ " + erreur, foreground=ROUGE)
            return
        self.bilan = bilan.splitlines()[0]
        messagebox.showinfo(self.title(), bilan, parent=self)
        self.charger()
