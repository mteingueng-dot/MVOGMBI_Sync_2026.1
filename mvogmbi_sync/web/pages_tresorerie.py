"""4e vague de l'application web (suite) : encaissements des dépôts sur les factures de vente et paiements des
fournisseurs (avis Interac). Même logique que page_encaissements et page_paiements : calcul, rapprochement proposé,
confirmation par la personne, puis saisie dans Sage par l'application (Sage fermé, travail en arrière-plan).
"""

from __future__ import annotations

import time
from datetime import date, timedelta
from decimal import Decimal

from .consultations import Section, sections_html, tableau_section
from .pages import Contexte, Fonction, argent, csrf, page
from .pages_compta import _message, _point_vente
from .serveur import Reponse, echapper as e

JOURS = ["lun.", "mar.", "mer.", "jeu.", "ven.", "sam.", "dim."]


# --------------------------------------------------------------------------------------------- encaissements
def encaissements(ctx: Contexte) -> Reponse:
    """Comme page_encaissements.PageEncaissements : ventes du … au … (30 jours jusqu'à hier), « ⟳ Calculer les
    dépôts », « 🏦 Encaisser dans Sage », résumé, tableau des dépôts et de leurs factures colorés selon l'état, puis
    « Saisie dans Sage (Encaissements) » du dépôt choisi (le premier à saisir, sinon celui cliqué)."""
    from .. import encaissements as en
    from ..points_vente import permis
    from . import taches

    pv_fichiers, choix_pv, code = _point_vente(ctx)
    points = permis(ctx.config, ctx.reg.points_vente_permis(ctx.u))
    pdv = next((p for p in points if str(p.code) == str(code)), None)
    hier = date.today() - timedelta(days=1)
    fin = _date(ctx.req.query.get("au") or ctx.req.champ("au"), hier)
    debut = _date(ctx.req.query.get("du") or ctx.req.champ("du"), fin - timedelta(days=30))
    cle = ("depots", code, debut, fin)
    compte_depot = str(ctx.config.get("encaissements", {}).get("compte_depot", "1055"))
    message = ""
    if ctx.req.methode == "POST" and ctx.req.champ("action") == "Encaisser dans Sage":
        depots = (ctx.app.memoire.get(cle) or (0, []))[1]
        a_saisir = [d for d in depots if d.etat == en.A_SAISIR]
        if not a_saisir:
            message = _message(erreur="Aucun dépôt « À saisir dans Sage » : calculez d'abord les dépôts.")
        else:
            def travail(journal):
                b = taches.executer_sage(ctx.racine, ["encaisser-bureau", "--point-de-vente", str(code)], journal)
                try:
                    from ..courriel import envoyer_bilan_encaissements
                    envoyer_bilan_encaissements(ctx.config, b)
                except Exception as exc:  # noqa: BLE001 — le courriel ne masque pas le résultat
                    b.setdefault("notes", []).append(f"Courriel non envoyé : {exc}")
                ctx.app.memoire.pop(cle, None)
                return [f"{len(b.get('encaisses', []))} dépôt(s) encaissé(s) sur {len(a_saisir)}."] + \
                    b.get("encaisses", []) + b.get("a_verifier", []) + ([b["erreur"]] if b.get("erreur") else []) + \
                    b.get("notes", [])

            total = argent(sum((d.montant for d in a_saisir), Decimal(0)))
            return taches.lancer(ctx, f"Encaissement de {len(a_saisir)} dépôt(s) ({total})", travail,
                                 f"/encaissements?du={debut}&au={fin}&pv={code}&calculer=1", sage=True)
    barre = (f"<form class='barre-onglet' method='post'>{csrf(ctx)}{choix_pv}<div><label>Ventes du</label><input "
             f"type='date' name='du' value='{debut}'></div><div><label>au</label><input type='date' name='au' "
             f"value='{fin}'></div><button formmethod='get' name='calculer' value='1'>⟳ Calculer les dépôts</button>"
             "<button class='accent a-droite' name='action' value='Encaisser dans Sage'>🏦 Encaisser dans Sage</button>"
             "</form>")
    resume = "Cliquez sur « Calculer les dépôts » : lots de cartes Clover et état dans Sage."
    depots = None
    gardee = ctx.app.memoire.get(cle)
    if gardee and time.time() - gardee[0] < 300 and not ctx.req.query.get("calculer"):
        depots = gardee[1]
    elif ctx.req.query.get("calculer"):
        if pdv is None:
            resume = "✘ Aucun point de vente actif n'est permis à votre profil."
        else:
            try:
                from ..__main__ import charger_config, lire_sage
                from ..api_clover import ClientClover

                client = ClientClover(charger_config(ctx.racine / "config.toml", pdv))
                compte = en.numero_compte_sage(compte_depot)
                depots = lire_sage(ctx.config, lambda b: en.calculer(
                    client, b, pdv.client_sage, compte, debut, fin, racine=ctx.racine if pdv.principal else None,
                    prefixe=pdv.prefixe), ouvrir=False)
                ctx.app.memoire[cle] = (time.time(), depots)
            except (Exception, SystemExit) as erreur:  # noqa: BLE001
                ctx.app.noter(f"Encaissements : {erreur!r}")
                resume = f"✘ {erreur}"
    corps = _entete_encaissements() + message + barre
    if depots is None:
        return Reponse(corps=page(ctx, "Encaissements", corps + f"<p class='note'>{e(resume)}</p>"))
    ordre = sorted(enumerate(depots), key=lambda x: (x[1].date, x[0]), reverse=True)  # plus récent en haut
    a_saisir = [d for d in depots if d.etat in (en.A_SAISIR, en.ECART, en.A_VERIFIER, en.A_RIA)]
    try:
        choisi = depots[int(ctx.req.query["choix"])]
    except (KeyError, ValueError, IndexError):
        choisi = a_saisir[0] if a_saisir else None
    lien = f"du={debut}&amp;au={fin}&amp;pv={e(code)}"
    lignes, classes = [], []
    for i, d in ordre:
        texte = f"{d.date} ({JOURS[d.date.weekday()]})" + (f"  •  {d.origine}" if d.origine else "") + \
            (f"  —  {d.remarque}" if d.remarque else "")
        marque = " ◀" if d is choisi else ""
        lignes.append([f"<a class='depot' href='?{lien}&amp;choix={i}'>{e(texte)}</a>{marque}", argent(d.montant), "",
                       e(d.etat)])
        classes.append(f"{COULEURS.get(d.etat, 'termine')} ligne-depot")
        for l in d.lignes:
            lignes.append([f"<span class='retrait'>{e(l.facture)}</span>", argent(l.montant),
                           argent(l.montant_du) if l.montant_du is not None else "", e(l.etat)])
            classes.append(COULEURS.get(l.etat, "termine"))
    total = argent(sum((d.montant for d in depots), Decimal(0)))
    resume = (f"{len(depots)} dépôt(s), {total} au total — {len(a_saisir)} à saisir dans Sage, "
              f"{sum(1 for d in depots if d.etat == en.APPLIQUE)} déjà appliqué(s).")
    corps += (f"<p class='note'>{e(resume)}</p>"
              + tableau_section(Section("Dépôts et factures", ["Date du dépôt / facture", "Montant", "Montant dû (Sage)",
                                                               "État"], lignes, classes=classes, html={0, 1, 2, 3}))
              + "<div class='carte'><h2>Saisie dans Sage (Encaissements)</h2><pre class='saisie'>"
              + e(_texte_saisie(choisi, pdv, compte_depot) if choisi else "Sélectionnez un dépôt dans le tableau.")
              + "</pre></div><p class='note'>« Encaisser dans Sage » : Sage doit être fermé sur le serveur ; "
                "l'application l'ouvre elle-même.</p>")
    return Reponse(corps=page(ctx, "Encaissements", corps))


