# CPMCM 2025 A 论文工程

本目录是 2025 A 题正式论文工程的工作区。当前阶段已经完成可复现论文资产链、章节施工图、Claim Ledger、理论文献层和获奖论文结构学习，再进入正文写作。

## 模板

已选定 2025 华为杯 LaTeX 模板作为版式基线：

`resources/paper_templates/candidates/04_gmcm_2025_overleaf/`

主文件示例：`MathModel.tex`；编译示例：`MathModel.pdf`。

正式论文不会直接修改第三方 submodule。待 2026 官方《竞赛论文标准文档》发布后，再把所选模板的必要版式迁入本目录并逐项校准。

## 单一可信数据源

论文中的数值、表格和数据图只读取已经验收并进入 `main` 的正式结果：

- Q1: `results/q1_promoted/q1_promoted_summary.csv`
- Q2: `results/q2_optimized/q2_optimized_summary.csv`
- Q3: `results/q3_formal_fixed_traffic/q3_formal_fixed_traffic_summary.csv`
- Q3 Pareto: `results/q3_pareto/q3_refined_official_frontier.csv`

不在论文脚本中重新求解模型，不手抄正式指标。

## 写作结构与证据约束

- 章节施工图：[`manuscript/OUTLINE.md`](manuscript/OUTLINE.md)
- 关键结论证据账本：[`manuscript/CLAIM_LEDGER.md`](manuscript/CLAIM_LEDGER.md)
- 2025 A 题获奖论文结构学习：[`manuscript/STYLE_STUDY.md`](manuscript/STYLE_STUDY.md)
- 图表规划：[`ASSET_PLAN.md`](ASSET_PLAN.md)

核心写作原则是：三问形成“逻辑调度 → 物理内存 → 时间流水”的统一递进；正文六组 case 优先合表/合图，详细结果和诊断资产进入附录；任何 `best-known / promoted / locally saturated` 结论都不能越界写成全局最优。

## 参考文献层

参考文献已经建立并纳入 CI：

- `references/references.bib`
- `references/REFERENCE_MAP.md`
- `references/SOURCE_AUDIT.md`
- `references/validate_references.py`

BibTeX 条目必须能回到 DOI / arXiv / 出版来源，并且在 `REFERENCE_MAP.md` 中说明“支持什么、不能支持什么”。

## 目录

```text
paper/
├─ README.md
├─ ASSET_PLAN.md
├─ Makefile
├─ figures/
│  ├─ scripts/generate_figures.py
│  └─ generated/        # 数据图，PDF + PNG
├─ tables/
│  ├─ scripts/generate_tables.py
│  └─ generated/        # LaTeX tabular 片段
├─ diagrams/
│  ├─ scripts/generate_diagrams.py
│  └─ generated/        # 方法框图，PDF + PNG
├─ references/          # BibTeX、来源审计与引用映射
└─ manuscript/          # 章节施工图、Claim Ledger、结构学习与正式 tex 工程
```

## 本地生成资产

从仓库根目录：

```bash
python -m pip install matplotlib
make -C problems/CPMCM/2025/A/paper assets
```

当前生成内容包括：

- Q1 六组 promoted 峰值驻留量图；
- Q2 六组 SPILL 次数 / extra traffic 图；
- Q3 fixed-traffic 改善百分比图；
- **Q3 `raw → formal core → post-pass final` 阶段贡献分解图；**
- Q3 promoted-Q2 raw cycles 与 final-Q3 cycles 对比图；
- FA1 refined Traffic–Cycles 局部权衡图；
- Q3 全局 Pareto 诊断图；
- D1 三问统一 solution pipeline 方法图；
- D2 Q2 buffer 生命周期/SPILL 机制图；
- Q1/Q2/Q3 三张详细 LaTeX 表；
- 一张跨 Q1/Q2/Q3 的 consolidated key-results 表；
- FA1 trade-off 精确数值表。

所有数据图和方法图同时输出矢量 `PDF` 和预览 `PNG`。Paper Assets workflow 会同时验证图表、方法图和 bibliography metadata。
