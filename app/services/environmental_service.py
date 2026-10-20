"""Regional environmental context with explicit provenance, age and missing data.

No calls, files or remote polygons are created on import. Geographic coordinates
select a model pixel, not a surveyed parcel or a laboratory soil sample.
"""

import asyncio
import math
import time
from collections import deque
from copy import deepcopy
from urllib.parse import urlsplit, urlunsplit

import aiohttp

from app.core.config import settings
from app.services.weather_service import SnapshotCache, validate_coordinates, weather_service


class EnvironmentalService:
    def __init__(self, cache_dir=None, weather=None):
        self.cache = SnapshotCache(cache_dir)
        self.weather = weather or weather_service
        self.request_timeout = 8
        self._soil_calls = deque()
        self._soil_gate = asyncio.Lock()

    @staticmethod
    def _soil_provenance():
        return {"provider": "ISRIC SoilGrids", "url": "https://rest.isric.org/soilgrids/v2.0/docs",
                "license": "CC BY 4.0", "resolution": "250 m; intervalos 0–5 e 5–15 cm",
                "reference_period": "SoilGrids 2.0; observações de várias datas, sem ano único",
                "data_kind": "spatial_prediction", "observed_at": None,
                "limitations": ["Predição regional com incerteza; não substitui amostragem e análise laboratorial.",
                                "Não informa umidade atual, classe de solo brasileira nem fertilidade do talhão."]}

    @staticmethod
    def _terrain_provenance():
        return {"provider": "Open-Meteo / Copernicus DEM", "url": "https://open-meteo.com/en/docs/elevation-api",
                "license": "CC BY 4.0 / Copernicus DEM GLO-90 license; atribuir Open-Meteo e Copernicus",
                "resolution": "90 m (GLO-90)", "reference_period": "Copernicus DEM, edição 2021",
                "data_kind": "digital_surface_model", "observed_at": None,
                "limitations": ["Elevação de modelo de superfície; não é levantamento topográfico ou altitude GNSS.",
                                "Um ponto não define declividade, drenagem ou microrelevo do talhão."]}

    async def _request_json(self, url, params):
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.request_timeout)) as session:
            async with session.get(url, params=params) as response:
                response.raise_for_status()
                return await response.json()

    async def _fetch_soil(self, latitude, longitude):
        # ISRIC explicitly asks for at most five calls per minute. Do not queue a
        # long sleep in an interactive analysis; expose missing data instead.
        async with self._soil_gate:
            now = time.monotonic()
            while self._soil_calls and self._soil_calls[0] <= now - 60:
                self._soil_calls.popleft()
            if len(self._soil_calls) >= 5:
                raise RuntimeError("Orçamento local SoilGrids por minuto atingido")
            self._soil_calls.append(now)
        params = [("lat", latitude), ("lon", longitude)]
        params.extend(("property", name) for name in ("phh2o", "soc", "clay", "sand", "silt"))
        params.extend(("depth", depth) for depth in ("0-5cm", "5-15cm"))
        params.extend(("value", statistic) for statistic in ("mean", "Q0.05", "Q0.95"))
        payload = await self._request_json(settings.SOILGRIDS_API_URL, params)
        return self._normalize_soil(payload)

    def _normalize_soil(self, payload):
        # Official mapped-unit conversion factors; no silent unit inference.
        definitions = {"phh2o": ("pH em água", "pH", 10), "soc": ("Carbono orgânico", "g/kg", 10),
                       "clay": ("Argila", "%", 10), "sand": ("Areia", "%", 10), "silt": ("Silte", "%", 10)}
        properties = {}
        for layer in payload.get("properties", {}).get("layers", []):
            name = layer.get("name")
            if name not in definitions:
                continue
            label, unit, factor = definitions[name]
            depths = {}
            for depth in layer.get("depths", []):
                if depth.get("label") not in {"0-5cm", "5-15cm"}:
                    continue
                values = depth.get("values") or {}
                converted = {}
                for source, target in (("mean", "mean"), ("Q0.05", "q05"), ("Q0.95", "q95")):
                    value = values.get(source)
                    converted[target] = round(float(value) / factor, 3) if isinstance(value, (float, int)) and math.isfinite(value) and value >= 0 else None
                if any(value is not None for value in converted.values()):
                    depths[depth["label"]] = converted
            if depths:
                properties[name] = {"label": label, "unit": unit, "depths": depths}
        if not properties:
            raise ValueError("SoilGrids não retornou propriedades válidas")
        provenance = self._soil_provenance()
        return {"availability": "available" if len(properties) == len(definitions) else "partial", "properties": properties,
                "source": "isric_soilgrids", "resolution": provenance["resolution"], "observed_at": None,
                "reference_period": provenance["reference_period"], "provenance": [provenance],
                "limitations": provenance["limitations"], "soil_type": None, "moisture_status": "desconhecida",
                "ph": properties.get("phh2o", {}).get("depths", {}).get("0-5cm", {}).get("mean")}

    async def get_soil(self, latitude, longitude, force_refresh=False):
        validate_coordinates(latitude, longitude)
        provenance = self._soil_provenance()
        unavailable = {"availability": "unavailable", "properties": {}, "source": None,
                       "resolution": provenance["resolution"], "observed_at": None, "soil_type": None,
                       "ph": None, "moisture_status": "desconhecida", "provenance": [provenance],
                       "limitations": provenance["limitations"],
                       "reason": "SoilGrids indisponível, sem cobertura ou sem propriedade válida; nenhum solo foi inferido."}
        return await self.cache.resolve(f"soil-v1:{latitude:.6f}:{longitude:.6f}",
                                        lambda: self._fetch_soil(latitude, longitude), 30 * 86400,
                                        unavailable, force_refresh, negative_ttl=600)

    async def _fetch_terrain(self, latitude, longitude):
        parsed = urlsplit(settings.OPEN_METEO_API_URL)
        url = urlunsplit((parsed.scheme, parsed.netloc, "/v1/elevation", "", ""))
        params = {"latitude": latitude, "longitude": longitude}
        if settings.OPEN_METEO_API_KEY:
            params["apikey"] = settings.OPEN_METEO_API_KEY
            if url.startswith("https://api.open-meteo.com/"):
                url = url.replace("https://api.open-meteo.com/", "https://customer-api.open-meteo.com/", 1)
        payload = await self._request_json(url, params)
        values = payload.get("elevation") or []
        value = values[0] if values else None
        if not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError("Elevação indisponível")
        provenance = self._terrain_provenance()
        return {"availability": "available", "elevation_m": value, "slope_degrees": None,
                "source": "open_meteo_copernicus_glo90", "resolution": provenance["resolution"],
                "observed_at": None, "reference_period": provenance["reference_period"],
                "provenance": [provenance], "limitations": provenance["limitations"]}

    async def get_terrain(self, latitude, longitude, force_refresh=False):
        validate_coordinates(latitude, longitude)
        provenance = self._terrain_provenance()
        unavailable = {"availability": "unavailable", "elevation_m": None, "slope_degrees": None, "source": None,
                       "resolution": provenance["resolution"], "observed_at": None, "provenance": [provenance],
                       "limitations": provenance["limitations"], "reason": "Modelo de elevação indisponível."}
        return await self.cache.resolve(f"terrain-v1:{latitude:.6f}:{longitude:.6f}",
                                        lambda: self._fetch_terrain(latitude, longitude), 30 * 86400,
                                        unavailable, force_refresh, negative_ttl=600)

    async def get_context(self, latitude, longitude, force_refresh=False):
        validate_coordinates(latitude, longitude)
        weather, soil, terrain = await asyncio.gather(self.weather.get_weather_bundle(latitude, longitude, force_refresh),
                                                     self.get_soil(latitude, longitude, force_refresh),
                                                     self.get_terrain(latitude, longitude, force_refresh))
        weather = deepcopy(weather)
        for row in [weather.get("current", {})] + weather.get("hourly", []) + weather.get("forecast", []):
            row.update(stale=weather["stale"], fetched_at=weather["fetched_at"], expires_at=weather["expires_at"])
            if weather["stale"]:
                row["spray_conditions"] = self.weather._unknown_conditions("Snapshot expirado; confirme condições atuais em campo.")
        components = (weather, soil, terrain)
        statuses = [component["availability"] for component in components]
        return {"weather": weather, "soil": soil, "terrain": terrain,
                "coordinates": {"latitude": latitude, "longitude": longitude, "crs": "EPSG:4326"},
                "availability": "available" if all(value == "available" for value in statuses) else "unavailable" if all(value == "unavailable" for value in statuses) else "partial",
                "provenance": [entry for component in components for entry in component.get("provenance", [])],
                "fetched_at": min(component["fetched_at"] for component in components),
                "expires_at": min(component["expires_at"] for component in components),
                "stale": any(component["stale"] for component in components),
                "limitations": ["Coordenadas selecionam grades regionais; nenhum campo representa medição exata do terreno."]}


environmental_service = EnvironmentalService()
