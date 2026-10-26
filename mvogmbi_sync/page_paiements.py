"""Page « Paiements fournisseurs » : avis Interac lus dans la boîte, rapprochés des factures fournisseurs de Sage."""

from __future__ import annotations

import threading
import tkinter as tk
from datetime import date
from pathlib import Path
from tkinter import messagebox, ttk

from .correspondance import normaliser
from .design import CARTE, ROUGE, TEXTE_DOUX, VERT_FONCE, Bouton, ChampRecherche
from .fournisseurs import MemoireCorrespondance, lire_copie_fournisseurs
from .langues import t
from .paiements_fournisseurs import (A_RELIER, CONFIRME, DEJA, ETATS, IGNORE, NON_PAYE, PROPOSE, SAISI,
                                     RegistrePaiements, rapprocher)

COULEURS = {A_RELIER: "#fff4d6", PROPOSE: "#eaf2fb", CONFIRME: "#e3f4e8", DEJA: "#eef1ef", SAISI: "#eef1ef",
            IGNORE: "#f4f4f4", NON_PAYE: "#fde2e4"}


class PagePaiements(ttk.Frame):
    def __init__(self, parent, racine: Path, titre: str):
        super().__init__(parent, padding=10)
        self.racine, self.titre = Path(racine), titre
        self.registre = RegistrePaiements(self.racine)
        self.memoire = MemoireCorrespondance(self.racine)
        self.fournisseurs = lire_copie_fournisseurs(self.racine)
        self.ouvertes = []
        self.existants = set()
        self.paiement = None

        barre = ttk.Frame(self)
        barre.pack(fill="x")
        Bouton(barre, "📥  " + t("Lire la boîte et Sage"), self.lire).pack(side="left")
        ttk.Label(barre, text=t("Afficher :")).pack(side="left", padx=(16, 4))
        self.filtre = tk.StringVar(value=t("À traiter"))
        liste = ttk.Combobox(barre, textvariable=self.filtre, state="readonly", width=22,
                             values=[t("À traiter"), t("Tous")] + [t(e) for e in ETATS])
        liste.pack(side="left")
        liste.bind("<<ComboboxSelected>>", lambda _e: self.afficher())
        self.resume = ttk.Label(self, text="", foreground=TEXTE_DOUX, padding=(0, 6))
        self.resume.pack(fill="x")

        cadre = ttk.Frame(self)
        cadre.pack(fill="both", expand=True)
        colonnes = (("date", "Date", 85), ("beneficiaire", "Bénéficiaire", 170), ("montant", "Montant", 90),
                    ("message", "Message", 170), ("fournisseur", "Fournisseur Sage", 180), ("facture", "Facture", 100),
                    ("solde", "Solde dû", 85), ("etat", "État", 130))
        self.tableau = ttk.Treeview(cadre, columns=[c[0] for c in colonnes], show="headings", height=10,
                                    selectmode="browse")
        for cle, titre_col, largeur in colonnes:
            self.tableau.heading(cle, text=t(titre_col))
            self.tableau.column(cle, width=largeur, anchor="e" if cle in ("montant", "solde") else "w",
                                stretch=cle in ("beneficiaire", "message", "fournisseur"))
        for etat, couleur in COULEURS.items():
            self.tableau.tag_configure(etat, background=couleur)
        defil = ttk.Scrollbar(cadre, orient="vertical", command=self.tableau.yview)
        self.tableau.configure(yscrollcommand=defil.set)
        self.tableau.pack(side="left", fill="both", expand=True)
        defil.pack(side="right", fill="y")
        self.tableau.bind("<<TreeviewSelect>>", lambda _e: self.choisir())

        carte = tk.Frame(self, background=CARTE, highlightthickness=1, highlightbackground="#e2e8e4")
        carte.pack(fill="x", pady=(8, 0))
        haut = tk.Frame(carte, background=CARTE)
        haut.pack(fill="x", padx=12, pady=(10, 4))
        self.info = tk.Label(haut, text=t("Sélectionnez un virement dans la liste."), background=CARTE, anchor="w",
                             justify="left", font=("Segoe UI", 10))
        self.info.pack(fill="x")
        ligne = tk.Frame(carte, background=CARTE)
        ligne.pack(fill="x", padx=12, pady=4)
        tk.Label(ligne, text=t("Fournisseur Sage"), background=CARTE, font=("Segoe UI", 9)).pack(side="left", padx=(0, 6))
        self.fournisseur = tk.StringVar()
        self.champ_fournisseur = ChampRecherche(ligne, self.fournisseur, self.fournisseurs, largeur=40,
                                                au_choix=lambda _n: self.lister_factures())
        self.champ_fournisseur.pack(side="left")
        self.remarque = tk.Label(ligne, text="", background=CARTE, foreground=ROUGE, font=("Segoe UI", 9))
        self.remarque.pack(side="left", padx=10)
        bas = tk.Frame(carte, background=CARTE)
        bas.pack(fill="x", padx=12, pady=(4, 10))
        gauche = tk.Frame(bas, background=CARTE)
        gauche.pack(side="left", fill="x", expand=True)
        tk.Label(gauche, text=t("Factures impayées de ce fournisseur dans Sage :"), background=CARTE,
                 font=("Segoe UI", 9), anchor="w").pack(fill="x")
        self.factures = tk.Listbox(gauche, height=5, font=("Consolas", 9), activestyle="none")
        self.factures.pack(fill="x")
        self.factures.bind("<Double-Button-1>", lambda _e: self.confirmer())
        boutons = tk.Frame(bas, background=CARTE)
        boutons.pack(side="left", anchor="n", padx=(10, 0))
        Bouton(boutons, "✔  " + t("Confirmer le paiement"), self.confirmer, fond=CARTE, largeur=210).pack()
        Bouton(boutons, t("Ignorer (pas un fournisseur)"), self.ignorer, "secondaire", fond=CARTE, largeur=210).pack(pady=4)
        Bouton(boutons, t("Remettre à relier"), self.remettre, "secondaire", fond=CARTE, largeur=210).pack()
        self.choix_factures = []
        self.afficher()

    # ---------------------------------------------------------------- lecture
    def _config(self) -> dict:
        import tomllib
        chemin = self.racine / "config.toml"
        return tomllib.loads(chemin.read_text(encoding="utf-8")) if chemin.exists() else {}

    def lire(self) -> None:
        self.resume.configure(text=t("Lecture de la boîte de courriel et des factures impayées dans Sage…"))

        def travail():
            try:
                from . import coffre
                from .__main__ import lire_sage
                from .encaissements import numero_compte_sage
                from .fournisseurs import fournisseurs_actifs
                from .paiements_courriel import lire_boite
                from .paiements_fournisseurs import factures_ouvertes, paiements_existants

                config = self._config()
                b = config.get("boite_paiements", {})
                if not b.get("serveur") or not b.get("utilisateur"):
                    raise RuntimeError(t("Réglez la boîte des avis de paiement (page Courriel)."))
                depuis = date.fromisoformat(str(b.get("depuis", "2026-08-01")))
                avis = lire_boite(b["serveur"], b["utilisateur"], coffre.lire(coffre.BOITE_PAIEMENTS), depuis,
                                  int(b.get("port", 993)))
                compte = numero_compte_sage(str(config.get("encaissements", {}).get("compte_depot", "1055")))
                ouvertes, existants, noms = lire_sage(
                    config, lambda base: (factures_ouvertes(base), paiements_existants(base, compte, depuis),
                                          fournisseurs_actifs(base)),
                    config.get("sage_import", {}).get("fichier_entreprise"))
                self.after(0, lambda: self._fin_lecture(avis, ouvertes, existants, noms))
            except Exception as exc:
                message = str(exc)
                self.after(0, lambda: self.resume.configure(text="✘ " + message))

        threading.Thread(target=travail, daemon=True).start()

    def _fin_lecture(self, avis, ouvertes, existants, noms) -> None:
        self.ouvertes, self.existants, self.fournisseurs = ouvertes, existants, noms
        self.champ_fournisseur.configurer_valeurs(noms)
        nouveaux = self.registre.ajouter(avis)
        beneficiaires = self.memoire.donnees.setdefault("beneficiaires", {})
        for p in self.registre.paiements:
            rapprocher(p, noms, beneficiaires, ouvertes, existants)
        self.registre.enregistrer()
        self.afficher()
        self.resume.configure(text=self.resume.cget("text") + "   •   " +
                              t("{n} nouvel(s) avis lu(s)", n=len(nouveaux)))

    # ---------------------------------------------------------------- liste
    def afficher(self) -> None:
        choix = self.filtre.get()
        self.tableau.delete(*self.tableau.get_children())
        for i, p in enumerate(self.registre.paiements):
            if choix == t("À traiter") and p.etat not in (A_RELIER, PROPOSE, CONFIRME):
                continue
            if choix not in (t("À traiter"), t("Tous")) and t(p.etat) != choix:
                continue
            a = p.avis
            self.tableau.insert("", "end", iid=str(i), tags=(p.etat,), values=(
                a.date_virement, a.beneficiaire, f"{a.montant:,.2f}", a.message, p.fournisseur_sage, p.facture,
                "" if p.solde_facture is None else f"{p.solde_facture:,.2f}", t(p.etat)))
        compte = {e: sum(1 for p in self.registre.paiements if p.etat == e) for e in ETATS}
        self.resume.configure(text=t("{n} virement(s) — à relier : {r}, proposés : {p}, confirmés : {c}, déjà dans "
                                     "Sage : {d}, ignorés : {i}, annulés/expirés : {x}", n=len(self.registre.paiements),
                                     r=compte[A_RELIER], p=compte[PROPOSE], c=compte[CONFIRME], d=compte[DEJA],
                                     i=compte[IGNORE], x=compte[NON_PAYE]))

    def choisir(self) -> None:
        choix = self.tableau.selection()
        if not choix:
            return
        self.paiement = p = self.registre.paiements[int(choix[0])]
        a = p.avis
        self.info.configure(text=t("Virement Interac du {d} : {m} $ à {b}   •   réf. {r}\nMessage : « {msg} »",
                                   d=a.date_virement, m=f"{a.montant:,.2f}", b=a.beneficiaire, r=a.reference or "—",
                                   msg=a.message or "—"))
        self.fournisseur.set(p.fournisseur_sage)
        self.remarque.configure(text=p.remarque)
        self.lister_factures()

    def lister_factures(self) -> None:
        self.factures.delete(0, "end")
        nom = self.fournisseur.get().strip()
        self.choix_factures = [f for f in self.ouvertes if f.fournisseur == nom]
        for f in self.choix_factures:
            marque = "  ◄" if self.paiement and f.numero == self.paiement.facture else ""
            self.factures.insert("end", f"{f.numero:<16} {f.date}   {f.solde:>12,.2f} ${marque}")
            if marque:
                self.factures.selection_set("end")
                self.factures.see("end")
        if not self.ouvertes:
            self.factures.insert("end", t("(cliquez sur « Lire la boîte et Sage » pour charger les factures impayées)"))

    # ---------------------------------------------------------------- décisions
    def _apres(self) -> None:
        self.registre.enregistrer()
        selection = self.tableau.selection()
        self.afficher()
        if selection and self.tableau.exists(selection[0]):
            self.tableau.selection_set(selection[0])

    def confirmer(self) -> None:
        p = self.paiement
        choix = self.factures.curselection()
        nom = self.fournisseur.get().strip()
        if not p or not nom or not choix or choix[0] >= len(self.choix_factures):
            messagebox.showinfo(self.titre, t("Choisissez le fournisseur Sage, puis la facture payée dans la liste."))
            return
        f = self.choix_factures[choix[0]]
        if f.solde < p.avis.montant and not messagebox.askyesno(
                self.titre, t("Le virement ({m} $) dépasse le solde de la facture ({s} $). Confirmer quand même ?",
                              m=f"{p.avis.montant:,.2f}", s=f"{f.solde:,.2f}")):
            return
        p.fournisseur_sage, p.facture, p.solde_facture, p.etat = nom, f.numero, f.solde, CONFIRME
        p.remarque = "" if f.solde == p.avis.montant else t("paiement partiel ou écart : virement {m} $, solde {s} $",
                                                              m=p.avis.montant, s=f.solde)
        self.memoire.donnees.setdefault("beneficiaires", {})[normaliser(p.avis.beneficiaire)] = nom
        self.memoire.enregistrer()
        self._apres()

    def ignorer(self) -> None:
        if self.paiement:
            self.paiement.etat, self.paiement.remarque = IGNORE, t("ignoré par le propriétaire")
            self._apres()

    def remettre(self) -> None:
        if self.paiement and self.paiement.etat != SAISI:
            self.paiement.etat, self.paiement.facture, self.paiement.solde_facture = A_RELIER, "", None
            self.paiement.remarque = ""
            self._apres()
