"""Consultations de l'application web (2e vague de « toutes les fonctionnalités dans l'application web, idem dans
l'application bureau », demande du propriétaire du 2026-11-03) : listes, interrogations de compte, rapports de
comptabilité et de paie, audit, journal des opérations.

Chaque consultation reprend la fonction de calcul de la fenêtre Windows du même nom (mêmes chiffres) ; la page web
générique (`consulter`) n'ajoute que les filtres et le tableau. Sage est lu par `lire_sage(..., ouvrir=False)` :
une page web n'ouvre jamais Sage elle-même ; lecture gardée 5 min.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import Callable
from urllib.parse import urlencode

from .pages import Contexte, Fonction, argent, page
from .serveur import Reponse, echapper as e

DUREE = 300  # s
MOTS_QUANTITE = ("Quantité", "Cumul", "Vendu", "Stock", "Besoin", "À acheter", "Sold", "Factures", "Jours")


@dataclass
class Section:
    titre: str
    entetes: list[str]
    lignes: list[list]
    note: str = ""
    classes: list[str] | None = None  # classe CSS de chaque ligne (couleurs des tableaux Windows)
    html: set = field(default_factory=set)  # colonnes déjà en HTML (liens) : ni formatées ni échappées


@dataclass
class Consultation:
    chemin: str
    titre: str            # entrée du menu de l'application Windows (droits)
    page: str             # clé de page de cette entrée
    filtres: tuple        # « periode », « au », « mois », « client », « fournisseur », « article », « cote », « vue »,
    calcul: Callable      # « texte », « source » ; calcul(ctx, valeurs) -> list[Section]
    explication: str = ""
    icone: str = "📋"
    rubrique: str = ""
    sans_sage: bool = False
    defauts: dict = field(default_factory=dict)
    choix: dict = field(default_factory=dict)  # filtre -> (libellé, valeurs) : liste de choix


# --------------------------------------------------------------------------------------------- outils
def sage(ctx: Contexte, fonction, cle):
    from ..__main__ import lire_sage

    cle = ("sage",) + tuple(cle)
    gardee = ctx.app.memoire.get(cle)
    if gardee and time.time() - gardee[0] < DUREE:
        return gardee[1]
    resultat = lire_sage(ctx.config, fonction, ouvrir=False)
    ctx.app.memoire[cle] = (time.time(), resultat)
    return resultat


def formater(entete: str, v) -> str:
    """Comme le tableau de l'application Windows (page_rapports.remplir)."""
    if v is None:
        return ""
    if isinstance(v, bool):
        return "Oui" if v else "Non"
    if isinstance(v, Decimal):
        if "%" in entete:
            return f"{v} %".replace(".", ",")
        if (any(m in entete for m in MOTS_QUANTITE) or "qté" in entete.casefold()) and "Valeur" not in entete \
                and not entete.startswith("Solde") and "Montant" not in entete:
            return f"{v.normalize():f}".replace(".", ",")
        return argent(v)
    if isinstance(v, date):
        return v.isoformat()
    return str(v)


def _numerique(lignes: list[list], i: int) -> bool:
    return any(isinstance(l[i], (Decimal, int)) and not isinstance(l[i], bool) for l in lignes if i < len(l))


