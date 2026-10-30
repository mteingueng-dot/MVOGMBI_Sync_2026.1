"""Fenêtres de gestion des ventes, des achats et des stocks (demande du propriétaire du 2026-10-29, comme les menus
de gestion de Sage) : listes lues dans Sage (listes_sage.py) et documents saisis dans l'application (documents.py,
fenetre_saisie.py)."""

from __future__ import annotations

import os
import threading
import tkinter as tk
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from tkinter import messagebox

from . import documents as dc
from .design import FenetreOutil, CARTE, ROUGE, TEXTE_DOUX, VERT_FONCE, Bouton, ChampDate, Rangee, apres_frappe
from .export_tableau import bouton_exporter
from .langues import t


def _config(racine: Path) -> dict:
    import tomllib

    chemin = Path(racine) / "config.toml"
    return tomllib.loads(chemin.read_text(encoding="utf-8")) if chemin.exists() else {}


def lire_sage_dans_un_fil(widget, racine: Path, fonction, fin, etat: tk.Label | None = None,
                          message: str = "Lecture de Sage…", cle: str = "", forcer: bool = False) -> None:
    """Lecture de Sage dans un fil (l'application ouvre Sage elle-même s'il est fermé), puis fin(résultat).
    `cle` : lecture gardée en mémoire (cache_lectures) et réaffichée tout de suite tant qu'elle est fraîche."""
    from . import cache_lectures

    if cle and not forcer:
        deja = cache_lectures.connue(cle)
        if deja is not None:
            widget.after(0, lambda: fin(deja))
            return
    if etat is not None:
        etat.configure(text=t(message), foreground=TEXTE_DOUX)

    def travail():
        try:
            from .__main__ import lire_sage

            config = _config(racine)
            resultat = lire_sage(config, fonction, config.get("sage_import", {}).get("fichier_entreprise"))
            if cle:
                cache_lectures.garder(cle, resultat)
            widget.after(0, lambda: fin(resultat))
        except Exception as exc:
            texte = str(exc)
            widget.after(0, lambda: (etat.configure(text="✘ " + texte, foreground=ROUGE) if etat is not None
                                     else messagebox.showerror("MVOGMBI_Sync", texte, parent=widget)))

    threading.Thread(target=travail, daemon=True).start()


