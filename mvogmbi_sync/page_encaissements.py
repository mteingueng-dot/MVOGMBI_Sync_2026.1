"""Page « Encaissements » : dépôts Clover, virements Interac et dépôts d'espèces à encaisser sur les factures de vente,
et leur état dans Sage."""

from __future__ import annotations

import threading
import tkinter as tk
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .design import CARTE, TEXTE_DOUX, Bouton, ChampDate, cadre_tableau, entete_page
from .encaissements import A_SAISIR, A_VENIR, A_VERIFIER, APPLIQUE, ECART, SANS_FACTURE
from .export_tableau import bouton_exporter, export_permis
from .langues import courante, jours_semaine, t

COULEURS = {APPLIQUE: "#e6f4ea", A_SAISIR: "#fff4d6", ECART: "#fde2e4", A_VERIFIER: "#fde2e4",
            SANS_FACTURE: None, A_VENIR: None}


def argent(montant: Decimal | None) -> str:
    if montant is None:
        return ""
    texte = f"{montant:,.2f}"
    return f"${texte}" if courante() == "en" else texte.replace(",", " ").replace(".", ",") + " $"


class PageEncaissements(ttk.Frame):
    def __init__(self, parent, racine: Path, titre: str, chemin_config: Path, points_vente=None):
        """`points_vente` : fonction -> points de vente visibles ; chacun a ses lots Clover et ses factures."""
        super().__init__(parent, padding=10)
        self.racine, self.titre, self.chemin_config = racine, titre, chemin_config
        self.depots = []
        self.choix_pdv = None

        entete_page(self, "💰", t("Encaissements des dépôts Clover"),
                    t("dépôts Clover, virements Interac et dépôts d'espèces appliqués sur les factures de vente")).pack(fill="x")
        barre = ttk.Frame(self)
        barre.pack(fill="x")
        hier = date.today() - timedelta(days=1)
        if points_vente is not None:
            from .page_points_vente import ChoixPointVente

            self.choix_pdv = ChoixPointVente(self, points_vente, self._changer_point_vente)
            self.choix_pdv.pack(anchor="w", pady=(0, 8), before=barre)
        ttk.Label(barre, text=t("Ventes du")).pack(side="left")
        self.debut = tk.StringVar(value=(hier - timedelta(days=30)).isoformat())
        ChampDate(barre, self.debut).pack(side="left", padx=4)
        ttk.Label(barre, text=t("au")).pack(side="left")
        self.fin = tk.StringVar(value=hier.isoformat())
        ChampDate(barre, self.fin).pack(side="left", padx=4)
        Bouton(barre, "⟳  " + t("Calculer les dépôts"), self.calculer).pack(side="left", padx=8)
        if export_permis():
            Bouton(barre, "📗  Excel", self.exporter, "secondaire").pack(side="right")
        Bouton(barre, "🏦  " + t("Encaisser dans Sage"), self.encaisser, "accent").pack(side="right", padx=8)
        self.resume = ttk.Label(self, text=t("Cliquez sur « Calculer les dépôts » : lots de cartes Clover et état dans Sage."),
                                foreground=TEXTE_DOUX, padding=(0, 8))
        self.resume.pack(fill="x")

        cadre = cadre_tableau(self)
        cadre.pack(fill="both", expand=True)
        colonnes = (("montant", t("Montant"), 120), ("du", t("Montant dû (Sage)"), 140), ("etat", t("État"), 230))
        self.tableau = ttk.Treeview(cadre, columns=[c[0] for c in colonnes], show="tree headings", height=12,
                                    selectmode="browse")
        self.tableau.heading("#0", text=t("Date du dépôt / facture"))
        self.tableau.column("#0", width=420)
        for cle, titre_col, largeur in colonnes:
            self.tableau.heading(cle, text=titre_col)
            self.tableau.column(cle, width=largeur, anchor="e" if cle != "etat" else "w")
        for etat, couleur in COULEURS.items():  # sans couleur : état terminé, texte grisé sur lignes rayées
            self.tableau.tag_configure(etat, **({"background": couleur} if couleur else {"foreground": TEXTE_DOUX}))
        self.tableau.tag_configure("depot", font=("Segoe UI Semibold", 10))
        defilement = ttk.Scrollbar(cadre, orient="vertical", command=self.tableau.yview)
        self.tableau.configure(yscrollcommand=defilement.set)
        defilement.pack(side="right", fill="y")  # avant le tableau : toujours visible, même s'il est large
        self.tableau.pack(side="left", fill="both", expand=True)
        self.tableau.bind("<<TreeviewSelect>>", lambda _e: self.afficher_saisie())
        bouton_exporter(barre, self.tableau, t("Encaissements")).pack(side="right")

        bas = tk.Frame(self, background=CARTE, highlightthickness=1, highlightbackground="#e2e8e4")
        bas.pack(fill="x", pady=(10, 0))
        entete = tk.Frame(bas, background=CARTE)
        entete.pack(fill="x", padx=14, pady=(10, 0))
        tk.Label(entete, text=t("Saisie dans Sage (Encaissements)"), font=("Segoe UI Semibold", 11),
                 background=CARTE).pack(side="left")
        Bouton(entete, "📋  " + t("Copier"), self.copier, "secondaire", fond=CARTE, petit=True).pack(side="right")
        self.saisie = tk.Text(bas, height=8, wrap="word", font=("Cascadia Mono", 9), relief="flat", background=CARTE,
                              borderwidth=0, padx=14, pady=8)
        self.saisie.pack(fill="x")
        self.saisie.insert("end", t("Sélectionnez un dépôt dans le tableau."))
        self.saisie.configure(state="disabled")

    # ---------------------------------------------------------------- calcul
    def _config(self) -> dict:
        import tomllib
        return tomllib.loads(self.chemin_config.read_text(encoding="utf-8")) if self.chemin_config.exists() else {}

    def compte_depot(self) -> str:
        return str(self._config().get("encaissements", {}).get("compte_depot", "1055"))

    def calculer(self) -> None:
        try:
            debut, fin = date.fromisoformat(self.debut.get().strip()), date.fromisoformat(self.fin.get().strip())
            assert debut <= fin
        except (ValueError, AssertionError):
            messagebox.showerror(self.titre, t("Vérifiez les dates (AAAA-MM-JJ)."))
            return
        self.resume.configure(text=t("Calcul en cours : lots de cartes Clover, relevés Desjardins, puis lecture de Sage…"))

        pdv = self.point_vente()
        if pdv is None:
            self.resume.configure(text="✘ " + t("Aucun point de vente actif n'est permis à votre profil."))
            return

        def travail():
            try:
                from .__main__ import charger_config, lire_sage
                from .api_clover import ClientClover
                from .encaissements import calculer, numero_compte_sage

                config = self._config()
                try:
                    client = ClientClover(charger_config(self.chemin_config, pdv))
                except SystemExit as exc:
                    raise RuntimeError(str(exc)) from None
                compte = numero_compte_sage(self.compte_depot())
                depots = lire_sage(config, lambda base: calculer(client, base, pdv.client_sage, compte, debut, fin,
                                                                 racine=self.racine if pdv.principal else None,
                                                                 prefixe=pdv.prefixe),
                                   config.get("sage_import", {}).get("fichier_entreprise"))
                self.after(0, lambda: self.afficher(depots))
            except Exception as exc:
                message = str(exc)
                self.after(0, lambda: self.resume.configure(text="✘ " + message))

        threading.Thread(target=travail, daemon=True).start()

    def afficher(self, depots) -> None:
        self.depots = depots
        self.tableau.delete(*self.tableau.get_children())
        jours = jours_semaine()
        for i, d in sorted(enumerate(depots), key=lambda x: (x[1].date, x[0]), reverse=True):  # plus récent en haut
            texte = f"{d.date.isoformat()} ({jours[d.date.weekday()]})" + (f"  •  {d.origine}" if d.origine else "")
            if d.remarque:
                texte += f"  —  {d.remarque}"
            parent = self.tableau.insert("", "end", iid=f"d{i}", text=texte,
                                         values=(argent(d.montant), "", t(d.etat)), tags=(d.etat, "depot"),
                                         open=d.etat != APPLIQUE)
            for j, l in enumerate(d.lignes):
                self.tableau.insert(parent, "end", iid=f"d{i}l{j}", text=f"   {l.facture}",
                                    values=(argent(l.montant), argent(l.montant_du), t(l.etat)), tags=(l.etat,))
        a_saisir = [d for d in depots if d.etat in (A_SAISIR, ECART, A_VERIFIER)]
        self.resume.configure(text=t("{n} dépôt(s), {total} au total — {a} à saisir dans Sage, {ok} déjà appliqué(s).",
                                     n=len(depots), total=argent(sum((d.montant for d in depots), Decimal(0))),
                                     a=len(a_saisir), ok=sum(1 for d in depots if d.etat == APPLIQUE)))
        if a_saisir:
            index = depots.index(a_saisir[0])
            self.tableau.selection_set(f"d{index}")
            self.tableau.see(f"d{index}")

    def encaisser(self) -> None:
        """Le robot saisit dans Sage chaque dépôt « À saisir » (Sage ouvert, fenêtre Encaissements affichée)."""
        a_saisir = [d for d in self.depots if d.etat == A_SAISIR]
        if not a_saisir:
            messagebox.showinfo(self.titre, t("Aucun dépôt « À saisir dans Sage » : calculez d'abord les dépôts."))
            return
        from .sage_bureau import sage_ouvert
        if sage_ouvert():
            messagebox.showwarning(self.titre, t("Fermez Sage : l'application l'ouvre elle-même pour encaisser "
                                                 "les dépôts."))
            return
        total = argent(sum((d.montant for d in a_saisir), Decimal(0)))
        if not messagebox.askyesno(self.titre, t("Encaisser {n} dépôt(s) ({total}) dans Sage ? L'application ouvre Sage "
                                                 "elle-même ; n'ouvrez pas Sage pendant ce temps.",
                                                 n=len(a_saisir), total=total)):
            return
        self.resume.configure(text=t("Saisie des encaissements dans Sage en cours…"))
        code = self.point_vente().code

        def travail():
            import json
            import tempfile

            from .__main__ import commande_moteur
            from .sage_bureau import executer_sur_bureau_cache

            try:
                with tempfile.TemporaryDirectory() as dossier:
                    fichier = Path(dossier) / "bilan.json"
                    executer_sur_bureau_cache(commande_moteur() + ["encaisser-bureau", "--resultat", str(fichier),
                                                                   "--point-de-vente", code], self.racine)
                    resultat = json.loads(fichier.read_text(encoding="utf-8")) if fichier.exists() else {}
                bilan = t("{ok} dépôt(s) encaissé(s) sur {n}.", ok=len(resultat.get("encaisses", [])), n=len(a_saisir))
                if resultat:
                    try:
                        from .courriel import envoyer_bilan_encaissements
                        envoyer_bilan_encaissements(self._config(), resultat)
                    except Exception as exc:  # le courriel ne doit pas masquer le résultat
                        resultat.setdefault("notes", []).append(f"Courriel non envoyé : {exc}")
                notes = resultat.get("encaisses", []) + resultat.get("a_verifier", []) + (
                    [resultat["erreur"]] if resultat.get("erreur") else []) + resultat.get("notes", [])
            except Exception as exc:
                bilan, notes = f"✘ {exc}", []
            message = bilan + ("\n\n" + "\n".join(notes) if notes else "")
            self.after(0, lambda: (messagebox.showinfo(self.titre, message), self.calculer()))

        threading.Thread(target=travail, daemon=True).start()

    def depot_choisi(self):
        choix = self.tableau.selection()
        if not choix:
            return None
        return self.depots[int(choix[0][1:].split("l")[0])]

    def point_vente(self):
        """Point de vente choisi (le n° 1 si la page n'a pas de choix)."""
        if self.choix_pdv is not None:
            return self.choix_pdv.courant
        from .points_vente import point_de_vente

        return point_de_vente(self._config())

    def _changer_point_vente(self) -> None:
        self.depots = []
        self.tableau.delete(*self.tableau.get_children())
        self.resume.configure(text=t("Cliquez sur « Calculer les dépôts » : lots de cartes Clover et état dans Sage."))

    def texte_saisie(self, d) -> str:
        pdv = self.point_vente()
        client = pdv.client_sage if pdv else "Vente Hebdomadaire"
        lignes = [t("Encaissements > Payé par : Comptant ; Reçu de : {client}", client=client),
                  t("Dépôt : {compte} (compte Desjardins)", compte=self.compte_depot()),
                  t("Date : {date}", date=d.date.isoformat()), "",
                  t("Montant reçu, facture par facture :")]
        for l in d.lignes:
            lignes.append(f"   {l.facture:<20} {argent(l.montant):>14}   ({t(l.etat)})")
        lignes += ["", t("Total du dépôt : {total}", total=argent(d.montant)),
                   t("Puis « Traiter ». L'état passera à « Appliqué » au prochain calcul.")]
        return "\n".join(lignes)

    def afficher_saisie(self) -> None:
        d = self.depot_choisi()
        if not d:
            return
        self.saisie.configure(state="normal")
        self.saisie.delete("1.0", "end")
        self.saisie.insert("end", self.texte_saisie(d))
        self.saisie.configure(state="disabled")

    def copier(self) -> None:
        d = self.depot_choisi()
        if d:
            self.clipboard_clear()
            self.clipboard_append(self.texte_saisie(d))

    def exporter(self) -> None:
        if not self.depots:
            messagebox.showinfo(self.titre, t("Calculez d'abord les dépôts."))
            return
        chemin = filedialog.asksaveasfilename(defaultextension=".xlsx", initialfile="encaissements.xlsx",
                                              filetypes=[("Excel", "*.xlsx")])
        if not chemin:
            return
        from .encaissements import ecrire_excel

        try:
            ecrire_excel(self.depots, Path(chemin), self.compte_depot())
        except PermissionError:
            messagebox.showerror(self.titre, t("Fichier ouvert dans Excel : fermez-le puis recommencez."))
            return
        import os
        os.startfile(chemin)
