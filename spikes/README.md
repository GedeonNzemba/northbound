# Spikes — run these before trusting the architecture

Two load-bearing assumptions in `docs/03-architecture.md` have never been checked
against reality, because the container this project was planned in cannot reach
`gc.ca` (the network policy refuses `CONNECT` — a `000`, not a site error).

Until these run, the contact-resolution and discovery designs are **hypotheses
written in confident prose**. That's a real weakness in the plan, not a formality.

## Run them on your own machine

```bash
pip install playwright requests && playwright install chromium

# 1. The one that matters most. Any single Job Bank posting URL.
python spikes/01_fetch_posting.py --url "https://www.jobbank.gc.ca/jobsearch/jobposting/XXXXXXX"

# watch it happen the first time
python spikes/01_fetch_posting.py --url "..." --headed

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

## What I expect to find

Stating predictions up front so the spikes can actually falsify something,
rather than being read to confirm what's already written:

1. **C1 fails.** Monthly open data cannot support "tell me about new jobs." The
   likely correction is: open data becomes a *backfill and employer-corroboration*
   source, and live discovery moves to the filtered search pages — which makes
   the fetch path in D5 central to discovery too, not just to contact resolution.
2. **Spike 1 shows AJAX or already-in-DOM**, not navigation. Either would let us
   drop Playwright from the production path entirely.
3. **A meaningful share of postings are not email-apply.** If it's above roughly
   a third, the `non_email` manual queue is a main workflow rather than an edge
   case, and the dashboard needs to treat it as such.

If the results contradict these, the plan changes — that's the point of running
them before writing code.
