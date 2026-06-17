import os
from dotenv import load_dotenv

load_dotenv()

# --- API Keys ---
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
QDRANT_LOCAL = os.getenv("QDRANT_LOCAL", "false").lower() == "true"

# --- LLM ---
LLM_MODEL = "claude-sonnet-4-6"
LLM_MAX_TOKENS = 1024

# --- Qdrant ---
COLLECTION_NAME = "indian_stocks"

# --- Embeddings ---
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50

# --- Data ---
PORTFOLIO_PATH = "config/portfolio.json"

# NSE indices to track for market context
MARKET_INDICES = {
    "NIFTY50": "^NSEI",      # change to -->  "NIFTY50": "NIFTY_50.NS",
    "SENSEX": "^BSESN",      # change to -->  "SENSEX": "SENSEX.BO",
    "NIFTY_BANK": "^NSEBANK", # change to --> "NIFTY_BANK": "NIFTYBANK.NS",
    "NIFTY_IT": "^CNXIT",    # change to -->  "NIFTY_IT": "NIFTY_IT.NS",
    "NIFTY_AUTO": "^CNXAUTO", # change to --> "NIFTY_AUTO": "NIFTY_AUTO.NS",
}

# Technical indicator settings
RSI_PERIOD = 14
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9
MA_SHORT = 20
MA_LONG = 50

# News sources for Indian markets
NEWS_SOURCES = [
    "the-times-of-india",
    "the-hindu",
]
NEWS_KEYWORDS = [
    "NSE", "BSE", "Nifty", "Sensex", "RBI", "SEBI",
    "Indian stock market", "India economy"
]

# Moneycontrol RSS feeds
MONEYCONTROL_RSS_FEEDS = [
    "https://www.moneycontrol.com/rss/latestnews.xml",
    "https://www.moneycontrol.com/rss/marketreports.xml",
    "https://www.moneycontrol.com/rss/stockreports.xml",
]

# RBI data endpoint
RBI_POLICY_URL = "https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx"

# Screener.in base URL
SCREENER_BASE_URL = "https://www.screener.in/company"

# Discovery — scan these NSE 500 stocks for opportunities
DISCOVERY_UNIVERSE = [
    "BAJFINANCE.NS", "PIDILITIND.NS", "DMART.NS", "TITAN.NS",
    "ZOMATO.NS", "NAUKRI.NS", "LTIM.NS", "HCLTECH.NS",
    "SUNPHARMA.NS", "DRREDDY.NS", "CIPLA.NS", "DIVISLAB.NS",
    "ASIANPAINT.NS", "BERGERPAINTS.NS", "ULTRACEMCO.NS",
    "GRASIM.NS", "POWERGRID.NS", "NTPC.NS", "ONGC.NS",
    "COALINDIA.NS", "BPCL.NS", "IOC.NS", "HINDUNILVR.NS",
    "ITC.NS", "NESTLEIND.NS", "BRITANNIA.NS", "MARICO.NS",
    "ICICIBANK.NS", "KOTAKBANK.NS", "AXISBANK.NS", "INDUSINDBK.NS",
    "BAJAJFINSV.NS", "SBILIFE.NS", "HDFCLIFE.NS", "ICICIGI.NS",
    "MARUTI.NS", "M&M.NS", "HEROMOTOCO.NS", "BAJAJ-AUTO.NS",
    "TECHM.NS", "MPHASIS.NS", "PERSISTENT.NS", "COFORGE.NS",
]
