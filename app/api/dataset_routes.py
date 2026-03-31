"""
API Routes para gerenciamento de dataset e treinamento ML
Sistema Inteligente de Pulverização - TCC ETEC
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import JSONResponse, FileResponse
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from pathlib import Path
import shutil
import json
from datetime import datetime
import uuid
from PIL import Image
import os

from app.core.database import get_db
from app.core.config import settings
from app.models.database import (
    ImageDataset, ImageAnnotation, ApplicationCondition, 
    AnalysisResult, MLModel, TrainingSession, AnnotationTask,
    create_image_entry, create_annotation, get_training_ready_images
)
from app.services.ml_training import start_training as start_ml_training, get_training_progress
from app.core.exceptions import ValidationError, FileProcessingError
from loguru import logger

router = APIRouter(tags=["Dataset Management"])

# ==================== UPLOAD E GERENCIAMENTO DE IMAGENS ====================

@router.post("/dataset/upload")
async def upload_dataset_image(
    file: UploadFile = File(...),
    original_filename: str = Form(None),
    notes: str = Form(None),
    uploaded_by: str = Form("system"),
    pixel_to_mm_ratio: float = Form(None),
    db: Session = Depends(get_db)
):
    """
    Upload de nova imagem para o dataset de treinamento
    """
    file_path = None
    try:
        logger.info(f"Iniciando upload: {file.filename}, content_type: {file.content_type}")
        
        # Validações
        if not file.content_type or not file.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="Arquivo deve ser uma imagem")
        
        # Lê o conteúdo do arquivo
        content = await file.read()
        logger.info(f"Arquivo lido: {len(content)} bytes")
        
        # Valida tamanho do arquivo
        file_size_mb = len(content) / 1024 / 1024
        max_size_mb = settings.MAX_IMAGE_SIZE / 1024 / 1024
        
        if len(content) > settings.MAX_IMAGE_SIZE:
            raise HTTPException(
                status_code=400, 
                detail=f"Arquivo muito grande ({file_size_mb:.1f} MB). Máximo: {max_size_mb:.1f} MB"
            )
        
        # Gera nome único
        file_extension = Path(file.filename).suffix.lower()
        if not file_extension:
            file_extension = '.png'  # Default
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        
        # Diretório de dataset
        dataset_dir = Path(settings.DATASET_PATH)
        dataset_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = dataset_dir / unique_filename
        logger.info(f"Salvando em: {file_path}")
        
        # Salva arquivo
        with open(file_path, "wb") as buffer:
            buffer.write(content)
        
        logger.info(f"Arquivo salvo, extraindo metadados...")
        
        # Extrai metadados da imagem
        try:
            with Image.open(file_path) as img:
                width, height = img.size
                image_format = img.format.lower() if img.format else 'png'
        except Exception as img_error:
            logger.error(f"Erro ao abrir imagem: {img_error}")
            raise HTTPException(status_code=400, detail=f"Arquivo de imagem inválido: {str(img_error)}")
        
        logger.info(f"Metadados: {width}x{height}, formato: {image_format}")
        logger.info(f"Criando entrada no banco...")
        
        # Cria entrada no banco
        try:
            image_entry = ImageDataset(
                filename=unique_filename,
                original_filename=original_filename or file.filename,
                file_path=str(file_path),
                file_size=len(content),
                image_width=width,
                image_height=height,
                image_format=image_format,
                uploaded_by=uploaded_by,
                notes=notes,
                pixel_to_mm_ratio=pixel_to_mm_ratio
            )
            
            db.add(image_entry)
            db.commit()
            db.refresh(image_entry)
            
            logger.info(f"Imagem {unique_filename} adicionada ao dataset com ID {image_entry.id}")
            
        except Exception as db_error:
            logger.error(f"Erro no banco de dados: {db_error}")
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Erro ao salvar no banco: {str(db_error)}")
        
        return {
            "status": "success",
            "message": "Imagem adicionada ao dataset",
            "image_id": image_entry.id,
            "filename": unique_filename,
            "size": f"{width}x{height}",
            "file_size_mb": round(len(content) / 1024 / 1024, 2)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro no upload: {e}")
        logger.exception("Traceback completo:")
        
        # Limpa arquivo se foi criado
        if 'file_path' in locals() and Path(file_path).exists():
            try:
                Path(file_path).unlink()
            except:
                pass
        
        raise HTTPException(status_code=500, detail=f"Erro ao processar upload: {str(e)}")

@router.get("/dataset/images")
async def list_dataset_images(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    annotated_only: bool = Query(False),
    validated_only: bool = Query(False),
    db: Session = Depends(get_db)
):
    """
    Lista imagens do dataset com filtros
    """
    try:
        query = db.query(ImageDataset)
        
        if annotated_only:
            query = query.filter(ImageDataset.is_annotated == True)
        
        if validated_only:
            query = query.filter(ImageDataset.is_validated == True)
        
        total = query.count()
        images = query.order_by(ImageDataset.upload_date.desc()).offset(skip).limit(limit).all()
        
        return {
            "total": total,
            "skip": skip,
            "limit": limit,
            "images": [
                {
                    "id": img.id,
                    "filename": img.filename,
                    "original_filename": img.original_filename,
                    "size": f"{img.image_width}x{img.image_height}",
                    "image_width": img.image_width,
                    "image_height": img.image_height,
                    "format": img.image_format,
                    "file_size_bytes": img.file_size,
                    "file_url": f"/api/v1/dataset/image/{img.id}",
                    "upload_date": img.upload_date.isoformat(),
                    "is_annotated": img.is_annotated,
                    "is_validated": img.is_validated,
                    "annotation_count": len(img.annotations),
                    "pixel_to_mm_ratio": img.pixel_to_mm_ratio,
                    "notes": img.notes
                }
                for img in images
            ]
        }
        
    except Exception as e:
        logger.error(f"Erro ao listar imagens: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/ml/training/{session_id}/status")
async def api_ml_training_status(session_id: int):
    """Retorna status de uma sessão de treinamento ML (usado por train_model.py)"""
    status = get_training_progress(session_id)
    if status.get("error"):
        raise HTTPException(status_code=404, detail=status["error"])
    return status

@router.post("/ml/train")
async def api_ml_train(config: Dict[str, Any], db: Session = Depends(get_db)):
    """Inicia treinamento de modelo ML via JSON (usado por train_model.py)"""
    try:
        model_name = config.get("model_name", "modelo_tcc_v1")
        algorithm = config.get("algorithm", "random_forest")
        test_split = float(config.get("test_split", 0.2))

        # Procura modelo existente ou cria um novo
        model = db.query(MLModel).filter(MLModel.name == model_name).first()
        if not model:
            model = MLModel(
                name=model_name,
                version="1.0",
                model_type="segmentation",
                architecture=algorithm,
                description="Modelo treinado via script train_model.py",
                created_by="cli_script"
            )
            db.add(model)
            db.commit()
            db.refresh(model)

        # Configuração básica de split
        dataset_split_config = {
            "train": 1.0 - test_split,
            "validation": 0.0,
            "test": test_split
        }

        session_name = f"{model_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        result = start_ml_training(
            model_id=model.id,
            session_name=session_name,
            total_epochs=config.get("hyperparameters", {}).get("total_epochs", 100),
            dataset_split_config=dataset_split_config,
            model_type="segmentation",
            architecture=algorithm
        )

        if result.get("status") != "success":
            raise HTTPException(status_code=500, detail=result.get("message", "Falha ao iniciar treinamento"))

        return {
            "status": "success",
            "session_id": result["session_id"],
            "message": result.get("message", "Treinamento iniciado")
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro no endpoint /ml/train: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/dataset/image/{image_id}")
async def get_dataset_image(image_id: int, db: Session = Depends(get_db)):
    """
    Retorna arquivo de imagem do dataset
    """
    try:
        image = db.query(ImageDataset).filter(ImageDataset.id == image_id).first()
        if not image:
            raise HTTPException(status_code=404, detail="Imagem não encontrada")
        
        file_path = Path(image.file_path)
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Arquivo não encontrado")
        
        return FileResponse(
            path=str(file_path),
            media_type=f"image/{image.image_format}",
            filename=image.original_filename
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao servir imagem: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== ANOTAÇÕES ====================

@router.post("/dataset/image/{image_id}/annotations")
async def create_annotations(
    image_id: int,
    annotations: List[Dict[str, Any]],
    annotated_by: str = Query("system"),
    db: Session = Depends(get_db)
):
    """
    Cria anotações para uma imagem
    
    annotations format:
    [
        {
            "x": 100.5,
            "y": 200.3,
            "radius": 5.2,
            "confidence": 0.95,
            "diameter_mm": 0.5
        }
    ]
    """
    try:
        # Verifica se imagem existe
        image = db.query(ImageDataset).filter(ImageDataset.id == image_id).first()
        if not image:
            raise HTTPException(status_code=404, detail="Imagem não encontrada")
        
        # Remove anotações existentes
        db.query(ImageAnnotation).filter(ImageAnnotation.image_id == image_id).delete()
        
        # Cria novas anotações
        created_annotations = []
        for ann_data in annotations:
            annotation = create_annotation(
                image_id=image_id,
                x=ann_data["x"],
                y=ann_data["y"],
                radius=ann_data["radius"],
                annotated_by=annotated_by,
                confidence=ann_data.get("confidence", 1.0),
                diameter_mm=ann_data.get("diameter_mm"),
                intensity_avg=ann_data.get("intensity_avg"),
                intensity_std=ann_data.get("intensity_std")
            )
            
            db.add(annotation)
            created_annotations.append(annotation)
        
        # Atualiza status da imagem
        image.is_annotated = len(created_annotations) > 0
        image.annotation_quality_score = (
            sum(ann.confidence for ann in created_annotations) / len(created_annotations)
            if created_annotations
            else None
        )
        
        db.commit()
        
        logger.info(f"Criadas {len(annotations)} anotações para imagem {image_id}")
        
        return {
            "status": "success",
            "message": f"Criadas {len(annotations)} anotações",
            "image_id": image_id,
            "annotation_count": len(annotations),
            "average_confidence": image.annotation_quality_score
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao criar anotações: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/dataset/image/{image_id}/annotations")
async def get_annotations(image_id: int, db: Session = Depends(get_db)):
    """
    Retorna anotações de uma imagem
    """
    try:
        annotations = db.query(ImageAnnotation).filter(
            ImageAnnotation.image_id == image_id
        ).all()
        
        return {
            "image_id": image_id,
            "annotation_count": len(annotations),
            "annotations": [
                {
                    "id": ann.id,
                    "x": ann.x,
                    "y": ann.y,
                    "radius": ann.radius,
                    "area_pixels": ann.area_pixels,
                    "diameter_mm": ann.diameter_mm,
                    "confidence": ann.confidence,
                    "annotated_by": ann.annotated_by,
                    "annotation_date": ann.annotation_date.isoformat(),
                    "review_status": ann.review_status
                }
                for ann in annotations
            ]
        }
        
    except Exception as e:
        logger.error(f"Erro ao obter anotações: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/dataset/annotation/{annotation_id}/review")
async def review_annotation(
    annotation_id: int,
    status: str = Form(...),  # approved, rejected
    reviewed_by: str = Form(...),
    notes: str = Form(None),
    db: Session = Depends(get_db)
):
    """
    Revisa uma anotação (aprova ou rejeita)
    """
    try:
        if status not in ["approved", "rejected"]:
            raise ValidationError("Status deve ser 'approved' ou 'rejected'")
        
        annotation = db.query(ImageAnnotation).filter(
            ImageAnnotation.id == annotation_id
        ).first()
        
        if not annotation:
            raise HTTPException(status_code=404, detail="Anotação não encontrada")
        
        annotation.review_status = status
        annotation.reviewed_by = reviewed_by
        annotation.review_date = datetime.now()
        annotation.review_notes = notes
        
        db.commit()
        
        return {
            "status": "success",
            "message": f"Anotação {status}",
            "annotation_id": annotation_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro na revisão: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== MODELOS ML ====================

@router.get("/models")
async def list_ml_models(db: Session = Depends(get_db)):
    """
    Lista todos os modelos ML
    """
    try:
        models = db.query(MLModel).all()
        
        return {
            "total": len(models),
            "models": [
                {
                    "id": model.id,
                    "name": model.name,
                    "version": model.version,
                    "architecture": model.architecture,
                    "is_active": model.is_active,
                    "accuracy": model.accuracy,
                    "precision": model.precision,
                    "recall": model.recall,
                    "f1_score": model.f1_score,
                    "created_date": model.created_date.isoformat(),
                    "description": model.description
                }
                for model in models
            ]
        }
        
    except Exception as e:
        logger.error(f"Erro ao listar modelos: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/models")
async def create_ml_model(
    name: str = Form(...),
    version: str = Form(...),
    model_type: str = Form(...),
    architecture: str = Form(...),
    description: str = Form(None),
    created_by: str = Form("system"),
    db: Session = Depends(get_db)
):
    """
    Cria novo modelo ML
    """
    try:
        model = MLModel(
            name=name,
            version=version,
            model_type=model_type,
            architecture=architecture,
            description=description,
            created_by=created_by
        )
        
        db.add(model)
        db.commit()
        db.refresh(model)
        
        return {
            "status": "success",
            "message": "Modelo criado",
            "model_id": model.id,
            "name": model.name,
            "version": model.version
        }
        
    except Exception as e:
        logger.error(f"Erro ao criar modelo: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== TREINAMENTO ====================

@router.post("/training/start")
async def start_training_session(
    model_id: int = Form(...),
    session_name: str = Form(...),
    total_epochs: int = Form(100),
    train_split: float = Form(0.7),
    val_split: float = Form(0.2),
    test_split: float = Form(0.1),
    started_by: str = Form("system"),
    db: Session = Depends(get_db)
):
    """
    Inicia sessão de treinamento
    """
    try:
        # Verifica se modelo existe
        model = db.query(MLModel).filter(MLModel.id == model_id).first()
        if not model:
            raise HTTPException(status_code=404, detail="Modelo não encontrado")
        
        # Verifica se há dados suficientes
        training_images = get_training_ready_images(db)
        if len(training_images) < settings.MIN_TRAINING_IMAGES:
            raise ValidationError(f"Mínimo de {settings.MIN_TRAINING_IMAGES} imagens anotadas necessárias")
        
        # Cria sessão de treinamento
        session = TrainingSession(
            model_id=model_id,
            session_name=session_name,
            total_epochs=total_epochs,
            dataset_split_config={
                "train": train_split,
                "validation": val_split,
                "test": test_split,
                "total_images": len(training_images)
            },
            status="pending",
            started_by=started_by
        )
        
        db.add(session)
        db.commit()
        db.refresh(session)
        
        # TODO: Aqui você adicionaria a lógica real de treinamento
        # Por enquanto, apenas marca como iniciado
        session.status = "running"
        session.start_time = datetime.now()
        db.commit()
        
        logger.info(f"Sessão de treinamento {session_name} iniciada")
        
        return {
            "status": "success",
            "message": "Treinamento iniciado",
            "session_id": session.id,
            "session_name": session_name,
            "dataset_size": len(training_images),
            "estimated_duration": "Calculando..."
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao iniciar treinamento: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/training/sessions")
async def list_training_sessions(db: Session = Depends(get_db)):
    """
    Lista sessões de treinamento
    """
    try:
        sessions = db.query(TrainingSession).order_by(
            TrainingSession.start_time.desc()
        ).all()
        
        return {
            "total": len(sessions),
            "sessions": [
                {
                    "id": session.id,
                    "session_name": session.session_name,
                    "model_name": session.model.name if session.model else "N/A",
                    "status": session.status,
                    "current_epoch": session.current_epoch,
                    "total_epochs": session.total_epochs,
                    "progress_percentage": round((session.current_epoch / session.total_epochs) * 100, 1) if session.total_epochs > 0 else 0,
                    "start_time": session.start_time.isoformat() if session.start_time else None,
                    "duration_minutes": session.total_duration_minutes,
                    "best_validation_loss": session.best_validation_loss
                }
                for session in sessions
            ]
        }
        
    except Exception as e:
        logger.error(f"Erro ao listar sessões: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== ESTATÍSTICAS ====================

@router.get("/dataset/stats")
async def get_dataset_statistics(db: Session = Depends(get_db)):
    """
    Retorna estatísticas do dataset
    """
    try:
        from app.core.database import get_database_stats
        
        stats = get_database_stats()
        
        # Estatísticas adicionais
        total_annotations = db.query(ImageAnnotation).count()
        approved_annotations = db.query(ImageAnnotation).filter(
            ImageAnnotation.review_status == "approved"
        ).count()
        
        avg_annotations_per_image = db.query(ImageDataset).filter(
            ImageDataset.is_annotated == True
        ).count()
        
        if avg_annotations_per_image > 0:
            avg_annotations_per_image = total_annotations / avg_annotations_per_image
        
        stats.update({
            "average_annotations_per_image": round(avg_annotations_per_image, 1),
            "annotation_approval_rate": round((approved_annotations / total_annotations * 100), 1) if total_annotations > 0 else 0,
            "ready_for_training": len(get_training_ready_images(db))
        })
        
        return stats
        
    except Exception as e:
        logger.error(f"Erro ao obter estatísticas: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== EXPORTAÇÃO ====================

@router.get("/dataset/export")
async def export_dataset(
    format: str = Query("coco", description="Formato de exportação: coco, yolo, csv"),
    include_unannotated: bool = Query(False),
    db: Session = Depends(get_db)
):
    """
    Exporta dataset em diferentes formatos
    """
    try:
        # Busca imagens
        query = db.query(ImageDataset)
        if not include_unannotated:
            query = query.filter(ImageDataset.is_annotated == True)
        
        images = query.all()
        
        if format.lower() == "coco":
            # Formato COCO JSON
            export_data = {
                "info": {
                    "description": "Droplet Detection Dataset",
                    "version": "1.0",
                    "year": datetime.now().year,
                    "contributor": "TCC ETEC Sistema Pulverização",
                    "date_created": datetime.now().isoformat()
                },
                "images": [],
                "annotations": [],
                "categories": [
                    {"id": 1, "name": "droplet", "supercategory": "object"}
                ]
            }
            
            annotation_id = 1
            for img in images:
                # Adiciona imagem
                export_data["images"].append({
                    "id": img.id,
                    "width": img.image_width,
                    "height": img.image_height,
                    "file_name": img.filename
                })
                
                # Adiciona anotações
                for ann in img.annotations:
                    if ann.review_status == "approved":
                        export_data["annotations"].append({
                            "id": annotation_id,
                            "image_id": img.id,
                            "category_id": 1,
                            "bbox": [
                                ann.x - ann.radius,
                                ann.y - ann.radius,
                                ann.radius * 2,
                                ann.radius * 2
                            ],
                            "area": ann.area_pixels,
                            "iscrowd": 0
                        })
                        annotation_id += 1
            
            return JSONResponse(content=export_data)
        
        elif format.lower() == "csv":
            # Formato CSV simples
            csv_data = []
            for img in images:
                for ann in img.annotations:
                    if ann.review_status == "approved":
                        csv_data.append({
                            "image_id": img.id,
                            "filename": img.filename,
                            "x": ann.x,
                            "y": ann.y,
                            "radius": ann.radius,
                            "diameter_mm": ann.diameter_mm,
                            "confidence": ann.confidence
                        })
            
            return JSONResponse(content={"data": csv_data})
        
        else:
            raise ValidationError("Formato não suportado")
        
    except Exception as e:
        logger.error(f"Erro na exportação: {e}")
        raise HTTPException(status_code=500, detail=str(e))
