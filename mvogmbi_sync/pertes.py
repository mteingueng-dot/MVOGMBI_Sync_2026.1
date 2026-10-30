"""Pertes et démarque (demande du propriétaire du 2026-10-29, priorité n° 3) : déclaration au magasin des produits
périmés, abîmés, disparus, donnés ou consommés, valorisés au coût, sortis du stock dans Clover et dans Sage, et
rapport des pertes par motif, catégorie, article ou mois, en pourcentage des ventes.

Une déclaration « PE-0001 » (une ou plusieurs lignes, un motif, un dépôt) :
- Clover : stock de chaque article diminué de la quantité (stock relu juste avant ; une ligne déjà faite n'est jamais
  refaite) ;
- Sage : document de stock « Sortie » (documents.py, « DS-… », dépôt du point de vente) pour les articles reliés,
  passé dans Sage avec « Passer dans Sage » comme tout document de stock ;
- coût d'une ligne : CUMP de Sage (couts_sage), sinon coût Clover, sinon inconnu (valeur 0, signalé).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from .cache_lectures import vide_apres

CENT = Decimal("0.01")
ZERO = Decimal(0)
MOTIFS = ["Périmé", "Abîmé ou cassé", "Vol ou disparition", "Don", "Consommation interne", "Erreur de réception",
          "Autre"]
REGROUPEMENTS = {"Motif": "motif", "Catégorie": "categorie", "Article": "nom", "Mois": "mois"}
ENTETES_RAPPORT = ["Regroupement", "Déclarations", "Quantité", "Valeur au coût", "Part des pertes"]


@dataclass
class LignePerte:
    id_clover: str
    nom: str
    quantite: str
    cout: str = "0"
    numero_sage: str = ""
    categorie: str = ""
    source_cout: str = ""      # « CUMP Sage », « Coût Clover », « Coût inconnu »
    clover_fait: bool = False

    @property
    def valeur(self) -> Decimal:
        return (Decimal(self.quantite) * Decimal(self.cout or 0)).quantize(CENT)


@dataclass
class Perte:
    numero: str
    jour: str
    motif: str
    lignes: list[LignePerte] = field(default_factory=list)
    depot: str = ""
    auteur: str = ""
    remarque: str = ""
    document: str = ""         # document de stock Sage (DS-…)
    point_vente: str = ""      # code du point de vente (n° 1 si vide) : son Clover et son dépôt Sage
    messages: list[str] = field(default_factory=list)
    cree: str = ""

    @property
    def valeur(self) -> Decimal:
        return sum((l.valeur for l in self.lignes), ZERO)


def ligne(article: dict, quantite: Decimal, liens: dict[str, str], couts: dict) -> LignePerte:
    """Ligne de perte d'un article du catalogue Clover, au CUMP de Sage si l'article est relié."""
    numero = liens.get(article.get("id", ""), "")
    cump = couts[numero].cump if numero in couts else None
    cout_clover = Decimal(article.get("cost") or 0) / 100
    if cump:
        cout, source = cump, "CUMP Sage"
    elif cout_clover > 0:
        cout, source = cout_clover, "Coût Clover"
    else:
        cout, source = ZERO, "Coût inconnu"
    categories = (article.get("categories") or {}).get("elements") or []
    return LignePerte(article.get("id", ""), article.get("name", ""), str(quantite), str(Decimal(cout).quantize(
        Decimal("0.0001"))), numero, categories[0].get("name", "") if categories else "", source)


class Registre:
    def __init__(self, racine: Path):
        self.racine = Path(racine)
        self.chemin = self.racine / "donnees" / "pertes.json"
        donnees = json.loads(self.chemin.read_text(encoding="utf-8")) if self.chemin.exists() else []
        self.pertes = [Perte(**{**p, "lignes": [LignePerte(**l) for l in p.get("lignes", [])]}) for p in donnees]

    def enregistrer(self) -> None:
        self.chemin.parent.mkdir(parents=True, exist_ok=True)
        provisoire = self.chemin.with_suffix(".tmp")
        provisoire.write_text(json.dumps([asdict(p) for p in self.pertes], ensure_ascii=False, indent=1),
                              encoding="utf-8")
        provisoire.replace(self.chemin)

    def prochain_numero(self) -> str:
        n = max((int(p.numero.split("-")[1]) for p in self.pertes if p.numero.startswith("PE-")), default=0)
        return f"PE-{n + 1:04d}"

    def perte(self, numero: str) -> Perte:
        return next(p for p in self.pertes if p.numero == numero)


def nouvelle(registre: Registre, jour: str, motif: str, lignes: list[LignePerte], depot: str = "", auteur: str = "",
             remarque: str = "", point_vente: str = "") -> Perte:
    if not lignes:
        raise ValueError("Ajoutez au moins un article.")
    if motif not in MOTIFS:
        raise ValueError("Choisissez le motif de la perte.")
    for l in lignes:
        if Decimal(l.quantite) <= 0:
            raise ValueError(f"{l.nom} : la quantité doit être positive.")
    date.fromisoformat(jour)
    p = Perte(registre.prochain_numero(), jour, motif, lignes, depot, auteur, remarque,
              cree=datetime.now().isoformat(timespec="seconds"), point_vente=point_vente)
    registre.pertes.append(p)
    registre.enregistrer()
    return p


@vide_apres  # mémoire des lectures vidée après une écriture
def appliquer(racine: Path, config_toml: dict, numero: str, client=None) -> Perte:
    """Sort la perte du stock : document de stock Sage (une fois) puis stock Clover ligne par ligne (une fois)."""
    from . import documents as dc

    registre = Registre(racine)
    p = registre.perte(numero)
    reliees = [l for l in p.lignes if l.numero_sage]
    if reliees and not p.document:
        doc = dc.Registre(racine).ajouter(
            dc.STOCK, "", p.jour, [dc.LigneDocument(l.numero_sage, l.nom, l.quantite, l.cout) for l in reliees],
            f"Perte {p.numero} — {p.motif}"[:60], dc.SORTIE, p.auteur, p.depot)
        p.document = doc.numero
        p.messages.append(f"Document de stock {doc.numero} créé : « Passer dans Sage » depuis la liste des documents "
                          "de stock.")
    sans_lien = [l.nom for l in p.lignes if not l.numero_sage]
    if sans_lien:
        p.messages.append("Sans article Sage relié (Clover seulement) : " + ", ".join(sans_lien))
    registre.enregistrer()
    if client is None:
        from .points_vente import client as client_de, point_de_vente

        client = client_de(racine, point_de_vente(config_toml, p.point_vente or None))
    for l in p.lignes:
        if l.clover_fait or not l.id_clover:
            continue
        try:
            stock = client.stock(l.id_clover)
            client.regler_stock(l.id_clover, stock - Decimal(l.quantite))
            l.clover_fait = True
            p.messages.append(f"Clover : {l.nom} {stock} -> {stock - Decimal(l.quantite)}")
        except Exception as exc:
            p.messages.append(f"Clover : {l.nom} non mis à jour ({exc})")
        registre.enregistrer()  # après chaque ligne : une reprise ne compte jamais deux fois
    return p


# --------------------------------------------------------------------------------------------- rapport
def rapport(pertes: list[Perte], debut: date, fin: date, regroupement: str = "motif") -> tuple[list[list], Decimal]:
    """Lignes [regroupement, déclarations, quantité, valeur, part] triées par valeur, et la valeur totale."""
    groupes: dict[str, list] = {}
    for p in pertes:
        if not debut.isoformat() <= p.jour <= fin.isoformat():
            continue
        for l in p.lignes:
            cle = {"motif": p.motif, "categorie": l.categorie or "Sans catégorie", "nom": l.nom,
                   "mois": p.jour[:7]}[regroupement]
            g = groupes.setdefault(cle, [set(), ZERO, ZERO])
            g[0].add(p.numero)
            g[1] += Decimal(l.quantite)
            g[2] += l.valeur
    total = sum((g[2] for g in groupes.values()), ZERO)
    lignes = [[cle, len(g[0]), g[1], g[2], f"{(g[2] / total * 100 if total else ZERO):.1f} %".replace(".", ",")]
              for cle, g in sorted(groupes.items(), key=lambda x: -x[1][2])]
    return lignes, total


def taux(valeur: Decimal, ventes_nettes: Decimal) -> str:
    """Pertes au coût en % des ventes nettes de la période (repère d'un marché d'alimentation : 2 à 4 %)."""
    if not ventes_nettes:
        return "—"
    return f"{valeur / ventes_nettes * 100:.2f} %".replace(".", ",")
