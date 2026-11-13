"""Rapprochement bancaire du compte Desjardins (1055) : relevés PDF de la banque <-> écritures de Sage.

Relevés : donnees/releves_desjardins/*.pdf (bouton « Charger des relevés… »), registre releves.json (décisions du
propriétaire par mouvement : compte Sage à utiliser, ignoré).
Lecture d'un relevé PDF numérique (pdfplumber) par colonnes : la ligne d'en-tête donne la position des colonnes
Retrait / Dépôt / Solde ; chaque montant est rangé dans la colonne la plus proche de son bord droit. Contrôle :
solde d'ouverture + dépôts − retraits = solde de fermeture.
Sage : lignes du compte 10550000 dans tjentact (montant > 0 = entrée) jointes à tjourent (date, source, description) ;
solde = taccount.dYtcLY (ouverture de l'exercice) + mouvements jusqu'à la date.
Rapprochement : même montant, même sens, date Sage de 7 jours avant à 3 jours après la date de banque (la plus
proche) ; sinon 2 ou 3 écritures Sage de la même période dont la somme égale le mouvement de banque.
Virements Interac reçus et dépôts d'espèces au guichet (règles du propriétaire, 2026-10-26) : ils font partie des
espèces des ventes ; absents de Sage, ils ne vont pas en écriture de journal : la page Encaissements les encaisse sur
les factures de vente (encaissements.especes_a_encaisser).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from itertools import combinations
from pathlib import Path

from .factures_fournisseurs import MOIS

COMPTE_BANQUE = 10550000
AVANT, APRES = 7, 3  # fenêtre de dates acceptée pour une écriture Sage autour du mouvement de banque

RAPPROCHE = "Rapproché"
A_SAISIR = "Absent de Sage"
CONFIRME = "Compte choisi (à saisir)"
SAISI = "Saisi dans Sage"
IGNORE = "Ignoré"
EN_CIRCULATION = "Seulement dans Sage"
A_ENCAISSER = "À encaisser sur les ventes"

# Virement Interac reçu : « VRW Virement Interac de » (Desjardins), « Virement Interac reçu », « INTERAC e-Transfer
# from », « E-TRANSFER RECEIVED / AUTODEPOSIT » (autres banques du Canada, demande du propriétaire du 2026-11-12)
INTERAC = re.compile(r"virement\s+interac\s+(de\b|re[çc]u)|interac\s+e-?transfer\s+(from|received|re[çc]u)|"
                     r"e-?transfer\s+(received|from|autodeposit|auto-deposit)|auto-?d[ée]p[ôo]t|"
                     r"virement\s+(?:par\s+)?courriel\s+re[çc]u|transfert\s+interac\s+re[çc]u", re.I)
# Espèces déposées au guichet : « DGA Dépôt au GA » (Desjardins), « Dépôt au guichet », « ATM DEPOSIT »,
# « ABM DEPOSIT », « BRANCH DEPOSIT », « Dépôt en succursale », « CASH DEPOSIT »…
DEPOT_ESPECES = re.compile(r"^DGA\b|d.p.t au GA|d[ée]p[ôo]t\s+(au\s+guichet|guichet|en\s+succursale|au\s+comptoir|"
                           r"d.esp[èe]ces|comptant)|\b(atm|abm|branch|cash|counter|teller)\s+deposit|"
                           r"deposit\s+(at\s+)?(atm|abm|branch)", re.I)
A_PAIE = "Paie absente de Sage"
SALAIRE = re.compile(r"salaire|payroll|salary|d[ée]p[ôo]t\s+de\s+paie", re.I)  # « PPW Paiement internet à / Depot Salaire/PAY05012026 »
REFERENCE_PAIE = re.compile(r"PAYE?(\d{8})", re.I)
DELAI_PAIE = 120  # jours : un salaire peut être versé longtemps après la paie de Sage

MONTANT = re.compile(r"^-?\$?(?:\d{1,3}(?:[,   ]?\d{3})*)?[.,]\d{2}-?$")  # « 1,000.00 », « ,15 » (RBC) : milliers à la virgule (banques anglophones)


# --------------------------------------------------------------------------------------------- modèles
@dataclass
class MouvementBanque:
    date: str
    description: str
    montant: Decimal          # > 0 dépôt, < 0 retrait
    solde: Decimal | None = None
    releve: str = ""
    rang: int = 0             # ordre dans le relevé (deux mouvements identiques le même jour restent distincts)
    etat: str = A_SAISIR
    sage: list[int] = field(default_factory=list)  # n° d'écritures Sage rapprochées
    compte: str = ""          # compte Sage choisi pour la saisie (ex. 5450)
    remarque: str = ""
    compte_banque: str = ""   # compte Sage de la banque du relevé (vide = Desjardins, [encaissements] compte_depot)

    @property
    def cle(self) -> str:
        return f"{self.releve}|{self.rang}"


@dataclass
class MouvementSage:
    ident: int
    date: str
    source: str
    description: str
    montant: Decimal
    rapproche: bool = False


@dataclass
class Releve:
    fichier: str
    debut: str = ""
    fin: str = ""
    solde_ouverture: Decimal | None = None
    solde_fermeture: Decimal | None = None
    mouvements: list[MouvementBanque] = field(default_factory=list)
    remarques: list[str] = field(default_factory=list)

    def controles(self) -> list[str]:
        problemes = list(self.remarques)
        if not self.mouvements:
            problemes.append("aucun mouvement lu")
        if self.solde_ouverture is not None and self.solde_fermeture is not None:
            calcule = self.solde_ouverture + sum((m.montant for m in self.mouvements), Decimal(0))
            if calcule != self.solde_fermeture:
                problemes.append(f"solde calculé {calcule} $ ≠ solde de fermeture {self.solde_fermeture} $")
        return problemes


# --------------------------------------------------------------------------------------------- lecture du PDF
def _montant(texte: str) -> Decimal:
    t = texte.replace(" ", "").replace(" ", "").replace(" ", "").replace("$", "")
    negatif = t.endswith("-") or t.startswith("-")
    t = t.strip("-").replace(",", ".") if t.count(",") == 1 and t.rfind(",") > t.rfind(".") else t.strip("-").replace(",", "")
    valeur = Decimal(t)
    return -valeur if negatif else valeur


_MOIS3 = {"jan": 1, "fév": 2, "fev": 2, "feb": 2, "mar": 3, "avr": 4, "apr": 4, "mai": 5, "may": 5, "jun": 6,
          "jul": 7, "aoû": 8, "aou": 8, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "déc": 12, "dec": 12}


def _date_ligne(texte: str, fin: date | None) -> date | None:
    """« 2026-09-02 », « 02/09 », « 02 SEP », « 2 sept. » ; l'année vient de la période du relevé."""
    t = texte.lower().replace(".", "").strip()
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})$", t)
    if m:
        return date(int(m[1]), int(m[2]), int(m[3]))
    m = re.match(r"(\d{1,2})[/ -]?([a-zéû]{3,9}|\d{1,2})$", t)
    if m:
        jour = int(m[1])
        mois = int(m[2]) if m[2].isdigit() else (MOIS.get(m[2]) or _MOIS3.get(m[2][:3]))
    else:
        m = re.match(r"([a-zéû]{3,9})[ -]?(\d{1,2})$", t)  # « Sep 02 » (banques anglophones)
        if not m:
            return None
        jour, mois = int(m[2]), MOIS.get(m[1]) or _MOIS3.get(m[1][:3])
    if not mois or not 1 <= mois <= 12:
        return None
    annee = fin.year if fin else date.today().year
    if fin and mois > fin.month + 1:  # relevé de janvier contenant des jours de décembre
        annee -= 1
    try:
        return date(annee, mois, jour)
    except ValueError:
        return None


