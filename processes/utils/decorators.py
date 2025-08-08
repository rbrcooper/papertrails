import time
import logging
from functools import wraps

logger = logging.getLogger(__name__)

def retry(max_retries=3, delay=5, backoff=2, exceptions=(Exception,)):
    """
    A decorator for retrying a function call with exponential backoff.

    Args:
        max_retries (int): The maximum number of retries.
        delay (int): The initial delay between retries in seconds.
        backoff (int): The factor by which the delay should increase after each retry.
        exceptions (tuple): A tuple of exceptions to catch and trigger a retry.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            mtries, mdelay = max_retries, delay
            while mtries > 1:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    msg = f"'{func.__name__}' failed with {e.__class__.__name__}. Retrying in {mdelay} seconds..."
                    logger.warning(msg)
                    time.sleep(mdelay)
                    mtries -= 1
                    mdelay *= backoff
            return func(*args, **kwargs)
        return wrapper
    return decorator 