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
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from .api_clover import SANS_CATEGORIE, _cents, _rabais, est_payee, lignes_commande, moment_paiement
from .periodes import en_millisecondes

ZERO = Decimal(0)
SEUIL_CUMP_DOUTEUX = 5  # CUMP Sage plus de 5 fois le prix de vente moyen : valeur de stock erronée dans Sage
EXPANSION = ("lineItems,lineItems.discounts,lineItems.modifications,lineItems.taxRates,discounts,payments,customers,"
             "employee")
JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
SAISIES = {"EMV_CONTACTLESS": "Sans contact", "EMV_CONTACT": "Puce", "SWIPED": "Carte glissée",
           "KEYED": "Saisie manuelle", "MSR_CONTACTLESS": "Sans contact (bande)", "SCANNED": "Lue (code)"}
CARTES = {"MC": "Mastercard", "VISA": "Visa", "AMEX": "American Express", "INTERAC": "Interac (débit)",
          "DISCOVER": "Discover", "JCB": "JCB", "UNIONPAY": "UnionPay"}
VUES = ["Résumé", "Rapport des ventes", "Bénéfices", "Jour × heure", "Par jour", "Par jour de la semaine", "Par heure", "Par employé", "Par mode de paiement",
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
    prepare: list | None = field(default=None, repr=False, compare=False)  # commandes préparées (calculées une fois)


_MEMOIRE: dict[str, dict] = {}          # jours terminés déjà lus (fichier -> données), le temps de la session
_LIGNES: dict[tuple, list] = {}        # (commande, modification, filtre) -> lignes de vente calculées
_REFERENTIELS: dict[str, tuple] = {}    # marchand -> (moment, employés, clients, appareils, catégories)
DUREE_REFERENTIELS = 3600               # secondes


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
        if fichier and jour < aujourdhui and str(fichier) in _MEMOIRE:
            par_jour[jour] = _MEMOIRE[str(fichier)]
        elif fichier and jour < aujourdhui and fichier.exists():
            par_jour[jour] = _MEMOIRE[str(fichier)] = json.loads(fichier.read_text(encoding="utf-8"))
        else:
            a_lire.append(jour)
    blocs: list[list[date]] = []
    for jour in a_lire:  # suites de jours consécutifs, 31 jours au plus
        if blocs and jour == blocs[-1][-1] + timedelta(days=1) and len(blocs[-1]) < 31:
            blocs[-1].append(jour)
        else:
            blocs.append([jour])
    lus = 0
    # 3 blocs à la fois (une année : 4 min au lieu de 2 h avec l'ancienne lecture, puis quelques secondes)
    with ThreadPoolExecutor(max_workers=3) as groupe:
        for bloc, resultat in zip(blocs, groupe.map(lambda b: lire_bloc(type(client)(client.config), b[0], b[-1]), blocs)):
            for jour, donnees in resultat.items():
                par_jour[jour] = donnees
                if cache and jour < aujourdhui:  # jour terminé : gardé
                    _MEMOIRE[str(cache / f"{jour.isoformat()}.json")] = donnees
                    cache.mkdir(parents=True, exist_ok=True)
                    (cache / f"{jour.isoformat()}.json").write_text(json.dumps(donnees, ensure_ascii=False),
                                                                     encoding="utf-8")
            lus += len(bloc)
            if progression:
                progression(lus, len(a_lire), bloc[0], bloc[-1])
    for jour in jours:
        donnees = par_jour.get(jour, {})
        d.commandes += donnees.get("commandes", [])
        d.paiements += donnees.get("paiements", [])
        d.remboursements += donnees.get("remboursements", [])
    d.employes, d.clients, d.appareils, d.categories = referentiels(client, cache)
    return d


DUREE_REFERENTIELS_DISQUE = 6 * 3600  # noms gardés sur disque : 1,3 s de Clover évitées à chaque lecture


def referentiels(client, cache: Path | None = None) -> tuple:
    """Employés, clients, appareils et catégories d'articles de Clover, relus au plus une fois par heure (mémoire)
    et gardés 6 heures dans `cache`/referentiels.json (un nouvel employé apparaît au plus tard 6 heures après)."""
    import time

    cle = client.config.merchant_id
    deja = _REFERENTIELS.get(cle)
    if deja and time.time() - deja[0] < DUREE_REFERENTIELS:
        return deja[1:]
    fichier = Path(cache) / "referentiels.json" if cache else None
    if fichier is not None:
        try:
            garde = json.loads(fichier.read_text(encoding="utf-8"))
            if garde.get("marchand") == cle and time.time() - garde["moment"] < DUREE_REFERENTIELS_DISQUE:
                _REFERENTIELS[cle] = (time.time(), *garde["donnees"])
                return _REFERENTIELS[cle][1:]
        except (OSError, ValueError, KeyError):
            pass
    employes = {e["id"]: e.get("name") or e.get("nickname") or e["id"] for e in client._pages("employees", {})}
    clients = {c["id"]: " ".join(x for x in (c.get("firstName"), c.get("lastName")) if x).strip() or c["id"]
               for c in client._pages("customers", {})}
    appareils = {a["id"]: f"{a.get('productName') or a.get('model') or 'Appareil'} ({a.get('serial') or a['id'][:8]})"
                 for a in client._pages("devices", {})}
    _REFERENTIELS[cle] = (time.time(), employes, clients, appareils, client.categories_par_article())
    if fichier is not None:
        try:
            fichier.parent.mkdir(parents=True, exist_ok=True)
            fichier.write_text(json.dumps({"marchand": cle, "moment": time.time(),
                                           "donnees": list(_REFERENTIELS[cle][1:])}, ensure_ascii=False),
                               encoding="utf-8")
        except (OSError, TypeError):
            pass
    return _REFERENTIELS[cle][1:]


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
    """Commandes payées prêtes pour les regroupements (calculées une seule fois par jeu de données)."""
    if d.prepare is not None:
        return d.prepare
    fuseau = ZoneInfo(d.fuseau)
    paiements_par_commande = defaultdict(list)
    for p in d.paiements:
        if p.get("result") == "SUCCESS":
            paiements_par_commande[(p.get("order") or {}).get("id")].append(p)
    resultat = []
    for o in d.commandes:
        if not est_payee(o):
            continue
        cle = (o["id"], o.get("modifiedTime"), o.get("_filtre", ""))  # lignes calculées une fois par commande
        lignes = _LIGNES.get(cle)
        if lignes is None:
            lignes = _LIGNES[cle] = lignes_commande(o, d.categories)
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
    d.prepare = sorted(resultat, key=lambda c: c.moment)
    return d.prepare


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


def statistiques(d: DonneesClover, couts: dict | None = None) -> dict[str, tuple[list[str], list[list]]]:
    """Toutes les vues : nom -> (en-têtes, lignes). `couts` : ID Clover -> (n° Sage, CUMP Sage) pour les bénéfices
    (coût des ventes = quantité nette × CUMP ; marge calculée sur les seuls articles dont le coût est connu)."""
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

    # ---- articles et catégories (avec le coût d'achat Sage quand il est connu)
    couts = couts or {}
    articles = defaultdict(lambda: {"cat": "", "qte": ZERO, "brut": ZERO, "rabais": ZERO, "remb": ZERO, "cmd": set(),
                                    "id": "", "cump": None, "cout": None, "nettes_cout": ZERO})
    for c in commandes:
        for l in c.lignes:
            a = articles[l.nom]
            a["cat"] = l.categorie
            a["qte"] += l.quantite_nette
            a["brut"] += l.ventes_brutes
            a["rabais"] += l.rabais
            a["remb"] += l.remboursements
            a["cmd"].add(c.id)
            numero, cump = couts.get(l.id_article, ("", None))
            a["id"], a["cump"] = l.id_article, cump if cump is not None else a["cump"]
            a["qte_vendue"] = a.get("qte_vendue", ZERO) + l.quantite_vendue
    douteux = 0
    for a in articles.values():
        a["nettes"] = a["brut"] + a["rabais"] + a["remb"]
        prix_unitaire = a["brut"] / a["qte_vendue"] if a.get("qte_vendue") else ZERO
        if a["cump"] is not None and prix_unitaire and a["cump"] > SEUIL_CUMP_DOUTEUX * prix_unitaire:
            douteux += 1  # erreur de valeur de stock dans Sage : coût ignoré
            a["douteux"] = True
        elif a["cump"] is not None:
            a["cout"] = a["qte"] * a["cump"]
            a["nettes_cout"] = a["nettes"]
        if a["cout"] is not None:
            a["cout"] = a["cout"].quantize(Decimal("0.01"))
            a["benefice"] = (a["nettes_cout"] - a["cout"]).quantize(Decimal("0.01"))
            a["marge"] = _pourcent(a["benefice"], a["nettes_cout"])
        else:
            a["benefice"] = a["marge"] = None
    ordre = sorted(articles.items(), key=lambda x: -x[1]["nettes"])
    entetes = ["Article", "Catégorie", "Quantité nette", "Ventes brutes", "Rabais", "Remboursements", "Ventes nettes",
               "Commandes", "% des ventes"]
    if couts:
        entetes += ["CUMP Sage", "Coût des ventes", "Bénéfice", "Marge %"]
    vues["Par article"] = (entetes, [
        [k, a["cat"], a["qte"], a["brut"], a["rabais"], a["remb"], a["nettes"], len(a["cmd"]), _pourcent(a["nettes"], total)]
        + ([a["cump"], a["cout"], a["benefice"], a["marge"]] if couts else []) for k, a in ordre])
    categories = defaultdict(lambda: {"qte": ZERO, "nettes": ZERO, "articles": set(), "cout": ZERO, "benefice": ZERO,
                                      "nettes_cout": ZERO})
    for k, a in articles.items():
        g = categories[a["cat"]]
        g["qte"] += a["qte"]
        g["nettes"] += a["nettes"]
        g["articles"].add(k)
        if a["cout"] is not None:
            g["cout"] += a["cout"]
            g["benefice"] += a["benefice"]
            g["nettes_cout"] += a["nettes_cout"]
    vues["Par catégorie"] = (
        ["Catégorie", "Quantité nette", "Ventes nettes", "Articles différents", "% des ventes"]
        + (["Coût des ventes", "Bénéfice", "Marge %"] if couts else []),
        [[k, g["qte"], g["nettes"], len(g["articles"]), _pourcent(g["nettes"], total)]
         + ([g["cout"], g["benefice"], _pourcent(g["benefice"], g["nettes_cout"])] if couts else [])
         for k, g in sorted(categories.items(), key=lambda x: -x[1]["nettes"])])
    avec_cout = [(k, a) for k, a in articles.items() if a["cout"] is not None]
    vues["Bénéfices"] = (["Article", "Catégorie", "Quantité nette", "Ventes nettes", "CUMP Sage", "Coût des ventes",
                          "Bénéfice", "Marge %"],
                         [[k, a["cat"], a["qte"], a["nettes_cout"], a["cump"], a["cout"], a["benefice"], a["marge"]]
                          for k, a in sorted(avec_cout, key=lambda x: -x[1]["benefice"])])
    cout_total = sum((a["cout"] for _, a in avec_cout), ZERO)
    benefice_total = sum((a["benefice"] for _, a in avec_cout), ZERO)
    nettes_cout = sum((a["nettes_cout"] for _, a in avec_cout), ZERO)

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
    lignes_par_commande = {c.id: c.lignes for c in commandes}  # lignes déjà calculées
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
        base = sum((l.ventes_brutes for l in lignes_par_commande.get(o["id"], [])), ZERO)
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

    # ---- carte de chaleur : ventes nettes par jour de la semaine × heure
    grille = defaultdict(Decimal)
    for c in commandes:
        grille[(c.moment.weekday(), c.moment.hour)] += c.nettes
    heures = sorted({h for _, h in grille}) or list(range(9, 21))
    heures = list(range(min(heures), max(heures) + 1))
    vues["Jour × heure"] = (["Jour"] + [f"{h:02d} h" for h in heures] + ["Total"],
                            [[JOURS[j]] + [grille.get((j, h), ZERO) for h in heures]
                             + [sum((grille.get((j, h), ZERO) for h in heures), ZERO)] for j in range(7)])

    # ---- rapport des ventes (comme Clover) : par jour, ou par heure pour une seule journée
    un_jour = len({c.moment.date() for c in commandes}) <= 1
    rapport = defaultdict(lambda: [0, ZERO, ZERO, ZERO, ZERO, ZERO, ZERO, ZERO])
    for c in commandes:
        g = rapport[f"{c.moment.hour:02d} h" if un_jour else c.moment.date().isoformat()]
        g[0] += 1
        g[1] += sum((l.ventes_brutes for l in c.lignes), ZERO)
        g[2] += sum((l.rabais for l in c.lignes), ZERO)
        g[3] += sum((l.remboursements for l in c.lignes), ZERO)
        g[4] += c.nettes
        g[5] += c.taxes
        g[6] += c.pourboires
        g[7] += c.encaisse
    vues["Rapport des ventes"] = (
        ["Heure" if un_jour else "Date", "Jour", "Commandes", "Ventes brutes", "Rabais", "Remboursements",
         "Ventes nettes", "Taxes", "Pourboires", "Montant perçu"],
        [[k, "" if un_jour else JOURS[date.fromisoformat(k).weekday()], *g] for k, g in sorted(rapport.items())])

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
    ] + ([
        ["Coût des ventes (CUMP Sage)", cout_total],
        ["Bénéfice brut", benefice_total],
        ["Marge brute (%)", _pourcent(benefice_total, nettes_cout)],
        ["Ventes nettes sans coût Sage", total - nettes_cout],
        ["Articles au coût Sage douteux", douteux],
    ] if couts else []))
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


