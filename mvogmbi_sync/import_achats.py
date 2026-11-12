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

from . import depots
from .facture import TAUX_TPS, TAUX_TVQ
from .fournisseurs import IMPORTEE, Facture, archiver, archiver_deja_dans_sage
from .cache_lectures import vide_apres

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
    """TPS et TVQ de chaque ligne selon sa taxe (TPS + TVQ, une seule, ou aucune ; taxes.py), ajustées au cent sur les
    totaux de la facture (arrondis du fournisseur, 5 cents au plus) sur la dernière ligne qui porte la taxe."""
    from . import taxes as tx

    codes = [tx.code(l) for l in facture.lignes]
    taxes = [list(tx.montants(l.montant, c)) for l, c in zip(facture.lignes, codes)]
    for rang, total, lettre in ((0, facture.tps, "G"), (1, facture.tvq, "Q")):
        portent = [i for i, c in enumerate(codes) if lettre in c]
        ecart = total - sum(x[rang] for x in taxes)
        if portent and abs(ecart) <= Decimal("0.05"):
            taxes[portent[-1]][rang] += ecart
    return [(a, b) for a, b in taxes]


def bloc_achat(facture: Facture) -> list[str]:
    jour = date.fromisoformat(facture.date_facture)
    total = facture.total if facture.total is not None else facture.somme_lignes + facture.tps + facture.tvq
    lignes = ["<PurInvoice>", _texte(facture.fournisseur_sage),
              ",".join([f'"{len(facture.lignes)}"', '""', _texte(facture.numero), _texte(jour.strftime("%m-%d-%Y")),
                        _nombre(total, 2), '"0.00"', '"0"', '"0"', '"0.00"'])]
    for l, (tps, tvq) in zip(facture.lignes, taxes_par_ligne(facture)):
        quantite, prix = l.en_sage()
        champs = [_texte(l.numero_sage), _nombre(quantite, 4), _nombre(prix, 4), _nombre(l.montant, 2)]
        from . import taxes as tx

        code = tx.code(l)
        if "G" in code:
            champs += ['"TPS/TVH"', '"0"', '"1"', '"5.00"', _nombre(tps, 2)]
        if "Q" in code:
            champs += ['"TVQ"', '"0"', '"1"', '"9.975"', _nombre(tvq, 2)]
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


def deja_dans_sage(base, factures: list[Facture]) -> dict[str, str]:
    """Factures déjà saisies dans Sage pour leur fournisseur (même n°, avec ou sans préfixe) : {fichier : n° Sage}."""
    ids = {l["sName"].strip(): l["lId"] for l in base.requete("SELECT lId, sName FROM tvendor")}
    resultat, sources = {}, {}
    for f in factures:
        v = ids.get(f.fournisseur_sage)
        if v is None or not f.numero:
            continue
        if v not in sources:
            sources[v] = [(x["sSource"] or "").strip() for x in base.requete("SELECT sSource FROM tventr WHERE lVenId = %s",
                                                                               (v,))]
        pareille = next((s for s in sources[v] if meme_numero(s, f.numero)), "")
        if pareille:
            resultat[f.fichier] = pareille
    return resultat


def facture_presente(base, fournisseur_sage: str, numero: str) -> bool:
    lignes = base.requete("SELECT COUNT(*) n FROM tventr t JOIN tvendor v ON v.lId = t.lVenId "
                          "WHERE v.sName = %s AND TRIM(t.sSource) = %s", (fournisseur_sage, numero.strip()))
    return bool(lignes and lignes[0]["n"])


# --------------------------------------------------------------------------------------------- import
def sage_ouvert() -> bool:
    from .sage_bureau import sage_ouvert as ouvert

    return ouvert()


