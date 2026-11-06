"""Consultations de l'application web (2e vague de « toutes les fonctionnalités dans l'application web, idem dans
l'application bureau », demande du propriétaire du 2026-11-03) : listes, interrogations de compte, rapports de
comptabilité et de paie, audit, journal des opérations.

Chaque consultation reprend la fonction de calcul de la fenêtre Windows du même nom (mêmes chiffres) ; la page web
générique (`consulter`) n'ajoute que les filtres et le tableau. Sage est lu par `lire_sage(..., ouvrir=False)` :
une page web n'ouvre jamais Sage elle-même ; lecture gardée 5 min.
"""

from __future__ import annotations

import re

from urllib.parse import quote

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
    bouton: str = "🔄 Actualiser"  # bouton de la barre, comme la fenêtre Windows (« 🔍 Calculer », « 🔍 Vérifier »)
    attente: str = ""  # calcul lancé seulement par le bouton (comme Windows) : texte de la ligne d'état avant


# --------------------------------------------------------------------------------------------- outils
class _Vide(list):
    """Résultat vide qui sert de liste comme de dictionnaire."""

    def get(self, _cle, defaut=None):
        return defaut

    def keys(self):
        return []

    def values(self):
        return []

    def items(self):
        return []


class BaseVide:
    """Base Sage sans aucune ligne : quand Sage ne répond pas, les fonctions de lecture tournent quand même sur elle et
    rendent leurs tableaux vides avec toutes leurs colonnes (demande du propriétaire du 2026-11-04 : jamais de page
    vide)."""

    def requete(self, sql: str = "", parametres: tuple = ()) -> list:
        return []

    def __getattr__(self, _nom):
        return lambda *a, **k: _Vide()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return None


def lire_ou_vide(ctx: Contexte, fonction, **options):
    """`lire_sage(…, ouvrir=False)` ; Sage injoignable : la même fonction sur `BaseVide` (tableaux vides), et la page
    signale « Sage ne répond pas »."""
    from ..__main__ import lire_sage

    try:
        return lire_sage(ctx.config, fonction, ouvrir=False, **options)
    except (Exception, SystemExit) as erreur:  # noqa: BLE001 — Sage absent du serveur, refus, base fermée
        ctx.app.noter(f"Sage injoignable : {erreur!r}")
        try:
            resultat = fonction(BaseVide())
        except Exception:  # noqa: BLE001 — fonction qui ne sait pas tourner à vide : erreur d'origine
            raise erreur from None
        ctx.absents.add("Sage")
        return resultat


def sage(ctx: Contexte, fonction, cle):
    cle = ("sage",) + tuple(cle)
    gardee = ctx.app.memoire.get(cle)
    if gardee and time.time() - gardee[0] < DUREE:
        return gardee[1]
    resultat = lire_ou_vide(ctx, fonction)
    if "Sage" not in ctx.absents:  # une lecture vide n'est jamais gardée
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


_RADIO = re.compile(r"^<input type='radio'([^>]*)>")
_RANG_RADIO = [0]


def ligne_cliquable(cellules: list[str]) -> list[str]:
    """Ligne dont la 1re cellule est un bouton radio : chaque autre cellule devient une étiquette de ce bouton (un
    clic n'importe où sur la ligne la choisit, comme dans un tableau de Windows ; le bouton lui-même est caché)."""
    m = _RADIO.match(cellules[0]) if cellules else None
    if not m or " id=" in m.group(1):
        return cellules
    _RANG_RADIO[0] += 1
    ident = f"l{_RANG_RADIO[0]}"
    premiere = f"<input type='radio' id='{ident}' class='choix-ligne'{m.group(1)}>" + cellules[0][m.end():]
    return [premiere] + [f"<label class='cellule' for='{ident}'>{c}</label>" if "<a " not in c and "<input" not in c
                         and "<select" not in c and "<button" not in c else c for c in cellules[1:]]