def kpis(vues: dict, moyens: list[tuple[str, Decimal]]) -> list[tuple[str, str, object]]:
    """Indicateurs de l'aperçu financier : (titre, genre « $ », « % », « n » ou « t », valeur)."""
    r = dict(vues["Résumé"][1])
    commandes, jours = r["Commandes payées"], r["Jours avec des ventes"] or 1
    brutes, nettes = r["Ventes brutes (articles)"], r["Ventes nettes (articles)"]
    quantite = Decimal(str(r["Quantité nette d'articles"]))
    paye = r["Montant encaissé (paiements)"]
    moyens = dict(moyens)

    def premier(nom: str, i_val: int = 2):
        lignes = vues[nom][1]
        return max(lignes, key=lambda l: l[i_val]) if lignes else None

    meilleur_jour = premier("Par jour")
    meilleur_jds = premier("Par jour de la semaine")
    meilleure_heure = premier("Par heure")
    article = vues["Par article"][1][0] if vues["Par article"][1] else None
    categorie = vues["Par catégorie"][1][0] if vues["Par catégorie"][1] else None
    employe = vues["Par employé"][1][0] if vues["Par employé"][1] else None
    liste = [
        ("Ventes brutes", "$", brutes), ("Ventes nettes", "$", nettes), ("Montant perçu", "$", paye),
        ("Taxes encaissées", "$", r["Taxes encaissées"]), ("Commandes", "n", commandes),
        ("Panier moyen", "$", r["Panier moyen"]), ("Ventes nettes par jour", "$", r["Ventes nettes par jour d'ouverture"]),
        ("Commandes par jour", "n", (Decimal(commandes) / jours).quantize(Decimal("0.1"))),
        ("Articles par commande", "n", (quantite / commandes).quantize(Decimal("0.1")) if commandes else ZERO),
        ("Prix moyen d'un article", "$", (nettes / quantite).quantize(Decimal("0.01")) if quantite else ZERO),
        ("Taux de rabais", "%", _pourcent(-r["Rabais"], brutes)),
        ("Taux de remboursement", "%", _pourcent(-r["Remboursements (articles)"], brutes)),
        ("Part payée par carte", "%", _pourcent(moyens.get("Carte", ZERO), paye)),
        ("Part payée en espèces", "%", _pourcent(moyens.get("Espèces", ZERO), paye)),
        ("Paiement moyen", "$", _moyenne(paye, r["Paiements"])),
        ("Commandes avec un client", "%", _pourcent(Decimal(r["Commandes avec un client identifié"]),
                                                   Decimal(commandes or 1))),
        ("Jours avec des ventes", "n", r["Jours avec des ventes"]),
        ("Articles différents vendus", "n", r["Articles différents vendus"]),
    ]
    if "Bénéfice brut" in r:
        liste[4:4] = [("Coût des ventes (Sage)", "$", r["Coût des ventes (CUMP Sage)"]),
                      ("Bénéfice brut", "$", r["Bénéfice brut"]), ("Marge brute", "%", r["Marge brute (%)"]),
                      ("Bénéfice par jour", "$", (r["Bénéfice brut"] / jours).quantize(Decimal("0.01")))]
    if meilleur_jour:
        montant_jour = f"{meilleur_jour[2]:,.2f} $".replace(",", " ").replace(".", ",")
        liste.append(("Meilleur jour", "t", f"{meilleur_jour[0]} ({montant_jour})"))
    if meilleur_jds:
        liste.append(("Jour de la semaine le plus fort", "t", meilleur_jds[0]))
    if meilleure_heure:
        liste.append(("Heure la plus forte", "t", meilleure_heure[0]))
    if article:
        liste.append(("Meilleur article", "t", article[0]))
    if categorie:
        liste.append(("Meilleure catégorie", "t", categorie[0]))
    if employe:
        liste.append(("Meilleur vendeur", "t", employe[0]))
    return liste


