"""Boutons « 📁 Dossier des données », « Dossier des factures », « Dossier des archives », « 📂 Ouvrir le dossier » et
« Choisir… » / « Parcourir… » de l'application Windows : le navigateur ne peut pas ouvrir un dossier du serveur, la
page web montre donc son contenu (sous-dossiers et fichiers, avec date et taille) et chaque fichier se télécharge ;
le choix d'un dossier ou d'un fichier .SAI du serveur revient dans la page de réglage.

Seuls les dossiers prévus sont montrés (jamais au-dessus de leur racine) ; chaque dossier a le droit de l'entrée de
menu qui porte son bouton dans Windows."""

from __future__ import annotations

import mimetypes
import string
from datetime import datetime
from pathlib import Path
from urllib.parse import quote, urlencode

from .pages import Contexte, Fonction, page
from .serveur import Reponse, echapper as e

# nom -> (titre de la page, fonction(ctx) -> dossier racine)
DOSSIERS = {
    "donnees": ("Dossier des données", lambda ctx: ctx.racine / "donnees"),
    "factures": ("Dossier des factures", lambda ctx: ctx.racine / "donnees" / "factures_fournisseurs"),
    "archives": ("Dossier des archives", lambda ctx: ctx.racine / "donnees" / "archives" / "factures_fournisseurs"),
    "sauvegardes": ("Dossier des sauvegardes", lambda ctx: _dossier_sauvegardes(ctx)),
}
# cible du choix -> (page de réglage, champ, fichiers acceptés)
CHOIX = {"sauvegarde": ("/sauvegarde", "dossier", None), "sai": ("/admin/sage", "fichier", ".sai")}


def _dossier_sauvegardes(ctx: Contexte) -> Path:
    from .. import sauvegarde as sv

    return sv.dossier(ctx.racine, ctx.config)


def _taille(n: int) -> str:
    for unite in ("o", "Ko", "Mo", "Go"):
        if n < 1024 or unite == "Go":
            return f"{n:.0f} {unite}" if unite == "o" else f"{n:.1f} {unite}".replace(".", ",")
        n /= 1024
    return ""


def _sous_chemin(racine: Path, relatif: str) -> Path | None:
    """Chemin sous la racine, jamais au-dessus (« .. » et chemins absolus refusés)."""
    try:
        cible = (racine / relatif).resolve()
        cible.relative_to(racine.resolve())
    except (ValueError, OSError):
        return None
    return cible


