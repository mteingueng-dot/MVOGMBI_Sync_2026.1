"""Traitement automatique de nuit : tous les jours sans facture dans Sage, de la date de départ jusqu'à hier ; une
facture par jour du lundi au jeudi et une seule pour le vendredi, le samedi et le dimanche (préparée après le dimanche).

Étapes (sans intervention) :
1. Lecture de Sage : factures « Vente AAAA-MM-JJ » du client (seulement celles dont la date dans Sage correspond au
   numéro : une ancienne facture mal numérotée est signalée et ignorée), articles, comptes, réglage du client.
   Si Sage est fermé, la base est ouverte par l'outil d'import, lue, puis la connexion est annulée.
2. Correspondance des articles mise à jour (nouveaux articles Clover : reliés si le nom est identique).
3. Préparation des factures des jours manquants, du plus ancien au plus récent (règles du propriétaire du
   2026-10-27) : les trous laissés par une nuit précédente passent donc en premier. Un jour qui pose problème
   (article non relié, compte manquant…) est bloqué seul ; pour le vendredi, le samedi ou le dimanche, c'est toute la
   fin de semaine. Les autres jours continuent ; le jour bloqué est repris à la prochaine exécution.
4. Import des factures prêtes par lots ; mot de passe saisi et résumé fermé automatiquement ; présence de chaque
   facture vérifiée dans Sage.
5. Encaissements : seulement les ventes importées pendant cette exécution (un jour bloqué n'est jamais encaissé).
6. Journal et courriel de compte rendu (une pièce jointe Excel par module).
"""

from __future__ import annotations

import csv
import re
import shutil
import traceback
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from . import coffre
from .correspondance import memoriser_a_relier
from .periodes import jours as jours_periode

MOTIF_FACTURE = re.compile(r"^Vente (\d{4}-\d{2}-\d{2})(/\d{2})?$")


@dataclass
class EtatSage:
    dates_factures: set[date]
    client_configure: bool | None
    articles: list            # ArticleSage
    invisibles: dict[str, str]
    incoherentes: list[str] = field(default_factory=list)  # « Vente 2026-06-07 » datée du 2025-06-07 dans Sage

    @property
    def derniere_date(self) -> date | None:
        return max(self.dates_factures) if self.dates_factures else None


# États d'une date traitée (repris dans le courriel de compte rendu)
IMPORTEE = "Facture importée"
PRETE = "Facture prête (simulation)"
AUCUNE_VENTE = "Aucune vente"
DEJA_PRESENTE = "Facture déjà présente dans Sage"
BLOQUEE = "Bloquée"
REPORTEE = "Reportée à la prochaine exécution"
ECHEC = "Échec de l'import"


@dataclass
class EtatJour:
    jour: date
    etat: str
    detail: str = ""
    lignes: int = 0
    sous_total: Decimal = Decimal("0")
    taxes: Decimal = Decimal("0")
    total: Decimal = Decimal("0")
    debut: date | None = None   # premier jour de la facture (vendredi pour la fin de semaine)
    numero: str = ""            # n° de la facture (historique des ventes, page Rapports)
    point_vente: str = "1"      # code du point de vente Clover (points_vente.py)


@dataclass
class CompteRendu:
    debut: datetime = field(default_factory=datetime.now)
    lignes: list[str] = field(default_factory=list)
    importees: list[str] = field(default_factory=list)
    problemes: list[str] = field(default_factory=list)
    erreur: str = ""
    fichier: str = ""
    derniere_avant: date | None = None   # dernière facture journalière trouvée dans Sage au départ
    periode: tuple[date, date] | None = None
    jours: list[EtatJour] = field(default_factory=list)
    simulation: bool = False
    numeros_importes: list[str] = field(default_factory=list)  # factures importées pendant cette exécution
    encaissements: list[str] = field(default_factory=list)  # dépôts encaissés par le robot
    notes_encaissements: list[str] = field(default_factory=list)
    notes_paiements: list[str] = field(default_factory=list)
    seulement_encaissements: bool = False  # compte rendu du bouton « Encaisser dans Sage » (sans import)
    paiements: list[str] = field(default_factory=list)  # paiements fournisseurs saisis par le robot
    seulement_paiements: bool = False  # compte rendu du bouton « Payer dans Sage » (sans import)

    def note(self, texte: str) -> None:
        horodate = f"{datetime.now():%H:%M:%S} {texte}"
        self.lignes.append(horodate)
        print(horodate, flush=True)

    @property
    def succes(self) -> bool:
        return not self.erreur and not self.problemes


