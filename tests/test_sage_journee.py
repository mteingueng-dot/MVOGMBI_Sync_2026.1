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
