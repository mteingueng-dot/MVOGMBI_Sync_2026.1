"""Comptabilité (demande du propriétaire du 2026-10-29, rubrique Comptabilité) — lecture seule de Sage.

- Âge des comptes : factures fournisseurs (tventr + tventrdt) et clients (tcustr + tcustrdt) ouvertes ; solde =
  somme des mouvements de la facture ; échéance = date + jours nets ; tranches À échoir, 1-30, 31-60, 61-90, plus
  de 90 jours de retard.
- Déclaration TPS/TVQ : mouvements de la période (tjentact + tjourent, sans écritures corrigées nType 32/33/64/65)
  des comptes de taxes nommés dans Sage : « perçue » (ventes, au crédit), « payée » (achats, CTI / RTI, au débit),
  « Régularisations » et « Retenues … sur avantages » ; les comptes « à remettre » (versements) sont exclus. Net à
  remettre = perçue + régularisations + retenues − payée. Contrôle : taxes encaissées par Clover sur la période.
- Prévision de trésorerie (4 semaines) : solde du compte de dépôt dans Sage ; entrées = prévision des ventes
  (previsions.prevoir_ventes) × rapport encaissé / ventes nettes des 8 dernières semaines (taxes comprises) ;
  sorties = factures fournisseurs ouvertes selon leur échéance (retards : 1re semaine) et paies (moyenne des paies
  passées au compte de dépôt les 12 dernières semaines, écritures du module Paie).
- Clôture du mois : contrôles (ventes facturées chaque jour, factures de vente encaissées, relevé bancaire chargé,
  factures et paiements fournisseurs en attente, feuilles de temps approuvées, paies dans Sage, taxes) et état des
  résultats (produits 4xxx, coût des marchandises vendues 50xx, autres charges 51xx-59xx) comparé au mois
  précédent et au même mois l'an dernier.
"""

from __future__ import annotations

import calendar
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

CENT = Decimal("0.01")
TRANCHES = ("À échoir", "1 à 30 jours", "31 à 60 jours", "61 à 90 jours", "Plus de 90 jours")
CORRIGEES = "(32, 33, 64, 65)"
OK, A_FAIRE, INFO = "✔ Fait", "● À faire", "ℹ Information"


def _d(v) -> Decimal:
    return Decimal(str(v or 0)).quantize(CENT)


def _jour(v) -> date:
    return v.date() if hasattr(v, "date") else v


def tranche(retard: int) -> str:
    if retard <= 0:
        return TRANCHES[0]
    if retard <= 30:
        return TRANCHES[1]
    if retard <= 60:
        return TRANCHES[2]
    if retard <= 90:
        return TRANCHES[3]
    return TRANCHES[4]


# --------------------------------------------------------------------------------------------- âge des comptes
@dataclass
class FactureOuverte:
    tiers: str
    numero: str
    date: date
    echeance: date
    solde: Decimal
    retard: int

    @property
    def tranche(self) -> str:
        return tranche(self.retard)


def factures_ouvertes(base, cote: str, aujourdhui: date) -> list[FactureOuverte]:
    """`cote` : « fournisseurs » ou « clients »."""
    from .articles_sage import reparer_texte

    if cote == "fournisseurs":
        sql = ("SELECT TRIM(v.sName) tiers, TRIM(t.sSource) n, t.dtDate d, t.nNetDay j, SUM(x.dAmount) s FROM tventr t "
               "JOIN tventrdt x ON x.lVenTrId = t.lId JOIN tvendor v ON v.lId = t.lVenId WHERE t.nTranType = 0 "
               "AND x.bReversed = 0 GROUP BY t.lId, v.sName, t.sSource, t.dtDate, t.nNetDay")
    else:
        sql = ("SELECT TRIM(c.sName) tiers, TRIM(t.sSource) n, t.dtDate d, t.nNetDay j, SUM(x.dAmount) s FROM tcustr t "
               "JOIN tcustrdt x ON x.lCusTrId = t.lId JOIN tcustomr c ON c.lId = t.lCusId WHERE t.nTranType = 0 "
               "AND x.bReversed = 0 GROUP BY t.lId, c.sName, t.sSource, t.dtDate, t.nNetDay")
    resultat = []
    for l in base.requete(sql):
        solde = _d(l["s"])
        if solde <= 0:
            continue
        jour = _jour(l["d"])
        echeance = jour + timedelta(days=int(l["j"] or 0))
        resultat.append(FactureOuverte(reparer_texte(l["tiers"] or ""), l["n"] or "", jour, echeance, solde,
                                       (aujourdhui - echeance).days))
    return sorted(resultat, key=lambda f: (-f.retard, f.tiers.casefold()))


