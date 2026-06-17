"""
Tests for data collectors.
Run: pytest tests/test_collectors.py -v
"""

import pytest
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestPriceCollector:
    def test_fetch_price_data_valid_ticker(self):
        from src.collectors.price_collector import fetch_price_data
        df = fetch_price_data("RELIANCE.NS", period="1mo")
        assert df is not None
        assert not df.empty
        assert "Close" in df.columns
        assert "Volume" in df.columns

    def test_fetch_price_data_invalid_ticker(self):
        from src.collectors.price_collector import fetch_price_data
        df = fetch_price_data("FAKEXYZ123.NS")
        assert df is None

    def test_compute_technicals(self):
        from src.collectors.price_collector import fetch_price_data, compute_technicals
        df = fetch_price_data("TCS.NS", period="3mo")
        assert df is not None
        tech = compute_technicals(df)

        assert "current_price" in tech
        assert "rsi" in tech
        assert "macd" in tech
        assert "trend" in tech
        assert 0 <= tech["rsi"] <= 100
        assert tech["current_price"] > 0

    def test_get_stock_info(self):
        from src.collectors.price_collector import get_stock_info
        info = get_stock_info("INFY.NS")
        assert isinstance(info, dict)
        # Should have at least some fields
        assert "sector" in info or "name" in info

    def test_get_full_analysis(self):
        from src.collectors.price_collector import get_full_analysis
        result = get_full_analysis("HDFCBANK.NS")
        assert "error" not in result
        assert "technicals" in result
        assert "price_history" in result


class TestFundamentalCollector:
    def test_nse_to_screener_conversion(self):
        from src.collectors.fundamental_collector import _nse_to_screener
        assert _nse_to_screener("RELIANCE.NS") == "RELIANCE"
        assert _nse_to_screener("TATAMOTORS.BO") == "TATAMOTORS"
        assert _nse_to_screener("INFY.NS") == "INFY"

    def test_scrape_fundamentals_structure(self):
        from src.collectors.fundamental_collector import scrape_fundamentals
        data = scrape_fundamentals("RELIANCE.NS")
        assert isinstance(data, dict)
        assert "ticker" in data
        # Either has data or a clean error
        assert "pe_ratio" in data or "error" in data

    def test_format_fundamentals_for_rag(self):
        from src.collectors.fundamental_collector import format_fundamentals_for_rag
        mock_fundamentals = {
            "ticker": "RELIANCE.NS",
            "pe_ratio": "24.5",
            "roe": "18%",
            "roce": "22%",
            "promoter_holding": "50.3%",
            "book_value": "₹1,200",
            "dividend_yield": "0.4%",
            "market_cap": "₹18L Cr",
            "pros": ["Strong cash flow", "Diversified revenue"],
            "cons": ["High debt in telecom"],
        }
        text = format_fundamentals_for_rag(mock_fundamentals)
        assert "RELIANCE.NS" in text
        assert "P/E" in text
        assert "Strong cash flow" in text


class TestNewsCollector:
    def test_moneycontrol_rss(self):
        from src.collectors.news_collector import fetch_moneycontrol_rss
        articles = fetch_moneycontrol_rss()
        # Should return a list (may be empty if RSS is down)
        assert isinstance(articles, list)

    def test_format_articles_for_rag(self):
        from src.collectors.news_collector import format_articles_for_rag
        mock_articles = [
            {
                "title": "Reliance Q3 results beat estimates",
                "description": "Strong performance in Jio and retail segments",
                "published_at": "2025-01-15",
                "source": "MoneyControl",
            }
        ]
        chunks = format_articles_for_rag(mock_articles, "RELIANCE.NS")
        assert len(chunks) == 1
        assert "Reliance Q3 results" in chunks[0]
        assert "RELIANCE.NS" in chunks[0]


class TestMacroCollector:
    def test_fetch_index_data(self):
        from src.collectors.macro_collector import fetch_index_data
        indices = fetch_index_data()
        assert isinstance(indices, dict)
        assert "NIFTY50" in indices

    def test_get_macro_context_structure(self):
        from src.collectors.macro_collector import get_macro_context
        macro = get_macro_context()
        assert "indices" in macro
        assert "market_mood" in macro
        assert "rbi_policy" in macro
        assert "timestamp" in macro

    def test_format_macro_for_rag(self):
        from src.collectors.macro_collector import format_macro_for_rag
        mock_macro = {
            "indices": {
                "NIFTY50": {"current": 22500, "change_pct": 0.5},
                "SENSEX": {"current": 74000, "change_pct": 0.4},
            },
            "rbi_policy": {"repo_rate": 6.5},
            "fii_dii": {"fii_net": "₹1,200 Cr", "dii_net": "₹800 Cr"},
            "market_mood": "Mildly Bullish",
        }
        text = format_macro_for_rag(mock_macro)
        assert "Nifty" in text
        assert "6.5" in text
        assert "Mildly Bullish" in text
