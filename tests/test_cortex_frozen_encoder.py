from hex_cortex.memory.cortex_frozen_encoder import build_encoder_plan
from hex_cortex.memory.cortex_frozen_encoder import build_frozen_encoder_descriptor
from hex_cortex.memory.cortex_frozen_encoder import encode_image_to_latent
from hex_cortex.memory.cortex_frozen_encoder import probe_frozen_encoder_runtime


def test_descriptor_is_frozen_and_local_first() -> None:
    descriptor = build_frozen_encoder_descriptor()

    assert descriptor["descriptor_allowed"] is True
    assert descriptor["frozen"] is True
    assert descriptor["training_allowed"] is False
    assert descriptor["local_files_only_default"] is True


def test_plan_requires_approval_for_download(tmp_path) -> None:
    image = tmp_path / "image.bin"
    image.write_bytes(b"image")
    descriptor = build_frozen_encoder_descriptor()

    plan = build_encoder_plan(
        descriptor=descriptor,
        image_path=image,
        allow_model_download=True,
        operator_approved=False,
    )

    assert plan["plan_allowed"] is False
    assert "operator_approval_required_for_download" in plan["blockers"]


def test_fake_runner_emits_hash_only_receipt(tmp_path) -> None:
    image = tmp_path / "image.bin"
    image.write_bytes(b"image")
    descriptor = build_frozen_encoder_descriptor(pooling="mean_patch")

    def runner(image_path, model_ref, pooling, device, local_files_only):
        assert image_path == image.resolve()
        assert model_ref == "facebook/dinov2-base"
        assert pooling == "mean_patch"
        assert device == "auto"
        assert local_files_only is True
        return [3.0, 4.0], {
            "device": "cpu",
            "model_eval_mode": True,
            "requires_grad": False,
        }

    receipt = encode_image_to_latent(
        descriptor=descriptor,
        image_path=image,
        runner=runner,
    )

    assert receipt["encoded"] is True
    assert receipt["embedding_dim"] == 2
    assert receipt["embedding_l2_norm"] == 1.0
    assert receipt["frozen"] is True
    assert receipt["embedding_vector_persisted"] is False
    assert "volatile_embedding" not in receipt


def test_vector_can_be_returned_as_volatile_only(tmp_path) -> None:
    image = tmp_path / "image.bin"
    image.write_bytes(b"image")
    descriptor = build_frozen_encoder_descriptor()

    def runner(image_path, model_ref, pooling, device, local_files_only):
        return [3.0, 4.0], {"device": "cpu"}

    receipt = encode_image_to_latent(
        descriptor=descriptor,
        image_path=image,
        include_vector=True,
        runner=runner,
    )

    assert receipt["volatile_embedding"] == [0.6, 0.8]
    assert receipt["embedding_vector_persisted"] is False


def test_runtime_probe_remains_false_without_cache() -> None:
    descriptor = build_frozen_encoder_descriptor()
    receipt = probe_frozen_encoder_runtime(
        descriptor,
        model_cache_present=False,
    )

    assert receipt["runtime_ready"] is False
    assert "model_cache_missing" in receipt["blockers"]
    assert receipt["network_call_performed"] is False
