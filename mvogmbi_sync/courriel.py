"""Compte rendu par courriel (SMTP) après chaque traitement automatique : succès comme problème.

Le courriel donne la période traitée et, pour chaque date, son état (facture importée et montants,
aucune vente, déjà présente, bloquée et pourquoi, reportée à la nuit suivante), puis les points à corriger.
"""

from __future__ import annotations

import html
import smtplib
import ssl
from decimal import Decimal
from email.message import EmailMessage

from . import coffre

JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
COULEURS = {
    "Facture importée": "#1b7f3b", "Facture prête (simulation)": "#1b5e9f", "Aucune vente": "#666666",
    "Facture déjà présente dans Sage": "#666666", "Bloquée": "#b3261e", "Échec de l'import": "#b3261e",
    "Reportée à la prochaine exécution": "#9a6700",
}


def parametres(config_toml: dict) -> dict:
    return config_toml.get("courriel", {})


def _argent(montant: Decimal) -> str:
    return f"{montant:,.2f} $".replace(",", " ").replace(".", ",")


def envoyer(config_toml: dict, sujet: str, corps: str, corps_html: str | None = None) -> None:
    c = parametres(config_toml)
    destinataires = [d.strip() for d in str(c.get("destinataires", "")).replace(";", ",").split(",") if d.strip()]
    if not c.get("serveur") or not destinataires:
        raise RuntimeError("Courriel non configuré (serveur ou destinataire manquant).")
    message = EmailMessage()
    message["Subject"] = sujet
    message["From"] = c.get("expediteur") or c.get("utilisateur")
    message["To"] = ", ".join(destinataires)
    message.set_content(corps)
    if corps_html:
        message.add_alternative(corps_html, subtype="html")
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


def sujet_compte_rendu(cr) -> str:
    importees = [j for j in cr.jours if j.etat == "Facture importée"]
    prefixe = "SIMULATION — " if cr.simulation else ""
    if cr.erreur:
        return f"{prefixe}MVOGMBI_Sync : ERREUR du traitement automatique"
    if cr.problemes:
        return f"{prefixe}MVOGMBI_Sync : {len(cr.problemes)} point(s) à corriger — {len(importees)} facture(s) importée(s)"
    if not cr.periode:
        return f"{prefixe}MVOGMBI_Sync : Sage est à jour (dernière facture : {cr.derniere_avant or 'aucune'})"
    d, f = cr.periode
    periode = f"du {d:%d/%m} au {f:%d/%m/%Y}" if d != f else f"du {d:%d/%m/%Y}"
    if cr.simulation:
        return f"{prefixe}MVOGMBI_Sync : {sum(1 for j in cr.jours if j.etat.startswith('Facture prête'))} facture(s) prête(s) {periode}"
    return f"MVOGMBI_Sync : succès — {len(importees)} facture(s) importée(s) {periode}"


def texte_compte_rendu(cr) -> str:
    parties = [f"Traitement du {cr.debut:%Y-%m-%d à %H:%M}" + (" (SIMULATION : aucun import)" if cr.simulation else ""),
               f"Fichier Sage : {cr.fichier or '?'}",
               f"Dernière facture journalière avant le traitement : {cr.derniere_avant or 'aucune'}"]
    if cr.periode:
        parties.append(f"Période traitée : du {cr.periode[0]} au {cr.periode[1]}")
    else:
        parties.append("Période traitée : aucune (Sage était déjà à jour)")
    parties.append("")
    if cr.jours:
        parties.append("Dates traitées :")
        for j in cr.jours:
            montants = (f" — {j.lignes} lignes, sous-total {_argent(j.sous_total)}, taxes {_argent(j.taxes)}, "
                        f"total {_argent(j.total)}") if j.lignes else ""
            parties.append(f"  {j.jour} ({JOURS[j.jour.weekday()]}) : {j.etat}{montants}"
                           + (f"\n      {j.detail}" if j.detail else ""))
        importees = [j for j in cr.jours if j.etat == "Facture importée"]
        if importees:
            parties.append(f"\n  Total importé : {len(importees)} facture(s), "
                           f"{_argent(sum((j.total for j in importees), Decimal('0')))} taxes comprises")
        parties.append("")
    if cr.problemes:
        parties += ["À corriger (le traitement reprendra automatiquement la nuit suivante) :"]
        parties += [f"  - {p}" for p in cr.problemes] + [""]
    if cr.erreur:
        parties += ["Erreur :", cr.erreur, ""]
    parties += ["Déroulement :"] + cr.lignes
    return "\n".join(parties)


