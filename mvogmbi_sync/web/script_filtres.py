"""Seul script du site web (/filtres.js, servi par l'application, aucun script d'ailleurs ni dans la page) :

- filtres automatiques (demandes du propriétaire du 2026-11-08 et 2026-11-09 : « pas besoin de cliquer sur le
  bouton Afficher », « sur tous les filtres ») : dans un formulaire de consultation (method="get"), changer une liste,
  une case, une date ou un champ texte relance la recherche (data-manuel : pas d'envoi) ; une date choisie passe la
  période à « Personnalisée », une période choisie vide les dates ; bandeau « Chargement… » pendant le rechargement ;
  le bouton reste pour un navigateur sans script et est caché sinon (classe « sans-js ») ;
- touche Entrée : clique le bouton [data-entree] du formulaire s'il existe, et n'actionne jamais un bouton qui
  supprime ou écarte ;
- filtres de tableau pendant la frappe : <input> ou <select> data-filtre="id du tableau" data-colonnes="1,2" cache les lignes
  qui ne contiennent pas le texte tapé (majuscules et accents ignorés) ; plusieurs champs se cumulent.
"""

SCRIPT = r"""
(function () {
  document.documentElement.classList.add('js');
  function simple(t) {
    return (t || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().trim();
  }
  function soumettre(f) { if (f.requestSubmit) { f.requestSubmit(); } else { f.submit(); } }
  // tous les filtres relancent la recherche d'eux-mêmes (demande du propriétaire du 2026-11-09 : « la sélection
  // d'un filtre actualise automatiquement la page, applique cela sur tous les filtres ») : listes, cases, dates, et
  // champs texte (valeur choisie dans la liste proposée, ou champ quitté après la frappe)
  document.addEventListener('change', function (ev) {
    var c = ev.target;
    // filtre de tableau (data-filtre) : tout de suite, même hors d'un formulaire (filtres du Détail des rapports)
    if (c && c.hasAttribute && c.hasAttribute('data-filtre')) { filtrer(c.getAttribute('data-filtre')); return; }
    if (!c || !c.form || (c.form.getAttribute('method') || 'get').toLowerCase() !== 'get') { return; }
    if (c.hasAttribute('data-manuel') || c.readOnly) { return; }
    var periode = c.form.querySelector('select[name="periode"]');
    if (periode && c.type === 'date' && (c.name === 'du' || c.name === 'au')) {
      // une date choisie : période personnalisée (sinon le serveur reprendrait les dates de la période)
      var perso = Array.prototype.find.call(periode.options, function (o) { return /personnalis/i.test(o.text); });
      if (perso) { periode.value = perso.value || perso.text; }
    } else if (periode && c === periode && !/personnalis/i.test(periode.value)) {
      // une période choisie : ses dates sont recalculées par le serveur
      c.form.querySelectorAll('input[type="date"][name="du"], input[type="date"][name="au"]').forEach(function (d) {
        d.value = '';
      });
    }
    if (c.tagName === 'SELECT' || c.type === 'checkbox' || c.type === 'radio' || c.type === 'date' ||
        c.type === 'text' || c.type === 'search' || c.type === 'number' || c.type === '') { soumettre(c.form); }
  });
  // la page se relance : bandeau « Chargement… » (une période longue se lit en quelques secondes dans Clover)
  function charger() { document.documentElement.classList.add('chargement'); }
  document.addEventListener('submit', function (ev) { if (!ev.defaultPrevented) { charger(); } });
  window.addEventListener('beforeunload', charger);
  window.addEventListener('pageshow', function () { document.documentElement.classList.remove('chargement'); });
  function filtrer(id) {
    var champs = document.querySelectorAll('[data-filtre="' + id + '"]');
    var zone = document.getElementById(id);
    if (!zone) { return; }
    var lignes = zone.querySelectorAll('tbody tr, table tr');
    var vues = 0, suites = {};
    lignes.forEach(function (tr) {
      if (tr.querySelector('th')) { return; }
      var garder = true;
      champs.forEach(function (champ, n) {
        var texte = simple(champ.value);
        if (!texte) { return; }
        if (champ.hasAttribute('data-suite')) {  // ligne sans valeur (élément d'une décision) : suit la ligne d'avant
          var k0 = Number((champ.getAttribute('data-colonnes') || '0').split(',')[0]);
          var c0 = tr.children[k0] ? simple(tr.children[k0].textContent) : '';
          if (!c0) { if (suites[n] === false) { garder = false; } return; }
          suites[n] = (c0 === texte);
          if (!suites[n]) { garder = false; }
          return;
        }
        var cols = (champ.getAttribute('data-colonnes') || '').split(',').filter(Boolean).map(Number);
        var cellules = tr.children, contenu = '';
        if (cols.length) { cols.forEach(function (k) { if (cellules[k]) { contenu += ' ' + cellules[k].textContent; } }); }
        else { contenu = tr.textContent; }
        if (champ.hasAttribute('data-exact')) {  // liste déroulante : la valeur exacte (« Fidèles » n'est pas « Très fidèles »)
          if (simple(contenu) !== texte) { garder = false; }
        } else if (simple(contenu).indexOf(texte) < 0) { garder = false; }
      });
      tr.style.display = garder ? '' : 'none';
      if (garder) { vues += 1; }
    });
    var compte = document.querySelector('[data-compte="' + id + '"]');
    if (compte) { compte.textContent = vues; }
  }
  document.addEventListener('input', function (ev) {
    var c = ev.target;
    if (c && c.hasAttribute && c.hasAttribute('data-filtre')) { filtrer(c.getAttribute('data-filtre')); }
  });
  document.addEventListener('keydown', function (ev) {
    var c = ev.target;
    if (ev.key !== 'Enter' || !c || !c.form || c.tagName === 'TEXTAREA' || c.tagName === 'BUTTON') { return; }
    if (c.hasAttribute('data-filtre')) { ev.preventDefault(); return; }  // filtre de tableau : pas d'envoi
    var entree = c.form.querySelector('button[data-entree]');
    if (entree) { ev.preventDefault(); entree.click(); return; }  // action prévue pour la touche Entrée
    // sécurité : Entrée n'actionne jamais un bouton qui supprime ou écarte
    var premier = c.form.querySelector('button:not([type=button]):not([type=reset]), input[type=submit]');
    var texte = premier ? (premier.value + ' ' + premier.textContent + ' ' + premier.className) : '';
    if (/supprim|écart|ecart|danger|delete|🗑/i.test(texte)) { ev.preventDefault(); }
  });
  document.addEventListener('click', function (ev) {  // les liens d'une liste gardent les filtres tapés
    var a = ev.target && ev.target.closest ? ev.target.closest('a[href]') : null;
    var zone = a ? a.closest('[data-garder]') : null;
    if (!zone) { return; }
    var url = new URL(a.href, location.href);
    zone.getAttribute('data-garder').split(',').forEach(function (nom) {
      var champ = document.querySelector('[name="' + nom + '"]');
      if (champ && champ.value) { url.searchParams.set(nom, champ.value); } else { url.searchParams.delete(nom); }
    });
    a.href = url.toString();
  }, true);
  // zones à la hauteur de la fenêtre (statistiques : menu des états et rapport défilent chacun, le tableau remplit
  // la place ; demande du propriétaire du 2026-11-09 : « il faut ajuster les tableaux à la taille de la fenêtre »)
  function ajuster() {
    document.querySelectorAll('[data-pleine-hauteur]').forEach(function (z) {
      if (window.innerWidth <= 820) { z.style.height = ''; return; }
      var haut = z.getBoundingClientRect().top + window.scrollY;
      z.style.height = Math.max(420, window.innerHeight - haut - 12) + 'px';
    });
  }
  window.addEventListener('resize', ajuster);
  // graphiques dynamiques (demande du propriétaire du 2026-11-09) : bulle immédiate qui suit la souris (texte du
  // <title> de l'élément), élément survolé surligné, clic sur un nom de la légende = série masquée ou réaffichée
  var bulle = null;
  function preparerGraphiques() {
    document.querySelectorAll('svg .g-zone, svg .g-part, svg .g-serie').forEach(function (el) {
      var titre = el.querySelector('title');
      if (titre) { el.setAttribute('data-bulle', titre.textContent); titre.remove(); }
    });
  }
  function montrerBulle(texte, ev) {
    if (!bulle) { bulle = document.createElement('div'); bulle.className = 'bulle-graph'; document.body.appendChild(bulle); }
    bulle.textContent = texte;
    bulle.hidden = false;
    var x = ev.clientX + 14, y = ev.clientY + 14;
    var l = bulle.offsetWidth, h = bulle.offsetHeight;
    if (x + l > window.innerWidth - 8) { x = ev.clientX - l - 14; }
    if (y + h > window.innerHeight - 8) { y = ev.clientY - h - 14; }
    bulle.style.left = x + 'px';
    bulle.style.top = y + 'px';
  }
  document.addEventListener('mousemove', function (ev) {
    var el = ev.target && ev.target.closest ? ev.target.closest('svg [data-bulle]') : null;
    if (el) { montrerBulle(el.getAttribute('data-bulle'), ev); } else if (bulle) { bulle.hidden = true; }
  });
  document.addEventListener('mouseleave', function () { if (bulle) { bulle.hidden = true; } });
  document.addEventListener('click', function (ev) {
    var leg = ev.target && ev.target.closest ? ev.target.closest('svg .g-leg') : null;
    if (!leg) { return; }
    var svg = leg.closest('svg'), serie = leg.getAttribute('data-serie');
    var masque = !leg.classList.contains('masque');
    leg.classList.toggle('masque', masque);
    svg.querySelectorAll('.g-serie[data-serie="' + serie + '"]').forEach(function (el) {
      el.classList.toggle('masque', masque);
    });
  });
  document.addEventListener('DOMContentLoaded', function () {
    ajuster();
    preparerGraphiques();
    var choisie = document.querySelector('[data-choisie]');  // facture choisie : visible dans la liste
    if (choisie && choisie.scrollIntoView) { choisie.scrollIntoView({block: 'nearest'}); }
    var vus = {};
    document.querySelectorAll('[data-filtre]').forEach(function (c) {
      var id = c.getAttribute('data-filtre');
      if (!vus[id] && c.value) { vus[id] = 1; filtrer(id); }
    });
  });
})();
"""
