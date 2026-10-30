"""Fenêtres du paquet 2 des fonctions ajoutées le 2026-10-29 : retours fournisseurs, étiquettes de prix, coût de la
main-d'œuvre. Calculs dans retours.py, etiquettes.py, budget.py."""

from __future__ import annotations

import os
import tempfile
import tkinter as tk
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from tkinter import messagebox, ttk

from .design import FenetreOutil, CARTE, ROUGE, TEXTE_DOUX, VERT_FONCE, Bouton, ChampDate, ChampRecherche, Rangee
from .export_tableau import bouton_exporter
from .fenetres_gestion2 import _config, _fil
from .langues import t


class FenetreRetours(FenetreOutil):
    def __init__(self, parent, racine: Path, auteur: str = ""):
        from . import retours as rt
        from .page_rapports import tableau_simple
        from .taxes import CHOIX

        super().__init__(parent)
        self.racine, self.auteur, self.rt, self.choix_taxes = Path(racine), auteur, rt, CHOIX
        self.lignes: list = []
        self.title(t("Retours fournisseurs"))
        self.configure(background=CARTE, padx=14, pady=10)
        self.geometry("1100x640")
        from .page_points_vente import ChoixPointVente
        from .points_vente import visibles

        forme = Rangee(self)
        forme.pack(fill="x")
        self.choix_pv = ChoixPointVente(forme, lambda: visibles(self, _config(self.racine)))
        forme.ajouter(self.choix_pv, 8)
        self.v = {c: tk.StringVar() for c in ("fournisseur", "facture", "jour", "motif", "numero", "description",
                                              "quantite", "prix")}
        self.v["jour"].set(date.today().isoformat())
        for cle, libelle, largeur in (("fournisseur", "Fournisseur Sage", 24), ("facture", "N° de la facture d'origine", 14),
                                      ("motif", "Motif", 20)):
            g = forme.ajouter(forme.groupe(), 8)
            tk.Label(g, text=t(libelle) + (" *" if cle != "motif" else ""), background=CARTE).pack(side="left", padx=(0, 4))
            ttk.Entry(g, textvariable=self.v[cle], width=largeur).pack(side="left")
        g = forme.ajouter(forme.groupe(), 8)
        tk.Label(g, text=t("Date"), background=CARTE).pack(side="left", padx=(0, 4))
        ChampDate(g, self.v["jour"], fond=CARTE).pack(side="left")
        forme.ajouter(Bouton(forme, "📥  " + t("Reprendre les lignes de la facture"), self.reprendre, "secondaire",
                             fond=CARTE, petit=True))
        ligne = Rangee(self)
        ligne.pack(fill="x", pady=(8, 0))
        for cle, libelle, largeur in (("numero", "N° Sage", 12), ("description", "Description", 26),
                                      ("quantite", "Quantité (unités Sage)", 8), ("prix", "Prix Sage", 9)):
            g = ligne.ajouter(ligne.groupe(), 8)
            tk.Label(g, text=t(libelle), background=CARTE).pack(side="left", padx=(0, 4))
            ttk.Entry(g, textvariable=self.v[cle], width=largeur).pack(side="left")
        g = ligne.ajouter(ligne.groupe(), 8)
        tk.Label(g, text=t("Taxes"), background=CARTE).pack(side="left", padx=(0, 4))
        self.taxe = tk.StringVar(value=t(CHOIX[""]))
        ttk.Combobox(g, textvariable=self.taxe, values=[t(x) for x in CHOIX.values()], state="readonly",
                     width=14).pack(side="left")
        ligne.ajouter(Bouton(ligne, "➕  " + t("Ajouter la ligne"), self.ajouter_ligne, fond=CARTE, petit=True), 6)
        ligne.ajouter(Bouton(ligne, "✖  " + t("Retirer la ligne"), self.retirer, "secondaire", fond=CARTE, petit=True))
        self.tableau = tableau_simple(self, hauteur=8)
        bas = Rangee(self)
        bas.pack(fill="x", pady=(8, 0))
        bas.ajouter(Bouton(bas, "✔  " + t("Enregistrer le retour"), self.enregistrer, fond=CARTE), 8)
        bas.ajouter(Bouton(bas, "📤  " + t("Importer le retour choisi dans Sage"), self.importer, "secondaire",
                           fond=CARTE), 8)
        self.etat = tk.Label(self, text=t("Le retour est importé dans Sage comme une facture d'achat négative "
                                          "(« R-n° de facture ») ; le stock Clover des articles reliés diminue."),
                             background=CARTE, foreground=TEXTE_DOUX, anchor="w", justify="left", wraplength=1050)
        self.etat.pack(fill="x", pady=(6, 0))
        self.tableau_retours = tableau_simple(self, hauteur=8)
        self.afficher()

    def afficher(self) -> None:
        from .page_rapports import remplir

        remplir(self.tableau, ["N° Sage", "Description", "Quantité", "Prix", "Montant", "Taxes"],
                [[l.numero_sage, l.description, Decimal(l.quantite), Decimal(l.prix), l.montant, l.taxe or "—"]
                 for l in self.lignes], {"Description": 320}, decroissant=False)
        self.retours = sorted(self.rt.Registre(self.racine).retours, key=lambda r: r.cree, reverse=True)
        remplir(self.tableau_retours, ["Date", "N°", "Fournisseur", "Facture d'origine", "Lignes", "Montant", "État",
                                       "Messages"],
                [[r.jour, r.numero, r.fournisseur_sage, r.facture_origine, len(r.lignes),
                  sum((l.montant for l in r.lignes), Decimal(0)), t(r.etat), " ; ".join(r.messages)]
                 for r in self.retours], {"Messages": 320})

    def reprendre(self) -> None:
        lignes = self.rt.lignes_facture_origine(self.racine, self.v["fournisseur"].get().strip(),
                                                self.v["facture"].get().strip())
        if not lignes:
            self.etat.configure(text="✘ " + t("Facture introuvable dans les factures fournisseurs (registre ou "
                                              "archives) : saisissez les lignes."), foreground=ROUGE)
            return
        self.lignes = lignes
        self.afficher()
        self.etat.configure(text=t("{n} ligne(s) reprises : retirez celles qui ne sont pas retournées et ajustez les "
                                   "quantités.", n=len(lignes)), foreground=VERT_FONCE)

    def ajouter_ligne(self) -> None:
        taxe = next((k for k, v in self.choix_taxes.items() if t(v) == self.taxe.get()), "")
        try:
            q = Decimal(self.v["quantite"].get().replace(",", "."))
            p = Decimal(self.v["prix"].get().replace(",", "."))
            if q <= 0 or p < 0 or not self.v["numero"].get().strip():
                raise InvalidOperation
        except InvalidOperation:
            self.etat.configure(text="✘ " + t("N° Sage, quantité positive et prix obligatoires."), foreground=ROUGE)
            return
        self.lignes.append(self.rt.LigneRetour(self.v["numero"].get().strip(), self.v["description"].get().strip(),
                                               str(q), str(p), taxe))
        for c in ("numero", "description", "quantite", "prix"):
            self.v[c].set("")
        self.afficher()

    def retirer(self) -> None:
        choix = self.tableau.selection()
        if choix:
            del self.lignes[int(choix[0])]
            self.afficher()

    def enregistrer(self) -> None:
        try:
            r = self.rt.Registre(self.racine).ajouter(self.v["fournisseur"].get().strip(),
                                                      self.v["facture"].get().strip(), self.v["jour"].get().strip(),
                                                      self.lignes, self.v["motif"].get().strip(), self.auteur,
                                                      self.choix_pv.courant.code if self.choix_pv.courant else "")
        except ValueError as exc:
            self.etat.configure(text="✘ " + t(str(exc)), foreground=ROUGE)
            return
        self.lignes = []
        self.afficher()
        self.etat.configure(text=t("✔ {n} enregistré : « Importer le retour choisi dans Sage ».", n=r.numero),
                            foreground=VERT_FONCE)

    def importer(self) -> None:
        from .design import action_permise

        if not action_permise(self, "Importer un retour dans Sage"):
            return
        choix = self.tableau_retours.selection()
        if not choix:
            messagebox.showinfo(self.title(), t("Choisissez un retour dans la liste."), parent=self)
            return
        r = self.retours[int(choix[0])]
        if not messagebox.askyesno(self.title(), t("Importer {n} ({f}) dans Sage ? Sage doit être fermé.",
                                                   n=r.numero, f=r.fournisseur_sage), parent=self):
            return
        _fil(self, lambda: self.rt.importer(self.racine, _config(self.racine), r.numero),
             lambda fait: (self.afficher(), self.etat.configure(text=f"{fait.numero} : {t(fait.etat)} — "
                                                                + " ; ".join(fait.messages),
                                                                foreground=VERT_FONCE if fait.etat == self.rt.IMPORTE
                                                                else ROUGE)),
             self.etat, "Import dans Sage…")


