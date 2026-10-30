// Présentation PowerPoint de MVOGMBI_Sync 1.0.0 (aucune donnée réelle : document publié).
//   node documentation/creer_presentation.js            (pptxgenjs requis : npm install pptxgenjs)
// Sortie : documentation/Presentation_MVOGMBI_Sync.pptx

const path = require("path");
const pptxgen = require("pptxgenjs");

const SORTIE = path.join(__dirname, "Presentation_MVOGMBI_Sync.pptx");
const P = { // couleurs du marché
  vert: "1F7A3A", vertFonce: "14532A", vertPale: "EAF4ED", vertClair: "97C9A8",
  jaune: "F2B705", rouge: "C62828", texte: "1D2B22", doux: "5B6B61", blanc: "FFFFFF", bord: "D5E3D9",
};
const W = 13.333, H = 7.5, M = 0.6;

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";
pres.author = "Concept Informatique inc.";
pres.company = "Concept Informatique inc.";
pres.title = "MVOGMBI_Sync 1.0";
pres.theme = { headFontFace: "Calibri", bodyFontFace: "Calibri" };

// ------------------------------------------------------------------ dispositions
pres.defineSlideMaster({
  title: "TITRE", background: { color: P.vertFonce },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: M, y: 2.2, w: W - 2 * M, h: 1.4, fontSize: 48, bold: true,
      color: P.blanc, valign: "bottom", align: "left", margin: 0 }, text: "" } },
    { placeholder: { options: { name: "body", type: "body", x: M, y: 3.75, w: W - 2 * M, h: 1.6, fontSize: 22,
      color: P.vertClair, valign: "top", margin: 0 }, text: "" } },
  ],
});
pres.defineSlideMaster({
  title: "CONTENU", background: { color: P.blanc },
  margin: [0.5, 0.6, 0.7, 0.6],
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: M, y: 0.35, w: W - 2 * M, h: 0.9, fontSize: 34, bold: true,
      color: P.vertFonce, valign: "middle", margin: 0 }, text: "" } },
    { text: { text: "MVOGMBI_Sync 1.0 — Marché MVOG-MBI Sherbrooke", options: { x: M, y: H - 0.5, w: 8, h: 0.3,
      fontSize: 10, color: P.doux, margin: 0 } } },
  ],
  slideNumber: { x: W - M - 0.6, y: H - 0.5, w: 0.6, h: 0.3, fontSize: 10, color: P.doux, align: "right" },
});

// ------------------------------------------------------------------ aides
function texte(slide, t, o) {
  slide.addText(t, Object.assign({ isTextBox: true, margin: 0, fontSize: 16, color: P.texte, valign: "top" }, o));
}
function carte(slide, x, y, w, h, nom, fond) {
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.12, objectName: nom,
    fill: { color: fond || P.vertPale }, line: { color: fond ? fond : P.bord, width: 1 } });
}
function pastille(slide, x, y, d, contenu, fond, encre) {
  slide.addShape(pres.shapes.OVAL, { x, y, w: d, h: d, fill: { color: fond }, line: { color: fond } });
  texte(slide, contenu, { x, y, w: d, h: d, align: "center", valign: "middle", fontSize: d * 22, bold: true, color: encre });
}
function contenu(section, titre, notes) {
  const s = pres.addSlide({ masterName: "CONTENU", sectionTitle: section });
  s.addText(titre, { placeholder: "title" });
  if (notes) s.addNotes(notes);
  return s;
}

// ------------------------------------------------------------------ 1. titre
pres.addSection({ title: "Introduction" });
let s = pres.addSlide({ masterName: "TITRE", sectionTitle: "Introduction" });
s.addText("MVOGMBI_Sync 1.0", { placeholder: "title" });
s.addText("Les ventes Clover dans Sage 50, chaque nuit, sans ressaisie\nMarché MVOG-MBI Sherbrooke · 30 octobre 2026",
  { placeholder: "body" });
pastille(s, W - M - 1.3, 0.6, 1.3, "✓", P.jaune, P.vertFonce);
s.addNotes("MVOGMBI_Sync relie la caisse Clover et la comptabilité Sage 50. Version 1.0 : tout ce qui suit est en service.");

// ------------------------------------------------------------------ 2. avant / après
s = contenu("Introduction", "Deux systèmes qui ne se parlaient pas",
  "Avant : tout se ressaisissait à la main. Après : l'application fait le lien chaque nuit et vérifie chaque écriture.");
