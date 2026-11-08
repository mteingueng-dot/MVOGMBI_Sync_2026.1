from datetime import date, datetime
from decimal import Decimal as D

from mvogmbi_sync.encaissements import (A_SAISIR, A_VENIR, APPLIQUE, ECART, SANS_FACTURE, date_depot, evaluer,
                                        numero_compte_sage, regrouper)


def test_date_de_depot():
    # lundi à jeudi : le lendemain
    assert date_depot(date(2026, 5, 18)) == date(2026, 5, 19)  # lundi -> mardi
    assert date_depot(date(2026, 5, 21)) == date(2026, 5, 22)  # jeudi -> vendredi
    # vendredi, samedi, dimanche : le lundi suivant
    for jour in (22, 23, 24):
        assert date_depot(date(2026, 5, jour)) == date(2026, 5, 25)


def test_regroupement_fin_de_semaine():
    lots = {date(2026, 5, 21): D("1722.89"), date(2026, 5, 22): D("3909.13"), date(2026, 5, 23): D("4166.37"),
            date(2026, 5, 24): D("2504.08"), date(2026, 5, 25): D("1198.00"), date(2026, 5, 26): D("0")}
    depots = regrouper(lots)
    assert [d.date for d in depots] == [date(2026, 5, 22), date(2026, 5, 25), date(2026, 5, 26)]
    assert depots[1].montant == D("10579.58")  # dépôt du lundi = ventes par carte de vendredi à dimanche
    assert [l.facture for l in depots[1].lignes] == ["Vente 2026-05-22", "Vente 2026-05-23", "Vente 2026-05-24"]


def test_compte_sage():
    assert numero_compte_sage("1055") == 10550000
    assert numero_compte_sage(10550000) == 10550000


def test_etats_selon_sage():
    lots = {date(2026, 5, 18): D("1942.95"), date(2026, 5, 19): D("1446.41"), date(2026, 5, 20): D("2560.81"),
            date(2026, 10, 25): D("100.00"), date(2026, 5, 21): D("1722.89")}
    depots = regrouper(lots)
    etat_sage = {
        "Vente 2026-05-18": {"du": D("139.16"), "encaisse": {date(2026, 5, 19): D("1942.95")}},
        "Vente 2026-05-19": {"du": D("1588.43"), "encaisse": {}},
        "Vente 2026-05-20": {"du": D("2640.56"), "encaisse": {date(2026, 5, 21): D("100.00")}},
        "Vente 2026-10-25": {"du": D("150.00"), "encaisse": {}},
    }
    evaluer(depots, etat_sage, aujourdhui=date(2026, 10, 25))
    etats = {d.date: d.etat for d in depots}
    assert etats[date(2026, 5, 19)] == APPLIQUE
    assert etats[date(2026, 5, 20)] == A_SAISIR
    assert etats[date(2026, 5, 21)] == ECART
    assert etats[date(2026, 5, 22)] == SANS_FACTURE  # facture du 21 pas encore importée
    assert etats[date(2026, 10, 26)] == A_VENIR


def test_facture_de_fin_de_semaine():
    from mvogmbi_sync.facture import jours_facture, numero_facture, numero_fin_de_semaine
    from mvogmbi_sync.periodes import TypePeriode, bornes

    assert bornes(TypePeriode.FIN_DE_SEMAINE, date(2026, 5, 23)) == (date(2026, 5, 22), date(2026, 5, 24))
    assert numero_fin_de_semaine(date(2026, 5, 22), date(2026, 5, 24)) == "Vente 2026-05-22/24"
    assert len(numero_fin_de_semaine(date(2026, 7, 31), date(2026, 8, 2))) <= 20  # limite du n° de facture Sage
    assert numero_facture(TypePeriode.FIN_DE_SEMAINE, date(2026, 7, 31), date(2026, 8, 2)) == "Vente 2026-07-31/02"
    assert jours_facture("Vente 2026-07-31/02") == [date(2026, 7, 31), date(2026, 8, 1), date(2026, 8, 2)]
    assert jours_facture("Vente 2026-05-20") == [date(2026, 5, 20)]
    assert jours_facture("Vente Mars 2025") == []


