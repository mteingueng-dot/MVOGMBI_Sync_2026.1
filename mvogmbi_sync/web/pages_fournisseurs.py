"""6e vague de l'application web : rubrique Fournisseur. Factures fournisseurs (comme page_fournisseurs) : envoi d'une
facture (PDF ou photo) par le navigateur, lecture des nouvelles, fournisseurs et articles relus dans Sage, fiche de la
facture (en-tête, lignes : article Sage, facteur, taxes, confirmation), enregistrement (mémoire du fournisseur), import
dans Sage (et Clover), écarter, supprimer. Mêmes règles : Qté Sage = Qté × Facteur ; Montant = Qté × Prix.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import quote, urlencode

from .consultations import Section, tableau_section
from .pages import Contexte, Fonction, argent, csrf, page
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


PAGES_MAX = 15  # pages photographiées d'une même facture


def pdf_des_photos(photos: list[bytes]) -> bytes:
    """Photos des pages d'une facture -> un PDF (sens de la photo corrigé, 2 000 px au plus de côté)."""
    from io import BytesIO

    from PIL import Image, ImageOps

    pages = []
    for contenu in photos:
        image = ImageOps.exif_transpose(Image.open(BytesIO(contenu))).convert("RGB")
        image.thumbnail((2000, 2000))
        pages.append(image)
    sortie = BytesIO()
    pages[0].save(sortie, "PDF", resolution=200, save_all=True, append_images=pages[1:])
    return sortie.getvalue()


def photo_facture(ctx: Contexte) -> Reponse:
    """« 📷 Photographier une facture » (demande du propriétaire du 2026-11-05 : « filmer les factures depuis notre
    téléphone et charger dans la liste ») : page faite pour le téléphone ; chaque photo est une page (gardée sur le
    serveur, jamais dans la page) ; « ✔ Terminer la facture » réunit les pages en un PDF dans le dossier des factures
    (« AAAA-MM-JJ_photo_HHMMSS.pdf ») puis la lecture (OCR de Windows) l'ajoute à la liste."""
    from datetime import datetime

    from .. import fournisseurs as fo
    from . import taches

    cle = ("photos_facture", ctx.session.jeton)
    pages = ctx.app.memoire.setdefault(cle, [])
    message = ""
    if ctx.req.methode == "POST":
        action = ctx.req.champ("action")
        if action == "Recommencer":
            pages.clear()
        elif action in ("Ajouter la page", "Terminer la facture") and "photo" in ctx.req.fichiers:
            nom, contenu = ctx.req.fichiers["photo"]
            if contenu:
                try:
                    pdf_des_photos([contenu])  # image lisible ?
                    if len(pages) >= PAGES_MAX:
                        raise ValueError(f"{PAGES_MAX} pages au plus.")
                    pages.append(contenu)
                except Exception as exc:  # noqa: BLE001 — format non lu (HEIC sans conversion, fichier abîmé)
                    message = _message(erreur=f"Photo illisible ({nom}) : {exc}. Prenez la photo avec l'appareil "
                                              "photo du téléphone (JPEG).")
        if action == "Terminer la facture" and not message:
            if not pages:
                message = _message(erreur="Prenez d'abord la photo de la facture.")
            else:
                dossier = fo.Registre(ctx.racine).dossier
                dossier.mkdir(parents=True, exist_ok=True)
                cible = dossier / f"{datetime.now():%Y-%m-%d}_photo_{datetime.now():%H%M%S}.pdf"
                cible.write_bytes(pdf_des_photos(pages))
                n = len(pages)
                pages.clear()
                return taches.lancer(ctx, f"Lecture de la facture photographiée ({n} page(s))",
                                     lambda j: _lire_nouvelles(ctx, j), "/factures-fournisseurs")
        elif action == "Ajouter la page" and not message:
            message = _message(f"Page {len(pages)} gardée. Photographiez la page suivante, ou « Terminer la facture ».")
    corps = (message + "<div class='carte photo-facture'><h2>📷 Photographier une facture</h2>"
             f"<p class='note'>Pages déjà prises : <strong>{len(pages)}</strong>. Posez la facture à plat, bien "
             "éclairée, toute la page dans la photo.</p>"
             f"<form method='post' enctype='multipart/form-data'>{csrf(ctx)}"
             "<label class='bouton-photo'>📷 Prendre la photo de la page "
             f"{len(pages) + 1}<input type='file' name='photo' accept='image/*' capture='environment' required></label>"
             "<div class='barre-onglet'><button name='action' value='Ajouter la page'>➕ Ajouter la page (il y en a "
             "d'autres)</button><button class='accent' name='action' value='Terminer la facture'>✔ Terminer la "
             "facture</button></div></form>"
             f"<form method='post' class='barre-onglet'>{csrf(ctx)}<button class='second' name='action' "
             "value='Terminer la facture' formnovalidate>✔ Terminer avec les pages prises</button><button "
             "class='danger' name='action' value='Recommencer' formnovalidate>✖ Recommencer</button><a "
             "class='ouvrir' href='/factures-fournisseurs'>◀ Factures fournisseurs</a></form></div>")
    return Reponse(corps=page(ctx, "Photographier une facture", corps))


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
        from .. import fournisseurs as fo
        from ..import_achats import importer_achats

        journal("Contrôles, import dans Sage, vérification…")
        with ctx.app.ecriture:
            # factures prises dans le registre qui sera enregistré : leur état « Importée » est gardé (défaut du
            # 2026-11-05 : importées dans Sage, elles restaient « Prête à importer » dans la liste web)
            registre = fo.Registre(ctx.racine)
            noms = {f.fichier for f in factures}
            choisies = [f for f in registre.factures if f.fichier in noms]
            try:
                resultats = importer_achats(ctx.racine, ctx.config, choisies, clover=clover)
            finally:
                registre.enregistrer()
        return [f"{fichier} : {texte}" for fichier, texte in resultats.items()]
    return travail


# couleurs de page_fournisseurs.COULEURS (Importée : terminée, texte grisé)
COULEURS = {"À saisir (photo)": "etat-a-saisir", "À vérifier": "etat-ecart", "Prête à importer": "etat-applique"}
COLONNES_LIGNES = ["Code", "Désignation du fournisseur", "Qté", "Prix fournisseur", "Montant", "N° Sage",
                   "Désignation Sage", "Qté Sage", "Prix Sage", "Facteur", "Correspondance"]


