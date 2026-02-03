"""
Flaky AI Service Mock
Simulates an unreliable external AI API with failures and latency
"""
import asyncio
import random
from typing import Dict, Optional
from datetime import datetime

from app.config import settings
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


class AIServiceError(Exception):
    """Raised when AI service fails"""
    pass


class AIService:
    """
    Mock AI Service that simulates transcription and sentiment analysis
    
    Characteristics:
    - 25% failure rate (returns 503 Service Unavailable)
    - Variable latency: 1-3 seconds
    - Returns mock transcription and sentiment when successful
    """
    
    def __init__(self):
        self.failure_rate = settings.AI_SERVICE_FAILURE_RATE
        self.min_latency = settings.AI_SERVICE_MIN_LATENCY
        self.max_latency = settings.AI_SERVICE_MAX_LATENCY
        self.request_count = 0
        self.failure_count = 0
        self.success_count = 0
    
    async def process_call(self, call_id: str, audio_data: str) -> Dict[str, str]:
        """
        Process call audio with AI transcription and sentiment analysis
        
        Args:
            call_id: Unique call identifier
            audio_data: Combined audio packet data
            
        Returns:
            Dictionary with 'transcription' and 'sentiment' keys
            
        Raises:
            AIServiceError: When service fails (25% of the time)
        """
        self.request_count += 1
        request_id = self.request_count
        
        logger.info(f"AI Service Request #{request_id} for call {call_id}")
        
        # Simulate variable latency (1-3 seconds)
        latency = random.uniform(self.min_latency, self.max_latency)
        await asyncio.sleep(latency)
        
        # Simulate 25% failure rate
        if random.random() < self.failure_rate:
            self.failure_count += 1
            logger.error(
                f"AI Service Request #{request_id} FAILED for call {call_id} "
                f"(latency: {latency:.2f}s, failure rate: {self.failure_count}/{self.request_count})"
            )
            raise AIServiceError("503 Service Unavailable - AI service temporarily unavailable")
        
        # Success case
        self.success_count += 1
        
        # Generate mock transcription based on audio data
        transcription = self._generate_mock_transcription(call_id, audio_data)
        
        # Generate mock sentiment analysis
        sentiment = self._generate_mock_sentiment()
        
        logger.info(
            f"AI Service Request #{request_id} SUCCESS for call {call_id} "
            f"(latency: {latency:.2f}s, sentiment: {sentiment})"
        )
        
        return {
            "transcription": transcription,
            "sentiment": sentiment,
            "processed_at": datetime.utcnow().isoformat(),
            "latency_seconds": round(latency, 2)
        }
    
    def _generate_mock_transcription(self, call_id: str, audio_data: str) -> str:
        """Generate mock transcription text"""
        templates = [
            f"Customer inquiry about product features and pricing for call {call_id}.",
            f"Technical support request regarding system integration issues in call {call_id}.",
            f"Sales conversation discussing service packages and contract terms for {call_id}.",
            f"Customer feedback session about recent experience with our services - {call_id}.",
            f"Billing inquiry and account management discussion for call {call_id}."
        ]
        
        base_text = random.choice(templates)
        word_count = len(audio_data.split('_'))  # Use audio data to vary length
        
        return f"{base_text} Audio processed: {word_count} segments analyzed."
    
    def _generate_mock_sentiment(self) -> str:
        """Generate mock sentiment analysis result"""
        sentiments = [
            "positive",
            "neutral", 
            "negative",
            "mixed"
        ]
        
        # Weight towards positive and neutral (80%)
        weights = [0.4, 0.4, 0.1, 0.1]
        
        return random.choices(sentiments, weights=weights)[0]
    
    def get_stats(self) -> Dict[str, int]:
        """Get service statistics"""
        return {
            "total_requests": self.request_count,
            "successful": self.success_count,
            "failed": self.failure_count,
            "success_rate": round(self.success_count / max(self.request_count, 1) * 100, 2)
        }


# Singleton instance
ai_service = AIService()