# Frozen final-v2 evaluation

Date: 2026-09-21
Provider/model: OpenAI `gpt-4o-mini`
Temperature: 0
Run policy: one shot after dataset and prompt hashes were frozen; no post-result tuning or rerun

## Results

| Suite | Primary metrics | n |
|---|---|---:|
| Intent final-v2 | 95.00% case exact; 97.16% field accuracy (342/352) | 100 |
| Text-to-SQL final-v2 | 96.00% status/execution; 82.00% output contract; 78.00% semantic result | 50 |

## Intent slices

| Slice | Case exact | Field accuracy | n |
|---|---:|---:|---:|
| bilingual/colloquial | 100.00% | 100.00% | 10 |
| budget semantics | 100.00% | 100.00% | 15 |
| complete core | 95.00% | 99.09% | 20 |
| date and duration | 80.00% | 91.30% | 10 |
| instruction robustness | 100.00% | 100.00% | 5 |
| location entities | 100.00% | 100.00% | 15 |
| missing or ambiguous | 86.67% | 89.71% | 15 |
| preferences | 100.00% | 100.00% | 10 |

Intent failures were: one explicit total budget incorrectly divided into a per-night amount; one USD request incorrectly converted to AUD; one ambiguous request failed both validation attempts; and two relative dates used incorrect years despite the supplied current date.

## SQL failure analysis

The model correctly accepted/rejected 48/50 questions. It falsely rejected two supported calendar questions: daily availability in December 2026 and availability on 2027-01-01.

Nine additional questions failed the stricter contract or semantic check:

- Alias/required-column failures: `s02`, `s09`, `s17`, `s18`, `s19`, `s27`, `s36`.
- `s13` grouped all room types instead of filtering to hotel rooms.
- `s33` returned a valid top-count query but omitted the required deterministic listing-ID tie-break at the tenth position, producing a different result set.

These results show that the retry logic materially improved support detection, but alias discipline, exact business filters, date-availability reasoning and deterministic ranking remain production risks.

## Usage and cost

| Suite | Calls | Input tokens | Output tokens | Total tokens | Estimated cost |
|---|---:|---:|---:|---:|---:|
| Intent final-v2 | 101 | 157,489 | 15,969 | 173,458 | US$0.03320 |
| SQL final-v2 | 66 | 76,671 | 2,538 | 79,209 | US$0.01302 |
| **Total** | **167** | **234,160** | **18,507** | **252,667** | **US$0.04623** |

Cost uses the official evaluation-date `gpt-4o-mini` rates of US$0.15 per million input tokens and US$0.60 per million output tokens.

## Allowed résumé claim

“Built and evaluated an auditable accommodation analytics agent on real public data. On frozen one-shot benchmarks, `gpt-4o-mini` achieved 95% exact Intent parsing across 100 cases and 78% semantic Text-to-SQL result accuracy across 50 business questions; all SQL was validated against a read-only allowlisted execution boundary.”

Do not claim 100% Intent accuracy, production-ready SQL, or that final-v2 remained untouched if it is reused for later prompt tuning.
