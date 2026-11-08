"""Récapitulatif des traitements (demande du propriétaire du 2026-11-08 : « à tout moment je dois savoir quand un
traitement a eu lieu dans le temps »)."""

from types import SimpleNamespace

import pytest

from mvogmbi_sync import traitements as tr


def test_un_traitement_note_une_fois_avec_debut_fin_et_resultat(tmp_path, monkeypatch):
    monkeypatch.delenv("MVOGMBI_LANCE_PAR", raising=False)
    with tr.suivre("Encaissements dans Sage", tmp_path, "Application", "Gérant") as etat:
        with tr.suivre("Import dans Sage", tmp_path):  # lancé dans un autre : pas noté une 2e fois
            pass
        etat["detail"] = "3 dépôt(s)"
    with pytest.raises(RuntimeError):
        with tr.suivre("Paie traitée dans Sage", tmp_path, "Web", "Comptable"):
            raise RuntimeError("Sage ne répond pas")
    liste = tr.lire(tmp_path)
    assert [x.nom for x in liste].count("Import dans Sage") == 0 and len(liste) == 2
    encaissement = next(x for x in liste if x.nom == "Encaissements dans Sage")
    assert encaissement.personne == "Gérant" and encaissement.resultat == "Terminé"
    assert encaissement.detail == "3 dépôt(s)" and encaissement.fin >= encaissement.debut and encaissement.duree
    paie = next(x for x in liste if x.nom.startswith("Paie"))
    assert paie.resultat == "Échec : Sage ne répond pas" and paie.origine == "Web"
    assert tr.filtrer(liste, nom="Paie traitée dans Sage") == [paie]


def test_personne_du_moteur_et_anciennes_nuits(tmp_path, monkeypatch):
    monkeypatch.setenv("MVOGMBI_LANCE_PAR", "Gérant")
    monkeypatch.setenv("MVOGMBI_ORIGINE", "Application")
    assert tr.personne_courante() == "Gérant" and tr.origine_courante("Nuit") == "Application"
    assert tr.duree(5) == "5 s" and tr.duree(125) == "2 min 05 s" and tr.duree(3700) == "1 h 01 min"
    assert tr.nom_commande(["x.exe", "encaisser-bureau"]) == "Encaissements dans Sage"
    assert tr.nom_commande(["x.exe", "garder-sage"]) is None
    (tmp_path / "donnees").mkdir()
    (tmp_path / "donnees" / "journal_automatique.log").write_text(
        "\n===== Exécution du 2026-10-25 02:12:05 =====\n02:12:05 Lecture de Sage…\n02:14:42 Aucune facture.\n"
        "PROBLÈME : article non relié\n\n===== Exécution du 2026-10-26 02:10:00 =====\nERREUR : panne\n",
        encoding="utf-8")
    nuits = tr.lire(tmp_path)
    assert [x.debut for x in nuits] == ["2026-10-26 02:10:00", "2026-10-25 02:12:05"]
    assert nuits[1].duree == "2 min 37 s" and nuits[1].resultat == "Terminé avec 1 problème(s)"
    assert nuits[0].resultat == "Échec : panne" and nuits[0].origine == "Nuit"


def test_journal_des_operations_web_affiche_le_recapitulatif(tmp_path, monkeypatch):
    from mvogmbi_sync.web import consultations

    monkeypatch.delenv("MVOGMBI_LANCE_PAR", raising=False)
    with tr.suivre("Import dans Sage", tmp_path, "Application", "Gérant"):
        pass
    ctx = SimpleNamespace(racine=tmp_path)
    from datetime import date
    sections = consultations._journal(ctx, {"du": date(2000, 1, 1), "au": date(2100, 1, 1)})
    assert sections[0].titre == "Récapitulatif des traitements" and sections[0].lignes[0][3] == "Import dans Sage"
    autres = consultations._journal(ctx, {"du": date(2000, 1, 1), "au": date(2100, 1, 1),
                                          "affichage": "Toutes les opérations"})
    assert autres[0].titre == "Journal des opérations"


# --------------------------------------------------------------------------------------------- opérations journalières
def _historique():
    from datetime import datetime

    return {"ventes": [{"dtDate": datetime(2026, 11, 6), "f": "Vente 2026-11-05", "client": "Client Ventes", "m": 1500}],
            "clients": [{"dtDate": datetime(2026, 11, 7), "nTranType": 1, "f": "Vente 2026-11-05", "piece": "12",
                         "nom": "Client Ventes", "dAmount": -1400}],
            "fournisseurs": [{"dtDate": datetime(2026, 11, 6), "nTranType": 0, "f": "F-100", "piece": "F-100",
                              "nom": "Fournisseur A", "dAmount": 885.95},
                             {"dtDate": datetime(2026, 11, 7), "nTranType": 1, "f": "F-100", "piece": "Chq 3",
                              "nom": "Fournisseur A", "dAmount": -885.95},
                             {"dtDate": datetime(2026, 10, 2), "nTranType": 0, "f": "F-090", "piece": "F-090",
                              "nom": "Fournisseur B", "dAmount": 50}]}


