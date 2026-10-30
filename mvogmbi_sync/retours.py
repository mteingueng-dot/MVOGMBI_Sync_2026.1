"""Retours fournisseurs et notes de crédit (demande du propriétaire du 2026-10-29) : un retour « R-<n° de la facture
d'origine> » est une facture d'achat aux quantités NÉGATIVES (même fournisseur Sage, articles Sage, prix de la facture
d'origine, taxes de chaque ligne), importée par Sage_SA_import (<PurInvoice>, comme les factures fournisseurs) puis
vérifiée dans Sage ; le stock Clover des articles reliés diminue (stock_clover, quantité négative). Registre
donnees/retours.json ; un retour déjà dans Sage n'est jamais réimporté."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from .cache_lectures import vide_apres

CENT = Decimal("0.01")
ZERO = Decimal(0)
BROUILLON, IMPORTE, ECHEC = "Brouillon", "Importé dans Sage", "Échec"


@dataclass
class LigneRetour:
    numero_sage: str
    description: str
    quantite: str      # en unités Sage, positive (le retour la rend négative)
    prix: str          # prix Sage unitaire de la facture d'origine
    taxe: str = ""     # « GQ », « G », « Q », « »

    @property
    def montant(self) -> Decimal:
        return (Decimal(self.quantite) * Decimal(self.prix)).quantize(CENT)


@dataclass
class Retour:
    numero: str
    fournisseur_sage: str
    facture_origine: str
    jour: str
    motif: str = ""
    lignes: list[LigneRetour] = field(default_factory=list)
    etat: str = BROUILLON
    messages: list[str] = field(default_factory=list)
    auteur: str = ""
    cree: str = ""
    point_vente: str = ""      # code du point de vente qui rend la marchandise (n° 1 si vide) : son stock Clover

    def facture(self):
        """Facture d'achat négative (fournisseurs.Facture) pour l'import."""
        from . import taxes as tx
        from .fournisseurs import Facture, Ligne

        lignes = [Ligne(l.description, -Decimal(l.quantite), Decimal(l.prix), -l.montant, numero_sage=l.numero_sage,
                        taxe=l.taxe, confirme=True) for l in self.lignes]
        tps = sum((tx.montants(l.montant, l.taxe)[0] for l in lignes if l.taxe), ZERO)
        tvq = sum((tx.montants(l.montant, l.taxe)[1] for l in lignes if l.taxe), ZERO)
        f = Facture(f"retour {self.numero}", self.numero, self.fournisseur_sage, self.fournisseur_sage, self.numero,
                    self.jour, lignes, sum((l.montant for l in lignes), ZERO), tps, tvq)
        f.total = f.sous_total + tps + tvq
        return f


class Registre:
    def __init__(self, racine: Path):
        self.chemin = Path(racine) / "donnees" / "retours.json"
        donnees = json.loads(self.chemin.read_text(encoding="utf-8")) if self.chemin.exists() else []
        self.retours = [Retour(**{**r, "lignes": [LigneRetour(**l) for l in r.get("lignes", [])]}) for r in donnees]

    def enregistrer(self) -> None:
        self.chemin.parent.mkdir(parents=True, exist_ok=True)
        provisoire = self.chemin.with_suffix(".tmp")
        provisoire.write_text(json.dumps([asdict(r) for r in self.retours], ensure_ascii=False, indent=1),
                              encoding="utf-8")
        provisoire.replace(self.chemin)

    def ajouter(self, fournisseur: str, facture: str, jour: str, lignes: list[LigneRetour], motif: str = "",
                auteur: str = "", point_vente: str = "") -> Retour:
        if not fournisseur or not facture:
            raise ValueError("Fournisseur Sage et n° de la facture d'origine obligatoires.")
        if not lignes or any(Decimal(l.quantite) <= 0 for l in lignes):
            raise ValueError("Ajoutez au moins un article, quantités positives.")
        date.fromisoformat(jour)
        numero = f"R-{facture}"[:20]
        if any(r.numero == numero and r.fournisseur_sage == fournisseur for r in self.retours):
            numero = f"R{sum(1 for r in self.retours if r.facture_origine == facture) + 1}-{facture}"[:20]
        r = Retour(numero, fournisseur, facture, jour, motif, lignes, auteur=auteur,
                   cree=datetime.now().isoformat(timespec="seconds"), point_vente=point_vente)
        self.retours.append(r)
        self.enregistrer()
        return r


def lignes_facture_origine(racine: Path, fournisseur: str, numero: str) -> list[LigneRetour]:
    """Lignes (en unités Sage) de la facture d'origine : registre des factures fournisseurs, puis archives."""
    from .fournisseurs import Facture, Registre as Factures, archives
    from .import_achats import meme_numero

    candidates = list(Factures(racine).factures)
    for d in archives(racine):
        try:
            candidates.append(Facture.depuis_dict({k: v for k, v in d.items() if k != "chemin"}))
        except Exception:
            continue
    for f in candidates:
        if f.fournisseur_sage == fournisseur and meme_numero(f.numero, numero):
            from . import taxes as tx

            resultat = []
            for l in f.lignes:
                if not l.numero_sage:
                    continue
                quantite, prix = l.en_sage()
                resultat.append(LigneRetour(l.numero_sage, l.description_sage or l.description, str(quantite),
                                            str(prix), tx.code(l)))
            return resultat
    return []


