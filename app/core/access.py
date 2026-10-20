"""Access to internal dataset/training tools is independent of public analysis."""

import secrets
from typing import Optional

from fastapi import Header, HTTPException

from app.core.config import settings


def require_admin_access(x_api_key: Optional[str] = Header(None)) -> None:
    """Keep annotation, dataset and training private unless explicitly configured."""
    if not settings.ENABLE_DATASET_API or not settings.ADMIN_API_KEY:
        raise HTTPException(403, "Ferramentas internas desativadas neste ambiente.")
    if not x_api_key or not secrets.compare_digest(x_api_key, settings.ADMIN_API_KEY):
        raise HTTPException(401, "Chave de acesso às ferramentas internas inválida.")
