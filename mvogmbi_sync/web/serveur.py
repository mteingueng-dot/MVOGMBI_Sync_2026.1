"""Serveur web : connexion, sessions, sécurité et aiguillage des pages (pages.py).

Sécurité (règles de l'application de bureau reprises) :
- mêmes comptes que l'application (utilisateurs.Registre : empreinte PBKDF2, 3 mots de passe faux = compte
  verrouillé, dernier administrateur seulement bloqué 15 min) ; en plus, 10 échecs en 10 min depuis une même adresse
  = connexion refusée 10 min depuis cette adresse ;
- session dans un témoin HttpOnly, SameSite=Strict (Secure en HTTPS), fermée après [web] inactivite_minutes (15) sans
  requête et au plus tard après 12 h ; jeton tiré au hasard, jamais dans une adresse ;
- chaque formulaire porte un jeton anti-falsification lié à la session ; un envoi venu d'une autre origine est refusé ;
- en-têtes : aucune page dans un cadre, aucun script, pas de mise en cache, référent jamais envoyé à un autre site ;
- chaque page ouverte et chaque action sont notées dans l'audit (fenêtre « Web »).
Le chiffrement passe par Tailscale (WireGuard) ; HTTPS en plus si [web] certificat et cle sont donnés.
"""

from __future__ import annotations

import html
import secrets
import ssl
import sys
import threading
import time
import tomllib
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

ADRESSE_DEFAUT = "127.0.0.1"   # rien n'est ouvert au réseau tant que [web] adresse n'est pas réglée
PORT_DEFAUT = 8765
INACTIVITE_DEFAUT = 15         # minutes
DUREE_MAX = 12 * 3600          # une session ne dure jamais plus de 12 h
TAILLE_MAX = 64 * 1024         # corps d'un formulaire
TAILLE_MAX_FICHIERS = 25 * 1024 * 1024  # formulaire avec fichiers (reçus, relevés, factures PDF, états RIA)
ECHECS_ADRESSE, FENETRE_ADRESSE = 10, 600
COOKIE = "mvogmbi_session"


@dataclass
class Session:
    jeton: str
    nom: str
    csrf: str
    debut: float
    vu: float


class Sessions:
    def __init__(self, inactivite: float):
        self.inactivite = inactivite
        self._sessions: dict[str, Session] = {}
        self._verrou = threading.Lock()

    def creer(self, nom: str) -> Session:
        maintenant = time.time()
        s = Session(secrets.token_urlsafe(32), nom, secrets.token_urlsafe(24), maintenant, maintenant)
        with self._verrou:
            self._sessions[s.jeton] = s
        return s

    def lire(self, jeton: str) -> Session | None:
        maintenant = time.time()
        with self._verrou:
            s = self._sessions.get(jeton or "")
            if s is None:
                return None
            if maintenant - s.vu > self.inactivite or maintenant - s.debut > DUREE_MAX:
                del self._sessions[s.jeton]
                return None
            s.vu = maintenant
            return s

    def fermer(self, jeton: str) -> None:
        with self._verrou:
            self._sessions.pop(jeton or "", None)

    def fermer_compte(self, nom: str) -> None:
        """Toutes les sessions d'un compte (mot de passe changé)."""
        with self._verrou:
            for j in [j for j, s in self._sessions.items() if s.nom.casefold() == nom.casefold()]:
                del self._sessions[j]


@dataclass
class Requete:
    methode: str
    chemin: str
    query: dict[str, str]
    form: dict[str, list[str]]
    adresse: str
    jeton: str = ""
    fichiers: dict = field(default_factory=dict)  # champ -> (nom du fichier, contenu)

    def champ(self, nom: str, defaut: str = "") -> str:
        valeurs = self.form.get(nom)
        return valeurs[-1] if valeurs else defaut

    def champs(self, nom: str) -> list[str]:
        return list(self.form.get(nom, []))


@dataclass
class Reponse:
    statut: int = 200
    corps: str | bytes = ""
    type: str = "text/html; charset=utf-8"
    entetes: dict[str, str] = field(default_factory=dict)
    style_en_ligne: bool = False  # page complète écrite ailleurs (tableau du gérant) : son propre style


def redirection(chemin: str) -> Reponse:
    return Reponse(303, "", entetes={"Location": chemin})


