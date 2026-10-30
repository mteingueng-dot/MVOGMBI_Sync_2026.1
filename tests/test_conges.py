from datetime import date, datetime, timedelta
from decimal import Decimal as D

from mvogmbi_sync import conges as co
from mvogmbi_sync import paie_temps as pt


def test_jours_feries_du_quebec():
    assert co.paques(2026) == date(2026, 4, 5) and co.paques(2027) == date(2027, 3, 28)
    feries = dict((n, j) for j, n in co.jours_feries(2026))
    assert feries["Vendredi saint"] == date(2026, 4, 3)
    assert feries["Journée nationale des patriotes"] == date(2026, 5, 18)   # le 24 mai 2026 est un dimanche
    assert co.jours_feries(2021)[2][0] == date(2021, 5, 24)                # le 24 mai 2021 est un lundi
    assert feries["Fête du Travail"] == date(2026, 9, 7) and feries["Action de grâces"] == date(2026, 10, 12)
    assert dict((n, j) for j, n in co.jours_feries(2029))["Fête du Canada"] == date(2029, 7, 2)  # 1er juillet dimanche
    assert dict((n, j) for j, n in co.jours_feries(2029))["Fête nationale du Québec"] == date(2029, 6, 25)
    assert co.jours_feries(2026, "lundi")[1] == (date(2026, 4, 6), "Lundi de Pâques")


def test_indemnite_un_vingtieme_des_heures_normales(tmp_path):
    registre = pt.Registre(tmp_path)
    e = registre.ajouter("Jean Essai")
    ferie = date(2026, 10, 12)                       # Action de grâces (lundi)
    debut = co.debut_semaine(ferie) - timedelta(days=28)
    for i in range(28):                              # 4 semaines : 6 jours × 8 h = 48 h -> 40 h normales comptées
        jour = debut + timedelta(days=i)
        if jour.weekday() != 6:
            registre.pointer(e.id, pt.ARRIVEE, datetime.combine(jour, datetime.min.time()).replace(hour=8))
            registre.pointer(e.id, pt.DEPART, datetime.combine(jour, datetime.min.time()).replace(hour=16))
    assert co.indemnite_heures(registre, e, ferie) == D("8.00")   # 4 × 40 h / 20


def test_conges_soldes_et_heures_a_payer(tmp_path):
    registre = pt.Registre(tmp_path)
    e = registre.ajouter("Jean Essai")
    conges = co.Registre(tmp_path)
    conges.embauches[e.id] = "2022-03-01"
    conges.ajouter(e.id, date(2026, 10, 13), date(2026, 10, 14), co.MALADIE_PAYE, D("8"), "gérant")
    conges.ajouter(e.id, date(2026, 10, 20), date(2026, 10, 24), co.VACANCES, D("8"), "gérant",
                   jours_travailles=lambda j: j.weekday() < 4)
    try:
        conges.ajouter(e.id, date(2026, 10, 13), date(2026, 10, 13), co.MALADIE_NON_PAYE, D("8"), "gérant")
        assert False, "doublon refusé"
    except ValueError:
        pass
    s = co.solde(co.Registre(tmp_path), e, date(2026, 10, 29))
    assert (s.vacances_semaines, s.vacances_taux, s.vacances_prises) == (3, "6 %", 3)  # 4,7 ans de service
    assert (s.maladie_payes_dus, s.maladie_payes_pris) == (2, 2) and not s.remarques
    feries, payes, detail = co.heures_a_payer(co.Registre(tmp_path), registre, e, date(2026, 10, 4), date(2026, 10, 17))
    assert payes == D("16") and feries == D("0.00") and "Action de grâces" in detail[0]
    nouveau = co.solde(conges, registre.ajouter("Nouveau"), date(2026, 10, 29))
    assert nouveau.maladie_payes_dus == 0 and "Date d'embauche à saisir" in nouveau.remarques
