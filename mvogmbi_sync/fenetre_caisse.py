"""Fenêtre « Comptabilité > Contrôle de la caisse » (demande du propriétaire du 2026-10-29) : comptage du soir par
coupures, écarts par jour, espèces à déposer contre dépôts au guichet. Calculs dans caisse.py ; Clover lu dans un fil
(jours terminés pris dans le cache des statistiques)."""

from __future__ import annotations

import threading
import tkinter as tk
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from tkinter import messagebox, ttk

from . import caisse as ca
from .design import FenetreOutil, CARTE, ROUGE, TEXTE_DOUX, VERT_FONCE, Bouton, ChampDate, Rangee
from .export_tableau import bouton_exporter
from .langues import t

ONGLETS = ["Comptage du soir", "Écarts par jour", "Dépôts d'espèces"]


def _argent(v) -> str:
    return f"{Decimal(v):,.2f} $".replace(",", " ").replace(".", ",")


def _config(racine: Path) -> dict:
    import tomllib

    chemin = Path(racine) / "config.toml"
    return tomllib.loads(chemin.read_text(encoding="utf-8")) if chemin.exists() else {}


def lire_clover(racine: Path, debut: date, fin: date, pv=None):
    from .points_vente import cache_clover, client
    from .statistiques_clover import lire

    return ca.attendus(lire(client(racine, pv), debut, fin, cache_clover(racine, pv)))


