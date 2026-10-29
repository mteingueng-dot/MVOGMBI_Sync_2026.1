"""Fenêtre « Transferts entre points de vente » : liste des transferts, saisie d'un transfert (départ, arrivée, date,
articles et quantités), puis transfert dans Sage (entre les deux dépôts) et dans Clover (stock des deux marchands)."""

from __future__ import annotations

import threading
import tkinter as tk
import tomllib
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from tkinter import messagebox, ttk

from .design import (FenetreOutil, CARTE, ROUGE, TEXTE_DOUX, VERT_FONCE, Bouton, ChampDate, ChampRecherche, Rangee, cadre_tableau,
                     defilement, rayer)
from .langues import t


class FenetreTransferts(FenetreOutil):
    def __init__(self, parent, racine: Path):
        from .points_vente import points_de_vente
        from .transferts import Registre

        super().__init__(parent)
        self.racine = Path(racine)
        self.config_toml = tomllib.loads((self.racine / "config.toml").read_text(encoding="utf-8"))
        self.points = {p.code: p for p in points_de_vente(self.config_toml, actifs=True)}
        self.registre = Registre(self.racine)
        self.courant = None  # transfert affiché dans le formulaire
        self.stocks: dict[str, dict[str, Decimal]] = {}
        self.articles: list[str] = []
        self.en_cours = False
        self.title(t("Transferts entre points de vente"))
        self.configure(background=CARTE, padx=14, pady=10)
        self.transient(parent)
        self.geometry("1100x720")
        self.minsize(640, 520)
        tk.Label(self, text=t("Des articles passent d'un point de vente à l'autre : dans Sage, transfert entre les deux "
                              "dépôts (même valeur, sans vente) ; dans Clover, stock diminué au départ et augmenté à "
                              "l'arrivée. Sage d'abord (vérifié), Clover ensuite ; un transfert n'est jamais fait deux "
                              "fois."), background=CARTE, foreground=TEXTE_DOUX, justify="left", anchor="w",
                 wraplength=1050).pack(fill="x")

        # liste des transferts
        haut = Rangee(self)
        haut.pack(fill="x", pady=(8, 4))
        haut.ajouter(Bouton(haut, "➕  " + t("Nouveau transfert"), self.nouveau, fond=CARTE, petit=True))
        haut.ajouter(Bouton(haut, "🗑  " + t("Supprimer"), self.supprimer, "secondaire", fond=CARTE, petit=True))
        cadre = cadre_tableau(self)
        cadre.pack(fill="x")
        colonnes = (("numero", "N°", 90), ("jour", "Date", 95), ("de", "De", 170), ("vers", "Vers", 170),
                    ("articles", "Articles", 70), ("quantite", "Quantité", 80), ("etat", "État", 120),
                    ("messages", "Remarques", 300))
        self.liste = ttk.Treeview(cadre, columns=[c[0] for c in colonnes], show="headings", height=6,
                                  selectmode="browse")
        for cle, titre, largeur in colonnes:
            self.liste.heading(cle, text=t(titre))
            self.liste.column(cle, width=largeur, anchor="e" if cle in ("articles", "quantite") else "w",
                              stretch=cle == "messages")
        self.liste.tag_configure("termine", foreground=TEXTE_DOUX)
        self.liste.tag_configure("a_completer", background="#fde2e4")
        self.liste.pack(side="left", fill="x", expand=True)
        defilement(self.liste)
        self.liste.bind("<<TreeviewSelect>>", lambda _e: self.choisir())

        # formulaire
        forme = ttk.LabelFrame(self, text=t("Transfert"), padding=8)
        forme.pack(fill="both", expand=True, pady=(10, 0))
        ligne = Rangee(forme)
        ligne.pack(fill="x")
        self.numero = ligne.ajouter(tk.Label(ligne, text="", font=("Segoe UI Semibold", 11), foreground=VERT_FONCE,
                                             background=ligne.cget("background")), 14)
        groupe = ligne.ajouter(ligne.groupe(), 12)
        ttk.Label(groupe, text=t("Date")).pack(side="left", padx=(0, 4))
        self.jour = tk.StringVar(value=date.today().isoformat())
        ChampDate(groupe, self.jour).pack(side="left")
        libelles = [p.libelle for p in self.points.values()]
        self.de, self.vers = tk.StringVar(), tk.StringVar()
        for texte, variable in ((t("De"), self.de), (t("Vers"), self.vers)):
            groupe = ligne.ajouter(ligne.groupe(), 12)
            ttk.Label(groupe, text=texte).pack(side="left", padx=(0, 4))
            liste = ttk.Combobox(groupe, textvariable=variable, values=libelles, state="readonly", width=24)
            liste.pack(side="left")
            liste.bind("<<ComboboxSelected>>", lambda _e: self.lire_stocks())
        groupe = ligne.ajouter(ligne.groupe())
        ttk.Label(groupe, text=t("Note")).pack(side="left", padx=(0, 4))
        self.note = tk.StringVar()
        ttk.Entry(groupe, textvariable=self.note, width=30).pack(side="left")

        ajout = Rangee(forme)
        ajout.pack(fill="x", pady=(8, 4))
        groupe = ajout.ajouter(ajout.groupe(), 10)
        ttk.Label(groupe, text=t("Article Sage")).pack(side="left", padx=(0, 4))
        self.article = tk.StringVar()
        self.champ_article = ChampRecherche(groupe, self.article, [], largeur=44)
        self.champ_article.pack(side="left")
        groupe = ajout.ajouter(ajout.groupe(), 10)
        ttk.Label(groupe, text=t("Quantité")).pack(side="left", padx=(0, 4))
        self.quantite = tk.StringVar()
        champ = ttk.Entry(groupe, textvariable=self.quantite, width=9)
        champ.pack(side="left")
        champ.bind("<Return>", lambda _e: self.ajouter())
        ajout.ajouter(Bouton(ajout, "➕  " + t("Ajouter la ligne"), self.ajouter, "secondaire", fond=CARTE, petit=True))
        ajout.ajouter(Bouton(ajout, "🗑  " + t("Retirer la ligne"), self.retirer, "secondaire", fond=CARTE,
                             petit=True))

        cadre = cadre_tableau(forme)
        cadre.pack(fill="both", expand=True)
        colonnes = (("numero", "N° Sage", 130), ("description", "Description", 340), ("quantite", "Quantité", 90),
                    ("depart", "Stock Sage au départ", 140), ("arrivee", "Stock Sage à l'arrivée", 150))
        self.lignes = ttk.Treeview(cadre, columns=[c[0] for c in colonnes], show="headings", height=7,
                                   selectmode="browse")
        for cle, titre, largeur in colonnes:
            self.lignes.heading(cle, text=t(titre))
            self.lignes.column(cle, width=largeur, anchor="w" if cle in ("numero", "description") else "e",
                               stretch=cle == "description")
        self.lignes.tag_configure("insuffisant", background="#fff3c4")
        self.lignes.pack(side="left", fill="both", expand=True)
        defilement(self.lignes)

        bas = Rangee(forme)
        bas.pack(fill="x", pady=(8, 0))
        bas.ajouter(Bouton(bas, "💾  " + t("Enregistrer"), self.enregistrer, "secondaire", fond=CARTE))
        self.bouton_transferer = bas.ajouter(Bouton(bas, "▶  " + t("Transférer (Sage puis Clover)"), self.transferer,
                                                    fond=CARTE))
        self.etat = tk.Label(self, text="", background=CARTE, foreground=TEXTE_DOUX, anchor="w", justify="left",
                             wraplength=1050)
        self.etat.pack(fill="x", pady=(6, 0))
        self.afficher_liste()
        self.nouveau()
        self.lire_articles()
        if len(self.points) < 2:
            self.etat.configure(text=t("Il faut au moins deux points de vente actifs (« Administration > Clover », carte « Points de "
                                       "vente »), chacun avec son dépôt Sage."), foreground=ROUGE)

    # ------------------------------------------------------------------ données
    def _fil(self, travail, fin) -> None:
        def executer():
            try:
                resultat, erreur = travail(), ""
            except BaseException as exc:  # SystemExit compris : la fenêtre ne reste jamais « en cours »
                resultat, erreur = None, str(exc) or exc.__class__.__name__
            self.after(0, lambda: fin(resultat, erreur) if self.winfo_exists() else None)

        threading.Thread(target=executer, daemon=True).start()

    def _lire_sage(self, fonction):
        from .__main__ import lire_sage

        return lire_sage(self.config_toml, fonction, self.config_toml.get("sage_import", {}).get("fichier_entreprise"))

    def lire_articles(self) -> None:
        from .rapports import articles

        def fin(valeurs, erreur):
            if erreur:
                self.etat.configure(text="✘ " + erreur, foreground=ROUGE)
                return
            self.articles = valeurs
            self.champ_article.configurer_valeurs(valeurs)

        self._fil(lambda: self._lire_sage(articles), fin)

    def lire_stocks(self) -> None:
        """Stock Sage de chaque ligne dans le dépôt de départ et dans celui d'arrivée."""
        from .transferts import stocks_par_depot

        numeros = [self.lignes.set(i, "numero") for i in self.lignes.get_children()]
        if not numeros:
            return

        def fin(stocks, erreur):
            if not erreur:
                self.stocks = stocks
                self.afficher_lignes(self._lignes_formulaire())

        self._fil(lambda: self._lire_sage(lambda b: stocks_par_depot(b, numeros)), fin)

    def _point(self, libelle: str):
        return next((p for p in self.points.values() if p.libelle == libelle), None)

    # ------------------------------------------------------------------ liste
    def afficher_liste(self) -> None:
        from .transferts import A_COMPLETER, TERMINE

        self.liste.delete(*self.liste.get_children())
        for tr in sorted(self.registre.transferts, key=lambda x: (x.jour, x.numero), reverse=True):
            nom = {c: p.nom for c, p in self.points.items()}
            tags = ("termine",) if tr.etat == TERMINE else (("a_completer",) if tr.etat == A_COMPLETER else ())
            self.liste.insert("", "end", iid=tr.numero, tags=tags, values=(
                tr.numero, tr.jour, f"{tr.de} — {nom.get(tr.de, '?')}", f"{tr.vers} — {nom.get(tr.vers, '?')}",
                len(tr.lignes), f"{tr.total_quantite.normalize():f}".replace(".", ","), t(tr.etat),
                " ; ".join(tr.messages)))
        rayer(self.liste)

    def choisir(self) -> None:
        choix = self.liste.selection()
        if not choix:
            return
        tr = self.registre.trouver(choix[0])
        if tr is None:
            return
        self.courant = tr
        self.numero.configure(text=tr.numero)
        self.jour.set(tr.jour)
        self.de.set(self.points[tr.de].libelle if tr.de in self.points else "")
        self.vers.set(self.points[tr.vers].libelle if tr.vers in self.points else "")
        self.note.set(tr.note)
        self.afficher_lignes([(l.numero, l.description, l.quantite) for l in tr.lignes])
        self.lire_stocks()

    def nouveau(self) -> None:
        from .transferts import Transfert

        points = list(self.points.values())
        self.courant = Transfert(self.registre.nouveau_numero(), date.today().isoformat(),
                                 points[0].code if points else "", points[1].code if len(points) > 1 else "")
        self.numero.configure(text=self.courant.numero)
        self.jour.set(self.courant.jour)
        self.de.set(points[0].libelle if points else "")
        self.vers.set(points[1].libelle if len(points) > 1 else "")
        self.note.set("")
        self.afficher_lignes([])
        self.liste.selection_remove(self.liste.selection())

    def supprimer(self) -> None:
        choix = self.liste.selection()
        if not choix or not messagebox.askyesno(self.title(), t("Supprimer le transfert {n} ?", n=choix[0]),
                                                parent=self):
            return
        try:
            self.registre.supprimer(choix[0])
        except ValueError as exc:
            messagebox.showwarning(self.title(), t(str(exc)), parent=self)
            return
        self.afficher_liste()
        self.nouveau()

    # ------------------------------------------------------------------ lignes
    def _lignes_formulaire(self) -> list[tuple[str, str, Decimal]]:
        return [(self.lignes.set(i, "numero"), self.lignes.set(i, "description"),
                 Decimal(self.lignes.set(i, "quantite").replace(",", "."))) for i in self.lignes.get_children()]

    def afficher_lignes(self, lignes) -> None:
        self.lignes.delete(*self.lignes.get_children())
        de, vers = self._point(self.de.get()), self._point(self.vers.get())
        for numero, description, quantite in lignes:
            depots = self.stocks.get(numero, {})
            depart = depots.get(de.depot_sage) if de else None
            arrivee = depots.get(vers.depot_sage) if vers else None
            insuffisant = depart is not None and depart < quantite
            self.lignes.insert("", "end", tags=("insuffisant",) if insuffisant else (), values=(
                numero, description, f"{quantite.normalize():f}".replace(".", ","),
                "" if depart is None else f"{depart.normalize():f}".replace(".", ","),
                "" if arrivee is None else f"{arrivee.normalize():f}".replace(".", ",")))

    def ajouter(self) -> None:
        texte = self.article.get().strip()
        numero, _, description = texte.partition(" — ")
        if not numero or texte not in self.articles:
            messagebox.showinfo(self.title(), t("Choisissez l'article dans la liste de Sage."), parent=self)
            return
        try:
            quantite = Decimal(self.quantite.get().replace(",", ".").strip())
        except InvalidOperation:
            quantite = Decimal(0)
        if quantite <= 0:
            messagebox.showinfo(self.title(), t("Quantité à transférer : un nombre plus grand que 0."), parent=self)
            return
        lignes = [l for l in self._lignes_formulaire() if l[0] != numero.strip()] + [
            (numero.strip(), description.strip(), quantite)]
        self.afficher_lignes(lignes)
        self.article.set("")
        self.quantite.set("")
        self.lire_stocks()

    def retirer(self) -> None:
        for i in self.lignes.selection():
            self.lignes.delete(i)

    # ------------------------------------------------------------------ enregistrement et transfert
    def _depuis_formulaire(self):
        from .transferts import BROUILLON, LigneTransfert

        tr = self.courant
        if tr.sage or tr.clover:  # déjà commencé : seul l'état change
            return tr
        de, vers = self._point(self.de.get()), self._point(self.vers.get())
        tr.jour, tr.note = self.jour.get().strip(), self.note.get().strip()
        tr.de, tr.vers = (de.code if de else ""), (vers.code if vers else "")
        tr.lignes = [LigneTransfert(n, d, q) for n, d, q in self._lignes_formulaire()]
        tr.etat = BROUILLON
        return tr

    def enregistrer(self) -> bool:
        tr = self._depuis_formulaire()
        problemes = tr.problemes(self.points)
        self.registre.garder(tr)
        self.afficher_liste()
        self.liste.selection_set(tr.numero)
        self.etat.configure(text=("⚠ " + " ; ".join(t(p) for p in problemes)) if problemes
                            else "✔ " + t("Transfert {n} enregistré.", n=tr.numero),
                            foreground=ROUGE if problemes else VERT_FONCE)
        return not problemes

    def transferer(self) -> None:
        from .transferts import transferer

        if self.en_cours or not self.enregistrer():
            return
        tr = self.courant
        insuffisants = [self.lignes.set(i, "numero") for i in self.lignes.get_children()
                        if "insuffisant" in self.lignes.item(i, "tags")]
        texte = t("Transférer {n} article(s) de « {de} » vers « {vers} » ?\n\nSage : transfert entre les deux dépôts. "
                  "Clover : stock diminué au départ, augmenté à l'arrivée. L'application ouvre Sage elle-même s'il est "
                  "fermé ; s'il est ouvert, ne touchez ni au clavier ni à la souris pendant le transfert.",
                  n=len(tr.lignes), de=self.de.get(), vers=self.vers.get())
        if insuffisants:
            texte += "\n\n" + t("Attention : stock Sage au départ plus petit que la quantité pour {a}.",
                                a=", ".join(insuffisants))
        if not messagebox.askyesno(self.title(), texte, parent=self):
            return
        self.en_cours = True
        self.etat.configure(text=t("Transfert en cours (Sage puis Clover)…"), foreground=TEXTE_DOUX)

        def fin(resultat, erreur):
            from .transferts import Registre, TERMINE

            self.en_cours = False
            self.registre = Registre(self.racine)
            self.afficher_liste()
            if erreur:
                self.etat.configure(text="✘ " + erreur, foreground=ROUGE)
                return
            self.courant = resultat
            self.liste.selection_set(resultat.numero)
            self.lire_stocks()
            ok = resultat.etat == TERMINE
            self.etat.configure(text=("✔ " if ok else "⚠ ") + t("{n} : {etat}", n=resultat.numero, etat=t(resultat.etat))
                                + (" — " + " ; ".join(resultat.messages) if resultat.messages else ""),
                                foreground=VERT_FONCE if ok else ROUGE)

        self._fil(lambda: transferer(self.racine, self.config_toml, tr.numero), fin)
