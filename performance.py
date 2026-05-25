"""
Performance monitoring and metrics collection.
"""

import logging
import time
from collections.abc import Callable
from functools import wraps
from typing import Any

logger = logging.getLogger(__name__)


def measure_time(func: Callable) -> Callable:
    """Decorator to measure function execution time."""

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        start = time.perf_counter()
        try:
            result = func(*args, **kwargs)
            elapsed = time.perf_counter() - start
            logger.debug('%s completed in %.3fs', func.__name__, elapsed)
            return result
        except Exception as e:
            elapsed = time.perf_counter() - start
            logger.error('%s failed after %.3fs: %s', func.__name__, elapsed, e)
            raise

    return wrapper
