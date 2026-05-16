from pathlib import Path
import polars as pl

from remora.services.cache_service import CacheService


def test_cache_key_consistency() -> None:
    cache = CacheService()
    query1 = {"Start": "2024-01-01", "Metrics": ["UnblendedCost"]}
    query2 = {"Metrics": ["UnblendedCost"], "Start": "2024-01-01"}
    assert cache._generate_key(query1) == cache._generate_key(query2)


def test_cache_set_get(tmp_path: Path) -> None:
    # Use temporary directory for testing
    cache = CacheService(cache_dir=tmp_path)
    df = pl.DataFrame({"a": [1, 2], "b": [3, 4]})
    query = {"id": "test"}

    cache.set(query, df)
    cached_df = cache.get(query)

    assert cached_df is not None
    assert cached_df.equals(df)


def test_cache_expiration(tmp_path: Path) -> None:
    cache = CacheService(cache_dir=tmp_path)
    df = pl.DataFrame({"a": [1]})
    query = {"id": "exp"}
    cache.set(query, df)

    # Simulate old file (25 hours ago)
    import os
    import time

    old_time = time.time() - (25 * 3600)
    for f in tmp_path.glob("*.parquet"):
        os.utime(f, (old_time, old_time))

    assert cache.get(query, max_age_hours=24) is None
