"""
Pydantic Schemas for Request/Response Validation
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, validator
from app.db.models import CallStatus


class PacketMetadata(BaseModel):
    """Schema for incoming audio packet metadata"""
    sequence: int = Field(..., ge=0, description="Packet sequence number")
    data: str = Field(..., min_length=1, description="Audio metadata payload")
    timestamp: float = Field(..., gt=0, description="Packet timestamp")
    
    class Config:
        json_schema_extra = {
            "example": {
                "sequence": 0,
                "data": "audio_chunk_base64_encoded_data",
                "timestamp": 1738512345.123
            }
        }


class PacketResponse(BaseModel):
    """Response after packet ingestion"""
    call_id: str
    sequence: int
    status: str
    received_at: datetime
    message: str
    
    class Config:
        from_attributes = True


class CallResponse(BaseModel):
    """Call object response"""
    id: int
    call_id: str
    status: CallStatus
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
    total_packets: int
    missing_packets: str
    transcription: Optional[str] = None
    sentiment: Optional[str] = None
    ai_processed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    
    class Config:
        from_attributes = True
        use_enum_values = True


class CallListResponse(BaseModel):
    """Response for list of calls"""
    calls: List[CallResponse]
    total: int


class CallDetailResponse(CallResponse):
    """Detailed call response with packets"""
    packets_count: int
    ai_processing_attempts: int


class WebSocketMessage(BaseModel):
    """WebSocket message format"""
    type: str  # "call_update", "call_completed", "ai_processing", etc.
    call_id: str
    status: str
    data: Optional[dict] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)