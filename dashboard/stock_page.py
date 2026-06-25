"""
stock_page.py — Stock deep dive with management insights integrated into AI signal.

Flow:
  1. Fetch price + technicals
  2. Fetch fundamentals
  3. On "Generate AI Signal":
     - Fetch management insights automatically (with source link)
     - Pass to LLM for richer recommendation
     - Display signal + brief management summary below
"""

import streamlit as st
import plotly.graph_objects as go
import json
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import PORTFOLIO_PATH
from src.collectors.price_collector import get_full_analysis
from src.collectors.fundamental_collector import scrape_fundamentals
from src.collectors.management_collector import fetch_management_insights
from src.rag.router import route_and_retrieve
from src.analysis.llm_analyst import analyze_stock


@st.cache_data(ttl=900)
def load_portfolio():
    with open(PORTFOLIO_PATH) as f:
        return json.load(f)


@st.cache_data(ttl=300)
def cached_price_analysis(ticker):
    return get_full_analysis(ticker)


@st.cache_data(ttl=3600)
def cached_fundamentals(ticker):
    return scrape_fundamentals(ticker)


@st.cache_data(ttl=600)
def cached_rag_context(ticker, company_name):
    return route_and_retrieve(
        f"Should I hold or sell {company_name}? What is the outlook?",
        portfolio_tickers=[ticker]
    )


@st.cache_data(ttl=86400)  # Cache 24h — IR data doesn't change daily
def cached_management_insights(ticker, company_name):
    return fetch_management_insights(ticker, company_name)


def _format_mgmt_for_llm(insights: dict) -> str:
    """Convert management insights to a text block for LLM context."""
    if not insights or insights.get("data_quality") == "limited":
        return ""
    lines = [f"MANAGEMENT INSIGHTS (Source: {insights.get('source_url', 'N/A')})"]
    if insights.get("ceo_commentary") not in [None, "Not available", ""]:
        lines.append(f"CEO Commentary: {insights['ceo_commentary']}")
    if insights.get("annual_highlights"):
        lines.append("Annual Highlights: " + " | ".join(insights["annual_highlights"]))
    if insights.get("strategic_outlook"):
        lines.append("Strategic Outlook: " + " | ".join(insights["strategic_outlook"]))
    if insights.get("quarterly_commentary") not in [None, "Not available", ""]:
        lines.append(f"Latest Quarter: {insights['quarterly_commentary']}")
    if insights.get("key_risks"):
        lines.append("Mgmt-flagged Risks: " + " | ".join(insights["key_risks"]))
    return "\n".join(lines)


