"""Transparent scoring, comparable-market prices and stable tie breaks."""
import numpy as np
from src.analytics.rating import add_bayesian_rating,add_price_score
DEFAULT_WEIGHTS={"price_score":.35,"rating_score":.30,"location_score":.20,"review_score":.15}
def pre_score_candidates(df,intent,reference,city_mean):
    if df.empty:return df.copy()
    out=add_bayesian_rating(add_price_score(df,reference),city_mean)
    d=out["distance_km"]
    loc=(100*(1-d/intent.max_distance_km)).clip(0,100) if intent.max_distance_km else 100*np.exp(-d/3)
    out["location_score"]=loc.fillna(50)
    if "transit_distance_km" in out:
        transit=(100*np.exp(-out.transit_distance_km/1)).fillna(50)
        out["location_score"]=(out.location_score+transit)/2 if intent.target_pois else transit
    return out
def rank_candidates(df,weights=None):
    weights=weights or DEFAULT_WEIGHTS
    if set(weights)!=set(DEFAULT_WEIGHTS) or any(not np.isfinite(v) or v<0 for v in weights.values()) or abs(sum(weights.values())-1)>1e-8:
        raise ValueError("Four non-negative weights must sum to 1")
    out=df.copy()
    out["final_score"]=sum(out[k]*v for k,v in weights.items())
    out=out.sort_values(["final_score","number_of_reviews","avg_nightly_price_aud","listing_id"],
                       ascending=[False,False,True,True]).reset_index(drop=True)
    out["rank"]=np.arange(1,len(out)+1)
    return out
def final_score_candidates(df,features=None,weights=None):
    out=df.copy()
    if features is not None and not features.empty:
        out=out.drop(columns=["review_score"],errors="ignore").merge(features,on="listing_id",how="left")
    for col,default in [("review_score",50.),("review_coverage",0.),("review_n",0)]:
        if col not in out:out[col]=default
        out[col]=out[col].fillna(default)
    for col in ["negative_evidence","positive_evidence"]:
        if col not in out:out[col]=[[] for _ in range(len(out))]
        out[col]=out[col].map(lambda x:x if isinstance(x,list) else [])
    return rank_candidates(out,weights)
