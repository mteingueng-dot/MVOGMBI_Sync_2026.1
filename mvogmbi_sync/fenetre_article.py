"""Fenêtres « Créer un article (Clover et Sage) » et « Comptes Sage par catégorie Clover »."""

from __future__ import annotations

import threading
import tkinter as tk
import tomllib
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from tkinter import messagebox, ttk

from .creation_articles import (AUCUNE_TAXE, TAXES_DEFAUT, TYPES_PRIX, ComptesCategorie, NouvelArticle, TableCategories,
                                choix_taxes, lire_date, prix_vente, prochain_numero)
from .design import FenetreOutil, CARTE, ROUGE, TEXTE_DOUX, VERT_FONCE, Bouton, ChampDate, cadre_tableau, defilement, rayer
from .langues import t


def nombre(texte: str) -> Decimal:
    nettoye = str(texte).replace("$", "").replace(" ", "").replace("\xa0", "").replace(",", ".")
    try:
        return Decimal(nettoye or "0")
    except InvalidOperation:
        raise ValueError(t("Nombre invalide : {v}", v=texte))


def _config(racine: Path) -> dict:
    chemin = Path(racine) / "config.toml"
    return tomllib.loads(chemin.read_text(encoding="utf-8")) if chemin.exists() else {}


def _client_clover(racine: Path):
    from .__main__ import charger_config
    from .api_clover import ClientClover

    return ClientClover(charger_config(Path(racine) / "config.toml"))


