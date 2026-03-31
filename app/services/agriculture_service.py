"""
Serviço de integração com APIs agrícolas
Obtém informações sobre tipos de plantas, solo e minerais
"""

import asyncio
import aiohttp
import requests
from typing import Dict, Optional, List
from datetime import datetime
import json
from loguru import logger

from app.core.config import settings
from app.core.exceptions import APIConnectionError
from app.utils.logger import log_api_call

class AgricultureService:
    """
    Serviço para obtenção de dados agrícolas e de solo
    """
    
    def __init__(self):
        self.apis = {
            'ibge': {
                'base_url': settings.IBGE_API_URL,
                'enabled': True
            },
            'embrapa': {
                'base_url': 'https://www.embrapa.br/api',
                'key': settings.EMBRAPA_API_KEY,
                'enabled': bool(settings.EMBRAPA_API_KEY)
            }
        }
        
        # Base de dados de culturas e suas características
        self.crop_database = {
            'soja': {
                'name': 'Soja',
                'scientific_name': 'Glycine max',
                'growth_stages': ['germinação', 'vegetativo', 'floração', 'enchimento_grãos', 'maturação'],
                'ideal_ph': {'min': 6.0, 'max': 7.0},
                'nutrient_requirements': {
                    'nitrogen': 'alto',
                    'phosphorus': 'médio',
                    'potassium': 'alto',
                    'calcium': 'médio',
                    'magnesium': 'médio'
                },
                'common_pests': ['lagarta-da-soja', 'percevejo', 'mosca-branca'],
                'common_diseases': ['ferrugem-asiática', 'antracnose', 'mancha-alvo'],
                'spray_recommendations': {
                    'nozzle_type': 'XR110015',
                    'pressure_bar': 3.0,
                    'volume_ha': 150,
                    'droplet_size': 'média'
                }
            },
            'milho': {
                'name': 'Milho',
                'scientific_name': 'Zea mays',
                'growth_stages': ['germinação', 'vegetativo', 'pendoamento', 'espigamento', 'maturação'],
                'ideal_ph': {'min': 5.5, 'max': 7.0},
                'nutrient_requirements': {
                    'nitrogen': 'muito_alto',
                    'phosphorus': 'alto',
                    'potassium': 'alto',
                    'calcium': 'médio',
                    'magnesium': 'médio'
                },
                'common_pests': ['lagarta-do-cartucho', 'broca-do-colmo', 'cigarrinha'],
                'common_diseases': ['mancha-branca', 'ferrugem-comum', 'antracnose'],
                'spray_recommendations': {
                    'nozzle_type': 'XR11002',
                    'pressure_bar': 2.5,
                    'volume_ha': 200,
                    'droplet_size': 'grossa'
                }
            },
            'algodao': {
                'name': 'Algodão',
                'scientific_name': 'Gossypium hirsutum',
                'growth_stages': ['germinação', 'vegetativo', 'floração', 'frutificação', 'abertura_capulhos'],
                'ideal_ph': {'min': 5.8, 'max': 8.0},
                'nutrient_requirements': {
                    'nitrogen': 'alto',
                    'phosphorus': 'alto',
                    'potassium': 'muito_alto',
                    'calcium': 'alto',
                    'magnesium': 'médio'
                },
                'common_pests': ['bicudo', 'lagarta-rosada', 'pulgão'],
                'common_diseases': ['murcha-de-fusarium', 'ramulose', 'mancha-angular'],
                'spray_recommendations': {
                    'nozzle_type': 'XR110025',
                    'pressure_bar': 3.5,
                    'volume_ha': 100,
                    'droplet_size': 'fina'
                }
            },
            'cana': {
                'name': 'Cana-de-açúcar',
                'scientific_name': 'Saccharum officinarum',
                'growth_stages': ['brotação', 'perfilhamento', 'crescimento', 'maturação'],
                'ideal_ph': {'min': 5.5, 'max': 7.5},
                'nutrient_requirements': {
                    'nitrogen': 'alto',
                    'phosphorus': 'médio',
                    'potassium': 'muito_alto',
                    'calcium': 'médio',
                    'magnesium': 'baixo'
                },
                'common_pests': ['broca-da-cana', 'cigarrinha', 'sphenophorus'],
                'common_diseases': ['ferrugem', 'carvão', 'podridão-vermelha'],
                'spray_recommendations': {
                    'nozzle_type': 'XR11003',
                    'pressure_bar': 2.0,
                    'volume_ha': 300,
                    'droplet_size': 'muito_grossa'
                }
            }
        }
        
        # Base de dados de solos brasileiros
        self.soil_database = {
            'latossolo': {
                'name': 'Latossolo',
                'characteristics': {
                    'drainage': 'boa',
                    'fertility': 'baixa_media',
                    'ph_typical': 5.5,
                    'organic_matter': 'baixa',
                    'cation_exchange': 'baixa'
                },
                'minerals': ['caulinita', 'gibbsita', 'goethita', 'hematita'],
                'recommendations': {
                    'liming': 'necessária',
                    'organic_matter': 'adicionar',
                    'phosphorus': 'alta_dose'
                }
            },
            'argissolo': {
                'name': 'Argissolo',
                'characteristics': {
                    'drainage': 'moderada',
                    'fertility': 'media',
                    'ph_typical': 6.0,
                    'organic_matter': 'media',
                    'cation_exchange': 'media'
                },
                'minerals': ['caulinita', 'illita', 'montmorilonita'],
                'recommendations': {
                    'liming': 'moderada',
                    'organic_matter': 'manter',
                    'phosphorus': 'dose_media'
                }
            },
            'neossolo': {
                'name': 'Neossolo',
                'characteristics': {
                    'drainage': 'excessiva',
                    'fertility': 'baixa',
                    'ph_typical': 6.5,
                    'organic_matter': 'muito_baixa',
                    'cation_exchange': 'muito_baixa'
                },
                'minerals': ['quartzo', 'feldspato', 'mica'],
                'recommendations': {
                    'liming': 'cuidadosa',
                    'organic_matter': 'essencial',
                    'phosphorus': 'parcelada'
                }
            }
        }
    
    def get_supported_crops(self) -> List[Dict]:
        """
        Retorna a lista de culturas suportadas para a interface web/mobile.
        """
        return [
            {
                "key": key,
                "name": value["name"],
                "scientific_name": value["scientific_name"],
                "growth_stages": value["growth_stages"],
            }
            for key, value in self.crop_database.items()
        ]

    async def get_crop_info(self, crop_type: str, growth_stage: str = None) -> Dict:
        """
        Obtém informações detalhadas sobre uma cultura
        
        Args:
            crop_type: Tipo da cultura (soja, milho, etc.)
            growth_stage: Estágio de crescimento atual
            
        Returns:
            Dicionário com informações da cultura
        """
        try:
            logger.info(f"Obtendo informações da cultura: {crop_type}")
            
            crop_type_lower = crop_type.lower()
            
            if crop_type_lower in self.crop_database:
                crop_info = self.crop_database[crop_type_lower].copy()
                
                # Adiciona recomendações específicas para o estágio
                if growth_stage:
                    crop_info['stage_recommendations'] = self._get_stage_recommendations(
                        crop_type_lower, growth_stage
                    )
                
                # Busca informações adicionais da Embrapa se disponível
                if self.apis['embrapa']['enabled']:
                    embrapa_data = await self._get_embrapa_crop_data(crop_type)
                    if embrapa_data:
                        crop_info['embrapa_data'] = embrapa_data
                
                crop_info['timestamp'] = datetime.now().isoformat()
                
                logger.info(f"Informações da cultura {crop_type} obtidas com sucesso")
                return crop_info
            else:
                # Busca em base externa se não encontrar localmente
                external_data = await self._search_external_crop_data(crop_type)
                if external_data:
                    return external_data
                else:
                    raise APIConnectionError(f"Cultura '{crop_type}' não encontrada na base de dados")
                    
        except Exception as e:
            logger.error(f"Erro ao obter informações da cultura: {e}")
            raise APIConnectionError(f"Falha na obtenção de dados da cultura: {str(e)}")
    
    def _get_stage_recommendations(self, crop_type: str, stage: str) -> Dict:
        """
        Obtém recomendações específicas para estágio de crescimento
        """
        stage_recommendations = {
            'soja': {
                'germinação': {
                    'pesticides': ['fungicida_semente'],
                    'nutrients': ['fósforo'],
                    'spray_volume': 100
                },
                'vegetativo': {
                    'pesticides': ['herbicida_pós', 'inseticida_preventivo'],
                    'nutrients': ['nitrogênio', 'potássio'],
                    'spray_volume': 150
                },
                'floração': {
                    'pesticides': ['fungicida_preventivo', 'inseticida_percevejo'],
                    'nutrients': ['boro', 'molibdênio'],
                    'spray_volume': 150
                },
                'enchimento_grãos': {
                    'pesticides': ['fungicida_ferrugem', 'inseticida_lagarta'],
                    'nutrients': ['potássio'],
                    'spray_volume': 200
                }
            },
            'milho': {
                'germinação': {
                    'pesticides': ['fungicida_semente', 'inseticida_solo'],
                    'nutrients': ['fósforo', 'zinco'],
                    'spray_volume': 150
                },
                'vegetativo': {
                    'pesticides': ['herbicida_pós', 'inseticida_lagarta'],
                    'nutrients': ['nitrogênio'],
                    'spray_volume': 200
                },
                'pendoamento': {
                    'pesticides': ['fungicida_foliar', 'inseticida_broca'],
                    'nutrients': ['nitrogênio', 'potássio'],
                    'spray_volume': 200
                }
            }
        }
        
        return stage_recommendations.get(crop_type, {}).get(stage, {})
    
    async def get_soil_info(self, latitude: float, longitude: float) -> Dict:
        """Obtém informações de solo com fallback mock"""
        try:
            return await self._get_soil_from_apis(latitude, longitude)
        except Exception as e:
            logger.warning(f"APIs de solo indisponíveis ({e}), usando dados estimados")
            return self._get_mock_soil_info(latitude, longitude)
    
    def _get_mock_soil_info(self, latitude: float, longitude: float) -> Dict:
        """Informações de solo estimadas por região"""
        # Estimativa baseada em coordenadas brasileiras
        if -25 <= latitude <= -15:  # Região Centro-Oeste/Sudeste
            soil_type = 'Latossolo Vermelho'
            ph = 5.8
            organic_matter = 2.5
        elif -15 <= latitude <= -5:  # Região Nordeste
            soil_type = 'Argissolo'
            ph = 6.2
            organic_matter = 1.8
        else:  # Outras regiões
            soil_type = 'Latossolo Amarelo'
            ph = 5.5
            organic_matter = 2.0
        
        return {
            'location': f"Lat: {latitude:.2f}, Lon: {longitude:.2f}",
            'soil_type': soil_type,
            'ph': ph,
            'organic_matter_percent': organic_matter,
            'texture': 'argilosa',
            'drainage': 'bem_drenado',
            'fertility': 'média',
            'recommendations': {
                'ph_adjustment': 'Aplicar calcário se pH < 6.0',
                'organic_matter': 'Manter cobertura vegetal',
                'spray_considerations': 'Solo argiloso retém mais água - ajustar dosagem'
            },
            'source': 'estimated_data'
        }
    
    async def _get_soil_from_apis(self, latitude: float, longitude: float) -> Dict:
        """
        Obtém informações sobre o solo da região
        
        Args:
            latitude: Latitude da localização
            longitude: Longitude da localização
            
        Returns:
            Dicionário com informações do solo
        """
        try:
            logger.info(f"Obtendo informações de solo para {latitude}, {longitude}")
            
            # Busca informações do IBGE sobre a região
            region_info = await self._get_ibge_region_data(latitude, longitude)
            
            # Determina tipo de solo predominante baseado na região
            soil_type = self._determine_soil_type(region_info)
            
            soil_info = {
                'region_info': region_info,
                'soil_type': soil_type,
                'soil_characteristics': self.soil_database.get(soil_type, {}),
                'mineral_composition': self._get_mineral_composition(soil_type),
                'recommendations': self._get_soil_recommendations(soil_type),
                'timestamp': datetime.now().isoformat()
            }
            
            logger.info("Informações de solo obtidas com sucesso")
            return soil_info
            
        except Exception as e:
            logger.error(f"Erro ao obter informações de solo: {e}")
            raise APIConnectionError(f"Falha na obtenção de dados de solo: {str(e)}")
    
    async def _get_ibge_region_data(self, lat: float, lon: float) -> Dict:
        """
        Obtém dados regionais do IBGE
        """
        try:
            # Busca município pela coordenada
            url = f"{self.apis['ibge']['base_url']}/localidades/municipios"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=30) as response:
                    if response.status == 200:
                        municipios = await response.json()
                        
                        # Encontra município mais próximo (simplificado)
                        # Em produção, usaria algoritmo de distância geográfica
                        municipio = municipios[0] if municipios else {}
                        
                        log_api_call('IBGE', url, response.status)
                        
                        return {
                            'municipio': municipio.get('nome', 'Desconhecido'),
                            'uf': municipio.get('microrregiao', {}).get('mesorregiao', {}).get('UF', {}).get('sigla', 'BR'),
                            'regiao': municipio.get('microrregiao', {}).get('mesorregiao', {}).get('UF', {}).get('regiao', {}).get('nome', 'Brasil'),
                            'bioma': self._get_bioma_by_region(lat, lon)
                        }
                        
        except Exception as e:
            logger.warning(f"Erro ao obter dados do IBGE: {e}")
            return {'municipio': 'Desconhecido', 'uf': 'BR', 'regiao': 'Brasil'}
    
    def _get_bioma_by_region(self, lat: float, lon: float) -> str:
        """
        Determina bioma baseado nas coordenadas (simplificado)
        """
        # Simplificação baseada em coordenadas aproximadas
        if -5 <= lat <= 5 and -75 <= lon <= -45:
            return 'Amazônia'
        elif -20 <= lat <= -5 and -60 <= lon <= -35:
            return 'Cerrado'
        elif -35 <= lat <= -20 and -55 <= lon <= -35:
            return 'Mata Atlântica'
        elif -20 <= lat <= -5 and -65 <= lon <= -35:
            return 'Caatinga'
        elif -35 <= lat <= -20 and -60 <= lon <= -45:
            return 'Pantanal'
        else:
            return 'Pampa'
    
    def _determine_soil_type(self, region_info: Dict) -> str:
        """
        Determina tipo de solo baseado na região
        """
        bioma = region_info.get('bioma', 'Cerrado')
        
        # Mapeamento simplificado bioma -> solo predominante
        soil_mapping = {
            'Cerrado': 'latossolo',
            'Amazônia': 'latossolo',
            'Mata Atlântica': 'argissolo',
            'Caatinga': 'neossolo',
            'Pantanal': 'argissolo',
            'Pampa': 'argissolo'
        }
        
        return soil_mapping.get(bioma, 'latossolo')
    
    def _get_mineral_composition(self, soil_type: str) -> Dict:
        """
        Obtém composição mineral típica do solo
        """
        mineral_data = {
            'latossolo': {
                'clay_minerals': ['caulinita', 'gibbsita'],
                'iron_oxides': ['goethita', 'hematita'],
                'aluminum_content': 'alto',
                'silicon_content': 'baixo',
                'base_saturation': 'baixa'
            },
            'argissolo': {
                'clay_minerals': ['caulinita', 'illita', 'montmorilonita'],
                'iron_oxides': ['goethita'],
                'aluminum_content': 'médio',
                'silicon_content': 'médio',
                'base_saturation': 'média'
            },
            'neossolo': {
                'primary_minerals': ['quartzo', 'feldspato', 'mica'],
                'clay_minerals': ['caulinita'],
                'aluminum_content': 'baixo',
                'silicon_content': 'alto',
                'base_saturation': 'variável'
            }
        }
        
        return mineral_data.get(soil_type, {})
    
    def _get_soil_recommendations(self, soil_type: str) -> Dict:
        """
        Gera recomendações baseadas no tipo de solo
        """
        recommendations = {
            'latossolo': {
                'liming': 'Aplicar calcário para elevar pH para 6.0-6.5',
                'phosphorus': 'Usar fonte solúvel, aplicar em sulco',
                'potassium': 'Parcelar aplicação, usar sulfato de potássio',
                'organic_matter': 'Adicionar matéria orgânica regularmente',
                'spray_adjustments': {
                    'volume': 'aumentar 20% devido à alta capacidade de retenção',
                    'pressure': 'reduzir para evitar compactação'
                }
            },
            'argissolo': {
                'liming': 'Calcário em dose moderada, pH 6.0',
                'phosphorus': 'Fonte parcialmente solúvel adequada',
                'potassium': 'Aplicação normal, monitorar lixiviação',
                'organic_matter': 'Manter níveis adequados',
                'spray_adjustments': {
                    'volume': 'volume padrão adequado',
                    'pressure': 'pressão normal'
                }
            },
            'neossolo': {
                'liming': 'Calcário em pequenas doses, monitorar pH',
                'phosphorus': 'Parcelar aplicação, usar fonte solúvel',
                'potassium': 'Aplicações frequentes e pequenas',
                'organic_matter': 'Essencial para retenção de nutrientes',
                'spray_adjustments': {
                    'volume': 'reduzir volume devido à baixa retenção',
                    'pressure': 'pressão normal a alta'
                }
            }
        }
        
        return recommendations.get(soil_type, {})
    
    async def _get_embrapa_crop_data(self, crop_type: str) -> Dict:
        """
        Busca dados adicionais da Embrapa (se API disponível)
        """
        try:
            if not self.apis['embrapa']['enabled']:
                return {}
            
            # Implementação simulada - em produção usaria API real da Embrapa
            url = f"{self.apis['embrapa']['base_url']}/crops/{crop_type}"
            
            # Dados simulados baseados em conhecimento da Embrapa
            embrapa_data = {
                'varieties': self._get_crop_varieties(crop_type),
                'research_recommendations': self._get_research_recommendations(crop_type),
                'regional_adaptations': self._get_regional_adaptations(crop_type)
            }
            
            return embrapa_data
            
        except Exception as e:
            logger.warning(f"Erro ao obter dados da Embrapa: {e}")
            return {}
    
    def _get_crop_varieties(self, crop_type: str) -> List[str]:
        """
        Retorna variedades recomendadas por cultura
        """
        varieties = {
            'soja': ['BRS 232', 'CD 215', 'TMG 132', 'M 6210'],
            'milho': ['BRS 1030', 'AG 8088', 'DKB 390', '30F53'],
            'algodao': ['BRS 286', 'FM 993', 'IMA 5675', 'DP 1228'],
            'cana': ['RB92579', 'SP81-3250', 'RB867515', 'CTC4']
        }
        
        return varieties.get(crop_type, [])
    
    def _get_research_recommendations(self, crop_type: str) -> Dict:
        """
        Recomendações baseadas em pesquisa Embrapa
        """
        recommendations = {
            'soja': {
                'spacing': '45-50 cm entre fileiras',
                'seeding_rate': '12-16 sementes/metro',
                'inoculation': 'Bradyrhizobium japonicum obrigatório',
                'micronutrients': 'Mo, Co, B essenciais'
            },
            'milho': {
                'spacing': '70-90 cm entre fileiras',
                'seeding_rate': '4-6 sementes/metro',
                'nitrogen': 'Parcelar em 3 aplicações',
                'micronutrients': 'Zn crítico em solos arenosos'
            }
        }
        
        return recommendations.get(crop_type, {})
    
    def _get_regional_adaptations(self, crop_type: str) -> Dict:
        """
        Adaptações regionais recomendadas
        """
        adaptations = {
            'soja': {
                'cerrado': 'Variedades de ciclo médio, atenção à ferrugem',
                'sul': 'Variedades precoces, manejo de nematoides',
                'nordeste': 'Irrigação essencial, variedades tolerantes ao calor'
            },
            'milho': {
                'cerrado': 'Safrinha viável, atenção ao veranico',
                'sul': 'Duas safras possíveis, manejo de pragas',
                'nordeste': 'Irrigação obrigatória, variedades adaptadas'
            }
        }
        
        return adaptations.get(crop_type, {})
    
    async def _search_external_crop_data(self, crop_type: str) -> Dict:
        """
        Busca dados de cultura em fontes externas
        """
        try:
            # Implementação básica para culturas não cadastradas
            return {
                'name': crop_type.title(),
                'status': 'dados_limitados',
                'message': 'Cultura não encontrada na base local. Recomenda-se consultar agrônomo.',
                'general_recommendations': {
                    'spray_volume': 150,
                    'nozzle_type': 'XR110015',
                    'pressure_bar': 3.0
                },
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Erro na busca externa: {e}")
            return {}

# Instância global do serviço
agriculture_service = AgricultureService()
