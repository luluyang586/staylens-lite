-- Documentation schema for the 2026-06-16 Sydney snapshot.
-- The authoritative build logic is scripts/build_database.py.
CREATE TABLE listings_clean (
  listing_id BIGINT PRIMARY KEY, listing_name VARCHAR, neighbourhood VARCHAR,
  latitude DOUBLE, longitude DOUBLE, room_type VARCHAR,
  minimum_nights DOUBLE, maximum_nights DOUBLE, accommodates BIGINT,
  bedrooms DOUBLE, beds DOUBLE, number_of_reviews BIGINT,
  host_is_superhost BOOLEAN, instant_bookable BOOLEAN,
  listing_url VARCHAR, last_scraped VARCHAR,
  base_price_aud DOUBLE, rating_5 DOUBLE
);
CREATE TABLE calendar_clean (
  listing_id BIGINT, stay_date DATE, available BOOLEAN,
  price_aud DOUBLE, minimum_nights INTEGER, maximum_nights INTEGER
);
CREATE TABLE reviews_clean (
  listing_id BIGINT, review_id BIGINT PRIMARY KEY,
  review_date TIMESTAMP, comments VARCHAR
);
CREATE TABLE poi (
  poi_id BIGINT PRIMARY KEY, poi_name VARCHAR, poi_type VARCHAR,
  latitude DOUBLE, longitude DOUBLE, source VARCHAR, precision_note VARCHAR
);
CREATE TABLE metadata (key VARCHAR PRIMARY KEY, value VARCHAR);

-- Review LLM outputs are derived data in data/review_cache.sqlite rather than
-- snapshot facts. The SQLite cache includes model and prompt hashes.
