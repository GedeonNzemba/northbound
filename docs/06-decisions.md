# 06 — Decision log

Settled decisions. Each one closes a question rather than leaving it to be
re-litigated during implementation. Add to the bottom; don't rewrite history.

---

## D1 — IT Academy items are coursework, not certifications
**Decided 2026-08-01 by Gedeon.** Status: settled.

He did **not** sit the AWS (DVA-C01), Microsoft (AZ-900/203/204/400, 70-357/480/
483/486/487/761, MTA 98-361/98-364), Oracle (1Z0-808/809) or ISTQB proctored
exams. The IT Academy certificates record course completion.

**Consequences:**
- `master-profile.yaml` renders every one of these under
  `certifications.coursework_completed` with `render_as: coursework`.
- The only independently verifiable credential on file is the **freeCodeCamp
  Responsive Web Design certification** (June 2019, with a public verify URL).
- Claim-audit rule 4 (`docs/04-cv-engine.md`) **rejects** any generation that
  states a coursework item as a held credential. This is a hard block, not a
  warning.
- The current CV (`profile/source-documents/CV-current-2026.pdf`) says
  *"earning certifications in AWS (Developer Associate) and Microsoft Azure
  (including AZ-204, AZ-400, AZ-900)"*. **That wording is inaccurate and must be
  corrected in any copy still in circulation** — LinkedIn, the portfolio site,
  and any CV already sent to an employer.

**Why this matters more than it looks.** A Canadian employer that checks AWS's
credential verifier and finds nothing does not conclude "administrative error".
Under a Temporary Foreign Worker Program that was reformed in 2025 specifically
because of misrepresentation, a finding of misrepresentation is not a rejected
application — it carries a multi-year bar. Correct coursework framing costs
nothing: two-plus years of structured study across cloud, backend, testing and
mobile is a genuinely strong story on its own.

---

## D2 — Trust ramp, not day-one full autonomy
**Decided 2026-08-01 by Gedeon.** Status: settled. Implements as roadmap phase 5.

The end state is fully hands-off. The path there is earned rather than assumed.

**Mechanism:**
- Approval gate **on** by default when sending goes live (phase 4).
- Auto-send unlocks **per category** — keyed on `(track, NOC family)` — after
  **N consecutive approvals with zero edits** in that category. Start `N = 10`,
  configurable.
- Any edit to a generated document, or any rejection, **resets that category's
  counter to zero**.
- A claim-audit failure resets the counter **and** re-locks the category.
- The dashboard shows each category's unlock progress explicitly, so autonomy is
  something Gedeon watches accumulate rather than a setting he has to trust.

Track A (front-end, NOC 21234) will almost certainly unlock first and fastest.
Track B (transferable-skills applications) will take longer, which is the right
outcome — those documents carry more judgment and more risk.

---

## D3 — Deploy to a small VPS
**Decided 2026-08-01 by Gedeon.** Status: settled.

Hetzner CX22 or equivalent, ~€5/month, Docker Compose: Postgres + FastAPI backend
+ built React frontend + Caddy for TLS.

**Why not Modal**, despite the existing account and credits: this workload needs a
persistent IMAP IDLE connection, a long-lived scheduler, and a dashboard that is
up whenever it's opened. Scale-to-zero fights all three. A fixed VPS also gives a
**stable outbound IP**, which materially helps email reputation during the warm-up
ramp. Modal remains the right answer for `whisperx-api` — different workload shape,
different tool.

**Follow-on setup:**
- DNS on `gedeonchrist.com`: SPF, DKIM, DMARC (`p=none` minimum) — start early,
  propagation and reputation both take time.
- Daily `pg_dump` off-box. The application history *is* the product; losing it
  means losing every reply thread and every outcome measurement.
- Dashboard behind auth. It contains PII and a live view of his immigration
  strategy.

---

## D4 — Discovery runs on sanctioned sources
**Decided 2026-08-01 during planning.** Status: settled. Rationale in
`docs/02-legal-compliance.md`.

Job Bank's Terms of Use prohibit automated access. **Discovery** — the bulk-data
layer — therefore runs on open.canada.ca's job-postings CSV, the Job Bank XML
partner feed (once granted), and the TFWP positive-LMIA employers list. Nothing
crawls Job Bank to find jobs.

**No Job Bank account. No Direct Apply automation. No stored Job Bank
credentials.** This is a hard constraint in code, not a configuration default.

Superseded in part by **D5** on how apply details are retrieved.

---

## D6 — Opposite role filters on the two queues
**Decided 2026-08-02 by Gedeon.** Status: settled. Supersedes every earlier
tech/general percentage split in `docs/01`.

| Queue | Role filter | Why |
|---|---|---|
| **LMIA-approved** (`fskl=101020`, 112 postings) | **None — apply to everything** | Sponsorship is proven; role fit is the variable |
| **International** (`fglo=1`, 7,884 postings) | **Developer roles only** | Role fit is achievable; sponsorship is unproven |

**The principle: in each queue, filter on whatever is not already guaranteed.**

An employer in the LMIA facet has paid the fee, run the recruitment and waited
out the decision. That willingness is rarer and harder to find than a matching
job title, so occupation is not a reason to skip one — farm work, greenhouse,
labouring, caregiving and butchery are all in scope. Only hard blockers exclude a
posting (unattainable licence, driver's licence, existing work authorisation
required, closed).

An employer in the international facet has shown only that they will read an
application from abroad. A general-labour application there carries neither
sponsorship nor role fit, so those slots go to Gedeon's actual profession. The
286 painter and 198 construction-labourer postings in that facet are
**deliberately out of scope** despite being the largest categories in it.

**This replaces the percentage-split framing entirely.** There is no 60/40, 85/15
or any other ratio — the split is an emergent consequence of two per-queue rules,
and it will land wherever the postings land.

**Operational consequence:** the initial universe is ~147 applications (112 + ~35),
about four to five days of sending. After that this is a **monitoring** system,
not a bulk sender. It also means the ranking layer matters far less than
`docs/03` assumed: for the LMIA queue there is nothing to rank, because the
answer is "all of them".

---

## D5 — Per-posting apply-detail retrieval is the default path
**Decided 2026-08-01 by Gedeon.** Status: settled. Supersedes the off-by-default
position in D4.

On Job Bank, the application method is behind the **"Show how to apply"** button
on the posting. That reveal is the only place the employer's email exists — the
open-data CSV does not carry it. A system that cannot read it cannot send an
application, which is the entire purpose of the project.

The trade-off was put to Gedeon explicitly (Job Bank's ToU prohibit automated
access — `docs/00-research-findings.md` F1) and he confirmed the approach twice.
**It runs by default.** Recorded here so it is not re-litigated during
implementation.

**Retained regardless, as engineering rather than ceremony:**
- Only postings already queued for application are fetched — tens per day.
- Logged out, concurrency of one, human-paced with jitter.
- Honest user agent. No fingerprint spoofing, no proxy rotation, no CAPTCHA
  solvers — those are what turn a soft block into a permanent one.
- Circuit breaker on any 403/429/CAPTCHA: halt, alert, manual reset.
- Manual paste fallback for any posting where retrieval fails.

The failure this guards against is Gedeon's own access being cut off partway
through a campaign — a practical risk to him, not an abstract one.

**Scope note:** the parser handles every method Job Bank offers (email, online,
in person, mail, fax, phone, Direct Apply). Non-email postings are recorded as
`contact_source = 'non_email'`, excluded from automated sending, and surfaced for
manual handling — never silently dropped.
