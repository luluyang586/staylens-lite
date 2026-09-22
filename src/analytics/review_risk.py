"""Time-decayed negative-review rate; no self-reported probability weights."""
import math
import pandas as pd
def listing_review_features(reviews,tagged_reviews,soft_preferences=None,as_of=None):
    columns=["listing_id","review_score","review_coverage","negative_evidence","positive_evidence","review_n"]
    if reviews.empty:return pd.DataFrame(columns=columns)
    as_of=pd.Timestamp(as_of).normalize() if as_of else pd.Timestamp.now(tz="UTC").tz_localize(None).normalize()
    tags={t.review_id:t.tags for t in tagged_reviews}
    preferred={"quiet":"noise","clean":"cleanliness","safe":"safety"}
    focus={preferred[p] for p in soft_preferences or [] if p in preferred}
    rows=[]
    for lid,group in reviews.groupby("listing_id"):
        num=den=0.; pos=[];neg=[];valid=0
        for r in group.itertuples():
            if int(r.review_id) not in tags:continue
            valid+=1
            ts=pd.Timestamp(r.review_date)
            days=max((as_of-ts).days,0)
            weight=math.exp(-days/365)
            rt=tags[int(r.review_id)]
            negative=any(t.sentiment in ("negative","mixed") for t in rt)
            if any(t.category in focus and t.sentiment in ("negative","mixed") for t in rt):weight*=2
            num+=weight*negative;den+=weight
            for t in rt:
                item={"review_id":int(r.review_id),"date":str(ts.date()),"category":t.category,"text":t.evidence}
                if t.sentiment in ("negative","mixed"):neg.append(item)
                if t.sentiment in ("positive","mixed"):pos.append(item)
        score=100*(1-num/den) if den else 50
        # Insufficient observations explicitly neutral; never equate missing tags with safety.
        if valid<3:score=50
        rows.append({"listing_id":int(lid),"review_score":score,"review_coverage":valid/len(group),
                     "negative_evidence":neg[:6],"positive_evidence":pos[:6],"review_n":valid})
    return pd.DataFrame(rows,columns=columns)
