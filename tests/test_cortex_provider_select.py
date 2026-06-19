from hex_cortex.memory.cortex_provider_select import select_cortex_provider


def test_provider_selection_prefers_local_candidate() -> None:
    payload = select_cortex_provider(
        capability_id="screen_vision",
        prefer_local=True,
    )

    assert payload["selected"] is True
    assert payload["provider_id"] == "local_image_file"
    assert payload["raw_input_persistence_allowed"] is False
    assert payload["candidate_count"] == 2


def test_provider_selection_can_choose_browser_candidate() -> None:
    payload = select_cortex_provider(
        capability_id="screen_vision",
        prefer_local=False,
    )

    assert payload["selected"] is True
    assert payload["provider_id"] == "browser_display"
    assert payload["secure_context_required"] is True


def test_provider_selection_blocks_unknown_capability() -> None:
    payload = select_cortex_provider(capability_id="unknown")

    assert payload["selected"] is False
    assert "no_provider_for_capability" in payload["blockers"]
