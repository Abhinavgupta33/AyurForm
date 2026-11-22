"""SQLAlchemy models for the PostgreSQL AyurForm structured store."""
from __future__ import annotations
from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker
from config import DATABASE_URL

class Base(DeclarativeBase): pass

class Source(Base):
    __tablename__ = "sources"
    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    title: Mapped[str] = mapped_column(Text)
    translator: Mapped[str | None] = mapped_column(Text)
    editor: Mapped[str | None] = mapped_column(Text)
    publisher: Mapped[str | None] = mapped_column(Text)
    edition: Mapped[str | None] = mapped_column(Text)
    publication_year: Mapped[int | None] = mapped_column(Integer)
    rights_status: Mapped[str] = mapped_column(String(40))
    usage_scope: Mapped[str] = mapped_column(String(40))
    review_status: Mapped[str] = mapped_column(String(40), index=True)
    source_sha256: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    passages: Mapped[list["SourcePassage"]] = relationship(cascade="all, delete-orphan")

class SourcePassage(Base):
    __tablename__ = "source_passages"
    id: Mapped[int] = mapped_column(primary_key=True)
    stable_passage_id: Mapped[str] = mapped_column(String(240), unique=True, index=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), index=True)
    text: Mapped[str] = mapped_column(Text)
    pdf_page: Mapped[int | None] = mapped_column(Integer)
    section: Mapped[str | None] = mapped_column(Text)
    chapter: Mapped[str | None] = mapped_column(Text)
    verse_reference: Mapped[str | None] = mapped_column(Text)
    provenance_role: Mapped[str] = mapped_column(String(40), index=True)
    review_status: Mapped[str] = mapped_column(String(40), index=True)
    chroma_id: Mapped[str | None] = mapped_column(String(240))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Dravya(Base):
    __tablename__ = "dravya"
    id: Mapped[int] = mapped_column(primary_key=True)
    canonical_name: Mapped[str] = mapped_column(String(240), unique=True, index=True)
    sanskrit_name: Mapped[str | None] = mapped_column(Text)
    botanical_identity: Mapped[str | None] = mapped_column(Text)
    botanical_verification_status: Mapped[str | None] = mapped_column(String(40))
    review_status: Mapped[str] = mapped_column(String(40), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Formulation(Base):
    __tablename__ = "formulations"
    id: Mapped[int] = mapped_column(primary_key=True)
    canonical_name: Mapped[str] = mapped_column(String(240), unique=True, index=True)
    sanskrit_name: Mapped[str | None] = mapped_column(Text)
    preparation_context: Mapped[str | None] = mapped_column(Text)
    review_status: Mapped[str] = mapped_column(String(40), index=True)
    source_passage_id: Mapped[int | None] = mapped_column(ForeignKey("source_passages.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class DravyaSynonym(Base):
    __tablename__ = "dravya_synonyms"
    id: Mapped[int] = mapped_column(primary_key=True)
    dravya_id: Mapped[int] = mapped_column(ForeignKey("dravya.id", ondelete="CASCADE"), index=True)
    synonym: Mapped[str] = mapped_column(Text)
    language: Mapped[str | None] = mapped_column(String(40))
    source_passage_id: Mapped[int | None] = mapped_column(ForeignKey("source_passages.id"))
    __table_args__ = (UniqueConstraint("dravya_id", "synonym"),)

class DravyaAttribute(Base):
    __tablename__ = "dravya_attributes"
    id: Mapped[int] = mapped_column(primary_key=True)
    dravya_id: Mapped[int] = mapped_column(ForeignKey("dravya.id", ondelete="CASCADE"), index=True)
    attribute_type: Mapped[str] = mapped_column(String(30))
    attribute_value: Mapped[str] = mapped_column(Text)
    source_passage_id: Mapped[int] = mapped_column(ForeignKey("source_passages.id"))
    provenance_role: Mapped[str] = mapped_column(String(40))
    review_status: Mapped[str] = mapped_column(String(40))

class FormulationIngredient(Base):
    __tablename__ = "formulation_ingredients"
    id: Mapped[int] = mapped_column(primary_key=True)
    formulation_id: Mapped[int] = mapped_column(ForeignKey("formulations.id", ondelete="CASCADE"), index=True)
    dravya_id: Mapped[int | None] = mapped_column(ForeignKey("dravya.id"))
    ingredient_name_recorded: Mapped[str] = mapped_column(Text)
    ingredient_role: Mapped[str | None] = mapped_column(Text)
    source_passage_id: Mapped[int] = mapped_column(ForeignKey("source_passages.id"))
    review_status: Mapped[str] = mapped_column(String(40))

class AnupanaRelationship(Base):
    __tablename__ = "anupana_relationships"
    id: Mapped[int] = mapped_column(primary_key=True)
    anupana_term: Mapped[str] = mapped_column(Text, index=True)
    dravya_id: Mapped[int | None] = mapped_column(ForeignKey("dravya.id"))
    formulation_id: Mapped[int | None] = mapped_column(ForeignKey("formulations.id"))
    source_passage_id: Mapped[int] = mapped_column(ForeignKey("source_passages.id"))
    relationship_context: Mapped[str] = mapped_column(Text)
    provenance_role: Mapped[str] = mapped_column(String(40))
    review_status: Mapped[str] = mapped_column(String(40))

class ExpertReview(Base):
    __tablename__ = "expert_reviews"
    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(40), index=True)
    entity_id: Mapped[int] = mapped_column(Integer, index=True)
    status: Mapped[str] = mapped_column(String(40), index=True)
    review_notes: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)

def make_engine(url: str | None = None):
    target = url or DATABASE_URL
    if not target or target.startswith("sqlite"):
        raise RuntimeError("PostgreSQL DATABASE_URL is required for the AyurForm structured store.")
    return create_engine(target, pool_pre_ping=True)

def session_factory(url: str | None = None):
    return sessionmaker(bind=make_engine(url), expire_on_commit=False)
