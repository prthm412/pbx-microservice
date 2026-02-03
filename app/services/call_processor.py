"""
Call Processor - Background Task Handler
Orchestrates AI processing for completed calls
"""
import asyncio
from typing import List
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select as sql_select
from sqlalchemy.orm import selectinload

from app.db.database import AsyncSessionLocal
from app.db.models import Call, CallStatus
from app.services.ai_service import ai_service, AIServiceError
from app.services.call_service import CallService
from app.services.retry_strategy import retry_with_backoff
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


class CallProcessor:
    """
    Background processor for AI transcription and sentiment analysis
    
    Workflow:
    1. Poll for calls in COMPLETED status
    2. Transition to PROCESSING_AI
    3. Combine all packet data
    4. Send to AI service with retry logic
    5. Store results and transition to COMPLETED or FAILED
    """
    
    def __init__(self, poll_interval: int = 5):
        """
        Initialize call processor
        
        Args:
            poll_interval: Seconds between polling for new calls (default: 5)
        """
        self.poll_interval = poll_interval
        self.is_running = False
        self.processed_count = 0
    
    async def start(self):
        """Start the background processor"""
        self.is_running = True
        logger.info("🤖 Call Processor started")
        
        while self.is_running:
            try:
                await self._process_pending_calls()
            except Exception as e:
                logger.error(f"Error in call processor loop: {str(e)}")
            
            # Wait before next poll
            await asyncio.sleep(self.poll_interval)
    
    def stop(self):
        """Stop the background processor"""
        self.is_running = False
        logger.info("🛑 Call Processor stopped")
    
    async def _process_pending_calls(self):
        """Process all pending calls"""
        async with AsyncSessionLocal() as db:
            try:
                # Get calls ready for processing
                calls = await CallService.get_calls_for_processing(db)
                
                # Always log what we found (even if 0)
                logger.info(f"📋 Polling for pending calls... Found: {len(calls)}")
                
                if calls:
                    logger.info(f"🔄 Processing {len(calls)} calls")
                    for call in calls:
                        logger.info(f"  - Call {call.call_id} (status: {call.status})")
                
                for call in calls:
                    try:
                        await self._process_single_call(db, call)
                    except Exception as e:
                        logger.error(f"Failed to process call {call.call_id}: {str(e)}")
            except Exception as e:
                logger.error(f"Error getting pending calls: {str(e)}")
    
    async def _process_single_call(self, db: AsyncSession, call: Call):
        """
        Process a single call through AI service
        
        Args:
            db: Database session
            call: Call object to process
        """
        logger.info(f"🔧 Processing call {call.call_id}")
        
        try:
            # Step 1: Transition to PROCESSING_AI
            logger.info(f"Step 1: Transitioning {call.call_id} to PROCESSING_AI")
            call = await CallService.update_call_status(
                db, call, CallStatus.PROCESSING_AI
            )
            
            # Step 2: Get fresh call with packets loaded
            logger.info(f"Step 2: Loading packets for {call.call_id}")
            
            result = await db.execute(
                sql_select(Call)
                .options(selectinload(Call.packets))
                .where(Call.call_id == call.call_id)
            )
            call_with_packets = result.scalar_one()
            
            # Step 3: Combine packet data
            logger.info(f"Step 3: Combining {len(call_with_packets.packets)} packets")
            audio_data = self._combine_packet_data(call_with_packets)
            logger.info(f"Combined audio data length: {len(audio_data)} chars")
            
            # Step 4: Process with AI service (with retry logic)
            logger.info(f"Step 4: Sending to AI service")
            ai_result = await self._process_with_retry(call.call_id, audio_data)
            
            # Step 5: Update call with results in a fresh query
            logger.info(f"Step 5: Updating call with AI results")
            result = await db.execute(
                sql_select(Call).where(Call.call_id == call.call_id)
            )
            call = result.scalar_one()
            
            call.transcription = ai_result["transcription"]
            call.sentiment = ai_result["sentiment"]
            call.ai_processed_at = datetime.utcnow()
            call.ai_processing_attempts += 1
            
            await db.commit()
            await db.refresh(call)
            
            # Step 6: Transition back to COMPLETED
            logger.info(f"Step 6: Transitioning back to COMPLETED")
            call = await CallService.update_call_status(
                db, call, CallStatus.COMPLETED
            )
            
            self.processed_count += 1
            logger.info(
                f"✅ Successfully processed call {call.call_id} "
                f"(sentiment: {call.sentiment})"
            )
            
        except AIServiceError as e:
            # AI service failed after all retries
            logger.error(f"AI Service failed for {call.call_id}: {str(e)}")
            
            # Get fresh call object
            result = await db.execute(
                sql_select(Call).where(Call.call_id == call.call_id)
            )
            call = result.scalar_one()
            
            call.ai_processing_attempts += 1
            await db.commit()
            
            call = await CallService.update_call_status(
                db, call, CallStatus.FAILED,
                error_message=f"AI service failed after retries: {str(e)}"
            )
            logger.error(f"❌ Failed to process call {call.call_id} after retries")
        
        except Exception as e:
            # Unexpected error
            logger.error(f"Unexpected error for {call.call_id}: {str(e)}", exc_info=True)
            
            try:
                # Get fresh call object
                result = await db.execute(
                    sql_select(Call).where(Call.call_id == call.call_id)
                )
                call = result.scalar_one()
                
                call.ai_processing_attempts += 1
                await db.commit()
                
                call = await CallService.update_call_status(
                    db, call, CallStatus.FAILED,
                    error_message=f"Unexpected error: {str(e)}"
                )
            except Exception as inner_e:
                logger.error(f"Failed to mark call as FAILED: {str(inner_e)}")
    
    def _combine_packet_data(self, call: Call) -> str:
        """
        Combine all packet data into single audio string
        
        Args:
            call: Call object with packets loaded
            
        Returns:
            Combined audio data string
        """
        if not call.packets:
            return ""
        
        # Sort packets by sequence
        sorted_packets = sorted(call.packets, key=lambda p: p.sequence)
        
        # Combine data
        combined = " ".join([p.data for p in sorted_packets])
        
        return combined
    
    @retry_with_backoff
    async def _process_with_retry(self, call_id: str, audio_data: str) -> dict:
        """
        Process call with AI service using retry logic
        
        This method is decorated with @retry_with_backoff which provides:
        - Up to 5 retry attempts
        - Exponential backoff (1s, 2s, 4s, 8s, 16s...)
        - Only retries on AIServiceError
        
        Args:
            call_id: Unique call identifier
            audio_data: Combined audio packet data
            
        Returns:
            AI processing results
            
        Raises:
            AIServiceError: If all retry attempts fail
        """
        return await ai_service.process_call(call_id, audio_data)
    
    def get_stats(self) -> dict:
        """Get processor statistics"""
        return {
            "is_running": self.is_running,
            "processed_count": self.processed_count,
            "ai_service_stats": ai_service.get_stats()
        }


# Global processor instance
call_processor = CallProcessor(poll_interval=5)