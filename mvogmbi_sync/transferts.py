"""Transferts de marchandises entre points de vente (demande du propriétaire du 2026-10-28).

Un point de vente = un marchand Clover + un dépôt (emplacement d'inventaire) Sage. Un transfert déplace des articles
du point de vente A vers le point de vente B :
- Sage : « Transfert entre Emplacements » du dépôt de A vers celui de B (même valeur, sans vente ni écriture de
  résultat), source = n° du transfert (« TR-0001 ») ; voir robot_transferts.py ;
- Clover : stock de l'article de A diminué, stock de l'article de B augmenté (articles trouvés par la correspondance
  de chaque point de vente : n° Sage -> ID Clover, lignes « Confirmé » ou « Automatique »).
Sage d'abord (vérifié dans la base), Clover ensuite ; chaque ligne Clover faite est notée dans le transfert : une
reprise ne la refait jamais. Registre : donnees/transferts.json.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from .cache_lectures import vide_apres

FICHIER = "transferts.json"
BROUILLON, SAGE_FAIT, TERMINE, A_COMPLETER = "Brouillon", "Fait dans Sage", "Terminé", "À compléter"


@dataclass
class LigneTransfert:
    numero: str          # n° d'article Sage
    description: str
    quantite: Decimal


@dataclass
class Transfert:
    numero: str          # « TR-0001 »
    jour: str            # AAAA-MM-JJ
    de: str              # code du point de vente de départ
    vers: str            # code du point de vente d'arrivée
    lignes: list[LigneTransfert] = field(default_factory=list)
    note: str = ""
    etat: str = BROUILLON
    sage: bool = False
    clover: dict[str, dict] = field(default_factory=dict)  # « code|n° Sage » -> {id, avant, apres}
    messages: list[str] = field(default_factory=list)
    cree: str = ""

    @property
    def total_quantite(self) -> Decimal:
        return sum((l.quantite for l in self.lignes), Decimal(0))

    def problemes(self, points: dict) -> list[str]:
        """`points` : code -> PointDeVente."""
        p = []
        if self.de not in points or self.vers not in points:
            p.append("point de vente de départ ou d'arrivée inconnu")
        elif self.de == self.vers:
            p.append("le point de vente d'arrivée doit être différent du départ")
        elif points[self.de].depot_sage.strip().lower() == points[self.vers].depot_sage.strip().lower():
            p.append("les deux points de vente ont le même dépôt Sage")
        if not self.lignes:
            p.append("aucun article")
        for l in self.lignes:
            if not l.numero:
                p.append("article sans n° Sage")
            if l.quantite <= 0:
                p.append(f"{l.numero} : quantité à transférer > 0")
        try:
            date.fromisoformat(self.jour)
        except ValueError:
            p.append("date invalide (AAAA-MM-JJ)")
        return p


def _transfert(d: dict) -> Transfert:
    lignes = [LigneTransfert(l["numero"], l.get("description", ""), Decimal(str(l["quantite"]))) for l in d["lignes"]]
    return Transfert(**{**d, "lignes": lignes})


class Registre:
    def __init__(self, racine: Path):
        self.chemin = Path(racine) / "donnees" / FICHIER
        self.transferts: list[Transfert] = []
        if self.chemin.exists():
            self.transferts = [_transfert(d) for d in json.loads(self.chemin.read_text(encoding="utf-8"))]

    def nouveau_numero(self) -> str:
        n = max((int(t.numero.split("-")[-1]) for t in self.transferts if t.numero.split("-")[-1].isdigit()),
                default=0)
        return f"TR-{n + 1:04d}"

    def trouver(self, numero: str) -> Transfert | None:
        return next((t for t in self.transferts if t.numero == numero), None)

    def garder(self, t: Transfert) -> None:
        if not t.cree:
            t.cree = datetime.now().isoformat(timespec="seconds")
        self.transferts = [x for x in self.transferts if x.numero != t.numero] + [t]
        self.enregistrer()

    def supprimer(self, numero: str) -> None:
        t = self.trouver(numero)
        if t and (t.sage or t.clover):
            raise ValueError("Transfert déjà commencé (Sage ou Clover) : il ne peut plus être supprimé.")
        self.transferts = [x for x in self.transferts if x.numero != numero]
        self.enregistrer()

    def enregistrer(self) -> None:
        self.chemin.parent.mkdir(parents=True, exist_ok=True)
        donnees = [{**asdict(t), "lignes": [{**asdict(l), "quantite": str(l.quantite)} for l in t.lignes]}
                   for t in sorted(self.transferts, key=lambda x: x.numero)]
        provisoire = self.chemin.with_suffix(".tmp")
        provisoire.write_text(json.dumps(donnees, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
        provisoire.replace(self.chemin)


def liens_clover(chemin_correspondance: Path) -> dict[str, list[str]]:
    """N° Sage -> ID Clover des articles reliés (« Confirmé » ou « Automatique ») d'un point de vente."""
    from .correspondance import AUTOMATIQUE, CONFIRME, lire_correspondances

    if not Path(chemin_correspondance).exists():
        return {}
    liens: dict[str, list[str]] = {}
    for c in lire_correspondances(Path(chemin_correspondance)):
        if c.statut in (CONFIRME, AUTOMATIQUE) and c.numero_sage and c.id_clover:
            liens.setdefault(" ".join(c.numero_sage.split()), []).append(c.id_clover)
    return liens


