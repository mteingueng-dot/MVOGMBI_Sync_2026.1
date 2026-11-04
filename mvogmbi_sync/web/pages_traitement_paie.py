"""8e vague de l'application web (fin) : Traitement de la paie (comme fenetre_paie.FenetrePaie : heures planifiées et
réalisées, heures validées et chèques de paie dans Sage, paies de Sage et bulletins envoyés à chaque employé, fin
d'année T4 / RL-1 sur les formulaires officiels) et Fin d'emploi et relevé d'emploi (comme fenetres_gestion2).
Mêmes règles : jamais de paie dans le futur, jamais deux fois la même paie, un bulletin à son seul destinataire.
"""

from __future__ import annotations

import tempfile
from datetime import date, timedelta
from pathlib import Path

from .consultations import Section, sections_html
from .pages import Contexte, Fonction, argent, csrf, page, tableau
from .pages_compta import _message, action_permise
from .pages_paie import _paies_annee, _reference, fiche_html
from .serveur import Reponse, echapper as e

TRAITER, ENVOYER = "Traiter la paie dans Sage", "Envoyer les bulletins par courriel"


def _periodes(ctx: Contexte) -> list[date]:
    from .. import paie_temps as pt

    debut = pt.debut_periode(date.today(), _reference(ctx.racine))
    return [debut - timedelta(days=pt.JOURS_PERIODE * i) for i in range(13)]


def _onglets(actif: str) -> str:
    """Onglets de la fenêtre « Traitement de la paie » (fenetre_paie.FenetrePaie)."""
    from .pages_rapports_web import onglets

    return onglets(actif)


