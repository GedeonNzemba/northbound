# 02 — Legal and compliance position

This chapter exists because one finding (F1) would otherwise quietly sink the
project six months in. It is better to design around it now than to discover it
after building the wrong thing.

---

## The constraint

Job Bank's Terms of Use prohibit accessing the service with "any script, robot,
spider, Web crawler, screen scraper, automated query program, artificial
intelligence or other automated device, software, or process" (F1).

There is no reading of that sentence in which a fully automated scraper is
permitted. Public scrapers for `jobbank.gc.ca` exist on GitHub and Apify — their
existence is not permission, and building on their model would put a project whose
entire purpose is a *Canadian government immigration outcome* in breach of a
*Canadian government website's* terms. That is a bad trade at any volume.

## What the law actually says vs. what the terms say

These are two different questions and it is worth separating them.

**Law.** US case law (persuasive, not binding in Canada) has settled into a clear
line: *hiQ v. LinkedIn* held that scraping public pages is not unauthorised access
under the CFAA; *Meta v. Bright Data* held that terms of service bound **logged-in**
scraping only, not logged-off collection of public content (F9). Collecting
publicly visible pages, logged out, at low volume, is not the legal exposure
people imagine.

**Contract.** But hiQ still lost on the contract claim — because it had **accepted**
LinkedIn's terms by creating accounts. That is the trap here: Job Bank's **Direct
Apply requires a Plus account** (F3), and creating one means accepting the very
terms that prohibit automation. Automating a logged-in Job Bank account is the
worst available position, combining the contract breach with an identifiable
account tied to Gedeon's real name in front of the department that will later
process his work permit.

## The resulting design rules

These are architectural, not advisory.

### Rule 1 — Sanctioned sources first

The discovery layer is built on channels Canada publishes *for reuse*:

1. **Open data CSV** of Job Bank postings, under the Open Government Licence
   (F2.1) — bulk, free, explicitly licensed for reuse.
2. **Job Bank XML feed** (F2.2) — apply for partner access in week 1. This is the
   single highest-value compliance action available: it turns the riskiest
   component into a sanctioned integration. Even if it is declined, having asked
   and been declined is a materially better position than never asking.
3. **TFWP Positive LMIA Employers List** (F2.3) — corroboration of which employers
   have genuinely obtained LMIAs.

Together these give NOC codes, employer names, locations, wages and terms — most of
what the matching engine needs — with no terms-of-use problem at all.

### Rule 2 — Never automate a logged-in session

No Job Bank account. No Direct Apply automation. No stored Job Bank credentials
anywhere in the system. This is a hard constraint in code, not a policy note.

### Rule 3 — Assisted apply, not autonomous scraping

The open data does not carry the employer's apply-to email. Something has to open
the specific posting to get it. The system handles this as an **assisted** step
rather than a crawl:

- It never sweeps the site. It opens only postings that already passed matching
  and were queued for application — tens per day, not thousands.
- Requests are logged out, serialised, and paced at human speed with jitter.
- `robots.txt` is fetched and honoured; a `Disallow` on the target path stops the
  queue.
- The user agent is honest. No fingerprint spoofing, no residential proxy
  rotation, no CAPTCHA-solving services. If the site does not want the traffic,
  the correct response is to stop, not to disguise it.
- Any 403/429/CAPTCHA trips a circuit breaker that halts retrieval, alerts on the
  dashboard, and requires a manual reset.

This mode ships behind a config flag that is **off by default**, with a plain-language
consent screen on first enable stating what it does and what the terms say. Gedeon
decides, knowingly. The default configuration of the shipped system is compliant.

**Manual fallback**, always available: the dashboard shows the queued posting and
a "open posting" button; Gedeon clicks it, copies the email, pastes it in. Two
seconds of human work per application, and every legal question disappears. For a
realistic 20–40 applications a day this is genuinely viable, and it is the mode to
run in until the XML feed request is answered.

### Rule 4 — Email conduct

CASL is very unlikely to bite (F10): a personal job application is not a commercial
electronic message, and the conspicuous-publication exemption covers it regardless.
The real risk is reputational. Rules:

- One recipient per message. Never CC, never BCC, never a mail-merge blast.
- Genuinely different content per message — a shared skeleton with a swapped name
  is worse than no personalisation, because it is *visibly* templated.
- Real `Reply-To`, real name, real phone number, real signature.
- **No tracking pixels, no link-wrapping, no open-tracking.** They mark the mail as
  bulk, they hurt deliverability, and they are what a spammer's stack looks like.
- No `List-Unsubscribe` header and no unsubscribe footer — on a one-to-one job
  application those *signal* bulk mail. (This is the correct call precisely
  because the message is not a CEM.)
- If an employer says "do not contact us again", that address is permanently
  suppressed. One list, checked before every send, no exceptions.
- Rate limit is a first-class system property, not a config nicety (F8).

### Rule 5 — Truth in the documents

Everything a generated CV asserts must trace to `profile/master-profile.yaml`.
The specific live risk today is the certification wording — the file records
IT Academy **coursework**, while the current CV claims AWS and Azure
**certifications** (see `profile/PROFILE-GAPS.md` item 1). Under the LMIA regime as
reformed in 2025, a misrepresentation found during processing is not a rejected
application, it is a finding of misrepresentation with a multi-year bar. This is
enforced in code by the generation contract in `docs/04-cv-engine.md`.

### Rule 6 — Data minimisation

- No RSA ID number, passport number, date of birth or home street address in the
  repo, in generated CVs, or in emails. Canadian CVs must not carry them (F11),
  and a leaked repo should not be able to hurt him.
- Employer contact addresses collected for applications are used for that purpose
  only. Never resold, never published, never bundled into a dataset. If this ever
  becomes a product for other users, that is a PIPEDA question requiring proper
  advice — flagged, not assumed.

---

## Summary of position

| Component | Basis | Comfort |
|---|---|---|
| Open data CSV ingestion | Open Government Licence – Canada | Fully sanctioned |
| TFWP LMIA employer list | Open Government Licence – Canada | Fully sanctioned |
| Job Bank XML feed | Partner programme, on request | Sanctioned if granted |
| Per-posting apply-detail retrieval | Contrary to Job Bank ToU; low volume, logged out, honest UA, robots-respecting | **Off by default, user-enabled, documented** |
| Manual copy-paste of apply details | Ordinary human use of a public website | Fully sanctioned |
| Emailing applications | Not a CEM; conspicuous-publication exemption applies regardless | Sound |
| Generated CVs | Traceable to source documents, no invented claims | Sound, enforced in code |

This project does not need to break Job Bank's terms to work. Design it so it
doesn't, and the one component that would has an off switch and a manual
alternative.
