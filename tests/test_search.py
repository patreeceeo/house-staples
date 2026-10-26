"""Search scoring, ported line-for-line from staples_site/site/app.js.

There is no JS runtime in this project (no Node), so this Python mirror checks
the algorithm against the real data. If you change the scoring in app.js,
change it here too.
"""
import re
import unicodedata

import pytest

from staples_site.build import build_time, site_data
from staples_site.data import load_data


def normalize(s):
    s = "".join(c for c in unicodedata.normalize("NFD", s) if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def edit_distance(a, b):
    d = [[i] + [0] * len(b) for i in range(len(a) + 1)]
    for j in range(1, len(b) + 1):
        d[0][j] = j
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + cost)
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                d[i][j] = min(d[i][j], d[i - 2][j - 2] + 1)
    return d[len(a)][len(b)]


def allowed_typos(n):
    return 0 if n < 4 else 1 if n < 8 else 2


def word_match(t, w):
    if w == t:
        return 1
    if w.startswith(t):
        return 0.9
    if len(t) >= 3 and w.find(t) > 0:
        return 0.6
    k = allowed_typos(len(t))
    if k == 0:
        return 0
    if edit_distance(t, w) <= k:
        return 0.5
    if len(w) > len(t) and edit_distance(t, w[:len(t)]) <= k:
        return 0.4
    return 0


def index_staple(s):
    titles = [normalize(t) for t in [s["name"], *s["aliases"]]]
    fields = [(t, 1) for t in titles]
    if s["product"]:
        fields.append((normalize(s["product"]), 0.7))
    fields.append((normalize(s["category"]), 0.5))
    words = [(w, weight) for text, weight in fields for w in text.split(" ") if w]
    return {"compact": [t.replace(" ", "") for t in titles], "words": words}


def score_staple(idx, query):
    tokens = [t for t in normalize(query).split(" ") if t]
    if not tokens:
        return 0
    q = "".join(tokens)
    best = 0
    for c in idx["compact"]:
        if c == q:
            best = max(best, 100)
        elif c.startswith(q):
            best = max(best, 80)
        elif len(q) >= 3 and c.find(q) > 0:
            best = max(best, 60)
    total = 0
    for t in tokens:
        token_best = max((weight * word_match(t, w) for w, weight in idx["words"]), default=0)
        if token_best == 0:
            return best
        total += token_best
    return max(best, 85 * total / len(tokens))


def search(query):
    staples = site_data(load_data(), build_time())["staples"]
    scored = [(score_staple(index_staple(s), query), s["name"]) for s in staples]
    return [name for score, name in sorted(scored, key=lambda x: (-x[0], len(x[1]), x[1])) if score > 0]


@pytest.mark.parametrize("query, top", [
    ("oatmilk", "Oat Milk"),
    ("oat milk", "Oat Milk"),
    ("Oat-Milk", "Oat Milk"),
    ("brocoli", "Broccoli"),
    ("brocolli", "Broccoli"),
    ("BROCCOLI", "Broccoli"),
    ("chikpeas", "Chickpeas"),
    ("pecorino", "Pecorino Romano"),
    ("peanut", "Peanut Butter"),
    ("tahni", "Tahini"),
])
def test_top_result(query, top):
    assert search(query)[0] == top


def test_tortilla_finds_tortillas_and_chips():
    results = search("tortilla")
    assert {"Tortilla Chips", "Corn Tortillas", "Flour Tortillas"} <= set(results[:3])


def test_partial_and_multiword():
    assert {"Corn Tortillas", "Flour Tortillas", "Tortilla Chips"} <= set(search("tort"))
    assert search("milk greek")[0] == "Plain Whole Milk Greek Yogurt"
    assert "Unsalted Butter" in search("butter")[:3]
    assert search("salt")[0] == "Kosher Salt"
    assert search("milk")[:2] == ["Oat Milk", "Whole Milk"]


def test_category_matches():
    results = search("spices")
    assert {"Cinnamon", "Cumin", "Kosher Salt"} <= set(results)


def test_no_false_positives():
    assert search("zzzz") == []
    assert search("") == []
    assert "Oats" not in search("oatmilk")