def lire_config(racine: Path) -> dict:
    chemin = Path(racine) / "config.toml"
    try:
        return tomllib.loads(chemin.read_text(encoding="utf-8")) if chemin.exists() else {}
    except (OSError, tomllib.TOMLDecodeError):
        return {}


class Application:
    """État partagé par toutes les requêtes."""

    def __init__(self, racine: Path, config: dict | None = None):
        self.racine = Path(racine)
        self.config = config if config is not None else lire_config(self.racine)
        web = self.config.get("web", {})
        self.sessions = Sessions(max(1, int(web.get("inactivite_minutes", INACTIVITE_DEFAUT) or INACTIVITE_DEFAUT))
                                 * 60)
        self.https = bool(web.get("certificat"))
        self.ecriture = threading.Lock()   # écritures dans donnees/ (fichiers JSON)
        self.echecs: dict[str, list[float]] = {}
        self.echecs_nip: dict[str, tuple] = {}  # NIP faux, gardés d'une requête à l'autre (paie_temps.ESSAIS_NIP)
        self.memoire: dict = {}                 # lectures Clover gardées un moment (pages.statistiques)
        self.journal = self.racine / "donnees" / "journal_web.log"

    # ---------------------------------------------------------------- journal
    def noter(self, texte: str) -> None:
        try:
            self.journal.parent.mkdir(parents=True, exist_ok=True)
            with open(self.journal, "a", encoding="utf-8") as f:
                f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} {texte}\n")
        except OSError:
            pass

    # ---------------------------------------------------------------- adresses refusées
    def adresse_bloquee(self, adresse: str) -> bool:
        maintenant = time.time()
        recents = [t for t in self.echecs.get(adresse, []) if maintenant - t < FENETRE_ADRESSE]
        self.echecs[adresse] = recents
        return len(recents) >= ECHECS_ADRESSE

    def echec(self, adresse: str) -> None:
        self.echecs.setdefault(adresse, []).append(time.time())

    # ---------------------------------------------------------------- aiguillage
    def traiter(self, req: Requete) -> Reponse:
        from .. import audit
        from ..utilisateurs import Registre
        from . import pages

        if req.chemin == "/style.css":
            from .accueil import STYLE_ACCUEIL
            from .menu import STYLE_MENU

            from .pages_statistiques import STYLE_STATS

            from .pages_rapports_web import STYLE_RAPPORTS

            from .export_web import STYLE_EXPORT
            from .style_windows import STYLE_WINDOWS

            return Reponse(corps=pages.STYLE + STYLE_MENU + STYLE_ACCUEIL + STYLE_STATS + STYLE_RAPPORTS + STYLE_EXPORT
                           + STYLE_WINDOWS,
                           type="text/css; charset=utf-8")
        if req.chemin == "/logo.png":
            from .accueil import logo

            return logo(self, req)
        if req.chemin == "/connexion":
            return pages.connexion(self, req)
        if req.chemin == "/deconnexion":
            self.sessions.fermer(req.jeton)
            return redirection("/connexion")
        session = self.sessions.lire(req.jeton)
        if session is None:
            return redirection("/connexion")
        reg = Registre(self.racine)
        u = reg.trouver(session.nom)
        if u is None or not u.actif or reg.bloque(u):
            self.sessions.fermer(session.jeton)
            return redirection("/connexion")
        if req.methode == "GET" and "csrf" in req.query:  # filet : le jeton ne reste jamais dans une adresse
            from urllib.parse import urlencode

            reste = {k: v for k, v in req.query.items() if k != "csrf"}
            return redirection(req.chemin + (f"?{urlencode(reste)}" if reste else ""))
        if req.methode == "POST" and not secrets.compare_digest(req.champ("csrf"), session.csrf):
            return Reponse(403, pages.page_simple("Formulaire refusé", "Le formulaire a expiré : rouvrez la page."))
        fonction = pages.trouver(req.chemin)
        if fonction is None:
            return Reponse(404, pages.page_simple("Page introuvable", "Cette page n'existe pas."))
        if not pages.permis(reg, u, fonction):
            audit.noter(self.racine, f"refus : {fonction.titre}", "Web", utilisateur=u.nom)
            return Reponse(403, pages.page_simple("Accès refusé", "Votre profil n'a pas accès à cette fonction."))
        ctx = pages.Contexte(self, req, reg, u, session)
        action = fonction.titre if req.methode == "GET" else f"{fonction.titre} : {req.champ('action', 'envoi')}"
        audit.noter(self.racine, action, "Web", detail=req.adresse, utilisateur=u.nom)
        try:
            reponse = fonction.gestionnaire(ctx)
            if (req.methode == "GET" and reponse.statut == 200 and isinstance(reponse.corps, str)
                    and reponse.type.startswith("text/html") and not reponse.style_en_ligne):
                from . import export_web

                if "exporter" in req.query:
                    if not reg.peut_exporter(u):
                        return Reponse(403, pages.page_simple("Accès refusé",
                                                              "Votre profil ne permet pas d'exporter les données."))
                    audit.noter(self.racine, f"{fonction.titre} : exporter ({req.query.get('format', '')})", "Web",
                                utilisateur=u.nom)
                    return export_web.fichier(self.racine, reponse.corps, req.query["exporter"],
                                              req.query.get("format", "xlsx"))
                if reg.peut_exporter(u):
                    reponse.corps = export_web.ajouter_menus(reponse.corps, req.query)
            return reponse
        except (Exception, SystemExit):  # noqa: BLE001 — une page en erreur n'arrête jamais le serveur
            self.noter(f"ERREUR {req.methode} {req.chemin} ({u.nom})\n{traceback.format_exc()}")
            return Reponse(500, pages.page(ctx, "Erreur", "<p class='erreur'>Une erreur est survenue ; elle est notée "
                                                          "dans donnees/journal_web.log.</p>"))


