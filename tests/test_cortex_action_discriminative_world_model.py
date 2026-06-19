from hex_cortex.memory.cortex_action_discriminative_world_model import build_action_discriminative_plan


def _manifest() -> dict[str, object]:
    return {
        "manifest_allowed": True,
        "training_ready": True,
        "promotion_ready": True,
        "manifest_hash": "a" * 64,
        "latent_dim": 768,
        "records": [
            {
                "action_values": [-1.0, 0.0],
            }
        ],
    }


def test_action_discriminative_plan_is_strict_by_default() -> None:
    payload = build_action_discriminative_plan(manifest=_manifest())

    assert payload["plan_allowed"] is True
    assert payload["config"]["architecture"] == "residual_mlp_action_discriminative_v2"
    assert payload["config"]["objective"] == "transition_mse_plus_counterfactual_margin_ranking"
    assert payload["config"]["minimum_top1_accuracy"] == 1.0
    assert len(payload["config"]["action_catalog"]) == 4


def test_action_discriminative_plan_rejects_catalog_dimension_mismatch() -> None:
    payload = build_action_discriminative_plan(
        manifest=_manifest(),
        action_catalog=((1.0,), (-1.0,)),
    )

    assert payload["plan_allowed"] is False
    assert "action_catalog_dimension_mismatch" in payload["blockers"]


def test_action_discriminative_plan_requires_ready_manifest() -> None:
    manifest = _manifest()
    manifest["training_ready"] = False

    payload = build_action_discriminative_plan(manifest=manifest)

    assert payload["plan_allowed"] is False
    assert "dataset_not_training_ready" in payload["blockers"]
