"""Page « RIA > Opérations RIA » (demande du propriétaire du 2026-10-30) : mouvements RIA des relevés, surplus des
dépôts d'espèces, paiements en espèces, commissions, et leurs écritures dans Sage (ria.py)."""

from __future__ import annotations

import json
import tempfile
import threading
import tkinter as tk
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from tkinter import messagebox, simpledialog

from . import ria
from .design import montant_saisi
from .design import FenetreOutil, CARTE, ROUGE, TEXTE_DOUX, VERT_FONCE, Bouton, ChampDate, Rangee, action_permise
from .export_tableau import bouton_exporter
from .langues import t

ENTETES = ["Date", "Opération", "Description", "Montant", "État"]


def _config(racine: Path) -> dict:
    import tomllib

    chemin = Path(racine) / "config.toml"
    return tomllib.loads(chemin.read_text(encoding="utf-8")) if chemin.exists() else {}


def regler_comptes(parent, racine: Path) -> bool:
    """Comptes RIA, commissions et espèces (menu « RIA > Comptes RIA » ou bouton « Comptes… ») ; True si enregistrés."""
    titre = t("Comptes RIA")
    registre = ria.Registre(racine)
    for cle, libelle in ria.COMPTES.items():
        valeur = simpledialog.askstring(titre, t(libelle) + " :", initialvalue=registre.comptes.get(cle, ""),
                                        parent=parent)
        if valeur is None:
            return False
        registre.comptes[cle] = valeur.strip()
    from .plan_comptable import problemes, comptes_connus

    erreurs = problemes(registre.comptes.values(), comptes_connus(racine, _config(racine)))
    if erreurs:  # un compte saisi doit exister dans le plan comptable (règle du propriétaire du 2026-11-01)
        messagebox.showerror(titre, " ; ".join(erreurs) + ".\n\n" + t(
            "Créez-le dans « Comptabilité > Plan comptable »."), parent=parent)
        return False
    registre.enregistrer()
    return True


