"""Analyses décisionnelles des statistiques Clover (analyses_clover.py) sur des ventes fictives."""
from datetime import date, datetime, timedelta
from decimal import Decimal as D
from zoneinfo import ZoneInfo

from mvogmbi_sync import analyses_clover as an
from mvogmbi_sync.statistiques_clover import DonneesClover

FUSEAU = ZoneInfo("America/Toronto")


def _commande(ident, jour: date, articles: list[tuple[str, str, int]], client=None, employe="E1", heure=11,
              rabais=None, nom_rabais="Rabais"):
    moment = int(datetime(jour.year, jour.month, jour.day, heure, 0, tzinfo=FUSEAU).timestamp() * 1000)
    lignes = []
    for nom, item, prix in articles:
        l = {"name": nom, "price": prix, "item": {"id": item}}
        if rabais:
            l["discounts"] = {"elements": [{"name": nom_rabais, "percentage": rabais}]}
        lignes.append(l)
    return {"id": ident, "title": ident, "createdTime": moment, "employee": {"id": employe}, "device": {"id": "D1"},
            "customers": {"elements": [{"id": client}] if client else []},
            "payments": {"elements": [{"result": "SUCCESS", "createdTime": moment}]},
            "lineItems": {"elements": lignes}}


def _donnees(commandes):
    return DonneesClover(commandes=commandes, employes={"E1": "Alice", "E2": "Bruno"},
                         clients={"C1": "Client Un", "C2": "Client Deux", "C3": "Client Trois"},
                         appareils={"D1": "Station"}, categories={"P": "Fruits", "M": "Fruits", "R": "Riz", "S": "Riz"})


DU, AU = date(2026, 9, 7), date(2026, 10, 4)          # 4 semaines, du lundi au dimanche
DU2, AU2 = date(2026, 8, 10), date(2026, 9, 6)


def _periode():
    """Chaque jour : plantain + manioc ensemble (paire), riz seul ; le samedi vend 3 fois plus ; une commande à
    rabais de 100 % ; Client Un revient chaque semaine."""
    cmds, n = [], 0
    for i in range((AU - DU).days + 1):
        j = DU + timedelta(days=i)
        fois = 3 if j.weekday() == 5 else 1
        for k in range(fois):
            n += 1
            cmds.append(_commande(f"A{n}", j, [("Plantain", "P", 500), ("Manioc", "M", 300)],
                                  client="C1" if j.weekday() == 0 and k == 0 else None))
            n += 1
            cmds.append(_commande(f"B{n}", j, [("Riz", "R", 1000)], employe="E2", heure=15))
    cmds.append(_commande("X1", DU + timedelta(days=3), [("Sel", "S", 2000)], rabais=100))
    cmds.append(_commande("DIR1", DU + timedelta(days=5), [("Sel", "S", 3000)], rabais=100, nom_rabais="Direction"))
    cmds.append(_commande("C2a", DU + timedelta(days=10), [("Riz", "R", 1000)], client="C2"))
    return _donnees(cmds)


def _avant():
    cmds = [_commande(f"V{i}", DU2 + timedelta(days=i), [("Plantain", "P", 500)],
                      client="C1" if i == 0 else "C3" if i == 1 else None) for i in range(28)]
    return _donnees(cmds)


def _toutes():
    d, a = _periode(), _avant()
    return {cle: an.calculer(cle, d, a, {}, DU, AU, DU2, AU2) for _l, cle, *_r in an.ANALYSES}


def test_chaque_analyse_est_rangee_dans_une_section_existante():
    from mvogmbi_sync.page_rapports import NAVIGATION

    sections = {nom: [c for _l, c in etats] for _i, nom, etats in NAVIGATION}
    for libelle, cle, _f, section, _apres in an.ANALYSES:
        assert cle in sections[section], libelle
    assert "Analyse BI" not in sections  # aucune section nouvelle : tout va dans l'existant
    toutes = [c for v in sections.values() for c in v]
    assert all(toutes.count(cle) == 1 for cle in an.CLES)  # chaque analyse une seule fois


def test_toutes_les_analyses_rendent_un_rapport_complet():
    for cle, r in _toutes().items():
        assert r.cartes and r.entetes and r.note, cle
        assert r.lignes or cle == "a_prix", cle  # aucun changement de prix dans ces ventes fictives
        assert all(len(l) == len(r.entetes) for l in r.lignes), cle
        assert all(len(v) == len(r.etiquettes) for _n, v in r.series), cle


