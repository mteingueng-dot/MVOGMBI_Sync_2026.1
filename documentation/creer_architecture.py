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
# Chrome en secours : Edge avec une mise à jour en attente rend une page vide sans erreur en mode sans fenêtre
# (constat du 2026-11-06)
NAVIGATEURS = EDGE + [Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
                      Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe")]


def _lancer(navigateur: Path, arguments: list[str]) -> bytes:
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as profil:
        r = subprocess.run([str(navigateur), "--headless", "--disable-gpu", f"--user-data-dir={profil}", *arguments],
                           timeout=180, capture_output=True, stdin=subprocess.DEVNULL)
    return r.stdout


def page_dessinee(uri: str, budget: int = 30000) -> str:
    """DOM de la page après ses scripts, par le premier navigateur qui rend quelque chose."""
    for nav in (p for p in NAVIGATEURS if p.exists()):
        sortie = _lancer(nav, [f"--virtual-time-budget={budget}", "--dump-dom", uri]).decode("utf-8")
        if sortie.strip():
            return sortie
    raise RuntimeError("Aucun navigateur (Edge, Chrome) n'a rendu la page.")


def imprimer_pdf(uri: str, pdf: Path) -> bool:
    """Page -> PDF (fichier provisoire puis remplacement) ; False si aucun navigateur ne l'a écrit."""
    provisoire = pdf.with_name(pdf.stem + "_nouveau.pdf")
    for nav in (p for p in NAVIGATEURS if p.exists()):
        provisoire.unlink(missing_ok=True)
        _lancer(nav, ["--no-pdf-header-footer", f"--print-to-pdf={provisoire}", uri])
        if provisoire.exists() and provisoire.stat().st_size:
            try:
                provisoire.replace(pdf)
            except PermissionError:
                raise SystemExit(f"{pdf.name} est ouvert dans un autre programme : fermez-le, puis relancez.")
            return True
    return False
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
table { width: 100%; border-collapse: collapse; margin: 8px 0 12px; font-size: 9pt; }
li:nth-last-child(2), tr:nth-last-child(2) { break-after: avoid; page-break-after: avoid; }
li:last-child:not(:first-child), tr:last-child { break-before: avoid; page-break-before: avoid; }
p, li { orphans: 2; widows: 2; }
thead { display: table-header-group; }
tr { break-inside: avoid; page-break-inside: avoid; }
p:has(+ table), p:has(+ ul), p:has(+ ol), p:has(+ .diagramme), p:has(+ pre) { break-after: avoid; page-break-after: avoid; }
h2 + h3 { break-before: avoid; }
th { background: var(--vert); color: #fff; text-align: left; padding: 5px 7px; font-weight: 600; }
td { padding: 5px 7px; border-bottom: 1px solid var(--bord); vertical-align: top; }
tr:nth-child(even) td { background: #f4f8f5; }
.diagramme { border: 1px solid var(--bord); border-radius: 6px; padding: 4px; margin: 10px 0 14px; text-align: center;
             page-break-inside: avoid; }
.diagramme svg { max-width: none !important; }
@page paysage { size: Letter landscape; margin: 8mm 8mm; }
section.tenir { break-inside: avoid; page-break-inside: avoid; }
section.paysage { page: paysage; }
section.paysage .diagramme { margin-top: 4px; }
pre.mermaid { background: none; font-family: inherit; }
/* page d'accueil et sommaire (demande du propriétaire du 2026-11-09) */
.couverture { height: 240mm; display: flex; flex-direction: column; justify-content: center; align-items: center;
              text-align: center; border-top: 10px solid var(--vert); break-after: page; page-break-after: always; }
.couverture img { width: 150px; margin-bottom: 26px; }
.couverture .grand { font-size: 28pt; font-weight: 700; color: var(--vert); line-height: 1.2; }
.couverture .sous { font-size: 14pt; color: var(--doux); margin-top: 8px; }
.couverture .filet { display: flex; gap: 6px; margin: 22px 0; justify-content: center; }
.couverture .filet span { display: inline-block; height: 6px; border-radius: 3px; }
.couverture .infos { margin-top: 40px; font-size: 10pt; color: var(--doux); max-width: 150mm; }
.sommaire { break-after: page; page-break-after: always; }
.sommaire h2 { margin-top: 0; }
.sommaire ol { font-size: 10.5pt; line-height: 1.7; }
"""
EDITEUR = "Concept Informatique inc."
LOGO = ICI.parent / "mvogmbi_sync" / "ressources" / "logo.png"


def version_application() -> str:
    texte = (ICI.parent / "mvogmbi_sync" / "aide.py").read_text(encoding="utf-8")
    m = re.search(r'^VERSION\s*=\s*"([^"]+)"', texte, re.M)
    return m.group(1) if m else ""


def accueil(markdown: str, titre: str) -> tuple[str, str]:
    """Page d'accueil (logo, titre du document, produit, version, éditeur) et sommaire des sections « ## » ;
    rend (html, markdown sans le titre « # » ni la ligne de version, repris par la page d'accueil)."""
    lignes = markdown.splitlines()
    grand, infos = titre, ""
    if lignes and lignes[0].startswith("# "):
        grand = lignes.pop(0)[2:].strip()
        while lignes and not lignes[0].strip():
            lignes.pop(0)
        if lignes and re.match(r"(Version|Concept|\w.* version )", lignes[0]) and len(lignes[0]) < 400:
            infos = lignes.pop(0).strip()
    grand = grand.replace("MVOGMBI_Sync — ", "")
    produit = "MVOGMBI_Sync — Clover → Sage 50"
    infos = infos or f"Version {version_application()}"
    sections = [re.sub(r"^\d+(\.\d+)*\.?\s+", "", en_ligne(m.group(1)))
                for m in re.finditer(r"(?m)^## (.+)$", "\n".join(lignes))]
    html_ = f"""<section class="couverture">
  <img src="{LOGO.as_uri()}" alt="Logo">
  <div class="grand">{en_ligne(grand)}</div>
  <div class="sous">{e(produit)}</div>
  <div class="filet"><span style="width:90px;background:#1f7a3a"></span><span style="width:60px;background:#f2b705">
  </span><span style="width:24px;background:#c62828"></span></div>
  <div class="infos">{en_ligne(infos)}<br>Version de l'application : {e(version_application())}<br>
  Conçu et développé par {e(EDITEUR)} — Tous droits réservés.</div>
</section>"""
    if len(sections) >= 3:
        html_ += ("<section class='sommaire'><h2>Sommaire</h2><ol>"
                  + "".join(f"<li>{t}</li>" for t in sections) + "</ol></section>")
    return html_, "\n".join(lignes)


def creer(sortie: Path | None = None, source: Path = SOURCE, titre: str = "Architecture MVOGMBI_Sync") -> Path:
    """Markdown `source` (titres, listes, tableaux, diagrammes Mermaid) -> PDF `sortie` ; sert aussi aux autres
    documents (creer_documents.py)."""
    sortie = sortie or ICI / "Architecture_MVOGMBI_Sync.pdf"
    page_accueil, markdown = accueil(Path(source).read_text(encoding="utf-8"), titre)
    corps = page_accueil + convertir(markdown)
    page = f"""<!doctype html><html lang="fr"><head><meta charset="utf-8"><title>{e(titre)}</title>
<style>{STYLE}</style></head><body>{corps}
<script type="module">
import mermaid from "{MERMAID}";
mermaid.initialize({{ startOnLoad: false, theme: "base", flowchart: {{ htmlLabels: false, useMaxWidth: false, nodeSpacing: 28, rankSpacing: 32, padding: 6,
               diagramPadding: 4 }},
  gantt: {{ leftPadding: 175, fontSize: 12, sectionFontSize: 12, barHeight: 20, barGap: 5, topPadding: 45,
            useMaxWidth: false }},
  sequence: {{ useMaxWidth: false, wrap: true, width: 140, actorMargin: 30, messageMargin: 28, boxMargin: 6 }}, state: {{ useMaxWidth: false }}, mindmap: {{ useMaxWidth: false }},
  themeVariables: {{ primaryColor: "#e8f3ec", primaryBorderColor: "#1f7a3a", primaryTextColor: "#1d2b22",
                     lineColor: "#5b6b61", secondaryColor: "#fff8e1", tertiaryColor: "#f7faf8",
                     fontFamily: "Segoe UI, Arial, sans-serif", fontSize: "13px" }} }});
// Taille de chaque diagramme : le texte doit rester lisible. On essaie le sens d'origine et l'autre sens (LR <-> TB)
// d'un organigramme, sur une page en hauteur ou en largeur, et on garde la plus grande échelle (page en hauteur et
// sens d'origine préférés à écart faible).
const PLACE = {{ portrait: [712, 840], paysage: [985, 650] }};
function variantes(t) {{
  const m = t.match(/^(\\s*(?:flowchart|graph)\\s+)(LR|RL|TB|TD|BT)\\b/);
  if (!m) return [t];
  return [t, t.replace(m[0], m[1] + (/LR|RL/.test(m[2]) ? "TB" : "LR"))];
}}
let n = 0;
for (const pre of [...document.querySelectorAll("pre.mermaid")]) {{  // un à la fois : les mesures restent justes
  let choix = null;
  const essais = variantes(pre.textContent);
  for (let k = 0; k < essais.length; k++) {{
    const {{ svg }} = await mermaid.render("diagramme" + (++n), essais[k]);
    const vb = svg.match(/viewBox="\\s*([-\\d.e]+)[ ,]+([-\\d.e]+)[ ,]+([\\d.e]+)[ ,]+([\\d.e]+)/);
    const w = vb ? parseFloat(vb[3]) : 700, h = vb ? parseFloat(vb[4]) : 400;
    const echelles = {{}};
    for (const sens of ["portrait", "paysage"]) {{
      const [lw, lh] = PLACE[sens];
      echelles[sens] = Math.min(1.15, lw / w, lh / h);
    }}
    // page en largeur seulement si le diagramme serait trop petit sur une page en hauteur
    for (const sens of ["portrait", "paysage"]) {{
      const echelle = echelles[sens];
      const note = (sens === "paysage" ? (echelles.portrait < 0.75 ? echelle * 0.9 : 0) : echelle) * (k ? 0.9 : 1);
      if (!choix || note > choix.note) choix = {{ svg, w, h, sens, echelle, note }};
    }}
  }}
  const boite = pre.parentElement;
  pre.outerHTML = choix.svg;
  const el = boite.querySelector("svg");
  el.removeAttribute("style");
  boite.dataset.echelle = choix.echelle.toFixed(2) + " " + choix.sens + " " + choix.w.toFixed(0) + "x" + choix.h.toFixed(0);
  el.setAttribute("width", (choix.w * choix.echelle).toFixed(0));
  el.setAttribute("height", (choix.h * choix.echelle).toFixed(0));
  {{  // le diagramme reste avec son titre (et sa phrase d'introduction) ; page en largeur au besoin
    const section = document.createElement("section");
    section.className = choix.sens === "paysage" ? "tenir paysage" : "tenir";
    boite.before(section);
    const titres = [];
    let avant = section.previousElementSibling;
    if (avant && avant.tagName === "P" && avant.textContent.length < 160) {{ titres.unshift(avant); avant = avant.previousElementSibling; }}
    while (avant && /^H[2-4]$/.test(avant.tagName) && titres.length < 3) {{ titres.unshift(avant); avant = avant.previousElementSibling; }}
    titres.forEach(t => section.append(t));
    section.append(boite);
  }}
}}
document.querySelector("script[type=module]").remove();
</script></body></html>"""
    sortie_html = sortie.with_suffix(".html")
    sortie_html.write_text(page, encoding="utf-8")
    if not any(p.exists() for p in NAVIGATEURS):
        print("Microsoft Edge et Chrome introuvables : seul le HTML est produit.")
        return sortie_html
    # 1er passage : diagrammes dessinés puis figés dans la page (SVG)
    page_figee = page_dessinee(sortie_html.as_uri())
    if "<pre class=\"mermaid\"" in page_figee:
        raise RuntimeError("Diagrammes non dessinés (Mermaid inaccessible ?)")
    sortie_html.write_text("<!doctype html>" + page_figee, encoding="utf-8")
    # 2e passage : impression dans un fichier à côté, puis remplacement (le navigateur échoue sans rien dire si le
    # PDF est ouvert dans un lecteur)
    if not imprimer_pdf(sortie_html.as_uri(), sortie):
        raise RuntimeError("PDF non créé (Edge, Chrome).")
    return sortie


if __name__ == "__main__":
    print(creer(Path(sys.argv[1]) if len(sys.argv) > 1 else None))
