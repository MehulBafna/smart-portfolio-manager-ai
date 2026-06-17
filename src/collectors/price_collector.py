"""
Price Collector — fetches OHLCV data and computes technical indicators
using yfinance for NSE-listed stocks.
"""
import requests
import yfinance as yf
import pandas as pd
import numpy as np
from ta.momentum import RSIIndicator
from ta.trend import MACD, SMAIndicator, EMAIndicator
from ta.volatility import BollingerBands
from datetime import datetime, timedelta
from typing import Optional
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import RSI_PERIOD, MACD_FAST, MACD_SLOW, MACD_SIGNAL, MA_SHORT, MA_LONG


def fetch_price_data(ticker: str, period: str = "6mo") -> Optional[pd.DataFrame]:
    """Fetch OHLCV data for a given NSE ticker."""
    try:
        import time
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        stock = yf.Ticker(ticker, session=session)
        df = stock.history(period=period)
        if df.empty:
            # Retry once with longer period
            time.sleep(1)
            df = stock.history(period="1y")
        if df.empty:
            print(f"[WARN] No data for {ticker}")
            return None
        df.index = df.index.tz_localize(None)
        return df
    except Exception as e:
        print(f"[ERROR] fetch_price_data({ticker}): {e}")
        return None


def compute_technicals(df: pd.DataFrame) -> dict:
    """
    Compute RSI, MACD, Moving Averages, Bollinger Bands.
    Returns a dict with latest values and signals.
    """
    close = df["Close"]

    # RSI
    rsi = RSIIndicator(close=close, window=RSI_PERIOD)
    rsi_val = round(rsi.rsi().iloc[-1], 2)

    # MACD
    macd = MACD(close=close, window_fast=MACD_FAST, window_slow=MACD_SLOW, window_sign=MACD_SIGNAL)
    macd_val = round(macd.macd().iloc[-1], 4)
    macd_signal_val = round(macd.macd_signal().iloc[-1], 4)
    macd_hist = round(macd.macd_diff().iloc[-1], 4)

    # Moving Averages
    sma20 = SMAIndicator(close=close, window=MA_SHORT).sma_indicator().iloc[-1]
    sma50 = SMAIndicator(close=close, window=MA_LONG).sma_indicator().iloc[-1]
    ema20 = EMAIndicator(close=close, window=MA_SHORT).ema_indicator().iloc[-1]

    # Bollinger Bands
    bb = BollingerBands(close=close, window=20, window_dev=2)
    bb_upper = round(bb.bollinger_hband().iloc[-1], 2)
    bb_lower = round(bb.bollinger_lband().iloc[-1], 2)
    bb_middle = round(bb.bollinger_mavg().iloc[-1], 2)

    # Price info
    current_price = round(close.iloc[-1], 2)
    prev_close = round(close.iloc[-2], 2)
    price_change_pct = round(((current_price - prev_close) / prev_close) * 100, 2)

    # 52-week high/low
    high_52w = round(df["High"].tail(252).max(), 2)
    low_52w = round(df["Low"].tail(252).min(), 2)

    # Volume analysis
    avg_volume_20d = int(df["Volume"].tail(20).mean())
    latest_volume = int(df["Volume"].iloc[-1])
    volume_surge = round(latest_volume / avg_volume_20d, 2) if avg_volume_20d > 0 else 1.0

    # --- Signal interpretation ---
    rsi_signal = (
        "Oversold (potential buy)" if rsi_val < 30
        else "Overbought (consider selling)" if rsi_val > 70
        else "Neutral"
    )

    macd_signal_str = (
        "Bullish crossover" if macd_val > macd_signal_val and macd_hist > 0
        else "Bearish crossover" if macd_val < macd_signal_val and macd_hist < 0
        else "Neutral"
    )

    trend = (
        "Strong uptrend" if current_price > sma20 > sma50
        else "Uptrend" if current_price > sma50
        else "Downtrend" if current_price < sma50
        else "Sideways"
    )

    price_vs_bb = (
        "Near upper band (overbought zone)" if current_price >= bb_upper * 0.98
        else "Near lower band (oversold zone)" if current_price <= bb_lower * 1.02
        else "Within bands (normal)"
    )

    return {
        "ticker": df.index.name or "N/A",
        "current_price": current_price,
        "prev_close": prev_close,
        "price_change_pct": price_change_pct,
        "high_52w": high_52w,
        "low_52w": low_52w,
        "rsi": rsi_val,
        "rsi_signal": rsi_signal,
        "macd": macd_val,
        "macd_signal": macd_signal_val,
        "macd_hist": macd_hist,
        "macd_interpretation": macd_signal_str,
        "sma_20": round(sma20, 2),
        "sma_50": round(sma50, 2),
        "ema_20": round(ema20, 2),
        "bb_upper": bb_upper,
        "bb_lower": bb_lower,
        "bb_middle": bb_middle,
        "price_vs_bb": price_vs_bb,
        "trend": trend,
        "avg_volume_20d": avg_volume_20d,
        "latest_volume": latest_volume,
        "volume_surge": volume_surge,
    }


def get_stock_info(ticker: str) -> dict:
    """Get basic stock metadata from yfinance."""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        return {
            "name": info.get("longName", ticker),
            "sector": info.get("sector", "N/A"),
            "industry": info.get("industry", "N/A"),
            "market_cap": info.get("marketCap", 0),
            "pe_ratio": info.get("trailingPE", None),
            "pb_ratio": info.get("priceToBook", None),
            "dividend_yield": info.get("dividendYield", None),
            "beta": info.get("beta", None),
            "description": info.get("longBusinessSummary", "")[:500],
        }
    except Exception as e:
        print(f"[ERROR] get_stock_info({ticker}): {e}")
        return {}


def get_full_analysis(ticker: str) -> dict:
    """Master function — returns price data + technicals + info."""
    df = fetch_price_data(ticker)
    if df is None:
        return {"error": f"Could not fetch data for {ticker}"}

    technicals = compute_technicals(df)
    info = get_stock_info(ticker)

    return {
        "ticker": ticker,
        "info": info,
        "technicals": technicals,
        "price_history": df,  # raw DataFrame for charting
    }


if __name__ == "__main__":
    result = get_full_analysis("RELIANCE.NS")
    print(f"Price: ₹{result['technicals']['current_price']}")
    print(f"RSI: {result['technicals']['rsi']} — {result['technicals']['rsi_signal']}")
    print(f"MACD: {result['technicals']['macd_interpretation']}")
    print(f"Trend: {result['technicals']['trend']}")
