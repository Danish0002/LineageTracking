import time
from core.logger import get_logger

logger = get_logger("Timer")

def measure_execution_time(func, *args, **kwargs):
    """
    Wrapper to execute a function and log the time taken.
    """
    start_time = time.time()
    try:
        result = func(*args, **kwargs)
        return result
    finally:
        end_time = time.time()
        duration = end_time - start_time
        logger.info("-" * 40)
        logger.info(f"Execution Time: {duration:.3f} seconds")
        logger.info("-" * 40)