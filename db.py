# db.py
# SQLite + SQLAlchemy models + init_db()
# Concept Catalog version (concept_id integer everywhere)

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    create_engine,
    String,
    Integer,
    Float,
    DateTime,
    Text,
    ForeignKey,
    UniqueConstraint,
    event,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker
from sqlalchemy.engine import Engine
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash


# ---------- Helpers ----------
def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------- SQLAlchemy base ----------
class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------
# SQLite: enforce foreign keys (OFF by default in SQLite)
# ---------------------------------------------------------
@event.listens_for(Engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    try:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.close()
    except Exception:
        # If this ever fails, we don't want app startup to crash.
        pass


# =========================================================
#                     CORE ENTITIES
# =========================================================

class User(Base, UserMixin):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)  # "student" or "teacher"
    name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # Role-Specific Metadata
    subject: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)      # Teachers only
    class_code: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)    # Students only

    concept_mastery: Mapped[list["ConceptMastery"]] = relationship(
        back_populates="student", cascade="all, delete-orphan"
    )
    mistake_patterns: Mapped[list["MistakePattern"]] = relationship(
        back_populates="student", cascade="all, delete-orphan"
    )
    interactions: Mapped[list["Interaction"]] = relationship(
        back_populates="student", cascade="all, delete-orphan"
    )

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


# =========================================================
#                CONCEPT CATALOG (CANONICAL)
# =========================================================


class ConceptCatalog(Base):
    __tablename__ = "concept_catalog"
    __table_args__ = (
        UniqueConstraint("subject", "label", name="uq_concept_subject_label"),
    )

    concept_id = mapped_column(Integer, primary_key=True, autoincrement=True)
    subject = mapped_column(String(64), nullable=False)
    label = mapped_column(String(128), nullable=False)
    embedding_json = mapped_column(Text, nullable=True)
    created_at = mapped_column(DateTime(timezone=True), default=utcnow)
# =========================================================
#                 STUDENT LEARNING STATE
# =========================================================

class ConceptMastery(Base):
    __tablename__ = "concept_mastery"
    __table_args__ = (
        UniqueConstraint(
            "student_id", "subject", "concept_id",
            name="uq_mastery_student_subject_concept"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    student_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    subject: Mapped[str] = mapped_column(String(64), nullable=False)

    concept_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("concept_catalog.concept_id", ondelete="CASCADE"),
        nullable=False
    )

    mastery: Mapped[float] = mapped_column(Float, default=0.5)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow
    )

    student: Mapped["User"] = relationship(back_populates="concept_mastery")
    concept: Mapped["ConceptCatalog"] = relationship()


class MistakePattern(Base):
    __tablename__ = "mistake_patterns"
    __table_args__ = (
        UniqueConstraint(
            "student_id", "subject", "concept_id", "mistake_tag",
            name="uq_mistake_student_subject_concept_tag"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    student_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    subject: Mapped[str] = mapped_column(String(64), nullable=False)

    concept_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("concept_catalog.concept_id", ondelete="CASCADE"),
        nullable=False
    )

    mistake_tag: Mapped[str] = mapped_column(String(64), nullable=False)
    count: Mapped[int] = mapped_column(Integer, default=0)
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow
    )

    student: Mapped["User"] = relationship(back_populates="mistake_patterns")
    concept: Mapped["ConceptCatalog"] = relationship()


# =========================================================
#                 EVENT LOG (for heatmap later)
# =========================================================

class Interaction(Base):
    __tablename__ = "interactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    student_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    subject: Mapped[str] = mapped_column(String(64), nullable=False)

    type: Mapped[str] = mapped_column(String(16), nullable=False)  # doubt / feedback
    question_text: Mapped[str] = mapped_column(Text, nullable=False)

    # store list of concept_ids (as JSON string)
    concepts_json: Mapped[str] = mapped_column(Text, default="[]")

    outcome: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    student: Mapped["User"] = relationship(back_populates="interactions")


# =========================================================
#                  ENGINE / SESSION
# =========================================================

def get_db_url(db_path: Optional[str] = None) -> str:
    if db_path is None:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        db_path = os.path.join(base_dir, "app.db")
    return f"sqlite:///{db_path}"


_engine = None
_SessionLocal = None


def init_db(db_path: Optional[str] = None):
    """
    Call this once on app startup.
    If you delete app.db, this will recreate tables from models.
    """
    global _engine, _SessionLocal

    db_url = get_db_url(db_path)

    # check_same_thread=False helps with Flask dev server threading
    _engine = create_engine(
        db_url,
        echo=False,
        future=True,
        connect_args={"check_same_thread": False},
    )

    Base.metadata.create_all(_engine)

    _SessionLocal = sessionmaker(
        bind=_engine,
        autoflush=False,
        autocommit=False,
        future=True,
    )
    return _engine


def get_session():
    if _SessionLocal is None:
        raise RuntimeError("DB not initialized. Call init_db() first.")
    return _SessionLocal()