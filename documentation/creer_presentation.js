// Présentation PowerPoint de MVOGMBI_Sync 1.0.0 du 9 novembre 2026 (aucune donnée de vente : document publié).
//   node documentation/creer_presentation.js            (pptxgenjs requis : npm install pptxgenjs)
// Sortie : documentation/Presentation_MVOGMBI_Sync.pptx

const path = require("path");
const pptxgen = require("pptxgenjs");

const SORTIE = path.join(__dirname, "Presentation_MVOGMBI_Sync.pptx");
const P = { // couleurs du marché
  vert: "1F7A3A", vertFonce: "14532A", vertPale: "EAF4ED", vertClair: "97C9A8",
  jaune: "F2B705", jaunePale: "FFF6D6", rouge: "C62828", rougePale: "FBEAEA",
  texte: "1D2B22", doux: "5B6B61", blanc: "FFFFFF", bord: "D5E3D9", bleu: "2E7D9A",
};
const W = 13.333, H = 7.5, M = 0.6;
const VERSION = "MVOGMBI_Sync 1.0";

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";
pres.author = "Concept Informatique inc.";
pres.company = "Concept Informatique inc.";
pres.title = VERSION;
pres.theme = { headFontFace: "Calibri", bodyFontFace: "Calibri" };

// ------------------------------------------------------------------ dispositions
pres.defineSlideMaster({
  title: "TITRE", background: { color: P.vertFonce },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: M, y: 2.0, w: W - 2 * M, h: 1.5, fontSize: 48, bold: true,
      color: P.blanc, valign: "bottom", align: "left", margin: 0 }, text: "" } },
    { placeholder: { options: { name: "body", type: "body", x: M, y: 3.7, w: W - 2 * M, h: 2.4, fontSize: 20,
      color: P.vertClair, valign: "top", margin: 0 }, text: "" } },
  ],
});
pres.defineSlideMaster({
  title: "SECTION", background: { color: P.vert },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: M, y: 2.6, w: W - 2 * M, h: 1.2, fontSize: 44, bold: true,
      color: P.blanc, valign: "bottom", margin: 0 }, text: "" } },
    { placeholder: { options: { name: "body", type: "body", x: M, y: 3.95, w: W - 2 * M, h: 1.2, fontSize: 20,
      color: P.vertPale, valign: "top", margin: 0 }, text: "" } },
  ],
});
pres.defineSlideMaster({
  title: "CONTENU", background: { color: P.blanc },
  margin: [0.5, 0.6, 0.7, 0.6],
  objects: [
    { rect: { x: 0, y: 0, w: W, h: 0.08, fill: { color: P.vert } } },
    { placeholder: { options: { name: "title", type: "title", x: M, y: 0.3, w: W - 2 * M, h: 0.9, fontSize: 32, bold: true,
      color: P.vertFonce, valign: "middle", margin: 0 }, text: "" } },
    { text: { text: VERSION + " — Clover et Sage 50 reliés", options: { x: M, y: H - 0.5, w: 8, h: 0.3,
      fontSize: 10, color: P.doux, margin: 0 } } },
  ],
  slideNumber: { x: W - M - 0.6, y: H - 0.5, w: 0.6, h: 0.3, fontSize: 10, color: P.doux, align: "right" },
});

// ------------------------------------------------------------------ aides
function texte(slide, t, o) {
  slide.addText(t, Object.assign({ isTextBox: true, margin: 0, fontSize: 16, color: P.texte, valign: "top" }, o));
}
function carte(slide, x, y, w, h, nom, fond, bord) {
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.1, objectName: nom,
    fill: { color: fond || P.vertPale }, line: { color: bord || fond || P.bord, width: 1 } });
}
function pastille(slide, x, y, d, contenu, fond, encre) {
  slide.addShape(pres.shapes.OVAL, { x, y, w: d, h: d, fill: { color: fond }, line: { color: fond } });
  texte(slide, contenu, { x, y, w: d, h: d, align: "center", valign: "middle", fontSize: Math.round(d * 22), bold: true, color: encre });
}
function fleche(slide, x, y, w, h) {
  slide.addShape(pres.shapes.RIGHT_ARROW, { x, y, w, h, fill: { color: P.jaune }, line: { color: P.jaune } });
}
function puces(lignes, gras) {
  return lignes.map((l, i) => {
    const fin = i < lignes.length - 1 ? { breakLine: true } : {};
    if (Array.isArray(l)) return [{ text: l[0], options: { bold: true, bullet: true } }, { text: l[1], options: fin }];
    return [{ text: l, options: Object.assign({ bullet: true }, fin, gras ? { bold: true } : {}) }];
  }).flat();
}
function contenu(section, titre, notes) {
  const s = pres.addSlide({ masterName: "CONTENU", sectionTitle: section });
  s.addText(titre, { placeholder: "title" });
  if (notes) s.addNotes(notes);
  return s;
}
function intercalaire(section, titre, sous, notes) {
  pres.addSection({ title: section });
  const s = pres.addSlide({ masterName: "SECTION", sectionTitle: section });
  s.addText(titre, { placeholder: "title" });
  s.addText(sous, { placeholder: "body" });
  if (notes) s.addNotes(notes);
  return s;
}
// grille de cartes titre + texte
function grille(s, elements, colonnes, y0, hauteur, opts) {
  opts = opts || {};
  const largeur = (W - 2 * M - (colonnes - 1) * 0.25) / colonnes;
  elements.forEach(([t, d], i) => {
    const col = i % colonnes, lig = Math.floor(i / colonnes);
    const x = M + col * (largeur + 0.25), y = y0 + lig * (hauteur + 0.22);
    carte(s, x, y, largeur, hauteur, "c" + i, opts.fond);
    texte(s, t, { x: x + 0.18, y: y + 0.15, w: largeur - 0.36, h: 0.45, fontSize: opts.titre || 17, bold: true, color: P.vertFonce });
    texte(s, d, { x: x + 0.18, y: y + 0.62, w: largeur - 0.36, h: hauteur - 0.75, fontSize: opts.corps || 13 });
  });
}

