from decimal import Decimal as D

from mvogmbi_sync.articles_sage import ArticleSage, lire_articles_sage, reparer_texte
from mvogmbi_sync.correspondance import (AUCUN, AUTOMATIQUE, A_CONFIRMER, CONFIRME, ArticleClover,
                                         ecrire_correspondance, lire_confirmes, normaliser, rapprocher)

SAGE = [
    ArticleSage("B0000015", "Arachide Frais Du Village en kg", "Inventory", "4013"),
    ArticleSage("C0001522", "Milk Sere Ne 1kg 6-36", "Inventory", "4013"),
    ArticleSage("1991003019", "Meche Afro Kinky Curly Bulk Hair Mira T1B/BUG", "Inventory", "4023"),
    ArticleSage("B0000094", "Igname Blanc (YAM) en lb", "Inventory", "4016"),
    ArticleSage("P1", "Palm Milk 400g", "Inventory", "4013"),
    ArticleSage("P2", "Palm Milk 900g", "Inventory", "4013"),
]


def test_normaliser():
    assert normaliser("Arachide Depulpé  CMR, 1,8 Kg") == "arachide depulpe cmr 1.8kg"


def test_reparer_texte():
    assert reparer_texte("Arachide Depulpé CMR") == "Arachide Depulpé CMR"
    assert reparer_texte("Déjà correct") == "Déjà correct"


def test_lire_articles_sage(tmp_path):
    fichier = tmp_path / "Article.txt"
    fichier.write_bytes(
        b'33101,3,Inventory\r\n'
        b'".",".","Service","Chaque",0,0,0,0,5010,0,".","Chaque",\r\n'
        b'"B0000094","Igname Blanc (YAM) en lb","Inventory","Chaque",3.99,3.99,1516,4016,5016,5016,"Igname","Chaque",\r\n'
        b'"X1","Arachide Depulp\xc3\xa9","Inventory","Chaque",1,1,1513,4013,5013,5013,"A","Chaque",\r\n'
    )
    articles = lire_articles_sage(fichier)
    assert [(a.numero, a.description, a.compte_revenus) for a in articles] == [
        ("B0000094", "Igname Blanc (YAM) en lb", "4016"), ("X1", "Arachide Depulpé", "4013")]


def test_rapprocher_methodes():
    clover = [
        ArticleClover("c1", "Igname Blanc (YAM) en lb"),                                   # nom identique
        ArticleClover("c2", "Meche Afro Kinky Curly Mira", code="1991003019"),            # code-barres
        ArticleClover("c3", "Arachides Frais Du Village en kg", ventes_30j=D("1295.76")), # ressemblant
        ArticleClover("c4", "Perruque Curly Wave"),                                       # aucun
    ]
    res = {c.id_clover: c for c in rapprocher(clover, SAGE)}
    assert (res["c1"].statut, res["c1"].numero_sage, res["c1"].compte_revenus) == (AUTOMATIQUE, "B0000094", "4016")
    assert (res["c2"].statut, res["c2"].methode) == (AUTOMATIQUE, "Code-barres")
    assert (res["c3"].statut, res["c3"].numero_sage) == (A_CONFIRMER, "B0000015")
    assert res["c4"].statut == AUCUN


def test_formats_differents_penalises():
    (res,) = rapprocher([ArticleClover("c", "Palm Milk 400 g")], SAGE)
    assert res.numero_sage == "P1"  # 400g et non 900g
    (res,) = rapprocher([ArticleClover("c", "Milk Sere Ne 1kg 7-36")], SAGE)
    assert res.statut == A_CONFIRMER  # tailles différentes : jamais automatique


def test_lignes_confirmees_conservees(tmp_path):
    chemin = tmp_path / "correspondance.xlsx"
    clover = [ArticleClover("c3", "Arachides Frais Du Village en kg")]
    premiere = rapprocher(clover, SAGE)
    premiere[0].statut, premiere[0].numero_sage = CONFIRME, "C0001522"  # choix manuel du propriétaire
    ecrire_correspondance(premiere, chemin)
    (res,) = rapprocher(clover, SAGE, lire_confirmes(chemin))
    assert (res.statut, res.numero_sage, res.description_sage) == (CONFIRME, "C0001522", "Milk Sere Ne 1kg 6-36")