# --------------------------------------------------------------------------------------------- filtres globaux
FILTRES = ("Article", "Client", "Employé", "Catégorie")


def filtrer(d: DonneesClover, filtres: dict[str, str]) -> DonneesClover:
    """Données réduites aux filtres de la page Rapports : client, employé et mode de paiement gardent les commandes
    concernées (mode de paiement : commandes payées au moins en partie ainsi, seuls ces paiements sont gardés) ;
    article et catégorie ne gardent que leurs lignes (et les commandes qui en ont). Paiements et remboursements
    suivent les commandes gardées ; avec un filtre d'article ou de catégorie, un paiement ne compte que pour la part
    des lignes gardées dans sa commande."""
    filtres = {k: v.strip() for k, v in (filtres or {}).items() if v and v.strip()}
    if not filtres:
        return d
    article, client = filtres.get("Article", "").casefold(), filtres.get("Client", "").casefold()
    employe, categorie = filtres.get("Employé", "").casefold(), filtres.get("Catégorie", "").casefold()
    mode = filtres.get("Mode de paiement", "").casefold()
    gardees, parts = [], {}

    def mode_de(p: dict) -> str:
        return ((p.get("tender") or {}).get("label") or "?").casefold()

    commandes_du_mode = {(p.get("order") or {}).get("id") for p in d.paiements if mode_de(p) == mode} if mode else set()

    def valeur(lignes) -> Decimal:
        return sum((_cents(l.get("price")) * (Decimal(l["unitQty"]) / 1000 if l.get("unitQty") else 1)
                    for l in lignes), ZERO)

    for o in d.commandes:
        nom_employe = ((o.get("employee") or {}).get("name") or d.employes.get((o.get("employee") or {}).get("id"), ""))
        clients = [d.clients.get(c["id"], c["id"]) for c in (o.get("customers") or {}).get("elements") or []]
        if employe and nom_employe.casefold() != employe:
            continue
        if client and client not in {c.casefold() for c in clients}:
            continue
        if mode and o["id"] not in commandes_du_mode:
            continue
        if article or categorie:
            lignes = [l for l in (o.get("lineItems") or {}).get("elements") or []
                      if (not article or (l.get("name") or "").strip().casefold() == article)
                      and (not categorie or d.categories.get((l.get("item") or {}).get("id"), SANS_CATEGORIE)
                           .casefold() == categorie)]
            if not lignes:
                continue
            tout = valeur((o.get("lineItems") or {}).get("elements") or [])
            parts[o["id"]] = valeur(lignes) / tout if tout else Decimal(1)
            o = {**o, "lineItems": {"elements": lignes}, "discounts": {"elements": []},  # rabais de commande : non répartis
                 "_filtre": f"{article}|{categorie}"}
        gardees.append(o)
    ids = {o["id"] for o in gardees}

    def part(p: dict) -> dict:
        k = parts.get((p.get("order") or {}).get("id"))
        if k is None:
            return p
        return {**p, **{c: int(Decimal(int(p.get(c) or 0)) * k) for c in ("amount", "taxAmount", "tipAmount")}}

    return DonneesClover(commandes=gardees,
                         paiements=[part(p) for p in d.paiements if (p.get("order") or {}).get("id") in ids
                                    and (not mode or mode_de(p) == mode)],
                         remboursements=[r for r in d.remboursements if (r.get("orderRef") or {}).get("id") in ids],
                         employes=d.employes, clients=d.clients, appareils=d.appareils, categories=d.categories,
                         fuseau=d.fuseau)


