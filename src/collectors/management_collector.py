"""
management_collector.py — Fetches management insights for ANY NSE/BSE stock.

Sources (in priority order):
  1. Official company IR page (annual report / investor relations section)
  2. BSE filing search page for the company
  3. Screener.in as reliable fallback (covers all listed companies)

Note: All requests run from the user's local machine so corporate
      websites are fully accessible (no IP blocking issues).
"""

import requests
from bs4 import BeautifulSoup
import anthropic
import os
import json
import logging
import re
import io
from typing import Optional, Tuple
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# Official IR pages for NSE stocks
# These are the investor relations / annual report sections
OFFICIAL_IR_URLS = {
    "RELIANCE.NS":   "https://www.ril.com/investor-relations",
    "INFY.NS":       "https://www.infosys.com/investors.html",
    "TCS.NS":        "https://www.tcs.com/investor-relations",
    "HDFCBANK.NS":   "https://www.hdfcbank.com/content/bbp/repositories/723fb80a-2dde-42a3-9793-7ae1be57c87f/?folderPath=/pdfs/invest/Annual_Report/",
    "WIPRO.NS":      "https://www.wipro.com/investors/",
    "TATAMOTORS.NS": "https://www.tatamotors.com/investors/",
    "SBIN.NS":       "https://sbi.co.in/web/investor-relations",
    "ADANIENT.NS":   "https://www.adanienterprises.com/investors",
    "BAJFINANCE.NS": "https://www.bajajfinserv.in/investors",
    "ZOMATO.NS":     "https://ir.zomato.com/",
    "ICICIBANK.NS":  "https://www.icicibank.com/aboutus/annual.page",
    "KOTAKBANK.NS":  "https://ir.kotak.com/",
    "AXISBANK.NS":   "https://www.axisbank.com/investors",
    "SUNPHARMA.NS":  "https://sunpharma.com/investors/",
    "MARUTI.NS":     "https://www.marutisuzuki.com/corporate/investors",
    "NTPC.NS":       "https://www.ntpc.co.in/en/investors",
    "HCLTECH.NS":    "https://www.hcltech.com/investors",
    "LTIM.NS":       "https://www.ltimindtree.com/investors/",
    "TECHM.NS":      "https://www.techmahindra.com/en-in/investors/",
    "DRREDDY.NS":    "https://www.drreddys.com/investors/",
    "NESTLEIND.NS":  "https://www.nestle.in/investors",
    "HINDUNILVR.NS": "https://www.hul.co.in/investor-relations/",
    "ITC.NS":        "https://www.itcportal.com/investor/index.aspx",
    "ASIANPAINT.NS": "https://www.asianpaints.com/more/investor-relations.html",
    "BAJAJ-AUTO.NS": "https://www.bajajauto.com/investors",
    "HEROMOTOCO.NS": "https://www.heromotocorp.com/en-in/investors.html",
    "POWERGRID.NS":  "https://www.powergridindia.com/investors",
    "COALINDIA.NS":  "https://www.coalindia.in/en-us/investors.aspx",
    "ONGC.NS":       "https://ongcindia.com/web/eng/investor-relations",
    "BPCL.NS":       "https://www.bharatpetroleum.in/investor-relations",
    "PIDILITIND.NS": "https://www.pidiliteindustries.com/investors",
    "DMART.NS":      "https://www.dmart.in/investors.aspx",
    "TITAN.NS":      "https://www.titancompany.in/investors",
    "BAJAJFINSV.NS": "https://www.bajajfinserv.in/investors",
    "INDUSINDBK.NS": "https://www.indusind.com/iib/home/investor-relations.html",
    "M&M.NS":        "https://www.mahindra.com/investor-relations",
    "ULTRACEMCO.NS": "https://www.ultratechcement.com/investors",
    "GRASIM.NS":     "https://www.grasim.com/investors",
    "CIPLA.NS":      "https://www.cipla.com/investors",
    "DIVISLAB.NS":   "https://www.divislab.com/investors.php",
    "BRITANNIA.NS":  "https://www.britannia.co.in/investor-relations/",
    "MARICO.NS":     "https://www.marico.com/india/investors",
    "DABUR.NS":      "https://www.dabur.com/investors",
    "GODREJCP.NS":   "https://www.godrejcp.com/investors",
    "HAVELLS.NS":    "https://www.havells.com/investors.html",
    "VOLTAS.NS":     "https://www.voltas.com/investors",
    "BERGEPAINT.NS": "https://www.bergerpaints.com/investor-relations",
    "PERSISTENT.NS": "https://www.persistent.com/investors/",
    "MPHASIS.NS":    "https://www.mphasis.com/investors.html",
    "COFORGE.NS":    "https://www.coforge.com/investors",
    "NAUKRI.NS":     "https://info.edgeindia.com/investors/",
}


