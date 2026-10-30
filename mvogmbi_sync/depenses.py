"""Petite caisse et dépenses avec reçu (demande du propriétaire du 2026-10-29) : chaque dépense (date, fournisseur,
montant payé taxes comprises, taxes, compte de charge, payée par la petite caisse, la carte de crédit ou un employé à
rembourser, photo ou PDF du reçu) est notée « DP-0001 » ; l'écriture se passe dans Sage par la fenêtre « Journal
général » (robot_journal, Sage fermé : l'application l'ouvre elle-même) : débit de la charge (hors taxes) et des taxes
payées (TPS 5 %, TVQ 9,975 %, à récupérer), crédit du compte de paiement. Approvisionnements de la petite caisse
notés aussi ; solde de la petite caisse = approvisionnements − dépenses payées par elle.
"""

from __future__ import annotations

import json
import shutil
import time
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

CENT = Decimal("0.01")
ZERO = Decimal(0)
TPS, TVQ = Decimal("0.05"), Decimal("0.09975")
PETITE_CAISSE, CARTE, EMPLOYE = "Petite caisse", "Carte de crédit", "Employé à rembourser"
MOYENS = [PETITE_CAISSE, CARTE, EMPLOYE]
A_SAISIR, SAISIE, APPRO = "À saisir dans Sage", "Saisie dans Sage", "Approvisionnement"
COMPTES = {"tps": "TPS payée", "tvq": "TVQ payée", "petite_caisse": PETITE_CAISSE, "carte": CARTE,
           "employe": EMPLOYE, "banque": "Banque (approvisionnement)"}


def taxes_de(ttc: Decimal, code: str) -> tuple[Decimal, Decimal, Decimal]:
    """(hors taxes, TPS, TVQ) d'un montant payé taxes comprises ; code « GQ », « G », « Q » ou « »."""
    taux = (TPS if "G" in code else ZERO) + (TVQ if "Q" in code else ZERO)
    ht = (ttc / (1 + taux)).quantize(CENT, ROUND_HALF_UP)
    tps = (ht * TPS).quantize(CENT, ROUND_HALF_UP) if "G" in code else ZERO
    tvq = (ttc - ht - tps) if "Q" in code else ZERO  # l'écart d'arrondi va à la TVQ : total = montant payé
    if "Q" not in code:
        ht = ttc - tps
    return ht, tps, tvq


@dataclass
class Depense:
    numero: str
    jour: str
    fournisseur: str
    description: str
    montant: str               # payé, taxes comprises (approvisionnement : montant remis dans la petite caisse)
    taxe: str = "GQ"
    compte: str = ""           # compte de charge (ex. 5450)
    moyen: str = PETITE_CAISSE
    recu: str = ""             # fichier du reçu dans donnees/recus/
    etat: str = A_SAISIR
    ecriture: int | None = None
    auteur: str = ""
    cree: str = ""
    messages: list[str] = field(default_factory=list)

    @property
    def source(self) -> str:
        return f"Dépense {self.numero}"[:20]

    def lignes(self, comptes: dict[str, str]) -> list[tuple[str, Decimal, Decimal]]:
        """[(compte, débit, crédit)] de l'écriture ; débits = crédits = montant. Le crédit d'abord : sur chaque ligne
        suivante, Sage propose le reste au DÉBIT, là où l'application tape (constat du 2026-10-29 : un débit après un
        autre débit trouvait la proposition au crédit et la case du débit ne s'ouvrait pas)."""
        montant = Decimal(self.montant)
        if self.moyen == APPRO:
            return [(comptes["banque"], ZERO, montant), (comptes["petite_caisse"], montant, ZERO)]
        ht, tps, tvq = taxes_de(montant, self.taxe)
        credit = {PETITE_CAISSE: "petite_caisse", CARTE: "carte", EMPLOYE: "employe"}[self.moyen]
        lignes = [(comptes[credit], ZERO, montant), (self.compte, ht, ZERO)]
        if tps:
            lignes.append((comptes["tps"], tps, ZERO))
        if tvq:
            lignes.append((comptes["tvq"], tvq, ZERO))
        return lignes


