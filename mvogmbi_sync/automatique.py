"""Traitement automatique de nuit : de la dernière facture présente dans Sage jusqu'à hier, une facture par jour.

Étapes (sans intervention) :
1. Lecture de Sage : dernière facture « Vente AAAA-MM-JJ » du client, articles, comptes, réglage du client.
   Si Sage est fermé, la base est ouverte par l'outil d'import, lue, puis la connexion est annulée.
2. Correspondance des articles mise à jour (nouveaux articles Clover : reliés si le nom est identique).
3. Préparation des factures des jours suivants, jusqu'à hier. Le traitement s'arrête au premier jour
   qui pose problème (article non relié, compte manquant…) pour que les jours restent consécutifs ;
   ce jour et les suivants seront repris à la prochaine exécution, une fois le problème corrigé.
4. Import de toutes les factures prêtes en une fois ; mot de passe saisi et résumé fermé automatiquement ;
   présence de chaque facture vérifiée dans Sage.
5. Journal et courriel de compte rendu.
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

MOTIF_FACTURE = re.compile(r"^Vente (\d{4}-\d{2}-\d{2})$")


@dataclass
class EtatSage:
    dates_factures: set[date]
    client_configure: bool | None
    articles: list            # ArticleSage
    invisibles: dict[str, str]

    @property
    def derniere_date(self) -> date | None:
        return max(self.dates_factures) if self.dates_factures else None


@dataclass
class CompteRendu:
    debut: datetime = field(default_factory=datetime.now)
    lignes: list[str] = field(default_factory=list)
    importees: list[str] = field(default_factory=list)
    problemes: list[str] = field(default_factory=list)
    erreur: str = ""

    def note(self, texte: str) -> None:
        horodate = f"{datetime.now():%H:%M:%S} {texte}"
        self.lignes.append(horodate)
        print(horodate, flush=True)

    @property
    def succes(self) -> bool:
        return not self.erreur and not self.problemes


def lire_etat_sage(base, client: str) -> EtatSage:
    lignes = base.requete(
        "SELECT TRIM(t.sSource) s FROM tcustr t JOIN tcustomr c ON c.lId = t.lCusId "
        "WHERE c.sName = %s AND TRIM(t.sSource) REGEXP %s", (client, r"^Vente [0-9]{4}-[0-9]{2}-[0-9]{2}$"))
    dates = {date.fromisoformat(MOTIF_FACTURE.match(r["s"]).group(1)) for r in lignes if MOTIF_FACTURE.match(r["s"])}
    return EtatSage(dates, base.client_utilise_mes_articles(client), base.articles(),
                    base.numeros_avec_caracteres_invisibles())


def executer_automatique(racine: Path, config_toml: dict, jusqua: date | None = None,
                         simulation: bool = False) -> CompteRendu:
    from .__main__ import charger_config, config_import, executable_import, ouvrir_base_sage
    from .api_clover import ClientClover
    from .facture import CLIENT, preparer_facture
    from .import_sage import ecrire_imp, preparer_import
    from .periodes import TypePeriode
    from .sage_auto import executer, lire_pendant_connexion

    cr = CompteRendu()
    donnees = racine / "donnees"
    c_import = config_toml.get("sage_import", {})
    c_auto = config_toml.get("automatique", {})
    fichier_sai = Path(c_import.get("fichier_entreprise", ""))
    if not fichier_sai.is_file():
        raise RuntimeError(f"Fichier d'entreprise Sage introuvable : {fichier_sai}")
    exe = Path(c_import["executable"]) if c_import.get("executable") else executable_import()
    if not exe or not exe.is_file():
        raise RuntimeError("Outil d'import de Sage (Sage_SA_import.exe) introuvable.")
    mot_de_passe = coffre.lire(coffre.SAGE_IMPORT)
    hier = date.today() - timedelta(days=1)
    fin = min(jusqua or hier, hier)
    date_depart = date.fromisoformat(str(c_auto.get("date_depart", fin.isoformat())))

    # 1. Lecture de Sage -------------------------------------------------------------------------------
    cr.note(f"Lecture de Sage ({fichier_sai.name})…")

    def lecture():
        with ouvrir_base_sage(config_toml, fichier_sai) as base:
            return lire_etat_sage(base, CLIENT)

    try:
        etat = lecture()  # Sage déjà ouvert sur ce fichier
        sage_ouvert = True
    except Exception:
        etat = lire_pendant_connexion(exe, fichier_sai, lecture)
        sage_ouvert = False
    debut = max(date_depart, (etat.derniere_date + timedelta(days=1)) if etat.derniere_date else date_depart)
    cr.note(f"Dernière facture journalière dans Sage : {etat.derniere_date or 'aucune'} ; "
            f"à traiter : du {debut} au {fin}" if debut <= fin else "Sage est à jour : rien à importer.")
    if debut > fin:
        return cr
    if not etat.client_configure:
        cr.problemes.append(f"Fiche client « {CLIENT} » : cocher « Ce client utilise mes n° articles » "
                            "(onglet Importer/Exporter), sinon Sage ne reconnaît aucun article.")
        return cr

    # 2. Correspondance des articles ----------------------------------------------------------------------
    client = ClientClover(charger_config(racine / "config.toml"))
    table = mettre_a_jour_correspondance(client, etat.articles, donnees, cr)
    comptes = {a.numero: a.compte_revenus for a in etat.articles}

    # 3. Préparation, jour par jour -------------------------------------------------------------------------
    pretes = []
    jour = debut
    while jour <= fin:
        if jour in etat.dates_factures:
            cr.note(f"{jour} : facture déjà présente dans Sage, ignorée.")
            jour += timedelta(days=1)
            continue
        rapport = client.rapport(jour, jour)
        if not rapport.lignes:
            cr.note(f"{jour} : aucune vente.")
            jour += timedelta(days=1)
            continue
        facture = preparer_facture(rapport, TypePeriode.JOUR)
        imp = preparer_import(facture, table)
        blocages = [f"article Clover non relié à Sage : {n}" for n in imp.non_reliees] + list(facture.anomalies)
        if imp.sous_total != rapport.total_net:
            blocages.append(f"écart de {rapport.total_net - imp.sous_total:.2f} $ avec les ventes Clover")
        numeros = {l.numero_sage for l in imp.lignes}
        blocages += [f"article Sage sans compte de produits : {n}" for n in sorted(numeros) if not comptes.get(n)]
        blocages += [f"numéro d'article Sage avec caractères invisibles (à retaper) : {n}"
                     for n in sorted(numeros & set(etat.invisibles))]
        for texte in facture.avertissements:
            cr.note(f"{jour} : (info) {texte}")
        if blocages:
            cr.problemes += [f"{jour} : {b}" for b in blocages]
            cr.note(f"{jour} : facture NON préparée ({len(blocages)} problème(s)) ; arrêt à ce jour, "
                    "elle sera reprise à la prochaine exécution.")
            break
        pretes.append(imp)
        cr.note(f"{facture.numero} : {len(imp.lignes)} lignes, sous-total {imp.sous_total:,.2f} $, "
                f"total {imp.total:,.2f} $")
        jour += timedelta(days=1)

    if not pretes:
        cr.note("Aucune facture prête à importer.")
        return cr
    chemin_imp = ecrire_imp(pretes, racine / "sortie" / "factures" / f"Auto_{pretes[0].facture.date_facture}"
                            f"_au_{pretes[-1].facture.date_facture}.IMP", config_import(config_toml))
    if simulation:
        cr.note(f"Simulation : {len(pretes)} facture(s) prête(s) dans {chemin_imp}, aucun import.")
        return cr

    # 4. Import et vérification --------------------------------------------------------------------------------
    cr.note(f"Import de {len(pretes)} facture(s) dans {fichier_sai.name}…")
    presentes: dict[str, bool] = {}

    def verifier(_resume: str = "") -> None:
        for _ in range(10):
            try:
                with ouvrir_base_sage(config_toml, fichier_sai) as base:
                    for imp in pretes:
                        presentes[imp.facture.numero] = base.facture_existe(imp.facture.numero, CLIENT)
                return
            except Exception:
                import time
                time.sleep(1)

    resultat = executer(exe, chemin_imp, fichier_sai, mot_de_passe, pendant_resume=verifier,
                        delai=int(c_auto.get("delai_import", 3600)))
    if not presentes and sage_ouvert:
        verifier()
    for texte in resultat.erreurs:
        cr.problemes.append(f"Sage : {texte}")
    journal = donnees / "journal_imports.csv"
    nouveau = not journal.exists()
    with journal.open("a", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        if nouveau:
            w.writerow(["Date et heure", "Facture", "Fichier d'entreprise", "Lignes", "Sous-total", "Total",
                        "Code de retour", "Résultat"])
        for imp in pretes:
            ok = presentes.get(imp.facture.numero)
            statut = "importée" if ok else ("non vérifiable" if ok is None else "ÉCHEC")
            w.writerow([f"{datetime.now():%Y-%m-%d %H:%M:%S}", imp.facture.numero, fichier_sai.name, len(imp.lignes),
                        f"{imp.sous_total:.2f}", f"{imp.total:.2f}", resultat.code_retour, statut])
            if ok:
                cr.importees.append(f"{imp.facture.numero} : {imp.total:,.2f} $")
            else:
                cr.problemes.append(f"{imp.facture.numero} : {statut} après l'import")
    cr.note(f"{len(cr.importees)} facture(s) importée(s) et vérifiée(s) dans Sage.")
    return cr


def mettre_a_jour_correspondance(client, articles_sage: list, donnees: Path, cr: CompteRendu):
    """Met à jour la correspondance avec le catalogue Clover ; renvoie la table utilisée pour les factures.

    Les confirmations du propriétaire sont conservées ; un nouvel article Clover dont le nom est identique
    à un article Sage est relié automatiquement ; les cas douteux restent « À confirmer » (le jour où un tel
    article est vendu, le traitement s'arrête et l'alerte demande de le confirmer dans le fichier).
    """
    from .api_clover import SANS_CATEGORIE
    from .correspondance import (AUTOMATIQUE, CONFIRME, ArticleClover, Correspondance, ecrire_correspondance,
                                 lire_a_relier, lire_confirmes, rapprocher)
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
    for id_article, nom, numero_sage in lire_a_relier(donnees / "articles_a_relier.csv"):
        if numero_sage:  # numéro Sage inscrit par le propriétaire : correspondance confirmée
            confirmes[id_article] = Correspondance(CONFIRME, nom, "", Decimal("0"), numero_sage, "", "",
                                                   "Manuel (articles_a_relier)", 100, "", "", id_article)
        if id_article not in ids:
                a = client.article(id_article) or {"id": id_article}
                a["name"] = a.get("name") or nom
                catalogue.append(a)
                ids.add(id_article)
    clover = [
        ArticleClover(
            id=a["id"], nom=(a.get("name") or "").strip(),
            categorie=(((a.get("categories") or {}).get("elements") or [{}])[0]).get("name", SANS_CATEGORIE),
            code=(a.get("code") or "").strip(), ventes_30j=anciennes_ventes.get(a["id"], Decimal("0")),
        )
        for a in catalogue
    ]
    resultat = rapprocher(clover, articles_sage, confirmes)
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
    for c in nouveaux:
        if c.statut not in (CONFIRME, AUTOMATIQUE):
            cr.note(f"Nouvel article Clover à confirmer : {c.nom_clover} ({c.statut})")
    table = TableCorrespondance({}, {})
    for c in resultat:
        if c.statut in (CONFIRME, AUTOMATIQUE) and c.numero_sage:
            table.par_id[c.id_clover] = c.numero_sage
            table.par_nom.setdefault(cle_nom(c.nom_clover), c.numero_sage)
    return table


def ecrire_journal(racine: Path, cr: CompteRendu) -> Path:
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


def lancer(racine: Path, config_toml: dict, jusqua: date | None = None, simulation: bool = False) -> CompteRendu:
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
    cr = CompteRendu()
    try:
        cr = executer_automatique(racine, config_toml, jusqua, simulation)
    except Exception as exc:
        cr.erreur = f"{exc}\n{traceback.format_exc()}"
        print(cr.erreur, flush=True)
    finally:
        verrou.unlink(missing_ok=True)
    ecrire_journal(racine, cr)
    if not simulation:
        try:
            envoyer_compte_rendu(config_toml, cr)
        except Exception as exc:  # l'échec d'envoi est noté, sans masquer le traitement
            cr.note(f"Courriel non envoyé : {exc}")
            ecrire_journal(racine, cr)
    return cr
