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
    """fenetre_gestion.saisir_facture_achat (SaisieDocument) : Fournisseur *, Date, N° de facture du fournisseur * ;
    Article, Quantité, Prix d'achat, Taxes, « ➕ Ajouter la ligne », « ✖ Retirer la ligne » ; tableau des lignes ;
    « n ligne(s) — total », « ✔ Ajouter aux factures fournisseurs », « ✖ Fermer »."""
    from .. import fournisseurs as fo
    from .. import taxes as tx
    from .consultations import Section, tableau_section
    from .pages_fournisseurs import _listes

    noms, articles = _listes(ctx.racine)
    descriptions = {a.numero: a.description for a in articles}
    message = ""
    v = {k: ctx.req.champ(k).strip() for k in ("fournisseur", "numero", "date")}
    v["date"] = v["date"] or date.today().isoformat()
    lignes = [(a_, d_, q_, p_, t_) for a_, d_, q_, p_, t_ in zip(
        ctx.req.champs("l_article"), ctx.req.champs("l_description"), ctx.req.champs("l_quantite"),
        ctx.req.champs("l_prix"), ctx.req.champs("l_taxe"))]
    if ctx.req.methode == "POST":
        action = ctx.req.champ("action")
        try:
            if action == "Ajouter la ligne":
                article = ctx.req.champ("article").strip().split("  ")[0].strip()
                quantite = Decimal((ctx.req.champ("quantite") or "1").replace(",", "."))
                prix = Decimal((ctx.req.champ("prix") or "0").replace(",", ".").replace("$", "").strip() or "0")
                if not article:
                    raise ValueError("Choisissez l'article.")
                if quantite <= 0:
                    raise ValueError("Quantité positive.")
                lignes.append((article, descriptions.get(article, article), str(quantite), str(prix),
                               ctx.req.champ("taxe")))
            elif action == "Retirer la ligne":
                k = ctx.req.champ("k")
                if not k.isdigit() or int(k) >= len(lignes):
                    raise ValueError("Choisissez une ligne.")
                del lignes[int(k)]
            elif action == "Ajouter aux factures fournisseurs":
                if not v["fournisseur"]:
                    raise ValueError("Choisissez le fournisseur.")
                if not v["numero"]:
                    raise ValueError("Le n° de facture du fournisseur est obligatoire.")
                if not lignes:
                    raise ValueError("Ajoutez au moins une ligne.")
                date.fromisoformat(v["date"])
                lignes_f = [fo.Ligne(d_, Decimal(q_), Decimal(p_), (Decimal(q_) * Decimal(p_)).quantize(Decimal("0.01")),
                                     numero_sage=a_, description_sage=d_, taxable=bool(t_), confirme=True, taxe=t_)
                            for a_, d_, q_, p_, t_ in lignes]
                sous_total = sum((l.montant for l in lignes_f), Decimal(0))
                montants = [tx.montants(l.montant, tx.code(l)) for l in lignes_f]
                tps = sum((m[0] for m in montants), Decimal(0))
                tvq = sum((m[1] for m in montants), Decimal(0))
                nom = f"Saisie manuelle {v['fournisseur']} {v['numero']}"
                facture = fo.Facture(nom, hashlib.sha1(f"{nom}{datetime.now()}".encode()).hexdigest(), v["fournisseur"],
                                     v["fournisseur"], v["numero"], v["date"], lignes_f, sous_total, tps, tvq,
                                     sous_total + tps + tvq, "Saisie manuelle")
                facture.etat = fo.etat_apres_controle(facture, facture.controles())
                with ctx.app.ecriture:
                    registre = fo.Registre(ctx.racine)
                    registre.factures.append(facture)
                    registre.enregistrer()
                    rang = len(registre.factures) - 1
                return redirection(f"/factures-fournisseurs?i={rang}")
        except (ValueError, InvalidOperation) as erreur:
            message = _message(erreur=str(erreur) or "Nombre invalide.")
    liste_f = "<datalist id='fournisseurs'>" + "".join(f"<option value='{e(n)}'>" for n in noms) + "</datalist>"
    liste_a = "<datalist id='articles-sage'>" + "".join(
        f"<option value='{e(a.numero)}  {e(a.description)}'>" for a in articles[:4000]) + "</datalist>"
    caches, rangees, total = "", [], Decimal(0)
    for k, (a_, d_, q_, p_, t_) in enumerate(lignes):
        caches += "".join(f"<input type='hidden' name='l_{n}' value='{e(x)}'>" for n, x in (
            ("article", a_), ("description", d_), ("quantite", q_), ("prix", p_), ("taxe", t_)))
        montant = (Decimal(q_) * Decimal(p_)).quantize(Decimal("0.01"))
        total += montant
        rangees.append([f"<input type='radio' name='k' value='{k}'>", e(a_), e(d_), e(q_), argent(Decimal(p_)),
                        argent(montant), e(tx.CHOIX.get(t_, t_))])
    taxes = "".join(f"<option value='{e(x)}'>{e(n)}</option>" for x, n in tx.CHOIX.items())
    corps = (message + f"<form method='post'>{csrf(ctx)}{caches}<div class='barre-onglet'><div><label>Fournisseur *"
             f"</label><input name='fournisseur' list='fournisseurs' value='{e(v['fournisseur'])}' size='26'>{liste_f}"
             f"</div><div><label>Date</label><input type='date' name='date' value='{e(v['date'])}'></div><div><label>"
             f"N° de facture du fournisseur *</label><input name='numero' value='{e(v['numero'])}' size='22'></div>"
             "</div><div class='barre-onglet'><div><label>Article</label><input name='article' list='articles-sage' "
             f"size='34'>{liste_a}</div><div><label>Quantité</label><input name='quantite' value='1' size='6'></div>"
             "<div><label>Prix d'achat</label><input name='prix' size='9'></div><div><label>Taxes</label><select "
             f"name='taxe'>{taxes}</select></div></div><div class='barre-onglet'><button name='action' value='Ajouter "
             "la ligne'>➕ Ajouter la ligne</button><button class='second' name='action' value='Retirer la ligne'>✖ "
             "Retirer la ligne</button></div>"
             + tableau_section(Section("Lignes", ["", "N° Sage", "Description", "Quantité", "Prix d'achat", "Montant",
                                                  "Taxes"], rangees, html=set(range(7))))
             + f"<div class='barre-onglet'><strong>{len(lignes)} ligne(s) — total {argent(total)}</strong><button "
               "name='action' value='Ajouter aux factures fournisseurs'>✔ Ajouter aux factures fournisseurs</button>"
               "<a class='ouvrir' href='/factures-fournisseurs'>✖ Fermer</a></div></form>")
    return Reponse(corps=page(ctx, "Saisir une facture d'achat", corps))


