"""Rapports des fonctions de gestion dans les statistiques Clover (demande du propriétaire du 2026-10-30) : pour
chaque fonction (pertes, caisse, dépenses, main-d'œuvre, promotions, retours, bons de commande), sur la période
choisie dans les statistiques :

- des cartes d'indicateurs ;
- un graphique d'évolution (par jour jusqu'à 62 jours, sinon par mois) ;
- une carte graphique (répartition : anneau ou classement) ;
- le rapport détaillé (tableau exportable).

Lecture seule : registres de l'application et données Clover déjà lues par les statistiques (`contexte`). Les textes
sont en français ; l'interface les traduit (tous dans `TEXTES`, vérifiés par les tests).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

ZERO, CENT = Decimal(0), Decimal("0.01")
JOURS_MAX_PAR_JOUR = 62  # au-delà, l'évolution est regroupée par mois


@dataclass
class RapportGestion:
    cartes: list[tuple[str, str, object]] = field(default_factory=list)  # (titre, genre « $ » « n » « % » « h » « t », valeur)
    titre_evolution: str = ""
    etiquettes: list[str] = field(default_factory=list)
    series: list[tuple[str, list]] = field(default_factory=list)          # (nom, valeurs)
    titre_repartition: str = ""
    genre_repartition: str = "anneau"                                     # « anneau » ou « classement »
    repartition: list[tuple[str, Decimal]] = field(default_factory=list)
    argent_repartition: bool = True
    entetes: list[str] = field(default_factory=list)
    lignes: list[list] = field(default_factory=list)
    note: str = ""


def _d(v) -> Decimal:
    try:
        return Decimal(str(v or 0))
    except Exception:
        return ZERO


def _dans(jour: str, du: date, au: date) -> bool:
    return du.isoformat() <= (jour or "")[:10] <= au.isoformat()


def evolution(par_jour: dict[date, Decimal], du: date, au: date) -> tuple[list[str], list[Decimal]]:
    """Valeurs jour par jour (« JJ/MM ») jusqu'à 62 jours, sinon mois par mois (« MM/AAAA »)."""
    if (au - du).days < JOURS_MAX_PAR_JOUR:
        jours = [du + timedelta(days=i) for i in range((au - du).days + 1)]
        return [f"{j.day:02d}/{j.month:02d}" for j in jours], [par_jour.get(j, ZERO) for j in jours]
    mois: dict[tuple[int, int], Decimal] = {}
    j = du.replace(day=1)
    while j <= au:
        mois[(j.year, j.month)] = ZERO
        j = (j + timedelta(days=32)).replace(day=1)
    for jour, v in par_jour.items():
        if (jour.year, jour.month) in mois:
            mois[(jour.year, jour.month)] += v
    return [f"{m:02d}/{a}" for a, m in mois], list(mois.values())


def _ajouter(d: dict, cle, valeur) -> None:
    d[cle] = d.get(cle, ZERO) + valeur


def _pourcent(partie: Decimal, total: Decimal) -> Decimal:
    return (partie * 100 / total).quantize(Decimal("0.1")) if total else ZERO


# --------------------------------------------------------------------------------------------- pertes
def pertes(racine: Path, du: date, au: date, contexte: dict) -> RapportGestion:
    from . import pertes as pe

    liste = [p for p in pe.Registre(racine).pertes if _dans(p.jour, du, au)]
    r = RapportGestion(entetes=["Date", "N°", "Motif", "Article", "Catégorie", "Quantité", "Coût unitaire", "Valeur",
                                "Point de vente"])
    par_jour, par_motif, total, articles = {}, {}, ZERO, 0
    for p in liste:
        for l in p.lignes:
            v = l.valeur
            total += v
            articles += 1
            _ajouter(par_jour, date.fromisoformat(p.jour[:10]), v)
            _ajouter(par_motif, p.motif or "Autre", v)
            r.lignes.append([p.jour[:10], p.numero, p.motif, l.nom, l.categorie, _d(l.quantite), _d(l.cout), v,
                             p.point_vente or "1"])
    ventes = sum(contexte.get("ventes_par_jour", {}).values(), ZERO)
    r.cartes = [("Valeur des pertes", "$", total.quantize(CENT)), ("Déclarations", "n", len(liste)),
                ("Lignes d'articles", "n", articles), ("Part des ventes nettes", "%", _pourcent(total, ventes))]
    r.titre_evolution = "Valeur des pertes"
    r.etiquettes, valeurs = evolution(par_jour, du, au)
    r.series = [("Valeur des pertes", valeurs)]
    r.titre_repartition, r.repartition = "Pertes par motif", sorted(par_motif.items(), key=lambda x: -x[1])
    return r