// ================================================================== 1. titre
pres.addSection({ title: "Introduction" });
let s = pres.addSlide({ masterName: "TITRE", sectionTitle: "Introduction" });
s.addText(VERSION, { placeholder: "title" });
s.addText("Les ventes Clover dans Sage 50, chaque nuit, sans ressaisie — et les décisions de la semaine chaque matin\n" +
  "Marché MVOG-MBI Sherbrooke · 9 novembre 2026", { placeholder: "body" });
pastille(s, W - M - 1.3, 0.6, 1.3, "✓", P.jaune, P.vertFonce);
s.addNotes("MVOGMBI_Sync relie la caisse Clover et la comptabilité Sage 50, et ajoute l'aide à la décision. " +
  "Version 1.0.0 du 9 novembre 2026 : numérotation remise à zéro, tout ce qui suit est en service.");

// ================================================================== 2. sommaire
s = contenu("Introduction", "Au programme",
  "Le déroulé de la présentation : le besoin, le fonctionnement, les fonctions par domaine, le Reporting, la confiance et la suite.");
const somm = [["1", "Le besoin", "deux systèmes qui ne se parlaient pas"], ["2", "Fonctionnement", "serveur, nuit, rubriques"],
  ["3", "Fonctions", "ventes, banque, fournisseurs, stocks, comptabilité, paie"], ["4", "Reporting", "18 états, 44 analyses, décisions"],
  ["5", "Confiance", "web, droits, sécurité, qualité, rapidité"], ["6", "Suite", "documentation et prochaines étapes"]];
somm.forEach(([n, t, d], i) => {
  const col = i % 2, lig = Math.floor(i / 2), x = M + col * 6.1, y = 1.55 + lig * 1.65;
  pastille(s, x, y, 0.9, n, col === 0 ? P.vert : P.jaune, col === 0 ? P.blanc : P.vertFonce);
  texte(s, t, { x: x + 1.15, y: y + 0.02, w: 4.8, h: 0.5, fontSize: 22, bold: true, color: P.vertFonce });
  texte(s, d, { x: x + 1.15, y: y + 0.52, w: 4.8, h: 0.5, fontSize: 15, color: P.doux });
});

// ================================================================== 3. avant / après
s = contenu("Introduction", "Deux systèmes qui ne se parlaient pas",
  "Avant : tout se ressaisissait à la main, et la marge réelle était inconnue. Après : l'application fait le lien chaque nuit, " +
  "vérifie chaque écriture dans Sage et propose chaque matin les décisions de la semaine.");
carte(s, M, 1.45, 5.8, 4.85, "avant", P.rougePale);
texte(s, "Avant", { x: M + 0.35, y: 1.65, w: 5, h: 0.5, fontSize: 24, bold: true, color: P.rouge });
texte(s, puces(["Ventes recopiées de Clover vers Sage", "Dépôts bancaires appliqués à la main",
  "Factures fournisseurs saisies ligne par ligne", "Stocks Clover et Sage qui divergent", "Heures et paies sur papier",
  "Rapports Clover sans les coûts : marge inconnue"]), { x: M + 0.35, y: 2.3, w: 5.1, h: 3.9, fontSize: 17, paraSpaceAfter: 9 });
carte(s, W - M - 5.8, 1.45, 5.8, 4.85, "apres");
texte(s, "Avec MVOGMBI_Sync", { x: W - M - 5.45, y: 1.65, w: 5, h: 0.5, fontSize: 24, bold: true, color: P.vert });
texte(s, puces(["Une facture de ventes par jour, importée la nuit", "Dépôts, Interac et espèces encaissés automatiquement",
  "PDF et photos des fournisseurs lus, importés, stock à jour", "Articles, inventaire et transferts dans les deux systèmes",
  "Pointage par NIP, paie traitée dans Sage", "Vraie marge et décisions priorisées chaque matin"]),
{ x: W - M - 5.45, y: 2.3, w: 5.1, h: 3.9, fontSize: 17, paraSpaceAfter: 9 });
fleche(s, W / 2 - 0.35, 3.6, 0.7, 0.6);

// ================================================================== 4. chiffres clés
s = contenu("Introduction", "MVOGMBI_Sync en chiffres",
  "Dix-sept jours de réalisation, plus de 200 versions livrées chacune avec son installateur, 369 tests automatiques, " +
  "44 analyses décisionnelles. Numérotation remise à 1.0.0 le 9 novembre 2026.");
const stats = [["200+", "versions livrées\nen 17 jours"], ["369", "tests automatiques\nréussis"], ["76", "fonctions au menu,\nWindows et web"],
  ["44", "analyses\ndécisionnelles"]];