@vide_apres  # mémoire des lectures vidée après une écriture
def importer_achats(racine: Path, config_toml: dict, factures: list[Facture], journal=print,
                    clover: bool = True, courriel: bool = True) -> dict[str, str]:
    """Contrôle, écrit le .IMP et l'importe (Sage fermé, fenêtres de l'outil cachées), puis vérifie chaque facture.

    Renvoie {fichier: résultat} ; les factures importées passent à l'état « Importée ». `clover` faux : Sage
    seulement (services, ou facture déjà entrée dans Clover), le stock et le coût Clover ne changent pas.
    """
    from . import coffre
    from .__main__ import executable_import, lire_sage, ouvrir_base_sage
    from .sage_auto import executer

    c = config_toml.get("sage_import", {})
    fichier_sai = Path(c.get("fichier_entreprise", ""))
    exe = executable_import()
    if not fichier_sai.is_file() or not exe:
        raise RuntimeError("Fichier d'entreprise Sage ou outil d'import introuvable (page Sage 50).")
    if sage_ouvert():
        raise RuntimeError("Sage est ouvert : fermez-le avant l'import.")
    for f in factures:  # note de crédit : toujours en négatif dans Sage et dans Clover (stock qui diminue)
        f.signer()
    etats = lire_sage(config_toml, lambda base: verifier_dans_sage(base, factures), str(fichier_sai))
    resultats = {f.fichier: "à importer" for f in factures}
    a_importer = []
    for f in factures:
        if etats[f.fichier].deja_present and not f.controles():  # saisie à la main entre-temps
            archiver_deja_dans_sage(racine, f, etats[f.fichier].deja_present)
            resultats[f.fichier] = (f"déjà dans Sage (n° « {etats[f.fichier].deja_present} ») : archivée et retirée de "
                                    "la liste, sans import")
            continue
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
            from .operations_journalieres import ACHAT, noter as noter_operation

            noter_operation(racine, ACHAT, f.date_facture, f.numero, f.numero, f.fournisseur_sage, f.total)
            try:  # gardée pour consultation (page Rapports)
                archiver(racine, f)
            except OSError as exc:
                resultats[f.fichier] += f" ; archive non faite : {exc}"
        else:
            resultats[f.fichier] = "ÉCHEC : absente de Sage après l'import" + (
                " — " + " ; ".join(resultat.erreurs) if resultat.erreurs else "")
    importees = [f for f in a_importer if f.etat == IMPORTEE]
    for f in importees:  # dépôt autre que par défaut : la marchandise y passe aussitôt (depots.apres_import)
        if f.depot and not depots.est_defaut(f.depot):
            lignes = [(l.numero_sage, l.en_sage()[0]) for l in f.lignes if l.numero_sage]
            for m in depots.apres_import(racine, config_toml, f.numero, f.depot, lignes, vente=False,
                                         jour=f.date_facture or None, journal=journal):
                resultats[f.fichier] += "\n   " + m
    # Clover suit facture par facture (case de chaque facture) : stock + quantité reçue, coût = nouveau prix
    # d'achat (règle du 2026-10-28) ; `clover` faux : aucune facture ne touche Clover
    avec = factures_pour_clover(importees, clover)
    for f in importees:
        if f not in avec:
            resultats[f.fichier] += "\n   Clover : non mis à jour (case décochée sur la facture : Sage seulement)"
    if avec:
        mettre_a_jour_clover(racine, config_toml, avec, resultats)
    for f in factures:
        journal(f"{f.fichier} : {resultats[f.fichier]}")
    if courriel:  # import à la demande : compte rendu par courriel (la nuit : dans le compte rendu de la nuit)
        try:
            from .courriel import envoyer_bilan_factures_fournisseurs

            envoyer_bilan_factures_fournisseurs(config_toml, resultats)
        except Exception as exc:  # noqa: BLE001 — l'import est fait ; le courriel manque seulement
            journal(f"Courriel du compte rendu non envoyé : {exc}")
    return resultats


def factures_pour_clover(importees: list, clover: bool = True) -> list:
    """Factures importées dont le stock Clover suit : case « Mettre à jour le stock Clover » de chaque facture
    (demande du propriétaire du 2026-11-09) ; `clover` faux : aucune."""
    return [f for f in importees if clover and getattr(f, "maj_clover", True)]


def mettre_a_jour_clover(racine: Path, config_toml: dict, importees: list, resultats: dict) -> dict:
    """Stock et coût Clover des factures importées, dans le Clover du point de vente de leur dépôt (rien pour un dépôt
    sans Clover). Refaisable (« 🔁 Refaire la mise à jour Clover », demande du 2026-11-05) : le journal du stock
    Clover écarte les lignes déjà ajoutées."""
    try:
        from .points_vente import point_de_vente
        from .stock_clover import mettre_a_jour_factures

        par_depot: dict[str, list] = {}  # Clover du point de vente du dépôt de chaque facture
        for f in importees:
            par_depot.setdefault(depots.du_nom(config_toml, f.depot).nom, []).append(f)
        for nom, groupe in par_depot.items():
            depot = depots.du_nom(config_toml, nom)
            if not depot.avec_clover:  # entrepôt sans caisse : Clover ne change pas
                for f in groupe:
                    resultats[f.fichier] = resultats.get(f.fichier, "") + (
                        f"\n   Clover : dépôt « {nom} » sans point de vente Clover, rien à changer")
                continue
            pv = point_de_vente(config_toml, depot.points_vente[0])
            for fichier, messages in mettre_a_jour_factures(racine, Path(racine) / "config.toml", groupe, pv).items():
                if messages:
                    resultats[fichier] = resultats.get(fichier, "") + "\n   Clover : " + "\n   ".join(messages)
    except Exception as exc:  # noqa: BLE001
        for f in importees:
            resultats[f.fichier] = resultats.get(f.fichier, "") + f"\n   Clover non mis à jour : {exc}"
    return resultats
