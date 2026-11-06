"""3e vague de l'application web (demande du propriétaire du 2026-11-03 : « lance toutes les vagues à la suite ») :
rubrique État (suivi des ventes, recherche dans l'historique, produits inactifs, articles 20/80), calendrier de
paie, coût de la main-d'œuvre, budget et écarts, factures fournisseurs archivées, comptes Sage par catégorie.
Mêmes calculs que les fenêtres Windows (page_rapports, onglets_articles, fenetre_paie, fenetres_gestion3,
fenetre_comptabilite, fenetre_article).
"""

from __future__ import annotations

import time
from datetime import date, timedelta
from decimal import Decimal

from .consultations import Consultation, Section, _cherche, _mois, sage

DUREE = 600  # s : catalogue et ventes Clover gardés 10 min


def _garde(ctx, cle, fonction):
    gardee = ctx.app.memoire.get(cle)
    if gardee and time.time() - gardee[0] < DUREE:
        return gardee[1]
    valeur = fonction()
    ctx.app.memoire[cle] = (time.time(), valeur)
    return valeur


def _clover_articles(ctx, du: date, au: date):
    """(catalogue Clover, ventes par article) de la période, comme onglets_articles._lire_clover."""
    from ..cache_lectures import inventaire_clover
    from ..points_vente import client
    from ..previsions import ventes_par_article_rapide

    return _garde(ctx, ("clover_articles", du, au), lambda: (
        inventaire_clover(ctx.racine),
        ventes_par_article_rapide(client(ctx.racine), du, au, ctx.racine / "donnees" / "cache_clover")))


def _premiere(entetes: list[str]) -> list[str]:
    return [{"N° Sage": "ID Clover", "CUMP": "Coût Clover"}.get(x, x) for x in entetes]


def _argent(v) -> str:
    from .pages import argent

    return argent(v)


# --------------------------------------------------------------------------------------------- État
def _suivi(ctx, v):
    from ..encaissements import numero_compte_sage
    from ..facture import CLIENT
    from ..rapports import ENTETES_SUIVI, suivi_ventes

    compte = numero_compte_sage(str(ctx.config.get("encaissements", {}).get("compte_depot", "1055")))
    suivi = sage(ctx, lambda b: suivi_ventes(ctx.racine, b, CLIENT, compte), ("suivi_ventes",))
    lignes = [[s.traitement, s.journee, s.statut, s.ht, s.taxes, s.ttc, s.commentaire, s.encaissement,
               s.rapprochement] for s in suivi]
    return [Section("Suivi des ventes", ENTETES_SUIVI, _cherche(lignes, v),
                    "Chaque journée : facture dans Sage, encaissement (solde dû) et rapprochement avec les relevés.")]


def _historique(ctx, v):
    from .. import rapports as rp

    genre = v.get("type", "Ventes")
    fonction = {"Ventes": rp.recherche_ventes, "Encaissements": rp.recherche_encaissements,
                "Paiements": rp.recherche_paiements}.get(genre, rp.recherche_ventes)
    texte, du, au = v.get("texte", ""), v["du"], v["au"]
    entetes, lignes = sage(ctx, lambda b: fonction(b, texte, du, au), ("histo", genre, texte, du, au))
    return [Section(f"{genre} du {du} au {au}", entetes, lignes,
                    "Clients, fournisseurs et articles : rubriques Vente, Fournisseur et Articles > Interrogation "
                    "de compte.")]


def _inactifs(ctx, v):
    from .. import analyse_articles as aa

    try:
        jours = max(1, int(v.get("jours") or 30))
    except ValueError:
        jours = 30
    aujourdhui = date.today()
    items, ventes = _clover_articles(ctx, aujourdhui - timedelta(days=aa.JOURS_CLOVER), aujourdhui)
    articles = aa.articles_clover(items, ventes)
    lignes, resume = aa.produits_inactifs(articles, jours, aujourdhui, bool(v.get("stock")), v.get("categorie", ""),
                                          aa.JAMAIS_CLOVER)
    entetes = _premiere(aa.ENTETES_INACTIFS)
    lignes = [l[:6] + l[7:] for l in lignes]  # aucun achat dans Clover
    entetes = entetes[:6] + entetes[7:]
    tranches = " • ".join(f"{k} : {n}" for k, n in resume["tranches"].items())
    return [Section(f"Produits sans vente depuis {jours} jours ou plus (Clover)", entetes, lignes,
                    f"{resume['articles']} article(s), valeur du stock immobilisé {_argent(resume['valeur'])}. "
                    f"{tranches}")]


