"""Cache Service — Local persistence for DataFrames using Parquet.

This service reduces AWS Cost Explorer API costs and enables fast offline analysis
by storing query results in local Parquet files.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import polars as pl

logger = logging.getLogger(__name__)

CACHE_DIR = Path.home() / ".remora" / "cache"


class CacheService:
    """Handles local caching of Polars DataFrames using Parquet files."""

    def __init__(
        self,
        cache_dir: Path = CACHE_DIR,
        *,
        enabled: bool = True,
        ttl_seconds: int = 3600,
    ) -> None:
        self.cache_dir = cache_dir
        self.enabled = enabled
        self.ttl_seconds = ttl_seconds
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cleanup()

    def _generate_key(self, query: dict[str, Any]) -> str:
        query_str = json.dumps(query, sort_keys=True, default=str)
        return hashlib.sha256(query_str.encode()).hexdigest()

    def _is_expired(self, cache_file: Path, max_age_hours: int | None) -> bool:
        max_age_seconds = max_age_hours * 3600 if max_age_hours is not None else self.ttl_seconds
        mtime = datetime.fromtimestamp(cache_file.stat().st_mtime)
        return datetime.now() - mtime > timedelta(seconds=max_age_seconds)

    def get(self, query: dict[str, Any], max_age_hours: int | None = None) -> pl.DataFrame | None:
        if not self.enabled:
            return None
        key = self._generate_key(query)
        cache_file = self.cache_dir / f"{key}.parquet"

        if not cache_file.exists():
            return None

        if self._is_expired(cache_file, max_age_hours):
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
        if not self.enabled:
            return
        key = self._generate_key(query)
        cache_file = self.cache_dir / f"{key}.parquet"

        try:
            with tempfile.NamedTemporaryFile(dir=self.cache_dir, suffix=".parquet", delete=False) as temp_file:
                temp_path = Path(temp_file.name)
            try:
                df.write_parquet(temp_path)
                os.replace(temp_path, cache_file)
            finally:
                temp_path.unlink(missing_ok=True)
            logger.debug("Cache saved for query %s", key[:8])
        except Exception as e:
            logger.error("Failed to write cache file %s: %s", cache_file, e)

    def get_json(self, query: dict[str, Any], max_age_hours: int | None = None) -> dict[str, Any] | list[Any] | None:
        if not self.enabled:
            return None
        key = self._generate_key(query)
        cache_file = self.cache_dir / f"{key}.json"

        if not cache_file.exists():
            return None

        if self._is_expired(cache_file, max_age_hours):
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
        if not self.enabled:
            return
        key = self._generate_key(query)
        cache_file = self.cache_dir / f"{key}.json"

        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                dir=self.cache_dir,
                suffix=".json",
                encoding="utf-8",
                delete=False,
            ) as temp_file:
                temp_file.write(json.dumps(data, default=str))
                temp_path = Path(temp_file.name)
            try:
                os.replace(temp_path, cache_file)
            finally:
                temp_path.unlink(missing_ok=True)
            logger.debug("JSON cache saved for query %s", key[:8])
        except Exception as e:
            logger.error("Failed to write JSON cache file %s: %s", cache_file, e)

    def clear(self) -> None:
        for f in self.cache_dir.glob("*.parquet"):
            f.unlink()
        for f in self.cache_dir.glob("*.json"):
            f.unlink()
        logger.info("Cache directory cleared")

    def get_stats(self) -> dict[str, Any]:
        files = list(self.cache_dir.iterdir())
        total_size = sum(f.stat().st_size for f in files if f.is_file())
        count = len([f for f in files if f.is_file()])
        return {
            "path": str(self.cache_dir),
            "size_bytes": total_size,
            "count": count,
        }

    def cleanup(self, max_age_days: int = 7) -> None:
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