def test_tendance_indice_du_samedi_et_semaines():
    r = _toutes()["a_tendance"]
    indices = dict(r.repartition)
    assert indices["samedi"] > D(200) and indices["lundi"] < D(100)
    assert len(r.lignes) == 4 and r.lignes[0][7] is None  # 1re semaine : pas de variation


def test_variation_effet_volume_et_panier():
    r = _toutes()["a_variation"]
    cartes = {t: v for t, _g, v in r.cartes}
    assert cartes["Écart"] == cartes["Ventes nettes"] - cartes["Période de comparaison"]
    assert cartes["Effet nombre de commandes"] + cartes["Effet panier moyen"] == cartes["Écart"]


def test_paires_et_lift():
    r = _toutes()["a_associations"]
    paire = next(l for l in r.lignes if {l[1], l[2]} == {"Manioc", "Plantain"})
    assert paire[3] == 36 and paire[5] == D("100.0") and paire[7] > 1  # toujours achetés ensemble


def test_anomalies_rabais_de_100_pourcent_une_seule_fois():
    r = _toutes()["a_anomalies"]
    types = [l[0] for l in r.lignes if l[2] == "X1"]
    assert types == ["Rabais de 50 % ou plus"]  # pas aussi « Commande à 0 $ »


def test_rfm_et_fidelite():
    t = _toutes()
    rfm = {l[0]: l for l in t["a_rfm"].lignes}
    assert rfm["Client Un"][3] > rfm["Client Deux"][3]  # fréquence : 4 visites contre 1
    fid = {l[0]: l[1] for l in t["a_fidelite"].lignes}
    assert fid == {"Client Un": "Retenu", "Client Deux": "Nouveau", "Client Trois": "Perdu"}
    cartes = {titre: v for titre, _g, v in t["a_fidelite"].cartes}
    assert cartes["Taux de rétention"] == D("50.0")


def test_scores_egaux_meme_note():
    s = an._scores({"a": 1, "b": 1, "c": 1, "d": 5})
    assert s["a"] == s["b"] == s["c"] == 1 and s["d"] > 1


def test_matrice_quadrants_avec_couts():
    d, a = _periode(), _avant()
    couts = {"P": ("A1", D("1.00")), "M": ("A2", D("2.50")), "R": ("A3", D("4.00")), "S": ("A4", D("1"))}
    r = an.calculer("a_matrice", d, a, couts, DU, AU, DU2, AU2)
    quadrants = {l[0]: l[11] for l in r.lignes}
    assert quadrants["Plantain"] == "Vedette"       # populaire, 4 $ de bénéfice par unité
    assert quadrants["Manioc"] == "Locomotive"      # populaire, 0,50 $ seulement
    assert r.lignes[0][5] == "A"


def test_concentration_gini():
    assert an._gini([1, 1, 1, 1]) == 0
    assert an._gini([0, 0, 0, 10]) == 0  # un seul élément vendu : rien à comparer
    assert 0.6 < an._gini([1, 1, 1, 97]) < 0.8
    r = _toutes()["a_concentration"]
    assert {l[0] for l in r.lignes} >= {"Articles", "Catégories", "Employés"}


def test_libelles_traduits():
    from mvogmbi_sync import langues

    for libelle, *_r in an.ANALYSES:
        assert libelle in langues.EN, libelle
    for r in _toutes().values():
        for titre, _g, _v in r.cartes:
            assert titre in langues.EN, titre
        for entete in r.entetes:
            assert entete in langues.EN or entete.startswith("Mois +"), entete  # « Mois +n % » déjà traduit
        assert r.titre_evolution in langues.EN and r.titre_repartition in langues.EN