def dossier(ctx: Contexte, nom: str) -> Reponse:
    titre, racine_de = DOSSIERS[nom]
    racine = racine_de(ctx)
    relatif = ctx.req.query.get("d", "")
    cible = _sous_chemin(racine, relatif)
    if cible is None:
        return Reponse(404, page(ctx, titre, "<p>Dossier introuvable.</p>"))
    if cible.is_file():
        nom_fichier = cible.name
        return Reponse(corps=cible.read_bytes(), type=mimetypes.guess_type(nom_fichier)[0] or "application/octet-stream",
                       entetes={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(nom_fichier)}"})
    if not cible.is_dir():
        return Reponse(corps=page(ctx, titre, f"<div class='ligne-etat'>{e(str(cible))} : dossier absent.</div>"))
    adresse = f"/dossier-{nom}"
    lignes = []
    if cible != racine.resolve():
        parent = cible.parent.relative_to(racine.resolve()).as_posix()
        lignes.append(f"<tr><td><a href='{adresse}?{e(urlencode({'d': '' if parent == '.' else parent}))}'>⬆ ..</a>"
                      "</td><td></td><td></td><td></td></tr>")
    try:
        elements = sorted(cible.iterdir(), key=lambda x: (not x.is_dir(), x.name.casefold()))
    except OSError as erreur:
        elements = []
        lignes.append(f"<tr><td colspan='4' class='vide'>{e(str(erreur))}</td></tr>")
    for x in elements:
        try:
            info = x.stat()
        except OSError:
            continue
        lien = x.relative_to(racine.resolve()).as_posix()
        lignes.append(f"<tr><td><a href='{adresse}?{e(urlencode({'d': lien}))}'>{'📁' if x.is_dir() else '📄'} "
                      f"{e(x.name)}</a></td><td>{'Dossier' if x.is_dir() else e(x.suffix.lstrip('.').upper())}</td>"
                      f"<td>{datetime.fromtimestamp(info.st_mtime):%Y-%m-%d %H:%M}</td>"
                      f"<td class='n'>{'' if x.is_dir() else _taille(info.st_size)}</td></tr>")
    if not elements:
        lignes.append("<tr><td colspan='4' class='vide'>Aucune ligne.</td></tr>")
    corps = (f"<div class='ligne-etat'>📂 {e(str(cible))} (sur le serveur) : cliquez sur un fichier pour le "
             "télécharger.</div><div class='defile'><table><tr><th>Nom</th><th>Type</th><th>Modifié le</th>"
             f"<th class='n'>Taille</th></tr>{''.join(lignes)}</table></div>")
    return Reponse(corps=page(ctx, titre, corps))


def parcourir(ctx: Contexte, cible: str) -> Reponse:
    """« Choisir… » / « Parcourir… » : dossiers (et fichiers .SAI) du serveur ; « Choisir » renvoie le chemin à la page
    de réglage, qui le met dans son champ (à enregistrer ensuite, comme dans Windows)."""
    retour, champ, extension = CHOIX[cible]
    chemin = ctx.req.query.get("chemin", "")
    titre = "Choisir un dossier" if extension is None else "Fichier d'entreprise Sage (*.SAI)"
    lignes = []
    if not chemin:  # lecteurs du serveur
        for lettre in string.ascii_uppercase:
            lecteur = Path(f"{lettre}:/")
            if lecteur.exists():
                lignes.append(f"<tr><td><a href='?{e(urlencode({'chemin': str(lecteur)}))}'>💽 {lettre}:</a></td>"
                              "<td></td></tr>")
        dossier_ = None
    else:
        dossier_ = Path(chemin)
        if dossier_.is_file():
            dossier_ = dossier_.parent
        parent = "" if dossier_.parent == dossier_ else str(dossier_.parent)
        lignes.append(f"<tr><td><a href='?{e(urlencode({'chemin': parent}))}'>⬆ ..</a></td><td></td></tr>")
        try:
            elements = sorted(dossier_.iterdir(), key=lambda x: (not x.is_dir(), x.name.casefold()))
        except OSError as erreur:
            elements = []
            lignes.append(f"<tr><td colspan='2' class='vide'>{e(str(erreur))}</td></tr>")
        for x in elements:
            try:
                est_dossier = x.is_dir()
            except OSError:
                continue
            if est_dossier:
                lignes.append(f"<tr><td><a href='?{e(urlencode({'chemin': str(x)}))}'>📁 {e(x.name)}</a></td><td></td>"
                              "</tr>")
            elif extension and x.suffix.lower() == extension:
                lignes.append(f"<tr><td>📄 {e(x.name)}</td><td><a class='ouvrir' href='{retour}?"
                              f"{e(urlencode({champ: str(x)}))}'>✔ Choisir</a></td></tr>")
    choisir = (f"<a class='ouvrir' href='{retour}?{e(urlencode({champ: str(dossier_)}))}'>✔ Choisir ce dossier</a>"
               if dossier_ is not None and extension is None else "")
    corps = (f"<div class='barre-onglet'><strong>{e(str(dossier_) if dossier_ else 'Ordinateur (serveur)')}</strong>"
             f"<span class='a-droite'>{choisir} <a class='ouvrir' href='{retour}'>Annuler</a></span></div>"
             f"<div class='defile'><table><tr><th>Nom</th><th></th></tr>{''.join(lignes)}</table></div>")
    return Reponse(corps=page(ctx, titre, corps))


def archives_fournisseurs(ctx: Contexte) -> Reponse:
    """Onglet « Factures fournisseurs archivées » de PageRapports : Rechercher :, « 📄 Voir la facture », « 📗 Détail
    (Excel) », « 📂 Dossier des archives », résumé, tableau (une facture choisie)."""
    from decimal import Decimal

    from ..fournisseurs import archives
    from .consultations import Section, tableau_section
    from .pages_rapports_web import onglets

    liste = archives(ctx.racine)
    texte = (ctx.req.query.get("texte") or "").strip()
    if texte:
        cle = texte.casefold()
        liste = [a for a in liste if cle in " ".join(str(a.get(k, "")) for k in (
            "date_facture", "fournisseur_sage", "fournisseur_lu", "numero")).casefold()]
    choisi = ctx.req.query.get("a", "")
    a = next((x for x in liste if x["chemin"] == choisi), None)
    voir = ctx.req.query.get("voir")
    if voir and a is None:
        message = "<p class='erreur-texte'>Choisissez une facture dans la liste.</p>"
    elif voir:
        json_ = Path(a["chemin"])
        cible = (json_.with_suffix(".xlsx") if voir == "detail" else
                 json_.with_name(a["fichier_archive"]) if a.get("fichier_archive") else
                 ctx.racine / "donnees" / "factures_fournisseurs" / a.get("fichier", ""))
        if voir == "detail" and not ctx.reg.peut_exporter(ctx.u):
            return Reponse(403, page(ctx, "Factures fournisseurs archivées", "<p>Export non permis.</p>"))
        if not cible.is_file():
            message = f"<p class='erreur-texte'>Fichier introuvable : {e(cible.name)}</p>"
        else:
            type_ = mimetypes.guess_type(cible.name)[0] or "application/octet-stream"
            dispo = "inline" if type_.startswith(("image/", "application/pdf")) else "attachment"
            return Reponse(corps=cible.read_bytes(), type=type_,
                           entetes={"Content-Disposition": f"{dispo}; filename*=UTF-8''{quote(cible.name)}"})
    else:
        message = ""
    lignes = []
    total = Decimal(0)
    for x in liste:
        montant = Decimal(x["total"]) if x.get("total") not in (None, "") else None
        total += montant or 0
        lignes.append([f"<input type='radio' name='a' value='{e(x['chemin'])}'{' checked' if x is a else ''}>",
                       e(x.get("date_facture", "")), e(x.get("fournisseur_sage") or x.get("fournisseur_lu", "")),
                       e(x.get("numero", "")), "" if montant is None else f"{montant:,.2f} $".replace(",", " ").replace(".", ","),
                       str(len(x.get("lignes", []))), e(x.get("archivee_le", "").replace("T", " "))])
    detail = ("<button class='second' name='voir' value='detail'>📗 Détail (Excel)</button>"
              if ctx.reg.peut_exporter(ctx.u) else "")
    corps = (onglets("Factures fournisseurs archivées", ctx) + "<div class='onglet-corps'>" + message
             + "<form method='get'><div class='barre-onglet'><div><label>Rechercher :</label><input name='texte' "
               f"value='{e(texte)}' size='28'></div><button class='second'>🔍</button><button class='second' "
               f"name='voir' value='piece'>📄 Voir la facture</button>{detail}<a class='ouvrir' "
               "href='/dossier-archives'>📂 Dossier des archives</a></div>"
             + f"<div class='ligne-etat'>{len(liste)} facture(s) archivée(s), total "
               f"{f'{total:,.2f} $'.replace(',', ' ').replace('.', ',')}.</div>"
             + tableau_section(Section("Factures fournisseurs archivées", ["", "Date", "Fournisseur", "N°", "Total",
                                                                           "Lignes", "Archivée le"], lignes,
                                       html=set(range(7))))
             + "</form></div>")
    return Reponse(corps=page(ctx, "Factures fournisseurs archivées", corps))


# Dossier des données : tout donnees/ (comptes, pointages…) : réservé à qui gère les utilisateurs
FONCTIONS = [
    Fonction("/archives-fournisseurs", "Factures fournisseurs archivées", "rapports", archives_fournisseurs, "🗄",
             "Fournisseur", menu=False),
    Fonction("/dossier-donnees", "utilisateurs", "utilisateurs", lambda ctx: dossier(ctx, "donnees"), "📁",
             "Administration", menu=False, page_entiere=True),
    Fonction("/dossier-factures", "Factures fournisseurs", "fournisseurs", lambda ctx: dossier(ctx, "factures"), "📁",
             "Fournisseur", menu=False, page_entiere=True),
    Fonction("/dossier-archives", "Factures fournisseurs archivées", "rapports", lambda ctx: dossier(ctx, "archives"),
             "📁", "Fournisseur", menu=False),
    Fonction("/dossier-sauvegardes", "Sauvegarde des données", "automatisation", lambda ctx: dossier(ctx, "sauvegardes"),
             "📂", "Administration", menu=False),
    Fonction("/parcourir-sauvegarde", "Sauvegarde des données", "automatisation",
             lambda ctx: parcourir(ctx, "sauvegarde"), "📁", "Administration", menu=False),
    Fonction("/parcourir-sai", "sage", "sage", lambda ctx: parcourir(ctx, "sai"), "📁", "Administration", menu=False,
             page_entiere=True),
]
