"""Pointage et feuilles de temps (demande du propriétaire du 2026-10-29, rubrique Paie).

Choix du propriétaire : pointage au magasin avec un NIP, paie aux 2 semaines, calcul de la paie par Sage Paie (les
heures approuvées y sont envoyées ; Sage calcule les retenues avec ses tables). Les données sensibles (NAS, taux,
adresses) restent dans Sage : ici, seulement le nom, l'empreinte du NIP (PBKDF2, jamais le NIP) et les heures.

Fichiers (donnees/) : employes_paie.json (employés et empreintes de NIP), pointages.json (chaque pointage, jamais
effacé : une correction du gérant est un nouveau pointage, ou l'annulation d'un pointage, avec l'auteur et le
motif), feuilles_temps.json (approbations par période et par employé).

Calcul : une présence = arrivée … départ, moins les pauses pointées (pause repas non payée) ; elle compte pour le
jour de l'arrivée. Heures supplémentaires : au-delà de 40 h par semaine (Loi sur les normes du travail du Québec),
semaine de 7 jours à partir du 1er jour de la période. Période de paie : 14 jours à partir de [paie]
debut_reference (un dimanche par défaut). Anomalies (départ manquant, pause non terminée…) : la feuille ne peut
pas être approuvée tant que le gérant ne les a pas corrigées.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import uuid
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

ARRIVEE, PAUSE, FIN_PAUSE, DEPART = "Arrivée", "Début de pause", "Fin de pause", "Départ"
TYPES = (ARRIVEE, PAUSE, FIN_PAUSE, DEPART)
JOURS_PERIODE = 14
HEURES_SEMAINE = Decimal(40)
DEBUT_REFERENCE = date(2026, 10, 18)  # un dimanche ; réglable : [paie] debut_reference
ITERATIONS = 200_000
A_APPROUVER, APPROUVEE, ENVOYEE = "À approuver", "Approuvée", "Envoyée à Sage"
ESSAIS_NIP, ATTENTE_NIP = 5, 60  # 5 NIP faux de suite : pointage bloqué 60 s pour cet employé


class ErreurPointage(ValueError):
    """Pointage refusé (message à afficher tel quel)."""


def _empreinte(nip: str, sel: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", nip.encode("utf-8"), bytes.fromhex(sel), ITERATIONS).hex()


def _heures(secondes: float) -> Decimal:
    return (Decimal(str(secondes)) / 3600).quantize(Decimal("0.01"))


@dataclass
class Employe:
    id: str
    nom: str
    sel: str = ""
    nip: str = ""          # empreinte
    actif: bool = True
    numero_sage: str = ""  # employé de Sage Paie (lien pour l'envoi des heures)
    clover: str = ""       # identifiant de l'employé Clover (importé)
    compte: str = ""       # compte de l'application relié (« Paie > Mon horaire »)


@dataclass
class Pointage:
    id: str
    employe: str
    type: str
    moment: str            # AAAA-MM-JJTHH:MM:SS (heure locale)
    source: str = "NIP"    # « NIP » ou « Correction »
    auteur: str = ""
    motif: str = ""
    annule: str = ""       # id du pointage qui l'annule (correction)
    cree: str = ""

    @property
    def quand(self) -> datetime:
        return datetime.fromisoformat(self.moment)


# --------------------------------------------------------------------------------------------- employés
class Registre:
    def __init__(self, racine: Path):
        self.donnees = Path(racine) / "donnees"
        self.employes: list[Employe] = [Employe(**e) for e in self._lire("employes_paie.json", [])]
        self.pointages: list[Pointage] = [Pointage(**p) for p in self._lire("pointages.json", [])]
        self.feuilles: dict = self._lire("feuilles_temps.json", {})
        self._echecs: dict[str, tuple[int, datetime]] = {}

    def _lire(self, nom: str, defaut):
        chemin = self.donnees / nom
        return json.loads(chemin.read_text(encoding="utf-8")) if chemin.exists() else defaut

    def _ecrire(self, nom: str, valeur) -> None:
        self.donnees.mkdir(parents=True, exist_ok=True)
        temporaire = self.donnees / (nom + ".tmp")
        temporaire.write_text(json.dumps(valeur, ensure_ascii=False, indent=1), encoding="utf-8")
        temporaire.replace(self.donnees / nom)  # jamais un fichier à moitié écrit

    def recharger(self) -> None:
        """Ajoute les pointages écrits entre-temps par une autre fenêtre (fusion par identifiant ; un pointage
        n'est jamais modifié) ; employés relus (NIP changé par le gérant)."""
        connus = {p.id for p in self.pointages}
        self.pointages += [Pointage(**p) for p in self._lire("pointages.json", []) if p["id"] not in connus]

    def recharger_employes(self) -> None:
        self.employes = [Employe(**e) for e in self._lire("employes_paie.json", [])]

    def enregistrer(self, tout: bool = True) -> None:
        """`tout` faux (poste de pointage) : seulement les pointages, jamais les employés ni les approbations,
        que le gérant a pu changer entre-temps."""
        self.recharger()  # le poste de pointage et la fenêtre du gérant peuvent être ouverts en même temps
        self._ecrire("pointages.json", [asdict(p) for p in self.pointages])
        if tout:
            self._ecrire("employes_paie.json", [asdict(e) for e in self.employes])
            self._ecrire("feuilles_temps.json", self.feuilles)

    def employe(self, ident: str) -> Employe:
        return next(e for e in self.employes if e.id == ident)

    def actifs(self) -> list[Employe]:
        return sorted((e for e in self.employes if e.actif), key=lambda e: e.nom.casefold())

    def ajouter(self, nom: str, clover: str = "") -> Employe:
        nom = " ".join(nom.split())
        if not nom:
            raise ErreurPointage("Le nom est obligatoire.")
        if any(e.nom.casefold() == nom.casefold() for e in self.employes):
            raise ErreurPointage(f"« {nom} » existe déjà.")
        e = Employe(uuid.uuid4().hex[:12], nom, clover=clover)
        self.employes.append(e)
        return e

    def renommer(self, ident: str, nom: str) -> None:
        nom = " ".join(nom.split())
        if not nom:
            raise ErreurPointage("Le nom est obligatoire.")
        if any(e.nom.casefold() == nom.casefold() and e.id != ident for e in self.employes):
            raise ErreurPointage(f"« {nom} » existe déjà.")
        self.employe(ident).nom = nom

    def supprimer(self, ident: str) -> None:
        """Seulement un employé qui n'a jamais pointé (sinon ses heures resteraient sans nom : le désactiver)."""
        if any(p.employe == ident for p in self.pointages):
            raise ErreurPointage("Cet employé a des pointages : désactivez-le plutôt (ses heures sont gardées).")
        self.employes = [e for e in self.employes if e.id != ident]

    def importer_clover(self, employes_clover: list[dict]) -> int:
        """Employés Clover absents du registre (par identifiant Clover ou par nom) ; renvoie le nombre ajouté."""
        connus = {e.clover for e in self.employes} | {e.nom.casefold() for e in self.employes}
        ajoutes = 0
        for c in employes_clover:
            nom = " ".join((c.get("name") or c.get("nickname") or "").split())
            if not nom or c.get("id") in connus or nom.casefold() in connus:
                continue
            self.ajouter(nom, c.get("id", ""))
            connus |= {c.get("id"), nom.casefold()}
            ajoutes += 1
        return ajoutes

    def definir_nip(self, ident: str, nip: str) -> None:
        if not (nip.isdigit() and 4 <= len(nip) <= 6):
            raise ErreurPointage("Le NIP doit avoir 4 à 6 chiffres.")
        e = self.employe(ident)
        autres = [x for x in self.employes if x.id != ident and x.nip]
        if any(_empreinte(nip, x.sel) == x.nip for x in autres):
            raise ErreurPointage("Ce NIP est déjà celui d'un autre employé : choisissez-en un autre.")
        e.sel = secrets.token_hex(16)
        e.nip = _empreinte(nip, e.sel)

    def verifier_nip(self, ident: str, nip: str, maintenant: datetime | None = None) -> bool:
        maintenant = maintenant or datetime.now()
        echecs, depuis = self._echecs.get(ident, (0, maintenant))
        if echecs >= ESSAIS_NIP and (maintenant - depuis).total_seconds() < ATTENTE_NIP:
            raise ErreurPointage("Trop d'essais : attendez une minute.")
        e = self.employe(ident)
        bon = bool(e.nip) and _empreinte(nip, e.sel) == e.nip
        self._echecs[ident] = (0, maintenant) if bon else (
            (1 if echecs >= ESSAIS_NIP else echecs + 1), maintenant)
        return bon

    # ----------------------------------------------------------------------------------------- pointages
    def valides(self, ident: str | None = None) -> list[Pointage]:
        """Pointages en vigueur (sans les pointages annulés), dans l'ordre du temps."""
        annules = {p.annule for p in self.pointages if p.annule}
        return sorted((p for p in self.pointages if not p.annule and p.id not in annules
                       and (ident is None or p.employe == ident)), key=lambda p: (p.moment, p.cree))

    def etat_actuel(self, ident: str) -> str:
        """Dernier pointage en vigueur de l'employé : « » (absent), Arrivée, Début de pause, Fin de pause."""
        derniers = self.valides(ident)
        if not derniers or derniers[-1].type == DEPART:
            return ""
        return derniers[-1].type

    def actions_permises(self, ident: str) -> list[str]:
        etat = self.etat_actuel(ident)
        if etat == "":
            return [ARRIVEE]
        if etat == PAUSE:
            return [FIN_PAUSE, DEPART]
        return [PAUSE, DEPART]

    def pointer(self, ident: str, type_: str, maintenant: datetime | None = None) -> Pointage:
        """Pointage d'un employé au poste du magasin (le NIP a été vérifié avant)."""
        self.recharger()
        if type_ not in self.actions_permises(ident):
            raise ErreurPointage(f"« {type_} » n'est pas possible maintenant.")
        maintenant = (maintenant or datetime.now()).replace(microsecond=0)
        nouveaux = []
        if type_ == DEPART and self.etat_actuel(ident) == PAUSE:  # départ pendant la pause : la pause se termine
            nouveaux.append(Pointage(uuid.uuid4().hex, ident, FIN_PAUSE, maintenant.isoformat(), cree=_maintenant()))
        nouveaux.append(Pointage(uuid.uuid4().hex, ident, type_, maintenant.isoformat(), cree=_maintenant()))
        self.pointages += nouveaux
        self.enregistrer(tout=False)
        return nouveaux[-1]

    def corriger(self, ident: str, type_: str, moment: datetime, auteur: str, motif: str,
                 remplace: str = "") -> Pointage:
        """Correction du gérant : nouveau pointage (et annulation de celui qu'il remplace) ; motif obligatoire."""
        if not motif.strip():
            raise ErreurPointage("Le motif de la correction est obligatoire.")
        if type_ not in TYPES:
            raise ErreurPointage("Type de pointage inconnu.")
        nouveau = Pointage(uuid.uuid4().hex, ident, type_, moment.replace(microsecond=0).isoformat(), "Correction",
                           auteur, motif.strip(), cree=_maintenant())
        self.pointages.append(nouveau)
        if remplace:
            self._annuler(remplace, auteur, motif)
        self.enregistrer()
        return nouveau

    def annuler(self, ident_pointage: str, auteur: str, motif: str) -> None:
        if not motif.strip():
            raise ErreurPointage("Le motif de la correction est obligatoire.")
        self._annuler(ident_pointage, auteur, motif)
        self.enregistrer()

    def _annuler(self, ident_pointage: str, auteur: str, motif: str) -> None:
        cible = next(p for p in self.pointages if p.id == ident_pointage)
        self.pointages.append(Pointage(uuid.uuid4().hex, cible.employe, cible.type, cible.moment, "Correction",
                                       auteur, motif.strip(), annule=cible.id, cree=_maintenant()))


def _maintenant() -> str:
    return datetime.now().isoformat(timespec="seconds")


# --------------------------------------------------------------------------------------------- calcul
@dataclass
class Presence:
    jour: date
    arrivee: datetime
    depart: datetime | None
    pauses: Decimal = Decimal(0)
    anomalies: list[str] = field(default_factory=list)

    @property
    def heures(self) -> Decimal:
        if self.depart is None:
            return Decimal(0)
        return max(Decimal(0), _heures((self.depart - self.arrivee).total_seconds()) - self.pauses)


def presences(pointages: list[Pointage], maintenant: datetime | None = None) -> tuple[list[Presence], list[str]]:
    """Pointages en vigueur d'un employé -> présences ; renvoie aussi les anomalies hors présence."""
    maintenant = maintenant or datetime.now()
    resultat, isoles, courante, debut_pause = [], [], None, None
    for p in pointages:
        quand = p.quand
        if p.type == ARRIVEE:
            if courante is not None:
                courante.anomalies.append("Départ manquant")
                resultat.append(courante)
            courante, debut_pause = Presence(quand.date(), quand, None), None
        elif courante is None:
            isoles.append(f"{quand:%Y-%m-%d %H:%M} : {p.type} sans arrivée")
        elif p.type == PAUSE:
            if debut_pause is not None:
                courante.anomalies.append("Pause non terminée")
            debut_pause = quand
        elif p.type == FIN_PAUSE:
            if debut_pause is None:
                courante.anomalies.append("Fin de pause sans début")
            else:
                courante.pauses += _heures((quand - debut_pause).total_seconds())
                debut_pause = None
        elif p.type == DEPART:
            if debut_pause is not None:
                courante.anomalies.append("Pause non terminée")
            courante.depart, debut_pause = quand, None
            resultat.append(courante)
            courante = None
    if courante is not None:
        if courante.jour < maintenant.date():
            courante.anomalies.append("Départ manquant")
        resultat.append(courante)  # présence en cours aujourd'hui : pas encore d'heures
    return resultat, isoles


def debut_periode(jour: date, reference: date = DEBUT_REFERENCE) -> date:
    return reference + timedelta(days=((jour - reference).days // JOURS_PERIODE) * JOURS_PERIODE)


@dataclass
class Feuille:
    employe: Employe
    debut: date
    jours: list[Decimal]                  # heures de chacun des 14 jours
    normales: Decimal
    supplementaires: Decimal
    anomalies: list[str]
    corrigee: bool                        # au moins un pointage corrigé par le gérant dans la période
    etat: str = A_APPROUVER
    approuvee_par: str = ""

    @property
    def total(self) -> Decimal:
        return self.normales + self.supplementaires

    @property
    def semaines(self) -> list[Decimal]:
        return [sum(self.jours[:7], Decimal(0)), sum(self.jours[7:], Decimal(0))]

    def empreinte(self) -> str:
        return ",".join(str(h) for h in self.jours)


def feuille(registre: Registre, employe: Employe, debut: date, maintenant: datetime | None = None) -> Feuille:
    fin = debut + timedelta(days=JOURS_PERIODE)
    valides = registre.valides(employe.id)
    liste, isoles = presences(valides, maintenant)
    jours = [Decimal(0)] * JOURS_PERIODE
    anomalies = []
    for pr in liste:
        if not debut <= pr.jour < fin:
            continue
        jours[(pr.jour - debut).days] += pr.heures
        anomalies += [f"{pr.jour:%Y-%m-%d} : {a}" for a in pr.anomalies]
    anomalies += [a for a in isoles if debut.isoformat() <= a[:10] < fin.isoformat()]
    normales, supp = Decimal(0), Decimal(0)
    for semaine in (jours[:7], jours[7:]):
        total = sum(semaine, Decimal(0))
        normales += min(total, HEURES_SEMAINE)
        supp += max(Decimal(0), total - HEURES_SEMAINE)
    corrigee = any(p.source == "Correction" and debut.isoformat() <= p.moment[:10] < fin.isoformat()
                   for p in registre.pointages if p.employe == employe.id)
    f = Feuille(employe, debut, jours, normales, supp, anomalies, corrigee)
    approbation = registre.feuilles.get(debut.isoformat(), {}).get(employe.id)
    if approbation and approbation.get("empreinte") == f.empreinte():
        f.etat, f.approuvee_par = approbation["etat"], f"{approbation.get('par', '')} {approbation.get('le', '')}".strip()
    return f


def feuilles(registre: Registre, debut: date, maintenant: datetime | None = None) -> list[Feuille]:
    """Feuilles de la période : employés actifs, et inactifs qui ont pointé pendant la période."""
    fin = (debut + timedelta(days=JOURS_PERIODE)).isoformat()
    ont_pointe = {p.employe for p in registre.valides() if debut.isoformat() <= p.moment[:10] < fin}
    employes = [e for e in registre.employes if e.actif or e.id in ont_pointe]
    return [feuille(registre, e, debut, maintenant) for e in sorted(employes, key=lambda e: e.nom.casefold())]


def approuver(registre: Registre, f: Feuille, par: str) -> None:
    if f.anomalies:
        raise ErreurPointage(f"{f.employe.nom} : corrigez d'abord les anomalies ({len(f.anomalies)}).")
    registre.feuilles.setdefault(f.debut.isoformat(), {})[f.employe.id] = {
        "etat": APPROUVEE, "par": par, "le": _maintenant(), "empreinte": f.empreinte(),
        "normales": str(f.normales), "supplementaires": str(f.supplementaires)}
    registre.enregistrer()
