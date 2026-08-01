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

## Status: PLANNING COMPLETE, NO CODE YET

`docs/` is the plan. `profile/` is the factual foundation. Nothing has been built.
Start at `docs/05-roadmap.md` Phase 1.

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
