from datetime import date, datetime, timedelta
from decimal import Decimal as D

from mvogmbi_sync import paie as pa
from mvogmbi_sync import paie_temps as pt
from mvogmbi_sync.planning import Planning, Quart


class BaseFactice:
    """Écriture de paie au sens normal des comptes : charges et passifs positifs, banque négative."""

    def __init__(self, lignes):
        self.lignes = lignes

    def requete(self, _sql, _params=()):
        return self.lignes


def _ligne(ident, jour, compte, nom, montant, employe="Jean Essai"):
    return {"i": ident, "d": datetime.fromisoformat(jour), "s": "PAY01112026", "c": employe, "compte": compte * 10000,
            "nom": nom, "m": D(montant)}


def test_paie_de_sage_classee_et_expliquee():
    base = BaseFactice([
        _ligne(1, "2026-11-01", 5300, "Salaires", "1000.00"),
        _ligne(1, "2026-11-01", 5310, "RRQ - employeur", "64.00"),
        _ligne(1, "2026-11-01", 5320, "Vacances", "40.00"),
        _ligne(1, "2026-11-01", 2330, "RRQ à payer", "128.00"),          # 64 employé + 64 employeur
        _ligne(1, "2026-11-01", 2310, "Impôt du Québec à payer", "90.00"),
        _ligne(1, "2026-11-01", 2390, "Vacances à payer", "40.00"),
        _ligne(1, "2026-11-01", 1055, "Desjardins", "-846.00"),
        _ligne(2, "2026-11-15", 5300, "Salaires", "500.00"),
        _ligne(2, "2026-11-15", 1055, "Desjardins", "-500.00"),
    ])
    paies = pa.paies_sage(base, date(2026, 1, 1), date(2026, 11, 30))
    p = paies[0]
    assert p.brut == D("1000.00") and p.net == D("846.00") and p.vacances == D("40.00")
    assert p.retenues == {"RRQ": D("64.00"), "Impôt du Québec": D("90.00")} and p.cotisations == {"RRQ": D("64.00")}
    assert [pa.rubrique(n) for n in ("RQAP à payer", "AE - employeur", "Impôt fédéral à payer", "CNESST")] == [
        "RQAP", "Assurance-emploi", "Impôt fédéral", "CNESST"]
    assert p.total_retenues == D("154.00") and p.total_cotisations == D("64.00") and p.ecart == 0
    assert pa.lignes_paies(paies)[0][-1] == "✔"
    cumul = pa.cumul_annee(paies, paies[1])
    assert cumul.brut == D("1500.00") and cumul.net == D("1346.00")
    entetes, lignes, sous_titre = pa.releve(paies[1], cumul, None)
    assert entetes[-1] == "Total de l'année" and "Jean Essai" in sous_titre
    assert ["Salaire brut", "", "500,00 $", "1 500,00 $"] in lignes


def test_heures_planifiees_realisees_et_validees(tmp_path):
    registre = pt.Registre(tmp_path)
    e = registre.ajouter("Jean Essai")
    debut = date(2026, 10, 18)
    for jour, arrivee, depart in ((debut + timedelta(days=1), 8, 16), (debut + timedelta(days=8), 9, 13)):
        registre.pointer(e.id, pt.ARRIVEE, datetime.combine(jour, datetime.min.time()).replace(hour=arrivee))
        registre.pointer(e.id, pt.DEPART, datetime.combine(jour, datetime.min.time()).replace(hour=depart))
    planning = Planning(tmp_path)
    planning.definir(e.id, [debut + timedelta(days=1)], Quart("08:00", "17:00", 60))
    feuilles = pt.feuilles(registre, debut, datetime(2026, 11, 5))
    semaines = pa.semaines(feuilles, planning)
    assert [(l.debut, l.planifiees, l.realisees) for l in semaines] == [
        (debut, D("8.00"), D("8.00")), (debut + timedelta(days=7), D(0), D("4.00"))]
    assert pa.jours(feuilles, planning)[0][2] == "08:00-17:00 (60 min)"
    lignes = pa.validees(feuilles)
    assert lignes[0][8] == pt.A_APPROUVER and lignes[0][7] == D("12.00")
    pt.approuver(registre, feuilles[0], "gérant")
    assert pa.validees(pt.feuilles(registre, debut, datetime(2026, 11, 5)))[0][8] == pt.APPROUVEE
    assert pa.heures(D("12.50")) == "12,5 h"