def test_changement_de_prix_et_elasticite():
    """Riz à 10 $ puis à 12 $ dès la 3e semaine : moins vendu ensuite (2 par jour, puis 1)."""
    cmds, n = [], 0
    for i in range((AU - DU).days + 1):
        j = DU + timedelta(days=i)
        prix, fois = (1000, 2) if i < 14 else (1200, 1)
        for _k in range(fois):
            n += 1
            cmds.append(_commande(f"R{n}", j, [("Riz", "R", prix)]))
    r = an.calculer("a_prix", _donnees(cmds), _avant(), {}, DU, AU, DU2, AU2)
    ligne = next(l for l in r.lignes if l[0] == "Riz")
    assert ligne[2] == str(DU + timedelta(days=14)) and ligne[3] == D("10.00") and ligne[4] == D("12.00")
    assert ligne[8] == D("-50.0") and ligne[9] == D("-2.50") and ligne[14] == "Très sensible au prix"


def test_cohortes_et_synthese():
    t = _toutes()
    coh = {l[0]: l for l in t["a_cohortes"].lignes}
    assert "2026-08" in coh and coh["2026-08"][1] == 2  # Client Un et Client Trois : premier achat en août
    syn = t["a_synthese"]
    assert syn.lignes and all(not l[2].startswith(("Jour atypique :", "Popularité :")) for l in syn.lignes)
    assert {c[0] for c in syn.cartes} >= {"Ventes nettes", "Tendance par semaine"}


def test_graphiques_de_plus_sans_vide():
    """« Ne laisse pas trop de vides » : chaque analyse a des graphiques de plus, jamais vides, titres traduits."""
    from mvogmbi_sync import langues

    for cle, r in _toutes().items():
        if cle != "a_prix":  # aucun changement de prix dans ces ventes fictives
            assert r.graphiques, cle
        for g in r.graphiques:
            assert g["elements"] or any(v for _n, vs in g["series"] for v in vs), (cle, g["titre"])
            assert g["titre"] in langues.EN, g["titre"]


def test_constats_en_couleur_et_decisions():
    """Direction : constats marqués (à agir, à surveiller, bon), cartes à feu, décisions priorisées."""
    t = _toutes()
    niveaux = {an.niveau_constat(l)[0] for r in t.values() for l in r.note.splitlines()}
    assert {"alerte", "bon", "info"} <= niveaux
    assert an.etat_carte("Variation", D("-5")) == "alerte" and an.etat_carte("Variation", D("2")) == "bon"
    assert an.etat_carte("Ventes nettes", D("10")) is None
    syn = t["a_synthese"]
    assert syn.entetes == ["Priorité", "Décision à prendre", "Concerné", "Détail", "Où regarder"]
    priorites = [l[0] for l in syn.lignes if l[0]]
    assert priorites == sorted(priorites) and priorites[0].startswith("1")
    assert any(l[1] == "Contrôler les rabais de 50 % et plus avec les employés concernés" for l in syn.lignes)
    assert an.niveau_constat(syn.note.splitlines()[1])[0] == "alerte"  # la décision la plus urgente en premier


def test_elements_concernes_par_les_decisions():
    """« Je veux avoir la liste des articles concernés dans les décisions » : chaque décision est suivie de ses
    éléments (articles, clients, employés, commandes) ; une commande ouvre sa facture Clover."""
    from mvogmbi_sync.web.pages_statistiques import _tableau_detaille

    syn = _toutes()["a_synthese"]
    assert len(syn.ids_commandes) == len(syn.lignes)
    rang = next(i for i, l in enumerate(syn.lignes) if l[1].startswith("Contrôler les rabais"))
    assert syn.lignes[rang][2].endswith("élément(s)")
    suivante = syn.lignes[rang + 1]
    assert suivante[0] == "" and suivante[2] == "X1" and syn.ids_commandes[rang + 1] == "X1"
    assert "/facture-clover?id=X1" in _tableau_detaille(syn)
    decision = next(d for d in syn.decisions if d[1].startswith("Contrôler les rabais"))
    assert decision[5][0][0] == "X1" and "X1" in an.resume_concernes(decision[5])
    assert all(len(d) == 6 for d in syn.decisions)


