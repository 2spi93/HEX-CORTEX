import pytest

from hex_cortex.core.cognitive_clock import (
    CognitiveClock,
    CognitiveTickContext,
    RegisteredTick,
    TickName,
    TickResult,
    TickStatus,
)
from hex_cortex.core.schemas import CognitiveMode, Task
from hex_cortex.spine.canonical_spine import CanonicalSpine


def test_cognitive_clock_runs_ticks_and_writes_spine_events() -> None:
    spine = CanonicalSpine()
    clock = CognitiveClock(spine=spine)
    task = Task(content="Run a basic cognitive loop")

    def intake(context: CognitiveTickContext) -> dict[str, str]:
        context.state["intake"] = "ok"
        return {"accepted": "true"}

    def action(context: CognitiveTickContext) -> TickResult:
        assert context.state["intake"] == "ok"
        return TickResult(
            tick_name=TickName.ACTION,
            status=TickStatus.SUCCESS,
            payload={"decision": "answer"},
            confidence=0.8,
        )

    report = clock.run(
        task=task,
        mode=CognitiveMode.WORKING,
        ticks=[
            RegisteredTick(TickName.INTAKE, intake),
            RegisteredTick(TickName.ACTION, action),
        ],
    )

    assert report.completed is True
    assert [result.tick_name for result in report.results] == [TickName.INTAKE, TickName.ACTION]
    assert spine.verify_integrity().ok is True
    assert spine.project().event_type_counts["tick.completed"] == 2
    assert spine.latest_by_type("clock.completed") is not None


def test_cognitive_clock_stops_on_required_tick_failure() -> None:
    clock = CognitiveClock()
    task = Task(content="Stop on required failure")

    def fail(_context: CognitiveTickContext) -> None:
        raise RuntimeError("boom")

    def should_not_run(_context: CognitiveTickContext) -> dict[str, str]:
        return {"ran": "false"}

    report = clock.run(
        task=task,
        mode=CognitiveMode.DEEP,
        ticks=[
            RegisteredTick(TickName.CRITIC, fail, required=True),
            RegisteredTick(TickName.ACTION, should_not_run, required=True),
        ],
    )

    assert report.completed is False
    assert report.stopped_reason == "required_tick_failed:critic"
    assert len(report.results) == 1
    assert report.results[0].status == TickStatus.FAILED


def test_cognitive_clock_continues_after_optional_tick_failure() -> None:
    clock = CognitiveClock()
    task = Task(content="Continue after optional failure")

    def optional_fail(_context: CognitiveTickContext) -> None:
        raise RuntimeError("optional boom")

    def action(_context: CognitiveTickContext) -> dict[str, str]:
        return {"decision": "continue"}

    report = clock.run(
        task=task,
        mode=CognitiveMode.WORKING,
        ticks=[
            RegisteredTick(TickName.PREDICTION, optional_fail, required=False),
            RegisteredTick(TickName.ACTION, action, required=True),
        ],
    )

    assert report.completed is True
    assert [result.status for result in report.results] == [TickStatus.FAILED, TickStatus.SUCCESS]


def test_cognitive_clock_rejects_too_many_ticks() -> None:
    clock = CognitiveClock(max_ticks=1)
    task = Task(content="Too many ticks")

    def noop(_context: CognitiveTickContext) -> None:
        return None

    with pytest.raises(ValueError, match="max_ticks"):
        clock.run(
            task=task,
            mode=CognitiveMode.REFLEX,
            ticks=[
                RegisteredTick(TickName.INTAKE, noop),
                RegisteredTick(TickName.ACTION, noop),
            ],
        )


def test_tick_handler_exception_never_leaks_tokens_to_spine() -> None:
    spine = CanonicalSpine()
    clock = CognitiveClock(spine=spine)
    secret = "api-key-do-not-persist"

    def broken(_context: CognitiveTickContext) -> None:
        raise RuntimeError("provider exploded: " + secret)

    report = clock.run(
        task=Task(task_id="redacted", content="Privately inspect a task"),
        mode=CognitiveMode.WORKING,
        ticks=[RegisteredTick(TickName.CRITIC, broken)],
    )
    assert report.completed is False
    assert report.results[0].error == "tick_handler_failed"
    assert secret not in str(spine.events)
    assert secret not in report.model_dump_json()
    assert spine.verify_integrity().ok


def test_overslow_tick_is_reported_as_budget_exceeded(monkeypatch) -> None:
    clock = CognitiveClock(max_latency_ms=20)
    ticks_called = []

    def slow(_context: CognitiveTickContext) -> dict[str, object]:
        from time import sleep

        ticks_called.append("slow")
        sleep(0.025)
        return {"ok": True}

    def should_not_run(_context: CognitiveTickContext) -> None:
        ticks_called.append("second")

    report = clock.run(
        task=Task(content="Latency-bound"),
        mode=CognitiveMode.REFLEX,
        ticks=[
            RegisteredTick(TickName.INTAKE, slow),
            RegisteredTick(TickName.ROUTING, should_not_run),
        ],
    )
    assert report.completed is False
    assert report.stopped_reason == "latency_budget_exceeded"
    assert ticks_called == ["slow"]