def factures(ctx: Contexte) -> Reponse:
    """Comme page_fournisseurs.PageFournisseurs : barre (« ➕ Ajouter des factures… », « 📧 Lire le courriel »,
    « ⟳ Actualiser », « 📒 Fournisseurs et articles Sage », « Afficher : », « 📤 Importer toutes les factures
    prêtes »), résumé, liste colorée ; sous la liste, la facture choisie (`?i=`) :
    en-tête, montants, contrôle, lignes, et la carte d'édition de la ligne choisie (`&l=`) avec la recherche
    d'article Sage (« Relier et confirmer », « Confirmer la proposition », « 🆕 Créer l'article »). Chaque bouton
    enregistre aussi ce qui est saisi (comme l'enregistrement automatique de Windows)."""
    from .. import fournisseurs as fo
    from . import taches
    from .pages_compta import action_permise

    filtre = ctx.req.query.get("filtre") or ctx.req.champ("filtre") or "Toutes"
    # filtres de la liste gardés quand on choisit une facture (ils changeaient l'affichage, constat du 2026-11-08)
    # sur un envoi, les champs « fournisseur » et « numero » sont ceux de la facture : les filtres de la liste
    # arrivent dans q_fichier / q_fournisseur / q_numero (avant, la liste se réduisait à la facture ouverte)
    def filtre_liste(nom):
        if ctx.req.methode == "POST":
            return (ctx.req.champ("q_" + nom) or "").strip()
        return (ctx.req.query.get(nom) or "").strip()

    q_fichier, q_fournisseur, q_numero = filtre_liste("fichier"), filtre_liste("fournisseur"), filtre_liste("numero")
    garder = "".join(f"<input type='hidden' name='q_{k}' value='{e(v)}'>" for k, v in
                     (("fichier", q_fichier), ("fournisseur", q_fournisseur), ("numero", q_numero)) if v)
    rang = _entier(ctx.req.query.get("i") or ctx.req.champ("i"))
    ligne = _entier(ctx.req.query.get("l") or ctx.req.champ("l"))
    clover = True  # chaque facture a sa case « Mettre à jour le stock Clover » (demande du 2026-11-09)
    message = ""
    if ctx.req.methode == "POST":
        action = ctx.req.champ("action")
        retour = (f"/factures-fournisseurs?filtre={filtre}" + (f"&i={rang}" if rang is not None else "")
                  + ("&onglet=liste" if ctx.req.champ("onglet") == "liste" else "")
                  + "".join(f"&{k}={quote(v)}" for k, v in (("fichier", q_fichier), ("fournisseur", q_fournisseur),
                                                                ("numero", q_numero))
                            if v))
        if action == "Ajouter des factures":
            if "facture" not in ctx.req.fichiers:
                message = _message(erreur="Choisissez une facture (PDF ou photo).")
            else:
                nom, contenu = ctx.req.fichiers["facture"]
                if Path(nom).suffix.lower() not in TYPES_FICHIERS:
                    message = _message(erreur=f"Fichiers ignorés (format non accepté) : {nom}")
                else:
                    dossier = fo.Registre(ctx.racine).dossier
                    dossier.mkdir(parents=True, exist_ok=True)
                    cible, numero = dossier / Path(nom).name, 2
                    while cible.exists():  # même nom, autre facture : on garde les deux
                        cible = dossier / f"{Path(nom).stem} ({numero}){Path(nom).suffix}"
                        numero += 1
                    cible.write_bytes(contenu)
                    return taches.lancer(ctx, "Lecture des nouvelles factures", lambda j: _lire_nouvelles(ctx, j),
                                         retour)
        elif action == "Actualiser":
            if fo.Registre(ctx.racine).nouveaux_fichiers():
                return taches.lancer(ctx, "Lecture des nouvelles factures", lambda j: _lire_nouvelles(ctx, j), retour)
            message = _message("Aucune nouvelle facture.")
        elif action == "Fournisseurs et articles Sage":
            return taches.lancer(ctx, "Fournisseurs et articles de Sage", lambda j: _relire_sage(ctx, j), retour)
        elif action == "Lire le courriel":
            from ..factures_courriel import configuree

            if not configuree(ctx.config):
                message = _message(erreur="Configurez d'abord la boîte de courriel (« Administration > Courriel », "
                                          "carte « Avis de paiement »).")
            else:
                def lire(journal):
                    from ..factures_courriel import recuperer

                    copies = recuperer(ctx.racine, ctx.config)
                    if not copies:
                        return ["Aucune nouvelle facture dans le courriel."]
                    return [f"{len(copies)} pièce(s) jointe(s) copiée(s)."] + _lire_nouvelles(ctx, journal)

                return taches.lancer(ctx, "Factures reçues par courriel", lire, retour)
        elif action == "Importer les factures cochées":  # demande du propriétaire du 2026-11-05
            if rang is not None:
                _enregistrer(ctx, rang, ligne)
            toutes_f = fo.Registre(ctx.racine).factures
            rangs = {int(x) for x in ctx.req.champs("coche") if x.isdigit() and int(x) < len(toutes_f)}
            choisies = [toutes_f[x] for x in sorted(rangs)]
            pretes = [x for x in choisies if x.etat == fo.PRETE]
            if not choisies:
                message = _message(erreur="Cochez les factures à importer (case de la 1re colonne).")
            elif not pretes:
                message = _message(erreur="Aucune facture cochée n'est « Prête à importer ».")
            else:
                return taches.lancer(ctx, f"Import de {len(pretes)} facture(s) fournisseurs cochée(s)",
                                     _importer(ctx, pretes, clover), retour, sage=True)
        elif action == "Importer toutes les factures prêtes":
            if rang is not None:
                _enregistrer(ctx, rang, ligne)
            pretes = [f for f in fo.Registre(ctx.racine).factures if f.etat == fo.PRETE]
            if not pretes:
                message = _message(erreur="Aucune facture « Prête à importer ». Reliez tous les articles et enregistrez "
                                          "la facture pour qu'elle le devienne.")
            else:
                return taches.lancer(ctx, f"Import de {len(pretes)} facture(s) fournisseurs",
                                     _importer(ctx, pretes, clover), retour, sage=True)
        elif rang is not None:
            if action in ("Écarter", "Supprimer", "Supprimer la ligne") and not action_permise(ctx, "Supprimer"):
                message = _message(erreur="Votre profil n'a pas le droit « Supprimer ».")
            elif action in ("Écarter", "Supprimer"):
                with ctx.app.ecriture:
                    r = fo.Registre(ctx.racine)
                    try:
                        f = r.factures[rang]
                    except IndexError:
                        f = None
                    if f is not None:
                        (r.ecarter if action == "Écarter" else r.supprimer)(f)
                        r.enregistrer()
                message = _message(f"Facture « {f.fichier if f else ''} » "
                                   + ("écartée (fichier rangé dans « ecartees »)." if action == "Écarter" else
                                      "supprimée de la liste (fichier rangé dans « supprimees »)."))
                rang = ligne = None
            elif action in ("Bon de réception", "Facture avec prix"):  # impressions (2026-11-05)
                from ..impression_fournisseur import bon_reception, facture_complete

                _enregistrer(ctx, rang, ligne)
                f = fo.Registre(ctx.racine).factures[rang]
                chemin = (bon_reception if action == "Bon de réception" else facture_complete)(ctx.racine, f)
                return Reponse(corps=chemin.read_bytes(), type="application/pdf",
                               entetes={"Content-Disposition": f"inline; filename=\"{chemin.name}\""})
            elif action == "Refaire la mise à jour Clover":
                f = fo.Registre(ctx.racine).factures[rang]
                if f.etat != fo.IMPORTEE:
                    message = _message(erreur="La facture n'est pas encore importée dans Sage.")
                else:
                    def refaire(journal, f=f):
                        from ..import_achats import mettre_a_jour_clover

                        journal("Stock et coût Clover des lignes pas encore faites…")
                        return [f"{x} : {t}" for x, t in mettre_a_jour_clover(ctx.racine, ctx.config, [f],
                                                                             {f.fichier: ""}).items()]

                    return taches.lancer(ctx, f"Clover de la facture {f.numero}", refaire, retour)
            else:
                try:
                    ligne, texte = _enregistrer(ctx, rang, ligne, action)
                    message = texte
                    if action == "Importer cette facture":
                        f = fo.Registre(ctx.racine).factures[rang]
                        if f.etat != fo.PRETE:
                            raise ValueError(f"Cette facture n'est pas prête à importer (état : {f.etat}). Reliez tous "
                                             "ses articles et vérifiez les totaux, puis enregistrez-la.")
                        return taches.lancer(ctx, f"Import de la facture {f.numero}", _importer(ctx, [f], clover),
                                             retour, sage=True)
                except (ValueError, InvalidOperation) as erreur:
                    message = _message(erreur=str(erreur) or "Nombre invalide.")
    registre = fo.Registre(ctx.racine)
    noms, articles = _listes(ctx.racine)
    lien = e(urlencode({"filtre": filtre, **({"fichier": q_fichier} if q_fichier else {}),
                        **({"fournisseur": q_fournisseur} if q_fournisseur else {}),
                        **({"numero": q_numero} if q_numero else {})}))
    cocher_pretes = bool(ctx.req.query.get("cocher"))
    lignes, classes = [], []
    ordre = []  # factures de la liste filtrée, dans l'ordre affiché (liste déroulante de la saisie)

    def nom_fournisseur(f):
        return f.fournisseur_sage or f"({f.fournisseur_lu or '?'})"

    for n, f in sorted(enumerate(registre.factures), key=lambda x: (x[1].date_facture or "", x[0]), reverse=True):
        if filtre != "Toutes" and f.etat != filtre:
            continue
        if q_fichier and _simple(q_fichier) not in _simple(f.fichier):
            continue
        if q_fournisseur and nom_fournisseur(f) != q_fournisseur:
            continue
        if q_numero and _simple(q_numero) not in _simple(f.numero):
            continue
        ordre.append(n)
        coche = ("<input type='checkbox' name='coche' value='{n}' form='barre-factures' aria-label='Cocher'"
                 + (" checked" if f.etat == fo.PRETE and cocher_pretes else "") + ">").format(n=n)
        lignes.append([coche, f"<a href='?{lien}&amp;i={n}'{' data-choisie' if n == rang else ''}>{e(f.fichier)}</a>"
                       + (" ◀" if n == rang else ""),
                       e(f.fournisseur_sage or f"({f.fournisseur_lu or '?'})"), e(f.numero), e(f.date_facture),
                       argent(f.total) if f.total is not None else "", e(f.depot or "Emplacement par défaut"),
                       "✔" if getattr(f, "maj_clover", True) else "—",
                       e(f.etat) + (" (note de crédit)" if getattr(f, "note_credit", False) else "")])
        classes.append(COULEURS.get(f.etat, "termine"))
    compte = {x: sum(1 for f in registre.factures if f.etat == x) for x in fo.ETATS}
    resume = (f"{len(registre.factures)} facture(s) — à saisir : {compte[fo.A_SAISIR]}, à vérifier : "
              f"{compte[fo.A_VERIFIER]}, prêtes : {compte[fo.PRETE]}, importées (archivées) : "
              f"{fo.nombre_archives(ctx.racine)}"
              + ("" if noms else "   •   liste des fournisseurs Sage absente : cliquez sur « Fournisseurs et "
                                 "articles Sage »"))
    options = "".join(f"<option{' selected' if x == filtre else ''}>{e(x)}</option>" for x in ["Toutes"] + fo.ETATS)
    barre = (f"<form method='post' enctype='multipart/form-data' class='barre-onglet' id='barre-factures'>{csrf(ctx)}"
             f"<input type='hidden' name='filtre' value='{e(filtre)}'>{garder}<input type='hidden' name='onglet' "
             "value='liste'>"
             + (f"<input type='hidden' name='i' value='{rang}'>" if rang is not None else "")
             + "<input type='file' name='facture' accept='.pdf,image/*' capture='environment'><button name='action' "
               "value='Ajouter des factures'>➕ Ajouter des factures…</button><a class='ouvrir plein' "
               "href='/photo-facture'>📷 Photographier une facture</a><button class='second' name='action' "
               "value='Lire le courriel'>📧 Lire le courriel</button><button class='second' name='action' "
               "value='Actualiser'>⟳ Actualiser</button><button class='second' name='action' value='Fournisseurs et "
               f"articles Sage'>📒 Fournisseurs et articles Sage</button><a class='ouvrir' href='/dossier-factures'>📂 "
               "Dossier des factures</a><button "
               "class='second a-droite' name='action' value='Importer les factures cochées'>☑ Importer les factures cochées"
               "</button><button class='accent' name='action' value='Importer toutes les factures prêtes'>📤 Importer "
               "toutes les factures prêtes</button></form>"
             f"<form method='get' class='barre-onglet'><div><label>Afficher :</label><select name='filtre'>{options}"
             "</select></div><button class='second sans-js'>Afficher</button>"
             # filtres de la liste pendant la frappe (nom du fichier, fournisseur)
             # (liste déroulante des fournisseurs de la liste, noms de fichiers proposés pendant la frappe)
             "<div class='filtres-tableau'><label>Fichier :</label><input type='search' data-filtre='liste-factures' "
             f"data-colonnes='1' placeholder='nom du fichier' list='fichiers-factures' name='fichier' "
             f"value='{e(q_fichier)}' autocomplete='off'>"
             + "<datalist id='fichiers-factures'>" + "".join(
                 f"<option value='{e(f.fichier)}'>" for f in registre.factures) + "</datalist>"
             + "<label>Fournisseur :</label><select name='fournisseur' autocomplete='off'>"
               "<option value=''>Tous les fournisseurs</option>" + "".join(
                 f"<option{' selected' if nom == q_fournisseur else ''}>{e(nom)}</option>" for nom in sorted(
                     {nom_fournisseur(f) for f in registre.factures}, key=str.casefold)) + "</select>"
             + "<label>N° de facture :</label><input type='search' data-filtre='liste-factures' data-colonnes='3' "
               f"placeholder='numéro' name='numero' value='{e(q_numero)}' size='12' autocomplete='off'></div>"
             + ("<a class='ouvrir' href='?" + lien + "'>☐ Tout décocher</a>" if cocher_pretes else
                "<a class='ouvrir' href='?" + lien + "&amp;cocher=1'>☑ Cocher les factures prêtes</a>") + "</form>")
    # deux onglets (demande du propriétaire du 2026-11-09 : « la fenêtre est trop chargée ; la liste des factures
    # dans une table à part et la saisie dans une autre fenêtre ; avec un menu déroulant on sélectionne la facture à
    # traiter ; la saisie s'enregistre automatiquement ») : un clic sur une facture ouvre l'onglet de saisie
    valide = rang is not None and rang < len(registre.factures)
    saisie = valide and (ctx.req.query.get("onglet") or ctx.req.champ("onglet") or "saisie") != "liste"
    if not valide:
        rang = None
    nav = ("<nav class='onglets'>"
           f"<a class='onglet{'' if saisie else ' actif'}' href='?{lien}"
           + (f"&amp;i={rang}&amp;onglet=liste" if rang is not None else "") + "'>📋 Liste des factures</a>"
           f"<a class='onglet{' actif' if saisie else ''}' href='?{lien}"
           + (f"&amp;i={rang}" if rang is not None else (f"&amp;i={ordre[0]}" if ordre else "")) + "'>✏ Saisie de la "
           "facture</a></nav>")
    corps = ("<p class='sous-titre'>🧾 Factures fournisseurs — lecture des factures, articles Sage et import dans Sage"
             "</p>" + message + nav)
    if not saisie:
        corps += (barre + f"<p class='note'>{e(resume)}</p>"
                  + "<div class='zone-liste-factures liste-seule' id='liste-factures' "
                    "data-garder='fichier,fournisseur,numero'>"
                  + tableau_section(Section("Factures", ["", "Fichier", "Fournisseur Sage", "N°", "Date", "Total", "Dépôt",
                                                        "Clover", "État"], lignes, classes=classes, html=set(range(9))))
                  + "</div><p class='note'>Cliquez sur une facture pour l'ouvrir dans « Saisie de la facture ». Sur "
                    "téléphone, « Ajouter des factures » ouvre l'appareil photo.</p>")
        return Reponse(corps=page(ctx, "Factures fournisseurs", corps))
    if ctx.req.methode == "GET":
        _proposer(ctx, rang, noms, articles)  # articles Sage proposés aux lignes pas encore reliées
        registre = fo.Registre(ctx.racine)
    if rang not in ordre:  # facture hors du filtre : gardée en tête de la liste déroulante
        ordre.insert(0, rang)
    position = ordre.index(rang)

    def libelle(n):
        f = registre.factures[n]
        return "  ·  ".join(v for v in (f.numero or "?", nom_fournisseur(f), f.date_facture or "", f.etat, f.fichier)
                            if v)

    caches = (f"<input type='hidden' name='filtre' value='{e(filtre)}'>"
              + "".join(f"<input type='hidden' name='{k}' value='{e(v)}'>" for k, v in
                        (("fichier", q_fichier), ("fournisseur", q_fournisseur), ("numero", q_numero)) if v))
    voisines = "".join(
        f"<a class='ouvrir' href='?{lien}&amp;i={ordre[position + pas]}'>{signe}</a>" if 0 <= position + pas < len(ordre)
        else f"<span class='ouvrir inactif'>{signe}</span>" for pas, signe in ((-1, "◀"), (1, "▶")))
    corps += (f"<form method='get' class='barre-onglet choix-facture'>{caches}<div class='large'><label>Facture à "
              "traiter :</label><select name='i'>" + "".join(
                  f"<option value='{n}'{' selected' if n == rang else ''}>{e(libelle(n))}</option>" for n in ordre)
              + f"</select></div><button class='second sans-js'>Ouvrir</button>{voisines}"
                "<span class='note'>💾 enregistrée automatiquement à chaque action</span></form>"
              + _detail(ctx, registre.factures[rang], rang, ligne, filtre, noms, articles, clover, garder))
    return Reponse(corps=page(ctx, "Factures fournisseurs", corps))


