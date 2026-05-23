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

class Student(Base):
    __tablename__ = "students"

    student_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    class_code: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    concept_mastery: Mapped[list["ConceptMastery"]] = relationship(
        back_populates="student", cascade="all, delete-orphan"
    )
    mistake_patterns: Mapped[list["MistakePattern"]] = relationship(
        back_populates="student", cascade="all, delete-orphan"
    )
    interactions: Mapped[list["Interaction"]] = relationship(
        back_populates="student", cascade="all, delete-orphan"
    )


class Teacher(Base):
    __tablename__ = "teachers"

    teacher_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    subject: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    assignments: Mapped[list["Assignment"]] = relationship(
        back_populates="teacher", cascade="all, delete-orphan"
    )


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
        ForeignKey("students.student_id", ondelete="CASCADE"),
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

    student: Mapped["Student"] = relationship(back_populates="concept_mastery")
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
        ForeignKey("students.student_id", ondelete="CASCADE"),
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

    student: Mapped["Student"] = relationship(back_populates="mistake_patterns")
    concept: Mapped["ConceptCatalog"] = relationship()


# =========================================================
#                 EVENT LOG (for heatmap later)
# =========================================================

class Interaction(Base):
    __tablename__ = "interactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    student_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("students.student_id", ondelete="CASCADE"),
        nullable=False
    )
    subject: Mapped[str] = mapped_column(String(64), nullable=False)

    type: Mapped[str] = mapped_column(String(16), nullable=False)  # doubt / feedback
    question_text: Mapped[str] = mapped_column(Text, nullable=False)

    # store list of concept_ids (as JSON string)
    concepts_json: Mapped[str] = mapped_column(Text, default="[]")

    outcome: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    student: Mapped["Student"] = relationship(back_populates="interactions")
# =========================================================
#             ASSIGNMENT SYSTEM (SIMPLIFIED)
# =========================================================

class Assignment(Base):
    __tablename__ = "assignments"

    assignment_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    subject: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    
    teacher_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        ForeignKey("teachers.teacher_id", ondelete="SET NULL"),
        nullable=True
    )

    teacher: Mapped[Optional["Teacher"]] = relationship(back_populates="assignments")

    questions: Mapped[list["Question"]] = relationship(
        back_populates="assignment", cascade="all, delete-orphan"
    )


class Question(Base):
    __tablename__ = "questions"

    question_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    assignment_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("assignments.assignment_id", ondelete="CASCADE"),
        nullable=False
    )

    subject: Mapped[str] = mapped_column(String(64), nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    rubric_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    concept_ids_json: Mapped[str] = mapped_column(Text, default="[]")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    assignment: Mapped["Assignment"] = relationship(back_populates="questions")
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
