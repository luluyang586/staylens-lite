"""Hard constraints and complete price checks. No truncation before geo scoring."""
import pandas as pd
from src.database.connection import connect
from src.models.intent import SearchMode,BudgetType
def build_recommendation_query(intent):
    if intent.needs_clarification: raise ValueError(intent.clarification_question)
    cond=["l.accommodates >= ?","l.minimum_nights <= ?",
          "(l.maximum_nights IS NULL OR l.maximum_nights >= ?)"]
    params=[intent.guests,intent.nights,intent.nights]
    if intent.room_type_preference:
        cond.append("l.room_type = ?");params.append(intent.room_type_preference)
    if intent.preferred_neighbourhoods:
        cond.append("l.neighbourhood IN ("+",".join("?" for _ in intent.preferred_neighbourhoods)+")")
        params.extend(intent.preferred_neighbourhoods)
    if intent.search_mode==SearchMode.EXPLORATION:
        cond+=["l.base_price_aud > 0","l.base_price_aud <= ?"]
        params.append(intent.nightly_budget)
        return ("SELECT l.*,l.base_price_aud AS avg_nightly_price_aud, "
                "l.base_price_aud * ? AS total_price_aud FROM listings_clean l WHERE "+
                " AND ".join(cond)),[intent.nights]+params
    cond+=["c.stay_date >= ?","c.stay_date < ?"]
    params.extend([intent.check_in_date,intent.check_out_date])
    price_filter="MAX(c.price_aud) <= ?" if intent.budget_type==BudgetType.PER_NIGHT else "SUM(c.price_aud) <= ?"
    sql="""SELECT l.*,AVG(c.price_aud) AS avg_nightly_price_aud,SUM(c.price_aud) AS total_price_aud
      FROM listings_clean l JOIN calendar_clean c ON l.listing_id=c.listing_id
      WHERE """+" AND ".join(cond)+"""
      GROUP BY ALL
      HAVING COUNT(DISTINCT c.stay_date)=?
        AND COUNT(DISTINCT CASE WHEN c.available THEN c.stay_date END)=?
        AND COUNT(c.price_aud)=?
        AND MIN(c.price_aud)>0
        AND MAX(CASE WHEN c.stay_date=? THEN COALESCE(c.minimum_nights,l.minimum_nights) END)<=?
        AND MAX(CASE WHEN c.stay_date=? THEN COALESCE(c.maximum_nights,l.maximum_nights) END)>=?
        AND """+price_filter
    params.extend([intent.nights,intent.nights,intent.nights,intent.check_in_date,intent.nights,
                   intent.check_in_date,intent.nights,intent.budget_amount])
    return sql,params
def search_candidates(intent):
    sql,params=build_recommendation_query(intent)
    with connect() as c:return c.execute(sql,params).fetchdf()
def get_pois(names=None):
    with connect() as c:
        df=c.execute("SELECT * FROM poi ORDER BY poi_id").fetchdf()
    return df if names is None else df[df.poi_name.str.casefold().isin([n.casefold() for n in names])]
def get_recent_reviews(listing_ids,per_listing=20):
    ids=[int(x) for x in listing_ids]
    if not ids:return pd.DataFrame(columns=["review_id","listing_id","review_date","comments"])
    sql="""SELECT review_id,listing_id,review_date,comments FROM reviews_clean
      WHERE listing_id IN ("""+",".join("?" for _ in ids)+""") AND comments IS NOT NULL
      AND LENGTH(TRIM(comments))>0
      QUALIFY ROW_NUMBER() OVER(PARTITION BY listing_id ORDER BY review_date DESC,review_id DESC)<=?
      ORDER BY listing_id,review_date DESC"""
    with connect() as c:return c.execute(sql,ids+[per_listing]).fetchdf()
def list_neighbourhoods():
    with connect() as c:return [r[0] for r in c.execute("SELECT DISTINCT neighbourhood FROM listings_clean ORDER BY 1").fetchall()]
def market_reference(intent):
    if intent.search_mode==SearchMode.EXPLORATION:
        with connect() as c:return c.execute("SELECT listing_id,neighbourhood,room_type,accommodates,base_price_aud AS reference_price,rating_5 FROM listings_clean WHERE base_price_aud>0").fetchdf()
    # No budget/capacity/availability filter: comparable whole-market date price basis.
    with connect() as c:
        return c.execute("""SELECT l.listing_id,l.neighbourhood,l.room_type,l.accommodates,l.rating_5,
          AVG(c.price_aud) reference_price FROM listings_clean l JOIN calendar_clean c ON c.listing_id=l.listing_id
          WHERE c.stay_date>=? AND c.stay_date<? GROUP BY ALL
          HAVING COUNT(DISTINCT c.stay_date)=? AND COUNT(c.price_aud)=? AND MIN(c.price_aud)>0""",
          [intent.check_in_date,intent.check_out_date,intent.nights,intent.nights]).fetchdf()
def city_rating():
    with connect() as c:return c.execute("SELECT AVG(rating_5) FROM listings_clean WHERE rating_5 BETWEEN 0 AND 5").fetchone()[0]
def date_support(intent):
    with connect() as c:
        lo,hi=c.execute("SELECT MIN(stay_date),MAX(stay_date) FROM calendar_clean").fetchone()
        if intent.check_in_date<lo or intent.check_out_date>hi+__import__("datetime").timedelta(days=1):
            return "date_out_of_coverage",f"数据日历覆盖 {lo} 至 {hi}，无法验证所选日期。"
        n=c.execute("SELECT COUNT(price_aud) FROM calendar_clean WHERE stay_date>=? AND stay_date<?",
                    [intent.check_in_date,intent.check_out_date]).fetchone()[0]
        if n==0:return "date_price_unavailable","该快照没有所选日期的每日价格，无法验证预算或总价。请显式切换市场探索；不会用基础价代替。"
    return None,None
