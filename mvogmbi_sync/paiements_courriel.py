"""Avis de paiement lus dans la boîte de courriel du marché (IMAP, sans service externe).

Avis Interac envoyés par Desjardins (catch@payments.interac.ca), par exemple :
    Sujet : « Virement Interac : Votre virement de 180,00 $ à LEOPOLD X a été déposé avec succès. »
    Corps : montant, date, numéro de référence, message (« Facture 14402 du 20/08/2026 »).
États retenus : déposé (paiement fait), annulé, expiré (paiement à ne pas saisir). Le courriel n'est jamais marqué
comme lu (BODY.PEEK). Les n° de facture cités dans le message servent à retrouver la facture du fournisseur.
"""

from __future__ import annotations

import email
import html
import imaplib
import re
import ssl
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from email.header import decode_header, make_header
from email.utils import parsedate_to_datetime

from .factures_fournisseurs import lire_date, montant

DEPOSE = "Déposé"
ANNULE = "Annulé"
EXPIRE = "Expiré"
ENVOYE = "Envoyé (pas encore déposé)"
EXPEDITEURS = ("payments.interac.ca", "interac.ca")


@dataclass
class AvisPaiement:
    identifiant: str               # Message-ID du courriel (clé : jamais traité deux fois)
    date_courriel: str             # AAAA-MM-JJ
    date_virement: str
    montant: Decimal
    beneficiaire: str
    reference: str = ""
    message: str = ""
    etat: str = DEPOSE
    source: str = "Interac"

    @property
    def numeros_facture(self) -> list[str]:
        return numeros_cites(self.message)

    def en_dict(self) -> dict:
        d = asdict(self)
        d["montant"] = str(self.montant)
        return d

    @classmethod
    def depuis_dict(cls, d: dict) -> "AvisPaiement":
        return cls(**{**d, "montant": Decimal(d["montant"])})


LIMITE_TEXTE = 20_000  # caractères lus d'un courriel (sujet, texte, message de virement)


def numeros_cites(message: str) -> list[str]:
    """N° de facture cités : « Facture 14402 du 20/08/2026 » -> ["14402"] ; « FA-104202, #1264 » -> [...]."""
    mois = r"(?:janv?|f[ée]vr?|mars|avr|mai|juin|juil|ao[uû]t|sept?|oct|nov|d[ée]c|jan|feb|apr|may|jun|jul|aug|dec)\w*\.?"
    sans_dates = re.sub(r"\b\d{1,4}[/-]\d{1,2}[/-]\d{2,4}\b", " ", message[:LIMITE_TEXTE])
    sans_dates = re.sub(rf"\b\d{{1,2}}\s+{mois}\s+\d{{4}}\b|\b{mois}\s+\d{{1,2}},?\s+\d{{4}}\b", " ", sans_dates, flags=re.I)
    # « Facture#1264 », « Faccture#15 » (faute de frappe), « Inv-201010-01 », « FA-104202 », « n° 14944 »
    candidats = re.findall(r"(?:fac+t(?:ure)?|inv(?:oice)?|fa|n[°o]|#)\s*[-:#.]?\s*([A-Z]{0,3}-?\d{2,})", sans_dates, re.I)
    candidats += re.findall(r"\b([A-Z]{0,3}\d{4,})\b", sans_dates)
    return [c for c in dict.fromkeys(c.strip("-") for c in candidats) if not re.fullmatch(r"(19|20)\d{2}", c)]


def texte_du_message(message: email.message.Message) -> str:
    """Texte lisible du courriel (partie texte, sinon HTML débarrassé de ses balises)."""
    textes, htmls = [], []
    for partie in message.walk():
        if partie.get_content_maintype() != "text":
            continue
        contenu = partie.get_payload(decode=True) or b""
        texte = contenu.decode(partie.get_content_charset() or "utf-8", "replace")
        (htmls if partie.get_content_subtype() == "html" else textes).append(texte)
    if textes:
        return "\n".join(textes)
    brut = "\n".join(htmls)
    brut = re.sub(r"(?is)<(script|style).*?</\1>", " ", brut)
    brut = re.sub(r"(?i)<br\s*/?>|</(p|div|tr|td|li|h\d)>", "\n", brut)
    return html.unescape(re.sub(r"<[^>]+>", " ", brut))


