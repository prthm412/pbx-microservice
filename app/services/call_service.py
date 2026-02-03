"""
Call Service - Business Logic for Call Management
"""
from datetime import datetime
from typing import Optional, List
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.db.models import Call, CallPacket, CallStatus
from app.services.state_machine import CallStateMachine, StateTransitionError
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


class CallService:
    """Service for managing calls and packets"""
    
    @staticmethod
    async def get_or_create_call(
        db: AsyncSession, 
        call_id: str
    ) -> Call:
        """
        Get existing call or create new one
        
        Args:
            db: Database session
            call_id: Unique call identifier
            
        Returns:
            Call object
        """
        # Try to find existing call
        result = await db.execute(
            select(Call).where(Call.call_id == call_id)
        )
        call = result.scalar_one_or_none()
        
        if not call:
            # Create new call
            call = Call(
                call_id=call_id,
                status=CallStatus.IN_PROGRESS,
                expected_sequence=0,
                total_packets=0
            )
            db.add(call)
            await db.commit()
            await db.refresh(call)
            logger.info(f"Created new call: {call_id}")
        
        return call
    
    @staticmethod
    async def add_packet(
        db: AsyncSession,
        call: Call,
        sequence: int,
        data: str,
        timestamp: float
    ) -> tuple[CallPacket, bool]:
        """
        Add packet to call and validate sequence
        
        Args:
            db: Database session
            call: Call object
            sequence: Packet sequence number
            data: Packet data
            timestamp: Packet timestamp
            
        Returns:
            Tuple of (CallPacket, is_in_order: bool)
        """
        is_in_order = True
        
        # Check if packet is in expected sequence
        if sequence != call.expected_sequence:
            is_in_order = False
            
            # Log missing packets
            if sequence > call.expected_sequence:
                missing = list(range(call.expected_sequence, sequence))
                logger.warning(
                    f"Call {call.call_id}: Missing packets {missing}. "
                    f"Expected {call.expected_sequence}, got {sequence}"
                )
                
                # Update missing packets list
                current_missing = set()
                if call.missing_packets:
                    current_missing = set(map(int, call.missing_packets.split(',')))
                current_missing.update(missing)
                call.missing_packets = ','.join(map(str, sorted(current_missing)))
            else:
                logger.warning(
                    f"Call {call.call_id}: Duplicate or out-of-order packet. "
                    f"Expected {call.expected_sequence}, got {sequence}"
                )
        
        # Create packet
        packet = CallPacket(
            call_id=call.call_id,
            sequence=sequence,
            data=data,
            timestamp=timestamp
        )
        db.add(packet)
        
        # Update call
        call.total_packets += 1
        if sequence >= call.expected_sequence:
            call.expected_sequence = sequence + 1
        call.updated_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(packet)
        
        return packet, is_in_order
    
    @staticmethod
    async def update_call_status(
        db: AsyncSession,
        call: Call,
        new_status: CallStatus,
        error_message: Optional[str] = None
    ) -> Call:
        """
        Update call status with state machine validation
        
        Args:
            db: Database session
            call: Call object
            new_status: Desired new status
            error_message: Optional error message if transitioning to FAILED
            
        Returns:
            Updated call object
            
        Raises:
            StateTransitionError: If transition is invalid
        """
        # Validate state transition
        old_status = call.status
        CallStateMachine.transition(old_status, new_status)
        
        # Update status
        call.status = new_status
        call.updated_at = datetime.utcnow()
        
        if new_status == CallStatus.COMPLETED:
            call.completed_at = datetime.utcnow()
        
        if new_status == CallStatus.FAILED and error_message:
            call.error_message = error_message
        
        await db.commit()
        await db.refresh(call)
        
        logger.info(f"Call {call.call_id}: Status changed {old_status.value} → {new_status.value}")
        
        return call
    
    @staticmethod
    async def get_call_by_id(
        db: AsyncSession,
        call_id: str
    ) -> Optional[Call]:
        """Get call by call_id with packets loaded"""
        from sqlalchemy.orm import selectinload
        
        result = await db.execute(
            select(Call)
            .options(selectinload(Call.packets))
            .where(Call.call_id == call_id)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_all_calls(
        db: AsyncSession,
        status: Optional[CallStatus] = None,
        limit: int = 100
    ) -> List[Call]:
        """
        Get all calls with optional status filter
        
        Args:
            db: Database session
            status: Optional status filter
            limit: Maximum number of results
            
        Returns:
            List of Call objects
        """
        query = select(Call).order_by(Call.updated_at.desc()).limit(limit)
        
        if status:
            query = query.where(Call.status == status)
        
        result = await db.execute(query)
        return result.scalars().all()
    
    @staticmethod
    async def get_calls_for_processing(
        db: AsyncSession
    ) -> List[Call]:
        """Get calls that are COMPLETED and ready for AI processing"""
        result = await db.execute(
            select(Call).where(Call.status == CallStatus.COMPLETED)
        )
        return result.scalars().all()