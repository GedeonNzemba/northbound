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

Job Bank's Terms of Use prohibit automated access. Discovery therefore runs on
open.canada.ca's job-postings CSV, the Job Bank XML partner feed (once granted),
and the TFWP positive-LMIA employers list. Per-posting apply-detail retrieval is
opt-in, off by default, logged-out, rate-limited and robots-respecting, with a
manual copy-paste alternative that is always available.

**No Job Bank account. No Direct Apply automation. No stored Job Bank
credentials.** This is a hard constraint in code, not a configuration default.
