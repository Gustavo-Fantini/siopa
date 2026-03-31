"""
Relatório de prontidão e execução do sistema.
"""

import os
from pathlib import Path
from typing import Any, Dict, List

from app.core.config import Settings


DEFAULT_SECRET_VALUES = {
    "",
    "CHANGE_ME",
    "change-me",
    "changeme",
    "your-secret-key-change-in-production",
}


def _path_status(path: Path) -> Dict[str, Any]:
    """Resume existência e escrita de um caminho local."""
    return {
        "path": str(path),
        "exists": path.exists(),
        "writable": path.exists() and os.access(path, os.W_OK),
    }


def build_runtime_report(settings: Settings) -> Dict[str, Any]:
    """Gera um relatório objetivo de prontidão para deploy e operação."""
    api_providers = {
        "openweather": bool(settings.OPENWEATHER_API_KEY),
        "weatherapi": bool(settings.WEATHERAPI_KEY),
        "climatempo": bool(settings.CLIMATEMPO_TOKEN),
        "embrapa": bool(settings.EMBRAPA_API_KEY),
        "agro_api": bool(settings.AGRO_API_TOKEN),
        "google_maps": bool(settings.GOOGLE_MAPS_API_KEY),
    }
    storage_paths = {
        "models": _path_status(Path(settings.MODEL_PATH)),
        "temp_uploads": _path_status(Path(settings.TEMP_UPLOAD_PATH)),
        "dataset": _path_status(Path(settings.DATASET_PATH)),
        "logs": _path_status(Path(settings.LOG_FILE).parent),
    }

    secret_key_configured = settings.SECRET_KEY not in DEFAULT_SECRET_VALUES
    cors_locked_down = "*" not in settings.CORS_ORIGINS
    allowed_hosts_locked_down = "*" not in settings.ALLOWED_HOSTS
    weather_provider_configured = any(
        api_providers[name] for name in ("openweather", "weatherapi", "climatempo")
    )

    warnings: List[str] = []
    if not secret_key_configured:
        warnings.append("SECRET_KEY ainda está com valor padrão ou vazio.")
    if settings.is_production and not cors_locked_down:
        warnings.append("CORS_ORIGINS ainda aceita qualquer origem em produção.")
    if settings.is_production and not allowed_hosts_locked_down:
        warnings.append("ALLOWED_HOSTS ainda aceita qualquer host em produção.")
    if not settings.PUBLIC_BASE_URL:
        warnings.append("PUBLIC_BASE_URL não foi definida; links públicos e PWA podem ficar inconsistentes.")
    if not weather_provider_configured:
        warnings.append("Nenhum provedor climático foi configurado.")

    return {
        "ready": secret_key_configured and all(item["exists"] for item in storage_paths.values()),
        "environment": settings.ENVIRONMENT,
        "application": {
            "name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "debug": settings.DEBUG,
            "workers": settings.WORKERS,
            "root_path": settings.ROOT_PATH,
            "public_base_url": settings.PUBLIC_BASE_URL,
            "pwa_enabled": settings.ENABLE_PWA,
        },
        "database": {
            "backend": settings.database_backend,
            "url_masked": settings.resolved_database_url.split("@")[-1]
            if "@" in settings.resolved_database_url
            else settings.resolved_database_url,
            "sqlite_path": str(settings.sqlite_database_path) if settings.sqlite_database_path else None,
        },
        "security": {
            "secret_key_configured": secret_key_configured,
            "cors_locked_down": cors_locked_down,
            "allowed_hosts_locked_down": allowed_hosts_locked_down,
            "file_logging_enabled": settings.ENABLE_FILE_LOGGING,
        },
        "integrations": api_providers,
        "storage": storage_paths,
        "warnings": warnings,
    }
