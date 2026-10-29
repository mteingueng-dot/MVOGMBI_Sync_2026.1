"""Documents saisis dans l'application (demande du propriétaire du 2026-10-29) : commandes clients, factures de vente
et documents de stock, gardés dans donnees/documents.json.

- Commande client « CC-0001 » : gardée dans l'application (la fonction « Commandes clients » n'est pas activée dans
  Sage : import <SalOrder> refusé, constat du 2026-10-29), PDF avec l'en-tête de l'entreprise ; « Facturer » en
  fait une facture de vente.
- Facture de vente « FV-0001 » : importée dans Sage par un fichier .IMP <SalInvoice> (même format que les factures
  « Vente », validé), Sage fermé ; contrôles avant : client existant qui utilise vos numéros d'articles, articles
  avec un compte de produits, numéro absent de Sage ; vérifiée dans Sage après l'import. Taxes TPS + TVQ sur les
  lignes taxables (prix hors taxes).
- Document de stock « DS-0001 » : entrée ou sortie de stock (perte, casse, don, réception sans facture) passée dans
  Sage par la fenêtre « Ajustements des Stocks & Transferts » (même méthode que l'inventaire), source = n° du
  document. La cible de chaque ligne (stock avant + entrée, ou − sortie) est notée au 1er essai : un nouvel essai
  ne compte jamais deux fois.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

CENT = Decimal("0.01")
COMMANDE, FACTURE, STOCK = "commande", "facture", "stock"
PREFIXES = {COMMANDE: "CC", FACTURE: "FV", STOCK: "DS"}
ENTREE, SORTIE = "Entrée", "Sortie"
BROUILLON, OUVERTE, FACTUREE, IMPORTEE, PASSE, ECHEC = (
    "Brouillon", "Ouverte", "Facturée", "Importée dans Sage", "Passé dans Sage", "Échec")


@dataclass
class LigneDocument:
    numero_sage: str
    description: str
    quantite: str
    prix: str = "0"           # prix de vente hors taxes, ou coût unitaire d'une entrée de stock
    taxable: bool = False
    cible: str = ""           # document de stock : stock visé dans Sage (noté au 1er essai)

    @property
    def montant(self) -> Decimal:
        return (Decimal(self.quantite) * Decimal(self.prix or 0)).quantize(CENT)


@dataclass
class Document:
    numero: str
    genre: str
    tiers: str = ""           # client (commande, facture)
    date: str = ""
    lignes: list[LigneDocument] = field(default_factory=list)
    remarque: str = ""
    sens: str = ""            # document de stock : Entrée ou Sortie
    etat: str = BROUILLON
    lien: str = ""            # commande -> n° de la facture ; facture -> n° de la commande
    messages: list[str] = field(default_factory=list)
    cree: str = ""
    auteur: str = ""

    @property
    def sous_total(self) -> Decimal:
        return sum((l.montant for l in self.lignes), Decimal(0))

    @property
    def taxes(self) -> Decimal:
        from .import_sage import TAXES_GQ

        return sum(((l.montant * taux).quantize(CENT) for l in self.lignes if l.taxable for _n, _a, taux in TAXES_GQ),
                   Decimal(0))

    @property
    def total(self) -> Decimal:
        return self.sous_total + self.taxes


class Registre:
    def __init__(self, racine: Path):
        self.racine = Path(racine)
        self.chemin = self.racine / "donnees" / "documents.json"
        self.documents: list[Document] = []
        if self.chemin.exists():
            for d in json.loads(self.chemin.read_text(encoding="utf-8")):
                d["lignes"] = [LigneDocument(**l) for l in d.get("lignes", [])]
                self.documents.append(Document(**d))

    def enregistrer(self) -> None:
        self.chemin.parent.mkdir(parents=True, exist_ok=True)
        provisoire = self.chemin.with_suffix(".tmp")
        provisoire.write_text(json.dumps([asdict(d) for d in self.documents], ensure_ascii=False, indent=1),
                              encoding="utf-8")
        provisoire.replace(self.chemin)

    def prochain_numero(self, genre: str) -> str:
        prefixe = PREFIXES[genre]
        nombres = [int(m.group(1)) for d in self.documents if (m := re.fullmatch(prefixe + r"-(\d+)", d.numero))]
        return f"{prefixe}-{max(nombres, default=0) + 1:04d}"

    def document(self, numero: str) -> Document:
        return next(d for d in self.documents if d.numero == numero)

    def du_genre(self, genre: str) -> list[Document]:
        return sorted((d for d in self.documents if d.genre == genre), key=lambda d: (d.date, d.numero), reverse=True)

    def ajouter(self, genre: str, tiers: str, jour: str, lignes: list[LigneDocument], remarque: str = "",
                sens: str = "", auteur: str = "") -> Document:
        if not lignes:
            raise ValueError("Ajoutez au moins une ligne.")
        if genre in (COMMANDE, FACTURE) and not tiers:
            raise ValueError("Choisissez le client.")
        for l in lignes:
            if Decimal(l.quantite) <= 0:
                raise ValueError(f"{l.numero_sage} : la quantité doit être positive.")
        date.fromisoformat(jour)
        doc = Document(self.prochain_numero(genre), genre, tiers, jour, lignes, remarque, sens,
                       OUVERTE if genre == COMMANDE else BROUILLON, cree=datetime.now().isoformat(timespec="seconds"),
                       auteur=auteur)
        self.documents.append(doc)
        self.enregistrer()
        return doc

    def facturer(self, numero_commande: str, auteur: str = "") -> Document:
        """Facture de vente (brouillon) faite des lignes de la commande ; la commande passe à « Facturée »."""
        commande = self.document(numero_commande)
        if commande.etat == FACTUREE:
            raise ValueError(f"{commande.numero} est déjà facturée ({commande.lien}).")
        facture = self.ajouter(FACTURE, commande.tiers, date.today().isoformat(),
                               [LigneDocument(**asdict(l)) for l in commande.lignes],
                               f"Commande {commande.numero}" + (f" — {commande.remarque}" if commande.remarque else ""),
                               auteur=auteur)
        facture.lien, commande.lien, commande.etat = commande.numero, facture.numero, FACTUREE
        self.enregistrer()
        return facture


# --------------------------------------------------------------------------------------------- PDF
def _argent(v: Decimal) -> str:
    return f"{v:,.2f} $".replace(",", " ").replace(".", ",")


def ecrire_pdf(racine: Path, doc: Document) -> Path:
    from .export_tableau import ecrire_pdf as pdf

    titres = {COMMANDE: "Commande client", FACTURE: "Facture de vente", STOCK: f"Document de stock ({doc.sens})"}
    dossier = Path(racine) / "donnees" / "documents"
    dossier.mkdir(parents=True, exist_ok=True)
    chemin = dossier / (re.sub(r'[\\/:*?"<>|]+', "-", f"{doc.numero} {doc.tiers}".strip())[:100] + ".pdf")
    lignes = [[l.numero_sage, l.description, l.quantite.replace(".", ","), _argent(Decimal(l.prix or 0)),
               "TPS+TVQ" if l.taxable else "", _argent(l.montant)] for l in doc.lignes]
    if doc.genre != STOCK:
        lignes += [["", "Sous-total", "", "", "", _argent(doc.sous_total)], ["", "Taxes", "", "", "", _argent(doc.taxes)],
                   ["", "Total", "", "", "", _argent(doc.total)]]
    sous = " — ".join(x for x in (f"Client : {doc.tiers}" if doc.tiers else "", f"date : {doc.date}", doc.remarque) if x)
    pdf(chemin, f"{titres[doc.genre]} {doc.numero}", ["N° article", "Description", "Quantité",
                                                       "Coût" if doc.genre == STOCK else "Prix", "Taxes", "Montant"],
        lignes, sous_titre=sous)
    return chemin


# --------------------------------------------------------------------------------------------- factures de vente
def ecrire_imp(docs: list[Document], chemin: Path, config_toml: dict) -> Path:
    from types import SimpleNamespace

    from .__main__ import config_import
    from .import_sage import ImportSage, LigneImport, ecrire_imp as ecrire

    imps = [ImportSage(SimpleNamespace(client=d.tiers, numero=d.numero, date_facture=date.fromisoformat(d.date)),
                       [LigneImport(l.numero_sage, Decimal(l.quantite), l.montant, l.taxable) for l in d.lignes], [])
            for d in docs]
    return ecrire(imps, chemin, config_import(config_toml))


def controler(base, docs: list[Document]) -> dict[str, list[str]]:
    """Problèmes qui empêchent l'import de chaque facture (vide = prête)."""
    numeros = sorted({l.numero_sage for d in docs for l in d.lignes})
    connus = {a.numero.strip() for a in base.articles()}
    sans_compte = {n for n, _d in base.articles_sans_compte_revenus(numeros)}
    resultat = {}
    for d in docs:
        problemes = []
        reglage = base.client_utilise_mes_articles(d.tiers)
        if reglage is None:
            problemes.append(f"client « {d.tiers} » absent de Sage")
        elif not reglage:
            problemes.append(f"fiche du client « {d.tiers} » : cochez « Ce client utilise mes n° articles » (onglet "
                             "Importer/Exporter)")
        problemes += [f"article {n} absent de Sage" for n in {l.numero_sage for l in d.lignes} - connus]
        problemes += [f"article {n} sans compte de produits" for n in {l.numero_sage for l in d.lignes} & sans_compte]
        if base.facture_existe(d.numero, d.tiers):
            problemes.append(f"la facture {d.numero} existe déjà dans Sage")
        resultat[d.numero] = problemes
    return resultat


