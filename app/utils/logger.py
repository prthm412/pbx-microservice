"""
Logging Configuration
"""
import logging
import sys
from datetime import datetime


def setup_logger(name: str) -> logging.Logger:
    """
    Configure and return a logger instance
    
    Args:
        name: Logger name (usually __name__ from calling module)
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    # Avoid duplicate handlers
    if logger.handlers:
        return logger
    
    # Create console handler with formatting
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.INFO)
    
    # Format: [2026-02-03 10:30:45] INFO - module_name - Message
    formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s - %(name)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)
    
    logger.addHandler(handler)
    return logger