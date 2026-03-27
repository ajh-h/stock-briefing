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
import time
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

For the HTML, use EXACTLY the following CSS (copy it verbatim into your <style> block — do not alter any values):

```css
:root {{
  --bg: #0a0e17; --card: #131929; --card-border: #1e2a3a;
  --text: #e2e8f0; --text-muted: #8892a4; --text-dim: #5a6578;
  --accent: #60a5fa; --green: #34d399; --green-bg: rgba(52,211,153,0.12);
  --red: #f87171; --red-bg: rgba(248,113,113,0.12);
  --yellow: #fbbf24; --yellow-bg: rgba(251,191,36,0.12); --divider: #1a2332;
}}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:-apple-system,BlinkMacSystemFont,'SF Pro Text','Segoe UI',system-ui,sans-serif; background:var(--bg); color:var(--text); line-height:1.5; -webkit-font-smoothing:antialiased; padding-bottom:env(safe-area-inset-bottom,20px); }}
.header {{ position:sticky; top:0; z-index:100; background:rgba(10,14,23,0.92); backdrop-filter:blur(20px); -webkit-backdrop-filter:blur(20px); border-bottom:1px solid var(--divider); padding:16px 20px 12px; }}
.header-date {{ font-size:12px; color:var(--text-muted); letter-spacing:0.5px; text-transform:uppercase; margin-bottom:2px; }}
.header-title {{ font-size:22px; font-weight:700; letter-spacing:-0.3px; }}
.header-subtitle {{ font-size:12px; color:var(--text-dim); margin-top:2px; }}
.sentiment {{ margin:16px 16px 0; padding:14px 16px; background:linear-gradient(135deg,rgba(248,113,113,0.08),rgba(251,191,36,0.06)); border:1px solid rgba(248,113,113,0.15); border-radius:14px; font-size:13.5px; color:var(--text-muted); line-height:1.55; }}
.sentiment-label {{ font-size:11px; font-weight:600; color:var(--red); letter-spacing:0.8px; text-transform:uppercase; margin-bottom:6px; }}
.tabs {{ display:flex; gap:6px; padding:14px 16px 0; overflow-x:auto; -webkit-overflow-scrolling:touch; scrollbar-width:none; }}
.tabs::-webkit-scrollbar {{ display:none; }}
.tab {{ flex-shrink:0; padding:8px 16px; border-radius:20px; font-size:13px; font-weight:600; cursor:pointer; transition:all 0.2s; background:var(--card); color:var(--text-muted); border:1px solid var(--card-border); }}
.tab.active {{ background:var(--accent); color:#fff; border-color:var(--accent); }}
.section {{ display:none; padding:16px; }}
.section.active {{ display:block; }}
.section-title {{ font-size:17px; font-weight:700; margin-bottom:14px; display:flex; align-items:center; gap:8px; }}
.section-title .flag {{ font-size:20px; }}
.index-row {{ display:grid; grid-template-columns:1fr 1fr 1fr; gap:10px; margin-bottom:16px; }}
.index-card {{ background:var(--card); border:1px solid var(--card-border); border-radius:14px; padding:14px 12px; text-align:center; }}
.index-name {{ font-size:11px; color:var(--text-muted); font-weight:600; letter-spacing:0.3px; margin-bottom:6px; }}
.index-price {{ font-size:16px; font-weight:700; letter-spacing:-0.3px; margin-bottom:4px; }}
.index-change {{ font-size:12px; font-weight:600; border-radius:6px; display:inline-block; padding:2px 8px; }}
.neg {{ color:var(--red); }} .neg-bg {{ background:var(--red-bg); color:var(--red); }}
.pos {{ color:var(--green); }} .pos-bg {{ background:var(--green-bg); color:var(--green); }}
.drivers {{ background:var(--card); border:1px solid var(--card-border); border-radius:14px; padding:14px 16px; margin-bottom:20px; }}
.drivers-label {{ font-size:11px; font-weight:600; color:var(--accent); letter-spacing:0.8px; text-transform:uppercase; margin-bottom:6px; }}
.drivers p {{ font-size:13.5px; color:var(--text-muted); line-height:1.55; }}
.stock-card {{ background:var(--card); border:1px solid var(--card-border); border-radius:14px; margin-bottom:12px; overflow:hidden; }}
.stock-header {{ display:flex; align-items:center; justify-content:space-between; padding:14px 16px; cursor:pointer; -webkit-tap-highlight-color:transparent; }}
.stock-left {{ display:flex; align-items:center; gap:12px; }}
.stock-ticker {{ font-size:14px; font-weight:700; letter-spacing:0.3px; min-width:50px; }}
.stock-company {{ font-size:12px; color:var(--text-muted); }}
.stock-right {{ text-align:right; }}
.stock-price {{ font-size:15px; font-weight:700; letter-spacing:-0.2px; }}
.stock-change {{ font-size:12px; font-weight:600; margin-top:2px; }}
.stock-meta {{ display:flex; gap:0; padding:0 16px 10px; border-bottom:1px solid var(--divider); }}
.meta-item {{ flex:1; text-align:center; padding:0 4px; }}
.meta-item:not(:last-child) {{ border-right:1px solid var(--divider); }}
.meta-label {{ font-size:10px; color:var(--text-dim); text-transform:uppercase; letter-spacing:0.5px; }}
.meta-value {{ font-size:13px; font-weight:600; color:var(--text-muted); margin-top:1px; }}
.signal {{ display:inline-flex; align-items:center; gap:4px; padding:3px 10px; border-radius:8px; font-size:11px; font-weight:700; letter-spacing:0.5px; }}
.signal-buy {{ background:var(--green-bg); color:var(--green); }}
.signal-hold {{ background:var(--yellow-bg); color:var(--yellow); }}
.signal-sell {{ background:var(--red-bg); color:var(--red); }}
.stock-analysis {{ max-height:0; overflow:hidden; transition:max-height 0.3s ease; }}
.stock-card.expanded .stock-analysis {{ max-height:500px; }}
.analysis-inner {{ padding:12px 16px 16px; font-size:13px; color:var(--text-muted); line-height:1.6; border-top:1px solid var(--divider); }}
.analysis-inner .signal {{ margin-bottom:8px; }}
.chevron {{ color:var(--text-dim); transition:transform 0.2s; font-size:12px; margin-left:8px; }}
.stock-card.expanded .chevron {{ transform:rotate(180deg); }}
.movers-title {{ font-size:14px; font-weight:700; color:var(--yellow); margin:20px 0 12px; display:flex; align-items:center; gap:6px; }}
.footer {{ text-align:center; padding:24px 16px 40px; font-size:11px; color:var(--text-dim); }}
html {{ scroll-behavior:smooth; }}
```

