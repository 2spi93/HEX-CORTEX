import json
from pathlib import Path

from hex_cortex.memory.cortex_self_consistency_cli import main


def _write(path: Path, payload: object) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_vote_command_returns_zero_on_consensus(tmp_path: Path, capsys) -> None:
    samples = _write(tmp_path / "s.json", ["42", "42", "42", "7"])
    receipt = tmp_path / "r.jsonl"
    code = main(["vote", "--samples", str(samples), "--receipt", str(receipt)])
    out = json.loads(capsys.readouterr().out)
    assert code == 0
    assert out["status"] == "verified"
    assert receipt.exists()


def test_vote_command_returns_nonzero_on_tie(tmp_path: Path, capsys) -> None:
    samples = _write(tmp_path / "s.json", ["a", "b"])
    code = main(["vote", "--samples", str(samples)])
    out = json.loads(capsys.readouterr().out)
    assert code == 1
    assert out["status"] == "no_consensus"


def test_vote_command_applies_weights(tmp_path: Path, capsys) -> None:
    samples = _write(tmp_path / "s.json", ["a", "a", "a", "b", "b"])
    weights = _write(tmp_path / "w.json", [0.2, 0.2, 0.2, 0.9, 0.9])
    code = main(["vote", "--samples", str(samples), "--weights", str(weights)])
    out = json.loads(capsys.readouterr().out)
    assert code == 0
    assert out["weighted"] is True
    assert out["consensus_answer"] == "b"


def test_verify_command_survives(tmp_path: Path, capsys) -> None:
    verdicts = _write(tmp_path / "v.json", [{"refuted": False}, {"refuted": False}, {"refuted": True}])
    code = main(["verify", "--verdicts", str(verdicts)])
    out = json.loads(capsys.readouterr().out)
    assert code == 0
    assert out["status"] == "survived"


def test_blocked_on_bad_input(tmp_path: Path, capsys) -> None:
    bad = _write(tmp_path / "bad.json", {"not": "an array"})
    code = main(["vote", "--samples", str(bad)])
    out = json.loads(capsys.readouterr().out)
    assert code == 2
    assert out["status"] == "blocked"
