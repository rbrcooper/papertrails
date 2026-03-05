import time
import logging
from functools import wraps
from typing import Tuple, Optional

logger = logging.getLogger(__name__)

# Error taxonomy: categorize exceptions for better logging and handling
NETWORK_ERRORS = (
    ConnectionError,
    TimeoutError,
    OSError,  # Network-related OSErrors
)

try:
    import requests
    NETWORK_ERRORS += (requests.RequestException, requests.ConnectionError, requests.Timeout)
except ImportError:
    pass

try:
    from selenium.common.exceptions import TimeoutException, WebDriverException
    NETWORK_ERRORS += (TimeoutException, WebDriverException)
except ImportError:
    pass

try:
    from json import JSONDecodeError
except ImportError:
    JSONDecodeError = ValueError

PARSE_ERRORS = (
    ValueError,
    KeyError,
    IndexError,
    TypeError,
    AttributeError,
    UnicodeDecodeError,
    JSONDecodeError,
)

PDF_CORRUPT_ERRORS = (
    FileNotFoundError,
    PermissionError,
)
# Note: IOError is an alias for OSError in Python 3, but OSError is too broad
# We only include specific file-related errors here

try:
    import fitz  # PyMuPDF
    PDF_CORRUPT_ERRORS += (fitz.FileDataError,)
except ImportError:
    pass

try:
    import pdfplumber
    # pdfplumber doesn't have specific exception types, but we can catch general PDF errors
except ImportError:
    pass


def categorize_error(exception: Exception) -> Tuple[str, str]:
    """
    Categorize an exception into error taxonomy.
    
    Args:
        exception: The exception to categorize
        
    Returns:
        Tuple of (category, description) where category is one of:
        - 'network': Network/timeout/connection errors
        - 'parse': Data parsing/format errors
        - 'pdf_corrupt': PDF file corruption or access errors
        - 'unknown': Unknown or uncategorized errors
    """
    exc_type = type(exception)
    exc_str = str(exception).lower()
    
    # Check PDF corruption errors FIRST (file access errors)
    # Note: FileNotFoundError and PermissionError are subclasses of OSError
    if isinstance(exception, PDF_CORRUPT_ERRORS) or 'corrupt' in exc_str or 'invalid pdf' in exc_str or 'not a pdf' in exc_str:
        return ('pdf_corrupt', f'PDF corruption/access error: {exc_type.__name__}')
    
    # Check network errors (ConnectionError, TimeoutError, etc.)
    # OSError can be network-related, but we check it here after PDF errors
    if isinstance(exception, NETWORK_ERRORS):
        # Additional check: if it's an OSError, check if it's file-related
        if isinstance(exception, OSError) and isinstance(exception, (FileNotFoundError, PermissionError)):
            return ('pdf_corrupt', f'PDF corruption/access error: {exc_type.__name__}')
        return ('network', f'Network error: {exc_type.__name__}')
    
    # Check network-related strings (but only if not already categorized)
    if 'connection' in exc_str or 'timeout' in exc_str or 'network' in exc_str:
        # But exclude file-related messages
        if 'file' not in exc_str and 'permission' not in exc_str:
            return ('network', f'Network error: {exc_type.__name__}')
    
    # Check parse errors
    if isinstance(exception, PARSE_ERRORS) or 'parse' in exc_str or 'decode' in exc_str or 'format' in exc_str:
        return ('parse', f'Parse error: {exc_type.__name__}')
    
    return ('unknown', f'Unknown error: {exc_type.__name__}')


def log_error_with_category(exception: Exception, context: str = "", logger_instance: Optional[logging.Logger] = None):
    """
    Log an exception with error category taxonomy.
    
    Args:
        exception: The exception to log
        context: Additional context string (e.g., "processing PDF X")
        logger_instance: Optional logger instance (defaults to module logger)
    """
    log = logger_instance if logger_instance else logger
    category, description = categorize_error(exception)
    
    context_str = f" [{context}]" if context else ""
    log.error(f"[{category.upper()}] {description}{context_str}: {str(exception)}", exc_info=True)


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
                    category, _ = categorize_error(e)
                    msg = f"'{func.__name__}' failed with [{category.upper()}] {e.__class__.__name__}. Retrying in {mdelay} seconds..."
                    logger.warning(msg)
                    time.sleep(mdelay)
                    mtries -= 1
                    mdelay *= backoff
            return func(*args, **kwargs)
        return wrapper
    return decorator 