def tableau_section(s: Section, limite: int = 2000) -> str:
    if not s.lignes:
        return f"<h2>{e(s.titre)}</h2><p>Aucune ligne.</p>" + (f"<p class='note'>{e(s.note)}</p>" if s.note else "")
    nombres = {i for i in range(len(s.entetes)) if _numerique(s.lignes, i)}
    th = "".join(f"<th class='{'n' if i in nombres else ''}'>{e(c)}</th>" for i, c in enumerate(s.entetes))
    corps = []
    for rang, ligne in enumerate(s.lignes[:limite]):
        total = str(ligne[0]).startswith("Total")
        classe = s.classes[rang] if s.classes and rang < len(s.classes) else ""
        cellules = "".join(f"<td class='{'n' if i in nombres else ''}'>"
                           f"{v if i in s.html else e(formater(s.entetes[i], v))}</td>"
                           for i, v in enumerate(ligne[:len(s.entetes)]))
        corps.append(f"<tr class='{'total' if total else classe}'>{cellules}</tr>")
    reste = (f"<p class='note'>{len(s.lignes) - limite} ligne(s) de plus : précisez les filtres.</p>"
             if len(s.lignes) > limite else "")
    return (f"<h2>{e(s.titre)} <span class='etat'>{len(s.lignes)}</span></h2>"
            f"<div class='defile'><table><tr>{th}</tr>{''.join(corps)}</table></div>{reste}"
            + (f"<p class='note'>{e(s.note)}</p>" if s.note else ""))


def _date(texte: str, defaut: date) -> date:
    try:
        return date.fromisoformat(texte)
    except (TypeError, ValueError):
        return defaut


def _mois(texte: str) -> tuple[int, int]:
    try:
        annee, mois = (int(x) for x in texte.split("-"))
        if 1 <= mois <= 12:
            return annee, mois
    except (AttributeError, ValueError):
        pass
    return date.today().year, date.today().month


def _noms(ctx: Contexte, table: str) -> list[str]:
    from .. import rapports as rp

    return sage(ctx, lambda b: rp.noms(b, table), ("noms", table))


# --------------------------------------------------------------------------------------------- calculs
def _tiers(cote):
    def calcul(ctx, v):
        from .. import listes_sage as ls

        entetes, lignes = sage(ctx, lambda b: ls.tiers(b, cote), ("tiers", cote))
        return [Section("Clients" if cote == "clients" else "Fournisseurs", entetes, _cherche(lignes, v))]
    return calcul


def _cherche(lignes: list[list], v: dict) -> list[list]:
    texte = (v.get("texte") or "").strip().casefold()
    return [l for l in lignes if not texte or any(texte in str(c).casefold() for c in l)]


def _documents(cote):
    def calcul(ctx, v):
        from .. import listes_sage as ls

        du, au = v["du"], v["au"]
        if cote == "stock":
            entetes, lignes = sage(ctx, lambda b: ls.documents_stock(b, du, au), ("docstock", du, au))
        else:
            entetes, lignes = sage(ctx, lambda b: ls.documents(b, cote, du, au), ("docs", cote, du, au))
        return [Section(f"Du {du} au {au}", entetes, _cherche(lignes, v))]
    return calcul


def _articles(ctx, v):
    from .. import listes_sage as ls
    from ..analyse_articles import categories
    from ..couts_sage import correspondance

    liens: dict[str, int] = {}
    try:
        for numero in correspondance(ctx.racine).values():
            liens[numero] = liens.get(numero, 0) + 1
    except Exception:  # noqa: BLE001 — correspondance absente : colonne vide
        pass
    cats = categories(ctx.racine)
    entetes, lignes = sage(ctx, lambda b: ls.articles(b, cats, {n: [f"{k} relié(s)"] for n, k in liens.items()}),
                           ("articles",))
    return [Section("Articles de Sage", entetes, _cherche(lignes, v))]


def _livre(ctx, v):
    from .. import listes_sage as ls
    from ..analyse_articles import categories

    au = v["au"]
    entetes, lignes = sage(ctx, lambda b: ls.livre_inventaire(b, au, categories(ctx.racine))[:2], ("livre", au))
    return [Section(f"Stock et valeur au {au}", entetes, _cherche(lignes, v),
                    "Quantité à la date (stock actuel moins les mouvements postérieurs), valeur au CUMP actuel.")]


