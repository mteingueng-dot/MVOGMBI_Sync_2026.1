"""Statistiques de vente Clover (page « 11. Rapports », onglet « Statistiques Clover ») — demande du propriétaire du
2026-10-27 : toutes les déclinaisons (jour, semaine, heure, employé, client, mode de paiement, carte, appareil,
article, catégorie, commande, rabais, remboursements).

Lecture seule de Clover, par blocs de jours (une vente est datée de son premier paiement réussi, comme la
facturation) : paiements (avec mode de paiement et transaction de carte), commandes de ces paiements (articles,
rabais, client, employé, appareil) lues par paquets, remboursements. Chaque jour terminé est gardé dans
donnees/cache_clover/AAAA-MM-JJ.json : une période déjà lue s'affiche ensuite sans attendre Clover ; la journée en
cours est toujours relue. Montants nets des articles calculés comme les factures
(`api_clover.lignes_commande`). Les 4 derniers chiffres des cartes ne sont pas repris.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from .api_clover import _cents, _rabais, est_payee, lignes_commande, moment_paiement
from .periodes import en_millisecondes

ZERO = Decimal(0)
EXPANSION = ("lineItems,lineItems.discounts,lineItems.modifications,lineItems.taxRates,discounts,payments,customers,"
             "employee")
JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
SAISIES = {"EMV_CONTACTLESS": "Sans contact", "EMV_CONTACT": "Puce", "SWIPED": "Carte glissée",
           "KEYED": "Saisie manuelle", "MSR_CONTACTLESS": "Sans contact (bande)", "SCANNED": "Lue (code)"}
CARTES = {"MC": "Mastercard", "VISA": "Visa", "AMEX": "American Express", "INTERAC": "Interac (débit)",
          "DISCOVER": "Discover", "JCB": "JCB", "UNIONPAY": "UnionPay"}
VUES = ["Résumé", "Par jour", "Par jour de la semaine", "Par heure", "Par employé", "Par mode de paiement",
        "Par type de carte", "Par mode de saisie de la carte", "Par appareil", "Par client", "Par article",
        "Par catégorie", "Commandes", "Paiements", "Rabais", "Remboursements"]


# --------------------------------------------------------------------------------------------- lecture
@dataclass
class DonneesClover:
    commandes: list[dict] = field(default_factory=list)
    paiements: list[dict] = field(default_factory=list)
    remboursements: list[dict] = field(default_factory=list)
    employes: dict[str, str] = field(default_factory=dict)
    clients: dict[str, str] = field(default_factory=dict)
    appareils: dict[str, str] = field(default_factory=dict)
    categories: dict[str, str] = field(default_factory=dict)
    fuseau: str = "America/Toronto"


def _sans_carte(paiements: list[dict]) -> list[dict]:
    """Seuls le type de carte et le mode de saisie sont gardés (jamais les chiffres de la carte)."""
    for p in paiements:
        carte = p.get("cardTransaction") or {}
        p["cardTransaction"] = {"cardType": carte.get("cardType"), "entryType": carte.get("entryType")}
    return paiements


def lire_bloc(client, debut: date, fin: date) -> dict[date, dict]:
    """Paiements, commandes et remboursements de plusieurs jours en une fois (lecture rapide par paquets de
    `ClientClover.commandes`), rangés par jour : paiement et remboursement par leur date, commande par son premier
    paiement réussi (comme la facturation)."""
    fuseau = ZoneInfo(client.config.fuseau_horaire)
    t0, t1 = en_millisecondes(debut, fin, client.config.fuseau_horaire)
    filtre = {"filter": [f"createdTime>={t0}", f"createdTime<{t1}"]}
    paiements = _sans_carte(list(client._pages("payments", {**filtre, "expand": "tender,cardTransaction"})))
    commandes = list(client.commandes(debut, fin, EXPANSION, paiements=paiements))
    remboursements = list(client._pages("refunds", filtre))
    jours = {debut + timedelta(days=i): {"commandes": [], "paiements": [], "remboursements": []}
             for i in range((fin - debut).days + 1)}

    def jour_de(ms: int) -> date:
        return datetime.fromtimestamp(ms / 1000, fuseau).date()

    for p in paiements:
        jours.get(jour_de(p["createdTime"]), {"paiements": []})["paiements"].append(p)
    for c in commandes:
        jours.get(jour_de(moment_paiement(c)), {"commandes": []})["commandes"].append(c)
    for r in remboursements:
        jours.get(jour_de(r["createdTime"]), {"remboursements": []})["remboursements"].append(r)
    return jours


def lire(client, debut: date, fin: date, cache: Path | None = None, progression=None) -> DonneesClover:
    """Données de la période : jours terminés déjà lus pris dans le cache, les autres lus dans Clover par blocs
    de jours consécutifs (au plus 31) ; aujourd'hui est toujours relu (journée en cours) et jamais gardé."""
    d = DonneesClover(fuseau=client.config.fuseau_horaire)
    aujourdhui = date.today()
    jours = [debut + timedelta(days=i) for i in range((fin - debut).days + 1)]
    par_jour: dict[date, dict] = {}
    a_lire = []
    for jour in jours:
        fichier = cache / f"{jour.isoformat()}.json" if cache else None
        if fichier and jour < aujourdhui and fichier.exists():
            par_jour[jour] = json.loads(fichier.read_text(encoding="utf-8"))
        else:
            a_lire.append(jour)
    blocs: list[list[date]] = []
    for jour in a_lire:  # suites de jours consécutifs, 31 jours au plus
        if blocs and jour == blocs[-1][-1] + timedelta(days=1) and len(blocs[-1]) < 31:
            blocs[-1].append(jour)
        else:
            blocs.append([jour])
    lus = 0
    for bloc in blocs:
        if progression:
            progression(lus + 1, len(a_lire), bloc[0], bloc[-1])
        for jour, donnees in lire_bloc(client, bloc[0], bloc[-1]).items():
            par_jour[jour] = donnees
            if cache and jour < aujourdhui:  # jour terminé : gardé
                cache.mkdir(parents=True, exist_ok=True)
                (cache / f"{jour.isoformat()}.json").write_text(json.dumps(donnees, ensure_ascii=False),
                                                                 encoding="utf-8")
        lus += len(bloc)
    for jour in jours:
        donnees = par_jour.get(jour, {})
        d.commandes += donnees.get("commandes", [])
        d.paiements += donnees.get("paiements", [])
        d.remboursements += donnees.get("remboursements", [])
    d.employes = {e["id"]: e.get("name") or e.get("nickname") or e["id"] for e in client._pages("employees", {})}
    d.clients = {c["id"]: " ".join(x for x in (c.get("firstName"), c.get("lastName")) if x).strip() or c["id"]
                 for c in client._pages("customers", {})}
    d.appareils = {a["id"]: f"{a.get('productName') or a.get('model') or 'Appareil'} ({a.get('serial') or a['id'][:8]})"
                   for a in client._pages("devices", {})}
    d.categories = client.categories_par_article()
    return d