def importer_factures(racine: Path, config_toml: dict, numeros: list[str], journal=print) -> dict[str, str]:
    """Contrôle, écrit le .IMP et l'importe (Sage fermé), puis vérifie chaque facture dans Sage."""
    from . import coffre
    from .__main__ import executable_import, fermer_bases, lire_sage, ouvrir_base_sage
    from .sage_auto import executer
    from .sage_bureau import sage_ouvert

    registre = Registre(racine)
    docs = [registre.document(n) for n in numeros]
    fichier_sai = Path(config_toml.get("sage_import", {}).get("fichier_entreprise", ""))
    exe = executable_import()
    if not fichier_sai.is_file() or not exe:
        raise RuntimeError("Fichier d'entreprise Sage ou outil d'import introuvable (page Sage 50).")
    if sage_ouvert():
        raise RuntimeError("Sage est ouvert : fermez-le avant l'import.")
    problemes = lire_sage(config_toml, lambda base: controler(base, docs), str(fichier_sai))
    resultats, a_importer = {}, []
    for d in docs:
        if problemes[d.numero]:
            resultats[d.numero] = "non importée : " + " ; ".join(problemes[d.numero])
            d.messages = problemes[d.numero]
        else:
            a_importer.append(d)
    if a_importer:
        chemin = ecrire_imp(a_importer, Path(racine) / "sortie" / "ventes_saisies" /
                            f"Ventes_{datetime.now():%Y%m%d_%H%M%S}.IMP", config_toml)
        journal(f"Import de {len(a_importer)} facture(s) de vente dans {fichier_sai.name}…")
        presentes: dict[str, bool] = {}

        def verifier(_resume: str = "") -> None:
            import time
            for _ in range(10):
                try:
                    with ouvrir_base_sage(config_toml, fichier_sai) as base:
                        for d in a_importer:
                            presentes[d.numero] = base.facture_existe(d.numero, d.tiers)
                    return
                except Exception:
                    time.sleep(1)

        fermer_bases()
        resultat = executer(exe, chemin, fichier_sai, coffre.lire(coffre.SAGE_IMPORT), pendant_resume=verifier,
                            delai=int(config_toml.get("automatique", {}).get("delai_import", 3600)))
        if not presentes:
            verifier()
        for d in a_importer:
            if presentes.get(d.numero):
                d.etat, d.messages = IMPORTEE, []
                resultats[d.numero] = f"importée dans Sage ({_argent(d.total)})"
            else:
                d.etat = ECHEC
                d.messages = ["absente de Sage après l'import"] + list(resultat.erreurs)
                resultats[d.numero] = "ÉCHEC : " + " ; ".join(d.messages)
    registre.enregistrer()
    for n, texte in resultats.items():
        journal(f"{n} : {texte}")
    return resultats


