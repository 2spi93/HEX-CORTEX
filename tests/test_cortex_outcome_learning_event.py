from hex_cortex.memory.cortex_outcome_learning_event import build_cortex_outcome_learning_event
from hex_cortex.memory.cortex_outcome_learning_event import summarize_cortex_outcome_learning_events


def test_outcome_learning_event_imports() -> None:
    assert callable(build_cortex_outcome_learning_event)
    assert callable(summarize_cortex_outcome_learning_events)
