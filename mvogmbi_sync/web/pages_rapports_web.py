"""Onglets de la page Rapports dans l'application web, disposés comme dans l'application Windows (page_rapports et
onglets_articles) : barre des onglets en haut (Suivi des ventes, Recherche dans l'historique, Statistiques Clover,
Produits inactifs, Articles 20/80, Factures fournisseurs archivées), filtres à gauche puis « Rechercher » à droite,
texte d'état, cartes des totaux (la première en grand), tableau aux lignes colorées (mêmes couleurs).
"""

from __future__ import annotations

import time
from datetime import date, timedelta

from .consultations import Section, sage, tableau_section
from .pages import Contexte, Fonction, argent, page
from .serveur import Reponse, echapper as e

ONGLETS = [("Suivi des ventes", "/suivi-ventes"), ("Recherche dans l'historique", "/historique"),
           ("Factures fournisseurs archivées", "/archives-fournisseurs"), ("Statistiques Clover", "/statistiques"),
           ("Produits inactifs", "/inactifs"), ("Articles 20/80", "/pareto")]  # ordre des onglets de PageRapports
# fenêtres Windows à onglets : (libellé de l'onglet, adresse web, entrée du menu qui donne le droit, page)
GROUPES = [
    [(t, a, t, "rapports") for t, a in ONGLETS],
    [("Âge des comptes", "/age-comptes", "Âge des comptes", "rapprochement"),
     ("Déclaration TPS/TVQ", "/taxes", "Déclaration TPS/TVQ", "rapprochement"),
     ("Prévision de trésorerie", "/tresorerie", "Prévision de trésorerie", "rapprochement"),
     ("Retenues à la source", "/retenues", "Retenues à la source", "rapprochement"),
     ("Suivi des remises", "/suivi-remises", "Suivi des remises", "rapprochement"),
     ("Budget et écarts", "/budget", "Budget et écarts", "rapprochement"),
     ("Clôture du mois", "/cloture", "Clôture du mois", "rapprochement")],
    [("Comptage du soir", "/caisse", "Contrôle de la caisse", "paiements"),
     ("Écarts par jour", "/caisse-ecarts?vue=ecarts", "Contrôle de la caisse", "paiements"),
     ("Dépôts d'espèces", "/caisse-ecarts?vue=depots", "Contrôle de la caisse", "paiements")],
    [("Heures planifiées et réalisées", "/traitement-paie", "Traitement de la paie", "rapprochement"),
     ("Heures validées", "/traitement-paie?onglet=validees", "Traitement de la paie", "rapprochement"),
     ("Paies dans Sage", "/paies-sage", "Traitement de la paie", "rapprochement"),
     ("Fin d'année (T4 / RL-1)", "/fin-annee", "Traitement de la paie", "rapprochement")],
    [("Déclarer une perte", "/pertes", "Pertes et démarque", "correspondance"),
     ("Pertes déclarées", "/pertes?onglet=liste", "Pertes et démarque", "correspondance"),
     ("Rapport des pertes", "/pertes?onglet=rapport", "Pertes et démarque", "correspondance")],
    [("Jours fériés", "/conges", "Jours fériés et congés", "paiements"),
     ("Congés", "/conges?onglet=conges", "Jours fériés et congés", "paiements"),
     ("Soldes par employé", "/conges?onglet=soldes", "Jours fériés et congés", "paiements")],
]


def est_onglet(libelle: str) -> bool:
    return any(libelle == o[0] for groupe in GROUPES for o in groupe)
DUREE = 600


def onglets(actif: str, ctx: Contexte | None = None) -> str:
    """Barre des onglets de la fenêtre Windows qui contient l'onglet `actif` (onglets non permis au profil masqués,
    comme dans Windows)."""
    from .pages import permis

    groupe = next((g for g in GROUPES if any(o[0] == actif for o in g)), [])
    liens = ""
    for libelle, adresse, titre, page_cle in groupe:
        if ctx is not None and not permis(ctx.reg, ctx.u, Fonction("", titre, page_cle, None, "", "")):
            continue
        liens += f"<a class='onglet{' actif' if libelle == actif else ''}' href='{adresse}'>{e(libelle)}</a>"
    entete = ""
    if groupe is GROUPES[0]:  # page « Rapports » de Windows : son titre au-dessus des onglets
        from .pages_admin import entete_page

        entete = entete_page("📊", "Rapports", "suivi complet des ventes, historique de Sage et factures fournisseurs "
                                               "archivées")
    return f"{entete}<nav class='onglets'>{liens}</nav>"