class FenetreEtiquettes(FenetreOutil):
    def __init__(self, parent, racine: Path):
        from .page_rapports import tableau_simple

        super().__init__(parent)
        self.racine = Path(racine)
        self.articles: dict[str, dict] = {}
        self.choisis: list[dict] = []
        self.title(t("Étiquettes de prix"))
        self.configure(background=CARTE, padx=14, pady=10)
        self.geometry("1000x600")
        from .page_points_vente import ChoixPointVente
        from .points_vente import visibles

        barre = Rangee(self)
        barre.pack(fill="x")
        self.choix_pv = ChoixPointVente(barre, lambda: visibles(self, _config(self.racine)),
                                        lambda: (self.vider(), self._charger()))
        barre.ajouter(self.choix_pv, 8)
        g = barre.ajouter(barre.groupe(), 8)
        tk.Label(g, text=t("Article"), background=CARTE).pack(side="left", padx=(0, 4))
        self.article = tk.StringVar()
        self.recherche = ChampRecherche(g, self.article, [], largeur=44)
        self.recherche.pack(side="left")
        g = barre.ajouter(barre.groupe(), 8)
        tk.Label(g, text=t("Nombre"), background=CARTE).pack(side="left", padx=(0, 4))
        self.nombre = tk.StringVar(value="1")
        ttk.Entry(g, textvariable=self.nombre, width=4).pack(side="left")
        barre.ajouter(Bouton(barre, "➕  " + t("Ajouter"), self.ajouter, fond=CARTE, petit=True), 8)
        g = barre.ajouter(barre.groupe(), 8)
        tk.Label(g, text=t("Prix changés depuis"), background=CARTE).pack(side="left", padx=(0, 4))
        self.depuis = tk.StringVar(value=(date.today() - timedelta(days=7)).isoformat())
        ChampDate(g, self.depuis, fond=CARTE).pack(side="left")
        barre.ajouter(Bouton(barre, "🏷  " + t("Ajouter ces articles"), self.prix_changes, "secondaire", fond=CARTE,
                             petit=True), 8)
        bas = Rangee(self)
        bas.pack(fill="x", pady=(8, 0))
        bas.ajouter(Bouton(bas, "🖨  " + t("Imprimer les étiquettes"), self.imprimer, fond=CARTE), 8)
        bas.ajouter(Bouton(bas, "🗑  " + t("Vider la liste"), self.vider, "secondaire", fond=CARTE))
        self.etat = tk.Label(self, text=t("Feuilles de 30 étiquettes (Avery 5160 / 8160, 3 × 10) : nom, prix, code-barres "
                                          "du code produit."), background=CARTE, foreground=TEXTE_DOUX, anchor="w")
        self.etat.pack(fill="x", pady=(6, 0))
        self.tableau = tableau_simple(self, hauteur=16)
        self._charger()

    def _charger(self) -> None:
        from .cache_lectures import inventaire_clover

        def fin(articles):
            self.articles = {f"{a.get('name', '')} — {a.get('code') or a.get('sku') or a['id'][:6]}": a
                             for a in articles if a.get("name") and not a.get("hidden")}
            self.recherche.configurer_valeurs(sorted(self.articles, key=str.casefold))
            self.etat.configure(text=t("{n} articles Clover.", n=len(self.articles)), foreground=TEXTE_DOUX)

        pv = self.choix_pv.courant  # prix du point de vente choisi
        _fil(self, lambda: inventaire_clover(self.racine, pv), fin, self.etat, "Lecture du catalogue Clover…")

    def afficher(self) -> None:
        from .etiquettes import depuis_article
        from .page_rapports import remplir

        lignes = [[e.nom, e.prix, e.unite, e.code] for e in (depuis_article(a) for a in self.choisis)]
        remplir(self.tableau, ["Article", "Prix", "Unité", "Code"], lignes, {"Article": 380}, decroissant=False)
        self.etat.configure(text=t("{n} étiquette(s) — {f} feuille(s)", n=len(self.choisis),
                                   f=(len(self.choisis) + 29) // 30), foreground=TEXTE_DOUX)

    def ajouter(self) -> None:
        a = self.articles.get(self.article.get())
        if not a:
            return
        try:
            n = max(1, min(300, int(self.nombre.get())))
        except ValueError:
            n = 1
        self.choisis += [a] * n
        self.article.set("")
        self.afficher()

    def prix_changes(self) -> None:
        from .etiquettes import prix_changes

        ids = prix_changes(self.racine, self.depuis.get().strip())
        self.choisis += [a for a in self.articles.values() if a.get("id") in ids]
        self.afficher()

    def vider(self) -> None:
        self.choisis = []
        self.afficher()

    def imprimer(self) -> None:
        from .design import action_permise

        if not action_permise(self, "Imprimer des étiquettes"):
            return
        from .etiquettes import depuis_article, page

        if not self.choisis:
            return
        dossier = Path(tempfile.gettempdir()) / "MVOGMBI_Sync_impression"
        dossier.mkdir(exist_ok=True)
        chemin = dossier / f"etiquettes_{datetime.now():%Y%m%d_%H%M%S}.html"
        chemin.write_text(page([depuis_article(a) for a in self.choisis]), encoding="utf-8")
        os.startfile(chemin)


class FenetreMainOeuvre(FenetreOutil):
    def __init__(self, parent, racine: Path):
        from .page_rapports import tableau_simple

        super().__init__(parent)
        self.racine = Path(racine)
        self.title(t("Coût de la main-d'œuvre"))
        self.configure(background=CARTE, padx=14, pady=10)
        self.geometry("1000x600")
        barre = Rangee(self)
        barre.pack(fill="x")
        g = barre.ajouter(barre.groupe(), 10)
        tk.Label(g, text=t("Du"), background=CARTE).pack(side="left")
        self.du = tk.StringVar(value=(date.today() - timedelta(days=28)).isoformat())
        ChampDate(g, self.du, fond=CARTE).pack(side="left", padx=4)
        tk.Label(g, text=t("au"), background=CARTE).pack(side="left")
        self.au = tk.StringVar(value=(date.today() + timedelta(days=13)).isoformat())
        ChampDate(g, self.au, fond=CARTE).pack(side="left", padx=4)
        barre.ajouter(Bouton(barre, "🔍  " + t("Afficher"), self.afficher, fond=CARTE, petit=True), 10)
        self.etat = tk.Label(self, text="", background=CARTE, foreground=TEXTE_DOUX, anchor="w", justify="left",
                             wraplength=960)
        self.etat.pack(fill="x", pady=(6, 0))
        self.tableau = tableau_simple(self, hauteur=18)
        barre.ajouter(bouton_exporter(barre, self.tableau, lambda: t("Coût de la main-d'œuvre")))
        self.afficher()

    def afficher(self) -> None:
        from . import budget as bu
        from .page_rapports import remplir

        try:
            debut, fin = date.fromisoformat(self.du.get().strip()), date.fromisoformat(self.au.get().strip())
        except ValueError:
            self.etat.configure(text="✘ " + t("Date au format AAAA-MM-JJ."), foreground=ROUGE)
            return
        config = _config(self.racine)
        taux, charges = bu.taux_et_charges(config)

        def travail():
            from .__main__ import charger_config
            from .api_clover import ClientClover
            from .previsions import ventes_par_jour
            from .statistiques_clover import lire

            from .points_vente import cache_clover, client, visibles

            hier = min(fin, date.today())
            ventes: dict = {}
            if debut <= hier:  # ventes de tous les points de vente visibles (les employés passent de l'un à l'autre)
                for pv in visibles(self, config):
                    for jour, v in ventes_par_jour(lire(client(self.racine, pv), debut, hier,
                                                        cache_clover(self.racine, pv))).items():
                        ventes[jour] = ventes.get(jour, Decimal(0)) + v
            pointees, planifiees = bu.heures_par_jour_tous(self.racine, debut, fin)
            return bu.main_oeuvre(ventes, pointees, planifiees, debut, fin, taux, charges)

        def termine(lignes):
            from .paie import heures

            remplir(self.tableau, ["Date", "Ventes nettes", "Heures pointées", "Heures planifiées",
                                   "Coût estimé", "Part des ventes"],
                    [[l[0], l[1], heures(l[2]), heures(l[3]), l[4], l[5]] for l in lignes])
            ventes = sum((l[1] for l in lignes), Decimal(0))
            cout = sum((l[4] for l in lignes), Decimal(0))
            part = f"{cout / ventes * 100:.1f} %".replace(".", ",") if ventes else "—"
            self.etat.configure(text=t("Coût estimé {c} pour {v} de ventes : {p}. Taux moyen {t} $/h + {s} % de charges "
                                       "([paie] taux_moyen et charges_sociales de config.toml).",
                                       c=f"{cout:,.2f} $".replace(",", " ").replace(".", ","),
                                       v=f"{ventes:,.2f} $".replace(",", " ").replace(".", ","), p=part, t=taux,
                                       s=charges), foreground=TEXTE_DOUX)

        _fil(self, travail, termine, self.etat, "Lecture des ventes et des heures…")
