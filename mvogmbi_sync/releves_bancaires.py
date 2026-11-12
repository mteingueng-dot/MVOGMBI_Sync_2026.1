"""Relevés de toutes les banques du Canada (demande du propriétaire du 2026-11-12) : OFX / QFX / QBO et CSV.

- OFX / QFX / QBO (« Microsoft Money », « Quicken », « QuickBooks » : téléchargement offert par toutes les banques et
  caisses canadiennes) : OFX 1.x (SGML, balises sans fin) et 2.x (XML) ; <STMTTRN> DTPOSTED, TRNAMT (signé),
  NAME / MEMO, FITID ; <LEDGERBAL> BALAMT = solde de fermeture, ouverture = fermeture − mouvements ; <BANKID>,
  <ACCTID>, <ORG> pour reconnaître la banque et le compte.
- CSV (« ; », « , » ou tabulation, avec ou sans ligne d'en-tête) : colonnes reconnues par leur nom (français ou
  anglais : Date, Description, Retrait / Débit / Withdrawal, Dépôt / Crédit / Deposit, Montant / Amount, Solde /
  Balance) ; sans en-tête (TD, Desjardins) : la date, le texte le plus long et les colonnes de nombres ; le sens des
  montants est vérifié avec la colonne du solde quand elle existe (solde = solde précédent + montant).
Les relevés PDF se lisent dans rapprochement.py (colonnes repérées sur l'en-tête, en français ou en anglais).
"""

from __future__ import annotations

import csv
import io
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

EXTENSIONS_OFX = (".ofx", ".qfx", ".qbo")
EXTENSIONS_CSV = (".csv",)
EXTENSIONS = (".pdf",) + EXTENSIONS_OFX + EXTENSIONS_CSV

MOIS_EN = {"jan": 1, "feb": 2, "fév": 2, "fev": 2, "mar": 3, "apr": 4, "avr": 4, "may": 5, "mai": 5, "jun": 6,
           "jui": 7, "jul": 7, "aug": 8, "aoû": 8, "aou": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12, "déc": 12}


def texte_du_fichier(chemin: Path) -> str:
    brut = Path(chemin).read_bytes()
    for codage in ("utf-8-sig", "cp1252"):
        try:
            return brut.decode(codage)
        except UnicodeDecodeError:
            continue
    return brut.decode("latin-1")


def montant(texte: str) -> Decimal | None:
    """« 1 234,56 », « -1,234.56 », « (12.50) », « 12.50- », « $1,234.56 », « 1234,56 CR » -> Decimal ; vide -> None."""
    t = (texte or "").strip().replace("\xa0", "").replace(" ", "").replace(" ", "").replace("$", "")
    t = t.replace("CAD", "").replace("cad", "")
    if not t:
        return None
    negatif = t.startswith("-") or t.endswith("-") or (t.startswith("(") and t.endswith(")"))
    if t.upper().endswith("DR"):
        negatif, t = True, t[:-2]
    elif t.upper().endswith("CR"):
        t = t[:-2]
    t = t.strip("-+()")
    if "," in t and "." in t:
        t = t.replace(",", "") if t.rfind(".") > t.rfind(",") else t.replace(".", "").replace(",", ".")
    elif "," in t:
        t = t.replace(",", ".") if re.fullmatch(r"\d+,\d{1,2}", t) else t.replace(",", "")
    try:
        valeur = Decimal(t)
    except InvalidOperation:
        return None
    return -valeur if negatif else valeur


