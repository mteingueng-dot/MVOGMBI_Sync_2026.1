"""Import des factures fournisseurs dans Sage 50 : fichier .IMP <PurInvoice>, importé avec Sage fermé.

Format (calqué sur un fichier d'achat produit par Sage lui-même, version 12001) :
    <PurInvoice>
    "Nom du fournisseur Sage"
    nb_lignes,"","n° facture","mm-jj-aaaa",total,frais_de_port,"0","0","0.00"
    "n° article Sage",quantité,prix,montant[,"TPS/TVH","0","1","5.00",taxe,"TVQ","0","1","9.975",taxe]
    </PurInvoice>
Quantité et prix dans l'unité de Sage (conditionnement : quantité × facteur, prix = montant / quantité Sage) ;
le montant de chaque ligne est celui de la facture.

Contrôles bloquants (dans le fichier d'entreprise visé) : fournisseur présent et réglé pour « utiliser mes numéros
d'articles » (sinon Sage croit recevoir les numéros du fournisseur), articles présents avec un compte d'actif,
facture absente (même n° écrit autrement : « FA-104202 » = « 104202 »), montants cohérents.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from .facture import TAUX_TPS, TAUX_TVQ
from .fournisseurs import IMPORTEE, Facture

CENT = Decimal("0.01")


def _texte(valeur) -> str:
    return '"' + str(valeur).replace('"', "'") + '"'


def _nombre(valeur: Decimal, decimales: int) -> str:
    return f'"{valeur.quantize(Decimal(1).scaleb(-decimales), rounding=ROUND_HALF_UP)}"'


def meme_numero(a: str, b: str) -> bool:
    """« FA-104202 » et « 104202 » désignent la même facture ; « 1264 » et « 11264 » non."""
    na, nb = (re.sub(r"[^0-9a-z]", "", x.lower()) for x in (a, b))
    if not na or not nb:
        return False
    if na == nb:
        return True
    court, long_ = sorted((na, nb), key=len)
    return len(court) >= 4 and long_.endswith(court) and not long_[:-len(court)].isdigit()


def taxes_par_ligne(facture: Facture) -> list[tuple[Decimal, Decimal]]:
    """TPS et TVQ de chaque ligne taxable (5 % et 9,975 % du montant), ajustées au cent sur les totaux de la facture."""
    taxes = [((l.montant * TAUX_TPS).quantize(CENT, ROUND_HALF_UP), (l.montant * TAUX_TVQ).quantize(CENT, ROUND_HALF_UP))
             if l.taxable else (Decimal(0), Decimal(0)) for l in facture.lignes]
    taxables = [i for i, l in enumerate(facture.lignes) if l.taxable]
    if taxables:
        dernier = taxables[-1]
        ecart_tps = facture.tps - sum(t[0] for t in taxes)
        ecart_tvq = facture.tvq - sum(t[1] for t in taxes)
        if abs(ecart_tps) <= Decimal("0.05") and abs(ecart_tvq) <= Decimal("0.05"):  # arrondis du fournisseur
            taxes[dernier] = (taxes[dernier][0] + ecart_tps, taxes[dernier][1] + ecart_tvq)
    return taxes


def bloc_achat(facture: Facture) -> list[str]:
    jour = date.fromisoformat(facture.date_facture)
    total = facture.total if facture.total is not None else facture.somme_lignes + facture.tps + facture.tvq
    lignes = ["<PurInvoice>", _texte(facture.fournisseur_sage),
              ",".join([f'"{len(facture.lignes)}"', '""', _texte(facture.numero), _texte(jour.strftime("%m-%d-%Y")),
                        _nombre(total, 2), '"0.00"', '"0"', '"0"', '"0.00"'])]
    for l, (tps, tvq) in zip(facture.lignes, taxes_par_ligne(facture)):
        quantite, prix = l.en_sage()
        champs = [_texte(l.numero_sage), _nombre(quantite, 4), _nombre(prix, 4), _nombre(l.montant, 2)]
        if l.taxable:
            champs += ['"TPS/TVH"', '"0"', '"1"', '"5.00"', _nombre(tps, 2),
                       '"TVQ"', '"0"', '"1"', '"9.975"', _nombre(tvq, 2)]
        lignes.append(",".join(champs))
    return lignes + ["</PurInvoice>"]


def ecrire_imp_achats(factures: list[Facture], chemin: Path, version: str = "12001", pays: str = "1",
                      encodage: str = "cp1252") -> Path:
    lignes = ["<Version>", f"{_texte(version)},{_texte(pays)}", "</Version>", ""]
    for f in factures:
        lignes += bloc_achat(f)
    lignes.append("")
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text("\r\n".join(lignes), encoding=encodage, errors="replace", newline="")
    return chemin


# --------------------------------------------------------------------------------------------- contrôles dans Sage
@dataclass
class EtatAchat:
    problemes: list[str] = field(default_factory=list)
    deja_present: str = ""          # n° de la facture déjà présente dans Sage (ex. « FA-104202 »)


def verifier_dans_sage(base, factures: list[Facture]) -> dict[str, EtatAchat]:
    """Contrôles bloquants de chaque facture dans le fichier d'entreprise (clé : nom du fichier de la facture)."""
    fournisseurs = {l["sName"].strip(): l for l in base.requete("SELECT lId, sName, bUseMyItem, bInactive FROM tvendor")}
    numeros = sorted({l.numero_sage for f in factures for l in f.lignes if l.numero_sage})
    articles = {}
    if numeros:
        marques = ",".join(["%s"] * len(numeros))
        articles = {l["sPartCode"].strip(): l for l in base.requete(
            f"SELECT sPartCode, sName, lAcNAsset, bService FROM tinvent WHERE sPartCode IN ({marques})", tuple(numeros))}
    resultat = {}
    for f in factures:
        e = EtatAchat()
        v = fournisseurs.get(f.fournisseur_sage)
        if not v:
            e.problemes.append(f"fournisseur « {f.fournisseur_sage} » absent de Sage")
        else:
            if not v["bUseMyItem"]:
                e.problemes.append(f"fiche du fournisseur « {f.fournisseur_sage} » (onglet Importer/Exporter) : cocher "
                                   "« utilise mes numéros d'articles »")
            existantes = base.requete("SELECT sSource FROM tventr WHERE lVenId = %s", (v["lId"],))
            pareille = next((x["sSource"].strip() for x in existantes if meme_numero(x["sSource"] or "", f.numero)), "")
            if pareille:
                e.deja_present = pareille
                e.problemes.append(f"facture déjà dans Sage pour ce fournisseur (n° « {pareille} »)")
        for l in f.lignes:
            a = articles.get(l.numero_sage)
            if not l.numero_sage:
                e.problemes.append(f"ligne sans article Sage : {l.description}")
            elif not a:
                e.problemes.append(f"article Sage {l.numero_sage} introuvable")
            elif not a["bService"] and not a["lAcNAsset"]:
                e.problemes.append(f"article Sage {l.numero_sage} sans compte d'actif")
        e.problemes = list(dict.fromkeys(e.problemes))
        resultat[f.fichier] = e
    return resultat


