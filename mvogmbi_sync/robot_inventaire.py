"""Saisie d'inventaire dans Sage 50 : fenêtre « Ajustements des Stocks & Transferts » (icône « Ajuster l'inventaire » de
la page Stocks & Services), remplie comme le journal général (Sage n'importe pas d'ajustement par fichier .IMP).

Relevé sur la copie d'essai (2026-10-28) : liste 35 « Ajustements des stocks », emplacement 37, Source Edit 21,
Date SimplyDate 22, Remarque Edit 24, grille 5015 (1re ligne y=30, 16 points par ligne) ; colonnes Article x=40,
Qté x=120, Coût unit. x=338 ; Sage remplit description, unité et compte de l'article ; total 100 ; « Traiter » 34.
Quantité = écart (positif : entrée au coût unitaire tapé = CUMP ; négatif : sortie au coût moyen de Sage).
Avant chaque lot, le stock est relu : l'écart est recalculé, donc une reprise ne compte jamais deux fois ; après
« Traiter », seul le stock lu dans la base (tinvbyln) fait foi.
"""

from __future__ import annotations

import ctypes
import time
from dataclasses import dataclass, field
from decimal import Decimal

from .robot_encaissements import (WM_SETTEXT, ErreurRobot, FenetreEncaissements, ResultatEncaissement, _classe,
                                  _enfants, _texte, user32)

TITRE = "Ajustements des Stocks & Transferts"
TACHE = "Ajuster l'inventaire"
ID_SOURCE, ID_REMARQUE, ID_TOTAL = 21, 24, 100
X_ARTICLE, X_QTE, X_COUT = 40, 120, 338
LIGNES_PAR_SAISIE = 7  # lignes visibles de la grille : un « Traiter » par groupe
LONGUEUR_SOURCE = 20


def nombre_sage(valeur: Decimal, decimales: int = 4) -> str:
    texte = f"{valeur:.{decimales}f}".rstrip("0").rstrip(".")
    return texte.replace(".", ",") or "0"


@dataclass
class LigneAjustement:
    numero: str
    cible: Decimal          # stock voulu (quantité comptée)
    cout: Decimal | None    # CUMP, pour une entrée
    avant: Decimal | None = None
    apres: Decimal | None = None
    valeur_avant: Decimal | None = None  # valeur du stock dans Sage : la différence = coût réel de l'ajustement
    valeur_apres: Decimal | None = None
    fait: bool = False
    messages: list[str] = field(default_factory=list)


class FenetreAjustement(FenetreEncaissements):
    titre, id_grille, colonne_montant, ligne_y0 = TITRE, 5015, "Article", 30
    id_date, id_traiter = 22, 34

    @staticmethod
    def message(dialogue) -> str:
        return " ".join(_texte(c) for c in _enfants(dialogue)
                        if _classe(c) in ("Static", "SimplyStat", "Edit") and _texte(c).strip())

    def traiter(self, resultat: ResultatEncaissement) -> bool:
        """« Traiter » : la fenêtre « Traitement… » de Sage est attendue (jamais fermée) ; « date antérieure » -> Oui ;
        toute autre question est notée puis refusée."""
        from .robot_encaissements import QUESTION_DATE_ANTERIEURE, WM_COMMAND

        user32.PostMessageW(self.h, WM_COMMAND, self.id_traiter, user32.GetDlgItem(self.h, self.id_traiter))
        calme = 0
        fin = time.time() + 120
        while time.time() < fin and calme < 3:
            dialogues = self.dialogues()
            if not dialogues:
                calme += 1
                time.sleep(1)
                continue
            calme = 0
            for d in dialogues:
                texte = self.message(d)
                if texte.startswith("Traitement") or not texte:
                    continue  # progression de Sage : attendre
                if QUESTION_DATE_ANTERIEURE in texte:
                    self.repondre(d, ("oui",))
                    resultat.messages.append("date antérieure à la session de Sage : confirmée")
                else:
                    resultat.messages.append(f"Sage : {texte}")
                    self.repondre(d, ("non", "annuler", "ok"))
                    return False
            time.sleep(1)
        return True

    def ecrire(self, ident: int, texte: str) -> None:
        user32.SendMessageW(user32.GetDlgItem(self.h, ident), WM_SETTEXT, 0, ctypes.c_wchar_p(texte))

    def saisir(self, lignes: list[tuple[str, Decimal, Decimal | None]], jour: str, source: str, remarque: str,
               resultat: ResultatEncaissement) -> bool:
        """Une saisie : [(n° Sage, écart, coût unitaire)] ; « Traiter » ; True si Sage n'a rien refusé."""
        self.ecrire(ID_SOURCE, source[:LONGUEUR_SOURCE])
        self.ecrire(ID_REMARQUE, remarque[:60])
        self.regler_date(jour)
        for rang, (numero, ecart, cout) in enumerate(lignes):
            y = self.ligne_y0 + 16 * rang
            self.taper(X_ARTICLE, y, numero, "Article")
            self.taper(X_QTE, y, nombre_sage(ecart, 3), "Qté")
            if ecart > 0 and cout:
                self.taper(X_COUT, y, nombre_sage(cout), "Coût unit.")
        time.sleep(0.8)
        return self.traiter(resultat)


