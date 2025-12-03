import sys
from pathlib import Path

import numpy as np  # type: ignore
import pandas as pd  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from src.equities.equity_signal_generator import EquitySignalGenerator


def _make_price_frame():
    dates = pd.date_range("2024-01-01", periods=5, freq="D")
    return pd.DataFrame(
        {
            "Date": dates,
            "Close": [100, 101, 102, 103, 104],
            "SMA_20": [99, 100, 101, 102, 103],
            "SMA_50": [98, 99, 100, 101, 102],
            "RSI": [45, 55, 60, 75, 50],
        }
    )


def test_generate_signal_event_and_position_modes():
    price_data = _make_price_frame()
    sentiment = np.full(len(price_data), 0.2)
    generator = EquitySignalGenerator()

    events = generator.generate_signal(price_data, sentiment, mode="event")
    positions = generator.generate_signal(price_data, sentiment, mode="position")

    assert events.tolist() == [0.0, 1.0, 0.0, -1.0, 1.0]
    assert positions.tolist() == [0.0, 1.0, 1.0, 0.0, 1.0]


def test_generate_signal_stop_loss_exit():
    price_data = pd.DataFrame(
        {
            "Date": pd.date_range("2024-02-01", periods=5, freq="D"),
            "Close": [100, 101, 101, 95, 95],
            "SMA_20": [100, 100, 100, 100, 100],
            "SMA_50": [90, 90, 90, 90, 90],
            "RSI": [50, 50, 50, 50, 50],
        }
    )
    sentiment = np.full(len(price_data), 0.2)
    generator = EquitySignalGenerator()

    events = generator.generate_signal(price_data, sentiment, stop_loss_pct=0.05)

    assert events[1] == 1.0  # entry
    assert events[3] == -1.0  # exit triggered by 5% stop
