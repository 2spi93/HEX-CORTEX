from __future__ import annotations

from hex_cortex.memory.cortex_bus import CortexUnit
from hex_cortex.memory.cortex_goal import build_cortex_goal
from hex_cortex.memory.cortex_goal import evaluate_cortex_cost


def build_cortex_goal_link() -> dict[str, CortexUnit]:
    return {
        "goal.build": CortexUnit(
            name="goal.build",
            unit=build_cortex_goal,
            description="Build an explicit bounded goal receipt.",
            mutates_receipt=True,
            requires_operator=False,
        ),
        "cost.evaluate": CortexUnit(
            name="cost.evaluate",
            unit=evaluate_cortex_cost,
            description="Evaluate a candidate state against a goal and cost budget.",
            mutates_receipt=True,
            requires_operator=False,
        ),
    }
