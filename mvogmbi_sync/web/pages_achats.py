"""6e vague de l'application web (suite) : facture d'achat saisie à la main (ajoutée aux factures fournisseurs),
bons de commande (comme fenetre_bons_commande : proposition des articles à commander, création d'un bon par
fournisseur, PDF, comparaison avec la facture, réception, suppression) et retours fournisseurs (comme
fenetres_gestion3 : lignes reprises de la facture d'origine, import dans Sage puis stock Clover).
"""

from __future__ import annotations

import hashlib
import time
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from .consultations import Section, sections_html
from .pages import Contexte, Fonction, argent, csrf, page, tableau
from .pages_compta import _message, action_permise
from .serveur import Reponse, echapper as e, redirection


# --------------------------------------------------------------------------------------------- facture saisie
def saisir_facture(ctx: Contexte) -> Reponse:
    from .. import fournisseurs as fo
    from .pages_fournisseurs import _listes

    noms, _articles = _listes(ctx.racine)
    message = ""
    if ctx.req.methode == "POST":
        tiers, numero, jour = (ctx.req.champ(k).strip() for k in ("fournisseur", "numero", "date"))
        try:
            if not tiers:
                raise ValueError("Choisissez le fournisseur.")
            if not numero:
                raise ValueError("Le n° de facture du fournisseur est obligatoire.")
            date.fromisoformat(jour)
            nom = f"Saisie manuelle {tiers} {numero}"
            facture = fo.Facture(nom, hashlib.sha1(f"{nom}{datetime.now()}".encode()).hexdigest(), tiers, tiers, numero,
                                 jour, modele="Saisie manuelle")
            facture.etat = fo.A_VERIFIER
            with ctx.app.ecriture:
                registre = fo.Registre(ctx.racine)
                registre.factures.append(facture)
                registre.enregistrer()
                rang = len(registre.factures) - 1
            return redirection(f"/facture-fournisseur?i={rang}")
        except ValueError as erreur:
            message = _message(erreur=str(erreur))
    liste = "<datalist id='fournisseurs'>" + "".join(f"<option value='{e(n)}'>" for n in noms) + "</datalist>"
    corps = (message + f"<form method='post' class='carte'>{csrf(ctx)}<div class='ligne'><div><label>Fournisseur Sage"
             f"</label><input name='fournisseur' list='fournisseurs' size='30' required>{liste}</div><div><label>N° de "
             "facture du fournisseur</label><input name='numero' required></div><div><label>Date</label><input "
             f"type='date' name='date' value='{date.today()}' required></div></div><div class='boutons'><button>"
             "Continuer : saisir les lignes</button></div></form><p class='note'>La facture rejoint la liste des "
             "factures fournisseurs ; elle s'importe dans Sage (et Clover) une fois prête.</p>")
    return Reponse(corps=page(ctx, "Saisir une facture d'achat", corps))


# --------------------------------------------------------------------------------------------- bons de commande
def bons(ctx: Contexte) -> Reponse:
    from .. import bons_commande as bc
    from . import taches

    message = ""
    if ctx.req.methode == "POST":
        action = ctx.req.champ("action")
        if action == "Proposer":
            try:
                jours = max(7, min(28, int(ctx.req.champ("jours") or 14)))
            except ValueError:
                jours = 14

            def proposer(journal):
                journal("Lecture des ventes Clover, du stock et des derniers achats dans Sage…")
                propositions = bc.lire(ctx.racine, ctx.config, jours)
                ctx.app.memoire["propositions"] = (time.time(), propositions)
                a_commander = [p for p in propositions if p.permis]
                return [f"{len(a_commander)} article(s) à commander chez "
                        f"{len({p.fournisseur for p in a_commander})} fournisseur(s). Ouvrez « Bons de commande » > "
                        "« Voir la proposition »."]

            return taches.lancer(ctx, f"Proposition des commandes ({jours} jours)", proposer, "/bons-proposition")
    registre = bc.Registre(ctx.racine)
    lignes = [[f"<a href='/bon?n={e(b.numero)}'>{e(b.numero)}</a>", e(b.fournisseur), e(b.date), len(b.lignes),
               argent(b.total), e(b.etat), e(b.facture)]
              for b in sorted(registre.bons, key=lambda b: (b.date, b.numero), reverse=True)]
    corps = (message + f"<form method='post' class='ligne'>{csrf(ctx)}<div><label>Couvrir (jours de ventes)</label>"
             "<select name='jours'>" + "".join(f"<option{' selected' if j == 14 else ''}>{j}</option>"
                                                for j in (7, 14, 21, 28))
             + "</select></div><button name='action' value='Proposer'>Proposer les commandes…</button>"
               "<a class='ouvrir' href='/bons-proposition'>Voir la proposition</a></form>"
             + tableau(["N°", "Fournisseur", "Date", "Lignes", "Total", "État", "Facture"],
                       [[l[0], l[1], l[2], str(l[3]), l[4], l[5], l[6]] for l in lignes], {3, 4}))
    return Reponse(corps=page(ctx, "Bons de commande", corps))


