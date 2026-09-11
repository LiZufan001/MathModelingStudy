# 2025 D 候选论文来源与身份边界

> 赛题：2025 中国研究生数学建模竞赛 D 题《低空湍流监测及最优航路规划》  
> 候选论文：**《低空湍流监测及最优航路规划研究》**  
> 候选证据 ID：`graduate:paper:2025-D:ac2d33da18fa`  
> 页数：60  
> SHA256：`ac2d33da18fa8fd500452655e0b6b92a82623fab99f303070157e812696b8217`  
> **状态：证据级深读；未看到候选 PDF 封面，不能把它标成 exact-match 全文。**

---

# 1. 目标团队

辽宁工程技术大学官方报道可核验：

- 石彤彤
- 赵其伟
- 安雪菱
- 指导教师：韩晓晨
- 获奖：2025 年中国研究生数学建模竞赛全国一等奖
- 官方作品题名：**《低空湍流监测与最优航路规划研究》**

本仓库一等奖白名单进一步给出该队参赛编号：

`D25101470116`

对应本仓库：

- `papers/CPMCM/_research/official_awards/FIRST_PRIZE_2024_2025.csv`
- `papers/CPMCM/2025/VERIFIED_FIRST_PRIZE.md`

# 2. 候选全文

公开的 2025 “优秀论文选”深读语料记录了一篇：

`D题-低空湍流监测及最优航路规划研究.pdf`

其元数据为：

- 60 页
- 8,658,181 B
- SHA256 `ac2d33da18fa8fd500452655e0b6b92a82623fab99f303070157e812696b8217`
- 证据 ID `graduate:paper:2025-D:ac2d33da18fa`

该题名与目标团队官方题名相比只有：

`及 ↔ 与`

一字差异，因此属于非常强的 `T+` 候选。

但是：

> **题名高度一致不能代替封面队号。**

只有真正看到候选 PDF 首页并确认：

`D25101470116`

才允许把它升级为 exact-match / `M`。

# 3. 当前能确认的全文审读证据

公开仓库 `yan315598-design/mathmodel-studio` 留下了该 PDF 的逐篇人工审读记录：

- `competitions/huaweibei/star_papers_deep.md`
- `competitions/huaweibei/papers/manual_paper_reviews.json`
- `competitions/huaweibei/papers/domain_index.md`

其中明确登记：

- `review_status = manually_reviewed`
- `evidence_scope = full_text_with_page_evidence`
- 页数 60
- Q1/Q2/Q3 的页码范围、模型链、中间输出、验证、图表角色、可复用点与反模式

因此本目录可以做**证据级深读**，但不能声称“本仓库本轮亲自逐页视觉扫描了该 PDF”。

# 4. PDF 恢复核查

2026-09-11 本轮额外做了公开 Git 历史核查：

1. 对 `yan315598-design/mathmodel-studio` 执行 mirror clone；
2. 搜索全部 refs；
3. 搜索全部 reachable Git objects；
4. 以候选文件名、D 题 PDF、低空湍流 PDF 为模式查找。

结果：

- 当前仓库无 PDF；
- 历史 reachable objects 中也无候选 PDF 路径；
- 只有 `main` 一个可达 ref；
- 不能从公开 Git 历史恢复原始 60 页 PDF。

临时 workflow 已在核查结束后删除。

# 5. 本目录的证据口径

本目录将结论分三类：

## A. 已核实事实

来自：

- 官方赛题；
- 官方一等奖名单；
- 辽宁工程技术大学官方报道；
- 带页码的全文人工审读记录。

可以写成确定事实。

## B. 候选身份推断

例如：

> 这 60 页候选与石彤彤团队论文高度疑似同篇。

只能写“高度疑似 / 强候选”，不能写“已确认”。

## C. 本轮新增数学审计

例如：

- `ε^(1/3)` 并不是无量纲 turbulence intensity；
- 随机时空点 70/30 切分可能造成自相关泄漏；
- 100 m 网格插值不等于 100 m 有效观测分辨率；
- `distance + α·TKE^β` 需要统一量纲或归一化；
- A* 的“全局最优”只对定义好的离散图、合法边集与启发函数成立。

这些属于我们基于已记录公式/流程做的二次推导，应明确和论文原文结论区分。

# 6. 升级条件

未来若获得原始候选 PDF：

1. 先算 SHA256；
2. 若 SHA 为 `ac2d33da18fa...`，视觉检查封面；
3. 若封面队号为 `D25101470116`，再升级为目标队 exact-match；
4. 渲染全部 60 页并逐页视觉扫描；
5. 对公式、表格、图、附录代码重新复核；
6. 修正本目录中所有依赖二手审读记录的字段。

在这之前，学习价值可以充分利用，但身份与“亲自逐页精读”状态必须保持黄色。