# --------------------------------------------------------------------------------------------- caisse
def caisse(racine: Path, du: date, au: date, contexte: dict) -> RapportGestion:
    from . import caisse as ca

    r = RapportGestion(entetes=["Date", "Espèces vendues", "Remboursements", "Argent remis", "Fond du matin",
                                "Attendu", "Compté", "Écart", "À déposer", "Compté par"])
    donnees = contexte.get("donnees")
    if not donnees:
        r.note = "Calculez d'abord les statistiques de la période (espèces lues dans Clover)."
        return r
    r.lignes = ca.lignes_jours(ca.attendus(donnees), ca.Registre(racine), du, au, contexte.get("config", {}))
    ecarts, attendu, comptes, non_comptes, hors_seuil = {}, ZERO, 0, 0, 0
    for l in r.lignes:
        attendu += _d(l[5])
        if l[7] != "":
            comptes += 1
            ecarts[date.fromisoformat(l[0])] = _d(l[7])
            hors_seuil += abs(_d(l[7])) > ca.SEUIL_ECART
        else:
            non_comptes += 1
    r.cartes = [("Espèces attendues", "$", attendu.quantize(CENT)),
                ("Écart cumulé", "$", sum(ecarts.values(), ZERO).quantize(CENT)),
                ("Jours comptés", "n", comptes), ("Jours non comptés", "n", non_comptes),
                ("Écarts de plus de 5 $", "n", int(hors_seuil))]
    r.titre_evolution = "Écart de caisse (compté − attendu)"
    r.etiquettes, valeurs = evolution(ecarts, du, au)
    r.series = [("Écart", valeurs)]
    r.titre_repartition, r.argent_repartition = "Comptages de la période", False
    r.repartition = [(k, Decimal(v)) for k, v in (("Écart de 5 $ ou moins", comptes - int(hors_seuil)),
                                                    ("Écart de plus de 5 $", int(hors_seuil)),
                                                    ("Non compté", non_comptes)) if v]
    return r


# --------------------------------------------------------------------------------------------- dépenses
def depenses(racine: Path, du: date, au: date, contexte: dict) -> RapportGestion:
    from . import depenses as dp

    registre = dp.Registre(racine)
    liste = [d for d in registre.depenses if _dans(d.jour, du, au) and d.moyen != dp.APPRO]
    r = RapportGestion(entetes=["Date", "N°", "Fournisseur", "Description", "Compte", "Payée par", "Hors taxes", "TPS",
                                "TVQ", "Total", "État"])
    par_jour, par_compte, ttc, taxes = {}, {}, ZERO, ZERO
    for d in liste:
        montant = _d(d.montant)
        ht, tps, tvq = dp.taxes_de(montant, d.taxe)
        ttc += montant
        taxes += tps + tvq
        _ajouter(par_jour, date.fromisoformat(d.jour[:10]), montant)
        _ajouter(par_compte, d.compte or "Sans compte", ht)
        r.lignes.append([d.jour[:10], d.numero, d.fournisseur, d.description, d.compte, d.moyen, ht, tps, tvq, montant,
                         d.etat])
    r.cartes = [("Dépenses (taxes comprises)", "$", ttc.quantize(CENT)), ("Taxes à récupérer", "$", taxes.quantize(CENT)),
                ("Dépenses", "n", len(liste)), ("Solde de la petite caisse", "$", registre.solde_petite_caisse())]
    r.titre_evolution = "Dépenses (taxes comprises)"
    r.etiquettes, valeurs = evolution(par_jour, du, au)
    r.series = [("Dépenses", valeurs)]
    r.titre_repartition, r.genre_repartition = "Dépenses hors taxes par compte", "classement"
    r.repartition = sorted(par_compte.items(), key=lambda x: -x[1])[:8]
    return r


