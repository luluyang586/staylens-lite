"""Scores use an independent whole-market reference, never filtered candidates."""
import numpy as np
import pandas as pd
def add_bayesian_rating(df,city_mean,minimum_reviews=20):
    out=df.copy()
    prior=city_mean if city_mean is not None and np.isfinite(city_mean) else 4.0
    ratings=pd.to_numeric(out.rating_5,errors="coerce")
    counts=pd.to_numeric(out.number_of_reviews,errors="coerce").fillna(0).clip(lower=0)
    # Missing rating has no evidence irrespective of stored review count.
    counts=counts.where(ratings.notna(),0)
    out["adjusted_rating"]=(counts*ratings.fillna(prior)+minimum_reviews*prior)/(counts+minimum_reviews)
    out["rating_score"]=out.adjusted_rating/5*100
    return out
def add_price_score(df,reference):
    out=df.copy(); values=[];medians=[];sizes=[];bases=[]
    for row in out.itertuples():
        ref=reference[(reference.neighbourhood==row.neighbourhood)&(reference.room_type==row.room_type)]
        near=ref[(ref.accommodates-row.accommodates).abs()<=1]
        basis="区域/房型/人数±1"
        if len(near)<5:near=ref;basis="区域/房型（人数可比样本不足）"
        if len(near)<5:near=reference[reference.room_type==row.room_type];basis="全市同房型（区域样本不足）"
        p=near.reference_price.dropna()
        if len(p)==0:score=50.;median=float("nan")
        else:
            # Midrank percentile handles ties; lower comparable prices score higher.
            percentile=((p<row.avg_nightly_price_aud).sum()+0.5*(p==row.avg_nightly_price_aud).sum())/len(p)
            score=100*(1-percentile);median=float(p.median())
        values.append(score);medians.append(median);sizes.append(len(p));bases.append(basis)
    out["price_score"]=values;out["reference_median_price"]=medians
    out["reference_n"]=sizes;out["reference_basis"]=bases
    return out
