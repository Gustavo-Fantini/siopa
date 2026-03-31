"""
Modelo de análise de imagens usando DeepLabV3+ para segmentação de gotículas
em papel microporoso (water-sensitive paper)
"""

import numpy as np
import cv2
# TensorFlow/TF Hub serão importados sob demanda em load_model() para evitar
# erros de importação quando não estiverem instalados/compatíveis
from PIL import Image, ImageEnhance
from typing import Dict, List, Tuple, Optional
import time
import json
from pathlib import Path
from loguru import logger

from app.core.exceptions import ImageProcessingError, ModelLoadError
from app.core.config import settings

class DropletAnalyzer:
    """
    Analisador de gotículas usando CNN DeepLabV3+ para segmentação semântica
    e algoritmos de visão computacional para análise quantitativa
    """
    
    def __init__(self):
        self.model = None
        self.model_loaded = False
        self.input_size = settings.IMAGE_SIZE
        
        # Parâmetros de análise
        self.min_droplet_area = 5  # pixels mínimos para considerar uma gotícula
        self.max_droplet_area = 1000  # pixels máximos
        self.overlap_threshold = 0.7  # threshold para detectar sobreposições
        self.protection_radius_factor = 2.0
        
        # Métricas de qualidade (ajustadas para papéis hidrossensíveis)
        self.quality_thresholds = {
            # Cobertura adequada costuma ficar em torno de 10–30%; abaixo de ~5% é baixa
            'min_coverage': 10.0,
            'max_cv': 15.0,        # CV máximo aceitável (para alertas mais fortes)
            'min_density': 20,     # gotículas/cm² mínimas recomendadas
            'max_density': 200     # gotículas/cm² máximas antes de possível excesso
        }
    
    def load_model(self) -> bool:
        """
        Carrega o modelo DeepLabV3+ do TensorFlow Hub
        """
        try:
            logger.info("Carregando modelo DeepLabV3+ (lazy import)...")
            # Lazy import de TensorFlow e TF Hub
            import tensorflow as tf  # noqa: F401
            import tensorflow_hub as hub

            model_url = "https://tfhub.dev/tensorflow/deeplabv3/1"
            self.model = hub.load(model_url)
            self.model_loaded = True
            logger.info("Modelo DeepLabV3+ carregado com sucesso")
            return True
        except ImportError as e:
            logger.warning(f"TensorFlow/TF Hub não disponíveis ({e}). Usando fallback OpenCV.")
            self.model = None
            self.model_loaded = False
            return False
        except Exception as e:
            logger.warning(f"Falha ao carregar modelo TF Hub ({e}). Usando fallback OpenCV.")
            self.model = None
            self.model_loaded = False
            return False
    
    def preprocess_image(self, image: np.ndarray) -> Tuple[np.ndarray, Dict]:
        """
        Pré-processamento da imagem para análise
        
        Args:
            image: Imagem original em formato numpy array
            
        Returns:
            Tuple com imagem processada e metadados
        """
        try:
            original_shape = image.shape
            
            # Conversão para RGB se necessário
            if len(image.shape) == 3 and image.shape[2] == 3:
                image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            else:
                image_rgb = image
            
            # Redimensionamento mantendo aspect ratio
            h, w = image_rgb.shape[:2]
            target_h, target_w = self.input_size
            
            scale = min(target_w/w, target_h/h)
            new_w, new_h = int(w * scale), int(h * scale)
            
            resized = cv2.resize(image_rgb, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)
            
            # Padding para atingir o tamanho alvo
            pad_w = (target_w - new_w) // 2
            pad_h = (target_h - new_h) // 2
            
            padded = np.pad(resized, 
                          ((pad_h, target_h - new_h - pad_h), 
                           (pad_w, target_w - new_w - pad_w), 
                           (0, 0)), 
                          mode='constant', constant_values=0)
            
            # Normalização
            normalized = padded.astype(np.float32) / 255.0
            
            # Melhoramento de contraste para papel hidrossensível
            enhanced = self._enhance_contrast(normalized)
            
            metadata = {
                'original_shape': original_shape,
                'scale': scale,
                'padding': (pad_h, pad_w),
                'new_size': (new_h, new_w)
            }
            
            return enhanced, metadata
            
        except Exception as e:
            logger.error(f"Erro no pré-processamento: {e}")
            raise ImageProcessingError(f"Falha no pré-processamento da imagem: {str(e)}")
    
    def _enhance_contrast(self, image: np.ndarray) -> np.ndarray:
        """
        Melhora o contraste especificamente para papel hidrossensível
        """
        try:
            # Conversão para PIL para usar ImageEnhance
            pil_image = Image.fromarray((image * 255).astype(np.uint8))
            
            # Aumento de contraste
            enhancer = ImageEnhance.Contrast(pil_image)
            enhanced = enhancer.enhance(1.3)
            
            # Aumento de nitidez
            sharpness_enhancer = ImageEnhance.Sharpness(enhanced)
            sharpened = sharpness_enhancer.enhance(1.2)
            
            # Conversão de volta para numpy
            result = np.array(sharpened).astype(np.float32) / 255.0
            
            return result
            
        except Exception as e:
            logger.warning(f"Erro no melhoramento de contraste: {e}")
            return image
    
    def segment_droplets(self, image: np.ndarray) -> np.ndarray:
        """
        Segmentação de gotículas usando DeepLabV3+
        
        Args:
            image: Imagem pré-processada
            
        Returns:
            Máscara de segmentação
        """
        try:
            if not self.model_loaded:
                self.load_model()

            if self.model_loaded and self.model is not None:
                import tensorflow as tf
                # Adiciona dimensão batch e faz inferência
                input_tensor = tf.expand_dims(image, 0)
                start_time = time.time()
                predictions = self.model(input_tensor)
                inference_time = time.time() - start_time
                logger.info(f"Tempo de inferência: {inference_time:.3f}s")
                segmentation_mask = predictions['segmentation_mask'][0]
                mask = segmentation_mask.numpy()
                processed_mask = self._postprocess_mask(mask)
                return processed_mask
            else:
                # Fallback baseado em OpenCV
                logger.info("Usando fallback OpenCV para segmentação de gotículas")
                return self._segment_with_opencv(image)
        except Exception as e:
            logger.error(f"Erro na segmentação: {e}")
            raise ImageProcessingError(f"Falha na segmentação de gotículas: {str(e)}")
    
    def _postprocess_mask(self, mask: np.ndarray) -> np.ndarray:
        """
        Pós-processamento da máscara de segmentação
        """
        try:
            # Conversão para binário
            binary_mask = (mask > 0.5).astype(np.uint8)
            
            # Operações morfológicas para limpeza
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
            
            # Remove ruído
            cleaned = cv2.morphologyEx(binary_mask, cv2.MORPH_OPEN, kernel)
            
            # Fecha pequenos buracos
            closed = cv2.morphologyEx(cleaned, cv2.MORPH_CLOSE, kernel)
            
            return closed
            
        except Exception as e:
            logger.warning(f"Erro no pós-processamento da máscara: {e}")
            return mask

    def _segment_with_opencv(self, image: np.ndarray) -> np.ndarray:
        """
        Fallback de segmentação usando operações OpenCV quando o modelo TF não está disponível.
        """
        try:
            # A imagem aqui está normalizada (0..1) e em RGB
            gray = cv2.cvtColor((image * 255).astype(np.uint8), cv2.COLOR_RGB2GRAY)
            # Equalização adaptativa para destacar gotículas
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            eq = clahe.apply(gray)
            # Suavização
            blur = cv2.GaussianBlur(eq, (5, 5), 0)
            # limiarização adaptativa
            th = cv2.adaptiveThreshold(blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                       cv2.THRESH_BINARY, 11, 2)
            # Inverte se predominância for branca (gotículas escuras)
            if np.mean(th) > 127:
                th = cv2.bitwise_not(th)
            # Morfologia para limpar ruídos
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
            opened = cv2.morphologyEx(th, cv2.MORPH_OPEN, kernel, iterations=1)
            closed = cv2.morphologyEx(opened, cv2.MORPH_CLOSE, kernel, iterations=1)
            return (closed > 0).astype(np.uint8)
        except Exception as e:
            logger.warning(f"Erro no fallback OpenCV: {e}")
            h, w = image.shape[:2]
            return np.zeros((h, w), dtype=np.uint8)
    
    def analyze_droplets(self, mask: np.ndarray, metadata: Dict) -> Dict:
        """
        Análise quantitativa das gotículas segmentadas
        
        Args:
            mask: Máscara de segmentação binária
            metadata: Metadados da imagem
            
        Returns:
            Dicionário com métricas de análise
        """
        try:
            # Encontra contornos das gotículas
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            # Filtra contornos por área
            valid_droplets = []
            droplet_areas = []
            # Diâmetros equivalentes em pixels (para área/raio) e em micrômetros (para DV50)
            droplet_diameters_px = []
            droplet_diameters_um = []
            
            for contour in contours:
                area = cv2.contourArea(contour)
                if self.min_droplet_area <= area <= self.max_droplet_area:
                    valid_droplets.append(contour)
                    droplet_areas.append(area)
                    
                    # Calcula diâmetro equivalente em pixels
                    diameter_px = 2 * np.sqrt(area / np.pi)
                    droplet_diameters_px.append(diameter_px)

                    # Converte para micrômetros usando escala física configurada
                    # PIXEL_TO_MM: milímetros por pixel -> 1 px = PIXEL_TO_MM mm = PIXEL_TO_MM * 1000 µm
                    try:
                        px_to_mm = float(getattr(settings, 'PIXEL_TO_MM', 0.1))
                    except Exception:
                        px_to_mm = 0.1

                    diameter_um = diameter_px * px_to_mm * 1000.0
                    droplet_diameters_um.append(diameter_um)
            
            # Detecta gotículas sobrepostas/duplicadas
            duplicated_count = self._detect_overlapping_droplets(valid_droplets)
            
            # Calcula métricas
            total_droplets = len(valid_droplets)

            image_h, image_w = mask.shape[:2]
            image_area = image_h * image_w

            # Máscara de proteção: cada gota cobre um raio maior que o contorno óptico
            protection_mask = np.zeros_like(mask, dtype=np.uint8)

            # Também acumulamos a área teórica de proteção (π * r_protecao^2)
            theoretical_protection_area = 0.0

            for contour, area in zip(valid_droplets, droplet_areas):
                M = cv2.moments(contour)
                if M['m00'] <= 0:
                    continue
                cx = int(M['m10'] / M['m00'])
                cy = int(M['m01'] / M['m00'])

                # Raio equivalente do contorno e raio de proteção ampliado
                base_radius = np.sqrt(area / np.pi)
                protection_radius = base_radius * self.protection_radius_factor
                int_radius = int(protection_radius)
                if int_radius <= 0:
                    continue

                cv2.circle(protection_mask, (cx, cy), int_radius, 1, -1)

                # Área contínua da zona de proteção desta gota
                theoretical_protection_area += np.pi * (protection_radius ** 2)

            # Área real de proteção pela união dos discos na máscara
            protection_area_mask = int(np.count_nonzero(protection_mask))
            if protection_area_mask == 0:
                # Fallback: usa soma das áreas segmentadas se nada foi desenhado
                protection_area_mask = int(sum(droplet_areas))

            # Usa o maior valor entre a área da máscara (união dos discos) e a
            # soma teórica das áreas de proteção, garantindo uma cobertura mais realista
            effective_protection_area = max(protection_area_mask, int(theoretical_protection_area))

            coverage_percentage = (effective_protection_area / image_area) * 100

            # Aplica fator de calibração configurável para alinhar com padrões de referência
            try:
                scale = float(getattr(settings, 'DROPLET_COVERAGE_SCALE', 1.0))
            except Exception:
                scale = 1.0

            coverage_percentage *= scale
            coverage_percentage = max(0.0, min(100.0, coverage_percentage))
            
            # Densidade (usando escala configurável de mm por pixel)
            pixel_to_mm = settings.PIXEL_TO_MM
            area_cm2 = (image_area * pixel_to_mm * pixel_to_mm) / 100
            density_per_cm2 = total_droplets / area_cm2 if area_cm2 > 0 else 0
            
            # Coeficiente de Variação (CV) calculado sobre os diâmetros em µm
            if len(droplet_diameters_um) > 1:
                mean_diameter = np.mean(droplet_diameters_um)
                std_diameter = np.std(droplet_diameters_um)
                cv_coefficient = (std_diameter / mean_diameter) * 100 if mean_diameter > 0 else 0
            else:
                cv_coefficient = 0
            
            # DV50 (diâmetro volumétrico médio)
            dv50 = np.median(droplet_diameters_um) if droplet_diameters_um else 0

            # Classe de gotas com base no DV50 (μm)
            droplet_class = self._classify_droplet_size(dv50)
            
            # Avaliação de qualidade
            quality_score = self._calculate_quality_score(
                coverage_percentage, cv_coefficient, density_per_cm2
            )
            
            results = {
                'total_droplets': total_droplets,
                'duplicated_droplets': duplicated_count,
                'coverage_percentage': round(coverage_percentage, 2),
                'density_per_cm2': round(density_per_cm2, 2),
                'cv_coefficient': round(cv_coefficient, 2),
                'dv50_diameter': round(dv50, 2),
                'droplet_class': droplet_class,
                'mean_diameter': round(np.mean(droplet_diameters_um), 2) if droplet_diameters_um else 0,
                'min_diameter': round(np.min(droplet_diameters_um), 2) if droplet_diameters_um else 0,
                'max_diameter': round(np.max(droplet_diameters_um), 2) if droplet_diameters_um else 0,
                'quality_score': quality_score,
                'quality_assessment': self._assess_quality(quality_score),
                'recommendations': self._generate_recommendations(
                    coverage_percentage, cv_coefficient, density_per_cm2
                )
            }
            
            logger.info(f"Análise concluída: {total_droplets} gotículas detectadas")
            return results
            
        except Exception as e:
            logger.error(f"Erro na análise de gotículas: {e}")
            raise ImageProcessingError(f"Falha na análise quantitativa: {str(e)}")
    
    def _detect_overlapping_droplets(self, contours: List) -> int:
        """
        Detecta gotículas sobrepostas/duplicadas
        """
        try:
            duplicated = 0
            
            for i, contour1 in enumerate(contours):
                for j, contour2 in enumerate(contours[i+1:], i+1):
                    # Calcula distância entre centroides
                    M1 = cv2.moments(contour1)
                    M2 = cv2.moments(contour2)
                    
                    if M1['m00'] > 0 and M2['m00'] > 0:
                        cx1, cy1 = M1['m10']/M1['m00'], M1['m01']/M1['m00']
                        cx2, cy2 = M2['m10']/M2['m00'], M2['m01']/M2['m00']
                        
                        distance = np.sqrt((cx1-cx2)**2 + (cy1-cy2)**2)
                        
                        # Raios médios
                        area1, area2 = cv2.contourArea(contour1), cv2.contourArea(contour2)
                        r1, r2 = np.sqrt(area1/np.pi), np.sqrt(area2/np.pi)
                        
                        # Verifica sobreposição
                        if distance < (r1 + r2) * self.overlap_threshold:
                            duplicated += 1
            
            return duplicated
            
        except Exception as e:
            logger.warning(f"Erro na detecção de sobreposições: {e}")
            return 0

    def _classify_droplet_size(self, dv50: float) -> str:
        """Classifica o tamanho médio de gotas (DV50, em micras) em classes padronizadas.

        Faixas aproximadas (baseado em materiais técnicos):
        - Muito fina:   80 a 190 µm
        - Fina:         190 a 280 µm
        - Média:        280 a 330 µm
        - Grossa:       330 a 400 µm
        - Extrema:      > 400 µm
        """
        try:
            if dv50 <= 0:
                return "Indefinida"

            if 80 <= dv50 < 190:
                return "Muito fina"
            if 190 <= dv50 < 280:
                return "Fina"
            if 280 <= dv50 < 330:
                return "Média"
            if 330 <= dv50 < 400:
                return "Grossa"
            if dv50 >= 400:
                return "Extremamente grossa"

            # Abaixo de 80 µm (gotas extremamente finas, alta deriva)
            return "Ultrafina"

        except Exception:
            return "Indefinida"
    
    def _calculate_quality_score(self, coverage: float, cv: float, density: float) -> float:
        """
        Calcula score de qualidade da pulverização (0-100)
        """
        try:
            # ---- Cobertura (% da área do papel) ----
            # Faixa considerada "ótima" em muitos materiais: ~10% a 30%
            cov_opt_low, cov_opt_high = 10.0, 30.0
            cov_min, cov_max = 3.0, 50.0  # abaixo/acima disso a qualidade de cobertura cai muito

            if coverage <= cov_min or coverage >= cov_max:
                coverage_score = 0.0
            elif cov_opt_low <= coverage <= cov_opt_high:
                coverage_score = 40.0
            elif coverage < cov_opt_low:
                # Sobe linearmente de 0 (em cov_min) até 40 (em cov_opt_low)
                coverage_score = 40.0 * (coverage - cov_min) / (cov_opt_low - cov_min)
            else:  # coverage > cov_opt_high
                # Cai linearmente de 40 (em cov_opt_high) até 0 (em cov_max)
                coverage_score = 40.0 * (cov_max - coverage) / (cov_max - cov_opt_high)

            coverage_score = max(0.0, min(40.0, coverage_score))

            # ---- Uniformidade: coeficiente de variação do diâmetro das gotas (CV%) ----
            # CV < 20%: excelente; 20–40%: aceitável; > 40%: ruim
            if cv <= 20.0:
                cv_score = 30.0
            elif cv >= 60.0:
                cv_score = 0.0
            else:
                # Cai linearmente de 30 (em 20%) para 0 (em 60%)
                cv_score = 30.0 * (60.0 - cv) / (60.0 - 20.0)

            cv_score = max(0.0, min(30.0, cv_score))

            # ---- Densidade de gotas (gotas/cm²) ----
            # Em muitos exemplos práticos, valores entre ~20 e 150 gotas/cm²
            # são aceitáveis, variando conforme alvo e produto.
            dens_opt_low, dens_opt_high = 20.0, 150.0
            dens_min, dens_max = 5.0, 250.0

            if density <= dens_min or density >= dens_max:
                density_score = 0.0
            elif dens_opt_low <= density <= dens_opt_high:
                density_score = 30.0
            elif density < dens_opt_low:
                density_score = 30.0 * (density - dens_min) / (dens_opt_low - dens_min)
            else:  # density > dens_opt_high
                density_score = 30.0 * (dens_max - density) / (dens_max - dens_opt_high)

            density_score = max(0.0, min(30.0, density_score))

            total_score = coverage_score + cv_score + density_score
            return min(100.0, max(0.0, total_score))
            
        except Exception as e:
            logger.warning(f"Erro no cálculo de qualidade: {e}")
            return 0
    
    def _assess_quality(self, score: float) -> str:
        """
        Avalia a qualidade da pulverização baseada no score
        """
        if score >= 80:
            return "Excelente"
        elif score >= 60:
            return "Boa"
        elif score >= 40:
            return "Regular"
        else:
            return "Inadequada"
    
    def _generate_recommendations(self, coverage: float, cv: float, density: float) -> List[str]:
        """
        Gera recomendações baseadas na análise
        """
        recommendations = []
        
        # Cobertura muito baixa (< ~5%) é preocupante; entre 5–10% é apenas um alerta leve.
        if coverage < 5.0:
            recommendations.append("Cobertura muito baixa - revisar calibração, volume de calda e velocidade de aplicação")
        elif coverage < self.quality_thresholds['min_coverage']:
            recommendations.append("Cobertura moderada - avaliar necessidade de ajuste de volume ou bicos conforme alvo")
        
        if cv > self.quality_thresholds['max_cv']:
            recommendations.append("Verificar calibração dos bicos e pressão de operação")
        
        if density < self.quality_thresholds['min_density']:
            recommendations.append("Reduzir altura de aplicação ou aumentar pressão")
        elif density > self.quality_thresholds['max_density']:
            recommendations.append("Aumentar altura de aplicação ou reduzir pressão")
        
        if not recommendations:
            recommendations.append("Aplicação dentro dos parâmetros ideais")
        
        return recommendations
    
    def process_image(self, image_path: str) -> Dict:
        """
        Processa uma imagem completa e retorna análise detalhada
        
        Args:
            image_path: Caminho para a imagem
            
        Returns:
            Dicionário com resultados da análise
        """
        try:
            start_time = time.time()
            
            # Carrega imagem
            image = cv2.imread(image_path)
            if image is None:
                raise ImageProcessingError(f"Não foi possível carregar a imagem: {image_path}")
            
            logger.info(f"Processando imagem: {Path(image_path).name}")
            
            # Pré-processamento
            processed_image, metadata = self.preprocess_image(image)
            
            # Segmentação
            mask = self.segment_droplets(processed_image)
            
            # Análise quantitativa
            analysis_results = self.analyze_droplets(mask, metadata)
            
            # Tempo total de processamento
            total_time = time.time() - start_time
            analysis_results['processing_time'] = round(total_time, 3)
            
            logger.info(f"Processamento concluído em {total_time:.3f}s")
            
            return analysis_results
            
        except Exception as e:
            logger.error(f"Erro no processamento da imagem: {e}")
            raise ImageProcessingError(f"Falha no processamento: {str(e)}")

# Instância global do analisador
droplet_analyzer = DropletAnalyzer()
