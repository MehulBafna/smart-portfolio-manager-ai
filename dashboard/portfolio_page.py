"""
Portfolio Overview Page — shows all holdings, P&L, signals, market context.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import json
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import PORTFOLIO_PATH
from src.collectors.price_collector import get_full_analysis
from src.collectors.macro_collector import get_macro_context


def get_signal_emoji(signal: str) -> str:
    mapping = {
        "BUY": "🟢", "ACCUMULATE": "🟢",
        "HOLD": "🟡",
        "SELL": "🔴", "REDUCE": "🔴",
    }
    return mapping.get(signal.upper(), "⚪")


@st.cache_data(ttl=900)  # Cache 15 mins
def load_portfolio_data():
    with open(PORTFOLIO_PATH) as f:
        return json.load(f)


@st.cache_data(ttl=300)  # Cache 5 mins
def fetch_all_prices(tickers):
    results = {}
    for ticker in tickers:
        data = get_full_analysis(ticker)
        if "error" not in data:
            results[ticker] = data
    return results


def render():
    st.title("📊 Portfolio Overview")

    # Load portfolio
    portfolio = load_portfolio_data()
    holdings = portfolio["holdings"]

    # Fetch live prices
    with st.spinner("Fetching live NSE prices..."):
        tickers = [h["ticker"] for h in holdings]
        price_data = fetch_all_prices(tuple(tickers))

    # Macro context
    with st.spinner("Loading market context..."):
        macro = get_macro_context()

    # --- Top market indices bar ---
    st.subheader("Market Pulse")
    cols = st.columns(5)
    indices = macro.get("indices", {})
    index_names = ["NIFTY50", "SENSEX", "NIFTY_BANK", "NIFTY_IT", "NIFTY_AUTO"]
    for i, (col, name) in enumerate(zip(cols, index_names)):
        idx = indices.get(name, {})
        if "current" in idx:
            delta = idx["change_pct"]
            col.metric(
                label=name.replace("_", " "),
                value=f"{idx['current']:,.0f}",
                delta=f"{delta:+.2f}%",
                delta_color="normal"
            )

    mood = macro.get("market_mood", "Unknown")
    mood_color = "🟢" if "Bullish" in mood else "🔴" if "Bearish" in mood else "🟡"
    st.info(f"{mood_color} **Market Mood:** {mood} | **RBI Repo Rate:** {macro.get('rbi_policy', {}).get('repo_rate', 'N/A')}%")

    st.divider()

    # --- Portfolio Summary Metrics ---
    total_invested = sum(h["qty"] * h["avg_price"] for h in holdings)
    total_current = 0
    for h in holdings:
        ticker = h["ticker"]
        if ticker in price_data:
            current_price = price_data[ticker]["technicals"]["current_price"]
            total_current += h["qty"] * current_price
        else:
            total_current += h["qty"] * h["avg_price"]

    total_pnl = total_current - total_invested
    total_pnl_pct = (total_pnl / total_invested) * 100

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Invested", f"₹{total_invested:,.0f}")
    m2.metric("Current Value", f"₹{total_current:,.0f}", f"{total_pnl_pct:+.1f}%")
    m3.metric("Total P&L", f"₹{total_pnl:,.0f}", delta_color="normal")
    m4.metric("Holdings", f"{len(holdings)} stocks")

    st.divider()

    # --- Holdings Table ---
    st.subheader("Your Holdings")

    rows = []
    for h in holdings:
        ticker = h["ticker"]
        if ticker in price_data:
            tech = price_data[ticker]["technicals"]
            current_price = tech["current_price"]
            day_change = tech["price_change_pct"]
            rsi = tech["rsi"]
            trend = tech["trend"]
        else:
            current_price = h["avg_price"]
            day_change = 0
            rsi = "-"
            trend = "N/A"

        invested = h["qty"] * h["avg_price"]
        current_val = h["qty"] * current_price
        pnl = current_val - invested
        pnl_pct = ((current_price - h["avg_price"]) / h["avg_price"]) * 100

        rows.append({
            "Stock": h["name"],
            "Ticker": ticker.replace(".NS", ""),
            "Sector": h.get("sector", "N/A"),
            "Qty": h["qty"],
            "Avg Price (₹)": f"₹{h['avg_price']:,.0f}",
            "Current (₹)": f"₹{current_price:,.0f}",
            "Day Change": f"{day_change:+.2f}%",
            "P&L": f"{'🟢' if pnl >= 0 else '🔴'} ₹{pnl:+,.0f} ({pnl_pct:+.1f}%)",
            "RSI": rsi,
            "Trend": trend,
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.divider()

    # --- Charts ---
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("Portfolio Allocation")
        sectors = {}
        for h in holdings:
            sector = h.get("sector", "Other")
            val = h["qty"] * price_data.get(h["ticker"], {}).get("technicals", {}).get("current_price", h["avg_price"])
            sectors[sector] = sectors.get(sector, 0) + val

        fig = px.pie(
            values=list(sectors.values()),
            names=list(sectors.keys()),
            hole=0.4,
            color_discrete_sequence=px.colors.qualitative.Set3,
        )
        fig.update_layout(margin=dict(t=0, b=0, l=0, r=0), height=300)
        st.plotly_chart(fig, use_container_width=True)

    with col_right:
        st.subheader("P&L by Stock")
        pnl_data = []
        for h in holdings:
            ticker = h["ticker"]
            cp = price_data.get(ticker, {}).get("technicals", {}).get("current_price", h["avg_price"])
            pnl_pct = ((cp - h["avg_price"]) / h["avg_price"]) * 100
            pnl_data.append({"Stock": h["name"].split()[0], "P&L %": round(pnl_pct, 2)})

        pnl_df = pd.DataFrame(pnl_data).sort_values("P&L %")
        fig2 = px.bar(
            pnl_df, x="P&L %", y="Stock", orientation="h",
            color="P&L %", color_continuous_scale=["#dc3545", "#ffc107", "#28a745"],
            color_continuous_midpoint=0
        )
        fig2.update_layout(margin=dict(t=0, b=0), height=300, coloraxis_showscale=False)
        st.plotly_chart(fig2, use_container_width=True)
