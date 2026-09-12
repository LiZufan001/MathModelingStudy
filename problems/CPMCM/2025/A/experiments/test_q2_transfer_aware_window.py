from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
EXP = Path(__file__).resolve().parent
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(EXP))

from q2_allocator import AddressPool, choose_min_cost_window
from q2_transfer_aware_window import choose_transfer_aware_window


def _two_equal_traffic_victims() -> AddressPool:
    pool = AddressPool(8)
    pool.reserve_at(1, 0, 4)
    pool.reserve_at(2, 4, 4)
    return pool


def test_transfer_cycles_break_only_equal_traffic_equal_count_tie() -> None:
    pool = _two_equal_traffic_victims()
    traffic = {1: 64, 2: 64}
    distances = {1: 100, 2: 1}

    production = choose_min_cost_window(pool, 4, traffic, distances)
    assert production is not None
    # Production prefers the farther-next-use victim: buffer 1 at offset 0.
    assert production.traffic_cost == 64
    assert production.victims == (1,)

    transfer_aware = choose_transfer_aware_window(
        pool,
        4,
        traffic,
        distances,
        frozenset(),
        transfer_cycle_costs={1: 428, 2: 278},
    )
    assert transfer_aware is not None
    # Same official traffic and same victim count; Q3 transfer work breaks the tie.
    assert transfer_aware.traffic_cost == production.traffic_cost == 64
    assert len(transfer_aware.victims) == len(production.victims) == 1
    assert transfer_aware.victims == (2,)
    assert transfer_aware.start == 4


def test_lower_official_traffic_still_dominates_transfer_cycles() -> None:
    pool = _two_equal_traffic_victims()
    traffic = {1: 32, 2: 64}
    distances = {1: 1, 2: 100}

    choice = choose_transfer_aware_window(
        pool,
        4,
        traffic,
        distances,
        frozenset(),
        transfer_cycle_costs={1: 10000, 2: 1},
    )
    assert choice is not None
    assert choice.traffic_cost == 32
    assert choice.victims == (1,)


def test_fewer_victims_still_dominates_transfer_cycles() -> None:
    pool = AddressPool(12)
    pool.reserve_at(1, 0, 2)
    pool.reserve_at(2, 2, 2)
    pool.reserve_at(3, 8, 4)
    traffic = {1: 32, 2: 32, 3: 64}
    distances = {1: 100, 2: 100, 3: 1}

    choice = choose_transfer_aware_window(
        pool,
        4,
        traffic,
        distances,
        frozenset(),
        transfer_cycle_costs={1: 1, 2: 1, 3: 10000},
    )
    assert choice is not None
    assert choice.traffic_cost == 64
    assert choice.victims == (3,)
