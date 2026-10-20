"""Tests must never initialize or contact the user's real data/providers."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SANDBOX = ROOT / ".tools" / "test-data"
for name, value in {
    "DATABASE_URL": "sqlite:///:memory:", "SECRET_KEY": "isolated-test-secret-key",
    "ENVIRONMENT": "development", "DEBUG": "False", "ENABLE_FILE_LOGGING": "False",
    "MODEL_PATH": str(SANDBOX / "models"), "TEMP_UPLOAD_PATH": str(SANDBOX / "uploads"),
    "DATASET_PATH": str(SANDBOX / "dataset"), "AGROFIT_CACHE_PATH": str(SANDBOX / "agrofit"),
    "ENVIRONMENT_CACHE_PATH": str(SANDBOX / "environment"), "LOG_FILE": str(SANDBOX / "logs" / "app.log"),
    "DATABASE_PATH": str(SANDBOX / "unused.db"), "CORS_ORIGINS": '["*"]', "ALLOWED_HOSTS": '["*"]',
    "OPENWEATHER_API_KEY": "", "WEATHERAPI_KEY": "", "OPEN_METEO_API_KEY": "",
    "CLIMATEMPO_TOKEN": "", "AGRO_API_TOKEN": "", "ENABLE_DATASET_API": "False", "ADMIN_API_KEY": "",
}.items():
    os.environ[name] = value