stats.forEach(([n, l], i) => {
  const x = M + i * 3.1;
  carte(s, x, 1.55, 2.85, 3.2, "stat" + i, i === 3 ? P.vert : undefined);
  texte(s, n, { x: x + 0.2, y: 1.8, w: 2.45, h: 1.4, fontSize: 58, bold: true, color: i === 3 ? P.blanc : P.vert, align: "center", valign: "middle" });
  texte(s, l, { x: x + 0.2, y: 3.3, w: 2.45, h: 1.2, fontSize: 16, color: i === 3 ? P.blanc : P.texte, align: "center" });
});
const stats2 = [["221", "factures de vente importées\nen une nuit (rattrapage)"], ["229", "dépôts encaissés\nen 2 heures"],
  ["< 0,3 s", "par page web"], ["0", "essai dans le vrai fichier\navant validation"]];
stats2.forEach(([n, l], i) => {
  const x = M + i * 3.1;
  texte(s, n, { x, y: 5.0, w: 1.3, h: 0.9, fontSize: 26, bold: true, color: P.vertFonce, valign: "middle" });
  texte(s, l, { x: x + 1.3, y: 5.0, w: 1.65, h: 0.9, fontSize: 11.5, color: P.doux, valign: "middle" });
});

// ================================================================== FONCTIONNEMENT
intercalaire("Fonctionnement", "Fonctionnement", "Clover reste la caisse, Sage reste la comptabilité : l'application lit, contrôle, écrit, vérifie.");

s = contenu("Fonctionnement", "Comment ça marche",
  "Clover reste la caisse, Sage reste la comptabilité. L'application lit, contrôle, écrit, puis vérifie dans la base de Sage.");
const blocs = [["Clover", "ventes, articles,\nstocks, employés"], ["MVOGMBI_Sync", "contrôle, prépare,\nécrit, vérifie"],
  ["Sage 50", "factures, encaissements,\nachats, paies, stocks"]];
blocs.forEach(([t, d], i) => {
  const x = M + 0.2 + i * 4.25, centre = i === 1;
  carte(s, x, 1.6, 3.5, 2.3, "bloc" + i, centre ? P.vert : undefined);
  texte(s, t, { x: x + 0.2, y: 1.8, w: 3.1, h: 0.7, fontSize: 26, bold: true, align: "center", color: centre ? P.blanc : P.vertFonce });
  texte(s, d, { x: x + 0.2, y: 2.55, w: 3.1, h: 1.2, fontSize: 16, align: "center", color: centre ? P.blanc : P.texte });
  if (i < 2) fleche(s, x + 3.6, 2.5, 0.55, 0.5);
});
grille(s, [["Imports (la nuit)", "Sage fermé, mono-utilisateur, par l'outil d'import ou l'assistant de Sage (entreprise partagée) ; jamais deux fois"],
  ["Saisies (le jour)", "multi-utilisateur, dans les fenêtres de Sage : encaissements, paiements, journal, stocks ; vous gardez Sage ouvert"],
  ["Chaque écriture", "relue dans la base de Sage avant d'être comptée comme faite ; un échec est signalé, jamais caché"]],
3, 4.25, 1.85, { corps: 14 });

s = contenu("Fonctionnement", "Où tourne l'application",
  "Tout est sur le serveur du magasin, à côté de Sage 50 : application Windows, serveur web, traitement de nuit et données. " +
  "Les postes et téléphones passent par un réseau privé (Tailscale) en HTTPS.");
grille(s, [["Serveur du magasin", "Sage 50, MVOGMBI_Sync, données, traitement de nuit ; l'application garde Sage ouvert pour les saisies de la journée"],
  ["Application Windows", "la fenêtre complète, sur le serveur ou en Bureau à distance ; ouvre Sage avec elle et le referme en sortant"],
  ["Application web", "identique à Windows : mêmes menus, tableaux, graphiques et droits ; HTTPS sans port, adresse du magasin"],
  ["Client des postes", "un programme qui ouvre l'application web en un clic, ou le Bureau à distance ; adresse du serveur réglable"],
  ["Téléphones", "pointage limité au Wi-Fi du magasin, pause automatique hors du Wi-Fi ; factures photographiées"],
  ["Données", "ventes gardées jour par jour, coûts de Sage relus, sauvegarde vérifiée chaque nuit (14 jours, 8 semaines, 12 mois)"]],
3, 1.5, 2.15, { corps: 14 });

s = contenu("Fonctionnement", "Chaque nuit, sans intervention",
  "Le traitement de nuit enchaîne ces étapes ; un jour bloqué est signalé, les autres continuent. Chaque étape est notée dans le registre des traitements.");
const nuit = ["Lire les ventes de chaque jour sans facture", "Importer les factures dans Sage (lots de 25)",
  "Encaisser les dépôts des ventes importées", "Payer les fournisseurs confirmés", "Lire et importer les factures reçues par courriel",
  "Passer les états RIA dans Sage", "Appliquer les promotions, sauvegarder", "Envoyer le résumé et les décisions du matin"];
