"""Page « 11. Rapports » : suivi complet des ventes, recherches dans l'historique de Sage (client, fournisseur, vente,
encaissement, paiement, article) et factures fournisseurs archivées."""

from __future__ import annotations

import os
import re
import threading
import tkinter as tk
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from tkinter import messagebox, ttk

from .design import (CARTE, MENU_ACTIF, MENU_FOND, MENU_SURVOL, ROUGE, TEXTE, TEXTE_DOUX, VERT_FONCE, Bouton,
                     ChampDate, ChampRecherche, cadre_tableau, entete_page, fond_de, rayer)
from .export_tableau import bouton_exporter
from .langues import t

# couleurs des lignes du suivi : vente bloquée, à encaisser, encaissée mais pas retrouvée sur les relevés
COULEURS = {"bloquee": "#fde2e4", "a_encaisser": "#fff4d6", "a_rapprocher": "#eaf2fb"}
# Menu des statistiques Clover : (icône, section, [(libellé, vue de statistiques_clover ou page)])
NAVIGATION = [
    ("🏠", "Accueil", [("Accueil", "accueil")]),
    ("🧾", "Activités de vente", [("Commandes", "Commandes"), ("Transactions", "Paiements"),
                                  ("Remboursements", "Remboursements")]),
    ("📊", "Rapports", [("Aperçu des ventes", "Résumé"), ("Ventes par jour", "Par jour"),
                       ("Jours de la semaine", "Par jour de la semaine"), ("Ventes par heure", "Par heure"),
                       ("Ventes d'articles", "Par article"), ("Ventes par employé", "Par employé"),
                       ("Modes de paiement", "Par mode de paiement"), ("Rabais", "Rabais"),
                       ("Appareils", "Par appareil")]),
    ("🏦", "Finances", [("Modes de paiement", "Par mode de paiement"), ("Types de carte", "Par type de carte"),
                       ("Saisie des cartes", "Par mode de saisie de la carte")]),
    ("🏷", "Articles", [("Ventes d'articles", "Par article"), ("Catégories", "Par catégorie"),
                       ("Péremption", "peremption")]),
    ("👤", "Employés", [("Ventes par employé", "Par employé")]),
    ("👥", "Clients", [("Liste des clients", "Par client")]),
    ("📈", "Prévisions", [("Prévision des ventes", "prev_ventes"), ("Prévision des achats", "prev_achats"),
                         ("Articles à commander", "prev_commande")]),
]
PREVISIONS = ("prev_ventes", "prev_achats", "prev_commande")
HORIZONS = (7, 10, 14, 21, 28, 30, 45, 60, 90)  # jours : horizon des prévisions et période des articles à commander
# graphique au-dessus de chaque état : (genre, colonne de l'étiquette, colonne de la valeur)
GRAPHIQUES_ETATS = {
    "Par jour": ("courbe", 0, 2), "Par heure": ("barres", 0, 2), "Par jour de la semaine": ("barres", 0, 2),
    "Par mode de paiement": ("anneau", 0, 2), "Par type de carte": ("anneau", 0, 2),
    "Par mode de saisie de la carte": ("anneau", 0, 2), "Par catégorie": ("anneau", 0, 2),
    "Par appareil": ("anneau", 0, 2), "Par article": ("classement", 0, 6), "Par employé": ("classement", 0, 2),
    "Par client": ("classement", 0, 2), "Rabais": ("classement", 0, 2), "prev_achats": ("classement", 0, 7),
}
NOTES_ETATS: dict[str, str] = {}   # texte sous le titre d'un état (prévisions)
A_COMMANDER_TEXTE = "À commander"
FILTRES_PEREMPTION = ["Bientôt périmés (3 mois ou moins)", "Périmés", "Un mois ou moins", "De 1 à 3 mois",
                      "Plus de 3 mois", "Tous"]
COULEURS_PEREMPTION = {"rouge": "#f8c9cf", "orange": "#ffe3a8", "neutre": "#eef1ef"}
FILTRES_SUIVI = ["Toutes", "Bloquées ou en échec", "Non encaissées", "Non rapprochées"]
TYPES_RECHERCHE = ["Client", "Fournisseur", "Vente", "Encaissement", "Paiement", "Article"]
EXTENSIBLES = {"Commentaire", "Description", "Client / fournisseur", "Fournisseur", "Client", "Article Sage", "Article",
               "Indicateur", "Appareil", "Employé", "Mode(s) de paiement"}
COLONNES_ARCHIVES = (("date", "Date", 90), ("fournisseur", "Fournisseur", 260), ("numero", "N°", 110),
                     ("total", "Total", 100), ("lignes", "Lignes", 70), ("archivee", "Archivée le", 150))


MODELES = [  # textes du suivi composés dans rapports.py : traduits à l'affichage
    (re.compile(r"^Partielle : reste (.+)$"), "Partielle : reste {0}"),
    (re.compile(r"^Reste (.+)$"), "Reste {0}"),
    (re.compile(r"^Encaissée \((\d+) encaissement\(s\)\)$"), "Encaissée ({0} encaissement(s))"),
    (re.compile(r"^En partie \((\d+) sur (\d+)\)$"), "En partie ({0} sur {1})"),
    (re.compile(r"^Import : (.+)$"), "Import : {0}"),
]


def traduire(texte: str) -> str:
    """Texte du suivi dans la langue de l'application (morceaux fixes et modèles avec valeurs)."""
    for modele, cle in MODELES:
        trouve = modele.match(texte)
        if trouve:
            return t(cle).format(*(t(g) for g in trouve.groups()))
    return " — ".join(t(x) for x in texte.split(" — "))


def montant(valeur) -> str:
    """« 1 234,56 $ » comme la page Rapprochement."""
    return f"{valeur:,.2f} $".replace(",", " ").replace(".", ",") if valeur is not None else ""


def tableau_simple(parent, hauteur: int = 12) -> ttk.Treeview:
    cadre = cadre_tableau(parent)
    cadre.pack(fill="both", expand=True, pady=(6, 0))
    tableau = ttk.Treeview(cadre, show="headings", height=hauteur, selectmode="browse")
    defil = ttk.Scrollbar(cadre, orient="vertical", command=tableau.yview)
    tableau.configure(yscrollcommand=defil.set)
    tableau.pack(side="left", fill="both", expand=True)
    defil.pack(side="right", fill="y")
    return tableau


def remplir(tableau: ttk.Treeview, entetes: list[str], lignes: list[list], largeurs: dict[str, int] | None = None,
            tags=None) -> None:
    """Colonnes et lignes d'un tableau de résultats ; montants en « 1 234,56 $ », quantités telles quelles."""
    tableau.delete(*tableau.get_children())
    cles = [f"c{i}" for i in range(len(entetes))]
    tableau.configure(columns=cles, displaycolumns=cles)
    for cle, entete in zip(cles, entetes):
        texte = t(entete)
        tableau.heading(cle, text=texte)
        nombre = any(isinstance(l[cles.index(cle)], (Decimal, int)) and not isinstance(l[cles.index(cle)], bool)
                     for l in lignes[:20] if len(l) > cles.index(cle))
        largeur = (largeurs or {}).get(entete, 95 if nombre else 140)
        extensible = entete in EXTENSIBLES  # garde au moins sa largeur : les colonnes de chiffres restent fixes
        tableau.column(cle, width=largeur, minwidth=largeur if extensible else 40, anchor="e" if nombre else "w",
                       stretch=extensible)
    for i, ligne in enumerate(lignes):
        valeurs = []
        for entete, v in zip(entetes, ligne):
            if isinstance(v, Decimal):
                if "%" in entete:
                    v = f"{v} %".replace(".", ",")
                elif any(m in entete for m in ("Quantité", "Cumul", "Vendu", "Stock", "Besoin", "À acheter", "Sold")):
                    v = f"{v.normalize():f}".replace(".", ",")
                else:
                    v = montant(v)
            valeurs.append("" if v is None else v)
        tableau.insert("", "end", iid=str(i), values=valeurs, tags=tags(i) if tags else ())
    rayer(tableau)