# vues regroupées qui peuvent être détaillées jour par jour (demande du propriétaire du 2026-10-28 : la date compte)
VUES_PAR_JOUR = ("Par article", "Par catégorie", "Par employé", "Par client", "Par mode de paiement",
                 "Par type de carte", "Par mode de saisie de la carte", "Par appareil", "Bénéfices")


def detail_par_jour(d: DonneesClover, vue: str, couts: dict | None = None) -> tuple[list[str], list[list]]:
    """La vue `vue` calculée jour par jour (jour du premier paiement, comme la facturation) : une colonne Date en
    premier, le jour le plus récent en haut."""
    fuseau = ZoneInfo(d.fuseau)
    par_jour: dict[date, list[dict]] = defaultdict(list)
    for o in d.commandes:
        moment = moment_paiement(o)
        if moment is not None:
            par_jour[datetime.fromtimestamp(moment / 1000, fuseau).date()].append(o)
    paiements, remboursements = defaultdict(list), defaultdict(list)
    for p in d.paiements:
        paiements[(p.get("order") or {}).get("id")].append(p)
    for r in d.remboursements:
        remboursements[(r.get("orderRef") or {}).get("id")].append(r)
    entetes, lignes = None, []
    for jour in sorted(par_jour, reverse=True):
        commandes = par_jour[jour]
        sous = replace(d, commandes=commandes, prepare=None,
                       paiements=[p for o in commandes for p in paiements.get(o["id"], [])],
                       remboursements=[r for o in commandes for r in remboursements.get(o["id"], [])])
        e, l = statistiques(sous, couts)[vue]
        entetes = ["Date"] + list(e)
        lignes += [[jour.isoformat()] + list(x) for x in l]
    return entetes or ["Date"], lignes


