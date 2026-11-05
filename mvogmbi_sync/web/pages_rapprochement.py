"""4e vague de l'application web (suite) : rapprochement bancaire (comme page_rapprochement) : relevés Desjardins PDF
envoyés par le navigateur, période, chiffres du rapprochement, mouvements, décisions (compte choisi, ignoré, remis),
saisie des écritures dans Sage (journal général, Sage fermé, en arrière-plan).
"""

from __future__ import annotations

import time
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from .pages import Contexte, Fonction, argent, csrf, page, tableau
from .pages_compta import _message
from .serveur import Reponse, echapper as e

A_TRAITER_LIBELLE = "À traiter"


def _periode(ctx: Contexte):
    textes = (ctx.req.query.get("du", ""), ctx.req.query.get("au", ""))
    if not any(textes):
        return None
    try:
        du, au = (date.fromisoformat(x) if x else None for x in textes)
    except ValueError:
        return None
    return du or date.min, au or date.max


def _lire(ctx: Contexte, choix, forcer: bool = False):
    """Comme PageRapprochement.actualiser + _fin_lecture ; gardé 5 min (clé : période choisie)."""
    from .. import rapprochement as rp
    from ..__main__ import lire_sage

    cle = ("rapprochement", choix)
    gardee = ctx.app.memoire.get(cle)
    if gardee and not forcer and time.time() - gardee[0] < 300:
        return gardee[1]
    registre = rp.RegistreReleves(ctx.racine)
    releves = registre.lire()
    periode = rp.periode_des(releves)
    if periode and choix:
        periode = (max(periode[0], choix[0]), min(periode[1], choix[1]))
        if periode[0] > periode[1]:
            periode = None
    if periode:
        sage, solde, ouverture, comptes, paies = lire_ou_vide(ctx, lambda base: (
            rp.mouvements_sage(base, periode[0], periode[1]), rp.solde_sage(base, periode[1]),
            rp.solde_sage(base, periode[0] - timedelta(days=1)), rp.comptes_sage(base),
            [s for s in rp.mouvements_sage(base, periode[0] - timedelta(days=rp.DELAI_PAIE),
                                           periode[0] - timedelta(days=1)) if s.source.upper().startswith("PAY")]))
        banque, ouverture_banque, solde_banque = rp.restreindre(releves, *periode)
    else:
        sage, solde, ouverture, comptes, paies, banque, ouverture_banque, solde_banque = [], None, None, [], [], [], \
            None, None
    rp.rapprocher(banque, sage, list(paies))
    soldes = (solde_banque, solde, ouverture_banque, ouverture)
    etat = {"releves": releves, "banque": banque, "sage": sage, "comptes": comptes, "periode": periode,
            "soldes": soldes}
    if "Sage" not in ctx.absents:  # une lecture vide n'est jamais gardée
        ctx.app.memoire[cle] = (time.time(), etat)
    return etat