def _normalize_ticker(ticker: str) -> str:
    """Strip exchange suffix: RELIANCE.NS → RELIANCE"""
    return re.sub(r'\.(NS|BO|BSE|NSE)$', '', ticker, flags=re.IGNORECASE).upper()


def _get_official_ir_url(ticker: str) -> Optional[str]:
    """Get official IR URL — tries exact match then NSE equivalent for BSE tickers."""
    if ticker in OFFICIAL_IR_URLS:
        return OFFICIAL_IR_URLS[ticker]
    # Try NSE equivalent for BSE tickers
    nse = ticker.replace(".BO", ".NS")
    if nse in OFFICIAL_IR_URLS:
        return OFFICIAL_IR_URLS[nse]
    return None


def _fetch_page_text(url: str, max_chars: int = 8000) -> Optional[str]:
    """Fetch clean text from any URL."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            logger.warning(f"HTTP {resp.status_code} for {url}")
            return None

        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()

        # Try to find main content area
        main = (
            soup.find("main") or
            soup.find("article") or
            soup.find("div", {"id": re.compile(r'content|main|body', re.I)}) or
            soup.find("div", {"class": re.compile(r'content|main|investor|annual', re.I)})
        )
        text = (main or soup).get_text(separator=" ", strip=True)
        text = re.sub(r'\s+', ' ', text).strip()
        return text[:max_chars] if len(text) > 200 else None

    except Exception as e:
        logger.error(f"Fetch error {url}: {e}")
        return None


def _fetch_pdf_text(url: str, max_chars: int = 8000) -> Optional[str]:
    """Download and extract text from a PDF annual report."""
    try:
        import pdfplumber
        resp = requests.get(url, headers=HEADERS, timeout=30, stream=True)
        if resp.status_code != 200:
            return None

        pdf_bytes = io.BytesIO(resp.content)
        text_parts = []

        with pdfplumber.open(pdf_bytes) as pdf:
            # Look for Management Discussion & Analysis section
            # Usually in pages 30-80 of annual report
            mda_found = False
            for i, page in enumerate(pdf.pages):
                if i > 120:  # Don't go too deep
                    break
                page_text = page.extract_text() or ""
                # Detect MDA section
                if any(kw in page_text.upper() for kw in
                       ["MANAGEMENT DISCUSSION", "MD&A", "MANAGEMENT'S DISCUSSION",
                        "CHAIRMAN'S MESSAGE", "CEO MESSAGE", "MANAGING DIRECTOR"]):
                    mda_found = True
                if mda_found:
                    text_parts.append(page_text)
                    if len(" ".join(text_parts)) > max_chars:
                        break

        if text_parts:
            return " ".join(text_parts)[:max_chars]

        # If MDA not found, take first 20 pages
        with pdfplumber.open(pdf_bytes) as pdf:
            for page in list(pdf.pages)[:20]:
                text_parts.append(page.extract_text() or "")
        return " ".join(text_parts)[:max_chars]

    except Exception as e:
        logger.error(f"PDF extraction error {url}: {e}")
        return None


def _find_annual_report_pdf(ir_url: str, company_name: str) -> Optional[str]:
    """
    Look for annual report PDF link on the IR page.
    Returns PDF URL if found.
    """
    try:
        resp = requests.get(ir_url, headers=HEADERS, timeout=12)
        if resp.status_code != 200:
            return None

        soup = BeautifulSoup(resp.text, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a["href"]
            text = a.get_text(strip=True).lower()
            # Look for annual report PDF links
            if ".pdf" in href.lower() and any(
                kw in text or kw in href.lower()
                for kw in ["annual report", "annual-report", "annualreport"]
            ):
                # Make absolute URL if relative
                if href.startswith("/"):
                    from urllib.parse import urlparse
                    base = urlparse(ir_url)
                    href = f"{base.scheme}://{base.netloc}{href}"
                logger.info(f"Found annual report PDF: {href}")
                return href
    except Exception as e:
        logger.debug(f"PDF search error: {e}")
    return None


def _fetch_screener_text(ticker: str) -> Tuple[str, str]:
    """Screener.in fallback — works for all NSE+BSE stocks."""
    slug = _normalize_ticker(ticker)
    urls = [
        f"https://www.screener.in/company/{slug}/consolidated/",
        f"https://www.screener.in/company/{slug}/",
    ]

    for url in urls:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=12)
            if resp.status_code != 200:
                continue

            soup = BeautifulSoup(resp.text, "html.parser")
            parts = []

            for section_id, label in [
                ("company-profile", "OVERVIEW"),
                ("top-ratios",      "KEY RATIOS"),
                ("quarters",        "QUARTERLY RESULTS"),
            ]:
                el = soup.find(id=section_id) or soup.find(class_=section_id)
                if el:
                    parts.append(f"{label}:\n{el.get_text(strip=True)[:800]}")

            for cls, label in [("pros", "STRENGTHS"), ("cons", "CONCERNS")]:
                el = soup.find("div", class_=cls)
                if el:
                    parts.append(f"{label}:\n{el.get_text(strip=True)}")

            # Also look for official IR/annual report links on Screener
            for a in soup.find_all("a", href=True):
                href = a["href"]
                text = a.get_text(strip=True).lower()
                skip = ["screener.in", "bseindia.com", "nseindia.com"]
                if any(s in href for s in skip):
                    continue
                if href.startswith("http") and any(
                    kw in text or kw in href.lower()
                    for kw in ["annual report", "investor relation", "ir."]
                ):
                    # Found official link — fetch that too
                    official_text = _fetch_page_text(href)
                    if official_text:
                        logger.info(f"Fetched official IR from Screener link: {href}")
                        return official_text + "\n\n" + "\n\n".join(parts), href
                    break

            if parts:
                return "\n\n".join(parts)[:8000], url

        except Exception as e:
            logger.error(f"Screener error for {ticker}: {e}")
            continue

    return "", f"https://www.screener.in/company/{slug}/"


def _extract_with_llm(raw_text: str, company_name: str,
                       ticker: str, source_url: str) -> dict:
    """Use Claude to extract structured management insights."""
    prompt = f"""You are analyzing official investor relations content for {company_name} ({ticker}).
