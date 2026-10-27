import json

import pytest

from mvogmbi_sync.utilisateurs import ADMIN, UTILISATEURS, ErreurUtilisateur, Registre


def test_premier_admin_connexion_et_mot_de_passe_jamais_garde(tmp_path):
    r = Registre(tmp_path)
    assert not r.existe()
    r.ajouter("  Médard  ", ADMIN, "secret123")
    r.enregistrer()
    texte = (tmp_path / "donnees" / "utilisateurs.json").read_text(encoding="utf-8")
    assert "secret123" not in texte and "Médard" in texte
    r = Registre(tmp_path)
    assert r.verifier("médard", "secret123").est_admin  # nom sans tenir compte des majuscules
    assert r.verifier("Médard", "mauvais") is None
    assert "échec : Médard" in (tmp_path / "donnees" / "journal_connexions.log").read_text(encoding="utf-8")


def test_pages_par_profil(tmp_path):
    r = Registre(tmp_path)
    admin = r.ajouter("Admin", ADMIN, "secret123")
    caisse = r.ajouter("Awa", "Employé", "caisse1")
    compta = r.ajouter("Paul", "Comptable", "compta1")
    assert UTILISATEURS in r.pages(admin) and "clover" in r.pages(admin)
    assert r.pages(caisse) == {"accueil", "tableau", "guide", "faq"}
    assert "rapprochement" in r.pages(compta) and "sage" not in r.pages(compta)
    r.definir_profil("Employé", ["tableau", "encaissements"])
    assert r.pages(caisse) == {"accueil", "tableau", "encaissements"}  # l'accueil reste toujours


def test_toujours_un_administrateur_actif(tmp_path):
    r = Registre(tmp_path)
    r.ajouter("Admin", ADMIN, "secret123")
    r.ajouter("Awa", "Employé", "caisse1")
    for action in (lambda: r.supprimer("Admin"), lambda: r.activer("Admin", False),
                   lambda: r.changer_profil("Admin", "Employé"), lambda: r.definir_profil(ADMIN, []),
                   lambda: r.supprimer_profil(ADMIN), lambda: r.supprimer_profil("Employé"),
                   lambda: r.ajouter("awa", "Employé", "autre12"), lambda: r.ajouter("Zoé", "Employé", "court")):
        with pytest.raises(ErreurUtilisateur):
            action()
    r.activer("Awa", False)
    assert r.verifier("Awa", "caisse1") is None  # compte désactivé
    r.ajouter("Chef", ADMIN, "chef1234")
    r.supprimer("Admin")
    assert [u.nom for u in r.admins_actifs()] == ["Chef"]


def test_profil_libre_enregistre(tmp_path):
    r = Registre(tmp_path)
    r.ajouter("Admin", ADMIN, "secret123")
    r.definir_profil("Livreur", ["fournisseurs", "inconnue"])
    r.enregistrer()
    donnees = json.loads((tmp_path / "donnees" / "utilisateurs.json").read_text(encoding="utf-8"))
    assert donnees["profils"]["Livreur"] == ["accueil", "fournisseurs"]
    assert len(Registre(tmp_path).profils[ADMIN]) == 13
