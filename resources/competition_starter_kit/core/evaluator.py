"""唯一 evaluator 接口。

比赛拿到题后，第一批代码就应该把题面口径翻译到这里。
不要在不同 notebook / script 中各写一份“差不多”的评分逻辑。
"""

from __future__ import annotations
from typing import Any


def check_input(data: Any) -> None:
    """检查输入字段、范围、单位和缺失值。

    不合法时应 raise ValueError / AssertionError，而不是静默修复。
    """
    raise NotImplementedError("TODO: implement check_input from the official problem statement")


def check_feasibility(solution: Any, data: Any) -> None:
    """检查所有 hard constraints。

    不可行解必须显式失败，不能只靠目标函数罚项掩盖。
    """
    raise NotImplementedError("TODO: implement hard-constraint checks")


def official_score(solution: Any, data: Any) -> float | dict[str, float]:
    """严格按题面/最新更正实现官方评价口径。"""
    raise NotImplementedError("TODO: implement the official evaluator")


def sanity_report(solution: Any, data: Any) -> dict[str, Any]:
    """返回范围、守恒、单位/数量级等 sanity checks。"""
    raise NotImplementedError("TODO: implement problem-specific sanity checks")