Source: {source_url}

Extract the following management insights from the content below:
1. Key financial highlights from the annual report (revenue growth, profit, achievements)
2. CEO / MD / Chairman strategic commentary and key messages
3. Strategic outlook — growth plans, new investments, expansion areas
4. Latest quarterly performance highlights
5. Key risks that management has flagged

CONTENT:
{raw_text[:5000]}

Return ONLY valid JSON with exactly these fields:
{{
  "company": "{company_name}",
  "source_url": "{source_url}",
  "source_type": "Official IR Page or BSE Filing or Screener.in",
  "annual_highlights": ["highlight 1", "highlight 2", "highlight 3"],
  "ceo_commentary": "2-3 sentence summary of CEO/Chairman key messages",
  "strategic_outlook": ["outlook point 1", "outlook point 2", "outlook point 3"],
  "quarterly_commentary": "latest quarterly summary or Not available",
  "key_risks": ["risk 1", "risk 2"],
  "data_quality": "good or partial or limited"
}}

Use empty list [] or "Not available" for missing fields.
Return valid JSON only — no markdown, no explanation."""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = response.content[0].text.strip().replace("```json","").replace("```","").strip()
        data = json.loads(raw)
        data["source_url"] = source_url
        return data
    except Exception as e:
        logger.error(f"LLM error for {company_name}: {e}")
        return {
            "company": company_name,
            "source_url": source_url,
            "source_type": "Unknown",
            "annual_highlights": [],
            "ceo_commentary": "Could not extract management commentary",
            "strategic_outlook": [],
            "quarterly_commentary": "Not available",
            "key_risks": [],
            "data_quality": "limited"
        }


def fetch_management_insights(ticker: str, company_name: str) -> dict:
    """
    Main entry point. Works for ANY NSE or BSE listed stock.

    Priority:
      1. Official company IR page → look for annual report PDF → extract MDA
      2. Official company IR page → extract HTML content
      3. Screener.in → extract management discussion + follow any IR links found
    """
    logger.info(f"Fetching management insights for {company_name} ({ticker})")

    # ── Strategy 1: Official IR page ──────────────────────────────────
    ir_url = _get_official_ir_url(ticker)

    if ir_url:
        logger.info(f"Trying official IR page: {ir_url}")

        # First try to find and extract annual report PDF
        pdf_url = _find_annual_report_pdf(ir_url, company_name)
        if pdf_url:
            logger.info(f"Extracting annual report PDF: {pdf_url}")
            pdf_text = _fetch_pdf_text(pdf_url)
            if pdf_text and len(pdf_text) > 500:
                insights = _extract_with_llm(pdf_text, company_name, ticker, pdf_url)
                insights["source_type"] = "Official Annual Report (PDF)"
                insights["source_url"] = pdf_url
                logger.info(f"Done via PDF — quality: {insights.get('data_quality')}")
                return insights

        # Try HTML content of IR page
        html_text = _fetch_page_text(ir_url)
        if html_text and len(html_text) > 500:
            insights = _extract_with_llm(html_text, company_name, ticker, ir_url)
            insights["source_type"] = "Official IR Page"
            logger.info(f"Done via official IR HTML — quality: {insights.get('data_quality')}")
            return insights

        logger.warning(f"Official IR page returned insufficient content, trying Screener")

    # ── Strategy 2: Screener.in fallback (all NSE+BSE stocks) ─────────
    raw_text, source_url = _fetch_screener_text(ticker)

    if not raw_text or len(raw_text) < 100:
        slug = _normalize_ticker(ticker)
        return {
            "company": company_name,
            "source_url": f"https://www.screener.in/company/{slug}/",
            "source_type": "Screener.in",
            "annual_highlights": [],
            "ceo_commentary": "Could not fetch management information",
            "strategic_outlook": [],
            "quarterly_commentary": "Not available",
            "key_risks": [],
            "data_quality": "limited"
        }

    # Determine source type
    source_type = "Official IR Page" if "screener" not in source_url else "Screener.in"
    insights = _extract_with_llm(raw_text, company_name, ticker, source_url)
    insights["source_type"] = source_type
    logger.info(f"Done via {source_type} — quality: {insights.get('data_quality')} | {source_url}")
    return insights


def format_insights_for_rag(insights: dict) -> str:
    """Format for vector store embedding."""
    lines = [f"Management Insights: {insights.get('company', '')}"]
    lines.append(f"Source: {insights.get('source_url', '')} ({insights.get('source_type','')})")
    for field, label in [("ceo_commentary","Commentary"), ("quarterly_commentary","Quarterly")]:
        val = insights.get(field)
        if val and val != "Not available":
            lines.append(f"{label}: {val}")
    for field, label in [("annual_highlights","Highlights"),("strategic_outlook","Outlook"),("key_risks","Risks")]:
        vals = insights.get(field, [])
        if vals:
            lines.append(f"{label}: " + "; ".join(vals))
    return "\n".join(lines)


if __name__ == "__main__":
    # Test
    r = fetch_management_insights("RELIANCE.NS", "Reliance Industries")
    print(json.dumps(r, indent=2))
    print(f"\nSource: {r['source_url']}")
    print(f"Type:   {r['source_type']}")