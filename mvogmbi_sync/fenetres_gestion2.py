"""Fenêtres des fonctions ajoutées le 2026-10-29 (« ajoute les fonctions manquantes ») : petite caisse et dépenses,
fin d'emploi (préparation du RE), journal des opérations. Calculs dans depenses.py, fin_emploi.py,
journal_operations.py."""

from __future__ import annotations

import os
import threading
import tkinter as tk
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from .design import FenetreOutil, CARTE, ROUGE, TEXTE_DOUX, VERT_FONCE, Bouton, ChampDate, Rangee
from .export_tableau import bouton_exporter
from .langues import t


def _config(racine: Path) -> dict:
    import tomllib

    chemin = Path(racine) / "config.toml"
    return tomllib.loads(chemin.read_text(encoding="utf-8")) if chemin.exists() else {}


def _argent(v) -> str:
    return f"{Decimal(v):,.2f} $".replace(",", " ").replace(".", ",")


def _fil(fenetre, travail, fin, etat: tk.Label, message: str) -> None:
    etat.configure(text=t(message), foreground=TEXTE_DOUX)

    def executer():
        try:
            r = travail()
            fenetre.after(0, lambda: fin(r))
        except BaseException as exc:  # SystemExit compris
            texte = str(exc) or type(exc).__name__
            fenetre.after(0, lambda: etat.configure(text="✘ " + texte, foreground=ROUGE))

    threading.Thread(target=executer, daemon=True).start()