def render():
    st.title("🔍 Stock Deep Dive")

    portfolio = load_portfolio()
    holdings = portfolio["holdings"]

    options = {f"{h['name']} ({h['ticker'].replace('.NS', '')})": h for h in holdings}
    selected = st.selectbox("Select a stock from your portfolio", list(options.keys()))
    holding = options[selected]
    ticker = holding["ticker"]
    name = holding["name"]

    with st.spinner(f"Loading data for {name}..."):
        analysis = cached_price_analysis(ticker)
        fundamentals = cached_fundamentals(ticker)

    if "error" in analysis:
        st.error(f"Could not load data: {analysis['error']}")
        return

    tech = analysis["technicals"]
    df = analysis["price_history"]
    current_price = tech["current_price"]

    pnl_pct = ((current_price - holding["avg_price"]) / holding["avg_price"]) * 100
    pnl_abs = (current_price - holding["avg_price"]) * holding["qty"]

    # ── Header metrics ──
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Current Price", f"₹{current_price:,.2f}", f"{tech['price_change_pct']:+.2f}% today")
    c2.metric("Your Avg Buy",  f"₹{holding['avg_price']:,.0f}")
    c3.metric("Your P&L",      f"₹{pnl_abs:+,.0f}", f"{pnl_pct:+.1f}%")
    c4.metric("52W High",      f"₹{tech['high_52w']:,.0f}")
    c5.metric("52W Low",       f"₹{tech['low_52w']:,.0f}")

    st.divider()

    # ── AI Signal ──
    st.subheader("🤖 AI Recommendation")
    st.caption("Powered by technical analysis, fundamentals, news sentiment + management insights")

    if st.button(f"Generate AI Signal for {name}", type="primary", use_container_width=True):
        with st.spinner("Step 1/3 — Fetching management insights from official IR page..."):
            insights = cached_management_insights(ticker, name)
            st.session_state[f"mgmt_{ticker}"] = insights

        with st.spinner("Step 2/3 — Retrieving news and macro context..."):
            rag_result = cached_rag_context(ticker, name)

        with st.spinner("Step 3/3 — Generating AI signal..."):
            # Build enriched context = RAG context + management insights
            mgmt_text = _format_mgmt_for_llm(insights)
            enriched_context = rag_result["context_text"]
            if mgmt_text:
                enriched_context = mgmt_text + "\n\n" + enriched_context

            signal = analyze_stock(
                ticker, name, tech, fundamentals,
                enriched_context, holding
            )
            st.session_state[f"signal_{ticker}"] = signal

    if f"signal_{ticker}" in st.session_state:
        sig = st.session_state[f"signal_{ticker}"]
        signal_colors = {
            "BUY": "🟢", "ACCUMULATE": "🟢",
            "HOLD": "🟡",
            "SELL": "🔴", "REDUCE": "🔴"
        }
        emoji = signal_colors.get(sig.signal, "⚪")

        # Signal cards
        col_sig, col_target, col_horizon, col_risk = st.columns(4)
        col_sig.metric("Signal",      f"{emoji} {sig.signal}", sig.signal_strength)
        col_target.metric("Target",   f"₹{sig.target_price:,.0f}" if sig.target_price else "N/A",
                          f"{sig.upside_potential_pct:+.1f}%" if sig.upside_potential_pct else "")
        col_horizon.metric("Horizon", sig.time_horizon)
        col_risk.metric("Risk",       sig.risk_level)

        st.info(f"📝 **Plain English:** {sig.plain_english}")

        col_l, col_r = st.columns(2)
        with col_l:
            st.success(f"✅ **When to accumulate:** {sig.good_time_to_buy}")
            st.write("**Key Reasons:**")
            for r in sig.key_reasons:
                st.write(f"• {r}")
        with col_r:
            st.warning(f"🚪 **When to exit:** {sig.when_to_exit}")
            st.write("**Key Risks:**")
            for r in sig.risks:
                st.write(f"• {r}")

        st.caption(
            f"Technical: {sig.technical_summary} | "
            f"Fundamental: {sig.fundamental_summary} | "
            f"News: {sig.news_sentiment} sentiment"
        )

        # ── Management Insights Brief (below signal) ──────────────────
        insights = st.session_state.get(f"mgmt_{ticker}")
        if insights:
            st.divider()
            quality = insights.get("data_quality", "limited")
            quality_icon = {"good": "🟢", "partial": "🟡", "limited": "🔴"}.get(quality, "⚪")
            source_url = insights.get("source_url", "")

            st.markdown(f"**🏢 Management Insights** {quality_icon} "
                        f"{'— [View Source](' + source_url + ')' if source_url and source_url != 'Not found' else ''}")

            col_m1, col_m2 = st.columns(2)

            with col_m1:
                if insights.get("ceo_commentary") not in [None, "Not available", ""]:
                    st.markdown("**💬 Management Commentary**")
                    st.info(insights["ceo_commentary"])

                if insights.get("annual_highlights"):
                    st.markdown("**📊 Key Highlights**")
                    for h in insights["annual_highlights"][:3]:
                        st.write(f"• {h}")

            with col_m2:
                if insights.get("strategic_outlook"):
                    st.markdown("**🎯 Strategic Outlook**")
                    for o in insights["strategic_outlook"][:3]:
                        st.write(f"• {o}")

                if insights.get("quarterly_commentary") not in [None, "Not available", ""]:
                    st.markdown("**📅 Latest Quarter**")
                    st.write(insights["quarterly_commentary"])

            if insights.get("key_risks"):
                st.markdown("**⚠️ Management-flagged Risks**")
                st.write(" | ".join(f"• {r}" for r in insights["key_risks"][:2]))

    st.divider()

    # ── Price Chart ──
    st.subheader("📈 Price Chart")
    chart_period = st.radio("Period", ["1mo", "3mo", "6mo", "1y"], horizontal=True, index=2)
    df_plot = df.tail({"1mo": 22, "3mo": 66, "6mo": 132, "1y": 252}.get(chart_period, 132))

    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=df_plot.index,
        open=df_plot["Open"], high=df_plot["High"],
        low=df_plot["Low"],  close=df_plot["Close"],
        name="Price",
        increasing_line_color="#26a69a",
        decreasing_line_color="#ef5350"
    ))
    sma20 = df_plot["Close"].rolling(20).mean()
    sma50 = df_plot["Close"].rolling(50).mean()
    fig.add_trace(go.Scatter(x=df_plot.index, y=sma20, name="SMA 20",
                             line=dict(color="#ff9800", width=1.5)))
    fig.add_trace(go.Scatter(x=df_plot.index, y=sma50, name="SMA 50",
                             line=dict(color="#2196f3", width=1.5)))
    fig.add_hline(y=holding["avg_price"], line_dash="dash", line_color="purple",
                  annotation_text=f"Your buy: ₹{holding['avg_price']}")
    fig.update_layout(height=400, xaxis_rangeslider_visible=False,
                      margin=dict(t=20, b=20), legend=dict(orientation="h"),
                      plot_bgcolor="white", paper_bgcolor="white")
    fig.update_xaxes(gridcolor="#f0f0f0")
    fig.update_yaxes(gridcolor="#f0f0f0", tickprefix="₹")
    st.plotly_chart(fig, use_container_width=True)

    # ── RSI ──
    st.subheader("RSI")
    from ta.momentum import RSIIndicator
    rsi_series = RSIIndicator(close=df_plot["Close"], window=14).rsi()
    fig_rsi = go.Figure()
    fig_rsi.add_trace(go.Scatter(x=df_plot.index, y=rsi_series, name="RSI",
                                  line=dict(color="#9c27b0", width=2)))
    fig_rsi.add_hline(y=70, line_dash="dash", line_color="red",   annotation_text="Overbought (70)")
    fig_rsi.add_hline(y=30, line_dash="dash", line_color="green", annotation_text="Oversold (30)")
    fig_rsi.add_hrect(y0=30, y1=70, fillcolor="lightyellow", opacity=0.3)
    fig_rsi.update_layout(height=200, margin=dict(t=10, b=10),
                           plot_bgcolor="white", paper_bgcolor="white")
    fig_rsi.update_yaxes(range=[0, 100])
    st.plotly_chart(fig_rsi, use_container_width=True)

    st.divider()

    # ── Fundamentals ──
    st.subheader("💰 Fundamentals (Screener.in)")
    if "error" not in fundamentals:
        f1, f2, f3, f4, f5, f6 = st.columns(6)
        f1.metric("P/E Ratio",     fundamentals.get("pe_ratio",        "N/A"))
        f2.metric("ROE",           fundamentals.get("roe",             "N/A"))
        f3.metric("ROCE",          fundamentals.get("roce",            "N/A"))
        f4.metric("Book Value",    fundamentals.get("book_value",      "N/A"))
        f5.metric("Div Yield",     fundamentals.get("dividend_yield",  "N/A"))
        f6.metric("Promoter Hold", fundamentals.get("promoter_holding","N/A"))

        col_pros, col_cons = st.columns(2)
        with col_pros:
            st.success("**Strengths**")
            for p in fundamentals.get("pros", []):
                st.write(f"✅ {p}")
        with col_cons:
            st.error("**Concerns**")
            for c in fundamentals.get("cons", []):
                st.write(f"⚠️ {c}")

        if fundamentals.get("screener_url"):
            st.caption(f"[View full profile on Screener.in]({fundamentals['screener_url']})")
    else:
        st.warning(f"Fundamentals unavailable: {fundamentals.get('error')}")