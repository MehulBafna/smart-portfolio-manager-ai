# 🇮🇳 Smart Portfolio Manager AI

An end-to-end AI portfolio management system for Indian stock markets (NSE/BSE) using RAG, multi-source data, and LLM reasoning.

## Features
- 📊 **Dashboard** — Visual portfolio overview with P&L, signals, charts
- 🤖 **AI Chat** — Ask anything: *"When should I sell Infosys?"*
- 📰 **News Sentiment** — Real-time analysis of Indian financial news
- 📈 **Technical Analysis** — RSI, MACD, Moving Averages
- 💰 **Fundamentals** — P/E, EPS, revenue from Screener.in
- 🏦 **Macro Data** — RBI rates, FII/DII flows impact
- 🔄 **Auto Refresh** — Daily data refresh via Prefect scheduler
- 🔍 **Stock Discovery** — Top upcoming NSE stocks to watch

## Project Structure
```
indian-portfolio-manager/
├── config/
│   ├── settings.py          # All config, API keys, constants
│   └── portfolio.json       # Your portfolio holdings
├── src/
│   ├── collectors/
│   │   ├── price_collector.py       # yfinance — prices + technicals
│   │   ├── fundamental_collector.py # Screener.in scraper
│   │   ├── news_collector.py        # NewsAPI + MoneyControl RSS
│   │   └── macro_collector.py       # RBI + FII/DII data
│   ├── rag/
│   │   ├── embedder.py       # Chunk + embed documents
│   │   ├── vector_store.py   # Qdrant vector DB interface
│   │   └── router.py         # Smart query routing logic
│   └── analysis/
│       ├── technicals.py     # RSI, MACD, MA calculations
│       ├── sentiment.py      # News sentiment scoring
│       └── llm_analyst.py    # LLM reasoning + structured output
├── dashboard/
│   ├── app.py               # Main Streamlit app
│   ├── portfolio_page.py    # Portfolio overview page
│   ├── stock_page.py        # Individual stock deep dive
│   ├── chat_page.py         # AI chat interface
│   └── discovery_page.py    # New stock recommendations
├── scheduler/
│   └── daily_refresh.py     # Prefect daily data pipeline
├── tests/
│   ├── test_collectors.py
│   ├── test_rag.py
│   └── test_analysis.py
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

## Quick Start

### 1. Clone & Install
```bash
git clone https://github.com/mehulbafna/smart-portfolio-manager-ai
cd smart-portfolio-manager-ai
pip install -r requirements.txt
```

### 2. Set Up API Keys
```bash
cp .env.example .env
# Edit .env and fill in your API keys
```

### 3. Add Your Portfolio
Edit `config/portfolio.json`:
```json
{
  "holdings": [
    {"ticker": "RELIANCE.NS", "name": "Reliance Industries", "qty": 10, "avg_price": 2500},
    {"ticker": "INFY.NS", "name": "Infosys", "qty": 25, "avg_price": 1450}
  ]
}
```

### 4. Initialize Vector DB
```bash
python -m src.rag.embedder --init
```

### 5. Run Dashboard
```bash
streamlit run dashboard/app.py
```

### 6. Run Scheduler (optional)
```bash
python scheduler/daily_refresh.py
```

## API Keys Required
| Service | Free Tier | Link |
|---|---|---|
| NewsAPI | 100 req/day | https://newsapi.org |
| Anthropic (Claude) | Pay per use | https://anthropic.com |
| Qdrant | Free cloud | https://qdrant.tech |

## Data Sources
- **Prices & Technicals** — yfinance (NSE tickers with `.NS` suffix)
- **Fundamentals** — Screener.in (scraped)
- **News** — NewsAPI + MoneyControl RSS
- **Macro** — RBI website + NSE FII/DII data

## Tech Stack
- **LLM** — Claude claude-sonnet-4-6 via Anthropic API
- **Vector DB** — Qdrant
- **Embeddings** — sentence-transformers (all-MiniLM-L6-v2)
- **Dashboard** — Streamlit + Plotly
- **Scheduler** — Prefect
- **Data** — yfinance, BeautifulSoup, requests
