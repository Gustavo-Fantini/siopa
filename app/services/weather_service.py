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
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import aiohttp
from loguru import logger

from app.core.config import settings
from app.core.exceptions import APIConnectionError
from app.utils.logger import log_api_call


class WeatherService:
    """Fetch and consolidate weather data from the configured APIs."""

    def __init__(self):
        self.request_timeout = 20
        self.request_retries = 2
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
        """Return live weather, falling back to mock data if providers fail."""
        try:
            return await self._get_weather_from_apis(latitude, longitude)
        except Exception as exc:
            logger.warning(f"APIs meteorologicas indisponiveis ({exc}), usando dados mock")
            return self._get_mock_weather_data(latitude, longitude)

    def _get_mock_weather_data(self, latitude: float, longitude: float) -> Dict:
        """Deterministic mock weather for local development."""
        base = {
            "temperature": 25.0,
            "humidity": 65.0,
            "wind_speed": 8.5,
            "wind_direction": 180,
            "pressure": 1013.25,
            "precipitation": 0.0,
            "weather_condition": "clear",
            "visibility": 10.0,
            "uv_index": 6.0,
            "cloudiness": 15.0,
            "location": {
                "name": "Mock location",
                "region": "Mock region",
                "country": "Brasil",
                "lat": latitude,
                "lon": longitude,
            },
            "timestamp": datetime.now().isoformat(),
            "source": "mock_data",
            "sources": ["mock_data"],
        }
        base["spray_conditions"] = self._analyze_spray_conditions(base)
        return base

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
            "wind_speed": float(data.get("wind", {}).get("speed", 0.0)) * 3.6,
            "wind_direction": float(data.get("wind", {}).get("deg", 0.0)),
            "precipitation": float(data.get("rain", {}).get("1h", 0.0) or data.get("snow", {}).get("1h", 0.0) or 0.0),
            "weather_condition": data.get("weather", [{}])[0].get("description", "indefinido"),
            "visibility": float(data.get("visibility", 0.0)) / 1000.0 if data.get("visibility") else None,
            "cloudiness": float(data.get("clouds", {}).get("all", 0.0)),
            "timestamp": datetime.now().isoformat(),
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
            "timestamp": datetime.now().isoformat(),
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
            "humidity": float(data.get("main", {}).get("humidity", 0.0)),
            "pressure": float(data.get("main", {}).get("pressure", 0.0)),
            "wind_speed": float(data.get("wind", {}).get("speed", 0.0)) * 3.6,
            "wind_direction": float(data.get("wind", {}).get("deg", 0.0)),
            "precipitation": float(data.get("rain", {}).get("1h", 0.0) or data.get("rain", {}).get("3h", 0.0) or 0.0),
            "weather_condition": data.get("weather", [{}])[0].get("description", "indefinido"),
            "cloudiness": float(data.get("clouds", {}).get("all", 0.0)),
            "timestamp": datetime.now().isoformat(),
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
            "temperature": float(payload.get("temperature", 0.0)),
            "humidity": float(payload.get("humidity", 0.0)),
            "pressure": float(payload.get("pressure", 0.0)),
            "wind_speed": float(payload.get("wind_velocity", 0.0)),
            "wind_direction": 0.0,
            "precipitation": float(payload.get("rain", 0.0) or 0.0),
            "weather_condition": payload.get("condition", "indefinido"),
            "timestamp": datetime.now().isoformat(),
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
        else:
            consolidated["wind_direction"] = 0.0
            consolidated["weather_condition"] = "indefinido"
            consolidated["location"] = None
            consolidated["source"] = "unknown"

        return consolidated

    def _analyze_spray_conditions(self, weather_data: Dict) -> Dict:
        """Translate weather values into an operational spray-readiness summary."""
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

        return conditions

    async def get_weather_forecast(self, latitude: float, longitude: float, days: int = 3) -> List[Dict]:
        """Return daily forecast data, with mock fallback if providers fail."""
        try:
            return await self._get_forecast_from_apis(latitude, longitude, days)
        except Exception as exc:
            logger.warning(f"APIs de previsao indisponiveis ({exc}), usando dados mock")
            return self._get_mock_forecast_data(latitude, longitude, days)

    def _get_mock_forecast_data(self, latitude: float, longitude: float, days: int) -> List[Dict]:
        """Simple forecast for development and smoke tests."""
        forecast = []
        for offset in range(days):
            date = datetime.now() + timedelta(days=offset)
            entry = {
                "date": date.strftime("%Y-%m-%d"),
                "temperature": 24.0 + offset,
                "temperature_max": 28.0 + offset,
                "temperature_min": 18.0 + offset,
                "humidity": 62.0 + offset,
                "wind_speed": 7.0 + offset,
                "precipitation": 0.0 if offset < 2 else 1.2,
                "precipitation_probability": min(20 + (offset * 10), 80),
                "weather_condition": "partly_cloudy" if offset % 2 else "clear",
                "source": "mock_data",
            }
            entry["spray_conditions"] = self._analyze_spray_conditions(entry)
            forecast.append(entry)
        return forecast

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
        temp = float(value or 0.0)
        return round(temp - 273.15, 2) if temp > 120 else round(temp, 2)


# Global singleton used by API routes and recommendation engine.
weather_service = WeatherService()
