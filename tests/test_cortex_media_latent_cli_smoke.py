from hex_cortex.memory.cortex_media_to_latent_cli import _parse_action
from hex_cortex.memory.cortex_media_to_latent_cli import build_parser


def test_from_image_arguments_are_parsed() -> None:
    args = build_parser().parse_args(
        [
            "from-image",
            "image.png",
            "--comfy-root",
            "ComfyUI",
            "--device",
            "cpu",
        ]
    )

    assert args.command == "from-image"
    assert args.image_path == "image.png"
    assert args.device == "cpu"


def test_from_receipt_arguments_are_parsed() -> None:
    args = build_parser().parse_args(
        [
            "from-receipt",
            "source.json",
            "--comfy-root",
            "ComfyUI",
            "--output-index",
            "1",
        ]
    )

    assert args.command == "from-receipt"
    assert args.output_index == 1


def test_action_csv_is_parsed() -> None:
    assert _parse_action("0,-0.5,1") == [0.0, -0.5, 1.0]
