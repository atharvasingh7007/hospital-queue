"""
AlloyDB connection module for the Hospital Queue AI system.

Connects to AlloyDB using the Google Cloud AlloyDB Python Connector
with IAM authentication. Falls back to SQLite for local development.

Environment variables:
    ALLOYDB_INSTANCE: Full instance URI
        (projects/PROJECT/locations/REGION/clusters/CLUSTER/instances/INSTANCE)
    ALLOYDB_DB_NAME: Database name (default: hospital_queue)
    ALLOYDB_IAM_USER: IAM user email (service account for Cloud Run)
"""

import os
import logging

import sqlalchemy
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

logger = logging.getLogger(__name__)

_engine = None
_SessionLocal = None


def _create_alloydb_engine():
    """Create SQLAlchemy engine connected to AlloyDB via IAM auth."""
    from google.cloud.alloydb.connector import Connector

    instance_uri = os.environ["ALLOYDB_INSTANCE"]
    db_name = os.environ.get("ALLOYDB_DB_NAME", "hospital_queue")
    iam_user = os.environ.get("ALLOYDB_IAM_USER", "")

    connector = Connector()

    def getconn():
        return connector.connect(
            instance_uri,
            "pg8000",
            enable_iam_auth=True,
            user=iam_user,
            db=db_name,
        )

    engine = create_engine(
        "postgresql+pg8000://",
        creator=getconn,
        pool_size=5,
        max_overflow=2,
        pool_timeout=30,
        pool_recycle=1800,
    )
    logger.info(f"Connected to AlloyDB: {instance_uri}")
    return engine


def _create_sqlite_engine():
    """Create SQLAlchemy engine with local SQLite for development."""
    db_path = os.path.join(os.path.dirname(__file__), "..", "..", "hospital_queue.db")
    engine = create_engine(
        f"sqlite:///{db_path}",
        echo=False,
        connect_args={"check_same_thread": False},
    )
    logger.info(f"Using local SQLite database: {db_path}")
    return engine


def get_engine():
    """Get or create the database engine."""
    global _engine
    if _engine is None:
        if os.environ.get("ALLOYDB_INSTANCE"):
            _engine = _create_alloydb_engine()
        else:
            _engine = _create_sqlite_engine()
    return _engine


def get_session() -> Session:
    """Get a new database session."""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine())
    return _SessionLocal()


def init_database():
    """Initialize database tables."""
    from .models import Base
    engine = get_engine()
    Base.metadata.create_all(engine)
    logger.info("Database tables created successfully.")