def lire_etat_sage(base, client: str, prefixe: str = "Vente", articles: list | None = None,
                   invisibles: dict | None = None) -> EtatSage:
    lignes = base.requete(
        "SELECT TRIM(t.sSource) s, t.dtDate d FROM tcustr t JOIN tcustomr c ON c.lId = t.lCusId "
        "WHERE c.sName = %s AND TRIM(t.sSource) REGEXP %s",
        (client, "^" + re.escape(prefixe) + r" [0-9]{4}-[0-9]{2}-[0-9]{2}(/[0-9]{2})?$"))
    dates, incoherentes = jours_couverts_sage(lignes, prefixe)
    return EtatSage(dates, base.client_utilise_mes_articles(client), base.articles() if articles is None else articles,
                    base.numeros_avec_caracteres_invisibles() if invisibles is None else invisibles, incoherentes)


def jours_couverts_sage(lignes: list[dict], prefixe: str = "Vente") -> tuple[set[date], list[str]]:
    """Jours couverts par les factures {"s": n°, "d": date dans Sage} : factures journalières et de fin de semaine
    (vendredi au dimanche). Une facture dont la date dans Sage n'est pas le dernier jour de son numéro (faute de
    frappe, ex. « Vente 2026-06-07 » datée du 2025-06-07) ne couvre rien : elle est renvoyée à part."""
    from .facture import jours_facture

    dates, incoherentes = set(), []
    for l in lignes:
        jours = jours_facture(l["s"], prefixe)
        jour_sage = l["d"].date() if hasattr(l["d"], "date") else l["d"]
        if not jours:
            continue
        if jour_sage is not None and jour_sage != jours[-1]:
            incoherentes.append(f"{l['s']} (datée du {jour_sage} dans Sage)")
            continue
        dates.update(jours)
    return dates, sorted(incoherentes)


def blocage_depot(point_vente, depots_sage: list[str] | None, config_toml: dict) -> str:
    """Raison qui empêche d'importer les factures d'un point de vente dans son dépôt Sage ; « » si rien.

    Le fichier d'import de Sage n'a pas de champ d'emplacement connu : les lignes vont dans l'emplacement par défaut.
    Un autre dépôt reste bloqué tant que [sage_import] depots_valides n'est pas vrai (essai sur la copie d'abord)."""
    depot = point_vente.depot_sage.strip()
    if depots_sage is not None and depot.lower() not in {d.lower() for d in depots_sage}:
        return (f"dépôt Sage « {depot} » introuvable (Sage : Configuration > Paramètres > Stocks et services > "
                "Emplacements)")
    if not point_vente.depot_par_defaut and not config_toml.get("sage_import", {}).get("depots_valides", False):
        return (f"dépôt Sage « {depot} » : l'import dans un autre emplacement que « Emplacement par défaut » doit "
                "d'abord être validé sur la copie d'essai")
    return ""


