"""5e vague de l'application web (suite) : documents saisis dans l'application (registre documents.py, comme
fenetre_chaine / fenetre_saisie) : devis, commandes, livraisons, factures de vente et de retour, documents d'achat
de l'application, documents de stock. Liste par côté, fiche (lignes, totaux, chaîne), saisie et modification,
transformer, facturer une commande, importer une facture dans Sage, passer un document de stock dans Sage et Clover,
supprimer, PDF.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation

from .pages import Contexte, Fonction, argent, csrf, page, permis, tableau
from .pages_compta import _message, action_permise
from .serveur import Reponse, echapper as e

LIGNES_SAISIE = 12
# côté -> (titres d'entrée du menu qui donnent accès, page de chacun)
ACCES = {"vente": [("Saisir une facture de vente", "encaissements"), ("Commandes clients", "encaissements"),
                   ("Liste des documents de vente", "encaissements")],
         "achat": [("Liste des documents d'achat", "fournisseurs"), ("Saisir une facture d'achat", "fournisseurs")],
         "stock": [("Saisir un document de stock", "correspondance"), ("Liste des documents de stock",
                                                                        "correspondance")]}
TAXES = ("GQ", "G", "Q", "")


def _permis(ctx: Contexte, cote: str) -> bool:
    return any(permis(ctx.reg, ctx.u, Fonction("", t, p, None, "", "")) for t, p in ACCES.get(cote, []))


def _refus(ctx: Contexte) -> Reponse:
    return Reponse(403, page(ctx, "Accès refusé", "<p>Votre profil n'a pas accès à ces documents.</p>"))


def _types(cote: str) -> list[str]:
    from .. import documents as dc

    if cote == "vente":
        return dc.TYPES_VENTE
    if cote == "achat":  # bons de commande, factures et retours d'achat : leurs registres (rubrique Fournisseur)
        return [g for g in dc.TYPES_ACHAT if g not in (dc.COMMANDE_ACHAT, dc.FACTURE_ACHAT, dc.FACTURE_RETOUR_ACHAT)]
    return [dc.STOCK]


def documents(ctx: Contexte) -> Reponse:
    from .. import documents as dc

    cote = ctx.req.query.get("cote", "vente")
    if not _permis(ctx, cote):
        return _refus(ctx)
    genre = ctx.req.query.get("genre", "")
    registre = dc.Registre(ctx.racine)
    docs = [d for d in registre.documents if dc.cote(d.genre) == cote and (not genre or d.genre == genre)]
    lignes = [[f"<a href='/document?n={e(d.numero)}'>{e(d.numero)}</a>", e(dc.libelle(d.genre)), e(d.date),
               e(d.tiers or d.sens), e(d.depot or "Emplacement par défaut"), argent(d.total), e(d.etat),
               e(d.lien or d.origine)] for d in sorted(docs, key=lambda d: (d.date, d.numero), reverse=True)]
    options = "".join(f"<option value='{g}'>{e(dc.libelle(g))}</option>" for g in _types(cote))
    titre = {"vente": "Documents de vente saisis", "achat": "Documents d'achat saisis",
             "stock": "Documents de stock saisis"}[cote]
    if genre:
        titre = dc.libelle(genre) + ("s" if not dc.libelle(genre).endswith("s") else "")
    corps = (f"<form class='ligne' method='get' action='/document/saisie'><div><label>Nouveau document</label><select "
             f"name='genre'>{options}</select></div><button>Ajouter</button></form>"
             + tableau(["N°", "Type", "Date", "Client / fournisseur", "Dépôt", "Total", "État", "Lien"], lignes, {5})
             + "<p class='note'>Documents saisis dans l'application ; ceux de Sage : listes des documents de la "
               "rubrique.</p>")
    return Reponse(corps=page(ctx, titre, corps))


def document(ctx: Contexte) -> Reponse:
    from .. import documents as dc
    from . import taches

    registre = dc.Registre(ctx.racine)
    numero = ctx.req.query.get("n") or ctx.req.champ("n")
    try:
        doc = registre.document(numero)
    except (StopIteration, KeyError, ValueError):
        return Reponse(404, page(ctx, "Document", "<p>Document introuvable.</p>"))
    cote = dc.cote(doc.genre)
    if not _permis(ctx, cote):
        return _refus(ctx)
    message = ""
    if ctx.req.methode == "POST":
        action = ctx.req.champ("action")
        try:
            if action == "Supprimer":
                if not action_permise(ctx, "Supprimer"):
                    raise ValueError("Votre profil n'a pas le droit « Supprimer ».")
                with ctx.app.ecriture:
                    dc.Registre(ctx.racine).supprimer(doc.numero)
                from .serveur import redirection

                return redirection(f"/documents?cote={cote}")
            if action == "Transformer":
                with ctx.app.ecriture:
                    nouveau = dc.Registre(ctx.racine).transformer(doc.numero, ctx.req.champ("cible"),
                                                                  ctx.req.champ("jour"), ctx.u.nom)
                from .serveur import redirection

                return redirection(f"/document?n={nouveau.numero}")
            if action == "Facturer":
                with ctx.app.ecriture:
                    facture = dc.Registre(ctx.racine).facturer(doc.numero, ctx.u.nom)
                from .serveur import redirection

                return redirection(f"/document?n={facture.numero}")
            if action == "Importer dans Sage":
                def importer(journal):
                    r = dc.importer_factures(ctx.racine, ctx.config, [doc.numero], journal)
                    return [f"{n} : {etat}" for n, etat in r.items()]

                return taches.lancer(ctx, f"Import de {doc.numero} dans Sage", importer, f"/document?n={doc.numero}",
                                     sage=True)
            if action == "Passer dans Sage":
                def passer(journal):
                    r = dc.passer_stock(ctx.racine, ctx.config, doc.numero, journal)
                    return [f"{n} : {etat}" for n, etat in r.items()]

                return taches.lancer(ctx, f"{doc.numero} passé dans Sage et Clover", passer,
                                     f"/document?n={doc.numero}", sage=True)
        except (ValueError, StopIteration) as erreur:
            message = _message(erreur=str(erreur))
        registre = dc.Registre(ctx.racine)
        doc = registre.document(numero)
    lignes = [[e(l.numero_sage), e(l.description), e(l.quantite.replace(".", ",")), argent(Decimal(l.prix or 0)),
               e(l.taxe or ("GQ" if l.taxable else "")), argent(l.montant)] for l in doc.lignes]
    lignes += [["", "<strong>Sous-total</strong>", "", "", "", argent(doc.sous_total)],
               ["", "Taxes", "", "", "", argent(doc.taxes)], ["", "<strong>Total</strong>", "", "", "",
                                                               f"<strong>{argent(doc.total)}</strong>"]]
    chaine = registre.chaine(doc.numero)
    actions = ""
    if registre.modifiable(doc):
        actions += f"<a class='ouvrir' href='/document/saisie?n={e(doc.numero)}'>Modifier</a> "
    cibles = [c for c in dc.TRANSFORMATIONS.get(doc.genre, [])
              if c not in (dc.COMMANDE_ACHAT, dc.FACTURE_ACHAT, dc.FACTURE_RETOUR_ACHAT)]
    formulaire = f"<form method='post' class='ligne'>{csrf(ctx)}<input type='hidden' name='n' value='{e(doc.numero)}'>"
    if cibles:
        options = "".join(f"<option value='{c}'>{e(dc.libelle(c))}</option>" for c in cibles)
        actions += (formulaire + f"<div><label>Transformer en</label><select name='cible'>{options}</select></div>"
                    f"<div><label>Date</label><input type='date' name='jour' value='{date.today()}'></div>"
                    "<button class='second' name='action' value='Transformer'>Transformer</button></form>")
    boutons = []
    if doc.genre == dc.COMMANDE and doc.etat != dc.FACTUREE:
        boutons.append("<button name='action' value='Facturer'>Facturer la commande</button>")
    if doc.genre in dc.FACTURES_STOCK and doc.etat in (dc.BROUILLON, dc.ECHEC):
        boutons.append("<button name='action' value='Importer dans Sage'>Importer dans Sage</button>")
    if doc.genre == dc.STOCK and doc.etat in (dc.BROUILLON, dc.ECHEC):
        boutons.append("<button name='action' value='Passer dans Sage'>Passer dans Sage et Clover</button>")
    if registre.modifiable(doc):
        boutons.append("<button class='second' name='action' value='Supprimer'>Supprimer</button>")
    if boutons:
        actions += formulaire.replace("class='ligne'", "class='boutons'") + "".join(boutons) + "</form>"
    corps = (message + f"<p><a href='/documents?cote={cote}'>◀ Documents</a> · <a href='/document/pdf?n="
             f"{e(doc.numero)}'>📄 PDF</a></p><div class='carte'><p><strong>{e(dc.libelle(doc.genre))} "
             f"{e(doc.numero)}</strong> du {e(doc.date)} · <span class='etat'>{e(doc.etat)}</span></p>"
             f"<p>{'Client' if cote == 'vente' else ('Fournisseur' if cote == 'achat' else 'Sens')} : "
             f"{e(doc.tiers or doc.sens)} · Dépôt : {e(doc.depot or 'Emplacement par défaut')}</p>"
             + (f"<p>Remarque : {e(doc.remarque)}</p>" if doc.remarque else "")
             + (f"<p>Vient de : {' → '.join(e(x) for x in chaine)}</p>" if chaine else "")
             + (f"<p>Suivant : {e(doc.lien)}</p>" if doc.lien else "")
             + ("".join(f"<p class='note'>{e(m)}</p>" for m in doc.messages)) + "</div>"
             + tableau(["N° Sage", "Description", "Quantité", "Prix", "Taxes", "Montant"], lignes, {2, 3, 5})
             + actions)
    return Reponse(corps=page(ctx, f"{dc.libelle(doc.genre)} {doc.numero}", corps))


def document_pdf(ctx: Contexte) -> Reponse:
    from .. import documents as dc

    try:
        doc = dc.Registre(ctx.racine).document(ctx.req.query.get("n", ""))
    except (StopIteration, KeyError, ValueError):
        return Reponse(404, page(ctx, "Document", "<p>Document introuvable.</p>"))
    if not _permis(ctx, dc.cote(doc.genre)):
        return _refus(ctx)
    chemin = dc.ecrire_pdf(ctx.racine, doc)
    return Reponse(corps=chemin.read_bytes(), type="application/pdf",
                   entetes={"Content-Disposition": f"inline; filename={doc.numero}.pdf"})


def _listes(ctx: Contexte, cote: str) -> tuple[list[str], dict[str, str]]:
    """(noms des tiers, {n° Sage : description}) lus dans Sage, gardés 5 min ; vides si Sage ne répond pas."""
    from .. import rapports as rp
    from ..bons_commande import descriptions_sage
    from .consultations import sage

    try:
        tiers = sage(ctx, lambda b: rp.noms(b, "tvendor" if cote == "achat" else "tcustomr"), ("noms", cote)) \
            if cote != "stock" else []
        articles = sage(ctx, descriptions_sage, ("descriptions",))
    except (Exception, SystemExit):  # noqa: BLE001
        tiers, articles = [], {}
    if not articles or (cote == "achat" and not tiers):  # Sage ne répond pas : copies locales des listes de Sage
        from .pages_fournisseurs import _listes as copies

        fournisseurs, articles_copie = copies(ctx.racine)
        articles = articles or {a.numero: a.description for a in articles_copie}
        if cote == "achat" and not tiers:
            tiers = fournisseurs
    return tiers, articles


def saisie(ctx: Contexte) -> Reponse:
    from .. import documents as dc
    from .serveur import redirection

    registre = dc.Registre(ctx.racine)
    numero = ctx.req.query.get("n") or ctx.req.champ("n")
    doc = None
    if numero:
        try:
            doc = registre.document(numero)
        except (StopIteration, KeyError, ValueError):
            return Reponse(404, page(ctx, "Document", "<p>Document introuvable.</p>"))
    genre = doc.genre if doc else (ctx.req.query.get("genre") or ctx.req.champ("genre") or dc.FACTURE)
    if genre not in dc.TYPES:
        return Reponse(404, page(ctx, "Document", "<p>Type de document inconnu.</p>"))
    cote = dc.cote(genre)
    if not _permis(ctx, cote):
        return _refus(ctx)
    tiers_noms, articles = _listes(ctx, cote)
    depots = dc.depots(ctx.config)
    message = ""
    valeurs = {"tiers": doc.tiers if doc else "", "jour": doc.date if doc else date.today().isoformat(),
               "remarque": doc.remarque if doc else "", "sens": doc.sens if doc else (ctx.req.query.get("sens") if ctx.req.query.get("sens") in (dc.ENTREE, dc.SORTIE)
                                           else dc.SORTIE),
               "depot": doc.depot if doc else ""}
    lignes_doc = [(l.numero_sage, l.description, l.quantite, l.prix, l.taxe or ("GQ" if l.taxable else ""))
                  for l in doc.lignes] if doc else []
    if ctx.req.methode == "POST":
        valeurs = {k: ctx.req.champ(k).strip() for k in valeurs}
        lignes_doc = [x for x in zip(ctx.req.champs("article"), ctx.req.champs("description"), ctx.req.champs("quantite"),
                                     ctx.req.champs("prix"), ctx.req.champs("taxe")) if x[0].strip() or x[2].strip()]
    action = ctx.req.champ("action") if ctx.req.methode == "POST" else ""
    edition = ctx.req.champ("edition")
    edition = int(edition) if edition.isdigit() else None
    ajout = {"a_article": "", "a_quantite": "", "a_prix": "", "a_taxe": "GQ" if cote == "vente" else ""}
    etat = ""
    if action in ("Ajouter la ligne", "Mettre à jour la ligne"):  # SaisieDocument.ajouter (Entrée)
        ajout = {k: ctx.req.champ(k).strip() for k in ajout}
        article = ajout["a_article"].split(" ")[0]
        try:
            if article not in articles:
                raise ValueError("Choisissez l'article dans la liste.")
            q = Decimal(ajout["a_quantite"].replace(",", ".") or "0")
            if q <= 0:
                raise ValueError("Quantité invalide.")
            prix_ = Decimal((ajout["a_prix"] or "0").replace(",", ".").replace("$", "").replace(" ", "") or "0")
            ligne = (article, articles.get(article, ""), str(q), str(prix_), ajout["a_taxe"])
            if edition is not None and edition < len(lignes_doc):
                lignes_doc[edition] = ligne
            else:
                lignes_doc.append(ligne)
            ajout = {"a_article": "", "a_quantite": "", "a_prix": "", "a_taxe": ajout["a_taxe"]}
            edition = None
        except (ValueError, InvalidOperation) as erreur:
            etat = f"✘ {erreur}" if str(erreur) else "✘ Quantité ou prix invalide."
    elif action == "Retirer la ligne":
        rang = ctx.req.champ("rang")
        if rang.isdigit() and int(rang) < len(lignes_doc):
            del lignes_doc[int(rang)]
        edition = None
    elif action.startswith("Reprendre ") and action[10:].isdigit() and int(action[10:]) < len(lignes_doc):
        edition = int(action[10:])
        a_, _d, q_, p_, t_ = lignes_doc[edition]
        ajout = {"a_article": a_, "a_quantite": str(q_).replace(".", ","), "a_prix": str(p_).replace(".", ","),
                 "a_taxe": t_}
        etat = f"Ligne {edition + 1} : modifiez les champs puis « Mettre à jour la ligne »."
    elif action == "Enregistrer":
        try:
            lignes = []
            for article, description, quantite, prix, taxe in lignes_doc:
                article = article.strip().split(" ")[0]
                if not article:
                    raise ValueError("Chaque ligne doit avoir un n° d'article Sage.")
                q = Decimal(str(quantite).replace(",", ".").strip() or "0")
                p_ = Decimal((str(prix) or "0").replace(",", ".").replace("$", "").replace(" ", "") or "0")
                lignes.append(dc.LigneDocument(article, str(description).strip() or articles.get(article, ""), str(q),
                                               str(p_), taxe in ("GQ", "G", "Q"), taxe=taxe if taxe in TAXES else ""))
            if not lignes:
                raise ValueError("Ajoutez au moins une ligne.")
            depot = valeurs["depot"] if valeurs["depot"] in depots.values() else ""
            with ctx.app.ecriture:
                r = dc.Registre(ctx.racine)
                if doc:
                    d = r.modifier(doc.numero, valeurs["tiers"], valeurs["jour"], lignes, valeurs["remarque"],
                                   valeurs["sens"], depot)
                else:
                    d = r.ajouter(genre, valeurs["tiers"], valeurs["jour"], lignes, valeurs["remarque"],
                                  valeurs["sens"] if cote == "stock" else "", ctx.u.nom, depot)
            return redirection(f"/document?n={d.numero}")
        except (ValueError, InvalidOperation) as erreur:
            message = _message(erreur=str(erreur) or "Quantité ou prix invalide.")
    liste_tiers = "<datalist id='tiers'>" + "".join(f"<option value='{e(n)}'>" for n in tiers_noms) + "</datalist>"
    liste_articles = "<datalist id='articles'>" + "".join(f"<option value='{e(n)}'>{e(d)}</option>"
                                                          for n, d in articles.items()) + "</datalist>"
    depots_html = "".join(f"<option value='{e(v)}'{' selected' if v == valeurs['depot'] else ''}>{e(k)}</option>"
                          for k, v in depots.items())
    entete = (f"<div><label>{'Client' if cote == 'vente' else 'Fournisseur'} *</label><input name='tiers' list='tiers' "
              f"value='{e(valeurs['tiers'])}' size='30'>{liste_tiers}</div>" if cote != "stock" else
              "<div><label>Mouvement</label><select name='sens'>" + "".join(
                  f"<option{' selected' if x == valeurs['sens'] else ''}>{x}</option>" for x in (dc.ENTREE, dc.SORTIE))
              + "</select></div>")
    libelle_prix = "Coût unitaire" if cote == "stock" else ("Prix d'achat" if cote == "achat" else "Prix de vente")
    taxes_options = "".join(f"<option value='{x}'{' selected' if x == ajout['a_taxe'] else ''}>{x or 'Aucune'}"
                            "</option>" for x in TAXES)
    caches = "".join(f"<input type='hidden' name='article' value='{e(a_)}'><input type='hidden' name='description' "
                     f"value='{e(d_)}'><input type='hidden' name='quantite' value='{e(str(q_))}'><input type='hidden' "
                     f"name='prix' value='{e(str(p_))}'><input type='hidden' name='taxe' value='{e(t_)}'>"
                     for a_, d_, q_, p_, t_ in lignes_doc)
    from .consultations import Section, tableau_section

    rangees, total = [], Decimal(0)
    for k, (a_, d_, q_, p_, t_) in enumerate(lignes_doc):
        try:
            q_d = Decimal(str(q_).replace(",", ".") or "0")
            p_d = Decimal(str(p_).replace(",", ".").replace("$", "").replace(" ", "") or "0")
        except InvalidOperation:
            q_d = p_d = Decimal(0)
        montant = (q_d * p_d).quantize(Decimal("0.01"))
        total += montant
        rangees.append([f"<input type='radio' name='rang' value='{k}'{' checked' if k == edition else ''}>",
                        f"<button class='lien' name='action' value='Reprendre {k}'>{e(a_)}</button>",
                        e(d_ or articles.get(a_, "")), f"{q_d.normalize():f}".replace(".", ","), argent(p_d),
                        argent(montant)] + ([e(t_ or "—")] if cote != "stock" else []))
    entetes = ["", "N° Sage", "Description", "Quantité", libelle_prix, "Montant"] + (["Taxes"] if cote != "stock" else [])
    corps = (message + f"<form method='post'>{csrf(ctx)}<input type='hidden' name='genre' value='{genre}'>"
             f"<input type='hidden' name='n' value='{e(numero or '')}'>{caches}"
             + (f"<input type='hidden' name='edition' value='{edition}'>" if edition is not None else "")
             + f"<div class='barre-onglet'>{entete}<div><label>Dépôt *</label><select name='depot'>{depots_html}"
               f"</select></div><div><label>Date</label><input type='date' name='jour' value='{e(valeurs['jour'])}'>"
               f"</div><div><label>Remarque</label><input name='remarque' value='{e(valeurs['remarque'])}' size='30'>"
               f"</div></div>{liste_articles}<div class='barre-onglet'><div class='large'><label>Article</label><input "
               f"name='a_article' list='articles' value='{e(ajout['a_article'])}' size='36'></div><div><label>Quantité"
               f"</label><input name='a_quantite' value='{e(ajout['a_quantite'])}' size='7'></div><div><label>"
               f"{libelle_prix}</label><input name='a_prix' value='{e(ajout['a_prix'])}' size='9'></div>"
             + (f"<div><label>Taxes</label><select name='a_taxe'>{taxes_options}</select></div>" if cote != "stock"
                else "")
             + "<button name='action' value='" + ("Mettre à jour la ligne'>✔ Mettre à jour la ligne" if edition is not None
                                                 else "Ajouter la ligne'>➕ Ajouter la ligne")
             + "</button><button class='second' name='action' value='Retirer la ligne'>✖ Retirer la ligne</button>"
               "</div>"
             + tableau_section(Section("Lignes", entetes, rangees, html=set(range(len(entetes)))))
             + f"<div class='barre-onglet'><strong>{len(lignes_doc)} ligne(s) — total {argent(total)}</strong><button "
               "class='a-droite' name='action' value='Enregistrer'>✔ Enregistrer</button><a class='ouvrir' "
               f"href='/documents?cote={cote}'>✖ Fermer</a></div></form>"
             + f"<p class='{'erreur-texte' if etat.startswith('✘') else 'note'}'>"
             + e(etat or "Cliquez sur le n° d'une ligne pour la reprendre dans les champs.") + "</p>")
    titre = f"Modifier {doc.numero}" if doc else f"Nouveau : {dc.libelle(genre).lower()}"
    return Reponse(corps=page(ctx, titre, corps))


def choisir_type(ctx: Contexte) -> Reponse:
    """Fenêtre « Ajouter un document » de Windows (fenetre_chaine.choisir) : type à choisir, puis la saisie, la page
    ou la fenêtre qui le crée (FenetreDocumentsChaine.ajouter)."""
    from urllib.parse import quote

    from .. import documents as dc
    from ..fenetre_chaine import STOCK_ENTREE, STOCK_INVENTAIRE, STOCK_PERTE, STOCK_TOURNANT, STOCK_TRANSFERT, TYPES_STOCK
    from .serveur import redirection

    cote = ctx.req.query.get("cote") or ctx.req.champ("cote")
    cote = cote if cote in ("vente", "achat", "stock") else "vente"
    if not _permis(ctx, cote):
        return _refus(ctx)
    retour = {"vente": "/documents-vente", "achat": "/documents-achat", "stock": "/documents-stock"}[cote]
    if cote == "stock":
        choix = [(x, x) for x in TYPES_STOCK]
        question = "Quel type de document de stock voulez-vous ajouter ?"
    else:
        choix = [(g, dc.libelle(g)) for g in (dc.TYPES_VENTE if cote == "vente" else dc.TYPES_ACHAT)]
        question = "Quel type de document voulez-vous ajouter ?"
    if ctx.req.methode == "POST":
        if ctx.req.champ("action") != "OK":
            return redirection(retour)
        genre = ctx.req.champ("type")
        if cote == "stock":
            pages_ = {STOCK_TRANSFERT: "/transferts", STOCK_PERTE: "/pertes", STOCK_INVENTAIRE: "/inventaire",
                      STOCK_TOURNANT: "/inventaire-tournant"}
            if genre in pages_:
                return redirection(pages_[genre])
            return redirection(f"/document/saisie?genre={dc.STOCK}&sens="
                               + quote(dc.ENTREE if genre == STOCK_ENTREE else dc.SORTIE))
        if genre == dc.COMMANDE_ACHAT:
            return redirection("/bons-commande?op=ajouter")
        if genre == dc.FACTURE_ACHAT:
            return redirection("/saisir-facture-achat")
        if genre == dc.FACTURE_RETOUR_ACHAT:
            return redirection("/retours")
        if genre in dict(choix):
            return redirection(f"/document/saisie?genre={quote(genre)}")
    radios = "".join(f"<label class='choix-radio'><input type='radio' name='type' value='{e(k)}'"
                     f"{' checked' if n == 0 else ''}> {e(lib)}</label>" for n, (k, lib) in enumerate(choix))
    corps = (f"<form method='post' class='carte fenetre-choix'>{csrf(ctx)}<input type='hidden' name='cote' "
             f"value='{cote}'><h2>Ajouter un document</h2><p>{e(question)}</p>{radios}<div class='barre-onglet'>"
             "<button class='a-droite' name='action' value='OK'>✔ OK</button><button class='second' name='action' "
             "value='Annuler'>Annuler</button></div></form>")
    return Reponse(corps=page(ctx, "Ajouter un document", corps))


FONCTIONS = [
    Fonction("/documents", "Documents saisis", None, documents, "🗂", "", toujours=True, menu=False),
    Fonction("/document", "Document", None, document, "🗂", "", toujours=True, menu=False),
    Fonction("/document/pdf", "Document (PDF)", None, document_pdf, "📄", "", toujours=True, menu=False),
    Fonction("/document/saisie", "Saisie d'un document", None, saisie, "✍", "", toujours=True, menu=False),
    Fonction("/document/choisir", "Ajouter un document", None, choisir_type, "✍", "", toujours=True, menu=False),
]
WEB = {"Saisir une facture de vente": "/document/saisie?genre=facture",
       "Commandes clients": "/documents?cote=vente&genre=commande",
       "Saisir un document de stock": "/document/saisie?genre=stock"}
