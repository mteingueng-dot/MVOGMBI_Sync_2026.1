"""Fichier d'import Sage 50 (.IMP) pour la facture de vente.

Format validé par un import réussi dans Sage 50 2026.2 (copie d'essai, facture du 17 oct. 2026) :

    <Version>
    "12001","1"                      version du format (33101 refusée) et pays (1 = Canada)
    </Version>
    <SalInvoice>
    "Vente Hebdomadaire"             ligne client (adresse ignorée si le client existe)
    nb_lignes,"","n° facture","mm-jj-aaaa","0","",total,frais_de_port
                                     n° de facture en 3e champ (en 2e, Sage numérote lui-même)
                                     « 0 » = payer plus tard ; total taxes comprises
    "n° article",quantité,prix,montant[,"TPS/TVH","0","1","5.00",taxe,"TVQ","0","1","9.975",taxe]
                                     taxe : nom, incluse (0/1), remboursable (0/1), taux, montant
    </SalInvoice>

Les lignes Clover reliées au même article Sage sont regroupées (ex. « Igname blanc en spécial »
et « Igname Blanc (YAM) en lb » -> B0000094), en gardant séparées les parties taxées et non taxées.
"""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import openpyxl

from .facture import TAUX_TPS, TAUX_TVQ, Facture

CENT = Decimal("0.01")
TAXES_GQ = (("TPS/TVH", Decimal("5.00"), TAUX_TPS), ("TVQ", Decimal("9.975"), TAUX_TVQ))


@dataclass
class ConfigImport:
    version: str = "12001"  # « 33101 » est refusé par Sage 2026.2 (« Line 2 does not contain a valid version »)
    pays: str = "1"
    position_numero: int = 3  # n° de facture en 3e champ ; en 2e, Sage l'ignore et numérote lui-même
    encodage: str = "cp1252"


@dataclass
class LigneImport:
    numero_sage: str
    quantite: Decimal
    montant: Decimal
    taxable: bool
    noms_clover: list[str] = field(default_factory=list)

    @property
    def prix(self) -> Decimal:
        return (self.montant / self.quantite).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

    def taxes(self) -> list[tuple[str, Decimal, Decimal]]:
        if not self.taxable:
            return []
        return [(nom, taux_affiche, (self.montant * taux).quantize(CENT, rounding=ROUND_HALF_UP))
                for nom, taux_affiche, taux in TAXES_GQ]


@dataclass
class ImportSage:
    facture: Facture
    lignes: list[LigneImport]
    non_reliees: list[str]  # articles Clover sans numéro Sage : non importés

    @property
    def sous_total(self) -> Decimal:
        return sum((l.montant for l in self.lignes), Decimal("0"))

    @property
    def total_taxes(self) -> Decimal:
        return sum((t for l in self.lignes for _, _, t in l.taxes()), Decimal("0"))

    @property
    def total(self) -> Decimal:
        return self.sous_total + self.total_taxes


def cle_nom(nom: str) -> str:
    """Nom Clover comparé sans casse, accents ni espaces multiples."""
    nom = unicodedata.normalize("NFKD", nom).encode("ascii", "ignore").decode().lower()
    return " ".join(nom.split())


@dataclass
class TableCorrespondance:
    par_id: dict[str, str]   # ID Clover -> numéro Sage (prioritaire : l'ID ne change jamais)
    par_nom: dict[str, str]  # nom Clover -> numéro Sage (exports Clover sans ID, articles renommés)

    def numero(self, id_article: str, nom: str) -> str | None:
        return self.par_id.get(id_article) or self.par_nom.get(cle_nom(nom))


def lire_correspondance(chemin: Path) -> TableCorrespondance:
    """Correspondance des lignes « Confirmé » ou « Automatique »."""
    feuille = openpyxl.load_workbook(chemin, read_only=True, data_only=True)["Correspondance"]
    lignes = feuille.iter_rows(values_only=True)
    entete = list(next(lignes))
    i_statut, i_nom, i_num, i_id = (entete.index(n) for n in ("Statut", "Nom Clover", "N° article Sage", "ID Clover"))
    table = TableCorrespondance({}, {})
    for r in lignes:
        statut = str(r[i_statut] or "").strip().lower()
        if statut in ("confirmé", "confirme", "ok", "oui", "automatique") and r[i_num]:
            numero = str(r[i_num]).strip()
            if r[i_id]:
                table.par_id[str(r[i_id])] = numero
            table.par_nom.setdefault(cle_nom(str(r[i_nom] or "")), numero)
    return table


def preparer_import(facture: Facture, correspondance: TableCorrespondance) -> ImportSage:
    regroupees: dict[tuple[str, bool], LigneImport] = {}
    non_reliees = []
    for ligne in facture.lignes:
        numero = correspondance.numero(ligne.id_article, ligne.nom)
        if not numero:
            non_reliees.append(f"{ligne.nom} ({ligne.quantite} x, {ligne.montant} $)")
            continue
        cle = (numero, bool(ligne.code_taxe))
        if cle not in regroupees:
            regroupees[cle] = LigneImport(numero, Decimal("0"), Decimal("0"), bool(ligne.code_taxe))
        regroupees[cle].quantite += ligne.quantite
        regroupees[cle].montant += ligne.montant
        regroupees[cle].noms_clover.append(ligne.nom)
    lignes = [l for l in regroupees.values() if l.quantite != 0]
    lignes.sort(key=lambda l: -l.montant)
    return ImportSage(facture, lignes, non_reliees)


def _texte(valeur: str) -> str:
    return '"' + str(valeur).replace('"', "'") + '"'


def _nombre(valeur: Decimal, decimales: int) -> str:
    return f'"{valeur.quantize(Decimal(1).scaleb(-decimales), rounding=ROUND_HALF_UP)}"'


def _bloc_facture(imp: ImportSage, config: ConfigImport) -> list[str]:
    f = imp.facture
    numero_facture, numero_commande = (f.numero, "") if config.position_numero == 2 else ("", f.numero)
    lignes = [
        "<SalInvoice>",
        _texte(f.client),
        ",".join([
            f'"{len(imp.lignes)}"', _texte(numero_facture), _texte(numero_commande),
            _texte(f.date_facture.strftime("%m-%d-%Y")), '"0"', '""', _nombre(imp.total, 2), '"0.00"',
        ]),
    ]
    for l in imp.lignes:
        champs = [_texte(l.numero_sage), _nombre(l.quantite, 4), _nombre(l.prix, 4), _nombre(l.montant, 2)]
        for nom, taux, montant in l.taxes():
            champs += [_texte(nom), '"0"', '"1"', f'"{taux}"', _nombre(montant, 2)]
        lignes.append(",".join(champs))
    return lignes + ["</SalInvoice>"]


def ecrire_imp(imps: ImportSage | list[ImportSage], chemin: Path, config: ConfigImport | None = None) -> Path:
    """Écrit une ou plusieurs factures dans un même fichier .IMP (un seul import dans Sage)."""
    config = config or ConfigImport()
    imps = [imps] if isinstance(imps, ImportSage) else imps
    lignes = ["<Version>", f'{_texte(config.version)},{_texte(config.pays)}', "</Version>", ""]
    for imp in imps:
        lignes += _bloc_facture(imp, config)
    lignes.append("")
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text("\r\n".join(lignes), encoding=config.encodage, errors="replace", newline="")
    return chemin


def nom_fichier(numero_facture: str) -> str:
    return re.sub(r"[^\w-]+", "_", numero_facture).strip("_") + ".IMP"