def proposition(ctx: Contexte) -> Reponse:
    from .. import bons_commande as bc

    propositions = (ctx.app.memoire.get("propositions") or (0, []))[1]
    message = ""
    if ctx.req.methode == "POST" and propositions:
        choisis = set(ctx.req.champs("choix"))
        retenues = [p for k, p in enumerate(propositions) if str(k) in choisis and p.permis]
        if not retenues:
            message = _message(erreur="Cochez au moins un article à commander.")
        else:
            try:
                with ctx.app.ecriture:
                    crees = bc.creer_bons(ctx.racine, retenues)
                ctx.app.memoire.pop("propositions", None)
                return Reponse(corps=page(ctx, "Bons créés", _message(f"{len(crees)} bon(s) créé(s) : "
                                                                       + ", ".join(b.numero for b in crees))
                                          + "<p><a href='/bons-commande'>◀ Bons de commande</a></p>"))
            except RuntimeError as erreur:
                message = _message(erreur=str(erreur))
    if not propositions:
        return Reponse(corps=page(ctx, "Proposition des commandes", "<p>Aucune proposition : lancez « Proposer les "
                                                                     "commandes… » depuis la liste des bons.</p>"
                                                                     "<p><a href='/bons-commande'>◀ Bons de commande"
                                                                     "</a></p>"))
    rangees = []
    for k, p in enumerate(propositions):
        case = (f"<input type='checkbox' name='choix' value='{k}'{' checked' if p.cochee_par_defaut else ''}>"
                if p.permis else "")
        rangees.append([case, e(p.fournisseur), e(p.numero_sage), e(p.description), e(f"{p.stock:g}"),
                        e(f"{p.vendu:g}"), e(f"{p.quantite:g}"), argent(p.prix) if p.prix is not None else "",
                        argent(p.montant) if p.montant is not None else "", e(p.etat)])
    corps = (message + f"<form method='post'>{csrf(ctx)}"
             + tableau(["", "Fournisseur", "N° Sage", "Article", "Stock", "Vendu", "À commander", "Prix", "Montant",
                        "État"], rangees, {4, 5, 6, 7, 8})
             + "<div class='boutons'><button>Créer les bons (un par fournisseur)</button></div></form>"
               "<p class='note'>Quantité et prix en unités du fournisseur (dernier achat). Articles non reliés à Sage "
               "ou jamais achetés : visibles, non cochables.</p>")
    return Reponse(corps=page(ctx, "Proposition des commandes", corps))


