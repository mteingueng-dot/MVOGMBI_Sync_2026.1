from datetime import date
from decimal import Decimal as D

from mvogmbi_sync.correspondance import AUTOMATIQUE, CONFIRME, Correspondance, lire_correspondances
from mvogmbi_sync.creation_articles import (AUCUNE_TAXE, TAXES_DEFAUT, ComptesCategorie, NouvelArticle, TableCategories,
                                            choix_taxes, comptes_a_corriger, prix_vente, prochain_numero, proposer_table,
                                            relier_correspondance)
from mvogmbi_sync.fournisseurs import Facture, Ligne
from mvogmbi_sync.stock_clover import Journal, mettre_a_jour, receptions


def corr(statut, numero, id_clover, categorie="Conserves"):
    return Correspondance(statut, "x", categorie, D(0), numero, "", "", "", 100, "", "", id_clover)


def test_table_proposee_depuis_les_articles_relies():
    sage = [{"sPartCode": "C0001159", "lAcNAsset": 15320000, "lAcNRev": 40320000, "lAcNExp": 50320000,
             "lAcNVar": 50320000},
            {"sPartCode": "C0000002", "lAcNAsset": 15320000, "lAcNRev": 40320000, "lAcNExp": 50320000, "lAcNVar": 0},
            {"sPartCode": "B0000190", "lAcNAsset": 15180000, "lAcNRev": 40180000, "lAcNExp": 50180000, "lAcNVar": 0}]
    p = proposer_table([corr(CONFIRME, "C0001159", "a"), corr(AUTOMATIQUE, "C0000002", "b"),
                        corr(CONFIRME, "B0000190", "c"), corr("À confirmer", "B0000190", "d", "Riz")], sage)
    assert list(p) == ["Conserves"]  # « À confirmer » ne compte pas
    c = p["Conserves"]
    assert (c.prefixe, c.actif, c.produits, c.cmv, c.ecart) == ("C", "1532", "4032", "5032", "5032")  # écart = CMV
    assert ComptesCategorie("Riz", "C", "1527", "4027", "5027", "").ecart == "5027"
    assert c.problemes() == []
    assert ComptesCategorie("Riz", "C", "4027", "4027", "5027").problemes() == ["compte actif 4027 : un 15xx est attendu"]


def test_table_enregistree_sans_ecraser(tmp_path):
    table = TableCategories(tmp_path)
    assert table.completer({"Riz": ComptesCategorie("Riz", "C", "1527", "4027", "5027")}) == 1
    table.enregistrer()
    relue = TableCategories(tmp_path)
    relue.lignes["Riz"].prefixe = "B"
    assert relue.completer({"Riz": ComptesCategorie("Riz", "C", "1500", "4000", "5000")}) == 0
    assert relue.pour("Riz").prefixe == "B"


def test_numero_suivant_prix_et_taxes():
    existants = ["C0001159", "C0001160", "c0000005", "B0000190", "CLOVER_GIFT_CARD", "C12"]
    assert prochain_numero(existants, "C") == "C0001161"
    assert prochain_numero(existants, "B") == "B0000191"
    assert prochain_numero([], "V") == "V0000001"
    assert prix_vente(D("4.00")) == D("5.60") and prix_vente(D("2.99")) == D("4.19")
    choix = choix_taxes([{"id": "q", "name": "TVQ", "rate": 997500}, {"id": "p", "name": "TPS", "rate": 500000},
                         {"id": "n", "name": "NO_TAX_APPLIED", "rate": 0}])
    assert choix == {TAXES_DEFAUT: None, "TVQ + TPS": ["q", "p"], "TVQ": ["q"], "TPS": ["p"], AUCUNE_TAXE: ["n"]}


def article(**valeurs):
    base = dict(nom="Riz Parfumé 5kg", cout=D("10"), prix=D("14.00"), peremption=date(2027, 12, 31), categorie="Riz",
                id_categorie="K1", numero_sage="C0001161", description_sage="Riz Parfumé 5kg",
                comptes=ComptesCategorie("Riz", "C", "1527", "4027", "5027"))
    base.update(valeurs)
    return NouvelArticle(**base)


