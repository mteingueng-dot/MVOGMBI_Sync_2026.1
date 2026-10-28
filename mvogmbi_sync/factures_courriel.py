"""Factures fournisseurs reçues par courriel (demande du propriétaire du 2026-10-28).

La boîte est celle des avis de paiement (page Courriel, [boite_paiements], mot de passe dans le coffre-fort Windows),
lue en IMAP en lecture seule : aucun courriel n'est marqué comme lu, déplacé ni supprimé (BODY.PEEK). Les pièces
jointes PDF ou photo sont copiées dans donnees/factures_fournisseurs/, puis lues comme une facture déposée à la main
(page « 8. Factures fournisseurs »).

Courriels retenus ([factures_courriel]) :
- reçus depuis la date `depuis` ;
- avec `expediteurs` (adresses ou domaines séparés par des virgules) : toutes leurs pièces jointes ;
- sans `expediteurs` : seulement si le sujet ou le nom du fichier parle de facture (facture, invoice, fact., inv) ;
- avec `textes` (séparés par des points-virgules, ex. « 11983938 Canada Inc Brisk ») : toutes les pièces jointes des
  courriels qui contiennent l'un de ces textes (sujet, nom de l'expéditeur, texte du message ou nom du fichier ; sans
  tenir compte des majuscules, des accents ni des espaces en trop ; demande du propriétaire du 2026-10-28) ;
- jamais les avis Interac.
Chaque pièce jointe n'est prise qu'une fois (donnees/factures_courriel.json : n° de message + nom du fichier, et
empreinte du contenu).
"""

from __future__ import annotations

import email
import hashlib
import imaplib
import json
import re
import ssl
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from email.header import decode_header, make_header
from email.utils import parseaddr, parsedate_to_datetime
from pathlib import Path

from .fournisseurs import EXTENSIONS
from .paiements_courriel import EXPEDITEURS as EXPEDITEURS_INTERAC

MOTS_FACTURE = re.compile(r"factur|invoice|\bfact\b|\bfa[-# ]?\d|\binv\b|\binv[-# ]?\d", re.I)
MEMOIRE = "factures_courriel.json"


@dataclass
class PieceJointe:
    cle: str             # n° de message + nom du fichier
    expediteur: str
    sujet: str
    recu: date | None
    nom: str
    contenu: bytes

    @property
    def empreinte(self) -> str:
        return hashlib.sha1(self.contenu).hexdigest()[:16]  # même calcul que fournisseurs.empreinte


def _decoder(texte: str | None) -> str:
    try:
        return str(make_header(decode_header(texte or "")))
    except Exception:
        return texte or ""


def expediteurs_choisis(texte: str) -> list[str]:
    return [e.strip().lower() for e in re.split(r"[,;\s]+", texte or "") if e.strip()]


def textes_choisis(texte: str) -> list[str]:
    """« 11983938 Canada Inc Brisk; Grossiste ABC » -> textes à chercher (points-virgules ou lignes)."""
    return [x.strip() for x in re.split(r"[;\n]+", texte or "") if x.strip()]


def _normaliser(texte: str) -> str:
    import unicodedata

    sans_accents = "".join(c for c in unicodedata.normalize("NFD", texte or "") if unicodedata.category(c) != "Mn")
    return " ".join(sans_accents.casefold().split())


def contient_texte(textes: list[str], *contenus: str) -> bool:
    """L'un des textes choisis se trouve-t-il dans le courriel (majuscules, accents et espaces ignorés) ?"""
    tout = _normaliser(" ".join(contenus))
    return any(_normaliser(x) in tout for x in textes if _normaliser(x))


def texte_du_message(message: email.message.Message) -> str:
    """Texte lisible du courriel (parties texte et HTML, balises retirées), sans les pièces jointes."""
    morceaux = []
    for partie in message.walk():
        if partie.get_filename() or partie.get_content_maintype() != "text":
            continue
        try:
            contenu = partie.get_payload(decode=True) or b""
            texte = contenu.decode(partie.get_content_charset() or "utf-8", "replace")
        except Exception:
            continue
        if partie.get_content_subtype() == "html":
            import html

            texte = html.unescape(re.sub(r"(?s)<(script|style).*?</\1>|<[^>]+>", " ", texte))
        morceaux.append(texte)
    return " ".join(morceaux)