def age_par_tiers(factures: list[FactureOuverte]) -> list[list]:
    """Une ligne par tiers : total puis montant de chaque tranche ; la plus grosse somme en retard en haut."""
    tiers: dict[str, dict] = defaultdict(lambda: {t: Decimal(0) for t in TRANCHES} | {"n": 0})
    for f in factures:
        tiers[f.tiers][f.tranche] += f.solde
        tiers[f.tiers]["n"] += 1
    lignes = [[nom, v["n"], sum((v[t] for t in TRANCHES), Decimal(0))] + [v[t] for t in TRANCHES]
              for nom, v in tiers.items()]
    lignes.sort(key=lambda l: (-(l[2] - l[3]), l[0].casefold()))
    if lignes:
        lignes.append(["Total", sum(l[1] for l in lignes)] + [sum((l[i] for l in lignes), Decimal(0))
                                                               for i in range(2, 3 + len(TRANCHES))])
    return lignes


ENTETES_AGE = ["Tiers", "Factures", "Montant dû"] + list(TRANCHES)


# --------------------------------------------------------------------------------------------- taxes
def mouvements_comptes(base, comptes: list[int], du: date, au: date) -> dict[int, Decimal]:
    """Somme des mouvements de chaque compte sur la période, dans le sens normal du compte (constat du 2026-10-29 :
    Sage compte en positif le débit d'un actif ou d'une charge et le crédit d'un passif ou d'un produit)."""
    if not comptes:
        return {}
    lignes = base.requete(
        f"SELECT a.lAcctId c, ROUND(SUM(a.dAmount), 2) s FROM tjentact a JOIN tjourent e ON e.lId = a.lJEntId "
        f"WHERE a.lAcctId IN ({', '.join(str(int(c)) for c in comptes)}) AND e.nType NOT IN {CORRIGEES} "
        "AND e.dtJourDate >= %s AND e.dtJourDate <= %s GROUP BY a.lAcctId", (du.isoformat(), au.isoformat()))
    return {l["c"]: _d(l["s"]) for l in lignes}


def nature_taxe(nom: str) -> tuple[str, str] | None:
    """(taxe, nature) d'un compte de taxe d'après son nom dans Sage ; None si à exclure (« à remettre »)."""
    texte = nom.casefold()
    taxe = "TPS/TVH" if ("tps" in texte or "tvh" in texte) else ("TVQ" if "tvq" in texte else "")
    if not taxe or "remettre" in texte:
        return None
    if "perçue" in texte or "percue" in texte:
        return taxe, "Perçue sur les ventes"
    if "payée" in texte or "payee" in texte:
        return taxe, "Payée sur les achats (CTI / RTI)"
    if "régularisation" in texte or "regularisation" in texte:
        return taxe, "Régularisations"
    if "retenue" in texte:
        return taxe, "Retenues sur avantages"
    return None


def declaration_taxes(base, du: date, au: date) -> list[list]:
    """[taxe, nature, compte, montant] avec le signe de la déclaration (perçue +, payée −), puis le net par taxe."""
    comptes = {r["lId"]: r["sName"] or "" for r in base.requete("SELECT lId, sName FROM taccount")}
    retenus = {c: nature_taxe(n) for c, n in comptes.items() if nature_taxe(n)}
    soldes = mouvements_comptes(base, list(retenus), du, au)
    lignes, nets = [], defaultdict(Decimal)
    for compte, (taxe, nature) in sorted(retenus.items()):
        montant = soldes.get(compte, Decimal(0))  # passif : perçue positive (à remettre), payée négative (à déduire)
        lignes.append([taxe, nature, f"{str(compte)[:4]} {comptes[compte]}", montant])
        nets[taxe] += montant
    for taxe in ("TPS/TVH", "TVQ"):
        if taxe in nets:
            lignes.append([taxe, "Net à remettre (ou à recevoir si négatif)", "", nets[taxe]])
    return lignes