def traitement(ctx: Contexte) -> Reponse:
    from .. import paie as pa
    from .. import paie_temps as pt
    from ..calendrier_paie import Calendrier
    from ..fenetre_paie import paie_dans_le_futur
    from ..planning import Planning
    from . import taches

    periodes = _periodes(ctx)
    try:
        debut = date.fromisoformat(ctx.req.query.get("periode") or ctx.req.champ("periode"))
    except (TypeError, ValueError):
        debut = periodes[1]  # dernière période terminée
    fin = debut + timedelta(days=pt.JOURS_PERIODE - 1)
    registre = pt.Registre(ctx.racine)
    feuilles = pt.feuilles(registre, debut)
    extras = pa.extras_periode(ctx.racine, feuilles)
    onglet = ctx.req.query.get("onglet") or ctx.req.champ("onglet")
    message = ""
    if ctx.req.methode == "POST":
        try:
            if not action_permise(ctx, TRAITER):
                raise ValueError(f"Votre profil n'a pas le droit « {TRAITER} ».")
            jour = date.fromisoformat(ctx.req.champ("jour"))
            probleme = paie_dans_le_futur(fin, jour, date.today())
            if probleme:
                raise ValueError(probleme)
            approuvees = [f for f in feuilles if f.etat == pt.APPROUVEE and f.total > 0]
            a_payer = [f for f in approuvees if f.employe.numero_sage]
            if not a_payer:
                raise ValueError("Aucune feuille approuvée d'un employé relié à Sage pour cette période.")
            from ..robot_paie import PaieATraiter, dans_sage, numero_desjardins

            def normales(f):  # heures normales + jours fériés + congés payés (payés au taux régulier)
                feries, conges = extras.get(f.employe.id, (pa.ZERO, pa.ZERO))
                return f.normales + feries + conges

            paies = [PaieATraiter(f.employe.numero_sage, debut.isoformat(), fin.isoformat(), jour.isoformat(),
                                  str(normales(f)), str(f.supplementaires), f.employe.id,
                                  numero_desjardins(jour.isoformat())) for f in a_payer]

            def traiter(journal):
                bilan = dans_sage(ctx.racine, ctx.config, [], paies)
                resultats, lignes = bilan.get("paies", []), []
                traitees = [p for p in paies if p.__dict__ not in bilan.get("deja", [])]
                with ctx.app.ecriture:
                    reg = pt.Registre(ctx.racine)
                    for rang, p in enumerate(traitees):
                        r = resultats[rang] if rang < len(resultats) else {"messages": ["non traité"]}
                        if r.get("fait"):
                            approbation = reg.feuilles.get(debut.isoformat(), {}).get(p.employe)
                            if approbation:
                                approbation.update({"etat": pt.ENVOYEE, "paie": p.date_cheque, "net": r.get("net", "")})
                            lignes.append(f"✔ {p.nom_sage} : brut {r.get('brut')} $, net {r.get('net')} $")
                        else:
                            lignes.append(f"✘ {p.nom_sage} : " + " ; ".join(r.get("messages") or ["non traité"]))
                    reg.enregistrer()
                lignes += [f"• {d['nom_sage']} : déjà traitée pour cette période" for d in bilan.get("deja", [])]
                ctx.app.memoire.pop(("paies", jour.year), None)
                return lignes + ["Bulletins : « Paies dans Sage » (date des chèques) > « Envoyer les bulletins »."]

            return taches.lancer(ctx, f"Chèques de paie du {debut} au {fin}", traiter,
                                 f"/paies-sage?du={jour}&au={jour}", sage=True)
        except ValueError as erreur:
            message = _message(erreur=str(erreur))
    options = "".join(f"<option value='{p}'{' selected' if p == debut else ''}>{p} au "
                      f"{p + timedelta(days=pt.JOURS_PERIODE - 1)}</option>" for p in periodes)
    from ..fenetre_paie import VUES

    vue = ctx.req.query.get("vue") or VUES[0]
    choix_vue = ("" if onglet == "validees" else "<div><label>Affichage</label><select name='vue'>" + "".join(
        f"<option{' selected' if v == vue else ''}>{e(v)}</option>" for v in VUES) + "</select></div>")
    choix = (f"<form class='ligne' method='get'><input type='hidden' name='onglet' value='{e(onglet)}'><div><label>"
             f"Période de paie</label><select name='periode'>{options}</select></div>{choix_vue}<button "
             "class='second'>Afficher</button></form>")
    if onglet == "validees":
        lignes = pa.validees(feuilles, extras)
        approuvees = [l for l in lignes if l[8] != pt.A_APPROUVER]
        prevue = Calendrier(ctx.racine).paie_de_periode(debut)
        jour = min(prevue.jour if prevue else date.today(), date.today())
        sans_lien = [f.employe.nom for f in feuilles if f.etat == pt.APPROUVEE and not f.employe.numero_sage]
        corps = (_onglets("Heures validées") + message + choix
                 + sections_html([Section(f"Heures validées du {debut} au {fin}", pa.ENTETES_VALIDEES,
                                          [l[:3] + [pa.heures(x) for x in l[3:8]] + l[8:] for l in lignes],
                                          f"{len(approuvees)} feuille(s) approuvée(s) ; les autres attendent "
                                          "l'approbation (Paie > Feuilles de temps).")])
                 + (_message(erreur="Sans lien avec Sage (ignorés) : " + ", ".join(sans_lien)) if sans_lien else "")
                 + f"<form method='post' class='ligne'>{csrf(ctx)}<input type='hidden' name='periode' value='{debut}'>"
                   "<input type='hidden' name='onglet' value='validees'>"
                   f"<div><label>Date des chèques</label><input type='date' name='jour' value='{jour}' "
                   f"max='{date.today()}'></div><button>Traiter la paie dans Sage</button></form><p class='note'>Sage "
                   "doit être fermé sur le serveur : l'application l'ouvre elle-même. Une paie déjà traitée pour la "
                   "période ne l'est jamais deux fois.</p>")
        return Reponse(corps=page(ctx, "Traitement de la paie", corps))
    planning = Planning(ctx.racine)
    if vue == VUES[1]:
        lignes = [[l[0], l[1], l[2], pa.heures(l[3]), pa.heures(l[4]), l[5]] for l in pa.jours(feuilles, planning)]
        section = Section(f"Heures par jour du {debut} au {fin}", pa.ENTETES_JOURS, lignes)
    else:
        section = Section(f"Heures par employé et par semaine du {debut} au {fin}", pa.ENTETES_SEMAINES,
                          [[l.debut, l.fin, l.employe, pa.heures(l.planifiees), pa.heures(l.realisees), l.ecart, l.etat]
                           for l in pa.semaines(feuilles, planning)])
    anomalies = sum(len(f.anomalies) for f in feuilles)
    corps = (_onglets("Heures planifiées et réalisées") + message + choix
             + sections_html([section])
             + (_message(erreur=f"{anomalies} anomalie(s) de pointage à corriger dans « Feuilles de temps ».")
                if anomalies else "")
             + "<p class='note'>Heures réalisées = pointages de l'application ; heures planifiées = planning mensuel."
               "</p>")
    return Reponse(corps=page(ctx, "Traitement de la paie", corps))


