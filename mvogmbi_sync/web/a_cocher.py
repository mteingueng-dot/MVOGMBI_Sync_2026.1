"""Liste à cocher commune des pages web, comme fenetre_cocher.FenetreACocher de l'application Windows : explication,
« Afficher : » (Tous + chaque état), « Rechercher : », « ☑ Tout cocher », « ☐ Tout décocher », « 🔄 Actualiser »,
réglages propres à la page, tableau (case de chaque ligne ; lignes non permises grisées et sans case), compteur
« n ligne(s) cochée(s) sur m », bouton d'action, ligne d'état.

Chaque ligne a `permis`, `cochee_par_defaut` et `etat` (mêmes attributs que pour la fenêtre Windows). La case
porte le rang de la ligne dans la liste complète (`choix`)."""

from __future__ import annotations

from urllib.parse import urlencode

from .pages import csrf
from .serveur import echapper as e

TOUS = "Tous"


def page_a_cocher(ctx, adresse: str, explication: str, colonnes: list[str], lignes: list, valeurs, resume: str,
                  action: str, reglages: str = "", caches: dict | None = None, etat_initial: str | None = None,
                  bilan: str = "") -> str:
    """HTML de la liste ; `valeurs(ligne)` -> cellules (texte) ; `reglages` : champs ajoutés à la barre (dans le
    formulaire GET, comme les `ajouts` de Windows) ; `caches` : champs gardés d'un envoi à l'autre."""
    from .consultations import Section, tableau_section

    q = ctx.req.query
    caches = dict(caches or {})
    etats = sorted({l.etat for l in lignes})
    filtre = q.get("filtre") or (etat_initial if etat_initial in etats else TOUS)
    texte = (q.get("texte") or "").strip().casefold()
    cocher = q.get("cocher")  # « tout » / « aucun » : lignes affichées
    rangees, classes, visibles = [], [], 0
    for n, l in enumerate(lignes):
        if filtre != TOUS and l.etat != filtre:
            continue
        cellules = [str(x) for x in valeurs(l)]
        if texte and texte not in " ".join(cellules).casefold():
            continue
        visibles += 1
        coche = l.permis and (cocher == "tout" or (cocher != "aucun" and l.cochee_par_defaut))
        case = (f"<input type='checkbox' name='choix' value='{n}'{' checked' if coche else ''}>" if l.permis else "")
        rangees.append([case] + [e(x) for x in cellules])
        classes.append("termine" if not l.permis else "")
    base = {**caches, "filtre": filtre, "texte": q.get("texte", "")}
    options = "".join(f"<option{' selected' if x == filtre else ''}>{e(x)}</option>" for x in [TOUS] + etats)
    caches_html = "".join(f"<input type='hidden' name='{e(k)}' value='{e(v)}'>" for k, v in caches.items())
    barre = (f"<form method='get' class='barre-onglet'>{caches_html}<div><label>Afficher :</label><select name='filtre'>"
             f"{options}</select></div><div><label>Rechercher :</label><input name='texte' value='{e(q.get('texte', ''))}'"
             f" size='22'></div>{reglages}<button class='second sans-js'>Afficher</button>"
             f"<a class='ouvrir' href='{adresse}?{e(urlencode({**base, 'cocher': 'tout'}))}'>☑ Tout cocher</a>"
             f"<a class='ouvrir' href='{adresse}?{e(urlencode({**base, 'cocher': 'aucun'}))}'>☐ Tout décocher</a>"
             f"<a class='ouvrir' href='{adresse}?{e(urlencode({**base, 'actualiser': '1'}))}'>🔄 Actualiser</a></form>")
    coches = sum(1 for l in lignes if l.permis and l.cochee_par_defaut)
    return (f"<p class='note'>{e(explication)}</p>" + barre
            + f"<form method='post'>{csrf(ctx)}{caches_html}"
            + tableau_section(Section(f"{visibles} ligne(s) affichée(s)", [""] + colonnes, rangees, classes=classes,
                                      html=set(range(len(colonnes) + 1))), limite=5000)
            + f"<div class='barre-onglet'><strong>{coches} ligne(s) proposée(s) sur {len(lignes)}</strong><button "
              f"class='a-droite' name='action' value='lancer'>▶ {e(action)}</button></div></form>"
            + f"<div class='ligne-etat'>{e(resume)}" + (f"<br>✔ {e(bilan)}" if bilan else "") + "</div>")


def choisies(ctx, lignes: list) -> list:
    """Lignes cochées et permises du formulaire envoyé."""
    return [lignes[int(k)] for k in ctx.req.champs("choix") if k.isdigit() and int(k) < len(lignes)
            and lignes[int(k)].permis]