def analyser(sujet: str, texte: str, identifiant: str = "", date_courriel: date | None = None) -> AvisPaiement | None:
    """Avis Interac -> AvisPaiement ; None pour tout autre courriel."""
    # un avis Interac tient en quelques milliers de caractères : un courriel démesuré venu d'Internet ne fait jamais
    # tourner les recherches ci-dessous longtemps (analyse SonarQube du 2026-11-13, S8786)
    tout = re.sub(r"[ \t\xa0]+", " ", f"{sujet[:LIMITE_TEXTE]}\n{texte[:LIMITE_TEXTE]}")
    m = re.search(r"virement de ([\d\s.,]+)\s*\$\s*(?:\(CAD\)\s*)?(?:que vous avez envoyé )?à (.+?) (?:a été|a expiré|est)",
                  tout, re.I)
    if not m:  # avis en anglais (toutes les banques du Canada passent par Interac, demande du 2026-11-12) :
        # « Your transfer of $180.00 (CAD) to LEOPOLD X has been deposited. »
        m = re.search(r"(?:transfer|money transfer) of \$?\s*([\d\s.,]+)\s*\$?\s*(?:\(CAD\)\s*)?(?:that you sent )?"
                      r"to (.+?) (?:has been|was|has expired|is)\b", tout, re.I)
    if not m:
        return None
    bas = tout.lower()
    if "annulé" in bas or "annule" in bas or "cancel" in bas:
        etat = ANNULE
    elif "expiré" in bas or "expire" in bas:
        etat = EXPIRE
    elif "déposé" in bas or "depose" in bas or "deposited" in bas:
        etat = DEPOSE
    else:
        etat = ENVOYE
    lignes = [l.strip() for l in tout.splitlines() if l.strip()]

    def apres(etiquette: str) -> str:
        for i, l in enumerate(lignes):
            if re.match(rf"{etiquette}\s*:?\s*$", l, re.I) and i + 1 < len(lignes):
                return lignes[i + 1]
            m2 = re.match(rf"{etiquette}\s*:\s*(.+)$", l, re.I)
            if m2:
                return m2.group(1).strip()
        return ""

    date_virement = lire_date(apres("Date")) or date_courriel
    reference = apres(r"Num[ée]ro de r[ée]f[ée]rence") or apres(r"Reference (?:Number|#)")
    if not reference:  # date et référence sur la même ligne de tableau : « 20 août 2026 CAbsrsb6 »
        m3 = re.search(r"r[ée]f[ée]rence\s*:?\s*\n?.*?\b([A-Za-z0-9]{6,12})\b", tout, re.I | re.S)
        reference = m3.group(1) if m3 else ""
    return AvisPaiement(identifiant=identifiant, date_courriel=(date_courriel or date.today()).isoformat(),
                        date_virement=(date_virement or date.today()).isoformat(), montant=montant(m.group(1)),
                        beneficiaire=" ".join(m.group(2).split()), reference=reference, message=apres("Message") or apres("Memo"),
                        etat=etat)


def entetes_en_une_fois(boite, uids, champ: str = "MESSAGE-ID") -> dict[bytes, str]:
    """UID -> valeur d'un en-tête, pour tous les messages en UNE demande au serveur IMAP (lecture rapide)."""
    import re

    if not uids:
        return {}
    _, donnees = boite.uid("fetch", b",".join(sorted(uids, key=int)), f"(BODY.PEEK[HEADER.FIELDS ({champ})])")
    valeurs = {}
    for d in donnees:
        if isinstance(d, tuple):
            m = re.search(rb"UID (\d+)", d[0])
            v = re.search(rb"(?im)^" + champ.encode() + rb":\s*(\S+)", d[1] or b"")
            if m:
                valeurs[m.group(1)] = v.group(1).decode("ascii", "replace") if v else ""
    return valeurs


def lire_boite(serveur: str, utilisateur: str, mot_de_passe: str, depuis: date, port: int = 993,
               dossier: str = "INBOX", connus: set[str] = frozenset()) -> list[AvisPaiement]:
    """Avis Interac reçus depuis `depuis` (lecture seule : les courriels ne sont pas marqués comme lus). `connus` :
    identifiants (Message-ID) déjà lus, jamais retéléchargés."""
    avis = []
    with imaplib.IMAP4_SSL(serveur, port, ssl_context=ssl.create_default_context(), timeout=60) as boite:
        boite.login(utilisateur, mot_de_passe)
        boite.select(dossier, readonly=True)
        depuis_imap = (depuis - timedelta(days=1)).strftime("%d-%b-%Y")
        uids = set()
        for expediteur in EXPEDITEURS:
            _, donnees = boite.uid("search", None, "SINCE", depuis_imap, "FROM", expediteur)
            uids.update((donnees[0] or b"").split())
        if connus:
            identifiants = entetes_en_une_fois(boite, uids)
            uids = {u for u in uids if identifiants.get(u, "") not in connus}
        for uid in sorted(uids, key=int):
            _, donnees = boite.uid("fetch", uid, "(BODY.PEEK[])")
            brut = next((d[1] for d in donnees if isinstance(d, tuple)), None)
            if not brut:
                continue
            message = email.message_from_bytes(brut)
            sujet = str(make_header(decode_header(message.get("Subject", ""))))
            try:
                recu = parsedate_to_datetime(message.get("Date")).date()
            except (TypeError, ValueError):
                recu = None
            a = analyser(sujet, texte_du_message(message), message.get("Message-ID", f"uid-{uid.decode()}").strip(), recu)
            if a:
                avis.append(a)
    return avis
