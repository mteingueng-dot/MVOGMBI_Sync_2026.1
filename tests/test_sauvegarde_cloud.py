"""Sauvegarde dans le cloud (sauvegarde_cloud.py) : chiffrement, envoi, conservation, restauration, connexion OAuth."""
import threading
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from mvogmbi_sync import sauvegarde as sv
from mvogmbi_sync import sauvegarde_cloud as sc

MOT = "Bonne-Sauvegarde-2026"


@pytest.fixture
def coffre_vide(monkeypatch):
    from mvogmbi_sync import coffre

    memoire = {}
    monkeypatch.setattr(coffre, "lire", lambda cle, defaut="": memoire.get(cle, defaut))
    monkeypatch.setattr(coffre, "lire_frais", lambda cle, defaut="": memoire.get(cle, defaut))
    monkeypatch.setattr(coffre, "ecrire", lambda cle, valeur: memoire.__setitem__(cle, valeur))
    monkeypatch.setattr(coffre, "supprimer", lambda cle: memoire.pop(cle, None))
    sc._ACCES.clear()
    return memoire


def test_chiffrement_aller_retour(tmp_path):
    for taille in (0, 10, sc.MORCEAU, sc.MORCEAU + 1, 3 * sc.MORCEAU + 17):
        source = tmp_path / f"s{taille}.bin"
        source.write_bytes(bytes(i % 251 for i in range(taille)))
        chiffre = sc.chiffrer(source, tmp_path / f"s{taille}.cssbak", MOT)
        assert source.read_bytes()[:64] not in chiffre.read_bytes() or taille == 0
        clair = sc.dechiffrer(chiffre, tmp_path / f"r{taille}.bin", MOT)
        assert clair.read_bytes() == source.read_bytes()


def test_chiffrement_refuse_mauvais_mot_et_fichier_coupe(tmp_path):
    source = tmp_path / "a.bin"
    source.write_bytes(b"x" * (sc.MORCEAU * 2 + 5))
    chiffre = sc.chiffrer(source, tmp_path / "a.cssbak", MOT)
    with pytest.raises(sc.ErreurCloud, match="faux"):
        sc.dechiffrer(chiffre, tmp_path / "b.bin", "Mauvais-Mot-2026")
    coupe = tmp_path / "coupe.cssbak"  # dernier morceau retiré : refusé (fichier coupé)
    donnees = chiffre.read_bytes()
    coupe.write_bytes(donnees[:len(donnees) - 40])
    with pytest.raises(sc.ErreurCloud):
        sc.dechiffrer(coupe, tmp_path / "c.bin", MOT)
    assert not (tmp_path / "b.bin").exists() and not (tmp_path / "c.bin").exists()
    autre = tmp_path / "autre.zip"
    autre.write_bytes(b"PK pas une sauvegarde")
    with pytest.raises(sc.ErreurCloud, match="pas une sauvegarde"):
        sc.dechiffrer(autre, tmp_path / "d.bin", MOT)


def test_mot_de_passe_exige(coffre_vide):
    with pytest.raises(sc.ErreurCloud, match="12"):
        sc.definir_mot("court")
    with pytest.raises(sc.ErreurCloud, match="3 sortes"):
        sc.definir_mot("toutenminuscules")
    sc.definir_mot(MOT)
    assert sc.mot_defini()


class Memoire(sc.Destination):
    """Service de stockage simulé : fichiers gardés en mémoire."""

    fichiers: dict = {}

    def __init__(self, config_toml, session=None):
        self.r = sc.reglages(config_toml)

    def compte(self):
        return "essai@exemple.ca"

    def envoyer(self, chemin, nom):
        Memoire.fichiers[nom] = Path(chemin).read_bytes()

    def lister(self):
        return [sc.FichierNuage(n, len(d)) for n, d in Memoire.fichiers.items()]

    def telecharger(self, f, sortie):
        Path(sortie).write_bytes(Memoire.fichiers[f.nom])

    def supprimer(self, f):
        Memoire.fichiers.pop(f.nom)


def _donnees(racine: Path, texte: str) -> None:
    (racine / "donnees").mkdir(parents=True, exist_ok=True)
    (racine / "donnees" / "registre.json").write_text(texte, encoding="utf-8")
    (racine / "config.toml").write_text('[sauvegarde_cloud]\nservice = "memoire"\n', encoding="utf-8")