nuit.forEach((t, i) => {
  const col = i % 2, lig = Math.floor(i / 2), x = M + col * 6.1, y = 1.5 + lig * 1.22;
  pastille(s, x, y, 0.75, String(i + 1), col === 0 ? P.vert : P.jaune, col === 0 ? P.blanc : P.vertFonce);
  texte(s, t, { x: x + 0.95, y: y + 0.05, w: 5, h: 0.65, fontSize: 18, valign: "middle" });
});
texte(s, "Verrou : un seul traitement à la fois · journal de la nuit · courriel même en cas d'erreur",
  { x: M, y: 6.45, w: W - 2 * M, h: 0.35, fontSize: 13, italic: true, color: P.doux });

s = contenu("Fonctionnement", "Dix rubriques, comme dans Sage",
  "Le menu reprend les rubriques de gestion de Sage, avec les fonctions propres au marché. Chaque fonction se donne séparément à un profil.");
grille(s, [["Accueil", "mise en route en 10 étapes, bienvenue"], ["Administration", "Clover, Sage, courriel, automatisation, utilisateurs, sauvegarde, audit"],
  ["Articles", "liste, création, correspondance, prix et marges, promotions, étiquettes"], ["Stock", "documents, transferts, pertes, inventaires, livre d'inventaire"],
  ["Vente", "ventes Clover → factures Sage, clients, devis à facture, relances"], ["Fournisseur", "factures PDF et photos, bons de commande, retours"],
  ["Comptabilité", "encaissements, paiements, rapprochement, caisse, taxes, budget"], ["RIA", "opérations, états de compte, comptes RIA"],
  ["Paie", "pointage, planning, feuilles de temps, chèques, T4 / RL-1"], ["État", "Reporting, suivi des ventes, opérations journalières, historique"]],
5, 1.5, 2.35, { titre: 16, corps: 12.5 });

// ================================================================== FONCTIONS
intercalaire("Fonctions", "Les fonctions", "Ventes, banque, fournisseurs, stocks, comptabilité, RIA et paie.");

s = contenu("Fonctions", "Des ventes à la facture Sage",
  "Règles fixées par le propriétaire : facture au net Clover, une facture pour la fin de semaine, jamais deux fois.");
const regles = [["1", "Une vente est datée de son premier paiement réussi"],
  ["2", "Une facture par jour du lundi au jeudi, une seule du vendredi au dimanche"],
  ["3", "Montant de ligne = ventes nettes Clover ; prix = net / quantité"],
  ["4", "Taxes TPS et TVQ selon les lignes taxées dans Clover"],
  ["5", "Une facture par point de vente et par jour (plusieurs magasins)"],
  ["6", "Jamais deux fois la même facture : présence vérifiée dans Sage"]];
regles.forEach(([n, t], i) => {
  const y = 1.45 + i * 0.82;
  pastille(s, M, y, 0.6, n, P.vert, P.blanc);
  texte(s, t, { x: M + 0.85, y: y + 0.03, w: 7.3, h: 0.55, fontSize: 17, valign: "middle" });
});
carte(s, 9.1, 1.45, W - M - 9.1, 4.85, "regle", P.jaunePale, P.jaune);
texte(s, "Jour bloqué ?", { x: 9.35, y: 1.65, w: 3.2, h: 0.5, fontSize: 20, bold: true, color: P.rouge });
texte(s, puces(["Article non relié ou compte manquant", "Signalé dans le courriel du matin", "Corrigé en deux clics (correspondance, comptes)",
  "Refait la nuit suivante", "Les autres jours continuent"]), { x: 9.35, y: 2.25, w: 3.25, h: 3.9, fontSize: 15, paraSpaceAfter: 8 });

s = contenu("Fonctions", "Encaissements et banque",
  "Le dépôt Clover de chaque jour est appliqué sur la facture de son lot ; les virements Interac et dépôts d'espèces sont répartis ; " +
  "les relevés Desjardins et Banque Nationale sont rapprochés de Sage.");
grille(s, [["Dépôts Clover", "lot de cartes du soir = dépôt du lendemain ; vendredi-dimanche déposés le lundi ; appliqué sur la facture du lot"],
  ["Interac et espèces", "virements et dépôts au guichet des relevés répartis sur les factures, la plus ancienne d'abord"],
  ["« Déjà au compte de dépôt ? »", "un lot déjà inscrit autrement dans Sage n'est jamais encaissé deux fois : à vérifier"],
  ["Un échec ne bloque rien", "chaque dépôt dans son propre essai ; montant relu dans la cellule avant validation"],
  ["Rapprochement", "relevés PDF Desjardins et BNC lus, chaque solde revérifié ; écart expliqué ligne par ligne"],
  ["Plusieurs comptes", "un compte Sage par banque ; encaissements et paiements manuels notés au rapprochement"]],
3, 1.5, 2.2, { corps: 13.5 });

s = contenu("Fonctions", "Fournisseurs : de la commande au paiement",
  "Les PDF et photos sont lus par l'OCR intégré à Windows, aucune intelligence artificielle ni service externe.");
const etapes = ["Bon de commande\nproposé", "Facture PDF ou\nphoto lue", "Lignes reliées\nà vos articles", "Import dans Sage\nstock Clover à jour",
  "Virement Interac\nrapproché, payé"];
