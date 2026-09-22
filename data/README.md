# Data

数据来自 [Inside Airbnb](https://insideairbnb.com/get-the-data/) Sydney, NSW, Australia `2026-06-16` 公开快照，许可为 CC BY 4.0。

## 仓库内数据

- `poi.csv`：人工整理的 10 个悉尼地标/车站近似坐标。
- `staylens_demo.duckdb`：从完整真实快照确定性抽样生成的可部署演示库。按 `neighbourhood × room_type` 以 listing ID 哈希排序，每组最多取 5 个房源；保留所选房源全部日历行和最近 20 条评论。
- 演示库 metadata 明确记录 `data_kind=real_public_sample`、来源、快照、抽样方法和表行数；应用界面会提示它不是全量数据。

它不是合成或手工伪造数据。可使用以下命令从本地全量库重建：

```bash
python scripts/build_demo_database.py
```

## 全量数据

原始大文件不提交 Git：

```bash
python scripts/download_data.py
python scripts/build_database.py
```

下载脚本写入 `data/raw/`，manifest 记录 URL、字节数和 SHA-256；建库脚本生成 `data/staylens.duckdb`。两者均被 `.gitignore` 排除。

## 已知限制

1. 数据是时间点快照，不是实时库存。
2. 日历 `available` 是挂牌状态，不是已验证的真实入住率或订单历史。
3. 数据不含平台交易量、转化率或因果实验指标。
4. 本快照没有日历每日价格列；指定日期价格与总价验证会被阻断。
5. 基础价可能不含税费、服务费或清洁费。
6. POI 距离是球面直线距离，不是步行或公共交通时间。
7. 评论存在选择偏差，评分与评论数只是质量代理变量。
8. 抽样演示结果不代表悉尼全量市场。
