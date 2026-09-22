# StayLens Lite PRD (as implemented)

## 1. Product goal

Build a portfolio-grade Sydney accommodation decision tool that demonstrates business interpretation, reproducible analytics, safe LLM integration and honest uncertainty. It is not a booking engine and must never present snapshot data as live inventory.

## 2. Users and jobs

1. A traveller supplies guests, nights, budget, room type, areas, target POIs and qualitative preferences. The system returns five traceable candidates without silently relaxing hard constraints.
2. An analyst asks a supply/price/rating question. The system returns a bounded read-only result table and shows the executed SQL.

## 3. Non-goals

No booking, live prices, real occupancy, causal inference, route planning, account system, multi-city support, currency conversion, web scraping or autonomous multi-agent operation.

## 4. Inputs and contracts

`StayIntent` is a strict Pydantic contract. Required recommendation fields are guests, nights and budget. A distance limit also requires at least one known POI. Currency must be AUD. Extra fields and invalid numeric ranges are rejected.

Input paths:

- Structured form: always available and deterministic.
- Natural language: only available when a real LLM provider, model and key are configured. There is no keyword-rule substitute.

Hard constraints: guests, nights, budget, explicit room type, explicit neighbourhood and explicit maximum distance. Soft preferences: quiet, clean, safe and near transit. Soft preferences affect ranking only.

## 5. Data

Source: Inside Airbnb Sydney public snapshot dated 2026-06-16.

| Entity | Rows | Notes |
|---|---:|---|
| listings_clean | 20,573 | 2,787 missing base price, retained as missing |
| calendar_clean | 7,509,145 | 2026-06-17 to 2027-06-28; no daily price in source |
| reviews_clean | 801,398 | 2009-12-05 to 2026-06-28 |
| poi | 10 | Manually curated approximate coordinates with provenance notes |

Raw-file URLs, sizes and SHA-256 values are in `data/raw/manifest.json`; transformation audit is in `docs/data_audit.json`. Download and build are separate, atomic scripts. Existing raw files are not silently overwritten.

For repository deployment, `data/staylens_demo.duckdb` is a deterministic sample of the same verified snapshot: up to five listings per neighbourhood and room type, all calendar rows for those listings, and their latest 20 reviews. It is labelled `real_public_sample` throughout the application and is never presented as the full market.

Critical rule: a date-specific search requires complete availability and daily prices for every stay date. Because this snapshot has no daily-price column, the workflow returns `date_price_unavailable`. It must not substitute `listings.price`.

## 6. Recommendation state machine

1. Validate intent and require a database marked `real_public_snapshot` or `real_public_sample`; visibly warn when the sample is used.
2. Reject unsupported hard constraints, unknown neighbourhoods and unknown POIs.
3. For date mode, validate coverage and daily-price support; otherwise stop with a typed status.
4. Run parameterized SQL for all structured hard constraints.
5. Compute distance to every requested POI. Multiple POIs are conjunctive; the farthest distance controls compliance and score.
6. Use complete candidates for comparable-market scoring; do not truncate before distance filtering.
7. Pre-rank structural candidates and take top 20 for review processing.
8. Classify reviews through live LLM or validated cache. If unavailable, use neutral 50 and display that evidence is missing.
9. Re-rank and return top 5, warnings and a persisted run trace.

No-result responses retain all hard constraints. The application does not automatically loosen a constraint or fabricate a “near match”.

## 7. Analytics

Price score uses an independent whole-market comparator: same neighbourhood, room type and accommodates ±1. If fewer than five observations exist, it falls back to same area/room type and then city-wide same room type. The inverse midrank percentile becomes a 0–100 score.

Bayesian rating uses city mean `C`, observed rating `R`, review count `v`, and prior weight `m=20`: `AdjustedRating = (vR + mC)/(v+m)`.

Location score uses linear decay to an explicit maximum distance, otherwise `100*exp(-distance/3)`. With no location preference it is neutral 50. Transit is an approximate nearest distance to four curated station points and always displays a coverage warning.

Review score is `100*(1-decayed negative rate)` using `exp(-days/365)`. User-relevant negative aspects receive double weight. Fewer than three classified reviews or no model output gives neutral 50, never an “all clear”.

Default final weights are price 35%, rating 30%, location 20% and review 15%. User weights are normalized in the UI and validated at the scoring boundary. Stable tie-break: score descending, review count descending, price ascending, listing ID ascending.

## 8. Review LLM contract

The schema has eight aspects (location, noise, cleanliness, value, host_service, amenities, accuracy, safety), four sentiments (positive, negative, neutral, mixed), and an exact source substring as evidence. Every requested review ID must appear once; foreign IDs, duplicate aspects and invented evidence are rejected. Cache key includes review text, provider/model and prompt hash. There is intentionally no model-authored confidence probability.

## 9. Text-to-SQL security boundary

Recommendations never use Text-to-SQL. Business analysis may use four fixed offline examples or a live LLM. Before execution:

- exactly one parsed SELECT is required;
- tables resolve only to listings_clean, calendar_clean, reviews_clean or poi, including valid CTEs;
- columns are qualified against the actual database schema;
- only approved aggregate, scalar, date and window functions are accepted;
- commands, file readers, qualified/external tables and extra statements are rejected;
- DuckDB is read-only with external access, extension autoload and autoinstall disabled;
- execution has an interrupt timer and an outer 200-row limit.

The system reports unsupported questions instead of inventing unavailable metrics such as revenue, conversion or bookings.

## 10. Traceability and UI

Every recommendation writes a JSON trace under `data/runs/` containing run ID, UTC time, source metadata, validated intent, status, parameterized SQL plus parameters, weights, review mode, warnings and returned rows. The UI includes a source/audit tab and CSV exports.

## 11. Acceptance criteria

- All automated tests pass and Streamlit loads without an exception.
- Unknown POIs fail closed.
- A real exploration scenario returns only listings within price/capacity hard constraints.
- A date scenario on this source returns `date_price_unavailable`.
- Destructive, multi-statement, external-reader, unknown-table and unknown-column SQL are rejected.
- No LLM metric is published without a configured model and an actual benchmark run.

Current evidence and remaining blockers are maintained in `docs/IMPLEMENTATION_STATUS.md`.
