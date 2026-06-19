from collections import Counter

import pytest

from hex_cortex.memory.cortex_screen_lab_policy_v2 import build_screen_lab_policy_v2_specs


def test_v2_specs_are_balanced_and_split_isolated() -> None:
    specs = build_screen_lab_policy_v2_specs()

    assert len(specs) == 40
    assert Counter(row["split"] for row in specs) == {
        "train": 24,
        "validation": 8,
        "test": 8,
    }
    action_counts = Counter(
        action_id
        for row in specs
        for action_id in row["actions"]
    )
    assert len(set(action_counts.values())) == 1
    assert action_counts == {
        "move_left": 80,
        "move_right": 80,
        "move_up": 80,
        "move_down": 80,
    }
    assert len({row["episode_id"] for row in specs}) == len(specs)


def test_v2_specs_reject_non_multiple_of_four_steps() -> None:
    with pytest.raises(ValueError):
        build_screen_lab_policy_v2_specs(steps_per_episode=6)


def test_v2_specs_are_deterministic() -> None:
    assert build_screen_lab_policy_v2_specs(seed=7) == build_screen_lab_policy_v2_specs(seed=7)
