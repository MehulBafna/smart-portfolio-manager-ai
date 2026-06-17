"""
Router — smart query routing logic.
Determines which data sources to retrieve from based on the question type.

Query types:
  - stock_specific   → retrieve from that stock's news + fundamentals + technicals
  - macro_impact     → retrieve macro data + sector-specific stocks
  - comparison       → retrieve multiple stocks
  - discovery        → scan watchlist stocks
  - general_market   → retrieve market-wide news + macro
"""

import re
from typing import Dict, List, Tuple
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from src.rag.vector_store import get_vector_store


# Keywords that suggest macro/economy focus
MACRO_KEYWORDS = [
    "rbi", "repo rate", "interest rate", "inflation", "gdp",
    "fii", "dii", "foreign investor", "budget", "fiscal",
    "economy", "recession", "global", "fed", "dollar", "rupee",
    "crude oil", "commodity"
]

# Keywords that suggest buy/discovery
DISCOVERY_KEYWORDS = [
    "buy", "invest", "recommend", "suggest", "new stock",
    "which stock", "good stock", "upcoming", "opportunity",
    "undervalued", "growth stock"
]

# Keywords that suggest sell/exit
EXIT_KEYWORDS = [
    "sell", "exit", "when to sell", "book profit", "stop loss",
    "hold or sell", "get out", "target"
]

# Keywords that suggest sector-wide analysis
SECTOR_KEYWORDS = {
    "IT": ["it", "tech", "software", "infosys", "tcs", "wipro", "hcltech"],
    "BANKING": ["bank", "banking", "hdfc", "sbi", "icici", "kotak", "nbfc"],
    "AUTO": ["auto", "automobile", "car", "ev", "tata motors", "maruti", "bajaj"],
    "PHARMA": ["pharma", "drug", "medicine", "healthcare", "sun pharma", "dr reddy"],
    "ENERGY": ["oil", "gas", "energy", "reliance", "ongc", "bpcl"],
}


def classify_query(query: str) -> Dict:
    """
    Classify the user query and determine routing strategy.
    Returns: {
        query_type, tickers_mentioned, sectors, needs_macro,
        needs_discovery, intent
    }
    """
    q_lower = query.lower()

    # Detect mentioned tickers or company names
    tickers_mentioned = []
    # Simple check for common NSE tickers in query
    common_tickers = {
        "reliance": "RELIANCE.NS", "infy": "INFY.NS", "infosys": "INFY.NS",
        "tcs": "TCS.NS", "wipro": "WIPRO.NS", "hdfc": "HDFCBANK.NS",
        "hdfcbank": "HDFCBANK.NS", "sbi": "SBIN.NS", "tatamotors": "TATAMOTORS.NS",
        "tata motors": "TATAMOTORS.NS", "adani": "ADANIENT.NS",
        "bajaj finance": "BAJFINANCE.NS", "zomato": "ZOMATO.NS",
    }
    for name, ticker in common_tickers.items():
        if name in q_lower:
            tickers_mentioned.append(ticker)

    # Detect sectors
    sectors_mentioned = []
    for sector, keywords in SECTOR_KEYWORDS.items():
        if any(kw in q_lower for kw in keywords):
            sectors_mentioned.append(sector)

    # Detect intent
    needs_macro = any(kw in q_lower for kw in MACRO_KEYWORDS)
    needs_discovery = any(kw in q_lower for kw in DISCOVERY_KEYWORDS)
    is_exit_question = any(kw in q_lower for kw in EXIT_KEYWORDS)

    # Classify query type
    if tickers_mentioned and len(tickers_mentioned) == 1:
        query_type = "stock_specific"
    elif tickers_mentioned and len(tickers_mentioned) > 1:
        query_type = "comparison"
    elif needs_discovery and not tickers_mentioned:
        query_type = "discovery"
    elif needs_macro:
        query_type = "macro_impact"
    elif sectors_mentioned:
        query_type = "sector_analysis"
    else:
        query_type = "general_market"

    intent = (
        "exit_strategy" if is_exit_question
        else "buy_recommendation" if needs_discovery
        else "analysis"
    )

    return {
        "query_type": query_type,
        "tickers_mentioned": tickers_mentioned,
        "sectors_mentioned": sectors_mentioned,
        "needs_macro": needs_macro,
        "needs_discovery": needs_discovery,
        "intent": intent,
    }


def route_and_retrieve(query: str, portfolio_tickers: List[str] = None) -> Dict:
    """
    Route the query and retrieve relevant context from the vector store.
    Returns structured context for the LLM.
    """
    store = get_vector_store()
    routing = classify_query(query)
    context_chunks = []

    query_type = routing["query_type"]
    tickers = routing["tickers_mentioned"]

    print(f"[Router] Query type: {query_type} | Tickers: {tickers} | Intent: {routing['intent']}")

    if query_type == "stock_specific" and tickers:
        ticker = tickers[0]
        # Retrieve news + fundamentals for this stock
        news = store.search(query, top_k=4, ticker_filter=ticker, doc_type_filter="news")
        funds = store.search(query, top_k=2, ticker_filter=ticker, doc_type_filter="fundamentals")
        macro = store.search(query, top_k=2, ticker_filter="MARKET")
        context_chunks = news + funds + macro

    elif query_type == "comparison" and tickers:
        # Retrieve for each mentioned ticker
        for ticker in tickers[:3]:
            chunks = store.search(query, top_k=3, ticker_filter=ticker)
            context_chunks.extend(chunks)
        # Add macro context
        macro = store.search(query, top_k=2, ticker_filter="MARKET")
        context_chunks.extend(macro)

    elif query_type == "macro_impact":
        # Heavy on macro, light on specific stocks
        macro = store.search(query, top_k=5, ticker_filter="MARKET")
        context_chunks.extend(macro)
        # If sectors mentioned, add sector stocks
        if routing["sectors_mentioned"] and portfolio_tickers:
            for ticker in portfolio_tickers[:3]:
                chunks = store.search(query, top_k=2, ticker_filter=ticker)
                context_chunks.extend(chunks)

    elif query_type == "discovery":
        # General market + macro
        market = store.search(query, top_k=4, ticker_filter="MARKET")
        context_chunks.extend(market)

    elif query_type == "sector_analysis":
        # Retrieve for portfolio stocks in that sector + macro
        macro = store.search(query, top_k=3, ticker_filter="MARKET")
        context_chunks.extend(macro)
        if portfolio_tickers:
            for ticker in portfolio_tickers[:4]:
                chunks = store.search(query, top_k=2, ticker_filter=ticker)
                context_chunks.extend(chunks)

    else:  # general_market
        context_chunks = store.search(query, top_k=6, ticker_filter="MARKET")

    # Deduplicate
    seen = set()
    unique_chunks = []
    for c in context_chunks:
        if c["text"] not in seen:
            seen.add(c["text"])
            unique_chunks.append(c)

    return {
        "routing": routing,
        "context": unique_chunks,
        "context_text": "\n\n---\n\n".join([c["text"] for c in unique_chunks]),
    }


if __name__ == "__main__":
    queries = [
        "Should I sell Infosys now?",
        "How will RBI rate hike affect my banking stocks?",
        "Which IT stocks should I buy?",
        "Compare Reliance and TCS performance",
        "What are good stocks to buy this week?",
    ]
    for q in queries:
        result = classify_query(q)
        print(f"Q: {q}")
        print(f"   Type: {result['query_type']}, Intent: {result['intent']}, Tickers: {result['tickers_mentioned']}")
        print()
