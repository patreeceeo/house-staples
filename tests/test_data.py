from pathlib import Path

import pytest

from staples_site.data import DEFAULT_DATA_DIR, HouseData, Staple, Store, ValidationError, load_data
from staples_site.validate import main

STORES = """\
- id: costco
  name: Costco
- id: restaurant-depot
  name: Restaurant Depot
"""

STAPLES = """\
- id: bananas
  name: Bananas
  category: Produce
  stores: []
- id: olive-oil
  name: Olive Oil
  aliases: [EVOO]
  category: Oils
  stores: [costco, restaurant-depot]
  product: Kirkland Organic EVOO
  unit: 2L
"""


def write(tmp_path: Path, staples: str = STAPLES, stores: str = STORES) -> Path:
    (tmp_path / "staples.yaml").write_text(staples)
    (tmp_path / "stores.yaml").write_text(stores)
    return tmp_path


def problems_for(tmp_path: Path, **kw) -> list[str]:
    with pytest.raises(ValidationError) as exc:
        load_data(write(tmp_path, **kw))
    return [str(p) for p in exc.value.problems]


def test_valid_data(tmp_path):
    data = load_data(write(tmp_path))
    assert isinstance(data, HouseData)
    assert data.stores == [Store("costco", "Costco"), Store("restaurant-depot", "Restaurant Depot")]
    assert data.staples[0] == Staple("bananas", "Bananas", "Produce")
    oil = data.staples[1]
    assert oil.aliases == ["EVOO"]
    assert oil.stores == ["costco", "restaurant-depot"]
    assert (oil.product, oil.unit) == ("Kirkland Organic EVOO", "2L")
    assert data.stores_by_id["costco"].name == "Costco"


def test_stores_field_optional(tmp_path):
    data = load_data(write(tmp_path, staples="- {id: salt, name: Salt, category: Spices}\n"))
    assert data.staples[0].stores == []


def test_real_data_validates():
    data = load_data(DEFAULT_DATA_DIR)
    assert data.staples and data.stores


@pytest.mark.parametrize("staples, expected", [
    ("- {name: Salt, category: Spices}\n", "staples.yaml [#0]: missing required field 'id'"),
    ("- {id: salt, category: Spices}\n", "staples.yaml [salt]: missing required field 'name'"),
    ("- {id: salt, name: Salt}\n", "staples.yaml [salt]: missing required field 'category'"),
    ("- {id: salt, name: '', category: Spices}\n", "'name' must be a non-empty string"),
    ("- {id: Sea_Salt, name: Salt, category: Spices}\n", "id 'Sea_Salt' is not kebab-case"),
    ("- {id: salt, name: Salt, category: Spices}\n- {id: salt, name: Salt 2, category: Spices}\n",
     "staples.yaml [salt]: duplicate id"),
    ("- {id: salt, name: Salt, category: Spices, stores: [aldi]}\n", "unknown store 'aldi'"),
    ("- {id: salt, name: Salt, category: Spices, stores: [costco, costco]}\n",
     "store 'costco' listed more than once"),
    ("- {id: salt, name: Salt, category: Spices, stores: costco}\n",
     "'stores' must be a list of non-empty strings"),
    ("- {id: salt, name: Salt, category: Spices, aliases: [1]}\n",
     "'aliases' must be a list of non-empty strings"),
    ("- {id: salt, name: Salt, category: Spices, colour: white}\n", "unknown field 'colour'"),
    ("- {id: salt, name: Salt, category: Spices, unit: 5}\n", "'unit' must be a non-empty string"),
    ("- just a string\n", "staples.yaml [#0]: entry must be a mapping"),
    ("id: salt\n", "staples.yaml: top level must be a list"),
    ("- [unclosed\n", "staples.yaml: invalid YAML"),
])
def test_staple_problems(tmp_path, staples, expected):
    problems = problems_for(tmp_path, staples=staples)
    assert any(expected in p for p in problems), problems


@pytest.mark.parametrize("stores, expected", [
    ("- {name: Costco}\n", "stores.yaml [#0]: missing required field 'id'"),
    ("- {id: costco}\n", "stores.yaml [costco]: missing required field 'name'"),
    ("- {id: Costco, name: Costco}\n", "id 'Costco' is not kebab-case"),
    ("- {id: costco, name: A}\n- {id: costco, name: B}\n", "stores.yaml [costco]: duplicate id"),
])
def test_store_problems(tmp_path, stores, expected):
    problems = problems_for(tmp_path, staples="[]\n", stores=stores)
    assert any(expected in p for p in problems), problems


def test_missing_file(tmp_path):
    with pytest.raises(ValidationError) as exc:
        load_data(tmp_path)
    assert {str(p) for p in exc.value.problems} == {
        "stores.yaml: file not found", "staples.yaml: file not found"}


def test_all_problems_reported(tmp_path):
    staples = ("- {id: a, name: A, category: X, stores: [nope]}\n"
               "- {id: B, name: B, category: X}\n"
               "- {id: c, name: C}\n")
    problems = problems_for(tmp_path, staples=staples)
    assert len(problems) == 3


def test_cli_ok(tmp_path, capsys):
    assert main(["--data-dir", str(write(tmp_path))]) == 0
    assert "OK: 2 staples (1 with stores), 2 stores" in capsys.readouterr().out


def test_cli_failure(tmp_path, capsys):
    write(tmp_path, staples="- {id: salt, name: Salt, category: X, stores: [aldi]}\n")
    assert main(["--data-dir", str(tmp_path)]) == 1
    assert "unknown store 'aldi'" in capsys.readouterr().err