# --------------------------------------------------------------------------------------------- listes Sage
class FenetreListe(FenetreOutil):
    """Liste lue dans Sage : `lecture(base, du, au)` -> (en-têtes, lignes) ; période facultative ; recherche."""

    def __init__(self, parent, racine: Path, titre: str, lecture, periode: bool = False, explication: str = "",
                 largeurs: dict | None = None, genre: str = ""):
        from .page_rapports import tableau_simple

        super().__init__(parent)
        self.racine, self.lecture, self.largeurs, self.genre = Path(racine), lecture, largeurs or {}, genre
        self.entetes, self.lignes, self.visibles = [], [], []
        self.title(t(titre))
        self.configure(background=CARTE, padx=14, pady=10)
        self.transient(parent)
        self.geometry("1150x640")
        barre = Rangee(self)
        barre.pack(fill="x")
        self.du, self.au = tk.StringVar(), tk.StringVar()
        if periode:
            g = barre.ajouter(barre.groupe(), 10)
            self.du.set((date.today() - timedelta(days=30)).isoformat())
            self.au.set(date.today().isoformat())
            tk.Label(g, text=t("Période du"), background=CARTE).pack(side="left", padx=(0, 4))
            ChampDate(g, self.du, fond=CARTE).pack(side="left")
            tk.Label(g, text=t("au"), background=CARTE).pack(side="left", padx=4)
            ChampDate(g, self.au, fond=CARTE).pack(side="left")
        g = barre.ajouter(barre.groupe(), 10)
        tk.Label(g, text=t("Rechercher :"), background=CARTE).pack(side="left", padx=(0, 4))
        self.texte = tk.StringVar()
        champ = tk.Entry(g, textvariable=self.texte, width=24)
        champ.pack(side="left")
        champ.bind("<KeyRelease>", apres_frappe(champ, self.afficher))
        barre.ajouter(Bouton(barre, "🔄  " + t("Actualiser"), lambda: self.charger(forcer=True), fond=CARTE,
                             petit=True), 10)
        for texte, commande, style in (("📂  " + t("Ouvrir"), self.fiche, "secondaire"),
                                       ("➕  " + t("Ajouter"), self.ajouter, "principal"),
                                       ("✎  " + t("Modifier"), self.modifier, "secondaire"),
                                       ("🗑  " + t("Supprimer"), self.supprimer, "danger")):
            barre.ajouter(Bouton(barre, texte, commande, style, fond=CARTE, petit=True))
        self.etat = tk.Label(self, text=t(explication), background=CARTE, foreground=TEXTE_DOUX, anchor="w",
                             justify="left", wraplength=1100)
        self.etat.pack(fill="x", pady=(6, 0))
        self.tableau = tableau_simple(self, hauteur=18)
        self.tableau.bind("<Double-1>", lambda _e: self.fiche())
        self.tableau.tag_configure("total", font=("Segoe UI Semibold", 9), background="#e8f3ea")
        barre.ajouter(bouton_exporter(barre, self.tableau, lambda: self.title()))
        self.charger()

    def charger(self, forcer: bool = False) -> None:
        try:
            du = date.fromisoformat(self.du.get()) if self.du.get() else None
            au = date.fromisoformat(self.au.get()) if self.au.get() else None
        except ValueError:
            self.etat.configure(text="✘ " + t("Dates au format AAAA-MM-JJ."), foreground=ROUGE)
            return

        def fin(resultat):
            self.entetes, self.lignes = resultat[0], resultat[1]
            self.afficher()

        lire_sage_dans_un_fil(self, self.racine, lambda base: self.lecture(base, du, au), fin, self.etat,
                              cle=f"liste:{self.genre}:{du}:{au}" if self.genre else "", forcer=forcer)

    def afficher(self) -> None:
        from .page_rapports import remplir

        texte = self.texte.get().strip().casefold()
        lignes = [l for l in self.lignes if not texte or any(texte in str(v).casefold() for v in l)]
        self.visibles = lignes
        remplir(self.tableau, self.entetes, [[t(v) if isinstance(v, str) and v in TRADUITS else v for v in l]
                                             for l in lignes],
                self.largeurs, lambda i: ("total",) if any(str(v).startswith("Total") for v in lignes[i][:3]) else (),
                decroissant=False)
        self.etat.configure(text=t("{n} ligne(s) affichée(s) sur {m}.", n=len(lignes), m=len(self.lignes)),
                            foreground=TEXTE_DOUX)


    # ------------------------------------------------------------------ actions
    def _ligne(self):
        choix = self.tableau.selection()
        if not choix:
            messagebox.showinfo(self.title(), t("Choisissez une ligne dans la liste."), parent=self)
            return None
        return self.visibles[int(choix[0])]

    def fiche(self) -> None:
        from .fiches import ouvrir_fiche

        ligne = self._ligne()
        if ligne is not None:
            ouvrir_fiche(self, self.racine, self.genre, ligne, self.entetes)

    def ajouter(self) -> None:
        """Création : document saisi dans l'application, ou article (Clover + Sage) ; les fiches de clients et de
        fournisseurs se créent dans Sage (Sage n'accepte pas leur import)."""
        racine = self.nametowidget(".")
        auteur = racine._auteur() if hasattr(racine, "_auteur") else ""
        if self.genre in ("articles", "livre"):
            if hasattr(racine, "ouvrir_creation_article"):
                racine.ouvrir_creation_article()
        elif self.genre == "documents_vente":
            saisir_document(self, self.racine, dc.FACTURE, auteur)
        elif self.genre == "documents_stock":
            saisir_document(self, self.racine, dc.STOCK, auteur)
        elif self.genre == "documents_achat":
            saisir_facture_achat(self, self.racine)
        elif self.genre in ("clients", "fournisseurs"):
            DialogueTiers(self, self.racine, self.genre, apres=lambda: self.charger(forcer=True))

    def modifier(self) -> None:
        ligne = self._ligne()
        if ligne is None:
            return
        messagebox.showinfo(self.title(), t("Les fiches et les documents enregistrés dans Sage se modifient dans "
                                            "Sage. La fiche s'ouvre pour consultation ; les documents saisis dans "
                                            "l'application se modifient dans leur liste (Vente, Articles)."),
                            parent=self)
        self.fiche()

    def supprimer(self) -> None:
        if self._ligne() is None:
            return
        messagebox.showinfo(self.title(), t("Une fiche ou un document de Sage ne se supprime pas d'ici : dans Sage, "
                                            "rendez la fiche inactive, ou corrigez / annulez le document. Les "
                                            "documents saisis dans l'application se suppriment dans leur liste."),
                            parent=self)


