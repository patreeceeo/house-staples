// House Staples: client-side search over data embedded in index.html.
// The scoring functions (normalize, editDistance, wordMatch, scoreStaple) are
// mirrored in tests/test_search.py; keep the two in step.
(function () {
  "use strict";

  // ---- Search scoring ------------------------------------------------------

  // Lowercase, strip accents, turn punctuation into spaces.
  function normalize(s) {
    return s.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase()
      .replace(/[^a-z0-9]+/g, " ").trim();
  }

  // Optimal string alignment distance (Levenshtein plus adjacent swaps).
  function editDistance(a, b) {
    var d = [];
    for (var i = 0; i <= a.length; i++) d.push([i]);
    for (var j = 1; j <= b.length; j++) d[0][j] = j;
    for (i = 1; i <= a.length; i++) {
      for (j = 1; j <= b.length; j++) {
        var cost = a[i - 1] === b[j - 1] ? 0 : 1;
        d[i][j] = Math.min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + cost);
        if (i > 1 && j > 1 && a[i - 1] === b[j - 2] && a[i - 2] === b[j - 1]) {
          d[i][j] = Math.min(d[i][j], d[i - 2][j - 2] + 1);
        }
      }
    }
    return d[a.length][b.length];
  }

  // Typos allowed for a query token of this length.
  function allowedTypos(len) { return len < 4 ? 0 : len < 8 ? 1 : 2; }

  // How well one query token matches one word (0..1).
  function wordMatch(t, w) {
    if (w === t) return 1;
    if (w.indexOf(t) === 0) return 0.9;
    if (t.length >= 3 && w.indexOf(t) > 0) return 0.6;
    var k = allowedTypos(t.length);
    if (k === 0) return 0;
    if (editDistance(t, w) <= k) return 0.5;
    if (w.length > t.length && editDistance(t, w.slice(0, t.length)) <= k) return 0.4;
    return 0;
  }

  // Pre-compute the searchable text for a staple.
  function indexStaple(s) {
    var titles = [s.name].concat(s.aliases).map(normalize);
    var fields = titles.map(function (t) { return { text: t, weight: 1 }; });
    if (s.product) fields.push({ text: normalize(s.product), weight: 0.7 });
    fields.push({ text: normalize(s.category), weight: 0.5 });
    var words = [];
    fields.forEach(function (f) {
      f.text.split(" ").forEach(function (w) { if (w) words.push({ w: w, weight: f.weight }); });
    });
    return { compact: titles.map(function (t) { return t.replace(/ /g, ""); }), words: words };
  }

  // Score a staple's index against a query (0 = no match, higher = better).
  function scoreStaple(idx, query) {
    var tokens = normalize(query).split(" ").filter(Boolean);
    if (!tokens.length) return 0;
    var q = tokens.join("");
    var best = 0;
    // Whole query against name/aliases with spaces removed ("oatmilk" ~ "Oat Milk").
    idx.compact.forEach(function (c) {
      if (c === q) best = Math.max(best, 100);
      else if (c.indexOf(q) === 0) best = Math.max(best, 80);
      else if (q.length >= 3 && c.indexOf(q) > 0) best = Math.max(best, 60);
    });
    // Every token must match some word; average the best match per token.
    var total = 0;
    for (var i = 0; i < tokens.length; i++) {
      var tokenBest = 0;
      idx.words.forEach(function (x) {
        tokenBest = Math.max(tokenBest, x.weight * wordMatch(tokens[i], x.w));
      });
      if (tokenBest === 0) return best;
      total += tokenBest;
    }
    return Math.max(best, 85 * total / tokens.length);
  }

  // ---- Order schedule ------------------------------------------------------

  var DAY_MS = 864e5;

  // "2026-10-27" -> days since the epoch (UTC, so no time-zone drift).
  function dayNumber(iso) {
    var p = iso.split("-").map(Number);
    return Date.UTC(p[0], p[1] - 1, p[2]) / DAY_MS;
  }

  function todayNumber() {
    var now = new Date();
    return Date.UTC(now.getFullYear(), now.getMonth(), now.getDate()) / DAY_MS;
  }

  // First order day on or after `today` for a {every_weeks, starting} schedule.
  function nextOrderDay(schedule, today) {
    var start = dayNumber(schedule.starting);
    var period = schedule.every_weeks * 7;
    if (today <= start) return start;
    return start + Math.ceil((today - start) / period) * period;
  }

  function formatDay(day) {
    return new Date(day * DAY_MS).toLocaleDateString(undefined,
      { weekday: "short", month: "short", day: "numeric", timeZone: "UTC" });
  }

  function relativeDay(day, today) {
    var n = day - today;
    return n === 0 ? "today" : n === 1 ? "tomorrow" : "in " + n + " days";
  }

  // ---- Page ----------------------------------------------------------------

  var data = JSON.parse(document.getElementById("staples-data").textContent);
  var staples = data.staples.map(function (s) { s.idx = indexStaple(s); return s; });
  var els = {
    q: document.getElementById("q"),
    store: document.getElementById("store-filter"),
    category: document.getElementById("category-filter"),
    sort: document.getElementById("sort"),
    status: document.getElementById("status"),
    results: document.getElementById("results")
  };

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }

  function addOptions(select, items) {
    items.forEach(function (it) {
      var o = el("option", null, it.label);
      o.value = it.value;
      select.appendChild(o);
    });
  }

  addOptions(els.store, data.stores.map(function (s) { return { value: s.id, label: s.name }; })
    .concat([{ value: "-none", label: "No store set yet" }]));
  addOptions(els.category, data.categories.map(function (c) { return { value: c, label: c }; }));

  var today = todayNumber();
  var nextOrders = data.stores
    .filter(function (s) { return s.order_schedule; })
    .map(function (s) { return { store: s, day: nextOrderDay(s.order_schedule, today) }; })
    .sort(function (a, b) { return a.day - b.day || a.store.name.localeCompare(b.store.name); });
  var nextOrderByStore = {};
  nextOrders.forEach(function (o) { nextOrderByStore[o.store.id] = o.day; });

  function renderNextOrders() {
    if (!nextOrders.length) return;
    var list = document.getElementById("next-orders-list");
    nextOrders.forEach(function (o, i) {
      var li = el("li", i === 0 ? "next-order soonest" : "next-order");
      li.appendChild(el("span", "next-order-store", o.store.name));
      var when = el("span", "next-order-date", formatDay(o.day) + " ");
      when.appendChild(el("span", "next-order-when", "· " + relativeDay(o.day, today)));
      li.appendChild(when);
      list.appendChild(li);
    });
    document.getElementById("next-orders").hidden = false;
  }

  function renderItem(s) {
    var li = el("li", "item");
    var head = el("div", "item-head");
    head.appendChild(el("span", "item-name", s.name));
    head.appendChild(el("span", "item-category", s.category));
    li.appendChild(head);
    var detail = [s.product, s.unit].filter(Boolean).join(" · ");
    if (detail) li.appendChild(el("div", "item-detail", detail));
    if (s.stores.length) {
      var ul = el("ul", "stores");
      ul.setAttribute("aria-label", "Stores, usual first");
      s.stores.forEach(function (st, i) {
        var chip = el("li", i === 0 ? "chip usual" : "chip", st.name);
        var title = i === 0 ? ["Usual store"] : [];
        if (st.id in nextOrderByStore) title.push("next order " + formatDay(nextOrderByStore[st.id]));
        if (title.length) chip.title = title.join(", ");
        ul.appendChild(chip);
      });
      li.appendChild(ul);
    } else {
      li.appendChild(el("div", "no-store", "No store set yet"));
    }
    return li;
  }

  function renderList(parent, items) {
    var ul = el("ul", "list");
    items.forEach(function (s) { ul.appendChild(renderItem(s)); });
    parent.appendChild(ul);
  }

  function byName(a, b) { return a.name.localeCompare(b.name); }
  // Equal scores: shorter names are closer matches ("Whole Milk" before "Coconut Milk").
  function byRank(a, b) { return b.score - a.score || a.s.name.length - b.s.name.length || byName(a.s, b.s); }

  function update() {
    var query = els.q.value;
    var store = els.store.value;
    var category = els.category.value;
    var list = staples.filter(function (s) {
      if (category && s.category !== category) return false;
      if (store === "-none") return s.stores.length === 0;
      return !store || s.stores.some(function (st) { return st.id === store; });
    });

    var searching = normalize(query) !== "";
    els.sort.disabled = searching; // search results are ranked instead
    els.results.textContent = "";
    if (searching) {
      list = list.map(function (s) { return { s: s, score: scoreStaple(s.idx, query) }; })
        .filter(function (r) { return r.score > 0; })
        .sort(byRank)
        .map(function (r) { return r.s; });
      renderList(els.results, list);
    } else if (els.sort.value === "name") {
      renderList(els.results, list.slice().sort(byName));
    } else {
      data.categories.forEach(function (c) {
        var items = list.filter(function (s) { return s.category === c; }).sort(byName);
        if (!items.length) return;
        var section = el("section", "group");
        section.appendChild(el("h2", null, c));
        renderList(section, items);
        els.results.appendChild(section);
      });
    }
    els.status.textContent = list.length === 1 ? "1 staple" :
      list.length ? list.length + " staples" : "No matching staples";
  }

  [els.q, els.store, els.category, els.sort].forEach(function (e) {
    e.addEventListener(e === els.q ? "input" : "change", update);
  });
  renderNextOrders();
  update();
})();