def executer_automatique(racine: Path, config_toml: dict, jusqua: date | None = None,
                         simulation: bool = False, depuis: date | None = None,
                         point_vente: str | None = None) -> CompteRendu:
    """`depuis` : période choisie par le propriétaire (bouton « Charger la période ») au lieu de « dernière facture de
    Sage + 1 jour » ; les jours déjà facturés sont sautés. `point_vente` : code d'un point de vente, ou « tous »
    (défaut) : chacun est traité à la suite avec son client, son préfixe et son dépôt Sage."""
    from .__main__ import config_import, executable_import, ouvrir_base_sage
    from .articles_sage import ecrire_copie
    from .import_sage import ecrire_imp
    from .points_vente import choisir, problemes_configuration
    from .sage_auto import lire_pendant_connexion

    cr = CompteRendu(simulation=simulation)
    c_import = config_toml.get("sage_import", {})
    c_auto = config_toml.get("automatique", {})
    fichier_sai = Path(c_import.get("fichier_entreprise", ""))
    if not fichier_sai.is_file():
        raise RuntimeError(f"Fichier d'entreprise Sage introuvable : {fichier_sai}")
    exe = Path(c_import["executable"]) if c_import.get("executable") else executable_import()
    if not exe or not exe.is_file():
        raise RuntimeError("Outil d'import de Sage (Sage_SA_import.exe) introuvable.")
    mot_de_passe = coffre.lire(coffre.SAGE_IMPORT)
    points = choisir(config_toml, point_vente)
    if erreurs := problemes_configuration(points):
        cr.problemes += erreurs
        return cr

    # 1. Lecture de Sage (une seule fois pour tous les points de vente) --------------------------------------
    cr.note(f"Lecture de Sage ({fichier_sai.name})…")

    def lecture():
        with ouvrir_base_sage(config_toml, fichier_sai) as base:
            articles, invisibles = base.articles(), base.numeros_avec_caracteres_invisibles()
            try:
                depots = base.depots()
            except Exception:  # droit de lecture absent sur tinvloc : seul le nom du dépôt n'est pas contrôlé
                depots = None
            return {p.code: lire_etat_sage(base, p.client_sage, p.prefixe, articles, invisibles) for p in points}, depots

    try:
        etats, depots_sage = lecture()  # Sage déjà ouvert sur ce fichier
        sage_ouvert = True
    except Exception:
        etats, depots_sage = lire_pendant_connexion(exe, fichier_sai, lecture)
        sage_ouvert = False
    ecrire_copie(etats[points[0].code].articles, racine / "donnees" / "articles_sage.csv")
    cr.fichier = fichier_sai.name

    pretes = []
    for pdv in points:
        if len(points) > 1:
            cr.note(f"——— Point de vente {pdv.libelle} (client « {pdv.client_sage} », dépôt « {pdv.depot_sage} ») ———")
        pretes += _preparer_point_vente(racine, config_toml, pdv, etats[pdv.code], depots_sage, cr, jusqua, depuis)

    if not pretes:
        cr.note("Aucune facture prête à importer.")
        return cr
    taille = max(1, int(c_auto.get("factures_par_import", 25)))
    lots = [pretes[k:k + taille] for k in range(0, len(pretes), taille)]
    if simulation:
        for lot in lots:
            chemin_imp = ecrire_imp(lot, chemin_lot(racine, lot), config_import(config_toml))
            cr.note(f"Simulation : {len(lot)} facture(s) prête(s) dans {chemin_imp}, aucun import.")
        return cr

    # 4. Import par lots et vérification -----------------------------------------------------------------------
    for numero_lot, lot in enumerate(lots, 1):
        chemin_imp = ecrire_imp(lot, chemin_lot(racine, lot), config_import(config_toml))
        cr.note(f"Import de {len(lot)} facture(s) dans {fichier_sai.name}"
                + (f" (lot {numero_lot} sur {len(lots)})" if len(lots) > 1 else "") + "…")
        importer_lot(racine, lot, chemin_imp, exe, fichier_sai, mot_de_passe, config_toml, sage_ouvert, cr)
    cr.note(f"{len(cr.importees)} facture(s) importée(s) et vérifiée(s) dans Sage.")
    # 5. Encaissements des seules ventes importées pendant cette exécution
    importees = [imp.facture.numero for imp in pretes if imp.facture.numero in cr.numeros_importes]
    encaisser_depots(racine, config_toml, cr, importees)
    payer_fournisseurs(racine, config_toml, cr)
    return cr


