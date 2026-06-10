from __future__ import annotations
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Text, JSON
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class DocumentRegistry(Base):
    __tablename__ = "document_registry"

    doc_id = Column(String, primary_key=True)
    original_filename = Column(String, nullable=False)
    raw_path = Column(String, nullable=False)
    file_type = Column(String)           # typed_pdf | scanned_pdf | text
    status = Column(String, nullable=False)
    retry_count = Column(Integer, default=0)
    error_message = Column(Text)
    uploader_id = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    doc_metadata = Column(JSON, default=dict)


class ChunkRegistry(Base):
    __tablename__ = "chunk_registry"

    chunk_id = Column(String, primary_key=True)
    doc_id = Column(String, nullable=False)
    chunk_hash = Column(String, nullable=False, unique=True)
    chunk_index = Column(Integer)
    parent_chunk_id = Column(String)
    section = Column(String)
    page_number = Column(Integer, default=0)
    is_redacted = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_type = Column(String, nullable=False)
    user_id = Column(String)
    doc_id = Column(String)
    query = Column(Text)
    details = Column(JSON)
    timestamp = Column(DateTime, default=datetime.utcnow)
