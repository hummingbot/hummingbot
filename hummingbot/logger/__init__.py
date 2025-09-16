"""
Hummingbot logging framework.
Provides centralized logging utilities for the Hummingbot framework.
"""

import logging
import sys
from typing import Optional, Dict, Any
from logging.handlers import RotatingFileHandler
import os


class HummingbotLogger:
    """
    Enhanced logger class for Hummingbot framework.
    Provides structured logging with file rotation and formatting.
    """
    
    def __init__(self, name: str):
        """
        Initialize Hummingbot logger.
        
        Args:
            name: Logger name (usually module name)
        """
        self._logger = logging.getLogger(name)
        self._name = name
        
        # Set default level
        if not self._logger.handlers:
            self._setup_default_handler()
    
    def _setup_default_handler(self):
        """Set up default console handler."""
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        self._logger.addHandler(handler)
        self._logger.setLevel(logging.INFO)
    
    def debug(self, message: str, *args, **kwargs):
        """Log debug message."""
        self._logger.debug(message, *args, **kwargs)
    
    def info(self, message: str, *args, **kwargs):
        """Log info message."""
        self._logger.info(message, *args, **kwargs)
    
    def warning(self, message: str, *args, **kwargs):
        """Log warning message."""
        self._logger.warning(message, *args, **kwargs)
    
    def error(self, message: str, *args, **kwargs):
        """Log error message."""
        self._logger.error(message, *args, **kwargs)
    
    def critical(self, message: str, *args, **kwargs):
        """Log critical message."""
        self._logger.critical(message, *args, **kwargs)
    
    def exception(self, message: str, *args, **kwargs):
        """Log exception with traceback."""
        self._logger.exception(message, *args, **kwargs)
    
    def setLevel(self, level):
        """Set logging level."""
        self._logger.setLevel(level)
    
    def addHandler(self, handler):
        """Add logging handler."""
        self._logger.addHandler(handler)
    
    def removeHandler(self, handler):
        """Remove logging handler."""
        self._logger.removeHandler(handler)
    
    @property
    def name(self) -> str:
        """Get logger name."""
        return self._name
    
    @property
    def level(self) -> int:
        """Get current logging level."""
        return self._logger.level
    
    @property
    def handlers(self):
        """Get logger handlers."""
        return self._logger.handlers


# Global logger registry
_logger_registry: Dict[str, HummingbotLogger] = {}


def getLogger(name: str) -> HummingbotLogger:
    """
    Get or create a Hummingbot logger.
    
    Args:
        name: Logger name
        
    Returns:
        HummingbotLogger instance
    """
    if name not in _logger_registry:
        _logger_registry[name] = HummingbotLogger(name)
    return _logger_registry[name]


def setup_logging(
    level: int = logging.INFO,
    log_file: Optional[str] = None,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5
):
    """
    Set up global logging configuration.
    
    Args:
        level: Logging level
        log_file: Optional log file path
        max_bytes: Maximum log file size before rotation
        backup_count: Number of backup files to keep
    """
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Clear existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # File handler (if specified)
    if log_file:
        try:
            # Create log directory if it doesn't exist
            log_dir = os.path.dirname(log_file)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir)
            
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=max_bytes,
                backupCount=backup_count
            )
            file_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            file_handler.setFormatter(file_formatter)
            root_logger.addHandler(file_handler)
            
        except Exception as e:
            console_handler.emit(
                logging.LogRecord(
                    name="hummingbot.logger",
                    level=logging.WARNING,
                    pathname="",
                    lineno=0,
                    msg=f"Failed to set up file logging: {e}",
                    args=(),
                    exc_info=None
                )
            )


def set_log_level(level: int):
    """
    Set global log level.
    
    Args:
        level: Logging level (logging.DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    logging.getLogger().setLevel(level)
    
    # Update all registered Hummingbot loggers
    for logger in _logger_registry.values():
        logger.setLevel(level)


def disable_logging():
    """Disable all logging."""
    logging.disable(logging.CRITICAL)


def enable_logging():
    """Re-enable logging."""
    logging.disable(logging.NOTSET)


class LoggerMixin:
    """
    Mixin class to add logging capabilities to any class.
    """
    
    @property
    def logger(self) -> HummingbotLogger:
        """Get logger for this class."""
        if not hasattr(self, '_logger'):
            self._logger = getLogger(self.__class__.__module__ + "." + self.__class__.__name__)
        return self._logger


# Convenience functions for backward compatibility
def create_logger(name: str) -> HummingbotLogger:
    """Create a new logger (alias for getLogger)."""
    return getLogger(name)


def get_logger(name: str) -> HummingbotLogger:
    """Get logger (alias for getLogger)."""
    return getLogger(name)


# Default setup
setup_logging()


# Export main classes and functions
__all__ = [
    'HummingbotLogger',
    'getLogger',
    'setup_logging',
    'set_log_level',
    'disable_logging',
    'enable_logging',
    'LoggerMixin',
    'create_logger',
    'get_logger'
]