def _preparer_point_vente(racine: Path, config_toml: dict, pdv, etat: EtatSage, depots_sage: list[str] | None,
                          cr: CompteRendu, jusqua: date | None, depuis: date | None) -> list:
    """Étapes 2 et 3 pour un point de vente : correspondance de ses articles, puis ses factures des jours manquants.
    Renvoie les factures prêtes à importer."""
    from .__main__ import charger_config
    from .api_clover import ClientClover
    from .facture import numero_fin_de_semaine, preparer_facture
    from .import_sage import preparer_import
    from .periodes import TypePeriode, dimanche, est_fin_de_semaine

    donnees = pdv.dossier(racine / "donnees")
    donnees.mkdir(parents=True, exist_ok=True)
    hier = date.today() - timedelta(days=1)
    fin = min(jusqua or hier, hier)
    date_depart = date.fromisoformat(str(config_toml.get("automatique", {}).get("date_depart", fin.isoformat())))
    # tous les jours sans facture depuis la date de départ (les trous d'abord, puisque du plus ancien au plus récent)
    debut = plancher = date_depart
    if depuis:  # un samedi ou un dimanche choisi : la facture de fin de semaine commence le vendredi
        debut = plancher = depuis - timedelta(days=max(0, depuis.weekday() - 4))
    if pdv.principal:
        cr.derniere_avant = etat.derniere_date
    for texte in etat.incoherentes:
        cr.note(f"Facture ignorée : {texte} ; son numéro ne correspond pas à sa date (à corriger dans Sage).")
    manquants = [j for j in jours_periode(debut, fin) if j not in etat.dates_factures] if debut <= fin else []
    if manquants and (cr.periode is None or manquants[0] < cr.periode[0]):
        cr.periode = (manquants[0], fin)
    cr.note(f"Dernière facture journalière dans Sage : {etat.derniere_date or 'aucune'} ; "
            f"{len(manquants)} jour(s) sans facture du {debut} au {fin} : {resumer_jours(manquants)}" if manquants else
            ("Période choisie : rien à importer." if depuis else "Sage est à jour : rien à importer."))
    if not manquants:
        return []
    if not etat.client_configure:
        cr.problemes.append(f"Fiche client « {pdv.client_sage} » : "
                            + ("client absent de Sage (à créer)." if etat.client_configure is None else
                               "cocher « Ce client utilise mes n° articles » (onglet Importer/Exporter), sinon Sage "
                               "ne reconnaît aucun article."))
        return []
    if raison := blocage_depot(pdv, depots_sage, config_toml):
        cr.problemes.append(f"Point de vente {pdv.libelle} : {raison}.")
        return []

    # 2. Correspondance des articles ----------------------------------------------------------------------
    client = ClientClover(charger_config(racine / "config.toml", pdv))
    table = mettre_a_jour_correspondance(client, etat.articles, donnees, cr)
    comptes = {a.numero: a.compte_revenus for a in etat.articles}

    # 3. Préparation : une facture par jour du lundi au jeudi, une seule du vendredi au dimanche ----------------
    pretes = []
    jour = manquants[0]
    while jour <= fin:
        if jour in etat.dates_factures:  # déjà facturé : on passe au jour suivant
            jour += timedelta(days=1)
            continue
        fin_bloc, type_facture = jour, TypePeriode.JOUR
        if est_fin_de_semaine(jour):
            # une seule facture du vendredi au dimanche (le dépôt du lundi couvre les trois jours)
            vendredi = jour - timedelta(days=jour.weekday() - 4)
            jour = max(vendredi, plancher)
            fin_bloc, type_facture = dimanche(jour), TypePeriode.FIN_DE_SEMAINE
            if fin_bloc > fin:  # la fin de semaine n'est pas terminée : facture préparée après le dimanche
                cr.note(f"{jour} : ventes de fin de semaine, facturées ensemble après le dimanche {fin_bloc}.")
                cr.jours.append(EtatJour(jour, REPORTEE, f"facture du vendredi au dimanche après le {fin_bloc}",
                                         point_vente=pdv.code))
                break
            if any(j in etat.dates_factures for j in jours_periode(vendredi, fin_bloc)):
                cr.problemes.append(f"{jour} : une partie de la fin de semaine est déjà facturée dans Sage ; "
                                    "facturer le reste à la main ou supprimer la facture partielle.")
                cr.jours.append(EtatJour(fin_bloc, BLOQUEE, "fin de semaine en partie déjà facturée", debut=jour,
                                         numero=numero_fin_de_semaine(jour, fin_bloc, pdv.prefixe),
                                         point_vente=pdv.code))
                jour = fin_bloc + timedelta(days=1)  # seule cette fin de semaine est bloquée
                continue
        rapport = client.rapport(jour, fin_bloc)
        if not rapport.lignes:
            cr.note(f"{jour} : aucune vente." if fin_bloc == jour else f"du {jour} au {fin_bloc} : aucune vente.")
            cr.jours.append(EtatJour(fin_bloc, AUCUNE_VENTE, debut=jour, point_vente=pdv.code))
            jour = fin_bloc + timedelta(days=1)
            continue
        facture = preparer_facture(rapport, type_facture, pdv)
        jour_etat = fin_bloc  # état repris par la date de la facture (le dimanche pour la fin de semaine)
        imp = preparer_import(facture, table)
        if imp.ids_non_relies:  # proposés à la page Correspondance dès la prochaine mise à jour (même supprimés)
            memoriser_a_relier(donnees / "articles_a_relier.csv", imp.ids_non_relies)
        blocages = [f"article Clover non relié à Sage : {n}" for n in imp.non_reliees] + list(facture.anomalies)
        if imp.sous_total != rapport.total_net:
            blocages.append(f"écart de {rapport.total_net - imp.sous_total:.2f} $ avec les ventes Clover")
        numeros = {l.numero_sage for l in imp.lignes}
        blocages += [f"article Sage sans compte de produits : {n}" for n in sorted(numeros) if not comptes.get(n)]
        blocages += [f"numéro d'article Sage avec caractères invisibles (à retaper) : {n}"
                     for n in sorted(numeros & set(etat.invisibles))]
        for texte in facture.avertissements:
            cr.note(f"{jour} : (info) {texte}")
        if blocages:  # seul ce jour (ou cette fin de semaine) est bloqué ; les autres continuent
            cr.problemes += [f"{facture.numero} : {b}" for b in blocages]
            cr.note(f"{facture.numero} : facture NON préparée ({len(blocages)} problème(s)) ; elle sera reprise à la "
                    "prochaine exécution, les autres jours continuent.")
            cr.jours.append(EtatJour(jour_etat, BLOQUEE, " ; ".join(blocages), len(imp.lignes), imp.sous_total,
                                     imp.total_taxes, imp.total, debut=jour, numero=facture.numero,
                                     point_vente=pdv.code))
            jour = fin_bloc + timedelta(days=1)
            continue
        pretes.append(imp)
        detail = "" if fin_bloc == jour else f"ventes du {jour} au {fin_bloc}"
        cr.jours.append(EtatJour(jour_etat, PRETE, detail, len(imp.lignes), imp.sous_total, imp.total_taxes, imp.total,
                                 debut=jour, numero=facture.numero, point_vente=pdv.code))
        cr.note(f"{facture.numero} : {len(imp.lignes)} lignes, sous-total {imp.sous_total:,.2f} $, "
                f"total {imp.total:,.2f} $")
        jour = fin_bloc + timedelta(days=1)
    return pretes