# --------------------------------------------------------------------------------------------- bons de commande
def bons(ctx: Contexte) -> Reponse:
    """Comme fenetre_bons_commande.FenetreBons : « 🔄 Actualiser », « 📂 Ouvrir » (PDF), « ➕ Ajouter », « ✎ Modifier »,
    « 🗑 Supprimer », « 🧮 Proposer les commandes… », « 🔁 Refaire le PDF », « ⚖ Comparer avec la facture »,
    « 🔀 Transformer… » ; liste des bons ; « Comparaison avec la facture » et « ✔ Marquer reçu »."""
    from .. import bons_commande as bc
    from .. import documents as dc
    from .consultations import Section, tableau_section
    from . import taches

    choisi = ctx.req.champ("bon") or ctx.req.query.get("bon", "")
    op = ctx.req.champ("op") or ctx.req.query.get("op", "")
    message, bas = "", ""
    registre = bc.Registre(ctx.racine)
    b = next((x for x in registre.bons if x.numero == choisi), None)
    action = ctx.req.champ("action") if ctx.req.methode == "POST" else ""
    if action:
        try:
            if action == "Proposer":
                from .serveur import redirection

                return redirection(f"/bons-proposition?jours={int(ctx.req.champ('jours') or 14)}&actualiser=1")
            if action in ("Créer le bon de commande", "Enregistrer le bon"):
                message = _enregistrer_bon(ctx, b if action == "Enregistrer le bon" else None)
                op = ""
            elif b is None:
                raise ValueError("Choisissez un bon dans la liste.")
            elif action == "Supprimer":
                if not action_permise(ctx, "Supprimer"):
                    raise ValueError("Votre profil n'a pas le droit « Supprimer ».")
                with ctx.app.ecriture:
                    bc.supprimer_bon(ctx.racine, b.numero)
                message, b = _message(f"{choisi} supprimé."), None
            elif action == "Refaire le PDF":
                bc.refaire_pdf(ctx.racine, b.numero)
                message = _message("✔ PDF refait.")
            elif action == "Transformer":
                from ..chaine_documents import transformer_achat

                cree = transformer_achat(ctx.racine, ("bc", b.numero), ctx.req.champ("cible"), ctx.req.champ("jour"),
                                         ctx.u.nom, ctx.req.champ("numero_facture").strip())
                message, op = _message(f"{cree} créé à partir de {b.numero}."), ""
            elif action == "Marquer reçu":
                f = next((x for x in bc.factures_du_fournisseur(ctx.racine, b)
                          if x.numero == ctx.req.champ("facture")), None)
                if f is None:
                    raise ValueError("Choisissez la facture du fournisseur.")
                _lignes, conforme = bc.comparer(b, f)
                with ctx.app.ecriture:
                    bc.noter_reception(ctx.racine, b.numero, f.numero, conforme)
                message = _message(f"Bon marqué « {'Reçu' if conforme else 'Reçu avec écarts'} ».")
        except (ValueError, RuntimeError, InvalidOperation) as erreur:
            message = _message(erreur=str(erreur) or "Nombre invalide.")
        registre = bc.Registre(ctx.racine)
        b = next((x for x in registre.bons if x.numero == choisi), None)
    if op == "ouvrir" and b is not None:  # « 📂 Ouvrir » : le PDF du bon
        chemin = bc.refaire_pdf(ctx.racine, b.numero)
        return Reponse(corps=chemin.read_bytes(), type="application/pdf",
                       entetes={"Content-Disposition": f"inline; filename={b.numero}.pdf"})
    if op in ("modifier", "comparer", "transformer", "ouvrir") and b is None:
        bas = "<p class='erreur-texte'>Choisissez un bon dans la liste.</p>"
    elif op == "ajouter" or (op == "modifier" and b is not None):
        if op == "modifier" and b.etat != bc.CREE:
            bas = f"<p class='erreur-texte'>{e(b.numero)} ({e(b.etat)}) ne peut plus être modifié.</p>"
        else:
            bas = _saisie_bon(ctx, b if op == "modifier" else None)
    elif op == "comparer" and b is not None:
        factures = bc.factures_du_fournisseur(ctx.racine, b)
        facture = next((x for x in factures if x.numero == ctx.req.query.get("facture")), factures[0] if factures else None)
        lignes_c, conforme = bc.comparer(b, facture) if facture else ([], False)
        options = "".join(f"<option{' selected' if facture and x.numero == facture.numero else ''}>{e(x.numero)}"
                          "</option>" for x in factures)
        bas = (f"<form method='get' class='barre-onglet'><input type='hidden' name='bon' value='{e(b.numero)}'><input "
               f"type='hidden' name='op' value='comparer'><div><label>Facture du fournisseur</label><select "
               f"name='facture'>{options}</select></div><button class='second'>⚖ Comparer</button></form>"
               + tableau_section(Section("Comparaison avec la facture", bc.ENTETES_COMPARAISON, lignes_c,
                                         ("Conforme." if conforme else "Écarts à vérifier.") if facture else
                                         "Aucune facture de ce fournisseur datée du bon ou après.",
                                         classes=["etat-ecart" if l and str(l[-1]).startswith("⚠") else ""
                                                  for l in lignes_c]))
               + (f"<form method='post' class='barre-onglet'>{csrf(ctx)}<input type='hidden' name='bon' "
                  f"value='{e(b.numero)}'><input type='hidden' name='facture' value='{e(facture.numero)}'><button "
                  "name='action' value='Marquer reçu'>✔ Marquer reçu</button></form>" if facture else ""))
    elif op == "transformer" and b is not None:
        cibles = "".join(f"<option value='{c}'>{e(dc.libelle(c))}</option>"
                         for c in dc.TRANSFORMATIONS[dc.COMMANDE_ACHAT])
        bas = (f"<form method='post' class='carte'>{csrf(ctx)}<input type='hidden' name='bon' value='{e(b.numero)}'>"
               f"<h2>Transformation de {e(b.numero)}</h2><div class='ligne'><div><label>Vers quel type ?</label><select "
               f"name='cible'>{cibles}</select></div><div><label>Date</label><input type='date' name='jour' "
               f"value='{date.today()}'></div><div><label>N° de facture du fournisseur</label><input "
               "name='numero_facture' size='16'></div><button name='action' value='Transformer'>🔀 Transformer</button>"
               "</div></form>")
    bons_ = sorted(registre.bons, key=lambda x: x.numero, reverse=True)
    lignes = [[f"<input type='radio' name='bon' value='{e(x.numero)}'{' checked' if x.numero == choisi else ''}>",
               e(x.numero), e(x.date), e(x.fournisseur), str(len(x.lignes)), argent(x.total), e(x.etat), e(x.facture)]
              for x in bons_]
    jours = "".join(f"<option{' selected' if j_ == 14 else ''}>{j_}</option>" for j_ in (7, 14, 21, 28))
    corps = (message + f"<form method='post'>{csrf(ctx)}<div class='barre-onglet'><a class='ouvrir' href='/bons-commande'>🔄 "
             "Actualiser</a><button class='second' name='op' value='ouvrir' formtarget='_blank'>📂 Ouvrir</button>"
             "<button class='second' name='op' value='ajouter'>➕ Ajouter</button><button class='second' name='op' "
             "value='modifier'>✎ Modifier</button><button class='danger' name='action' "
             "value='Supprimer'>🗑 Supprimer</button><button class='second' name='action' "
             "value='Refaire le PDF'>🔁 Refaire le PDF</button><button class='second' name='op' value='comparer'>⚖ "
             "Comparer avec la facture</button><button class='second' name='op' value='transformer'>🔀 Transformer…"
             "</button></div>"
             f"<p class='note'>{len(bons_)} bon(s). « Comparer avec la facture » : la facture du même fournisseur reçue "
             "depuis le bon (factures fournisseurs) est comparée au bon.</p>"
             + tableau_section(Section("Bons de commande", ["", "N°", "Date", "Fournisseur", "Articles", "Total", "État",
                                                           "Facture"], lignes, html=set(range(8))))
             + "</form>"
             + f"<form method='post' class='barre-onglet'>{csrf(ctx)}<div><label>Couvrir (jours de ventes)</label><select "
               f"name='jours'>{jours}</select></div><button name='action' value='Proposer'>🧮 Proposer les commandes…"
               "</button></form>" + bas)
    return Reponse(corps=page(ctx, "Bons de commande", corps))


