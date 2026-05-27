"""Cache Service — Local persistence for DataFrames using Parquet.

This service reduces AWS Cost Explorer API costs and enables fast offline analysis
by storing query results in local Parquet files.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import polars as pl

logger = logging.getLogger(__name__)

CACHE_DIR = Path.home() / ".remora" / "cache"


class CacheService:
    """Handles local caching of Polars DataFrames using Parquet files."""

    def __init__(self, cache_dir: Path = CACHE_DIR) -> None:
        """Initialize the CacheService with a specific directory.

        Args:
            cache_dir: The directory where cache files will be stored.
        """
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cleanup()

    def _generate_key(self, query: dict[str, Any]) -> str:
        """Generate a unique SHA-256 hash for a Cost Explorer query.

        Args:
            query: The query parameters used for hashing.

        Returns:
            A unique hexadecimal string representing the query.
        """
        query_str = json.dumps(query, sort_keys=True, default=str)
        return hashlib.sha256(query_str.encode()).hexdigest()

    def get(self, query: dict[str, Any], max_age_hours: int = 24) -> pl.DataFrame | None:
        """Retrieve a DataFrame from cache if it exists and is within the age limit.

        Args:
            query: The query parameters used to identify the cache.
            max_age_hours: Maximum age of the cache in hours.

        Returns:
            The cached Polars DataFrame or None if not found or expired.
        """
        key = self._generate_key(query)
        cache_file = self.cache_dir / f"{key}.parquet"

        if not cache_file.exists():
            return None

        mtime = datetime.fromtimestamp(cache_file.stat().st_mtime)
        if datetime.now() - mtime > timedelta(hours=max_age_hours):
            logger.debug("Cache expired for query %s", key[:8])
            return None

        try:
            df = pl.read_parquet(cache_file)
            logger.info("Cache hit for query %s", key[:8])
            return df
        except Exception as e:
            logger.error("Failed to read cache file %s: %s", cache_file, e)
            return None

    def set(self, query: dict[str, Any], df: pl.DataFrame) -> None:
        """Save a Polars DataFrame to a local Parquet cache file.

        Args:
            query: The query parameters used to identify the cache.
            df: The Polars DataFrame to cache.
        """
        key = self._generate_key(query)
        cache_file = self.cache_dir / f"{key}.parquet"

        try:
            df.write_parquet(cache_file)
            logger.debug("Cache saved for query %s", key[:8])
        except Exception as e:
            logger.error("Failed to write cache file %s: %s", cache_file, e)

    def get_json(self, query: dict[str, Any], max_age_hours: int = 24) -> Any | None:
        """Retrieve JSON data from cache if it exists and is within the age limit.

        Args:
            query: The query parameters used to identify the cache.
            max_age_hours: Maximum age of the cache in hours.

        Returns:
            The cached JSON data or None if not found or expired.
        """
        key = self._generate_key(query)
        cache_file = self.cache_dir / f"{key}.json"

        if not cache_file.exists():
            return None

        mtime = datetime.fromtimestamp(cache_file.stat().st_mtime)
        if datetime.now() - mtime > timedelta(hours=max_age_hours):
            logger.debug("JSON cache expired for query %s", key[:8])
            return None

        try:
            data = json.loads(cache_file.read_text(encoding="utf-8"))
            logger.info("JSON cache hit for query %s", key[:8])
            return data
        except Exception as e:
            logger.error("Failed to read JSON cache file %s: %s", cache_file, e)
            return None

    def set_json(self, query: dict[str, Any], data: Any) -> None:
        """Save arbitrary data to a local JSON cache file.

        Args:
            query: The query parameters used to identify the cache.
            data: The data to cache (must be JSON serializable).
        """
        key = self._generate_key(query)
        cache_file = self.cache_dir / f"{key}.json"

        try:
            cache_file.write_text(json.dumps(data, default=str), encoding="utf-8")
            logger.debug("JSON cache saved for query %s", key[:8])
        except Exception as e:
            logger.error("Failed to write JSON cache file %s: %s", cache_file, e)

    def clear(self) -> None:
        """Clear all cached files in the cache directory."""
        for f in self.cache_dir.glob("*.parquet"):
            f.unlink()
        for f in self.cache_dir.glob("*.json"):
            f.unlink()
        logger.info("Cache directory cleared")

    def cleanup(self, max_age_days: int = 7) -> None:
        """Remove cache files older than max_age_days.

        Args:
            max_age_days: Files older than this will be deleted.
        """
        cutoff = datetime.now() - timedelta(days=max_age_days)
        count = 0
        for f in self.cache_dir.iterdir():
            if f.is_file() and (f.suffix in [".parquet", ".json"]):
                mtime = datetime.fromtimestamp(f.stat().st_mtime)
                if mtime < cutoff:
                    f.unlink()
                    count += 1
        if count > 0:
            logger.info("Auto-cleanup: removed %d expired cache files", count)
