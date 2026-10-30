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
    CREATION = True  # fenêtre de création : reste une fenêtre à part (avec « Fermer »)


    def __init__(self, parent, titre: str, articles: dict[str, tuple[str, Decimal | None]], valider,
                 tiers: list[str] | None = None, libelle_tiers: str = "Client", libelle_prix: str = "Prix (HT)",
                 taxable: bool = False, sens: list[str] | None = None, action: str = "Enregistrer",
                 libelle_remarque: str = "Remarque", initial: dict | None = None, remarque_obligatoire: bool = False,
                 facteurs: dict | None = None, depots: dict[str, str] | None = None):
        """`initial` (« Modifier ») : {"tiers", "date", "remarque", "sens", "lignes": [dict comme self.lignes]}."""
        super().__init__(parent)
        self.articles, self.valider_document, self.avec_taxes = articles, valider, taxable
        # bons de commande : facteur du dernier achat (Qté Sage = Qté × Facteur), affiché en gris, non modifiable
        self.facteurs = facteurs
        self.remarque_obligatoire, self.libelle_remarque = remarque_obligatoire, libelle_remarque
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
        # documents de stock : dépôt (emplacement Sage d'un point de vente) d'où sort ou entre la marchandise
        self.depots = depots or {}
        self.depot = tk.StringVar(value=next(iter(self.depots)) if len(self.depots) == 1 else "")
        if depots is not None:
            g = entete.ajouter(entete.groupe(), 12)
            tk.Label(g, text=t("Dépôt") + " *", background=CARTE).pack(side="left", padx=(0, 4))
            ttk.Combobox(g, textvariable=self.depot, values=list(self.depots), state="readonly",
                         width=34).pack(side="left")
        g = entete.ajouter(entete.groupe(), 12)
        tk.Label(g, text=t("Date"), background=CARTE).pack(side="left", padx=(0, 4))
        self.date = tk.StringVar(value=date.today().isoformat())
        ChampDate(g, self.date, fond=CARTE).pack(side="left")
        g = entete.ajouter(entete.groupe(), 12)
        tk.Label(g, text=t(libelle_remarque) + (" *" if remarque_obligatoire else ""), background=CARTE).pack(
            side="left", padx=(0, 4))
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
        if facteurs is not None:
            self.facteur, self.qte_sage = tk.StringVar(value="1"), tk.StringVar(value="")
            for libelle, variable in (("Facteur", self.facteur), ("Qté Sage", self.qte_sage)):
                g = ajout.ajouter(ajout.groupe(), 10)
                tk.Label(g, text=t(libelle), background=CARTE).pack(side="left", padx=(0, 4))
                tk.Label(g, textvariable=variable, width=7, anchor="e", background="#e9eeea", foreground="#24332a",
                         font=("Segoe UI Semibold", 10), padx=6, pady=3).pack(side="left")
            self.quantite.trace_add("write", lambda *_: self._qte_sage())
        from . import taxes as tx

        self.taxe = tk.StringVar(value=t(tx.CHOIX[""]))
        if taxable:
            g = ajout.ajouter(ajout.groupe(), 10)
            tk.Label(g, text=t("Taxes"), background=CARTE).pack(side="left", padx=(0, 4))
            ttk.Combobox(g, textvariable=self.taxe, values=[t(v) for v in tx.CHOIX.values()], state="readonly",
                         width=14).pack(side="left")
        ajout.ajouter(Bouton(ajout, "➕  " + t("Ajouter la ligne"), self.ajouter, fond=CARTE, petit=True), 6)
        ajout.ajouter(Bouton(ajout, "✖  " + t("Retirer la ligne"), self.retirer, "secondaire", fond=CARTE,
                             petit=True))
        cadre = cadre_tableau(self)
        cadre.pack(fill="both", expand=True)
        colonnes = (["N° Sage", "Description", "Quantité"] + (["Facteur", "Qté Sage"] if facteurs is not None else [])
                    + [libelle_prix, "Montant"] + (["Taxes"] if taxable else []))
        self.arbre = ttk.Treeview(cadre, columns=[f"c{i}" for i in range(len(colonnes))], show="headings",
                                  selectmode="browse", height=10)
        largeurs = {"N° Sage": 110, "Description": 300, "Taxes": 110}
        for i, c in enumerate(colonnes):
            self.arbre.heading(f"c{i}", text=t(c))
            self.arbre.column(f"c{i}", width=largeurs.get(c, 85), anchor="w" if c in largeurs else "e",
                              stretch=c == "Description")
        self.arbre.pack(fill="both", expand=True)
        bas = Rangee(self)
        bas.pack(fill="x", pady=(8, 0))
        self.total = bas.ajouter(tk.Label(bas, text="", background=CARTE, font=("Segoe UI Semibold", 10)), 16)
        bas.ajouter(Bouton(bas, "✔  " + t(action), self.valider, fond=CARTE), 8)
        bas.ajouter(Bouton(bas, "✖  " + t("Fermer"), self.destroy, "secondaire", fond=CARTE))
        self.etat = tk.Label(self, text="", background=CARTE, foreground=TEXTE_DOUX, anchor="w", justify="left",
                             wraplength=940)
        self.etat.pack(fill="x", pady=(6, 0))
        if initial:
            self.tiers.set(initial.get("tiers", ""))
            self.date.set(initial.get("date") or self.date.get())
            self.remarque.set(initial.get("remarque", ""))
            if initial.get("sens"):
                self.sens.set(t(initial["sens"]))
            if initial.get("depot") is not None and self.depots:
                self.depot.set(next((k for k, v in self.depots.items() if v == initial["depot"]),
                                    self.depot.get()))
            self.lignes = [dict(l) for l in initial.get("lignes", [])]
        self._afficher()

    def _qte_sage(self) -> None:
        quantite, facteur = _decimal(self.quantite.get()), _decimal(self.facteur.get()) or Decimal(1)
        self.qte_sage.set(f"{(quantite * facteur).normalize():f}".replace(".", ",") if quantite else "")

    def _prix_propose(self) -> None:
        numero = self.choix.get(self.article.get())
        if numero and self.facteurs is not None:
            facteur = self.facteurs(self.tiers.get().strip(), numero) or Decimal(1)
            self.facteur.set(f"{facteur.normalize():f}".replace(".", ","))
            self._qte_sage()
            if self.articles[numero][1] is not None and not self.prix.get().strip():  # prix Sage × facteur
                self.prix.set(f"{self.articles[numero][1] * facteur:.2f}".replace(".", ","))
            return
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
        from . import taxes as tx

        code = tx.code_du_libelle(self.taxe.get(), t)
        ligne = {"numero_sage": numero, "description": self.articles[numero][0], "quantite": quantite, "prix": prix,
                 "taxable": bool(code), "taxe": code}
        if self.facteurs is not None:
            ligne["facteur"] = _decimal(self.facteur.get()) or Decimal(1)
        self.lignes.append(ligne)
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
            from . import taxes as tx

            facteur = l.get("facteur", Decimal(1))
            valeurs = ([l["numero_sage"], l["description"], f"{l['quantite'].normalize():f}".replace(".", ",")]
                       + ([f"{facteur.normalize():f}".replace(".", ","),
                           f"{(l['quantite'] * facteur).normalize():f}".replace(".", ",")]
                          if self.facteurs is not None else [])
                       + [_argent(l["prix"]), _argent(montant)]
                       + ([t(tx.libelle(tx.code(l)))] if self.avec_taxes else []))
            self.arbre.insert("", "end", iid=str(i), values=valeurs)
        rayer(self.arbre)
        total = sum(((l["quantite"] * l["prix"]).quantize(Decimal("0.01")) for l in self.lignes), Decimal(0))
        self.total.configure(text=t("{n} ligne(s) — total {m}", n=len(self.lignes), m=_argent(total)))

    def valider(self) -> None:
        if not self.lignes:
            self.etat.configure(text="✘ " + t("Ajoutez au moins une ligne."), foreground=ROUGE)
            return
        if self.remarque_obligatoire and not self.remarque.get().strip():
            self.etat.configure(text="✘ " + t("{c} est obligatoire.", c=t(self.libelle_remarque)), foreground=ROUGE)
            return
        try:
            date.fromisoformat(self.date.get().strip())
        except ValueError:
            self.etat.configure(text="✘ " + t("Date au format AAAA-MM-JJ."), foreground=ROUGE)
            return
        if self.depots and self.depot.get() not in self.depots:
            self.etat.configure(text="✘ " + t("Choisissez le dépôt."), foreground=ROUGE)
            return
        sens = next((s for s in self._sens if t(s) == self.sens.get()), "")
        entete = {"tiers": self.tiers.get().strip(), "date": self.date.get().strip(),
                  "remarque": self.remarque.get().strip(), "sens": sens,
                  "depot": self.depots.get(self.depot.get(), "")}
        try:
            message = self.valider_document(entete, self.lignes)
        except Exception as exc:
            self.etat.configure(text="✘ " + str(exc), foreground=ROUGE)
            return
        messagebox.showinfo(self.title(), message, parent=self.master)
        self.destroy()
