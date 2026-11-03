"""Comptabilité > « Plan comptable » (demande du propriétaire du 2026-11-01) : comptes de Sage, et Ajouter /
Modifier / Supprimer appliqués dans Sage (robot_comptes.py, l'application ouvre Sage elle-même ; Sage doit être
fermé). Vérifié dans Sage après chaque changement."""

from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk

from . import plan_comptable as pc
from .design import CARTE, ROUGE, TEXTE_DOUX, VERT_FONCE, Bouton, FenetreOutil, Rangee, action_permise, apres_frappe
from .export_tableau import bouton_exporter
from .langues import t


def _config(racine: Path) -> dict:
    import tomllib

    chemin = Path(racine) / "config.toml"
    return tomllib.loads(chemin.read_text(encoding="utf-8")) if chemin.exists() else {}


class FenetrePlanComptable(FenetreOutil):
    def __init__(self, parent, racine: Path):
        from .page_rapports import tableau_simple

        super().__init__(parent)
        self.racine = Path(racine)
        self.title(t("Plan comptable"))
        self.configure(background=CARTE, padx=14, pady=10)
        self.geometry("1000x650")
        self.comptes: list[pc.Compte] = []
        self.visibles: list[pc.Compte] = []
        barre = Rangee(self)
        barre.pack(fill="x")
        g = barre.ajouter(barre.groupe(), 10)
        tk.Label(g, text=t("Rechercher :"), background=CARTE).pack(side="left", padx=(0, 4))
        self.texte = tk.StringVar()
        champ = tk.Entry(g, textvariable=self.texte, width=26)
        champ.pack(side="left")
        champ.bind("<KeyRelease>", apres_frappe(champ, self.afficher))
        for texte, commande, style in (("🔄  " + t("Actualiser"), lambda: self.charger(True), "principal"),
                                       ("➕  " + t("Ajouter"), self.ajouter, "principal"),
                                       ("✎  " + t("Modifier"), self.modifier, "secondaire"),
                                       ("🗑  " + t("Supprimer"), self.supprimer, "danger")):
            barre.ajouter(Bouton(barre, texte, commande, style, fond=CARTE, petit=True), 8)
        self.etat = tk.Label(self, text="", background=CARTE, foreground=TEXTE_DOUX, anchor="w", justify="left",
                             wraplength=960)
        self.etat.pack(fill="x", pady=(6, 0))
        self.tableau = tableau_simple(self, hauteur=20)
        self.tableau.tag_configure("titre", font=("Segoe UI Semibold", 9), background="#e8f3ea")
        self.tableau.tag_configure("inactif", foreground="#9aa79e")
        self.tableau.bind("<Double-1>", lambda _e: self.modifier())
        barre.ajouter(bouton_exporter(barre, self.tableau, lambda: t("Plan comptable")))
        self.charger()

    def charger(self, forcer: bool = False) -> None:
        self.etat.configure(text=t("Lecture du plan comptable dans Sage…"), foreground=TEXTE_DOUX)

        def travail():
            comptes = pc.comptes_connus(self.racine, _config(self.racine), forcer=forcer)
            self.after(0, lambda: self._charge(comptes))

        threading.Thread(target=travail, daemon=True).start()

    def _charge(self, comptes: dict) -> None:
        self.comptes = sorted(comptes.values(), key=lambda c: int(c.numero))
        self.afficher()
        if not comptes:
            self.etat.configure(text="✘ " + t("Le plan comptable n'a pas pu être lu dans Sage."), foreground=ROUGE)

    def afficher(self) -> None:
        from .page_rapports import remplir

        texte = self.texte.get().strip().casefold()
        self.visibles = [c for c in self.comptes if not texte or texte in f"{c.numero} {c.nom}".casefold()]
        remplir(self.tableau, ["N°", "Compte", "Type", "Classe", "État"],
                [[c.numero, c.nom, t(pc.TYPES.get(c.type, c.type)), t(c.classe),
                  t("Inactif") if c.inactif else t("Actif")] for c in self.visibles],
                {"N°": 80, "Compte": 380, "Type": 190},
                lambda i: ("titre",) if self.visibles[i].type not in pc.DETAIL else (
                    ("inactif",) if self.visibles[i].inactif else ()), decroissant=False)
        self.etat.configure(text=t("{n} compte(s). En vert : en-têtes et totaux (aucune écriture). Ajouter, modifier ou "
                                   "supprimer : l'application ouvre Sage elle-même (fermez Sage).",
                                   n=len(self.visibles)), foreground=TEXTE_DOUX)

    def _choisi(self):
        choix = self.tableau.selection()
        if not choix:
            messagebox.showinfo(self.title(), t("Choisissez un compte dans la liste."), parent=self)
            return None
        return self.visibles[int(choix[0])]

    def _appliquer(self, demandes, texte: str) -> None:
        from .robot_comptes import appliquer

        if not action_permise(self, "Modifier le plan comptable"):
            return
        self.etat.configure(text=texte, foreground=TEXTE_DOUX)

        def travail():
            try:
                resultats = appliquer(self.racine, _config(self.racine), demandes)
                message = "\n".join(f"{r['numero']} : " + (t("fait") if r["fait"] else "✘ " + " ; ".join(r["messages"]))
                                    for r in resultats)
                couleur = VERT_FONCE if all(r["fait"] for r in resultats) else ROUGE
            except Exception as exc:
                message, couleur = "✘ " + str(exc), ROUGE

            def fin():
                self.etat.configure(text=message, foreground=couleur)
                self.charger(forcer=True)

            self.after(0, fin)

        threading.Thread(target=travail, daemon=True).start()

    def ajouter(self) -> None:
        from .robot_comptes import DemandeCompte

        fenetre = tk.Toplevel(self)
        fenetre.title(t("Nouveau compte"))
        fenetre.configure(background=CARTE, padx=16, pady=12)
        fenetre.transient(self.winfo_toplevel())
        v = {"numero": tk.StringVar(), "nom": tk.StringVar(), "type": tk.StringVar(value=t("Compte de groupe"))}
        for rang, (cle, libelle) in enumerate((("numero", "N° de compte *"), ("nom", "Description *"))):
            tk.Label(fenetre, text=t(libelle), background=CARTE, anchor="w").grid(row=rang, column=0, sticky="w", pady=3)
            ttk.Entry(fenetre, textvariable=v[cle], width=36 if cle == "nom" else 10).grid(row=rang, column=1, sticky="w")
        tk.Label(fenetre, text=t("Type"), background=CARTE, anchor="w").grid(row=2, column=0, sticky="w", pady=3)
        ttk.Combobox(fenetre, textvariable=v["type"], state="readonly", width=24,
                     values=[t("Compte de groupe"), t("Compte de sous-groupe")]).grid(row=2, column=1, sticky="w")
        message = tk.Label(fenetre, text=t("Le n° doit tomber dans la bonne section de Sage (ex. 5xxx entre l'en-tête "
                                           "et le total des charges)."), background=CARTE, foreground=TEXTE_DOUX,
                           wraplength=380, justify="left")
        message.grid(row=3, column=0, columnspan=2, sticky="w", pady=(6, 0))

        def valider() -> None:
            numero, nom = v["numero"].get().strip(), " ".join(v["nom"].get().split())
            if not numero.isdigit() or not nom:
                message.configure(text="✘ " + t("N° (chiffres) et description obligatoires."), foreground=ROUGE)
                return
            if any(c.numero == numero for c in self.comptes):
                message.configure(text="✘ " + t("Le compte {n} existe déjà.", n=numero), foreground=ROUGE)
                return
            fenetre.destroy()
            type_ = "L" if v["type"].get() == t("Compte de sous-groupe") else "R"
            self._appliquer([DemandeCompte("creer", numero, nom, type_)], t("Création du compte {n} dans Sage…",
                                                                          n=numero))

        Bouton(fenetre, "✔  " + t("Créer dans Sage"), valider, fond=CARTE).grid(row=4, column=1, sticky="e", pady=(10, 0))

    def modifier(self) -> None:
        from .robot_comptes import DemandeCompte

        c = self._choisi()
        if c is None:
            return
        nom = simpledialog.askstring(self.title(), t("Description du compte {n} :", n=c.numero), initialvalue=c.nom,
                                     parent=self)
        if nom is None:
            return
        inactif = messagebox.askyesno(self.title(), t("Le compte {n} doit-il être inactif ?", n=c.numero), parent=self,
                                      default="yes" if c.inactif else "no")
        demande = DemandeCompte("modifier", c.numero, " ".join(nom.split()) if nom.strip() != c.nom else "",
                                inactif=inactif if inactif != c.inactif else None)
        if not demande.nom and demande.inactif is None:
            return
        self._appliquer([demande], t("Modification du compte {n} dans Sage…", n=c.numero))

    def supprimer(self) -> None:
        from .robot_comptes import DemandeCompte

        c = self._choisi()
        if c is None:
            return
        if messagebox.askyesno(self.title(), t("Supprimer le compte {n} ({c}) de Sage ? Sage refuse un compte qui a des "
                                               "écritures ou un solde.", n=c.numero, c=c.nom), parent=self):
            self._appliquer([DemandeCompte("supprimer", c.numero)], t("Suppression du compte {n} dans Sage…",
                                                                      n=c.numero))