ENTETES_TAXES = ["Taxe", "Nature", "Compte Sage", "Montant"]


def taxes_clover(racine: Path, du: date, au: date) -> Decimal:
    """Taxes encaissées par Clover sur la période (paiements réussis, cache des jours)."""
    from .__main__ import charger_config
    from .api_clover import ClientClover
    from .statistiques_clover import lire, preparer

    donnees = lire(ClientClover(charger_config(Path(racine) / "config.toml")), du, au,
                   Path(racine) / "donnees" / "cache_clover")
    return sum((c.taxes for c in preparer(donnees)), Decimal(0)).quantize(CENT)


# --------------------------------------------------------------------------------------------- trésorerie
def paies_passees(base, compte: int, du: date, au: date) -> Decimal:
    """Total des paies sorties du compte de dépôt (écritures du module Paie, nModule 3)."""
    lignes = base.requete(
        f"SELECT ROUND(SUM(a.dAmount), 2) s FROM tjentact a JOIN tjourent e ON e.lId = a.lJEntId WHERE "
        f"a.lAcctId = %s AND e.nModule = 3 AND e.nType NOT IN {CORRIGEES} AND e.dtJourDate >= %s "
        "AND e.dtJourDate <= %s", (compte, du.isoformat(), au.isoformat()))
    return -_d(lignes[0]["s"]) if lignes else Decimal(0)


def prevoir_tresorerie(solde: Decimal, entrees: list[Decimal], factures: list[FactureOuverte],
                       paie_semaine: Decimal, aujourdhui: date) -> list[list]:
    """4 semaines : [semaine, solde de départ, entrées, factures fournisseurs, paies, solde de fin]."""
    lignes, courant = [], solde
    for i, entree in enumerate(entrees):
        debut = aujourdhui + timedelta(days=7 * i)
        fin = debut + timedelta(days=6)
        a_payer = sum((f.solde for f in factures if (f.echeance <= fin if i == 0 else debut <= f.echeance <= fin)),
                      Decimal(0))
        sortie = courant + entree - a_payer - paie_semaine
        lignes.append([f"{debut:%Y-%m-%d} au {fin:%Y-%m-%d}", courant, entree, a_payer, paie_semaine, sortie])
        courant = sortie
    return lignes


ENTETES_TRESORERIE = ["Semaine", "Trésorerie au début", "Entrées prévues (ventes)", "Factures fournisseurs",
                      "Paies", "Trésorerie à la fin"]


def calculer_tresorerie(racine: Path, config_toml: dict, aujourdhui: date | None = None) -> tuple[list[list], dict]:
    from .__main__ import charger_config, lire_sage
    from .api_clover import ClientClover
    from .encaissements import numero_compte_sage
    from .previsions import prevoir_ventes, ventes_par_jour
    from .rapprochement import solde_sage
    from .statistiques_clover import lire, preparer

    aujourdhui = aujourdhui or date.today()
    hier = aujourdhui - timedelta(days=1)
    donnees = lire(ClientClover(charger_config(Path(racine) / "config.toml")), hier - timedelta(days=55), hier,
                   Path(racine) / "donnees" / "cache_clover")
    commandes = preparer(donnees)
    nettes = sum((c.nettes for c in commandes), Decimal(0))
    rapport = (sum((c.encaisse for c in commandes), Decimal(0)) / nettes) if nettes else Decimal(1)
    prevision = prevoir_ventes(ventes_par_jour(donnees), aujourdhui, 28)
    entrees = [(sum((l[2] for l in prevision[7 * i:7 * i + 7]), Decimal(0)) * rapport).quantize(CENT)
               for i in range(4)]
    compte = numero_compte_sage(str(config_toml.get("encaissements", {}).get("compte_depot", "1055")))

    def lecture(base):
        return (solde_sage(base, aujourdhui, compte), factures_ouvertes(base, "fournisseurs", aujourdhui),
                paies_passees(base, compte, aujourdhui - timedelta(days=84), hier))

    solde, factures, paies = lire_sage(config_toml, lecture,
                                       config_toml.get("sage_import", {}).get("fichier_entreprise"))
    paie_semaine = (paies / 12).quantize(CENT)
    lignes = prevoir_tresorerie(solde, entrees, factures, paie_semaine, aujourdhui)
    return lignes, {"rapport": rapport, "paie_semaine": paie_semaine, "en_retard":
                    sum((f.solde for f in factures if f.retard > 0), Decimal(0))}


