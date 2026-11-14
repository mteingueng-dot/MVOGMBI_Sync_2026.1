"""Carte « ☁ Sauvegarde dans le cloud » de la page web Sauvegarde des données (comme fenetre_sauvegarde_cloud.py).

La connexion OAuth (OneDrive, Google Drive, Dropbox) se fait depuis l'application Windows du serveur : le service
renvoie le navigateur vers http://localhost:8767 de l'appareil qui a ouvert la page de connexion. Tout le reste
(service, stockage S3, mot de passe de chiffrement, envoi, liste et restauration) se fait aussi ici. Les secrets vont
dans le coffre-fort de Windows du serveur et ne sont jamais réaffichés."""
from __future__ import annotations

from html import escape as e
from pathlib import Path

from .. import coffre
from .. import sauvegarde as sv
from .. import sauvegarde_cloud as sc

CHAMPS_S3 = (("s3_adresse", "Adresse du service"), ("s3_region", "Région"), ("s3_compartiment", "Compartiment"),
             ("s3_prefixe", "Dossier (préfixe)"), ("s3_cle_acces", "Clé d'accès"))
CLES_ID = {"onedrive": "onedrive_client_id", "google_drive": "google_client_id", "dropbox": "dropbox_client_id"}


def traiter(ctx, action: str, message_fn, refus_config, action_permise) -> tuple[str, object]:
    """Actions « cloud_… » de la page ; rend (message HTML, réponse de tâche ou None)."""
    from ..ecriture_config import ecrire_valeurs
    from . import taches

    if action == "cloud_enregistrer":
        refus = refus_config(ctx)
        if refus:
            return refus, None
        code = ctx.req.champ("service")
        valeurs = {"service": code if code in sc.SERVICES else "", "actif": bool(ctx.req.champ("actif"))}
        if code in CLES_ID:
            valeurs[CLES_ID[code]] = ctx.req.champ("client_id").strip()
            if code == "google_drive" and ctx.req.champ("secret_google").strip():
                coffre.ecrire(sc.GOOGLE_SECRET, ctx.req.champ("secret_google").strip())
        if code == "s3":
            valeurs.update({cle: ctx.req.champ(cle).strip() for cle, _ in CHAMPS_S3})
            if ctx.req.champ("s3_secret").strip():
                coffre.ecrire(sc.S3_SECRET, ctx.req.champ("s3_secret").strip())
        ecrire_valeurs(Path(ctx.racine) / "config.toml", sc.SECTION, valeurs)
        ctx.config.setdefault(sc.SECTION, {}).update(valeurs)
        return message_fn("Réglages de la sauvegarde dans le cloud enregistrés."), None
    if action == "cloud_mot":
        refus = refus_config(ctx)
        if refus:
            return refus, None
        mot, mot2 = ctx.req.champ("mot"), ctx.req.champ("mot2")
        if mot != mot2:
            return message_fn(erreur="Les deux mots de passe sont différents : rien n'est changé."), None
        try:
            sc.definir_mot(mot)
        except sc.ErreurCloud as exc:
            return message_fn(erreur=str(exc)), None
        return message_fn("Mot de passe de chiffrement enregistré dans le coffre-fort de Windows du serveur. Notez-le "
                          "en lieu sûr : sans lui, une sauvegarde du cloud ne se restaure pas."), None
    if action == "cloud_verifier":
        r = sc.reglages(ctx.config)
        if r["service"] != "s3":
            return message_fn(erreur="La connexion à OneDrive, Google Drive ou Dropbox se fait depuis l'application "
                                     "Windows du serveur (Administration > Sauvegarde des données > « Se connecter au "
                                     "compte… »)."), None
        try:
            nom = sc.destination("s3", ctx.config).compte()
        except Exception as exc:  # noqa: BLE001
            return message_fn(erreur=str(exc)), None
        ecrire_valeurs(Path(ctx.racine) / "config.toml", sc.SECTION, {"compte": nom})
        return message_fn(f"Accès vérifié : {nom}."), None
    if action == "cloud_envoyer":
        derniere = sv.derniere(ctx.racine)
        if not (derniere.ok and derniere.fichier and Path(derniere.fichier).exists()):
            return message_fn(erreur="Faites d'abord une sauvegarde (« Sauvegarder maintenant »)."), None

        def envoyer(journal):
            etat = sc.envoyer(ctx.racine, ctx.config, Path(derniere.fichier))
            return f"{'✔' if etat.ok else '✘'} {etat.fichier or ''} {etat.message}".strip()

        return "", taches.lancer(ctx, "Sauvegarde dans le cloud", envoyer, "/sauvegarde")
    if action == "cloud_restaurer":
        nom_action = "Restaurer une sauvegarde"
        nom = Path(ctx.req.champ("nuage")).name
        if not action_permise(ctx, nom_action):
            return message_fn(erreur=f"Votre profil n'a pas le droit « {nom_action} »."), None
        if not ctx.req.champ("confirme_nuage"):
            return message_fn(erreur="Cochez la confirmation : les données actuelles seront remplacées (elles sont "
                                     "d'abord sauvegardées dans « avant_restauration »)."), None
        if not nom.endswith(sc.EXTENSION):
            return message_fn(erreur="Choisissez une sauvegarde du cloud."), None

        def restaurer(journal):
            fichier = next((f for f in sc.sauvegardes_nuage(ctx.config) if f.nom == nom), None)
            if fichier is None:
                raise sc.ErreurCloud(f"« {nom} » n'est plus sur le compte.")
            archive = sc.telecharger_pour_restaurer(ctx.racine, ctx.config, fichier)
            etat, n = sv.restaurer(ctx.racine, ctx.config, archive)
            return [f"{n} fichier(s) restauré(s) depuis {nom}.", f"État actuel gardé : {etat.fichier}"]

        return "", taches.lancer(ctx, f"Restauration de {nom} (cloud)", restaurer, "/sauvegarde")
    return "", None