def evolution_par_annee(par_annee: dict[int, DonneesClover], du: date, au: date) -> tuple[list[str], dict[int, list]]:
    """Ventes nettes par jour (jj/mm) de la période, une série par année (mêmes dates les années d'avant)."""
    jours = [du + timedelta(days=i) for i in range((au - du).days + 1)]
    etiquettes = [f"{j.day:02d}/{j.month:02d}" for j in jours]
    series = {}
    for annee, d in sorted(par_annee.items(), reverse=True):
        decalage = du.year - annee
        totaux: dict[date, Decimal] = defaultdict(Decimal)
        for c in preparer(d):
            totaux[c.moment.date()] += c.nettes
        valeurs = []
        for j in jours:
            try:
                meme = j.replace(year=j.year - decalage)
            except ValueError:  # 29 février
                meme = j.replace(year=j.year - decalage, day=28)
            valeurs.append(totaux.get(meme, ZERO) if meme < date.today() or decalage == 0 else None)
        if any(valeurs):
            series[annee] = valeurs
    return etiquettes, series


def resume_rapide(d: DonneesClover) -> dict[str, tuple[list[str], list[list]]]:
    """Seulement les chiffres des cartes (période de comparaison) : bien plus rapide que `statistiques`."""
    commandes = preparer(d)
    lignes = [l for c in commandes for l in c.lignes]
    nettes = sum((c.nettes for c in commandes), ZERO)
    paye = sum((_cents(p.get("amount")) for p in d.paiements if p.get("result") == "SUCCESS"), ZERO)
    return {"Résumé": (["Indicateur", "Valeur"], [
        ["Commandes payées", len(commandes)],
        ["Ventes brutes (articles)", sum((l.ventes_brutes for l in lignes), ZERO)],
        ["Ventes nettes (articles)", nettes],
        ["Taxes encaissées", sum((c.taxes for c in commandes), ZERO)],
        ["Montant encaissé (paiements)", paye],
        ["Panier moyen", _moyenne(nettes, len(commandes))],
        ["Rabais", sum((l.rabais for l in lignes), ZERO)],
        ["Remboursements (articles)", sum((l.remboursements for l in lignes), ZERO)],
    ])}
