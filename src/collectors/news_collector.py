"""
News Collector — fetches Indian stock market news from:
1. NewsAPI (requires free API key)
2. MoneyControl RSS feeds (no key needed)
"""

import feedparser
import requests
from datetime import datetime, timedelta
from typing import List, Dict
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import NEWS_API_KEY, MONEYCONTROL_RSS_FEEDS, NEWS_KEYWORDS


def fetch_newsapi(query: str, days_back: int = 7) -> List[Dict]:
    """Fetch news articles from NewsAPI for a given query."""
    if not NEWS_API_KEY:
        print("[WARN] NEWS_API_KEY not set, skipping NewsAPI")
        return []

    from_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    url = "https://newsapi.org/v2/everything"
    params = {
        "q": query,
        "from": from_date,
        "sortBy": "publishedAt",
        "language": "en",
        "apiKey": NEWS_API_KEY,
        "pageSize": 10,
    }

    try:
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()
        articles = []
        for art in data.get("articles", []):
            articles.append({
                "title": art.get("title", ""),
                "description": art.get("description", ""),
                "content": art.get("content", ""),
                "url": art.get("url", ""),
                "published_at": art.get("publishedAt", ""),
                "source": art.get("source", {}).get("name", "NewsAPI"),
            })
        return articles
    except Exception as e:
        print(f"[ERROR] NewsAPI fetch error: {e}")
        return []


def fetch_moneycontrol_rss() -> List[Dict]:
    """Fetch latest news from MoneyControl RSS feeds."""
    articles = []
    for feed_url in MONEYCONTROL_RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:15]:
                articles.append({
                    "title": entry.get("title", ""),
                    "description": entry.get("summary", ""),
                    "content": entry.get("summary", ""),
                    "url": entry.get("link", ""),
                    "published_at": entry.get("published", ""),
                    "source": "MoneyControl",
                })
        except Exception as e:
            print(f"[ERROR] RSS fetch error ({feed_url}): {e}")
    return articles


def fetch_stock_news(ticker: str, company_name: str = "") -> List[Dict]:
    """
    Fetch news specifically about a stock.
    Combines NewsAPI + MoneyControl RSS filtered by company name.
    """
    slug = ticker.replace(".NS", "").replace(".BO", "")
    query = company_name if company_name else slug

    # NewsAPI — company-specific
    newsapi_articles = fetch_newsapi(f"{query} stock India NSE")

    # MoneyControl RSS — filter by company name
    rss_articles = fetch_moneycontrol_rss()
    filtered_rss = [
        a for a in rss_articles
        if slug.lower() in a["title"].lower()
        or (company_name and company_name.lower() in a["title"].lower())
    ]

    all_articles = newsapi_articles + filtered_rss

    # Deduplicate by title
    seen_titles = set()
    unique_articles = []
    for a in all_articles:
        if a["title"] not in seen_titles:
            seen_titles.add(a["title"])
            unique_articles.append(a)

    return unique_articles[:20]


def fetch_market_news() -> List[Dict]:
    """Fetch general Indian market news (Nifty, Sensex, RBI, SEBI)."""
    rss_articles = fetch_moneycontrol_rss()
    newsapi_articles = fetch_newsapi("Nifty Sensex RBI India stock market")
    all_articles = rss_articles + newsapi_articles

    seen = set()
    unique = []
    for a in all_articles:
        if a["title"] not in seen:
            seen.add(a["title"])
            unique.append(a)
    return unique[:30]


def format_articles_for_rag(articles: List[Dict], ticker: str = "") -> List[str]:
    """
    Convert article list into text chunks for embedding.
    Each article becomes one chunk.
    """
    chunks = []
    for art in articles:
        text = f"News: {art['title']}\n"
        if art.get("description"):
            text += f"Summary: {art['description']}\n"
        if art.get("published_at"):
            text += f"Date: {art['published_at']}\n"
        text += f"Source: {art['source']}"
        if ticker:
            text = f"[{ticker}] " + text
        chunks.append(text)
    return chunks


if __name__ == "__main__":
    articles = fetch_stock_news("RELIANCE.NS", "Reliance Industries")
    print(f"Found {len(articles)} articles for Reliance")
    for a in articles[:3]:
        print(f"  - {a['title']} ({a['source']})")

    market_news = fetch_market_news()
    print(f"\nFound {len(market_news)} general market news articles")