def tableau_section(s: Section, limite: int = 2000) -> str:
    if not s.lignes:  # tableau vide : ses colonnes restent affichées, comme dans Windows
        th = "".join(f"<th>{e(c)}</th>" for c in s.entetes)
        vide = (f"<tr><td class='vide' colspan='{max(len(s.entetes), 1)}'>Aucune ligne.</td></tr>")
        return (f"<h2>{e(s.titre)} <span class='etat'>0</span></h2><div class='defile'><table>"
                + (f"<tr>{th}</tr>" if th else "") + f"{vide}</table></div>"
                + (f"<p class='note'>{e(s.note)}</p>" if s.note else ""))
    nombres = {i for i in range(len(s.entetes)) if _numerique(s.lignes, i)}
    th = "".join(f"<th class='{'n' if i in nombres else ''}'>{e(c)}</th>" for i, c in enumerate(s.entetes))
    corps = []
    for rang, ligne in enumerate(s.lignes[:limite]):
        total = str(ligne[0]).startswith("Total")
        classe = s.classes[rang] if s.classes and rang < len(s.classes) else ""
        textes = [v if i in s.html else e(formater(s.entetes[i], v)) for i, v in enumerate(ligne[:len(s.entetes)])]
        corps.append(f"<tr class='{'total' if total else classe}'>"
                     + "".join(f"<td class='{'n' if i in nombres else ''}'>{t}</td>"
                               for i, t in enumerate(ligne_cliquable(textes))) + "</tr>")
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
            from .filtres import depots_choisis

            depots = depots_choisis(ctx)
            entetes, lignes = sage(ctx, lambda b: ls.documents_stock(b, du, au, depots),
                                   ("docstock", du, au, tuple(depots or ())))
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
    from .filtres import depots_choisis

    depots = depots_choisis(ctx)
    entetes, lignes = sage(ctx, lambda b: ls.articles(b, cats, {n: [f"{k} relié(s)"] for n, k in liens.items()},
                                                      depots), ("articles", tuple(depots or ())))
    return [Section("Articles de Sage", entetes, _cherche(lignes, v))]