# couleurs de page_encaissements.COULEURS (état sans couleur : terminé, texte grisé)
COULEURS = {"Appliqué": "etat-applique", "À saisir dans Sage": "etat-a-saisir", "Montant différent dans Sage":
            "etat-ecart", "Espèces à répartir à la main": "etat-ecart", "Part RIA à confirmer": "etat-ria"}


def _entete_encaissements() -> str:
    return ("<p class='sous-titre'>💰 Encaissements des dépôts Clover — dépôts Clover, virements Interac et dépôts "
            "d'espèces appliqués sur les factures de vente</p>")


def _texte_saisie(d, pdv, compte_depot: str) -> str:
    """Comme PageEncaissements.texte_saisie."""
    client = pdv.client_sage if pdv else "Vente Hebdomadaire"
    lignes = [f"Encaissements > Payé par : Comptant ; Reçu de : {client}", f"Dépôt : {compte_depot} (compte Desjardins)",
              f"Date : {d.date.isoformat()}", "", "Montant reçu, facture par facture :"]
    lignes += [f"   {l.facture:<20} {argent(l.montant):>14}   ({l.etat})" for l in d.lignes]
    lignes += ["", f"Total du dépôt : {argent(d.montant)}",
               "Puis « Traiter ». L'état passera à « Appliqué » au prochain calcul."]
    return "\n".join(lignes)


