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
            "payments": {"elements": [{"result": "SUCCESS", "createdTime": moment,
                                       "amount": sum(p for _n, _i, p in articles),
                                       "taxAmount": sum(p for _n, _i, p in articles) * 15 // 100,
                                       "tipAmount": 100 if employe == "E1" else 0,
                                       "tender": {"label": "Espèces" if employe == "E2" else "Carte"}}]},
            "lineItems": {"elements": lignes}}


def _donnees(commandes):
    paiements = [{**p, "order": {"id": o["id"]}} for o in commandes for p in o["payments"]["elements"]]
    return DonneesClover(commandes=commandes, paiements=paiements, employes={"E1": "Alice", "E2": "Bruno"},
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
    rembourse = _commande("RB1", DU + timedelta(days=2), [("Riz", "R", 1000)], employe="E2", heure=15)
    rembourse["lineItems"]["elements"][0]["refunded"] = True  # article remboursé
    cmds.append(rembourse)
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
        assert r.lignes or cle in ("a_prix", "a_marge", "a_baisse", "a_poids", "a_ruptures", "a_prix_format"), cle  # aucun changement de prix ; marge : sans coûts
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
    assert cartes["Effet du nombre de ventes"] + cartes["Effet du montant moyen par vente"] == cartes["Écart"]


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
    assert quadrants["Plantain"] == "Très vendu et rentable"       # populaire, 4 $ de bénéfice par unité
    assert quadrants["Manioc"] == "Très vendu, peu rentable"      # populaire, 0,50 $ seulement
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
    assert {c[0] for c in syn.cartes} >= {"Ventes nettes", "Hausse ou baisse par semaine"}


def test_graphiques_de_plus_sans_vide():
    """« Ne laisse pas trop de vides » : chaque analyse a des graphiques de plus, jamais vides, titres traduits."""
    from mvogmbi_sync import langues

    for cle, r in _toutes().items():
        if cle not in ("a_prix", "a_marge", "a_baisse", "a_seuil", "a_poids", "a_ruptures", "a_prix_format"):  # pas de changement de prix ni de baisse ; marge : sans coûts
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


COUTS = {"P": ("A1", D("1.00")), "M": ("A2", D("2.50")), "R": ("A3", D("4.00")), "S": ("A4", D("1"))}


def test_pont_de_marge():
    """Écart du bénéfice = effet prix + effet volume + effet mix + articles nouveaux ou arrêtés."""
    r = an.calculer("a_marge", _periode(), _avant(), COUTS, DU, AU, DU2, AU2)
    c = {t: v for t, _g, v in r.cartes}
    assert c["Écart du bénéfice"] == c["Bénéfice brut"] - c["Période de comparaison"]
    total = c["Effet des prix"] + c["Effet des quantités"] + c["Effet du choix des articles"] + c["Articles nouveaux ou arrêtés"]
    assert abs(total - c["Écart du bénéfice"]) <= D("0.03")
    plantain = next(l for l in r.lignes if l[0] == "Plantain")
    assert plantain[6] == D("1.00") and plantain[12] == D("80.0")  # 5 $ - 1 $ = 80 % de marge
    assert r.graphiques and all(len(l) == len(r.entetes) for l in r.lignes)


def test_portefeuille_et_achalandage():
    t = {cle: an.calculer(cle, _periode(), _avant(), COUTS, DU, AU, DU2, AU2)
         for cle in ("a_portefeuille", "a_achalandage", "a_synthese")}
    quadrants = {l[0]: l[9] for l in t["a_portefeuille"].lignes}
    assert set(quadrants.values()) <= {"Étoile", "Vache à lait", "Prometteuse", "En recul"}
    assert quadrants["Riz"] in ("Étoile", "Prometteuse")  # absent de la comparaison : en croissance
    ach = t["a_achalandage"]
    samedi = next(l for l in ach.lignes if l[:2] == ["samedi", "11 h"])
    assert samedi[3] == D("3.2") and samedi[5] == D("1.0")  # (4 × 3 + DIR1) / 4 samedis, une seule employée
    cartes = {t_: v for t_, _g, v in ach.cartes}
    assert cartes["Heure de pointe"] == "samedi 11 h"
    assert any(c[0] == "Marge brute" for c in t["a_synthese"].cartes)


def test_rythme_et_objectif(tmp_path):
    """Période en cours : réalisé, projection par jour de la semaine, à faire par jour ; budget prioritaire."""
    from mvogmbi_sync.budget import Budget, POSTES

    d, a = _periode(), _avant()
    r = an.calculer("a_rythme", d, a, {}, DU, AU, DU2, AU2, aujourd_hui=DU + timedelta(days=14))
    c = {t: v for t, _g, v in r.cartes}
    assert c["Jours restants"] == 14 and c["Objectif"] == D("140.00")  # comparaison : 28 × 5 $
    assert c["Projection de fin de période"] > c["Réalisé"] * D("0.9")
    assert len(r.lignes) == 28 and r.lignes[13][2] == "Réalisé" and r.lignes[14][2] == "En cours (projection)"
    assert r.lignes[-1][6] == D("140.00")  # objectif cumulé = objectif
    Budget(tmp_path).definir(2026, 9, {POSTES[0]: D("3000")})
    r = an.calculer("a_rythme", d, a, {}, DU, AU, DU2, AU2, racine=tmp_path, aujourd_hui=DU + timedelta(days=14))
    c = {t: v for t, _g, v in r.cartes}
    assert c["Objectif"] == D("2400.00")  # 24 jours de septembre × 100 $ (octobre sans budget)
    syn = an.calculer("a_synthese", d, a, {}, DU, AU, DU2, AU2, racine=tmp_path, aujourd_hui=DU + timedelta(days=14))
    assert any(l[1] == "Rattraper l'objectif de la période" for l in syn.lignes)
    fini = an.calculer("a_rythme", d, a, {}, DU, AU, DU2, AU2)
    assert dict((t, v) for t, _g, v in fini.cartes)["Jours restants"] == 0
    # « Ce mois-ci » s'arrête à aujourd'hui : la fin visée est la fin du mois, de même pour la semaine et l'année
    assert an.fin_naturelle(date(2026, 11, 1), date(2026, 11, 8), date(2026, 11, 8)) == date(2026, 11, 30)
    assert an.fin_naturelle(date(2026, 11, 2), date(2026, 11, 8), date(2026, 11, 8)) == date(2026, 11, 8)
    assert an.fin_naturelle(date(2026, 11, 2), date(2026, 11, 4), date(2026, 11, 4)) == date(2026, 11, 8)
    assert an.fin_naturelle(date(2026, 1, 1), date(2026, 11, 8), date(2026, 11, 8)) == date(2026, 12, 31)
    assert an.fin_naturelle(date(2026, 10, 1), date(2026, 10, 31), date(2026, 11, 8)) == date(2026, 10, 31)


def test_remboursements_et_especes():
    t = {cle: an.calculer(cle, _periode(), _avant(), {}, DU, AU, DU2, AU2) for cle in ("a_remboursements", "a_especes")}
    rem = t["a_remboursements"]
    c = {t_: v for t_, _g, v in rem.cartes}
    assert c["Montant remboursé"] == D("10.00") and c["Commandes remboursées"] == 1
    ligne = next(i for i, l in enumerate(rem.lignes) if l[0] == "Commande")
    assert rem.ids_commandes[ligne] == "RB1"
    assert an._genre_paiement("Espèces") == "Espèces" and an._genre_paiement("Carte, Espèces") == "Espèces et carte"
    assert an._genre_paiement("Carte de crédit") == "Carte ou autre"
    esp = t["a_especes"]
    assert len(esp.lignes) == 28 and esp.cartes[0][0] == "Payé en espèces"


def test_nouveaux_articles_et_jours_feries():
    t = {cle: an.calculer(cle, _periode(), _avant(), {}, DU, AU, DU2, AU2) for cle in ("a_nouveaux", "a_feries")}
    nouveaux = {l[0] for l in t["a_nouveaux"].lignes}
    assert "Plantain" not in nouveaux and {"Manioc", "Riz", "Sel"} <= nouveaux  # le plantain se vendait déjà
    fer = t["a_feries"]
    assert fer.lignes[0][0] == "2026-09-07" and fer.lignes[0][1] == "Fête du Travail"  # 1er lundi de septembre
    assert dict((t_, v) for t_, _g, v in fer.cartes)["Jours fériés dans la période"] == 1


def test_analyses_de_la_soiree():
    """Taxes et pourboires, gains par moment, articles qui baissent, catégories selon le jour, achalandage prévu."""
    t = {cle: an.calculer(cle, _periode(), _avant(), COUTS, DU, AU, DU2, AU2)
         for cle in ("a_taxes", "a_gains", "a_baisse", "a_categories_jour", "a_prevu")}
    gains = {t_: v for t_, _g, v in t["a_gains"].cartes}
    assert gains["Jour qui rapporte le plus"] == "samedi" and gains["Mesure"] == "Bénéfice brut"
    cj = t["a_categories_jour"]
    assert cj.entetes[1] == "lundi" and {l[0] for l in cj.lignes} == {"Fruits", "Riz"}
    prevu = t["a_prevu"]
    assert prevu.lignes and all(l[3] >= 1 for l in prevu.lignes)
    assert {t_: v for t_, _g, v in t["a_baisse"].cartes}["Semaines comparées"] == 4
    assert t["a_taxes"].cartes[0][0] == "Taxes perçues"


def test_article_qui_baisse():
    """Riz vendu 4 fois par jour la 1re semaine, puis 3, 2, 1 : forte baisse."""
    cmds, n = [], 0
    for i in range(28):
        j = DU + timedelta(days=i)
        for _k in range(4 - i // 7):
            n += 1
            cmds.append(_commande(f"R{n}", j, [("Riz", "R", 1000)]))
    r = an.calculer("a_baisse", _donnees(cmds), _donnees([]), {}, DU, AU, DU2, AU2)
    assert r.lignes and r.lignes[0][0] == "Riz" and r.lignes[0][7] == "Forte baisse"


def test_valeur_seuil_et_quantites(tmp_path):
    from mvogmbi_sync.budget import Budget, POSTES

    Budget(tmp_path).definir(2026, 9, {POSTES[2]: D("100")})
    Budget(tmp_path).definir(2026, 10, {POSTES[2]: D("100")})
    d, a = _periode(), _avant()
    seuil = an.calculer("a_seuil", d, a, COUTS, DU, AU, DU2, AU2, racine=tmp_path)
    c = {t_: v for t_, _g, v in seuil.cartes}
    assert c["Frais du mois (budget)"] == D("100.00") and c["Ventes nécessaires par jour ouvert"] > 0
    valeur = an.calculer("a_valeur", d, a, {}, DU, AU, DU2, AU2)
    assert valeur.lignes[0][0] in ("Client Un", "Client Deux", "Client Trois")
    q = an.calculer("a_quantites", d, a, {}, DU, AU, DU2, AU2)
    samedi = {l[0]: l[7] for l in q.lignes}  # le samedi vend 3 fois plus
    assert samedi and max(samedi.values()) >= D("3.0")


def test_jour_du_mois_saison_et_poids():
    """Début de mois plus fort ; mangue vendue surtout en août ; plantain au poids plus cher qu'avant."""
    cmds, n = [], 0
    debut = date(2026, 6, 1)
    for i in range(122):  # juin à septembre
        j = debut + timedelta(days=i)
        for _k in range(3 if j.day <= 5 else 1):
            n += 1
            cmds.append(_commande(f"J{n}", j, [("Riz", "R", 1000)]))
        if j.month == 8:
            n += 1
            cmds.append(_commande(f"J{n}", j, [("Mangue", "M", 1500)]))
        elif j.day == 15:
            n += 1
            cmds.append(_commande(f"J{n}", j, [("Mangue", "M", 1500)]))
    poids = _commande("P1", date(2026, 9, 20), [("Plantain lb", "P", 500)])
    poids["lineItems"]["elements"][0]["unitQty"] = 1500
    cmds.append(poids)
    d = _donnees(cmds)
    avant = _commande("P0", date(2026, 5, 20), [("Plantain lb", "P", 400)])
    avant["lineItems"]["elements"][0]["unitQty"] = 2000
    a = _donnees([avant])
    du, au = date(2026, 6, 1), date(2026, 9, 30)
    jdm = an.calculer("a_jour_mois", d, a, {}, du, au, date(2026, 2, 1), date(2026, 5, 31))
    c = {t_: v for t_, _g, v in jdm.cartes}
    assert c["Meilleur moment du mois"] == "du 1er au 5" and c["Indice du meilleur moment"] > 150
    sai = an.calculer("a_saison", d, a, {}, du, au, date(2026, 2, 1), date(2026, 5, 31),
                      aujourd_hui=date(2026, 7, 10))
    mangue = next(l for l in sai.lignes if l[0] == "Mangue")
    assert mangue[2] == "août 2026" and mangue[8] == "Article de saison"
    assert [l[0] for l in sai.prochains] == ["Mangue"]  # août = mois prochain
    poi = an.calculer("a_poids", d, a, {}, du, au, date(2026, 2, 1), date(2026, 5, 31))
    ligne = poi.lignes[0]
    assert ligne[0] == "Plantain lb" and ligne[3] == D("1.500") and ligne[5] == D("5.00") and ligne[7] == D("25.0")
    assert poi.hausses_prix and poi.graphiques
    syn = an.calculer("a_synthese", d, a, {}, du, au, date(2026, 2, 1), date(2026, 5, 31), aujourd_hui=date(2026, 7, 10))
    assert any("saison" in str(l[1]) for l in syn.lignes)


def test_ruptures_probables():
    """Article vendu chaque jour puis plus du tout depuis 4 jours : rupture en cours ; trou de 2 jours : rien."""
    cmds, n = [], 0
    debut = date(2026, 9, 1)
    for k in range(30):
        j = debut + timedelta(days=k)
        n += 1
        cmds.append(_commande(f"T{n}", j, [("Pain", "P", 300)]))
        if k < 26:
            cmds.append(_commande(f"R{n}", j, [("Riz", "R", 1000)]))
        if k not in (10, 11):
            cmds.append(_commande(f"L{n}", j, [("Lait", "L", 500)]))
        if k >= 10:  # lancé en cours de période : pas une rupture avant sa 1re vente
            cmds.append(_commande(f"N{n}", j, [("Neuf", "N", 800)]))
    d = _donnees(cmds)
    a = _donnees([])
    du, au = debut, debut + timedelta(days=29)
    r = an.calculer("a_ruptures", d, a, {}, du, au, date(2026, 8, 1), date(2026, 8, 31), aujourd_hui=au + timedelta(days=1))
    noms = {l[0]: l for l in r.lignes}
    assert "Lait" not in noms and "Pain" not in noms and "Neuf" not in noms
    riz = noms["Riz"]
    assert riz[4] == 4 and riz[7] == "Oui" and riz[9] == D("40.00")
    assert r.graphiques
    syn = an.calculer("a_synthese", d, a, {}, du, au, date(2026, 8, 1), date(2026, 8, 31), aujourd_hui=au + timedelta(days=1))
    assert any("ne se vendent plus" in str(l[1]) for l in syn.lignes)


def test_articles_d_appel():
    """Viande toujours avec d'autres articles dans de grosses commandes : article d'appel ; Eau achetée seule : achat
    rapide."""
    cmds = []
    for k in range(30):
        j = date(2026, 9, 1) + timedelta(days=k)
        cmds.append(_commande(f"AP-V{k}", j, [("Viande", "V", 3000), ("Riz", "R", 1500), ("Huile", "H", 2000)]))
        for e in range(3):
            cmds.append(_commande(f"AP-E{k}-{e}", j, [("Eau", "E", 200)]))
        cmds.append(_commande(f"AP-F{k}", j, [("Riz", "R", 1500)]))
    d, a = _donnees(cmds), _donnees([])
    r = an.calculer("a_appel", d, a, {}, date(2026, 9, 1), date(2026, 9, 30), date(2026, 8, 1), date(2026, 8, 31))
    profils = {l[0]: l[10] for l in r.lignes}
    assert profils["Viande"] == "Article d'appel" and profils["Eau"] == "Achat rapide"
    viande = next(l for l in r.lignes if l[0] == "Viande")
    assert viande[4] == D("65.00") and viande[8] == D("35.00") and viande[7] == 0
    assert r.graphiques and r.appel


def test_ventes_complementaires_manquees():
    """Eru presque toujours avec Fufu (20 fois sur 30) : complément habituel, 10 commandes sans, gain = 10 × 5 $ / 4."""
    cmds = []
    for k in range(30):
        j = date(2026, 9, 1) + timedelta(days=k)
        cmds.append(_commande(f"CM-A{k}", j, [("Eru", "E", 1000), ("Fufu", "F", 500)] if k < 20 else [("Eru", "E", 1000)]))
        for e in range(4):
            cmds.append(_commande(f"CM-B{k}-{e}", j, [("Pain", "P", 300)]))
    d, a = _donnees(cmds), _donnees([])
    r = an.calculer("a_complements", d, a, {}, date(2026, 9, 1), date(2026, 9, 30), date(2026, 8, 1), date(2026, 8, 31))
    eru = next(l for l in r.lignes if l[0] == "Eru")
    assert eru[1] == "Fufu" and eru[6] == 10 and eru[8] == D("12.50")
    assert r.graphiques


def test_prix_selon_le_format():
    """Riz 1kg à 4 $ (4 $ / kg) et Riz 5kg à 25 $ (5 $ / kg) : le grand format est plus cher au kg."""
    assert an.format_article("Attieke 1kg Sun")[1:] == (1000.0, "kg")
    assert an.format_article("Jus Oasis 6x330ml")[1:] == (1980.0, "L")
    assert an.format_article("Plantain Jaune en lb") is None
    cmds = []
    for k in range(5):
        j = date(2026, 9, 1) + timedelta(days=k)
        cmds.append(_commande(f"PF-A{k}", j, [("Riz Parfumé 1kg", "R1", 400)]))
        cmds.append(_commande(f"PF-B{k}", j, [("Riz Parfumé 5kg", "R5", 2500)]))
        cmds.append(_commande(f"PF-C{k}", j, [("Sucre 1kg", "S1", 300), ("Sucre 2kg", "S2", 500)]))
    d, a = _donnees(cmds), _donnees([])
    r = an.calculer("a_prix_format", d, a, {}, date(2026, 9, 1), date(2026, 9, 30), date(2026, 8, 1), date(2026, 8, 31))
    riz5 = next(l for l in r.lignes if l[1] == "Riz Parfumé 5kg")
    assert riz5[6] == D("5.00") and riz5[8] == D("25.0") and riz5[9] == "Plus cher qu'un format plus petit"
    assert all(l[9] == "Correct" for l in r.lignes if l[0] == "sucre")
    assert [l[1] for l in r.mal] == ["Riz Parfumé 5kg"] and r.graphiques


def test_ventes_par_tranche_de_prix():
    cmds = [_commande(f"TP-A{k}", date(2026, 9, 1) + timedelta(days=k), [("Sel", "S", 150), ("Riz 5kg", "R", 2500)])
            for k in range(10)]
    avant = [_commande(f"TP-B{k}", date(2026, 8, 1) + timedelta(days=k), [("Sel", "S", 150)]) for k in range(10)]
    r = an.calculer("a_tranches", _donnees(cmds), _donnees(avant), {}, date(2026, 9, 1), date(2026, 9, 30),
                    date(2026, 8, 1), date(2026, 8, 31))
    par = {l[0]: l for l in r.lignes}
    assert par["Moins de 2 $"][1] == 1 and par["Moins de 2 $"][3] == D("15.00")
    assert par["20 à 50 $"][3] == D("250.00") and par["20 à 50 $"][6] is None
    assert dict((t_, v) for t_, _g, v in r.cartes)["Tranche qui vend le plus"] == "20 à 50 $"
    assert r.graphiques


def test_ce_qui_fait_monter_ou_baisser_les_ventes():
    cmds = [_commande(f"CO-A{k}", date(2026, 9, 1) + timedelta(days=k), [("Riz", "R", 2000), ("Pomme", "P", 100)])
            for k in range(10)]
    avant = [_commande(f"CO-B{k}", date(2026, 8, 1) + timedelta(days=k), [("Riz", "R", 1000), ("Pomme", "P", 500)])
             for k in range(10)]
    r = an.calculer("a_contribution", _donnees(cmds), _donnees(avant), {}, date(2026, 9, 1), date(2026, 9, 30),
                    date(2026, 8, 1), date(2026, 8, 31))
    cartes = dict((t_, v) for t_, _g, v in r.cartes)
    assert cartes["Écart des ventes nettes"] == D("60.00")
    assert cartes["Fait le plus monter"] == "Riz" and cartes["Fait le plus baisser"] == "Fruits"
    riz = next(l for l in r.lignes if l[0] == "Articles" and l[1] == "Riz")
    assert riz[5] == D("100.00")
    assert r.graphiques


def test_effet_des_rabais():
    cmds = []
    for k in range(10):
        j = date(2026, 9, 1) + timedelta(days=k)
        cmds.append(_commande(f"ER-A{k}", j, [("Riz", "R", 4000), ("Pain", "P", 1000)], rabais=10,
                              nom_rabais="Rabais 10%"))
        cmds.append(_commande(f"ER-B{k}", j, [("Pain", "P", 1000)]))
        cmds.append(_commande(f"ER-C{k}", j, [("Riz", "R", 4000)], rabais=100, nom_rabais="Direction"))
    d = _donnees(cmds)
    r = an.calculer("a_effet_rabais", d, _donnees([]), {}, date(2026, 9, 1), date(2026, 9, 30), date(2026, 8, 1),
                    date(2026, 8, 31))
    avec, sans = r.lignes[0], r.lignes[1]
    assert avec[1] == 10 and sans[1] == 10  # les rabais Direction sont mis à part
    assert avec[3] == D("45.00") and avec[4] == D("5.00") and sans[3] == D("10.00")
    assert r.lignes[2][0] == "Rabais 10%" and not r.inefficace
