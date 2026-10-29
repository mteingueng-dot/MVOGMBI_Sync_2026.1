"""Page « Factures fournisseurs » : lecture des PDF et photos, vérification, correspondance des articles avec Sage."""

from __future__ import annotations

import os
import threading
import tkinter as tk
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from tkinter import messagebox, ttk

from rapidfuzz import fuzz, process

from .articles_sage import lire_copie
from .correspondance import conflit_format, normaliser
from .design import (CARTE, ROUGE, TEXTE_DOUX, VERT_FONCE, Bouton, ChampDate, ChampRecherche, apres_frappe, cadre_tableau,
                     entete_page, fond_de, rayer)
from .fournisseurs import (A_SAISIR, A_VERIFIER, ETATS, IMPORTEE, PRETE, Ligne, MemoireCorrespondance, Registre,
                           completer, etat_apres_controle, lire_copie_fournisseurs, lire_facture)
from .export_tableau import bouton_exporter, placer_a_droite, rendre_exportable
from .langues import t

COULEURS = {A_SAISIR: "#fff4d6", A_VERIFIER: "#fde2e4", PRETE: "#e6f4ea", IMPORTEE: None}
COLONNES_LIGNES = (("code", "Code", 60), ("description", "Désignation du fournisseur", 190), ("quantite", "Qté", 50),
                   ("prix", "Prix fournisseur", 85), ("montant", "Montant", 80), ("numero_sage", "N° Sage", 95),
                   ("description_sage", "Désignation Sage", 170), ("qte_sage", "Qté Sage", 70),
                   ("prix_sage", "Prix Sage", 80), ("facteur", "Facteur", 55), ("etat", "Correspondance", 100))


def decimal(texte: str) -> Decimal:
    nettoye = str(texte).replace("$", "").replace(" ", "").replace("\xa0", "").replace(",", ".")
    try:
        return Decimal(nettoye or "0")
    except InvalidOperation:
        raise ValueError(t("Nombre invalide : {v}", v=texte))


