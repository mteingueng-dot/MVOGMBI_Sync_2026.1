"""Page « Utilisateurs » (administrateurs seulement) : comptes, profils et pages visibles de chaque profil."""

from __future__ import annotations

import re
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk

from .design import CARTE, TEXTE, TEXTE_DOUX, VERT_FONCE, Bouton, cadre_tableau, defilement, entete_page, rayer
from .export_tableau import bouton_exporter, placer_a_droite
from .langues import t
from .utilisateurs import ADMIN, LONGUEUR_MIN, PAGES, ErreurUtilisateur, Registre


class PageUtilisateurs(ttk.Frame):
    def __init__(self, parent, racine: Path, titre: str, libelles: dict[str, str], moi: str):
        """`libelles` : clé de page -> titre du menu ; `moi` : nom de l'utilisateur connecté."""
        super().__init__(parent, padding=10)
        self.racine, self.titre, self.libelles, self.moi = Path(racine), titre, libelles, moi
        self.registre = Registre(self.racine)

        entete_page(self, "👥", t("Utilisateurs et accès"),
                    t("comptes, profils et fonctions permises à chaque profil")).pack(fill="x")
        corps = ttk.Frame(self)
        corps.pack(fill="both", expand=True)
        corps.columnconfigure(0, weight=3)
        corps.columnconfigure(1, weight=2)
        corps.rowconfigure(0, weight=1)

        # ------------------------------------------------------------------ comptes
        gauche = ttk.Frame(corps)
        gauche.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        barre = ttk.Frame(gauche)
        barre.pack(fill="x", pady=(0, 6))
        ttk.Label(barre, text=t("Comptes"), font=("Segoe UI Semibold", 12), foreground=TEXTE).pack(side="left")
        cadre = cadre_tableau(gauche)
        cadre.pack(fill="both", expand=True)
        colonnes = (("nom", t("Nom"), 170), ("profil", t("Profil"), 130), ("etat", t("État"), 90),
                    ("derniere", t("Dernière connexion"), 150))
        self.tableau = ttk.Treeview(cadre, columns=[c[0] for c in colonnes], show="headings", height=10,
                                    selectmode="browse")
        for cle, texte, largeur in colonnes:
            self.tableau.heading(cle, text=texte)
            self.tableau.column(cle, width=largeur, stretch=cle == "nom")
        self.tableau.tag_configure("inactif", foreground=TEXTE_DOUX)
        self.tableau.pack(side="left", fill="both", expand=True)
        defilement(self.tableau)
        self.tableau.bind("<<TreeviewSelect>>", lambda _e: self.choisir())
        placer_a_droite(bouton_exporter(barre, self.tableau, t("Utilisateurs")))

        fiche = tk.Frame(gauche, background=CARTE, highlightthickness=1, highlightbackground="#e2e8e4", padx=14,
                         pady=10)
        fiche.pack(fill="x", pady=(10, 0))
        self.nom, self.profil, self.mdp = tk.StringVar(), tk.StringVar(), tk.StringVar()
        for col, (libelle, widget) in enumerate((
                (t("Nom"), ttk.Entry(fiche, textvariable=self.nom, width=22)),
                (t("Profil"), ttk.Combobox(fiche, textvariable=self.profil, state="readonly", width=18)),
                (t("Mot de passe ({n} caractères min.)", n=LONGUEUR_MIN),
                 ttk.Entry(fiche, textvariable=self.mdp, show="•", width=20)))):
            tk.Label(fiche, text=libelle, font=("Segoe UI", 9), foreground=TEXTE_DOUX, background=CARTE).grid(
                row=0, column=col, sticky="w", padx=(0, 10))
            widget.grid(row=1, column=col, sticky="we", padx=(0, 10))
        self.liste_profils_compte = fiche.grid_slaves(row=1, column=1)[0]
        boutons = tk.Frame(fiche, background=CARTE)
        boutons.grid(row=2, column=0, columnspan=3, sticky="w", pady=(10, 0))
        for texte, commande, genre in (("➕  " + t("Ajouter"), self.ajouter, "principal"),
                                       (t("Changer le profil"), self.changer_profil, "secondaire"),
                                       (t("Nouveau mot de passe"), self.nouveau_mot_de_passe, "secondaire"),
                                       (t("Activer / désactiver"), self.basculer, "secondaire"),
                                       ("🗑  " + t("Supprimer"), self.supprimer, "danger")):
            Bouton(boutons, texte, commande, genre, fond=CARTE, petit=True).pack(side="left", padx=(0, 6))

        # ------------------------------------------------------------------ profils
        droite = tk.Frame(corps, background=CARTE, highlightthickness=1, highlightbackground="#e2e8e4", padx=16,
                          pady=12)
        droite.grid(row=0, column=1, sticky="nsew")
        tk.Label(droite, text=t("Profils et fonctions permises"), font=("Segoe UI Semibold", 12), foreground=TEXTE,
                 background=CARTE).pack(anchor="w")
        ligne = tk.Frame(droite, background=CARTE)
        ligne.pack(fill="x", pady=(8, 6))
        self.profil_choisi = tk.StringVar()
        self.liste_profils = ttk.Combobox(ligne, textvariable=self.profil_choisi, state="readonly", width=22)
        self.liste_profils.pack(side="left")
        self.liste_profils.bind("<<ComboboxSelected>>", lambda _e: self.afficher_acces())
        Bouton(ligne, "➕", self.nouveau_profil, "secondaire", fond=CARTE, petit=True, largeur=34).pack(
            side="left", padx=6)
        Bouton(ligne, "🗑", self.supprimer_profil, "danger", fond=CARTE, petit=True, largeur=34).pack(side="left")
        # arbre du menu (demande du propriétaire du 2026-10-30) : rubriques -> fonctions, cochées une à une ; une
        # fonction cochée seule (ex. « Liste des articles ») ne donne pas le reste de sa rubrique
        tk.Label(droite, text=t("Cliquez pour cocher ou décocher ; une rubrique coche toutes ses fonctions."),
                 font=("Segoe UI", 9), foreground=TEXTE_DOUX, background=CARTE, wraplength=330,
                 justify="left").pack(anchor="w")
        cadre_arbre = cadre_tableau(droite)
        cadre_arbre.pack(fill="both", expand=True, pady=(4, 0))
        # hauteur demandée basse : l'arbre s'agrandit avec la place, sans pousser hors de la carte les droits et
        # « Enregistrer les accès » (capture du 2026-10-30)
        self.arbre = ttk.Treeview(cadre_arbre, show="tree", height=6, selectmode="none")
        self.arbre.column("#0", width=320)
        self.arbre.tag_configure("rubrique", font=("Segoe UI Semibold", 10))
        self.arbre.tag_configure("fixe", foreground=TEXTE_DOUX)
        self.arbre.pack(side="left", fill="both", expand=True)
        defilement(self.arbre)
        self.arbre.bind("<Button-1>", self._clic_arbre)
        self.coches: dict[str, bool] = {}       # id du nœud -> coché
        self.libelle_noeud: dict[str, str] = {}
        self.pages_noeud: dict[str, str] = {}   # fonction -> clé de la page qu'elle doit pouvoir afficher
        self.actions_fenetres: set[str] = set()
        self._remplir_arbre()
        from .interface import lire_config
        from .points_vente import points_de_vente

        tk.Label(droite, text=t("Points de vente permis"), font=("Segoe UI Semibold", 10), foreground=TEXTE,
                 background=CARTE).pack(anchor="w", pady=(10, 2))
        self.pdv_tous = tk.BooleanVar(value=True)
        self.boite_pdv_tous = ttk.Checkbutton(droite, text=t("Tous les points de vente"), variable=self.pdv_tous,
                                              style="Carte.TCheckbutton", command=self._etat_cases_pdv)
        self.boite_pdv_tous.pack(anchor="w", pady=1)
        self.cases_pdv: dict[str, tk.BooleanVar] = {}
        self.boites_pdv: dict[str, ttk.Checkbutton] = {}
        for p in points_de_vente(lire_config(self.racine / "config.toml")):
            self.cases_pdv[p.code] = tk.BooleanVar()
            boite = ttk.Checkbutton(droite, text=p.libelle, variable=self.cases_pdv[p.code], style="Carte.TCheckbutton")
            boite.pack(anchor="w", padx=(18, 0), pady=1)
            self.boites_pdv[p.code] = boite
        tk.Label(droite, text=t("Droits"), font=("Segoe UI Semibold", 10), foreground=TEXTE,
                 background=CARTE).pack(anchor="w", pady=(10, 2))
        self.exporter = tk.BooleanVar(value=True)
        self.boite_exporter = ttk.Checkbutton(droite, text=t("Exporter les données (Excel, CSV, PDF, images)"),
                                              variable=self.exporter, style="Carte.TCheckbutton")
        self.boite_exporter.pack(anchor="w", pady=1)
        self.supprimer_permis = tk.BooleanVar(value=True)
        self.boite_supprimer = ttk.Checkbutton(droite, text=t("Supprimer des éléments"),
                                               variable=self.supprimer_permis, style="Carte.TCheckbutton")
        self.boite_supprimer.pack(anchor="w", pady=1)
        self.note = tk.Label(droite, text="", font=("Segoe UI", 9), foreground=TEXTE_DOUX, background=CARTE,
                             wraplength=330, justify="left")
        self.note.pack(anchor="w", pady=(8, 4))
        rangee = tk.Frame(droite, background=CARTE)
        rangee.pack(anchor="w")
        Bouton(rangee, "💾  " + t("Enregistrer les accès"), self.enregistrer_acces, "accent", fond=CARTE).pack(
            side="left")
        self.afficher()

    # ------------------------------------------------------------------ arbre des accès
    def _remplir_arbre(self) -> None:
        """Rubriques du menu et leurs fonctions (pages et fenêtres), puis les actions dans les fenêtres. Clé d'une
        fonction : clé de la page (« correspondance ») ou titre de la fenêtre (« Liste des articles »)."""
        from .interface import ACCUEIL, LIBELLES_MENU, MENU_GROUPES
        from .utilisateurs import ACTIONS_FENETRES

        def ajouter(parent, cle, libelle, tags=()):
            self.arbre.insert(parent, "end", iid=cle, text=libelle, open=True, tags=tags)
            self.libelle_noeud[cle] = libelle
            self.coches[cle] = False

        for nom, icone, elements in MENU_GROUPES:
            parent = ""
            if nom:
                parent = f"rubrique:{nom}"
                ajouter("", parent, f"{icone}  {t(nom)}", ("rubrique",))
            for e in elements:
                if isinstance(e, int):
                    if e >= len(PAGES):
                        continue  # page Utilisateurs : administrateurs seulement
                    cle = PAGES[e]
                    libelle = t(LIBELLES_MENU[e]) if e in LIBELLES_MENU else re.sub(
                        r"^\d+\.\s*", "", self.libelles.get(cle, cle))
                    ajouter(parent, cle, libelle, ("fixe",) if e == ACCUEIL else ())
                    self.pages_noeud[cle] = cle
                else:
                    if e[1] in self.coches:
                        continue
                    ajouter(parent, e[1], f"{e[0]}  {t(e[1])}")
                    self.pages_noeud[e[1]] = PAGES[e[2]] if e[2] < len(PAGES) else ""
        racine_actions = "rubrique:actions"
        ajouter("", racine_actions, "🔒  " + t("Actions dans les fenêtres"), ("rubrique",))
        for groupe, actions in ACTIONS_FENETRES.items():
            if groupe == "Général":
                continue  # « Supprimer » : case de la section Droits (demande du propriétaire du 2026-10-30)
            for action in actions:
                ajouter(racine_actions, f"action:{action}", f"{t(action)}  ({t(groupe)})")
                self.actions_fenetres.add(action)

    def _dessiner(self) -> None:
        for cle in self.coches:
            if cle.startswith("rubrique:"):
                enfants = self.arbre.get_children(cle)
                self.coches[cle] = bool(enfants) and all(self.coches[e] for e in enfants)
                partiel = any(self.coches[e] for e in enfants) and not self.coches[cle]
                marque = "☑" if self.coches[cle] else ("◩" if partiel else "☐")
            else:
                marque = "☑" if self.coches[cle] else "☐"
            self.arbre.item(cle, text=f"{marque}  {self.libelle_noeud[cle]}")

    def _clic_arbre(self, evenement) -> str:
        cle = self.arbre.identify_row(evenement.y)
        profil = self._interne(self.profil_choisi.get())
        if not cle or profil == ADMIN or cle == "accueil":
            return "break"
        if self.arbre.identify_element(evenement.x, evenement.y) == "Treeitem.indicator":
            return ""  # flèche : déplier / replier
        valeur = not self.coches[cle]
        for c in [cle, *self.arbre.get_children(cle)]:
            if c != "accueil":
                self.coches[c] = valeur
        self._dessiner()
        return "break"

    # ------------------------------------------------------------------ affichage
    def afficher(self, choisi: str | None = None) -> None:
        self.tableau.delete(*self.tableau.get_children())
        for u in self.registre.utilisateurs:
            self.tableau.insert("", "end", iid=u.nom, tags=() if u.actif else ("inactif",), values=(
                u.nom, t(u.profil), t("Actif") if u.actif else t("Désactivé"),
                u.derniere_connexion.replace("T", " ")))
        rayer(self.tableau)
        profils = [t(p) for p in self.registre.profils]  # noms affichés (profils de départ traduits)
        self.liste_profils_compte.configure(values=profils)
        self.liste_profils.configure(values=profils)
        if self.profil.get() not in profils:
            self.profil.set(t("Employé") if t("Employé") in profils else profils[-1])
        self.profil_choisi.set(t(choisi) if choisi else (self.profil_choisi.get() if self.profil_choisi.get() in profils
                                                         else profils[0]))
        self.afficher_acces()

    def _interne(self, affiche: str) -> str:
        """Nom affiché -> nom du profil dans le registre."""
        return next((p for p in self.registre.profils if t(p) == affiche), affiche)

    def afficher_acces(self) -> None:
        profil = self._interne(self.profil_choisi.get())
        pages = set(self.registre.profils.get(profil, [])) | {"accueil"}
        admin = profil == ADMIN
        refusees = set(self.registre.fonctions_refusees.get(profil, []))
        permises = self.registre.fonctions_permises.get(profil)
        for cle in self.coches:
            if cle.startswith("rubrique:"):
                continue
            if admin:
                self.coches[cle] = True
            elif cle.startswith("action:"):
                self.coches[cle] = cle[len("action:"):] not in refusees
            elif permises is not None:  # accès par fonction
                self.coches[cle] = cle in permises or cle == "accueil"
            elif cle in PAGES:  # ancien modèle : la page elle-même
                self.coches[cle] = cle in pages
            else:  # fenêtre : sa page est permise et la fonction n'est pas retirée
                self.coches[cle] = self.pages_noeud.get(cle) in pages and cle not in refusees
        self._dessiner()
        codes = None if admin else self.registre.points_vente.get(profil)
        self.pdv_tous.set(codes is None)
        for code, variable in self.cases_pdv.items():
            variable.set(codes is None or code in codes)
        self.boite_pdv_tous.state(["disabled"] if admin else ["!disabled"])
        self.exporter.set(admin or profil not in self.registre.sans_export)
        self.boite_exporter.state(["disabled"] if admin else ["!disabled"])
        self.supprimer_permis.set(admin or "Supprimer" not in refusees)
        self.boite_supprimer.state(["disabled"] if admin else ["!disabled"])
        self._etat_cases_pdv()
        n = sum(1 for u in self.registre.utilisateurs if u.profil == profil)
        self.note.configure(text=(t("L'administrateur voit toutes les pages et gère les utilisateurs.") if admin
                                  else t("Accueil toujours visible. Une fonction non cochée disparaît du menu ; "
                                         "une action non cochée est refusée dans sa fenêtre.")) + "\n"
                            + t("{n} compte(s) avec ce profil ; les changements s'appliquent à leur prochaine "
                                "connexion.", n=n))

    def _etat_cases_pdv(self) -> None:
        """« Tous les points de vente » coché : les cases une à une sont grisées (tous, y compris les futurs)."""
        admin = self._interne(self.profil_choisi.get()) == ADMIN
        for code, boite in self.boites_pdv.items():
            if self.pdv_tous.get():
                self.cases_pdv[code].set(True)
            boite.state(["disabled"] if admin or self.pdv_tous.get() else ["!disabled"])

    def choisir(self) -> None:
        selection = self.tableau.selection()
        if not selection:
            return
        u = self.registre.trouver(selection[0])
        self.nom.set(u.nom)
        self.profil.set(t(u.profil))
        self.mdp.set("")
        self.profil_choisi.set(t(u.profil))
        self.afficher_acces()

    def _selection(self):
        selection = self.tableau.selection()
        if not selection:
            messagebox.showinfo(self.titre, t("Choisissez d'abord un compte dans le tableau."), parent=self)
            return None
        return self.registre.trouver(selection[0])

    def _faire(self, action, message: str = "") -> bool:
        try:
            action()
        except ErreurUtilisateur as exc:
            messagebox.showwarning(self.titre, t(str(exc)), parent=self)
            self.registre = Registre(self.racine)  # annule ce qui n'a pas été enregistré
            return False
        self.registre.enregistrer()
        self.afficher()
        if message:
            messagebox.showinfo(self.titre, message, parent=self)
        return True

    # ------------------------------------------------------------------ comptes
    def ajouter(self) -> None:
        nom = self.nom.get().strip()
        if self._faire(lambda: self.registre.ajouter(nom, self._interne(self.profil.get()), self.mdp.get()),
                       t("Compte « {nom} » créé avec le profil {profil}.", nom=nom, profil=self.profil.get())):
            self.mdp.set("")

    def changer_profil(self) -> None:
        u = self._selection()
        if u:
            self._faire(lambda: self.registre.changer_profil(u.nom, self._interne(self.profil.get())))

    def nouveau_mot_de_passe(self) -> None:
        u = self._selection()
        if not u:
            return
        mdp = simpledialog.askstring(self.titre, t("Nouveau mot de passe pour {nom} :", nom=u.nom), show="•",
                                     parent=self)
        if mdp is not None:
            self._faire(lambda: self.registre.changer_mot_de_passe(u.nom, mdp), t("Mot de passe changé."))

    def basculer(self) -> None:
        u = self._selection()
        if u:
            if u.nom == self.moi and u.actif:
                messagebox.showwarning(self.titre, t("Vous ne pouvez pas désactiver votre propre compte."),
                                       parent=self)
                return
            self._faire(lambda: self.registre.activer(u.nom, not u.actif))

    def supprimer(self) -> None:
        u = self._selection()
        if not u:
            return
        if u.nom == self.moi:
            messagebox.showwarning(self.titre, t("Vous ne pouvez pas supprimer votre propre compte."), parent=self)
            return
        if messagebox.askyesno(self.titre, t("Supprimer le compte « {nom} » ?", nom=u.nom), parent=self):
            self._faire(lambda: self.registre.supprimer(u.nom))

    # ------------------------------------------------------------------ profils
    def nouveau_profil(self) -> None:
        nom = simpledialog.askstring(self.titre, t("Nom du nouveau profil :"), parent=self)
        if nom and nom.strip():
            nom = " ".join(nom.split())
            if nom in self.registre.profils or self._interne(nom) in self.registre.profils:
                messagebox.showwarning(self.titre, t("Ce profil existe déjà."), parent=self)
                return
            if self._faire(lambda: self.registre.definir_profil(nom, ["accueil", "guide", "faq"])):
                self.profil_choisi.set(nom)
                self.afficher_acces()

    def supprimer_profil(self) -> None:
        profil = self._interne(self.profil_choisi.get())
        if profil and messagebox.askyesno(self.titre, t("Supprimer le profil « {nom} » ?", nom=t(profil)),
                                          parent=self):
            self._faire(lambda: self.registre.supprimer_profil(profil))

    def enregistrer_acces(self) -> None:
        profil = self._interne(self.profil_choisi.get())
        if profil == ADMIN:
            messagebox.showinfo(self.titre, t("Le profil Administrateur a toujours accès à tout."), parent=self)
            return
        fonctions = [c for c, v in self.coches.items() if v and not c.startswith(("rubrique:", "action:"))]
        # pages à pouvoir afficher : celles cochées et celles des fenêtres cochées (ex. onglets des Rapports)
        pages = {self.pages_noeud.get(c, "") for c in fonctions} - {""}
        refusees = [c[len("action:"):] for c, v in self.coches.items() if c.startswith("action:") and not v]
        if not self.supprimer_permis.get():
            refusees.append("Supprimer")
        codes = None if self.pdv_tous.get() else [c for c, v in self.cases_pdv.items() if v.get()]

        def enregistrer():
            self.registre.definir_export(profil, self.exporter.get())
            self.registre.definir_points_vente(profil, codes)
            self.registre.definir_acces(profil, fonctions, sorted(pages))
            self.registre.definir_fonctions(profil, refusees)

        self._faire(enregistrer, t("Accès du profil {nom} enregistrés.", nom=t(profil)))
