import uuid
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, JSON, Integer
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector
from .database import Base

class Website(Base):
    __tablename__ = "websites"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    url = Column(String, nullable=False)
    name = Column(String, nullable=True)
    logo_url = Column(String, nullable=True)
    primary_color = Column(String, default="#C8CBD0")
    status = Column(String, default="PROCESSING")
    current_stage = Column(String, default="QUEUED")
    pages_scanned = Column(Integer, default=0)
    chunks_indexed = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    total_pages = Column(JSON, default=list)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    documents = relationship("DocumentChunk", back_populates="website", cascade="all, delete-orphan")

class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    website_id = Column(String, ForeignKey("websites.id"))
    page_url = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    embedding = Column(Vector(1536))

    website = relationship("Website", back_populates="documents")