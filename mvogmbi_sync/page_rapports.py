"""Page « 11. Rapports » : suivi complet des ventes, recherches dans l'historique de Sage (client, fournisseur, vente,
encaissement, paiement, article) et factures fournisseurs archivées."""

from __future__ import annotations

import os
import re
import threading
import tkinter as tk
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from tkinter import messagebox, ttk

from .design import (TEXTE_DOUX, Bouton, ChampDate, ChampRecherche, cadre_tableau, entete_page, fond_de,
                     rayer)
from .export_tableau import bouton_exporter
from .langues import t

# couleurs des lignes du suivi : vente bloquée, à encaisser, encaissée mais pas retrouvée sur les relevés
COULEURS = {"bloquee": "#fde2e4", "a_encaisser": "#fff4d6", "a_rapprocher": "#eaf2fb"}
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
                elif "Quantité" in entete or "Cumul" in entete:
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
    def _onglet_statistiques(self) -> None:
        from .statistiques_clover import VUES

        cadre = ttk.Frame(self.onglets, padding=(0, 8, 0, 0))
        self.onglets.add(cadre, text="  " + t("Statistiques Clover") + "  ")
        barre = ttk.Frame(cadre)
        barre.pack(fill="x")
        hier = date.today() - timedelta(days=1)
        ttk.Label(barre, text=t("Période du")).pack(side="left", padx=(0, 4))
        self.stat_du = tk.StringVar(value=hier.replace(day=1).isoformat())
        ChampDate(barre, self.stat_du).pack(side="left")
        ttk.Label(barre, text=t("au")).pack(side="left", padx=4)
        self.stat_au = tk.StringVar(value=hier.isoformat())
        ChampDate(barre, self.stat_au).pack(side="left")
        Bouton(barre, "📈  " + t("Calculer"), self.calculer_statistiques, petit=True).pack(side="left", padx=8)
        ttk.Label(barre, text=t("Vue :")).pack(side="left", padx=(12, 4))
        self.vue = tk.StringVar(value=t(VUES[0]))
        choix = ttk.Combobox(barre, textvariable=self.vue, values=[t(v) for v in VUES], state="readonly", width=28)
        choix.pack(side="left")
        choix.bind("<<ComboboxSelected>>", lambda _e: self.afficher_statistiques())
        self.etat_stats = ttk.Label(cadre, text=t("Choisissez la période puis « Calculer » : chaque jour terminé déjà "
                                                  "lu dans Clover est gardé et s'affiche ensuite tout de suite."),
                                    foreground=TEXTE_DOUX, padding=(0, 6))
        self.etat_stats.pack(fill="x")
        self.tableau_stats = tableau_simple(cadre)
        bouton_exporter(barre, self.tableau_stats, t("Statistiques Clover")).pack(side="right")
        self.vues_stats: dict = {}

    def calculer_statistiques(self) -> None:
        try:
            du, au = date.fromisoformat(self.stat_du.get().strip()), date.fromisoformat(self.stat_au.get().strip())
        except ValueError:
            messagebox.showwarning(self.titre, t("Date invalide : utilisez le format AAAA-MM-JJ (ou le calendrier 📅)."))
            return
        if du > au or au >= date.today():
            messagebox.showwarning(self.titre, t("Choisissez une période terminée (au plus tard hier), début avant la fin."))
            return
        self.etat_stats.configure(text=t("Lecture de Clover…"))

        def progression(i, n, jour):
            self.after(0, lambda: self.etat_stats.configure(
                text=t("Lecture de Clover : jour {i} sur {n} ({j})…", i=i, n=n, j=jour)))

        def travail():
            try:
                from .__main__ import charger_config
                from .api_clover import ClientClover
                from .statistiques_clover import lire, statistiques

                client = ClientClover(charger_config(self.racine / "config.toml"))
                donnees = lire(client, du, au, self.racine / "donnees" / "cache_clover", progression)
                vues = statistiques(donnees)
                self.after(0, lambda: self._fin_statistiques(vues, du, au))
            except Exception as exc:
                texte = str(exc)
                self.after(0, lambda: self.etat_stats.configure(text="✘ " + texte))

        threading.Thread(target=travail, daemon=True).start()

    def _fin_statistiques(self, vues: dict, du: date, au: date) -> None:
        self.vues_stats = vues
        resume = dict(vues["Résumé"][1])
        self.etat_stats.configure(text=t("Du {du} au {au} : {c} commande(s), ventes nettes {v}, panier moyen {p}.",
                                         du=du, au=au, c=resume["Commandes payées"],
                                         v=montant(resume["Ventes nettes (articles)"]),
                                         p=montant(resume["Panier moyen"])))
        self.afficher_statistiques()

    def afficher_statistiques(self) -> None:
        from .statistiques_clover import VUES

        if not self.vues_stats:
            return
        nom = next(v for v in VUES if t(v) == self.vue.get())
        entetes, lignes = self.vues_stats[nom]
        lignes = [[t(x) if isinstance(x, str) and nom == "Résumé" else x for x in l] for l in lignes]
        remplir(self.tableau_stats, entetes, lignes, {"Indicateur": 320, "Article": 300, "Client": 240,
                                                      "Employé": 190, "Appareil": 300, "Date et heure": 130})

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
        if self.onglets.index("current") == 2:
            self.charger_archives()

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