def rapprochement(ctx: Contexte) -> Reponse:
    """Comme page_rapprochement.PageRapprochement : « 📂 Charger des relevés… », « 🔄 Actualiser », « 🗑 Supprimer le
    relevé », « 📤 Saisir dans Sage », « 📗 Rapport Excel » ; période du … au … (« Rapprocher cette période »,
    « Toute la période des relevés ») ; relevés chargés ; 5 cartes ; « Afficher : » ; mouvements colorés ; fiche du
    mouvement choisi (compte Sage, Confirmer / Ignorer / Remettre à traiter, encaissement et paiement fournisseur
    manuels)."""
    from .. import rapprochement as rp
    from . import taches

    choix = _periode(ctx)
    du = choix[0].isoformat() if choix and choix[0] != date.min else ""
    au = choix[1].isoformat() if choix and choix[1] != date.max else ""
    filtre = ctx.req.query.get("filtre") or ctx.req.champ("filtre") or A_TRAITER_LIBELLE
    cle_m = ctx.req.query.get("m") or ctx.req.champ("m")
    releve = ctx.req.query.get("releve") or ctx.req.champ("releve")
    retour = f"/rapprochement?du={du}&au={au}&filtre={filtre}"
    message = ""
    if ctx.req.methode == "POST":
        action = ctx.req.champ("action")
        registre = rp.RegistreReleves(ctx.racine)
        if action == "Charger":
            if "releves" not in ctx.req.fichiers:
                message = _message(erreur="Choisissez un relevé de compte Desjardins en PDF.")
            else:
                nom, contenu = ctx.req.fichiers["releves"]
                if not nom.lower().endswith(".pdf") or not contenu.startswith(b"%PDF"):
                    message = _message(erreur="Choisissez un relevé de compte Desjardins en PDF.")
                else:
                    registre.dossier.mkdir(parents=True, exist_ok=True)
                    (registre.dossier / Path(nom).name).write_bytes(contenu)
                    message = _message(f"Relevé « {nom} » chargé.")
                    choix, du, au = None, "", ""  # comme Windows : toute la période des relevés
                    _oublier(ctx)
        elif action == "Supprimer le relevé":
            if not releve:
                message = _message(erreur="Sélectionnez le relevé à supprimer dans la liste du haut.")
            else:
                fichier = Path(releve).name
                with ctx.app.ecriture:
                    registre.supprimer(fichier)
                    registre.enregistrer()
                message = _message(f"Relevé « {fichier} » retiré du rapprochement (fichier mis de côté dans "
                                   "« supprimes »).")
                releve = ""
                _oublier(ctx)
        elif action == "Saisir dans Sage":
            etat = _lire(ctx, choix)
            choisis = [m for m in etat["banque"] if m.etat == rp.CONFIRME]
            if not choisis:
                message = _message(erreur="Aucun mouvement « Compte choisi » : choisissez d'abord le compte Sage des "
                                          "mouvements absents de Sage.")
            else:
                def travail(journal):
                    b = taches.executer_sage(ctx.racine, ["journal-bureau"], journal)
                    _oublier(ctx)
                    return [f"{len(b.get('saisis', []))} écriture(s) enregistrée(s) sur {len(choisis)}."] + \
                        b.get("a_verifier", []) + ([b["erreur"]] if b.get("erreur") else [])

                return taches.lancer(ctx, f"Saisie de {len(choisis)} écriture(s) du relevé", travail, retour,
                                     sage=True)
        elif action in ("Confirmer le compte", "Ignorer", "Remettre à traiter", "Paiement fournisseur manuel",
                        "Noter l'encaissement"):
            try:
                etat = _lire(ctx, choix)
                message = _decider(ctx, etat, cle_m, action)
            except (Exception, SystemExit) as erreur:  # noqa: BLE001
                ctx.app.noter(f"Rapprochement : {erreur!r}")
                message = _message(erreur="Lecture impossible : Sage ne répond pas sur le serveur pour l'instant.")
    if ctx.req.query.get("rapport"):
        return _rapport(ctx, choix)
    try:
        etat = _lire(ctx, choix, forcer=bool(ctx.req.query.get("actualiser")))
    except (Exception, SystemExit) as erreur:  # noqa: BLE001 — Sage absent : relevés seuls, tableaux affichés
        ctx.app.noter(f"Rapprochement : {erreur!r}")
        ctx.absents.add("Sage")
        etat = _sans_sage(ctx, choix)
    if etat and etat["periode"] and not (du or au) and not choix:
        du, au = etat["periode"][0].isoformat(), etat["periode"][1].isoformat()
    lien = f"du={du}&amp;au={au}&amp;filtre={e(filtre)}"
    barre = (f"<form method='post' enctype='multipart/form-data' class='barre-onglet'>{csrf(ctx)}"
             f"<input type='hidden' name='du' value='{du}'><input type='hidden' name='au' value='{au}'>"
             f"<input type='hidden' name='filtre' value='{e(filtre)}'><input type='hidden' name='releve' "
             f"value='{e(releve)}'><input type='file' name='releves' accept='.pdf'><button name='action' "
             "value='Charger'>📂 Charger des relevés…</button>"
             f"<a class='ouvrir' href='?{lien}&amp;actualiser=1'>🔄 Actualiser</a>"
             "<button class='danger' name='action' value='Supprimer le relevé'>🗑 Supprimer le relevé</button>"
             "<button class='accent a-droite' name='action' value='Saisir dans Sage'>📤 Saisir dans Sage</button>"
             + (f"<a class='ouvrir' href='?{lien}&amp;rapport=1'>📗 Rapport Excel</a>" if ctx.reg.peut_exporter(ctx.u)
                else "") + "</form>"
             f"<form method='get' class='barre-onglet'><div><label>Période du</label><input type='date' name='du' "
             f"value='{du}'></div><div><label>au</label><input type='date' name='au' value='{au}'></div>"
             f"<input type='hidden' name='filtre' value='{e(filtre)}'><input type='hidden' name='actualiser' value='1'>"
             "<button>🔄 Rapprocher cette période</button><a class='ouvrir' "
             f"href='?filtre={e(filtre)}&amp;actualiser=1'>Toute la période des relevés</a></form>")
    corps = ("<p class='sous-titre'>🏦 Rapprochement bancaire — relevés Desjardins (compte 1055) rapprochés des "
             "écritures de Sage</p>" + message + barre)
    if etat is None:
        return Reponse(corps=page(ctx, "Rapprochement bancaire", corps))
    corps += _corps(ctx, etat, filtre, du, au, cle_m, releve)
    return Reponse(corps=page(ctx, "Rapprochement bancaire", corps))


