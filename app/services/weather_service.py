"""
Serviço de integração com APIs meteorológicas
Integra múltiplas fontes para dados de clima e condições ambientais
"""

import asyncio
import aiohttp
import requests
from typing import Dict, Optional, List, Tuple
from datetime import datetime, timedelta
import json
from loguru import logger

from app.core.config import settings
from app.core.exceptions import APIConnectionError
from app.utils.logger import log_api_call

class WeatherService:
    """
    Serviço para obtenção de dados meteorológicos de múltiplas APIs
    """
    
    def __init__(self):
        self.apis = {
            'openweather': {
                'base_url': 'https://api.openweathermap.org/data/2.5',
                'key': settings.OPENWEATHER_API_KEY,
                'enabled': bool(settings.OPENWEATHER_API_KEY)
            },
            'weatherapi': {
                'base_url': 'https://api.weatherapi.com/v1',
                'key': settings.WEATHERAPI_KEY,
                'enabled': bool(settings.WEATHERAPI_KEY)
            },
            'climatempo': {
                'base_url': 'http://apiadvisor.climatempo.com.br/api/v1',
                'key': settings.CLIMATEMPO_TOKEN,
                'enabled': bool(settings.CLIMATEMPO_TOKEN)
            }
        }
        
        # Condições ideais para pulverização
        self.ideal_conditions = {
            'temperature': {'min': 15, 'max': 30},  # °C
            'humidity': {'min': 50, 'max': 90},     # %
            'wind_speed': {'min': 3, 'max': 15},    # km/h
            'wind_direction': 'stable',              # estável
            'precipitation': 0                       # sem chuva
        }
    
    async def get_current_weather(self, latitude: float, longitude: float) -> Dict:
        """Obtém dados meteorológicos atuais com fallback mock"""
        # Tenta APIs reais primeiro, depois fallback
        try:
            return await self._get_weather_from_apis(latitude, longitude)
        except Exception as e:
            logger.warning(f"APIs meteorológicas indisponíveis ({e}), usando dados mock")
            return self._get_mock_weather_data(latitude, longitude)
    
    def _get_mock_weather_data(self, latitude: float, longitude: float) -> Dict:
        """Dados meteorológicos mock para desenvolvimento/teste"""
        return {
            'temperature': 25.0,
            'humidity': 65.0,
            'wind_speed': 8.5,
            'wind_direction': 180,
            'pressure': 1013.25,
            'precipitation': 0.0,
            'weather_condition': 'clear',
            'visibility': 10.0,
            'uv_index': 6,
            'location': f"Lat: {latitude:.2f}, Lon: {longitude:.2f}",
            'timestamp': datetime.now().isoformat(),
            'source': 'mock_data',
            'spray_conditions': {
                'suitable': True,
                'score': 85,
                'recommendations': ['Condições favoráveis para pulverização']
            }
        }
    
    async def _get_weather_from_apis(self, latitude: float, longitude: float) -> Dict:
        """
        Obtém dados meteorológicos atuais de múltiplas fontes
        
        Args:
            latitude: Latitude da localização
            longitude: Longitude da localização
            
        Returns:
            Dicionário com dados meteorológicos consolidados
        """
        try:
            logger.info(f"Obtendo dados meteorológicos para {latitude}, {longitude}")
            
            # Coleta dados de todas as APIs disponíveis
            weather_data = {}
            
            if self.apis['openweather']['enabled']:
                weather_data['openweather'] = await self._get_openweather_data(latitude, longitude)
            
            if self.apis['weatherapi']['enabled']:
                weather_data['weatherapi'] = await self._get_weatherapi_data(latitude, longitude)
            
            if self.apis['climatempo']['enabled']:
                weather_data['climatempo'] = await self._get_climatempo_data(latitude, longitude)
            
            # Consolida os dados
            consolidated_data = self._consolidate_weather_data(weather_data)
            
            # Adiciona análise de condições para pulverização
            consolidated_data['spray_conditions'] = self._analyze_spray_conditions(consolidated_data)
            
            logger.info("Dados meteorológicos obtidos com sucesso")
            return consolidated_data
            
        except Exception as e:
            logger.error(f"Erro ao obter dados meteorológicos: {e}")
            raise APIConnectionError(f"Falha na obtenção de dados meteorológicos: {str(e)}")
    
    async def _get_openweather_data(self, lat: float, lon: float) -> Dict:
        """Obtém dados do OpenWeatherMap"""
        try:
            url = f"{self.apis['openweather']['base_url']}/weather"
            params = {
                'lat': lat,
                'lon': lon,
                'appid': self.apis['openweather']['key'],
                'units': 'metric',
                'lang': 'pt_br'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=30) as response:
                    if response.status == 200:
                        data = await response.json()
                        log_api_call('OpenWeather', url, response.status)
                        
                        return {
                            'temperature': data['main']['temp'],
                            'humidity': data['main']['humidity'],
                            'pressure': data['main']['pressure'],
                            'wind_speed': data['wind']['speed'] * 3.6,  # m/s para km/h
                            'wind_direction': data['wind'].get('deg', 0),
                            'weather_condition': data['weather'][0]['description'],
                            'visibility': data.get('visibility', 10000) / 1000,  # metros para km
                            'timestamp': datetime.now().isoformat(),
                            'source': 'openweather'
                        }
                    else:
                        raise APIConnectionError(f"OpenWeather API retornou status {response.status}")
                        
        except Exception as e:
            logger.warning(f"Erro na API OpenWeather: {e}")
            return {}
    
    async def _get_weatherapi_data(self, lat: float, lon: float) -> Dict:
        """Obtém dados do WeatherAPI"""
        try:
            url = f"{self.apis['weatherapi']['base_url']}/current.json"
            params = {
                'key': self.apis['weatherapi']['key'],
                'q': f"{lat},{lon}",
                'lang': 'pt'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=30) as response:
                    if response.status == 200:
                        data = await response.json()
                        log_api_call('WeatherAPI', url, response.status)
                        
                        current = data['current']
                        return {
                            'temperature': current['temp_c'],
                            'humidity': current['humidity'],
                            'pressure': current['pressure_mb'],
                            'wind_speed': current['wind_kph'],
                            'wind_direction': current['wind_degree'],
                            'weather_condition': current['condition']['text'],
                            'visibility': current['vis_km'],
                            'uv_index': current['uv'],
                            'timestamp': datetime.now().isoformat(),
                            'source': 'weatherapi'
                        }
                    else:
                        raise APIConnectionError(f"WeatherAPI retornou status {response.status}")
                        
        except Exception as e:
            logger.warning(f"Erro na API WeatherAPI: {e}")
            return {}
    
    async def _get_climatempo_data(self, lat: float, lon: float) -> Dict:
        """Obtém dados do Climatempo (API brasileira)"""
        try:
            # Primeiro, busca a cidade mais próxima
            search_url = f"{self.apis['climatempo']['base_url']}/locale/city"
            params = {
                'name': f"{lat},{lon}",
                'token': self.apis['climatempo']['key']
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(search_url, params=params, timeout=30) as response:
                    if response.status == 200:
                        cities = await response.json()
                        if cities:
                            city_id = cities[0]['id']
                            
                            # Obtém dados meteorológicos da cidade
                            weather_url = f"{self.apis['climatempo']['base_url']}/weather/locale/{city_id}/current"
                            weather_params = {'token': self.apis['climatempo']['key']}
                            
                            async with session.get(weather_url, params=weather_params, timeout=30) as weather_response:
                                if weather_response.status == 200:
                                    data = await weather_response.json()
                                    log_api_call('Climatempo', weather_url, weather_response.status)
                                    
                                    return {
                                        'temperature': data['data']['temperature'],
                                        'humidity': data['data']['humidity'],
                                        'pressure': data['data']['pressure'],
                                        'wind_speed': data['data']['wind_velocity'],
                                        'wind_direction': data['data']['wind_direction'],
                                        'weather_condition': data['data']['condition'],
                                        'timestamp': datetime.now().isoformat(),
                                        'source': 'climatempo'
                                    }
                        
        except Exception as e:
            logger.warning(f"Erro na API Climatempo: {e}")
            return {}
    
    def _consolidate_weather_data(self, weather_data: Dict) -> Dict:
        """
        Consolida dados de múltiplas fontes usando média ponderada
        """
        try:
            if not weather_data:
                raise APIConnectionError("Nenhum dado meteorológico disponível")
            
            # Pesos por confiabilidade da fonte
            weights = {
                'openweather': 0.4,
                'weatherapi': 0.4,
                'climatempo': 0.2
            }
            
            consolidated = {
                'temperature': 0,
                'humidity': 0,
                'pressure': 0,
                'wind_speed': 0,
                'wind_direction': 0,
                'sources': list(weather_data.keys()),
                'timestamp': datetime.now().isoformat()
            }
            
            total_weight = 0
            
            for source, data in weather_data.items():
                if data and source in weights:
                    weight = weights[source]
                    total_weight += weight
                    
                    for key in ['temperature', 'humidity', 'pressure', 'wind_speed']:
                        if key in data:
                            consolidated[key] += data[key] * weight
                    
                    # Para direção do vento, usa a mais recente
                    if 'wind_direction' in data:
                        consolidated['wind_direction'] = data['wind_direction']
                    
                    # Mantém a primeira condição meteorológica encontrada
                    if 'weather_condition' not in consolidated and 'weather_condition' in data:
                        consolidated['weather_condition'] = data['weather_condition']
            
            # Normaliza pelos pesos
            if total_weight > 0:
                for key in ['temperature', 'humidity', 'pressure', 'wind_speed']:
                    consolidated[key] = round(consolidated[key] / total_weight, 2)
            
            return consolidated
            
        except Exception as e:
            logger.error(f"Erro na consolidação de dados: {e}")
            # Retorna o primeiro conjunto de dados disponível
            for data in weather_data.values():
                if data:
                    return data
            raise APIConnectionError("Falha na consolidação de dados meteorológicos")
    
    def _analyze_spray_conditions(self, weather_data: Dict) -> Dict:
        """
        Analisa se as condições são adequadas para pulverização
        """
        try:
            conditions = {
                'overall_rating': 'unknown',
                'temperature_ok': False,
                'humidity_ok': False,
                'wind_ok': False,
                'recommendations': [],
                'risk_factors': []
            }
            
            temp = weather_data.get('temperature', 0)
            humidity = weather_data.get('humidity', 0)
            wind_speed = weather_data.get('wind_speed', 0)
            
            # Análise de temperatura
            if self.ideal_conditions['temperature']['min'] <= temp <= self.ideal_conditions['temperature']['max']:
                conditions['temperature_ok'] = True
            else:
                if temp < self.ideal_conditions['temperature']['min']:
                    conditions['risk_factors'].append("Temperatura muito baixa - risco de deriva")
                else:
                    conditions['risk_factors'].append("Temperatura muito alta - risco de evaporação")
            
            # Análise de umidade
            if self.ideal_conditions['humidity']['min'] <= humidity <= self.ideal_conditions['humidity']['max']:
                conditions['humidity_ok'] = True
            else:
                if humidity < self.ideal_conditions['humidity']['min']:
                    conditions['risk_factors'].append("Umidade baixa - risco de evaporação")
                else:
                    conditions['risk_factors'].append("Umidade alta - risco de escorrimento")
            
            # Análise de vento
            if self.ideal_conditions['wind_speed']['min'] <= wind_speed <= self.ideal_conditions['wind_speed']['max']:
                conditions['wind_ok'] = True
            else:
                if wind_speed < self.ideal_conditions['wind_speed']['min']:
                    conditions['risk_factors'].append("Vento insuficiente - risco de deriva térmica")
                else:
                    conditions['risk_factors'].append("Vento excessivo - risco de deriva")
            
            # Avaliação geral
            ok_conditions = sum([conditions['temperature_ok'], conditions['humidity_ok'], conditions['wind_ok']])
            
            if ok_conditions == 3:
                conditions['overall_rating'] = 'ideal'
                conditions['recommendations'].append("Condições ideais para pulverização")
            elif ok_conditions == 2:
                conditions['overall_rating'] = 'good'
                conditions['recommendations'].append("Condições boas - proceder com cautela")
            elif ok_conditions == 1:
                conditions['overall_rating'] = 'caution'
                conditions['recommendations'].append("Condições marginais - considerar adiamento")
            else:
                conditions['overall_rating'] = 'poor'
                conditions['recommendations'].append("Condições inadequadas - não recomendado")
            
            # Recomendações específicas
            if not conditions['wind_ok'] and wind_speed > self.ideal_conditions['wind_speed']['max']:
                conditions['recommendations'].append("Aguardar redução da velocidade do vento")
            
            if not conditions['temperature_ok'] and temp > self.ideal_conditions['temperature']['max']:
                conditions['recommendations'].append("Aplicar no início da manhã ou final da tarde")
            
            if not conditions['humidity_ok'] and humidity < self.ideal_conditions['humidity']['min']:
                conditions['recommendations'].append("Aguardar aumento da umidade relativa")
            
            return conditions
            
        except Exception as e:
            logger.error(f"Erro na análise de condições: {e}")
            return {'overall_rating': 'unknown', 'error': str(e)}
    
    async def get_weather_forecast(self, latitude: float, longitude: float, days: int = 3) -> List[Dict]:
        """Obtém previsão meteorológica com fallback mock"""
        try:
            return await self._get_forecast_from_apis(latitude, longitude, days)
        except Exception as e:
            logger.warning(f"APIs de previsão indisponíveis ({e}), usando dados mock")
            return self._get_mock_forecast_data(latitude, longitude, days)
    
    def _get_mock_forecast_data(self, latitude: float, longitude: float, days: int) -> List[Dict]:
        """Previsão mock para desenvolvimento/teste"""
        forecast = []
        for i in range(days):
            date = datetime.now() + timedelta(days=i)
            forecast.append({
                'date': date.strftime('%Y-%m-%d'),
                'temperature_max': 28.0 + (i * 2),
                'temperature_min': 18.0 + i,
                'humidity': 60.0 + (i * 5),
                'wind_speed': 7.0 + i,
                'precipitation_probability': min(20 + (i * 10), 80),
                'weather_condition': 'partly_cloudy' if i % 2 else 'clear',
                'spray_suitable': i < 2  # Primeiros 2 dias adequados
            })
        return forecast
    
    async def _get_forecast_from_apis(self, latitude: float, longitude: float, days: int) -> List[Dict]:
        """
        Obtém previsão meteorológica para os próximos dias
        """
        try:
            logger.info(f"Obtendo previsão para {days} dias")
            
            forecast_data = []
            
            if self.apis['openweather']['enabled']:
                forecast_data = await self._get_openweather_forecast(latitude, longitude, days)
            elif self.apis['weatherapi']['enabled']:
                forecast_data = await self._get_weatherapi_forecast(latitude, longitude, days)
            
            # Adiciona análise de condições para cada dia
            for day_data in forecast_data:
                day_data['spray_conditions'] = self._analyze_spray_conditions(day_data)
            
            return forecast_data
            
        except Exception as e:
            logger.error(f"Erro ao obter previsão: {e}")
            raise APIConnectionError(f"Falha na obtenção da previsão: {str(e)}")
    
    async def _get_openweather_forecast(self, lat: float, lon: float, days: int) -> List[Dict]:
        """Obtém previsão do OpenWeatherMap"""
        try:
            url = f"{self.apis['openweather']['base_url']}/forecast"
            params = {
                'lat': lat,
                'lon': lon,
                'appid': self.apis['openweather']['key'],
                'units': 'metric',
                'lang': 'pt_br'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=30) as response:
                    if response.status == 200:
                        data = await response.json()
                        log_api_call('OpenWeather Forecast', url, response.status)
                        
                        forecast = []
                        for item in data['list'][:days * 8]:  # 8 previsões por dia (3h cada)
                            forecast.append({
                                'date': item['dt_txt'],
                                'temperature': item['main']['temp'],
                                'humidity': item['main']['humidity'],
                                'pressure': item['main']['pressure'],
                                'wind_speed': item['wind']['speed'] * 3.6,
                                'wind_direction': item['wind'].get('deg', 0),
                                'weather_condition': item['weather'][0]['description'],
                                'source': 'openweather'
                            })
                        
                        return forecast
                        
        except Exception as e:
            logger.warning(f"Erro na previsão OpenWeather: {e}")
            return []
    
    async def _get_weatherapi_forecast(self, lat: float, lon: float, days: int) -> List[Dict]:
        """Obtém previsão do WeatherAPI"""
        try:
            url = f"{self.apis['weatherapi']['base_url']}/forecast.json"
            params = {
                'key': self.apis['weatherapi']['key'],
                'q': f"{lat},{lon}",
                'days': min(days, 10),  # Máximo 10 dias
                'lang': 'pt'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=30) as response:
                    if response.status == 200:
                        data = await response.json()
                        log_api_call('WeatherAPI Forecast', url, response.status)
                        
                        forecast = []
                        for day in data['forecast']['forecastday']:
                            day_data = day['day']
                            forecast.append({
                                'date': day['date'],
                                'temperature': day_data['avgtemp_c'],
                                'humidity': day_data['avghumidity'],
                                'wind_speed': day_data['maxwind_kph'],
                                'weather_condition': day_data['condition']['text'],
                                'source': 'weatherapi'
                            })
                        
                        return forecast
                        
        except Exception as e:
            logger.warning(f"Erro na previsão WeatherAPI: {e}")
            return []

# Instância global do serviço
weather_service = WeatherService()
