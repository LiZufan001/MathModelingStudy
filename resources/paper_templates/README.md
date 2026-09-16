# GMCM / 华为杯研究生数学建模论文模板候选

更新时间：2026-09-16

这个目录用于在正式撰写 2025 A 题论文之前，先比较几套真实可用的 LaTeX 排版方案。所有外部候选都以 Git submodule 固定到具体 commit，避免上游后续修改导致模板悄悄变化，也避免把第三方字体/二进制文件直接复制进本仓库。

## 关于“国一模板”的核验结论

公开网络上能明确核验为“全国一等奖”的华为杯/研赛仓库，常见情况是只公开最终 PDF、代码或数据；公开且完整的 GMCM LaTeX 仓库，则通常是根据当年官方 Word 格式规范制作的通用模板，并不等于某篇国一论文的原始 LaTeX 工程。

截至本次检索，没有找到同时满足以下三点、且奖级可以公开核验的仓库：

1. 明确为全国一等奖论文；
2. 公开完整 LaTeX 源码；
3. 同时公开与源码对应的最终 PDF。

因此这里严格分成两类：

1. **5 套可选 LaTeX 模板 / 完整 LaTeX 实战论文**：全部有 `.tex` 源码和 PDF 示例，可直接比较版式；
2. **1 篇已核验全国一等奖论文**：只有最终 PDF，用来观察真实国一成品的摘要、章节密度、图表、公式和篇幅风格，不冒充 LaTeX 模板。

## 候选对比

| 编号 | 目录 | 年份/类型 | LaTeX 源码 | PDF 示例 | 适合看什么 | 建议 |
|---|---|---|---|---|---|---|
| 01 | `candidates/01_latexstudio_gmcm_2024` | 2024 华为杯/研赛通用模板 | `example.tex`, `example-color.tex`, `gmcmthesis.cls` | `example.pdf`, `example-color.pdf` | 长期维护、标准稳妥 | **优先候选** |
| 02 | `candidates/02_gmcm_2022_bw_color` | 2022 华为杯模板 | `example.tex`, `example-color.tex`, `gmcmthesis.cls` | `example.pdf`, `example-color.pdf` | 黑白/彩色两种传统版式 | 候选 |
| 03 | `candidates/03_cpipc_2023_modular` | 2023 华为杯模板 | `A23100010001.tex`, `CPIPC.cls`, `section/`, `table/` | `A23100010001.pdf` | 模块化拆章节，适合长论文/多人协作 | **优先候选** |
| 04 | `candidates/04_cpgmcm_2023_full_paper` | 2023 E 题完整实战论文 | `example.tex`, `example.bib`, `gmcmthesis.cls` | `出血性脑卒中预后预测_集成静态模型和时序模型.pdf` | 直接看完整论文落版，不是空模板 | **强烈建议看** |
| 05 | `candidates/05_gmcm_2025_overleaf` | 2025 华为杯 Overleaf 模板 | `MathModel.tex`, `gmcmthesis.cls` | `MathModel.pdf` | 年份最新、直接对应 2025 竞赛格式 | **优先看** |
| Ref | `references/05_national_first_2021_problem_e` | **2021 华为杯 E 题全国一等奖** | 无 | `paper.pdf` | 真正国一成品风格标尺 | **必看参考** |

### 01 — latexstudio/GMCMthesis（2024）

- 固定提交：`f49b88a2d95c8588ff22f80c35978ab51756ac12`
- 上游：<https://github.com/latexstudio/GMCMthesis>
- 长期维护的 GMCMthesis 路线，当前固定快照对应 2024 年第二十一届论文模板更新。
- 优点：成熟、简洁、与官方 Word 规范贴近；如果后续我们要自己维护模板，这一套改造成本最低。
- 建议先看：`example.pdf`、`example-color.pdf`。

### 02 — wsr1998 / 2022 GMCM template

- 固定提交：`9f2ba712311df12335cdbfc4dfa521bd2ce1c55d`
- 上游：<https://github.com/wsr1998/2022-China_post-graduate_mathematical_contest_in_modeling_thesis_template_Latex>
- 同时提供黑白和彩色版本，适合快速比较传统竞赛论文与适度彩色表格的视觉差异。
- 建议先看：`example.pdf`、`example-color.pdf`。

### 03 — mathliuyang/CPIPC（2023）

