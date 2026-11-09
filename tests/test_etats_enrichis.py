"""États de base des statistiques enrichis (cartes, constats, graphiques de plus), demande du propriétaire du
2026-11-09 : « développe tous les états »."""
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from mvogmbi_sync import analyses_clover as an
from mvogmbi_sync import etats_enrichis as ee
from mvogmbi_sync import langues
from mvogmbi_sync import statistiques_clover as sc
from mvogmbi_sync.statistiques_clover import DonneesClover

FUSEAU = ZoneInfo("America/Toronto")


def _commande(ident, jour, articles, client=None, employe="E1", heure=11, mode="Carte"):
    moment = int(datetime(jour.year, jour.month, jour.day, heure, 0, tzinfo=FUSEAU).timestamp() * 1000)
    lignes = [{"name": n, "price": p, "item": {"id": i}} for n, i, p in articles]
    total = sum(p for _n, _i, p in articles)
    return {"id": ident, "title": ident, "createdTime": moment, "employee": {"id": employe}, "device": {"id": "D1"},
            "customers": {"elements": [{"id": client}] if client else []},
            "payments": {"elements": [{"result": "SUCCESS", "createdTime": moment, "amount": total,
                                       "taxAmount": total * 15 // 100, "tipAmount": 0, "tender": {"label": mode}}]},
            "lineItems": {"elements": lignes}}


def _donnees(commandes):
    paiements = [{**p, "order": {"id": o["id"]}} for o in commandes for p in o["payments"]["elements"]]
    return DonneesClover(commandes=commandes, paiements=paiements, employes={"E1": "Alice", "E2": "Bruno"},
                         clients={"C1": "Client Un", "C2": "Client Deux"}, appareils={"D1": "Station"},
                         categories={"R": "Riz", "P": "Pain", "H": "Huile"})


def _periode(prefixe, debut, jours, facteur=1):
    cmds = []
    for k in range(jours):
        j = debut + timedelta(days=k)
        for n in range(3 + (j.weekday() == 5) * 4):  # samedi plus achalandé
            cmds.append(_commande(f"{prefixe}-{k}-{n}", j, [("Riz", "R", 1000 * facteur), ("Pain", "P", 300)]
                                  + ([("Huile", "H", 800)] if n % 2 else []),
                                  client="C1" if n == 0 else ("C2" if n == 1 and k % 2 else None),
                                  employe="E1" if n % 3 else "E2", heure=10 + n, mode="Espèces" if n == 2 else "Carte"))
    return _donnees(cmds)


def test_tous_les_etats_sont_enrichis_et_traduits():
    vus = set()
    ancien = an._t
    an._t = lambda texte, **v: (vus.add(texte), ancien(texte, **v))[1]
    try:
        d = _periode("EE-A", date(2026, 9, 1), 28, facteur=2)
        a = _periode("EE-B", date(2026, 8, 4), 28)
        vues, avant = sc.statistiques(d, {}), sc.statistiques(a, {})
        for nom in ee.ETATS:
            r = ee.enrichir(nom, vues, avant, {"du": date(2026, 9, 1), "au": date(2026, 9, 28)})
            if nom in ("Bénéfices", "Rabais", "Remboursements") and r is None:
                continue  # aucune donnée de ce genre dans le jeu d'essai
            assert r is not None, nom
            assert r.cartes and r.note and (r.graphiques or nom == "Remboursements"), nom
            vus.update(t for t, _g, _v in r.cartes)
            for g in r.graphiques:
                vus.add(g["titre"])
    finally:
        an._t = ancien
    manque = sorted(x for x in vus if x not in langues.EN)
    assert not manque, manque


def test_constats_et_sens_des_variations():
    d = _periode("EE-C", date(2026, 9, 1), 28, facteur=2)
    a = _periode("EE-D", date(2026, 8, 4), 28)
    vues, avant = sc.statistiques(d, {}), sc.statistiques(a, {})
    jour = ee.enrichir("Par jour de la semaine", vues, avant, {})
    assert dict((t, v) for t, _g, v in jour.cartes)["Jour le plus fort"] == "samedi"
    art = ee.enrichir("Par article", vues, avant, {})
    assert any("Plus forte hausse : Riz" in l for l in art.note.splitlines())
    assert any(l.startswith("✔") and "Total" in l for l in art.note.splitlines())  # ventes en hausse : bon
    cli = ee.enrichir("Par client", vues, avant, {})
    assert all(t != "Le premier" or v != "Sans client" for t, _g, v in cli.cartes)
    assert ee.enrichir("Liste d'articles", vues, avant, {}) is None
