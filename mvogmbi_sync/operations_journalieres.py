"""Opérations journalières (demande du propriétaire du 2026-11-08 : « un tableau qui récapitule tous les traitements
effectués ; à tout moment je dois savoir quand un traitement a eu lieu dans le temps » — « c'est une table des
opérations journalières : vente, achat, encaissement, paiement fournisseur », « avec des filtres de navigation »).

Une ligne par opération inscrite dans Sage (lecture seule, `rapports.historique`) :
- Vente : facture de vente (tcustr nTranType 0), montant avant taxes ;
- Achat : facture d'achat (tventrdt nTranType 0), montant de la facture ;
- Encaissement : encaissement appliqué à une facture de vente (tcustrdt nTranType 1) ;
- Paiement fournisseur : paiement d'une facture d'achat (tventrdt nTranType 1 ou 2).

« Traité le » / « Par » / « Origine » : moment où l'APPLICATION a fait l'opération, d'après ses journaux
(`journal_imports.csv` pour les ventes, `journal_operations_traitees.csv` pour les achats, encaissements et paiements,
écrit à chaque opération réussie depuis la version 1.0.25) ; vide = saisie directement dans Sage (ou avant ce journal).

Navigation : période (aujourd'hui, hier, semaine, mois, année ou du … au …) avec ◀ / ▶ qui avancent d'une période,
types d'opération, « traitées par l'application / saisies dans Sage », recherche ; vue « Détail » ou « Par jour ».
"""

from __future__ import annotations

import csv
import threading
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

VENTE, ACHAT, ENCAISSEMENT, PAIEMENT = "Vente", "Achat", "Encaissement", "Paiement fournisseur"
TYPES = (VENTE, ACHAT, ENCAISSEMENT, PAIEMENT)
PERIODES = ("Aujourd'hui", "Hier", "Cette semaine", "Semaine dernière", "Ce mois", "Mois dernier", "Cette année",
            "Personnalisée")
VUES = ("Détail des opérations", "Par jour")
ETATS = ("Toutes", "Traitées par l'application", "Saisies dans Sage")
ENTETES = ["Date", "Type", "Référence", "Facture", "Client / fournisseur", "Montant", "Traité le", "Par", "Origine"]
ENTETES_JOURS = ["Date", "Jour", "Ventes", "Achats", "Encaissements", "Paiements fournisseurs", "Opérations",
                 "Traitées par l'application"]
JOURS = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")
FICHIER = "journal_operations_traitees.csv"
_ENTETES_FICHIER = ["Traité le", "Type", "Date", "Référence", "Facture", "Client / fournisseur", "Montant", "Par",
                    "Origine"]
_VERROU = threading.Lock()


@dataclass
class Operation:
    jour: date
    genre: str
    reference: str
    facture: str
    tiers: str
    montant: Decimal
    traite_le: str = ""
    par: str = ""
    origine: str = ""

    def ligne(self) -> list:
        return [self.jour.isoformat(), self.genre, self.reference, self.facture, self.tiers, self.montant,
                self.traite_le, self.par, self.origine]


# --------------------------------------------------------------------------------------------- noter
def noter(racine, genre: str, jour, reference: str, facture: str, tiers: str, montant) -> None:
    """Note une opération faite par l'application (achat importé, encaissement, paiement) ; jamais d'erreur."""
    from .traitements import origine_courante, personne_courante

    try:
        chemin = Path(racine) / "donnees" / FICHIER
        with _VERROU:
            chemin.parent.mkdir(parents=True, exist_ok=True)
            nouveau = not chemin.exists()
            with chemin.open("a", encoding="utf-8-sig" if nouveau else "utf-8", newline="") as f:
                w = csv.writer(f, delimiter=";")
                if nouveau:
                    w.writerow(_ENTETES_FICHIER)
                w.writerow([f"{datetime.now():%Y-%m-%d %H:%M:%S}", genre, str(jour)[:10], reference, facture, tiers,
                            str(montant), personne_courante(), origine_courante()])
    except Exception:  # noqa: BLE001 — le journal ne bloque jamais le travail
        pass


def _cle(*morceaux) -> tuple:
    return tuple(" ".join(str(m or "").split()).casefold() for m in morceaux)


def traces(racine) -> dict:
    """{clé de l'opération: (traité le, par, origine)} d'après les journaux de l'application (le plus récent gagne)."""
    donnees = Path(racine) / "donnees"
    trouve: dict = {}
    imports = donnees / "journal_imports.csv"
    if imports.exists():
        with imports.open(encoding="utf-8-sig", newline="") as f:
            for l in csv.DictReader(f, delimiter=";"):
                resultat = (l.get("Résultat") or "").casefold()
                if l.get("Facture") and ("import" in resultat or resultat in ("ok", "réussi")):
                    trouve[_cle(VENTE, l["Facture"])] = (l.get("Date et heure", ""), "", "")
    chemin = donnees / FICHIER
    if chemin.exists():
        with chemin.open(encoding="utf-8-sig", newline="") as f:
            for l in csv.DictReader(f, delimiter=";"):
                valeur = (l.get("Traité le", ""), l.get("Par", ""), l.get("Origine", ""))
                if l.get("Type") == ACHAT:
                    trouve[_cle(ACHAT, l.get("Client / fournisseur"), l.get("Référence"))] = valeur
                else:  # un encaissement ou un paiement touche une ligne par facture
                    for facture in (l.get("Facture") or "").split(","):
                        trouve[_cle(l.get("Type"), l.get("Date"), facture)] = valeur
    return trouve


