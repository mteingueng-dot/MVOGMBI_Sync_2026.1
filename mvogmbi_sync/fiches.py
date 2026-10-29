"""Fiches de description ouvertes par un double-clic dans les listes (demande du propriétaire du 2026-10-29) :
client, fournisseur, article, document de vente ou d'achat, document de stock — lus dans Sage (lecture seule) et
affichés dans la fenêtre principale par-dessus la liste (« ◀ Retour » y revient)."""

from __future__ import annotations

import tkinter as tk
from decimal import Decimal
from pathlib import Path

from .articles_sage import reparer_texte
from .design import FenetreOutil, CARTE, TEXTE, TEXTE_DOUX, dans_application
from .export_tableau import bouton_exporter
from .langues import t

CENT = Decimal("0.01")


def _d(v) -> Decimal:
    return Decimal(str(v or 0)).quantize(CENT)


def _jour(v) -> str:
    return (v.date() if hasattr(v, "date") else v).isoformat() if v else ""


def _argent(v) -> str:
    return f"{v:,.2f} $".replace(",", " ").replace(".", ",")


# --------------------------------------------------------------------------------------------- lectures
def lire_tiers(base, cote: str, nom: str) -> tuple[list[tuple[str, str]], list]:
    """Renseignements de la fiche du client ou du fournisseur, puis ses mouvements (avec le solde)."""
    from .rapports import mouvements_client, mouvements_fournisseur

    table = "tcustomr" if cote == "clients" else "tvendor"
    lignes = base.requete(f"SELECT * FROM {table} WHERE sName = %s", (nom,))
    if not lignes:
        return [(t("Nom"), nom), (t("État"), t("Introuvable dans Sage"))], []
    f = lignes[0]
    adresse = ", ".join(x for x in (f.get("sStreet1"), f.get("sStreet2")) if x and x.strip())
    ville = " ".join(x for x in (f.get("sCity"), f.get("sProvState"), f.get("sPostalZip")) if x and x.strip())
    infos = [(t("Nom"), reparer_texte(f.get("sName") or "")), (t("Contact"), f.get("sCntcName") or ""),
             (t("Adresse"), adresse), (t("Ville"), ville), (t("Pays"), f.get("sCountry") or ""),
             (t("Téléphone"), " / ".join(x for x in (f.get("sPhone1"), f.get("sPhone2")) if x and x.strip())),
             (t("Courriel"), f.get("sEmail") or ""), (t("Site web"), f.get("sWebSite") or ""),
             (t("Paiement net (jours)"), str(f.get("nNetDay") or 0)),
             (t("État"), t("Inactif") if f.get("bInactive") else t("Actif")),
             (t("Montant de l'année"), _argent(_d(f.get("dAmtYtd")))),
             (t("Montant de l'an dernier"), _argent(_d(f.get("dLastYrAmt"))))]
    if cote == "clients":
        infos += [(t("Limite de crédit"), _argent(_d(f.get("dCrLimit")))),
                  (t("Utilise mes n° d'articles"), t("Oui") if f.get("bUseMyItem") else t("Non"))]
    else:
        infos += [(t("N° de taxe"), f.get("sTaxId") or ""),
                  (t("Utilise mes n° d'articles"), t("Oui") if f.get("bUseMyItem") else t("Non"))]
    mouvements = (mouvements_client if cote == "clients" else mouvements_fournisseur)(base, nom)
    return [(k, v) for k, v in infos if str(v).strip()], [("Mouvements", *mouvements)]