def _simple(texte: str) -> str:
    import unicodedata

    return "".join(c for c in unicodedata.normalize("NFD", texte or "") if not unicodedata.combining(c)).casefold()


def _options_depots(ctx: Contexte, actuel: str) -> str:
    from ..depots import est_defaut, noms

    choisi = "" if est_defaut(actuel) else actuel
    return "".join(f"<option{' selected' if (n == choisi or (not choisi and est_defaut(n))) else ''}>{e(n)}</option>"
                   for n in noms(ctx.config))


def _detail_vide() -> str:
    """Bas de la page Windows avant le choix d'une facture : mêmes cadres, champs et boutons, vides et inactifs."""
    from .consultations import Section, tableau_section

    def champ(libelle, taille=14):
        return f"<div><label>{e(libelle)}</label><input size='{taille}' disabled></div>"

    return ("<div class='carte'><div class='barre-onglet'>" + champ("Fournisseur Sage", 30) + champ("N° de facture")
            + champ("Date", 11) + champ("Dépôt", 18) + "<button class='accent' disabled>Enregistrer la facture</button><button "
            "class='danger' disabled>🗑 Écarter</button></div><div class='barre-onglet'>" + champ("Sous-total", 10)
            + champ("TPS", 10) + champ("TVQ", 10) + champ("Total", 10) + "<button disabled>📤 Importer cette facture"
            "</button></div>"
            + tableau_section(Section("Lignes", ["Code", "Désignation du fournisseur", "Qté", "Prix fournisseur",
                                                 "Montant", "N° Sage", "Désignation Sage", "Qté Sage", "Prix Sage",
                                                 "Facteur"], []))
            + "<div class='barre-onglet'>" + champ("Code", 10) + champ("Désignation", 34)
            + "<div><label>Taxes</label><select disabled><option>Aucune</option></select></div></div>"
            "<div class='barre-onglet'>" + champ("Qté", 6) + champ("Prix fournisseur", 8) + champ("Montant", 8)
            + champ("Qté Sage", 8) + champ("Facteur", 6) + "<button class='second' disabled>Appliquer</button><button "
            "class='second' disabled>➕</button><button class='danger' disabled>🗑</button></div>"
            "<div class='fiche-bas'><div class='factures'><label>Article Sage :</label><input size='50' disabled></div>"
            "<div class='boutons-colonne'><button disabled>✔ Relier et confirmer</button><button class='second' "
            "disabled>Confirmer la proposition</button><button class='second' disabled>🆕 Créer l'article</button>"
            "</div></div></div>")