class Registre:
    def __init__(self, racine: Path):
        self.racine = Path(racine)
        self.chemin = self.racine / "donnees" / "depenses.json"
        donnees = json.loads(self.chemin.read_text(encoding="utf-8")) if self.chemin.exists() else {}
        self.depenses = [Depense(**d) for d in donnees.get("depenses", [])]
        self.comptes: dict[str, str] = donnees.get("comptes", {})

    def enregistrer(self) -> None:
        self.chemin.parent.mkdir(parents=True, exist_ok=True)
        provisoire = self.chemin.with_suffix(".tmp")
        provisoire.write_text(json.dumps({"depenses": [asdict(d) for d in self.depenses], "comptes": self.comptes},
                                         ensure_ascii=False, indent=1), encoding="utf-8")
        provisoire.replace(self.chemin)

    def ajouter(self, d: Depense, recu: Path | None = None) -> Depense:
        if Decimal(d.montant) <= 0:
            raise ValueError("Le montant doit être positif.")
        date.fromisoformat(d.jour)
        if d.moyen != APPRO and not d.compte.isdigit():
            raise ValueError("Choisissez le compte de charge (ex. 5450).")
        n = max((int(x.numero.split("-")[1]) for x in self.depenses), default=0) + 1
        d.numero, d.cree = f"DP-{n:04d}", datetime.now().isoformat(timespec="seconds")
        if d.moyen == APPRO:
            d.etat = A_SAISIR
        if recu:
            dossier = self.racine / "donnees" / "recus"
            dossier.mkdir(parents=True, exist_ok=True)
            cible = dossier / f"{d.numero}{Path(recu).suffix.lower()}"
            shutil.copy2(recu, cible)
            d.recu = cible.name
        self.depenses.append(d)
        self.enregistrer()
        return d

    def solde_petite_caisse(self) -> Decimal:
        entrees = sum((Decimal(d.montant) for d in self.depenses if d.moyen == APPRO), ZERO)
        sorties = sum((Decimal(d.montant) for d in self.depenses if d.moyen == PETITE_CAISSE), ZERO)
        return entrees - sorties

    def comptes_manquants(self, depenses: list[Depense] | None = None) -> list[str]:
        """Comptes nécessaires aux dépenses à saisir : TPS et TVQ payées, et le compte de chaque moyen utilisé."""
        depenses = self.depenses if depenses is None else depenses
        cles = {"tps", "tvq"} | {{PETITE_CAISSE: "petite_caisse", CARTE: "carte", EMPLOYE: "employe"}.get(d.moyen, "")
                                 for d in depenses} | ({"petite_caisse", "banque"} if any(d.moyen == APPRO
                                                                                         for d in depenses) else set())
        return [COMPTES[c] for c in COMPTES if c in cles and not str(self.comptes.get(c, "")).isdigit()]


def proposer_comptes(base) -> dict[str, str]:
    """Comptes de Sage dont le nom correspond (TPS / TVQ payée, petite caisse, carte de crédit, banque)."""
    import unicodedata

    def simple(t):
        return unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().lower()

    noms = {str(r["lId"])[:4]: simple(r["sName"]) for r in base.requete("SELECT lId, sName FROM taccount")}
    regles = {"tps": lambda n: ("tps" in n or "federal" in n) and "paye" in n,
              "tvq": lambda n: ("tvq" in n or "quebec" in n) and "paye" in n,
              "petite_caisse": lambda n: "petite caisse" in n,
              "carte": lambda n: "carte" in n and "credit" in n,
              "banque": lambda n: "desjardins" in n or n.startswith("banque") or "compte courant" in n}
    return {cle: next((numero for numero, nom in sorted(noms.items()) if test(nom)), "") for cle, test in regles.items()}


# --------------------------------------------------------------------------------------------- Sage
def ecriture_presente(base, d: Depense) -> int | None:
    lignes = base.requete("SELECT lId FROM tjourent WHERE sSource = %s AND dtJourDate = %s AND nType NOT IN "
                          "(32, 33, 64, 65) ORDER BY lId DESC LIMIT 1", (d.source, d.jour))
    return lignes[0]["lId"] if lignes else None


