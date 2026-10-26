"""CLI: validate the data files. Usage: uv run python -m staples_site.validate [--data-dir DIR]"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from staples_site.data import DEFAULT_DATA_DIR, ValidationError, load_data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate staples.yaml and stores.yaml.")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR,
                        help="directory containing staples.yaml and stores.yaml (default: data/)")
    args = parser.parse_args(argv)

    try:
        data = load_data(args.data_dir)
    except ValidationError as e:
        print(e, file=sys.stderr)
        return 1

    with_stores = sum(1 for s in data.staples if s.stores)
    print(f"OK: {len(data.staples)} staples ({with_stores} with stores), "
          f"{len(data.stores)} stores")
    return 0


if __name__ == "__main__":
    sys.exit(main())
