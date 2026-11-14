"""Sauvegarde dans le cloud (demande du propriétaire du 2026-11-13 : « le client se connecte sur son compte de stockage
dans le cloud et y dépose le fichier sauvegarde » ; choix : tous les services, chiffrement par mot de passe).

Chaque sauvegarde .zip (sauvegarde.py) est CHIFFRÉE sur le poste (AES-256-GCM par morceaux de 4 Mo, clé tirée du mot
de passe du client par PBKDF2-SHA256 600 000 tours ; le service de stockage ne peut rien lire) puis déposée sur le
compte du client :

- OneDrive (compte Microsoft personnel ou professionnel) : dossier de l'application « Applications/ConceptSolutionStock »
  (portée Files.ReadWrite.AppFolder : l'application ne voit RIEN d'autre du OneDrive) ;
- Google Drive : dossier « MVOGMBI_Sync » (portée drive.file : seulement les fichiers créés par l'application) ;
- Dropbox : dossier de l'application (Applications/ConceptSolutionStock) ;
- stockage compatible S3 (Amazon S3, Wasabi, Backblaze B2, MinIO…) : compartiment + préfixe, clés d'accès du client.

Connexion OneDrive / Google Drive / Dropbox : page d'accord du service ouverte dans le navigateur (OAuth 2.0 avec PKCE),
retour reçu sur ce poste (http://localhost:8767/sauvegarde/retour) ; seul le jeton de renouvellement est gardé, dans le
coffre-fort de Windows. Identifiants des applications de l'éditeur : [sauvegarde_cloud] onedrive_client_id /
google_client_id / dropbox_client_id (sinon IDENTIFIANTS ci-dessous) ; secret de l'application Google (Google l'exige
même pour une application de bureau) dans le coffre.

Conservation dans le cloud : même règle que sur le poste (14 jours, 8 semaines, 12 mois). Restauration : sauvegarde
téléchargée dans le dossier des sauvegardes (sous-dossier « depuis_le_cloud »), déchiffrée, puis sauvegarde.restaurer.
SANS le mot de passe de chiffrement, une sauvegarde du cloud ne se restaure pas : il faut le noter en lieu sûr.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import struct
import threading
import time
import webbrowser
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, quote, urlencode, urlparse

from . import coffre
from . import sauvegarde as sv

SERVICES = {"onedrive": "OneDrive", "google_drive": "Google Drive", "dropbox": "Dropbox",
            "s3": "Stockage S3 (Amazon, Wasabi, Backblaze…)"}
SECTION = "sauvegarde_cloud"
EXTENSION = ".cssbak"
DOSSIER_NUAGE = "MVOGMBI_Sync"
PORT_RETOUR = 8767
CHEMIN_RETOUR = "/sauvegarde/retour"
DELAI = 120
LONGUEUR_MOT = 12

# Identifiants (publics) des applications de l'éditeur, une fois inscrites chez Microsoft, Google et Dropbox ; une
# valeur de [sauvegarde_cloud] passe d'abord (essais, autre éditeur).
IDENTIFIANTS = {"onedrive": "6fffa1bd-1dff-4b13-af6f-921b3b27e046",  # « ConceptSolutionStock Sauvegarde »
               "google_drive": "", "dropbox": ""}

MOT = "sauvegarde_cloud_mot"                      # mot de passe de chiffrement des sauvegardes (client)
RENOUVELLEMENT = {"onedrive": "sauvegarde_onedrive_refresh", "google_drive": "sauvegarde_google_refresh",
                  "dropbox": "sauvegarde_dropbox_refresh"}
GOOGLE_SECRET = "sauvegarde_google_secret"        # secret de l'application Google de l'éditeur
S3_SECRET = "sauvegarde_s3_secret"                # clé secrète d'accès S3 du client


class ErreurCloud(RuntimeError):
    pass


# --------------------------------------------------------------------------------------------- réglages
def reglages(config_toml: dict | None) -> dict:
    s = (config_toml or {}).get(SECTION)
    s = s if isinstance(s, dict) else {}
    return {"service": str(s.get("service") or "").strip(), "actif": bool(s.get("actif", True)),
            "compte": str(s.get("compte") or ""),
            "onedrive_client_id": str(s.get("onedrive_client_id") or IDENTIFIANTS["onedrive"]).strip(),
            "google_client_id": str(s.get("google_client_id") or IDENTIFIANTS["google_drive"]).strip(),
            "dropbox_client_id": str(s.get("dropbox_client_id") or IDENTIFIANTS["dropbox"]).strip(),
            "s3_adresse": str(s.get("s3_adresse") or "https://s3.amazonaws.com").strip().rstrip("/"),
            "s3_region": str(s.get("s3_region") or "us-east-1").strip(),
            "s3_compartiment": str(s.get("s3_compartiment") or "").strip(),
            "s3_prefixe": str(s.get("s3_prefixe") or "MVOGMBI_Sync/").strip().lstrip("/"),
            "s3_cle_acces": str(s.get("s3_cle_acces") or "").strip()}


def probleme_mot(mot: str) -> str:
    if len(mot) < LONGUEUR_MOT:
        return f"Le mot de passe de chiffrement doit avoir au moins {LONGUEUR_MOT} caractères."
    sortes = sum((any(c.islower() for c in mot), any(c.isupper() for c in mot), any(c.isdigit() for c in mot),
                  any(not c.isalnum() for c in mot)))
    return "" if sortes >= 3 else ("Mélangez au moins 3 sortes de caractères (minuscules, majuscules, chiffres, "
                                   "symboles).")


def definir_mot(mot: str) -> None:
    probleme = probleme_mot(mot)
    if probleme:
        raise ErreurCloud(probleme)
    coffre.ecrire(MOT, mot)


def mot_defini() -> bool:
    return bool(coffre.lire_frais(MOT))


# --------------------------------------------------------------------------------------------- chiffrement
MAGIQUE = b"CSSBAK1\n"
TOURS = 600_000
MORCEAU = 4 * 1024 * 1024


def _cle(mot: str, sel: bytes, tours: int) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", mot.encode("utf-8"), sel, tours, 32)


def chiffrer(source: Path, sortie: Path, mot: str) -> Path:
    """Fichier chiffré : MAGIQUE | sel (16) | tours (4) | base de nonce (8) | morceaux [longueur (4) | données
    chiffrées]. Chaque morceau : AES-256-GCM, nonce = base + n° (4), données associées = en-tête + n° + « fin »
    (le dernier morceau est marqué : un fichier tronqué ou réordonné est refusé)."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    sel, base = os.urandom(16), os.urandom(8)
    entete = MAGIQUE + sel + struct.pack(">I", TOURS) + base
    aes = AESGCM(_cle(mot, sel, TOURS))
    provisoire = Path(str(sortie) + ".partiel")
    with open(source, "rb") as entree, open(provisoire, "wb") as fichier:
        fichier.write(entete)
        n, morceau = 0, entree.read(MORCEAU)
        while True:
            suivant = entree.read(MORCEAU) if morceau else b""
            fin = not suivant
            nonce = base + struct.pack(">I", n)
            chiffre = aes.encrypt(nonce, morceau, entete + struct.pack(">I?", n, fin))
            fichier.write(struct.pack(">I", len(chiffre)) + chiffre)
            if fin:
                break
            n, morceau = n + 1, suivant
    provisoire.replace(sortie)
    return Path(sortie)


