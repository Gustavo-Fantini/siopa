"""
Sistema de tratamento de exceções personalizado
"""

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from loguru import logger
import traceback
from typing import Any, Dict
from datetime import datetime

class CustomException(Exception):
    """Exceção base personalizada"""
    def __init__(self, message: str, error_code: str = None, details: Dict[str, Any] = None):
        self.message = message
        self.error_code = error_code or "GENERIC_ERROR"
        self.details = details or {}
        super().__init__(self.message)

class ImageProcessingError(CustomException):
    """Erro no processamento de imagens"""
    def __init__(self, message: str, details: Dict[str, Any] = None):
        super().__init__(message, "IMAGE_PROCESSING_ERROR", details)

class ModelLoadError(CustomException):
    """Erro no carregamento do modelo"""
    def __init__(self, message: str, details: Dict[str, Any] = None):
        super().__init__(message, "MODEL_LOAD_ERROR", details)

class APIConnectionError(CustomException):
    """Erro de conexão com APIs externas"""
    def __init__(self, message: str, api_name: str = None, details: Dict[str, Any] = None):
        details = details or {}
        if api_name:
            details["api_name"] = api_name
        super().__init__(message, "API_CONNECTION_ERROR", details)

class ValidationError(CustomException):
    """Erro de validação de dados"""
    def __init__(self, message: str, field: str = None, details: Dict[str, Any] = None):
        details = details or {}
        if field:
            details["field"] = field
        super().__init__(message, "VALIDATION_ERROR", details)

class DatabaseError(CustomException):
    """Erro de banco de dados"""
    def __init__(self, message: str, details: Dict[str, Any] = None):
        super().__init__(message, "DATABASE_ERROR", details)

class FileProcessingError(CustomException):
    """Erro no processamento de arquivos"""
    def __init__(self, message: str, filename: str = None, details: Dict[str, Any] = None):
        details = details or {}
        if filename:
            details["filename"] = filename
        super().__init__(message, "FILE_PROCESSING_ERROR", details)

async def custom_exception_handler(request: Request, exc: CustomException):
    """Handler para exceções personalizadas"""
    logger.error(f"Exceção personalizada: {exc.error_code} - {exc.message}")
    logger.error(f"Detalhes: {exc.details}")
    logger.error(f"URL: {request.url}")
    
    return JSONResponse(
        status_code=400,
        content={
            "error": True,
            "error_code": exc.error_code,
            "message": exc.message,
            "details": exc.details,
            "timestamp": datetime.now().isoformat(),
            "path": str(request.url.path)
        }
    )

async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Handler para exceções HTTP"""
    logger.warning(f"HTTP Exception: {exc.status_code} - {exc.detail}")
    logger.warning(f"URL: {request.url}")
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "error_code": f"HTTP_{exc.status_code}",
            "message": exc.detail,
            "timestamp": datetime.now().isoformat(),
            "path": str(request.url.path)
        }
    )

async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handler para erros de validação"""
    logger.error(f"Erro de validação: {exc.errors()}")
    logger.error(f"URL: {request.url}")
    
    errors = []
    for error in exc.errors():
        errors.append({
            "field": " -> ".join(str(x) for x in error["loc"]),
            "message": error["msg"],
            "type": error["type"]
        })
    
    return JSONResponse(
        status_code=422,
        content={
            "error": True,
            "error_code": "VALIDATION_ERROR",
            "message": "Dados de entrada inválidos",
            "details": {"validation_errors": errors},
            "timestamp": datetime.now().isoformat(),
            "path": str(request.url.path)
        }
    )

async def general_exception_handler(request: Request, exc: Exception):
    """Handler geral para exceções não tratadas"""
    error_id = f"err_{int(datetime.now().timestamp())}"
    
    logger.error(f"Erro não tratado [{error_id}]: {str(exc)}")
    logger.error(f"Traceback: {traceback.format_exc()}")
    logger.error(f"URL: {request.url}")
    
    return JSONResponse(
        status_code=500,
        content={
            "error": True,
            "error_code": "INTERNAL_SERVER_ERROR",
            "message": "Erro interno do servidor. Contate o suporte técnico.",
            "details": {
                "error_id": error_id,
                "type": type(exc).__name__
            },
            "timestamp": datetime.now().isoformat(),
            "path": str(request.url.path)
        }
    )

def setup_exception_handlers(app: FastAPI):
    """Configura todos os handlers de exceção"""
    
    # Handlers personalizados
    app.add_exception_handler(CustomException, custom_exception_handler)
    app.add_exception_handler(ImageProcessingError, custom_exception_handler)
    app.add_exception_handler(ModelLoadError, custom_exception_handler)
    app.add_exception_handler(APIConnectionError, custom_exception_handler)
    app.add_exception_handler(ValidationError, custom_exception_handler)
    app.add_exception_handler(DatabaseError, custom_exception_handler)
    app.add_exception_handler(FileProcessingError, custom_exception_handler)
    
    # Handlers padrão
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)
    
    logger.info("Handlers de exceção configurados")
