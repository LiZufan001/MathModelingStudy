# CPMCM Competition Starter Kit

目标：把赛前手册里的“应该这样做”变成每次开题都自动执行的最低纪律。

## 10 分钟启动

1. 复制本目录到本次比赛项目根目录，例如 `contest/`。
2. 将 `config.example.json` 复制为 `config.json`，填写题号、队伍与关键路径。
3. 打开 `core/evaluator.py`，按题面实现四个接口：
   - `check_input`
   - `check_feasibility`
   - `official_score`
   - `sanity_report`
4. 先写 `templates/RESEARCH_CANVAS.md`，再讨论模型名。
5. 每次真正改变研究判断的实验都记录：
   ```bash
   python tools/log_experiment.py \
     --question Q1 \
     --observation "..." \
     --judgment "..." \
     --change "..." \
     --result "..." \
     --interpretation "..." \
     --next-decision "..."
   ```
6. 每个稳定实验把正式指标写入一个 JSON 结果文件；正文数字从该文件渲染，不手抄。
7. 冻结前运行：
   ```bash
   python tools/preflight.py
   python -m unittest discover -s tests
   ```

## 目录

```text
competition_starter_kit/
├─ README.md
├─ config.example.json
├─ core/
│  ├─ evaluator.py          # 题目口径与唯一 evaluator 接口
│  └─ result_store.py       # 原子写入结果 + 元数据
├─ tools/
│  ├─ log_experiment.py     # O/J/M/E/B 研究决策日志
│  ├─ render_paper.py       # results.json → 论文数字
│  └─ preflight.py          # 冻结前强制检查
├─ templates/
│  ├─ RESEARCH_CANVAS.md
│  └─ PAPER_NUMBERS.example.md
└─ tests/
   └─ test_starter.py
```

## 三条硬规则

### 1. 实验日志不是“跑过什么”，而是“为什么路线改变”

至少记录：

`observation → judgment → change → result → interpretation → next_decision`

没有改变判断的调参可以简写；真正改变模型路线的实验必须完整记录。

### 2. 论文数字只认一个结果源

稳定结果写到 JSON，例如：

```json
{
  "question": "Q1",
  "method": "baseline_rf",
  "metrics": {
    "rmse": 0.123456,
    "r2": 0.87654
  }
}
```

论文草稿写：

```text
RMSE={{metrics.rmse:.4f}}，R²={{metrics.r2:.3f}}
```

然后：

```bash
python tools/render_paper.py results/q1_final.json templates/PAPER_NUMBERS.example.md build/q1_numbers.md
```

若 key 不存在，脚本直接失败，不允许静默留错数字。

### 3. evaluator-first 是执行纪律，不是研究思想

研究判断仍从题意、数据、机理与实验事实产生。`evaluator.py` 只负责确保后面的所有比较都在**同一个正确口径**上进行。

## 推荐结果冻结流程

```text
候选模型
→ evaluator 验证
→ baseline / sensitivity / independent validation
→ 写 final results JSON
→ git commit/tag
→ render paper numbers
→ preflight
→ 冻结
```

不要冻结以后继续边跑实验边手改摘要数字。