def dechiffrer(source: Path, sortie: Path, mot: str) -> Path:
    from cryptography.exceptions import InvalidTag
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    provisoire = Path(str(sortie) + ".partiel")
    with open(source, "rb") as entree:
        entete = entree.read(len(MAGIQUE) + 16 + 4 + 8)
        if not entete.startswith(MAGIQUE) or len(entete) < len(MAGIQUE) + 28:
            raise ErreurCloud("Ce fichier n'est pas une sauvegarde chiffrée de MVOGMBI_Sync.")
        sel = entete[len(MAGIQUE):len(MAGIQUE) + 16]
        tours = struct.unpack(">I", entete[len(MAGIQUE) + 16:len(MAGIQUE) + 20])[0]
        base = entete[len(MAGIQUE) + 20:]
        aes = AESGCM(_cle(mot, sel, tours))
        n, fini = 0, False
        try:
            with open(provisoire, "wb") as fichier:
                while True:
                    taille = entree.read(4)
                    if len(taille) < 4:
                        break
                    chiffre = entree.read(struct.unpack(">I", taille)[0])
                    nonce = base + struct.pack(">I", n)
                    try:  # morceau ordinaire, sinon le dernier (marqué « fin ») ; ni l'un ni l'autre = refus
                        clair, fin = aes.decrypt(nonce, chiffre, entete + struct.pack(">I?", n, False)), False
                    except InvalidTag:
                        clair, fin = aes.decrypt(nonce, chiffre, entete + struct.pack(">I?", n, True)), True
                    fichier.write(clair)
                    if fin:
                        fini = True
                        break
                    n += 1
        except InvalidTag as exc:
            provisoire.unlink(missing_ok=True)
            raise ErreurCloud("Mot de passe de chiffrement faux, ou sauvegarde abîmée.") from exc
    if not fini:
        provisoire.unlink(missing_ok=True)
        raise ErreurCloud("Sauvegarde incomplète (le fichier a été coupé).")
    provisoire.replace(sortie)
    return Path(sortie)


# --------------------------------------------------------------------------------------------- OAuth (PKCE)
@dataclass
class Oauth:
    code: str
    page: str
    jeton: str
    portees: str
    hote: str                                        # localhost (Microsoft) ou 127.0.0.1 (Google, Dropbox)
    supplement: dict = field(default_factory=dict)  # paramètres de plus pour la page d'accord

    @property
    def redirection(self) -> str:  # à déclarer TELLE QUELLE dans l'application du service
        return f"http://{self.hote}:{PORT_RETOUR}{CHEMIN_RETOUR}"