def retenue(expediteur: str, sujet: str, nom: str, expediteurs: list[str], texte_trouve: bool = False) -> bool:
    """La pièce jointe est-elle une facture à prendre ? (`texte_trouve` : le courriel contient un texte choisi)"""
    adresse = expediteur.lower()
    if any(adresse.endswith(d) for d in EXPEDITEURS_INTERAC):
        return False
    if Path(nom).suffix.lower() not in EXTENSIONS:
        return False
    if texte_trouve:
        return True
    if expediteurs:
        return any(adresse == e or adresse.endswith("@" + e.lstrip("@")) or adresse.endswith("." + e.lstrip("@"))
                   for e in expediteurs)
    return bool(MOTS_FACTURE.search(sujet) or MOTS_FACTURE.search(nom))


def pieces_du_message(message: email.message.Message, cle_message: str, expediteurs: list[str],
                      textes: list[str] = ()) -> list[PieceJointe]:
    nom_expediteur, expediteur = parseaddr(_decoder(message.get("From", "")))
    sujet = _decoder(message.get("Subject"))
    noms = [Path(_decoder(p.get_filename()).replace("\\", "/")).name for p in message.walk() if p.get_filename()]
    trouve = bool(textes) and contient_texte(textes, sujet, nom_expediteur, expediteur, texte_du_message(message),
                                             *noms)
    try:
        recu = parsedate_to_datetime(message.get("Date")).date()
    except (TypeError, ValueError):
        recu = None
    pieces = []
    for partie in message.walk():
        nom = _decoder(partie.get_filename())
        if not nom or partie.get_content_maintype() == "multipart":
            continue
        nom = Path(nom.replace("\\", "/")).name
        if not retenue(expediteur, sujet, nom, expediteurs, trouve):
            continue
        contenu = partie.get_payload(decode=True) or b""
        if contenu:
            pieces.append(PieceJointe(f"{cle_message}|{nom}", expediteur, sujet, recu, nom, contenu))
    return pieces


def lire_boite(serveur: str, utilisateur: str, mot_de_passe: str, depuis: date, expediteurs: list[str],
               port: int = 993, dossier: str = "INBOX", deja: set[str] = frozenset(),
               textes: list[str] = ()) -> list[PieceJointe]:
    """Pièces jointes de factures reçues depuis `depuis` (lecture seule)."""
    pieces = []
    with imaplib.IMAP4_SSL(serveur, port, ssl_context=ssl.create_default_context(), timeout=60) as boite:
        boite.login(utilisateur, mot_de_passe)
        boite.select(dossier, readonly=True)
        depuis_imap = (depuis - timedelta(days=1)).strftime("%d-%b-%Y")
        uids: set[bytes] = set()
        if expediteurs:
            for e in expediteurs:
                _, donnees = boite.uid("search", None, "SINCE", depuis_imap, "FROM", e)
                uids.update((donnees[0] or b"").split())
        else:
            _, donnees = boite.uid("search", None, "SINCE", depuis_imap)
            uids.update((donnees[0] or b"").split())
        if textes and expediteurs:
            # textes cherchés ici, pas par le serveur (sa recherche TEXT ne trouve rien, constat du 2026-10-28) :
            # tous les courriels de la période avec pièce jointe sont lus (pieces_du_message)
            _, donnees = boite.uid("search", None, "SINCE", depuis_imap)
            uids.update((donnees[0] or b"").split())
        for uid in sorted(uids, key=int):
            # en-têtes d'abord : un courriel sans pièce jointe ni « facture » n'est pas téléchargé en entier
            _, entete = boite.uid("fetch", uid, "(BODY.PEEK[HEADER.FIELDS (MESSAGE-ID CONTENT-TYPE)])")
            brut_entete = next((d[1] for d in entete if isinstance(d, tuple)), b"") or b""
            if b"multipart" not in brut_entete.lower():
                continue  # pas de pièce jointe
            m = re.search(rb"(?im)^message-id:\s*(\S+)", brut_entete)
            cle_message = m.group(1).decode("ascii", "replace") if m else f"uid-{uid.decode()}"
            if deja and any(c.startswith(cle_message + "|") for c in deja):
                continue
            _, donnees = boite.uid("fetch", uid, "(BODY.PEEK[])")
            brut = next((d[1] for d in donnees if isinstance(d, tuple)), None)
            if brut:
                pieces += pieces_du_message(email.message_from_bytes(brut), cle_message, expediteurs, textes)
    return pieces


def nom_fichier(piece: PieceJointe) -> str:
    """« 2026-10-27_fournisseur.com_Facture 14402.pdf » : date de réception et domaine de l'expéditeur."""
    domaine = piece.expediteur.split("@")[-1] if "@" in piece.expediteur else piece.expediteur
    propre = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", f"{piece.recu or date.today()}_{domaine}_{piece.nom}")
    return propre[:150]


