"""Reusable, user-facing Streamlit rendering helpers."""
from __future__ import annotations

import pandas as pd
import streamlit as st


ROOM_LABELS = {
    "Entire home/apt": "整套房源",
    "Private room": "独立房间",
    "Shared room": "合住房间",
    "Hotel room": "酒店房间",
}
PREFERENCE_LABELS = {
    "quiet": "安静",
    "clean": "干净",
    "safe": "安全感",
    "near_transit": "靠近公共交通",
}


def render_intent(intent) -> None:
    budget_label = "每晚" if intent.budget_type.value == "per_night" else "全程"
    parts = [
        f"{intent.guests} 人",
        f"{intent.nights} 晚",
        f"{budget_label}不超过 A${intent.budget_amount:,.0f}",
    ]
    if intent.room_type_preference:
        parts.append(ROOM_LABELS.get(intent.room_type_preference, intent.room_type_preference))
    if intent.preferred_neighbourhoods:
        parts.append("区域：" + "、".join(intent.preferred_neighbourhoods))
    if intent.target_pois:
        place = "、".join(intent.target_pois)
        distance = f"（{intent.max_distance_km:g} 公里内）" if intent.max_distance_km else ""
        parts.append(f"靠近 {place}{distance}")
    if intent.soft_preferences:
        labels = [PREFERENCE_LABELS.get(x, x) for x in intent.soft_preferences]
        parts.append("偏好：" + "、".join(labels))
    with st.expander("本次筛选条件", expanded=False):
        st.write(" · ".join(parts))


def _evidence_lines(items: object) -> list[str]:
    if not isinstance(items, list):
        return []
    return [
        str(x.get("text", "")).strip()
        for x in items
        if isinstance(x, dict) and str(x.get("text", "")).strip()
    ]


def render_recommendations(df: pd.DataFrame) -> None:
    if df.empty:
        st.info("没有可展示的推荐结果。")
        return

    map_df = df[["latitude", "longitude"]].dropna().rename(
        columns={"latitude": "lat", "longitude": "lon"}
    )
    if not map_df.empty:
        st.map(map_df, size=70)

    for _, row in df.iterrows():
        with st.container(border=True):
            st.subheader(f"{int(row['rank'])}. {row['listing_name']}")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("推荐分", f"{row['final_score']:.1f}")
            c2.metric("每晚基础价", f"A${row['avg_nightly_price_aud']:.0f}")
            c3.metric("参考评分", f"{row['adjusted_rating']:.2f}/5")
            c4.metric("住客评论", f"{int(row['number_of_reviews'])} 条")

            room = ROOM_LABELS.get(row["room_type"], row["room_type"])
            st.caption(
                f"{row['neighbourhood']} · {room} · 最多 {int(row['accommodates'])} 人 · "
                f"{int(row['minimum_nights'])} 晚起住"
            )

            reasons = []
            if row["price_score"] >= 65:
                reasons.append("在相似区域和房型中，价格具有一定优势")
            if row["rating_score"] >= 70:
                reasons.append("综合评分和评论数量表现较稳健")
            if row["location_score"] >= 70:
                reasons.append("与目标地点的距离较符合你的要求")
            if row["review_score"] >= 70 and int(row.get("review_n", 0)) >= 3:
                reasons.append("近期评论中需要特别关注的问题相对较少")
            if not reasons:
                reasons.append("综合考虑预算、评分和位置后排名靠前")

            st.markdown("**推荐理由**")
            for reason in reasons[:3]:
                st.markdown(f"- {reason}")

            negatives = _evidence_lines(row.get("negative_evidence", []))
            if negatives:
                with st.expander("评论中值得留意的内容"):
                    for item in negatives[:3]:
                        st.markdown(f"> {item}")

            listing_url = row.get("listing_url")
            if isinstance(listing_url, str) and listing_url.startswith("http"):
                st.link_button("查看房源原始页面", listing_url)


def render_analysis_chart(df: pd.DataFrame) -> None:
    if df.empty or len(df.columns) < 2:
        return
    numeric = [c for c in df.columns[1:] if pd.api.types.is_numeric_dtype(df[c])]
    if numeric and len(df) <= 60:
        st.bar_chart(df.set_index(df.columns[0])[numeric[0]])
