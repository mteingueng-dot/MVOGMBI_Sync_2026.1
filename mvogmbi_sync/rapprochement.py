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
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date
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

MONTANT = re.compile(r"^-?\d{1,3}(?:[   ]?\d{3})*[.,]\d{2}-?$")


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


def _date_ligne(texte: str, fin: date | None) -> date | None:
    """« 2026-09-02 », « 02/09 », « 02 SEP », « 2 sept. » ; l'année vient de la période du relevé."""
    t = texte.lower().replace(".", "").strip()
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})$", t)
    if m:
        return date(int(m[1]), int(m[2]), int(m[3]))
    m = re.match(r"(\d{1,2})[/ -]?([a-zéû]{3,9}|\d{1,2})$", t)
    if not m:
        return None
    jour = int(m[1])
    mois = int(m[2]) if m[2].isdigit() else MOIS.get(m[2])
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
    from .factures_fournisseurs import lire_date

    m = re.search(r"(?:du|période du|from)\s+(.{6,25}?)\s+(?:au|to)\s+(.{6,25}?)(?:\n|$|\s{2})", texte, re.IGNORECASE)
    if m:
        return lire_date(m[1].replace("1er", "1")), lire_date(m[2])
    dates = [d for d in (lire_date(x) for x in re.findall(r"\d{4}-\d{2}-\d{2}", texte)) if d]
    return (min(dates), max(dates)) if dates else (None, None)


def lire_releve(chemin: Path) -> Releve:
    import pdfplumber

    releve = Releve(Path(chemin).name)
    with pdfplumber.open(chemin) as pdf:
        texte = "\n".join((p.extract_text() or "") for p in pdf.pages)
        debut, fin = _periode(texte)
        releve.debut, releve.fin = (debut.isoformat() if debut else ""), (fin.isoformat() if fin else "")
        colonnes: dict[str, float] = {}
        dernier: MouvementBanque | None = None
        solde_courant: Decimal | None = None
        for page in pdf.pages:
            for mots in _lignes(page.dedupe_chars()):
                mots = _fusionner_nombres(mots)
                bas = " ".join(m["text"] for m in mots).lower()
                if "solde" in bas and any(x in bas for x in ("retrait", "débit", "debit")):  # en-tête des colonnes
                    for m in mots:
                        nom = m["text"].lower().strip(".:")
                        if nom in ("retrait", "retraits", "débit", "débits", "debit"):
                            colonnes["retrait"] = m["x1"]
                        elif nom in ("dépôt", "dépôts", "depot", "depots", "crédit", "crédits", "credit"):
                            colonnes["depot"] = m["x1"]
                        elif nom == "solde":
                            colonnes["solde"] = m["x1"]
                    continue
                montants = [m for m in mots if MONTANT.match(m["text"])]
                autres = [m for m in mots if m not in montants]
                if re.search(r"solde (reporté|précédent|d'ouverture|au début|initial)|ancien solde", bas) and montants:
                    releve.solde_ouverture = solde_courant = _montant(montants[-1]["text"])
                    continue
                if re.search(r"(nouveau solde|solde de fermeture|solde à la fin|solde final)", bas) and montants:
                    releve.solde_fermeture = _montant(montants[-1]["text"])
                    continue
                if not colonnes:
                    continue
                jour = None
                if autres:
                    for n in (2, 1):  # « 02 SEP » ou « 2026-09-02 »
                        jour = _date_ligne(" ".join(m["text"] for m in autres[:n]), fin)
                        if jour:
                            autres = autres[n:]
                            break
                description = " ".join(m["text"] for m in autres).strip()
                if not montants:
                    if dernier and description and not jour:  # suite de la description sur la ligne suivante
                        dernier.description = f"{dernier.description} {description}".strip()
                    continue
                valeurs = {"retrait": None, "depot": None, "solde": None}
                for m in montants:
                    colonne = min(colonnes, key=lambda c: abs(colonnes[c] - m["x1"]))
                    valeurs[colonne] = _montant(m["text"])
                if valeurs["retrait"] is None and valeurs["depot"] is None:
                    if valeurs["solde"] is not None:
                        solde_courant = valeurs["solde"]
                    continue
                montant = (valeurs["depot"] or Decimal(0)) - (valeurs["retrait"] or Decimal(0))
                jour = jour or (date.fromisoformat(dernier.date) if dernier else None)
                if not jour:
                    releve.remarques.append(f"ligne sans date ignorée : {bas}")
                    continue
                dernier = MouvementBanque(jour.isoformat(), description, montant, valeurs["solde"], releve.fichier,
                                          len(releve.mouvements))
                if valeurs["solde"] is not None and solde_courant is not None and solde_courant + montant != valeurs["solde"]:
                    dernier.remarque = f"solde attendu {solde_courant + montant} $, imprimé {valeurs['solde']} $"
                if valeurs["solde"] is not None:
                    solde_courant = valeurs["solde"]
                elif solde_courant is not None:
                    solde_courant += montant
                releve.mouvements.append(dernier)
        if not colonnes:
            releve.remarques.append("colonnes Retrait / Dépôt / Solde introuvables (relevé numérisé ?)")
        if releve.solde_fermeture is None and solde_courant is not None and releve.mouvements:
            releve.solde_fermeture = solde_courant
    return releve


