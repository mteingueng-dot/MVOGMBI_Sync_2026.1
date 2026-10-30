"""Création d'un article à la fois dans Clover et dans Sage, depuis l'application (demande du propriétaire du 2026-10-28).

Clover : nom, prix = prix d'achat + 40 % (modifiable), type de prix, aucune couleur, taxes, aucun groupe de
modificateurs, catégorie, coût = prix d'achat, code du produit (facultatif), UGS = date de péremption (obligatoire,
JJ/MM/AAAA comme les articles existants), stock.
Sage : numéro = préfixe de la catégorie + numéro suivant libre (« C0001160 »), description, comptes d'actif, de
produits, de CMV et d'écart pris dans la table « catégorie Clover -> comptes Sage » (`donnees/categories_comptes.json`),
proposée à partir des articles déjà reliés (règle 15xx -> 40xx / 50xx).
L'article créé est relié dans la correspondance (« Confirmé ») ; chaque création est notée dans
`donnees/journal_articles_crees.csv`.
"""

from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from .cache_lectures import vide_apres

MARGE = Decimal("0.40")  # prix de vente = prix d'achat + 40 %
CENT = Decimal("100")
PREFIXE_DEFAUT = "C"
LARGEUR_DEFAUT = 7  # « C0001159 »
TYPES_PRIX = {"FIXED": "Fixe", "VARIABLE": "Variable", "PER_UNIT": "Par unité"}
TAXES_DEFAUT = "Taxes par défaut de Clover"
AUCUNE_TAXE = "Aucune taxe"
METHODE = "Créé par l'application"


# ----------------------------------------------------------------------------- table catégorie -> comptes Sage
@dataclass
class ComptesCategorie:
    categorie: str
    prefixe: str = PREFIXE_DEFAUT
    actif: str = ""
    produits: str = ""
    cmv: str = ""
    ecart: str = ""  # règle du propriétaire du 2026-10-28 : écart = CMV (rempli d'office s'il est vide)

    def __post_init__(self) -> None:
        if not (self.ecart or "").strip():
            self.ecart = self.cmv

    def problemes(self) -> list[str]:
        p = []
        for nom, compte, debut in (("actif", self.actif, "15"), ("produits", self.produits, "40"), ("CMV", self.cmv, "50")):
            if not re.fullmatch(r"\d{4}", compte or ""):
                p.append(f"compte {nom} manquant")
            elif not compte.startswith(debut):
                p.append(f"compte {nom} {compte} : un {debut}xx est attendu")
        if self.ecart and not re.fullmatch(r"\d{4}", self.ecart):
            p.append("compte d'écart invalide")
        if not re.fullmatch(r"[A-Za-z0-9]{0,5}", self.prefixe or ""):
            p.append("préfixe : lettres ou chiffres, 5 au plus")
        return p


class TableCategories:
    def __init__(self, racine: Path):
        self.chemin = Path(racine) / "donnees" / "categories_comptes.json"
        self.lignes: dict[str, ComptesCategorie] = {}
        if self.chemin.exists():
            for d in json.loads(self.chemin.read_text(encoding="utf-8")):
                self.lignes[d["categorie"]] = ComptesCategorie(**d)

    def pour(self, categorie: str) -> ComptesCategorie | None:
        return self.lignes.get(categorie)

    def completer(self, propositions: dict[str, ComptesCategorie]) -> int:
        """Ajoute les catégories absentes (jamais de changement d'une ligne existante) ; renvoie le nombre d'ajouts."""
        ajouts = 0
        for nom, c in propositions.items():
            if nom not in self.lignes:
                self.lignes[nom] = c
                ajouts += 1
        return ajouts

    def enregistrer(self) -> None:
        self.chemin.parent.mkdir(parents=True, exist_ok=True)
        donnees = [asdict(c) for c in sorted(self.lignes.values(), key=lambda c: c.categorie.lower())]
        provisoire = self.chemin.with_suffix(".tmp")
        provisoire.write_text(json.dumps(donnees, ensure_ascii=False, indent=1), encoding="utf-8")
        provisoire.replace(self.chemin)


def compte4(valeur) -> str:
    """Compte Sage de la base (15130000) -> « 1513 »."""
    texte = str(valeur or "").strip()
    return texte[:4] if texte and texte != "0" else ""


