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
from .cache_lectures import vide_apres

CENT = Decimal("0.01")
COMMANDE, FACTURE, STOCK = "commande", "facture", "stock"
ENTREE, SORTIE = "Entrée", "Sortie"
BROUILLON, OUVERTE, FACTUREE, IMPORTEE, PASSE, ECHEC = (
    "Brouillon", "Ouverte", "Facturée", "Importée dans Sage", "Passé dans Sage", "Échec")
TRANSFORME, ANNULE = "Transformé", "Annulé"

# Types de documents (demande du propriétaire du 2026-11-01, comme les documents de vente et d'achat de Sage) :
# genre -> (côté, libellé, préfixe). Seules les factures touchent le stock (Sage et Clover) ; devis, commandes,
# préparations, bons de livraison / réception / retour et avoirs financiers restent dans l'application. Passer d'un
# type à l'autre (« Transformer ») crée le document suivant avec les mêmes lignes et garde la chaîne (`origine`) :
# depuis une facture on retrouve la commande et le bon de livraison.
DEVIS, PREPARATION, LIVRAISON, RETOUR, AVOIR, FACTURE_RETOUR, FACTURE_AVOIR = (
    "devis", "preparation", "livraison", "retour", "avoir", "facture_retour", "facture_avoir")
PREPARATION_ACHAT, COMMANDE_ACHAT, RECEPTION, RETOUR_ACHAT, AVOIR_ACHAT, FACTURE_ACHAT, FACTURE_RETOUR_ACHAT, \
    FACTURE_AVOIR_ACHAT = ("preparation_achat", "commande_achat", "reception", "retour_achat", "avoir_achat",
                           "facture_achat", "facture_retour_achat", "facture_avoir_achat")
TYPES = {
    DEVIS: ("vente", "Devis", "DV"),
    COMMANDE: ("vente", "Bon de commande", "CC"),
    PREPARATION: ("vente", "Préparation de livraison", "PL"),
    LIVRAISON: ("vente", "Bon de livraison", "BL"),
    RETOUR: ("vente", "Bon de retour", "RC"),
    AVOIR: ("vente", "Bon d'avoir financier", "AV"),
    FACTURE: ("vente", "Facture", "FV"),
    FACTURE_RETOUR: ("vente", "Facture de retour", "FRC"),
    FACTURE_AVOIR: ("vente", "Facture d'avoir", "FAV"),
    PREPARATION_ACHAT: ("achat", "Préparation de commande", "PC"),
    COMMANDE_ACHAT: ("achat", "Bon de commande", "BC"),       # registre bons_commande.py
    RECEPTION: ("achat", "Bon de réception", "BR"),
    RETOUR_ACHAT: ("achat", "Bon de retour", "RT"),
    AVOIR_ACHAT: ("achat", "Bon d'avoir financier", "AVF"),
    FACTURE_ACHAT: ("achat", "Facture", "FA"),               # registre fournisseurs.py (factures fournisseurs)
    FACTURE_RETOUR_ACHAT: ("achat", "Facture de retour", "FRT"),  # registre retours.py
    FACTURE_AVOIR_ACHAT: ("achat", "Facture d'avoir", "FAF"),
    STOCK: ("stock", "Document de stock", "DS"),
}
PREFIXES = {genre: prefixe for genre, (_c, _l, prefixe) in TYPES.items()}
# types proposés par « Ajouter » (ordre de Sage)
TYPES_VENTE = [DEVIS, COMMANDE, PREPARATION, LIVRAISON, RETOUR, AVOIR, FACTURE, FACTURE_RETOUR, FACTURE_AVOIR]
TYPES_ACHAT = [PREPARATION_ACHAT, COMMANDE_ACHAT, RECEPTION, RETOUR_ACHAT, AVOIR_ACHAT, FACTURE_ACHAT,
               FACTURE_RETOUR_ACHAT, FACTURE_AVOIR_ACHAT]