def cartes(valeurs: list[tuple[str, str]]) -> str:
    """Cartes d'indicateurs au-dessus du tableau, la première en grand (onglets_articles._cartes)."""
    html = "".join(f"<div class='carte-total{' premiere' if rang == 0 else ''}'><div class='t'>{e(t)}</div>"
                   f"<div class='v'>{e(v)}</div></div>" for rang, (t, v) in enumerate(valeurs))
    return f"<div class='cartes-totaux'>{html}</div>"


def _formulaire(contenu: str, bouton: bool = True) -> str:
    fin = "<button class='second'>Afficher</button>" if bouton else ""
    return f"<form class='barre-onglet' method='get'>{contenu}{fin}</form>"


def _choix(nom: str, libelle: str, valeurs, actuelle: str) -> str:
    options = "".join(f"<option{' selected' if v == actuelle else ''}>{e(v)}</option>" for v in valeurs)
    return f"<div><label>{e(libelle)}</label><select name='{nom}'>{options}</select></div>"


def _recherche(valeur: str) -> str:
    return (f"<div class='a-droite'><label>Rechercher</label><input name='recherche' value='{e(valeur)}' size='22'>"
            "</div>")


# --------------------------------------------------------------------------------------------- suivi des ventes
def suivi_ventes(ctx: Contexte) -> Reponse:
    from ..encaissements import numero_compte_sage
    from ..facture import CLIENT
    from ..page_rapports import FILTRES_SUIVI, traduire
    from ..rapports import ENTETES_SUIVI, suivi_ventes as calculer

    q = ctx.req.query
    filtre = q.get("filtre", FILTRES_SUIVI[0])
    texte = (q.get("recherche") or "").strip().casefold()
    entete = onglets("Suivi des ventes", ctx) + _formulaire(
        "<button name='actualiser' value='1'>🔄 Actualiser</button>"
        + _choix("filtre", "Afficher :", FILTRES_SUIVI, filtre) + _recherche(q.get("recherche", "")))
    try:
        compte = numero_compte_sage(str(ctx.config.get("encaissements", {}).get("compte_depot", "1055")))
        suivi = sage(ctx, lambda b: calculer(ctx.racine, b, CLIENT, compte), ("suivi_ventes",))
    except (Exception, SystemExit) as erreur:  # noqa: BLE001
        ctx.app.noter(f"Suivi des ventes : {erreur!r}")
        return Reponse(corps=page(ctx, "Rapports", entete + "<p class='erreur'>Lecture impossible : Sage ne répond pas "
                                                            "sur le serveur pour l'instant.</p>"))

    def bloquee(l) -> bool:
        return any(m in l.statut for m in ("Bloquée", "Échec", "ÉCHEC", "Import :"))

    lignes = []
    for l in suivi:
        if filtre == "Bloquées ou en échec" and not bloquee(l):
            continue
        if filtre == "Non encaissées" and (bloquee(l) or l.encaissement.startswith("Encaissée")):
            continue
        if filtre == "Non rapprochées" and l.rapprochement in ("Rapproché", "—"):
            continue
        if texte and not any(texte in str(v).casefold() for v in l.valeurs() + [l.facture]):
            continue
        lignes.append(l)

    def couleur(l) -> str:
        if bloquee(l):
            return "ligne-bloquee"
        if l.encaissement not in ("—",) and not l.encaissement.startswith("Encaissée"):
            return "ligne-a-encaisser"
        if l.rapprochement in ("Non rapproché",) or l.rapprochement.startswith("En partie"):
            return "ligne-a-rapprocher"
        return ""

    importees = sum(1 for l in suivi if l.statut in ("Facture importée", "Dans Sage"))
    etat = (f"{len(lignes)} vente(s) affichée(s) sur {len(suivi)} — dans Sage : {importees}, bloquées ou en échec : "
            f"{sum(1 for l in suivi if bloquee(l))}, non encaissées : "
            f"{sum(1 for l in suivi if l.encaissement not in ('—',) and not l.encaissement.startswith('Encaissée'))}, "
            f"non rapprochées : {sum(1 for l in suivi if l.rapprochement == 'Non rapproché')}")
    section = Section("Suivi complet des ventes : traitement, encaissement et rapprochement", ENTETES_SUIVI,
                      [[l.traitement, l.journee, traduire(l.statut), l.ht, l.taxes, l.ttc, traduire(l.commentaire),
                        traduire(l.encaissement), traduire(l.rapprochement)] for l in lignes],
                      classes=[couleur(l) for l in lignes])
    corps = entete + f"<p class='note'>{e(etat)}</p>" + tableau_section(section, limite=5000)
    return Reponse(corps=page(ctx, "Rapports", corps))