OAUTH = {
    "onedrive": Oauth("onedrive", "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
                      "https://login.microsoftonline.com/common/oauth2/v2.0/token",
                      "Files.ReadWrite.AppFolder User.Read offline_access",
                      "localhost", {"prompt": "select_account"}),
    "google_drive": Oauth("google_drive", "https://accounts.google.com/o/oauth2/v2/auth",
                          "https://oauth2.googleapis.com/token", "https://www.googleapis.com/auth/drive.file",
                          "127.0.0.1", {"access_type": "offline", "prompt": "consent"}),
    "dropbox": Oauth("dropbox", "https://www.dropbox.com/oauth2/authorize", "https://api.dropboxapi.com/oauth2/token",
                     "", "127.0.0.1", {"token_access_type": "offline"}),
}
_ACCES: dict[str, tuple[float, str]] = {}  # jeton d'accès en mémoire : service -> (fin, jeton)


def _client_id(service: str, r: dict) -> str:
    cle = {"onedrive": "onedrive_client_id", "google_drive": "google_client_id", "dropbox": "dropbox_client_id"}[service]
    if not r[cle]:
        raise ErreurCloud(f"Identifiant de l'application {SERVICES[service]} absent (Administration > Sauvegarde : "
                          "« Identifiant de l'application »).")
    return r[cle]


def _formulaire_jeton(service: str, r: dict, valeurs: dict) -> dict:
    o = OAUTH[service]
    corps = {"client_id": _client_id(service, r), **valeurs}
    if service == "google_drive":
        corps["client_secret"] = coffre.lire_frais(GOOGLE_SECRET)
    if service == "onedrive":
        corps["scope"] = o.portees
    return corps


def _demander_jeton(service: str, r: dict, valeurs: dict, session=None) -> dict:
    import requests

    reponse = (session or requests).post(OAUTH[service].jeton, data=_formulaire_jeton(service, r, valeurs), timeout=DELAI)
    try:
        donnees = reponse.json()
    except ValueError:
        donnees = {}
    if reponse.status_code != 200 or "access_token" not in donnees:
        raison = donnees.get("error_description") or donnees.get("error") or reponse.text[:200]
        raise ErreurCloud(f"{SERVICES[service]} refuse la connexion ({reponse.status_code}) : {raison}")
    if donnees.get("refresh_token"):
        coffre.ecrire(RENOUVELLEMENT[service], donnees["refresh_token"])
    _ACCES[service] = (time.time() + int(donnees.get("expires_in") or 3600) - 120, donnees["access_token"])
    return donnees


def jeton_acces(service: str, r: dict, session=None) -> str:
    _client_id(service, r)
    fin, jeton = _ACCES.get(service, (0, ""))
    if jeton and time.time() < fin:
        return jeton
    renouvellement = coffre.lire_frais(RENOUVELLEMENT[service])
    if not renouvellement:
        raise ErreurCloud(f"Aucun compte {SERVICES[service]} connecté : Administration > Sauvegarde > « Se connecter ».")
    return _demander_jeton(service, r, {"grant_type": "refresh_token", "refresh_token": renouvellement},
                           session)["access_token"]


def adresse_accord(service: str, r: dict, etat: str, defi: str) -> str:
    o = OAUTH[service]
    parametres = {"client_id": _client_id(service, r), "response_type": "code", "redirect_uri": o.redirection,
                  "state": etat, "code_challenge": defi, "code_challenge_method": "S256", **o.supplement}
    if o.portees:
        parametres["scope"] = o.portees
    return f"{o.page}?{urlencode(parametres)}"