def _lignes(page) -> list[list[dict]]:
    """Mots de la page regroupés en lignes (même hauteur à 3 points près), de gauche à droite."""
    lignes: list[list[dict]] = []
    for mot in sorted(page.extract_words(keep_blank_chars=False, x_tolerance=1.5), key=lambda m: (round(m["top"]), m["x0"])):
        if lignes and abs(lignes[-1][0]["top"] - mot["top"]) <= 3:
            lignes[-1].append(mot)
        else:
            lignes.append([mot])
    return [sorted(l, key=lambda m: m["x0"]) for l in lignes]


def _fusionner_nombres(mots: list[dict]) -> list[dict]:
    """« 1 » « 842,10 » (séparateur de milliers imprimé en espace) -> un seul mot « 1842,10 »."""
    sortie: list[dict] = []
    for mot in mots:
        precedent = sortie[-1] if sortie else None
        if (precedent and re.fullmatch(r"-?\d{1,3}", precedent["text"]) and re.match(r"\d{3}([ .,]|$)", mot["text"])
                and mot["x0"] - precedent["x1"] < 6):
            sortie[-1] = {**precedent, "text": precedent["text"] + mot["text"], "x1": mot["x1"]}
        else:
            sortie.append(dict(mot))
    return sortie


def _periode(texte: str) -> tuple[date | None, date | None]:
    """« du 1er février au 28 février 2026 » : la première date prend l'année de la seconde si elle n'en a pas."""
    from .factures_fournisseurs import lire_date

    m = re.search(r"\bdu\s+(\d{1,2})(?:er)?\s+([a-zéû]+)\.?\s*(\d{4})?\s+au\s+(\d{1,2})(?:er)?\s+([a-zéû]+)\.?\s+(\d{4})",
                  texte, re.IGNORECASE)
    if m:
        fin = lire_date(f"{m[4]} {m[5]} {m[6]}")
        annee = int(m[3]) if m[3] else (fin.year if fin else date.today().year)
        debut = lire_date(f"{m[1]} {m[2]} {annee}")
        if debut and fin and debut > fin:  # « du 1er décembre au 31 janvier 2027 »
            debut = debut.replace(year=debut.year - 1)
        return debut, fin
    m = re.search(r"p[ée]riode\s+(\d{2})-(\d{2})\s+(?:à|au|-)\s+(\d{2})-(\d{2})\s+(\d{4})", texte, re.IGNORECASE)
    if m:  # « Pour la période 03-01 à 03-31 2023 » (UNI : mois-jour)
        try:
            fin = date(int(m[5]), int(m[3]), int(m[4]))
            debut = date(int(m[5]), int(m[1]), int(m[2]))
            return (debut.replace(year=debut.year - 1) if debut > fin else debut), fin
        except ValueError:
            pass
    m = re.search(r"([a-z]{3,9})\.?\s+(\d{1,2}),?\s*(\d{4})?\s*(?:to|-|–)\s*([a-z]{3,9})\.?\s+(\d{1,2}),?\s+(\d{4})",
                  texte, re.IGNORECASE)  # « From Sep 1, 2026 to Sep 30, 2026 » (banques anglophones)
    if m and _MOIS3.get(m[1][:3].lower()) and _MOIS3.get(m[4][:3].lower()):
        try:
            fin = date(int(m[6]), _MOIS3[m[4][:3].lower()], int(m[5]))
            debut = date(int(m[3]) if m[3] else fin.year, _MOIS3[m[1][:3].lower()], int(m[2]))
            return (debut.replace(year=debut.year - 1) if debut > fin else debut), fin
        except ValueError:
            pass
    dates = [d for d in (lire_date(x) for x in re.findall(r"\d{4}-\d{2}-\d{2}", texte)) if d]
    return (min(dates), max(dates)) if dates else (None, None)


COLONNES = {"frais": "frais", "retrait": "retrait", "retraits": "retrait", "débit": "retrait", "débits": "retrait",
            "debit": "retrait", "dépôt": "depot", "dépôts": "depot", "depot": "depot", "depots": "depot",
            "crédit": "depot", "crédits": "depot", "credit": "depot", "solde": "solde",
            # autres banques du Canada (en-têtes en anglais ou autrement libellés)
            "fees": "frais", "withdrawal": "retrait", "withdrawals": "retrait", "withdrawn": "retrait",
            "debits": "retrait", "deducted": "retrait", "retirés": "retrait", "déduits": "retrait",
            "chèques": "retrait", "cheques": "retrait", "deposit": "depot", "deposits": "depot",
            "deposited": "depot", "credits": "depot", "added": "depot", "déposés": "depot", "ajoutés": "depot",
            "balance": "solde", "amount": "montant", "date": "date"}
OUVERTURE = re.compile(r"solde (reporté|précédent|d'ouverture|au début|initial|antérieur)|ancien solde|"
                       r"opening balance|balance forward|previous balance|starting balance|beginning balance|"
                       r"balance brought forward", re.I)
FERMETURE = re.compile(r"nouveau solde|solde de fermeture|solde de cl[ôo]ture|^\S*\s*\S*\s*solde courant\b|solde à la fin|solde final|closing balance|ending balance|"
                       r"new balance|balance at end|balance carried forward", re.I)


def _genre_colonne(mot: dict) -> str | None:
    return COLONNES.get(mot["text"].lower().strip(".:()$"))


def _est_entete(mots: list[dict], bas: str) -> bool:
    """Ligne d'en-tête des colonnes : « Description … Solde » (Desjardins) ou, pour toute banque, un mot de solde
    avec au moins une colonne de retrait ou de dépôt (« Withdrawals ($) Deposits ($) Balance ($) »), sans montant."""
    if "solde" in bas and "description" in bas:
        return True
    genres = {_genre_colonne(m) for m in mots}
    return ("solde" in genres and (len({"retrait", "depot", "frais"} & genres) >= 2 or "montant" in genres)
            and not any(MONTANT.match(m["text"]) for m in mots))
