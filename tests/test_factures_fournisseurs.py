from datetime import date
from decimal import Decimal as D

from mvogmbi_sync.factures_fournisseurs import (LigneFournisseur, convertir, facteur_propose, lire_date, lire_texte,
                                                montant)

# Texte inventé, au format du fournisseur (aucune vraie facture dans le dépôt public)
CHAMPS = """Produits des Champs
3400 Boulevard Losch, Suite 28 FACTURE No : 999001
T. (450) 812-8686 Date Facture : 2026-10-02
CODE PRODUIT DESCRIPTION COMMANDÉ EXPÉDIÉ PRIX UNITÉ UNITÉ TOTAL
113 Produit Test Coco 12/276 g 12 un 12 un 27.800$ Ca 27.80$
113 1 Ca 1 Ca
273 Produit Test Chips 24/85 g 48 un 0 un 28.600$ Ca 0.00$TX
273 2 Ca Ca
1109 Fromage Test 1/5 kg 5 kg 5.00 kg 113.050$ Ca 113.05$
Note pour cette commande Sous-total :non taxable : 140.85$
Consignes : 0.00$
TPS 0.00$
$30 seront imposés pour chaque chèque refusé. TVQ 0.00$
Total à payer : CAD 140.85$
"""


def test_montants_et_dates():
    assert montant("$1,751.20") == D("1751.20")
    assert montant("1 200,00 $") == D("1200.00")
    assert montant("27.800$") == D("27.800")
    assert lire_date("22-Oct-2026") == date(2026, 10, 22)
    assert lire_date("Août 20, 2026") == date(2026, 8, 20)
    assert lire_date("31/12/2025") == date(2025, 12, 31)
    assert lire_date("2026-09-30") == date(2026, 9, 30)


def test_modele_produits_des_champs():
    f = lire_texte(CHAMPS, "essai.pdf")
    assert (f.modele, f.numero, f.date_facture) == ("Produits des Champs", "999001", date(2026, 10, 2))
    assert [(l.code, l.quantite, l.montant) for l in f.lignes] == [("113", D("1"), D("27.80")),
                                                                    ("1109", D("1.000"), D("113.05"))]
    assert f.fiable, f.controles()


def test_facture_incoherente_signalee():
    f = lire_texte(CHAMPS.replace("Total à payer : CAD 140.85$", "Total à payer : CAD 150.00$"), "essai.pdf")
    assert not f.fiable
    assert any("total" in p for p in f.controles())


def test_conditionnement():
    assert facteur_propose("Colombina Max Coco 12/276 g") == 12
    assert facteur_propose("MR NAGA 36 x 190g") == 36
    assert facteur_propose("LEFFE BRUNE 4X6 0,330 L BOTTLE") == 24
    assert facteur_propose("Bobolo - Bâton de Manioc Congelé - (15 x 1.5 kg)") == 15
    assert facteur_propose("La Poblanita White Family Pack Tortilla 6/5 Lb") == 6
    assert facteur_propose("Okra") is None
    quantite, prix = convertir(LigneFournisseur("Coco 12/276 g", D("1"), D("27.80"), D("27.80")), D("12"))
    assert (quantite, prix) == (D("12.000"), D("2.3167"))


def test_ecarter_une_facture(tmp_path):
    from mvogmbi_sync.fournisseurs import Facture, Registre, empreinte

    dossier = tmp_path / "donnees" / "factures_fournisseurs"
    dossier.mkdir(parents=True)
    photo = dossier / "photo.jpeg"
    photo.write_bytes(b"photo de facture")
    registre = Registre(tmp_path)
    assert registre.nouveaux_fichiers() == [photo]
    facture = Facture(photo.name, empreinte(photo))
    registre.factures.append(facture)
    rangee = registre.ecarter(facture)
    assert rangee == dossier / "ecartees" / "photo.jpeg" and rangee.read_bytes() == b"photo de facture"
    assert not photo.exists() and Registre(tmp_path).factures == []
    assert registre.nouveaux_fichiers() == []  # une facture écartée n'est pas relue


def test_numero_deja_dans_sage():
    from mvogmbi_sync.import_achats import meme_numero

    assert meme_numero("FA-104202", "104202")
    assert meme_numero("A0084707", "a0084707")
    assert not meme_numero("11264", "1264")      # un chiffre de plus : autre facture
    assert not meme_numero("12", "FA-12")         # numéros trop courts : pas de rapprochement


def test_bloc_achat_conditionnement_et_taxes():
    from mvogmbi_sync.fournisseurs import Facture, Ligne
    from mvogmbi_sync.import_achats import bloc_achat

    f = Facture("essai.pdf", "x", fournisseur_sage="Fournisseur Test", numero="9001", date_facture="2026-10-02",
                sous_total=D("207.80"), tps=D("1.39"), tvq=D("2.77"), total=D("211.96"))
    f.lignes = [Ligne("Sac 10lbs", D("3"), D("60"), D("180.00"), numero_sage="B0000015", facteur=D("4.536")),
                Ligne("Chips 24/85 g", D("1"), D("27.80"), D("27.80"), taxable=True, numero_sage="C0000001",
                      facteur=D("24"))]
    lignes = bloc_achat(f)
    assert lignes[0] == "<PurInvoice>" and lignes[1] == '"Fournisseur Test"'
    assert lignes[2] == '"2","","9001","10-02-2026","211.96","0.00","0","0","0.00"'
    assert lignes[3] == '"B0000015","13.6080","13.2275","180.00"'
    assert lignes[4] == ('"C0000001","24.0000","1.1583","27.80","TPS/TVH","0","1","5.00","1.39",'
                         '"TVQ","0","1","9.975","2.77"')



def test_facture_prete_deja_dans_sage_archivee_et_retiree(tmp_path):
    from mvogmbi_sync.fournisseurs import (A_VERIFIER, PRETE, Facture, Registre, archiver_pretes_deja_dans_sage,
                                           archives, empreinte)

    class Base:  # Sage : la facture « FA-104202 » a été saisie à la main pour ce fournisseur
        def requete(self, sql, parametres=()):
            if "FROM tvendor" in sql:
                return [{"lId": 7, "sName": "Nourriture D'afrique"}]
            return [{"sSource": "FA-104202 "}] if parametres == (7,) else []

    registre = Registre(tmp_path)
    registre.dossier.mkdir(parents=True)
    (registre.dossier / "a.pdf").write_bytes(b"%PDF a")
    (registre.dossier / "b.pdf").write_bytes(b"%PDF b")
    registre.factures = [
        Facture("a.pdf", "e1", fournisseur_sage="Nourriture D'afrique", numero="104202", date_facture="2026-10-20",
                total=D("50"), etat=PRETE),
        Facture("b.pdf", empreinte(registre.dossier / "b.pdf"), fournisseur_sage="Nourriture D'afrique", numero="104202", date_facture="2026-10-20",
                etat=A_VERIFIER),  # pas encore prête : laissée à vérifier
    ]
    registre.enregistrer()
    (archivee,) = archiver_pretes_deja_dans_sage(tmp_path, Base())
    assert archivee.fichier == "a.pdf"
    relu = Registre(tmp_path)
    assert [f.fichier for f in relu.factures] == ["b.pdf"]
    assert not (registre.dossier / "a.pdf").exists() and (registre.dossier / "b.pdf").exists()
    assert relu.nouveaux_fichiers() == []  # le fichier archivé n'est pas relu comme nouveau
    (a,) = archives(tmp_path)
    assert a["etat"] == "Déjà dans Sage" and a["fichier_archive"].endswith(".pdf")
