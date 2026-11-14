"""Réglages communs des tests."""
import time
import tkinter

import pytest

from mvogmbi_sync import utilisateurs

# Création d'une fenêtre Tk : sur ce poste, Tcl échoue parfois au hasard à lire ses propres fichiers
# (« Can't find a usable init.tcl / tk.tcl », fichiers tenus un instant par l'antivirus) ; le test échouait alors
# sans rapport avec le code. La création est réessayée quelques fois avant d'abandonner (version 1.0.14).
_INIT_TK = tkinter.Tk.__init__
ESSAIS_TK = 6


def _tk_patient(self, *args, **kwargs):
    for essai in range(ESSAIS_TK):
        try:
            return _INIT_TK(self, *args, **kwargs)
        except tkinter.TclError:
            if essai == ESSAIS_TK - 1:
                raise
            time.sleep(0.3 * (essai + 1))


tkinter.Tk.__init__ = _tk_patient


@pytest.fixture(autouse=True)
def _empreintes_rapides(monkeypatch):
    """600 000 tours de PBKDF2 par mot de passe rendraient les tests très lents : 1 000 tours suffisent ici
    (le test des empreintes vérifie le vrai nombre de tours)."""
    monkeypatch.setattr(utilisateurs, "ITERATIONS", 1_000)