# --------------------------------------------------------------------------------------------- articles (Clover / Sage)
def _articles_clover(ctx: Contexte, du: date, au: date):
    from .. import analyse_articles as aa
    from ..cache_lectures import inventaire_clover
    from ..points_vente import client
    from ..previsions import ventes_par_article_rapide

    def lire():
        items = inventaire_clover(ctx.racine)
        ventes = ventes_par_article_rapide(client(ctx.racine), du, au, ctx.racine / "donnees" / "cache_clover")
        return aa.articles_clover(items, ventes), aa.ventes_clover(ventes)

    gardee = ctx.app.memoire.get(("art_clover", du, au))
    if gardee and time.time() - gardee[0] < DUREE:
        return gardee[1]
    valeur = lire()
    ctx.app.memoire[("art_clover", du, au)] = (time.time(), valeur)
    return valeur


def _articles_sage(ctx: Contexte, du: date | None = None, au: date | None = None):
    from .. import analyse_articles as aa

    categories = aa.categories(ctx.racine)
    if du is None:
        return sage(ctx, lambda b: aa.lire_articles(b, categories), ("art_sage",))
    return sage(ctx, lambda b: (aa.lire_articles(b, categories), aa.lire_ventes(b, du, au)), ("art_sage", du, au))


def _premiere(entetes: list[str], clover: bool) -> list[str]:
    return [{"N° Sage": "ID Clover", "CUMP": "Coût Clover"}.get(x, x) for x in entetes] if clover else entetes


def inactifs(ctx: Contexte) -> Reponse:
    from .. import analyse_articles as aa
    from ..onglets_articles import SOURCES, TOUTES

    q = ctx.req.query
    source = q.get("source", SOURCES[0])
    clover = source != "Sage"
    try:
        jours = max(1, int(q.get("jours") or 30))
    except ValueError:
        jours = 30
    categorie = q.get("categorie", TOUTES)
    avec_stock = bool(q.get("stock"))
    jamais = aa.JAMAIS_CLOVER if clover else aa.JAMAIS_SAGE
    try:
        if clover:
            articles, _ventes = _articles_clover(ctx, date.today() - timedelta(days=aa.JOURS_CLOVER), date.today())
        else:
            articles = _articles_sage(ctx)
    except (Exception, SystemExit) as erreur:  # noqa: BLE001
        ctx.app.noter(f"Produits inactifs : {erreur!r}")
        articles = {}  # tableau vide avec ses colonnes
        ctx.absents.add("Clover" if clover else "Sage")
    noms = [TOUTES] + sorted({a.categorie for a in (articles or {}).values()}, key=str.casefold)
    entete = onglets("Produits inactifs", ctx) + _formulaire(
        _choix("source", "Source", SOURCES, source)
        + f"<div><label>Sans vente depuis au moins</label><input name='jours' value='{jours}' list='seuils' "
          "size='5'><datalist id='seuils'>" + "".join(f"<option value='{j}'>" for j in aa.SEUILS_INACTIVITE)
        + "</datalist> jours</div>"
        + f"<div><label><input type='checkbox' name='stock' value='1'{' checked' if avec_stock else ''}> Seulement les "
          "articles en stock</label></div><button name='actualiser' value='1'>🔄 Actualiser</button>"
        + _choix("categorie", "Catégorie", noms, categorie), bouton=False)  # même ordre que onglets_articles
    explication = ("Articles (Clover, ou articles de stock actifs de Sage) qui n'ont pas été vendus depuis le nombre de "
                   "jours choisi (30, 60, 90… ou un autre nombre), ou jamais vendus ; la plus grande valeur de stock "
                   "en haut.")
    if articles is None:
        return Reponse(corps=page(ctx, "Rapports", entete + f"<p class='note'>{e(explication)}</p><p class='erreur'>"
                                  f"{'Clover' if clover else 'Sage'} ne répond pas pour l'instant.</p>"))
    lignes, resume = aa.produits_inactifs(articles, jours, date.today(), avec_stock,
                                          "" if categorie == TOUTES else categorie, jamais)
    entetes = _premiere(aa.ENTETES_INACTIFS, clover)
    classes = ["ligne-jamais" if l[4] == "" else ("ligne-stock" if l[7] > 0 else "") for l in lignes]
    if clover:  # aucun achat dans Clover
        lignes, entetes = [l[:6] + l[7:] for l in lignes], entetes[:6] + entetes[7:]
    texte = (q.get("recherche") or "").strip().casefold()
    if texte:
        garde = [i for i, l in enumerate(lignes) if any(texte in str(v).casefold() for v in l)]
        lignes, classes = [lignes[i] for i in garde], [classes[i] for i in garde]
    ordre = [aa.tranche(j, jamais) for j in aa.SEUILS_INACTIVITE] + [jamais]
    tranches = "  •  ".join(f"{k} : {resume['tranches'][k]}" for k in ordre if k in resume["tranches"])
    etat = (f"{resume['articles']} article(s) inactif(s) sur {sum(1 for a in articles.values() if a.catalogue)} — "
            f"jamais vendus : {resume['jamais']}, encore en stock : {resume['en_stock']}, valeur du stock immobilisé : "
            f"{argent(resume['valeur'])}")
    corps = (entete + f"<p class='note'>{e(etat)}" + (f"<br>{e(tranches)}" if tranches else "") + "</p>"
             + cartes([("Valeur du stock immobilisé", argent(resume["valeur"])),
                       ("Articles inactifs", str(resume["articles"])), ("Encore en stock", str(resume["en_stock"])),
                       ("Jamais vendus", str(resume["jamais"]))])
             + tableau_section(Section(f"Produits sans vente depuis {jours} jours ou plus ({source})", entetes, lignes,
                                       classes=classes), limite=5000))
    return Reponse(corps=page(ctx, "Rapports", corps))