def _sans_sage(ctx: Contexte, choix):
    """Relevés et mouvements de banque sans les écritures de Sage (Sage ne répond pas)."""
    from .. import rapprochement as rp

    releves = rp.RegistreReleves(ctx.racine).lire()
    periode = rp.periode_des(releves)
    if periode and choix:
        periode = (max(periode[0], choix[0]), min(periode[1], choix[1]))
        if periode[0] > periode[1]:
            periode = None
    banque, ouverture, solde = rp.restreindre(releves, *periode) if periode else ([], None, None)
    rp.rapprocher(banque, [], [])
    return {"releves": releves, "banque": banque, "sage": [], "comptes": [], "periode": periode,
            "soldes": (solde, None, ouverture, None)}


def _oublier(ctx: Contexte) -> None:
    for cle in [c for c in list(ctx.app.memoire) if isinstance(c, tuple) and c and c[0] == "rapprochement"]:
        ctx.app.memoire.pop(cle, None)


COULEURS_MOUVEMENTS = {"Absent de Sage": "etat-a-saisir", "À encaisser sur les ventes": "etat-encaisser",
                       "Paie absente de Sage": "etat-ecart", "Compte choisi (à saisir)": "etat-applique",
                       "Seulement dans Sage": "etat-propose"}


def _corps(ctx: Contexte, etat: dict, filtre: str, du: str, au: str, cle_m: str, releve: str) -> str:
    from .. import rapprochement as rp
    from .consultations import lire_ou_vide, Section, tableau_section

    lien = f"du={du}&amp;au={au}&amp;filtre={e(filtre)}"
    releves, classes = [], []
    for r in etat["releves"]:
        problemes = r.controles()
        nom = f"<a href='?{lien}&amp;releve={e(r.fichier)}'>{e(r.fichier)}</a>" + (" ◀" if r.fichier == releve else "")
        releves.append([nom, f"{e(r.debut)} → {e(r.fin)}", argent(r.solde_ouverture), argent(r.solde_fermeture),
                        e("; ".join(problemes) or "✔ relevé complet et cohérent")])
        classes.append("etat-ecart" if problemes else "")
    if not etat["releves"]:
        for chemin in rp.RegistreReleves(ctx.racine).fichiers():
            releves.append([e(chemin.name), "", "", "", "cliquez sur « Actualiser »"])
    html = tableau_section(Section("Relevés chargés", ["Relevé", "Période", "Solde d'ouverture", "Solde de fermeture",
                                                       "Contrôle"], releves, classes=classes, html=set(range(5))))
    periode = etat["periode"]
    banque, sage = etat["banque"], etat["sage"]
    chiffres = rp.resume(banque, sage, *etat["soldes"], debut=periode[0]) if periode else {}
    cartes = ""
    for cle, libelle in (("solde_banque", "Solde du relevé"), ("solde_sage", "Solde Sage (1055)"), ("ecart", "Écart"),
                         ("ecart_ouverture", "dont écart d'ouverture"), ("non_explique", "Écart non expliqué")):
        v = chiffres.get(cle)
        classe = "baisse" if cle in ("ecart", "non_explique") and v not in (None, Decimal(0)) else "hausse"
        cartes += (f"<div class='carte-total'><div class='t'>{libelle}</div><div class='v {classe}'>"
                   f"{argent(v) if v is not None else '—'}</div></div>")
    html += f"<div class='cartes-cinq'>{cartes}</div>"
    if not periode:
        return html + ("<p class='note'>Aucun relevé chargé ne couvre cette période.</p>" if etat["releves"] else
                       "<p class='note'>Chargez un relevé PDF Desjardins, puis « Actualiser ».</p>")
    a_traiter = (rp.A_SAISIR, rp.A_ENCAISSER, rp.A_PAIE, rp.CONFIRME)
    etats = [rp.A_SAISIR, rp.A_ENCAISSER, rp.A_PAIE, rp.CONFIRME, rp.RAPPROCHE, rp.SAISI, rp.IGNORE]
    renvois = {rp.A_ENCAISSER: "→ Comptabilité > Encaissements", rp.A_PAIE: "→ module Paie de Sage"}
    prevus = _manuels_prevus(ctx)
    lignes = []
    if filtre != rp.EN_CIRCULATION:
        for m in banque:
            if filtre == A_TRAITER_LIBELLE and m.etat not in a_traiter:
                continue
            if filtre not in (A_TRAITER_LIBELLE, "Tous") and m.etat != filtre:
                continue
            renvoi = ", ".join(f"n° {n}" for n in m.sage) if m.sage else (m.compte or prevus.get(m.cle)
                                                                          or renvois.get(m.etat, ""))
            lignes.append((m.date, [e(m.date), f"<a href='?{lien}&amp;m={e(m.cle)}'>{e(m.description)}</a>"
                                    + (" ◀" if m.cle == cle_m else ""),
                                    argent(m.montant) if m.montant > 0 else "",
                                    argent(-m.montant) if m.montant < 0 else "", e(m.etat), e(renvoi)],
                           COULEURS_MOUVEMENTS.get(m.etat, "termine")))
    if filtre in (rp.EN_CIRCULATION, A_TRAITER_LIBELLE, "Tous"):
        for n, s in enumerate(sage):
            if s.rapproche:
                continue
            lignes.append((s.date, [e(s.date), f"<a href='?{lien}&amp;m=sage:{n}'>{e(s.description)}  [{e(s.source)}]"
                                               "</a>" + (" ◀" if cle_m == f"sage:{n}" else ""),
                                    argent(s.montant) if s.montant > 0 else "",
                                    argent(-s.montant) if s.montant < 0 else "", e(rp.EN_CIRCULATION),
                                    f"n° {e(s.ident)}"], "etat-propose"))
    lignes.sort(key=lambda l: l[0], reverse=True)  # le plus récent en haut (banque et Sage mêlés)
    compte = {x: sum(1 for m in banque if m.etat == x) for x in etats}
    resume = (f"{len(banque)} mouvement(s) de banque — rapprochés : {compte[rp.RAPPROCHE] + compte[rp.SAISI]}, absents "
              f"de Sage : {compte[rp.A_SAISIR]}, à encaisser sur les ventes : {compte[rp.A_ENCAISSER]}, paies absentes : "
              f"{compte[rp.A_PAIE]}, compte choisi : {compte[rp.CONFIRME]}, ignorés : {compte[rp.IGNORE]} • écritures "
              f"Sage seulement : {sum(1 for s in sage if not s.rapproche)}")
    options = "".join(f"<option{' selected' if f == filtre else ''}>{e(f)}</option>"
                      for f in [A_TRAITER_LIBELLE, "Tous"] + etats + [rp.EN_CIRCULATION])
    html += (f"<form method='get' class='barre-onglet'><input type='hidden' name='du' value='{du}'><input type='hidden' "
             f"name='au' value='{au}'><div><label>Afficher :</label><select name='filtre'>{options}</select></div>"
             "<button class='second'>Afficher</button></form>"
             f"<p class='note'>{e(resume)}</p>"
             + tableau_section(Section("Mouvements de banque et écritures Sage", ["Date", "Description", "Entrée",
                                                                                   "Sortie", "État", "Sage / compte"],
                                       [l[1] for l in lignes], classes=[l[2] for l in lignes], html=set(range(6))))
             + _fiche(ctx, etat, cle_m, du, au, filtre))
    return html


