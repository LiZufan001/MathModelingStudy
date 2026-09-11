# 2025 A题公开代码仓身份追查矩阵

> 更新时间：2026-09-11  
> 目标：把公开 A题赛期 / 赛后整理仓通过 `代码内容 → commit 身份 → 学校/个人公开资料 → 官方获奖行` 反向绑定到真实参赛队，避免仅凭仓库名或算法相似度猜身份。  
> **本页不改变全国一等奖 `M` 统计。**

## 1. 已完成强闭环的公开代码源

### 1.1 全国一等奖 · `A25104250018` · 中国石油大学（华东）

- 队伍：赵浩羽 / 蒋铭皓 / 田欣媛
- 公开仓库：<https://github.com/HaoyuZhao31415/MathModel>
- 状态：一等奖身份、带队号全文、代码仓均已完成正式闭环。
- 详见：`VERIFIED_FIRST_PRIZE.md`

### 1.2 全国二等奖 · `A25104650064` · 中原工学院

- 队伍：张颢震 / 王宇豪 / 李子杭
- 公开仓库：<https://github.com/1357570890/NPU-Operator-Scheduler>
- README 明确自述全国二等奖核心算法；初始 commit 作者 `haozhen zhang` / `1357570890@qq.com`，与张颢震身份形成交叉证据。
- 状态：代码身份已按项目既有口径升级为 `N2-V`；尚无正式比赛 PDF。
- 详见：`SECOND_PRIZE_REFERENCES.md`

### 1.3 全国三等奖 · `A25100550012` · 南开大学

- 队伍：姜政旭 / 于雪婧 / 徐志骏
- 公开仓库：<https://github.com/Zysishuiyears/2025Huaweicup_Cachenpuscheduling>
- 官方获奖表 exact match：全国三等奖。
- 仓库保存：队号提交包、原提交代码、论文 PDF、历史输出、原题附件。
- 详见：`THIRD_PRIZE_REFERENCES.md`

## 2. 高置信身份候选：`zupengwang/math_modeling`

公开仓库：

- <https://github.com/zupengwang/math_modeling>

### 2.1 比赛期时间链

仓库 commit 历史从 2025-09-23 起持续到 2025-09-24，处于比赛期；提交作者长期为：

- `Wang Zupeng`
- `wangzupeng12061@gmail.com`

仓库内容直接使用 A题六个官方 case，并实现 SIMD/NPU DAG 调度、缓存与 SPILL 求解。

### 2.2 人员 / 学校交叉

公开 GitHub / 教育信息可将 owner 锚定为 `Zupeng Wang`，并出现 2021–2025 华中科技大学教育经历。

华中科技大学软件学院公开奖学金材料中存在 **王祖鹏**。

官方 2025 A题获奖表中存在：

- `A25104870289`
- 代武君 · 华中科技大学
- 王琢玉 · 华中科技大学
- **王祖鹏 · 华中科技大学**
- 奖项：成功参与奖

因此当前形成：

> 比赛期 A题代码仓 + commit `Wang Zupeng` + 华中科技大学背景 + 官方 A题唯一对应“王祖鹏 / 华中科技大学”获奖行

这已经是**高置信身份绑定候选**。

但与 `A25100550012` 不同：

- 该仓目前没有发现参赛队号；
- 没有原提交包或带队号 PDF；
- 尚未在仓内找到队友姓名。

所以本页暂不把它写成“文件级 exact identity closure”，而记录为：

> **高置信：`zupengwang/math_modeling` ↔ `A25104870289`，仍待队号/队友/提交包类直接证据补强。**

### 2.3 方法与 A1/A2 对照

实际代码为 memory-aware list scheduler：

- 固定多级缓存容量；
- 根据驻留峰值、release/alloc、bottom level、tile/workload 特征挑选 ready node；
- 针对 Conv / FlashAttention 使用 workload-specific tile heuristic。

当前没有找到：

- A1：Chaitin + 分层 ILP/Rounding + SPILL；
- A2：ABQPSO / `[seq|alloc|spill|offset]` / R1–R5 / DPEA / `domain_greedy_results.txt`。

因此这支仓基本可从 A1/A2 身份候选中降级，主要作为真实赛期参与方案对照。

## 3. 仍未完成 exact closure 的公开赛期仓

### 3.1 `song-xh/huaweibei-A-codeRepository`

- 仓库：<https://github.com/song-xh/huaweibei-A-codeRepository>
- 2025-09-26 比赛期 commit；
- commit 作者：`sxh`
- 邮箱：`1770986733@qq.com`
- GitHub commit 关联账号：`1125rx`

代码中 Q2 主要是 Best-Fit / greedy SPILL，Q3 存在 GA / 并行优化脚本；当前方法链与 A1/A2 均不吻合。

目前没有找到足够公开信息将 `sxh / 1125rx / 1770986733@qq.com` 安全绑定到官方参赛名单。

**禁止仅凭 `song-xh` / `sxh` 猜测中文姓名。**

### 3.2 `nsyw705/2025-MM` · 高优先级身份假设

- 仓库：<https://github.com/nsyw705/2025-MM>
- 2025-09-24 比赛期 commit；
- commit 作者：`LJH`
- 邮箱：`3393625446@qq.com`
- GitHub 用户：`nsyw705`
- 仓库包含六个官方 A题 case、`ProcessorScheduling.cpp`、可执行文件和原题文档。

#### 3.2.1 GitHub 账号可以独立落到北邮课程环境

GitHub 仓库检索发现：