# --------------------------------------------------------------------------------------------- HTTP
POLITIQUE = ("default-src 'none'; style-src 'self'{inline}; img-src 'self' data:; form-action 'self'; "
             "frame-ancestors 'none'; base-uri 'none'")


class Gestionnaire(BaseHTTPRequestHandler):
    server_version = "MVOGMBI_Sync"
    sys_version = ""

    @property
    def app(self) -> Application:
        return self.server.app  # type: ignore[attr-defined]

    def do_GET(self):  # noqa: N802
        self._servir("GET")

    def do_POST(self):  # noqa: N802
        self._servir("POST")

    def log_message(self, format, *args):  # noqa: A002 — chemin seulement (aucun formulaire n'est noté)
        self.app.noter(f"{self.address_string()} {format % args}")

    def _origine_permise(self) -> bool:
        """Envoi venu d'une page de ce serveur (Origin, sinon Referer) ; absent : accepté (témoin SameSite)."""
        hote = self.headers.get("Host", "")
        for entete in ("Origin", "Referer"):
            valeur = self.headers.get(entete)
            if valeur:
                return urlsplit(valeur).netloc == hote
        return True

    def _servir(self, methode: str) -> None:
        url = urlsplit(self.path)
        query = {k: v[-1] for k, v in parse_qs(url.query).items()}
        form: dict[str, list[str]] = {}
        fichiers: dict = {}
        if methode == "POST":
            longueur = int(self.headers.get("Content-Length") or 0)
            type_contenu = self.headers.get("Content-Type", "")
            multipart = type_contenu.startswith("multipart/form-data")
            if longueur > (TAILLE_MAX_FICHIERS if multipart else TAILLE_MAX):
                return self._envoyer(Reponse(413, "Formulaire trop long (25 Mo au plus)."))
            if not self._origine_permise():
                return self._envoyer(Reponse(403, "Origine refusée."))
            corps = self.rfile.read(longueur)
            if multipart:
                form, fichiers = lire_multipart(type_contenu, corps)
            else:
                form = parse_qs(corps.decode("utf-8", "replace"), keep_blank_values=True)
        temoin = cookies.SimpleCookie()
        try:
            temoin.load(self.headers.get("Cookie", ""))
        except cookies.CookieError:
            pass
        jeton = temoin[COOKIE].value if COOKIE in temoin else ""
        req = Requete(methode, url.path.rstrip("/") or "/", query, form, self.client_address[0], jeton, fichiers)
        self._envoyer(self.app.traiter(req))

    def _envoyer(self, rep: Reponse) -> None:
        corps = rep.corps.encode("utf-8") if isinstance(rep.corps, str) else rep.corps
        self.send_response(rep.statut)
        self.send_header("Content-Type", rep.type)
        self.send_header("Content-Length", str(len(corps)))
        self.send_header("Content-Security-Policy",
                         POLITIQUE.format(inline=" 'unsafe-inline'" if rep.style_en_ligne else ""))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        # « same-origin » : « no-referrer » fait envoyer « Origin: null » aux formulaires (connexion refusée)
        self.send_header("Referrer-Policy", "same-origin")
        self.send_header("Cache-Control", "no-store")
        if self.app.https:
            self.send_header("Strict-Transport-Security", "max-age=31536000")
        for nom, valeur in rep.entetes.items():
            self.send_header(nom, valeur)
        self.end_headers()
        self.wfile.write(corps)


