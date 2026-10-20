"""Update the offline catalogue from its canonical, reviewed source.

Run after editing app/data/crops.json and before packaging Android/PWA assets.
"""
from pathlib import Path
import json


def main():
    root = Path(__file__).resolve().parents[1]
    source = root / "app" / "data" / "crops.json"
    content = source.read_bytes()
    data = json.loads(content.decode("utf-8-sig"))
    if data.get("schema_version") != 1 or not data.get("crops"):
        raise ValueError("Catálogo offline inválido")
    (root / "app" / "static" / "crops.json").write_bytes(content)
    print(f"Catálogo offline atualizado: {len(data['crops'])} culturas")


if __name__ == "__main__":
    main()
