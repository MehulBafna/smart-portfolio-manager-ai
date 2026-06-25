"""
Main Streamlit App — Indian Portfolio Manager
Entry point for the dashboard.
"""

from dotenv import load_dotenv
import os
load_dotenv()
os.environ["ANTHROPIC_API_KEY"] = os.getenv("ANTHROPIC_API_KEY", "")

import streamlit as st
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

st.set_page_config(
    page_title="Indian Portfolio Manager — AI Powered",
    page_icon="🇮🇳",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS
st.markdown("""
<style>
    .main-header {font-size: 2rem; font-weight: 700; color: #1a1a2e;}
    .signal-buy {background: #d4edda; color: #155724; padding: 4px 12px; border-radius: 20px; font-weight: 600;}
    .signal-sell {background: #f8d7da; color: #721c24; padding: 4px 12px; border-radius: 20px; font-weight: 600;}
    .signal-hold {background: #fff3cd; color: #856404; padding: 4px 12px; border-radius: 20px; font-weight: 600;}
    .metric-card {background: #f8f9fa; padding: 1rem; border-radius: 10px; border-left: 4px solid #0066cc;}
    .stTabs [data-baseweb="tab"] {font-size: 1rem; font-weight: 500;}
</style>
""", unsafe_allow_html=True)

# Sidebar navigation
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/en/4/41/Flag_of_India.svg", width=60)
    st.title("Portfolio Manager")
    st.caption("AI-Powered Indian Stock Analysis")
    st.divider()

    page = st.radio(
        "Navigate",
        ["📊 Portfolio Overview", "🔍 Stock Analysis", "💬 AI Chat", "🌟 Discover Stocks"],
        label_visibility="collapsed"
    )

    st.divider()
    st.caption("Data Sources")
    st.caption("• NSE via yfinance")
    st.caption("• Screener.in (Fundamentals)")
    st.caption("• MoneyControl RSS (News)")
    st.caption("• RBI (Macro)")
    st.divider()

    if st.button("🔄 Refresh All Data", use_container_width=True):
        with st.spinner("Re-embedding all data... (2-5 mins)"):
            try:
                from src.rag.embedder import run_full_embed
                run_full_embed(refresh=True)
                st.success("✓ Data refreshed!")
            except Exception as e:
                st.error(f"Error: {e}")

# Route to correct page
if page == "📊 Portfolio Overview":
    from dashboard.portfolio_page import render
    render()
elif page == "🔍 Stock Analysis":
    from dashboard.stock_page import render
    render()
elif page == "💬 AI Chat":
    from dashboard.chat_page import render
    render()
elif page == "🌟 Discover Stocks":
    from dashboard.discovery_page import render
    render()
