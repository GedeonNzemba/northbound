# 05 — Delivery roadmap

Sequenced so that **something useful exists after phase 1** and every phase after
that is an increment on a working system. Nothing here requires the whole thing to
be finished before the first application goes out.

Phases are ordered by dependency, not by calendar. Actual pace depends on how much
time Gedeon has.

---

## Phase 0 — Do these first, outside the software

These are higher expected value than any code in this repo and they are not
blocked by it.

| # | Action | Why now |
|---|---|---|
| 0.1 | **Book TEF Canada / TCF Canada.** | `docs/01-immigration-strategy.md`. French draws in 2026 have cut off at CRS 379–446 vs ~514–525 general. Native French speaker. Nothing else in this project comes close to that leverage. |
| 0.2 | **Book IELTS General or CELPIP.** | Required for Express Entry regardless of route, and required to claim the French + English combination bonus. |
| 0.3 | **Request Job Bank XML feed access.** | Converts the riskiest component of the system into a sanctioned integration. One email. Do it in week 1 so the answer arrives before the ingest layer is finished. |
| 0.4 | **Close the blocking profile gaps.** | `profile/PROFILE-GAPS.md` items 1–4: certification wording, two current referees, the Eat Creative / UCOOK overlap, and dates for FootGear and Cumpsty Electric. The generator excludes anything still flagged, so these directly limit output quality. |
| 0.5 | **Buy the VPS, set up DNS.** | SPF, DKIM and DMARC on `gedeonchrist.com` need time to propagate and the sending reputation needs time to warm. Starting this early costs nothing. |

---

## Phase 1 — Manual loop, real applications

**Goal: Gedeon sends genuinely tailored applications, chosen by the system, this
week.** No ingest automation, no send automation. Prove the document quality
first, because everything downstream is worthless if the CVs aren't good.

- `master-profile.yaml` finalised (gaps 1–4 closed).
- CV engine: generation contract, claim audit, both tracks, HTML→PDF render.
- CLI: `northbound generate --posting <url-or-file>` → CV + cover letter + the
  claim-audit report.
- Postgres schema and the `events` spine.

**Exit criteria:** 10 applications generated across both tracks. Every one read
end-to-end by Gedeon. Zero audit failures. He would send all ten without editing.

If the Track B documents don't read well, **stop and fix them here.** That is
what phase 1 is for.

---

## Phase 2 — Ingest and matching

- Open-data CSV ingest, monthly refresh, normalisation, dedupe by content hash.
- TFWP positive-LMIA employer list cross-reference.
- ESDC refusal-to-process CMA list, applied as the low-wage de-prioritisation
  signal.
- NOC 2021 mapping table.
- Stage 1 deterministic filters; stage 2 LLM scoring via the Batch API.
- Job Bank XML feed ingest if 0.3 was granted.

**Exit criteria:** an overnight run produces a ranked queue Gedeon agrees with.
Concretely: he reviews the top 20 and would apply to at least 15 of them.

---

## Phase 3 — Dashboard

Deliberately before send automation. Nothing should start sending on its own
before he can watch it.

- FastAPI REST + `/ws/events`.
- React dashboard: live activity stream, pipeline board, application detail with
  the generated CV shown next to the profile entries it cited, health panel.
- Manual "resolve contact" and "approve & send" actions.

**Exit criteria:** he can run a full day's applications from the dashboard without
touching a terminal.

---

## Phase 4 — Sending, on a leash

- SMTP with SPF/DKIM/DMARC verified end-to-end (test to a Gmail address and read
  the raw headers).
- Throttle, warm-up ramp, business-hours scheduling, suppression list, bounce
  handling.
- IMAP IDLE reply detection and classification.
- Contact resolution: structured → assisted (opt-in, off) → manual.
- **Approval gate on by default.** Every application waits for one click.

**Exit criteria:** 50 applications sent. Zero bounces from address errors, zero
spam placements, zero duplicates. Replies land in the dashboard correctly.

---

## Phase 5 — Autonomy

Only after phase 4 has run clean for two weeks.

- **Trust ramp**, not a switch. Auto-send unlocks per track and per NOC family
  only after N consecutive approvals with no edits in that category — so the
  system earns autonomy where it has demonstrated it, and keeps asking where it
  hasn't. Track A will unlock long before Track B, which is correct.
- Continuous monitoring: new postings polled on a schedule, high-fit matches
  surfaced immediately.
- Push notification on any employer reply.
- Analytics: reply rate by NOC family, province, track and template version —
  which turns the 60/40 weighting in `docs/01-immigration-strategy.md` into a
  measurement rather than an assumption.
- Weekly digest.

**Exit criteria:** a week passes in which the system runs unattended, Gedeon only
opens the dashboard to read replies, and the numbers are right.

---

## Explicitly not in scope yet

Named so they don't creep in:

- Multi-user / SaaS. The user has said this could become a product. It might.
  Building for that now would compromise the thing that has to work first, and
  multi-tenancy raises real PIPEDA questions that need proper advice rather than
  assumptions.
- LinkedIn / Indeed / Workopolis ingest. Different terms, different anti-bot
  posture, one problem at a time.
- Auto-filling employer ATS web forms. High breakage, low trust, and the
  boundary between assisting and impersonating gets thin.
- Interview scheduling and follow-up sequences. Worth doing once replies exist.
  Not before.

---

## What "it worked" means

Success is **one LMIA-supported job offer**. Not applications sent — that number
is a vanity metric and optimising for it is how this kind of system goes wrong.

Leading indicators, in order of how much they actually tell you:

1. Employer replies that are not rejections
2. Interview requests
3. Reply rate by occupation family (which is what tells you where to spend the
   next hundred applications)
4. Applications sent

And the honest framing from `docs/01-immigration-strategy.md`: hundreds of
applications producing a handful of real conversations is a **working** outcome
for cold cross-border applications, not a failing one.
