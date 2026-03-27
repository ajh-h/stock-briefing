#!/usr/bin/env python3
"""
generate.py — Call Claude API to generate the morning stock briefing.

Runs as part of the GitHub Actions workflow. Produces:
  - site/index.html              (mobile web app, served by GitHub Pages)
  - site/morning-stock-briefing-YYYY-MM-DD.md  (archive copy)

Requires: ANTHROPIC_API_KEY environment variable.
"""

import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import anthropic

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
MODEL = "claude-sonnet-4-20250514"  # Cost-effective for daily runs; swap to opus for higher quality
MAX_TOKENS = 12000
SITE_DIR = Path("docs")

# Determine "today" in US Eastern time (the primary market timezone)
ET = timezone(timedelta(hours=-4))  # EDT; change to -5 for EST if needed
TODAY = datetime.now(ET)
DATE_STR = TODAY.strftime("%Y-%m-%d")
DAY_OF_WEEK = TODAY.strftime("%A")
DISPLAY_DATE = TODAY.strftime("%A, %B %d, %Y")

# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """You are a financial analyst assistant that produces a daily morning stock market briefing.
You have access to web search via the tool provided. Use it extensively to get the latest market data.
Be precise with numbers. Be decisive with BUY/HOLD/SELL signals. Never leave placeholders."""

USER_PROMPT = f"""Generate a morning stock market briefing for {DISPLAY_DATE}.

Search the web for the latest available closing prices for these assets:

**US Indices:** S&P 500, DJIA, NASDAQ Composite
**Korea Indices:** KOSPI, KOSDAQ
**US Stocks:** AAPL, MSFT, AMZN, GOOG, NVDA, TSLA (need: price, change, % change, market cap, trailing P/E)
**Korea Stocks:** Samsung Electronics (005930), SK Hynix (000660), Naver (035420), Kakao (035720) (need: price in KRW, change, % change, market cap in 조, trailing P/E)

Also search for:
- 1-2 notable US stock movers from the previous session
- 1-2 notable Korea stock movers from the previous session
- Recent analyst ratings and target prices for each stock

For each stock, provide a BUY, HOLD, or SELL signal based on price action, valuation, analyst consensus, catalysts, and macro factors.

**OUTPUT FORMAT:**
Produce EXACTLY TWO code blocks in your response:

1. First, a code block labeled ```markdown containing the full markdown briefing
2. Second, a code block labeled ```html containing a complete, self-contained mobile-optimized HTML web app

The HTML must be a dark-themed, mobile-first single-page app with:
- Sticky header with date
- Sentiment banner (bearish=red tint, bullish=green tint, neutral=blue tint)
- Tab navigation: US Market | Korea Market | Notable Movers
- Index summary cards in a grid
- Expandable stock cards (tap to reveal analysis + signal badge)
- Signal badges: 🟢 BUY (green), 🟡 HOLD (yellow), 🔴 SELL (red)
- Color-coded changes (red=negative, green=positive)
- Meta row per stock: Market Cap, P/E, Change
- Pure HTML/CSS/JS, no external dependencies
- apple-mobile-web-app-capable meta tags
- Footer with "Not financial advice" disclaimer

Use these exact CSS variables:
--bg: #0a0e17; --card: #131929; --card-border: #1e2a3a;
--text: #e2e8f0; --text-muted: #8892a4; --green: #34d399; --red: #f87171; --yellow: #fbbf24; --accent: #60a5fa;
"""

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    print(f"Generating briefing for {DISPLAY_DATE}...")

    # Use extended thinking or web search if available; otherwise standard completion
    # Note: For web search, you may need to enable it in your API plan
    message = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": USER_PROMPT}],
    )

    response_text = ""
    for block in message.content:
        if hasattr(block, "text"):
            response_text += block.text

    # Extract markdown and HTML from code blocks
    md_content = extract_code_block(response_text, "markdown")
    html_content = extract_code_block(response_text, "html")

    if not html_content:
        print("ERROR: No HTML code block found in response", file=sys.stderr)
        print("Response preview:", response_text[:500], file=sys.stderr)
        sys.exit(1)

    # Ensure site directory exists
    SITE_DIR.mkdir(exist_ok=True)

    # Write files
    html_path = SITE_DIR / "index.html"
    html_path.write_text(html_content, encoding="utf-8")
    print(f"Wrote {html_path}")

    if md_content:
        md_path = SITE_DIR / f"morning-stock-briefing-{DATE_STR}.md"
        md_path.write_text(md_content, encoding="utf-8")
        print(f"Wrote {md_path}")
    else:
        print("WARNING: No markdown block found; skipping .md file")

    print("Done!")


def extract_code_block(text: str, label: str) -> str | None:
    """Extract content from a fenced code block with a given label."""
    import re
    # Match ```label ... ``` or ```label\n ... ```
    pattern = rf"```{label}\s*\n(.*?)```"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()

    # Fallback: try matching just ```html or ```markdown without strict boundaries
    pattern2 = rf"```{label}(.*?)```"
    match2 = re.search(pattern2, text, re.DOTALL)
    if match2:
        return match2.group(1).strip()

    return None


if __name__ == "__main__":
    main()
