# 2025 A题 · 附录 E 示例计算图数据

本目录补充 A 题《通用神经网络处理器下的核内调度问题》附录 E 所述的 6 个示例计算图。

## 目录

- `json/`：6 个 `<任务名>.json` 文件。
- `csv/`：12 个 CSV 文件，每个任务分别为 `<任务名>_Nodes.csv` 与 `<任务名>_Edges.csv`。

JSON 与 CSV 仅文件格式不同，导入时已逐项校验节点数、边数一致，并与附录 E 表 2 一致。

| 任务 | 节点数 | 依赖边数 |
| --- | ---: | ---: |
| Matmul_Case0 | 4160 | 7104 |
| Matmul_Case1 | 30976 | 55040 |
| FlashAttention_Case0 | 1716 | 2712 |
| FlashAttention_Case1 | 6952 | 11184 |
| Conv_Case0 | 2580 | 3869 |
| Conv_Case1 | 36086 | 85653 |

## 来源

- JSON 公共副本：`1357570890/NPU-Operator-Scheduler`，固定 commit `b3f47fb07ef247cf82f4cb5d2e876983a84d3ace`，路径 `data_generation/`。
- CSV 公共副本：`nsyw705/2025-MM`，固定 commit `da007ef7893caedefbeea47e4ef13fc41e837062`。
- 题面依据：2025 年第二十二届中国研究生数学建模竞赛 A 题附录 E《示例计算图数据格式及提交附件格式说明》。

> 说明：比赛平台原始下载入口已过赛期关闭，因此这里采用公开留存副本；通过文件名、数据结构以及附录 E 表 2 的六组节点/边数量进行交叉核验。