def _interrogation(genre):
    def calcul(ctx, v):
        from .. import rapports as rp

        nom = (v.get(genre) or "").strip()
        if not nom:
            return [Section(f"Choisissez {'un' if genre != 'article' else 'un'} {genre}", [], [])]
        fonction = {"client": rp.mouvements_client, "fournisseur": rp.mouvements_fournisseur,
                    "article": rp.mouvements_article}[genre]
        entetes, lignes = sage(ctx, lambda b: fonction(b, nom, v["du"], v["au"]), ("interro", genre, nom, v["du"],
                                                                                      v["au"]))
        return [Section(f"{nom} : du {v['du']} au {v['au']}", entetes, lignes)]
    return calcul


def _age(ctx, v):
    from .. import comptabilite as cp

    cote = "fournisseurs" if v.get("cote") == "Fournisseurs" else "clients"
    factures = sage(ctx, lambda b: cp.factures_ouvertes(b, cote, date.today()), ("age", cote))
    retard = sum((f.solde for f in factures if f.retard > 0), Decimal(0))
    note = f"{len(factures)} facture(s) ouverte(s), dont {argent(retard)} en retard. Échéance = date + délai du tiers."
    if v.get("vue") == "Par facture":
        return [Section(f"Âge des comptes {cote}", ["Tiers", "Facture", "Date", "Échéance", "Jours de retard",
                                                     "Tranche", "Montant dû"],
                        [[f.tiers, f.numero, f.date, f.echeance, max(f.retard, 0), f.tranche, f.solde]
                         for f in factures], note)]
    return [Section(f"Âge des comptes {cote}", cp.ENTETES_AGE, cp.age_par_tiers(factures), note)]


def _taxes(ctx, v):
    from .. import comptabilite as cp

    du, au = v["du"], v["au"]
    lignes = sage(ctx, lambda b: cp.declaration_taxes(b, du, au), ("taxes", du, au))
    try:
        clover = cp.taxes_clover(ctx.racine, du, au)
        note = f"Contrôle : taxes encaissées par Clover sur la période : {argent(clover)}."
    except Exception:  # noqa: BLE001
        note = ""
    return [Section(f"Déclaration TPS/TVQ du {du} au {au}", cp.ENTETES_TAXES, lignes, note)]


def _tresorerie(ctx, v):
    from .. import comptabilite as cp

    cle = ("tresorerie", date.today())
    gardee = ctx.app.memoire.get(cle)
    lignes, info = gardee[1] if gardee and time.time() - gardee[0] < DUREE else cp.calculer_tresorerie(ctx.racine,
                                                                                                       ctx.config)
    ctx.app.memoire[cle] = (time.time(), (lignes, info))
    return [Section(f"Prévision de trésorerie au {date.today()}", cp.ENTETES_TRESORERIE, lignes,
                    f"Factures en retard comptées en 1re semaine : {argent(info['en_retard'])} ; paies : "
                    f"{argent(info['paie_semaine'])} par semaine.")]


def _cloture(ctx, v):
    from .. import comptabilite as cp

    annee, mois = _mois(v.get("mois"))
    controles, resultats = sage(ctx, lambda b: (cp.controles_cloture(ctx.racine, b, annee, mois),
                                                cp.etat_resultats(b, annee, mois)), ("cloture", annee, mois))
    a_faire = sum(1 for c in controles if c[1] == cp.A_FAIRE)
    return [Section(f"Clôture du mois {annee}-{mois:02d}", cp.ENTETES_CLOTURE, controles,
                    f"{a_faire} point(s) à faire avant de clôturer." if a_faire else "Tous les contrôles sont faits."),
            Section("État des résultats", cp.entetes_resultats(annee, mois), resultats)]