Use EXACTLY this JavaScript (copy verbatim):
```javascript
function showSection(id) {{
  document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.getElementById(id).classList.add('active');
  event.target.classList.add('active');
  window.scrollTo({{ top: 0, behavior: 'smooth' }});
}}
function toggleCard(card) {{ card.classList.toggle('expanded'); }}
```

HTML structure rules (follow exactly):
- Header: `<div class="header"><div class="header-date">FULL DAY DATE</div><div class="header-title">Morning Briefing</div><div class="header-subtitle">Data as of market close DATE</div></div>`
- Sentiment: `<div class="sentiment"><div class="sentiment-label">BEARISH|BULLISH|NEUTRAL</div>TEXT</div>` — color the .sentiment-label: red for bearish, green for bullish, blue/accent for neutral
- Tabs: `<div class="tabs"><button class="tab active" onclick="showSection('us')">US Market</button><button class="tab" onclick="showSection('kr')">Korea Market</button><button class="tab" onclick="showSection('movers')">Notable Movers</button></div>`
- Sections: `<div id="us" class="section active">` / `<div id="kr" class="section">` / `<div id="movers" class="section">`
- Index cards: use `.neg-bg` class for negative % change, `.pos-bg` for positive
- Stock cards: `<div class="stock-card" onclick="toggleCard(this)">` containing `.stock-header` > `.stock-left` (ticker+company) + `.stock-right` (price+change with `.neg`/`.pos` + `<span class="chevron">▼</span>`), then `.stock-meta` row, then `.stock-analysis` > `.analysis-inner` > signal div + analysis text
- Signal badges inside analysis: `<div class="signal signal-buy">🟢 BUY</div>` or `signal-hold`/`signal-sell`
- Footer: `<div class="footer">Generated by Claude &middot; Not financial advice<br>Data sourced from Google Finance, Yahoo Finance, Investing.com</div>`
- PWA meta tags: `<meta name="apple-mobile-web-app-capable" content="yes">` and `<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">`
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

    for attempt in range(1, 4):
        try:
            message = client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": USER_PROMPT}],
            )
            break
        except anthropic.APIStatusError as e:
            if e.status_code == 529 and attempt < 3:
                wait = 30 * attempt
                print(f"API overloaded (attempt {attempt}/3), retrying in {wait}s...")
                time.sleep(wait)
            else:
                raise

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
