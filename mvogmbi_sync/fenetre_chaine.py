"""Listes des documents de vente, d'achat et de stock (demande du propriétaire du 2026-11-01) : TOUS les types dans
une même liste (documents de Sage + documents de l'application), « Ajouter » demande le type à créer (comme
« Ajouter un document » de Sage), « Transformer » passe au type suivant de la chaîne (chaine_documents.py), et les
documents de stock se modifient ou se suppriment en reportant la correction dans Sage et Clover."""

from __future__ import annotations

import os
import threading
import tkinter as tk
from datetime import date
from decimal import Decimal
from pathlib import Path
from tkinter import messagebox, ttk

from . import documents as dc
from .design import CARTE, ROUGE, TEXTE_DOUX, VERT_FONCE, Bouton, ChampDate
from .fenetre_gestion import FenetreListe, _config, saisir_document
from .langues import t

ENTETES_VENTE = ["Date", "Type", "Facture", "Pièce", "Client", "Montant", "Reste dû", "État"]
ENTETES_ACHAT = ["Date", "Type", "Facture", "Pièce", "Fournisseur", "Montant", "Reste dû", "État"]
ENTETES_STOCK = ["Date", "Type", "Source", "Dépôt", "Lignes", "Quantité (+ entrée / − sortie)", "Montant", "État"]
STOCK_ENTREE, STOCK_SORTIE, STOCK_TRANSFERT, STOCK_PERTE, STOCK_INVENTAIRE, STOCK_TOURNANT = (
    "Entrée de stock", "Sortie de stock", "Transfert entre magasins", "Perte et démarque", "Inventaire Clover et Sage",
    "Inventaire tournant")
TYPES_STOCK = [STOCK_ENTREE, STOCK_SORTIE, STOCK_TRANSFERT, STOCK_PERTE, STOCK_INVENTAIRE, STOCK_TOURNANT]


def choisir(parent, titre: str, question: str, choix: list[tuple[str, str]], avec_date: bool = False,
            libelle_numero: str = "", cles_numero=()) -> tuple[str, str, str] | None:
    """Fenêtre de choix à boutons radio (comme Sage) : (clé, date, n°) ou None (Annuler)."""
    fenetre = tk.Toplevel(parent)
    fenetre.title(t(titre))
    fenetre.configure(background=CARTE, padx=16, pady=12)
    fenetre.transient(parent.winfo_toplevel())
    fenetre.resizable(False, False)
    tk.Label(fenetre, text=t(question), background=CARTE, anchor="w", justify="left").pack(fill="x", pady=(0, 6))
    valeur = tk.StringVar(value=choix[0][0])
    for cle, libelle in choix:
        ttk.Radiobutton(fenetre, text=t(libelle), value=cle, variable=valeur).pack(anchor="w", pady=1)
    jour, numero = tk.StringVar(value=date.today().isoformat()), tk.StringVar()
    if avec_date:
        ligne = tk.Frame(fenetre, background=CARTE)
        ligne.pack(fill="x", pady=(10, 0))
        tk.Label(ligne, text=t("Date"), background=CARTE, width=22, anchor="w").pack(side="left")
        ChampDate(ligne, jour, fond=CARTE).pack(side="left")
    zone_numero = tk.Frame(fenetre, background=CARTE)
    if libelle_numero:
        tk.Label(zone_numero, text=t(libelle_numero), background=CARTE, width=22, anchor="w").pack(side="left")
        ttk.Entry(zone_numero, textvariable=numero, width=18).pack(side="left")

        def montrer(*_):
            if valeur.get() in cles_numero:
                zone_numero.pack(fill="x", pady=(6, 0))
            else:
                zone_numero.pack_forget()

        valeur.trace_add("write", montrer)
        montrer()
    resultat: list = []
    boutons = tk.Frame(fenetre, background=CARTE)
    boutons.pack(side="bottom", fill="x", pady=(12, 0))

    def ok() -> None:
        resultat.append((valeur.get(), jour.get().strip(), numero.get().strip()))
        fenetre.destroy()

    Bouton(boutons, t("Annuler"), fenetre.destroy, "secondaire", fond=CARTE, petit=True).pack(side="right")
    Bouton(boutons, "✔  " + t("OK"), ok, fond=CARTE, petit=True).pack(side="right", padx=(0, 8))
    fenetre.bind("<Return>", lambda _e: ok())
    fenetre.bind("<Escape>", lambda _e: fenetre.destroy())
    fenetre.grab_set()
    fenetre.wait_window()
    return resultat[0] if resultat else None


