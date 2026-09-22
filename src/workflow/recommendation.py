"""Evidence-backed recommendation workflow with explicit blocking states."""
from dataclasses import dataclass,field
from datetime import datetime,timezone
import json,uuid
import numpy as np
import pandas as pd
from src.config import ROOT,settings
from src.models.intent import StayIntent
from src.database.connection import metadata
from src.database.query_builder import (search_candidates,get_pois,get_recent_reviews,market_reference,
                                       city_rating,date_support,build_recommendation_query,list_neighbourhoods)
from src.analytics.geospatial import haversine_km
from src.analytics.scoring import pre_score_candidates,final_score_candidates,DEFAULT_WEIGHTS
from src.analytics.review_risk import listing_review_features
from src.llm.intent_parser import parse_intent
from src.llm.review_tagger import tag_reviews
@dataclass
class RecommendationResult:
    intent:StayIntent
    status:str
    message:str|None=None
    recommendations:pd.DataFrame=field(default_factory=pd.DataFrame)
    candidates_found:int=0
    intent_mode:str="form"
    review_mode:str="not_run"
    warnings:list[str]=field(default_factory=list)
    source:dict=field(default_factory=dict)
    trace:dict=field(default_factory=dict)
def run_recommendation(user_message="",use_llm=False,intent_override=None,weights=None,previous=None,persist=True):
    intent,mode=(intent_override,"form") if intent_override is not None else parse_intent(user_message,previous)
    result=RecommendationResult(intent,"pending",intent_mode=mode,source=metadata())
    def finish(status,message=None):
        result.status=status;result.message=message
        result.trace.update({"run_id":str(uuid.uuid4()),"timestamp":datetime.now(timezone.utc).isoformat(),
          "source":result.source,"intent":intent.model_dump(mode="json"),"status":status,"message":message,
          "warnings":result.warnings,"review_mode":result.review_mode,"weights":weights or DEFAULT_WEIGHTS})
        if not result.recommendations.empty:
            result.trace["results"]=json.loads(result.recommendations.to_json(orient="records",date_format="iso"))
        if persist:
            folder=ROOT/"data/runs";folder.mkdir(exist_ok=True,parents=True)
            (folder/(result.trace["run_id"]+".json")).write_text(json.dumps(result.trace,ensure_ascii=False,indent=2,default=str))
        return result
    if intent.needs_clarification:return finish("needs_clarification",intent.clarification_question)
    data_kind=result.source.get("data_kind")
    if data_kind not in {"real_public_snapshot","real_public_sample"}:
        return finish("data_unverified","数据缺少真实快照来源记录，禁止当作真实房源展示。")
    if data_kind=="real_public_sample":
        result.warnings.append("当前使用真实公开快照的确定性抽样演示库；结果不代表悉尼全量房源。")
    unsupported=set(intent.hard_preferences)-{"budget","guests","nights","room_type","location","distance","neighbourhood"}
    if unsupported:return finish("unsupported_constraints","无法验证硬性要求："+", ".join(sorted(unsupported)))
    missing_areas=set(intent.preferred_neighbourhoods)-set(list_neighbourhoods())
    if missing_areas:return finish("unknown_area","数据中没有这些区域："+", ".join(sorted(missing_areas)))
    pois=get_pois()
    lookup={str(r.poi_name).casefold():r for r in pois.itertuples()}
    unknown=[p for p in intent.target_pois if p.casefold() not in lookup]
    if unknown:return finish("unknown_poi","无法定位："+", ".join(unknown)+"。请使用地点列表选择；距离要求未被忽略。")
    if intent.check_in_date:
        state,msg=date_support(intent)
        if state:return finish(state,msg)
    query,params=build_recommendation_query(intent)
    result.trace["query"]={"sql":query,"parameters":[str(p) for p in params]}
    df=search_candidates(intent)
    if df.empty:
        return finish("no_results","没有满足全部硬约束的房源。软偏好仅用于排名，放宽它们不会增加候选；请自行调整预算、人数、房型或区域后重试。")
    df["distance_km"]=np.nan
    if intent.target_pois:
        dist=[]
        for name in intent.target_pois:
            point=lookup[name.casefold()]
            dist.append(haversine_km(df.latitude.to_numpy(),df.longitude.to_numpy(),point.latitude,point.longitude))
        # Multiple POIs are all requirements: score the farthest one.
        df["distance_km"]=np.max(np.vstack(dist),axis=0)
        df["target_poi"]=", ".join(intent.target_pois)
        if intent.max_distance_km:df=df[df.distance_km<=intent.max_distance_km].copy()
    if "near_transit" in intent.soft_preferences and not df.empty:
        stations=pois[pois.poi_type=="transit"]
        if stations.empty:return finish("transit_data_unavailable","交通偏好无法评价：没有车站数据。")
        distances=np.vstack([haversine_km(df.latitude.to_numpy(),df.longitude.to_numpy(),r.latitude,r.longitude) for r in stations.itertuples()])
        df["transit_distance_km"]=np.min(distances,axis=0)
        result.warnings.append("交通便利度仅比较预置的4个车站近似坐标，不覆盖悉尼完整交通网络。")
    if df.empty:return finish("no_results","所有候选均不满足距离硬约束；请明确修改距离上限。")
    result.candidates_found=len(df)
    reference=market_reference(intent)
    df=pre_score_candidates(df,intent,reference,city_rating())
    first=final_score_candidates(df,weights=weights).head(20).copy()
    reviews=get_recent_reviews(first.listing_id,20)
    records=reviews[["review_id","comments"]].to_dict("records")
    tagged,review_mode,warnings=tag_reviews(records,use_llm)
    result.review_mode=review_mode;result.warnings.extend(warnings)
    features=listing_review_features(reviews,tagged,intent.soft_preferences,
                                     as_of=datetime.now(timezone.utc).date())
    ranked=final_score_candidates(first,features,weights)
    result.recommendations=ranked.head(5)
    result.trace["two_stage_scope"]="Top 5 within structural Top 20; not a globally optimal rerank of all reviews"
    return finish("ok")
