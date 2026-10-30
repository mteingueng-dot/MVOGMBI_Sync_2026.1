"""Document d'architecture en PDF à partir de ARCHITECTURE.md (source unique, lisible aussi sur GitHub).

Le Markdown du document (titres, paragraphes, listes, tableaux, blocs de code) est converti ici sans bibliothèque de
plus ; les diagrammes de flux (blocs « mermaid ») sont dessinés par Mermaid dans Microsoft Edge sans fenêtre (un premier
passage les fige en images SVG, un second imprime la page en PDF, comme le manuel). Le document ne contient aucune
donnée réelle : il est publié.

    python documentation/creer_architecture.py
"""

from __future__ import annotations

import html
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ICI = Path(__file__).resolve().parent
SOURCE = ICI.parent / "ARCHITECTURE.md"
EDGE = [Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe")]
MERMAID = "https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.esm.min.mjs"

e = html.escape


def en_ligne(texte: str) -> str:
    """Gras, code et liens d'une ligne de Markdown."""
    morceaux = re.split(r"(`[^`]+`)", texte)
    sortie = []
    for m in morceaux:
        if m.startswith("`") and m.endswith("`") and len(m) > 1:
            sortie.append(f"<code>{e(m[1:-1])}</code>")
        else:
            m = e(m, quote=False)
            m = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", m)
            m = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"<a href='\2'>\1</a>", m)
            sortie.append(m)
    return "".join(sortie)


def convertir(markdown: str) -> str:
    lignes = markdown.splitlines()
    html_ = []
    i = 0
    while i < len(lignes):
        ligne = lignes[i]
        if ligne.startswith("```"):
            langage = ligne[3:].strip()
            bloc = []
            i += 1
            while i < len(lignes) and not lignes[i].startswith("```"):
                bloc.append(lignes[i])
                i += 1
            i += 1
            texte = "\n".join(bloc)
            html_.append(f"<div class='diagramme'><pre class='mermaid'>{e(texte)}</pre></div>" if langage == "mermaid"
                         else f"<pre><code>{e(texte)}</code></pre>")
            continue
        if m := re.match(r"(#{1,4}) (.+)", ligne):
            n = len(m.group(1))
            html_.append(f"<h{n}>{en_ligne(m.group(2))}</h{n}>")
        elif ligne.strip() == "---":
            html_.append("<hr>")
        elif ligne.startswith("|"):
            tableau = []
            while i < len(lignes) and lignes[i].startswith("|"):
                tableau.append([c.strip() for c in lignes[i].strip().strip("|").split("|")])
                i += 1
            entetes, corps = tableau[0], [r for r in tableau[1:] if not all(set(c) <= set("-: ") for c in r)]
            html_.append("<table><thead><tr>" + "".join(f"<th>{en_ligne(c)}</th>" for c in entetes) + "</tr></thead>"
                         "<tbody>" + "".join("<tr>" + "".join(f"<td>{en_ligne(c)}</td>" for c in r) + "</tr>"
                                             for r in corps) + "</tbody></table>")
            continue
        elif ligne.startswith("- "):
            elements = []
            while i < len(lignes) and lignes[i].startswith("- "):
                elements.append(f"<li>{en_ligne(lignes[i][2:])}</li>")
                i += 1
            html_.append("<ul>" + "".join(elements) + "</ul>")
            continue
        elif re.match(r"\d+\. ", ligne):  # liste numérotée
            elements = []
            while i < len(lignes) and re.match(r"\d+\. ", lignes[i]):
                elements.append(f"<li>{en_ligne(re.sub(r'^\d+\. ', '', lignes[i]))}</li>")
                i += 1
            html_.append("<ol>" + "".join(elements) + "</ol>")
            continue
        elif ligne.strip():
            paragraphe = [ligne]
            while i + 1 < len(lignes) and lignes[i + 1].strip() and not re.match(r"(#|```|\||- |---|\d+\. )", lignes[i + 1]):
                i += 1
                paragraphe.append(lignes[i])
            html_.append(f"<p>{en_ligne(' '.join(paragraphe))}</p>")
        i += 1
    return "\n".join(html_)


