# 03 — System architecture

Design goals, in priority order:

1. **Never send something false.** Every generated document traces to `master-profile.yaml`.
2. **Never lose state.** A crash mid-campaign must not re-send 200 applications.
3. **Always visible.** Gedeon must be able to watch it work, not infer it from logs.
4. **Never get the sending address burned.** Reputation is the scarce resource.
5. Compliant by default (`docs/02-legal-compliance.md`).

---

## Stack

| Layer | Choice | Why this and not the alternative |
|---|---|---|
| Backend | **Python 3.12 + FastAPI** | Same stack as `whisperx-api` — no new runtime to learn, and the WebSocket-driven live dashboard pattern is already proven there. |
| Database | **PostgreSQL 16** | JSONB for raw posting payloads, real transactions for the application state machine, full-text search over descriptions. SQLite would work for phase 1 but the ingest + worker + API concurrency is exactly where it starts hurting. |
| Queue / scheduling | **APScheduler + a `jobs` table** | Volume is tens of emails and thousands of postings a day. Celery + Redis is two more moving parts for no benefit at this size. The `jobs` table gives durable, inspectable, restartable work. |
| Browser automation | **Playwright (Chromium)** | Only used in assisted-apply mode. Already available in the environment. |
| Document rendering | **HTML → PDF via WeasyPrint** | Deterministic, no headless-browser dependency in the render path, and single-column ATS-safe HTML is exactly what WeasyPrint does well. |
| LLM | **Claude API — `claude-opus-5`** | See below. |
| Frontend | **React 19 + TypeScript + Vite + Tailwind** | Gedeon's home turf. This is the part he should enjoy building. |
| Live updates | **WebSocket (`/ws/events`)** | Same pattern as `whisperx-api`'s `/ws/stt`. |
| Email out | **SMTP on his own domain** (`gedeonchrist.com`) | See email section. |
| Email in | **IMAP IDLE** | Reply detection is what turns "sent 300" into "3 employers are talking to me". |
| Hosting | **One small VPS + Docker Compose** | Needs to be always-on for IMAP IDLE and the dashboard. Serverless scale-to-zero is the wrong shape here — see below. |

### On hosting

Modal is excellent for the whisperx workload (bursty GPU, scale-to-zero) and wrong for this one: this system needs a persistent IMAP connection, a long-lived scheduler, and a dashboard that is up when Gedeon opens it. A €4–5/month VPS (Hetzner CX22 or equivalent) running Docker Compose is simpler, cheaper at this duty cycle, and gives a stable outbound IP — which matters for email reputation. Modal stays the right answer for whisperx; they are different problems.

### On the LLM

Verified against the Claude API reference on 2026-08-01:

| Model | Input / Output per MTok | Use here |
|---|---|---|
| `claude-opus-5` | $5 / $25 | **CV and cover-letter generation** — the quality-critical path, and the one where a bad output costs an opportunity that cannot be recovered. |
| `claude-sonnet-5` | $3 / $15 | Optional cost lever for bulk relevance scoring if volume ever justifies it. Not the default. |

Implementation notes that are easy to get wrong:

- **Thinking is on by default on `claude-opus-5`** — omitting the `thinking` parameter runs adaptive thinking, and `max_tokens` caps thinking *plus* response text together. Size `max_tokens` with headroom (start at 16000 for generation) or responses truncate mid-document.
- **Structured outputs, not prose parsing.** Use `client.messages.parse()` with a Pydantic model so the generator returns a typed CV object, never a blob of markdown to regex. Assistant prefill returns a 400 on this model — structured outputs are the replacement.
- **Prompt caching pays for itself immediately.** `master-profile.yaml` is a large, byte-stable prefix reused on every single generation. Put a `cache_control: {"type": "ephemeral"}` breakpoint at the end of it; cache reads cost ~0.1× input. The minimum cacheable prefix on `claude-opus-5` is 512 tokens — the profile is far above that. Keep the volatile part (the specific job posting) strictly *after* the breakpoint, and never interpolate a timestamp into the system prompt.
- **Batch API for bulk scoring** — 50% off, results within an hour. Relevance scoring of a night's ingest is exactly the right shape for it. Keep generation on the live API.

Rough cost: ~30 tailored applications/day at ~15K input (mostly cached) + ~4K output ≈ **well under $2/day**. Not the constraint.

---

## Component map

