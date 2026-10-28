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
    assert normaliser("Attieke Meme1kg") == normaliser("Attieke Meme 1kg")


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
    # Formats différents = articles différents : seul 6-36 existe dans Sage -> article à créer
    assert (res.statut, res.numero_sage) == (AUCUN, "")
    assert "créer" in res.methode and "C0001522" in res.suggestions


def test_confirmation_avec_autre_format_annulee(tmp_path):
    chemin = tmp_path / "correspondance.xlsx"
    clover = [ArticleClover("c", "Milk Sere Ne 1kg 7-36")]
    ligne = rapprocher(clover, SAGE)[0]
    ligne.statut, ligne.numero_sage = CONFIRME, "C0001522"  # confirmé par erreur sur 6-36
    ecrire_correspondance([ligne], chemin)
    (res,) = rapprocher(clover, SAGE, lire_confirmes(chemin))
    assert res.statut == AUCUN and "Confirmation annulée" in res.suggestions


def test_plusieurs_formats_sur_un_article_sans_format():
    sage = [ArticleSage("B0000134", "matembele", "Inventory", "4022")]
    clover = [ArticleClover("a", "Matembele 500g"), ArticleClover("b", "Matembele 1kg")]
    resultat = rapprocher(clover, sage)
    assert all(c.statut == A_CONFIRMER and "un article par format" in c.methode for c in resultat)


def test_numero_confirme_absent_de_la_liste_sage(tmp_path):
    chemin = tmp_path / "correspondance.xlsx"
    clover = [ArticleClover("c", "Perruque Curly Wave")]
    ligne = rapprocher(clover, SAGE)[0]
    ligne.statut, ligne.numero_sage = CONFIRME, "C0001644"  # article créé après l'export de la liste
    ecrire_correspondance([ligne], chemin)
    (res,) = rapprocher(clover, SAGE, lire_confirmes(chemin))
    assert (res.statut, res.numero_sage) == (A_CONFIRMER, "C0001644")


def test_lignes_confirmees_conservees(tmp_path):
    chemin = tmp_path / "correspondance.xlsx"
    clover = [ArticleClover("c3", "Arachides Frais Du Village en kg")]
    premiere = rapprocher(clover, SAGE)
    premiere[0].statut, premiere[0].numero_sage = CONFIRME, "C0001522"  # choix manuel du propriétaire
    ecrire_correspondance(premiere, chemin)
    (res,) = rapprocher(clover, SAGE, lire_confirmes(chemin))
    assert (res.statut, res.numero_sage, res.description_sage) == (CONFIRME, "C0001522", "Milk Sere Ne 1kg 6-36")


def test_confirmation_annulee_puis_article_cree_au_bon_format(tmp_path):
    chemin = tmp_path / "correspondance.xlsx"
    clover = [ArticleClover("c", "Milk Sere Ne 1kg 7-36")]
    ligne = rapprocher(clover, SAGE)[0]
    ligne.statut, ligne.numero_sage = CONFIRME, "C0001522"  # 6-36 : autre format
    ecrire_correspondance([ligne], chemin)
    sage = SAGE + [ArticleSage("C0001679", "Milk Sere Ne 1kg 7-36", "Inventory", "4013")]  # créé dans Sage
    (res,) = rapprocher(clover, sage, lire_confirmes(chemin))
    assert (res.statut, res.numero_sage) == (AUTOMATIQUE, "C0001679")


def test_lire_articles_sage_guillemets_et_retours_a_la_ligne(tmp_path):
    # Export Sage réel : guillemets non doublés et description coupée par un retour à la ligne
    fichier = tmp_path / "Article.txt"
    fichier.write_bytes(
        b'33101,3,Inventory\r\n'
        b'"C0001646","Meche X-Pression 3x Kids 28" 02","Inventory","Chaque",12.99,12.99,1523,4023,5023,5023,'
        b'"Meche X-Pression 3x Kids 28" 02","Chaque",\r\n'
        b'"C0001647","Meche X-Pression 3x Kids 28" 04\r\n'
        b'","Inventory","Chaque",12.99,12.99,1523,4023,5023,5023,"Meche X-Pression 3x Kids 28" 04\r\n'
        b'","Chaque",\r\n'
        b'"0103020131B\r\r\n","French Curl Braid Afro 22\'\' 3X 1B#","Inventory","Chaque",14.99,14.99,1523,4023,5023,5023,'
        b'"French","Chaque",\r\n'
    )
    articles = lire_articles_sage(fichier)
    assert [(a.numero, a.description, a.compte_revenus) for a in articles] == [
        ("C0001646", 'Meche X-Pression 3x Kids 28" 02', "4023"),
        ("C0001647", 'Meche X-Pression 3x Kids 28" 04', "4023"),
        ("0103020131B", "French Curl Braid Afro 22'' 3X 1B#", "4023"),
    ]


def test_numero_compte_sage():
    from mvogmbi_sync.base_sage import numero_compte

    assert numero_compte(40230000) == "4023"
    assert numero_compte("40140000") == "4014"
    assert numero_compte(0) == "" and numero_compte(None) == ""


def test_article_renomme_dans_clover_propose_le_nouveau_nom(tmp_path):
    from mvogmbi_sync.correspondance import (PERSONNALISE, RENOMME, lire_a_relier, memoriser_a_relier,
                                             proposer_renommes)

    # ventes : l'ancien ID (supprimé de Clover) et un montant saisi sans article ; mémorisés une seule fois
    a_relier = tmp_path / "articles_a_relier.csv"
    assert memoriser_a_relier(a_relier, [("OLD1", "Arachide Frais Village kg"), ("", "Article personnalisé")]) == 2
    assert memoriser_a_relier(a_relier, [("OLD1", "Arachide Frais Village kg")]) == 0
    assert [r[0] for r in lire_a_relier(a_relier)] == ["OLD1", "nom:article personnalise"]

    clover = [ArticleClover("NEW1", "Arachide Frais Du Village en kg"),        # nouveau nom (nouvel ID)
              ArticleClover("OLD1", "Arachide Frais Village kg"),              # ancien nom, supprimé
              ArticleClover("OLD2", "Milk Sere Ne 1kg 12"),                    # autre format : jamais relié
              ArticleClover("nom:article personnalise", "Article personnalisé")]
    resultat = rapprocher(clover, SAGE + [ArticleSage("C0001523", "Milk Sere Ne 1kg 12-36", "Inventory", "4013")])
    assert proposer_renommes(resultat, {"OLD1", "OLD2", "nom:article personnalise"}) >= 1
    par_id = {c.id_clover: c for c in resultat}
    ancien = par_id["OLD1"]
    assert (ancien.statut, ancien.numero_sage, ancien.methode) == (A_CONFIRMER, "B0000015", RENOMME)
    assert "Arachide Frais Du Village en kg" in ancien.suggestions
    assert par_id["nom:article personnalise"].methode == PERSONNALISE
    assert par_id["OLD2"].numero_sage != "C0001522"

