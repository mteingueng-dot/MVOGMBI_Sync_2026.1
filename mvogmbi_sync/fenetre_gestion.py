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
from .design import CARTE, ROUGE, TEXTE_DOUX, VERT_FONCE, Bouton, ChampDate, Rangee, apres_frappe
from .export_tableau import bouton_exporter
from .langues import t


def _config(racine: Path) -> dict:
    import tomllib

    chemin = Path(racine) / "config.toml"
    return tomllib.loads(chemin.read_text(encoding="utf-8")) if chemin.exists() else {}


def lire_sage_dans_un_fil(widget, racine: Path, fonction, fin, etat: tk.Label | None = None,
                          message: str = "Lecture de Sage…") -> None:
    """Lecture de Sage dans un fil (l'application ouvre Sage elle-même s'il est fermé), puis fin(résultat)."""
    if etat is not None:
        etat.configure(text=t(message), foreground=TEXTE_DOUX)

    def travail():
        try:
            from .__main__ import lire_sage

            config = _config(racine)
            resultat = lire_sage(config, fonction, config.get("sage_import", {}).get("fichier_entreprise"))
            widget.after(0, lambda: fin(resultat))
        except Exception as exc:
            texte = str(exc)
            widget.after(0, lambda: (etat.configure(text="✘ " + texte, foreground=ROUGE) if etat is not None
                                     else messagebox.showerror("MVOGMBI_Sync", texte, parent=widget)))

    threading.Thread(target=travail, daemon=True).start()


# --------------------------------------------------------------------------------------------- listes Sage
class FenetreListe(tk.Toplevel):
    """Liste lue dans Sage : `lecture(base, du, au)` -> (en-têtes, lignes) ; période facultative ; recherche."""

    def __init__(self, parent, racine: Path, titre: str, lecture, periode: bool = False, explication: str = "",
                 largeurs: dict | None = None):
        from .page_rapports import tableau_simple

        super().__init__(parent)
        self.racine, self.lecture, self.largeurs = Path(racine), lecture, largeurs or {}
        self.entetes, self.lignes = [], []
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
        barre.ajouter(Bouton(barre, "🔄  " + t("Actualiser"), self.charger, fond=CARTE, petit=True), 10)
        self.etat = tk.Label(self, text=t(explication), background=CARTE, foreground=TEXTE_DOUX, anchor="w",
                             justify="left", wraplength=1100)
        self.etat.pack(fill="x", pady=(6, 0))
        self.tableau = tableau_simple(self, hauteur=18)
        self.tableau.tag_configure("total", font=("Segoe UI Semibold", 9), background="#e8f3ea")
        barre.ajouter(bouton_exporter(barre, self.tableau, lambda: self.title()))
        self.charger()

    def charger(self) -> None:
        try:
            du = date.fromisoformat(self.du.get()) if self.du.get() else None
            au = date.fromisoformat(self.au.get()) if self.au.get() else None
        except ValueError:
            self.etat.configure(text="✘ " + t("Dates au format AAAA-MM-JJ."), foreground=ROUGE)
            return

        def fin(resultat):
            self.entetes, self.lignes = resultat[0], resultat[1]
            self.afficher()

        lire_sage_dans_un_fil(self, self.racine, lambda base: self.lecture(base, du, au), fin, self.etat)

    def afficher(self) -> None:
        from .page_rapports import remplir

        texte = self.texte.get().strip().casefold()
        lignes = [l for l in self.lignes if not texte or any(texte in str(v).casefold() for v in l)]
        remplir(self.tableau, self.entetes, [[t(v) if isinstance(v, str) and v in TRADUITS else v for v in l]
                                             for l in lignes],
                self.largeurs, lambda i: ("total",) if any(str(v).startswith("Total") for v in lignes[i][:3]) else (),
                decroissant=False)
        self.etat.configure(text=t("{n} ligne(s) affichée(s) sur {m}.", n=len(lignes), m=len(self.lignes)),
                            foreground=TEXTE_DOUX)


TRADUITS = {"Actif", "Inactif", "Facture", "Encaissement", "Paiement", "Payée comptant", "Note de crédit", "Payée",
            "Ouverte", "Stock", "Service", "Ajustement d'inventaire", "Transfert entre emplacements",
            "Total de la catégorie", "Total général", "Escompte / ajustement", "Dépôt / avance"}


