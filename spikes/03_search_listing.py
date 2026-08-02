#!/usr/bin/env python3
"""
SPIKE 3 — Can the search pages be the live discovery feed?

Gedeon supplied the two queries the whole system hangs off:

  international : ...jobsearch?searchstring=&locationstring=&locationparam=&fglo=1&sort=M
  LMIA approved : ...jobsearch?page=1&sort=M&fskl=101020

This spike answers the question that decides the discovery architecture:

  Q1  Does sort=M actually mean newest-first?
      → If yes, polling page 1 IS the monitoring mechanism, and the freshness
        gap left by the monthly open-data CSV closes. This is the single most
        important unknown left in the plan.
  Q2  Is the results list server-rendered, or assembled by JS?
      → Server-rendered means a plain HTTP GET is enough; no browser in prod.
  Q3  What is the posting-URL / posting-ID pattern?  (dedup key)
  Q4  How does pagination work, and how many results does each facet return?
  Q5  What fields are on the result card, without opening the posting?
      → Anything available here is a field we never need a detail fetch for,
        which directly reduces how often we touch the site.
  Q6  Does the facet label text still appear on the page?
      → Guard against fskl=101020 silently changing meaning.

    pip install requests beautifulsoup4 lxml
    python spikes/03_search_listing.py                 # both configured searches
    python spikes/03_search_listing.py --url "<any search URL>"

No browser needed unless Q2 says otherwise. Writes to spikes/out/.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse, parse_qs

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    sys.exit("missing deps.  pip install requests beautifulsoup4 lxml")

OUT = Path(__file__).parent / "out"
BASE = "https://www.jobbank.gc.ca"

SEARCHES = {
    "international_candidates":
        f"{BASE}/jobsearch/jobsearch?searchstring=&locationstring=&locationparam=&fglo=1&sort=M",
    "lmia_approved":
        f"{BASE}/jobsearch/jobsearch?page=1&sort=M&fskl=101020",
}

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36 "
      "(Northbound job-application assistant; gedeon@gedeonchrist.com)")

POSTING_HREF = re.compile(r"/jobsearch/jobposting/(\d+)", re.I)
DATE_HINT = re.compile(
    r"\b(\d{4}-\d{2}-\d{2}|"
    r"(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}|"
    r"\d{1,2}\s+(?:hours?|days?|minutes?)\s+ago|today|yesterday)\b", re.I)
COUNT_HINT = re.compile(r"([\d,]{2,})\s+(?:jobs?|results?|postings?)", re.I)
STOP = ("captcha", "unusual traffic", "access denied", "are you a robot")


def analyse(name: str, url: str, session: requests.Session) -> dict:
    print(f"\n=== {name} ===\n→ GET {url}")
    r = session.get(url, timeout=45)
    print(f"  status {r.status_code}  {len(r.text):,} bytes")

    res: dict = {"name": name, "url": url, "http_status": r.status_code,
                 "bytes": len(r.text)}

    low = r.text.lower()
    hit = [s for s in STOP if s in low]
    if hit:
        res["fatal"] = f"stop signal: {hit}"
        print(f"  !! {res['fatal']} — stopping, not retrying")
        return res
    if r.status_code != 200:
        res["fatal"] = f"HTTP {r.status_code}"
        return res

    (OUT / f"search-{name}.html").write_text(r.text, encoding="utf-8")
    soup = BeautifulSoup(r.text, "lxml")

    # ---- Q3: posting links + id pattern --------------------------------
    ids, links = [], []
    for a in soup.find_all("a", href=True):
        m = POSTING_HREF.search(a["href"])
        if m:
            ids.append(m.group(1))
            links.append(urljoin(BASE, a["href"]))
    seen, uniq = set(), []
    for i, l in zip(ids, links):
        if i not in seen:
            seen.add(i)
            uniq.append({"id": i, "url": l})
    res["Q3_postings"] = {
        "count_on_page": len(uniq),
        "id_looks_numeric": all(i.isdigit() for i in seen),
        "first_10": uniq[:10],
        "dedup_key_note": "posting id from the URL path is the natural dedup key",
    }
    print(f"  Q3 postings on page: {len(uniq)}")

    # ---- Q2: server-rendered or JS-assembled? --------------------------
    res["Q2_server_rendered"] = {
        "verdict": "server_rendered" if uniq else "js_assembled_or_changed_markup",
        "implication": ("plain HTTP GET is sufficient — no browser needed for discovery"
                        if uniq else
                        "results not in raw HTML; discovery needs a browser, or an "
                        "underlying JSON endpoint should be found in devtools"),
    }
    print(f"  Q2 {res['Q2_server_rendered']['verdict']}")

    # ---- Q1: is sort=M newest-first? -----------------------------------
    dates = [m.group(0) for m in DATE_HINT.finditer(soup.get_text(" ", strip=True))]
    res["Q1_sort_order"] = {
        "date_like_strings_in_page_order": dates[:25],
        "how_to_read": ("If these run newest → oldest down the page, sort=M is "
                        "newest-first and polling page 1 is a valid live feed. "
                        "If they look unordered, sort=M is NOT date sort and the "
                        "monitoring design needs a different sort value."),
        "verdict": "INSPECT MANUALLY — this one needs a human eye",
    }
    print(f"  Q1 first dates seen: {dates[:5]}")

    # ---- Q4: pagination + result count ---------------------------------
    total = COUNT_HINT.search(soup.get_text(" ", strip=True))
    pager = []
    for a in soup.find_all("a", href=True):
        q = parse_qs(urlparse(a["href"]).query)
        if "page" in q:
            pager.append({"page": q["page"][0], "href": urljoin(BASE, a["href"])})
    res["Q4_pagination"] = {
        "reported_total": total.group(1) if total else None,
        "page_links_sample": pager[:8],
        "mechanism": "query param ?page=N" if pager else "none found — inspect HTML",
    }
    print(f"  Q4 total reported: {res['Q4_pagination']['reported_total']}")

    # ---- Q5: what's on the card without opening the posting? -----------
    card = None
    if uniq:
        anchor = soup.find("a", href=re.compile(POSTING_HREF))
        node = anchor
        for _ in range(4):                      # walk up to the card container
            if node and node.parent:
                node = node.parent
        if node:
            card = {
                "html_excerpt": str(node)[:2500],
                "text": node.get_text(" ", strip=True)[:600],
                "classes_seen": Counter(
                    c for el in node.find_all(True) for c in (el.get("class") or [])
                ).most_common(15),
            }
    res["Q5_result_card"] = card or {"note": "no card isolated — inspect saved HTML"}

    # ---- Q6: facet label still present? --------------------------------
    text_low = soup.get_text(" ", strip=True).lower()
    res["Q6_facet_guard"] = {
        "lmia_words_present": [w for w in
            ("lmia", "labour market impact", "temporary foreign worker", "tfw")
            if w in text_low],
        "international_words_present": [w for w in
            ("international", "outside canada", "foreign candidate")
            if w in text_low],
        "why": "If the facet code silently changes meaning, these words disappear "
               "while the query still returns results. Assert on them at ingest.",
    }
    print(f"  Q6 facet words: {res['Q6_facet_guard']['lmia_words_present'] or res['Q6_facet_guard']['international_words_present']}")
    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", help="analyse a single search URL instead of the configured two")
    args = ap.parse_args()

    OUT.mkdir(exist_ok=True)
    targets = {"custom": args.url} if args.url else SEARCHES

    s = requests.Session()
    s.headers.update({"User-Agent": UA,
                      "Accept-Language": "en-CA,en;q=0.9",
                      "Accept": "text/html,application/xhtml+xml"})

    report = {"spike": "03_search_listing",
              "run_at": datetime.now(timezone.utc).isoformat(),
              "results": []}
    for name, url in targets.items():
        try:
            report["results"].append(analyse(name, url, s))
        except Exception as e:
            report["results"].append({"name": name, "url": url,
                                      "error": f"{type(e).__name__}: {e}"})
            print(f"  !! {type(e).__name__}: {e}")

    path = OUT / "search-listing-report.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"\n✔ wrote {path}")
    first = next((p["url"] for r in report["results"]
                  if isinstance(r.get("Q3_postings"), dict)
                  for p in r["Q3_postings"]["first_10"][:1]), None)
    if first:
        print("\nNext — run spike 1 against a real posting from this list:")
        print(f'  python spikes/01_fetch_posting.py --url "{first}" --headed')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
