"""Fenêtres du paquet 3 des fonctions ajoutées le 2026-10-29 : inventaire tournant, promotions, relances des clients
professionnels, tableau du gérant pour le téléphone. Calculs dans paquet3.py."""

from __future__ import annotations

import os
import tempfile
import tkinter as tk
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from tkinter import messagebox, ttk

from . import paquet3 as p3
from .design import FenetreOutil, CARTE, ROUGE, TEXTE_DOUX, VERT_FONCE, Bouton, ChampDate, ChampRecherche, Rangee
from .export_tableau import bouton_exporter
from .fenetres_gestion2 import _argent, _config, _fil
from .langues import t


class FenetreInventaireTournant(FenetreOutil):
    def __init__(self, parent, racine: Path):
        from .page_rapports import tableau_simple

        super().__init__(parent)
        self.racine = Path(racine)
        self.title(t("Inventaire tournant"))
        self.configure(background=CARTE, padx=14, pady=10)
        self.geometry("900x560")
        barre = Rangee(self)
        barre.pack(fill="x")
        barre.ajouter(Bouton(barre, "📋  " + t("Feuille de comptage de la semaine"), self.feuille, fond=CARTE,
                             petit=True), 8)
        self.etat = tk.Label(self, text=t("Chaque semaine, on compte quelques catégories ; toutes le sont une fois par "
                                          "cycle ([inventaire] semaines_cycle, 8 par défaut). La feuille remplie se "
                                          "saisit dans Articles > Inventaire (« Saisir »)."), background=CARTE,
                             foreground=TEXTE_DOUX, anchor="w", justify="left", wraplength=860)
        self.etat.pack(fill="x", pady=(6, 0))
        self.tableau = tableau_simple(self, hauteur=14)
        self._plan()

    def _plan(self) -> None:
        from .cache_lectures import inventaire_clover
        from .page_rapports import remplir

        semaines = int(_config(self.racine).get("inventaire", {}).get("semaines_cycle", 8))

        def fin(articles):
            categories = [((a.get("categories") or {}).get("elements") or [{}])[0].get("name", "") for a in articles]
            plan = p3.plan_tournant(categories, semaines)
            actuelle = p3.semaine_du_cycle(date.today(), semaines)
            remplir(self.tableau, ["Semaine du cycle", "Catégories à compter"],
                    [[("▶ " if i == actuelle else "") + str(i + 1), ", ".join(c)] for i, c in enumerate(plan)],
                    {"Catégories à compter": 700}, decroissant=False)

        _fil(self, lambda: inventaire_clover(self.racine), fin, self.etat, "Lecture du catalogue Clover…")

    def feuille(self) -> None:
        def fin(r):
            chemin, categories, n = r
            self.etat.configure(text=t("✔ {n} ligne(s) à compter ({c}) : {f}", n=n, c=", ".join(categories),
                                       f=chemin.name), foreground=VERT_FONCE)
            os.startfile(chemin)

        _fil(self, lambda: p3.feuille_tournante(self.racine, _config(self.racine), date.today()), fin, self.etat,
             "Préparation de la feuille (Clover et Sage)…")


