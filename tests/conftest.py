"""Réglages communs des tests."""
import pytest

from mvogmbi_sync import utilisateurs


@pytest.fixture(autouse=True)
def _empreintes_rapides(monkeypatch):
    """600 000 tours de PBKDF2 par mot de passe rendraient les tests très lents : 1 000 tours suffisent ici
    (le test des empreintes vérifie le vrai nombre de tours)."""
    monkeypatch.setattr(utilisateurs, "ITERATIONS", 1_000)