# --------------------------------------------------------------------------------------------- lire
def _jour(valeur) -> date | None:
    if isinstance(valeur, datetime):
        return valeur.date()
    if isinstance(valeur, date):
        return valeur
    try:
        return date.fromisoformat(str(valeur)[:10])
    except ValueError:
        return None


def lire(racine, h: dict) -> list[Operation]:
    """Toutes les opérations de l'historique Sage `h` (rapports.historique), la plus récente en haut."""
    from .rapports import _d

    ops: list[Operation] = []
    for l in h.get("ventes", []):
        j = _jour(l.get("dtDate"))
        if j:
            ops.append(Operation(j, VENTE, l.get("f") or "", l.get("f") or "", l.get("client") or "", _d(l.get("m"))))
    for l in h.get("clients", []):
        j = _jour(l.get("dtDate"))
        if j and l.get("nTranType") == 1:
            ops.append(Operation(j, ENCAISSEMENT, l.get("piece") or "", l.get("f") or "", l.get("nom") or "",
                                 -_d(l.get("dAmount"))))
    for l in h.get("fournisseurs", []):
        j = _jour(l.get("dtDate"))
        if j and l.get("nTranType") == 0:
            ops.append(Operation(j, ACHAT, l.get("f") or "", l.get("f") or "", l.get("nom") or "",
                                 _d(l.get("dAmount"))))
        elif j and l.get("nTranType") in (1, 2):
            ops.append(Operation(j, PAIEMENT, l.get("piece") or "", l.get("f") or "", l.get("nom") or "",
                                 -_d(l.get("dAmount"))))
    trouve = traces(racine)
    for o in ops:
        cle = (_cle(VENTE, o.facture) if o.genre == VENTE else _cle(ACHAT, o.tiers, o.facture) if o.genre == ACHAT
               else _cle(o.genre, o.jour.isoformat(), o.facture))
        if cle in trouve:
            o.traite_le, o.par, o.origine = trouve[cle]
            o.origine = o.origine or "Application"
    return sorted(ops, key=lambda o: (o.jour, o.traite_le), reverse=True)


# --------------------------------------------------------------------------------------------- navigation
def bornes(periode: str, aujourd_hui: date | None = None) -> tuple[date, date]:
    a = aujourd_hui or date.today()
    lundi = a - timedelta(days=a.weekday())
    debut_mois = a.replace(day=1)
    fin_mois_dernier = debut_mois - timedelta(days=1)
    return {
        "Aujourd'hui": (a, a),
        "Hier": (a - timedelta(days=1), a - timedelta(days=1)),
        "Cette semaine": (lundi, lundi + timedelta(days=6)),
        "Semaine dernière": (lundi - timedelta(days=7), lundi - timedelta(days=1)),
        "Ce mois": (debut_mois, (debut_mois + timedelta(days=32)).replace(day=1) - timedelta(days=1)),
        "Mois dernier": (fin_mois_dernier.replace(day=1), fin_mois_dernier),
        "Cette année": (a.replace(month=1, day=1), a.replace(month=12, day=31)),
    }.get(periode, (a - timedelta(days=30), a))


def decaler(du: date, au: date, sens: int) -> tuple[date, date]:
    """◀ / ▶ : période précédente ou suivante de même genre (jour, semaine, mois entier, année, ou même durée)."""
    if du.day == 1 and (au + timedelta(days=1)).day == 1 and du.month == au.month and du.year == au.year:  # un mois
        if sens < 0:
            fin = du - timedelta(days=1)
            return fin.replace(day=1), fin
        debut = au + timedelta(days=1)
        return debut, (debut + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    if (du.month, du.day, au.month, au.day) == (1, 1, 12, 31) and du.year == au.year:  # une année
        return du.replace(year=du.year + sens), au.replace(year=au.year + sens)
    longueur = (au - du).days + 1
    return du + timedelta(days=sens * longueur), au + timedelta(days=sens * longueur)


def filtrer(ops: list[Operation], du: date | None = None, au: date | None = None, genres=None, etat: str = "Toutes",
            texte: str = "") -> list[Operation]:
    genres = set(genres or TYPES)
    texte = texte.strip().casefold()
    return [o for o in ops if (du is None or o.jour >= du) and (au is None or o.jour <= au) and o.genre in genres
            and (etat == "Toutes" or (etat == ETATS[1]) == bool(o.traite_le))
            and (not texte or texte in " ".join(str(x) for x in o.ligne()).casefold())]


def par_jour(ops: list[Operation]) -> list[list]:
    jours: dict[date, dict] = {}
    for o in ops:
        j = jours.setdefault(o.jour, {g: Decimal(0) for g in TYPES} | {"n": 0, "app": 0})
        j[o.genre] += o.montant
        j["n"] += 1
        j["app"] += bool(o.traite_le)
    return [[j.isoformat(), JOURS[j.weekday()], v[VENTE], v[ACHAT], v[ENCAISSEMENT], v[PAIEMENT], v["n"], v["app"]]
            for j, v in sorted(jours.items(), reverse=True)]


def totaux(ops: list[Operation]) -> list[tuple[str, int, Decimal]]:
    """(type, nombre, montant) de chaque type d'opération."""
    return [(g, sum(1 for o in ops if o.genre == g), sum((o.montant for o in ops if o.genre == g), Decimal(0)))
            for g in TYPES]
