# Profile gaps — things that must be resolved before mass applications go out

Ordered by how much damage they do if left unresolved. Every item corresponds to a
`verify: true` flag in `master-profile.yaml`.

## Blocking — the system should not auto-send until these are closed

| # | Gap | Why it blocks | What's needed |
|---|-----|---------------|---------------|
| ~~1~~ | ~~**Certification wording**~~ | **RESOLVED 2026-08-01.** Gedeon confirmed he did not sit the AWS, Microsoft, Oracle or ISTQB exams. Everything from IT Academy renders as *coursework*, and the claim audit rejects any generation that states one as a held credential. The current CV's "certifications in AWS… and Microsoft Azure…" wording must be corrected wherever it is still in use. See `docs/06-decisions.md` D1. | — |
| 2 | **Two current professional referees** | Both referees on file are from 2018 Salesian youth programmes. Canadian employers phone referees, and expect a recent manager. | Two referees from Kurtosys and/or DataBalk — name, title, company, work email, phone. Ask permission first. |
| 3 | **Eat Creative / UCOOK date overlap** | `Eat Creative Africa` is listed Jan 2021 – Oct 2022 and `UCOOK` Jan 2022 – May 2022. Overlapping full-time dates read as padding. | Confirm which was contract / part-time / freelance, and label it as such. This is a normal, easily-explained situation — but it has to be stated, not hidden. |
| 4 | **FootGear and Cumpsty Electric have no dates and no documents** | These two roles carry the entire honest case for retail and trades applications. Undated entries on a CV are a red flag. | Month/year start and end for each, branch/site location, and ideally one contactable referee each. |

## Important — fix before the first non-IT application

| # | Gap | Detail |
|---|-----|--------|
| 5 | **Painter placement conflict** | `CV-early-talentmarket.pdf` says 4 Nov 2016 – 9 Jan 2017, rating *Excellent*. The screenshot record says 23 Nov 2016 – 5 Jan 2017, rating *Well Balanced*. Pick the one backed by the official record and use it consistently. |
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