carte(s, M, 1.5, 5.8, 4.4, "avant", "FBEAEA");
texte(s, "Avant", { x: M + 0.35, y: 1.75, w: 5, h: 0.5, fontSize: 24, bold: true, color: P.rouge });
texte(s, [
  { text: "Ventes recopiées de Clover vers Sage", options: { bullet: true, breakLine: true } },
  { text: "Dépôts bancaires appliqués à la main", options: { bullet: true, breakLine: true } },
  { text: "Factures fournisseurs saisies ligne par ligne", options: { bullet: true, breakLine: true } },
  { text: "Stocks Clover et Sage qui divergent", options: { bullet: true, breakLine: true } },
  { text: "Heures et paies sur papier", options: { bullet: true } },
], { x: M + 0.35, y: 2.4, w: 5.1, h: 3.8, paraSpaceAfter: 10 });
carte(s, W - M - 5.8, 1.5, 5.8, 4.4, "apres");
texte(s, "Avec MVOGMBI_Sync", { x: W - M - 5.45, y: 1.75, w: 5, h: 0.5, fontSize: 24, bold: true, color: P.vert });
texte(s, [
  { text: "Une facture de ventes par jour, importée la nuit", options: { bullet: true, breakLine: true } },
  { text: "Dépôts, Interac et espèces encaissés automatiquement", options: { bullet: true, breakLine: true } },
  { text: "PDF des fournisseurs lus, importés, stock mis à jour", options: { bullet: true, breakLine: true } },
  { text: "Articles, inventaire et transferts dans les deux systèmes", options: { bullet: true, breakLine: true } },
  { text: "Pointage par NIP, paie traitée dans Sage", options: { bullet: true } },
], { x: W - M - 5.45, y: 2.4, w: 5.1, h: 3.8, paraSpaceAfter: 10 });
s.addShape(pres.shapes.RIGHT_ARROW, { x: W / 2 - 0.35, y: 3.7, w: 0.7, h: 0.6, fill: { color: P.jaune }, line: { color: P.jaune } });

// ------------------------------------------------------------------ 3. chiffres clés
s = contenu("Introduction", "La version 1.0 en chiffres",
  "Sept jours de réalisation, 97 versions livrées avec leur installateur, 212 tests automatiques.");
const stats = [["97", "versions livrées\nen 7 jours"], ["212", "tests automatiques\nréussis"], ["8", "rubriques au menu"],
               ["< 1 s", "pour ouvrir une liste\nmême Sage fermé"]];
stats.forEach(([n, l], i) => {
  const x = M + i * 3.1;
  carte(s, x, 1.7, 2.85, 3.3, "stat" + i);
  texte(s, n, { x: x + 0.2, y: 2.0, w: 2.45, h: 1.4, fontSize: 60, bold: true, color: P.vert, align: "center", valign: "middle" });
  texte(s, l, { x: x + 0.2, y: 3.5, w: 2.45, h: 1.4, fontSize: 16, color: P.texte, align: "center" });
});
texte(s, "Aucune donnée réelle dans ce document.", { x: M, y: 5.8, w: 8, h: 0.4, fontSize: 12, italic: true, color: P.doux });

// ------------------------------------------------------------------ 4. fonctionnement
pres.addSection({ title: "Fonctionnement" });
s = contenu("Fonctionnement", "Comment ça marche",
  "Clover reste la caisse, Sage reste la comptabilité. L'application lit, contrôle, écrit, puis vérifie dans la base de Sage.");
const blocs = [["Clover", "ventes, articles,\nstocks, employés"], ["MVOGMBI_Sync", "contrôle, prépare,\nécrit, vérifie"],
               ["Sage 50", "factures, encaissements,\npaies, stocks"]];
blocs.forEach(([t, d], i) => {
  const x = M + 0.2 + i * 4.25, centre = i === 1;
  carte(s, x, 1.9, 3.5, 2.6, "bloc" + i, centre ? P.vert : undefined);
  texte(s, t, { x: x + 0.2, y: 2.15, w: 3.1, h: 0.7, fontSize: 26, bold: true, align: "center", color: centre ? P.blanc : P.vertFonce });
  texte(s, d, { x: x + 0.2, y: 2.95, w: 3.1, h: 1.3, fontSize: 16, align: "center", color: centre ? P.blanc : P.texte });
  if (i < 2) s.addShape(pres.shapes.RIGHT_ARROW, { x: x + 3.6, y: 2.95, w: 0.55, h: 0.5, fill: { color: P.jaune }, line: { color: P.jaune } });
});
texte(s, [
  { text: "Import des factures : ", options: { bold: true } }, { text: "Sage fermé, mono-utilisateur, jamais deux fois", options: { breakLine: true } },
  { text: "Saisies : ", options: { bold: true } }, { text: "multi-utilisateur, vous pouvez garder Sage ouvert", options: { breakLine: true } },
  { text: "Chaque écriture : ", options: { bold: true } }, { text: "relue dans la base de Sage avant d'être comptée comme faite" },
], { x: M + 0.2, y: 5.0, w: W - 2 * M - 0.4, h: 1.5, fontSize: 16, paraSpaceAfter: 6 });

