"""T4 et Relevé 1 de chaque employé (demande du propriétaire du 2026-10-30), d'après les paies de Sage de l'année.

Présentation calquée sur les formulaires (cases numérotées), en copie de l'employé : imprimés pour un, plusieurs ou
tous les employés, ou envoyés à chacun par courriel (un seul destinataire). Le NAS n'est jamais gardé par
l'application : la case reste vide. Les feuillets officiels (T4 transmis à l'ARC, RL-1 de Revenu Québec, qui exige un
numéro attribué au formulaire) restent ceux de Sage : ces pages servent à remettre et à vérifier les montants.
Gains assurables et admissibles : ceux des tables de paie de Sage ; sans accès au module Paie, les revenus d'emploi,
sans plafond annuel.
"""

from __future__ import annotations

import html
import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from . import paie as pa

ZERO = Decimal(0)


@dataclass
class Feuillet:
    annee: int
    employe: str               # nom tel que Sage l'écrit
    brut: Decimal = ZERO
    rrq: Decimal = ZERO
    rpc: Decimal = ZERO
    ae: Decimal = ZERO
    rqap: Decimal = ZERO
    impot_federal: Decimal = ZERO
    impot_quebec: Decimal = ZERO
    gains_ae: Decimal = ZERO
    gains_pension: Decimal = ZERO
    gains_rqap: Decimal = ZERO
    adresse: str = ""
    courriel: str = ""

    @property
    def cle(self) -> str:
        return f"{self.annee}|{self.employe}"


def calculer(paies: list[pa.PaieSage], annee: int, employes=()) -> list[Feuillet]:
    """Un feuillet par employé Sage ayant une paie dans l'année ; adresse et courriel de l'employé relié."""
    par_nom: dict[str, Feuillet] = {}
    for p in paies:
        if p.jour.year != annee:
            continue
        f = par_nom.get(p.employe)
        if f is None:
            f = par_nom[p.employe] = Feuillet(annee, p.employe)
            e = pa.employe_de(p, list(employes))
            if e:
                f.adresse, f.courriel = e.adresse, e.courriel
            if p.detail:  # la fiche de Sage d'abord
                f.adresse, f.courriel = p.detail.adresse or f.adresse, p.detail.courriel or f.courriel
        r = p.retenues
        f.brut += p.brut
        # gains assurables et admissibles : ceux de Sage, plafonds annuels appliqués ; sans détail, le brut
        f.gains_ae += p.detail.gains_ae if p.detail else p.brut
        f.gains_pension += p.detail.gains_pension if p.detail else p.brut
        f.gains_rqap += p.detail.gains_rqap if p.detail else p.brut
        f.rrq += r.get("RRQ", ZERO)
        f.rpc += r.get("RPC", ZERO)
        f.ae += r.get("Assurance-emploi", ZERO)
        f.rqap += r.get("RQAP", ZERO)
        f.impot_federal += r.get("Impôt fédéral", ZERO)
        f.impot_quebec += r.get("Impôt du Québec", ZERO)
    return sorted(par_nom.values(), key=lambda x: x.employe.casefold())


def _m(v) -> str:
    return f"{v:,.2f}".replace(",", " ").replace(".", ",") if v else ""


def _adresse(texte: str) -> str:
    return "<br>".join(html.escape(x.strip()) for x in (texte or "").split("|") if x.strip())


CSS = """<style>
.feuillet { font-size: 8pt; color: #111; }
.feuillet .rang { display: flex; gap: 6px; margin-bottom: 6px; }
.feuillet .bloc { border: 1.5px solid #222; padding: 5px 7px; min-height: 66px; flex: 1; }
.feuillet .bloc b { display: block; font-size: 7pt; font-weight: 600; margin-bottom: 3px; }
.feuillet .val { color: #1f2d6e; font-size: 9.5pt; font-weight: 600; }
.feuillet .cases { display: grid; grid-template-columns: repeat(4, 1fr); gap: 5px; }
.feuillet .case { border: 1px solid #333; padding: 3px 5px; min-height: 34px; }
.feuillet .case .lib { font-size: 6.5pt; line-height: 1.15; display: block; min-height: 15px; }
.feuillet .case .num { font-weight: 700; margin-right: 3px; }
.feuillet .case .montant { display: block; text-align: right; color: #1f2d6e; font-size: 10pt; font-weight: 600; }
.feuillet h2 { font-size: 13pt; margin: 2px 0 6px; }
.feuillet .mention { font-size: 7pt; color: #555; margin-top: 8px; }
.saut { page-break-after: always; }
</style>"""