def connecter(racine: Path, config_toml: dict, service: str, ouvrir=webbrowser.open, attente: float = 300,
              session=None) -> str:
    """Connexion au compte de stockage : page d'accord ouverte dans le navigateur, retour reçu sur ce poste, jeton
    de renouvellement rangé dans le coffre ; nom du compte noté dans [sauvegarde_cloud] compte. Rend ce nom."""
    from http.server import BaseHTTPRequestHandler, HTTPServer

    r = reglages(config_toml)
    verificateur = secrets.token_urlsafe(64)
    defi = base64.urlsafe_b64encode(hashlib.sha256(verificateur.encode()).digest()).rstrip(b"=").decode()
    etat = secrets.token_urlsafe(24)
    recu: dict = {}

    class Retour(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 — nom imposé par http.server
            demande = urlparse(self.path)
            if demande.path != CHEMIN_RETOUR:
                self.send_response(404)
                self.end_headers()
                return
            recu.update({k: v[0] for k, v in parse_qs(demande.query).items()})
            ok = recu.get("state") == etat and "code" in recu
            corps = ("<html><head><meta charset='utf-8'><title>MVOGMBI_Sync</title></head><body style='font-"
                     "family:Segoe UI;margin:40px'><h2>" + ("✔ Compte connecté : vous pouvez fermer cette page." if ok
                                                            else "✖ Connexion refusée ou annulée.") +
                     "</h2></body></html>").encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(corps)))
            self.end_headers()
            self.wfile.write(corps)

        def log_message(self, *_a):
            pass

    class Exclusif(HTTPServer):
        allow_reuse_address = False  # Windows : sinon un autre programme peut écouter le même port et recevoir le code

        def server_bind(self):
            import socket

            if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            super().server_bind()

    try:
        serveur = Exclusif(("127.0.0.1", PORT_RETOUR), Retour)
    except OSError as exc:
        raise ErreurCloud(f"Le port {PORT_RETOUR} de ce poste est déjà pris : fermez l'autre connexion en cours.") \
            from exc
    serveur.timeout = 1
    try:
        ouvrir(adresse_accord(service, r, etat, defi))
        fin = time.time() + attente
        while not recu and time.time() < fin:
            serveur.handle_request()
    finally:
        serveur.server_close()
    if not recu:
        raise ErreurCloud("Aucune réponse du service dans le délai : recommencez.")
    if recu.get("state") != etat:
        raise ErreurCloud("Réponse inattendue (état différent) : recommencez.")
    if "code" not in recu:
        raise ErreurCloud(f"Connexion refusée : {recu.get('error_description') or recu.get('error') or 'annulée'}.")
    _demander_jeton(service, r, {"grant_type": "authorization_code", "code": recu["code"],
                                 "redirect_uri": OAUTH[service].redirection, "code_verifier": verificateur}, session)
    nom = destination(service, config_toml, session).compte()
    _noter(racine, {"service": service, "compte": nom})
    return nom


def deconnecter(racine: Path, service: str) -> None:
    if service in RENOUVELLEMENT:
        coffre.supprimer(RENOUVELLEMENT[service])
    _ACCES.pop(service, None)
    _noter(racine, {"compte": ""})


def _noter(racine: Path, valeurs: dict) -> None:
    from .ecriture_config import ecrire_valeurs

    ecrire_valeurs(Path(racine) / "config.toml", SECTION, valeurs)


# --------------------------------------------------------------------------------------------- services
@dataclass
class FichierNuage:
    nom: str
    taille: int = 0
    quand: str = ""
    ident: str = ""


class Destination:
    """Contrat : compte(), envoyer(chemin, nom), lister() -> [FichierNuage], telecharger(f, sortie), supprimer(f)."""

    def __init__(self, config_toml: dict, session=None):
        import requests

        self.r = reglages(config_toml)
        self.session = session or requests.Session()

    def _verifier(self, reponse, quoi: str):
        if reponse.status_code >= 300:
            raise ErreurCloud(f"{quoi} : refus du service ({reponse.status_code}) {reponse.text[:300]}")
        return reponse


class OneDrive(Destination):
    BASE = "https://graph.microsoft.com/v1.0/me/drive/special/approot"
    TRANCHE = 320 * 1024 * 32  # 10 Mo, multiple de 320 Ko comme exigé

    def _en_tetes(self):
        return {"Authorization": "Bearer " + jeton_acces("onedrive", self.r, self.session)}

    def compte(self) -> str:
        d = self._verifier(self.session.get("https://graph.microsoft.com/v1.0/me/drive", headers=self._en_tetes(),
                                            timeout=DELAI), "Compte OneDrive").json()
        return (d.get("owner", {}).get("user", {}) or {}).get("displayName") or "OneDrive"

    def envoyer(self, chemin: Path, nom: str) -> None:
        session = self._verifier(self.session.post(
            f"{self.BASE}:/{quote(nom)}:/createUploadSession", headers=self._en_tetes(),
            json={"item": {"@microsoft.graph.conflictBehavior": "replace"}}, timeout=DELAI), "Envoi OneDrive").json()
        adresse, taille = session["uploadUrl"], Path(chemin).stat().st_size
        with open(chemin, "rb") as f:
            debut = 0
            while debut < taille or taille == 0:
                morceau = f.read(self.TRANCHE)
                fin = debut + len(morceau) - 1
                reponse = self.session.put(adresse, data=morceau, timeout=DELAI * 3, headers={
                    "Content-Length": str(len(morceau)), "Content-Range": f"bytes {debut}-{fin}/{taille}"})
                self._verifier(reponse, "Envoi OneDrive")
                debut += len(morceau)
                if taille == 0:
                    break

    def lister(self) -> list[FichierNuage]:
        adresse = f"{self.BASE}/children?$select=name,size,lastModifiedDateTime,id&$top=200"
        fichiers = []
        while adresse:
            d = self._verifier(self.session.get(adresse, headers=self._en_tetes(), timeout=DELAI),
                               "Liste OneDrive").json()
            fichiers += [FichierNuage(e["name"], int(e.get("size") or 0), e.get("lastModifiedDateTime", ""), e["id"])
                         for e in d.get("value", [])]
            adresse = d.get("@odata.nextLink", "")
        return fichiers

    def telecharger(self, f: FichierNuage, sortie: Path) -> None:
        reponse = self._verifier(self.session.get(f"{self.BASE}:/{quote(f.nom)}:/content", headers=self._en_tetes(),
                                                  timeout=DELAI * 3, stream=True), "Téléchargement OneDrive")
        _ecrire_flux(reponse, sortie)

    def supprimer(self, f: FichierNuage) -> None:
        self._verifier(self.session.delete(f"{self.BASE}:/{quote(f.nom)}", headers=self._en_tetes(), timeout=DELAI),
                       "Suppression OneDrive")


