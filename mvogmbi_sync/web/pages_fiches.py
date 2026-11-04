"""Fiches de Sage créées ou changées depuis les listes, comme l'application Windows :

- « ➕ Ajouter » des listes des clients et des fournisseurs = `fenetre_gestion.DialogueTiers` (Nom *, Contact, adresse,
  téléphones, courriel, site Web, n° de taxe du fournisseur ; compte de produits / de charges ; « Ce client utilise mes
  n° articles ») puis « ✔ Créer dans Sage » (`robot_tiers.creer_dans_sage`, l'application ouvre Sage elle-même) ;
- « ✎ Modifier » et « 🗑 Supprimer » de la liste des articles = `fenetre_fiches_articles.modifier_article` /
  `supprimer_article` (Sage d'abord, puis les articles Clover reliés).
"""

from __future__ import annotations

import re
from urllib.parse import quote

from .pages import Contexte, Fonction, csrf, page
from .pages_compta import _message, action_permise
from .serveur import Reponse, echapper as e


# --------------------------------------------------------------------------------------------- nouveau client / fournisseur
def _comptes_proposes(ctx: Contexte, genre: str) -> list[str]:
    """Comptes de détail du plan comptable : produits (4xxx) pour un client, charges (5xxx) pour un fournisseur."""
    from ..plan_comptable import DETAIL, comptes_connus

    try:
        connus = comptes_connus(ctx.racine, ctx.config)
    except (Exception, SystemExit):  # noqa: BLE001 — Sage absent : liste vide, compte tapé à la main
        return []
    classe = "4" if genre == "clients" else "5"
    return [f"{c.numero} {c.nom}" for c in sorted(connus.values(), key=lambda c: int(c.numero))
            if c.numero.startswith(classe) and c.type in DETAIL and not c.inactif]