# --------------------------------------------------------------------------------------------- calcul
@dataclass
class Commande:
    """Une commande payée, prête pour les regroupements."""
    id: str
    moment: datetime
    numero: str
    employe: str
    client: str
    appareil: str
    lignes: list
    nettes: Decimal
    taxes: Decimal
    encaisse: Decimal
    pourboires: Decimal
    modes: str


def _cumul():
    return {"commandes": 0, "nettes": ZERO, "taxes": ZERO, "encaisse": ZERO, "pourboires": ZERO}


def preparer(d: DonneesClover) -> list[Commande]:
    fuseau = ZoneInfo(d.fuseau)
    paiements_par_commande = defaultdict(list)
    for p in d.paiements:
        if p.get("result") == "SUCCESS":
            paiements_par_commande[(p.get("order") or {}).get("id")].append(p)
    resultat = []
    for o in d.commandes:
        if not est_payee(o):
            continue
        lignes = lignes_commande(o, d.categories)
        paiements = paiements_par_commande.get(o["id"], [])
        clients = [d.clients.get(c["id"], c["id"]) for c in (o.get("customers") or {}).get("elements") or []]
        employe = (o.get("employee") or {})
        resultat.append(Commande(
            id=o["id"], moment=datetime.fromtimestamp(moment_paiement(o) / 1000, fuseau),
            numero=str(o.get("title") or o["id"]),
            employe=employe.get("name") or d.employes.get(employe.get("id"), "Sans employé"),
            client=", ".join(clients) or "Sans client",
            appareil=d.appareils.get((o.get("device") or {}).get("id"), "Appareil inconnu"),
            lignes=lignes, nettes=sum((l.ventes_nettes for l in lignes), ZERO),
            taxes=sum((_cents(p.get("taxAmount")) for p in paiements), ZERO),
            encaisse=sum((_cents(p.get("amount")) for p in paiements), ZERO),
            pourboires=sum((_cents(p.get("tipAmount")) for p in paiements), ZERO),
            modes=", ".join(sorted({(p.get("tender") or {}).get("label", "?") for p in paiements}))))
    return sorted(resultat, key=lambda c: c.moment)


