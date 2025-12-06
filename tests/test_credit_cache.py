import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

from src.credit.credit_data_fetcher import CreditDataFetcher


def test_oas_cache_ttl_expires(tmp_path):
    cache = tmp_path / "fred_oas.pkl"
    df = pd.DataFrame(
        {
            "Date": pd.date_range("2024-01-01", periods=3, freq="D"),
            "hy_oas": [400, 410, 405],
            "ig_oas": [150, 152, 151],
            "hy_ig_oas_spread": [250, 258, 254],
        }
    )
    df.to_pickle(cache)

    # Set mtime to 3 days ago
    old_time = (datetime.now() - timedelta(days=3)).timestamp()
    os.utime(cache, (old_time, old_time))

    # Also drop a meta file with old saved_at
    meta_path = cache.with_suffix(".meta.json")
    meta = {"saved_at": datetime.utcfromtimestamp(old_time).isoformat()}
    meta_path.write_text(json.dumps(meta), encoding="utf-8")

    fetcher = CreditDataFetcher(cache_path=cache, cache_ttl_days=1)
    cached = fetcher._load_cached_oas()
    assert cached is None, "Cache older than TTL should be ignored"


def test_oas_cache_provenance(tmp_path):
    cache = tmp_path / "fred_oas.pkl"
    df = pd.DataFrame(
        {
            "Date": pd.date_range("2024-01-01", periods=3, freq="D"),
            "hy_oas": [400, 410, 405],
            "ig_oas": [150, 152, 151],
            "hy_ig_oas_spread": [250, 258, 254],
        }
    )
    fetcher = CreditDataFetcher(cache_path=cache, cache_ttl_days=1)
    fetcher._save_oas_cache(df)

    meta_path = cache.with_suffix(".meta.json")
    assert meta_path.exists(), "Meta file should be written alongside cache"
    meta = json.loads(meta_path.read_text())
    assert meta.get("rows") == 3
    assert meta.get("source") == "fred"