# --------------------------------------------------------------------------------------------- clôture du mois
def bornes_mois(annee: int, mois: int) -> tuple[date, date]:
    return date(annee, mois, 1), date(annee, mois, calendar.monthrange(annee, mois)[1])


def mois_precedent(annee: int, mois: int) -> tuple[int, int]:
    return (annee - 1, 12) if mois == 1 else (annee, mois - 1)


def etat_resultats(base, annee: int, mois: int) -> list[list]:
    """Produits, CMV, autres charges et résultat du mois, du mois précédent et du même mois l'an dernier."""
    periodes = [(annee, mois), mois_precedent(annee, mois), (annee - 1, mois)]
    comptes = {r["lId"]: r["sName"] or "" for r in base.requete("SELECT lId, sName FROM taccount")}
    groupes = [("Produits (ventes)", lambda c: c.startswith("4"), 1),
               ("Coût des marchandises vendues", lambda c: c.startswith("50"), 1),
               ("Autres charges", lambda c: c.startswith("5") and not c.startswith("50"), 1)]
    valeurs = []
    for a, m in periodes:
        du, au = bornes_mois(a, m)
        soldes = mouvements_comptes(base, [c for c in comptes if str(c)[0] in "45"], du, au)
        valeurs.append([sum((s for c, s in soldes.items() if test(str(c))), Decimal(0)) * signe
                        for _nom, test, signe in groupes])
    lignes = [[nom] + [v[i] for v in valeurs] for i, (nom, _t, _s) in enumerate(groupes)]
    marge = ["Marge brute"] + [v[0] - v[1] for v in valeurs]
    resultat = ["Résultat (bénéfice ou perte)"] + [v[0] - v[1] - v[2] for v in valeurs]
    taux = ["Marge brute (%)"] + [((v[0] - v[1]) / v[0] * 100).quantize(Decimal("0.1")) if v[0] else Decimal(0)
                                  for v in valeurs]
    return lignes[:2] + [marge, taux] + lignes[2:] + [resultat]


def entetes_resultats(annee: int, mois: int) -> list[str]:
    a, m = mois_precedent(annee, mois)
    return ["Poste", f"{annee}-{mois:02d}", f"{a}-{m:02d}", f"{annee - 1}-{mois:02d}"]


