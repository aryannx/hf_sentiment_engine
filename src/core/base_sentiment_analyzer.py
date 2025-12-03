# src/core/base_sentiment_analyzer.py
"""
Abstract base class for sentiment analysis
Works for equity news, credit events, macro news, etc.
"""

from abc import ABC, abstractmethod


class BaseSentimentAnalyzer(ABC):
    """
    Abstract base for sentiment analysis across all asset classes
    """

    @abstractmethod
    def get_sentiment(self, symbol, **kwargs):
        """
        Return sentiment score (-1 to 1) for a symbol/asset

        Args:
            symbol: str (ticker, ETF, or asset identifier)
            **kwargs: source-specific parameters

        Returns:
            float: sentiment score (-1 to 1)
                -1.0 = strongly negative
                 0.0 = neutral
                +1.0 = strongly positive
        """
        pass
