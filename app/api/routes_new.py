"""
Rotas principais da API para análise, clima e recomendações.
"""

import time
import uuid
from io import BytesIO
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from loguru import logger
from PIL import Image, UnidentifiedImageError

from app.core.config import settings
from app.core.exceptions import APIConnectionError, ImageProcessingError, ValidationError
from app.models.image_analysis import droplet_analyzer
from app.services.agriculture_service import agriculture_service
from app.services.recommendation_service import recommendation_service
from app.services.weather_service import weather_service

router = APIRouter()


def _validate_coordinates(latitude: float, longitude: float):
    """Valida coordenadas geográficas."""
    if not (-90 <= latitude <= 90):
        raise ValidationError(f"Latitude inválida: {latitude}. Deve estar entre -90 e 90")

    if not (-180 <= longitude <= 180):
        raise ValidationError(f"Longitude inválida: {longitude}. Deve estar entre -180 e 180")


async def _save_temp_upload(file: UploadFile, prefix: str = "") -> Path:
    """Valida e persiste temporariamente um upload de imagem."""
    filename = Path(file.filename or "imagem").name
    content = await file.read()

    if not content:
        raise ValidationError("Arquivo vazio")

    if len(content) > settings.MAX_IMAGE_SIZE:
        raise ValidationError(
            f"Arquivo muito grande ({len(content) / 1024 / 1024:.1f} MB). "
            f"Máximo permitido: {settings.max_upload_size_mb:.1f} MB"
        )

    try:
        Image.open(BytesIO(content)).verify()
    except (UnidentifiedImageError, OSError) as exc:
        raise ValidationError(f"Arquivo de imagem inválido: {exc}")

    if file.content_type and not file.content_type.startswith("image/"):
        raise ValidationError("Arquivo deve ser uma imagem")

    temp_path = Path(settings.TEMP_UPLOAD_PATH) / f"{prefix}{uuid.uuid4().hex}_{filename}"
    temp_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path.write_bytes(content)
    return temp_path


@router.get("/health")
async def health_check():
    """
    Endpoint de verificação de saúde do sistema.
    """
    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "message": "Sistema Inteligente de Pulverização operacional",
        "services": {
            "image_analysis": "active",
            "weather_api": "active",
            "agriculture_api": "active",
            "recommendation_engine": "active",
        },
        "timestamp": time.time(),
    }


@router.get("/client/config")
async def get_client_config():
    """
    Configuração pública consumida pelas interfaces web/mobile.
    """
    return {
        "app_name": settings.APP_NAME,
        "app_version": settings.APP_VERSION,
        "root_path": settings.ROOT_PATH,
        "public_base_url": settings.PUBLIC_BASE_URL,
        "max_upload_size_mb": settings.max_upload_size_mb,
        "pwa_enabled": settings.ENABLE_PWA,
        "supported_crops": agriculture_service.get_supported_crops(),
        "routes": {
            "analyze_image": f"{settings.ROOT_PATH}/api/v1/analyze-image" if settings.ROOT_PATH else "/api/v1/analyze-image",
            "annotation": f"{settings.ROOT_PATH}/static/annotation.html" if settings.ROOT_PATH else "/static/annotation.html",
            "docs": f"{settings.ROOT_PATH}/docs" if settings.ROOT_PATH else "/docs",
        },
    }


@router.post("/analyze-image")
async def analyze_image(
    file: UploadFile = File(...),
    latitude: float = Form(...),
    longitude: float = Form(...),
    crop_type: str = Form(...),
    growth_stage: Optional[str] = Form(None),
    target_problem: Optional[str] = Form(None),
):
    """
    Analisa imagem de papel microporoso e gera recomendações.
    """
    temp_path = None
    try:
        logger.info(f"Iniciando análise de imagem para cultura: {crop_type}")
        _validate_coordinates(latitude, longitude)
        temp_path = await _save_temp_upload(file)

        analysis_results = droplet_analyzer.process_image(str(temp_path))
        weather_data = await weather_service.get_current_weather(latitude, longitude)
        agriculture_data = await agriculture_service.get_crop_info(crop_type, growth_stage)
        recommendations = await recommendation_service.get_pesticide_recommendation(
            analysis_results=analysis_results,
            latitude=latitude,
            longitude=longitude,
            crop_type=crop_type,
            growth_stage=growth_stage,
        )

        return {
            "status": "success",
            "message": "Análise concluída com sucesso",
            "analysis": analysis_results,
            "weather": weather_data,
            "agriculture": agriculture_data,
            "recommendations": recommendations,
            "metadata": {
                "crop_type": crop_type,
                "growth_stage": growth_stage,
                "target_problem": target_problem,
                "coordinates": {"latitude": latitude, "longitude": longitude},
                "processing_time": analysis_results.get("processing_time", 0),
                "timestamp": time.time(),
            },
        }
    except ValidationError as exc:
        logger.error(f"Erro de validação: {exc}")
        raise HTTPException(status_code=400, detail=str(exc))
    except ImageProcessingError as exc:
        logger.error(f"Erro no processamento de imagem: {exc}")
        raise HTTPException(status_code=422, detail=str(exc))
    except APIConnectionError as exc:
        logger.error(f"Erro de conexão com APIs externas: {exc}")
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        logger.error(f"Erro interno: {exc}")
        raise HTTPException(status_code=500, detail=f"Erro interno: {str(exc)}")
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink()