// ------------------------------------------------------------------ 5. la nuit
s = contenu("Fonctionnement", "Chaque nuit, sans intervention",
  "Le traitement de nuit enchaîne ces étapes ; un jour bloqué est signalé, les autres continuent.");
const nuit = ["Lire les ventes de chaque jour sans facture", "Importer les factures dans Sage",
  "Encaisser les dépôts", "Payer les fournisseurs confirmés", "Lire les factures reçues par courriel",
  "Appliquer les promotions", "Sauvegarder les données", "Envoyer le résumé du matin"];
nuit.forEach((t, i) => {
  const col = i % 2, lig = Math.floor(i / 2), x = M + col * 6.1, y = 1.55 + lig * 1.25;
  pastille(s, x, y, 0.75, String(i + 1), col === 0 ? P.vert : P.jaune, col === 0 ? P.blanc : P.vertFonce);
  texte(s, t, { x: x + 0.95, y: y + 0.05, w: 5, h: 0.65, fontSize: 18, valign: "middle" });
});

// ------------------------------------------------------------------ 6. rubriques
s = contenu("Fonctionnement", "Huit rubriques, comme dans Sage",
  "Le menu reprend les rubriques de gestion de Sage, avec les fonctions propres au marché.");
const rub = [["Administration", "Clover, Sage, courriel, sauvegarde, utilisateurs"], ["Articles", "création, inventaire, transferts, pertes, promotions"],
  ["Vente", "factures des ventes, clients, commandes, relances"], ["Fournisseur", "factures PDF, bons de commande, retours"],
  ["Comptabilité", "encaissements, banque, caisse, taxes, budget"], ["Paie", "pointage, planning, chèques, bulletins, congés"],
  ["État", "statistiques, bénéfices, prévisions, 20/80"], ["Accueil", "mise en route, résumé, alertes"]];
rub.forEach(([t, d], i) => {
  const col = i % 4, lig = Math.floor(i / 4), x = M + col * 3.08, y = 1.55 + lig * 2.55;
  carte(s, x, y, 2.85, 2.3, "rub" + i);
  texte(s, t, { x: x + 0.25, y: y + 0.25, w: 2.4, h: 0.55, fontSize: 20, bold: true, color: P.vertFonce });
  texte(s, d, { x: x + 0.25, y: y + 0.9, w: 2.4, h: 1.25, fontSize: 14, color: P.texte });
});

// ------------------------------------------------------------------ 7. ventes
pres.addSection({ title: "Fonctions" });
s = contenu("Fonctions", "Des ventes à l'encaissement",
  "Règles fixées par le propriétaire : facture au net Clover, une facture pour la fin de semaine, encaissement daté du dépôt.");
const regles = [["1", "Une vente est datée de son premier paiement réussi"],
  ["2", "Une facture par jour du lundi au jeudi, une seule du vendredi au dimanche"],
  ["3", "Montant de ligne = ventes nettes Clover ; prix = net / quantité"],
  ["4", "Dépôt Clover appliqué sur la facture de son lot ; Interac et espèces répartis"],
  ["5", "Jamais deux fois la même facture ni le même encaissement"]];
regles.forEach(([n, t], i) => {
  const y = 1.55 + i * 0.95;
  pastille(s, M, y, 0.65, n, P.vert, P.blanc);
  texte(s, t, { x: M + 0.9, y: y + 0.05, w: 7.2, h: 0.6, fontSize: 18, valign: "middle" });
});
carte(s, 9.1, 1.55, W - M - 9.1, 4.5, "regle");
texte(s, "Jour bloqué ?", { x: 9.35, y: 1.8, w: 3.2, h: 0.5, fontSize: 20, bold: true, color: P.rouge });
texte(s, "Article non relié ou compte manquant : le jour est signalé dans le courriel du matin, corrigé en deux clics, puis refait. Les autres jours continuent.",
  { x: 9.35, y: 2.4, w: 3.2, h: 3.4, fontSize: 15 });

// ------------------------------------------------------------------ 8. fournisseurs
s = contenu("Fonctions", "Fournisseurs : de la commande au paiement",
  "Les PDF sont lus par l'OCR intégré à Windows, aucune intelligence artificielle ni service externe.");
