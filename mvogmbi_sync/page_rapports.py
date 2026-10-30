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
                     ChampDate, ChampRecherche, Rangee, apres_frappe, cadre_tableau, entete_page, fond_de, rayer)
from .export_tableau import bouton_exporter, export_permis, placer_a_droite
from .statistiques_clover import SEUIL_CUMP_DOUTEUX
from .langues import t
from .rapports_gestion import TEXTES as _TEXTES_GESTION

TEXTES_GESTION = set(_TEXTES_GESTION)  # états, motifs, notes des rapports de gestion : traduits à l'affichage

# couleurs des lignes du suivi : vente bloquée, à encaisser, encaissée mais pas retrouvée sur les relevés
COULEURS = {"bloquee": "#fde2e4", "a_encaisser": "#fff4d6", "a_rapprocher": "#eaf2fb"}
# Menu des statistiques Clover : (icône, section, [(libellé, vue de statistiques_clover ou page)])
NAVIGATION = [
    ("🏠", "Accueil", [("Accueil", "accueil")]),
    ("🧾", "Activités de vente", [("Commandes", "Commandes"), ("Transactions", "Paiements"),
                                  ("Remboursements", "Remboursements")]),
    # dans l'ordre du menu « Rapports » de Clover (articles supprimés et cartes-cadeaux : absents de l'API Clover)
    ("📊", "Rapports", [("Aperçu des ventes", "apercu"), ("Rapport des ventes", "Rapport des ventes"),
                       ("Évolution par année", "evolution_annees"), ("Carte de chaleur", "Jour × heure"),
                       ("Ventes d'articles", "Par article"), ("Bénéfices", "Bénéfices"),
                       ("Ventes par employé", "Par employé"), ("Modes de paiement", "Par mode de paiement"),
                       ("Rabais", "Rabais")]),
    ("🏦", "Finances", [("Aperçu financier", "Résumé"), ("Modes de paiement", "Par mode de paiement"),
                       ("Types de carte", "Par type de carte"), ("Saisie des cartes", "Par mode de saisie de la carte"),
                       ("Ventes par jour", "Par jour"), ("Appareils", "Par appareil")]),
    ("🏷", "Articles", [("Liste d'articles", "liste_articles"), ("Ventes d'articles", "Par article"),
                       ("Catégories", "Par catégorie"),
                       ("Péremption", "peremption")]),
    ("👤", "Employés", [("Ventes par employé", "Par employé")]),
    ("👥", "Clients", [("Liste des clients", "Par client")]),
    ("📈", "Prévisions", [("Prévision des ventes", "prev_ventes"), ("Prévision des achats", "prev_achats"),
                         ("Articles à commander", "prev_commande")]),
    # rapports des fonctions de gestion (demande du propriétaire du 2026-10-30) : cartes, évolution, répartition,
    # rapport détaillé, sur la période choisie (rapports_gestion.py)
    ("🧩", "Gestion", [(libelle, cle) for libelle, cle, _f in __import__(
        "mvogmbi_sync.rapports_gestion", fromlist=["ETATS"]).ETATS]),
]
PREVISIONS = ("prev_ventes", "prev_achats", "prev_commande")
HORIZONS = (7, 10, 14, 21, 28, 30, 45, 60, 90)  # jours : horizon des prévisions et période des articles à commander
# graphique au-dessus de chaque état : (genre, colonne de l'étiquette, colonne de la valeur)
GRAPHIQUES_ETATS = {
    "Par jour": ("courbe", 0, 3),  # colonnes : date, jour, commandes, ventes nettes… "Par heure": ("barres", 0, 2), "Par jour de la semaine": ("barres", 0, 2),
    "Par mode de paiement": ("anneau", 0, 2), "Par type de carte": ("anneau", 0, 2),
    "Par mode de saisie de la carte": ("anneau", 0, 2), "Par catégorie": ("anneau", 0, 2),
    "Par appareil": ("anneau", 0, 2), "Par article": ("classement", 0, 6), "Par employé": ("classement", 0, 2),
    "Par client": ("classement", 0, 2), "Rabais": ("classement", 0, 2), "prev_achats": ("classement", 0, 7),
    "Bénéfices": ("classement", 0, 6),
}
TITRES_GRAPHIQUES = {
    "Par jour": "Ventes nettes par jour", "Par heure": "Ventes nettes par heure",
    "Par jour de la semaine": "Ventes nettes par jour de la semaine",
    "Par mode de paiement": "Montant perçu par mode de paiement", "Par type de carte": "Montant perçu par type de carte",
    "Par mode de saisie de la carte": "Montant perçu par mode de saisie de la carte",
    "Par catégorie": "Ventes nettes par catégorie", "Par appareil": "Ventes nettes par appareil",
    "Par article": "Les 8 articles qui vendent le plus", "Par employé": "Les 8 meilleurs vendeurs",
    "Par client": "Les 8 meilleurs clients", "Rabais": "Les 8 rabais les plus importants",
    "Bénéfices": "Les 8 articles les plus rentables", "prev_achats": "Les 8 plus gros achats à prévoir",
    "Jour × heure": "Ventes nettes par jour de la semaine et par heure",
}
NOTES_ETATS: dict[str, str] = {}   # texte sous le titre d'un état (prévisions)
A_COMMANDER_TEXTE = "À commander"
FILTRES_PEREMPTION = ["Bientôt périmés (3 mois ou moins)", "Périmés", "Un mois ou moins", "De 1 à 3 mois",
                      "Plus de 3 mois", "Tous"]
COULEURS_PEREMPTION = {"rouge": "#f8c9cf", "orange": "#ffe3a8", "neutre": "#eef1ef"}
FILTRES_SUIVI = ["Toutes", "Bloquées ou en échec", "Non encaissées", "Non rapprochées"]
FILTRES_GLOBAUX = ("Article", "Client", "Employé", "Catégorie", "Mode de paiement")
TYPES_RECHERCHE = ["Client", "Fournisseur", "Vente", "Encaissement", "Paiement", "Article", "Statistiques client",
                   "Statistiques fournisseur", "Statistiques employé"]
# statistiques (demande du propriétaire du 2026-10-28) : liste à choisir pour chaque type
STATISTIQUES = {"Statistiques client": "Client", "Statistiques fournisseur": "Fournisseur",
                "Statistiques employé": "Employé"}
REGROUPEMENTS = ["Article", "Catégorie", "Article par jour", "Catégorie par jour"]
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
    horizontal = ttk.Scrollbar(cadre, orient="horizontal", command=tableau.xview)  # tableaux larges
    tableau.configure(yscrollcommand=defil.set, xscrollcommand=horizontal.set)
    horizontal.pack(side="bottom", fill="x")
    defil.pack(side="right", fill="y")  # avant le tableau : toujours visible, même s'il est large
    tableau.pack(side="left", fill="both", expand=True)
    return tableau