class GoogleDrive(Destination):
    API = "https://www.googleapis.com/drive/v3"
    TRANCHE = 256 * 1024 * 32  # 8 Mo, multiple de 256 Ko comme exigé

    def _en_tetes(self):
        return {"Authorization": "Bearer " + jeton_acces("google_drive", self.r, self.session)}

    def compte(self) -> str:
        d = self._verifier(self.session.get(f"{self.API}/about?fields=user(displayName,emailAddress)",
                                            headers=self._en_tetes(), timeout=DELAI), "Compte Google Drive").json()
        u = d.get("user", {})
        return u.get("emailAddress") or u.get("displayName") or "Google Drive"

    def _dossier(self) -> str:
        q = f"name='{DOSSIER_NUAGE}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
        d = self._verifier(self.session.get(f"{self.API}/files", params={"q": q, "fields": "files(id)"},
                                            headers=self._en_tetes(), timeout=DELAI), "Dossier Google Drive").json()
        if d.get("files"):
            return d["files"][0]["id"]
        d = self._verifier(self.session.post(f"{self.API}/files", headers=self._en_tetes(), timeout=DELAI, json={
            "name": DOSSIER_NUAGE, "mimeType": "application/vnd.google-apps.folder"}), "Dossier Google Drive").json()
        return d["id"]

    def envoyer(self, chemin: Path, nom: str) -> None:
        dossier = self._dossier()
        for ancien in [f for f in self.lister(dossier) if f.nom == nom]:
            self.supprimer(ancien)
        taille = Path(chemin).stat().st_size
        debut = self._verifier(self.session.post(
            "https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable", timeout=DELAI,
            headers={**self._en_tetes(), "X-Upload-Content-Type": "application/octet-stream",
                     "X-Upload-Content-Length": str(taille)},
            json={"name": nom, "parents": [dossier]}), "Envoi Google Drive")
        adresse = debut.headers["Location"]
        with open(chemin, "rb") as f:
            position = 0
            while True:
                morceau = f.read(self.TRANCHE)
                fin = position + len(morceau) - 1
                plage = f"bytes {position}-{fin}/{taille}" if morceau else f"bytes */{taille}"
                reponse = self.session.put(adresse, data=morceau, timeout=DELAI * 3,
                                           headers={"Content-Length": str(len(morceau)), "Content-Range": plage})
                if reponse.status_code not in (200, 201, 308):
                    self._verifier(reponse, "Envoi Google Drive")
                position += len(morceau)
                if reponse.status_code in (200, 201):
                    return
                if not morceau:
                    raise ErreurCloud("Envoi Google Drive : le service n'a pas confirmé la fin de l'envoi.")

    def lister(self, dossier: str | None = None) -> list[FichierNuage]:
        dossier = dossier or self._dossier()
        fichiers, page = [], ""
        while True:
            parametres = {"q": f"'{dossier}' in parents and trashed=false", "pageSize": 1000,
                          "fields": "nextPageToken,files(id,name,size,modifiedTime)"}
            if page:
                parametres["pageToken"] = page
            d = self._verifier(self.session.get(f"{self.API}/files", params=parametres, headers=self._en_tetes(),
                                                timeout=DELAI), "Liste Google Drive").json()
            fichiers += [FichierNuage(e["name"], int(e.get("size") or 0), e.get("modifiedTime", ""), e["id"])
                         for e in d.get("files", [])]
            page = d.get("nextPageToken", "")
            if not page:
                return fichiers

    def telecharger(self, f: FichierNuage, sortie: Path) -> None:
        reponse = self._verifier(self.session.get(f"{self.API}/files/{f.ident}?alt=media", headers=self._en_tetes(),
                                                  timeout=DELAI * 3, stream=True), "Téléchargement Google Drive")
        _ecrire_flux(reponse, sortie)

    def supprimer(self, f: FichierNuage) -> None:
        self._verifier(self.session.delete(f"{self.API}/files/{f.ident}", headers=self._en_tetes(), timeout=DELAI),
                       "Suppression Google Drive")


