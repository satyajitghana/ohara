"""Database configuration and session management."""
import os
from typing import Annotated
from sqlmodel import SQLModel, create_engine, Session
from fastapi import Depends


# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./app.db")

# SQLite specific configuration
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

# Create engine
engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    echo=False  # Set to True for SQL debugging
)


def create_db_and_tables():
    """Create database tables."""
    SQLModel.metadata.create_all(engine)


def get_session():
    """Get database session dependency."""
    with Session(engine) as session:
        yield session


# Session dependency
SessionDep = Annotated[Session, Depends(get_session)]