# --------------------------------------------------------------------------------------------- main-d'œuvre
def main_oeuvre(racine: Path, du: date, au: date, contexte: dict) -> RapportGestion:
    from . import paie_temps as pt
    from .budget import heures_par_jour_tous, main_oeuvre as calcul, taux_et_charges

    taux, charges = taux_et_charges(contexte.get("config", {}))
    pointees, planifiees = heures_par_jour_tous(racine, du, au)
    ventes = contexte.get("ventes_par_jour", {})
    r = RapportGestion(entetes=["Date", "Ventes nettes", "Heures pointées", "Heures planifiées", "Coût estimé",
                                "Part des ventes"])
    r.lignes = calcul(ventes, pointees, planifiees, du, au, taux, charges)
    h, hp = sum(pointees.values(), ZERO), sum(planifiees.values(), ZERO)
    cout, total_ventes = sum((_d(l[4]) for l in r.lignes), ZERO), sum(ventes.values(), ZERO)
    r.cartes = [("Heures pointées", "h", h.quantize(CENT)), ("Heures planifiées", "h", hp.quantize(CENT)),
                ("Coût estimé", "$", cout.quantize(CENT)), ("Part des ventes nettes", "%", _pourcent(cout, total_ventes)),
                ("Ventes par heure pointée", "$", (total_ventes / h).quantize(CENT) if h else ZERO)]
    r.titre_evolution = "Heures pointées et planifiées"
    r.etiquettes, v1 = evolution(pointees, du, au)
    _, v2 = evolution(planifiees, du, au)
    r.series = [("Heures pointées", v1), ("Heures planifiées", v2)]
    registre, par_employe = pt.Registre(racine), {}
    for e in registre.employes:
        liste, _ = pt.presences(registre.valides(e.id))
        heures = sum((p.heures for p in liste if du <= p.jour <= au), ZERO)
        if heures:
            par_employe[e.nom] = heures
    r.titre_repartition, r.genre_repartition, r.argent_repartition = "Heures pointées par employé", "classement", False
    r.repartition = sorted(par_employe.items(), key=lambda x: -x[1])[:8]
    r.note = "Coût estimé = heures pointées × taux moyen × (1 + charges sociales), réglages [paie] de la configuration."
    return r


# --------------------------------------------------------------------------------------------- promotions
def promotions(racine: Path, du: date, au: date, contexte: dict) -> RapportGestion:
    from .paquet3 import Promotions

    liste = [p for p in Promotions(racine).liste if p.du <= au.isoformat() and p.au >= du.isoformat()]
    r = RapportGestion(entetes=["N°", "Article", "Prix normal", "Prix promotionnel", "Baisse", "Du", "Au", "État",
                                "Point de vente"])
    actives, par_etat, baisses = {}, {}, []
    for p in liste:
        normal, promo = _d(p.prix_normal), _d(p.prix_promo)
        baisse = _pourcent(normal - promo, normal) if normal else None
        if baisse is not None:
            baisses.append(baisse)
        _ajouter(par_etat, p.etat, Decimal(1))
        j = max(du, date.fromisoformat(p.du))
        while j <= min(au, date.fromisoformat(p.au)):
            _ajouter(actives, j, Decimal(1))
            j += timedelta(days=1)
        r.lignes.append([p.numero, p.nom, normal if normal else "", promo, f"{baisse} %".replace(".", ",")
                         if baisse is not None else "", p.du, p.au, p.etat, p.point_vente or "1"])
    r.cartes = [("Promotions", "n", len(liste)), ("Articles en promotion", "n", len({p.id_clover for p in liste})),
                ("Baisse moyenne", "%", (sum(baisses, ZERO) / len(baisses)).quantize(Decimal("0.1")) if baisses else ZERO)]
    r.titre_evolution = "Promotions en cours par jour"
    r.etiquettes, valeurs = evolution(actives, du, au)
    r.series = [("Promotions en cours", valeurs)]
    r.titre_repartition, r.argent_repartition = "Promotions par état", False
    r.repartition = sorted(par_etat.items(), key=lambda x: -x[1])
    return r


# --------------------------------------------------------------------------------------------- retours
def retours(racine: Path, du: date, au: date, contexte: dict) -> RapportGestion:
    from . import retours as rt

    liste = [x for x in rt.Registre(racine).retours if _dans(x.jour, du, au)]
    r = RapportGestion(entetes=["Date", "N°", "Fournisseur", "Facture d'origine", "Motif", "Lignes", "Montant", "État"])
    par_jour, par_fournisseur, total = {}, {}, ZERO
    for x in liste:
        montant = sum((l.montant for l in x.lignes), ZERO)
        total += montant
        _ajouter(par_jour, date.fromisoformat(x.jour[:10]), montant)
        _ajouter(par_fournisseur, x.fournisseur_sage, montant)
        r.lignes.append([x.jour[:10], x.numero, x.fournisseur_sage, x.facture_origine, x.motif, len(x.lignes), montant,
                         x.etat])
    r.cartes = [("Montant des retours", "$", total.quantize(CENT)), ("Retours", "n", len(liste)),
                ("Fournisseurs", "n", len(par_fournisseur))]
    r.titre_evolution = "Montant des retours"
    r.etiquettes, valeurs = evolution(par_jour, du, au)
    r.series = [("Retours", valeurs)]
    r.titre_repartition, r.genre_repartition = "Retours par fournisseur", "classement"
    r.repartition = sorted(par_fournisseur.items(), key=lambda x: -x[1])[:8]
    return r


