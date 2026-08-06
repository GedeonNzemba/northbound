#!/usr/bin/env python3
"""
SPIKE 6 — Harvest the golden set: real postings, frozen, in the generator's format.

Everything in the CV engine so far has been tested against one hand-written
Ridge Farms fixture. That proves the gate works; it proves nothing about
document quality, because there is exactly one input and I wrote it.

This produces the real inputs: 15 from the LMIA-approved queue (all occupations
— D6) and 5 developer roles from the international-candidates queue, written as
`Posting` JSON the CLI consumes directly:

    northbound generate --posting postings/golden/49816590.json

**Frozen on purpose.** Job Bank postings expire; a golden set that re-harvests
is a moving target and no two evaluation runs are comparable. These files are
committed once and then treated as immutable. Re-run this spike to build a
*new* set under a new directory, never to refresh an existing one.

The extraction is deliberately multi-path and self-reporting. I do not know
Job Bank's DOM, and guessing selectors then discovering they were wrong costs a
whole CI cycle. Every field tries JSON-LD first (a government job site very
likely publishes schema.org JobPosting), then labelled-field heuristics, then a
text fallback — and records which path fired, so the next version can drop the
paths that never win.

Mechanics reused from spike 4, already confirmed against the live site:
  • `#applynowbutton` ("Show how to apply") is click 1 of 2
  • the email lives behind the SECOND disclosure, "Additional ways to apply"
  • no bot signals, no CAPTCHA, HTTP 200 to GitHub runners

    python spikes/06_golden_set.py --lmia 15 --intl 5
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Imported lazily-ish: the network deps are only needed to actually run a
# harvest, and failing at module scope would make the pure selection logic
# below untestable off a runner. The check moves into main().
try:
    import requests
    from bs4 import BeautifulSoup
    from playwright.sync_api import sync_playwright
    _DEPS_ERROR = ""
except ImportError as _exc:  # pragma: no cover — exercised only off a runner
    requests = BeautifulSoup = sync_playwright = None  # type: ignore[assignment]
    _DEPS_ERROR = f"{_exc}.  pip install requests beautifulsoup4 lxml playwright"

REPO = Path(__file__).resolve().parents[1]
OUT_DIR = REPO / "postings" / "golden"
REPORT = REPO / "spikes" / "out" / "golden-set-report.json"

BASE = "https://www.jobbank.gc.ca"
LMIA = f"{BASE}/jobsearch/jobsearch?sort=M&fskl=101020&page={{page}}"
INTL = (f"{BASE}/jobsearch/jobsearch?searchstring=&locationstring=&locationparam="
        f"&fglo=1&sort=M&page={{page}}")

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36 "
      "(Northbound job-application assistant; gedeon@gedeonchrist.com)")

POSTING_HREF = re.compile(r"/jobsearch/jobposting/(\d+)")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
NOISE = re.compile(r"^(test@test\.com|.*@jobbank\.gc\.ca)$", re.I)
NOC_RE = re.compile(r"\bNOC\b[^\d]{0,12}(\d{5})")
STOP = ("captcha", "unusual traffic", "access denied", "are you a robot")

# config/sources.yaml, TECH_ONLY queue. Duplicated here rather than imported so
# the spike stays a single file with no repo imports — it runs on a bare runner.
TECH_TITLE = re.compile(
    r"\b(web|front[- ]?end|frontend|full[- ]?stack|software|javascript|react|ui)\b"
    r".{0,20}\b(developer|designer|programmer|engineer)\b"
    r"|\bprogrammer\b|\bapplication developer\b", re.I)
TECH_NOC = {"21234", "21233", "21232", "21230", "22222"}


# --------------------------------------------------------------------------- #
# Listing
# --------------------------------------------------------------------------- #

def collect(session: requests.Session, url_tpl: str, pages: int) -> list[str]:
    ids: list[str] = []
    for p in range(1, pages + 1):
        r = session.get(url_tpl.format(page=p), timeout=45)
        print(f"→ listing page {p}: HTTP {r.status_code}")
        if r.status_code != 200:
            break
        soup = BeautifulSoup(r.text, "lxml")
        found = [m.group(1) for a in soup.find_all("a", href=True)
                 if (m := POSTING_HREF.search(a["href"]))]
        fresh = [i for i in dict.fromkeys(found) if i not in ids]
        print(f"  +{len(fresh)}")
        if not fresh:
            break
        ids.extend(fresh)
        time.sleep(random.uniform(2.0, 4.0))
    return ids


# --------------------------------------------------------------------------- #
# Extraction — every field tries several paths and says which one won
# --------------------------------------------------------------------------- #

def _jsonld(soup: BeautifulSoup) -> dict:
    """schema.org JobPosting, if the site publishes one. Cheapest correct path."""
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "{}")
        except (json.JSONDecodeError, TypeError):
            continue
        for node in (data if isinstance(data, list) else [data]):
            if isinstance(node, dict) and "JobPosting" in str(node.get("@type", "")):
                return node
    return {}


def _first(*candidates) -> tuple[str, str]:
    """Return (value, which_path_won) for the first non-empty candidate."""
    for name, value in candidates:
        if value and str(value).strip():
            return " ".join(str(value).split()), name
    return "", "none"


def _labelled(text: str, *labels: str) -> str:
    """Job Bank renders many fields as `Label: value` or `Label\\nvalue`."""
    for label in labels:
        m = re.search(rf"{re.escape(label)}\s*:?\s*\n?\s*(.+)", text, re.I)
        if m:
            return m.group(1).splitlines()[0].strip()
    return ""


def _body_text(page, soup: BeautifulSoup) -> tuple[str, str]:
    """
    The description the model reads. Prefer a scoped container; the whole page
    drags in nav, cookie banners and 'similar jobs', all of which are noise the
    specificity budget would happily quote back at the employer.
    """
    for sel in ("#job-posting-details", ".job-posting-details", "#jobdescription",
                "main", "[property='description']"):
        node = soup.select_one(sel)
        if node:
            txt = " ".join(node.get_text("\n").split("\n"))
            if len(txt) > 400:
                return node.get_text("\n"), sel
    ld = _jsonld(soup)
    if desc := ld.get("description"):
        return BeautifulSoup(desc, "lxml").get_text("\n"), "jsonld.description"
    return page.inner_text("body"), "body(fallback)"


def _clean(text: str) -> str:
    """Collapse runs of blank lines; strip the boilerplate tail."""
    text = re.sub(r"\n{3,}", "\n\n", text)
    for cut in ("Similar jobs", "Date modified:", "Report a problem",
                "Government of Canada footer"):
        text = text.split(cut)[0]
    return text.strip()


def harvest(page, pid: str, queue: str) -> dict:
    url = f"{BASE}/jobsearch/jobposting/{pid}"
    rec: dict = {"posting_id": pid, "url": url, "queue": queue}
    page.goto(url, timeout=45_000, wait_until="domcontentloaded")

    before = page.content()
    if any(s in before.lower() for s in STOP):
        rec["fatal"] = "stop signal"
        return rec

    # ---- reveal, both clicks (spike 4) ---------------------------------- #
    btn = page.locator("#applynowbutton")
    if btn.count() == 0:
        btn = page.get_by_role("button", name=re.compile(r"how to apply", re.I))
    if btn.count():
        btn.first.click()
        page.wait_for_timeout(1800)

    revealed = False
    for build in (
        lambda: page.locator("summary", has_text=re.compile(r"additional ways to apply", re.I)),
        lambda: page.get_by_text(re.compile(r"additional ways to apply", re.I)),
        lambda: page.locator("a,button", has_text=re.compile(r"additional ways to apply", re.I)),
    ):
        try:
            loc = build()
            if loc.count() and loc.first.is_visible():
                loc.first.click()
                page.wait_for_timeout(1200)
                revealed = True
                break
        except Exception:
            continue
    if not revealed:
        try:
            n = page.evaluate("""() => {
                let n = 0;
                document.querySelectorAll('details').forEach(d => {
                    if (/additional ways to apply/i.test(d.textContent) && !d.open) {
                        d.open = true; n++;
                    }
                });
                return n;
            }""")
            if n:
                page.wait_for_timeout(600)
                revealed = True
        except Exception:
            pass

    html = page.content()
    soup = BeautifulSoup(html, "lxml")
    text = page.inner_text("body")
    ld = _jsonld(soup)
    paths: dict[str, str] = {}

    h1 = soup.find("h1")
    title, paths["title"] = _first(
        ("jsonld", ld.get("title")),
        ("h1", h1.get_text(" ") if h1 else ""),
        ("<title>", re.sub(r"\s*[-|]\s*Job Bank.*$", "", page.title(), flags=re.I)),
    )

    org = ld.get("hiringOrganization") or {}
    org_node = soup.find(attrs={"property": "hiringOrganization"})
    employer, paths["employer"] = _first(
        ("jsonld", org.get("name") if isinstance(org, dict) else org),
        ("property", org_node.get_text(" ") if org_node else ""),
        ("labelled", _labelled(text, "Employer", "Company")),
    )

    loc = (ld.get("jobLocation") or {})
    addr = (loc.get("address") if isinstance(loc, dict) else {}) or {}
    location, paths["location"] = _first(
        ("jsonld", ", ".join(x for x in (addr.get("addressLocality"),
                                         addr.get("addressRegion")) if x)
         if isinstance(addr, dict) else ""),
        ("labelled", _labelled(text, "Location", "Work location")),
    )

    noc_m = NOC_RE.search(text)
    noc, paths["noc"] = _first(
        ("regex", noc_m.group(1) if noc_m else ""),
        ("jsonld", (ld.get("occupationalCategory") or "")),
    )
    noc = (re.search(r"\d{5}", noc).group(0) if re.search(r"\d{5}", noc) else "")

    raw_body, paths["body"] = _body_text(page, soup)
    body = _clean(raw_body)

    # Screening questions — the same over-inclusive extractor the audit uses, so
    # the generator is asked to answer exactly what the audit will demand.
    questions = [" ".join(q.split()) for q in re.findall(r"([^\n?]{10,160}\?)", body)]

    emails = sorted(
        e for e in set(EMAIL_RE.findall(html)) - set(EMAIL_RE.findall(before))
        if not NOISE.match(e))

    rec.update({
        "title": title, "employer": employer, "location": location,
        "noc": noc, "body": body,
        "screening": questions[:8],
        "_extraction_paths": paths,
        "_revealed_additional": revealed,
        "_emails": emails,
        "_body_chars": len(body),
        "_screening_count": len(questions),
    })
    return rec


def usable(rec: dict) -> tuple[bool, str]:
    """A golden-set entry must be complete enough to generate against."""
    if rec.get("fatal") or rec.get("error"):
        return False, rec.get("fatal") or rec["error"]
    for field in ("title", "employer", "body"):
        if not rec.get(field):
            return False, f"missing {field}"
    if rec["_body_chars"] < 400:
        return False, f"body too short ({rec['_body_chars']} chars)"
    return True, ""


def is_dev_role(rec: dict) -> bool:
    return bool(rec.get("noc") in TECH_NOC or TECH_TITLE.search(rec.get("title", "")))


# --------------------------------------------------------------------------- #

POSTING_FIELDS = ("posting_id", "title", "employer", "body",
                  "url", "location", "noc", "queue", "screening")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lmia", type=int, default=15)
    ap.add_argument("--intl", type=int, default=5)
    ap.add_argument("--intl-pages", type=int, default=12,
                    help="developer roles are ~0.4%% of this queue; page deep")
    ap.add_argument("--out", default=str(OUT_DIR))
    args = ap.parse_args()

    if _DEPS_ERROR:
        print(f"missing deps: {_DEPS_ERROR}", file=sys.stderr)
        return 1

    out_dir = Path(args.out)
    if out_dir.exists() and any(out_dir.glob("*.json")):
        print(f"REFUSING: {out_dir} already holds a golden set.\n"
              "A frozen set is only meaningful if it never moves. Harvest a new "
              "one into a new directory with --out instead.", file=sys.stderr)
        return 2
    out_dir.mkdir(parents=True, exist_ok=True)
    REPORT.parent.mkdir(parents=True, exist_ok=True)

    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept-Language": "en-CA,en;q=0.9"})

    print("== LMIA-approved queue (all occupations — D6) ==")
    lmia_ids = collect(s, LMIA, pages=3)
    print(f"\n== International-candidates queue (developer roles only — D6) ==")
    intl_ids = collect(s, INTL, pages=args.intl_pages)

    kept: list[dict] = []
    skipped: list[dict] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent=UA, locale="en-CA",
                                  viewport={"width": 1440, "height": 900})
        page = ctx.new_page()

        def sweep(ids: list[str], queue: str, want: int, dev_only: bool) -> int:
            got = 0
            for pid in ids:
                if got >= want:
                    break
                try:
                    rec = harvest(page, pid, queue)
                except Exception as e:
                    rec = {"posting_id": pid, "queue": queue,
                           "error": f"{type(e).__name__}: {e}"}
                ok, why = usable(rec)
                if ok and dev_only and not is_dev_role(rec):
                    ok, why = False, f"not a developer role ({rec.get('title')!r})"
                if not ok:
                    skipped.append({"posting_id": pid, "queue": queue, "why": why})
                    print(f"  skip {pid}: {why}")
                    if rec.get("fatal"):
                        break
                    time.sleep(random.uniform(1.5, 3.0))
                    continue
                kept.append(rec)
                got += 1
                print(f"  [{got:>2}/{want}] {pid}  {rec['title'][:52]!r} — "
                      f"{rec['employer'][:28]!r}  "
                      f"{rec['_body_chars']}ch  {rec['_screening_count']}q"
                      f"{'  email' if rec['_emails'] else ''}")
                time.sleep(random.uniform(2.0, 4.0))
            return got

        n_lmia = sweep(lmia_ids, "lmia_approved", args.lmia, dev_only=False)
        n_intl = sweep(intl_ids, "international_candidates", args.intl, dev_only=True)

    # ---- write: posting files stay pure, provenance goes in the manifest -- #
    manifest = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "frozen": True,
        "note": ("Immutable. Job Bank postings expire; re-harvesting would make "
                 "two evaluation runs incomparable. Build a NEW set instead."),
        "counts": {"lmia_approved": n_lmia, "international_candidates": n_intl},
        "entries": [],
    }
    for rec in kept:
        posting = {k: rec[k] for k in POSTING_FIELDS if k in rec}
        blob = json.dumps(posting, indent=2, ensure_ascii=False, sort_keys=True)
        (out_dir / f"{rec['posting_id']}.json").write_text(blob + "\n", encoding="utf-8")
        manifest["entries"].append({
            "posting_id": rec["posting_id"],
            "queue": rec["queue"],
            "title": rec["title"],
            "employer": rec["employer"],
            "noc": rec.get("noc", ""),
            "sha256": hashlib.sha256(blob.encode()).hexdigest(),
            "body_chars": rec["_body_chars"],
            "screening_questions": rec["_screening_count"],
            "email_capable": bool(rec["_emails"]),
            "revealed_additional": rec["_revealed_additional"],
            "extraction_paths": rec["_extraction_paths"],
        })
    (out_dir / "MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # Which extraction path actually won, per field — the point of the spike.
    tally: dict[str, dict[str, int]] = {}
    for e in manifest["entries"]:
        for field, path in e["extraction_paths"].items():
            tally.setdefault(field, {}).setdefault(path, 0)
            tally[field][path] += 1

    REPORT.write_text(json.dumps({
        "spike": "06_golden_set",
        "run_at": manifest["captured_at"],
        "kept": len(kept), "skipped": len(skipped),
        "counts": manifest["counts"],
        "extraction_path_tally": tally,
        "email_capable_pct": round(
            100 * sum(e["email_capable"] for e in manifest["entries"])
            / max(len(manifest["entries"]), 1)),
        "with_screening_questions": sum(
            1 for e in manifest["entries"] if e["screening_questions"]),
        "skipped_detail": skipped[:40],
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"\nwrote {len(kept)} postings to {out_dir}")
    print(f"  LMIA {n_lmia}/{args.lmia}   international-dev {n_intl}/{args.intl}")
    print(f"  extraction paths that won: {json.dumps(tally)}")
    if n_lmia < args.lmia or n_intl < args.intl:
        print("  SHORT of target — see skipped_detail in the report", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