def ouvrir_liste(parent, racine: Path, genre: str):
    """Listes du menu : clients, fournisseurs, documents de vente / d'achat / de stock, articles, livre d'inventaire."""
    from . import listes_sage as ls

    if genre == "clients":
        return FenetreListe(parent, racine, "Liste des clients", lambda b, _d, _a: ls.tiers(b, "clients"),
                            explication="Clients de Sage : solde dû, factures ouvertes, dernière facture.",
                            largeurs={"Client": 280})
    if genre == "fournisseurs":
        return FenetreListe(parent, racine, "Liste des fournisseurs", lambda b, _d, _a: ls.tiers(b, "fournisseurs"),
                            largeurs={"Fournisseur": 280})
    if genre == "documents_vente":
        return FenetreListe(parent, racine, "Liste des documents de vente",
                            lambda b, d, a: ls.documents(b, "ventes", d, a), periode=True,
                            largeurs={"Client": 220, "Facture": 160})
    if genre == "documents_achat":
        return FenetreListe(parent, racine, "Liste des documents d'achat",
                            lambda b, d, a: ls.documents(b, "achats", d, a), periode=True,
                            largeurs={"Fournisseur": 220, "Facture": 160})
    if genre == "documents_stock":
        return FenetreListe(parent, racine, "Liste des documents de stock",
                            lambda b, d, a: ls.documents_stock(b, d, a), periode=True, largeurs={"Source": 160})
    if genre == "articles":
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

        return FenetreListe(parent, racine, "Liste des articles", lecture, largeurs={"Description": 280},
                            explication="Articles de Sage avec leur stock, CUMP, valeur, comptes et lien Clover.")
    if genre == "livre":
        from .analyse_articles import categories

        fenetre = FenetreListe(parent, racine, "Livre d'inventaire",
                               lambda b, _d, a: ls.livre_inventaire(b, a or date.today(), categories(racine))[:2],
                               periode=True, largeurs={"Article": 280, "Catégorie": 160},
                               explication="Quantité à la date « au » (stock actuel moins les mouvements postérieurs) "
                                           "et valeur au CUMP actuel, par catégorie.")
        fenetre.du.set("")
        return fenetre
    raise ValueError(genre)


# --------------------------------------------------------------------------------------------- documents saisis
TITRES = {dc.COMMANDE: "Commandes clients", dc.FACTURE: "Factures de vente saisies", dc.STOCK: "Documents de stock"}


