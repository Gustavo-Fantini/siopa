"""
Configurações centrais do sistema.
"""

import json
from pathlib import Path
from typing import List, Optional, Tuple

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configurações da aplicação."""

    # Aplicação
    APP_NAME: str = "Sistema Inteligente Pulverização"
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    ROOT_PATH: str = ""
    PUBLIC_BASE_URL: Optional[str] = None
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ENABLE_PWA: bool = True

    # Banco de dados
    DATABASE_URL: Optional[str] = None
    DATABASE_PATH: str = "data/app.db"

    # APIs meteorológicas
    OPENWEATHER_API_KEY: Optional[str] = None
    WEATHERAPI_KEY: Optional[str] = None
    CLIMATEMPO_TOKEN: Optional[str] = None

    # APIs de solo e agricultura
    EMBRAPA_API_KEY: Optional[str] = None
    AGRO_API_TOKEN: Optional[str] = None

    # APIs de geolocalização
    GOOGLE_MAPS_API_KEY: Optional[str] = None
    IBGE_API_URL: str = "https://servicodados.ibge.gov.br/api/v1"

    # Caminhos
    MODEL_PATH: str = "data/models"
    TEMP_UPLOAD_PATH: str = "data/temp/uploads"
    DATASET_PATH: str = "data/dataset"
    LOG_FILE: str = "logs/app.log"

    # Logging
    LOG_LEVEL: str = "INFO"

    # Segurança
    CORS_ORIGINS: List[str] = ["*"]
    ALLOWED_HOSTS: List[str] = ["*"]
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Configurações de processamento
    MAX_WORKERS: int = 4
    BATCH_SIZE: int = 32
    IMAGE_SIZE: Tuple[int, int] = (512, 512)
    PIXEL_TO_MM: float = 0.1
    DROPLET_COVERAGE_SCALE: float = 1.3

    # Configurações de upload e treinamento
    MAX_IMAGE_SIZE: int = 10 * 1024 * 1024
    MIN_TRAINING_IMAGES: int = 5

    @field_validator("CORS_ORIGINS", "ALLOWED_HOSTS", mode="before")
    @classmethod
    def parse_list_fields(cls, value):
        """Aceita lista, JSON ou string separada por vírgula."""
        if isinstance(value, list):
            return value
        if value is None:
            return []
        if isinstance(value, str):
            raw_value = value.strip()
            if not raw_value:
                return []
            if raw_value.startswith("["):
                try:
                    parsed = json.loads(raw_value)
                    if isinstance(parsed, list):
                        return [str(item).strip() for item in parsed if str(item).strip()]
                except json.JSONDecodeError:
                    pass
            return [item.strip() for item in raw_value.split(",") if item.strip()]
        return value

    @field_validator("ROOT_PATH", mode="before")
    @classmethod
    def normalize_root_path(cls, value):
        """Normaliza o root path para uso atrás de proxy reverso."""
        if value in (None, "", "/"):
            return ""
        raw_value = str(value).strip()
        return raw_value if raw_value.startswith("/") else f"/{raw_value}"

    @field_validator("PUBLIC_BASE_URL", mode="before")
    @classmethod
    def normalize_public_base_url(cls, value):
        """Remove barra final da URL pública quando informada."""
        if value in (None, ""):
            return None
        return str(value).strip().rstrip("/")

    @field_validator(
        "MODEL_PATH",
        "TEMP_UPLOAD_PATH",
        "DATASET_PATH",
        "LOG_FILE",
        "DATABASE_PATH",
        mode="before",
    )
    @classmethod
    def create_directories(cls, value):
        """Cria diretórios se não existirem."""
        if value in (None, ""):
            return value

        path = Path(str(value))
        if path.suffix in {".log", ".db", ".sqlite", ".sqlite3"}:
            path.parent.mkdir(parents=True, exist_ok=True)
        else:
            path.mkdir(parents=True, exist_ok=True)
        return str(path)

    @property
    def resolved_database_url(self) -> str:
        """Resolve a URL efetiva do banco de dados."""
        if self.DATABASE_URL:
            return self.DATABASE_URL

        normalized_path = str(Path(self.DATABASE_PATH)).replace("\\", "/")
        return f"sqlite:///{normalized_path}"

    @property
    def sqlite_database_path(self) -> Optional[Path]:
        """Retorna o caminho do arquivo quando o banco configurado é SQLite."""
        database_url = self.resolved_database_url
        if not database_url.startswith("sqlite:///"):
            return None

        return Path(database_url.removeprefix("sqlite:///"))

    @property
    def max_upload_size_mb(self) -> float:
        """Retorna o tamanho máximo de upload em MB."""
        return round(self.MAX_IMAGE_SIZE / 1024 / 1024, 2)

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")


settings = Settings()