class PageRapports(ttk.Frame):
    def __init__(self, parent, racine: Path, titre: str):
        super().__init__(parent, padding=10)
        self.racine, self.titre = Path(racine), titre
        self.suivi = []
        self.listes: dict[str, list[str]] = {}   # clients, fournisseurs, articles lus dans Sage (une fois)
        self.archives = []

        entete_page(self, "📊", t("Rapports"),
                    t("suivi complet des ventes, historique de Sage et factures fournisseurs archivées")).pack(fill="x")
        self.onglets = ttk.Notebook(self)
        self.onglets.pack(fill="both", expand=True)
        self._onglet_suivi()
        self._onglet_recherche()
        self._onglet_archives()
        self._onglet_statistiques()
        self.onglets.bind("<<NotebookTabChanged>>", lambda _e: self._au_changement())

    def _config(self) -> dict:
        import tomllib

        chemin = self.racine / "config.toml"
        return tomllib.loads(chemin.read_text(encoding="utf-8")) if chemin.exists() else {}

    def _lire_sage(self, fonction, fin, message: str, etiquette: ttk.Label) -> None:
        """Lit Sage dans un fil (l'application l'ouvre elle-même s'il est fermé), puis fin(résultat) ; le message et
        une éventuelle erreur s'affichent dans `etiquette`."""
        etiquette.configure(text=message)

        def travail():
            try:
                from .__main__ import lire_sage

                config = self._config()
                resultat = lire_sage(config, fonction, config.get("sage_import", {}).get("fichier_entreprise"))
                self.after(0, lambda: fin(resultat))
            except Exception as exc:
                texte = str(exc)
                self.after(0, lambda: etiquette.configure(text="✘ " + texte))

        threading.Thread(target=travail, daemon=True).start()

    # ---------------------------------------------------------------- suivi des ventes
    def _onglet_suivi(self) -> None:
        cadre = ttk.Frame(self.onglets, padding=(0, 8, 0, 0))
        self.onglets.add(cadre, text="  " + t("Suivi des ventes") + "  ")
        barre = ttk.Frame(cadre)
        barre.pack(fill="x")
        Bouton(barre, "🔄  " + t("Actualiser"), self.actualiser).pack(side="left")
        ttk.Label(barre, text=t("Afficher :")).pack(side="left", padx=(16, 4))
        self.filtre_suivi = tk.StringVar(value=t(FILTRES_SUIVI[0]))
        choix = ttk.Combobox(barre, textvariable=self.filtre_suivi, values=[t(f) for f in FILTRES_SUIVI],
                             state="readonly", width=24)
        choix.pack(side="left")
        choix.bind("<<ComboboxSelected>>", lambda _e: self.afficher_suivi())
        ttk.Label(barre, text=t("Rechercher :")).pack(side="left", padx=(16, 4))
        self.texte_suivi = tk.StringVar()
        champ = ttk.Entry(barre, textvariable=self.texte_suivi, width=22)
        champ.pack(side="left")
        champ.bind("<KeyRelease>", lambda _e: self.afficher_suivi())
        self.etat = ttk.Label(cadre, text=t("Cliquez sur « Actualiser » : historique des traitements, Sage et relevés."),
                              foreground=TEXTE_DOUX, padding=(0, 6))
        self.etat.pack(fill="x")
        self.tableau_suivi = tableau_simple(cadre)
        for cle, couleur in COULEURS.items():
            self.tableau_suivi.tag_configure(cle, background=couleur)
        bouton_exporter(barre, self.tableau_suivi, t("Suivi des ventes")).pack(side="right")

    def actualiser(self) -> None:
        from .encaissements import numero_compte_sage
        from .facture import CLIENT
        from .rapports import suivi_ventes

        compte = numero_compte_sage(str(self._config().get("encaissements", {}).get("compte_depot", "1055")))

        def fin(suivi):
            self.suivi = suivi
            self.afficher_suivi()

        self._lire_sage(lambda base: suivi_ventes(self.racine, base, CLIENT, compte), fin,
                        t("Lecture de l'historique, de Sage et des relevés…"), self.etat)

    def afficher_suivi(self) -> None:
        from .rapports import ENTETES_SUIVI

        filtre, texte = self.filtre_suivi.get(), self.texte_suivi.get().strip().casefold()
        lignes = []
        for l in self.suivi:
            bloquee = any(m in l.statut for m in ("Bloquée", "Échec", "ÉCHEC", "Import :"))
            if filtre == t("Bloquées ou en échec") and not bloquee:
                continue
            if filtre == t("Non encaissées") and (bloquee or l.encaissement.startswith("Encaissée")):
                continue
            if filtre == t("Non rapprochées") and l.rapprochement in ("Rapproché", "—"):
                continue
            if texte and not any(texte in str(v).casefold() for v in l.valeurs() + [l.facture]):
                continue
            lignes.append(l)
        valeurs = [[l.traitement, l.journee, traduire(l.statut), l.ht, l.taxes, l.ttc, traduire(l.commentaire),
                    traduire(l.encaissement), traduire(l.rapprochement)] for l in lignes]

        def couleur(i):
            l = lignes[i]
            if any(m in l.statut for m in ("Bloquée", "Échec", "ÉCHEC", "Import :")):
                return ("bloquee",)
            if l.encaissement not in ("—",) and not l.encaissement.startswith("Encaissée"):
                return ("a_encaisser",)
            if l.rapprochement in ("Non rapproché",) or l.rapprochement.startswith("En partie"):
                return ("a_rapprocher",)
            return ()

        remplir(self.tableau_suivi, ENTETES_SUIVI, valeurs, {
            "Date de traitement": 108, "Journée": 150, "Statut": 112, "Montant HT": 88, "Taxes": 64, "Montant TTC": 92,
            "Commentaire": 160, "État de l'encaissement": 155, "État du rapprochement": 112}, couleur)
        importees = sum(1 for l in self.suivi if l.statut in ("Facture importée", "Dans Sage"))
        self.etat.configure(text=t("{n} vente(s) affichée(s) sur {total} — dans Sage : {s}, bloquées ou en échec : {b}, "
                                   "non encaissées : {e}, non rapprochées : {r}", n=len(lignes), total=len(self.suivi),
                                   s=importees,
                                   b=sum(1 for l in self.suivi if any(m in l.statut for m in ("Bloquée", "Échec",
                                                                                               "ÉCHEC", "Import :"))),
                                   e=sum(1 for l in self.suivi if l.encaissement not in ("—",)
                                         and not l.encaissement.startswith("Encaissée")),
                                   r=sum(1 for l in self.suivi if l.rapprochement == "Non rapproché")))

    # ---------------------------------------------------------------- recherches
    def _onglet_recherche(self) -> None:
        cadre = ttk.Frame(self.onglets, padding=(0, 8, 0, 0))
        self.onglets.add(cadre, text="  " + t("Recherche dans l'historique") + "  ")
        barre = ttk.Frame(cadre)
        barre.pack(fill="x")
        ttk.Label(barre, text=t("Rechercher :")).pack(side="left", padx=(0, 4))
        self.type_recherche = tk.StringVar(value=t(TYPES_RECHERCHE[0]))
        choix = ttk.Combobox(barre, textvariable=self.type_recherche, values=[t(x) for x in TYPES_RECHERCHE],
                             state="readonly", width=14)
        choix.pack(side="left")
        choix.bind("<<ComboboxSelected>>", lambda _e: self._preparer_recherche())
        self.valeur = tk.StringVar()
        self.champ_valeur = ChampRecherche(barre, self.valeur, [], largeur=46)
        self.champ_valeur.pack(side="left", padx=6)
        periode = ttk.Frame(cadre)  # deuxième ligne : période et bouton
        periode.pack(fill="x", pady=(6, 0))
        ttk.Label(periode, text=t("Période du")).pack(side="left", padx=(0, 4))
        self.du = tk.StringVar()
        ChampDate(periode, self.du).pack(side="left")
        ttk.Label(periode, text=t("au")).pack(side="left", padx=4)
        self.au = tk.StringVar()
        ChampDate(periode, self.au).pack(side="left")
        Bouton(periode, "🔍  " + t("Rechercher"), self.rechercher, petit=True).pack(side="left", padx=8)
        self.aide_recherche = ttk.Label(cadre, text="", foreground=TEXTE_DOUX, padding=(0, 6))
        self.aide_recherche.pack(fill="x")
        self.tableau_recherche = tableau_simple(cadre)
        bouton_exporter(barre, self.tableau_recherche, t("Recherche")).pack(side="right")
        self._preparer_recherche(lire=False)

    def _type(self) -> str:
        return next(x for x in TYPES_RECHERCHE if t(x) == self.type_recherche.get())

    def _preparer_recherche(self, lire: bool = True) -> None:
        """Client, fournisseur, article : liste tirée de Sage (lue une fois) ; sinon texte libre (facultatif)."""
        from . import rapports

        type_ = self._type()
        self.valeur.set("")
        aides = {"Client": "Choisissez le client : ses factures et encaissements, avec le solde.",
                 "Fournisseur": "Choisissez le fournisseur : factures, paiements et notes de crédit, avec le solde dû.",
                 "Article": "Choisissez l'article (n° ou nom) : ventes, achats, retours et ajustements, avec le cumul.",
                 "Vente": "Texte facultatif (n° de facture, client, montant) et période.",
                 "Encaissement": "Texte facultatif (client, facture, n° d'encaissement, montant) et période.",
                 "Paiement": "Texte facultatif (fournisseur, facture, pièce, montant) et période."}
        self.aide_recherche.configure(text=t(aides[type_]))
        sources = {"Client": lambda b: rapports.noms(b, "tcustomr"),
                   "Fournisseur": lambda b: rapports.noms(b, "tvendor"), "Article": rapports.articles}
        if type_ not in sources:
            self.champ_valeur.configurer_valeurs([])
            return
        if type_ in self.listes:
            self.champ_valeur.configurer_valeurs(self.listes[type_])
        elif lire:
            def fin(valeurs):
                self.listes[type_] = valeurs
                self.champ_valeur.configurer_valeurs(valeurs)
                self.aide_recherche.configure(text=t(aides[type_]))

            self._lire_sage(sources[type_], fin, t("Lecture de la liste dans Sage…"), self.aide_recherche)

    def _date(self, variable: tk.StringVar) -> date | None:
        texte = variable.get().strip()
        return date.fromisoformat(texte) if texte else None

    def rechercher(self) -> None:
        from . import rapports

        type_, valeur = self._type(), self.valeur.get().strip()
        try:
            du, au = self._date(self.du), self._date(self.au)
        except ValueError:
            messagebox.showwarning(self.titre, t("Date invalide : utilisez le format AAAA-MM-JJ (ou le calendrier 📅)."))
            return
        if type_ in ("Client", "Fournisseur", "Article") and not valeur:
            messagebox.showinfo(self.titre, t("Choisissez d'abord dans la liste : {quoi}.", quoi=t(type_).lower()))
            return
        fonctions = {
            "Client": lambda b: rapports.mouvements_client(b, valeur, du, au),
            "Fournisseur": lambda b: rapports.mouvements_fournisseur(b, valeur, du, au),
            "Article": lambda b: rapports.mouvements_article(b, valeur.split(" — ")[0].strip(), du, au),
            "Vente": lambda b: rapports.recherche_ventes(b, valeur, du, au),
            "Encaissement": lambda b: rapports.recherche_encaissements(b, valeur, du, au),
            "Paiement": lambda b: rapports.recherche_paiements(b, valeur, du, au)}

        def fin(resultat):
            entetes, lignes = resultat
            remplir(self.tableau_recherche, entetes, lignes, {"Client / fournisseur": 220, "Facture": 170})
            self.aide_recherche.configure(text=t("{n} résultat(s).", n=len(lignes)))

        self._lire_sage(fonctions[type_], fin, t("Recherche dans Sage…"), self.aide_recherche)

    # ---------------------------------------------------------------- statistiques Clover
    INDICATEURS = (("Ventes brutes", "Ventes brutes (articles)", True),
                   ("Ventes nettes", "Ventes nettes (articles)", True), ("Commandes", "Commandes payées", False),
                   ("Panier moyen", "Panier moyen", True), ("Montant perçu", "Montant encaissé (paiements)", True),
                   ("Taxes", "Taxes encaissées", True), ("Rabais", "Rabais", True),
                   ("Remboursements", "Remboursements (articles)", True))

    def _onglet_statistiques(self) -> None:
        from .graphiques import Graphique

        cadre = ttk.Frame(self.onglets, padding=(0, 8, 0, 0))
        self.onglets.add(cadre, text="  " + t("Statistiques Clover") + "  ")
        barre = ttk.Frame(cadre)
        barre.pack(fill="x")
        # filtre de date comme Clover : un bouton « 📅 Aujourd'hui ⌄ » qui ouvre la liste des périodes
        self.nom_periode = "Aujourd'hui"
        self.stat_du = tk.StringVar(value=date.today().isoformat())
        self.stat_au = tk.StringVar(value=date.today().isoformat())
        self.bouton_periode = Bouton(barre, "📅  " + t("Aujourd'hui") + "  ⌄", self._menu_periodes, "secondaire",
                                     largeur=250)
        self.bouton_periode.pack(side="left")
        self.libelle_periode = ttk.Label(barre, text="", foreground=TEXTE_DOUX)
        self.libelle_periode.pack(side="left", padx=10)
        Bouton(barre, "🔄  " + t("Actualiser"), self.calculer_statistiques, petit=True).pack(side="left")
        self.auto = tk.BooleanVar(value=True)
        ttk.Checkbutton(barre, text=t("Journée en cours : actualiser toutes les 5 minutes"),
                        variable=self.auto).pack(side="left", padx=12)
        self.etat_stats = ttk.Label(cadre, text="", foreground=TEXTE_DOUX, padding=(0, 4))
        self.etat_stats.pack(fill="x")

        # menu de navigation à gauche (comme Clover) et contenu à droite
        corps = tk.Frame(cadre, background=fond_de(cadre))
        corps.pack(fill="both", expand=True, pady=(4, 0))
        self.nav = tk.Frame(corps, background=MENU_FOND, width=205)
        self.nav.pack(side="left", fill="y")
        self.nav.pack_propagate(False)
        self.contenu_stats = tk.Frame(corps, background=fond_de(cadre))
        self.contenu_stats.pack(side="left", fill="both", expand=True, padx=(12, 0))

        # page « Accueil » : cartes d'indicateurs (valeur et variation) et graphiques
        self.page_accueil = tk.Frame(self.contenu_stats, background=fond_de(cadre))
        cartes = tk.Frame(self.page_accueil, background=fond_de(cadre))
        cartes.pack(fill="x")
        self.cartes_stats = {}
        for i, (titre, _, _) in enumerate(self.INDICATEURS):  # deux rangées de 4 cartes, bien lisibles
            carte = tk.Frame(cartes, background=CARTE, highlightthickness=1, highlightbackground="#e2e8e4")
            carte.grid(row=i // 4, column=i % 4, sticky="nsew", padx=(0 if i % 4 == 0 else 6, 0),
                       pady=(0 if i < 4 else 6, 0))
            cartes.columnconfigure(i % 4, weight=1, uniform="cartes")
            tk.Label(carte, text=t(titre), background=CARTE, foreground=TEXTE, font=("Segoe UI", 10)).pack(
                anchor="w", padx=10, pady=(6, 0))
            ligne_valeur = tk.Frame(carte, background=CARTE)
            ligne_valeur.pack(fill="x", padx=10, pady=(0, 6))
            valeur = tk.Label(ligne_valeur, text="—", background=CARTE, font=("Segoe UI Semibold", 15))
            valeur.pack(side="left")
            ecart = tk.Label(ligne_valeur, text="", background=CARTE, font=("Segoe UI Semibold", 10))
            ecart.pack(side="right", anchor="s", pady=(0, 3))
            self.cartes_stats[titre] = (valeur, ecart)
        graphiques = tk.Frame(self.page_accueil, background=fond_de(cadre))
        graphiques.pack(fill="both", expand=True, pady=(8, 0))
        graphiques.columnconfigure((0, 1, 2), weight=1, uniform="g")
        graphiques.rowconfigure((0, 1), weight=1)
        self.g_ventes = Graphique(graphiques, 170, t("Ventes nettes"))
        self.g_ventes.grid(row=0, column=0, columnspan=3, sticky="nsew")
        self.g_moyens = Graphique(graphiques, 175, t("Montant perçu"))
        self.g_moyens.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
        self.g_categories = Graphique(graphiques, 175, t("Ventes par catégorie"))
        self.g_categories.grid(row=1, column=1, sticky="nsew", padx=8, pady=(8, 0))
        self.g_articles = Graphique(graphiques, 175, t("Meilleurs articles"))
        self.g_articles.grid(row=1, column=2, sticky="nsew", pady=(8, 0))

        # page « tableau » : un état (titre, tableau, export)
        self.page_tableau = tk.Frame(self.contenu_stats, background=fond_de(cadre))
        ligne = tk.Frame(self.page_tableau, background=fond_de(cadre))
        ligne.pack(fill="x")
        self.titre_etat = tk.Label(ligne, text="", font=("Segoe UI Semibold", 13), foreground=VERT_FONCE,
                                   background=fond_de(cadre))
        self.titre_etat.pack(side="left")
        filtres = tk.Frame(self.page_tableau, background=fond_de(cadre))
        filtres.pack(fill="x", pady=(4, 0))
        ttk.Label(filtres, text=t("Rechercher :")).pack(side="left", padx=(0, 4))
        self.recherche_etat = tk.StringVar()
        champ = ttk.Entry(filtres, textvariable=self.recherche_etat, width=28)
        champ.pack(side="left")
        champ.bind("<KeyRelease>", lambda _e: self.afficher_statistiques())
        self.cadre_horizon = tk.Frame(filtres, background=fond_de(cadre))
        ttk.Label(self.cadre_horizon, text=t("Horizon :")).pack(side="left", padx=(16, 4))
        self.horizon = tk.StringVar(value=t("{n} jours", n=14))
        horizon = ttk.Combobox(self.cadre_horizon, textvariable=self.horizon, state="readonly", width=10,
                               values=[t("{n} jours", n=n) for n in HORIZONS])
        horizon.pack(side="left")
        horizon.bind("<<ComboboxSelected>>", lambda _e: self._changer_horizon())
        self.note_etat = ttk.Label(self.page_tableau, text="", foreground=TEXTE_DOUX, wraplength=900, justify="left")
        self.note_etat.pack(fill="x", pady=(4, 0))
        self.g_etat = Graphique(self.page_tableau, 170)
        self.g_etat.pack(fill="x", pady=(6, 0))
        self.tableau_stats = tableau_simple(self.page_tableau)
        self.tableau_stats.tag_configure("a_commander", background=COULEURS_PEREMPTION["rouge"])
        bouton_exporter(ligne, self.tableau_stats, t("Statistiques Clover")).pack(side="right")
        self.donnees_prev = None
        self.vues_prev: dict = {}
        self._lecture_prev = False

        # page « Péremption »
        self.page_peremption = tk.Frame(self.contenu_stats, background=fond_de(cadre))
        self._onglet_peremption(self.page_peremption)

        self.vue_courante = "accueil"
        self.section_ouverte = "Accueil"
        self._construire_nav()
        self._montrer("accueil", "Accueil")
        self.vues_stats: dict = {}
        self._minuterie = None
        self._calcul_en_cours = False
        self._afficher_periode()

    def _menu_periodes(self) -> None:
        from .statistiques_clover import PERIODES

        menu = tk.Menu(self, tearoff=0)
        for nom in PERIODES:
            menu.add_command(label=t(nom), command=lambda n=nom: self._choisir_periode(n))
        menu.add_separator()
        menu.add_command(label=t("Période personnalisée…"), command=self._periode_personnalisee)
        b = self.bouton_periode
        menu.tk_popup(b.winfo_rootx(), b.winfo_rooty() + b.winfo_height())

    def _choisir_periode(self, nom: str, du: date | None = None, au: date | None = None) -> None:
        from .statistiques_clover import periode

        if du is None:
            du, au = periode(nom)
        self.nom_periode = nom
        self.stat_du.set(du.isoformat())
        self.stat_au.set(au.isoformat())
        self._afficher_periode()
        self.calculer_statistiques()

    def _afficher_periode(self) -> None:
        du, au = self.stat_du.get(), self.stat_au.get()
        nom = t(self.nom_periode) if self.nom_periode != "Personnalisée" else (du if du == au else f"{du} → {au}")
        self.bouton_periode.configure(text="📅  " + nom + "  ⌄")
        self.libelle_periode.configure(text=du if du == au else f"{du} → {au}")

    def _periode_personnalisee(self) -> None:
        fenetre = tk.Toplevel(self)
        fenetre.title(t("Période personnalisée"))
        fenetre.configure(background=CARTE)
        fenetre.transient(self.winfo_toplevel())
        cadre = tk.Frame(fenetre, background=CARTE, padx=18, pady=14)
        cadre.pack()
        du, au = tk.StringVar(value=self.stat_du.get()), tk.StringVar(value=self.stat_au.get())
        for rang, (texte, variable) in enumerate(((t("Du"), du), (t("Au"), au))):
            tk.Label(cadre, text=texte, background=CARTE).grid(row=rang, column=0, sticky="w", pady=4)
            ChampDate(cadre, variable, fond=CARTE).grid(row=rang, column=1, sticky="w", padx=(8, 0), pady=4)

        def valider() -> None:
            try:
                d, a = date.fromisoformat(du.get().strip()), date.fromisoformat(au.get().strip())
            except ValueError:
                messagebox.showwarning(self.titre, t("Date invalide : utilisez le format AAAA-MM-JJ (ou le "
                                                     "calendrier 📅)."), parent=fenetre)
                return
            if d > a or a > date.today():
                messagebox.showwarning(self.titre, t("Le début doit précéder la fin, au plus tard aujourd'hui."),
                                       parent=fenetre)
                return
            fenetre.destroy()
            self._choisir_periode("Personnalisée", d, a)

        Bouton(cadre, t("Appliquer"), valider, fond=CARTE).grid(row=2, column=0, columnspan=2, pady=(10, 0))
        fenetre.grab_set()

    def calculer_statistiques(self) -> None:
        if self._calcul_en_cours:
            return
        du, au = date.fromisoformat(self.stat_du.get()), date.fromisoformat(self.stat_au.get())
        self._calcul_en_cours = True
        self.etat_stats.configure(text=t("Lecture de Clover…"))

        def progression(i, n, debut, fin):
            self.after(0, lambda: self.etat_stats.configure(
                text=t("Lecture de Clover : jours {i} à {j} sur {n} ({d} → {f})…", i=i, j=min(n, i + (fin - debut).days),
                       n=n, d=debut, f=fin)))

        def travail():
            try:
                from .__main__ import charger_config
                from .api_clover import ClientClover
                from .statistiques_clover import comparaison, lire, montants_par_moyen, series, statistiques

                client = ClientClover(charger_config(self.racine / "config.toml"))
                cache = self.racine / "donnees" / "cache_clover"
                du2, au2, libelle = comparaison(du, au, self.nom_periode)
                donnees = lire(client, du, au, cache, progression)
                autres = lire(client, du2, au2, cache, progression)
                resultat = {"vues": statistiques(donnees), "avant": statistiques(autres), "libelle": libelle,
                            "series": series(donnees, du, au), "series_avant": series(autres, du2, au2),
                            "moyens": montants_par_moyen(donnees), "du": du, "au": au}
                self.after(0, lambda: self._fin_statistiques(resultat))
            except Exception as exc:
                texte = str(exc)
                self.after(0, lambda: (self.etat_stats.configure(text="✘ " + texte),
                                       setattr(self, "_calcul_en_cours", False)))

        threading.Thread(target=travail, daemon=True).start()

    def _fin_statistiques(self, r: dict) -> None:
        from .graphiques import BLEU, BLEU_PALE

        self._calcul_en_cours = False
        self.vues_stats = r["vues"]
        actuel, avant = dict(r["vues"]["Résumé"][1]), dict(r["avant"]["Résumé"][1])
        for titre, cle, argent in self.INDICATEURS:
            valeur_l, ecart_l = self.cartes_stats[titre]
            v, w = actuel.get(cle, 0), avant.get(cle, 0)
            if titre in ("Rabais", "Remboursements"):  # montants négatifs : on compare leur importance
                v, w = abs(v), abs(w)
            valeur_l.configure(text=montant(v) if argent else str(v))
            if w and v is not None:
                variation = (Decimal(str(v)) - Decimal(str(w))) * 100 / abs(Decimal(str(w)))
                hausse = variation >= 0
                bon = hausse if titre not in ("Rabais", "Remboursements") else not hausse
                ecart_l.configure(text=("↑ " if hausse else "↓ ") + f"{abs(variation):.1f} %".replace(".", ","),
                                  foreground="#1b7f3b" if bon else ROUGE)
            else:
                ecart_l.configure(text="—", foreground=TEXTE_DOUX)
        etiquettes, valeurs = r["series"]
        _, valeurs_avant = r["series_avant"]
        valeurs_avant = (valeurs_avant + [0] * len(valeurs))[:len(valeurs)]
        nom = (t("Aujourd'hui") if r["du"] == r["au"] == date.today() else
               (str(r["du"]) if r["du"] == r["au"] else t("Période choisie")))
        self.g_ventes.titre = t("Ventes nettes par heure") if r["du"] == r["au"] else t("Évolution des ventes nettes")
        if r["du"] == r["au"]:
            self.g_ventes.barres(etiquettes, [(nom, valeurs, BLEU), (t(r["libelle"]).capitalize(), valeurs_avant,
                                                                     BLEU_PALE)], t("Aucune vente"))
        else:
            self.g_ventes.courbes(etiquettes, [(nom, valeurs, BLEU, False),
                                               (t(r["libelle"]).capitalize(), valeurs_avant, BLEU_PALE, True)],
                                  t("Aucune vente"))
        self.g_moyens.anneau([(t(k), v) for k, v in r["moyens"]], t("Aucun paiement"), format_valeur=montant)
        self.g_categories.anneau([(l[0], l[2]) for l in r["vues"]["Par catégorie"][1]], t("Aucune vente"),
                                 format_valeur=montant)
        articles = [(l[0], l[6]) for l in r["vues"]["Par article"][1][:8]]
        self.g_articles.classement(articles, vide=t("Aucune vente"), format_valeur=montant)
        self.etat_stats.configure(text=t("Mis à jour à {h} — variations par rapport à {x}.",
                                         h=f"{datetime.now():%H:%M}", x=t(r["libelle"])))
        self.afficher_statistiques()
        # journée en cours : nouvelle lecture dans 5 minutes
        if self._minuterie:
            self.after_cancel(self._minuterie)
            self._minuterie = None
        if self.auto.get() and r["au"] >= date.today():
            self._minuterie = self.after(5 * 60 * 1000, self.calculer_statistiques)

    # ---------------------------------------------------------------- navigation des états
    def _construire_nav(self) -> None:
        """Sections (icône + titre, dépliées au clic, une seule ouverte) et leurs états, comme le menu de Clover."""
        for enfant in self.nav.winfo_children():
            enfant.destroy()
        self.liens_nav = {}
        tk.Frame(self.nav, height=6, background=MENU_FOND).pack()
        for icone, section, etats in NAVIGATION:
            ouverte = section == self.section_ouverte
            entete = tk.Label(self.nav, text=f"{icone}   {t(section)}", anchor="w", cursor="hand2",
                              font=("Segoe UI Semibold" if ouverte else "Segoe UI", 10), padx=12, pady=6,
                              background=MENU_SURVOL if ouverte and len(etats) > 1 else MENU_FOND, foreground=TEXTE)
            entete.pack(fill="x", padx=6, pady=(2, 0))
            premier = etats[0]
            entete.bind("<Button-1>", lambda _e, s=section, e=premier: self._ouvrir_section(s, e))
            if not ouverte or len(etats) == 1:
                if len(etats) == 1:
                    self.liens_nav[(section, premier[1])] = entete
                continue
            for libelle, cle in etats:
                lien = tk.Label(self.nav, text=t(libelle), anchor="w", cursor="hand2", font=("Segoe UI", 9),
                                padx=34, pady=5, background=MENU_FOND, foreground=TEXTE)
                lien.pack(fill="x", padx=6)
                lien.bind("<Button-1>", lambda _e, c=cle, s=section: self._montrer(c, s))
                self.liens_nav[(section, cle)] = lien
        self._surligner()

    def _ouvrir_section(self, section: str, premier: tuple[str, str]) -> None:
        self.section_ouverte = section
        self._construire_nav()
        self._montrer(premier[1], section)

    def _surligner(self) -> None:
        for (section, cle), lien in self.liens_nav.items():
            actif = cle == self.vue_courante and section == self.section_ouverte
            lien.configure(background=MENU_ACTIF if actif else MENU_FOND,
                           foreground=VERT_FONCE if actif else TEXTE,
                           font=(("Segoe UI Semibold" if actif else "Segoe UI"), 10 if lien.cget("padx") == 12 else 9))

    def _montrer(self, cle: str, section: str) -> None:
        self.vue_courante, self.section_ouverte = cle, section
        for page in (self.page_accueil, self.page_tableau, self.page_peremption):
            page.pack_forget()
        if cle == "accueil":
            self.page_accueil.pack(fill="both", expand=True)
        elif cle == "peremption":
            self.page_peremption.pack(fill="both", expand=True)
            if not self.peremption:
                self.lire_peremption()
        elif cle in PREVISIONS:
            self.page_tableau.pack(fill="both", expand=True)
            self.titre_etat.configure(text=t(next(l for _, _, e in NAVIGATION for l, c in e if c == cle)))
            if self.donnees_prev is None:
                self.lire_previsions()
            self.afficher_statistiques()
        else:
            self.page_tableau.pack(fill="both", expand=True)
            libelle = next((l for _, _, etats in NAVIGATION for l, c in etats if c == cle), cle)
            self.titre_etat.configure(text=t(libelle))
            self.afficher_statistiques()
        self._surligner()

    def afficher_statistiques(self) -> None:
        nom = self.vue_courante
        if nom in ("accueil", "peremption"):
            return
        if nom in PREVISIONS:
            self.cadre_horizon.pack(side="left")
        else:
            self.cadre_horizon.pack_forget()
        source = self.vues_prev if nom in PREVISIONS else self.vues_stats
        if nom not in source:
            self.tableau_stats.delete(*self.tableau_stats.get_children())
            self.g_etat.pack_forget()
            self.note_etat.configure(text="")
            return
        entetes, lignes = source[nom]
        self.note_etat.configure(text=t(NOTES_ETATS.get(nom, "")) if NOTES_ETATS.get(nom) else "")
        self._graphique_etat(nom, lignes)
        texte = self.recherche_etat.get().strip().casefold()
        if texte:
            lignes = [l for l in lignes if any(texte in str(v).casefold() for v in l)]
        lignes = [[t(x) if isinstance(x, str) and nom == "Résumé" else x for x in l] for l in lignes]
        remplir(self.tableau_stats, entetes, lignes, {"Indicateur": 320, "Article": 280, "Client": 240,
                                                      "Employé": 190, "Appareil": 300, "Date et heure": 130},
                (lambda i: ("a_commander",) if t(A_COMMANDER_TEXTE) in lignes[i] else ()))

    def _graphique_etat(self, nom: str, lignes: list[list]) -> None:
        """Graphique adapté à l'état : courbe, barres, anneau ou classement (rien pour les listes détaillées)."""
        from .graphiques import BLEU, BLEU_PALE

        if nom == "prev_ventes" and self.donnees_prev:
            historique, prevision = self.donnees_prev["historique"], lignes
            jours = sorted(historique)[-28:]
            etiquettes = [f"{j.day:02d}/{j.month:02d}" for j in jours] + [l[0][8:10] + "/" + l[0][5:7] for l in prevision]
            reels = [historique[j] for j in jours] + [None] * len(prevision)
            prevus = [None] * (len(jours) - 1) + [historique[jours[-1]] if jours else None] + [l[2] for l in prevision]
            self.g_etat.titre = t("Ventes nettes : 28 derniers jours et prévision")
            self.g_etat.courbes(etiquettes, [(t("Ventes réelles"), reels, BLEU, False),
                                             (t("Prévision"), prevus, "#f6b81a", True)], t("Aucune vente"))
            self.g_etat.pack(fill="x", pady=(6, 0), before=self.tableau_stats.master)
            return
        if nom == "prev_commande":
            compte = {}
            for l in lignes:
                compte[l[5]] = compte.get(l[5], 0) + 1
            self.g_etat.titre = t("Articles vendus en {n} jours", n=self._horizon())
            self.g_etat.anneau([(t(k), Decimal(v)) for k, v in compte.items()], t("Aucune vente"),
                               format_valeur=lambda v: f"{v:.0f}")
            self.g_etat.pack(fill="x", pady=(6, 0), before=self.tableau_stats.master)
            return
        genre = GRAPHIQUES_ETATS.get(nom)
        if not genre or not lignes:
            self.g_etat.pack_forget()
            return
        type_, i_nom, i_val = genre
        valeurs = [(str(l[i_nom]), abs(l[i_val]) if isinstance(l[i_val], Decimal) else Decimal(l[i_val] or 0))
                   for l in lignes]
        self.g_etat.titre = ""
        if type_ == "courbe":
            self.g_etat.courbes([v[0][8:10] + "/" + v[0][5:7] for v in valeurs],
                                [(t("Ventes nettes"), [v[1] for v in valeurs], BLEU, False)], t("Aucune vente"))
        elif type_ == "barres":
            self.g_etat.barres([v[0] for v in valeurs], [(t("Ventes nettes"), [v[1] for v in valeurs], BLEU)],
                               t("Aucune vente"))
        elif type_ == "anneau":
            self.g_etat.anneau(valeurs, t("Aucune vente"), format_valeur=montant)
        else:
            self.g_etat.classement(sorted(valeurs, key=lambda v: -v[1])[:8], vide=t("Aucune vente"),
                                   format_valeur=montant, couleur=BLEU_PALE if nom == "Rabais" else BLEU)
        self.g_etat.pack(fill="x", pady=(6, 0), before=self.tableau_stats.master)

    # ---------------------------------------------------------------- prévisions
    def _horizon(self) -> int:
        return int(self.horizon.get().split()[0])

    def _changer_horizon(self) -> None:
        """Un horizon plus long que les ventes déjà lues : on relit la période nécessaire, sinon simple calcul."""
        if self.donnees_prev and self._horizon() > self.donnees_prev["jours"]:
            self.lire_previsions(self._horizon())
        else:
            self._calculer_previsions()

    def lire_previsions(self, jours: int = 56) -> None:
        """Ventes des `jours` derniers jours (au moins 8 semaines ; cache des jours terminés) et articles Clover
        (stock, coût), lus une fois."""
        if self._lecture_prev:
            return
        jours = max(56, jours, self._horizon())
        self._lecture_prev = True
        self.note_etat.configure(text=t("Lecture de {n} jours de ventes et des articles dans Clover…", n=jours))

        def travail():
            try:
                from .__main__ import charger_config
                from .api_clover import ClientClover
                from .statistiques_clover import lire

                client = ClientClover(charger_config(self.racine / "config.toml"))
                aujourdhui = date.today()
                donnees = lire(client, aujourdhui - timedelta(days=jours), aujourdhui - timedelta(days=1),
                               self.racine / "donnees" / "cache_clover")
                articles = list(client._pages("items", {"expand": "categories,itemStock"}))
                resultat = {"donnees": donnees, "articles": articles, "aujourdhui": aujourdhui, "jours": jours}
                self.after(0, lambda: self._fin_previsions(resultat))
            except Exception as exc:
                texte = str(exc)
                self.after(0, lambda: (self.note_etat.configure(text="✘ " + texte),
                                       setattr(self, "_lecture_prev", False)))

        threading.Thread(target=travail, daemon=True).start()

    def _fin_previsions(self, resultat: dict) -> None:
        from .previsions import ventes_par_jour

        self._lecture_prev = False
        self.donnees_prev = resultat
        resultat["historique"] = ventes_par_jour(resultat["donnees"])
        self._calculer_previsions()

    def _calculer_previsions(self) -> None:
        from .previsions import articles_a_commander, prevoir_achats, prevoir_ventes, ventes_par_article

        if not self.donnees_prev:
            return
        r = self.donnees_prev
        a, d = r["aujourdhui"], r["donnees"]
        horizon = self._horizon()
        ventes = prevoir_ventes(r["historique"], a, horizon)
        self.vues_prev["prev_ventes"] = (["Date", "Jour", "Prévision", "Même jour la semaine dernière",
                                          "Moyenne des 4 mêmes jours"], ventes)
        self.vues_prev["prev_commande"] = (
            ["Article", "Catégorie", t("Vendu {n} jours", n=horizon), "Stock", "Stock − vendu", "État",
             "Quantité suggérée", "Coût estimé", "Dernière vente"],
            [l[:5] + [t(l[5])] + l[6:] for l in articles_a_commander(
                ventes_par_article(d, a - timedelta(days=horizon), a - timedelta(days=1)), r["articles"])])
        achats = prevoir_achats(ventes_par_article(d, a - timedelta(days=28), a - timedelta(days=1)), r["articles"],
                                horizon)
        self.vues_prev["prev_achats"] = (["Article", "Catégorie", "Vendu 28 jours", f"Besoin {horizon} jours",
                                          "Stock", "À acheter", "Coût unitaire", "Montant estimé"], achats)
        NOTES_ETATS["prev_ventes"] = t("Total prévu sur {n} jours : {m} (même jour de la semaine sur 4 semaines, "
                                       "tendance des 4 dernières semaines).", n=horizon,
                                       m=montant(sum((l[2] for l in ventes), Decimal(0))))
        NOTES_ETATS["prev_achats"] = t("Achats estimés sur {n} jours : {m} (rythme de vente des 28 derniers jours, "
                                       "stock et coût des articles dans Clover).", n=horizon,
                                       m=montant(sum((l[7] or Decimal(0) for l in achats), Decimal(0))))
        a_commander = sum(1 for l in self.vues_prev["prev_commande"][1] if l[5] == t("À commander"))
        NOTES_ETATS["prev_commande"] = t("{n} article(s) à commander : stock restant − quantité vendue les {j} "
                                         "derniers jours ≤ 0 (articles vendus dont Clover suit le stock).",
                                         n=a_commander, j=horizon)
        self.afficher_statistiques()

    # ---------------------------------------------------------------- péremption (date dans le SKU Clover)
    def _onglet_peremption(self, cadre) -> None:
        barre = ttk.Frame(cadre)
        barre.pack(fill="x")
        Bouton(barre, "🔄  " + t("Actualiser"), self.lire_peremption).pack(side="left")
        ttk.Label(barre, text=t("Afficher :")).pack(side="left", padx=(16, 4))
        self.filtre_peremption = tk.StringVar(value=t("Bientôt périmés (3 mois ou moins)"))
        choix = ttk.Combobox(barre, textvariable=self.filtre_peremption, state="readonly", width=34,
                             values=[t(x) for x in FILTRES_PEREMPTION])
        choix.pack(side="left")
        choix.bind("<<ComboboxSelected>>", lambda _e: self.afficher_peremption())
        legende = tk.Frame(cadre, background=fond_de(cadre))
        legende.pack(fill="x", pady=(8, 0))
        self.texte_peremption = tk.StringVar()
        champ = ttk.Entry(legende, textvariable=self.texte_peremption, width=20)
        champ.pack(side="right")
        champ.bind("<KeyRelease>", lambda _e: self.afficher_peremption())
        ttk.Label(legende, text=t("Rechercher :")).pack(side="right", padx=(12, 4))
        self.en_stock = tk.BooleanVar(value=False)
        ttk.Checkbutton(legende, text=t("Seulement les articles en stock"), variable=self.en_stock,
                        command=self.afficher_peremption).pack(side="right")
        for texte, couleur in ((t("Un mois ou moins (ou périmé)"), COULEURS_PEREMPTION["rouge"]),
                               (t("De 1 à 3 mois"), COULEURS_PEREMPTION["orange"]),
                               (t("Plus de 3 mois"), COULEURS_PEREMPTION["neutre"])):
            tk.Label(legende, text="   ", background=couleur, relief="solid", borderwidth=1).pack(side="left")
            tk.Label(legende, text=texte, background=fond_de(cadre), foreground=TEXTE_DOUX,
                     font=("Segoe UI", 9)).pack(side="left", padx=(4, 16))
        self.etat_peremption = ttk.Label(cadre, text=t("Date de péremption lue dans le champ SKU des articles Clover "
                                                       "(JJ/MM/AAAA) ; SKU vides ou sans date ignorés. Cliquez sur "
                                                       "« Actualiser »."), foreground=TEXTE_DOUX, padding=(0, 6))
        self.etat_peremption.pack(fill="x")
        self.tableau_peremption = tableau_simple(cadre)
        for cle, couleur in COULEURS_PEREMPTION.items():
            self.tableau_peremption.tag_configure(cle, background=couleur)
        bouton_exporter(barre, self.tableau_peremption, t("Péremption")).pack(side="right")
        self.peremption = []

    def lire_peremption(self) -> None:
        self.etat_peremption.configure(text=t("Lecture des articles dans Clover…"))

        def travail():
            try:
                from .__main__ import charger_config
                from .api_clover import ClientClover
                from .peremption import articles_peremption

                client = ClientClover(charger_config(self.racine / "config.toml"))
                articles = list(client._pages("items", {"expand": "categories,itemStock"}))
                resultat = articles_peremption(articles)
                self.after(0, lambda: self._fin_peremption(resultat, len(articles)))
            except Exception as exc:
                texte = str(exc)
                self.after(0, lambda: self.etat_peremption.configure(text="✘ " + texte))

        threading.Thread(target=travail, daemon=True).start()

    def _fin_peremption(self, resultat: list, total: int) -> None:
        self.peremption = resultat
        self.total_articles = total
        self.afficher_peremption()

    def afficher_peremption(self) -> None:
        from .peremption import NEUTRE, ORANGE, PERIME, ROUGE

        filtre = next(x for x in FILTRES_PEREMPTION if t(x) == self.filtre_peremption.get())
        garder = {"Bientôt périmés (3 mois ou moins)": (PERIME, ROUGE, ORANGE), "Périmés": (PERIME,),
                  "Un mois ou moins": (PERIME, ROUGE), "De 1 à 3 mois": (ORANGE,), "Plus de 3 mois": (NEUTRE,),
                  "Tous": (PERIME, ROUGE, ORANGE, NEUTRE)}[filtre]
        texte = self.texte_peremption.get().strip().casefold()
        lignes = [p for p in self.peremption if p.etat in garder
                  and (not self.en_stock.get() or (p.stock or 0) > 0)
                  and (not texte or texte in (p.nom + " " + p.categorie).casefold())]
        entetes = ["Article", "Catégorie", "Date de péremption", "Jours restants", "État", "Stock", "Prix", "SKU"]
        valeurs = [[p.nom, p.categorie, p.peremption.isoformat(), p.jours, t(p.etat),
                    "" if p.stock is None else f"{p.stock:f}".replace(".", ","), p.prix, p.sku] for p in lignes]
        remplir(self.tableau_peremption, entetes, valeurs, {
            "Article": 290, "Catégorie": 140, "Date de péremption": 115, "Jours restants": 95, "État": 120,
            "Stock": 70, "Prix": 80, "SKU": 95},
                lambda i: (lignes[i].couleur,))
        compte = {e: sum(1 for p in self.peremption if p.etat == e) for e in (PERIME, ROUGE, ORANGE, NEUTRE)}
        self.etat_peremption.configure(text=t(
            "{n} article(s) affiché(s) — sur {d} articles avec une date dans le SKU ({total} articles Clover) : "
            "périmés {p}, un mois ou moins {r}, 1 à 3 mois {o}, plus de 3 mois {x}.", n=len(lignes),
            d=len(self.peremption), total=getattr(self, "total_articles", 0), p=compte[PERIME], r=compte[ROUGE],
            o=compte[ORANGE], x=compte[NEUTRE]))

    # ---------------------------------------------------------------- factures fournisseurs archivées
    def _onglet_archives(self) -> None:
        cadre = ttk.Frame(self.onglets, padding=(0, 8, 0, 0))
        self.onglets.add(cadre, text="  " + t("Factures fournisseurs archivées") + "  ")
        barre = ttk.Frame(cadre)
        barre.pack(fill="x")
        ttk.Label(barre, text=t("Rechercher :")).pack(side="left", padx=(0, 4))
        self.texte_archives = tk.StringVar()
        champ = ttk.Entry(barre, textvariable=self.texte_archives, width=28)
        champ.pack(side="left")
        champ.bind("<KeyRelease>", lambda _e: self.afficher_archives())
        Bouton(barre, "📄  " + t("Voir la facture"), self.ouvrir_piece, "secondaire", petit=True).pack(
            side="left", padx=(12, 6))
        Bouton(barre, "📗  " + t("Détail (Excel)"), self.ouvrir_detail, "secondaire", petit=True).pack(side="left")
        Bouton(barre, "📂  " + t("Dossier des archives"), self.ouvrir_dossier, "secondaire", petit=True).pack(
            side="left", padx=6)
        self.resume_archives = ttk.Label(cadre, text="", foreground=TEXTE_DOUX, padding=(0, 6))
        self.resume_archives.pack(fill="x")
        cadre_t = cadre_tableau(cadre)
        cadre_t.pack(fill="x")
        self.tableau_archives = ttk.Treeview(cadre_t, columns=[c[0] for c in COLONNES_ARCHIVES], show="headings",
                                             height=7, selectmode="browse")
        for cle, texte, largeur in COLONNES_ARCHIVES:
            self.tableau_archives.heading(cle, text=t(texte))
            self.tableau_archives.column(cle, width=largeur, anchor="e" if cle in ("total", "lignes") else "w",
                                         stretch=cle == "fournisseur")
        self.tableau_archives.pack(fill="x")
        self.tableau_archives.bind("<<TreeviewSelect>>", lambda _e: self.afficher_lignes())
        self.tableau_archives.bind("<Double-Button-1>", lambda _e: self.ouvrir_piece())
        bouton_exporter(barre, self.tableau_archives, t("Factures fournisseurs archivées")).pack(side="right")
        tk.Label(cadre, text=t("Lignes de la facture choisie"), font=("Segoe UI Semibold", 10),
                 background=fond_de(cadre)).pack(anchor="w", pady=(10, 0))
        self.tableau_lignes = tableau_simple(cadre, hauteur=6)

    def _au_changement(self) -> None:
        onglet = self.onglets.index("current")
        if onglet == 2:
            self.charger_archives()
        elif onglet == 3 and not self.vues_stats and not self._calcul_en_cours:
            self.calculer_statistiques()  # journée en cours dès l'ouverture de l'onglet

    def charger_archives(self) -> None:
        from .fournisseurs import archiver_importees, archives

        try:
            nouvelles = archiver_importees(self.racine)  # factures importées avant l'archivage
        except OSError:
            nouvelles = 0
        self.archives = archives(self.racine)
        self.afficher_archives()
        if nouvelles:
            self.resume_archives.configure(text=self.resume_archives.cget("text") +
                                           t("  •  {n} facture(s) importée(s) archivée(s) à l'instant", n=nouvelles))

    def _visibles(self) -> list[dict]:
        texte = self.texte_archives.get().strip().casefold()
        return [a for a in self.archives if not texte or any(
            texte in str(a.get(c, "")).casefold() for c in ("fournisseur_sage", "fournisseur_lu", "numero",
                                                            "date_facture", "total", "fichier"))
            or any(texte in (l.get("description", "") + l.get("numero_sage", "")).casefold()
                   for l in a.get("lignes", []))]

    def afficher_archives(self) -> None:
        self.tableau_archives.delete(*self.tableau_archives.get_children())
        visibles = self._visibles()
        for i, a in enumerate(visibles):
            total = Decimal(a["total"]) if a.get("total") not in (None, "") else None
            self.tableau_archives.insert("", "end", iid=str(i), values=(
                a.get("date_facture", ""), a.get("fournisseur_sage") or a.get("fournisseur_lu", ""), a.get("numero", ""),
                montant(total), len(a.get("lignes", [])), a.get("archivee_le", "").replace("T", " ")))
        rayer(self.tableau_archives)
        self.resume_archives.configure(text=t("{n} facture(s) archivée(s) sur {total}.", n=len(visibles),
                                              total=len(self.archives)))
        self.tableau_lignes.delete(*self.tableau_lignes.get_children())

    def _choisie(self) -> dict | None:
        choix = self.tableau_archives.selection()
        if not choix:
            messagebox.showinfo(self.titre, t("Choisissez d'abord une facture dans la liste."))
            return None
        return self._visibles()[int(choix[0])]

    def afficher_lignes(self) -> None:
        choix = self.tableau_archives.selection()
        if not choix:
            return
        a = self._visibles()[int(choix[0])]
        entetes = ["Description", "Qté", "Prix fournisseur", "Montant", "N° Sage", "Article Sage", "Facteur"]
        lignes = [[l.get("description", ""), l.get("quantite", ""), Decimal(l.get("prix") or 0),
                   Decimal(l.get("montant") or 0), l.get("numero_sage", ""), l.get("description_sage", ""),
                   l.get("facteur", "")] for l in a.get("lignes", [])]
        remplir(self.tableau_lignes, entetes, lignes, {"Description": 260, "Article Sage": 240})

    def _ouvrir(self, chemin: Path) -> None:
        if chemin.exists():
            os.startfile(chemin)
        else:
            messagebox.showinfo(self.titre, t("Fichier introuvable : {f}", f=chemin.name))

    def ouvrir_piece(self) -> None:
        a = self._choisie()
        if a:
            json_ = Path(a["chemin"])
            self._ouvrir(json_.with_name(a["fichier_archive"]) if a.get("fichier_archive") else
                         self.racine / "donnees" / "factures_fournisseurs" / a.get("fichier", ""))

    def ouvrir_detail(self) -> None:
        a = self._choisie()
        if a:
            self._ouvrir(Path(a["chemin"]).with_suffix(".xlsx"))

    def ouvrir_dossier(self) -> None:
        from .fournisseurs import ARCHIVES

        dossier = self.racine / "donnees" / ARCHIVES
        dossier.mkdir(parents=True, exist_ok=True)
        os.startfile(dossier)