def _decimal(texte: str, defaut: str = "0") -> Decimal:
    texte = (texte or "").replace(",", ".").replace("$", "").replace(" ", "").replace(" ", "").strip()
    return Decimal(texte or defaut)


def _entier(texte):
    try:
        return int(texte)
    except (TypeError, ValueError):
        return None


def _enregistrer(ctx: Contexte, rang: int, ligne, action: str = "Enregistrer la facture"):
    """En-tête et ligne de la carte reportés sur la facture, puis l'action de la ligne (Appliquer, ➕, 🗑, Relier,
    Confirmer la proposition), mémoire du fournisseur, état recalculé et enregistrement (comme sauvegarder_auto).
    Rend (ligne affichée ensuite, message)."""
    from .. import fournisseurs as fo
    from ..factures_fournisseurs import facteur_propose
    from ..fournisseurs import conflit_format_achat, facteur_achat

    noms, articles = _listes(ctx.racine)
    texte, relie_par_saisie = "", False
    with ctx.app.ecriture:
        r = fo.Registre(ctx.racine)
        f = r.factures[rang]
        f.fournisseur_sage = ctx.req.champ("fournisseur").strip()
        f.numero, f.date_facture = ctx.req.champ("numero").strip(), ctx.req.champ("date").strip()
        if "maj_clover_vu" in ctx.req.form:  # case de la facture (absente du formulaire quand elle est décochée)
            f.maj_clover = ctx.req.champ("maj_clover") == "1"
        if "depot" in ctx.req.form:  # dépôt qui reçoit la marchandise (transfert après l'import)
            from ..depots import est_defaut

            f.depot = "" if est_defaut(ctx.req.champ("depot")) else ctx.req.champ("depot").strip()
        f.sous_total = _decimal(ctx.req.champ("sous_total")) if ctx.req.champ("sous_total").strip() else None
        f.tps, f.tvq = _decimal(ctx.req.champ("tps")), _decimal(ctx.req.champ("tvq"))
        f.total = _decimal(ctx.req.champ("total")) if ctx.req.champ("total").strip() else None
        if ligne is not None and ligne < len(f.lignes) and ctx.req.champ("l_quantite") != "":
            l = f.lignes[ligne]
            l.code, l.description = ctx.req.champ("l_code").strip(), ctx.req.champ("l_description").strip()
            l.quantite, l.prix = _decimal(ctx.req.champ("l_quantite")), _decimal(ctx.req.champ("l_prix"))
            l.facteur = _decimal(ctx.req.champ("l_facteur"), "1")
            if l.facteur <= 0:
                raise ValueError("Le facteur doit être supérieur à 0.")
            l.montant = (l.quantite * l.prix).quantize(Decimal("0.01"))  # Montant = Qté × Prix fournisseur
            taxe = ctx.req.champ("l_taxe")
            l.taxe, l.taxable = (taxe, True) if taxe in ("GQ", "G", "Q") else ("", False)
            if "l_numero_sage" in ctx.req.form:  # n° / désignation Sage tapés directement (assistant de saisie)
                texte, relie_par_saisie = _article_tape(ctx, l, articles, action)
        # touche Entrée (demande du propriétaire du 2026-11-08) : la ligne en cours est validée (reportée ci-dessus),
        # puis la ligne suivante ; à la dernière ligne, une nouvelle ligne est créée. Sans ligne : facture enregistrée.
        if action == "Entrée" and ligne is not None and ligne < len(f.lignes):
            if ligne + 1 < len(f.lignes):
                ligne += 1
            else:
                action = "➕"
        if action == "➕":
            f.lignes.append(fo.Ligne("", Decimal(1), Decimal(0), Decimal(0)))
            if f.etat == fo.A_SAISIR:
                f.etat = fo.A_VERIFIER
            ligne = len(f.lignes) - 1
        elif action == "Supprimer la ligne" and ligne is not None and ligne < len(f.lignes):
            texte = _message(f"Ligne « {f.lignes[ligne].description} » supprimée.")
            del f.lignes[ligne]
            ligne = None
        elif relie_par_saisie:
            ligne = _suivante(f, ligne) if action == "Relier et confirmer" else ligne
        elif action in ("Relier et confirmer", "Relier quand même") and ligne is not None and ligne < len(f.lignes):
            l = f.lignes[ligne]
            numero = ctx.req.champ("article")
            coche = next((x for x in articles if x.numero == numero), None)
            # l'article choisi dans l'assistant de saisie passe avant la liste SEULEMENT s'il vient d'être tapé
            # (constat du 2026-11-10 : la recherche de la ligne d'avant, restée dans le champ, reliait la ligne
            # Fanta à l'article Chip RealTaste au lieu de l'article coché)
            tape = ctx.req.champ("recherche").strip() != ctx.req.champ("recherche_affichee").strip()
            choisi = article_choisi(ctx.req.champ("recherche"), articles)
            a = (choisi or coche) if tape else (coche or choisi)
            if a is None:
                texte = _message(erreur="Choisissez une ligne de la facture, puis un article Sage dans la liste.")
            elif conflit_format_achat(l.description, a.description) and action != "Relier quand même":
                texte = (f"<p class='erreur'>Les formats semblent différents (« {e(l.description)} » / "
                         f"« {e(a.description)} »). Deux formats différents sont deux articles différents. "
                         f"<button form='facture' name='action' value='Relier quand même'>Relier quand même "
                         "(conditionnement différent)</button></p>")
            else:
                if not l.description:  # ligne ajoutée à la main : désignation de l'article Sage
                    l.description = a.description
                l.numero_sage, l.description_sage, l.confirme = a.numero, a.description, True
                if l.facteur == 1 or l.facteur == (facteur_propose(l.description) or 1):  # pas changé à la main
                    l.facteur = facteur_achat(l.description, a.description) or Decimal(1)
                texte = _message(f"« {l.description} » relié à {a.numero} — {a.description}.")
                ligne = _suivante(f, ligne)
        elif action == "Confirmer la proposition" and ligne is not None and ligne < len(f.lignes):
            if f.lignes[ligne].numero_sage:
                f.lignes[ligne].confirme = True
                texte = _message(f"Proposition confirmée : {f.lignes[ligne].numero_sage}.")
                ligne = _suivante(f, ligne)
            else:
                texte = _message(erreur="Cette ligne n'a pas encore d'article Sage proposé : choisissez-en un.")
        elif action == "Confirmer toutes les propositions":
            faites = 0
            for x in f.lignes:
                if x.nature == "article" and x.numero_sage and not x.confirme \
                        and not conflit_format_achat(x.description, x.description_sage):
                    x.confirme = True
                    faites += 1
            texte = _message(f"{faites} proposition(s) confirmée(s).")
            ligne = _suivante(f, -1)
        # note de crédit (règle du propriétaire du 2026-11-11) : quantités et montants en négatif, même saisis en positif
        f.signer(credit=ctx.req.champ("note_credit") == "1" if "note_credit_vu" in ctx.req.form else None)
        memoire = fo.MemoireCorrespondance(ctx.racine)
        if f.fournisseur_sage and f.fournisseur_lu and (not noms or f.fournisseur_sage in noms):
            memoire.retenir_fournisseur(f.fournisseur_lu, f.fournisseur_sage)
        for x in f.lignes:
            if x.confirme and x.numero_sage and f.fournisseur_sage:
                memoire.retenir_article(f.fournisseur_sage, x)
        f.etat = fo.etat_apres_controle(f, f.controles(set(noms) or None))
        memoire.enregistrer()
        r.enregistrer()
    if not texte and (action == "Enregistrer la facture" or (action == "Entrée" and ligne is None)):
        texte = _message("Facture enregistrée.")
        if f.fournisseur_sage and noms and f.fournisseur_sage not in noms:
            texte += _message(erreur="Choisissez le fournisseur dans la liste des fournisseurs Sage.")
    return ligne, texte