def _lecture_articles(racine: Path):
    from . import listes_sage as ls
    from .analyse_articles import categories
    from .couts_sage import correspondance

    def lecture(base, _d, _a):
        liens: dict[str, int] = {}
        try:
            for numero in correspondance(racine).values():
                liens[numero] = liens.get(numero, 0) + 1
        except Exception:  # correspondance absente : colonne vide
            pass
        return ls.articles(base, categories(racine), {n: [f"{k} relié(s)"] for n, k in liens.items()})

    return lecture


def _lecture_tiers(cote: str):
    def fabrique(_racine: Path):
        from . import listes_sage as ls

        return lambda base, _d, _a: ls.tiers(base, cote)

    return fabrique


# listes sans période : lues d'avance au démarrage si Sage répond (cache_lectures.precharger)
LECTURES = {"clients": _lecture_tiers("clients"), "fournisseurs": _lecture_tiers("fournisseurs"),
            "articles": _lecture_articles}


TRADUITS = {"Actif", "Inactif", "Facture", "Encaissement", "Paiement", "Payée comptant", "Note de crédit", "Payée",
            "Ouverte", "Stock", "Service", "Ajustement d'inventaire", "Transfert entre emplacements",
            "Total de la catégorie", "Total général", "Escompte / ajustement", "Dépôt / avance"}


def ouvrir_liste(parent, racine: Path, genre: str):
    """Listes du menu : clients, fournisseurs, documents de vente / d'achat / de stock, articles, livre d'inventaire."""
    from . import listes_sage as ls

    if genre == "clients":
        return FenetreListe(parent, racine, "Liste des clients", LECTURES["clients"](racine),
                            explication="Clients de Sage : montant dû, factures ouvertes, dernière facture. "
                                        "Double-clic : fiche du client.",
                            largeurs={"Client": 280}, genre=genre)
    if genre == "fournisseurs":
        return FenetreListe(parent, racine, "Liste des fournisseurs", LECTURES["fournisseurs"](racine),
                            largeurs={"Fournisseur": 280}, genre=genre,
                            explication="Fournisseurs de Sage. Double-clic : fiche du fournisseur.")
    if genre == "documents_vente":
        return FenetreListe(parent, racine, "Liste des documents de vente",
                            lambda b, d, a: ls.documents(b, "ventes", d, a), periode=True,
                            largeurs={"Client": 220, "Facture": 160}, genre=genre,
                            explication="Factures et encaissements de Sage. Double-clic : détail du document.")
    if genre == "documents_achat":
        return FenetreListe(parent, racine, "Liste des documents d'achat",
                            lambda b, d, a: ls.documents(b, "achats", d, a), periode=True,
                            largeurs={"Fournisseur": 220, "Facture": 160}, genre=genre,
                            explication="Factures, paiements et notes de crédit de Sage. Double-clic : détail.")
    if genre == "documents_stock":
        return FenetreListe(parent, racine, "Liste des documents de stock",
                            lambda b, d, a: ls.documents_stock(b, d, a), periode=True, largeurs={"Source": 160},
                            genre=genre, explication="Ajustements et transferts de Sage. Double-clic : lignes.")
    if genre == "articles":
        return FenetreListe(parent, racine, "Liste des articles", LECTURES["articles"](racine), largeurs={"Description": 280},
                            genre=genre, explication="Articles de Sage avec leur stock, CUMP, valeur, comptes et "
                                                     "lien Clover. Double-clic : fiche de l'article.")
    if genre == "livre":
        from .analyse_articles import categories

        fenetre = FenetreListe(parent, racine, "Livre d'inventaire",
                               lambda b, _d, a: ls.livre_inventaire(b, a or date.today(), categories(racine))[:2],
                               periode=True, largeurs={"Article": 280, "Catégorie": 160}, genre=genre,
                               explication="Quantité à la date « au » (stock actuel moins les mouvements postérieurs) "
                                           "et valeur au CUMP actuel, par catégorie.")
        fenetre.du.set("")
        return fenetre
    raise ValueError(genre)


# --------------------------------------------------------------------------------------------- documents saisis
TITRES = {dc.COMMANDE: "Commandes clients", dc.FACTURE: "Factures de vente saisies", dc.STOCK: "Documents de stock"}


