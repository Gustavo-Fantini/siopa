"""
Serviço de recomendações inteligentes para seleção de agrotóxicos
Utiliza Machine Learning para otimizar aplicações baseado em múltiplos fatores
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
from sklearn.preprocessing import StandardScaler
import joblib
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from pathlib import Path
from loguru import logger

from app.core.config import settings
from app.core.exceptions import ModelLoadError, ValidationError
from app.services.weather_service import weather_service
from app.services.agriculture_service import agriculture_service

class PesticideRecommendationService:
    """
    Sistema de recomendações baseado em ML para otimização de agrotóxicos
    """
    
    def __init__(self):
        self.models = {
            'pesticide_selector': None,
            'dosage_calculator': None,
            'timing_optimizer': None
        }
        
        self.scalers = {}
        self.models_loaded = False
        
        # Base de dados de agrotóxicos (simplificada, por ingrediente ativo ou combinação)
        # Cada produto traz faixas "típicas" de temperatura, umidade, pressão e vento.
        self.pesticide_database = {
            'herbicidas': {
                'glifosato': {
                    'name': 'Glifosato',
                    'active_ingredient': 'glyphosate',
                    'concentration': '480g/L',
                    'dosage_range': {'min': 1.0, 'max': 4.0},
                    'restrictions': {
                        'temperature_min': 20,
                        'temperature_max': 35,
                        'humidity_min': 40,
                        'humidity_max': 70,
                        'pressure_min': 990,
                        'pressure_max': 1020,
                        'wind_max': 10,
                    }
                },
                '2_4_d': {
                    'name': '2,4-D',
                    'active_ingredient': '2,4-dichlorophenoxyacetic acid',
                    'concentration': '806g/L',
                    'dosage_range': {'min': 0.7, 'max': 1.5},
                    'restrictions': {
                        'temperature_min': 15,
                        'temperature_max': 28,
                        'humidity_min': 60,
                        'humidity_max': 95,
                        'pressure_min': 980,
                        'pressure_max': 1015,
                        'wind_max': 8,
                    }
                },
                'atrazina': {
                    'name': 'Atrazina',
                    'active_ingredient': 'atrazine',
                    'concentration': '500g/L',
                    'dosage_range': {'min': 1.5, 'max': 4.0},
                    'restrictions': {
                        'temperature_min': 18,
                        'temperature_max': 32,
                        'humidity_min': 55,
                        'humidity_max': 95,
                        'pressure_min': 980,
                        'pressure_max': 1015,
                        'wind_max': 10,
                    }
                },
                'paraquate': {
                    'name': 'Paraquate',
                    'active_ingredient': 'paraquat',
                    'concentration': '200g/L',
                    'dosage_range': {'min': 1.0, 'max': 2.5},
                    'restrictions': {
                        'temperature_min': 15,
                        'temperature_max': 28,
                        'humidity_min': 60,
                        'humidity_max': 95,
                        'pressure_min': 980,
                        'pressure_max': 1015,
                        'wind_max': 8,
                    }
                },
                'dicamba': {
                    'name': 'Dicamba',
                    'active_ingredient': 'dicamba',
                    'concentration': '480g/L',
                    'dosage_range': {'min': 0.4, 'max': 0.8},
                    'restrictions': {
                        'temperature_min': 15,
                        'temperature_max': 28,
                        'humidity_min': 60,
                        'humidity_max': 95,
                        'pressure_min': 980,
                        'pressure_max': 1015,
                        'wind_max': 8,
                    }
                },
                'glufosinato': {
                    'name': 'Glufosinato de amônio',
                    'active_ingredient': 'glufosinate-ammonium',
                    'concentration': '200g/L',
                    'dosage_range': {'min': 1.0, 'max': 2.0},
                    'restrictions': {
                        'temperature_min': 18,
                        'temperature_max': 30,
                        'humidity_min': 55,
                        'humidity_max': 95,
                        'pressure_min': 980,
                        'pressure_max': 1015,
                        'wind_max': 10,
                    }
                },
                'carboxina': {
                    'name': 'Carboxina',
                    'active_ingredient': 'carboxin',
                    'concentration': '200g/L',
                    'dosage_range': {'min': 0.5, 'max': 1.0},
                    'restrictions': {
                        'temperature_min': 15,
                        'temperature_max': 28,
                        'humidity_min': 60,
                        'humidity_max': 90,
                        'pressure_min': 980,
                        'pressure_max': 1015,
                        'wind_max': 10,
                    }
                },
            },
            'inseticidas': {
                'imidacloprido': {
                    'name': 'Imidacloprido',
                    'active_ingredient': 'imidacloprid',
                    'concentration': '200g/L',
                    'dosage_range': {'min': 0.3, 'max': 0.5},
                    'restrictions': {
                        'temperature_min': 15,
                        'temperature_max': 28,
                        'humidity_min': 50,
                        'humidity_max': 80,
                        'pressure_min': 980,
                        'pressure_max': 1010,
                        'wind_max': 10,
                    }
                },
                'lambda_cialotrina': {
                    'name': 'Lambda-cialotrina',
                    'active_ingredient': 'lambda-cyhalothrin',
                    'concentration': '50g/L',
                    'dosage_range': {'min': 0.02, 'max': 0.06},
                    'restrictions': {
                        'temperature_min': 20,
                        'temperature_max': 30,
                        'humidity_min': 55,
                        'humidity_max': 95,
                        'pressure_min': 980,
                        'pressure_max': 1015,
                        'wind_max': 10,
                    }
                },
                'acefato': {
                    'name': 'Acefato',
                    'active_ingredient': 'acephate',
                    'concentration': '750g/kg',
                    'dosage_range': {'min': 0.5, 'max': 1.0},
                    'restrictions': {
                        'temperature_min': 18,
                        'temperature_max': 30,
                        'humidity_min': 50,
                        'humidity_max': 80,
                        'pressure_min': 970,
                        'pressure_max': 1010,
                        'wind_max': 12,
                    }
                },
                'abamectina': {
                    'name': 'Abamectina',
                    'active_ingredient': 'abamectin',
                    'concentration': '18g/L',
                    'dosage_range': {'min': 0.1, 'max': 0.3},
                    'restrictions': {
                        'temperature_min': 30,
                        'temperature_max': 42,
                        'humidity_min': 30,
                        'humidity_max': 60,
                        'pressure_min': 1000,
                        'pressure_max': 1025,
                        'wind_max': 12,
                    }
                },
                'clorantraniliprole': {
                    'name': 'Clorantraniliprole',
                    'active_ingredient': 'chlorantraniliprole',
                    'concentration': '200g/L',
                    'dosage_range': {'min': 0.05, 'max': 0.15},
                    'restrictions': {
                        'temperature_min': 15,
                        'temperature_max': 30,
                        'humidity_min': 50,
                        'humidity_max': 85,
                        'pressure_min': 975,
                        'pressure_max': 1015,
                        'wind_max': 10,
                    }
                },
                'fipronil': {
                    'name': 'Fipronil',
                    'active_ingredient': 'fipronil',
                    'concentration': '250g/L',
                    'dosage_range': {'min': 0.05, 'max': 0.12},
                    'restrictions': {
                        'temperature_min': 20,
                        'temperature_max': 35,
                        'humidity_min': 40,
                        'humidity_max': 70,
                        'pressure_min': 990,
                        'pressure_max': 1020,
                        'wind_max': 12,
                    }
                },
                'triazofos': {
                    'name': 'Triazofós',
                    'active_ingredient': 'triazophos',
                    'concentration': '400g/L',
                    'dosage_range': {'min': 0.3, 'max': 0.6},
                    'restrictions': {
                        'temperature_min': 22,
                        'temperature_max': 38,
                        'humidity_min': 45,
                        'humidity_max': 75,
                        'pressure_min': 985,
                        'pressure_max': 1015,
                        'wind_max': 12,
                    }
                },
                'malation': {
                    'name': 'Malation',
                    'active_ingredient': 'malathion',
                    'concentration': '500g/L',
                    'dosage_range': {'min': 0.5, 'max': 1.5},
                    'restrictions': {
                        'temperature_min': 35,
                        'temperature_max': 45,
                        'humidity_min': 20,
                        'humidity_max': 50,
                        'pressure_min': 1005,
                        'pressure_max': 1025,
                        'wind_max': 12,
                    }
                },
                'emamectina_benzoato': {
                    'name': 'Emamectina benzoato',
                    'active_ingredient': 'emamectin benzoate',
                    'concentration': '50g/kg',
                    'dosage_range': {'min': 0.05, 'max': 0.15},
                    'restrictions': {
                        'temperature_min': 30,
                        'temperature_max': 42,
                        'humidity_min': 30,
                        'humidity_max': 60,
                        'pressure_min': 1000,
                        'pressure_max': 1020,
                        'wind_max': 12,
                    }
                },
                'cipermetrina': {
                    'name': 'Cipermetrina',
                    'active_ingredient': 'cypermethrin',
                    'concentration': '250g/L',
                    'dosage_range': {'min': 0.05, 'max': 0.15},
                    'restrictions': {
                        'temperature_min': 18,
                        'temperature_max': 32,
                        'humidity_min': 50,
                        'humidity_max': 80,
                        'pressure_min': 985,
                        'pressure_max': 1015,
                        'wind_max': 10,
                    }
                },
                'bifentrina': {
                    'name': 'Bifentrina',
                    'active_ingredient': 'bifenthrin',
                    'concentration': '200g/L',
                    'dosage_range': {'min': 0.05, 'max': 0.15},
                    'restrictions': {
                        'temperature_min': 20,
                        'temperature_max': 35,
                        'humidity_min': 40,
                        'humidity_max': 70,
                        'pressure_min': 990,
                        'pressure_max': 1020,
                        'wind_max': 12,
                    }
                },
                'indoxacarbe': {
                    'name': 'Indoxacarbe',
                    'active_ingredient': 'indoxacarb',
                    'concentration': '300g/kg',
                    'dosage_range': {'min': 0.05, 'max': 0.15},
                    'restrictions': {
                        'temperature_min': 20,
                        'temperature_max': 35,
                        'humidity_min': 50,
                        'humidity_max': 80,
                        'pressure_min': 980,
                        'pressure_max': 1015,
                        'wind_max': 12,
                    }
                },
                'spinosade': {
                    'name': 'Spinosade',
                    'active_ingredient': 'spinosad',
                    'concentration': '480g/L',
                    'dosage_range': {'min': 0.05, 'max': 0.12},
                    'restrictions': {
                        'temperature_min': 22,
                        'temperature_max': 35,
                        'humidity_min': 50,
                        'humidity_max': 80,
                        'pressure_min': 980,
                        'pressure_max': 1015,
                        'wind_max': 10,
                    }
                },
                'espinetoram': {
                    'name': 'Espinetoram',
                    'active_ingredient': 'spinetoram',
                    'concentration': '250g/L',
                    'dosage_range': {'min': 0.05, 'max': 0.15},
                    'restrictions': {
                        'temperature_min': 25,
                        'temperature_max': 38,
                        'humidity_min': 40,
                        'humidity_max': 70,
                        'pressure_min': 990,
                        'pressure_max': 1020,
                        'wind_max': 12,
                    }
                },
                'ciantraniliprole': {
                    'name': 'Ciantraniliprole',
                    'active_ingredient': 'cyantraniliprole',
                    'concentration': '200g/L',
                    'dosage_range': {'min': 0.05, 'max': 0.15},
                    'restrictions': {
                        'temperature_min': 20,
                        'temperature_max': 35,
                        'humidity_min': 50,
                        'humidity_max': 80,
                        'pressure_min': 985,
                        'pressure_max': 1015,
                        'wind_max': 12,
                    }
                },
                'deltametrina': {
                    'name': 'Deltametrina',
                    'active_ingredient': 'deltamethrin',
                    'concentration': '25g/L',
                    'dosage_range': {'min': 0.05, 'max': 0.15},
                    'restrictions': {
                        'temperature_min': 20,
                        'temperature_max': 35,
                        'humidity_min': 50,
                        'humidity_max': 80,
                        'pressure_min': 985,
                        'pressure_max': 1015,
                        'wind_max': 12,
                    }
                },
                'tiametoxam': {
                    'name': 'Tiametoxam',
                    'active_ingredient': 'thiamethoxam',
                    'concentration': '250g/kg',
                    'dosage_range': {'min': 0.1, 'max': 0.2},
                    'restrictions': {
                        'temperature_min': 22,
                        'temperature_max': 35,
                        'humidity_min': 40,
                        'humidity_max': 70,
                        'pressure_min': 990,
                        'pressure_max': 1020,
                        'wind_max': 12,
                    }
                },
                'clorantraniliprole_lambda': {
                    'name': 'Chlorantraniliprole + Lambda-cialotrina',
                    'active_ingredient': 'chlorantraniliprole + lambda-cyhalothrin',
                    'concentration': 'varia',
                    'dosage_range': {'min': 0.05, 'max': 0.15},
                    'restrictions': {
                        'temperature_min': 20,
                        'temperature_max': 35,
                        'humidity_min': 50,
                        'humidity_max': 80,
                        'pressure_min': 985,
                        'pressure_max': 1015,
                        'wind_max': 10,
                    }
                },
                'metomil': {
                    'name': 'Metomil',
                    'active_ingredient': 'methomyl',
                    'concentration': '215g/L',
                    'dosage_range': {'min': 0.3, 'max': 0.7},
                    'restrictions': {
                        'temperature_min': 30,
                        'temperature_max': 42,
                        'humidity_min': 30,
                        'humidity_max': 60,
                        'pressure_min': 1000,
                        'pressure_max': 1020,
                        'wind_max': 12,
                    }
                },
            },
            'fungicidas': {
                'tebuconazol': {
                    'name': 'Tebuconazol',
                    'active_ingredient': 'tebuconazole',
                    'concentration': '200g/L',
                    'dosage_range': {'min': 0.15, 'max': 0.25},
                    'restrictions': {
                        'temperature_min': 15,
                        'temperature_max': 28,
                        'humidity_min': 60,
                        'humidity_max': 90,
                        'pressure_min': 980,
                        'pressure_max': 1015,
                        'wind_max': 10,
                    }
                },
                'mancozebe': {
                    'name': 'Mancozebe',
                    'active_ingredient': 'mancozeb',
                    'concentration': '800g/kg',
                    'dosage_range': {'min': 1.5, 'max': 2.5},
                    'restrictions': {
                        'temperature_min': 10,
                        'temperature_max': 25,
                        'humidity_min': 70,
                        'humidity_max': 95,
                        'pressure_min': 980,
                        'pressure_max': 1010,
                        'wind_max': 8,
                    }
                },
                'metalaxil_m': {
                    'name': 'Metalaxil-M',
                    'active_ingredient': 'metalaxyl-M',
                    'concentration': '480g/L',
                    'dosage_range': {'min': 0.1, 'max': 0.3},
                    'restrictions': {
                        'temperature_min': 10,
                        'temperature_max': 22,
                        'humidity_min': 80,
                        'humidity_max': 100,
                        'pressure_min': 970,
                        'pressure_max': 1000,
                        'wind_max': 10,
                    }
                },
                'piraclostrobina': {
                    'name': 'Piraclostrobina',
                    'active_ingredient': 'pyraclostrobin',
                    'concentration': '250g/L',
                    'dosage_range': {'min': 0.2, 'max': 0.4},
                    'restrictions': {
                        'temperature_min': 28,
                        'temperature_max': 40,
                        'humidity_min': 40,
                        'humidity_max': 70,
                        'pressure_min': 995,
                        'pressure_max': 1020,
                        'wind_max': 10,
                    }
                },
                'protioconazol': {
                    'name': 'Protioconazol',
                    'active_ingredient': 'prothioconazole',
                    'concentration': '300g/L',
                    'dosage_range': {'min': 0.2, 'max': 0.4},
                    'restrictions': {
                        'temperature_min': 20,
                        'temperature_max': 30,
                        'humidity_min': 70,
                        'humidity_max': 95,
                        'pressure_min': 980,
                        'pressure_max': 1010,
                        'wind_max': 10,
                    }
                },
                'propiconazol': {
                    'name': 'Propiconazol',
                    'active_ingredient': 'propiconazole',
                    'concentration': '250g/L',
                    'dosage_range': {'min': 0.15, 'max': 0.3},
                    'restrictions': {
                        'temperature_min': 20,
                        'temperature_max': 30,
                        'humidity_min': 65,
                        'humidity_max': 90,
                        'pressure_min': 980,
                        'pressure_max': 1010,
                        'wind_max': 10,
                    }
                },
                'flutriafol': {
                    'name': 'Flutriafol',
                    'active_ingredient': 'flutriafol',
                    'concentration': '250g/L',
                    'dosage_range': {'min': 0.1, 'max': 0.3},
                    'restrictions': {
                        'temperature_min': 20,
                        'temperature_max': 32,
                        'humidity_min': 70,
                        'humidity_max': 95,
                        'pressure_min': 980,
                        'pressure_max': 1010,
                        'wind_max': 10,
                    }
                },
                'azoxistrobina_ciproconazol': {
                    'name': 'Azoxistrobina + Ciproconazol',
                    'active_ingredient': 'azoxystrobin + cyproconazole',
                    'concentration': 'varia',
                    'dosage_range': {'min': 0.25, 'max': 0.5},
                    'restrictions': {
                        'temperature_min': 20,
                        'temperature_max': 35,
                        'humidity_min': 60,
                        'humidity_max': 90,
                        'pressure_min': 980,
                        'pressure_max': 1015,
                        'wind_max': 10,
                    }
                },
                'fludioxonil': {
                    'name': 'Fludioxonil',
                    'active_ingredient': 'fludioxonil',
                    'concentration': '250g/L',
                    'dosage_range': {'min': 0.1, 'max': 0.3},
                    'restrictions': {
                        'temperature_min': 15,
                        'temperature_max': 28,
                        'humidity_min': 70,
                        'humidity_max': 95,
                        'pressure_min': 980,
                        'pressure_max': 1010,
                        'wind_max': 10,
                    }
                },
                'azoxistrobina_milho': {
                    'name': 'Azoxistrobina',
                    'active_ingredient': 'azoxystrobin',
                    'concentration': '250g/L',
                    'dosage_range': {'min': 0.3, 'max': 0.6},
                    'restrictions': {
                        'temperature_min': 20,
                        'temperature_max': 35,
                        'humidity_min': 60,
                        'humidity_max': 90,
                        'pressure_min': 985,
                        'pressure_max': 1015,
                        'wind_max': 10,
                    }
                },
                'tebuconazol_trifloxistrobina': {
                    'name': 'Tebuconazol + Trifloxistrobina',
                    'active_ingredient': 'tebuconazole + trifloxystrobin',
                    'concentration': 'varia',
                    'dosage_range': {'min': 0.25, 'max': 0.5},
                    'restrictions': {
                        'temperature_min': 30,
                        'temperature_max': 42,
                        'humidity_min': 30,
                        'humidity_max': 60,
                        'pressure_min': 1000,
                        'pressure_max': 1020,
                        'wind_max': 10,
                    }
                },
            },
            'biologicos': {
                'metarhizium_anisopliae': {
                    'name': 'Metarhizium anisopliae',
                    'active_ingredient': 'Metarhizium anisopliae',
                    'concentration': 'varia',
                    'dosage_range': {'min': 0.5, 'max': 1.5},
                    'restrictions': {
                        'temperature_min': 22,
                        'temperature_max': 30,
                        'humidity_min': 70,
                        'humidity_max': 100,
                        'pressure_min': 975,
                        'pressure_max': 1005,
                        'wind_max': 10,
                    }
                },
                'azadiractina': {
                    'name': 'Azadiractina',
                    'active_ingredient': 'azadirachtin',
                    'concentration': 'varia',
                    'dosage_range': {'min': 0.2, 'max': 0.6},
                    'restrictions': {
                        'temperature_min': 20,
                        'temperature_max': 30,
                        'humidity_min': 70,
                        'humidity_max': 100,
                        'pressure_min': 975,
                        'pressure_max': 1005,
                        'wind_max': 10,
                    }
                },
                'bacillus_thuringiensis': {
                    'name': 'Bacillus thuringiensis',
                    'active_ingredient': 'Bacillus thuringiensis',
                    'concentration': 'varia',
                    'dosage_range': {'min': 0.5, 'max': 1.5},
                    'restrictions': {
                        'temperature_min': 18,
                        'temperature_max': 30,
                        'humidity_min': 60,
                        'humidity_max': 90,
                        'pressure_min': 980,
                        'pressure_max': 1010,
                        'wind_max': 10,
                    }
                },
                'beauveria_bassiana': {
                    'name': 'Beauveria bassiana',
                    'active_ingredient': 'Beauveria bassiana',
                    'concentration': 'varia',
                    'dosage_range': {'min': 0.5, 'max': 1.5},
                    'restrictions': {
                        'temperature_min': 22,
                        'temperature_max': 30,
                        'humidity_min': 75,
                        'humidity_max': 100,
                        'pressure_min': 975,
                        'pressure_max': 1005,
                        'wind_max': 10,
                    }
                },
            }
        }
    
    def load_models(self) -> bool:
        """Carrega ou treina os modelos de ML"""
        try:
            logger.info("Carregando modelos de recomendação...")
            
            model_path = Path(settings.MODEL_PATH)
            
            if self._load_existing_models(model_path):
                self.models_loaded = True
                logger.info("Modelos carregados com sucesso")
                return True
            
            logger.info("Treinando novos modelos...")
            self._train_models()
            self._save_models(model_path)
            
            self.models_loaded = True
            logger.info("Modelos treinados e salvos com sucesso")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao carregar modelos: {e}")
            raise ModelLoadError(f"Falha no carregamento dos modelos: {str(e)}")
    
    def _load_existing_models(self, model_path: Path) -> bool:
        """Carrega modelos existentes do disco"""
        try:
            model_files = {
                'pesticide_selector': model_path / 'pesticide_selector.joblib',
                'dosage_calculator': model_path / 'dosage_calculator.joblib',
                'timing_optimizer': model_path / 'timing_optimizer.joblib'
            }
            
            if not all(f.exists() for f in model_files.values()):
                return False
            
            for name, file_path in model_files.items():
                self.models[name] = joblib.load(file_path)
            
            scaler_path = model_path / 'feature_scaler.joblib'
            if scaler_path.exists():
                self.scalers['features'] = joblib.load(scaler_path)
            
            return True
            
        except Exception as e:
            logger.warning(f"Erro ao carregar modelos existentes: {e}")
            return False
    
    def _train_models(self):
        """Treina novos modelos com dados sintéticos"""
        try:
            X, y_pesticide, y_dosage, y_timing = self._generate_synthetic_dataset()
            X_scaled = self._prepare_features(X)
            
            # Treina modelo seletor de pesticidas
            self.models['pesticide_selector'] = RandomForestClassifier(n_estimators=100, random_state=42)
            self.models['pesticide_selector'].fit(X_scaled, y_pesticide)
            
            # Treina modelo calculador de dosagem
            self.models['dosage_calculator'] = RandomForestRegressor(n_estimators=100, random_state=42)
            self.models['dosage_calculator'].fit(X_scaled, y_dosage)
            
            # Treina modelo otimizador de tempo
            self.models['timing_optimizer'] = RandomForestClassifier(n_estimators=100, random_state=42)
            self.models['timing_optimizer'].fit(X_scaled, y_timing)
            
            logger.info("Modelos treinados com sucesso")
            
        except Exception as e:
            logger.error(f"Erro no treinamento: {e}")
            raise ModelLoadError(f"Falha no treinamento dos modelos: {str(e)}")
    
    def _generate_synthetic_dataset(self):
        """Gera dataset sintético baseado em conhecimento agronômico"""
        np.random.seed(42)
        n_samples = 5000
        
        data = {
            'temperature': np.clip(np.random.normal(25, 8, n_samples), 10, 45),
            'humidity': np.clip(np.random.normal(70, 15, n_samples), 30, 100),
            'wind_speed': np.clip(np.random.exponential(8, n_samples), 0, 25),
            'pest_pressure': np.random.uniform(0, 10, n_samples),
            'disease_pressure': np.random.uniform(0, 10, n_samples),
            'weed_pressure': np.random.uniform(0, 10, n_samples),
            'coverage_quality': np.random.uniform(50, 100, n_samples)
        }
        
        X = pd.DataFrame(data)
        
        # Gera labels baseado em regras
        y_pesticide = []
        y_dosage = []
        y_timing = []
        
        for _, row in X.iterrows():
            # Seleção de pesticida
            if row['weed_pressure'] > 7:
                pesticide = 'glifosato'
                dosage = 2.5
            elif row['pest_pressure'] > 7:
                pesticide = 'imidacloprido'
                dosage = 0.4
            else:
                pesticide = 'azoxistrobina'
                dosage = 0.4
            
            # Ajuste de dosagem
            if row['temperature'] > 30:
                dosage *= 0.9
            if row['coverage_quality'] < 70:
                dosage *= 1.2
            
            # Timing
            if row['temperature'] > 30 or row['wind_speed'] > 15:
                timing = 0  # Manhã
            else:
                timing = np.random.choice([0, 1, 2])
            
            y_pesticide.append(pesticide)
            y_dosage.append(dosage)
            y_timing.append(timing)
        
        return X, np.array(y_pesticide), np.array(y_dosage), np.array(y_timing)
    
    def _prepare_features(self, X: pd.DataFrame) -> np.ndarray:
        """Prepara features para treinamento/predição"""
        if 'features' not in self.scalers:
            self.scalers['features'] = StandardScaler()
            X_scaled = self.scalers['features'].fit_transform(X)
        else:
            X_scaled = self.scalers['features'].transform(X)
        
        return X_scaled
    
    def _save_models(self, model_path: Path):
        """Salva modelos treinados"""
        try:
            model_path.mkdir(parents=True, exist_ok=True)
            
            for name, model in self.models.items():
                joblib.dump(model, model_path / f'{name}.joblib')
            
            if 'features' in self.scalers:
                joblib.dump(self.scalers['features'], model_path / 'feature_scaler.joblib')
            
            logger.info("Modelos salvos com sucesso")
            
        except Exception as e:
            logger.error(f"Erro ao salvar modelos: {e}")
    
    async def get_pesticide_recommendation(self, analysis_results: Dict, latitude: float, 
                                         longitude: float, crop_type: str, growth_stage: Optional[str] = None) -> Dict:
        """Gera recomendação completa de pesticida"""
        try:
            if not self.models_loaded:
                self.load_models()
            
            logger.info("Gerando recomendação de pesticida...")
            
            # Obtém dados contextuais
            weather_data = await weather_service.get_current_weather(latitude, longitude)
            crop_info = await agriculture_service.get_crop_info(crop_type)
            
            temperature = weather_data.get('temperature', 25)
            humidity = weather_data.get('humidity', 70)
            wind_speed = weather_data.get('wind_speed', 8)
            pressure = weather_data.get('pressure', 1013)
            coverage = analysis_results.get('coverage_percentage', 75)
            density = analysis_results.get('density_per_cm2', 0)
            cv = analysis_results.get('cv_coefficient', 0)

            pressures = self._estimate_pressures(
                crop_type=crop_type,
                growth_stage=growth_stage,
                coverage=coverage,
                density=density,
                cv=cv,
                temperature=temperature,
                humidity=humidity,
                wind_speed=wind_speed
            )

            logger.info(f"Pressões calculadas: {pressures}")

            # Prepara features
            features = pd.DataFrame([{
                'temperature': temperature,
                'humidity': humidity,
                'wind_speed': wind_speed,
                'pest_pressure': pressures['pest_pressure'],
                'disease_pressure': pressures['disease_pressure'],
                'weed_pressure': pressures['weed_pressure'],
                'coverage_quality': coverage
            }])
            
            X_scaled = self._prepare_features(features)
            
            # Faz predições do modelo (apoio)
            ml_pesticide = self.models['pesticide_selector'].predict(X_scaled)[0]
            dosage = float(self.models['dosage_calculator'].predict(X_scaled)[0])
            timing = self.models['timing_optimizer'].predict(X_scaled)[0]
            ml_confidence = np.max(self.models['pesticide_selector'].predict_proba(X_scaled)[0])

            # Escolha principal do produto: baseada nas pressões e cultura/estágio,
            # usando a predição do modelo apenas como sugestão secundária.
            pesticide = self._select_pesticide_by_pressures(
                pressures=pressures,
                crop_type=crop_type,
                growth_stage=growth_stage,
                ml_suggestion=str(ml_pesticide),
            )

            logger.info(f"Pesticida selecionado (após regras): {pesticide}")

            pesticide_info = self._get_pesticide_info(pesticide)
            dosage = self._adjust_dosage(dosage, coverage, pesticide_info)

            # Avalia se as condições climáticas atuais respeitam as restrições do produto
            pesticide_weather = self._evaluate_pesticide_weather(
                pesticide_info=pesticide_info,
                temperature=temperature,
                humidity=humidity,
                wind_speed=wind_speed,
                pressure=pressure,
            )

            # Se as condições forem ruins para o produto escolhido, tenta encontrar
            # outro da mesma categoria que se encaixe melhor nas condições atuais.
            if pesticide_weather.get('rating') == 'poor':
                category_name = self._find_pesticide_category(pesticide)
                if category_name:
                    better_name, better_info, better_weather = self._find_better_pesticide_for_weather(
                        category=category_name,
                        exclude=pesticide,
                        temperature=temperature,
                        humidity=humidity,
                        wind_speed=wind_speed,
                        pressure=pressure,
                    )
                    if better_name:
                        logger.info(
                            f"Trocando pesticida '{pesticide}' por '{better_name}' devido às condições climáticas atuais"
                        )
                        pesticide = better_name
                        pesticide_info = better_info
                        pesticide_weather = better_weather
                        dosage = self._adjust_dosage(dosage, coverage, pesticide_info)
            
            # Confiança: combinamos a confiança do modelo com a intensidade das pressões
            dominant_pressure_value = max(pressures.values()) if pressures else 0.0
            rule_conf = min(1.0, dominant_pressure_value / 10.0)
            confidence = (ml_confidence * 0.6) + (rule_conf * 0.4)

            # Recomendações gerais baseadas em clima e análise de gotículas
            base_recommendations = self._generate_recommendations(weather_data, analysis_results)

            # Complementa recomendações com avaliação climática específica do pesticida
            pesticide_rating = pesticide_weather.get('rating', 'unknown')
            pesticide_issues = pesticide_weather.get('issues', []) or []

            if pesticide_rating == 'ideal':
                base_recommendations.append(
                    "Condições climáticas consideradas ideais para o produto recomendado (segundo faixas de temperatura, umidade, pressão e vento)."
                )
            elif pesticide_rating == 'caution':
                base_recommendations.append(
                    "Condições climáticas apenas marginais para o produto recomendado - avaliar ajuste de horário ou considerar outro produto compatível com o clima atual."
                )
                if pesticide_issues:
                    base_recommendations.extend(
                        [f"• {issue}" for issue in pesticide_issues]
                    )
            elif pesticide_rating == 'poor':
                base_recommendations.append(
                    "Condições climáticas inadequadas para o produto recomendado - **não é recomendada a aplicação nestas condições**."
                )
                if pesticide_issues:
                    base_recommendations.extend(
                        [f"• {issue}" for issue in pesticide_issues]
                    )

            # Define adequação climática geral combinando clima e produto
            overall_weather = weather_data.get('spray_conditions', {}).get('overall_rating', 'unknown')
            pesticide_rating = pesticide_weather.get('rating', 'unknown')

            # Se o produto estiver ruim ou no limite, isso deve se sobrepor ao rating geral
            if pesticide_rating == 'poor':
                combined_weather = 'poor'
            elif pesticide_rating == 'caution':
                combined_weather = 'caution'
            else:
                combined_weather = overall_weather

            # Atualiza também o campo usado pelo front antigo, para manter compatibilidade
            try:
                if 'spray_conditions' not in weather_data:
                    weather_data['spray_conditions'] = {}
                weather_data['spray_conditions']['overall_rating'] = combined_weather
            except Exception:
                # Se por algum motivo não conseguir atualizar, segue apenas com combined_weather na aplicação
                pass

            # Gera recomendação final
            recommendation = {
                'pesticide': {
                    'name': pesticide_info.get('name', pesticide),
                    'active_ingredient': pesticide_info.get('active_ingredient', 'N/A'),
                    'concentration': pesticide_info.get('concentration', 'N/A')
                },
                'dosage': {
                    'recommended': round(dosage, 2),
                    'unit': 'L/ha',
                    'range': pesticide_info.get('dosage_range', {'min': 0.5, 'max': 2.0})
                },
                'application': {
                    'timing': self._get_timing_text(timing),
                    'weather_suitability': combined_weather,
                    'pesticide_weather_suitability': pesticide_weather
                },
                'confidence': round(confidence * 100, 1),
                'recommendations': base_recommendations,
                'timestamp': datetime.now().isoformat()
            }
            
            logger.info("Recomendação gerada com sucesso")
            return recommendation
            
        except Exception as e:
            logger.error(f"Erro na geração de recomendação: {e}")
            raise ValidationError(f"Falha na geração de recomendação: {str(e)}")

    def _evaluate_pesticide_weather(
        self,
        pesticide_info: Dict,
        temperature: float,
        humidity: float,
        wind_speed: float,
        pressure: float,
    ) -> Dict:
        """Compara condições atuais com as restrições climáticas do pesticida.

        Usa os campos em `restrictions` (temperature_max, humidity_min, wind_max).
        Retorna um pequeno resumo com rating e avisos que podem ser mostrados
        na interface.
        """

        try:
            restrictions = pesticide_info.get('restrictions', {}) or {}

            temp_max = float(restrictions.get('temperature_max', 30.0))
            temp_min = float(restrictions.get('temperature_min', 15.0))
            hum_min = float(restrictions.get('humidity_min', 50.0))
            hum_max = float(restrictions.get('humidity_max', 95.0))
            wind_max = float(restrictions.get('wind_max', 12.0))
            pres_min = float(restrictions.get('pressure_min', 970.0))
            pres_max = float(restrictions.get('pressure_max', 1030.0))

            # Margens internas para diferenciar IDEAL de ATENÇÃO.
            # Qualquer valor fora dos limites min/max é considerado "poor".
            # Dentro da faixa, se estiver muito próximo das bordas vira "caution".
            margin_temp = 1.0   # °C
            margin_hum = 5.0    # % UR
            margin_pres = 3.0   # hPa
            margin_wind = 1.0   # km/h

            issues: List[str] = []

            if temperature > temp_max:
                issues.append(
                    f"Temperatura atual ({temperature:.1f}°C) acima do máximo recomendado para este produto ({temp_max:.1f}°C)."
                )
            if temperature < temp_min:
                issues.append(
                    f"Temperatura atual ({temperature:.1f}°C) abaixo do mínimo recomendado para este produto ({temp_min:.1f}°C)."
                )

            if humidity < hum_min:
                issues.append(
                    f"Umidade relativa baixa ({humidity:.0f}%) para este produto (mínimo recomendado {hum_min:.0f}%)."
                )
            if humidity > hum_max:
                issues.append(
                    f"Umidade relativa muito alta ({humidity:.0f}%) - risco de escorrimento com este produto."
                )

            if wind_speed > wind_max:
                issues.append(
                    f"Velocidade do vento elevada ({wind_speed:.1f} km/h) acima do limite recomendado ({wind_max:.1f} km/h)."
                )

            if pressure < pres_min or pressure > pres_max:
                issues.append(
                    f"Pressão atmosférica atual ({pressure:.0f} hPa) fora da faixa típica para melhor desempenho deste produto ({pres_min:.0f}–{pres_max:.0f} hPa)."
                )

            # Determina rating de forma mais restritiva, sem extrapolar.

            # Qualquer valor fora dos limites declarados do produto -> "poor".
            outside_main_range = (
                temperature < temp_min or temperature > temp_max or
                humidity < hum_min or humidity > hum_max or
                wind_speed > wind_max or
                pressure < pres_min or pressure > pres_max
            )

            if outside_main_range:
                rating = 'poor'
                if not issues:
                    issues.append(
                        'Condições climáticas fora da faixa recomendada em rótulo/bula para este produto.'
                    )
                summary = 'Condições inadequadas para este produto - considerar outro produto ou adiar a aplicação.'
            else:
                # Está dentro da faixa; verifica se está muito perto das bordas.
                near_temp_edge = (
                    (temperature - temp_min) <= margin_temp or
                    (temp_max - temperature) <= margin_temp
                )
                near_hum_edge = (
                    (humidity - hum_min) <= margin_hum or
                    (hum_max - humidity) <= margin_hum
                )
                near_pres_edge = (
                    (pressure - pres_min) <= margin_pres or
                    (pres_max - pressure) <= margin_pres
                )
                near_wind_edge = (wind_max - wind_speed) <= margin_wind

                if near_temp_edge or near_hum_edge or near_pres_edge or near_wind_edge:
                    rating = 'caution'
                    summary = 'Condições aceitáveis porém no limite para este produto (ATENÇÃO).'
                else:
                    rating = 'ideal'
                    summary = 'Condições climáticas ideais para este produto.'

            return {
                'rating': rating,
                'summary': summary,
                'issues': issues,
                'limits': {
                    'temperature_min': temp_min,
                    'temperature_max': temp_max,
                    'humidity_min': hum_min,
                    'humidity_max': hum_max,
                    'wind_max': wind_max,
                    'pressure_min': pres_min,
                    'pressure_max': pres_max,
                },
            }

        except Exception as e:
            logger.warning(f"Falha ao avaliar condições climáticas do pesticida: {e}")
            return {
                'rating': 'unknown',
                'summary': 'Não foi possível avaliar as condições climáticas específicas do produto.',
                'issues': [str(e)],
            }

    def _find_pesticide_category(self, pesticide_name: str) -> Optional[str]:
        """Retorna o nome da categoria (herbicidas, inseticidas, fungicidas) de um pesticida."""
        for category_name, category in self.pesticide_database.items():
            if pesticide_name in category:
                return category_name
        return None

    def _find_better_pesticide_for_weather(
        self,
        category: str,
        exclude: str,
        temperature: float,
        humidity: float,
        wind_speed: float,
        pressure: float,
    ) -> Tuple[Optional[str], Optional[Dict], Optional[Dict]]:
        """Procura, dentro de uma categoria, um pesticida com rating climático melhor.

        Prioriza produtos com rating 'ideal'; se não houver, tenta 'caution'.
        Retorna (nome, info, avaliação_clima) ou (None, None, None) se não achar.
        """

        try:
            category_dict = self.pesticide_database.get(category, {}) or {}
            ideal_candidate = None
            ideal_info = None
            ideal_weather = None

            caution_candidate = None
            caution_info = None
            caution_weather = None

            for name, info in category_dict.items():
                if name == exclude:
                    continue

                weather_eval = self._evaluate_pesticide_weather(
                    pesticide_info=info,
                    temperature=temperature,
                    humidity=humidity,
                    wind_speed=wind_speed,
                    pressure=pressure,
                )

                rating = weather_eval.get('rating', 'unknown')

                if rating == 'ideal' and ideal_candidate is None:
                    ideal_candidate = name
                    ideal_info = info
                    ideal_weather = weather_eval
                elif rating == 'caution' and caution_candidate is None:
                    caution_candidate = name
                    caution_info = info
                    caution_weather = weather_eval

            if ideal_candidate:
                return ideal_candidate, ideal_info, ideal_weather
            if caution_candidate:
                return caution_candidate, caution_info, caution_weather

            return None, None, None

        except Exception as e:
            logger.warning(f"Falha ao buscar pesticida alternativo para clima: {e}")
            return None, None, None
    
    def _get_pesticide_info(self, pesticide_name: str) -> Dict:
        """Obtém informações detalhadas do pesticida"""
        for category in self.pesticide_database.values():
            if pesticide_name in category:
                return category[pesticide_name]
        
        return {
            'name': pesticide_name,
            'dosage_range': {'min': 0.5, 'max': 2.0},
            'restrictions': {'wind_max': 10, 'temperature_max': 30, 'humidity_min': 60}
        }
    
    def _estimate_pressures(
        self,
        crop_type: str,
        growth_stage: Optional[str],
        coverage: float,
        density: float,
        cv: float,
        temperature: float,
        humidity: float,
        wind_speed: float
    ) -> Dict[str, float]:
        """Estima pressões de pragas, doenças e plantas daninhas.

        Esta função é totalmente baseada em regras e foi pensada para ser fácil
        de ajustar/ampliar depois. Você pode mudar limiares e pesos sem tocar
        no restante do pipeline.
        """

        # Normaliza alguns valores básicos
        coverage = max(0.0, min(100.0, coverage or 0.0))
        density = max(0.0, float(density or 0.0))
        cv = max(0.0, float(cv or 0.0))

        crop_type_lower = (crop_type or "").lower()
        growth_stage_lower = (growth_stage or "").lower()

        # Pressão base por cultura (pode ser expandido depois)
        base_pest = 4.0
        base_disease = 4.0
        base_weed = 4.0

        if crop_type_lower == 'soja':
            base_pest += 1.0
            base_disease += 1.0
        elif crop_type_lower == 'milho':
            base_pest += 0.5
        elif crop_type_lower == 'algodao':
            base_pest += 1.5
        elif crop_type_lower == 'cana':
            base_weed += 1.0

        # Ajustes por estágio de crescimento (fortes para diferenciar bem)
        if growth_stage_lower in ['germinação', 'germinacao']:
            # Fase inicial: maior foco em mato
            base_weed += 2.5
            base_pest += 0.5
        elif growth_stage_lower == 'vegetativo':
            # Crescimento vegetativo: ataque de pragas e competição com mato
            base_pest += 2.0
            base_weed += 1.2
        elif growth_stage_lower == 'floração' or growth_stage_lower == 'floracao':
            # Floração: doenças foliares ganham muito peso
            base_disease += 3.0
            base_pest += 0.5
        elif growth_stage_lower in ['enchimento_grãos', 'enchimento_graos']:
            # Enchimento de grãos: ainda foco em doenças
            base_disease += 2.0
        elif growth_stage_lower == 'maturação' or growth_stage_lower == 'maturacao':
            # Maturação: menor foco geral, mas ainda alguma doença
            base_disease += 1.0

        # Efeito da qualidade de cobertura (baixa cobertura => maior pressão)
        # Também reforça mais mato/pragas em vegetativo e doenças em floração.
        # Ajustado para não saturar tão facilmente em 10.
        if coverage < 25:
            coverage_factor = 1.8
        elif coverage < 50:
            coverage_factor = 1.4
        elif coverage < 70:
            coverage_factor = 1.1
        else:
            coverage_factor = 0.9

        # Efeito da uniformidade (CV alto => maior risco)
        if cv > 25:
            cv_factor = 1.4
        elif cv > 15:
            cv_factor = 1.2
        else:
            cv_factor = 1.0

        # Efeito da densidade de gotas (baixa densidade => maior pressão)
        if density < 20:
            density_factor = 1.6
        elif density < 40:
            density_factor = 1.3
        else:
            density_factor = 1.0

        # Clima favorecendo doenças (quente e úmido)
        disease_climate_bonus = 0.0
        if 20 <= temperature <= 30 and humidity >= 70:
            disease_climate_bonus = 1.5
        elif humidity >= 80:
            disease_climate_bonus = 1.0

        # Clima favorecendo pragas (quente e seco)
        pest_climate_bonus = 0.0
        if temperature >= 28 and humidity <= 50:
            pest_climate_bonus = 0.8

        # Vento alto pode aumentar deriva e falha de controle
        wind_factor = 0.0
        if wind_speed > 15:
            wind_factor = 1.0
        elif wind_speed > 10:
            wind_factor = 0.5

        pest_raw = (base_pest * coverage_factor * cv_factor * density_factor) + pest_climate_bonus + wind_factor
        disease_raw = (base_disease * coverage_factor * cv_factor) + disease_climate_bonus
        weed_raw = (base_weed * coverage_factor * density_factor)

        # Normalização suave para manter valores típicos entre ~3 e 8
        pest_pressure = max(0.0, min(10.0, pest_raw * 0.8))
        disease_pressure = max(0.0, min(10.0, disease_raw * 0.8))
        weed_pressure = max(0.0, min(10.0, weed_raw * 0.8))

        return {
            'pest_pressure': float(round(pest_pressure, 2)),
            'disease_pressure': float(round(disease_pressure, 2)),
            'weed_pressure': float(round(weed_pressure, 2))
        }

    def _select_pesticide_by_pressures(
        self,
        pressures: Dict[str, float],
        crop_type: str,
        growth_stage: Optional[str],
        ml_suggestion: Optional[str] = None,
    ) -> str:
        """Escolhe o pesticida principalmente pelas pressões calculadas.

        Regras gerais (refinadas para usar melhor a base atual):
        - Pressão dominante < 4.0: usa sugestão do modelo ou um fungicida leve
          (já que a análise principal é de cobertura/gotículas).
        - Dominante weed: prioriza herbicidas específicos por cultura.
        - Dominante pest: escolhe inseticidas por cultura/estágio, evitando usar
          sempre o mesmo produto.
        - Dominante disease: escolhe fungicidas por cultura.
        """

        if not pressures:
            return ml_suggestion or 'azoxistrobina'

        dominant_key = max(pressures, key=pressures.get)
        dominant_value = pressures[dominant_key]

        crop_type_lower = (crop_type or '').lower()
        stage_lower = (growth_stage or '').lower()

        # Baixa pressão geral: deixar o modelo decidir ou cair em um produto
        # de menor impacto (fungicida leve)
        if dominant_value < 4.0:
            if ml_suggestion and ml_suggestion in self._all_pesticide_keys():
                return ml_suggestion
            # fallback suave por cultura
            if crop_type_lower in ['soja']:
                return 'protioconazol'
            if crop_type_lower in ['milho']:
                return 'azoxistrobina_milho'
            if crop_type_lower in ['algodao']:
                return 'tebuconazol'
            if crop_type_lower in ['cana']:
                return 'flutriafol'
            return 'azoxistrobina_milho'

        # Alta pressão de plantas daninhas (herbicidas)
        if dominant_key == 'weed_pressure':
            if crop_type_lower in ['soja', 'milho']:
                return 'glifosato'
            if crop_type_lower in ['cana']:
                return 'atrazina'
            if crop_type_lower in ['algodao']:
                return 'paraquate'
            return 'glifosato'

        # Alta pressão de pragas (pragas variam bastante com o estágio)
        if dominant_key == 'pest_pressure':
            # Estágios vegetativos: decisão entre herbicida x inseticida
            if 'vegetativo' in stage_lower:
                weed_p = pressures.get('weed_pressure', 0.0)
                pest_p = pressures.get('pest_pressure', 0.0)

                # Se o mato está quase tão crítico quanto a praga
                if weed_p >= 0.9 * pest_p and weed_p > 5.0:
                    if crop_type_lower in ['soja', 'milho']:
                        return 'glifosato'
                    if crop_type_lower in ['cana']:
                        return 'atrazina'

                # Foco em pragas de parte aérea por cultura
                if crop_type_lower == 'algodao':
                    return 'clorantraniliprole'
                if crop_type_lower == 'soja':
                    return 'bifentrina'
                if crop_type_lower == 'milho':
                    return 'espinetoram'
                if crop_type_lower == 'cana':
                    return 'fipronil'

            # Germinação: inseticidas sistêmicos de solo/semente por cultura
            if stage_lower in ['germinação', 'germinacao']:
                if crop_type_lower in ['soja', 'milho']:
                    return 'imidacloprido'
                if crop_type_lower == 'algodao':
                    return 'acefato'
                if crop_type_lower == 'cana':
                    return 'triazofos'

            # Floração / enchimento: proteção de estruturas reprodutivas
            if stage_lower in ['floração', 'floracao', 'enchimento_grãos', 'enchimento_graos']:
                if crop_type_lower == 'soja':
                    return 'lambda_cialotrina'
                if crop_type_lower == 'milho':
                    return 'clorantraniliprole_lambda'
                if crop_type_lower == 'algodao':
                    return 'emamectina_benzoato'
                if crop_type_lower == 'cana':
                    return 'ciantraniliprole'

            # Maturação: opções mais econômicas / choque
            if stage_lower in ['maturação', 'maturacao']:
                if crop_type_lower == 'algodao':
                    return 'deltametrina'
                if crop_type_lower == 'soja':
                    return 'bifentrina'
                if crop_type_lower == 'milho':
                    return 'indoxacarbe'
                if crop_type_lower == 'cana':
                    return 'fipronil'

            # Demais casos: fallback baseado em cultura
            if crop_type_lower == 'soja':
                return 'imidacloprido'
            if crop_type_lower == 'milho':
                return 'clorantraniliprole'
            if crop_type_lower == 'algodao':
                return 'clorantraniliprole'
            if crop_type_lower == 'cana':
                return 'triazofos'
            return 'imidacloprido'

        # Alta pressão de doenças (fungicidas)
        if dominant_key == 'disease_pressure':
            if crop_type_lower == 'soja':
                return 'protioconazol'
            if crop_type_lower == 'milho':
                return 'azoxistrobina_milho'
            if crop_type_lower == 'algodao':
                return 'tebuconazol'
            if crop_type_lower == 'cana':
                return 'flutriafol'
            return 'protioconazol'

        # Fallback final
        return ml_suggestion or 'protioconazol'

    def _all_pesticide_keys(self) -> List[str]:
        keys: List[str] = []
        for cat in self.pesticide_database.values():
            keys.extend(list(cat.keys()))
        return keys

    def _adjust_dosage(self, base_dosage: float, coverage: float, pesticide_info: Dict) -> float:
        """Ajusta a dosagem recomendada com base na cobertura e nos limites do produto.

        Regras principais (podem ser refinadas depois):
        - Cobertura < 25%: usa dose próxima do máximo do rótulo
        - 25% <= cobertura < 50%: aumenta dose para faixa alta
        - 50% <= cobertura < 70%: faixa intermediária
        - cobertura >= 70%: tende à dose mais econômica (próxima do mínimo)
        """

        dosage_range = pesticide_info.get('dosage_range', {'min': 0.5, 'max': 2.0})
        min_dose = float(dosage_range.get('min', 0.5))
        max_dose = float(dosage_range.get('max', 2.0))

        coverage = max(0.0, min(100.0, coverage or 0.0))

        if coverage < 25:
            target = max_dose * 0.95
        elif coverage < 50:
            target = min_dose + (max_dose - min_dose) * 0.75
        elif coverage < 70:
            target = min_dose + (max_dose - min_dose) * 0.5
        else:
            target = min_dose + (max_dose - min_dose) * 0.25

        # Combina previsão do modelo com alvo baseado em regras
        if base_dosage is None or base_dosage <= 0:
            final_dose = target
        else:
            final_dose = 0.5 * float(base_dosage) + 0.5 * target

        return max(min_dose, min(max_dose, final_dose))

    def _get_timing_text(self, timing_code: int) -> str:
        """Converte código de timing em texto"""
        timing_map = {
            0: 'Manhã (06:00-09:00)',
            1: 'Tarde (16:00-18:00)',
            2: 'Noite (19:00-22:00)'
        }
        return timing_map.get(timing_code, 'Manhã (06:00-09:00)')
    
    def _generate_recommendations(self, weather_data: Dict, analysis_results: Dict) -> List[str]:
        """Gera recomendações específicas"""
        recommendations = []
        
        temp = weather_data.get('temperature', 25)
        wind = weather_data.get('wind_speed', 8)
        coverage = analysis_results.get('coverage_percentage', 75)
        
        if temp > 30:
            recommendations.append("Temperatura alta - aplicar no início da manhã")
        
        if wind > 15:
            recommendations.append("Vento forte - aguardar condições mais calmas")
        
        # Para papéis hidrossensíveis, coberturas típicas boas ficam em ~10–20%.
        # Só emitir alerta forte quando for realmente baixa.
        if coverage < 5:
            recommendations.append("Cobertura muito baixa detectada - verificar calibração, bicos e volume de calda")
        elif coverage < 10:
            recommendations.append("Cobertura um pouco baixa - avaliar ajuste de volume, bicos ou velocidade")
        
        if not recommendations:
            recommendations.append("Condições adequadas para aplicação")
        
        return recommendations

# Instância global do serviço
recommendation_service = PesticideRecommendationService()
