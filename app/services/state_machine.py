"""
Call State Machine Implementation
Manages valid state transitions for Call objects
"""
from enum import Enum
from typing import Dict, Set
from app.db.models import CallStatus


class StateTransitionError(Exception):
    """Raised when an invalid state transition is attempted"""
    pass


class CallStateMachine:
    """
    Manages state transitions for Call objects
    
    Valid transitions:
    IN_PROGRESS → COMPLETED
    IN_PROGRESS → FAILED
    COMPLETED → PROCESSING_AI
    PROCESSING_AI → COMPLETED (retry)
    PROCESSING_AI → FAILED
    COMPLETED → ARCHIVED
    FAILED → ARCHIVED
    """
    
    # Define valid state transitions
    VALID_TRANSITIONS: Dict[CallStatus, Set[CallStatus]] = {
        CallStatus.IN_PROGRESS: {
            CallStatus.COMPLETED,
            CallStatus.FAILED
        },
        CallStatus.COMPLETED: {
            CallStatus.PROCESSING_AI,
            CallStatus.ARCHIVED
        },
        CallStatus.PROCESSING_AI: {
            CallStatus.COMPLETED,  # For retry scenarios
            CallStatus.FAILED,
            CallStatus.ARCHIVED
        },
        CallStatus.FAILED: {
            CallStatus.ARCHIVED
        },
        CallStatus.ARCHIVED: set()  # Terminal state
    }
    
    @classmethod
    def can_transition(cls, from_status: CallStatus, to_status: CallStatus) -> bool:
        """
        Check if transition from one status to another is valid
        
        Args:
            from_status: Current status
            to_status: Desired status
            
        Returns:
            True if transition is valid, False otherwise
        """
        return to_status in cls.VALID_TRANSITIONS.get(from_status, set())
    
    @classmethod
    def transition(cls, from_status: CallStatus, to_status: CallStatus) -> CallStatus:
        """
        Perform state transition with validation

        Args:
            from_status: Current status
            to_status: Desired status
            
        Returns:
            The new status if transition is valid
            
        Raises:
            StateTransitionError: If transition is invalid
        """
        # Allow staying in the same state (idempotent)
        if from_status == to_status:
            return to_status

        if not cls.can_transition(from_status, to_status):
            raise StateTransitionError(
                f"Invalid state transition: {from_status.value} → {to_status.value}"
            )
        return to_status
    
    @classmethod
    def get_valid_transitions(cls, from_status: CallStatus) -> Set[CallStatus]:
        """
        Get all valid transitions from a given status
        
        Args:
            from_status: Current status
            
        Returns:
            Set of valid next statuses
        """
        return cls.VALID_TRANSITIONS.get(from_status, set())