- `bupt-zhangleihan/webappdev-assignment-1-nsyw705`

这是北京邮电大学课程组织下按 GitHub 用户名建立的作业仓。该仓 2023-10 / 2023-12 的提交作者仍是同一个 GitHub user id `112456012` / `nsyw705`，网页提交显示名为：

- `serely`

这说明 `nsyw705` 至少在 2023 年确实参与过 **北京邮电大学课程 GitHub Classroom / 课程组织环境**，而不是仅靠用户名猜学校。

#### 3.2.2 官方 2025 A题名单出现一个与 `LJH` 高度吻合的北邮队员

官方 2025 A题获奖表中存在：

- `A25100130018`
- 余嘉宁 · 北京邮电大学
- **李俊豪 · 北京邮电大学**
- 张铮宇 · 北京邮电大学
- 奖项：成功参与奖

同时，2025 MathorCup 华北赛区公开获奖表中又出现北京邮电大学队：

- 魏泽群 / **余嘉宁 / 李俊豪** / 吕昕

说明华为杯队员余嘉宁、李俊豪在 2025 年此前已有共同参加数学建模竞赛的公开组队记录。

由此当前形成一个具体而非泛化的研究假设：

> `nsyw705`（北邮课程环境） + 2025 A题仓 commit `LJH` + 官方北邮 A题队员“李俊豪” + 李俊豪/余嘉宁赛前共同数模组队  
> → **`nsyw705/2025-MM` 很可能对应 `A25100130018`，且 `LJH` 很可能是李俊豪。**

#### 3.2.3 为什么仍不能写成已验证身份

本轮已经继续检查：

- 北邮课程仓全文；
- `nsyw705/2025-MM` 文本文件；
- `nsyw705` / `serely` / `3393625446@qq.com` 的公开搜索；
- `李俊豪` 与账号、邮箱的组合搜索。

目前仍**没有**找到：

- `nsyw705 = 李俊豪` 的直接实名页面；
- `3393625446@qq.com = 李俊豪` 的公开绑定；
- `2025-MM` 仓中的 `A25100130018` 队号；
- 队友余嘉宁 / 张铮宇姓名；
- 带队号提交包或比赛论文。

因此严格状态只能是：

> **高优先级身份假设：`nsyw705/2025-MM` ↔ `A25100130018` / 李俊豪；尚未达到 exact identity closure。**

不能仅凭 `LJH` 首字母把仓库正式绑定为李俊豪。

#### 3.2.4 与 A1/A2 的关系

当前 `ProcessorScheduling.cpp` 主要表现为单体 C++ 调度/缓存/SPILL 求解框架；尚未检出：

- A1 的 Chaitin + 分层 ILP/Rounding 组合；
- A2 的 `ABQPSO`、四段编码 `[seq|alloc|spill|offset]`、Repair `R1–R5`、`DPEA`、`domain_greedy_results.txt`。

所以即使未来完成身份闭环，当前代码也没有把它提升为 A1/A2 匿名全文来源候选。

## 4. 当前公开 A题代码生态

通过 `FlashAttention_Case0`、`SPILL_OUT` 等官方附件/代码指纹做 GitHub 全局代码检索，当前高价值公开命中主要集中于：

1. `HaoyuZhao31415/MathModel` — 国一已验证；
2. `1357570890/NPU-Operator-Scheduler` — 国二代码身份已验证；
3. `Zysishuiyears/2025Huaweicup_Cachenpuscheduling` — 国三官方队号已验证；
4. `zupengwang/math_modeling` — 高置信对应成功参与奖 `A25104870289`；
5. `song-xh/huaweibei-A-codeRepository` — 身份未绑定，方法不似 A1/A2；
6. `nsyw705/2025-MM` — 高优先级疑似 `A25100130018` / 李俊豪，尚未 exact closure。

后续发现的新仓应优先执行同一套身份流程：

> 赛题附件指纹确认真 A题 → commit name/email → owner 其他仓/课程组织/个人主页/学校资料 → 官方奖项表 exact row → 检查是否有队号/PDF/提交包。

## 5. 对 A1/A2 追查的意义

本轮最大方法论收获是：

- 普通算法关键词搜索容易受到公开算法和同名噪声干扰；
- **赛期仓的 commit metadata / 邮箱 / 时间戳 / GitHub Classroom 痕迹通常比方法名更适合身份反查**；
- 一旦拿到真实团队代码，还可以立即与 A1/A2 特化结构做排除式比较。

当前新补齐/加强的真实赛期样本均未命中 A1/A2 独特指纹，因此没有改变 A1/A2 的 `C` 状态。

跨平台精确残留反搜也继续没有发现第二来源：

- A2 `domain_greedy_results.txt`：GitHub 公开命中仍只回到匿名论文深读记录 / 本仓整理；
- A1 `0922(2).pdf`：公开搜索中的其它同名结果均为无关文档；
- A1 六元结果向量的全局搜索以无关数字数据为主，没有比赛第二来源。

后续优先级：

1. 继续给 `nsyw705 ↔ 李俊豪 / A25100130018` 寻找第三条直接身份锚点；
2. 继续挖 `song-xh / 1125rx` 的课程组织、其他仓、commit 历史与公开平台身份；
3. 用官方附件文件名、输出格式、缓存容量与 SPILL 代码片段发现更多仓名不含“华为杯/NPU”的隐藏赛期仓；
4. 对新仓第一时间跑 A1/A2 独特指纹比对；
5. 持续查赛后专利、学校附件、原始 PDF/提交包与网盘目录残留。
