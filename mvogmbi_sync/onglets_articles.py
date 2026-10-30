"""Onglets « Produits inactifs » et « Articles 20/80 » de la page Rapports (rubrique État, demande du propriétaire du
2026-10-29). Calculs dans analyse_articles.py ; source Clover (par défaut) ou Sage, lue une fois par « Actualiser » /
« Calculer », filtres recalculés sans relire."""

from __future__ import annotations

import threading
import tkinter as tk
from datetime import date, timedelta
from tkinter import ttk

from . import analyse_articles as aa
from .design import TEXTE, TEXTE_DOUX, Bouton, ChampDate, Rangee, fond_de
from .export_tableau import bouton_exporter
from .langues import t

TOUTES = "Toutes les catégories"
SOURCES = ["Clover", "Sage"]
PERIODES = ["30 derniers jours", "90 derniers jours", "6 derniers mois", "12 derniers mois", "Cette année",
            "Période choisie"]
AFFICHAGES_PARETO = ["Les 20 % d'articles qui vendent le plus", "Les 50 % premiers (A et B)", "Toutes les classes"]
COULEURS_CLASSES = {"A": "#dff3e4", "B": "#fff4d6", "C": "#f3f4f3"}


def argent(v) -> str:
    return f"{v:,.2f} $".replace(",", " ").replace(".", ",")


def bornes(periode: str, aujourdhui: date) -> tuple[date, date] | None:
    """Période proposée -> (du, au), jusqu'à hier (la journée en cours n'est pas encore facturée)."""
    hier = aujourdhui - timedelta(days=1)
    jours = {"30 derniers jours": 30, "90 derniers jours": 90, "6 derniers mois": 182, "12 derniers mois": 365}
    if periode in jours:
        return hier - timedelta(days=jours[periode] - 1), hier
    if periode == "Cette année":
        return date(aujourdhui.year, 1, 1), max(hier, date(aujourdhui.year, 1, 1))
    return None


class _Onglet(ttk.Frame):
    """Base : lecture Sage par la page Rapports, liste des catégories, titre et tableau exportable."""

    titre = ""

    def __init__(self, page, notebook):
        super().__init__(notebook, padding=(0, 8, 0, 0))
        self.page, self.lu = page, False
        self.articles: dict[str, aa.ArticleSage] = {}
        self.barre = Rangee(self)
        self.barre.pack(fill="x")
        groupe = self.barre.ajouter(self.barre.groupe(), 10)
        ttk.Label(groupe, text=t("Source")).pack(side="left", padx=(0, 4))
        self.source = tk.StringVar(value=SOURCES[0])
        choix = ttk.Combobox(groupe, textvariable=self.source, values=SOURCES, state="readonly", width=8)
        choix.pack(side="left")
        choix.bind("<<ComboboxSelected>>", lambda _e: self.actualiser())

    def _fin_barre(self, explication: str) -> None:
        from .page_rapports import tableau_simple

        groupe = self.barre.ajouter(self.barre.groupe(), 10)
        ttk.Label(groupe, text=t("Catégorie")).pack(side="left", padx=(0, 4))
        self.categorie = tk.StringVar(value=t(TOUTES))
        self.choix_categorie = ttk.Combobox(groupe, textvariable=self.categorie, values=[t(TOUTES)],
                                            state="readonly", width=24)
        self.choix_categorie.pack(side="left")
        self.choix_categorie.bind("<<ComboboxSelected>>", lambda _e: self.afficher())
        self.etat = ttk.Label(self, text=t(explication), foreground=TEXTE_DOUX, padding=(0, 6), wraplength=1100,
                              justify="left")
        self.etat.pack(fill="x")
        self.libelle = tk.Label(self, text=t(self.titre), font=("Segoe UI Semibold", 10), foreground=TEXTE,
                                background=fond_de(self), anchor="w")
        self.libelle.pack(fill="x")
        self.tableau = tableau_simple(self, hauteur=16)
        self.barre.ajouter(bouton_exporter(self.barre, self.tableau, lambda: self.libelle.cget("text")))

    def _clover(self) -> bool:
        return self.source.get() == "Clover"

    def _premiere(self, entetes: list[str]) -> list[str]:
        """En-têtes selon la source : ID Clover et coût Clover, ou n° Sage et CUMP."""
        if not self._clover():
            return entetes
        return [{"N° Sage": "ID Clover", "CUMP": "Coût Clover"}.get(e, e) for e in entetes]

    def _lire_clover(self, du: date, au: date, fin) -> None:
        """Ventes Clover de la période (jours terminés gardés en cache) et catalogue (stock, coût), dans un fil ;
        puis fin(articles, ventes par article)."""
        racine = self.page.racine
        self.etat.configure(text=t("Lecture des ventes et des articles dans Clover (la première fois peut prendre "
                                   "une minute, ensuite quelques secondes)…"))

        def travail():
            try:
                from .__main__ import charger_config
                from .api_clover import ClientClover
                from .previsions import ventes_par_article_rapide

                client = ClientClover(charger_config(racine / "config.toml"))
                from .cache_lectures import inventaire_clover

                items = inventaire_clover(racine)  # catalogue gardé quelques minutes
                ventes = ventes_par_article_rapide(client, du, au, racine / "donnees" / "cache_clover")
                self.after(0, lambda: fin(items, ventes))
            except BaseException as exc:  # SystemExit compris (jeton absent)
                texte = str(exc) or type(exc).__name__
                self.after(0, lambda: self.etat.configure(text="✘ " + texte))

        threading.Thread(target=travail, daemon=True).start()

    def _categorie(self) -> str:
        valeur = self.categorie.get()
        return "" if valeur == t(TOUTES) else valeur

    def _categories(self) -> None:
        noms = sorted({a.categorie for a in self.articles.values()}, key=str.casefold)
        self.choix_categorie.configure(values=[t(TOUTES)] + noms)

    def premiere_fois(self) -> None:
        if not self.lu:
            self.lu = True
            self.actualiser()

    def afficher(self) -> None:
        raise NotImplementedError

    def actualiser(self) -> None:
        raise NotImplementedError


