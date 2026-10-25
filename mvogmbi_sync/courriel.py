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

from . import coffre, langues
from .langues import t
COULEURS = {
    "Facture importée": "#1b7f3b", "Facture prête (simulation)": "#1b5e9f", "Aucune vente": "#666666",
    "Facture déjà présente dans Sage": "#666666", "Bloquée": "#b3261e", "Échec de l'import": "#b3261e",
    "Reportée à la prochaine exécution": "#9a6700",
}


def parametres(config_toml: dict) -> dict:
    return config_toml.get("courriel", {})


def _argent(montant: Decimal) -> str:
    if langues.courante() == "en":
        return f"${montant:,.2f}"
    return f"{montant:,.2f} $".replace(",", " ").replace(".", ",")


def _jour(j) -> str:
    return langues.jours_semaine()[j.weekday()]


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
    prefixe = t("SIMULATION — ") if cr.simulation else ""
    if cr.erreur:
        return prefixe + t("MVOGMBI_Sync : ERREUR du traitement automatique")
    if cr.problemes:
        return prefixe + t("MVOGMBI_Sync : {n} point(s) à corriger — {i} facture(s) importée(s)",
                           n=len(cr.problemes), i=len(importees))
    if not cr.periode:
        return prefixe + t("MVOGMBI_Sync : Sage est à jour (dernière facture : {d})", d=cr.derniere_avant or t("aucune"))
    d, f = cr.periode
    periode = (t("du {d} au {f}", d=f"{d:%d/%m}", f=f"{f:%d/%m/%Y}") if d != f else t("du {d}", d=f"{d:%d/%m/%Y}"))
    if cr.simulation:
        return prefixe + t("MVOGMBI_Sync : {n} facture(s) prête(s) {periode}",
                           n=sum(1 for j in cr.jours if j.etat.startswith("Facture prête")), periode=periode)
    return t("MVOGMBI_Sync : succès — {n} facture(s) importée(s) {periode}", n=len(importees), periode=periode)


def texte_compte_rendu(cr) -> str:
    parties = [t("Traitement du {d}", d=f"{cr.debut:%Y-%m-%d %H:%M}")
               + (t(" (SIMULATION : aucun import)") if cr.simulation else ""),
               t("Fichier Sage : {f}", f=cr.fichier or "?"),
               t("Dernière facture journalière avant le traitement : {d}", d=cr.derniere_avant or t("aucune"))]
    if cr.periode:
        parties.append(t("Période traitée : du {d} au {f}", d=cr.periode[0], f=cr.periode[1]))
    else:
        parties.append(t("Période traitée : aucune (Sage était déjà à jour)"))
    parties.append("")
    if cr.jours:
        parties.append(t("Dates traitées :"))
        for j in cr.jours:
            montants = t(" — {l} lignes, sous-total {s}, taxes {t}, total {total}", l=j.lignes, s=_argent(j.sous_total),
                         t=_argent(j.taxes), total=_argent(j.total)) if j.lignes else ""
            parties.append(f"  {j.jour} ({_jour(j.jour)}) : {t(j.etat)}{montants}"
                           + (f"\n      {j.detail}" if j.detail else ""))
        importees = [j for j in cr.jours if j.etat == "Facture importée"]
        if importees:
            parties.append("\n  " + t("Total importé : {n} facture(s), {total} taxes comprises", n=len(importees),
                                        total=_argent(sum((j.total for j in importees), Decimal("0")))))
        parties.append("")
    if cr.problemes:
        parties += [t("À corriger (le traitement reprendra automatiquement la nuit suivante) :")]
        parties += [f"  - {p}" for p in cr.problemes] + [""]
    if cr.erreur:
        parties += [t("Erreur :"), cr.erreur, ""]
    parties += [t("Déroulement :")] + cr.lignes
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
            f"<tr><td>{j.jour:%Y-%m-%d}</td><td>{_jour(j.jour)}</td>"
            f"<td style='color:{couleur};font-weight:bold'>{e(t(j.etat))}</td>{montants}"
            f"<td style='color:#555'>{e(j.detail)}</td></tr>")
    importees = [j for j in cr.jours if j.etat == "Facture importée"]
    total = ("<p><b>" + e(t("Total importé : {n} facture(s), {total} taxes comprises", n=len(importees),
                                 total=_argent(sum((j.total for j in importees), Decimal("0"))))) + "</b></p>"
             if importees else "")
    tableau = ("<table cellpadding='6' cellspacing='0' border='1' style='border-collapse:collapse;"
               "border-color:#ddd;font-size:13px'><tr style='background:#f0f0f0'>"
               + "".join(f"<th>{t(c)}</th>" for c in ("Date", "Jour", "État", "Lignes", "Sous-total", "Taxes",
                                                      "Total", "Détail")) + "</tr>"
               + "".join(lignes_tableau) + "</table>") if cr.jours else ""
    problemes = (f"<h3 style='color:#b3261e'>{t('À corriger')}</h3>"
                 f"<p>{t('Le traitement reprendra automatiquement la nuit suivante.')}</p><ul>"
                 + "".join(f"<li>{e(p)}</li>" for p in cr.problemes) + "</ul>") if cr.problemes else ""
    erreur = f"<h3 style='color:#b3261e'>{t('Erreur')}</h3><pre>{e(cr.erreur)}</pre>" if cr.erreur else ""
    periode = (t("du <b>{d}</b> au <b>{f}</b>", d=cr.periode[0], f=cr.periode[1]) if cr.periode
               else t("aucune (Sage était déjà à jour)"))
    return (
        "<div style='font-family:Segoe UI,Arial,sans-serif;font-size:14px'>"
        f"<h2 style='margin-bottom:4px'>{e(sujet_compte_rendu(cr))}</h2>"
        f"<p>{e(t('Traitement du {d}', d=f'{cr.debut:%Y-%m-%d %H:%M}'))}"
        f"{t(' — <b>SIMULATION</b> : aucun import') if cr.simulation else ''}<br>"
        f"{e(t('Fichier Sage : {f}', f=cr.fichier or '?'))}<br>"
        f"{e(t('Dernière facture journalière avant le traitement : {d}', d=cr.derniere_avant or t('aucune')))}<br>"
        f"{t('Période traitée : ')}{periode}</p>"
        f"{tableau}{total}{problemes}{erreur}"
        f"<details><summary>{t('Déroulement détaillé')}</summary><pre style='font-size:12px'>"
        + e("\n".join(cr.lignes)) + "</pre></details></div>")


def envoyer_compte_rendu(config_toml: dict, cr) -> None:
    """Compte rendu après chaque traitement (succès compris, sauf si envoyer_si_succes = false)."""
    c = parametres(config_toml)
    if not c.get("serveur"):
        return
    langues.depuis_config(config_toml)  # courriel dans la langue choisie dans l'application
    if cr.succes and not c.get("envoyer_si_succes", True):
        return
    envoyer(config_toml, sujet_compte_rendu(cr), texte_compte_rendu(cr), html_compte_rendu(cr))