class FenetreDocuments(FenetreOutil):
    def __init__(self, parent, racine: Path, genre: str, auteur: str):
        from .page_rapports import tableau_simple

        super().__init__(parent)
        self.racine, self.genre, self.auteur = Path(racine), genre, auteur
        self.title(t(TITRES[genre]))
        self.configure(background=CARTE, padx=14, pady=10)
        self.transient(parent)
        self.geometry("1100x600")
        barre = Rangee(self)
        barre.pack(fill="x")
        actions = [("📂  " + t("Ouvrir"), lambda: self.modifier(double_clic=True)),
                   ("➕  " + t("Ajouter"), self.nouveau), ("✎  " + t("Modifier"), self.modifier),
                   ("🗑  " + t("Supprimer"), self.supprimer), ("📄  " + t("PDF"), self.pdf)]
        if genre == dc.COMMANDE:
            actions.append(("🧾  " + t("Facturer la commande"), self.facturer))
        if genre == dc.FACTURE:
            actions.append(("⬆  " + t("Importer dans Sage"), self.importer))
        if genre == dc.STOCK:
            actions.append(("⬆  " + t("Passer dans Sage"), self.passer))
        for texte, commande in actions:
            barre.ajouter(Bouton(barre, texte, commande, "danger" if commande == self.supprimer else
                                 "secondaire" if commande in (self.pdf, self.modifier) else "principal", fond=CARTE,
                                 petit=True))
        explications = {
            dc.COMMANDE: "Commandes des clients gardées dans l'application (la fonction « Commandes clients » n'est pas "
                         "activée dans Sage) ; « Facturer la commande » en fait une facture de vente à importer.",
            dc.FACTURE: "Factures de vente saisies à la main : « Importer dans Sage » (Sage fermé) ; vérifiées dans Sage "
                        "après l'import.",
            dc.STOCK: "Entrées et sorties de stock (perte, casse, don, réception sans facture) : « Passer dans Sage » "
                      "(fenêtre Ajustements des Stocks de Sage ; ouvrez Sage sur le fichier de l'entreprise)."}
        self.etat = tk.Label(self, text=t(explications[genre]), background=CARTE, foreground=TEXTE_DOUX, anchor="w",
                             justify="left", wraplength=1050)
        self.etat.pack(fill="x", pady=(6, 0))
        self.tableau = tableau_simple(self, hauteur=16)
        self.tableau.bind("<Double-1>", lambda _e: self.modifier(double_clic=True))
        self.tableau.tag_configure("echec", background="#fde2e4")
        self.tableau.tag_configure("fait", foreground="#7d8b81")
        barre.ajouter(bouton_exporter(barre, self.tableau, lambda: self.title()))
        self.afficher()

    def afficher(self) -> None:
        from .page_rapports import remplir

        from .points_vente import DEPOT_DEFAUT

        self.docs = dc.Registre(self.racine).du_genre(self.genre)
        entetes = ["N°", "Date", "Client" if self.genre != dc.STOCK else "Mouvement", "Lignes", "Sous-total",
                   "Total", "État", "Lien" if self.genre != dc.STOCK else "Dépôt", "Messages"]
        remplir(self.tableau, entetes,
                [[d.numero, d.date, d.tiers if self.genre != dc.STOCK else t(d.sens), len(d.lignes), d.sous_total,
                  d.total, t(d.etat), d.lien if self.genre != dc.STOCK else (d.depot or DEPOT_DEFAUT),
                  " ; ".join(d.messages)] for d in self.docs],
                {"Client": 220, "Messages": 300},
                lambda i: ("echec",) if self.docs[i].etat == dc.ECHEC else (
                    ("fait",) if self.docs[i].etat in (dc.IMPORTEE, dc.PASSE, dc.FACTUREE) else ()), decroissant=False)

    def _doc(self):
        choix = self.tableau.selection()
        if not choix:
            messagebox.showinfo(self.title(), t("Choisissez un document dans la liste."), parent=self)
            return None
        return self.docs[int(choix[0])]

    def nouveau(self) -> None:
        saisir_document(self, self.racine, self.genre, self.auteur, self.afficher)

    def modifier(self, double_clic: bool = False) -> None:
        d = self._doc()
        if not d:
            return
        if not dc.Registre(self.racine).modifiable(d):
            if double_clic:
                self.pdf()  # document déjà dans Sage ou facturé : consultation
            else:
                messagebox.showinfo(self.title(), t("{n} ({e}) ne peut plus être modifié.", n=d.numero, e=t(d.etat)),
                                    parent=self)
            return
        saisir_document(self, self.racine, self.genre, self.auteur, self.afficher, d.numero)

    def supprimer(self) -> None:
        d = self._doc()
        if not d:
            return
        if not messagebox.askyesno(self.title(), t("Supprimer {n} ?", n=d.numero), parent=self):
            return
        try:
            dc.Registre(self.racine).supprimer(d.numero)
        except ValueError as exc:
            messagebox.showerror(self.title(), t(str(exc)), parent=self)
        self.afficher()

    def pdf(self) -> None:
        d = self._doc()
        if not d:
            return
        try:
            os.startfile(dc.ecrire_pdf(self.racine, d))
        except Exception as exc:
            messagebox.showerror(self.title(), str(exc), parent=self)

    def facturer(self) -> None:
        d = self._doc()
        if not d:
            return
        try:
            facture = dc.Registre(self.racine).facturer(d.numero, self.auteur)
        except ValueError as exc:
            messagebox.showerror(self.title(), t(str(exc)), parent=self)
            return
        self.afficher()
        messagebox.showinfo(self.title(), t("Facture {f} créée : importez-la depuis « Vente > Saisir une facture de "
                                            "vente ».", f=facture.numero), parent=self)

    def _lancer(self, travail, question: str) -> None:
        if not messagebox.askyesno(self.title(), question, parent=self):
            return
        self.etat.configure(text=t("Traitement en cours…"), foreground=TEXTE_DOUX)

        def executer():
            try:
                resultat = travail()
                texte = "\n".join(f"{k} : {v}" for k, v in resultat.items()) or t("Rien à faire.")
                self.after(0, lambda: (self.afficher(), self.etat.configure(text=texte, foreground=VERT_FONCE)))
            except Exception as exc:
                texte = str(exc)
                self.after(0, lambda: (self.afficher(), self.etat.configure(text="✘ " + texte, foreground=ROUGE)))

        threading.Thread(target=executer, daemon=True).start()

    def importer(self) -> None:
        d = self._doc()
        if not d:
            return
        if d.etat == dc.IMPORTEE:
            messagebox.showinfo(self.title(), t("{n} est déjà dans Sage.", n=d.numero), parent=self)
            return
        self._lancer(lambda: dc.importer_factures(self.racine, _config(self.racine), [d.numero]),
                     t("Importer la facture {n} ({m}) dans Sage ? Sage doit être fermé.", n=d.numero,
                       m=f"{d.total:,.2f} $".replace(",", " ").replace(".", ",")))

    def passer(self) -> None:
        d = self._doc()
        if not d:
            return
        if d.etat == dc.PASSE:
            messagebox.showinfo(self.title(), t("{n} est déjà dans Sage.", n=d.numero), parent=self)
            return
        self._lancer(lambda: dc.passer_stock(self.racine, _config(self.racine), d.numero),
                     t("Passer le document {n} ({s}, {l} ligne(s)) dans Sage ?", n=d.numero, s=t(d.sens),
                       l=len(d.lignes)))