def facture_presente(base, fournisseur_sage: str, numero: str) -> bool:
    lignes = base.requete("SELECT COUNT(*) n FROM tventr t JOIN tvendor v ON v.lId = t.lVenId "
                          "WHERE v.sName = %s AND TRIM(t.sSource) = %s", (fournisseur_sage, numero.strip()))
    return bool(lignes and lignes[0]["n"])


# --------------------------------------------------------------------------------------------- import
def importer_achats(racine: Path, config_toml: dict, factures: list[Facture], journal=print) -> dict[str, str]:
    """Contrôle, écrit le .IMP et l'importe (Sage fermé, fenêtres de l'outil cachées), puis vérifie chaque facture.

    Renvoie {fichier: résultat} ; les factures importées passent à l'état « Importée dans Sage ».
    """
    from . import coffre
    from .__main__ import executable_import, lire_sage, ouvrir_base_sage
    from .sage_auto import executer

    c = config_toml.get("sage_import", {})
    fichier_sai = Path(c.get("fichier_entreprise", ""))
    exe = executable_import()
    if not fichier_sai.is_file() or not exe:
        raise RuntimeError("Fichier d'entreprise Sage ou outil d'import introuvable (page Sage 50).")
    etats = lire_sage(config_toml, lambda base: verifier_dans_sage(base, factures), str(fichier_sai))
    resultats = {f.fichier: "à importer" for f in factures}
    a_importer = []
    for f in factures:
        problemes = f.controles() + etats[f.fichier].problemes
        if problemes:
            resultats[f.fichier] = "non importée : " + " ; ".join(problemes)
        else:
            a_importer.append(f)
    if not a_importer:
        return resultats
    chemin = ecrire_imp_achats(a_importer, Path(racine) / "sortie" / "achats" / f"Achats_{datetime.now():%Y%m%d_%H%M%S}.IMP",
                               str(c.get("version", "12001")), str(c.get("pays", "1")))
    journal(f"Import de {len(a_importer)} facture(s) d'achat dans {fichier_sai.name}…")
    presentes: dict[str, bool] = {}

    def verifier(_resume: str = "") -> None:
        import time
        for _ in range(10):
            try:
                with ouvrir_base_sage(config_toml, fichier_sai) as base:
                    for f in a_importer:
                        presentes[f.fichier] = facture_presente(base, f.fournisseur_sage, f.numero)
                return
            except Exception:
                time.sleep(1)

    resultat = executer(exe, chemin, fichier_sai, coffre.lire(coffre.SAGE_IMPORT), pendant_resume=verifier,
                        delai=int(config_toml.get("automatique", {}).get("delai_import", 3600)))
    for f in a_importer:
        if presentes.get(f.fichier):
            f.etat = IMPORTEE
            resultats[f.fichier] = f"importée (n° {f.numero}, {f.total} $)"
        else:
            resultats[f.fichier] = "ÉCHEC : absente de Sage après l'import" + (
                " — " + " ; ".join(resultat.erreurs) if resultat.erreurs else "")
    for f in factures:
        journal(f"{f.fichier} : {resultats[f.fichier]}")
    return resultats
