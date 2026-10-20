"""Agrofit/MAPA product catalog integration.

The official Agrofit open dataset is the safest path to a broad product base.
This service keeps a local CSV cache and exposes lightweight search helpers
without embedding product labels or doses in source code.
"""

from __future__ import annotations

import csv
import json
import time
import unicodedata
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Dict, List, Optional

import requests
from loguru import logger

from app.core.config import settings


@dataclass
class AgrofitResource:
    name: str
    url: str
    last_modified: Optional[str] = None


class AgrofitService:
    """Sync and query MAPA Agrofit product data."""

    def __init__(self):
        self.cache_dir = Path(settings.AGROFIT_CACHE_PATH)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.csv_path = self.cache_dir / "agrofit_produtos_formulados.csv"
        self.meta_path = self.cache_dir / "agrofit_meta.json"
        self._products_cache: Optional[List[Dict]] = None

    def sync_products(self, force: bool = False) -> Dict:
        """Download the current Produto Formulado CSV from MAPA CKAN."""
        if not force and not self._is_cache_stale() and self.csv_path.exists():
            products = self.load_products(refresh=False)
            return {
                "status": "cached",
                "message": "Cache Agrofit ainda valido",
                "record_count": len(products),
                "metadata": self._read_metadata(),
            }

        resource = self._discover_formulated_product_resource()
        response = requests.get(resource.url, timeout=60)
        response.raise_for_status()
        self.csv_path.write_bytes(response.content)
        self._products_cache = None

        products = self.load_products(refresh=True)
        metadata = {
            "source": "MAPA Agrofit",
            "dataset_api": settings.AGROFIT_CKAN_API_URL,
            "package_id": settings.AGROFIT_CKAN_PACKAGE_ID,
            "resource_name": resource.name,
            "resource_url": resource.url,
            "resource_last_modified": resource.last_modified,
            "synced_at": time.time(),
            "record_count": len(products),
        }
        self.meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

        return {
            "status": "success",
            "message": "Base Agrofit sincronizada",
            "record_count": len(products),
            "metadata": metadata,
        }

    def load_products(self, refresh: bool = False) -> List[Dict]:
        """Load normalized products from the local CSV cache."""
        if self._products_cache is not None and not refresh:
            return self._products_cache

        if not self.csv_path.exists():
            try:
                self.sync_products(force=True)
            except Exception as exc:
                logger.warning(f"Nao foi possivel sincronizar Agrofit automaticamente: {exc}")
                self._products_cache = []
                return self._products_cache

        content = self.csv_path.read_bytes()
        text = self._decode_csv(content)
        dialect = self._sniff_dialect(text)
        reader = csv.DictReader(StringIO(text), dialect=dialect)
        products = [self._normalize_record(row) for row in reader if row]
        products = [item for item in products if item.get("product_name") or item.get("raw")]
        self._products_cache = products
        return products

    def search_products(
        self,
        crop_type: Optional[str] = None,
        active_ingredient: Optional[str] = None,
        product_name: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 50,
        refresh: bool = False,
    ) -> Dict:
        """Search the cached official product catalog with tolerant matching."""
        products = self.load_products(refresh=refresh)
        normalized_filters = {
            "crop_type": self._normalize_text(crop_type),
            "active_ingredient": self._normalize_text(active_ingredient),
            "product_name": self._normalize_text(product_name),
            "category": self._normalize_text(category),
        }

        ranked = []
        for product in products:
            score = self._score_product(product, normalized_filters)
            if score > 0 or not any(normalized_filters.values()):
                ranked.append((score, product))

        ranked.sort(key=lambda item: item[0], reverse=True)
        limited = [item for _, item in ranked[: max(1, min(int(limit or 50), 500))]]
        return {
            "status": "success",
            "source": "MAPA Agrofit",
            "record_count": len(products),
            "returned": len(limited),
            "filters": {key: value for key, value in normalized_filters.items() if value},
            "metadata": self._read_metadata(),
            "products": limited,
            "notice": "Use Agrofit para disponibilidade/registro. Dose e uso devem seguir bula/rotulo vigente.",
        }

    def _discover_formulated_product_resource(self) -> AgrofitResource:
        response = requests.get(
            settings.AGROFIT_CKAN_API_URL,
            params={"id": settings.AGROFIT_CKAN_PACKAGE_ID},
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        if not payload.get("success"):
            raise RuntimeError("CKAN nao retornou sucesso para o pacote Agrofit")

        resources = payload.get("result", {}).get("resources", [])
        csv_resources = [
            resource for resource in resources
            if "csv" in str(resource.get("format", "")).lower()
        ]
        preferred = [
            resource for resource in csv_resources
            if "formulado" in self._normalize_text(resource.get("name"))
        ]
        selected = (preferred or csv_resources or [None])[0]
        if not selected or not selected.get("url"):
            raise RuntimeError("Recurso CSV de Produto Formulado nao encontrado no Agrofit")

        return AgrofitResource(
            name=str(selected.get("name") or "Produto Formulado"),
            url=str(selected["url"]),
            last_modified=selected.get("last_modified") or selected.get("metadata_modified"),
        )

    def _score_product(self, product: Dict, filters: Dict[str, str]) -> int:
        score = 0
        fields = {
            "product_name": product.get("product_name_normalized", ""),
            "active_ingredient": product.get("active_ingredient_normalized", ""),
            "crop_type": product.get("crop_normalized", ""),
            "category": product.get("category_normalized", ""),
        }
        for key, needle in filters.items():
            if not needle:
                continue
            haystack = fields.get(key, "")
            if not haystack:
                # Missing crop/category data cannot satisfy an explicit filter.
                return 0
            if needle in haystack:
                score += 4 if key in {"product_name", "active_ingredient"} else 2
            else:
                return 0
        return score or 1

    def _normalize_record(self, row: Dict) -> Dict:
        clean = {str(key or "").strip(): str(value or "").strip() for key, value in row.items()}
        product_name = self._first_matching(clean, ["marca", "produto comercial", "produto"])
        active_ingredient = self._first_matching(clean, ["ingrediente", "ativo", "composicao"])
        registration = self._first_matching(clean, ["registro"])
        category = self._first_matching(clean, ["classe", "tipo", "categoria"])
        company = self._first_matching(clean, ["titular", "empresa", "registrante"])
        crop = self._first_matching(clean, ["cultura"])

        return {
            "product_name": product_name,
            "active_ingredient": active_ingredient,
            "registration": registration,
            "category": category,
            "company": company,
            "crop": crop,
            "product_name_normalized": self._normalize_text(product_name),
            "active_ingredient_normalized": self._normalize_text(active_ingredient),
            "category_normalized": self._normalize_text(category),
            "crop_normalized": self._normalize_text(crop),
            "raw": clean,
        }

    def _first_matching(self, row: Dict[str, str], terms: List[str]) -> Optional[str]:
        for key, value in row.items():
            normalized_key = self._normalize_text(key)
            if value and any(term in normalized_key for term in terms):
                return value
        return None

    def _is_cache_stale(self) -> bool:
        metadata = self._read_metadata()
        synced_at = float(metadata.get("synced_at") or 0)
        max_age_seconds = max(1, int(settings.AGROFIT_REFRESH_HOURS)) * 3600
        return (time.time() - synced_at) > max_age_seconds

    def _read_metadata(self) -> Dict:
        if not self.meta_path.exists():
            return {}
        try:
            return json.loads(self.meta_path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    @staticmethod
    def _decode_csv(content: bytes) -> str:
        for encoding in ("utf-8-sig", "utf-8", "latin-1"):
            try:
                return content.decode(encoding)
            except UnicodeDecodeError:
                continue
        return content.decode("utf-8", errors="replace")

    @staticmethod
    def _sniff_dialect(text: str):
        sample = text[:4096]
        try:
            return csv.Sniffer().sniff(sample, delimiters=",;|\t")
        except csv.Error:
            return csv.excel

    @staticmethod
    def _normalize_text(value: Optional[str]) -> str:
        if value is None:
            return ""
        normalized = unicodedata.normalize("NFKD", str(value).strip().lower())
        return "".join(char for char in normalized if not unicodedata.combining(char))


agrofit_service = AgrofitService()
