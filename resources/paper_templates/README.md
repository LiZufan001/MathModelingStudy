# GMCM / 华为杯研究生数学建模竞赛论文模板候选

更新时间：2026-09-16

这个目录**只用于中国研究生数学建模竞赛（华为杯 / GMCM）参赛论文**。不收普通学术论文模板，不收本科数模模板，也不把完整参赛论文混进“模板候选”。

## candidates：只放可直接拿来打华为杯的 LaTeX 模板

| 编号 | 目录 | 年份 | LaTeX 源码 | PDF 示例 | 备注 |
|---|---|---:|---|---|---|
| 01 | `candidates/01_latexstudio_gmcm_2024` | 2024 | `example.tex`, `example-color.tex`, `gmcmthesis.cls` | `example.pdf`, `example-color.pdf` | 长期维护、格式稳 |
| 02 | `candidates/02_gmcm_2022_bw_color` | 2022 | `example.tex`, `example-color.tex`, `gmcmthesis.cls` | `example.pdf`, `example-color.pdf` | 黑白/彩色两套成品 |
| 03 | `candidates/03_cpipc_2023_modular` | 2023 | `A23100010001.tex`, `CPIPC.cls`, `section/`, `table/` | `A23100010001.pdf` | 模块化，适合长论文/多人协作 |
| 04 | `candidates/04_gmcm_2025_overleaf` | 2025 | `MathModel.tex`, `gmcmthesis.cls` 等 | `MathModel.pdf` | 年份最新，优先看 |

以上四套都明确面向**中国研究生数学建模竞赛**，不是普通论文模板。

## references：只放比赛成品参考，不作为模板候选

- `references/01_cpgmcm_2023_full_paper`
  - 2023 E 题完整参赛论文工程，带 LaTeX 源码和最终 PDF；
  - 用来观察摘要长度、图表密度、章节组织和参考文献排版；
  - 奖级未核验，因此不称为国一论文。

- `references/02_national_first_2021_problem_e`
  - 上游明确标注为 **2021 华为杯 E 题全国一等奖**；
  - 有最终 `paper.pdf`、代码和数据，但没有 `.tex`；
  - 只作为真正国一成品风格标尺。

## 关于“国一 LaTeX 原稿”

我额外检索了公开 GitHub / 网页。目前能明确核验为“全国一等奖”的华为杯仓库，常见情况是只公开最终 PDF 和代码；公开完整 LaTeX 工程的仓库，又往往没有可核验的奖级说明。

因此目前**没有把任何无法同时核验“国一身份 + LaTeX 源码 + 对应最终 PDF”的资料冒充为国一模板**。如果后续找到三件套都能核验的国一仓库，再单独加入 `references/`。

## 建议你先看

1. `04_gmcm_2025_overleaf/MathModel.pdf`
2. `01_latexstudio_gmcm_2024/example.pdf`
3. `03_cpipc_2023_modular/A23100010001.pdf`
4. `references/02_national_first_2021_problem_e/paper.pdf`

你最终要选的是 **01 / 02 / 03 / 04** 其中一套比赛模板；国一 PDF 只用于判断成品风格。

## 拉取 submodule

已有本地仓库：

```bash
git pull
git submodule sync --recursive
git submodule update --init --recursive resources/paper_templates
```

只拉某一套，例如 2025 模板：

```bash
git submodule update --init resources/paper_templates/candidates/04_gmcm_2025_overleaf
```