def lire_date(texte: str, ordre: str = "jma") -> date | None:
    """« 2026-09-02 », « 2026/09/02 », « 20260902 », « 02/09/2026 » (ordre jma) ou « 9/2/2026 » (ordre mja),
    « 02 sep 2026 », « Sep 2, 2026 », « 2-Sep-26 »."""
    t = (texte or "").strip().lower().replace(".", "").replace(",", " ")
    m = re.match(r"(\d{4})[-/]?(\d{2})[-/]?(\d{2})", t)
    if m:
        try:
            return date(int(m[1]), int(m[2]), int(m[3]))
        except ValueError:
            return None
    m = re.match(r"(\d{1,2})[-/](\d{1,2})[-/](\d{2,4})$", t)
    if m:
        a, b, annee = int(m[1]), int(m[2]), int(m[3])
        annee += 2000 if annee < 100 else 0
        jour, mois = (a, b) if ordre == "jma" else (b, a)
        try:
            return date(annee, mois, jour)
        except ValueError:
            return None
    m = re.match(r"(\d{1,2})[\s-]+([a-zéû]{3,9})[\s-]+(\d{2,4})$", t) or None
    if m:
        jour, mois, annee = int(m[1]), MOIS_EN.get(m[2][:3]), int(m[3])
    else:
        m = re.match(r"([a-zéû]{3,9})[\s-]+(\d{1,2})\s+(\d{4})$", t)
        if not m:
            return None
        jour, mois, annee = int(m[2]), MOIS_EN.get(m[1][:3]), int(m[3])
    if not mois:
        return None
    annee += 2000 if annee < 100 else 0
    try:
        return date(annee, mois, jour)
    except ValueError:
        return None


# --------------------------------------------------------------------------------------------- OFX
def _valeur(bloc: str, balise: str) -> str:
    m = re.search(rf"<{balise}>\s*([^<\r\n]*)", bloc, re.I)
    return m.group(1).strip() if m else ""


def infos_ofx(texte: str) -> dict:
    return {"banque": _valeur(texte, "BANKID"), "compte": _valeur(texte, "ACCTID"), "org": _valeur(texte, "ORG"),
            "fid": _valeur(texte, "FID")}


def lire_ofx(chemin: Path):
    from .rapprochement import MouvementBanque, Releve

    texte = texte_du_fichier(chemin)
    releve = Releve(Path(chemin).name)
    releves = re.split(r"<STMTRS>", texte, flags=re.I)[1:] or [texte]
    comptes = [_valeur(r, "ACCTID") for r in releves]
    if len({c for c in comptes if c}) > 1:
        releve.remarques.append(f"le fichier contient {len(comptes)} comptes : seul le compte {comptes[0]} est lu "
                                "(téléchargez un fichier par compte)")
    bloc = releves[0]
    for rang, trn in enumerate(re.findall(r"<STMTTRN>(.*?)(?=</STMTTRN>|<STMTTRN>|</BANKTRANLIST>)", bloc, re.I | re.S)):
        jour = lire_date(_valeur(trn, "DTPOSTED")[:8])
        valeur = montant(_valeur(trn, "TRNAMT"))
        if not jour or valeur is None:
            releve.remarques.append(f"opération illisible ignorée ({_valeur(trn, 'FITID') or rang + 1})")
            continue
        nom, memo = _valeur(trn, "NAME"), _valeur(trn, "MEMO")
        description = " ".join(x for x in (nom, memo if memo and memo != nom else "") if x) or _valeur(trn, "TRNTYPE")
        if _valeur(trn, "CHECKNUM"):
            description += f" chèque {_valeur(trn, 'CHECKNUM')}"
        releve.mouvements.append(MouvementBanque(jour.isoformat(), description.strip(), valeur, None, releve.fichier,
                                                 len(releve.mouvements)))
    releve.mouvements.sort(key=lambda m: m.date)  # certaines banques donnent le plus récent d'abord
    for rang, m in enumerate(releve.mouvements):
        m.rang = rang
    debut, fin = lire_date(_valeur(bloc, "DTSTART")[:8]), lire_date(_valeur(bloc, "DTEND")[:8])
    jours = [m.date for m in releve.mouvements]
    releve.debut = debut.isoformat() if debut else (min(jours) if jours else "")
    releve.fin = fin.isoformat() if fin else (max(jours) if jours else "")
    ledger = re.search(r"<LEDGERBAL>(.*?)(?:</LEDGERBAL>|<AVAILBAL>|</STMTRS>|$)", bloc, re.I | re.S)
    solde = montant(_valeur(ledger.group(1), "BALAMT")) if ledger else None
    if solde is not None:
        releve.solde_fermeture = solde
        releve.solde_ouverture = solde - sum((m.montant for m in releve.mouvements), Decimal(0))
        courant = releve.solde_ouverture
        for m in releve.mouvements:
            courant += m.montant
            m.solde = courant
    return releve