```
                      ┌──────────────────────────────────────────┐
                      │  SOURCES                                 │
                      │  • open.canada.ca job-postings CSV       │
                      │  • Job Bank XML feed (once granted)      │
                      │  • TFWP positive-LMIA employer list      │
                      │  • ESDC refusal-to-process CMA list      │
                      └────────────────┬─────────────────────────┘
                                       │
                            ┌──────────▼──────────┐
                            │  ingest/            │  normalise → dedupe →
                            │  (scheduled)        │  NOC map → upsert
                            └──────────┬──────────┘
                                       │
                            ┌──────────▼──────────┐
                            │  match/             │  hard filters → LLM
                            │  (scored, batched)  │  relevance score + rationale
                            └──────────┬──────────┘
                                       │
        ┌──────────────────────────────▼──────────────────────────────┐
        │  APPLICATION STATE MACHINE  (one row per job × attempt)      │
        │                                                             │
        │  DISCOVERED → SCORED → QUEUED → CONTACT_RESOLVED →           │
        │  DOCS_GENERATED → [REVIEW] → SENT → REPLIED → OUTCOME        │
        │           └────────────► SKIPPED / FAILED / SUPPRESSED       │
        └──────┬──────────────────┬───────────────────┬───────────────┘
               │                  │                   │
     ┌─────────▼────────┐ ┌───────▼────────┐ ┌────────▼─────────┐
     │ contact/         │ │ generate/      │ │ send/            │
     │ • open data      │ │ • CV (opus-5)  │ │ • SMTP, throttled│
     │ • assisted fetch │ │ • cover letter │ │ • suppression    │
     │   (opt-in)       │ │ • PDF render   │ │ • warm-up ramp   │
     │ • manual paste   │ │ • claim audit  │ └────────┬─────────┘
     └──────────────────┘ └────────────────┘          │
                                              ┌───────▼────────┐
                                              │ inbox/         │
                                              │ IMAP IDLE →    │
                                              │ classify reply │
                                              └───────┬────────┘
                                                      │
     ┌────────────────────────────────────────────────▼─────────────┐
     │  FastAPI  ──  REST + /ws/events  ──►  React dashboard         │
     └──────────────────────────────────────────────────────────────┘
```

Every stage writes an immutable row to `events`. The dashboard is a projection of that table — which means the live view and the audit trail are the same thing, and there is no way for the UI to show something the system didn't actually do.

---

## Matching

Two-stage, because LLM-scoring every posting in the country is wasteful and slow.

**Stage 1 — deterministic filters (SQL, free, instant).** Drops the great majority.
- Employer must be recruiting foreign candidates / LMIA-linked, or corroborated in the positive-LMIA list.
- Occupation must be in the configured NOC allowlist (tech codes + the general-work codes backed by real documented experience — see `master-profile.yaml`).
- Hard blockers: requires a Canadian licence/certification Gedeon cannot hold, requires a driver's licence he does not have, requires existing Canadian work authorisation, closing date passed.
- Low-wage postings in a CMA currently on the refusal-to-process list are **de-prioritised, not dropped** — the employer may still be recruiting, but they cannot get an LMIA there this quarter.
- Never applied to this employer + NOC within N days.

**Stage 2 — LLM relevance scoring (`claude-opus-5`, batched).** Returns a typed object:

```python
class Score(BaseModel):
    fit: int                      # 0-100
    track: Literal["direct", "transferable"]
    matched_evidence_ids: list[str]   # ids from master-profile.yaml
    blockers: list[str]
    rationale: str                # one paragraph, shown in the dashboard
```

`track` is the important field: it decides which CV template and which cover-letter register the generator uses. `matched_evidence_ids` is the anti-hallucination hook — the scorer must name the profile entries it is relying on, and the generator is later restricted to that set plus the core profile.

---

## Contact resolution

Three sources, in order, per `docs/02-legal-compliance.md`:

1. **Structured data** — whatever the feed/CSV carries.
2. **Assisted fetch** (opt-in, off by default) — one logged-out, human-paced, robots-respecting request for a posting already queued for application. Circuit-breaks on any 403/429/CAPTCHA.
3. **Manual** — the dashboard surfaces the posting with an "open posting" button and a paste field. Two seconds of Gedeon's time, zero ambiguity.

Resolved addresses are validated (MX lookup, syntax, role-account detection) before anything is generated — no point spending a generation on an address that will bounce.

---

## Sending

This is where the project most plausibly destroys itself, so the constraints are hard-coded rather than configurable:

- **Own domain only.** `gedeonchrist.com` with SPF, DKIM and DMARC (`p=none` minimum). Never `nzemba48@gmail.com` — losing that mailbox mid-campaign would be worse than sending nothing.
- **Warm-up ramp.** Day 1–3: 5/day. Week 1: 10/day. Week 2: 20/day. Steady state: **30–40/day maximum.** Practitioner guidance for cold outreach is ~25 per inbox per day, an order of magnitude below the formal cap, because the cap is not what triggers suspension — reputation is.
- **Human-shaped timing.** Sends spread across Canadian business hours in the posting's own timezone, randomised gaps, nothing on weekends by default.
- **One recipient per message.** Never CC, never BCC.
- **Suppression list**, checked before every send, permanent, no override.
- **Bounce handling** — hard bounce suppresses the address and flags the employer record.
- **No tracking pixels, no link wrapping.** See `docs/02-legal-compliance.md` Rule 4.

