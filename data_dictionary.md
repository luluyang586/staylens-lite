# Data dictionary and observed audit

Source: Inside Airbnb Sydney snapshot dated 2026-06-16. Counts and value lists below are observed results, not a to-do list. Full machine-readable evidence is in `docs/data_audit.json`.

## listings_clean (20,573 rows)

| Column | Type | Meaning / observed rule |
|---|---|---|
| listing_id | BIGINT | Source listing identifier; primary key |
| listing_name | VARCHAR | Source name |
| neighbourhood | VARCHAR | `neighbourhood_cleansed`; 38 observed values |
| latitude, longitude | DOUBLE | Source coordinates; not a route location |
| room_type | VARCHAR | Entire home/apt, Hotel room, Private room, Shared room |
| minimum_nights, maximum_nights | DOUBLE | Listing-level stay limits |
| accommodates | BIGINT | Declared guest capacity |
| bedrooms, beds | DOUBLE | Nullable declared capacity fields |
| number_of_reviews | BIGINT | Source cumulative count |
| host_is_superhost | BOOLEAN | Parsed from source t/f |
| instant_bookable | BOOLEAN | Parsed from source t/f |
| listing_url | VARCHAR | Source detail URL |
| last_scraped | VARCHAR | Source scrape date; observed 2026-06-17/28/29 |
| base_price_aud | DOUBLE | Cleaned listing `price`; 2,787 null values retained |
| rating_5 | DOUBLE | Observed source scale is 0–5; null retained |

## calendar_clean (7,509,145 rows)

| Column | Type | Meaning / observed rule |
|---|---|---|
| listing_id | BIGINT | Source listing identifier |
| stay_date | DATE | 2026-06-17 through 2027-06-28 |
| available | BOOLEAN | Source t/f; not proof of occupancy or booking |
| price_aud | DOUBLE | All null: the downloaded calendar file has no price column |
| minimum_nights, maximum_nights | INTEGER | Date-level limits where present |

## reviews_clean (801,398 rows)

| Column | Type | Meaning |
|---|---|---|
| listing_id | BIGINT | Source listing identifier |
| review_id | BIGINT | Source review identifier; primary key |
| review_date | TIMESTAMP | Review date, 2009-12-05 through 2026-06-28 |
| comments | VARCHAR | Original review text; no generated translation |

## poi (10 rows)

Manually curated approximate Sydney places and stations. `source` records the curator/source and `precision_note` states coordinate limitations. Distance is haversine straight-line distance only.

## metadata

Key/value facts embedded during the atomic build: real-public-snapshot marker, snapshot date, source index URL, daily-price support and build timestamp.
