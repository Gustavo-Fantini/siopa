"""
Aplicação principal FastAPI do sistema.
"""

import sys
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger
from starlette.middleware.trustedhost import TrustedHostMiddleware

sys.path.append(str(Path(__file__).parent))

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "app" / "static"

from app.api.dataset_routes import router as dataset_router
from app.api.routes_new import router
from app.core.config import settings
from app.core.database import init_database
from app.core.exceptions import setup_exception_handlers
from app.utils.logger import setup_logging


load_dotenv()

APP_DESCRIPTION = """
Sistema desenvolvido para TCC e iniciação científica com foco em:
- análise automatizada de papel hidrossensível;
- integração climática e agronômica;
- recomendações inteligentes para aplicação;
- interface web responsiva pronta para acesso mobile.
"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Prepara infraestrutura compartilhada na subida da aplicação."""
    setup_logging()
    init_database()
    logger.info("Aplicação inicializada")
    yield
    logger.info("Aplicação finalizada")


def create_app() -> FastAPI:
    """Cria e configura a aplicação FastAPI."""
    app = FastAPI(
        title=settings.APP_NAME,
        description=APP_DESCRIPTION,
        version=settings.APP_VERSION,
        docs_url="/docs",
        redoc_url="/redoc",
        root_path=settings.ROOT_PATH,
        lifespan=lifespan,
    )

    cors_origins = settings.CORS_ORIGINS or ["*"]
    wildcard_cors = "*" in cors_origins

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=not wildcard_cors,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(GZipMiddleware, minimum_size=512)

    allowed_hosts = settings.ALLOWED_HOSTS or ["*"]
    if "*" not in allowed_hosts:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)

    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    app.include_router(router, prefix="/api/v1")
    app.include_router(dataset_router, prefix="/api/v1")
    setup_exception_handlers(app)

    @app.get("/favicon.ico")
    async def favicon():
        return {"message": "No favicon"}

    @app.get("/service-worker.js")
    async def service_worker():
        return FileResponse(
            str(STATIC_DIR / "service-worker.js"),
            media_type="application/javascript",
            headers={"Service-Worker-Allowed": settings.ROOT_PATH or "/"},
        )

    @app.get("/manifest.webmanifest")
    async def manifest():
        return FileResponse(str(STATIC_DIR / "manifest.webmanifest"), media_type="application/manifest+json")

    @app.get("/icon.svg")
    async def app_icon():
        return FileResponse(str(STATIC_DIR / "icon.svg"), media_type="image/svg+xml")

    @app.get("/", response_class=HTMLResponse)
    async def read_root():
        """Página principal da aplicação."""
        try:
            html_file = STATIC_DIR / "index.html"
            if html_file.exists():
                return html_file.read_text(encoding="utf-8")
            raise FileNotFoundError("app/static/index.html não encontrado")
        except Exception as exc:
            logger.error(f"Erro ao carregar página principal: {exc}")
            raise HTTPException(status_code=500, detail="Erro interno do servidor")

    @app.get("/health")
    async def health_check():
        """Verificação de saúde do sistema."""
        return {
            "status": "healthy",
            "app_name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "root_path": settings.ROOT_PATH,
            "pwa_enabled": settings.ENABLE_PWA,
        }

    return app


def main():
    """Função principal para execução local/servidor."""
    try:
        logger.info("Iniciando aplicação FastAPI")
        uvicorn.run(
            "main:create_app",
            factory=True,
            host=settings.HOST,
            port=settings.PORT,
            reload=settings.DEBUG,
            log_level=settings.LOG_LEVEL.lower(),
            limit_max_requests=10000,
            timeout_keep_alive=30,
            proxy_headers=True,
            forwarded_allow_ips="*",
            server_header=False,
        )
    except KeyboardInterrupt:
        logger.info("Servidor interrompido pelo usuário")
    except Exception as exc:
        logger.error(f"Erro fatal ao iniciar servidor: {exc}")
        raise


if __name__ == "__main__":
    main()