def nouveau_tiers(ctx: Contexte, genre: str) -> Reponse:
    from ..robot_tiers import LIBELLES, FicheTiers
    from . import taches

    titre = "Nouveau client" if genre == "clients" else "Nouveau fournisseur"
    liste = "/clients" if genre == "clients" else "/fournisseurs-liste"
    cles = [c for c in LIBELLES if c != "no_taxe" or genre == "fournisseurs"]
    defaut = FicheTiers("")
    v = {c: (" ".join(ctx.req.champ(c).split()) if ctx.req.methode == "POST" else str(getattr(defaut, c) or ""))
         for c in cles}
    compte = ctx.req.champ("compte").strip().split(" ")[0]
    mes_numeros = ctx.req.methode == "GET" or bool(ctx.req.champ("mes_numeros"))
    message = ""
    if ctx.req.methode == "POST":
        erreur = ""
        if compte:
            from ..plan_comptable import comptes_connus, problemes

            try:
                erreurs = problemes([compte], comptes_connus(ctx.racine, ctx.config))
            except (Exception, SystemExit):  # noqa: BLE001 — plan illisible : rien n'est bloqué
                erreurs = []
            erreur = " ; ".join(erreurs)
        if not erreur and not v["nom"]:
            erreur = "Le nom est obligatoire."
        if not erreur and v.get("courriel") and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", v["courriel"]):
            erreur = "Courriel invalide."
        if not erreur and v.get("no_taxe"):
            v["no_taxe"] = v["no_taxe"].replace(" ", "").upper()
            if not re.fullmatch(r"\d{9}(RP|RT|RZ)\d{4}", v["no_taxe"]):
                erreur = "N° d'inscription aux taxes invalide (ex. 123456789RT0001)."
        if erreur:
            message = _message(erreur=erreur)
        else:
            fiche = FicheTiers(**v, compte=compte, mes_numeros=mes_numeros)

            def creer(journal):
                from ..robot_tiers import creer_dans_sage

                journal("Création dans Sage… (l'application ouvre Sage elle-même s'il est fermé : environ une minute)")
                r = creer_dans_sage(ctx.racine, ctx.config, genre, [fiche])[0]
                if not r["cree"]:
                    raise RuntimeError("Non créé : " + " ; ".join(r["messages"]))
                ctx.app.memoire.pop(("sage", "liste", genre), None)
                return [f"« {fiche.nom} » est créé dans Sage."] + (
                    [] if r["mes_numeros"] else ["Cochez « utilise mes numéros d'articles » dans sa fiche de Sage."])

            return taches.lancer(ctx, f"{titre} : {fiche.nom}", creer, liste, sage=True)
    champs = ""
    for cle in cles:
        taille = 34 if cle in ("nom", "rue1", "rue2", "courriel", "site") else 24
        champs += (f"<label>{e(LIBELLES[cle])}{' *' if cle == 'nom' else ''}</label><input name='{cle}' "
                   f"value='{e(v[cle])}' size='{taille}'>")
    comptes = "".join(f"<option value='{e(x)}'>" for x in _comptes_proposes(ctx, genre))
    case = "Ce client utilise mes n° articles" if genre == "clients" else "Ce fournisseur utilise mes n° d'articles"
    corps = (message + f"<form method='post' class='carte'>{csrf(ctx)}<div class='grille-tiers'>{champs}</div>"
             f"<div class='barre-onglet'><div><label>{'Compte de produits' if genre == 'clients' else 'Compte de charges'}"
             f"</label><input name='compte' list='comptes-tiers' value='{e(compte)}' size='44'><datalist "
             f"id='comptes-tiers'>{comptes}</datalist></div><label class='case'><input type='checkbox' "
             f"name='mes_numeros' value='1'{' checked' if mes_numeros else ''}> {case}</label></div>"
             + ("<p class='note'>N° d'inscription aux taxes : 9 chiffres + RP, RT ou RZ + 4 chiffres (ex. "
                "123456789RT0001), ou vide.</p>" if genre == "fournisseurs" else "")
             + "<div class='ligne-etat'>La fiche est créée dans Sage, avec « utilise mes numéros d'articles » coché "
               "(nécessaire aux imports de factures).</div>"
             + f"<div class='barre-onglet'><span class='a-droite'><button>✔ Créer dans Sage</button> <a class='ouvrir' "
               f"href='{liste}'>✖ Fermer</a></span></div></form>")
    return Reponse(corps=page(ctx, titre, corps))


# --------------------------------------------------------------------------------------------- article de Sage
DROIT = "Modifier les articles dans Sage et Clover"


def formulaire_article(ctx: Contexte, op: str, numero: str, description: str) -> str:
    """Petites fenêtres « Modifier l'article … » et « Supprimer l'article … » de la liste des articles."""
    from ..fenetre_fiches_articles import ids_clover

    try:
        liens = ids_clover(ctx.racine, numero)
    except Exception:  # noqa: BLE001
        liens = []
    caches = (f"{csrf(ctx)}<input type='hidden' name='numero' value='{e(numero)}'><input type='hidden' "
              f"name='ancienne' value='{e(description)}'>")
    if op == "modifier":
        return (f"<form method='post' action='/article-sage' class='carte'>{caches}<h2>Modifier l'article "
                f"{e(numero)}</h2><div class='grille-champs'><label>Description</label><input name='description' "
                f"value='{e(description)}' size='48'><span></span><label class='case'><input type='checkbox' "
                "name='inactif' value='1'> Article inactif dans Sage</label><span></span><label class='case'><input "
                f"type='checkbox' name='clover' value='1'{' checked' if liens else ' disabled'}> Renommer aussi "
                f"l'article Clover relié ({len(liens)})</label></div><p class='note'>Sage doit être fermé : "
                "l'application l'ouvre elle-même.</p><div class='barre-onglet'><span class='a-droite'><button "
                "name='action' value='modifier'>✔ Enregistrer dans Sage</button></span></div></form>")
    question = f"Supprimer l'article {numero} ({description}) de Sage ?"
    if liens:
        question += f" Les {len(liens)} article(s) Clover relié(s) seront aussi supprimés de Clover."
    question += (" Si Sage refuse (article encore en stock), l'article est rendu inactif dans Sage et l'article Clover "
                 "est gardé.")
    return (f"<form method='post' action='/article-sage' class='carte'>{caches}<h2>Supprimer l'article {e(numero)}</h2>"
            f"<p>{e(question)}</p><div class='barre-onglet'><span class='a-droite'><a class='ouvrir' href='/articles'>"
            "Non</a> <button class='danger' name='action' value='supprimer'>🗑 Oui, supprimer</button></span></div>"
            "</form>")


