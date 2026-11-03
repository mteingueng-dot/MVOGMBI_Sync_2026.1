"""Liste des articles : « Modifier » et « Supprimer » appliqués dans Sage ET Clover (demande du propriétaire du
2026-11-03). Sage : robot_fiches_articles (l'application ouvre Sage elle-même, Sage fermé) ; Clover : les articles
reliés au n° Sage (correspondance Confirmé / Automatique) sont renommés, ou supprimés."""

from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from .design import CARTE, TEXTE_DOUX, Bouton, action_permise
from .langues import t

DROIT = "Modifier les articles dans Sage et Clover"  # utilisateurs.ACTIONS_FENETRES["Articles"]


def _config(racine: Path) -> dict:
    import tomllib

    chemin = Path(racine) / "config.toml"
    return tomllib.loads(chemin.read_text(encoding="utf-8")) if chemin.exists() else {}


def ids_clover(racine: Path, numero: str) -> list[str]:
    from .correspondance import lire_correspondances
    from .points_vente import fichier_correspondance
    from .stock_clover import articles_clover_par_numero

    return articles_clover_par_numero(lire_correspondances(fichier_correspondance(racine, None))).get(numero, [])


def _executer(fenetre, racine: Path, travail, apres) -> None:
    def fil():
        try:
            texte, ok = travail()
        except Exception as exc:
            texte, ok = "✘ " + str(exc), False
        fenetre.after(0, lambda: (messagebox.showinfo(t("Liste des articles"), texte, parent=fenetre),
                                  apres() if ok and apres else None))

    threading.Thread(target=fil, daemon=True).start()


def modifier_article(parent, racine: Path, numero: str, description: str, apres=None) -> None:
    from .robot_fiches_articles import DemandeArticle, appliquer

    if not action_permise(parent, DROIT):
        return
    fenetre = tk.Toplevel(parent)
    fenetre.title(t("Modifier l'article {n}", n=numero))
    fenetre.configure(background=CARTE, padx=16, pady=12)
    fenetre.transient(parent.winfo_toplevel())
    nom, inactif, clover = tk.StringVar(value=description), tk.BooleanVar(value=False), tk.BooleanVar(value=True)
    tk.Label(fenetre, text=t("Description"), background=CARTE).grid(row=0, column=0, sticky="w", pady=4)
    ttk.Entry(fenetre, textvariable=nom, width=48).grid(row=0, column=1, sticky="w")
    ttk.Checkbutton(fenetre, text=t("Article inactif dans Sage"), variable=inactif).grid(row=1, column=1, sticky="w")
    liens = ids_clover(racine, numero)
    ttk.Checkbutton(fenetre, text=t("Renommer aussi l'article Clover relié ({n})", n=len(liens)),
                    variable=clover, state="normal" if liens else "disabled").grid(row=2, column=1, sticky="w")
    tk.Label(fenetre, text=t("Sage doit être fermé : l'application l'ouvre elle-même."), background=CARTE,
             foreground=TEXTE_DOUX).grid(row=3, column=0, columnspan=2, sticky="w", pady=(6, 0))

    def valider() -> None:
        nouveau = " ".join(nom.get().split())
        demande = DemandeArticle("modifier", numero, nouveau if nouveau != description else "",
                                 True if inactif.get() else None)
        fenetre.destroy()
        if not demande.description and demande.inactif is None:
            return

        def travail():
            r = appliquer(racine, _config(racine), [demande])[0]
            lignes = [t("Sage : {r}", r=t("fait") if r["fait"] else " ; ".join(r["messages"]))]
            if r["fait"] and demande.description and clover.get() and liens:
                from .points_vente import client

                c = client(racine, None)
                for i in liens:
                    c.renommer_article(i, demande.description)
                lignes.append(t("Clover : {n} article(s) renommé(s)", n=len(liens)))
            return "\n".join(lignes), r["fait"]

        _executer(parent, racine, travail, apres)

    Bouton(fenetre, "✔  " + t("Enregistrer dans Sage"), valider, fond=CARTE).grid(row=4, column=1, sticky="e", pady=(10, 0))


def supprimer_article(parent, racine: Path, numero: str, description: str, apres=None) -> None:
    from .robot_fiches_articles import DemandeArticle, appliquer

    if not action_permise(parent, DROIT):
        return
    liens = ids_clover(racine, numero)
    question = t("Supprimer l'article {n} ({d}) de Sage ?", n=numero, d=description)
    if liens:
        question += "\n\n" + t("Les {n} article(s) Clover relié(s) seront aussi supprimés de Clover.", n=len(liens))
    question += "\n\n" + t("Si Sage refuse (article encore en stock), l'article est rendu inactif dans Sage et "
                           "l'article Clover est gardé.")
    if not messagebox.askyesno(t("Liste des articles"), question, parent=parent):
        return

    def travail():
        config = _config(racine)
        r = appliquer(racine, config, [DemandeArticle("supprimer", numero)])[0]
        lignes = []
        if r["fait"]:
            lignes.append(t("Sage : article supprimé"))
        else:  # mouvements : rendu inactif
            r2 = appliquer(racine, config, [DemandeArticle("modifier", numero, inactif=True)])[0]
            lignes.append(t("Sage : suppression refusée ({m}) ; article rendu inactif : {r}",
                            m=" ; ".join(r["messages"])[:200], r=t("fait") if r2["fait"] else " ; ".join(r2["messages"])))
        if liens and r["fait"]:
            from .points_vente import client

            c = client(racine, None)
            for i in liens:
                c.supprimer_article(i)
            lignes.append(t("Clover : {n} article(s) supprimé(s)", n=len(liens)))
        return "\n".join(lignes), True

    _executer(parent, racine, travail, apres)