def bon(ctx: Contexte) -> Reponse:
    from .. import bons_commande as bc

    registre = bc.Registre(ctx.racine)
    b = next((x for x in registre.bons if x.numero == (ctx.req.query.get("n") or ctx.req.champ("n"))), None)
    if b is None:
        return Reponse(404, page(ctx, "Bon de commande", "<p>Bon introuvable.</p>"))
    message, comparaison = "", ""
    factures = bc.factures_du_fournisseur(ctx.racine, b)
    if ctx.req.methode == "POST":
        action = ctx.req.champ("action")
        try:
            if action == "Supprimer":
                if not action_permise(ctx, "Supprimer"):
                    raise ValueError("Votre profil n'a pas le droit « Supprimer ».")
                with ctx.app.ecriture:
                    bc.supprimer_bon(ctx.racine, b.numero)
                return redirection("/bons-commande")
            if action == "Refaire le PDF":
                bc.refaire_pdf(ctx.racine, b.numero)
                message = _message("PDF refait.")
            f = next((x for x in factures if x.numero == ctx.req.champ("facture")), None)
            if action in ("Comparer", "Marquer reçu"):
                if f is None:
                    raise ValueError("Choisissez la facture du fournisseur.")
                lignes, conforme = bc.comparer(b, f)
                comparaison = sections_html([Section(f"{b.numero} contre la facture {f.numero}",
                                                     bc.ENTETES_COMPARAISON, lignes,
                                                     "Conforme." if conforme else "Écarts à vérifier.")])
                if action == "Marquer reçu":
                    with ctx.app.ecriture:
                        bc.noter_reception(ctx.racine, b.numero, f.numero, conforme)
                    message = _message(f"Bon marqué « {'Reçu' if conforme else 'Reçu avec écarts'} ».")
        except (ValueError, RuntimeError) as erreur:
            message = _message(erreur=str(erreur))
        b = next(x for x in bc.Registre(ctx.racine).bons if x.numero == b.numero)
    lignes = [[e(l.numero_sage), e(l.description), e(l.quantite), argent(Decimal(l.prix or 0)), e(l.facteur),
               argent(Decimal(l.montant or 0))] for l in b.lignes]
    options = "".join(f"<option>{e(f.numero)}</option>" for f in factures)
    corps = (message + f"<p><a href='/bons-commande'>◀ Bons de commande</a> · <a href='/bon-pdf?n={e(b.numero)}'>📄 PDF"
             f"</a></p><div class='carte'><p><strong>{e(b.numero)}</strong> · {e(b.fournisseur)} · {e(b.date)} · "
             f"<span class='etat'>{e(b.etat)}</span> {e(b.facture)}</p></div>"
             + tableau(["N° Sage", "Description", "Quantité", "Prix", "Facteur", "Montant"], lignes, {2, 3, 4, 5})
             + f"<p>Total : <strong>{argent(b.total)}</strong></p>"
             + (f"<form method='post' class='ligne'>{csrf(ctx)}<input type='hidden' name='n' value='{e(b.numero)}'>"
                f"<div><label>Facture du fournisseur</label><select name='facture'>{options}</select></div><button "
                "class='second' name='action' value='Comparer'>Comparer</button><button name='action' value='Marquer "
                "reçu'>Marquer reçu</button></form>" if factures else
                "<p class='note'>Aucune facture de ce fournisseur datée du bon ou après.</p>")
             + comparaison
             + f"<form method='post' class='boutons'>{csrf(ctx)}<input type='hidden' name='n' value='{e(b.numero)}'>"
               "<button class='second' name='action' value='Refaire le PDF'>Refaire le PDF</button>"
             + ("<button class='second' name='action' value='Supprimer'>Supprimer</button>" if b.etat == bc.CREE else "")
             + "</form>")
    return Reponse(corps=page(ctx, f"Bon de commande {b.numero}", corps))


def bon_pdf(ctx: Contexte) -> Reponse:
    from .. import bons_commande as bc

    b = next((x for x in bc.Registre(ctx.racine).bons if x.numero == ctx.req.query.get("n")), None)
    if b is None:
        return Reponse(404, page(ctx, "Bon de commande", "<p>Bon introuvable.</p>"))
    chemin = bc.refaire_pdf(ctx.racine, b.numero)
    return Reponse(corps=chemin.read_bytes(), type="application/pdf",
                   entetes={"Content-Disposition": f"inline; filename={b.numero}.pdf"})