def test_depot_du_lundi_sur_la_facture_de_fin_de_semaine():
    from mvogmbi_sync.encaissements import factures_fin_de_semaine

    lots = {date(2026, 10, 23): D("100.00"), date(2026, 10, 24): D("200.00"), date(2026, 10, 25): D("50.00"),
            date(2026, 5, 22): D("3909.13"), date(2026, 5, 23): D("4166.37"), date(2026, 5, 24): D("2504.08")}
    depots = regrouper(lots)
    # mai : factures journalières déjà dans Sage -> une ligne par facture ; octobre : une seule facture
    factures_fin_de_semaine(depots, {"Vente 2026-05-22", "Vente 2026-05-23", "Vente 2026-05-24"})
    mai, octobre = depots
    assert [l.facture for l in mai.lignes] == ["Vente 2026-05-22", "Vente 2026-05-23", "Vente 2026-05-24"]
    assert [(l.facture, l.montant) for l in octobre.lignes] == [("Vente 2026-10-23/25", D("350.00"))]


def test_fin_de_semaine_facturee_en_partie():
    """Vendredi et samedi déjà facturés jour par jour, dimanche seul ensuite (cas du 2026-10-26)."""
    from mvogmbi_sync.encaissements import factures_fin_de_semaine
    from mvogmbi_sync.facture import numero_fin_de_semaine

    assert numero_fin_de_semaine(date(2026, 10, 25), date(2026, 10, 25)) == "Vente 2026-10-25"
    lots = {date(2026, 10, 23): D("100.00"), date(2026, 10, 24): D("200.00"), date(2026, 10, 25): D("50.00")}
    for dimanche in ("Vente 2026-10-25/25", "Vente 2026-10-25"):  # ancien et nouveau n° du dimanche seul
        depots = regrouper(lots)
        factures_fin_de_semaine(depots, {"Vente 2026-10-23", "Vente 2026-10-24", dimanche})
        assert [(l.facture, l.montant) for l in depots[0].lignes] == [
            ("Vente 2026-10-23", D("100.00")), ("Vente 2026-10-24", D("200.00")), (dimanche, D("50.00"))]
    # samedi et dimanche ensemble, vendredi déjà facturé
    depots = regrouper(lots)
    factures_fin_de_semaine(depots, {"Vente 2026-10-23", "Vente 2026-10-24/25"})
    assert [(l.facture, l.montant) for l in depots[0].lignes] == [
        ("Vente 2026-10-23", D("100.00")), ("Vente 2026-10-24/25", D("250.00"))]


def test_depot_deja_au_compte_par_une_autre_ecriture():
    """Un lot « À saisir » dont le montant est déjà au 1055 (journal général…) n'est jamais encaissé d'office."""
    from mvogmbi_sync.encaissements import (A_SAISIR, APPLIQUE, DEJA_EN_BANQUE, Depot, LigneEncaissement,
                                            marquer_deja_en_banque)
    from mvogmbi_sync.rapprochement import MouvementSage

    deja = Depot(date(2026, 1, 6), [LigneEncaissement(date(2026, 1, 5), D("812.40"), etat=A_SAISIR)],
                 etat=A_SAISIR)
    libre = Depot(date(2026, 1, 7), [LigneEncaissement(date(2026, 1, 6), D("500.00"), etat=A_SAISIR)],
                  etat=A_SAISIR)
    applique = Depot(date(2026, 1, 8), [LigneEncaissement(date(2026, 1, 7), D("300.00"), etat=APPLIQUE)],
                     etat=APPLIQUE)
    autre = Depot(date(2026, 1, 9), [LigneEncaissement(date(2026, 1, 8), D("300.00"), etat=A_SAISIR)],
                  etat=A_SAISIR)
    mouvements = [MouvementSage(1, "2026-01-07", "Dépôt", "", D("812.40")),
                  MouvementSage(2, "2026-01-07", "Chèque", "", D("-500.00")),   # sortie : ignorée
                  MouvementSage(3, "2026-01-08", "Encaissement", "", D("300.00"))]  # celle de « applique »
    marquer_deja_en_banque([deja, libre, applique, autre], mouvements)
    assert deja.etat == DEJA_EN_BANQUE and deja.lignes[0].etat == DEJA_EN_BANQUE and "2026-01-07" in deja.remarque
    assert libre.etat == A_SAISIR and autre.etat == A_SAISIR and applique.etat == APPLIQUE


