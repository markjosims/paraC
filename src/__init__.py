import os
import sys
from loguru import logger
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv() 

# Configure logging level from environment variable
# Set TIRA_LOG_LEVEL=DEBUG to see debug messages, otherwise defaults to INFO
_log_level = os.environ.get("TIRA_LOG_LEVEL", "INFO").upper()
_log_output = os.environ.get("TIRA_LOG_OUTPUT", "stdout")

if _log_output == "stderr":
    _log_output = sys.stderr
elif _log_output == "stdout":
    _log_output = sys.stdout

# Remove default handler and add one with the configured level
logger.remove()
logger.add(_log_output, level=_log_level)