STYLE = """
@page { size: Letter; margin: 14mm 12mm; }
:root { --vert: #1f7a3a; --rouge: #c62828; --jaune: #f2b705; --texte: #1d2b22; --doux: #5b6b61; --bord: #dfe7e1; }
body { font-family: "Segoe UI", Arial, sans-serif; font-size: 10pt; color: var(--texte); line-height: 1.45; }
.bandeau { border-top: 6px solid var(--vert); padding-top: 8px; margin-bottom: 4px; }
h1 { color: var(--vert); font-size: 22pt; margin: 4px 0 2px; }
h2 { color: var(--vert); font-size: 15pt; border-bottom: 2px solid var(--jaune); padding-bottom: 3px;
     margin-top: 22px; page-break-after: avoid; }
h3 { font-size: 11.5pt; margin: 14px 0 4px; page-break-after: avoid; }
hr { display: none; }
code { font-family: Consolas, monospace; font-size: 9pt; background: #f1f5f2; padding: 0 3px; border-radius: 3px; }
pre code { display: block; padding: 8px; white-space: pre-wrap; }
table { width: 100%; border-collapse: collapse; margin: 8px 0 12px; font-size: 9pt; page-break-inside: avoid; }
th { background: var(--vert); color: #fff; text-align: left; padding: 5px 7px; font-weight: 600; }
td { padding: 5px 7px; border-bottom: 1px solid var(--bord); vertical-align: top; }
tr:nth-child(even) td { background: #f4f8f5; }
.diagramme { border: 1px solid var(--bord); border-radius: 6px; padding: 8px; margin: 10px 0 14px; text-align: center;
             page-break-inside: avoid; }
.diagramme svg { max-width: 100% !important; max-height: 215mm; height: auto; }
pre.mermaid { background: none; font-family: inherit; }
"""


def creer(sortie: Path | None = None, source: Path = SOURCE, titre: str = "Architecture MVOGMBI_Sync") -> Path:
    """Markdown `source` (titres, listes, tableaux, diagrammes Mermaid) -> PDF `sortie` ; sert aussi aux autres
    documents (creer_documents.py)."""
    sortie = sortie or ICI / "Architecture_MVOGMBI_Sync.pdf"
    corps = convertir(Path(source).read_text(encoding="utf-8"))
    page = f"""<!doctype html><html lang="fr"><head><meta charset="utf-8"><title>{e(titre)}</title>
<style>{STYLE}</style></head><body><div class="bandeau"></div>{corps}
<script type="module">
import mermaid from "{MERMAID}";
mermaid.initialize({{ startOnLoad: false, theme: "base", flowchart: {{ htmlLabels: false, useMaxWidth: true }},
  themeVariables: {{ primaryColor: "#e8f3ec", primaryBorderColor: "#1f7a3a", primaryTextColor: "#1d2b22",
                     lineColor: "#5b6b61", secondaryColor: "#fff8e1", tertiaryColor: "#f7faf8",
                     fontFamily: "Segoe UI, Arial, sans-serif", fontSize: "13px" }} }});
let n = 0;
for (const pre of document.querySelectorAll("pre.mermaid")) {{  // un à la fois : les mesures restent justes
  const {{ svg }} = await mermaid.render("diagramme" + (++n), pre.textContent);
  pre.outerHTML = svg;
}}
document.querySelector("script[type=module]").remove();
</script></body></html>"""
    sortie_html = sortie.with_suffix(".html")
    sortie_html.write_text(page, encoding="utf-8")
    edge = next((p for p in EDGE if p.exists()), None)
    if not edge:
        print("Microsoft Edge introuvable : seul le HTML est produit.")
        return sortie_html
    with tempfile.TemporaryDirectory() as profil:
        base = [str(edge), "--headless", "--disable-gpu", f"--user-data-dir={profil}"]
        # 1er passage : diagrammes dessinés puis figés dans la page (SVG)
        dessin = subprocess.run(base + ["--virtual-time-budget=30000", "--dump-dom", sortie_html.as_uri()],
                                check=True, timeout=180, capture_output=True)
        page_figee = dessin.stdout.decode("utf-8")
        if "<pre class=\"mermaid\"" in page_figee:
            raise RuntimeError("Diagrammes non dessinés (Mermaid inaccessible ?)")
        sortie_html.write_text("<!doctype html>" + page_figee, encoding="utf-8")
        # 2e passage : impression dans un fichier à côté, puis remplacement (Edge échoue sans rien dire si le PDF
        # est ouvert dans un lecteur)
        provisoire = sortie.with_name(sortie.stem + "_nouveau.pdf")
        provisoire.unlink(missing_ok=True)
        subprocess.run(base + ["--no-pdf-header-footer", f"--print-to-pdf={provisoire}", sortie_html.as_uri()],
                       check=True, timeout=180, capture_output=True)
    if not provisoire.exists():
        raise RuntimeError("PDF non créé par Edge.")
    try:
        provisoire.replace(sortie)
    except PermissionError:
        raise SystemExit(f"{sortie.name} est ouvert dans un autre programme : fermez-le, puis relancez. "
                         f"Le nouveau document est dans {provisoire.name}.") from None
    return sortie


if __name__ == "__main__":
    print(creer(Path(sys.argv[1]) if len(sys.argv) > 1 else None))
