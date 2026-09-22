# Evaluation policy

本目录只保留可复核的最终评测资产，不保留已被取代的提示词迭代和临时报告。

## 确定性评测

```bash
python scripts/run_evaluation.py
```

该脚本运行端到端场景和 SQL 安全边界测试，写入 `latest_report.json`；同时读取已保存的真实 LLM 报告并汇总，**不会发起 API 调用或编造模型分数**。

## 冻结 final-v2

- `intent_final_v2_cases.json`：100 题，覆盖八类意图表达。
- `sql_final_v2_cases.json`：50 题，其中 38 题可回答、12 题应拒绝。
- `final_v2_manifest.json`：冻结时的数据集与提示词 SHA-256。
- `llm_intent_final_v2_report.json`、`llm_sql_final_v2_report.json`：一次性真实 API 运行的逐题结果与 token 用量。

结果：Intent 95% 整题正确、97.16% 字段正确；SQL 96% 状态/执行正确、82% 输出契约正确、78% 语义结果正确。执行发生在提示词与数据集冻结后，没有依据 final-v2 结果调参或重跑。详见 `FINAL_V2_EVALUATION_REPORT.md`。

若确需复现付费调用：

```bash
python scripts/run_llm_evaluation.py --suite intent_final_v2 --confirm-live-calls
python scripts/run_llm_evaluation.py --suite sql_final_v2 --confirm-live-calls
```

运行器默认拒绝覆盖最终报告。添加 `--allow-final-rerun` 才能覆盖，且新结果必须标记为复跑，不能冒充原始 one-shot。

## 评论分析评测

`review_reference_v1.json` 包含 55 条真实评论、138 个主题/情感参考标签及 5 个空标签对照；所有 evidence 均经程序验证为评论原文精确子串。标注来源是 **Codex-assisted curated reference labels; not human-labelled**。

一次性 `gpt-4o-mini` 结果保存在 `llm_review_reference_v1_report.json`：严格主题+情感微平均 F1 63.48%，原文证据合规率 89.13%。它是用于作品集诊断的临时参考基准，不能表述为人工金标准。详见 `REVIEW_EVALUATION_REPORT.md`。

## 文件保留原则

最终资产包含 final-v2 数据集、manifest、模型报告、评论参考集、两份正式说明和最新确定性汇总。开发阶段 v1/v2/v3、旧 holdout 和重复汇总已删除，避免读者误把调参历史当成独立最终测试。
