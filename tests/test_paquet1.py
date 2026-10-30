import json
from datetime import date, datetime, timedelta
from decimal import Decimal as D

from mvogmbi_sync import depenses as dp
from mvogmbi_sync import fin_emploi as fe
from mvogmbi_sync import journal_operations as jo
from mvogmbi_sync import paie as pa
from mvogmbi_sync import paie_temps as pt


def test_depense_taxes_et_ecriture(tmp_path):
    assert dp.taxes_de(D("11.50"), "GQ") == (D("10.00"), D("0.50"), D("1.00"))
    assert dp.taxes_de(D("21.00"), "G") == (D("20.00"), D("1.00"), D(0))
    assert dp.taxes_de(D("8.00"), "") == (D("8.00"), D(0), D(0))
    comptes = {"tps": "2315", "tvq": "2345", "petite_caisse": "1050", "carte": "1086", "banque": "1055"}
    d = dp.Depense("DP-0001", "2026-11-30", "ESSAI", "x", "11.50", "GQ", "5700", dp.PETITE_CAISSE)
    lignes = d.lignes(comptes)
    assert lignes[0] == ("1050", D(0), D("11.50"))                      # le crédit d'abord
    assert sum(l[1] for l in lignes) == sum(l[2] for l in lignes) == D("11.50")
    r = dp.Registre(tmp_path)
    r.comptes = comptes
    r.ajouter(dp.Depense("", "2026-11-01", "Banque", "fond", "200", "", "", dp.APPRO))
    r.ajouter(d)
    assert r.solde_petite_caisse() == D("188.50")
    assert dp.Registre(tmp_path).comptes_manquants() == []
    assert dp.Registre(tmp_path).comptes_manquants([dp.Depense("", "", "", "", "1", moyen=dp.EMPLOYE)]) == \
        ["Employé à rembourser"]

class _BaseComptes:
    def requete(self, sql, *_a):
        if "ttaxauth" in sql:
            return [{"sName": "TPS/TVH", "lAcPurTax": 23150000}, {"sName": "TVQ", "lAcPurTax": 23450000}]
        return [{"lId": 21900000, "sName": "Impôt fédéral à payer"}, {"lId": 22050000, "sName": "Québec à payer"},
                {"lId": 23150000, "sName": "TPS/TVH payée sur les achats"},
                {"lId": 23450000, "sName": "TVQ payée sur les achats"}, {"lId": 10500000, "sName": "Petite caisse"}]


def test_comptes_de_taxes_jamais_les_retenues_de_paie():
    comptes = dp.proposer_comptes(_BaseComptes())
    assert (comptes["tps"], comptes["tvq"], comptes["petite_caisse"]) == ("2315", "2345", "1050")
    noms = {"2190": "Impôt fédéral à payer", "2205": "Québec à payer", "2315": "TPS/TVH payée sur les achats",
            "2345": "TVQ payée sur les achats"}
    assert len(dp.comptes_douteux({"tps": "2190", "tvq": "2205"}, noms)) == 2
    assert dp.comptes_douteux({"tps": "2315", "tvq": "2345"}, noms) == []


def test_releve_emploi_et_concordance(tmp_path):
    registre = pt.Registre(tmp_path)
    e = registre.ajouter("Jean Essai")
    e.numero_sage = "Jean Essai"
    for i in range(10):
        j = date(2026, 10, 1) + timedelta(days=i)
        registre.pointer(e.id, pt.ARRIVEE, datetime.combine(j, datetime.min.time()).replace(hour=9))
        registre.pointer(e.id, pt.DEPART, datetime.combine(j, datetime.min.time()).replace(hour=17))
    heures, premier = fe.heures_assurables(registre, e, date(2026, 10, 31))
    assert heures == D("80.00") and premier == date(2026, 10, 1)
    paies = []
    for i, jour in enumerate((date(2026, 10, 12), date(2026, 10, 26))):
        p = pa.PaieSage(i, jour, "PAY", "Jean Essai")
        for c, n, m in ((5410, "Salaires", "600"), (2330, "RRQ à payer", "38"), (2310, "Impôt du Québec à payer", "40"),
                        (1055, "Banque", "-522")):
            pa.classer(p, c, n, D(m))
        paies.append(p)
    assert fe.remunerations(paies, "Jean Essai", date(2026, 10, 31)) == [(date(2026, 10, 26), D("600.00")),
                                                                         (date(2026, 10, 12), D("600.00"))]
    lignes, sous_titre = fe.preparation_re(registre, e, paies, date(2026, 10, 31), "E")
    assert "motif E" in sous_titre and ["Rémunération assurable totale", "1 200,00 $"] in lignes
    c = fe.concordance(paies, registre, 2026)[0]
    assert c[0] == "Jean Essai" and c[1] == 2 and c[3] == D("1200.00") and c[-2] == D("1044.00") and c[-1] == "✔"


def test_journal_des_operations(tmp_path):
    donnees = tmp_path / "donnees"
    donnees.mkdir()
    (donnees / "journal_prix_clover.csv").write_text(
        "﻿Date;ID Clover;Article Clover;Prix avant;Prix après\n2026-10-29 10:00:00;X1;Riz;10;11\n", encoding="utf-8")
    (donnees / "pertes.json").write_text(json.dumps([{"numero": "PE-0001", "motif": "Périmé", "lignes": [{}],
                                                      "cree": "2026-10-28T09:00:00", "auteur": "gérant"}]),
                                         encoding="utf-8")
    ops = jo.lire(tmp_path)
    assert [o.source for o in ops] == ["Prix Clover changés", "Pertes"]
    assert "Riz" in ops[0].detail and ops[1].personne == "gérant"
    assert len(jo.filtrer(ops, du="2026-10-29")) == 1 and len(jo.filtrer(ops, texte="périmé")) == 1
