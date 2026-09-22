"""StayLens Lite: a clear, evidence-backed accommodation decision experience."""
from __future__ import annotations

import streamlit as st

from src.analytics.scoring import DEFAULT_WEIGHTS
from src.config import settings
from src.database.connection import database_exists, metadata
from src.database.query_builder import get_pois, list_neighbourhoods
from src.llm.text_to_sql import EXAMPLES, run_analysis
from src.models.intent import BudgetType, StayIntent
from src.ui.components import render_analysis_chart, render_intent, render_recommendations
from src.workflow.recommendation import run_recommendation


st.set_page_config(page_title="StayLens · 悉尼住宿分析", page_icon="🏡", layout="wide")

st.title("🏡 StayLens")
st.markdown("### 用真实公开数据，快速比较悉尼住宿选择")
st.caption("输入预算和偏好，获得兼顾价格、评价与位置的候选房源。")

if not database_exists():
    st.error("暂时无法读取住宿数据，请稍后再试。")
    st.stop()

meta = metadata()
llm_enabled = settings.has_llm
data_kind = meta.get("data_kind")
data_label = {
    "real_public_snapshot": "悉尼公开房源完整快照",
    "real_public_sample": "悉尼公开房源演示样本",
}.get(data_kind, "悉尼住宿数据")

with st.sidebar:
    st.header("使用说明")
    st.markdown(f"**数据版本**  \n{data_label} · {meta.get('snapshot', '日期未知')}")
    smart_input_label = "可用" if llm_enabled else "当前未启用，可使用筛选表单"
    st.markdown(f"**智能输入**  \n{smart_input_label}")
    st.divider()
    st.caption("当前价格是数据快照中的基础价，不代表指定日期的实时可订价格，也可能不含税费和清洁费。")
    if data_kind == "real_public_sample":
        st.caption("在线版本使用真实公开数据的抽样样本，适合功能体验，不代表悉尼全部房源。")

recommend_tab, analyst_tab, about_tab = st.tabs(["✨ 找住宿", "📊 市场洞察", "ℹ️ 数据说明"])