def proposer_table(correspondances, articles_sage: list[dict]) -> dict[str, ComptesCategorie]:
    """Comptes et préfixe les plus fréquents parmi les articles Sage déjà reliés à chaque catégorie Clover.

    `articles_sage` : lignes de tinvent (sPartCode, lAcNAsset, lAcNRev, lAcNExp, lAcNVar).
    """
    from .correspondance import AUTOMATIQUE, CONFIRME

    sage = {" ".join(str(r["sPartCode"] or "").split()): r for r in articles_sage}
    par_categorie = defaultdict(list)
    for c in correspondances:
        if c.statut in (CONFIRME, AUTOMATIQUE) and c.categorie_clover and c.numero_sage in sage:
            par_categorie[c.categorie_clover].append(sage[c.numero_sage])
    propositions = {}
    for categorie, lignes in par_categorie.items():
        def frequent(cle: str) -> str:
            valeurs = Counter(compte4(r[cle]) for r in lignes if compte4(r[cle]))
            return valeurs.most_common(1)[0][0] if valeurs else ""

        lettres = Counter(m.group(1) for r in lignes if (m := re.match(r"([A-Za-z]+)\d", str(r["sPartCode"]))))
        cmv = frequent("lAcNExp")
        propositions[categorie] = ComptesCategorie(  # écart = CMV (règle du propriétaire)
            categorie, lettres.most_common(1)[0][0] if lettres else PREFIXE_DEFAUT, frequent("lAcNAsset"),
            frequent("lAcNRev"), cmv, cmv)
    return propositions


@dataclass
class CorrectionComptes:
    """Article Sage dont les comptes ne suivent pas la table de sa catégorie."""
    numero: str
    description: str
    categorie: str
    source: str            # « catégorie Clover » ou « compte d'actif »
    actuel: tuple          # (actif, produits, CMV, écart)
    attendu: tuple

    @property
    def changements(self) -> list[str]:
        return [nom for nom, a, b in zip(("Actif", "Produits", "CMV", "Écart"), self.actuel, self.attendu) if a != b]


def comptes_a_corriger(articles_sage: list[dict], table: TableCategories, correspondances=()) -> tuple[list, int]:
    """Articles de stock Sage (lignes tinvent : sPartCode, sName, lAcNAsset, lAcNRev, lAcNExp, lAcNVar) dont un
    compte diffère de la table catégorie -> comptes. Catégorie = celle qui s'accorde le mieux avec l'article : un
    point par compte de l'article (actif, produits, CMV) égal à celui de la catégorie, un point de plus si c'est la
    catégorie Clover de ses articles reliés (Confirmé ou Automatique). Ex. « Oignon » 1520 / 4017 / 5017, Clover
    « Fruits & Légumes » : Fruits & Légumes (3 points) et non Jus & Bières (1 point) ; seul l'actif est corrigé.
    En cas d'égalité, l'article n'est pas proposé (catégorie à décider). Renvoie (corrections, nombre d'articles sans
    catégorie reconnue)."""
    from .articles_sage import reparer_texte
    from .correspondance import AUTOMATIQUE, CONFIRME

    completes = {nom: c for nom, c in table.lignes.items() if not c.problemes()}
    clover = defaultdict(Counter)
    for c in correspondances:
        if c.statut in (CONFIRME, AUTOMATIQUE) and c.categorie_clover in completes and c.numero_sage:
            clover[" ".join(c.numero_sage.split())][c.categorie_clover] += 1
    corrections, inconnus = [], 0
    for r in articles_sage:
        numero = " ".join(str(r.get("sPartCode") or "").split())
        if not numero:
            continue
        actuel = tuple(compte4(r.get(k)) for k in ("lAcNAsset", "lAcNRev", "lAcNExp", "lAcNVar"))
        favorite = clover[numero].most_common(1)[0][0] if clover.get(numero) else None
        points = {}
        for nom, c in completes.items():
            n = sum(1 for a, b in zip(actuel[:3], (c.actif, c.produits, c.cmv)) if a and a == b)
            if nom == favorite:
                n += 1
            if n:
                points[nom] = n
        meilleur = max(points.values(), default=0)
        gagnants = [n for n, p in points.items() if p == meilleur]
        if not gagnants or len({(completes[n].actif, completes[n].produits, completes[n].cmv) for n in gagnants}) != 1:
            inconnus += 1  # aucune catégorie, ou plusieurs à égalité : à décider à la main
            continue
        categorie = favorite if favorite in gagnants else gagnants[0]
        source = "comptes et Clover" if categorie == favorite and meilleur > 1 else (
            "catégorie Clover" if categorie == favorite else "comptes de l'article")
        c = completes[categorie]
        attendu = (c.actif, c.produits, c.cmv, c.ecart or c.cmv)
        if actuel != attendu:
            corrections.append(CorrectionComptes(numero, reparer_texte(str(r.get("sName") or "").strip()), categorie,
                                                 source, actuel, attendu))
    corrections.sort(key=lambda x: x.numero)
    return corrections, inconnus


def lire_comptes_sage(racine: Path, config_toml: dict) -> list[dict]:
    from .__main__ import lire_sage

    return lire_sage(config_toml, lambda b: b.requete(
        "SELECT sPartCode, sName, lAcNAsset, lAcNRev, lAcNExp, lAcNVar FROM tinvent WHERE bService = 0"),
        config_toml.get("sage_import", {}).get("fichier_entreprise"))