const etapes = ["Bon de commande\nproposé", "Facture PDF\nlue et contrôlée", "Import dans Sage\nstock Clover à jour",
  "Virement Interac\nrapproché", "Paiement saisi\ndans Sage"];
etapes.forEach((t, i) => {
  const x = M + i * 2.48;
  carte(s, x, 2.0, 2.15, 1.9, "etape" + i, i === 2 ? P.vert : undefined);
  texte(s, t, { x: x + 0.12, y: 2.15, w: 1.9, h: 1.6, fontSize: 16, bold: true, align: "center", valign: "middle",
    color: i === 2 ? P.blanc : P.vertFonce });
  if (i < 4) s.addShape(pres.shapes.RIGHT_ARROW, { x: x + 2.17, y: 2.75, w: 0.3, h: 0.4, fill: { color: P.jaune }, line: { color: P.jaune } });
});
texte(s, [
  { text: "Qté Sage = Qté × Facteur ; Prix Sage = Montant / Qté Sage", options: { bullet: true, breakLine: true } },
  { text: "Doublons reconnus, même avec un préfixe sur le n° de facture", options: { bullet: true, breakLine: true } },
  { text: "Paiement partiel accepté, jamais plus que le solde dû", options: { bullet: true } },
], { x: M, y: 4.5, w: W - 2 * M, h: 1.8, fontSize: 17, paraSpaceAfter: 8 });

// ------------------------------------------------------------------ 9. paie
s = contenu("Fonctions", "La paie, du pointage au bulletin",
  "Les heures viennent de l'application, jamais saisies dans Sage ; Sage calcule les retenues.");
const paie = [["Pointer", "par NIP au magasin"], ["Approuver", "feuilles de temps, fériés, congés"],
  ["Traiter", "chèques de paie créés dans Sage"], ["Remettre", "bulletin à chaque employé, suivi des remises"]];
paie.forEach(([t, d], i) => {
  const x = M + i * 3.08;
  pastille(s, x + 0.95, 1.7, 0.95, String(i + 1), i % 2 ? P.jaune : P.vert, i % 2 ? P.vertFonce : P.blanc);
  texte(s, t, { x, y: 2.85, w: 2.85, h: 0.55, fontSize: 22, bold: true, align: "center", color: P.vertFonce });
  texte(s, d, { x, y: 3.45, w: 2.85, h: 1.0, fontSize: 15, align: "center" });
});
carte(s, M, 4.9, W - 2 * M, 1.4, "normes");
texte(s, "Normes du travail du Québec : 8 jours fériés, indemnité = 1/20 des 4 semaines précédentes, vacances 4 % / 6 %. Le NAS n'est jamais gardé par l'application.",
  { x: M + 0.3, y: 5.1, w: W - 2 * M - 0.6, h: 1.0, fontSize: 16, valign: "middle" });

// ------------------------------------------------------------------ 10. rapidité
s = contenu("Fonctions", "Des listes à moins d'une seconde",
  "Mesures du 30 octobre 2026 (temps techniques, aucune donnée de vente). Avant : chaque ouverture de liste avec Sage fermé attendait l'ouverture de la base.");
s.addChart(pres.charts.BAR, [{ name: "Secondes", labels: ["1re lecture, Sage fermé", "Liste des articles (préchargée)",
  "Livre d'inventaire (préchargé)", "Requête Sage courante"], values: [10.4, 0.09, 0.38, 0.05] }], {
  x: M, y: 1.45, w: 7.6, h: 4.9, barDir: "bar", showTitle: true, title: "Temps d'ouverture (secondes)", titleFontSize: 16,
  titleColor: P.vertFonce, titleFontFace: "+mn-lt", chartColors: [P.vert], showValue: true, dataLabelPosition: "outEnd",
  dataLabelColor: P.texte, dataLabelFontSize: 12, dataLabelFormatCode: "0.00", dataLabelFontFace: "+mn-lt", catAxisLabelColor: P.texte, catAxisLabelFontSize: 12,
  catAxisLabelFontFace: "+mn-lt", valAxisLabelColor: P.doux, valAxisLabelFontSize: 10, valAxisLabelFontFace: "+mn-lt",
  valGridLine: { color: P.bord, size: 0.5 }, catGridLine: { style: "none" }, showLegend: false,
});
carte(s, 8.6, 1.6, W - M - 8.6, 4.6, "rapide");
texte(s, [
  { text: "Préchargement au démarrage", options: { bold: true, breakLine: true } },
  { text: "Base gardée 10 minutes", options: { bold: true, breakLine: true } },
  { text: "Relâchée dès que vous lancez Sage", options: { bold: true, breakLine: true } },
  { text: "ou qu'un import en a besoin", options: { breakLine: true } },
], { x: 8.85, y: 1.9, w: 3.6, h: 4.0, fontSize: 17, color: P.vertFonce, paraSpaceAfter: 10 });

