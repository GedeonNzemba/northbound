#!/usr/bin/env python3
"""
SPIKE 4 — What fraction of postings can actually be applied to by email?

Spike 1 sampled ONE LMIA posting. It was "Direct Apply" only, with no email
anywhere on the page. If that is typical, the email-sending architecture in
docs/03 does not apply to the LMIA queue at all, and the plan needs rethinking
rather than extending.

This censuses a sample and reports the distribution:

  by email        → automatable, the design works
  direct apply    → needs a Job Bank account, which D4 forbids automating
  online          → employer's own ATS; manual, or out of scope
  phone / mail / fax / in person → manual only

It also captures, for the email cases, exactly where the address lives in the
DOM after the reveal — which is the last unknown blocking the contact resolver.

Mechanics confirmed by spike 1:
  • button id = "applynowbutton", text "Show how to apply"
  • clicking fires a JSF POST back to the same URL (the site is JavaServer
    Faces — note the .xhtml endpoints and jsessionid), growing the DOM ~29 KB
  • no bot signals, no CAPTCHA

    python spikes/04_method_census.py --limit 30
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

try:
    import requests
    from bs4 import BeautifulSoup
    from playwright.sync_api import sync_playwright
except ImportError:
    sys.exit("missing deps.  pip install requests beautifulsoup4 lxml playwright")

OUT = Path(__file__).parent / "out"
BASE = "https://www.jobbank.gc.ca"
LMIA = f"{BASE}/jobsearch/jobsearch?sort=M&fskl=101020&page={{page}}"

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36 "
      "(Northbound job-application assistant; gedeon@gedeonchrist.com)")

POSTING_HREF = re.compile(r"/jobsearch/jobposting/(\d+)")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
# Share-this-job links and placeholders — never an employer's apply-to address.
NOISE = re.compile(r"^(test@test\.com|.*@jobbank\.gc\.ca)$", re.I)

METHODS = {
    "email": re.compile(r"\bby email\b", re.I),
    "direct_apply": re.compile(r"\bdirect apply\b|\bapply now on job bank\b", re.I),
    "online": re.compile(r"\bonline\b|\bapply online\b", re.I),
    "phone": re.compile(r"\bby phone\b|\bby telephone\b", re.I),
    "mail": re.compile(r"\bby mail\b", re.I),
    "fax": re.compile(r"\bby fax\b", re.I),
    "in_person": re.compile(r"\bin person\b", re.I),
}
STOP = ("captcha", "unusual traffic", "access denied", "are you a robot")


def collect_ids(session: requests.Session, pages: int) -> list[str]:
    """Walk the LMIA search pages and gather posting ids, newest first."""
    ids: list[str] = []
    for p in range(1, pages + 1):
        url = LMIA.format(page=p)
        print(f"→ listing page {p}")
        r = session.get(url, timeout=45)
        if r.status_code != 200:
            print(f"  HTTP {r.status_code} — stopping")
            break
        soup = BeautifulSoup(r.text, "lxml")
        found = []
        for a in soup.find_all("a", href=True):
            m = POSTING_HREF.search(a["href"])
            if m and m.group(1) not in ids and m.group(1) not in found:
                found.append(m.group(1))
        print(f"  +{len(found)}")
        if not found:
            break
        ids.extend(found)
        time.sleep(random.uniform(2.0, 4.0))
    return ids


def inspect(page, pid: str) -> dict:
    url = f"{BASE}/jobsearch/jobposting/{pid}"
    rec: dict = {"id": pid, "url": url}
    page.goto(url, timeout=45_000, wait_until="domcontentloaded")

    before = page.content()
    if any(s in before.lower() for s in STOP):
        rec["fatal"] = "stop signal"
        return rec

    rec["title"] = page.title()

    btn = page.locator("#applynowbutton")
    if btn.count() == 0:
        btn = page.get_by_role("button", name=re.compile(r"how to apply", re.I))
    if btn.count() == 0:
        rec["methods"] = []
        rec["note"] = "no apply button — posting may be expired"
        return rec

    btn.first.click()
    page.wait_for_timeout(1800)
    after = page.content()

    text = page.inner_text("body")
    rec["methods"] = [name for name, rx in METHODS.items() if rx.search(text)]

    # Emails that appeared only after the reveal, minus known noise.
    new = sorted(set(EMAIL_RE.findall(after)) - set(EMAIL_RE.findall(before)))
    rec["emails"] = [e for e in new if not NOISE.match(e)]

    # Where does the address actually live? The resolver needs this.
    if rec["emails"]:
        soup = BeautifulSoup(after, "lxml")
        node = soup.find(string=re.compile(re.escape(rec["emails"][0])))
        if node and node.parent:
            par = node.parent
            rec["email_dom_context"] = {
                "tag": par.name,
                "class": par.get("class"),
                "id": par.get("id"),
                "is_mailto": par.name == "a" and str(par.get("href", "")).startswith("mailto:"),
                "html": str(par)[:600],
                "parent_html": str(par.parent)[:900] if par.parent else None,
            }
    return rec


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=30, help="postings to inspect")
    ap.add_argument("--pages", type=int, default=5, help="listing pages to walk (25/page)")
    args = ap.parse_args()

    OUT.mkdir(exist_ok=True)
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept-Language": "en-CA,en;q=0.9"})

    ids = collect_ids(s, args.pages)
    print(f"\ncollected {len(ids)} posting ids; inspecting {min(args.limit, len(ids))}\n")

    records: list[dict] = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent=UA, locale="en-CA",
                                  viewport={"width": 1440, "height": 900})
        page = ctx.new_page()
        for n, pid in enumerate(ids[: args.limit], 1):
            try:
                rec = inspect(page, pid)
            except Exception as e:
                rec = {"id": pid, "error": f"{type(e).__name__}: {e}"}
            records.append(rec)
            print(f"  [{n:>3}] {pid}  {rec.get('methods')}  {rec.get('emails') or ''}"
                  f"{'  !! ' + rec['error'] if rec.get('error') else ''}")
            if rec.get("fatal"):
                print("  stop signal — halting census")
                break
            time.sleep(random.uniform(2.5, 5.0))   # human pace, jittered
        browser.close()

    ok = [r for r in records if "error" not in r and "fatal" not in r]
    method_counts = Counter(m for r in ok for m in r.get("methods", []))
    with_email = [r for r in ok if r.get("emails")]

    report = {
        "spike": "04_method_census",
        "run_at": datetime.now(timezone.utc).isoformat(),
        "queue": "lmia_approved (fskl=101020)",
        "ids_available": len(ids),
        "inspected": len(records),
        "usable": len(ok),
        "method_distribution": dict(method_counts),
        "email_capable": len(with_email),
        "email_capable_pct": round(100 * len(with_email) / len(ok), 1) if ok else None,
        "verdict": (
            "email path viable for this queue" if ok and len(with_email) / len(ok) >= 0.4
            else "EMAIL PATH NOT VIABLE for this queue — most postings are not "
                 "email-apply. docs/03 must be reconsidered, not extended."
        ),
        "records": records,
    }
    (OUT / "method-census.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("\n" + "=" * 60)
    print(f"  inspected      : {len(ok)}")
    print(f"  methods        : {dict(method_counts)}")
    print(f"  email-capable  : {len(with_email)} ({report['email_capable_pct']}%)")
    print(f"  VERDICT        : {report['verdict']}")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