def pareto(ctx: Contexte) -> Reponse:
    from .. import analyse_articles as aa
    from ..onglets_articles import AFFICHAGES_PARETO, PERIODES, SOURCES, TOUTES, bornes

    q = ctx.req.query
    source = q.get("source", SOURCES[0])
    clover = source != "Sage"
    periode = q.get("periode", PERIODES[1])
    dates = bornes(periode, date.today()) if periode != "Période choisie" else None
    try:
        du = dates[0] if dates else date.fromisoformat(q.get("du", ""))
        au = dates[1] if dates else date.fromisoformat(q.get("au", ""))
    except ValueError:
        du, au = bornes(PERIODES[1], date.today())
    affichage = q.get("affichage", AFFICHAGES_PARETO[0])
    categorie = q.get("categorie", TOUTES)
    try:
        articles, ventes = _articles_clover(ctx, du, au) if clover else _articles_sage(ctx, du, au)
    except (Exception, SystemExit) as erreur:  # noqa: BLE001
        ctx.app.noter(f"20/80 : {erreur!r}")
        articles, ventes = {}, {}  # tableau vide avec ses colonnes
        ctx.absents.add("Clover" if clover else "Sage")
    noms = [TOUTES] + sorted({a.categorie for a in (articles or {}).values()}, key=str.casefold)
    entete = onglets("Articles 20/80", ctx) + _formulaire(
        _choix("source", "Source", SOURCES, source) + _choix("periode", "Période", PERIODES, periode)
        + f"<div><label>du</label><input type='date' name='du' value='{du}'></div><div><label>au</label><input "
          f"type='date' name='au' value='{au}'></div>" + _choix("affichage", "Afficher", AFFICHAGES_PARETO, affichage)
        + "<button>🔍 Calculer</button>" + _choix("categorie", "Catégorie", noms, categorie), bouton=False)
    if articles is None:
        return Reponse(corps=page(ctx, "Rapports", entete + f"<p class='erreur'>{'Clover' if clover else 'Sage'} ne "
                                                            "répond pas pour l'instant.</p>"))
    lignes, resume = aa.pareto(articles, ventes, (au - du).days + 1, "" if categorie == TOUTES else categorie)
    classes_voulues = {AFFICHAGES_PARETO[0]: "A", AFFICHAGES_PARETO[1]: "AB"}.get(affichage, "ABC")
    visibles = [l for l in lignes if l[1] in classes_voulues]
    texte = (q.get("recherche") or "").strip().casefold()
    if texte:
        visibles = [l for l in visibles if any(texte in str(v).casefold() for v in l)]
    if lignes:
        ventes_a = (resume["ventes_A"] / resume["ventes"] * 100).quantize(aa.Decimal("0.1")) if resume["ventes"] else 0
        etat = (f"Les 20 % d'articles qui vendent le plus ({resume['A']} sur {resume['articles']} articles vendus) font "
                f"{str(ventes_a).replace('.', ',')} % de votre chiffre d'affaires ({argent(resume['ventes_A'])} sur "
                f"{argent(resume['ventes'])}) — valeur de leur stock : {argent(resume['valeur_A'])} ; de tous les "
                f"articles vendus : {argent(resume['valeur'])}")
        if resume["douteux"]:
            etat += (f" — {resume['douteux']} valeur(s) de stock douteuse(s) (coût plus de 5 fois le prix de vente) "
                     "laissée(s) hors des totaux : à vérifier.")
    else:
        etat = "Aucune vente sur cette période."
    corps = (entete + f"<p class='note'>{e(etat)}</p>"
             + tableau_section(Section(f"Articles 20/80 du {du} au {au} ({source})", _premiere(aa.ENTETES_PARETO, clover),
                                       visibles, classes=[f"classe-{l[1]}" for l in visibles]), limite=5000))
    return Reponse(corps=page(ctx, "Rapports", corps))


