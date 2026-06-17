"""
LLM Analyst — sends context + technicals to Claude and gets
structured analysis back as a Pydantic model.
"""

import anthropic
import json
from pydantic import BaseModel
from typing import Optional, List
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from config.settings import ANTHROPIC_API_KEY, LLM_MODEL, LLM_MAX_TOKENS


client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


class StockSignal(BaseModel):
    ticker: str
    company_name: str
    signal: str                    # BUY / HOLD / SELL / ACCUMULATE / REDUCE
    signal_strength: str           # Strong / Moderate / Weak
    current_price: float
    target_price: Optional[float]
    time_horizon: str              # e.g. "3-6 months", "1 year"
    risk_level: str                # Low / Medium / High
    upside_potential_pct: Optional[float]
    technical_summary: str
    fundamental_summary: str
    news_sentiment: str            # Positive / Neutral / Negative
    key_reasons: List[str]         # Top 3 bullet points
    risks: List[str]               # Top 2 risks
    plain_english: str             # 3-sentence explanation for non-experts
    good_time_to_buy: str          # When to accumulate
    when_to_exit: str              # Exit conditions


class DiscoveryStock(BaseModel):
    ticker: str
    company_name: str
    sector: str
    why_interesting: str
    entry_price_range: str
    risk_level: str
    time_horizon: str


class ChatResponse(BaseModel):
    answer: str
    actionable_advice: Optional[str]
    relevant_tickers: List[str]
    confidence: str                # High / Medium / Low


SYSTEM_PROMPT = """You are an expert Indian stock market analyst with deep knowledge of NSE-listed stocks, 
Indian macroeconomics, RBI policy, FII/DII flows, and technical analysis. 

Your analysis is:
- Data-driven and based on provided context
- Specific to Indian market conditions
- Actionable with clear signals
- In INR (₹) for all price targets
- Honest about uncertainty and risks

Always respond in valid JSON matching the exact schema requested. No preamble, no markdown, just JSON."""


