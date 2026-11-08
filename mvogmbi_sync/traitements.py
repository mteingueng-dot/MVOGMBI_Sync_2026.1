"""Récapitulatif des traitements (demande du propriétaire du 2026-11-08 : « ajoute aussi un tableau qui récapitule
tous les traitements effectués ; à tout moment je dois savoir quand un traitement a eu lieu dans le temps »).

Chaque traitement (traitement de nuit, « Charger la période », import dans Sage, saisies que l'application fait dans
Sage — encaissements, paiements, journal général, transferts, inventaire, articles, clients et fournisseurs, prix,
paie, dépenses, plan comptable —, travaux lancés depuis l'application web) est noté UNE fois dans
`donnees/journal_traitements.csv` : début, fin, durée, traitement, origine, personne, résultat, détail. Un traitement
lancé à l'intérieur d'un autre (la saisie dans Sage d'un travail web, l'import du traitement de nuit) n'est pas noté
une 2e fois. Les traitements de nuit d'avant ce registre sont repris de `journal_automatique.log`.

Le tableau est la vue « Récapitulatif des traitements » d'Administration > Journal des opérations (Windows et web).
Jamais d'erreur levée : le registre ne bloque jamais le travail.
"""

from __future__ import annotations

import csv
import re
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

FICHIER = "journal_traitements.csv"
ENTETES = ["Début", "Fin", "Durée", "Traitement", "Origine", "Lancé par", "Résultat", "Détail"]
_VERROU = threading.Lock()
_LOCAL = threading.local()   # profondeur (traitement dans un traitement) et personne du fil (travaux web)

# commandes internes (lancées sur le bureau de l'application) -> nom du traitement ; None = technique, jamais noté
COMMANDES = {
    "encaisser-bureau": "Encaissements dans Sage",
    "payer-bureau": "Paiements fournisseurs dans Sage",
    "journal-bureau": "Écritures du journal général dans Sage",
    "depenses-bureau": "Dépenses dans Sage",
    "transfert-bureau": "Transfert entre dépôts dans Sage",
    "inventaire-bureau": "Inventaire / document de stock dans Sage",
    "creer-articles-bureau": "Articles créés ou comptes corrigés dans Sage",
    "fiches-articles-bureau": "Articles modifiés ou supprimés dans Sage",
    "prix-sage-bureau": "Prix de vente changés dans Sage",
    "tiers-bureau": "Clients / fournisseurs créés dans Sage",
    "comptes-bureau": "Plan comptable modifié dans Sage",
    "paie-bureau": "Paie traitée dans Sage",
    "import-assistant-bureau": "Import dans Sage",
    "garder-sage": None, "fermer-sage-orphelin": None, "liberer-sage": None,
}


@dataclass
class Traitement:
    debut: str
    fin: str
    duree: str
    nom: str
    origine: str
    personne: str
    resultat: str
    detail: str

    def ligne(self) -> list[str]:
        return [self.debut, self.fin, self.duree, self.nom, self.origine, self.personne, self.resultat, self.detail]


def duree(secondes: float) -> str:
    s = int(round(max(0, secondes)))
    if s < 60:
        return f"{s} s"
    if s < 3600:
        return f"{s // 60} min {s % 60:02d} s"
    return f"{s // 3600} h {(s % 3600) // 60:02d} min"


def _racine(racine) -> Path | None:
    if racine:
        return Path(racine)
    try:
        from .__main__ import RACINE

        return Path(RACINE)
    except Exception:  # noqa: BLE001
        return None


def personne_courante() -> str:
    """Personne du fil (travail web), sinon personne connectée à l'application Windows, sinon « Automatique »."""
    import os

    nom = getattr(_LOCAL, "personne", "") or os.environ.get("MVOGMBI_LANCE_PAR", "")
    if nom:
        return nom
    try:
        from .audit import SESSION

        return SESSION.get("utilisateur") or "Automatique"
    except Exception:  # noqa: BLE001
        return "Automatique"


def definir_personne(nom: str) -> None:
    """Personne qui a lancé les traitements de ce fil (travaux de l'application web)."""
    _LOCAL.personne = nom or ""


def env_enfant(origine: str) -> dict:
    """Variables d'environnement d'un traitement lancé en commande (« Charger la période ») : personne et origine,
    reprises par le traitement qui s'y note lui-même."""
    return {"MVOGMBI_LANCE_PAR": personne_courante(), "MVOGMBI_ORIGINE": origine}


def origine_courante(defaut: str = "Application") -> str:
    """Origine du traitement en cours dans ce fil, sinon celle transmise par le programme qui a lancé la commande."""
    import os

    return getattr(_LOCAL, "origine", "") or os.environ.get("MVOGMBI_ORIGINE") or defaut


def noter(racine, t: Traitement) -> None:
    racine = _racine(racine)
    if racine is None:
        return
    try:
        chemin = racine / "donnees" / FICHIER
        with _VERROU:
            chemin.parent.mkdir(parents=True, exist_ok=True)
            nouveau = not chemin.exists()
            with chemin.open("a", encoding="utf-8-sig" if nouveau else "utf-8", newline="") as f:
                ecrivain = csv.writer(f, delimiter=";")
                if nouveau:
                    ecrivain.writerow(ENTETES)
                ecrivain.writerow([" ".join(str(x).split()) for x in t.ligne()])
    except Exception:  # noqa: BLE001 — le registre ne bloque jamais le travail
        pass


