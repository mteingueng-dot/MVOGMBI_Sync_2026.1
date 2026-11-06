"""Sage gardé ouvert pour les saisies de la journée (règle du propriétaire du 2026-11-06)."""
import threading

from mvogmbi_sync import __main__ as m


def test_fermer_bases_garde_le_sage_de_la_journee(monkeypatch, tmp_path):
    arret = threading.Event()
    fil = threading.Thread(target=arret.wait, daemon=True)
    fil.start()
    signaux = []
    monkeypatch.setattr(m, "_signal_garde", lambda nom: signaux.append(nom) or arret.set())
    monkeypatch.setattr(m, "_liberer_base_des_autres", lambda *a, **k: None)
    monkeypatch.setitem(m._SAGE_GARDE, "fil", fil)
    monkeypatch.setitem(m._SAGE_GARDE, "permanent", True)
    monkeypatch.setitem(m._SAGE_GARDE, "pid", None)
    m.fermer_bases()                      # avant une saisie : le Sage de la journée reste ouvert
    assert not signaux and fil.is_alive()
    m.fermer_bases(sage=True)             # import, nuit, sortie de l'application : refermé
    assert signaux == ["arret"] and m._SAGE_GARDE["fil"] is None


def test_marque_du_sage_garde(monkeypatch, tmp_path):
    import os

    from mvogmbi_sync import sage_bureau as sb

    monkeypatch.setattr(sb, "_marque_sage_garde", lambda: tmp_path / "sage_garde.json")
    assert sb.sage_garde() is None and sb.pids_gardes() == sb.PIDS_GARDES
    sb.noter_sage_garde(os.getpid(), r"C:\Sage\ESSAI.SAI", tmp_path)   # processus vivant : ce test
    assert sb.sage_garde("ESSAI.SAI")["pid"] == os.getpid()
    assert sb.sage_garde("AUTRE.SAI") is None
    assert os.getpid() in sb.pids_gardes()                              # jamais pris pour le Sage de la personne
    sb.oublier_sage_garde(os.getpid())
    assert sb.sage_garde() is None


def test_sage_de_la_journee_en_ouverture(monkeypatch, tmp_path):
    """Constat du 2026-11-06 sur SERVDCSAGE : pendant l'ouverture, ce Sage était pris pour celui d'une personne et
    l'outil d'import relancé par les lectures prenait l'entreprise."""
    import os
    import subprocess
    import sys
    import time

    from mvogmbi_sync import sage_bureau as sb

    monkeypatch.setattr(sb, "_marque_sage_garde", lambda: tmp_path / "sage_garde.json")
    monkeypatch.setitem(m._SAGE_GARDE, "fil", None)
    assert not m.sage_journee_en_cours()
    sb.noter_ouverture_garde(r"C:\Sage\ESSAI.SAI", tmp_path)            # ce programme ouvre Sage
    assert sb.garde_en_ouverture() and sb.sage_garde() is None and m.sage_journee_en_cours()
    debut = time.time()
    sb.attendre_fin_ouverture(delai=30)                                # jamais d'attente de soi-même
    assert time.time() - debut < 1
    autre = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:   # ouvert par un autre programme : on attend qu'il ait fini (marque retirée)
        marque = sb._lire_marque()
        marque["ouverture"] = autre.pid
        (tmp_path / "sage_garde.json").write_text(__import__("json").dumps(marque), encoding="utf-8")
        assert sb.oublier_ouverture_garde() is None and sb.garde_en_ouverture()   # pas la sienne : gardée
        debut = time.time()
        sb.attendre_fin_ouverture(delai=2)
        assert time.time() - debut >= 1.5
    finally:
        autre.kill()
        autre.wait()
    assert sb.garde_en_ouverture() is None                             # programme parti : plus en ouverture
    sb.noter_ouverture_garde(r"C:\Sage\ESSAI.SAI", tmp_path)
    sb.oublier_ouverture_garde()
    assert sb._lire_marque() is None and os.getpid() not in sb.pids_gardes()


