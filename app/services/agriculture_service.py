"""
Agricultural context service.

This service combines:
- a richer local agronomic knowledge base
- reverse location hints from configured weather providers
- IBGE locality metadata
- optional Agromonitoring soil snapshots driven by lat/lon
"""

from __future__ import annotations

import asyncio
import math
import unicodedata
from copy import deepcopy
from datetime import datetime
from typing import Dict, List, Optional

import aiohttp
from loguru import logger

from app.core.config import settings
from app.core.exceptions import APIConnectionError
from app.utils.logger import log_api_call


class AgricultureService:
    """Return crop, region and soil context for spray decisions."""

    def __init__(self):
        self.request_timeout = 20
        self.request_retries = 2
        self._regional_context_cache: Dict[str, Dict] = {}
        self._agro_polygon_cache: Dict[str, str] = {}

        self.apis = {
            "ibge": {
                "base_url": settings.IBGE_API_URL,
                "enabled": True,
            },
            "weatherapi": {
                "base_url": "https://api.weatherapi.com/v1",
                "key": settings.WEATHERAPI_KEY,
                "enabled": bool(settings.WEATHERAPI_KEY),
            },
            "openweather": {
                "base_url": "https://api.openweathermap.org/data/2.5",
                "key": settings.OPENWEATHER_API_KEY,
                "enabled": bool(settings.OPENWEATHER_API_KEY),
            },
            "agromonitoring": {
                "base_url": "https://api.agromonitoring.com/agro/1.0",
                "key": settings.AGRO_API_TOKEN,
                "enabled": bool(settings.AGRO_API_TOKEN),
            },
        }

        self.state_name_to_code = {
            "acre": "AC",
            "alagoas": "AL",
            "amapa": "AP",
            "amazonas": "AM",
            "bahia": "BA",
            "ceara": "CE",
            "distrito federal": "DF",
            "espirito santo": "ES",
            "goias": "GO",
            "maranhao": "MA",
            "mato grosso": "MT",
            "mato grosso do sul": "MS",
            "minas gerais": "MG",
            "para": "PA",
            "paraiba": "PB",
            "parana": "PR",
            "pernambuco": "PE",
            "piaui": "PI",
            "rio de janeiro": "RJ",
            "rio grande do norte": "RN",
            "rio grande do sul": "RS",
            "rondonia": "RO",
            "roraima": "RR",
            "santa catarina": "SC",
            "sao paulo": "SP",
            "sergipe": "SE",
            "tocantins": "TO",
        }

        self.dominant_biome_by_state = {
            "AC": "Amazonia",
            "AL": "Mata Atlantica",
            "AP": "Amazonia",
            "AM": "Amazonia",
            "BA": "Cerrado",
            "CE": "Caatinga",
            "DF": "Cerrado",
            "ES": "Mata Atlantica",
            "GO": "Cerrado",
            "MA": "Amazonia",
            "MT": "Cerrado",
            "MS": "Cerrado",
            "MG": "Cerrado",
            "PA": "Amazonia",
            "PB": "Caatinga",
            "PR": "Mata Atlantica",
            "PE": "Caatinga",
            "PI": "Caatinga",
            "RJ": "Mata Atlantica",
            "RN": "Caatinga",
            "RS": "Pampa",
            "RO": "Amazonia",
            "RR": "Amazonia",
            "SC": "Mata Atlantica",
            "SP": "Mata Atlantica",
            "SE": "Caatinga",
            "TO": "Cerrado",
        }

        self.crop_database = {
            "soja": {
                "name": "Soja",
                "scientific_name": "Glycine max",
                "growth_stages": ["germinacao", "vegetativo", "floracao", "enchimento_graos", "maturacao"],
                "ideal_ph": {"min": 6.0, "max": 7.0},
                "nutrient_requirements": {
                    "nitrogen": "alto",
                    "phosphorus": "medio",
                    "potassium": "alto",
                    "calcium": "medio",
                    "magnesium": "medio",
                },
                "common_pests": ["lagarta-da-soja", "percevejo", "mosca-branca"],
                "common_diseases": ["ferrugem-asiatica", "antracnose", "mancha-alvo"],
                "spray_recommendations": {
                    "nozzle_type": "XR110015",
                    "pressure_bar": 3.0,
                    "volume_ha": 150,
                    "droplet_size": "media",
                },
            },
            "milho": {
                "name": "Milho",
                "scientific_name": "Zea mays",
                "growth_stages": ["germinacao", "vegetativo", "pendoamento", "espigamento", "maturacao"],
                "ideal_ph": {"min": 5.5, "max": 7.0},
                "nutrient_requirements": {
                    "nitrogen": "muito_alto",
                    "phosphorus": "alto",
                    "potassium": "alto",
                    "calcium": "medio",
                    "magnesium": "medio",
                },
                "common_pests": ["lagarta-do-cartucho", "broca-do-colmo", "cigarrinha"],
                "common_diseases": ["mancha-branca", "ferrugem-comum", "antracnose"],
                "spray_recommendations": {
                    "nozzle_type": "XR11002",
                    "pressure_bar": 2.5,
                    "volume_ha": 180,
                    "droplet_size": "grossa",
                },
            },
            "algodao": {
                "name": "Algodao",
                "scientific_name": "Gossypium hirsutum",
                "growth_stages": ["germinacao", "vegetativo", "floracao", "frutificacao", "abertura_capulhos"],
                "ideal_ph": {"min": 5.8, "max": 8.0},
                "nutrient_requirements": {
                    "nitrogen": "alto",
                    "phosphorus": "alto",
                    "potassium": "muito_alto",
                    "calcium": "alto",
                    "magnesium": "medio",
                },
                "common_pests": ["bicudo", "lagarta-rosada", "pulgao"],
                "common_diseases": ["murcha-de-fusarium", "ramulose", "mancha-angular"],
                "spray_recommendations": {
                    "nozzle_type": "XR110025",
                    "pressure_bar": 3.5,
                    "volume_ha": 100,
                    "droplet_size": "fina",
                },
            },
            "cana": {
                "name": "Cana-de-acucar",
                "scientific_name": "Saccharum officinarum",
                "growth_stages": ["brotacao", "perfilhamento", "crescimento", "maturacao"],
                "ideal_ph": {"min": 5.5, "max": 7.5},
                "nutrient_requirements": {
                    "nitrogen": "alto",
                    "phosphorus": "medio",
                    "potassium": "muito_alto",
                    "calcium": "medio",
                    "magnesium": "baixo",
                },
                "common_pests": ["broca-da-cana", "cigarrinha", "sphenophorus"],
                "common_diseases": ["ferrugem", "carvao", "podridao-vermelha"],
                "spray_recommendations": {
                    "nozzle_type": "XR11003",
                    "pressure_bar": 2.0,
                    "volume_ha": 250,
                    "droplet_size": "muito_grossa",
                },
            },
        }

        self.stage_recommendations = {
            "soja": {
                "germinacao": {
                    "pesticides": ["fungicida_semente"],
                    "nutrients": ["fosforo"],
                    "spray_volume": 100,
                },
                "vegetativo": {
                    "pesticides": ["herbicida_pos", "inseticida_preventivo"],
                    "nutrients": ["nitrogenio", "potassio"],
                    "spray_volume": 140,
                },
                "floracao": {
                    "pesticides": ["fungicida_preventivo", "inseticida_percevejo"],
                    "nutrients": ["boro", "molibdenio"],
                    "spray_volume": 150,
                },
                "enchimento_graos": {
                    "pesticides": ["fungicida_ferrugem", "inseticida_lagarta"],
                    "nutrients": ["potassio"],
                    "spray_volume": 180,
                },
            },
            "milho": {
                "germinacao": {
                    "pesticides": ["fungicida_semente", "inseticida_solo"],
                    "nutrients": ["fosforo", "zinco"],
                    "spray_volume": 120,
                },
                "vegetativo": {
                    "pesticides": ["herbicida_pos", "inseticida_lagarta"],
                    "nutrients": ["nitrogenio"],
                    "spray_volume": 170,
                },
                "pendoamento": {
                    "pesticides": ["fungicida_foliar", "inseticida_broca"],
                    "nutrients": ["nitrogenio", "potassio"],
                    "spray_volume": 180,
                },
            },
            "algodao": {
                "vegetativo": {
                    "pesticides": ["regulador_crescimento", "inseticida_preventivo"],
                    "nutrients": ["boro", "nitrogenio"],
                    "spray_volume": 90,
                },
                "floracao": {
                    "pesticides": ["fungicida_foliar", "bicudicida"],
                    "nutrients": ["potassio", "boro"],
                    "spray_volume": 110,
                },
            },
            "cana": {
                "perfilhamento": {
                    "pesticides": ["herbicida_linha", "controle_cigarrinha"],
                    "nutrients": ["nitrogenio", "potassio"],
                    "spray_volume": 220,
                },
                "crescimento": {
                    "pesticides": ["fungicida_foliar", "controle_broca"],
                    "nutrients": ["potassio"],
                    "spray_volume": 250,
                },
            },
        }

        self.soil_database = {
            "latossolo": {
                "name": "Latossolo",
                "characteristics": {
                    "texture": "media a argilosa",
                    "drainage": "boa",
                    "fertility": "baixa a media",
                    "ph_typical": 5.6,
                    "organic_matter": "baixa",
                    "cation_exchange": "baixa",
                },
                "minerals": ["caulinita", "gibbsita", "goethita", "hematita"],
            },
            "argissolo": {
                "name": "Argissolo",
                "characteristics": {
                    "texture": "media",
                    "drainage": "moderada",
                    "fertility": "media",
                    "ph_typical": 6.0,
                    "organic_matter": "media",
                    "cation_exchange": "media",
                },
                "minerals": ["caulinita", "illita", "montmorilonita"],
            },
            "neossolo": {
                "name": "Neossolo",
                "characteristics": {
                    "texture": "arenosa a media",
                    "drainage": "alta",
                    "fertility": "baixa",
                    "ph_typical": 6.3,
                    "organic_matter": "muito_baixa",
                    "cation_exchange": "muito_baixa",
                },
                "minerals": ["quartzo", "feldspato", "mica"],
            },
            "gleissolo": {
                "name": "Gleissolo",
                "characteristics": {
                    "texture": "argilosa",
                    "drainage": "deficiente",
                    "fertility": "media",
                    "ph_typical": 5.4,
                    "organic_matter": "media a alta",
                    "cation_exchange": "media",
                },
                "minerals": ["argilominerais hidratados", "materia organica", "ferro reduzido"],
            },
            "cambissolo": {
                "name": "Cambissolo",
                "characteristics": {
                    "texture": "variavel",
                    "drainage": "boa",
                    "fertility": "media",
                    "ph_typical": 5.8,
                    "organic_matter": "media",
                    "cation_exchange": "media",
                },
                "minerals": ["caulinita", "quartzo", "mica"],
            },
        }

        self.biome_profiles = {
            "Amazonia": {
                "climate_pattern": "quente e muito umido",
                "regional_risks": ["chuvas frequentes", "alta pressao de doencas foliares"],
                "default_spray_adjustments": {"droplet_size": "grossa", "volume_ha_delta": 20},
            },
            "Cerrado": {
                "climate_pattern": "tropical com estacao seca definida",
                "regional_risks": ["veranico", "evaporacao alta na tarde", "janelas curtas de umidade ideal"],
                "default_spray_adjustments": {"droplet_size": "media a grossa", "volume_ha_delta": 10},
            },
            "Mata Atlantica": {
                "climate_pattern": "umido a subtropical",
                "regional_risks": ["orvalho prolongado", "alta variabilidade de relevo"],
                "default_spray_adjustments": {"droplet_size": "media", "volume_ha_delta": 0},
            },
            "Caatinga": {
                "climate_pattern": "semiarido",
                "regional_risks": ["baixa umidade", "temperaturas elevadas", "necessidade de horario restrito"],
                "default_spray_adjustments": {"droplet_size": "grossa", "volume_ha_delta": -10},
            },
            "Pantanal": {
                "climate_pattern": "planicie sazonalmente alagavel",
                "regional_risks": ["encharcamento", "janela operacional reduzida", "solo sensivel a trafego"],
                "default_spray_adjustments": {"droplet_size": "grossa", "volume_ha_delta": 15},
            },
            "Pampa": {
                "climate_pattern": "subtropical com inverno marcado",
                "regional_risks": ["vento frequente", "janelas frias pela manha"],
                "default_spray_adjustments": {"droplet_size": "media", "volume_ha_delta": 0},
            },
        }

        self.crop_regional_profiles = {
            "soja": {
                "Cerrado": {
                    "planting_window": ["setembro", "outubro", "novembro"],
                    "alerts": ["monitorar ferrugem asiatica a partir da floracao", "ajustar horario para evitar baixa umidade"],
                    "spray_adjustments": {"volume_ha": 140, "pressure_bar": 3.0, "droplet_size": "media a grossa"},
                },
                "Mata Atlantica": {
                    "planting_window": ["outubro", "novembro", "dezembro"],
                    "alerts": ["maior pressao de doencas em periodos de molhamento foliar longo"],
                    "spray_adjustments": {"volume_ha": 130, "pressure_bar": 2.8, "droplet_size": "media"},
                },
                "Pampa": {
                    "planting_window": ["outubro", "novembro"],
                    "alerts": ["cuidar com vento em operacoes de campo aberto"],
                    "spray_adjustments": {"volume_ha": 120, "pressure_bar": 2.6, "droplet_size": "media"},
                },
            },
            "milho": {
                "Cerrado": {
                    "planting_window": ["setembro", "outubro", "janeiro", "fevereiro"],
                    "alerts": ["safrinha pede atencao a cigarrinha e seca terminal"],
                    "spray_adjustments": {"volume_ha": 170, "pressure_bar": 2.7, "droplet_size": "grossa"},
                },
                "Mata Atlantica": {
                    "planting_window": ["setembro", "outubro", "novembro"],
                    "alerts": ["monitorar mancha branca e ferrugens em talhoes umidos"],
                    "spray_adjustments": {"volume_ha": 180, "pressure_bar": 2.6, "droplet_size": "media a grossa"},
                },
                "Caatinga": {
                    "planting_window": ["janeiro", "fevereiro", "marco"],
                    "alerts": ["preferir manejo sincronizado com chuvas ou irrigacao"],
                    "spray_adjustments": {"volume_ha": 160, "pressure_bar": 2.5, "droplet_size": "grossa"},
                },
            },
            "algodao": {
                "Cerrado": {
                    "planting_window": ["novembro", "dezembro", "janeiro"],
                    "alerts": ["alto risco de bicudo e necessidade de cobertura fina no terco medio"],
                    "spray_adjustments": {"volume_ha": 110, "pressure_bar": 3.4, "droplet_size": "fina a media"},
                },
                "Caatinga": {
                    "planting_window": ["fevereiro", "marco"],
                    "alerts": ["restrinja aplicacoes a janelas de maior umidade relativa"],
                    "spray_adjustments": {"volume_ha": 100, "pressure_bar": 3.1, "droplet_size": "media"},
                },
            },
            "cana": {
                "Cerrado": {
                    "planting_window": ["fevereiro", "marco", "abril", "setembro"],
                    "alerts": ["acompanhar deficit hidrico e broca em expansao vegetativa"],
                    "spray_adjustments": {"volume_ha": 240, "pressure_bar": 2.1, "droplet_size": "muito_grossa"},
                },
                "Mata Atlantica": {
                    "planting_window": ["marco", "abril", "setembro", "outubro"],
                    "alerts": ["umidade favorece ferrugens e podridoes em areas densas"],
                    "spray_adjustments": {"volume_ha": 260, "pressure_bar": 2.0, "droplet_size": "grossa a muito_grossa"},
                },
            },
        }

    def get_supported_crops(self) -> List[Dict]:
        """Return crop metadata consumed by the UI."""
        return [
            {
                "key": key,
                "name": value["name"],
                "scientific_name": value["scientific_name"],
                "growth_stages": value["growth_stages"],
            }
            for key, value in self.crop_database.items()
        ]

    async def get_crop_info(
        self,
        crop_type: str,
        growth_stage: Optional[str] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
    ) -> Dict:
        """Return crop data optionally enriched by region and coordinates."""
        try:
            crop_key = self._normalize_crop_key(crop_type)
            logger.info(f"Obtendo informacoes da cultura: {crop_type}")

            if crop_key not in self.crop_database:
                return await self._search_external_crop_data(crop_type, latitude, longitude)

            crop_info = deepcopy(self.crop_database[crop_key])
            crop_info["spray_recommendations"] = self._normalize_spray_recommendations(crop_info["spray_recommendations"])

            if growth_stage:
                crop_info["stage_recommendations"] = self._get_stage_recommendations(crop_key, growth_stage)

            if latitude is not None and longitude is not None:
                regional_context = await self._get_location_context(latitude, longitude)
                regional_profile = self._get_regional_crop_profile(crop_key, regional_context)
                crop_info["regional_context"] = regional_context
                crop_info["regional_profile"] = regional_profile
                crop_info["planting_window"] = regional_profile.get("planting_window", [])
                crop_info["regional_alerts"] = regional_profile.get("alerts", [])
                crop_info["spray_recommendations"] = self._merge_spray_recommendations(
                    crop_info["spray_recommendations"],
                    regional_profile,
                    regional_context,
                )

            crop_info["timestamp"] = datetime.now().isoformat()
            return crop_info
        except Exception as exc:
            logger.error(f"Erro ao obter informacoes da cultura: {exc}")
            raise APIConnectionError(f"Falha na obtencao de dados da cultura: {exc}")

    def _get_stage_recommendations(self, crop_key: str, stage: str) -> Dict:
        """Return stage-specific agronomic guidance."""
        normalized_stage = self._normalize_text(stage).replace(" ", "_")
        return deepcopy(self.stage_recommendations.get(crop_key, {}).get(normalized_stage, {}))

    async def get_soil_info(self, latitude: float, longitude: float) -> Dict:
        """Return soil context, preferring Agromonitoring data when available."""
        try:
            regional_context = await self._get_location_context(latitude, longitude)
            soil_key = self._determine_soil_type(regional_context)
            soil_profile = deepcopy(self.soil_database.get(soil_key, self.soil_database["latossolo"]))
            agromonitoring_data = await self._get_agromonitoring_soil_data(latitude, longitude)

            moisture_status = self._classify_soil_moisture(
                agromonitoring_data.get("moisture_m3m3") if agromonitoring_data else None
            )

            return {
                "location": regional_context,
                "soil_key": soil_key,
                "soil_type": soil_profile["name"],
                "ph": soil_profile["characteristics"]["ph_typical"],
                "texture": soil_profile["characteristics"]["texture"],
                "drainage": soil_profile["characteristics"]["drainage"],
                "fertility": soil_profile["characteristics"]["fertility"],
                "organic_matter": soil_profile["characteristics"]["organic_matter"],
                "mineral_composition": soil_profile["minerals"],
                "agromonitoring": agromonitoring_data,
                "moisture_status": moisture_status,
                "recommendations": self._build_soil_recommendations(soil_profile, moisture_status, regional_context),
                "source": "agromonitoring+regional_profile" if agromonitoring_data else "regional_profile",
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as exc:
            logger.warning(f"APIs de solo indisponiveis ({exc}), usando dados regionais estimados")
            return self._get_mock_soil_info(latitude, longitude)

    def _get_mock_soil_info(self, latitude: float, longitude: float) -> Dict:
        """Fallback soil answer when network providers fail."""
        biome = self._get_biome_by_coordinates(latitude, longitude, None)
        regional_context = {
            "municipio": "Desconhecido",
            "uf": "BR",
            "regiao": "Brasil",
            "bioma": biome,
            "agricultural_zone": self._classify_agricultural_zone(latitude, longitude, biome, None),
            "coordinates": {"latitude": latitude, "longitude": longitude},
        }
        soil_key = self._determine_soil_type(regional_context)
        soil_profile = deepcopy(self.soil_database.get(soil_key, self.soil_database["latossolo"]))
        return {
            "location": regional_context,
            "soil_key": soil_key,
            "soil_type": soil_profile["name"],
            "ph": soil_profile["characteristics"]["ph_typical"],
            "texture": soil_profile["characteristics"]["texture"],
            "drainage": soil_profile["characteristics"]["drainage"],
            "fertility": soil_profile["characteristics"]["fertility"],
            "organic_matter": soil_profile["characteristics"]["organic_matter"],
            "mineral_composition": soil_profile["minerals"],
            "agromonitoring": None,
            "moisture_status": "desconhecida",
            "recommendations": self._build_soil_recommendations(soil_profile, "desconhecida", regional_context),
            "source": "regional_profile",
            "timestamp": datetime.now().isoformat(),
        }

    async def _get_location_context(self, lat: float, lon: float) -> Dict:
        """Resolve municipality, UF, biome and agricultural zone for lat/lon."""
        cache_key = f"{lat:.4f}:{lon:.4f}"
        if cache_key in self._regional_context_cache:
            return deepcopy(self._regional_context_cache[cache_key])

        async with aiohttp.ClientSession() as session:
            location_hint = await self._resolve_location_hint(session, lat, lon)
            ibge_match = await self._lookup_ibge_context(session, location_hint)

        uf = ibge_match.get("uf") or location_hint.get("uf")
        biome = self._get_biome_by_coordinates(lat, lon, uf)
        agricultural_zone = self._classify_agricultural_zone(lat, lon, biome, uf)

        context = {
            "municipio": ibge_match.get("municipio") or location_hint.get("municipio") or "Desconhecido",
            "municipio_ibge_id": ibge_match.get("municipio_ibge_id"),
            "uf": uf or "BR",
            "uf_name": ibge_match.get("uf_name") or location_hint.get("uf_name") or "Brasil",
            "regiao": ibge_match.get("regiao") or "Brasil",
            "mesorregiao": ibge_match.get("mesorregiao"),
            "microrregiao": ibge_match.get("microrregiao"),
            "regiao_imediata": ibge_match.get("regiao_imediata"),
            "regiao_intermediaria": ibge_match.get("regiao_intermediaria"),
            "bioma": biome,
            "agricultural_zone": agricultural_zone,
            "coordinates": {"latitude": lat, "longitude": lon},
            "location_source": location_hint.get("source", "coordinates_only"),
            "ibge_matched": bool(ibge_match.get("municipio_ibge_id")),
        }

        self._regional_context_cache[cache_key] = deepcopy(context)
        return context

    async def _resolve_location_hint(self, session: aiohttp.ClientSession, lat: float, lon: float) -> Dict:
        """Use configured weather providers as reverse geocoding hints."""
        if self.apis["weatherapi"]["enabled"]:
            try:
                data = await self._request_json(
                    session,
                    "WeatherAPI location",
                    f"{self.apis['weatherapi']['base_url']}/current.json",
                    params={"key": self.apis["weatherapi"]["key"], "q": f"{lat},{lon}", "aqi": "no"},
                )
                location = data.get("location", {})
                return {
                    "municipio": location.get("name"),
                    "uf_name": location.get("region"),
                    "uf": self._state_to_code(location.get("region")),
                    "country": location.get("country"),
                    "source": "weatherapi",
                }
            except Exception as exc:
                logger.debug(f"WeatherAPI nao conseguiu resolver localizacao: {exc}")

        if self.apis["openweather"]["enabled"]:
            try:
                data = await self._request_json(
                    session,
                    "OpenWeather location",
                    f"{self.apis['openweather']['base_url']}/weather",
                    params={
                        "lat": lat,
                        "lon": lon,
                        "appid": self.apis["openweather"]["key"],
                        "units": "metric",
                    },
                )
                return {
                    "municipio": data.get("name"),
                    "uf_name": None,
                    "uf": None,
                    "country": data.get("sys", {}).get("country"),
                    "source": "openweather",
                }
            except Exception as exc:
                logger.debug(f"OpenWeather nao conseguiu resolver localizacao: {exc}")

        return {"municipio": None, "uf": None, "uf_name": None, "country": "Brasil", "source": "coordinates_only"}

    async def _lookup_ibge_context(self, session: aiohttp.ClientSession, location_hint: Dict) -> Dict:
        """Match municipality and state against the IBGE localities API."""
        municipio = location_hint.get("municipio")
        uf = location_hint.get("uf")
        if not municipio or not uf:
            return {}

        url = f"{self.apis['ibge']['base_url']}/localidades/estados/{uf}/municipios"
        data = await self._request_json(
            session,
            "IBGE",
            url,
            params={"orderBy": "nome"},
        )

        selected = self._match_municipality(municipio, data)
        if not selected:
            return {
                "municipio": municipio,
                "uf": uf,
                "uf_name": location_hint.get("uf_name"),
            }

        microrregiao = selected.get("microrregiao", {}) or {}
        mesorregiao = microrregiao.get("mesorregiao", {}) or {}
        uf_info = mesorregiao.get("UF", {}) or {}
        regiao = uf_info.get("regiao", {}) or {}
        regiao_imediata = selected.get("regiao-imediata", {}) or {}
        regiao_intermediaria = regiao_imediata.get("regiao-intermediaria", {}) or {}

        return {
            "municipio": selected.get("nome"),
            "municipio_ibge_id": selected.get("id"),
            "uf": uf_info.get("sigla", uf),
            "uf_name": uf_info.get("nome", location_hint.get("uf_name")),
            "regiao": regiao.get("nome", "Brasil"),
            "mesorregiao": mesorregiao.get("nome"),
            "microrregiao": microrregiao.get("nome"),
            "regiao_imediata": regiao_imediata.get("nome"),
            "regiao_intermediaria": regiao_intermediaria.get("nome"),
        }

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
        """Perform one JSON request with retry/backoff."""
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
                        text = await response.text()
                        raise APIConnectionError(f"{source_name} retornou status {response.status}: {text[:200]}")
                    return await response.json()
            except Exception as exc:
                last_error = exc
                if attempt >= self.request_retries:
                    break
                await asyncio.sleep(0.35 * (attempt + 1))

        raise APIConnectionError(f"Falha ao consultar {source_name}: {last_error}")

    async def _get_agromonitoring_soil_data(self, latitude: float, longitude: float) -> Optional[Dict]:
        """Return current soil moisture and temperature from Agromonitoring."""
        if not self.apis["agromonitoring"]["enabled"]:
            return None

        async with aiohttp.ClientSession() as session:
            polyid = await self._ensure_agro_polygon(session, latitude, longitude)
            if not polyid:
                return None

            data = await self._request_json(
                session,
                "Agromonitoring Soil",
                f"{self.apis['agromonitoring']['base_url']}/soil",
                params={"appid": self.apis["agromonitoring"]["key"], "polyid": polyid},
            )

        moisture = float(data.get("moisture", 0.0))
        return {
            "polygon_id": polyid,
            "surface_temperature_c": self._normalize_temperature(data.get("t0")),
            "temperature_10cm_c": self._normalize_temperature(data.get("t10")),
            "moisture_m3m3": moisture,
            "moisture_status": self._classify_soil_moisture(moisture),
            "timestamp": datetime.now().isoformat(),
        }

    async def _ensure_agro_polygon(self, session: aiohttp.ClientSession, lat: float, lon: float) -> Optional[str]:
        """Create or reuse a small deterministic polygon around the requested point."""
        cache_key = f"{lat:.4f}:{lon:.4f}"
        if cache_key in self._agro_polygon_cache:
            return self._agro_polygon_cache[cache_key]

        polygon_name = f"siopa-{lat:.4f}-{lon:.4f}"
        dlat = 0.0007
        dlon = dlat / max(math.cos(math.radians(lat)), 0.35)
        coordinates = [
            [lon - dlon, lat - dlat],
            [lon + dlon, lat - dlat],
            [lon + dlon, lat + dlat],
            [lon - dlon, lat + dlat],
            [lon - dlon, lat - dlat],
        ]
        body = {
            "name": polygon_name,
            "geo_json": {
                "type": "Feature",
                "properties": {},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [coordinates],
                },
            },
        }

        data = await self._request_json(
            session,
            "Agromonitoring Polygon",
            f"{self.apis['agromonitoring']['base_url']}/polygons",
            method="POST",
            params={"appid": self.apis["agromonitoring"]["key"], "duplicated": "true"},
            json_body=body,
            expected_statuses={200, 201},
        )

        polygon_id = data.get("id")
        if polygon_id:
            self._agro_polygon_cache[cache_key] = polygon_id
        return polygon_id

    def _normalize_crop_key(self, crop_type: str) -> str:
        """Normalize crop aliases to the internal keys."""
        normalized = self._normalize_text(crop_type).replace(" ", "_").replace("-", "_")
        aliases = {
            "soja": "soja",
            "milho": "milho",
            "algodao": "algodao",
            "algodao_herbaceo": "algodao",
            "cana": "cana",
            "cana_de_acucar": "cana",
        }
        return aliases.get(normalized, normalized)

    def _match_municipality(self, expected_name: str, municipalities: List[Dict]) -> Optional[Dict]:
        """Match municipality names ignoring accents and case."""
        target = self._normalize_text(expected_name)
        exact = next((item for item in municipalities if self._normalize_text(item.get("nome", "")) == target), None)
        if exact:
            return exact

        startswith = next(
            (item for item in municipalities if self._normalize_text(item.get("nome", "")).startswith(target)),
            None,
        )
        if startswith:
            return startswith

        contains = next(
            (item for item in municipalities if target in self._normalize_text(item.get("nome", ""))),
            None,
        )
        return contains

    def _state_to_code(self, value: Optional[str]) -> Optional[str]:
        """Translate a state string into a UF code."""
        if not value:
            return None
        normalized = self._normalize_text(value)
        if len(normalized) == 2:
            return normalized.upper()
        return self.state_name_to_code.get(normalized)

    def _normalize_text(self, value: Optional[str]) -> str:
        """Remove accents and normalize whitespace/case."""
        text = unicodedata.normalize("NFKD", str(value or ""))
        text = text.encode("ascii", "ignore").decode("ascii")
        return " ".join(text.lower().strip().split())

    def _get_biome_by_coordinates(self, lat: float, lon: float, uf: Optional[str]) -> str:
        """Infer the dominant biome from coordinates, with UF fallback."""
        if uf == "RS":
            return "Pampa"
        if -20.8 <= lat <= -15.0 and -59.8 <= lon <= -54.0:
            return "Pantanal"
        if -8.5 <= lat <= 5.5 and -74.0 <= lon <= -44.0 and (uf in {"AC", "AM", "AP", "PA", "RO", "RR", "MA"} or lon < -52):
            return "Amazonia"
        if uf in {"CE", "RN", "PB", "PE", "AL", "SE", "PI"}:
            return "Caatinga"
        if uf == "BA" and lat > -18.5 and lon < -39.5:
            return "Caatinga"
        if -25.5 <= lat <= 3.5 and -62.5 <= lon <= -42.0:
            return "Cerrado"
        if uf in {"ES", "RJ", "SP", "PR", "SC"}:
            return "Mata Atlantica"
        if uf in {"MG", "GO", "DF", "TO", "MT", "MS"}:
            return "Cerrado"
        return self.dominant_biome_by_state.get(uf or "", "Mata Atlantica")

    def _classify_agricultural_zone(self, lat: float, lon: float, biome: str, uf: Optional[str]) -> str:
        """Return a practical agricultural zone label for recommendation tuning."""
        if biome == "Cerrado":
            return "graos_tropicais_planalto"
        if biome == "Amazonia":
            return "fronteira_umida"
        if biome == "Caatinga":
            return "semiarido_irrigado"
        if biome == "Pantanal":
            return "baixada_alagavel"
        if biome == "Pampa":
            return "campos_sulinos"
        if uf in {"PR", "SC", "RS"}:
            return "sul_subtropical"
        return "faixa_litoranea_e_transicao"

    def _determine_soil_type(self, region_info: Dict) -> str:
        """Map biome/zone context to a representative soil group."""
        biome = region_info.get("bioma", "Cerrado")
        zone = region_info.get("agricultural_zone", "")
        mapping = {
            "Cerrado": "latossolo",
            "Amazonia": "latossolo",
            "Mata Atlantica": "argissolo",
            "Caatinga": "neossolo",
            "Pantanal": "gleissolo",
            "Pampa": "cambissolo",
        }
        if "alagavel" in zone:
            return "gleissolo"
        return mapping.get(biome, "latossolo")

    def _get_regional_crop_profile(self, crop_key: str, regional_context: Dict) -> Dict:
        """Return crop-specific agronomic adjustments for the resolved biome."""
        biome = regional_context.get("bioma")
        profile = deepcopy(self.crop_regional_profiles.get(crop_key, {}).get(biome, {}))
        profile["biome"] = biome
        profile["biome_profile"] = deepcopy(self.biome_profiles.get(biome, {}))
        return profile

    def _normalize_spray_recommendations(self, spray: Dict) -> Dict:
        """Expose spray parameters in both numeric and UI-friendly formats."""
        normalized = deepcopy(spray)
        pressure_bar = float(normalized.get("pressure_bar", 0.0) or 0.0)
        normalized["pressure_bar"] = pressure_bar
        normalized["pressure"] = f"{pressure_bar:.1f} bar" if pressure_bar else "N/A"
        return normalized

    def _merge_spray_recommendations(self, base_spray: Dict, regional_profile: Dict, regional_context: Dict) -> Dict:
        """Blend base crop setup with biome-specific operating hints."""
        merged = self._normalize_spray_recommendations(base_spray)
        spray_adjustments = regional_profile.get("spray_adjustments", {})
        biome_profile = regional_profile.get("biome_profile", {})
        default_adjustments = biome_profile.get("default_spray_adjustments", {})

        if "volume_ha" in spray_adjustments:
            merged["volume_ha"] = spray_adjustments["volume_ha"]
        elif "volume_ha_delta" in default_adjustments:
            merged["volume_ha"] = max(60, merged.get("volume_ha", 120) + default_adjustments["volume_ha_delta"])

        if "pressure_bar" in spray_adjustments:
            merged["pressure_bar"] = float(spray_adjustments["pressure_bar"])

        if spray_adjustments.get("droplet_size"):
            merged["droplet_size"] = spray_adjustments["droplet_size"]
        elif default_adjustments.get("droplet_size"):
            merged["droplet_size"] = default_adjustments["droplet_size"]

        merged["pressure"] = f"{merged['pressure_bar']:.1f} bar"
        merged["regional_note"] = (
            f"Bioma {regional_context.get('bioma')} com zona {regional_context.get('agricultural_zone')} "
            f"exige janela operacional ajustada ao clima {biome_profile.get('climate_pattern', 'regional')}."
        )
        return merged

    def _classify_soil_moisture(self, moisture: Optional[float]) -> str:
        """Translate soil moisture in m3/m3 into an operational label."""
        if moisture is None:
            return "desconhecida"
        if moisture < 0.12:
            return "baixa"
        if moisture < 0.22:
            return "moderada"
        if moisture < 0.35:
            return "alta"
        return "muito_alta"

    def _build_soil_recommendations(self, soil_profile: Dict, moisture_status: str, regional_context: Dict) -> Dict:
        """Generate soil and field-operation notes."""
        recommendations = {
            "ph_adjustment": f"Monitorar correcao para manter pH proximo de {soil_profile['characteristics']['ph_typical']}.",
            "organic_matter": "Manter palhada e aporte organico para estabilizar infiltracao e disponibilidade de agua.",
            "spray_considerations": [],
        }

        if moisture_status in {"alta", "muito_alta"}:
            recommendations["spray_considerations"].append("Evitar trafego pesado em solo muito umido para reduzir compactacao.")
        if moisture_status == "baixa":
            recommendations["spray_considerations"].append("Priorizar janelas de maior umidade relativa para reduzir evaporacao na aplicacao.")
        if regional_context.get("bioma") == "Caatinga":
            recommendations["spray_considerations"].append("No semiarido, restringir aplicacoes aos periodos mais amenos do dia.")
        if regional_context.get("bioma") == "Pantanal":
            recommendations["spray_considerations"].append("Areas sujeitas a encharcamento pedem atencao redobrada ao trafego e a infiltracao.")
        return recommendations

    async def _search_external_crop_data(
        self,
        crop_type: str,
        latitude: Optional[float],
        longitude: Optional[float],
    ) -> Dict:
        """Return a safe fallback for unsupported crops."""
        regional_context = None
        if latitude is not None and longitude is not None:
            regional_context = await self._get_location_context(latitude, longitude)

        return {
            "name": str(crop_type).title(),
            "status": "dados_limitados",
            "message": "Cultura nao encontrada na base local. Recomenda-se validacao com engenheiro agronomo.",
            "general_recommendations": {
                "spray_volume": 150,
                "nozzle_type": "XR110015",
                "pressure_bar": 3.0,
            },
            "regional_context": regional_context,
            "timestamp": datetime.now().isoformat(),
        }

    @staticmethod
    def _normalize_temperature(value: Optional[float]) -> float:
        """Convert Kelvin temperatures to Celsius when needed."""
        temp = float(value or 0.0)
        return round(temp - 273.15, 2) if temp > 120 else round(temp, 2)


# Global singleton used by routes and recommendation engine.
agriculture_service = AgricultureService()
