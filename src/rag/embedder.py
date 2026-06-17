"""
Embedder — orchestrates data collection and embeds everything
into the vector store. Run this to initialize or refresh.
"""

import json
import argparse
from datetime import datetime
from typing import List, Dict
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config.settings import PORTFOLIO_PATH, CHUNK_SIZE, CHUNK_OVERLAP
from src.collectors.news_collector import fetch_stock_news, fetch_market_news, format_articles_for_rag
from src.collectors.fundamental_collector import scrape_fundamentals, format_fundamentals_for_rag
from src.collectors.macro_collector import get_macro_context, format_macro_for_rag
from src.rag.vector_store import get_vector_store


def load_portfolio() -> List[Dict]:
    with open(PORTFOLIO_PATH) as f:
        data = json.load(f)
    return data["holdings"]


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """Split long text into overlapping chunks."""
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i:i + chunk_size])
        chunks.append(chunk)
        i += chunk_size - overlap
    return chunks


def embed_stock(ticker: str, name: str, store, refresh: bool = False):
    """Embed all data for a single stock."""
    today = datetime.now().strftime("%Y-%m-%d")

    if refresh:
        store.delete_by_ticker(ticker)

    documents = []

    # 1. News articles
    print(f"  → Fetching news for {ticker}...")
    articles = fetch_stock_news(ticker, name)
    news_chunks = format_articles_for_rag(articles, ticker)
    for chunk in news_chunks:
        documents.append({
            "text": chunk,
            "metadata": {
                "ticker": ticker,
                "doc_type": "news",
                "date": today,
                "source": "NewsAPI/MoneyControl",
            }
        })

    # 2. Fundamentals
    print(f"  → Fetching fundamentals for {ticker}...")
    fundamentals = scrape_fundamentals(ticker)
    fund_text = format_fundamentals_for_rag(fundamentals)
    for chunk in chunk_text(fund_text):
        documents.append({
            "text": chunk,
            "metadata": {
                "ticker": ticker,
                "doc_type": "fundamentals",
                "date": today,
                "source": "Screener.in",
            }
        })

    store.upsert(documents)
    print(f"  ✓ Embedded {len(documents)} documents for {ticker}")


def embed_macro(store, refresh: bool = False):
    """Embed macro/market context data."""
    today = datetime.now().strftime("%Y-%m-%d")

    if refresh:
        store.delete_by_ticker("MARKET")

    print("  → Fetching macro data...")
    macro = get_macro_context()
    macro_text = format_macro_for_rag(macro)

    print("  → Fetching market news...")
    market_news = fetch_market_news()
    news_chunks = format_articles_for_rag(market_news, "MARKET")

    documents = []
    for chunk in chunk_text(macro_text):
        documents.append({
            "text": chunk,
            "metadata": {
                "ticker": "MARKET",
                "doc_type": "macro",
                "date": today,
                "source": "RBI/NSE",
            }
        })

    for chunk in news_chunks:
        documents.append({
            "text": chunk,
            "metadata": {
                "ticker": "MARKET",
                "doc_type": "market_news",
                "date": today,
                "source": "MoneyControl/NewsAPI",
            }
        })

    store.upsert(documents)
    print(f"  ✓ Embedded {len(documents)} macro documents")


def run_full_embed(refresh: bool = False):
    """Embed everything — all portfolio stocks + macro."""
    holdings = load_portfolio()
    store = get_vector_store()

    print(f"\n{'='*50}")
    print(f"Indian Portfolio Manager — Embedding Pipeline")
    print(f"Mode: {'Refresh (delete + re-embed)' if refresh else 'Initial'}")
    print(f"Stocks to process: {len(holdings)}")
    print(f"{'='*50}\n")

    # Embed macro context first
    print("[1/2] Embedding market & macro data...")
    embed_macro(store, refresh=refresh)

    # Embed each stock
    print(f"\n[2/2] Embedding {len(holdings)} portfolio stocks...")
    for i, holding in enumerate(holdings, 1):
        ticker = holding["ticker"]
        name = holding["name"]
        print(f"\n  [{i}/{len(holdings)}] {name} ({ticker})")
        embed_stock(ticker, name, store, refresh=refresh)

    info = store.get_collection_info()
    print(f"\n{'='*50}")
    print(f"✓ Done! Total vectors in store: {info.get('vectors_count', 'N/A')}")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Embed portfolio data into vector store")
    parser.add_argument("--init", action="store_true", help="Initial embedding")
    parser.add_argument("--refresh", action="store_true", help="Refresh all data")
    parser.add_argument("--ticker", type=str, help="Refresh a single ticker only")
    args = parser.parse_args()

    if args.ticker:
        store = get_vector_store()
        holdings = load_portfolio()
        match = next((h for h in holdings if h["ticker"] == args.ticker), None)
        name = match["name"] if match else args.ticker
        embed_stock(args.ticker, name, store, refresh=True)
    else:
        run_full_embed(refresh=args.refresh or args.init)
