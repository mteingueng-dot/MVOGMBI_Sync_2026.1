from dataclasses import fields

from mvogmbi_sync import robot_tiers as rt


def test_champs_de_la_fiche_tiers():
    noms = {f.name for f in fields(rt.FicheTiers)}
    assert noms == set(rt.CHAMPS) == set(rt.LIBELLES)
    assert rt.CHAMPS["nom"] == 26 and rt.GENRES["fournisseurs"][3] == "tvendor"
    assert rt._simple("Ce client utilise mes &numéros") == "ce client utilise mes numeros"