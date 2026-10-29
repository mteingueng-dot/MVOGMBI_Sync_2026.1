"""Fenêtre de saisie d'un document (demande du propriétaire du 2026-10-29) : en-tête (tiers, date, remarque) et
lignes (article Sage, quantité, prix ou coût, taxable). Commune aux commandes clients, factures de vente, documents
de stock, bons de commande et factures d'achat saisis à la main ; `valider(entete, lignes)` fait le reste."""

from __future__ import annotations

import tkinter as tk
from datetime import date
from decimal import Decimal, InvalidOperation
from tkinter import messagebox, ttk

from .design import CARTE, ROUGE, TEXTE_DOUX, Bouton, ChampDate, ChampRecherche, Rangee, cadre_tableau, rayer
from .langues import t


def _decimal(texte: str) -> Decimal | None:
    try:
        return Decimal(texte.replace(" ", "").replace(",", ".")) if texte.strip() else None
    except InvalidOperation:
        return None


def _argent(v: Decimal) -> str:
    return f"{v:,.2f} $".replace(",", " ").replace(".", ",")


class SaisieDocument(tk.Toplevel):
    """`articles` : {n° Sage : (description, prix proposé)} ; `tiers` : liste des clients ou fournisseurs (None :
    pas de tiers) ; `sens` : choix Entrée / Sortie (documents de stock) ; `taxable` : colonne des taxes."""

    def __init__(self, parent, titre: str, articles: dict[str, tuple[str, Decimal | None]], valider,
                 tiers: list[str] | None = None, libelle_tiers: str = "Client", libelle_prix: str = "Prix (HT)",
                 taxable: bool = False, sens: list[str] | None = None, action: str = "Enregistrer",
                 libelle_remarque: str = "Remarque"):
        super().__init__(parent)
        self.articles, self.valider_document, self.avec_taxes = articles, valider, taxable
        self.lignes: list[dict] = []
        self.title(t(titre))
        self.configure(background=CARTE, padx=14, pady=10)
        self.transient(parent)
        self.geometry("980x600")
        entete = Rangee(self)
        entete.pack(fill="x")
        self.tiers = tk.StringVar()
        if tiers is not None:
            g = entete.ajouter(entete.groupe(), 12)
            tk.Label(g, text=t(libelle_tiers) + " *", background=CARTE).pack(side="left", padx=(0, 4))
            ChampRecherche(g, self.tiers, tiers, largeur=34).pack(side="left")
        self.sens = tk.StringVar(value=t(sens[0]) if sens else "")
        self._sens = sens or []
        if sens:
            g = entete.ajouter(entete.groupe(), 12)
            tk.Label(g, text=t("Mouvement"), background=CARTE).pack(side="left", padx=(0, 4))
            ttk.Combobox(g, textvariable=self.sens, values=[t(s) for s in sens], state="readonly",
                         width=10).pack(side="left")
        g = entete.ajouter(entete.groupe(), 12)
        tk.Label(g, text=t("Date"), background=CARTE).pack(side="left", padx=(0, 4))
        self.date = tk.StringVar(value=date.today().isoformat())
        ChampDate(g, self.date, fond=CARTE).pack(side="left")
        g = entete.ajouter(entete.groupe(), 12)
        tk.Label(g, text=t(libelle_remarque), background=CARTE).pack(side="left", padx=(0, 4))
        self.remarque = tk.StringVar()
        ttk.Entry(g, textvariable=self.remarque, width=36).pack(side="left")
        # ligne à ajouter
        ajout = Rangee(self)
        ajout.pack(fill="x", pady=(10, 4))
        g = ajout.ajouter(ajout.groupe(), 10)
        tk.Label(g, text=t("Article"), background=CARTE).pack(side="left", padx=(0, 4))
        self.article = tk.StringVar()
        self.choix = {f"{n} — {d}": n for n, (d, _p) in articles.items()}
        ChampRecherche(g, self.article, sorted(self.choix, key=str.casefold), largeur=46,
                       au_choix=lambda _v=None: self._prix_propose()).pack(side="left")
        g = ajout.ajouter(ajout.groupe(), 10)
        tk.Label(g, text=t("Quantité"), background=CARTE).pack(side="left", padx=(0, 4))
        self.quantite = tk.StringVar(value="1")
        ttk.Entry(g, textvariable=self.quantite, width=8).pack(side="left")
        g = ajout.ajouter(ajout.groupe(), 10)
        self.libelle_prix = libelle_prix
        tk.Label(g, text=t(libelle_prix), background=CARTE).pack(side="left", padx=(0, 4))
        self.prix = tk.StringVar()
        ttk.Entry(g, textvariable=self.prix, width=10).pack(side="left")
        self.taxe = tk.BooleanVar(value=False)
        if taxable:
            ajout.ajouter(ttk.Checkbutton(ajout, text=t("TPS + TVQ"), variable=self.taxe), 10)
        ajout.ajouter(Bouton(ajout, "➕  " + t("Ajouter la ligne"), self.ajouter, fond=CARTE, petit=True), 6)
        ajout.ajouter(Bouton(ajout, "✖  " + t("Retirer la ligne"), self.retirer, "secondaire", fond=CARTE,
                             petit=True))
        cadre = cadre_tableau(self)
        cadre.pack(fill="both", expand=True)
        colonnes = ["N° Sage", "Description", "Quantité", libelle_prix, "Montant"] + (["Taxes"] if taxable else [])
        self.arbre = ttk.Treeview(cadre, columns=[f"c{i}" for i in range(len(colonnes))], show="headings",
                                  selectmode="browse", height=10)
        for i, (c, l) in enumerate(zip(colonnes, (110, 330, 80, 100, 100, 80))):
            self.arbre.heading(f"c{i}", text=t(c))
            self.arbre.column(f"c{i}", width=l, anchor="e" if i in (2, 3, 4) else "w", stretch=i == 1)
        self.arbre.pack(fill="both", expand=True)
        bas = Rangee(self)
        bas.pack(fill="x", pady=(8, 0))
        self.total = bas.ajouter(tk.Label(bas, text="", background=CARTE, font=("Segoe UI Semibold", 10)), 16)
        bas.ajouter(Bouton(bas, "✔  " + t(action), self.valider, fond=CARTE))
        self.etat = tk.Label(self, text="", background=CARTE, foreground=TEXTE_DOUX, anchor="w", justify="left",
                             wraplength=940)
        self.etat.pack(fill="x", pady=(6, 0))
        self._afficher()

    def _prix_propose(self) -> None:
        numero = self.choix.get(self.article.get())
        if numero and self.articles[numero][1] is not None and not self.prix.get().strip():
            self.prix.set(f"{self.articles[numero][1]:.2f}".replace(".", ","))

    def ajouter(self) -> None:
        numero = self.choix.get(self.article.get())
        quantite, prix = _decimal(self.quantite.get()), _decimal(self.prix.get()) or Decimal(0)
        if not numero:
            self.etat.configure(text="✘ " + t("Choisissez un article de la liste."), foreground=ROUGE)
            return
        if not quantite or quantite <= 0:
            self.etat.configure(text="✘ " + t("La quantité doit être un nombre positif."), foreground=ROUGE)
            return
        self.lignes.append({"numero_sage": numero, "description": self.articles[numero][0], "quantite": quantite,
                            "prix": prix, "taxable": self.taxe.get()})
        self.article.set("")
        self.quantite.set("1")
        self.prix.set("")
        self.etat.configure(text="", foreground=TEXTE_DOUX)
        self._afficher()

    def retirer(self) -> None:
        choix = self.arbre.selection()
        if choix:
            del self.lignes[int(choix[0])]
            self._afficher()

    def _afficher(self) -> None:
        self.arbre.delete(*self.arbre.get_children())
        for i, l in enumerate(self.lignes):
            montant = (l["quantite"] * l["prix"]).quantize(Decimal("0.01"))
            valeurs = [l["numero_sage"], l["description"], f"{l['quantite'].normalize():f}".replace(".", ","),
                       _argent(l["prix"]), _argent(montant)] + (["✔" if l["taxable"] else ""] if self.avec_taxes else [])
            self.arbre.insert("", "end", iid=str(i), values=valeurs)
        rayer(self.arbre)
        total = sum(((l["quantite"] * l["prix"]).quantize(Decimal("0.01")) for l in self.lignes), Decimal(0))
        self.total.configure(text=t("{n} ligne(s) — total {m}", n=len(self.lignes), m=_argent(total)))

    def valider(self) -> None:
        if not self.lignes:
            self.etat.configure(text="✘ " + t("Ajoutez au moins une ligne."), foreground=ROUGE)
            return
        try:
            date.fromisoformat(self.date.get().strip())
        except ValueError:
            self.etat.configure(text="✘ " + t("Date au format AAAA-MM-JJ."), foreground=ROUGE)
            return
        sens = next((s for s in self._sens if t(s) == self.sens.get()), "")
        entete = {"tiers": self.tiers.get().strip(), "date": self.date.get().strip(),
                  "remarque": self.remarque.get().strip(), "sens": sens}
        try:
            message = self.valider_document(entete, self.lignes)
        except Exception as exc:
            self.etat.configure(text="✘ " + str(exc), foreground=ROUGE)
            return
        messagebox.showinfo(self.title(), message, parent=self.master)
        self.destroy()