def test_operations_journalieres_et_moment_du_traitement(tmp_path, monkeypatch):
    from datetime import date
    from decimal import Decimal

    from mvogmbi_sync import operations_journalieres as oj

    monkeypatch.setenv("MVOGMBI_LANCE_PAR", "Gérant")
    monkeypatch.delenv("MVOGMBI_ORIGINE", raising=False)
    (tmp_path / "donnees").mkdir()
    (tmp_path / "donnees" / "journal_imports.csv").write_text(
        "Date et heure;Facture;Fichier d'entreprise;Lignes;Sous-total;Total;Code de retour;Résultat\n"
        "2026-11-06 02:40:00;Vente 2026-11-05;X.SAI;10;1500;1600;0;importée\n", encoding="utf-8-sig")
    oj.noter(tmp_path, oj.ENCAISSEMENT, "2026-11-07", "Dépôt du 2026-11-07", "Vente 2026-11-05", "Client Ventes", 1400)
    oj.noter(tmp_path, oj.ACHAT, "2026-11-06", "F-100", "F-100", "Fournisseur A", Decimal("885.95"))
    ops = oj.lire(tmp_path, _historique())
    assert [o.genre for o in ops][:2] == [oj.ENCAISSEMENT, oj.PAIEMENT] and len(ops) == 5
    par_genre = {(o.genre, o.reference): o for o in ops}
    assert par_genre[(oj.VENTE, "Vente 2026-11-05")].traite_le == "2026-11-06 02:40:00"
    encaissement = par_genre[(oj.ENCAISSEMENT, "12")]
    assert encaissement.par == "Gérant" and encaissement.traite_le and encaissement.montant == Decimal("1400")
    assert par_genre[(oj.ACHAT, "F-100")].traite_le and not par_genre[(oj.PAIEMENT, "Chq 3")].traite_le
    semaine = oj.filtrer(ops, date(2026, 11, 2), date(2026, 11, 8))
    assert len(semaine) == 4
    assert [o.genre for o in oj.filtrer(semaine, genres=[oj.ACHAT])] == [oj.ACHAT]
    assert len(oj.filtrer(semaine, etat="Saisies dans Sage")) == 1
    assert oj.filtrer(semaine, texte="fournisseur a")[0].tiers == "Fournisseur A"
    jours = oj.par_jour(semaine)
    assert jours[0][:2] == ["2026-11-07", "samedi"] and jours[0][4] == Decimal("1400") and jours[0][7] == 1
    assert dict((g, n) for g, n, _m in oj.totaux(semaine)) == {oj.VENTE: 1, oj.ACHAT: 1, oj.ENCAISSEMENT: 1,
                                                                 oj.PAIEMENT: 1}


def test_navigation_des_periodes():
    from datetime import date

    from mvogmbi_sync import operations_journalieres as oj

    jour = date(2026, 11, 8)  # un dimanche
    assert oj.bornes("Cette semaine", jour) == (date(2026, 11, 2), date(2026, 11, 8))
    assert oj.bornes("Mois dernier", jour) == (date(2026, 10, 1), date(2026, 10, 31))
    assert oj.decaler(date(2026, 11, 1), date(2026, 11, 30), -1) == (date(2026, 10, 1), date(2026, 10, 31))
    assert oj.decaler(date(2026, 1, 1), date(2026, 1, 31), -1) == (date(2025, 12, 1), date(2025, 12, 31))
    assert oj.decaler(date(2026, 11, 2), date(2026, 11, 8), 1) == (date(2026, 11, 9), date(2026, 11, 15))
    assert oj.decaler(date(2026, 1, 1), date(2026, 12, 31), -1) == (date(2025, 1, 1), date(2025, 12, 31))
    assert oj.decaler(date(2026, 11, 8), date(2026, 11, 8), -1) == (date(2026, 11, 7), date(2026, 11, 7))


def test_page_web_des_operations_journalieres(tmp_path, monkeypatch):
    import time
    from types import SimpleNamespace

    from mvogmbi_sync.web import pages_rapports_web as w

    class Requete:
        def __init__(self, q):
            self.query = q

        def valeurs(self, nom):
            return ["Achat"] if nom == "type" else []

    app = SimpleNamespace(memoire={"historique_sage": (time.time(), _historique())})
    ctx = SimpleNamespace(racine=tmp_path, app=app, absents=set(),
                          req=Requete({"periode": "Personnalisée", "du": "2026-11-02", "au": "2026-11-08"}))
    monkeypatch.setattr(w, "onglets", lambda actif, c=None: "")
    monkeypatch.setattr(w, "page", lambda c, titre, corps: corps)
    corps = w.operations_journalieres(ctx).corps
    corps = corps if isinstance(corps, str) else corps.decode("utf-8")
    assert "F-100" in corps and "Vente 2026-11-05" not in corps.split("<table")[1]
    assert "du=2026-10-26" in corps and "du=2026-11-09" in corps  # ◀ ▶ : semaine précédente et suivante
