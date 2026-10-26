"""Robot de saisie des paiements fournisseurs dans la fenêtre « Paiements » de Sage 50 (même méthode que les encaissements).

Sage n'importe pas de paiement : le robot remplit la fenêtre, puis « Traiter ». Relevé sur la copie d'essai (2026-10-26) :
- en-tête : « Payer les factures d'achat » (liste 39), « Par » 49 = « Comptant », « De » 51 = « 1055 … », fournisseur
  (« À l'ordre de ») 25, date SimplyDate 31 ; le champ 22 devient « Source » (« Comptant ») ;
- grille (conteneur 5012) : toutes les écritures ouvertes du fournisseur (factures ET notes de crédit), triées par date
  puis n° interne, comme dans la base (tventr/tventrdt) ; 16 points par ligne, 1re ligne à y=42 ; colonne
  « Montant de paiement » en dernier (≈ 91 % de la largeur) ; total dans l'étiquette 101 ;
- un virement peut payer plusieurs factures (une ligne chacune, un seul « Traiter ») ; paiement partiel accepté
  (choix du propriétaire) ; jamais plus que le solde d'une facture ;
- fermer la fenêtre sans traiter : « Désirez-vous vraiment supprimer cette écriture de journal ? » -> Oui.
Contrôle après « Traiter » dans la base : le solde de chaque facture a baissé du montant payé.
"""

from __future__ import annotations

import ctypes.wintypes as wt
import ctypes
import time
from datetime import date
from decimal import Decimal

from .robot_encaissements import (HAUTEUR_LIGNE, ErreurRobot, FenetreEncaissements, ResultatEncaissement, _lire_montant,
                                  _texte, user32)

ID_TYPE, ID_FOURNISSEUR, ID_MODE, ID_COMPTE, ID_TOTAL = 39, 25, 49, 51, 101
TYPE_FACTURES = "Payer les factures d'achat"


