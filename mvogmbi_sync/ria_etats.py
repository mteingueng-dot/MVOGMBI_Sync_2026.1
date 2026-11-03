"""États de compte RIA (« Account Statement Summary / Detail », AgentBalanceReport.pdf), demande du propriétaire du
2026-10-30 : importés à la main ou relevés dans la boîte de courriel où RIA les envoie ([ria] courriel, page
Courriel, carte « États RIA »).

Le relevé RIA donne, pour la période : le solde précédent, les envois (« MT Send » : montant + frais, au débit de
l'agent), les versements (« MT Payout », au crédit), le solde, le montant à payer, le dernier dépôt de RIA, et la
commission payée le mois précédent / courue ce mois-ci. Chaque ligne du détail est relue et le solde courant est
recalculé (contrôle). La commission payée sert à reconnaître le dépôt de commission dans le relevé Desjardins
(`commissions_reconnues`).

Fichiers : donnees/etats_ria/ (PDF) et donnees/etats_ria/etats.json (états lus, jamais deux fois : empreinte).
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

ZERO = Decimal(0)
DATE = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
NOMBRE = re.compile(r"^-?[\d,]+\.\d{2}$")
# ligne datée du détail : date, activité / réf. / description, puis les montants (au moins deux : mouvement, solde)
LIGNE = re.compile(r"^(\d{1,2}/\d{1,2}/\d{4})\s+(.+?)\s+(-?[\d,]+\.\d{2}(?:\s+-?[\d,]+\.\d{2})+)$")
VERSION_LECTURE = 2  # 2026-11-03 : lignes ACH / Deposit, sous-totaux, « Total Balance » à 2 montants
JOURS_COMMISSION = 12  # le dépôt de la commission arrive quelques jours après la date de paiement indiquée


def _date(texte: str) -> date | None:
    m = DATE.search(texte or "")
    return date(int(m.group(3)), int(m.group(1)), int(m.group(2))) if m else None


def _montant(texte: str) -> Decimal:
    return Decimal(texte.replace(",", ""))


@dataclass
class LigneRia:
    jour: str
    activite: str        # « MT Send » (envoi), « MT Payout » (versement), autre
    reference: str
    description: str
    montant: str
    frais: str = "0"
    commission: str = "0"
    mouvement: str = "0"  # débit (> 0, dû à RIA) ou crédit (< 0, dû par RIA)
    solde: str = "0"


@dataclass
class EtatRia:
    fichier: str
    empreinte: str
    agence: str = ""
    debut: str = ""
    fin: str = ""
    solde_precedent: str = "0"
    debits: str = "0"
    credits: str = "0"
    total: str = "0"
    a_payer: str = "0"
    dernier_depot: str = ""
    montant_dernier_depot: str = "0"
    commission_payee: str = "0"
    mois_commission_payee: str = ""
    date_paiement_commission: str = ""
    commission_courue: str = "0"
    mois_commission_courue: str = ""
    lignes: list[LigneRia] = field(default_factory=list)
    remarques: list[str] = field(default_factory=list)
    importe_le: str = ""
    lecture: int = 0          # version de la lecture : un état lu par une version plus ancienne est relu

    @property
    def cle(self) -> str:
        return f"{self.agence}|{self.debut}|{self.fin}"

    def somme(self, activite: str, champ: str) -> Decimal:
        return sum((Decimal(getattr(l, champ)) for l in self.lignes if l.activite == activite), ZERO)


def _valeur_apres(texte: str, libelle: str) -> str:
    m = re.search(re.escape(libelle) + r"\s*:?\s*(-?[\d,]+\.\d{2})", texte)
    return str(_montant(m.group(1))) if m else "0"


def lire_texte(texte: str, fichier: str = "", empreinte: str = "") -> EtatRia:
    """État RIA d'après le texte du PDF (pdfplumber)."""
    e = EtatRia(fichier, empreinte)
    if "Account Statement" not in texte:
        raise ValueError("Ce PDF n'est pas un état de compte RIA (« Account Statement »).")
    m = re.search(r"\(([A-Z]{2}\d+)\)", texte)
    e.agence = m.group(1) if m else ""
    m = re.search(r"From\s+(\d{1,2}/\d{1,2}/\d{4})\s+To\s+(\d{1,2}/\d{1,2}/\d{4})", texte)
    if m:
        e.debut, e.fin = _date(m.group(1)).isoformat(), _date(m.group(2)).isoformat()
    m = re.search(r"Previous Balance as of\s+(-?[\d,]+\.\d{2})\s+(-?[\d,]+\.\d{2})\s+(-?[\d,]+\.\d{2})", texte)
    e.solde_precedent = str(_montant(m.group(3))) if m else "0"
    m = re.search(r"Total Balance((?:\s+-?[\d,]+\.\d{2}){2,3})", texte)
    if m:  # 3 colonnes (débits, crédits, total) ; 2 quand une colonne est vide : crédits déduits du total
        nombres = [_montant(x) for x in m.group(1).split()]
        if len(nombres) == 3:
            e.debits, e.credits, e.total = (str(x) for x in nombres)
        else:  # une colonne vide : un montant négatif est le total des crédits, sinon celui des débits
            premier, total = nombres
            autre = total - Decimal(e.solde_precedent) - premier
            debits, credits = (autre, premier) if premier < 0 else (premier, autre)
            e.debits, e.credits, e.total = str(debits), str(credits), str(total)
    e.a_payer = _valeur_apres(texte, "Amount to Pay")
    m = re.search(r"Date of Last Deposit:\s*(\d{1,2}/\d{1,2}/\d{4})", texte)
    e.dernier_depot = _date(m.group(1)).isoformat() if m else ""
    e.montant_dernier_depot = _valeur_apres(texte, "Amount of Last Deposit:")
    m = re.search(r"Payment Date\s+(\d{1,2}/\d{1,2}/\d{4})", texte)
    e.date_paiement_commission = _date(m.group(1)).isoformat() if m else ""
    m = re.search(r"Commission paid for\s+([A-Za-z]{3,9} \d{4})\s+(-?[\d,]+\.\d{2})", texte)
    if m:
        e.mois_commission_payee, e.commission_payee = m.group(1), str(_montant(m.group(2)))
    m = re.search(r"Commission accrued for\s+([A-Za-z]{3,9} \d{4})\s+(-?[\d,]+\.\d{2})", texte)
    if m:
        e.mois_commission_courue, e.commission_courue = m.group(1), str(_montant(m.group(2)))
    detail = texte.split("Account Statement Detail", 1)[-1] if "Account Statement Detail" in texte else texte
    vues = set()
    for brute in detail.splitlines():
        brute = " ".join(brute.split())
        if " Total " in f" {brute} " or "Grand" in brute:
            continue
        m = LIGNE.match(brute)
        if not m:
            continue
        nombres = [_montant(x) for x in m.group(3).split()]
        mots = m.group(2).split()
        if len(nombres) < 2 or not mots:
            continue
        # activité : « MT Send », « MT Payout » (deux mots) ou un mot (« ACH » : règlement de RIA, …)
        nb = 2 if mots[0] == "MT" and len(mots) > 1 else 1
        activite, reste = " ".join(mots[:nb]), mots[nb:]
        reference, description = (reste[0], " ".join(reste[1:])) if reste else ("", "")
        if reference.isdigit() and not description:  # sous-total « MT Payout 1 … » (« Total » à la ligne suivante)
            continue
        cle = (m.group(1), activite, reference, tuple(nombres))
        if cle in vues:  # le détail est parfois répété (une page par appareil) : jamais deux fois
            continue
        vues.add(cle)
        montant = nombres[0] if len(nombres) >= 3 else nombres[-2]
        frais = nombres[1] if len(nombres) >= 5 else ZERO
        commission = nombres[2] if len(nombres) >= 5 else nombres[1] if len(nombres) == 4 else ZERO
        e.lignes.append(LigneRia(_date(m.group(1)).isoformat(), activite, reference, description, str(montant),
                                 str(frais), str(commission), str(nombres[-2]), str(nombres[-1])))
    controler(e)
    return e