def saisir_document(parent, racine: Path, genre: str, auteur: str, apres=None, numero: str = "") -> None:
    """Nouveau document (commande client, facture de vente, document de stock), ou modification de `numero`."""
    from .fenetre_saisie import SaisieDocument
    from .inventaire import lire_sage as stocks
    from .points_vente import DEPOT_DEFAUT

    def lecture(base):
        articles = stocks(base)
        clients = [] if genre == dc.STOCK else sorted(
            (r["n"] for r in base.requete("SELECT TRIM(sName) n FROM tcustomr WHERE bInactive = 0") if r["n"]),
            key=str.casefold)
        prix = {}
        if genre != dc.STOCK:  # services aussi vendables ; prix de vente de Sage proposé
            for r in base.requete("SELECT TRIM(sPartCode) n, TRIM(sName) d FROM tinvent WHERE bService = 1"):
                articles.setdefault(r["n"], {"nom": r["d"], "cout": None})
            prix = {r["n"]: Decimal(str(r["p"])) for r in base.requete(
                "SELECT TRIM(i.sPartCode) n, MIN(p.dPrice) p FROM tinvprc p JOIN tinvent i ON i.lId = p.lInventId "
                "WHERE p.dPrice > 0 AND p.lPrcListId = 1 GROUP BY i.sPartCode")}
        return articles, clients, prix

    def fin(resultat):  # lecture gardée en mémoire : les saisies suivantes s'ouvrent tout de suite
        articles, clients, prix = resultat
        initial = None
        if numero:
            d = dc.Registre(racine).document(numero)
            initial = {"tiers": d.tiers, "date": d.date, "remarque": d.remarque, "sens": d.sens,
                       "depot": d.depot or DEPOT_DEFAUT,
                       "lignes": [{"numero_sage": l.numero_sage, "description": l.description,
                                   "quantite": Decimal(l.quantite), "prix": Decimal(l.prix or 0),
                                   "taxable": l.taxable, "taxe": l.taxe} for l in d.lignes]}

        def valider(entete, lignes):
            registre = dc.Registre(racine)
            lignes_doc = [dc.LigneDocument(l["numero_sage"], l["description"], str(l["quantite"]), str(l["prix"]),
                                           l["taxable"], taxe=l.get("taxe", "")) for l in lignes]
            if numero:
                doc = registre.modifier(numero, entete["tiers"], entete["date"], lignes_doc, entete["remarque"],
                                        entete["sens"], entete.get("depot", ""))
            else:
                doc = registre.ajouter(genre, entete["tiers"], entete["date"], lignes_doc, entete["remarque"],
                                       entete["sens"], auteur, entete.get("depot", ""))
            if apres:
                apres()
            return t("{n} enregistré.", n=doc.numero)

        proposes = {n: (a["nom"] or "", a["cout"] if genre == dc.STOCK else prix.get(n)) for n, a in articles.items()}
        titres = {dc.STOCK: "Saisir un document de stock", dc.COMMANDE: "Saisir une commande client",
                  dc.FACTURE: "Saisir une facture de vente"}
        titre = t(titres[genre]) + (f" — {numero}" if numero else "")
        if genre == dc.STOCK:
            SaisieDocument(parent, titre, proposes, valider, libelle_prix="Coût unitaire",
                           sens=[dc.ENTREE, dc.SORTIE], initial=initial, depots=dc.depots(_config(racine)))
        else:
            SaisieDocument(parent, titre, proposes, valider, tiers=clients, taxable=True, initial=initial)

    lire_sage_dans_un_fil(parent, racine, lecture, fin, cle=f"saisie:{genre}")