def _case(numero: str, libelle: str, valeur: str = "") -> str:
    return (f"<div class='case'><span class='lib'><span class='num'>{numero}</span>{html.escape(libelle)}</span>"
            f"<span class='montant'>{html.escape(valeur)}</span></div>")


def _parties(f: Feuillet, employeur, no_employeur: str) -> tuple[str, str]:
    e = html.escape
    tiers = (f"<div class='bloc'><b>Nom de l'employeur</b><span class='val'>{e(employeur.nom)}<br>"
             f"{e(employeur.adresse)}<br>{e(employeur.ville)}</span>"
             + (f"<br><b>N° de compte de l'employeur</b><span class='val'>{e(no_employeur)}</span>" if no_employeur
                else "") + "</div>")
    employe = (f"<div class='bloc'><b>Nom et adresse de l'employé</b><span class='val'>{e(f.employe)}<br>"
               f"{_adresse(f.adresse)}</span><b style='margin-top:5px'>Numéro d'assurance sociale</b>"
               "<span class='val'>&nbsp;</span></div>")
    return tiers, employe


def t4_html(f: Feuillet, employeur, no_employeur: str = "") -> str:
    tiers, employe = _parties(f, employeur, no_employeur)
    cases = [("14", "Revenus d'emploi", _m(f.brut)), ("22", "Impôt sur le revenu retenu", _m(f.impot_federal)),
             ("16", "Cotisations de l'employé au RPC", _m(f.rpc)), ("17", "Cotisations de l'employé au RRQ", _m(f.rrq)),
             ("18", "Cotisations de l'employé à l'AE", _m(f.ae)), ("24", "Gains assurables d'AE", _m(f.gains_ae)),
             ("26", "Gains ouvrant droit à pension – RPC/RRQ", _m(f.gains_pension)), ("44", "Cotisations syndicales"),
             ("20", "Cotisations à un RPA"), ("46", "Dons de bienfaisance"), ("52", "Facteur d'équivalence"),
             ("50", "N° d'agrément d'un RPA ou d'un RPDB"), ("55", "Cotisations de l'employé au RPAP", _m(f.rqap)),
             ("56", "Gains assurables du RPAP", _m(f.gains_rqap)), ("10", "Province d'emploi", "QC"), ("29", "Code d'emploi")]
    return (f"<div class='feuillet'><h2>T4 — État de la rémunération payée — {f.annee}</h2>"
            f"<div class='rang'>{tiers}{employe}</div><div class='cases'>"
            + "".join(_case(*c) for c in cases)
            + "</div><div class='mention'>Copie de l'employé. Protégé B une fois rempli. Le numéro d'assurance sociale "
              "n'est pas conservé par l'application.</div></div>")


def rl1_html(f: Feuillet, employeur, no_employeur: str = "") -> str:
    tiers, employe = _parties(f, employeur, "")
    cases = [("A", "Revenus d'emploi", _m(f.brut)), ("B", "Cotisation au RRQ", _m(f.rrq)),
             ("C", "Cotisation à l'assurance emploi", _m(f.ae)), ("D", "Cotisation à un RPA"),
             ("E", "Impôt du Québec retenu", _m(f.impot_quebec)), ("F", "Cotisation syndicale"),
             ("G", "Salaire admissible au RRQ", _m(f.gains_pension)), ("H", "Cotisation au RQAP", _m(f.rqap)),
             ("I", "Salaire admissible au RQAP", _m(f.gains_rqap)), ("J", "Régime privé d'ass. maladie"),
             ("K", "Voyages (région éloignée)"), ("L", "Autres avantages"), ("M", "Commissions"),
             ("N", "Dons de bienfaisance"), ("O", "Autres revenus"), ("P", "Régime d'ass. interentreprises"),
             ("Q", "Salaires différés"), ("R", "Revenu « situé » dans une réserve"), ("S", "Pourboires reçus"),
             ("T", "Pourboires attribués"), ("U", "Retraite progressive"), ("V", "Nourriture et logement"),
             ("W", "Véhicule à moteur"), ("", "Code (case O)")]
    return (f"<div class='feuillet'><h2>Relevé 1 — Revenus d'emploi et revenus divers — {f.annee}</h2>"
            "<div class='cases'>" + "".join(_case(*c) for c in cases)
            + f"</div><div class='rang' style='margin-top:8px'>{employe}{tiers}</div>"
              "<div class='mention'>Copie de l'employé. Le relevé officiel transmis à Revenu Québec est celui produit "
              "par Sage. Le numéro d'assurance sociale n'est pas conservé par l'application.</div></div>")


