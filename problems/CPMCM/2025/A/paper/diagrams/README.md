# diagrams

论文方法框图、流程图与结构示意图工作区。

## 当前可复现方法图

源文件：

`diagrams/scripts/generate_diagrams.py`

当前生成：

- `generated/pipeline_overview.pdf` / `.png`
  - 三问统一 pipeline：输入图 → Q1 调度 → Q2 地址/SPILL → Q3 timing 优化 → 独立验收；
- `generated/q2_buffer_lifecycle.pdf` / `.png`
  - Q2 buffer 的 ALLOC / resident-use / optional SPILL / DDR / reload / FREE 生命周期。

两张图都由 Python + matplotlib 程序化生成，进入 `make assets` 和 GitHub Actions 验收链。

## 规则

- 正文引用优先使用矢量 PDF；
- 图中任何定量数字必须来自 `results/` 的正式结果，而不是手填实验草稿；
- 方法图必须与当前 `src/` 实现和 validator/evaluator 语义一致；
- 不把截图当作最终图源；
- 后续如果改用 draw.io/TikZ，应同时保留可编辑源文件和可复现导出步骤。
