"""Page « Correspondance des articles » de l'application : consulter, filtrer et corriger Clover -> Sage."""

from __future__ import annotations

import shutil
import subprocess
import threading
import tkinter as tk
from collections import Counter
from datetime import datetime
from pathlib import Path
from tkinter import messagebox, ttk

from rapidfuzz import fuzz, process

from .articles_sage import lire_copie
from .design import Bouton, Rangee, cadre_tableau, entete_page, rayer
from .export_tableau import bouton_exporter, rendre_exportable
from .langues import t
from .correspondance import (AUCUN, AUTOMATIQUE, A_CONFIRMER, CONFIRME, PERSONNALISE, RENOMME, conflit_format,
                             ecrire_correspondance, lire_correspondances, normaliser)

SUPPRIMES = "Supprimés ou renommés dans Clover"
FILTRES = ["À traiter (À confirmer + Aucun)", SUPPRIMES, "Tous", CONFIRME, AUTOMATIQUE, A_CONFIRMER,
           AUCUN]  # valeurs internes
COLONNES = [("statut", "Statut", 95), ("nom", "Article Clover", 290), ("categorie", "Catégorie", 130),
            ("ventes", "Ventes 30 j", 80), ("numero", "N° article Sage", 120), ("description", "Description Sage", 290)]
COULEURS = {CONFIRME: "#e6f4ea", A_CONFIRMER: "#fff4cc", AUCUN: "#fbe0de"}  # « Automatique » : lignes rayées


