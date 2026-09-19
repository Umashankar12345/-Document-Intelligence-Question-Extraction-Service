import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, Float, BigInteger, DateTime, ForeignKey, Text
)
from sqlalchemy.sql import func

from app.db import Base, JSONType, IntArray


def _uuid():
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, default=_uuid)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    role = Column(String, default="user", nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class DocumentGroup(Base):
    __tablename__ = "document_groups"
    id = Column(String, primary_key=True, default=_uuid)
    owner_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Document(Base):
    __tablename__ = "documents"
    id = Column(String, primary_key=True, default=_uuid)
    owner_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    group_id = Column(String, ForeignKey("document_groups.id"), nullable=True, index=True)
    role = Column(String, default="question_paper")
    filename = Column(String, nullable=False)
    mime_type = Column(String, nullable=False)
    size_bytes = Column(BigInteger, nullable=False)
    storage_key = Column(String, nullable=False)
    checksum = Column(String, nullable=True)
    status = Column(String, default="pending", index=True)
    error = Column(Text, nullable=True)
    page_count = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())


class DocumentPage(Base):
    __tablename__ = "document_pages"
    id = Column(String, primary_key=True, default=_uuid)
    document_id = Column(String, ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    page_number = Column(Integer, nullable=False)
    image_key = Column(String, nullable=True)
    raw_text = Column(Text, nullable=True)
    ocr_confidence = Column(Float, nullable=True)
    rotation_deg = Column(Integer, default=0)


class Question(Base):
    __tablename__ = "questions"
    id = Column(String, primary_key=True, default=_uuid)
    document_id = Column(String, ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    group_id = Column(String, ForeignKey("document_groups.id"), nullable=True, index=True)
    question_number = Column(String, nullable=True)
    question_text = Column(Text, nullable=True)
    options = Column(JSONType, default=list)
    question_type = Column(String, default="unknown")
    answer = Column(String, nullable=True)
    answer_source = Column(String, default="none")
    answer_confidence = Column(Float, nullable=True)
    source_pages = Column(IntArray, default=list)
    bounding_boxes = Column(JSONType, default=list)
    confidence = Column(Float, default=0.0)
    status = Column(String, default="needs_review", index=True)
    warnings = Column(JSONType, default=list)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
