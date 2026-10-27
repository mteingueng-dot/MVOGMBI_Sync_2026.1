"""Rapports et recherches (page « 11. Rapports ») : suivi complet de chaque vente et historique de Sage.

Suivi des ventes (règle du propriétaire du 2026-10-27) : une ligne par facture de vente de l'application — date de
traitement, journée(s), statut (importée, bloquée, échec…), montants HT / taxes / TTC, commentaire, état de
l'encaissement (solde dû dans Sage) et état du rapprochement (encaissements retrouvés sur les relevés Desjardins
chargés). Sources : historique des traitements (donnees/historique_ventes.csv, écrit à chaque exécution), journal des
imports (anciennes exécutions), factures « Vente … » de Sage.

Recherches dans Sage (lecture seule) par client, fournisseur, vente, encaissement, paiement, article :
- client : factures, encaissements (tcustr + tcustrdt) ;
- fournisseur : factures, paiements, notes de crédit (tventr + tventrdt), avec le solde courant ;
- article : mouvements de stock (titrec + titrline : ventes, achats, retours, ajustements), sans les écritures
  corrigées (« CORR ») qui s'annulent ni les lignes d'écart de coût.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

CENT = Decimal("0.01")
HISTORIQUE = "historique_ventes.csv"
ENTETES_HISTORIQUE = ["Date de traitement", "Début", "Fin", "Facture", "Statut", "Montant HT", "Taxes", "Montant TTC",
                      "Commentaire"]

# Codes de Sage
JOURNAUX_ARTICLES = {7: "Achat", 8: "Vente", 12: "Ajustement d'inventaire", 17: "Retour / note de crédit d'achat"}
TYPES_CLIENT = {0: "Facture", 1: "Encaissement", 2: "Escompte / ajustement"}
TYPES_FOURNISSEUR = {0: "Facture", 1: "Paiement", 2: "Payée comptant", 3: "Dépôt / avance", 8: "Note de crédit"}


def _d(valeur) -> Decimal:
    return Decimal(str(valeur or 0)).quantize(CENT)


def argent(valeur: Decimal) -> str:
    return f"{valeur:,.2f} $".replace(",", " ").replace(".", ",")


def _jour(valeur) -> str:
    return (valeur.date() if hasattr(valeur, "date") else valeur).isoformat() if valeur else ""


# --------------------------------------------------------------------------------------------- historique
def noter_historique(racine: Path, cr) -> None:
    """Ajoute à donnees/historique_ventes.csv une ligne par journée traitée (hors simulation)."""
    if cr.simulation or not cr.jours:
        return
    chemin = Path(racine) / "donnees" / HISTORIQUE
    nouveau = not chemin.exists()
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with chemin.open("a", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        if nouveau:
            w.writerow(ENTETES_HISTORIQUE)
        for j in cr.jours:
            debut = getattr(j, "debut", None) or j.jour
            w.writerow([f"{cr.debut:%Y-%m-%d %H:%M}", debut.isoformat(), j.jour.isoformat(), getattr(j, "numero", ""),
                        j.etat, f"{j.sous_total:.2f}" if j.lignes else "",
                        f"{j.taxes:.2f}" if j.lignes else "", f"{j.total:.2f}" if j.lignes else "", j.detail])


@dataclass
class LigneSuivi:
    traitement: str
    journee: str
    facture: str
    statut: str
    ht: Decimal | None
    taxes: Decimal | None
    ttc: Decimal | None
    commentaire: str = ""
    encaissement: str = "—"
    rapprochement: str = "—"
    fin: str = ""             # dernier jour (tri)

    def valeurs(self) -> list[str]:
        argent = (lambda v: "" if v is None else f"{v:,.2f}")
        return [self.traitement, self.journee, self.statut, argent(self.ht), argent(self.taxes), argent(self.ttc),
                self.commentaire, self.encaissement, self.rapprochement]


ENTETES_SUIVI = ["Date de traitement", "Journée", "Statut", "Montant HT", "Taxes", "Montant TTC", "Commentaire",
                 "État de l'encaissement", "État du rapprochement"]


def _journee(debut: str, fin: str) -> str:
    return fin if not debut or debut == fin else f"{debut} → {fin}"


def lire_historique(racine: Path) -> dict[str, LigneSuivi]:
    """Dernier état connu de chaque facture (clé : n° de facture, sinon la journée)."""
    from .facture import jours_facture

    suivi: dict[str, LigneSuivi] = {}
    imports = Path(racine) / "donnees" / "journal_imports.csv"
    if imports.exists():  # anciennes exécutions (avant l'historique) : factures importées ou en échec
        with imports.open(encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f, delimiter=";"):
                numero = r.get("Facture", "")
                jours = jours_facture(numero)
                if not jours:
                    continue
                ht, ttc = _d(r.get("Sous-total")), _d(r.get("Total"))
                statut = "Facture importée" if r.get("Résultat") == "importée" else f"Import : {r.get('Résultat')}"
                suivi[numero] = LigneSuivi(r.get("Date et heure", "")[:16], _journee(str(jours[0]), str(jours[-1])),
                                           numero, statut, ht, ttc - ht, ttc, fin=str(jours[-1]))
    historique = Path(racine) / "donnees" / HISTORIQUE
    if historique.exists():
        with historique.open(encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f, delimiter=";"):
                cle = r["Facture"] or r["Fin"]
                montant = (lambda c: _d(r[c]) if r.get(c) else None)
                suivi[cle] = LigneSuivi(r["Date de traitement"], _journee(r["Début"], r["Fin"]), r["Facture"],
                                        r["Statut"], montant("Montant HT"), montant("Taxes"), montant("Montant TTC"),
                                        r["Commentaire"], fin=r["Fin"])
    return suivi


def suivi_ventes(racine: Path, base, client: str, compte_depot: int) -> list[LigneSuivi]:
    """Tableau de suivi complet : historique + factures de Sage + encaissement + rapprochement."""
    from .automatique import jours_couverts_sage
    from .encaissements import etat_factures_sage
    from .facture import jours_facture

    suivi = lire_historique(racine)
    lignes = base.requete(
        "SELECT TRIM(t.sSource) s, t.dtDate d, t.dPreTaxAmt m FROM tcustr t JOIN tcustomr c ON c.lId = t.lCusId "
        "WHERE c.sName = %s AND TRIM(t.sSource) REGEXP %s", (client, r"^Vente [0-9]{4}-[0-9]{2}-[0-9]{2}(/[0-9]{2})?$"))
    _, incoherentes = jours_couverts_sage(lignes)
    dans_sage = {l["s"] for l in lignes}
    for ligne in suivi.values():  # importée autrefois, supprimée de Sage depuis
        if ligne.statut == "Facture importée" and ligne.facture not in dans_sage:
            ligne.commentaire = " — ".join(x for x in (ligne.commentaire, "n'est plus dans Sage (supprimée)") if x)
    for l in lignes:
        numero = l["s"]
        jours = jours_facture(numero)
        if not jours or any(x.startswith(numero + " ") for x in incoherentes):
            continue
        ligne = suivi.get(numero)
        if ligne is None:  # facture saisie autrement (ancienne, à la main) : connue seulement de Sage
            suivi[numero] = ligne = LigneSuivi("", _journee(str(jours[0]), str(jours[-1])), numero, "Dans Sage",
                                               None, None, _d(l["m"]), fin=str(jours[-1]))
        elif not ligne.statut.startswith("Facture importée"):  # bloquée puis saisie ou importée plus tard
            ligne.statut = "Dans Sage"
            ligne.commentaire = " — ".join(x for x in (ligne.commentaire, "facture présente dans Sage depuis") if x)
    numeros = [l.facture for l in suivi.values() if l.facture]
    etat = etat_factures_sage(base, client, compte_depot, numeros) if numeros else {}
    recus_par_facture = {}
    for ligne in suivi.values():
        e = etat.get(ligne.facture)
        if not e:
            ligne.encaissement = "—" if ligne.statut != "Dans Sage" else "Non encaissée"
            continue
        du = e["du"]
        recus = [(j, m) for j, montants in e.get("recus", {}).items() for m in montants]
        recus_par_facture[ligne.facture] = recus
        total = ligne.ttc if ligne.ttc is not None else du + sum((m for _, m in recus), Decimal(0))
        if du <= 0:
            ligne.encaissement = "Encaissée" + (f" ({len(recus)} encaissement(s))" if len(recus) > 1 else "")
        elif recus:
            ligne.encaissement = f"Partielle : reste {argent(du)}"
        else:
            ligne.encaissement = "Non encaissée" if du >= total else f"Reste {argent(du)}"
    rapprocher_encaissements(racine, base, suivi, recus_par_facture)
    return sorted(suivi.values(), key=lambda l: (l.fin, l.traitement), reverse=True)


def rapprocher_encaissements(racine: Path, base, suivi: dict[str, LigneSuivi],
                             recus_par_facture: dict[str, list[tuple[date, Decimal]]]) -> None:
    """État du rapprochement : chaque encaissement de la facture retrouvé dans une écriture du compte 1055 reliée à
    un mouvement des relevés Desjardins chargés."""
    from datetime import timedelta

    from .rapprochement import RegistreReleves, mouvements_sage, periode_des, rapprocher

    releves = RegistreReleves(racine).lire() if recus_par_facture else []
    periode = periode_des(releves)
    rapproches: set[tuple[str, Decimal]] = set()
    if periode:
        banque = [m for r in releves for m in r.mouvements]
        sage = mouvements_sage(base, periode[0] - timedelta(days=7), periode[1] + timedelta(days=7))
        rapprocher(banque, sage)
        rapproches = {(s.date, _d(s.montant)) for s in sage if s.rapproche}
    for ligne in suivi.values():
        recus = recus_par_facture.get(ligne.facture)
        if not recus:
            continue
        couverts = [(j, m) for j, m in recus if periode and periode[0] <= j <= periode[1]]
        trouves = [(j, m) for j, m in couverts if (j.isoformat(), m) in rapproches]
        if not couverts:
            ligne.rapprochement = "Relevé non chargé"
        elif len(trouves) == len(recus):
            ligne.rapprochement = "Rapproché"
        elif trouves:
            ligne.rapprochement = f"En partie ({len(trouves)} sur {len(recus)})"
        else:
            ligne.rapprochement = "Non rapproché"


# --------------------------------------------------------------------------------------------- recherches Sage
def noms(base, table: str) -> list[str]:
    return [r["n"] for r in base.requete(f"SELECT TRIM(sName) n FROM {table} ORDER BY sName")]


def articles(base) -> list[str]:
    return [f"{r['c']} — {r['n']}" for r in base.requete(
        "SELECT TRIM(sPartCode) c, TRIM(sName) n FROM tinvent ORDER BY sPartCode")]


def _periode(colonne: str, du: date | None, au: date | None) -> tuple[str, list]:
    conditions, parametres = [], []
    if du:
        conditions.append(f"{colonne} >= %s")
        parametres.append(du.isoformat())
    if au:
        conditions.append(f"{colonne} < DATE_ADD(%s, INTERVAL 1 DAY)")
        parametres.append(au.isoformat())
    return "".join(f" AND {c}" for c in conditions), parametres


def mouvements_client(base, nom: str, du=None, au=None) -> tuple[list[str], list[list]]:
    filtre, p = _periode("d.dtDate", du, au)
    lignes = base.requete(
        "SELECT d.dtDate, d.nTranType, TRIM(t.sSource) f, TRIM(d.sSource) piece, d.dAmount FROM tcustrdt d "
        "JOIN tcustr t ON t.lId = d.lCusTrId JOIN tcustomr c ON c.lId = t.lCusId "
        "WHERE TRIM(c.sName) = %s AND d.bReversed = 0" + filtre + " ORDER BY d.dtDate, d.lId", [nom] + p)
    solde, resultat = Decimal(0), []
    for l in lignes:
        montant = _d(l["dAmount"])
        solde += montant
        resultat.append([_jour(l["dtDate"]), TYPES_CLIENT.get(l["nTranType"], f"Type {l['nTranType']}"), l["f"],
                         l["piece"] if l["piece"] != l["f"] else "", montant, solde])
    return ["Date", "Type", "Facture", "Pièce", "Montant", "Solde"], resultat


def mouvements_fournisseur(base, nom: str, du=None, au=None) -> tuple[list[str], list[list]]:
    filtre, p = _periode("d.dtDate", du, au)
    lignes = base.requete(
        "SELECT d.dtDate, d.nTranType, TRIM(t.sSource) f, TRIM(d.sSource) piece, d.dAmount FROM tventrdt d "
        "JOIN tventr t ON t.lId = d.lVenTrId JOIN tvendor v ON v.lId = t.lVenId "
        "WHERE TRIM(v.sName) = %s AND d.bReversed = 0" + filtre + " ORDER BY d.dtDate, d.lId", [nom] + p)
    solde, resultat = Decimal(0), []
    for l in lignes:
        montant = _d(l["dAmount"])
        solde += montant
        resultat.append([_jour(l["dtDate"]), TYPES_FOURNISSEUR.get(l["nTranType"], f"Type {l['nTranType']}"), l["f"],
                         l["piece"] if l["piece"] != l["f"] else "", montant, solde])
    return ["Date", "Type", "Facture", "Pièce", "Montant", "Solde dû"], resultat


def mouvements_article(base, code: str, du=None, au=None) -> tuple[list[str], list[list]]:
    filtre, p = _periode("r.dtJournal", du, au)
    lignes = base.requete(
        "SELECT r.dtJournal, r.nJournal, TRIM(r.sSource1) s, r.lVenCusId, l.dQty, l.dPrice, l.dAmt, "
        "c.sName client, v.sName fournisseur FROM titrline l JOIN titrec r ON r.lId = l.lITRecId "
        "JOIN tinvent i ON i.lId = l.lInventId "
        "LEFT JOIN tcustomr c ON r.nJournal = 8 AND c.lId = r.lVenCusId "
        "LEFT JOIN tvendor v ON r.nJournal IN (7, 17) AND v.lId = r.lVenCusId "
        "WHERE TRIM(i.sPartCode) = %s AND l.bVarLine = 0 AND r.bReversed = 0 AND r.bReversal = 0" + filtre +
        " ORDER BY r.dtJournal, r.lId, l.nLineNum", [code] + p)
    stock, resultat = Decimal(0), []
    for l in lignes:
        quantite = Decimal(str(l["dQty"] or 0)).quantize(Decimal("0.0001")).normalize()
        # sens du stock : une vente sort, un achat entre, un retour d'achat sort, un ajustement selon son signe
        entree = quantite if l["nJournal"] in (7, 12) else -quantite
        stock += entree
        tiers = (l["client"] or l["fournisseur"] or "").strip()
        resultat.append([_jour(l["dtJournal"]), JOURNAUX_ARTICLES.get(l["nJournal"], f"Journal {l['nJournal']}"),
                         l["s"], tiers, entree, _d(l["dPrice"]), _d(l["dAmt"]), stock])
    return ["Date", "Type", "Pièce", "Client / fournisseur", "Quantité (+ entrée / − sortie)", "Prix", "Montant",
            "Cumul"], resultat


def recherche_ventes(base, texte: str = "", du=None, au=None) -> tuple[list[str], list[list]]:
    filtre, p = _periode("t.dtDate", du, au)
    lignes = base.requete(
        "SELECT t.dtDate, TRIM(t.sSource) f, TRIM(c.sName) client, t.dPreTaxAmt m, "
        "(SELECT SUM(d.dAmount) FROM tcustrdt d WHERE d.lCusTrId = t.lId) du FROM tcustr t "
        "JOIN tcustomr c ON c.lId = t.lCusId WHERE t.nTranType = 0" + filtre + " ORDER BY t.dtDate DESC, t.lId DESC", p)
    return (["Date", "Facture", "Client", "Montant", "Solde dû"],
            _filtrer([[_jour(l["dtDate"]), l["f"], l["client"], _d(l["m"]), _d(l["du"])] for l in lignes], texte))


def recherche_encaissements(base, texte: str = "", du=None, au=None) -> tuple[list[str], list[list]]:
    filtre, p = _periode("d.dtDate", du, au)
    lignes = base.requete(
        "SELECT d.dtDate, TRIM(c.sName) client, TRIM(t.sSource) f, TRIM(d.sSource) piece, d.dAmount FROM tcustrdt d "
        "JOIN tcustr t ON t.lId = d.lCusTrId JOIN tcustomr c ON c.lId = t.lCusId WHERE d.nTranType = 1 "
        "AND d.bReversed = 0" + filtre +
        " ORDER BY d.dtDate DESC, d.lId DESC", p)
    return (["Date", "Client", "Facture", "N° d'encaissement", "Montant"],
            _filtrer([[_jour(l["dtDate"]), l["client"], l["f"], l["piece"], -_d(l["dAmount"])] for l in lignes], texte))


def recherche_paiements(base, texte: str = "", du=None, au=None) -> tuple[list[str], list[list]]:
    filtre, p = _periode("d.dtDate", du, au)
    lignes = base.requete(
        "SELECT d.dtDate, TRIM(v.sName) fournisseur, TRIM(t.sSource) f, TRIM(d.sSource) piece, d.dAmount, d.nTranType "
        "FROM tventrdt d JOIN tventr t ON t.lId = d.lVenTrId JOIN tvendor v ON v.lId = t.lVenId "
        "WHERE d.nTranType IN (1, 2) AND d.bReversed = 0" + filtre + " ORDER BY d.dtDate DESC, d.lId DESC", p)
    return (["Date", "Fournisseur", "Facture", "Pièce", "Montant"],
            _filtrer([[_jour(l["dtDate"]), l["fournisseur"], l["f"], l["piece"], -_d(l["dAmount"])] for l in lignes],
                     texte))


def _filtrer(lignes: list[list], texte: str) -> list[list]:
    """Lignes dont une colonne contient le texte (sans tenir compte des majuscules)."""
    texte = texte.strip().casefold()
    if not texte:
        return lignes
    return [l for l in lignes if any(texte in str(v).casefold() for v in l)]



# --------------------------------------------------------------------------------------------- historique en mémoire
def historique(base) -> dict:
    """Tout l'historique des clients et des fournisseurs lu en une fois (une seule ouverture de Sage) ; les
    recherches client, fournisseur, vente, encaissement et paiement se font ensuite en mémoire, sans attendre."""
    clients = base.requete(
        "SELECT d.dtDate, d.nTranType, TRIM(t.sSource) f, TRIM(d.sSource) piece, d.dAmount, TRIM(c.sName) nom "
        "FROM tcustrdt d JOIN tcustr t ON t.lId = d.lCusTrId JOIN tcustomr c ON c.lId = t.lCusId "
        "WHERE d.bReversed = 0 ORDER BY d.dtDate, d.lId")
    fournisseurs = base.requete(
        "SELECT d.dtDate, d.nTranType, TRIM(t.sSource) f, TRIM(d.sSource) piece, d.dAmount, TRIM(v.sName) nom "
        "FROM tventrdt d JOIN tventr t ON t.lId = d.lVenTrId JOIN tvendor v ON v.lId = t.lVenId "
        "WHERE d.bReversed = 0 ORDER BY d.dtDate, d.lId")
    ventes = base.requete(
        "SELECT t.dtDate, TRIM(t.sSource) f, TRIM(c.sName) client, t.dPreTaxAmt m, "
        "(SELECT SUM(d.dAmount) FROM tcustrdt d WHERE d.lCusTrId = t.lId) du FROM tcustr t "
        "JOIN tcustomr c ON c.lId = t.lCusId WHERE t.nTranType = 0 ORDER BY t.dtDate DESC, t.lId DESC")
    for liste in (clients, fournisseurs, ventes):
        for l in liste:
            l["jour"] = l["dtDate"].date() if hasattr(l["dtDate"], "date") else l["dtDate"]
    return {"clients": clients, "fournisseurs": fournisseurs, "ventes": ventes,
            "noms_clients": noms(base, "tcustomr"), "noms_fournisseurs": noms(base, "tvendor")}


def _dans(l: dict, du, au) -> bool:
    return (du is None or l["jour"] >= du) and (au is None or l["jour"] <= au)


def _mouvements(lignes: list[dict], types: dict, nom: str, du, au) -> list[list]:
    solde, resultat = Decimal(0), []
    for l in lignes:
        if l["nom"] != nom or not _dans(l, du, au):
            continue
        montant = _d(l["dAmount"])
        solde += montant
        resultat.append([_jour(l["dtDate"]), types.get(l["nTranType"], f"Type {l['nTranType']}"), l["f"],
                         l["piece"] if l["piece"] != l["f"] else "", montant, solde])
    return resultat


def h_mouvements_client(h: dict, nom: str, du=None, au=None):
    return ["Date", "Type", "Facture", "Pièce", "Montant", "Solde"], _mouvements(h["clients"], TYPES_CLIENT, nom, du, au)


def h_mouvements_fournisseur(h: dict, nom: str, du=None, au=None):
    return (["Date", "Type", "Facture", "Pièce", "Montant", "Solde dû"],
            _mouvements(h["fournisseurs"], TYPES_FOURNISSEUR, nom, du, au))


def h_ventes(h: dict, texte: str = "", du=None, au=None):
    return (["Date", "Facture", "Client", "Montant", "Solde dû"],
            _filtrer([[_jour(l["dtDate"]), l["f"], l["client"], _d(l["m"]), _d(l["du"])]
                      for l in h["ventes"] if _dans(l, du, au)], texte))


def h_encaissements(h: dict, texte: str = "", du=None, au=None):
    return (["Date", "Client", "Facture", "N° d'encaissement", "Montant"],
            _filtrer([[_jour(l["dtDate"]), l["nom"], l["f"], l["piece"], -_d(l["dAmount"])]
                      for l in reversed(h["clients"]) if l["nTranType"] == 1 and _dans(l, du, au)], texte))


def h_paiements(h: dict, texte: str = "", du=None, au=None):
    return (["Date", "Fournisseur", "Facture", "Pièce", "Montant"],
            _filtrer([[_jour(l["dtDate"]), l["nom"], l["f"], l["piece"], -_d(l["dAmount"])]
                      for l in reversed(h["fournisseurs"]) if l["nTranType"] in (1, 2) and _dans(l, du, au)], texte))
