"""Transfert de marchandises entre deux dépôts Sage (un dépôt = un point de vente), dans la fenêtre « Ajustements des
Stocks & Transferts » en mode « Transfert entre Emplacements » (icône « Transfert des stocks » de la page Stocks &
Services ; Sage n'importe pas de transfert par fichier .IMP).

Relevé sur la copie d'essai (2026-10-28) : liste 35 (« Ajustements des stocks » / « Transfert entre Emplacements »),
De = liste 40, au = liste 42, Source Edit 21, Date SimplyDate 22, Remarque Edit 24, grille 5015 (1re ligne y=30,
16 points par ligne) : Article x=40, Qté x=114 ; Sage reprend l'unité, la description et le coût moyen ; « Traiter »
34. Le transfert est écrit dans titrec (nJournal 14, bTrfLoc 1, sSource1 = source) et déplace quantité et valeur
entre les lignes tinvbyln des deux emplacements. La source (n° du transfert) fait foi : un lot déjà dans Sage n'est
jamais refait. Validé : ESSAI0001, 1 unité de « Emplacement par défaut » vers « Dépôt essai 2 » (2,05 $).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from decimal import Decimal

from .robot_encaissements import ErreurRobot, ResultatEncaissement, user32
from .robot_inventaire import TITRE, FenetreAjustement, nombre_sage

TACHE = "Transfert des stocks"
MODE_TRANSFERT = "Transfert entre Emplacements"
ID_MODE, ID_DE, ID_VERS, ID_SOURCE, ID_REMARQUE = 35, 40, 42, 21, 24
X_ARTICLE, X_QTE = 40, 114
LIGNES_PAR_LOT = 7  # lignes visibles de la grille : un « Traiter » par lot
LONGUEUR_SOURCE = 20


@dataclass
class LotSage:
    source: str
    lignes: list[tuple[str, Decimal]]  # (n° Sage, quantité)
    fait: bool = False
    deja: bool = False  # trouvé dans Sage avant la saisie
    messages: list[str] = field(default_factory=list)


def lots(reference: str, lignes: list[tuple[str, Decimal]]) -> list[LotSage]:
    """Lots de 7 lignes ; source = n° du transfert (« TR-0001 », puis « TR-0001-2 »… s'il y a plusieurs lots)."""
    groupes = [lignes[i:i + LIGNES_PAR_LOT] for i in range(0, len(lignes), LIGNES_PAR_LOT)]
    return [LotSage((reference if i == 0 else f"{reference}-{i + 1}")[:LONGUEUR_SOURCE], g)
            for i, g in enumerate(groupes)]


def sources_dans_sage(base, reference: str) -> set[str]:
    return {r["s"] for r in base.requete(
        "SELECT TRIM(sSource1) s FROM titrec WHERE nJournal = 14 AND bTrfLoc = 1 AND bReversed = 0 "
        "AND sSource1 LIKE %s", (reference + "%",))}


def transferer(config_toml: dict, reference: str, de: str, vers: str, lignes: list[tuple[str, Decimal]], jour: str,
               remarque: str = "", journal=print) -> list[LotSage]:
    """Transfère les lignes du dépôt `de` vers le dépôt `vers` (Sage ouvert sur le fichier configuré, sinon
    l'application l'ouvre elle-même : appelé alors par la commande interne `transfert-bureau`)."""
    from .__main__ import lire_sage
    from .robot_articles import cliquer_vrai, icone_tache, ouvrir_session, premier_plan
    from .sage_bureau import ErreurSage, _attendre

    fichier = config_toml.get("sage_import", {}).get("fichier_entreprise")
    a_faire = lots(reference, lignes)
    deja = lire_sage(config_toml, lambda b: sources_dans_sage(b, reference), fichier)
    for lot in a_faire:
        lot.deja = lot.fait = lot.source in deja
    if all(l.fait for l in a_faire):
        return a_faire
    session = ouvrir_session(config_toml, journal)

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
        for lot in a_faire:
            if lot.fait:
                continue
            fenetre = ouvrir_fenetre()
            if not session.processus:
                premier_plan(fenetre.h)
            r = ResultatEncaissement(jour, Decimal(0))
            try:
                fenetre.choisir(ID_MODE, MODE_TRANSFERT)
                fenetre.choisir(ID_DE, de)
                fenetre.choisir(ID_VERS, vers)
                fenetre.ecrire(ID_SOURCE, lot.source)
                fenetre.ecrire(ID_REMARQUE, (remarque or f"Transfert {de} -> {vers}")[:60])
                fenetre.regler_date(jour)
                for rang, (numero, quantite) in enumerate(lot.lignes):
                    y = fenetre.ligne_y0 + 16 * rang
                    fenetre.taper(X_ARTICLE, y, numero, "Article")
                    fenetre.taper(X_QTE, y, nombre_sage(quantite, 3), "Qté")
                time.sleep(0.8)
                fenetre.traiter(r)
            except ErreurRobot as exc:
                r.messages.append(str(exc))
            lot.messages += r.messages
            for _ in range(10):  # seule la présence du transfert dans Sage fait foi
                if lot.source in lire_sage(config_toml, lambda b: sources_dans_sage(b, reference), fichier):
                    lot.fait = True
                    break
                time.sleep(1.5)
            journal(f"{lot.source} : {'transféré' if lot.fait else 'NON transféré — ' + ' ; '.join(lot.messages)}")
            if not lot.fait:
                break  # jamais de lot suivant après un échec
    finally:
        h = user32.FindWindowW("#32770", TITRE)
        if h:
            user32.PostMessageW(h, 0x0010, 0, 0)
        if session.processus:
            session.fermer()
    return a_faire
