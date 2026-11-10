"""Version Word (.docx) de chaque document, à partir de sa page HTML déjà fabriquée (creer_documents.py,
creer_manuel.py) : page d'accueil, sommaire, titres, tableaux, diagrammes et captures (demande du propriétaire du
2026-11-09 : « pour chaque document … aussi en format Word »).

Les diagrammes (SVG figés par le 1er passage de Mermaid) sont photographiés en PNG par Edge / Chrome sans fenêtre ;
Microsoft Word ouvre ensuite la page et l'enregistre en .docx, images intégrées au fichier. Sortie :
documentation/Word/<nom>.docx.

    python documentation/creer_word.py [nom…]
"""

from __future__ import annotations

import re
import sys
import tempfile
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI))
from creer_architecture import NAVIGATEURS, _lancer  # noqa: E402

SORTIE = ICI / "Word"
LARGEUR_MAX = 660  # largeur utile d'une page Letter en points d'écran (marges de 2 cm)
HAUTEUR_MAX = 860

# Word ne connaît ni flex ni les sauts de page CSS « break-after » : la page d'accueil et le sommaire sont refaits
STYLE_WORD = """
<style>
.couverture { display: block; text-align: center; padding-top: 120px; border-top: none; height: auto;
              page-break-after: auto; }
.couverture div, .couverture p, .sommaire, .sommaire li, .toc, .toc li { page-break-after: auto;
              page-break-before: auto; }
h1 { page-break-before: auto; }
.couverture .grand { font-size: 28pt; font-weight: bold; color: #1f7a3a; }
.couverture .sous { font-size: 14pt; color: #5b6b61; }
.couverture .infos { font-size: 10pt; color: #5b6b61; margin-top: 40px; }
.couverture .filet { text-align: center; }
.diagramme { border: none; text-align: center; }
figure { margin: 8px 0; text-align: center; }
figcaption { font-style: italic; color: #5b6b61; text-align: center; }
body { font-family: "Segoe UI", Arial, sans-serif; font-size: 10pt; color: #1d2b22; }
h1 { font-size: 20pt; color: #1f7a3a; page-break-after: avoid; }
h2 { font-size: 15pt; color: #1f7a3a; border-bottom: solid #f2b705 1.5pt; page-break-after: avoid;
     margin-top: 18pt; }
h3 { font-size: 11.5pt; color: #13772d; page-break-after: avoid; }
hr { display: none; }
table { border-collapse: collapse; width: 100%; font-size: 9pt; }
th { background: #1f7a3a; color: #ffffff; text-align: left; padding: 4px 6px; }
td { border-bottom: solid #dfe7e1 1pt; padding: 4px 6px; vertical-align: top; }
code { font-family: Consolas, monospace; font-size: 9pt; background: #f1f5f2; }
.note { background: #f4f8f5; border-left: solid #1f7a3a 3pt; padding: 6px; }
</style>
"""
SAUT = "<br clear=all style='page-break-before:always'>"


def _png_du_svg(svg: str, dossier: Path, n: int) -> tuple[Path, int, int] | None:
    """Image PNG d'un diagramme SVG (taille d'affichage lue sur la balise), le double en pixels pour la netteté."""
    w = re.search(r'\swidth="([\d.]+)', svg[:600])
    h = re.search(r'\sheight="([\d.]+)', svg[:600])
    if not (w and h):
        return None
    largeur, hauteur = int(float(w.group(1))) + 4, int(float(h.group(1))) + 4
    page = dossier / f"d{n}.html"
    page.write_text("<!doctype html><html><head><meta charset='utf-8'><style>html,body{margin:0;background:#fff}"
                    "svg{display:block}</style></head><body>" + svg + "</body></html>", encoding="utf-8")
    png = dossier / f"d{n}.png"
    for nav in (p for p in NAVIGATEURS if p.exists()):
        _lancer(nav, ["--hide-scrollbars", "--force-device-scale-factor=2", f"--window-size={largeur},{hauteur}",
                      f"--screenshot={png}", page.as_uri()])
        if png.exists() and png.stat().st_size:
            return png, largeur, hauteur
    return None


def _a_l_echelle(largeur: int, hauteur: int) -> tuple[int, int]:
    k = min(1.0, LARGEUR_MAX / largeur, HAUTEUR_MAX / hauteur)
    return int(largeur * k), int(hauteur * k)


