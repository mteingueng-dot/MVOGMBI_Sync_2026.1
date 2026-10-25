from mvogmbi_sync.verification_comptes import ComptesArticle, comptes_attendus, ecrire_anomalies, verifier


def article(numero, actif, produits, cmv):
    return ComptesArticle(numero, f"Article {numero}", actif, produits, cmv)


def test_comptes_attendus():
    assert comptes_attendus("1514") == ("4014", "5014")
    assert comptes_attendus("1020") is None


def test_verification(tmp_path):
    anomalies = verifier([
        article("OK", "1514", "4014", "5014"),         # conforme
        article("SANS", "1529", "", "5029"),           # bloquant
        article("FRUIT", "1520", "4017", "5020"),      # actif probablement faux
        article("CMV", "1514", "4014", "5013"),        # CMV incohérent
        article("ESS", "1020", "4200", "5200"),        # actif hors stock
    ], {"4029": "Produit des Ventes - Viandes & Volailles", "1517": "Stock - Fruits & Légumes"})
    par_numero = {x.article.numero: x for x in anomalies}
    assert "OK" not in par_numero
    assert anomalies[0].article.numero == "SANS" and anomalies[0].bloquante
    assert par_numero["SANS"].proposition == "Produits : 4029 Produit des Ventes - Viandes & Volailles"
    assert "1517 Stock - Fruits & Légumes" in par_numero["FRUIT"].proposition
    assert par_numero["CMV"].proposition == "CMV -> 5014"
    assert not par_numero["ESS"].bloquante
    assert ecrire_anomalies(anomalies, tmp_path / "comptes.xlsx").exists()