def _pareto(ctx, v):
    from .. import analyse_articles as aa

    du, au = v["du"], v["au"]
    items, ventes = _clover_articles(ctx, du, au)
    articles, par_article = aa.articles_clover(items, ventes), aa.ventes_clover(ventes)
    lignes, resume = aa.pareto(articles, par_article, (au - du).days + 1, v.get("categorie", ""))
    classes = {"Classe A": "A", "Classes A et B": "AB"}.get(v.get("affichage", ""), "ABC")
    visibles = [l for l in lignes if l[1] in classes]
    part = (resume["ventes_A"] / resume["ventes"] * 100).quantize(Decimal("0.1")) if resume.get("ventes") else 0
    return [Section(f"Articles 20/80 du {du} au {au} (Clover)", _premiere(aa.ENTETES_PARETO), visibles,
                    f"{resume.get('A', 0)} article(s) de classe A (les 20 % qui vendent le plus) = {part} % des ventes "
                    f"({_argent(resume.get('ventes', 0))}).".replace(".", ",", 1) if lignes else "")]


# --------------------------------------------------------------------------------------------- paie et gestion
def _calendrier(ctx, v):
    """Comme fenetre_paie.FenetreCalendrier : paies passées en gris, la prochaine en vert."""
    from ..calendrier_paie import Calendrier

    try:
        annee = int(v.get("annee") or date.today().year)
    except ValueError:
        annee = date.today().year
    cal = Calendrier(ctx.racine)
    paies = cal.paies(annee)
    aujourdhui = date.today()
    prochaine = cal.prochaine(aujourdhui)
    lignes = [[str(p.numero), p.jour.isoformat(), p.debut.isoformat(), p.fin.isoformat(),
               "Payée" if p.jour < aujourdhui else "À venir"] for p in paies]
    classes = ["etat-applique" if prochaine and p.jour == prochaine.jour else ("termine" if p.jour < aujourdhui else "")
               for p in paies]
    if not cal.premiere(annee):
        note = ("Renseignez la date de la première paie de l'année dans « Administration > Sage 50 », carte « Paie » : "
                "les paies suivantes (tous les 14 jours) et leurs périodes se calculent.")
    else:
        note = f"{len(paies)} paies en {annee}." + ("" if cal.saisie(annee) else
                                                   " Suite de l'année précédente : modifiable dans « Administration > "
                                                   "Sage 50 ».")
    return [Section(f"Calendrier de paie {annee}", ["N°", "Date de paie", "Période du", "au", "État"], lignes, note,
                    classes=classes)]