etapes.forEach((t, i) => {
  const x = M + i * 2.48;
  carte(s, x, 1.5, 2.15, 1.55, "etape" + i, i === 3 ? P.vert : undefined);
  texte(s, t, { x: x + 0.1, y: 1.6, w: 1.95, h: 1.35, fontSize: 15, bold: true, align: "center", valign: "middle",
    color: i === 3 ? P.blanc : P.vertFonce });
  if (i < 4) fleche(s, x + 2.17, 2.1, 0.3, 0.4);
});
texte(s, puces([["Propositions à l'ouverture : ", "même vendu à la caisse ou au poids, avec le facteur ; « Confirmer toutes les propositions »"],
  ["Taxes de chaque ligne : ", "« F P », « TX », « GQ » lus après le montant"],
  ["Règle du propriétaire : ", "Qté Sage = Qté × Facteur ; Prix Sage = Montant / Qté Sage"],
  ["Stock Clover : ", "case réglée facture par facture ; facture importée archivée avec son PDF"],
  ["Contrôles : ", "doublons reconnus (même avec un préfixe), facture déjà dans Sage archivée sans 2e import"],
  ["Paiements : ", "un virement peut payer plusieurs factures ; jamais plus que le solde"]]),
{ x: M, y: 3.35, w: W - 2 * M, h: 3.1, fontSize: 15.5, paraSpaceAfter: 7 });

s = contenu("Fonctions", "Articles et stocks dans les deux systèmes",
  "Chaque article Clover est relié à un article Sage ; les mouvements de stock passent dans Sage et dans Clover.");
grille(s, [["Correspondance", "Clover ↔ Sage par code, nom et ressemblance ; deux formats différents = deux articles"],
  ["Créer un article", "dans Clover et Sage en une fois, comptes de sa catégorie, prix = achat + marge"],
  ["Inventaire", "compté une fois, saisi dans Clover et Sage ; rapport d'écarts au coût moyen ; inventaire tournant"],
  ["Transferts et dépôts", "entre magasins et dépôts, Sage puis Clover ; bon de transfert imprimé"],
  ["Pertes et démarque", "périmé, abîmé, vol, don… sortie de stock dans les deux systèmes, rapport par motif"],
  ["Prix", "prix et marges, promotions planifiées, prix de vente Sage alignés sur Clover, étiquettes"]],
3, 1.5, 2.2, { corps: 13.5 });

s = contenu("Fonctions", "Comptabilité et RIA",
  "Les fonctions de comptabilité lisent Sage et préparent les écritures ; l'agence RIA est suivie de bout en bout.");
grille(s, [["Contrôle de la caisse", "espèces attendues selon Clover, comptage du soir, écarts, dépôts d'espèces"],
  ["Dépenses", "petite caisse, carte, employé à rembourser ; taxes calculées ; reçu gardé ; écriture au journal"],
  ["Taxes et clôture", "TPS / TVQ contrôlées avec Clover, âge des comptes, trésorerie 4 semaines, clôture du mois"],
  ["Plan comptable et budget", "comptes ajoutés ou modifiés dans Sage ; budget mensuel et écarts"],
  ["Retenues", "à remettre par organisme, échéances, alertes de retard"],
  ["RIA", "états de compte lus, envois, versements et commissions passés dans Sage, surplus d'espèces"]],
3, 1.5, 2.2, { corps: 13.5 });

s = contenu("Fonctions", "La paie, du pointage au bulletin",
  "Les heures viennent de l'application, jamais saisies dans Sage ; Sage calcule les retenues.");
const paie = [["Pointer", "par NIP, poste du magasin\nou téléphone sur le Wi-Fi"], ["Approuver", "feuilles de temps,\nfériés et congés"],
  ["Traiter", "chèques de paie\ncréés dans Sage"], ["Remettre", "bulletin à chaque employé,\nT4 / RL-1 officiels"]];
paie.forEach(([t, d], i) => {
  const x = M + i * 3.08;
  pastille(s, x + 0.95, 1.5, 0.95, String(i + 1), i % 2 ? P.jaune : P.vert, i % 2 ? P.vertFonce : P.blanc);
  texte(s, t, { x, y: 2.6, w: 2.85, h: 0.55, fontSize: 22, bold: true, align: "center", color: P.vertFonce });
  texte(s, d, { x, y: 3.15, w: 2.85, h: 0.9, fontSize: 15, align: "center" });
  if (i < 3) fleche(s, x + 2.65, 1.75, 0.4, 0.45);
});
carte(s, M, 4.45, W - 2 * M, 1.95, "normes");
texte(s, puces(["Planning mensuel par dépôt, publié aux employés ; « Mon horaire » et « Mes heures et mes paies »",
  "Normes du travail du Québec : 8 jours fériés, indemnité = 1/20 des 4 semaines précédentes, vacances 4 % / 6 %",
  "Le NAS n'est jamais gardé par l'application ; chaque bulletin part à un seul destinataire"]),
{ x: M + 0.3, y: 4.65, w: W - 2 * M - 0.6, h: 1.6, fontSize: 15, paraSpaceAfter: 6 });

// ================================================================== REPORTING
intercalaire("Reporting", "Reporting et aide à la décision", "18 états enrichis, 44 analyses, 7 rapports de gestion — et les décisions de la semaine.",
  "Le Reporting croise les ventes Clover avec les coûts de Sage : la vraie marge, et des décisions écrites en mots simples.");