class FenetrePromotions(FenetreOutil):
    def __init__(self, parent, racine: Path, auteur: str = ""):
        from .page_rapports import tableau_simple

        super().__init__(parent)
        self.racine, self.auteur = Path(racine), auteur
        self.articles: dict[str, dict] = {}
        self.title(t("Promotions"))
        self.configure(background=CARTE, padx=14, pady=10)
        self.geometry("1100x600")
        from .page_points_vente import ChoixPointVente
        from .points_vente import visibles

        forme = Rangee(self)
        forme.pack(fill="x")
        self.choix_pv = ChoixPointVente(forme, lambda: visibles(self, _config(self.racine)), self._charger)
        forme.ajouter(self.choix_pv, 8)
        g = forme.ajouter(forme.groupe(), 8)
        tk.Label(g, text=t("Article"), background=CARTE).pack(side="left", padx=(0, 4))
        self.article = tk.StringVar()
        self.recherche = ChampRecherche(g, self.article, [], largeur=40)
        self.recherche.pack(side="left")
        g = forme.ajouter(forme.groupe(), 8)
        tk.Label(g, text=t("Prix promotionnel"), background=CARTE).pack(side="left", padx=(0, 4))
        self.prix = tk.StringVar()
        ttk.Entry(g, textvariable=self.prix, width=8).pack(side="left")
        g = forme.ajouter(forme.groupe(), 8)
        tk.Label(g, text=t("Du"), background=CARTE).pack(side="left")
        self.du = tk.StringVar(value=date.today().isoformat())
        ChampDate(g, self.du, fond=CARTE).pack(side="left", padx=4)
        tk.Label(g, text=t("au"), background=CARTE).pack(side="left")
        self.au = tk.StringVar(value=(date.today() + timedelta(days=6)).isoformat())
        ChampDate(g, self.au, fond=CARTE).pack(side="left", padx=4)
        forme.ajouter(Bouton(forme, "➕  " + t("Ajouter"), self.ajouter, fond=CARTE, petit=True), 8)
        barre = Rangee(self)
        barre.pack(fill="x", pady=(8, 0))
        barre.ajouter(Bouton(barre, "▶  " + t("Appliquer maintenant"), self.appliquer, "secondaire", fond=CARTE,
                             petit=True), 8)
        barre.ajouter(Bouton(barre, "📈  " + t("Calculer l'effet"), self.calculer_effet, "secondaire", fond=CARTE,
                             petit=True), 8)
        barre.ajouter(Bouton(barre, "✖  " + t("Annuler la promotion"), self.annuler, "danger", fond=CARTE, petit=True), 8)
        self.etat = tk.Label(self, text=t("Le traitement de nuit met le prix promotionnel le premier jour et remet le prix "
                                          "normal après le dernier jour."), background=CARTE, foreground=TEXTE_DOUX,
                             anchor="w", justify="left", wraplength=1050)
        self.etat.pack(fill="x", pady=(6, 0))
        self.tableau = tableau_simple(self, hauteur=15)
        barre.ajouter(bouton_exporter(barre, self.tableau, lambda: t("Promotions")))
        self.effets: dict[str, tuple] = {}
        self.afficher()
        self._charger()

    def _charger(self) -> None:
        from .cache_lectures import inventaire_clover

        def fin(articles):
            self.articles = {f"{a.get('name', '')} — {Decimal(int(a.get('price') or 0)) / 100} $": a
                             for a in articles if a.get("name")}
            self.recherche.configurer_valeurs(sorted(self.articles, key=str.casefold))

        pv = self.choix_pv.courant
        _fil(self, lambda: inventaire_clover(self.racine, pv), fin, self.etat, "Lecture du catalogue Clover…")

    def afficher(self) -> None:
        from .page_rapports import remplir

        self.liste = sorted(p3.Promotions(self.racine).liste, key=lambda p: p.du, reverse=True)
        lignes = []
        for p in self.liste:
            e = self.effets.get(p.numero)
            lignes.append([p.du, p.au, p.numero, p.point_vente or "1", p.nom, Decimal(p.prix_normal) if p.prix_normal else "",
                           Decimal(p.prix_promo), t(p.etat),
                           f"{e[1]} -> {e[0]}" if e else "", _argent(e[3]) + " -> " + _argent(e[2]) if e else "",
                           " ; ".join(p.messages[-2:])])
        remplir(self.tableau, ["Du", "au", "N°", "Point de vente", "Article", "Prix normal", "Prix promo", "État",
                               "Quantité (avant -> pendant)", "Ventes (avant -> pendant)", "Messages"], lignes,
                {"Article": 220, "Messages": 260})

    def ajouter(self) -> None:
        from .design import action_permise

        if not action_permise(self, "Changer les prix Clover (promotions)"):
            return
        a = self.articles.get(self.article.get())
        try:
            prix = Decimal(self.prix.get().replace(",", "."))
            p = p3.Promotions(self.racine).ajouter(a["id"] if a else "", (a or {}).get("name", ""), prix,
                                                   date.fromisoformat(self.du.get()), date.fromisoformat(self.au.get()),
                                                   self.auteur, self.choix_pv.courant.code if self.choix_pv.courant else "")
            if not a:
                raise ValueError("Choisissez un article de la liste.")
        except (InvalidOperation, ValueError, TypeError) as exc:
            self.etat.configure(text="✘ " + (t(str(exc)) if str(exc) else t("Prix promotionnel invalide.")),
                                foreground=ROUGE)
            return
        self.afficher()
        self.etat.configure(text=t("✔ {n} prévue.", n=p.numero), foreground=VERT_FONCE)

    def appliquer(self) -> None:
        from .design import action_permise

        if not action_permise(self, "Changer les prix Clover (promotions)"):
            return
        pv = self.choix_pv.courant

        def travail():
            from .points_vente import client

            return p3.appliquer_promotions(self.racine, client(self.racine, pv), code=pv.code if pv else "1")

        _fil(self, travail, lambda faits: (self.afficher(), self.etat.configure(
            text="\n".join(faits) or t("Rien à faire aujourd'hui."), foreground=TEXTE_DOUX)), self.etat,
             "Mise à jour des prix dans Clover…")

    def annuler(self) -> None:
        choix = self.tableau.selection()
        if not choix:
            return
        p = self.liste[int(choix[0])]
        if p.etat != p3.PREVUE:
            messagebox.showinfo(self.title(), t("Seule une promotion prévue s'annule ; une promotion en cours se "
                                                "termine à sa date de fin."), parent=self)
            return
        registre = p3.Promotions(self.racine)
        next(x for x in registre.liste if x.numero == p.numero).etat = p3.ANNULEE
        registre.enregistrer()
        self.afficher()

    def calculer_effet(self) -> None:
        def travail():
            from .points_vente import cache_clover, client as client_de, point_de_vente
            from .previsions import ventes_par_article_rapide

            config, effets = _config(self.racine), {}
            for p in self.liste:
                if p.etat not in (p3.EN_COURS, p3.TERMINEE):
                    continue
                pv = point_de_vente(config, p.point_vente or None)
                client, cache = client_de(self.racine, pv), cache_clover(self.racine, pv)
                du, au = date.fromisoformat(p.du), min(date.fromisoformat(p.au), date.today())
                duree = (au - du).days + 1
                pendant = ventes_par_article_rapide(client, du, au, cache)
                avant = ventes_par_article_rapide(client, du - timedelta(days=duree), du - timedelta(days=1), cache)
                effets[p.numero] = p3.effet(p, pendant, avant)
            return effets

        def fin(effets):
            self.effets = effets
            self.afficher()
            self.etat.configure(text=t("Effet = ventes pendant la promotion contre la même durée juste avant."),
                                foreground=TEXTE_DOUX)

        _fil(self, travail, fin, self.etat, "Lecture des ventes Clover…")