class OngletInactifs(_Onglet):
    titre = "Produits inactifs"

    def __init__(self, page, notebook):
        super().__init__(page, notebook)
        groupe = self.barre.ajouter(self.barre.groupe(), 10)
        ttk.Label(groupe, text=t("Sans vente depuis au moins")).pack(side="left", padx=(0, 4))
        self.jours = tk.StringVar(value="30")
        choix = ttk.Combobox(groupe, textvariable=self.jours, values=[str(j) for j in aa.SEUILS_INACTIVITE],
                             width=6)
        choix.pack(side="left")
        choix.bind("<<ComboboxSelected>>", lambda _e: self.afficher())
        choix.bind("<Return>", lambda _e: self.afficher())
        ttk.Label(groupe, text=t("jours")).pack(side="left", padx=(4, 0))
        self.avec_stock = tk.BooleanVar(value=False)
        self.barre.ajouter(ttk.Checkbutton(self.barre, text=t("Seulement les articles en stock"),
                                           variable=self.avec_stock, command=self.afficher), 10)
        self.barre.ajouter(Bouton(self.barre, "🔄  " + t("Actualiser"), self.actualiser, petit=True), 10)
        self._fin_barre("Articles (Clover, ou articles de stock actifs de Sage) qui n'ont pas été vendus depuis le nombre de jours choisi "
                        "(30, 60, 90… ou un autre nombre), ou jamais vendus ; la plus grande valeur de stock en haut.")
        for cle, couleur in (("jamais", "#fde2e4"), ("stock", "#fff4d6")):
            self.tableau.tag_configure(cle, background=couleur)

    def actualiser(self) -> None:
        racine = self.page.racine
        self.lu = True

        def fin(articles):
            self.articles = articles
            self._categories()
            self.afficher()

        if self._clover():  # dernière vente cherchée sur 365 jours, journée en cours comprise
            aujourdhui = date.today()
            self._lire_clover(aujourdhui - timedelta(days=aa.JOURS_CLOVER), aujourdhui,
                              lambda items, ventes: fin(aa.articles_clover(items, ventes)))
            return
        self.page._lire_sage(lambda base: aa.lire_articles(base, aa.categories(racine)), fin,
                             t("Lecture des articles, des ventes et du stock dans Sage…"), self.etat)

    def afficher(self) -> None:
        from .page_rapports import remplir

        if not self.articles:
            return
        try:
            jours = max(1, int(self.jours.get().strip()))
        except ValueError:
            jours = 30
            self.jours.set("30")
        jamais = aa.JAMAIS_CLOVER if self._clover() else aa.JAMAIS_SAGE
        lignes, resume = aa.produits_inactifs(self.articles, jours, date.today(), self.avec_stock.get(),
                                              self._categorie(), jamais)
        valeurs = [l[:3] + [t(l[3]) if l[3] == jamais else l[3], l[4], t(l[5])] + l[6:] for l in lignes]
        entetes = self._premiere(aa.ENTETES_INACTIFS)
        if self._clover():  # aucun achat dans Clover
            valeurs = [v[:6] + v[7:] for v in valeurs]
            entetes = entetes[:6] + entetes[7:]
        remplir(self.tableau, entetes, valeurs, {
            "N° Sage": 110, "ID Clover": 120, "Article": 260, "Catégorie": 150, "Dernière vente": 105,
            "Jours sans vente": 105, "Tranche": 150, "Dernier achat": 105, "Stock": 80, "CUMP": 90,
            "Coût Clover": 90, "Valeur du stock": 110},
            lambda i: ("jamais",) if lignes[i][4] == "" else (("stock",) if lignes[i][7] > 0 else ()),
            decroissant=False)
        self.libelle.configure(text=t("Produits sans vente depuis {n} jours ou plus", n=jours)
                               + f" ({self.source.get()})")
        ordre = [aa.tranche(j, jamais) for j in aa.SEUILS_INACTIVITE] + [jamais]  # de 30 jours à jamais vendu
        tranches = "  •  ".join(f"{t(k)} : {resume['tranches'][k]}" for k in ordre if k in resume["tranches"])
        self.etat.configure(text=t("{n} article(s) inactif(s) sur {total} — jamais vendus : {j}, encore en stock : {s}, "
                                   "valeur du stock immobilisé : {v}", n=resume["articles"],
                                   total=sum(1 for a in self.articles.values() if a.catalogue),
                                   j=resume["jamais"], s=resume["en_stock"], v=argent(resume["valeur"]))
                           + (f"\n{tranches}" if tranches else ""))


