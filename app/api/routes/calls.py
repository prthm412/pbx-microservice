"""
Call API Routes
"""
import time
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.models import CallStatus
from app.schemas.call_schemas import (
    PacketMetadata,
    PacketResponse,
    CallResponse,
    CallListResponse,
    CallDetailResponse
)
from app.services.call_service import CallService
from app.utils.logger import setup_logger

router = APIRouter(prefix="/v1/call", tags=["calls"])
logger = setup_logger(__name__)


@router.post(
    "/stream/{call_id}",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=PacketResponse
)
async def stream_packet(
    call_id: str,
    packet: PacketMetadata,
    db: AsyncSession = Depends(get_db)
):
    """
    Ingest audio metadata packet for a call
    
    This endpoint:
    - Validates packet sequence order
    - Logs warnings for missing packets (non-blocking)
    - Returns 202 Accepted within < 50ms
    - Does not block on AI processing
    
    Args:
        call_id: Unique call identifier
        packet: Audio packet metadata
        db: Database session
        
    Returns:
        PacketResponse with acceptance confirmation
    """
    start_time = time.time()
    
    try:
        # Get or create call
        call = await CallService.get_or_create_call(db, call_id)
        
        # Add packet (validates sequence, logs missing packets)
        packet_obj, is_in_order = await CallService.add_packet(
            db=db,
            call=call,
            sequence=packet.sequence,
            data=packet.data,
            timestamp=packet.timestamp
        )
        
        # Calculate processing time
        processing_time = (time.time() - start_time) * 1000  # Convert to ms
        
        status_msg = "accepted" if is_in_order else "accepted_with_warning"
        
        logger.info(
            f"Packet {packet.sequence} for call {call_id} processed in {processing_time:.2f}ms"
        )
        
        return PacketResponse(
            call_id=call_id,
            sequence=packet.sequence,
            status=status_msg,
            received_at=packet_obj.received_at,
            message=f"Packet {packet.sequence} received successfully"
        )
        
    except Exception as e:
        logger.error(f"Error processing packet for call {call_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process packet: {str(e)}"
        )


@router.post(
    "/complete/{call_id}",
    status_code=status.HTTP_200_OK,
    response_model=CallResponse
)
async def complete_call(
    call_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Mark a call as completed
    
    This triggers the call to be picked up by background AI processing
    
    Args:
        call_id: Unique call identifier
        db: Database session
        
    Returns:
        Updated call object
    """
    call = await CallService.get_call_by_id(db, call_id)
    
    if not call:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Call {call_id} not found"
        )
    
    # Check if already completed
    if call.status == CallStatus.COMPLETED:
        logger.info(f"Call {call_id} is already completed")
        return CallResponse.model_validate(call)
    
    # Check if in a state that can transition to COMPLETED
    if call.status not in [CallStatus.IN_PROGRESS, CallStatus.PROCESSING_AI]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot complete call in status {call.status.value}"
        )
    
    # Update status to COMPLETED
    call = await CallService.update_call_status(db, call, CallStatus.COMPLETED)
    
    return CallResponse.model_validate(call)


@router.get(
    "/history",
    response_model=CallListResponse
)
async def get_call_history(
    status: CallStatus = None,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """
    Get call history with optional status filter
    
    Args:
        status: Optional status filter
        limit: Maximum number of results (default: 100)
        db: Database session
        
    Returns:
        List of calls
    """
    calls = await CallService.get_all_calls(db, status=status, limit=limit)
    
    return CallListResponse(
        calls=[CallResponse.model_validate(call) for call in calls],
        total=len(calls)
    )


@router.get(
    "/{call_id}",
    response_model=CallDetailResponse
)
async def get_call_details(
    call_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get detailed information about a specific call
    
    Args:
        call_id: Unique call identifier
        db: Database session
        
    Returns:
        Detailed call information
    """
    call = await CallService.get_call_by_id(db, call_id)
    
    if not call:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Call {call_id} not found"
        )
    
    # Build response manually to include computed fields
    return CallDetailResponse(
        id=call.id,
        call_id=call.call_id,
        status=call.status,
        created_at=call.created_at,
        updated_at=call.updated_at,
        completed_at=call.completed_at,
        total_packets=call.total_packets,
        missing_packets=call.missing_packets,
        transcription=call.transcription,
        sentiment=call.sentiment,
        ai_processed_at=call.ai_processed_at,
        error_message=call.error_message,
        packets_count=len(call.packets),
        ai_processing_attempts=call.ai_processing_attempts
    )