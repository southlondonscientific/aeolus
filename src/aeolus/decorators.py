# Aeolus: download UK and standardise air quality data
# Copyright (C) 2025 Ruaraidh Dobson, South London Scientific

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
Function decorators for cross-cutting concerns.

This module provides decorators that add retry logic, logging, and other
functionality to functions without modifying their core logic.

All decorators are designed to work with the functional architecture and
can be easily composed together.
"""

import logging
from functools import wraps
from typing import Callable, TypeVar

import requests
from tenacity import (
    after_log,
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

# Type variable for generic function signatures
F = TypeVar("F", bound=Callable)

# Get logger for this module
logger = logging.getLogger(__name__)


def with_retry(
    max_attempts: int = 3,
    min_wait: float = 1.0,
    max_wait: float = 10.0,
    multiplier: float = 2.0,
) -> Callable[[F], F]:
    """
    Decorator to add exponential backoff retry logic to a function.

    Retries on common network errors (connection errors, timeouts, HTTP 5xx errors).
    Uses exponential backoff: waits increase as 2^attempt * multiplier seconds,
    bounded by min_wait and max_wait.

    Args:
        max_attempts: Maximum number of attempts (default: 3)
        min_wait: Minimum wait time between retries in seconds (default: 1.0)
        max_wait: Maximum wait time between retries in seconds (default: 10.0)
        multiplier: Multiplier for exponential backoff (default: 2.0)

    Returns:
        Callable: Decorated function with retry logic

    Example:
        >>> @with_retry(max_attempts=5, min_wait=2.0)
        ... def fetch_data(url):
        ...     response = requests.get(url)
        ...     response.raise_for_status()
        ...     return response.json()

    Note:
        This decorator catches and retries on:
        - requests.exceptions.ConnectionError (network issues)
        - requests.exceptions.Timeout (request timeouts)
        - requests.exceptions.HTTPError (HTTP 5xx server errors only)
    """

    def decorator(func: F) -> F:
        # Define which exceptions to retry on
        def should_retry_http_error(exception):
            """Only retry on HTTP 5xx server errors, not 4xx client errors."""
            if isinstance(exception, requests.exceptions.HTTPError):
                if exception.response is not None:
                    # Retry only on 5xx server errors, not 4xx client errors
                    return 500 <= exception.response.status_code < 600
            return False

        @retry(
            # Retry on connection errors, timeouts, and server errors (5xx)
            retry=(
                retry_if_exception_type(requests.exceptions.ConnectionError)
                | retry_if_exception_type(requests.exceptions.Timeout)
                | retry_if_exception_type(
                    (requests.exceptions.HTTPError,),
                )
                & retry_if_exception_type(should_retry_http_error)
            ),
            # Stop after max_attempts
            stop=stop_after_attempt(max_attempts),
            # Exponential backoff between attempts
            wait=wait_exponential(multiplier=multiplier, min=min_wait, max=max_wait),
            # Log before sleeping
            before_sleep=before_sleep_log(logger, logging.WARNING),
            # Log after all attempts
            after=after_log(logger, logging.DEBUG),
            # Re-raise the last exception if all attempts fail
            reraise=True,
        )
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        return wrapper

    return decorator


def with_timeout(seconds: int) -> Callable[[F], F]:
    """
    Decorator to ensure requests have a timeout.

    This decorator adds a 'timeout' parameter to function calls if not already present.
    Useful for ensuring all HTTP requests have sensible timeouts.

    Args:
        seconds: Timeout in seconds

    Returns:
        Callable: Decorated function with timeout parameter

    Example:
        >>> @with_timeout(30)
        ... def fetch_data(url, **kwargs):
        ...     return requests.get(url, **kwargs)

    Note:
        This only adds the timeout if the function accepts **kwargs and
        'timeout' is not already specified.
    """

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Add timeout if not already present
            if "timeout" not in kwargs:
                kwargs["timeout"] = seconds
            return func(*args, **kwargs)

        return wrapper

    return decorator


def with_logging(logger_name: str | None = None) -> Callable[[F], F]:
    """
    Decorator to add logging to function entry and exit.

    Logs function calls at INFO level with arguments and return values.
    Errors are logged at ERROR level before being re-raised.

    Args:
        logger_name: Name of logger to use. If None, uses the module name.

    Returns:
        Callable: Decorated function with logging

    Example:
        >>> @with_logging("aeolus.fetchers")
        ... def fetch_data(site, year):
        ...     return download(site, year)

    Note:
        Be careful with logging sensitive data (API keys, etc.).
        This decorator logs function arguments.
    """

    def decorator(func: F) -> F:
        func_logger = logging.getLogger(logger_name or func.__module__)

        @wraps(func)
        def wrapper(*args, **kwargs):
            func_logger.info(
                f"Calling {func.__name__}",
                extra={
                    "function": func.__name__,
                    "args_count": len(args),
                    "kwargs_keys": list(kwargs.keys()),
                },
            )

            try:
                result = func(*args, **kwargs)
                func_logger.info(
                    f"Completed {func.__name__}", extra={"function": func.__name__}
                )
                return result
            except Exception as e:
                func_logger.error(
                    f"Error in {func.__name__}: {e}",
                    extra={
                        "function": func.__name__,
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                    },
                    exc_info=True,
                )
                raise

        return wrapper

    return decorator


def ignore_exceptions(
    *exception_types: type[Exception], default=None
) -> Callable[[F], F]:
    """
    Decorator to catch and ignore specific exceptions, returning a default value.

    Useful for non-critical operations where failures should not stop execution.

    Args:
        *exception_types: Exception types to catch and ignore
        default: Value to return if an exception is caught (default: None)

    Returns:
        Callable: Decorated function that catches exceptions

    Example:
        >>> @ignore_exceptions(ValueError, KeyError, default=[])
        ... def parse_data(data):
        ...     return [int(x) for x in data]

    Warning:
        Use with caution! Swallowing exceptions can hide bugs.
        Only use for truly optional operations.
    """

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except exception_types as e:
                logger.debug(
                    f"Ignored exception in {func.__name__}: {e}",
                    extra={
                        "function": func.__name__,
                        "exception_type": type(e).__name__,
                    },
                )
                return default

        return wrapper

    return decorator


# Commonly used retry configurations as pre-configured decorators

# Standard retry for most network operations
retry_on_network_error = with_retry(
    max_attempts=3, min_wait=1.0, max_wait=10.0, multiplier=2.0
)

# Aggressive retry for critical operations
retry_aggressive = with_retry(
    max_attempts=5, min_wait=2.0, max_wait=30.0, multiplier=2.0
)

# Gentle retry for rate-limited APIs
retry_gentle = with_retry(max_attempts=3, min_wait=5.0, max_wait=60.0, multiplier=3.0)