s = contenu("Reporting", "Le Reporting en un coup d'œil",
  "Ancien onglet « Statistiques Clover ». Tout se calcule sur les ventes déjà lues, sans relire Clover, et se compare à la période d'avant.");
const rep = [["18", "états enrichis\ncomme dans Clover"], ["44", "analyses\ndécisionnelles"], ["7", "rapports\nde gestion"], ["3", "sous-pages : Résumé,\nGraphiques, Détail"]];
rep.forEach(([n, l], i) => {
  const x = M + i * 3.1;
  texte(s, n, { x, y: 1.45, w: 2.85, h: 1.1, fontSize: 60, bold: true, color: i === 1 ? P.jaune : P.vert, align: "center" });
  texte(s, l, { x, y: 2.6, w: 2.85, h: 0.8, fontSize: 15, align: "center" });
});
grille(s, [["Période comme Clover", "aujourd'hui, semaine, 30 jours, mois, année… comparée à la même durée d'avant"],
  ["Filtres globaux", "point de vente, article, client, employé, catégorie, mode de paiement"],
  ["Vraie marge", "ventes Clover × coût moyen de Sage ; coûts aberrants écartés"],
  ["Facture Clover", "un clic sur un n° de commande ouvre la vraie facture"]],
4, 3.75, 2.45, { corps: 13.5, titre: 16 });

s = contenu("Reporting", "Synthèse et décisions",
  "La synthèse rassemble les décisions de toutes les analyses, de la plus urgente à la moins urgente, avec les articles, clients ou " +
  "commandes concernés. Exemples de libellés tels qu'ils apparaissent (sans chiffres réels).");
const dec = [["1", P.rouge, "Remettre en stock d'abord les articles d'appel qui manquent", "Ruptures probables · Articles d'appel"],
  ["1", P.rouge, "Protéger la marge brute", "Pourquoi le bénéfice change"],
  ["2", P.jaune, "Revoir les prix des grands formats plus chers au kg que les petits", "Prix selon le format"],
  ["2", P.jaune, "Prévoir plus de stock pour les articles qui montent", "Articles qui montent"],
  ["2", P.jaune, "Renforcer l'équipe aux heures de pointe", "Achalandage et personnel"],
  ["3", P.bleu, "Proposer à la caisse le complément habituel", "Ventes complémentaires manquées"]];
dec.forEach(([n, c, t, ou], i) => {
  const y = 1.45 + i * 0.8;
  pastille(s, M, y + 0.05, 0.55, n, c, P.blanc);
  texte(s, t, { x: M + 0.8, y, w: 7.2, h: 0.4, fontSize: 16.5, bold: true, color: P.texte });
  texte(s, "Où regarder : " + ou, { x: M + 0.8, y: y + 0.38, w: 7.2, h: 0.35, fontSize: 12.5, color: P.doux });
});
carte(s, 9.0, 1.45, W - M - 9.0, 4.85, "matin", P.vertPale);
texte(s, "Courriel du matin", { x: 9.25, y: 1.65, w: 3.4, h: 0.5, fontSize: 20, bold: true, color: P.vertFonce });
texte(s, puces(["Ventes d'hier contre la semaine passée", "Marge au coût moyen", "Solde du compte de dépôt", "Factures à payer, ruptures, péremption",
  "Décisions des 28 derniers jours, colorées par priorité, avec 5 éléments concernés"]),
{ x: 9.25, y: 2.25, w: 3.35, h: 3.9, fontSize: 14, paraSpaceAfter: 7 });

s = contenu("Reporting", "44 analyses, rangées comme le menu de Clover",
  "Chaque analyse répond à une question de gestion et propose une décision. Le catalogue des rapports les décrit toutes.");
grille(s, [["Accueil · 1", "Synthèse et décisions"],
  ["Activités de vente · 2", "ventes inhabituelles, remboursements"],
  ["Rapports · 11", "tendance, pourquoi les ventes changent, prix et volume, rythme et objectif, jours fériés, jour du mois, paniers, rabais"],
  ["Finances · 5", "pont de marge, espèces et cartes, taxes et pourboires, heures rentables, seuil de rentabilité"],
  ["Articles · 17", "rentables ou non, ruptures, articles d'appel, compléments, formats, saison, au poids, qui montent ou baissent, assortiment"],
  ["Employés · 2", "performance, achalandage et personnel"],
  ["Clients · 4", "groupes, fidélité, valeur, retour des nouveaux clients"],
  ["Prévisions · 2", "achalandage prévu, quantités prévues par article"]],
4, 1.5, 2.35, { titre: 16, corps: 12.5 });

s = contenu("Reporting", "Lire un rapport : Résumé, Graphiques, Détail",
  "Même présentation pour les 69 rapports, sous Windows et sur le web.");
const sp = [["Résumé", "Cartes à feu vert, jaune ou rouge avec la variation ▲ / ▼, puis les constats en clair : ✔ bon, ⚠ à surveiller, ✖ à agir, ℹ information"],
  ["Graphiques", "Graphique principal et deux graphiques complémentaires ; bulle au survol, clic sur la légende pour masquer une série ; évolution par jour et par mois"],
  ["Détail", "Tableau complet à la hauteur de la fenêtre ; filtre texte sur la 1re colonne et liste du groupe (catégorie, employé, jour…) ; export Excel, CSV, PDF"]];