def controles_cloture(racine: Path, base, annee: int, mois: int, aujourdhui: date | None = None) -> list[list]:
    """[contrôle, état, détail] ; état : Fait, À faire ou Information."""
    from .automatique import jours_couverts_sage
    from .facture import CLIENT

    aujourdhui = aujourdhui or date.today()
    du, au = bornes_mois(annee, mois)
    fin_controle = min(au, aujourdhui - timedelta(days=1))
    lignes = []
    # 1. ventes facturées chaque jour
    factures = base.requete("SELECT TRIM(t.sSource) s, t.dtDate d FROM tcustr t JOIN tcustomr c ON c.lId = t.lCusId "
                            "WHERE c.sName = %s AND t.nTranType = 0", (CLIENT,))
    couverts, _ = jours_couverts_sage(factures)
    manquants = [du + timedelta(days=i) for i in range((fin_controle - du).days + 1)
                 if du + timedelta(days=i) not in couverts]
    lignes.append(["Ventes facturées dans Sage (chaque jour)", OK if not manquants else A_FAIRE,
                   "tous les jours du mois" if not manquants else
                   f"{len(manquants)} jour(s) sans facture : " + ", ".join(f"{j:%d/%m}" for j in manquants[:10])])
    # 2. factures de vente encaissées
    ouvertes = [f for f in factures_ouvertes(base, "clients", aujourdhui) if du <= f.date <= au]
    lignes.append(["Factures de vente du mois encaissées", OK if not ouvertes else A_FAIRE,
                   "aucun solde dû" if not ouvertes else
                   f"{len(ouvertes)} facture(s), {sum((f.solde for f in ouvertes), Decimal(0))} $ dus"])
    # 3. relevé bancaire chargé
    try:
        from .rapprochement import RegistreReleves

        couvre = any(r.debut and r.fin and r.debut <= du.isoformat() and r.fin >= au.isoformat()
                     for r in RegistreReleves(racine).lire())
        lignes.append(["Relevé bancaire du mois chargé (Comptabilité > Rapprochement)", OK if couvre else A_FAIRE,
                       "relevé chargé : vérifiez l'écart à 0,00 $" if couvre else "relevé du mois absent"])
    except Exception as exc:
        lignes.append(["Relevé bancaire du mois chargé", A_FAIRE, f"non vérifié : {exc}"])
    # 4. factures fournisseurs en attente
    try:
        from .fournisseurs import IMPORTEE, Registre

        attente = [f for f in Registre(racine).factures if f.etat != IMPORTEE
                   and (f.date_facture or "")[:7] <= f"{annee}-{mois:02d}"]
        lignes.append(["Factures fournisseurs importées", OK if not attente else A_FAIRE,
                       "aucune en attente" if not attente else f"{len(attente)} facture(s) en attente "
                                                                 "(Fournisseur > Factures fournisseurs)"])
    except Exception as exc:
        lignes.append(["Factures fournisseurs importées", A_FAIRE, f"non vérifié : {exc}"])
    # 5. feuilles de temps approuvées
    try:
        from . import paie_temps as pt
        from .fenetre_pointage import reference

        registre = pt.Registre(racine)
        debut = pt.debut_periode(du, reference(racine))
        attente = []
        while debut <= au:
            if debut + timedelta(days=pt.JOURS_PERIODE - 1) < aujourdhui:  # période terminée
                attente += [f"{f.employe.nom} ({debut:%d/%m})" for f in pt.feuilles(registre, debut)
                            if f.total > 0 and f.etat == pt.A_APPROUVER]
            debut += timedelta(days=pt.JOURS_PERIODE)
        lignes.append(["Feuilles de temps approuvées (Paie > Feuilles de temps)", OK if not attente else A_FAIRE,
                       "toutes approuvées" if not attente else f"{len(attente)} à approuver : " + ", ".join(attente[:6])])
    except Exception as exc:
        lignes.append(["Feuilles de temps approuvées", A_FAIRE, f"non vérifié : {exc}"])
    # 6. paies dans Sage
    paies = base.requete(f"SELECT COUNT(DISTINCT e.lId) n FROM tjourent e WHERE e.nModule = 3 AND e.nType NOT IN "
                         f"{CORRIGEES} AND e.dtJourDate >= %s AND e.dtJourDate <= %s", (du.isoformat(), au.isoformat()))
    n = int(paies[0]["n"] or 0) if paies else 0
    lignes.append(["Paies du mois dans Sage", OK if n else A_FAIRE, f"{n} écriture(s) de paie"])
    # 7. retenues à la source
    try:
        from .retenues import etat

        _lignes, info = etat(base, annee, mois)
        remises = info.get("a_remettre", {})
        lignes.append(["Retenues à la source du mois (Paie > Retenues à la source)", INFO,
                       (" ; ".join(f"{o} : {m} $" for o, m in remises.items()) + f" — à remettre au plus tard le "
                        f"{info['echeance']:%Y-%m-%d}") if remises else "aucune paie dans le mois"])
    except Exception as exc:
        lignes.append(["Retenues à la source du mois", A_FAIRE, f"non vérifié : {exc}"])
    # 8. taxes
    nets = [l for l in declaration_taxes(base, du, au) if l[1].startswith("Net")]
    lignes.append(["Taxes du mois calculées (Comptabilité > Déclaration TPS/TVQ)", INFO,
                   " ; ".join(f"{l[0]} : {l[3]} $" for l in nets) or "aucun mouvement de taxe"])
    return lignes


ENTETES_CLOTURE = ["Contrôle", "État", "Détail"]
