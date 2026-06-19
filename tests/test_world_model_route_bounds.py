from hex_cortex.memory.cortex_world_model_route_guard import _unit_interval


def test_route_score_bounds() -> None:
    assert _unit_interval(1.0000006) == 1.0
    assert _unit_interval(-0.0000006) == 0.0
    assert _unit_interval(0.75) == 0.75


def test_negative_improvement_floor() -> None:
    assert _unit_interval(-0.25, floor_negative=True) == 0.0
    assert _unit_interval(0.25, floor_negative=True) == 0.25
