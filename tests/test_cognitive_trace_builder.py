from hex_cortex.memory.cognitive_trace_builder import build_cognitive_trace_from_cycle


def test_cognitive_trace_builder_persists_multistep_trace(tmp_path) -> None:
    profile = tmp_path / "profile"
    payload = build_cognitive_trace_from_cycle(profile)
    trace = payload["trace_record"]

    assert payload["trace_type"] == "cognitive_trace_build"
    assert payload["trace_count"] == 1
    assert payload["final_action"] == "repair_profile_readiness"
    assert len(trace["steps"]) == 5
    assert trace["steps"][0]["label"] == "readiness"
    assert (profile / "cognitive-trace.jsonl").exists()
