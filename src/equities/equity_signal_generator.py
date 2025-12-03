# src/equities/equity_signal_generator.py
"""
Equity signal generator: combine news sentiment + technical trend filters.

Design is aligned with common hedge-fund / academic practices:
- Sentiment: 3-day rolling average, thresholds at +/- 0.05 (VADER-style)
- Trend: SMA20 > SMA50 and Close > SMA50 (short/medium-term uptrend)
- Entries: only when trend is up AND sentiment is bullish
- Exits: sentiment turns bearish, trend breaks, RSI > 70, or stop-loss

Inherits from BaseSignalGenerator for shared metrics (Sharpe, MaxDD, win_rate).
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Ensure src/ is on path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.base_signal_generator import BaseSignalGenerator


class EquitySignalGenerator(BaseSignalGenerator):
    """
    Generate buy/sell/hold signals for equities.
    Combines:
      - Price trend (SMA20/SMA50, optional RSI)
      - News sentiment (time-varying series)

    Supports two modes:
      - mode="event": +1/-1 only on entry/exit bars (single-bar exposure)
      - mode="position": +1 while in long position, 0 when flat
    """

    def __init__(self):
        super().__init__()
        self.signals = {}

    # ---------- core event logic ----------

    def _generate_event_signals(
        self,
        price_data: pd.DataFrame,
        sentiment,
        sentiment_threshold: float = 0.05,
        use_rsi: bool = True,
        use_sma: bool = True,
        stop_loss_pct: float = 0.05,
    ) -> np.ndarray:
        """
        Core signal logic that emits *events*:
        +1 on entry bars, -1 on exit bars, 0 otherwise.

        This is your original behavior.
        """

        n = len(price_data)
        signals = np.zeros(n, dtype=float)

        # Broadcast scalar sentiment to array
        if np.isscalar(sentiment):
            sentiment_arr = np.full(n, float(sentiment), dtype=float)
        else:
            sentiment_arr = np.asarray(sentiment, dtype=float)
            assert len(sentiment_arr) == n, "sentiment length must match price_data"

        # 3-day rolling mean of sentiment (common in literature)
        sent_ma3 = (
            pd.Series(sentiment_arr)
            .rolling(window=3, min_periods=1)
            .mean()
            .to_numpy()
        )

        closes = price_data["Close"].to_numpy()
        sma20 = (
            price_data["SMA_20"].to_numpy()
            if "SMA_20" in price_data.columns
            else closes
        )
        sma50 = (
            price_data["SMA_50"].to_numpy()
            if "SMA_50" in price_data.columns
            else closes
        )
        rsi = (
            price_data["RSI"].to_numpy()
            if "RSI" in price_data.columns
            else np.full(n, 50.0)
        )

        in_position = False
        entry_price = None

        for i in range(1, n):
            c = closes[i]
            s_ma3 = sent_ma3[i]

            s20, s50 = sma20[i], sma50[i]
            s20_prev, s50_prev = sma20[i - 1], sma50[i - 1]
            r = rsi[i]

            # Trend filters
            if use_sma:
                # Basic uptrend: fast MA above slow, price above slow MA
                trend_up = (s20 > s50) and (c > s50)
                trend_down = (s20 < s50) or (c < s50)

                # Golden/death cross info (not strictly required to fire)
                cross_up = (s20 > s50) and (s20_prev <= s50_prev)
                cross_down = (s20 < s50) and (s20_prev >= s50_prev)
            else:
                trend_up = True
                trend_down = False
                cross_up = cross_down = False

            # RSI filters
            if use_rsi:
                rsi_ok_for_entry = (30.0 <= r <= 70.0)
                rsi_overbought = (r > 70.0)
            else:
                rsi_ok_for_entry = True
                rsi_overbought = False

            # Sentiment filters (3-day mean)
            bullish_sent = s_ma3 >= sentiment_threshold
            bearish_sent = s_ma3 <= -sentiment_threshold

            # Stop-loss (only if in position)
            stop_hit = False
            if in_position and entry_price is not None:
                stop_hit = c <= entry_price * (1.0 - stop_loss_pct)

            # ENTRY logic: need uptrend + acceptable RSI + bullish sentiment
            if not in_position:
                if trend_up and rsi_ok_for_entry and bullish_sent:
                    signals[i] = 1.0     # ENTRY event
                    in_position = True
                    entry_price = c
                else:
                    signals[i] = 0.0
                continue

            # EXIT logic (when already in position)
            exit_on_trend = trend_down or cross_down
            exit_on_sentiment = bearish_sent
            exit_on_rsi = rsi_overbought

            if exit_on_trend or exit_on_sentiment or exit_on_rsi or stop_hit:
                signals[i] = -1.0    # EXIT event
                in_position = False
                entry_price = None
            else:
                signals[i] = 0.0     # no event this bar

        return signals



    # ---------- event → position conversion ----------

    @staticmethod
    @staticmethod
    def _events_to_positions(events: np.ndarray) -> np.ndarray:
        """
        Convert entry/exit events into a position series:
        +1 while long, 0 when flat.

        Assumes:
          +1 event = open long
          -1 event = close long (go flat)

        Position carries forward until explicitly closed.
        """
        pos = np.zeros_like(events, dtype=float)
        holding = 0.0

        for i, e in enumerate(events):
            if e == 1.0:  # entry event
                holding = 1.0
            elif e == -1.0:  # exit event
                holding = 0.0
            # else: e == 0.0, keep holding unchanged

            pos[i] = holding

        return pos

    # ---------- public API ----------

    def generate_signal(
        self,
        price_data: pd.DataFrame,
        sentiment,
        sentiment_threshold: float = 0.05,
        use_rsi: bool = True,
        use_sma: bool = True,
        stop_loss_pct: float = 0.05,
        mode: str = "event",   # "event" or "position"
    ) -> np.ndarray:
        """
        Generate hybrid buy/sell/hold signals.

        mode="event":
            +1 only on entry bar, -1 only on exit bar, 0 otherwise.
        mode="position":
            +1 while in long position, 0 when flat.
        """
        events = self._generate_event_signals(
            price_data=price_data,
            sentiment=sentiment,
            sentiment_threshold=sentiment_threshold,
            use_rsi=use_rsi,
            use_sma=use_sma,
            stop_loss_pct=stop_loss_pct,
        )

        if mode == "event":
            return events
        elif mode == "position":
            return self._events_to_positions(events)
        else:
            raise ValueError(f"Unknown mode '{mode}'. Use 'event' or 'position'.")

    def generate_signal_conservative(self, price_data, sentiment, mode: str = "event"):
        """
        Conservative variant:
        - Higher sentiment threshold (0.1)
        - RSI filter ON
        - SMA trend filter ON
        - Same stop-loss
        """
        return self.generate_signal(
            price_data,
            sentiment,
            sentiment_threshold=0.10,
            use_rsi=True,
            use_sma=True,
            stop_loss_pct=0.05,
            mode=mode,
        )

    def generate_signal_aggressive(self, price_data, sentiment, mode: str = "event"):
        """
        Aggressive variant:
        - Lower sentiment threshold (0.03)
        - RSI filter optional
        - SMA trend filter ON
        """
        return self.generate_signal(
            price_data,
            sentiment,
            sentiment_threshold=0.03,
            use_rsi=False,
            use_sma=True,
            stop_loss_pct=0.05,
            mode=mode,
        )



if __name__ == "__main__":
    """
    Simple standalone test:
    - Fetch price data
    - Build blended daily sentiment via EquitySentimentAnalyzer
    - Generate signals
    - Print summary metrics via BaseSignalGenerator
    """
    from equities.equity_data_fetcher import EquityDataFetcher
    from equities.equity_sentiment_analyzer import EquitySentimentAnalyzer

    ticker = "AAPL"
    period = "1y"

    print("=" * 60)
    print(f"EQUITY SIGNAL GENERATOR TEST – {ticker}")
    print("=" * 60)

    # 1) Price data
    fetcher = EquityDataFetcher()
    print(f"\n📊 Fetching {ticker} data ({period})...")
    price_data = fetcher.fetch_stock_data(ticker, period=period)

    if price_data.empty:
        print("❌ Failed to fetch data")
        sys.exit(1)

    print(f"✅ Fetched {len(price_data)} rows")

    # 2) Daily sentiment (real APIs)
    analyzer = EquitySentimentAnalyzer()
    start = price_data["Date"].min().strftime("%Y-%m-%d")
    end = price_data["Date"].max().strftime("%Y-%m-%d")
    print(f"\n💭 Fetching blended sentiment [{start} → {end}]...")
    daily_sent = analyzer.get_daily_sentiment_series(ticker, start, end)

    if daily_sent.empty:
        print("⚠️ No sentiment data; defaulting to zeros")
        sentiment_series = np.zeros(len(price_data))
    else:
        sentiment_series = (
            daily_sent.reindex(price_data["Date"])
            .fillna(0.0)
            .to_numpy()
        )

    print(f"✅ Sentiment mean: {sentiment_series.mean():.3f}")

    # 3) Signals
    print("\n🎯 Generating signals...")
    sig_gen = EquitySignalGenerator()
    signals = sig_gen.generate_signal(price_data, sentiment_series)

    buys = int((signals == 1).sum())
    sells = int((signals == -1).sum())
    print(f"✅ Signals: {buys} BUY, {sells} SELL, {int((signals == 0).sum())} HOLD")

    # 4) Strategy report (BaseSignalGenerator)
    print("\n📈 Computing metrics (BaseSignalGenerator)...")
    report = sig_gen.generate_strategy_report(price_data, signals, sentiment_series)

    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"Total Signals:      {report['total_signals']}")
    print(f"Buy Signals:        {report['buy_signals']}")
    print(f"Sell Signals:       {report['sell_signals']}")
    print(f"Avg Sentiment:      {report['avg_sentiment']:.3f}")
    print(f"Win Rate:           {report['win_rate']:.2%}")
    print(f"Total Trades:       {report['total_trades']}")
    print(f"Sharpe Ratio:       {report['sharpe_ratio']:.2f}")
    print(f"Max Drawdown:       {report['max_drawdown']:.2%}")
    print("=" * 60)
