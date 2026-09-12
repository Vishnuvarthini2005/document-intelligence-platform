"""SQLAlchemy ORM model for a processed document result."""
import datetime as dt

from sqlalchemy import Column, Integer, String, Text, DateTime

from app.core.database import Base


class ProcessedDocument(Base):
    __tablename__ = "processed_documents"

    id = Column(Integer, primary_key=True, index=True)
    document_name = Column(String(512), index=True, nullable=False)
    document_type = Column(String(64), nullable=False)
    processing_status = Column(String(16), nullable=False)  # PASS / FAILED
    result_json = Column(Text, nullable=False)  # full structured response, stored as JSON text
    overall_confidence = Column(String(16), nullable=True)
    created_at = Column(DateTime, default=dt.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow, nullable=False)
