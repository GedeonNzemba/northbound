# 01 — Immigration strategy: what this system is actually buying

Read this before `03-architecture.md`. The software is a means to an end, and the
end changed in 2025. Building the pipeline on the old assumptions would produce a
technically excellent system pointed at the wrong target.

---

## The premise, restated accurately

The original plan: *get an LMIA-backed job offer → that boosts my Express Entry
score → I get permanent residence.*

**The middle step no longer exists.** Since 25 March 2025 a job offer — LMIA-backed
or not — is worth **zero** additional CRS points (F4). It was removed specifically
because LMIA job-offer letters were being sold for $20,000–$75,000.

That does **not** make the plan wrong. It makes the mechanism different, and the
difference matters for how the system is tuned.

## What an LMIA job offer is still worth — which is a great deal

```
LMIA-backed job offer
        ↓
   Closed work permit  ──────────────►  You are legally living and working in Canada
        ↓
   12 months of Canadian skilled work experience
        ↓
   ┌────────────────────────┬───────────────────────────────┐
   │ Canadian Experience    │ Provincial Nominee Program    │
   │ Class (Express Entry)  │ — most streams still weight a │
   │ + Canadian-experience  │   local job offer heavily     │
   │   CRS points           │ → nomination = +600 CRS       │
   └────────────────────────┴───────────────────────────────┘
                            ↓
                   Permanent residence
```

Three things to take from this:

1. **The job offer is the entry ticket, not the score.** Its value is that it puts
   you physically in Canada, legally, earning. Everything else follows from being
   there.
2. **A provincial nomination is still worth +600 CRS** — the largest single boost
   available — and PNP streams still care about a local job offer even though
   Express Entry no longer does. Province of employment is therefore a real
   variable, not a detail.
3. **Canadian work experience is the compounding asset.** One year of it converts
   a foreign-experience profile into a CEC-eligible one.

## Where the 2026 squeeze actually lands

The TFWP tightening in F5 is not uniform. It falls almost entirely on the
**low-wage stream**:

| | Low-wage stream | High-wage stream |
|---|---|---|
| Not processed in CMAs with unemployment ≥ 6% | ✅ applies | ❌ does not |
| 8-week advertising requirement (from 1 Apr 2026) | ✅ applies | ❌ does not |
| Cap on TFW share of workforce (10%, 15% rural) | ✅ applies | ❌ does not |
| Typical roles | painter, security guard, retail, general labour, packing | **web developer (NOC 21234, TEER 1)** |

So: the non-IT applications — painter, security, retail, electrician's helper —
are aimed at the part of the programme that Canada spent 2024–2026 deliberately
shrinking, in the cities where most jobs are. The web-developer applications are
aimed at the part that was left largely intact.

### The recommended split, and a correction

An earlier draft of this document recommended 60/40 between tech and general
work. **That was wrong** — it was a compromise with the stated preference to
"apply to everything", not a conclusion from the evidence above. Corrected:

- **~85% of send capacity → NOC 21234 / 21233 / 22222 and adjacent tech roles**
- **~15% → documented general work**, as a hedge, not a second strategy

The reasoning is arithmetic, not caution. Daily send capacity is capped at 30–40
for deliverability reasons (F8) and that cap — not the supply of jobs — is the
binding constraint on this entire system. Every general-work application spends a
slot that a tech application could have used. So the question is never "should I
also apply to general work?" but "**is this slot better spent here or on a
front-end role?**"

For most slots the answer is clearly the front-end role:

- The low-wage stream is the part of the programme Canada spent 2024–2026
  deliberately shrinking; the high-wage stream where TEER 1 sits is largely intact.
- In tech, Gedeon is a *strong* candidate — seven years, production work, North
  American clients including a Canadian bank. In general work he is an honest
  applicant with vacation placements from a decade ago, competing against local
  candidates the employer must demonstrably fail to find before an LMIA is even
  possible.
- An employer must justify hiring a foreign worker over a Canadian. That
  justification is far easier to write for a specialised developer than for a
  painter.

**Why keep 15% rather than zero.** Rural and remote employers face genuinely
different labour markets, rural low-wage caps were *loosened* in April 2026, and
the general experience is real and documented. It is a live lottery ticket, just
a much cheaper one than the main strategy — and worth buying a few of.