def _pourcent(partie: Decimal, total: Decimal) -> Decimal:
    return (partie * 100 / total).quantize(Decimal("0.1")) if total else ZERO


def _moyenne(montant: Decimal, nombre: int) -> Decimal:
    return (montant / nombre).quantize(Decimal("0.01")) if nombre else ZERO


def _regrouper(commandes: list[Commande], cle) -> dict:
    groupes = defaultdict(_cumul)
    for c in commandes:
        g = groupes[cle(c)]
        g["commandes"] += 1
        for champ in ("nettes", "taxes", "encaisse", "pourboires"):
            g[champ] += getattr(c, champ)
    return groupes


def statistiques(d: DonneesClover) -> dict[str, tuple[list[str], list[list]]]:
    """Toutes les vues : nom -> (en-têtes, lignes)."""
    commandes = preparer(d)
    total = sum((c.nettes for c in commandes), ZERO)
    vues: dict[str, tuple[list[str], list[list]]] = {}
    paiements = [p for p in d.paiements if p.get("result") == "SUCCESS"]
    fuseau = ZoneInfo(d.fuseau)

    # ---- par jour, jour de semaine, heure, employé, appareil, client
    def vue_groupes(nom, entete, cle, ordre=None, extra=None):
        groupes = _regrouper(commandes, cle)
        cles = sorted(groupes, key=ordre) if ordre else sorted(groupes, key=lambda k: -groupes[k]["nettes"])
        lignes = []
        for k in cles:
            g = groupes[k]
            lignes.append([*(k if isinstance(k, tuple) else (k,)), g["commandes"], g["nettes"],
                           _moyenne(g["nettes"], g["commandes"]), g["taxes"], g["encaisse"], g["pourboires"],
                           _pourcent(g["nettes"], total)] + (extra(k) if extra else []))
        vues[nom] = ([*entete, "Commandes", "Ventes nettes", "Panier moyen", "Taxes", "Encaissé", "Pourboires",
                      "% des ventes"] + (["Rabais", "Remboursements"] if extra else []), lignes)

    vue_groupes("Par jour", ["Date", "Jour"], lambda c: (c.moment.date().isoformat(), JOURS[c.moment.weekday()]),
                ordre=lambda k: k)
    vue_groupes("Par jour de la semaine", ["Jour"], lambda c: JOURS[c.moment.weekday()],
                ordre=lambda k: JOURS.index(k))
    vue_groupes("Par heure", ["Heure"], lambda c: f"{c.moment.hour:02d} h", ordre=lambda k: k)
    rabais_employe, remb_employe = defaultdict(Decimal), defaultdict(Decimal)
    for c in commandes:
        rabais_employe[c.employe] += sum((l.rabais for l in c.lignes), ZERO)
        remb_employe[c.employe] += sum((l.remboursements for l in c.lignes), ZERO)
    vue_groupes("Par employé", ["Employé"], lambda c: c.employe,
                extra=lambda k: [rabais_employe[k], remb_employe[k]])
    vue_groupes("Par appareil", ["Appareil"], lambda c: c.appareil)
    visites = defaultdict(list)
    for c in commandes:
        visites[c.client].append(c.moment.date().isoformat())
    groupes = _regrouper(commandes, lambda c: c.client)
    vues["Par client"] = (["Client", "Commandes", "Ventes nettes", "Panier moyen", "% des ventes", "Première visite",
                           "Dernière visite"],
                          [[k, g["commandes"], g["nettes"], _moyenne(g["nettes"], g["commandes"]),
                            _pourcent(g["nettes"], total), min(visites[k]), max(visites[k])]
                           for k, g in sorted(groupes.items(), key=lambda x: (x[0] == "Sans client", -x[1]["nettes"]))])

    # ---- paiements : mode, carte, saisie
    montant_paye = sum((_cents(p.get("amount")) for p in paiements), ZERO)

    def vue_paiements(nom, entete, cle):
        groupes = defaultdict(lambda: [0, ZERO, ZERO])
        for p in paiements:
            g = groupes[cle(p)]
            g[0] += 1
            g[1] += _cents(p.get("amount"))
            g[2] += _cents(p.get("tipAmount"))
        vues[nom] = ([entete, "Paiements", "Montant", "Pourboires", "Moyenne", "% du montant"],
                     [[k, g[0], g[1], g[2], _moyenne(g[1], g[0]), _pourcent(g[1], montant_paye)]
                      for k, g in sorted(groupes.items(), key=lambda x: -x[1][1])])

    vue_paiements("Par mode de paiement", "Mode de paiement", lambda p: (p.get("tender") or {}).get("label", "?"))
    vue_paiements("Par type de carte", "Carte", lambda p: CARTES.get(
        (p.get("cardTransaction") or {}).get("cardType"), (p.get("cardTransaction") or {}).get("cardType") or
        "Sans carte (" + (p.get("tender") or {}).get("label", "?") + ")"))
    vue_paiements("Par mode de saisie de la carte", "Saisie", lambda p: SAISIES.get(
        (p.get("cardTransaction") or {}).get("entryType"), (p.get("cardTransaction") or {}).get("entryType") or
        "Sans carte"))

    # ---- articles et catégories
    articles = defaultdict(lambda: {"cat": "", "qte": ZERO, "brut": ZERO, "rabais": ZERO, "remb": ZERO, "cmd": set()})
    for c in commandes:
        for l in c.lignes:
            a = articles[l.nom]
            a["cat"] = l.categorie
            a["qte"] += l.quantite_nette
            a["brut"] += l.ventes_brutes
            a["rabais"] += l.rabais
            a["remb"] += l.remboursements
            a["cmd"].add(c.id)
    vues["Par article"] = (["Article", "Catégorie", "Quantité nette", "Ventes brutes", "Rabais", "Remboursements",
                            "Ventes nettes", "Commandes", "% des ventes"],
                           [[k, a["cat"], a["qte"], a["brut"], a["rabais"], a["remb"], a["brut"] + a["rabais"] + a["remb"],
                             len(a["cmd"]), _pourcent(a["brut"] + a["rabais"] + a["remb"], total)]
                            for k, a in sorted(articles.items(), key=lambda x: -(x[1]["brut"] + x[1]["rabais"]
                                                                                 + x[1]["remb"]))])
    categories = defaultdict(lambda: {"qte": ZERO, "nettes": ZERO, "articles": set()})
    for k, a in articles.items():
        g = categories[a["cat"]]
        g["qte"] += a["qte"]
        g["nettes"] += a["brut"] + a["rabais"] + a["remb"]
        g["articles"].add(k)
    vues["Par catégorie"] = (["Catégorie", "Quantité nette", "Ventes nettes", "Articles différents", "% des ventes"],
                             [[k, g["qte"], g["nettes"], len(g["articles"]), _pourcent(g["nettes"], total)]
                              for k, g in sorted(categories.items(), key=lambda x: -x[1]["nettes"])])

    # ---- détail : commandes, paiements, rabais, remboursements
    vues["Commandes"] = (["Date et heure", "N°", "Employé", "Client", "Articles", "Ventes nettes", "Taxes", "Encaissé",
                          "Pourboires", "Mode(s) de paiement", "Appareil"],
                         [[f"{c.moment:%Y-%m-%d %H:%M}", c.numero, c.employe, c.client, len(c.lignes), c.nettes,
                           c.taxes, c.encaisse, c.pourboires, c.modes, c.appareil] for c in reversed(commandes)])
    numeros = {c.id: c.numero for c in commandes}
    vues["Paiements"] = (["Date et heure", "Commande", "Mode de paiement", "Carte", "Saisie", "Employé", "Montant",
                          "Taxes", "Pourboire", "Remise en argent"],
                         [[f"{datetime.fromtimestamp(p['createdTime'] / 1000, fuseau):%Y-%m-%d %H:%M}",
                           numeros.get((p.get("order") or {}).get("id"), ""), (p.get("tender") or {}).get("label", "?"),
                           CARTES.get((p.get("cardTransaction") or {}).get("cardType"),
                                      (p.get("cardTransaction") or {}).get("cardType") or ""),
                           SAISIES.get((p.get("cardTransaction") or {}).get("entryType"),
                                       (p.get("cardTransaction") or {}).get("entryType") or ""),
                           d.employes.get((p.get("employee") or {}).get("id"), ""), _cents(p.get("amount")),
                           _cents(p.get("taxAmount")), _cents(p.get("tipAmount")), _cents(p.get("cashbackAmount"))]
                          for p in sorted(paiements, key=lambda p: -p.get("createdTime", 0))])
    rabais = defaultdict(lambda: [0, ZERO])
    for o in d.commandes:
        if not est_payee(o):
            continue
        for l in (o.get("lineItems") or {}).get("elements") or []:
            quantite = Decimal(l["unitQty"]) / 1000 if l.get("unitQty") else Decimal(1)
            base = _cents(l.get("price")) * quantite
            for r in (l.get("discounts") or {}).get("elements") or []:
                g = rabais[r.get("name") or "Rabais d'article"]
                g[0] += 1
                g[1] += _rabais([r], base)
        base = sum((l.ventes_brutes for l in lignes_commande(o, d.categories)), ZERO)
        for r in (o.get("discounts") or {}).get("elements") or []:
            g = rabais[(r.get("name") or "Rabais de commande") + " (commande)"]
            g[0] += 1
            g[1] += _rabais([r], base)
    vues["Rabais"] = (["Rabais", "Utilisations", "Montant"],
                      [[k, g[0], g[1].quantize(Decimal("0.01"))] for k, g in sorted(rabais.items(), key=lambda x: x[1][1])])
    vues["Remboursements"] = (["Date et heure", "Commande", "Employé", "Montant", "Taxes"],
                              [[f"{datetime.fromtimestamp(r['createdTime'] / 1000, fuseau):%Y-%m-%d %H:%M}",
                                str((r.get("orderRef") or {}).get("title") or (r.get("orderRef") or {}).get("id", "")),
                                d.employes.get((r.get("employee") or (r.get("orderRef") or {}).get("employee") or {})
                                               .get("id"), ""), -_cents(r.get("amount")), -_cents(r.get("taxAmount"))]
                               for r in sorted(d.remboursements, key=lambda r: -r.get("createdTime", 0))])

    # ---- résumé
    quantite = sum((l.quantite_nette for c in commandes for l in c.lignes), ZERO)
    rabais_total = sum((l.rabais for c in commandes for l in c.lignes), ZERO)
    remb_total = sum((l.remboursements for c in commandes for l in c.lignes), ZERO)
    jours = {c.moment.date() for c in commandes}
    vues["Résumé"] = (["Indicateur", "Valeur"], [
        ["Commandes payées", len(commandes)],
        ["Ventes brutes (articles)", sum((l.ventes_brutes for c in commandes for l in c.lignes), ZERO)],
        ["Ventes nettes (articles)", total],
        ["Taxes encaissées", sum((c.taxes for c in commandes), ZERO)],
        ["Montant encaissé (paiements)", montant_paye],
        ["Pourboires", sum((_cents(p.get("tipAmount")) for p in paiements), ZERO)],
        ["Panier moyen", _moyenne(total, len(commandes))],
        ["Ventes nettes par jour d'ouverture", _moyenne(total, len(jours))],
        ["Jours avec des ventes", len(jours)],
        ["Quantité nette d'articles", f"{quantite.normalize():f}"],
        ["Articles différents vendus", len(articles)],
        ["Rabais", rabais_total],
        ["Remboursements (articles)", remb_total],
        ["Remboursements (nombre)", len(d.remboursements)],
        ["Clients identifiés", len({c.client for c in commandes if c.client != "Sans client"})],
        ["Commandes avec un client identifié", sum(1 for c in commandes if c.client != "Sans client")],
        ["Employés ayant vendu", len({c.employe for c in commandes})],
        ["Paiements", len(paiements)],
    ])
    return {nom: vues[nom] for nom in VUES}