def _retenues(ctx, v):
    from .. import retenues as rt

    annee, mois = _mois(v.get("mois"))
    lignes, info = sage(ctx, lambda b: rt.etat(b, annee, mois), ("retenues", annee, mois))
    remises = info.get("a_remettre", {})
    note = (f"À remettre au plus tard le {info['echeance']} : "
            + " ; ".join(f"{o} {argent(m)}" for o, m in remises.items())) if remises else "Aucune paie ce mois-ci."
    return [Section(f"Retenues à la source de {annee}-{mois:02d}", rt.ENTETES, lignes, note),
            Section("Salaires du mois", ["Compte de charge", "Montant du mois"],
                    info["charges"] + ([["Total", info["salaires"]]] if info["charges"] else []))]


def _suivi_remises(ctx, v):
    from .. import retenues as rt

    lignes = sage(ctx, lambda b: rt.suivi(b, date.today()), ("suivi_remises", date.today()))
    alertes = rt.alertes(lignes, date.today())
    return [Section("Suivi des remises (12 derniers mois)", rt.ENTETES_SUIVI, lignes,
                    ("⚠ " + " ; ".join(alertes)) if alertes else "Aucune remise en retard ni à faire d'ici 5 jours.")]


def _plan(ctx, v):
    from .. import plan_comptable as pc

    comptes = sage(ctx, pc.lire, ("plan",))
    lignes = [[c.numero, c.nom, c.classe, c.type, "Inactif" if c.inactif else "Actif", c.solde] for c in comptes]
    return [Section("Plan comptable de Sage", ["N°", "Compte", "Classe", "Type", "État", "Solde"], _cherche(lignes, v),
                    "Types : H en-tête, L sous-groupe, R groupe, S / T totaux, X bénéfice. Ajouter, modifier ou "
                    "désactiver un compte : application complète.")]


def _audit(ctx, v):
    from .. import audit

    entrees = audit.lire(ctx.racine)
    douteuses = set(audit.verifier(entrees))
    du, au = str(v["du"]), str(v["au"])
    lignes = [[x.moment, x.utilisateur, x.poste, x.fenetre, x.action, x.detail,
               "⚠ modifiée" if i in douteuses else ""]
              for i, x in enumerate(entrees) if du <= x.moment[:10] <= au]
    lignes = _cherche(list(reversed(lignes)), v)
    return [Section(f"Actions du {du} au {au}", ["Moment", "Utilisateur", "Poste", "Fenêtre", "Action", "Détail",
                                                 "Contrôle"], lignes,
                    f"⚠ {len(douteuses)} ligne(s) modifiée(s) depuis leur écriture." if douteuses
                    else "Chaîne d'empreintes intacte : aucune ligne modifiée.")]


def _journal(ctx, v):
    from .. import journal_operations as jo

    ops = jo.filtrer(jo.lire(ctx.racine), str(v["du"]), str(v["au"]), v.get("source", ""), v.get("texte", ""))
    return [Section("Journal des opérations", ["Moment", "Source", "Personne", "Détail"],
                    [[o.quand, o.source, o.personne, o.detail] for o in ops])]


def sections_html(sections) -> str:
    return "".join(tableau_section(s) for s in sections)


