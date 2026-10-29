from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest

from mvogmbi_sync import paie_temps as pt


def registre(tmp_path):
    r = pt.Registre(tmp_path)
    e = r.ajouter("Employé A")
    r.definir_nip(e.id, "1234")
    r.enregistrer()
    return r, e


def jour(d, h, m=0):
    return datetime(2026, 10, d, h, m)


def test_nip_empreinte_et_blocage(tmp_path):
    r, e = registre(tmp_path)
    assert "1234" not in (tmp_path / "donnees" / "employes_paie.json").read_text(encoding="utf-8")
    assert r.verifier_nip(e.id, "1234") and not r.verifier_nip(e.id, "9999")
    autre = r.ajouter("Employé B")
    with pytest.raises(pt.ErreurPointage):
        r.definir_nip(autre.id, "1234")  # NIP déjà pris
    with pytest.raises(pt.ErreurPointage):
        r.definir_nip(autre.id, "12")
    moment = datetime(2026, 10, 20, 9)
    for _ in range(pt.ESSAIS_NIP - 1):  # un NIP faux déjà tapé plus haut
        r.verifier_nip(e.id, "0000", moment)
    with pytest.raises(pt.ErreurPointage):
        r.verifier_nip(e.id, "1234", moment + timedelta(seconds=10))
    assert r.verifier_nip(e.id, "1234", moment + timedelta(seconds=pt.ATTENTE_NIP + 1))


def test_pointages_pauses_supplementaires_et_approbation(tmp_path):
    r, e = registre(tmp_path)
    debut = date(2026, 10, 18)  # dimanche
    with pytest.raises(pt.ErreurPointage):
        r.pointer(e.id, pt.DEPART, jour(19, 8))
    for d in (19, 20, 21, 22, 23):  # 5 jours de 8 h 30 à 18 h avec 30 min de pause : 9 h
        r.pointer(e.id, pt.ARRIVEE, jour(d, 8, 30))
        r.pointer(e.id, pt.PAUSE, jour(d, 12))
        r.pointer(e.id, pt.FIN_PAUSE, jour(d, 12, 30))
        r.pointer(e.id, pt.DEPART, jour(d, 18))
    r.pointer(e.id, pt.ARRIVEE, jour(26, 9))
    r.pointer(e.id, pt.PAUSE, jour(26, 12))
    r.pointer(e.id, pt.DEPART, jour(26, 13))     # départ pendant la pause : la pause se termine
    r.pointer(e.id, pt.ARRIVEE, jour(27, 9))     # départ oublié
    f = pt.feuille(pt.Registre(tmp_path), e, debut, datetime(2026, 10, 30, 10))
    assert f.jours[1:6] == [Decimal("9.00")] * 5 and f.jours[8] == Decimal("3.00")
    assert f.semaines == [Decimal(45), Decimal(3)]
    assert (f.normales, f.supplementaires) == (Decimal(43), Decimal(5))
    assert f.anomalies == ["2026-10-27 : Départ manquant"]
    with pytest.raises(pt.ErreurPointage):
        pt.approuver(r, f, "Gérant")
    # correction du gérant : départ ajouté avec motif, puis approbation
    r2 = pt.Registre(tmp_path)
    with pytest.raises(pt.ErreurPointage):
        r2.corriger(e.id, pt.DEPART, jour(27, 17), "Gérant", " ")
    r2.corriger(e.id, pt.DEPART, jour(27, 17), "Gérant", "oubli de pointer")
    f = pt.feuille(r2, e, debut, datetime(2026, 10, 30, 10))
    assert not f.anomalies and f.jours[9] == Decimal(8) and f.corrigee
    pt.approuver(r2, f, "Gérant")
    assert pt.feuille(pt.Registre(tmp_path), e, debut).etat == pt.APPROUVEE
    # heure changée après approbation : la feuille revient à approuver
    r3 = pt.Registre(tmp_path)
    depart = [p for p in r3.valides(e.id) if p.moment.startswith("2026-10-27") and p.type == pt.DEPART][0]
    r3.corriger(e.id, pt.DEPART, jour(27, 16), "Gérant", "erreur d'heure", remplace=depart.id)
    f = pt.feuille(pt.Registre(tmp_path), e, debut)
    assert f.jours[9] == Decimal(7) and f.etat == pt.A_APPROUVER
    assert len([p for p in r3.pointages if p.employe == e.id]) == 28  # 26 pointages + 2 corrections : rien n'est effacé


def test_poste_et_gerant_ne_s_ecrasent_pas(tmp_path):
    r, e = registre(tmp_path)
    gerant = pt.Registre(tmp_path)
    poste = pt.Registre(tmp_path)
    poste.pointer(e.id, pt.ARRIVEE, jour(20, 8))
    gerant.definir_nip(e.id, "5678")
    gerant.corriger(e.id, pt.DEPART, jour(20, 16), "Gérant", "départ")
    poste.pointer(e.id, pt.ARRIVEE, jour(21, 8))
    relu = pt.Registre(tmp_path)
    assert len(relu.pointages) == 3 and relu.verifier_nip(e.id, "5678")


def test_periode_et_import_clover(tmp_path):
    assert pt.debut_periode(date(2026, 10, 31)) == date(2026, 10, 18)
    assert pt.debut_periode(date(2026, 11, 1)) == date(2026, 11, 1)
    assert pt.debut_periode(date(2026, 10, 17)) == date(2026, 10, 4)
    r = pt.Registre(tmp_path)
    assert r.importer_clover([{"id": "c1", "name": "Employé A"}, {"id": "c2", "name": "Employé A"},
                              {"id": "c3", "name": ""}]) == 1
    assert r.importer_clover([{"id": "c1", "name": "Employé A"}]) == 0
