"""
Modelos de banco de dados para sistema de treinamento ML
Sistema Inteligente de Pulverização - TCC ETEC
"""

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey, JSON, LargeBinary
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
from typing import Dict, List, Optional
import json

Base = declarative_base()

class ImageDataset(Base):
    """
    Tabela principal para armazenar imagens do dataset de treinamento
    """
    __tablename__ = "image_datasets"
    
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), unique=True, nullable=False, index=True)
    original_filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer, nullable=False)  # em bytes
    image_width = Column(Integer, nullable=False)
    image_height = Column(Integer, nullable=False)
    image_format = Column(String(10), nullable=False)  # jpg, png, etc
    
    # Metadados de captura
    capture_date = Column(DateTime, nullable=True)
    camera_model = Column(String(100), nullable=True)
    dpi = Column(Integer, nullable=True)
    pixel_to_mm_ratio = Column(Float, nullable=True)  # conversão física
    
    # Status de anotação
    is_annotated = Column(Boolean, default=False, index=True)
    is_validated = Column(Boolean, default=False, index=True)
    annotation_quality_score = Column(Float, nullable=True)  # 0-1
    
    # Metadados de upload
    uploaded_by = Column(String(100), nullable=True)
    upload_date = Column(DateTime, default=func.now())
    notes = Column(Text, nullable=True)
    
    # Relacionamentos
    annotations = relationship("ImageAnnotation", back_populates="image", cascade="all, delete-orphan")
    application_conditions = relationship("ApplicationCondition", back_populates="image", cascade="all, delete-orphan")
    analysis_results = relationship("AnalysisResult", back_populates="image", cascade="all, delete-orphan")

class ImageAnnotation(Base):
    """
    Anotações manuais das gotículas nas imagens
    """
    __tablename__ = "image_annotations"
    
    id = Column(Integer, primary_key=True, index=True)
    image_id = Column(Integer, ForeignKey("image_datasets.id"), nullable=False, index=True)
    
    # Coordenadas da gotícula (centro)
    x = Column(Float, nullable=False)
    y = Column(Float, nullable=False)
    radius = Column(Float, nullable=False)  # raio em pixels
    
    # Características da gotícula
    area_pixels = Column(Float, nullable=False)
    diameter_mm = Column(Float, nullable=True)  # diâmetro real em mm
    intensity_avg = Column(Float, nullable=True)  # intensidade média
    intensity_std = Column(Float, nullable=True)  # desvio padrão
    
    # Qualidade da anotação
    confidence = Column(Float, default=1.0)  # confiança do anotador (0-1)
    is_overlapping = Column(Boolean, default=False)
    is_edge_droplet = Column(Boolean, default=False)  # gotícula na borda
    
    # Metadados de anotação
    annotated_by = Column(String(100), nullable=False)
    annotation_date = Column(DateTime, default=func.now())
    review_status = Column(String(20), default="pending")  # pending, approved, rejected
    reviewed_by = Column(String(100), nullable=True)
    review_date = Column(DateTime, nullable=True)
    review_notes = Column(Text, nullable=True)
    
    # Relacionamento
    image = relationship("ImageDataset", back_populates="annotations")

class ApplicationCondition(Base):
    """
    Condições de aplicação dos agrotóxicos (contexto para ML)
    """
    __tablename__ = "application_conditions"
    
    id = Column(Integer, primary_key=True, index=True)
    image_id = Column(Integer, ForeignKey("image_datasets.id"), nullable=False, index=True)
    
    # Condições meteorológicas
    temperature = Column(Float, nullable=True)  # °C
    humidity = Column(Float, nullable=True)  # %
    wind_speed = Column(Float, nullable=True)  # km/h
    wind_direction = Column(Float, nullable=True)  # graus
    pressure = Column(Float, nullable=True)  # hPa
    
    # Parâmetros de aplicação
    nozzle_type = Column(String(50), nullable=True)
    nozzle_pressure = Column(Float, nullable=True)  # bar
    application_height = Column(Float, nullable=True)  # metros
    application_speed = Column(Float, nullable=True)  # km/h
    spray_volume = Column(Float, nullable=True)  # L/ha
    
    # Cultura e solo
    crop_type = Column(String(50), nullable=True)
    growth_stage = Column(String(50), nullable=True)
    soil_moisture = Column(Float, nullable=True)  # %
    
    # Produto aplicado
    product_name = Column(String(100), nullable=True)
    active_ingredient = Column(String(100), nullable=True)
    concentration = Column(Float, nullable=True)  # %
    dosage = Column(Float, nullable=True)  # L/ha ou kg/ha
    
    # Localização
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    farm_name = Column(String(100), nullable=True)
    
    # Metadados
    recorded_by = Column(String(100), nullable=True)
    record_date = Column(DateTime, default=func.now())
    
    # Relacionamento
    image = relationship("ImageDataset", back_populates="application_conditions")