def appliquer_clover(t: Transfert, clients: dict, liens: dict[str, dict[str, list[str]]]) -> list[str]:
    """Stock Clover : départ − quantité, arrivée + quantité. `clients` : code -> ClientClover ; `liens` : code ->
    (n° Sage -> ID Clover). Renvoie les messages ; une ligne déjà faite n'est jamais refaite."""
    messages = []
    for code, signe in ((t.de, -1), (t.vers, 1)):
        for l in t.lignes:
            cle = f"{code}|{l.numero}"
            if cle in t.clover:
                continue
            ids = liens.get(code, {}).get(l.numero, [])
            if len(ids) != 1:
                messages.append(f"Clover {code} : {l.numero} {'non relié' if not ids else 'relié à plusieurs articles'}"
                                " — stock à corriger à la main")
                continue
            try:
                avant = clients[code].stock(ids[0])
                apres = avant + signe * l.quantite
                clients[code].regler_stock(ids[0], apres)
                t.clover[cle] = {"id": ids[0], "avant": str(avant), "apres": str(apres)}
            except Exception as exc:
                messages.append(f"Clover {code} : {l.numero} — {exc}")
    return messages


def faits_clover(t: Transfert) -> bool:
    return all(f"{code}|{l.numero}" in t.clover for code in (t.de, t.vers) for l in t.lignes)


@vide_apres  # mémoire des lectures vidée après une écriture
def transferer(racine: Path, config_toml: dict, numero: str, journal=print) -> Transfert:
    """Sage puis Clover ; état et messages enregistrés dans le registre."""
    from .__main__ import charger_config
    from .api_clover import ClientClover
    from .points_vente import points_de_vente

    racine = Path(racine)
    registre = Registre(racine)
    t = registre.trouver(numero)
    if t is None:
        raise ValueError(f"Transfert {numero} introuvable.")
    points = {p.code: p for p in points_de_vente(config_toml)}
    problemes = t.problemes(points)
    if problemes:
        raise ValueError(" ; ".join(problemes))
    t.messages = []
    de, vers = points[t.de], points[t.vers]
    if not t.sage:
        resultats = transferer_dans_sage(racine, config_toml, t.numero, de.depot_sage, vers.depot_sage,
                                         [(l.numero, l.quantite) for l in t.lignes], t.jour,
                                         f"{t.numero} {de.nom} -> {vers.nom}"[:60])
        t.sage = bool(resultats) and all(r["fait"] for r in resultats)
        t.messages += [m for r in resultats for m in r["messages"] if m and "date antérieure" not in m]
        if not t.sage:
            t.etat = A_COMPLETER
            registre.garder(t)
            return t
    t.etat = SAGE_FAIT
    registre.garder(t)
    try:
        clients = {p.code: ClientClover(charger_config(racine / "config.toml", p)) for p in (de, vers)}
    except SystemExit as exc:  # identifiant marchand ou jeton absent : message clair, Sage déjà fait
        t.messages.append(f"Clover : {exc}")
        t.etat = A_COMPLETER
        registre.garder(t)
        return t
    liens = {p.code: liens_clover(p.fichier(racine / "donnees", "correspondance_articles.xlsx")) for p in (de, vers)}
    t.messages += appliquer_clover(t, clients, liens)
    t.etat = TERMINE if faits_clover(t) else A_COMPLETER
    registre.garder(t)
    journal(f"{t.numero} : {t.etat}")
    return t