class PageCorrespondance(ttk.Frame):
    def __init__(self, parent, racine: Path, titre: str, points_vente=None):
        """`points_vente` : fonction -> points de vente visibles (chacun a sa correspondance) ; None = le n° 1."""
        super().__init__(parent, padding=10)
        self.racine, self.titre = racine, titre
        self.chemin = racine / "donnees" / "correspondance_articles.xlsx"
        self.lignes = []
        self.par_id = {}
        self.modifie = False
        self.articles_sage = []
        self.choix_sage = []

        entete_page(self, "🔗", t("Correspondance des articles"),
                    t("chaque article Clover relié à son article Sage")).pack(fill="x")
        barre = Rangee(self)  # passe à la ligne si la fenêtre est étroite : tous les boutons restent visibles
        barre.pack(fill="x")
        self.choix_pdv = None
        if points_vente is not None:
            from .page_points_vente import ChoixPointVente

            self.choix_pdv = ChoixPointVente(self, points_vente, self._changer_point_vente)
            self.choix_pdv.pack(anchor="w", pady=(0, 8), before=barre)
            self._chemin_du_point_vente()
        groupe = barre.ajouter(barre.groupe(), 10)
        ttk.Label(groupe, text=t("Afficher :")).pack(side="left")
        self.libelles_filtres = {t(f): f for f in FILTRES}  # libellé affiché -> valeur interne
        self.filtre_affiche = tk.StringVar(value=t(FILTRES[0]))
        liste = ttk.Combobox(groupe, textvariable=self.filtre_affiche, values=list(self.libelles_filtres),
                             state="readonly", width=24)
        liste.pack(side="left", padx=(4, 0))
        liste.bind("<<ComboboxSelected>>", lambda _e: self.afficher())
        groupe = barre.ajouter(barre.groupe(), 12)
        ttk.Label(groupe, text=t("Rechercher :")).pack(side="left")
        self.recherche = tk.StringVar()
        champ = ttk.Entry(groupe, textvariable=self.recherche, width=20)
        champ.pack(side="left", padx=(4, 0))
        champ.bind("<KeyRelease>", lambda _e: self.afficher())
        barre.ajouter(Bouton(barre, "⟳  " + t("Mettre à jour depuis Clover et Sage"), self.mettre_a_jour))
        barre.ajouter(Bouton(barre, t("Recharger"), self.charger, "secondaire"))
        barre.ajouter(Bouton(barre, "🆕  " + t("Créer un article"), self.creer_article, "secondaire"))
        barre.ajouter(Bouton(barre, "📦  " + t("Inventaire"), self.inventaire, "secondaire"))
        barre.ajouter(Bouton(barre, "💲  " + t("Coûts Clover depuis Sage"), self.couts_clover, "secondaire"))
        barre.ajouter(Bouton(barre, "🧾  " + t("Comptes Sage par catégorie"), self.comptes_sage, "secondaire"))
        self.compteurs = ttk.Label(self, text="", foreground="#444", padding=(0, 6))
        self.compteurs.pack(fill="x")

        cadre = cadre_tableau(self)
        cadre.pack(fill="both", expand=True)
        self.tableau = ttk.Treeview(cadre, columns=[c[0] for c in COLONNES], show="headings", height=12,
                                    selectmode="browse")
        for cle, titre_col, largeur in COLONNES:
            self.tableau.heading(cle, text=t(titre_col))
            self.tableau.column(cle, width=largeur, anchor="e" if cle == "ventes" else "w", stretch=cle in ("nom", "description"))
        for statut, couleur in COULEURS.items():
            self.tableau.tag_configure(statut, background=couleur)
        defilement = ttk.Scrollbar(cadre, orient="vertical", command=self.tableau.yview)
        self.tableau.configure(yscrollcommand=defilement.set)
        defilement.pack(side="right", fill="y")  # avant le tableau : toujours visible, même s'il est large
        self.tableau.pack(side="left", fill="both", expand=True)
        self.tableau.bind("<<TreeviewSelect>>", lambda _e: self.selectionner())
        barre.ajouter(bouton_exporter(barre, self.tableau, t("Correspondance des articles")))

        edition = ttk.LabelFrame(self, text=t("Article sélectionné"), padding=8)
        edition.pack(fill="x", pady=(8, 0))
        self.info = ttk.Label(edition, text=t("Sélectionnez un article dans le tableau."), wraplength=780, justify="left")
        self.info.grid(row=0, column=0, columnspan=4, sticky="w")
        ttk.Label(edition, text=t("Chercher un article Sage :")).grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.recherche_sage = tk.StringVar()
        champ_sage = ttk.Entry(edition, textvariable=self.recherche_sage, width=40)
        champ_sage.grid(row=1, column=1, sticky="we", pady=(6, 0), padx=4)
        champ_sage.bind("<KeyRelease>", lambda _e: self.chercher_sage())
        self.resultats = tk.Listbox(edition, height=5, font=("Consolas", 9))
        self.resultats.grid(row=2, column=0, columnspan=2, sticky="we", pady=4)
        self.resultats.bind("<Double-Button-1>", lambda _e: self.confirmer())
        boutons = ttk.Frame(edition)
        boutons.grid(row=2, column=2, sticky="n", padx=8)
        largeur = 240
        Bouton(boutons, "✔  " + t("Confirmer l'article choisi"), self.confirmer, largeur=largeur).pack()
        Bouton(boutons, t("Accepter la proposition"), self.accepter, "secondaire", largeur=largeur).pack(pady=4)
        Bouton(boutons, t("Retirer la confirmation"), self.retirer, "danger", largeur=largeur).pack()
        Bouton(boutons, "🆕  " + t("Créer l'article dans Sage"), self.creer_dans_sage, "secondaire",
               largeur=largeur).pack(pady=(4, 0))
        Bouton(edition, "💾  " + t("Enregistrer les modifications"), self.enregistrer, "accent").grid(
            row=2, column=3, sticky="s")
        edition.columnconfigure(1, weight=1)
        self.charger()

    # ---------------------------------------------------------------- données
    def _chemin_du_point_vente(self) -> None:
        p = self.choix_pdv.courant if self.choix_pdv else None
        if p is not None:
            self.chemin = p.fichier(self.racine / "donnees", "correspondance_articles.xlsx")

    def _changer_point_vente(self) -> None:
        ancien = self.chemin
        self._chemin_du_point_vente()
        if self.chemin != ancien:
            if self.modifie and not messagebox.askyesno(self.titre, t("Abandonner les modifications non "
                                                                      "enregistrées ?")):
                self.chemin = ancien
                return
            self.modifie = False
            self.charger()

    def charger(self) -> None:
        if self.modifie and not messagebox.askyesno(self.titre, t("Abandonner les modifications non enregistrées ?")):
            return
        self.lignes = lire_correspondances(self.chemin)
        self.par_id = {c.id_clover: c for c in self.lignes}
        self.articles_sage = lire_copie(self.racine / "donnees" / "articles_sage.csv")
        self.normalises = [normaliser(f"{a.description} {a.numero}") for a in self.articles_sage]
        self.modifie = False
        self.afficher()

    def afficher(self) -> None:
        filtre = self.libelles_filtres.get(self.filtre_affiche.get(), FILTRES[0])
        texte = normaliser(self.recherche.get())
        self.tableau.delete(*self.tableau.get_children())
        visibles = 0
        for c in self.lignes:
            if filtre.startswith("À traiter") and c.statut not in (A_CONFIRMER, AUCUN):
                continue
            if filtre in (CONFIRME, AUTOMATIQUE, A_CONFIRMER, AUCUN) and c.statut != filtre:
                continue
            if filtre == SUPPRIMES and c.methode not in (RENOMME, PERSONNALISE):
                continue
            if texte and texte not in normaliser(f"{c.nom_clover} {c.numero_sage} {c.description_sage}"):
                continue
            nom = c.nom_clover + (t("  (supprimé de Clover)") if c.methode == RENOMME else "")
            self.tableau.insert("", "end", iid=c.id_clover, tags=(c.statut,), values=(
                t(c.statut), nom, c.categorie_clover, f"{c.ventes_30j:,.2f}" if c.ventes_30j else "",
                c.numero_sage, c.description_sage))
            visibles += 1
        rayer(self.tableau)
        compte = Counter(c.statut for c in self.lignes)
        self.compteurs.config(text=(
            t("{n} articles Clover — Confirmé : {c}   Automatique : {a}   À confirmer : {q}   Aucun : {z}   •   affichés : {v}",
              n=len(self.lignes), c=compte[CONFIRME], a=compte[AUTOMATIQUE], q=compte[A_CONFIRMER], z=compte[AUCUN],
              v=visibles)
            + (t("   •   MODIFICATIONS NON ENREGISTRÉES") if self.modifie else "")
            + ("" if self.articles_sage else t("   •   liste Sage absente : cliquez sur « Mettre à jour »"))))

    def courant(self):
        selection = self.tableau.selection()
        return self.par_id.get(selection[0]) if selection else None

    def selectionner(self) -> None:
        c = self.courant()
        if not c:
            return
        self.info.config(text=(
            t("Clover : {nom}   (catégorie {cat}, ID {id})\nSage : {num} {desc}   •   statut {statut}, méthode {methode}",
              nom=c.nom_clover, cat=c.categorie_clover or "—", id=c.id_clover, num=c.numero_sage or "—",
              desc=c.description_sage, statut=t(c.statut), methode=c.methode or "—")
            + (t("\nAutres suggestions : {s}", s=c.suggestions) if c.suggestions else "")))
        if c.methode == RENOMME and c.description_sage:  # ancien nom : chercher plutôt l'article Sage proposé
            self.recherche_sage.set(c.description_sage)
        else:
            self.recherche_sage.set(c.nom_clover)
        self.chercher_sage()

    def chercher_sage(self) -> None:
        self.resultats.delete(0, "end")
        self.choix_sage = []
        texte = normaliser(self.recherche_sage.get())
        if not texte or not self.articles_sage:
            return
        c = self.courant()
        for _, score, i in process.extract(texte, self.normalises, scorer=fuzz.token_set_ratio, limit=15):
            a = self.articles_sage[i]
            alerte = t("  (autre format)") if c and conflit_format(c.nom_clover, a.description) else ""
            self.choix_sage.append(a)
            self.resultats.insert("end", f"{a.numero:<16} {a.description}  [{a.compte_revenus or t('sans compte')}]{alerte}")

    # ---------------------------------------------------------------- modifications
    def _appliquer(self, c, statut: str, numero: str = "", description: str = "", compte: str = "") -> None:
        c.statut = statut
        if numero:
            c.numero_sage, c.description_sage, c.compte_revenus = numero, description, compte
        c.methode = "Manuel (application)"  # valeur enregistrée dans le fichier, non traduite
        self.modifie = True
        position = self.tableau.index(c.id_clover) if self.tableau.exists(c.id_clover) else None
        self.afficher()
        if self.tableau.exists(c.id_clover):
            self.tableau.selection_set(c.id_clover)
            self.tableau.see(c.id_clover)
        elif position is not None and self.tableau.get_children():
            enfants = self.tableau.get_children()
            suivant = enfants[min(position, len(enfants) - 1)]
            self.tableau.selection_set(suivant)
            self.tableau.see(suivant)

    def confirmer(self) -> None:
        c = self.courant()
        choix = self.resultats.curselection()
        if not c or not choix:
            messagebox.showinfo(self.titre, t("Sélectionnez un article dans le tableau, puis un article Sage dans la liste."))
            return
        a = self.choix_sage[choix[0]]
        if conflit_format(c.nom_clover, a.description) and not messagebox.askyesno(
                self.titre, t("« {a} » et « {b} » n'ont pas le même format.\nDeux formats différents sont deux "
                              "articles différents. Confirmer quand même ?", a=c.nom_clover, b=a.description)):
            return
        if not a.compte_revenus:
            messagebox.showwarning(self.titre, t("L'article Sage {num} n'a pas de compte de produits : l'import sera "
                                                 "bloqué tant qu'il n'est pas complété dans Sage.", num=a.numero))
        self._appliquer(c, CONFIRME, a.numero, a.description, a.compte_revenus)

    def accepter(self) -> None:
        c = self.courant()
        if not c or not c.numero_sage:
            messagebox.showinfo(self.titre, t("Aucune proposition pour cet article : choisissez un article Sage dans la liste."))
            return
        self._appliquer(c, CONFIRME)

    def retirer(self) -> None:
        c = self.courant()
        if c:
            self._appliquer(c, A_CONFIRMER)

    def comptes_sage(self) -> None:
        from .fenetre_article import FenetreCategories
        FenetreCategories(self, self.racine)

    def couts_clover(self) -> None:
        from .fenetre_couts import FenetreCoutsClover
        FenetreCoutsClover(self, self.racine)

    def inventaire(self) -> None:
        from .page_inventaire import FenetreInventaire
        FenetreInventaire(self, self.racine)

    def creer_article(self) -> None:
        """Nouvel article dans Clover et Sage (relié dans la correspondance, puis rechargée)."""
        from .fenetre_article import FenetreCreationArticle

        if self.modifie:
            messagebox.showinfo(self.titre, t("Enregistrez d'abord les modifications en cours."))
            return
        FenetreCreationArticle(self, self.racine, numeros_sage=[a.numero for a in self.articles_sage],
                               au_succes=lambda _a: self.charger())

    def creer_dans_sage(self) -> None:
        """L'article Clover choisi n'existe pas dans Sage : création de sa fiche Sage, puis liaison « Confirmé »."""
        from .fenetre_article import FenetreCreationArticle

        c = self.courant()
        if not c or c.id_clover.startswith("nom:"):
            messagebox.showinfo(self.titre, t("Sélectionnez dans le tableau l'article Clover à créer dans Sage."))
            return

        def cree(a) -> None:
            from .articles_sage import ArticleSage
            self.articles_sage.append(ArticleSage(a.numero_sage, a.description_sage, "Stock", a.comptes.produits))
            self.normalises.append(normaliser(f"{a.description_sage} {a.numero_sage}"))
            self._appliquer(c, CONFIRME, a.numero_sage, a.description_sage, a.comptes.produits)
            self.enregistrer()

        FenetreCreationArticle(self, self.racine, nom=c.nom_clover, categorie=c.categorie_clover,
                               numeros_sage=[a.numero for a in self.articles_sage], au_succes=cree,
                               id_clover=c.id_clover, relier=False)

    def enregistrer(self) -> None:
        if not self.modifie:
            messagebox.showinfo(self.titre, t("Aucune modification à enregistrer."))
            return
        try:
            if self.chemin.exists():
                copie = self.chemin.parent / "sauvegardes" / f"{self.chemin.stem}_{datetime.now():%Y%m%d-%H%M%S}.xlsx"
                copie.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(self.chemin, copie)
            ecrire_correspondance(self.lignes, self.chemin)
        except PermissionError:
            messagebox.showerror(self.titre, t("Le fichier de correspondance est ouvert dans Excel : fermez-le puis réessayez."))
            return
        self.modifie = False
        self.afficher()
        messagebox.showinfo(self.titre, t("Correspondance enregistrée (copie de sécurité de l'ancienne version faite)."))

    def mettre_a_jour(self) -> None:
        if self.modifie:
            messagebox.showinfo(self.titre, t("Enregistrez d'abord vos modifications."))
            return
        from .__main__ import commande_moteur

        self.compteurs.config(text=t("Mise à jour en cours (lecture de Clover et de Sage, quelques minutes)…"))

        def travail():
            p = self.choix_pdv.courant if self.choix_pdv else None
            r = subprocess.run(commande_moteur() + ["correspondance"] + (["--point-de-vente", p.code] if p else []),
                               cwd=self.racine, capture_output=True,
                               text=True, encoding="utf-8", errors="replace",
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            self.after(0, lambda: self._fin_mise_a_jour(r.returncode, (r.stdout + r.stderr).strip()))

        threading.Thread(target=travail, daemon=True).start()

    def _fin_mise_a_jour(self, code: int, sortie: str) -> None:
        self.charger()
        resume = "\n".join(sortie.splitlines()[-8:])
        if code == 0:
            messagebox.showinfo(self.titre, t("Correspondance mise à jour.\n\n{resume}", resume=resume))
        else:
            messagebox.showerror(self.titre, t("Mise à jour impossible.\n\n{resume}", resume=resume))
