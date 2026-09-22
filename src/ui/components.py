"""Reusable Streamlit rendering helpers."""
from __future__ import annotations

import json
import pandas as pd
import streamlit as st


def render_intent(intent, mode: str) -> None:
    with st.expander(f"结构化需求 · {mode}", expanded=False):
        st.json(json.loads(intent.model_dump_json()))


def _evidence_lines(items: object) -> list[str]:
    if not isinstance(items, list):
        return []
    return [f"{x.get('date', '')} [{x.get('category', '')}] {x.get('text', '')}" for x in items if isinstance(x, dict)]


def render_recommendations(df: pd.DataFrame) -> None:
    if df.empty:
        st.info("没有可展示的推荐结果。")
        return
    map_df = df[["latitude", "longitude"]].dropna().rename(columns={"latitude": "lat", "longitude": "lon"})
    if not map_df.empty:
        st.map(map_df, size=70)
    for _, row in df.iterrows():
        with st.container(border=True):
            st.subheader(f"#{int(row['rank'])}  {row['listing_name']}")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("综合得分", f"{row['final_score']:.1f}")
            c2.metric("快照基础价", f"A${row['avg_nightly_price_aud']:.0f}")
            c3.metric("贝叶斯评分", f"{row['adjusted_rating']:.2f}/5")
            c4.metric("评论数", f"{int(row['number_of_reviews'])}")
            st.caption(f"{row['neighbourhood']} · {row['room_type']} · {int(row['accommodates'])}人 · {int(row['minimum_nights'])}晚起")
            reasons = [
                f"价格得分 {row['price_score']:.1f}：相对同区域、同房型、相近容量的全市场参照组",
                f"评分得分 {row['rating_score']:.1f}：小样本评分向全市均值收缩",
                f"位置得分 {row['location_score']:.1f}",
                f"评论得分 {row['review_score']:.1f}（已分类 {int(row.get('review_n', 0))} 条）",
            ]
            st.markdown("**可审计的排名依据**")
            for reason in reasons:
                st.markdown(f"- {reason}")
            negatives = _evidence_lines(row.get("negative_evidence", []))
            st.markdown("**负面评论证据**")
            if negatives:
                for item in negatives[:3]:
                    st.markdown(f"- {item}")
            else:
                st.markdown("- 无经模型验证的负面证据；这不等于没有风险。")


def render_analysis_chart(df: pd.DataFrame) -> None:
    if df.empty or len(df.columns) < 2:
        return
    numeric = [c for c in df.columns[1:] if pd.api.types.is_numeric_dtype(df[c])]
    if numeric and len(df) <= 60:
        st.bar_chart(df.set_index(df.columns[0])[numeric[0]])