class FenetreCaisse(FenetreOutil):
    def __init__(self, parent, racine: Path, auteur: str = ""):
        super().__init__(parent)
        self.racine, self.auteur = Path(racine), auteur
        self.config_toml = _config(racine)
        self.title(t("Contrôle de la caisse"))
        self.configure(background=CARTE, padx=14, pady=10)
        self.geometry("1100x660")
        from .page_points_vente import ChoixPointVente
        from .points_vente import visibles

        self.choix_pv = ChoixPointVente(self, lambda: visibles(self, self.config_toml), self.charger_jour)
        self.choix_pv.pack(anchor="w", pady=(0, 6))
        self.onglets = ttk.Notebook(self)
        self.onglets.pack(fill="both", expand=True)
        self.cadres = {}
        for nom, construire in zip(ONGLETS, (self._comptage, self._ecarts, self._depots)):
            cadre = ttk.Frame(self.onglets, padding=(0, 8, 0, 0))
            self.onglets.add(cadre, text="  " + t(nom) + "  ")
            self.cadres[nom] = cadre
            construire(cadre)
        self.charger_jour()

    def _lire(self, travail, fin, etat: tk.Label) -> None:
        etat.configure(text=t("Lecture des ventes dans Clover…"), foreground=TEXTE_DOUX)

        def executer():
            try:
                resultat = travail()
                self.after(0, lambda: fin(resultat))
            except BaseException as exc:  # SystemExit compris (jeton absent)
                texte = str(exc) or type(exc).__name__
                self.after(0, lambda: etat.configure(text="✘ " + texte, foreground=ROUGE))

        threading.Thread(target=executer, daemon=True).start()

    # ------------------------------------------------------------------ comptage du soir
    def _comptage(self, cadre) -> None:
        haut = Rangee(cadre)
        haut.pack(fill="x")
        groupe = haut.ajouter(haut.groupe(), 10)
        tk.Label(groupe, text=t("Journée"), background=CARTE).pack(side="left", padx=(0, 4))
        self.jour = tk.StringVar(value=date.today().isoformat())
        ChampDate(groupe, self.jour, fond=CARTE).pack(side="left")
        haut.ajouter(Bouton(haut, "🔄  " + t("Actualiser"), self.charger_jour, fond=CARTE, petit=True))
        corps = tk.Frame(cadre, background=CARTE)
        corps.pack(fill="both", expand=True, pady=(10, 0))
        gauche = ttk.LabelFrame(corps, text=" " + t("Espèces attendues (Clover)") + " ", padding=10)
        gauche.pack(side="left", fill="both", expand=True, padx=(0, 10))
        self.attendu_texte = tk.Label(gauche, text="", justify="left", anchor="nw", font=("Segoe UI", 10))
        self.attendu_texte.pack(fill="both", expand=True)
        droite = ttk.LabelFrame(corps, text=" " + t("Comptage du tiroir") + " ", padding=10)
        droite.pack(side="left", fill="both")
        self.coupures = {}
        for rang, valeur in enumerate(ca.COUPURES):
            libelle = f"{Decimal(valeur):.2f} $".replace(".", ",") if Decimal(valeur) < 1 else f"{valeur} $"
            tk.Label(droite, text=libelle, anchor="e", width=8).grid(row=rang % 5, column=(rang // 5) * 2, sticky="e",
                                                                     pady=2)
            v = tk.StringVar()
            v.trace_add("write", lambda *_: self.calculer())
            ttk.Entry(droite, textvariable=v, width=6, justify="right").grid(row=rang % 5, column=(rang // 5) * 2 + 1,
                                                                             padx=(4, 16), pady=2)
            self.coupures[valeur] = v
        tk.Label(droite, text=t("Fond laissé pour demain"), anchor="w").grid(row=5, column=0, columnspan=2, sticky="w",
                                                                             pady=(10, 2))
        self.fond = tk.StringVar(value=str(ca.fond_de_caisse(self.config_toml)).replace(".", ","))
        self.fond.trace_add("write", lambda *_: self.calculer())
        ttk.Entry(droite, textvariable=self.fond, width=10, justify="right").grid(row=5, column=2, columnspan=2,
                                                                                  sticky="w", pady=(10, 2))
        tk.Label(droite, text=t("Remarque"), anchor="w").grid(row=6, column=0, columnspan=2, sticky="w")
        self.remarque = tk.StringVar()
        ttk.Entry(droite, textvariable=self.remarque, width=30).grid(row=6, column=2, columnspan=2, sticky="w")
        self.resultat = tk.Label(droite, text="", justify="left", anchor="w", font=("Segoe UI Semibold", 11))
        self.resultat.grid(row=7, column=0, columnspan=4, sticky="w", pady=(10, 4))
        Bouton(droite, "✔  " + t("Enregistrer le comptage"), self.enregistrer, fond=CARTE).grid(
            row=8, column=0, columnspan=4, sticky="w", pady=(6, 0))
        self.etat_jour = tk.Label(cadre, text="", background=CARTE, foreground=TEXTE_DOUX, anchor="w")
        self.etat_jour.pack(fill="x", pady=(6, 0))
        self.attendu_jour: ca.Attendu | None = None

    def _jour(self) -> date | None:
        try:
            return date.fromisoformat(self.jour.get().strip())
        except ValueError:
            self.etat_jour.configure(text="✘ " + t("Date au format AAAA-MM-JJ."), foreground=ROUGE)
            return None

    def charger_jour(self) -> None:
        jour = self._jour()
        if not jour:
            return
        registre = ca.Registre(self.racine, self.choix_pv.courant)
        c = registre.comptage(jour)
        for valeur, v in self.coupures.items():
            v.set(str((c.coupures if c else {}).get(valeur, "")))
        if c:
            self.fond.set(str(c.fond).replace(".", ","))
            self.remarque.set(c.remarque)

        def fin(attendu):
            if self.jour.get().strip() != jour.isoformat():
                return  # lecture d'une autre journée, finie après le changement de date : ignorée
            self.attendu_jour = attendu.get(jour) or ca.Attendu(jour)
            self.etat_jour.configure(text=(t("Comptage déjà enregistré par {p} le {l}.", p=c.par, l=c.le[:16].replace(
                "T", " ")) if c else t("Comptez le tiroir à la fermeture, puis « Enregistrer le comptage ».")),
                foreground=TEXTE_DOUX)
            self.calculer()

        self._lire(lambda: lire_clover(self.racine, jour, jour, self.choix_pv.courant), fin, self.etat_jour)

    def calculer(self) -> None:
        a = self.attendu_jour
        if a is None:
            return
        registre = ca.Registre(self.racine, self.choix_pv.courant)
        fond_matin = ca.fond_du_matin(registre, a.jour, self.config_toml)
        prevu = fond_matin + a.net
        lignes = [t("Fond du matin : {m}", m=_argent(fond_matin)),
                  t("Ventes en espèces : {m} ({n} paiements)", m=_argent(a.ventes), n=a.paiements),
                  t("Remboursements en espèces : −{m}", m=_argent(a.remboursements)),
                  t("Argent remis sur carte : −{m}", m=_argent(a.remis)),
                  "", t("Attendu dans le tiroir : {m}", m=_argent(prevu)), ""]
        if a.par_employe:
            lignes.append(t("Espèces encaissées par employé :"))
            lignes += [f"   • {e} : {_argent(m)}" for e, m in sorted(a.par_employe.items(), key=lambda x: -x[1])]
        self.attendu_texte.configure(text="\n".join(lignes))
        try:
            compte = ca.total_coupures({k: v.get().strip() for k, v in self.coupures.items()})
            fond = Decimal(self.fond.get().replace(",", ".").strip() or 0)
        except Exception as exc:
            self.resultat.configure(text="✘ " + str(exc), foreground=ROUGE)
            return
        ecart = compte - prevu
        couleur = VERT_FONCE if abs(ecart) < Decimal("0.01") else (ROUGE if abs(ecart) > ca.SEUIL_ECART else "#b07d00")
        self.resultat.configure(text=t("Compté : {c}   Écart : {e}\nÀ déposer : {d}", c=_argent(compte),
                                       e=("+" if ecart > 0 else "") + _argent(ecart), d=_argent(compte - fond)),
                                foreground=couleur)

    def enregistrer(self) -> None:
        from .design import action_permise

        if not action_permise(self, "Enregistrer un comptage de caisse"):
            return
        jour = self._jour()
        if not jour or self.attendu_jour is None:
            return
        try:
            coupures = {k: int(v.get().strip()) for k, v in self.coupures.items() if v.get().strip()}
            compte = ca.total_coupures(coupures)
            fond = Decimal(self.fond.get().replace(",", ".").strip() or 0).quantize(ca.CENT)
        except Exception:
            messagebox.showerror(self.title(), t("Nombres entiers seulement pour les coupures."), parent=self)
            return
        if fond > compte:
            messagebox.showerror(self.title(), t("Le fond laissé dépasse le montant compté."), parent=self)
            return
        registre = ca.Registre(self.racine, self.choix_pv.courant)
        if registre.comptage(jour) and not messagebox.askyesno(
                self.title(), t("Un comptage existe déjà pour le {j}. Le remplacer ?", j=jour.isoformat()), parent=self):
            return
        registre.noter(ca.Comptage(jour.isoformat(), str(compte), str(fond), coupures, self.auteur,
                                   remarque=self.remarque.get().strip()))
        self.etat_jour.configure(text=t("✔ Comptage du {j} enregistré.", j=jour.isoformat()), foreground=VERT_FONCE)

    # ------------------------------------------------------------------ écarts par jour
    def _periode(self, barre, action) -> tuple[tk.StringVar, tk.StringVar]:
        groupe = barre.ajouter(barre.groupe(), 10)
        tk.Label(groupe, text=t("Du"), background=CARTE).pack(side="left")
        du = tk.StringVar(value=(date.today() - timedelta(days=30)).isoformat())
        ChampDate(groupe, du, fond=CARTE).pack(side="left", padx=4)
        tk.Label(groupe, text=t("au"), background=CARTE).pack(side="left")
        au = tk.StringVar(value=date.today().isoformat())
        ChampDate(groupe, au, fond=CARTE).pack(side="left", padx=4)
        barre.ajouter(Bouton(barre, "🔍  " + t("Afficher"), action, fond=CARTE, petit=True), 10)
        return du, au

    def _ecarts(self, cadre) -> None:
        from .page_rapports import tableau_simple

        barre = Rangee(cadre)
        barre.pack(fill="x")
        self.du_e, self.au_e = self._periode(barre, self.afficher_ecarts)
        self.etat_e = tk.Label(cadre, text=t("Choisissez la période puis « Afficher »."), background=CARTE,
                               foreground=TEXTE_DOUX, anchor="w")
        self.etat_e.pack(fill="x", pady=(6, 0))
        self.tableau_e = tableau_simple(cadre, hauteur=16)
        barre.ajouter(bouton_exporter(barre, self.tableau_e, lambda: t("Écarts de caisse")))

    def _bornes(self, du: tk.StringVar, au: tk.StringVar, etat: tk.Label):
        try:
            return date.fromisoformat(du.get().strip()), min(date.fromisoformat(au.get().strip()), date.today())
        except ValueError:
            etat.configure(text="✘ " + t("Date au format AAAA-MM-JJ."), foreground=ROUGE)
            return None

    def afficher_ecarts(self) -> None:
        from .page_rapports import remplir

        bornes = self._bornes(self.du_e, self.au_e, self.etat_e)
        if not bornes:
            return
        debut, fin = bornes

        def termine(attendu):
            lignes = ca.lignes_jours(attendu, ca.Registre(self.racine, self.choix_pv.courant), debut, fin, self.config_toml)
            remplir(self.tableau_e, ca.ENTETES_JOURS, lignes, {"Compté par": 160},
                    lambda i: ("manque",) if isinstance(lignes[i][7], Decimal) and lignes[i][7] < -ca.SEUIL_ECART
                    else (("non",) if lignes[i][9] == "Non compté" else ()))
            self.tableau_e.tag_configure("manque", foreground=ROUGE)
            self.tableau_e.tag_configure("non", foreground="#7d8b81")
            ecarts = [l[7] for l in lignes if isinstance(l[7], Decimal)]
            self.etat_e.configure(text=t("{c} jour(s) comptés sur {n} ; écart total {e} ; {g} écart(s) de plus de {s}.",
                                         c=len(ecarts), n=len(lignes), e=_argent(sum(ecarts, ca.ZERO)),
                                         g=sum(1 for x in ecarts if abs(x) > ca.SEUIL_ECART),
                                         s=_argent(ca.SEUIL_ECART)),
                                  foreground=ROUGE if any(abs(x) > ca.SEUIL_ECART for x in ecarts) else VERT_FONCE)

        self._lire(lambda: lire_clover(self.racine, debut, fin, self.choix_pv.courant), termine, self.etat_e)

    # ------------------------------------------------------------------ dépôts
    def _depots(self, cadre) -> None:
        from .page_rapports import tableau_simple

        barre = Rangee(cadre)
        barre.pack(fill="x")
        self.du_d, self.au_d = self._periode(barre, self.afficher_depots)
        self.etat_d = tk.Label(cadre, text=t("Espèces à déposer (comptages) et dépôts au guichet des relevés Desjardins "
                                             "chargés (Comptabilité > Rapprochement)."), background=CARTE,
                               foreground=TEXTE_DOUX, anchor="w", justify="left", wraplength=1050)
        self.etat_d.pack(fill="x", pady=(6, 0))
        self.tableau_d = tableau_simple(cadre, hauteur=16)
        barre.ajouter(bouton_exporter(barre, self.tableau_d, lambda: t("Dépôts d'espèces")))

    def afficher_depots(self) -> None:
        from .page_rapports import remplir

        bornes = self._bornes(self.du_d, self.au_d, self.etat_d)
        if not bornes:
            return
        debut, fin = bornes

        def termine(resultat):
            attendu, depots = resultat
            lignes = ca.lignes_jours(attendu, ca.Registre(self.racine, self.choix_pv.courant), debut, fin, self.config_toml)
            b = ca.bilan_depots(lignes, depots)
            par_jour = {}
            for jour, montant, _r in depots:
                par_jour[jour] = par_jour.get(jour, ca.ZERO) + montant
            jours = sorted({l[0] for l in lignes} | set(par_jour))
            a_deposer = {l[0]: l[8] for l in lignes}
            cumul, tableau = ca.ZERO, []
            for j in jours:
                ad = a_deposer.get(j, "")
                dep = par_jour.get(j, ca.ZERO)
                cumul += dep - (ad if isinstance(ad, Decimal) else ca.ZERO)
                tableau.append([j, ad, dep or "", cumul])
            remplir(self.tableau_d, ["Date", "À déposer", "Déposé au guichet", "Écart cumulé"], tableau)
            self.etat_d.configure(text=t("À déposer : {a} ; déposé : {d} ; écart : {e}{n}", a=_argent(b["a_deposer"]),
                                         d=_argent(b["depose"]), e=_argent(b["ecart"]),
                                         n=t(" ; {n} jour(s) non comptés", n=b["non_comptes"]) if b["non_comptes"]
                                         else ""),
                                  foreground=ROUGE if abs(b["ecart"]) > ca.SEUIL_ECART else VERT_FONCE)

        self._lire(lambda: (lire_clover(self.racine, debut, fin, self.choix_pv.courant), (ca.depots_especes(self.racine, debut, fin) if (self.choix_pv.courant is None or self.choix_pv.courant.principal) else [])),
                   termine, self.etat_d)
