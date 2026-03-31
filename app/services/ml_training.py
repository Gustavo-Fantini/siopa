"""
Sistema de Treinamento Automatizado de ML
Sistema Inteligente de Pulverização - TCC ETEC
"""

import os
import json
import numpy as np
import cv2
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import joblib
import pickle
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
from sqlalchemy.orm import Session
import threading
import time

from app.core.database import get_db, DatabaseTransaction
from app.models.database import (
    ImageDataset, ImageAnnotation, MLModel, TrainingSession,
    get_training_ready_images
)
from app.core.config import settings
from loguru import logger

class MLTrainer:
    """
    Sistema principal de treinamento de modelos ML
    """
    
    def __init__(self):
        self.models_dir = Path(settings.MODEL_PATH)
        self.models_dir.mkdir(parents=True, exist_ok=True)
        
        self.training_sessions = {}  # Sessões ativas
        
    def start_training_session(
        self, 
        session_id: int,
        model_type: str = "segmentation",
        architecture: str = "random_forest"
    ) -> bool:
        """
        Inicia uma sessão de treinamento
        """
        try:
            with DatabaseTransaction() as db:
                session = db.query(TrainingSession).filter(
                    TrainingSession.id == session_id
                ).first()

                if not session:
                    raise ValueError(f"Sessão {session_id} não encontrada")

                # Marca como iniciada
                session.status = "running"
                session.start_time = datetime.now()
                db.commit()
                
                # Inicia treinamento em thread separada
                training_thread = threading.Thread(
                    target=self._run_training,
                    args=(session_id, model_type, architecture)
                )
                training_thread.daemon = True
                training_thread.start()
                
                self.training_sessions[session_id] = {
                    "thread": training_thread,
                    "status": "running",
                    "progress": 0
                }
                
                logger.info(f"Treinamento {session_id} iniciado")
                return True
                
        except Exception as e:
            logger.error(f"Erro ao iniciar treinamento: {e}")
            return False
    
    def _run_training(self, session_id: int, model_type: str, architecture: str):
        """
        Executa o treinamento em background
        """
        try:
            with DatabaseTransaction() as db:
                session = db.query(TrainingSession).filter(
                    TrainingSession.id == session_id
                ).first()
                
                if not session:
                    return
                
                # Carrega dados de treinamento
                logger.info("Carregando dados de treinamento...")
                X, y, metadata = self._prepare_training_data(db)

                # Validação baseada em número de imagens anotadas
                total_images = metadata.get("total_images", 0)
                if total_images < settings.MIN_TRAINING_IMAGES:
                    raise ValueError(
                        f"Dados insuficientes para treinamento (mínimo {settings.MIN_TRAINING_IMAGES} imagens anotadas)"
                    )

                # Garante que há amostras extraídas
                if len(X) == 0:
                    raise ValueError("Não foi possível extrair amostras das anotações (features vazias)")
                
                # Estatísticas de distribuição de classes
                unique, counts = np.unique(y, return_counts=True)
                class_dist = {int(cls): int(cnt) for cls, cnt in zip(unique, counts)}
                metadata["class_distribution"] = class_dist
                logger.info(f"Distribuição de classes (0=não-gota, 1=gota): {class_dist}")

                # Divide dataset
                X_train, X_test, y_train, y_test = train_test_split(
                    X, y, test_size=0.2, random_state=42, stratify=y
                )
                
                logger.info(f"Dataset: {len(X_train)} treino, {len(X_test)} teste")
                
                # Treina modelo baseado na arquitetura
                if architecture == "random_forest":
                    model = self._train_random_forest(
                        X_train, y_train, X_test, y_test, session_id
                    )
                elif architecture == "svm":
                    model = self._train_svm(
                        X_train, y_train, X_test, y_test, session_id
                    )
                else:
                    raise ValueError(f"Arquitetura não suportada: {architecture}")
                
                # Avalia modelo
                metrics = self._evaluate_model(model, X_test, y_test)
                
                # Salva modelo
                model_path = self._save_model(model, session_id, architecture)
                
                # Atualiza banco de dados
                self._update_training_results(
                    db, session, model_path, metrics, metadata
                )
                
                logger.info(f"Treinamento {session_id} concluído com sucesso")
                
        except Exception as e:
            logger.error(f"Erro no treinamento {session_id}: {e}")
            self._mark_training_failed(session_id, str(e))
    
    def _prepare_training_data(self, db: Session) -> Tuple[np.ndarray, np.ndarray, Dict]:
        """
        Prepara dados de treinamento a partir das anotações
        """
        # Busca imagens anotadas e validadas
        images = get_training_ready_images(db)

        features = []
        labels = []
        metadata = {
            "total_images": len(images),
            "total_annotations": 0,
            "feature_names": [
                "intensity_mean", "intensity_std", "laplacian_var",
                "sobel_x_mean", "sobel_y_mean", "area_pixels",
                "aspect_ratio", "solidity", "perimeter",
                "circularity", "bbox_fill_ratio"
            ]
        }

        for image in images:
            # Carrega imagem
            img_path = Path(image.file_path)
            if not img_path.exists():
                continue
                
            img = cv2.imread(str(img_path))
            if img is None:
                continue
                
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Extrai features positivas (gotículas anotadas)
            for annotation in image.annotations:
                    
                # Extrai patch ao redor da gotícula
                x, y, r = int(annotation.x), int(annotation.y), int(annotation.radius)
                
                # Garante que o patch está dentro da imagem
                x1, y1 = max(0, x - r - 5), max(0, y - r - 5)
                x2, y2 = min(gray.shape[1], x + r + 5), min(gray.shape[0], y + r + 5)
                
                if x2 - x1 < 10 or y2 - y1 < 10:
                    continue
                    
                patch = gray[y1:y2, x1:x2]
                
                # Extrai características
                feature_vector = self._extract_patch_features(patch)
                if feature_vector is not None:
                    features.append(feature_vector)
                    labels.append(1)  # Gotícula positiva
                    metadata["total_annotations"] += 1
            
            # Extrai features negativas (patches aleatórios sem gotículas)
            num_negatives = len(image.annotations)
            for _ in range(num_negatives):
                # Posição aleatória
                x = np.random.randint(20, gray.shape[1] - 20)
                y = np.random.randint(20, gray.shape[0] - 20)
                
                # Verifica se não está próximo de nenhuma gotícula
                is_near_droplet = False
                for ann in image.annotations:
                    distance = np.sqrt((ann.x - x)**2 + (ann.y - y)**2)
                    if distance < ann.radius + 10:
                        is_near_droplet = True
                        break
                
                if not is_near_droplet:
                    patch = gray[y-10:y+10, x-10:x+10]
                    if patch.shape == (20, 20):
                        feature_vector = self._extract_patch_features(patch)
                        if feature_vector is not None:
                            features.append(feature_vector)
                            labels.append(0)  # Não-gotícula
        
        return np.array(features), np.array(labels), metadata
    
    def _extract_patch_features(self, patch: np.ndarray) -> Optional[np.ndarray]:
        """Extrai características de um patch de imagem para o Random Forest."""
        try:
            if patch.size == 0:
                return None

            # Características básicas de intensidade
            intensity_mean = np.mean(patch)
            intensity_std = np.std(patch)

            # Características de textura
            laplacian = cv2.Laplacian(patch, cv2.CV_64F)
            laplacian_var = np.var(laplacian)

            # Gradientes
            sobel_x = cv2.Sobel(patch, cv2.CV_64F, 1, 0, ksize=3)
            sobel_y = cv2.Sobel(patch, cv2.CV_64F, 0, 1, ksize=3)
            sobel_x_mean = np.mean(np.abs(sobel_x))
            sobel_y_mean = np.mean(np.abs(sobel_y))

            # Características morfológicas
            _, binary = cv2.threshold(patch, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            if contours:
                # Maior contorno
                largest_contour = max(contours, key=cv2.contourArea)
                area = cv2.contourArea(largest_contour)

                if area > 0:
                    # Bounding box mínima
                    rect = cv2.minAreaRect(largest_contour)
                    width, height = rect[1]
                    aspect_ratio = max(width, height) / max(min(width, height), 1)

                    # Solidez (área / área do hull convexo)
                    hull = cv2.convexHull(largest_contour)
                    hull_area = cv2.contourArea(hull)
                    solidity = area / max(hull_area, 1)

                    # Perímetro e circularidade
                    perimeter = cv2.arcLength(largest_contour, True)
                    if perimeter > 0:
                        circularity = 4 * np.pi * area / (perimeter ** 2)
                    else:
                        circularity = 0.0

                    # Relação área / bounding box (preenchimento)
                    bbox_w = max(width, 1)
                    bbox_h = max(height, 1)
                    bbox_area = bbox_w * bbox_h
                    bbox_fill_ratio = area / bbox_area if bbox_area > 0 else 0.0
                else:
                    area = 0
                    aspect_ratio = 1
                    solidity = 0
                    perimeter = 0
                    circularity = 0.0
                    bbox_fill_ratio = 0.0
            else:
                area = 0
                aspect_ratio = 1
                solidity = 0
                perimeter = 0
                circularity = 0.0
                bbox_fill_ratio = 0.0

            return np.array([
                intensity_mean, intensity_std, laplacian_var,
                sobel_x_mean, sobel_y_mean, area,
                aspect_ratio, solidity, perimeter,
                circularity, bbox_fill_ratio,
            ])

        except Exception as e:
            logger.warning(f"Erro ao extrair features: {e}")
            return None
    
    def _train_random_forest(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_test: np.ndarray,
        y_test: np.ndarray,
        session_id: int
    ):
        """
        Treina modelo Random Forest
        """
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.metrics import accuracy_score

        logger.info("Treinando Random Forest...")
        
        model = RandomForestClassifier(
            n_estimators=100,
            criterion="gini",
            max_depth=None,
            min_samples_split=2,
            min_samples_leaf=1,
            max_features="sqrt",
            class_weight="balanced",  # lida melhor com desbalanceamento entre gota/não-gota
            oob_score=True,
            random_state=42,
            n_jobs=-1,
        )

        # Simula progresso de treinamento
        for i in range(10):
            time.sleep(0.5)
            progress = (i + 1) * 10
            self._update_training_progress(session_id, progress)

        model.fit(X_train, y_train)

        # Loga métricas internas do modelo
        try:
            logger.info("Random Forest treinado com sucesso")
            if hasattr(model, "oob_score_"):
                logger.info(
                    f"OOB score (estimativa de acurácia fora da amostra): {model.oob_score_:.4f}"
                )
        except Exception as e:
            logger.warning(f"Erro ao registrar métricas do Random Forest: {e}")

        return model
    
    def _train_svm(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_test: np.ndarray,
        y_test: np.ndarray,
        session_id: int
    ):
        """
        Treina modelo SVM
        """
        from sklearn.svm import SVC
        from sklearn.preprocessing import StandardScaler
        
        logger.info("Treinando SVM...")
        
        # Normalização
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)
        
        model = SVC(
            kernel='rbf',
            C=1.0,
            gamma='scale',
            probability=True,
            random_state=42
        )
        
        # Simula progresso
        for i in range(10):
            time.sleep(0.3)
            progress = (i + 1) * 10
            self._update_training_progress(session_id, progress)
        
        model.fit(X_train_scaled, y_train)
        
        # Retorna modelo e scaler juntos
        return {"model": model, "scaler": scaler}
    
    def _evaluate_model(self, model, X_test: np.ndarray, y_test: np.ndarray) -> Dict:
        """
        Avalia performance do modelo
        """
        # Faz predições
        if isinstance(model, dict):  # SVM com scaler
            X_test_scaled = model["scaler"].transform(X_test)
            y_pred = model["model"].predict(X_test_scaled)
            y_prob = model["model"].predict_proba(X_test_scaled)[:, 1]
        else:  # Random Forest
            y_pred = model.predict(X_test)
            y_prob = model.predict_proba(X_test)[:, 1]
        
        # Calcula métricas
        metrics = {
            "accuracy": accuracy_score(y_test, y_pred),
            "precision": precision_score(y_test, y_pred, zero_division=0),
            "recall": recall_score(y_test, y_pred, zero_division=0),
            "f1_score": f1_score(y_test, y_pred, zero_division=0)
        }
        
        logger.info(f"Métricas do modelo: {metrics}")
        return metrics
    
    def _save_model(self, model, session_id: int, architecture: str) -> str:
        """
        Salva modelo treinado
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        model_filename = f"model_{architecture}_{session_id}_{timestamp}.pkl"
        model_path = self.models_dir / model_filename
        
        # Salva usando joblib (mais eficiente para sklearn)
        joblib.dump(model, model_path)
        
        logger.info(f"Modelo salvo em: {model_path}")
        return str(model_path)
    
    def _update_training_progress(self, session_id: int, progress: int):
        """
        Atualiza progresso do treinamento
        """
        try:
            with DatabaseTransaction() as db:
                session = db.query(TrainingSession).filter(
                    TrainingSession.id == session_id
                ).first()
                
                if session:
                    session.current_epoch = progress
                    
                    # Atualiza histórico de treinamento
                    if not session.training_history:
                        session.training_history = []
                    
                    history = session.training_history or []
                    history.append({
                        "epoch": progress,
                        "timestamp": datetime.now().isoformat(),
                        "status": "training"
                    })
                    session.training_history = history
                    
                    db.commit()
                    
        except Exception as e:
            logger.warning(f"Erro ao atualizar progresso: {e}")
    
    def _update_training_results(
        self,
        db: Session,
        session: TrainingSession,
        model_path: str,
        metrics: Dict,
        metadata: Dict
    ):
        """
        Atualiza resultados do treinamento no banco
        """
        try:
            # Atualiza sessão
            session.status = "completed"
            session.end_time = datetime.now()
            session.total_duration_minutes = (
                session.end_time - session.start_time
            ).total_seconds() / 60
            session.final_model_path = model_path
            session.best_validation_loss = 1 - metrics["accuracy"]  # Aproximação
            
            # Atualiza modelo
            model = db.query(MLModel).filter(MLModel.id == session.model_id).first()
            if model:
                model.accuracy = metrics["accuracy"]
                model.precision = metrics["precision"]
                model.recall = metrics["recall"]
                model.f1_score = metrics["f1_score"]
                model.model_path = model_path
                model.training_dataset_size = metadata["total_images"]
                model.is_production_ready = metrics["accuracy"] > 0.8
                
                # Se é o melhor modelo, torna ativo
                if metrics["accuracy"] > 0.85:
                    # Desativa outros modelos do mesmo tipo
                    db.query(MLModel).filter(
                        MLModel.model_type == model.model_type,
                        MLModel.id != model.id
                    ).update({"is_active": False})
                    
                    model.is_active = True
            
            db.commit()
            logger.info("Resultados do treinamento salvos")
            
        except Exception as e:
            logger.error(f"Erro ao salvar resultados: {e}")
    
    def _mark_training_failed(self, session_id: int, error_message: str):
        """
        Marca treinamento como falhou
        """
        try:
            with DatabaseTransaction() as db:
                session = db.query(TrainingSession).filter(
                    TrainingSession.id == session_id
                ).first()
                
                if session:
                    session.status = "failed"
                    session.end_time = datetime.now()
                    session.error_message = error_message
                    db.commit()
                    
        except Exception as e:
            logger.error(f"Erro ao marcar falha: {e}")
    
    def get_training_status(self, session_id: int) -> Dict:
        """
        Retorna status de uma sessão de treinamento
        """
        try:
            with DatabaseTransaction() as db:
                session = db.query(TrainingSession).filter(
                    TrainingSession.id == session_id
                ).first()
                
                if not session:
                    return {"error": "Sessão não encontrada"}
                
                return {
                    "session_id": session.id,
                    "status": session.status,
                    "progress": session.current_epoch,
                    "total_epochs": session.total_epochs,
                    "start_time": session.start_time.isoformat() if session.start_time else None,
                    "duration_minutes": session.total_duration_minutes,
                    "error_message": session.error_message
                }
                
        except Exception as e:
            logger.error(f"Erro ao obter status: {e}")
            return {"error": str(e)}
    
    def load_best_model(self, model_type: str = "segmentation"):
        """
        Carrega o melhor modelo ativo
        """
        try:
            with DatabaseTransaction() as db:
                model = db.query(MLModel).filter(
                    MLModel.model_type == model_type,
                    MLModel.is_active == True
                ).first()
                
                if not model or not model.model_path:
                    return None
                
                model_path = Path(model.model_path)
                if not model_path.exists():
                    return None
                
                loaded_model = joblib.load(model_path)
                
                logger.info(f"Modelo {model.name} carregado com sucesso")
                return {
                    "model": loaded_model,
                    "metadata": {
                        "name": model.name,
                        "version": model.version,
                        "architecture": model.architecture,
                        "accuracy": model.accuracy
                    }
                }
                
        except Exception as e:
            logger.error(f"Erro ao carregar modelo: {e}")
            return None

# Instância global do trainer
ml_trainer = MLTrainer()

# Funções helper para uso nas APIs
def start_training(
    model_id: int,
    session_name: str,
    total_epochs: int = 100,
    **kwargs
) -> Dict:
    """
    Função helper para iniciar treinamento
    """
    try:
        with DatabaseTransaction() as db:
            # Cria sessão de treinamento
            session = TrainingSession(
                model_id=model_id,
                session_name=session_name,
                total_epochs=total_epochs,
                dataset_split_config=kwargs.get('dataset_split_config', {}),
                status="pending"
            )
            
            db.add(session)
            db.commit()
            db.refresh(session)
            
            # Inicia treinamento
            success = ml_trainer.start_training_session(
                session.id,
                kwargs.get('model_type', 'segmentation'),
                kwargs.get('architecture', 'random_forest')
            )
            
            if success:
                return {
                    "status": "success",
                    "session_id": session.id,
                    "message": "Treinamento iniciado"
                }
            else:
                return {
                    "status": "error",
                    "message": "Falha ao iniciar treinamento"
                }
                
    except Exception as e:
        logger.error(f"Erro ao iniciar treinamento: {e}")
        return {
            "status": "error",
            "message": str(e)
        }

def get_training_progress(session_id: int) -> Dict:
    """
    Função helper para obter progresso
    """
    return ml_trainer.get_training_status(session_id)

def load_active_model(model_type: str = "segmentation"):
    """
    Função helper para carregar modelo ativo
    """
    return ml_trainer.load_best_model(model_type)
