"""Écritures de journal général dans Sage 50 : mouvements du relevé Desjardins absents de Sage (frais, prélèvements…).

Sage_SA_import.exe n'importe pas d'écriture de journal (« The tag … is out of sequence » pour <GENJOUR>, essais du
2026-10-26) : le robot remplit la fenêtre « Journal général » (page Entreprise), comme pour les encaissements.
Relevé sur la copie d'essai : Source = Edit 20, Date = SimplyDate 21, Remarque = Edit 23 ; grille (conteneur 5006),
1re ligne à y=30, 16 points par ligne ; colonnes Compte x=60, Débits x=168, Crédits x=264 ; totaux 100 / 101 ;
« Traiter » 102. Le compte se tape par son numéro (« 5690 »).
Une écriture par mouvement : un dépôt débite le 1055 et crédite le compte choisi, un retrait l'inverse. Les deux totaux
doivent égaler le montant avant « Traiter » ; ensuite l'écriture est cherchée dans la base (source « Relevé
AAAA-MM-JJ », date, montant au 1055). Une écriture déjà présente n'est jamais saisie deux fois.
"""

from __future__ import annotations

import time

from .rapprochement import COMPTE_BANQUE, SAISI, MouvementBanque
from .robot_encaissements import (HAUTEUR_LIGNE, ErreurRobot, FenetreEncaissements, ResultatEncaissement, _lire_montant,
                                  _texte, montant_sage, user32)

WM_SETTEXT = 0x000C
ID_SOURCE, ID_REMARQUE, ID_TOTAL_DEBITS, ID_TOTAL_CREDITS = 20, 23, 100, 101
X_COMPTE, X_DEBIT, X_CREDIT = 60, 168, 264
LONGUEUR_SOURCE, LONGUEUR_REMARQUE = 20, 39


class FenetreJournal(FenetreEncaissements):
    titre, id_grille, colonne_montant, ligne_y0 = "Journal général", 5006, "Compte", 30
    id_date, id_traiter = 21, 102

    def ecrire(self, ident: int, texte: str) -> None:
        import ctypes
        user32.SendMessageW(user32.GetDlgItem(self.h, ident), WM_SETTEXT, 0, ctypes.c_wchar_p(texte))

    def totaux(self):
        return (_lire_montant(_texte(user32.GetDlgItem(self.h, ID_TOTAL_DEBITS))),
                _lire_montant(_texte(user32.GetDlgItem(self.h, ID_TOTAL_CREDITS))))


def compte_sage(numero: str) -> int:
    """« 5690 » -> 56900000 (numéro interne de Sage sur 8 chiffres)."""
    return int(str(numero).strip().ljust(8, "0"))


def source(m: MouvementBanque) -> str:
    return f"Relevé {m.date}"[:LONGUEUR_SOURCE]


def ecriture_presente(base, m: MouvementBanque) -> int | None:
    """N° de l'écriture déjà dans Sage pour ce mouvement (même source, date et montant au compte de banque)."""
    lignes = base.requete(
        "SELECT e.lId FROM tjourent e JOIN tjentact a ON a.lJEntId = e.lId WHERE e.sSource = %s AND "
        "e.dtJourDate = %s AND a.lAcctId = %s AND ROUND(a.dAmount, 2) = %s AND e.nType NOT IN (32, 33, 64, 65) "
        "ORDER BY e.lId DESC LIMIT 1", (source(m), m.date, COMPTE_BANQUE, str(m.montant)))
    return lignes[0]["lId"] if lignes else None


def comptes_valides(base, mouvements: list[MouvementBanque]) -> dict[str, str]:
    """Problème par compte choisi : inexistant, inactif, ou compte de banque lui-même."""
    problemes = {}
    for numero in {m.compte for m in mouvements}:
        if not numero.isdigit() or compte_sage(numero) == COMPTE_BANQUE:
            problemes[numero] = "compte invalide"
            continue
        lignes = base.requete("SELECT bInactive FROM taccount WHERE lId = %s", (compte_sage(numero),))
        if not lignes:
            problemes[numero] = "compte absent de Sage"
        elif lignes[0]["bInactive"]:
            problemes[numero] = "compte inactif dans Sage"
    return problemes


