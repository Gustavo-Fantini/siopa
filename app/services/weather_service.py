"""
Weather integration service.

This version consolidates multiple providers with:
- concurrent requests
- retry/backoff
- normalized location metadata
- optional Agromonitoring support
- daily forecast aggregation for sources that return 3h steps
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import time
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import aiohttp
from loguru import logger

from app.core.config import settings
from app.core.exceptions import APIConnectionError
from app.utils.logger import log_api_call


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_coordinates(latitude: float, longitude: float) -> None:
    if not math.isfinite(latitude) or not math.isfinite(longitude) or not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise ValueError("Latitude/longitude fora dos limites WGS84.")


class SnapshotCache:
    """Lazy, atomic JSON snapshots; expired successes survive provider failures.

    Timestamps describe collection time, never the observation/model reference time.
    Failure backoff is persisted so an offline client does not hammer providers.
    """

    def __init__(self, cache_dir=None):
        self.cache_dir = Path(cache_dir or settings.ENVIRONMENT_CACHE_PATH)
        self._locks = {}

    def _path(self, key):
        return self.cache_dir / (hashlib.sha256(key.encode("utf-8")).hexdigest() + ".json")

    def read(self, key):
        try:
            envelope = json.loads(self._path(key).read_text(encoding="utf-8"))
            if envelope.get("version") != 1 or envelope.get("key") != key or not isinstance(envelope.get("value"), dict):
                return None
            envelope["expires_epoch"] = float(envelope["expires_epoch"])
            if not math.isfinite(envelope["expires_epoch"]) or not all(isinstance(envelope.get(name), str) for name in ("fetched_at", "expires_at")):
                return None
            envelope["retry_after_epoch"] = float(envelope.get("retry_after_epoch", 0))
            if not math.isfinite(envelope["retry_after_epoch"]):
                return None
            return envelope
        except (OSError, ValueError, TypeError, KeyError):
            return None

    def _write(self, key, envelope):
        temporary = None
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            temporary = self._path(key).with_suffix("." + uuid.uuid4().hex + ".tmp")
            temporary.write_text(json.dumps(envelope, ensure_ascii=False, allow_nan=False), encoding="utf-8")
            temporary.replace(self._path(key))
        except (OSError, ValueError, TypeError):
            logger.warning("Snapshot ambiental não pôde ser persistido; resposta atual preservada.")
        finally:
            if temporary and temporary.exists():
                try:
                    temporary.unlink()
                except OSError:
                    pass

    @staticmethod
    def _decorate(envelope, cached):
        value = deepcopy(envelope["value"])
        value.update(fetched_at=envelope["fetched_at"], expires_at=envelope["expires_at"],
                     stale=time.time() >= envelope["expires_epoch"], cached=cached)
        if envelope.get("refresh_failed"):
            value["refresh_failed"] = True
            value["refresh_error"] = "Atualização indisponível; exibindo snapshot anterior com data e validade preservadas."
        return value

    async def resolve(self, key, fetcher, ttl_seconds, unavailable, force_refresh=False, negative_ttl=300):
        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:
            now = time.time()
            old = self.read(key)
            if not force_refresh and old and max(old["expires_epoch"], old.get("retry_after_epoch", 0)) > now:
                return self._decorate(old, True)
            try:
                value = await fetcher()
                if not isinstance(value, dict) or value.get("availability") not in {"available", "partial"}:
                    raise ValueError("Resposta ambiental sem dados utilizáveis.")
                duration = ttl_seconds
            except Exception as exc:
                logger.info("Consulta ambiental indisponível ({})", type(exc).__name__)
                if old and old["value"].get("availability") in {"available", "partial"}:
                    old.update(retry_after_epoch=now + negative_ttl, refresh_failed=True)
                    self._write(key, old)
                    return self._decorate(old, True)
                value = deepcopy(unavailable)
                duration = negative_ttl
            envelope = {"version": 1, "key": key, "value": value, "fetched_at": utc_now(),
                        "expires_at": datetime.fromtimestamp(now + duration, timezone.utc).isoformat(),
                        "expires_epoch": now + duration}
            self._write(key, envelope)
            return self._decorate(envelope, False)


class WeatherService:
    """Fetch and consolidate weather data from the configured APIs."""

    def __init__(self):
        self.request_timeout = 8
        self.request_retries = 0
        self.cache = SnapshotCache()
        self.source_priority = ["weatherapi", "openweather", "agromonitoring", "climatempo"]
        self.apis = {
            "openweather": {
                "base_url": "https://api.openweathermap.org/data/2.5",
                "key": settings.OPENWEATHER_API_KEY,
                "enabled": bool(settings.OPENWEATHER_API_KEY),
            },
            "weatherapi": {
                "base_url": "https://api.weatherapi.com/v1",
                "key": settings.WEATHERAPI_KEY,
                "enabled": bool(settings.WEATHERAPI_KEY),
            },
            "climatempo": {
                "base_url": "http://apiadvisor.climatempo.com.br/api/v1",
                "key": settings.CLIMATEMPO_TOKEN,
                "enabled": bool(settings.CLIMATEMPO_TOKEN),
            },
            "agromonitoring": {
                "base_url": "https://api.agromonitoring.com/agro/1.0",
                "key": settings.AGRO_API_TOKEN,
                "enabled": bool(settings.AGRO_API_TOKEN),
            },
        }

        self.ideal_conditions = {
            "temperature": {"min": 15, "max": 30},
            "humidity": {"min": 50, "max": 90},
            "wind_speed": {"min": 3, "max": 15},
            "precipitation": 0.2,
        }

    async def get_current_weather(self, latitude: float, longitude: float) -> Dict:
        """Open-Meteo first, configured legacy providers second, stale snapshot last."""
        bundle = await self.get_weather_bundle(latitude, longitude)
        current = deepcopy(bundle["current"])
        for key in ("fetched_at", "expires_at", "stale", "cached", "refresh_failed", "refresh_error"):
            if key in bundle:
                current[key] = bundle[key]
        if current.get("stale"):
            current["spray_conditions"] = self._unknown_conditions("Snapshot meteorológico expirado; confirme as condições atuais em campo.")
        return current

    @staticmethod
    def _unavailable_current(latitude, longitude):
        return {"availability": "unavailable", "temperature": None, "humidity": None,
                "wind_speed": None, "wind_direction": None, "pressure": None, "precipitation": None,
                "weather_condition": None, "source": None, "sources": [], "timestamp": None,
                "location": {"lat": latitude, "lon": longitude},
                "reason": "Nenhuma fonte meteorológica respondeu com dados válidos.",
                "spray_conditions": WeatherService._unknown_conditions("Clima indisponível; não é possível avaliar janela de aplicação.")}

    @staticmethod
    def _unknown_conditions(reason):
        return {"overall_rating": "unknown", "score": None, "temperature_ok": None,
                "humidity_ok": None, "wind_ok": None, "precipitation_ok": None,
                "summary": reason, "recommendations": [reason], "risk_factors": [],
                "assessment_type": "screening_only"}

    async def get_weather_bundle(self, latitude, longitude, force_refresh=False):
        validate_coordinates(latitude, longitude)
        key = f"weather-v3:{latitude:.6f}:{longitude:.6f}"
        unavailable = {"availability": "unavailable", "current": self._unavailable_current(latitude, longitude),
                       "forecast": [], "hourly": [], "source": None, "provenance": []}

        async def fetch_bundle():
            try:
                async with aiohttp.ClientSession() as session:
                    return await self._get_open_meteo_bundle(session, latitude, longitude)
            except Exception:
                # No averaging with the primary model: retain explicit fallback provenance.
                results = await asyncio.gather(self._get_weather_from_apis(latitude, longitude),
                                               self._get_forecast_from_apis(latitude, longitude, 7), return_exceptions=True)
                current = results[0] if isinstance(results[0], dict) else self._unavailable_current(latitude, longitude)
                forecast = results[1] if isinstance(results[1], list) else []
                if current.get("availability") == "unavailable" and not forecast:
                    raise APIConnectionError("Nenhuma fonte meteorológica disponível")
                current.setdefault("availability", "available")
                current["data_kind"] = "external_provider"
                providers = list(dict.fromkeys(current.get("sources", []) + [row.get("source") for row in forecast if row.get("source")]))
                provenance = [{"provider": name, "url": self.apis[name]["base_url"],
                               "license": "Conforme contrato do provedor configurado", "resolution": "Não informada pela resposta normalizada",
                               "reference_period": current.get("timestamp"), "data_kind": "external_provider"}
                              for name in providers if name in self.apis]
                return {"availability": "available" if forecast and current.get("availability") == "available" else "partial",
                        "current": current, "forecast": forecast, "hourly": [],
                        "source": current.get("source"), "provenance": provenance}

        bundle = await self.cache.resolve(key, fetch_bundle, max(60, int(settings.ENVIRONMENT_CACHE_TTL_SECONDS)), unavailable, force_refresh)
        current = bundle["current"]
        try:
            reference = datetime.fromisoformat(str(current.get("timestamp") or "").replace("Z", "+00:00"))
            if reference.tzinfo is None:
                raise ValueError("Reference timezone missing")
            age = max(0, (datetime.now(timezone.utc) - reference).total_seconds())
            current["observation_age_seconds"] = round(age)
            current["reference_time_known"] = True
            current["data_stale"] = age > max(3600, int(settings.ENVIRONMENT_CACHE_TTL_SECONDS) * 2)
        except (TypeError, ValueError, KeyError):
            current.update(observation_age_seconds=None, reference_time_known=False,
                           data_stale=current.get("availability") != "unavailable")
        bundle["stale"] = bundle["stale"] or current["data_stale"]
        return bundle

    async def _get_open_meteo_bundle(self, session, latitude, longitude):
        fields = "temperature_2m,relative_humidity_2m,precipitation,weather_code,cloud_cover,surface_pressure,wind_speed_10m,wind_direction_10m,wind_gusts_10m"
        params = {
            "latitude": latitude, "longitude": longitude, "current": fields,
            "hourly": fields + ",precipitation_probability", "forecast_days": 7,
            "timezone": "UTC", "wind_speed_unit": "kmh", "temperature_unit": "celsius", "precipitation_unit": "mm"}
        url = settings.OPEN_METEO_API_URL
        if settings.OPEN_METEO_API_KEY:
            params["apikey"] = settings.OPEN_METEO_API_KEY
            if url.startswith("https://api.open-meteo.com/"):
                url = url.replace("https://api.open-meteo.com/", "https://customer-api.open-meteo.com/", 1)
        payload = await self._request_json(session, "Open-Meteo", url, params=params)
        raw = payload.get("current") or {}
        if not raw.get("time") or any(self._number(raw.get(field)) is None for field in ("temperature_2m", "relative_humidity_2m", "wind_speed_10m", "precipitation")):
            raise APIConnectionError("Open-Meteo sem condições atuais completas")
        provenance = {"provider": "Open-Meteo", "url": "https://open-meteo.com/en/docs", "license": "CC BY 4.0; endpoint gratuito para uso não comercial",
                      "resolution": "Grade de modelo variável por região/modelo; vento a 10 m, temperatura/UR a 2 m",
                      "reference_period": raw["time"] + "Z", "data_kind": "weather_model",
                      "limitations": ["Estimativa de modelo; não é estação nem sensor no talhão.", "Confirmar vento e rajadas na altura de aplicação."]}

        def normalize(row, interval=3600):
            result = {"temperature": self._number(row.get("temperature_2m")), "humidity": self._number(row.get("relative_humidity_2m")),
                      "wind_speed": self._number(row.get("wind_speed_10m")), "wind_direction": self._number(row.get("wind_direction_10m")),
                      "wind_gusts": self._number(row.get("wind_gusts_10m")), "pressure": self._number(row.get("surface_pressure")),
                      "precipitation": self._number(row.get("precipitation")), "precipitation_probability": self._number(row.get("precipitation_probability")),
                      "weather_code": row.get("weather_code"), "weather_condition": self._weather_code_text(row.get("weather_code")),
                      "cloudiness": row.get("cloud_cover"), "timestamp": row.get("time", "") + "Z",
                      "precipitation_interval_seconds": interval, "source": "open_meteo", "sources": ["open_meteo"],
                      "data_kind": "weather_model", "availability": "available", "provenance": provenance,
                      "location": {"lat": latitude, "lon": longitude, "grid_latitude": payload.get("latitude"),
                                   "grid_longitude": payload.get("longitude"), "timezone": "UTC"}}
            result["spray_conditions"] = self._analyze_spray_conditions(result)
            return result

        current = normalize(raw, raw.get("interval", 900))
        hourly_raw = payload.get("hourly") or {}
        hourly = [normalize({name: values[index] if index < len(values) else None for name, values in hourly_raw.items() if isinstance(values, list)})
                  for index in range(len(hourly_raw.get("time", [])))]
        grouped = {}
        for row in hourly:
            grouped.setdefault(row["timestamp"][:10], []).append(row)
        forecast = []
        for day, rows in sorted(grouped.items()):
            def values(name):
                return [float(row[name]) for row in rows if row.get(name) is not None]
            temps, humidities, winds, rain = (values(name) for name in ("temperature", "humidity", "wind_speed", "precipitation"))
            if not temps:
                continue
            forecast.append({"date": day, "temperature": round(sum(temps) / len(temps), 2), "temperature_min": min(temps),
                             "temperature_max": max(temps), "humidity": round(sum(humidities) / len(humidities), 2) if humidities else None,
                             "wind_speed": max(winds) if winds else None, "precipitation": round(sum(rain), 2) if rain else None,
                             "source": "open_meteo", "availability": "available", "data_kind": "weather_model",
                             "spray_conditions": self._unknown_conditions("Resumo diário; use a previsão horária para avaliar janelas.")})
        return {"availability": "available" if forecast else "partial", "current": current, "forecast": forecast,
                "hourly": hourly, "source": "open_meteo", "provenance": [provenance]}

    @staticmethod
    def _weather_code_text(code):
        if code == 0:
            return "Céu limpo"
        if code in {1, 2, 3}:
            return "Parcialmente nublado ou nublado"
        if code in {45, 48}:
            return "Nevoeiro"
        if code in {95, 96, 99}:
            return "Trovoada"
        if code is not None:
            return "Precipitação ou condição WMO " + str(code)
        return None

    @staticmethod
    def _number(value, multiplier=1.0):
        try:
            result = float(value) * multiplier
            return result if math.isfinite(result) else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _observation_time(epoch):
        try:
            return datetime.fromtimestamp(int(epoch), timezone.utc).isoformat()
        except (TypeError, ValueError, OverflowError, OSError):
            return None

    async def _get_weather_from_apis(self, latitude: float, longitude: float) -> Dict:
        """Fetch current weather concurrently from all enabled providers."""
        logger.info(f"Obtendo dados meteorologicos para {latitude}, {longitude}")

        async with aiohttp.ClientSession() as session:
            tasks = {}
            if self.apis["weatherapi"]["enabled"]:
                tasks["weatherapi"] = self._get_weatherapi_data(session, latitude, longitude)
            if self.apis["openweather"]["enabled"]:
                tasks["openweather"] = self._get_openweather_data(session, latitude, longitude)
            if self.apis["agromonitoring"]["enabled"]:
                tasks["agromonitoring"] = self._get_agromonitoring_current_weather(session, latitude, longitude)
            if self.apis["climatempo"]["enabled"]:
                tasks["climatempo"] = self._get_climatempo_data(session, latitude, longitude)

            if not tasks:
                raise APIConnectionError("Nenhuma API meteorologica configurada")

            results = await asyncio.gather(*tasks.values(), return_exceptions=True)

        normalized: Dict[str, Dict] = {}
        for source_name, result in zip(tasks.keys(), results):
            if isinstance(result, Exception):
                logger.warning(f"Fonte meteorologica {source_name} falhou: {result}")
                continue
            if result:
                normalized[source_name] = result

        if not normalized:
            raise APIConnectionError("Nenhum dado meteorologico disponivel")

        consolidated = self._consolidate_weather_data(normalized)
        consolidated["spray_conditions"] = self._analyze_spray_conditions(consolidated)
        logger.info("Dados meteorologicos consolidados com sucesso")
        return consolidated

    async def _request_json(
        self,
        session: aiohttp.ClientSession,
        source_name: str,
        url: str,
        *,
        params: Optional[Dict] = None,
        method: str = "GET",
        json_body: Optional[Dict] = None,
        expected_statuses: Optional[set] = None,
    ) -> Dict:
        """Perform one JSON HTTP request with retry/backoff."""
        expected = expected_statuses or {200}
        last_error: Optional[Exception] = None

        for attempt in range(self.request_retries + 1):
            try:
                async with session.request(
                    method,
                    url,
                    params=params,
                    json=json_body,
                    timeout=aiohttp.ClientTimeout(total=self.request_timeout),
                ) as response:
                    log_api_call(source_name, url, response.status)
                    if response.status not in expected:
                        response_text = await response.text()
                        raise APIConnectionError(
                            f"{source_name} retornou status {response.status}: {response_text[:200]}"
                        )
                    return await response.json()
            except Exception as exc:
                last_error = exc
                if attempt >= self.request_retries:
                    break
                await asyncio.sleep(0.35 * (attempt + 1))

        raise APIConnectionError(f"Falha ao consultar {source_name}: {last_error}")

    async def _get_openweather_data(self, session: aiohttp.ClientSession, lat: float, lon: float) -> Dict:
        """Normalize current weather from OpenWeather."""
        data = await self._request_json(
            session,
            "OpenWeather",
            f"{self.apis['openweather']['base_url']}/weather",
            params={
                "lat": lat,
                "lon": lon,
                "appid": self.apis["openweather"]["key"],
                "units": "metric",
                "lang": "pt_br",
            },
        )

        return {
            "temperature": float(data["main"]["temp"]),
            "humidity": float(data["main"]["humidity"]),
            "pressure": float(data["main"]["pressure"]),
            "wind_speed": self._number(data.get("wind", {}).get("speed"), 3.6),
            "wind_direction": self._number(data.get("wind", {}).get("deg")),
            "precipitation": float(data.get("rain", {}).get("1h", 0.0) or data.get("snow", {}).get("1h", 0.0) or 0.0),
            "weather_condition": data.get("weather", [{}])[0].get("description", "indefinido"),
            "visibility": float(data.get("visibility", 0.0)) / 1000.0 if data.get("visibility") else None,
            "cloudiness": float(data.get("clouds", {}).get("all", 0.0)),
            "timestamp": self._observation_time(data.get("dt")),
            "source": "openweather",
            "location": {
                "name": data.get("name"),
                "region": None,
                "country": data.get("sys", {}).get("country"),
                "lat": data.get("coord", {}).get("lat", lat),
                "lon": data.get("coord", {}).get("lon", lon),
            },
        }

    async def _get_weatherapi_data(self, session: aiohttp.ClientSession, lat: float, lon: float) -> Dict:
        """Normalize current weather from WeatherAPI."""
        data = await self._request_json(
            session,
            "WeatherAPI",
            f"{self.apis['weatherapi']['base_url']}/current.json",
            params={
                "key": self.apis["weatherapi"]["key"],
                "q": f"{lat},{lon}",
                "lang": "pt",
                "aqi": "no",
            },
        )
        current = data["current"]
        location = data.get("location", {})

        return {
            "temperature": float(current["temp_c"]),
            "humidity": float(current["humidity"]),
            "pressure": float(current["pressure_mb"]),
            "wind_speed": float(current["wind_kph"]),
            "wind_direction": float(current["wind_degree"]),
            "precipitation": float(current.get("precip_mm", 0.0)),
            "weather_condition": current.get("condition", {}).get("text", "indefinido"),
            "visibility": float(current.get("vis_km", 0.0)),
            "uv_index": float(current.get("uv", 0.0)),
            "cloudiness": float(current.get("cloud", 0.0)),
            "timestamp": self._observation_time(current.get("last_updated_epoch")),
            "source": "weatherapi",
            "location": {
                "name": location.get("name"),
                "region": location.get("region"),
                "country": location.get("country"),
                "lat": location.get("lat", lat),
                "lon": location.get("lon", lon),
                "timezone": location.get("tz_id"),
            },
        }

    async def _get_agromonitoring_current_weather(
        self,
        session: aiohttp.ClientSession,
        lat: float,
        lon: float,
    ) -> Dict:
        """Normalize current weather from Agromonitoring."""
        data = await self._request_json(
            session,
            "Agromonitoring Weather",
            f"{self.apis['agromonitoring']['base_url']}/weather",
            params={
                "lat": lat,
                "lon": lon,
                "appid": self.apis["agromonitoring"]["key"],
                "units": "metric",
            },
        )

        temperature = self._normalize_temperature(data.get("main", {}).get("temp"))
        return {
            "temperature": temperature,
            "humidity": self._number(data.get("main", {}).get("humidity")),
            "pressure": self._number(data.get("main", {}).get("pressure")),
            "wind_speed": self._number(data.get("wind", {}).get("speed"), 3.6),
            "wind_direction": self._number(data.get("wind", {}).get("deg")),
            "precipitation": float(data.get("rain", {}).get("1h", 0.0) or data.get("rain", {}).get("3h", 0.0) or 0.0),
            "weather_condition": data.get("weather", [{}])[0].get("description", "indefinido"),
            "cloudiness": float(data.get("clouds", {}).get("all", 0.0)),
            "timestamp": self._observation_time(data.get("dt")),
            "source": "agromonitoring",
            "location": {
                "name": "Agromonitoring field point",
                "region": None,
                "country": "Brasil",
                "lat": lat,
                "lon": lon,
            },
        }

    async def _get_climatempo_data(self, session: aiohttp.ClientSession, lat: float, lon: float) -> Dict:
        """Best-effort support for the legacy Climatempo flow."""
        search = await self._request_json(
            session,
            "Climatempo search",
            f"{self.apis['climatempo']['base_url']}/locale/city",
            params={"name": f"{lat},{lon}", "token": self.apis["climatempo"]["key"]},
        )
        if not search:
            return {}

        city_id = search[0]["id"]
        data = await self._request_json(
            session,
            "Climatempo current",
            f"{self.apis['climatempo']['base_url']}/weather/locale/{city_id}/current",
            params={"token": self.apis["climatempo"]["key"]},
        )
        payload = data.get("data", {})
        return {
            "temperature": self._number(payload.get("temperature")),
            "humidity": self._number(payload.get("humidity")),
            "pressure": self._number(payload.get("pressure")),
            "wind_speed": self._number(payload.get("wind_velocity")),
            "wind_direction": None,
            "precipitation": self._number(payload.get("rain")),
            "weather_condition": payload.get("condition", "indefinido"),
            "timestamp": None,
            "source": "climatempo",
            "location": {
                "name": payload.get("city"),
                "region": payload.get("state"),
                "country": "Brasil",
                "lat": lat,
                "lon": lon,
            },
        }

    def _consolidate_weather_data(self, weather_data: Dict[str, Dict]) -> Dict:
        """Blend multiple providers into one normalized response."""
        weights = {
            "weatherapi": 0.4,
            "openweather": 0.3,
            "agromonitoring": 0.2,
            "climatempo": 0.1,
        }
        numeric_fields = [
            "temperature",
            "humidity",
            "pressure",
            "wind_speed",
            "precipitation",
            "visibility",
            "uv_index",
            "cloudiness",
        ]

        consolidated = {
            "sources": list(weather_data.keys()),
            "source_details": weather_data,
            "timestamp": datetime.now().isoformat(),
        }

        for field in numeric_fields:
            weighted_total = 0.0
            total_weight = 0.0
            for source_name, payload in weather_data.items():
                value = payload.get(field)
                if value is None:
                    continue
                weight = weights.get(source_name, 0.1)
                weighted_total += float(value) * weight
                total_weight += weight
            consolidated[field] = round(weighted_total / total_weight, 2) if total_weight > 0 else None

        primary_source = next((name for name in self.source_priority if name in weather_data), None)
        if primary_source:
            primary_payload = weather_data[primary_source]
            consolidated["wind_direction"] = primary_payload.get("wind_direction", 0.0)
            consolidated["weather_condition"] = primary_payload.get("weather_condition", "indefinido")
            consolidated["location"] = primary_payload.get("location")
            consolidated["source"] = primary_source
            consolidated["timestamp"] = primary_payload.get("timestamp")
        else:
            consolidated["wind_direction"] = 0.0
            consolidated["weather_condition"] = "indefinido"
            consolidated["location"] = None
            consolidated["source"] = "unknown"

        required = [consolidated.get(field) for field in ("temperature", "humidity", "wind_speed", "precipitation")]
        consolidated["availability"] = "available" if all(value is not None for value in required) else "partial" if any(value is not None for value in required) else "unavailable"
        return consolidated

    def _analyze_spray_conditions(self, weather_data: Dict) -> Dict:
        """Translate weather values into an operational spray-readiness summary."""
        required = ("temperature", "humidity", "wind_speed", "precipitation")
        if weather_data.get("availability") == "unavailable" or weather_data.get("stale") or any(weather_data.get(key) is None for key in required):
            return self._unknown_conditions("Clima ausente, incompleto ou expirado; confirme condições em campo.")
        conditions = {
            "overall_rating": "unknown",
            "temperature_ok": False,
            "humidity_ok": False,
            "wind_ok": False,
            "precipitation_ok": False,
            "recommendations": [],
            "risk_factors": [],
            "score": 0,
            "summary": "",
        }

        temp = float(weather_data.get("temperature") or 0.0)
        humidity = float(weather_data.get("humidity") or 0.0)
        wind_speed = float(weather_data.get("wind_speed") or 0.0)
        precipitation = float(weather_data.get("precipitation") or 0.0)

        if self.ideal_conditions["temperature"]["min"] <= temp <= self.ideal_conditions["temperature"]["max"]:
            conditions["temperature_ok"] = True
            conditions["score"] += 25
        elif temp < self.ideal_conditions["temperature"]["min"]:
            conditions["risk_factors"].append("Temperatura baixa - pode reduzir atividade biologica e cobertura efetiva")
        else:
            conditions["risk_factors"].append("Temperatura alta - aumenta evaporacao e risco de deriva")

        if self.ideal_conditions["humidity"]["min"] <= humidity <= self.ideal_conditions["humidity"]["max"]:
            conditions["humidity_ok"] = True
            conditions["score"] += 25
        elif humidity < self.ideal_conditions["humidity"]["min"]:
            conditions["risk_factors"].append("Umidade baixa - risco elevado de evaporacao")
        else:
            conditions["risk_factors"].append("Umidade muito alta - aumenta chance de escorrimento")

        if self.ideal_conditions["wind_speed"]["min"] <= wind_speed <= self.ideal_conditions["wind_speed"]["max"]:
            conditions["wind_ok"] = True
            conditions["score"] += 25
        elif wind_speed < self.ideal_conditions["wind_speed"]["min"]:
            conditions["risk_factors"].append("Vento muito baixo - pode indicar inversao termica")
        else:
            conditions["risk_factors"].append("Vento alto - risco de deriva")

        if precipitation <= self.ideal_conditions["precipitation"]:
            conditions["precipitation_ok"] = True
            conditions["score"] += 25
        else:
            conditions["risk_factors"].append("Chuva ou molhamento presentes - risco de lavagem do produto")

        if conditions["score"] >= 90:
            conditions["overall_rating"] = "ideal"
            conditions["summary"] = "Janela muito favoravel para pulverizacao."
            conditions["recommendations"].append("Conduzir aplicacao dentro da janela atual.")
        elif conditions["score"] >= 70:
            conditions["overall_rating"] = "good"
            conditions["summary"] = "Conjunto de condicoes bom, com pequenos pontos de atencao."
            conditions["recommendations"].append("Aplicar com acompanhamento do vento e da umidade.")
        elif conditions["score"] >= 45:
            conditions["overall_rating"] = "caution"
            conditions["summary"] = "Janela marginal; ajustes operacionais sao recomendados."
            conditions["recommendations"].append("Avaliar adiamento ou ajuste de horario.")
        else:
            conditions["overall_rating"] = "poor"
            conditions["summary"] = "Condicoes inadequadas para uma aplicacao robusta."
            conditions["recommendations"].append("Nao aplicar ate a janela meteorologica melhorar.")

        if wind_speed > self.ideal_conditions["wind_speed"]["max"]:
            conditions["recommendations"].append("Aguardar reducao do vento ou usar espectro de gotas mais grosso.")
        if humidity < self.ideal_conditions["humidity"]["min"]:
            conditions["recommendations"].append("Priorizar inicio da manha ou final da tarde.")
        if temp > self.ideal_conditions["temperature"]["max"]:
            conditions["recommendations"].append("Evitar horario mais quente do dia.")

        conditions["assessment_type"] = "screening_only"
        conditions["limitations"] = ["Faixas genéricas de triagem; não substituem bula, responsável técnico nem medição na altura da barra."]
        return conditions

    async def get_weather_forecast(self, latitude: float, longitude: float, days: int = 3) -> List[Dict]:
        """Daily rows from the same cached request; no fabricated forecast."""
        bundle = await self.get_weather_bundle(latitude, longitude)
        result = deepcopy(bundle["forecast"][:max(1, min(int(days), 7))])
        for row in result:
            row.update(stale=bundle["stale"], fetched_at=bundle["fetched_at"], expires_at=bundle["expires_at"])
            if bundle["stale"]:
                row["spray_conditions"] = self._unknown_conditions("Previsão em snapshot expirado.")
        return result

    async def _get_forecast_from_apis(self, latitude: float, longitude: float, days: int) -> List[Dict]:
        """Fetch and merge forecast data."""
        days = max(1, min(int(days), 7))

        async with aiohttp.ClientSession() as session:
            tasks = {}
            if self.apis["weatherapi"]["enabled"]:
                tasks["weatherapi"] = self._get_weatherapi_forecast(session, latitude, longitude, days)
            if self.apis["openweather"]["enabled"]:
                tasks["openweather"] = self._get_openweather_forecast(session, latitude, longitude, days)
            if self.apis["agromonitoring"]["enabled"]:
                tasks["agromonitoring"] = self._get_agromonitoring_forecast(session, latitude, longitude, days)

            if not tasks:
                raise APIConnectionError("Nenhuma API de previsao configurada")

            results = await asyncio.gather(*tasks.values(), return_exceptions=True)

        normalized: Dict[str, List[Dict]] = {}
        for source_name, result in zip(tasks.keys(), results):
            if isinstance(result, Exception):
                logger.warning(f"Previsao {source_name} falhou: {result}")
                continue
            if result:
                normalized[source_name] = result

        if not normalized:
            raise APIConnectionError("Nenhuma previsao meteorologica disponivel")

        merged = self._merge_daily_forecasts(normalized, days)
        for entry in merged:
            entry["spray_conditions"] = self._analyze_spray_conditions(entry)
        return merged

    async def _get_openweather_forecast(
        self,
        session: aiohttp.ClientSession,
        lat: float,
        lon: float,
        days: int,
    ) -> List[Dict]:
        """OpenWeather 3h forecast normalized into daily rows."""
        data = await self._request_json(
            session,
            "OpenWeather Forecast",
            f"{self.apis['openweather']['base_url']}/forecast",
            params={
                "lat": lat,
                "lon": lon,
                "appid": self.apis["openweather"]["key"],
                "units": "metric",
                "lang": "pt_br",
            },
        )
        return self._aggregate_three_hour_forecast(data.get("list", []), "openweather", days)

    async def _get_weatherapi_forecast(
        self,
        session: aiohttp.ClientSession,
        lat: float,
        lon: float,
        days: int,
    ) -> List[Dict]:
        """WeatherAPI daily forecast."""
        data = await self._request_json(
            session,
            "WeatherAPI Forecast",
            f"{self.apis['weatherapi']['base_url']}/forecast.json",
            params={
                "key": self.apis["weatherapi"]["key"],
                "q": f"{lat},{lon}",
                "days": days,
                "lang": "pt",
                "alerts": "yes",
                "aqi": "no",
            },
        )
        forecast = []
        for day in data.get("forecast", {}).get("forecastday", []):
            payload = day.get("day", {})
            forecast.append(
                {
                    "date": day.get("date"),
                    "temperature": float(payload.get("avgtemp_c", 0.0)),
                    "temperature_max": float(payload.get("maxtemp_c", 0.0)),
                    "temperature_min": float(payload.get("mintemp_c", 0.0)),
                    "humidity": float(payload.get("avghumidity", 0.0)),
                    "wind_speed": float(payload.get("maxwind_kph", 0.0)),
                    "precipitation": float(payload.get("totalprecip_mm", 0.0)),
                    "precipitation_probability": float(payload.get("daily_chance_of_rain", 0.0)),
                    "uv_index": float(payload.get("uv", 0.0)),
                    "weather_condition": payload.get("condition", {}).get("text", "indefinido"),
                    "source": "weatherapi",
                }
            )
        return forecast[:days]

    async def _get_agromonitoring_forecast(
        self,
        session: aiohttp.ClientSession,
        lat: float,
        lon: float,
        days: int,
    ) -> List[Dict]:
        """Agromonitoring 3h forecast normalized into daily rows."""
        data = await self._request_json(
            session,
            "Agromonitoring Forecast",
            f"{self.apis['agromonitoring']['base_url']}/weather/forecast",
            params={
                "lat": lat,
                "lon": lon,
                "appid": self.apis["agromonitoring"]["key"],
                "units": "metric",
            },
        )
        return self._aggregate_three_hour_forecast(data, "agromonitoring", days)

    def _aggregate_three_hour_forecast(self, items: List[Dict], source: str, days: int) -> List[Dict]:
        """Aggregate 3h weather steps into daily forecast rows."""
        grouped: Dict[str, List[Dict]] = {}
        for item in items:
            if "dt_txt" in item:
                day_key = str(item["dt_txt"])[:10]
            else:
                day_key = datetime.utcfromtimestamp(int(item.get("dt", 0))).strftime("%Y-%m-%d")
            grouped.setdefault(day_key, []).append(item)

        forecast: List[Dict] = []
        for day_key in sorted(grouped.keys())[:days]:
            entries = grouped[day_key]
            temperatures = [self._normalize_temperature(entry.get("main", {}).get("temp")) for entry in entries]
            humidities = [float(entry.get("main", {}).get("humidity", 0.0)) for entry in entries]
            wind_speeds = [float(entry.get("wind", {}).get("speed", 0.0)) * 3.6 for entry in entries]
            pressures = [float(entry.get("main", {}).get("pressure", 0.0)) for entry in entries]
            precipitations = [
                float(entry.get("rain", {}).get("3h", 0.0) or entry.get("snow", {}).get("3h", 0.0) or 0.0)
                for entry in entries
            ]
            precipitation_probability = [float(entry.get("pop", 0.0)) * 100.0 for entry in entries if entry.get("pop") is not None]

            condition = entries[0].get("weather", [{}])[0].get("description", "indefinido")
            forecast.append(
                {
                    "date": day_key,
                    "temperature": round(sum(temperatures) / max(len(temperatures), 1), 2),
                    "temperature_max": round(max(temperatures), 2),
                    "temperature_min": round(min(temperatures), 2),
                    "humidity": round(sum(humidities) / max(len(humidities), 1), 2),
                    "pressure": round(sum(pressures) / max(len(pressures), 1), 2),
                    "wind_speed": round(max(wind_speeds), 2) if wind_speeds else 0.0,
                    "precipitation": round(sum(precipitations), 2),
                    "precipitation_probability": round(max(precipitation_probability), 2) if precipitation_probability else 0.0,
                    "weather_condition": condition,
                    "source": source,
                }
            )
        return forecast

    def _merge_daily_forecasts(self, source_forecasts: Dict[str, List[Dict]], days: int) -> List[Dict]:
        """Merge daily rows by date, keeping provider priority for text fields."""
        weights = {"weatherapi": 0.45, "openweather": 0.3, "agromonitoring": 0.25}
        numeric_fields = [
            "temperature",
            "temperature_max",
            "temperature_min",
            "humidity",
            "pressure",
            "wind_speed",
            "precipitation",
            "precipitation_probability",
            "uv_index",
        ]

        by_date: Dict[str, Dict[str, Dict]] = {}
        for source_name, rows in source_forecasts.items():
            for row in rows[:days]:
                by_date.setdefault(row["date"], {})[source_name] = row

        merged: List[Dict] = []
        for day_key in sorted(by_date.keys())[:days]:
            rows = by_date[day_key]
            merged_row = {"date": day_key, "source_details": rows, "sources": list(rows.keys())}

            for field in numeric_fields:
                weighted_total = 0.0
                total_weight = 0.0
                for source_name, payload in rows.items():
                    value = payload.get(field)
                    if value is None:
                        continue
                    weight = weights.get(source_name, 0.1)
                    weighted_total += float(value) * weight
                    total_weight += weight
                if total_weight > 0:
                    merged_row[field] = round(weighted_total / total_weight, 2)

            for source_name in self.source_priority:
                payload = rows.get(source_name)
                if payload and payload.get("weather_condition"):
                    merged_row["weather_condition"] = payload["weather_condition"]
                    merged_row["source"] = source_name
                    break

            merged.append(merged_row)

        return merged

    @staticmethod
    def _normalize_temperature(value: Optional[float]) -> float:
        """Convert Kelvin responses to Celsius when needed."""
        if value is None:
            return None
        temp = float(value)
        return round(temp - 273.15, 2) if temp > 120 else round(temp, 2)


# Global singleton used by API routes and recommendation engine.
weather_service = WeatherService()