def _article_tape(ctx: Contexte, l, articles, action: str):
    """N° Sage ou désignation Sage tapés dans la carte de la ligne (demande du propriétaire du 2026-11-10) : l'article
    trouvé est relié et confirmé (formats différents : « Relier quand même ») ; les deux champs vidés = lien retiré.
    Rend (message, relié)."""
    from ..correspondance import normaliser
    from ..factures_fournisseurs import facteur_propose
    from ..fournisseurs import article_saisi, conflit_format_achat, facteur_achat

    numero = ctx.req.champ("l_numero_sage").split(SEPARATEUR)[0].strip()
    description = ctx.req.champ("l_description_sage").strip()
    if not numero and not description:
        if l.numero_sage:
            ancien = l.numero_sage
            l.numero_sage, l.description_sage, l.confirme = "", "", False
            return _message(f"Lien avec {ancien} retiré."), False
        return "", False
    numero_change = numero.upper() != (l.numero_sage or "").strip().upper()
    description_change = normaliser(description) != normaliser(l.description_sage or "")
    if not numero_change and not description_change:
        return "", False
    a = (article_saisi(numero, "", articles) if numero_change else None) or (
        article_saisi("", description, articles) if description or not numero_change else None)
    if a is None:
        return _message(erreur=f"Article Sage introuvable (« {numero or description} ») : choisissez-le dans la liste "
                               "proposée pendant la frappe."), False
    if a.numero == l.numero_sage and l.confirme:
        return "", False
    if conflit_format_achat(l.description, a.description) and action != "Relier quand même":
        return (f"<p class='erreur'>Les formats semblent différents (« {e(l.description)} » / « {e(a.description)} »). "
                f"Deux formats différents sont deux articles différents. <button form='facture' name='action' "
                f"value='Relier quand même'>Relier quand même (conditionnement différent)</button></p>"), False
    if not l.description:
        l.description = a.description
    l.numero_sage, l.description_sage, l.confirme = a.numero, a.description, True
    if l.facteur == 1 or l.facteur == (facteur_propose(l.description) or 1):  # pas changé à la main
        l.facteur = facteur_achat(l.description, a.description) or Decimal(1)
    return _message(f"« {l.description} » relié à {a.numero} — {a.description}."), True


