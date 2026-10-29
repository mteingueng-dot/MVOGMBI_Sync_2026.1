"""Poste de pointage du magasin (demande du propriétaire du 2026-10-29) : l'employé touche son nom, tape son NIP,
puis Arrivée / Début de pause / Fin de pause / Départ. Ouvert depuis le menu Paie, ou seul sur le poste du magasin
par le raccourci « Pointage MVOGMBI » (commande `pointage`, sans connexion à l'application : le NIP suffit)."""

from __future__ import annotations

import tkinter as tk
from datetime import date, datetime, timedelta
from pathlib import Path

from . import paie_temps as pt
from .design import CARTE, FOND, ROUGE, TEXTE, TEXTE_DOUX, VERT_FONCE, Bouton
from .langues import t

RETOUR_ACCUEIL_MS = 12000  # après un pointage ou sans action : retour à la liste des noms
JOURS_FR = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]


class PostePointage(tk.Frame):
    def __init__(self, parent, racine: Path):
        super().__init__(parent, background=FOND)
        self.racine = Path(racine)
        self.registre = pt.Registre(racine)
        self.choisi: pt.Employe | None = None
        self.nip = ""
        self._retour = None
        haut = tk.Frame(self, background=FOND)
        haut.pack(fill="x", padx=24, pady=(18, 6))
        self.horloge = tk.Label(haut, font=("Segoe UI Semibold", 22), background=FOND, foreground=TEXTE)
        self.horloge.pack(side="left")
        tk.Label(haut, text=t("Pointage des employés"), font=("Segoe UI", 12), background=FOND,
                 foreground=TEXTE_DOUX).pack(side="right")
        self.message = tk.Label(self, text="", font=("Segoe UI Semibold", 13), background=FOND, foreground=VERT_FONCE)
        self.message.pack(fill="x", padx=24)
        self.zone = tk.Frame(self, background=FOND)
        self.zone.pack(fill="both", expand=True, padx=24, pady=12)
        self._tic()
        self.accueil()

    def _tic(self) -> None:
        maintenant = datetime.now()
        self.horloge.configure(text=f"{t(JOURS_FR[maintenant.weekday()]).capitalize()} {maintenant:%d/%m/%Y  %H:%M:%S}")
        self.after(1000, self._tic)

    def _vider(self) -> None:
        if self._retour:
            self.after_cancel(self._retour)
        self._retour = None
        for w in self.zone.winfo_children():
            w.destroy()

    def _plus_tard_accueil(self) -> None:
        self._retour = self.after(RETOUR_ACCUEIL_MS, self.accueil)

    # ------------------------------------------------------------------ étape 1 : nom
    def accueil(self) -> None:
        self._vider()
        self.choisi, self.nip = None, ""
        self.registre.recharger_employes()
        self.registre.recharger()
        employes = [e for e in self.registre.actifs() if e.nip]
        tk.Label(self.zone, text=t("Touchez votre nom"), font=("Segoe UI Semibold", 14), background=FOND,
                 foreground=TEXTE).pack(anchor="w", pady=(0, 10))
        grille = tk.Frame(self.zone, background=FOND)
        grille.pack(fill="both", expand=True)
        if not employes:
            tk.Label(grille, text=t("Aucun employé n'a de NIP : le gérant les crée dans « Paie > Employés et NIP »."),
                     background=FOND, foreground=TEXTE_DOUX, font=("Segoe UI", 11)).pack(anchor="w")
        colonnes = 4
        for i, e in enumerate(employes):
            present = self.registre.etat_actuel(e.id)
            texte = e.nom + ("\n● " + t("présent") if present in (pt.ARRIVEE, pt.FIN_PAUSE) else
                             "\n● " + t("en pause") if present == pt.PAUSE else "")
            b = tk.Button(grille, text=texte, font=("Segoe UI Semibold", 12), relief="flat", background=CARTE,
                          foreground=TEXTE, activebackground="#e3f1e7", height=3, cursor="hand2",
                          command=lambda x=e: self.demander_nip(x))
            b.grid(row=i // colonnes, column=i % colonnes, sticky="nsew", padx=6, pady=6)
        for c in range(colonnes):
            grille.columnconfigure(c, weight=1)

    # ------------------------------------------------------------------ étape 2 : NIP
    def demander_nip(self, employe: pt.Employe) -> None:
        self._vider()
        self.choisi, self.nip = employe, ""
        self.message.configure(text="")
        tk.Label(self.zone, text=employe.nom, font=("Segoe UI Semibold", 16), background=FOND,
                 foreground=TEXTE).pack(pady=(0, 6))
        tk.Label(self.zone, text=t("Tapez votre NIP"), font=("Segoe UI", 12), background=FOND,
                 foreground=TEXTE_DOUX).pack()
        self.affichage = tk.Label(self.zone, text="", font=("Segoe UI Semibold", 26), background=FOND,
                                  foreground=TEXTE, width=8)
        self.affichage.pack(pady=8)
        pave = tk.Frame(self.zone, background=FOND)
        pave.pack()
        touches = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "✖", "0", "✔"]
        for i, touche in enumerate(touches):
            tk.Button(pave, text=touche, font=("Segoe UI Semibold", 18), width=4, height=1, relief="flat",
                      background=CARTE, activebackground="#e3f1e7", cursor="hand2",
                      command=lambda x=touche: self._touche(x)).grid(row=i // 3, column=i % 3, padx=5, pady=5)
        Bouton(self.zone, "◀  " + t("Retour"), self.accueil, "secondaire").pack(pady=10)
        self.winfo_toplevel().bind("<Key>", self._clavier)
        self._plus_tard_accueil()

    def _clavier(self, evenement) -> None:
        if self.choisi is None:
            return
        if evenement.char.isdigit():
            self._touche(evenement.char)
        elif evenement.keysym in ("Return", "KP_Enter"):
            self._touche("✔")
        elif evenement.keysym in ("BackSpace", "Escape"):
            self._touche("✖")

    def _touche(self, touche: str) -> None:
        if not hasattr(self, "affichage") or not self.affichage.winfo_exists():
            return
        if touche == "✖":
            self.nip = ""
        elif touche == "✔":
            self._valider()
            return
        elif len(self.nip) < 6:
            self.nip += touche
        self.affichage.configure(text="●" * len(self.nip))

    def _valider(self) -> None:
        try:
            bon = self.registre.verifier_nip(self.choisi.id, self.nip)
        except pt.ErreurPointage as exc:
            self.message.configure(text=t(str(exc)), foreground=ROUGE)
            self.nip = ""
            self.affichage.configure(text="")
            return
        if not bon:
            self.message.configure(text=t("NIP incorrect."), foreground=ROUGE)
            self.nip = ""
            self.affichage.configure(text="")
            return
        self.message.configure(text="")
        self.actions()

    # ------------------------------------------------------------------ étape 3 : action
    def actions(self) -> None:
        employe = self.choisi
        self._vider()
        self.registre.recharger()
        tk.Label(self.zone, text=employe.nom, font=("Segoe UI Semibold", 16), background=FOND,
                 foreground=TEXTE).pack(pady=(0, 10))
        rangee = tk.Frame(self.zone, background=FOND)
        rangee.pack(pady=6)
        for action in self.registre.actions_permises(employe.id):
            Bouton(rangee, t(action), lambda a=action: self._pointer(a),
                   "danger" if action == pt.DEPART else "principal").pack(side="left", padx=8)
        tk.Label(self.zone, text=self._resume(employe), font=("Segoe UI", 11), background=FOND,
                 foreground=TEXTE_DOUX, justify="center").pack(pady=12)
        bas = tk.Frame(self.zone, background=FOND)
        bas.pack()
        Bouton(bas, "📅  " + t("Mon horaire"), lambda: self.horaire(employe), "secondaire").pack(side="left", padx=6)
        Bouton(bas, "◀  " + t("Retour"), self.accueil, "secondaire").pack(side="left", padx=6)
        self._plus_tard_accueil()

    def horaire(self, employe: pt.Employe) -> None:
        """Horaire publié de l'employé (5 semaines), après son NIP."""
        from . import planning as pl
        from .fenetre_planning import lignes_horaire

        self._vider()
        tk.Label(self.zone, text=t("Horaire de {n}", n=employe.nom), font=("Segoe UI Semibold", 15), background=FOND,
                 foreground=TEXTE).pack(pady=(0, 8))
        lignes = lignes_horaire(pl.Planning(self.racine), employe.id, date.today())
        texte = "\n".join(f"{l[1]} {l[0][8:]}/{l[0][5:7]}   " + (f"{l[2]} – {l[3]}" if l[3] else l[2])
                          for l in lignes) or t("Aucun horaire publié.")
        tk.Label(self.zone, text=texte, font=("Consolas", 11), background=FOND, foreground=TEXTE,
                 justify="left").pack()
        Bouton(self.zone, "◀  " + t("Retour"), self.accueil, "secondaire").pack(pady=10)
        self._plus_tard_accueil()

    def _resume(self, employe: pt.Employe) -> str:
        aujourdhui = date.today()
        pointages = [p for p in self.registre.valides(employe.id) if p.moment[:10] == aujourdhui.isoformat()]
        lignes = [t("Aujourd'hui : {l}", l=", ".join(f"{t(p.type)} {p.quand:%H:%M}" for p in pointages) or "—")]
        semaine = pt.feuille(self.registre, employe, pt.debut_periode(aujourdhui, self._reference()))
        heures = semaine.semaines[0 if aujourdhui < semaine.debut + timedelta(days=7) else 1]
        lignes.append(t("Cette semaine : {h} h", h=str(heures).replace(".", ",")))
        return "\n".join(lignes)

    def _reference(self) -> date:
        return reference(self.racine)

    def _pointer(self, action: str) -> None:
        try:
            p = self.registre.pointer(self.choisi.id, action)
        except pt.ErreurPointage as exc:
            self.message.configure(text=t(str(exc)), foreground=ROUGE)
            self.accueil()
            return
        self.message.configure(text=t("{n} : {a} à {h} — merci !", n=self.choisi.nom, a=t(action),
                                      h=f"{p.quand:%H:%M}"), foreground=VERT_FONCE)
        self.after(5000, lambda: self.message.configure(text=""))
        self.accueil()


def reference(racine: Path) -> date:
    """Premier jour d'une période de paie ([paie] debut_reference de config.toml, sinon DEBUT_REFERENCE)."""
    import tomllib

    try:
        chemin = Path(racine) / "config.toml"
        texte = tomllib.loads(chemin.read_text(encoding="utf-8")).get("paie", {}).get("debut_reference", "")
        return date.fromisoformat(str(texte)) if texte else pt.DEBUT_REFERENCE
    except (OSError, ValueError):
        return pt.DEBUT_REFERENCE


def ouvrir(parent, racine: Path) -> tk.Toplevel:
    fenetre = tk.Toplevel(parent)
    fenetre.title(t("Pointage des employés"))
    fenetre.geometry("980x680")
    fenetre.configure(background=FOND)
    PostePointage(fenetre, racine).pack(fill="both", expand=True)
    return fenetre


def poste_seul(racine: Path) -> None:
    """Poste du magasin : fenêtre de pointage seule, plein écran, sans connexion à l'application."""
    from .design import ICONE

    racine_tk = tk.Tk()
    racine_tk.title(t("Pointage des employés") + " — MVOGMBI_Sync")
    racine_tk.configure(background=FOND)
    racine_tk.state("zoomed")
    try:
        racine_tk.iconbitmap(default=str(ICONE))
    except Exception:
        pass
    PostePointage(racine_tk, racine).pack(fill="both", expand=True)
    racine_tk.mainloop()
