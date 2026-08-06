# 05 — Delivery roadmap

Sequenced so that **something useful exists after phase 1** and every phase after
that is an increment on a working system. Nothing here requires the whole thing to
be finished before the first application goes out.

## How long this actually takes

This should have been in the first version of this document and wasn't. Estimates
assume Gedeon working evenings and weekends around a full-time job, with me doing
the bulk of the implementation.

| Phase | What it delivers | Estimate |
|---|---|---|
| **Spikes** | The two unvalidated assumptions checked | **1 evening** — and they may invalidate parts of phases 2–3 |
| **0** | Tests booked, feed requested, profile gaps closed, VPS + DNS | **1 week**, mostly waiting |
| **1** | CV engine + claim audit + entailment pass — **sendable applications** | **1.5–2.5 weeks** |
| **2** | Ingest, NOC mapping, two-stage matching | **2–3 weeks** |
| **3** | Dashboard | **2–4 weeks** — the widest range here; UI always is |
| **4** | Sending, throttle, IMAP replies, contact resolution | **2–3 weeks** |
| **5** | Trust ramp, monitoring, analytics | **1–2 weeks** |
| | **Total to fully autonomous** | **≈ 2.5–4 months** |

**The number that actually matters is different.** After **phase 1 — roughly two
weeks — Gedeon can send real, individually tailored applications by hand.** That
is the point where this project starts affecting the outcome. Everything after it
raises throughput; nothing after it is required to start.

So the honest framing is: *two weeks to start applying, a few months to stop doing
it manually.* If the timeline feels long, the correct response is not to cut
phase 1 — it is to run phase 1 and start sending while the rest gets built.

**Phase 3 is the most cuttable thing here.** The dashboard is 2–4 weeks for
visibility into a system whose value lives in phases 1 and 4. It was asked for
explicitly and it is genuinely useful for trusting the automation — but if time
gets short, a CLI plus a daily email digest buys most of the benefit for a couple
of days' work, and the dashboard can come later.

Phases are ordered by dependency, not calendar.

---

## Spikes — before anything else

`spikes/` contains two runnable scripts that check the assumptions the
architecture rests on. Both need a machine that can reach `gc.ca`; the planning
container could not.

- `01_fetch_posting.py` — what "Show how to apply" actually does. Decides whether
  the production path needs a browser at all.
- `02_inspect_opendata.py` — whether the open-data CSV is fresh enough to support
  monitoring, and whether it carries an LMIA signal.

**Expected to invalidate something.** The prediction on record is that spike 2
fails its freshness check, which would move live discovery from open data to the
filtered search pages and change `docs/03`. Better to find that in an evening than
in week six.

---

## Phase 0 — Do these first, outside the software

These are higher expected value than any code in this repo and they are not
blocked by it.

| # | Action | Why now |
|---|---|---|
| 0.1 | **Book TEF Canada / TCF Canada.** | `docs/01-immigration-strategy.md`. French draws in 2026 have cut off at CRS 379–446 vs ~514–525 general. Native French speaker. Nothing else in this project comes close to that leverage. |
| 0.2 | **Book IELTS General or CELPIP.** | Required for Express Entry regardless of route, and required to claim the French + English combination bonus. |
| 0.3 | **Request Job Bank XML feed access.** | Converts the riskiest component of the system into a sanctioned integration. One email. Do it in week 1 so the answer arrives before the ingest layer is finished. |
| 0.4 | **Close the blocking profile gaps.** | `profile/PROFILE-GAPS.md` items 2–4: two current referees, the Eat Creative / UCOOK overlap, and dates for FootGear and Cumpsty Electric. **Not cosmetic:** the generator excludes every entry still flagged `verify: true`, and FootGear + Cumpsty are two of the five general-work entries — including the only trades experience. Until those dates arrive, a Track B CV is painter, packer and security guard only, which is materially weaker than the profile suggests. |
| 0.5 | **Buy the VPS, set up DNS.** | SPF, DKIM and DMARC on `gedeonchrist.com` need time to propagate and the sending reputation needs time to warm. Starting this early costs nothing. |

---

## Phase 1 — Manual loop, real applications

**Goal: Gedeon sends genuinely tailored applications, chosen by the system, this
week.** No ingest automation, no send automation. Prove the document quality
first, because everything downstream is worthless if the CVs aren't good.

Ordered so the **measurement exists before the thing being measured**. Building
the generator first and the harness later is how a CV engine ends up quietly
producing plausible documents nobody can tell are underperforming.

1. **Golden set** — 20 real postings captured from the spikes: 15 LMIA-queue
   (farm, greenhouse, food, caregiving, labouring), 5 international-queue
   developer roles. Frozen and version-controlled.
2. **Layer 1 deterministic checks** — claim audit, coursework rule, referee rule,
   structure, length, banned phrases, specificity budget, screening questions,
   Canadian English, date format. (`docs/07`)
3. **Layer 2 ATS round-trip** — generate → parse with two independent résumé
   parsers → diff against the structured object. 100% recovery of the six fields
   from F-C or the document is rejected. **This is the highest-value test in the
   system** and it must exist before the first document is sent.
4. **Generator** — generation contract, claim audit, claim-level entailment pass,
   both tracks.
5. **Renderer** — native DOCX via `python-docx` (primary), PDF companion.
6. **CLI** — `northbound generate --posting <url-or-file>` → DOCX + PDF + cover
   letter + audit report.
7. **Layer 3 LLM-as-judge** with the F-F bias mitigations; Layer 4 calibration
   against Gedeon's own ratings.
8. `master-profile.yaml` is already complete — no blocking gaps remain.
9. Postgres schema and the `events` spine.

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