def test_controles_et_donnees_clover():
    a = article()
    assert a.problemes({"C0001160"}) == []
    assert a.donnees_clover() == {"name": "Riz Parfumé 5kg", "price": 1400, "priceType": "FIXED", "cost": 1000,
                                  "isRevenue": True, "hidden": False, "defaultTaxRates": True, "sku": "31/12/2027"}
    assert article(taxes=["p"], code="123", type_prix="PER_UNIT", unite="lb").donnees_clover()["unitName"] == "lb"
    assert article(taxes=["p"]).donnees_clover()["defaultTaxRates"] is False
    p = article(peremption=None, id_categorie="").problemes({"c0001161"})
    assert "UGS : date de péremption obligatoire" in p and "catégorie Clover à choisir" in p
    assert "le n° Sage « C0001161 » existe déjà" in p
    assert article(creer_clover=False, peremption=None).problemes(set()) == []  # Sage seulement
    s = article().article_sage()
    assert (s.numero, s.actif, s.produits, s.cmv, s.ecart) == ("C0001161", "1527", "4027", "5027", "5027")


def test_service_cree_seulement_dans_sage():
    """Règle du propriétaire (2026-10-30) : un service se crée dans Sage seulement, jamais dans Clover."""
    service = dict(nom="Livraison", numero_sage="S0000001", description_sage="Livraison", service=True,
                   compte_charges="5700", comptes=None, peremption=None)
    assert "un service se crée seulement dans Sage, pas dans Clover" in article(**service).problemes(set())
    assert article(**service, creer_clover=False).problemes(set()) == []
    a = article(**service, creer_clover=False).article_sage()
    assert (a.numero, a.service, a.cmv) == ("S0000001", True, "5700")


def test_lien_ajoute_a_la_correspondance(tmp_path):
    chemin = tmp_path / "correspondance_articles.xlsx"
    a = article(id_clover="NEW1")
    relier_correspondance(chemin, a)
    relier_correspondance(chemin, a)  # jamais en double
    (c,) = lire_correspondances(chemin)
    assert (c.statut, c.numero_sage, c.id_clover, c.categorie_clover) == (CONFIRME, "C0001161", "NEW1", "Riz")


class FauxClover:
    def __init__(self):
        self.stocks = {"A": D("-3"), "B": D("5")}
        self.couts, self.reglages = {}, []

    def stock(self, i):
        return self.stocks.get(i, D(0))

    def regler_stock(self, i, q):
        self.stocks[i] = q
        self.reglages.append((i, q))

    def regler_cout(self, i, c):
        self.couts[i] = c


def test_stock_et_cout_clover_apres_import(tmp_path):
    f = Facture("a.pdf", "e", fournisseur_sage="Grossiste", numero="14402", lignes=[
        Ligne("Riz 25 lb", D(2), D("30"), D("60.00"), numero_sage="C1", facteur=D(10), confirme=True),
        Ligne("Riz 25 lb", D(1), D("33"), D("33.00"), numero_sage="C1", facteur=D(10), confirme=True),
        Ligne("Huile", D(4), D("5"), D("20.00"), numero_sage="C2", confirme=True),
        Ligne("Sans lien", D(1), D("1"), D("1.00")),
        Ligne("Transport", D(1), D("9"), D("9.00"), nature="frais", numero_sage="C9")])
    assert [(r.numero_sage, r.quantite, r.cout) for r in receptions(f)] == [("C1", D(30), D("3.10")),
                                                                           ("C2", D(4), D("5.00"))]
    client = FauxClover()
    correspondances = [corr(CONFIRME, "C1", "A"), corr(AUTOMATIQUE, "C2", "B"), corr(CONFIRME, "C2", "B2"),
                       corr("À confirmer", "C1", "Z")]
    messages = mettre_a_jour(client, f, correspondances, Journal(tmp_path))
    assert client.stocks["A"] == D(27) and client.couts == {"A": D("3.10"), "B": D("5.00"), "B2": D("5.00")}
    assert client.stocks["B"] == D(5)  # deux articles Clover pour C2 : stock non touché
    assert "stock NON modifié" in messages[1]
    assert mettre_a_jour(client, f, correspondances, Journal(tmp_path)) == [
        "C1 : déjà ajouté au stock Clover", "C2 : déjà ajouté au stock Clover"]
    assert client.reglages == [("A", D(27))]  # jamais deux fois


