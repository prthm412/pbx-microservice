"""
SQLAlchemy Database Models
"""
from datetime import datetime
from enum import Enum as PyEnum
from sqlalchemy import (
    Column, String, Integer, Float, DateTime, Text, 
    ForeignKey, Enum, Boolean, Index
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class CallStatus(str, PyEnum):
    """Call status enum for state machine"""
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    PROCESSING_AI = "PROCESSING_AI"
    FAILED = "FAILED"
    ARCHIVED = "ARCHIVED"


class Call(Base):
    """
    Call model representing a phone call session
    Implements state machine: IN_PROGRESS → COMPLETED → PROCESSING_AI → ARCHIVED
                           or: IN_PROGRESS → FAILED
    """
    __tablename__ = "calls"
    
    id = Column(Integer, primary_key=True, index=True)
    call_id = Column(String(100), unique=True, index=True, nullable=False)
    status = Column(Enum(CallStatus), default=CallStatus.IN_PROGRESS, nullable=False)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    
    # Packet tracking
    expected_sequence = Column(Integer, default=0, nullable=False)
    total_packets = Column(Integer, default=0, nullable=False)
    missing_packets = Column(Text, default="", nullable=False)  # Comma-separated list
    
    # AI Processing results
    transcription = Column(Text, nullable=True)
    sentiment = Column(String(50), nullable=True)
    ai_processing_attempts = Column(Integer, default=0, nullable=False)
    ai_processed_at = Column(DateTime, nullable=True)
    
    # Error tracking
    error_message = Column(Text, nullable=True)
    
    # Relationships
    packets = relationship("CallPacket", back_populates="call", cascade="all, delete-orphan")
    
    # Indexes for query performance
    __table_args__ = (
        Index('idx_call_status_updated', 'status', 'updated_at'),
    )
    
    def __repr__(self):
        return f"<Call(call_id={self.call_id}, status={self.status})>"


class CallPacket(Base):
    """
    Individual audio metadata packet for a call
    """
    __tablename__ = "call_packets"
    
    id = Column(Integer, primary_key=True, index=True)
    call_id = Column(String(100), ForeignKey("calls.call_id"), nullable=False, index=True)
    sequence = Column(Integer, nullable=False)
    data = Column(Text, nullable=False)
    timestamp = Column(Float, nullable=False)
    received_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationship
    call = relationship("Call", back_populates="packets")
    
    # Composite index for efficient sequence queries
    __table_args__ = (
        Index('idx_call_sequence', 'call_id', 'sequence'),
    )
    
    def __repr__(self):
        return f"<CallPacket(call_id={self.call_id}, sequence={self.sequence})>"