def _saisie_bon(ctx: Contexte, b) -> str:
    """Saisie d'un bon (fenetre_gestion.saisir_bon_commande) : fournisseur, date, lignes en unités du fournisseur."""
    from .pages_fournisseurs import _listes

    noms, articles = _listes(ctx.racine)
    lignes = list(b.lignes) if b else []
    rangees = ""
    for k in range(max(len(lignes) + 3, 6)):
        l = lignes[k] if k < len(lignes) else None
        rangees += (f"<tr><td><input name='l_numero' list='articles-sage' value='{e(l.numero_sage if l else '')}' "
                    f"size='14'></td><td><input name='l_description' value='{e(l.description if l else '')}' size='30'>"
                    f"</td><td><input name='l_quantite' value='{e(l.quantite if l else '')}' size='6'></td><td><input "
                    f"name='l_prix' value='{e(l.prix if l else '')}' size='8'></td><td><input name='l_facteur' "
                    f"value='{e(l.facteur if l else '1')}' size='5'></td></tr>")
    liste_f = "<datalist id='fournisseurs'>" + "".join(f"<option value='{e(n)}'>" for n in noms) + "</datalist>"
    liste_a = "<datalist id='articles-sage'>" + "".join(f"<option value='{e(a.numero)}'>{e(a.description)}</option>"
                                                        for a in articles) + "</datalist>"
    return (f"<form method='post' class='carte'>{csrf(ctx)}<input type='hidden' name='bon' value='{e(b.numero if b else '')}'>"
            f"<h2>{'Modifier ' + e(b.numero) if b else 'Saisir une commande fournisseur'}</h2><div class='ligne'><div>"
            f"<label>Fournisseur *</label><input name='fournisseur' list='fournisseurs' value='{e(b.fournisseur if b else '')}' "
            f"size='34'>{liste_f}</div><div><label>Date</label><input type='date' name='jour' "
            f"value='{e(b.date if b else date.today().isoformat())}'></div></div>{liste_a}<div class='defile'><table><tr>"
            "<th>N° Sage</th><th>Description</th><th>Quantité</th><th>Prix d'achat</th><th>Facteur</th></tr>"
            f"{rangees}</table></div><div class='barre-onglet'><button name='action' value='"
            + ("Enregistrer le bon'>💾 Enregistrer" if b else "Créer le bon de commande'>➕ Créer le bon de commande")
            + "</button></div><p class='note'>Quantité et prix en unités du fournisseur ; facteur = unités Sage par "
              "unité du fournisseur.</p></form>")