def _date(texte, defaut: date) -> date:
    try:
        return date.fromisoformat(texte)
    except (TypeError, ValueError):
        return defaut


# --------------------------------------------------------------------------------------------- paiements
def paiements(ctx: Contexte) -> Reponse:
    """Comme page_paiements.PagePaiements : « Lire depuis le » … « au », « 🔄 Actualiser », « Afficher : » (À traiter,
    Tous, chaque état), « 💸 Payer dans Sage », résumé, liste colorée, puis la fiche du virement choisi : fournisseur
    Sage, factures impayées (plusieurs cases = un virement sur plusieurs factures), « ✔ Confirmer le paiement »,
    « Ignorer (pas un fournisseur) », « Remettre à relier »."""
    from .. import paiements_fournisseurs as pf
    from ..correspondance import normaliser
    from ..fournisseurs import MemoireCorrespondance
    from . import taches

    reglage = str(ctx.config.get("boite_paiements", {}).get("depuis", "2026-08-01"))
    depuis = _date(ctx.req.query.get("depuis") or ctx.req.champ("depuis"), _date(reglage, date.today()))
    au = _date(ctx.req.query.get("au") or ctx.req.champ("au"), date.today())
    filtre = ctx.req.query.get("filtre") or ctx.req.champ("filtre") or "À traiter"
    try:
        rang = int(ctx.req.query.get("i") or ctx.req.champ("i"))
    except (TypeError, ValueError):
        rang = None
    ouvertes, noms = (ctx.app.memoire.get("paiements_sage") or (0, ([], [])))[1]
    retour = f"/paiements-fournisseurs?depuis={depuis}&au={au}&filtre={filtre}"
    message = ""
    if ctx.req.methode == "POST":
        action = ctx.req.champ("action")
        if action == "Actualiser":
            def lire(journal):
                return _actualiser(ctx, depuis, journal)

            return taches.lancer(ctx, "Lecture des avis de paiement", lire, retour)
        if action == "Payer dans Sage":
            confirmes = [x for x in pf.RegistrePaiements(ctx.racine).paiements if x.etat == pf.CONFIRME]
            if not confirmes:
                message = _message(erreur="Aucun paiement « Confirmé » : sélectionnez un virement, choisissez sa "
                                          "facture puis « Confirmer le paiement ».")
            else:
                def payer(journal):
                    b = taches.executer_sage(ctx.racine, ["payer-bureau"], journal)
                    try:
                        from ..courriel import envoyer_bilan_paiements
                        envoyer_bilan_paiements(ctx.config, b)
                    except Exception as exc:  # noqa: BLE001
                        b.setdefault("notes", []).append(f"Courriel non envoyé : {exc}")
                    return [f"{len(b.get('payes', []))} paiement(s) saisi(s) sur {len(confirmes)}."] + \
                        b.get("payes", []) + b.get("a_verifier", []) + ([b["erreur"]] if b.get("erreur") else []) + \
                        b.get("notes", [])

                return taches.lancer(ctx, f"Saisie de {len(confirmes)} paiement(s)", payer, retour, sage=True)
        if rang is not None and action in ("Confirmer", "Ignorer", "Remettre à relier"):
            with ctx.app.ecriture:
                registre = pf.RegistrePaiements(ctx.racine)
                try:
                    x = registre.paiements[rang]
                except IndexError:
                    x = None
                if x is None:
                    message = _message(erreur="Virement introuvable : actualisez la liste.")
                elif action == "Confirmer":
                    nom = ctx.req.champ("fournisseur").strip()
                    choisies = [f for f in ouvertes if f.fournisseur == nom and f.numero in ctx.req.champs("factures")]
                    try:
                        if not nom or not choisies:
                            raise ValueError("Choisissez le fournisseur Sage puis la ou les factures payées.")
                        parts = pf.repartir(x.avis.montant, sorted(choisies, key=lambda f: f.date))
                        x.fournisseur_sage, x.etat = nom, pf.CONFIRME
                        x.appliquer_repartition(parts)
                        x.remarque = (f"virement réparti sur {len(parts)} factures" if len(parts) > 1 else
                                      ("" if parts[0][0].solde == x.avis.montant else
                                       f"paiement partiel : virement {x.avis.montant} $, solde {parts[0][0].solde} $"))
                        memoire = MemoireCorrespondance(ctx.racine)
                        memoire.donnees.setdefault("beneficiaires", {})[normaliser(x.avis.beneficiaire)] = nom
                        memoire.enregistrer()
                        registre.enregistrer()
                        message = _message("Paiement confirmé : il sera saisi avec « Payer dans Sage ».")
                    except ValueError as erreur:
                        message = _message(erreur=str(erreur) if "Choisissez" in str(erreur) else
                                           "Le virement dépasse le solde des factures choisies : choisissez-en "
                                           "d'autres.")
                elif action == "Ignorer":
                    x.etat, x.remarque = pf.IGNORE, "ignoré par le propriétaire"
                    registre.enregistrer()
                elif x.etat != pf.SAISI:
                    x.etat, x.facture, x.solde_facture, x.remarque, x.repartition = pf.A_RELIER, "", None, "", []
                    registre.enregistrer()
    registre = pf.RegistrePaiements(ctx.racine)
    visibles = [(n, x) for n, x in enumerate(registre.paiements)
                if depuis.isoformat() <= x.avis.date_virement <= au.isoformat()]
    lien = f"depuis={depuis}&amp;au={au}&amp;filtre={e(filtre)}"
    lignes, classes = [], []
    for n, x in sorted(visibles, key=lambda v: (v[1].avis.date_virement, v[0]), reverse=True):  # plus récent en haut
        if filtre == "À traiter" and x.etat not in (pf.A_RELIER, pf.PROPOSE, pf.CONFIRME):
            continue
        if filtre not in ("À traiter", "Tous") and x.etat != filtre:
            continue
        a = x.avis
        lignes.append([f"<a href='?{lien}&amp;i={n}'>{e(a.date_virement)}</a>" + (" ◀" if n == rang else ""),
                       e(a.beneficiaire), argent(a.montant), e(a.message), e(x.fournisseur_sage), e(x.facture),
                       "" if x.solde_facture is None else argent(x.solde_facture), e(x.etat)])
        classes.append(COULEURS_PAIEMENTS.get(x.etat, "termine"))
    compte = {et: sum(1 for _n, x in visibles if x.etat == et) for et in pf.ETATS}
    resume = (f"{len(visibles)} virement(s) — à relier : {compte[pf.A_RELIER]}, proposés : {compte[pf.PROPOSE]}, "
              f"confirmés : {compte[pf.CONFIRME]}, déjà dans Sage : {compte[pf.DEJA]}, ignorés : {compte[pf.IGNORE]}, "
              f"annulés/expirés : {compte[pf.NON_PAYE]}")
    if not ctx.app.memoire.get("paiements_sage"):
        resume += "   •   cliquez sur « Actualiser » pour lire les avis et les factures impayées de Sage"
    options = "".join(f"<option{' selected' if f == filtre else ''}>{e(f)}</option>"
                      for f in ["À traiter", "Tous"] + list(pf.ETATS))
    barre = (f"<form class='barre-onglet' method='post'>{csrf(ctx)}<div><label>Lire depuis le</label><input "
             f"type='date' name='depuis' value='{depuis}'></div><div><label>au</label><input type='date' name='au' "
             f"value='{au}'></div><button name='action' value='Actualiser'>🔄 Actualiser</button><div><label>Afficher :"
             f"</label><select name='filtre'>{options}</select></div><button class='second' formmethod='get'>Afficher"
             "</button><button class='accent a-droite' name='action' value='Payer dans Sage'>💸 Payer dans Sage"
             "</button></form>")
    corps = ("<p class='sous-titre'>💸 Paiements fournisseurs — virements Interac reliés aux factures fournisseurs et "
             "saisis dans Sage</p>" + message + barre + f"<p class='note'>{e(resume)}</p>"
             + tableau_section(Section("Virements Interac", ["Date", "Bénéficiaire", "Montant", "Message",
                                                             "Fournisseur Sage", "Facture", "Solde dû", "État"],
                                       lignes, classes=classes, html=set(range(8))))
             + _fiche_paiement(ctx, registre, rang, ouvertes, noms, depuis, au, filtre))
    return Reponse(corps=page(ctx, "Paiements fournisseurs", corps))