def lire_article(base, numero: str) -> tuple[list[tuple[str, str]], list]:
    from .rapports import mouvements_article

    lignes = base.requete("SELECT * FROM tinvent WHERE TRIM(sPartCode) = %s", (numero,))
    if not lignes:
        return [(t("N° Sage"), numero), (t("État"), t("Introuvable dans Sage"))], []
    a = lignes[0]
    comptes = {r["lId"]: r["sName"] or "" for r in base.requete("SELECT lId, sName FROM taccount")}

    def compte(c):
        return f"{str(c)[:4]} {comptes.get(c, '')}".strip() if c else ""

    prix = base.requete("SELECT lPrcListId l, dPrice p FROM tinvprc WHERE lInventId = %s ORDER BY lPrcListId",
                        (a["lId"],))
    stocks = base.requete(
        "SELECT TRIM(l.sGrpDesc) d, y.dInStock q, y.dCostStk v, y.dLastCost c FROM tinvbyln y "
        "LEFT JOIN tinvloc l ON l.lId = y.lInvLocId WHERE y.lInventId = %s", (a["lId"],))
    quantite = sum((Decimal(str(s["q"] or 0)) for s in stocks), Decimal(0))
    valeur = sum((_d(s["v"]) for s in stocks), Decimal(0))
    infos = [(t("N° Sage"), numero), (t("Description"), reparer_texte(a.get("sName") or "")),
             (t("Type"), t("Service") if a.get("bService") else t("Stock")),
             (t("État"), t("Inactif") if a.get("bInactive") else t("Actif")),
             (t("Unité de vente"), a.get("sSellUnit") or ""), (t("Unité d'achat"), a.get("sBuyUnit") or ""),
             (t("Compte d'actif"), compte(a.get("lAcNAsset"))), (t("Compte de produits"), compte(a.get("lAcNRev"))),
             (t("Compte CMV"), compte(a.get("lAcNExp"))), (t("Compte d'écart"), compte(a.get("lAcNVar"))),
             (t("Prix de vente"), " ; ".join(_argent(_d(p["p"])) for p in prix if p["p"]) or "—"),
             (t("Stock"), f"{quantite.normalize():f}".replace(".", ",")), (t("Valeur du stock"), _argent(valeur)),
             (t("CUMP"), _argent((valeur / quantite).quantize(Decimal("0.0001"))) if quantite > 0 and valeur > 0
              else "—")]
    sections = [("Stock par emplacement", ["Emplacement", "Quantité", "Valeur", "Dernier coût"],
                 [[s["d"] or t("Emplacement par défaut"), Decimal(str(s["q"] or 0)).normalize(), _d(s["v"]),
                   _d(s["c"])] for s in stocks])]
    if not a.get("bService"):
        sections.append(("Mouvements", *mouvements_article(base, numero)))
    return [(k, v) for k, v in infos if str(v).strip()], sections


def lire_document(base, cote: str, numero: str, tiers: str) -> tuple[list[tuple[str, str]], list]:
    """Facture de vente (journal 8) ou d'achat (journal 7) : en-tête et lignes d'articles."""
    table, journal = ("tcustomr", 8) if cote == "ventes" else ("tvendor", 7)
    lignes = base.requete(
        f"SELECT r.lId, r.dtJournal d, r.dInvAmt m, r.sComment c, TRIM(i.sPartCode) n, TRIM(i.sName) nom, x.dQty q, "
        f"x.dPrice p, x.dAmt a FROM titrec r JOIN {table} t ON t.lId = r.lVenCusId LEFT JOIN titrline x ON "
        "x.lITRecId = r.lId AND x.bVarLine = 0 LEFT JOIN tinvent i ON i.lId = x.lInventId "
        f"WHERE r.nJournal = %s AND TRIM(r.sSource1) = %s AND t.sName = %s AND r.bReversed = 0 AND r.bReversal = 0",
        (journal, numero, tiers))
    if not lignes:
        return [(t("Document"), numero), (t("Tiers"), tiers), (t("Lignes"), t("aucune ligne d'article dans Sage"))], []
    e = lignes[0]
    infos = [(t("Document"), numero), (t("Client") if cote == "ventes" else t("Fournisseur"), tiers),
             (t("Date"), _jour(e["d"])), (t("Montant"), _argent(_d(e["m"]))), (t("Remarque"), e["c"] or "")]
    sections = [("Lignes", ["N° Sage", "Article", "Quantité", "Prix", "Montant"],
                 [[l["n"] or "", reparer_texte(l["nom"] or ""), Decimal(str(l["q"] or 0)).normalize(),
                   _d(l["p"]), _d(l["a"])] for l in lignes if l["n"]])]
    return [(k, v) for k, v in infos if str(v).strip()], sections


def lire_document_stock(base, source: str, jour: str) -> tuple[list[tuple[str, str]], list]:
    lignes = base.requete(
        "SELECT r.nJournal j, r.sComment c, TRIM(i.sPartCode) n, TRIM(i.sName) nom, x.dQty q, x.dPrice p, x.dAmt a "
        "FROM titrec r JOIN titrline x ON x.lITRecId = r.lId JOIN tinvent i ON i.lId = x.lInventId "
        "WHERE r.nJournal IN (12, 14) AND TRIM(r.sSource1) = %s AND r.dtJournal = %s AND x.bVarLine = 0",
        (source, jour))
    infos = [(t("Source"), source), (t("Date"), jour)]
    if lignes:
        infos += [(t("Type"), t("Ajustement d'inventaire") if lignes[0]["j"] == 12 else t("Transfert entre emplacements")),
                  (t("Remarque"), lignes[0]["c"] or "")]
    sections = [("Lignes", ["N° Sage", "Article", "Quantité", "Prix", "Montant"],
                 [[l["n"], reparer_texte(l["nom"] or ""), Decimal(str(l["q"] or 0)).normalize(), _d(l["p"]),
                   _d(l["a"])] for l in lignes])]
    return [(k, v) for k, v in infos if str(v).strip()], sections