def article_sage(ctx: Contexte) -> Reponse:
    """Applique la modification ou la suppression (travail Sage), puis les articles Clover reliés."""
    from ..fenetre_fiches_articles import ids_clover
    from ..robot_fiches_articles import DemandeArticle, appliquer
    from . import taches

    if ctx.req.methode != "POST":
        from .serveur import redirection

        return redirection("/articles")
    action, numero = ctx.req.champ("action"), ctx.req.champ("numero").strip()
    if not action_permise(ctx, DROIT):
        return Reponse(corps=page(ctx, "Liste des articles", _message(erreur=f"Votre profil n'a pas le droit « {DROIT} ».")))
    if action == "supprimer" and not action_permise(ctx, "Supprimer"):
        return Reponse(corps=page(ctx, "Liste des articles", _message(erreur="Votre profil n'a pas le droit « Supprimer ».")))
    liens = ids_clover(ctx.racine, numero)
    if action == "modifier":
        ancienne = ctx.req.champ("ancienne")
        nouveau = " ".join(ctx.req.champ("description").split())
        demande = DemandeArticle("modifier", numero, nouveau if nouveau != ancienne else "",
                                 True if ctx.req.champ("inactif") else None)
        if not demande.description and demande.inactif is None:
            return Reponse(corps=page(ctx, "Liste des articles", _message(erreur="Rien à changer.")))
        renommer = bool(ctx.req.champ("clover")) and liens

        def travail(journal):
            r = appliquer(ctx.racine, ctx.config, [demande])[0]
            lignes = ["Sage : " + ("fait" if r["fait"] else " ; ".join(r["messages"]))]
            if r["fait"] and demande.description and renommer:
                from ..points_vente import client

                c = client(ctx.racine, None)
                for i in liens:
                    c.renommer_article(i, demande.description)
                lignes.append(f"Clover : {len(liens)} article(s) renommé(s)")
            return lignes

        return taches.lancer(ctx, f"Modifier l'article {numero}", travail, f"/articles?texte={quote(numero)}",
                             sage=True)

    def supprimer(journal):
        r = appliquer(ctx.racine, ctx.config, [DemandeArticle("supprimer", numero)])[0]
        if r["fait"]:
            lignes = ["Sage : article supprimé"]
        else:  # mouvements : rendu inactif
            r2 = appliquer(ctx.racine, ctx.config, [DemandeArticle("modifier", numero, inactif=True)])[0]
            lignes = [f"Sage : suppression refusée ({' ; '.join(r['messages'])[:200]}) ; article rendu inactif : "
                      + ("fait" if r2["fait"] else " ; ".join(r2["messages"]))]
        if liens and r["fait"]:
            from ..points_vente import client

            c = client(ctx.racine, None)
            for i in liens:
                c.supprimer_article(i)
            lignes.append(f"Clover : {len(liens)} article(s) supprimé(s)")
        return lignes

    return taches.lancer(ctx, f"Supprimer l'article {numero}", supprimer, "/articles", sage=True)



FONCTIONS = [
    Fonction("/client-nouveau", "Liste des clients", "encaissements", lambda ctx: nouveau_tiers(ctx, "clients"), "👥",
             "Vente", menu=False),
    Fonction("/fournisseur-nouveau", "Liste des fournisseurs", "fournisseurs",
             lambda ctx: nouveau_tiers(ctx, "fournisseurs"), "🏭", "Fournisseur", menu=False),
    Fonction("/article-sage", "Liste des articles", "correspondance", article_sage, "📚", "Articles", menu=False),
]
