"""Carte « Points de vente » de la page Clover : chaque point de vente Clover est un dépôt Sage (points_vente.py).

Le n° 1 est le point de vente d'origine (identifiant et jeton de la carte « Identifiants Clover ») : on n'y change que
son nom, son client et son dépôt Sage. Les suivants ont leur identifiant marchand, leur jeton (coffre-fort Windows),
leur client Sage, leur dépôt Sage et leur préfixe de facture.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from . import coffre
from .design import Bouton, cadre_tableau, defilement, rayer
from .langues import t
from .points_vente import (DEPOT_DEFAUT, LONGUEUR_PREFIXE, PRINCIPAL, PointDeVente, points_de_vente,
                           problemes_configuration)

COLONNES = (("code", "N°", 40), ("nom", "Nom", 170), ("marchand", "Identifiant marchand", 150),
            ("jeton", "Jeton", 60), ("client", "Client Sage", 170), ("depot", "Dépôt Sage", 170),
            ("prefixe", "Préfixe", 70), ("actif", "Actif", 50))


class CartePointsVente:
    """Liste des points de vente et boutons Ajouter / Modifier / Supprimer / Tester."""

    def __init__(self, app, zone):
        self.app = app
        cadre = cadre_tableau(zone)
        cadre.grid(row=0, column=0, columnspan=3, sticky="we")
        self.tableau = ttk.Treeview(cadre, columns=[c for c, _, _ in COLONNES], show="headings", height=4,
                                    selectmode="browse")
        for cle, titre, largeur in COLONNES:
            self.tableau.heading(cle, text=t(titre))
            self.tableau.column(cle, width=largeur, stretch=cle in ("nom", "client", "depot"),
                                anchor="center" if cle in ("code", "jeton", "actif", "prefixe") else "w")
        self.tableau.pack(side="left", fill="x", expand=True, padx=1, pady=1)
        defilement(self.tableau)
        self.tableau.bind("<Double-Button-1>", lambda _e: self.modifier())
        boutons = ttk.Frame(zone, style="Carte.TFrame")
        boutons.grid(row=1, column=0, columnspan=3, sticky="w", pady=(8, 0))
        Bouton(boutons, "➕  " + t("Ajouter un point de vente"), self.ajouter, petit=True).pack(side="left")
        Bouton(boutons, t("Modifier"), self.modifier, "secondaire", petit=True).pack(side="left", padx=(8, 0))
        Bouton(boutons, t("Supprimer"), self.supprimer, "danger", petit=True).pack(side="left", padx=(8, 0))
        Bouton(boutons, "🔌  " + t("Tester ce point de vente"), self.tester, "secondaire", petit=True).pack(
            side="left", padx=(8, 0))
        self.remplir()

    # ------------------------------------------------------------------------------------------------ données
    def points(self) -> list[PointDeVente]:
        return points_de_vente(self.app.config_toml)

    def remplir(self) -> None:
        self.tableau.delete(*self.tableau.get_children())
        for p in self.points():
            jeton = coffre.present(p.cle_jeton)
            self.tableau.insert("", "end", iid=p.code, values=(
                p.code, p.nom, p.merchant_id or "—", "✔" if jeton else "✘", p.client_sage, p.depot_sage, p.prefixe,
                t("Oui") if p.actif else t("Non")))
        rayer(self.tableau)

    def courant(self) -> PointDeVente | None:
        choix = self.tableau.selection()
        return next((p for p in self.points() if choix and p.code == choix[0]), None)

    def _enregistrer(self, points: list[PointDeVente]) -> bool:
        if erreurs := problemes_configuration(points):
            messagebox.showerror(t("Points de vente"), "\n".join(erreurs), parent=self.app)
            return False
        from .interface import ecrire_config

        c = self.app.config_toml
        principal = points[0]
        c.setdefault("clover", {}).update(nom=principal.nom, client_sage=principal.client_sage,
                                          depot_sage=principal.depot_sage)
        c["points_vente"] = [dict(code=p.code, nom=p.nom, merchant_id=p.merchant_id, client_sage=p.client_sage,
                                  depot_sage=p.depot_sage, prefixe=p.prefixe, actif=p.actif) for p in points[1:]]
        if not c["points_vente"]:
            c.pop("points_vente")
        ecrire_config(self.app.chemin_config, c)
        self.remplir()
        return True

    # ------------------------------------------------------------------------------------------------ actions
    def ajouter(self) -> None:
        codes = {p.code for p in self.points()}
        code = next(str(n) for n in range(2, 100) if str(n) not in codes)
        Fiche(self, PointDeVente(code, f"Point de vente {code}", "", "", DEPOT_DEFAUT, f"V{code}", True), nouveau=True)

    def modifier(self) -> None:
        p = self.courant()
        if p is None:
            messagebox.showinfo(t("Points de vente"), t("Sélectionnez un point de vente dans la liste."), parent=self.app)
            return
        Fiche(self, p)

    def supprimer(self) -> None:
        p = self.courant()
        if p is None:
            return
        if p.principal:
            messagebox.showinfo(t("Points de vente"), t("Le point de vente n° 1 ne peut pas être supprimé."),
                                parent=self.app)
            return
        if not messagebox.askyesno(t("Points de vente"), t("Supprimer le point de vente {nom} ? Ses factures déjà "
                                                           "dans Sage ne sont pas touchées.", nom=p.libelle),
                                   parent=self.app):
            return
        if self._enregistrer([x for x in self.points() if x.code != p.code]):
            coffre.supprimer(p.cle_jeton)

    def tester(self) -> None:
        p = self.courant()
        if p is None:
            messagebox.showinfo(t("Points de vente"), t("Sélectionnez un point de vente dans la liste."), parent=self.app)
            return

        def test():
            from .__main__ import charger_config
            from .api_clover import ClientClover

            try:
                config = charger_config(self.app.chemin_config, p)
            except SystemExit as exc:
                raise RuntimeError(str(exc)) from None
            return t("connecté à « {nom} »", nom=ClientClover(config).marchand().get("name", "?"))

        self.app._tache(t("Test Clover") + f" ({p.libelle})", test, self.app.sortie_clover)


class Fiche(tk.Toplevel):
    """Fenêtre de saisie d'un point de vente."""

    def __init__(self, carte: CartePointsVente, p: PointDeVente, nouveau: bool = False):
        super().__init__(carte.app)
        self.carte, self.p, self.nouveau = carte, p, nouveau
        self.title(t("Point de vente {code}", code=p.code))
        self.transient(carte.app)
        self.resizable(False, False)
        corps = ttk.Frame(self, padding=16)
        corps.pack(fill="both", expand=True)
        self.vars: dict[str, tk.Variable] = {}
        lignes = [("nom", t("Nom"), p.nom, "")]
        if not p.principal:
            lignes += [("marchand", t("Identifiant marchand"), p.merchant_id,
                        t("13 caractères, dans l'adresse du tableau de bord Clover de ce point de vente.")),
                       ("jeton", t("Jeton API"), "",
                        t("Laissez vide pour conserver le jeton enregistré.") if coffre.present(p.cle_jeton) else
                        t("Clover > Compte et configuration > Jetons API (droits en lecture)."))]
        lignes += [("client", t("Client Sage"), p.client_sage,
                    t("Client des factures de ce point de vente (fiche : « Ce client utilise mes n° articles »).")),
                   ("depot", t("Dépôt Sage"), p.depot_sage,
                    t("Emplacement d'inventaire Sage de ce point de vente (« {d} » par défaut).", d=DEPOT_DEFAUT))]
        if not p.principal:
            lignes.append(("prefixe", t("Préfixe des factures"), p.prefixe,
                           t("{n} caractères au plus, sans espace : « {p} 2026-10-23/25 ».", n=LONGUEUR_PREFIXE,
                             p=p.prefixe or "V2")))
        self.libelles = {cle: libelle for cle, libelle, _, _ in lignes}
        self.jeton_present = not p.principal and coffre.present(p.cle_jeton)
        for i, (cle, libelle, valeur, aide) in enumerate(lignes):
            obligatoire = cle != "jeton" or not self.jeton_present  # tous obligatoires (demande du propriétaire)
            ttk.Label(corps, text=libelle + (" *" if obligatoire else "")).grid(row=2 * i, column=0, sticky="w", pady=(4, 0), padx=(0, 12))
            self.vars[cle] = tk.StringVar(value=valeur)
            ttk.Entry(corps, textvariable=self.vars[cle], width=44, show="•" if cle == "jeton" else "").grid(
                row=2 * i, column=1, sticky="we", pady=(4, 0))
            if aide:
                ttk.Label(corps, text=aide, font=("Segoe UI", 8), foreground="#6b7a70", wraplength=360).grid(
                    row=2 * i + 1, column=1, sticky="w")
        ligne = 2 * len(lignes)
        if not p.principal:
            self.vars["actif"] = tk.BooleanVar(value=p.actif)
            ttk.Checkbutton(corps, text=t("Actif (traité avec « tous les points de vente »)"),
                            variable=self.vars["actif"]).grid(row=ligne, column=1, sticky="w", pady=(8, 0))
        ttk.Label(corps, text=t("* champ obligatoire"), font=("Segoe UI", 8), foreground="#6b7a70").grid(
            row=ligne + 1, column=0, sticky="w", pady=(14, 0))
        boutons = ttk.Frame(corps)
        boutons.grid(row=ligne + 1, column=1, sticky="e", pady=(14, 0))
        Bouton(boutons, t("Enregistrer"), self.valider, petit=True).pack(side="left")
        Bouton(boutons, t("Annuler"), self.destroy, "secondaire", petit=True).pack(side="left", padx=(8, 0))
        self.grab_set()

    def manquants(self, v: dict) -> list[str]:
        """Champs obligatoires vides (le jeton seulement s'il n'est pas déjà dans le coffre-fort) ; identifiant
        marchand de 13 caractères."""
        manquants = [self.libelles[cle] for cle in self.libelles
                     if not str(v.get(cle, "")).strip() and (cle != "jeton" or not self.jeton_present)]
        marchand = str(v.get("marchand", "")).strip()
        if "marchand" in self.libelles and marchand and (len(marchand) != 13 or not marchand.isalnum()):
            manquants.append(t("Identifiant marchand (13 lettres ou chiffres)"))
        return manquants

    def valider(self) -> None:
        v = {cle: (var.get().strip() if isinstance(var.get(), str) else var.get()) for cle, var in self.vars.items()}
        if manquants := self.manquants(v):
            messagebox.showwarning(self.title(), t("Champs obligatoires à remplir :") + "\n\n• "
                                   + "\n• ".join(manquants), parent=self)
            return
        p = self.p
        p.nom, p.client_sage, p.depot_sage = v["nom"], v["client"], v["depot"] or DEPOT_DEFAUT
        if not p.principal:
            p.merchant_id, p.prefixe, p.actif = v["marchand"], v["prefixe"], bool(v["actif"])
        points = [x for x in self.carte.points() if x.code != p.code] + [p]
        points.sort(key=lambda x: (x.code != PRINCIPAL, int(x.code) if x.code.isdigit() else 999, x.code))
        if not self.carte._enregistrer(points):
            return
        if not p.principal and v.get("jeton"):
            coffre.ecrire(p.cle_jeton, v["jeton"])
            self.carte.remplir()
        self.destroy()


class ChoixPointVente(ttk.Frame):
    """Liste « Point de vente : » des pages de travail (Correspondance, Encaissements) : un seul à la fois,
    parmi ceux que le profil de la personne connectée peut voir (`points` : fonction -> liste de PointDeVente)."""

    def __init__(self, parent, points, au_changement=None):
        super().__init__(parent)
        self.points = points
        ttk.Label(self, text=t("Point de vente :")).pack(side="left")
        self.choix = tk.StringVar()
        self.liste = ttk.Combobox(self, textvariable=self.choix, state="readonly", width=26,
                                  postcommand=self._remplir)
        self.liste.pack(side="left", padx=(4, 0))
        self._remplir()
        if au_changement:
            self.liste.bind("<<ComboboxSelected>>", lambda _e: au_changement())

    def _remplir(self) -> None:
        libelles = [p.libelle for p in self.points()]
        self.liste.configure(values=libelles)
        if self.choix.get() not in libelles:
            self.choix.set(libelles[0] if libelles else "")

    @property
    def courant(self) -> PointDeVente | None:
        return next((p for p in self.points() if p.libelle == self.choix.get()), None)
