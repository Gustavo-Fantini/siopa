"""Public analysis and versioned offline packages; network data is optional."""

import asyncio
import hashlib
import json
import math
import time
import uuid
import warnings
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from loguru import logger
from PIL import Image, UnidentifiedImageError
from starlette.concurrency import run_in_threadpool

from app.core.access import require_admin_access
from app.core.config import settings
from app.core.exceptions import ImageProcessingError, ValidationError
from app.core.runtime import build_runtime_report
from app.models.image_analysis import droplet_analyzer
from app.services.agriculture_service import agriculture_service
from app.services.agrofit_service import agrofit_service
from app.services.crop_catalog import crop_catalog
from app.services.environmental_service import environmental_service
from app.services.recommendation_service import recommendation_service
from app.services.spray_quality import ENGINE_VERSION, SCREENING_PROFILE, evaluate_quality
from app.services.weather_service import weather_service

router = APIRouter()
_started = time.monotonic()
_stats = {"completed": 0, "failed": 0, "processing_seconds": 0.0}


def _validate_coordinates(latitude, longitude):
    if latitude is None and longitude is None:
        return
    if latitude is None or longitude is None:
        raise ValidationError("Informe latitude e longitude juntas, ou deixe ambas vazias.")
    if not math.isfinite(latitude) or not -90 <= latitude <= 90:
        raise ValidationError("Latitude inválida; use um número entre -90 e 90.")
    if not math.isfinite(longitude) or not -180 <= longitude <= 180:
        raise ValidationError("Longitude inválida; use um número entre -180 e 180.")