STYLE_RAPPORTS = """
nav.onglets { display: flex; flex-wrap: wrap; gap: 2px; border-bottom: 1px solid var(--bord); margin-bottom: 10px; }
nav.onglets a.onglet { padding: 7px 14px; text-decoration: none; color: var(--texte); border: 1px solid transparent;
  border-bottom: 0; border-radius: 6px 6px 0 0; font-size: 14px; }
nav.onglets a.onglet.actif { background: var(--carte); border-color: var(--bord); font-weight: 600; margin-bottom: -1px; }
nav.onglets a.onglet:hover { background: var(--menu-survol); }
.barre-onglet { display: flex; flex-wrap: wrap; gap: 8px; align-items: end; }
.barre-onglet .a-droite { margin-left: auto; }
.cartes-totaux { display: grid; grid-template-columns: 2fr 1fr 1fr 1fr; gap: 8px; margin: 2px 0 6px; }
.carte-total { background: var(--carte); border: 1px solid #dfe9e2; padding: 8px 12px; }
.carte-total .t { font-size: 12px; color: #6b7a70; } .carte-total .v { color: var(--vert); font-weight: 600; font-size: 19px; }
.carte-total.premiere .v { font-size: 24px; }
tr.ligne-bloquee td { background: #fde2e4 !important; } tr.ligne-a-encaisser td { background: #fff4d6 !important; }
tr.ligne-a-rapprocher td { background: #eaf2fb !important; }
tr.ligne-jamais td { background: #fde2e4 !important; } tr.ligne-stock td { background: #fff4d6 !important; }
tr.classe-A td { background: #dff3e4 !important; } tr.classe-B td { background: #fff4d6 !important; }
tr.classe-C td { background: #f3f4f3 !important; }
tr.ligne-anomalie td { background: #fde2e4 !important; } tr.ligne-approuvee td { background: #e3f1e7 !important; }
tr.ligne-corrigee td { background: #fff4d6 !important; }
tr.etat-applique td { background: #e6f4ea !important; } tr.etat-a-saisir td { background: #fff4d6 !important; }
tr.etat-ecart td { background: #fde2e4 !important; } tr.etat-ria td { background: #e4ecfb !important; }
tr.termine td { color: #7a857e; } tr.ligne-depot td { font-weight: 600; } .retrait { padding-left: 22px; }
a.depot { color: inherit; } pre.saisie { font-family: "Cascadia Mono", Consolas, monospace; font-size: 12.5px;
  white-space: pre-wrap; margin: 0; } .sous-titre { color: #6b7a70; margin: -6px 0 10px; }
button.accent { background: #e0a800; color: #222; }
tr.etat-propose td { background: #eaf2fb !important; }
tr.etat-encaisser td { background: #efe8fb !important; }
tr.negatif td { color: #c8102e; }
button.lien { background: none; border: 0; color: var(--texte); padding: 0; text-decoration: underline; cursor: pointer; font: inherit; }
.ok-texte { color: #1f7a3a; font-size: 13px; } span.calcule { display: inline-block; min-width: 70px; text-align: right;
  background: #e9eeea; padding: 6px; font-weight: 600; border-radius: 4px; }
.carte.edition .large { flex: 1; } .carte.edition .large input { width: 100%; }
.cartes-cinq { display: grid; grid-template-columns: repeat(5, 1fr); gap: 8px; margin: 8px 0; }
.carte-total .v.baisse { color: #c8102e; } button.danger { background: #c8102e; }
a.ouvrir.accent { background: #e0a800; color: #222; }
@media (max-width: 820px) { .cartes-cinq { grid-template-columns: 1fr 1fr; } }
.fiche-bas { display: flex; gap: 14px; flex-wrap: wrap; align-items: flex-start; }
.fiche-bas .factures { flex: 1; min-width: 280px; max-height: 300px; overflow: auto; }
label.facture { display: block; padding: 2px 0; } label.facture code { white-space: pre; font-size: 12.5px; }
.boutons-colonne { display: flex; flex-direction: column; gap: 6px; min-width: 210px; flex: none; }
.boutons-colonne > button, .boutons-colonne > a { flex: none; text-align: center; white-space: nowrap; }
.carte:has(.fiche-bas) { height: auto; overflow: visible; display: flow-root; }
.erreur-texte { color: #c8102e; font-size: 13px; align-self: center; }
.barre-onglet .periode { padding: 7px 10px; } .barre-onglet { align-items: center; margin-bottom: 8px; }
@media (max-width: 820px) { .cartes-totaux { grid-template-columns: 1fr 1fr; } .barre-onglet .a-droite { margin-left: 0; } }
"""

