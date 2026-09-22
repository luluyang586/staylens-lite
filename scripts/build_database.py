"""Audit real data and atomically build a separate, versioned snapshot database."""
import hashlib, json, os, sys, shutil
from pathlib import Path
from datetime import datetime, timezone
import duckdb
import pandas as pd
ROOT=Path(__file__).resolve().parent.parent
RAW=ROOT/"data/raw"
TARGET=ROOT/"data/staylens.duckdb"
def money(s):
    return pd.to_numeric(s.astype("string").str.replace(r"[^0-9.\-]","",regex=True),errors="coerce")
def verify_manifest(manifest):
    for item in manifest["files"]:
        path=RAW/item["file"]
        if not path.exists() or path.stat().st_size != item["bytes"]:
            raise ValueError(f"Raw file missing or size mismatch: {path.name}")
        h=hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda:stream.read(1024*1024),b""):h.update(chunk)
        if h.hexdigest()!=item["sha256"]:
            raise ValueError(f"Raw file checksum mismatch: {path.name}")
def build():
    manifest=json.loads((RAW/"manifest.json").read_text())
    verify_manifest(manifest)
    d=pd.read_csv(RAW/"listings.csv.gz",low_memory=False)
    audit={"source":manifest,"raw_listings":len(d),"missing_base_price":int(d.price.isna().sum())}
    rating=pd.to_numeric(d.review_scores_rating,errors="coerce")
    # Explicit source-level audit: fail on mixed/unknown scales rather than guessing per row.
    if rating.dropna().between(0,5).all(): scale=5
    elif rating.dropna().between(0,100).all() and rating.dropna().median()>5: scale=100
    else: raise ValueError("Ambiguous rating scale: manual audit required")
    audit["rating_scale"]=scale
    keep=["id","name","neighbourhood_cleansed","latitude","longitude","room_type",
          "minimum_nights","maximum_nights","accommodates","bedrooms","beds","number_of_reviews",
          "host_is_superhost","instant_bookable","listing_url","last_scraped"]
    out=d[keep].rename(columns={"id":"listing_id","name":"listing_name","neighbourhood_cleansed":"neighbourhood"})
    out["base_price_aud"]=money(d.price)
    out["rating_5"]=rating/(20 if scale==100 else 1)
    for col in ["host_is_superhost","instant_bookable"]:
        out[col]=out[col].map({"t":True,"f":False}).astype("boolean")
    out=out[out.latitude.between(-34.5,-33) & out.longitude.between(150,152)]
    out=out.drop_duplicates("listing_id")
    # Keep price outliers/missing data in the audit; eligibility excludes invalid prices.
    out.loc[out.base_price_aud<=0,"base_price_aud"]=None
    audit["clean_listings"]=len(out)
    audit["actual_scrape_dates"]=sorted(out.last_scraped.dropna().astype(str).unique().tolist())
    audit["room_types"]=sorted(out.room_type.dropna().unique().tolist())
    audit["neighbourhoods"]=sorted(out.neighbourhood.dropna().unique().tolist())
    tmp=ROOT/"data/building.duckdb"
    if tmp.exists(): raise FileExistsError("Previous staging DB exists; inspect before rebuilding")
    c=duckdb.connect(str(tmp))
    try:
        c.register("frame",out)
        c.execute("CREATE TABLE listings_clean AS SELECT * FROM frame")
        c.execute("CREATE UNIQUE INDEX listing_key ON listings_clean(listing_id)")
        c.execute("""CREATE TABLE calendar_clean(listing_id BIGINT,stay_date DATE,available BOOLEAN,
          price_aud DOUBLE,minimum_nights INTEGER,maximum_nights INTEGER,PRIMARY KEY(listing_id,stay_date))""")
        has_price=None
        raw_calendar=0
        for frame in pd.read_csv(RAW/"calendar.csv.gz",chunksize=400000):
            raw_calendar+=len(frame)
            has_price="price" in frame
            cal=pd.DataFrame({"listing_id":frame.listing_id,"stay_date":pd.to_datetime(frame.date),
              "available":frame.available.map({"t":True,"f":False}),
              "price_aud":money(frame.price) if has_price else float("nan"),
              "minimum_nights":frame.get("minimum_nights"),"maximum_nights":frame.get("maximum_nights")})
            c.register("cal",cal)
            c.execute("INSERT OR REPLACE INTO calendar_clean SELECT * FROM cal WHERE listing_id IN (SELECT listing_id FROM listings_clean)")
        audit["raw_calendar_rows"]=raw_calendar
        audit["calendar_has_price_column"]=bool(has_price)
        rev=pd.read_csv(RAW/"reviews.csv.gz",usecols=["id","listing_id","date","comments"])
        rev=rev.rename(columns={"id":"review_id","date":"review_date"}).drop_duplicates("review_id")
        rev["review_date"]=pd.to_datetime(rev.review_date,errors="coerce")
        c.register("rev",rev)
        c.execute("CREATE TABLE reviews_clean AS SELECT * FROM rev WHERE listing_id IN (SELECT listing_id FROM listings_clean)")
        poi=pd.read_csv(ROOT/"data/poi.csv")
        c.register("poi_frame",poi)
        c.execute("CREATE TABLE poi AS SELECT * FROM poi_frame")
        c.execute("CREATE TABLE metadata(key VARCHAR PRIMARY KEY,value VARCHAR)")
        c.executemany("INSERT INTO metadata VALUES (?,?)",[
          ("data_kind","real_public_snapshot"),("snapshot",manifest["snapshot"]),("source_url",manifest["index_url"]),
          ("calendar_has_price",json.dumps(bool(has_price))),("built_at",datetime.now(timezone.utc).isoformat())])
        audit["counts"]={t:c.execute("SELECT COUNT(*) FROM "+t).fetchone()[0] for t in ["listings_clean","calendar_clean","reviews_clean","poi"]}
        audit["calendar_coverage"]=[str(x) for x in c.execute("SELECT MIN(stay_date),MAX(stay_date) FROM calendar_clean").fetchone()]
        audit["calendar_missing_prices"]=c.execute("SELECT COUNT(*) FROM calendar_clean WHERE price_aud IS NULL").fetchone()[0]
        audit["review_date_range"]=[str(x) for x in c.execute("SELECT MIN(review_date),MAX(review_date) FROM reviews_clean").fetchone()]
        c.close()
        if TARGET.exists():
            backup=TARGET.with_name("previous-"+datetime.now().strftime("%Y%m%d-%H%M%S")+".duckdb")
            shutil.copy2(TARGET,backup)
        os.replace(tmp,TARGET)
        (ROOT/"docs/data_audit.json").write_text(json.dumps(audit,ensure_ascii=False,indent=2))
        print(json.dumps(audit["counts"]), "calendar price present:",has_price)
    except Exception:
        c.close()
        raise
if __name__=="__main__": build()