def saisir(f, d: Depense, comptes: dict[str, str]) -> list[str]:
    """Remplit la fenêtre « Journal général » ouverte puis « Traiter » ; renvoie les problèmes (vide si traité)."""
    from .robot_encaissements import ResultatEncaissement, montant_sage
    from .robot_journal import HAUTEUR_LIGNE, ID_REMARQUE, ID_SOURCE, LONGUEUR_REMARQUE, X_COMPTE, X_CREDIT, X_DEBIT

    lignes = d.lignes(comptes)
    f.ecrire(ID_SOURCE, d.source)
    f.regler_date(d.jour)
    f.ecrire(ID_REMARQUE, f"{d.fournisseur} {d.description}"[:LONGUEUR_REMARQUE])
    for rang, (compte, debit, credit) in enumerate(lignes):
        y = f.ligne_y0 + HAUTEUR_LIGNE * rang
        f.taper(X_COMPTE, y, compte, "Compte")
        if f.dialogues():
            return [f"Sage ne reconnaît pas le compte {compte}."]
        f.taper(X_DEBIT if debit else X_CREDIT, y, montant_sage(debit or credit), "Montant")
    attendu = Decimal(d.montant)
    if f.totaux() != (attendu, attendu):
        return [f"totaux affichés {f.totaux()} au lieu de {attendu} : écriture abandonnée"]
    r = ResultatEncaissement(d.jour, attendu)
    return [] if f.traiter(r) else (r.messages or ["Sage n'a pas traité l'écriture"])


def saisir_sur_bureau_cache(racine: Path, config_toml: dict, journal=print) -> dict:
    """Exécuté sur le bureau caché : ouvre Sage, saisit les dépenses « À saisir dans Sage », les vérifie."""
    from . import coffre
    from .__main__ import executable_import, lire_sage
    from .robot_inventaire import FenetreAjustement
    from .robot_journal import FenetreJournal
    from .sage_bureau import SessionSage, executable_sage

    class FenetreJournalDepense(FenetreJournal):
        """« Traiter » qui attend la fenêtre « Traitement… » de Sage (sans texte) au lieu de la refuser."""
        message = staticmethod(FenetreAjustement.message)
        traiter = FenetreAjustement.traiter

    registre = Registre(racine)
    bilan = {"saisies": [], "a_verifier": [], "erreur": ""}
    a_faire = [d for d in registre.depenses if d.etat == A_SAISIR]
    if not a_faire:
        return bilan
    manquants = registre.comptes_manquants(a_faire)
    if manquants:
        bilan["erreur"] = "Comptes Sage à choisir : " + ", ".join(manquants)
        return bilan
    fichier = config_toml.get("sage_import", {}).get("fichier_entreprise")
    session = SessionSage(executable_sage(executable_import()), journal)
    try:
        session.ouvrir(fichier, str(config_toml.get("sage_import", {}).get("utilisateur", "sysadmin")),
                       coffre.lire(coffre.SAGE_IMPORT, ""))
        session.ouvrir_journal()
        f = FenetreJournalDepense()
        for d in a_faire:
            deja = lire_sage(config_toml, lambda b: ecriture_presente(b, d), fichier)
            if deja:
                d.etat, d.ecriture = SAISIE, deja
                bilan["saisies"].append(f"{d.numero} déjà dans Sage (écriture n° {deja})")
                continue
            problemes = saisir(f, d, registre.comptes)
            time.sleep(1.5)
            numero = None if problemes else lire_sage(config_toml, lambda b: ecriture_presente(b, d), fichier)
            if numero:
                d.etat, d.ecriture, d.messages = SAISIE, numero, []
                bilan["saisies"].append(f"{d.numero} {d.fournisseur} {d.montant} $ : écriture n° {numero}")
            else:
                d.messages = problemes or ["absente de Sage après « Traiter »"]
                bilan["a_verifier"].append(f"{d.numero} : " + " ; ".join(d.messages))
                break  # jamais la suivante après un problème
            registre.enregistrer()
    except Exception as exc:
        bilan["erreur"] = str(exc)
    finally:
        registre.enregistrer()
        session.fermer()
    return bilan
