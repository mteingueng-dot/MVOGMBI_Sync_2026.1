"""Bons de commande fournisseurs (demande du propriétaire du 2026-10-29, rubrique Fournisseur).

Proposition : règle du propriétaire des « articles à commander » (stock Clover − quantité vendue pendant les N
derniers jours <= 0 ; articles vendus dont Clover suit le stock), regroupée par article Sage (correspondance Confirmé
ou Automatique : plusieurs articles Clover peuvent faire un seul n° Sage). Quantité à commander = de quoi couvrir de
nouveau N jours de ventes (vendu − stock positif), arrondie à l'unité supérieure. Fournisseur et prix = dernier achat
de l'article dans Sage (journal 7). Un article sans lien Sage ou jamais acheté reste visible mais ne peut pas être
commandé.

Bons : un par fournisseur à partir des lignes cochées, numérotés « BC-0001 », gardés dans donnees/bons_commande.json,
PDF (en-tête de l'entreprise) dans donnees/bons_commande/. Rien n'est envoyé : la personne transmet le PDF. À la
réception, la facture du fournisseur (registre ou archives des factures fournisseurs, même fournisseur Sage, datée
du jour du bon ou après) est comparée au bon : quantités et prix Sage commandés contre facturés.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import date
from decimal import ROUND_CEILING, Decimal
from pathlib import Path

CENT = Decimal("0.01")
FICHIER = "bons_commande.json"
DOSSIER = "bons_commande"
A_COMMANDER = "À commander"
SANS_LIEN = "Non relié à Sage"
SANS_FOURNISSEUR = "Jamais acheté dans Sage"
CREE, RECU, RECU_ECARTS = "Créé", "Reçu", "Reçu avec écarts"
ECART_PRIX = Decimal("0.02")  # 2 % d'écart de prix toléré à la comparaison


@dataclass
class Proposition:
    numero_sage: str
    description: str
    articles_clover: str
    stock: Decimal
    vendu: Decimal
    quantite: Decimal
    fournisseur: str = ""
    prix: Decimal | None = None
    dernier_achat: str = ""
    etat: str = A_COMMANDER
    facteur: Decimal = Decimal(1)  # unités Sage par unité du fournisseur (dernier achat) : quantité et prix fournisseur

    @property
    def montant(self) -> Decimal | None:
        return (self.quantite * self.prix).quantize(CENT) if self.prix is not None else None

    @property
    def permis(self) -> bool:
        return self.etat == A_COMMANDER

    @property
    def cochee_par_defaut(self) -> bool:
        return self.permis


@dataclass
class LigneBon:
    numero_sage: str
    description: str
    quantite: str      # unités du fournisseur
    prix: str          # prix du fournisseur (par unité du fournisseur)
    montant: str
    facteur: str = "1"  # Qté Sage = quantité × facteur (dernier achat)


@dataclass
class Bon:
    numero: str
    fournisseur: str
    date: str
    lignes: list[LigneBon] = field(default_factory=list)
    etat: str = CREE
    pdf: str = ""
    facture: str = ""

    @property
    def total(self) -> Decimal:
        return sum((Decimal(l.montant or 0) for l in self.lignes), Decimal(0))


# --------------------------------------------------------------------------------------------- proposition
def derniers_achats(base) -> dict[str, dict]:
    """N° Sage -> dernier achat (fournisseur, date, prix Sage, description), journal 7 sans écritures corrigées."""
    from .articles_sage import reparer_texte

    resultat = {}
    for l in base.requete(
            "SELECT TRIM(i.sPartCode) n, TRIM(i.sName) nom, r.dtJournal d, TRIM(v.sName) f, l.dPrice p "
            "FROM titrline l JOIN titrec r ON r.lId = l.lITRecId JOIN tinvent i ON i.lId = l.lInventId "
            "JOIN tvendor v ON v.lId = r.lVenCusId WHERE r.nJournal = 7 AND l.bVarLine = 0 AND r.bReversed = 0 "
            "AND r.bReversal = 0 AND l.dQty > 0 ORDER BY r.dtJournal, r.lId"):
        resultat[l["n"]] = {"fournisseur": reparer_texte(l["f"] or ""), "prix": Decimal(str(l["p"] or 0)).quantize(
            Decimal("0.0001")), "date": l["d"].date().isoformat() if hasattr(l["d"], "date") else str(l["d"] or ""),
                            "nom": reparer_texte(l["nom"] or "")}
    return resultat


def facteurs_dernier_achat(racine: Path) -> dict[tuple[str, str], Decimal]:
    """(fournisseur Sage, n° Sage) -> facteur de la dernière facture reliée (mémoire des factures fournisseurs)."""
    from .fournisseurs import MemoireCorrespondance

    resultat = {}
    for fournisseur, articles in MemoireCorrespondance(racine).donnees.get("articles", {}).items():
        for a in articles.values():
            try:
                facteur = Decimal(str(a.get("facteur") or 1))
            except Exception:
                continue
            if a.get("numero_sage") and facteur > 0:
                resultat[(fournisseur, a["numero_sage"])] = facteur
    return resultat


def descriptions_sage(base) -> dict[str, str]:
    from .articles_sage import reparer_texte

    return {r["n"]: reparer_texte(r["nom"] or "")
            for r in base.requete("SELECT TRIM(sPartCode) n, TRIM(sName) nom FROM tinvent WHERE bService = 0")}


def proposer(ventes: dict, articles: list[dict], liens: dict[str, str], achats: dict[str, dict],
             descriptions: dict[str, str] | None = None,
             facteurs: dict[tuple[str, str], Decimal] | None = None) -> list[Proposition]:
    """`ventes` : ID Clover -> VenteArticle des N jours ; `articles` : catalogue Clover (itemStock) ; `liens` : ID
    Clover -> n° Sage ; `achats` : derniers_achats. Une ligne par n° Sage à commander (ou par article Clover non
    relié) ; quantités Clover additionnées."""
    descriptions = descriptions or {}
    par_id = {a["id"]: a for a in articles if not a.get("deleted")}
    groupes: dict[str, dict] = {}
    for cle, v in ventes.items():
        article = par_id.get(cle)
        quantite = ((article or {}).get("itemStock") or {}).get("quantity")
        if article is None or quantite is None or v.quantite <= 0:
            continue
        numero = liens.get(cle, "")
        g = groupes.setdefault(numero or f"clover:{cle}", {"numero": numero, "noms": [], "stock": Decimal(0),
                                                            "vendu": Decimal(0)})
        g["noms"].append((article.get("name") or v.nom).strip())
        g["stock"] += Decimal(str(quantite))
        g["vendu"] += v.quantite
    resultat = []
    for g in groupes.values():
        if g["stock"] - g["vendu"] > 0:
            continue
        quantite = (g["vendu"] - max(g["stock"], Decimal(0))).quantize(Decimal(1), ROUND_CEILING)
        if quantite <= 0:
            continue
        achat = achats.get(g["numero"]) if g["numero"] else None
        p = Proposition(g["numero"], descriptions.get(g["numero"]) or (achat or {}).get("nom") or g["noms"][0],
                        ", ".join(sorted(set(g["noms"]))), g["stock"].normalize(), g["vendu"].normalize(), quantite)
        if not g["numero"]:
            p.etat = SANS_LIEN
        elif not achat:
            p.etat = SANS_FOURNISSEUR
        else:
            p.fournisseur, p.prix, p.dernier_achat = achat["fournisseur"], achat["prix"], achat["date"]
            facteur = (facteurs or {}).get((p.fournisseur, g["numero"]), Decimal(1))
            if facteur != 1:  # commande en unités du fournisseur : quantité Sage / facteur, prix Sage × facteur
                p.facteur = facteur
                p.quantite = (quantite / facteur).quantize(Decimal(1), ROUND_CEILING)
                p.prix = (achat["prix"] * facteur).quantize(Decimal("0.0001"))
        resultat.append(p)
    ordre = {A_COMMANDER: 0, SANS_FOURNISSEUR: 1, SANS_LIEN: 2}
    resultat.sort(key=lambda p: (ordre[p.etat], p.fournisseur.casefold(), p.description.casefold()))
    return resultat


def lire(racine: Path, config_toml: dict, jours: int) -> list[Proposition]:
    """Ventes Clover des `jours` derniers jours (cache), catalogue Clover, correspondance et derniers achats Sage."""
    from datetime import timedelta

    from .__main__ import charger_config, lire_sage
    from .api_clover import ClientClover
    from .couts_sage import correspondance
    from .previsions import ventes_par_article
    from .statistiques_clover import lire as lire_clover

    client = ClientClover(charger_config(Path(racine) / "config.toml"))
    hier = date.today() - timedelta(days=1)
    donnees = lire_clover(client, hier - timedelta(days=jours - 1), hier, Path(racine) / "donnees" / "cache_clover")
    ventes = ventes_par_article(donnees, hier - timedelta(days=jours - 1), hier)
    achats, descriptions = lire_sage(config_toml, lambda b: (derniers_achats(b), descriptions_sage(b)),
                                     config_toml.get("sage_import", {}).get("fichier_entreprise"))
    from .cache_lectures import inventaire_clover

    return proposer(ventes, inventaire_clover(racine), correspondance(racine), achats, descriptions,
                    facteurs_dernier_achat(racine))


# --------------------------------------------------------------------------------------------- bons
class Registre:
    def __init__(self, racine: Path):
        self.racine = Path(racine)
        self.chemin = self.racine / "donnees" / FICHIER
        self.bons: list[Bon] = []
        if self.chemin.exists():
            for d in json.loads(self.chemin.read_text(encoding="utf-8")):
                d["lignes"] = [LigneBon(**l) for l in d.get("lignes", [])]
                self.bons.append(Bon(**d))

    def enregistrer(self) -> None:
        self.chemin.parent.mkdir(parents=True, exist_ok=True)
        self.chemin.write_text(json.dumps([asdict(b) for b in self.bons], ensure_ascii=False, indent=1),
                               encoding="utf-8")

    def prochain_numero(self) -> str:
        nombres = [int(m.group(1)) for b in self.bons if (m := re.fullmatch(r"BC-(\d+)", b.numero))]
        return f"BC-{max(nombres, default=0) + 1:04d}"


def creer_bons(racine: Path, propositions: list[Proposition], aujourdhui: date | None = None) -> list[Bon]:
    """Un bon par fournisseur (lignes permises seulement), enregistré puis mis en PDF ; renvoie les bons créés."""
    registre = Registre(racine)
    jour = (aujourdhui or date.today()).isoformat()
    par_fournisseur: dict[str, list[Proposition]] = {}
    for p in propositions:
        if p.permis:
            par_fournisseur.setdefault(p.fournisseur, []).append(p)
    crees = []
    for fournisseur in sorted(par_fournisseur, key=str.casefold):
        lignes = [LigneBon(p.numero_sage, p.description, str(p.quantite), str(p.prix), str(p.montant), str(p.facteur))
                  for p in sorted(par_fournisseur[fournisseur], key=lambda p: p.description.casefold())]
        bon = Bon(registre.prochain_numero(), fournisseur, jour, lignes)
        registre.bons.append(bon)
        crees.append(bon)
    registre.enregistrer()
    erreurs = []
    for bon in crees:
        try:
            bon.pdf = str(ecrire_pdf_bon(racine, bon))
        except Exception as exc:  # le bon reste enregistré ; « Refaire le PDF » le recrée
            erreurs.append(f"{bon.numero} : {exc}")
    registre.enregistrer()
    if erreurs:
        raise RuntimeError("Bons enregistrés, mais PDF non créé : " + " ; ".join(erreurs))
    return crees


def modifier_bon(racine: Path, numero: str, fournisseur: str, jour: str, lignes: list[LigneBon]) -> Bon:
    """Bon pas encore reçu : fournisseur, date et lignes remplacés, PDF refait."""
    registre = Registre(racine)
    bon = next(b for b in registre.bons if b.numero == numero)
    if bon.etat != CREE:
        raise ValueError(f"{numero} ({bon.etat}) ne peut plus être modifié.")
    if not lignes:
        raise ValueError("Ajoutez au moins une ligne.")
    bon.fournisseur, bon.date, bon.lignes = fournisseur, jour, lignes
    registre.enregistrer()
    bon.pdf = str(ecrire_pdf_bon(racine, bon))
    registre.enregistrer()
    return bon


def supprimer_bon(racine: Path, numero: str) -> None:
    registre = Registre(racine)
    bon = next(b for b in registre.bons if b.numero == numero)
    if bon.etat != CREE:
        raise ValueError(f"{numero} ({bon.etat}) ne peut plus être supprimé.")
    registre.bons.remove(bon)
    registre.enregistrer()
    if bon.pdf:
        Path(bon.pdf).unlink(missing_ok=True)


def refaire_pdf(racine: Path, numero: str) -> Path:
    registre = Registre(racine)
    bon = next(b for b in registre.bons if b.numero == numero)
    bon.pdf = str(ecrire_pdf_bon(racine, bon))
    registre.enregistrer()
    return Path(bon.pdf)


def _argent(texte: str) -> str:
    return f"{Decimal(texte or 0):,.2f} $".replace(",", " ").replace(".", ",")


def ecrire_pdf_bon(racine: Path, bon: Bon) -> Path:
    from .export_tableau import ecrire_pdf

    dossier = Path(racine) / "donnees" / DOSSIER
    dossier.mkdir(parents=True, exist_ok=True)
    chemin = dossier / (re.sub(r'[\\/:*?"<>|]+', "-", f"{bon.numero} {bon.fournisseur}")[:100] + ".pdf")
    lignes = [[l.numero_sage, l.description, l.quantite.replace(".", ","), _argent(l.prix), _argent(l.montant)]
              for l in bon.lignes]
    lignes.append(["", "Total", "", "", _argent(str(bon.total))])
    ecrire_pdf(chemin, f"Bon de commande {bon.numero}", ["N° article", "Description", "Quantité", "Prix", "Montant"],
               lignes, sous_titre=f"Fournisseur : {bon.fournisseur} — date : {bon.date} — {len(bon.lignes)} article(s)")
    return chemin


# --------------------------------------------------------------------------------------------- réception
def factures_du_fournisseur(racine: Path, bon: Bon) -> list:
    """Factures du même fournisseur Sage datées du jour du bon ou après (registre et archives), la plus récente
    d'abord."""
    from .fournisseurs import Facture, Registre as RegistreFactures, archives

    factures = list(RegistreFactures(racine).factures)
    connues = {(f.fournisseur_sage, f.numero) for f in factures}
    for d in archives(racine):
        try:
            f = Facture.depuis_dict({k: v for k, v in d.items() if k not in ("chemin", "archivee_le",
                                                                             "fichier_archive")})
        except Exception:
            continue
        if (f.fournisseur_sage, f.numero) not in connues:
            factures.append(f)
    retenues = [f for f in factures if (f.fournisseur_sage or "").casefold() == bon.fournisseur.casefold()
                and (f.date_facture or "") >= bon.date]
    return sorted(retenues, key=lambda f: (f.date_facture, f.numero), reverse=True)


