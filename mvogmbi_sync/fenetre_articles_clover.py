"""Fenêtre « Articles Clover » (menu Articles, demande du propriétaire du 2026-10-28) : la liste des articles de Clover
avec ID Clover, nom, prix, type de prix, unité de prix, code produit, date de péremption, quantité et catégories ;
recherche, filtres (catégorie, type de prix, stock), tri par colonne (clic sur l'en-tête) et export Excel, CSV ou PDF.

Date de péremption = UGS (SKU) de Clover lue comme une date (peremption.lire_date : JJ/MM/AAAA, JJ-MM-AAAA, JJ/MM/AA,
AAAA-MM-JJ) ; une UGS qui n'est pas une date n'est pas affichée. « Effacer les UGS qui ne sont pas des dates » les
liste, la personne coche, puis l'UGS est vidée dans Clover (règle du propriétaire du 2026-10-28) ; chaque UGS effacée
est notée dans donnees/journal_ugs_effacees.csv (pour la retrouver au besoin)."""

from __future__ import annotations

import threading
import tkinter as tk
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from tkinter import ttk

from .design import (CARTE, ROUGE, TEXTE_DOUX, Bouton, ChampRecherche, Rangee, apres_frappe, cadre_tableau, defilement,
                     rayer)
from .export_tableau import bouton_exporter
from .langues import t

COLONNES = (("id", "ID Clover", 120), ("nom", "Nom", 320), ("prix", "Prix", 80), ("type", "Type de prix", 100),
            ("unite", "Unité de prix", 95), ("code", "Code produit", 130), ("ugs", "Date de péremption", 130),
            ("quantite", "Quantité", 80), ("categories", "Catégories", 200))
TOUS = "Toutes"
STOCKS = ("Tous", "En stock (> 0)", "Stock nul", "Stock négatif", "Sans suivi du stock")


def ligne_article(a: dict, types: dict[str, str]) -> tuple:
    """Article Clover (expand itemStock, categories) -> valeurs des 9 colonnes (date de péremption : date ou None)."""
    from .peremption import lire_date

    stock = (a.get("itemStock") or {})
    quantite = stock.get("quantity", stock.get("stockCount"))
    categories = ", ".join(c.get("name", "") for c in (a.get("categories") or {}).get("elements") or [])
    prix = (Decimal(int(a.get("price") or 0)) / 100).quantize(Decimal("0.01"))
    return (a.get("id", ""), (a.get("name") or "").strip(), prix, types.get(a.get("priceType"), a.get("priceType") or ""),
            a.get("unitName") or "", a.get("code") or "", lire_date(a.get("sku")),
            None if quantite is None else Decimal(str(quantite)).normalize(), categories)


def _texte(v) -> str:
    if isinstance(v, Decimal):
        return f"{v:f}".replace(".", ",")
    if isinstance(v, date):
        return f"{v:%d/%m/%Y}"
    return "" if v is None else str(v)


