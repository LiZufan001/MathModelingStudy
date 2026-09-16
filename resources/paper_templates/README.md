# GMCM / 华为杯研究生数学建模论文模板候选

更新时间：2026-09-16

这个目录用于在正式写 2025 A 题论文之前，先比较几套真实可用的 LaTeX 排版方案。候选全部固定到具体 Git commit，避免上游后续修改导致模板悄悄变化。

## 先说明“国一模板”的筛选结论

公开网络上能核验为“全国一等奖”的研赛仓库，很多只公开最终 PDF/代码或 Word 版本，并没有同时公开 LaTeX 源码。相反，公开且完整的 GMCM LaTeX 模板通常是按官方 Word 规范制作，并不声称自己就是某篇国一论文的原始源码。

因此这里分成两类：

1. **4 套可选 LaTeX 基础模板/完整 LaTeX 实战论文**：每套都有 `.tex` 源码和 PDF 成品可直接比较；
2. **1 篇已核验全国一等奖论文**：用于观察真正国一成品的摘要、章节密度、图表、公式和篇幅风格，但它没有 LaTeX 源码，所以不作为基础模板候选。

这比把网上“国一模板”营销标题直接当作获奖论文原始源码更可靠。

## 候选对比

| 编号 | 目录 | 年份/类型 | LaTeX 源码 | PDF 示例 | 适合看什么 | 当前建议 |
|---|---|---|---|---|---|---|
| 01 | `candidates/01_latexstudio_gmcm_2024` | 2024 华为杯/研赛通用模板 | `example.tex`, `example-color.tex`, `gmcmthesis.cls` | `example.pdf`, `example-color.pdf` | 最接近长期维护的 GMCM 标准模板，格式稳 | **优先候选** |
| 02 | `candidates/02_gmcm_2022_bw_color` | 2022 华为杯模板 | `example.tex`, `example-color.tex`, `gmcmthesis.cls` | `example.pdf`, `example-color.pdf` | 黑白/彩色成品直接对比，比较传统 | 候选 |
| 03 | `candidates/03_cpipc_2023_modular` | 2023 华为杯模板 | `A23100010001.tex`, `CPIPC.cls`, `section/`, `table/` | `A23100010001.pdf` | 模块化拆章节，适合多人协作和长论文 | **优先候选** |
| 04 | `candidates/04_cpgmcm_2023_full_paper` | 2023 E 题完整实战论文 | `example.tex`, `example.bib`, `gmcmthesis.cls` | `出血性脑卒中预后预测_集成静态模型和时序模型.pdf` | 不是空壳模板，可直接看完整论文如何落版 | **强烈建议看** |
| 05 | `references/05_national_first_2021_problem_e` | **2021 华为杯 E 题全国一等奖** | 无 | `paper.pdf` | 真正国一成品风格参照 | 只作参考 |

### 01 — latexstudio/GMCMthesis

- 固定提交：`f49b88a2d95c8588ff22f80c35978ab51756ac12`
- 上游：<https://github.com/latexstudio/GMCMthesis>
- 该仓库长期维护 GMCMthesis，当前快照对应 2024 年第二十一届论文模板更新。
- 优点：成熟、简洁、接近官方 Word 规范；我们后续自己维护也最省事。
- 建议先看：`example.pdf` 和 `example-color.pdf`。

### 02 — wsr1998 / 2022 GMCM template

- 固定提交：`9f2ba712311df12335cdbfc4dfa521bd2ce1c55d`
- 上游：<https://github.com/wsr1998/2022-China_post-graduate_mathematical_contest_in_modeling_thesis_template_Latex>
- 同时提供黑白和彩色版本，适合快速比较“稳重竞赛论文”与“适度彩色表格”的观感。
- 建议先看：`example.pdf`、`example-color.pdf`。

### 03 — mathliuyang/CPIPC

- 固定提交：`c07ca8f08155cf9b6ac4fd14bda29123ce0d4667`
- 上游：<https://github.com/mathliuyang/CPIPC>
- 2023 第二十届华为杯模板，正文按 `section/`、`table/` 等目录拆分，比单文件模板更适合后续多人/Agent 协作。
- 注意：上游仓库带有 TTF 字体文件。我们这里只以 submodule 引用上游，不把这些字体复制进本仓库；正式采用时应优先改成系统/TeX Live 可用字体。
- 建议先看：`A23100010001.pdf`。

### 04 — spiritysdx/CPGMCM_2023

- 固定提交：`ed69e0673d04785c3d52f253d34cb94bccb4bac4`
- 上游：<https://github.com/spiritysdx/CPGMCM_2023>
- 这是一篇完整的 2023 E 题 LaTeX 论文，而不只是 lorem ipsum 模板；正文约 9 万字符，并配完整 PDF。
- 其 README 没有声明该论文的奖级，因此**不要把它称为国一论文**；这里主要拿它比较摘要长度、图表密度、章节组织、参考文献和正文排版。
- 建议先看：`出血性脑卒中预后预测_集成静态模型和时序模型.pdf`。

### 05 — hiyouga/HuaweiCup2021-MCM-ProblemE

- 固定提交：`f800024df78f5520ca73355430b37d91be5d23be`
- 上游：<https://github.com/hiyouga/HuaweiCup2021-MCM-ProblemE>
- 上游明确标注：**2021 年华为杯第十八届中国研究生数学建模竞赛 E 题全国一等奖**。
- 仓库包含 `paper.pdf`、代码和数据，但没有 `.tex`，所以它只作为“国一成品参照”，不作为我们最终的 LaTeX 基础模板。

## 为什么没有直接收入网上的“2025 国一论文模板”

搜索能找到以“2025 华为杯研赛国一论文模板”为标题的视频/资料分享，但没有找到同时满足“公开可核验 + 可直接访问的 LaTeX 源码 + PDF 成品”的版本。因此当前不把这类营销标题资料当作可信的 LaTeX 基线。

## 拉取候选

首次克隆仓库时：

```bash
git clone --recurse-submodules https://github.com/LiZufan001/MathModelingStudy.git
```

已有本地仓库时：

```bash
git pull
git submodule update --init --recursive resources/paper_templates
```

如果只想拉某一个，例如 01：

```bash
git submodule update --init resources/paper_templates/candidates/01_latexstudio_gmcm_2024
```

## 你怎么选

建议依次打开这五个 PDF：

1. `01/.../example.pdf`
2. `01/.../example-color.pdf`
3. `03/.../A23100010001.pdf`
4. `04/.../出血性脑卒中预后预测_集成静态模型和时序模型.pdf`
5. `05/.../paper.pdf`（国一风格参照）

然后告诉我你最喜欢 **01 / 02 / 03 / 04** 哪一套的整体排版。我们会以你选中的一套为基础，再按当年正式竞赛要求校准封面、摘要、标题层级、公式、表格、参考文献和附录，而不是原样照搬旧年份模板。
