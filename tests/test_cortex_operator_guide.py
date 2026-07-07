"""Tests for the operator guide playbooks."""

from __future__ import annotations

import pytest

from hex_cortex.memory.cortex_operator_guide import (
    GUIDE_TOPICS,
    build_operator_guide,
    build_troubleshooting_guide,
    list_guide_topics,
)

EXPECTED_TOPICS = {
    "local_model_setup",
    "model_training",
    "mcp_connection",
    "server_setup",
    "voice_setup",
    "vision_setup",
    "video_training",
    "gpu_setup",
}


def test_catalog_covers_all_expected_topics() -> None:
    topics = list_guide_topics()

    assert {row["topic"] for row in topics} == EXPECTED_TOPICS
    for row in topics:
        assert row["step_count"] >= 4
        assert row["title"]
        assert row["summary"]


def test_every_step_is_complete_and_advisory() -> None:
    for topic in GUIDE_TOPICS:
        guide = build_operator_guide(topic=topic, experience_level="beginner")

        assert guide["advisory_only"] is True
        assert guide["commands_executed"] == 0
        assert guide["verify_each_step_before_next"] is True
        for step in guide["steps"]:
            assert step["step_id"]
            assert step["title"]
            assert step["why"]
            assert step["action"]
            assert step["verify"]


def test_experience_level_scales_detail_down() -> None:
    beginner = build_operator_guide(topic="local_model_setup", experience_level="beginner")
    expert = build_operator_guide(topic="local_model_setup", experience_level="expert")

    assert beginner["verify_each_step_before_next"] is True
    assert expert["verify_each_step_before_next"] is False
    assert any("why" in step for step in beginner["steps"])
    assert all("why" not in step for step in expert["steps"])
    assert all("pitfall" not in step for step in expert["steps"])
    # Same steps in the same order at every level.
    assert [step["step_id"] for step in expert["steps"]] == [
        step["step_id"] for step in beginner["steps"]
    ]


def test_troubleshooting_filters_by_symptom() -> None:
    all_rows = build_troubleshooting_guide(topic="local_model_setup")
    assert all_rows["symptom_matched"] is True
    assert len(all_rows["issues"]) == 3

    slow = build_troubleshooting_guide(topic="local_model_setup", symptom="slow")
    assert slow["symptom_matched"] is True
    assert len(slow["issues"]) == 1
    assert "slow" in slow["issues"][0]["symptom"].lower()

    unknown = build_troubleshooting_guide(topic="local_model_setup", symptom="zzz_no_match")
    assert unknown["symptom_matched"] is False
    assert len(unknown["issues"]) == 3


def test_invalid_inputs_are_rejected() -> None:
    with pytest.raises(ValueError):
        build_operator_guide(topic="does_not_exist")
    with pytest.raises(ValueError):
        build_operator_guide(topic="gpu_setup", experience_level="wizard")
    with pytest.raises(ValueError):
        build_troubleshooting_guide(topic="does_not_exist")


def test_guides_are_copies_not_shared_state() -> None:
    first = build_operator_guide(topic="gpu_setup")
    first["steps"][0]["title"] = "mutated"

    second = build_operator_guide(topic="gpu_setup")
    assert second["steps"][0]["title"] != "mutated"