def _manuels_prevus(ctx: Contexte) -> dict[str, str]:
    """Comme PageRapprochement._manuels_prevus."""
    from ..encaissements import RegistreEncaissementsManuels
    from ..paiements_fournisseurs import RegistrePaiements

    prevus = {x["cle"]: f"→ Encaissements : encaissement manuel sur {x['facture']}"
              for x in RegistreEncaissementsManuels(ctx.racine).liste}
    for p in RegistrePaiements(ctx.racine).paiements:
        if p.avis.identifiant.startswith("releve:"):
            prevus[p.avis.identifiant[len("releve:"):]] = "→ Paiements fournisseur : paiement manuel"
    return prevus


def _fiche(ctx: Contexte, etat: dict, cle_m: str, du: str, au: str, filtre: str) -> str:
    """Carte du bas : décision pour le mouvement choisi."""
    from .. import rapprochement as rp

    if cle_m and cle_m.startswith("sage:"):
        try:
            s = etat["sage"][int(cle_m[5:])]
        except (ValueError, IndexError):
            s = None
        if s is not None:
            return (f"<div class='carte'><p>Écriture Sage n° {e(s.ident)} du {e(s.date)} : {argent(s.montant)} — "
                    f"{e(s.description)} [{e(s.source)}]<br>Pas encore vue sur un relevé : chèque ou paiement pas encore "
                    "passé, ou écriture à vérifier dans Sage.</p></div>")
    m = next((x for x in etat["banque"] if x.cle == cle_m), None)
    if m is None:
        return ("<div class='carte'><p>Sélectionnez un mouvement de banque.</p><div class='barre-onglet'><div><label>"
                "Compte Sage</label><input size='36' disabled></div><button disabled>✔ Confirmer le compte</button>"
                "<button class='second' disabled>Ignorer</button><button class='second' disabled>Remettre à traiter"
                "</button></div><div class='barre-onglet'><button class='accent' disabled>💰 Encaissement manuel"
                "</button><button class='accent' disabled>💸 Paiement fournisseur manuel</button></div></div>")
    conseil = {rp.A_ENCAISSER: "Argent des ventes (Interac ou espèces) : il s'encaisse sur les factures de vente à la "
                               "« Comptabilité > Encaissements », pas en écriture de journal.",
               rp.A_PAIE: "Dépôt de salaire : aucune paie du même montant dans Sage (source PAY…). Saisissez ou "
                          "corrigez la paie dans le module Paie de Sage, puis « Actualiser »."}.get(m.etat, "")
    comptes = "<datalist id='comptes'>" + "".join(f"<option value='{e(c)}'>" for c in etat["comptes"]) + "</datalist>"
    cache = (f"{csrf(ctx)}<input type='hidden' name='m' value='{e(m.cle)}'><input type='hidden' name='du' "
             f"value='{e(du)}'><input type='hidden' name='au' value='{e(au)}'><input type='hidden' name='filtre' "
             f"value='{e(filtre)}'>")
    html = (f"<form method='post' class='carte'>{cache}<p>{e(m.date)} : {e(m.description)}<br>"
            f"{'Entrée' if m.montant > 0 else 'Sortie'} de {argent(abs(m.montant))}   •   relevé {e(m.releve)}</p>"
            f"<div class='ligne'><div><label>Compte Sage</label><input name='compte' list='comptes' "
            f"value='{e(m.compte)}' size='40'>{comptes}</div><button name='action' value='Confirmer le compte'>✔ "
            "Confirmer le compte</button><button class='second' name='action' value='Ignorer'>Ignorer</button>"
            "<button class='second' name='action' value='Remettre à traiter'>Remettre à traiter</button></div>"
            f"<div class='boutons'><a class='ouvrir accent' href='?du={e(du)}&amp;au={e(au)}&amp;filtre={e(filtre)}"
            f"&amp;m={e(m.cle)}&amp;manuel=1'>💰 Encaissement manuel</a><button class='accent' name='action' "
            "value='Paiement fournisseur manuel'>💸 Paiement fournisseur manuel</button></div>"
            + (f"<p class='erreur-texte'>{e(m.remarque or conseil)}</p>" if (m.remarque or conseil) else "")
            + "</form>")
    if ctx.req.query.get("manuel"):
        html += _encaissement_manuel(ctx, m, cache)
    return html