def saisir_ecriture(f: FenetreJournal, m: MouvementBanque, compte_banque: str = "1055") -> ResultatEncaissement:
    """Remplit la fenêtre pour un mouvement, contrôle les totaux, puis « Traiter »."""
    resultat = ResultatEncaissement(m.date, m.montant)
    montant = montant_sage(abs(m.montant))
    f.ecrire(ID_SOURCE, source(m))
    f.regler_date(m.date)
    f.ecrire(ID_REMARQUE, m.description[:LONGUEUR_REMARQUE])
    banque_x, autre_x = (X_DEBIT, X_CREDIT) if m.montant > 0 else (X_CREDIT, X_DEBIT)
    for rang, (compte, x) in enumerate(((compte_banque, banque_x), (m.compte, autre_x))):
        y = f.ligne_y0 + HAUTEUR_LIGNE * rang
        f.taper(X_COMPTE, y, compte, "Compte")
        if f.dialogues():  # compte inconnu : Sage ouvre sa liste de comptes
            raise ErreurRobot(f"Sage ne reconnaît pas le compte {compte}.")
        f.taper(x, y, montant, "Montant")
    attendu = abs(m.montant)
    if f.totaux() != (attendu, attendu):
        resultat.messages.append(f"totaux affichés {f.totaux()} au lieu de {attendu} : écriture abandonnée")
        return resultat
    resultat.traite = f.traiter(resultat)
    return resultat


def appliquer(config_toml: dict, mouvements: list[MouvementBanque], journal=print) -> list:
    """Saisit dans Sage (fenêtre Journal général ouverte) chaque mouvement « Compte choisi », puis le vérifie."""
    from .__main__ import ouvrir_base_sage

    fichier = config_toml.get("sage_import", {}).get("fichier_entreprise")
    compte_banque = str(config_toml.get("encaissements", {}).get("compte_depot", "1055"))
    with ouvrir_base_sage(config_toml, fichier) as base:
        problemes = comptes_valides(base, mouvements)
        deja = {m.cle: ecriture_presente(base, m) for m in mouvements}
    fenetre = FenetreJournal()
    resultats = []
    for m in mouvements:
        if deja.get(m.cle):
            m.etat, m.sage = SAISI, [deja[m.cle]]
            r = ResultatEncaissement(m.date, m.montant, True, [f"déjà dans Sage (écriture n° {deja[m.cle]})"])
        elif m.compte in problemes:
            r = ResultatEncaissement(m.date, m.montant, False, [f"compte {m.compte} : {problemes[m.compte]}"])
        else:
            r = saisir_ecriture(fenetre, m, compte_banque)
            time.sleep(1.5)
            if r.traite:
                with ouvrir_base_sage(config_toml, fichier) as base:
                    numero = ecriture_presente(base, m)
                if numero:
                    m.etat, m.sage = SAISI, [numero]
                    r.messages.append(f"écriture n° {numero}")
                else:
                    r.traite = False
                    r.messages.append("absente de Sage après « Traiter »")
        journal(f"{m.date} {m.montant} $ {m.description[:40]} -> compte {m.compte} : "
                f"{'enregistré' if r.traite else 'NON enregistré'} " + " ".join(r.messages))
        resultats.append((m, r))
        if not r.traite and m.compte not in problemes:
            break  # on s'arrête au premier problème de saisie
    return resultats


def journal_sur_bureau_cache(racine, config_toml: dict, journal=print) -> dict:
    """Exécuté sur le bureau caché : ouvre Sage (fermé au départ), saisit les mouvements « Compte choisi » des relevés,
    enregistre leur nouvel état, referme Sage. Renvoie {"saisis": [...], "a_verifier": [...], "erreur": ""}."""
    from . import coffre
    from .__main__ import executable_import
    from .rapprochement import CONFIRME, RegistreReleves
    from .sage_bureau import SessionSage, executable_sage

    bilan = {"saisis": [], "a_verifier": [], "erreur": ""}
    registre = RegistreReleves(racine)
    mouvements = [m for r in registre.lire() for m in r.mouvements if m.etat == CONFIRME and m.compte]
    if not mouvements:
        return bilan
    exe = executable_sage(executable_import())
    if not exe:
        bilan["erreur"] = "Sage50Accounting.exe introuvable."
        return bilan
    session = SessionSage(exe, journal)
    try:
        fichier = config_toml.get("sage_import", {}).get("fichier_entreprise")
        utilisateur = str(config_toml.get("sage_import", {}).get("utilisateur", "sysadmin"))
        session.ouvrir(fichier, utilisateur, coffre.lire(coffre.SAGE_IMPORT, ""))
        journal(f"{len(mouvements)} écriture(s) à enregistrer.")
        session.ouvrir_journal()
        for m, r in appliquer(config_toml, mouvements, journal):
            texte = f"{m.date} : {m.montant:,.2f} $ — {m.description[:45]} → compte {m.compte}"
            (bilan["saisis"] if r.traite else bilan["a_verifier"]).append(
                texte + ("" if r.traite else " — NON enregistré : " + " ".join(r.messages)))
            registre.retenir(m)
    except Exception as exc:
        bilan["erreur"] = str(exc)
        journal(f"Erreur : {exc}")
    finally:
        registre.enregistrer()
        session.fermer()
    return bilan