def paies_sage(ctx: Contexte) -> Reponse:
    from .. import paie as pa
    from .. import paie_temps as pt
    from . import taches

    try:
        du = date.fromisoformat(ctx.req.query.get("du") or ctx.req.champ("du"))
        au = date.fromisoformat(ctx.req.query.get("au") or ctx.req.champ("au"))
    except (TypeError, ValueError):
        au = date.today()
        du = au - timedelta(days=30)
    try:
        paies_annee = [p for p in _paies_annee(ctx, du.year) if p.jour <= au]
    except (Exception, SystemExit) as erreur:  # noqa: BLE001
        ctx.app.noter(f"Paies Sage : {erreur!r}")
        return Reponse(corps=page(ctx, "Traitement de la paie", _onglets("Paies dans Sage") + _message(
            erreur="Les paies se lisent dans Sage, qui ne répond pas sur le serveur pour l'instant.")))
    paies = [p for p in paies_annee if p.jour >= du]
    registre = pt.Registre(ctx.racine)
    message = ""
    if ctx.req.methode == "POST":
        choisies = [p for p in paies if str(p.ident) in set(ctx.req.champs("paie"))]
        if not action_permise(ctx, ENVOYER):
            message = _message(erreur=f"Votre profil n'a pas le droit « {ENVOYER} ».")
        elif not choisies:
            message = _message(erreur="Cochez une ou plusieurs paies.")
        else:
            envois = [(p, x) for p in choisies if (x := pa.employe_de(p, registre.employes)) and x.courriel]
            sans = [p.employe for p in choisies if not ((x := pa.employe_de(p, registre.employes)) and x.courriel)]
            bulletins = [(p, x, fiche_html(ctx, registre, x, p, paies_annee)) for p, x in envois]

            def envoyer(journal):
                from ..export_tableau import pdf_depuis_html

                resultats = []
                for p, x, fiche in bulletins:
                    try:
                        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as dossier:
                            chemin = Path(dossier) / "bulletin.pdf"
                            pdf_depuis_html(fiche, chemin)
                            contenu = chemin.read_bytes()
                        pa.envoyer_bulletin(ctx.config, x.courriel, x.nom, p, contenu)
                        pa.noter_envoi(ctx.racine, p, x.courriel)
                        resultats.append(f"✔ {p.employe} → {x.courriel}")
                    except Exception as exc:  # noqa: BLE001
                        resultats.append(f"✘ {p.employe} : {exc}")
                return resultats + ([f"Sans courriel (non envoyés) : {', '.join(sans)}"] if sans else [])

            return taches.lancer(ctx, f"Bulletins de paie ({len(envois)})", envoyer, f"/paies-sage?du={du}&au={au}")
    deja = pa.bulletins_envoyes(ctx.racine)
    lignes = []
    for p in sorted(paies, key=lambda p: (p.jour, p.employe), reverse=True):
        x = pa.employe_de(p, registre.employes)
        lien = (f"<a href='/bulletin?employe={e(x.id)}&annee={p.jour.year}&paie={p.ident}'>{p.jour:%Y-%m-%d}</a>"
                if x else f"{p.jour:%Y-%m-%d}")
        lignes.append([f"<input type='checkbox' name='paie' value='{p.ident}'>", lien, e(p.source), e(p.employe),
                       argent(p.brut), argent(p.total_retenues), argent(p.net),
                       "envoyé" if pa.cle_bulletin(p) in deja else "", e(x.courriel if x else "")])
    corps = (_onglets("Paies dans Sage") + message
             + f"<form class='ligne' method='get'><div><label>Du</label><input type='date' name='du' value='{du}'></div>"
               f"<div><label>Au</label><input type='date' name='au' value='{au}'></div><button class='second'>Afficher"
               "</button></form>"
             + f"<form method='post'>{csrf(ctx)}<input type='hidden' name='du' value='{du}'><input type='hidden' "
               f"name='au' value='{au}'>"
             + tableau(["", "Date", "Source", "Employé", "Brut", "Retenues", "Net", "Bulletin", "Courriel"], lignes,
                       {4, 5, 6})
             + "<div class='boutons'><button>Envoyer les bulletins cochés (chacun à son employé)</button></div></form>"
               "<p class='note'>Cliquez sur une date pour le bulletin (imprimable par le navigateur).</p>")
    return Reponse(corps=page(ctx, "Traitement de la paie", corps))