def _factures_ventes(ctx: Contexte):
    """Factures de vente avec leur solde dû (comme PageRapprochement.encaissement_manuel)."""
    from ..__main__ import lire_sage
    from ..encaissements import etat_factures_sage, numero_compte_sage
    from ..facture import CLIENT
    from ..rapprochement import factures_ventes

    compte = numero_compte_sage(str(ctx.config.get("encaissements", {}).get("compte_depot", "1055")))

    def lire(base):
        dates = factures_ventes(base, CLIENT)
        etat = etat_factures_sage(base, CLIENT, compte, list(dates))
        return [(n, d, etat.get(n, {}).get("du")) for n, d in dates.items()]

    return sorted(((n, d, du) for n, d, du in lire_ou_vide(ctx, lire) if du and du > 0),
                  key=lambda x: (x[1], x[0]))


def _encaissement_manuel(ctx: Contexte, m, cache: str) -> str:
    from ..rapprochement import facture_du_jour

    if m.montant <= 0 or m.etat in ("Rapproché", "Saisi dans Sage"):
        return _message(erreur="Choisissez une entrée d'argent absente de Sage.")
    try:
        ouvertes = _factures_ventes(ctx)
    except (Exception, SystemExit) as erreur:  # noqa: BLE001
        ctx.app.noter(f"Encaissement manuel : {erreur!r}")
        return _message(erreur="Lecture des factures impossible : Sage ne répond pas sur le serveur pour l'instant.")
    if not ouvertes:
        return _message(erreur="Aucune facture de vente avec un solde dû dans Sage.")
    proposee = facture_du_jour(date.fromisoformat(m.date), {n: d for n, d, _ in ouvertes}) or next(
        (n for n, _, du in reversed(ouvertes) if du >= m.montant), ouvertes[-1][0])
    du_propose = next(du for n, _, du in ouvertes if n == proposee)
    options = "".join(f"<option value='{e(n)}'{' selected' if n == proposee else ''}>{e(n)}  —  solde {argent(du)}"
                      f"</option>" for n, _d, du in ouvertes)
    return (f"<form method='post' class='carte'>{cache}<h2>Encaissement manuel</h2><p>{e(m.date)} : "
            f"{e(m.description)}<br>Entrée de {argent(m.montant)}</p><div class='ligne'><div><label>Facture de vente"
            f"</label><select name='facture'>{options}</select></div><div><label>Montant</label><input name='montant' "
            f"value='{min(m.montant, du_propose):.2f}' size='12'></div><button name='action' value=\"Noter "
            "l'encaissement\">✔ Noter l'encaissement</button></div><p class='note'>Montant du mouvement, au plus le "
            "solde dû de la facture choisie. Il sera saisi dans Sage par « Encaisser dans Sage » (« Comptabilité > "
            "Encaissements »).</p></form>")


