"""Crop identities and sourced regional context without presumed field soil."""

from copy import deepcopy

from app.services.crop_catalog import crop_catalog, normalize_crop_name
from app.services.weather_service import utc_now, validate_coordinates


class AgricultureService:
    def get_supported_crops(self):
        return crop_catalog.list_crops()

    def _normalize_crop_key(self, crop_type):
        crop = crop_catalog.get_crop(crop_type)
        return crop['key'] if crop else normalize_crop_name(crop_type).replace(' ', '_')

    async def get_crop_info(self, crop_type, growth_stage=None, latitude=None, longitude=None):
        crop = crop_catalog.get_crop(crop_type)
        result = deepcopy(crop) if crop else {'key': self._normalize_crop_key(crop_type), 'name': str(crop_type),
                                            'scientific_name': None, 'aliases': [], 'growth_stages': [], 'sources': []}
        result['status'] = 'catalogued' if crop else 'not_catalogued'
        result['quality_profile'] = crop_catalog.quality_profile(crop_type, growth_stage)
        result['stage_recommendations'] = {'growth_stage': growth_stage, 'status': 'generic_navigation_only',
                                           'message': 'Estágio informado pelo usuário; sem prescrição fitossanitária automática.'}
        result['spray_recommendations'] = {'nozzle_type': None, 'pressure_bar': None, 'pressure': None,
                                         'volume_ha': None, 'droplet_size': None, 'status': 'requires_local_calibration',
                                         'message': 'Definir tecnologia e volume por alvo, equipamento, bula e avaliação local.'}
        result['climate_considerations'] = ['Clima regional é estimativa; medir vento e rajadas na altura da aplicação.']
        result['regional_alerts'] = []
        result['regional_profile'] = {}
        result['regional_context'] = await self._get_location_context(latitude, longitude) if latitude is not None and longitude is not None else None
        result['timestamp'] = utc_now()
        result['limitations'] = ['Reconhecer cultura não valida indicação, dose, praga ou doença.',
                                'Nomes botânicos são referências informativas; grupos comerciais podem incluir híbridos e outras espécies.']
        return result

    async def _get_location_context(self, latitude, longitude):
        validate_coordinates(latitude, longitude)
        return {'municipio': None, 'uf': None, 'regiao': None, 'bioma': None, 'agricultural_zone': None,
                'coordinates': {'latitude': latitude, 'longitude': longitude}, 'location_source': 'user_coordinates',
                'availability': 'coordinates_only', 'ibge_matched': False,
                'limitations': ['Nenhum município, bioma ou classe de solo é presumido apenas pela coordenada.']}

    async def get_soil_info(self, latitude, longitude):
        from app.services.environmental_service import environmental_service
        soil = deepcopy(await environmental_service.get_soil(latitude, longitude))
        soil['location'] = await self._get_location_context(latitude, longitude)
        soil.update(texture=None, drainage=None, fertility=None, organic_matter=None, mineral_composition=[], agromonitoring=None)
        soil['recommendations'] = {'spray_considerations': ['Amostragem local e avaliação técnica são necessárias para decisões sobre o solo.']}
        soil['timestamp'] = soil.get('fetched_at')
        return soil


agriculture_service = AgricultureService()