# --------------------------------------------------------------------------------------------- page générique
def _formulaire(ctx: Contexte, c: Consultation, v: dict) -> str:
    champs = []
    f = c.filtres
    if "periode" in f or "du" in f:
        champs.append(f"<div><label>Du</label><input type='date' name='du' value='{v['du']}'></div>")
    if "periode" in f or "au" in f:
        champs.append(f"<div><label>Au</label><input type='date' name='au' value='{v['au']}'></div>")
    if "mois" in f:
        champs.append(f"<div><label>Mois</label><input type='month' name='mois' value='{e(v.get('mois', ''))}'></div>")
    for genre, table in (("client", "tcustomr"), ("fournisseur", "tvendor"), ("article", "")):
        if genre in f:
            liste = ""
            try:
                noms = _noms(ctx, table) if table else []
                liste = "<datalist id='noms'>" + "".join(f"<option value='{e(n)}'>" for n in noms) + "</datalist>"
            except Exception:  # noqa: BLE001 — Sage absent : saisie libre
                pass
            etiquette = "N° de l'article" if genre == "article" else genre.capitalize()
            champs.append(f"<div><label>{etiquette}</label><input name='{genre}' list='noms' value='{e(v.get(genre, ''))}'"
                          f" size='28'>{liste}</div>")
    for nom, choix in (("cote", ("Clients", "Fournisseurs")), ("vue", ("Par tiers", "Par facture"))):
        if nom in f:
            options = "".join(f"<option{' selected' if v.get(nom) == x else ''}>{x}</option>" for x in choix)
            champs.append(f"<div><label>{'Côté' if nom == 'cote' else 'Vue'}</label><select name='{nom}'>{options}"
                          f"</select></div>")
    for nom, (libelle, valeurs) in c.choix.items():
        options = "".join(f"<option{' selected' if str(v.get(nom)) == str(x) else ''}>{e(x)}</option>" for x in valeurs)
        champs.append(f"<div><label>{e(libelle)}</label><select name='{nom}'>{options}</select></div>")
    if "categorie" in f:
        champs.append(f"<div><label>Catégorie</label><input name='categorie' value='{e(v.get('categorie', ''))}' "
                      "size='16'></div>")
    if "stock" in f:
        coche = " checked" if v.get("stock") else ""
        champs.append(f"<div><label><input type='checkbox' name='stock' value='1'{coche}> Seulement les articles en "
                      "stock</label></div>")
    if "source" in f:
        champs.append(f"<div><label>Source</label><input name='source' value='{e(v.get('source', ''))}' size='14'></div>")
    if "texte" in f:
        champs.append(f"<div><label>Rechercher</label><input name='texte' value='{e(v.get('texte', ''))}'></div>")
    return (f"<form class='ligne' method='get'>{''.join(champs)}<input type='hidden' name='voir' value='1'>"
            f"<button class='second' type='submit'>Afficher</button></form>")


def consulter(c: Consultation):
    def gestionnaire(ctx: Contexte) -> Reponse:
        q = ctx.req.query
        aujourdhui = date.today()
        v = dict(c.defauts) | {k: q[k] for k in q if q[k] != ""}
        v["du"] = _date(q.get("du"), c.defauts.get("du", aujourdhui.replace(day=1)))
        v["au"] = _date(q.get("au"), aujourdhui)
        v.setdefault("mois", f"{aujourdhui:%Y-%m}")
        from .pages_rapports_web import est_onglet, onglets

        corps = (onglets(c.titre, ctx) if est_onglet(c.titre) else "") + (
            f"<p class='note'>{e(c.explication)}</p>" if c.explication else "") + _formulaire(ctx, c, v)
        try:
            sections = c.calcul(ctx, v)
            corps += "".join(tableau_section(s) for s in sections)
        except (Exception, SystemExit) as erreur:  # noqa: BLE001 — Sage absent, jeton Clover absent (SystemExit)
            ctx.app.noter(f"{c.titre} : {erreur!r}")
            source = "Clover" if c.sans_sage else "Sage"
            corps += f"<p class='erreur'>Lecture impossible : {source} ne répond pas sur le serveur pour l'instant.</p>"
        return Reponse(corps=page(ctx, c.titre, corps))
    return gestionnaire