def _enregistrer_bon(ctx: Contexte, b) -> str:
    from .. import bons_commande as bc
    from .pages_fournisseurs import _listes

    _noms, articles = _listes(ctx.racine)
    descriptions = {a.numero: a.description for a in articles}
    fournisseur, jour = ctx.req.champ("fournisseur").strip(), ctx.req.champ("jour").strip() or date.today().isoformat()
    if not fournisseur:
        raise ValueError("Choisissez le fournisseur.")
    lignes = []
    for n, d, q, pr, f in zip(ctx.req.champs("l_numero"), ctx.req.champs("l_description"), ctx.req.champs("l_quantite"),
                              ctx.req.champs("l_prix"), ctx.req.champs("l_facteur")):
        n = n.strip().split(" ")[0]
        if not n or not q.strip():
            continue
        quantite = Decimal(q.replace(",", "."))
        prix = Decimal((pr or "0").replace(",", ".").replace("$", "").strip() or "0")
        facteur = Decimal((f or "1").replace(",", ".") or "1")
        lignes.append((n, d.strip() or descriptions.get(n, ""), quantite, prix, facteur))
    if not lignes:
        raise ValueError("Ajoutez au moins une ligne (n° Sage et quantité).")
    with ctx.app.ecriture:
        if b is not None:
            modifie = bc.modifier_bon(ctx.racine, b.numero, fournisseur, jour, [
                bc.LigneBon(n, d, str(q), str(pr), str((q * pr).quantize(Decimal("0.01"))), str(f))
                for n, d, q, pr, f in lignes])
            return _message(f"✔ {modifie.numero} enregistré.")
        propositions = [bc.Proposition(n, d, "", Decimal(0), Decimal(0), q, fournisseur, pr, facteur=f)
                        for n, d, q, pr, f in lignes]
        crees = bc.creer_bons(ctx.racine, propositions, date.fromisoformat(jour))
    return _message(f"✔ Bon {crees[0].numero} créé pour {fournisseur}.")