def controler(e: EtatRia) -> None:
    """Solde courant recalculé ligne par ligne ; total des débits et des crédits contre le résumé."""
    solde = Decimal(e.solde_precedent)
    for l in e.lignes:
        solde += Decimal(l.mouvement)
        if solde != Decimal(l.solde):
            e.remarques.append(f"Solde courant différent le {l.jour} (réf. {l.reference}) : {solde} calculé, "
                               f"{l.solde} sur l'état.")
            solde = Decimal(l.solde)
    debits = sum((Decimal(l.mouvement) for l in e.lignes if Decimal(l.mouvement) > 0), ZERO)
    credits = sum((Decimal(l.mouvement) for l in e.lignes if Decimal(l.mouvement) < 0), ZERO)
    if e.lignes and (debits != Decimal(e.debits) or credits != Decimal(e.credits)):
        e.remarques.append(f"Lignes lues : débits {debits}, crédits {credits} ; résumé de l'état : {e.debits}, "
                           f"{e.credits}.")


def lire_pdf(chemin: Path) -> EtatRia:
    import pdfplumber

    contenu = Path(chemin).read_bytes()
    with pdfplumber.open(chemin) as pdf:
        texte = "\n".join(p.extract_text() or "" for p in pdf.pages)
    e = lire_texte(texte, Path(chemin).name, hashlib.sha256(contenu).hexdigest())
    e.lecture = VERSION_LECTURE
    return e