def transferer_dans_sage(racine: Path, config_toml: dict, reference: str, de: str, vers: str, lignes, jour: str,
                         remarque: str) -> list[dict]:
    """Sage ouvert sur le fichier configuré : directement ; sinon l'application ouvre Sage elle-même (commande
    interne `transfert-bureau`). Renvoie [{source, fait, messages}]."""
    import tempfile

    from .__main__ import commande_moteur
    from .robot_articles import fenetre_principale_ouverte
    from .robot_transferts import transferer as robot
    from .sage_bureau import executer_sur_bureau_cache, sage_ouvert

    fichier = config_toml.get("sage_import", {}).get("fichier_entreprise")
    if fenetre_principale_ouverte(fichier):
        return [asdict(l) | {"lignes": [(n, str(q)) for n, q in l.lignes]}
                for l in robot(config_toml, reference, de, vers, lignes, jour, remarque)]
    if sage_ouvert():
        raise RuntimeError("Sage est ouvert sur un autre fichier d'entreprise : fermez-le, l'application l'ouvrira "
                           "elle-même.")
    with tempfile.TemporaryDirectory() as dossier:
        demande, bilan = Path(dossier) / "transfert.json", Path(dossier) / "bilan.json"
        demande.write_text(json.dumps({"reference": reference, "de": de, "vers": vers, "jour": jour,
                                       "remarque": remarque, "lignes": [(n, str(q)) for n, q in lignes]},
                                      ensure_ascii=False), encoding="utf-8")
        executer_sur_bureau_cache(commande_moteur() + ["transfert-bureau", "--demande", str(demande),
                                                      "--resultat", str(bilan)], racine)
        resultat = json.loads(bilan.read_text(encoding="utf-8")) if bilan.exists() else {}
    if resultat.get("erreur"):
        raise RuntimeError(resultat["erreur"])
    return resultat.get("resultats", [])


def stocks_par_depot(base, numeros: list[str]) -> dict[str, dict[str, Decimal]]:
    """N° Sage -> {dépôt : quantité} (tinvbyln par emplacement)."""
    if not numeros:
        return {}
    marques = ", ".join(["%s"] * len(numeros))
    resultat: dict[str, dict[str, Decimal]] = {}
    for r in base.requete(
            "SELECT TRIM(i.sPartCode) n, TRIM(l.sGrpCode) d, y.dInStock q FROM tinvbyln y "
            "JOIN tinvent i ON i.lId = y.lInventId JOIN tinvloc l ON l.lId = y.lInvLocId "
            f"WHERE i.sPartCode IN ({marques})", tuple(numeros)):
        resultat.setdefault(r["n"], {})[r["d"]] = Decimal(str(r["q"] or 0)).quantize(Decimal("0.001"))
    return resultat


def depots_sage(base) -> list[str]:
    return [r["d"] for r in base.requete("SELECT TRIM(sGrpCode) d FROM tinvloc WHERE bActive = 1 ORDER BY lId")]