class AnalysisResult(Base):
    """
    Resultados de análise (manual ou automática) para comparação
    """
    __tablename__ = "analysis_results"
    
    id = Column(Integer, primary_key=True, index=True)
    image_id = Column(Integer, ForeignKey("image_datasets.id"), nullable=False, index=True)
    model_id = Column(Integer, ForeignKey("ml_models.id"), nullable=True, index=True)
    
    # Métricas de análise
    total_droplets = Column(Integer, nullable=False)
    coverage_percentage = Column(Float, nullable=False)
    density_per_cm2 = Column(Float, nullable=False)
    cv_coefficient = Column(Float, nullable=False)
    dv50_diameter = Column(Float, nullable=True)
    mean_diameter = Column(Float, nullable=True)
    min_diameter = Column(Float, nullable=True)
    max_diameter = Column(Float, nullable=True)
    
    # Qualidade da aplicação
    quality_score = Column(Float, nullable=True)  # 0-100
    quality_assessment = Column(String(20), nullable=True)  # Excelente, Boa, etc
    
    # Tipo de análise
    analysis_type = Column(String(20), nullable=False)  # manual, opencv, deeplab, custom
    processing_time = Column(Float, nullable=True)  # segundos
    
    # Metadados
    analyzed_by = Column(String(100), nullable=True)
    analysis_date = Column(DateTime, default=func.now())
    is_ground_truth = Column(Boolean, default=False)  # se é referência para treinamento
    
    # Dados adicionais em JSON
    additional_metrics = Column(JSON, nullable=True)
    
    # Relacionamentos
    image = relationship("ImageDataset", back_populates="analysis_results")
    model = relationship("MLModel", back_populates="analysis_results")

class MLModel(Base):
    """
    Modelos de Machine Learning treinados
    """
    __tablename__ = "ml_models"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, index=True)
    version = Column(String(20), nullable=False)
    model_type = Column(String(50), nullable=False)  # segmentation, classification, regression
    architecture = Column(String(100), nullable=False)  # opencv, unet, deeplabv3, etc
    
    # Arquivo do modelo
    model_path = Column(String(500), nullable=True)
    model_size_mb = Column(Float, nullable=True)
    
    # Métricas de performance
    accuracy = Column(Float, nullable=True)
    precision = Column(Float, nullable=True)
    recall = Column(Float, nullable=True)
    f1_score = Column(Float, nullable=True)
    iou_score = Column(Float, nullable=True)  # Intersection over Union
    
    # Configuração de treinamento
    training_dataset_size = Column(Integer, nullable=True)
    validation_dataset_size = Column(Integer, nullable=True)
    epochs_trained = Column(Integer, nullable=True)
    learning_rate = Column(Float, nullable=True)
    batch_size = Column(Integer, nullable=True)
    
    # Status e metadados
    is_active = Column(Boolean, default=False, index=True)
    is_production_ready = Column(Boolean, default=False)
    created_by = Column(String(100), nullable=True)
    created_date = Column(DateTime, default=func.now())
    description = Column(Text, nullable=True)
    
    # Configurações em JSON
    hyperparameters = Column(JSON, nullable=True)
    preprocessing_config = Column(JSON, nullable=True)
    
    # Relacionamentos
    training_sessions = relationship("TrainingSession", back_populates="model")
    analysis_results = relationship("AnalysisResult", back_populates="model")

class TrainingSession(Base):
    """
    Sessões de treinamento de modelos ML
    """
    __tablename__ = "training_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(Integer, ForeignKey("ml_models.id"), nullable=False, index=True)
    
    # Configuração da sessão
    session_name = Column(String(100), nullable=False)
    dataset_split_config = Column(JSON, nullable=False)  # train/val/test split
    augmentation_config = Column(JSON, nullable=True)
    
    # Progresso do treinamento
    status = Column(String(20), default="pending")  # pending, running, completed, failed
    current_epoch = Column(Integer, default=0)
    total_epochs = Column(Integer, nullable=False)
    
    # Métricas por época (JSON array)
    training_history = Column(JSON, nullable=True)
    
    # Tempos
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    total_duration_minutes = Column(Float, nullable=True)
    
    # Recursos utilizados
    gpu_used = Column(Boolean, default=False)
    memory_usage_gb = Column(Float, nullable=True)
    
    # Resultados finais
    best_epoch = Column(Integer, nullable=True)
    best_validation_loss = Column(Float, nullable=True)
    final_model_path = Column(String(500), nullable=True)
    
    # Metadados
    started_by = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    
    # Relacionamento
    model = relationship("MLModel", back_populates="training_sessions")

