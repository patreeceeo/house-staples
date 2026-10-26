"""Load and validate data/staples.yaml and data/stores.yaml.

Public API:
    load_data(data_dir) -> HouseData   (raises ValidationError listing every problem)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = REPO_ROOT / "data"

STAPLES_FILE = "staples.yaml"
STORES_FILE = "stores.yaml"

KEBAB_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")

STORE_FIELDS = {"id", "name"}
STAPLE_REQUIRED = {"id", "name", "category"}
STAPLE_FIELDS = STAPLE_REQUIRED | {"aliases", "stores", "product", "unit"}


@dataclass(frozen=True)
class Store:
    id: str
    name: str


@dataclass(frozen=True)
class Staple:
    id: str
    name: str
    category: str
    aliases: list[str] = field(default_factory=list)
    stores: list[str] = field(default_factory=list)  # store ids, preferred first
    product: str | None = None
    unit: str | None = None


@dataclass(frozen=True)
class HouseData:
    staples: list[Staple]
    stores: list[Store]

    @property
    def stores_by_id(self) -> dict[str, Store]:
        return {s.id: s for s in self.stores}


@dataclass(frozen=True)
class Problem:
    file: str
    item: str | None  # item id, or "#<index>" if it has no usable id
    message: str

    def __str__(self) -> str:
        where = f"{self.file} [{self.item}]" if self.item else self.file
        return f"{where}: {self.message}"


class ValidationError(Exception):
    def __init__(self, problems: list[Problem]):
        self.problems = problems
        lines = "\n".join(f"  - {p}" for p in problems)
        super().__init__(f"{len(problems)} data problem(s):\n{lines}")


def _read_list(path: Path, problems: list[Problem]) -> list:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        problems.append(Problem(path.name, None, "file not found"))
        return []
    except yaml.YAMLError as e:
        problems.append(Problem(path.name, None, f"invalid YAML: {e}"))
        return []
    if raw is None:
        return []
    if not isinstance(raw, list):
        problems.append(Problem(path.name, None, "top level must be a list"))
        return []
    return raw


def _is_str(value) -> bool:
    return isinstance(value, str) and value.strip() != ""


def _check_entry(fname: str, index: int, entry, required: set, allowed: set,
                 problems: list[Problem]) -> str | None:
    """Common checks for one list entry. Returns a label for messages, or None if unusable."""
    if not isinstance(entry, dict):
        problems.append(Problem(fname, f"#{index}", "entry must be a mapping"))
        return None
    raw_id = entry.get("id")
    label = raw_id if _is_str(raw_id) else f"#{index}"
    for key in sorted(required):
        if key not in entry or entry[key] is None:
            problems.append(Problem(fname, label, f"missing required field '{key}'"))
        elif not _is_str(entry[key]):
            problems.append(Problem(fname, label, f"'{key}' must be a non-empty string"))
    for key in sorted(set(entry) - allowed):
        problems.append(Problem(fname, label, f"unknown field '{key}'"))
    if _is_str(raw_id) and not KEBAB_RE.match(raw_id):
        problems.append(Problem(fname, label, f"id '{raw_id}' is not kebab-case"))
    return label


def _check_unique_ids(fname: str, entries: list, problems: list[Problem]) -> None:
    seen: set[str] = set()
    for e in entries:
        if isinstance(e, dict) and _is_str(e.get("id")):
            if e["id"] in seen:
                problems.append(Problem(fname, e["id"], "duplicate id"))
            seen.add(e["id"])


def _str_list(fname: str, label: str, entry: dict, key: str,
              problems: list[Problem]) -> list[str]:
    value = entry.get(key)
    if value is None:
        return []
    if not isinstance(value, list) or not all(_is_str(v) for v in value):
        problems.append(Problem(fname, label, f"'{key}' must be a list of non-empty strings"))
        return []
    return value


def load_data(data_dir: Path = DEFAULT_DATA_DIR) -> HouseData:
    """Load and validate both data files. Raises ValidationError with every problem found."""
    data_dir = Path(data_dir)
    problems: list[Problem] = []

    raw_stores = _read_list(data_dir / STORES_FILE, problems)
    raw_staples = _read_list(data_dir / STAPLES_FILE, problems)

    stores: list[Store] = []
    for i, entry in enumerate(raw_stores):
        if _check_entry(STORES_FILE, i, entry, STORE_FIELDS, STORE_FIELDS, problems) is not None:
            stores.append(Store(id=entry.get("id"), name=entry.get("name")))
    _check_unique_ids(STORES_FILE, raw_stores, problems)
    store_ids = {s.id for s in stores}

    staples: list[Staple] = []
    for i, entry in enumerate(raw_staples):
        label = _check_entry(STAPLES_FILE, i, entry, STAPLE_REQUIRED, STAPLE_FIELDS, problems)
        if label is None:
            continue
        aliases = _str_list(STAPLES_FILE, label, entry, "aliases", problems)
        store_refs = _str_list(STAPLES_FILE, label, entry, "stores", problems)
        seen: set[str] = set()
        for ref in store_refs:
            if ref in seen:
                problems.append(Problem(STAPLES_FILE, label, f"store '{ref}' listed more than once"))
            elif ref not in store_ids:
                problems.append(Problem(STAPLES_FILE, label, f"unknown store '{ref}'"))
            seen.add(ref)
        for key in ("product", "unit"):
            if entry.get(key) is not None and not _is_str(entry[key]):
                problems.append(Problem(STAPLES_FILE, label, f"'{key}' must be a non-empty string"))
        staples.append(Staple(
            id=entry.get("id"),
            name=entry.get("name"),
            category=entry.get("category"),
            aliases=aliases,
            stores=store_refs,
            product=entry.get("product"),
            unit=entry.get("unit"),
        ))
    _check_unique_ids(STAPLES_FILE, raw_staples, problems)

    if problems:
        raise ValidationError(problems)
    return HouseData(staples=staples, stores=stores)
