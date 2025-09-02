import logging
from logging.handlers import RotatingFileHandler  # For controlling the log file size and rotating
 
def get_logger(name):
    """
    Get a configured logger instance.
    Prevents duplicate handlers and sets a formatter for both file and console.
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)  # Set the logging level
 
    if not logger.handlers:
        # Formatter with detailed log structure
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(threadName)s - %(message)s"
        )
 
        # File handler with rotation
        file_handler = RotatingFileHandler(
            "smart_inventory_fastapi.log",
            maxBytes=10_000_000,  # ~10MB
            backupCount=10,
            encoding='utf-8',
            delay=True  # File is opened only when needed
        )
        file_handler.setFormatter(formatter)
 
        # Console handler
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
 
        # Add both handlers
        logger.addHandler(file_handler)
        logger.addHandler(stream_handler)
 
    return logger
