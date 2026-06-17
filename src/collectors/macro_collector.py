"""
Macro Collector — fetches Indian macroeconomic data:
- RBI repo rate (scraped from RBI website)
- FII/DII activity from NSE
- Nifty index data as market context
"""

import requests
from bs4 import BeautifulSoup
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import MARKET_INDICES

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
    )
}


def fetch_index_data() -> Dict:
    """Fetch current data for major Indian market indices."""
    indices = {}
    for name, ticker in MARKET_INDICES.items():
        try:
            idx = yf.Ticker(ticker)
            hist = idx.history(period="5d")
            if not hist.empty:
                current = round(hist["Close"].iloc[-1], 2)
                prev = round(hist["Close"].iloc[-2], 2)
                change_pct = round(((current - prev) / prev) * 100, 2)
                indices[name] = {
                    "current": current,
                    "prev_close": prev,
                    "change_pct": change_pct,
                    "trend": "up" if change_pct > 0 else "down",
                }
        except Exception as e:
            print(f"[ERROR] Index fetch {name}: {e}")
            indices[name] = {"error": str(e)}
    return indices


def fetch_nse_fii_dii() -> Dict:
    """
    Fetch FII/DII activity data from NSE website.
    Returns net buy/sell figures.
    """
    url = "https://www.nseindia.com/api/fiidiiTradeReact"
    headers = {
        **HEADERS,
        "Referer": "https://www.nseindia.com/reports/fii-dii",
        "Accept": "application/json",
    }
    session = requests.Session()
    # NSE requires a session cookie — first hit the main page
    try:
        session.get("https://www.nseindia.com", headers=HEADERS, timeout=10)
        resp = session.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list) and len(data) > 0:
                latest = data[0]
                return {
                    "date": latest.get("date", "N/A"),
                    "fii_net": latest.get("fiinet", "N/A"),
                    "dii_net": latest.get("diinet", "N/A"),
                    "fii_buy": latest.get("fiiBuy", "N/A"),
                    "fii_sell": latest.get("fiiSell", "N/A"),
                    "dii_buy": latest.get("diiBuy", "N/A"),
                    "dii_sell": latest.get("diiSell", "N/A"),
                }
    except Exception as e:
        print(f"[ERROR] NSE FII/DII fetch: {e}")

    # Fallback: return simulated structure so system doesn't break
    return {
        "date": datetime.now().strftime("%d-%b-%Y"),
        "fii_net": "Data unavailable",
        "dii_net": "Data unavailable",
        "note": "NSE API requires browser session — check NSE website directly",
        "nse_url": "https://www.nseindia.com/reports/fii-dii",
    }


def fetch_rbi_policy_rate() -> Dict:
    """
    Scrape current RBI repo rate from RBI website.
    Falls back to known rate if scraping fails.
    """
    url = "https://www.rbi.org.in/Scripts/bs_viewcontent.aspx?Id=4"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")
        # Look for repo rate in text
        text = soup.get_text()
        if "Repo Rate" in text or "repo rate" in text:
            # Extract the percentage near "Repo Rate"
            import re
            matches = re.findall(r"[Rr]epo [Rr]ate.*?(\d+\.\d+)%", text)
            if matches:
                return {
                    "repo_rate": float(matches[0]),
                    "source": "RBI website",
                    "note": "Current RBI repo rate"
                }
    except Exception as e:
        print(f"[ERROR] RBI scrape: {e}")

    # Fallback to last known rate (update manually if needed)
    return {
        "repo_rate": 6.50,
        "source": "Last known value (June 2025)",
        "note": "RBI held rates steady. Verify at https://www.rbi.org.in",
        "rbi_url": "https://www.rbi.org.in",
    }


def get_macro_context() -> Dict:
    """Master function — returns full macro picture."""
    indices = fetch_index_data()
    fii_dii = fetch_nse_fii_dii()
    rbi = fetch_rbi_policy_rate()

    # Market sentiment from Nifty
    nifty = indices.get("NIFTY50", {})
    if isinstance(nifty, dict) and "change_pct" in nifty:
        change = nifty["change_pct"]
        if change > 1.5:
            market_mood = "Strongly Bullish"
        elif change > 0.3:
            market_mood = "Mildly Bullish"
        elif change < -1.5:
            market_mood = "Strongly Bearish"
        elif change < -0.3:
            market_mood = "Mildly Bearish"
        else:
            market_mood = "Neutral / Consolidating"
    else:
        market_mood = "Unknown"

    return {
        "indices": indices,
        "fii_dii": fii_dii,
        "rbi_policy": rbi,
        "market_mood": market_mood,
        "timestamp": datetime.now().isoformat(),
    }


def format_macro_for_rag(macro: Dict) -> str:
    """Format macro context as text for embedding."""
    lines = ["Indian Market Macro Context"]

    nifty = macro.get("indices", {}).get("NIFTY50", {})
    if "current" in nifty:
        lines.append(
            f"Nifty 50: {nifty['current']} "
            f"({'+' if nifty['change_pct'] > 0 else ''}{nifty['change_pct']}%)"
        )

    sensex = macro.get("indices", {}).get("SENSEX", {})
    if "current" in sensex:
        lines.append(
            f"Sensex: {sensex['current']} "
            f"({'+' if sensex['change_pct'] > 0 else ''}{sensex['change_pct']}%)"
        )

    rbi = macro.get("rbi_policy", {})
    lines.append(f"RBI Repo Rate: {rbi.get('repo_rate', 'N/A')}%")

    fii = macro.get("fii_dii", {})
    lines.append(f"FII Net: {fii.get('fii_net', 'N/A')} | DII Net: {fii.get('dii_net', 'N/A')}")
    lines.append(f"Overall Market Mood: {macro.get('market_mood', 'N/A')}")

    return "\n".join(lines)


if __name__ == "__main__":
    macro = get_macro_context()
    print(f"Market Mood: {macro['market_mood']}")
    print(f"Nifty: {macro['indices'].get('NIFTY50', {})}")
    print(f"RBI Rate: {macro['rbi_policy']['repo_rate']}%")
