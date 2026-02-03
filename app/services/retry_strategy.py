"""
Retry Strategy with Exponential Backoff
Uses Tenacity library for robust retry logic
"""
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
    after_log
)
import logging

from app.config import settings
from app.services.ai_service import AIServiceError

logger = logging.getLogger(__name__)


def create_retry_decorator():
    """
    Create retry decorator with exponential backoff
    
    Configuration:
    - Max attempts: 5 (from settings.MAX_RETRY_ATTEMPTS)
    - Wait: Exponential backoff starting at 1s, max 60s
    - Retry on: AIServiceError only
    - Logging: Before each retry and after final attempt
    """
    return retry(
        # Stop after max attempts
        stop=stop_after_attempt(settings.MAX_RETRY_ATTEMPTS),
        
        # Exponential backoff: 2^x seconds (1, 2, 4, 8, 16...)
        wait=wait_exponential(
            multiplier=settings.RETRY_INITIAL_WAIT,
            max=settings.RETRY_MAX_WAIT
        ),
        
        # Only retry on AIServiceError
        retry=retry_if_exception_type(AIServiceError),
        
        # Log before each retry
        before_sleep=before_sleep_log(logger, logging.WARNING),
        
        # Log after final attempt
        after=after_log(logger, logging.INFO)
    )


# Decorator instance for use in call processor
retry_with_backoff = create_retry_decorator()