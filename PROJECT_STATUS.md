# 项目整理进度

更新时间：2026-06-22

## 当前结论

题源、讲义、考纲已经分开管理。当前题库可以跑基础刷题，但正式可刷池仍偏少；新导入的环球网校中级真题已经完成逐题知识点映射，仍保持 `needs_review=1`，等待抽样复核后再转入可刷池。

## 知识点骨架

三科 2026 中级会计考纲骨架已入库：

| 科目 | 考点 | 知识点 | 要义 |
|---|---:|---:|---|
| 经济法 | 35 | 116 | 116/116 |
| 中级会计实务 | 71 | 197 | 197/197 |
| 财务管理 | 43 | 135 | 135/135 |
| 合计 | 149 | 448 | 448/448 |

## 当前题库

题库总量：2553 道。

| 来源 | 数量 | 状态 |
|---|---:|---|
| PDF阿里质检通过 | 220 | 可刷，已绑定知识点 |
| Claude自编 | 165 | 可刷，已绑定知识点 |
| 环球网校中级真题PDF | 1061 | 待复核，1052/1061 已绑定主知识点 |
| GitHub题源-IDEAFinBench-CPA会计 | 575 | 待复核，CPA相邻题源 |
| GitHub题源-IDEAFinBench-CPA财务成本管理 | 390 | 待复核，CPA相邻题源 |
| GitHub题源-IDEAFinBench-CPA经济法 | 142 | 待复核，CPA相邻题源 |

当前可刷题：385 道。  
当前待复核题：2168 道。

## 环球网校中级真题

下载目录：`C:\Users\xiaoznz\Downloads\zhongji_kuaiji_pdfs`

处理方式：

- 共保留 71 个 PDF。
- 使用文字层轻量解析，不跑全页 VLM。
- 只导入可自动判分的单选、多选、判断题。
- 导入来源：`环球网校中级真题PDF`。
- 导入 1061 道，2 道重复跳过。
- 逐题语义映射完成 1061/1061。
- 已绑定主知识点 1052 道。
- 未绑定 9 道，原因主要是信托、出口退税、题干残缺、科目错分等，现有知识点体系没有合适位置，未硬塞。

三科映射结果：

| 科目 | 已绑定题量 | 覆盖知识点 |
|---|---:|---:|
| 经济法 | 431 | 91 |
| 中级会计实务 | 286 | 112 |
| 财务管理 | 335 | 81 |
| 合计 | 1052 | 284 |

报告：

- `data/imports/reports/_hqwx_zhongji_import_report.json`
- `data/imports/reports/_hqwx_zhongji_semantic_mapping.json`

脚本：

- `backend/scripts/extract_hqwx_zhongji_questions.py`
- `backend/scripts/map_hqwx_zhongji_questions.py`

## 数据与提交

数据库：`mistakegenie.db`

可重建数据包：

- `data/imports/exam_points.jsonl`
- `data/imports/knowledge_points.jsonl`
- `data/imports/questions.jsonl`
- `data/imports/lecture_materials.jsonl`
- `data/imports/reports/`

最近相关提交：

- `17233a9 Import HQWX Zhongji PDF questions`
- `18d72e1 Tighten HQWX knowledge point mapping`
- `1e51e2d Map HQWX questions to knowledge points`

## 下一步

1. 抽样复核 `环球网校中级真题PDF`，合格批次转 `needs_review=0`。
2. 给 app 加科目筛选，避免三科混刷。
3. 继续处理 9 道未映射题：要么补知识点，要么标记为题源异常/科目错分。
4. CPA 相邻题源仍需筛掉不适配中级的题。
5. 可刷池目标仍是每个知识点 10-20 道骨干题。
