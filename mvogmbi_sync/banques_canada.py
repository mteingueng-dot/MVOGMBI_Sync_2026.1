"""Banques et caisses du Canada (demande du propriétaire du 2026-11-12 : « on ne limite pas les paiements,
encaissements et rapprochement uniquement à Desjardins et BNC, utilise toutes les banques du Canada »).

Chaque banque a un code (celui des comptes bancaires de config.toml : [[comptes_bancaires]] format), son nom, ses
numéros d'institution (3 chiffres, ceux du chèque et des fichiers OFX : <BANKID>) et les mots qui la reconnaissent
sur un relevé. La lecture du relevé ne dépend pas de la banque : OFX / QFX (exporté par toutes les banques
canadiennes : « Microsoft Money », « Quicken », « Logiciel de comptabilité »), CSV, ou PDF par colonnes
(releves_bancaires.py) ; Desjardins et la Banque Nationale ont en plus leur lecteur PDF propre.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Banque:
    code: str
    nom: str
    institutions: tuple[str, ...] = ()
    mots: tuple[str, ...] = ()   # en minuscules ; le premier trouvé dans le texte du relevé l'emporte (ordre de BANQUES)


# ordre : les noms les plus précis d'abord (Simplii avant CIBC, Tangerine avant Scotia, Desjardins Ontario…)
BANQUES: tuple[Banque, ...] = (
    Banque("desjardins", "Desjardins", ("815", "829"), ("desjardins", "caisse populaire", "accèsd", "accesd")),
    Banque("bnc", "Banque Nationale (BNC)", ("006",), ("banque nationale", "national bank", "bnc.ca", "nbc.ca")),
    Banque("simplii", "Simplii Financial", ("010",), ("simplii",)),
    Banque("tangerine", "Tangerine", ("614",), ("tangerine",)),
    Banque("pcfinancial", "PC Financial", ("320",), ("pc financial", "services financiers le choix du président")),
    Banque("rbc", "RBC Banque Royale", ("003",), ("banque royale", "royal bank", "rbc")),
    Banque("td", "Banque TD (TD Canada Trust)", ("004",), ("td canada trust", "banque td", "td bank")),
    Banque("scotia", "Banque Scotia", ("002",), ("scotiabank", "banque scotia", "bank of nova scotia")),
    Banque("bmo", "BMO Banque de Montréal", ("001",), ("bmo", "banque de montréal", "bank of montreal")),
    Banque("cibc", "CIBC", ("010",), ("cibc", "banque canadienne impériale", "canadian imperial bank")),
    Banque("laurentienne", "Banque Laurentienne", ("039",), ("banque laurentienne", "laurentian bank")),
    Banque("hsbc", "HSBC Canada", ("016",), ("hsbc",)),
    Banque("eq", "EQ Bank (Banque Équitable)", ("623",), ("eq bank", "equitable bank", "banque équitable")),
    Banque("manuvie", "Banque Manuvie", ("540",), ("manuvie", "manulife bank", "banque manuvie")),
    Banque("atb", "ATB Financial", ("219",), ("atb financial",)),
    Banque("bcw", "Banque canadienne de l'Ouest", ("030",), ("canadian western bank", "banque canadienne de l'ouest")),
    Banque("alterna", "Alterna", ("842",), ("alterna",)),
    Banque("meridian", "Meridian", ("837",), ("meridian credit union", "meridian")),
    Banque("vancity", "Vancity", ("809",), ("vancity",)),
    Banque("coastcapital", "Coast Capital", ("809",), ("coast capital",)),
    Banque("servus", "Servus Credit Union", ("899",), ("servus",)),
    Banque("caisseuni", "UNI Coopération financière", ("865",), ("uni coopération", "uni financial", "caisse populaire acadienne")),
    Banque("autre", "Autre banque ou caisse", (), ()),
)

PAR_CODE = {b.code: b for b in BANQUES}
NOMS = {b.code: b.nom for b in BANQUES}


def nom(code: str) -> str:
    return NOMS.get(code, code or NOMS["autre"])


def code_du_nom(texte: str) -> str:
    """Nom affiché (ou code) -> code ; inconnu -> « autre »."""
    texte = (texte or "").strip()
    if texte in PAR_CODE:
        return texte
    return next((b.code for b in BANQUES if b.nom == texte), "autre")


def detecter(texte: str, institution: str = "") -> str:
    """Banque d'un relevé : la banque dont les mots reviennent le plus souvent (un virement vers une autre banque
    cité dans une description ne l'emporte pas sur l'en-tête répété à chaque page), sinon le n° d'institution
    (OFX <BANKID>) ; « autre » quand rien ne la reconnaît."""
    bas = re.sub(r"\s+", " ", (texte or "").lower())
    meilleur, score = "", 0
    for b in BANQUES:
        n = sum(len(re.findall(rf"(?<![a-z0-9]){re.escape(m)}(?![a-z0-9])", bas)) for m in b.mots)
        if n > score:
            meilleur, score = b.code, n
    if meilleur:
        return meilleur
    inst = "".join(c for c in (institution or "") if c.isdigit())
    if inst:
        inst = inst[-3:].zfill(3) if len(inst) <= 4 else inst[1:4]  # « 0006 » ou n° de transit « 0815… »
        codes = [b.code for b in BANQUES if inst in b.institutions]
        if codes:
            return codes[0]
    return "autre"