class Dropbox(Destination):
    API, CONTENU = "https://api.dropboxapi.com/2", "https://content.dropboxapi.com/2"
    TRANCHE = 8 * 1024 * 1024

    def _en_tetes(self, **autres):
        return {"Authorization": "Bearer " + jeton_acces("dropbox", self.r, self.session), **autres}

    def compte(self) -> str:
        d = self._verifier(self.session.post(f"{self.API}/users/get_current_account", headers=self._en_tetes(),
                                             timeout=DELAI), "Compte Dropbox").json()
        return d.get("email") or d.get("name", {}).get("display_name") or "Dropbox"

    def envoyer(self, chemin: Path, nom: str) -> None:
        octets = {"Content-Type": "application/octet-stream"}
        with open(chemin, "rb") as f:
            morceau = f.read(self.TRANCHE)
            d = self._verifier(self.session.post(
                f"{self.CONTENU}/files/upload_session/start", data=morceau, timeout=DELAI * 3,
                headers=self._en_tetes(**octets, **{"Dropbox-API-Arg": json.dumps({"close": False})})),
                "Envoi Dropbox").json()
            ident, position = d["session_id"], len(morceau)
            while True:
                morceau = f.read(self.TRANCHE)
                if not morceau:
                    break
                self._verifier(self.session.post(
                    f"{self.CONTENU}/files/upload_session/append_v2", data=morceau, timeout=DELAI * 3,
                    headers=self._en_tetes(**octets, **{"Dropbox-API-Arg": json.dumps(
                        {"cursor": {"session_id": ident, "offset": position}, "close": False})})), "Envoi Dropbox")
                position += len(morceau)
        self._verifier(self.session.post(
            f"{self.CONTENU}/files/upload_session/finish", data=b"", timeout=DELAI,
            headers=self._en_tetes(**octets, **{"Dropbox-API-Arg": json.dumps(
                {"cursor": {"session_id": ident, "offset": position},
                 "commit": {"path": f"/{nom}", "mode": "overwrite", "mute": True}})})), "Envoi Dropbox")

    def lister(self) -> list[FichierNuage]:
        d = self._verifier(self.session.post(f"{self.API}/files/list_folder", json={"path": ""},
                                             headers=self._en_tetes(), timeout=DELAI), "Liste Dropbox").json()
        fichiers = []
        while True:
            fichiers += [FichierNuage(e["name"], int(e.get("size") or 0), e.get("server_modified", ""),
                                      e.get("path_lower", ""))
                         for e in d.get("entries", []) if e.get(".tag") == "file"]
            if not d.get("has_more"):
                return fichiers
            d = self._verifier(self.session.post(f"{self.API}/files/list_folder/continue",
                                                 json={"cursor": d["cursor"]}, headers=self._en_tetes(),
                                                 timeout=DELAI), "Liste Dropbox").json()

    def telecharger(self, f: FichierNuage, sortie: Path) -> None:
        reponse = self._verifier(self.session.post(
            f"{self.CONTENU}/files/download", timeout=DELAI * 3, stream=True,
            headers=self._en_tetes(**{"Dropbox-API-Arg": json.dumps({"path": f.ident or f"/{f.nom}"})})),
            "Téléchargement Dropbox")
        _ecrire_flux(reponse, sortie)

    def supprimer(self, f: FichierNuage) -> None:
        self._verifier(self.session.post(f"{self.API}/files/delete_v2", json={"path": f.ident or f"/{f.nom}"},
                                         headers=self._en_tetes(), timeout=DELAI), "Suppression Dropbox")