@contextmanager
def suivre(nom: str, racine=None, origine: str = "Application", personne: str | None = None, detail: str = ""):
    """Note le traitement à sa fin (réussi, ou « Échec : … » s'il lève une erreur). Un traitement lancé dans un
    autre n'est pas noté. `etat` (dict rendu) : etat["resultat"] / etat["detail"] précisent ce qui sera noté."""
    profondeur = getattr(_LOCAL, "profondeur", 0)
    etat = {"resultat": "Terminé", "detail": detail}
    _LOCAL.profondeur = profondeur + 1
    origine_avant = getattr(_LOCAL, "origine", "")
    if profondeur == 0:
        _LOCAL.origine = origine
    debut = datetime.now()
    try:
        yield etat
    except BaseException as erreur:
        etat["resultat"] = "Échec : " + (str(erreur).splitlines()[0][:200] if str(erreur) else type(erreur).__name__)
        raise
    finally:
        _LOCAL.profondeur = profondeur
        _LOCAL.origine = origine_avant
        if profondeur == 0 and nom:
            fin = datetime.now()
            noter(racine, Traitement(f"{debut:%Y-%m-%d %H:%M:%S}", f"{fin:%Y-%m-%d %H:%M:%S}",
                                     duree((fin - debut).total_seconds()), nom, origine,
                                     personne if personne is not None else personne_courante(),
                                     etat["resultat"], str(etat.get("detail") or "")[:500]))


def nom_commande(commande: list[str]) -> str | None:
    """Nom du traitement d'une commande interne (None = commande technique, non notée)."""
    for morceau in commande:
        if morceau in COMMANDES:
            return COMMANDES[morceau]
    return "Travail dans Sage"


# --------------------------------------------------------------------------------------------- lecture
_EXECUTION = re.compile(r"===== Exécution du (\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2})")
_HEURE = re.compile(r"^(\d{2}:\d{2}:\d{2}) ")


def _anciennes_nuits(racine: Path, avant: str) -> list[Traitement]:
    """Traitements automatiques notés dans journal_automatique.log avant le début du registre."""
    chemin = racine / "donnees" / "journal_automatique.log"
    if not chemin.exists():
        return []
    blocs, courant = [], None
    for ligne in chemin.read_text(encoding="utf-8", errors="replace").splitlines():
        m = _EXECUTION.search(ligne)
        if m:
            courant = {"jour": m.group(1), "debut": m.group(2), "fin": m.group(2), "lignes": []}
            blocs.append(courant)
        elif courant is not None and ligne.strip():
            h = _HEURE.match(ligne)
            if h:
                courant["fin"] = h.group(1)
            courant["lignes"].append(ligne.strip())
    sortie = []
    for b in blocs:
        debut = f"{b['jour']} {b['debut']}"
        if avant and debut >= avant:
            continue
        try:
            secondes = (datetime.strptime(b["fin"], "%H:%M:%S") - datetime.strptime(b["debut"], "%H:%M:%S")).seconds
        except ValueError:
            secondes = 0
        erreur = next((l for l in b["lignes"] if l.startswith("ERREUR")), "")
        problemes = sum(1 for l in b["lignes"] if l.startswith("PROBLÈME"))
        resultat = ("Échec : " + erreur[8:].strip()[:200] if erreur else
                    f"Terminé avec {problemes} problème(s)" if problemes else "Terminé")
        detail = " ; ".join(_HEURE.sub("", l) for l in b["lignes"] if not l.startswith(("Traceback", "File", "^")))
        sortie.append(Traitement(debut, f"{b['jour']} {b['fin']}", duree(secondes), "Traitement automatique",
                                 "Nuit", "Automatique", resultat, detail[:500]))
    return sortie


def lire(racine) -> list[Traitement]:
    """Tous les traitements, du plus récent au plus ancien."""
    racine = _racine(racine)
    if racine is None:
        return []
    traitements = []
    chemin = racine / "donnees" / FICHIER
    if chemin.exists():
        try:
            with chemin.open(encoding="utf-8-sig", newline="") as f:
                lecteur = csv.reader(f, delimiter=";")
                next(lecteur, None)
                for l in lecteur:
                    if len(l) >= 8:
                        traitements.append(Traitement(*l[:8]))
        except OSError:
            pass
    premier_auto = min((t.debut for t in traitements if t.origine == "Nuit"), default="")
    traitements += _anciennes_nuits(racine, premier_auto)
    return sorted(traitements, key=lambda t: t.debut, reverse=True)


def filtrer(liste: list[Traitement], du: str = "", au: str = "", nom: str = "", texte: str = "") -> list[Traitement]:
    texte = texte.casefold().strip()
    return [t for t in liste if (not du or t.debut[:10] >= du) and (not au or t.debut[:10] <= au)
            and (not nom or t.nom == nom)
            and (not texte or texte in " ".join(t.ligne()).casefold())]


def dernier(liste: list[Traitement], nom: str) -> Traitement | None:
    return next((t for t in liste if t.nom == nom), None)