class PageFournisseurs(ttk.Frame):
    def __init__(self, parent, racine: Path, titre: str):
        super().__init__(parent, padding=10)
        self.racine, self.titre = Path(racine), titre
        self.registre = Registre(self.racine)
        self.memoire = MemoireCorrespondance(self.racine)
        self.fournisseurs_sage = lire_copie_fournisseurs(self.racine)
        self.articles_sage = lire_copie(self.racine / "donnees" / "articles_sage.csv")
        self.normalises = [normaliser(f"{a.description} {a.numero}") for a in self.articles_sage]
        self.facture = None
        self.choix_sage = []
        self._ligne_editee = None  # rang de la ligne affichée dans la carte d'édition
        self._minuterie = None  # enregistrement automatique en attente
        self._chargement = False

        entete_page(self, "🧾", t("Factures fournisseurs"),
                    t("lecture des factures, articles Sage et import dans Sage")).pack(fill="x")
        barre = ttk.Frame(self)
        barre.pack(fill="x")
        Bouton(barre, "➕  " + t("Ajouter des factures…"), self.ajouter_factures).pack(side="left")
        Bouton(barre, "📧  " + t("Lire le courriel"), self.lire_courriel, "secondaire").pack(side="left", padx=(8, 0))
        Bouton(barre, "⟳  " + t("Actualiser"), self.actualiser, "secondaire").pack(side="left", padx=(8, 0))
        Bouton(barre, "📂  " + t("Dossier des factures"), self.ouvrir_dossier, "secondaire").pack(side="left", padx=8)
        Bouton(barre, "📒  " + t("Fournisseurs et articles Sage"), self.mettre_a_jour_sage, "secondaire").pack(side="left")
        ttk.Label(barre, text=t("Afficher :")).pack(side="left", padx=(16, 4))
        self.filtre = tk.StringVar(value=t("Toutes"))
        liste = ttk.Combobox(barre, textvariable=self.filtre, state="readonly", width=20,
                             values=[t("Toutes")] + [t(e) for e in ETATS])
        liste.pack(side="left")
        liste.bind("<<ComboboxSelected>>", lambda _e: self.afficher_liste())
        Bouton(barre, "📤  " + t("Importer toutes les factures prêtes"), lambda: self.importer(toutes=True),
               "accent").pack(side="right", padx=(8, 0))
        self.resume = ttk.Label(self, text="", foreground=TEXTE_DOUX, padding=(0, 6))
        self.resume.pack(fill="x")

        volets = ttk.PanedWindow(self, orient="vertical")
        volets.pack(fill="both", expand=True)
        haut = cadre_tableau(volets)
        volets.add(haut, weight=1)
        colonnes = (("fichier", "Fichier", 220), ("fournisseur", "Fournisseur Sage", 220), ("numero", "N°", 90),
                    ("date", "Date", 85), ("total", "Total", 90), ("etat", "État", 130))
        self.liste = ttk.Treeview(haut, columns=[c[0] for c in colonnes], show="headings", height=3, selectmode="browse")
        for cle, titre_col, largeur in colonnes:
            self.liste.heading(cle, text=t(titre_col))
            self.liste.column(cle, width=largeur, anchor="e" if cle == "total" else "w", stretch=cle == "fichier")
        for etat, couleur in COULEURS.items():  # sans couleur : état terminé, texte grisé sur lignes rayées
            self.liste.tag_configure(etat, **({"background": couleur} if couleur else {"foreground": TEXTE_DOUX}))
        defil = ttk.Scrollbar(haut, orient="vertical", command=self.liste.yview)
        self.liste.configure(yscrollcommand=defil.set)
        defil.pack(side="right", fill="y")  # avant le tableau : toujours visible, même s'il est large
        self.liste.pack(side="left", fill="both", expand=True)
        self.liste.bind("<<TreeviewSelect>>", lambda _e: self.choisir_facture())
        placer_a_droite(bouton_exporter(barre, self.liste, t("Factures fournisseurs")))
        self.liste.bind("<Delete>", lambda _e: self.ecarter())
        self.bind("<Map>", lambda _e: self.actualiser(silencieux=True))  # retour sur la page : liste à jour
        # départ de la page ou fermeture : la saisie en cours est gardée
        self.bind("<Unmap>", lambda e: self.sauvegarder_auto() if e.widget is self else None)
        self.bind("<Destroy>", lambda e: self.sauvegarder_auto() if e.widget is self else None)

        bas = ttk.Frame(volets)
        volets.add(bas, weight=3)
        self._construire_detail(bas)
        self.afficher_liste()
        if not self.fournisseurs_sage or not self.articles_sage:
            self.after(800, self.mettre_a_jour_sage)  # première ouverture : listes lues dans Sage

    # ---------------------------------------------------------------- construction du détail
    def _construire_detail(self, parent) -> None:
        self.v = {cle: tk.StringVar() for cle in ("fournisseur", "numero", "date", "sous_total", "tps", "tvq", "total")}
        entete = ttk.Frame(parent, padding=(0, 6, 0, 2))
        entete.pack(fill="x")
        ttk.Label(entete, text=t("Fournisseur Sage")).pack(side="left")
        # recherche rapide : taper quelques lettres (« basm », « champs ») affiche les fournisseurs Sage correspondants
        self.liste_fournisseurs = ChampRecherche(entete, self.v["fournisseur"], self.fournisseurs_sage, largeur=34)
        self.liste_fournisseurs.pack(side="left", padx=(4, 12))
        ttk.Label(entete, text=t("N° de facture")).pack(side="left")
        ttk.Entry(entete, textvariable=self.v["numero"], width=12).pack(side="left", padx=(4, 12))
        ttk.Label(entete, text=t("Date")).pack(side="left")
        ChampDate(entete, self.v["date"]).pack(side="left", padx=(4, 12))
        Bouton(entete, "🗑  " + t("Écarter"), self.ecarter, "danger", petit=True).pack(side="right", padx=(6, 0))
        Bouton(entete, "👁  " + t("Voir la facture"), self.voir_facture, "secondaire", petit=True).pack(side="right")
        Bouton(entete, "✖  " + t("Supprimer"), self.supprimer_facture, "danger", petit=True).pack(side="right",
                                                                                                 padx=(0, 6))
        self.lu = ttk.Label(parent, text="", foreground=TEXTE_DOUX)
        self.lu.pack(fill="x")
        montants = ttk.Frame(parent, padding=(0, 4, 0, 0))
        montants.pack(fill="x")
        for cle, libelle in (("sous_total", "Sous-total"), ("tps", "TPS"), ("tvq", "TVQ"), ("total", "Total")):
            ttk.Label(montants, text=t(libelle)).pack(side="left", padx=(0, 4))
            ttk.Entry(montants, textvariable=self.v[cle], width=11).pack(side="left", padx=(0, 14))
        Bouton(montants, "📤  " + t("Importer cette facture"), self.importer, "principal").pack(side="right", padx=(8, 0))
        Bouton(montants, "💾  " + t("Enregistrer la facture"), self.enregistrer_facture, "accent").pack(side="right")
        self.controle = tk.Label(parent, text="", font=("Segoe UI", 9), anchor="w", justify="left", wraplength=900,
                                 background=fond_de(parent))
        self.controle.pack(fill="x", pady=(4, 0))
        for variable in self.v.values():  # chaque saisie de l'en-tête est enregistrée au fur et à mesure
            variable.trace_add("write", self._planifier_sauvegarde)

        tableau = cadre_tableau(parent)
        tableau.pack(fill="both", expand=True, pady=(4, 0))
        self.lignes = ttk.Treeview(tableau, columns=[c[0] for c in COLONNES_LIGNES], show="headings", height=4,
                                   selectmode="browse")
        for cle, titre_col, largeur in COLONNES_LIGNES:
            self.lignes.heading(cle, text=t(titre_col))
            self.lignes.column(cle, width=largeur, anchor="e" if cle in ("quantite", "prix", "montant", "facteur",
                                                                        "qte_sage") else "w",
                               stretch=cle in ("description", "description_sage"))
        self.lignes.tag_configure("a_faire", background="#fff4d6")
        self.lignes.tag_configure("ok", foreground="#1f2d24")
        defil = ttk.Scrollbar(tableau, orient="vertical", command=self.lignes.yview)
        self.lignes.configure(yscrollcommand=defil.set)
        defil.pack(side="right", fill="y")  # avant le tableau : toujours visible, même s'il est large
        self.lignes.pack(side="left", fill="both", expand=True)
        self.lignes.bind("<<TreeviewSelect>>", lambda _e: self.choisir_ligne())
        rendre_exportable(self.lignes, t("Lignes de la facture"))
        self.lignes.bind("<Double-Button-1>", lambda _e: self.chercher_article())

        # Carte d'édition de la ligne choisie : valeurs lues (à corriger), conditionnement, article Sage
        edition = tk.Frame(parent, background=CARTE, highlightthickness=1, highlightbackground="#e2e8e4")
        edition.pack(fill="x", pady=(6, 0))
        self.l = {cle: tk.StringVar() for cle in ("code", "description", "quantite", "prix", "montant", "facteur",
                                                  "qte_sage", "recherche")}
        self.l_taxe = tk.StringVar(value=t("Aucune"))  # taxes de la ligne : aucune, TPS + TVQ, une seule (taxes.py)

        def etiquette(cadre, texte):
            tk.Label(cadre, text=t(texte), background=CARTE, font=("Segoe UI", 9)).pack(side="left", padx=(0, 4))

        rang1 = tk.Frame(edition, background=CARTE)
        rang1.pack(fill="x", padx=12, pady=(8, 2))
        self.champs_ligne = {}
        etiquette(rang1, "Code")
        self.champs_ligne["code"] = ttk.Entry(rang1, textvariable=self.l["code"], width=10)
        self.champs_ligne["code"].pack(side="left", padx=(0, 10))
        etiquette(rang1, "Désignation")
        self.champs_ligne["description"] = ttk.Entry(rang1, textvariable=self.l["description"])
        self.champs_ligne["description"].pack(side="left", fill="x", expand=True, padx=(0, 10))
        from . import taxes as tx

        etiquette(rang1, "Taxes")
        ttk.Combobox(rang1, textvariable=self.l_taxe, values=[t(v) for v in tx.CHOIX.values()], state="readonly",
                     width=14).pack(side="left")

        rang2 = tk.Frame(edition, background=CARTE)
        rang2.pack(fill="x", padx=12, pady=2)
        for cle, libelle, largeur in (("quantite", "Qté", 7), ("prix", "Prix fournisseur", 9), ("montant", "Montant", 10),
                                      ("qte_sage", "Qté Sage", 9), ("facteur", "Facteur", 7)):
            etiquette(rang2, libelle)
            if cle in ("montant", "qte_sage"):  # valeurs calculées : affichées sur fond gris, non saisissables
                tk.Label(rang2, textvariable=self.l[cle], width=largeur, anchor="e", background="#e9eeea",
                         foreground="#24332a", font=("Segoe UI Semibold", 10), padx=6, pady=4).pack(side="left",
                                                                                                  padx=(0, 10))
            else:
                self.champs_ligne[cle] = ttk.Entry(rang2, textvariable=self.l[cle], width=largeur)
                self.champs_ligne[cle].pack(side="left", padx=(0, 10))
        # Entrée dans un champ de la ligne : appliquer, puis ouvrir aussitôt une nouvelle ligne
        for champ in self.champs_ligne.values():
            champ.bind("<Return>", lambda _e: self.appliquer_et_suivante())
        for cle in ("quantite", "prix", "facteur"):
            self.l[cle].trace_add("write", lambda *_: self._recalculer())
        for cle in ("code", "description", "quantite", "prix", "facteur"):
            self.l[cle].trace_add("write", self._planifier_sauvegarde)
        self.l_taxe.trace_add("write", self._planifier_sauvegarde)
        Bouton(rang2, t("Appliquer"), self.appliquer_ligne, "secondaire", fond=CARTE, petit=True).pack(side="left")
        Bouton(rang2, "➕", self.ajouter_ligne, "secondaire", fond=CARTE, petit=True, largeur=34).pack(side="left", padx=4)
        Bouton(rang2, "🗑", self.supprimer_ligne, "danger", fond=CARTE, petit=True, largeur=34).pack(side="left")

        rang3 = tk.Frame(edition, background=CARTE)
        rang3.pack(fill="x", padx=12, pady=(4, 8))
        gauche = tk.Frame(rang3, background=CARTE)
        gauche.pack(side="left", fill="x", expand=True)
        recherche_cadre = tk.Frame(gauche, background=CARTE)
        recherche_cadre.pack(fill="x")
        etiquette(recherche_cadre, "Article Sage :")
        recherche = self.champ_recherche = ttk.Entry(recherche_cadre, textvariable=self.l["recherche"])
        recherche.pack(side="left", fill="x", expand=True)
        recherche.bind("<KeyRelease>", apres_frappe(recherche, self.chercher_sage))
        recherche.bind("<Return>", lambda _e: self.relier())
        recherche.bind("<Down>", lambda _e: (self.resultats.focus_set(), self.resultats.selection_set(0)))
        self.resultats = tk.Listbox(gauche, height=3, font=("Consolas", 9), activestyle="none")
        self.resultats.pack(fill="x", pady=(4, 0))
        self.resultats.bind("<Double-Button-1>", lambda _e: self.relier())
        self.resultats.bind("<Return>", lambda _e: self.relier())
        boutons = tk.Frame(rang3, background=CARTE)
        boutons.pack(side="left", anchor="n", padx=(10, 0))
        Bouton(boutons, "✔  " + t("Relier et confirmer"), self.relier, fond=CARTE, largeur=190).pack()
        Bouton(boutons, t("Confirmer la proposition"), self.confirmer_proposition, "secondaire", fond=CARTE,
               largeur=190).pack(pady=4)
        Bouton(boutons, "🆕  " + t("Créer l'article"), self.creer_article, "secondaire", fond=CARTE,
               largeur=190).pack()
        self.qte_sage = tk.Label(boutons, text="", background=CARTE, foreground=VERT_FONCE, font=("Segoe UI", 9),
                                 wraplength=190, justify="left")
        self.qte_sage.pack(anchor="w")

    # ---------------------------------------------------------------- liste des factures
    def afficher_liste(self) -> None:
        choix = self.filtre.get()
        self.liste.delete(*self.liste.get_children())
        for i, f in sorted(enumerate(self.registre.factures), key=lambda x: (x[1].date_facture or "", x[0]),
                           reverse=True):  # la plus récente en haut
            if choix != t("Toutes") and t(f.etat) != choix:
                continue
            self.liste.insert("", "end", iid=str(i), tags=(f.etat,), values=self._valeurs_liste(f))
        rayer(self.liste)
        self._afficher_resume()

    @staticmethod
    def _valeurs_liste(f) -> tuple:
        return (f.fichier, f.fournisseur_sage or f"({f.fournisseur_lu or '?'})", f.numero, f.date_facture,
                f"{f.total:,.2f}" if f.total is not None else "", t(f.etat))

    def _afficher_resume(self, suite: str = "") -> None:
        compte = {e: sum(1 for f in self.registre.factures if f.etat == e) for e in ETATS}
        self.resume.configure(text=t("{n} facture(s) — à saisir : {s}, à vérifier : {v}, prêtes : {p}, importées : {i}",
                                     n=len(self.registre.factures), s=compte[A_SAISIR], v=compte[A_VERIFIER],
                                     p=compte[PRETE], i=compte[IMPORTEE])
                              + ("" if self.fournisseurs_sage else
                                 t("   •   liste des fournisseurs Sage absente : cliquez sur « Fournisseurs et articles Sage »"))
                              + suite)

    def ajouter_factures(self) -> None:
        """Copie dans le dossier des factures les PDF ou photos choisis n'importe où sur le poste, puis les lit."""
        import shutil
        from tkinter import filedialog

        from .fournisseurs import EXTENSIONS

        motifs = " ".join(f"*{e}" for e in sorted(EXTENSIONS))
        fichiers = filedialog.askopenfilenames(title=t("Factures fournisseurs à ajouter"),
                                               filetypes=[(t("Factures (PDF, photos)"), motifs), (t("Tous les fichiers"), "*.*")])
        if not fichiers:
            return
        self.registre.dossier.mkdir(parents=True, exist_ok=True)
        ignores = []
        for source in map(Path, fichiers):
            if source.suffix.lower() not in EXTENSIONS:
                ignores.append(source.name)
                continue
            if source.resolve().parent == self.registre.dossier.resolve():
                continue  # déjà dans le dossier
            cible = self.registre.dossier / source.name
            numero = 2
            while cible.exists():  # même nom, autre facture : on garde les deux
                cible = self.registre.dossier / f"{source.stem} ({numero}){source.suffix}"
                numero += 1
            shutil.copy2(source, cible)
        if ignores:
            messagebox.showwarning(self.titre, t("Fichiers ignorés (format non accepté) : {f}", f=", ".join(ignores)))
        self.lire_nouvelles()

    def lire_courriel(self) -> None:
        """Copie les factures jointes aux courriels de la boîte configurée (page Courriel), puis les lit."""
        import tomllib

        from .factures_courriel import configuree, recuperer

        config = tomllib.loads((self.racine / "config.toml").read_text(encoding="utf-8")) \
            if (self.racine / "config.toml").exists() else {}
        if not configuree(config):
            messagebox.showinfo(self.titre, t("Configurez d'abord la boîte de courriel (« Administration > Courriel », carte "
                                              "« Avis de paiement »)."))
            return
        self.resume.configure(text=t("Lecture du courriel (pièces jointes des factures)…"))

        def travail():
            try:
                crees = recuperer(self.racine, config)
                self.after(0, lambda: self._fin_courriel(crees))
            except Exception as exc:
                message = str(exc)
                self.after(0, lambda: (self.afficher_liste(),
                                       messagebox.showerror(self.titre, t("Lecture du courriel impossible : {e}",
                                                                          e=message))))

        threading.Thread(target=travail, daemon=True).start()

    def _fin_courriel(self, crees: list) -> None:
        if not crees:
            self.afficher_liste()
            self.resume.configure(text=self.resume.cget("text") + "   •   " + t("aucune nouvelle facture dans le courriel"))
            return
        self.lire_nouvelles()

    def actualiser(self, silencieux: bool = False) -> None:
        """Relit la liste enregistrée et lit les nouvelles factures déposées dans le dossier."""
        if getattr(self, "_lecture_en_cours", False):
            return
        self.sauvegarder_auto()  # la relecture du registre ne doit pas perdre la saisie en cours
        selection = self.liste.selection()
        self.registre.charger()
        self.facture = None
        self.afficher_liste()
        if selection and self.liste.exists(selection[0]):
            self.liste.selection_set(selection[0])
        if self.registre.nouveaux_fichiers():
            self.lire_nouvelles()
        elif not silencieux:
            self.resume.configure(text=self.resume.cget("text") + "   •   " + t("aucune nouvelle facture"))

    def importer(self, toutes: bool = False) -> None:
        """Importe dans Sage la facture ouverte (ou, avec `toutes`, toutes les factures « Prêtes à importer »), Sage
        fermé, puis vérifie chacune."""
        if self.facture:
            self.enregistrer_facture()
        if toutes:
            pretes = [f for f in self.registre.factures if f.etat == PRETE]
            if not pretes:
                messagebox.showinfo(self.titre, t("Aucune facture « Prête à importer ». Reliez tous les articles et "
                                                  "enregistrez la facture pour qu'elle le devienne."))
                return
        elif not self.facture:
            messagebox.showinfo(self.titre, t("Choisissez dans la liste la facture à importer (ou « Importer toutes "
                                              "les factures prêtes »)."))
            return
        elif self.facture.etat != PRETE:
            messagebox.showinfo(self.titre, t("Cette facture n'est pas prête à importer (état : {etat}). Reliez tous "
                                              "ses articles et vérifiez les totaux, puis enregistrez-la.",
                                              etat=t(self.facture.etat)))
            return
        else:
            pretes = [self.facture]
        from .sage_bureau import sage_ouvert
        if sage_ouvert():
            messagebox.showwarning(self.titre, t("Fermez Sage : l'import exige que personne ne soit "
                                                 "dans le fichier d'entreprise."))
            return
        liste = "\n".join(f"  • {f.fournisseur_sage} n° {f.numero} — {f.total:,.2f} $" for f in pretes)
        if not messagebox.askyesno(self.titre, t("Importer {n} facture(s) dans Sage ?\n\n{liste}", n=len(pretes),
                                                 liste=liste)):
            return
        self.resume.configure(text=t("Import dans Sage en cours (contrôles, import, vérification)…"))

        def travail():
            try:
                import tomllib

                from .import_achats import importer_achats

                config = tomllib.loads((self.racine / "config.toml").read_text(encoding="utf-8"))
                resultats = importer_achats(self.racine, config, pretes)
                message = "\n\n".join(f"{fichier} : {texte}" for fichier, texte in resultats.items())
            except Exception as exc:
                message = f"✘ {exc}"
            self.after(0, lambda: self._fin_import(message))

        threading.Thread(target=travail, daemon=True).start()

    def _fin_import(self, message: str) -> None:
        from .fournisseurs import DEJA_DANS_SAGE

        if self.facture is not None and self.facture.etat == DEJA_DANS_SAGE:  # archivée, retirée de la liste
            self.facture = None
        self.registre.enregistrer()
        self.afficher_liste()
        messagebox.showinfo(self.titre, message)

    def ecarter(self) -> None:
        """Retire de la liste une facture à ne pas traiter maintenant (fichier rangé dans « ecartees »)."""
        if not self.facture:
            messagebox.showinfo(self.titre, t("Choisissez d'abord la facture à écarter dans la liste."))
            return
        if not messagebox.askyesno(self.titre, t("Écarter la facture « {f} » ?\n\nElle ne sera plus dans la liste à "
                                                 "traiter. Son fichier est rangé dans le sous-dossier « ecartees » : "
                                                 "remettez-le dans le dossier des factures pour la traiter plus tard.",
                                                 f=self.facture.fichier)):
            return
        self.registre.ecarter(self.facture)
        self.facture = None
        for cle in self.v:
            self.v[cle].set("")
        self.lignes.delete(*self.lignes.get_children())
        self.controle.configure(text="")
        self.lu.configure(text="")
        self.afficher_liste()

    def supprimer_facture(self) -> None:
        """Supprime la facture choisie de la liste (fichier rangé dans « supprimees »)."""
        if not self.facture:
            messagebox.showinfo(self.titre, t("Choisissez d'abord la facture à supprimer dans la liste."))
            return
        if not messagebox.askyesno(self.titre, t("Supprimer la facture « {f} » de la liste ?\n\nSon fichier est rangé "
                                                 "dans le sous-dossier « supprimees » (rien n'est importé ni changé "
                                                 "dans Sage).", f=self.facture.fichier)):
            return
        self.registre.supprimer(self.facture)
        self.facture = None
        for cle in self.v:
            self.v[cle].set("")
        self.lignes.delete(*self.lignes.get_children())
        self.controle.configure(text="")
        self.lu.configure(text="")
        self.afficher_liste()

    def lire_nouvelles(self) -> None:
        nouveaux = self.registre.nouveaux_fichiers()
        if not nouveaux:
            messagebox.showinfo(self.titre, t("Aucune nouvelle facture dans le dossier :\n{d}", d=self.registre.dossier))
            return
        self._lecture_en_cours = True
        self.resume.configure(text=t("Lecture de {n} facture(s) (l'OCR prend quelques secondes par page)…",
                                     n=len(nouveaux)))

        def travail():
            lues = []
            for chemin in nouveaux:
                try:
                    facture = lire_facture(chemin)
                except Exception as exc:
                    from .fournisseurs import Facture, empreinte
                    facture = Facture(chemin.name, empreinte(chemin), etat=A_SAISIR, remarques=[f"lecture impossible : {exc}"])
                completer(facture, self.memoire, self.fournisseurs_sage, self.articles_sage)
                facture.etat = etat_apres_controle(facture, facture.controles(set(self.fournisseurs_sage) or None))
                lues.append(facture)
            self.after(0, lambda: self._fin_lecture(lues))

        threading.Thread(target=travail, daemon=True).start()

    def _fin_lecture(self, lues) -> None:
        self._lecture_en_cours = False
        self.registre.factures.extend(lues)
        self.registre.enregistrer()
        self.afficher_liste()

    def ouvrir_dossier(self) -> None:
        self.registre.dossier.mkdir(parents=True, exist_ok=True)
        os.startfile(self.registre.dossier)

    def mettre_a_jour_sage(self) -> None:
        self.resume.configure(text=t("Lecture des fournisseurs et des articles dans Sage…"))

        def travail():
            try:
                import tomllib

                from .__main__ import lire_sage
                from .articles_sage import ecrire_copie
                from .fournisseurs import ecrire_copie_fournisseurs, fournisseurs_actifs

                from .fournisseurs import PRETE, deja_dans_sage_fichiers

                config = tomllib.loads((self.racine / "config.toml").read_text(encoding="utf-8"))
                pretes = [f for f in self.registre.factures if f.etat == PRETE]
                noms, articles, deja = lire_sage(
                    config, lambda base: (fournisseurs_actifs(base), base.articles(), deja_dans_sage_fichiers(base, pretes)),
                    config.get("sage_import", {}).get("fichier_entreprise"))
                ecrire_copie_fournisseurs(self.racine, noms)
                ecrire_copie(articles, self.racine / "donnees" / "articles_sage.csv")
                self.after(0, lambda: self._fin_sage(noms, articles, deja))
            except Exception as exc:
                message = str(exc)
                self.after(0, lambda: self.resume.configure(text="✘ " + message))

        threading.Thread(target=travail, daemon=True).start()

    def _fin_sage(self, noms, articles, deja: dict | None = None) -> None:
        from .fournisseurs import DEJA_DANS_SAGE, archiver_deja_dans_sage

        archivees = []
        for f in list(self.registre.factures):
            if deja and f.fichier in deja:  # prête à importer mais saisie à la main entre-temps
                archiver_deja_dans_sage(self.racine, f, deja[f.fichier])
                archivees.append(f"{f.fournisseur_sage} n° {f.numero}")
        if archivees:
            if self.facture is not None and self.facture.etat == DEJA_DANS_SAGE:
                self.facture = None
            self.registre.enregistrer()
            messagebox.showinfo(self.titre, t("Déjà dans Sage, archivée(s) et retirée(s) de la liste :\n{liste}",
                                              liste="\n".join(archivees)))
        self.fournisseurs_sage, self.articles_sage = noms, articles
        self.normalises = [normaliser(f"{a.description} {a.numero}") for a in articles]
        self.liste_fournisseurs.configurer_valeurs(noms)
        self.afficher_liste()

    # ---------------------------------------------------------------- facture choisie
    def choisir_facture(self) -> None:
        choix = self.liste.selection()
        if not choix:
            return
        if self.facture is not self.registre.factures[int(choix[0])]:
            self.sauvegarder_auto()  # la facture quittée est gardée telle que saisie
        self.facture = self.registre.factures[int(choix[0])]
        self._ligne_editee = None
        f = self.facture
        valeurs = {"fournisseur": f.fournisseur_sage, "numero": f.numero, "date": f.date_facture,
                   "sous_total": "" if f.sous_total is None else f"{f.sous_total:.2f}", "tps": f"{f.tps:.2f}",
                   "tvq": f"{f.tvq:.2f}", "total": "" if f.total is None else f"{f.total:.2f}"}
        self._chargement = True  # affichage seulement : rien à enregistrer
        for cle, valeur in valeurs.items():
            self.v[cle].set(valeur)
        self._chargement = False
        self.lu.configure(text=t("Lu sur la facture : {f}   •   lecture : {m}", f=f.fournisseur_lu or "?", m=f.modele)
                          + (f"   •   {' ; '.join(f.remarques)}" if f.remarques else ""))
        self.afficher_lignes()
        self.verifier()
        if f.etat == A_SAISIR:
            self.voir_facture()

    def afficher_lignes(self, selection: int | None = None) -> None:
        self.lignes.delete(*self.lignes.get_children())
        if not self.facture:
            return
        for i, l in enumerate(self.facture.lignes):
            self.lignes.insert("", "end", iid=str(i), **self._valeurs_ligne(l))
        rayer(self.lignes)
        if selection is not None and self.lignes.exists(str(selection)):
            self.lignes.selection_set(str(selection))
            self.lignes.see(str(selection))

    @staticmethod
    def _valeurs_ligne(l: Ligne) -> dict:
        quantite, prix_sage = l.en_sage()
        etat = t("Confirmée") if l.confirme else (t("Proposée") if l.numero_sage else t("À relier"))
        if l.nature != "article":
            etat = t("Frais")
        return {"tags": ("ok" if l.confirme or l.nature != "article" else "a_faire",),
                "values": (l.code, l.description, f"{l.quantite:g}", f"{l.prix:.2f}", f"{l.montant:.2f}", l.numero_sage,
                           l.description_sage, f"{quantite:g}", f"{prix_sage:.4f}", f"{l.facteur:g}", etat)}

    def lire_entete(self) -> None:
        f = self.facture
        f.fournisseur_sage = self.v["fournisseur"].get().strip()
        f.numero, f.date_facture = self.v["numero"].get().strip(), self.v["date"].get().strip()
        f.sous_total = decimal(self.v["sous_total"].get()) if self.v["sous_total"].get().strip() else None
        f.tps, f.tvq = decimal(self.v["tps"].get()), decimal(self.v["tvq"].get())
        f.total = decimal(self.v["total"].get()) if self.v["total"].get().strip() else None

    def verifier(self) -> list[str]:
        problemes = self.facture.controles(set(self.fournisseurs_sage) or None) if self.facture else []
        if problemes:
            self.controle.configure(text="⚠ " + " ; ".join(problemes[:6]) + (" …" if len(problemes) > 6 else ""),
                                    foreground=ROUGE)
        else:
            self.controle.configure(text="✔ " + t("Facture cohérente et entièrement reliée : prête à importer."),
                                    foreground=VERT_FONCE)
        return problemes

    def voir_facture(self) -> None:
        if self.facture:
            chemin = self.registre.chemin_fichier(self.facture)
            if chemin.exists():
                os.startfile(chemin)

    def enregistrer_facture(self) -> None:
        if not self.facture:
            return
        try:
            self.lire_entete()
        except ValueError as exc:
            messagebox.showerror(self.titre, str(exc))
            return
        if self.facture.fournisseur_sage and self.fournisseurs_sage \
                and self.facture.fournisseur_sage not in self.fournisseurs_sage:
            messagebox.showwarning(self.titre, t("Choisissez le fournisseur dans la liste des fournisseurs Sage."))
        if self.facture.fournisseur_sage and self.facture.fournisseur_lu:
            self.memoire.retenir_fournisseur(self.facture.fournisseur_lu, self.facture.fournisseur_sage)
        for l in self.facture.lignes:
            if l.confirme and l.numero_sage and self.facture.fournisseur_sage:
                self.memoire.retenir_article(self.facture.fournisseur_sage, l)
        self.facture.etat = etat_apres_controle(self.facture, self.verifier())
        self.memoire.enregistrer()
        self.registre.enregistrer()
        index = self.registre.factures.index(self.facture)
        self.afficher_liste()
        if self.liste.exists(str(index)):
            self.liste.selection_set(str(index))

    # ---------------------------------------------------------------- enregistrement automatique
    def _planifier_sauvegarde(self, *_) -> None:
        """Une saisie vient d'être faite : enregistrement peu après la dernière frappe."""
        if self._chargement or not self.facture:
            return
        if self._minuterie:
            self.after_cancel(self._minuterie)
        self._minuterie = self.after(700, self.sauvegarder_auto)

    def _appliquer_silencieux(self) -> None:
        """Reporte sur la ligne affichée les valeurs de la carte d'édition (sans message : une valeur en cours de
        frappe, par exemple « 12, », attend la frappe suivante)."""
        i = self._ligne_editee
        if i is None or not self.facture or i >= len(self.facture.lignes):
            return
        l = self.facture.lignes[i]
        try:
            quantite, prix = decimal(self.l["quantite"].get()), decimal(self.l["prix"].get())
            facteur = decimal(self.l["facteur"].get() or "1")
        except (ValueError, tk.TclError):
            return
        if facteur <= 0:
            return
        l.code, l.description = self.l["code"].get().strip(), self.l["description"].get().strip()
        l.quantite, l.prix, l.facteur = quantite, prix, facteur
        l.montant = (quantite * prix).quantize(Decimal("0.01"))
        self._taxe_vers_ligne(l)
        if self.lignes.exists(str(i)):
            self.lignes.item(str(i), **self._valeurs_ligne(l))
            rayer(self.lignes)
        self.montrer_conversion(l)

    def sauvegarder_auto(self) -> None:
        """Enregistre sans question la facture ouverte : chaque saisie est gardée au fur et à mesure (demande du
        propriétaire du 2026-10-28)."""
        if self._minuterie:
            self.after_cancel(self._minuterie)
            self._minuterie = None
        f = self.facture
        if f is None or f not in self.registre.factures:
            return
        try:
            self._appliquer_silencieux()
            try:
                self.lire_entete()
            except ValueError:
                pass  # montant en cours de frappe : le reste est gardé
            if f.fournisseur_sage and f.fournisseur_lu and (not self.fournisseurs_sage
                                                            or f.fournisseur_sage in self.fournisseurs_sage):
                self.memoire.retenir_fournisseur(f.fournisseur_lu, f.fournisseur_sage)
            for l in f.lignes:
                if l.confirme and l.numero_sage and f.fournisseur_sage:
                    self.memoire.retenir_article(f.fournisseur_sage, l)
            f.etat = etat_apres_controle(f, self.verifier())
            self.memoire.enregistrer()
            self.registre.enregistrer()
        except tk.TclError:
            return  # page en cours de fermeture
        index = str(self.registre.factures.index(f))
        if self.liste.exists(index):
            self.liste.item(index, values=self._valeurs_liste(f), tags=(f.etat,))
            rayer(self.liste)
        self._afficher_resume("   •   " + t("enregistré automatiquement à {h}",
                                            h=datetime.now().strftime("%H:%M:%S")))

    # ---------------------------------------------------------------- lignes
    def ligne_choisie(self) -> tuple[int, Ligne] | tuple[None, None]:
        choix = self.lignes.selection()
        if not choix or not self.facture:
            return None, None
        i = int(choix[0])
        return i, self.facture.lignes[i]

    def _recalculer(self) -> None:
        """Montant = Qté × Prix fournisseur ; Qté Sage = Qté × Facteur (affichage immédiat, pendant la frappe)."""
        if self._chargement:
            return
        try:
            quantite, prix = decimal(self.l["quantite"].get()), decimal(self.l["prix"].get())
            facteur = decimal(self.l["facteur"].get() or "1")
        except ValueError:
            return
        self.l["montant"].set(f"{(quantite * prix).quantize(Decimal('0.01'))}")
        self.l["qte_sage"].set(f"{(quantite * facteur).quantize(Decimal('0.001')):g}")

    def choisir_ligne(self) -> None:
        i, l = self.ligne_choisie()
        if not l:
            return
        if self._ligne_editee is not None and self._ligne_editee != i:
            self.sauvegarder_auto()  # la ligne quittée garde ce qui a été tapé
        self._ligne_editee = i
        self._chargement = True  # les valeurs de la ligne s'affichent telles quelles
        for cle, valeur in (("code", l.code), ("description", l.description), ("quantite", f"{l.quantite:g}"),
                            ("prix", f"{l.prix}"), ("montant", f"{l.montant}"), ("facteur", f"{l.facteur:g}"),
                            ("qte_sage", f"{l.en_sage()[0]:g}")):
            self.l[cle].set(valeur)
        self.l_taxe.set(t(__import__("mvogmbi_sync.taxes", fromlist=["x"]).libelle(
            __import__("mvogmbi_sync.taxes", fromlist=["x"]).code(l))))
        self._chargement = False
        self.l["recherche"].set(l.description)
        self.chercher_sage()
        self.montrer_conversion(l)

    def _taxe_vers_ligne(self, l: Ligne) -> None:
        from . import taxes as tx

        l.taxe = tx.code_du_libelle(self.l_taxe.get(), t)
        l.taxable = bool(l.taxe)

    def montrer_conversion(self, l: Ligne) -> None:
        quantite, prix = l.en_sage()
        self.qte_sage.configure(text=t("Dans Sage : {q} × {p} $ = {m} $ (prix Sage = montant / quantité Sage)",
                                       q=f"{quantite:g}", p=f"{prix:.4f}", m=f"{l.montant:.2f}"))

    def appliquer_ligne(self) -> None:
        i, l = self.ligne_choisie()
        if l is None:
            return
        try:
            l.code, l.description = self.l["code"].get().strip(), self.l["description"].get().strip()
            l.quantite, l.prix = decimal(self.l["quantite"].get()), decimal(self.l["prix"].get())
            # Montant = Qté × Prix fournisseur ; Qté Sage = Qté × Facteur (calculées, non saisissables)
            l.montant = (l.quantite * l.prix).quantize(Decimal("0.01"))
            l.facteur = decimal(self.l["facteur"].get() or "1")
            if l.facteur <= 0:
                raise ValueError(t("Le facteur doit être supérieur à 0."))
        except ValueError as exc:
            messagebox.showerror(self.titre, str(exc))
            return False
        self._taxe_vers_ligne(l)
        self.l["facteur"].set(f"{l.facteur:g}")
        self.l["qte_sage"].set(f"{l.en_sage()[0]:g}")
        self.afficher_lignes(i)
        self.montrer_conversion(l)
        self.sauvegarder_auto()

    def appliquer_et_suivante(self) -> str:
        """Entrée : applique la ligne, puis passe à la ligne suivante ; après la dernière, ouvre une nouvelle ligne."""
        i, _ = self.ligne_choisie()
        if i is None or self.appliquer_ligne() is False:
            return "break"
        if i + 1 < len(self.facture.lignes):
            self.lignes.selection_set(str(i + 1))
            self.lignes.see(str(i + 1))
            self.choisir_ligne()
            self.champs_ligne["quantite"].focus_set()
            self.champs_ligne["quantite"].select_range(0, "end")
        else:
            self.ajouter_ligne()
        return "break"

    def ajouter_ligne(self) -> None:
        if not self.facture:
            return
        self.facture.lignes.append(Ligne("", Decimal(1), Decimal(0), Decimal(0)))
        if self.facture.etat == A_SAISIR:
            self.facture.etat = A_VERIFIER
        self.afficher_lignes(len(self.facture.lignes) - 1)
        self.choisir_ligne()
        self.sauvegarder_auto()
        self.chercher_article()

    def chercher_article(self) -> None:
        """Place le curseur dans la recherche « Article Sage » (taper quelques lettres, puis Entrée ou double-clic)."""
        _, l = self.ligne_choisie()
        if l is not None and not l.description:
            self.l["recherche"].set("")
            self.resultats.delete(0, "end")
        self.champ_recherche.focus_set()
        self.champ_recherche.select_range(0, "end")

    def supprimer_ligne(self) -> None:
        i, l = self.ligne_choisie()
        if l is not None and messagebox.askyesno(self.titre, t("Supprimer la ligne « {d} » ?", d=l.description)):
            self._ligne_editee = None
            del self.facture.lignes[i]
            self.afficher_lignes()
            self.sauvegarder_auto()

    def chercher_sage(self) -> None:
        self.resultats.delete(0, "end")
        self.choix_sage = []
        texte = normaliser(self.l["recherche"].get())
        if not texte or not self.articles_sage:
            return
        _, l = self.ligne_choisie()
        for _, _, i in process.extract(texte, self.normalises, scorer=fuzz.token_set_ratio, limit=12):
            a = self.articles_sage[i]
            alerte = t("  (autre format)") if l and conflit_format(l.description, a.description) else ""
            self.choix_sage.append(a)
            self.resultats.insert("end", f"{a.numero:<16} {a.description}{alerte}")

    def relier(self) -> None:
        i, l = self.ligne_choisie()
        choix = self.resultats.curselection() or ((0,) if self.choix_sage else ())
        if l is None or not choix:
            messagebox.showinfo(self.titre, t("Choisissez une ligne de la facture, puis un article Sage dans la liste."))
            return
        a = self.choix_sage[choix[0]]
        if not self.l["description"].get().strip():  # ligne ajoutée à la main : désignation de l'article Sage
            self.l["description"].set(a.description)
        if conflit_format(l.description, a.description) and not messagebox.askyesno(
                self.titre, t("Les formats semblent différents (« {f} » / « {s} »). Deux formats différents sont deux "
                              "articles différents. Relier quand même (conditionnement différent) ?",
                              f=l.description, s=a.description)):
            return
        self.appliquer_ligne()
        l.numero_sage, l.description_sage, l.confirme = a.numero, a.description, True
        self.afficher_lignes(i)
        self.montrer_conversion(l)
        self.sauvegarder_auto()
        self.champs_ligne["quantite"].focus_set()  # au clavier : Qté, Tab, Prix, Tab, Facteur, Entrée
        self.champs_ligne["quantite"].select_range(0, "end")

    def creer_article(self) -> None:
        """Article absent de Sage et de Clover : création dans les deux (prix d'achat = prix Sage de la ligne,
        stock Clover 0 : l'import de la facture ajoutera la quantité), puis la ligne est reliée."""
        from .fenetre_article import FenetreCreationArticle

        i, l = self.ligne_choisie()
        if l is None:
            messagebox.showinfo(self.titre, t("Choisissez d'abord la ligne de la facture."))
            return
        self.appliquer_ligne()

        def cree(a) -> None:
            from .articles_sage import ArticleSage
            if a.numero_sage:
                self.articles_sage.append(ArticleSage(a.numero_sage, a.description_sage, "Stock",
                                                      a.comptes.produits if a.comptes else ""))
                self.normalises.append(normaliser(f"{a.description_sage} {a.numero_sage}"))
                if self.facture and i < len(self.facture.lignes) and self.facture.lignes[i] is l:
                    l.numero_sage, l.description_sage, l.confirme = a.numero_sage, a.description_sage, True
                    self.afficher_lignes(i)
                    self.sauvegarder_auto()

        FenetreCreationArticle(self, self.racine, nom=l.description, cout=l.en_sage()[1],
                               numeros_sage=[a.numero for a in self.articles_sage], au_succes=cree)

    def confirmer_proposition(self) -> None:
        i, l = self.ligne_choisie()
        if l is None or not l.numero_sage:
            return
        self.appliquer_ligne()
        l.confirme = True
        self.afficher_lignes(i)
        self.sauvegarder_auto()
