"""Alertes par courriel (SMTP) après chaque traitement automatique."""

from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage

from . import coffre


def parametres(config_toml: dict) -> dict:
    return config_toml.get("courriel", {})


def envoyer(config_toml: dict, sujet: str, corps: str) -> None:
    c = parametres(config_toml)
    destinataires = [d.strip() for d in str(c.get("destinataires", "")).replace(";", ",").split(",") if d.strip()]
    if not c.get("serveur") or not destinataires:
        raise RuntimeError("Courriel non configuré (serveur ou destinataire manquant).")
    message = EmailMessage()
    message["Subject"] = sujet
    message["From"] = c.get("expediteur") or c.get("utilisateur")
    message["To"] = ", ".join(destinataires)
    message.set_content(corps)
    port = int(c.get("port", 587))
    securite = str(c.get("securite", "starttls")).lower()
    contexte = ssl.create_default_context()
    if securite == "ssl":
        serveur = smtplib.SMTP_SSL(c["serveur"], port, context=contexte, timeout=60)
    else:
        serveur = smtplib.SMTP(c["serveur"], port, timeout=60)
        if securite == "starttls":
            serveur.starttls(context=contexte)
    with serveur:
        if c.get("utilisateur"):
            serveur.login(c["utilisateur"], coffre.lire(coffre.COURRIEL))
        serveur.send_message(message)


def envoyer_compte_rendu(config_toml: dict, cr) -> None:
    """Courriel si problème ; aussi en cas de succès si [courriel] envoyer_si_succes = true."""
    c = parametres(config_toml)
    if not c.get("serveur"):
        return
    if cr.succes and not c.get("envoyer_si_succes", False):
        return
    if cr.erreur:
        sujet = "MVOGMBI_Sync : ERREUR du traitement automatique"
    elif cr.problemes:
        sujet = f"MVOGMBI_Sync : {len(cr.problemes)} point(s) à corriger"
    else:
        sujet = f"MVOGMBI_Sync : {len(cr.importees)} facture(s) importée(s)"
    parties = [f"Traitement du {cr.debut:%Y-%m-%d à %H:%M}", ""]
    if cr.importees:
        parties += ["Factures importées dans Sage :"] + [f"  - {t}" for t in cr.importees] + [""]
    if cr.problemes:
        parties += ["À corriger (le traitement reprendra automatiquement la nuit suivante) :"]
        parties += [f"  - {p}" for p in cr.problemes] + [""]
    if cr.erreur:
        parties += ["Erreur :", cr.erreur, ""]
    parties += ["Déroulement :"] + cr.lignes
    envoyer(config_toml, sujet, "\n".join(parties))
