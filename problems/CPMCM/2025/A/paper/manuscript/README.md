# manuscript

2025 A 题第一版完整 LaTeX 工作稿已经形成，并纳入独立 XeLaTeX CI。

## 当前状态

正文已覆盖：

- `sections/01_problem.tex`：问题重述；
- `sections/02_assumptions_symbols.tex`：模型假设与符号说明；
- `sections/03_analysis.tex`：问题分析；
- `sections/04_framework.tex`：总体求解框架；
- `sections/05_q1.tex`：问题一建模、四策略 portfolio、六组结果与验证；
- `sections/06_q2.tex`：问题二连续地址/SPILL、footprint-aware 调度、polish、六组结果；
- `sections/07_q3.tex`：问题三双 evaluator、fixed-traffic 优化、六组结果与 FA1 trade-off；
- `sections/08_validation.tex`：统一验证与可复现性；
- `sections/09_evaluation.tex`：模型优点、局限与改进方向；
- `sections/10_conclusion.tex`：结论；
- `draft.tex`：包含正式第一版摘要、关键词与全部章节的当前工作稿外壳。

写作与证据控制文件：

- `OUTLINE.md`：章节施工图；
- `CLAIM_LEDGER.md`：关键结论与证据边界；
- `STYLE_STUDY.md`：2025 A 题获奖论文结构学习记录。

当前稿已经能够在 GitHub Actions 的完整 TeX Live 环境中自动生成 PDF。后续工作以内容润色、附录整理和 2026 官方格式迁移为主，而不是重新搭建正文结构。

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
