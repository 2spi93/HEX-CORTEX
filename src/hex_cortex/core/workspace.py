"""Global workspace helper for HEX-CORTEX."""

from __future__ import annotations

from statistics import fmean

from hex_cortex.core.schemas import CognitiveMode, Hypothesis, WorkspaceState


class GlobalWorkspace:
    """Small inspectable state shared by active cells."""

    def __init__(
        self,
        task_id: str,
        goal: str,
        mode: CognitiveMode,
        active_cells: list[str],
    ) -> None:
        self.state = WorkspaceState(
            task_id=task_id,
            goal=goal,
            mode=mode,
            active_cells=active_cells,
        )

    def add_hypothesis(self, hypothesis: Hypothesis) -> WorkspaceState:
        self.state.hypotheses.append(hypothesis)
        self._refresh_confidence()
        return self.state

    def add_issue(self, message: str) -> WorkspaceState:
        if message.strip():
            self.state.contradictions.append(message)
            self._refresh_confidence()
        return self.state

    def set_next_action(self, action: str) -> WorkspaceState:
        self.state.next_action = action
        return self.state

    def snapshot(self) -> WorkspaceState:
        return self.state.model_copy(deep=True)

    def _refresh_confidence(self) -> None:
        if not self.state.hypotheses:
            self.state.confidence = 0.0
            return

        base_confidence = fmean(h.confidence for h in self.state.hypotheses)
        issue_penalty = min(0.5, 0.1 * len(self.state.contradictions))
        confidence = max(0.0, min(1.0, base_confidence - issue_penalty))
        self.state.confidence = round(confidence, 10)
