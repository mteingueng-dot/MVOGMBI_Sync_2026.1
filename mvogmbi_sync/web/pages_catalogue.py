"""7e vague de l'application web (suite) : Articles Clover (liste, UGS qui ne sont pas des dates effacées),
correspondance Clover -> Sage (modifier une ligne, confirmer, mettre à jour), créer un article dans Clover et Sage,
inventaire Clover et Sage (fichier à remplir, saisie du fichier compté), inventaire tournant, transferts entre
magasins. Mêmes fonctions que les fenêtres Windows ; travaux longs en arrière-plan.
"""

from __future__ import annotations

import csv
import time
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .pages import Contexte, Fonction, argent, csrf, page, tableau
from .pages_compta import _message, action_permise
from .serveur import Reponse, echapper as e, redirection

LIMITE = 300


def _telecharger(chemin: Path, nom: str = "") -> Reponse:
    return Reponse(corps=Path(chemin).read_bytes(),
                   type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                   entetes={"Content-Disposition": f"attachment; filename=\"{nom or Path(chemin).name}\""})


# --------------------------------------------------------------------------------------------- articles Clover
def articles_clover(ctx: Contexte) -> Reponse:
    from ..cache_lectures import inventaire_clover
    from ..correspondance import normaliser
    from ..peremption import lire_date
    from . import taches

    try:
        articles = inventaire_clover(ctx.racine)
    except (Exception, SystemExit):  # noqa: BLE001
        return Reponse(corps=page(ctx, "Articles Clover", _message(erreur="Clover ne répond pas pour l'instant.")))
    message = ""
    if ctx.req.methode == "POST":
        choisis = [a for a in articles if a["id"] in set(ctx.req.champs("id"))]
        if not choisis:
            message = _message(erreur="Cochez au moins un article.")
        else:
            def effacer(journal):
                from ..points_vente import client

                c = client(ctx.racine)
                chemin = ctx.racine / "donnees" / "journal_ugs_effacees.csv"
                nouveau = not chemin.exists()
                erreurs = []
                with chemin.open("a", newline="", encoding="utf-8-sig") as f:
                    ecrivain = csv.writer(f, delimiter=";")
                    if nouveau:
                        ecrivain.writerow(["Date", "ID Clover", "Article", "UGS effacée"])
                    for a in choisis:
                        try:
                            c.regler_ugs(a["id"], "")
                            ecrivain.writerow([datetime.now().isoformat(timespec="seconds"), a["id"], a.get("name"),
                                               a.get("sku")])
                        except Exception as exc:  # noqa: BLE001
                            erreurs.append(f"{a.get('name')} : {exc}")
                return [f"{len(choisis) - len(erreurs)} UGS effacée(s) dans Clover."] + erreurs

            return taches.lancer(ctx, f"UGS effacées ({len(choisis)})", effacer, "/articles-clover")
    texte = normaliser(ctx.req.query.get("q", ""))
    categorie = ctx.req.query.get("categorie", "")
    stock = ctx.req.query.get("stock", "")
    ugs = ctx.req.query.get("ugs", "")

    def cat(a):
        return ", ".join(c.get("name", "") for c in (a.get("categories") or {}).get("elements", []))

    retenus = []
    for a in sorted(articles, key=lambda a: (a.get("name") or "").casefold()):
        quantite = (a.get("itemStock") or {}).get("quantity")
        if texte and texte not in normaliser(f"{a.get('name', '')} {a.get('code') or ''} {a.get('sku') or ''}"):
            continue
        if categorie and categorie.casefold() not in cat(a).casefold():
            continue
        if stock == "en stock" and not (quantite or 0) > 0 or stock == "sans stock" and (quantite or 0) > 0:
            continue
        if ugs and not (a.get("sku") and lire_date(a.get("sku")) is None):
            continue
        retenus.append(a)
    lignes = []
    for a in retenus[:LIMITE]:
        peremption = lire_date(a.get("sku") or "")
        case = (f"<input type='checkbox' name='id' value='{e(a['id'])}' checked>" if ugs else "")
        lignes.append([case, e(a["id"]), e(a.get("name", "")), argent(Decimal(int(a.get("price") or 0)) / 100),
                       e(a.get("priceType", "")), e(a.get("code") or ""), e(peremption.isoformat() if peremption else
                                                                           (a.get("sku") or "")),
                       e(str((a.get("itemStock") or {}).get("quantity", ""))), e(cat(a))])
    filtres = (f"<form class='ligne' method='get'><div><label>Rechercher</label><input name='q' "
               f"value='{e(ctx.req.query.get('q', ''))}'></div><div><label>Catégorie</label><input name='categorie' "
               f"value='{e(categorie)}' size='14'></div><div><label>Stock</label><select name='stock'>"
               + "".join(f"<option{' selected' if s == stock else ''}>{s}</option>" for s in ("", "en stock",
                                                                                              "sans stock"))
               + f"</select></div><div><label><input type='checkbox' name='ugs' value='1'{' checked' if ugs else ''}> "
                 "UGS qui ne sont pas des dates</label></div><button class='second'>Afficher</button></form>")
    corps = (message + filtres + f"<p class='note'>{len(retenus)} article(s)"
             + (f", {LIMITE} affichés" if len(retenus) > LIMITE else "") + ".</p>"
             + (f"<form method='post'>{csrf(ctx)}" if ugs else "")
             + tableau(["", "ID Clover", "Nom", "Prix", "Type de prix", "Code", "Péremption (UGS)", "Quantité",
                        "Catégories"], lignes, {3, 7})
             + ("<div class='boutons'><button>Effacer l'UGS des articles cochés dans Clover</button></div></form>"
                if ugs and lignes else ""))
    return Reponse(corps=page(ctx, "Articles Clover", corps))