def page_feuillets(feuillets: list[Feuillet], employeur, no_employeur: str = "", genres=("T4", "RL-1"),
                   imprimer: bool = False) -> str:
    """Une page HTML : T4 puis RL-1 de chaque employé, chacun sur sa feuille."""
    from .export_tableau import page_html

    blocs = []
    for f in feuillets:
        if "T4" in genres:
            blocs.append(t4_html(f, employeur, no_employeur))
        if "RL-1" in genres:
            blocs.append(rl1_html(f, employeur, no_employeur))
    corps = CSS + "<div class='saut'></div>".join(blocs)
    annee = feuillets[0].annee if feuillets else ""
    page = page_html(f"T4 et Relevé 1 {annee}", [], [], sous_titre=(feuillets[0].employe if len(feuillets) == 1 else
                                                                    f"{len(feuillets)} employés"), imprimer=imprimer)
    return page.replace("</body></html>", corps + "</body></html>")


# --------------------------------------------------------------------------------------------- formulaires officiels
# Formulaires officiels remplis (demande du propriétaire du 2026-11-01) : T4 de l'ARC (t4-26b.pdf, 2 feuillets par
# page + verso) et RL-1 de Revenu Québec (RL-1(2026-10).pdf, modèle « SPÉCIMEN »). Ces PDF n'ont aucun champ à
# remplir : les montants sont écrits par-dessus, aux coordonnées des cases relevées dans le formulaire (points,
# origine en haut à gauche). Le NAS n'est jamais écrit (jamais gardé par l'application).
FORMULAIRES = Path(__file__).parent / "ressources" / "formulaires"
T4_PDF, RL1_PDF = FORMULAIRES / "t4-26b.pdf", FORMULAIRES / "RL-1-2026-10.pdf"
T4_DECALAGE = 387.4  # 2e feuillet de la page : même dessin, plus bas
T4_GAUCHE, T4_DROITE = (352.4, 424.2, 455.4), (485.5, 557.3, 588.6)  # début, séparation des cents, fin
T4_LIGNES = {"14": (72.8, 90.8), "16": (106.6, 124.6), "16A": (144.1, 162.1), "24": (176.5, 194.5),
             "18": (208.1, 226.1), "20": (240.4, 258.4), "52": (272.7, 290.7), "55": (305.7, 323.7)}
T4_CASES = {"14": ("14", T4_GAUCHE), "22": ("14", T4_DROITE), "16": ("16", T4_GAUCHE), "17": ("16", T4_DROITE),
            "16A": ("16A", T4_GAUCHE), "17A": ("16A", T4_DROITE), "24": ("24", T4_GAUCHE), "26": ("24", T4_DROITE),
            "18": ("18", T4_GAUCHE), "44": ("18", T4_DROITE), "20": ("20", T4_GAUCHE), "46": ("20", T4_DROITE),
            "52": ("52", T4_GAUCHE), "55": ("55", T4_GAUCHE), "56": ("55", T4_DROITE)}