# --------------------------------------------------------------------------------------------- documents de stock
def passer_stock(racine: Path, config_toml: dict, numero: str, journal=print) -> dict[str, str]:
    """Entrée ou sortie de stock dans Sage ; renvoie {n° Sage : résultat}."""
    from .__main__ import lire_sage
    from .inventaire import AjustementSage, ajuster_sage, lire_sage as stocks_sage

    registre = Registre(racine)
    doc = registre.document(numero)
    if doc.etat == PASSE:
        raise ValueError(f"{doc.numero} est déjà passé dans Sage.")
    actuels = lire_sage(config_toml, stocks_sage, config_toml.get("sage_import", {}).get("fichier_entreprise"))
    ajustements = []
    for l in doc.lignes:
        if l.numero_sage not in actuels:
            raise ValueError(f"Article {l.numero_sage} absent de Sage (ou service).")
        avant = actuels[l.numero_sage]["quantite"]
        if not l.cible:  # 1er essai : la cible est notée, un nouvel essai ne compte jamais deux fois
            signe = 1 if doc.sens == ENTREE else -1
            l.cible = str(avant + signe * Decimal(l.quantite))
        cout = Decimal(l.prix) if doc.sens == ENTREE and Decimal(l.prix or 0) > 0 else actuels[l.numero_sage]["cout"]
        ajustements.append(AjustementSage(l.numero_sage, l.description, avant, Decimal(l.cible), cout))
    registre.enregistrer()
    resultats = ajuster_sage(racine, config_toml, ajustements, doc.date, source=doc.numero,
                             remarque=(doc.remarque or f"{doc.sens} de stock MVOGMBI_Sync")[:60])
    textes = {n: r.get("texte", "") for n, r in resultats.items()}
    if not textes:
        doc.etat, doc.messages = ECHEC, ["Sage n'a rien renvoyé : ouvrez Sage sur le fichier de l'entreprise, puis "
                                          "relancez « Passer dans Sage »."]
        registre.enregistrer()
        raise RuntimeError(doc.messages[0])
    reussi = bool(textes) and all(t.startswith("fait") for t in textes.values())
    doc.etat = PASSE if reussi else ECHEC
    doc.messages = [f"{n} : {t}" for n, t in textes.items()]
    registre.enregistrer()
    for m in doc.messages:
        journal(m)
    return textes