class FenetreCreationArticle(tk.Toplevel):
    """Crée l'article dans Sage (fiche de stock) puis dans Clover, et les relie dans la correspondance.

    `au_succes(nouvel_article)` est appelé après une création réussie (ex. : la ligne de facture est reliée).
    """
    CREATION = True  # fenêtre de création : reste une fenêtre à part (avec « Fermer »)


    def __init__(self, parent, racine: Path, nom: str = "", cout: Decimal | None = None, numeros_sage=(),
                 au_succes=None, categorie: str = "", id_clover: str = "", relier: bool = True):
        """`id_clover` : article Clover existant (création dans Sage seulement) ; `relier` : écrire le lien dans le
        fichier de correspondance (la page 5 le fait elle-même)."""
        super().__init__(parent)
        self.racine, self.au_succes = Path(racine), au_succes
        self.id_clover_existant, self.relier = id_clover, relier
        self.numeros_sage = {str(n).strip() for n in numeros_sage}
        self.table = TableCategories(self.racine)
        self.categories: list[dict] = []
        self.taxes: dict[str, list[str] | None] = {TAXES_DEFAUT: None}
        self.title(t("Créer un article dans Clover et Sage"))
        self.configure(background=CARTE, padx=16, pady=12)
        self.transient(parent)
        self.resizable(False, False)
        self.v = {cle: tk.StringVar() for cle in ("nom", "cout", "prix", "type", "unite", "taxes", "categorie", "code",
                                                  "peremption", "stock", "numero", "description", "actif", "produits",
                                                  "cmv", "ecart")}
        self.v["nom"].set(nom)
        self.v["description"].set(nom)
        self.v["cout"].set("" if cout is None else f"{cout:.2f}")
        self.v["type"].set(t(TYPES_PRIX["FIXED"]))
        self.v["taxes"].set(t(TAXES_DEFAUT))
        self.v["stock"].set("0")
        self.prix_saisi = False  # le prix suit le coût (+40 %) tant qu'il n'est pas tapé à la main
        self.v["categorie"].set(categorie)
        self.creer_sage, self.creer_clover = tk.BooleanVar(value=True), tk.BooleanVar(value=not id_clover)
        self._construire()
        self.v["cout"].trace_add("write", lambda *_: self._prix_auto())
        self.v["nom"].trace_add("write", lambda *_: self._description_auto())
        self._prix_auto()
        threading.Thread(target=self._charger, daemon=True).start()

    # ---------------------------------------------------------------- construction
    def _construire(self) -> None:
        def ligne(cadre, rang, libelle, widget, obligatoire=False):
            tk.Label(cadre, text=t(libelle) + (" *" if obligatoire else ""), background=CARTE,
                     font=("Segoe UI", 9)).grid(row=rang, column=0, sticky="w", pady=3, padx=(0, 8))
            widget.grid(row=rang, column=1, sticky="we", pady=3)
            return widget

        clover = tk.LabelFrame(self, text=" Clover ", background=CARTE, padx=10, pady=6, font=("Segoe UI Semibold", 10))
        clover.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        ligne(clover, 0, "Nom", ttk.Entry(clover, textvariable=self.v["nom"], width=38), True)
        ligne(clover, 1, "Prix d'achat (coût)", ttk.Entry(clover, textvariable=self.v["cout"], width=12), True)
        prix = ligne(clover, 2, "Prix de vente (achat + 40 %)", ttk.Entry(clover, textvariable=self.v["prix"], width=12),
                     True)
        prix.bind("<Key>", lambda _e: setattr(self, "prix_saisi", True))
        types = ttk.Frame(clover)
        ttk.Combobox(types, textvariable=self.v["type"], state="readonly", width=12,
                     values=[t(v) for v in TYPES_PRIX.values()]).pack(side="left")
        ttk.Label(types, text=t("Unité")).pack(side="left", padx=(8, 4))
        ttk.Entry(types, textvariable=self.v["unite"], width=8).pack(side="left")
        ligne(clover, 3, "Type de prix", types, True)
        self.liste_taxes = ligne(clover, 4, "Taxes et frais",
                                 ttk.Combobox(clover, textvariable=self.v["taxes"], state="readonly", width=28))
        self.liste_categories = ligne(clover, 5, "Catégorie",
                                      ttk.Combobox(clover, textvariable=self.v["categorie"], state="readonly", width=28),
                                      True)
        self.liste_categories.bind("<<ComboboxSelected>>", lambda _e: self._categorie_choisie())
        ligne(clover, 6, "Code du produit (facultatif)", ttk.Entry(clover, textvariable=self.v["code"], width=20))
        ligne(clover, 7, "UGS = date de péremption", ChampDate(clover, self.v["peremption"], fond=CARTE), True)
        ligne(clover, 8, "Stock", ttk.Entry(clover, textvariable=self.v["stock"], width=10))
        tk.Label(clover, text=t("Couleur : aucune • groupes de modificateurs : aucun"), background=CARTE,
                 foreground=TEXTE_DOUX, font=("Segoe UI", 8)).grid(row=9, column=0, columnspan=2, sticky="w")
        self.case_clover = ttk.Checkbutton(clover, text=t("Créer dans Clover"), variable=self.creer_clover,
                                           style="Carte.TCheckbutton")
        self.case_clover.grid(row=10, column=0, columnspan=2, sticky="w", pady=(6, 0))
        self.creer_clover_stock = self.creer_clover.get()  # choix gardé pour le retour à « Stock »

        sage = tk.LabelFrame(self, text=" Sage 50 ", background=CARTE, padx=10, pady=6, font=("Segoe UI Semibold", 10))
        sage.grid(row=0, column=1, sticky="nsew")
        # stock ou service (demande du propriétaire du 2026-10-29) : un service (n° « S… ») n'a que des comptes de
        # produits (facultatif) et de charges ; un article de stock : actif, produits, CMV, écart
        self.type_sage = tk.StringVar(value="stock")
        types_sage = tk.Frame(sage, background=CARTE)
        for valeur, libelle in (("stock", "Stock"), ("service", "Service")):
            ttk.Radiobutton(types_sage, text=t(libelle), value=valeur, variable=self.type_sage,
                            command=self._type_change).pack(side="left", padx=(0, 12))
        ligne(sage, 0, "Type", types_sage, True)
        ligne(sage, 1, "N° d'article", ttk.Entry(sage, textvariable=self.v["numero"], width=20), True)
        description = ligne(sage, 2, "Description", ttk.Entry(sage, textvariable=self.v["description"], width=34), True)
        description.bind("<Key>", lambda _e: setattr(self, "_description_tapee", True))
        self.lignes_comptes = {}
        for rang, cle in enumerate(("actif", "produits", "cmv", "ecart"), start=3):
            etiquette = tk.Label(sage, background=CARTE, font=("Segoe UI", 9))
            etiquette.grid(row=rang, column=0, sticky="w", pady=3, padx=(0, 8))
            champ = ttk.Entry(sage, textvariable=self.v[cle], width=8)
            champ.grid(row=rang, column=1, sticky="we", pady=3)
            self.lignes_comptes[cle] = (etiquette, champ)
        self.aide_comptes = tk.Label(sage, background=CARTE, foreground=TEXTE_DOUX, font=("Segoe UI", 8),
                                     wraplength=260, justify="left")
        self.aide_comptes.grid(row=7, column=0, columnspan=2, sticky="w")
        self.bouton_table = Bouton(sage, t("Comptes par catégorie…"), self.ouvrir_table, "secondaire", fond=CARTE,
                                   petit=True)
        self.bouton_table.grid(row=8, column=0, columnspan=2, sticky="w", pady=4)
        self._type_change(initial=True)
        ttk.Checkbutton(sage, text=t("Créer dans Sage"), variable=self.creer_sage,
                        style="Carte.TCheckbutton").grid(row=10, column=0, columnspan=2, sticky="w", pady=(6, 0))

        self.etat = tk.Label(self, text=t("Lecture des catégories et des taxes Clover…"), background=CARTE,
                             foreground=TEXTE_DOUX, anchor="w", justify="left", wraplength=720)
        self.etat.grid(row=1, column=0, columnspan=2, sticky="we", pady=(10, 4))
        boutons = tk.Frame(self, background=CARTE)
        boutons.grid(row=2, column=0, columnspan=2, sticky="e")
        Bouton(boutons, "✖  " + t("Fermer"), self.destroy, "secondaire", fond=CARTE).pack(side="right", padx=(8, 0))
        self.bouton_creer = Bouton(boutons, "🆕  " + t("Créer l'article"), self.creer, fond=CARTE)
        self.bouton_creer.pack(side="right")

    def _type_change(self, initial: bool = False) -> None:
        """Libellés et champs des comptes selon le type ; n° proposé : « S » + suivant libre pour un service."""
        service = self.type_sage.get() == "service"
        libelles = ({"produits": "Compte de produits (4xxx, facultatif)", "cmv": "Compte de charges (5xxx) *"}
                    if service else {"actif": "Compte d'actif (15xx) *", "produits": "Compte de produits (40xx) *",
                                     "cmv": "Compte CMV (50xx) *", "ecart": "Compte d'écart"})
        for cle, (etiquette, champ) in self.lignes_comptes.items():
            if cle in libelles:
                etiquette.configure(text=t(libelles[cle].rstrip(" *")) + (" *" if libelles[cle].endswith("*") else ""))
                etiquette.grid()
                champ.grid()
            else:
                etiquette.grid_remove()
                champ.grid_remove()
        self.aide_comptes.configure(text=t("Service : créé dans Sage seulement, n° commençant par S ; comptes de produits "
                                           "et de charges seulement.")
                                    if service else t("Comptes et préfixe du n° viennent de la catégorie Clover."))
        if service:
            # règle du propriétaire (2026-10-30) : un service se crée seulement dans Sage, jamais dans Clover
            if hasattr(self, "case_clover"):
                if "disabled" not in self.case_clover.state():
                    self.creer_clover_stock = self.creer_clover.get()
                self.creer_clover.set(False)
                self.case_clover.state(["disabled"])
            self.bouton_table.grid_remove()
            for cle in ("actif", "ecart", "produits", "cmv"):
                self.v[cle].set("")
            self.v["numero"].set(prochain_numero(self.numeros_sage, "S"))
        else:
            if hasattr(self, "case_clover") and "disabled" in self.case_clover.state():
                self.case_clover.state(["!disabled"])
                self.creer_clover.set(self.creer_clover_stock)
            self.bouton_table.grid()
            if not initial:
                self._categorie_choisie()

    # ---------------------------------------------------------------- valeurs automatiques
    def _prix_auto(self) -> None:
        if self.prix_saisi:
            return
        try:
            self.v["prix"].set(f"{prix_vente(nombre(self.v['cout'].get())):.2f}" if self.v["cout"].get().strip() else "")
        except ValueError:
            pass

    def _description_auto(self) -> None:
        if not getattr(self, "_description_tapee", False):
            self.v["description"].set(self.v["nom"].get())

    def _categorie_choisie(self) -> None:
        if getattr(self, "type_sage", None) is not None and self.type_sage.get() == "service":
            return  # un service garde ses comptes de produits et de charges
        comptes = self.table.pour(self.v["categorie"].get())
        for cle in ("actif", "produits", "cmv", "ecart"):
            self.v[cle].set(getattr(comptes, cle) if comptes else "")
        prefixe = comptes.prefixe if comptes else "C"
        self.v["numero"].set(prochain_numero(self.numeros_sage, prefixe))
        if not comptes:
            self.etat.configure(text=t("Catégorie sans comptes Sage : renseignez-la dans « Comptes par catégorie… »."),
                                foreground=ROUGE)

    def _charger(self) -> None:
        try:
            client = _client_clover(self.racine)
            categories, taux = client.categories(), client.taux_taxes()
            if any(c["name"] not in self.table.lignes for c in categories):
                try:  # catégories sans comptes : proposées une fois à partir des articles Sage déjà reliés
                    table = TableCategories(self.racine)
                    if table.completer(proposer_depuis_sage(self.racine)):
                        table.enregistrer()
                        self.table = table
                except Exception:
                    pass  # Sage illisible : la table se remplit à la main (« Comptes par catégorie… »)
            self.after(0, lambda: self._fin_chargement(categories, taux, ""))
        except Exception as exc:
            message = str(exc)
            self.after(0, lambda: self._fin_chargement([], [], message))

    def _fin_chargement(self, categories, taux, erreur: str) -> None:
        if not self.winfo_exists():
            return
        self.categories = categories
        self.taxes = choix_taxes(taux) if taux else {TAXES_DEFAUT: None}
        self.liste_taxes.configure(values=[t(k) if k in (TAXES_DEFAUT, AUCUNE_TAXE) else k for k in self.taxes])
        self.liste_categories.configure(values=[c["name"] for c in categories])
        if self.v["categorie"].get() and not self.v["numero"].get():
            self._categorie_choisie()
        self.etat.configure(text=("✘ " + t("Clover illisible : {e}", e=erreur)) if erreur else
                            t("Champs * obligatoires. Prix de vente = prix d'achat + 40 % (modifiable)."),
                            foreground=ROUGE if erreur else TEXTE_DOUX)

    def ouvrir_table(self) -> None:
        """Fenêtre à part : choisir (ou compléter) une catégorie puis « Valider la sélection » remplit l'article
        (demande du propriétaire du 2026-10-29)."""
        FenetreCategories(self, self.racine, [c["name"] for c in self.categories],
                          au_retour=lambda: (setattr(self, "table", TableCategories(self.racine)),
                                             self._categorie_choisie() if self.v["categorie"].get() else None),
                          selection=self.categorie_selectionnee, actuelle=self.v["categorie"].get())

    def categorie_selectionnee(self, nom: str) -> None:
        self.table = TableCategories(self.racine)
        self.v["categorie"].set(nom)
        self._categorie_choisie()
        if self.table.pour(nom):
            self.etat.configure(text="✔ " + t("Comptes de « {n} » repris.", n=nom), foreground=VERT_FONCE)

    # ---------------------------------------------------------------- création
    def article(self) -> NouvelArticle:
        type_prix = next((k for k, v in TYPES_PRIX.items() if t(v) == self.v["type"].get()), "FIXED")
        taxes_libelle = self.v["taxes"].get()
        taxes = next((v for k, v in self.taxes.items() if taxes_libelle in (k, t(k))), None)
        categorie = self.v["categorie"].get()
        comptes = ComptesCategorie(categorie, "", *(self.v[c].get().strip() for c in ("actif", "produits", "cmv", "ecart")))
        return NouvelArticle(
            nom=self.v["nom"].get().strip(), cout=nombre(self.v["cout"].get()), prix=nombre(self.v["prix"].get()),
            peremption=lire_date(self.v["peremption"].get()), categorie=categorie,
            id_categorie=next((c["id"] for c in self.categories if c["name"] == categorie), ""), type_prix=type_prix,
            unite=self.v["unite"].get().strip(), taxes=taxes, code=self.v["code"].get().strip(),
            stock=nombre(self.v["stock"].get()), numero_sage=self.v["numero"].get().strip(),
            description_sage=self.v["description"].get().strip(), comptes=comptes,
            creer_sage=self.creer_sage.get(), creer_clover=self.creer_clover.get(),
            id_clover="" if self.creer_clover.get() else self.id_clover_existant,
            service=self.type_sage.get() == "service", compte_charges=self.v["cmv"].get().strip(),
            compte_produits=self.v["produits"].get().strip())

    def creer(self) -> None:
        if getattr(self, "_en_cours", False):
            return
        try:
            a = self.article()
        except ValueError as exc:
            messagebox.showerror(self.title(), str(exc), parent=self)
            return
        if a.peremption and a.peremption < date.today():
            if not messagebox.askyesno(self.title(), t("La date de péremption est passée. Créer quand même ?"), parent=self):
                return
        problemes = a.problemes(self.numeros_sage)
        if not (a.creer_sage or a.creer_clover):
            problemes.append(t("cochez « Créer dans Clover » ou « Créer dans Sage »"))
        if problemes:
            messagebox.showwarning(self.title(), t("À corriger :") + "\n  • " + "\n  • ".join(problemes), parent=self)
            return
        self.etat.configure(text=t("Création en cours (Sage puis Clover)…"), foreground=TEXTE_DOUX)
        self._en_cours = True
        threading.Thread(target=self._travail, args=(a,), daemon=True).start()

    def _travail(self, a: NouvelArticle) -> None:
        from .creation_articles import creer_dans_clover, creer_dans_sage, noter, relier_correspondance

        etapes, self._sage_fait = [], False
        try:
            if a.creer_sage:
                (r,) = creer_dans_sage(self.racine, _config(self.racine), [a.article_sage()])
                if not r["cree"]:
                    raise RuntimeError(t("Sage : article non créé — {m}", m=" ; ".join(m for m in r["messages"] if m)))
                etapes.append(t("Sage : article {n} créé", n=a.numero_sage))
                self._sage_fait = True
            if a.creer_clover:
                creer_dans_clover(_client_clover(self.racine), a)
                etapes.append(t("Clover : article créé"))
            if self.relier and a.id_clover and a.numero_sage:
                relier_correspondance(self.racine / "donnees" / "correspondance_articles.xlsx", a)
                etapes.append(t("correspondance : reliés (Confirmé)"))
            noter(self.racine, a, " ; ".join(etapes))
            self.after(0, lambda: self._fin(a, etapes, ""))
        except Exception as exc:
            noter(self.racine, a, " ; ".join(etapes + [f"ERREUR : {exc}"]))
            message = str(exc)
            self.after(0, lambda: self._fin(a, etapes, message))

    def _fin(self, a: NouvelArticle, etapes: list[str], erreur: str) -> None:
        texte = "\n".join(["✔ " + e for e in etapes] + (["✘ " + erreur] if erreur else []))
        self._en_cours = False
        if erreur:
            if self._sage_fait:  # article déjà dans Sage : un nouvel essai ne crée plus que dans Clover
                self.creer_sage.set(False)
                self.numeros_sage.add(a.numero_sage)
            if self.winfo_exists():
                self.etat.configure(text=texte, foreground=ROUGE)
            return
        if a.numero_sage:
            self.numeros_sage.add(a.numero_sage)
        if self.au_succes:
            self.au_succes(a)
        messagebox.showinfo(self.title(), texte, parent=self.master)
        self.destroy()


