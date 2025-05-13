import logging
import sys
from datetime import datetime
import os

def setup_logging():
    """Configure logging for the entire application"""
    # Create logs directory if it doesn't exist
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # Generate log filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(log_dir, f"lokilens_{timestamp}.log")

    # Configure root logger
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout)
        ]
    )

    # Create loggers for different components
    loggers = {
        'slack': logging.getLogger('slack'),
        'mcp': logging.getLogger('mcp'),
        's3': logging.getLogger('s3'),
        'loki': logging.getLogger('loki'),
        'openai': logging.getLogger('openai')
    }

    # Set all loggers to DEBUG level
    for logger in loggers.values():
        logger.setLevel(logging.DEBUG)

    return loggers 