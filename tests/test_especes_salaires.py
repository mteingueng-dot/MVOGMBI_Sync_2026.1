from datetime import date
from decimal import Decimal as D

from mvogmbi_sync.encaissements import (A_SAISIR, A_VERIFIER, APPLIQUE, ECART, Depot, LigneEncaissement, evaluer,
                                        repartir_especes)
from mvogmbi_sync.rapprochement import (A_ENCAISSER, A_PAIE, RAPPROCHE, MouvementBanque, MouvementSage, est_especes,
                                        facture_du_jour, jours_couverts, rapprocher)


def banque(jour, montant, description, rang=0):
    return MouvementBanque(jour, description, D(montant), releve="R.pdf", rang=rang)


INTERAC = "VRW Virement Interac de / JEAN EXEMPLE/"
ESPECES = "DGA Dépôt au GA / CDS CARREFOUR DE L'ESTRIE"


def test_mouvements_d_especes_reconnus():
    assert est_especes(banque("2026-01-13", "80.88", INTERAC))
    assert est_especes(banque("2026-02-10", "1370.00", ESPECES))
    assert not est_especes(banque("2026-01-02", "-139.00", "VNW Virement Interac à / MARIE EXEMPLE/"))
    assert not est_especes(banque("2026-01-02", "6279.34", "DI Dépôt direct / FIRST DATA CANADA(K)"))


def test_facture_qui_couvre_le_jour():
    factures = {"Vente 2026-10-22", "Vente 2026-10-23/25", "Vente Septembre 2026", "Vente S38-2026"}
    assert facture_du_jour(date(2026, 10, 22), factures) == "Vente 2026-10-22"
    assert facture_du_jour(date(2026, 10, 24), factures) == "Vente 2026-10-23/25"
    assert facture_du_jour(date(2026, 9, 16), factures) == "Vente S38-2026"  # la semaine avant le mois
    assert facture_du_jour(date(2026, 9, 30), factures) == "Vente Septembre 2026"
    assert facture_du_jour(date(2026, 10, 26), factures) == ""
    assert len(jours_couverts("Vente Février 2026")) == 28


def test_interac_et_especes_absents_a_encaisser():
    mouvements = [banque("2026-10-22", "80.88", INTERAC), banque("2026-10-23", "500.00", ESPECES, 1),
                  banque("2026-10-23", "-5.95", "FIX Frais fixes d'utilisation", 2)]
    rapprocher(mouvements, [])
    assert [m.etat for m in mouvements] == [A_ENCAISSER, A_ENCAISSER, "Absent de Sage"]


def test_repartition_interac_et_especes():
    factures = {"Vente 2026-10-20": date(2026, 10, 20), "Vente 2026-10-21": date(2026, 10, 21),
                "Vente 2026-10-23/25": date(2026, 10, 25)}
    dus = {"Vente 2026-10-20": D("300.00"), "Vente 2026-10-21": D("1100.00"), "Vente 2026-10-23/25": D("900.00")}
    # lot de cartes du 21 pas encore encaissé : il reste 100 $ d'espèces sur cette facture
    clover = [Depot(date(2026, 10, 22), [LigneEncaissement(date(2026, 10, 21), D("1000.00"), etat=A_SAISIR)])]
    mouvements = [banque("2026-10-24", "50.00", INTERAC), banque("2026-10-22", "350.00", ESPECES, 1),
                  banque("2026-10-22", "999.00", ESPECES, 2), banque("2026-10-21", "40.00", INTERAC, 3)]
    for m in mouvements:
        m.etat = A_ENCAISSER
    depots = repartir_especes(mouvements, factures, dus, clover)
    interac_21 = next(d for d in depots if d.montant == D("40.00"))
    especes = next(d for d in depots if d.montant == D("350.00"))
    trop = next(d for d in depots if d.lignes[0].montant == D("999.00"))
    interac_samedi = next(d for d in depots if d.montant == D("50.00"))
    assert [(l.facture, l.montant) for l in interac_21.lignes] == [("Vente 2026-10-21", D("40.00"))]
    # dépôt d'espèces : la facture la plus ancienne d'abord (300 $), puis ce qui reste sur le 21 (100 - 40 = 60 $)
    assert [(l.facture, l.montant) for l in especes.lignes] == [("Vente 2026-10-20", D("300.00")),
                                                                 ("Vente 2026-10-21", D("50.00"))]
    assert trop.etat == A_VERIFIER and "de trop" in trop.remarque
    # Interac du samedi : facture de fin de semaine, encaissement daté du dimanche (date de la facture)
    assert interac_samedi.lignes[0].facture == "Vente 2026-10-23/25"
    assert interac_samedi.date == date(2026, 10, 25) and interac_samedi.origine == "Interac JEAN EXEMPLE"


