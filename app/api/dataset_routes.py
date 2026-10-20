"""
API Routes para gerenciamento de dataset e treinamento ML
Sistema Inteligente de Pulverização - TCC ETEC
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import JSONResponse, FileResponse
from sqlalchemy import func
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from pathlib import Path
import shutil
import json
from datetime import datetime
import uuid
from PIL import Image
import os
import math

from app.core.database import get_db
from app.core.config import settings
from app.core.access import require_admin_access
from app.models.database import (
    ImageDataset, ImageAnnotation, ApplicationCondition, 
    AnalysisResult, MLModel, TrainingSession, AnnotationTask,
    create_image_entry, create_annotation, get_training_ready_images
)
from app.services.ml_training import start_training as start_ml_training, get_training_progress
from app.core.exceptions import ValidationError, FileProcessingError
from loguru import logger

router = APIRouter(tags=["Dataset Management"], dependencies=[Depends(require_admin_access)])

# ==================== UPLOAD E GERENCIAMENTO DE IMAGENS ====================

@router.post("/dataset/upload")
async def upload_dataset_image(
    file: UploadFile = File(...), original_filename: str = Form(None),
    notes: str = Form(None), uploaded_by: str = Form("system"),
    pixel_to_mm_ratio: float = Form(None), db: Session = Depends(get_db),
):
    """Persist lossless, oriented RGB pixels so annotation coordinates match metadata."""
    from io import BytesIO
    from PIL import ImageOps, UnidentifiedImageError
    import warnings

    file_path = None
    persisted = False
    try:
        if pixel_to_mm_ratio is not None and (not math.isfinite(pixel_to_mm_ratio) or pixel_to_mm_ratio <= 0):
            raise HTTPException(422, "Escala deve ser finita e positiva.")
        content = await file.read(settings.MAX_IMAGE_SIZE + 1)
        if not content or len(content) > settings.MAX_IMAGE_SIZE:
            raise HTTPException(400, "Imagem vazia ou acima do limite de upload.")
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(BytesIO(content)) as raw:
                    if raw.width * raw.height > settings.MAX_IMAGE_PIXELS:
                        raise HTTPException(400, "Imagem acima do limite de pixels.")
                    raw.verify()
                with Image.open(BytesIO(content)) as raw:
                    oriented = ImageOps.exif_transpose(raw)
                    # Fresh pixels omit EXIF/GPS and maintain the decoder's orientation.
                    clean = Image.new("RGB", oriented.size, "white")
                    if "A" in oriented.getbands():
                        clean.paste(oriented.convert("RGB"), mask=oriented.getchannel("A"))
                    else:
                        clean.paste(oriented.convert("RGB"))
                    width, height = clean.size
                    output = BytesIO()
                    clean.save(output, format="PNG")
                    normalized = output.getvalue()
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
            raise HTTPException(400, "Imagem inválida ou grande demais.") from exc
        if len(normalized) > settings.MAX_IMAGE_SIZE * 5:
            raise HTTPException(400, "Pixels normalizados excedem o limite de armazenamento por imagem.")
        unique_filename = f"{uuid.uuid4()}.png"
        dataset_dir = Path(settings.DATASET_PATH)
        dataset_dir.mkdir(parents=True, exist_ok=True)
        file_path = dataset_dir / unique_filename
        file_path.write_bytes(normalized)
        entry = ImageDataset(
            filename=unique_filename, original_filename=original_filename or Path(file.filename or "foto").name,
            file_path=str(file_path), file_size=len(normalized), image_width=width,
            image_height=height, image_format="png", uploaded_by=uploaded_by, notes=notes,
            pixel_to_mm_ratio=pixel_to_mm_ratio,
        )
        db.add(entry)
        db.commit()
        persisted = True
        db.refresh(entry)
        return {"status": "success", "message": "Imagem orientada e salva no dataset",
                "image_id": entry.id, "filename": unique_filename, "size": f"{width}x{height}",
                "file_size_mb": round(len(normalized) / 1048576, 2),
                "normalization": "exif_orientation_applied; lossless_decoded_RGB_PNG; metadata_removed"}
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        logger.exception("Falha no upload do dataset")
        raise HTTPException(500, "Não foi possível salvar a imagem no dataset.")
    finally:
        if file_path and not persisted:
            file_path.unlink(missing_ok=True)

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
    pixel_to_mm_ratio: Optional[float] = Query(None, gt=0),
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
            "annotation_type": "droplet",
            "droplet_size_class": "small",
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
        
        if pixel_to_mm_ratio is not None and not math.isfinite(pixel_to_mm_ratio):
            raise HTTPException(422, "Escala deve ser finita e positiva.")
        if len(annotations) > 30000:
            raise HTTPException(422, "Quantidade de anotações acima do limite por imagem.")
        for ann in annotations:
            for key in ("x", "y", "radius"):
                value = ann.get(key)
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                    raise HTTPException(422, f"Anotação exige {key} numérico e finito.")
            if not (0 <= ann["x"] < image.image_width and 0 <= ann["y"] < image.image_height
                    and 0 < ann["radius"] <= max(image.image_width, image.image_height)):
                raise HTTPException(422, "Centro ou raio da anotação fora da imagem.")
            confidence = ann.get("confidence", 1.0)
            if not isinstance(confidence, (int, float)) or not math.isfinite(confidence) or not 0 <= confidence <= 1:
                raise HTTPException(422, "Confiança deve ser um número entre 0 e 1.")
            if ann.get("annotation_type", "droplet") not in {"droplet", "droplet_small", "droplet_medium", "droplet_large", "droplet_duplicate", "dirt", "background"}:
                raise HTTPException(422, "Tipo de anotação desconhecido.")
            for key in ("diameter_mm", "intensity_avg", "intensity_std"):
                value = ann.get(key)
                if value is not None and (not isinstance(value, (float, int)) or not math.isfinite(value) or value < 0):
                    raise HTTPException(422, f"{key} inválido na anotação.")

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
                intensity_std=ann_data.get("intensity_std"),
                annotation_type=ann_data.get("annotation_type", "droplet"),
                droplet_size_class=ann_data.get("droplet_size_class"),
                shape_type=ann_data.get("shape_type", "circle"),
                color_profile=ann_data.get("color_profile"),
                auto_adjusted_radius=bool(ann_data.get("auto_adjusted_radius", False)),
                source_tool=ann_data.get("source_tool"),
                mask_points=ann_data.get("mask_points"),
                is_overlapping=ann_data.get("annotation_type") == "droplet_duplicate",
            )
            
            db.add(annotation)
            created_annotations.append(annotation)
        
        # Atualiza status da imagem
        image.is_annotated = len(created_annotations) > 0
        image.is_validated = False
        if pixel_to_mm_ratio is not None:
            image.pixel_to_mm_ratio = pixel_to_mm_ratio
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
                    "annotation_type": ann.annotation_type or "droplet",
                    "droplet_size_class": ann.droplet_size_class,
                    "shape_type": ann.shape_type or "circle",
                    "color_profile": ann.color_profile,
                    "auto_adjusted_radius": ann.auto_adjusted_radius,
                    "source_tool": ann.source_tool,
                    "mask_points": ann.mask_points,
                    "confidence": ann.confidence,
                    "is_overlapping": ann.is_overlapping,
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
        db.flush()
        remaining = db.query(ImageAnnotation).filter(
            ImageAnnotation.image_id == annotation.image_id,
            ImageAnnotation.review_status != "approved",
        ).count()
        annotation.image.is_validated = remaining == 0
        
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
        if isinstance(e, ValidationError):
            raise HTTPException(status_code=422, detail=str(e))
        raise HTTPException(status_code=500, detail="Não foi possível salvar a revisão.")

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
        
        split_total = train_split + val_split + test_split
        if split_total <= 0:
            raise ValidationError("A soma dos splits de treinamento precisa ser maior que zero")

        dataset_split_config = {
            "train": train_split / split_total,
            "validation": val_split / split_total,
            "test": test_split / split_total,
            "total_images": len(training_images),
            "started_by": started_by,
        }

        result = start_ml_training(
            model_id=model_id,
            session_name=session_name,
            total_epochs=total_epochs,
            dataset_split_config=dataset_split_config,
            model_type=model.model_type,
            architecture=model.architecture,
            started_by=started_by,
        )

        if result.get("status") != "success":
            raise HTTPException(status_code=500, detail=result.get("message", "Falha ao iniciar treinamento"))

        logger.info(f"Sessao de treinamento {session_name} iniciada")
        
        return {
            "status": "success",
            "message": "Treinamento iniciado",
            "session_id": result["session_id"],
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

        annotation_types = {}
        for annotation_type, count in db.query(
            ImageAnnotation.annotation_type,
            func.count(ImageAnnotation.id)
        ).group_by(ImageAnnotation.annotation_type).all():
            annotation_types[annotation_type or "droplet"] = count
        
        stats.update({
            "average_annotations_per_image": round(avg_annotations_per_image, 1),
            "annotation_approval_rate": round((approved_annotations / total_annotations * 100), 1) if total_annotations > 0 else 0,
            "annotation_types": annotation_types,
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
                    {"id": 1, "name": "droplet_small", "supercategory": "droplet"},
                    {"id": 2, "name": "droplet_medium", "supercategory": "droplet"},
                    {"id": 3, "name": "droplet_large", "supercategory": "droplet"},
                    {"id": 4, "name": "droplet_duplicate", "supercategory": "quality_issue"},
                    {"id": 5, "name": "dirt", "supercategory": "artifact"}
                ]
            }
            category_map = {item["name"]: item["id"] for item in export_data["categories"]}
            
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
                        category_name = ann.annotation_type or "droplet"
                        if category_name == "droplet":
                            category_name = f"droplet_{ann.droplet_size_class or 'medium'}"
                        category_id = category_map.get(category_name, category_map["droplet_medium"])
                        export_data["annotations"].append({
                            "id": annotation_id,
                            "image_id": img.id,
                            "category_id": category_id,
                            "bbox": [
                                ann.x - ann.radius,
                                ann.y - ann.radius,
                                ann.radius * 2,
                                ann.radius * 2
                            ],
                            "area": ann.area_pixels,
                            "iscrowd": 1 if category_name == "droplet_duplicate" else 0
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
                            "annotation_type": ann.annotation_type or "droplet",
                            "droplet_size_class": ann.droplet_size_class,
                            "confidence": ann.confidence
                        })
            
            return JSONResponse(content={"data": csv_data})
        
        else:
            raise ValidationError("Formato não suportado")
        
    except Exception as e:
        logger.error(f"Erro na exportação: {e}")
        raise HTTPException(status_code=500, detail=str(e))
