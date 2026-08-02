# Spikes — run these before trusting the architecture

Two load-bearing assumptions in `docs/03-architecture.md` have never been checked
against reality, because the container this project was planned in cannot reach
`gc.ca` (the network policy refuses `CONNECT` — a `000`, not a site error).

Until these run, the contact-resolution and discovery designs are **hypotheses
written in confident prose**. That's a real weakness in the plan, not a formality.

## Run them on your own machine

**Start with spike 3** — it needs no browser, takes seconds, and prints the exact
command for spike 1 with a real posting URL already filled in.

```bash
pip install requests beautifulsoup4 lxml playwright && playwright install chromium

# 3. The two search URLs. No browser needed.
python spikes/03_search_listing.py

# 1. Then a real posting — spike 3 prints this command for you with a live URL.
python spikes/01_fetch_posting.py --url "<url spike 3 printed>" --headed

# 2. Independent, run any time.
python spikes/02_inspect_opendata.py
```

Then send back the whole `spikes/out/` directory.

## What each one decides

### Spike 1 — "Show how to apply"

| Question | Why the answer changes the build |
|---|---|
| Is the reveal a navigation, an AJAX call, or already in the DOM? | If the content ships with the page, **no browser is needed at all** — a plain HTTP GET does it, which is faster, cheaper and far less conspicuous than driving Chromium. If it's AJAX, we call that endpoint directly. Only a true navigation needs the heavier path. |
| What is the stable selector? | Everything in `contact/` depends on it. |
| Which methods appear, and how are they marked up? | Decides the parser, and how many postings are email-capable at all. |
| Is the email a `mailto:`, plain text, or obfuscated? | Obfuscation would mean this is a deliberate anti-harvesting measure — which is information worth having before building on top of it. |
| Any CAPTCHA / rate limiting / consent wall? | Decides whether the throttling design is adequate or naive. |

The script **stops on the first stop-signal** rather than retrying. If Job Bank
pushes back, that's an answer, not an obstacle.

### Spike 2 — the open-data CSV

| Claim | If it fails |
|---|---|
| **C1 — fresh enough to monitor** | This is the one likely to fail. You asked for monitoring of newly posted jobs; the dataset appears to be monthly. If the newest row is weeks old, the open-data discovery layer **cannot meet your requirement** and `docs/03` needs rewriting around either the XML feed or polling the search pages. |
| **C2 — has an LMIA / foreign-candidate signal** | The Stage 1 "LMIA employers only" filter has no basis in this source and must come from the filtered search URL or the XML feed instead. |
| **C3 — has NOC, wage, employer, location** | Ranking would have to be derived from the posting page itself, making spike 1's path the primary source rather than a supplement. |

### Spike 3 — the two search URLs

Added 2026-08-02, once Gedeon supplied the actual queries (`config/sources.yaml`).
It is now the **most decisive** of the three.

| Question | Why it matters |
|---|---|
| **Does `sort=M` mean newest-first?** | If yes, polling page 1 of each search is the live feed, and the monitoring requirement is solved by two page loads an hour. This single answer decides whether the discovery architecture is right. |
| Server-rendered or JS-assembled? | Server-rendered means no browser in production — cheaper, faster, less conspicuous. |
| Posting-URL / ID pattern | The dedup key the whole state machine turns on. |
| What's on the result card? | Every field readable from the listing is one we never open a posting for — directly reduces how often we touch the site. |
| Do the facet label words still appear? | `fskl=101020` is an internal code. If it silently changes meaning, the query still returns results — just the wrong ones. This is the guard against that. |

## What I expect to find

Predictions on record, so the spikes can falsify something rather than be read as
confirmation:

1. **Spike 2's freshness check fails**, and the open-data CSV is demoted from
   discovery layer to backfill. *(Already acted on — `docs/03` now treats search
   polling as the live feed. If spike 2 surprises us and the CSV turns out to be
   near-daily, that decision gets revisited.)*
2. **`sort=M` is newest-first.** The `M` and the fact that Gedeon uses these URLs
   to spot new postings both point that way. If it turns out to mean relevance or
   match, monitoring needs a different sort value and spike 3 will surface it.
3. **Spike 1 shows AJAX or already-in-DOM**, not a navigation. Either drops
   Playwright from the production path.
4. **A meaningful share of postings are not email-apply.** Above roughly a third
   and the `non_email` manual queue is a main workflow rather than an edge case,
   and the dashboard has to treat it as one.

Where the results contradict these, the plan changes. That is the point.
