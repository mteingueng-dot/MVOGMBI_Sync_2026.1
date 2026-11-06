"""Filtres communs des pages web. « Dépôt » (demande du propriétaire du 2026-11-05 : « les états de tous les dépôts à
la fois, filtrer sur un dépôt, option sélectionner tout ») : liste à cocher dans un <details> (aucun script, comme
design.ChoixMultiple de Windows) ; la case « Tous les dépôts » = tout sélectionner ; rien de coché = tous."""

from __future__ import annotations

from ..depots import TOUS, noms
from .serveur import echapper as e

STYLE = """
details.choix-multiple { position: relative; display: inline-block; }
details.choix-multiple > summary { list-style: none; cursor: pointer; border: 1px solid #b9c7be; border-radius: 5px;
  padding: 4px 10px; background: var(--carte); min-width: 150px; }
details.choix-multiple > summary::after { content: " ▾"; color: var(--gris); }
details.choix-multiple > div { position: absolute; z-index: 6; background: var(--carte); border: 1px solid var(--bord);
  padding: 6px 10px; box-shadow: 0 4px 12px rgba(0,0,0,.12); max-height: 260px; overflow-y: auto; min-width: 220px; }
details.choix-multiple label { display: flex; gap: 6px; align-items: center; white-space: nowrap; margin: 3px 0; }
details.choix-multiple label.tout { font-weight: 600; border-bottom: 1px solid var(--bord); padding-bottom: 4px; }
/* « Photographier une facture » : gros bouton pour le téléphone */
.photo-facture label.bouton-photo { display: block; text-align: center; background: #1a9b3c; color: #fff;
  border-radius: 10px; padding: 22px 12px; font-size: 20px; font-weight: 600; margin: 12px 0; cursor: pointer; }
.photo-facture label.bouton-photo input { display: block; margin: 10px auto 0; font-size: 14px; color: #fff; }
.photo-facture .barre-onglet button { font-size: 16px; padding: 10px 14px; }
/* Factures fournisseurs : la page tient dans la fenêtre sur PC, la liste défile seule (demande du propriétaire du
   2026-11-05 : « ne fais pas défiler la page ») */
@media (min-width: 821px) {
  .zone-liste-factures .defile { height: max(120px, calc(100vh - 900px)); min-height: 120px; max-height: none; }
  .zone-liste-factures ~ * .defile { height: 96px; min-height: 96px; max-height: none; }
}
"""


def depots_choisis(ctx, nom: str = "depot") -> list[str] | None:
    """Dépôts cochés ; None = tous (« Tous les dépôts » coché, ou rien de coché)."""
    valeurs = [v for v in ctx.req.valeurs(nom) if v.strip()]
    if not valeurs or TOUS in valeurs:
        return None
    return valeurs


def filtre_depots(ctx, nom: str = "depot", libelle: str = "Dépôt") -> str:
    """Champ « Dépôt » à placer dans un formulaire GET (il part avec « Afficher » / « Actualiser »)."""
    choisis = depots_choisis(ctx, nom)
    tous = choisis is None
    resume = "Tous les dépôts" if tous else (choisis[0] if len(choisis) == 1 else f"{len(choisis)} dépôts")
    cases = (f"<label class='tout'><input type='checkbox' name='{nom}' value='{e(TOUS)}'"
             f"{' checked' if tous else ''}> Tout sélectionner</label>"
             + "".join(f"<label><input type='checkbox' name='{nom}' value='{e(d)}'"
                       f"{' checked' if tous or d in choisis else ''}> {e(d)}</label>" for d in noms(ctx.config)))
    return (f"<div><label>{e(libelle)} :</label><details class='choix-multiple'><summary>{e(resume)}</summary>"
            f"<div>{cases}</div></details></div>")


def parametres_depots(ctx, nom: str = "depot") -> str:
    """Dépôts choisis à remettre dans un lien (« &depot=A&depot=B »)."""
    from urllib.parse import quote

    choisis = depots_choisis(ctx, nom)
    return "" if choisis is None else "".join(f"&amp;{nom}={quote(d)}" for d in choisis)
