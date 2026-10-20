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
import hashlib
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import GroupShuffleSplit
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
from app.services.vision_features import FEATURE_NAMES, extract_patch_features
from loguru import logger

CLASS_LABELS = {
    0: "background",
    1: "droplet_small",
    2: "droplet_medium",
    3: "droplet_large",
    4: "droplet_duplicate",
    5: "dirt",
}
LABEL_BY_CLASS = {value: key for key, value in CLASS_LABELS.items()}


def split_by_source_image(X, y, groups, holdout_fraction=0.2):
    """Keep every patch and byte-identical source image in exactly one partition."""
    groups = np.asarray(groups)
    if len(groups) != len(X) or len(set(groups)) < 2:
        raise ValueError("São necessárias ao menos duas imagens distintas para um holdout independente.")
    if not 0 < holdout_fraction < 1:
        raise ValueError("A fração de avaliação deve estar entre 0 e 1.")
    train_indices, test_indices = next(GroupShuffleSplit(
        n_splits=1, test_size=holdout_fraction, random_state=42,
    ).split(X, y, groups))
    if len(np.unique(y[train_indices])) < 2:
        raise ValueError("A divisão por imagem deixou menos de duas classes no treino; amplie o dataset revisado.")
    return train_indices, test_indices

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
                
                # Estatisticas de distribuicao de classes
                unique, counts = np.unique(y, return_counts=True)
                class_dist = {int(cls): int(cnt) for cls, cnt in zip(unique, counts)}
                metadata["class_distribution"] = class_dist
                readable_dist = {
                    CLASS_LABELS.get(int(cls), str(cls)): int(cnt)
                    for cls, cnt in zip(unique, counts)
                }
                metadata["class_distribution_readable"] = readable_dist
                logger.info(f"Distribuicao de classes: {readable_dist}")

                if len(class_dist) < 2:
                    raise ValueError("Treinamento precisa de ao menos 2 classes: anotacoes positivas e fundo/sujeira")

                split_config = session.dataset_split_config or {}
                train_share = float(split_config.get("train", 0.8))
                validation_share = float(split_config.get("validation", 0.1))
                test_share = float(split_config.get("test", 0.1))
                shares = (train_share, validation_share, test_share)
                if any(not np.isfinite(value) or value < 0 for value in shares) or min(train_share, validation_share + test_share) <= 0:
                    raise ValueError("Informe frações finitas e positivas para treino e avaliação.")
                holdout = (validation_share + test_share) / sum(shares)
                train_indices, test_indices = split_by_source_image(X, y, metadata["sample_groups"], holdout)
                X_train, X_test, y_train, y_test = X[train_indices], X[test_indices], y[train_indices], y[test_indices]
                metadata["evaluation_scope"] = "grouped_source_image_holdout; validation_and_test_combined"
                metadata["train_source_hashes"] = sorted(set(metadata["sample_groups"][i] for i in train_indices))
                metadata["holdout_source_hashes"] = sorted(set(metadata["sample_groups"][i] for i in test_indices))
                self._update_training_progress(session_id, 25)
                
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
                self._attach_model_metadata(model, metadata)
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
        Prepara dados de treinamento multiclasses a partir das anotacoes.

        Classes:
        0 background, 1 gota pequena, 2 gota media, 3 gota grande,
        4 gota dupla/mesclada, 5 sujeira/artefato.
        """
        images = get_training_ready_images(db)
        rng = np.random.default_rng(42)

        features: List[np.ndarray] = []
        labels: List[int] = []
        metadata = {
            "total_images": 0,
            "total_annotations": 0,
            "negative_samples": 0,
            "feature_names": FEATURE_NAMES,
            "class_labels": CLASS_LABELS,
            "training_mode": "multiclass_patch_classifier",
            "sample_groups": [],
        }

        for image in images:
            img_path = Path(image.file_path)
            if not img_path.exists():
                continue

            img = cv2.imread(str(img_path), cv2.IMREAD_COLOR)
            if img is None:
                continue

            source_hash = hashlib.sha256(img_path.read_bytes()).hexdigest()

            height, width = img.shape[:2]
            annotations = [annotation for annotation in image.annotations or [] if annotation.review_status == "approved"]
            valid_annotations = []

            for annotation in annotations:
                patch = self._extract_annotation_patch(img, annotation)
                feature_vector = extract_patch_features(patch) if patch is not None else None
                if feature_vector is None:
                    continue

                label = self._annotation_to_label(annotation)
                features.append(feature_vector)
                labels.append(label)
                metadata["sample_groups"].append(source_hash)
                valid_annotations.append(annotation)
                metadata["total_annotations"] += 1

            if valid_annotations:
                metadata["total_images"] += 1

            negative_target = max(len(valid_annotations), 3 if valid_annotations else 0)
            if width < 24 or height < 24 or negative_target <= 0:
                continue

            negative_count = 0
            attempts = 0
            patch_radius = max(8, min(18, int(min(width, height) * 0.03)))
            max_attempts = max(negative_target * 12, 30)

            while negative_count < negative_target and attempts < max_attempts:
                attempts += 1
                x = int(rng.integers(patch_radius, max(patch_radius + 1, width - patch_radius)))
                y = int(rng.integers(patch_radius, max(patch_radius + 1, height - patch_radius)))
                if self._is_near_annotation(x, y, annotations, patch_radius):
                    continue

                patch = img[y - patch_radius:y + patch_radius, x - patch_radius:x + patch_radius]
                feature_vector = extract_patch_features(patch)
                if feature_vector is None:
                    continue

                features.append(feature_vector)
                labels.append(0)
                metadata["sample_groups"].append(source_hash)
                negative_count += 1
                metadata["negative_samples"] += 1

        if not features:
            return np.empty((0, len(FEATURE_NAMES)), dtype=np.float32), np.empty((0,), dtype=np.int64), metadata

        return np.asarray(features, dtype=np.float32), np.asarray(labels, dtype=np.int64), metadata

    def _extract_annotation_patch(self, image_bgr: np.ndarray, annotation: ImageAnnotation) -> Optional[np.ndarray]:
        """Return a context patch around one manual annotation."""
        try:
            height, width = image_bgr.shape[:2]
            x = int(round(annotation.x))
            y = int(round(annotation.y))
            radius = max(2, int(round(annotation.radius or 2)))
            padding = max(6, int(round(radius * 0.7)))

            x1 = max(0, x - radius - padding)
            y1 = max(0, y - radius - padding)
            x2 = min(width, x + radius + padding)
            y2 = min(height, y + radius + padding)
            if x2 - x1 < 8 or y2 - y1 < 8:
                return None
            return image_bgr[y1:y2, x1:x2]
        except Exception:
            return None

    def _annotation_to_label(self, annotation: ImageAnnotation) -> int:
        """Map persisted annotation metadata to a stable ML class id."""
        annotation_type = str(annotation.annotation_type or "droplet").lower().strip()
        size_class = str(annotation.droplet_size_class or "").lower().strip()

        if annotation_type in {"dirt", "sujeira", "artifact", "artefato"}:
            return LABEL_BY_CLASS["dirt"]
        if annotation_type in {"droplet_duplicate", "duplicate", "dupla", "merged"} or annotation.is_overlapping:
            return LABEL_BY_CLASS["droplet_duplicate"]
        if annotation_type in {"droplet_small", "small"}:
            return LABEL_BY_CLASS["droplet_small"]
        if annotation_type in {"droplet_large", "large"}:
            return LABEL_BY_CLASS["droplet_large"]
        if annotation_type in {"droplet_medium", "medium"}:
            return LABEL_BY_CLASS["droplet_medium"]

        if size_class in {"small", "pequena", "pequeno"}:
            return LABEL_BY_CLASS["droplet_small"]
        if size_class in {"large", "grande"}:
            return LABEL_BY_CLASS["droplet_large"]
        if size_class in {"medium", "media", "medio"}:
            return LABEL_BY_CLASS["droplet_medium"]

        if annotation.diameter_mm is not None:
            diameter_mm = float(annotation.diameter_mm)
            if diameter_mm <= 0.5:
                return LABEL_BY_CLASS["droplet_small"]
            if diameter_mm <= 1.2:
                return LABEL_BY_CLASS["droplet_medium"]
            return LABEL_BY_CLASS["droplet_large"]

        radius = float(annotation.radius or 0)
        if radius <= 6:
            return LABEL_BY_CLASS["droplet_small"]
        if radius <= 12:
            return LABEL_BY_CLASS["droplet_medium"]
        return LABEL_BY_CLASS["droplet_large"]

    @staticmethod
    def _is_near_annotation(x: int, y: int, annotations: List[ImageAnnotation], patch_radius: int) -> bool:
        """Avoid sampling random negatives over known manual annotations."""
        for annotation in annotations:
            distance = float(np.hypot(float(annotation.x) - x, float(annotation.y) - y))
            if distance <= float(annotation.radius or 0) + patch_radius + 4:
                return True
        return False

    def _extract_patch_features(self, patch: np.ndarray) -> Optional[np.ndarray]:
        """Compatibility wrapper around shared feature extraction."""
        return extract_patch_features(patch)

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

        model.fit(X_train, y_train)
        self._update_training_progress(session_id, 85)

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
        
        model.fit(X_train_scaled, y_train)
        self._update_training_progress(session_id, 85)
        
        # Retorna modelo e scaler juntos
        return {"model": model, "scaler": scaler}
    
    def _evaluate_model(self, model, X_test: np.ndarray, y_test: np.ndarray) -> Dict:
        """
        Avalia performance do modelo.
        """
        if isinstance(model, dict):
            X_test_scaled = model["scaler"].transform(X_test)
            y_pred = model["model"].predict(X_test_scaled)
        else:
            y_pred = model.predict(X_test)

        metrics = {
            "accuracy": accuracy_score(y_test, y_pred),
            "precision": precision_score(y_test, y_pred, average="weighted", zero_division=0),
            "recall": recall_score(y_test, y_pred, average="weighted", zero_division=0),
            "f1_score": f1_score(y_test, y_pred, average="weighted", zero_division=0),
        }

        logger.info(f"Metricas do modelo: {metrics}")
        return metrics

    def _attach_model_metadata(self, model, metadata: Dict):
        """Persist class/feature metadata together with the sklearn artifact."""
        payload = {
            "feature_names": metadata.get("feature_names", FEATURE_NAMES),
            "class_labels": metadata.get("class_labels", CLASS_LABELS),
            "class_distribution": metadata.get("class_distribution", {}),
            "class_distribution_readable": metadata.get("class_distribution_readable", {}),
            "training_mode": metadata.get("training_mode", "multiclass_patch_classifier"),
        }

        if isinstance(model, dict):
            model["metadata"] = payload
            estimator = model.get("model")
        else:
            estimator = model

        try:
            setattr(estimator, "siopa_metadata", payload)
            setattr(estimator, "siopa_feature_names", payload["feature_names"])
            setattr(estimator, "siopa_class_labels", payload["class_labels"])
        except Exception:
            logger.debug("Nao foi possivel anexar metadados diretamente ao estimador")

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
                # A patch holdout does not validate the physical analysis pipeline.
                # Activation must follow an explicit, independent field evaluation.
                model.is_production_ready = False
            
            db.commit()
            logger.info("Resultados do treinamento salvos")
            
        except Exception as e:
            logger.error(f"Erro ao salvar resultados: {e}")
            raise
    
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
                artifact_metadata = {}
                if isinstance(loaded_model, dict):
                    artifact_metadata = loaded_model.get("metadata", {}) or {}
                    estimator = loaded_model.get("model")
                else:
                    estimator = loaded_model

                if not artifact_metadata and estimator is not None:
                    artifact_metadata = getattr(estimator, "siopa_metadata", {}) or {}
                
                logger.info(f"Modelo {model.name} carregado com sucesso")
                return {
                    "model": loaded_model,
                    "metadata": {
                        "name": model.name,
                        "version": model.version,
                        "architecture": model.architecture,
                        "accuracy": model.accuracy,
                        **artifact_metadata,
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
                status="pending",
                started_by=kwargs.get("started_by", "system"),
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
