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
from .aide import COPYRIGHT
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


def adresses(texte) -> list[str]:
    """Adresses séparées par des virgules, des points-virgules, des espaces ou des retours à la ligne."""
    return [a for a in str(texte or "").replace(";", ",").replace("\n", ",").replace(" ", ",").split(",") if a]


def adresses_invalides(texte) -> list[str]:
    return [a for a in adresses(texte) if a.count("@") != 1 or "." not in a.split("@")[1] or a.startswith("@")]


def preparer_message(c: dict, sujet: str, corps: str, corps_html: str | None = None) -> EmailMessage:
    destinataires = adresses(c.get("destinataires"))
    copies = [a for a in adresses(c.get("copie")) if a.lower() not in {d.lower() for d in destinataires}]
    if not c.get("serveur") or not destinataires:
        raise RuntimeError("Courriel non configuré (serveur ou destinataire manquant).")
    message = EmailMessage()
    message["Subject"] = sujet
    message["From"] = c.get("expediteur") or c.get("utilisateur")
    message["To"] = ", ".join(destinataires)
    if copies:
        message["Cc"] = ", ".join(copies)  # send_message envoie aussi aux adresses en copie
    message.set_content(corps)
    if corps_html:
        message.add_alternative(corps_html, subtype="html")
    return message


def envoyer(config_toml: dict, sujet: str, corps: str, corps_html: str | None = None) -> None:
    c = parametres(config_toml)
    message = preparer_message(c, sujet, corps, corps_html)
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
    sujet = _sujet_factures(cr)
    encaisses = len(getattr(cr, "encaissements", []) or [])
    if encaisses and not cr.erreur:
        sujet += t(" — {n} dépôt(s) encaissé(s)", n=encaisses)
    payes = len(getattr(cr, "paiements", []) or [])
    if payes and not cr.erreur and not getattr(cr, "seulement_paiements", False):
        sujet += t(" — {n} paiement(s) fournisseur(s)", n=payes)
    return sujet


def _sujet_factures(cr) -> str:
    importees = [j for j in cr.jours if j.etat == "Facture importée"]
    prefixe = t("SIMULATION — ") if cr.simulation else ""
    if getattr(cr, "seulement_encaissements", False):
        if cr.erreur or cr.problemes:
            return t("MVOGMBI_Sync : encaissements — {n} point(s) à vérifier", n=len(cr.problemes) + bool(cr.erreur))
        return t("MVOGMBI_Sync : encaissements")
    if getattr(cr, "seulement_paiements", False):
        if cr.erreur or cr.problemes:
            return t("MVOGMBI_Sync : paiements fournisseurs — {n} point(s) à vérifier",
                     n=len(cr.problemes) + bool(cr.erreur))
        return t("MVOGMBI_Sync : {n} paiement(s) fournisseur(s) saisi(s)", n=len(cr.paiements))
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
    if getattr(cr, "encaissements", None):
        parties += [t("Encaissements des dépôts Clover (compte Desjardins) :")]
        parties += [f"  {x}" for x in cr.encaissements] + [""]
    if getattr(cr, "paiements", None):
        parties += [t("Paiements fournisseurs saisis dans Sage :")]
        parties += [f"  {x}" for x in cr.paiements] + [""]
    if cr.problemes:
        parties += [t("À corriger (le traitement reprendra automatiquement la nuit suivante) :")]
        parties += [f"  - {p}" for p in cr.problemes] + [""]
    if cr.erreur:
        parties += [t("Erreur :"), cr.erreur, ""]
    parties += [t("Déroulement :")] + cr.lignes
    parties += ["", "—", f"MVOGMBI_Sync — {COPYRIGHT} — " + t("Tous droits réservés.")]
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
    encaissements = (f"<h3 style='color:#1b7f3b'>{e(t('Encaissements des dépôts Clover (compte Desjardins) :'))}</h3><ul>"
                     + "".join(f"<li>{e(x)}</li>" for x in cr.encaissements) + "</ul>") \
        if getattr(cr, "encaissements", None) else ""
    encaissements += (f"<h3 style='color:#1b7f3b'>{e(t('Paiements fournisseurs saisis dans Sage :'))}</h3><ul>"
                      + "".join(f"<li>{e(x)}</li>" for x in cr.paiements) + "</ul>")         if getattr(cr, "paiements", None) else ""
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
        f"{tableau}{total}{encaissements}{problemes}{erreur}"
        f"<details><summary>{t('Déroulement détaillé')}</summary><pre style='font-size:12px'>"
        + e("\n".join(cr.lignes)) + "</pre></details>"
        f"<p style='margin-top:18px;color:#8a978e;font-size:12px'>MVOGMBI_Sync — {e(COPYRIGHT)} — "
        f"{e(t('Tous droits réservés.'))}</p></div>")


def envoyer_bilan_encaissements(config_toml: dict, bilan: dict) -> None:
    """Courriel après des encaissements lancés à la demande (bouton « Encaisser dans Sage »)."""
    from .automatique import CompteRendu

    cr = CompteRendu(seulement_encaissements=True)
    cr.fichier = str(config_toml.get("sage_import", {}).get("fichier_entreprise", "")).rsplit("\\", 1)[-1]
    cr.encaissements = list(bilan.get("encaisses", []))
    cr.problemes = [f"Encaissement : {p}" for p in bilan.get("a_verifier", [])]
    if bilan.get("erreur"):
        cr.problemes.append(f"Encaissements non faits : {bilan['erreur']}")
    cr.lignes = list(bilan.get("notes", []))
    envoyer_compte_rendu(config_toml, cr)


def envoyer_bilan_paiements(config_toml: dict, bilan: dict) -> None:
    """Courriel après des paiements fournisseurs saisis à la demande (bouton « Payer dans Sage »)."""
    from .automatique import CompteRendu

    cr = CompteRendu(seulement_paiements=True)
    cr.fichier = str(config_toml.get("sage_import", {}).get("fichier_entreprise", "")).rsplit("\\", 1)[-1]
    cr.paiements = list(bilan.get("payes", []))
    cr.problemes = [f"Paiement fournisseur : {p}" for p in bilan.get("a_verifier", [])]
    if bilan.get("erreur"):
        cr.problemes.append(f"Paiements fournisseurs non faits : {bilan['erreur']}")
    cr.lignes = list(bilan.get("notes", []))
    envoyer_compte_rendu(config_toml, cr)


def envoyer_compte_rendu(config_toml: dict, cr) -> None:
    """Compte rendu après chaque traitement (succès compris, sauf si envoyer_si_succes = false)."""
    c = parametres(config_toml)
    if not c.get("serveur"):
        return
    langues.depuis_config(config_toml)  # courriel dans la langue choisie dans l'application
    if cr.succes and not c.get("envoyer_si_succes", True):
        return
    envoyer(config_toml, sujet_compte_rendu(cr), texte_compte_rendu(cr), html_compte_rendu(cr))