def _verify_image(content):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(content)) as image:
                if image.width * image.height > settings.MAX_IMAGE_PIXELS:
                    raise ValidationError("Imagem excede o limite de pixels; reduza a resolução da foto.")
                image_format = image.format
                if image_format not in {"JPEG", "PNG", "WEBP", "BMP", "TIFF"}:
                    raise ValidationError("Use uma foto JPEG, PNG, WebP, BMP ou TIFF.")
                image.verify()
                return {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp", "BMP": ".bmp", "TIFF": ".tiff"}[image_format]
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ValidationError("Imagem inválida ou grande demais para análise.") from exc


async def _save_temp_upload(file: UploadFile, prefix=""):
    content = await file.read(settings.MAX_IMAGE_SIZE + 1)
    if not content or len(content) > settings.MAX_IMAGE_SIZE:
        raise ValidationError(f"Envie uma imagem não vazia de até {settings.max_upload_size_mb} MB.")
    suffix = await run_in_threadpool(_verify_image, content)
    path = Path(settings.TEMP_UPLOAD_PATH) / f"{prefix}{uuid.uuid4().hex}{suffix}"
    path.parent.mkdir(parents=True, exist_ok=True)
    await run_in_threadpool(path.write_bytes, content)
    return path


def _profile(raw):
    if not raw:
        return None
    if len(raw) > 8192:
        raise ValidationError("Perfil de avaliação grande demais.")
    try:
        value = json.loads(raw, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (ValueError, TypeError) as exc:
        raise ValidationError("Perfil de avaliação deve ser um objeto JSON válido.") from exc
    if not isinstance(value, dict):
        raise ValidationError("Perfil de avaliação deve ser um objeto JSON.")
    fields = ("coverageMin", "coverageTarget", "coverageMax", "densityMin", "densityTarget", "densityMax", "uniformityCvMax")
    for name in fields:
        number = value.get(name)
        if isinstance(number, bool) or not isinstance(number, (int, float)) or not math.isfinite(number):
            raise ValidationError(f"Informe o parâmetro numérico finito {name} no perfil.")
    if not (0 <= value["coverageMin"] < value["coverageTarget"] < value["coverageMax"] <= 100
            and 0 <= value["densityMin"] < value["densityTarget"] < value["densityMax"] <= 100000
            and 0 < value["uniformityCvMax"] <= 10000):
        raise ValidationError("Perfil exige mínimo < alvo < máximo e CV máximo positivo.")
    value["confirmed"] = value.get("confirmed") is True
    return value


def _no_environment():
    return {"availability": "not_requested", "weather": {"current": None, "forecast": [], "availability": "unavailable"},
            "soil": {"availability": "unavailable", "properties": {}},
            "terrain": {"availability": "unavailable", "elevation_m": None},
            "provenance": [], "fetched_at": None, "expires_at": None, "stale": False}


@router.get("/health")
async def health_check():
    return {"status": "healthy", "version": settings.APP_VERSION, "engine_version": ENGINE_VERSION,
            "external_providers": "checked_on_request", "timestamp": time.time()}


@router.get("/client/config")
async def get_client_config():
    base = settings.ROOT_PATH
    return {"app_name": settings.APP_NAME, "app_version": settings.APP_VERSION, "engine_version": ENGINE_VERSION,
            "root_path": base, "public_base_url": settings.PUBLIC_BASE_URL,
            "max_upload_size_mb": settings.max_upload_size_mb, "pwa_enabled": settings.ENABLE_PWA,
            "local_analysis": True, "dataset_enabled": settings.ENABLE_DATASET_API,
            "supported_crops": crop_catalog.list_crops(),
            "routes": {"analyze_image": f"{base}/api/v1/analyze-image", "bootstrap": f"{base}/api/v1/offline/bootstrap",
                       "annotation": f"{base}/static/annotation.html", "docs": f"{base}/docs"}}


@router.get("/offline/bootstrap")
async def offline_bootstrap(latitude: Optional[float] = None, longitude: Optional[float] = None):
    """Only catalogue/context are synchronized. No image is needed or uploaded."""
    try:
        _validate_coordinates(latitude, longitude)
        metadata = crop_catalog.metadata()
        crops = crop_catalog.list_crops()
        digest = hashlib.sha256(json.dumps({"crops": crops, "metadata": metadata}, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]
        environment = await environmental_service.get_context(latitude, longitude) if latitude is not None else _no_environment()
        return {**metadata, "schema_version": 1, "generated_at": datetime.now(timezone.utc).isoformat(),
                "catalog_version": digest, "engine_version": ENGINE_VERSION, "crops": crops,
                "quality_profiles": {**metadata["quality_profiles"], "experimental-screening": SCREENING_PROFILE},
                "environment": environment,
                "paper_defaults": {"paperWidthMm": settings.MICROPOROUS_PAPER_WIDTH_MM,
                                   "paperHeightMm": settings.MICROPOROUS_PAPER_HEIGHT_MM,
                                   "paperSizeConfirmed": False, "minStainDiameterMm": settings.MIN_STAIN_DIAMETER_MM},
                "capabilities": {"offline_analysis": True, "offline_history": True, "local_crop_catalog": True,
                                 "dataset_api": settings.ENABLE_DATASET_API,
                                 "pesticide_dosage_inference": False, "server_receives_photos_for_sync": False}}
    except ValidationError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/environment/{latitude}/{longitude}")
async def get_environment(latitude: float, longitude: float):
    try:
        _validate_coordinates(latitude, longitude)
        return await environmental_service.get_context(latitude, longitude)
    except ValidationError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/crops")
async def get_crops():
    return {**crop_catalog.metadata(), "crops": crop_catalog.list_crops()}


@router.post("/analyze-image")
async def analyze_image(
    file: UploadFile = File(...), latitude: Optional[float] = Form(None), longitude: Optional[float] = Form(None),
    crop_type: str = Form("soja"), growth_stage: Optional[str] = Form(None), target_problem: Optional[str] = Form(None),
    paper_width_mm: float = Form(76.0, gt=0, le=1000), paper_height_mm: float = Form(26.0, gt=0, le=1000),
    paper_size_confirmed: bool = Form(False), min_stain_diameter_mm: float = Form(0.10, gt=0, le=10),
    quality_profile: Optional[str] = Form(None),
):
    temp_path = None
    try:
        _validate_coordinates(latitude, longitude)
        options = {"paperWidthMm": paper_width_mm, "paperHeightMm": paper_height_mm,
                   "paperSizeConfirmed": paper_size_confirmed, "minStainDiameterMm": min_stain_diameter_mm,
                   "profile": _profile(quality_profile)}
        if not crop_catalog.get_crop(crop_type):
            raise ValidationError("Cultura não encontrada no catálogo local.")
        temp_path = await _save_temp_upload(file)
        context_task = environmental_service.get_context(latitude, longitude) if latitude is not None else asyncio.sleep(0, result=_no_environment())
        analysis, environment = await asyncio.gather(
            run_in_threadpool(droplet_analyzer.process_image, str(temp_path), options=options), context_task,
        )
        crop = await agriculture_service.get_crop_info(crop_type, growth_stage)
        current_weather = (environment.get("weather") or {}).get("current") or {}
        advice = recommendation_service.build_recommendation(
            analysis, crop_type, growth_stage, target_problem, current_weather, crop, environment.get("soil"),
        )
        _stats["completed"] += 1
        _stats["processing_seconds"] += analysis.get("processing_time", 0)
        return {"status": "success", "message": "Deposição analisada; confira a calibração e as marcações.",
                "analysis": analysis, "environment": environment, "weather": current_weather,
                "agriculture": crop, "recommendations": advice,
                "metadata": {"crop_type": crop_type, "growth_stage": growth_stage, "target_problem": target_problem,
                             "coordinates": {"latitude": latitude, "longitude": longitude}, "engine_version": ENGINE_VERSION,
                             "timestamp": datetime.now(timezone.utc).isoformat()}}
    except ValidationError as exc:
        raise HTTPException(400, str(exc)) from exc
    except ImageProcessingError as exc:
        _stats["failed"] += 1
        raise HTTPException(422, str(exc)) from exc
    except Exception:
        _stats["failed"] += 1
        logger.exception("Falha na análise de imagem")
        raise HTTPException(500, "Não foi possível concluir a análise.")
    finally:
        if temp_path:
            temp_path.unlink(missing_ok=True)


@router.post("/test-analysis")
async def test_analysis(file: UploadFile = File(...)):
    # An uncalibrated upload can count candidates but cannot assert physical units.
    return await analyze_image(file, None, None, "soja", None, None, 76.0, 26.0, False, 0.10, None)


@router.get("/weather/{latitude}/{longitude}")
async def get_weather_info(latitude: float, longitude: float):
    try:
        _validate_coordinates(latitude, longitude)
        return {"status": "success", "weather": await weather_service.get_current_weather(latitude, longitude)}
    except ValidationError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/weather/forecast/{latitude}/{longitude}")
async def get_weather_forecast(latitude: float, longitude: float, days: int = Query(3, ge=1, le=7)):
    try:
        _validate_coordinates(latitude, longitude)
        return {"status": "success", "days": days, "forecast": await weather_service.get_weather_forecast(latitude, longitude, days)}
    except ValidationError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/agriculture/{crop_type}")
async def get_agriculture_info(crop_type: str, growth_stage: Optional[str] = None,
                               latitude: Optional[float] = None, longitude: Optional[float] = None):
    try:
        _validate_coordinates(latitude, longitude)
        if not crop_catalog.get_crop(crop_type):
            raise HTTPException(404, "Cultura não encontrada.")
        crop = await agriculture_service.get_crop_info(crop_type, growth_stage)
        response = {"status": "success", "agriculture": crop, "crop_type": crop_type, "growth_stage": growth_stage}
        if latitude is not None:
            response["environment"] = await environmental_service.get_context(latitude, longitude)
            response["soil"] = response["environment"]["soil"]
        return response
    except ValidationError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/crop/{crop_type}")
async def get_crop_info_alias(crop_type: str, growth_stage: Optional[str] = None,
                              latitude: Optional[float] = None, longitude: Optional[float] = None):
    return await get_agriculture_info(crop_type, growth_stage, latitude, longitude)


@router.get("/soil/{latitude}/{longitude}")
async def get_soil_info(latitude: float, longitude: float):
    try:
        _validate_coordinates(latitude, longitude)
        return {"status": "success", "soil": await environmental_service.get_soil(latitude, longitude)}
    except ValidationError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/agrofit/products")
async def search_agrofit_products(crop_type: Optional[str] = None, active_ingredient: Optional[str] = None,
                                  product_name: Optional[str] = None, category: Optional[str] = None,
                                  limit: int = Query(50, ge=1, le=500)):
    try:
        return await run_in_threadpool(agrofit_service.search_products, crop_type=crop_type,
                                      active_ingredient=active_ingredient, product_name=product_name,
                                      category=category, limit=limit, refresh=False)
    except Exception:
        raise HTTPException(503, "Catálogo AGROFIT indisponível.")


@router.post("/agrofit/sync", dependencies=[Depends(require_admin_access)])
async def sync_agrofit_products(force: bool = False):
    try:
        return await run_in_threadpool(agrofit_service.sync_products, force=force)
    except Exception:
        raise HTTPException(503, "Não foi possível sincronizar AGROFIT.")


@router.get("/recommendations/preview")
async def preview_recommendations(crop_type: str, coverage_percentage: float = Query(..., ge=0, le=100),
                                  cv_coefficient: float = Query(..., ge=0, le=10000),
                                  density_per_cm2: float = Query(..., ge=0, le=100000),
                                  latitude: Optional[float] = None, longitude: Optional[float] = None,
                                  growth_stage: Optional[str] = None, temperature: Optional[float] = None,
                                  humidity: Optional[float] = None):
    """Explicit simulation of the profile; no fabricated live weather or precision."""
    try:
        _validate_coordinates(latitude, longitude)
        metrics = {"total_droplets": 1 if density_per_cm2 > 0 else 0,
                   "coverage_percentage": coverage_percentage, "density_per_cm2": density_per_cm2,
                   "spatial_uniformity": {"cv": cv_coefficient}, "calibration": {"valid": True, "confirmed": False}}
        metrics["quality"] = evaluate_quality(metrics)
        metrics["quality"]["status"] = "simulated"
        advice = recommendation_service.build_recommendation(metrics, crop_type, growth_stage)
        return {"status": "simulation", "recommendations": advice,
                "input_parameters": {"coverage_percentage": coverage_percentage, "spatial_cv": cv_coefficient,
                                     "density_per_cm2": density_per_cm2, "temperature": temperature, "humidity": humidity}}
    except ValidationError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/system/stats")
async def get_system_stats():
    completed = _stats["completed"]
    return {"status": "success", "stats": {"scope": "current_server_process_only; local_phone_analyses_not_collected",
            "system": {"version": settings.APP_VERSION, "uptime_seconds": round(time.monotonic() - _started, 2)},
            "analysis": {"total_processed": completed, "failed": _stats["failed"],
                         "average_processing_time": _stats["processing_seconds"] / completed if completed else None},
            "models": {"engine": ENGINE_VERSION, "measured_accuracy": None}}, "timestamp": time.time()}


@router.get("/system/runtime")
async def get_runtime_summary():
    return {"status": "success", "runtime": build_runtime_report(settings), "timestamp": time.time()}


@router.get("/statistics")
async def get_statistics_alias():
    return await get_system_stats()