**This is a starting weight, not a belief.** The system tracks reply rate per
occupation family from the first application. If general-work applications come
back at three times the tech reply rate, the split should move, and the data will
say so within a few hundred applications. What it must not do is stay at a number
that was chosen to feel balanced.

## The finding that outranks this entire project

**Gedeon's home language is French.**

His own earlier CV records French as *Excellent / Excellent / Excellent* across
speaking, reading and writing. He is Congolese; French is a first language, not a
school subject.

In 2026, Express Entry rounds targeting French-language proficiency have issued
invitations at **CRS 379–446** — one round on 22 July 2026 went to **399** with
5,000 invitations — while general rounds sat around **514–525** (F6).

That is a gap of roughly **120 CRS points**, which is more than a decade of work
experience is worth. Qualifying requires **NCLC 7** across all four skills on TEF
Canada or TCF Canada. For a native speaker, NCLC 7 (roughly B2) is a preparation
and booking problem, not a language problem. Holding NCLC 7 French *and* CLB 5
English also adds **+50 CRS** on top.

| Action | Approx. cost | Approx. time | Plausible effect |
|---|---|---|---|
| Book and sit TEF Canada | ~CAD 400 | 4–10 weeks | Access to a draw stream running ~120 CRS below the general cut-off |
| This entire application system | dev time | ongoing | One offer, if the pipeline connects |

These are not alternatives — do both. But if only one thing happens this month,
**it should be booking the French test.** No amount of engineering competes with a
120-point structural advantage that is already sitting in the profile, unused.

The same applies to the ECA gap: the ICAS report on file assesses only the
National Senior Certificate as *Secondary School Graduation*. The IT Academy and
Shaw Academy study is unassessed and therefore currently contributes nothing to an
education score.

## What this means for the software

The strategy above translates into concrete system requirements:

| Strategic fact | System requirement |
|---|---|
| Job offer = entry ticket, not points | Optimise for **reply rate and offer rate**, not applications sent. Sent-count is a vanity metric. |
| **Send capacity (30–40/day) is the binding constraint, not job supply** | **Ranking quality matters far more than ingest coverage.** With thousands of eligible postings and ~35 slots a day, the only question that matters is *which 35*. Invest in the scorer before broadening the funnel. |
| PNP nomination = +600 CRS | Track and surface **province** on every posting; allow per-province weighting; flag provinces with active PNP streams matching NOC 21234. |
| Low-wage stream is constrained by regional unemployment | Ingest the quarterly ESDC refusal-to-process region list and **de-prioritise low-wage postings in blocked CMAs** — those employers cannot get an LMIA there right now, so applying is wasted capacity. |
| High-wage / TEER 1 is the softer target | Weight send capacity toward NOC 21234 and adjacent codes. |
| Prior positive LMIA is a strong signal | Cross-reference every employer against the TFWP Positive LMIA Employers List; **rank corroborated employers first**. |
| Non-IT applications must be honest | The CV engine's transferable-skills mode is a core feature, not a nice-to-have. See `docs/04-cv-engine.md`. |
| Outcome data beats assumptions | Per-occupation, per-province, per-template outcome tracking from day one. |

## Honest expectations

An employer sponsoring a foreign worker is not doing a favour — they are paying a
fee, running a recruitment process for weeks, waiting months for a decision, and
accepting a compliance inspection risk. They do it when they cannot fill the role
locally.

That means:
- Reply rates on cold applications from abroad are **low**. Hundreds of
  applications producing a handful of conversations is a normal, working outcome,
  not a failure.
- The applications most likely to land are the ones where Gedeon is **genuinely
  the answer to the employer's problem** — which, given seven years of production
  front-end work with North American clients including BMO, is the tech ones.
- Nothing in this system should ever overstate the profile. An LMIA application is
  a government process with fraud investigators attached to it, in a programme
  that was *just* reformed because of fraud. The integrity rules in
  `master-profile.yaml` and `docs/04-cv-engine.md` are not bureaucratic caution —
  they protect the one thing Gedeon cannot rebuild if it is damaged.
