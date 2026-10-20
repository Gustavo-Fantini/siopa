import json
from pathlib import Path


def test_bundled_catalogue_matches_canonical_source():
    root = Path(__file__).resolve().parents[1]
    source = root / "app" / "data" / "crops.json"
    assert source.read_bytes() == (root / "app" / "static" / "crops.json").read_bytes()
    data = json.loads(source.read_text(encoding="utf-8-sig"))
    assert len(data["crops"]) >= 100
    assert all(crop["sampling_guidance"] for crop in data["crops"])