# --------------------------------------------------------------------------------------------- historique
AIDES_RECHERCHE = {
    "Client": "Choisissez le client : ses factures et encaissements, avec le solde.",
    "Fournisseur": "Choisissez le fournisseur : factures, paiements et notes de crédit, avec le solde dû.",
    "Article": "Choisissez l'article (n° ou nom) : ventes, achats, retours et ajustements, avec le cumul. « au » "
               "(facultatif) : une plage d'articles, chacun à la suite de l'autre avec son total.",
    "Vente": "Texte facultatif (n° de facture, client, montant) et période.",
    "Encaissement": "Texte facultatif (client, facture, n° d'encaissement, montant) et période.",
    "Paiement": "Texte facultatif (fournisseur, facture, pièce, montant) et période.",
    "Statistiques client": "Choisissez le client : ses achats par article ou par catégorie (Sage), sur la période et "
                           "la plage d'articles (facultatives).",
    "Statistiques fournisseur": "Choisissez le fournisseur : achats moins retours par article ou par catégorie (Sage), "
                                "sur la période et la plage d'articles (facultatives).",
    "Statistiques employé": "Choisissez l'employé : ses ventes par article ou par catégorie (Clover), sur la période "
                            "(30 derniers jours si elle est vide)."}


def historique(ctx: Contexte) -> Reponse:
    """Comme l'onglet « Recherche dans l'historique » de page_rapports : « Rechercher : » (9 types) + valeur, plage
    d'articles « du … au », Catégorie, « Par : », « Période du … au », « 🔍 Rechercher », « ✖ Réinitialiser les
    filtres » ; titre des résultats, nombre de résultats, lignes de total en gras."""
    from .. import rapports
    from ..page_rapports import REGROUPEMENTS, STATISTIQUES, TYPES_RECHERCHE
    from .consultations import lire_ou_vide

    q = ctx.req.query
    type_ = q.get("type") if q.get("type") in TYPES_RECHERCHE else TYPES_RECHERCHE[0]
    valeur, categorie = q.get("valeur", "").strip(), q.get("categorie", "").strip()
    de, a = q.get("du_art", "").split(" — ")[0].strip(), q.get("au_art", "").split(" — ")[0].strip()
    par = q.get("par") if q.get("par") in REGROUPEMENTS else REGROUPEMENTS[0]

    def jour(cle):
        try:
            return date.fromisoformat(q.get(cle, ""))
        except ValueError:
            return None

    du, au = jour("du"), jour("au")
    # listes à choisir (comme les ChampRecherche de Windows)
    from .pages_fournisseurs import _listes

    noms_fournisseurs, articles = _listes(ctx.racine)
    listes = {"Fournisseur": noms_fournisseurs, "Statistiques fournisseur": noms_fournisseurs}
    if type_ in ("Client", "Statistiques client"):
        try:
            listes[type_] = lire_ou_vide(ctx, lambda b: [r["n"] for r in b.requete(
                "SELECT TRIM(sName) n FROM tcustomr ORDER BY sName") if r["n"]])
        except (Exception, SystemExit):  # noqa: BLE001
            listes[type_] = []
    if type_ == "Statistiques employé":
        from .. import paie_temps as pt

        listes[type_] = [x.nom for x in pt.Registre(ctx.racine).employes]
    valeurs_articles = [f"{x.numero} — {x.description}" for x in articles]
    plage = type_ in ("Article", "Statistiques client", "Statistiques fournisseur")
    types = "".join(f"<option{' selected' if x == type_ else ''}>{e(x)}</option>" for x in TYPES_RECHERCHE)
    pars = "".join(f"<option{' selected' if x == par else ''}>{e(x)}</option>" for x in REGROUPEMENTS)

    def liste(id_, valeurs):
        return f"<datalist id='{id_}'>" + "".join(f"<option value='{e(x)}'>" for x in valeurs) + "</datalist>"

    formulaire = (
        "<form method='get'><div class='barre-onglet'><div><label>Rechercher :</label><select name='type'>"
        f"{types}</select></div>"
        + ("" if type_ == "Article" else
           f"<div class='large'><input name='valeur' list='valeurs' value='{e(valeur)}' size='46'>"
           f"{liste('valeurs', listes.get(type_, []))}</div>")
        + "<button class='second' name='changer' value='1'>Choisir</button></div><div class='barre-onglet'>"
        + (f"<div><label>{'Article' if type_ == 'Article' else 'Articles du'}</label><input name='du_art' "
           f"list='articles-sage' value='{e(q.get('du_art', ''))}' size='30'></div><div><label>au</label><input "
           f"name='au_art' list='articles-sage' value='{e(q.get('au_art', ''))}' size='30'></div>"
           f"{liste('articles-sage', valeurs_articles)}" if plage else "")
        + (f"<div><label>Catégorie</label><input name='categorie' value='{e(categorie)}' size='22'></div>"
           if type_ == "Article" or type_ in STATISTIQUES else "")
        + (f"<div><label>Par :</label><select name='par'>{pars}</select></div>" if type_ in STATISTIQUES else "")
        + f"<div><label>Période du</label><input type='date' name='du' value='{du or ''}'></div><div><label>au</label>"
          f"<input type='date' name='au' value='{au or ''}'></div><button name='chercher' value='1'>🔍 Rechercher"
          f"</button><a class='ouvrir' href='?type={e(type_)}'>✖ Réinitialiser les filtres</a></div></form>")
    aide = AIDES_RECHERCHE[type_]
    resultat = "<div class='defile'><table><tr><td class='vide'></td></tr></table></div>"  # zone vide comme Windows
    if q.get("chercher"):
        tous = {"Client": "tous les clients", "Fournisseur": "tous les fournisseurs",
                "Statistiques client": "tous les clients", "Statistiques fournisseur": "tous les fournisseurs",
                "Statistiques employé": "tous les employés"}
        affiche = valeur
        if type_ == "Article":
            affiche = (q.get("du_art", "").strip() or "tous") + (f"  →  {q.get('au_art', '').strip()}" if a else "")
        titre = f"Résultats : {type_}" + (f" — {affiche}" if affiche else (f" — {tous[type_]}" if type_ in tous else "")) \
            + (f" — par {par.lower()}" if type_ in STATISTIQUES else "") \
            + (f" — articles {de} → {a or '…'}" if type_ in ("Statistiques client", "Statistiques fournisseur")
               and (de or a) else "") + (f" — catégorie {categorie}" if categorie else "")
        try:
            entetes, lignes = _recherche_historique(ctx, type_, valeur, categorie, de, a, par, du, au)
        except (Exception, SystemExit) as erreur:  # noqa: BLE001 — tableau vide, source signalée
            ctx.app.noter(f"Recherche dans l'historique : {erreur!r}")
            ctx.absents.add("Clover" if type_ == "Statistiques employé" else "Sage")
            entetes, lignes = [], []
        totaux = [i_ for i_, l in enumerate(lignes) if any(str(x).startswith(("Total", "… plus de")) for x in l[:4])]
        from .consultations import Section, tableau_section

        aide = f"{len(lignes) - len(totaux)} résultat(s)."
        resultat = tableau_section(Section(titre, entetes, lignes, classes=["total" if i_ in totaux else ""
                                                                            for i_ in range(len(lignes))]), limite=20000)
    corps = onglets("Recherche dans l'historique", ctx) + formulaire + f"<p class='note'>{e(aide)}</p>" + resultat
    return Reponse(corps=page(ctx, "Rapports", corps))


