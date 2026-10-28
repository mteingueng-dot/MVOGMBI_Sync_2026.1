import json
from datetime import date
from decimal import Decimal as D

from mvogmbi_sync.automatique import BLOQUEE, IMPORTEE, CompteRendu, EtatJour
from mvogmbi_sync.fournisseurs import IMPORTEE as FACTURE_IMPORTEE
from mvogmbi_sync.fournisseurs import Facture, Ligne, Registre, archiver_importees, archives
from mvogmbi_sync.rapports import _filtrer, lire_historique, noter_historique


def test_historique_des_traitements_dernier_etat(tmp_path):
    (tmp_path / "donnees").mkdir()
    (tmp_path / "donnees" / "journal_imports.csv").write_text(
        "Date et heure;Facture;Fichier d'entreprise;Lignes;Sous-total;Total;Code de retour;Résultat\n"
        "2026-10-20 01:02:03;Vente 2026-10-19;X.SAI;10;100.00;105.00;0;importée\n", encoding="utf-8-sig")
    cr = CompteRendu()
    cr.jours = [EtatJour(date(2026, 10, 25), BLOQUEE, "article non relié", 5, D("50.00"), D("2.50"), D("52.50"),
                         debut=date(2026, 10, 23), numero="Vente 2026-10-23/25")]
    noter_historique(tmp_path, cr)
    cr2 = CompteRendu()
    cr2.jours = [EtatJour(date(2026, 10, 25), IMPORTEE, "", 5, D("50.00"), D("2.50"), D("52.50"),
                          debut=date(2026, 10, 23), numero="Vente 2026-10-23/25")]
    noter_historique(tmp_path, cr2)
    suivi = lire_historique(tmp_path)
    assert suivi["Vente 2026-10-19"].taxes == D("5.00") and suivi["Vente 2026-10-19"].statut == "Facture importée"
    fds = suivi["Vente 2026-10-23/25"]
    assert (fds.journee, fds.statut, fds.ttc) == ("2026-10-23 → 2026-10-25", IMPORTEE, D("52.50"))  # dernier état


def test_simulation_pas_dans_l_historique(tmp_path):
    cr = CompteRendu(simulation=True)
    cr.jours = [EtatJour(date(2026, 10, 25), IMPORTEE)]
    noter_historique(tmp_path, cr)
    assert not (tmp_path / "donnees" / "historique_ventes.csv").exists()


def test_filtre_texte():
    lignes = [["2026-10-01", "Nourriture D'afrique", D("10.00")], ["2026-10-02", "Transport Exemple", D("5.00")]]
    assert _filtrer(lignes, "afrique") == [lignes[0]] and _filtrer(lignes, "") == lignes


def test_factures_fournisseurs_importees_archivees(tmp_path):
    registre = Registre(tmp_path)
    (tmp_path / "donnees" / "factures_fournisseurs").mkdir(parents=True)
    (tmp_path / "donnees" / "factures_fournisseurs" / "f.pdf").write_bytes(b"%PDF-1.4")
    facture = Facture("f.pdf", "abc", fournisseur_sage="Fournisseur Exemple", numero="14402", date_facture="2026-08-20",
                      lignes=[Ligne("Sac arachide", D("3"), D("60.00"), D("180.00"), numero_sage="B1",
                                    facteur=D("4.54"))], total=D("180.00"), etat=FACTURE_IMPORTEE)
    registre.factures.append(facture)
    registre.enregistrer()
    assert archiver_importees(tmp_path) == 1 and archiver_importees(tmp_path) == 0  # une seule fois
    (a,) = archives(tmp_path)
    assert a["numero"] == "14402" and a["fichier_archive"].endswith(".pdf")
    dossier = tmp_path / "donnees" / "archives" / "factures_fournisseurs" / "2026"
    assert sorted(p.suffix for p in dossier.iterdir()) == [".json", ".pdf", ".xlsx"]
    assert json.loads(next(dossier.glob("*.json")).read_text(encoding="utf-8"))["lignes"][0]["numero_sage"] == "B1"


class BaseFactice:
    def __init__(self, lignes, comptes):
        self.lignes, self.comptes, self.requetes = lignes, comptes, []

    def requete(self, sql, parametres=()):
        self.requetes.append((sql, list(parametres)))
        return self.comptes if "taccount" in sql else self.lignes