# --------------------------------------------------------------------------------------------- fenêtre
class Fiche(FenetreOutil):
    """Fiche : renseignements (deux colonnes) puis un tableau par section ; lue dans Sage dans un fil."""

    def __init__(self, parent, racine: Path, titre: str, lecture):
        from .fenetre_gestion import lire_sage_dans_un_fil

        super().__init__(parent.nametowidget("."))  # enfant de la fenêtre principale : affichable dans sa zone
        self.title(titre)
        self.configure(background=CARTE, padx=14, pady=10)
        self.geometry("1000x640")
        self.etat = tk.Label(self, text="", background=CARTE, foreground=TEXTE_DOUX, anchor="w")
        self.etat.pack(fill="x")
        self.corps = tk.Frame(self, background=CARTE)
        self.corps.pack(fill="both", expand=True)
        dans_application(parent, self)
        lire_sage_dans_un_fil(self, racine, lecture, self.afficher, self.etat, "Lecture de la fiche dans Sage…",
                              cle=f"fiche:{titre}")

    def afficher(self, resultat) -> None:
        from .page_rapports import remplir, tableau_simple

        infos, sections = resultat
        self.etat.configure(text="")
        grille = tk.Frame(self.corps, background=CARTE)
        grille.pack(fill="x", pady=(0, 8))
        moitie = (len(infos) + 1) // 2
        for i, (cle, valeur) in enumerate(infos):
            colonne, rang = (0, i) if i < moitie else (2, i - moitie)
            tk.Label(grille, text=cle, background=CARTE, foreground=TEXTE_DOUX, anchor="w").grid(
                row=rang, column=colonne, sticky="w", padx=(0, 10), pady=1)
            tk.Label(grille, text=valeur, background=CARTE, foreground=TEXTE, anchor="w",
                     font=("Segoe UI Semibold", 10)).grid(row=rang, column=colonne + 1, sticky="w", padx=(0, 40))
        for titre, entetes, lignes in sections:
            ligne = tk.Frame(self.corps, background=CARTE)
            ligne.pack(fill="x", pady=(6, 0))
            tk.Label(ligne, text=t(titre), background=CARTE, font=("Segoe UI Semibold", 10)).pack(side="left")
            tableau = tableau_simple(self.corps, hauteur=8)
            remplir(tableau, entetes, lignes, {"Article": 260, "Client / fournisseur": 200}, decroissant=False)
            bouton_exporter(ligne, tableau, f"{self.title()} — {t(titre)}").pack(side="right")


def ouvrir_fiche(parent, racine: Path, genre: str, ligne: list, entetes: list[str]):
    """Fiche de la ligne double-cliquée d'une liste (`genre` : celui de fenetre_gestion.ouvrir_liste)."""
    valeur = dict(zip(entetes, ligne))
    if genre in ("clients", "fournisseurs"):
        nom = str(ligne[0])
        return Fiche(parent, racine, f"{t('Fiche')} : {nom}", lambda b: lire_tiers(b, genre, nom))
    if genre in ("articles", "livre"):
        numero = str(valeur.get("N° Sage") or "")
        if not numero:
            return None
        return Fiche(parent, racine, f"{t('Fiche article')} : {numero}", lambda b: lire_article(b, numero))
    if genre in ("documents_vente", "documents_achat"):
        cote = "ventes" if genre == "documents_vente" else "achats"
        numero, tiers = str(valeur.get("Facture") or ""), str(valeur.get("Client") or valeur.get("Fournisseur") or "")
        return Fiche(parent, racine, f"{t('Document')} : {numero}", lambda b: lire_document(b, cote, numero, tiers))
    if genre == "documents_stock":
        source, jour = str(valeur.get("Source") or ""), str(valeur.get("Date") or "")
        return Fiche(parent, racine, f"{t('Document de stock')} : {source}",
                     lambda b: lire_document_stock(b, source, jour))
    return None
