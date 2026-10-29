"""Manuel d'utilisation selon le profil (demande du propriétaire du 2026-10-29) : la personne connectée ne reçoit que
les chapitres des pages que son profil lui permet de voir.

Le manuel complet est fabriqué par documentation/creer_manuel.py ; sa page HTML marque chaque chapitre de ses
pages (`<section class='chapitre' data-pages='5,8'>`, aucune page = chapitre pour tous) et chaque ligne du sommaire
de même. Ici, les chapitres non permis sont retirés, les chapitres restants renumérotés, le profil est écrit sur la
couverture, puis la page est imprimée en PDF par Microsoft Edge et gardée dans donnees/manuels/ (refaite à chaque
version ou si les pages du profil changent). Profil qui voit tout (ou aucune session) : le manuel complet.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

NOMS = {"fr": "Manuel_MVOGMBI_Sync", "en": "User_Manual_MVOGMBI_Sync"}
SECTION = re.compile(r"<section class='chapitre' data-pages='([^']*)'>.*?</section>", re.S)
LIGNE_SOMMAIRE = re.compile(r"<li data-pages='([^']*)'><span>\d+</span>(.*?)</li>", re.S)


def _dossiers(racine: Path) -> list[Path]:
    paquet = Path(__file__).resolve().parent.parent
    return [Path(racine), Path(racine) / "manuel", Path(racine) / "documentation", paquet / "documentation"]


def trouver(racine: Path, langue: str, extension: str) -> Path | None:
    """Manuel complet (PDF) ou sa page HTML (« .html ») : à côté du programme installé, sinon dans documentation/."""
    noms = ([NOMS["en"]] if langue == "en" else []) + [NOMS["fr"]]
    return next((d / f"{n}{extension}" for n in noms for d in _dossiers(racine) if (d / f"{n}{extension}").exists()),
                None)


def _permis(pages: str, permises: set[int]) -> bool:
    return not pages or any(int(p) in permises for p in pages.split(","))


def filtrer(page: str, permises: set[int], profil: str = "") -> str:
    """Page HTML du manuel sans les chapitres non permis, chapitres et sommaire renumérotés."""
    page = SECTION.sub(lambda m: m.group(0) if _permis(m.group(1), permises) else "", page)
    numero = iter(range(1, 1000))
    page = LIGNE_SOMMAIRE.sub(lambda m: f"<li><span>{next(numero)}</span>{m.group(2)}</li>"
                              if _permis(m.group(1), permises) else "", page)
    numero = iter(range(1, 1000))
    page = re.sub(r"<span class='num'>\d+</span>", lambda _m: f"<span class='num'>{next(numero)}</span>", page)
    if profil:
        page = page.replace("<div class=\"sous\">MVOGMBI_Sync — Clover → Sage 50</div>",
                            f"<div class=\"sous\">MVOGMBI_Sync — Clover → Sage 50</div>"
                            f"<div class=\"sous\" style=\"font-size:13pt\">{profil}</div>", 1)
    return page


def tout_permis(page: str, permises: set[int]) -> bool:
    return all(_permis(m.group(1), permises) for m in SECTION.finditer(page))


def manuel_du_profil(racine: Path, permises: set[int] | None, profil: str, langue: str = "fr") -> Path | None:
    """PDF à ouvrir : le manuel complet si le profil voit tout, sinon le manuel du profil (fabriqué au besoin)."""
    from .aide import VERSION
    from .design import LOGO
    from .export_tableau import pdf_depuis_html

    complet = trouver(racine, langue, ".pdf")
    source = trouver(racine, langue, ".html")
    if permises is None or source is None:
        return complet
    page = source.read_text(encoding="utf-8")
    if tout_permis(page, permises):
        return complet
    empreinte = hashlib.sha1(f"{VERSION}|{langue}|{sorted(permises)}|{profil}".encode("utf-8")).hexdigest()[:12]
    chemin = Path(racine) / "donnees" / "manuels" / f"{source.stem}_{empreinte}.pdf"
    if chemin.exists():
        return chemin
    titre_profil = (f"Manual for the “{profil}” profile" if langue == "en" else f"Manuel du profil « {profil} »")
    page = filtrer(page, permises, titre_profil)
    # images : chemins absolus (le PDF est fabriqué ailleurs que la page d'origine)
    page = page.replace("src='captures/", f"src='{source.parent.as_uri()}/captures/")
    page = page.replace("src=\"../mvogmbi_sync/ressources/logo.png\"", f"src=\"{Path(LOGO).as_uri()}\"")
    pdf_depuis_html(page, chemin, delai=300)
    return chemin
