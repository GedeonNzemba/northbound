# Profile gaps — things that must be resolved before mass applications go out

Ordered by how much damage they do if left unresolved. Every item corresponds to a
`verify: true` flag in `master-profile.yaml`.

## Blocking — the system should not auto-send until these are closed

| # | Gap | Why it blocks | What's needed |
|---|-----|---------------|---------------|
| **0** | **LinkedIn contradicts the CV — fix LinkedIn first** | Two public discrepancies a recruiter can find in ten seconds, and a mismatch looks worse than either version alone: (a) **Salesian Institute** — LinkedIn says Jan 2017 – Mar 2019, the confirmed dates are **Jan 2018 – Nov 2018**; (b) the **AWS/Azure wording** (decision D1) — those are coursework, not held certifications, and any claim of certification should be reworded on LinkedIn and the portfolio. **This now outranks referees as the top action.** | Edit both on `linkedin.com/in/nzemba`. Fifteen minutes. |
| ~~1~~ | ~~**Certification wording**~~ | **RESOLVED 2026-08-01.** Gedeon confirmed he did not sit the AWS, Microsoft, Oracle or ISTQB exams. Everything from IT Academy renders as *coursework*, and the claim audit rejects any generation that states one as a held credential. The current CV's "certifications in AWS… and Microsoft Azure…" wording must be corrected wherever it is still in use. See `docs/06-decisions.md` D1. | — |
| 2 | **Cumpsty overlaps a full-time job** | Cumpsty Electrical (Oct 2017 – 2019) sits squarely inside the **full-time** Salesian Institute IT Support role (Jan 2017 – Mar 2019). Two concurrent full-time jobs is the one combination a Canadian recruiter will query. Everything else on the timeline is now self-explanatory once employment types are shown; this is the last one that isn't. | One word: was Cumpsty **weekends**, **evenings**, or **school-holiday** site work? The CV then states it and the question disappears. Same question, lower stakes, for McDonald's (2019–2020). |
| 3 | **Salesian IT responsibilities are truncated** | LinkedIn shows the bullet list cut off at *"Set-up and install workstations…"*. Two years of full-time IT work is currently rendering on two thin bullets. | Paste the full responsibilities list from that LinkedIn entry. |
| ~~4~~ | ~~**Referees are weak**~~ | **LARGELY RESOLVED 2026-08-02.** Milton Saaiman and Rene Darling were written off as 2018 youth-programme contacts. LinkedIn shows Gedeon was **full-time staff** at Salesian Institute as an IT Support Technician for two years — so they are colleagues from a real employment relationship. Still worth adding **one current referee** from Kurtosys or DataBalk, since Canadian employers weight recency; and confirm the 2018 contact details still work and ask permission. | One current referee. |
| ~~5~~ | ~~**Eat Creative / UCOOK overlap**~~ | **RESOLVED 2026-08-02.** LinkedIn records Eat Creative as **Contract Part-time** and UCOOK as **Contract**. Two concurrent part-time/contract engagements, not two undeclared full-time roles. Rendering the employment type was all that was ever required. | — |
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