def test_envoi_conservation_et_restauration(tmp_path, coffre_vide, monkeypatch):
    monkeypatch.setitem(sc.CLASSES, "memoire", Memoire)
    Memoire.fichiers = {}
    racine = tmp_path / "app"
    _donnees(racine, '{"version": 1}')
    config = {"sauvegarde": {"dossier": str(tmp_path / "sauvegardes")}, "sauvegarde_cloud": {"service": "memoire"}}
    etat = sc.envoyer(racine, config, tmp_path / "rien.zip")
    assert not etat.ok and "Mot de passe" in etat.message and not sc.derniere(racine).ok
    sc.definir_mot(MOT)
    jour = datetime(2026, 11, 13, 22, 0)
    # 40 jours de sauvegardes : la conservation du cloud suit celle du poste
    for i in range(40, 0, -1):
        e = sv.sauvegarder(racine, config, maintenant=jour - timedelta(days=i))
        etat = sc.envoyer(racine, config, Path(e.fichier), maintenant=jour - timedelta(days=i))
        assert etat.ok, etat.message
    assert etat.fichier.endswith(sc.EXTENSION) and sc.derniere(racine).ok
    noms = sorted(Memoire.fichiers)
    attendus = sorted(p.name for p in sv.a_garder([Path(n) for n in noms], (jour - timedelta(days=1)).date()))
    assert noms == attendus and len(noms) < 40
    assert all(b"version" not in d for d in Memoire.fichiers.values())  # chiffré : illisible chez le service
    # restauration depuis le cloud : téléchargée, déchiffrée, vérifiée, puis remise en place
    (racine / "donnees" / "registre.json").write_text('{"version": 2}', encoding="utf-8")
    plus_recente = sc.sauvegardes_nuage(config)[0]
    archive = sc.telecharger_pour_restaurer(racine, config, plus_recente)
    assert archive.suffix == ".zip" and archive.parent.name == "depuis_le_cloud"
    with zipfile.ZipFile(archive) as z:
        assert z.read("donnees/registre.json") == b'{"version": 1}'
    sv.restaurer(racine, config, archive)
    assert (racine / "donnees" / "registre.json").read_text(encoding="utf-8") == '{"version": 1}'


def test_nuit_envoie_apres_la_sauvegarde(tmp_path, coffre_vide, monkeypatch):
    from mvogmbi_sync import automatique

    monkeypatch.setitem(sc.CLASSES, "memoire", Memoire)
    Memoire.fichiers = {}
    racine = tmp_path / "app"
    _donnees(racine, "{}")
    config = {"sauvegarde": {"dossier": str(tmp_path / "s")}, "sauvegarde_cloud": {"service": "memoire"}}
    sc.definir_mot(MOT)
    cr = automatique.CompteRendu()
    automatique.sauvegarder_donnees(racine, config, cr)
    assert len(Memoire.fichiers) == 1 and not [p for p in cr.problemes if "cloud" in p]
    sans = {"sauvegarde": {"dossier": str(tmp_path / "s")}}
    automatique.sauvegarder_donnees(racine, sans, automatique.CompteRendu())  # aucun service : rien n'est envoyé
    assert len(Memoire.fichiers) == 1
    coffre_vide.pop(sc.MOT)
    cr = automatique.CompteRendu()
    automatique.sauvegarder_donnees(racine, config, cr)
    assert any("cloud" in p for p in cr.problemes)


class Reponse:
    def __init__(self, statut=200, json_=None, en_tetes=None, contenu=b""):
        self.status_code, self._json, self.headers, self.content = statut, json_ or {}, en_tetes or {}, contenu
        self.text = str(json_ or contenu)

    def json(self):
        return self._json

    def iter_content(self, _taille):
        yield self.content


class SessionFausse:
    def __init__(self, reponses):
        self.reponses, self.appels = reponses, []

    def _repondre(self, methode, adresse, **kw):
        self.appels.append((methode, adresse, kw))
        for (m, debut), rep in self.reponses.items():
            if m == methode and adresse.startswith(debut):
                return rep(adresse, kw) if callable(rep) else rep
        raise AssertionError(f"appel inattendu {methode} {adresse}")

    def get(self, a, **kw):
        return self._repondre("GET", a, **kw)

    def post(self, a, **kw):
        return self._repondre("POST", a, **kw)

    def put(self, a, **kw):
        return self._repondre("PUT", a, **kw)

    def delete(self, a, **kw):
        return self._repondre("DELETE", a, **kw)


