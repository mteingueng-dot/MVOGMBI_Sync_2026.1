"""Interface graphique d'installation et de suivi de MVOGMBI_Sync (tkinter, incluse avec Python).

Pages : Accueil (mise en route), Clover, Sage, Courriel, Automatisation, Correspondance des articles,
Tableau de bord, Encaissements, Guide de configuration, Aide / FAQ.
Langues : français et anglais (sélecteur dans le menu, enregistré dans config.toml [general] langue).
Les secrets (jeton Clover, mots de passe) vont dans le coffre-fort de Windows, jamais dans config.toml.
"""

from __future__ import annotations

import json
import os
import queue
import re
import subprocess
import sys
import threading
import time
import tkinter as tk
import tomllib
from datetime import date, timedelta
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from . import coffre, entreprise, export_tableau, langues
from .design import (BORDURE, CARTE, FOND, ICONE, ID_APPLICATION, JAUNE, LOGO, MENU_ACTIF, MENU_FOND, MENU_SURVOL, ROUGE, TEXTE,
                     TEXTE_DOUX, VERT, VERT_FONCE, Bouton, ChampDate, fond_de, image_filigrane, styler)
from .design import action_permise
from .langues import t

TITRE = "MVOGMBI_Sync — Clover → Sage 50"
MASQUE = "••••••••"  # affiché quand un secret est déjà enregistré dans le coffre

# Index des pages (ordre du menu)
(ACCUEIL, CLOVER, SAGE, COURRIEL, AUTOMATISATION, CORRESPONDANCE, TABLEAU, ENCAISSEMENTS, FOURNISSEURS, PAIEMENTS,
 RAPPROCHEMENT, RAPPORTS, GUIDE, FAQ, UTILISATEURS) = range(15)
# menu en groupes (demande du propriétaire du 2026-10-28) : pages (index) ou fenêtres (icône, titre, page dont le
# profil donne l'accès, méthode qui ouvre la fenêtre)
MENU_GROUPES = [
    (None, "", [ACCUEIL]),
    ("Administration", "⚙", [CLOVER, SAGE, COURRIEL, AUTOMATISATION,
                             ("💾", "Sauvegarde des données", AUTOMATISATION, "ouvrir_sauvegarde"),
                             ("🧭", "Journal des opérations", UTILISATEURS, "ouvrir_journal_operations"),
                             ("📱", "Tableau du gérant (téléphone)", AUTOMATISATION, "ouvrir_tableau"), UTILISATEURS]),
    # rubriques Articles, Vente et Fournisseur rangées comme les menus de gestion de Sage (demande du propriétaire
    # du 2026-10-29 ; noms des rubriques gardés)
    ("Articles", "🏷", [("📚", "Liste des articles", CORRESPONDANCE, "ouvrir_liste", "articles"),
                       ("📄", "Articles Clover", CORRESPONDANCE, "ouvrir_articles_clover"),
                       ("🆕", "Créer un article", CORRESPONDANCE, "ouvrir_creation_article"),
                       ("🗂", "Liste des documents de stock", CORRESPONDANCE, "ouvrir_liste", "documents_stock"),
                       ("✏", "Saisir un document de stock", CORRESPONDANCE, "ouvrir_documents", "stock"),
                       ("🔁", "Transferts entre magasins", CORRESPONDANCE, "ouvrir_transferts"),
                       ("🗑", "Pertes et démarque", CORRESPONDANCE, "ouvrir_pertes"),
                       ("🏷", "Étiquettes de prix", CORRESPONDANCE, "ouvrir_etiquettes"),
                       ("🏷", "Promotions", CORRESPONDANCE, "ouvrir_promotions"),
                       ("🔄", "Inventaire tournant", CORRESPONDANCE, "ouvrir_inventaire_tournant"),
                       ("🔎", "Interrogation de compte article", RAPPORTS, "ouvrir_interrogation", "Article"),
                       ("📋", "Inventaire Clover et Sage", CORRESPONDANCE, "ouvrir_inventaire"),
                       ("📒", "Livre d'inventaire", CORRESPONDANCE, "ouvrir_liste", "livre"),
                       CORRESPONDANCE,
                       ("💲", "Coûts Clover depuis Sage", CORRESPONDANCE, "ouvrir_couts_clover"),
                       ("💹", "Prix et marges", CORRESPONDANCE, "ouvrir_prix_marges")]),
    ("Vente", "🛒", [("👥", "Liste des clients", ENCAISSEMENTS, "ouvrir_liste", "clients"),
                    ("🗂", "Liste des documents de vente", ENCAISSEMENTS, "ouvrir_liste", "documents_vente"),
                    ("✏", "Saisir une facture de vente", ENCAISSEMENTS, "ouvrir_documents", "facture"),
                    ("📝", "Commandes clients", ENCAISSEMENTS, "ouvrir_documents", "commande"),
                    ("📨", "Clients professionnels et relances", RAPPROCHEMENT, "ouvrir_relances"),
                    ("🔎", "Interrogation de compte client", RAPPORTS, "ouvrir_interrogation", "Client"),
                    TABLEAU]),
    ("Fournisseur", "🚚", [("🏭", "Liste des fournisseurs", FOURNISSEURS, "ouvrir_liste", "fournisseurs"),
                          ("🗂", "Liste des documents d'achat", FOURNISSEURS, "ouvrir_liste", "documents_achat"),
                          FOURNISSEURS,
                          ("✏", "Saisir une facture d'achat", FOURNISSEURS, "ouvrir_saisie_achat"),
                          # bons de commande : liste, saisie, proposition et réception réunies (2026-10-29)
                          ("🛍", "Bons de commande", FOURNISSEURS, "ouvrir_receptions"),
                          ("🔎", "Interrogation de compte fournisseur", RAPPORTS, "ouvrir_interrogation",
                           "Fournisseur"),
                          ("↩", "Retours fournisseurs", FOURNISSEURS, "ouvrir_retours"),
                          ("🗄", "Factures fournisseurs archivées", RAPPORTS, "ouvrir_rapports",
                           "Factures fournisseurs archivées")]),
    ("Comptabilité", "🏦", [("💵", "Contrôle de la caisse", PAIEMENTS, "ouvrir_caisse"),
                        ("🧾", "Petite caisse et dépenses", PAIEMENTS, "ouvrir_depenses"),
                        ENCAISSEMENTS, PAIEMENTS, RAPPROCHEMENT,
                           ("🧾", "Comptes Sage par catégorie", CORRESPONDANCE, "ouvrir_comptes_sage"),
                           ("⏳", "Âge des comptes", RAPPROCHEMENT, "ouvrir_comptabilite", "Âge des comptes"),
                           ("🧮", "Déclaration TPS/TVQ", RAPPROCHEMENT, "ouvrir_comptabilite", "Déclaration TPS/TVQ"),
                           ("💧", "Prévision de trésorerie", RAPPROCHEMENT, "ouvrir_comptabilite",
                            "Prévision de trésorerie"),
                           ("📐", "Budget et écarts", RAPPROCHEMENT, "ouvrir_comptabilite", "Budget et écarts"),
                           ("📅", "Clôture du mois", RAPPROCHEMENT, "ouvrir_comptabilite", "Clôture du mois")]),
    # paie (demande du propriétaire du 2026-10-29) : pointage pour tous ; feuilles de temps et NIP pour qui voit
    # les paiements fournisseurs (administrateur, comptable)
    ("Paie", "🕑", [("⏱", "Pointage des employés", ACCUEIL, "ouvrir_pointage"),
                   ("🗓", "Feuilles de temps", PAIEMENTS, "ouvrir_feuilles_temps"),
                   ("📅", "Planning mensuel", PAIEMENTS, "ouvrir_planning"),
                   ("🗓", "Mon horaire", ACCUEIL, "ouvrir_mon_horaire"),
                   ("👥", "Employés et NIP", PAIEMENTS, "ouvrir_employes_paie"),
                   ("🏖", "Jours fériés et congés", PAIEMENTS, "ouvrir_conges"),
                   ("💵", "Traitement de la paie", RAPPROCHEMENT, "ouvrir_traitement_paie"),
                   ("🚪", "Fin d'emploi et relevé d'emploi", PAIEMENTS, "ouvrir_fin_emploi"),
                   ("👷", "Coût de la main-d'œuvre", RAPPROCHEMENT, "ouvrir_main_oeuvre"),
                   ("🏛", "Retenues à la source", RAPPROCHEMENT, "ouvrir_comptabilite", "Retenues à la source"),
                   ("📬", "Suivi des remises", RAPPROCHEMENT, "ouvrir_comptabilite", "Suivi des remises")]),
    ("État", "📊", [("📈", "Suivi des ventes", RAPPORTS, "ouvrir_rapports", "Suivi des ventes"),
                    ("🔎", "Recherche dans l'historique", RAPPORTS, "ouvrir_rapports", "Recherche dans l'historique"),
                    ("📊", "Statistiques Clover", RAPPORTS, "ouvrir_rapports", "Statistiques Clover"),
                    ("💤", "Produits inactifs", RAPPORTS, "ouvrir_rapports", "Produits inactifs"),
                    ("🥇", "Articles 20/80", RAPPORTS, "ouvrir_rapports", "Articles 20/80")]),
    (None, "", [GUIDE, FAQ]),  # aide : hors des rubriques, en bas du menu (demande du propriétaire)
]
# libellés du menu (sans n° de page) ; la page « Tableau de bord » est la facturation des ventes Clover
LIBELLES_MENU = {TABLEAU: "Ventes Clover → factures Sage"}
TITRES_ONGLETS_RAPPORTS = ("Suivi des ventes", "Recherche dans l'historique", "Statistiques Clover",
                           "Produits inactifs", "Articles 20/80", "Factures fournisseurs archivées")
# pages ouvertes seulement par des entrées de fenêtre ou d'onglet : leur groupe
GROUPE_DES_PAGES_SANS_LIGNE = {RAPPORTS: "État"}


# --------------------------------------------------------------------------------------------- configuration
def lire_config(chemin: Path) -> dict:
    return tomllib.loads(chemin.read_text(encoding="utf-8")) if chemin.exists() else {}