def test_mouvement_deja_dans_sage_et_lot_clover_le_meme_jour():
    m = banque("2026-10-22", "80.88", INTERAC)
    m.etat, m.sage = RAPPROCHE, [1234]
    (depot,) = repartir_especes([m], {}, {}, [])
    assert depot.etat == APPLIQUE
    # même jour qu'un encaissement d'espèces : le lot Clover n'est appliqué que si son montant exact est dans Sage
    lot = Depot(date(2026, 10, 22), [LigneEncaissement(date(2026, 10, 21), D("1000.00"))])
    etat = {"Vente 2026-10-21": {"du": D("500.00"), "encaisse": {date(2026, 10, 22): D("350.00")},
                                 "recus": {date(2026, 10, 22): [D("350.00")]}}}
    evaluer([lot], etat, date(2026, 10, 26), {date(2026, 10, 22)})
    assert lot.lignes[0].etat == A_SAISIR
    evaluer([lot], etat, date(2026, 10, 26))
    assert lot.lignes[0].etat == ECART  # sans encaissement d'espèces connu ce jour-là : écart à vérifier
    etat["Vente 2026-10-21"]["recus"][date(2026, 10, 22)].append(D("1000.00"))
    evaluer([lot], etat, date(2026, 10, 26), {date(2026, 10, 22)})
    assert lot.lignes[0].etat == APPLIQUE


def test_salaires_relies_aux_paies_meme_en_retard():
    sage = [MouvementSage(40, "2026-01-05", "PAY05012026", "Employé A", D("-449.94")),
            MouvementSage(38, "2026-01-19", "PAY19012026", "Employé A", D("-449.94"))]
    salaire = banque("2026-02-04", "-449.94", "PPW Paiement internet à / Depot Salaire/PAYE05012026")
    absent = banque("2026-02-04", "-1541.54", "PPW Paiement internet à / Depot Salaire/PAY16022026", 1)
    rapprocher([salaire, absent], [], sage)  # paies d'avant la période des relevés
    assert salaire.etat == RAPPROCHE and salaire.sage == [40]  # la paie de la référence, pas la plus proche
    assert absent.etat == A_PAIE


def test_periode_choisie_soldes_et_mouvements():
    from mvogmbi_sync.rapprochement import Releve, restreindre

    janvier = Releve("R1.pdf", "2026-01-01", "2026-01-31", D("100.00"), D("130.00"),
                     [MouvementBanque("2026-01-10", "a", D("50.00"), D("150.00"), "R1.pdf", 0),
                      MouvementBanque("2026-01-20", "b", D("-20.00"), None, "R1.pdf", 1)])
    fevrier = Releve("R2.pdf", "2026-02-01", "2026-02-28", D("130.00"), D("100.00"),
                     [MouvementBanque("2026-02-05", "c", D("-30.00"), D("100.00"), "R2.pdf", 0)])
    banque, ouverture, fermeture = restreindre([fevrier, janvier], date(2026, 1, 15), date(2026, 2, 3))
    assert [m.description for m in banque] == ["b"]
    assert (ouverture, fermeture) == (D("150.00"), D("130.00"))
    assert restreindre([janvier, fevrier], date(2026, 1, 1), date(2026, 2, 28))[1:] == (D("100.00"), D("100.00"))
