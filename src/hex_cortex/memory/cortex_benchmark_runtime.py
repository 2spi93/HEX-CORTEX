"""Benchmark runtime — run the measured-intelligence loop against local models.

This is the bridge between the cold benchmark kit and real local models: it
sends the deterministic suite to an Ollama model at temperature 0, scores the
responses locally, and appends the resulting fingerprint to a JSONL registry
that seeds the bandit router's priors.

Rails: localhost endpoints only, bounded timeouts, and no raw model response
persistence — only pass/fail per task and per-domain scores reach disk. The
transport is injectable so everything is testable without a live runtime.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

from hex_cortex.memory.cortex_bandit_router import empty_routing_stats, rank_models
from hex_cortex.memory.cortex_model_benchmark import (
    build_benchmark_suite,
    score_benchmark_responses,
)

_RUN_TYPE = "cortex_benchmark_run_v1"
_LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}

Transport = Callable[[str, bytes | None, float], str]


def _require_localhost(url: str) -> None:
    if urlparse(url).hostname not in _LOCAL_HOSTS:
        raise ValueError("benchmark runtime only calls localhost endpoints")


def default_local_transport(url: str, body: bytes | None, timeout_seconds: float) -> str:
    """Minimal localhost-only HTTP transport (GET when body is None)."""

    import urllib.request

    _require_localhost(url)
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"} if body is not None else {},
        method="POST" if body is not None else "GET",
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
        return response.read().decode("utf-8")


def list_local_models(
    *,
    endpoint: str = "http://127.0.0.1:11434",
    transport: Transport,
    timeout_seconds: float = 10.0,
) -> list[str]:
    """Return the model names known to the local runtime."""

    url = f"{endpoint.rstrip('/')}/api/tags"
    _require_localhost(url)
    payload = json.loads(transport(url, None, timeout_seconds))
    models = payload.get("models", [])
    return sorted(
        str(row["name"]) for row in models if isinstance(row, dict) and row.get("name")
    )


def collect_benchmark_responses(
    model: str,
    *,
    endpoint: str = "http://127.0.0.1:11434",
    transport: Transport,
    timeout_seconds: float = 60.0,
) -> dict[str, str]:
    """Send every suite prompt to the model at temperature 0.

    A task whose call fails is simply left unanswered — the scorer already
    counts missing answers as failures, which is the honest interpretation.
    """

    if not model.strip():
        raise ValueError("model must not be empty")
    url = f"{endpoint.rstrip('/')}/api/chat"
    _require_localhost(url)

    responses: dict[str, str] = {}
    for task in build_benchmark_suite()["tasks"]:
        body = json.dumps(
            {
                "model": model,
                "messages": [{"role": "user", "content": task["prompt"]}],
                "options": {"temperature": 0.0},
                "stream": False,
            }
        ).encode("utf-8")
        try:
            raw = transport(url, body, timeout_seconds)
            content = json.loads(raw)["message"]["content"]
        except Exception:  # noqa: BLE001 - one failed task must not sink the run
            continue
        if isinstance(content, str):
            responses[str(task["task_id"])] = content
    return responses


def run_model_benchmark(
    model: str,
    *,
    endpoint: str = "http://127.0.0.1:11434",
    transport: Transport,
    timeout_seconds: float = 60.0,
) -> dict[str, object]:
    """Run the full loop for one model and return its fingerprint record."""

    responses = collect_benchmark_responses(
        model,
        endpoint=endpoint,
        transport=transport,
        timeout_seconds=timeout_seconds,
    )
    report = score_benchmark_responses(model_id=model, responses=responses)
    report["run_type"] = _RUN_TYPE
    report["endpoint"] = endpoint
    report["measured_at"] = datetime.now(UTC).isoformat()
    report["model_call_performed"] = True
    return report


def append_fingerprint(report: dict[str, object], registry_path: Path) -> None:
    """Append one fingerprint record to the JSONL registry."""

    registry_path.parent.mkdir(parents=True, exist_ok=True)
    with registry_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(report, sort_keys=True) + "\n")


def load_routing_priors(registry_path: Path, *, domain: str) -> dict[str, float]:
    """Read the latest fingerprint per model into bandit priors for a domain."""

    priors: dict[str, float] = {}
    if not registry_path.exists():
        return priors
    for line in registry_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        score = record.get("domain_scores", {}).get(domain)
        if isinstance(score, (int, float)) and record.get("model_id"):
            priors[str(record["model_id"])] = float(score)  # latest record wins
    return priors


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hexcortex-benchmark",
        description="Benchmark local models into routing fingerprints.",
    )
    parser.add_argument("--model", action="append", default=None, help="repeatable; default: all local models")
    parser.add_argument("--endpoint", default="http://127.0.0.1:11434")
    parser.add_argument("--registry", type=Path, default=Path("receipts/model_fingerprints.jsonl"))
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--domain", default="coding", help="domain used for the routing demo ranking")
    parser.add_argument("--pretty", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    transport = default_local_transport

    models = args.model or list_local_models(
        endpoint=args.endpoint, transport=transport
    )
    reports = []
    for model in models:
        report = run_model_benchmark(
            model,
            endpoint=args.endpoint,
            transport=transport,
            timeout_seconds=args.timeout,
        )
        append_fingerprint(report, args.registry)
        reports.append(report)

    priors = load_routing_priors(args.registry, domain=args.domain)
    routing = rank_models(
        empty_routing_stats(),
        domain=args.domain,
        candidates=models,
        benchmark_priors=priors,
    )
    payload = {
        "run_type": _RUN_TYPE,
        "registry": str(args.registry),
        "fingerprints": [
            {
                "model_id": report["model_id"],
                "overall_score": report["overall_score"],
                "domain_scores": report["domain_scores"],
            }
            for report in reports
        ],
        "routing_demo": {
            "domain": args.domain,
            "selected_model": routing["selected_model"],
            "ranking": routing["ranking"],
        },
    }
    json.dump(payload, sys.stdout, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