class DatasetSplit(Base):
    """
    Divisão do dataset para treinamento/validação/teste
    """
    __tablename__ = "dataset_splits"
    
    id = Column(Integer, primary_key=True, index=True)
    image_id = Column(Integer, ForeignKey("image_datasets.id"), nullable=False, index=True)
    split_name = Column(String(50), nullable=False)  # train, validation, test
    split_version = Column(String(20), default="v1.0")
    
    # Metadados da divisão
    created_date = Column(DateTime, default=func.now())
    created_by = Column(String(100), nullable=True)
    
    # Índices compostos para performance
    __table_args__ = (
        {"sqlite_autoincrement": True}
    )

class AnnotationTask(Base):
    """
    Tarefas de anotação para distribuir trabalho
    """
    __tablename__ = "annotation_tasks"
    
    id = Column(Integer, primary_key=True, index=True)
    task_name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    
    # Imagens da tarefa (JSON array de IDs)
    image_ids = Column(JSON, nullable=False)
    
    # Status da tarefa
    status = Column(String(20), default="pending")  # pending, in_progress, completed, reviewed
    assigned_to = Column(String(100), nullable=True)
    assigned_date = Column(DateTime, nullable=True)
    
    # Progresso
    total_images = Column(Integer, nullable=False)
    annotated_images = Column(Integer, default=0)
    reviewed_images = Column(Integer, default=0)
    
    # Qualidade
    average_quality_score = Column(Float, nullable=True)
    requires_review = Column(Boolean, default=True)
    
    # Metadados
    created_by = Column(String(100), nullable=False)
    created_date = Column(DateTime, default=func.now())
    completed_date = Column(DateTime, nullable=True)
    
    # Configurações da tarefa
    annotation_guidelines = Column(Text, nullable=True)
    quality_threshold = Column(Float, default=0.8)

# Funções helper para trabalhar com os modelos

def create_image_entry(
    filename: str,
    file_path: str,
    width: int,
    height: int,
    file_size: int,
    image_format: str,
    **kwargs
) -> ImageDataset:
    """
    Cria uma nova entrada de imagem no dataset
    """
    return ImageDataset(
        filename=filename,
        original_filename=kwargs.get('original_filename', filename),
        file_path=file_path,
        file_size=file_size,
        image_width=width,
        image_height=height,
        image_format=image_format,
        **{k: v for k, v in kwargs.items() if hasattr(ImageDataset, k)}
    )

def create_annotation(
    image_id: int,
    x: float,
    y: float,
    radius: float,
    annotated_by: str,
    **kwargs
) -> ImageAnnotation:
    """
    Cria uma nova anotação de gotícula
    """
    area_pixels = 3.14159 * radius * radius
    
    return ImageAnnotation(
        image_id=image_id,
        x=x,
        y=y,
        radius=radius,
        area_pixels=area_pixels,
        annotated_by=annotated_by,
        **{k: v for k, v in kwargs.items() if hasattr(ImageAnnotation, k)}
    )

def get_training_ready_images(db_session) -> List[ImageDataset]:
    """
    Retorna imagens prontas para treinamento (atualmente: todas as anotadas)
    """
    return db_session.query(ImageDataset).filter(
        ImageDataset.is_annotated == True
    ).all()

def get_model_performance_summary(db_session, model_id: int) -> Dict:
    """
    Retorna resumo de performance de um modelo
    """
    model = db_session.query(MLModel).filter(MLModel.id == model_id).first()
    if not model:
        return {}
    
    results = db_session.query(AnalysisResult).filter(
        AnalysisResult.model_id == model_id
    ).all()
    
    return {
        "model_name": model.name,
        "version": model.version,
        "total_predictions": len(results),
        "accuracy": model.accuracy,
        "precision": model.precision,
        "recall": model.recall,
        "f1_score": model.f1_score,
        "is_active": model.is_active
    }