class Memoire:
    """Pièces jointes déjà prises (jamais deux fois, même si la facture a été écartée ou importée depuis)."""

    def __init__(self, racine: Path):
        self.chemin = Path(racine) / "donnees" / MEMOIRE
        self.prises: dict[str, dict] = json.loads(self.chemin.read_text(encoding="utf-8")) if self.chemin.exists() \
            else {}

    def deja(self, piece: PieceJointe) -> bool:
        return piece.cle in self.prises or any(p.get("empreinte") == piece.empreinte for p in self.prises.values())

    def noter(self, piece: PieceJointe, fichier: str) -> None:
        self.prises[piece.cle] = {"empreinte": piece.empreinte, "expediteur": piece.expediteur, "sujet": piece.sujet,
                                  "recu": piece.recu.isoformat() if piece.recu else "", "fichier": fichier,
                                  "pris_le": datetime.now().isoformat(timespec="seconds")}

    def enregistrer(self) -> None:
        self.chemin.parent.mkdir(parents=True, exist_ok=True)
        provisoire = self.chemin.with_suffix(".tmp")
        provisoire.write_text(json.dumps(self.prises, ensure_ascii=False, indent=1), encoding="utf-8")
        provisoire.replace(self.chemin)


def configuree(config_toml: dict) -> bool:
    b = config_toml.get("boite_paiements", {})
    return bool(b.get("serveur") and b.get("utilisateur"))


def recuperer(racine: Path, config_toml: dict) -> list[Path]:
    """Copie dans le dossier des factures les nouvelles pièces jointes ; renvoie les fichiers créés."""
    from . import coffre
    from .fournisseurs import Registre

    if not configuree(config_toml):
        raise RuntimeError("Boîte de courriel non configurée (« Administration > Courriel », carte « Avis de paiement »).")
    b, c = config_toml.get("boite_paiements", {}), config_toml.get("factures_courriel", {})
    mot_de_passe = coffre.lire(coffre.BOITE_PAIEMENTS)
    if not mot_de_passe:
        raise RuntimeError("Mot de passe de la boîte de courriel absent (« Administration > Courriel »).")
    depuis = date.fromisoformat(str(c.get("depuis") or b.get("depuis") or date.today() - timedelta(days=30)))
    registre = Registre(racine)
    memoire = Memoire(racine)
    connues = {f.empreinte for f in registre.factures}
    pieces = lire_boite(b["serveur"], b["utilisateur"], mot_de_passe, depuis,
                        expediteurs_choisis(str(c.get("expediteurs", ""))), int(b.get("port", 993)),
                        str(c.get("dossier") or "INBOX"), set(memoire.prises), textes_choisis(str(c.get("textes", ""))))
    registre.dossier.mkdir(parents=True, exist_ok=True)
    crees = []
    for piece in pieces:
        if memoire.deja(piece):
            continue
        if piece.empreinte in connues:  # déjà déposée à la main
            memoire.noter(piece, "")
            continue
        cible = registre.dossier / nom_fichier(piece)
        numero = 2
        while cible.exists():
            cible = cible.with_name(f"{Path(nom_fichier(piece)).stem} ({numero}){cible.suffix}")
            numero += 1
        cible.write_bytes(piece.contenu)
        memoire.noter(piece, cible.name)
        crees.append(cible)
    memoire.enregistrer()
    return crees


def lire_nouvelles(racine: Path) -> list:
    """Lit les nouveaux fichiers du dossier des factures (sans l'interface : traitement de nuit) et les ajoute au
    registre, avec les fournisseurs et articles Sage proposés. Renvoie les factures ajoutées."""
    from .articles_sage import lire_copie
    from .fournisseurs import (A_SAISIR, Facture, MemoireCorrespondance, Registre, completer, empreinte,
                               etat_apres_controle, lire_copie_fournisseurs, lire_facture)

    registre = Registre(racine)
    memoire = MemoireCorrespondance(racine)
    fournisseurs_sage = lire_copie_fournisseurs(racine)
    articles_sage = lire_copie(Path(racine) / "donnees" / "articles_sage.csv")
    lues = []
    for chemin in registre.nouveaux_fichiers():
        try:
            facture = lire_facture(chemin)
        except Exception as exc:
            facture = Facture(chemin.name, empreinte(chemin), etat=A_SAISIR, remarques=[f"lecture impossible : {exc}"])
        completer(facture, memoire, fournisseurs_sage, articles_sage)
        facture.etat = etat_apres_controle(facture, facture.controles(set(fournisseurs_sage) or None))
        lues.append(facture)
    if lues:
        registre.factures.extend(lues)
        registre.enregistrer()
    return lues