def proposer_depuis_sage(racine: Path) -> dict:
    from .__main__ import lire_sage
    from .correspondance import lire_correspondances
    from .creation_articles import proposer_table

    config = _config(racine)
    lignes = lire_sage(config, lambda b: b.requete(
        "SELECT sPartCode, lAcNAsset, lAcNRev, lAcNExp, lAcNVar FROM tinvent WHERE bService = 0"),
        config.get("sage_import", {}).get("fichier_entreprise"))
    return proposer_table(lire_correspondances(Path(racine) / "donnees" / "correspondance_articles.xlsx"), lignes)


class FenetreCategories(FenetreOutil):
    """Table « catégorie Clover -> préfixe du n° Sage et comptes Sage » (actif 15xx, produits 40xx, CMV 50xx, écart)."""

    COLONNES = (("categorie", "Catégorie Clover", 200), ("prefixe", "Préfixe n° Sage", 90), ("actif", "Actif", 70),
                ("produits", "Produits", 70), ("cmv", "CMV", 70), ("ecart", "Écart", 70))

    def __init__(self, parent, racine: Path, categories_clover=(), au_retour=None, selection=None, actuelle: str = ""):
        """selection : fonction(nom de catégorie) appelée par « Valider la sélection » ; la table s'ouvre alors
        dans une fenêtre à part, au-dessus de la fenêtre de création."""
        super().__init__(parent, a_part=selection is not None)
        self.racine, self.au_retour, self.selection = Path(racine), au_retour, selection
        self.table = TableCategories(self.racine)
        for nom in categories_clover:
            self.table.lignes.setdefault(nom, ComptesCategorie(nom))
        self.title(t("Comptes Sage par catégorie Clover"))
        self.configure(background=CARTE, padx=14, pady=10)
        self.transient(parent)
        cadre = cadre_tableau(self)
        cadre.pack(fill="both", expand=True)
        self.arbre = ttk.Treeview(cadre, columns=[c[0] for c in self.COLONNES], show="headings", height=14,
                                  selectmode="browse")
        for cle, titre, largeur in self.COLONNES:
            self.arbre.heading(cle, text=t(titre))
            self.arbre.column(cle, width=largeur, anchor="w")
        self.arbre.tag_configure("incomplet", background="#fde2e4")
        self.arbre.pack(side="left", fill="both", expand=True)
        defilement(self.arbre)
        self.arbre.bind("<<TreeviewSelect>>", lambda _e: self.choisir())
        edition = tk.Frame(self, background=CARTE)
        edition.pack(fill="x", pady=8)
        self.v = {cle: tk.StringVar() for cle, _, _ in self.COLONNES}
        tk.Label(edition, textvariable=self.v["categorie"], background=CARTE, font=("Segoe UI Semibold", 10),
                 width=24, anchor="w").pack(side="left")
        for cle, titre, _ in self.COLONNES[1:]:
            tk.Label(edition, text=t(titre), background=CARTE, font=("Segoe UI", 9)).pack(side="left", padx=(8, 2))
            ttk.Entry(edition, textvariable=self.v[cle], width=7).pack(side="left")
        Bouton(edition, t("Appliquer"), self.appliquer, "secondaire", fond=CARTE, petit=True).pack(side="left", padx=8)
        Bouton(edition, "➕", self.ajouter, "secondaire", fond=CARTE, petit=True, largeur=34).pack(side="left")
        Bouton(edition, "🗑", self.supprimer, "danger", fond=CARTE, petit=True, largeur=34).pack(side="left", padx=4)
        self.etat = tk.Label(self, text=t("Règle : actif 15xx -> produits 40xx / CMV 50xx ; écart = CMV."),
                             background=CARTE, foreground=TEXTE_DOUX, anchor="w")
        self.etat.pack(fill="x")
        boutons = tk.Frame(self, background=CARTE)
        boutons.pack(fill="x", pady=(8, 0))
        Bouton(boutons, t("Proposer depuis Sage"), self.proposer, "secondaire", fond=CARTE).pack(side="left")
        Bouton(boutons, "🔎  " + t("Articles Sage à corriger…"), self.verifier_articles, "secondaire",
               fond=CARTE).pack(side="left", padx=8)
        if selection:
            Bouton(boutons, "✔  " + t("Valider la sélection"), self.valider, fond=CARTE).pack(side="right")
            Bouton(boutons, "✖  " + t("Fermer"), self.destroy, "secondaire", fond=CARTE).pack(side="right", padx=8)
            self.arbre.bind("<Double-1>", lambda _e: self.valider())
            self.etat.configure(text=t("Choisissez la catégorie de l'article (double-clic ou « Valider la "
                                       "sélection »). Comptes modifiables : « Appliquer » avant de valider."))
        else:
            Bouton(boutons, t("Enregistrer"), self.enregistrer, fond=CARTE).pack(side="right")
        self.afficher()
        if actuelle in self.table.lignes:
            self.arbre.selection_set(actuelle)
            self.arbre.see(actuelle)
        if selection:
            self.geometry("820x560")
            self.grab_set()

    def afficher(self) -> None:
        self.arbre.delete(*self.arbre.get_children())
        for nom, c in sorted(self.table.lignes.items(), key=lambda x: x[0].lower()):
            self.arbre.insert("", "end", iid=nom, values=(nom, c.prefixe, c.actif, c.produits, c.cmv, c.ecart),
                              tags=("incomplet",) if c.problemes() else ())
        rayer(self.arbre)

    def choisir(self) -> None:
        choix = self.arbre.selection()
        if choix:
            c = self.table.lignes[choix[0]]
            for cle in self.v:
                self.v[cle].set(getattr(c, cle))

    def appliquer(self) -> None:
        nom = self.v["categorie"].get()
        if nom not in self.table.lignes:
            return
        c = ComptesCategorie(nom, *(self.v[cle].get().strip() for cle, _, _ in self.COLONNES[1:]))
        self.table.lignes[nom] = c
        self.afficher()
        self.arbre.selection_set(nom)
        problemes = c.problemes()
        self.etat.configure(text=("⚠ " + " ; ".join(problemes)) if problemes else "✔ " + nom,
                            foreground=ROUGE if problemes else VERT_FONCE)

    def ajouter(self) -> None:
        """Nouvelle ligne : catégorie (nom exact de la catégorie Clover), puis ses comptes et « Appliquer »."""
        from tkinter import simpledialog

        nom = simpledialog.askstring(self.title(), t("Nom de la catégorie Clover :"), parent=self)
        nom = " ".join((nom or "").split())
        if not nom:
            return
        if nom in self.table.lignes:
            self.etat.configure(text=t("« {n} » existe déjà.", n=nom), foreground=ROUGE)
        else:
            self.table.lignes[nom] = ComptesCategorie(nom)
            self.afficher()
        self.arbre.selection_set(nom)
        self.arbre.see(nom)
        self.etat.configure(text=t("Complétez les comptes de « {n} », puis « Appliquer » et « Enregistrer ».", n=nom),
                            foreground=VERT_FONCE)

    def supprimer(self) -> None:
        choix = self.arbre.selection()
        if not choix:
            return
        if messagebox.askyesno(self.title(), t("Retirer la catégorie « {n} » de la table ?", n=choix[0]), parent=self):
            del self.table.lignes[choix[0]]
            self.afficher()

    def proposer(self) -> None:
        """Complète les catégories sans comptes à partir des articles Sage déjà reliés (comptes les plus fréquents)."""
        self.etat.configure(text=t("Lecture des articles Sage…"), foreground=TEXTE_DOUX)

        def travail():
            try:
                propositions = proposer_depuis_sage(self.racine)
                self.after(0, lambda: self._fin_proposition(propositions, ""))
            except Exception as exc:
                message = str(exc)
                self.after(0, lambda: self._fin_proposition({}, message))

        threading.Thread(target=travail, daemon=True).start()

    def _fin_proposition(self, propositions: dict, erreur: str) -> None:
        if erreur:
            self.etat.configure(text="✘ " + erreur, foreground=ROUGE)
            return
        n = 0
        for nom, c in propositions.items():
            actuel = self.table.lignes.get(nom)
            if actuel is None or actuel.problemes():  # jamais une ligne déjà complète
                self.table.lignes[nom] = c
                n += 1
        self.afficher()
        self.etat.configure(text=t("{n} catégorie(s) proposée(s) : vérifiez puis « Enregistrer ».", n=n),
                            foreground=VERT_FONCE)

    def verifier_articles(self) -> None:
        """Articles Sage dont les comptes ne suivent pas cette table (table enregistrée d'abord)."""
        from .fenetre_couts import FenetreComptesSage

        self.table.enregistrer()
        FenetreComptesSage(self, self.racine)

    def valider(self) -> None:
        """Table enregistrée, catégorie choisie renvoyée à la fenêtre de création ; refusé si ses comptes sont
        incomplets."""
        choix = self.arbre.selection()
        if not choix:
            self.etat.configure(text=t("Choisissez une catégorie dans la liste."), foreground=ROUGE)
            return
        problemes = self.table.lignes[choix[0]].problemes()
        if problemes:
            self.etat.configure(text="⚠ " + " ; ".join(problemes), foreground=ROUGE)
            return
        self.table.enregistrer()
        nom, selection = choix[0], self.selection
        self.destroy()
        selection(nom)

    def enregistrer(self) -> None:
        self.table.enregistrer()
        if self.au_retour:
            self.au_retour()
        self.destroy()
