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

## 3. 尚未绑定身份的公开赛期仓

### 3.1 `song-xh/huaweibei-A-codeRepository`

- 仓库：<https://github.com/song-xh/huaweibei-A-codeRepository>
- 2025-09-26 比赛期 commit；
- commit 作者：`sxh`
- 邮箱：`1770986733@qq.com`
- GitHub commit 关联账号：`1125rx`

当前没有找到足够公开信息将 `sxh / 1125rx / 1770986733@qq.com` 安全绑定到官方参赛名单。

**禁止仅凭 `song-xh` / `sxh` 猜测中文姓名。**

### 3.2 `nsyw705/2025-MM`

- 仓库：<https://github.com/nsyw705/2025-MM>
- 2025-09-24 比赛期 commit；
- commit 作者：`LJH`
- 邮箱：`3393625446@qq.com`
- 仓库包含六个官方 case、`ProcessorScheduling.cpp` 和题目材料。

当前没有找到邮箱/用户名的独立身份锚点，因此保持未绑定。

## 4. 当前公开 A题代码生态

通过 `FlashAttention_Case0` 等官方附件指纹做 GitHub 全局代码检索，当前高价值公开命中主要集中于：

1. `HaoyuZhao31415/MathModel` — 国一已验证；
2. `1357570890/NPU-Operator-Scheduler` — 国二代码身份已验证；
3. `Zysishuiyears/2025Huaweicup_Cachenpuscheduling` — 国三官方队号已验证；
4. `zupengwang/math_modeling` — 高置信对应成功参与奖 `A25104870289`；
5. `song-xh/huaweibei-A-codeRepository` — 未绑定；
6. `nsyw705/2025-MM` — 未绑定。

后续发现的新仓应优先执行同一套身份流程：

> 赛题附件指纹确认真 A题 → commit name/email → owner 其他仓/个人主页/学校资料 → 官方奖项表 exact row → 检查是否有队号/PDF/提交包。

## 5. 对 A1/A2 追查的意义

本轮最大方法论收获是：

- 普通算法关键词搜索容易受到公开算法和同名噪声干扰；
- **赛期仓的 commit metadata / 邮箱 / 时间戳通常比方法名更适合身份反查**；
- 一旦拿到真实团队代码，还可以立即与 A1/A2 特化结构做排除式比较。

目前新发现的南开国三仓和 `zupengwang` 仓均未命中 A1/A2 独特指纹，因此没有改变 A1/A2 的 `C` 状态。

后续优先级：

1. 继续挖 `song-xh` / `nsyw705` 的 owner 其他公开活动和平台身份；
2. 用官方附件文件名、输出格式、缓存容量与 SPILL 代码片段发现更多仓名不含“华为杯/NPU”的隐藏赛期仓；
3. 对新仓第一时间跑 A1/A2 独特指纹比对；
4. 持续查赛后专利和原始 PDF/提交包。