class FenetreRia(FenetreOutil):
    def __init__(self, parent, racine: Path):
        from .page_rapports import tableau_simple

        super().__init__(parent)
        self.racine = Path(racine)
        self.title(t("RIA (transferts d'argent)"))
        self.configure(background=CARTE, padx=14, pady=10)
        self.transient(parent)
        self.geometry("1120x680")
        self.lignes: list[dict] = []
        barre = Rangee(self)
        barre.pack(fill="x")
        g = barre.ajouter(barre.groupe(), 10)
        tk.Label(g, text=t("Du"), background=CARTE).pack(side="left")
        self.du = tk.StringVar(value=(date.today() - timedelta(days=45)).isoformat())
        ChampDate(g, self.du, fond=CARTE).pack(side="left", padx=4)
        tk.Label(g, text=t("au"), background=CARTE).pack(side="left")
        self.au = tk.StringVar(value=date.today().isoformat())
        ChampDate(g, self.au, fond=CARTE).pack(side="left", padx=4)
        barre.ajouter(Bouton(barre, "🔄  " + t("Actualiser"), self.actualiser, fond=CARTE, petit=True), 10)
        for texte, commande in (("✔  " + t("Confirmer le surplus"), self.confirmer_surplus),
                                ("💵  " + t("Commission"), self.basculer_commission),
                                ("➕  " + t("Paiement en espèces…"), self.paiement_especes),
                                ("🗑  " + t("Supprimer"), self.supprimer),
                                ("🔢  " + t("Comptes…"), self.reglages)):
            barre.ajouter(Bouton(barre, texte, commande, "secondaire", fond=CARTE, petit=True), 10)
        self.bouton_sage = Bouton(barre, "📒  " + t("Saisir dans Sage"), self.saisir, "accent", fond=CARTE, petit=True)
        barre.ajouter(self.bouton_sage, 10)
        barre.ajouter(Bouton(barre, "📑  " + t("États de compte RIA…"), self.ouvrir_etats, "secondaire", fond=CARTE,
                             petit=True), 10)
        self.etat = tk.Label(self, text="", background=CARTE, foreground=TEXTE_DOUX, anchor="w", justify="left",
                             wraplength=1080)
        self.etat.pack(fill="x", pady=(6, 0))
        self.cartes = tk.Frame(self, background=CARTE)
        self.cartes.pack(fill="x", pady=(6, 2))
        self.tableau = tableau_simple(self, hauteur=15)
        self.tableau.configure(selectmode="extended")
        self.tableau.tag_configure("a_confirmer", background="#e4ecfb")
        self.tableau.tag_configure("a_saisir", background="#fff4d6")
        self.tableau.tag_configure("fait", foreground="#7d8b81")
        barre.ajouter(bouton_exporter(barre, self.tableau, lambda: t("Opérations RIA")))
        self.actualiser()

    def ouvrir_etats(self) -> None:
        FenetreEtatsRia(self, self.racine)

    def _periode(self) -> tuple[date, date] | None:
        try:
            return date.fromisoformat(self.du.get().strip()), date.fromisoformat(self.au.get().strip())
        except ValueError:
            self.etat.configure(text="✘ " + t("Date au format AAAA-MM-JJ."), foreground=ROUGE)
            return None

    def actualiser(self) -> None:
        periode = self._periode()
        if not periode:
            return
        du, au = periode
        self.etat.configure(text=t("Lecture des relevés, de Clover et de Sage…"), foreground=TEXTE_DOUX)

        def travail():
            from .__main__ import charger_config, lire_sage
            from .api_clover import ClientClover
            from .encaissements import calculer, numero_compte_sage
            from .points_vente import points_de_vente
            from .rapprochement import RegistreReleves, mouvements_sage, periode_des, rapprocher

            config = _config(self.racine)

            def lire(base):
                releves = RegistreReleves(self.racine).lire()
                bornes = periode_des(releves)
                if not bornes:
                    return [], []
                banque = [m for r in releves for m in r.mouvements]
                rapprocher(banque, mouvements_sage(base, bornes[0] - timedelta(days=7), bornes[1] + timedelta(days=7)))
                mouvements = [m for m in banque if ria.est_ria(m) and du <= date.fromisoformat(m.date) <= au]
                depots = []
                try:
                    pdv = next(p for p in points_de_vente(config, actifs=True) if p.principal)
                    client = ClientClover(charger_config(self.racine / "config.toml", pdv))
                    compte = numero_compte_sage(config.get("encaissements", {}).get("compte_depot", "1055"))
                    depots = calculer(client, base, pdv.client_sage, compte, du, au, racine=self.racine,
                                      prefixe=pdv.prefixe)
                except (Exception, SystemExit):
                    pass  # Clover illisible : mouvements du relevé seulement
                return mouvements, depots

            try:
                mouvements, depots = lire_sage(config, lire, config.get("sage_import", {}).get("fichier_entreprise"))
                self.after(0, lambda: self._afficher(mouvements, depots, du, au))
            except Exception as exc:
                texte = str(exc)
                self.after(0, lambda: self.etat.configure(text="✘ " + texte, foreground=ROUGE))

        threading.Thread(target=travail, daemon=True).start()

    def _afficher(self, mouvements, depots, du: date, au: date) -> None:
        from .page_rapports import montant, remplir

        registre = ria.Registre(self.racine)
        # dépôt RIA égal à la commission payée d'un état de compte : marqué « Commission » d'office
        from .ria_etats import Registre as RegistreEtats, commissions_reconnues

        nouvelles = [c for c in commissions_reconnues(mouvements, RegistreEtats(self.racine).etats)
                     if c not in registre.commissions]
        if nouvelles:
            registre.commissions += nouvelles
            registre.enregistrer()
        self.lignes, bilan = registre.lignes(mouvements, depots, du, au)
        for enfant in self.cartes.winfo_children():
            enfant.destroy()
        for i, (titre, valeur) in enumerate((("Dépôts de RIA", bilan.depots), ("Surplus de dépôts", bilan.surplus),
                                             ("Retraits par RIA", bilan.retraits), ("Paiements", bilan.paiements),
                                             ("Commissions", bilan.commissions), ("Solde dû à RIA", bilan.solde))):
            carte = tk.Frame(self.cartes, background="#f4f9f5", highlightthickness=1, highlightbackground="#e1ece4")
            carte.grid(row=0, column=i, sticky="nsew", padx=3)
            self.cartes.columnconfigure(i, weight=1, uniform="r")
            tk.Label(carte, text=t(titre), background="#f4f9f5", foreground=TEXTE_DOUX, font=("Segoe UI", 9),
                     anchor="w").pack(fill="x", padx=8, pady=(5, 0))
            tk.Label(carte, text=montant(valeur), background="#f4f9f5", foreground=VERT_FONCE,
                     font=("Segoe UI Semibold", 13), anchor="w").pack(fill="x", padx=8, pady=(0, 5))

        def couleur(i):
            l = self.lignes[i]
            if l["sorte"] == "surplus":
                return ("a_confirmer",)
            return ("fait",) if l["etat"] in ("Dans Sage", ria.SAISIE) else ("a_saisir",)

        remplir(self.tableau, ENTETES, [[l["date"], t(l["genre"]), l["description"], l["montant"], t(l["etat"])]
                                        for l in self.lignes],
                {"Description": 480, "Opération": 200, "État": 170}, couleur, decroissant=False)
        manquants = registre.comptes_manquants()
        texte = t("{n} opération(s). Bleu : surplus à confirmer ; jaune : à saisir dans Sage.", n=len(self.lignes))
        if manquants:
            texte += " " + t("⚠ Comptes à renseigner (« Comptes… ») : {c}", c=", ".join(t(m) for m in manquants))
        self.etat.configure(text=texte, foreground=ROUGE if manquants else TEXTE_DOUX)

    def _choisies(self) -> list[dict]:
        choix = [self.lignes[int(i)] for i in self.tableau.selection()]
        if not choix:
            messagebox.showinfo(self.title(), t("Choisissez une ou plusieurs lignes dans la liste."), parent=self)
        return choix

    def confirmer_surplus(self) -> None:
        """La part de RIA du dépôt est retenue : l'écriture se saisit, puis le reste s'encaisse sur les ventes."""
        choix = [l for l in self._choisies() if l["sorte"] == "surplus"]
        if not choix:
            return
        registre = ria.Registre(self.racine)
        try:
            for l in choix:
                d = l["depot"]
                registre.ajouter(d.date.isoformat(), ria.SURPLUS, d.ria, d.origine, d.cle, self._auteur())
        except ValueError as exc:
            messagebox.showerror(self.title(), t(str(exc)), parent=self)
            return
        registre.enregistrer()
        self.actualiser()

    def _auteur(self) -> str:
        widget = self.master
        while widget is not None and not getattr(widget, "session", None):
            widget = widget.master
        return widget.session.nom if widget is not None else ""

    def basculer_commission(self) -> None:
        """Un dépôt de RIA choisi devient une commission (revenu), ou redevient un dépôt."""
        choix = [l for l in self._choisies() if l["sorte"] == "releve" and l["montant"] > 0]
        if not choix:
            return
        registre = ria.Registre(self.racine)
        for l in choix:
            cle = l["mouvement"].cle
            if cle in registre.commissions:
                registre.commissions.remove(cle)
            else:
                registre.commissions.append(cle)
        registre.enregistrer()
        self.actualiser()

    def paiement_especes(self) -> None:
        jour = simpledialog.askstring(self.title(), t("Date du paiement (AAAA-MM-JJ) :"),
                                      initialvalue=date.today().isoformat(), parent=self)
        if not jour:
            return
        texte = simpledialog.askstring(self.title(), t("Montant payé en espèces :"), parent=self)
        if not texte:
            return
        description = simpledialog.askstring(self.title(), t("Description (facultatif) :"), parent=self) or ""
        registre = ria.Registre(self.racine)
        try:
            registre.ajouter(jour.strip(), ria.ESPECES, montant_saisi(texte), description,
                             auteur=self._auteur())
        except (ValueError, InvalidOperation) as exc:
            messagebox.showerror(self.title(), t("Montant ou date invalide.") + f"\n{exc}", parent=self)
            return
        registre.enregistrer()
        self.actualiser()

    def supprimer(self) -> None:
        choix = [l for l in self._choisies() if l["sorte"] == "operation"]
        if not choix:
            return
        registre = ria.Registre(self.racine)
        try:
            for l in choix:
                registre.supprimer(l["operation"].numero)
        except ValueError as exc:
            messagebox.showerror(self.title(), t(str(exc)), parent=self)
            return
        registre.enregistrer()
        self.actualiser()

    def reglages(self) -> None:
        if regler_comptes(self, self.racine):
            self.actualiser()

    def saisir(self) -> None:
        """Mouvements RIA du relevé (compte choisi d'après leur sorte) et opérations : écritures de journal général."""
        from .rapprochement import A_SAISIR as ABSENT, CONFIRME, RegistreReleves
        from .sage_bureau import sage_ouvert

        if not action_permise(self, "Saisir les dépenses dans Sage"):
            return
        registre = ria.Registre(self.racine)
        manquants = registre.comptes_manquants()
        if manquants:
            messagebox.showwarning(self.title(), t("Comptes à renseigner (« Comptes… ») : {c}",
                                                   c=", ".join(t(m) for m in manquants)), parent=self)
            return
        if sage_ouvert():
            messagebox.showwarning(self.title(), t("Fermez Sage : l'application l'ouvre elle-même."), parent=self)
            return
        a_saisir = [l for l in self.lignes if l["sorte"] == "releve" and l["mouvement"].etat in (ABSENT, CONFIRME)]
        operations = registre.mouvements_a_saisir()
        if not a_saisir and not operations:
            messagebox.showinfo(self.title(), t("Rien à saisir dans Sage."), parent=self)
            return
        if not messagebox.askyesno(self.title(), t("Saisir {n} écriture(s) RIA dans Sage ?",
                                                   n=len(a_saisir) + len(operations)), parent=self):
            return
        releves = RegistreReleves(self.racine)
        for l in a_saisir:
            m = l["mouvement"]
            m.compte = registre.comptes["commissions" if l["genre"] == ria.COMMISSION else "ria"]
            m.etat = CONFIRME
            releves.retenir(m)
        releves.enregistrer()
        self.bouton_sage._commande = None
        self.etat.configure(text=t("Saisie dans Sage… (l'application ouvre Sage elle-même)"), foreground=TEXTE_DOUX)

        def travail():
            from .__main__ import commande_moteur
            from .sage_bureau import executer_sur_bureau_cache

            try:
                with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as dossier:
                    fichier = Path(dossier) / "bilan.json"
                    executer_sur_bureau_cache(commande_moteur() + ["journal-bureau", "--resultat", str(fichier)],
                                              self.racine)
                    bilan = json.loads(fichier.read_text(encoding="utf-8")) if fichier.exists() else {}
            except Exception as exc:
                bilan = {"erreur": str(exc)}
            self.after(0, lambda: self._fin_saisie(bilan))

        threading.Thread(target=travail, daemon=True).start()

    def _fin_saisie(self, bilan: dict) -> None:
        self.bouton_sage._commande = self.saisir
        details = bilan.get("a_verifier", []) + ([bilan["erreur"]] if bilan.get("erreur") else [])
        message = t("{n} écriture(s) enregistrée(s).", n=len(bilan.get("saisis", [])))
        messagebox.showinfo(self.title(), message + ("\n\n" + "\n".join(details[:15]) if details else ""), parent=self)
        self.actualiser()


