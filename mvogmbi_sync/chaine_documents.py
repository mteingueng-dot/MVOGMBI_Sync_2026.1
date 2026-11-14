"""Chaîne des documents de vente et d'achat (demande du propriétaire du 2026-11-01).

Vente : devis -> bon de commande (CC) -> préparation -> bon de livraison (BL) -> facture (FV) -> bon de retour (RC)
-> facture de retour (FRC) ; bon d'avoir financier (AV) -> facture d'avoir (FAV). Registre documents.py.
Achat : préparation (PC) -> bon de commande (BC, bons_commande.py) -> bon de réception (BR) -> facture (factures
fournisseurs, fournisseurs.py, « Prête à importer ») -> bon de retour (RT) -> facture de retour (FRT, retours.py) ;
avoir financier (AVF) -> facture d'avoir (FAF).

Règle du propriétaire : les bons (commande, livraison, réception, retour) et les avoirs financiers restent dans
l'application ; seules les factures touchent le stock, dans Sage ET dans Clover (`ajuster_clover`) : facture de
vente = sortie, facture de retour client = entrée, facture d'achat = entrée (stock_clover.py), facture de retour
fournisseur = sortie (retours.py). Les documents de stock (DS) font de même au dépôt choisi.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from . import documents as dc

CENT = Decimal("0.01")


# --------------------------------------------------------------------------------------------- Clover
def point_vente_du_depot(config_toml: dict, depot: str):
    """Point de vente rattaché au dépôt Sage (le n° 1 pour « Emplacement par défaut » ou un dépôt inconnu)."""
    from .points_vente import points_de_vente

    points = points_de_vente(config_toml, actifs=True)
    depot = (depot or "").strip().casefold()
    return next((p for p in points if p.depot_sage.strip().casefold() == depot), None) or next(
        (p for p in points if p.principal), None)


def ajuster_clover(racine: Path, config_toml: dict, depot: str, mouvements: list[tuple[str, Decimal]]) -> list[str]:
    """Stock Clover du point de vente du dépôt : stock relu + variation, par article Sage relié (Confirmé /
    Automatique) à UN seul article Clover ; sinon la ligne est signalée (à corriger à la main)."""
    from .__main__ import charger_config
    from .api_clover import ClientClover
    from .correspondance import lire_correspondances
    from .points_vente import fichier_correspondance
    from .stock_clover import articles_clover_par_numero

    pv = point_vente_du_depot(config_toml, depot)
    client = ClientClover(charger_config(Path(racine) / "config.toml", pv))
    liens = articles_clover_par_numero(lire_correspondances(fichier_correspondance(racine, pv)))
    messages = []
    for numero, variation in mouvements:
        ids = liens.get(numero.strip(), [])
        if len(ids) != 1:
            messages.append(f"{numero} : {'aucun' if not ids else 'plusieurs'} article(s) Clover relié(s), stock "
                            "Clover à corriger à la main")
            continue
        avant = client.stock(ids[0])
        client.regler_stock(ids[0], avant + variation)
        messages.append(f"{numero} : Clover {avant.normalize():f} -> {(avant + variation).normalize():f}")
    return messages


def clover_du_document(racine: Path, config_toml: dict, doc: dc.Document) -> list[str]:
    """Stock Clover suivant un document passé dans Sage (une seule fois : « Clover : » dans ses messages)."""
    if any(m.startswith("Clover :") for m in doc.messages):
        return []
    if doc.genre == dc.STOCK:
        signe = 1 if doc.sens == dc.ENTREE else -1
    elif doc.genre in dc.FACTURES_STOCK:
        signe = 1 if doc.genre == dc.FACTURE_RETOUR else -1
    else:
        return []
    try:
        messages = ajuster_clover(racine, config_toml, doc.depot,
                                  [(l.numero_sage, signe * Decimal(l.quantite)) for l in doc.lignes])
    except Exception as exc:
        return [f"Clover non mis à jour : {exc}"]
    return ["Clover : " + " ; ".join(messages)]


# --------------------------------------------------------------------------------------------- achats
def _lignes_bon(bon) -> tuple[list[dc.LigneDocument], dict]:
    lignes = [dc.LigneDocument(l.numero_sage, l.description, l.quantite, l.prix) for l in bon.lignes]
    return lignes, {l.numero_sage: l.facteur for l in bon.lignes}


def facture_achat(racine: Path, fournisseur: str, numero: str, jour: str, lignes: list[dc.LigneDocument],
                  facteurs: dict, origine: list[str]):
    """Facture fournisseur « Prête à importer » (registre des factures fournisseurs) faite des lignes reçues ;
    quantités et prix du fournisseur, Qté Sage = quantité × facteur."""
    from . import taxes as tx
    from .fournisseurs import Facture, Ligne, Registre, etat_apres_controle

    if not numero:
        raise ValueError("Le n° de facture du fournisseur est obligatoire.")
    lignes_f = [Ligne(l.description, Decimal(l.quantite), Decimal(l.prix or 0), l.montant, numero_sage=l.numero_sage,
                      description_sage=l.description, facteur=Decimal(str(facteurs.get(l.numero_sage, 1) or 1)),
                      taxable=l.taxable, confirme=True, taxe=l.taxe) for l in lignes]
    sous_total = sum((l.montant for l in lignes_f), Decimal(0))
    montants = [tx.montants(l.montant, tx.code(l)) for l in lignes_f]
    tps, tvq = sum((m[0] for m in montants), Decimal(0)), sum((m[1] for m in montants), Decimal(0))
    nom = f"{' → '.join(origine)} {fournisseur} {numero}".strip()
    facture = Facture(nom, uuid.uuid4().hex, fournisseur, fournisseur,
                      numero, jour, lignes_f, sous_total, tps, tvq, sous_total + tps + tvq,
                      "Bon de réception" if origine else "Saisie manuelle",
                      [f"Origine : {' → '.join(origine)}"] if origine else [])
    facture.etat = etat_apres_controle(facture, facture.controles())
    registre = Registre(racine)
    registre.factures.append(facture)
    registre.enregistrer()
    return facture


def transformer_achat(racine: Path, source: tuple[str, str], cible: str, jour: str = "", auteur: str = "",
                      numero_facture: str = "") -> str:
    """`source` : ("bc", n° du bon) ou ("doc", n° d'un document de l'application) ou ("fa", fichier d'une facture
    fournisseur). Renvoie le n° (ou le nom) du document créé."""
    from . import bons_commande as bc

    jour = jour or date.today().isoformat()
    registre = dc.Registre(racine)
    sorte, ident = source
    if sorte == "bc":
        bon = next(b for b in bc.Registre(racine).bons if b.numero == ident)
        lignes, facteurs = _lignes_bon(bon)
        fournisseur, origine, depot = bon.fournisseur, [bon.numero], ""
    elif sorte == "doc":
        doc = registre.document(ident)
        lignes, facteurs = [dc.LigneDocument(**asdict(l)) for l in doc.lignes], dict(doc.facteurs)
        fournisseur, origine, depot = doc.tiers, registre.chaine(doc.numero) + [doc.numero], doc.depot
    else:  # facture fournisseur : lignes en unités Sage (quantité × facteur, prix Sage)
        from .fournisseurs import Registre as Factures

        f = next(x for x in Factures(racine).factures if x.fichier == ident)
        lignes = []
        for l in f.lignes:
            if not l.numero_sage:
                continue
            qte_sage, prix_sage = l.en_sage()
            lignes.append(dc.LigneDocument(l.numero_sage, l.description_sage or l.description, str(qte_sage),
                                           str(prix_sage), taxe=l.taxe, taxable=bool(l.taxe or l.taxable)))
        facteurs, fournisseur, origine, depot = {}, f.fournisseur_sage, [f.numero], ""
    if cible == dc.FACTURE_ACHAT:
        facture = facture_achat(racine, fournisseur, numero_facture, jour, lignes, facteurs, origine)
        if sorte == "bc":
            bc.noter_reception(racine, ident, numero_facture, True)
        elif sorte == "doc":
            doc = registre.document(ident)
            doc.etat, doc.lien = dc.TRANSFORME, f"FA {numero_facture}"
            registre.enregistrer()
        return f"FA {facture.numero}"
    if cible == dc.FACTURE_RETOUR_ACHAT:
        from .retours import LigneRetour, Registre as Retours

        facture_origine = numero_facture or (origine[-1] if origine else "")
        retour = Retours(racine).ajouter(fournisseur, facture_origine, jour,
                                         [LigneRetour(l.numero_sage, l.description,
                                                      str(Decimal(l.quantite) * Decimal(str(facteurs.get(
                                                          l.numero_sage, 1) or 1))),
                                                      str((Decimal(l.prix or 0) / Decimal(str(facteurs.get(
                                                          l.numero_sage, 1) or 1))).quantize(Decimal("0.0001"))),
                                                      l.taxe) for l in lignes],
                                         f"Origine : {' → '.join(origine)}", auteur)
        if sorte == "doc":
            doc = registre.document(ident)
            doc.etat, doc.lien = dc.TRANSFORME, retour.numero
            registre.enregistrer()
        return retour.numero
    nouveau = registre.ajouter(cible, fournisseur, jour, lignes, auteur=auteur, depot=depot)
    nouveau.origine, nouveau.facteurs = origine[-1] if origine else "", facteurs
    if sorte == "bc":
        bc.noter_reception(racine, ident, nouveau.numero, True)
    elif sorte == "doc":
        doc = registre.document(ident)
        doc.etat, doc.lien = dc.TRANSFORME, nouveau.numero
    registre.enregistrer()
    return nouveau.numero


# --------------------------------------------------------------------------------------------- stock
def annuler_stock(racine: Path, config_toml: dict, numero: str, auteur: str = "") -> dc.Document:
    """Document de stock déjà passé dans Sage : contre-passé par le document inverse (même dépôt, mêmes lignes,
    mouvement contraire), passé dans Sage et Clover ; l'original devient « Annulé »."""
    registre = dc.Registre(racine)
    doc = registre.document(numero)
    if doc.etat == dc.ANNULE:
        raise ValueError(f"{numero} est déjà annulé.")
    if doc.etat != dc.PASSE:  # rien dans Sage : il suffit de le supprimer
        registre.supprimer(numero)
        return doc
    inverse = registre.ajouter(dc.STOCK, "", date.today().isoformat(),
                               [dc.LigneDocument(l.numero_sage, l.description, l.quantite, l.prix) for l in doc.lignes],
                               f"Annulation de {numero}", dc.SORTIE if doc.sens == dc.ENTREE else dc.ENTREE, auteur,
                               doc.depot)
    inverse.origine = numero
    registre.enregistrer()
    dc.passer_stock(racine, config_toml, inverse.numero)
    registre = dc.Registre(racine)
    if registre.document(inverse.numero).etat == dc.PASSE:
        original = registre.document(numero)
        original.etat, original.lien = dc.ANNULE, inverse.numero
        registre.enregistrer()
    return registre.document(inverse.numero)


