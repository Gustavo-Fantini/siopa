"""
Sistema de logging configurado com Loguru
"""

import sys
from pathlib import Path
from loguru import logger
from app.core.config import settings

def setup_logging():
    """Configura o sistema de logging"""
    
    # Remove handler padrão
    logger.remove()
    
    # Configuração para console
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=settings.LOG_LEVEL,
        colorize=True
    )
    
    # Configuração para arquivo
    log_path = Path(settings.LOG_FILE)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    logger.add(
        str(log_path),
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level=settings.LOG_LEVEL,
        rotation="10 MB",
        retention="30 days",
        compression="zip"
    )
    
    # Log de inicialização
    logger.info("Sistema de logging configurado")
    logger.info(f"Nível de log: {settings.LOG_LEVEL}")
    logger.info(f"Arquivo de log: {log_path}")

def log_function_call(func_name: str, params: dict = None):
    """Log de chamada de função"""
    params_str = f" com parâmetros: {params}" if params else ""
    logger.debug(f"Chamando função: {func_name}{params_str}")

def log_api_call(api_name: str, endpoint: str, status_code: int = None, response_time: float = None):
    """Log de chamada de API"""
    msg = f"API {api_name} - {endpoint}"
    if status_code:
        msg += f" - Status: {status_code}"
    if response_time:
        msg += f" - Tempo: {response_time:.2f}s"
    logger.info(msg)

def log_error_with_context(error: Exception, context: dict = None):
    """Log de erro com contexto adicional"""
    logger.error(f"Erro: {str(error)}")
    if context:
        logger.error(f"Contexto: {context}")
    logger.exception("Detalhes do erro:")
