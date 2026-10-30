import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path

from mvogmbi_sync import sauvegarde as sv


def _donnees(racine: Path) -> None:
    (racine / "donnees" / "cache_clover").mkdir(parents=True)
    (racine / "donnees" / "cache_clover" / "2026-10-01.json").write_text("{}", encoding="utf-8")
    (racine / "donnees" / "correspondance_articles.xlsx").write_bytes(b"xlsx")
    (racine / "donnees" / "correspondance_articles.cache.json").write_text("{}", encoding="utf-8")
    (racine / "donnees" / "pointages.json").write_text('[{"id": 1}]', encoding="utf-8")
    (racine / "config.toml").write_text("[clover]\n", encoding="utf-8")


def test_sauvegarde_verifiee_sans_les_caches(tmp_path):
    racine, cible = tmp_path / "app", tmp_path / "copies"
    _donnees(racine)
    e = sv.sauvegarder(racine, {}, cible, maintenant=datetime(2026, 10, 29, 23, 0))
    assert e.ok and e.fichiers == 3
    with zipfile.ZipFile(e.fichier) as z:
        assert sorted(z.namelist()) == ["config.toml", "donnees/correspondance_articles.xlsx", "donnees/pointages.json"]
    assert sv.derniere(racine).ok and not sv.en_retard(racine, datetime(2026, 10, 30, 8, 0))
    assert "jours" in sv.en_retard(racine, datetime(2026, 11, 3, 8, 0))


def test_conservation_jours_semaines_mois():
    aujourdhui = date(2026, 10, 29)
    noms = [Path(f"{sv.PREFIXE}{aujourdhui - timedelta(days=i):%Y-%m-%d}_230000.zip") for i in range(400)]
    noms.append(Path(f"{sv.PREFIXE}{aujourdhui:%Y-%m-%d}_120000.zip"))  # 2e du jour : la plus ancienne des deux part
    gardees = sv.a_garder(noms, aujourdhui)
    jours = {sv._jour(a) for a in gardees}
    assert all(aujourdhui - timedelta(days=i) in jours for i in range(14))
    assert Path(f"{sv.PREFIXE}{aujourdhui:%Y-%m-%d}_120000.zip") not in gardees
    assert len({(j.year, j.month) for j in jours}) == 12 and min(jours) >= date(2025, 11, 1)
    assert len(gardees) < 40


def test_restauration_garde_l_etat_actuel(tmp_path):
    racine, cible = tmp_path / "app", tmp_path / "copies"
    _donnees(racine)
    e = sv.sauvegarder(racine, {}, cible)
    (racine / "donnees" / "pointages.json").write_text("[]", encoding="utf-8")  # données abîmées
    avant, n = sv.restaurer(racine, {}, Path(e.fichier))
    assert n == 3 and (racine / "donnees" / "pointages.json").read_text(encoding="utf-8") == '[{"id": 1}]'
    with zipfile.ZipFile(avant.fichier) as z:
        assert z.read("donnees/pointages.json") == b"[]"   # l'état d'avant est gardé


def test_restauration_jamais_hors_de_l_application(tmp_path):
    racine = tmp_path / "app"
    _donnees(racine)
    piege = tmp_path / "copies" / f"{sv.PREFIXE}2026-10-29_230000.zip"
    piege.parent.mkdir()
    with zipfile.ZipFile(piege, "w") as z:
        z.writestr("../dehors.txt", "x")
        z.writestr("donnees/ok.json", "{}")
    _avant, n = sv.restaurer(racine, {}, piege)
    assert n == 1 and not (tmp_path / "dehors.txt").exists()
