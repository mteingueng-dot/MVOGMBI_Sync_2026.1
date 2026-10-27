"""Page « Rapprochement bancaire » : relevés PDF Desjardins (compte 1055) rapprochés des écritures de Sage."""

from __future__ import annotations

import shutil
import threading
import tkinter as tk
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .design import (CARTE, ROUGE, TEXTE_DOUX, VERT_FONCE, Bouton, ChampDate, ChampRecherche, cadre_tableau,
                     entete_page, fond_de, rayer)
from .export_tableau import bouton_exporter, rendre_exportable
from .langues import t
from .rapprochement import (A_ENCAISSER, A_PAIE, A_SAISIR, CONFIRME, DELAI_PAIE, EN_CIRCULATION, IGNORE, RAPPROCHE,
                            MouvementBanque,
                            SAISI, RegistreReleves, comptes_sage, ecrire_rapport, mouvements_sage, periode_des,
                            rapprocher, restreindre, resume, solde_sage)

ETATS = [A_SAISIR, A_ENCAISSER, A_PAIE, CONFIRME, RAPPROCHE, SAISI, IGNORE]
A_TRAITER = (A_SAISIR, A_ENCAISSER, A_PAIE, CONFIRME)
COULEURS = {A_SAISIR: "#fff4d6", A_ENCAISSER: "#efe8fb", A_PAIE: "#fde2e4", CONFIRME: "#e6f4ea", RAPPROCHE: None,
            SAISI: None, IGNORE: None}
RENVOIS = {A_ENCAISSER: "→ page 7 Encaissements", A_PAIE: "→ module Paie de Sage"}


def argent(valeur) -> str:
    return "" if valeur is None else f"{valeur:,.2f} $".replace(",", " ").replace(".", ",")