# --------------------------------------------------------------------------------------------- dépenses
class FenetreDepenses(FenetreOutil):
    def __init__(self, parent, racine: Path, auteur: str = ""):
        from . import depenses as dp
        from .page_rapports import tableau_simple
        from .taxes import CHOIX

        super().__init__(parent)
        self.racine, self.auteur, self.dp = Path(racine), auteur, dp
        self.title(t("Petite caisse et dépenses"))
        self.configure(background=CARTE, padx=14, pady=10)
        self.geometry("1150x640")
        forme = Rangee(self)
        forme.pack(fill="x")
        self.v = {c: tk.StringVar() for c in ("jour", "fournisseur", "description", "montant", "compte", "recu")}
        self.v["jour"].set(date.today().isoformat())
        g = forme.ajouter(forme.groupe(), 8)
        tk.Label(g, text=t("Date"), background=CARTE).pack(side="left", padx=(0, 4))
        ChampDate(g, self.v["jour"], fond=CARTE).pack(side="left")
        for cle, libelle, largeur in (("fournisseur", "Fournisseur", 18), ("description", "Description", 22),
                                      ("montant", "Montant payé (taxes comprises)", 9), ("compte", "Compte de charge", 6)):
            g = forme.ajouter(forme.groupe(), 8)
            tk.Label(g, text=t(libelle), background=CARTE).pack(side="left", padx=(0, 4))
            ttk.Entry(g, textvariable=self.v[cle], width=largeur).pack(side="left")
        self.choix_taxes = CHOIX
        g = forme.ajouter(forme.groupe(), 8)
        tk.Label(g, text=t("Taxes"), background=CARTE).pack(side="left", padx=(0, 4))
        self.taxe = tk.StringVar(value=t(CHOIX["GQ"]))
        ttk.Combobox(g, textvariable=self.taxe, values=[t(x) for x in CHOIX.values()], state="readonly",
                     width=14).pack(side="left")
        g = forme.ajouter(forme.groupe(), 8)
        tk.Label(g, text=t("Payée par"), background=CARTE).pack(side="left", padx=(0, 4))
        self.moyen = tk.StringVar(value=t(dp.PETITE_CAISSE))
        ttk.Combobox(g, textvariable=self.moyen, values=[t(m) for m in dp.MOYENS + [dp.APPRO]], state="readonly",
                     width=24).pack(side="left")
        forme.ajouter(Bouton(forme, "📎  " + t("Reçu…"), self.choisir_recu, "secondaire", fond=CARTE, petit=True), 6)
        forme.ajouter(Bouton(forme, "➕  " + t("Ajouter"), self.ajouter, fond=CARTE, petit=True), 6)
        barre = Rangee(self)
        barre.pack(fill="x", pady=(8, 0))
        barre.ajouter(Bouton(barre, "🧾  " + t("Saisir dans Sage"), self.saisir_sage, fond=CARTE, petit=True), 6)
        barre.ajouter(Bouton(barre, "🔢  " + t("Comptes Sage…"), self.comptes, "secondaire", fond=CARTE, petit=True), 6)
        barre.ajouter(Bouton(barre, "👁  " + t("Voir le reçu"), self.voir_recu, "secondaire", fond=CARTE, petit=True),
                      6)
        self.etat = tk.Label(self, text="", background=CARTE, foreground=TEXTE_DOUX, anchor="w", justify="left",
                             wraplength=1100)
        self.etat.pack(fill="x", pady=(6, 0))
        self.tableau = tableau_simple(self, hauteur=15)
        barre.ajouter(bouton_exporter(barre, self.tableau, lambda: t("Dépenses")))
        self.afficher()

    def afficher(self) -> None:
        from .page_rapports import remplir

        r = self.dp.Registre(self.racine)
        self.liste = sorted(r.depenses, key=lambda d: (d.jour, d.numero), reverse=True)
        remplir(self.tableau, ["Date", "N°", "Fournisseur", "Description", "Montant", "Taxes", "Compte", "Payée par",
                               "Reçu", "État"],
                [[d.jour, d.numero, d.fournisseur, d.description, Decimal(d.montant), d.taxe or "—", d.compte,
                  t(d.moyen), "📎" if d.recu else "", t(d.etat) + (f" n° {d.ecriture}" if d.ecriture else "")]
                 for d in self.liste], {"Description": 220, "Payée par": 150})
        manquants = r.comptes_manquants([d for d in r.depenses if d.etat == self.dp.A_SAISIR])
        self.etat.configure(text=t("Solde de la petite caisse : {s}", s=_argent(r.solde_petite_caisse()))
                            + (" — ⚠ " + t("Comptes Sage à choisir : {c}", c=", ".join(t(x) for x in manquants))
                               if manquants else ""), foreground=ROUGE if manquants else TEXTE_DOUX)

    def choisir_recu(self) -> None:
        chemin = filedialog.askopenfilename(parent=self, title=t("Reçu (photo ou PDF)"),
                                            filetypes=[("Reçu", "*.jpg *.jpeg *.png *.pdf *.heic"), ("*", "*.*")])
        if chemin:
            self.v["recu"].set(chemin)
            self.etat.configure(text=t("Reçu choisi : {f}", f=Path(chemin).name), foreground=TEXTE_DOUX)

    def ajouter(self) -> None:
        dp = self.dp
        moyen = next((m for m in dp.MOYENS + [dp.APPRO] if t(m) == self.moyen.get()), dp.PETITE_CAISSE)
        taxe = next((k for k, v in self.choix_taxes.items() if t(v) == self.taxe.get()), "GQ")
        try:
            montant = Decimal(self.v["montant"].get().replace(",", ".").replace(" ", "").strip())
            d = dp.Depense("", self.v["jour"].get().strip(), self.v["fournisseur"].get().strip(),
                           self.v["description"].get().strip(), str(montant), "" if moyen == dp.APPRO else taxe,
                           self.v["compte"].get().strip(), moyen, auteur=self.auteur)
            recu = Path(self.v["recu"].get()) if self.v["recu"].get() else None
            d = dp.Registre(self.racine).ajouter(d, recu)
        except (InvalidOperation, ValueError) as exc:
            self.etat.configure(text="✘ " + (t(str(exc)) if str(exc) else t("Montant invalide.")), foreground=ROUGE)
            return
        for c in ("fournisseur", "description", "montant", "recu"):
            self.v[c].set("")
        self.afficher()
        self.etat.configure(text=t("✔ {n} ajoutée.", n=d.numero), foreground=VERT_FONCE)

    def voir_recu(self) -> None:
        choix = self.tableau.selection()
        if choix and self.liste[int(choix[0])].recu:
            os.startfile(self.racine / "donnees" / "recus" / self.liste[int(choix[0])].recu)

    def comptes(self) -> None:
        """Comptes Sage de l'écriture : proposés d'après les noms des comptes de Sage, modifiables."""
        r = self.dp.Registre(self.racine)
        for cle, libelle in self.dp.COMPTES.items():
            valeur = simpledialog.askstring(self.title(), t("Compte Sage « {l} » (4 chiffres, vide si inutile) :",
                                                            l=t(libelle)), initialvalue=r.comptes.get(cle, ""),
                                            parent=self)
            if valeur is None:
                return
            r.comptes[cle] = valeur.strip()
        r.enregistrer()
        self.afficher()

    def saisir_sage(self) -> None:
        from .design import action_permise

        if not action_permise(self, "Saisir les dépenses dans Sage"):
            return
        r = self.dp.Registre(self.racine)
        a_faire = [d for d in r.depenses if d.etat == self.dp.A_SAISIR]
        if not a_faire:
            messagebox.showinfo(self.title(), t("Aucune dépense à saisir dans Sage."), parent=self)
            return
        if not r.comptes or not any(r.comptes.values()):
            def proposer():
                from .__main__ import lire_sage

                c = _config(self.racine)
                return lire_sage(c, self.dp.proposer_comptes, c.get("sage_import", {}).get("fichier_entreprise"))

            def fin(comptes):
                r2 = self.dp.Registre(self.racine)
                r2.comptes.update({k: v for k, v in comptes.items() if v})
                r2.enregistrer()
                self.comptes()

            _fil(self, proposer, fin, self.etat, "Lecture des comptes dans Sage…")
            return
        if not messagebox.askyesno(self.title(), t("Saisir {n} dépense(s) dans Sage (journal général) ? Sage doit être "
                                                   "fermé : l'application l'ouvre elle-même.", n=len(a_faire)),
                                   parent=self):
            return

        def travail():
            import json
            import tempfile

            from .__main__ import commande_moteur
            from .sage_bureau import executer_sur_bureau_cache, sage_ouvert

            if sage_ouvert():
                raise RuntimeError(t("Fermez Sage : l'application l'ouvre elle-même."))
            with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as dossier:
                bilan = Path(dossier) / "bilan.json"
                executer_sur_bureau_cache(commande_moteur() + ["depenses-bureau", "--resultat", str(bilan)],
                                          self.racine)
                return json.loads(bilan.read_text(encoding="utf-8")) if bilan.exists() else {"erreur": "?"}

        def fin(b):
            self.afficher()
            messagebox.showinfo(self.title(), "\n".join(b.get("saisies", []) + ["✘ " + x for x in b.get("a_verifier", [])]
                                                        + (["✘ " + b["erreur"]] if b.get("erreur") else []))
                                or t("Rien n'a été saisi."), parent=self)

        _fil(self, travail, fin, self.etat, "Saisie dans Sage… (l'application ouvre Sage elle-même)")