RL1_COLONNES = (24, 119, 215, 309, 404, 499)  # largeur 89 ; séparation des cents à +73
RL1_LIGNES = (79.0, 102.8, 127.2, 151.4)       # haut de la zone de saisie de chaque rangée (hauteur 11)
RL1_CASES = {"A": (0, 0), "B.A": (0, 1), "B.B": (0, 2), "C": (0, 3), "D": (0, 4), "E": (0, 5),
             "F": (1, 0), "G": (1, 1), "H": (1, 2), "I": (1, 3), "J": (1, 4), "K": (1, 5),
             "L": (2, 0), "M": (2, 1), "N": (2, 2), "O": (2, 3), "P": (2, 4), "Q": (2, 5),
             "R": (3, 0), "S": (3, 1), "T": (3, 2), "V": (3, 3), "W": (3, 4)}


def _dollars_cents(v: Decimal) -> tuple[str, str]:
    texte = f"{v:,.2f}".replace(",", " ")
    return texte[:-3], texte[-2:]


def montants_t4(f: Feuillet) -> dict[str, Decimal]:
    return {"14": f.brut, "22": f.impot_federal, "16": f.rpc, "17": f.rrq, "24": f.gains_ae or f.brut,
            "26": f.gains_pension or f.brut, "18": f.ae, "55": f.rqap, "56": f.gains_rqap or f.brut}


def montants_rl1(f: Feuillet) -> dict[str, Decimal]:
    return {"A": f.brut, "B.A": f.rrq, "C": f.ae, "E": f.impot_quebec, "G": f.gains_pension or f.brut,
            "H": f.rqap, "I": f.gains_rqap or f.brut}


def _calque(largeur: float, hauteur: float):
    from fpdf import FPDF

    from .export_tableau import POLICES

    calque = FPDF(unit="pt", format=(largeur, hauteur))
    calque.set_auto_page_break(False)
    calque.set_margins(0, 0, 0)
    if all(p.exists() for p in POLICES):
        calque.add_font("Arial", "", str(POLICES[0]))
        calque.add_font("Arial", "B", str(POLICES[1]))
        calque.police = "Arial"
    else:
        calque.police = "Helvetica"
    return calque


def _texte(calque, x: float, y: float, largeur: float, hauteur: float, texte: str, taille: float = 9,
           align: str = "L", gras: bool = False) -> None:
    if not texte:
        return
    calque.set_font(calque.police, "B" if gras else "", taille)
    calque.set_xy(x, y)
    calque.cell(largeur, hauteur, texte, align=align)


def _montant(calque, case: tuple[float, float, float], haut: float, bas: float, valeur: Decimal) -> None:
    if not valeur:
        return
    debut, separation, fin = case
    dollars, cents = _dollars_cents(valeur)
    _texte(calque, debut, haut, separation - debut - 3, bas - haut, dollars, 10, "R")
    _texte(calque, separation + 2, haut, fin - separation - 4, bas - haut, cents, 10, "L")


def _calque_t4(f: Feuillet, employeur, no_employeur: str) -> bytes:
    calque = _calque(612, 792)
    calque.add_page()
    adresse = [x.strip() for x in (f.adresse or "").split("|") if x.strip()]
    for d in (0.0, T4_DECALAGE):  # les deux feuillets de la page portent les mêmes montants
        lignes = [employeur.nom, employeur.adresse, employeur.ville]
        for rang, ligne in enumerate(x for x in lignes if x):
            _texte(calque, 52, d + 47 + 11 * rang, 196, 11, ligne, 9)
        _texte(calque, 293.4, d + 36, 57.6, 18, str(f.annee), 12, "C", True)
        _texte(calque, 60, d + 106, 194, 16, no_employeur, 10)
        _texte(calque, 289.8, d + 121.6, 28.8, 18, "QC", 10, "C")
        _texte(calque, 60, d + 210, 230, 15, f.employe.upper(), 10)
        for rang, ligne in enumerate(adresse[:4]):
            _texte(calque, 52, d + 250 + 12 * rang, 270, 12, ligne, 9)
        for case, valeur in montants_t4(f).items():
            ligne, colonne = T4_CASES[case]
            haut, bas = T4_LIGNES[ligne]
            _montant(calque, colonne, d + haut, d + bas, valeur)
    return bytes(calque.output())


