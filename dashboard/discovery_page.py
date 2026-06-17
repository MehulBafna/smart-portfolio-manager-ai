"""
Discovery Page — AI-powered recommendations for new stocks to watch/buy.
"""

import streamlit as st
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.collectors.macro_collector import get_macro_context, format_macro_for_rag
from src.collectors.price_collector import get_full_analysis
from src.rag.vector_store import get_vector_store
from src.analysis.llm_analyst import get_discovery_picks
from config.settings import DISCOVERY_UNIVERSE


RISK_COLORS = {"Low": "🟢", "Medium": "🟡", "High": "🔴"}


@st.cache_data(ttl=300)
def fetch_macro():
    return get_macro_context()


@st.cache_data(ttl=1800)  # Cache 30 mins — discovery doesn't need to refresh often
def fetch_discovery_picks(market_mood, macro_summary):
    store = get_vector_store()
    context = store.search("Indian stock market opportunities upcoming growth stocks NSE", top_k=8,
                           ticker_filter="MARKET")
    context_text = "\n\n".join([c["text"] for c in context])
    return get_discovery_picks(context_text, market_mood, macro_summary)


def render():
    st.title("🌟 Discover New Stocks")
    st.caption("AI-powered recommendations for NSE stocks worth watching — updated daily.")

    # Market context
    with st.spinner("Loading market conditions..."):
        macro = fetch_macro()

    mood = macro.get("market_mood", "Unknown")
    rbi_rate = macro.get("rbi_policy", {}).get("repo_rate", "N/A")
    mood_emoji = "🟢" if "Bullish" in mood else "🔴" if "Bearish" in mood else "🟡"

    col1, col2, col3 = st.columns(3)
    col1.metric("Market Mood", f"{mood_emoji} {mood}")
    col2.metric("RBI Repo Rate", f"{rbi_rate}%")
    nifty = macro.get("indices", {}).get("NIFTY50", {})
    if "current" in nifty:
        col3.metric("Nifty 50", f"{nifty['current']:,.0f}", f"{nifty['change_pct']:+.2f}%")

    st.divider()

    # Discovery picks
    st.subheader("🤖 AI Stock Picks for This Week")
    st.caption("Based on current market sentiment, macro conditions, and recent news.")

    if st.button("🔄 Generate Fresh Picks", type="primary", use_container_width=True):
        st.cache_data.clear()

    with st.spinner("Scanning NSE universe for opportunities... (30-60s)"):
        macro_summary = format_macro_for_rag(macro)
        picks = fetch_discovery_picks(mood, macro_summary)

    if not picks:
        st.warning("Could not generate picks. Check your Anthropic API key.")
        return

    # Display picks as cards
    for i, pick in enumerate(picks, 1):
        risk_emoji = RISK_COLORS.get(pick.risk_level, "⚪")

        with st.expander(f"#{i} — {pick.company_name} ({pick.ticker.replace('.NS', '')}) | {risk_emoji} {pick.risk_level} Risk", expanded=(i <= 2)):
            col_l, col_r = st.columns([2, 1])

            with col_l:
                st.write(f"**Sector:** {pick.sector}")
                st.write(f"**Why interesting now:** {pick.why_interesting}")
                st.write(f"**Time horizon:** {pick.time_horizon}")

            with col_r:
                st.metric("Entry Range", pick.entry_price_range)
                st.write(f"**Risk:** {risk_emoji} {pick.risk_level}")

            # Fetch live price for context
            try:
                price_data = get_full_analysis(pick.ticker)
                if "error" not in price_data:
                    tech = price_data["technicals"]
                    p1, p2, p3, p4 = st.columns(4)
                    p1.metric("Current Price", f"₹{tech['current_price']:,.0f}", f"{tech['price_change_pct']:+.2f}%")
                    p2.metric("RSI", tech["rsi"], tech["rsi_signal"].split()[0])
                    p3.metric("Trend", tech["trend"])
                    p4.metric("52W High", f"₹{tech['high_52w']:,.0f}")
            except Exception:
                pass

    st.divider()

    # Watchlist from portfolio.json
    st.subheader("👀 Your Watchlist")
    from config.settings import PORTFOLIO_PATH
    import json
    with open(PORTFOLIO_PATH) as f:
        portfolio = json.load(f)

    watchlist = portfolio.get("watchlist", [])
    if watchlist:
        wcols = st.columns(len(watchlist))
        for col, ticker in zip(wcols, watchlist):
            try:
                data = get_full_analysis(ticker)
                if "error" not in data:
                    tech = data["technicals"]
                    col.metric(
                        ticker.replace(".NS", ""),
                        f"₹{tech['current_price']:,.0f}",
                        f"{tech['price_change_pct']:+.2f}%"
                    )
            except Exception:
                col.write(ticker)
    else:
        st.info("Add tickers to 'watchlist' in config/portfolio.json to track them here.")
