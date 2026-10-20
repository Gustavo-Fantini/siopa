"""Offline crop identities and deliberately unvalidated deposition profiles.

Crop recognition never implies pesticide, dose or spraying appropriateness.
Generic stages are navigation labels, not a validated crop phenology model.
"""

import json
import unicodedata
from copy import deepcopy
from pathlib import Path


def normalize_crop_name(value):
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii")
    return " ".join(text.lower().replace("_", " ").replace("-", " ").split())


class CropCatalog:
    def __init__(self, path=None):
        self.path = Path(path or Path(__file__).resolve().parents[1] / "data" / "crops.json")
        self._data = None
        self._lookup = {}

    def _load(self):
        if self._data is None:
            data = json.loads(self.path.read_text(encoding="utf-8-sig"))
            keys = set()
            for crop in data["crops"]:
                if crop["key"] in keys:
                    raise ValueError("Chave de cultura duplicada")
                keys.add(crop["key"])
                for name in [crop["key"], crop["name"], crop["scientific_name"]] + crop["aliases"]:
                    normalized = normalize_crop_name(name)
                    if normalized in self._lookup and self._lookup[normalized]["key"] != crop["key"]:
                        raise ValueError("Alias de cultura ambíguo: " + name)
                    self._lookup[normalized] = crop
            self._data = data
        return self._data

    def list_crops(self):
        return deepcopy(self._load()["crops"])

    def get_crop(self, value):
        self._load()
        crop = self._lookup.get(normalize_crop_name(value))
        return deepcopy(crop) if crop else None

    def quality_profile(self, crop, stage=None):
        record = crop if isinstance(crop, dict) else self.get_crop(crop)
        profile = deepcopy(self._load()["quality_profiles"]["unvalidated"])
        profile["culture"] = record["name"] if record else str(crop or "Cultura não identificada")
        profile["growth_stage"] = stage
        return profile

    def metadata(self):
        data = self._load()
        return {key: deepcopy(data[key]) for key in ("schema_version", "updated_at", "sources", "stage_profiles", "quality_profiles")}


crop_catalog = CropCatalog()
