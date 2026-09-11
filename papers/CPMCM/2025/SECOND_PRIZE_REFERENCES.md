# CPMCM 2025 全国二等奖公开材料

> 本页收录可公开访问、具有明确“全国二等奖”来源声明的补充学习材料。它们与 `VERIFIED_FIRST_PRIZE.md` / `fulltext/` 分开管理，**不计入全国一等奖 `M` 统计，也不改变当前 209 篇国一全文总数**。

## 状态口径

- `N2-V`：已取得官方名单等身份材料，可精确核对参赛编号、队员/学校与全国二等奖；若尚未取得正式论文 PDF，会单独标明，不能把“身份已闭环”误写成“全文已验证”。
- `N2-S`：公开原作者/项目仓库明确自述为全国二等奖，但尚未完成参赛编号、队员/学校的独立身份闭环；可作为学习资料，不能当作已完成官方身份核验的国二项目。

## A 题

### Zhengzhou University A-codeRepository｜`N2-V`

- 题目：2025 A《通用神经网络处理器下的核内调度问题》
- 参赛编号：`A25104590087`
- 学校：郑州大学
- 队员：徐志鹏 / 宋旭辉 / 韩冰琪
- 奖项：全国二等奖
- 公开项目：[`song-xh/huaweibei-A-codeRepository`](https://github.com/song-xh/huaweibei-A-codeRepository)
- 已核验比赛期 commit：`2f2b70cf7974f568935fc8f8581125f7c3f3e639`、`342b1849585a999b6c2904dab78ead079088f21a`
- **全文状态：尚未取得正式参赛论文 PDF**。本条 `N2-V` 仅表示“官方获奖身份 + 公开赛中代码身份”已经完成交叉闭环。

#### 身份闭环证据

1. 官方 2025 最终获奖附件 `A.xlsx` 中，`A25104590087` 的奖项为“二等奖”，三名队员均为郑州大学：徐志鹏 / 宋旭辉 / 韩冰琪。仓库保留的官方解析基线见：
   - `papers/CPMCM/_research/official_awards/SECOND_PRIZE_2025.csv`
   - `papers/CPMCM/_research/official_awards/SECOND_PRIZE_2025_DIAGNOSTICS.json`
2. 郑州大学 2024 年硕士研究生复试结果综合排序公示中，计算机技术专业公开列有“宋旭辉”，能够独立确认同名研究生的学校与专业身份：
   - <https://www7.zzu.edu.cn/__local/8/49/46/AA0CAC008420860358C198FD12C_CBB36C49_5BB63.pdf>
3. `song-xh/huaweibei-A-codeRepository` 的 2025-09-26 比赛期提交，Git author / committer 均为 `sxh <1770986733@qq.com>`；GitHub 将提交关联到账号 `1125rx`。同一 `1125rx` 身份长期向 `song-xh` 名下多个仓库提交，并非比赛当天偶然出现的第三方账号。
4. `song-xh/auction_aware_task_assignment` 中公开保留的研究论文《Auction-Aware Crowdsourced Parcel Assignment for Cooperative Urban Logistics》作者列表明确包含 **Xuhui Song**，单位为 **School of Computer Science and Artificial Intelligence, Zhengzhou University**，并公开研究生邮箱 `xhsong@gs.zzu.edu.cn`。这与“宋旭辉 / 郑州大学”的姓名拼音、学校和研究生身份形成独立交叉证据。
5. A 题代码仓本身完整保留 Conv / Matmul / FlashAttention 六组赛题 JSON/CSV、Problem1/2/3 求解代码、schedule/spill 结果和可视化等比赛材料，且提交时间处于正式比赛窗口。结合上述身份链，可将其作为 `A25104590087` 的公开原队代码来源收录为 `N2-V`。

#### 可学习内容

该仓库更接近比赛现场工程快照，而不是赛后整理教程：

1. **Q1 调度**：按 Problem1 组织调度生成、内存轨迹和各 case 的 schedule 输出。
2. **Q2 缓存/搬运**：保留 Problem2 的缓存分配、SPILL 相关实现及对应结果文件。
3. **Q3 联合优化**：Problem3 中继续围绕调度与缓存代价进行联合优化，并输出各计算图结果。
4. **原始数据完整**：同时保留官方 JSON 与转换后的 CSV 版本，便于与其他国一/国二方案做同输入对比。

#### 当前缺口

- 尚未发现该队正式提交论文 PDF，因此目前不能进行 PDF SHA256、封面队号或论文方法与源码的逐段绑定。
- 后续优先反查队员姓名、学校公开材料、赛后分享、文档分享站、网盘镜像以及 GitHub 历史对象；找到 PDF 后应作为独立“全文已取得”证据补入本条。

### NPU Operator Scheduler｜`N2-V`

- 题目：2025 A《通用神经网络处理器下的核内调度问题》
- 参赛编号：`A25104650064`
- 学校：中原工学院
- 队员：张颢震 / 王宇豪 / 李子杭
- 奖项：全国二等奖
- 公开项目：[`1357570890/NPU-Operator-Scheduler`](https://github.com/1357570890/NPU-Operator-Scheduler)
- 当前公开 HEAD：`b3f47fb07ef247cf82f4cb5d2e876983a84d3ace`
- 项目 README 明确声明：该工程为“**第二十二届中国研究生数学建模竞赛全国二等奖**核心算法的实现源码”。
- **全文状态：尚未取得正式参赛论文 PDF**。本条 `N2-V` 只表示“项目作者身份 + 官方奖项身份”已经闭环，不表示论文全文已经取得或封面已经核验。

#### 身份闭环证据

1. 官方 2025 最终获奖附件 `A.xlsx` 中，`A25104650064` 的奖项为“二等奖”，三名队员均为中原工学院：张颢震 / 王宇豪 / 李子杭。仓库保留的官方解析基线见：
   - `papers/CPMCM/_research/official_awards/SECOND_PRIZE_2025.csv`
   - `papers/CPMCM/_research/official_awards/SECOND_PRIZE_2025_DIAGNOSTICS.json`
2. 中原工学院研究生处 2024 级录取通知名单公开列出“张颢震 / 控制理论与控制工程”；原电子信息学院 2024 年调剂四批复试名单也公开列出同名考生，能独立确认张颢震确为中原工学院该方向研究生：
   - <https://yjsc.zut.edu.cn/info/1128/4076.htm>
   - <https://xt.zut.edu.cn/info/1003/1021.htm>
3. `1357570890/NPU-Operator-Scheduler` 的初始 commit `3024595a4e6f373be82d43c9f02bc8493a141982`，Git author / committer 均为 `haozhen zhang <1357570890@qq.com>`；该 GitHub 账号正是仓库 owner：
   - <https://github.com/1357570890/NPU-Operator-Scheduler/commit/3024595a4e6f373be82d43c9f02bc8493a141982>
4. 同一 GitHub 账号的个人主页仓库 [`1357570890/1357570890.github.io`](https://github.com/1357570890/1357570890.github.io) 在 README 首部直接自述 **“Haozhen's Interactive Portfolio”** 和 **“张颢震的个人主页与算法控制系统仿真实验室”**。这给出了账号 owner 对英文名 `Haozhen` 与中文名“张颢震”的直接自我绑定，因此不再需要仅凭拼音对应推断身份。
5. 因此本条 `N2-V` 的身份链现为“官方最终获奖名单 + 学校官方在读/录取身份 + Git commit 作者身份 + 同账号中英文实名自述 + 原项目全国二等奖自述”的交叉闭环。

#### 可学习内容

该仓库不是单纯的赛题代码片段，而是按三问整理的完整算法工程：

1. **Q1 调度**：计算图解析、拓扑排序、多准则启发式优先级、关键路径/局部剪枝，以及调度合法性验证。
2. **Q2 缓存与 SPILL**：连续内存分配、动态 Spill victim 选择、额外搬运代价评估、碎片分析与验证器。
3. **Q3 性能优化**：多核/异构流水下的调度优化、搬运成本计算、性能对比与可视化。
4. **工程验证**：仓库含 Conv / Matmul / FlashAttention 六组赛题计算图、自动检查脚本、内存/调度图表以及结果对比。

项目 README 自述 Q3 相对 Q2 单核基准的执行时延降低约 **35.49%**；该数字目前只记录为原项目报告结果，尚未在本仓库独立复算。

#### 与本仓库国一路线的关系

- 这份资料适合用作**国二等奖例/工程实现基线**，尤其可以参考其“解析器 → 调度器 → 内存模拟器 → 验证器 → 可视化”的代码组织方式。
- 它不能替代正在追踪的 2025 A 题国一原始 PDF，也不能用于给匿名优秀论文候选绑定国一身份。
- 后续若找到该队正式论文 PDF，应继续保存 SHA256、读取封面队号，并把“全文已取得”作为独立状态补充；无需重新证明其全国二等奖身份。

## 后续收录规则

后续如果继续发现 2025 A 题全国二等奖材料：

- 有完整论文 PDF：保存 SHA256、读取封面队号，并与官方二等奖名单核对；
- 只有公开代码/项目：先记为 `N2-S`；只有在“官方名单 + 独立作者/学校身份”完成交叉核验后，才升级 `N2-V`；
- 赛中教程、售卖稿、“国奖水平”等没有明确奖项身份的材料，不进入本页。