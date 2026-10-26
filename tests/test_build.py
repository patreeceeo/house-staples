import json
import re
from pathlib import Path

import pytest

from staples_site.build import build, main
from tests.test_data import write

EPOCH = "1767225600"  # 2026-01-01T00:00:00Z


@pytest.fixture
def site(tmp_path, monkeypatch):
    monkeypatch.setenv("SOURCE_DATE_EPOCH", EPOCH)
    out = tmp_path / "dist"
    build(out)
    return out


def embedded(index_html: str) -> dict:
    m = re.search(r'<script id="staples-data" type="application/json">(.*?)</script>',
                  index_html, re.S)
    assert m
    return json.loads(m.group(1))


def test_files_exist(site):
    for name in ("index.html", "style.css", "app.js", "staples.json", ".nojekyll"):
        assert (site / name).is_file(), name


def test_staples_json_content(site):
    payload = json.loads((site / "staples.json").read_text())
    assert payload["built_at"] == "2026-01-01T00:00:00Z"
    assert [s["id"] for s in payload["stores"]] == ["costco", "restaurant-depot"]
    assert len(payload["staples"]) == 56
    assert payload["categories"] == sorted(payload["categories"])
    oat = next(s for s in payload["staples"] if s["id"] == "oat-milk")
    assert oat["aliases"] == ["Oatmilk"]
    assert set(oat) == {"id", "name", "category", "aliases", "product", "unit", "stores"}


def test_stores_joined_in_preference_order(tmp_path, monkeypatch):
    monkeypatch.setenv("SOURCE_DATE_EPOCH", EPOCH)
    payload = build(tmp_path / "out", write(tmp_path))
    oil = next(s for s in payload["staples"] if s["id"] == "olive-oil")
    assert oil["stores"] == [{"id": "costco", "name": "Costco"},
                             {"id": "restaurant-depot", "name": "Restaurant Depot"}]
    assert oil["product"] == "Kirkland Organic EVOO"


def test_index_embeds_same_data(site):
    html = (site / "index.html").read_text()
    assert embedded(html) == json.loads((site / "staples.json").read_text())
    assert "{{" not in html
    assert 'datetime="2026-01-01T00:00:00Z">1 January 2026</time>' in html


def test_embedded_json_cannot_close_script(tmp_path, monkeypatch):
    monkeypatch.setenv("SOURCE_DATE_EPOCH", EPOCH)
    staples = "- id: x\n  name: \"</script><b>&\"\n  category: Odd\n"
    build(tmp_path / "out", write(tmp_path, staples=staples))
    html = (tmp_path / "out" / "index.html").read_text()
    assert html.count("</script>") == 2  # data block + app.js
    assert embedded(html)["staples"][0]["name"] == "</script><b>&"


def test_relative_asset_paths(site):
    html = (site / "index.html").read_text()
    refs = re.findall(r'(?:href|src)="([^"]*)"', html)
    assert {"style.css", "app.js", "staples.json"} <= set(refs)
    for ref in refs:
        assert not ref.startswith(("/", "http:", "https:", "//")), ref


def test_deterministic_apart_from_timestamp(tmp_path, monkeypatch):
    monkeypatch.setenv("SOURCE_DATE_EPOCH", EPOCH)
    build(tmp_path / "a")
    build(tmp_path / "b")
    for f in (tmp_path / "a").iterdir():
        assert f.read_bytes() == (tmp_path / "b" / f.name).read_bytes(), f.name


def test_cli(tmp_path, capsys):
    assert main(["--out", str(tmp_path / "out")]) == 0
    assert "Built 56 staples" in capsys.readouterr().out


def test_cli_invalid_data(tmp_path, capsys):
    data = write(tmp_path, staples="- id: Bad\n  name: X\n  category: Y\n")
    assert main(["--out", str(tmp_path / "out"), "--data-dir", str(data)]) == 1
    assert "kebab-case" in capsys.readouterr().err
    assert not (tmp_path / "out").exists()