# couleurs de page_paiements.COULEURS (états sans couleur : terminés, texte grisé)
COULEURS_PAIEMENTS = {"À relier": "etat-a-saisir", "Proposé": "etat-propose", "Confirmé (à saisir)": "etat-applique",
                      "Annulé / expiré": "etat-ecart"}


def _fiche_paiement(ctx: Contexte, registre, rang, ouvertes, noms, depuis, au, filtre) -> str:
    """Carte du bas de PagePaiements : virement choisi, fournisseur, factures impayées et décisions."""
    try:
        x = registre.paiements[rang] if rang is not None else None
    except IndexError:
        x = None
    if x is None:
        return "<div class='carte'><p>Sélectionnez un virement dans la liste.</p></div>"
    a = x.avis
    nom = ctx.req.query.get("fournisseur") or ctx.req.champ("fournisseur") or x.fournisseur_sage
    retenues = {n: mt for n, mt, _s in x.lignes()}
    factures = [f for f in ouvertes if f.fournisseur == nom]
    cases = "".join(
        f"<label class='facture'><input type='checkbox' name='factures' value='{e(f.numero)}'"
        f"{' checked' if f.numero in retenues else ''}> <code>{e(f.numero):<16} {e(f.date)}   {argent(f.solde):>12}"
        f"{'  ◄ ' + argent(retenues[f.numero]) if f.numero in retenues else ''}</code></label>" for f in factures)
    if not ouvertes:
        cases = "<p class='note'>(cliquez sur « Actualiser » pour charger les factures impayées)</p>"
    liste = "<datalist id='fournisseurs'>" + "".join(f"<option value='{e(n)}'>" for n in noms) + "</datalist>"
    cache = (f"{csrf(ctx)}<input type='hidden' name='i' value='{rang}'><input type='hidden' name='depuis' "
             f"value='{depuis}'><input type='hidden' name='au' value='{au}'><input type='hidden' name='filtre' "
             f"value='{e(filtre)}'>")
    return (f"<form method='post' class='carte'>{cache}<p>Virement Interac du <strong>{e(a.date_virement)}</strong> : "
            f"<strong>{argent(a.montant)}</strong> à {e(a.beneficiaire)}   •   réf. {e(a.reference or '—')}<br>"
            f"Message : « {e(a.message or '—')} »</p><div class='ligne'><div><label>Fournisseur Sage</label><input "
            f"name='fournisseur' list='fournisseurs' value='{e(nom)}' size='40'>{liste}</div><button class='second' "
            f"name='action' value='Voir'>Voir ses factures</button>"
            + (f"<span class='erreur-texte'>{e(x.remarque)}</span>" if x.remarque else "") + "</div>"
            "<div class='fiche-bas'><div class='factures'><p class='note'>Factures impayées de ce fournisseur dans Sage "
            "(cochez-en plusieurs : plusieurs factures pour un même virement) :</p>" + cases + "</div>"
            "<div class='boutons-colonne'><button name='action' value='Confirmer'>✔ Confirmer le paiement</button>"
            "<button class='second' name='action' value='Ignorer'>Ignorer (pas un fournisseur)</button>"
            "<button class='second' name='action' value='Remettre à relier'>Remettre à relier</button></div></div>"
            "</form>")