def document_inverse_sage(racine: Path, config_toml: dict, source: str, jour: str,
                          auteur: str = "") -> list[dc.Document]:
    """Ajustement d'inventaire de Sage (pas un document de l'application) : document de stock inverse préparé
    (quantités de signe contraire), à passer ensuite dans Sage et Clover. Les transferts se défont par un transfert
    en sens inverse (Stock > Transferts entre magasins)."""
    from .__main__ import lire_sage
    from .fiches import lire_document_stock

    infos, sections = lire_sage(config_toml, lambda base: lire_document_stock(base, source, jour),
                                config_toml.get("sage_import", {}).get("fichier_entreprise"))
    if any(v == "Transfert entre emplacements" or "Transfer" in str(v) for _k, v in infos):
        raise ValueError("Un transfert se défait par un transfert en sens inverse (Stock > Transferts entre magasins).")
    lignes = sections[0][2] if sections else []
    if not lignes:
        raise ValueError(f"Aucune ligne trouvée pour {source} du {jour} dans Sage.")
    registre = dc.Registre(racine)
    entrees = [dc.LigneDocument(n, d, str(-q), str(p or 0)) for n, d, q, p, _m in lignes if q < 0]
    sorties = [dc.LigneDocument(n, d, str(q), str(p or 0)) for n, d, q, p, _m in lignes if q > 0]
    crees = []
    for sens, lignes_sens in ((dc.ENTREE, entrees), (dc.SORTIE, sorties)):
        if lignes_sens:
            doc = registre.ajouter(dc.STOCK, "", date.today().isoformat(), lignes_sens,
                                   f"Annulation de {source} du {jour}", sens, auteur)
            doc.origine = source
            crees.append(doc)
    registre.enregistrer()
    return crees
