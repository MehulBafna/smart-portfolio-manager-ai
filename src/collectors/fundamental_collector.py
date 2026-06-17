"""
Fundamental Collector — scrapes Screener.in for P/E, EPS,
revenue, debt, promoter holding, and quarterly results.
"""

import requests
from bs4 import BeautifulSoup
import re
from typing import Optional
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import SCREENER_BASE_URL

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def _nse_to_screener(ticker: str) -> str:
    """Convert NSE ticker (RELIANCE.NS) to Screener.in slug (RELIANCE)."""
    return ticker.replace(".NS", "").replace(".BO", "").upper()


def scrape_fundamentals(ticker: str) -> dict:
    """
    Scrape key fundamental data from Screener.in.
    Returns dict with P/E, EPS, revenue growth, debt, promoter holding etc.
    """
    slug = _nse_to_screener(ticker)
    url = f"{SCREENER_BASE_URL}/{slug}/consolidated/"

    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code == 404:
            # Try standalone (non-consolidated)
            url = f"{SCREENER_BASE_URL}/{slug}/"
            resp = requests.get(url, headers=HEADERS, timeout=10)

        if resp.status_code != 200:
            return {"error": f"Screener.in returned {resp.status_code} for {slug}"}

        soup = BeautifulSoup(resp.text, "html.parser")
        result = {"ticker": ticker, "screener_url": url}

        # --- Key ratios ---
        ratios = {}
        ratio_section = soup.find("ul", id="top-ratios")
        if ratio_section:
            for li in ratio_section.find_all("li"):
                name_tag = li.find("span", class_="name")
                value_tag = li.find("span", class_="number")
                if name_tag and value_tag:
                    key = name_tag.get_text(strip=True)
                    val = value_tag.get_text(strip=True)
                    ratios[key] = val

        result["ratios"] = ratios
        result["pe_ratio"] = ratios.get("Stock P/E", "N/A")
        result["book_value"] = ratios.get("Book Value", "N/A")
        result["dividend_yield"] = ratios.get("Dividend Yield", "N/A")
        result["roce"] = ratios.get("ROCE", "N/A")
        result["roe"] = ratios.get("ROE", "N/A")
        result["face_value"] = ratios.get("Face Value", "N/A")
        result["market_cap"] = ratios.get("Market Cap", "N/A")

        # --- About section ---
        about = soup.find("div", class_="company-profile")
        if about:
            result["about"] = about.get_text(strip=True)[:600]

        # --- Pros and Cons (Screener's own analysis) ---
        pros, cons = [], []
        pros_section = soup.find("div", class_="pros")
        cons_section = soup.find("div", class_="cons")
        if pros_section:
            pros = [li.get_text(strip=True) for li in pros_section.find_all("li")]
        if cons_section:
            cons = [li.get_text(strip=True) for li in cons_section.find_all("li")]
        result["pros"] = pros[:5]
        result["cons"] = cons[:5]

        # --- Quarterly results (last 4 quarters) ---
        quarterly = []
        q_section = soup.find("section", id="quarters")
        if q_section:
            table = q_section.find("table")
            if table:
                headers_row = [th.get_text(strip=True) for th in table.find_all("th")]
                for row in table.find_all("tr")[1:5]:  # last 4 rows
                    cells = [td.get_text(strip=True) for td in row.find_all("td")]
                    if cells:
                        quarterly.append(dict(zip(headers_row, cells)))
        result["quarterly_results"] = quarterly

        # --- Shareholding pattern ---
        promoter_holding = "N/A"
        sh_section = soup.find("section", id="shareholding")
        if sh_section:
            table = sh_section.find("table")
            if table:
                for row in table.find_all("tr"):
                    cells = row.find_all("td")
                    if cells and "Promoter" in cells[0].get_text():
                        promoter_holding = cells[-1].get_text(strip=True)
                        break
        result["promoter_holding"] = promoter_holding

        return result

    except requests.exceptions.Timeout:
        return {"error": f"Timeout fetching Screener.in for {ticker}"}
    except Exception as e:
        return {"error": f"Scraping error for {ticker}: {str(e)}"}


def format_fundamentals_for_rag(fundamentals: dict) -> str:
    """
    Convert fundamentals dict into a readable text chunk
    suitable for embedding into the vector store.
    """
    if "error" in fundamentals:
        return f"Fundamental data unavailable: {fundamentals['error']}"

    ticker = fundamentals.get("ticker", "")
    lines = [
        f"Fundamental Analysis for {ticker}",
        f"P/E Ratio: {fundamentals.get('pe_ratio', 'N/A')}",
        f"Book Value: {fundamentals.get('book_value', 'N/A')}",
        f"ROE: {fundamentals.get('roe', 'N/A')}",
        f"ROCE: {fundamentals.get('roce', 'N/A')}",
        f"Dividend Yield: {fundamentals.get('dividend_yield', 'N/A')}",
        f"Market Cap: {fundamentals.get('market_cap', 'N/A')}",
        f"Promoter Holding: {fundamentals.get('promoter_holding', 'N/A')}",
    ]
    if fundamentals.get("pros"):
        lines.append("Strengths: " + "; ".join(fundamentals["pros"]))
    if fundamentals.get("cons"):
        lines.append("Concerns: " + "; ".join(fundamentals["cons"]))
    if fundamentals.get("about"):
        lines.append(f"About: {fundamentals['about'][:300]}")

    return "\n".join(lines)


if __name__ == "__main__":
    data = scrape_fundamentals("RELIANCE.NS")
    print(f"P/E: {data.get('pe_ratio')}")
    print(f"ROE: {data.get('roe')}")
    print(f"Promoter Holding: {data.get('promoter_holding')}")
    print(f"Pros: {data.get('pros')}")