def page_pour_word(html: str, dossier: Path) -> str:
    """Page HTML du document adaptée à Word : diagrammes en PNG, captures à la largeur de la page, sauts de page."""
    n = 0

    def remplacer(m: re.Match) -> str:
        nonlocal n
        n += 1
        image = _png_du_svg(m.group(0), dossier, n)
        if not image:
            return ""
        png, largeur, hauteur = image
        largeur, hauteur = _a_l_echelle(largeur, hauteur)
        return f"<img src='{png.as_uri()}' width='{largeur}' height='{hauteur}'>"

    html = re.sub(r"<svg[\s\S]*?</svg>", remplacer, html)
    html = re.sub(r"<script[\s\S]*?</script>", "", html)

    # captures du manuel : largeur de la page
    def capture(m: re.Match) -> str:
        return m.group(1) + f" width='{LARGEUR_MAX}'" + m.group(2)

    html = re.sub(r"(<img src='captures/[^']+')([^>]*>)", capture, html)
    # sauts de page : après la page d'accueil, après le sommaire, avant chaque chapitre du manuel
    # (la page figée par le navigateur écrit les attributs entre guillemets doubles)
    html = re.sub(r"(<section class=[\"']couverture[\"']>[\s\S]*?</section>)", r"\1" + SAUT, html, count=1)
    html = re.sub(r"(<section class=[\"']sommaire[\"']>[\s\S]*?</section>)", r"\1" + SAUT, html, count=1)
    html = re.sub(r"(<section class=[\"']chapitre[\"'])", SAUT + r"\1", html)
    html = re.sub(r"(<div class=[\"']couverture[\"']>[\s\S]*?<div class=[\"']infos[\"']>[\s\S]*?</div>\s*</div>)",
                  r"\1" + SAUT, html, count=1)
    # logo de la page d'accueil : Word ne lit pas la largeur donnée par le style
    from PIL import Image

    with Image.open(ICI.parent / "mvogmbi_sync" / "ressources" / "logo.png") as logo:
        haut = round(150 * logo.height / logo.width)
    html = re.sub(r"(<img src=[\"'][^\"']*logo\.png[\"'])", rf"\1 width='150' height='{haut}'", html)
    # sommaire du manuel : le numéro écrit dans l'élément ferait double emploi avec la liste numérotée de Word
    html = re.sub(r"(<li data-pages=[\"'][^\"']*[\"']>)<span>\d+</span>", r"\1", html)
    # Word ne connaît pas <section> : ses classes (page d'accueil centrée…) ne s'appliqueraient pas
    html = re.sub(r"<section\b", "<div", html).replace("</section>", "</div>")
    return html.replace("</head>", STYLE_WORD + "</head>", 1)


def vers_word(source_html: Path, docx: Path) -> Path:
    import pythoncom
    import win32com.client

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        dossier = Path(tmp)
        texte = source_html.read_text(encoding="utf-8")
        # les chemins relatifs (captures, logo) restent valables : page écrite à côté de l'originale
        page = source_html.with_name(source_html.stem + "_word.html")
        page.write_text(page_pour_word(texte, dossier), encoding="utf-8")
        pythoncom.CoInitialize()
        word = win32com.client.DispatchEx("Word.Application")
        word.Visible = False
        word.DisplayAlerts = 0
        try:
            doc = word.Documents.Open(str(page), False, True, False)
            doc.ActiveWindow.View.Type = 3  # page
            ps = doc.PageSetup
            ps.PageWidth, ps.PageHeight = 612, 792  # Letter
            ps.TopMargin = ps.BottomMargin = 50
            ps.LeftMargin = ps.RightMargin = 45
            for forme in list(doc.InlineShapes):  # images intégrées au fichier, plus de lien vers le disque
                try:
                    if forme.LinkFormat is not None:
                        forme.LinkFormat.SavePictureWithDocument = True
                        forme.LinkFormat.BreakLink()
                except Exception:
                    pass
            for forme in list(doc.Shapes):
                try:
                    forme.LinkFormat.SavePictureWithDocument = True
                    forme.LinkFormat.BreakLink()
                except Exception:
                    pass
            docx.parent.mkdir(exist_ok=True)
            docx.unlink(missing_ok=True)
            doc.SaveAs2(str(docx), 16)  # wdFormatDocumentDefault
            doc.Close(False)
        finally:
            word.Quit()
            page.unlink(missing_ok=True)
    return docx


def documents() -> list[tuple[Path, Path]]:
    from creer_documents import DOCUMENTS

    paires = [(ICI / Path(pdf).with_suffix(".html").name, SORTIE / Path(pdf).with_suffix(".docx").name)
              for _source, pdf, _titre in DOCUMENTS]
    paires += [(ICI / "Manuel_MVOGMBI_Sync.html", SORTIE / "Manuel_MVOGMBI_Sync.docx"),
               (ICI / "User_Manual_MVOGMBI_Sync.html", SORTIE / "User_Manual_MVOGMBI_Sync.docx")]
    return paires


def creer_tout(noms: list[str] | None = None) -> list[Path]:
    faits = []
    for html, docx in documents():
        if noms and not any(n.lower() in docx.name.lower() for n in noms):
            continue
        if not html.exists():
            print("absent :", html.name)
            continue
        try:
            faits.append(vers_word(html, docx))
        except PermissionError:  # document ouvert dans Word : gardé tel quel, les autres sont faits
            print("ouvert dans un autre programme, non refait :", docx.name)
            continue
        print(docx.name)
    return faits


if __name__ == "__main__":
    creer_tout(sys.argv[1:] or None)