class Registre:
    def __init__(self, racine: Path):
        self.dossier = Path(racine) / "donnees" / "etats_ria"
        self.chemin = self.dossier / "etats.json"
        self.etats: list[EtatRia] = []
        if self.chemin.exists():
            for d in json.loads(self.chemin.read_text(encoding="utf-8")):
                lignes = [LigneRia(**l) for l in d.pop("lignes", [])]
                self.etats.append(EtatRia(**d, lignes=lignes))
            relus = False
            for rang, e in enumerate(self.etats):  # lu par une version plus ancienne : relu depuis son PDF
                pdf = self.dossier / e.fichier
                if e.lecture < VERSION_LECTURE and pdf.exists():
                    try:
                        neuf = lire_pdf(pdf)
                    except Exception:
                        continue
                    neuf.fichier, neuf.importe_le = e.fichier, e.importe_le
                    self.etats[rang], relus = neuf, True
            if relus:
                self.enregistrer()

    def enregistrer(self) -> None:
        self.dossier.mkdir(parents=True, exist_ok=True)
        provisoire = self.chemin.with_suffix(".tmp")
        provisoire.write_text(json.dumps([asdict(e) for e in self.etats], ensure_ascii=False, indent=1),
                              encoding="utf-8")
        provisoire.replace(self.chemin)

    def importer(self, chemin: Path) -> tuple[EtatRia, bool]:
        """(état, nouveau) : le PDF est copié dans donnees/etats_ria/ ; un même fichier ou une même période d'une
        même agence n'est gardé qu'une fois (la version la plus récente remplace l'ancienne)."""
        import shutil

        e = lire_pdf(chemin)
        if any(x.empreinte == e.empreinte for x in self.etats):
            return next(x for x in self.etats if x.empreinte == e.empreinte), False
        self.dossier.mkdir(parents=True, exist_ok=True)
        cible = self.dossier / f"RIA_{e.agence}_{e.debut}_{e.fin}.pdf"
        if Path(chemin).resolve() != cible.resolve():
            shutil.copyfile(chemin, cible)
        e.fichier, e.importe_le = cible.name, datetime.now().isoformat(timespec="seconds")
        self.etats = [x for x in self.etats if x.cle != e.cle] + [e]
        self.etats.sort(key=lambda x: (x.debut, x.fin), reverse=True)
        return e, True

    def supprimer(self, cle: str) -> None:
        self.etats = [x for x in self.etats if x.cle != cle]


def commissions_reconnues(mouvements, etats: list[EtatRia]) -> list[str]:
    """Clés des dépôts RIA du relevé bancaire égaux à une commission payée d'un état (même montant, dans les
    JOURS_COMMISSION jours qui suivent la date de paiement) : à marquer « Commission » dans la page RIA."""
    trouves = []
    for e in etats:
        montant = Decimal(e.commission_payee)
        if not montant or not e.date_paiement_commission:
            continue
        depuis = date.fromisoformat(e.date_paiement_commission) - timedelta(days=3)
        jusqua = depuis + timedelta(days=3 + JOURS_COMMISSION)
        for m in mouvements:
            if m.montant == montant and depuis <= date.fromisoformat(m.date) <= jusqua and m.cle not in trouves:
                trouves.append(m.cle)
                break
    return trouves


# ----------------------------------------------------------------------------------------- traitement dans Sage
ACTIVITES_COMPTOIR = {"MT Send", "MT Payout", "MT Refund"}  # ACH et Deposit : mouvements de banque (relevé)
JOURS_INTERAC = 3


