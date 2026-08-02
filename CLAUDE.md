# Northbound — project state

Read this before doing anything else in this repo. It is the portable memory for
this project — like the one in `whisperx-api`, it travels with `git clone`/`git pull`
to any machine.

## What this is

An automated pipeline that finds Canadian job postings from LMIA-approved
employers, generates a **unique, Canadian-format, ATS-safe CV and cover letter for
each one**, sends the application, tracks replies, and shows the whole thing
happening live on a dashboard.

The purpose is immigration to Canada via an LMIA-supported job offer. Gedeon is a
front-end developer with 7 years of experience, currently in Cape Town. The system
applies to **both** software roles and general roles backed by his real documented
work history (painting, warehouse, security, retail, electrical assistance) — the
non-software applications are honest transferable-skills applications, never
inflated claims.

## ▶ RESUME HERE — state as of 2026-08-02

**Where things stand:** planning complete, decisions recorded, five spikes
written **and run against the live site via GitHub Actions**, zero application
code. `main` = working branch.

### The application rule (D6) — read this before touching the matcher

Two queues, **opposite** role filters. Filter on whatever is not already
guaranteed:

| Queue | Postings | Role filter |
|---|---:|---|
| **LMIA-approved** `fskl=101020` | 112 | **NONE — apply to all of them.** Sponsorship is proven; occupation is irrelevant. Farm, greenhouse, labouring, caregiving, butchery all in scope. |
| **International** `fglo=1` | 7,884 | **Developer roles only.** Sponsorship is unproven; slots go to the profession. The 286 painter / 198 construction postings here are deliberately out of scope. |

Initial universe ≈ **147 applications** (~4–5 days of sending). After that this is
a **monitoring** system, not a bulk sender — and for the LMIA queue there is
nothing to rank, because the answer is "all of them".

### Measured facts (spikes 3–5, 2026-08-02, live)

- `sort=M` is **newest-first** — polling page 1 is a valid live feed.
- Search results are **server-rendered**, 25/page, `?page=N`. No browser needed
  for discovery.
- The apply reveal is **two clicks**: `#applynowbutton` ("Show how to apply"),
  then the **"Additional ways to apply"** disclosure. The email is behind the
  *second* one — missing it makes a posting look like Direct Apply only.
- **75%** of LMIA postings are email-capable; address is a plain
  `<a href="mailto:…">`.
- **30%** carry screening questions the employer expects answered in the
  application. The cover letter must answer them explicitly.
- LMIA queue composition: ~70% agriculture, plus physicians, caregivers,
  butchers. **Two** tech roles in the entire facet.
- Job Bank serves GitHub Actions runners fine — HTTP 200, no bot checks.

### CV engine non-negotiables (docs/07)

- **DOCX is primary, PDF is the companion.** DOCX parses at ~97% across ATS
  platforms, PDF at ~72%. Generate DOCX natively; never convert from HTML/PDF.
- **Contact details are body text.** Never a header or footer — many parsers
  never read that region and the application arrives anonymous.
- **7.4 seconds, ~80% on six fields** (name, current title/employer, previous
  title/employer, dates, education). Structure and keyword placement carry the
  first pass, not prose quality.
- **Genericness is the risk, not AI.** 80% of hiring managers reject generic AI
  output; 63% accept genuinely personalised AI-assisted applications. Enforce a
  specificity budget: two concrete particulars per paragraph, minimum.
- **The ATS round-trip test is the highest-value check in the system.** Generate
  → parse → diff. 100% recovery of the six fields or reject.

**Two ways forward. They are independent — neither blocks the other.**

### Path A — validate (needs Gedeon's machine, ~10 min)

The planning container cannot reach `gc.ca` (egress policy: `CONNECT` → 403 at
the proxy, confirmed repeatedly across client stacks; `api.github.com` returns 200
through the same proxy, so it is a policy denial, not a client fault). The spikes
must therefore run on a machine with normal network.

```bash
pip install requests beautifulsoup4 lxml playwright && playwright install chromium
python spikes/03_search_listing.py      # start here — no browser, prints spike 1's command
python spikes/01_fetch_posting.py --url "<url spike 3 prints>" --headed
python spikes/02_inspect_opendata.py
```

Send back `spikes/out/`. That unblocks ingest, matching and contact resolution
(`docs/03`), all of which currently rest on inferences marked `inferred: true` in
`config/sources.yaml`.

### Path B — build the CV engine (blocked on nothing)

**Phase 1 in `docs/05-roadmap.md` does not touch Job Bank at all.** It needs only
`profile/master-profile.yaml` and the Claude API, both available. It is also the
highest-value component — roughly two weeks of the estimate, and the piece whose
output quality decides whether any of the rest matters.

Deliverables: generation contract, claim audit **including the entailment pass**
(`docs/04` — the structural checks alone are not sufficient), both CV tracks,
HTML→PDF render, and a CLI that takes a posting and emits CV + cover letter +
audit report.

Exit test: **10 applications across both tracks that Gedeon would send unedited.**

### Open items on Gedeon

| | |
|---|---|
| Referees | Two current professional referees (Kurtosys / DataBalk). The two on file are 2018 youth-programme contacts. |
| Dates | FootGear and Cumpsty Electric — both `verify: true`, so both currently **excluded** from generated CVs. That leaves Track B with three of five general-work entries and no trades experience. |
| Corrections | AWS/Azure wording on LinkedIn (`https://www.linkedin.com/in/nzemba`) and the portfolio site — they are coursework, not certifications (D1). |
| Optional | TEF Canada booking; Job Bank XML feed request; VPS + SPF/DKIM/DMARC on `gedeonchrist.com`. |