def _decider(ctx: Contexte, etat: dict, cle_m: str, action: str) -> str:
    from .. import rapprochement as rp

    m = next((x for x in etat["banque"] if x.cle == cle_m), None)
    if m is None:
        return _message(erreur="Sélectionnez un mouvement de banque.")
    if action == "Paiement fournisseur manuel":
        return _paiement_manuel(ctx, m)
    if action == "Noter l'encaissement":
        return _noter_encaissement(ctx, m)
    if action == "Confirmer le compte":
        compte = ctx.req.champ("compte").strip().split(" ")[0]
        if m.etat in (rp.RAPPROCHE, rp.SAISI):
            return _message(erreur="Choisissez un mouvement « Absent de Sage ».")
        if not compte.isdigit():
            return _message(erreur="Choisissez le compte Sage dans la liste (ex. 5450 Frais bancaires).")
        m.compte, m.etat = compte, rp.CONFIRME
    elif action == "Ignorer" and m.etat not in (rp.RAPPROCHE, rp.SAISI):
        m.etat = rp.IGNORE
    elif action == "Remettre à traiter" and m.etat in (rp.CONFIRME, rp.IGNORE):
        m.etat, m.compte = rp.A_SAISIR, ""
    else:
        return ""
    with ctx.app.ecriture:
        registre = rp.RegistreReleves(ctx.racine)
        registre.retenir(m)
        registre.enregistrer()
    return ""