class FenetrePaiements(FenetreEncaissements):
    titre, id_grille, colonne_montant, ligne_y0 = "Paiements", 5012, "Montant de paiement", 42

    def _taille_grille(self) -> tuple[int, int]:
        r = wt.RECT()
        user32.GetClientRect(self.grille, ctypes.byref(r))
        return r.right, r.bottom

    def x_montant(self) -> int:
        return int(self._taille_grille()[0] * 0.915)

    def lignes_visibles(self) -> int:
        return max(1, (self._taille_grille()[1] - self.ligne_y0) // HAUTEUR_LIGNE)

    def total(self) -> Decimal:
        return _lire_montant(_texte(user32.GetDlgItem(self.h, ID_TOTAL)))


def ordre_grille(base, fournisseur: str) -> list[str]:
    """N° des écritures ouvertes du fournisseur (notes de crédit comprises), dans l'ordre de la grille Paiements."""
    lignes = base.requete(
        "SELECT t.sSource numero FROM tventr t JOIN tvendor v ON v.lId = t.lVenId JOIN tventrdt d ON d.lVenTrId = t.lId "
        "WHERE v.sName = %s GROUP BY t.lId, t.dtDate, t.sSource HAVING ROUND(SUM(d.dAmount), 2) <> 0 "
        "ORDER BY t.dtDate, t.lId", (fournisseur,))
    return [(l["numero"] or "").strip() for l in lignes]


def solde_facture(base, fournisseur: str, numero: str) -> Decimal | None:
    lignes = base.requete(
        "SELECT ROUND(SUM(d.dAmount), 2) solde FROM tventr t JOIN tvendor v ON v.lId = t.lVenId "
        "JOIN tventrdt d ON d.lVenTrId = t.lId WHERE v.sName = %s AND TRIM(t.sSource) = %s", (fournisseur, numero))
    return None if not lignes or lignes[0]["solde"] is None else Decimal(str(lignes[0]["solde"])).quantize(Decimal("0.01"))


def payer(fenetre: FenetrePaiements, fournisseur: str, lignes: list[tuple[str, Decimal, Decimal | None]], jour: date,
          ordre: list[str], compte: str, mode: str = "Comptant") -> ResultatEncaissement:
    """Saisit un paiement (une ligne par facture : (n°, montant, solde dans Sage)), vérifie le total, puis « Traiter »."""
    montant = sum((m for _, m, _ in lignes), Decimal(0))
    resultat = ResultatEncaissement(jour.isoformat(), montant)
    for facture, part, solde in lignes:
        if facture not in ordre:
            resultat.messages.append(f"{facture} n'est pas parmi les factures impayées de {fournisseur} dans Sage.")
            return resultat
        if solde is None or part > solde:
            resultat.messages.append(f"{facture} : paiement {part} $ supérieur au solde {solde} $ ; rien n'est saisi.")
            return resultat
    for tentative in range(1, 4):
        fenetre.choisir(ID_TYPE, TYPE_FACTURES)
        fenetre.choisir(ID_MODE, mode)
        fenetre.choisir(ID_COMPTE, f"{compte} ")
        fenetre.choisir(ID_FOURNISSEUR, fournisseur)
        fenetre.regler_date(jour.isoformat())
        for facture, part, _ in lignes:
            fenetre.saisir_ligne(ordre.index(facture), part)
        lu = fenetre.total()
        if lu == montant:
            resultat.traite = fenetre.traiter(resultat)
            return resultat
        resultat.messages.append(f"Essai {tentative} : total affiché {lu} au lieu de {montant}, saisie effacée.")
        fenetre.effacer(fournisseur)
        time.sleep(1.5)
    resultat.messages.append("Saisie abandonnée après 3 essais.")
    return resultat


def appliquer(config_toml: dict, paiements, compte: str, mode: str = "Comptant", journal=print) -> list:
    """Saisit dans Sage (fenêtre Paiements ouverte) chaque paiement confirmé, puis vérifie le solde dans la base.

    `paiements` : objets Paiement (paiements_fournisseurs) ; ceux qui sont saisis passent à l'état SAISI.
    """
    from .__main__ import ouvrir_base_sage
    from .paiements_fournisseurs import SAISI

    fichier = config_toml.get("sage_import", {}).get("fichier_entreprise")
    fenetre = FenetrePaiements()
    resultats = []
    for p in paiements:
        montant, jour = p.avis.montant, date.fromisoformat(p.avis.date_virement)
        with ouvrir_base_sage(config_toml, fichier) as base:
            ordre = ordre_grille(base, p.fournisseur_sage)
            lignes = [(f, m, solde_facture(base, p.fournisseur_sage, f)) for f, m, _ in p.lignes()]
        resultat = payer(fenetre, p.fournisseur_sage, lignes, jour, ordre, compte, mode)
        time.sleep(1.5)
        if resultat.traite:
            with ouvrir_base_sage(config_toml, fichier) as base:
                apres = {f: solde_facture(base, p.fournisseur_sage, f) for f, _, _ in lignes}
            ecarts = [f"{f} : {apres[f]} $ (avant : {avant} $)" for f, m, avant in lignes
                      if apres[f] is None or avant - apres[f] != m]
            if not ecarts:
                restes = ", ".join(f"{f} : {apres[f]} $" for f, _, _ in lignes)
                p.etat, p.remarque = SAISI, f"payé {montant} $ le {jour} (solde restant {restes})"
            else:
                resultat.traite = False
                resultat.messages.append("Après « Traiter », solde inattendu : " + " ; ".join(ecarts))
        journal(f"{p.fournisseur_sage} {p.facture} : {montant} $ le {jour} -> "
                f"{'payé' if resultat.traite else 'NON payé'} " + " ".join(resultat.messages))
        resultats.append((p, resultat))
        if not resultat.traite:
            break  # on s'arrête au premier problème
    return resultats
