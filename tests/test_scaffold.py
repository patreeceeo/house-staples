from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_data_files_exist():
    assert (ROOT / "data" / "staples.yaml").is_file()
    assert (ROOT / "data" / "stores.yaml").is_file()


def test_root_copies_removed():
    assert not (ROOT / "staples.yaml").exists()
    assert not (ROOT / "stores.yaml").exists()