# --------------------------------------------------------------------------------------------- périodes (filtre)
PERIODES = ["Aujourd'hui", "Hier", "Cette semaine", "Semaine dernière", "Ce mois-ci", "Mois dernier",
            "30 derniers jours", "Cette année"]


def _mois_precedent(jour: date) -> date:
    premier = jour.replace(day=1) - timedelta(days=1)
    return premier.replace(day=1)


def periode(nom: str, aujourdhui: date | None = None) -> tuple[date, date]:
    """Bornes d'une période du filtre (comme le filtre de date de Clover)."""
    a = aujourdhui or date.today()
    lundi = a - timedelta(days=a.weekday())
    if nom == "Hier":
        return a - timedelta(days=1), a - timedelta(days=1)
    if nom == "Cette semaine":
        return lundi, a
    if nom == "Semaine dernière":
        return lundi - timedelta(days=7), lundi - timedelta(days=1)
    if nom == "Ce mois-ci":
        return a.replace(day=1), a
    if nom == "Mois dernier":
        debut = _mois_precedent(a)
        return debut, a.replace(day=1) - timedelta(days=1)
    if nom == "30 derniers jours":
        return a - timedelta(days=29), a
    if nom == "Cette année":
        return a.replace(month=1, day=1), a
    return a, a


def comparaison(du: date, au: date, nom: str = "") -> tuple[date, date, str]:
    """Période de comparaison et son libellé : un jour -> le même jour la semaine dernière (« mardi dernier ») ;
    semaine -> semaine d'avant ; mois -> mois d'avant ; année -> année d'avant ; sinon la période précédente."""
    if du == au:
        return du - timedelta(days=7), au - timedelta(days=7), f"{JOURS[du.weekday()]} dernier"
    if nom in ("Cette semaine", "Semaine dernière"):
        return du - timedelta(days=7), au - timedelta(days=7), "la semaine dernière"
    if nom in ("Ce mois-ci", "Mois dernier"):
        debut = _mois_precedent(du)
        fin_mois = du - timedelta(days=1)
        return debut, min(debut + (au - du), fin_mois), "le mois dernier"
    if nom == "Cette année":
        return du.replace(year=du.year - 1), au.replace(year=au.year - 1), "l'an dernier"
    duree = au - du
    return du - duree - timedelta(days=1), du - timedelta(days=1), "la période précédente"