class PageRapprochement(ttk.Frame):
    def __init__(self, parent, racine: Path, titre: str, naviguer=None):
        """`naviguer(cle)` : ouvre la page « encaissements » ou « paiements » (après un encaissement ou un paiement
        fournisseur manuel)."""
        super().__init__(parent, padding=10)
        self.racine, self.titre, self.naviguer = Path(racine), titre, naviguer
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
        Bouton(barre, "📤  " + t("Saisir dans Sage"), self.saisir, "accent").pack(side="right", padx=8)
        periode = ttk.Frame(self)
        periode.pack(fill="x", pady=(8, 0))
        ttk.Label(periode, text=t("Période du")).pack(side="left", padx=(0, 4))
        self.du, self.au = tk.StringVar(), tk.StringVar()
        ChampDate(periode, self.du).pack(side="left")
        ttk.Label(periode, text=t("au")).pack(side="left", padx=4)
        ChampDate(periode, self.au).pack(side="left")
        Bouton(periode, "🔄  " + t("Rapprocher cette période"), self.actualiser, petit=True).pack(side="left", padx=8)
        Bouton(periode, t("Toute la période des relevés"), self.toute_la_periode, "secondaire", petit=True).pack(
            side="left")
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
        self.tableau = ttk.Treeview(cadre, columns=[c[0] for c in colonnes], show="headings", height=4,
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
        bouton_exporter(barre, self.tableau, t("Rapprochement bancaire")).pack(side="right")
        rendre_exportable(self.liste, t("Relevés Desjardins"))

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
        manuels = tk.Frame(carte, background=CARTE)  # argent des ventes ou paiement fournisseur saisis à la main
        manuels.pack(fill="x", padx=12, pady=(0, 8))
        Bouton(manuels, "💰  " + t("Encaissement manuel"), self.encaissement_manuel, "accent", fond=CARTE,
               petit=True).pack(side="left")
        Bouton(manuels, "💸  " + t("Paiement fournisseur manuel"), self.paiement_manuel, "accent", fond=CARTE,
               petit=True).pack(side="left", padx=6)
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
        self.toute_la_periode()

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
    def toute_la_periode(self) -> None:
        self.du.set("")
        self.au.set("")
        self.actualiser()

    def _choix_periode(self) -> tuple[date, date] | None | bool:
        """(du, au) choisis ; None = toute la période des relevés ; False = date invalide (message affiché)."""
        textes = (self.du.get().strip(), self.au.get().strip())
        if not any(textes):
            return None
        try:
            du, au = (date.fromisoformat(x) if x else None for x in textes)
        except ValueError:
            messagebox.showwarning(self.titre, t("Date invalide : utilisez le format AAAA-MM-JJ (ou le calendrier 📅)."))
            return False
        du, au = du or date.min, au or date.max
        if du > au:
            messagebox.showwarning(self.titre, t("La date de début est après la date de fin."))
            return False
        return du, au

    def actualiser(self) -> None:
        choix = self._choix_periode()
        if choix is False:
            return
        self.resume.configure(text=t("Lecture des relevés et des écritures du compte 1055 dans Sage…"))

        def travail():
            try:
                from .__main__ import lire_sage

                self.registre = RegistreReleves(self.racine)
                releves = self.registre.lire()
                periode = periode_des(releves)
                if periode and choix:  # période choisie, ramenée à celle des relevés chargés
                    periode = (max(periode[0], choix[0]), min(periode[1], choix[1]))
                    if periode[0] > periode[1]:
                        periode = None
                config = self._config()
                fichier = config.get("sage_import", {}).get("fichier_entreprise")
                if periode:
                    sage, solde, ouverture, comptes, paies = lire_sage(config, lambda base: (
                        mouvements_sage(base, periode[0], periode[1]), solde_sage(base, periode[1]),
                        solde_sage(base, periode[0] - timedelta(days=1)), comptes_sage(base),
                        [s for s in mouvements_sage(base, periode[0] - timedelta(days=DELAI_PAIE),
                                                    periode[0] - timedelta(days=1)) if s.source.upper().startswith("PAY")]),
                        fichier)
                else:
                    sage, solde, ouverture, comptes, paies = [], None, None, [], []
                self.after(0, lambda: self._fin_lecture(releves, sage, solde, ouverture, comptes, periode, paies))
            except Exception as exc:
                message = str(exc)
                self.after(0, lambda: self.resume.configure(text="✘ " + message))

        threading.Thread(target=travail, daemon=True).start()

    def _fin_lecture(self, releves, sage, solde, ouverture_sage, comptes, periode, paies=()) -> None:
        self.releves, self.sage, self.comptes, self.periode = releves, sage, comptes, periode
        if periode:
            self.du.set(periode[0].isoformat())
            self.au.set(periode[1].isoformat())
            self.banque, ouverture_banque, solde_banque = restreindre(releves, *periode)
        else:
            self.banque, ouverture_banque, solde_banque = [], None, None
        rapprocher(self.banque, self.sage, list(paies))  # salaires versés en retard : paies d'avant la période
        self.soldes = (solde_banque, solde, ouverture_banque, ouverture_sage)
        self.chiffres = resume(self.banque, self.sage, *self.soldes, debut=self.periode[0] if self.periode else None)
        self.champ_compte.configurer_valeurs(comptes)
        self.afficher_releves()
        self.afficher()
        if not periode and releves:
            self.resume.configure(text=t("Aucun relevé chargé ne couvre cette période."))

    def afficher(self) -> None:
        for cle, etiquette in self.valeurs.items():
            valeur = self.chiffres.get(cle)
            couleur = ROUGE if cle in ("ecart", "non_explique") and valeur not in (None, Decimal(0)) else VERT_FONCE
            etiquette.configure(text=argent(valeur) if valeur is not None else "—", foreground=couleur)
        choix = self.filtre.get()
        self.tableau.delete(*self.tableau.get_children())
        prevus = self._manuels_prevus()
        if choix != t(EN_CIRCULATION):
            for i, m in enumerate(self.banque):
                if choix == t("À traiter") and m.etat not in A_TRAITER:
                    continue
                if choix not in (t("À traiter"), t("Tous")) and t(m.etat) != choix:
                    continue
                lien = (", ".join(f"n° {n}" for n in m.sage) if m.sage else
                        m.compte or prevus.get(m.cle) or t(RENVOIS.get(m.etat, "")))
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
        # le mouvement le plus récent en haut (banque et écritures Sage mêlées)
        lignes = sorted(self.tableau.get_children(), key=lambda i: self.tableau.item(i, "values")[0], reverse=True)
        for rang, ligne in enumerate(lignes):
            self.tableau.move(ligne, "", rang)
        rayer(self.tableau)
        compte = {e: sum(1 for m in self.banque if m.etat == e) for e in ETATS}
        self.resume.configure(text=t("{n} mouvement(s) de banque — rapprochés : {r}, absents de Sage : {a}, à encaisser "
                                     "sur les ventes : {e}, paies absentes : {p}, compte choisi : {c}, ignorés : {i} • "
                                     "écritures Sage seulement : {s}",
                                     n=len(self.banque), r=compte[RAPPROCHE] + compte[SAISI], a=compte[A_SAISIR],
                                     e=compte[A_ENCAISSER], p=compte[A_PAIE], c=compte[CONFIRME], i=compte[IGNORE],
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
        conseil = {A_ENCAISSER: t("Argent des ventes (Interac ou espèces) : il s'encaisse sur les factures de vente à la "
                                  "page 7 « Encaissements », pas en écriture de journal."),
                   A_PAIE: t("Dépôt de salaire : aucune paie du même montant dans Sage (source PAY…). Saisissez ou "
                             "corrigez la paie dans le module Paie de Sage, puis « Actualiser ».")}.get(m.etat, "")
        self.remarque.configure(text=m.remarque or conseil)

    def _apres(self) -> None:
        self.registre.retenir(self.mouvement)
        self.registre.enregistrer()
        selection = self.tableau.selection()
        self.chiffres = resume(self.banque, self.sage, *self.soldes, debut=self.periode[0] if self.periode else None)
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

    # ---------------------------------------------------------------- encaissements et paiements manuels
    def _manuels_prevus(self) -> dict[str, str]:
        """Clé de mouvement -> renvoi affiché, pour les encaissements et paiements fournisseurs décidés à la main."""
        from .encaissements import RegistreEncaissementsManuels
        from .paiements_fournisseurs import RegistrePaiements

        prevus = {e["cle"]: t("→ page 7 : encaissement manuel sur {f}", f=e["facture"])
                  for e in RegistreEncaissementsManuels(self.racine).liste}
        for p in RegistrePaiements(self.racine).paiements:
            if p.avis.identifiant.startswith("releve:"):
                prevus[p.avis.identifiant[len("releve:"):]] = t("→ page 9 : paiement fournisseur manuel")
        return prevus

    def _mouvement_libre(self, entree: bool) -> MouvementBanque | None:
        m = self.mouvement
        if not m or m.etat in (RAPPROCHE, SAISI) or (m.montant > 0) != entree:
            messagebox.showinfo(self.titre, t("Choisissez une entrée d'argent absente de Sage.") if entree else
                                t("Choisissez une sortie d'argent absente de Sage."))
            return None
        return m

    def paiement_manuel(self) -> None:
        """Sortie d'argent payée à un fournisseur : ajoutée à la page Paiements fournisseurs, où l'on choisit le
        fournisseur et la facture, puis « Payer dans Sage »."""
        from .paiements_courriel import AvisPaiement
        from .paiements_fournisseurs import RegistrePaiements

        m = self._mouvement_libre(entree=False)
        if not m:
            return
        morceaux = [x.strip() for x in m.description.split("/") if x.strip()]
        avis = AvisPaiement(identifiant=f"releve:{m.cle}", date_courriel=m.date, date_virement=m.date,
                            montant=-m.montant, beneficiaire=morceaux[1] if len(morceaux) > 1 else m.description,
                            reference=m.releve, message=m.description, source="Relevé Desjardins")
        registre = RegistrePaiements(self.racine)
        if not registre.ajouter([avis]):
            messagebox.showinfo(self.titre, t("Ce mouvement est déjà à la page 9 (Paiements fournisseurs)."))
        registre.enregistrer()
        self.afficher()
        if messagebox.askyesno(self.titre, t("Paiement de {m} ajouté à la page 9 : choisissez le fournisseur et la "
                                             "facture, confirmez, puis « Payer dans Sage ».\n\nOuvrir la page 9 ?",
                                             m=argent(-m.montant))) and self.naviguer:
            self.naviguer("paiements")

    def encaissement_manuel(self) -> None:
        """Entrée d'argent à encaisser sur une facture de vente choisie : notée, puis saisie dans Sage par la page
        Encaissements (« Encaisser dans Sage »)."""
        m = self._mouvement_libre(entree=True)
        if not m:
            return
        self.resume.configure(text=t("Lecture des factures de vente ouvertes dans Sage…"))

        def travail():
            try:
                from .__main__ import lire_sage
                from .encaissements import etat_factures_sage, numero_compte_sage
                from .facture import CLIENT
                from .rapprochement import factures_ventes

                config = self._config()
                compte = numero_compte_sage(str(config.get("encaissements", {}).get("compte_depot", "1055")))

                def lire(base):
                    dates = factures_ventes(base, CLIENT)
                    etat = etat_factures_sage(base, CLIENT, compte, list(dates))
                    return [(n, d, etat.get(n, {}).get("du")) for n, d in dates.items()]

                factures = lire_sage(config, lire, config.get("sage_import", {}).get("fichier_entreprise"))
                self.after(0, lambda: self._choisir_facture(m, factures))
            except Exception as exc:
                message = str(exc)
                self.after(0, lambda: self.resume.configure(text="✘ " + message))

        threading.Thread(target=travail, daemon=True).start()

    def _choisir_facture(self, m: MouvementBanque, factures) -> None:
        from .encaissements import RegistreEncaissementsManuels, origine
        from .rapprochement import facture_du_jour

        self.afficher()
        ouvertes = sorted(((n, d, du) for n, d, du in factures if du and du > 0), key=lambda x: (x[1], x[0]))
        if not ouvertes:
            messagebox.showinfo(self.titre, t("Aucune facture de vente avec un solde dû dans Sage."))
            return
        libelles = [f"{n}  —  {t('solde')} {argent(du)}" for n, d, du in ouvertes]
        # facture du jour du mouvement, sinon la plus récente dont le solde couvre le montant
        proposee = facture_du_jour(date.fromisoformat(m.date), {n: d for n, d, _ in ouvertes}) or next(
            (n for n, _, du in reversed(ouvertes) if du >= m.montant), ouvertes[-1][0])
        fenetre = tk.Toplevel(self)
        fenetre.title(t("Encaissement manuel"))
        fenetre.configure(background=CARTE)
        fenetre.transient(self.winfo_toplevel())
        cadre = tk.Frame(fenetre, background=CARTE, padx=20, pady=16)
        cadre.pack()
        tk.Label(cadre, text=t("{d} : {desc}\nEntrée de {m}", d=m.date, desc=m.description, m=argent(m.montant)),
                 background=CARTE, justify="left", font=("Segoe UI", 10)).grid(row=0, column=0, columnspan=2,
                                                                                 sticky="w", pady=(0, 10))
        tk.Label(cadre, text=t("Facture de vente"), background=CARTE).grid(row=1, column=0, sticky="w")
        choix = tk.StringVar(value=next((l for l, (n, _, _) in zip(libelles, ouvertes) if n == proposee),
                                        libelles[-1]))
        ttk.Combobox(cadre, textvariable=choix, values=libelles, state="readonly", width=44).grid(
            row=1, column=1, sticky="w", padx=(8, 0))
        tk.Label(cadre, text=t("Montant"), background=CARTE).grid(row=2, column=0, sticky="w", pady=(8, 0))
        montant = tk.StringVar()
        ttk.Entry(cadre, textvariable=montant, width=14).grid(row=2, column=1, sticky="w", padx=(8, 0), pady=(8, 0))

        def ajuster(_e=None) -> None:  # montant du mouvement, au plus le solde dû de la facture choisie
            du = ouvertes[libelles.index(choix.get())][2]
            montant.set(f"{min(m.montant, du):.2f}")

        ajuster()
        cadre.grid_slaves(row=1, column=1)[0].bind("<<ComboboxSelected>>", ajuster)

        def valider() -> None:
            numero, _, du = ouvertes[libelles.index(choix.get())]
            try:
                valeur = Decimal(montant.get().replace(",", ".").replace(" ", "")).quantize(Decimal("0.01"))
            except Exception:
                messagebox.showwarning(self.titre, t("Montant invalide."), parent=fenetre)
                return
            if valeur <= 0 or valeur > m.montant or valeur > du:
                messagebox.showwarning(self.titre, t("Le montant doit être positif, sans dépasser le mouvement ni le "
                                                     "solde dû de la facture ({du}).", du=argent(du)), parent=fenetre)
                return
            registre = RegistreEncaissementsManuels(self.racine)
            registre.ajouter(m.cle, date.fromisoformat(m.date), valeur, numero, origine(m))
            registre.enregistrer()
            fenetre.destroy()
            self.afficher()
            if messagebox.askyesno(self.titre, t("Encaissement de {m} sur {f} noté. Il sera saisi dans Sage par « "
                                                 "Encaisser dans Sage » (page 7).\n\nOuvrir la page 7 ?",
                                                 m=argent(valeur), f=numero)) and self.naviguer:
                self.naviguer("encaissements")

        Bouton(cadre, "✔  " + t("Noter l'encaissement"), valider, fond=CARTE).grid(row=3, column=0, columnspan=2,
                                                                                  pady=(14, 0))
        fenetre.grab_set()

    # ---------------------------------------------------------------- saisie dans Sage
    def saisir(self) -> None:
        """Saisit en écritures de journal les mouvements « Compte choisi » (Sage fermé, ouvert par l'application dans
        la fenêtre Journal général), puis les vérifie dans Sage."""
        from .sage_bureau import sage_ouvert

        choisis = [m for m in self.banque if m.etat == CONFIRME]
        if not choisis:
            messagebox.showinfo(self.titre, t("Aucun mouvement « Compte choisi » : choisissez d'abord le compte Sage des "
                                              "mouvements absents de Sage."))
            return
        if sage_ouvert():
            messagebox.showwarning(self.titre, t("Fermez Sage : l'import exige que personne ne soit dans le fichier "
                                                 "d'entreprise."))
            return
        liste = "\n".join(f"  • {m.date}  {argent(m.montant)}  → {m.compte}   {m.description[:40]}" for m in choisis[:25])
        if len(choisis) > 25:
            liste += "\n  …"
        if not messagebox.askyesno(self.titre, t("Enregistrer {n} écriture(s) dans Sage (compte 1055) ?\n\n{liste}",
                                                 n=len(choisis), liste=liste)):
            return
        self.registre.enregistrer()  # les comptes choisis doivent être sur le disque pour la saisie
        self.resume.configure(text=t("Enregistrement des écritures dans Sage…"))

        def travail():
            import json
            import tempfile

            from .__main__ import commande_moteur
            from .sage_bureau import executer_sur_bureau_cache

            try:
                with tempfile.TemporaryDirectory() as dossier:
                    fichier = Path(dossier) / "bilan.json"
                    executer_sur_bureau_cache(commande_moteur() + ["journal-bureau", "--resultat", str(fichier)],
                                              self.racine)
                    bilan = json.loads(fichier.read_text(encoding="utf-8")) if fichier.exists() else {}
                message = t("{ok} écriture(s) enregistrée(s) sur {n}.", n=len(choisis), ok=len(bilan.get("saisis", [])))
                details = bilan.get("a_verifier", []) + ([bilan["erreur"]] if bilan.get("erreur") else [])
                if details:
                    message += "\n\n" + "\n".join(details[:15])
            except Exception as exc:
                message = f"✘ {exc}"
            self.after(0, lambda: (messagebox.showinfo(self.titre, message), self.actualiser()))

        threading.Thread(target=travail, daemon=True).start()

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