# --------------------------------------------------------------------------------------------- CSV
NOMS_COLONNES = {
    "date": ("date", "date de l'opération", "date de transaction", "transaction date", "posted date", "date d'inscription",
             "date de l'opération", "date comptable", "posting date"),
    "description": ("description", "description 1", "description 2", "libellé", "libelle", "détails", "details",
                    "transaction", "payee", "bénéficiaire", "name", "nom", "memo", "mémo", "narrative", "opération"),
    "retrait": ("retrait", "retraits", "débit", "débits", "debit", "debits", "withdrawal", "withdrawals",
                "montant retiré", "funds out", "paid out", "sortie", "sorties", "montant du débit", "debit amount"),
    "depot": ("dépôt", "dépôts", "depot", "depots", "crédit", "crédits", "credit", "credits", "deposit", "deposits",
              "montant déposé", "funds in", "paid in", "entrée", "entrées", "montant du crédit", "credit amount"),
    "montant": ("montant", "amount", "cad$", "cad", "montant ($)", "amount ($)", "transaction amount"),
    "solde": ("solde", "balance", "solde ($)", "balance ($)", "running balance", "solde courant"),
}


ANGLAIS = {"transaction date", "posted date", "posting date", "amount", "withdrawal", "withdrawals", "deposit",
           "deposits", "balance", "debit", "credit", "description 1"}


def _nom_colonne(entete: str) -> str | None:
    t = re.sub(r"\s+", " ", (entete or "").strip().lower().strip('"')).replace("($)", "").strip()
    for genre, noms in NOMS_COLONNES.items():
        if t in noms:
            return genre
    for genre in ("retrait", "depot", "solde", "montant", "date", "description"):  # « Montant du retrait ($) »
        if any(n in t for n in NOMS_COLONNES[genre] if len(n) > 4):
            return genre
    return None


def _ordre_des_dates(valeurs: list[str], anglais: bool) -> str:
    """« jma » (02/09/2026) ou « mja » (9/2/2026) d'après les valeurs (un nombre > 12 tranche), sinon la langue."""
    for v in valeurs:
        m = re.match(r"\s*(\d{1,2})[-/](\d{1,2})[-/]\d{2,4}\s*$", v or "")
        if m and int(m[1]) > 12:
            return "jma"
        if m and int(m[2]) > 12:
            return "mja"
    return "mja" if anglais else "jma"


