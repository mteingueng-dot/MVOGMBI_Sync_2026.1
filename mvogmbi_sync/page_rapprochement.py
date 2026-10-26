"""Page « Rapprochement bancaire » : relevés PDF Desjardins (compte 1055) rapprochés des écritures de Sage."""

from __future__ import annotations

import shutil
import threading
import tkinter as tk
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .design import (CARTE, ROUGE, TEXTE_DOUX, VERT_FONCE, Bouton, ChampRecherche, cadre_tableau, entete_page,
                     fond_de, rayer)
from .langues import t
from .rapprochement import (A_SAISIR, CONFIRME, EN_CIRCULATION, IGNORE, RAPPROCHE, SAISI, RegistreReleves, comptes_sage,
                            ecrire_rapport, mouvements_sage, periode_des, rapprocher, resume, solde_sage)

ETATS = [A_SAISIR, CONFIRME, RAPPROCHE, SAISI, IGNORE]
COULEURS = {A_SAISIR: "#fff4d6", CONFIRME: "#e6f4ea", RAPPROCHE: None, SAISI: None, IGNORE: None}


def argent(valeur) -> str:
    return "" if valeur is None else f"{valeur:,.2f} $".replace(",", " ").replace(".", ",")


class PageRapprochement(ttk.Frame):
    def __init__(self, parent, racine: Path, titre: str):
        super().__init__(parent, padding=10)
        self.racine, self.titre = Path(racine), titre
        self.registre = RegistreReleves(self.racine)
        self.releves, self.banque, self.sage, self.comptes = [], [], [], []
        self.chiffres: dict = {}
        self.soldes = (None, None, None, None)
        self.mouvement = None

        entete_page(self, "🏦", t("Rapprochement bancaire"),
                    t("relevés Desjardins (compte 1055) rapprochés des écritures de Sage")).pack(fill="x")
        barre = ttk.Frame(self)
        barre.pack(fill="x")
        Bouton(barre, "📂  " + t("Charger des relevés…"), self.charger).pack(side="left")
        Bouton(barre, "🔄  " + t("Actualiser"), self.actualiser, "secondaire").pack(side="left", padx=8)
        Bouton(barre, "🗑  " + t("Supprimer le relevé"), self.supprimer, "danger").pack(side="left")
        Bouton(barre, "📗  " + t("Rapport Excel"), self.rapport, "secondaire").pack(side="right")
        self.resume = ttk.Label(self, text=t("Chargez un relevé PDF Desjardins, puis « Actualiser »."),
                                foreground=TEXTE_DOUX, padding=(0, 6))
        self.resume.pack(fill="x")

        # relevés chargés
        haut = cadre_tableau(self)
        haut.pack(fill="x")
        colonnes = (("fichier", "Relevé", 260), ("periode", "Période", 190), ("ouverture", "Solde d'ouverture", 130),
                    ("fermeture", "Solde de fermeture", 130), ("controle", "Contrôle", 320))
        self.liste = ttk.Treeview(haut, columns=[c[0] for c in colonnes], show="headings", height=3, selectmode="browse")
        for cle, titre_col, largeur in colonnes:
            self.liste.heading(cle, text=t(titre_col))
            self.liste.column(cle, width=largeur, anchor="e" if cle in ("ouverture", "fermeture") else "w",
                              stretch=cle in ("fichier", "controle"))
        self.liste.tag_configure("erreur", background="#fde2e4")
        self.liste.pack(fill="x")
        self.liste.bind("<Delete>", lambda _e: self.supprimer())

        # chiffres du rapprochement
        self.cartes = tk.Frame(self, background=fond_de(self))
        self.cartes.pack(fill="x", pady=8)
        self.valeurs = {}
        for cle, libelle in (("solde_banque", "Solde du relevé"), ("solde_sage", "Solde Sage (1055)"),
                             ("ecart", "Écart"), ("ecart_ouverture", "dont écart d'ouverture"),
                             ("non_explique", "Écart non expliqué")):
            carte = tk.Frame(self.cartes, background=CARTE, highlightthickness=1, highlightbackground="#e2e8e4")
            carte.pack(side="left", fill="x", expand=True, padx=(0, 8))
            tk.Label(carte, text=t(libelle), background=CARTE, foreground=TEXTE_DOUX, font=("Segoe UI", 9)).pack(
                anchor="w", padx=12, pady=(8, 0))
            self.valeurs[cle] = tk.Label(carte, text="—", background=CARTE, font=("Segoe UI Semibold", 13))
            self.valeurs[cle].pack(anchor="w", padx=12, pady=(0, 8))

        # mouvements : banque / écritures Sage non rapprochées
        filtre = ttk.Frame(self)
        filtre.pack(fill="x")
        ttk.Label(filtre, text=t("Afficher :")).pack(side="left")
        self.filtre = tk.StringVar(value=t("À traiter"))
        choix = ttk.Combobox(filtre, textvariable=self.filtre, state="readonly", width=30,
                             values=[t("À traiter"), t("Tous")] + [t(e) for e in ETATS] + [t(EN_CIRCULATION)])
        choix.pack(side="left", padx=4)
        choix.bind("<<ComboboxSelected>>", lambda _e: self.afficher())
        cadre = cadre_tableau(self)
        cadre.pack(fill="both", expand=True, pady=(6, 0))
        colonnes = (("date", "Date", 90), ("description", "Description", 330), ("entree", "Entrée", 110),
                    ("sortie", "Sortie", 110), ("etat", "État", 170), ("lien", "Sage / compte", 220))
        self.tableau = ttk.Treeview(cadre, columns=[c[0] for c in colonnes], show="headings", height=9,
                                    selectmode="browse")
        for cle, titre_col, largeur in colonnes:
            self.tableau.heading(cle, text=t(titre_col))
            self.tableau.column(cle, width=largeur, anchor="e" if cle in ("entree", "sortie") else "w",
                                stretch=cle in ("description", "lien"))
        for etat, couleur in COULEURS.items():
            self.tableau.tag_configure(etat, **({"background": couleur} if couleur else {"foreground": TEXTE_DOUX}))
        self.tableau.tag_configure(EN_CIRCULATION, background="#eaf2fb")
        defil = ttk.Scrollbar(cadre, orient="vertical", command=self.tableau.yview)
        self.tableau.configure(yscrollcommand=defil.set)
        self.tableau.pack(side="left", fill="both", expand=True)
        defil.pack(side="right", fill="y")
        self.tableau.bind("<<TreeviewSelect>>", lambda _e: self.choisir())

        # décision pour le mouvement choisi
        carte = tk.Frame(self, background=CARTE, highlightthickness=1, highlightbackground="#e2e8e4")
        carte.pack(fill="x", pady=(8, 0))
        self.info = tk.Label(carte, text=t("Sélectionnez un mouvement de banque."), background=CARTE, anchor="w",
                             justify="left", font=("Segoe UI", 10))
        self.info.pack(fill="x", padx=12, pady=(10, 4))
        ligne = tk.Frame(carte, background=CARTE)
        ligne.pack(fill="x", padx=12, pady=(0, 10))
        tk.Label(ligne, text=t("Compte Sage"), background=CARTE, font=("Segoe UI", 9)).pack(side="left", padx=(0, 6))
        self.compte = tk.StringVar()
        self.champ_compte = ChampRecherche(ligne, self.compte, [], largeur=40)
        self.champ_compte.pack(side="left")
        Bouton(ligne, "✔  " + t("Confirmer le compte"), self.confirmer, fond=CARTE).pack(side="left", padx=(12, 0))
        Bouton(ligne, t("Ignorer"), self.ignorer, "secondaire", fond=CARTE).pack(side="left", padx=6)
        Bouton(ligne, t("Remettre à traiter"), self.remettre, "secondaire", fond=CARTE).pack(side="left")
        self.remarque = tk.Label(carte, text="", background=CARTE, foreground=ROUGE, font=("Segoe UI", 9), anchor="w")
        self.remarque.pack(fill="x", padx=12, pady=(0, 8))
        self.afficher_releves()

    # ---------------------------------------------------------------- configuration
    def _config(self) -> dict:
        import tomllib
        chemin = self.racine / "config.toml"
        return tomllib.loads(chemin.read_text(encoding="utf-8")) if chemin.exists() else {}

    # ---------------------------------------------------------------- relevés
    def charger(self) -> None:
        fichiers = filedialog.askopenfilenames(parent=self, title=t("Relevés de compte Desjardins (PDF)"),
                                               filetypes=[("PDF", "*.pdf")])
        if not fichiers:
            return
        self.registre.dossier.mkdir(parents=True, exist_ok=True)
        for f in fichiers:
            cible = self.registre.dossier / Path(f).name
            if Path(f).resolve() != cible.resolve():
                shutil.copy2(f, cible)
        self.actualiser()

    def supprimer(self) -> None:
        choix = self.liste.selection()
        if not choix:
            messagebox.showinfo(self.titre, t("Sélectionnez le relevé à supprimer dans la liste du haut."))
            return
        fichier = self.liste.item(choix[0], "values")[0]
        if not messagebox.askyesno(self.titre, t("Retirer le relevé « {f} » du rapprochement ? (le fichier est mis "
                                                 "de côté dans « supprimes »)", f=fichier)):
            return
        self.registre.supprimer(fichier)
        self.registre.enregistrer()
        self.actualiser()

    def afficher_releves(self) -> None:
        self.liste.delete(*self.liste.get_children())
        if not self.releves:
            for chemin in self.registre.fichiers():
                self.liste.insert("", "end", values=(chemin.name, "", "", "", t("cliquez sur « Actualiser »")))
            return
        for r in self.releves:
            problemes = r.controles()
            self.liste.insert("", "end", tags=("erreur",) if problemes else (), values=(
                r.fichier, f"{r.debut} → {r.fin}", argent(r.solde_ouverture), argent(r.solde_fermeture),
                "; ".join(problemes) or "✔ " + t("relevé complet et cohérent")))
        rayer(self.liste)

    # ---------------------------------------------------------------- lecture et rapprochement
    def actualiser(self) -> None:
        self.resume.configure(text=t("Lecture des relevés et des écritures du compte 1055 dans Sage…"))

        def travail():
            try:
                from .__main__ import lire_sage

                self.registre = RegistreReleves(self.racine)
                releves = self.registre.lire()
                periode = periode_des(releves)
                config = self._config()
                fichier = config.get("sage_import", {}).get("fichier_entreprise")
                if periode:
                    sage, solde, ouverture, comptes = lire_sage(config, lambda base: (
                        mouvements_sage(base, periode[0], periode[1]), solde_sage(base, periode[1]),
                        solde_sage(base, periode[0] - timedelta(days=1)), comptes_sage(base)), fichier)
                else:
                    sage, solde, ouverture, comptes = [], None, None, []
                self.after(0, lambda: self._fin_lecture(releves, sage, solde, ouverture, comptes, periode))
            except Exception as exc:
                message = str(exc)
                self.after(0, lambda: self.resume.configure(text="✘ " + message))

        threading.Thread(target=travail, daemon=True).start()

    def _fin_lecture(self, releves, sage, solde, ouverture_sage, comptes, periode) -> None:
        self.releves, self.sage, self.comptes, self.periode = releves, sage, comptes, periode
        self.banque = [m for r in releves for m in r.mouvements]
        rapprocher(self.banque, self.sage)
        fins = [r for r in releves if r.solde_fermeture is not None and r.fin]
        solde_banque = max(fins, key=lambda r: r.fin).solde_fermeture if fins else None
        debuts = [r for r in releves if r.solde_ouverture is not None and r.debut]
        ouverture_banque = min(debuts, key=lambda r: r.debut).solde_ouverture if debuts else None
        self.soldes = (solde_banque, solde, ouverture_banque, ouverture_sage)
        self.chiffres = resume(self.banque, self.sage, *self.soldes)
        self.champ_compte.configurer_valeurs(comptes)
        self.afficher_releves()
        self.afficher()

    def afficher(self) -> None:
        for cle, etiquette in self.valeurs.items():
            valeur = self.chiffres.get(cle)
            couleur = ROUGE if cle in ("ecart", "non_explique") and valeur not in (None, Decimal(0)) else VERT_FONCE
            etiquette.configure(text=argent(valeur) if valeur is not None else "—", foreground=couleur)
        choix = self.filtre.get()
        self.tableau.delete(*self.tableau.get_children())
        if choix != t(EN_CIRCULATION):
            for i, m in enumerate(self.banque):
                if choix == t("À traiter") and m.etat not in (A_SAISIR, CONFIRME):
                    continue
                if choix not in (t("À traiter"), t("Tous")) and t(m.etat) != choix:
                    continue
                lien = (", ".join(f"n° {n}" for n in m.sage) if m.sage else m.compte)
                self.tableau.insert("", "end", iid=f"b{i}", tags=(m.etat,), values=(
                    m.date, m.description, argent(m.montant) if m.montant > 0 else "",
                    argent(-m.montant) if m.montant < 0 else "", t(m.etat), lien))
        if choix in (t(EN_CIRCULATION), t("À traiter"), t("Tous")):
            for i, s in enumerate(self.sage):
                if s.rapproche:
                    continue
                self.tableau.insert("", "end", iid=f"s{i}", tags=(EN_CIRCULATION,), values=(
                    s.date, f"{s.description}  [{s.source}]", argent(s.montant) if s.montant > 0 else "",
                    argent(-s.montant) if s.montant < 0 else "", t(EN_CIRCULATION), f"n° {s.ident}"))
        rayer(self.tableau)
        compte = {e: sum(1 for m in self.banque if m.etat == e) for e in ETATS}
        self.resume.configure(text=t("{n} mouvement(s) de banque — rapprochés : {r}, absents de Sage : {a}, compte "
                                     "choisi : {c}, ignorés : {i} • écritures Sage seulement : {s}",
                                     n=len(self.banque), r=compte[RAPPROCHE] + compte[SAISI], a=compte[A_SAISIR],
                                     c=compte[CONFIRME], i=compte[IGNORE],
                                     s=sum(1 for s in self.sage if not s.rapproche)))

    # ---------------------------------------------------------------- décisions
    def choisir(self) -> None:
        choix = self.tableau.selection()
        if not choix:
            return
        if choix[0].startswith("s"):
            s = self.sage[int(choix[0][1:])]
            self.mouvement = None
            self.info.configure(text=t("Écriture Sage n° {n} du {d} : {m} — {desc}\nPas encore vue sur un relevé : "
                                       "chèque ou paiement pas encore passé, ou écriture à vérifier dans Sage.",
                                       n=s.ident, d=s.date, m=argent(s.montant), desc=f"{s.description} [{s.source}]"))
            self.remarque.configure(text="")
            return
        m = self.mouvement = self.banque[int(choix[0][1:])]
        self.info.configure(text=t("{d} : {desc}\n{sens} de {m}   •   relevé {r}", d=m.date, desc=m.description,
                                   sens=t("Entrée") if m.montant > 0 else t("Sortie"), m=argent(abs(m.montant)),
                                   r=m.releve))
        self.compte.set(m.compte)
        self.remarque.configure(text=m.remarque)

    def _apres(self) -> None:
        self.registre.retenir(self.mouvement)
        self.registre.enregistrer()
        selection = self.tableau.selection()
        self.chiffres = resume(self.banque, self.sage, *self.soldes)
        self.afficher()
        if selection and self.tableau.exists(selection[0]):
            self.tableau.selection_set(selection[0])

    def confirmer(self) -> None:
        m = self.mouvement
        compte = self.compte.get().strip().split(" ")[0]
        if not m or m.etat in (RAPPROCHE, SAISI):
            messagebox.showinfo(self.titre, t("Choisissez un mouvement « Absent de Sage »."))
            return
        if not compte.isdigit():
            messagebox.showinfo(self.titre, t("Choisissez le compte Sage dans la liste (ex. 5450 Frais bancaires)."))
            return
        m.compte, m.etat = compte, CONFIRME
        self._apres()

    def ignorer(self) -> None:
        if self.mouvement and self.mouvement.etat not in (RAPPROCHE, SAISI):
            self.mouvement.etat = IGNORE
            self._apres()

    def remettre(self) -> None:
        if self.mouvement and self.mouvement.etat in (CONFIRME, IGNORE):
            self.mouvement.etat, self.mouvement.compte = A_SAISIR, ""
            self._apres()

    # ---------------------------------------------------------------- rapport
    def rapport(self) -> None:
        if not self.releves or not getattr(self, "periode", None):
            messagebox.showinfo(self.titre, t("Cliquez d'abord sur « Actualiser »."))
            return
        debut, fin = self.periode
        chemin = self.racine / "sortie" / f"rapprochement_1055_{debut}_{fin}.xlsx"
        try:
            ecrire_rapport(chemin, self.releves, self.banque, self.sage, self.chiffres, (debut, fin))
        except PermissionError:
            messagebox.showerror(self.titre, t("Fermez le fichier Excel ouvert, puis recommencez."))
            return
        import os
        os.startfile(chemin)