class FenetreRelances(FenetreOutil):
    def __init__(self, parent, racine: Path):
        from .page_rapports import tableau_simple

        super().__init__(parent)
        self.racine = Path(racine)
        self.clients: list = []
        self.title(t("Clients professionnels et relances"))
        self.configure(background=CARTE, padx=14, pady=10)
        self.geometry("1100x600")
        barre = Rangee(self)
        barre.pack(fill="x")
        barre.ajouter(Bouton(barre, "🔍  " + t("Lire dans Sage"), self.lire, fond=CARTE, petit=True), 8)
        barre.ajouter(Bouton(barre, "🖨  " + t("Imprimer la lettre de relance"), self.imprimer, "secondaire",
                             fond=CARTE, petit=True), 8)
        barre.ajouter(Bouton(barre, "✉  " + t("Envoyer la relance par courriel…"), self.envoyer, "secondaire",
                             fond=CARTE, petit=True), 8)
        self.etat = tk.Label(self, text=t("Factures ouvertes des clients de Sage (hors ventes Clover), limite de crédit et "
                                          "retards."), background=CARTE, foreground=TEXTE_DOUX, anchor="w")
        self.etat.pack(fill="x", pady=(6, 0))
        self.tableau = tableau_simple(self, hauteur=16)
        barre.ajouter(bouton_exporter(barre, self.tableau, lambda: t("Clients professionnels")))

    def lire(self) -> None:
        from .page_rapports import remplir

        def travail():
            from .__main__ import lire_sage
            from .facture import CLIENT
            from .points_vente import points_de_vente

            c = _config(self.racine)
            exclus = {CLIENT} | {p.client_sage for p in points_de_vente(c)}
            return lire_sage(c, lambda b: p3.clients_pro(b, date.today(), exclus),
                             c.get("sage_import", {}).get("fichier_entreprise"))

        def fin(clients):
            self.clients = clients
            relances = p3.derniere_relance(self.racine)
            remplir(self.tableau, ["Client", "Courriel", "Factures", "Solde", "Échu", "Plus de 30 jours",
                                   "Limite de crédit", "Dépassement", "Dernière relance"],
                    [[c.nom, c.courriel, len(c.factures), c.solde, c.echu, c.plus_30, c.limite or "",
                      t("Oui") if c.depasse else "", relances.get(c.nom, "")] for c in clients],
                    {"Client": 220, "Courriel": 200},
                    lambda i: ("retard",) if clients[i].plus_30 or clients[i].depasse else (), decroissant=False)
            self.tableau.tag_configure("retard", foreground=ROUGE)
            self.etat.configure(text=t("{n} client(s) avec des factures ouvertes.", n=len(clients)),
                                foreground=TEXTE_DOUX)

        _fil(self, travail, fin, self.etat, "Lecture des clients dans Sage…")

    def _client(self):
        choix = self.tableau.selection()
        if not choix:
            messagebox.showinfo(self.title(), t("Choisissez un client dans la liste."), parent=self)
            return None
        c = self.clients[int(choix[0])]
        if not c.echu:
            messagebox.showinfo(self.title(), t("{n} n'a aucune facture échue.", n=c.nom), parent=self)
            return None
        return c

    def imprimer(self) -> None:
        from .export_tableau import autorise, page_html

        c = self._client()
        if not c or not autorise(self):
            return
        entetes, lignes, sous = p3.lettre_relance(c, date.today())
        dossier = Path(tempfile.gettempdir()) / "MVOGMBI_Sync_impression"
        dossier.mkdir(exist_ok=True)
        chemin = dossier / f"relance_{datetime.now():%Y%m%d_%H%M%S}.html"
        chemin.write_text(page_html(t("Rappel de paiement"), entetes, lignes, sous_titre=sous, imprimer=True),
                          encoding="utf-8")
        os.startfile(chemin)
        p3.noter_relance(self.racine, c.nom, c.echu, "imprimée")

    def envoyer(self) -> None:
        from .design import action_permise

        if not action_permise(self, "Envoyer une relance par courriel"):
            return
        from .export_tableau import page_html, pdf_depuis_html

        c = self._client()
        if not c:
            return
        if not c.courriel:
            messagebox.showinfo(self.title(), t("{n} n'a pas de courriel dans sa fiche Sage.", n=c.nom), parent=self)
            return
        if not messagebox.askyesno(self.title(), t("Envoyer à {n} ({c}) un rappel de paiement de {m} ?", n=c.nom,
                                                   c=c.courriel, m=_argent(c.echu)), parent=self):
            return

        def travail():
            from .courriel import envoyer_a

            entetes, lignes, sous = p3.lettre_relance(c, date.today())
            with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as dossier:
                pdf = Path(dossier) / "rappel.pdf"
                pdf_depuis_html(page_html(t("Rappel de paiement"), entetes, lignes, sous_titre=sous), pdf)
                envoyer_a(_config(self.racine), c.courriel, f"Rappel de paiement — {c.nom}",
                          f"Bonjour,\n\nSauf erreur de notre part, des factures sont échues ({_argent(c.echu)}). Vous "
                          "trouverez le détail ci-joint.\n\nMerci de votre attention.\n",
                          [("Rappel de paiement.pdf", pdf.read_bytes())])
            p3.noter_relance(self.racine, c.nom, c.echu, "courriel")
            return c.nom

        _fil(self, travail, lambda nom: self.etat.configure(text=t("✔ Rappel envoyé à {n}.", n=nom),
                                                           foreground=VERT_FONCE), self.etat, "Envoi du rappel…")


