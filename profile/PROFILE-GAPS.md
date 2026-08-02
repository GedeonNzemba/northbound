# Profile gaps — things that must be resolved before mass applications go out

Ordered by how much damage they do if left unresolved. Every item corresponds to a
`verify: true` flag in `master-profile.yaml`.

## Blocking — the system should not auto-send until these are closed

**None.** Every entry in `master-profile.yaml` is confirmed and usable as of
2026-08-02. The CV engine can generate against the full profile.

### Resolved

| Gap | Outcome |
|---|---|
| Certification wording | The AWS, Azure, Microsoft, Oracle and ISTQB items are **coursework from Gedeon's remote studies at IT Academy**, not separately-sat vendor exams. They now render **under Education → IT Academy** as curriculum content rather than as a certifications list — which is both accurate and stronger, since it presents two years of structured study instead of a list of unverifiable badges. (D1) |
| Referees | Closed on Gedeon's instruction. The two former Salesian contacts are not to be used; their names and details are deleted from `master-profile.yaml` and must not be reinstated from `CV-early-talentmarket.pdf`. **No referees section is generated at all** — Canadian CV convention omits one, and "References available upon request" reads as filler. |
| Salesian Institute | Jan 2018 – Nov 2018. He studied there, earned both certificates, and was offered a job on the strength of his first exam result — supporting teaching staff with technology and acting as the institution's media officer. Full responsibilities recorded: 14 highlights. |
| Filming / editing / photography | Not a separate role — part of the Salesian media duties. |
| FootGear | Jul 2018 – Jan 2019, Contract, Sales Representative (LinkedIn). |
| Cumpsty Electrical | Oct 2017 – 2019 recorded. Gedeon chose not to specify an employment type, so **none is rendered** — an unlabelled role is unremarkable; a guessed one would be false. |
| Eat Creative / UCOOK overlap | Eat Creative is Contract Part-time, UCOOK is Contract. Two concurrent contracts, fully explained by rendering the employment type. |
| Painter dates | Sources agree at month level → renders "Nov 2016 – Jan 2017". Day-level dates forbidden; performance ratings not rendered. |
| McDonald's | 2019–2020, kitchen / food production. Directly relevant — the LMIA queue is ~70% agriculture and food. |

### Noted, not blocking

`linkedin.com/in/nzemba` still shows the Salesian role as Jan 2017 – Mar 2019
against the confirmed Jan 2018 – Nov 2018, and describes the IT Academy
coursework as certifications. Recorded here as a known state of the world.
Gedeon is aware; **do not raise it again.**

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