# Fin du compte principal : les sections suivantes du relevé (parts sociales, sommaire des frais) sont ignorées
PIED_DE_PAGE = re.compile(r"^(page\s+)?\d+\s*(de|of|/|sur)\s*\d+$", re.I)
FIN_DU_COMPTE = re.compile(r"^(compte d'[ée]pargne et de placement|sommaire des frais|part de qualification)")


_RELEVES_LUS: dict[str, tuple] = {}


def _releve_en_dict(r: Releve) -> dict:
    from dataclasses import asdict

    return json.loads(json.dumps(asdict(r), default=str))


def _releve_depuis_dict(d: dict) -> Releve:
    def dec(v):
        return None if v is None else Decimal(v)

    mouvements = [MouvementBanque(m["date"], m["description"], Decimal(m["montant"]), dec(m["solde"]), m["releve"],
                                  m["rang"], m["etat"], list(m["sage"]), m["compte"], m["remarque"])
                  for m in d["mouvements"]]
    return Releve(d["fichier"], d["debut"], d["fin"], dec(d["solde_ouverture"]), dec(d["solde_fermeture"]),
                  mouvements, list(d["remarques"]))


def lire_releve_garde(chemin: Path) -> Releve:
    """Relevé lu une seule fois tant que le fichier ne change pas (date et taille) : gardé en mémoire et dans
    « releves_lus.cache.json » du dossier des relevés. Lire les PDF prenait environ 3 s à chaque suivi des ventes
    ou rapprochement (mesuré le 2026-10-30). Chaque appel rend une copie neuve (les décisions s'y appliquent)."""
    chemin = Path(chemin)
    etat = chemin.stat()
    signature = [etat.st_mtime_ns, etat.st_size]
    deja = _RELEVES_LUS.get(str(chemin))
    if deja and deja[0] == signature:
        return _releve_depuis_dict(deja[1])
    cache = chemin.parent / "releves_lus.cache.json"
    try:
        tous = json.loads(cache.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        tous = {}
    entree = tous.get(chemin.name)
    if entree and entree.get("signature") == signature:
        _RELEVES_LUS[str(chemin)] = (signature, entree["releve"])
        return _releve_depuis_dict(entree["releve"])
    releve = lire_releve(chemin)
    donnees = _releve_en_dict(releve)
    _RELEVES_LUS[str(chemin)] = (signature, donnees)
    tous[chemin.name] = {"signature": signature, "releve": donnees}
    try:
        cache.write_text(json.dumps(tous, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass
    return _releve_depuis_dict(donnees)


from .banques_canada import NOMS as BANQUES  # noqa: E402  (toutes les banques et caisses du Canada)


def banque_du_texte(texte: str) -> str:
    """« bnc » : relevé de la Banque Nationale (« MM JJ DESCRIPTION DÉBIT ($) CRÉDIT ($) SOLDE ($) », « No
    succursale ») ; sinon « desjardins »."""
    t = texte.lower()
    if "no succursale" in t and re.search(r"mm\s+jj\s+description", t):
        return "bnc"
    return "desjardins"


def lire_releve(chemin: Path) -> Releve:
    """Relevé de n'importe quelle banque du Canada : OFX / QFX / QBO, CSV, ou PDF (Desjardins et Banque Nationale
    ont leur lecteur ; les autres banques : colonnes repérées sur l'en-tête)."""
    import pdfplumber

    from .releves_bancaires import EXTENSIONS_CSV, EXTENSIONS_OFX, lire_csv, lire_ofx

    extension = Path(chemin).suffix.lower()
    if extension in EXTENSIONS_OFX:
        return lire_ofx(chemin)
    if extension in EXTENSIONS_CSV:
        return lire_csv(chemin)

    with pdfplumber.open(chemin) as pdf:
        texte = "\n".join((p.extract_text() or "") for p in pdf.pages)
        if banque_du_texte(texte) == "bnc":
            return lire_releve_bnc(chemin, pdf, texte)
    return lire_releve_desjardins(chemin)


LIGNE_BNC = re.compile(r"^(\d{2}) (\d{2}) (.*?) ((?:\d{1,3}(?: \d{3})*,\d{2} ?){1,3})$")


def lire_releve_bnc(chemin: Path, pdf, texte: str) -> Releve:
    """Relevé de compte de la Banque Nationale (demande du propriétaire du 2026-11-05 : « ajoute aussi les relevés
    de compte de BNC ») : « Période du 01-09-2025 au 30-09-2025 », lignes « MM JJ DESCRIPTION  DÉBIT  CRÉDIT
    SOLDE » (montants « 1 802,86 ») ; débit ou crédit d'après la variation du solde imprimé ; « SOLDE PRECEDENT » ;
    facturation détaillée ignorée ; contrôle avec « TRANSACTIONS DÉBIT n montant CRÉDIT n montant »."""
    releve = Releve(Path(chemin).name)
    m = re.search(r"P.riode du (\d{2})-(\d{2})-(\d{4}) au (\d{2})-(\d{2})-(\d{4})", texte)
    debut = date(int(m[3]), int(m[2]), int(m[1])) if m else None
    fin = date(int(m[6]), int(m[5]), int(m[4])) if m else None
    releve.debut, releve.fin = (debut.isoformat() if debut else ""), (fin.isoformat() if fin else "")
    solde_courant: Decimal | None = None
    dans_tableau = False
    for ligne in texte.splitlines():
        ligne = ligne.replace(" ", " ").replace(" ", " ").strip()
        if re.match(r"MM JJ DESCRIPTION", ligne):
            dans_tableau = True
            continue
        if not dans_tableau:
            continue
        if re.match(r"(FACTURATION D.TAILL|NOMBRE MONTANT|Veuillez v.rifier)", ligne):
            dans_tableau = False  # fin du tableau de la page (repris à l'en-tête suivant)
            continue
        trouve = LIGNE_BNC.match(ligne)
        if not trouve:
            continue
        mois, jour, description = int(trouve[1]), int(trouve[2]), trouve[3].strip()
        montants = [_montant(x) for x in re.findall(r"\d{1,3}(?: \d{3})*,\d{2}", trouve[4])]
        solde = montants[-1]
        if re.match(r"SOLDE PR.C.DENT", description, re.I):
            releve.solde_ouverture = solde_courant = solde
            continue
        if len(montants) < 2:
            continue
        valeur = montants[-2]
        if solde_courant is not None and solde_courant + valeur == solde:
            montant = valeur          # crédit (dépôt)
        elif solde_courant is not None and solde_courant - valeur == solde:
            montant = -valeur         # débit (retrait)
        else:
            montant = -valeur if solde_courant is None or solde < solde_courant else valeur
        annee = fin.year if fin else date.today().year
        if fin and mois > fin.month + 1:  # relevé de janvier avec des jours de décembre
            annee -= 1
        try:
            jour_mvt = date(annee, mois, jour)
        except ValueError:
            releve.remarques.append(f"date illisible ignorée : {ligne}")
            continue
        mvt = MouvementBanque(jour_mvt.isoformat(), description, montant, solde, releve.fichier,
                              len(releve.mouvements))
        if solde_courant is not None and solde_courant + montant != solde:
            mvt.remarque = f"solde attendu {solde_courant + montant} $, imprimé {solde} $"
        solde_courant = solde
        releve.mouvements.append(mvt)
    releve.solde_fermeture = solde_courant
    totaux = re.search(r"TRANSACTIONS D.BIT (\d+) ([\d  ]+,\d{2}) CR.DIT (\d+) ([\d  ]+,\d{2})", texte)
    if totaux:  # contrôle avec les totaux imprimés par la banque
        debits = [x for x in releve.mouvements if x.montant < 0]
        credits = [x for x in releve.mouvements if x.montant > 0]
        attendus = (int(totaux[1]), _montant(totaux[2]), int(totaux[3]), _montant(totaux[4]))
        lus = (len(debits), -sum((x.montant for x in debits), Decimal(0)), len(credits),
               sum((x.montant for x in credits), Decimal(0)))
        if lus != attendus:
            releve.remarques.append(f"totaux lus {lus} ≠ totaux du relevé {attendus}")
    return releve


def lire_releve_desjardins(chemin: Path) -> Releve:
    """Relevé Desjardins : colonnes Date, Code, Description, Frais, Retrait, Dépôt, Solde ; « 6 840.89 » ;
    description parfois sur deux lignes (les montants sont alors sur la seconde)."""
    import pdfplumber

    releve = Releve(Path(chemin).name)
    with pdfplumber.open(chemin) as pdf:
        texte = "\n".join((p.extract_text() or "") for p in pdf.pages)
        debut, fin = _periode(texte)
        releve.debut, releve.fin = (debut.isoformat() if debut else ""), (fin.isoformat() if fin else "")
        colonnes: dict[str, float] = {}
        solde_courant: Decimal | None = None
        en_attente: tuple[date, str] | None = None  # ligne datée dont les montants sont sur la ligne suivante
        termine = compte_ferme = False
        for page in pdf.pages:
            if termine:
                break
            for mots in _lignes(page.dedupe_chars()):
                mots = _fusionner_nombres(mots)
                bas = " ".join(m["text"] for m in mots).lower().replace("’", "'").replace("‘", "'")
                if PIED_DE_PAGE.match(bas):  # « 1 de 2 », « Page 1 of 2 »
                    continue
                if colonnes and FIN_DU_COMPTE.match(bas):
                    termine = True
                    break
                if _est_entete(mots, bas):  # en-tête des colonnes (répété sur chaque page)
                    if compte_ferme:  # un autre compte du même relevé commence (épargne, prêt…) : il est ignoré
                        termine = True
                        break
                    colonnes = {_genre_colonne(m): m["x1"] for m in mots if _genre_colonne(m)}
                    continue
                if colonnes.get("solde"):  # notes imprimées dans la marge, à droite de la colonne du solde
                    mots = [m for m in mots if m["x0"] <= colonnes["solde"] + 4]
                    bas = " ".join(m["text"] for m in mots).lower().replace("’", "'").replace("‘", "'")
                montants = [m for m in mots if MONTANT.match(m["text"])]
                autres = [m for m in mots if m not in montants]
                if OUVERTURE.search(bas) and montants:
                    if releve.solde_ouverture is None:
                        releve.solde_ouverture = solde_courant = _montant(montants[-1]["text"])
                    continue
                if FERMETURE.search(bas) and montants:
                    releve.solde_fermeture = _montant(montants[-1]["text"])
                    compte_ferme = bool(colonnes and releve.mouvements)
                    continue
                if not colonnes:
                    continue
                jour = None
                for n in (2, 1):  # « 2 FEV » ou « 2026-09-02 »
                    if len(autres) >= n:
                        jour = _date_ligne(" ".join(m["text"] for m in autres[:n]), fin)
                        if jour:
                            autres = autres[n:]
                            break
                if not jour and colonnes.get("date"):  # TD : colonne Date après les montants (« MAR04 », « APR 11 »)
                    proches = [m for m in autres if abs(m["x1"] - colonnes["date"]) < 40
                               or abs(m["x0"] - colonnes["date"]) < 40]
                    for n in (2, 1):
                        if len(proches) >= n:
                            texte_date = " ".join(m["text"] for m in proches[-n:])
                            texte_date = re.sub(r"^([A-Za-zÉéû]{3})(\d{1,2})$", r"\1 \2", texte_date)
                            jour = _date_ligne(texte_date, fin)
                            if jour:
                                autres = [m for m in autres if m not in proches[-n:]]
                                break
                description = " ".join(m["text"] for m in autres).strip()
                if not montants:
                    if jour and description:
                        en_attente = (jour, description)
                    elif en_attente and description:
                        en_attente = (en_attente[0], f"{en_attente[1]} {description}")
                    elif releve.mouvements and description and not jour:
                        releve.mouvements[-1].description += f" {description}"
                    continue
                if not jour and en_attente:  # suite de la ligne précédente, avec les montants
                    jour, description = en_attente[0], f"{en_attente[1]} {description}".strip()
                en_attente = None
                valeurs = {"frais": None, "retrait": None, "depot": None, "solde": None, "montant": None}
                montantes = {c: x for c, x in colonnes.items() if c != "date"}
                for m in montants:
                    colonne = min(montantes, key=lambda c: abs(montantes[c] - m["x1"]))
                    valeurs[colonne] = _montant(m["text"])
                if all(valeurs[c] is None for c in ("frais", "retrait", "depot", "montant")):
                    continue
                montant = (valeurs["depot"] or Decimal(0)) - (valeurs["retrait"] or Decimal(0)) - (
                    valeurs["frais"] or Decimal(0)) + (valeurs["montant"] or Decimal(0))  # colonne unique signée (Tangerine)
                if (valeurs["solde"] is not None and solde_courant is not None and montant
                        and valeurs["solde"] - solde_courant == -montant):
                    # le solde imprimé tranche le sens (« Correction : … Frais 1.25 » rend les frais, UNI)
                    montant = -montant
                jour = jour or (date.fromisoformat(releve.mouvements[-1].date) if releve.mouvements else None)
                if not jour:
                    releve.remarques.append(f"ligne sans date ignorée : {bas}")
                    continue
                mouvement = MouvementBanque(jour.isoformat(), description, montant, valeurs["solde"], releve.fichier,
                                            len(releve.mouvements))
                if valeurs["solde"] is not None and solde_courant is not None and solde_courant + montant != valeurs["solde"]:
                    mouvement.remarque = f"solde attendu {solde_courant + montant} $, imprimé {valeurs['solde']} $"
                solde_courant = valeurs["solde"] if valeurs["solde"] is not None else (
                    None if solde_courant is None else solde_courant + montant)
                releve.mouvements.append(mouvement)
        if not colonnes:
            releve.remarques.append("colonnes Retrait / Dépôt / Solde introuvables (relevé numérisé ? Téléchargez "
                                    "plutôt le relevé en OFX / QFX ou CSV sur le site de la banque)")
        if releve.solde_fermeture is None and solde_courant is not None and releve.mouvements:
            releve.solde_fermeture = solde_courant
    return releve


# --------------------------------------------------------------------------------------------- Sage
def mouvements_sage(base, debut: date, fin: date, compte: int = COMPTE_BANQUE) -> list[MouvementSage]:
    """Écritures du compte, sans les écritures corrigées ni leurs contreparties (tjourent.nType 64/65 : original
    corrigé, 32/33 : contrepassation « CORR … Contrep. de Jn ») : elles s'annulent et ne passent pas à la banque."""
    lignes = base.requete(
        "SELECT e.lId, e.dtJourDate, e.sSource, e.sComment, ROUND(SUM(a.dAmount), 2) montant FROM tjentact a "
        "JOIN tjourent e ON e.lId = a.lJEntId WHERE a.lAcctId = %s AND e.dtJourDate BETWEEN %s AND %s "
        "AND e.nType NOT IN (32, 33, 64, 65) "
        "GROUP BY e.lId, e.dtJourDate, e.sSource, e.sComment HAVING ROUND(SUM(a.dAmount), 2) <> 0 "
        "ORDER BY e.dtJourDate, e.lId", (compte, debut.isoformat(), fin.isoformat()))
    return [MouvementSage(l["lId"], l["dtJourDate"].date().isoformat(), (l["sSource"] or "").strip(),
                          (l["sComment"] or "").strip(), Decimal(str(l["montant"]))) for l in lignes]


def solde_sage(base, jour: date, compte: int = COMPTE_BANQUE) -> Decimal:
    """Solde du compte à la fin de `jour` : ouverture de l'exercice + écritures jusqu'à ce jour."""
    ouverture = base.requete("SELECT dYtcLY FROM taccount WHERE lId = %s", (compte,))
    mouvements = base.requete("SELECT ROUND(SUM(a.dAmount), 2) s FROM tjentact a JOIN tjourent e ON e.lId = a.lJEntId "
                              "WHERE a.lAcctId = %s AND e.dtJourDate <= %s", (compte, jour.isoformat()))
    return (Decimal(str(ouverture[0]["dYtcLY"] if ouverture else 0)) + Decimal(str(mouvements[0]["s"] or 0))
            ).quantize(Decimal("0.01"))


def factures_ventes(base, client: str) -> dict[str, date]:
    """Factures de vente du client « Vente Hebdomadaire » dans Sage : n° -> date de la facture."""
    return {l["s"]: l["d"].date() if hasattr(l["d"], "date") else l["d"] for l in base.requete(
        "SELECT TRIM(t.sSource) s, t.dtDate d FROM tcustr t JOIN tcustomr c ON c.lId = t.lCusId "
        "WHERE c.sName = %s AND t.sSource LIKE 'Vente %%'", (client,))}


def comptes_sage(base) -> list[str]:
    """« 5450 Frais bancaires » : comptes actifs, pour le choix du compte d'une écriture à saisir."""
    from .base_sage import numero_compte

    return [f"{numero_compte(l['lId'])} {l['sName'].strip()}"
            for l in base.requete("SELECT lId, sName FROM taccount WHERE bInactive = 0 ORDER BY lId")]


# --------------------------------------------------------------------------------------------- rapprochement
def _dans_fenetre(banque: MouvementBanque, sage: MouvementSage) -> bool:
    ecart = (date.fromisoformat(banque.date) - date.fromisoformat(sage.date)).days
    return -APRES <= ecart <= AVANT


def _date_reference(texte: str) -> date | None:
    """« PAY05012026 », « PAYE05012026 » (jjmmaaaa) ou « PAY20260119 » (aaaammjj) -> date de la paie."""
    m = REFERENCE_PAIE.search(texte or "")
    if not m:
        return None
    chiffres = m.group(1)
    for jour, mois, annee in ((chiffres[:2], chiffres[2:4], chiffres[4:]), (chiffres[6:], chiffres[4:6], chiffres[:4])):
        try:
            return date(int(annee), int(mois), int(jour))
        except ValueError:
            continue
    return None


def est_salaire(m: MouvementBanque) -> bool:
    return m.montant < 0 and bool(SALAIRE.search(m.description))


def _rapprocher_salaires(a_relier: list[MouvementBanque], sage: list[MouvementSage],
                         anterieures: list[MouvementSage]) -> None:
    """Dépôts de salaire (règle du propriétaire) : reliés aux paies de Sage (source « PAY… ») du même montant, même
    payées plusieurs semaines plus tard ; la paie dont la référence (date) est celle du relevé passe en premier."""
    for b in sorted((x for x in a_relier if est_salaire(x)), key=lambda x: x.date):
        jour, reference = date.fromisoformat(b.date), _date_reference(b.description)
        candidates = [s for s in sage + anterieures if not s.rapproche and s.montant == b.montant
                      and s.source.upper().startswith("PAY")
                      and -APRES <= (jour - date.fromisoformat(s.date)).days <= DELAI_PAIE]
        if not candidates:
            continue
        s = min(candidates, key=lambda c: (reference is None or _date_reference(c.source) != reference,
                                           abs((jour - date.fromisoformat(c.date)).days)))
        s.rapproche, b.etat, b.sage = True, RAPPROCHE, [s.ident]
        if s not in sage:
            sage.append(s)


def rapprocher(banque: list[MouvementBanque], sage: list[MouvementSage],
               anterieures: list[MouvementSage] | None = None) -> None:
    """Relie les mouvements de banque aux écritures Sage (ne touche pas aux mouvements saisis, choisis ou ignorés).
    `anterieures` : paies de Sage d'avant la période des relevés (salaires versés en retard) ; celles qui sont reliées
    sont ajoutées à `sage`."""
    for s in sage:
        s.rapproche = False
    a_relier = [b for b in banque if b.etat in (A_SAISIR, RAPPROCHE, A_ENCAISSER, A_PAIE)]
    for b in a_relier:
        b.etat, b.sage = A_SAISIR, []
    for b in banque:  # mouvements déjà saisis par l'application : leurs écritures restent prises
        if b.etat == SAISI:
            for s in sage:
                if s.ident in b.sage:
                    s.rapproche = True
    # 0. dépôts de salaire -> paies de Sage
    _rapprocher_salaires(a_relier, sage, [s for s in anterieures or [] if s.ident not in {x.ident for x in sage}])
    # 1. une écriture du même montant, à la date la plus proche
    for b in sorted(a_relier, key=lambda x: x.date):
        candidates = [s for s in sage if not s.rapproche and s.montant == b.montant and _dans_fenetre(b, s)]
        if candidates:
            s = min(candidates, key=lambda c: abs((date.fromisoformat(b.date) - date.fromisoformat(c.date)).days))
            s.rapproche, b.etat, b.sage = True, RAPPROCHE, [s.ident]
    # 2. deux ou trois écritures dont la somme égale le mouvement (ex. dépôt de fin de semaine)
    for b in [x for x in a_relier if x.etat == A_SAISIR]:
        libres = [s for s in sage if not s.rapproche and _dans_fenetre(b, s) and (s.montant > 0) == (b.montant > 0)][:14]
        for taille in (2, 3):
            groupe = next((g for g in combinations(libres, taille) if sum(s.montant for s in g) == b.montant), None)
            if groupe:
                for s in groupe:
                    s.rapproche = True
                b.etat, b.sage = RAPPROCHE, [s.ident for s in groupe]
                break
    # 3. Interac reçu ou dépôt d'espèces absent de Sage : à encaisser sur les factures de vente (page Encaissements)
    for b in a_relier:
        if b.etat == A_SAISIR and est_especes(b):
            b.etat = A_ENCAISSER
        elif b.etat == A_SAISIR and est_salaire(b):
            b.etat = A_PAIE  # la paie se saisit dans le module Paie de Sage, pas en écriture de journal


def est_interac(m: MouvementBanque) -> bool:
    return m.montant > 0 and bool(INTERAC.search(m.description))


def est_especes(m: MouvementBanque) -> bool:
    """Argent des ventes encaissé hors Clover : virement Interac reçu ou dépôt d'espèces au guichet automatique."""
    return m.montant > 0 and (est_interac(m) or bool(DEPOT_ESPECES.search(m.description)))


def jours_couverts(numero: str) -> list[date]:
    """Jours de vente d'une facture : jour, fin de semaine, « Vente S43-2026 » ou « Vente Octobre 2026 »."""
    from .facture import MOIS as MOIS_FACTURE
    from .facture import jours_facture

    jours = jours_facture(numero)
    if jours:
        return jours
    m = re.fullmatch(r"Vente S(\d{2})-(\d{4})", numero.strip())
    if m:
        lundi = date.fromisocalendar(int(m.group(2)), int(m.group(1)), 1)
        return [lundi + timedelta(days=i) for i in range(7)]
    m = re.fullmatch(r"Vente (\S+) (\d{4})", numero.strip())
    if m and m.group(1) in MOIS_FACTURE:
        premier = date(int(m.group(2)), MOIS_FACTURE.index(m.group(1)) + 1, 1)
        return [premier + timedelta(days=i) for i in range(31) if (premier + timedelta(days=i)).month == premier.month]
    return []


def facture_du_jour(jour: date, factures: dict[str, date] | set[str]) -> str:
    """Facture de vente qui couvre `jour` (la plus précise : jour, puis fin de semaine, semaine, mois) ; « » sinon."""
    candidates = [(len(jours), n) for n in factures if jour in (jours := jours_couverts(n))]
    return min(candidates)[1] if candidates else ""


def resume(banque: list[MouvementBanque], sage: list[MouvementSage], solde_banque: Decimal | None,
           solde_de_sage: Decimal | None, ouverture_banque: Decimal | None = None,
           ouverture_sage: Decimal | None = None, debut: date | None = None) -> dict:
    """Chiffres du rapprochement. Écart de fin = écart déjà présent à l'ouverture de la période + mouvements de banque
    absents de Sage − écritures Sage pas encore passées à la banque ; le reste est « non expliqué ».

    Un mouvement relié à une écriture Sage d'AVANT le `debut` de la période (salaire versé en retard, écriture saisie
    quelques jours plus tôt) compte comme absent : l'écriture est déjà dans l'écart d'ouverture."""
    dates = {s.ident: s.date for s in sage}
    avant = (lambda b: debut is not None and b.etat == RAPPROCHE and b.sage
             and all(n in dates and date.fromisoformat(dates[n]) < debut for n in b.sage))
    absents = sum((b.montant for b in banque if b.etat in (A_SAISIR, CONFIRME, A_ENCAISSER, A_PAIE) or avant(b)),
                  Decimal(0))
    circulation = sum((s.montant for s in sage if not s.rapproche), Decimal(0))
    ecart = None if solde_banque is None or solde_de_sage is None else solde_banque - solde_de_sage
    ouverture = (None if ouverture_banque is None or ouverture_sage is None else ouverture_banque - ouverture_sage)
    explique = absents - circulation + (ouverture or Decimal(0))
    return {"solde_banque": solde_banque, "solde_sage": solde_de_sage, "ecart": ecart, "ecart_ouverture": ouverture,
            "absents": absents, "circulation": circulation, "non_explique": None if ecart is None else ecart - explique}


# --------------------------------------------------------------------------------------------- registre
@dataclass
class CompteBancaire:
    """Compte bancaire rapproché (demande du propriétaire du 2026-11-05 : « ajouter la possibilité d'ajouter un
    compte bancaire ») : `format` = banque du compte (code de banques_canada : « desjardins », « bnc », « rbc »,
    « td », « scotia », « bmo », « cibc »… ou « autre » ; demande du propriétaire du 2026-11-12 : toutes les banques
    du Canada) ; `numero` = n° du compte à la banque, pour ranger un relevé quand une banque a plusieurs comptes ;
    relevés dans donnees/releves_<code>/. Le 1er compte (code « desjardins », dossier releves_desjardins gardé
    pour les données déjà chargées) est le compte de dépôt des ventes, quelle que soit sa banque."""
    code: str
    nom: str
    format: str
    compte_sage: str
    numero: str = ""

    @property
    def libelle(self) -> str:
        return f"{self.nom} ({self.compte_sage})"


def comptes_bancaires(config_toml: dict) -> list[CompteBancaire]:
    """Compte de dépôt des ventes (1055, [encaissements] compte_depot ; sa banque : [rapprochement] banque_depot,
    Desjardins par défaut) et BNC (1060, [rapprochement] compte_bnc) d'office, puis les comptes ajoutés
    ([[comptes_bancaires]] code, nom, format, compte_sage, numero, actif)."""
    from .banques_canada import PAR_CODE, nom

    r = config_toml.get("rapprochement", {})
    banque_depot = str(r.get("banque_depot") or "desjardins")
    banque_depot = banque_depot if banque_depot in PAR_CODE else "desjardins"
    comptes = [CompteBancaire("desjardins", nom(banque_depot), banque_depot,
                              str(config_toml.get("encaissements", {}).get("compte_depot", "1055") or "1055").strip(),
                              str(r.get("numero_desjardins", "") or "")),
               CompteBancaire("bnc", "Banque Nationale (BNC)", "bnc",  # 1060 : indication du propriétaire du 2026-11-05
                              str(r.get("compte_bnc", "1060") or "1060").strip(), str(r.get("numero_bnc", "") or ""))]
    for c in config_toml.get("comptes_bancaires", []) or []:
        code = "".join(x for x in str(c.get("code", "")).lower() if x.isalnum() or x in "-_")
        if not code or code in {x.code for x in comptes} or not c.get("actif", True):
            continue
        comptes.append(CompteBancaire(code, str(c.get("nom") or code), str(c.get("format") or "desjardins"),
                                      str(c.get("compte_sage") or "").strip(), str(c.get("numero") or "")))
    return [c for c in comptes if c.compte_sage]


def compte_bancaire(config_toml: dict, code: str = "desjardins") -> CompteBancaire:
    comptes = comptes_bancaires(config_toml)
    return next((c for c in comptes if c.code == code), comptes[0])


def compte_banque(config_toml: dict, banque: str = "desjardins") -> str:
    """Compte Sage du compte bancaire (1055 Desjardins, 1060 BNC, ou un compte ajouté)."""
    return compte_bancaire(config_toml, banque).compte_sage


def banques_reglees(config_toml: dict) -> list[str]:
    """Codes des comptes bancaires du rapprochement, dans l'ordre."""
    return [c.code for c in comptes_bancaires(config_toml)]


class RegistreReleves:
    """Relevés chargés et décisions du propriétaire (donnees/releves_<banque>/releves.json) ; une banque par
    registre (« desjardins » par défaut, « bnc » : Banque Nationale, demande du propriétaire du 2026-11-05)."""

    def __init__(self, racine: Path, banque: str = "desjardins", compte: str = ""):
        self.banque, self.compte = banque, compte
        self.dossier = Path(racine) / "donnees" / f"releves_{banque}"
        self.chemin = self.dossier / "releves.json"
        self.decisions: dict[str, dict] = {}   # clé de mouvement -> {"etat", "compte", "sage", "remarque"}
        self.memoire: dict[str, str] = {}      # description normalisée -> compte Sage (pour les mouvements semblables)
        if self.chemin.exists():
            donnees = json.loads(self.chemin.read_text(encoding="utf-8"))
            self.decisions, self.memoire = donnees.get("decisions", {}), donnees.get("memoire", {})

    def enregistrer(self) -> None:
        self.dossier.mkdir(parents=True, exist_ok=True)
        provisoire = self.chemin.with_suffix(".tmp")
        provisoire.write_text(json.dumps({"decisions": self.decisions, "memoire": self.memoire}, ensure_ascii=False,
                                         indent=1), encoding="utf-8")
        provisoire.replace(self.chemin)

    def fichiers(self) -> list[Path]:
        from .releves_bancaires import EXTENSIONS

        if not self.dossier.exists():
            return []
        return sorted(p for p in self.dossier.iterdir() if p.is_file() and p.suffix.lower() in EXTENSIONS)

    def lire(self) -> list[Releve]:
        releves = []
        for chemin in self.fichiers():
            try:
                r = lire_releve_garde(chemin)
            except Exception as exc:
                r = Releve(chemin.name, remarques=[f"lecture impossible : {exc}"])
            for m in r.mouvements:
                if self.banque != "desjardins":
                    m.compte_banque = self.compte  # écriture au compte de cette banque (robot_journal)
                d = self.decisions.get(m.cle)
                if d:
                    m.etat, m.compte, m.sage, m.remarque = d["etat"], d.get("compte", ""), d.get("sage", []), \
                        d.get("remarque", m.remarque)
                elif not m.compte:
                    m.compte = self.memoire.get(motif(m.description), "")
            releves.append(r)
        return releves

    def retenir(self, m: MouvementBanque) -> None:
        if m.etat in (CONFIRME, SAISI, IGNORE):
            self.decisions[m.cle] = {"etat": m.etat, "compte": m.compte, "sage": m.sage, "remarque": m.remarque}
        else:
            self.decisions.pop(m.cle, None)
        if m.compte and m.etat in (CONFIRME, SAISI):
            self.memoire[motif(m.description)] = m.compte

    def supprimer(self, fichier: str) -> None:
        """Retire un relevé : le fichier va dans « supprimes », ses décisions sont oubliées."""
        chemin = self.dossier / fichier
        if chemin.exists():
            corbeille = self.dossier / "supprimes"
            corbeille.mkdir(exist_ok=True)
            chemin.replace(corbeille / chemin.name)
        self.decisions = {k: v for k, v in self.decisions.items() if not k.startswith(f"{fichier}|")}


def motif(description: str) -> str:
    """Description sans chiffres ni ponctuation : « FRAIS MENS. 09/2026 » et « FRAIS MENS. 10/2026 » se ressemblent."""
    from .correspondance import normaliser

    return " ".join(re.sub(r"[^a-z ]", " ", normaliser(description)).split())


# --------------------------------------------------------------------------------------------- rapport
def ecrire_rapport(chemin: Path, releves: list[Releve], banque: list[MouvementBanque], sage: list[MouvementSage],
                   chiffres: dict, periode: tuple[date, date]) -> Path:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill

    vert = PatternFill("solid", fgColor="1F7A3A")
    blanc_gras = Font(bold=True, color="FFFFFF")
    classeur = Workbook()
    f = classeur.active
    f.title = "Rapprochement"
    f.append([f"Rapprochement bancaire — compte 1055 Desjardins — du {periode[0]} au {periode[1]}"])
    f["A1"].font = Font(bold=True, size=14, color="13772D")
    f.append([])
    for libelle, cle in (("Solde du relevé (banque)", "solde_banque"), ("Solde du compte 1055 dans Sage", "solde_sage"),
                         ("Écart (banque − Sage)", "ecart"), ("Écart déjà présent à l'ouverture", "ecart_ouverture"),
                         ("Mouvements de banque absents de Sage", "absents"),
                         ("Écritures Sage pas encore à la banque", "circulation"), ("Écart non expliqué", "non_explique")):
        f.append([libelle, float(chiffres[cle]) if chiffres[cle] is not None else ""])
    f.append([])
    f.append(["Relevés", "Période", "Solde d'ouverture", "Solde de fermeture", "Contrôle"])
    for r in releves:
        f.append([r.fichier, f"{r.debut} au {r.fin}", float(r.solde_ouverture or 0), float(r.solde_fermeture or 0),
                  "; ".join(r.controles()) or "OK"])
    f.column_dimensions["A"].width = 46
    for col in "BCDE":
        f.column_dimensions[col].width = 22
    for titre, entetes, lignes in (
            ("Banque", ["Date", "Description", "Montant", "Solde", "État", "Écritures Sage", "Compte", "Relevé"],
             [[b.date, b.description, float(b.montant), float(b.solde) if b.solde is not None else "", b.etat,
               ", ".join(map(str, b.sage)), b.compte, b.releve] for b in banque]),
            ("Sage", ["N° écriture", "Date", "Source", "Description", "Montant", "Rapprochée"],
             [[s.ident, s.date, s.source, s.description, float(s.montant), "oui" if s.rapproche else "NON"]
              for s in sage])):
        feuille = classeur.create_sheet(titre)
        feuille.append(entetes)
        for cellule in feuille[1]:
            cellule.fill, cellule.font = vert, blanc_gras
        for ligne in lignes:
            feuille.append(ligne)
        for i, largeur in enumerate((12, 46, 14, 14, 24, 16, 12, 30)[:len(entetes)]):
            feuille.column_dimensions[chr(65 + i)].width = largeur
        feuille.freeze_panes = "A2"
    chemin.parent.mkdir(parents=True, exist_ok=True)
    classeur.save(chemin)
    return chemin


def restreindre(releves: list[Releve], du: date, au: date):
    """Mouvements de banque du `du` au `au` inclus, solde à l'ouverture du `du` et solde à la fin du `au`.

    Solde courant suivi relevé par relevé (dans l'ordre des dates) : solde d'ouverture du relevé, puis chaque
    mouvement ; le solde imprimé sur la ligne, quand il existe, fait foi."""
    banque, ouverture, fermeture = [], None, None
    for r in sorted(releves, key=lambda r: r.debut or "9999"):
        courant = r.solde_ouverture
        if r.debut and date.fromisoformat(r.debut) >= du and ouverture is None:
            ouverture = courant
        for m in r.mouvements:
            jour = date.fromisoformat(m.date)
            if jour < du:
                pass
            elif jour <= au:
                if ouverture is None:
                    ouverture = courant
                banque.append(m)
            courant = m.solde if m.solde is not None else (None if courant is None else courant + m.montant)
            if jour <= au:
                fermeture = courant
        if r.fin and date.fromisoformat(r.fin) <= au and r.solde_fermeture is not None:
            fermeture = r.solde_fermeture
    return banque, ouverture, fermeture


def periode_des(releves: list[Releve]) -> tuple[date, date] | None:
    jours = [date.fromisoformat(m.date) for r in releves for m in r.mouvements]
    debuts = [date.fromisoformat(r.debut) for r in releves if r.debut]
    fins = [date.fromisoformat(r.fin) for r in releves if r.fin]
    if not jours and not debuts:
        return None
    return min(debuts + jours), max(fins + jours)



# --------------------------------------------------------------------------------------------- plusieurs banques
def registre_de(racine: Path, config_toml: dict, banque: str = "desjardins") -> RegistreReleves:
    return RegistreReleves(racine, banque, compte_banque(config_toml, banque))


def nombre_releves(racine: Path) -> int:
    """Relevés chargés dans tous les comptes bancaires (PDF, OFX / QFX / QBO, CSV)."""
    from .releves_bancaires import EXTENSIONS

    donnees = Path(racine) / "donnees"
    if not donnees.is_dir():
        return 0
    return sum(1 for d in donnees.glob("releves_*") if d.is_dir()
               for p in d.iterdir() if p.is_file() and p.suffix.lower() in EXTENSIONS)


def compte_entier(config_toml: dict, banque: str = "desjardins") -> int:
    """Compte Sage de la banque au format de Sage (1055 -> 10550000)."""
    from .encaissements import numero_compte_sage

    return numero_compte_sage(compte_banque(config_toml, banque) or "1055")


def texte_pour_banque(chemin: Path) -> tuple[str, str]:
    """(texte de la 1re page ou du fichier, n° d'institution) pour reconnaître la banque et le compte."""
    from .releves_bancaires import EXTENSIONS_OFX, infos_ofx, texte_du_fichier

    chemin = Path(chemin)
    if chemin.suffix.lower() == ".pdf":
        import pdfplumber

        with pdfplumber.open(chemin) as pdf:
            return "\n".join((p.extract_text() or "") for p in pdf.pages[:1]), ""
    texte = texte_du_fichier(chemin)
    if chemin.suffix.lower() in EXTENSIONS_OFX:
        infos = infos_ofx(texte)
        return f"{infos['org']} {infos['fid']} {infos['compte']}", infos["banque"]
    return texte[:6000], ""


def banque_du_fichier(chemin: Path) -> str:
    """Banque du relevé (code de banques_canada ; « autre » si rien ne la reconnaît)."""
    from .banques_canada import detecter

    texte, institution = texte_pour_banque(chemin)
    if Path(chemin).suffix.lower() == ".pdf" and banque_du_texte(texte) == "bnc":
        return "bnc"
    return detecter(texte, institution)


def ranger_releve(racine: Path, source: Path, nom: str | None = None, config_toml: dict | None = None
                  ) -> tuple[str, Path]:
    """Relevé chargé (PDF, OFX / QFX / QBO ou CSV, de n'importe quelle banque du Canada) : le compte bancaire dont
    le n° figure dans le relevé, sinon le premier compte de la banque reconnue, sinon le seul compte « Autre banque »,
    sinon le seul compte réglé ; copié dans donnees/releves_<code>/. Renvoie (code, fichier). Aucun compte ne
    convient : ValueError (ajouter le compte bancaire dans Administration > Sage 50)."""
    import shutil

    from .banques_canada import nom as nom_banque
    from .releves_bancaires import EXTENSIONS

    if Path(source).suffix.lower() not in EXTENSIONS:
        raise ValueError("Format de relevé non reconnu : choisissez un fichier PDF, OFX, QFX, QBO ou CSV.")
    texte, _institution = texte_pour_banque(source)
    fmt = banque_du_fichier(source)
    chiffres = "".join(c for c in texte if c.isdigit())
    comptes = comptes_bancaires(config_toml or {})
    par_numero = [c for c in comptes if c.numero and len("".join(x for x in c.numero if x.isdigit())) >= 4
                  and "".join(x for x in c.numero if x.isdigit()) in chiffres]
    de_la_banque = [c for c in comptes if c.format == fmt]
    autres = [c for c in comptes if c.format == "autre"]
    choisi = next(iter([c for c in par_numero if c.format == fmt] or par_numero or de_la_banque
                       or (autres if len(autres) == 1 else []) or (comptes if len(comptes) == 1 else [])), None)
    if choisi is None:
        raise ValueError(f"Aucun compte bancaire réglé pour {nom_banque(fmt)} : ajoutez-le dans « Administration > "
                         "Sage 50 », carte « Comptes bancaires (rapprochement) », puis chargez de nouveau le relevé.")
    banque = choisi.code
    dossier = Path(racine) / "donnees" / f"releves_{banque}"
    dossier.mkdir(parents=True, exist_ok=True)
    cible = dossier / (nom or Path(source).name)
    if Path(source).resolve() != cible.resolve():
        shutil.copy2(source, cible)
    return banque, cible