def _recherche_historique(ctx: Contexte, type_, valeur, categorie, de, a, par, du, au):
    """Comme PageRapports.rechercher (et _statistiques_employe pour l'employé)."""
    from .. import rapports
    from ..page_rapports import STATISTIQUES
    from .consultations import lire_ou_vide

    if type_ == "Statistiques employé":
        from ..points_vente import client
        from ..statistiques_clover import detail_par_jour, filtrer, lire, statistiques

        au = au or date.today()
        du = du or au - timedelta(days=29)
        donnees = lire(client(ctx.racine), du, au, ctx.racine / "donnees" / "cache_clover")
        filtres = {k: x for k, x in (("Employé", valeur), ("Catégorie", categorie)) if x}
        nom_vue = "Par catégorie" if par.startswith("Catégorie") else "Par article"
        donnees = filtrer(donnees, filtres)
        return detail_par_jour(donnees, nom_vue) if par.endswith("par jour") else statistiques(donnees)[nom_vue]
    categories = rapports.categories_par_compte(ctx.racine) if type_ in STATISTIQUES or categorie else {}
    fonctions = {
        "Article": lambda b: (rapports.mouvements_article(b, de, du, au) if de and (not a or a == de) and not categorie
                              else rapports.mouvements_articles(b, de, a, du, au, categorie, categories)),
        "Vente": lambda b: rapports.recherche_ventes(b, valeur, du, au),
        "Encaissement": lambda b: rapports.recherche_encaissements(b, valeur, du, au),
        "Paiement": lambda b: rapports.recherche_paiements(b, valeur, du, au),
        "Statistiques client": lambda b: rapports.statistiques_tiers(b, "client", valeur, par, du, au, de, a,
                                                                     categories, categorie),
        "Statistiques fournisseur": lambda b: rapports.statistiques_tiers(b, "fournisseur", valeur, par, du, au, de,
                                                                          a, categories, categorie)}
    if type_ in fonctions:
        return lire_ou_vide(ctx, fonctions[type_])
    import time

    gardee = ctx.app.memoire.get("historique_sage")  # historique des tiers lu une fois (10 min), comme Windows
    if gardee and time.time() - gardee[0] < 600:
        h = gardee[1]
    else:
        h = lire_ou_vide(ctx, rapports.historique)
        if "Sage" not in ctx.absents:
            ctx.app.memoire["historique_sage"] = (time.time(), h)
    fonction = {"Client": rapports.h_mouvements_client, "Fournisseur": rapports.h_mouvements_fournisseur}[type_]
    return fonction(h, valeur, du, au)