class FenetreArticlesClover(tk.Toplevel):
    def __init__(self, parent, racine: Path):
        from .creation_articles import TYPES_PRIX

        super().__init__(parent)
        self.racine = Path(racine)
        self.types = TYPES_PRIX
        self.lignes: list[tuple] = []
        self.tri = (1, False)  # par nom
        self.title(t("Articles Clover"))
        self.configure(background=CARTE, padx=14, pady=10)
        self.transient(parent)
        self.geometry("1250x700")
        self.minsize(640, 400)
        barre = Rangee(self)
        barre.pack(fill="x")
        groupe = barre.ajouter(barre.groupe(), 12)
        tk.Label(groupe, text=t("Rechercher :"), background=CARTE).pack(side="left", padx=(0, 4))
        self.recherche = tk.StringVar()
        champ = ttk.Entry(groupe, textvariable=self.recherche, width=26)
        champ.pack(side="left")
        champ.bind("<KeyRelease>", apres_frappe(champ, self.afficher))
        groupe = barre.ajouter(barre.groupe(), 12)
        tk.Label(groupe, text=t("Catégorie"), background=CARTE).pack(side="left", padx=(0, 4))
        self.categorie = tk.StringVar()
        self.champ_categorie = ChampRecherche(groupe, self.categorie, [], largeur=20,
                                              au_choix=lambda _v=None: self.afficher())
        self.champ_categorie.pack(side="left")
        groupe = barre.ajouter(barre.groupe(), 12)
        tk.Label(groupe, text=t("Type de prix"), background=CARTE).pack(side="left", padx=(0, 4))
        self.type_prix = tk.StringVar(value=t(TOUS))
        liste = ttk.Combobox(groupe, textvariable=self.type_prix, state="readonly", width=12,
                             values=[t(TOUS)] + [t(v) for v in self.types.values()])
        liste.pack(side="left")
        liste.bind("<<ComboboxSelected>>", lambda _e: self.afficher())
        groupe = barre.ajouter(barre.groupe(), 12)
        tk.Label(groupe, text=t("Stock"), background=CARTE).pack(side="left", padx=(0, 4))
        self.stock = tk.StringVar(value=t(STOCKS[0]))
        liste = ttk.Combobox(groupe, textvariable=self.stock, state="readonly", width=18, values=[t(s) for s in STOCKS])
        liste.pack(side="left")
        liste.bind("<<ComboboxSelected>>", lambda _e: self.afficher())
        barre.ajouter(Bouton(barre, "✖  " + t("Réinitialiser les filtres"), self.reinitialiser, "secondaire", fond=CARTE,
                             petit=True), 8)
        barre.ajouter(Bouton(barre, "🔄  " + t("Actualiser"), self.charger, "secondaire", fond=CARTE, petit=True), 8)
        barre.ajouter(Bouton(barre, "🧹  " + t("Effacer les UGS qui ne sont pas des dates…"), self.effacer_ugs,
                             "secondaire", fond=CARTE, petit=True), 8)
        cadre = cadre_tableau(self)
        cadre.pack(fill="both", expand=True, pady=(8, 0))
        self.arbre = ttk.Treeview(cadre, columns=[c[0] for c in COLONNES], show="headings", selectmode="extended")
        for i, (cle, titre, largeur) in enumerate(COLONNES):
            self.arbre.heading(cle, text=t(titre), command=lambda i=i: self.trier(i))
            self.arbre.column(cle, width=largeur, anchor="e" if cle in ("prix", "quantite") else "w",
                              stretch=cle in ("nom", "categories"))
        self.arbre.tag_configure("negatif", foreground=ROUGE)
        horizontal = ttk.Scrollbar(cadre, orient="horizontal", command=self.arbre.xview)
        self.arbre.configure(xscrollcommand=horizontal.set)
        horizontal.pack(side="bottom", fill="x")
        self.arbre.pack(side="left", fill="both", expand=True)
        defilement(self.arbre)
        bas = Rangee(self)
        bas.pack(fill="x", pady=(8, 0))
        self.etat = bas.ajouter(tk.Label(bas, text="", background=CARTE, foreground=TEXTE_DOUX), 16)
        bas.ajouter(bouton_exporter(bas, self.arbre, t("Articles Clover")))
        self.charger()

    def charger(self) -> None:
        self.etat.configure(text=t("Lecture des articles dans Clover…"), foreground=TEXTE_DOUX)

        def travail():
            try:
                from .__main__ import charger_config
                from .api_clover import ClientClover

                articles = ClientClover(charger_config(self.racine / "config.toml")).inventaire()
                lignes = [ligne_article(a, self.types) for a in articles]
                self.ugs = {a.get("id"): (a.get("sku") or "").strip() for a in articles}
                self.after(0, lambda: self._charge(lignes, ""))
            except BaseException as exc:  # SystemExit compris (jeton absent)
                texte = str(exc) or exc.__class__.__name__
                self.after(0, lambda: self._charge([], texte))

        threading.Thread(target=travail, daemon=True).start()

    def _charge(self, lignes: list[tuple], erreur: str) -> None:
        if not self.winfo_exists():
            return
        if erreur:
            self.etat.configure(text="✘ " + erreur, foreground=ROUGE)
            return
        from .correspondance import normaliser

        self.lignes = lignes
        self.textes = {id(l): normaliser(" ".join(_texte(v) for v in l)) for l in lignes}  # recherche rapide
        categories = sorted({c.strip() for l in lignes for c in l[8].split(",") if c.strip()}, key=str.casefold)
        self.champ_categorie.configurer_valeurs(categories)
        self.afficher()

    def _gardees(self) -> list[tuple]:
        from .correspondance import normaliser

        texte = normaliser(self.recherche.get())
        mots = texte.split()
        categorie = self.categorie.get().strip().casefold()
        type_prix = self.type_prix.get()
        stock = next((s for s in STOCKS if t(s) == self.stock.get()), STOCKS[0])
        gardees = []
        for l in self.lignes:
            if mots and not all(m in self.textes[id(l)] for m in mots):
                continue
            if categorie and categorie not in [c.strip().casefold() for c in l[8].split(",")]:
                continue
            if type_prix != t(TOUS) and t(l[3]) != type_prix:
                continue
            q = l[7]
            if (stock == STOCKS[1] and not (q is not None and q > 0)) or (stock == STOCKS[2] and q != 0) or (
                    stock == STOCKS[3] and not (q is not None and q < 0)) or (stock == STOCKS[4] and q is not None):
                continue
            gardees.append(l)
        colonne, inverse = self.tri
        vides = {2: Decimal("-1e18"), 7: Decimal("-1e18"), 6: date.min}
        gardees.sort(key=lambda l: (l[colonne] if l[colonne] is not None else vides[colonne]) if colonne in vides
                     else str(l[colonne]).casefold(), reverse=inverse)
        return gardees

    def afficher(self) -> None:
        self.arbre.delete(*self.arbre.get_children())
        gardees = self._gardees()
        for l in gardees:
            self.arbre.insert("", "end", values=tuple(_texte(v) for v in l),
                              tags=("negatif",) if l[7] is not None and l[7] < 0 else ())
        rayer(self.arbre)
        self.etat.configure(text=t("{n} article(s) affiché(s) sur {m}", n=len(gardees), m=len(self.lignes)),
                            foreground=TEXTE_DOUX)

    def trier(self, colonne: int) -> None:
        self.tri = (colonne, not self.tri[1] if self.tri[0] == colonne else False)
        self.afficher()

    def effacer_ugs(self) -> None:
        """Articles dont l'UGS n'est pas une date : liste à cocher, puis UGS vidée dans Clover."""
        from .fenetre_cocher import FenetreACocher
        from .peremption import lire_date

        noms = {l[0]: l[1] for l in self.lignes}
        racine = self.racine

        class Ligne:
            def __init__(self, id_clover, ugs):
                self.id, self.ugs, self.nom = id_clover, ugs, noms.get(id_clover, "")
                self.permis = self.cochee_par_defaut = True
                self.etat = "UGS qui n'est pas une date"

        def lire():
            lignes = [Ligne(i, u) for i, u in sorted(getattr(self, "ugs", {}).items(), key=lambda x: noms.get(x[0], ""))
                      if u and lire_date(u) is None]
            return lignes, t("{n} article(s) Clover ont une UGS qui n'est pas une date (JJ/MM/AAAA).", n=len(lignes))

        def traiter(lignes, progression):
            import csv

            from .__main__ import charger_config
            from .api_clover import ClientClover

            client = ClientClover(charger_config(racine / "config.toml"))
            journal = racine / "donnees" / "journal_ugs_effacees.csv"
            journal.parent.mkdir(parents=True, exist_ok=True)
            nouveau = not journal.exists()
            erreurs = []
            with journal.open("a", newline="", encoding="utf-8-sig") as f:
                ecrivain = csv.writer(f, delimiter=";")
                if nouveau:
                    ecrivain.writerow(["Date", "ID Clover", "Article", "UGS effacée"])
                for n, l in enumerate(lignes, 1):
                    try:
                        client.regler_ugs(l.id, "")
                        ecrivain.writerow([datetime.now().isoformat(timespec="seconds"), l.id, l.nom, l.ugs])
                        self.ugs[l.id] = ""
                    except Exception as exc:
                        erreurs.append(f"{l.nom} : {exc}")
                    progression(n, len(lignes))
            self.after(0, self.charger)
            return t("{n} UGS effacée(s) dans Clover.", n=len(lignes) - len(erreurs)) + (
                "\n\n" + "\n".join(erreurs[:15]) if erreurs else "")

        FenetreACocher(self, t("UGS qui ne sont pas des dates"),
                       t("Ces articles ont dans Clover une UGS qui n'est pas une date de péremption (JJ/MM/AAAA). "
                         "Cochez celles à effacer, puis lancez : l'UGS est vidée dans Clover ; chaque UGS effacée est "
                         "notée dans donnees/journal_ugs_effacees.csv."),
                       [("ID Clover", 130), ("Article", 380), ("UGS actuelle", 220)],
                       lambda l: (l.id, l.nom, l.ugs), lire, traiter, t("Effacer dans Clover"),
                       t("L'UGS de {n} article(s) sera effacée dans Clover.\n\nContinuer ?"))

    def reinitialiser(self) -> None:
        self.recherche.set("")
        self.categorie.set("")
        self.type_prix.set(t(TOUS))
        self.stock.set(t(STOCKS[0]))
        self.afficher()