class FenetreEtatsRia(FenetreOutil):
    """États de compte RIA importés (PDF « Account Statement ») : à la main ou depuis la boîte de courriel
    configurée ([ria] courriel). En haut les états, en bas les opérations de l'état choisi."""

    ENTETES = ["Du", "au", "Agence", "Solde précédent", "Envois (débits)", "Versements (crédits)", "Solde",
               "Commission payée", "Commission courue", "Dernier dépôt RIA", "Contrôle"]

    def __init__(self, parent, racine: Path):
        from .page_rapports import tableau_simple

        super().__init__(parent)
        self.page_ria = parent  # « Traiter dans Sage » passe par sa saisie
        self.racine = Path(racine)
        self.title(t("États de compte RIA"))
        self.configure(background=CARTE, padx=14, pady=10)
        self.transient(parent)
        self.geometry("1180x700")
        barre = Rangee(self)
        barre.pack(fill="x")
        barre.ajouter(Bouton(barre, "📥  " + t("Importer des états…"), self.importer, fond=CARTE, petit=True), 10)
        barre.ajouter(Bouton(barre, "📧  " + t("Lire le courriel"), self.lire_courriel, "secondaire", fond=CARTE,
                             petit=True), 10)
        barre.ajouter(Bouton(barre, "👁  " + t("Voir l'état"), self.voir, "secondaire", fond=CARTE, petit=True), 10)
        barre.ajouter(Bouton(barre, "🗑  " + t("Supprimer"), self.supprimer, "danger", fond=CARTE, petit=True), 10)
        barre.ajouter(Bouton(barre, "📒  " + t("Traiter dans Sage"), self.traiter, "accent", fond=CARTE, petit=True), 10)
        self.etat = tk.Label(self, text="", background=CARTE, foreground=TEXTE_DOUX, anchor="w", justify="left",
                             wraplength=1120)
        self.etat.pack(fill="x", pady=(6, 0))
        self.tableau = tableau_simple(self, hauteur=8)
        self.tableau.bind("<<TreeviewSelect>>", lambda _e: self.detail())
        self.tableau.bind("<Double-1>", lambda _e: self.voir())
        tk.Label(self, text=t("Opérations de l'état choisi"), font=("Segoe UI Semibold", 10), background=CARTE,
                 anchor="w").pack(fill="x", pady=(8, 0))
        self.lignes = tableau_simple(self, hauteur=10)
        barre.ajouter(bouton_exporter(barre, self.tableau, lambda: t("États de compte RIA")))
        self.afficher()

    def afficher(self) -> None:
        from .page_rapports import remplir
        from .ria_etats import Registre

        self.etats = Registre(self.racine).etats
        remplir(self.tableau, self.ENTETES,
                [[e.debut, e.fin, e.agence, Decimal(e.solde_precedent), Decimal(e.debits), Decimal(e.credits),
                  Decimal(e.total), Decimal(e.commission_payee), Decimal(e.commission_courue),
                  f"{e.dernier_depot} — {e.montant_dernier_depot} $" if e.dernier_depot else "",
                  "✔" if not e.remarques else "⚠ " + " ".join(e.remarques)] for e in self.etats],
                {"Contrôle": 260}, decroissant=False)
        self.etat.configure(text=t("{n} état(s). Solde négatif : RIA doit au marché ; positif : le marché doit à "
                                   "RIA. La commission payée reconnaît son dépôt dans le relevé de la caisse.",
                                   n=len(self.etats)), foreground=TEXTE_DOUX)
        if self.etats:
            self.tableau.selection_set("0")

    def _choisi(self):
        choix = self.tableau.selection()
        return self.etats[int(choix[0])] if choix else None

    def detail(self) -> None:
        from .page_rapports import remplir

        e = self._choisi()
        remplir(self.lignes, ["Date", "Opération", "Réf.", "Description", "Montant", "Frais", "Commission",
                              "Débit / crédit", "Solde"],
                [[l.jour, l.activite, l.reference, l.description, Decimal(l.montant), Decimal(l.frais),
                  Decimal(l.commission), Decimal(l.mouvement), Decimal(l.solde)] for l in (e.lignes if e else [])],
                decroissant=False)

    def importer(self) -> None:
        from tkinter import filedialog

        from .ria_etats import Registre

        chemins = filedialog.askopenfilenames(parent=self, title=t("États de compte RIA (PDF)"),
                                              filetypes=[("PDF", "*.pdf")])
        if not chemins:
            return
        registre, messages = Registre(self.racine), []
        for chemin in chemins:
            try:
                e, nouveau = registre.importer(Path(chemin))
                messages.append(("✔ " if nouveau else "• ") + f"{Path(chemin).name} : {e.debut} → {e.fin}"
                                + ("" if nouveau else " " + t("(déjà importé)")))
            except Exception as exc:
                messages.append(f"✘ {Path(chemin).name} : {t(str(exc))}")
        registre.enregistrer()
        self.afficher()
        messagebox.showinfo(self.title(), "\n".join(messages), parent=self)

    def lire_courriel(self) -> None:
        from .ria_etats import configuree, recuperer

        config = _config(self.racine)
        if not configuree(config):
            messagebox.showinfo(self.title(), t("Renseignez le courriel de réception des états RIA dans "
                                                "« Administration > Courriel », carte « États RIA »."), parent=self)
            return
        self.etat.configure(text=t("Lecture de la boîte de courriel…"), foreground=TEXTE_DOUX)

        def travail():
            try:
                nouveaux = recuperer(self.racine, config)
                texte = t("{n} nouvel(s) état(s) RIA.", n=len(nouveaux))
            except Exception as exc:
                texte = "✘ " + str(exc)
            self.after(0, lambda: (self.afficher(), self.etat.configure(text=texte)))

        threading.Thread(target=travail, daemon=True).start()

    def traiter(self) -> None:
        """Opérations de comptoir des états (envois, versements en espèces) créées puis saisies dans Sage avec les
        autres opérations RIA (fenêtre RIA, « Saisir dans Sage »)."""
        from .rapprochement import RegistreReleves
        from .ria_etats import operations_des_etats

        banque = [m for r in RegistreReleves(self.racine).lire() for m in r.mouvements]
        crees = operations_des_etats(self.racine, banque)
        manquants = ria.Registre(self.racine).comptes_manquants()
        texte = t("{n} opération(s) créée(s) depuis les états.", n=crees)
        if manquants:
            messagebox.showwarning(self.title(), texte + "\n\n" + t("Comptes à renseigner (« Comptes… ») : {c}",
                                                                    c=", ".join(t(m) for m in manquants)), parent=self)
            return
        if hasattr(self.page_ria, "saisir"):
            self.page_ria.saisir()
        else:  # ouvert par le menu : la saisie se fait dans « RIA > Opérations RIA »
            texte += " " + t("Saisie : « RIA > Opérations RIA » puis « Saisir dans Sage ».")
            messagebox.showinfo(self.title(), texte, parent=self)
        self.etat.configure(text=texte, foreground=VERT_FONCE)

    def voir(self) -> None:
        import os

        e = self._choisi()
        if e:
            chemin = self.racine / "donnees" / "etats_ria" / e.fichier
            if chemin.exists():
                os.startfile(chemin)

    def supprimer(self) -> None:
        from .ria_etats import Registre

        e = self._choisi()
        if e and messagebox.askyesno(self.title(), t("Retirer l'état du {d} au {f} ?", d=e.debut, f=e.fin),
                                     parent=self):
            registre = Registre(self.racine)
            registre.supprimer(e.cle)
            registre.enregistrer()
            self.afficher()