# --------------------------------------------------------------------------------------------- correspondance
def _chemin_correspondance(ctx: Contexte) -> Path:
    return ctx.racine / "donnees" / "correspondance_articles.xlsx"


def correspondance(ctx: Contexte) -> Reponse:
    from .. import correspondance as co
    from . import taches

    if ctx.req.methode == "POST" and ctx.req.champ("action") == "Mettre à jour":
        def mettre_a_jour(journal):
            import os
            import subprocess

            from ..__main__ import commande_moteur

            processus = subprocess.Popen(commande_moteur() + ["correspondance"], cwd=ctx.racine, stdout=subprocess.PIPE,
                                         stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
                                         env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            for ligne in processus.stdout:
                journal(ligne.rstrip())
            return "Correspondance mise à jour." if processus.wait() == 0 else "Mise à jour avec des erreurs."

        return taches.lancer(ctx, "Mise à jour de la correspondance", mettre_a_jour, "/correspondance")
    lignes_c = co.lire_correspondances(_chemin_correspondance(ctx))
    texte = co.normaliser(ctx.req.query.get("q", ""))
    statut = ctx.req.query.get("statut", "")
    retenues = [(i, c) for i, c in enumerate(lignes_c)
                if (not statut or c.statut == statut or (statut == co.RENOMME and c.methode == co.RENOMME))
                and (not texte or texte in co.normaliser(f"{c.nom_clover} {c.numero_sage} {c.description_sage}"))]
    compte = {s: sum(1 for c in lignes_c if c.statut == s) for s in co.STATUTS}
    lignes = [[f"<a href='/correspondance-ligne?i={i}'>{e(c.nom_clover)}</a>", e(c.statut), e(c.categorie_clover),
               argent(c.ventes_30j), e(c.numero_sage), e(c.description_sage), e(c.methode), str(c.confiance)]
              for i, c in retenues[:LIMITE]]
    options = "".join(f"<option{' selected' if s == statut else ''}>{e(s)}</option>"
                      for s in [""] + co.STATUTS + [co.RENOMME])
    corps = (" · ".join(f"{e(s)} : {n}" for s, n in compte.items())
             + f"<form class='ligne' method='get'><div><label>Statut</label><select name='statut'>{options}</select></div>"
               f"<div><label>Rechercher</label><input name='q' value='{e(ctx.req.query.get('q', ''))}'></div><button "
               "class='second'>Afficher</button></form>"
             + tableau(["Article Clover", "Statut", "Catégorie", "Ventes 30 j", "N° Sage", "Description Sage",
                        "Méthode", "Confiance"], lignes, {3, 7})
             + f"<form method='post' class='boutons'>{csrf(ctx)}<button name='action' value='Mettre à jour'>Mettre à "
               "jour la correspondance (Clover et Sage)</button></form><p class='note'>Les lignes « Confirmé » sont "
               "toujours gardées. Deux formats différents sont deux articles différents.</p>")
    return Reponse(corps=page(ctx, "Correspondance", corps))


def correspondance_ligne(ctx: Contexte) -> Reponse:
    from .. import correspondance as co
    from .pages_fournisseurs import _listes

    chemin = _chemin_correspondance(ctx)
    lignes = co.lire_correspondances(chemin)
    try:
        i = int(ctx.req.query.get("i") or ctx.req.champ("i"))
        c = lignes[i]
    except (ValueError, IndexError):
        return Reponse(404, page(ctx, "Correspondance", "<p>Ligne introuvable.</p>"))
    _noms, articles = _listes(ctx.racine)
    descriptions = {a.numero: a.description for a in articles}
    message = ""
    if ctx.req.methode == "POST":
        numero = ctx.req.champ("numero").strip().split(" ")[0]
        statut = ctx.req.champ("statut")
        description = descriptions.get(numero, c.description_sage if numero == c.numero_sage else "")
        if statut == co.CONFIRME and numero and co.conflit_format(c.nom_clover, description) \
                and not ctx.req.champ("quand_meme"):
            message = _message(erreur=f"Formats différents (« {c.nom_clover} » / « {description} ») : deux formats "
                                      "différents sont deux articles différents. Cochez « Confirmer quand même » si "
                                      "c'est bien le même article.")
        else:
            c.numero_sage, c.description_sage = numero, description
            c.statut = statut if statut in co.STATUTS else c.statut
            if c.statut == co.CONFIRME:
                c.methode, c.confiance = c.methode or "Confirmé par le propriétaire", 100
            with ctx.app.ecriture:
                co.ecrire_correspondance(lignes, chemin)
            return redirection(f"/correspondance?q={c.nom_clover}")
    liste = "<datalist id='articles'>" + "".join(f"<option value='{e(a.numero)}'>{e(a.description)}</option>"
                                                 for a in articles) + "</datalist>"
    statuts = "".join(f"<option{' selected' if s == c.statut else ''}>{e(s)}</option>" for s in co.STATUTS)
    corps = (message + f"<p><a href='/correspondance'>◀ Correspondance</a></p><div class='carte'><p><strong>"
             f"{e(c.nom_clover)}</strong> · {e(c.categorie_clover)} · ID {e(c.id_clover)} · ventes 30 j "
             f"{argent(c.ventes_30j)}</p><p>Suggestions : {e(c.suggestions or '—')}</p></div>"
             + f"<form method='post' class='carte'>{csrf(ctx)}<input type='hidden' name='i' value='{i}'>"
               f"<div class='ligne'><div><label>N° d'article Sage</label><input name='numero' list='articles' "
               f"value='{e(c.numero_sage)}' size='16'>{liste}</div><div><label>Statut</label><select name='statut'>"
               f"{statuts}</select></div></div><p>Sage : {e(c.description_sage or '—')}</p><p><label><input "
               "type='checkbox' name='quand_meme' value='1'> Confirmer quand même (formats différents)</label></p>"
               "<div class='boutons'><button>Enregistrer</button></div></form>")
    return Reponse(corps=page(ctx, "Correspondance : une ligne", corps))


# --------------------------------------------------------------------------------------------- créer un article
def creer_article(ctx: Contexte) -> Reponse:
    from .. import creation_articles as ca
    from ..points_vente import client
    from . import taches
    from .consultations import sage

    try:
        cle = ("clover_categories",)
        gardee = ctx.app.memoire.get(cle)
        if gardee and time.time() - gardee[0] < 600:
            categories, taux = gardee[1]
        else:
            c = client(ctx.racine)
            categories, taux = c.categories(), c.taux_taxes()
            ctx.app.memoire[cle] = (time.time(), (categories, taux))
    except (Exception, SystemExit):  # noqa: BLE001
        categories, taux = [], []
    try:
        from ..bons_commande import descriptions_sage

        numeros_sage = set(sage(ctx, descriptions_sage, ("descriptions",)))
    except (Exception, SystemExit):  # noqa: BLE001
        numeros_sage = set()
    choix_taxes = ca.choix_taxes(taux) if taux else {ca.TAXES_DEFAUT: None}
    table = ca.TableCategories(ctx.racine)
    v = {k: ctx.req.champ(k).strip() for k in ("nature", "nom", "cout", "prix", "peremption", "categorie", "type_prix",
                                                "unite", "taxes", "code", "stock", "numero", "description",
                                                "charges", "produits")}
    message = ""
    if ctx.req.methode == "POST" and ctx.req.champ("action") == "Créer":
        try:
            service = v["nature"] == "Service"
            cout = Decimal((v["cout"] or "0").replace(",", "."))
            prix = Decimal(v["prix"].replace(",", ".")) if v["prix"] else ca.prix_vente(cout)
            cat = next((x for x in categories if x.get("name") == v["categorie"]), {})
            a = ca.NouvelArticle(v["nom"], cout, prix, ca.lire_date(v["peremption"]) if v["peremption"] else None,
                                 v["categorie"], cat.get("id", ""), v["type_prix"] or "FIXED", v["unite"],
                                 choix_taxes.get(v["taxes"]), v["code"], Decimal((v["stock"] or "0").replace(",", ".")),
                                 v["numero"], v["description"] or v["nom"], table.pour(v["categorie"]),
                                 creer_sage=bool(ctx.req.champ("sage")), creer_clover=bool(ctx.req.champ("clover")) and
                                 not service, service=service, compte_charges=v["charges"], compte_produits=v["produits"])
            problemes = a.problemes(numeros_sage or None)
            if not (a.creer_sage or a.creer_clover):
                problemes.append("cochez « Créer dans Clover » ou « Créer dans Sage »")
            if problemes:
                raise ValueError("À corriger : " + " ; ".join(problemes))

            def creer(journal):
                etapes = []
                try:
                    if a.creer_sage:
                        journal("Création dans Sage (l'application ouvre Sage elle-même si besoin)…")
                        (r,) = ca.creer_dans_sage(ctx.racine, ctx.config, [a.article_sage()])
                        if not r["cree"]:
                            raise RuntimeError("Sage : article non créé — " + " ; ".join(m for m in r["messages"] if m))
                        etapes.append(f"Sage : article {a.numero_sage} créé")
                    if a.creer_clover:
                        ca.creer_dans_clover(client(ctx.racine), a)
                        etapes.append("Clover : article créé")
                    if a.id_clover and a.numero_sage:
                        ca.relier_correspondance(_chemin_correspondance(ctx), a)
                        etapes.append("Correspondance : reliés (Confirmé)")
                    ca.noter(ctx.racine, a, " ; ".join(etapes))
                except Exception as exc:
                    ca.noter(ctx.racine, a, " ; ".join(etapes + [f"ERREUR : {exc}"]))
                    raise RuntimeError(" ; ".join(etapes + [str(exc)])) from exc
                return etapes

            return taches.lancer(ctx, f"Création de l'article {a.nom}", creer, "/creer-article", sage=a.creer_sage)
        except (ValueError, InvalidOperation) as erreur:
            message = _message(erreur=str(erreur) or "Nombre invalide.")
    # proposition du n° Sage d'après la catégorie (préfixe de la table)
    if v["categorie"] and not v["numero"]:
        comptes = table.pour(v["categorie"])
        v["numero"] = ca.prochain_numero(numeros_sage, "S" if v["nature"] == "Service" else
                                         (comptes.prefixe if comptes else ca.PREFIXE_DEFAUT))
    options_cat = "".join(f"<option{' selected' if x.get('name') == v['categorie'] else ''}>{e(x.get('name', ''))}"
                          "</option>" for x in categories)
    options_taxes = "".join(f"<option{' selected' if k == v['taxes'] else ''}>{e(k)}</option>" for k in choix_taxes)
    options_prix = "".join(f"<option value='{k}'{' selected' if k == v['type_prix'] else ''}>{e(n)}</option>"
                           for k, n in ca.TYPES_PRIX.items())
    nature = "".join(f"<option{' selected' if n == v['nature'] else ''}>{n}</option>" for n in ("Stock", "Service"))

    def champ(nom, libelle, taille=12, type_="text"):
        return (f"<div><label>{libelle}</label><input type='{type_}' name='{nom}' value='{e(v[nom])}' size='{taille}'>"
                "</div>")

    comptes = table.pour(v["categorie"]) if v["categorie"] else None
    corps = (message + f"<form method='post' class='carte'>{csrf(ctx)}<div class='ligne'><div><label>Type</label>"
             f"<select name='nature'>{nature}</select></div>" + champ("nom", "Nom (Clover)", 30)
             + champ("cout", "Prix d'achat", 8) + champ("prix", "Prix de vente (vide = achat + 40 %)", 8)
             + f"<div><label>Catégorie Clover</label><select name='categorie'><option></option>{options_cat}</select>"
               "</div>" + champ("peremption", "Péremption (UGS)", 10, "date")
             + f"<div><label>Type de prix</label><select name='type_prix'>{options_prix}</select></div>"
             + champ("unite", "Unité (prix par unité)", 6)
             + f"<div><label>Taxes</label><select name='taxes'>{options_taxes}</select></div>"
             + champ("code", "Code (facultatif)", 14) + champ("stock", "Stock Clover", 5) + "</div><h2>Sage</h2>"
             + "<div class='ligne'>" + champ("numero", "N° Sage", 12) + champ("description", "Description Sage", 30)
             + champ("charges", "Compte de charges (service)", 6) + champ("produits", "Compte de produits (service)", 6)
             + "</div>"
             + (f"<p class='note'>Comptes de la catégorie : actif {e(comptes.actif)}, produits {e(comptes.produits)}, "
                f"CMV {e(comptes.cmv)}, écart {e(comptes.ecart)}.</p>" if comptes else
                "<p class='note'>Choisissez la catégorie puis « Proposer le n° Sage » ; ses comptes viennent de "
                "« Comptabilité > Comptes Sage par catégorie ».</p>")
             + "<p><label><input type='checkbox' name='clover' value='1' checked> Créer dans Clover</label> "
               "<label><input type='checkbox' name='sage' value='1' checked> Créer dans Sage</label></p>"
               "<div class='boutons'><button class='second' name='action' value='Proposer'>Proposer le n° Sage</button>"
               "<button name='action' value='Créer'>Créer l'article</button></div></form>"
               "<p class='note'>Un service se crée dans Sage seulement (n° commençant par S).</p>")
    return Reponse(corps=page(ctx, "Créer un article", corps))


# --------------------------------------------------------------------------------------------- inventaire
def inventaire(ctx: Contexte) -> Reponse:
    from .. import inventaire as inv
    from . import taches

    dossier = ctx.racine / "sortie" / "inventaire"
    if ctx.req.methode == "POST":
        action = ctx.req.champ("action")
        if action == "Préparer":
            def exporter(journal):
                journal("Lecture du stock Clover et Sage…")
                lignes = inv.lire(ctx.racine, ctx.config)
                chemin = inv.ecrire(lignes, dossier / inv.nom_fichier("Inventaire"))
                return [f"{len(lignes)} ligne(s) : fichier {chemin.name} prêt (liste ci-dessous)."]

            return taches.lancer(ctx, "Fichier d'inventaire Clover et Sage", exporter, "/inventaire")
        if action == "Saisir" and "fichier" in ctx.req.fichiers:
            nom, contenu = ctx.req.fichiers["fichier"]
            if not nom.lower().endswith(".xlsx"):
                return Reponse(corps=page(ctx, "Inventaire Clover et Sage", _message(
                    erreur="Envoyez le fichier Excel (.xlsx) rempli.")))
            dossier.mkdir(parents=True, exist_ok=True)
            chemin = dossier / f"Compte_{datetime.now():%Y%m%d_%H%M%S}.xlsx"
            chemin.write_bytes(contenu)

            def saisir(journal):
                saisie, rapport = inv.saisir(ctx.racine, ctx.config, chemin, journal)
                return [f"Saisie faite : rapport {rapport.name} (liste ci-dessous)."]

            return taches.lancer(ctx, "Saisie de l'inventaire compté", saisir, "/inventaire", sage=True)
    fichiers = sorted(dossier.glob("*.xlsx"), key=lambda p: p.stat().st_mtime, reverse=True) if dossier.exists() else []
    lignes = [[f"<a href='/inventaire-fichier?f={e(p.name)}'>{e(p.name)}</a>",
               datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M")] for p in fichiers[:30]]
    corps = (f"<form method='post' class='boutons'>{csrf(ctx)}<button name='action' value='Préparer'>Préparer le fichier "
             "d'inventaire</button></form>"
             + f"<form method='post' enctype='multipart/form-data' class='ligne'>{csrf(ctx)}<div><label>Fichier compté "
               "(colonne jaune « Quantité comptée » remplie)</label><input type='file' name='fichier' accept='.xlsx' "
               "required></div><button name='action' value='Saisir'>Saisir dans Clover et Sage</button></form>"
             + "<h2>Fichiers</h2>" + tableau(["Fichier", "Date"], lignes)
             + "<p class='note'>Clover = quantité comptée de chaque ligne ; Sage = somme des lignes de son n°. Sage "
               "doit être fermé sur le serveur ou ouvert sur le fichier configuré.</p>")
    return Reponse(corps=page(ctx, "Inventaire Clover et Sage", corps))


def inventaire_fichier(ctx: Contexte) -> Reponse:
    chemin = ctx.racine / "sortie" / "inventaire" / Path(ctx.req.query.get("f", "")).name
    if not chemin.exists() or chemin.suffix.lower() != ".xlsx":
        return Reponse(404, page(ctx, "Inventaire", "<p>Fichier introuvable.</p>"))
    return _telecharger(chemin)


def inventaire_tournant(ctx: Contexte) -> Reponse:
    from .. import paquet3 as p3
    from . import taches

    if ctx.req.methode == "POST":
        def feuille(journal):
            chemin, categories, n = p3.feuille_tournante(ctx.racine, ctx.config, date.today())
            cible = ctx.racine / "sortie" / "inventaire" / chemin.name
            if chemin.resolve() != cible.resolve():
                cible.parent.mkdir(parents=True, exist_ok=True)
                cible.write_bytes(chemin.read_bytes())
            return [f"{n} ligne(s), catégories de la semaine : {', '.join(categories)}.",
                    f"Fichier {cible.name} : Stock > Inventaire Clover et Sage."]

        return taches.lancer(ctx, "Feuille de l'inventaire tournant", feuille, "/inventaire")
    semaines = int(ctx.config.get("inventaire", {}).get("semaines_cycle", 8))
    corps = (f"<p>Semaine {p3.semaine_du_cycle(date.today(), semaines) + 1} sur {semaines} du cycle : les catégories "
             "Clover sont comptées tour à tour, une partie chaque semaine.</p>"
             f"<form method='post' class='boutons'>{csrf(ctx)}<button>Préparer la feuille de la semaine</button></form>"
             "<p class='note'>La feuille remplie se saisit dans « Stock > Inventaire Clover et Sage ».</p>")
    return Reponse(corps=page(ctx, "Inventaire tournant", corps))


# --------------------------------------------------------------------------------------------- transferts
def transferts(ctx: Contexte) -> Reponse:
    from .. import transferts as tr
    from ..points_vente import points_de_vente
    from . import taches

    points = {str(p.code): p for p in points_de_vente(ctx.config, actifs=True)}
    message = ""
    if ctx.req.methode == "POST":
        action = ctx.req.champ("action")
        try:
            if action == "Créer":
                lignes = [tr.LigneTransfert(n.strip(), d.strip(), Decimal(q.replace(",", ".")))
                          for n, d, q in zip(ctx.req.champs("article"), ctx.req.champs("description"),
                                             ctx.req.champs("quantite")) if n.strip() and q.strip()]
                with ctx.app.ecriture:
                    registre = tr.Registre(ctx.racine)
                    t = tr.Transfert(registre.nouveau_numero(), ctx.req.champ("jour"), ctx.req.champ("de"),
                                     ctx.req.champ("vers"), lignes, ctx.req.champ("note"))
                    problemes = t.problemes(points)
                    if problemes:
                        raise ValueError("À corriger : " + " ; ".join(problemes))
                    registre.garder(t)
                message = _message(f"Transfert {t.numero} créé : « Transférer » pour le passer dans Sage et Clover.")
            elif action == "Transférer":
                numero = ctx.req.champ("numero")

                def transferer(journal):
                    t = tr.transferer(ctx.racine, ctx.config, numero, journal)
                    return [f"{t.numero} : {t.etat}"] + t.messages

                return taches.lancer(ctx, f"Transfert {numero}", transferer, "/transferts", sage=True)
            elif action == "Supprimer":
                if not action_permise(ctx, "Supprimer"):
                    raise ValueError("Votre profil n'a pas le droit « Supprimer ».")
                with ctx.app.ecriture:
                    tr.Registre(ctx.racine).supprimer(ctx.req.champ("numero"))
                message = _message("Transfert supprimé.")
        except (ValueError, InvalidOperation) as erreur:
            message = _message(erreur=str(erreur) or "Quantité invalide.")
    registre = tr.Registre(ctx.racine)
    lignes = []
    for t in sorted(registre.transferts, key=lambda t: t.jour, reverse=True):
        boutons = (f"<form method='post' class='ligne'>{csrf(ctx)}<input type='hidden' name='numero' value='{e(t.numero)}'>"
                   + ("<button name='action' value='Transférer'>Transférer</button>" if t.etat != "Terminé" else "")
                   + ("<button class='second' name='action' value='Supprimer'>Supprimer</button>"
                      if t.etat == tr.BROUILLON else "") + "</form>")
        lignes.append([e(t.numero), e(t.jour), e(points[t.de].libelle if t.de in points else t.de),
                       e(points[t.vers].libelle if t.vers in points else t.vers), e(f"{t.total_quantite:g}"), e(t.etat),
                       boutons])
    options = "".join(f"<option value='{e(c)}'>{e(p.libelle)}</option>" for c, p in points.items())
    rangees = "".join("<tr><td><input name='article' size='12'></td><td><input name='description' size='30'></td>"
                      "<td><input name='quantite' size='6'></td></tr>" for _ in range(8))
    corps = (message + tableau(["N°", "Date", "De", "Vers", "Quantité", "État", ""], lignes, {4})
             + (f"<form method='post' class='carte'>{csrf(ctx)}<h2>Nouveau transfert</h2><div class='ligne'><div><label>"
                f"Date</label><input type='date' name='jour' value='{date.today()}'></div><div><label>De</label><select "
                f"name='de'>{options}</select></div><div><label>Vers</label><select name='vers'>{options}</select></div>"
                "<div><label>Note</label><input name='note' size='30'></div></div><div class='defile'><table><tr><th>"
                f"N° Sage</th><th>Description</th><th>Quantité</th></tr>{rangees}</table></div><div class='boutons'>"
                "<button name='action' value='Créer'>Créer le transfert</button></div></form>" if len(points) > 1 else
                "<p class='note'>Un seul point de vente actif : les transferts demandent au moins deux points de vente "
                "(Administration > Clover).</p>"))
    return Reponse(corps=page(ctx, "Transferts entre magasins", corps))


FONCTIONS = [
    Fonction("/articles-clover", "Articles Clover", "correspondance", articles_clover, "📄", "Articles", menu=False),
    Fonction("/correspondance", "correspondance", "correspondance", correspondance, "🔗", "Articles", menu=False,
             page_entiere=True),
    Fonction("/correspondance-ligne", "correspondance", "correspondance", correspondance_ligne, "🔗", "Articles",
             menu=False, page_entiere=True),
    Fonction("/creer-article", "Créer un article", "correspondance", creer_article, "🆕", "Articles", menu=False),
    Fonction("/inventaire", "Inventaire Clover et Sage", "correspondance", inventaire, "📋", "Stock", menu=False),
    Fonction("/inventaire-fichier", "Inventaire Clover et Sage", "correspondance", inventaire_fichier, "📋", "Stock",
             menu=False),
    Fonction("/inventaire-tournant", "Inventaire tournant", "correspondance", inventaire_tournant, "🔄", "Stock",
             menu=False),
    Fonction("/transferts", "Transferts entre magasins", "correspondance", transferts, "🔁", "Stock", menu=False),
]
WEB = {"Articles Clover": "/articles-clover", "Correspondance": "/correspondance", "Créer un article": "/creer-article",
       "Inventaire Clover et Sage": "/inventaire", "Inventaire tournant": "/inventaire-tournant",
       "Transferts entre magasins": "/transferts"}
