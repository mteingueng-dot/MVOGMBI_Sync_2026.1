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