class OngletPareto(_Onglet):
    titre = "Articles 20/80"

    def __init__(self, page, notebook):
        super().__init__(page, notebook)
        self.ventes: dict = {}
        self.jours_periode = 0
        groupe = self.barre.ajouter(self.barre.groupe(), 10)
        ttk.Label(groupe, text=t("Période")).pack(side="left", padx=(0, 4))
        self.periode = tk.StringVar(value=t(PERIODES[1]))
        choix = ttk.Combobox(groupe, textvariable=self.periode, values=[t(p) for p in PERIODES], state="readonly",
                             width=18)
        choix.pack(side="left")
        choix.bind("<<ComboboxSelected>>", lambda _e: self._periode_choisie())
        dates = self.barre.ajouter(self.barre.groupe(), 10)
        ttk.Label(dates, text=t("du")).pack(side="left", padx=(0, 4))
        self.du, self.au = tk.StringVar(), tk.StringVar()
        ChampDate(dates, self.du).pack(side="left")
        ttk.Label(dates, text=t("au")).pack(side="left", padx=4)
        ChampDate(dates, self.au).pack(side="left")
        self._periode_choisie(lire=False)
        groupe = self.barre.ajouter(self.barre.groupe(), 10)
        ttk.Label(groupe, text=t("Afficher")).pack(side="left", padx=(0, 4))
        self.affichage = tk.StringVar(value=t(AFFICHAGES_PARETO[0]))
        choix = ttk.Combobox(groupe, textvariable=self.affichage, values=[t(a) for a in AFFICHAGES_PARETO],
                             state="readonly", width=30)
        choix.pack(side="left")
        choix.bind("<<ComboboxSelected>>", lambda _e: self.afficher())
        self.barre.ajouter(Bouton(self.barre, "🔍  " + t("Calculer"), self.actualiser, petit=True), 10)
        self._fin_barre("Ventes nettes de la période (Clover, ou factures de vente de Sage), de l'article le plus vendu au moins vendu : "
                        "classe A = les 20 % d'articles qui vendent le plus, B = les 30 % suivants, C = le reste ; "
                        "stock actuel, valeur du stock (coût Clover, ou CUMP de Sage) et couverture en jours de "
                        "vente.")
        for classe, couleur in COULEURS_CLASSES.items():
            self.tableau.tag_configure(classe, background=couleur)

    def _periode_choisie(self, lire: bool = True) -> None:
        periode = next((p for p in PERIODES if t(p) == self.periode.get()), PERIODES[1])
        dates = bornes(periode, date.today())
        if dates:
            self.du.set(dates[0].isoformat())
            self.au.set(dates[1].isoformat())
            if lire and self.lu:
                self.actualiser()

    def _dates(self) -> tuple[date, date] | None:
        try:
            du, au = date.fromisoformat(self.du.get().strip()), date.fromisoformat(self.au.get().strip())
        except ValueError:
            return None
        return (du, au) if du <= au else None

    def actualiser(self) -> None:
        dates = self._dates()
        if not dates:
            self.etat.configure(text="✘ " + t("Période invalide : dates au format AAAA-MM-JJ, « du » avant « au »."))
            return
        self.lu = True
        du, au = dates
        racine = self.page.racine
        if self._clover():
            def fin_clover(items, ventes):
                self.articles, self.ventes = aa.articles_clover(items, ventes), aa.ventes_clover(ventes)
                self.jours_periode, self.periode_lue = (au - du).days + 1, (du, au)
                self._categories()
                self.afficher()

            self._lire_clover(du, au, fin_clover)
            return

        def lire(base):
            return aa.lire_articles(base, aa.categories(racine)), aa.lire_ventes(base, du, au)

        def fin(resultat):
            self.articles, self.ventes = resultat
            self.jours_periode = (au - du).days + 1
            self.periode_lue = (du, au)
            self._categories()
            self.afficher()

        self.page._lire_sage(lire, fin, t("Lecture des ventes et du stock dans Sage…"), self.etat)

    def afficher(self) -> None:
        from .page_rapports import remplir

        if not getattr(self, "periode_lue", None):
            return
        lignes, resume = aa.pareto(self.articles, self.ventes, self.jours_periode, self._categorie())
        choix = next((a for a in AFFICHAGES_PARETO if t(a) == self.affichage.get()), AFFICHAGES_PARETO[0])
        classes = {AFFICHAGES_PARETO[0]: "A", AFFICHAGES_PARETO[1]: "AB"}.get(choix, "ABC")
        visibles = [l for l in lignes if l[1] in classes]
        valeurs = [l[:-1] + [t(l[-1]) if l[-1] else ""] for l in visibles]
        remplir(self.tableau, self._premiere(aa.ENTETES_PARETO), valeurs, {
            "Rang": 50, "Classe": 55, "N° Sage": 105, "ID Clover": 120, "Coût Clover": 85, "Article": 240, "Catégorie": 140, "Quantité vendue": 100,
            "Ventes": 105, "Part (%)": 70, "Cumul (%)": 75, "Prix moyen": 85, "Stock": 75, "CUMP": 85,
            "Valeur du stock": 105, "Couverture (jours)": 110, "Contrôle": 220},
            lambda i: (visibles[i][1],), decroissant=False)
        du, au = self.periode_lue
        self.libelle.configure(text=t("Articles 20/80 du {du} au {au}", du=du.isoformat(), au=au.isoformat())
                               + f" ({self.source.get()})")
        if not lignes:
            self.etat.configure(text=t("Aucune vente sur cette période."))
            return
        ventes_a = (resume["ventes_A"] / resume["ventes"] * 100).quantize(aa.Decimal("0.1")) if resume["ventes"] else 0
        texte = t("Les 20 % d'articles qui vendent le plus ({a} sur {n} articles vendus) font {pa} % de votre chiffre "
                  "d'affaires ({va} sur {v}) — valeur de leur stock : {sa} ; de tous les articles vendus : {s}",
                  a=resume["A"], n=resume["articles"], pa=str(ventes_a).replace(".", ","),
                  va=argent(resume["ventes_A"]), v=argent(resume["ventes"]), sa=argent(resume["valeur_A"]),
                  s=argent(resume["valeur"]))
        if resume["douteux"]:
            texte += "\n" + t("{n} valeur(s) de stock douteuse(s) (coût plus de 5 fois le prix de vente) laissée(s) hors "
                              "des totaux : à vérifier.", n=resume["douteux"])
        self.etat.configure(text=texte)
