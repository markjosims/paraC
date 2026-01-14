import os
import sys
from loguru import logger

# Configure logging level from environment variable
# Set TIRA_LOG_LEVEL=DEBUG to see debug messages, otherwise defaults to INFO
_log_level = os.environ.get("TIRA_LOG_LEVEL", "INFO").upper()

# Remove default handler and add one with the configured level
logger.remove()
logger.add(sys.stderr, level=_log_level)
