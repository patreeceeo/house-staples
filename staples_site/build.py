"""Build the static site.

Usage: uv run python -m staples_site.build [--out dist] [--data-dir data]

Renders staples_site/site/index.html (embedding the data so the page works from
file://), copies the other site assets, and writes staples.json. Output is
deterministic apart from the build timestamp; set SOURCE_DATE_EPOCH to pin it.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from staples_site.data import DEFAULT_DATA_DIR, HouseData, Store, ValidationError, load_data

SITE_DIR = Path(__file__).resolve().parent / "site"
TEMPLATE = "index.html"
STATIC_FILES = ("style.css", "app.js")
DEFAULT_OUT = Path("dist")


def build_time() -> datetime:
    epoch = os.environ.get("SOURCE_DATE_EPOCH")
    if epoch:
        return datetime.fromtimestamp(int(epoch), tz=timezone.utc)
    return datetime.now(timezone.utc).replace(microsecond=0)


def order_schedule(store: Store) -> dict | None:
    sched = store.order_schedule
    if sched is None:
        return None
    return {"every_weeks": sched.every_weeks, "starting": sched.starting.isoformat()}


def site_data(data: HouseData, built_at: datetime) -> dict:
    """The JSON payload: staples joined with store names, in preference order."""
    stores = data.stores_by_id
    return {
        "built_at": built_at.isoformat().replace("+00:00", "Z"),
        "stores": [{"id": s.id, "name": s.name, "order_schedule": order_schedule(s)}
                   for s in data.stores],
        "categories": sorted({s.category for s in data.staples}),
        "staples": [
            {
                "id": s.id,
                "name": s.name,
                "category": s.category,
                "aliases": list(s.aliases),
                "product": s.product,
                "unit": s.unit,
                "stores": [{"id": sid, "name": stores[sid].name} for sid in s.stores],
            }
            for s in data.staples
        ],
    }


def embed_json(payload: dict) -> str:
    """JSON safe to place inside a <script> element."""
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return text.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def render_index(payload: dict, built_at: datetime) -> str:
    template = (SITE_DIR / TEMPLATE).read_text(encoding="utf-8")
    values = {
        "built_at": html.escape(payload["built_at"]),
        "built_date": f"{built_at.day} {built_at:%B %Y}",
        "staple_count": str(len(payload["staples"])),
        "data_json": embed_json(payload),
    }
    for key, value in values.items():
        template = template.replace("{{" + key + "}}", value)
    return template


def build(out_dir: Path = DEFAULT_OUT, data_dir: Path = DEFAULT_DATA_DIR) -> dict:
    """Build the site into out_dir (overwriting the files it writes). Returns the JSON payload."""
    data = load_data(data_dir)
    built_at = build_time()
    payload = site_data(data, built_at)

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    (out_dir / "index.html").write_text(render_index(payload, built_at), encoding="utf-8")
    for name in STATIC_FILES:
        shutil.copyfile(SITE_DIR / name, out_dir / name)
    (out_dir / "staples.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out_dir / ".nojekyll").write_text("", encoding="utf-8")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the static staples site.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT,
                        help="output directory (default: dist/)")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR,
                        help="directory containing staples.yaml and stores.yaml (default: data/)")
    args = parser.parse_args(argv)

    try:
        payload = build(args.out, args.data_dir)
    except ValidationError as e:
        print(e, file=sys.stderr)
        return 1
    print(f"Built {len(payload['staples'])} staples into {args.out}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