def appliquer(config_toml: dict, lignes: list[LigneAjustement], jour: str, journal=print) -> list[LigneAjustement]:
    """Ramène le stock Sage de chaque article à sa cible (Sage ouvert sur le fichier configuré, sinon l'application
    l'ouvre elle-même : appelé alors par la commande interne `inventaire-bureau`)."""
    from . import coffre
    from .__main__ import executable_import, lire_sage
    from .robot_articles import cliquer_vrai, fenetre_principale_ouverte, icone_tache, premier_plan
    from .sage_bureau import ErreurSage, SessionSage, _attendre, executable_sage, sage_ouvert

    fichier = config_toml.get("sage_import", {}).get("fichier_entreprise")

    valeurs: dict[str, Decimal] = {}

    def stocks(numeros: list[str]) -> dict[str, Decimal]:
        if not numeros:
            return {}
        marques = ",".join(["%s"] * len(numeros))
        lu = lire_sage(config_toml, lambda b: b.requete(
            "SELECT TRIM(i.sPartCode) n, COALESCE(SUM(y.dInStock), 0) q, COALESCE(SUM(y.dCostStk), 0) v FROM tinvent i "
            f"LEFT JOIN tinvbyln y ON y.lInventId = i.lId WHERE i.sPartCode IN ({marques}) "
            "GROUP BY i.lId, i.sPartCode", tuple(numeros)), fichier)
        for l in lu:
            valeurs[l["n"]] = Decimal(str(l["v"])).quantize(Decimal("0.01"))
        return {l["n"]: Decimal(str(l["q"])).quantize(Decimal("0.001")) for l in lu}

    principale = fenetre_principale_ouverte(fichier)
    if principale:
        session = SessionSage.__new__(SessionSage)
        session.exe, session.journal, session.processus, session.principale = None, journal, None, principale
    elif sage_ouvert():
        raise ErreurRobot("Sage est ouvert sur un autre fichier d'entreprise : fermez-le.")
    else:
        exe = executable_sage(executable_import())
        if not exe:
            raise ErreurRobot("Sage50Accounting.exe introuvable.")
        session = SessionSage(exe, journal)
        try:
            session.ouvrir(fichier, str(config_toml.get("sage_import", {}).get("utilisateur", "sysadmin")),
                           coffre.lire(coffre.SAGE_IMPORT, ""))
        except Exception:
            session.fermer()  # jamais de Sage laissé ouvert après un échec
            raise

    def ouvrir_fenetre() -> FenetreAjustement:
        h = user32.FindWindowW("#32770", TITRE)
        if h:
            return FenetreAjustement(h)
        for _ in range(4):
            if not session.processus:
                premier_plan(session.principale)
            icone = _attendre(lambda: icone_tache(session, TACHE), 30)
            if not icone:
                lien = session._visible("Stocks & Services")
                if lien:
                    (cliquer_vrai if not session.processus else session._cliquer)(lien)
                time.sleep(3)
                continue
            (cliquer_vrai if not session.processus else session._cliquer)(icone)
            h = _attendre(lambda: user32.FindWindowW("#32770", TITRE), 10)
            if h:
                return FenetreAjustement(h)
            if session.processus:
                session.fermer_message_chargement()
        raise ErreurSage("La fenêtre « Ajustements des Stocks & Transferts » de Sage ne s'ouvre pas.")

    try:
        par_numero = {l.numero: l for l in lignes}
        actuels = stocks(list(par_numero))
        for l in lignes:
            l.avant, l.valeur_avant = actuels.get(l.numero), valeurs.get(l.numero)
            if l.avant is None:
                l.messages.append("article absent de Sage")
        a_faire = [l for l in lignes if l.avant is not None and l.avant != l.cible]
        for l in lignes:
            if l.avant is not None and l.avant == l.cible:
                l.fait, l.apres = True, l.avant
        for debut in range(0, len(a_faire), LIGNES_PAR_SAISIE):
            groupe = a_faire[debut:debut + LIGNES_PAR_SAISIE]
            maintenant = stocks([l.numero for l in groupe])  # relu : une reprise ne compte jamais deux fois
            saisies = [(l.numero, l.cible - maintenant[l.numero], l.cout) for l in groupe
                       if maintenant.get(l.numero) is not None and maintenant[l.numero] != l.cible]
            if saisies:
                fenetre = ouvrir_fenetre()
                if not session.processus:
                    premier_plan(fenetre.h)
                r = ResultatEncaissement(jour, Decimal(0))
                fenetre.saisir(saisies, jour, f"Inv. {jour}", "Saisie d'inventaire MVOGMBI_Sync", r)
                time.sleep(1.5)
                if r.messages:
                    journal("Sage : " + " ; ".join(r.messages))
            for _ in range(20):  # Sage écrit le stock après « Traiter » : relu jusqu'à ce qu'il soit à jour
                apres = stocks([l.numero for l in groupe])
                if all(apres.get(l.numero) == l.cible for l in groupe):
                    break
                time.sleep(1.5)
            for l in groupe:
                l.apres, l.valeur_apres = apres.get(l.numero), valeurs.get(l.numero)
                l.fait = l.apres == l.cible
                if not l.fait:
                    l.messages.append(f"stock Sage {l.apres} au lieu de {l.cible}")
                journal(f"{l.numero} : {l.avant} -> {l.apres} ({'fait' if l.fait else 'NON fait'})")
    finally:
        h = user32.FindWindowW("#32770", TITRE)
        if h:
            user32.PostMessageW(h, 0x0010, 0, 0)
        if session.processus:
            session.fermer()
    return lignes