# --------------------------------------------------------------------------------------------- retours
def retours(ctx: Contexte) -> Reponse:
    from .. import retours as rt
    from . import taches
    from .pages_fournisseurs import _listes

    noms, _articles = _listes(ctx.racine)
    message = ""
    valeurs = {k: ctx.req.champ(k).strip() for k in ("fournisseur", "facture", "jour", "motif")}
    lignes_proposees = []
    if ctx.req.methode == "POST":
        action = ctx.req.champ("action")
        try:
            if action == "Importer dans Sage":
                action_nom = "Importer un retour dans Sage"
                if not action_permise(ctx, action_nom):
                    raise ValueError(f"Votre profil n'a pas le droit « {action_nom} ».")
                numero = ctx.req.champ("numero")

                def importer(journal):
                    r = rt.importer(ctx.racine, ctx.config, numero, journal)
                    return [f"{r.numero} : {r.etat}"] + r.messages

                return taches.lancer(ctx, f"Import du retour {numero}", importer, "/retours", sage=True)
            if action == "Reprendre les lignes":
                lignes_proposees = rt.lignes_facture_origine(ctx.racine, valeurs["fournisseur"], valeurs["facture"])
                if not lignes_proposees:
                    message = _message(erreur="Facture d'origine introuvable dans les factures de l'application : "
                                              "saisissez les lignes.")
            if action == "Créer le retour":
                lignes = []
                for article, description, quantite, prix, taxe in zip(
                        ctx.req.champs("article"), ctx.req.champs("description"), ctx.req.champs("quantite"),
                        ctx.req.champs("prix"), ctx.req.champs("taxe")):
                    if article.strip() and quantite.strip():
                        lignes.append(rt.LigneRetour(article.strip(), description.strip(),
                                                     str(Decimal(quantite.replace(",", "."))),
                                                     str(Decimal(prix.replace(",", ".") or "0")), taxe))
                with ctx.app.ecriture:
                    r = rt.Registre(ctx.racine).ajouter(valeurs["fournisseur"], valeurs["facture"],
                                                        valeurs["jour"] or date.today().isoformat(), lignes,
                                                        valeurs["motif"], ctx.u.nom)
                message = _message(f"Retour {r.numero} créé : « Importer dans Sage » pour l'appliquer.")
                valeurs = {k: "" for k in valeurs}
        except (ValueError, InvalidOperation) as erreur:
            message = _message(erreur=str(erreur) or "Quantité ou prix invalide.")
    registre = rt.Registre(ctx.racine)
    lignes = []
    for r in sorted(registre.retours, key=lambda r: r.jour, reverse=True):
        bouton = (f"<form method='post'>{csrf(ctx)}<input type='hidden' name='numero' value='{e(r.numero)}'><button "
                  "name='action' value='Importer dans Sage'>Importer dans Sage</button></form>"
                  if r.etat != rt.IMPORTE else "")
        lignes.append([e(r.numero), e(r.fournisseur_sage), e(r.facture_origine), e(r.jour), len(r.lignes),
                       argent(-sum((l.montant for l in r.lignes), Decimal(0))), e(r.etat), bouton])
    liste = "<datalist id='fournisseurs'>" + "".join(f"<option value='{e(n)}'>" for n in noms) + "</datalist>"
    rangees = []
    for l in lignes_proposees + [rt.LigneRetour("", "", "", "")] * 4:
        rangees.append(f"<tr><td><input name='article' value='{e(l.numero_sage)}' size='12'></td><td><input "
                       f"name='description' value='{e(l.description)}' size='28'></td><td><input name='quantite' "
                       f"value='{e(l.quantite)}' size='6'></td><td><input name='prix' value='{e(l.prix)}' size='8'></td>"
                       f"<td><select name='taxe'>" + "".join(
                           f"<option value='{x}'{' selected' if x == l.taxe else ''}>{x or 'aucune'}</option>"
                           for x in ("", "GQ", "G", "Q")) + "</select></td></tr>")
    corps = (message + tableau(["N°", "Fournisseur", "Facture d'origine", "Date", "Lignes", "Montant", "État", ""],
                               [[l[0], l[1], l[2], l[3], str(l[4]), l[5], l[6], l[7]] for l in lignes], {4, 5})
             + f"<form method='post' class='carte'>{csrf(ctx)}<h2>Nouveau retour</h2><div class='ligne'><div><label>"
               f"Fournisseur Sage</label><input name='fournisseur' list='fournisseurs' value='{e(valeurs['fournisseur'])}' "
               f"size='28' required>{liste}</div><div><label>Facture d'origine</label><input name='facture' "
               f"value='{e(valeurs['facture'])}' required></div><div><label>Date</label><input type='date' name='jour' "
               f"value='{e(valeurs['jour'] or date.today().isoformat())}'></div><div><label>Motif</label><input "
               f"name='motif' value='{e(valeurs['motif'])}'></div><button class='second' name='action' "
               "value='Reprendre les lignes' formnovalidate>Reprendre les lignes de la facture</button></div>"
               "<div class='defile'><table><tr><th>N° Sage</th><th>Description</th><th>Qté Sage</th><th>Prix Sage</th>"
               f"<th>Taxes</th></tr>{''.join(rangees)}</table></div><div class='boutons'><button name='action' "
               "value='Créer le retour'>Créer le retour</button></div></form>"
               "<p class='note'>Le retour est une facture d'achat aux quantités et montants négatifs ; à l'import, "
               "le stock Clover des articles reliés diminue aussi.</p>")
    return Reponse(corps=page(ctx, "Retours fournisseurs", corps))


FONCTIONS = [
    Fonction("/saisir-facture-achat", "Saisir une facture d'achat", "fournisseurs", saisir_facture, "✍",
             "Fournisseur", menu=False),
    Fonction("/bons-commande", "Bons de commande", "fournisseurs", bons, "🛍", "Fournisseur", menu=False),
    Fonction("/bons-proposition", "Bons de commande", "fournisseurs", proposition, "🛍", "Fournisseur", menu=False),
    Fonction("/bon", "Bons de commande", "fournisseurs", bon, "🛍", "Fournisseur", menu=False),
    Fonction("/bon-pdf", "Bons de commande", "fournisseurs", bon_pdf, "🛍", "Fournisseur", menu=False),
    Fonction("/retours", "Retours fournisseurs", "fournisseurs", retours, "↩", "Fournisseur", menu=False),
]
WEB = {"Saisir une facture d'achat": "/saisir-facture-achat", "Bons de commande": "/bons-commande",
       "Retours fournisseurs": "/retours"}