def fin_annee(ctx: Contexte) -> Reponse:
    from .. import feuillets as fe
    from .. import paie_temps as pt
    from ..entreprise import lire as entreprise
    from ..fin_emploi import ENTETES_CONCORDANCE, concordance
    from . import taches

    try:
        annee = int(ctx.req.query.get("annee") or ctx.req.champ("annee") or date.today().year - 1)
    except ValueError:
        annee = date.today().year - 1
    try:
        paies = _paies_annee(ctx, annee)
    except (Exception, SystemExit) as erreur:  # noqa: BLE001
        ctx.app.noter(f"Fin d'année : {erreur!r}")
        return Reponse(corps=page(ctx, "Traitement de la paie", _onglets("Fin d'année (T4 / RL-1)") + _message(
            erreur="Les paies se lisent dans Sage, qui ne répond pas sur le serveur pour l'instant.")))
    registre = pt.Registre(ctx.racine)
    feuillets = fe.calculer(paies, annee, registre.employes)
    if ctx.req.methode == "POST":
        choisis = [f for f in feuillets if f.employe in set(ctx.req.champs("employe"))]
        if not choisis:
            return Reponse(corps=page(ctx, "Traitement de la paie", _message(erreur="Cochez un ou plusieurs employés.")))
        if ctx.req.champ("action") == "PDF":
            contenu = fe.pdf_officiels(choisis, entreprise(ctx.racine), fe.numero_employeur(ctx.racine),
                                       racine=ctx.racine, config_toml=ctx.config)
            return Reponse(corps=contenu, type="application/pdf",
                           entetes={"Content-Disposition": f"inline; filename=T4_RL-1_{annee}.pdf"})
        if not action_permise(ctx, ENVOYER):
            return Reponse(corps=page(ctx, "Traitement de la paie", _message(
                erreur=f"Votre profil n'a pas le droit « {ENVOYER} ».")))

        def envoyer(journal):
            resultats = []
            employeur, numero = entreprise(ctx.racine), fe.numero_employeur(ctx.racine)
            for f in choisis:
                if not f.courriel:
                    resultats.append(f"✘ {f.employe} : pas de courriel")
                    continue
                try:
                    fe.envoyer(ctx.config, f, fe.pdf_officiels([f], employeur, numero, racine=ctx.racine,
                                                               config_toml=ctx.config))
                    fe.noter_envoi(ctx.racine, f)
                    resultats.append(f"✔ {f.employe} → {f.courriel}")
                except Exception as exc:  # noqa: BLE001
                    resultats.append(f"✘ {f.employe} : {exc}")
            return resultats

        return taches.lancer(ctx, f"T4 et Relevés 1 {annee}", envoyer, f"/fin-annee?annee={annee}")
    deja = fe.envoyes(ctx.racine)
    lignes = [[f"<input type='checkbox' name='employe' value='{e(f.employe)}'>", e(f.employe), argent(f.brut),
               e(f.courriel or "—"), "envoyé" if f.cle in deja else ""] for f in feuillets]
    corps = (_onglets("Fin d'année (T4 / RL-1)")
             + f"<form class='ligne' method='get'><div><label>Année</label><input name='annee' value='{annee}' "
               "size='5'></div><button class='second'>Calculer</button></form>"
             + sections_html([Section(f"Concordance {annee}", ENTETES_CONCORDANCE,
                                      concordance(paies, registre, annee))])
             + f"<form method='post'>{csrf(ctx)}<input type='hidden' name='annee' value='{annee}'><h2>T4 et Relevé 1</h2>"
             + tableau(["", "Employé", "Brut", "Courriel", "Envoi"], lignes, {2})
             + "<div class='boutons'><button class='second' name='action' value='PDF'>PDF (formulaires officiels)"
               "</button><button name='action' value='Envoyer'>Envoyer à chaque employé</button></div></form>"
               "<p class='note'>Le NAS n'est jamais écrit. Les feuillets transmis aux gouvernements restent ceux de "
               "Sage.</p>")
    return Reponse(corps=page(ctx, "Traitement de la paie", corps))


