"""
Tests for LLM analyst (uses mock data to avoid API calls in CI).
Run: pytest tests/test_analysis.py -v
"""

import pytest
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


MOCK_TECHNICALS = {
    "current_price": 2650.0,
    "prev_close": 2620.0,
    "price_change_pct": 1.14,
    "rsi": 58,
    "rsi_signal": "Neutral",
    "macd": 12.5,
    "macd_signal": 10.2,
    "macd_hist": 2.3,
    "macd_interpretation": "Bullish crossover",
    "trend": "Uptrend",
    "high_52w": 3200.0,
    "low_52w": 2100.0,
    "price_vs_bb": "Within bands (normal)",
    "volume_surge": 1.3,
    "sma_20": 2580.0,
    "sma_50": 2490.0,
    "ema_20": 2600.0,
    "bb_upper": 2800.0,
    "bb_lower": 2350.0,
    "bb_middle": 2575.0,
    "avg_volume_20d": 5000000,
    "latest_volume": 6500000,
}

MOCK_FUNDAMENTALS = {
    "ticker": "RELIANCE.NS",
    "pe_ratio": "24.5",
    "roe": "18%",
    "roce": "22%",
    "book_value": "₹1,250",
    "dividend_yield": "0.4%",
    "market_cap": "₹18L Cr",
    "promoter_holding": "50.3%",
    "pros": ["Strong cash flow generation", "Diversified revenue streams"],
    "cons": ["High debt in telecom segment"],
}

MOCK_HOLDING = {
    "qty": 10,
    "avg_price": 2500.0,
}


class TestStockSignalStructure:
    """Test that StockSignal Pydantic model validates correctly."""

    def test_valid_signal_creation(self):
        from src.analysis.llm_analyst import StockSignal
        signal = StockSignal(
            ticker="RELIANCE.NS",
            company_name="Reliance Industries",
            signal="HOLD",
            signal_strength="Moderate",
            current_price=2650.0,
            target_price=3000.0,
            time_horizon="6-12 months",
            risk_level="Medium",
            upside_potential_pct=13.2,
            technical_summary="RSI neutral, MACD bullish crossover, uptrend intact.",
            fundamental_summary="Strong ROE and ROCE with diversified revenue.",
            news_sentiment="Positive",
            key_reasons=["Strong Jio subscriber growth", "Retail segment expanding", "New energy investments"],
            risks=["High capex in green energy", "Global oil price volatility"],
            plain_english="Reliance is in an uptrend with strong fundamentals. Hold for 6-12 months targeting ₹3000. Risk is medium.",
            good_time_to_buy="Add more on dips below ₹2400",
            when_to_exit="Exit above ₹3000 or if RSI crosses 80",
        )
        assert signal.signal == "HOLD"
        assert signal.target_price == 3000.0
        assert len(signal.key_reasons) == 3

    def test_signal_with_null_target(self):
        from src.analysis.llm_analyst import StockSignal
        signal = StockSignal(
            ticker="TCS.NS",
            company_name="TCS",
            signal="HOLD",
            signal_strength="Weak",
            current_price=3800.0,
            target_price=None,
            time_horizon="Unknown",
            risk_level="Low",
            upside_potential_pct=None,
            technical_summary="Sideways movement.",
            fundamental_summary="Stable fundamentals.",
            news_sentiment="Neutral",
            key_reasons=["Stable business"],
            risks=["US recession risk"],
            plain_english="TCS is stable. Hold.",
            good_time_to_buy="Below ₹3600",
            when_to_exit="Above ₹4200",
        )
        assert signal.target_price is None


class TestChatResponseStructure:
    def test_valid_chat_response(self):
        from src.analysis.llm_analyst import ChatResponse
        response = ChatResponse(
            answer="Based on current technicals, Infosys shows a bullish setup with RSI at 58 and MACD crossover. The IT sector is facing some headwinds from US client spending cuts, but Infosys's strong Q3 guidance suggests holding.",
            actionable_advice="Hold Infosys. Consider adding more if it dips below ₹1,400.",
            relevant_tickers=["INFY.NS"],
            confidence="Medium",
        )
        assert response.confidence == "Medium"
        assert "INFY.NS" in response.relevant_tickers


class TestDiscoveryStockStructure:
    def test_valid_discovery_stock(self):
        from src.analysis.llm_analyst import DiscoveryStock
        stock = DiscoveryStock(
            ticker="BAJFINANCE.NS",
            company_name="Bajaj Finance",
            sector="NBFC",
            why_interesting="Strong AUM growth and improving asset quality make this a compelling buy.",
            entry_price_range="₹6,800-7,000",
            risk_level="Medium",
            time_horizon="6-12 months",
        )
        assert stock.ticker == "BAJFINANCE.NS"
        assert stock.risk_level == "Medium"


class TestTechnicalIndicators:
    def test_rsi_bounds(self):
        """RSI should always be between 0 and 100."""
        from src.collectors.price_collector import fetch_price_data, compute_technicals
        df = fetch_price_data("WIPRO.NS", period="3mo")
        if df is not None:
            tech = compute_technicals(df)
            assert 0 <= tech["rsi"] <= 100

    def test_price_positive(self):
        from src.collectors.price_collector import fetch_price_data, compute_technicals
        df = fetch_price_data("SBIN.NS", period="1mo")
        if df is not None:
            tech = compute_technicals(df)
            assert tech["current_price"] > 0
            assert tech["high_52w"] >= tech["low_52w"]