def _actualiser(ctx: Contexte, depuis: date, journal) -> list[str]:
    """Comme PagePaiements.lire + _fin_lecture : avis de la boîte, factures impayées de Sage, rapprochement."""
    from .. import coffre
    from .. import paiements_fournisseurs as pf
    from ..__main__ import lire_sage
    from ..correspondance import normaliser  # noqa: F401 — même module que la page Windows
    from ..encaissements import numero_compte_sage
    from ..fournisseurs import MemoireCorrespondance, fournisseurs_actifs
    from ..paiements_courriel import lire_boite

    b = ctx.config.get("boite_paiements", {})
    if not b.get("serveur") or not b.get("utilisateur"):
        raise RuntimeError("Réglez la boîte des avis de paiement (Administration > Courriel).")
    registre = pf.RegistrePaiements(ctx.racine)
    connus = {p.avis.identifiant for p in registre.paiements if getattr(p.avis, "identifiant", "")}
    journal("Lecture de la boîte de courriel…")
    avis = lire_boite(b["serveur"], b["utilisateur"], coffre.lire(coffre.BOITE_PAIEMENTS), depuis,
                      int(b.get("port", 993)), connus=connus)
    journal("Lecture des factures impayées dans Sage…")
    compte = numero_compte_sage(str(ctx.config.get("encaissements", {}).get("compte_depot", "1055")))
    ouvertes, existants, noms = lire_sage(ctx.config, lambda base: (
        pf.factures_ouvertes(base), pf.paiements_existants(base, compte, depuis), fournisseurs_actifs(base)),
        ouvrir=False)
    with ctx.app.ecriture:
        registre = pf.RegistrePaiements(ctx.racine)
        nouveaux = registre.ajouter(avis)
        memoire = MemoireCorrespondance(ctx.racine)
        beneficiaires = memoire.donnees.setdefault("beneficiaires", {})
        for p in registre.paiements:
            if p.etat == pf.CONFIRME and (p.fournisseur_sage, p.avis.date_virement, p.avis.montant) in existants:
                p.etat, p.remarque = pf.DEJA, "saisi entre-temps dans Sage"
            pf.rapprocher(p, noms, beneficiaires, ouvertes, existants)
        registre.enregistrer()
    ctx.app.memoire["paiements_sage"] = (time.time(), (ouvertes, noms))
    return [f"{len(nouveaux)} nouvel(s) avis lu(s) ; {len(ouvertes)} facture(s) impayée(s) dans Sage."]


def paiement(ctx: Contexte) -> Reponse:
    """Ancienne adresse de la fiche d'un virement : la fiche est maintenant sous la liste."""
    from .serveur import redirection

    return redirection(f"/paiements-fournisseurs?filtre=Tous&depuis=2000-01-01&i={e(ctx.req.query.get('i', ''))}")


FONCTIONS = [
    Fonction("/encaissements", "Encaissements", "encaissements", encaissements, "💰", "Comptabilité", menu=False,
             page_entiere=True),
    Fonction("/paiements-fournisseurs", "Paiements fournisseurs", "paiements", paiements, "💸", "Comptabilité",
             menu=False, page_entiere=True),
    Fonction("/paiement", "Paiements fournisseurs", "paiements", paiement, "💸", "Comptabilité", menu=False,
             page_entiere=True),
]
WEB = {"Encaissements": "/encaissements", "Paiements fournisseurs": "/paiements-fournisseurs"}