def html_compte_rendu(cr) -> str:
    e = html.escape
    lignes_tableau = []
    for j in cr.jours:
        couleur = COULEURS.get(j.etat, "#333")
        montants = (f"<td style='text-align:right'>{j.lignes}</td><td style='text-align:right'>{_argent(j.sous_total)}</td>"
                    f"<td style='text-align:right'>{_argent(j.taxes)}</td><td style='text-align:right'><b>{_argent(j.total)}</b></td>"
                    if j.lignes else "<td></td><td></td><td></td><td></td>")
        lignes_tableau.append(
            f"<tr><td>{j.jour:%Y-%m-%d}</td><td>{JOURS[j.jour.weekday()]}</td>"
            f"<td style='color:{couleur};font-weight:bold'>{e(j.etat)}</td>{montants}"
            f"<td style='color:#555'>{e(j.detail)}</td></tr>")
    importees = [j for j in cr.jours if j.etat == "Facture importée"]
    total = (f"<p><b>Total importé : {len(importees)} facture(s), "
             f"{_argent(sum((j.total for j in importees), Decimal('0')))} taxes comprises</b></p>" if importees else "")
    tableau = ("<table cellpadding='6' cellspacing='0' border='1' style='border-collapse:collapse;"
               "border-color:#ddd;font-size:13px'><tr style='background:#f0f0f0'><th>Date</th><th>Jour</th><th>État</th>"
               "<th>Lignes</th><th>Sous-total</th><th>Taxes</th><th>Total</th><th>Détail</th></tr>"
               + "".join(lignes_tableau) + "</table>") if cr.jours else ""
    problemes = ("<h3 style='color:#b3261e'>À corriger</h3><p>Le traitement reprendra automatiquement la nuit suivante.</p><ul>"
                 + "".join(f"<li>{e(p)}</li>" for p in cr.problemes) + "</ul>") if cr.problemes else ""
    erreur = f"<h3 style='color:#b3261e'>Erreur</h3><pre>{e(cr.erreur)}</pre>" if cr.erreur else ""
    periode = (f"du <b>{cr.periode[0]}</b> au <b>{cr.periode[1]}</b>" if cr.periode
               else "aucune (Sage était déjà à jour)")
    return (
        "<div style='font-family:Segoe UI,Arial,sans-serif;font-size:14px'>"
        f"<h2 style='margin-bottom:4px'>{e(sujet_compte_rendu(cr))}</h2>"
        f"<p>Traitement du {cr.debut:%Y-%m-%d à %H:%M}{' — <b>SIMULATION</b> : aucun import' if cr.simulation else ''}<br>"
        f"Fichier Sage : {e(cr.fichier or '?')}<br>"
        f"Dernière facture journalière avant le traitement : {cr.derniere_avant or 'aucune'}<br>"
        f"Période traitée : {periode}</p>"
        f"{tableau}{total}{problemes}{erreur}"
        "<details><summary>Déroulement détaillé</summary><pre style='font-size:12px'>"
        + e("\n".join(cr.lignes)) + "</pre></details></div>")


def envoyer_compte_rendu(config_toml: dict, cr) -> None:
    """Compte rendu après chaque traitement (succès compris, sauf si envoyer_si_succes = false)."""
    c = parametres(config_toml)
    if not c.get("serveur"):
        return
    if cr.succes and not c.get("envoyer_si_succes", True):
        return
    envoyer(config_toml, sujet_compte_rendu(cr), texte_compte_rendu(cr), html_compte_rendu(cr))
