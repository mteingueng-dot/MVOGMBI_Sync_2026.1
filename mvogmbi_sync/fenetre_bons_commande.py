"""Fenêtres « Bons de commande » (rubrique Fournisseur, demande du propriétaire du 2026-10-29) : proposition à
cocher, bons créés (PDF) et comparaison avec la facture reçue. Calculs dans bons_commande.py."""

from __future__ import annotations

import os
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from . import bons_commande as bc
from .design import CARTE, ROUGE, TEXTE_DOUX, VERT_FONCE, Bouton, Rangee
from .export_tableau import bouton_exporter
from .langues import t

HORIZONS = (7, 10, 14, 21, 28)


def _nombre(v) -> str:
    return "" if v is None else f"{v:f}".replace(".", ",")


def _argent(v) -> str:
    return "" if v is None else f"{v:,.2f} $".replace(",", " ").replace(".", ",")


def _config(racine: Path) -> dict:
    import tomllib

    chemin = Path(racine) / "config.toml"
    return tomllib.loads(chemin.read_text(encoding="utf-8")) if chemin.exists() else {}


def ouvrir(parent, racine: Path):
    """Proposition des bons de commande (liste à cocher)."""
    from .fenetre_cocher import FenetreACocher

    racine = Path(racine)
    reglages = {"jours": tk.StringVar(value="14")}

    def ajouts(fenetre, barre):
        groupe = barre.ajouter(barre.groupe(), 12)
        tk.Label(groupe, text=t("Couvrir"), background=CARTE).pack(side="left")
        choix = ttk.Combobox(groupe, textvariable=reglages["jours"], values=[str(h) for h in HORIZONS],
                             state="readonly", width=4)
        choix.pack(side="left", padx=4)
        choix.bind("<<ComboboxSelected>>", lambda _e: fenetre.charger())
        tk.Label(groupe, text=t("jours de ventes"), background=CARTE).pack(side="left")
        barre.ajouter(Bouton(barre, "📂  " + t("Bons créés…"), lambda: FenetreBons(fenetre, racine), "secondaire",
                             fond=CARTE, petit=True))

    def lire():
        jours = int(reglages["jours"].get())
        lignes = bc.lire(racine, _config(racine), jours)
        a_commander = [p for p in lignes if p.permis]
        fournisseurs = {p.fournisseur for p in a_commander}
        total = sum((p.montant or 0 for p in a_commander), 0)
        return lignes, t("{n} article(s) à commander chez {f} fournisseur(s), {m} au dernier prix d'achat — règle : "
                         "stock Clover − ventes des {j} derniers jours <= 0 ; quantité = de quoi couvrir {j} jours. "
                         "Fournisseur et prix : dernier achat dans Sage.", n=len(a_commander), f=len(fournisseurs),
                         m=_argent(total), j=jours)

    def traiter(choisies, _progression):
        bons = bc.creer_bons(racine, choisies)
        dossier = racine / "donnees" / bc.DOSSIER
        if bons and dossier.exists():
            os.startfile(dossier)
        return t("{n} bon(s) de commande créé(s) : ", n=len(bons)) + ", ".join(
            f"{b.numero} {b.fournisseur} ({_argent(b.total)})" for b in bons) + "\n" + t(
            "Les PDF sont dans le dossier qui vient de s'ouvrir : envoyez-les à vos fournisseurs.")

    return FenetreACocher(
        parent, t("Bons de commande"),
        t("Articles à commander (règle des prévisions), regroupés par article Sage, avec le fournisseur et le prix du "
          "dernier achat dans Sage. Cochez les lignes : un bon par fournisseur est créé en PDF (rien n'est envoyé "
          "sans vous)."),
        [("Fournisseur", 180), ("N° Sage", 100), ("Article Sage", 240), ("Articles Clover", 200), ("Stock", 70),
         ("Vendu", 70), ("À commander", 90), ("Prix", 80), ("Montant", 90), ("Dernier achat", 95), ("État", 150)],
        lambda p: (p.fournisseur, p.numero_sage, p.description, p.articles_clover, _nombre(p.stock),
                   _nombre(p.vendu), _nombre(p.quantite), _argent(p.prix), _argent(p.montant), p.dernier_achat,
                   t(p.etat)),
        lire, traiter, t("Créer les bons de commande"),
        t("Créer les bons de commande pour {n} ligne(s) cochée(s) ?"), ajouts=ajouts)