class FenetreDocumentsChaine(FenetreListe):
    """`cote` : « vente », « achat » ou « stock ». Les lignes de Sage et celles de l'application sont réunies ;
    `refs` dit d'où vient chaque ligne : ("sage", None), ("doc", n°), ("bc", n°), ("fa", fichier), ("rt", n°)."""

    def __init__(self, parent, racine: Path, titre: str, lecture, cote: str, explication: str, largeurs: dict):
        self.cote = cote
        self.refs, self.refs_visibles = [], []
        super().__init__(parent, racine, titre, lecture, periode=True, explication=explication, largeurs=largeurs,
                         genre=f"documents_{cote}" if cote != "stock" else "documents_stock")
        if cote == "stock":
            self.barre.ajouter(Bouton(self.barre, "⬆  " + t("Passer dans Sage et Clover"), self.passer, "accent",
                                      fond=CARTE, petit=True))
        else:
            self.barre.ajouter(Bouton(self.barre, "🔀  " + t("Transformer"), self.transformer, "accent", fond=CARTE,
                                      petit=True))
            self.barre.ajouter(Bouton(self.barre, "⬆  " + t("Importer dans Sage"), self.importer, "secondaire",
                                      fond=CARTE, petit=True))
        self.tableau.configure(selectmode="browse")

    # ------------------------------------------------------------------ lignes de l'application
    def _entetes(self) -> list[str]:
        return ENTETES_STOCK if self.cote == "stock" else ENTETES_ACHAT if self.cote == "achat" else ENTETES_VENTE

    def _rangees_application(self) -> list[tuple[list, tuple]]:
        from .points_vente import DEPOT_DEFAUT

        registre = dc.Registre(self.racine)
        du, au = self.du.get() or "0000", self.au.get() or "9999"
        rangees = []
        for d in registre.documents:
            if not du <= d.date <= au:
                continue
            if self.cote == "stock":
                if d.genre != dc.STOCK:
                    continue
                signe = 1 if d.sens == dc.ENTREE else -1
                quantite = sum((Decimal(l.quantite) for l in d.lignes), Decimal(0)) * signe
                rangees.append(([d.date, t(d.sens) + " — " + t("application"), d.numero, d.depot or DEPOT_DEFAUT,
                                 len(d.lignes), quantite, d.sous_total, t(d.etat)], ("doc", d.numero)))
                continue
            if dc.cote(d.genre) != self.cote or (d.genre in dc.FACTURES_STOCK and d.etat == dc.IMPORTEE):
                continue  # une facture importée apparaît par sa ligne de Sage
            chaine = registre.chaine(d.numero)
            rangees.append(([d.date, t(dc.libelle(d.genre)), d.numero, " → ".join(chaine), d.tiers, d.total, None,
                             t(d.etat) + (f" → {d.lien}" if d.lien else "")], ("doc", d.numero)))
        if self.cote == "achat":
            from . import bons_commande as bc
            from .fournisseurs import IMPORTEE, Registre as Factures
            from .retours import IMPORTE as IMPORTE_RT, Registre as Retours

            for b in bc.Registre(self.racine).bons:
                if du <= b.date <= au:
                    rangees.append(([b.date, t("Bon de commande"), b.numero, "", b.fournisseur, b.total, None,
                                     t(b.etat) + (f" → {b.facture}" if b.facture else "")], ("bc", b.numero)))
            for f in Factures(self.racine).factures:
                if f.etat != IMPORTEE and du <= (f.date_facture or "") <= au:
                    origine = next((r.split(" : ", 1)[1] for r in f.remarques if r.startswith("Origine : ")), "")
                    rangees.append(([f.date_facture, t("Facture"), f.numero, origine, f.fournisseur_sage,
                                     f.total, None, t(f.etat)], ("fa", f.fichier)))
            for r in Retours(self.racine).retours:
                if du <= r.jour <= au and r.etat != IMPORTE_RT:
                    rangees.append(([r.jour, t("Facture de retour"), r.numero, r.facture_origine, r.fournisseur_sage,
                                     -sum((l.montant for l in r.lignes), Decimal(0)), None, t(r.etat)],
                                    ("rt", r.numero)))
        return rangees

    def afficher(self) -> None:
        from .page_rapports import remplir

        entetes = self._entetes()
        sage = [list(l) for l in self.lignes]
        if self.cote == "stock":  # colonne Dépôt (non lue dans Sage) et État
            sage = [l[:3] + [""] + l[3:] + [t("Dans Sage")] for l in sage]
        else:  # facture importée depuis l'application : sa chaîne (commande, livraison) dans « Pièce »
            registre = dc.Registre(self.racine)
            for l in sage:
                if l[2] and any(d.numero == l[2] for d in registre.documents):
                    l[3] = " → ".join(registre.chaine(l[2])) or l[3]
        tout = [(l, ("sage", None)) for l in sage] + self._rangees_application()
        tout.sort(key=lambda x: str(x[0][0]), reverse=True)
        texte = self.texte.get().strip().casefold()
        visibles = [x for x in tout if not texte or any(texte in str(v).casefold() for v in x[0])]
        self.visibles = [x[0] for x in visibles]
        self.refs_visibles = [x[1] for x in visibles]
        self.entetes = entetes
        remplir(self.tableau, entetes, self.visibles, self.largeurs,
                lambda i: ("application",) if self.refs_visibles[i][0] != "sage" else (), decroissant=False)
        self.tableau.tag_configure("application", foreground="#1f4fa0")
        self.etat.configure(text=t("{n} document(s) ; en bleu : documents de l'application.", n=len(visibles)),
                            foreground=TEXTE_DOUX)

    def _ref(self):
        choix = self.tableau.selection()
        if not choix:
            messagebox.showinfo(self.title(), t("Choisissez une ligne dans la liste."), parent=self)
            return None, None
        i = int(choix[0])
        return self.refs_visibles[i], self.visibles[i]

    def _auteur(self) -> str:
        racine = self.nametowidget(".")
        return racine._auteur() if hasattr(racine, "_auteur") else ""

    def _apres(self) -> None:
        self.after(0, self.afficher)

    # ------------------------------------------------------------------ actions
    def fiche(self) -> None:
        (sorte, ident), ligne = self._ref()
        if sorte is None:
            return
        if sorte == "sage":
            return super().fiche()
        if sorte == "doc":
            try:
                os.startfile(dc.ecrire_pdf(self.racine, dc.Registre(self.racine).document(ident)))
            except Exception as exc:
                messagebox.showerror(self.title(), str(exc), parent=self)
        elif sorte == "bc":
            from . import bons_commande as bc

            try:
                os.startfile(bc.refaire_pdf(self.racine, ident))
            except Exception as exc:
                messagebox.showerror(self.title(), str(exc), parent=self)
        else:
            messagebox.showinfo(self.title(), t("Ce document s'ouvre dans « Fournisseur > Factures fournisseurs » "
                                                "ou « Retours fournisseurs »."), parent=self)

    def ajouter(self) -> None:
        if self.cote == "stock":
            choix = choisir(self, "Ajouter un document", "Quel type de document de stock voulez-vous ajouter ?",
                            [(x, x) for x in TYPES_STOCK])
            if not choix:
                return
            racine = self.nametowidget(".")
            ouvrir = {STOCK_TRANSFERT: "ouvrir_transferts", STOCK_PERTE: "ouvrir_pertes",
                      STOCK_INVENTAIRE: "ouvrir_inventaire", STOCK_TOURNANT: "ouvrir_inventaire_tournant"}
            if choix[0] in ouvrir:
                getattr(racine, ouvrir[choix[0]])()
            else:
                saisir_document(self, self.racine, dc.STOCK, self._auteur(), self._apres,
                                sens=dc.ENTREE if choix[0] == STOCK_ENTREE else dc.SORTIE)
            return
        types = dc.TYPES_VENTE if self.cote == "vente" else dc.TYPES_ACHAT
        choix = choisir(self, "Ajouter un document", "Quel type de document voulez-vous ajouter ?",
                        [(g, dc.libelle(g)) for g in types])
        if not choix:
            return
        genre = choix[0]
        if genre == dc.COMMANDE_ACHAT:
            from .fenetre_gestion import saisir_bon_commande

            saisir_bon_commande(self, self.racine, apres=self._apres)
        elif genre == dc.FACTURE_ACHAT:
            from .fenetre_gestion import saisir_facture_achat

            saisir_facture_achat(self, self.racine)
        elif genre == dc.FACTURE_RETOUR_ACHAT:
            self.nametowidget(".").ouvrir_retours()
        else:
            saisir_document(self, self.racine, genre, self._auteur(), self._apres)

    def modifier(self) -> None:
        (sorte, ident), ligne = self._ref()
        if sorte is None:
            return
        if sorte == "doc":
            registre = dc.Registre(self.racine)
            d = registre.document(ident)
            if registre.modifiable(d):
                saisir_document(self, self.racine, d.genre, self._auteur(), self._apres, d.numero)
            elif d.genre == dc.STOCK and d.etat == dc.PASSE:
                self._refaire_stock(d)
            else:
                messagebox.showinfo(self.title(), t("{n} ({e}) ne peut plus être modifié.", n=d.numero, e=t(d.etat)),
                                    parent=self)
        elif sorte == "bc":
            from . import bons_commande as bc
            from .fenetre_gestion import saisir_bon_commande

            bon = next(b for b in bc.Registre(self.racine).bons if b.numero == ident)
            if bon.etat != bc.CREE:
                messagebox.showinfo(self.title(), t("{n} ({e}) ne peut plus être modifié.", n=bon.numero,
                                                    e=t(bon.etat)), parent=self)
                return
            saisir_bon_commande(self, self.racine, apres=self._apres, bon=bon)
        elif sorte == "sage" and self.cote == "stock":
            self._defaire_sage(ligne, refaire=True)
        else:
            messagebox.showinfo(self.title(), t("Une facture importée dans Sage se corrige par un retour ou un avoir "
                                                "(« Transformer »)."), parent=self)

    def supprimer(self) -> None:
        (sorte, ident), ligne = self._ref()
        if sorte is None:
            return
        try:
            if sorte == "doc":
                registre = dc.Registre(self.racine)
                d = registre.document(ident)
                if d.genre == dc.STOCK and d.etat == dc.PASSE:
                    if messagebox.askyesno(self.title(), t("{n} est dans Sage et Clover : il sera annulé par un "
                                                           "document inverse passé dans les deux. Continuer ?",
                                                           n=d.numero), parent=self):
                        self._en_fil(lambda: self._annuler(d.numero))
                    return
                if not messagebox.askyesno(self.title(), t("Supprimer {n} ?", n=d.numero), parent=self):
                    return
                registre.supprimer(ident)
            elif sorte == "bc":
                from . import bons_commande as bc

                if not messagebox.askyesno(self.title(), t("Supprimer {n} ?", n=ident), parent=self):
                    return
                bc.supprimer_bon(self.racine, ident)
            elif sorte == "sage" and self.cote == "stock":
                self._defaire_sage(ligne, refaire=False)
                return
            else:
                messagebox.showinfo(self.title(), t("Une facture importée dans Sage se corrige par un retour ou un "
                                                    "avoir (« Transformer »)."), parent=self)
                return
        except ValueError as exc:
            messagebox.showerror(self.title(), t(str(exc)), parent=self)
        self.afficher()

    def transformer(self) -> None:
        (sorte, ident), ligne = self._ref()
        if sorte is None:
            return
        if sorte == "doc":
            genre = dc.Registre(self.racine).document(ident).genre
        elif sorte == "bc":
            genre = dc.COMMANDE_ACHAT
        elif sorte == "fa":
            genre = dc.FACTURE_ACHAT
        elif sorte == "sage" and self.cote == "vente" and ligne[1] in (t("Facture"), "Facture"):
            messagebox.showinfo(self.title(), t("Facture de Sage : son retour ou son avoir se saisit avec "
                                                "« Ajouter » (Bon de retour, Facture de retour, Facture d'avoir)."),
                                parent=self)
            return
        else:
            messagebox.showinfo(self.title(), t("Ce document ne se transforme pas."), parent=self)
            return
        cibles = dc.TRANSFORMATIONS.get(genre, [])
        if not cibles:
            messagebox.showinfo(self.title(), t("Un document de ce type ne se transforme pas."), parent=self)
            return
        choix = choisir(self, "Transformation", "Vers quel type voulez-vous transformer le document ?",
                        [(c, dc.libelle(c)) for c in cibles], avec_date=True,
                        libelle_numero="N° de facture du fournisseur", cles_numero=(dc.FACTURE_ACHAT,))
        if not choix:
            return
        cible, jour, numero = choix
        try:
            date.fromisoformat(jour)
            if self.cote == "achat":
                from .chaine_documents import transformer_achat

                cree = transformer_achat(self.racine, (sorte, ident), cible, jour, self._auteur(), numero)
            else:
                cree = dc.Registre(self.racine).transformer(ident, cible, jour, self._auteur()).numero
        except (ValueError, StopIteration) as exc:
            messagebox.showerror(self.title(), t(str(exc)) or t("Document introuvable."), parent=self)
            return
        self.afficher()
        messagebox.showinfo(self.title(), t("{n} créé à partir de {o}.", n=cree, o=ident), parent=self)

    def importer(self) -> None:
        (sorte, ident), _ligne = self._ref()
        if sorte != "doc" or dc.Registre(self.racine).document(ident).genre not in dc.FACTURES_STOCK:
            messagebox.showinfo(self.title(), t("Choisissez une facture ou une facture de retour de l'application. Les "
                                                "factures d'achat s'importent depuis « Factures fournisseurs »."),
                                parent=self)
            return
        if not messagebox.askyesno(self.title(), t("Importer {n} dans Sage (Sage fermé) ? Le stock Clover suit.",
                                                   n=ident), parent=self):
            return
        self._en_fil(lambda: dc.importer_factures(self.racine, _config(self.racine), [ident]))

    def passer(self) -> None:
        (sorte, ident), _ligne = self._ref()
        if sorte != "doc":
            messagebox.showinfo(self.title(), t("Choisissez un document de stock de l'application (en bleu)."),
                                parent=self)
            return
        d = dc.Registre(self.racine).document(ident)
        if d.etat == dc.PASSE:
            messagebox.showinfo(self.title(), t("{n} est déjà dans Sage.", n=d.numero), parent=self)
            return
        if messagebox.askyesno(self.title(), t("Passer {n} ({s}, {l} ligne(s)) dans Sage et Clover ?", n=d.numero,
                                               s=t(d.sens), l=len(d.lignes)), parent=self):
            self._en_fil(lambda: dc.passer_stock(self.racine, _config(self.racine), d.numero))

    # ------------------------------------------------------------------ stock : défaire dans Sage et Clover
    def _annuler(self, numero: str) -> dict:
        from .chaine_documents import annuler_stock

        inverse = annuler_stock(self.racine, _config(self.racine), numero, self._auteur())
        return {inverse.numero: t(inverse.etat) + " ; " + " ; ".join(inverse.messages)}

    def _refaire_stock(self, d) -> None:
        if not messagebox.askyesno(self.title(), t("{n} est dans Sage et Clover : il sera annulé (document inverse "
                                                   "passé dans les deux), puis un nouveau document reprenant ses "
                                                   "lignes s'ouvrira pour être corrigé. Continuer ?", n=d.numero),
                                   parent=self):
            return
        lignes = [{"numero_sage": l.numero_sage, "description": l.description, "quantite": Decimal(l.quantite),
                   "prix": Decimal(l.prix or 0), "taxable": False, "taxe": ""} for l in d.lignes]

        def apres(_resultat):
            saisir_document(self, self.racine, dc.STOCK, self._auteur(), self._apres, sens=d.sens,
                            initial_lignes=lignes)

        self._en_fil(lambda: self._annuler(d.numero), apres)

    def _defaire_sage(self, ligne, refaire: bool) -> None:
        source, jour = str(ligne[2]), str(ligne[0])
        if not messagebox.askyesno(self.title(), t("Le document {s} du {j} vient de Sage : un document inverse sera "
                                                   "préparé puis passé dans Sage et Clover. Continuer ?", s=source,
                                                   j=jour), parent=self):
            return

        def travail():
            from .chaine_documents import document_inverse_sage

            config = _config(self.racine)
            inverses = document_inverse_sage(self.racine, config, source, jour, self._auteur())
            resultats = {}
            for doc in inverses:
                dc.passer_stock(self.racine, config, doc.numero)
                d = dc.Registre(self.racine).document(doc.numero)
                resultats[d.numero] = t(d.etat)
            return resultats

        def apres(_resultat):
            if refaire:
                saisir_document(self, self.racine, dc.STOCK, self._auteur(), self._apres)

        self._en_fil(travail, apres)

    def _en_fil(self, travail, apres=None) -> None:
        self.etat.configure(text=t("Traitement en cours…"), foreground=TEXTE_DOUX)

        def executer():
            try:
                resultat = travail()
                texte = "\n".join(f"{k} : {v}" for k, v in (resultat or {}).items()) or t("Terminé.")
                couleur = VERT_FONCE
            except Exception as exc:
                resultat, texte, couleur = None, "✘ " + str(exc), ROUGE

            def fin():
                self.charger(forcer=True)
                self.etat.configure(text=texte, foreground=couleur)
                if apres and resultat is not None:
                    apres(resultat)

            self.after(0, fin)

        threading.Thread(target=executer, daemon=True).start()


