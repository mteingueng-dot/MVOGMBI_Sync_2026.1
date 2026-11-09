"""Seul script du site web (/filtres.js, servi par l'application, aucun script d'ailleurs ni dans la page) :

- filtres automatiques (demande du propriétaire du 2026-11-08 : « pas besoin de cliquer sur le bouton Afficher ») :
  dans un formulaire de consultation (method="get"), changer une liste, une case ou une date relance la recherche ;
  le bouton reste pour un navigateur sans script et est caché sinon (classe « sans-js ») ;
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
  document.addEventListener('change', function (ev) {
    var c = ev.target;
    if (!c || !c.form || (c.form.getAttribute('method') || 'get').toLowerCase() !== 'get') { return; }
    if (c.hasAttribute('data-filtre')) { filtrer(c.getAttribute('data-filtre')); return; }
    if (c.tagName === 'SELECT' || c.type === 'checkbox' || c.type === 'radio' || c.type === 'date') { soumettre(c.form); }
  });
  function filtrer(id) {
    var champs = document.querySelectorAll('[data-filtre="' + id + '"]');
    var zone = document.getElementById(id);
    if (!zone) { return; }
    var lignes = zone.querySelectorAll('tbody tr, table tr');
    var vues = 0;
    lignes.forEach(function (tr) {
      if (tr.querySelector('th')) { return; }
      var garder = true;
      champs.forEach(function (champ) {
        var texte = simple(champ.value);
        if (!texte) { return; }
        var cols = (champ.getAttribute('data-colonnes') || '').split(',').filter(Boolean).map(Number);
        var cellules = tr.children, contenu = '';
        if (cols.length) { cols.forEach(function (k) { if (cellules[k]) { contenu += ' ' + cellules[k].textContent; } }); }
        else { contenu = tr.textContent; }
        if (simple(contenu).indexOf(texte) < 0) { garder = false; }
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
  document.addEventListener('keydown', function (ev) {  // Entrée dans un filtre de tableau : pas d'envoi du formulaire
    var c = ev.target;
    if (ev.key === 'Enter' && c && c.hasAttribute && c.hasAttribute('data-filtre')) { ev.preventDefault(); }
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
  document.addEventListener('DOMContentLoaded', function () {
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