ENTETES_COMPARAISON = ["N° Sage", "Description", "Qté commandée", "Qté facturée", "Écart qté", "Prix commandé",
                       "Prix facturé", "Écart prix", "Constat"]


def comparer(bon: Bon, facture) -> tuple[list[list], bool]:
    """Bon contre facture, en unités Sage (Qté Sage = Qté × Facteur ; prix Sage = montant / Qté Sage). Renvoie
    (lignes, conforme)."""
    facturees: dict[str, list[Decimal]] = {}
    for l in facture.lignes:
        if not l.numero_sage:
            continue
        quantite = l.quantite * l.facteur
        f = facturees.setdefault(l.numero_sage, [Decimal(0), Decimal(0)])
        f[0] += quantite
        f[1] += l.montant
    lignes, conforme = [], True
    for l in bon.lignes:  # bon en unités du fournisseur : ramené en unités Sage avec son facteur
        facteur = Decimal(l.facteur or 1)
        commandee = Decimal(l.quantite) * facteur
        prix = (Decimal(l.prix or 0) / facteur).quantize(Decimal("0.0001"))
        q, m = facturees.pop(l.numero_sage, [Decimal(0), Decimal(0)])
        prix_facture = (m / q).quantize(Decimal("0.0001")) if q else None
        ecart_q = (q - commandee).normalize()
        ecart_p = (prix_facture - prix).quantize(CENT) if prix_facture is not None else None
        if not q:
            constat = "Non livré"
        elif ecart_q < 0:
            constat = "Livré en partie"
        elif ecart_q > 0:
            constat = "Plus que commandé"
        elif prix and ecart_p is not None and abs(ecart_p) > prix * ECART_PRIX:
            constat = "Prix différent"
        else:
            constat = "Conforme"
        conforme &= constat == "Conforme"
        lignes.append([l.numero_sage, l.description, commandee.normalize(), q.normalize(), ecart_q, prix,
                       prix_facture, ecart_p, constat])
    for numero, (q, m) in facturees.items():
        conforme = False
        lignes.append([numero, "", Decimal(0), q.normalize(), q.normalize(), None,
                       (m / q).quantize(Decimal("0.0001")) if q else None, None, "Non commandé"])
    return lignes, conforme


def noter_reception(racine: Path, numero: str, facture: str, conforme: bool) -> None:
    registre = Registre(racine)
    for b in registre.bons:
        if b.numero == numero:
            b.etat, b.facture = (RECU if conforme else RECU_ECARTS), facture
    registre.enregistrer()