def test_colonne_montant_recu_selon_la_taille_de_la_grille():
    """Constat du 2026-11-06 : grille de 791 points sur la copie d'essai, ~640 sur le serveur (x fixe 692 hors grille)."""
    from mvogmbi_sync.robot_encaissements import FenetreEncaissements

    class Fausse(FenetreEncaissements):
        def __init__(self, taille):
            self.taille, self.ligne_y0 = taille, 40

        def _taille_grille(self):
            return self.taille

    essai, serveur = Fausse((774, 160)), Fausse((641, 96))
    assert 631 <= essai.x_montant() <= 774 and essai.lignes_visibles() == 8
    assert 540 <= serveur.x_montant() <= 623 and serveur.lignes_visibles() == 4


def test_un_encaissement_en_echec_ne_bloque_pas_les_suivants(monkeypatch):
    """Règle du propriétaire (2026-11-07) : un dépôt en échec est noté, la fenêtre remise à zéro, les autres continuent."""
    from contextlib import contextmanager
    from datetime import date as _d
    from decimal import Decimal as D
    from types import SimpleNamespace

    from mvogmbi_sync import __main__ as principal
    from mvogmbi_sync import robot_encaissements as re_

    class Fenetre:
        titre = "Encaissements"

        def photo_diagnostic(self, nom):
            return None

    monkeypatch.setattr(re_, "FenetreEncaissements", Fenetre)
    remises = []
    monkeypatch.setattr(re_, "remettre_a_zero", lambda f, tiers, rouvrir=None: remises.append(tiers) or f)

    def faux(fenetre, depot, *args):
        if depot.montant == D("1"):
            raise re_.ErreurRobot("La cellule « Montant reçu » ne s'est pas ouverte")
        return re_.ResultatEncaissement(depot.date.isoformat(), depot.montant, True)

    monkeypatch.setattr(re_, "_encaisser_et_verifier", faux)

    @contextmanager
    def base(*a, **k):
        yield None

    monkeypatch.setattr(principal, "ouvrir_base_sage", base)
    depots = [SimpleNamespace(etat="À saisir dans Sage", date=_d(2026, 1, j), montant=D(str(j)), origine="", lignes=[])
              for j in (1, 2, 3)]
    resultats = re_.appliquer({}, depots, "Vente Hebdomadaire", "1055", journal=lambda t: None)
    assert [r.traite for r in resultats] == [False, True, True]
    assert "Montant reçu" in resultats[0].messages[0]
    assert remises == ["Vente Hebdomadaire"]

    # fenêtre impossible à rouvrir : les dépôts restants sont notés « non tenté », un résultat chacun
    def casse(f, tiers, rouvrir=None):
        raise re_.ErreurRobot("fermée")

    monkeypatch.setattr(re_, "remettre_a_zero", casse)
    resultats = re_.appliquer({}, depots, "Vente Hebdomadaire", "1055", journal=lambda t: None)
    assert len(resultats) == 3 and not any(r.traite for r in resultats)
    assert resultats[1].messages[0].startswith("Non tenté")