# chaînes du propriétaire : vente BC -> BL -> FA -> RC -> FRC ; achat BC -> BR -> FA -> RT -> FRT
TRANSFORMATIONS = {
    DEVIS: [COMMANDE, PREPARATION, LIVRAISON, FACTURE],
    COMMANDE: [PREPARATION, LIVRAISON, FACTURE],
    PREPARATION: [LIVRAISON, FACTURE],
    LIVRAISON: [FACTURE, RETOUR],
    FACTURE: [RETOUR, FACTURE_RETOUR, AVOIR, FACTURE_AVOIR],
    RETOUR: [FACTURE_RETOUR],
    AVOIR: [FACTURE_AVOIR],
    PREPARATION_ACHAT: [COMMANDE_ACHAT, RECEPTION],
    COMMANDE_ACHAT: [RECEPTION, FACTURE_ACHAT],
    RECEPTION: [FACTURE_ACHAT, RETOUR_ACHAT],
    FACTURE_ACHAT: [RETOUR_ACHAT, FACTURE_RETOUR_ACHAT, AVOIR_ACHAT, FACTURE_AVOIR_ACHAT],
    RETOUR_ACHAT: [FACTURE_RETOUR_ACHAT],
    AVOIR_ACHAT: [FACTURE_AVOIR_ACHAT],
}
FACTURES_STOCK = {FACTURE, FACTURE_RETOUR}  # factures de vente importées dans Sage (stock Sage et Clover)


def libelle(genre: str) -> str:
    return TYPES[genre][1] if genre in TYPES else genre


def cote(genre: str) -> str:
    return TYPES[genre][0] if genre in TYPES else ""


