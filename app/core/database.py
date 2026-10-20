"""
Configuração e gerenciamento da base de dados.
"""

from pathlib import Path
from typing import Generator

from loguru import logger
from sqlalchemy import MetaData, create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.engine import make_url

from app.core.config import settings
from app.models.database import Base


def _build_engine():
    """Cria a engine do SQLAlchemy respeitando a configuração atual."""
    database_url = settings.resolved_database_url

    connect_args = {}
    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
        sqlite_path = settings.sqlite_database_path
        if sqlite_path is not None:
            sqlite_path.parent.mkdir(parents=True, exist_ok=True)

    return create_engine(
        database_url,
        connect_args=connect_args,
        echo=settings.DEBUG,
        future=True,
        pool_pre_ping=not database_url.startswith("sqlite"),
    )


engine = _build_engine()
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,
)
metadata = MetaData()


def init_database():
    """
    Inicializa o banco de dados criando todas as tabelas.
    """
    try:
        logger.info("Inicializando banco de dados: {}", settings.database_backend)

        sqlite_path = settings.sqlite_database_path
        if sqlite_path is not None:
            sqlite_path.parent.mkdir(parents=True, exist_ok=True)

        Base.metadata.create_all(bind=engine)
        _apply_lightweight_migrations()
        _create_initial_data()

        logger.info("Banco de dados inicializado com sucesso")
    except Exception as exc:
        logger.error(f"Erro ao inicializar banco de dados: {exc}")
        raise


def get_db() -> Generator[Session, None, None]:
    """
    Dependency para obter sessão do banco de dados.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _create_initial_data():
    """
    Cria dados iniciais necessários no banco.
    """
    db = SessionLocal()
    try:
        from app.models.database import MLModel

        existing_models = db.query(MLModel).count()
        if existing_models > 0:
            return

        logger.info("Criando dados iniciais...")
        opencv_model = MLModel(
            name="OpenCV Fallback",
            version="1.0.0",
            model_type="segmentation",
            architecture="opencv_adaptive_threshold",
            description="Modelo fallback baseado em OpenCV para segmentação de gotículas",
            is_active=True,
            # No measured performance is assigned to a fallback without an experiment.
        )

        db.add(opencv_model)
        db.commit()
        logger.info("Dados iniciais criados com sucesso")
    except Exception as exc:
        db.rollback()
        logger.warning(f"Erro ao criar dados iniciais: {exc}")
    finally:
        db.close()


def _apply_lightweight_migrations():
    """Add backward-compatible columns for existing SQLite/Postgres databases."""
    try:
        inspector = inspect(engine)
        if "image_annotations" not in inspector.get_table_names():
            return

        existing_columns = {
            column["name"]
            for column in inspector.get_columns("image_annotations")
        }
        required_columns = {
            "annotation_type": "VARCHAR(50) DEFAULT 'droplet'",
            "droplet_size_class": "VARCHAR(20)",
            "shape_type": "VARCHAR(20) DEFAULT 'circle'",
            "color_profile": "JSON",
            "auto_adjusted_radius": "BOOLEAN DEFAULT FALSE",
            "source_tool": "VARCHAR(50)",
            "mask_points": "JSON",
        }

        with engine.begin() as connection:
            for column_name, column_type in required_columns.items():
                if column_name in existing_columns:
                    continue
                connection.execute(
                    text(f"ALTER TABLE image_annotations ADD COLUMN {column_name} {column_type}")
                )
                logger.info(f"Migracao aplicada: image_annotations.{column_name}")
    except Exception as exc:
        logger.warning(f"Migracao leve de banco nao aplicada: {exc}")


def reset_database():
    """
    Reseta o banco de dados (remove todos os dados).
    """
    try:
        logger.warning("Resetando banco de dados...")
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        _create_initial_data()
        logger.info("Banco de dados resetado com sucesso")
    except Exception as exc:
        logger.error(f"Erro ao resetar banco de dados: {exc}")
        raise


def backup_database(backup_path: str = None):
    """
    Cria backup do banco de dados SQLite.
    """
    try:
        import sqlite3
        from datetime import datetime

        sqlite_path = settings.sqlite_database_path
        if sqlite_path is None:
            raise ValueError("Backup automático disponível apenas para bancos SQLite")

        if backup_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"backup_db_{timestamp}.sqlite"

        source_uri = f"{sqlite_path.resolve().as_uri()}?mode=ro"
        with sqlite3.connect(source_uri, uri=True) as source:
            with sqlite3.connect(backup_path) as destination:
                source.backup(destination)
        logger.info(f"Backup criado em: {backup_path}")
        return backup_path
    except Exception as exc:
        logger.error(f"Erro ao criar backup: {exc}")
        raise


def get_database_stats():
    """
    Retorna estatísticas do banco de dados.
    """
    db = SessionLocal()
    try:
        from app.models.database import (
            AnalysisResult,
            ImageAnnotation,
            ImageDataset,
            MLModel,
            TrainingSession,
        )

        return {
            "database_url": make_url(settings.resolved_database_url).render_as_string(hide_password=True),
            "total_images": db.query(ImageDataset).count(),
            "annotated_images": db.query(ImageDataset).filter(ImageDataset.is_annotated == True).count(),
            "validated_images": db.query(ImageDataset).filter(ImageDataset.is_validated == True).count(),
            "total_annotations": db.query(ImageAnnotation).count(),
            "approved_annotations": db.query(ImageAnnotation).filter(ImageAnnotation.review_status == "approved").count(),
            "total_analysis_results": db.query(AnalysisResult).count(),
            "total_models": db.query(MLModel).count(),
            "active_models": db.query(MLModel).filter(MLModel.is_active == True).count(),
            "training_sessions": db.query(TrainingSession).count(),
            "completed_trainings": db.query(TrainingSession).filter(TrainingSession.status == "completed").count(),
        }
    except Exception as exc:
        logger.error(f"Erro ao obter estatísticas: {exc}")
        return {"database_backend": settings.database_backend, "status": "unavailable"}
    finally:
        db.close()


class DatabaseTransaction:
    """
    Context manager para transações de banco de dados.
    """

    def __init__(self):
        self.db = None

    def __enter__(self) -> Session:
        self.db = SessionLocal()
        return self.db

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if exc_type is None:
                self.db.commit()
            else:
                self.db.rollback()
        finally:
            self.db.close()


def with_db_session(func):
    """
    Decorator para funções que precisam de sessão de banco.
    """

    def wrapper(*args, **kwargs):
        with DatabaseTransaction() as db:
            return func(db, *args, **kwargs)

    return wrapper