class DialogueTiers(tk.Toplevel):
    """Nouveau client ou fournisseur créé dans Sage : l'application remplit la fiche de Sage (robot_tiers), dans le
    Sage ouvert sur le fichier de l'entreprise, sinon elle ouvre Sage elle-même ; vérifié dans la base."""

    CREATION = True  # fenêtre de création : reste une fenêtre à part (avec « Fermer »)

    def __init__(self, parent, racine: Path, genre: str, apres=None):
        from tkinter import ttk

        from .robot_tiers import FicheTiers, LIBELLES

        super().__init__(parent)
        self.racine, self.genre, self.apres = Path(racine), genre, apres
        self.title(t("Nouveau client") if genre == "clients" else t("Nouveau fournisseur"))
        self.configure(background=CARTE, padx=16, pady=12)
        self.transient(parent.winfo_toplevel())
        defaut = FicheTiers("")
        self.v: dict[str, tk.StringVar] = {}
        grille = tk.Frame(self, background=CARTE)
        grille.pack(fill="x")
        cles = [c for c in LIBELLES if c != "no_taxe" or genre == "fournisseurs"]
        for i, cle in enumerate(cles):
            rang, colonne = i % 7, (i // 7) * 2
            tk.Label(grille, text=t(LIBELLES[cle]) + (" *" if cle == "nom" else ""), background=CARTE,
                     anchor="w").grid(row=rang, column=colonne, sticky="w", padx=(0 if colonne == 0 else 16, 6), pady=3)
            self.v[cle] = tk.StringVar(value=getattr(defaut, cle))
            ttk.Entry(grille, textvariable=self.v[cle], width=34 if cle in ("nom", "rue1", "rue2", "courriel", "site")
                      else 24).grid(row=rang, column=colonne + 1, sticky="w", pady=3)
        if genre == "fournisseurs":
            tk.Label(self, text=t("N° d'inscription aux taxes : 9 chiffres + RP, RT ou RZ + 4 chiffres "
                                  "(ex. 123456789RT0001), ou vide."), background=CARTE, foreground=TEXTE_DOUX,
                     anchor="w").pack(fill="x", pady=(6, 0))
        self.etat = tk.Label(self, text=t("La fiche est créée dans Sage, avec « utilise mes numéros d'articles » coché "
                                          "(nécessaire aux imports de factures)."), background=CARTE,
                             foreground=TEXTE_DOUX, anchor="w", justify="left", wraplength=640)
        self.etat.pack(fill="x", pady=(8, 0))
        bas = tk.Frame(self, background=CARTE)
        bas.pack(anchor="e", pady=(10, 0))
        Bouton(bas, "✖  " + t("Fermer"), self.destroy, "secondaire", fond=CARTE).pack(side="right")
        self.bouton = Bouton(bas, "✔  " + t("Créer dans Sage"), self.creer, fond=CARTE)
        self.bouton.pack(side="right", padx=8)

    def creer(self) -> None:
        import re

        from .robot_tiers import FicheTiers

        valeurs = {c: " ".join(v.get().split()) for c, v in self.v.items()}
        if not valeurs["nom"]:
            self.etat.configure(text="✘ " + t("Le nom est obligatoire."), foreground=ROUGE)
            return
        if valeurs.get("courriel") and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", valeurs["courriel"]):
            self.etat.configure(text="✘ " + t("Courriel invalide."), foreground=ROUGE)
            return
        if valeurs.get("no_taxe") and not re.fullmatch(r"\d{9}(RP|RT|RZ)\d{4}", valeurs["no_taxe"].replace(" ", "").upper()):
            self.etat.configure(text="✘ " + t("N° d'inscription aux taxes invalide (ex. 123456789RT0001)."),
                                foreground=ROUGE)
            return
        if "no_taxe" in valeurs:
            valeurs["no_taxe"] = valeurs["no_taxe"].replace(" ", "").upper()
        fiche = FicheTiers(**valeurs)
        self.etat.configure(text=t("Création dans Sage… (l'application ouvre Sage elle-même s'il est fermé : environ "
                                   "une minute)"), foreground=TEXTE_DOUX)

        def travail():
            try:
                from .robot_tiers import creer_dans_sage

                r = creer_dans_sage(self.racine, _config(self.racine), self.genre, [fiche])[0]
                texte = (t("« {n} » est créé dans Sage.", n=fiche.nom) if r["cree"] else
                         "✘ " + t("Non créé : {m}", m=" ; ".join(r["messages"])))
                if r["cree"] and not r["mes_numeros"]:
                    texte += " " + t("Cochez « utilise mes numéros d'articles » dans sa fiche de Sage.")
                self.after(0, lambda: self._fin(texte, r["cree"]))
            except Exception as exc:
                message = str(exc)
                self.after(0, lambda: self._fin("✘ " + message, False))

        threading.Thread(target=travail, daemon=True).start()

    def _fin(self, texte: str, cree: bool) -> None:
        if not self.winfo_exists():
            return
        self.etat.configure(text=texte, foreground=VERT_FONCE if cree else ROUGE)
        if cree:
            if self.apres:
                self.apres()
            messagebox.showinfo(self.title(), texte, parent=self)
            self.destroy()


# --------------------------------------------------------------------------------------------- achats saisis
def saisir_facture_achat(parent, racine: Path) -> None:
    """Facture d'achat saisie à la main : ajoutée à « Fournisseur > Factures fournisseurs », d'où elle est importée."""
    from .bons_commande import derniers_achats
    from .fenetre_saisie import SaisieDocument
    from .inventaire import lire_sage as stocks

    def lecture(base):
        achats = derniers_achats(base)
        articles = {n: (a["nom"] or "", achats.get(n, {}).get("prix")) for n, a in stocks(base).items()}
        fournisseurs = sorted((r["n"] for r in base.requete("SELECT TRIM(sName) n FROM tvendor WHERE bInactive = 0")
                               if r["n"]), key=str.casefold)
        return articles, fournisseurs

    def fin(resultat):
        articles, fournisseurs = resultat

        def valider(entete, lignes):
            import hashlib
            from datetime import datetime

            from .fournisseurs import Facture, Ligne, Registre, etat_apres_controle
            if not entete["tiers"]:
                raise ValueError(t("Choisissez le fournisseur."))
            if not entete["remarque"]:
                raise ValueError(t("Le n° de facture du fournisseur est obligatoire."))
            from . import taxes as tx

            lignes_f = [Ligne(l["description"], l["quantite"], l["prix"],
                              (l["quantite"] * l["prix"]).quantize(Decimal("0.01")), numero_sage=l["numero_sage"],
                              description_sage=l["description"], taxable=l["taxable"], confirme=True,
                              taxe=l.get("taxe", "")) for l in lignes]
            sous_total = sum((l.montant for l in lignes_f), Decimal(0))
            montants = [tx.montants(l.montant, tx.code(l)) for l in lignes_f]
            taxes = [sum((m[0] for m in montants), Decimal(0)), sum((m[1] for m in montants), Decimal(0))]
            nom = f"Saisie manuelle {entete['tiers']} {entete['remarque']}"
            facture = Facture(nom, hashlib.sha1(f"{nom}{datetime.now()}".encode()).hexdigest(), entete["tiers"],
                              entete["tiers"], entete["remarque"], entete["date"], lignes_f, sous_total, taxes[0],
                              taxes[1], sous_total + taxes[0] + taxes[1], "Saisie manuelle")
            facture.etat = etat_apres_controle(facture, facture.controles())
            registre = Registre(racine)
            registre.factures.append(facture)
            registre.enregistrer()
            return t("Facture {n} de {f} ajoutée ({e}) : importez-la depuis « Fournisseur > Factures fournisseurs ».",
                     n=facture.numero, f=facture.fournisseur_sage, e=t(facture.etat))

        SaisieDocument(parent, "Saisir une facture d'achat", articles, valider, tiers=fournisseurs,
                       libelle_tiers="Fournisseur", libelle_prix="Prix d'achat", taxable=True,
                       libelle_remarque="N° de facture du fournisseur", action="Ajouter aux factures fournisseurs",
                       remarque_obligatoire=True)

    lire_sage_dans_un_fil(parent, racine, lecture, fin, cle="saisie:achats")


def saisir_bon_commande(parent, racine: Path, apres=None, bon=None) -> None:
    """Bon de commande saisi à la main (fournisseur, articles, prix du dernier achat proposé), PDF créé ; `bon` :
    modification d'un bon pas encore reçu."""
    from . import bons_commande as bc
    from .fenetre_saisie import SaisieDocument
    from .inventaire import lire_sage as stocks

    def lecture(base):
        achats = bc.derniers_achats(base)
        articles = {n: (a["nom"] or "", achats.get(n, {}).get("prix")) for n, a in stocks(base).items()}
        fournisseurs = sorted((r["n"] for r in base.requete("SELECT TRIM(sName) n FROM tvendor WHERE bInactive = 0")
                               if r["n"]), key=str.casefold)
        return articles, fournisseurs

    facteurs = bc.facteurs_dernier_achat(racine)  # unités Sage par unité du fournisseur (dernier achat)

    def fin(resultat):
        articles, fournisseurs = resultat

        def valider(entete, lignes):
            if not entete["tiers"]:
                raise ValueError(t("Choisissez le fournisseur."))
            lignes_bon = [bc.LigneBon(l["numero_sage"], l["description"], str(l["quantite"]), str(l["prix"]),
                                      str((l["quantite"] * l["prix"]).quantize(Decimal("0.01"))),
                                      str(l.get("facteur", 1))) for l in lignes]
            if bon is not None:
                modifie = bc.modifier_bon(racine, bon.numero, entete["tiers"], entete["date"], lignes_bon)
                if apres:
                    apres()
                return t("{n} enregistré.", n=modifie.numero)
            propositions = [bc.Proposition(l["numero_sage"], l["description"], "", Decimal(0), Decimal(0),
                                           l["quantite"], entete["tiers"], l["prix"],
                                           facteur=l.get("facteur", Decimal(1))) for l in lignes]
            bons = bc.creer_bons(racine, propositions, date.fromisoformat(entete["date"]))
            if apres:
                apres()
            if bons and bons[0].pdf:
                os.startfile(bons[0].pdf)
            return t("Bon {n} créé pour {f}.", n=bons[0].numero, f=entete["tiers"])

        initial = None if bon is None else {
            "tiers": bon.fournisseur, "date": bon.date,
            "lignes": [{"numero_sage": l.numero_sage, "description": l.description, "quantite": Decimal(l.quantite),
                        "prix": Decimal(l.prix or 0), "taxable": False, "facteur": Decimal(l.facteur or 1)}
                       for l in bon.lignes]}
        SaisieDocument(parent, t("Saisir une commande fournisseur") + (f" — {bon.numero}" if bon else ""), articles,
                       valider, tiers=fournisseurs, libelle_tiers="Fournisseur", libelle_prix="Prix d'achat",
                       action="Enregistrer" if bon else "Créer le bon de commande", initial=initial,
                       facteurs=lambda fournisseur, numero: facteurs.get((fournisseur, numero)))

    lire_sage_dans_un_fil(parent, racine, lecture, fin, cle="saisie:achats")