def analyze_stock(
    ticker: str,
    company_name: str,
    technicals: dict,
    fundamentals: dict,
    context_text: str,
    holding: dict = None,
) -> StockSignal:
    """Get structured buy/hold/sell analysis for a single stock."""

    holding_info = ""
    if holding:
        pnl = ((technicals.get("current_price", 0) - holding["avg_price"]) / holding["avg_price"]) * 100
        holding_info = f"""
HOLDING INFO:
- Quantity: {holding['qty']} shares
- Average Buy Price: ₹{holding['avg_price']}
- Current P&L: {'+' if pnl >= 0 else ''}{pnl:.1f}%
"""

    prompt = f"""Analyze this Indian stock and provide a structured recommendation.

STOCK: {company_name} ({ticker})
{holding_info}

TECHNICAL INDICATORS:
- Current Price: ₹{technicals.get('current_price', 'N/A')}
- RSI ({technicals.get('rsi', 'N/A')}): {technicals.get('rsi_signal', 'N/A')}
- MACD: {technicals.get('macd_interpretation', 'N/A')}
- Trend: {technicals.get('trend', 'N/A')}
- 52W High: ₹{technicals.get('high_52w', 'N/A')} | 52W Low: ₹{technicals.get('low_52w', 'N/A')}
- Bollinger Bands: {technicals.get('price_vs_bb', 'N/A')}
- Volume Surge: {technicals.get('volume_surge', 'N/A')}x avg

FUNDAMENTALS:
- P/E Ratio: {fundamentals.get('pe_ratio', 'N/A')}
- ROE: {fundamentals.get('roe', 'N/A')}
- ROCE: {fundamentals.get('roce', 'N/A')}
- Promoter Holding: {fundamentals.get('promoter_holding', 'N/A')}
- Pros: {'; '.join(fundamentals.get('pros', [])[:3])}
- Cons: {'; '.join(fundamentals.get('cons', [])[:2])}

RECENT NEWS & CONTEXT:
{context_text[:2000]}

Return a JSON object with EXACTLY these fields:
{{
  "ticker": "{ticker}",
  "company_name": "{company_name}",
  "signal": "BUY|HOLD|SELL|ACCUMULATE|REDUCE",
  "signal_strength": "Strong|Moderate|Weak",
  "current_price": <float>,
  "target_price": <float or null>,
  "time_horizon": "<string e.g. '3-6 months'>",
  "risk_level": "Low|Medium|High",
  "upside_potential_pct": <float or null>,
  "technical_summary": "<1 sentence>",
  "fundamental_summary": "<1 sentence>",
  "news_sentiment": "Positive|Neutral|Negative",
  "key_reasons": ["<reason 1>", "<reason 2>", "<reason 3>"],
  "risks": ["<risk 1>", "<risk 2>"],
  "plain_english": "<3 sentences, simple language, no jargon>",
  "good_time_to_buy": "<when to accumulate/add more>",
  "when_to_exit": "<exit conditions/target>"
}}"""

    try:
        response = client.messages.create(
            model=LLM_MODEL,
            max_tokens=LLM_MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = response.content[0].text.strip()
        # Clean any accidental markdown
        raw = raw.replace("```json", "").replace("```", "").strip()
        data = json.loads(raw)
        return StockSignal(**data)
    except Exception as e:
        print(f"[ERROR] LLM analysis for {ticker}: {e}")
        # Return a safe fallback
        return StockSignal(
            ticker=ticker,
            company_name=company_name,
            signal="HOLD",
            signal_strength="Weak",
            current_price=technicals.get("current_price", 0),
            target_price=None,
            time_horizon="Unknown",
            risk_level="Medium",
            upside_potential_pct=None,
            technical_summary="Analysis unavailable",
            fundamental_summary="Analysis unavailable",
            news_sentiment="Neutral",
            key_reasons=["LLM analysis failed — check API key"],
            risks=["Unable to assess"],
            plain_english="Analysis could not be generated. Please check your Anthropic API key.",
            good_time_to_buy="Unavailable",
            when_to_exit="Unavailable",
        )


def answer_chat_question(
    question: str,
    context_text: str,
    portfolio_summary: str,
    routing_info: dict,
) -> ChatResponse:
    """Answer a free-form chat question about the portfolio."""

    prompt = f"""Answer this question about an Indian stock portfolio.

QUESTION: {question}

PORTFOLIO SUMMARY:
{portfolio_summary}

RETRIEVED CONTEXT:
{context_text[:3000]}

ROUTING INFO: {routing_info}

Return JSON with EXACTLY:
{{
  "answer": "<detailed answer, use ₹ for prices, be specific>",
  "actionable_advice": "<1-2 specific actions the investor should consider, or null>",
  "relevant_tickers": ["<tickers mentioned>"],
  "confidence": "High|Medium|Low"
}}"""

    try:
        response = client.messages.create(
            model=LLM_MODEL,
            max_tokens=LLM_MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = response.content[0].text.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        data = json.loads(raw)
        return ChatResponse(**data)
    except Exception as e:
        print(f"[ERROR] Chat LLM: {e}")
        return ChatResponse(
            answer=f"I couldn't generate an answer. Error: {str(e)}",
            actionable_advice=None,
            relevant_tickers=[],
            confidence="Low",
        )


def get_discovery_picks(
    context_text: str,
    market_mood: str,
    macro_summary: str,
) -> List[DiscoveryStock]:
    """Get top stock discovery recommendations from the universe."""

    prompt = f"""Based on current Indian market conditions, recommend 5 NSE stocks worth watching.

MARKET MOOD: {market_mood}
MACRO CONTEXT: {macro_summary}

MARKET NEWS & CONTEXT:
{context_text[:2000]}

Return a JSON array of exactly 5 stocks:
[
  {{
    "ticker": "<NSE ticker with .NS suffix>",
    "company_name": "<full company name>",
    "sector": "<sector>",
    "why_interesting": "<2 sentences on why this stock now>",
    "entry_price_range": "<e.g. ₹450-480>",
    "risk_level": "Low|Medium|High",
    "time_horizon": "<investment horizon>"
  }}
]

Focus on fundamentally sound Indian companies with near-term catalysts.
Avoid penny stocks. Mix of large-cap and mid-cap."""

    try:
        response = client.messages.create(
            model=LLM_MODEL,
            max_tokens=LLM_MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = response.content[0].text.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        data = json.loads(raw)
        return [DiscoveryStock(**item) for item in data]
    except Exception as e:
        print(f"[ERROR] Discovery LLM: {e}")
        return []


if __name__ == "__main__":
    # Quick test with mock data
    mock_technicals = {
        "current_price": 2650.0,
        "rsi": 58,
        "rsi_signal": "Neutral",
        "macd_interpretation": "Bullish crossover",
        "trend": "Uptrend",
        "high_52w": 3200.0,
        "low_52w": 2100.0,
        "price_vs_bb": "Within bands (normal)",
        "volume_surge": 1.3,
    }
    mock_fundamentals = {
        "pe_ratio": "24.5",
        "roe": "18%",
        "roce": "22%",
        "promoter_holding": "50.3%",
        "pros": ["Strong cash flow", "Diversified revenue"],
        "cons": ["High debt in telecom segment"],
    }
    result = analyze_stock(
        "RELIANCE.NS", "Reliance Industries",
        mock_technicals, mock_fundamentals,
        "Reliance reported strong Q3 with Jio subscriber growth.",
        {"qty": 10, "avg_price": 2500}
    )
    print(f"Signal: {result.signal} ({result.signal_strength})")
    print(f"Target: ₹{result.target_price} in {result.time_horizon}")
    print(f"Plain English: {result.plain_english}")
