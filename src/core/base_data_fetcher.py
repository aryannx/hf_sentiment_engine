"""
BaseDataFetcher: lightweight base class for data fetchers.

Acts as a marker for common fetcher behavior; concrete classes
should implement their own fetch methods.
"""

from __future__ import annotations

from typing import Any


class BaseDataFetcher:
    """Minimal base interface for data fetchers."""

    def fetch(self, *args: Any, **kwargs: Any) -> Any:  # pragma: no cover
        raise NotImplementedError("fetch method must be implemented by subclasses")