# --------------------------------------------------------------------------------------------- fin d'emploi
class FenetreFinEmploi(FenetreOutil):
    def __init__(self, parent, racine: Path):
        from . import fin_emploi as fe
        from . import paie_temps as pt
        from .page_rapports import tableau_simple

        super().__init__(parent)
        self.racine, self.fe, self.pt = Path(racine), fe, pt
        self.title(t("Fin d'emploi et relevé d'emploi"))
        self.configure(background=CARTE, padx=14, pady=10)
        self.geometry("980x620")
        forme = Rangee(self)
        forme.pack(fill="x")
        self.employes = {e.nom: e for e in sorted(pt.Registre(self.racine).employes, key=lambda e: e.nom.casefold())}
        g = forme.ajouter(forme.groupe(), 10)
        tk.Label(g, text=t("Employé") + " *", background=CARTE).pack(side="left", padx=(0, 4))
        self.employe = tk.StringVar()
        ttk.Combobox(g, textvariable=self.employe, values=list(self.employes), state="readonly",
                     width=26).pack(side="left")
        g = forme.ajouter(forme.groupe(), 10)
        tk.Label(g, text=t("Dernier jour travaillé"), background=CARTE).pack(side="left", padx=(0, 4))
        self.jour = tk.StringVar(value=date.today().isoformat())
        ChampDate(g, self.jour, fond=CARTE).pack(side="left")
        g = forme.ajouter(forme.groupe(), 10)
        tk.Label(g, text=t("Motif"), background=CARTE).pack(side="left", padx=(0, 4))
        self.motifs = {f"{k} — {t(v)}": k for k, v in fe.MOTIFS_RE.items()}
        self.motif = tk.StringVar(value=next(iter(self.motifs)))
        ttk.Combobox(g, textvariable=self.motif, values=list(self.motifs), state="readonly", width=40).pack(side="left")
        forme.ajouter(Bouton(forme, "🔍  " + t("Préparer le relevé d'emploi"), self.preparer, fond=CARTE, petit=True), 6)
        barre = Rangee(self)
        barre.pack(fill="x", pady=(8, 0))
        barre.ajouter(Bouton(barre, "🖨  " + t("Imprimer"), self.imprimer, "secondaire", fond=CARTE, petit=True), 6)
        barre.ajouter(Bouton(barre, "⏻  " + t("Désactiver l'employé (poste de pointage)"), self.desactiver, "danger",
                             fond=CARTE, petit=True), 6)
        self.etat = tk.Label(self, text=t("Le RE se produit dans RE Web de Service Canada (ou par Sage) dans les 5 jours ; "
                                          "l'application en prépare les données."), background=CARTE,
                             foreground=TEXTE_DOUX, anchor="w", justify="left", wraplength=940)
        self.etat.pack(fill="x", pady=(6, 0))
        self.tableau = tableau_simple(self, hauteur=16)
        self.document = None

    def _choix(self):
        e = self.employes.get(self.employe.get())
        try:
            jour = date.fromisoformat(self.jour.get().strip())
        except ValueError:
            jour = None
        if not e or not jour:
            self.etat.configure(text="✘ " + t("Choisissez l'employé et la date."), foreground=ROUGE)
        return e, jour

    def preparer(self) -> None:
        from .page_rapports import remplir

        e, jour = self._choix()
        if not e:
            return
        code = self.motifs[self.motif.get()]

        def travail():
            from . import paie as pa
            from .__main__ import lire_sage

            c = _config(self.racine)
            try:
                paies = lire_sage(c, lambda b: pa.paies_sage(b, jour - timedelta(days=400), jour + timedelta(days=21)),
                                  c.get("sage_import", {}).get("fichier_entreprise"))
            except Exception:
                paies = []  # Sage illisible : heures seulement
            return self.fe.preparation_re(self.pt.Registre(self.racine), e, paies, jour, code)

        def fin(resultat):
            lignes, sous_titre = resultat
            self.document = (lignes, sous_titre)
            remplir(self.tableau, ["Rubrique", "Valeur"], [[t(a), b] for a, b in lignes], {"Rubrique": 520},
                    decroissant=False)
            self.etat.configure(text=sous_titre, foreground=VERT_FONCE)

        _fil(self, travail, fin, self.etat, "Lecture des heures et des paies…")

    def imprimer(self) -> None:
        import tempfile
        from datetime import datetime

        from .export_tableau import autorise, page_html

        if not self.document or not autorise(self):
            return
        lignes, sous_titre = self.document
        dossier = Path(tempfile.gettempdir()) / "MVOGMBI_Sync_impression"
        dossier.mkdir(exist_ok=True)
        chemin = dossier / f"releve_emploi_{datetime.now():%Y%m%d_%H%M%S}.html"
        chemin.write_text(page_html(t("Préparation du relevé d'emploi"), ["Rubrique", "Valeur"], lignes,
                                    sous_titre=sous_titre, imprimer=True), encoding="utf-8")
        os.startfile(chemin)

    def desactiver(self) -> None:
        from .design import action_permise

        if not action_permise(self, "Désactiver un employé"):
            return
        e, _jour = self._choix()
        if not e or not messagebox.askyesno(self.title(), t("Désactiver {n} ? Il ne pourra plus pointer ; son "
                                                           "historique est gardé.", n=e.nom), parent=self):
            return
        registre = self.pt.Registre(self.racine)
        registre.employe(e.id).actif = False
        registre.enregistrer()
        self.etat.configure(text=t("✔ {n} désactivé. Pensez à le désactiver aussi dans Clover.", n=e.nom),
                            foreground=VERT_FONCE)


