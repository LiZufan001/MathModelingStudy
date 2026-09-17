# manuscript

正式 LaTeX 正文已经开始施工。

## 当前状态

已完成第一批可编译正文：

- `draft.tex`：当前工作稿外壳；
- `sections/04_framework.tex`：总体求解框架；
- `sections/05_q1.tex`：问题一建模、四策略 portfolio、六组结果与验证；
- `OUTLINE.md`：章节施工图；
- `CLAIM_LEDGER.md`：关键结论与证据边界；
- `STYLE_STUDY.md`：2025 A 题获奖论文结构学习记录。

下一批按 `Q2 -> Q3 -> trade-off -> 验证` 的顺序继续，摘要最后写。

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