def _livre(ctx, v):
    from .. import listes_sage as ls
    from ..analyse_articles import categories

    from .filtres import depots_choisis

    au, depots = v["au"], depots_choisis(ctx)
    entetes, lignes = sage(ctx, lambda b: ls.livre_inventaire(b, au, categories(ctx.racine), depots)[:2],
                           ("livre", au, tuple(depots or ())))
    titre = f"Stock et valeur au {au}" + (f" — {', '.join(depots)}" if depots else "")
    return [Section(titre, entetes, _cherche(lignes, v),
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

    cote = "clients" if v.get("cote") == "Clients" else "fournisseurs"
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
        champs.append(f"<div><label>Période du</label><input type='date' name='du' value='{v['du']}'></div>")
    if "periode" in f or "au" in f:
        champs.append(f"<div><label>au</label><input type='date' name='au' value='{v['au']}'></div>")
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
    # fenetre_comptabilite : « Comptes » Fournisseurs (par défaut) / Clients, « Afficher » Par tiers / Par facture
    for nom, choix in (("cote", ("Fournisseurs", "Clients")), ("vue", ("Par tiers", "Par facture"))):
        if nom in f:
            options = "".join(f"<option{' selected' if v.get(nom, choix[0]) == x else ''}>{x}</option>" for x in choix)
            champs.append(f"<div><label>{'Comptes' if nom == 'cote' else 'Afficher'}</label><select name='{nom}'>"
                          f"{options}</select></div>")
    for nom, (libelle, valeurs) in c.choix.items():
        options = "".join(f"<option{' selected' if str(v.get(nom)) == str(x) else ''}>{e(x)}</option>" for x in valeurs)
        champs.append(f"<div><label>{e(libelle)}</label><select name='{nom}'>{options}</select></div>")
    if "depot" in f:  # filtre « Dépôt » (tous ou certains), comme design.filtre_depots
        from .filtres import filtre_depots

        champs.append(filtre_depots(ctx))
    if "categorie" in f:
        champs.append(f"<div><label>Catégorie</label><input name='categorie' value='{e(v.get('categorie', ''))}' "
                      "size='16'></div>")
    if "stock" in f:
        coche = " checked" if v.get("stock") else ""
        champs.append(f"<div><label><input type='checkbox' name='stock' value='1'{coche}> Seulement les articles en "
                      "stock</label></div>")
    if "source" in f:  # FenetreJournalOperations : liste des sources (Toutes + celles du journal)
        try:
            from .. import journal_operations as jo

            sources = sorted({o.source for o in jo.lire(ctx.racine)})
        except Exception:  # noqa: BLE001
            sources = []
        options = "<option value=''>Toutes</option>" + "".join(
            f"<option{' selected' if x == v.get('source') else ''}>{e(x)}</option>" for x in sources)
        champs.append(f"<div><label>Source</label><select name='source'>{options}</select></div>")
    if "texte" in f:
        champs.append(f"<div><label>Rechercher :</label><input name='texte' value='{e(v.get('texte', ''))}' "
                      "size='24'></div>")
    return (f"<form class='barre-onglet' method='get'>{''.join(champs)}<input type='hidden' name='voir' value='1'>"
            f"<button type='submit' name='actualiser' value='1'>{e(c.bouton)}</button></form>")


# listes de fenetre_gestion.ouvrir_liste : genre (fiches.ouvrir_fiche) et page web de « ➕ Ajouter »
LISTES = {"/clients": ("clients", "/client-nouveau"), "/fournisseurs-liste": ("fournisseurs", "/fournisseur-nouveau"),
          "/articles": ("articles", "/creer-article"), "/livre-inventaire": ("livre", "/creer-article"),
          "/documents-vente": ("documents_vente", "/document/choisir?cote=vente"),
          "/documents-achat": ("documents_achat", "/document/choisir?cote=achat"),
          "/documents-stock": ("documents_stock", "/document/choisir?cote=stock")}
# tableaux vides de la fenêtre Windows avant « Calculer » / « Vérifier » (fenetre_comptabilite)
ZONES_ATTENTE = {"/retenues": ["Retenues à la source", "Salaires et cotisations de l'employeur du mois"],
                 "/tresorerie": ["Prévision de trésorerie"], "/taxes": ["Déclaration TPS/TVQ"],
                 "/suivi-remises": ["Suivi des remises de retenues"], "/cloture": ["Clôture du mois"]}
MESSAGE_MODIFIER = ("Les fiches et les documents enregistrés dans Sage se modifient dans Sage. La fiche s'ouvre pour "
                    "consultation ; les documents saisis dans l'application se modifient dans leur liste (Vente, "
                    "Articles).")
MESSAGE_SUPPRIMER = ("Une fiche ou un document de Sage ne se supprime pas d'ici : dans Sage, rendez la fiche inactive, "
                     "ou corrigez / annulez le document. Les documents saisis dans l'application se suppriment dans "
                     "leur liste.")


def consulter(c: Consultation):
    def gestionnaire(ctx: Contexte) -> Reponse:
        q = ctx.req.query
        aujourdhui = date.today()
        v = dict(c.defauts) | {k: q[k] for k in q if q[k] != ""}
        v["du"] = _date(q.get("du"), c.defauts.get("du", aujourdhui - timedelta(days=30)))  # comme Windows
        v["au"] = _date(q.get("au"), c.defauts.get("au", aujourdhui))
        precedent = aujourdhui.replace(day=1) - timedelta(days=1)  # fenetre_comptabilite : mois terminé
        v.setdefault("mois", f"{precedent:%Y-%m}" if c.chemin in ("/retenues", "/cloture") else f"{aujourdhui:%Y-%m}")
        from .pages_rapports_web import est_onglet, onglets

        if q.get("actualiser"):  # « 🔄 Actualiser » : relu dans Sage
            for cle in [k for k in list(ctx.app.memoire) if isinstance(k, tuple) and k and k[0] == "sage"]:
                ctx.app.memoire.pop(cle, None)
        liste = LISTES.get(c.chemin)
        corps = (onglets(c.titre, ctx) if est_onglet(c.titre) else "") + _formulaire(ctx, c, v)
        if liste:  # barre de FenetreListe : Actualiser, Ouvrir, Ajouter, Modifier, Supprimer (+ chaîne des documents)
            cote = {"documents_vente": "vente", "documents_achat": "achat", "documents_stock": "stock"}.get(liste[0])
            ajouter = (f"<a class='ouvrir' href='{liste[1]}'>➕ Ajouter</a>" if liste[1] else
                       f"<a class='ouvrir' href='{c.chemin}?ajouter=1'>➕ Ajouter</a>")
            boutons = ("<button class='second' form='liste' name='op' value='ouvrir'>📂 Ouvrir</button>" + ajouter
                       + "<button class='second' form='liste' name='op' value='modifier'>✎ Modifier</button>"
                       "<button class='danger' form='liste' name='op' value='supprimer'>🗑 Supprimer</button>"
                       + ("<button class='accent' form='liste' name='op' value='piece'>⬆ Passer dans Sage et Clover"
                          "</button>" if cote == "stock" else
                          "<button class='accent' form='liste' name='op' value='piece'>🔀 Transformer</button>"
                          "<button class='second' form='liste' name='op' value='piece'>⬆ Importer dans Sage</button>"
                          if cote else ""))
            corps = corps.replace("</form>", boutons + "</form>", 1)
        if c.attente and not q.get("actualiser"):  # fenêtre Windows : rien n'est lu avant « Calculer »
            corps += f"<div class='ligne-etat-haut'>{e(c.attente)}</div>" + "".join(
                (f"<h2 class='titre-zone'>{e(t_)}</h2>" if t_ else "")
                + "<div class='defile'><table><tr><td class='vide'></td></tr></table></div>"
                for t_ in ZONES_ATTENTE.get(c.chemin, [c.titre]))
            return Reponse(corps=page(ctx, c.titre, corps))
        try:
            sections = c.calcul(ctx, v)
        except (Exception, SystemExit) as erreur:  # noqa: BLE001 — jeton Clover absent (SystemExit), autre panne
            ctx.app.noter(f"{c.titre} : {erreur!r}")
            ctx.absents.add("Clover" if c.sans_sage else "Sage")
            sections = []
        if liste and sections:
            corps += _liste_comme_windows(ctx, c, sections, v, liste[0])
        else:
            corps += "".join(tableau_section(x) for x in sections)
            if not sections:
                corps += tableau_section(Section(c.titre, [], []))
        n = sum(len(x.lignes) for x in sections[:1])
        etat = c.explication or ""
        if q.get("ajouter") and liste and liste[0] in ("clients", "fournisseurs"):
            etat = ("Les fiches de clients et de fournisseurs se créent dans Sage (Sage n'accepte pas leur import) : "
                    "« Ajouter » de la liste de l'application Windows les crée en ouvrant Sage.")
        corps += f"<div class='ligne-etat'>{e(etat + (' — ' if etat else '') + f'{n} ligne(s) affichée(s).')}</div>"
        return Reponse(corps=page(ctx, c.titre, corps))
    return gestionnaire


def _rangees_application(ctx: Contexte, cote: str, v: dict) -> list:
    """Lignes des documents de l'application, calculées par FenetreDocumentsChaine._rangees_application."""
    from types import SimpleNamespace

    from ..fenetre_chaine import FenetreDocumentsChaine

    class _Date:
        def __init__(self, valeur):
            self.valeur = str(valeur or "")

        def get(self):
            return self.valeur

    faux = SimpleNamespace(racine=ctx.racine, cote=cote, du=_Date(v.get("du")), au=_Date(v.get("au")))
    try:
        return FenetreDocumentsChaine._rangees_application(faux)
    except Exception as erreur:  # noqa: BLE001
        ctx.app.noter(f"Documents de l'application : {erreur!r}")
        return []


def _liste_comme_windows(ctx: Contexte, c: Consultation, sections: list, v: dict, genre: str) -> str:
    """Tableau à choisir (une ligne) + « 📂 Ouvrir », « ✎ Modifier », « 🗑 Supprimer » ; fiche sous la liste."""
    from .. import fiches

    s0 = sections[0]
    choisi = v.get("ligne", "")
    cote = {"documents_vente": "vente", "documents_achat": "achat", "documents_stock": "stock"}.get(genre)
    rangees = [(list(l), ("sage", str(n))) for n, l in enumerate(s0.lignes)]
    entetes = list(s0.entetes)
    if cote:  # FenetreDocumentsChaine : documents de Sage + documents de l'application (en bleu)
        from ..fenetre_chaine import ENTETES_ACHAT, ENTETES_STOCK, ENTETES_VENTE

        entetes = ENTETES_STOCK if cote == "stock" else ENTETES_ACHAT if cote == "achat" else ENTETES_VENTE
        application = _rangees_application(ctx, cote, v)
        if cote == "stock":
            from .filtres import depots_choisis

            rangees = [(l + ["Dans Sage"], r) for l, r in rangees]  # dépôt lu dans Sage (titrline.lInvLocId)
            choisis = {d.casefold() for d in depots_choisis(ctx) or []}
            if choisis:
                application = [x for x in application if str(x[0][3]).casefold() in choisis]
        rangees += [(l, ("app",) + ref) for l, ref in application]
        texte = str(v.get("texte", "")).strip().casefold()
        rangees = [x for x in rangees if not texte or x[1][0] == "sage" or any(texte in str(c).casefold() for c in x[0])]
        rangees.sort(key=lambda x: str(x[0][0]), reverse=True)
    valeur = (lambda ref: ref[1] if ref[0] == "sage" else ":".join(ref))
    lignes = [[f"<input type='radio' name='ligne' value='{e(valeur(ref))}'{' checked' if valeur(ref) == choisi else ''}>"]
              + [e(formater(entetes[k], x)) for k, x in enumerate(l[:len(entetes)])]
              for l, ref in rangees[:2000]]
    classes_app = ["application" if ref[0] == "app" else ("total" if str(l[0]).startswith("Total") else "")
                   for l, ref in rangees[:2000]]
    caches = "".join(f"<input type='hidden' name='{k}' value='{e(v[k])}'>" for k in ("du", "au", "texte", "mois")
                     if k in v and str(v[k]))
    # boutons de la liste : placés dans la barre du haut par `consulter` (attribut form=), comme FenetreListe
    html = (f"<form method='get' id='liste'>{caches}<input type='hidden' name='voir' value='1'>"
            + (f"<div class='ligne-etat-haut'>{len(rangees)} document(s) ; en bleu : documents de l'application.</div>"
               if cote else f"<div class='ligne-etat-haut'>{len(rangees)} ligne(s) affichée(s) sur {len(rangees)}.</div>")
            + "<div class='liste-windows'>"
            + tableau_section(Section(s0.titre, [""] + list(entetes), lignes, s0.note, classes_app,
                                      html=set(range(len(entetes) + 1))), limite=10000)
            + "</div></form>" + "".join(tableau_section(x) for x in sections[1:]))
    op = v.get("op")
    if not op:
        return html
    if choisi.startswith("app:"):  # document de l'application : sa propre page (transformer, importer, passer)
        _a, sorte, ident = (choisi.split(":", 2) + ["", ""])[:3]
        adresse = {"doc": f"/document?n={quote(ident)}", "bc": "/bons-commande", "fa": "/factures-fournisseurs",
                   "rt": "/retours"}.get(sorte, "/documents")
        return html + (f"<div class='carte'><p>Document de l'application : <a class='ouvrir' href='{adresse}'>📂 Ouvrir "
                       f"{e(ident)}</a> (modifier, transformer, importer ou passer dans Sage depuis sa page).</p></div>")
    if op == "piece":
        return html + ("<p class='note'>Ce document est déjà dans Sage : transformer, importer et passer dans Sage "
                       "concernent les documents de l'application (en bleu).</p>")
    if not choisi.isdigit() or int(choisi) >= len(s0.lignes):
        return html + "<p class='erreur-texte'>Choisissez une ligne dans la liste.</p>"
    ligne = list(s0.lignes[int(choisi)])
    if genre == "articles" and op in ("modifier", "supprimer"):  # Sage puis Clover, comme fenetre_fiches_articles
        from .pages_fiches import formulaire_article

        valeur = dict(zip(s0.entetes, ligne))
        numero = str(valeur.get("N° Sage") or ligne[0])
        return html + formulaire_article(ctx, op, numero, str(valeur.get("Description") or ""))
    message = {"modifier": MESSAGE_MODIFIER, "supprimer": MESSAGE_SUPPRIMER}.get(op, "")
    if op == "supprimer":
        return html + f"<p class='note'>{e(message)}</p>"
    valeur = dict(zip(s0.entetes, ligne))
    if genre in ("clients", "fournisseurs"):
        titre, lecture = f"Fiche : {ligne[0]}", (lambda b: fiches.lire_tiers(b, genre, str(ligne[0])))
    elif genre in ("articles", "livre"):
        numero = str(valeur.get("N° Sage") or "")
        titre, lecture = f"Fiche article : {numero}", (lambda b: fiches.lire_article(b, numero))
    elif genre in ("documents_vente", "documents_achat"):
        cote = "ventes" if genre == "documents_vente" else "achats"
        numero, tiers = str(valeur.get("Facture") or ""), str(valeur.get("Client") or valeur.get("Fournisseur") or "")
        titre, lecture = f"Document : {numero}", (lambda b: fiches.lire_document(b, cote, numero, tiers))
    else:
        source, jour = str(valeur.get("Source") or ""), str(valeur.get("Date") or "")
        titre, lecture = f"Document de stock : {source}", (lambda b: fiches.lire_document_stock(b, source, jour))
    try:
        infos, sections_fiche = sage(ctx, lecture, ("fiche", titre))
    except (Exception, SystemExit) as erreur:  # noqa: BLE001
        ctx.app.noter(f"Fiche : {erreur!r}")
        infos, sections_fiche = [], []
    moitie = (len(infos) + 1) // 2
    grille = "".join(f"<div class='colonne-fiche'>" + "".join(
        f"<div class='t'>{e(k)}</div><div class='v'>{e(x)}</div>" for k, x in partie) + "</div>"
        for partie in (infos[:moitie], infos[moitie:]))
    return (html + f"<div class='carte'><h2>{e(titre)}</h2>" + (f"<p class='note'>{e(message)}</p>" if message else "")
            + f"<div class='fiche-infos'>{grille}</div>"
            + "".join(tableau_section(Section(t_, ent, lig)) for t_, ent, lig in sections_fiche) + "</div>")


AN = date.today().replace(month=1, day=1)
CONSULTATIONS = [
    Consultation("/clients", "Liste des clients", "encaissements", ("texte",), _tiers("clients"),
                 "Clients de Sage : montant dû, factures ouvertes, dernière facture.", "👥", "Vente"),
    Consultation("/documents-vente", "Liste des documents de vente", "encaissements", ("periode", "texte"),
                 _documents("ventes"), "Factures, encaissements et autres documents de vente de Sage.", "🗂", "Vente"),
    Consultation("/fournisseurs-liste", "Liste des fournisseurs", "fournisseurs", ("texte",), _tiers("fournisseurs"),
                 "Fournisseurs de Sage avec le montant dû.", "🏭", "Fournisseur"),
    Consultation("/documents-achat", "Liste des documents d'achat", "fournisseurs", ("periode", "texte"),
                 _documents("achats"), "Factures, paiements et notes de crédit des fournisseurs dans Sage.", "🗂",
                 "Fournisseur"),
    Consultation("/articles", "Liste des articles", "correspondance", ("depot", "texte"), _articles,
                 "Articles de Sage : stock, CUMP, valeur, comptes et lien Clover.", "📚", "Articles"),
    Consultation("/documents-stock", "Liste des documents de stock", "correspondance", ("periode", "depot", "texte"),
                 _documents("stock"), "Ajustements d'inventaire et transferts entre emplacements de Sage.", "🗂",
                 "Stock"),
    Consultation("/livre-inventaire", "Livre d'inventaire", "correspondance", ("au", "depot", "texte"), _livre, "", "📒",
                 "Stock"),
    Consultation("/age-comptes", "Âge des comptes", "rapprochement", ("cote", "vue"), _age, "", "⏳", "Comptabilité"),
    Consultation("/taxes", "Déclaration TPS/TVQ", "rapprochement", ("periode",), _taxes, "", "🧮", "Comptabilité", bouton="🔍 Calculer",
                 attente="Choisissez la période de déclaration puis « Calculer »."),
    Consultation("/tresorerie", "Prévision de trésorerie", "rapprochement", (), _tresorerie,
                 "Solde du compte de dépôt, ventes prévues, factures fournisseurs et paies sur 4 semaines.", "💧",
                 "Comptabilité", bouton="🔍 Calculer",
                 attente="« Calculer » : 4 semaines à partir d'aujourd'hui."),
    Consultation("/cloture", "Clôture du mois", "rapprochement", ("mois",), _cloture, "", "📅", "Comptabilité", bouton="🔍 Vérifier",
                 attente="Choisissez le mois puis « Vérifier »."),
    Consultation("/retenues", "Retenues à la source", "rapprochement", ("mois",), _retenues, "", "🏛", "Paie", bouton="🔍 Calculer",
                 attente="Choisissez le mois puis « Calculer »."),
    Consultation("/suivi-remises", "Suivi des remises", "rapprochement", (), _suivi_remises, "", "📬", "Paie", bouton="🔍 Calculer",
                 attente="12 derniers mois : à remettre par organisme, versements jusqu'à 60 jours après l'échéance du 15. « Calculer » lit Sage."),
    Consultation("/audit", "Audit des actions", "utilisateurs", ("periode", "texte"), _audit,
                 "Chaque page, bouton et connexion, avec la personne et le poste.", "🛡", "Administration",
                 sans_sage=True, defauts={"du": date.today() - timedelta(days=7)}),
    Consultation("/journal-operations", "Journal des opérations", "utilisateurs", ("periode", "source", "texte"),
                 _journal, "Journaux et registres de l'application réunis.", "🧭", "Administration", sans_sage=True,
                 defauts={"du": date.today() - timedelta(days=30)}, bouton="🔍 Afficher"),
]

from .consultations_etat import CONSULTATIONS_ETAT  # noqa: E402 — 3e vague (État, paie, budget)

CONSULTATIONS += CONSULTATIONS_ETAT
FONCTIONS = [Fonction(c.chemin, c.titre, c.page, consulter(c), c.icone, c.rubrique, menu=False)
             for c in CONSULTATIONS]
WEB = {c.titre: c.chemin for c in CONSULTATIONS}


def lien(chemin: str, **valeurs) -> str:
    return chemin + ("?" + urlencode(valeurs) if valeurs else "")