@dataclass
class LigneDocument:
    numero_sage: str
    description: str
    quantite: str
    prix: str = "0"           # prix de vente hors taxes, ou coût unitaire d'une entrée de stock
    taxable: bool = False
    cible: str = ""           # document de stock : stock visé dans Sage (noté au 1er essai)
    taxe: str = ""            # « GQ », « G » (TPS), « Q » (TVQ), « » ; vide + taxable = « GQ » (taxes.py)

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
    depot: str = ""           # emplacement Sage (dépôt d'un point de vente) ; vide = par défaut
    origine: str = ""         # document dont celui-ci vient (« Transformer ») : BC -> BL -> FA …
    facteurs: dict = field(default_factory=dict)  # achats : n° Sage -> facteur (unités Sage par unité fournisseur)

    @property
    def sous_total(self) -> Decimal:
        return sum((l.montant for l in self.lignes), Decimal(0))

    @property
    def taxes(self) -> Decimal:
        from . import taxes as tx

        return sum((sum(tx.montants(l.montant, tx.code(l)), Decimal(0)) for l in self.lignes), Decimal(0))

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
                sens: str = "", auteur: str = "", depot: str = "") -> Document:
        if not lignes:
            raise ValueError("Ajoutez au moins une ligne.")
        if cote(genre) in ("vente", "achat") and not tiers:
            raise ValueError("Choisissez le client." if cote(genre) == "vente" else "Choisissez le fournisseur.")
        for l in lignes:
            if Decimal(l.quantite) <= 0:
                raise ValueError(f"{l.numero_sage} : la quantité doit être positive.")
        date.fromisoformat(jour)
        doc = Document(self.prochain_numero(genre), genre, tiers, jour, lignes, remarque, sens,
                       BROUILLON if genre in FACTURES_STOCK or genre == STOCK else OUVERTE,
                       cree=datetime.now().isoformat(timespec="seconds"), auteur=auteur, depot=depot)
        self.documents.append(doc)
        self.enregistrer()
        return doc

    def modifiable(self, doc: Document) -> bool:
        """Un document se modifie ou se supprime tant qu'il n'est pas dans Sage, ni facturé, ni transformé."""
        return doc.etat in (BROUILLON, OUVERTE, ECHEC) and not (doc.genre == STOCK and any(l.cible for l in doc.lignes))

    def chaine(self, numero: str) -> list[str]:
        """Documents d'où vient `numero`, du plus ancien au plus proche (ex. [CC-0001, BL-0002] pour une facture)."""
        precedents, vus = [], {numero}
        doc = next((d for d in self.documents if d.numero == numero), None)
        while doc is not None and doc.origine and doc.origine not in vus:
            precedents.insert(0, doc.origine)
            vus.add(doc.origine)
            doc = next((d for d in self.documents if d.numero == doc.origine), None)
        return precedents

    def transformer(self, numero: str, cible: str, jour: str = "", auteur: str = "") -> Document:
        """Document suivant de la chaîne (mêmes lignes, même tiers et dépôt) ; l'original passe à « Transformé ».
        Un document se transforme une fois ; une facture peut aussi devenir un retour ou un avoir."""
        doc = self.document(numero)
        if cible not in TRANSFORMATIONS.get(doc.genre, []):
            raise ValueError(f"Un {libelle(doc.genre).lower()} ne se transforme pas en {libelle(cible).lower()}.")
        if doc.etat == TRANSFORME and doc.genre not in (FACTURE, FACTURE_ACHAT, LIVRAISON, RECEPTION):
            raise ValueError(f"{numero} est déjà transformé ({doc.lien}).")
        if cible in (COMMANDE_ACHAT, FACTURE_ACHAT, FACTURE_RETOUR_ACHAT):
            raise ValueError("Ce type d'achat se crée dans son registre (transformer_achat).")
        nouveau = self.ajouter(cible, doc.tiers, jour or date.today().isoformat(),
                               [LigneDocument(**asdict(l)) for l in doc.lignes], doc.remarque, auteur=auteur,
                               depot=doc.depot)
        for l in nouveau.lignes:
            l.cible = ""
        nouveau.origine, nouveau.facteurs = doc.numero, dict(doc.facteurs)
        if doc.genre not in (FACTURE, FACTURE_ACHAT):  # une facture reste « Importée » (elle a touché le stock)
            doc.etat = TRANSFORME
        doc.lien = nouveau.numero
        self.enregistrer()
        return nouveau

    def modifier(self, numero: str, tiers: str, jour: str, lignes: list[LigneDocument], remarque: str = "",
                 sens: str = "", depot: str = "") -> Document:
        doc = self.document(numero)
        if not self.modifiable(doc):
            raise ValueError(f"{numero} ({doc.etat}) ne peut plus être modifié.")
        if not lignes:
            raise ValueError("Ajoutez au moins une ligne.")
        date.fromisoformat(jour)
        doc.tiers, doc.date, doc.lignes, doc.remarque = tiers, jour, lignes, remarque
        doc.sens = sens or doc.sens
        doc.depot = depot or doc.depot
        doc.messages = []
        self.enregistrer()
        return doc

    def supprimer(self, numero: str) -> None:
        doc = self.document(numero)
        if not self.modifiable(doc):
            raise ValueError(f"{numero} ({doc.etat}) ne peut plus être supprimé.")
        self.documents.remove(doc)
        for autre in self.documents:  # commande facturée : le lien vers la facture supprimée est retiré
            if autre.lien == numero:
                autre.lien = ""
                if autre.genre == COMMANDE and autre.etat == FACTUREE:
                    autre.etat = OUVERTE
        self.enregistrer()

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
    """PDF du document sur son modèle (pdf_documents.document_commercial : en-tête, cadre du document, client ou
    fournisseur, lignes, totaux avec TPS et TVQ) ; un PDF ouvert dans le lecteur n'empêche pas d'en écrire un autre."""
    from .pdf_documents import document_commercial
    from .points_vente import DEPOT_DEFAUT

    titres = {STOCK: f"Document de stock — {doc.sens}", COMMANDE: "Commande client", FACTURE: "Facture de vente"}
    titres.setdefault(doc.genre, libelle(doc.genre))
    dossier = Path(racine) / "donnees" / "documents"
    chemin = dossier / (re.sub(r'[\\/:*?"<>|]+', "-", f"{doc.numero} {doc.tiers}".strip())[:100] + ".pdf")
    chaine = Registre(racine).chaine(doc.numero)
    infos = [f"Origine : {' → '.join(chaine)}" if chaine else "", f"Dépôt : {doc.depot or DEPOT_DEFAUT}",
             f"Saisi par : {doc.auteur}" if doc.auteur else "", f"Suivant : {doc.lien}" if doc.lien else ""]
    tiers_titre = "Fournisseur" if cote(doc.genre) == "achat" else "Client" if doc.genre != STOCK else "Mouvement"
    tiers = [doc.tiers] if doc.tiers else [doc.sens or ""]
    lignes = [{"numero": l.numero_sage, "description": l.description, "quantite": l.quantite, "prix": l.prix or 0,
               "montant": l.montant, "taxe": l.taxe or ("GQ" if l.taxable else "")} for l in doc.lignes]
    return document_commercial(chemin, racine, titres[doc.genre], doc.numero, doc.date, tiers_titre, tiers,
                               [x for x in infos if x], lignes, avec_taxes=doc.genre != STOCK, etat=doc.etat,
                               remarque=doc.remarque, libelle_prix="Coût unitaire" if doc.genre == STOCK else "Prix")


