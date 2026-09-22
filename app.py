"""StayLens Lite: evidence-backed Sydney accommodation analysis."""
from __future__ import annotations

from datetime import date
import json
import streamlit as st

from src.config import settings, ROOT
from src.database.connection import database_exists, metadata
from src.database.query_builder import get_pois, list_neighbourhoods
from src.llm.text_to_sql import EXAMPLES, run_analysis
from src.models.intent import BudgetType, StayIntent
from src.analytics.scoring import DEFAULT_WEIGHTS
from src.ui.components import render_analysis_chart, render_intent, render_recommendations
from src.workflow.recommendation import run_recommendation

st.set_page_config(page_title="StayLens Lite", page_icon="🏠", layout="wide")
st.title("🏠 StayLens Lite")
st.caption("真实公开数据 · 硬约束不自动放宽 · 结论可追溯")

if not database_exists():
    st.error("未找到数据库。请先运行下载和建库脚本。")
    st.stop()

meta = metadata()
llm_enabled = settings.has_llm
data_kind = meta.get("data_kind")
with st.sidebar:
    st.header("运行状态")
    data_label = {
        "real_public_snapshot": "已验证真实全量快照",
        "real_public_sample": "真实公开抽样演示库",
    }.get(data_kind, "来源未验证")
    st.write("数据：", data_label)
    st.write("快照日期：", meta.get("snapshot", "unknown"))
    st.write("LLM：", f"已配置 {settings.llm_model}" if llm_enabled else "未配置（不会伪装调用）")
    st.caption("指定日期的可订性与价格必须由日历数据同时验证。本快照缺少每日价格，日期搜索会被阻断。")

if data_kind == "real_public_sample":
    st.info("在线演示使用真实公开快照的确定性抽样，不是虚构数据；全量分析请按 README 构建本地数据库。")

recommend_tab, analyst_tab, audit_tab = st.tabs(["住宿推荐", "商业分析", "数据与审计"])

with recommend_tab:
    mode = st.radio("需求输入", ["结构化表单", "LLM自然语言"], horizontal=True)
    submitted = False
    if mode == "结构化表单":
        areas = list_neighbourhoods()
        poi_df = get_pois()
        with st.form("stay_form"):
            c1, c2, c3 = st.columns(3)
            guests = c1.number_input("入住人数", 1, 30, 2)
            nights = c2.number_input("晚数", 1, 90, 3)
            budget = c3.number_input("预算（AUD）", 1.0, value=250.0)
            budget_type = st.radio("预算口径", ["每晚", "总价"], horizontal=True)
            date_specific = st.checkbox("指定入住日期（当前快照将因无每日价格而阻断）")
            check_in = st.date_input("入住日期", value=date(2026, 7, 1), disabled=not date_specific)
            room = st.selectbox("房型", ["不限", "Entire home/apt", "Private room", "Shared room", "Hotel room"])
            selected_areas = st.multiselect("区域（硬约束）", areas)
            selected_pois = st.multiselect("目标地点（多个时必须全部满足）", poi_df.poi_name.tolist())
            max_distance = st.number_input("目标地点最大直线距离（km，0=不限）", 0.0, 100.0, 0.0, 0.5)
            soft = st.multiselect("软偏好", ["quiet", "clean", "safe", "near_transit"])
            st.markdown("排名权重（系统会归一化）")
            w1, w2, w3, w4 = st.columns(4)
            wp=w1.slider("价格",0,100,35); wr=w2.slider("评分",0,100,30)
            wl=w3.slider("位置",0,100,20); wv=w4.slider("评论",0,100,15)
            submitted = st.form_submit_button("开始分析", type="primary", use_container_width=True)
        if submitted:
            hard = ["budget", "guests", "nights"]
            if room != "不限": hard.append("room_type")
            if selected_areas: hard.append("neighbourhood")
            if max_distance > 0: hard.append("distance")
            intent = StayIntent(check_in_date=check_in if date_specific else None, nights=nights,
                budget_amount=budget, budget_type=BudgetType.PER_NIGHT if budget_type=="每晚" else BudgetType.TOTAL,
                guests=guests, room_type_preference=None if room=="不限" else room,
                preferred_neighbourhoods=selected_areas, target_pois=selected_pois,
                max_distance_km=max_distance or None, hard_preferences=hard, soft_preferences=soft)
            total=wp+wr+wl+wv
            weights=DEFAULT_WEIGHTS if total == 0 else {
                "price_score":wp/total,"rating_score":wr/total,
                "location_score":wl/total,"review_score":wv/total}
            result=run_recommendation(intent_override=intent,use_llm=llm_enabled,weights=weights)
    else:
        if not llm_enabled:
            st.error("未配置 LLM_API_KEY 和 LLM_MODEL；自然语言模式禁用，不会用关键词规则冒充模型。")
        user_message=st.text_area("旅行需求", height=110, disabled=not llm_enabled)
        submitted=st.button("调用LLM并分析", disabled=not llm_enabled, use_container_width=True)
        if submitted:
            result=run_recommendation(user_message,use_llm=True)
    if submitted:
        render_intent(result.intent,result.intent_mode)
        if result.status != "ok":
            st.warning(f"{result.status}: {result.message}")
        else:
            st.success(f"硬约束筛选后 {result.candidates_found} 个候选；展示前 5 个。")
            for warning in result.warnings: st.warning(warning)
            render_recommendations(result.recommendations)
            st.download_button("下载结果 CSV", result.recommendations.to_csv(index=False).encode("utf-8-sig"), "staylens_results.csv", "text/csv")

with analyst_tab:
    st.subheader("只读 Text-to-SQL")
    fixed=st.selectbox("离线可验证问题", list(EXAMPLES))
    custom=st.text_input("或输入自定义问题（需LLM）", disabled=not llm_enabled)
    if st.button("生成、校验并执行SQL", use_container_width=True):
        analysis=run_analysis(custom if custom else fixed,use_llm=bool(custom))
        if analysis.status!="ok": st.warning(analysis.reason)
        else:
            st.caption(f"模式：{analysis.generation_mode}；最多返回200行")
            st.code(analysis.sql,language="sql"); st.dataframe(analysis.data,use_container_width=True)
            render_analysis_chart(analysis.data)
            st.download_button("下载分析 CSV",analysis.data.to_csv(index=False).encode("utf-8-sig"),"analysis.csv","text/csv")

with audit_tab:
    st.subheader("数据来源与局限")
    st.json(meta)
    audit_path=ROOT/"docs/data_audit.json"
    if audit_path.exists(): st.json(json.loads(audit_path.read_text()))
    st.markdown("""
- 房源、日历和评论来自 Inside Airbnb Sydney 公开快照；原文件哈希在 `data/raw/manifest.json`。
- `availability` 不等于真实入住率；基础价不代表某日实时可订价，可能不包含全部税费。
- POI 是人工整理的近似坐标；距离是球面直线距离，不是步行或通勤时间。
- 评论风险只在配置真实LLM后分类；未分类时给中性分，不表示无风险。
""")