def test_statistiques_fournisseur_par_article_et_categorie():
    from decimal import Decimal as D

    from mvogmbi_sync.rapports import statistiques_tiers

    lignes = [{"n": "B1", "nom": "Bobolo", "lAcctId": 15220000, "nJournal": 7, "rec": 1, "dQty": 10, "dAmt": 70},
              {"n": "B1", "nom": "Bobolo", "lAcctId": 15220000, "nJournal": 17, "rec": 2, "dQty": 2, "dAmt": 14},
              {"n": "C1", "nom": "Riz", "lAcctId": 15270000, "nJournal": 7, "rec": 1, "dQty": 4, "dAmt": 44}]
    base = BaseFactice(lignes, [{"lId": 15270000, "sName": "Stock - Riz"}])
    entetes, r = statistiques_tiers(base, "fournisseur", "Grossiste", "Article", de="A", a="C9",
                                    categories={"1522": "Légumes Congelés"})
    assert entetes[:5] == ["N° Sage", "Article", "Catégorie", "Quantité", "Montant"]
    assert r[0][:7] == ["B1", "Bobolo", "Légumes Congelés", D(8), D("56.00"), D("7.00"), 2]  # achat − retour
    assert r[1][2] == "Riz" and r[-1][1] == "Total" and r[-1][4] == D("100.00")
    sql, parametres = base.requetes[0]
    assert "IN (7, 17)" in sql and parametres == ["Grossiste", "A", "C9"]  # plage d'articles
    _, r = statistiques_tiers(base, "fournisseur", "Grossiste", "Catégorie", categories={"1522": "Légumes Congelés"})
    assert [l[0] for l in r] == ["Légumes Congelés", "Riz", "Total"] and r[0][1] == 1


def test_filtre_categorie_des_statistiques():
    from mvogmbi_sync.rapports import comptes_de_categorie, statistiques_tiers

    comptes = [{"lId": 15220000, "sName": "Stock - Légumes Congelés"}, {"lId": 40220000, "sName": "Produit - X"},
               {"lId": 15270000, "sName": "Stock - Riz"}]
    base = BaseFactice([], comptes)
    assert comptes_de_categorie(base, "riz") == [15270000]
    assert comptes_de_categorie(base, "Légumes Congelés", {"4022": "Légumes Congelés"}) == [15220000, 40220000]
    statistiques_tiers(base, "client", "", "Article", categories={"4022": "Légumes Congelés"},
                       categorie="Légumes Congelés")
    sql, parametres = next(r for r in base.requetes if "titrline" in r[0])
    assert "l.lAcctId IN (15220000, 40220000)" in sql and "t.sName" not in sql and parametres == []


def test_statistiques_par_jour_et_date_de_peremption():
    from datetime import date, datetime
    from decimal import Decimal as D

    from mvogmbi_sync.fenetre_articles_clover import ligne_article
    from mvogmbi_sync.rapports import statistiques_tiers

    lignes = [{"n": "C1", "nom": "Riz", "lAcctId": 40270000, "nJournal": 8, "rec": 1, "dtJournal": datetime(2026, 10, 20),
               "dQty": 2, "dAmt": 20},
              {"n": "C1", "nom": "Riz", "lAcctId": 40270000, "nJournal": 8, "rec": 2, "dtJournal": datetime(2026, 10, 21),
               "dQty": 1, "dAmt": 10}]
    entetes, r = statistiques_tiers(BaseFactice(lignes, []), "client", "X", "Article par jour", categories={"4027": "Riz"})
    assert entetes[:3] == ["Date", "N° Sage", "Article"]
    assert [l[:2] for l in r[:2]] == [["2026-10-21", "C1"], ["2026-10-20", "C1"]] and r[-1][2] == "Total"
    a = {"id": "A", "name": "Riz", "price": 180, "priceType": "FIXED", "sku": "31/12/2027", "itemStock": {"quantity": 3}}
    assert ligne_article(a, {"FIXED": "Fixe"})[2] == D("1.80") and ligne_article(a, {})[6] == date(2027, 12, 31)
    assert ligne_article({**a, "sku": "4CotEcras150g"}, {})[6] is None  # pas une date : non affichée