class FenetreBons(tk.Toplevel):
    """Bons créés : PDF, comparaison avec la facture du fournisseur, réception."""

    def __init__(self, parent, racine: Path):
        from .page_rapports import tableau_simple

        super().__init__(parent)
        self.racine = Path(racine)
        self.title(t("Bons de commande créés"))
        self.configure(background=CARTE, padx=14, pady=10)
        self.transient(parent)
        self.geometry("1000x620")
        barre = Rangee(self)
        barre.pack(fill="x")
        for texte, commande in (("➕  " + t("Nouveau bon…"), self.nouveau),
                                ("📄  " + t("Ouvrir le PDF"), self.ouvrir_pdf),
                                ("🔁  " + t("Refaire le PDF"), self.refaire),
                                ("⚖  " + t("Comparer avec la facture"), self.comparer)):
            barre.ajouter(Bouton(barre, texte, commande, "secondaire", fond=CARTE, petit=True))
        self.etat = tk.Label(self, text="", background=CARTE, foreground=TEXTE_DOUX, anchor="w", justify="left",
                             wraplength=950)
        self.etat.pack(fill="x", pady=(6, 0))
        self.tableau = tableau_simple(self, hauteur=8)
        self.tableau.configure(selectmode="browse")
        self.tableau.bind("<Double-1>", lambda _e: self.comparer())
        tk.Label(self, text=t("Comparaison avec la facture"), background=CARTE,
                 font=("Segoe UI Semibold", 10), anchor="w").pack(fill="x", pady=(10, 0))
        self.comparaison = tableau_simple(self, hauteur=8)
        self.comparaison.tag_configure("ecart", background="#fde2e4")
        bas = Rangee(self)
        bas.pack(fill="x", pady=(6, 0))
        self.bouton_recu = bas.ajouter(Bouton(bas, "✔  " + t("Marquer reçu"), self.marquer_recu, fond=CARTE,
                                              petit=True))
        bas.ajouter(bouton_exporter(bas, self.comparaison, lambda: t("Comparaison bon et facture")))
        barre.ajouter(bouton_exporter(barre, self.tableau, t("Bons de commande")))
        self.resultat = None
        self.afficher()

    def afficher(self) -> None:
        from .page_rapports import remplir

        self.bons = sorted(bc.Registre(self.racine).bons, key=lambda b: b.numero, reverse=True)
        remplir(self.tableau, ["N°", "Date", "Fournisseur", "Articles", "Total", "État", "Facture"],
                [[b.numero, b.date, b.fournisseur, len(b.lignes), b.total, t(b.etat), b.facture] for b in self.bons],
                {"N°": 80, "Date": 95, "Fournisseur": 220, "Articles": 70, "Total": 100, "État": 130,
                 "Facture": 200}, decroissant=False)
        self.etat.configure(text=t("{n} bon(s). Double-clic ou « Comparer avec la facture » : la facture du même "
                                   "fournisseur reçue depuis le bon (factures fournisseurs) est comparée au bon.",
                                   n=len(self.bons)))

    def nouveau(self) -> None:
        from .fenetre_gestion import saisir_bon_commande
        saisir_bon_commande(self, self.racine, apres=self.afficher)

    def _bon(self):
        choix = self.tableau.selection()
        if not choix:
            messagebox.showinfo(self.title(), t("Choisissez un bon dans la liste."), parent=self)
            return None
        return self.bons[int(choix[0])]

    def ouvrir_pdf(self) -> None:
        bon = self._bon()
        if bon and bon.pdf and Path(bon.pdf).exists():
            os.startfile(bon.pdf)
        elif bon:
            messagebox.showinfo(self.title(), t("PDF absent : « Refaire le PDF »."), parent=self)

    def refaire(self) -> None:
        bon = self._bon()
        if not bon:
            return
        try:
            os.startfile(bc.refaire_pdf(self.racine, bon.numero))
        except Exception as exc:
            messagebox.showerror(self.title(), str(exc), parent=self)
        self.afficher()

    def comparer(self) -> None:
        from .page_rapports import remplir

        bon = self._bon()
        if not bon:
            return
        factures = bc.factures_du_fournisseur(self.racine, bon)
        if not factures:
            remplir(self.comparaison, [], [])
            self.resultat = None
            self.etat.configure(text=t("Aucune facture de {f} reçue depuis le {d} : lisez-la d'abord dans "
                                       "« Fournisseur > Factures fournisseurs ».", f=bon.fournisseur, d=bon.date),
                                foreground=ROUGE)
            return
        facture = factures[0]
        lignes, conforme = bc.comparer(bon, facture)
        remplir(self.comparaison, bc.ENTETES_COMPARAISON, [l[:-1] + [t(l[-1])] for l in lignes],
                {"N° Sage": 100, "Description": 230, "Constat": 140}, lambda i: () if lignes[i][-1] == "Conforme"
                else ("ecart",), decroissant=False)
        self.resultat = (bon.numero, f"{facture.numero} du {facture.date_facture}", conforme)
        self.etat.configure(text=t("Bon {b} comparé à la facture {f} : {c}.", b=bon.numero,
                                   f=self.resultat[1], c=t("conforme") if conforme else t("écarts en rouge")),
                            foreground=VERT_FONCE if conforme else ROUGE)

    def marquer_recu(self) -> None:
        if not self.resultat:
            messagebox.showinfo(self.title(), t("Comparez d'abord le bon avec sa facture."), parent=self)
            return
        bc.noter_reception(self.racine, *self.resultat)
        self.afficher()