def _proposer(ctx: Contexte, rang: int, noms, articles) -> None:
    """À l'ouverture d'une facture : mémoire du fournisseur puis article Sage ressemblant de même taille
    d'unité proposé à chaque ligne pas encore reliée (fournisseurs.completer) ; enregistré s'il y a du nouveau."""
    from .. import fournisseurs as fo

    if not articles:
        return
    with ctx.app.ecriture:
        r = fo.Registre(ctx.racine)
        if rang >= len(r.factures):
            return
        f = r.factures[rang]
        if f.etat == fo.IMPORTEE:
            return
        avant = [(l.numero_sage, l.confirme, l.facteur) for l in f.lignes]
        fo.completer(f, fo.MemoireCorrespondance(ctx.racine), noms, articles)
        if [(l.numero_sage, l.confirme, l.facteur) for l in f.lignes] != avant:
            f.etat = fo.etat_apres_controle(f, f.controles(set(noms) or None))
            r.enregistrer()


def _suivante(f, depuis: int):
    """Ligne d'article suivante pas encore confirmée (après `depuis`, puis depuis le début) ; None s'il n'y en a
    plus : le traitement passe de lui-même à la ligne à relier suivante."""
    n = len(f.lignes)
    for k in list(range(depuis + 1, n)) + list(range(0, depuis + 1)):
        l = f.lignes[k]
        if l.nature == "article" and not l.confirme:
            return k
    return None