sp.forEach(([t, d], i) => {
  const x = M + i * 4.1;
  carte(s, x, 1.5, 3.85, 3.6, "sp" + i, i === 0 ? P.vert : undefined);
  texte(s, t, { x: x + 0.25, y: 1.7, w: 3.35, h: 0.6, fontSize: 24, bold: true, color: i === 0 ? P.blanc : P.vertFonce });
  texte(s, d, { x: x + 0.25, y: 2.4, w: 3.35, h: 2.6, fontSize: 15, color: i === 0 ? P.blanc : P.texte });
});
texte(s, "Mots simples : « très vendu et rentable », « coût moyen (Sage) », « affinité »… · ruban horizontal pour les sections longues · PDF de la page complet",
  { x: M, y: 5.5, w: W - 2 * M, h: 0.7, fontSize: 14, italic: true, color: P.doux });

s = contenu("Reporting", "Savoir quand chaque traitement a eu lieu",
  "Deux tables répondent à « quand et par qui ? » : les opérations journalières et le récapitulatif des traitements.");
grille(s, [["Opérations journalières", "ventes, achats, encaissements et paiements fournisseurs inscrits dans Sage, jour par jour : traité le, par qui, d'où (nuit, Windows, web) ; ◀ ▶ et filtres"],
  ["Récapitulatif des traitements", "chaque traitement (nuit, import, saisie dans Sage) : début, fin, personne, origine, résultat"],
  ["Suivi des ventes", "chaque journée : facture, statut (importée, bloquée, remplacée par la fin de semaine), encaissement, rapprochement"],
  ["Recherche dans l'historique", "client, fournisseur, vente, encaissement, paiement, article, catégorie, employé ; plage d'articles"]],
2, 1.5, 2.2, { corps: 14.5, titre: 18 });

// ================================================================== CONFIANCE
intercalaire("Confiance", "Confiance", "Application web identique, droits fins, sécurité, qualité et rapidité.");

s = contenu("Confiance", "Une application web identique à Windows",
  "Les 76 entrées du menu existent en pages web, avec la même structure, les mêmes boutons et les mêmes droits.");
grille(s, [["Partout", "PC du bureau, Bureau à distance, téléphone ; HTTPS sans port, adresse du magasin"],
  ["Même état en temps réel", "une facture importée sur le web est archivée sous Windows, et l'inverse"],
  ["Filtres automatiques", "choisir une période ou une liste relance la page ; bandeau « Chargement… »"],
  ["Téléphone", "thème clair lisible, tableaux qui défilent, menu replié, photo de factures"],
  ["Reprise", "verrouillé après inactivité : le travail continue, la reconnexion revient à la même page"],
  ["Rapide", "Sage surveillé en arrière-plan ; chaque page en moins de 0,3 seconde"]],
3, 1.5, 2.2, { corps: 14 });

s = contenu("Confiance", "Chacun ne voit que ce qui lui est permis",
  "Les droits se règlent fonction par fonction : on peut donner « Liste des articles » sans le reste de la rubrique.");
const droits = [["Par fonction", "arbre du menu à cocher, rubrique entière ou une seule fonction"],
  ["Dans les fenêtres", "traiter la paie, restaurer une sauvegarde, lancer la nuit… refusables"],
  ["Supprimer, exporter", "deux droits à part, sur tous les boutons concernés"],
  ["Points de vente, employés", "un profil limité à un magasin ; un employé ne voit que ses heures et ses paies"]];
droits.forEach(([t, d], i) => {
  const col = i % 2, lig = Math.floor(i / 2), x = M + col * 6.1, y = 1.5 + lig * 1.9;
  carte(s, x, y, 5.85, 1.65, "droit" + i);
  pastille(s, x + 0.3, y + 0.42, 0.8, "✓", P.vert, P.blanc);
  texte(s, t, { x: x + 1.35, y: y + 0.25, w: 4.3, h: 0.5, fontSize: 19, bold: true, color: P.vertFonce });
  texte(s, d, { x: x + 1.35, y: y + 0.8, w: 4.3, h: 0.75, fontSize: 14.5 });
});
texte(s, "Mots de passe jamais en clair (mot de passe web distinct, 12 caractères) · secrets dans le coffre-fort de Windows · " +
  "3 essais faux = compte verrouillé · audit de chaque action, chaîné · écran verrouillé après 5 minutes",
{ x: M, y: 5.45, w: W - 2 * M, h: 0.8, fontSize: 14, italic: true, color: P.doux });

s = contenu("Confiance", "Testé avant chaque livraison",
  "369 tests automatiques, tour de toutes les pages web, puis essais réels sur une copie du fichier d'entreprise, " +
  "et enfin validation sur le vrai fichier.");
