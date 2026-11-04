"""6e vague de l'application web : rubrique Fournisseur. Factures fournisseurs (comme page_fournisseurs) : envoi d'une
facture (PDF ou photo) par le navigateur, lecture des nouvelles, fournisseurs et articles relus dans Sage, fiche de la
facture (en-tête, lignes : article Sage, facteur, taxes, confirmation), enregistrement (mémoire du fournisseur), import
dans Sage (et Clover), écarter, supprimer. Mêmes règles : Qté Sage = Qté × Facteur ; Montant = Qté × Prix.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .pages import Contexte, Fonction, argent, csrf, page, tableau
from .pages_compta import _message
from .serveur import Reponse, echapper as e, redirection

TYPES_FICHIERS = (".pdf", ".jpg", ".jpeg", ".png", ".heic", ".tif", ".tiff")


def _listes(racine: Path):
    from ..articles_sage import lire_copie
    from ..fournisseurs import lire_copie_fournisseurs

    return lire_copie_fournisseurs(racine), lire_copie(racine / "donnees" / "articles_sage.csv")


def _lire_nouvelles(ctx: Contexte, journal) -> list[str]:
    from ..fournisseurs import (A_SAISIR, Facture, MemoireCorrespondance, Registre, completer, empreinte,
                                etat_apres_controle, lire_facture)

    registre = Registre(ctx.racine)
    nouveaux = registre.nouveaux_fichiers()
    noms, articles = _listes(ctx.racine)
    memoire = MemoireCorrespondance(ctx.racine)
    lues = []
    for chemin in nouveaux:
        journal(f"Lecture de {chemin.name}…")
        try:
            facture = lire_facture(chemin)
        except Exception as exc:  # noqa: BLE001 — facture illisible : à saisir à la main
            facture = Facture(chemin.name, empreinte(chemin), etat=A_SAISIR, remarques=[f"lecture impossible : {exc}"])
        completer(facture, memoire, noms, articles)
        facture.etat = etat_apres_controle(facture, facture.controles(set(noms) or None))
        lues.append(facture)
    with ctx.app.ecriture:
        registre = Registre(ctx.racine)
        registre.factures.extend(lues)
        registre.enregistrer()
    return [f"{len(lues)} facture(s) lue(s)."] + [f"{f.fichier} : {f.etat}" for f in lues]


def _relire_sage(ctx: Contexte, journal) -> list[str]:
    from ..__main__ import lire_sage
    from ..articles_sage import ecrire_copie
    from ..fournisseurs import (DEJA_DANS_SAGE, PRETE, Registre, archiver_deja_dans_sage, deja_dans_sage_fichiers,
                                ecrire_copie_fournisseurs, fournisseurs_actifs)

    pretes = [f for f in Registre(ctx.racine).factures if f.etat == PRETE]
    journal("Lecture des fournisseurs et des articles dans Sage…")
    noms, articles, deja = lire_sage(ctx.config, lambda base: (
        fournisseurs_actifs(base), base.articles(), deja_dans_sage_fichiers(base, pretes)), ouvrir=False)
    ecrire_copie_fournisseurs(ctx.racine, noms)
    ecrire_copie(articles, ctx.racine / "donnees" / "articles_sage.csv")
    archivees = []
    with ctx.app.ecriture:
        registre = Registre(ctx.racine)
        for f in list(registre.factures):
            if f.fichier in deja:
                archiver_deja_dans_sage(ctx.racine, f, deja[f.fichier])
                archivees.append(f"{f.fournisseur_sage} n° {f.numero}")
        registre.factures = [f for f in registre.factures if f.etat != DEJA_DANS_SAGE]
        registre.enregistrer()
    return [f"{len(noms)} fournisseur(s), {len(articles)} article(s) lus dans Sage."] + \
        ([f"Déjà dans Sage, archivée(s) : {', '.join(archivees)}"] if archivees else [])


def _importer(ctx: Contexte, factures, clover: bool):
    def travail(journal):
        from ..import_achats import importer_achats

        journal("Contrôles, import dans Sage, vérification…")
        with ctx.app.ecriture:
            resultats = importer_achats(ctx.racine, ctx.config, factures, clover=clover)
        return [f"{fichier} : {texte}" for fichier, texte in resultats.items()]
    return travail


def factures(ctx: Contexte) -> Reponse:
    from .. import fournisseurs as fo
    from . import taches

    message = ""
    if ctx.req.methode == "POST":
        action = ctx.req.champ("action")
        if action == "Envoyer" and "facture" in ctx.req.fichiers:
            nom, contenu = ctx.req.fichiers["facture"]
            if Path(nom).suffix.lower() not in TYPES_FICHIERS:
                message = _message(erreur="PDF ou photo seulement (pdf, jpg, png, heic, tif).")
            else:
                dossier = fo.Registre(ctx.racine).dossier
                dossier.mkdir(parents=True, exist_ok=True)
                cible = dossier / f"{date.today()}_{Path(nom).name}"
                cible.write_bytes(contenu)
                return taches.lancer(ctx, "Lecture des nouvelles factures", lambda j: _lire_nouvelles(ctx, j),
                                     "/factures-fournisseurs")
        elif action == "Lire les nouvelles":
            return taches.lancer(ctx, "Lecture des nouvelles factures", lambda j: _lire_nouvelles(ctx, j),
                                 "/factures-fournisseurs")
        elif action == "Fournisseurs et articles Sage":
            return taches.lancer(ctx, "Fournisseurs et articles de Sage", lambda j: _relire_sage(ctx, j),
                                 "/factures-fournisseurs")
        elif action == "Lire le courriel":
            def lire(journal):
                from ..factures_courriel import recuperer

                copies = recuperer(ctx.racine, ctx.config)
                return [f"{len(copies)} pièce(s) jointe(s) copiée(s)."] + _lire_nouvelles(ctx, journal)

            return taches.lancer(ctx, "Factures reçues par courriel", lire, "/factures-fournisseurs")
        elif action == "Importer toutes":
            pretes = [f for f in fo.Registre(ctx.racine).factures if f.etat == fo.PRETE]
            if not pretes:
                message = _message(erreur="Aucune facture « Prête à importer ».")
            else:
                return taches.lancer(ctx, f"Import de {len(pretes)} facture(s) fournisseurs",
                                     _importer(ctx, pretes, ctx.req.champ("clover") == "1"), "/factures-fournisseurs",
                                     sage=True)
    registre = fo.Registre(ctx.racine)
    filtre = ctx.req.query.get("filtre", "À traiter")
    visibles = [(i, f) for i, f in enumerate(registre.factures) if filtre == "Toutes" or f.etat != fo.IMPORTEE]
    lignes = [[f"<a href='/facture-fournisseur?i={i}'>{e(f.fichier)}</a>", e(f.fournisseur_sage or f.fournisseur_lu),
               e(f.numero), e(f.date_facture), argent(f.total) if f.total is not None else "", e(f.etat)]
              for i, f in sorted(visibles, key=lambda x: x[1].date_facture, reverse=True)]
    pretes = sum(1 for f in registre.factures if f.etat == fo.PRETE)
    options = "".join(f"<option{' selected' if x == filtre else ''}>{x}</option>" for x in ("À traiter", "Toutes"))
    corps = (message
             + f"<form method='post' enctype='multipart/form-data' class='ligne'>{csrf(ctx)}<div><label>Facture (PDF "
               "ou photo)</label><input type='file' name='facture' accept='.pdf,image/*' capture='environment' "
               "required></div><button name='action' value='Envoyer'>Envoyer et lire</button></form>"
             + f"<form method='post' class='boutons'>{csrf(ctx)}<button class='second' name='action' value='Lire les "
               "nouvelles'>Lire les nouvelles</button><button class='second' name='action' value='Lire le courriel'>"
               "📧 Lire le courriel</button><button class='second' name='action' value='Fournisseurs et articles "
               "Sage'>Fournisseurs et articles Sage</button></form>"
             + f"<form class='ligne' method='get'><div><label>Afficher</label><select name='filtre'>{options}</select>"
               "</div><button class='second'>Afficher</button></form>"
             + tableau(["Fichier", "Fournisseur", "N°", "Date", "Total", "État"], lignes, {4})
             + (f"<form method='post' class='ligne'>{csrf(ctx)}<label><input type='checkbox' name='clover' value='1' "
                f"checked> Mettre aussi à jour Clover</label><button name='action' value='Importer toutes'>Importer "
                f"les {pretes} facture(s) prête(s)</button></form>" if pretes else "")
             + "<p class='note'>Sur téléphone, « Facture » ouvre l'appareil photo.</p>")
    return Reponse(corps=page(ctx, "Factures fournisseurs", corps))


def _decimal(texte: str, defaut: str = "0") -> Decimal:
    texte = (texte or "").replace(",", ".").replace("$", "").replace(" ", "").strip()
    return Decimal(texte or defaut)


def facture(ctx: Contexte) -> Reponse:
    from .. import fournisseurs as fo
    from . import taches

    registre = fo.Registre(ctx.racine)
    try:
        i = int(ctx.req.query.get("i") or ctx.req.champ("i"))
        f = registre.factures[i]
    except (ValueError, IndexError):
        return Reponse(404, page(ctx, "Facture fournisseur", "<p>Facture introuvable.</p>"))
    noms, articles = _listes(ctx.racine)
    descriptions = {a.numero: a.description for a in articles}
    message = ""
    if ctx.req.methode == "POST":
        action = ctx.req.champ("action")
        if action in ("Écarter", "Supprimer"):
            with ctx.app.ecriture:
                r = fo.Registre(ctx.racine)
                (r.ecarter if action == "Écarter" else r.supprimer)(r.factures[i])
                r.enregistrer()
            return redirection("/factures-fournisseurs")
        try:
            with ctx.app.ecriture:
                r = fo.Registre(ctx.racine)
                f = r.factures[i]
                f.fournisseur_sage = ctx.req.champ("fournisseur").strip()
                f.numero, f.date_facture = ctx.req.champ("numero").strip(), ctx.req.champ("date").strip()
                f.sous_total = _decimal(ctx.req.champ("sous_total")) if ctx.req.champ("sous_total").strip() else None
                f.tps, f.tvq = _decimal(ctx.req.champ("tps")), _decimal(ctx.req.champ("tvq"))
                f.total = _decimal(ctx.req.champ("total")) if ctx.req.champ("total").strip() else None
                nouvelles = []
                confirmees = set(ctx.req.champs("confirme"))
                for k, (desc, code, qte, prix, facteur, taxe, numero) in enumerate(zip(
                        ctx.req.champs("description"), ctx.req.champs("code"), ctx.req.champs("quantite"),
                        ctx.req.champs("prix"), ctx.req.champs("facteur"), ctx.req.champs("taxe"),
                        ctx.req.champs("article"))):
                    if not desc.strip() and not numero.strip() and not qte.strip():
                        continue
                    l = fo.Ligne(desc.strip(), _decimal(qte, "1"), _decimal(prix), Decimal(0), code.strip())
                    l.montant = (l.quantite * l.prix).quantize(Decimal("0.01"))
                    l.facteur = _decimal(facteur, "1")
                    if l.facteur <= 0:
                        raise ValueError(f"Ligne {k + 1} : le facteur doit être supérieur à 0.")
                    l.taxe, l.taxable = taxe if taxe in ("GQ", "G", "Q") else "", taxe in ("GQ", "G", "Q")
                    l.numero_sage = numero.strip().split(" ")[0]
                    l.description_sage = descriptions.get(l.numero_sage, "")
                    l.confirme = bool(l.numero_sage) and str(k) in confirmees
                    nouvelles.append(l)
                f.lignes = nouvelles
                memoire = fo.MemoireCorrespondance(ctx.racine)
                if f.fournisseur_sage and f.fournisseur_lu:
                    memoire.retenir_fournisseur(f.fournisseur_lu, f.fournisseur_sage)
                for l in f.lignes:
                    if l.confirme and l.numero_sage and f.fournisseur_sage:
                        memoire.retenir_article(f.fournisseur_sage, l)
                problemes = f.controles(set(noms) or None)
                f.etat = fo.etat_apres_controle(f, problemes)
                memoire.enregistrer()
                r.enregistrer()
            if action == "Importer":
                if f.etat != fo.PRETE:
                    raise ValueError("Cette facture n'est pas prête à importer : " + " ; ".join(problemes))
                return taches.lancer(ctx, f"Import de la facture {f.numero}", _importer(ctx, [f], ctx.req.champ(
                    "clover") == "1"), f"/facture-fournisseur?i={i}", sage=True)
            message = _message("Facture enregistrée." if not problemes else "Enregistrée ; à compléter : "
                               + " ; ".join(problemes))
        except (ValueError, InvalidOperation) as erreur:
            message = _message(erreur=str(erreur) or "Nombre invalide.")
        registre = fo.Registre(ctx.racine)
        f = registre.factures[i]
    liste_f = "<datalist id='fournisseurs'>" + "".join(f"<option value='{e(n)}'>" for n in noms) + "</datalist>"
    liste_a = "<datalist id='articles'>" + "".join(f"<option value='{e(a.numero)}'>{e(a.description)}</option>"
                                                   for a in articles) + "</datalist>"
    rangees = []
    for k, l in enumerate(f.lignes + [fo.Ligne("", Decimal(1), Decimal(0), Decimal(0))] * 3):
        taxe = l.taxe or ("GQ" if l.taxable else "")
        options = "".join(f"<option value='{x}'{' selected' if x == taxe else ''}>{x or 'aucune'}</option>"
                          for x in ("GQ", "G", "Q", ""))
        qte_sage = l.en_sage()[0] if l.description or l.numero_sage else ""
        rangees.append(
            f"<tr><td><input name='description' value='{e(l.description)}' size='26'></td><td><input name='code' "
            f"value='{e(l.code)}' size='8'></td><td><input name='quantite' value='{e(f'{l.quantite:g}')}' size='5'>"
            f"</td><td><input name='prix' value='{e(str(l.prix))}' size='7'></td><td class='n'>"
            f"{argent(l.montant) if l.description else ''}</td><td><input name='facteur' value='{e(f'{l.facteur:g}')}' "
            f"size='4'></td><td class='n'>{e(f'{qte_sage:g}' if qte_sage != '' else '')}</td><td><select name='taxe'>"
            f"{options}</select></td><td><input name='article' list='articles' value='{e(l.numero_sage)}' size='12'>"
            f"<div class='note'>{e(l.description_sage)}</div></td><td><input type='checkbox' name='confirme' "
            f"value='{k}'{' checked' if l.confirme else ''}></td></tr>")
    problemes = f.controles(set(noms) or None)
    corps = (message + f"<p><a href='/factures-fournisseurs'>◀ Factures fournisseurs</a> · <a href='/facture-fichier?i="
             f"{i}'>📄 Voir la facture</a></p><p>État : <span class='etat'>{e(f.etat)}</span> · lu : "
             f"{e(f.fournisseur_lu)} · modèle {e(f.modele or '—')}</p>"
             + ("<ul>" + "".join(f"<li class='erreur'>{e(p)}</li>" for p in problemes) + "</ul>" if problemes else "")
             + f"<form method='post'>{csrf(ctx)}<input type='hidden' name='i' value='{i}'><div class='carte'>"
               f"<div class='ligne'><div><label>Fournisseur Sage</label><input name='fournisseur' list='fournisseurs' "
               f"value='{e(f.fournisseur_sage)}' size='30'>{liste_f}</div><div><label>N° de facture</label><input "
               f"name='numero' value='{e(f.numero)}'></div><div><label>Date</label><input type='date' name='date' "
               f"value='{e(f.date_facture)}'></div><div><label>Sous-total</label><input name='sous_total' "
               f"value='{e('' if f.sous_total is None else str(f.sous_total))}' size='9'></div><div><label>TPS</label>"
               f"<input name='tps' value='{e(str(f.tps))}' size='7'></div><div><label>TVQ</label><input name='tvq' "
               f"value='{e(str(f.tvq))}' size='7'></div><div><label>Total</label><input name='total' "
               f"value='{e('' if f.total is None else str(f.total))}' size='9'></div></div></div>{liste_a}"
               "<div class='defile'><table><tr><th>Description</th><th>Code</th><th>Qté</th><th>Prix</th>"
               "<th class='n'>Montant</th><th>Facteur</th><th class='n'>Qté Sage</th><th>Taxes</th><th>Article Sage</th>"
               f"<th>Confirmé</th></tr>{''.join(rangees)}</table></div><p class='note'>Somme des lignes : "
               f"{argent(f.somme_lignes)}. Qté Sage = Qté × Facteur ; prix Sage = montant / Qté Sage. Cochez "
               "« Confirmé » quand l'article Sage est le bon (retenu pour ce fournisseur).</p><div class='boutons'>"
               "<button name='action' value='Enregistrer'>Enregistrer</button><label><input type='checkbox' "
               "name='clover' value='1' checked> Mettre aussi à jour Clover</label><button name='action' "
               "value='Importer'>Enregistrer et importer dans Sage</button></div></form>"
             + f"<form method='post' class='boutons'>{csrf(ctx)}<input type='hidden' name='i' value='{i}'><button "
               "class='second' name='action' value='Écarter'>Écarter</button><button class='second' name='action' "
               "value='Supprimer'>Supprimer</button></form>")
    return Reponse(corps=page(ctx, f"Facture {f.numero or f.fichier}", corps))


def fichier(ctx: Contexte) -> Reponse:
    from .. import fournisseurs as fo

    registre = fo.Registre(ctx.racine)
    try:
        f = registre.factures[int(ctx.req.query.get("i", ""))]
    except (ValueError, IndexError):
        return Reponse(404, page(ctx, "Facture", "<p>Facture introuvable.</p>"))
    chemin = registre.chemin_fichier(f)
    if not chemin.exists():
        return Reponse(404, page(ctx, "Facture", "<p>Le fichier de la facture n'est plus dans le dossier.</p>"))
    types = {".pdf": "application/pdf", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}
    return Reponse(corps=chemin.read_bytes(), type=types.get(chemin.suffix.lower(), "application/octet-stream"),
                   entetes={"Content-Disposition": "inline"})


FONCTIONS = [
    Fonction("/factures-fournisseurs", "Factures fournisseurs", "fournisseurs", factures, "🧾", "Fournisseur",
             menu=False, page_entiere=True),
    Fonction("/facture-fournisseur", "Factures fournisseurs", "fournisseurs", facture, "🧾", "Fournisseur", menu=False,
             page_entiere=True),
    Fonction("/facture-fichier", "Factures fournisseurs", "fournisseurs", fichier, "🧾", "Fournisseur", menu=False,
             page_entiere=True),
]
WEB = {"Factures fournisseurs": "/factures-fournisseurs"}