def _paiement_manuel(ctx: Contexte, m) -> str:
    """Comme PageRapprochement.paiement_manuel : sortie d'argent ajoutée à Paiements fournisseurs."""
    from ..paiements_courriel import AvisPaiement
    from ..paiements_fournisseurs import RegistrePaiements

    if m.montant >= 0 or m.etat in ("Rapproché", "Saisi dans Sage"):
        return _message(erreur="Choisissez une sortie d'argent absente de Sage.")
    morceaux = [x.strip() for x in m.description.split("/") if x.strip()]
    avis = AvisPaiement(identifiant=f"releve:{m.cle}", date_courriel=m.date, date_virement=m.date,
                        montant=-m.montant, beneficiaire=morceaux[1] if len(morceaux) > 1 else m.description,
                        reference=m.releve, message=m.description, source="Relevé Desjardins")
    with ctx.app.ecriture:
        registre = RegistrePaiements(ctx.racine)
        ajoute = registre.ajouter([avis])
        registre.enregistrer()
    if not ajoute:
        return _message(erreur="Ce mouvement est déjà dans « Comptabilité > Paiements fournisseur ».")
    return ("<p class='ok'>Paiement de " + e(argent(-m.montant)) + " ajouté à « Paiements fournisseur » : choisissez "
            "le fournisseur et la facture, confirmez, puis « Payer dans Sage ». <a href='/paiements-fournisseurs'>"
            "Ouvrir « Paiements fournisseur »</a></p>")


def _noter_encaissement(ctx: Contexte, m) -> str:
    from ..encaissements import RegistreEncaissementsManuels, origine

    numero = ctx.req.champ("facture")
    try:
        ouvertes = _factures_ventes(ctx)
        du = next(d for n, _x, d in ouvertes if n == numero)
        valeur = Decimal(ctx.req.champ("montant").replace(",", ".").replace(" ", "").replace("$", "")
                         ).quantize(Decimal("0.01"))
    except StopIteration:
        return _message(erreur="Facture introuvable : rouvrez « Encaissement manuel ».")
    except (Exception, SystemExit):  # noqa: BLE001
        return _message(erreur="Montant invalide.")
    if valeur <= 0 or valeur > m.montant or valeur > du:
        return _message(erreur=f"Le montant doit être positif, sans dépasser le mouvement ni le solde dû de la facture "
                               f"({argent(du)}).")
    with ctx.app.ecriture:
        registre = RegistreEncaissementsManuels(ctx.racine)
        registre.ajouter(m.cle, date.fromisoformat(m.date), valeur, numero, origine(m))
        registre.enregistrer()
    return ("<p class='ok'>Encaissement de " + e(argent(valeur)) + f" sur {e(numero)} noté. Il sera saisi dans Sage par "
            "« Encaisser dans Sage » (« Comptabilité > Encaissements »). <a href='/encaissements'>Ouvrir "
            "« Encaissements »</a></p>")


def _rapport(ctx: Contexte, choix) -> Reponse:
    """« 📗 Rapport Excel » : rapprochement.ecrire_rapport, envoyé au navigateur."""
    import tempfile
    from urllib.parse import quote

    from .. import rapprochement as rp

    if not ctx.reg.peut_exporter(ctx.u):
        return Reponse(403, page(ctx, "Rapprochement bancaire", _message(
            erreur="Votre profil ne permet pas d'exporter les données.")))
    etat = _lire(ctx, choix)
    if not etat["releves"] or not etat["periode"]:
        return Reponse(corps=page(ctx, "Rapprochement bancaire", _message(erreur="Cliquez d'abord sur « Actualiser ».")))
    debut, fin = etat["periode"]
    chiffres = rp.resume(etat["banque"], etat["sage"], *etat["soldes"], debut=debut)
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as dossier:
        chemin = Path(dossier) / "rapport.xlsx"
        rp.ecrire_rapport(chemin, etat["releves"], etat["banque"], etat["sage"], chiffres, (debut, fin))
        contenu = chemin.read_bytes()
    nom = f"rapprochement_1055_{debut}_{fin}.xlsx"
    return Reponse(corps=contenu, type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                   entetes={"Content-Disposition": f"attachment; filename=\"{nom}\"; filename*=UTF-8''{quote(nom)}"})


def mouvement(ctx: Contexte) -> Reponse:
    """Ancienne adresse de la fiche d'un mouvement : la fiche est maintenant sous la liste."""
    from urllib.parse import urlencode

    from .serveur import redirection

    q = {k: ctx.req.query.get(k, "") for k in ("du", "au")}
    return redirection("/rapprochement?" + urlencode({**q, "filtre": "Tous", "m": ctx.req.query.get("cle", "")}))


FONCTIONS = [
    Fonction("/rapprochement", "Rapprochement", "rapprochement", rapprochement, "🏦", "Comptabilité", menu=False,
             page_entiere=True),
    Fonction("/mouvement", "Rapprochement", "rapprochement", mouvement, "🏦", "Comptabilité", menu=False,
             page_entiere=True),
]
WEB = {"Rapprochement": "/rapprochement"}