def prochain_numero(existants, prefixe: str) -> str:
    """Numéro suivant libre pour le préfixe : « C » + 7 chiffres (largeur la plus fréquente des numéros existants)."""
    motif = re.compile(re.escape(prefixe) + r"(\d+)$", re.IGNORECASE)
    trouves = [m.group(1) for n in existants if (m := motif.match(str(n).strip()))]
    largeur = Counter(len(t) for t in trouves).most_common(1)[0][0] if trouves else LARGEUR_DEFAUT
    suivant = max((int(t) for t in trouves if len(t) == largeur), default=0) + 1
    pris = {str(n).strip().upper() for n in existants}
    while f"{prefixe}{suivant:0{largeur}d}".upper() in pris:
        suivant += 1
    return f"{prefixe}{suivant:0{largeur}d}"


def prix_vente(cout: Decimal, marge: Decimal = MARGE) -> Decimal:
    return (cout * (1 + marge)).quantize(Decimal("0.01"), ROUND_HALF_UP)


def ugs_peremption(jour: date) -> str:
    """UGS Clover = date de péremption au format des articles existants (« 25/05/2028 »)."""
    return jour.strftime("%d/%m/%Y")


def lire_date(texte: str) -> date | None:
    texte = str(texte or "").strip()
    for format_ in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(texte, format_).date()
        except ValueError:
            pass
    return None


def choix_taxes(taux: list[dict]) -> dict[str, list[str] | None]:
    """Libellé -> ids de taxes Clover (None = taxes par défaut de Clover, [] = aucune taxe)."""
    vraies = [t for t in taux if int(t.get("rate") or 0) > 0]
    choix: dict[str, list[str] | None] = {TAXES_DEFAUT: None}
    if len(vraies) > 1:
        choix[" + ".join(t["name"] for t in vraies)] = [t["id"] for t in vraies]
    for t in vraies:
        choix[t["name"]] = [t["id"]]
    sans = [t["id"] for t in taux if int(t.get("rate") or 0) == 0]
    choix[AUCUNE_TAXE] = sans[:1]
    return choix


# ----------------------------------------------------------------------------- l'article à créer
@dataclass
class NouvelArticle:
    nom: str
    cout: Decimal                      # prix d'achat
    prix: Decimal                      # prix de vente Clover
    peremption: date | None            # UGS Clover
    categorie: str = ""                # nom de la catégorie Clover
    id_categorie: str = ""
    type_prix: str = "FIXED"
    unite: str = ""                    # pour « Par unité »
    taxes: list[str] | None = None     # None = taxes par défaut de Clover
    code: str = ""                     # code du produit (code-barres), facultatif
    stock: Decimal = Decimal(0)
    numero_sage: str = ""
    description_sage: str = ""
    comptes: ComptesCategorie | None = None
    creer_sage: bool = True
    creer_clover: bool = True
    id_clover: str = ""
    messages: list[str] = field(default_factory=list)
    service: bool = False              # service Sage (n° « S… ») : compte de charges, produits facultatif
    compte_charges: str = ""           # service : 5xxx
    compte_produits: str = ""          # service : 4xxx, facultatif (service vendu)

    def problemes(self, numeros_sage: set[str] | None = None) -> list[str]:
        p = []
        if not self.nom.strip():
            p.append("nom obligatoire")
        if self.creer_clover:
            if self.prix <= 0:
                p.append("prix de vente obligatoire")
            if self.peremption is None and not self.service:
                p.append("UGS : date de péremption obligatoire")
            if not self.id_categorie:
                p.append("catégorie Clover à choisir")
            if self.type_prix == "PER_UNIT" and not self.unite.strip():
                p.append("unité obligatoire pour un prix par unité")
        if self.cout < 0:
            p.append("prix d'achat négatif")
        if self.creer_sage:
            from .robot_articles import LONGUEUR_NUMERO
            if not self.numero_sage or len(self.numero_sage) > LONGUEUR_NUMERO:
                p.append(f"n° Sage vide ou de plus de {LONGUEUR_NUMERO} caractères")
            elif numeros_sage is not None and self.numero_sage.upper() in {n.upper() for n in numeros_sage}:
                p.append(f"le n° Sage « {self.numero_sage} » existe déjà")
            if not self.description_sage.strip():
                p.append("description Sage obligatoire")
            if self.service:  # règle du propriétaire : les services Sage commencent par « S »
                if not self.numero_sage.upper().startswith("S"):
                    p.append("le n° d'un service commence par S")
                if not re.fullmatch(r"5\d{3}", self.compte_charges or ""):
                    p.append("compte de charges (5xxx) obligatoire pour un service")
                if self.compte_produits and not re.fullmatch(r"4\d{3}", self.compte_produits):
                    p.append("compte de produits : un 4xxx est attendu")
            elif self.comptes is None:
                p.append("comptes Sage de la catégorie à renseigner")
            else:
                p.extend(self.comptes.problemes())
        return p

    def donnees_clover(self) -> dict:
        d = {"name": self.nom.strip(), "price": int((self.prix * CENT).quantize(Decimal(1), ROUND_HALF_UP)),
             "priceType": self.type_prix, "cost": int((self.cout * CENT).quantize(Decimal(1), ROUND_HALF_UP)),
             "isRevenue": True, "hidden": False, "defaultTaxRates": self.taxes is None}
        if self.peremption:
            d["sku"] = ugs_peremption(self.peremption)
        if self.code.strip():
            d["code"] = self.code.strip()
        if self.type_prix == "PER_UNIT":
            d["unitName"] = self.unite.strip()
        return d

    def article_sage(self):
        from .robot_articles import ArticleACreer
        if self.service:
            return ArticleACreer(self.numero_sage.strip(), self.description_sage.strip(), "", self.compte_produits,
                                 self.compte_charges, "", service=True)
        c = self.comptes
        return ArticleACreer(self.numero_sage.strip(), self.description_sage.strip(), c.actif, c.produits, c.cmv, c.ecart)