def test_connexion_onedrive_et_envoi_par_tranches(tmp_path, coffre_vide):
    """Page d'accord (PKCE), retour reçu sur ce poste, jeton rangé ; envoi par tranches de 10 Mo."""
    import socket

    with socket.socket() as libre:  # port libre pour l'essai (8767 peut servir ailleurs sur le poste)
        libre.bind(("127.0.0.1", 0))
        port = libre.getsockname()[1]
    monkeypatch_port = pytest.MonkeyPatch()
    monkeypatch_port.setattr(sc, "PORT_RETOUR", port)
    racine = tmp_path
    (racine / "config.toml").write_text("", encoding="utf-8")
    config = {"sauvegarde_cloud": {"service": "onedrive", "onedrive_client_id": "id-essai"}}
    jetons = Reponse(json_={"access_token": "A1", "refresh_token": "R1", "expires_in": 3600})
    session = SessionFausse({
        ("POST", sc.OAUTH["onedrive"].jeton): lambda a, kw: (kw["data"].get("code_verifier") and jetons) or jetons,
        ("GET", "https://graph.microsoft.com/v1.0/me/drive"): Reponse(json_={"owner": {"user": {"displayName": "Marc"}}}),
    })

    def navigateur(adresse):
        q = parse_qs(urlparse(adresse).query)
        assert q["code_challenge_method"] == ["S256"] and "Files.ReadWrite.AppFolder" in q["scope"][0]
        import requests

        threading.Thread(target=lambda: requests.get(
            f"{q['redirect_uri'][0].replace('localhost', '127.0.0.1')}?code=C1&state={q['state'][0]}", timeout=10),
            daemon=True).start()

    try:
        assert sc.connecter(racine, config, "onedrive", ouvrir=navigateur, attente=20, session=session) == "Marc"
    finally:
        monkeypatch_port.undo()
    assert coffre_vide[sc.RENOUVELLEMENT["onedrive"]] == "R1"
    assert "compte = \"Marc\"" in (racine / "config.toml").read_text(encoding="utf-8")
    jeton = next(kw for m, a, kw in session.appels if m == "POST")["data"]
    assert jeton["grant_type"] == "authorization_code" and jeton["code"] == "C1" and jeton["code_verifier"]

    plages = []
    session.reponses[("POST", sc.OneDrive.BASE)] = Reponse(json_={"uploadUrl": "https://envoi.exemple/s"})
    session.reponses[("PUT", "https://envoi.exemple/s")] = lambda a, kw: plages.append(
        kw["headers"]["Content-Range"]) or Reponse(201)
    fichier = tmp_path / "gros.cssbak"
    fichier.write_bytes(b"z" * (sc.OneDrive.TRANCHE + 100))
    sc.OneDrive(config, session).envoyer(fichier, fichier.name)
    taille = fichier.stat().st_size
    assert plages == [f"bytes 0-{sc.OneDrive.TRANCHE - 1}/{taille}",
                      f"bytes {sc.OneDrive.TRANCHE}-{taille - 1}/{taille}"]


def test_jeton_renouvele_et_compte_absent(coffre_vide):
    config = {"sauvegarde_cloud": {"service": "dropbox", "dropbox_client_id": "cle-app"}}
    with pytest.raises(sc.ErreurCloud, match="Aucun compte"):
        sc.jeton_acces("dropbox", sc.reglages(config))
    coffre_vide[sc.RENOUVELLEMENT["dropbox"]] = "R-ancien"
    session = SessionFausse({("POST", sc.OAUTH["dropbox"].jeton): Reponse(json_={"access_token": "A2",
                                                                                 "expires_in": 14400})})
    assert sc.jeton_acces("dropbox", sc.reglages(config), session) == "A2"
    corps = session.appels[0][2]["data"]
    assert corps == {"client_id": "cle-app", "grant_type": "refresh_token", "refresh_token": "R-ancien"}
    assert sc.jeton_acces("dropbox", sc.reglages(config), session) == "A2" and len(session.appels) == 1
    with pytest.raises(sc.ErreurCloud, match="Identifiant"):
        sc.jeton_acces("google_drive", sc.reglages({}))
    assert sc.reglages({})["onedrive_client_id"] == "6fffa1bd-1dff-4b13-af6f-921b3b27e046"


def test_signature_s3(coffre_vide):
    coffre_vide[sc.S3_SECRET] = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
    config = {"sauvegarde_cloud": {"service": "s3", "s3_adresse": "https://s3.wasabisys.com", "s3_region": "us-east-1",
                                   "s3_compartiment": "mon-magasin", "s3_cle_acces": "AKIAIOSFODNN7EXAMPLE"}}
    s3 = sc.StockageS3(config, session=object())
    adresse = s3._adresse("MVOGMBI_Sync_x.cssbak")
    assert adresse == "https://s3.wasabisys.com/mon-magasin/MVOGMBI_Sync/MVOGMBI_Sync_x.cssbak"
    en_tetes = s3._signer("PUT", adresse, s3.VIDE)
    auth = en_tetes["Authorization"]
    assert auth.startswith("AWS4-HMAC-SHA256 Credential=AKIAIOSFODNN7EXAMPLE/")
    assert "/us-east-1/s3/aws4_request" in auth and "SignedHeaders=host;x-amz-content-sha256;x-amz-date" in auth
    with pytest.raises(sc.ErreurCloud, match="obligatoires"):
        sc.StockageS3({"sauvegarde_cloud": {"service": "s3"}}, session=object())._signer("GET", adresse, s3.VIDE)


