"""Serveur web : une page n'attend jamais l'ouverture de Sage (demande du propriétaire du 2026-11-06)."""
import time

import pytest

from mvogmbi_sync import __main__ as m


def test_page_web_n_attend_jamais_sage(monkeypatch):
    appels = []
    monkeypatch.setattr(m, "_lire_sage", lambda *a, **k: appels.append(a) or time.sleep(5))
    monkeypatch.setitem(m.SURVEILLANCE_SAGE, "active", True)
    monkeypatch.setitem(m.SURVEILLANCE_SAGE, "pret", {})
    m.SURVEILLANCE_SAGE["reveil"].clear()
    debut = time.time()
    with pytest.raises(RuntimeError, match="ne répond pas"):
        m.lire_sage({"sage_import": {"fichier_entreprise": "X.SAI"}}, lambda b: 1, ouvrir=False)
    assert time.time() - debut < 0.5 and not appels           # aucune tentative d'ouverture depuis la page
    assert m.SURVEILLANCE_SAGE["reveil"].is_set()             # la surveillance de fond est réveillée

    class Base:
        def requete(self, *_):
            return [{"n": 1}]

    m.SURVEILLANCE_SAGE["pret"]["X.SAI"] = True                # base ouverte par la surveillance : lecture directe
    monkeypatch.setattr(m, "base_partagee", lambda *_: Base())
    assert m.lire_sage({"sage_import": {"fichier_entreprise": "X.SAI"}}, lambda b: b.requete("SELECT 1"),
                       ouvrir=False) == [{"n": 1}]
    assert not appels


def test_textes_longs_coupes_dans_les_tableaux():
    """Constat du 2026-11-06 (page Rapprochement) : une description très longue poussait les montants hors de la zone."""
    from mvogmbi_sync.web.export_web import couper_textes_longs

    long = "VRW Virement Interac de / " + "X" * 80
    html = (f"<table><tr><td class='n'>12,00 $</td><td><a href='?m=1'>{long}</a></td>"
            f"<td><input name='q' value='{long}'></td></tr></table>")
    sortie = couper_textes_longs(html)
    assert f"<td title='{long}'><div class='coupe'><a href='?m=1'>{long}</a></div></td>" in sortie
    assert "<td class='n'>12,00 $</td>" in sortie                    # court : inchangé
    assert f"<td><input name='q' value='{long}'></td>" in sortie      # champ de saisie : jamais touché
    assert couper_textes_longs(sortie) == sortie                       # une seule fois
