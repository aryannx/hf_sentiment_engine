# src/equities/equity_sentiment_analyzer.py
import os
from dotenv import load_dotenv
load_dotenv()  # loads .env into os.environ

#print("DEBUG FINNHUB:", os.getenv("FINNHUB_API_KEY"))
#print("DEBUG FMP:", os.getenv("FMP_API_KEY"))
#print("DEBUG EODHD:", os.getenv("EODHD_API_KEY"))


import os
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import requests

from nltk.sentiment import SentimentIntensityAnalyzer
import nltk
nltk.download("vader_lexicon", quiet=True)


class EquitySentimentAnalyzer:
    def __init__(self):
        self.finnhub_key = os.getenv("FINNHUB_API_KEY")
        self.fmp_key = os.getenv("FMP_API_KEY")
        self.eodhd_key = os.getenv("EODHD_API_KEY")
        self.vader = SentimentIntensityAnalyzer()

    def _score(self, text: str) -> float:
        if not text:
            return 0.0
        s = self.vader.polarity_scores(text)["compound"]
        return float(np.clip(s, -1, 1))

    def _finnhub_daily(self, ticker: str, start: str, end: str) -> pd.Series:
        if not self.finnhub_key:
            return pd.Series(dtype=float)

        url = "https://finnhub.io/api/v1/company-news"
        r = requests.get(url, params={"symbol": ticker,
                                      "from": start,
                                      "to": end,
                                      "token": self.finnhub_key},
                         timeout=5)
        if r.status_code != 200:
            return pd.Series(dtype=float)
        rows = []
        for x in r.json():
            dt = datetime.fromtimestamp(x.get("datetime", 0)).date()
            txt = f"{x.get('headline','')} {x.get('summary','')}"
            rows.append({"date": dt, "sent": self._score(txt)})
        if not rows:
            return pd.Series(dtype=float)
        df = pd.DataFrame(rows)
        return df.groupby("date")["sent"].mean().rename("finnhub")

    def _fmp_daily(self, ticker: str, start: str, end: str) -> pd.Series:
        if not self.fmp_key:
            return pd.Series(dtype=float)

        url = "https://financialmodelingprep.com/api/v3/stock_news"
        r = requests.get(url, params={
            "tickers": ticker,
            "from": start,
            "to": end,
            "limit": 200,
            "apikey": self.fmp_key,
        }, timeout=5)
        if r.status_code != 200:
            return pd.Series(dtype=float)
        rows = []
        for x in r.json():
            try:
                dt = datetime.fromisoformat(x["publishedDate"].split("T")[0]).date()
            except Exception:
                continue
            txt = f"{x.get('title','')} {x.get('text','')}"
            rows.append({"date": dt, "sent": self._score(txt)})
        if not rows:
            return pd.Series(dtype=float)
        df = pd.DataFrame(rows)
        return df.groupby("date")["sent"].mean().rename("fmp")

    def _eodhd_daily(self, ticker: str, start: str, end: str) -> pd.Series:
        if not self.eodhd_key:
            return pd.Series(dtype=float)

        url = f"https://eodhd.com/api/news"
        r = requests.get(url, params={
            "s": ticker,
            "from": start,
            "to": end,
            "api_token": self.eodhd_key,
            "fmt": "json",
        }, timeout=5)
        if r.status_code != 200:
            return pd.Series(dtype=float)

        rows = []
        for x in r.json():
            try:
                dt = datetime.fromisoformat(x["date"].split("T")[0]).date()
            except Exception:
                continue
            txt = f"{x.get('title','')} {x.get('content','')}"
            rows.append({"date": dt, "sent": self._score(txt)})
        if not rows:
            return pd.Series(dtype=float)
        df = pd.DataFrame(rows)
        return df.groupby("date")["sent"].mean().rename("eodhd")

    def get_daily_sentiment_series(self, ticker: str, start: str, end: str) -> pd.Series:
        #print(f"DEBUG: get_daily_sentiment_series({ticker}, {start}, {end})")
        #print(f"DEBUG: FINNHUB_API_KEY set? {bool(self.finnhub_key)}")
        #print(f"DEBUG: FMP_API_KEY set? {bool(self.fmp_key)}")
        #print(f"DEBUG: EODHD_API_KEY set? {bool(self.eodhd_key)}")

        s1 = self._finnhub_daily(ticker, start, end)
        #print(f"DEBUG: Finnhub days: {len(s1)}")
        s2 = self._fmp_daily(ticker, start, end)
        #print(f"DEBUG: FMP days: {len(s2)}")
        s3 = self._eodhd_daily(ticker, start, end)
        #print(f"DEBUG: EODHD days: {len(s3)}")

        # Combine
        df = pd.concat([s1, s2, s3], axis=1)

        if df.empty:
            print("DEBUG: df empty after concat → no articles from any source")
            # Always return an EMPTY Series, never None
            return pd.Series(dtype=float)

        # Blend sources by mean across columns
        daily = df.mean(axis=1)
        daily.name = "sentiment"
        daily = daily.sort_index()

        #print(f"DEBUG: daily sentiment days: {len(daily)}")
        #print(f"DEBUG: daily sentiment mean: {daily.mean():.3f}")

        return daily