def series(d: DonneesClover, du: date, au: date) -> tuple[list[str], list[Decimal]]:
    """Ventes nettes par heure (un seul jour) ou par jour (plusieurs jours), pour le graphique principal."""
    commandes = preparer(d)
    if du == au:
        valeurs = [ZERO] * 24
        for c in commandes:
            valeurs[c.moment.hour] += c.nettes
        return [f"{h:02d}h" for h in range(24)], valeurs
    jours = [du + timedelta(days=i) for i in range((au - du).days + 1)]
    index = {j: i for i, j in enumerate(jours)}
    valeurs = [ZERO] * len(jours)
    for c in commandes:
        i = index.get(c.moment.date())
        if i is not None:
            valeurs[i] += c.nettes
    return [f"{j.day:02d}/{j.month:02d}" for j in jours], valeurs


def montants_par_moyen(d: DonneesClover) -> list[tuple[str, Decimal]]:
    """Montant perçu : Carte / Espèces / Autre (comme Clover)."""
    groupes = {"Carte": ZERO, "Espèces": ZERO, "Autre": ZERO}
    for p in d.paiements:
        if p.get("result") != "SUCCESS":
            continue
        libelle = ((p.get("tender") or {}).get("label") or "").lower()
        cle = "Carte" if "carte" in libelle or "card" in libelle else ("Espèces" if "esp" in libelle
                                                                         or "cash" in libelle else "Autre")
        groupes[cle] += _cents(p.get("amount"))
    return list(groupes.items())
