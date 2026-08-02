# Profile gaps — things that must be resolved before mass applications go out

Ordered by how much damage they do if left unresolved. Every item corresponds to a
`verify: true` flag in `master-profile.yaml`.

## Blocking — the system should not auto-send until these are closed

| # | Gap | Why it blocks | What's needed |
|---|-----|---------------|---------------|
| ~~1~~ | ~~**Certification wording**~~ | **RESOLVED 2026-08-01.** Gedeon confirmed he did not sit the AWS, Microsoft, Oracle or ISTQB exams. Everything from IT Academy renders as *coursework*, and the claim audit rejects any generation that states one as a held credential. The current CV's "certifications in AWS… and Microsoft Azure…" wording must be corrected wherever it is still in use. See `docs/06-decisions.md` D1. | — |
| 2 | **Two current professional referees** | Both referees on file are from 2018 Salesian youth programmes. Canadian employers phone referees, and expect a recent manager. **Now the top blocking gap.** | Two referees from Kurtosys and/or DataBalk — name, title, company, work email, phone. Ask permission first. |
| 3 | **Employment timeline needs one clarification** | Gedeon describes UCOOK (Jan 2022) as his "first professional job", but the 2026 CV lists **Next Steps Digital** as Frontend Web Developer Jun–Sep 2019 and **Eat Creative Africa** as Web Developer Jan 2021 – Oct 2022 — both before or overlapping it. Separately, Eat Creative (Jan 2021 – Oct 2022) overlaps UCOOK (Jan–May 2022). A Canadian recruiter reading the CV will ask about both. | Confirm how to characterise Next Steps Digital and Eat Creative — internship, freelance, part-time, contract? Any of those is completely normal and easy to state; what cannot happen is two unexplained overlapping full-time roles. |
| ~~4~~ | ~~**FootGear and Cumpsty Electric have no dates**~~ | **RESOLVED 2026-08-02.** Gedeon supplied the full general-work timeline: FootGear Jan–Jun 2019 (contract), Cumpsty Electrical Oct 2017–2019 at Val de Vie Estate and nearby Paarl estates under a supervising electrician. Also surfaced a previously unrecorded job — **McDonald's kitchen / food production, 2019–2020** — which is directly relevant given the LMIA queue is ~70% agriculture and food. All six general-work entries are now usable. | — |

## Important — fix before the first non-IT application

| # | Gap | Detail |
|---|-----|--------|
| ~~5~~ | ~~**Painter placement conflict**~~ | **RESOLVED 2026-08-02 by granularity.** The two sources disagree on days (4 Nov–9 Jan vs 23 Nov–5 Jan) but agree on months. Canadian CV convention is `Mon YYYY` anyway, so rendering **"Nov 2016 – Jan 2017"** is true under either record and the conflict never reaches the page. Day-level dates must not be emitted for this entry. Performance ratings are not rendered at all — they are a South African placement-report convention, not a Canadian CV element, and the two sources disagree on that too. |
| 5b | **Polarama recurrence** | The documented window (Nov 2015 – Jan 2016) is used. Gedeon recalls returning "every school holidays" for nearly a year — that specific bullet (`gen.packer.h4`) is excluded until confirmed. Worth pinning down: *being asked back* is exactly the reliability signal agricultural and warehouse employers look for. |
| 6 | **Northlink N1–N2–N4 status** | Confirm which N-levels were completed and when. This is the strongest formal credential for any trades, manufacturing or technical-operations application, and it is currently missing from the 2026 CV entirely. |
| 7 | **Current phone number** | Two numbers on file (`+27832532615` from the 2026 CV, `+27631748193` from the older one). A Canadian employer calling a dead number is a lost opportunity. |
| 8 | **Driver's licence** | The old CV says "Driving Permits: None". A huge share of LMIA-approved general and trades roles require a valid driver's licence, and many Canadian postings ask for it explicitly. If this is still true, the system must filter those postings out rather than apply and waste the slot. If it has changed, record the licence code and issue date. |

## Strategic — not blocking the software, but higher value than the software

| # | Item | Why |
|---|------|-----|
| 9 | **French language test (TEF Canada / TCF Canada)** | See `docs/01-immigration-strategy.md`. French is Gedeon's home language. In 2026 French-language Express Entry rounds have been issuing invitations at CRS 379–446 while general rounds sit around 514–525. This single item plausibly outweighs the entire application pipeline. |
| 10 | **English test (IELTS General / CELPIP)** | Required for Express Entry regardless of route, and required to claim the French + English combination bonus. |
| 11 | **ECA for post-secondary study** | The ICAS report on file assesses only the National Senior Certificate → *Secondary School Graduation*. The IT Academy and Shaw Academy credentials are unassessed, so they currently contribute nothing to an Express Entry education score. Worth asking ICAS/WES whether either is assessable. |
| 12 | **Passport validity** | A work permit cannot be issued beyond passport expiry. Record the expiry date and renew if under ~2 years. |

## How this file is used

`master-profile.yaml` is the only input the CV engine reads. Any entry still
carrying `verify: true` is excluded from generated documents by default — the
generator will simply omit it rather than risk stating something unconfirmed.
Closing a gap means editing the YAML and removing the flag.