def test_comptes_a_corriger_selon_la_table(tmp_path):
    table = TableCategories(tmp_path)
    table.lignes = {"Conserves": ComptesCategorie("Conserves", "C", "1532", "4032", "5032"),
                    "Riz": ComptesCategorie("Riz", "C", "1527", "4027", "5027")}

    def art(n, a, r, e, v):
        return {"sPartCode": n, "sName": n, "lAcNAsset": a * 10000, "lAcNRev": r * 10000, "lAcNExp": e * 10000,
                "lAcNVar": v * 10000}

    sage = [art("C1", 1532, 4032, 5032, 5032),  # conforme
            art("C2", 1532, 4032, 5032, 0),     # écart vide
            art("C3", 1513, 4013, 5013, 5013),  # relié à « Riz » dans Clover : tout est à changer
            art("C4", 1527, 4011, 5027, 5027),  # sans lien : catégorie qui s'accorde avec le plus de comptes
            art("C5", 1999, 4999, 5999, 5999)]  # catégorie inconnue
    corrections, inconnus = comptes_a_corriger(sage, table, [corr(CONFIRME, "C3", "x", "Riz")])
    assert inconnus == 1
    assert [(c.numero, c.categorie, c.source, c.changements) for c in corrections] == [
        ("C2", "Conserves", "comptes de l'article", ["Écart"]),
        ("C3", "Riz", "catégorie Clover", ["Actif", "Produits", "CMV", "Écart"]),  # seul indice : Clover
        ("C4", "Riz", "comptes de l'article", ["Produits"])]  # actif et CMV de Riz : seul le produit change
    assert corrections[0].attendu == ("1532", "4032", "5032", "5032")


def test_couts_clover_sans_valeur_aberrante():
    from mvogmbi_sync.couts_clover import A_METTRE_A_JOUR, A_VERIFIER, ABERRANT, SANS_CUMP, proposer
    from mvogmbi_sync.couts_sage import CoutSage

    def cs(n, cump):
        return CoutSage(n, n, None if cump is None else D(cump), D(1), D(1))

    clover = [{"id": i, "name": i, "price": prix, "cost": cout} for i, prix, cout in (
        ("ok", 1000, 500), ("egal", 1000, 520), ("haut", 100, 50), ("bas", 1000, 500), ("vide", 1000, 500),
        ("cher", 1000, 500), ("double1", 1000, 500), ("double2", 2000, 500), ("saut", 1000, 100))]
    liens = {"ok": "A", "egal": "B", "haut": "C", "bas": "D", "vide": "E", "cher": "F", "double1": "G",
             "double2": "G", "saut": "H"}
    couts = {"A": cs("A", "5.4321"), "B": cs("B", "5.2"), "C": cs("C", "6"), "D": cs("D", "0.2"), "E": cs("E", None),
             "F": cs("F", "10.5"), "G": cs("G", "6"), "H": cs("H", "4")}
    propositions, a_jour = proposer(clover, liens, couts)
    etats = {p.id_clover: p.etat for p in propositions}
    assert a_jour == 1 and "egal" not in etats
    assert etats == {"ok": A_METTRE_A_JOUR, "haut": ABERRANT, "bas": ABERRANT, "vide": SANS_CUMP, "cher": A_VERIFIER,
                     "double1": A_VERIFIER, "double2": A_VERIFIER, "saut": A_VERIFIER}
    ok = next(p for p in propositions if p.id_clover == "ok")
    assert ok.cump == D("5.43") and ok.permis and ok.cochee_par_defaut
    assert not any(p.permis for p in propositions if p.etat in (ABERRANT, SANS_CUMP))



def test_categorie_selon_la_majorite_des_comptes(tmp_path):
    table = TableCategories(tmp_path)
    table.lignes = {"Fruits & Légumes": ComptesCategorie("Fruits & Légumes", "B", "1517", "4017", "5017"),
                    "Jus & Bières": ComptesCategorie("Jus & Bières", "C", "1520", "4020", "5020")}
    oignon = {"sPartCode": "O1", "sName": "Oignon", "lAcNAsset": 15200000, "lAcNRev": 40170000,
              "lAcNExp": 50170000, "lAcNVar": 50170000}
    (c,), _ = comptes_a_corriger([oignon], table, [corr(CONFIRME, "O1", "x", "Fruits & Légumes")])
    assert (c.categorie, c.changements, c.attendu[0]) == ("Fruits & Légumes", ["Actif"], "1517")
