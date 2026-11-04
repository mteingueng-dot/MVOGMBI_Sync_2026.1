"""« ⬇ Exporter ▾ » de l'application Windows (export_tableau) sur chaque tableau des pages web : Excel, CSV, PDF
et « 🖨 Imprimer » (PDF ouvert dans le navigateur, puis sa boîte d'impression).

Aucune page n'a à s'en occuper : le serveur ajoute le menu devant chaque tableau d'une page affichée (GET) et,
quand le lien est suivi (`exporter=<rang du tableau>&format=…`), refait la même page, en relit le tableau et
renvoie le fichier. Même droit que dans Windows : `Registre.peut_exporter` (profil sans export : pas de menu,
lien refusé)."""

from __future__ import annotations

import re
import tempfile
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlencode

from .serveur import Reponse, echapper as e

FORMATS = {"xlsx": ("Excel", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
           "csv": ("CSV", "text/csv; charset=utf-8"), "pdf": ("PDF", "application/pdf")}
DEBUT_TABLEAU = "<div class='defile'><table>"


def ajouter_menus(html: str, query: dict[str, str]) -> str:
    """Menu d'export devant chaque tableau de la page (rang = ordre dans la page)."""
    if DEBUT_TABLEAU not in html:
        return html
    # sans « calculer » / « actualiser » : l'export reprend la lecture gardée 5 min au lieu de tout relire
    base = {k: v for k, v in query.items() if k not in ("exporter", "format", "calculer", "actualiser")}
    morceaux = html.split(DEBUT_TABLEAU)
    sortie = [morceaux[0]]
    for rang, morceau in enumerate(morceaux[1:]):
        def lien(format_: str, libelle: str, cible: str = "") -> str:
            q = urlencode({**base, "exporter": rang, "format": format_})
            return f"<a href='?{e(q)}'{cible}>{libelle}</a>"

        sortie.append("<details class='exporter'><summary>⬇ Exporter ▾</summary><div>"
                      + lien("xlsx", "📗 Excel") + lien("csv", "📄 CSV") + lien("pdf", "📕 PDF")
                      + lien("imprimer", "🖨 Imprimer…", " target='_blank'") + "</div></details>"
                      + DEBUT_TABLEAU + morceau)
    return "".join(sortie)


class _Lecteur(HTMLParser):
    """Tableaux de la page : titre (dernier <h2> ou <h1> avant le tableau), en-têtes, lignes en texte."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tableaux: list[dict] = []
        self.titre = ""
        self._titre_en_cours: list[str] | None = None
        self._ignorer = 0  # <span class='etat'> du titre (nombre de lignes), <summary> du menu
        self._table: dict | None = None
        self._ligne: list[str] | None = None
        self._cellule: list[str] | None = None
        self._entete_ligne = False

    def handle_starttag(self, balise, attributs):
        classes = dict(attributs).get("class") or ""
        if balise in ("h1", "h2") and self._table is None:
            self._titre_en_cours = []
        elif balise == "span" and self._titre_en_cours is not None and "etat" in classes:
            self._ignorer += 1
        elif balise == "table":
            self._table = {"titre": self.titre, "entetes": [], "lignes": []}
        elif balise == "tr" and self._table is not None:
            self._ligne, self._entete_ligne = [], False
        elif balise in ("td", "th") and self._ligne is not None:
            self._cellule = []
            self._entete_ligne = self._entete_ligne or balise == "th"
        elif balise == "input" and self._cellule is not None:  # case à cocher d'une liste : ☑ / ☐
            a = dict(attributs)
            if a.get("type") == "checkbox":
                self._cellule.append("☑" if "checked" in a else "☐")

    def handle_endtag(self, balise):
        if balise in ("h1", "h2") and self._titre_en_cours is not None:
            self.titre = " ".join("".join(self._titre_en_cours).split())
            self._titre_en_cours = None
        elif balise == "span" and self._ignorer:
            self._ignorer -= 1
        elif balise in ("td", "th") and self._cellule is not None and self._ligne is not None:
            self._ligne.append(" ".join("".join(self._cellule).split()))
            self._cellule = None
        elif balise == "tr" and self._ligne is not None and self._table is not None:
            if self._entete_ligne and not self._table["entetes"]:
                self._table["entetes"] = self._ligne
            else:
                self._table["lignes"].append(self._ligne)
            self._ligne = None
        elif balise == "table" and self._table is not None:
            self.tableaux.append(self._table)
            self._table = None

    def handle_data(self, texte):
        if self._ignorer:
            return
        if self._cellule is not None:
            self._cellule.append(texte)
        elif self._titre_en_cours is not None:
            self._titre_en_cours.append(texte)


def tableaux(html: str) -> list[dict]:
    lecteur = _Lecteur()
    lecteur.feed(re.sub(r"(?is)<details class='exporter'>.*?</details>", "", html))
    return lecteur.tableaux


def nom_fichier(titre: str) -> str:
    from ..export_tableau import nom_de_fichier

    return nom_de_fichier(titre or "Tableau")


def fichier(racine: Path, html: str, rang: str, format_: str) -> Reponse:
    """Fichier du tableau n° `rang` de la page `html` (Excel, CSV, PDF ; « imprimer » = PDF affiché)."""
    from ..export_tableau import ecrire_csv, ecrire_excel
    from ..pdf_documents import tableau

    try:
        t = tableaux(html)[int(rang)]
    except (ValueError, IndexError):
        return Reponse(404, "Tableau introuvable : rouvrez la page.", "text/plain; charset=utf-8")
    titre = t["titre"] or "Tableau"
    entetes = t["entetes"] or [f"Colonne {i + 1}" for i in range(max((len(l) for l in t["lignes"]), default=0))]
    lignes = [l + [""] * (len(entetes) - len(l)) for l in t["lignes"]]
    sorte = "pdf" if format_ == "imprimer" else format_
    if sorte not in FORMATS:
        return Reponse(400, "Format inconnu.", "text/plain; charset=utf-8")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as dossier:
        chemin = Path(dossier) / f"export.{sorte}"
        if sorte == "xlsx":
            ecrire_excel(chemin, titre, entetes, lignes)
        elif sorte == "csv":
            ecrire_csv(chemin, entetes, lignes)
        else:
            tableau(chemin, racine, titre, entetes, lignes)
        contenu = chemin.read_bytes()
    nom = f"{nom_fichier(titre)}.{sorte}"
    disposition = "inline" if format_ == "imprimer" else "attachment"
    from urllib.parse import quote

    return Reponse(corps=contenu, type=FORMATS[sorte][1],
                   entetes={"Content-Disposition": f"{disposition}; filename=\"export.{sorte}\"; "
                                                   f"filename*=UTF-8''{quote(nom)}"})


STYLE_EXPORT = """
details.exporter { float: right; position: relative; margin: -2px 0 4px 8px; z-index: 5; }
details.exporter summary { list-style: none; cursor: pointer; padding: 5px 12px; border: 1px solid var(--bord);
  border-radius: 6px; background: var(--carte); font-size: 13px; }
details.exporter summary::-webkit-details-marker { display: none; }
details.exporter > div { position: absolute; right: 0; background: var(--carte); border: 1px solid var(--bord);
  border-radius: 6px; box-shadow: 0 4px 12px rgba(0,0,0,.12); min-width: 150px; }
details.exporter a { display: block; padding: 7px 12px; text-decoration: none; color: var(--texte); font-size: 13px; }
details.exporter a:hover { background: var(--menu-survol); }
.defile { clear: both; }
"""