def _detail(ctx: Contexte, f, rang: int, ligne, filtre: str, noms, articles, clover: bool, garder: str = "") -> str:
    """Bas de la page Windows : en-tête, montants, contrôle, lignes, carte d'édition de la ligne choisie."""
    from .. import taxes as tx
    from .consultations import Section, tableau_section

    def v(x) -> str:
        return "" if x is None else f"{x:.2f}"

    liste_f = "<datalist id='fournisseurs'>" + "".join(f"<option value='{e(n)}'>" for n in noms) + "</datalist>"
    problemes = f.controles(set(noms) or None)
    controle = ("<p class='erreur-texte'>⚠ " + e(" ; ".join(problemes[:6]) + (" …" if len(problemes) > 6 else ""))
                + "</p>" if problemes else
                "<p class='ok-texte'>✔ Facture cohérente et entièrement reliée : prête à importer.</p>")
    lu = (f"Lu sur la facture : {f.fournisseur_lu or '?'}   •   lecture : {f.modele}"
          + (f"   •   {' ; '.join(f.remarques)}" if f.remarques else ""))
    # 1er bouton du formulaire = celui de la touche Entrée (avant : « Supprimer », la facture était supprimée)
    html = (f"<form method='post' id='facture' class='carte'>{csrf(ctx)}<button class='bouton-entree' name='action' "
            "value='Entrée' data-entree tabindex='-1' aria-hidden='true'>Valider</button><input type='hidden' name='i' "
            f"value='{rang}'>"
            f"<input type='hidden' name='filtre' value='{e(filtre)}'>{garder}"
            + (f"<input type='hidden' name='l' value='{ligne}'>" if ligne is not None else "")
            + f"<input type='hidden' name='clover' value='{'1' if clover else '0'}'>"
            f"<div class='ligne'><div><label>Fournisseur Sage</label><input name='fournisseur' list='fournisseurs' "
            f"value='{e(f.fournisseur_sage)}' size='34'>{liste_f}</div><div><label>N° de facture</label><input "
            f"name='numero' value='{e(f.numero)}' size='12'></div><div><label>Date</label><input type='date' name='date' "
            f"value='{e(f.date_facture)}'></div><div><label>Dépôt</label><select name='depot'>{_options_depots(ctx, f.depot)}"
            "</select></div><div><input type='hidden' name='maj_clover_vu' value='1'><label><input type='checkbox' "
            f"name='maj_clover' value='1'{' checked' if getattr(f, 'maj_clover', True) else ''}> Mettre à jour le "
            "stock Clover</label></div><div><input type='hidden' name='note_credit_vu' value='1'><label><input "
            f"type='checkbox' name='note_credit' value='1'{' checked' if getattr(f, 'note_credit', False) else ''}> "
            "Note de crédit</label></div><div class='a-droite boutons'><button class='danger' name='action' "
            f"value='Supprimer'>✖ Supprimer</button><a class='ouvrir' href='/facture-fichier?i={rang}' "
            "target='_blank'>👁 Voir la facture</a><button class='danger' name='action' value='Écarter'>🗑 Écarter"
            f"</button></div></div><p class='note'>{e(lu)}</p><div class='ligne'>"
            + "".join(f"<div><label>{lib}</label><input name='{cle}' value='{val}' size='10'></div>"
                      for cle, lib, val in (("sous_total", "Sous-total", v(f.sous_total)), ("tps", "TPS", v(f.tps)),
                                            ("tvq", "TVQ", v(f.tvq)), ("total", "Total", v(f.total))))
            + "<div class='a-droite boutons'><button class='accent' name='action' value='Enregistrer la facture'>💾 "
              "Enregistrer la facture</button><button name='action' value='Importer cette facture'>📤 Importer cette "
              "facture</button>"
            + ("<button class='second' name='action' value='Refaire la mise à jour Clover'>🔁 Refaire la mise à jour "
               "Clover</button>" if f.etat == "Importée" else "")
            + "<button class='second' name='action' value='Bon de réception' formtarget='_blank'>🖨 Bon de réception"
              "</button><button class='second' name='action' value='Facture avec prix' formtarget='_blank'>🖨 Facture "
              "(avec prix)</button>"
            + f"</div></div>{controle}")
    rangees, classes = [], []
    for k, l in enumerate(f.lignes):
        quantite, prix_sage = l.en_sage()
        etat = "Confirmée" if l.confirme else ("Proposée" if l.numero_sage else "À relier")
        if l.nature != "article":
            etat = "Frais"
        rangees.append([f"<a href='?filtre={e(filtre)}&amp;i={rang}&amp;l={k}'>{e(l.code) or '·'}</a>"
                        + (" ◀" if k == ligne else ""), e(l.description), f"{l.quantite:g}", f"{l.prix:.2f}",
                        f"{l.montant:.2f}", e(l.numero_sage), e(l.description_sage), f"{quantite:g}", f"{prix_sage:.4f}",
                        f"{l.facteur:g}", etat])
        classes.append("" if l.confirme or l.nature != "article" else "etat-a-saisir")
    html += tableau_section(Section("Lignes de la facture", COLONNES_LIGNES, rangees, classes=classes,
                                    html=set(range(11)),
                                    note=f"Somme des lignes : {argent(f.somme_lignes)}. Cliquez sur une ligne pour la "
                                         "corriger et la relier à un article Sage."))
    a_confirmer = sum(1 for x in f.lignes if x.nature == "article" and x.numero_sage and not x.confirme)
    a_relier = sum(1 for x in f.lignes if x.nature == "article" and not x.numero_sage)
    html += ("<div class='boutons'>"
             + (f"<button class='accent' name='action' value='Confirmer toutes les propositions'>✔ Confirmer les "
                f"{a_confirmer} proposition(s)</button>" if a_confirmer else "")
             + (f"<a class='ouvrir' href='?filtre={e(filtre)}&amp;i={rang}&amp;l={_suivante(f, -1)}'>➡ Ligne suivante à "
                f"relier ({a_relier + a_confirmer})</a>" if a_relier + a_confirmer and _suivante(f, -1) is not None else "")
             + "</div>")
    if ligne is None or ligne >= len(f.lignes):
        return html + ("<div class='boutons'><button name='action' value='➕'>➕ Ajouter une ligne</button></div>"
                       "</form>")
    l = f.lignes[ligne]
    quantite, prix_sage = l.en_sage()
    taxe = tx.code(l)
    choix_taxe = "".join(f"<option value='{c}'{' selected' if c == taxe else ''}>{e(lib)}</option>"
                         for c, lib in tx.CHOIX.items())
    # recherche tapée gardée pour la même ligne seulement : une autre ligne repart de sa propre désignation
    meme_ligne = ctx.req.champ("l") == str(ligne)
    recherche = ctx.req.query.get("recherche") if "recherche" in ctx.req.query else (
        ctx.req.champ("recherche") if ctx.req.champ("recherche") and meme_ligne else l.description)
    resultats = _chercher(recherche, articles, l)
    radios = "".join(f"<label class='facture'><input type='radio' name='article' value='{e(a.numero)}'"
                     f"{' checked' if n == 0 else ''}> <code>{e(a.numero):<16} {e(a.description)}{e(alerte)}</code>"
                     "</label>" for n, (a, alerte) in enumerate(resultats))
    lien_creer = (f"/creer-article?nom={quote(l.description)}&amp;cout={prix_sage:.4f}")
    html += (f"<div class='carte edition'><div class='ligne'><div><label>Code</label><input name='l_code' "
             f"value='{e(l.code)}' size='10'></div><div class='large'><label>Désignation</label><input "
             f"name='l_description' value='{e(l.description)}' size='40'></div><div><label>Taxes</label><select "
             f"name='l_taxe'>{choix_taxe}</select></div></div><div class='ligne'><div><label>Qté</label><input "
             f"name='l_quantite' value='{l.quantite:g}' size='7'></div><div><label>Prix fournisseur</label><input "
             f"name='l_prix' value='{l.prix}' size='9'></div><div><label>Montant</label><span class='calcule'>"
             f"{l.montant:.2f}</span></div><div><label>Qté Sage</label><span class='calcule'>{quantite:g}</span></div>"
             f"<div><label>Facteur</label><input name='l_facteur' value='{l.facteur:g}' size='7'></div><button "
             "class='second' name='action' value='Appliquer'>Appliquer</button><button class='second' name='action' "
             "value='➕'>➕</button><button class='danger' name='action' value='Supprimer la ligne'>🗑</button></div>"
             "<div class='ligne'><div><label>N° Sage</label><input name='l_numero_sage' list='sage-numeros' "
             f"value='{e(l.numero_sage)}' size='14' data-paire='l_description_sage' autocomplete='off' "
             "placeholder='Tapez le n°'></div><div class='large'><label>Désignation Sage</label><input "
             f"name='l_description_sage' list='sage-designations' value='{e(l.description_sage)}' size='40' "
             "data-paire='l_numero_sage' autocomplete='off' placeholder='Tapez quelques lettres de la désignation'>"
             "</div></div>" + assistants_saisie(articles) + "<div class='fiche-bas'><div class='factures' data-sans-position>"
             "<div class='ligne'><div class='large'><label>Article Sage :</label><input type='hidden' "
             f"name='recherche_affichee' value='{e(recherche)}'><input name='recherche' value='{e(recherche)}' "
             "size='40' list='articles-sage' "
             "placeholder='Tapez le n° ou quelques lettres : les articles Sage apparaissent'></div><button "
             "class='second' name='action' value='Chercher'>Chercher</button></div>" + assistant_articles(articles)
             + (radios or ("<p class='note'>Tapez quelques lettres : choisissez l'article proposé, puis « Relier et "
                           "confirmer ».</p>" if articles else
                           "<p class='erreur-texte'>Liste des articles Sage absente : cliquez sur « Fournisseurs et "
                           "articles Sage ».</p>"))
             + "</div><div class='boutons-colonne'><button name='action' value='Relier et confirmer'>✔ Relier et "
               "confirmer</button><button class='second' name='action' value='Confirmer la proposition'>Confirmer la "
               f"proposition</button><a class='ouvrir' href='{lien_creer}'>🆕 Créer l'article</a><p class='ok-texte'>"
               f"Dans Sage : {quantite:g} × {prix_sage:.4f} $ = {l.montant:.2f} $ (prix Sage = montant / quantité "
               "Sage)</p></div></div></div></form>")
    return html