def carte(ctx, csrf) -> str:
    r = sc.reglages(ctx.config)
    code = ctx.req.query.get("service") or r["service"]
    derniere = sc.derniere(ctx.racine)
    options = "".join(f"<option value='{c}'{' selected' if c == code else ''}>{e(n)}</option>"
                      for c, n in [("", "Aucun (sauvegarde sur le serveur seulement)"), *sc.SERVICES.items()])
    champs = ""
    if code in CLES_ID:
        champs += (f"<div class='large'><label>Identifiant de l'application</label><input name='client_id' "
                   f"value='{e(r[CLES_ID[code]])}' size='52'></div>")
        if code == "google_drive":
            champs += ("<div><label>Secret de l'application (Google)</label><input type='password' "
                       f"name='secret_google' autocomplete='off' placeholder="
                       f"'{'enregistré' if coffre.lire_frais(sc.GOOGLE_SECRET) else ''}'></div>")
    if code == "s3":
        champs += "".join(f"<div><label>{e(libelle)}</label><input name='{cle}' value='{e(r[cle])}' size='30'></div>"
                          for cle, libelle in CHAMPS_S3)
        champs += ("<div><label>Clé secrète</label><input type='password' name='s3_secret' autocomplete='off' "
                   f"placeholder='{'enregistrée' if coffre.lire_frais(sc.S3_SECRET) else ''}'></div>")
    etat = []
    if r["service"]:
        etat.append(f"Compte : {e(r['compte'] or 'pas encore connecté')}" if r["service"] != "s3"
                    else f"Compartiment : {e(r['s3_compartiment'] or '—')}")
    etat.append("✔ Mot de passe de chiffrement défini." if sc.mot_defini()
                else "⚠ Mot de passe de chiffrement à définir.")
    if derniere.quand:
        etat.append(f"{'✔' if derniere.ok else '✖'} Dernier envoi : {derniere.quand[:16].replace('T', ' ')} — "
                    f"{e(derniere.fichier)} {e(derniere.message)}")
    bon = sc.mot_defini() and (derniere.ok or not derniere.quand)
    liste = ""
    if ctx.req.query.get("nuage") and r["service"]:
        try:
            fichiers = sc.sauvegardes_nuage(ctx.config)
            lignes = "".join(f"<tr><td><input type='radio' name='nuage' value='{e(f.nom)}'></td><td>{e(f.nom)}</td>"
                             f"<td>{f.taille / 1_048_576:.1f} Mo</td><td>{e(f.quand[:16].replace('T', ' '))}</td></tr>"
                             for f in fichiers) or "<tr><td colspan='4'>Aucune sauvegarde sur le compte.</td></tr>"
            liste = (f"<form method='post'>{csrf(ctx)}<h2 class='titre-tableau'>Sauvegardes dans le cloud</h2>"
                     "<div class='defile'><table><tr><th></th><th>Sauvegarde</th><th>Taille</th><th>Déposée le</th>"
                     f"</tr>{lignes}</table></div><div class='barre-onglet'><button class='danger' name='action' "
                     "value='cloud_restaurer'>↩ Restaurer la sauvegarde choisie…</button><label class='case'><input "
                     "type='checkbox' name='confirme_nuage' value='1'> Je remplace les données actuelles par cette "
                     "sauvegarde</label></div></form>")
        except Exception as exc:  # noqa: BLE001
            liste = f"<p class='erreur-texte'>✖ {e(str(exc))}</p>"
    return (f"<fieldset class='groupe'><legend>☁ Sauvegarde dans le cloud</legend><p class='note'>Chaque sauvegarde "
            "est CHIFFRÉE sur le serveur (mot de passe de chiffrement) puis déposée sur votre compte de stockage. Sans "
            "ce mot de passe, une sauvegarde du cloud ne se restaure pas : notez-le en lieu sûr.</p>"
            f"<form method='get' class='ligne'><div><label>Service</label><select name='service'>{options}</select>"
            "</div><button class='sans-js second'>Afficher</button></form>"
            f"<form method='post'>{csrf(ctx)}<input type='hidden' name='service' value='{e(code)}'><div class='ligne'>"
            f"{champs}<label class='case'><input type='checkbox' name='actif' value='1'"
            f"{' checked' if r['actif'] else ''}> Envoyer chaque nuit après la sauvegarde</label></div>"
            "<div class='barre-onglet'><button class='second' name='action' value='cloud_enregistrer'>💾 Enregistrer"
            "</button><button class='second' name='action' value='cloud_verifier'>🔗 Vérifier le compte</button>"
            "<button class='second' name='action' value='cloud_envoyer'>☁ Envoyer la dernière sauvegarde</button>"
            "<a class='ouvrir' href='/sauvegarde?nuage=1'>📋 Sauvegardes dans le cloud…</a></div></form>"
            f"<form method='post' class='ligne'>{csrf(ctx)}<div><label>Mot de passe de chiffrement</label><input "
            "type='password' name='mot' autocomplete='new-password'></div><div><label>Retapez-le</label><input "
            "type='password' name='mot2' autocomplete='new-password'></div><button class='second' name='action' "
            "value='cloud_mot'>🔑 Enregistrer le mot de passe</button></form>"
            f"<p class='{'ok-texte' if bon else 'erreur-texte'}'>{'<br>'.join(etat)}</p>{liste}</fieldset>")