# --------------------------------------------------------------------------------------------- Sage
def mouvements_sage(base, debut: date, fin: date, compte: int = COMPTE_BANQUE) -> list[MouvementSage]:
    lignes = base.requete(
        "SELECT e.lId, e.dtJourDate, e.sSource, e.sComment, ROUND(SUM(a.dAmount), 2) montant FROM tjentact a "
        "JOIN tjourent e ON e.lId = a.lJEntId WHERE a.lAcctId = %s AND e.dtJourDate BETWEEN %s AND %s "
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


def comptes_sage(base) -> list[str]:
    """« 5450 Frais bancaires » : comptes actifs, pour le choix du compte d'une écriture à saisir."""
    from .base_sage import numero_compte

    return [f"{numero_compte(l['lId'])} {l['sName'].strip()}"
            for l in base.requete("SELECT lId, sName FROM taccount WHERE bInactive = 0 ORDER BY lId")]


# --------------------------------------------------------------------------------------------- rapprochement
def _dans_fenetre(banque: MouvementBanque, sage: MouvementSage) -> bool:
    ecart = (date.fromisoformat(banque.date) - date.fromisoformat(sage.date)).days
    return -APRES <= ecart <= AVANT


def rapprocher(banque: list[MouvementBanque], sage: list[MouvementSage]) -> None:
    """Relie les mouvements de banque aux écritures Sage (ne touche pas aux mouvements saisis, choisis ou ignorés)."""
    for s in sage:
        s.rapproche = False
    a_relier = [b for b in banque if b.etat in (A_SAISIR, RAPPROCHE)]
    for b in a_relier:
        b.etat, b.sage = A_SAISIR, []
    for b in banque:  # mouvements déjà saisis par l'application : leurs écritures restent prises
        if b.etat == SAISI:
            for s in sage:
                if s.ident in b.sage:
                    s.rapproche = True
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


def resume(banque: list[MouvementBanque], sage: list[MouvementSage], solde_banque: Decimal | None,
           solde_de_sage: Decimal | None) -> dict:
    """Chiffres du rapprochement : écart expliqué par les mouvements absents de Sage et les écritures en circulation."""
    absents = sum((b.montant for b in banque if b.etat in (A_SAISIR, CONFIRME)), Decimal(0))
    circulation = sum((s.montant for s in sage if not s.rapproche), Decimal(0))
    ecart = None if solde_banque is None or solde_de_sage is None else solde_banque - solde_de_sage
    explique = absents - circulation
    return {"solde_banque": solde_banque, "solde_sage": solde_de_sage, "ecart": ecart, "absents": absents,
            "circulation": circulation, "non_explique": None if ecart is None else ecart - explique}


# --------------------------------------------------------------------------------------------- registre
class RegistreReleves:
    """Relevés chargés et décisions du propriétaire (donnees/releves_desjardins/releves.json)."""

    def __init__(self, racine: Path):
        self.dossier = Path(racine) / "donnees" / "releves_desjardins"
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
        return sorted(p for p in self.dossier.glob("*.pdf")) if self.dossier.exists() else []

    def lire(self) -> list[Releve]:
        releves = []
        for chemin in self.fichiers():
            try:
                r = lire_releve(chemin)
            except Exception as exc:
                r = Releve(chemin.name, remarques=[f"lecture impossible : {exc}"])
            for m in r.mouvements:
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
                         ("Écart (banque − Sage)", "ecart"), ("Mouvements de banque absents de Sage", "absents"),
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


def periode_des(releves: list[Releve]) -> tuple[date, date] | None:
    jours = [date.fromisoformat(m.date) for r in releves for m in r.mouvements]
    debuts = [date.fromisoformat(r.debut) for r in releves if r.debut]
    fins = [date.fromisoformat(r.fin) for r in releves if r.fin]
    if not jours and not debuts:
        return None
    return min(debuts + jours), max(fins + jours)

