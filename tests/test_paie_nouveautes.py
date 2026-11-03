from datetime import date, datetime
from decimal import Decimal as D
from types import SimpleNamespace

from mvogmbi_sync.calendrier_paie import Calendrier
from mvogmbi_sync.fenetre_planning import semaines_horaire
from mvogmbi_sync.utilisateurs import ACTIONS_FENETRES, LIMITES_DEFAUT, PROFILS_DEFAUT
from mvogmbi_sync import feuillets
from mvogmbi_sync.paie import PaieSage, completer_details, cumul_annee, fiche_de_paie, rubrique


def test_calendrier_premiere_paie_puis_automatique(tmp_path):
    c = Calendrier(tmp_path)
    assert c.paies(2026) == [] and c.reference(date(2026, 3, 1)) is None
    c.definir(2026, date(2026, 2, 2))
    c.enregistrer()
    c = Calendrier(tmp_path)
    paies = c.paies(2026)
    assert (paies[0].debut, paies[0].fin) == (date(2026, 1, 5), date(2026, 1, 18))
    assert paies[1].jour == date(2026, 2, 16) and all(p.jour.year == 2026 for p in paies)
    suite = c.paies(2027)   # année à venir : suite de 14 jours
    assert not c.saisie(2027) and (suite[0].jour - paies[-1].jour).days == 14
    assert c.paie_de_periode(date(2026, 1, 5)).numero == 1
    assert c.prochaine(date(2026, 2, 3)).jour == date(2026, 2, 16)


def test_droits_gerant_et_lancer():
    assert "Gérant" in PROFILS_DEFAUT and "Employé" in LIMITES_DEFAUT
    assert "Lancer le traitement maintenant" in ACTIONS_FENETRES["Général"]


def paie_test(jour):
    return PaieSage(1, jour, "PAY", "EXEMPLE JEAN", gains={"5300": D("1000.00")},
                    passifs={"RRQ": D("60.00"), "Impôt du Québec": D("90.00")}, net=D("850.00"))


def test_feuillets_cumulent_l_annee():
    paies = [paie_test(date(2026, 1, 5)), paie_test(date(2026, 2, 2)), paie_test(date(2025, 12, 1))]
    f = feuillets.calculer(paies, 2026)[0]
    assert (f.brut, f.rrq, f.impot_quebec) == (D("2000.00"), D("120.00"), D("180.00"))
    employeur = SimpleNamespace(nom="Marché", adresse="1 rue", ville="Sherbrooke")
    html = feuillets.t4_html(f, employeur, "123") + feuillets.rl1_html(f, employeur)
    assert "2 000,00" in html and "Relevé 1" in html


def test_fiche_de_paie_sans_part_de_l_employeur():
    p = paie_test(date(2026, 2, 2))
    p.cotisations = {"RRQ": D("60.00")}
    p.passifs["RRQ"] = D("120.00")
    page = fiche_de_paie(p, p, None)
    assert "EXEMPLE JEAN" in page and "1 000,00" in page and "cotisation de l'employeur" not in page.lower()


def test_horaire_par_semaine():
    lignes = [["2026-10-25", "dim.", "9:00", "17:00", 30, "7,50"], ["2026-10-26", "lun.", "Repos", "", 0, ""],
              ["2026-11-01", "dim.", "9:00", "13:00", 0, "4,00"]]
    sortie, totaux = semaines_horaire(lignes)
    assert totaux == [D("7.50"), D("4.00")]
    assert [x[4] for x in sortie] == ["semaine", "quart", "repos", "semaine", "quart"] and sortie[0][3] == "7,50"


class BaseFausse:
    """Tables de paie de Sage ; `refus` : accès au module Paie non donné."""

    def __init__(self, refus=False):
        self.refus = refus

    def requete(self, sql, params=()):
        if self.refus:
            raise RuntimeError(1142, "SELECT command denied")
        assert "sSIN" not in sql and "*" not in sql  # jamais le NAS
        if "FROM tpydet a" in sql:
            return [{"lId": 5, "lEmpId": 9, "lJourId": 1, "dGross": 90.0, "dHrsWorked": 5.0,
                     "dtPrdStart": datetime(2026, 12, 13), "dtPrdEnd": datetime(2026, 12, 26), "dEIEarn": 90.0,
                     "dPenEarn": 90.0, "dQpipEarn": 90.0, "dVacBalFor": 100.0}]
        if "tcomppy5" in sql:
            return [{"lId": 6, "sName": "Régulières", "sUnit": "Heure"}]
        if "tcomppy6" in sql:
            return []
        if "FROM temp" in sql:
            return [{"lId": 9, "sStreet1": "1 rue Exemple", "sStreet2": "", "sCity": "Sherbrooke", "sProvState": "QC",
                     "sPostalZip": "J1J 1J1", "sEmail": "a@exemple.test"}]
        if "tpydet1" in sql:
            return [{"lDetId": 5, "lEmpId": 9, "lIncId": 4, "nType": 3, "dAmtPrUnit": 0, "dUnitsPrPd": 1, "dAmtPerPd": 3.6,
                     "dAmtYTD": 40.0},
                    {"lDetId": 5, "lEmpId": 9, "lIncId": 5, "nType": 3, "dAmtPrUnit": 0, "dUnitsPrPd": 0, "dAmtPerPd": 0,
                     "dAmtYTD": 15.0},
                    {"lDetId": 5, "lEmpId": 9, "lIncId": 6, "nType": 3, "dAmtPrUnit": 18.0, "dUnitsPrPd": 5, "dAmtPerPd": 90.0,
                     "dAmtYTD": 450.0}]
        return [{"lDetId": 5, "lEmpId": 9, "lDedId": 1, "dDedPerPd": 1.17, "dAmtYTD": 5.85},
                {"lDetId": 5, "lEmpId": 9, "lDedId": 6, "dDedPerPd": 11.84, "dAmtYTD": 59.15}]


def test_detail_lu_dans_les_tables_de_paie():
    p = PaieSage(1, date(2026, 12, 28), "PAY", "EXEMPLE JEAN", gains={"Salaires": D("93.60")}, net=D("76.99"))
    assert completer_details(BaseFausse(), [p])
    assert p.brut == D("90.00") and p.ecart == 0  # la provision de vacances n'est pas dans le brut
    assert p.retenues == {"Assurance-emploi": D("1.17"), "Impôt du Québec": D("11.84")}
    d = p.detail
    assert d.vacances_dues == D("125.00") and d.courriel == "a@exemple.test" and "J1J 1J1" in d.adresse
    cumul = cumul_annee([p], p)
    assert cumul.brut == D("465.00") and cumul.retenues["Impôt du Québec"] == D("59.15")
    page = fiche_de_paie(p, cumul, None)
    assert "Vacances dues" in page and "125,00" in page and "Solde rep." in page and "Régulières @ 18,00/Hr" in page
    f = feuillets.calculer([p], 2026)[0]
    assert (f.gains_ae, f.impot_quebec, f.courriel) == (D("90.00"), D("11.84"), "a@exemple.test")


def test_sans_acces_paie_les_ecritures_servent():
    p = PaieSage(1, date(2026, 12, 28), "PAY", "EXEMPLE JEAN", gains={"Salaires": D("100.00")}, net=D("100.00"))
    assert not completer_details(BaseFausse(refus=True), [p])
    assert p.detail is None and p.brut == D("100.00")
    assert rubrique("Québec à payer") == "Impôt du Québec"