def _main_oeuvre(ctx, v):
    from .. import budget as bu
    from ..points_vente import cache_clover, client, permis
    from ..previsions import ventes_par_jour
    from ..statistiques_clover import lire

    from ..depots import points_vente_des
    from .filtres import depots_choisis

    debut, fin = v["du"], v["au"]
    taux, charges = bu.taux_et_charges(ctx.config)
    hier = min(fin, date.today())
    depots = depots_choisis(ctx)
    codes = points_vente_des(ctx.config, depots)

    def ventes_clover():
        ventes: dict = {}
        for pv in permis(ctx.config, ctx.reg.points_vente_permis(ctx.u)):
            if codes is not None and pv.code not in codes:
                continue  # filtre « Dépôt »
            for jour, montant in ventes_par_jour(lire(client(ctx.racine, pv), debut, hier,
                                                      cache_clover(ctx.racine, pv))).items():
                ventes[jour] = ventes.get(jour, Decimal(0)) + montant
        return ventes

    ventes = _garde(ctx, ("ventes_jour", debut, hier, tuple(codes or ())), ventes_clover) if debut <= hier else {}
    pointees, planifiees = bu.heures_par_jour_tous(ctx.racine, debut, fin, depots)
    lignes = bu.main_oeuvre(ventes, pointees, planifiees, debut, fin, taux, charges)
    total_v = sum((l[1] for l in lignes), Decimal(0))
    total_c = sum((l[4] for l in lignes), Decimal(0))
    part = f"{total_c / total_v * 100:.1f} %".replace(".", ",") if total_v else "—"
    return [Section(f"Coût de la main-d'œuvre du {debut} au {fin}",
                    ["Date", "Ventes nettes", "Heures pointées", "Heures planifiées", "Coût estimé", "Part des ventes"],
                    lignes, f"Total : ventes {_argent(total_v)}, coût {_argent(total_c)} ({part}). Coût = heures × "
                            f"{_argent(taux)} × (1 + {charges} % de charges sociales) ; aucun taux d'employé gardé.")]


def _budget(ctx, v):
    from .. import comptabilite as cp
    from ..budget import ENTETES_BUDGET, POSTES, Budget, ecarts, reel

    annee, mois = _mois(v.get("mois"))
    budget = Budget(ctx.racine)
    reels = sage(ctx, lambda b: [reel(cp.etat_resultats(b, annee, m)) for m in range(1, mois + 1)],
                 ("budget", annee, mois))
    cumul_r = {p: sum((r[p] for r in reels), Decimal(0)) for p in POSTES}
    cumul_b = {p: sum((budget.mois(annee, m)[p] for m in range(1, mois + 1)), Decimal(0)) for p in POSTES}
    return [Section(f"Budget et écarts de {annee}-{mois:02d}", ENTETES_BUDGET,
                    ecarts(reels[-1], budget.mois(annee, mois), cumul_r, cumul_b),
                    "Écart = réel − budget ; depuis janvier = cumul de l'année. Saisie du budget : application "
                    "complète.")]


def _archives(ctx, v):
    from ..fournisseurs import archives

    lignes = []
    for a in archives(ctx.racine):
        total = Decimal(a["total"]) if a.get("total") not in (None, "") else None
        lignes.append([a.get("date_facture", ""), a.get("fournisseur_sage") or a.get("fournisseur_lu", ""),
                       a.get("numero", ""), total, len(a.get("lignes", [])), a.get("archivee_le", "").replace("T", " ")])
    lignes.sort(key=lambda l: str(l[0]), reverse=True)
    return [Section("Factures fournisseurs archivées", ["Date", "Fournisseur", "N°", "Total", "Lignes", "Archivée le"],
                    _cherche(lignes, v))]


def _categories(ctx, v):
    from ..creation_articles import TableCategories

    table = TableCategories(ctx.racine)
    lignes = [[c.categorie, c.prefixe, c.actif, c.produits, c.cmv, c.ecart]
              for c in sorted(table.lignes.values(), key=lambda c: c.categorie.casefold())]
    return [Section("Comptes Sage par catégorie Clover", ["Catégorie", "Préfixe", "Actif", "Produits", "CMV", "Écart"],
                    _cherche(lignes, v), "Comptes donnés aux articles créés de chaque catégorie. Modification : "
                                         "application complète.")]


ANNEES = [str(date.today().year + i) for i in range(-1, 5)]  # comme FenetreCalendrier
CONSULTATIONS_ETAT = [
    Consultation("/calendrier-paie", "Calendrier de paie", "rapprochement", (), _calendrier, "", "📆", "Paie",
                 sans_sage=True, choix={"annee": ("Année", ANNEES)}, defauts={"annee": str(date.today().year)}),
    Consultation("/main-oeuvre", "Coût de la main-d'œuvre", "rapprochement", ("periode", "depot"), _main_oeuvre, "", "👷",
                 "Paie", sans_sage=True, defauts={"du": date.today() - timedelta(days=28),
                                                  "au": date.today() + timedelta(days=13)}, bouton="🔍 Afficher"),
]