@vide_apres  # mémoire des lectures vidée après une écriture
def importer(racine: Path, config_toml: dict, numero: str, journal=print) -> Retour:
    """Importe le retour dans Sage (Sage fermé), vérifie sa présence, puis diminue le stock Clover."""
    from . import coffre
    from .__main__ import executable_import, lire_sage, ouvrir_base_sage
    from .import_achats import ecrire_imp_achats, facture_presente, sage_ouvert
    from .sage_auto import executer

    registre = Registre(racine)
    r = next(x for x in registre.retours if x.numero == numero)
    if r.etat == IMPORTE:
        return r
    c = config_toml.get("sage_import", {})
    fichier = Path(c.get("fichier_entreprise", ""))
    exe = executable_import()
    if sage_ouvert():
        raise RuntimeError("Sage est ouvert : fermez-le avant l'import.")
    if lire_sage(config_toml, lambda b: facture_presente(b, r.fournisseur_sage, r.numero), str(fichier)):
        r.etat, r.messages = IMPORTE, ["déjà dans Sage"]
        registre.enregistrer()
        return r
    f = r.facture()
    chemin = ecrire_imp_achats([f], Path(racine) / "sortie" / "achats" / f"Retour_{datetime.now():%Y%m%d_%H%M%S}.IMP",
                               str(c.get("version", "12001")), str(c.get("pays", "1")))
    present = {}

    def verifier(_resume: str = "") -> None:
        import time
        for _ in range(10):
            try:
                with ouvrir_base_sage(config_toml, fichier) as base:
                    present["oui"] = facture_presente(base, r.fournisseur_sage, r.numero)
                return
            except Exception:
                time.sleep(1)

    resultat = executer(exe, chemin, fichier, coffre.lire(coffre.SAGE_IMPORT), pendant_resume=verifier)
    if present.get("oui"):
        r.etat, r.messages = IMPORTE, [f"importé dans Sage ({f.total} $)"]
        try:
            from .points_vente import point_de_vente
            from .stock_clover import mettre_a_jour_factures

            pv = point_de_vente(config_toml, r.point_vente or None)
            for messages in mettre_a_jour_factures(racine, Path(racine) / "config.toml", [f], pv).values():
                r.messages += [f"Clover : {m}" for m in messages]
        except Exception as exc:
            r.messages.append(f"Clover non mis à jour : {exc}")
    else:
        r.etat, r.messages = ECHEC, ["absent de Sage après l'import"] + list(resultat.erreurs or [])
    registre.enregistrer()
    journal(f"{r.numero} : {r.etat} — " + " ; ".join(r.messages))
    return r
