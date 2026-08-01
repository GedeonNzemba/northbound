#!/usr/bin/env python3
"""
SPIKE 1 — What actually happens when you click "Show how to apply"?

Everything in docs/03-architecture.md about contact resolution is an ASSUMPTION
until this script has been run and its output read. It answers:

  Q1  Is the reveal a page navigation, an AJAX call, or content already in the
      DOM behind a CSS toggle?  (decides: HTTP client vs headless browser)
  Q2  What is the stable selector for the button and the revealed block?
  Q3  Which application methods appear, and how is each marked up?
  Q4  Is an email a mailto: link, plain text, or obfuscated?
  Q5  Is there a bot check, a rate limit, or a cookie/consent wall in the way?
  Q6  What does the filtered LMIA search URL look like, and does paging hold?

Run it on a normal machine — NOT in a datacenter/CI container, where gc.ca
traffic is frequently blocked before it reaches the site.

    pip install playwright && playwright install chromium
    python spikes/01_fetch_posting.py --url "<a single Job Bank posting URL>"

Then send back  spikes/out/  — that is what turns the architecture from guess
into design.

Deliberate constraints (see docs/06-decisions.md D5):
  • one posting per run, logged out, no account, no credentials
  • honest user agent — no fingerprint spoofing, no proxy rotation
  • stops on the first sign the site doesn't want the traffic
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
except ImportError:
    sys.exit("playwright not installed.  pip install playwright && playwright install chromium")

OUT = Path(__file__).parent / "out"

# Honest identification. If Job Bank objects to this traffic they can identify
# and contact us — which is the point.
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36 "
    "(Northbound job-application assistant; gedeon@gedeonchrist.com)"
)

# The button text varies by locale and has changed before — match generously.
BUTTON_PATTERNS = [
    re.compile(r"how to apply", re.I),
    re.compile(r"show how to apply", re.I),
    re.compile(r"comment postuler", re.I),
]

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")

# Signals that we should stop rather than push harder.
STOP_SIGNALS = ("captcha", "unusual traffic", "access denied", "rate limit",
                "temporarily blocked", "are you a robot")


def find_apply_button(page):
    """Return (locator, how_we_found_it) or (None, None)."""
    strategies = [
        ("role=button", lambda p: p.get_by_role("button", name=BUTTON_PATTERNS[0])),
        ("role=link", lambda p: p.get_by_role("link", name=BUTTON_PATTERNS[0])),
        ("text", lambda p: p.get_by_text(BUTTON_PATTERNS[0])),
        ("id~=apply", lambda p: p.locator("[id*='apply' i], [id*='postuler' i]")),
        ("class~=apply", lambda p: p.locator("[class*='apply' i]")),
    ]
    for label, build in strategies:
        try:
            loc = build(page)
            if loc.count() > 0 and loc.first.is_visible():
                return loc.first, label
        except Exception:
            continue
    return None, None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True, help="A single Job Bank posting URL")
    ap.add_argument("--headed", action="store_true", help="Watch it happen")
    ap.add_argument("--timeout", type=int, default=30_000)
    args = ap.parse_args()

    OUT.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    findings: dict = {
        "spike": "01_fetch_posting",
        "run_at": stamp,
        "url": args.url,
        "questions": {},
    }

    # Q1 evidence: record every network request the click provokes.
    network_after_click: list[dict] = []
    clicked = False

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=not args.headed)
        ctx = browser.new_context(user_agent=UA, locale="en-CA",
                                  viewport={"width": 1440, "height": 900})
        page = ctx.new_page()

        def on_request(req):
            if clicked and req.resource_type in ("xhr", "fetch", "document"):
                network_after_click.append(
                    {"method": req.method, "url": req.url, "type": req.resource_type}
                )

        page.on("request", on_request)

        print(f"→ GET {args.url}")
        try:
            resp = page.goto(args.url, timeout=args.timeout, wait_until="domcontentloaded")
        except PWTimeout:
            findings["fatal"] = "navigation timeout"
            (OUT / f"findings-{stamp}.json").write_text(json.dumps(findings, indent=2))
            return 2

        findings["http_status"] = resp.status if resp else None
        print(f"  status {findings['http_status']}")

        before_html = page.content()
        (OUT / f"before-click-{stamp}.html").write_text(before_html, encoding="utf-8")

        low = before_html.lower()
        tripped = [s for s in STOP_SIGNALS if s in low]
        if tripped:
            findings["fatal"] = f"stop signal on load: {tripped}"
            print(f"  !! {findings['fatal']} — stopping, not retrying")
            (OUT / f"findings-{stamp}.json").write_text(json.dumps(findings, indent=2))
            browser.close()
            return 3

        # Q4 (part 1): is the email already in the DOM before we click?
        emails_before = sorted(set(EMAIL_RE.findall(before_html)))
        mailto_before = page.locator("a[href^='mailto:']").count()
        findings["questions"]["Q4_email_present_before_click"] = {
            "regex_hits": emails_before,
            "mailto_links": mailto_before,
            "note": "If the real address is here already, no click is needed and "
                    "a plain HTTP GET is sufficient — no browser required.",
        }

        btn, how = find_apply_button(page)
        findings["questions"]["Q2_button"] = {
            "found": btn is not None,
            "located_via": how,
            "text": (btn.inner_text().strip()[:200] if btn else None),
            "tag": (btn.evaluate("e => e.tagName") if btn else None),
            "id": (btn.get_attribute("id") if btn else None),
            "class": (btn.get_attribute("class") if btn else None),
            "href": (btn.get_attribute("href") if btn else None),
            "aria_controls": (btn.get_attribute("aria-controls") if btn else None),
            "aria_expanded": (btn.get_attribute("aria-expanded") if btn else None),
        }

        if not btn:
            findings["fatal"] = "apply button not found — inspect before-click HTML"
            print("  !! button not found; dumped HTML for manual inspection")
            (OUT / f"findings-{stamp}.json").write_text(json.dumps(findings, indent=2))
            browser.close()
            return 4

        print(f"  found button via {how}: {findings['questions']['Q2_button']['text']!r}")

        url_before = page.url
        clicked = True
        btn.click()
        page.wait_for_timeout(2500)  # let any XHR settle
        after_html = page.content()
        (OUT / f"after-click-{stamp}.html").write_text(after_html, encoding="utf-8")

        # Q1: classify the mechanism from hard evidence, not vibes.
        navigated = page.url != url_before
        xhr = [r for r in network_after_click if r["type"] in ("xhr", "fetch")]
        grew = len(after_html) - len(before_html)
        if navigated:
            mechanism = "navigation"
        elif xhr:
            mechanism = "ajax"
        elif grew > 200:
            mechanism = "dom_mutation_no_network"
        else:
            mechanism = "css_toggle_content_already_present"

        findings["questions"]["Q1_mechanism"] = {
            "verdict": mechanism,
            "url_before": url_before,
            "url_after": page.url,
            "network_requests_after_click": network_after_click[:20],
            "html_growth_bytes": grew,
            "implication": {
                "navigation": "second GET; plain HTTP client is enough",
                "ajax": "call the JSON/HTML endpoint directly — no browser needed in prod",
                "dom_mutation_no_network": "content was inlined; plain GET + parse hidden node",
                "css_toggle_content_already_present": "NO fetch needed at all — the data "
                                                     "ships with the page. Cheapest possible path.",
            }[mechanism],
        }
        print(f"  mechanism: {mechanism}")

        # Q3/Q4: what application methods are now visible?
        emails_after = sorted(set(EMAIL_RE.findall(after_html)))
        new_emails = [e for e in emails_after if e not in emails_before]
        mailtos = page.eval_on_selector_all(
            "a[href^='mailto:']", "els => els.map(e => e.getAttribute('href'))"
        )
        body_text = page.inner_text("body")
        methods_seen = [
            m for m in ("by email", "online", "in person", "by mail", "by fax",
                        "by phone", "direct apply", "apply now")
            if m in body_text.lower()
        ]
        findings["questions"]["Q3_methods_visible"] = methods_seen
        findings["questions"]["Q4_email_after_click"] = {
            "new_emails": new_emails,
            "all_emails": emails_after,
            "mailto_hrefs": mailtos,
            "obfuscated_suspected": bool(methods_seen) and not emails_after,
        }
        print(f"  methods: {methods_seen or '(none matched)'}")
        print(f"  emails revealed: {new_emails or '(none)'}")

        # Q5: anything suggesting we're unwelcome?
        low_after = after_html.lower()
        findings["questions"]["Q5_bot_signals"] = [s for s in STOP_SIGNALS if s in low_after]

        # Q6 hint: capture canonical/pagination shape for the search-results work.
        findings["questions"]["Q6_page_metadata"] = {
            "canonical": page.eval_on_selector(
                "link[rel=canonical]", "e => e.href"
            ) if page.locator("link[rel=canonical]").count() else None,
            "title": page.title(),
        }

        browser.close()

    path = OUT / f"findings-{stamp}.json"
    path.write_text(json.dumps(findings, indent=2), encoding="utf-8")
    print(f"\n✔ wrote {path}")
    print("  send back the whole spikes/out/ directory")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