SEPARATEUR = " — "  # « C0001161 — Plantain jaune en lb » : choix de l'assistant de saisie


def article_choisi(texte: str, articles):
    """Article Sage désigné par le champ de l'assistant (« n° — description », ou le n° seul)."""
    numero = (texte or "").split(SEPARATEUR)[0].strip()
    return next((a for a in articles if a.numero == numero), None) if numero else None


def assistant_articles(articles) -> str:
    """Assistant de saisie (demande du propriétaire du 2026-11-08) : liste de suggestions du navigateur (datalist,
    sans script) qui propose les articles Sage pendant la frappe, par n° ou par description."""
    options = "".join(f"<option value='{e(a.numero + SEPARATEUR + a.description)}'>" for a in articles)
    return f"<datalist id='articles-sage'>{options}</datalist>"


def assistants_saisie(articles) -> str:
    """Listes des champs « N° Sage » et « Désignation Sage » de la carte de la ligne : la valeur est le n° (ou la
    désignation), le libellé l'autre moitié ; /filtres.js remplit l'autre champ (data-paire) au choix."""
    numeros = "".join(f"<option value='{e(a.numero)}' label='{e(a.description)}'>" for a in articles)
    vues, designations = set(), []
    for a in articles:
        if a.description not in vues:
            vues.add(a.description)
            designations.append(f"<option value='{e(a.description)}' label='{e(a.numero)}'>")
    return (f"<datalist id='sage-numeros'>{numeros}</datalist>"
            f"<datalist id='sage-designations'>{''.join(designations)}</datalist>")


def _chercher(texte: str, articles, l) -> list:
    """Comme PageFournisseurs.chercher_sage : 12 articles Sage les plus ressemblants, « (autre format) » signalé ;
    un article choisi dans l'assistant de saisie vient en premier."""
    from rapidfuzz import fuzz, process

    from ..correspondance import normaliser
    from ..fournisseurs import conflit_format_achat

    choisi = article_choisi(texte, articles)
    if choisi is not None:
        return [(choisi, "  (autre format)" if conflit_format_achat(l.description, choisi.description) else "")]
    texte = normaliser(texte or "")
    if not texte or not articles:
        return []
    normalises = [normaliser(f"{a.description} {a.numero}") for a in articles]
    trouves = [articles[i] for _, _, i in process.extract(texte, normalises, scorer=fuzz.token_set_ratio, limit=12)]
    # même taille d'unité d'abord, et l'article déjà proposé à la ligne en tête : il est coché d'office
    trouves.sort(key=lambda a: conflit_format_achat(l.description, a.description))
    propose = next((a for a in articles if a.numero == l.numero_sage), None) if l.numero_sage else None
    if propose is not None:
        trouves = [propose] + [a for a in trouves if a.numero != propose.numero]
    return [(a, "  (autre format)" if conflit_format_achat(l.description, a.description) else "") for a in trouves[:12]]


def facture(ctx: Contexte) -> Reponse:
    """Ancienne adresse de la fiche d'une facture : elle est maintenant sous la liste."""
    return redirection(f"/factures-fournisseurs?i={_entier(ctx.req.query.get('i')) or 0}")


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
    Fonction("/photo-facture", "Factures fournisseurs", "fournisseurs", photo_facture, "📷", "Fournisseur",
             menu=False),
    Fonction("/facture-fournisseur", "Factures fournisseurs", "fournisseurs", facture, "🧾", "Fournisseur", menu=False,
             page_entiere=True),
    Fonction("/facture-fichier", "Factures fournisseurs", "fournisseurs", fichier, "🧾", "Fournisseur", menu=False,
             page_entiere=True),
]
WEB = {"Factures fournisseurs": "/factures-fournisseurs"}
