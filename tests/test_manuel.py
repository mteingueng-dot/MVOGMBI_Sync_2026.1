from mvogmbi_sync import manuel

PAGE = ("<div class=\"sous\">MVOGMBI_Sync — Clover → Sage 50</div><ol>"
        "<li data-pages=''><span>1</span>Présentation</li><li data-pages='7'><span>2</span>Encaissements</li>"
        "<li data-pages='5,8'><span>3</span>Commercial</li><li data-pages=''><span>4</span>FAQ</li></ol>"
        "<section class='chapitre' data-pages=''><h1><span class='num'>1</span>Présentation</h1></section>"
        "<section class='chapitre' data-pages='7'><h1><span class='num'>2</span>Encaissements</h1>\n<p>x</p></section>"
        "<section class='chapitre' data-pages='5,8'><h1><span class='num'>3</span>Commercial</h1></section>"
        "<section class='chapitre' data-pages=''><h1><span class='num'>4</span>FAQ</h1></section>")


def test_manuel_filtre_et_renumerote():
    page = manuel.filtrer(PAGE, {0, 8}, "Manuel du profil « Employé »")
    assert "Encaissements" not in page
    assert "<span class='num'>2</span>Commercial" in page and "<span class='num'>3</span>FAQ" in page
    assert "<li><span>2</span>Commercial</li>" in page and "Manuel du profil « Employé »" in page
    assert manuel.tout_permis(PAGE, {0, 5, 7}) and not manuel.tout_permis(PAGE, {0, 5})