def test_employe_de_la_paie_et_feuille(tmp_path):
    registre = pt.Registre(tmp_path)
    e = registre.ajouter("Jean Essai")
    registre.ajouter("Jean")
    p = pa.PaieSage(1, date(2026, 11, 3), "PAY03112026", "ESSAI, JEAN")
    assert pa.employe_de(p, registre.employes) is e
    registre.pointer(e.id, pt.ARRIVEE, datetime(2026, 10, 20, 8))
    registre.pointer(e.id, pt.DEPART, datetime(2026, 10, 20, 12))
    f = pa.feuille_de_la_paie(registre, e, p.jour, date(2026, 10, 18))
    assert f is not None and f.debut == date(2026, 10, 18) and f.total == D("4.00")


def test_lien_employe_clover_sage(tmp_path):
    registre = pt.Registre(tmp_path)
    e = registre.ajouter("Jean Essai")
    autre = registre.ajouter("Marie Test")
    noms = ["ESSAI, JEAN", "TEST MARIE", "TEST MARIE-EVE"]
    assert pa.proposer_lien(e, noms) == "ESSAI, JEAN"
    assert pa.proposer_lien(autre, noms) == ""  # deux possibilités : rien n'est proposé
    autre.numero_sage = "TEST MARIE-EVE"         # lien choisi par le gérant
    p = pa.PaieSage(1, date(2026, 11, 3), "PAY03112026", "Test Marie-Eve")
    assert pa.employe_de(p, registre.employes) is autre

    class Base:
        def requete(self, sql, _p=()):
            if "FROM temp" in sql:
                raise PermissionError("SELECT refusé")
            return [{"n": "TEST MARIE"}, {"n": "ESSAI, JEAN"}, {"n": ""}]

    assert pa.employes_sage(Base()) == ["ESSAI, JEAN", "TEST MARIE"]


def test_paie_sage_jamais_deux_fois(tmp_path):
    from mvogmbi_sync import robot_paie as rp

    assert rp._nombre("18") == "18,00" and rp._nombre("75.5") == "75,50"
    registre = rp.Registre(tmp_path)
    p = rp.PaieATraiter("ESSAI EMPLOYE 2", "2026-11-15", "2026-11-28", "2026-11-30", "10", "2")
    assert not registre.deja(p)
    registre.noter(p, rp.Resultat("ESSAI EMPLOYE 2", messages=["échec"]))
    assert not rp.Registre(tmp_path).deja(p)          # un échec se refait
    registre.noter(p, rp.Resultat("ESSAI EMPLOYE 2", fait=True, brut="234.00", net="173.63"))
    assert rp.Registre(tmp_path).deja(p)              # une paie traitée, jamais deux fois


def test_bulletin_envoye_au_seul_employe(tmp_path, monkeypatch):
    from mvogmbi_sync import courriel

    envoyes = []
    monkeypatch.setattr(courriel, "_expedier", lambda c, m: envoyes.append(m))
    config = {"courriel": {"serveur": "smtp.exemple.test", "expediteur": "paie@exemple.test",
                           "destinataires": "gerant@exemple.test", "copie": "comptable@exemple.test"}}
    p = pa.PaieSage(1, date(2026, 11, 30), "6", "Jean Essai")
    pa.envoyer_bulletin(config, "jean@exemple.test", "Jean Essai", p, b"%PDF-1.4 essai")
    m = envoyes[0]
    assert m["To"] == "jean@exemple.test" and m["Cc"] is None   # jamais le gérant ni le comptable en copie
    pieces = list(m.iter_attachments())
    assert pieces[0].get_content_type() == "application/pdf" and pieces[0].get_content() == b"%PDF-1.4 essai"
    assert pa.cle_bulletin(p) not in pa.bulletins_envoyes(tmp_path)
    pa.noter_envoi(tmp_path, p, "jean@exemple.test")
    assert pa.cle_bulletin(p) in pa.bulletins_envoyes(tmp_path)
    try:
        courriel.envoyer_a(config, "jean@exemple.test, marie@exemple.test", "s", "c")
        assert False, "deux destinataires refusés"
    except ValueError:
        pass


def test_numero_desjardins_rapproche():
    from mvogmbi_sync.rapprochement import REFERENCE_PAIE
    from mvogmbi_sync.robot_paie import numero_desjardins

    n = numero_desjardins("2026-12-28")
    assert n == "PAY28122026" and REFERENCE_PAIE.search("Depot Salaire/" + n).group(1) == "28122026"