class FenetreDocuments(tk.Toplevel):
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
        actions = [("➕  " + t("Nouveau…"), self.nouveau), ("📄  " + t("PDF"), self.pdf)]
        if genre == dc.COMMANDE:
            actions.append(("🧾  " + t("Facturer la commande"), self.facturer))
        if genre == dc.FACTURE:
            actions.append(("⬆  " + t("Importer dans Sage"), self.importer))
        if genre == dc.STOCK:
            actions.append(("⬆  " + t("Passer dans Sage"), self.passer))
        for texte, commande in actions:
            barre.ajouter(Bouton(barre, texte, commande, "secondaire" if "PDF" in texte else "principal", fond=CARTE,
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
        self.tableau.tag_configure("echec", background="#fde2e4")
        self.tableau.tag_configure("fait", foreground="#7d8b81")
        barre.ajouter(bouton_exporter(barre, self.tableau, lambda: self.title()))
        self.afficher()

    def afficher(self) -> None:
        from .page_rapports import remplir

        self.docs = dc.Registre(self.racine).du_genre(self.genre)
        entetes = ["N°", "Date", "Client" if self.genre != dc.STOCK else "Mouvement", "Lignes", "Sous-total",
                   "Total", "État", "Lien", "Messages"]
        remplir(self.tableau, entetes,
                [[d.numero, d.date, d.tiers if self.genre != dc.STOCK else t(d.sens), len(d.lignes), d.sous_total,
                  d.total, t(d.etat), d.lien, " ; ".join(d.messages)] for d in self.docs],
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
        from .fenetre_saisie import SaisieDocument
        from .inventaire import lire_sage as stocks

        genre = self.genre

        def lecture(base):
            articles = stocks(base)
            clients = [] if genre == dc.STOCK else sorted(
                (r["n"] for r in base.requete("SELECT TRIM(sName) n FROM tcustomr WHERE bInactive = 0") if r["n"]),
                key=str.casefold)
            if genre != dc.STOCK:  # services aussi vendables
                for r in base.requete("SELECT TRIM(sPartCode) n, TRIM(sName) d FROM tinvent WHERE bService = 1"):
                    articles.setdefault(r["n"], {"nom": r["d"], "cout": None})
            return articles, clients

        def fin(resultat):
            articles, clients = resultat

            def valider(entete, lignes):
                registre = dc.Registre(self.racine)
                doc = registre.ajouter(genre, entete["tiers"], entete["date"],
                                       [dc.LigneDocument(l["numero_sage"], l["description"], str(l["quantite"]),
                                                         str(l["prix"]), l["taxable"]) for l in lignes],
                                       entete["remarque"], entete["sens"], self.auteur)
                self.afficher()
                return t("{n} enregistré.", n=doc.numero)

            proposes = {n: (a["nom"] or "", a["cout"] if genre == dc.STOCK else None) for n, a in articles.items()}
            if genre == dc.STOCK:
                SaisieDocument(self, "Saisir un document de stock", proposes, valider, libelle_prix="Coût unitaire",
                               sens=[dc.ENTREE, dc.SORTIE])
            else:
                SaisieDocument(self, "Saisir une commande client" if genre == dc.COMMANDE else
                               "Saisir une facture de vente", proposes, valider, tiers=clients, taxable=True)

        lire_sage_dans_un_fil(self, self.racine, lecture, fin, self.etat, "Lecture des clients et articles de Sage…")

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
            from .import_sage import TAXES_GQ

            if not entete["tiers"]:
                raise ValueError(t("Choisissez le fournisseur."))
            if not entete["remarque"]:
                raise ValueError(t("Le n° de facture du fournisseur est obligatoire."))
            lignes_f = [Ligne(l["description"], l["quantite"], l["prix"],
                              (l["quantite"] * l["prix"]).quantize(Decimal("0.01")), numero_sage=l["numero_sage"],
                              description_sage=l["description"], taxable=l["taxable"], confirme=True)
                        for l in lignes]
            sous_total = sum((l.montant for l in lignes_f), Decimal(0))
            taxes = [sum(((l.montant * taux).quantize(Decimal("0.01")) for l in lignes_f if l.taxable), Decimal(0))
                     for _n, _a, taux in TAXES_GQ]
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
                       libelle_remarque="N° de facture du fournisseur", action="Ajouter aux factures fournisseurs")

    lire_sage_dans_un_fil(parent, racine, lecture, fin)


def saisir_bon_commande(parent, racine: Path, apres=None) -> None:
    """Bon de commande saisi à la main (fournisseur, articles, prix du dernier achat proposé), PDF créé."""
    from . import bons_commande as bc
    from .fenetre_saisie import SaisieDocument
    from .inventaire import lire_sage as stocks

    def lecture(base):
        achats = bc.derniers_achats(base)
        articles = {n: (a["nom"] or "", achats.get(n, {}).get("prix")) for n, a in stocks(base).items()}
        fournisseurs = sorted((r["n"] for r in base.requete("SELECT TRIM(sName) n FROM tvendor WHERE bInactive = 0")
                               if r["n"]), key=str.casefold)
        return articles, fournisseurs

    def fin(resultat):
        articles, fournisseurs = resultat

        def valider(entete, lignes):
            if not entete["tiers"]:
                raise ValueError(t("Choisissez le fournisseur."))
            propositions = [bc.Proposition(l["numero_sage"], l["description"], "", Decimal(0), Decimal(0),
                                           l["quantite"], entete["tiers"], l["prix"]) for l in lignes]
            bons = bc.creer_bons(racine, propositions, date.fromisoformat(entete["date"]))
            if apres:
                apres()
            if bons and bons[0].pdf:
                os.startfile(bons[0].pdf)
            return t("Bon {n} créé pour {f}.", n=bons[0].numero, f=entete["tiers"])

        SaisieDocument(parent, "Saisir une commande fournisseur", articles, valider, tiers=fournisseurs,
                       libelle_tiers="Fournisseur", libelle_prix="Prix d'achat", action="Créer le bon de commande")

    lire_sage_dans_un_fil(parent, racine, lecture, fin)
