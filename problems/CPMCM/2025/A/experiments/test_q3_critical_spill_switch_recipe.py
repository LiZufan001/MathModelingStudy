from __future__ import annotations

import sys
from pathlib import Path

EXP = Path(__file__).resolve().parent
SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(EXP))
sys.path.insert(0, str(SRC))

from q2_validator import validate_q2_solution
from q3_critical_spill_switch_recipe import replay_q3_critical_spill_switch_move
from test_q3_critical_spill_switch import _spill_switch_fixture


def test_replay_critical_spill_switch_move_matches_selected_operator_move() -> None:
    graph, solution = _spill_switch_fixture()
    replay = replay_q3_critical_spill_switch_move(
        graph,
        solution,
        spill_index=0,
        mode="out_earlier",
        expected_reversed_edges=((1, 4),),
    )
    assert replay.official.total_cycles == 404
    assert replay.safe.ok
    assert replay.reversed_edges == ((1, 4),)
    assert replay.changed_positions > 0
    assert replay.solution.spills == solution.spills

    q2 = validate_q2_solution(graph, replay.solution)
    q2.require_ok()
    assert q2.extra_traffic == validate_q2_solution(graph, solution).extra_traffic
    assert q2.spill_count == 1