class StockageS3(Destination):
    """Amazon S3 ou compatible (Wasabi, Backblaze B2, MinIO…) : adresse en style chemin
    https://<adresse>/<compartiment>/<préfixe><nom>, signature AWS v4 calculée ici (aucune bibliothèque de plus)."""

    VIDE = hashlib.sha256(b"").hexdigest()

    def _verifier_reglages(self):
        if not (self.r["s3_compartiment"] and self.r["s3_cle_acces"] and coffre.lire_frais(S3_SECRET)):
            raise ErreurCloud("Stockage S3 : compartiment, clé d'accès et clé secrète obligatoires (Administration > "
                              "Sauvegarde).")

    def _adresse(self, nom: str = "") -> str:
        return f"{self.r['s3_adresse']}/{quote(self.r['s3_compartiment'])}/{quote(self.r['s3_prefixe'] + nom)}" \
            if nom else f"{self.r['s3_adresse']}/{quote(self.r['s3_compartiment'])}"

    def _signer(self, methode: str, adresse: str, empreinte: str, parametres: dict | None = None) -> dict:
        self._verifier_reglages()
        u = urlparse(adresse)
        maintenant = datetime.now(timezone.utc)
        jour, horodatage = maintenant.strftime("%Y%m%d"), maintenant.strftime("%Y%m%dT%H%M%SZ")
        requete = "&".join(f"{quote(str(k), safe='-_.~')}={quote(str(v), safe='-_.~')}"
                           for k, v in sorted((parametres or {}).items()))
        en_tetes = {"host": u.netloc, "x-amz-content-sha256": empreinte, "x-amz-date": horodatage}
        signes = ";".join(sorted(en_tetes))
        canonique = "\n".join([methode, u.path or "/", requete,
                               "".join(f"{k}:{en_tetes[k]}\n" for k in sorted(en_tetes)), signes, empreinte])
        portee = f"{jour}/{self.r['s3_region']}/s3/aws4_request"
        a_signer = "\n".join(["AWS4-HMAC-SHA256", horodatage, portee,
                              hashlib.sha256(canonique.encode()).hexdigest()])
        cle = ("AWS4" + coffre.lire_frais(S3_SECRET)).encode()
        for morceau in (jour, self.r["s3_region"], "s3", "aws4_request"):
            cle = hmac.new(cle, morceau.encode(), hashlib.sha256).digest()
        signature = hmac.new(cle, a_signer.encode(), hashlib.sha256).hexdigest()
        return {"x-amz-content-sha256": empreinte, "x-amz-date": horodatage,
                "Authorization": f"AWS4-HMAC-SHA256 Credential={self.r['s3_cle_acces']}/{portee}, "
                                 f"SignedHeaders={signes}, Signature={signature}"}

    def compte(self) -> str:
        self.lister()
        return f"{self.r['s3_compartiment']} ({urlparse(self.r['s3_adresse']).netloc})"

    def envoyer(self, chemin: Path, nom: str) -> None:
        empreinte = hashlib.sha256()
        with open(chemin, "rb") as f:
            for bloc in iter(lambda: f.read(1024 * 1024), b""):
                empreinte.update(bloc)
        adresse = self._adresse(nom)
        with open(chemin, "rb") as f:
            self._verifier(self.session.put(adresse, data=f, timeout=DELAI * 10, headers={
                **self._signer("PUT", adresse, empreinte.hexdigest()),
                "Content-Length": str(Path(chemin).stat().st_size)}), "Envoi S3")

    def lister(self) -> list[FichierNuage]:
        import xml.etree.ElementTree as ET

        adresse, fichiers, suite = self._adresse(), [], ""
        while True:
            parametres = {"list-type": "2", "prefix": self.r["s3_prefixe"]}
            if suite:
                parametres["continuation-token"] = suite
            reponse = self._verifier(self.session.get(adresse, params=parametres, timeout=DELAI,
                                                      headers=self._signer("GET", adresse, self.VIDE, parametres)),
                                     "Liste S3")
            racine = ET.fromstring(reponse.content)
            ns = racine.tag.split("}")[0] + "}" if racine.tag.startswith("{") else ""
            for c in racine.findall(f"{ns}Contents"):
                cle = c.findtext(f"{ns}Key", "")
                fichiers.append(FichierNuage(cle[len(self.r["s3_prefixe"]):], int(c.findtext(f"{ns}Size", "0")),
                                             c.findtext(f"{ns}LastModified", ""), cle))
            suite = racine.findtext(f"{ns}NextContinuationToken", "")
            if racine.findtext(f"{ns}IsTruncated", "false") != "true" or not suite:
                return [f for f in fichiers if f.nom and "/" not in f.nom]

    def telecharger(self, f: FichierNuage, sortie: Path) -> None:
        adresse = self._adresse(f.nom)
        reponse = self._verifier(self.session.get(adresse, timeout=DELAI * 3, stream=True,
                                                  headers=self._signer("GET", adresse, self.VIDE)), "Téléchargement S3")
        _ecrire_flux(reponse, sortie)

    def supprimer(self, f: FichierNuage) -> None:
        adresse = self._adresse(f.nom)
        self._verifier(self.session.delete(adresse, timeout=DELAI, headers=self._signer("DELETE", adresse, self.VIDE)),
                       "Suppression S3")


CLASSES = {"onedrive": OneDrive, "google_drive": GoogleDrive, "dropbox": Dropbox, "s3": StockageS3}


def destination(service: str, config_toml: dict, session=None) -> Destination:
    if service not in CLASSES:
        raise ErreurCloud("Aucun service de stockage choisi (Administration > Sauvegarde).")
    return CLASSES[service](config_toml, session)


def _ecrire_flux(reponse, sortie: Path) -> None:
    provisoire = Path(str(sortie) + ".partiel")
    Path(sortie).parent.mkdir(parents=True, exist_ok=True)
    with open(provisoire, "wb") as f:
        for bloc in reponse.iter_content(1024 * 1024):
            f.write(bloc)
    provisoire.replace(sortie)


# --------------------------------------------------------------------------------------------- envoi et restauration
@dataclass
class EtatCloud:
    quand: str = ""
    service: str = ""
    fichier: str = ""
    taille: int = 0
    ok: bool = False
    message: str = ""