def _valeur_toml(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    texte = str(v)
    if "'" not in texte and "\n" not in texte:
        return f"'{texte}'"  # chaîne littérale : les « \\ » des chemins Windows restent tels quels
    return '"' + texte.replace("\\", "\\\\").replace('"', '\\"') + '"'


def ecrire_config(chemin: Path, config: dict) -> None:
    lignes = ["# Configuration de MVOGMBI_Sync (modifiée par l'application de configuration).",
              "# Les secrets sont dans le coffre-fort de Windows, pas dans ce fichier.", ""]
    tableaux = {s: v for s, v in config.items() if isinstance(v, list)}  # [[points_vente]] : à la fin
    for section, valeurs in config.items():
        if section in tableaux:
            continue
        lignes.append(f"[{section}]")
        for cle, valeur in valeurs.items():
            lignes.append(f"{cle} = {_valeur_toml(valeur)}")
        lignes.append("")
    for section, elements in tableaux.items():
        for valeurs in elements:
            lignes.append(f"[[{section}]]")
            for cle, valeur in valeurs.items():
                lignes.append(f"{cle} = {_valeur_toml(valeur)}")
            lignes.append("")
    chemin.write_text("\n".join(lignes), encoding="utf-8")


# --------------------------------------------------------------------------------------------- application
class Application(tk.Tk):
    def __init__(self, racine: Path, session=None):
        """`session` : utilisateur connecté (pages selon son profil) ; None = toutes les pages (outils, captures)."""
        super().__init__()
        self.racine = racine
        self.relancer = False
        self.deconnecter = False
        self.session = session
        if session is not None:
            from .utilisateurs import Registre

            self._permises = Registre(racine).pages(session)
            self.points_permis = Registre(racine).points_vente_permis(session)
            export_tableau.EXPORT_PERMIS = Registre(racine).peut_exporter(session)
            self._refusees = Registre(racine).refusees(session)
            self._fonctions = Registre(racine).permises(session)  # accès par fonction (None = par pages)
        else:
            self._refusees = set()
            self._fonctions = None
            self._permises = None
            self.points_permis = None  # None = tous les points de vente
        from .__main__ import OUVERTURE_SAGE

        OUVERTURE_SAGE["permise"] = False  # pas d'ouverture de Sage avant une action de la personne

        def _action_de_la_personne(_e=None):
            OUVERTURE_SAGE["permise"] = True

        self.bind_all("<ButtonPress>", _action_de_la_personne, add="+")
        self.bind_all("<KeyPress>", _action_de_la_personne, add="+")
        export_tableau.RACINE_ENTETE = Path(racine)  # en-tête des impressions : informations Clover de l'entreprise
        threading.Thread(target=lambda: entreprise.actualiser(Path(racine)), daemon=True).start()  # 1 fois/jour
        # listes principales lues d'avance si Sage répond déjà (jamais d'ouverture de Sage pour cela)
        # lancé 3 s après l'affichage : il ne ralentit plus la construction de la fenêtre (GIL partagé)
        self.after(3000, lambda: threading.Thread(target=lambda: __import__(
            "mvogmbi_sync.cache_lectures", fromlist=["x"]).precharger(Path(racine)), daemon=True).start())
        self.chemin_config = racine / "config.toml"
        self.config_toml = lire_config(self.chemin_config)
        langues.depuis_config(self.config_toml)
        self.file_messages: queue.Queue = queue.Queue()
        self.title(TITRE)
        largeur = min(1320, self.winfo_screenwidth() - 60)
        hauteur = min(980, self.winfo_screenheight() - 90)  # la fenêtre reste au-dessus de la barre des tâches
        self.geometry(f"{largeur}x{hauteur}+{max(0, (self.winfo_screenwidth() - largeur) // 2)}+20")
        self.minsize(920, 620)
        self.configure(background=FOND)
        try:  # thème moderne « Sun Valley » (style Windows 11)
            import sv_ttk
            sv_ttk.set_theme("light")
        except Exception:
            pass
        self._styles()
        self._images = self._charger_images()
        if ICONE.exists():  # icône .ico multi-tailles : nette dans la barre des tâches
            self.iconbitmap(default=str(ICONE))
        elif self._images:
            self.iconphoto(True, self._images["icone"])
        self._tache_installee = False

        self._bandeau()
        corps = tk.Frame(self, background=FOND)
        corps.pack(fill="both", expand=True)
        self.menu = tk.Frame(corps, background=MENU_FOND, width=262)
        self.menu.pack(side="left", fill="y")
        self.menu.pack_propagate(False)
        contenu = ttk.Frame(corps, padding=(20, 14, 20, 10))
        contenu.pack(side="left", fill="both", expand=True)

        bas = ttk.Frame(contenu, padding=(0, 10, 0, 0))
        bas.pack(side="bottom", fill="x")
        if any(self.permis(i) for i in (CLOVER, SAGE, COURRIEL, AUTOMATISATION)):
            Bouton(bas, "💾  " + t("Enregistrer la configuration"),
                   lambda: action_permise(self, "Enregistrer la configuration") and self.enregistrer()).pack(side="right")
        self.etat = ttk.Label(bas, text="", foreground=TEXTE_DOUX)
        self.etat.pack(side="left")
        self.onglets = ttk.Notebook(contenu, style="Pages.TNotebook")
        self.onglets.pack(fill="both", expand=True)
        # outils (listes, fenêtres de travail) affichés dans la fenêtre principale, pas dans une fenêtre à part
        # (demande du propriétaire du 2026-10-29) ; seules les créations ouvrent une nouvelle fenêtre
        self.zone_outil = ttk.Frame(contenu)
        self._pile_outils: list = []
        self.vars: dict[str, tk.Variable] = {}
        self._pages: list[tuple[str, str]] = []
        self._onglet_accueil()
        self._onglet_clover()
        self._onglet_sage()
        self._onglet_courriel()
        self._onglet_automatisation()
        self._onglet_correspondance()
        self._onglet_tableau()
        self._onglet_encaissements()
        self._onglet_fournisseurs()
        self._onglet_paiements()
        self._onglet_rapprochement()
        self._onglet_rapports()
        self._onglet_texte(t("Guide de configuration"), "guide", "📘")
        self._onglet_texte(t("Aide / FAQ"), "faq", "❓")
        if self.permis(UTILISATEURS):
            self._onglet_utilisateurs()
        self._construire_menu()

        self._attente = self.after(200, self._relayer_messages)
        self.actualiser_tableau()
        self.aller(ACCUEIL)
        self._preparer_verrou()

    def permis(self, index: int) -> bool:
        """Page visible pour l'utilisateur connecté (profil)."""
        from .utilisateurs import PAGES, UTILISATEURS as CLE_UTILISATEURS

        if self._permises is None:
            return True
        return (PAGES[index] if index < len(PAGES) else CLE_UTILISATEURS) in self._permises

    def au_menu(self, index: int) -> bool:
        """Ligne de page affichée au menu. Accès par fonction : la page elle-même doit être cochée (une page ouverte
        seulement pour une fenêtre permise reste hors du menu)."""
        from .utilisateurs import PAGES, UTILISATEURS as CLE_UTILISATEURS

        fonctions = getattr(self, "_fonctions", None)
        if fonctions is None:
            return self.permis(index)
        return index == ACCUEIL or (PAGES[index] if index < len(PAGES) else CLE_UTILISATEURS) in fonctions

    # ---------------------------------------------------------------- apparence
    def _styles(self) -> None:
        style = ttk.Style(self)
        style.layout("Pages.TNotebook.Tab", [])  # onglets masqués : navigation par le menu latéral
        style.configure("Pages.TNotebook", borderwidth=0, padding=0)
        style.configure("Aide.TLabel", foreground=TEXTE_DOUX)
        style.configure("Carte.TFrame", background=CARTE)
        style.configure("Carte.TLabel", background=CARTE, foreground=TEXTE)
        style.configure("CarteAide.TLabel", background=CARTE, foreground=TEXTE_DOUX, font=("Segoe UI", 9))
        style.configure("Carte.TCheckbutton", background=CARTE)
        styler(style)

    def _charger_images(self) -> dict:
        """Logo (en-tête), icône de la fenêtre et filigranes ; rien si l'image est introuvable."""
        try:
            from PIL import Image, ImageTk

            logo = Image.open(LOGO).convert("RGBA")
            entete = logo.copy()
            entete.thumbnail((84, 84), Image.LANCZOS)
            largeur, hauteur = logo.size
            icone = logo.crop((0, 0, largeur, int(hauteur * 0.76)))
            icone.thumbnail((64, 64), Image.LANCZOS)
            fond_page = fond_de(ttk.Frame(self))
            return {"entete": ImageTk.PhotoImage(entete), "icone": ImageTk.PhotoImage(icone),
                    "filigrane": image_filigrane(330, fond_page, 0.09),
                    "filigrane_texte": image_filigrane(250, CARTE, 0.11)}
        except Exception:
            return {}

    def _bandeau(self) -> None:
        bandeau = tk.Frame(self, background=VERT)
        bandeau.pack(fill="x")
        if self._images:
            carte = tk.Frame(bandeau, background="white", padx=6, pady=4)
            carte.pack(side="left", padx=(18, 16), pady=12)
            tk.Label(carte, image=self._images["entete"], background="white", borderwidth=0).pack()
        textes = tk.Frame(bandeau, background=VERT)
        textes.pack(side="left", fill="x", expand=True, pady=12)
        tk.Label(textes, text=t("Marché MVOG-MBI Sherbrooke"), font=("Segoe UI Semibold", 20), foreground="white",
                 background=VERT).pack(anchor="w")
        tk.Label(textes, text=t("Synchronisation des ventes Clover → Sage 50"), font=("Segoe UI", 12, "bold"),
                 foreground="#eaf7ee", background=VERT).pack(anchor="w")
        tk.Label(textes, text=t("Chaque nuit, les ventes Clover sont importées dans Sage 50 : une facture par jour, une pour la fin de semaine."),
                 font=("Segoe UI", 10), foreground="#cdebd6", background=VERT).pack(anchor="w")
        lisere = tk.Frame(self, height=5, background=FOND)
        lisere.pack(fill="x")
        for couleur in (VERT_FONCE, ROUGE, JAUNE):
            tk.Frame(lisere, height=5, background=couleur).pack(side="left", fill="x", expand=True)

    def _construire_menu(self) -> None:
        """Menu en groupes repliables (demande du propriétaire du 2026-10-28) : Accueil, puis Administration, Stock,
        Vente, Fournisseur, Comptabilité, État ; un seul groupe ouvert à la fois (celui de la page affichée). Une page
        cachée par le profil est absente ; un groupe sans page permise aussi."""
        tk.Label(self.menu, text="MENU", font=("Segoe UI", 8, "bold"), foreground="#7d8b81",
                 background=MENU_FOND).pack(anchor="w", padx=22, pady=(16, 6))
        n = len(self._pages)
        self.boutons_menu, self.barres_menu, self.pastilles_menu = [None] * n, [None] * n, [None] * n
        self.groupes_menu: dict[str, tuple[tk.Label, tk.Frame]] = {}
        self.groupe_de_page: dict[int, str] = {}
        self.groupe_ouvert = None
        for nom, icone_groupe, elements in MENU_GROUPES:
            visibles = [e for e in elements if isinstance(e, int) and e < n and self.au_menu(e)] + [
                e for e in elements if not isinstance(e, int) and self.permis_action(e)]
            if not visibles:
                continue
            parent = self.menu
            if nom:
                entete = tk.Label(self.menu, text=f"▸  {icone_groupe}  {t(nom)}", anchor="w",
                                  font=("Segoe UI Semibold", 10), background=MENU_FOND, foreground="#3d4a41",
                                  padx=14, pady=6, cursor="hand2")
                entete.pack(fill="x", padx=(8, 10), pady=(4, 0))
                parent = tk.Frame(self.menu, background=MENU_FOND)
                entete.bind("<Button-1>", lambda _e, g=nom: self.ouvrir_groupe(g, basculer=True))
                entete.bind("<Enter>", lambda _e, w=entete: w.configure(background=MENU_SURVOL))
                entete.bind("<Leave>", lambda _e, w=entete: w.configure(background=MENU_FOND))
                self.groupes_menu[nom] = (entete, parent)
            for element in elements:
                if isinstance(element, int):
                    if element >= n:
                        continue
                    self._ligne_menu(parent, element, decale=bool(nom))
                    if nom:
                        self.groupe_de_page[element] = nom
                elif self.permis_action(element):
                    self._action_menu(parent, nom, *element)
        cachees = tk.Frame(self.menu)  # pages sans ligne de menu (Rapports : par ses onglets) : jamais affiché
        for index in range(n):
            if self.boutons_menu[index] is None:
                self._ligne_menu(cachees, index, decale=False)
                if index in GROUPE_DES_PAGES_SANS_LIGNE:
                    self.groupe_de_page[index] = GROUPE_DES_PAGES_SANS_LIGNE[index]
        manuel = tk.Label(self.menu, text="📖   " + t("Manuel d'utilisation (PDF)"), anchor="w", font=("Segoe UI", 10),
                          background=MENU_FOND, foreground=VERT_FONCE, padx=16, pady=7, cursor="hand2")
        manuel.pack(fill="x", padx=(12, 10), pady=(10, 1))
        manuel.bind("<Button-1>", lambda _e: self.ouvrir_manuel())
        manuel.bind("<Enter>", lambda _e: manuel.configure(background=MENU_SURVOL))
        manuel.bind("<Leave>", lambda _e: manuel.configure(background=MENU_FOND))
        self._actif = None
        bas = tk.Frame(self.menu, background=MENU_FOND)
        bas.pack(side="bottom", fill="x", padx=16, pady=14)
        if self.session is not None:
            tk.Label(bas, text=f"👤  {self.session.nom}", font=("Segoe UI Semibold", 10), foreground=TEXTE,
                     background=MENU_FOND).pack(anchor="w")
            tk.Label(bas, text=t(self.session.profil), font=("Segoe UI", 9), foreground="#5a6b60",
                     background=MENU_FOND).pack(anchor="w", padx=(24, 0))
            for texte, commande in ((t("Changer mon mot de passe"), self.changer_mot_de_passe),
                                    (t("Se déconnecter"), self.se_deconnecter)):
                lien = tk.Label(bas, text=texte, font=("Segoe UI", 9, "underline"), foreground=VERT_FONCE,
                                background=MENU_FOND, cursor="hand2")
                lien.pack(anchor="w", padx=(24, 0))
                lien.bind("<Button-1>", lambda _e, c=commande: c())
            tk.Frame(bas, height=10, background=MENU_FOND).pack()
        tk.Label(bas, text="🌐  Langue / Language", font=("Segoe UI", 9), foreground="#5a6b60",
                 background=MENU_FOND).pack(anchor="w")
        self.langue = tk.StringVar(value=langues.LANGUES[langues.courante()])
        selecteur = ttk.Combobox(bas, textvariable=self.langue, values=list(langues.LANGUES.values()),
                                 state="readonly", width=18)
        selecteur.pack(anchor="w", pady=(4, 10), fill="x")
        selecteur.bind("<<ComboboxSelected>>", lambda _e: self.changer_langue())
        from .aide import COPYRIGHT, VERSION
        for texte in (f"MVOGMBI_Sync {VERSION}", COPYRIGHT, t("Tous droits réservés.")):
            tk.Label(bas, text=texte, font=("Segoe UI", 8), foreground="#8a978e", background=MENU_FOND).pack(anchor="w")

    def _ligne_menu(self, parent, index: int, decale: bool) -> None:
        icone, titre = self._pages[index]
        titre = t(LIBELLES_MENU[index]) if index in LIBELLES_MENU else re.sub(r"^\d+\.\s*", "", titre)
        ligne = tk.Frame(parent, background=MENU_FOND)
        if self.au_menu(index):  # page cachée : absente du menu
            ligne.pack(fill="x", padx=(20 if decale else 8, 10), pady=1)
        barre = tk.Frame(ligne, width=4, background=MENU_FOND)
        barre.pack(side="left", fill="y")
        bouton = tk.Label(ligne, text=f"{icone}   {titre}", anchor="w", font=("Segoe UI", 10),
                          background=MENU_FOND, foreground=TEXTE, padx=12, pady=4, cursor="hand2")
        bouton.pack(side="left", fill="x", expand=True)
        pastille = tk.Label(ligne, text="", font=("Segoe UI", 9), background=MENU_FOND, padx=6)
        pastille.place(relx=1.0, rely=0.5, anchor="e")
        for element in (bouton, pastille):
            element.bind("<Button-1>", lambda _e, i=index: self.aller(i))
            element.bind("<Enter>", lambda _e, i=index: self._survol_menu(i, True))
            element.bind("<Leave>", lambda _e, i=index: self._survol_menu(i, False))
        self.boutons_menu[index], self.barres_menu[index], self.pastilles_menu[index] = bouton, barre, pastille

    def _action_menu(self, parent, groupe, icone: str, titre: str, _page: int, methode: str, *arguments) -> None:
        """Entrée qui ouvre une fenêtre de travail (inventaire, transferts…) ou un onglet des Rapports."""
        bouton = tk.Label(parent, text=f"{icone}   {t(titre)}", anchor="w", font=("Segoe UI", 10),
                          background=MENU_FOND, foreground=TEXTE, padx=12, pady=4, cursor="hand2")
        bouton.pack(fill="x", padx=(24, 10), pady=1)
        bouton.bind("<Button-1>", lambda _e: (self._lancer_action(methode, *arguments), self.ouvrir_groupe(groupe)))
        bouton.bind("<Enter>", lambda _e: bouton.configure(background=MENU_SURVOL))
        bouton.bind("<Leave>", lambda _e: bouton.configure(background=MENU_FOND))

    def permis_fenetre(self, action: str) -> bool:
        """Action sensible d'une fenêtre (utilisateurs.ACTIONS_FENETRES) non retirée au profil."""
        return action not in getattr(self, "_refusees", set())

    def permis_action(self, element: tuple) -> bool:
        """Entrée du menu permise : cochée (accès par fonction) ; sinon sa page l'est et le profil n'a pas retiré
        cette fonction."""
        fonctions = getattr(self, "_fonctions", None)
        if fonctions is not None:
            return element[1] in fonctions
        return self.permis(element[2]) and element[1] not in getattr(self, "_refusees", set())

    def _lancer_action(self, methode: str, *arguments) -> None:
        """Entrée du menu : la fenêtre de travail qu'elle ouvre (FenetreOutil) remplace l'outil affiché dans la
        fenêtre principale ; une fenêtre de création (tk.Toplevel) reste à part."""
        self._mode_outil = "remplacer"
        try:
            getattr(self, methode)(*arguments)
        finally:
            self._mode_outil = "empiler"

    # ------------------------------------------------------------ outils dans la fenêtre principale
    def nouvel_outil(self, fenetre) -> ttk.Frame:
        """Panneau d'une FenetreOutil : bandeau (titre, « ✖ Fermer » ou « ◀ Retour ») puis le corps où elle se
        place. Ouvert depuis le menu : remplace l'outil affiché ; depuis un outil (fiche, sous-liste) : par-dessus."""
        if getattr(self, "_mode_outil", "empiler") == "remplacer":
            self._vider_pile()
            self._mode_outil = "empiler"  # les fenêtres ouvertes ensuite par le même clic s'empilent
        if self._pile_outils:
            self._pile_outils[-1]["cadre"].pack_forget()
        cadre = ttk.Frame(self.zone_outil)
        bandeau = ttk.Frame(cadre)
        bandeau.pack(fill="x", pady=(0, 6))
        titre = tk.Label(bandeau, text="", font=("Segoe UI Semibold", 15), foreground=VERT_FONCE,
                         background=fond_de(bandeau))
        titre.pack(side="left")
        Bouton(bandeau, ("◀  " + t("Retour")) if self._pile_outils else ("✖  " + t("Fermer")), fenetre.destroy,
               "secondaire", petit=True).pack(side="right")
        corps = ttk.Frame(cadre)
        corps.pack(fill="both", expand=True)
        self._pile_outils.append({"cadre": cadre, "fenetre": fenetre, "titre": titre})
        cadre.pack(fill="both", expand=True)
        self.onglets.pack_forget()
        self.zone_outil.pack(fill="both", expand=True)
        return corps

    def titre_outil(self, fenetre, texte: str) -> None:
        for entree in self._pile_outils:
            if entree["fenetre"] is fenetre:
                entree["titre"].configure(text=texte)

    def fermer_outil(self, fenetre=None) -> None:
        if self._pile_outils:
            (fenetre or self._pile_outils[-1]["fenetre"]).destroy()

    def _outil_detruit(self, fenetre) -> None:
        entree = next((e for e in self._pile_outils if e["fenetre"] is fenetre), None)
        if entree is None or not self.onglets.winfo_exists():  # application en train de se fermer
            return
        self._pile_outils.remove(entree)
        if entree["cadre"].winfo_exists():
            entree["cadre"].destroy()
        if self._pile_outils:
            self._pile_outils[-1]["cadre"].pack(fill="both", expand=True)
        else:
            self.zone_outil.pack_forget()
            self.onglets.pack(fill="both", expand=True)

    def _vider_pile(self) -> None:
        pile, self._pile_outils = list(self._pile_outils), []
        for entree in pile:
            if entree["cadre"].winfo_exists():
                entree["cadre"].destroy()

    def _cacher_outils(self) -> None:
        """Retour à une page : l'outil affiché est fermé."""
        self._vider_pile()
        self.zone_outil.pack_forget()
        if not self.onglets.winfo_ismapped():
            self.onglets.pack(fill="both", expand=True)

    def ouvrir_groupe(self, nom: str | None, basculer: bool = False) -> None:
        """Ouvre le groupe `nom` et referme les autres (un clic sur le groupe ouvert le referme)."""
        if basculer and nom == self.groupe_ouvert:
            nom = None
        for g, (entete, conteneur) in self.groupes_menu.items():
            ouvert = g == nom
            texte = entete.cget("text")
            entete.configure(text=("▾" if ouvert else "▸") + texte[1:])
            if ouvert:
                conteneur.pack(fill="x", after=entete)
            else:
                conteneur.pack_forget()
        self.groupe_ouvert = nom

    def ouvrir_creation_article(self) -> None:
        self.page_correspondance.creer_article()

    def ouvrir_rapports(self, onglet: str) -> None:
        """Page Rapports sur l'onglet voulu (Suivi, Recherche, Factures archivées, Statistiques)."""
        self.aller(RAPPORTS)
        onglets = self.page_rapports.onglets
        if getattr(self, "_fonctions", None) is not None:  # accès par fonction : onglets non permis masqués
            permis = set(self._fonctions)
            if any(f.startswith("Interrogation de compte") for f in permis):
                permis.add("Recherche dans l'historique")
            for o in onglets.tabs():  # les onglets masqués y sont aussi
                titre = next((x for x in TITRES_ONGLETS_RAPPORTS if t(x) == onglets.tab(o, "text").strip()), None)
                if titre and titre not in permis:
                    onglets.hide(o)
                elif titre:
                    onglets.add(o)  # réaffiche un onglet masqué
        for o in onglets.tabs():
            if onglets.tab(o, "text").strip() == t(onglet):
                onglets.select(o)

    def ouvrir_articles_clover(self) -> None:
        from .fenetre_articles_clover import FenetreArticlesClover
        FenetreArticlesClover(self, self.racine)

    def corriger_comptes_sage(self) -> None:
        """Articles Sage dont les comptes manquent ou ne suivent pas la table catégorie -> comptes ; les comptes
        manquants (qui bloquent l'import) d'abord."""
        from .fenetre_couts import FenetreComptesSage
        FenetreComptesSage(self, self.racine, manquants_d_abord=True)

    def ouvrir_inventaire(self) -> None:
        from .page_inventaire import FenetreInventaire
        FenetreInventaire(self, self.racine)

    def ouvrir_prix_marges(self) -> None:
        from .fenetre_prix_marges import ouvrir
        ouvrir(self, self.racine)

    def ouvrir_planning(self) -> None:
        from .fenetre_planning import FenetrePlanning
        FenetrePlanning(self, self.racine)

    def ouvrir_mon_horaire(self) -> None:
        from .fenetre_planning import FenetreMonHoraire
        FenetreMonHoraire(self, self.racine, self.session.nom if self.session is not None else "")

    def ouvrir_liste(self, genre: str) -> None:
        from .fenetre_gestion import ouvrir_liste
        ouvrir_liste(self, self.racine, genre)

    def ouvrir_documents(self, genre: str) -> None:
        from .fenetre_gestion import FenetreDocuments
        FenetreDocuments(self, self.racine, genre, self._auteur())

    def ouvrir_interrogation(self, type_: str) -> None:
        """Interrogation de compte (client, fournisseur, article) : recherche dans l'historique de ce type."""
        self.ouvrir_rapports("Recherche dans l'historique")
        self.page_rapports.type_recherche.set(t(type_))
        self.page_rapports._preparer_recherche()

    def ouvrir_saisie_achat(self) -> None:
        from .fenetre_gestion import saisir_facture_achat
        saisir_facture_achat(self, self.racine)

    def ouvrir_saisie_bon(self) -> None:
        from .fenetre_gestion import saisir_bon_commande
        saisir_bon_commande(self, self.racine)

    def ouvrir_receptions(self) -> None:
        from .fenetre_bons_commande import FenetreBons
        FenetreBons(self, self.racine)

    def ouvrir_comptabilite(self, onglet: str) -> None:
        from .fenetre_comptabilite import FenetreComptabilite
        FenetreComptabilite(self, self.racine, onglet)

    def ouvrir_pointage(self) -> None:
        from .fenetre_pointage import ouvrir
        ouvrir(self, self.racine)

    def _auteur(self) -> str:
        return self.session.nom if self.session is not None else "Administrateur"

    def ouvrir_feuilles_temps(self) -> None:
        from .fenetre_feuilles_temps import ouvrir
        ouvrir(self, self.racine, self._auteur())

    def ouvrir_promotions(self) -> None:
        from .fenetres_gestion4 import FenetrePromotions
        FenetrePromotions(self, self.racine, self._auteur())

    def ouvrir_inventaire_tournant(self) -> None:
        from .fenetres_gestion4 import FenetreInventaireTournant
        FenetreInventaireTournant(self, self.racine)

    def ouvrir_relances(self) -> None:
        from .fenetres_gestion4 import FenetreRelances
        FenetreRelances(self, self.racine)

    def ouvrir_tableau(self) -> None:
        from .fenetres_gestion4 import FenetreTableau
        FenetreTableau(self, self.racine)

    def ouvrir_retours(self) -> None:
        from .fenetres_gestion3 import FenetreRetours
        FenetreRetours(self, self.racine, self._auteur())

    def ouvrir_etiquettes(self) -> None:
        from .fenetres_gestion3 import FenetreEtiquettes
        FenetreEtiquettes(self, self.racine)

    def ouvrir_main_oeuvre(self) -> None:
        from .fenetres_gestion3 import FenetreMainOeuvre
        FenetreMainOeuvre(self, self.racine)

    def ouvrir_depenses(self) -> None:
        from .fenetres_gestion2 import FenetreDepenses
        FenetreDepenses(self, self.racine, self._auteur())

    def ouvrir_fin_emploi(self) -> None:
        from .fenetres_gestion2 import FenetreFinEmploi
        FenetreFinEmploi(self, self.racine)

    def ouvrir_journal_operations(self) -> None:
        from .fenetres_gestion2 import FenetreJournalOperations
        FenetreJournalOperations(self, self.racine)

    def ouvrir_conges(self) -> None:
        from .fenetre_conges import FenetreConges
        FenetreConges(self, self.racine, self._auteur())

    def ouvrir_pertes(self) -> None:
        from .fenetre_pertes import FenetrePertes
        FenetrePertes(self, self.racine, self._auteur())

    def ouvrir_caisse(self) -> None:
        from .fenetre_caisse import FenetreCaisse
        FenetreCaisse(self, self.racine, self._auteur())

    def ouvrir_sauvegarde(self) -> None:
        from .fenetre_sauvegarde import FenetreSauvegarde
        FenetreSauvegarde(self, self.racine)

    def ouvrir_traitement_paie(self) -> None:
        from .fenetre_paie import FenetrePaie
        FenetrePaie(self, self.racine, ouvrir_feuilles=self.ouvrir_feuilles_temps)

    def ouvrir_employes_paie(self) -> None:
        from .fenetre_feuilles_temps import FenetreEmployes
        FenetreEmployes(self, self.racine, lambda: None)

    def ouvrir_bons_commande(self) -> None:
        from .fenetre_bons_commande import ouvrir
        ouvrir(self, self.racine)

    def ouvrir_transferts(self) -> None:
        from .fenetre_transferts import FenetreTransferts
        FenetreTransferts(self, self.racine)

    def ouvrir_comptes_sage(self) -> None:
        from .fenetre_article import FenetreCategories
        FenetreCategories(self, self.racine)

    def ouvrir_couts_clover(self) -> None:
        from .fenetre_couts import FenetreCoutsClover
        FenetreCoutsClover(self, self.racine)

    def ouvrir_manuel(self) -> None:
        """Manuel illustré dans la langue de l'application (sinon en français) : à côté du programme installé, sinon
        dans documentation/ (poste de développement)."""
        # manuel du profil (demande du propriétaire du 2026-10-29) : seulement les chapitres des pages permises
        from .manuel import manuel_du_profil

        permises = None if self._permises is None else {i for i in range(len(self._pages)) if self.permis(i)}
        profil = t(self.session.profil) if self.session is not None else ""

        def travail():
            try:
                chemin = manuel_du_profil(self.racine, permises, profil, langues.courante())
            except Exception as exc:
                texte = str(exc)
                self.after(0, lambda: messagebox.showerror(TITRE, texte))
                return
            if chemin is None:
                self.after(0, lambda: messagebox.showinfo(
                    TITRE, t("Le manuel d'utilisation est introuvable : réinstallez l'application.")))
            else:
                os.startfile(chemin)

        threading.Thread(target=travail, daemon=True).start()  # manuel du profil : quelques secondes la 1re fois

    def _survol_menu(self, index: int, survol: bool) -> None:
        if self.boutons_menu[index] is None or self.boutons_menu[index] is self._actif:
            return
        couleur = MENU_SURVOL if survol else MENU_FOND
        self.boutons_menu[index].configure(background=couleur)
        self.pastilles_menu[index].configure(background=couleur)

    def changer_mot_de_passe(self) -> None:
        from .connexion import changer_mon_mot_de_passe

        changer_mon_mot_de_passe(self, self.racine, self.session, TITRE)

    # ---------------------------------------------------------------- verrouillage après inactivité
    def _preparer_verrou(self) -> None:
        """Verrouillage après [general] verrouillage_minutes (5 par défaut ; 0 = jamais) sans souris ni clavier."""
        self.minutes_verrou = int(self.config_toml.get("general", {}).get("verrouillage_minutes", 5) or 0)
        self._verrou = None
        self._derniere_activite = time.time()
        if self.session is None or self.minutes_verrou <= 0:
            return
        for evenement in ("<Any-KeyPress>", "<Any-ButtonPress>", "<Motion>", "<MouseWheel>"):
            self.bind_all(evenement, self._activite, add="+")
        self.after(10_000, self._surveiller_inactivite)

    def _activite(self, _evenement=None) -> None:
        if self._verrou is None:
            self._derniere_activite = time.time()

    def _surveiller_inactivite(self) -> None:
        try:
            if self._verrou is None and time.time() - self._derniere_activite >= self.minutes_verrou * 60:
                self.verrouiller()
            self.after(10_000, self._surveiller_inactivite)
        except tk.TclError:  # fenêtre fermée
            pass

    def verrouiller(self) -> None:
        from .connexion import Verrou

        if self._verrou is not None or self.session is None:
            return
        self.withdraw()  # rien n'est visible tant que le mot de passe n'est pas redonné ; les traitements continuent
        self._verrou = Verrou(self, self.racine, self.session, TITRE, self._deverrouiller, self.se_deconnecter)

    def _deverrouiller(self) -> None:
        if self._verrou is not None:
            self._verrou.destroy()
            self._verrou = None
        self.deiconify()
        self.lift()
        self._derniere_activite = time.time()

    def se_deconnecter(self) -> None:
        self.deconnecter = True  # retour à la fenêtre de connexion
        self.destroy()

    def aller(self, index: int) -> None:
        if not self.permis(index):
            return
        if getattr(self, "_pile_outils", None) is not None:
            self._cacher_outils()
        self.onglets.select(index)
        if hasattr(self, "groupes_menu") and self.groupe_de_page.get(index, self.groupe_ouvert) != self.groupe_ouvert:
            self.ouvrir_groupe(self.groupe_de_page.get(index))
        for i, bouton in enumerate(self.boutons_menu):
            if bouton is None:
                continue
            actif = i == index
            fond = MENU_ACTIF if actif else MENU_FOND
            bouton.configure(background=fond, foreground=VERT_FONCE if actif else TEXTE,
                             font=("Segoe UI Semibold", 10) if actif else ("Segoe UI", 10))
            self.pastilles_menu[i].configure(background=fond)
            self.barres_menu[i].configure(background=JAUNE if actif else MENU_FOND)
        self._actif = self.boutons_menu[index]

    def changer_langue(self) -> None:
        code = next(c for c, nom in langues.LANGUES.items() if nom == self.langue.get())
        if code == langues.courante():
            return
        self.config_toml.setdefault("general", {})["langue"] = code
        ecrire_config(self.chemin_config, self.config_toml)
        self.relancer = True  # la fenêtre est reconstruite dans la nouvelle langue
        self.destroy()

    # ---------------------------------------------------------------- outils d'interface
    def _var(self, cle: str, valeur, type_=tk.StringVar) -> tk.Variable:
        self.vars[cle] = type_(value=valeur)
        return self.vars[cle]

    def _champ(self, parent, ligne: int, libelle: str, cle: str, valeur="", secret: str | None = None,
               aide: str = "", parcourir: tuple | None = None, calendrier: bool = False):
        sur_carte = fond_de(parent) == CARTE
        ttk.Label(parent, text=libelle, style="Carte.TLabel" if sur_carte else "TLabel").grid(
            row=ligne, column=0, sticky="w", pady=4, padx=(0, 14))
        if secret:
            valeur = MASQUE if coffre.present(secret) else ""
        if calendrier:  # date AAAA-MM-JJ avec calendrier cliquable
            champ = ChampDate(parent, self._var(cle, valeur))
            champ.grid(row=ligne, column=1, sticky="w", pady=4)
        else:
            champ = ttk.Entry(parent, textvariable=self._var(cle, valeur), width=52, show="•" if secret else "")
            champ.grid(row=ligne, column=1, sticky="we", pady=4)
        if secret:
            # Le masque « •••••••• » n'est pas le mot de passe : il s'efface dès qu'on entre dans le champ,
            # sinon ce qu'on tape s'ajoute à lui ; il revient si le champ est laissé vide.
            variable = self.vars[cle]

            def entree(_evt, variable=variable):
                if variable.get() == MASQUE:
                    variable.set("")

            def sortie(_evt, variable=variable, secret=secret):
                if not variable.get() and coffre.present(secret):
                    variable.set(MASQUE)

            champ.bind("<FocusIn>", entree, add="+")
            champ.bind("<FocusOut>", sortie, add="+")
        if parcourir:
            Bouton(parent, t("Parcourir…"), lambda: self._parcourir(cle, *parcourir), "secondaire", petit=True).grid(
                row=ligne, column=2, padx=(8, 0))
        if aide:
            tk.Label(parent, text=aide, font=("Segoe UI", 9), foreground=TEXTE_DOUX, background=fond_de(parent),
                     wraplength=620, justify="left").grid(row=ligne + 1, column=1, sticky="w", pady=(0, 6))
        parent.columnconfigure(1, weight=1)
        return champ

    def _parcourir(self, cle: str, titre: str, types: list) -> None:
        chemin = filedialog.askopenfilename(title=titre, filetypes=types)
        if chemin:
            self.vars[cle].set(str(Path(chemin)))

    def _cadre(self, titre: str, icone: str = "•", filigrane: bool = True) -> ttk.Frame:
        """Page défilante (barre de défilement et molette seulement si le contenu dépasse la fenêtre),
        avec le logo pâli en bas à droite ; renvoie le cadre où placer le contenu."""
        exterieur = ttk.Frame(self.onglets)
        self.onglets.add(exterieur, text=titre)
        self._pages.append((icone, titre))
        toile = tk.Canvas(exterieur, background=fond_de(exterieur), highlightthickness=0, borderwidth=0)
        barre = ttk.Scrollbar(exterieur, orient="vertical", command=toile.yview)
        toile.configure(yscrollcommand=barre.set)
        toile.pack(side="left", fill="both", expand=True)
        logo = toile.create_image(0, 0, image=self._images["filigrane"], anchor="se") \
            if filigrane and self._images else None
        cadre = ttk.Frame(toile, padding=(4, 4))
        fenetre = toile.create_window(0, 0, window=cadre, anchor="nw")
        cadre.columnconfigure(0, weight=1)

        def ajuster(_evt=None):
            largeur, visible, contenu = toile.winfo_width(), toile.winfo_height(), cadre.winfo_reqheight()
            toile.itemconfigure(fenetre, width=largeur)
            toile.configure(scrollregion=(0, 0, largeur, max(contenu, visible)))
            if logo:
                toile.coords(logo, largeur - 16, max(contenu, visible) - 16)
            if contenu > visible and not barre.winfo_ismapped():
                barre.pack(side="right", fill="y", before=toile)
            elif contenu <= visible and barre.winfo_ismapped():
                barre.pack_forget()
                toile.yview_moveto(0)

        def molette(evt):
            if cadre.winfo_reqheight() > toile.winfo_height():
                toile.yview_scroll(-evt.delta // 120, "units")

        toile.bind("<Configure>", ajuster)
        cadre.bind("<Configure>", ajuster)
        exterieur.bind("<Enter>", lambda _e: self.bind_all("<MouseWheel>", molette))
        exterieur.bind("<Leave>", lambda _e: self.unbind_all("<MouseWheel>"))
        return cadre

    def _titre(self, parent, texte: str, sous_titre: str = "") -> tk.Frame:
        fond = fond_de(parent)
        bloc = tk.Frame(parent, background=fond)
        tk.Label(bloc, text=texte, font=("Segoe UI Semibold", 17), foreground=VERT_FONCE, background=fond).pack(anchor="w")
        souligne = tk.Frame(bloc, background=fond)
        souligne.pack(anchor="w", pady=(4, 0))
        for couleur, largeur in ((JAUNE, 46), (ROUGE, 14)):
            tk.Frame(souligne, width=largeur, height=4, background=couleur).pack(side="left", padx=(0, 4))
        if sous_titre:
            tk.Label(bloc, text=sous_titre, font=("Segoe UI", 10), foreground=TEXTE_DOUX, background=fond,
                     wraplength=760, justify="left").pack(anchor="w", pady=(8, 0))
        bloc.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 14))
        return bloc

    def _carte(self, parent, ligne: int, titre: str, numero: str = "", description: str = "",
               couleur: str = VERT) -> ttk.Frame:
        """Carte blanche à bordure fine, avec pastille numérotée et titre ; renvoie la zone des champs."""
        cadre = tk.Frame(parent, background=CARTE, highlightthickness=1, highlightbackground=BORDURE)
        cadre.grid(row=ligne, column=0, columnspan=3, sticky="we", pady=(0, 12))
        tk.Frame(cadre, width=4, background=couleur).pack(side="left", fill="y")
        interieur = tk.Frame(cadre, background=CARTE)
        interieur.pack(side="left", fill="both", expand=True)
        entete = tk.Frame(interieur, background=CARTE)
        entete.pack(fill="x", padx=16, pady=(12, 2))
        if numero:
            tk.Label(entete, text=numero, font=("Segoe UI Semibold", 9), foreground="white", background=couleur,
                     width=3, pady=1).pack(side="left", padx=(0, 10))
        tk.Label(entete, text=titre, font=("Segoe UI Semibold", 12), foreground=TEXTE, background=CARTE).pack(side="left")
        if description:
            tk.Label(interieur, text=description, font=("Segoe UI", 9), foreground=TEXTE_DOUX, background=CARTE,
                     wraplength=760, justify="left").pack(anchor="w", padx=16)
        zone = ttk.Frame(interieur, style="Carte.TFrame", padding=(16, 8, 16, 14))
        zone.pack(fill="x")
        zone.columnconfigure(1, weight=1)
        return zone

    def _sortie(self, parent, hauteur=6) -> tk.Text:
        zone = tk.Text(parent, height=hauteur, wrap="word", font=("Cascadia Mono", 9), relief="flat",
                       background="#f6f8f7", foreground="#24332a", borderwidth=0, padx=10, pady=8,
                       highlightthickness=1, highlightbackground="#dfe6e1", highlightcolor=VERT)
        zone.tag_configure("ok", foreground=VERT_FONCE)
        zone.tag_configure("erreur", foreground=ROUGE)
        zone.tag_configure("attention", foreground="#9a6a00")
        zone.tag_configure("date", foreground="#8a978e")
        return zone

    @staticmethod
    def _ecrire(zone: tk.Text, texte: str) -> None:
        """Ajoute une ligne colorée selon son contenu (succès, problème, information)."""
        bas = texte.lower()
        if texte.startswith("✘") or any(m in texte for m in ("PROBLÈME", "ERREUR", "PROBLEM", "ERROR")) \
                or "bloqu" in bas or "blocked" in bas or "refus" in bas:
            etiquette = "erreur"
        elif texte.startswith("✔") or "importée" in bas or "imported" in bas or "réussi" in bas:
            etiquette = "ok"
        elif "(info)" in bas or "à confirmer" in bas or "to confirm" in bas or "attention" in bas:
            etiquette = "attention"
        else:
            etiquette = ""
        if len(texte) > 9 and texte[2] == ":" and texte[5] == ":" and texte[8] == " ":  # « 19:38:46 … »
            zone.insert("end", texte[:9], "date")
            zone.insert("end", texte[9:] + "\n", etiquette)
        else:
            zone.insert("end", texte + "\n", etiquette)

    def _tache(self, titre: str, fonction, zone: tk.Text | None = None) -> None:
        """Exécute une action longue en arrière-plan ; ses messages s'affichent dans `zone`."""
        self.etat.config(text=f"{titre}…")

        def travail():
            try:
                resultat = fonction()
                self.file_messages.put((zone, f"✔ {titre} : {resultat or t('terminé')}"))
            except Exception as exc:
                self.file_messages.put((zone, f"✘ {titre} : {exc}"))
            self.file_messages.put((None, ""))

        threading.Thread(target=travail, daemon=True).start()

    def _relayer_messages(self) -> None:
        try:
            while True:
                zone, texte = self.file_messages.get_nowait()
                if zone is None:
                    self.etat.config(text=texte)
                    self.actualiser_tableau()
                else:
                    self._ecrire(zone, texte)
                    zone.see("end")
        except queue.Empty:
            pass
        self._attente = self.after(200, self._relayer_messages)

    def destroy(self) -> None:
        try:
            self.after_cancel(self._attente)
        except Exception:
            pass
        super().destroy()

    # ---------------------------------------------------------------- pages de texte
    def _zone_document(self, parent, blocs) -> tk.Text:
        """Texte mis en forme (titres, étapes, notes) ; le logo pâli occupe la marge de droite."""
        marge = 290 if self._images else 26
        zone = tk.Text(parent, wrap="word", relief="flat", background=CARTE, borderwidth=0, highlightthickness=1,
                       highlightbackground=BORDURE, padx=28, pady=20, font=("Segoe UI", 10), cursor="arrow",
                       spacing1=2, spacing3=2)
        zone.tag_configure("marge", rmargin=marge)
        zone.tag_configure("titre", font=("Segoe UI Semibold", 20), foreground=VERT, spacing3=12)
        zone.tag_configure("sous_titre", font=("Segoe UI Semibold", 13), foreground=VERT_FONCE, spacing1=18,
                           spacing3=6)
        zone.tag_configure("para", spacing3=6)
        zone.tag_configure("etape", lmargin1=14, lmargin2=32, spacing3=5)
        zone.tag_configure("puce", lmargin1=14, lmargin2=30, spacing3=3)
        zone.tag_configure("note", lmargin1=14, lmargin2=34, foreground="#8a5a00", spacing1=8, spacing3=10,
                           font=("Segoe UI Semibold", 10))
        zone.tag_configure("question", font=("Segoe UI Semibold", 11), foreground=VERT_FONCE, spacing1=14)
        zone.tag_configure("reponse", lmargin1=14, lmargin2=14, spacing3=4)
        for type_bloc, texte in blocs:
            prefixe = {"puce": "•  ", "question": "Q.  ", "note": "💡  "}.get(type_bloc, "")
            zone.insert("end", prefixe + texte + "\n", (type_bloc, "marge"))
        zone.configure(state="disabled")
        if self._images:
            logo = tk.Label(zone, image=self._images["filigrane_texte"], background=CARTE, borderwidth=0,
                            cursor="arrow")
            logo.place(relx=1.0, rely=0.0, x=-24, y=24, anchor="ne")
        return zone

    def _onglet_texte(self, titre_onglet: str, page: str, icone: str) -> None:
        from .aide import FAQ as TEXTE_FAQ
        from .aide import GUIDE as TEXTE_GUIDE

        blocs = (TEXTE_GUIDE if page == "guide" else TEXTE_FAQ)[langues.courante()]
        cadre = ttk.Frame(self.onglets, padding=(4, 4))
        self.onglets.add(cadre, text=titre_onglet)
        self._pages.append((icone, titre_onglet))
        zone = self._zone_document(cadre, blocs)
        defilement = ttk.Scrollbar(cadre, orient="vertical", command=zone.yview)
        zone.configure(yscrollcommand=defilement.set)
        defilement.pack(side="right", fill="y")
        zone.pack(side="left", fill="both", expand=True)

    # ---------------------------------------------------------------- Accueil : mise en route
    ETAPES = (
        (CLOVER, "1", "Clover", "Identifiant marchand et jeton API"),
        (SAGE, "2", "Sage 50", "Fichier d'entreprise et mots de passe"),
        (COURRIEL, "3", "Courriel", "Compte rendu après chaque nuit"),
        (AUTOMATISATION, "4", "Automatisation", "Tâche planifiée installée"),
        (CORRESPONDANCE, "5", "Correspondance", "Articles Clover reliés à Sage"),
        (TABLEAU, "6", "Premier import", "Une facture importée dans Sage"),
        (ENCAISSEMENTS, "7", "Encaissements", "Dépôts appliqués sur les factures"),
        (FOURNISSEURS, "8", "Factures fournisseurs", "Factures d'achat importées dans Sage"),
        (PAIEMENTS, "9", "Paiements fournisseurs", "Boîte des avis de paiement reliée"),
        (RAPPROCHEMENT, "10", "Rapprochement bancaire", "Relevés Desjardins chargés"),
    )

    def _onglet_accueil(self) -> None:
        from .aide import ACCUEIL as TEXTE_ACCUEIL

        cadre = ttk.Frame(self.onglets, padding=(4, 4))
        self.onglets.add(cadre, text=t("Accueil"))
        self._pages.append(("🏠", t("Accueil")))
        cadre.columnconfigure(0, weight=1)
        cadre.rowconfigure(1, weight=1)
        self.lignes_etapes, self.progression_etapes = {}, None
        if self.session is None or self.session.est_admin:  # la mise en service : administrateur
            self._mise_en_route(cadre)
        zone = self._zone_document(cadre, TEXTE_ACCUEIL[langues.courante()])
        zone.grid(row=1, column=0, sticky="nsew")
        defilement = ttk.Scrollbar(cadre, orient="vertical", command=zone.yview)
        zone.configure(yscrollcommand=defilement.set)
        defilement.grid(row=1, column=1, sticky="ns")

    def _mise_en_route(self, cadre) -> None:
        """Carte « Mise en route » : les dix étapes, une par page, avec ✔ quand elle est faite."""
        carte = self._carte(cadre, 0, t("Mise en route"), "✓",
                            t("Dix étapes, une par page, pour une gestion entièrement automatique. Chaque étape "
                              "passe au vert (✔) quand elle est faite."))
        self.progression_etapes = tk.Label(carte, text="", font=("Segoe UI Semibold", 9), foreground=VERT_FONCE,
                                           background=CARTE)
        self.progression_etapes.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 4))
        etapes = [e for e in self.ETAPES if self.permis(e[0])]  # pages du profil seulement
        moitie = (len(etapes) + 1) // 2  # deux colonnes : 1 à 5 à gauche, 6 à 10 à droite
        for n, (page, numero, titre, description) in enumerate(etapes):
            case = tk.Frame(carte, background=CARTE)
            case.grid(row=1 + n % moitie, column=n // moitie, sticky="we", padx=(0, 18), pady=4)
            carte.columnconfigure(n // moitie, weight=1, uniform="etapes")
            etat = tk.Label(case, text="●", font=("Segoe UI Semibold", 14), foreground=JAUNE, background=CARTE,
                            width=2)
            etat.grid(row=0, column=0, rowspan=2, padx=(0, 8))
            tk.Label(case, text=f"{numero}. {t(titre)}", font=("Segoe UI Semibold", 10), foreground=TEXTE,
                     background=CARTE).grid(row=0, column=1, sticky="w")
            detail = tk.Label(case, text=t(description), font=("Segoe UI", 9), foreground=TEXTE_DOUX,
                              background=CARTE)
            detail.grid(row=1, column=1, sticky="w")
            Bouton(case, t("Ouvrir"), lambda p=page: self.aller(p), "secondaire", fond=CARTE, petit=True).grid(
                row=0, column=2, rowspan=2, padx=(10, 0))
            case.columnconfigure(1, weight=1)
            self.lignes_etapes[page] = (etat, detail, t(description))

    def _etat_etapes(self) -> dict[int, tuple[bool, str]]:
        """Pour chaque étape de mise en route : (faite, précision)."""
        c = self.config_toml
        etats = {
            CLOVER: (bool(c.get("clover", {}).get("merchant_id")) and coffre.present(coffre.CLOVER_JETON), ""),
            COURRIEL: (bool(c.get("courriel", {}).get("serveur") and c["courriel"].get("destinataires"))
                       and coffre.present(coffre.COURRIEL), ""),
            AUTOMATISATION: (self._tache_installee, ""),
        }
        fichier = c.get("sage_import", {}).get("fichier_entreprise", "")
        sage_ok = bool(fichier) and Path(fichier).is_file() and coffre.present(coffre.SAGE_LECTURE) \
            and coffre.present(coffre.SAGE_IMPORT)
        etats[SAGE] = (sage_ok, Path(fichier).name if sage_ok else "")
        correspondance = self.racine / "donnees" / "correspondance_articles.xlsx"
        etats[CORRESPONDANCE] = (correspondance.exists(), "")
        journal = self.racine / "donnees" / "journal_imports.csv"
        derniere = ""
        if journal.exists():
            lignes = [l for l in journal.read_text(encoding="utf-8-sig").splitlines()[1:] if ";importée" in l]
            if lignes:
                derniere = lignes[-1].split(";")[1]
        etats[TABLEAU] = (bool(derniere), derniere)
        enc = c.get("encaissements", {})
        log = self.racine / "donnees" / "journal_automatique.log"
        encaisse = log.exists() and bool(re.search(r"[1-9]\d* dépôt\(s\) encaissé",
                                                    log.read_text(encoding="utf-8", errors="replace")))
        etats[ENCAISSEMENTS] = (bool(enc.get("date_depart")) and encaisse,
                                t("Depuis le {date}", date=enc["date_depart"]) if enc.get("date_depart") and encaisse
                                else "")
        etats[FOURNISSEURS] = self._etat_registre("factures_fournisseurs.json", "Importée dans Sage",
                                                  "{n} facture(s) importée(s)")
        b = c.get("boite_paiements", {})
        boite = bool(b.get("serveur") and b.get("utilisateur")) and coffre.present(coffre.BOITE_PAIEMENTS)
        saisis = self._etat_registre("paiements_fournisseurs.json", ("Saisi dans Sage", "Déjà dans Sage"),
                                     "{n} paiement(s) saisi(s)")[1]
        etats[PAIEMENTS] = (boite, saisis if boite else "")
        dossier = self.racine / "donnees" / "releves_desjardins"
        releves = len(list(dossier.glob("*.pdf"))) if dossier.is_dir() else 0
        etats[RAPPROCHEMENT] = (releves > 0, t("{n} relevé(s) chargé(s)", n=releves) if releves else "")
        return etats

    def _etat_registre(self, nom: str, etats, texte: str) -> tuple[bool, str]:
        """(au moins un élément dans l'un des `etats`, « n … ») d'un registre JSON de donnees/."""
        chemin = self.racine / "donnees" / nom
        try:
            elements = json.loads(chemin.read_text(encoding="utf-8")) if chemin.exists() else []
        except (OSError, ValueError):
            elements = []
        etats = (etats,) if isinstance(etats, str) else etats
        n = sum(1 for x in elements if isinstance(x, dict) and x.get("etat") in etats)
        return n > 0, t(texte, n=n) if n else ""

    def _maj_etapes(self) -> None:
        etats = self._etat_etapes()
        etats = {page: etat for page, etat in etats.items() if page in self.lignes_etapes}
        for page, (faite, precision) in etats.items():
            etat, detail, description = self.lignes_etapes[page]
            etat.configure(text="✔" if faite else "●", foreground=VERT if faite else JAUNE)
            detail.configure(text=precision or description)
            if hasattr(self, "pastilles_menu"):
                self.pastilles_menu[page].configure(text="✔" if faite else "●", foreground=VERT if faite else JAUNE)
        faites = sum(1 for faite, _ in etats.values() if faite)
        if self.progression_etapes is None:
            return None
        self.progression_etapes.configure(text=t("{n} étape(s) sur {total} terminée(s)", n=faites, total=len(etats))
                                          + ("  ✔" if faites == len(etats) else ""))
        return None

    # ---------------------------------------------------------------- pages de configuration
    def _onglet_clover(self) -> None:
        c = self.config_toml.get("clover", {})
        f = self._cadre(t("1. Clover"), "🛒")
        self._titre(f, t("Accès à votre compte Clover (lecture des ventes)"),
                    t("L'application lit les ventes payées dans Clover ; elle n'y modifie jamais rien."))
        carte = self._carte(f, 1, t("Identifiants Clover"), "1")
        self._champ(carte, 0, t("Identifiant marchand"), "clover.merchant_id", c.get("merchant_id", ""),
                    aide=t("13 caractères, visibles dans l'adresse du tableau de bord Clover après « /m/ »."))
        self._champ(carte, 2, t("Jeton API"), "secret.clover", secret=coffre.CLOVER_JETON,
                    aide=t("Clover > Compte et configuration > Jetons API (droits en lecture). "
                           "Laissez « •••• » pour conserver le jeton enregistré."))
        Bouton(carte, "🔌  " + t("Tester la connexion à Clover"), self.tester_clover).grid(
            row=4, column=1, sticky="w", pady=(6, 8))
        self.sortie_clover = self._sortie(carte, 4)
        self.sortie_clover.grid(row=5, column=0, columnspan=3, sticky="we")
        from .page_points_vente import CartePointsVente

        zone = self._carte(f, 2, t("Points de vente"), "2",
                           t("Chaque point de vente Clover est un dépôt (emplacement d'inventaire) dans Sage, avec son "
                             "client Sage et ses factures (« Vente 2026-10-23 » pour le n° 1, « V2 2026-10-23 » pour "
                             "le n° 2…). Le n° 1 utilise les identifiants ci-dessus."))
        self.points_vente = CartePointsVente(self, zone)

    def _onglet_sage(self) -> None:
        b, i, a = (self.config_toml.get(s, {}) for s in ("sage_base", "sage_import", "automatique"))
        f = self._cadre(t("2. Sage 50"), "📒")
        self._titre(f, t("Fichier d'entreprise et comptes Sage"))
        types = [(t("Fichier d'entreprise Sage"), "*.SAI"), (t("Tous les fichiers"), "*.*")]
        fichier = self._carte(f, 1, t("Fichier d'entreprise"), "1")
        self._champ(fichier, 0, t("Fichier d'entreprise (.SAI)"), "sage.fichier", i.get("fichier_entreprise", ""),
                    aide=t("Le fichier dans lequel les factures sont importées. Pour les essais : une COPIE."),
                    parcourir=(t("Fichier d'entreprise Sage"), types))
        self._champ(fichier, 2, t("Premier jour à importer"), "auto.date_depart",
                    a.get("date_depart", date.today().isoformat()), calendrier=True,
                    aide=t("AAAA-MM-JJ. Utilisé seulement si Sage ne contient encore aucune facture « Vente AAAA-MM-JJ »."))
        self._champ(fichier, 4, t("Compte de dépôt des encaissements"), "enc.compte",
                    str(self.config_toml.get("encaissements", {}).get("compte_depot", "1055")),
                    aide=t("Compte de banque Sage où Clover dépose les ventes par carte (1055 = Compte Desjardins)."))
        self._champ(fichier, 6, t("Encaisser à partir des ventes du"), "enc.depart",
                    str(self.config_toml.get("encaissements", {}).get("date_depart", date.today().isoformat())),
                    calendrier=True, aide=t("AAAA-MM-JJ. Les dépôts des ventes antérieures ne sont jamais encaissés."))
        comptes = self._carte(f, 2, t("Utilisateurs Sage"), "2")
        self._champ(comptes, 0, t("Utilisateur Sage (lecture)"), "sage.utilisateur", b.get("utilisateur", "mvogmbi_sync"),
                    aide=t("Utilisateur avec « Droits d'accès aux produits tiers : Consultation seule » "
                           "et accès Vue aux modules Stocks & Services et Clients & Ventes."))
        self._champ(comptes, 2, t("Mot de passe (lecture)"), "secret.sage_lecture", secret=coffre.SAGE_LECTURE)
        self._champ(comptes, 3, t("Mot de passe Sage pour l'import"), "secret.sage_import", secret=coffre.SAGE_IMPORT,
                    aide=t("Mot de passe demandé par la fenêtre « Sage 50 - Password » de l'import (utilisateur sysadmin)."))
        Bouton(comptes, "📒  " + t("Tester l'accès à Sage"), self.tester_sage).grid(row=5, column=1, sticky="w",
                                                                                    pady=(6, 8))
        self.sortie_sage = self._sortie(comptes, 4)
        self.sortie_sage.grid(row=6, column=0, columnspan=3, sticky="we")

    def _onglet_courriel(self) -> None:
        c = self.config_toml.get("courriel", {})
        f = self._cadre(t("3. Courriel"), "📧")
        self._titre(f, t("Alertes par courriel"))
        serveur = self._carte(f, 1, t("Serveur d'envoi"), "1")
        self._champ(serveur, 0, t("Serveur d'envoi (SMTP)"), "courriel.serveur", c.get("serveur", ""),
                    aide=t("Ex. smtp.office365.com (Outlook) ou smtp.gmail.com (Gmail : mot de passe d'application)."))
        self._champ(serveur, 2, t("Port"), "courriel.port", str(c.get("port", 587)))
        ttk.Label(serveur, text=t("Sécurité"), style="Carte.TLabel").grid(row=3, column=0, sticky="w", pady=4)
        ttk.Combobox(serveur, textvariable=self._var("courriel.securite", c.get("securite", "starttls")),
                     values=["starttls", "ssl", "aucune"], state="readonly", width=12).grid(row=3, column=1, sticky="w")
        self._champ(serveur, 4, t("Utilisateur"), "courriel.utilisateur", c.get("utilisateur", ""))
        self._champ(serveur, 5, t("Mot de passe"), "secret.courriel", secret=coffre.COURRIEL)
        envoi = self._carte(f, 2, t("Envoi du compte rendu"), "2")
        self._champ(envoi, 0, t("Expéditeur"), "courriel.expediteur", c.get("expediteur", ""))
        self._champ(envoi, 1, t("Destinataire(s)"), "courriel.destinataires", c.get("destinataires", ""),
                    aide=t("Une ou plusieurs adresses séparées par des virgules."))
        self._champ(envoi, 4, t("Autres destinataires"), "courriel.copie", c.get("copie", ""),
                    aide=t("Facultatif : autres personnes à informer, adresses séparées par des virgules "
                           "(ex. comptable@exemple.com, gerant@exemple.com)."))
        ttk.Checkbutton(envoi, text=t("Envoyer le compte rendu après chaque traitement, y compris en cas de succès "
                                      "(dates traitées et leur état)"), style="Carte.TCheckbutton",
                        variable=self._var("courriel.envoyer_si_succes", bool(c.get("envoyer_si_succes", True)),
                                           tk.BooleanVar)).grid(row=6, column=1, sticky="w", pady=6)
        Bouton(envoi, "✉  " + t("Envoyer un courriel de test"), self.tester_courriel).grid(
            row=7, column=1, sticky="w", pady=(6, 8))
        self.sortie_courriel = self._sortie(envoi, 3)
        self.sortie_courriel.grid(row=8, column=0, columnspan=3, sticky="we")
        b = self.config_toml.get("boite_paiements", {})
        boite = self._carte(f, 3, t("Avis de paiement (lecture de la boîte)"), "3",
                            t("Boîte où arrivent les avis Interac de Desjardins : l'application les lit (sans les marquer "
                              "comme lus) pour enregistrer les paiements aux fournisseurs."))
        self._champ(boite, 0, t("Serveur (IMAP)"), "boite.serveur", b.get("serveur", "mail.marchemvogmbi.com"))
        self._champ(boite, 1, t("Adresse"), "boite.utilisateur", b.get("utilisateur", "contact@marchemvogmbi.com"))
        self._champ(boite, 2, t("Mot de passe"), "secret.boite", secret=coffre.BOITE_PAIEMENTS)
        self._champ(boite, 3, t("Lire les avis à partir du"), "boite.depuis", b.get("depuis", "2026-08-01"),
                    calendrier=True)
        fc = self.config_toml.get("factures_courriel", {})
        factures = self._carte(f, 4, t("Factures fournisseurs reçues par courriel"), "4",
                               t("Les factures (PDF ou photos) jointes aux courriels de cette même boîte sont copiées "
                                 "dans « Fournisseur > Factures fournisseurs », puis lues. Lecture seule : aucun courriel "
                                 "n'est marqué comme lu, déplacé ni supprimé ; chaque pièce jointe n'est prise "
                                 "qu'une fois."))
        self._champ(factures, 0, t("Expéditeurs des factures"), "fc.expediteurs", fc.get("expediteurs", ""),
                    aide=t("Adresses ou domaines séparés par des virgules (ex. factures@fournisseur.com, "
                           "grossiste.ca). Vide : tout courriel dont le sujet ou la pièce jointe parle de facture."))
        self._champ(factures, 2, t("Textes dans le courriel"), "fc.textes", fc.get("textes", ""),
                    aide=t("Textes séparés par des points-virgules (ex. 11983938 Canada Inc Brisk) : les pièces "
                           "jointes de tout courriel qui contient l'un d'eux (sujet, expéditeur, message ou nom du "
                           "fichier) sont prises."))
        self._champ(factures, 4, t("Lire les factures à partir du"), "fc.depuis",
                    fc.get("depuis", b.get("depuis", "2026-08-01")), calendrier=True)
        ttk.Checkbutton(factures, text=t("Les relever aussi pendant le traitement de nuit"), style="Carte.TCheckbutton",
                        variable=self._var("fc.automatique", bool(fc.get("automatique", True)), tk.BooleanVar)).grid(
            row=5, column=1, sticky="w", pady=6)

    def _onglet_automatisation(self) -> None:
        a = self.config_toml.get("automatique", {})
        f = self._cadre(t("4. Automatisation"), "⏰")
        self._titre(f, t("Traitement automatique quotidien"))
        tache = self._carte(f, 1, t("Tâche planifiée"), "1")
        self._champ(tache, 0, t("Heure du traitement"), "auto.heure", a.get("heure", "01:00"),
                    aide=t("HH:MM. L'ordinateur doit être allumé et la session Windows ouverte ; Sage peut être fermé."))
        boutons = tk.Frame(tache, background=CARTE)
        boutons.grid(row=2, column=1, sticky="w", pady=(6, 8))
        Bouton(boutons, "⏰  " + t("Installer la tâche planifiée"), self.installer_tache).pack(side="left")
        Bouton(boutons, t("Retirer la tâche"), self.retirer_tache, "danger").pack(side="left", padx=8)
        Bouton(boutons, t("État de la tâche"), self.etat_tache, "secondaire").pack(side="left")
        self.sortie_auto = self._sortie(tache, 6)
        self.sortie_auto.grid(row=3, column=0, columnspan=3, sticky="we")
        outils = self._carte(f, 2, t("Outils"), "2", couleur=JAUNE)
        ligne = tk.Frame(outils, background=CARTE)
        ligne.grid(row=0, column=0, columnspan=3, sticky="w")
        Bouton(ligne, t("Créer un raccourci sur le Bureau"), self.raccourci, "secondaire").pack(side="left")
        Bouton(ligne, t("Reprendre une configuration existante…"), self.reprendre, "secondaire").pack(side="left",
                                                                                                    padx=8)
        tk.Label(outils, text=t("Copie config.toml, la correspondance des articles et les articles à relier depuis un "
                                "autre dossier (ex. le dossier du projet). Les mots de passe restent dans le coffre-fort."),
                 font=("Segoe UI", 9), foreground=TEXTE_DOUX, background=CARTE, wraplength=640,
                 justify="left").grid(row=1, column=0, columnspan=3, sticky="w", pady=(6, 0))

    def _onglet_correspondance(self) -> None:
        from .page_correspondance import PageCorrespondance

        self.page_correspondance = PageCorrespondance(self.onglets, self.racine, TITRE, self.points_visibles)
        self.onglets.add(self.page_correspondance, text=t("5. Correspondance des articles"))
        self._pages.append(("🔗", t("5. Correspondance")))

    def _onglet_encaissements(self) -> None:
        from .page_encaissements import PageEncaissements

        self.page_encaissements = PageEncaissements(self.onglets, self.racine, TITRE, self.chemin_config,
                                                    self.points_visibles)
        self.onglets.add(self.page_encaissements, text=t("7. Encaissements"))
        self._pages.append(("💰", t("7. Encaissements")))

    def _onglet_fournisseurs(self) -> None:
        from .page_fournisseurs import PageFournisseurs

        self.page_fournisseurs = PageFournisseurs(self.onglets, self.racine, TITRE)
        self.onglets.add(self.page_fournisseurs, text=t("8. Factures fournisseurs"))
        self._pages.append(("🧾", t("8. Factures fournisseurs")))

    def _onglet_utilisateurs(self) -> None:
        from .page_utilisateurs import PageUtilisateurs
        from .utilisateurs import PAGES

        libelles = {cle: titre for cle, (_, titre) in zip(PAGES, self._pages)}
        self.page_utilisateurs = PageUtilisateurs(self.onglets, self.racine, TITRE, libelles,
                                                  self.session.nom if self.session else "")
        self.onglets.add(self.page_utilisateurs, text=t("Utilisateurs"))
        self._pages.append(("👥", t("Utilisateurs")))

    def _onglet_paiements(self) -> None:
        from .page_paiements import PagePaiements

        self.page_paiements = PagePaiements(self.onglets, self.racine, TITRE, self.vars.get("boite.depuis"),
                                            self._enregistrer_depuis_boite)
        self.onglets.add(self.page_paiements, text=t("9. Paiements fournisseurs"))
        self._pages.append(("💸", t("9. Paiements fournisseurs")))

    def _onglet_rapprochement(self) -> None:
        from .page_rapprochement import PageRapprochement

        self.page_rapprochement = PageRapprochement(self.onglets, self.racine, TITRE, self._vers_page_manuelle)
        self.onglets.add(self.page_rapprochement, text=t("10. Rapprochement bancaire"))
        self._pages.append(("🏦", t("10. Rapprochement")))

    def _onglet_rapports(self) -> None:
        from .page_rapports import PageRapports

        self.page_rapports = PageRapports(self.onglets, self.racine, TITRE)
        self.onglets.add(self.page_rapports, text=t("11. Rapports"))
        self._pages.append(("📊", t("11. Rapports")))

    def _vers_page_manuelle(self, cle: str) -> None:
        """Après un encaissement ou un paiement fournisseur manuel noté à la page 10 : page 7 ou 9, relue."""
        if cle == "paiements" and self.permis(PAIEMENTS):
            self.page_paiements._recharger()
            self.aller(PAIEMENTS)
        elif cle == "encaissements" and self.permis(ENCAISSEMENTS):
            self.aller(ENCAISSEMENTS)

    def _enregistrer_depuis_boite(self, depuis: str) -> None:
        """Date de lecture des avis changée sur la page 9 : même réglage que la page Courriel."""
        self.config_toml.setdefault("boite_paiements", {})["depuis"] = depuis
        ecrire_config(self.chemin_config, self.config_toml)

    def _onglet_tableau(self) -> None:
        f = self._cadre(t("6. Tableau de bord"), "📊")
        self._titre(f, t("6. Tableau de bord")[3:])
        self.cartes = tk.Frame(f, background=fond_de(f))
        self.cartes.grid(row=1, column=0, columnspan=3, sticky="we", pady=(0, 14))
        # point de vente à traiter : un seul, ou tous ceux du profil à la suite (chacun dans son dépôt Sage)
        ligne_pdv = ttk.Frame(f)
        ligne_pdv.grid(row=2, column=0, columnspan=3, sticky="w", pady=(0, 10))
        ttk.Label(ligne_pdv, text=t("Point de vente :")).pack(side="left")
        self.point_vente = tk.StringVar(value=t("Tous les points de vente"))
        choix = ttk.Combobox(ligne_pdv, textvariable=self.point_vente, state="readonly", width=30,
                             postcommand=lambda: choix.configure(values=self._choix_points_vente()))
        choix.configure(values=self._choix_points_vente())
        choix.pack(side="left", padx=(6, 0))
        haut = ttk.Frame(f)
        haut.grid(row=3, column=0, columnspan=3, sticky="we")
        Bouton(haut, "▶  " + t("Lancer maintenant"),
               lambda: action_permise(self, "Lancer le traitement maintenant") and self.lancer(False)).pack(side="left")
        Bouton(haut, "🧪  " + t("Simulation (sans import)"), lambda: self.lancer(True), "accent").pack(side="left", padx=8)
        if export_tableau.export_permis():
            Bouton(haut, "📗  Excel", lambda: self.ouvrir(self.racine / "donnees" / "correspondance_articles.xlsx"),
                   "secondaire").pack(side="left")
        Bouton(haut, "📁  " + t("Dossier des données"), lambda: self.ouvrir(self.racine / "donnees"),
               "secondaire").pack(side="left", padx=8)
        # « article Sage sans compte de produits » bloque l'import : correction dans Sage depuis ici
        Bouton(haut, "🧾  " + t("Corriger les comptes dans Sage…"), self.corriger_comptes_sage, "secondaire").pack(
            side="left")
        Bouton(haut, "⟳", self.actualiser_tableau, "secondaire", largeur=40).pack(side="right")
        # point de vente à traiter : un seul, ou tous à la suite (chacun dans son dépôt Sage)
        # une date ou une période choisie (rattrapage) au lieu de « dernière facture de Sage jusqu'à hier »
        periode = ttk.Frame(f)
        periode.grid(row=4, column=0, columnspan=3, sticky="we", pady=(12, 0))
        hier = (date.today() - timedelta(days=1)).isoformat()
        self.periode_du, self.periode_au = tk.StringVar(value=hier), tk.StringVar(value=hier)
        ttk.Label(periode, text=t("Charger une date ou une période : du")).pack(side="left")
        ChampDate(periode, self.periode_du).pack(side="left", padx=4)
        ttk.Label(periode, text=t("au")).pack(side="left")
        ChampDate(periode, self.periode_au).pack(side="left", padx=4)
        Bouton(periode, "📥  " + t("Charger la période"), self.charger_periode, "secondaire").pack(side="left", padx=8)
        self.sortie_tableau = self._sortie(f, 18)
        self.sortie_tableau.grid(row=5, column=0, columnspan=3, sticky="we", pady=(14, 0))

    # ---------------------------------------------------------------- actions
    def enregistrer(self) -> bool:
        v = {k: var.get() for k, var in self.vars.items()}
        heure = str(v["auto.heure"]).strip()
        try:
            date.fromisoformat(str(v["auto.date_depart"]).strip())
            date.fromisoformat(str(v["enc.depart"]).strip())
            date.fromisoformat(str(v["fc.depuis"]).strip())
            h, m = heure.split(":")
            assert 0 <= int(h) < 24 and 0 <= int(m) < 60
            int(str(v["courriel.port"]).strip() or 587)
        except (ValueError, AssertionError):
            messagebox.showerror(TITRE, t("Vérifiez la date (AAAA-MM-JJ), l'heure (HH:MM) et le port du courriel."))
            return False
        from .courriel import adresses, adresses_invalides

        invalides = adresses_invalides(v["courriel.destinataires"]) + adresses_invalides(v["courriel.copie"])
        if invalides:
            messagebox.showerror(TITRE, t("Adresse(s) courriel invalide(s) : {liste}", liste=", ".join(invalides)))
            return False
        c = self.config_toml
        c.setdefault("clover", {}).update(merchant_id=str(v["clover.merchant_id"]).strip())
        c["clover"].setdefault("base_url", "https://api.clover.com")
        c["clover"].pop("api_token", None)
        c.setdefault("general", {}).setdefault("fuseau_horaire", "America/Toronto")
        c["general"]["langue"] = langues.courante()
        fichier = str(v["sage.fichier"]).strip()
        c.setdefault("sage_base", {}).update(utilisateur=str(v["sage.utilisateur"]).strip(), fichier_entreprise=fichier)
        c["sage_base"].pop("mot_de_passe", None)
        c["sage_base"].setdefault("port", 13540)
        c.setdefault("sage_import", {}).update(fichier_entreprise=fichier)
        for cle, defaut in (("version", "12001"), ("pays", "1"), ("position_numero", 3)):
            c["sage_import"].setdefault(cle, defaut)
        c.setdefault("automatique", {}).update(date_depart=str(v["auto.date_depart"]).strip(), heure=heure)
        c["automatique"].setdefault("delai_import", 3600)
        c.setdefault("encaissements", {})["compte_depot"] = str(v["enc.compte"]).strip() or "1055"
        c["encaissements"]["date_depart"] = str(v["enc.depart"]).strip() or date.today().isoformat()
        c["encaissements"].setdefault("mode", "Comptant")
        c["encaissements"].setdefault("automatique", True)
        c.setdefault("courriel", {}).update(
            serveur=str(v["courriel.serveur"]).strip(), port=int(str(v["courriel.port"]).strip() or 587),
            securite=v["courriel.securite"], utilisateur=str(v["courriel.utilisateur"]).strip(),
            expediteur=str(v["courriel.expediteur"]).strip(),
            destinataires=", ".join(adresses(v["courriel.destinataires"])), copie=", ".join(adresses(v["courriel.copie"])),
            envoyer_si_succes=bool(v["courriel.envoyer_si_succes"]))
        c.setdefault("boite_paiements", {}).update(
            serveur=str(v["boite.serveur"]).strip(), utilisateur=str(v["boite.utilisateur"]).strip(),
            depuis=str(v["boite.depuis"]).strip() or "2026-08-01")
        c.setdefault("factures_courriel", {}).update(
            expediteurs=", ".join(e.strip() for e in str(v["fc.expediteurs"]).replace(";", ",").split(",") if e.strip()),
            textes="; ".join(x.strip() for x in str(v["fc.textes"]).split(";") if x.strip()),
            depuis=str(v["fc.depuis"]).strip() or str(v["boite.depuis"]).strip() or "2026-08-01",
            automatique=bool(v["fc.automatique"]))
        c["boite_paiements"].setdefault("port", 993)
        for cle_var, cle_coffre in (("secret.clover", coffre.CLOVER_JETON), ("secret.sage_lecture", coffre.SAGE_LECTURE),
                                    ("secret.sage_import", coffre.SAGE_IMPORT), ("secret.courriel", coffre.COURRIEL),
                                    ("secret.boite", coffre.BOITE_PAIEMENTS)):
            valeur = str(v[cle_var])
            if valeur.startswith(MASQUE):  # tapé à la suite du masque : seul l'ajout est le mot de passe
                valeur = valeur[len(MASQUE):]
            if valeur:
                coffre.ecrire(cle_coffre, valeur)
                self.vars[cle_var].set(MASQUE)
        ecrire_config(self.chemin_config, c)
        self.etat.config(text=t("Configuration enregistrée."))
        self._maj_etapes()
        return True

    def tester_clover(self) -> None:
        if not self.enregistrer():
            return

        def test():
            from .__main__ import charger_config
            from .api_clover import ClientClover

            client = ClientClover(charger_config(self.chemin_config))
            return t("connecté à « {nom} »", nom=client.marchand().get("name", "?"))

        self._tache(t("Test Clover"), test, self.sortie_clover)

    def tester_sage(self) -> None:
        if not self.enregistrer():
            return

        def test():
            from .__main__ import executable_import, ouvrir_base_sage
            from .automatique import lire_etat_sage
            from .facture import CLIENT
            from .sage_auto import lire_pendant_connexion

            config = lire_config(self.chemin_config)
            fichier = Path(config["sage_import"]["fichier_entreprise"])
            if not fichier.is_file():
                raise RuntimeError(t("fichier introuvable : {fichier}", fichier=fichier))

            def lecture():
                with ouvrir_base_sage(config, fichier) as base:
                    return lire_etat_sage(base, CLIENT)

            try:
                etat = lecture()
                mode = t("Sage ouvert")
            except PermissionError:
                raise
            except Exception:
                exe = executable_import()
                if not exe:
                    raise RuntimeError("Sage_SA_import.exe ?")
                etat = lire_pendant_connexion(exe, fichier, lecture)
                mode = t("Sage fermé : base ouverte puis refermée automatiquement")
            client = "OK" if etat.client_configure else t(
                "À RÉGLER : cocher « Ce client utilise mes n° articles » dans la fiche du client")
            sans_compte = sum(1 for a in etat.articles if not a.compte_revenus and a.type == "Inventory")
            return t("{mode}. {n} articles. Dernière facture journalière : {derniere}. Client « {client} » : {etat}. "
                     "Articles sans compte de produits : {sans}.", mode=mode, n=len(etat.articles),
                     derniere=etat.derniere_date or t("aucune"), client=CLIENT, etat=client, sans=sans_compte)

        self._tache(t("Test Sage"), test, self.sortie_sage)

    def tester_courriel(self) -> None:
        if not self.enregistrer():
            return

        def test():
            from .courriel import envoyer

            envoyer(lire_config(self.chemin_config), t("MVOGMBI_Sync : courriel de test"),
                    t("Ce courriel confirme que les alertes de MVOGMBI_Sync sont bien configurées."))
            return t("courriel envoyé")

        self._tache(t("Courriel de test"), test, self.sortie_courriel)

    def installer_tache(self) -> None:
        if not self.enregistrer():
            return
        from . import planification

        heure = str(self.vars["auto.heure"].get()).strip()
        self._tache(t("Installation de la tâche"), lambda: planification.installer(self.racine, heure), self.sortie_auto)

    def retirer_tache(self) -> None:
        from . import planification

        if messagebox.askyesno(TITRE, t("Retirer la tâche planifiée ? Les ventes ne seront plus importées automatiquement.")):
            self._tache(t("Retrait de la tâche"), planification.retirer, self.sortie_auto)

    def etat_tache(self) -> None:
        from . import planification

        self._tache(t("État de la tâche"), planification.etat, self.sortie_auto)

    def raccourci(self) -> None:
        bureau = Path(os.environ.get("USERPROFILE", "~")).expanduser() / "Desktop"
        cible = (str(Path(sys.executable).resolve()) if getattr(sys, "frozen", False)
                 else str(Path(sys.executable).with_name("pythonw.exe")))
        arguments = "" if getattr(sys, "frozen", False) else "-m mvogmbi_sync interface"
        script = (f'$s=(New-Object -ComObject WScript.Shell).CreateShortcut("{bureau / "MVOGMBI_Sync.lnk"}");'
                  f'$s.TargetPath="{cible}";$s.Arguments="{arguments}";$s.WorkingDirectory="{self.racine}";$s.Save()')
        self._tache(t("Raccourci sur le Bureau"),
                    lambda: subprocess.run(["powershell", "-NoProfile", "-Command", script], check=True) and t("créé"),
                    self.sortie_auto)

    def reprendre(self) -> None:
        import shutil

        dossier = filedialog.askdirectory(title=t("Dossier contenant config.toml (et le sous-dossier donnees)"))
        if not dossier:
            return
        source = Path(dossier)
        copies = []
        if (source / "config.toml").exists():
            ancienne = lire_config(source / "config.toml")
            # Secrets encore en clair dans l'ancienne configuration : transférés dans le coffre-fort
            jeton = ancienne.get("clover", {}).pop("api_token", "")
            mdp = ancienne.get("sage_base", {}).pop("mot_de_passe", "")
            if jeton and not coffre.present(coffre.CLOVER_JETON):
                coffre.ecrire(coffre.CLOVER_JETON, jeton)
            if mdp and not coffre.present(coffre.SAGE_LECTURE):
                coffre.ecrire(coffre.SAGE_LECTURE, mdp)
            ecrire_config(self.chemin_config, ancienne)
            copies.append("config.toml")
        for nom in ("correspondance_articles.xlsx", "articles_a_relier.csv", "journal_imports.csv", "articles_sage.csv"):
            if (source / "donnees" / nom).exists():
                (self.racine / "donnees").mkdir(parents=True, exist_ok=True)
                shutil.copy2(source / "donnees" / nom, self.racine / "donnees" / nom)
                copies.append(nom)
        if not copies:
            messagebox.showwarning(TITRE, t("Aucun fichier de configuration trouvé dans ce dossier."))
            return
        messagebox.showinfo(TITRE, t("Repris : {fichiers}.\nL'application va se fermer : rouvrez-la.",
                                     fichiers=", ".join(copies)))
        self.destroy()

    def charger_periode(self) -> None:
        """Importe les factures de la date ou de la période choisie (jours déjà dans Sage sautés ; vendredi à
        dimanche : une seule facture)."""
        try:
            du, au = date.fromisoformat(self.periode_du.get().strip()), date.fromisoformat(self.periode_au.get().strip())
            assert du <= au < date.today()
        except (ValueError, AssertionError):
            messagebox.showerror(TITRE, t("Vérifiez les dates (AAAA-MM-JJ) : du ≤ au, au plus tard hier."))
            return
        if not messagebox.askyesno(TITRE, t("Charger dans Sage les ventes du {du} au {au} ? Les jours déjà facturés "
                                            "sont sautés ; vendredi, samedi et dimanche forment une seule facture.",
                                            du=du, au=au)):
            return
        self.lancer(False, depuis=du, jusqua=au, confirme=True)

    def points_visibles(self) -> list:
        """Points de vente actifs que le profil de la personne connectée peut traiter."""
        from .points_vente import permis

        return permis(self.config_toml, self.points_permis)

    def _choix_points_vente(self) -> list[str]:
        return [t("Tous les points de vente")] + [p.libelle for p in self.points_visibles()]

    def _code_point_vente(self) -> str:
        """Point de vente choisi au Tableau de bord ; « Tous » = tous ceux du profil (« tous » s'il n'a pas de
        restriction, sinon leurs codes « 1,3 »)."""
        from .points_vente import TOUS

        choix = self.point_vente.get() if hasattr(self, "point_vente") else ""
        if " — " in choix:
            return choix.split(" — ")[0]
        return TOUS if self.points_permis is None else ",".join(p.code for p in self.points_visibles())

    def lancer(self, simulation: bool, depuis: date | None = None, jusqua: date | None = None,
               confirme: bool = False) -> None:
        if not self.enregistrer():
            return
        if not simulation and not confirme and not messagebox.askyesno(
                TITRE, t("Lancer le traitement maintenant ? Les factures manquantes seront importées dans Sage.")):
            return
        zone = self.sortie_tableau
        zone.delete("1.0", "end")
        code = self._code_point_vente()
        if not code:
            messagebox.showwarning(TITRE, t("Aucun point de vente actif n'est permis à votre profil."))
            return

        def traitement():
            from .__main__ import commande_moteur, fermer_bases

            fermer_bases()  # base gardée par cette fenêtre relâchée : le traitement importe dans Sage
            commande = commande_moteur() + ["auto", "--point-de-vente", code]
            if simulation:
                commande.append("--simulation")
            if depuis:
                commande += ["--depuis", depuis.isoformat()]
            if jusqua:
                commande += ["--jusqua", jusqua.isoformat()]
            processus = subprocess.Popen(commande, cwd=self.racine, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                         text=True, encoding="utf-8", errors="replace",
                                         env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"},
                                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            for ligne in processus.stdout:
                self.file_messages.put((zone, ligne.rstrip()))
            return t("réussi") if processus.wait() == 0 else t("terminé avec des points à corriger (voir ci-dessus)")

        self._tache(t("Simulation") if simulation else t("Traitement"), traitement, zone)

    def ouvrir(self, chemin: Path) -> None:
        if chemin.exists():
            os.startfile(chemin)
        else:
            messagebox.showinfo(TITRE, t("Introuvable pour l'instant : {chemin}", chemin=chemin))

    def actualiser_tableau(self) -> None:
        from . import planification

        try:
            self._tache_installee = "non installée" not in planification.etat()
            tache = t("installée") if self._tache_installee else t("NON installée")
        except Exception:
            tache = "?"
        derniere = self._etat_etapes()[TABLEAU][1] or t("aucune")
        problemes = 0
        journal_auto = self.racine / "donnees" / "journal_automatique.log"
        if journal_auto.exists():
            execution = journal_auto.read_text(encoding="utf-8").split("===== ")[-1]
            problemes = execution.count("PROBLÈME") + execution.count("ERREUR")
        for enfant in self.cartes.winfo_children():
            enfant.destroy()
        for icone, titre, valeur, couleur in (
                ("🧾", t("Dernière facture importée"), derniere, VERT),
                ("⏰", t("Tâche planifiée"), tache, VERT if self._tache_installee else JAUNE),
                ("⚠", t("Points à corriger (dernier traitement)"), str(problemes), ROUGE if problemes else VERT)):
            carte = tk.Frame(self.cartes, background=CARTE, highlightthickness=1, highlightbackground=BORDURE)
            carte.pack(side="left", fill="x", expand=True, padx=(0, 12))
            tk.Frame(carte, height=4, background=couleur).pack(fill="x")
            ligne = tk.Frame(carte, background=CARTE)
            ligne.pack(fill="x", padx=14, pady=(10, 12))
            tk.Label(ligne, text=icone, font=("Segoe UI Emoji", 20), foreground=couleur, background=CARTE).pack(
                side="left", padx=(0, 12))
            textes = tk.Frame(ligne, background=CARTE)
            textes.pack(side="left", fill="x")
            tk.Label(textes, text=titre, font=("Segoe UI", 9), foreground=TEXTE_DOUX, background=CARTE,
                     anchor="w").pack(fill="x")
            tk.Label(textes, text=valeur, font=("Segoe UI Semibold", 15), foreground=TEXTE, background=CARTE,
                     anchor="w").pack(fill="x")
        if journal_auto.exists() and not self.sortie_tableau.get("1.0", "end").strip():
            for ligne in journal_auto.read_text(encoding="utf-8").splitlines()[-60:]:
                self._ecrire(self.sortie_tableau, ligne)
            self.sortie_tableau.see("end")
        self._maj_etapes()


def lancer_interface(racine: Path) -> None:
    (racine / "donnees").mkdir(parents=True, exist_ok=True)
    try:  # affichage net sur les écrans à mise à l'échelle (125 %, 150 %…)
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
        # identité propre dans la barre des tâches (sinon l'icône générique de Python ou de Windows)
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(ID_APPLICATION)
    except Exception:
        pass
    from .connexion import connecter

    session = None
    while True:  # un changement de langue reconstruit la fenêtre ; une déconnexion revient à la connexion
        if session is None:
            langues.depuis_config(lire_config(racine / "config.toml"))
            session = connecter(racine, TITRE)
            if session is None:
                break
        application = Application(racine, session)
        application.mainloop()
        if application.deconnecter:
            session = None
        elif not application.relancer:
            break