def lire_csv(chemin: Path):
    from .rapprochement import MouvementBanque, Releve

    texte = texte_du_fichier(chemin)
    releve = Releve(Path(chemin).name)
    try:
        dialecte = csv.Sniffer().sniff(texte[:4000], delimiters=";,\t")
    except csv.Error:
        dialecte = csv.excel
    rangees = [r for r in csv.reader(io.StringIO(texte), dialecte) if any(c.strip() for c in r)]
    if not rangees:
        releve.remarques.append("fichier vide")
        return releve
    # ligne d'en-tête : la première où l'on reconnaît une date et un montant (ou retrait / dépôt)
    colonnes: dict[str, list[int]] = {}
    debut_donnees = 0
    for i, r in enumerate(rangees[:15]):
        genres = [_nom_colonne(c) for c in r]
        if "date" in genres and ({"montant", "retrait", "depot"} & set(genres)):
            for j, g in enumerate(genres):
                if g:
                    colonnes.setdefault(g, []).append(j)
            debut_donnees = i + 1
            anglais = any(c.strip().lower() in ANGLAIS for c in r)
            break
    donnees = rangees[debut_donnees:]
    if not colonnes:
        anglais = False
        colonnes = _colonnes_sans_entete(donnees)
        if not colonnes:
            releve.remarques.append("colonnes Date / Montant introuvables dans le fichier CSV")
            return releve
    col_date = colonnes["date"][0]
    ordre = _ordre_des_dates([r[col_date] for r in donnees if len(r) > col_date], anglais)

    def cellule(r, genre):
        idx = colonnes.get(genre, [])
        return r[idx[0]] if idx and len(r) > idx[0] else ""

    lignes = []
    for r in donnees:
        jour = lire_date(r[col_date] if len(r) > col_date else "", ordre)
        if not jour:
            continue
        description = " ".join(r[j].strip() for j in colonnes.get("description", []) if len(r) > j and r[j].strip())
        if "montant" in colonnes:
            valeur = montant(cellule(r, "montant"))
        else:
            retrait, depot = montant(cellule(r, "retrait")), montant(cellule(r, "depot"))
            if retrait is None and depot is None:
                continue
            valeur = (depot or Decimal(0)) - abs(retrait or Decimal(0))
        if valeur is None:
            continue
        lignes.append([jour, description, valeur, montant(cellule(r, "solde"))])
    if len(lignes) > 1 and lignes[0][0] > lignes[-1][0]:
        lignes.reverse()  # plus récent d'abord (RBC, Scotia) : remis dans l'ordre du relevé
    soldes = [l[3] for l in lignes]
    if any(s is not None for s in soldes) and len(lignes) > 1:
        # sens des montants contrôlé par le solde : si l'inverse explique mieux les soldes, les montants sont inversés
        def accords(signe):
            return sum(1 for a, b in zip(lignes, lignes[1:]) if a[3] is not None and b[3] is not None
                       and a[3] + signe * b[2] == b[3])
        if accords(-1) > accords(1):
            for l in lignes:
                l[2] = -l[2]
    for jour, description, valeur, solde in lignes:
        releve.mouvements.append(MouvementBanque(jour.isoformat(), description, valeur, solde, releve.fichier,
                                                 len(releve.mouvements)))
    if releve.mouvements:
        releve.debut, releve.fin = releve.mouvements[0].date, releve.mouvements[-1].date
        premier, dernier = releve.mouvements[0], releve.mouvements[-1]
        if premier.solde is not None and dernier.solde is not None:
            releve.solde_ouverture = premier.solde - premier.montant
            releve.solde_fermeture = dernier.solde
            courant = releve.solde_ouverture
            for m in releve.mouvements:
                courant += m.montant
                if m.solde is not None and m.solde != courant:
                    m.remarque = f"solde attendu {courant} $, imprimé {m.solde} $"
                    courant = m.solde
    return releve


def _colonnes_sans_entete(rangees: list[list[str]]) -> dict[str, list[int]]:
    """CSV sans en-tête : colonne de dates, colonne de texte la plus longue, colonnes de nombres (2 colonnes dont une
    seule est remplie par ligne = retrait puis dépôt ; la dernière toujours remplie = solde ; une seule = montant)."""
    echantillon = rangees[:60]
    if not echantillon:
        return {}
    largeur = max(len(r) for r in echantillon)

    def part(j, test):
        valeurs = [r[j] for r in echantillon if len(r) > j]
        return sum(1 for v in valeurs if v.strip() and test(v)) / max(1, len(echantillon))

    dates = [j for j in range(largeur) if part(j, lambda v: lire_date(v) or lire_date(v, "mja")) > 0.8]
    if not dates:
        return {}
    nombres = [j for j in range(largeur) if j not in dates
               and part(j, lambda v: montant(v) is not None and re.search(r"\d[.,]\d{2}\b", v)) > 0.05
               and part(j, lambda v: montant(v) is None) < 0.05]
    textes = [j for j in range(largeur) if j not in dates and j not in nombres]
    if not nombres:
        return {}
    longueur = {j: sum(len(r[j]) for r in echantillon if len(r) > j) for j in textes}
    colonnes = {"date": [dates[0]], "description": [max(longueur, key=longueur.get)] if longueur else []}
    pleins = [j for j in nombres if part(j, lambda v: bool(v.strip())) > 0.95]
    solde = pleins[-1] if pleins and pleins[-1] == nombres[-1] and len(nombres) > 1 else None
    restants = [j for j in nombres if j != solde]
    if solde is not None:
        colonnes["solde"] = [solde]
    if len(restants) >= 2:
        colonnes["retrait"], colonnes["depot"] = [restants[0]], [restants[1]]
    else:
        colonnes["montant"] = [restants[0]]
    return colonnes