def _interrogation(type_: str):
    """Interrogation de compte = « Recherche dans l'historique » de ce type (Application.ouvrir_interrogation)."""
    def gestionnaire(ctx: Contexte) -> Reponse:
        # même page, sous l'adresse de l'interrogation : son droit suffit (comme dans Windows)
        ctx.req.query.setdefault("type", type_)
        return historique(ctx)
    return gestionnaire


FONCTIONS = [
    Fonction("/interrogation-client", "Interrogation de compte client", "rapports", _interrogation("Client"), "🔎",
             "Vente", menu=False),
    Fonction("/interrogation-fournisseur", "Interrogation de compte fournisseur", "rapports",
             _interrogation("Fournisseur"), "🔎", "Fournisseur", menu=False),
    Fonction("/interrogation-article", "Interrogation de compte article", "rapports", _interrogation("Article"), "🔎",
             "Articles", menu=False),
    Fonction("/historique", "Recherche dans l'historique", "rapports", historique, "🔎", "État", menu=False),
    Fonction("/suivi-ventes", "Suivi des ventes", "rapports", suivi_ventes, "📈", "État", menu=False),
    Fonction("/inactifs", "Produits inactifs", "rapports", inactifs, "💤", "État", menu=False),
    Fonction("/pareto", "Articles 20/80", "rapports", pareto, "🥇", "État", menu=False),
]
WEB = {"Suivi des ventes": "/suivi-ventes", "Produits inactifs": "/inactifs", "Articles 20/80": "/pareto",
       "Recherche dans l'historique": "/historique", "Interrogation de compte client": "/interrogation-client",
       "Interrogation de compte fournisseur": "/interrogation-fournisseur",
       "Interrogation de compte article": "/interrogation-article"}
