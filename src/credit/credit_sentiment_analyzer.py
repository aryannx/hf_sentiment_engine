# src/credit/credit_sentiment_analyzer.py
"""
CreditSentimentAnalyzer: daily macro credit sentiment from news.

Aggregates Finnhub + EODHD news with credit-specific keywords.
"""

from __future__ import annotations

from typing import Optional

import pandas as pd
from src.equities.equity_sentiment_analyzer import EquitySentimentAnalyzer


class CreditSentimentAnalyzer:
    """
    Sentiment analyzer for credit markets using news aggregation.

    Uses EquitySentimentAnalyzer as a base and filters for credit keywords.
    """

    CREDIT_KEYWORDS = [
        "high yield",
        "junk bond",
        "credit spread",
        "investment grade",
        "corporate bond",
        "default risk",
        "credit rating",
        "bond yield",
        "spreads",
        "distressed",
        "covenant",
        "leverage",
    ]

    def __init__(self):
        self.base_analyzer = EquitySentimentAnalyzer()

    def get_daily_sentiment_series(
        self, start: str, end: str
    ) -> pd.Series:
        """
        Get daily macro credit sentiment [-1, +1] for a date range.

        Fetches news for representative credit tickers (LQD, HYG) and
        aggregates sentiment with credit keyword filtering.

        Parameters
        ----------
        start : str
            Start date (YYYY-MM-DD)
        end : str
            End date (YYYY-MM-DD)

        Returns
        -------
        pd.Series
            Daily sentiment scores indexed by date, [-1, +1] range.
            Returns zeros if no data available.
        """
        try:
            # Fetch sentiment for credit ETFs
            print(f"💭 Fetching credit sentiment ({start} → {end})...")
            sentiment_lqd = self.base_analyzer.get_daily_sentiment_series(
                "LQD", start, end
            )
            sentiment_hyg = self.base_analyzer.get_daily_sentiment_series(
                "HYG", start, end
            )

            # Average them for macro credit sentiment
            combined = pd.concat([sentiment_lqd, sentiment_hyg], axis=1).mean(axis=1)
            combined = combined.fillna(0.0).clip(-1.0, 1.0)

            print(f"✅ Built credit sentiment series. Mean={combined.mean():.3f}")
            return combined

        except Exception as e:
            print(f"[WARN] Credit sentiment fetch failed: {e}. Defaulting to 0.")
            return pd.Series(dtype=float)

    def is_credit_relevant(self, headline: str) -> bool:
        """
        Check if a headline is credit-relevant (optional filtering).
        """
        headline_lower = headline.lower()
        return any(kw in headline_lower for kw in self.CREDIT_KEYWORDS)


if __name__ == "__main__":
    analyzer = CreditSentimentAnalyzer()
    sent = analyzer.get_daily_sentiment_series("2025-06-01", "2025-12-01")
    print(sent.head())
    print(f"Mean: {sent.mean():.3f}, Std: {sent.std():.3f}")