def resumer_jours(jours: list[date]) -> str:
    """« 2026-02-01 → 2026-02-28, 2026-03-05 » : suites de jours consécutifs regroupées."""
    morceaux, i = [], 0
    while i < len(jours):
        k = i
        while k + 1 < len(jours) and jours[k + 1] == jours[k] + timedelta(days=1):
            k += 1
        morceaux.append(str(jours[i]) if k == i else f"{jours[i]} → {jours[k]}")
        i = k + 1
    return ", ".join(morceaux[:12]) + (f" (+{len(morceaux) - 12} autres)" if len(morceaux) > 12 else "")


def chemin_lot(racine: Path, lot: list) -> Path:
    return racine / "sortie" / "factures" / f"Auto_{lot[0].facture.date_facture}_au_{lot[-1].facture.date_facture}.IMP"


def importer_lot(racine: Path, lot: list, chemin_imp: Path, exe: Path, fichier_sai: Path, mot_de_passe: str,
                 config_toml: dict, sage_ouvert: bool, cr: CompteRendu) -> None:
    """Un lot de factures : import, vérification de chaque facture dans Sage, journal des imports."""
    from .__main__ import ouvrir_base_sage
    from .sage_auto import executer

    presentes: dict[str, bool] = {}

    def verifier(_resume: str = "") -> None:
        for _ in range(10):
            try:
                with ouvrir_base_sage(config_toml, fichier_sai) as base:
                    for imp in lot:
                        presentes[imp.facture.numero] = base.facture_existe(imp.facture.numero, imp.facture.client)
                return
            except Exception:
                import time
                time.sleep(1)

    resultat = executer(exe, chemin_imp, fichier_sai, mot_de_passe, pendant_resume=verifier,
                        delai=int(config_toml.get("automatique", {}).get("delai_import", 3600)))
    if not presentes and sage_ouvert:
        verifier()
    for texte in resultat.erreurs:
        cr.problemes.append(f"Sage : {texte}")
    journal = racine / "donnees" / "journal_imports.csv"
    nouveau = not journal.exists()
    with journal.open("a", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        if nouveau:
            w.writerow(["Date et heure", "Facture", "Fichier d'entreprise", "Lignes", "Sous-total", "Total",
                        "Code de retour", "Résultat"])
        etats = {e.numero: e for e in cr.jours if e.numero}  # n° unique, même avec plusieurs points de vente
        for imp in lot:
            ok = presentes.get(imp.facture.numero)
            statut = "importée" if ok else ("non vérifiable" if ok is None else "ÉCHEC")
            e = etats[imp.facture.numero]
            e.etat = IMPORTEE if ok else ECHEC
            if not ok:
                e.detail = f"{statut} après l'import ; " + " ; ".join(resultat.erreurs)
            w.writerow([f"{datetime.now():%Y-%m-%d %H:%M:%S}", imp.facture.numero, fichier_sai.name, len(imp.lignes),
                        f"{imp.sous_total:.2f}", f"{imp.total:.2f}", resultat.code_retour, statut])
            if ok:
                cr.importees.append(f"{imp.facture.numero} : {imp.total:,.2f} $")
                cr.numeros_importes.append(imp.facture.numero)
            else:
                cr.problemes.append(f"{imp.facture.numero} : {statut} après l'import")


def encaisser_depots(racine: Path, config_toml: dict, cr: CompteRendu, factures: list[str] | None = None) -> None:
    """5. Encaissements : le robot ouvre Sage sur un bureau caché (fonctionne session verrouillée), encaisse les
    dépôts sur les factures, vérifie dans la base, puis referme Sage. `factures` : seules les ventes importées
    pendant cette exécution sont encaissées (règle du propriétaire) ; liste vide = aucun encaissement."""
    import json
    import tempfile

    from .__main__ import commande_moteur
    from .sage_bureau import executer_sur_bureau_cache

    if not config_toml.get("encaissements", {}).get("automatique", True):
        return
    if factures is not None and not factures:
        cr.note("Encaissements : aucune vente importée pendant cette exécution, rien à encaisser.")
        return
    cr.note("Encaissements des ventes importées…" if factures else "Encaissements des dépôts Clover…")
    with tempfile.TemporaryDirectory() as dossier:
        fichier = Path(dossier) / "bilan.json"
        commande = commande_moteur() + ["encaisser-bureau", "--resultat", str(fichier)]
        if factures:
            liste = Path(dossier) / "factures.json"
            liste.write_text(json.dumps(factures, ensure_ascii=False), encoding="utf-8")
            commande += ["--factures", str(liste)]
        code = executer_sur_bureau_cache(commande, racine,
                                         delai=int(config_toml.get("encaissements", {}).get("delai", 1800)))
        bilan = json.loads(fichier.read_text(encoding="utf-8")) if fichier.exists() else {}
    for note in bilan.get("notes", []):
        cr.note(f"  {note}")
        cr.notes_encaissements.append(note)
    cr.encaissements += bilan.get("encaisses", [])
    cr.problemes += [f"Encaissement : {p}" for p in bilan.get("a_verifier", [])]
    if bilan.get("erreur"):
        cr.problemes.append(f"Encaissements non faits : {bilan['erreur']}")
    elif code == -1:
        cr.problemes.append("Encaissements : le traitement n'a pas terminé dans le délai ; Sage a été arrêté.")
    cr.note(f"{len(cr.encaissements)} dépôt(s) encaissé(s) dans Sage.")


def payer_fournisseurs(racine: Path, config_toml: dict, cr: CompteRendu) -> None:
    """6. Paiements fournisseurs confirmés par le propriétaire (page 9) : le robot les saisit dans la fenêtre
    Paiements de Sage (bureau caché), vérifie le solde de chaque facture, puis referme Sage."""
    import json
    import tempfile

    from .__main__ import commande_moteur
    from .paiements_fournisseurs import CONFIRME, RegistrePaiements
    from .sage_bureau import executer_sur_bureau_cache

    if not config_toml.get("paiements", {}).get("automatique", True):
        return
    if not any(p.etat == CONFIRME for p in RegistrePaiements(racine).paiements):
        return
    cr.note("Paiements fournisseurs confirmés…")
    with tempfile.TemporaryDirectory() as dossier:
        fichier = Path(dossier) / "bilan.json"
        code = executer_sur_bureau_cache(commande_moteur() + ["payer-bureau", "--resultat", str(fichier)],
                                         racine, delai=int(config_toml.get("paiements", {}).get("delai", 1800)))
        bilan = json.loads(fichier.read_text(encoding="utf-8")) if fichier.exists() else {}
    for note in bilan.get("notes", []):
        cr.note(f"  {note}")
        cr.notes_paiements.append(note)
    cr.paiements += bilan.get("payes", [])
    cr.problemes += [f"Paiement fournisseur : {p}" for p in bilan.get("a_verifier", [])]
    if bilan.get("erreur"):
        cr.problemes.append(f"Paiements fournisseurs non faits : {bilan['erreur']}")
    elif code == -1:
        cr.problemes.append("Paiements fournisseurs : le traitement n'a pas terminé dans le délai ; Sage a été arrêté.")
    cr.note(f"{len(cr.paiements)} paiement(s) fournisseur(s) saisi(s) dans Sage.")


def mettre_a_jour_correspondance(client, articles_sage: list, donnees: Path, cr: CompteRendu):
    """Met à jour la correspondance avec le catalogue Clover ; renvoie la table utilisée pour les factures.

    Les confirmations du propriétaire sont conservées ; un nouvel article Clover dont le nom est identique
    à un article Sage est relié automatiquement ; les cas douteux restent « À confirmer » (le jour où un tel
    article est vendu, le traitement s'arrête et l'alerte demande de le confirmer dans le fichier).
    """
    from .api_clover import SANS_CATEGORIE
    from .correspondance import (AUTOMATIQUE, CONFIRME, PREFIXE_SANS_ID, ArticleClover, Correspondance,
                                 ecrire_correspondance, lire_a_relier, lire_confirmes, proposer_renommes, rapprocher)
    from .import_sage import TableCorrespondance, cle_nom

    import openpyxl

    chemin = donnees / "correspondance_articles.xlsx"
    confirmes = lire_confirmes(chemin)
    anciennes_ventes: dict[str, Decimal] = {}
    anciens_statuts: dict[str, str] = {}
    if chemin.exists():
        feuille = openpyxl.load_workbook(chemin, read_only=True, data_only=True)["Correspondance"]
        lignes = feuille.iter_rows(values_only=True)
        entete = list(next(lignes))
        i_id, i_v, i_s = entete.index("ID Clover"), entete.index("Ventes 30 j ($)"), entete.index("Statut")
        for r in lignes:
            if r[i_id]:
                anciennes_ventes[str(r[i_id])] = Decimal(str(r[i_v] or 0))
                anciens_statuts[str(r[i_id])] = str(r[i_s] or "")

    catalogue = client.articles()
    ids = {a["id"] for a in catalogue}
    absents: set[str] = set()
    for id_article, nom, numero_sage in lire_a_relier(donnees / "articles_a_relier.csv"):
        if numero_sage:  # numéro Sage inscrit par le propriétaire : correspondance confirmée
            confirmes[id_article] = Correspondance(CONFIRME, nom, "", Decimal("0"), numero_sage, "", "",
                                                   "Manuel (articles_a_relier)", 100, "", "", id_article)
        if id_article not in ids:  # vendu puis supprimé (ou renommé) dans Clover
            a = ({} if id_article.startswith(PREFIXE_SANS_ID) else client.article(id_article)) or {"id": id_article}
            a["name"] = a.get("name") or nom
            catalogue.append(a)
            ids.add(id_article)
            absents.add(id_article)
    clover = [
        ArticleClover(
            id=a["id"], nom=(a.get("name") or "").strip(),
            categorie=(((a.get("categories") or {}).get("elements") or [{}])[0]).get("name", SANS_CATEGORIE),
            code=(a.get("code") or "").strip(), ventes_30j=anciennes_ventes.get(a["id"], Decimal("0")),
        )
        for a in catalogue
    ]
    resultat = rapprocher(clover, articles_sage, confirmes, absents)
    if proposes := proposer_renommes(resultat, absents):
        cr.note(f"{proposes} article(s) vendu(s) puis supprimé(s) ou renommé(s) dans Clover : nouveau nom proposé, "
                "à confirmer à la page Correspondance (filtre « Supprimés ou renommés dans Clover »).")
    nouveaux = [c for c in resultat if c.id_clover not in anciens_statuts]
    changes = [c for c in resultat if anciens_statuts.get(c.id_clover, c.statut) != c.statut]
    if nouveaux or changes or not chemin.exists():
        try:
            if chemin.exists():
                copie = chemin.parent / "sauvegardes" / f"{chemin.stem}_{datetime.now():%Y%m%d-%H%M%S}{chemin.suffix}"
                copie.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(chemin, copie)
            ecrire_correspondance(resultat, chemin)
            cr.note(f"Correspondance mise à jour : {len(nouveaux)} nouvel(s) article(s) Clover, "
                    f"{len(changes)} statut(s) modifié(s).")
        except PermissionError:
            cr.note("Correspondance non enregistrée (fichier ouvert dans Excel) : table utilisée en mémoire.")
    a_confirmer = [c for c in nouveaux if c.statut not in (CONFIRME, AUTOMATIQUE)]
    if not anciens_statuts and a_confirmer:
        # Premier fichier de correspondance : un résumé plutôt qu'une ligne par article
        cr.note(f"Fichier de correspondance créé : {len(a_confirmer)} article(s) Clover à confirmer "
                "(page Correspondance). Si vous aviez déjà une correspondance validée, reprenez-la "
                "(page Automatisation > « Reprendre une configuration existante »).")
    else:
        for c in a_confirmer:
            cr.note(f"Nouvel article Clover à confirmer : {c.nom_clover} ({c.statut})")
    table = TableCorrespondance({}, {})
    for c in resultat:
        if c.statut in (CONFIRME, AUTOMATIQUE) and c.numero_sage:
            table.par_id[c.id_clover] = c.numero_sage
            table.par_nom.setdefault(cle_nom(c.nom_clover), c.numero_sage)
    return table


def ecrire_journal(racine: Path, cr: CompteRendu) -> Path:
    from .rapports import noter_historique

    try:
        noter_historique(racine, cr)  # suivi des ventes de la page Rapports
    except OSError:
        pass
    chemin = racine / "donnees" / "journal_automatique.log"
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with chemin.open("a", encoding="utf-8") as f:
        f.write(f"\n===== Exécution du {cr.debut:%Y-%m-%d %H:%M:%S} =====\n")
        f.write("\n".join(cr.lignes) + "\n")
        for p in cr.problemes:
            f.write(f"PROBLÈME : {p}\n")
        if cr.erreur:
            f.write(f"ERREUR : {cr.erreur}\n")
    return chemin


def recevoir_factures_fournisseurs(racine: Path, config_toml: dict, cr: CompteRendu) -> None:
    """Factures fournisseurs jointes aux courriels de la boîte configurée : copiées et lues pour la page 8 (rien
    n'est importé sans le propriétaire). Une erreur ici ne touche pas le traitement."""
    from .factures_courriel import configuree, lire_nouvelles, recuperer

    if not configuree(config_toml) or not config_toml.get("factures_courriel", {}).get("automatique", True):
        return
    try:
        crees = recuperer(racine, config_toml)
        lues = lire_nouvelles(racine) if crees else []
        if lues:
            cr.note(f"{len(lues)} facture(s) fournisseur(s) reçue(s) par courriel, à vérifier à la page "
                    "« 8. Factures fournisseurs » : " + ", ".join(f.fichier for f in lues))
    except Exception as exc:
        cr.note(f"Factures fournisseurs du courriel non relevées : {exc}")


def archiver_factures_deja_dans_sage(racine: Path, config_toml: dict, cr: CompteRendu) -> None:
    """Factures fournisseurs « Prête à importer » déjà saisies dans Sage : archivées et retirées de la liste
    (règle du propriétaire du 2026-10-28)."""
    from .fournisseurs import PRETE, Registre, archiver_pretes_deja_dans_sage

    if not any(f.etat == PRETE for f in Registre(racine).factures):
        return
    try:
        from .__main__ import lire_sage

        archivees = lire_sage(config_toml, lambda base: archiver_pretes_deja_dans_sage(racine, base),
                              config_toml.get("sage_import", {}).get("fichier_entreprise"))
        if archivees:
            cr.note(f"{len(archivees)} facture(s) fournisseur(s) déjà dans Sage, archivée(s) et retirée(s) de la "
                    "page 8 : " + ", ".join(f"{f.fournisseur_sage} n° {f.numero}" for f in archivees))
    except Exception as exc:
        cr.note(f"Factures fournisseurs déjà dans Sage non vérifiées : {exc}")


def prechauffer_statistiques(racine: Path, cr: CompteRendu) -> None:
    """Statistiques Clover (page Rapports) : les 7 derniers jours sont gardés dans le cache chaque nuit, pour que
    les statistiques s'ouvrent sans attendre Clover. Une erreur ici ne touche pas le traitement."""
    try:
        from .__main__ import charger_config
        from .api_clover import ClientClover
        from .statistiques_clover import lire

        hier = date.today() - timedelta(days=1)
        lire(ClientClover(charger_config(racine / "config.toml")), hier - timedelta(days=6), hier,
             racine / "donnees" / "cache_clover")
    except Exception as exc:
        cr.note(f"Statistiques Clover non préparées : {exc}")


def lancer(racine: Path, config_toml: dict, jusqua: date | None = None, simulation: bool = False,
           depuis: date | None = None, point_vente: str | None = None) -> CompteRendu:
    """Point d'entrée de la tâche planifiée : n'échoue jamais sans journal ni alerte."""
    from .courriel import envoyer_compte_rendu

    verrou = racine / "donnees" / "traitement.verrou"
    verrou.parent.mkdir(parents=True, exist_ok=True)
    if verrou.exists() and (datetime.now().timestamp() - verrou.stat().st_mtime) < 6 * 3600:
        cr = CompteRendu()
        cr.erreur = "Un traitement est déjà en cours (verrou présent) : exécution annulée."
        ecrire_journal(racine, cr)
        return cr
    verrou.write_text(f"{datetime.now():%Y-%m-%d %H:%M:%S}", encoding="utf-8")
    cr = CompteRendu(simulation=simulation)
    try:
        cr = executer_automatique(racine, config_toml, jusqua, simulation, depuis, point_vente)
    except Exception as exc:
        cr.erreur = f"{exc}\n{traceback.format_exc()}"
        print(cr.erreur, flush=True)
    finally:
        verrou.unlink(missing_ok=True)
    if not simulation:
        recevoir_factures_fournisseurs(racine, config_toml, cr)
        archiver_factures_deja_dans_sage(racine, config_toml, cr)
        prechauffer_statistiques(racine, cr)
    ecrire_journal(racine, cr)
    if not simulation or config_toml.get("courriel", {}).get("envoyer_si_simulation", False):
        try:
            envoyer_compte_rendu(config_toml, cr)
        except Exception as exc:  # l'échec d'envoi est noté, sans masquer le traitement
            cr.note(f"Courriel non envoyé : {exc}")
            ecrire_journal(racine, cr)
    return cr
