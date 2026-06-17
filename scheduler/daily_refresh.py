"""
Daily Refresh Pipeline — Prefect flow that runs every morning at 8 AM IST.
Re-fetches all data and refreshes the vector store.

Run manually:    python scheduler/daily_refresh.py
Schedule:        prefect deployment run daily-refresh/indian-portfolio-refresh
"""

from prefect import flow, task, get_run_logger
from prefect.schedules import CronSchedule
from datetime import datetime
import json
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import PORTFOLIO_PATH
from src.collectors.price_collector import get_full_analysis
from src.collectors.news_collector import fetch_stock_news, fetch_market_news, format_articles_for_rag
from src.collectors.fundamental_collector import scrape_fundamentals, format_fundamentals_for_rag
from src.collectors.macro_collector import get_macro_context, format_macro_for_rag
from src.rag.vector_store import get_vector_store
from src.rag.embedder import embed_stock, embed_macro, load_portfolio


@task(retries=2, retry_delay_seconds=30)
def refresh_macro_data():
    logger = get_run_logger()
    logger.info("Refreshing macro and market data...")
    store = get_vector_store()
    embed_macro(store, refresh=True)
    macro = get_macro_context()
    logger.info(f"Market mood: {macro.get('market_mood')}")
    return macro


@task(retries=2, retry_delay_seconds=30)
def refresh_stock_data(ticker: str, name: str):
    logger = get_run_logger()
    logger.info(f"Refreshing data for {name} ({ticker})")
    store = get_vector_store()
    embed_stock(ticker, name, store, refresh=True)

    # Also fetch and log current technicals
    analysis = get_full_analysis(ticker)
    if "error" not in analysis:
        tech = analysis["technicals"]
        logger.info(
            f"{ticker}: ₹{tech['current_price']} | "
            f"RSI {tech['rsi']} | {tech['trend']}"
        )
    return ticker


@task
def generate_daily_summary(holdings, macro):
    """Generate a brief daily summary log."""
    logger = get_run_logger()
    today = datetime.now().strftime("%Y-%m-%d %H:%M")
    mood = macro.get("market_mood", "Unknown")
    nifty = macro.get("indices", {}).get("NIFTY50", {})
    nifty_val = nifty.get("current", "N/A")
    nifty_chg = nifty.get("change_pct", 0)

    summary = f"""
╔══════════════════════════════════════╗
  Indian Portfolio Manager — Daily Refresh
  {today}
╠══════════════════════════════════════╣
  Market Mood : {mood}
  Nifty 50    : {nifty_val} ({nifty_chg:+.2f}%)
  RBI Rate    : {macro.get('rbi_policy', {}).get('repo_rate', 'N/A')}%
  Stocks Done : {len(holdings)}
╚══════════════════════════════════════╝
    """
    logger.info(summary)
    print(summary)

    # Save summary to file
    os.makedirs("data", exist_ok=True)
    with open("data/last_refresh.txt", "w") as f:
        f.write(summary)

    return summary


@flow(
    name="daily-refresh",
    description="Refresh all Indian stock portfolio data daily at 8 AM IST",
)
def daily_refresh_flow():
    logger = get_run_logger()
    logger.info("Starting daily portfolio data refresh...")

    # Load portfolio
    holdings = load_portfolio()
    logger.info(f"Portfolio has {len(holdings)} stocks")

    # Refresh macro first
    macro = refresh_macro_data()

    # Refresh each stock (sequentially to avoid rate limits)
    for holding in holdings:
        refresh_stock_data(holding["ticker"], holding["name"])

    # Summary
    generate_daily_summary(holdings, macro)
    logger.info("✓ Daily refresh complete!")


if __name__ == "__main__":
    # Run immediately when executed directly
    print("Running daily refresh now...")
    daily_refresh_flow()