# --------------------------------------------------------------------------------------------- factures de vente
def ecrire_imp(docs: list[Document], chemin: Path, config_toml: dict) -> Path:
    from types import SimpleNamespace

    from .__main__ import config_import
    from . import taxes as tx
    from .import_sage import ImportSage, LigneImport, ecrire_imp as ecrire

    def signe(d):  # facture de retour : marchandise reprise, quantités et montants négatifs
        return -1 if d.genre == FACTURE_RETOUR else 1

    imps = [ImportSage(SimpleNamespace(client=d.tiers, numero=d.numero, date_facture=date.fromisoformat(d.date)),
                       [LigneImport(l.numero_sage, signe(d) * Decimal(l.quantite), signe(d) * l.montant,
                                    bool(tx.code(l)), codes=tx.code(l)) for l in d.lignes], [])
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


@vide_apres  # mémoire des lectures vidée après une écriture
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
                from .chaine_documents import clover_du_document

                d.etat, d.messages = IMPORTEE, []
                d.messages = clover_du_document(racine, config_toml, d)  # la facture touche aussi le stock Clover
                resultats[d.numero] = f"importée dans Sage ({_argent(d.total)})" + (
                    " ; " + " ; ".join(d.messages) if d.messages else "")
            else:
                d.etat = ECHEC
                d.messages = ["absente de Sage après l'import"] + list(resultat.erreurs)
                resultats[d.numero] = "ÉCHEC : " + " ; ".join(d.messages)
    registre.enregistrer()
    for n, texte in resultats.items():
        journal(f"{n} : {texte}")
    return resultats


# --------------------------------------------------------------------------------------------- documents de stock
def depots(config_toml: dict) -> dict[str, str]:
    """Dépôts proposés à un document de stock (règle du propriétaire du 2026-10-29 : tout document de stock part d'un
    dépôt, rattaché aux points de vente) : {« dépôt (points de vente) » : emplacement Sage}."""
    from .points_vente import points_de_vente

    par_depot: dict[str, list[str]] = {}
    for p in points_de_vente(config_toml, actifs=True):
        par_depot.setdefault(p.depot_sage, []).append(p.libelle)
    return {f"{d} ({', '.join(noms)})": d for d, noms in par_depot.items()}


@vide_apres  # mémoire des lectures vidée après une écriture
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
                             remarque=(doc.remarque or f"{doc.sens} de stock MVOGMBI_Sync")[:60], depot=doc.depot)
    textes = {n: r.get("texte", "") for n, r in resultats.items()}
    if not textes:
        doc.etat, doc.messages = ECHEC, ["Sage n'a rien renvoyé : ouvrez Sage sur le fichier de l'entreprise, puis "
                                          "relancez « Passer dans Sage »."]
        registre.enregistrer()
        raise RuntimeError(doc.messages[0])
    reussi = bool(textes) and all(t.startswith("fait") for t in textes.values())
    doc.etat = PASSE if reussi else ECHEC
    clover = [m for m in doc.messages if m.startswith("Clover :")]  # Clover déjà fait : jamais deux fois
    doc.messages = [f"{n} : {t}" for n, t in textes.items()] + clover
    if reussi:  # le stock Clover du point de vente du dépôt suit (demande du propriétaire du 2026-11-01)
        from .chaine_documents import clover_du_document

        doc.messages += clover_du_document(racine, config_toml, doc)
    registre.enregistrer()
    for m in doc.messages:
        journal(m)
    return textes