def test_facture_clover_et_lien_des_anomalies():
    """Anomalie : le n° de commande ouvre la vraie facture Clover (lien web, double-clic Windows)."""
    from mvogmbi_sync import facture_clover as fc
    from mvogmbi_sync.web.pages_statistiques import _tableau_detaille

    r = _toutes()["a_anomalies"]
    assert len(r.ids_commandes) == len(r.lignes)
    rang = next(i for i, l in enumerate(r.lignes) if l[2] == "X1")
    assert r.ids_commandes[rang] == "X1"
    html = _tableau_detaille(r)
    assert "/facture-clover?id=X1" in html and "target='_blank'" in html
    commande = _commande("X1", DU, [("Sel", "S", 2000)], rabais=100)
    commande["payments"]["elements"][0].update({"amount": 0, "taxAmount": 0, "tipAmount": 0,
                                                "tender": {"label": "Espèces"}})
    f = fc.detail(commande, categories={"S": "Riz"})
    assert f.numero == "X1" and f.lignes[0][:2] == ["Sel", "Riz"] and f.lignes[0][5] == D("-20.00")
    assert dict(f.totaux)["Ventes nettes"] == 0 and f.note.startswith("Rabais de 50 %")
    assert f.paiements[0][1] == "Espèces" and f.paiements[0][7] == "Réussi"


def test_numero_de_commande_partout():
    """Commandes, Transactions, Remboursements : chaque n° de commande retrouve sa commande Clover (facture)."""
    from mvogmbi_sync import statistiques_clover as sc

    d = _periode()
    d.remboursements = [{"createdTime": d.commandes[0]["createdTime"], "amount": -100,
                         "orderRef": {"id": "ANCIENNE", "title": "999"}}]
    vues = sc.statistiques(d)
    for nom, (cd, cn) in sc.COLONNES_COMMANDE.items():
        for ligne in vues[nom][1]:
            assert sc.id_commande(d, ligne[cd], ligne[cn]), (nom, ligne)
    assert sc.id_commande(d, "2026-09-07", "999") == "ANCIENNE"   # commande d'une autre période
    assert sc.id_commande(d, "", "inconnue") == ""


def test_decisions_du_courriel_du_matin(tmp_path):
    """Résumé du matin : décisions de la synthèse sur 28 jours contre les 28 d'avant, sans relire Clover."""
    from mvogmbi_sync import resume_matin as rm

    d = _periode()
    d.commandes += _avant().commandes
    hier = AU
    partie = rm.tranche(d, DU + timedelta(days=7), AU)
    assert partie.commandes and all(c["id"][0] in "ABXC" for c in partie.commandes)
    decisions = rm.decisions_du_mois(tmp_path, {}, d, hier)
    assert decisions and decisions[0][0].startswith("1")
    r = rm.ResumeMatin(hier, decisions=decisions)
    assert "Décisions proposées" in rm.html(r) and any("1 — Haute" in l for l in rm.texte(r))


def test_rabais_direction_et_administrateurs_a_part():
    """« Mets les rabais Direction et compte administrateur dans un autre état » : ni anomalie, ni taux de rabais
    des employés, ni décision ; listés dans leur état avec le lien vers la facture."""
    d = _periode()
    d.commandes.append(_commande("ADM1", DU + timedelta(days=6), [("Riz", "R", 1000)], employe="E3", rabais=50))
    d.employes["E3"] = "Patronne"
    d.administrateurs = {"Patronne"}
    r = an.calculer("a_rabais_direction", d, _avant(), {}, DU, AU, DU2, AU2)
    motifs = {l[2]: l[0] for l in r.lignes}
    assert motifs == {"DIR1": "Rabais Direction", "ADM1": "Compte administrateur"}
    assert r.ids_commandes == [{"ADM1": "ADM1", "DIR1": "DIR1"}[l[2]] for l in r.lignes]
    cartes = {c[0]: c[2] for c in r.cartes}
    assert cartes["Rabais Direction"] == D("30.00") and cartes["Rabais des administrateurs"] == D("5.00")
    ano = an.calculer("a_anomalies", d, _avant(), {}, DU, AU, DU2, AU2)
    assert {l[2] for l in ano.lignes if l[0] == "Rabais de 50 % ou plus"} == {"X1"}
    emp = an.calculer("a_employes", d, _avant(), {}, DU, AU, DU2, AU2)
    patronne = next(l for l in emp.lignes if l[0] == "Patronne")
    assert patronne[7] == 0 and patronne[15] == D("5.00")
    syn = an.calculer("a_synthese", d, _avant(), {}, DU, AU, DU2, AU2)
    assert not any("Patronne" in str(l) for l in syn.lignes if l[1] == "Encadrer les rabais accordés")