def proposition(ctx: Contexte) -> Reponse:
    """Comme fenetre_bons_commande.ouvrir (FenetreACocher + « Couvrir … jours de ventes ») : articles à commander
    regroupés par article Sage, fournisseur et prix du dernier achat ; « Créer les bons de commande » (un bon par
    fournisseur, en PDF)."""
    from .. import bons_commande as bc
    from ..fenetre_bons_commande import HORIZONS
    from .a_cocher import choisies, page_a_cocher
    from . import taches

    try:
        jours = int(ctx.req.query.get("jours") or ctx.req.champ("jours") or 14)
    except ValueError:
        jours = 14
    jours = jours if jours in HORIZONS else 14
    gardee = ctx.app.memoire.get("propositions")
    if not gardee or gardee[2] != jours or ctx.req.query.get("actualiser"):
        def lire(journal):  # ventes Clover, stock et derniers achats : quelques secondes
            journal("Lecture des ventes Clover, du stock et des derniers achats dans Sage…")
            ctx.app.memoire["propositions"] = (time.time(), bc.lire(ctx.racine, ctx.config, jours), jours)
            return ["Proposition prête."]

        return taches.lancer(ctx, f"Proposition des commandes ({jours} jours)", lire, f"/bons-proposition?jours={jours}")
    lignes = gardee[1]
    if ctx.req.methode == "POST" and ctx.req.champ("action") == "lancer":
        retenues = choisies(ctx, lignes)
        if not retenues:
            return Reponse(corps=page(ctx, "Bons de commande", _message(erreur="Cochez au moins une ligne.")))
        try:
            with ctx.app.ecriture:
                bons_ = bc.creer_bons(ctx.racine, retenues)
        except RuntimeError as erreur:
            return Reponse(corps=page(ctx, "Bons de commande", _message(erreur=str(erreur))))
        ctx.app.memoire.pop("propositions", None)
        texte = (f"{len(bons_)} bon(s) de commande créé(s) : "
                 + ", ".join(f"{b.numero} {b.fournisseur} ({argent(b.total)})" for b in bons_))
        return Reponse(corps=page(ctx, "Bons de commande", _message(texte)
                                  + "<p><a class='ouvrir' href='/bons-commande'>◀ Bons de commande</a> (« 📂 Ouvrir » "
                                    "donne le PDF à envoyer au fournisseur)</p>"))
    a_commander = [x for x in lignes if x.permis]
    total = sum((x.montant or 0 for x in a_commander), 0)

    def nombre(v):
        return "" if v is None else f"{v:f}".replace(".", ",")

    resume = (f"{len(a_commander)} article(s) à commander chez {len({x.fournisseur for x in a_commander})} "
              f"fournisseur(s), {argent(total)} au dernier prix d'achat — règle : stock Clover − ventes des {jours} "
              f"derniers jours <= 0 ; quantité = de quoi couvrir {jours} jours. Fournisseur et prix : dernier achat dans "
              "Sage.")
    options = "".join(f"<option{' selected' if h == jours else ''}>{h}</option>" for h in HORIZONS)
    corps = page_a_cocher(
        ctx, "/bons-proposition",
        "Articles à commander (règle des prévisions), regroupés par article Sage, avec le fournisseur et le prix du "
        "dernier achat dans Sage. Cochez les lignes : un bon par fournisseur est créé en PDF (rien n'est envoyé sans "
        "vous).",
        ["Fournisseur", "N° Sage", "Article Sage", "Articles Clover", "Stock", "Vendu", "À commander", "Prix",
         "Montant", "Dernier achat", "État"], lignes,
        lambda x: (x.fournisseur, x.numero_sage, x.description, x.articles_clover, nombre(x.stock), nombre(x.vendu),
                   nombre(x.quantite), argent(x.prix) if x.prix is not None else "",
                   argent(x.montant) if x.montant is not None else "", x.dernier_achat, x.etat),
        resume, "Créer les bons de commande",
        f"<div><label>Couvrir</label><select name='jours'>{options}</select> jours de ventes</div>", {"jours": jours})
    return Reponse(corps=page(ctx, "Bons de commande", corps))


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

    from .pages_compta import _point_vente

    noms, _articles = _listes(ctx.racine)
    _pv, choix_pv, code_pv = _point_vente(ctx)
    message = ""
    valeurs = {k: ctx.req.champ(k).strip() for k in ("fournisseur", "facture", "jour", "motif")}
    lignes_proposees = []
    if ctx.req.methode == "POST":  # lignes déjà saisies (champs cachés, comme le tableau de la fenêtre Windows)
        lignes_proposees = [rt.LigneRetour(a_.strip(), d_.strip(), q_.strip(), p_.strip(), t_)
                            for a_, d_, q_, p_, t_ in zip(ctx.req.champs("l_article"), ctx.req.champs("l_description"),
                                                          ctx.req.champs("l_quantite"), ctx.req.champs("l_prix"),
                                                          ctx.req.champs("l_taxe"))]
    if ctx.req.methode == "POST":
        action = ctx.req.champ("action")
        try:
            if action == "Ajouter la ligne":
                article, quantite = ctx.req.champ("article").strip(), ctx.req.champ("quantite").strip()
                if not article or not quantite:
                    raise ValueError("N° Sage et quantité obligatoires.")
                if Decimal(quantite.replace(",", ".")) <= 0:
                    raise ValueError("Quantité positive (unités Sage).")
                Decimal((ctx.req.champ("prix") or "0").replace(",", "."))
                lignes_proposees.append(rt.LigneRetour(article, ctx.req.champ("description").strip(), quantite,
                                                       ctx.req.champ("prix").strip() or "0", ctx.req.champ("taxe")))
            elif action == "Retirer la ligne":
                k = ctx.req.champ("k")
                if not k.isdigit() or int(k) >= len(lignes_proposees):
                    raise ValueError("Choisissez une ligne.")
                del lignes_proposees[int(k)]
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
                for l_ in lignes_proposees:
                    lignes.append(rt.LigneRetour(l_.numero_sage, l_.description,
                                                 str(Decimal(str(l_.quantite).replace(",", "."))),
                                                 str(Decimal(str(l_.prix).replace(",", ".") or "0")), l_.taxe))
                if not lignes:
                    raise ValueError("Ajoutez au moins une ligne.")
                with ctx.app.ecriture:
                    r = rt.Registre(ctx.racine).ajouter(valeurs["fournisseur"], valeurs["facture"],
                                                        valeurs["jour"] or date.today().isoformat(), lignes,
                                                        valeurs["motif"], ctx.u.nom,
                                                        str(code_pv))  # comme FenetreRetours (choix_pv.courant.code)
                message = _message(f"Retour {r.numero} créé : « Importer dans Sage » pour l'appliquer.")
                valeurs = {k: "" for k in valeurs}
                lignes_proposees = []
        except (ValueError, InvalidOperation) as erreur:
            message = _message(erreur=str(erreur) or "Quantité ou prix invalide.")
    from .consultations import Section, tableau_section

    registre = rt.Registre(ctx.racine)
    lignes = [[f"<input type='radio' name='numero' value='{e(r.numero)}'>", e(r.jour), e(r.numero),
               e(r.fournisseur_sage), e(r.facture_origine), str(len(r.lignes)),
               argent(sum((l.montant for l in r.lignes), Decimal(0))), e(r.etat), e(" ; ".join(r.messages))]
              for r in sorted(registre.retours, key=lambda r: r.cree, reverse=True)]
    classes = ["termine" if r.etat == rt.IMPORTE else "" for r in sorted(registre.retours, key=lambda r: r.cree,
                                                                           reverse=True)]
    liste = "<datalist id='fournisseurs'>" + "".join(f"<option value='{e(n)}'>" for n in noms) + "</datalist>"
    from ..taxes import CHOIX

    caches, rangees = "", []
    for k, l in enumerate(lignes_proposees):
        caches += "".join(f"<input type='hidden' name='l_{n}' value='{e(str(v))}'>" for n, v in (
            ("article", l.numero_sage), ("description", l.description), ("quantite", l.quantite), ("prix", l.prix),
            ("taxe", l.taxe)))
        rangees.append([f"<input type='radio' name='k' value='{k}'>", e(l.numero_sage), e(l.description),
                        e(str(l.quantite)), e(str(l.prix)), e(CHOIX.get(l.taxe, l.taxe))])
    taxes = "".join(f"<option value='{e(x)}'>{e(v)}</option>" for x, v in CHOIX.items())
    corps = (message + f"<form method='post'>{csrf(ctx)}{caches}<div class='barre-onglet'>{choix_pv}<div><label>Fournisseur Sage *"
             f"</label><input name='fournisseur' list='fournisseurs' value='{e(valeurs['fournisseur'])}' size='24'>"
             f"{liste}</div><div><label>N° de la facture d'origine *</label><input name='facture' "
             f"value='{e(valeurs['facture'])}' size='14'></div><div><label>Motif</label><input name='motif' "
             f"value='{e(valeurs['motif'])}' size='20'></div><div><label>Date</label><input type='date' name='jour' "
             f"value='{e(valeurs['jour'] or date.today().isoformat())}'></div><button class='second' name='action' "
             "value='Reprendre les lignes'>📥 Reprendre les lignes de la facture</button></div>"
             "<div class='barre-onglet'><div><label>N° Sage</label><input name='article' size='12'></div><div><label>"
             "Description</label><input name='description' size='26'></div><div><label>Quantité (unités Sage)</label>"
             "<input name='quantite' size='8'></div><div><label>Prix Sage</label><input name='prix' size='9'></div>"
             f"<div><label>Taxes</label><select name='taxe'>{taxes}</select></div><button name='action' "
             "value='Ajouter la ligne'>➕ Ajouter la ligne</button><button class='second' name='action' "
             "value='Retirer la ligne'>✖ Retirer la ligne</button></div>"
             + tableau_section(Section("Lignes du retour", ["", "N° Sage", "Description", "Quantité", "Prix Sage",
                                                           "Taxes"], rangees, html=set(range(6))))
             + "<div class='barre-onglet'><button name='action' value='Créer le retour'>✔ Enregistrer le retour"
               "</button></div></form>"
             + f"<form method='post'>{csrf(ctx)}<div class='barre-onglet'><button class='second' name='action' "
               "value='Importer dans Sage'>📤 Importer le retour choisi dans Sage</button></div>"
               "<div class='ligne-etat'>Le retour est importé dans Sage comme une facture d'achat négative (« R-n° de "
               "facture ») ; le stock Clover des articles reliés diminue.</div>"
             + tableau_section(Section("Retours", ["", "Date", "N°", "Fournisseur", "Facture d'origine", "Lignes",
                                                  "Montant", "État", "Messages"], lignes, classes=classes,
                                       html=set(range(9))))
             + "</form>")
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