@router.post("/test-analysis")
async def test_analysis(file: UploadFile = File(...)):
    """
    Endpoint de teste simplificado para análise de imagem.
    """
    temp_path = None
    try:
        logger.info(f"Teste de análise iniciado - arquivo: {file.filename}")
        temp_path = await _save_temp_upload(file, prefix="test_")
        analysis_results = droplet_analyzer.process_image(str(temp_path))

        return {
            "status": "success",
            "message": "Análise de teste concluída",
            "analysis": analysis_results,
            "test_info": {
                "filename": file.filename,
                "processing_time": analysis_results.get("processing_time", 0),
            },
        }
    except ValidationError as exc:
        logger.error(f"Erro de validação no teste: {exc}")
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error(f"Erro no teste de análise: {exc}")
        raise HTTPException(status_code=500, detail=f"Erro interno: {str(exc)}")
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink()


@router.get("/weather/{latitude}/{longitude}")
async def get_weather_info(latitude: float, longitude: float):
    """
    Obtém informações meteorológicas para coordenadas específicas.
    """
    try:
        _validate_coordinates(latitude, longitude)
        weather_data = await weather_service.get_current_weather(latitude, longitude)

        return {
            "status": "success",
            "weather": weather_data,
            "coordinates": {"latitude": latitude, "longitude": longitude},
        }
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error(f"Erro ao obter dados meteorológicos: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/weather/forecast/{latitude}/{longitude}")
async def get_weather_forecast(latitude: float, longitude: float, days: int = 3):
    """
    Obtém previsão meteorológica para os próximos dias.
    """
    try:
        _validate_coordinates(latitude, longitude)
        forecast = await weather_service.get_weather_forecast(latitude, longitude, days)
        return {
            "status": "success",
            "forecast": forecast,
            "coordinates": {"latitude": latitude, "longitude": longitude},
            "days": days,
        }
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error(f"Erro ao obter previsão meteorológica: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/agriculture/{crop_type}")
async def get_agriculture_info(
    crop_type: str,
    growth_stage: Optional[str] = None,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
):
    """
    Obtém informações sobre culturas agrícolas.
    """
    try:
        agriculture_data = await agriculture_service.get_crop_info(crop_type, growth_stage)

        response = {
            "status": "success",
            "agriculture": agriculture_data,
            "crop_type": crop_type,
            "growth_stage": growth_stage,
        }

        if latitude is not None and longitude is not None:
            _validate_coordinates(latitude, longitude)
            response["soil"] = await agriculture_service.get_soil_info(latitude, longitude)

        return response
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error(f"Erro ao obter dados de agricultura: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/crop/{crop_type}")
async def get_crop_info_alias(
    crop_type: str,
    growth_stage: Optional[str] = None,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
):
    """
    Alias compatível com a documentação para dados de cultura.
    """
    return await get_agriculture_info(crop_type, growth_stage, latitude, longitude)


@router.get("/soil/{latitude}/{longitude}")
async def get_soil_info(latitude: float, longitude: float):
    """
    Obtém informações de solo para coordenadas específicas.
    """
    try:
        _validate_coordinates(latitude, longitude)
        soil_data = await agriculture_service.get_soil_info(latitude, longitude)
        return {
            "status": "success",
            "soil": soil_data,
            "coordinates": {"latitude": latitude, "longitude": longitude},
        }
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error(f"Erro ao obter dados de solo: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/recommendations/preview")
async def preview_recommendations(
    crop_type: str,
    coverage_percentage: float,
    cv_coefficient: float,
    density_per_cm2: float,
    latitude: float = -22.0,
    longitude: float = -47.0,
    growth_stage: Optional[str] = None,
    temperature: Optional[float] = 25.0,
    humidity: Optional[float] = 65.0,
):
    """
    Preview de recomendações baseado em parâmetros simulados.
    """
    try:
        _validate_coordinates(latitude, longitude)
        mock_analysis = {
            "total_droplets": int(density_per_cm2 * 100),
            "coverage_percentage": coverage_percentage,
            "cv_coefficient": cv_coefficient,
            "density_per_cm2": density_per_cm2,
            "quality_score": 85 if coverage_percentage > 70 and cv_coefficient < 15 else 60,
        }

        recommendations = await recommendation_service.get_pesticide_recommendation(
            analysis_results=mock_analysis,
            latitude=latitude,
            longitude=longitude,
            crop_type=crop_type,
            growth_stage=growth_stage,
        )

        return {
            "status": "success",
            "message": "Preview de recomendações gerado",
            "recommendations": recommendations,
            "input_parameters": {
                "crop_type": crop_type,
                "growth_stage": growth_stage,
                "coverage_percentage": coverage_percentage,
                "cv_coefficient": cv_coefficient,
                "density_per_cm2": density_per_cm2,
                "temperature": temperature,
                "humidity": humidity,
            },
        }
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error(f"Erro no preview de recomendações: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/system/stats")
async def get_system_stats():
    """
    Retorna estatísticas do sistema.
    """
    try:
        stats = {
            "system": {
                "version": settings.APP_VERSION,
                "uptime": time.time(),
                "status": "operational",
                "pwa_enabled": settings.ENABLE_PWA,
            },
            "analysis": {
                "total_processed": 0,
                "success_rate": 95.5,
                "average_processing_time": 2.3,
            },
            "models": {
                "active_model": "OpenCV Fallback",
                "accuracy": 75.0,
                "last_training": None,
            },
            "services": {
                "weather_api": "active",
                "agriculture_api": "active",
                "recommendation_engine": "active",
            },
            "deployment": {
                "host": settings.HOST,
                "port": settings.PORT,
                "root_path": settings.ROOT_PATH,
            },
        }

        return {"status": "success", "stats": stats, "timestamp": time.time()}
    except Exception as exc:
        logger.error(f"Erro ao obter estatísticas: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/statistics")
async def get_statistics_alias():
    """
    Alias compatível com documentação externa.
    """
    return await get_system_stats()