def _calque_rl1(f: Feuillet, employeur) -> bytes:
    calque = _calque(612, 792)
    calque.add_page()
    _texte(calque, 366, 47, 40, 11, "R", 10, "L", True)  # code du relevé : R = relevé original
    for case, valeur in montants_rl1(f).items():
        rangee, colonne = RL1_CASES[case]
        x, haut = RL1_COLONNES[colonne], RL1_LIGNES[rangee]
        _montant(calque, (x + 2, x + 73, x + 89), haut, haut + 11, valeur)
    lignes = [employeur.nom, employeur.adresse, employeur.ville]
    for rang, ligne in enumerate(x for x in lignes if x):
        _texte(calque, 356, 648 + 11 * rang, 230, 11, ligne, 9)
    adresse = [f.employe] + [x.strip() for x in (f.adresse or "").split("|") if x.strip()]
    for rang, ligne in enumerate(adresse[:5]):
        _texte(calque, 51, 668 + 12 * rang, 280, 12, ligne, 10, gras=rang == 0)
    return bytes(calque.output())


# formulaires téléchargés des sites de l'ARC et de Revenu Québec (demande du propriétaire du 2026-11-03) :
# [feuillets] url_t4 / url_rl1 pour une nouvelle version ; copie gardée dans donnees/formulaires/, relue au plus
# tous les JOURS_FORMULAIRES jours ; utilisée seulement si les cases sont toujours aux coordonnées connues (repères),
# sinon la dernière copie valable (ou celle livrée avec l'application) sert et le changement est signalé
URLS_FORMULAIRES = {"T4": "https://www.canada.ca/content/dam/cra-arc/formspubs/pbg/t4/t4-26b.pdf",
                    "RL-1": "https://www.revenuquebec.ca/documents/fr/formulaires/rl/RL-1%282026-10%29.pdf"}
JOURS_FORMULAIRES = 7
REPERES = {"T4": (2, [("14", 339.4, 74.4), ("22", 461.8, 74.4), ("56", 472.6, 307.3), ("14", 339.4, 462.0)]),
           "RL-1": (1, [("A-", 24.3, 71.9), ("E-", 499.7, 71.9), ("R-", 24.3, 144.2), ("Année", 324.3, 37.0)])}


def formulaire_conforme(contenu: bytes, genre: str) -> bool:
    """Le PDF a le nombre de pages attendu et ses cases aux coordonnées connues (à 2 points près)."""
    import io

    import pdfplumber

    pages, reperes = REPERES[genre]
    try:
        with pdfplumber.open(io.BytesIO(contenu)) as pdf:
            if len(pdf.pages) != pages:
                return False
            mots = pdf.pages[0].extract_words()
    except Exception:
        return False
    return all(any(m["text"] == texte and abs(m["x0"] - x) < 2 and abs(m["top"] - y) < 2 for m in mots)
               for texte, x, y in reperes)


def formulaire(racine, genre: str, config_toml: dict | None = None) -> tuple[Path, str]:
    """(chemin du formulaire officiel, remarque) : copie téléchargée du site gouvernemental si elle est récente et
    conforme, sinon téléchargée maintenant ; à défaut, la dernière copie conforme ou celle de l'application."""
    import time

    livre = T4_PDF if genre == "T4" else RL1_PDF
    if racine is None:
        return livre, ""
    url = str((config_toml or {}).get("feuillets", {}).get("url_t4" if genre == "T4" else "url_rl1", "")
              or URLS_FORMULAIRES[genre])
    copie = Path(racine) / "donnees" / "formulaires" / ("t4.pdf" if genre == "T4" else "rl1.pdf")
    if copie.exists() and time.time() - copie.stat().st_mtime < JOURS_FORMULAIRES * 86400:
        return copie, ""
    remarque = ""
    try:
        import requests

        reponse = requests.get(url, timeout=30, headers={"User-Agent": "MVOGMBI_Sync"})
        reponse.raise_for_status()
        if not reponse.content.startswith(b"%PDF"):
            raise ValueError("le site n'a pas renvoyé de PDF")
        if formulaire_conforme(reponse.content, genre):
            copie.parent.mkdir(parents=True, exist_ok=True)
            copie.write_bytes(reponse.content)
            return copie, ""
        remarque = (f"Le formulaire {genre} du site a changé de mise en page : l'ancienne version est utilisée "
                    "(à adapter dans l'application).")
    except Exception as exc:
        remarque = f"Formulaire {genre} non téléchargé ({exc}) : la dernière copie est utilisée."
    if copie.exists():
        copie.touch()  # pas de nouvel essai avant JOURS_FORMULAIRES jours
        return copie, remarque
    return livre, remarque