def operations_des_etats(racine: Path, mouvements_banque=()) -> int:
    """Crée dans le registre RIA (ria.py) une opération par mouvement de comptoir des états importés (demande du
    propriétaire du 2026-11-03 : « les imports de RIA traités dans Sage ») ; jamais deux fois (clé = agence, date,
    réf.). Envoi = espèces reçues pour RIA ; versement ou remboursement = espèces versées par le marché, sauf s'il a
    été payé par virement Interac (même montant au relevé de banque, « Paiement RIA », à JOURS_INTERAC jours) :
    la banque l'a déjà. Renvoie le nombre d'opérations créées."""
    from datetime import date as _date

    from . import ria

    etats = Registre(racine).etats
    registre = ria.Registre(racine)
    connues = {o.cle for o in registre.operations if o.cle}
    interac = [m for m in mouvements_banque if Decimal(m.montant) < 0 and "interac" in m.description.lower()
               and ria.est_ria(m)]
    crees = 0
    for e in etats:
        for l in e.lignes:
            if l.activite not in ACTIVITES_COMPTOIR:
                continue
            cle = f"etat:{e.agence}|{l.jour}|{l.reference}|{l.activite}"
            if cle in connues:
                continue
            montant = abs(Decimal(l.mouvement))
            if l.activite == "MT Send":
                genre = ria.ENVOI
            else:
                jour = _date.fromisoformat(l.jour)
                paye = next((m for m in interac if abs(Decimal(m.montant)) == montant
                             and abs((_date.fromisoformat(m.date) - jour).days) <= JOURS_INTERAC), None)
                if paye is not None:
                    interac.remove(paye)
                    connues.add(cle)
                    continue  # versé par Interac : déjà au relevé de banque
                genre = ria.ESPECES
            registre.ajouter(l.jour, genre, montant, f"{l.activite} {l.reference} {l.description}".strip(), "",
                             "États RIA").cle = cle
            connues.add(cle)
            crees += 1
    if crees or etats:
        registre.comptes.setdefault("mode", "etats")  # le surplus d'un dépôt d'espèces va alors aux espèces
        registre.enregistrer()
    return crees


# ----------------------------------------------------------------------------------------- boîte de courriel
def configuree(config_toml: dict) -> bool:
    r, b = config_toml.get("ria", {}), config_toml.get("boite_paiements", {})
    return bool(r.get("courriel") and (r.get("serveur") or b.get("serveur")))


def recuperer(racine: Path, config_toml: dict) -> list[EtatRia]:
    """États RIA reçus par courriel ([ria] courriel, lecture seule, jamais marqués comme lus) depuis [ria] depuis :
    pièces jointes PDF qui sont des états de compte RIA. Mot de passe : coffre « boite_ria », sinon celui de la boîte
    des avis de paiement si c'est la même adresse."""
    from . import coffre
    from .factures_courriel import Memoire, expediteurs_choisis, lire_boite

    if not configuree(config_toml):
        raise RuntimeError("Courriel de réception des états RIA non configuré (« Administration > Courriel »).")
    r, b = config_toml.get("ria", {}), config_toml.get("boite_paiements", {})
    adresse = str(r["courriel"]).strip()
    meme = adresse.lower() == str(b.get("utilisateur", "")).strip().lower()
    mot_de_passe = coffre.lire(coffre.BOITE_RIA) or (coffre.lire(coffre.BOITE_PAIEMENTS) if meme else "")
    if not mot_de_passe:
        raise RuntimeError("Mot de passe de la boîte des états RIA absent (« Administration > Courriel »).")
    depuis = date.fromisoformat(str(r.get("depuis") or (date.today() - timedelta(days=62)).isoformat()))
    expediteurs = expediteurs_choisis(str(r.get("expediteurs", "")))
    memoire = Memoire(racine)
    memoire.chemin = Path(racine) / "donnees" / "etats_ria" / "courriels_lus.json"
    memoire.prises = json.loads(memoire.chemin.read_text(encoding="utf-8")) if memoire.chemin.exists() else {}
    pieces = lire_boite(str(r.get("serveur") or b.get("serveur")).strip(), adresse, mot_de_passe, depuis, expediteurs,
                        int(r.get("port") or b.get("port", 993)), "INBOX", set(memoire.prises),
                        ["Account Statement", "AgentBalanceReport", "RIA"])
    registre = Registre(racine)
    nouveaux = []
    import tempfile

    for piece in pieces:
        if memoire.deja(piece) or not piece.nom.lower().endswith(".pdf"):
            continue
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as dossier:
            chemin = Path(dossier) / piece.nom
            chemin.write_bytes(piece.contenu)
            try:
                e, nouveau = registre.importer(chemin)
            except ValueError:  # PDF joint qui n'est pas un état RIA
                memoire.noter(piece, "")
                continue
        memoire.noter(piece, e.fichier)
        if nouveau:
            nouveaux.append(e)
    registre.enregistrer()
    memoire.enregistrer()
    return nouveaux