# --------------------------------------------------------------------------------------------- bons de commande
def bons(racine: Path, du: date, au: date, contexte: dict) -> RapportGestion:
    from . import bons_commande as bc

    liste = [b for b in bc.Registre(racine).bons if _dans(b.date, du, au)]
    r = RapportGestion(entetes=["Date", "N°", "Fournisseur", "Lignes", "Total", "État", "Facture"])
    par_jour, par_fournisseur, total, recus = {}, {}, ZERO, 0
    for b in liste:
        total += b.total
        recus += b.etat != bc.CREE
        _ajouter(par_jour, date.fromisoformat(b.date[:10]), b.total)
        _ajouter(par_fournisseur, b.fournisseur, b.total)
        r.lignes.append([b.date[:10], b.numero, b.fournisseur, len(b.lignes), b.total, b.etat, b.facture])
    r.cartes = [("Montant commandé", "$", total.quantize(CENT)), ("Bons de commande", "n", len(liste)),
                ("Reçus", "n", recus), ("En attente", "n", len(liste) - recus)]
    r.titre_evolution = "Montant commandé"
    r.etiquettes, valeurs = evolution(par_jour, du, au)
    r.series = [("Montant commandé", valeurs)]
    r.titre_repartition, r.genre_repartition = "Commandes par fournisseur", "classement"
    r.repartition = sorted(par_fournisseur.items(), key=lambda x: -x[1])[:8]
    return r


# (libellé du menu, clé de la vue, fonction) : section « Gestion » des statistiques
ETATS = [("Pertes et démarque", "g_pertes", pertes), ("Contrôle de la caisse", "g_caisse", caisse),
         ("Petite caisse et dépenses", "g_depenses", depenses), ("Main-d'œuvre", "g_main_oeuvre", main_oeuvre),
         ("Promotions", "g_promotions", promotions), ("Retours fournisseurs", "g_retours", retours),
         ("Bons de commande", "g_bons", bons)]
CLES = {cle for _l, cle, _f in ETATS}


def calculer(cle: str, racine: Path, du: date, au: date, contexte: dict) -> RapportGestion:
    return next(f for _l, c, f in ETATS if c == cle)(Path(racine), du, au, contexte)


# textes affichés (traduits par l'interface) : vérifiés par les tests
TEXTES = [
    "Gestion", "Pertes et démarque", "Contrôle de la caisse", "Petite caisse et dépenses", "Main-d'œuvre", "Promotions",
    "Retours fournisseurs", "Bons de commande", "Rapport détaillé", "Aucune donnée pour la période",
    # cartes
    "Valeur des pertes", "Déclarations", "Lignes d'articles", "Part des ventes nettes", "Espèces attendues",
    "Écart cumulé", "Jours comptés", "Jours non comptés", "Écarts de plus de 5 $", "Dépenses (taxes comprises)",
    "Taxes à récupérer", "Dépenses", "Solde de la petite caisse", "Heures pointées", "Heures planifiées",
    "Coût estimé", "Ventes par heure pointée", "Articles en promotion", "Baisse moyenne", "Montant des retours",
    "Retours", "Fournisseurs", "Montant commandé", "Reçus", "En attente",
    # graphiques
    "Écart de caisse (compté − attendu)", "Écart", "Promotions en cours par jour", "Promotions en cours",
    "Pertes par motif", "Comptages de la période", "Écart de 5 $ ou moins", "Écart de plus de 5 $", "Non compté",
    "Dépenses hors taxes par compte", "Heures pointées par employé", "Promotions par état", "Retours par fournisseur",
    "Commandes par fournisseur", "Sans compte", "Autre",
    # colonnes
    "N°", "Motif", "Article", "Catégorie", "Quantité", "Coût unitaire", "Valeur", "Point de vente",
    "Espèces vendues", "Remboursements", "Argent remis", "Fond du matin", "Attendu", "Compté", "À déposer",
    "Compté par", "Fournisseur", "Description", "Compte", "Payée par", "Hors taxes", "TPS", "TVQ", "Total", "État",
    "Ventes nettes", "Prix normal", "Prix promotionnel", "Baisse", "Du", "Au", "Facture d'origine", "Lignes",
    "Montant", "Facture", "Date",
    # notes
    "Calculez d'abord les statistiques de la période (espèces lues dans Clover).",
    "Coût estimé = heures pointées × taux moyen × (1 + charges sociales), réglages [paie] de la configuration.",
]