def test_le_sage_d_une_personne_passe_d_abord(monkeypatch, tmp_path):
    """Constat du 2026-11-06 sur SERVDCSAGE : « Cette entreprise partagée est déjà ouverte » quand le propriétaire
    ouvre Sage dans la session de l'application ; Sage n'ouvre l'entreprise qu'une fois par ordinateur."""
    import time
    from datetime import datetime

    import pytest

    from mvogmbi_sync import sage_bureau as sb

    if datetime.now().hour < 6:
        pytest.skip("la nuit, le Sage de la journée est refermé de toute façon")

    class Fin(Exception):
        pass

    def un_tour(_s):
        raise Fin

    arret = threading.Event()
    fil = threading.Thread(target=arret.wait, daemon=True)
    fil.start()
    fermetures, ouvertures = [], []
    monkeypatch.setattr(time, "sleep", un_tour)
    monkeypatch.setattr(sb, "sage_ouvert", lambda: True)            # une personne a lancé Sage
    monkeypatch.setattr(m, "fermer_bases", lambda sage=False: fermetures.append(sage))
    monkeypatch.setattr(m, "_sage_garde", lambda *a, **k: ouvertures.append(a))
    config = lambda: {"sage_import": {"fichier_entreprise": r"C:\Sage\ESSAI.SAI"}}  # noqa: E731
    monkeypatch.setitem(m._SAGE_GARDE, "fil", fil)
    monkeypatch.setitem(m._SAGE_GARDE, "permanent", True)
    with pytest.raises(Fin):
        m.garder_sage_ouvert(tmp_path, lire_config=config)
    assert fermetures == [True]                                      # Sage de la journée refermé tout de suite
    monkeypatch.setitem(m._SAGE_GARDE, "fil", None)                  # ensuite : plus de Sage gardé
    with pytest.raises(Fin):
        m.garder_sage_ouvert(tmp_path, lire_config=config)
    assert ouvertures == []                                          # jamais rouvert tant que ce Sage est là
    arret.set()


def test_sage_orphelin_du_bureau_cache(monkeypatch):
    """Constat du 2026-11-06 sur SERVDCSAGE : l'installation a coupé le gardien, Sage est resté seul sur le bureau
    caché ; il ne doit jamais passer pour le Sage d'une personne, et il est reconnu comme orphelin."""
    from mvogmbi_sync import sage_bureau as sb

    monkeypatch.setattr(sb, "sages_du_bureau_cache", lambda: {1644: 9800, 2000: 3000})
    monkeypatch.setattr(sb, "_processus", lambda: {1644: (9800, "sage50accounting.exe"),
                                                   2000: (3000, "sage50accounting.exe"),
                                                   3000: (1, "mvogmbi_sync_console.exe")})
    assert sb.sages_orphelins() == {1644}                 # gardien 9800 disparu ; 2000 a encore le sien
    assert {1644, 2000} <= sb.pids_gardes()                # jamais « le Sage de la personne »


def test_pause_de_l_installateur(monkeypatch, tmp_path):
    import time

    monkeypatch.setattr(m, "_fichier_pause", lambda: tmp_path / "sage_pause.txt")
    assert not m.sage_en_pause()
    (tmp_path / "sage_pause.txt").write_text(str(time.time()), encoding="utf-8")
    assert m.sage_en_pause()                               # programme lancé avant la mise à jour : pas de Sage rouvert
    monkeypatch.setattr(m, "DEMARRAGE", time.time() + 1)
    assert not m.sage_en_pause()                           # programme lancé après : la pause ne le concerne pas


def test_le_serveur_web_n_ouvre_jamais_sage(monkeypatch, tmp_path):
    """Règle du propriétaire du 2026-11-06 : Sage est lié à l'application Windows ; si elle n'est pas ouverte, Sage
    reste fermé. Le serveur web ne fait que refermer un Sage resté seul."""
    import time

    import pytest

    from mvogmbi_sync import sage_bureau as sb

    class Fin(Exception):
        pass

    monkeypatch.setattr(time, "sleep", lambda _s: (_ for _ in ()).throw(Fin()))
    monkeypatch.setattr(sb, "sage_ouvert", lambda: False)
    monkeypatch.setattr(sb, "sages_orphelins", lambda: set())
    ouvertures = []
    monkeypatch.setattr(m, "_sage_garde", lambda *a, **k: ouvertures.append(a))
    monkeypatch.setitem(m._SAGE_GARDE, "fil", None)
    with pytest.raises(Fin):
        m.garder_sage_ouvert(tmp_path, lire_config=lambda: {"sage_import": {"fichier_entreprise": "X.SAI"}},
                             ouvrir=False)
    assert ouvertures == []
