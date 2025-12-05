import pandas as pd
from datetime import datetime, timedelta
from src.data.validators import check_staleness, check_missing, check_spikes


def test_staleness_detects_old_data():
    dates = [datetime.utcnow() - timedelta(days=3)]
    df = pd.DataFrame({"Date": dates, "Close": [100]})
    msgs = check_staleness(df, max_age_days=2)
    assert msgs


def test_missing_detects_nan():
    df = pd.DataFrame({"Date": [datetime.utcnow()], "Close": [None]})
    msgs = check_missing(df, ["Date", "Close"])
    assert msgs


def test_spikes_detects_outlier():
    df = pd.DataFrame({"Close": [100, 101, 102, 300]})
    msgs = check_spikes(df, z_thresh=2.0)
    assert msgs