AN = date.today().replace(month=1, day=1)
CONSULTATIONS = [
    Consultation("/clients", "Liste des clients", "encaissements", ("texte",), _tiers("clients"),
                 "Clients de Sage : montant dû, factures ouvertes, dernière facture.", "👥", "Vente"),
    Consultation("/documents-vente", "Liste des documents de vente", "encaissements", ("periode", "texte"),
                 _documents("ventes"), "Factures, encaissements et autres documents de vente de Sage.", "🗂", "Vente"),
    Consultation("/interrogation-client", "Interrogation de compte client", "rapports", ("client", "periode"),
                 _interrogation("client"), "", "🔎", "Vente", defauts={"du": AN}),
    Consultation("/fournisseurs-liste", "Liste des fournisseurs", "fournisseurs", ("texte",), _tiers("fournisseurs"),
                 "Fournisseurs de Sage avec le montant dû.", "🏭", "Fournisseur"),
    Consultation("/documents-achat", "Liste des documents d'achat", "fournisseurs", ("periode", "texte"),
                 _documents("achats"), "Factures, paiements et notes de crédit des fournisseurs dans Sage.", "🗂",
                 "Fournisseur"),
    Consultation("/interrogation-fournisseur", "Interrogation de compte fournisseur", "rapports",
                 ("fournisseur", "periode"), _interrogation("fournisseur"), "", "🔎", "Fournisseur",
                 defauts={"du": AN}),
    Consultation("/articles", "Liste des articles", "correspondance", ("texte",), _articles,
                 "Articles de Sage : stock, CUMP, valeur, comptes et lien Clover.", "📚", "Articles"),
    Consultation("/interrogation-article", "Interrogation de compte article", "rapports", ("article", "periode"),
                 _interrogation("article"), "Ventes, achats et ajustements d'un article de Sage.", "🔎", "Articles",
                 defauts={"du": AN}),
    Consultation("/documents-stock", "Liste des documents de stock", "correspondance", ("periode", "texte"),
                 _documents("stock"), "Ajustements d'inventaire et transferts entre emplacements de Sage.", "🗂",
                 "Stock"),
    Consultation("/livre-inventaire", "Livre d'inventaire", "correspondance", ("au", "texte"), _livre, "", "📒",
                 "Stock"),
    Consultation("/age-comptes", "Âge des comptes", "rapprochement", ("cote", "vue"), _age, "", "⏳", "Comptabilité"),
    Consultation("/taxes", "Déclaration TPS/TVQ", "rapprochement", ("periode",), _taxes, "", "🧮", "Comptabilité"),
    Consultation("/tresorerie", "Prévision de trésorerie", "rapprochement", (), _tresorerie,
                 "Solde du compte de dépôt, ventes prévues, factures fournisseurs et paies sur 4 semaines.", "💧",
                 "Comptabilité"),
    Consultation("/cloture", "Clôture du mois", "rapprochement", ("mois",), _cloture, "", "📅", "Comptabilité"),
    Consultation("/plan-comptable", "Plan comptable", "rapprochement", ("texte",), _plan, "", "📒", "Comptabilité"),
    Consultation("/retenues", "Retenues à la source", "rapprochement", ("mois",), _retenues, "", "🏛", "Paie"),
    Consultation("/suivi-remises", "Suivi des remises", "rapprochement", (), _suivi_remises, "", "📬", "Paie"),
    Consultation("/audit", "Audit des actions", "utilisateurs", ("periode", "texte"), _audit,
                 "Chaque page, bouton et connexion, avec la personne et le poste.", "🛡", "Administration",
                 sans_sage=True, defauts={"du": date.today() - timedelta(days=7)}),
    Consultation("/journal-operations", "Journal des opérations", "utilisateurs", ("periode", "source", "texte"),
                 _journal, "Journaux et registres de l'application réunis.", "🧭", "Administration", sans_sage=True,
                 defauts={"du": date.today() - timedelta(days=30)}),
]

from .consultations_etat import CONSULTATIONS_ETAT  # noqa: E402 — 3e vague (État, paie, budget)

CONSULTATIONS += CONSULTATIONS_ETAT
FONCTIONS = [Fonction(c.chemin, c.titre, c.page, consulter(c), c.icone, c.rubrique, menu=False)
             for c in CONSULTATIONS]
WEB = {c.titre: c.chemin for c in CONSULTATIONS}


def lien(chemin: str, **valeurs) -> str:
    return chemin + ("?" + urlencode(valeurs) if valeurs else "")