// ------------------------------------------------------------------ 11. droits
pres.addSection({ title: "Confiance" });
s = contenu("Confiance", "Chacun ne voit que ce qui lui est permis",
  "Les droits se règlent fonction par fonction : on peut donner « Liste des articles » sans le reste de la rubrique.");
const droits = [["Par fonction", "cocher « Liste des articles » seule, sans le reste de la rubrique"],
  ["Dans les fenêtres", "traiter la paie, restaurer une sauvegarde… refusables"],
  ["Supprimer, exporter", "deux droits à part, sur tous les boutons concernés"],
  ["Points de vente", "un profil limité à un ou plusieurs magasins"]];
droits.forEach(([t, d], i) => {
  const col = i % 2, lig = Math.floor(i / 2), x = M + col * 6.1, y = 1.6 + lig * 1.9;
  carte(s, x, y, 5.85, 1.65, "droit" + i);
  pastille(s, x + 0.3, y + 0.42, 0.8, "✓", P.vert, P.blanc);
  texte(s, t, { x: x + 1.35, y: y + 0.25, w: 4.3, h: 0.5, fontSize: 20, bold: true, color: P.vertFonce });
  texte(s, d, { x: x + 1.35, y: y + 0.8, w: 4.3, h: 0.7, fontSize: 15 });
});
texte(s, "Mots de passe jamais gardés en clair · secrets dans le coffre-fort de Windows · écran verrouillé après 5 minutes",
  { x: M, y: 5.6, w: W - 2 * M, h: 0.5, fontSize: 15, italic: true, color: P.doux });

// ------------------------------------------------------------------ 12. qualité
s = contenu("Confiance", "Testé avant chaque livraison",
  "212 tests automatiques, puis essais réels sur une copie du fichier d'entreprise et sur des articles Clover d'essai supprimés ensuite.");
const qual = [["212", "tests automatiques"], ["0", "écriture d'essai dans\nle vrai fichier Sage"], ["12", "scénarios d'écriture\nvalidés dans Sage"]];
qual.forEach(([n, l], i) => {
  const x = M + i * 4.1;
  texte(s, n, { x, y: 1.6, w: 3.8, h: 1.3, fontSize: 64, bold: true, color: i === 1 ? P.rouge : P.vert });
  texte(s, l, { x, y: 2.9, w: 3.8, h: 0.9, fontSize: 16 });
});
carte(s, M, 4.2, W - 2 * M, 2.0, "recette");
texte(s, [
  { text: "Import et doublon · encaissements · paiements · journal · documents de stock · transferts · inventaire", options: { breakLine: true } },
  { text: "Création d'articles, de services, de clients, de fournisseurs, d'employés · chèques de paie · profils et droits" },
], { x: M + 0.3, y: 4.45, w: W - 2 * M - 0.6, h: 1.5, fontSize: 16, paraSpaceAfter: 8 });

// ------------------------------------------------------------------ 13. suite
pres.addSection({ title: "Suite" });
s = pres.addSlide({ masterName: "TITRE", sectionTitle: "Suite" });
s.addText("Et maintenant", { placeholder: "title" });
s.addText("Deuxième point de vente réel · remises de retenues · promotions et bulletins en conditions réelles\nDocumentation complète : manuel, documentation fonctionnelle, architecture, workflows, processus, plan de test",
  { placeholder: "body" });
s.addNotes("Prochaines étapes : brancher un deuxième point de vente, suivre les premières remises, utiliser promotions et bulletins par courriel au quotidien.");

pres.writeFile({ fileName: SORTIE }).then(async (f) => {
  if (process.env.APPLY_THEME) { // thème nommé (outil de création de présentations), facultatif
    const { applyTheme } = require(process.env.APPLY_THEME);
    await applyTheme(f, { name: "Marché MVOG-MBI", headFontFace: "Calibri", bodyFontFace: "Calibri", colors: {
      dk1: P.texte, lt1: P.blanc, dk2: P.vertFonce, lt2: P.vertPale, accent1: P.vert, accent2: P.jaune, accent3: P.rouge,
      accent4: P.doux, accent5: P.vertClair, accent6: "2E7D9A", hlink: P.vert, folHlink: P.vertFonce } });
  }
  console.log(f);
});
