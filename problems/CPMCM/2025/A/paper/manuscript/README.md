# manuscript

2025 A 题 LaTeX 论文已经从“完整结构稿”扩充为一版可持续审阅的比赛论文工作稿，并纳入独立 XeLaTeX CI。

## 当前状态

当前扩充稿共 **47 页 A4**（ctex/Fandol 工作外壳口径），其中正文、参考文献与附录均已形成。页数不是优化目标；本轮新增内容来自模型推导、消融、机制解释、复杂度/可扩展性、验证与附录，而不是通过字号、空白或大段源码撑页数。

正文已覆盖：

- `sections/01_problem.tex`：问题重述；
- `sections/02_assumptions_symbols.tex`：模型假设与符号说明；
- `sections/03_analysis.tex`：问题分析；
- `sections/04_framework.tex`：总体求解框架；
- `sections/04b_experiment_protocol.tex`：六组规模、正式指标、候选/评价/晋升协议；
- `sections/05_q1.tex`：问题一建模、四策略 portfolio、策略消融、复杂度、六组结果与验证；
- `sections/06_q2.tex`：连续地址/碎片、SPILL、footprint-aware 调度、三阶段消融、复杂度与六组结果；
- `sections/07_q3.tex`：双 evaluator、时序边分解、fixed-traffic 优化、局部终止性、阶段贡献、FA1 trade-off 与复杂度；
- `sections/08_validation.tex`：验证矩阵、典型失败模式、自动化复现与论文数字防漂移；
- `sections/09_evaluation.tex`：模型优点、局限与改进方向；
- `sections/10_conclusion.tex`：结论；
- `sections/11_appendix_results.tex`：详细结果与消融表；
- `sections/12_appendix_algorithms.tex`：关键算法补充说明与伪代码；
- `sections/13_appendix_repro.tex`：正式 run/artifact/SHA 与复现入口；
- `draft.tex`：摘要、关键词、正文、参考文献与附录的当前工作稿外壳。

写作与证据控制文件：

- `OUTLINE.md`：章节施工图；
- `CLAIM_LEDGER.md`：关键结论与证据边界；
- `STYLE_STUDY.md`：2025 A 题获奖论文结构学习记录。

## 最新验收

当前扩充稿 source head：`4e6f3fa928a51fdbee8f8595d69fec2cc7356ab0`。

- Paper Assets run：`35224816450`，success；
- Paper Draft run：`35224816467`，success；
- Draft artifact：`10498673465`；
- Artifact digest：`sha256:f9cc391ea6e51d29e13cc6122901ae8955f26a4bf0d38c38bb3d6b27e5f071da`；
- 当前 PDF：47 pages，777,408 bytes；
- 最终 XeLaTeX 日志无 `Overfull \\hbox`；仅有少量窄表格的 `Underfull`，视觉检查无裁切或越界。

## 版式策略

已选版式基线：

`resources/paper_templates/candidates/04_gmcm_2025_overleaf/`

该上游模板包含自带 TTF 字体。正式工程不复制这些字体文件；正文 section 与版式外壳解耦。当前 `draft.tex` 使用 TeX Live 自带 Fandol 中文字体进行持续集成编译，待 2026 第二十三届官方《竞赛论文标准文档》发布后，再把最终正文接入当届官方版式并逐项校准封面、页边距、字体字号、标题层级、页码、图表和参考文献。

## 数据与引用约束

- 正式数字只来自 `problems/CPMCM/2025/A/results/`；
- 图表在编译前由 `paper/Makefile` 重新生成；
- 正文引用使用 `../references/references.bib`；
- 所有“最优 / 提升 / 不变 / 饱和”等措辞必须符合 `CLAIM_LEDGER.md`；
- 不把 promoted / best-known / locally saturated 扩写成全局最优。

## 本地编译

从 `problems/CPMCM/2025/A/paper/` 执行：

```bash
python -m pip install matplotlib
make manuscript
```

需要本机安装 XeLaTeX、latexmk 和 BibTeX。GitHub Actions 另有独立 LaTeX workflow，在完整 TeX Live 环境中编译并上传 `draft.pdf`。