class FenetreTableau(FenetreOutil):
    def __init__(self, parent, racine: Path):
        super().__init__(parent)
        self.racine = Path(racine)
        self.title(t("Tableau du gérant (téléphone)"))
        self.configure(background=CARTE, padx=14, pady=10)
        self.geometry("760x260")
        chemin = p3.dossier_tableau(self.racine, _config(self.racine)) / "tableau_du_gerant.html"
        tk.Label(self, text=t("Chaque nuit, le traitement automatique écrit une page légère (ventes d'hier, marge, "
                              "factures à payer, alertes) dans ce dossier ; avec OneDrive, elle s'ouvre sur le "
                              "téléphone. Elle contient des données de l'entreprise : ne la partagez pas."),
                 background=CARTE, foreground=TEXTE_DOUX, anchor="w", justify="left", wraplength=720).pack(fill="x")
        tk.Label(self, text=str(chemin), background=CARTE, anchor="w").pack(fill="x", pady=(8, 0))
        barre = Rangee(self)
        barre.pack(fill="x", pady=(10, 0))
        barre.ajouter(Bouton(barre, "🔄  " + t("Mettre à jour maintenant"), self.mettre_a_jour, fond=CARTE, petit=True),
                      8)
        barre.ajouter(Bouton(barre, "👁  " + t("Ouvrir la page"), lambda: os.startfile(chemin) if chemin.exists()
                             else None, "secondaire", fond=CARTE, petit=True))
        self.etat = tk.Label(self, text="", background=CARTE, foreground=TEXTE_DOUX, anchor="w")
        self.etat.pack(fill="x", pady=(8, 0))

    def mettre_a_jour(self) -> None:
        _fil(self, lambda: p3.ecrire_tableau(self.racine, _config(self.racine)),
             lambda chemin: self.etat.configure(text=t("✔ Page mise à jour : {f}", f=chemin.name), foreground=VERT_FONCE),
             self.etat, "Calcul du résumé (Clover et Sage)…")