def lire_multipart(type_contenu: str, corps: bytes) -> tuple[dict[str, list[str]], dict]:
    """Formulaire multipart/form-data -> (champs, fichiers) ; nom de fichier réduit à son dernier élément."""
    from email.parser import BytesParser
    from email.policy import HTTP

    message = BytesParser(policy=HTTP).parsebytes(f"Content-Type: {type_contenu}\r\n\r\n".encode("latin-1") + corps)
    champs: dict[str, list[str]] = {}
    fichiers: dict = {}
    for partie in message.iter_parts():
        nom = partie.get_param("name", header="content-disposition")
        if not nom:
            continue
        nom_fichier = partie.get_filename()
        contenu = partie.get_payload(decode=True) or b""
        if nom_fichier is not None:
            try:  # le navigateur envoie le nom en UTF-8, lu ici en Latin-1
                nom_fichier = nom_fichier.encode("latin-1").decode("utf-8")
            except (UnicodeEncodeError, UnicodeDecodeError):
                pass
            if contenu:
                fichiers[nom] = (Path(nom_fichier.replace("\\", "/")).name, contenu)
        else:
            champs.setdefault(nom, []).append(contenu.decode(partie.get_content_charset() or "utf-8", "replace"))
    return champs, fichiers


def temoin_session(jeton: str, https: bool, effacer: bool = False) -> str:
    attributs = "; Path=/; HttpOnly; SameSite=Strict" + ("; Secure" if https else "")
    return f"{COOKIE}={'' if effacer else jeton}{attributs}" + ("; Max-Age=0" if effacer else "")


def creer_serveur(racine: Path, adresse: str | None = None, port: int | None = None) -> ThreadingHTTPServer:
    app = Application(racine)
    web = app.config.get("web", {})
    adresse = adresse or str(web.get("adresse", ADRESSE_DEFAUT))
    port = int(port if port is not None else web.get("port", PORT_DEFAUT))
    serveur = ThreadingHTTPServer((adresse, port), Gestionnaire)
    serveur.daemon_threads = True
    serveur.app = app  # type: ignore[attr-defined]
    if app.https:
        contexte = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        contexte.minimum_version = ssl.TLSVersion.TLSv1_2
        contexte.load_cert_chain(str(web["certificat"]), str(web.get("cle") or "") or None)
        serveur.socket = contexte.wrap_socket(serveur.socket, server_side=True)
    return serveur


def _suivre_telephones(app) -> None:
    """Chaque minute : pause automatique des employés dont le téléphone a quitté le Wi-Fi du magasin, fin de pause
    à leur retour (pointage_wifi.controler)."""
    import time

    from ..pointage_wifi import controler

    while True:
        time.sleep(60)
        try:
            with app.ecriture:
                for ligne in controler(app.racine, app.config):
                    app.noter(f"pointage : {ligne}")
        except Exception:  # noqa: BLE001 — le serveur web continue
            app.noter(f"suivi des téléphones : {traceback.format_exc(limit=2)}")


def lancer(racine: Path, adresse: str | None = None, port: int | None = None) -> None:
    try:
        serveur = creer_serveur(racine, adresse, port)
    except Exception:  # lancé par la tâche planifiée : personne ne voit la console -> journal
        Application(racine).noter(f"ÉCHEC du démarrage\n{traceback.format_exc()}")
        raise
    hote, port_reel = serveur.server_address[:2]
    schema = "https" if serveur.app.https else "http"  # type: ignore[attr-defined]
    print(f"Application web : {schema}://{hote}:{port_reel}/  (Ctrl+C pour arrêter)")
    serveur.app.noter(f"démarrage {schema}://{hote}:{port_reel}/")  # type: ignore[attr-defined]
    threading.Thread(target=_suivre_telephones, args=(serveur.app,), daemon=True).start()
    try:
        serveur.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        serveur.server_close()
        serveur.app.noter("arrêt")  # type: ignore[attr-defined]


def echapper(v) -> str:
    return html.escape(str(v), quote=True)


if __name__ == "__main__":  # pragma: no cover
    lancer(Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd())
