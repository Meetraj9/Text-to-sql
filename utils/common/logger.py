"""
Logging configuration for the text-to-SQL application.
"""

import logging
import sys
from pathlib import Path


def setup_logger(
    name: str = "text_to_sql",
    log_level: str = "INFO",
    log_to_file: bool = True,
    log_file: str = "text_to_sql.log"
) -> logging.Logger:
    """
    Set up and configure logger for the application.
    
    Args:
        name: Logger name
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_to_file: Whether to log to file
        log_file: Log file path
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    
    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()
    # Prevent propagation to root logger to avoid duplicate logs
    logger.propagate = False
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    simple_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    
    # Console handler (always)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(simple_formatter)
    logger.addHandler(console_handler)
    
    # File handler (optional)
    if log_to_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_path, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(detailed_formatter)
        logger.addHandler(file_handler)
    
    return logger


def get_logger(name: str = None) -> logging.Logger:
    """
    Get logger instance. Creates one if it doesn't exist.
    
    Args:
        name: Logger name (defaults to module name)
        
    Returns:
        Logger instance
    """
    if name is None:
        # Use caller's module name
        import inspect
        frame = inspect.currentframe().f_back
        name = frame.f_globals.get('__name__', 'text_to_sql')
    
    logger = logging.getLogger(name)
    
    # If logger has no handlers, check if root logger is configured
    if not logger.handlers:
        root_logger = logging.getLogger()
        if not root_logger.handlers:
            # Set up root logger first
            setup_logger("text_to_sql")
        # Get logger again (it will inherit from root)
        logger = logging.getLogger(name)
    
    return logger

