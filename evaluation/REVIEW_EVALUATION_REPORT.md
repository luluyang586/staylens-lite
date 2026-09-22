# Review classification evaluation

Date: 2026-09-21
Provider/model: OpenAI `gpt-4o-mini`
Temperature: 0

## Reference set

- 55 reviews from the real Inside Airbnb Sydney 2026-06-16 snapshot.
- 138 aspect/sentiment reference tags across location, noise, cleanliness, value, host service, amenities, accuracy and safety.
- Five generic-review controls whose correct output is an empty tag list.
- Every reference evidence span is verified as an exact substring of its source review.
- Annotation provenance: **Codex-assisted curated reference labels; not human-labelled**.

The dataset and prompt were hashed before the live run. No model outcome was used to change the reference labels or prompt.

## Results

| Metric | Result |
|---|---:|
| Strict aspect + sentiment micro precision | 79.35% |
| Strict aspect + sentiment micro recall | 52.90% |
| Strict aspect + sentiment micro F1 | 63.48% |
| Aspect-detection micro F1 | 64.35% |
| Review-level exact match | 25.45% |
| Sentiment accuracy on matched aspects | 98.65% |
| Exact-source evidence compliance | 89.13% |
| Empty-control accuracy | 100.00% |
| Reviews returned | 51/55 |

The model is strong at sentiment once it identifies an aspect, but recall is the primary weakness. It omitted four review IDs in one 10-review batch and missed many amenities, noise, value and accuracy labels.

## Per-category strict aspect + sentiment

| Category | Precision | Recall | F1 | Reference tags |
|---|---:|---:|---:|---:|
| location | 87.10% | 90.00% | 88.52% | 30 |
| noise | 100.00% | 25.00% | 40.00% | 8 |
| cleanliness | 61.90% | 86.67% | 72.22% | 15 |
| value | 66.67% | 30.77% | 42.11% | 13 |
| host_service | 81.82% | 69.23% | 75.00% | 26 |
| amenities | 100.00% | 10.34% | 18.75% | 29 |
| accuracy | 66.67% | 20.00% | 30.77% | 10 |
| safety | 100.00% | 57.14% | 72.73% | 7 |

## API usage and cost

The final scored run used 6 calls, 5,195 input tokens and 2,807 output tokens (8,002 total). At the official `gpt-4o-mini` rates current on the evaluation date—$0.15 per million input tokens and $0.60 per million output tokens—the final run cost is approximately **US$0.00246**.

An earlier scored-output attempt used another 5,195 input and 3,047 output tokens but exposed a batch-grading harness defect: invalid evidence in one item caused the whole batch to be discarded. It was not reported as model accuracy. Including that diagnostic run, total API cost was approximately **US$0.00507**.

## Allowed claim

“On 55 real accommodation reviews with 138 Codex-assisted reference labels, `gpt-4o-mini` achieved 63.48% strict aspect/sentiment micro F1 and 89.13% exact-source evidence compliance.”

Do not call the set human-labelled, do not treat 55 reviews as population-level accuracy, and do not hide the four omitted review IDs or the weak amenities/accuracy recall.
