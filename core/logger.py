import logging
import sys
from io import StringIO

# Global buffer to hold logs for Streamlit display
log_buffer = StringIO()


def get_logger(name="LineageTracer"):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    if logger.hasHandlers():
        logger.handlers.clear()

    logger.propagate = False

    # Format: Time - Level - Message
    formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s', datefmt='%H:%M:%S')

    # 1. Console Handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    # 2. Buffer Handler (for Streamlit UI)
    memory_handler = logging.StreamHandler(log_buffer)
    memory_handler.setLevel(logging.INFO)
    memory_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(memory_handler)

    # Suppress noisy external libraries
    logging.getLogger("azure").setLevel(logging.WARNING)
    logging.getLogger("py4j").setLevel(logging.ERROR)

    return logger


def get_log_contents():
    """Returns the current contents of the log buffer."""
    return log_buffer.getvalue()


def clear_logs():
    """Clears the log buffer."""
    log_buffer.truncate(0)
    log_buffer.seek(0)