def _etat_chemin(racine: Path) -> Path:
    return Path(racine) / "donnees" / "derniere_sauvegarde_cloud.json"


def derniere(racine: Path) -> EtatCloud:
    try:
        return EtatCloud(**json.loads(_etat_chemin(racine).read_text(encoding="utf-8")))
    except (OSError, ValueError, TypeError):
        return EtatCloud()


def nom_nuage(archive: Path) -> str:
    return Path(archive).stem + EXTENSION


def conserver(dest: Destination, aujourdhui: date) -> list[str]:
    """Même règle que sur le poste (14 jours, 8 semaines, 12 mois) pour les sauvegardes de l'application."""
    fichiers = [f for f in dest.lister() if f.nom.startswith(sv.PREFIXE) and f.nom.endswith(EXTENSION)]
    par_chemin = {Path(f.nom): f for f in fichiers}
    gardees = sv.a_garder(list(par_chemin), aujourdhui)
    retirees = []
    for chemin, f in par_chemin.items():
        if chemin not in gardees:
            dest.supprimer(f)
            retirees.append(f.nom)
    return retirees


def envoyer(racine: Path, config_toml: dict, archive: Path, session=None, maintenant: datetime | None = None) -> EtatCloud:
    """Chiffre la sauvegarde et la dépose sur le compte du client, puis applique la conservation. L'état est noté
    dans donnees/derniere_sauvegarde_cloud.json ; une erreur ne lève jamais d'exception (état ok faux)."""
    import tempfile

    r = reglages(config_toml)
    maintenant = maintenant or datetime.now()
    etat = EtatCloud(quand=maintenant.isoformat(timespec="seconds"), service=r["service"])
    try:
        mot = coffre.lire_frais(MOT)
        if not mot:
            raise ErreurCloud("Mot de passe de chiffrement des sauvegardes non défini (Administration > Sauvegarde).")
        dest = destination(r["service"], config_toml, session)
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            chiffre = chiffrer(Path(archive), Path(tmp) / nom_nuage(archive), mot)
            dest.envoyer(chiffre, chiffre.name)
            etat.fichier, etat.taille = chiffre.name, chiffre.stat().st_size
        presents = {f.nom for f in dest.lister()}
        if etat.fichier not in presents:
            raise ErreurCloud("la sauvegarde n'apparaît pas sur le compte après l'envoi")
        retirees = conserver(dest, maintenant.date())
        etat.ok = True
        etat.message = f"{len(retirees)} ancienne(s) sauvegarde(s) retirée(s) du cloud" if retirees else ""
    except Exception as exc:  # noqa: BLE001 — l'état dit pourquoi ; la nuit continue
        etat.ok, etat.message = False, str(exc)
    _etat_chemin(racine).parent.mkdir(parents=True, exist_ok=True)
    _etat_chemin(racine).write_text(json.dumps(asdict(etat), ensure_ascii=False, indent=1), encoding="utf-8")
    return etat


def envoi_actif(config_toml: dict) -> bool:
    r = reglages(config_toml)
    return bool(r["service"]) and r["actif"]


def sauvegardes_nuage(config_toml: dict, session=None) -> list[FichierNuage]:
    r = reglages(config_toml)
    fichiers = [f for f in destination(r["service"], config_toml, session).lister() if f.nom.endswith(EXTENSION)]
    return sorted(fichiers, key=lambda f: f.nom, reverse=True)


def telecharger_pour_restaurer(racine: Path, config_toml: dict, fichier: FichierNuage, session=None) -> Path:
    """Télécharge et déchiffre une sauvegarde du cloud dans <dossier des sauvegardes>/depuis_le_cloud ; rend le .zip
    prêt pour sauvegarde.restaurer (qui le vérifie et sauvegarde d'abord l'état actuel)."""
    mot = coffre.lire_frais(MOT)
    if not mot:
        raise ErreurCloud("Mot de passe de chiffrement des sauvegardes non défini : saisissez-le d'abord.")
    r = reglages(config_toml)
    dossier = sv.dossier(racine, config_toml) / "depuis_le_cloud"
    dossier.mkdir(parents=True, exist_ok=True)
    chiffre = dossier / fichier.nom
    destination(r["service"], config_toml, session).telecharger(fichier, chiffre)
    archive = dechiffrer(chiffre, dossier / (Path(fichier.nom).stem + ".zip"), mot)
    chiffre.unlink(missing_ok=True)
    probleme = sv.verifier(archive)
    if probleme:
        raise ErreurCloud(f"Sauvegarde téléchargée inutilisable : {probleme}")
    return archive


def envoyer_en_fond(racine: Path, config_toml: dict, archive: Path, fin=None) -> threading.Thread:
    def travail():
        etat = envoyer(racine, config_toml, archive)
        if fin:
            fin(etat)

    fil = threading.Thread(target=travail, daemon=True)
    fil.start()
    return fil