def fin_emploi(ctx: Contexte) -> Reponse:
    from .. import fin_emploi as fe
    from .. import paie_temps as pt

    registre = pt.Registre(ctx.racine)
    employes = registre.actifs()
    message, resultat = "", ""
    ident = ctx.req.query.get("employe") or ctx.req.champ("employe")
    employe = next((x for x in registre.employes if x.id == ident), None)
    if ctx.req.methode == "POST" and employe is not None:
        if ctx.req.champ("action") == "Désactiver":
            if not action_permise(ctx, "Désactiver un employé"):
                message = _message(erreur="Votre profil n'a pas le droit « Désactiver un employé ».")
            else:
                with ctx.app.ecriture:
                    reg = pt.Registre(ctx.racine)
                    reg.employe(employe.id).actif = False
                    reg.enregistrer()
                message = _message(f"{employe.nom} désactivé (ses heures sont gardées).")
    if employe is not None and ctx.req.query.get("dernier"):
        try:
            dernier = date.fromisoformat(ctx.req.query["dernier"])
            paies = []
            for annee in {dernier.year, dernier.year - 1}:
                try:
                    paies += _paies_annee(ctx, annee)
                except (Exception, SystemExit):  # noqa: BLE001 — Sage absent : heures seulement
                    pass
            lignes, sous = fe.preparation_re(registre, employe, paies, dernier, ctx.req.query.get("code", "A"))
            resultat = sections_html([Section(f"Préparation du relevé d'emploi : {sous}", ["", ""], lignes)])
        except ValueError:
            message = _message(erreur="Dernier jour au format AAAA-MM-JJ.")
    options = "".join(f"<option value='{e(x.id)}'{' selected' if employe and x.id == employe.id else ''}>{e(x.nom)}"
                      "</option>" for x in employes)
    codes = "".join(f"<option value='{e(c)}'>{e(c)} — {e(t)}</option>" for c, t in fe.MOTIFS_RE.items())
    corps = (message + f"<form class='ligne' method='get'><div><label>Employé</label><select name='employe'>{options}"
             f"</select></div><div><label>Dernier jour travaillé</label><input type='date' name='dernier' "
             f"value='{date.today()}'></div><div><label>Motif</label><select name='code'>{codes}</select></div><button>"
             "Préparer le relevé d'emploi</button></form>" + resultat
             + (f"<form method='post' class='boutons'>{csrf(ctx)}<input type='hidden' name='employe' "
                f"value='{e(employe.id)}'><button class='second' name='action' value='Désactiver'>Désactiver "
                f"{e(employe.nom)}</button></form>" if employe and employe.actif else "")
             + "<p class='note'>Le RE lui-même se produit dans Sage Paie ou sur le site de Service Canada (RE Web) ; "
               "cette page en prépare les chiffres (heures assurables des 53 semaines, rémunération des 27 dernières "
               "paies).</p>")
    return Reponse(corps=page(ctx, "Fin d'emploi et relevé d'emploi", corps))


FONCTIONS = [
    Fonction("/traitement-paie", "Traitement de la paie", "rapprochement", traitement, "💵", "Paie", menu=False),
    Fonction("/paies-sage", "Traitement de la paie", "rapprochement", paies_sage, "💵", "Paie", menu=False),
    Fonction("/fin-annee", "Traitement de la paie", "rapprochement", fin_annee, "💵", "Paie", menu=False),
    Fonction("/fin-emploi", "Fin d'emploi et relevé d'emploi", "paiements", fin_emploi, "🚪", "Paie", menu=False),
]
WEB = {"Traitement de la paie": "/traitement-paie", "Fin d'emploi et relevé d'emploi": "/fin-emploi"}
