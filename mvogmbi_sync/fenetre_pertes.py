"""Fenêtre « Articles > Pertes et démarque » (demande du propriétaire du 2026-10-29) : déclaration d'une perte
(articles du catalogue Clover, motif, dépôt), liste des pertes déclarées, rapport par motif / catégorie / article /
mois avec la part des ventes. Calculs dans pertes.py."""

from __future__ import annotations

import threading
import tkinter as tk
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from tkinter import messagebox, ttk

from . import pertes as pe
from .design import FenetreOutil, CARTE, ROUGE, TEXTE_DOUX, VERT_FONCE, Bouton, ChampDate, ChampRecherche, Rangee
from .export_tableau import bouton_exporter
from .langues import t

ONGLETS = ["Déclarer une perte", "Pertes déclarées", "Rapport des pertes"]


def _argent(v) -> str:
    return f"{Decimal(v):,.2f} $".replace(",", " ").replace(".", ",")


def _config(racine: Path) -> dict:
    import tomllib

    chemin = Path(racine) / "config.toml"
    return tomllib.loads(chemin.read_text(encoding="utf-8")) if chemin.exists() else {}


class FenetrePertes(FenetreOutil):
    def __init__(self, parent, racine: Path, auteur: str = ""):
        super().__init__(parent)
        self.racine, self.auteur = Path(racine), auteur
        self.config_toml = _config(racine)
        self.articles: dict[str, dict] = {}   # « nom — code » -> article Clover
        self.liens, self.couts = {}, {}
        self.lignes: list[pe.LignePerte] = []
        self.title(t("Pertes et démarque"))
        self.configure(background=CARTE, padx=14, pady=10)
        self.geometry("1100x660")
        self.onglets = ttk.Notebook(self)
        self.onglets.pack(fill="both", expand=True)
        self.cadres = {}
        for nom, construire in zip(ONGLETS, (self._declarer, self._liste, self._rapport)):
            cadre = ttk.Frame(self.onglets, padding=(0, 8, 0, 0))
            self.onglets.add(cadre, text="  " + t(nom) + "  ")
            self.cadres[nom] = cadre
            construire(cadre)
        self.charger()

    # ------------------------------------------------------------------ catalogue
    def charger(self) -> None:
        self.etat.configure(text=t("Lecture du catalogue Clover…"), foreground=TEXTE_DOUX)

        def travail():
            from .cache_lectures import inventaire_clover
            from .couts_sage import charger, correspondance

            pv = self.choix_pv.courant
            articles = inventaire_clover(self.racine, pv)
            liens = correspondance(self.racine, pv)
            try:
                couts = charger(self.racine, self.config_toml)  # CUMP du jour (gardé), sinon lu dans Sage
            except Exception:
                couts = {}  # Sage illisible : coût Clover
            return articles, liens, couts

        def fin(resultat, erreur=""):
            if erreur:
                self.etat.configure(text="✘ " + erreur, foreground=ROUGE)
                return
            articles, self.liens, self.couts = resultat
            self.articles = {f"{a.get('name', '')} — {a.get('code') or a.get('sku') or a['id'][:6]}": a
                             for a in articles if a.get("name")}
            self.recherche.configurer_valeurs(sorted(self.articles, key=str.casefold))
            self.etat.configure(text=t("{n} articles Clover ; coût = CUMP de Sage s'il est relié, sinon coût Clover.",
                                       n=len(self.articles)), foreground=TEXTE_DOUX)

        def executer():
            try:
                r = travail()
                self.after(0, lambda: fin(r))
            except BaseException as exc:
                message = str(exc) or type(exc).__name__
                self.after(0, lambda: fin(None, message))

        threading.Thread(target=executer, daemon=True).start()

    def _changer_pv(self) -> None:
        if self.lignes and not messagebox.askyesno(self.title(), t("Changer de point de vente vide les lignes en cours. "
                                                                    "Continuer ?"), parent=self):
            return
        self.lignes = []
        self.afficher_lignes()
        self.charger()

    # ------------------------------------------------------------------ déclarer
    def _declarer(self, cadre) -> None:
        from . import documents as dc
        from .page_rapports import tableau_simple

        entete = Rangee(cadre)
        entete.pack(fill="x")
        g = entete.ajouter(entete.groupe(), 12)
        tk.Label(g, text=t("Date"), background=CARTE).pack(side="left", padx=(0, 4))
        self.jour = tk.StringVar(value=date.today().isoformat())
        ChampDate(g, self.jour, fond=CARTE).pack(side="left")
        g = entete.ajouter(entete.groupe(), 12)
        tk.Label(g, text=t("Motif") + " *", background=CARTE).pack(side="left", padx=(0, 4))
        self.motif = tk.StringVar(value=t(pe.MOTIFS[0]))
        ttk.Combobox(g, textvariable=self.motif, values=[t(m) for m in pe.MOTIFS], state="readonly",
                     width=20).pack(side="left")
        from .page_points_vente import ChoixPointVente
        from .points_vente import visibles

        # point de vente : son catalogue Clover, sa correspondance et son dépôt Sage (sortie de stock)
        self.choix_pv = ChoixPointVente(entete, lambda: visibles(self, self.config_toml), self._changer_pv)
        entete.ajouter(self.choix_pv, 12)
        g = entete.ajouter(entete.groupe(), 12)
        tk.Label(g, text=t("Remarque"), background=CARTE).pack(side="left", padx=(0, 4))
        self.remarque = tk.StringVar()
        ttk.Entry(g, textvariable=self.remarque, width=28).pack(side="left")
        ajout = Rangee(cadre)
        ajout.pack(fill="x", pady=(10, 4))
        g = ajout.ajouter(ajout.groupe(), 10)
        tk.Label(g, text=t("Article"), background=CARTE).pack(side="left", padx=(0, 4))
        self.article = tk.StringVar()
        self.recherche = ChampRecherche(g, self.article, [], largeur=48)
        self.recherche.pack(side="left")
        g = ajout.ajouter(ajout.groupe(), 10)
        tk.Label(g, text=t("Quantité"), background=CARTE).pack(side="left", padx=(0, 4))
        self.quantite = tk.StringVar(value="1")
        ttk.Entry(g, textvariable=self.quantite, width=8).pack(side="left")
        ajout.ajouter(Bouton(ajout, "➕  " + t("Ajouter la ligne"), self.ajouter, fond=CARTE, petit=True), 6)
        ajout.ajouter(Bouton(ajout, "✖  " + t("Retirer la ligne"), self.retirer, "secondaire", fond=CARTE,
                             petit=True), 6)
        ajout.ajouter(Bouton(ajout, "⏰  " + t("Ajouter les produits périmés en stock"), self.perimes, "secondaire",
                             fond=CARTE, petit=True))
        self.tableau = tableau_simple(cadre, hauteur=11)
        bas = Rangee(cadre)
        bas.pack(fill="x", pady=(8, 0))
        self.total = bas.ajouter(tk.Label(bas, text="", background=CARTE, font=("Segoe UI Semibold", 10)), 16)
        bas.ajouter(Bouton(bas, "✔  " + t("Enregistrer et sortir du stock"), self.enregistrer, fond=CARTE), 8)
        self.etat = tk.Label(cadre, text="", background=CARTE, foreground=TEXTE_DOUX, anchor="w", justify="left",
                             wraplength=1050)
        self.etat.pack(fill="x", pady=(6, 0))
        self.afficher_lignes()

    def afficher_lignes(self) -> None:
        from .page_rapports import remplir

        remplir(self.tableau, ["Article", "N° Sage", "Quantité", "Coût unitaire", "Coût d'après", "Valeur au coût"],
                [[l.nom, l.numero_sage or t("Non relié"), Decimal(l.quantite), Decimal(l.cout), t(l.source_cout),
                  l.valeur] for l in self.lignes], {"Article": 320}, decroissant=False)
        self.total.configure(text=t("{n} ligne(s) — valeur au coût {v}", n=len(self.lignes),
                                    v=_argent(sum((l.valeur for l in self.lignes), pe.ZERO))))

    def ajouter(self) -> None:
        article = self.articles.get(self.article.get())
        if not article:
            self.etat.configure(text="✘ " + t("Choisissez un article de la liste."), foreground=ROUGE)
            return
        try:
            quantite = Decimal(self.quantite.get().replace(",", ".").strip())
            if quantite <= 0:
                raise InvalidOperation
        except InvalidOperation:
            self.etat.configure(text="✘ " + t("Quantité invalide."), foreground=ROUGE)
            return
        l = pe.ligne(article, quantite, self.liens, self.couts)
        self.lignes.append(l)
        self.article.set("")
        self.quantite.set("1")
        self.afficher_lignes()
        self.etat.configure(text=("⚠ " + t("Coût inconnu : la valeur de cette ligne est 0.")) if l.source_cout ==
                            "Coût inconnu" else "", foreground=ROUGE)

    def perimes(self) -> None:
        """Articles dont l'UGS (date de péremption) est passée et qui ont du stock : ajoutés pour tout leur stock,
        motif « Périmé »."""
        from .peremption import lire_date

        aujourdhui, n = date.today(), 0
        deja = {l.id_clover for l in self.lignes}
        for article in self.articles.values():
            jour = lire_date(article.get("sku"))
            stock = Decimal(str((article.get("itemStock") or {}).get("quantity") or 0))
            if jour and jour < aujourdhui and stock > 0 and article.get("id") not in deja:
                self.lignes.append(pe.ligne(article, stock, self.liens, self.couts))
                n += 1
        self.motif.set(t("Périmé"))
        self.afficher_lignes()
        self.etat.configure(text=t("{n} produit(s) périmé(s) en stock ajouté(s) : vérifiez les quantités.", n=n),
                            foreground=VERT_FONCE if n else TEXTE_DOUX)

    def retirer(self) -> None:
        choix = self.tableau.selection()
        if choix:
            del self.lignes[int(choix[0])]
            self.afficher_lignes()

    def enregistrer(self) -> None:
        from .design import action_permise

        if not action_permise(self, "Sortir des pertes du stock"):
            return
        motif = next((m for m in pe.MOTIFS if t(m) == self.motif.get()), "")
        try:
            date.fromisoformat(self.jour.get().strip())
        except ValueError:
            self.etat.configure(text="✘ " + t("Date au format AAAA-MM-JJ."), foreground=ROUGE)
            return
        if not self.lignes:
            self.etat.configure(text="✘ " + t("Ajoutez au moins un article."), foreground=ROUGE)
            return
        valeur = sum((l.valeur for l in self.lignes), pe.ZERO)
        if not messagebox.askyesno(self.title(), t("Déclarer {n} ligne(s) en perte ({m}), valeur au coût {v} ?\n\n"
                                                   "Le stock Clover est diminué tout de suite ; un document de stock "
                                                   "« Sortie » est préparé pour Sage.", n=len(self.lignes), m=t(motif),
                                                   v=_argent(valeur)), parent=self):
            return
        try:
            pv = self.choix_pv.courant
            p = pe.nouvelle(pe.Registre(self.racine), self.jour.get().strip(), motif, self.lignes,
                            pv.depot_sage if pv else "", self.auteur, self.remarque.get().strip(),
                            pv.code if pv else "")
        except ValueError as exc:
            self.etat.configure(text="✘ " + t(str(exc)), foreground=ROUGE)
            return
        self.etat.configure(text=t("Sortie du stock en cours…"), foreground=TEXTE_DOUX)

        def executer():
            try:
                fait = pe.appliquer(self.racine, self.config_toml, p.numero)
                self.after(0, lambda: self._fin(fait, ""))
            except BaseException as exc:
                message = str(exc) or type(exc).__name__
                self.after(0, lambda: self._fin(p, message))

        threading.Thread(target=executer, daemon=True).start()

    def _fin(self, p: pe.Perte, erreur: str) -> None:
        if not self.winfo_exists():
            return
        self.lignes = []
        self.remarque.set("")
        self.afficher_lignes()
        self.afficher_liste()
        messagebox.showinfo(self.title(), f"{p.numero} — {_argent(p.valeur)}\n\n" + "\n".join(
            (["✘ " + erreur] if erreur else []) + p.messages), parent=self)
        self.etat.configure(text=t("✔ {n} enregistrée.", n=p.numero), foreground=VERT_FONCE)

    # ------------------------------------------------------------------ liste
    def _liste(self, cadre) -> None:
        from .page_rapports import tableau_simple

        barre = Rangee(cadre)
        barre.pack(fill="x")
        barre.ajouter(Bouton(barre, "🔄  " + t("Actualiser"), self.afficher_liste, fond=CARTE, petit=True), 8)
        barre.ajouter(Bouton(barre, "↻  " + t("Refaire la sortie du stock Clover"), self.reprendre, "secondaire",
                             fond=CARTE, petit=True), 8)
        self.tableau_liste = tableau_simple(cadre, hauteur=16)
        barre.ajouter(bouton_exporter(barre, self.tableau_liste, lambda: t("Pertes déclarées")))
        self.afficher_liste()

    def afficher_liste(self) -> None:
        from .page_rapports import remplir

        self.pertes = pe.Registre(self.racine).pertes
        remplir(self.tableau_liste, ["Date", "N°", "Point de vente", "Motif", "Lignes", "Valeur au coût",
                                     "Document de stock", "Déclarée par", "Messages"],
                [[p.jour, p.numero, p.point_vente or "1", t(p.motif), len(p.lignes), p.valeur, p.document, p.auteur,
                  " ; ".join(p.messages)] for p in self.pertes], {"Messages": 360})

    def reprendre(self) -> None:
        choix = self.tableau_liste.selection()
        if not choix:
            messagebox.showinfo(self.title(), t("Choisissez une perte dans la liste."), parent=self)
            return
        numero = self.pertes[int(choix[0])].numero

        def executer():
            try:
                p = pe.appliquer(self.racine, self.config_toml, numero)
                self.after(0, lambda: self._fin(p, ""))
            except BaseException as exc:
                message = str(exc) or type(exc).__name__
                self.after(0, lambda: messagebox.showerror(self.title(), message, parent=self))

        threading.Thread(target=executer, daemon=True).start()

    # ------------------------------------------------------------------ rapport
    def _rapport(self, cadre) -> None:
        from .page_rapports import tableau_simple

        barre = Rangee(cadre)
        barre.pack(fill="x")
        g = barre.ajouter(barre.groupe(), 10)
        tk.Label(g, text=t("Du"), background=CARTE).pack(side="left")
        self.du = tk.StringVar(value=date.today().replace(day=1).isoformat())
        ChampDate(g, self.du, fond=CARTE).pack(side="left", padx=4)
        tk.Label(g, text=t("au"), background=CARTE).pack(side="left")
        self.au = tk.StringVar(value=date.today().isoformat())
        ChampDate(g, self.au, fond=CARTE).pack(side="left", padx=4)
        g = barre.ajouter(barre.groupe(), 10)
        tk.Label(g, text=t("Par"), background=CARTE).pack(side="left", padx=(0, 4))
        self.regroupement = tk.StringVar(value=t("Motif"))
        ttk.Combobox(g, textvariable=self.regroupement, values=[t(r) for r in pe.REGROUPEMENTS], state="readonly",
                     width=12).pack(side="left")
        barre.ajouter(Bouton(barre, "🔍  " + t("Afficher"), self.afficher_rapport, fond=CARTE, petit=True), 10)
        self.etat_rapport = tk.Label(cadre, text=t("Choisissez la période puis « Afficher »."), background=CARTE,
                                     foreground=TEXTE_DOUX, anchor="w")
        self.etat_rapport.pack(fill="x", pady=(6, 0))
        self.tableau_rapport = tableau_simple(cadre, hauteur=16)
        barre.ajouter(bouton_exporter(barre, self.tableau_rapport, lambda: t("Rapport des pertes")))

    def afficher_rapport(self) -> None:
        from .page_rapports import remplir

        try:
            debut, fin = date.fromisoformat(self.du.get().strip()), date.fromisoformat(self.au.get().strip())
        except ValueError:
            self.etat_rapport.configure(text="✘ " + t("Date au format AAAA-MM-JJ."), foreground=ROUGE)
            return
        cle = next((v for k, v in pe.REGROUPEMENTS.items() if t(k) == self.regroupement.get()), "motif")
        lignes, total = pe.rapport(pe.Registre(self.racine).pertes, debut, fin, cle)
        remplir(self.tableau_rapport, pe.ENTETES_RAPPORT, [[t(l[0]) if cle == "motif" else l[0]] + l[1:] for l in lignes],
                {"Regroupement": 320}, decroissant=False)
        self.etat_rapport.configure(text=t("Pertes au coût : {v} — calcul de la part des ventes…", v=_argent(total)),
                                    foreground=TEXTE_DOUX)

        def executer():
            try:
                from .__main__ import charger_config
                from .api_clover import ClientClover
                from .previsions import ventes_par_article_rapide

                client = ClientClover(charger_config(self.racine / "config.toml"))
                ventes = ventes_par_article_rapide(client, debut, min(fin, date.today()),
                                                   self.racine / "donnees" / "cache_clover")
                nettes = sum((v.nettes for v in ventes.values()), pe.ZERO)
            except BaseException:
                nettes = pe.ZERO
            self.after(0, lambda: self.etat_rapport.configure(
                text=t("Pertes au coût : {v} ; ventes nettes : {n} ; pertes = {p} des ventes.", v=_argent(total),
                       n=_argent(nettes), p=pe.taux(total, nettes)),
                foreground=VERT_FONCE if total else TEXTE_DOUX))

        threading.Thread(target=executer, daemon=True).start()
