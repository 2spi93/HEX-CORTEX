from pathlib import Path

from hex_cortex.memory.cortex_repo_context import build_bounded_repo_context


def test_bounded_repo_context_returns_only_real_paths(tmp_path: Path) -> None:
    src = tmp_path / "src" / "pkg"
    tests = tmp_path / "tests"
    src.mkdir(parents=True)
    tests.mkdir()
    (src / "router.py").write_text(
        "def build_cognitive_loop_plan():\n    return 'ok'\n",
        encoding="utf-8",
    )
    (src / "consensus.py").write_text(
        "def aggregate_consensus():\n    return 'ok'\n",
        encoding="utf-8",
    )
    (tests / "test_router.py").write_text(
        "from pkg.router import build_cognitive_loop_plan\n\n"
        "def test_plan():\n    assert build_cognitive_loop_plan() == 'ok'\n",
        encoding="utf-8",
    )

    payload = build_bounded_repo_context(
        tmp_path,
        "Improve cognitive loop plan and consensus routing",
        max_modules=4,
        max_chars=4_000,
    )

    assert payload["context_type"] == "cortex_bounded_repo_context_v1"
    assert payload["raw_source_persisted"] is False
    assert payload["context_chars"] <= 4_000
    assert "src/pkg/router.py" in payload["allowed_paths"]
    assert all((tmp_path / path).is_file() for path in payload["allowed_paths"])
    assert "return 'ok'" not in payload["context_text"]


def test_bounded_repo_context_rejects_invalid_limits(tmp_path: Path) -> None:
    tmp_path.joinpath("mod.py").write_text("def f():\n    return 1\n", encoding="utf-8")

    try:
        build_bounded_repo_context(tmp_path, "task", max_chars=10)
    except ValueError as exc:
        assert "max_chars" in str(exc)
    else:
        raise AssertionError("too-small context budget should be rejected")