---

## Status: PLANNED, NOT YET VALIDATED. NO APPLICATION CODE.

`docs/` is the plan. `profile/` is the factual foundation. `spikes/` contains two
runnable scripts that check the assumptions the plan rests on.

**Run the spikes before writing application code.** The planning container could
not reach `gc.ca` (network policy refuses `CONNECT`), so two load-bearing claims
were never checked against reality:

1. What clicking **"Show how to apply"** actually does. The whole contact-resolution
   design is built on a step nobody has observed.
2. Whether the open-data CSV is fresh enough to support "monitor for new jobs".
   **Probably not** — it appears to be monthly, against a near-real-time
   requirement. If that holds, live discovery moves to the filtered search pages
   and `docs/03` changes.

Then start at `docs/05-roadmap.md` Phase 1.

**Research confidence is graded** in `docs/00`. Anything grade C is a lead, not a
fact. Nothing in this repo was read from a primary government page.

## Read these in order

| File | What it settles |
|---|---|
| `docs/00-research-findings.md` | Verified facts (1 Aug 2026) with sources. **Do not restate anything here from training-data memory — it is out of date.** |
| `docs/01-immigration-strategy.md` | What the system is actually buying, and the French-language finding that outranks it |
| `docs/02-legal-compliance.md` | Job Bank ToU, CASL, the sanctioned data sources. **Architecture-determining.** |
| `docs/03-architecture.md` | Stack, components, data model, dashboard |
| `docs/04-cv-engine.md` | Generation contract, Canadian format rules, the two tracks |
| `docs/05-roadmap.md` | Phased delivery |
| `docs/06-decisions.md` | **Settled decisions — don't re-litigate these** |
| `docs/07-cv-engine-research.md` | **Research behind the CV engine. Read before touching generation or rendering.** |
| `profile/master-profile.yaml` | **Single source of truth for every generated document** |
| `profile/PROFILE-GAPS.md` | What must be confirmed before mass sending |

## The four things that must never be broken

1. **No invented claims.** The CV engine may only assert what is in
   `master-profile.yaml`, every bullet cites an `id`, and the post-generation
   audit blocks on any violation. An LMIA application is a government process with
   fraud investigators attached to it — the programme was reformed in 2025
   *because* of misrepresentation. See `docs/04-cv-engine.md`.

2. **No logged-in Job Bank automation, ever.** No Job Bank account, no Direct
   Apply automation, no stored credentials — hard constraint in code.
   *Discovery* runs on sanctioned sources (open.canada.ca CSV, the Job Bank XML
   partner feed, the TFWP positive-LMIA list) — nothing crawls Job Bank to find
   jobs. *Apply-detail retrieval* — loading a queued posting and clicking "Show
   how to apply" to read the employer's email — **runs by default** (decision D5,
   made by Gedeon with the ToU trade-off on the table; don't re-litigate it).
   Logged out, one at a time, human-paced, circuit-broken on 403/429/CAPTCHA.
   See `docs/02-legal-compliance.md` and `docs/06-decisions.md`.

3. **Never send from `nzemba48@gmail.com`.** Own domain (`gedeonchrist.com`) with
   SPF/DKIM/DMARC, hard-capped at 30–40 sends/day after a warm-up ramp. Losing
   the primary mailbox mid-campaign would be worse than sending nothing.

4. **Optimise for replies, not sends.** Applications-sent is a vanity metric.

## Facts that changed since the model's training data

- **Arranged-employment CRS points were removed on 25 March 2025.** An LMIA job
  offer is worth **zero** Express Entry points. It is still the entry ticket —
  work permit → Canadian experience → CEC / PNP (+600 for a nomination) — but the
  mechanism is different from what most guidance online still assumes.
- **2026 TFWP is tighter**: admissions cut to 60,000; low-wage LMIAs not processed
  in CMAs with unemployment ≥ 6%; 8-week advertising requirement from 1 Apr 2026;
  wage thresholds = provincial median + 20% from 17 Jul 2026. The squeeze is on
  the *low-wage* stream — where the general-work applications sit. High-wage
  (TEER 1 web developer) is far less affected.
- **French-language Express Entry rounds in 2026 cut off at CRS 379–446** vs
  ~514–525 for general rounds. Gedeon's home language is French. This is the
  highest-leverage fact in the entire project and it costs a test booking.

## Machine setup (per machine, not in git)

1. `secrets/identity.local.yaml` — RSA ID, passport, street address. **Gitignored.
   Never commit. Never put in a generated CV** (Canadian CVs must not carry them).
2. `.env` — `ANTHROPIC_API_KEY`, Postgres URL, SMTP + IMAP credentials for
   `gedeonchrist.com`.
3. `docker compose up` — Postgres + backend + frontend.

## Conventions

- Canadian English in every generated document (*colour, behaviour, centre, licence*).
- Model: `claude-opus-5`. Thinking is on by default on this model and `max_tokens`
  caps thinking + output together — leave headroom. Use structured outputs
  (`messages.parse()`), not prose parsing; assistant prefill 400s. Put the
  `cache_control` breakpoint at the end of the profile block and keep the posting
  after it.
- The `events` table is append-only and is both the audit trail and the dashboard
  feed. If it didn't emit an event, it didn't happen.