def remplir(tableau: ttk.Treeview, entetes: list[str], lignes: list[list], largeurs: dict[str, int] | None = None,
            tags=None, decroissant: bool = True) -> None:
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
    # tableaux datés : la date la plus récente en haut (demande du propriétaire du 2026-10-27)
    ordre = list(range(len(lignes)))
    if decroissant and lignes and entetes and str(entetes[0]).startswith("Date") and len(lignes) > 1:
        premiere, derniere = str(lignes[0][0]), str(lignes[-1][0])
        if len(premiere) == 5 or premiere <= derniere:  # « jj/mm » (chronologique) ou date ISO croissante
            ordre.reverse()
    for i in ordre:
        ligne = lignes[i]
        valeurs = []
        for entete, v in zip(entetes, ligne):
            if isinstance(v, Decimal):
                if "%" in entete:
                    v = f"{v} %".replace(".", ",")
                elif any(m in entete for m in ("Quantité", "Cumul", "Vendu", "Stock ", "Stock", "Besoin", "À acheter",
                                                 "Sold")) and "Valeur" not in entete and not entete.startswith("Solde"):
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
        from .onglets_articles import OngletInactifs, OngletPareto  # rubrique État (demande du 2026-10-29)

        self.onglet_inactifs = OngletInactifs(self, self.onglets)
        self.onglets.add(self.onglet_inactifs, text="  " + t("Produits inactifs") + "  ")
        self.onglet_pareto = OngletPareto(self, self.onglets)
        self.onglets.add(self.onglet_pareto, text="  " + t("Articles 20/80") + "  ")
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
        champ.bind("<KeyRelease>", apres_frappe(champ, self.afficher_suivi))
        self.etat = ttk.Label(cadre, text=t("Cliquez sur « Actualiser » : historique des traitements, Sage et relevés."),
                              foreground=TEXTE_DOUX, padding=(0, 6))
        self.etat.pack(fill="x")
        tk.Label(cadre, text=t("Suivi complet des ventes : traitement, encaissement et rapprochement"),
                 font=("Segoe UI Semibold", 10), foreground=TEXTE, background=fond_de(cadre), anchor="w").pack(
            fill="x")
        self.tableau_suivi = tableau_simple(cadre)
        for cle, couleur in COULEURS.items():
            self.tableau_suivi.tag_configure(cle, background=couleur)
        placer_a_droite(bouton_exporter(barre, self.tableau_suivi, t("Suivi des ventes")))

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
        barre = Rangee(cadre)
        barre.pack(fill="x")
        groupe = barre.ajouter(barre.groupe(), 6)
        ttk.Label(groupe, text=t("Rechercher :")).pack(side="left", padx=(0, 4))
        self.type_recherche = tk.StringVar(value=t(TYPES_RECHERCHE[0]))
        choix = ttk.Combobox(groupe, textvariable=self.type_recherche, values=[t(x) for x in TYPES_RECHERCHE],
                             state="readonly", width=22)
        choix.pack(side="left")
        choix.bind("<<ComboboxSelected>>", lambda _e: self._preparer_recherche())
        self.valeur = tk.StringVar()
        self.champ_valeur = barre.ajouter(ChampRecherche(barre, self.valeur, [], largeur=46,
                                                         au_choix=lambda _v=None: self._choix_fait()), 12)
        self.barre_recherche = barre
        # deuxième ligne : plage d'articles, regroupement, période et bouton
        ligne = Rangee(cadre)
        ligne.pack(fill="x", pady=(6, 0))
        self.ligne_recherche = ligne
        self.groupe_plage = ligne.ajouter(ligne.groupe(), 14)
        self.libelle_plage = ttk.Label(self.groupe_plage, text=t("Articles du"))
        self.libelle_plage.pack(side="left", padx=(0, 4))
        self.art_du, self.art_au = tk.StringVar(), tk.StringVar()
        self.champ_art_du = ChampRecherche(self.groupe_plage, self.art_du, [], largeur=30,
                                           au_choix=lambda _v=None: self._choix_fait(article=True))
        self.champ_art_du.pack(side="left")
        ttk.Label(self.groupe_plage, text=t("au")).pack(side="left", padx=4)
        self.champ_art_au = ChampRecherche(self.groupe_plage, self.art_au, [], largeur=30,
                                           au_choix=lambda _v=None: self._choix_fait(article=True))
        self.champ_art_au.pack(side="left")
        self.groupe_categorie = ligne.ajouter(ligne.groupe(), 14)
        ttk.Label(self.groupe_categorie, text=t("Catégorie")).pack(side="left", padx=(0, 4))
        self.categorie = tk.StringVar()
        self.champ_categorie = ChampRecherche(self.groupe_categorie, self.categorie, [], largeur=22,
                                              au_choix=lambda _v=None: self._choix_fait(article=True))
        self.champ_categorie.pack(side="left")
        self.groupe_par = ligne.ajouter(ligne.groupe(), 14)
        ttk.Label(self.groupe_par, text=t("Par :")).pack(side="left", padx=(0, 4))
        self.par = tk.StringVar(value=t(REGROUPEMENTS[0]))
        par = ttk.Combobox(self.groupe_par, textvariable=self.par, values=[t(x) for x in REGROUPEMENTS],
                           state="readonly", width=20)
        par.pack(side="left")
        par.bind("<<ComboboxSelected>>", lambda _e: self._choix_fait())
        periode = ligne.ajouter(ligne.groupe(), 8)
        ttk.Label(periode, text=t("Période du")).pack(side="left", padx=(0, 4))
        self.du = tk.StringVar()
        ChampDate(periode, self.du).pack(side="left")
        ttk.Label(periode, text=t("au")).pack(side="left", padx=4)
        self.au = tk.StringVar()
        ChampDate(periode, self.au).pack(side="left")
        ligne.ajouter(Bouton(ligne, "🔍  " + t("Rechercher"), self.rechercher, petit=True), 6)
        ligne.ajouter(Bouton(ligne, "✖  " + t("Réinitialiser les filtres"), self.reinitialiser, "secondaire",
                             petit=True))
        self.aide_recherche = ttk.Label(cadre, text="", foreground=TEXTE_DOUX, padding=(0, 6))
        self.aide_recherche.pack(fill="x")
        self.titre_recherche = tk.Label(cadre, text="", font=("Segoe UI Semibold", 10), foreground=TEXTE,
                                        background=fond_de(cadre), anchor="w")
        self.titre_recherche.pack(fill="x")
        self.tableau_recherche = tableau_simple(cadre)
        self.tableau_recherche.tag_configure("total", font=("Segoe UI Semibold", 9), background="#e8f3ea")
        barre.ajouter(bouton_exporter(barre, self.tableau_recherche,  # titre : celui des résultats affichés
                                      lambda: self.titre_recherche.cget("text") or t("Recherche dans l'historique")))
        self._preparer_recherche(lire=False)

    def _type(self) -> str:
        return next(x for x in TYPES_RECHERCHE if t(x) == self.type_recherche.get())

    def _choix_fait(self, article: bool = False) -> None:
        """Un choix dans une liste lance la recherche (pas de clic de plus) ; texte libre : bouton Rechercher."""
        type_ = self._type()
        if type_ == "Article" and article and (self.art_du.get().strip() or self.categorie.get().strip()):
            self.rechercher()
        elif type_ in ("Client", "Fournisseur") or (type_ in STATISTIQUES and self.valeur.get().strip()):
            self.rechercher()

    def _preparer_recherche(self, lire: bool = True) -> None:
        """Client, fournisseur, article, employé : liste tirée de Sage ou de Clover (lue une fois) ; sinon texte libre
        (facultatif). Les résultats de la recherche précédente sont effacés."""
        from . import rapports

        type_ = self._type()
        # chaque sorte de choix garde sa valeur d'un type à l'autre (client de « Client » et de « Statistiques
        # client »…) ; plage d'articles, catégorie, regroupement et période restent tels quels
        memoire = self.__dict__.setdefault("_valeurs_par_sorte", {})
        precedent = getattr(self, "_sorte_precedente", None)
        if precedent is not None:
            memoire[precedent] = self.valeur.get()
        self._sorte_precedente = STATISTIQUES.get(type_, type_)
        self.valeur.set(memoire.get(self._sorte_precedente, ""))
        remplir(self.tableau_recherche, [], [])
        self.titre_recherche.configure(text="")
        aides = {"Client": "Choisissez le client : ses factures et encaissements, avec le solde.",
                 "Fournisseur": "Choisissez le fournisseur : factures, paiements et notes de crédit, avec le solde dû.",
                 "Article": "Choisissez l'article (n° ou nom) : ventes, achats, retours et ajustements, avec le cumul. "
                            "« au » (facultatif) : une plage d'articles, chacun à la suite de l'autre avec son total.",
                 "Vente": "Texte facultatif (n° de facture, client, montant) et période.",
                 "Encaissement": "Texte facultatif (client, facture, n° d'encaissement, montant) et période.",
                 "Paiement": "Texte facultatif (fournisseur, facture, pièce, montant) et période.",
                 "Statistiques client": "Choisissez le client : ses achats par article ou par catégorie (Sage), sur "
                                        "la période et la plage d'articles (facultatives).",
                 "Statistiques fournisseur": "Choisissez le fournisseur : achats moins retours par article ou par "
                                             "catégorie (Sage), sur la période et la plage d'articles (facultatives).",
                 "Statistiques employé": "Choisissez l'employé : ses ventes par article ou par catégorie (Clover), "
                                         "sur la période (30 derniers jours si elle est vide)."}
        self.aide_recherche.configure(text=self._aide(aides[type_], type_))
        plage = type_ in ("Article", "Statistiques client", "Statistiques fournisseur")
        self.barre_recherche.montrer(self.champ_valeur, type_ != "Article")
        self.ligne_recherche.montrer(self.groupe_plage, plage)
        self.ligne_recherche.montrer(self.groupe_par, type_ in STATISTIQUES)
        self.ligne_recherche.montrer(self.groupe_categorie, type_ == "Article" or type_ in STATISTIQUES)
        self.champ_categorie.configurer_valeurs(self._categories())
        self.libelle_plage.configure(text=t("Article") if type_ == "Article" else t("Articles du"))
        if plage and "Article" not in self.listes and lire:
            def fin_articles(valeurs):
                self.listes["Article"] = valeurs
                self.champ_art_du.configurer_valeurs(valeurs)
                self.champ_art_au.configurer_valeurs(valeurs)
                self.aide_recherche.configure(text=self._aide(aides[type_], type_))

            self._lire_sage(rapports.articles, fin_articles, t("Lecture de la liste dans Sage…"), self.aide_recherche)
        elif plage and "Article" in self.listes:
            self.champ_art_du.configurer_valeurs(self.listes["Article"])
            self.champ_art_au.configurer_valeurs(self.listes["Article"])
        liste = STATISTIQUES.get(type_, type_)
        if liste == "Employé":
            if "Employé" in self.listes:
                self.champ_valeur.configurer_valeurs(self.listes["Employé"])
            elif lire:
                self._lire_employes(lambda: self.aide_recherche.configure(text=self._aide(aides[type_], type_)))
            return
        if liste not in ("Client", "Fournisseur"):
            self.champ_valeur.configurer_valeurs([])
            return
        if liste in self.listes:
            self.champ_valeur.configurer_valeurs(self.listes[liste])
        elif lire:  # listes tirées de l'historique (une seule lecture)
            self._avec_historique(lambda _h: self.aide_recherche.configure(text=self._aide(aides[type_], type_)))

    @staticmethod
    def _aide(texte: str, type_: str) -> str:
        if type_ in ("Client", "Fournisseur", "Article") or type_ in STATISTIQUES:
            return t(texte) + " " + t("Sans choix : tout est affiché.")
        return t(texte)

    def reinitialiser(self) -> None:
        """Vide tous les filtres (nom, plage d'articles, regroupement, période) et les résultats."""
        self.__dict__.get("_valeurs_par_sorte", {}).clear()
        for variable in (self.valeur, self.art_du, self.art_au, self.du, self.au, self.categorie):
            variable.set("")
        self.par.set(t(REGROUPEMENTS[0]))
        remplir(self.tableau_recherche, [], [])
        self.titre_recherche.configure(text="")
        self.aide_recherche.configure(text=t("Filtres réinitialisés : « Rechercher » sans filtre affiche tout."))

    def _categories(self) -> list[str]:
        """Catégories de la table « Comptes Sage par catégorie Clover » (les mêmes noms que dans Clover)."""
        from .creation_articles import TableCategories

        return sorted(TableCategories(self.racine).lignes, key=str.casefold)

    def _lire_employes(self, suite) -> None:
        """Noms des employés de Clover (lus une fois)."""
        self.aide_recherche.configure(text=t("Lecture des employés dans Clover…"))

        def travail():
            try:
                from .__main__ import charger_config
                from .api_clover import ClientClover
                from .statistiques_clover import referentiels

                employes = referentiels(ClientClover(charger_config(self.racine / "config.toml")))[0]
                noms = sorted(set(employes.values()), key=str.casefold)

                def fin():
                    self.listes["Employé"] = noms
                    if self._type() == "Statistiques employé":
                        self.champ_valeur.configurer_valeurs(noms)
                    suite()

                self.after(0, fin)
            except Exception as exc:
                texte = str(exc)
                self.after(0, lambda: self.aide_recherche.configure(text="✘ " + texte))

        threading.Thread(target=travail, daemon=True).start()

    def _date(self, variable: tk.StringVar) -> date | None:
        texte = variable.get().strip()
        return date.fromisoformat(texte) if texte else None

    def _par(self) -> str:
        return next(x for x in REGROUPEMENTS if t(x) == self.par.get())

    def rechercher(self) -> None:
        from . import rapports

        type_, valeur = self._type(), self.valeur.get().strip()
        try:
            du, au = self._date(self.du), self._date(self.au)
        except ValueError:
            messagebox.showwarning(self.titre, t("Date invalide : utilisez le format AAAA-MM-JJ (ou le calendrier 📅)."))
            return
        categorie = self.categorie.get().strip() if type_ == "Article" or type_ in STATISTIQUES else ""
        de = self.art_du.get().split(" — ")[0].strip()
        a = self.art_au.get().split(" — ")[0].strip()
        if type_ == "Article":  # aucun article choisi : tous les articles (chacun à la suite de l'autre)
            valeur = (self.art_du.get().strip() or t("tous")) + (f"  →  {self.art_au.get().strip()}" if a else "")
        elif not valeur and (type_ in ("Client", "Fournisseur") or type_ in STATISTIQUES):
            valeur = ""  # aucun filtre : tout est affiché
        par = self._par()
        tous = {"Client": "tous les clients", "Fournisseur": "tous les fournisseurs",
                "Statistiques client": "tous les clients", "Statistiques fournisseur": "tous les fournisseurs",
                "Statistiques employé": "tous les employés"}
        titre = t("Résultats : {type}", type=t(type_)) + (
            f" — {valeur}" if valeur else (f" — {t(tous[type_])}" if type_ in tous else "")) + (
            f" — {t('par')} {t(par).lower()}" if type_ in STATISTIQUES else "") + (
            f" — {t('articles')} {de} → {a or '…'}" if type_ in ("Statistiques client", "Statistiques fournisseur") and (de or a) else "") + (
            f" — {t('Catégorie').lower()} {categorie}" if categorie else "")

        def fin(resultat):
            entetes, lignes = resultat
            totaux = [i for i, l in enumerate(lignes) if any(str(v).startswith(("Total", "… plus de")) for v in l[:4])]
            remplir(self.tableau_recherche, entetes, lignes, {"Client / fournisseur": 220, "Facture": 170,
                                                              "Article": 260, "Catégorie": 170, "Type et pièce": 190},
                    lambda i: ("total",) if i in totaux else ())
            self.titre_recherche.configure(text=titre)
            self.aide_recherche.configure(text=t("{n} résultat(s).", n=len(lignes) - len(totaux)))

        if type_ == "Statistiques employé":
            self._statistiques_employe(valeur, par, du, au, fin, categorie)
            return
        categories = rapports.categories_par_compte(self.racine) if type_ in STATISTIQUES or categorie else {}
        fonctions = {
            "Article": lambda b: (rapports.mouvements_article(b, de, du, au) if de and (not a or a == de) and not categorie
                                  else rapports.mouvements_articles(b, de, a, du, au, categorie, categories)),
            "Vente": lambda b: rapports.recherche_ventes(b, valeur, du, au),
            "Encaissement": lambda b: rapports.recherche_encaissements(b, valeur, du, au),
            "Paiement": lambda b: rapports.recherche_paiements(b, valeur, du, au),
            "Statistiques client": lambda b: rapports.statistiques_tiers(b, "client", valeur, par, du, au, de, a,
                                                                         categories, categorie),
            "Statistiques fournisseur": lambda b: rapports.statistiques_tiers(b, "fournisseur", valeur, par, du, au,
                                                                              de, a, categories, categorie)}
        if type_ in fonctions:  # requête dans Sage (trop de lignes pour la mémoire)
            self._lire_sage(fonctions[type_], fin, t("Recherche dans Sage…"), self.aide_recherche)
            return
        en_memoire = {"Client": rapports.h_mouvements_client, "Fournisseur": rapports.h_mouvements_fournisseur}[type_]
        self._avec_historique(lambda h: fin(en_memoire(h, valeur, du, au)))

    def _statistiques_employe(self, employe: str, par: str, du, au, fin, categorie: str = "") -> None:
        """Ventes Clover de l'employé (vide : tous) par article ou par catégorie (jours terminés gardés en
        cache)."""
        from datetime import timedelta

        au = au or date.today()
        du = du or au - timedelta(days=29)
        self.aide_recherche.configure(text=t("Lecture de Clover…"))

        def progression(i, n, _debut, _fin):
            self.after(0, lambda: self.aide_recherche.configure(
                text=t("Lecture de Clover : {i} jour(s) lu(s) sur {n}…", i=i, n=n)))

        def travail():
            try:
                from .__main__ import charger_config
                from .api_clover import ClientClover
                from .statistiques_clover import filtrer, lire, statistiques

                client = ClientClover(charger_config(self.racine / "config.toml"))
                donnees = lire(client, du, au, self.racine / "donnees" / "cache_clover", progression)
                from .statistiques_clover import detail_par_jour

                filtres = {k: v for k, v in (("Employé", employe), ("Catégorie", categorie)) if v}
                nom_vue = "Par catégorie" if par.startswith("Catégorie") else "Par article"
                donnees = filtrer(donnees, filtres)
                vue = (detail_par_jour(donnees, nom_vue) if par.endswith("par jour")
                       else statistiques(donnees)[nom_vue])
                self.after(0, lambda: fin(vue))
                self.after(0, lambda: self.titre_recherche.configure(
                    text=self.titre_recherche.cget("text") + f" — {du.isoformat()} → {au.isoformat()}"))
            except Exception as exc:
                texte = str(exc)
                self.after(0, lambda: self.aide_recherche.configure(text="✘ " + texte))

        threading.Thread(target=travail, daemon=True).start()

    def _avec_historique(self, suite) -> None:
        """Historique Sage des clients et fournisseurs : lu une fois (10 minutes), puis recherches instantanées."""
        import time

        from . import rapports

        h = getattr(self, "historique_sage", None)
        if h and time.time() - h["_lu"] < 600:
            suite(h)
            return

        def garder(h):
            h["_lu"] = time.time()
            self.historique_sage = h
            self.listes["Client"], self.listes["Fournisseur"] = h["noms_clients"], h["noms_fournisseurs"]
            liste = STATISTIQUES.get(self._type(), self._type())
            if liste in ("Client", "Fournisseur"):
                self.champ_valeur.configurer_valeurs(self.listes[liste])
            suite(h)

        self._lire_sage(rapports.historique, garder, t("Lecture de l'historique de Sage (une fois)…"),
                        self.aide_recherche)

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
        barre = Rangee(cadre)  # passe à la ligne si la fenêtre est étroite
        barre.pack(fill="x")
        # filtre de date comme Clover : un bouton « 📅 Aujourd'hui ⌄ » qui ouvre la liste des périodes
        self.nom_periode = "Aujourd'hui"
        self.stat_du = tk.StringVar(value=date.today().isoformat())
        self.stat_au = tk.StringVar(value=date.today().isoformat())
        self.bouton_periode = barre.ajouter(Bouton(barre, "📅  " + t("Aujourd'hui") + "  ⌄", self._menu_periodes,
                                                   "secondaire", largeur=250), 10)
        self.libelle_periode = barre.ajouter(ttk.Label(barre, text="", foreground=TEXTE_DOUX), 10)
        barre.ajouter(Bouton(barre, "🔄  " + t("Actualiser"), self.calculer_statistiques, petit=True), 12)
        self.auto = tk.BooleanVar(value=True)
        barre.ajouter(ttk.Checkbutton(barre, text=t("Journée en cours : actualiser chaque minute"),
                                      variable=self.auto), 12)
        if export_permis():
            barre.ajouter(Bouton(barre, "📕  " + t("PDF de la page"), self.pdf_page, "secondaire", petit=True))
        filtres = Rangee(cadre)  # filtres globaux : tous les états de la période ; passent à la ligne si étroit
        filtres.pack(fill="x", pady=(6, 0))
        filtres.ajouter(ttk.Label(filtres, text=t("Filtrer :")), 6)
        self.filtres = {}
        self.champs_filtres = {}
        for nom in FILTRES_GLOBAUX:
            groupe = filtres.ajouter(filtres.groupe(), 10)
            ttk.Label(groupe, text=t(nom)).pack(side="left", padx=(0, 3))
            variable = tk.StringVar()
            champ = ChampRecherche(groupe, variable, [], largeur=16, au_choix=lambda _v=None: self.recalculer())
            champ.pack(side="left")
            self.filtres[nom], self.champs_filtres[nom] = variable, champ
        filtres.ajouter(Bouton(filtres, "✔  " + t("Appliquer"), self.recalculer, petit=True), 4)
        filtres.ajouter(Bouton(filtres, "✖  " + t("Effacer"), self.effacer_filtres, "secondaire", petit=True))
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

        # page « Aperçu des ventes » (comme Clover) : quatre graphiques
        self.page_apercu = tk.Frame(self.contenu_stats, background=fond_de(cadre))
        tk.Label(self.page_apercu, text=t("Aperçu des ventes"), font=("Segoe UI Semibold", 13), foreground=VERT_FONCE,
                 background=fond_de(cadre)).pack(anchor="w")
        self.resume_apercu = tk.Label(self.page_apercu, text="", font=("Segoe UI", 10), foreground=TEXTE,
                                      background=fond_de(cadre), justify="left", anchor="w", wraplength=780)
        self.resume_apercu.pack(fill="x", pady=(2, 6))
        grille = tk.Frame(self.page_apercu, background=fond_de(cadre))
        grille.pack(fill="both", expand=True)
        grille.columnconfigure((0, 1), weight=1, uniform="a")
        grille.rowconfigure((0, 1), weight=1)
        self.g_ap_evolution = Graphique(grille, 200, t("Ventes brutes et nettes"))
        self.g_ap_evolution.grid(row=0, column=0, sticky="nsew", padx=(0, 4), pady=(0, 4))
        self.g_ap_composition = Graphique(grille, 200, t("Des ventes brutes aux ventes nettes"))
        self.g_ap_composition.grid(row=0, column=1, sticky="nsew", padx=(4, 0), pady=(0, 4))
        self.g_ap_semaine = Graphique(grille, 200, t("Ventes par jour de la semaine"))
        self.g_ap_semaine.grid(row=1, column=0, sticky="nsew", padx=(0, 4), pady=(4, 0))
        self.g_ap_heure = Graphique(grille, 200, t("Ventes par heure"))
        self.g_ap_heure.grid(row=1, column=1, sticky="nsew", padx=(4, 0), pady=(4, 0))

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
        champ.bind("<KeyRelease>", apres_frappe(champ, self.afficher_statistiques))
        self.par_jour = tk.BooleanVar(value=False)  # vues regroupées : une ligne par jour, colonne Date en premier
        self.case_par_jour = ttk.Checkbutton(filtres, text=t("Détail par jour"), variable=self.par_jour,
                                             command=self.afficher_statistiques)
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
        self.titre_tableau = tk.Label(self.page_tableau, text="", font=("Segoe UI Semibold", 10), foreground=TEXTE,
                                      background=fond_de(cadre), anchor="w")
        self.titre_tableau.pack(fill="x", pady=(8, 0))
        self.tableau_stats = tableau_simple(self.page_tableau)
        self.tableau_stats.tag_configure("a_commander", background=COULEURS_PEREMPTION["rouge"])
        placer_a_droite(bouton_exporter(ligne, self.tableau_stats, t("Statistiques Clover")))
        self.donnees_prev = None
        self.vues_prev: dict = {}
        self._lecture_prev = False
        self.kpi_cadre = tk.Frame(self.page_tableau, background=fond_de(cadre))  # à droite de l'aperçu financier
        self.vues_articles: dict = {}
        self.vues_annees: dict = {}
        self.donnees_annees: dict = {}
        self._lecture_annees = False
        self._lecture_articles = False
        self.couts_clover: dict = {}   # ID Clover -> (n° Sage, CUMP Sage)
        self.moyens_stats: list = []

        # page « Péremption »
        self.page_peremption = tk.Frame(self.contenu_stats, background=fond_de(cadre))
        self._onglet_peremption(self.page_peremption)

        # page « Gestion » : rapport d'une fonction de gestion (cartes, évolution, répartition, tableau)
        self.page_gestion = tk.Frame(self.contenu_stats, background=fond_de(cadre))
        ligne_g = tk.Frame(self.page_gestion, background=fond_de(cadre))
        ligne_g.pack(fill="x")
        self.titre_gestion = tk.Label(ligne_g, text="", font=("Segoe UI Semibold", 13), foreground=VERT_FONCE,
                                      background=fond_de(cadre))
        self.titre_gestion.pack(side="left")
        self.note_gestion = ttk.Label(self.page_gestion, text="", foreground=TEXTE_DOUX, wraplength=900,
                                      justify="left")
        self.note_gestion.pack(fill="x", pady=(4, 0))
        self.cartes_gestion = tk.Frame(self.page_gestion, background=fond_de(cadre))
        self.cartes_gestion.pack(fill="x", pady=(6, 0))
        graphiques_g = tk.Frame(self.page_gestion, background=fond_de(cadre))
        graphiques_g.pack(fill="x", pady=(6, 0))
        graphiques_g.columnconfigure(0, weight=3, uniform="g")
        graphiques_g.columnconfigure(1, weight=2, uniform="g")
        self.g_gestion_evolution = Graphique(graphiques_g, 200)
        self.g_gestion_evolution.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        self.g_gestion_repartition = Graphique(graphiques_g, 200)
        self.g_gestion_repartition.grid(row=0, column=1, sticky="nsew", padx=(4, 0))
        tk.Label(self.page_gestion, text=t("Rapport détaillé"), font=("Segoe UI Semibold", 10), foreground=TEXTE,
                 background=fond_de(cadre), anchor="w").pack(fill="x", pady=(8, 0))
        self.tableau_gestion = tableau_simple(self.page_gestion, 10)
        placer_a_droite(bouton_exporter(ligne_g, self.tableau_gestion,
                                        lambda: self.titre_gestion.cget("text") or t("Gestion")))
        self._calcul_gestion = 0

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
                text=t("Lecture de Clover : {i} jour(s) lu(s) sur {n}…", i=i, n=n)))

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
                couts = self._couts_sage()
                self.brut_stats = {"donnees": donnees, "autres": autres, "couts": couts, "du": du,
                                   "au": au, "du2": du2, "au2": au2, "libelle": libelle,
                                   "completes": statistiques(donnees, couts)}  # sans filtre : calculé une fois
                self.donnees_annees = {}  # évolution par année : relue pour la nouvelle période
                resultat = self._calculer(self.brut_stats)
                self.after(0, lambda: self._fin_statistiques(resultat))
            except Exception as exc:
                texte = str(exc)
                self.after(0, lambda: (self.etat_stats.configure(text="✘ " + texte),
                                       setattr(self, "_calcul_en_cours", False)))

        threading.Thread(target=travail, daemon=True).start()

    def _filtres_actifs(self) -> dict[str, str]:
        return {nom: v.get().strip() for nom, v in self.filtres.items() if v.get().strip()}

    def _calculer(self, b: dict) -> dict:
        """Statistiques de la période et de sa comparaison, filtres globaux appliqués."""
        from .statistiques_clover import filtrer, montants_par_moyen, resume_rapide, series, statistiques

        f = self._filtres_actifs()
        donnees, autres = filtrer(b["donnees"], f), filtrer(b["autres"], f)
        return {"vues": statistiques(donnees, b["couts"]) if f else b["completes"], "avant": resume_rapide(autres),
                "libelle": b["libelle"], "series": series(donnees, b["du"], b["au"]),
                "series_avant": series(autres, b["du2"], b["au2"]), "moyens": montants_par_moyen(donnees),
                "du": b["du"], "au": b["au"], "du2": b["du2"], "filtres": f}

    def recalculer(self) -> None:
        """Un filtre a changé : nouveau calcul sur les données déjà lues (pas de nouvelle lecture de Clover)."""
        if not getattr(self, "brut_stats", None):
            return
        if self._calcul_en_cours:
            self._recalcul_attendu = True  # refait avec les derniers filtres dès la fin du calcul en cours
            return
        brut = self.brut_stats
        cle = tuple(sorted(self._filtres_actifs().items()))
        memoire = brut.setdefault("_par_filtres", {})
        if cle in memoire:  # combinaison déjà calculée : affichage immédiat
            self._calcul_en_cours = True
            self._fin_statistiques(memoire[cle])
            return
        self._calcul_en_cours = True
        self.etat_stats.configure(text=t("Calcul avec les filtres…"))

        def travail():
            try:
                resultat = self._calculer(brut)
                memoire[cle] = resultat
                self.after(0, lambda: self._fin_statistiques(resultat))
            except Exception as exc:
                texte = str(exc)
                self.after(0, lambda: (self.etat_stats.configure(text="✘ " + texte),
                                       setattr(self, "_calcul_en_cours", False)))

        threading.Thread(target=travail, daemon=True).start()

    def effacer_filtres(self) -> None:
        for variable in self.filtres.values():
            variable.set("")
        self.recalculer()

    def _couts_sage(self) -> dict:
        """ID Clover -> (n° Sage, CUMP) ; coûts lus dans Sage une fois par jour ; rien si Sage est illisible."""
        from .couts_sage import charger, cout_par_clover

        try:
            self.couts_clover = cout_par_clover(self.racine, charger(self.racine, self._config()))
        except Exception:
            self.couts_clover = {}
        return self.couts_clover

    def _fin_statistiques(self, r: dict) -> None:
        from .graphiques import BLEU, BLEU_PALE

        self._calcul_en_cours = False
        if getattr(self, "_recalcul_attendu", False):
            self._recalcul_attendu = False
            self.after(10, self.recalculer)
        self.vues_stats = r["vues"]
        self.moyens_stats = r["moyens"]
        from .rapports_gestion import CLES as CLES_GESTION

        if self.vue_courante in CLES_GESTION:  # nouvelle période : le rapport de gestion affiché suit
            self.after(0, self.afficher_gestion)
        completes = self.brut_stats["completes"]  # choix des filtres : toutes les valeurs de la période
        for nom, vue, colonne in (("Article", "Par article", 0), ("Client", "Par client", 0),
                                  ("Employé", "Par employé", 0), ("Catégorie", "Par catégorie", 0),
                                  ("Mode de paiement", "Par mode de paiement", 0)):
            self.champs_filtres[nom].configurer_valeurs(sorted({str(l[colonne]) for l in completes[vue][1]}
                                                               - {"Sans client"}, key=str.casefold))
        self.vues_annees.clear()
        if self.donnees_annees:
            self._calculer_annees()
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
            legende_avant = t(r["libelle"]).capitalize()
            if r["du2"].year != r["du"].year and r["du"].year == r["au"].year:  # l'an dernier : légende = années
                nom, legende_avant = str(r["du"].year), str(r["du2"].year)
            self.g_ventes.courbes(etiquettes, [(nom, valeurs, BLEU, False), (legende_avant, valeurs_avant, BLEU_PALE, True)],
                                  t("Aucune vente"))
        self.g_moyens.anneau([(t(k), v) for k, v in r["moyens"]], t("Aucun paiement"), format_valeur=montant)
        self.g_categories.anneau([(l[0], l[2]) for l in r["vues"]["Par catégorie"][1]], t("Aucune vente"),
                                 format_valeur=montant)
        articles = [(l[0], l[6]) for l in r["vues"]["Par article"][1][:8]]
        self.g_articles.classement(articles, vide=t("Aucune vente"), format_valeur=montant)
        self.etat_stats.configure(text=t("Mis à jour à {h} — variations par rapport à {x}.",
                                         h=f"{datetime.now():%H:%M}", x=t(r["libelle"]))
                                  + (t("   •   filtres : {f}", f=", ".join(f"{t(k)} = {v}" for k, v in r["filtres"].items()))
                                     if r["filtres"] else ""))
        self.afficher_statistiques()
        # journée en cours : nouvelle lecture dans 1 minute (seule la journée est relue ; les autres jours sont en cache)
        if self._minuterie:
            self.after_cancel(self._minuterie)
            self._minuterie = None
        if self.auto.get() and r["au"] >= date.today():
            self._minuterie = self.after(60 * 1000, self.calculer_statistiques)

    def pdf_page(self) -> None:
        """La page affichée en PDF : cartes et graphiques tels qu'à l'écran, puis le tableau complet (toutes ses
        lignes, pas seulement celles visibles), avec la période et les filtres."""
        from .export_tableau import contenu, demander_et_ecrire, ecrire_pdf, image_widget

        cle = self.vue_courante
        libelle = next((l for _, _, etats in NAVIGATION for l, c in etats if c == cle), cle)
        images, entetes, lignes = [], [], []
        if cle == "accueil":
            images = [image_widget(self.page_accueil)]
        elif cle == "apercu":
            images = [image_widget(self.page_apercu)]
        elif cle == "peremption":
            entetes, lignes = contenu(self.tableau_peremption)
        else:
            if self.kpi_cadre.winfo_ismapped():
                images.append(image_widget(self.kpi_cadre))
            if self.g_etat.winfo_ismapped():
                self.g_etat.delete("bulle")
                images.append(image_widget(self.g_etat))
            if self.tableau_stats.winfo_ismapped():
                entetes, lignes = contenu(self.tableau_stats)
        f = self._filtres_actifs()
        sous_titre = (f"{self.stat_du.get()} → {self.stat_au.get()}"
                      + (t("   •   filtres : {f}", f=", ".join(f"{t(k)} = {v}" for k, v in f.items())) if f else ""))
        nom = f"{t('Statistiques Clover')} — {t(libelle)}"
        demander_et_ecrire(self, nom, "pdf",
                           lambda chemin: ecrire_pdf(chemin, nom, entetes, lignes, images, sous_titre))

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
        for page in (self.page_accueil, self.page_apercu, self.page_tableau, self.page_peremption,
                     self.page_gestion):
            page.pack_forget()
        from .rapports_gestion import CLES as CLES_GESTION

        if cle in CLES_GESTION:
            self.page_gestion.pack(fill="both", expand=True)
            self.afficher_gestion()
        elif cle == "accueil":
            self.page_accueil.pack(fill="both", expand=True)
        elif cle == "apercu":
            self.page_apercu.pack(fill="both", expand=True)
            self.afficher_apercu()
        elif cle == "peremption":
            self.page_peremption.pack(fill="both", expand=True)
            if not self.peremption:
                self.lire_peremption()
        elif cle in ("liste_articles", "evolution_annees"):
            self.page_tableau.pack(fill="both", expand=True)
            self.titre_etat.configure(text=t("Liste d'articles") if cle == "liste_articles" else t("Évolution par année"))
            self.afficher_statistiques()
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

    # ---------------------------------------------------------------- rapports de gestion
    def afficher_gestion(self) -> None:
        """Rapport de la fonction de gestion choisie sur la période des statistiques (calcul dans un fil : les
        registres sont locaux, la caisse et la main-d'œuvre reprennent les ventes Clover déjà lues)."""
        import tomllib

        from .rapports_gestion import ETATS, calculer

        cle = self.vue_courante
        libelle = next((l for l, c, _f in ETATS if c == cle), cle)
        self.titre_gestion.configure(text=t(libelle))
        try:
            du, au = date.fromisoformat(self.stat_du.get()), date.fromisoformat(self.stat_au.get())
        except ValueError:
            return
        brut = getattr(self, "brut_stats", None) or {}
        contexte = {"ventes_par_jour": {}, "donnees": None}
        if brut and brut.get("du") == du and brut.get("au") == au:
            contexte["donnees"] = brut.get("donnees")
            for l in brut.get("completes", {}).get("Par jour", ([], []))[1]:
                try:
                    contexte["ventes_par_jour"][date.fromisoformat(str(l[0])[:10])] = Decimal(str(l[3]))
                except (ValueError, IndexError, ArithmeticError):
                    pass
        try:
            contexte["config"] = tomllib.loads((self.racine / "config.toml").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            contexte["config"] = {}
        self._calcul_gestion += 1
        numero = self._calcul_gestion
        self.note_gestion.configure(text=t("Calcul…"))

        def travail():
            try:
                rapport = calculer(cle, self.racine, du, au, contexte)
                self.after(0, lambda: numero == self._calcul_gestion and self._remplir_gestion(rapport))
            except Exception as exc:
                texte = str(exc)
                self.after(0, lambda: self.note_gestion.configure(text="✘ " + texte))

        threading.Thread(target=travail, daemon=True).start()

    def _remplir_gestion(self, r) -> None:
        from .graphiques import BLEU, BLEU_PALE, PALETTE

        self.note_gestion.configure(text=t(r.note) if r.note else "")
        for enfant in self.cartes_gestion.winfo_children():
            enfant.destroy()
        for i, (titre, genre, valeur) in enumerate(r.cartes):  # cartes d'indicateurs
            carte = tk.Frame(self.cartes_gestion, background=CARTE, highlightthickness=1,
                             highlightbackground="#e2e8e4")
            carte.grid(row=0, column=i, sticky="nsew", padx=3)
            self.cartes_gestion.columnconfigure(i, weight=1, uniform="cg")
            texte = (montant(valeur) if genre == "$" else f"{valeur} %".replace(".", ",") if genre == "%"
                     else f"{valeur} h".replace(".", ",") if genre == "h" else str(valeur))
            tk.Label(carte, text=t(titre), background=CARTE, foreground=TEXTE_DOUX, font=("Segoe UI", 9),
                     anchor="w").pack(fill="x", padx=8, pady=(6, 0))
            tk.Label(carte, text=texte, background=CARTE, foreground=VERT_FONCE, font=("Segoe UI Semibold", 15),
                     anchor="w").pack(fill="x", padx=8, pady=(0, 6))
        vide = t("Aucune donnée pour la période")
        # graphique d'évolution (courbe ; barres pour un seul jour)
        self.g_gestion_evolution.titre = t(r.titre_evolution)
        couleurs = [BLEU, "#f6b81a", *PALETTE]
        if len(r.etiquettes) <= 1:
            self.g_gestion_evolution.barres(r.etiquettes, [(t(n), v, couleurs[k]) for k, (n, v) in enumerate(r.series)],
                                            vide)
        else:
            self.g_gestion_evolution.courbes(r.etiquettes, [(t(n), v, couleurs[k], k > 0)
                                                            for k, (n, v) in enumerate(r.series)], vide)
        # carte graphique (répartition)
        self.g_gestion_repartition.titre = t(r.titre_repartition)
        format_ = montant if r.argent_repartition else (lambda v: f"{v:.0f}" if v == int(v) else f"{v:.1f}")
        valeurs = [(t(n), v) for n, v in r.repartition]
        if r.genre_repartition == "anneau":
            self.g_gestion_repartition.anneau(valeurs, vide, format_valeur=format_)
        else:
            self.g_gestion_repartition.classement(valeurs, vide=vide, format_valeur=format_, couleur=BLEU_PALE)
        remplir(self.tableau_gestion, r.entetes, [[t(x) if isinstance(x, str) and x in TEXTES_GESTION else x
                                                   for x in l] for l in r.lignes])

    def afficher_apercu(self) -> None:
        """Aperçu des ventes : évolution brutes / nettes, composition, jour de la semaine, heure."""
        from .graphiques import BLEU, BLEU_PALE

        if not self.vues_stats:
            return
        v = self.vues_stats
        resume = dict(v["Résumé"][1])
        brutes, nettes = resume["Ventes brutes (articles)"], resume["Ventes nettes (articles)"]
        self.resume_apercu.configure(text=t(
            "Ventes brutes {b}   •   rabais {r}   •   remboursements {m}   •   ventes nettes {n}   •   "
            "{c} commande(s), panier moyen {p}", b=montant(brutes), r=montant(resume["Rabais"]),
            m=montant(resume["Remboursements (articles)"]), n=montant(nettes), c=resume["Commandes payées"],
            p=montant(resume["Panier moyen"])))
        lignes = v["Rapport des ventes"][1]  # par jour (ou par heure pour une journée)
        etiquettes = [l[0][8:10] + "/" + l[0][5:7] if len(l[0]) == 10 else l[0] for l in lignes]
        if len(lignes) > 1 and len(lignes[0][0]) == 10:
            self.g_ap_evolution.courbes(etiquettes, [(t("Ventes brutes"), [l[3] for l in lignes], BLEU_PALE, False),
                                                     (t("Ventes nettes"), [l[6] for l in lignes], BLEU, False)],
                                        t("Aucune vente"))
        else:
            self.g_ap_evolution.barres(etiquettes, [(t("Ventes brutes"), [l[3] for l in lignes], BLEU_PALE),
                                                    (t("Ventes nettes"), [l[6] for l in lignes], BLEU)], t("Aucune vente"))
        self.g_ap_composition.anneau([(t("Ventes nettes"), nettes), (t("Rabais"), abs(resume["Rabais"])),
                                      (t("Remboursements"), abs(resume["Remboursements (articles)"]))],
                                     t("Aucune vente"), format_valeur=montant)
        semaine = v["Par jour de la semaine"][1]
        self.g_ap_semaine.barres([t(l[0])[:3] for l in semaine], [(t("Ventes nettes"), [l[2] for l in semaine], BLEU)],
                                 t("Aucune vente"))
        heures = v["Par heure"][1]
        self.g_ap_heure.barres([l[0].replace(" h", "h") for l in heures],
                               [(t("Ventes nettes"), [l[2] for l in heures], BLEU)], t("Aucune vente"))

    def _vue_par_jour(self, nom: str) -> tuple[list[str], list[list]]:
        """Vue `nom` jour par jour, filtres globaux appliqués ; calculée une fois par jeu de données et filtres."""
        from .statistiques_clover import detail_par_jour, filtrer

        brut = self.brut_stats
        f = self._filtres_actifs()
        cle = (nom, tuple(sorted(f.items())))
        memoire = brut.setdefault("_par_jour", {})
        if cle not in memoire:
            memoire[cle] = detail_par_jour(filtrer(brut["donnees"], f), nom, brut.get("couts"))
        return memoire[cle]

    def afficher_statistiques(self) -> None:
        nom = self.vue_courante
        if nom == "apercu":
            self.afficher_apercu()
            return
        if nom in ("accueil", "peremption"):
            return
        if nom in PREVISIONS:
            self.cadre_horizon.pack(side="left")
        else:
            self.cadre_horizon.pack_forget()
        if nom == "liste_articles" and not self.vues_articles:
            self.lire_liste_articles()
        if nom == "evolution_annees" and not self.vues_annees:
            self.lire_annees()
        source = (self.vues_prev if nom in PREVISIONS else self.vues_articles if nom == "liste_articles"
                  else self.vues_annees if nom == "evolution_annees" else self.vues_stats)
        from .statistiques_clover import VUES_PAR_JOUR

        if nom in VUES_PAR_JOUR:
            self.case_par_jour.pack(side="left", padx=(12, 0))
        else:
            self.case_par_jour.pack_forget()
        if nom in VUES_PAR_JOUR and self.par_jour.get() and source is self.vues_stats and nom in source:
            source = {nom: self._vue_par_jour(nom)}
        self._afficher_kpi(nom == "Résumé")
        if nom not in source:
            self.tableau_stats.delete(*self.tableau_stats.get_children())
            self.g_etat.pack_forget()
            self.note_etat.configure(text="")
            return
        entetes, lignes = source[nom]
        self.note_etat.configure(text=t(NOTES_ETATS.get(nom, "")) if NOTES_ETATS.get(nom) else "")
        # graphique : totaux de la période, même avec le détail par jour (colonne Date en plus dans le tableau)
        self._graphique_etat(nom, self.vues_stats[nom][1] if source is not self.vues_stats and nom in self.vues_stats
                             and nom in VUES_PAR_JOUR else lignes)
        texte = self.recherche_etat.get().strip().casefold()
        if texte:
            lignes = [l for l in lignes if any(texte in str(v).casefold() for v in l)]
        lignes = [[t(x) if isinstance(x, str) and nom == "Résumé" else x for x in l] for l in lignes]
        libelle = next((l for _, _, etats in NAVIGATION for l, c in etats if c == nom), nom)
        self.titre_tableau.configure(text=t("Tableau : {etat} — {n} ligne(s)", etat=t(libelle), n=len(lignes)))
        remplir(self.tableau_stats, entetes, lignes, decroissant=nom not in PREVISIONS, largeurs={
            "Indicateur": 175 if nom == "Résumé" else 320, "Valeur": 105, "Article": 280, "Client": 240,
            "Employé": 190, "Appareil": 300, "Date et heure": 130},
            tags=lambda i: ("a_commander",) if t(A_COMMANDER_TEXTE) in lignes[i] else ())

    def _afficher_kpi(self, montrer: bool) -> None:
        """Aperçu financier : tableau étroit à gauche, le plus de KPI possible en cartes à droite."""
        from .statistiques_clover import kpis

        cadre_table = self.tableau_stats.master
        self.kpi_cadre.pack_forget()
        for enfant in self.kpi_cadre.winfo_children():
            enfant.destroy()
        if not montrer or not self.vues_stats:
            if not cadre_table.winfo_manager():
                self.titre_tableau.pack(fill="x", pady=(8, 0))
                cadre_table.pack(fill="both", expand=True, pady=(6, 0))
            return
        # toute la place aux indicateurs (le tableau, rempli quand même, reste exportable)
        cadre_table.pack_forget()
        self.titre_tableau.pack_forget()
        self.kpi_cadre.pack(fill="both", expand=True, pady=(6, 0))
        colonnes = 4
        for i, (titre, genre, valeur) in enumerate(kpis(self.vues_stats, self.moyens_stats)):
            carte = tk.Frame(self.kpi_cadre, background=CARTE, highlightthickness=1, highlightbackground="#e2e8e4")
            carte.grid(row=i // colonnes, column=i % colonnes, sticky="nsew", padx=3, pady=3)
            self.kpi_cadre.columnconfigure(i % colonnes, weight=1, uniform="kpi")
            texte = (montant(valeur) if genre == "$" else f"{valeur} %".replace(".", ",") if genre == "%"
                     else str(valeur).replace(".", ",") if genre == "n" else t(str(valeur)))
            tk.Label(carte, text=t(titre), background=CARTE, foreground=TEXTE_DOUX, font=("Segoe UI", 9),
                     anchor="w").pack(fill="x", padx=8, pady=(5, 0))
            tk.Label(carte, text=texte, background=CARTE, foreground=VERT_FONCE if titre.startswith("Bénéfice")
                     else TEXTE, font=("Segoe UI Semibold", 12 if genre != "t" else 9), anchor="w",
                     wraplength=150, justify="left").pack(fill="x", padx=8, pady=(0, 5))

    # ---------------------------------------------------------------- liste d'articles (Clover + coût Sage)
    def lire_liste_articles(self) -> None:
        if self._lecture_articles:
            return
        self._lecture_articles = True
        self.note_etat.configure(text=t("Lecture des articles dans Clover et des coûts dans Sage…"))

        def travail():
            try:
                from .__main__ import charger_config
                from .api_clover import ClientClover
                from .couts_sage import charger, correspondance

                client = ClientClover(charger_config(self.racine / "config.toml"))
                articles = [a for a in client._pages("items", {"expand": "categories,itemStock"})
                            if not a.get("deleted")]
                try:
                    couts = charger(self.racine, self._config())
                except Exception:
                    couts = {}
                lien = correspondance(self.racine)
                self.after(0, lambda: self._fin_liste_articles(articles, couts, lien))
            except Exception as exc:
                texte = str(exc)
                self.after(0, lambda: (self.note_etat.configure(text="✘ " + texte),
                                       setattr(self, "_lecture_articles", False)))

        threading.Thread(target=travail, daemon=True).start()

    def _fin_liste_articles(self, articles: list, couts: dict, lien: dict) -> None:
        self._lecture_articles = False
        types = {"FIXED": "Fixe", "VARIABLE": "Variable", "PER_UNIT": "Au poids / à l'unité"}
        lignes = []
        for a in sorted(articles, key=lambda x: (x.get("name") or "").casefold()):
            prix = Decimal(int(a.get("price") or 0)) / 100
            numero = lien.get(a["id"], "")
            cout = couts.get(numero)
            cump = cout.cump if cout else None
            stock = (a.get("itemStock") or {}).get("quantity")
            categories = (a.get("categories") or {}).get("elements") or []
            lignes.append([
                (a.get("name") or "").strip(), categories[0].get("name", "") if categories else "",
                (a.get("code") or "").strip(), (a.get("sku") or "").strip(), prix,
                t(types.get(a.get("priceType"), a.get("priceType") or "")) + (
                    f" ({a['unitName']})" if a.get("unitName") else ""),
                Decimal(int(a["cost"])) / 100 if a.get("cost") else None,
                None if stock is None else Decimal(str(stock)).normalize(), numero, cump,
                ((prix - cump) * 100 / prix).quantize(Decimal("0.1")) if cump is not None and prix else None,
                cout.quantite.normalize() if cout else None, cout.valeur if cout else None,
                t("Oui") if a.get("defaultTaxRates") else t("Non"), t("Caché") if a.get("hidden") else t("Visible"),
                t("CUMP douteux (à vérifier dans Sage)") if cump and prix and cump > SEUIL_CUMP_DOUTEUX * prix else ""])
        self.vues_articles["liste_articles"] = (
            ["Article", "Catégorie", "Code-barres", "SKU", "Prix de vente", "Type de prix", "Coût Clover",
             "Stock Clover", "N° Sage", "CUMP Sage", "Marge sur prix %", "Stock Sage", "Valeur du stock Sage",
             "Taxable", "Affichage", "Contrôle"], lignes)
        relies = sum(1 for l in lignes if l[8])
        NOTES_ETATS["liste_articles"] = t("{n} article(s) Clover, dont {r} relié(s) à un article Sage ({c} avec un "
                                          "CUMP). Marge sur prix = (prix de vente − CUMP Sage) / prix de vente.",
                                          n=len(lignes), r=relies, c=sum(1 for l in lignes if l[9] is not None))
        self.afficher_statistiques()

    # ---------------------------------------------------------------- évolution par année
    ANNEES_COMPAREES = 2  # années d'avant comparées à la période

    def lire_annees(self) -> None:
        """Même période les années d'avant (cache Clover), puis courbe par jour avec une série par année."""
        if self._lecture_annees or not getattr(self, "brut_stats", None):
            return
        self._lecture_annees = True
        b = self.brut_stats
        self.note_etat.configure(text=t("Lecture de la même période les années d'avant…"))

        def travail():
            try:
                from .__main__ import charger_config
                from .api_clover import ClientClover
                from .statistiques_clover import lire

                client = ClientClover(charger_config(self.racine / "config.toml"))
                annees = {b["du"].year: b["donnees"]}
                for k in range(1, self.ANNEES_COMPAREES + 1):
                    try:
                        du, au = b["du"].replace(year=b["du"].year - k), b["au"].replace(year=b["au"].year - k)
                    except ValueError:
                        du, au = b["du"].replace(year=b["du"].year - k, day=28), b["au"].replace(year=b["au"].year - k, day=28)
                    annees[b["du"].year - k] = lire(client, du, au, self.racine / "donnees" / "cache_clover")
                self.after(0, lambda: self._fin_annees(annees))
            except Exception as exc:
                texte = str(exc)
                self.after(0, lambda: (self.note_etat.configure(text="✘ " + texte),
                                       setattr(self, "_lecture_annees", False)))

        threading.Thread(target=travail, daemon=True).start()

    def _fin_annees(self, annees: dict) -> None:
        self._lecture_annees = False
        self.donnees_annees = annees
        self._calculer_annees()

    def _calculer_annees(self) -> None:
        from .statistiques_clover import evolution_par_annee, filtrer

        if not self.donnees_annees:
            return
        b, f = self.brut_stats, self._filtres_actifs()
        etiquettes, series = evolution_par_annee({a: filtrer(d, f) for a, d in self.donnees_annees.items()},
                                                 b["du"], b["au"])
        annees = list(series)
        lignes = []
        for i, jour in enumerate(etiquettes):
            valeurs = [series[a][i] for a in annees]
            ecart = (None if len(valeurs) < 2 or not valeurs[1] or valeurs[0] is None else
                     ((valeurs[0] - valeurs[1]) * 100 / valeurs[1]).quantize(Decimal("0.1")))
            lignes.append([jour] + valeurs + [ecart])
        self.vues_annees["evolution_annees"] = (["Date"] + [str(a) for a in annees] + [
            f"% {annees[0]} / {annees[1]}" if len(annees) > 1 else "%"], lignes)
        self.series_annees = (etiquettes, series)
        totaux = {a: sum((v or 0 for v in series[a]), Decimal(0)) for a in annees}
        NOTES_ETATS["evolution_annees"] = "   •   ".join(f"{a} : {montant(v)}" for a, v in totaux.items())
        self.afficher_statistiques()

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
            self.g_etat.pack(fill="x", pady=(6, 0), before=self.titre_tableau)
            return
        if nom == "evolution_annees" and getattr(self, "series_annees", None):
            from .graphiques import PALETTE

            etiquettes, series = self.series_annees
            self.g_etat.titre = t("Ventes nettes par jour, année par année")
            self.g_etat.courbes(etiquettes, [(str(a), v, PALETTE[k % len(PALETTE)], k > 0)
                                             for k, (a, v) in enumerate(series.items())], t("Aucune vente"))
            self.g_etat.pack(fill="x", pady=(6, 0), before=self.titre_tableau)
            return
        if nom == "prev_commande":
            compte = {}
            for l in lignes:
                compte[l[5]] = compte.get(l[5], 0) + 1
            self.g_etat.titre = t("Articles vendus en {n} jours", n=self._horizon())
            self.g_etat.anneau([(t(k), Decimal(v)) for k, v in compte.items()], t("Aucune vente"),
                               format_valeur=lambda v: f"{v:.0f}")
            self.g_etat.pack(fill="x", pady=(6, 0), before=self.titre_tableau)
            return
        if nom == "Rapport des ventes" and lignes:  # brutes et nettes, comme Clover
            etiquettes = [l[0][8:10] + "/" + l[0][5:7] if len(l[0]) == 10 else l[0] for l in lignes]
            self.g_etat.titre = t("Ventes brutes et nettes")
            self.g_etat.barres(etiquettes, [(t("Ventes brutes"), [l[3] for l in lignes], BLEU_PALE),
                                            (t("Ventes nettes"), [l[6] for l in lignes], BLEU)], t("Aucune vente"))
            self.g_etat.pack(fill="x", pady=(6, 0), before=self.titre_tableau)
            return
        if nom == "Jour × heure" and lignes:
            entetes = self.vues_stats[nom][0]
            self.g_etat.titre = t(TITRES_GRAPHIQUES[nom])
            self.g_etat.chaleur([t(l[0])[:3] for l in lignes], [e.replace(" h", "h") for e in entetes[1:-1]],
                                [l[1:-1] for l in lignes], t("Aucune vente"))
            self.g_etat.pack(fill="x", pady=(6, 0), before=self.titre_tableau)
            return
        genre = GRAPHIQUES_ETATS.get(nom)
        if not genre or not lignes:
            self.g_etat.pack_forget()
            return
        type_, i_nom, i_val = genre
        valeurs = [(str(l[i_nom]), abs(l[i_val]) if isinstance(l[i_val], Decimal) else Decimal(l[i_val] or 0))
                   for l in lignes]
        self.g_etat.titre = t(TITRES_GRAPHIQUES.get(nom, "Les 8 premiers"))
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
        self.g_etat.pack(fill="x", pady=(6, 0), before=self.titre_tableau)

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
        champ.bind("<KeyRelease>", apres_frappe(champ, self.afficher_peremption))
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
        tk.Label(cadre, text=t("Articles et dates de péremption (champ SKU de Clover)"), font=("Segoe UI Semibold", 10),
                 foreground=TEXTE, background=fond_de(cadre), anchor="w").pack(fill="x", pady=(4, 0))
        self.tableau_peremption = tableau_simple(cadre)
        for cle, couleur in COULEURS_PEREMPTION.items():
            self.tableau_peremption.tag_configure(cle, background=couleur)
        placer_a_droite(bouton_exporter(barre, self.tableau_peremption, t("Péremption")))
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
        champ.bind("<KeyRelease>", apres_frappe(champ, self.afficher_archives))
        Bouton(barre, "📄  " + t("Voir la facture"), self.ouvrir_piece, "secondaire", petit=True).pack(
            side="left", padx=(12, 6))
        if export_permis():
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
        placer_a_droite(bouton_exporter(barre, self.tableau_archives, t("Factures fournisseurs archivées")))
        tk.Label(cadre, text=t("Lignes de la facture choisie"), font=("Segoe UI Semibold", 10),
                 background=fond_de(cadre)).pack(anchor="w", pady=(10, 0))
        self.tableau_lignes = tableau_simple(cadre, hauteur=6)

    def _au_changement(self) -> None:
        onglet = self.onglets.index("current")
        if onglet == 2:
            self.charger_archives()
        elif onglet == 3 and not self.vues_stats and not self._calcul_en_cours:
            self.calculer_statistiques()  # journée en cours dès l'ouverture de l'onglet
        elif onglet == 4:
            self.onglet_inactifs.premiere_fois()
        elif onglet == 5:
            self.onglet_pareto.premiere_fois()

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