@vide_apres  # mémoire des lectures vidée après une écriture
def creer_dans_clover(client, a: NouvelArticle) -> str:
    article = client.creer_article(a.donnees_clover(), a.id_categorie, a.taxes or None, a.stock)
    a.id_clover = article["id"]
    return a.id_clover


def relier_correspondance(chemin: Path, a: NouvelArticle) -> None:
    """Ajoute (ou remplace) la ligne de l'article Clover créé, « Confirmé » vers son n° Sage."""
    from .correspondance import CONFIRME, Correspondance, ecrire_correspondance, lire_correspondances

    lignes = [c for c in lire_correspondances(chemin) if c.id_clover != a.id_clover]
    lignes.append(Correspondance(CONFIRME, a.nom, a.categorie, Decimal(0), a.numero_sage, a.description_sage,
                                 a.comptes.produits if a.comptes else "", METHODE, 100, "", a.code, a.id_clover))
    ecrire_correspondance(lignes, chemin)


def noter(racine: Path, a: NouvelArticle, resultat: str) -> None:
    chemin = Path(racine) / "donnees" / "journal_articles_crees.csv"
    nouveau = not chemin.exists()
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with chemin.open("a", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        if nouveau:
            w.writerow(["Date", "Nom", "Catégorie", "Coût", "Prix", "UGS", "N° Sage", "ID Clover", "Résultat"])
        w.writerow([datetime.now().strftime("%Y-%m-%d %H:%M"), a.nom, a.categorie, a.cout, a.prix,
                    ugs_peremption(a.peremption) if a.peremption else "", a.numero_sage, a.id_clover, resultat])


@vide_apres  # mémoire des lectures vidée après une écriture
def creer_dans_sage(racine: Path, config_toml: dict, articles: list, comptes: bool = False) -> list[dict]:
    """Crée les articles (ArticleACreer) dans Sage — ou, avec `comptes`, corrige les comptes d'articles existants :
    dans le Sage déjà ouvert sur le fichier d'entreprise configuré, sinon l'application ouvre Sage elle-même.
    Renvoie [{numero, cree, messages}] (`cree` = créé, ou comptes conformes)."""
    import tempfile

    from .__main__ import commande_moteur
    from .robot_articles import corriger_comptes, creer_articles, fenetre_principale_ouverte
    from .sage_bureau import executer_sur_bureau_cache, sage_ouvert

    fichier = config_toml.get("sage_import", {}).get("fichier_entreprise")
    if fenetre_principale_ouverte(fichier):
        return [asdict(r) for r in (corriger_comptes if comptes else creer_articles)(config_toml, articles)]
    if sage_ouvert():
        raise RuntimeError("Sage est ouvert sur un autre fichier d'entreprise : fermez-le, l'application l'ouvrira "
                           "elle-même.")
    with tempfile.TemporaryDirectory() as dossier:
        demandes, bilan = Path(dossier) / "articles.json", Path(dossier) / "bilan.json"
        demandes.write_text(json.dumps([asdict(a) for a in articles], ensure_ascii=False), encoding="utf-8")
        executer_sur_bureau_cache(commande_moteur() + ["creer-articles-bureau", "--articles", str(demandes),
                                                      "--resultat", str(bilan)] + (["--comptes"] if comptes else []),
                                  racine)
        resultat = json.loads(bilan.read_text(encoding="utf-8")) if bilan.exists() else {}
    if resultat.get("erreur"):
        raise RuntimeError(resultat["erreur"])
    return resultat.get("resultats", [])
