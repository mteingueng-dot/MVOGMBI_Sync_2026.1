"""Page « Paiements fournisseurs » : avis Interac lus dans la boîte, rapprochés des factures fournisseurs de Sage."""

from __future__ import annotations

import threading
import tkinter as tk
from datetime import date
from pathlib import Path
from tkinter import messagebox, ttk

from .correspondance import normaliser
from .design import (CARTE, ROUGE, TEXTE_DOUX, VERT_FONCE, Bouton, ChampDate, ChampRecherche, cadre_tableau, entete_page,
                     rayer)
from .fournisseurs import MemoireCorrespondance, lire_copie_fournisseurs
from .export_tableau import bouton_exporter, rendre_exportable
from .langues import t
from .paiements_fournisseurs import (A_RELIER, CONFIRME, DEJA, ETATS, IGNORE, NON_PAYE, PROPOSE, SAISI,
                                     RegistrePaiements, rapprocher, repartir)

COULEURS = {A_RELIER: "#fff4d6", PROPOSE: "#eaf2fb", CONFIRME: "#e6f4ea", DEJA: None, SAISI: None, IGNORE: None,
            NON_PAYE: "#fde2e4"}


class PagePaiements(ttk.Frame):
    def __init__(self, parent, racine: Path, titre: str, depuis: tk.StringVar | None = None, au_changement_date=None):
        super().__init__(parent, padding=10)
        self.racine, self.titre = Path(racine), titre
        self.au_changement_date = au_changement_date
        self.depuis = depuis or tk.StringVar(value=str(self._config().get("boite_paiements", {}).get("depuis",
                                                                                                    "2026-08-01")))
        self.deja_lu = False
        self.registre = RegistrePaiements(self.racine)
        self.memoire = MemoireCorrespondance(self.racine)
        self.fournisseurs = lire_copie_fournisseurs(self.racine)
        self.ouvertes = []
        self.existants = set()
        self.paiement = None

        entete_page(self, "💸", t("Paiements fournisseurs"),
                    t("virements Interac reliés aux factures fournisseurs et saisis dans Sage")).pack(fill="x")
        barre = ttk.Frame(self)
        barre.pack(fill="x")
        ttk.Label(barre, text=t("Lire depuis le")).pack(side="left", padx=(0, 4))
        ChampDate(barre, self.depuis).pack(side="left")
        # date de fin : filtre l'affichage entre deux dates (la lecture du courriel part toujours de « depuis »)
        self.au = tk.StringVar(value=date.today().isoformat())
        ttk.Label(barre, text=t("au")).pack(side="left", padx=(6, 4))
        ChampDate(barre, self.au).pack(side="left")
        for variable in (self.depuis, self.au):
            variable.trace_add("write", lambda *_: self._dates_changees())
        Bouton(barre, "🔄  " + t("Actualiser"), self.lire).pack(side="left", padx=(8, 0))
        ttk.Label(barre, text=t("Afficher :")).pack(side="left", padx=(16, 4))
        self.filtre = tk.StringVar(value=t("À traiter"))
        liste = ttk.Combobox(barre, textvariable=self.filtre, state="readonly", width=22,
                             values=[t("À traiter"), t("Tous")] + [t(e) for e in ETATS])
        liste.pack(side="left")
        liste.bind("<<ComboboxSelected>>", lambda _e: self.afficher())
        Bouton(barre, "💸  " + t("Payer dans Sage"), self.payer, "accent").pack(side="right")
        self.resume = ttk.Label(self, text="", foreground=TEXTE_DOUX, padding=(0, 6))
        self.resume.pack(fill="x")

        cadre = cadre_tableau(self)
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
        for etat, couleur in COULEURS.items():  # sans couleur : état terminé, texte grisé sur lignes rayées
            self.tableau.tag_configure(etat, **({"background": couleur} if couleur else {"foreground": TEXTE_DOUX}))
        defil = ttk.Scrollbar(cadre, orient="vertical", command=self.tableau.yview)
        self.tableau.configure(yscrollcommand=defil.set)
        defil.pack(side="right", fill="y")  # avant le tableau : toujours visible, même s'il est large
        self.tableau.pack(side="left", fill="both", expand=True)
        self.tableau.bind("<<TreeviewSelect>>", lambda _e: self.choisir())
        bouton_exporter(barre, self.tableau, t("Paiements fournisseurs")).pack(side="right", padx=8)

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
        tk.Label(gauche, text=t("Factures impayées de ce fournisseur dans Sage (Ctrl+clic : plusieurs factures pour "
                                "un même virement) :"), background=CARTE,
                 font=("Segoe UI", 9), anchor="w").pack(fill="x")
        self.factures = tk.Listbox(gauche, height=5, font=("Consolas", 9), activestyle="none", selectmode="extended",
                                   exportselection=False)
        self.factures.pack(fill="x")
        self.factures.bind("<Double-Button-1>", lambda _e: self.confirmer())
        boutons = tk.Frame(bas, background=CARTE)
        boutons.pack(side="left", anchor="n", padx=(10, 0))
        Bouton(boutons, "✔  " + t("Confirmer le paiement"), self.confirmer, fond=CARTE, largeur=210).pack()
        Bouton(boutons, t("Ignorer (pas un fournisseur)"), self.ignorer, "secondaire", fond=CARTE, largeur=210).pack(pady=4)
        Bouton(boutons, t("Remettre à relier"), self.remettre, "secondaire", fond=CARTE, largeur=210).pack()
        self.choix_factures = []
        self.afficher()
        self.bind("<Map>", lambda _e: self._premiere_lecture())

    def _premiere_lecture(self) -> None:
        """À la première ouverture de la page : lecture automatique si la boîte est réglée."""
        if not self.deja_lu and self._config().get("boite_paiements", {}).get("serveur"):
            self.deja_lu = True
            self.lire()

    def _date_depuis(self) -> date | None:
        try:
            return date.fromisoformat(self.depuis.get().strip())
        except ValueError:
            return None

    def _date_au(self) -> date:
        try:
            return date.fromisoformat(self.au.get().strip())
        except (ValueError, AttributeError):
            return date.max

    def _dates_changees(self) -> None:
        """Une date valide choisie : la liste est refiltrée tout de suite (sans relire le courriel)."""
        if hasattr(self, "tableau") and self._date_depuis() and self._date_au() != date.max:
            self.afficher()

    # ---------------------------------------------------------------- lecture
    def _config(self) -> dict:
        import tomllib
        chemin = self.racine / "config.toml"
        return tomllib.loads(chemin.read_text(encoding="utf-8")) if chemin.exists() else {}

    def lire(self) -> None:
        """Actualiser : relit les avis reçus depuis la date choisie et les factures impayées de Sage, puis affiche
        tous les virements pas encore traités."""
        depuis = self._date_depuis()
        if not depuis:
            messagebox.showerror(self.titre, t("Date invalide (AAAA-MM-JJ)."))
            return
        self.deja_lu = True
        if self.au_changement_date:
            self.au_changement_date(depuis.isoformat())
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
            if p.etat == CONFIRME and (p.fournisseur_sage, p.avis.date_virement, p.avis.montant) in existants:
                p.etat, p.remarque = DEJA, t("saisi entre-temps dans Sage")  # payé à la main depuis la confirmation
            rapprocher(p, noms, beneficiaires, ouvertes, existants)
        self.registre.enregistrer()
        self.filtre.set(t("À traiter"))
        self.afficher()
        self.resume.configure(text=self.resume.cget("text") + "   •   " +
                              t("{n} nouvel(s) avis lu(s)", n=len(nouveaux)))

    # ---------------------------------------------------------------- liste
    def afficher(self) -> None:
        choix = self.filtre.get()
        depuis, au = (self._date_depuis() or date.min).isoformat(), self._date_au().isoformat()
        self.tableau.delete(*self.tableau.get_children())
        for i, p in sorted(enumerate(self.registre.paiements), key=lambda x: (x[1].avis.date_virement, x[0]),
                           reverse=True):  # le plus récent en haut
            if not depuis <= p.avis.date_virement <= au:
                continue
            if choix == t("À traiter") and p.etat not in (A_RELIER, PROPOSE, CONFIRME):
                continue
            if choix not in (t("À traiter"), t("Tous")) and t(p.etat) != choix:
                continue
            a = p.avis
            self.tableau.insert("", "end", iid=str(i), tags=(p.etat,), values=(
                a.date_virement, a.beneficiaire, f"{a.montant:,.2f}", a.message, p.fournisseur_sage, p.facture,
                "" if p.solde_facture is None else f"{p.solde_facture:,.2f}", t(p.etat)))
        rayer(self.tableau)
        visibles = [p for p in self.registre.paiements if depuis <= p.avis.date_virement <= au]
        compte = {e: sum(1 for p in visibles if p.etat == e) for e in ETATS}
        self.resume.configure(text=t("{n} virement(s) — à relier : {r}, proposés : {p}, confirmés : {c}, déjà dans "
                                     "Sage : {d}, ignorés : {i}, annulés/expirés : {x}", n=len(visibles),
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
        retenues = {n: m for n, m, _ in self.paiement.lignes()} if self.paiement else {}
        for f in self.choix_factures:
            marque = f"  ◄ {retenues[f.numero]:,.2f} $" if f.numero in retenues else ""
            self.factures.insert("end", f"{f.numero:<16} {f.date}   {f.solde:>12,.2f} ${marque}")
            if marque:
                self.factures.selection_set("end")
                self.factures.see("end")
        if not self.ouvertes:
            self.factures.insert("end", t("(cliquez sur « Actualiser » pour charger les factures impayées)"))

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
        choisies = [self.choix_factures[i] for i in choix if i < len(self.choix_factures)]
        if not p or not nom or not choisies:
            messagebox.showinfo(self.titre, t("Choisissez le fournisseur Sage, puis la facture payée dans la liste."))
            return
        try:  # de la plus ancienne à la plus récente ; seule la dernière peut être payée en partie
            parts = repartir(p.avis.montant, choisies)
        except ValueError:
            messagebox.showwarning(self.titre, t("Le virement ({m} $) dépasse le solde des factures choisies ({s} $) : "
                                                 "choisissez d'autres factures (Ctrl+clic).", m=f"{p.avis.montant:,.2f}",
                                                 s=f"{sum(f.solde for f in choisies):,.2f}"))
            return
        if len(choisies) > 1:
            detail = "\n".join(f"  • {f.numero} ({f.date}) : {m:,.2f} $"
                                + (t("  (partiel, solde {s} $)", s=f"{f.solde:,.2f}") if m < f.solde else "")
                                for f, m in parts)
            inutiles = len(choisies) - len(parts)
            if not messagebox.askyesno(self.titre, t("Répartir le virement de {m} $ ainsi ?\n\n{detail}", m=f"{p.avis.montant:,.2f}",
                                                     detail=detail)
                                       + (t("\n\n{n} facture(s) choisie(s) inutile(s) : non payée(s).", n=inutiles)
                                          if inutiles else "")):
                return
        p.fournisseur_sage, p.etat = nom, CONFIRME
        p.appliquer_repartition(parts)
        if len(parts) > 1:
            p.remarque = t("virement réparti sur {n} factures", n=len(parts))
        else:
            f = parts[0][0]
            p.remarque = "" if f.solde == p.avis.montant else t("paiement partiel : virement {m} $, solde {s} $",
                                                                  m=p.avis.montant, s=f.solde)
        self.memoire.donnees.setdefault("beneficiaires", {})[normaliser(p.avis.beneficiaire)] = nom
        self.memoire.enregistrer()
        self._apres()

    # ---------------------------------------------------------------- saisie dans Sage
    def payer(self) -> None:
        """Le robot saisit les paiements confirmés dans la fenêtre Paiements de Sage (Sage fermé, bureau caché)."""
        from .sage_bureau import sage_ouvert

        confirmes = [p for p in self.registre.paiements if p.etat == CONFIRME]
        if not confirmes:
            messagebox.showinfo(self.titre, t("Aucun paiement « Confirmé (à saisir) » : confirmez d'abord les virements."))
            return
        if sage_ouvert():
            messagebox.showwarning(self.titre, t("Fermez Sage : l'application l'ouvre elle-même pour saisir "
                                                 "les paiements."))
            return
        liste = "\n".join(f"  • {p.avis.date_virement}  {p.fournisseur_sage} n° {p.facture} — {p.avis.montant:,.2f} $"
                          for p in confirmes)
        if not messagebox.askyesno(self.titre, t("Saisir {n} paiement(s) dans Sage (compte 1055, Comptant) ?\n\n{liste}\n\n"
                                                 "L'application ouvre Sage elle-même ; n'ouvrez pas Sage pendant ce temps.",
                                                 n=len(confirmes), liste=liste)):
            return
        self.resume.configure(text=t("Saisie des paiements dans Sage…"))

        def travail():
            import json
            import tempfile

            from .__main__ import commande_moteur
            from .sage_bureau import executer_sur_bureau_cache

            try:
                with tempfile.TemporaryDirectory() as dossier:
                    fichier = Path(dossier) / "bilan.json"
                    executer_sur_bureau_cache(commande_moteur() + ["payer-bureau", "--resultat", str(fichier)],
                                              self.racine)
                    resultat = json.loads(fichier.read_text(encoding="utf-8")) if fichier.exists() else {}
                bilan = t("{ok} paiement(s) saisi(s) sur {n}.", ok=len(resultat.get("payes", [])), n=len(confirmes))
                if resultat:
                    try:
                        from .courriel import envoyer_bilan_paiements
                        envoyer_bilan_paiements(self._config(), resultat)
                    except Exception as exc:  # le courriel ne doit pas masquer le résultat
                        resultat.setdefault("notes", []).append(f"Courriel non envoyé : {exc}")
                notes = resultat.get("payes", []) + resultat.get("a_verifier", []) + (
                    [resultat["erreur"]] if resultat.get("erreur") else []) + resultat.get("notes", [])
            except Exception as exc:
                bilan, notes = f"✘ {exc}", []
            message = bilan + ("\n\n" + "\n".join(notes) if notes else "")
            self.after(0, lambda: (messagebox.showinfo(self.titre, message), self._recharger()))

        threading.Thread(target=travail, daemon=True).start()

    def _recharger(self) -> None:
        """Le robot a mis à jour le registre (paiements « Saisi dans Sage ») : on le relit."""
        self.registre = RegistrePaiements(self.racine)
        self.paiement = None
        self.afficher()

    def ignorer(self) -> None:
        if self.paiement:
            self.paiement.etat, self.paiement.remarque = IGNORE, t("ignoré par le propriétaire")
            self._apres()

    def remettre(self) -> None:
        if self.paiement and self.paiement.etat != SAISI:
            self.paiement.etat, self.paiement.facture, self.paiement.solde_facture = A_RELIER, "", None
            self.paiement.remarque = ""
            self._apres()
