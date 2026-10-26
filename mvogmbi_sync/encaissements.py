"""Encaissements des dépôts Clover sur les factures journalières « Vente AAAA-MM-JJ ».

Règles du propriétaire :
- le dépôt Clover dans le compte Desjardins = ventes encaissées moins les espèces, c'est-à-dire le lot
  de cartes que Clover ferme chaque soir (vérifié au cent près : 2026-05-20, 2 740,59 $ - 179,78 $
  d'espèces = lot de 2 560,81 $) ;
- ventes du lundi au jeudi : déposées le lendemain ; ventes du vendredi, samedi et dimanche : déposées
  ensemble le lundi suivant ;
- l'encaissement est enregistré dans Sage à la date du dépôt, au compte Desjardins (1055), et appliqué
  sur la facture de chaque jour de vente pour le montant de son lot.

Sage n'accepte pas d'importer un encaissement (Sage_SA_import.exe ne lit que factures, commandes, achats
et écritures de journal) : l'application calcule les encaissements et vérifie dans Sage s'ils sont saisis.
Dans Sage, un encaissement est une ligne tcustrdt de type 1 (montant négatif, compte de banque lBnkAcctId)
rattachée à la facture (lCusTrId).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from .periodes import en_millisecondes

CENT = Decimal("0.01")

# États d'un encaissement
APPLIQUE = "Appliqué"
A_SAISIR = "À saisir dans Sage"
ECART = "Montant différent dans Sage"
SANS_FACTURE = "Facture pas encore dans Sage"
A_VENIR = "Dépôt à venir"


def date_depot(jour_vente: date) -> date:
    """Lundi à jeudi : le lendemain ; vendredi, samedi, dimanche : le lundi suivant."""
    if jour_vente.weekday() <= 3:
        return jour_vente + timedelta(days=1)
    return jour_vente + timedelta(days=7 - jour_vente.weekday())


def numero_facture(jour_vente: date) -> str:
    return f"Vente {jour_vente.isoformat()}"


def numero_compte_sage(compte: str | int) -> int:
    """« 1055 » -> 10550000 (comptes stockés sur 8 chiffres dans la base Sage)."""
    texte = str(compte).strip()
    return int(texte.ljust(8, "0")) if len(texte) < 8 else int(texte)


@dataclass
class LigneEncaissement:
    jour_vente: date
    montant: Decimal                     # lot(s) de cartes Clover des jours de la facture = part du dépôt
    numero: str = ""                     # n° de facture s'il diffère de « Vente AAAA-MM-JJ » (fin de semaine)
    facture_presente: bool = False
    montant_du: Decimal | None = None    # solde de la facture dans Sage
    deja_encaisse: Decimal = Decimal(0)  # encaissements déjà saisis au compte de dépôt à la date du dépôt
    etat: str = ""

    @property
    def facture(self) -> str:
        return self.numero or numero_facture(self.jour_vente)


@dataclass
class Depot:
    date: date
    lignes: list[LigneEncaissement] = field(default_factory=list)
    etat: str = ""

    @property
    def montant(self) -> Decimal:
        return sum((l.montant for l in self.lignes), Decimal(0))


def lots_par_jour(client, debut: date, fin: date) -> dict[date, Decimal]:
    """Total des lots de cartes Clover fermés chaque jour (ventes - remboursements, hors espèces)."""
    fuseau = ZoneInfo(client.config.fuseau_horaire)
    t0, t1 = en_millisecondes(debut, fin, client.config.fuseau_horaire)
    totaux: dict[date, Decimal] = defaultdict(Decimal)
    for lot in client._pages("batches", {"filter": [f"createdTime>={t0}", f"createdTime<{t1}"]}):
        jour = datetime.fromtimestamp(lot["createdTime"] / 1000, fuseau).date()
        totaux[jour] += Decimal(int(lot.get("totalBatchAmount") or 0)) / 100
    return dict(totaux)


def regrouper(lots: dict[date, Decimal]) -> list[Depot]:
    """Dépôts (date de dépôt -> jours de vente) à partir des lots de chaque jour."""
    depots: dict[date, Depot] = {}
    for jour in sorted(lots):
        if lots[jour] == 0:
            continue
        d = date_depot(jour)
        depots.setdefault(d, Depot(d)).lignes.append(LigneEncaissement(jour, lots[jour]))
    return [depots[d] for d in sorted(depots)]


def factures_fin_de_semaine(depots: list[Depot], factures_sage: set[str]) -> None:
    """Regroupe les lignes vendredi-samedi-dimanche d'un dépôt du lundi sur une seule facture « Vente AAAA-MM-JJ/JJ ».

    Règle du propriétaire depuis octobre 2026 : une seule facture pour la fin de semaine. Les anciennes fins de
    semaine facturées jour par jour restent encaissées facture par facture.
    """
    from .facture import numero_fin_de_semaine

    for depot in depots:
        fds = [l for l in depot.lignes if l.jour_vente.weekday() >= 4]
        if len(fds) < 1 or any(numero_facture(l.jour_vente) in factures_sage for l in fds):
            continue
        vendredi = depot.date - timedelta(days=3)
        numero = numero_fin_de_semaine(vendredi, vendredi + timedelta(days=2))
        if fds[0].jour_vente != vendredi and numero not in factures_sage:
            continue
        reste = [l for l in depot.lignes if l not in fds]
        depot.lignes = reste + [LigneEncaissement(fds[0].jour_vente, sum((l.montant for l in fds), Decimal(0)), numero)]


def noms_factures_sage(base, client_sage: str) -> set[str]:
    return {l["s"] for l in base.requete(
        "SELECT TRIM(t.sSource) s FROM tcustr t JOIN tcustomr c ON c.lId = t.lCusId "
        "WHERE c.sName = %s AND t.sSource LIKE 'Vente %%'", (client_sage,))}


def etat_factures_sage(base, client_sage: str, compte_depot: int, factures: list[str]) -> dict[str, dict]:
    """Pour chaque facture : solde dû et encaissements au compte de dépôt, par date."""
    if not factures:
        return {}
    marques = ",".join(["%s"] * len(factures))
    lignes = base.requete(
        "SELECT t.sSource facture, d.nTranType type, d.dtDate date, d.dAmount montant, d.lBnkAcctId banque "
        "FROM tcustr t JOIN tcustomr c ON c.lId = t.lCusId JOIN tcustrdt d ON d.lCusTrId = t.lId "
        f"WHERE c.sName = %s AND t.sSource IN ({marques})", (client_sage, *factures))
    etat: dict[str, dict] = {}
    for l in lignes:
        e = etat.setdefault(l["facture"], {"du": Decimal(0), "encaisse": defaultdict(Decimal)})
        montant = Decimal(str(l["montant"])).quantize(CENT)
        e["du"] += montant
        if l["type"] == 1 and int(l["banque"] or 0) == compte_depot:
            e["encaisse"][l["date"].date() if hasattr(l["date"], "date") else l["date"]] -= montant
    return etat


def evaluer(depots: list[Depot], etat_sage: dict[str, dict], aujourdhui: date) -> None:
    """Fixe l'état de chaque ligne et de chaque dépôt d'après Sage."""
    for depot in depots:
        for l in depot.lignes:
            e = etat_sage.get(l.facture)
            l.facture_presente = e is not None
            if e is None:
                l.etat = SANS_FACTURE
                continue
            l.montant_du = e["du"]
            l.deja_encaisse = e["encaisse"].get(depot.date, Decimal(0))
            if l.deja_encaisse == l.montant:
                l.etat = APPLIQUE
            elif l.deja_encaisse:
                l.etat = ECART
            elif depot.date > aujourdhui:
                l.etat = A_VENIR
            else:
                l.etat = A_SAISIR
        etats = {l.etat for l in depot.lignes}
        for possible in (ECART, SANS_FACTURE, A_SAISIR, A_VENIR, APPLIQUE):
            if possible in etats:
                depot.etat = possible
                break


def calculer(client, base, client_sage: str, compte_depot: int, debut: date, fin: date,
             aujourdhui: date | None = None) -> list[Depot]:
    """Dépôts des ventes du `debut` au `fin` inclus, avec leur état dans Sage."""
    depots = regrouper(lots_par_jour(client, debut, fin))
    if base:
        factures_fin_de_semaine(depots, noms_factures_sage(base, client_sage))
    factures = [l.facture for d in depots for l in d.lignes]
    evaluer(depots, etat_factures_sage(base, client_sage, compte_depot, factures) if base else {},
            aujourdhui or date.today())
    return depots


def ecrire_excel(depots: list[Depot], chemin, compte_depot: str) -> None:
    """Liste des encaissements : une ligne par facture, regroupées par dépôt."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill

    classeur = Workbook()
    feuille = classeur.active
    feuille.title = "Encaissements"
    feuille.append(["Date du dépôt", "Compte de dépôt", "Facture", "Montant à encaisser", "Montant dû (Sage)", "État"])
    for cellule in feuille[1]:
        cellule.font = Font(bold=True, color="FFFFFF")
        cellule.fill = PatternFill("solid", fgColor="1A9B3C")
    for d in depots:
        for l in d.lignes:
            feuille.append([d.date, compte_depot, l.facture, float(l.montant),
                            float(l.montant_du) if l.montant_du is not None else None, l.etat])
        feuille.append([d.date, compte_depot, "Total du dépôt", float(d.montant), None, d.etat])
        for cellule in feuille[feuille.max_row]:
            cellule.font = Font(bold=True)
    for colonne, largeur in zip("ABCDEF", (14, 16, 20, 20, 18, 30)):
        feuille.column_dimensions[colonne].width = largeur
    for ligne in feuille.iter_rows(min_row=2):
        ligne[0].number_format = "yyyy-mm-dd"
        ligne[3].number_format = ligne[4].number_format = "# ##0.00 $"
    classeur.save(chemin)