def pdf_officiels(feuillets: list[Feuillet], employeur, no_employeur: str = "", genres=("T4", "RL-1"),
                  racine=None, config_toml: dict | None = None) -> bytes:
    """Un PDF : pour chaque employé, le T4 officiel rempli (feuillets + verso) puis le RL-1. Le RL-1 de Revenu Québec
    transmis aux gouvernements reste celui de Sage (formulaire numéroté) ; ce RL-1 est la copie de l'employé."""
    import io

    from pypdf import PdfReader, PdfWriter

    t4_pdf, _ = formulaire(racine, "T4", config_toml) if "T4" in genres else (T4_PDF, "")
    rl1_pdf, _ = formulaire(racine, "RL-1", config_toml) if "RL-1" in genres else (RL1_PDF, "")
    sortie = PdfWriter()
    for f in feuillets:
        if "T4" in genres:
            modele = PdfReader(t4_pdf)
            calque = PdfReader(io.BytesIO(_calque_t4(f, employeur, no_employeur))).pages[0]
            for rang, page in enumerate(modele.pages):
                ajoutee = sortie.add_page(page)  # la page est d'abord au document, puis le calque y est posé
                if rang == 0:
                    ajoutee.merge_page(calque)
        if "RL-1" in genres:
            ajoutee = sortie.add_page(PdfReader(rl1_pdf).pages[0])
            ajoutee.merge_page(PdfReader(io.BytesIO(_calque_rl1(f, employeur))).pages[0])
    tampon = io.BytesIO()
    sortie.write(tampon)
    return tampon.getvalue()


# --------------------------------------------------------------------------------------------- réglages et envois
def numero_employeur(racine) -> str:
    chemin = Path(racine) / "donnees" / "feuillets.json"
    return json.loads(chemin.read_text(encoding="utf-8")).get("no_employeur", "") if chemin.exists() else ""


def definir_numero_employeur(racine, numero: str) -> None:
    chemin = Path(racine) / "donnees" / "feuillets.json"
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps({"no_employeur": numero.strip()}, ensure_ascii=False, indent=1), encoding="utf-8")


def envoyes(racine) -> set[str]:
    import csv

    chemin = Path(racine) / "donnees" / "journal_feuillets_envoyes.csv"
    if not chemin.exists():
        return set()
    with chemin.open(encoding="utf-8-sig", newline="") as fichier:
        return {r["Feuillet"] for r in csv.DictReader(fichier, delimiter=";")}


def noter_envoi(racine, f: Feuillet) -> None:
    import csv
    from datetime import datetime

    chemin = Path(racine) / "donnees" / "journal_feuillets_envoyes.csv"
    nouveau = not chemin.exists()
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with chemin.open("a", encoding="utf-8-sig", newline="") as fichier:
        ecrivain = csv.writer(fichier, delimiter=";")
        if nouveau:
            ecrivain.writerow(["Envoyé le", "Feuillet", "Employé", "Courriel"])
        ecrivain.writerow([datetime.now().isoformat(timespec="seconds"), f.cle, f.employe, f.courriel])


def envoyer(config_toml: dict, f: Feuillet, pdf: bytes) -> None:
    """T4 et RL-1 en PDF, au seul employé concerné."""
    from .courriel import envoyer_a

    envoyer_a(config_toml, f.courriel, f"T4 et Relevé 1 {f.annee}",
              f"Bonjour {f.employe},\n\nVous trouverez ci-joint votre T4 et votre Relevé 1 de {f.annee}.\n\n"
              "Ce message est personnel et confidentiel.\n", [(f"T4 et Releve 1 {f.annee}.pdf", pdf)])