def ouvrir_documents(parent, racine: Path, genre: str):
    from . import listes_sage as ls

    if genre == "documents_vente":
        return FenetreDocumentsChaine(
            parent, racine, "Liste des documents de vente", lambda b, d, a: ls.documents(b, "ventes", d, a), "vente",
            "Tous les documents de vente : factures et encaissements de Sage, et devis, commandes, bons de livraison, "
            "retours et avoirs de l'application (en bleu). « Transformer » passe au document suivant ; seules les "
            "factures touchent le stock (Sage et Clover).", {"Client": 220, "Facture": 130, "Pièce": 200})
    if genre == "documents_achat":
        return FenetreDocumentsChaine(
            parent, racine, "Liste des documents d'achat", lambda b, d, a: ls.documents(b, "achats", d, a), "achat",
            "Tous les documents d'achat : factures, paiements et notes de crédit de Sage, et bons de commande, bons "
            "de réception, retours et factures en attente de l'application (en bleu). Bon de réception -> "
            "« Transformer » -> Facture : la facture est prête à importer (Factures fournisseurs).",
            {"Fournisseur": 220, "Facture": 130, "Pièce": 200})
    return FenetreDocumentsChaine(
        parent, racine, "Liste des documents de stock", lambda b, d, a: ls.documents_stock(b, d, a), "stock",
        "Ajustements et transferts de Sage, et documents de stock de l'application (en bleu). Modifier ou supprimer "
        "un document déjà passé le défait dans Sage ET Clover par un document inverse.",
        {"Source": 160, "Dépôt": 180, "Type": 220})