Every one of these is a first-class system property with a test, not a config default someone can quietly raise.

---

## Data model (core tables)

```sql
employers          id, name, normalized_name, city, province, noc_codes[],
                   lmia_corroborated bool, lmia_last_seen_quarter,
                   suppressed bool, notes

postings           id, source, source_ref, employer_id, title, noc_2021, teer,
                   city, province, cma, wage_low, wage_high, wage_unit,
                   wage_stream ('high'|'low'|'unknown'),
                   posted_at, closes_at, raw jsonb, content_hash, first_seen, last_seen

applications       id, posting_id, state, track, fit_score, rationale,
                   contact_email, contact_source,
                   cv_path, cover_letter_path, generation_id,
                   queued_at, sent_at, message_id, thread_id,
                   replied_at, outcome, outcome_notes

generations        id, application_id, model, prompt_hash, input_tokens,
                   output_tokens, cached_tokens, evidence_ids[],
                   claim_audit jsonb, created_at

events             id, ts, application_id, employer_id, kind, level, payload jsonb
                   -- the append-only spine: audit trail AND dashboard feed

suppression        email, reason, created_at
send_budget        date, sent_count, cap
```

`postings.content_hash` over the meaningful fields is what makes "is this a genuinely new posting or the same one re-listed?" answerable — which matters, because re-applying to a repost looks careless.

---

## The dashboard

Not a progress bar. The point is that Gedeon can see the machine thinking.

- **Live activity stream** (WebSocket) — every event as it happens: *"Scored: Junior Front-End Developer @ Coastal Digital, Halifax NS — fit 84, direct track"*, *"Generated CV (3.1s, 12,400 cached tokens)"*, *"Sent to careers@… — 18/30 today"*.
- **Pipeline board** — columns for each state, cards move between them live.
- **Today** — sent vs cap, remaining budget, next scheduled send, ingest freshness per source.
- **Application detail** — the posting, the fit rationale, the generated CV rendered inline next to the source profile entries it drew on, the exact email body, the thread.
- **Replies** — the inbox view. This is the screen that matters; everything else is machinery.
- **Analytics** — reply rate by NOC family, by province, by track, by template version. This is what turns the 60/40 split in `docs/01-immigration-strategy.md` from a guess into a measurement.
- **Health** — source freshness, send-budget consumption, bounce rate, circuit-breaker state, API spend today.

Dark operations panels, light content cards — the same visual language as the whisperx dashboard, so the two systems feel like one person's work.

---

## Repository layout

```
northbound/
├── docs/                    # this planning set
├── profile/                 # master-profile.yaml + source documents
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI, /ws/events
│   │   ├── config.py
│   │   ├── db/                  # models, migrations (alembic)
│   │   ├── ingest/              # opendata.py, jobbank_feed.py, lmia_list.py
│   │   ├── match/               # filters.py, scorer.py
│   │   ├── contact/             # resolver.py, assisted.py, validate.py
│   │   ├── generate/            # cv.py, cover_letter.py, render.py, audit.py
│   │   ├── send/                # smtp.py, throttle.py, suppression.py
│   │   ├── inbox/               # imap.py, classify.py
│   │   ├── templates/           # cv/*.html, letters/*.jinja
│   │   └── events.py            # the append-only spine
│   └── tests/
├── frontend/                # React + Vite + Tailwind
├── docker-compose.yml
└── .env.example
```

---

## Failure modes that must not be silent

| Failure | Handling |
|---|---|
| Source feed changes shape | Schema validation on ingest; refuse to write malformed rows; dashboard flags stale source. |
| Assisted fetch hits 403/429/CAPTCHA | Circuit breaker halts retrieval, alerts, requires manual reset. Never retries harder. |
| SMTP bounce | Suppress address, flag employer, surface on dashboard. |
| Claim-audit failure on a generated CV | Application blocked in `DOCS_GENERATED`, never auto-sent, surfaced for review. |
| Send budget exhausted | Queue holds; no burst tomorrow — the ramp is a rate, not a quota to catch up on. |
| Duplicate application to same employer+NOC | Blocked at the state machine, logged, visible. |
| API spend spike | Daily spend cap; generation pauses and alerts rather than running up a bill. |
