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
        return [], {}
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
               "remarque": doc.remarque if doc else "", "sens": doc.sens if doc else dc.SORTIE,
               "depot": doc.depot if doc else ""}
    lignes_doc = [(l.numero_sage, l.description, l.quantite, l.prix, l.taxe or ("GQ" if l.taxable else ""))
                  for l in doc.lignes] if doc else []
    nombre = LIGNES_SAISIE
    if ctx.req.methode == "POST":
        valeurs = {k: ctx.req.champ(k).strip() for k in valeurs}
        lignes_doc = list(zip(ctx.req.champs("article"), ctx.req.champs("description"), ctx.req.champs("quantite"),
                              ctx.req.champs("prix"), ctx.req.champs("taxe")))
        nombre = max(LIGNES_SAISIE, len(lignes_doc)) + (LIGNES_SAISIE if ctx.req.champ("action") == "Plus" else 0)
        if ctx.req.champ("action") == "Enregistrer":
            try:
                lignes = []
                for article, description, quantite, prix, taxe in lignes_doc:
                    if not article.strip() and not quantite.strip():
                        continue
                    article = article.strip().split(" ")[0]
                    if not article:
                        raise ValueError("Chaque ligne doit avoir un n° d'article Sage.")
                    q = Decimal(quantite.replace(",", ".").strip() or "0")
                    p = Decimal((prix or "0").replace(",", ".").replace("$", "").replace(" ", "") or "0")
                    lignes.append(dc.LigneDocument(article, description.strip() or articles.get(article, ""), str(q),
                                                   str(p), taxe in ("GQ", "G", "Q"), taxe=taxe if taxe in TAXES else ""))
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
    entete = (f"<div><label>{'Client' if cote == 'vente' else 'Fournisseur'}</label><input name='tiers' list='tiers' "
              f"value='{e(valeurs['tiers'])}' size='30' required>{liste_tiers}</div>" if cote != "stock" else
              "<div><label>Sens</label><select name='sens'>" + "".join(
                  f"<option{' selected' if s == valeurs['sens'] else ''}>{s}</option>" for s in (dc.ENTREE, dc.SORTIE))
              + "</select></div>")
    rangees = []
    for i in range(nombre):
        a, d, q, p, t = (lignes_doc[i] if i < len(lignes_doc) else ("", "", "", "", "GQ" if cote == "vente" else ""))
        options = "".join(f"<option value='{x}'{' selected' if x == t else ''}>{x or 'aucune'}</option>" for x in TAXES)
        rangees.append(f"<tr><td><input name='article' list='articles' value='{e(a)}' size='14'></td>"
                       f"<td><input name='description' value='{e(d)}' size='30'></td><td><input name='quantite' "
                       f"value='{e(str(q).replace('.', ','))}' size='6' inputmode='decimal'></td><td><input name='prix' "
                       f"value='{e(str(p).replace('.', ','))}' size='8' inputmode='decimal'></td><td><select "
                       f"name='taxe'>{options}</select></td></tr>")
    corps = (message + f"<form method='post'>{csrf(ctx)}<input type='hidden' name='genre' value='{genre}'>"
             f"<input type='hidden' name='n' value='{e(numero or '')}'><div class='carte'><div class='ligne'>{entete}"
             f"<div><label>Date</label><input type='date' name='jour' value='{e(valeurs['jour'])}' required></div>"
             f"<div><label>Dépôt *</label><select name='depot'>{depots_html}</select></div><div><label>Remarque"
             f"</label><input name='remarque' value='{e(valeurs['remarque'])}' size='30'></div></div></div>"
             f"{liste_articles}<div class='defile'><table><tr><th>N° d'article Sage</th><th>Description</th>"
             f"<th class='n'>Quantité</th><th class='n'>Prix{' (coût unitaire)' if cote == 'stock' else ''}</th>"
             f"<th>Taxes</th></tr>{''.join(rangees)}</table></div><div class='boutons'><button name='action' "
             "value='Enregistrer'>Enregistrer</button><button class='second' name='action' value='Plus'>Plus de lignes"
             "</button></div></form><p class='note'>Lignes vides ignorées ; description vide = celle de Sage.</p>")
    titre = f"Modifier {doc.numero}" if doc else f"Nouveau : {dc.libelle(genre).lower()}"
    return Reponse(corps=page(ctx, titre, corps))


FONCTIONS = [
    Fonction("/documents", "Documents saisis", None, documents, "🗂", "", toujours=True, menu=False),
    Fonction("/document", "Document", None, document, "🗂", "", toujours=True, menu=False),
    Fonction("/document/pdf", "Document (PDF)", None, document_pdf, "📄", "", toujours=True, menu=False),
    Fonction("/document/saisie", "Saisie d'un document", None, saisie, "✍", "", toujours=True, menu=False),
]
WEB = {"Saisir une facture de vente": "/document/saisie?genre=facture",
       "Commandes clients": "/documents?cote=vente&genre=commande",
       "Saisir un document de stock": "/document/saisie?genre=stock"}