- 固定提交：`c07ca8f08155cf9b6ac4fd14bda29123ce0d4667`
- 上游：<https://github.com/mathliuyang/CPIPC>
- 2023 第二十届华为杯模板，正文按 `section/`、`table/` 等目录拆分，比单文件模板更适合后续多人/Agent 协作。
- 注意：上游仓库带 TTF 字体。这里仅以 submodule 引用，不把字体复制进本仓库；正式采用时优先改成系统/TeX Live 可用字体。
- 建议先看：`A23100010001.pdf`。

### 04 — spiritysdx/CPGMCM_2023（完整实战论文）

- 固定提交：`ed69e0673d04785c3d52f253d34cb94bccb4bac4`
- 上游：<https://github.com/spiritysdx/CPGMCM_2023>
- 不是 lorem ipsum 空壳，而是一篇完整的 2023 E 题 LaTeX 论文，含完整正文、参考文献和约 13 MB 的最终 PDF。
- 上游 README 没有声明奖级，因此**不要把它称为国一论文**；它最适合比较摘要长度、图表密度、章节组织、参考文献和正文实际落版。
- 建议先看：`出血性脑卒中预后预测_集成静态模型和时序模型.pdf`。

### 05 — springli07/GMCM_LaTeX_overleaf（2025）

- 固定提交：`a4df69ca77b58ed9eff353c3593305c01d6fc78a`
- 上游：<https://github.com/springli07/GMCM_LaTeX_overleaf>
- 直接面向 2025 年华为杯研究生数学建模竞赛，XeLaTeX/Overleaf 可用，包含 `MathModel.tex` 和对应 `MathModel.pdf`。
- 上游为了 Overleaf 兼容直接包含多种中文 TTF 字体；本仓库不复制这些字体，只保留 submodule 引用。后续若选中它，我们会重构字体依赖，避免把字体文件纳入自己的论文工程。
- 建议先看：`MathModel.pdf`。

### Ref — hiyouga/HuaweiCup2021-MCM-ProblemE（可核验国一）

- 固定提交：`f800024df78f5520ca73355430b37d91be5d23be`
- 上游：<https://github.com/hiyouga/HuaweiCup2021-MCM-ProblemE>
- 上游明确标注：**2021 年华为杯第十八届中国研究生数学建模竞赛 E 题全国一等奖**。
- 仓库包含 `paper.pdf`、代码和数据，但没有 `.tex`，因此只作为“国一成品参照”，不作为最终 LaTeX 基础模板。

## 额外检索到但未收入的源

- `chenkxin/2021-math-model`：公开了 2021 华为杯完整 `.tex` 工程，但仓库没有对应最终正文 PDF，也没有公开可核验奖级，因此不满足本目录的候选三件套标准。
- 网上存在以“2025 国一论文模板”为标题的视频/资料分享，但未找到同时具备公开可核验奖级、可访问 LaTeX 源码和对应 PDF 的版本，因此不按“国一源码”收录。

## 拉取候选

首次克隆仓库：

```bash
git clone --recurse-submodules https://github.com/LiZufan001/MathModelingStudy.git
```

已有本地仓库：

```bash
git pull
git submodule update --init --recursive resources/paper_templates
```

只拉某一个，例如 05：

```bash
git submodule update --init resources/paper_templates/candidates/05_gmcm_2025_overleaf
```

## 推荐浏览顺序

先比较“模板长相”，再看“国一成品长相”：

1. `05_gmcm_2025_overleaf/MathModel.pdf` —— 年份最新；
2. `01_latexstudio_gmcm_2024/example.pdf` —— 最稳妥基线；
3. `03_cpipc_2023_modular/A23100010001.pdf` —— 模块化方案；
4. `04_cpgmcm_2023_full_paper/出血性脑卒中预后预测_集成静态模型和时序模型.pdf` —— 完整实战落版；
5. `references/05_national_first_2021_problem_e/paper.pdf` —— 真正国一成品参照；
6. 若想比较颜色，再看 01/02 的 `example-color.pdf`。

你最终只需要告诉我喜欢 **01 / 02 / 03 / 04 / 05** 中哪一套的整体排版。选定后，我们再创建自己的论文目录并开始写，不直接在第三方 submodule 里改文件；同时按最终比赛规范校准封面、摘要、标题层级、公式、表格、参考文献和附录。
