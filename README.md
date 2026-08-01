# Northbound

Automated Canadian LMIA job discovery, tailored Canadian CV generation, and
application pipeline — with a live operations dashboard.

**Status: planning complete, no code yet.** Start at [`docs/05-roadmap.md`](docs/05-roadmap.md).

---

## The problem

Getting an LMIA-supported job offer in Canada from South Africa means applying to
a lot of employers, quickly, with a document tailored to each one — across two very
different kinds of role:

- **Software** — 7 years of production front-end work, NOC 21234, TEER 1.
- **General work** — real, documented painting, warehouse, security, retail and
  electrical-assistant experience, applied for honestly as transferable-skills
  applications rather than inflated claims.

Doing that by hand is a full-time job. Doing it badly at scale is worse than not
doing it at all.

## What this builds

```
sanctioned data sources → filter → LLM relevance score → tailored CV + cover letter
      → claim audit (blocks on any uncited claim) → throttled send → reply tracking
                                    ↓
                        live dashboard over all of it
```

## Documentation

| | |
|---|---|
| [`docs/00-research-findings.md`](docs/00-research-findings.md) | Verified facts with sources — Job Bank terms, open data, LMIA policy, CASL, Canadian CV conventions |
| [`docs/01-immigration-strategy.md`](docs/01-immigration-strategy.md) | What an LMIA offer is worth in 2026, and the one finding that outranks this whole project |
| [`docs/02-legal-compliance.md`](docs/02-legal-compliance.md) | Why discovery runs on open data rather than a scraper |
| [`docs/03-architecture.md`](docs/03-architecture.md) | Stack, components, data model, dashboard |
| [`docs/04-cv-engine.md`](docs/04-cv-engine.md) | The generation contract and the two CV tracks |
| [`docs/05-roadmap.md`](docs/05-roadmap.md) | Phased delivery — phase 1 produces real applications |
| [`profile/master-profile.yaml`](profile/master-profile.yaml) | Single source of truth for every generated document |
| [`profile/PROFILE-GAPS.md`](profile/PROFILE-GAPS.md) | What must be confirmed before anything is sent at volume |

## Principles

1. **Nothing is invented.** Every line of every generated CV traces to a source
   document, and an automated audit blocks anything that doesn't.
2. **Compliant by default.** No logged-in automation of Job Bank, no scraping in
   the default configuration.
3. **Reputation is the scarce resource.** Own sending domain, hard daily cap,
   permanent suppression list.
4. **Replies are the metric.** Applications sent is a vanity number.

## Stack (planned)

Python 3.12 · FastAPI · PostgreSQL · Playwright · WeasyPrint · Claude API
(`claude-opus-5`) · React 19 + TypeScript + Vite + Tailwind · Docker Compose on a
small VPS.