const qual = [["369", "tests automatiques\n(63 fichiers)"], ["0", "écriture d'essai dans\nle vrai fichier Sage"], ["30+", "scénarios d'écriture\nvalidés sur la copie"]];
qual.forEach(([n, l], i) => {
  const x = M + i * 4.1;
  texte(s, n, { x, y: 1.4, w: 3.8, h: 1.2, fontSize: 60, bold: true, color: i === 1 ? P.rouge : P.vert });
  texte(s, l, { x, y: 2.6, w: 3.8, h: 0.8, fontSize: 16 });
});
carte(s, M, 3.7, W - 2 * M, 2.6, "recette");
texte(s, "Validé sur le vrai fichier (Sage 2027, entreprise partagée)", { x: M + 0.3, y: 3.85, w: 11, h: 0.45, fontSize: 18, bold: true, color: P.vertFonce });
texte(s, puces(["221 factures de vente importées en une nuit (10 mois rattrapés), vérifiées une à une",
  "229 dépôts en retard encaissés en environ 2 heures ; les cas douteux mis de côté, à vérifier",
  "Factures fournisseurs importées par l'assistant de Sage, stock et coût Clover mis à jour",
  "Reporting vérifié sur les vraies ventes Clover (lecture seule), Windows et web"]),
{ x: M + 0.3, y: 4.35, w: W - 2 * M - 0.6, h: 1.9, fontSize: 15, paraSpaceAfter: 6 });

s = contenu("Confiance", "Des pages à moins d'une seconde",
  "Mesures techniques (aucune donnée de vente). Une année de ventes Clover se lit une fois, puis en quelques secondes ; chaque page web en moins de 0,3 seconde.");
s.addChart(pres.charts.BAR, [{ name: "Secondes", labels: ["Livre d'inventaire (préchargé)", "Liste des articles (préchargée)",
  "Tour des 64 pages web, après", "Tour des 64 pages web, avant"], values: [0.38, 0.09, 2.8, 70.5] }], {
  x: M, y: 1.45, w: 7.6, h: 4.9, barDir: "bar", showTitle: true, title: "Temps (secondes)", titleFontSize: 16,
  titleColor: P.vertFonce, titleFontFace: "+mn-lt", chartColors: [P.vert], showValue: true, dataLabelPosition: "outEnd",
  dataLabelColor: P.texte, dataLabelFontSize: 12, dataLabelFormatCode: "0.0#", dataLabelFontFace: "+mn-lt", catAxisLabelColor: P.texte, catAxisLabelFontSize: 12,
  catAxisLabelFontFace: "+mn-lt", valAxisLabelColor: P.doux, valAxisLabelFontSize: 10, valAxisLabelFontFace: "+mn-lt",
  valGridLine: { color: P.bord, size: 0.5 }, catGridLine: { style: "none" }, showLegend: false,
});
carte(s, 8.6, 1.6, W - M - 8.6, 4.6, "rapide");
texte(s, puces(["Ventes des jours terminés gardées", "Coûts de Sage relus une fois par jour", "Sage surveillé en arrière-plan",
  "Pages préparées chaque heure", "Chaque combinaison de filtres calculée une fois"], true),
{ x: 8.85, y: 1.9, w: 3.6, h: 4.0, fontSize: 16, color: P.vertFonce, paraSpaceAfter: 10 });

// ================================================================== SUITE
intercalaire("Suite", "Documentation et suite", "Tout est documenté, installé avec l'application, et tenu à jour à chaque version.");

s = contenu("Suite", "Une documentation complète",
  "Les documents sont installés dans le dossier de l'application (raccourci « Documents du projet ») et refaits à chaque fabrication.");
grille(s, [["Manuel d'utilisation", "français et anglais, adapté au profil de la personne"],
  ["Guide de l'administrateur", "installation, réseau, Sage, nuit, journaux, dépannage"],
  ["Catalogue des rapports", "les 69 rapports du Reporting : question et décision"],
  ["Documentation fonctionnelle", "chaque fonction, page par page"],
  ["Règles d'affaires", "codes RG-…, règles fixées par le propriétaire"],
  ["Architecture", "composants, données, flux, pilotage de Sage"],
  ["Workflows et processus", "pas à pas d'utilisation, processus métier en couloirs"],
  ["Plan de test, projet, notes de version", "369 tests, planning, jalons, risques, nouveautés"],
  ["Présentation des services", "document remis au client : services, démarche, engagements"]],
3, 1.5, 1.42, { titre: 15, corps: 12.5 });

s = pres.addSlide({ masterName: "TITRE", sectionTitle: "Suite" });
s.addText("Et maintenant", { placeholder: "title" });
s.addText("Deuxième point de vente réel · paiements fournisseurs et écritures du rapprochement sur le vrai fichier · " +
  "remises de retenues · comptes RIA dans Sage · pointage sur le Wi-Fi du magasin\n" +
  "Chaque lundi : lire les décisions du Reporting, agir, mesurer la semaine suivante", { placeholder: "body" });
s.addNotes("Prochaines étapes : brancher un deuxième point de vente, faire les paiements et écritures du rapprochement sur le vrai fichier, " +
  "suivre les premières remises, créer les comptes RIA, et installer le rituel du lundi avec le Reporting.");

pres.writeFile({ fileName: SORTIE }).then(async (f) => {
  if (process.env.APPLY_THEME) { // thème nommé (outil de création de présentations), facultatif
    const { applyTheme } = require(process.env.APPLY_THEME);
    await applyTheme(f, { name: "Marché MVOG-MBI", headFontFace: "Calibri", bodyFontFace: "Calibri", colors: {
      dk1: P.texte, lt1: P.blanc, dk2: P.vertFonce, lt2: P.vertPale, accent1: P.vert, accent2: P.jaune, accent3: P.rouge,
      accent4: P.doux, accent5: P.vertClair, accent6: P.bleu, hlink: P.vert, folHlink: P.vertFonce } });
  }
  console.log(f);
});