with recommend_tab:
    st.subheader("告诉我你的住宿需求")
    input_options = ["筛选条件"] + (["直接描述"] if llm_enabled else [])
    mode = st.segmented_control("输入方式", input_options, default="筛选条件")
    submitted = False

    if mode == "筛选条件":
        areas = list_neighbourhoods()
        poi_df = get_pois()
        room_options = {
            "不限": None,
            "整套房源": "Entire home/apt",
            "独立房间": "Private room",
            "合住房间": "Shared room",
            "酒店房间": "Hotel room",
        }
        preference_options = {
            "安静": "quiet",
            "干净": "clean",
            "安全感": "safe",
            "靠近公共交通": "near_transit",
        }

        with st.form("stay_form"):
            c1, c2, c3 = st.columns(3)
            guests = c1.number_input("入住人数", 1, 30, 2)
            nights = c2.number_input("入住晚数", 1, 90, 3)
            budget = c3.number_input("预算（澳元）", 1.0, value=250.0)

            c4, c5 = st.columns(2)
            budget_type = c4.radio("预算方式", ["每晚预算", "全程预算"], horizontal=True)
            room_label = c5.selectbox("房型", list(room_options))

            selected_areas = st.multiselect("偏好的区域", areas, placeholder="不选择则比较所有区域")
            selected_pois = st.multiselect(
                "希望靠近的地点",
                poi_df.poi_name.tolist(),
                placeholder="可选择景点或交通枢纽",
            )
            max_distance = st.number_input(
                "距离上限（公里，0 表示不限）", 0.0, 100.0, 0.0, 0.5
            )
            selected_preferences = st.multiselect(
                "你更在意什么？", list(preference_options), placeholder="可多选"
            )

            with st.expander("调整排序偏好（可选）"):
                st.caption("数值越高，排序时越重视该因素。")
                w1, w2, w3, w4 = st.columns(4)
                wp = w1.slider("价格", 0, 100, 35)
                wr = w2.slider("住客评分", 0, 100, 30)
                wl = w3.slider("位置", 0, 100, 20)
                wv = w4.slider("评论表现", 0, 100, 15)

            submitted = st.form_submit_button(
                "查看推荐", type="primary", width="stretch"
            )

        if submitted:
            room = room_options[room_label]
            hard = ["budget", "guests", "nights"]
            if room:
                hard.append("room_type")
            if selected_areas:
                hard.append("neighbourhood")
            if max_distance > 0:
                hard.append("distance")
            intent = StayIntent(
                nights=nights,
                budget_amount=budget,
                budget_type=(
                    BudgetType.PER_NIGHT if budget_type == "每晚预算" else BudgetType.TOTAL
                ),
                guests=guests,
                room_type_preference=room,
                preferred_neighbourhoods=selected_areas,
                target_pois=selected_pois,
                max_distance_km=max_distance or None,
                hard_preferences=hard,
                soft_preferences=[preference_options[x] for x in selected_preferences],
            )
            total = wp + wr + wl + wv
            weights = DEFAULT_WEIGHTS if total == 0 else {
                "price_score": wp / total,
                "rating_score": wr / total,
                "location_score": wl / total,
                "review_score": wv / total,
            }
            result = run_recommendation(
                intent_override=intent, use_llm=llm_enabled, weights=weights
            )
    else:
        st.caption("可以用一句话描述人数、晚数、预算、区域和偏好。")
        user_message = st.text_area(
            "住宿需求",
            placeholder="例如：两个人住三晚，每晚不超过 250 澳元，希望靠近歌剧院并且环境安静。",
            height=120,
        )
        submitted = st.button("理解需求并推荐", type="primary", width="stretch")
        if submitted:
            result = run_recommendation(user_message, use_llm=True)

    if submitted:
        render_intent(result.intent)
        if result.status != "ok":
            st.warning(result.message or "暂时没有找到合适的结果，请调整条件后再试。")
        else:
            st.success(f"找到 {result.candidates_found} 个符合条件的房源，优先展示 5 个。")
            for warning in result.warnings:
                st.warning(warning)
            render_recommendations(result.recommendations)
            st.download_button(
                "下载推荐结果",
                result.recommendations.to_csv(index=False).encode("utf-8-sig"),
                "staylens_results.csv",
                "text/csv",
            )

with analyst_tab:
    st.subheader("看看悉尼住宿市场")
    st.caption("选择常见问题，或在启用智能输入后提出自己的问题。")
    fixed = st.selectbox("你想了解什么？", list(EXAMPLES))
    custom = st.text_input(
        "也可以直接提问",
        placeholder="例如：哪些区域的整套房源价格较高？",
        disabled=not llm_enabled,
    )
    if not llm_enabled:
        st.caption("当前可使用上方预设问题；直接提问功能尚未启用。")
    if st.button("查看分析", type="primary", width="stretch"):
        analysis = run_analysis(custom if custom else fixed, use_llm=bool(custom))
        if analysis.status != "ok":
            st.warning(analysis.reason or "这个问题暂时无法回答，请换一种问法。")
        else:
            render_analysis_chart(analysis.data)
            st.dataframe(analysis.data, width="stretch", hide_index=True)
            st.download_button(
                "下载分析结果",
                analysis.data.to_csv(index=False).encode("utf-8-sig"),
                "market_analysis.csv",
                "text/csv",
            )

with about_tab:
    st.subheader("这份结果应该怎样理解？")
    st.markdown(
        f"""
**数据来源**

[Inside Airbnb](https://insideairbnb.com/get-the-data/) 悉尼公开数据，快照日期为 **{meta.get('snapshot', '未知')}**。

**适合用来做什么**

比较区域、房型、基础价格、评分和评论表现，帮助缩小住宿选择范围。

**需要注意什么**

- 这里不是实时预订系统，不能确认某个日期是否可订。
- 页面显示的是快照基础价，最终支付价格可能包含税费、清洁费或其他费用。
- 地点距离是直线距离，不等于步行、驾车或公共交通时间。
- 评论分析用于提示可能的关注点；没有发现负面内容不代表完全没有风险。
- 推荐结果仅供比较和研究，预订前请回到住宿平台核对最新信息。
"""
    )
