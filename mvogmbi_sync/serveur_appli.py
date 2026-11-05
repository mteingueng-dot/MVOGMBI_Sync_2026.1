"""Serveur de l'application (demande du propriétaire du 2026-11-04 : « il faut ajouter ces informations dans la
configuration afin que je puisse déployer ailleurs que sur mon poste ») : nom de l'ordinateur qui a Sage et
MVOGMBI_Sync, son adresse Tailscale et son adresse locale, le nom que l'on tape dans le client et le port du serveur
web. Gardés dans config.toml ([serveur] ; adresse et port = [web]) et réglés dans « Administration > Automatisation ».

Le client (MVOGMBI_Sync_Client.exe, sur les postes) n'a pas config.toml : il lit `serveur.json`, à côté de son
programme ou dans %APPDATA%\\MVOGMBI_Sync_Client ; ce fichier se télécharge depuis la même carte (`fichier_client`).
"""

from __future__ import annotations

import json

# valeurs de départ : serveur SERVDCSAGE (Sage 50 installé le 2026-11-04)
DEFAUTS = {"machine": "SERVDCSAGE", "adresse": "100.99.52.28", "adresse_locale": "192.168.2.62",
           "nom_public": "app.marchemvogmbi.com", "port": 8765}  # DNS : app.marchemvogmbi.com -> 100.99.52.28


def lire(config: dict) -> dict:
    """Réglages du serveur : [serveur] et [web] de config.toml, sinon les valeurs de départ."""
    s, w = config.get("serveur", {}), config.get("web", {})
    adresse = str(w.get("adresse") or "")
    if adresse in ("", "127.0.0.1", "0.0.0.0", "localhost"):
        adresse = str(s.get("adresse") or DEFAUTS["adresse"])
    return {"machine": str(s.get("machine") or DEFAUTS["machine"]), "adresse": adresse,
            "adresse_locale": str(s.get("adresse_locale") or DEFAUTS["adresse_locale"]),
            "nom_public": str(s.get("nom_public") or DEFAUTS["nom_public"]),
            "port": int(w.get("port") or s.get("port") or DEFAUTS["port"]),
            "certificat": str(w.get("certificat") or ""), "cle": str(w.get("cle") or "")}


def ecrire(config: dict, valeurs: dict) -> None:
    """Réglages saisis -> [serveur] (+ [web] port ; [web] adresse seulement si elle était déjà une vraie adresse)."""
    port = int(valeurs.get("port") or DEFAUTS["port"])
    if not 1 <= port <= 65535:
        raise ValueError("Port invalide (1 à 65535).")
    config.setdefault("serveur", {}).update(
        machine=str(valeurs.get("machine", "")).strip(), adresse=str(valeurs.get("adresse", "")).strip(),
        adresse_locale=str(valeurs.get("adresse_locale", "")).strip(),
        nom_public=str(valeurs.get("nom_public", "")).strip().lower(), port=port)
    web = config.setdefault("web", {})
    web["port"] = port
    # HTTPS (demande du propriétaire du 2026-11-04 : « https sans port ») : certificat et clé PEM (Let's Encrypt)
    certificat, cle = str(valeurs.get("certificat", "")).strip(), str(valeurs.get("cle", "")).strip()
    if "certificat" in valeurs:
        if certificat:
            web["certificat"], web["cle"] = certificat, cle
        else:
            web.pop("certificat", None)
            web.pop("cle", None)
    if web.get("adresse") not in (None, "", "127.0.0.1", "0.0.0.0", "localhost"):
        web["adresse"] = config["serveur"]["adresse"] or web["adresse"]


def url(reglages: dict) -> str:
    """Par le nom (s'il a un point : enregistrement DNS vers l'adresse Tailscale), sinon par l'adresse ; HTTPS si un
    certificat est réglé ; port omis quand c'est celui du protocole (443 / 80)."""
    hote = reglages["nom_public"] if "." in reglages["nom_public"] else reglages["adresse"]
    schema = "https" if reglages.get("certificat") else "http"
    port = int(reglages["port"])
    return f"{schema}://{hote}" + ("" if (schema, port) in (("https", 443), ("http", 80)) else f":{port}")


def fichier_client(config: dict) -> bytes:
    """serveur.json du client : le nom tapé (« marchemvogmbi.com ») -> l'adresse du serveur."""
    r = lire(config)
    noms = {r["nom_public"]: url(r), f"www.{r['nom_public']}": url(r), "marchemvogmbi.com": url(r)}
    contenu = {"serveur": r["machine"], "noms": noms, "adresse": url(r),
               "adresse_locale": r["adresse_locale"]}
    return json.dumps(contenu, ensure_ascii=False, indent=1).encode("utf-8")


def copier_pour_client(racine, config: dict) -> None:
    """serveur.json dans le dossier du client installé avec l'application ({app}\\client), s'il existe."""
    from pathlib import Path

    dossier = Path(racine) / "client"
    if dossier.is_dir():
        try:
            (dossier / "serveur.json").write_bytes(fichier_client(config))
        except OSError:
            pass
