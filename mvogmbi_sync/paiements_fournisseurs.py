"""Paiements aux fournisseurs : avis Interac lus dans la boîte -> facture fournisseur dans Sage -> paiement à saisir.

Registre : donnees/paiements_fournisseurs.json (un avis par Message-ID : jamais traité deux fois).
Rapprochement proposé, confirmé par le propriétaire :
- fournisseur : bénéficiaire mémorisé (donnees/correspondance_fournisseurs.json, « beneficiaires »), sinon le nom le
  plus ressemblant parmi les fournisseurs Sage ;
- facture : n° cité dans le message (« Facture#1264 », même écrit « FA-1264 » dans Sage), sinon la seule facture
  impayée du fournisseur au même montant ;
- déjà saisi : un paiement du même montant, le même jour, au compte de paiement, existe déjà pour ce fournisseur.
Dans Sage (fenêtre Paiements) : compte 1055, « Payé par : Comptant », à la date du virement (choix du propriétaire).
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path

from rapidfuzz import fuzz, process

from .correspondance import normaliser
from .import_achats import meme_numero
from .paiements_courriel import ANNULE, EXPIRE, AvisPaiement

A_RELIER = "À relier"
PROPOSE = "Proposé"
CONFIRME = "Confirmé (à saisir)"
DEJA = "Déjà dans Sage"
SAISI = "Saisi dans Sage"
IGNORE = "Ignoré"
NON_PAYE = "Annulé / expiré"
ETATS = [A_RELIER, PROPOSE, CONFIRME, DEJA, SAISI, IGNORE, NON_PAYE]


@dataclass
class FactureOuverte:
    fournisseur: str
    numero: str
    date: str
    solde: Decimal


@dataclass
class Paiement:
    avis: AvisPaiement
    fournisseur_sage: str = ""
    facture: str = ""
    solde_facture: Decimal | None = None
    etat: str = A_RELIER
    remarque: str = ""

    def en_dict(self) -> dict:
        d = asdict(self)
        d["avis"] = self.avis.en_dict()
        d["solde_facture"] = None if self.solde_facture is None else str(self.solde_facture)
        return d

    @classmethod
    def depuis_dict(cls, d: dict) -> "Paiement":
        return cls(**{**d, "avis": AvisPaiement.depuis_dict(d["avis"]),
                      "solde_facture": None if d.get("solde_facture") in (None, "") else Decimal(d["solde_facture"])})


class RegistrePaiements:
    def __init__(self, racine: Path):
        self.chemin = Path(racine) / "donnees" / "paiements_fournisseurs.json"
        self.paiements: list[Paiement] = []
        if self.chemin.exists():
            self.paiements = [Paiement.depuis_dict(d) for d in json.loads(self.chemin.read_text(encoding="utf-8"))]

    def enregistrer(self) -> None:
        self.chemin.parent.mkdir(parents=True, exist_ok=True)
        provisoire = self.chemin.with_suffix(".tmp")
        provisoire.write_text(json.dumps([p.en_dict() for p in self.paiements], ensure_ascii=False, indent=1),
                              encoding="utf-8")
        provisoire.replace(self.chemin)

    def ajouter(self, avis: list[AvisPaiement]) -> list[Paiement]:
        connus = {p.avis.identifiant for p in self.paiements}
        nouveaux = [Paiement(a, etat=NON_PAYE if a.etat in (ANNULE, EXPIRE) else A_RELIER)
                    for a in avis if a.identifiant not in connus]
        self.paiements.extend(nouveaux)
        self.paiements.sort(key=lambda p: (p.avis.date_virement, p.avis.identifiant))
        return nouveaux


# --------------------------------------------------------------------------------------------- lecture de Sage
def factures_ouvertes(base) -> list[FactureOuverte]:
    """Factures d'achat dont le solde n'est pas nul (factures positives seulement : les notes de crédit sont exclues)."""
    lignes = base.requete(
        "SELECT v.sName fournisseur, t.sSource numero, t.dtDate date, ROUND(SUM(d.dAmount), 2) solde "
        "FROM tventr t JOIN tvendor v ON v.lId = t.lVenId JOIN tventrdt d ON d.lVenTrId = t.lId "
        "GROUP BY t.lId, v.sName, t.sSource, t.dtDate HAVING ROUND(SUM(d.dAmount), 2) > 0 ORDER BY t.dtDate")
    return [FactureOuverte(l["fournisseur"].strip(), (l["numero"] or "").strip(), l["date"].date().isoformat(),
                           Decimal(str(l["solde"]))) for l in lignes]


def paiements_existants(base, compte: int, depuis: date) -> set[tuple[str, str, Decimal]]:
    """(fournisseur, date, montant) des paiements déjà saisis au compte de paiement depuis `depuis`."""
    lignes = base.requete(
        "SELECT v.sName fournisseur, d.dtDate date, -d.dAmount montant FROM tventrdt d JOIN tventr t ON t.lId = d.lVenTrId "
        "JOIN tvendor v ON v.lId = t.lVenId WHERE d.nTranType = 1 AND d.lBnkAcctId = %s AND d.dtDate >= %s",
        (compte, depuis.isoformat()))
    return {(l["fournisseur"].strip(), l["date"].date().isoformat(), Decimal(str(l["montant"])).quantize(Decimal("0.01")))
            for l in lignes}


# --------------------------------------------------------------------------------------------- rapprochement
# Mots qui ne distinguent pas un fournisseur (« Rodrigue Fotso Transport » n'est pas « QBS Transport »)
MOTS_VIDES = {"inc", "ltee", "ltd", "les", "la", "le", "de", "du", "des", "et", "and", "cie", "enr", "co", "aliments",
              "foods", "transport", "transporteur", "maison", "fruits", "import", "imports", "export", "distribution",
              "marche", "quebec", "canada", "sherbrooke", "montreal", "payez", "emportez"}


def _mots(nom: str) -> set[str]:
    texte = re.sub(r"[^a-z0-9 ]", " ", normaliser(nom).replace(".", "").replace("/", " ").replace("-", " "))
    return {m for m in texte.split() if m not in MOTS_VIDES and len(m) > 1}


def _pareils(a: str, b: str) -> bool:
    return a == b if min(len(a), len(b)) <= 4 else fuzz.ratio(a, b) >= 88  # « amr » ≠ « amir »


def proposer_fournisseur(beneficiaire: str, fournisseurs: list[str], memoire: dict[str, str]) -> str:
    """Bénéficiaire mémorisé, sinon le fournisseur qui partage avec lui les mots les plus distinctifs."""
    connu = memoire.get(normaliser(beneficiaire))
    if connu:
        return connu
    mots_beneficiaire = _mots(beneficiaire)
    if not fournisseurs or not mots_beneficiaire:
        return ""
    mots_fournisseurs = {f: _mots(f) for f in fournisseurs}
    frequence: dict[str, int] = {}
    for mots in mots_fournisseurs.values():
        for m in mots:
            frequence[m] = frequence.get(m, 0) + 1
    scores = []
    for f, mots in mots_fournisseurs.items():
        poids = sum(1 / frequence[x] for m in mots_beneficiaire for x in mots if _pareils(m, x))
        if poids:
            scores.append((poids, fuzz.token_set_ratio(normaliser(beneficiaire), normaliser(f)), f))
    scores.sort(reverse=True)
    if not scores or scores[0][0] < 0.99:  # au moins un mot propre à ce fournisseur, ou deux mots partagés
        return ""
    if len(scores) > 1 and scores[1][:2] == scores[0][:2]:
        return ""  # deux fournisseurs aussi plausibles : au propriétaire de choisir
    return scores[0][2]


def rapprocher(p: Paiement, fournisseurs: list[str], memoire: dict[str, str], ouvertes: list[FactureOuverte],
               existants: set[tuple[str, str, Decimal]]) -> None:
    """Propose fournisseur et facture pour un avis « à relier » (ne touche pas aux choix confirmés)."""
    if p.etat not in (A_RELIER, PROPOSE):
        return
    if not p.fournisseur_sage:
        p.fournisseur_sage = proposer_fournisseur(p.avis.beneficiaire, fournisseurs, memoire)
    if not p.fournisseur_sage:
        p.etat = A_RELIER
        return
    if (p.fournisseur_sage, p.avis.date_virement, p.avis.montant) in existants:
        p.etat, p.remarque = DEJA, "paiement du même montant, le même jour, déjà saisi dans Sage"
        return
    candidates = [f for f in ouvertes if f.fournisseur == p.fournisseur_sage]
    choisie = next((f for f in candidates for n in p.avis.numeros_facture if meme_numero(f.numero, n)), None)
    if not choisie:
        memes_montants = [f for f in candidates if f.solde == p.avis.montant]
        choisie = memes_montants[0] if len(memes_montants) == 1 else None
    if choisie:
        p.facture, p.solde_facture = choisie.numero, choisie.solde
        p.remarque = "" if choisie.solde == p.avis.montant else \
            f"écart : virement {p.avis.montant} $ / solde de la facture {choisie.solde} $"
    p.etat = PROPOSE if p.facture else A_RELIER


# --------------------------------------------------------------------------------------------- saisie dans Sage
def payer_sur_bureau_cache(racine, config_toml: dict, journal=print) -> dict:
    """Exécuté sur le bureau caché : ouvre Sage (fermé au départ), saisit chaque paiement confirmé, referme Sage.

    Renvoie {"payes": [...], "a_verifier": [...], "erreur": ""} pour le compte rendu.
    """
    from . import coffre
    from .__main__ import executable_import
    from .robot_paiements import appliquer
    from .sage_bureau import SessionSage, executable_sage

    c = config_toml.get("paiements", {})
    compte = str(c.get("compte", "1055"))
    mode = str(c.get("mode", "Comptant"))
    fichier = config_toml.get("sage_import", {}).get("fichier_entreprise")
    bilan = {"payes": [], "a_verifier": [], "erreur": ""}
    registre = RegistrePaiements(racine)
    a_saisir = [p for p in registre.paiements if p.etat == CONFIRME and p.fournisseur_sage and p.facture]
    if not a_saisir:
        return bilan
    exe = executable_sage(executable_import())
    if not exe:
        bilan["erreur"] = "Sage50Accounting.exe introuvable."
        return bilan
    session = SessionSage(exe, journal)
    try:
        utilisateur = str(config_toml.get("sage_import", {}).get("utilisateur", "sysadmin"))
        session.ouvrir(fichier, utilisateur, coffre.lire(coffre.SAGE_IMPORT, ""))
        journal(f"{len(a_saisir)} paiement(s) confirmé(s) à saisir.")
        session.ouvrir_paiements()
        for p, r in appliquer(config_toml, a_saisir, compte, mode, journal):
            texte = (f"{p.avis.date_virement} : {p.avis.montant:,.2f} $ à {p.fournisseur_sage}, facture {p.facture} "
                     f"(virement {p.avis.reference})")
            (bilan["payes"] if r.traite else bilan["a_verifier"]).append(
                texte + ("" if r.traite else " — NON saisi : " + " ".join(r.messages)))
    except Exception as exc:
        bilan["erreur"] = str(exc)
        journal(f"Erreur : {exc}")
    finally:
        registre.enregistrer()  # les paiements saisis passent à « Saisi dans Sage »
        session.fermer()
    return bilan
