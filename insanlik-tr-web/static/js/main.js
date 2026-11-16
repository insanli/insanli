/* İnsanlık Eli portfolio — small enhancements; every page works without them. */
(function () {
  var d = document;
  try { localStorage.setItem('lang', d.documentElement.lang); } catch (e) {}

  var hdr = d.querySelector('.hdr');
  var onScroll = function () { if (hdr) hdr.classList.toggle('scrolled', window.scrollY > 8); };
  window.addEventListener('scroll', onScroll, { passive: true }); onScroll();

  var btn = d.querySelector('.menu-btn');
  if (btn) {
    btn.addEventListener('click', function () {
      var open = d.body.classList.toggle('menu-open');
      btn.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
    d.querySelectorAll('.mainnav a').forEach(function (a) {
      a.addEventListener('click', function (e) {
        var li = a.parentElement;
        if (li.classList.contains('has-sub') && a.classList.contains('snav-top') && window.matchMedia('(max-width: 1280px)').matches) {
          e.preventDefault();
          var o = li.classList.toggle('open');
          a.setAttribute('aria-expanded', o ? 'true' : 'false');
          return;
        }
        d.body.classList.remove('menu-open'); btn.setAttribute('aria-expanded', 'false');
      });
    });
    d.addEventListener('keydown', function (e) { if (e.key === 'Escape') { d.body.classList.remove('menu-open'); btn.setAttribute('aria-expanded', 'false'); } });
  }

  // Reports menu: clicking a category opens its contents (the phone menu keeps its own open/close above)
  var repClose = function (except) {
    d.querySelectorAll('.shdr li.rep-drop.open').forEach(function (x) { if (x !== except) { x.classList.remove('open'); x.firstElementChild.setAttribute('aria-expanded', 'false'); } });
  };
  d.querySelectorAll('.shdr li.rep-drop > a').forEach(function (a) {
    a.addEventListener('click', function (e) {
      if (a.closest('.mainnav') && window.matchMedia('(max-width: 1280px)').matches) return;
      e.preventDefault();
      var li = a.parentElement, o = !li.classList.contains('open');
      repClose(li); li.classList.toggle('open', o); a.setAttribute('aria-expanded', o ? 'true' : 'false');
    });
  });
  d.addEventListener('click', function (e) { if (!e.target.closest('.rep-drop')) repClose(null); });
  d.addEventListener('keydown', function (e) { if (e.key === 'Escape') repClose(null); });

  // project list filters (sector + country), also reads ?country= / ?sector= from the address.
  // The projects are not listed at once: under the boxes every country shows its tiles (36 Projects / Quick Interventions /
  // Situation Update); choosing a sector or a country narrows these rows, and the Projects tile then opens the projects.
  // A link that names a country or sector (…?country=gaza) lists the projects straight away.
  var box = d.querySelector('.filters[data-filter-for]');
  if (box) {
    var list = d.querySelector(box.getAttribute('data-filter-for'));
    var sels = box.querySelectorAll('select[data-filter]');
    var counter = box.querySelector('[data-count]');
    var empty = d.querySelector('.empty');
    var tiles = d.getElementById('ptiles');
    var params = new URLSearchParams(location.search);
    sels.forEach(function (s) { var v = params.get(s.getAttribute('data-filter')); if (v) s.value = v; });
    var asTiles = !!tiles && (params.get('view') === 'tiles' || !(params.get('country') || params.get('sector')));
    var apply = function () {
      var f = {}; sels.forEach(function (s) { f[s.getAttribute('data-filter')] = s.value; });
      var n = 0, per = {}, shown = 0;
      list.querySelectorAll('.pcard').forEach(function (c) {
        var ok = (!f.sector || c.getAttribute('data-sector') === f.sector || (' ' + (c.getAttribute('data-groups') || '') + ' ').indexOf(' ' + f.sector + ' ') > -1) && (!f.country || c.getAttribute('data-country') === f.country);
        c.classList.toggle('is-hidden', !ok);
        if (ok) { n++; var k = c.getAttribute('data-country'); per[k] = (per[k] || 0) + 1; }
      });
      if (tiles) {
        d.documentElement.classList.toggle('plist-on', !asTiles);   // plist-on = the list of projects, otherwise the country tiles
        if (asTiles) tiles.querySelectorAll('.country-row').forEach(function (r) {
          var c = r.getAttribute('data-country'), k = per[c] || 0;
          var on = f.country ? c === f.country : (k > 0 || !f.sector);   // chosen country; or every country that has such projects
          r.hidden = !on; if (on) shown++;
          var a = r.querySelector('a.opp[href*="country="]'), num = a && a.querySelector('strong');
          if (!a) return;
          if (num) num.textContent = k;   // number of matching projects of this country
          var lq = new URLSearchParams(); if (f.sector) lq.set('sector', f.sector); lq.set('country', c);
          a.setAttribute('href', location.pathname + '?' + lq);
        });
      }
      if (counter) counter.textContent = n;
      if (empty) empty.hidden = asTiles ? shown > 0 : n > 0;
      var q = new URLSearchParams(); Object.keys(f).forEach(function (k) { if (f[k]) q.set(k, f[k]); });
      if (asTiles && q.toString()) q.set('view', 'tiles');
      history.replaceState(null, '', location.pathname + (q.toString() ? '?' + q : ''));
    };
    sels.forEach(function (s) { s.addEventListener('change', function () { asTiles = !!tiles; apply(); }); });
    apply();
  }

  // campaign tables: show only rows for one country
  d.querySelectorAll('[data-row-filter]').forEach(function (bar) {
    var scope = d.querySelector(bar.getAttribute('data-row-filter'));
    var pills = bar.querySelectorAll('.pill');
    pills.forEach(function (p) {
      p.addEventListener('click', function () {
        var v = p.getAttribute('data-value');
        pills.forEach(function (x) { x.classList.toggle('on', x === p); });
        scope.querySelectorAll('tbody tr[data-text]').forEach(function (tr) {
          tr.classList.toggle('is-hidden', !!v && tr.getAttribute('data-text').indexOf(v) === -1);
        });
        scope.querySelectorAll('.qcat').forEach(function (g) {
          var any = g.querySelector('tbody tr[data-text]:not(.is-hidden)');
          g.style.display = any ? '' : 'none';
        });
      });
    });
  });
})();

/* chart tooltips (values are also printed next to each bar and in the table) */
(function () {
  var tip = document.querySelector('.tip');
  if (!tip) return;
  var strong = tip.querySelector('strong'), span = tip.querySelector('span');
  function show(el, x, y) {
    strong.textContent = el.getAttribute('data-tip-value');
    span.textContent = el.getAttribute('data-tip-label');
    tip.hidden = false;
    var r = tip.getBoundingClientRect();
    tip.style.left = Math.min(window.innerWidth - r.width - 8, x + 14) + 'px';
    tip.style.top = Math.max(8, y - r.height - 10) + 'px';
  }
  document.querySelectorAll('[data-tip-value]').forEach(function (el) {
    el.addEventListener('pointermove', function (e) { show(el, e.clientX, e.clientY); });
    el.addEventListener('pointerleave', function () { tip.hidden = true; });
    el.addEventListener('focus', function () { var b = el.getBoundingClientRect(); show(el, b.left + b.width / 2, b.top); });
    el.addEventListener('blur', function () { tip.hidden = true; });
  });
})();
