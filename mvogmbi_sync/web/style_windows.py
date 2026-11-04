"""Allure des fenêtres de l'application Windows pour toutes les pages web (demande du propriétaire du 2026-11-04 :
« les écrans sont différents… c'est toutes les fenêtres ») : zone de travail blanche encadrée avec le titre et
« ✖ Fermer » (bandeau de `Application.nouvel_outil`), police Segoe UI 13 px, champs et boutons compacts de
`design.Bouton` (vert du marché), cadres à titre comme `ttk.LabelFrame` (`fieldset.groupe`), onglets gris comme le
`ttk.Notebook` (Sun Valley), tableaux serrés aux en-têtes verts (`design.styler`), ligne d'état en bas.

Sur téléphone (moins de 820 px) les champs restent grands pour le doigt : seules les couleurs changent."""

STYLE_WINDOWS = """
.alerte-source { background: #fff4d6; border: 1px solid #f2b705; color: #6b4e00; padding: 6px 10px; border-radius: 4px;
  font-size: 13px; margin: 0 0 8px; }
td.vide { color: var(--gris); font-style: italic; text-align: center; background: var(--carte) !important; }
.entete-outil { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin: 0 0 10px; }
.entete-outil h1 { margin: 0; }
a.fermer { text-decoration: none; color: var(--texte); background: var(--carte); border: 1px solid var(--bord);
  border-radius: 4px; padding: 6px 14px; font-size: 13px; font-weight: 600; }
a.fermer:hover { border-color: var(--vert); }
fieldset.groupe { border: 1px solid #d5dcd7; border-radius: 4px; padding: 8px 12px 12px; margin: 0; min-width: 0;
  background: var(--carte); }
fieldset.groupe legend { padding: 0 4px; color: var(--vert); font-weight: 600; font-size: 13px; }
.colonnes { display: flex; gap: 10px; align-items: stretch; flex-wrap: wrap; }
.colonnes > * { flex: 1 1 320px; }
.ligne-etat { border-top: 1px solid var(--bord); color: var(--gris); font-size: 12.5px; padding: 6px 2px 0; margin-top: 10px; }
.grille-coupures { display: grid; grid-template-columns: auto 90px auto 90px; gap: 6px 10px; align-items: center; }
.grille-coupures label { margin: 0; text-align: right; color: var(--texte); font-size: 13px; }
.grille-tiers { display: grid; grid-template-columns: auto 1fr auto 1fr; gap: 6px 10px; align-items: center; }
.grille-tiers label { margin: 0; }
@media (max-width: 820px) { .grille-tiers { grid-template-columns: auto 1fr; } }
.ouvrir.inactif { opacity: .45; cursor: default; }
.deux-colonnes { display: flex; gap: 12px; flex-wrap: wrap; align-items: flex-start; }
.deux-colonnes > fieldset { flex: 1 1 320px; }
.grille-champs { display: grid; grid-template-columns: auto 1fr; gap: 6px 10px; align-items: center; margin-top: 12px; }
.grille-champs label { margin: 0; color: var(--texte); font-size: 13px; }
.texte-fixe { white-space: pre-line; font-size: 13px; line-height: 1.55; }
.resultat-rouge { color: var(--rouge); font-weight: 600; font-size: 14px; white-space: pre-line; margin: 12px 0 8px; }
.resultat-vert { color: var(--vert); font-weight: 600; font-size: 14px; white-space: pre-line; margin: 12px 0 8px; }
.resultat-jaune { color: #b07d00; font-weight: 600; font-size: 14px; white-space: pre-line; margin: 12px 0 8px; }
.fiche-infos { display: flex; gap: 40px; flex-wrap: wrap; margin-bottom: 8px; }
.colonne-fiche { display: grid; grid-template-columns: auto auto; gap: 2px 12px; align-content: start; }
.colonne-fiche .t { color: var(--gris); } .colonne-fiche .v { font-weight: 600; }
tr.application td { color: #1f4fa0; }
tr.total td { font-weight: 600; background: #e8f3ea !important; }
.cartes-bord { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 14px; }
.carte-bord { flex: 1 1 220px; display: flex; gap: 12px; align-items: center; background: var(--carte);
  border: 1px solid var(--bord); border-top: 4px solid var(--vert); padding: 10px 14px 12px; border-radius: 2px; }
.carte-bord.jaune { border-top-color: var(--jaune); } .carte-bord.rouge { border-top-color: var(--rouge); }
.carte-bord .ic { font-size: 26px; } .carte-bord .t { color: var(--gris); font-size: 12px; }
.carte-bord .v { font-size: 19px; font-weight: 600; }
pre.sortie { background: #f6f8f7; color: #24332a; border: 1px solid #dfe6e1; font-family: "Cascadia Mono", Consolas,
  monospace; font-size: 12px; padding: 8px 10px; max-height: 360px; overflow: auto; white-space: pre-wrap; margin-top: 14px; min-height: 64px; }
td.centre { text-align: center; }
pre.sortie .ok { color: #13772d; font-weight: normal; } pre.sortie .erreur { color: var(--rouge); }
pre.sortie .attention { color: #9a6a00; }
.poste-haut { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.poste-haut .horloge { font-size: 24px; font-weight: 600; }
.poste-message { font-size: 15px; font-weight: 600; }
.poste-grille { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
@media (max-width: 820px) { .poste-grille { grid-template-columns: 1fr 1fr; } }
a.poste-nom { display: flex; flex-direction: column; justify-content: center; align-items: center; min-height: 78px;
  background: var(--carte); border: 1px solid var(--bord); border-radius: 6px; color: var(--texte);
  text-decoration: none; font-size: 16px; font-weight: 600; text-align: center; padding: 8px; }
a.poste-nom:hover { background: #e3f1e7; } a.poste-nom span { font-size: 12px; color: var(--vert); font-weight: normal; }
.poste-centre { display: flex; flex-direction: column; align-items: center; gap: 6px; }
.poste-employe { font-size: 21px; font-weight: 600; }
.poste-nip { font-size: 34px; font-weight: 600; min-height: 46px; letter-spacing: 6px; }
.poste-pave { display: grid; grid-template-columns: repeat(3, 76px); gap: 10px; }
main button.poste-touche { font-size: 24px; height: 62px; background: var(--carte); color: var(--texte);
  border: 1px solid var(--bord); }
.poste-actions { display: flex; gap: 14px; flex-wrap: wrap; justify-content: center; }
main button.poste-action { font-size: 18px; padding: 14px 26px; }
.fenetre-choix { max-width: 380px; } .fenetre-choix h2 { margin-top: 0; }
label.choix-radio { display: flex; gap: 10px; align-items: center; font-size: 15px; color: var(--texte); padding: 6px 0; }
label.choix-radio input { width: 20px; height: 20px; accent-color: #13772d; }
.cartes-trois { display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; margin: 8px 0; }
.cartes-six { display: grid; grid-template-columns: repeat(6, 1fr); gap: 6px; margin: 6px 0; }
@media (max-width: 820px) { .cartes-six { grid-template-columns: 1fr 1fr; } }
.titre-admin { margin: 0 0 14px; } .titre-admin .t { font-size: 20px; font-weight: 600; color: #13772d; }
.titre-admin .souligne { display: flex; gap: 4px; margin-top: 4px; } .titre-admin .souligne span { height: 4px; }
.titre-admin .souligne .j { width: 46px; background: var(--jaune); } .titre-admin .souligne .r { width: 14px; background: var(--rouge); }
.titre-admin p { color: var(--gris); margin: 8px 0 0; }
.carte-admin { background: var(--carte); border: 1px solid var(--bord); border-left: 4px solid var(--vert);
  margin: 0 0 12px; padding: 12px 16px 14px; }
.carte-admin.jaune { border-left-color: var(--jaune); } .carte-admin.jaune .pastille { background: var(--jaune); }
.carte-admin .entete { font-size: 15px; font-weight: 600; display: flex; align-items: center; gap: 10px; }
.carte-admin .pastille { background: var(--vert); color: #fff; font-size: 12px; padding: 1px 8px; border-radius: 3px; }
.carte-admin .desc { color: var(--gris); font-size: 12.5px; margin: 4px 0 0; }
.carte-admin .champs { display: grid; grid-template-columns: max-content 1fr; gap: 6px 14px; align-items: start;
  margin-top: 8px; }
.carte-admin .champs > label { padding-top: 5px; color: var(--texte); }
.carte-admin .champs .aide { color: var(--gris); font-size: 12px; margin-top: 2px; max-width: 640px; }
.carte-admin .champs > .defile, .carte-admin .champs > h2 { grid-column: 1 / -1; }
label.case { display: flex; gap: 6px; align-items: center; color: var(--texte); }
@media (min-width: 821px) {
  main .barre-onglet > div, main .ligne > div:not(.large) { display: flex; align-items: center; gap: 6px; }
  main .barre-onglet > div > label, main .ligne > div > label { margin: 0; white-space: nowrap; }
  main { font-size: 13px; }
  main .zone-outil { background: var(--carte); border: 1px solid var(--bord); border-radius: 4px; padding: 12px 14px; }
  main h1.titre-page { font-size: 19px; }
  main h2 { font-size: 14px; margin: 14px 0 6px; }
  main label { font-size: 13px; color: var(--texte); margin-bottom: 2px; }
  main input, main select { padding: 4px 6px; border-radius: 3px; border-color: #c8cfca; font-size: 13px; }
  main textarea { font-size: 13px; }
  main button, main a.ouvrir { padding: 5px 12px; border-radius: 5px; font-size: 13px; font-weight: 600; }
  main button { background: #1a9b3c; }
  main button.second, main a.ouvrir { background: var(--carte); color: var(--vert); border: 1px solid #b9d8c2; }
  main button.danger { background: var(--rouge); color: #fff; }
  main button.accent { background: #f2b705; color: #222; }
  main .boutons button { min-width: 0; padding: 6px 14px; font-size: 13px; }
  main .ligne { gap: 8px 12px; margin-bottom: 8px; }
  main .carte { border-radius: 4px; padding: 10px 12px; }
  main .defile { border-radius: 2px; }
  main table { font-size: 13px; }
  main th { padding: 5px 8px; background: #1f7a3a; font-weight: 600; }
  main td { padding: 4px 8px; height: 30px; vertical-align: middle; }
  main tr:nth-child(even) td { background: #f4f8f5; }
  main .note { font-size: 12.5px; }
  main nav.onglets { background: #ececec; border: 1px solid #dadada; border-radius: 4px 4px 0 0; padding: 4px 4px 0;
    gap: 0; margin-bottom: 0; }
  main nav.onglets a.onglet { border-radius: 4px 4px 0 0; padding: 7px 18px; }
  main nav.onglets a.onglet.actif { background: var(--carte); border-color: #dadada; }
  main nav.onglets + * { margin-top: 0; }
  main .onglet-corps { border: 1px solid #dadada; border-top: 0; padding: 10px; background: var(--carte); }
}
"""