# --------------------------------------------------------------------------------------------- journal
class FenetreJournalOperations(FenetreOutil):
    def __init__(self, parent, racine: Path):
        from . import journal_operations as jo
        from .page_rapports import tableau_simple

        super().__init__(parent)
        self.racine, self.jo = Path(racine), jo
        self.title(t("Journal des opérations"))
        self.configure(background=CARTE, padx=14, pady=10)
        self.geometry("1150x640")
        barre = Rangee(self)
        barre.pack(fill="x")
        g = barre.ajouter(barre.groupe(), 10)
        tk.Label(g, text=t("Du"), background=CARTE).pack(side="left")
        self.du = tk.StringVar(value=(date.today() - timedelta(days=30)).isoformat())
        ChampDate(g, self.du, fond=CARTE).pack(side="left", padx=4)
        tk.Label(g, text=t("au"), background=CARTE).pack(side="left")
        self.au = tk.StringVar(value=date.today().isoformat())
        ChampDate(g, self.au, fond=CARTE).pack(side="left", padx=4)
        self.ops = jo.lire(self.racine)
        g = barre.ajouter(barre.groupe(), 10)
        tk.Label(g, text=t("Source"), background=CARTE).pack(side="left", padx=(0, 4))
        self.source = tk.StringVar(value=t("Toutes"))
        ttk.Combobox(g, textvariable=self.source, values=[t("Toutes")] + sorted({o.source for o in self.ops}),
                     state="readonly", width=26).pack(side="left")
        g = barre.ajouter(barre.groupe(), 10)
        tk.Label(g, text=t("Recherche"), background=CARTE).pack(side="left", padx=(0, 4))
        self.texte = tk.StringVar()
        ttk.Entry(g, textvariable=self.texte, width=22).pack(side="left")
        barre.ajouter(Bouton(barre, "🔍  " + t("Afficher"), self.afficher, fond=CARTE, petit=True), 10)
        self.etat = tk.Label(self, text="", background=CARTE, foreground=TEXTE_DOUX, anchor="w")
        self.etat.pack(fill="x", pady=(6, 0))
        self.tableau = tableau_simple(self, hauteur=18)
        barre.ajouter(bouton_exporter(barre, self.tableau, lambda: t("Journal des opérations")))
        self.afficher()

    def afficher(self) -> None:
        from .page_rapports import remplir

        source = "" if self.source.get() == t("Toutes") else self.source.get()
        ops = self.jo.filtrer(self.ops, self.du.get().strip(), self.au.get().strip(), source, self.texte.get())
        remplir(self.tableau, ["Date", "Source", "Personne", "Détail"],
                [[o.quand, o.source, o.personne, o.detail] for o in ops[:5000]], {"Source": 200, "Détail": 640})
        self.etat.configure(text=t("{n} opération(s)", n=len(ops)))
