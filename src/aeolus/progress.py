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
Progress indicator wrapper for Aeolus.

Provides a ``track()`` function that wraps iterables with a tqdm progress
bar when available, falling back to logging when tqdm is not installed.

Install tqdm for visual progress bars::

    pip install aeolus[progress]
"""

import logging

logger = logging.getLogger(__name__)


def track(iterable, description="", total=None):
    """Wrap an iterable with a progress bar if tqdm is available.

    Uses ``tqdm.auto`` which automatically picks the right frontend
    (terminal, Jupyter notebook, etc.).  If tqdm is not installed,
    falls back to ``logging.info`` messages.

    When *total* is 1, no progress bar is shown (no overhead for
    single-item fetches).

    Args:
        iterable: The iterable to wrap.
        description: Short label for the progress bar.
        total: Total number of items (inferred from iterable if possible).

    Returns:
        An iterable that yields the same items, optionally with progress.
    """
    # Infer total if not provided
    if total is None:
        try:
            total = len(iterable)
        except TypeError:
            pass

    # Skip progress for single-item iterables
    if total is not None and total <= 1:
        return iterable

    try:
        from tqdm.auto import tqdm

        return tqdm(iterable, desc=description, total=total)
    except ImportError:
        return _LoggingProgress(iterable, description, total)


class _LoggingProgress:
    """Fallback progress reporter using logging when tqdm is unavailable."""

    def __init__(self, iterable, description, total):
        self._iterable = iterable
        self._description = description
        self._total = total

    def __iter__(self):
        total_str = f"/{self._total}" if self._total else ""
        for i, item in enumerate(self._iterable, 1):
            logger.info("%s %d%s", self._description, i, total_str)
            yield item

    def __len__(self):
        if self._total is not None:
            return self._total
        return len(self._iterable)