def test_conservation_jamais_les_autres_fichiers(coffre_vide, monkeypatch):
    monkeypatch.setitem(sc.CLASSES, "memoire", Memoire)
    Memoire.fichiers = {"photo_vacances.jpg": b"1", f"{sv.PREFIXE}2025-01-01_000000{sc.EXTENSION}": b"2",
                        f"{sv.PREFIXE}2026-11-12_220000{sc.EXTENSION}": b"3"}
    retirees = sc.conserver(Memoire({}), date(2026, 11, 13))
    assert "photo_vacances.jpg" in Memoire.fichiers and retirees == [f"{sv.PREFIXE}2025-01-01_000000{sc.EXTENSION}"]


def test_page_web_sauvegarde_cloud(tmp_path, coffre_vide, monkeypatch):
    """Page /sauvegarde : carte du cloud, réglages S3, mot de passe de chiffrement, liste et restauration."""
    from test_web import connecter, jeton_csrf, ouvrir

    from mvogmbi_sync.utilisateurs import Registre
    from mvogmbi_sync.web import serveur

    monkeypatch.setitem(sc.CLASSES, "memoire", Memoire)
    monkeypatch.setitem(sc.SERVICES, "memoire", "Mémoire d'essai")
    Memoire.fichiers = {}
    (tmp_path / "donnees").mkdir()
    (tmp_path / "config.toml").write_text(f'[sauvegarde]\ndossier = "{(tmp_path / "s").as_posix()}"\n',
                                          encoding="utf-8")
    Registre._blocages.clear()
    reg = Registre(tmp_path)
    reg.ajouter("Patron", "Administrateur", "secret123456")
    reg.enregistrer()
    srv = serveur.creer_serveur(tmp_path, "127.0.0.1", 0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        base = f"http://127.0.0.1:{srv.server_address[1]}"
        nav = connecter(base, "Patron", "secret123456")
        statut, page, _ = ouvrir(nav, base + "/sauvegarde?service=s3")
        assert statut == 200 and "Sauvegarde dans le cloud" in page and "Compartiment" in page
        _, page, _ = ouvrir(nav, base + "/sauvegarde", {
            "csrf": jeton_csrf(page), "action": "cloud_enregistrer", "service": "s3", "actif": "1",
            "s3_adresse": "https://s3.wasabisys.com", "s3_region": "us-east-1", "s3_compartiment": "mon-magasin",
            "s3_prefixe": "CSS/", "s3_cle_acces": "AKIAESSAI", "s3_secret": "secret-s3"})
        texte = (tmp_path / "config.toml").read_text(encoding="utf-8")
        assert 'service = "s3"' in texte and 's3_compartiment = "mon-magasin"' in texte and "secret-s3" not in texte
        assert coffre_vide[sc.S3_SECRET] == "secret-s3" and "secret-s3" not in page
        _, page, _ = ouvrir(nav, base + "/sauvegarde", {"csrf": jeton_csrf(page), "action": "cloud_mot",
                                                        "mot": MOT, "mot2": "autre"})
        assert "différents" in page and sc.MOT not in coffre_vide
        _, page, _ = ouvrir(nav, base + "/sauvegarde", {"csrf": jeton_csrf(page), "action": "cloud_mot",
                                                        "mot": MOT, "mot2": MOT})
        assert "Mot de passe de chiffrement enregistré" in page and coffre_vide[sc.MOT] == MOT
        # liste des sauvegardes d'un service (simulé) et refus sans confirmation
        _, page, _ = ouvrir(nav, base + "/sauvegarde", {"csrf": jeton_csrf(page), "action": "cloud_enregistrer",
                                                        "service": "memoire", "actif": "1"})
        Memoire.fichiers[f"{sv.PREFIXE}2026-11-12_220000{sc.EXTENSION}"] = b"x"
        _, page, _ = ouvrir(nav, base + "/sauvegarde?nuage=1")
        assert f"{sv.PREFIXE}2026-11-12_220000{sc.EXTENSION}" in page and "Restaurer la sauvegarde choisie" in page
        _, page, _ = ouvrir(nav, base + "/sauvegarde", {"csrf": jeton_csrf(page), "action": "cloud_restaurer",
                                                        "nuage": f"{sv.PREFIXE}2026-11-12_220000{sc.EXTENSION}"})
        assert "Cochez la confirmation" in page
    finally:
        srv.shutdown()
        srv.server_close()
