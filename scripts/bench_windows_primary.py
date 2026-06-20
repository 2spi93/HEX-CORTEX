"""One-off live benchmark for the windows-primary cognitive brain.

Operator-approved live measurement (autonomy ladder step 4). Calls the local
Ollama HTTP API only; no mutation, no secrets, no network beyond localhost.

Methodology:
  - deterministic prompts (temperature 0, fixed seed) with a checkable answer
  - harder task set: algorithms, precise facts, classic reasoning traps
  - numeric answers graded by exact value (comma/symbol insensitive);
    text answers graded by normalized substring
  - one warmup call (model load) is excluded from latency
  - domain_scores[d]  = correct / total within domain d
  - reliability_score = correct / total across all tasks
  - latency_ms        = mean wall-clock latency per scored call
"""

from __future__ import annotations

import json
import re
import time
import urllib.request

MODEL = "qwen2.5-coder:7b"
ENDPOINT = "http://localhost:11434/api/generate"

# (domain, prompt, expected, is_numeric)
TASKS = [
    # --- coding / algorithms -------------------------------------------------
    ("coding", "F(1)=1, F(2)=1 Fibonacci. Reply with ONLY F(20).", "6765", True),
    ("coding", "Reply with ONLY the count of prime numbers below 100.", "25", True),
    ("coding", "Reply with ONLY the value of 12 factorial.", "479001600", True),
    ("coding", "Reply with ONLY the greatest common divisor of 1071 and 462.", "21", True),
    ("coding", "Reply with ONLY how many integers in 1..1000 are divisible by 3 or 5.", "467", True),
    ("coding", "Reply with ONLY the decimal value of binary 101101.", "45", True),
    # --- research / precise facts -------------------------------------------
    ("research", "Reply with ONLY the atomic number of uranium.", "92", True),
    ("research", "Reply with ONLY the speed of light in vacuum in m/s as an integer.", "299792458", True),
    ("research", "Reply with ONLY the year the Berlin Wall fell.", "1989", True),
    ("research", "Reply with ONLY the name of the largest moon of Saturn.", "titan", False),
    ("research", "Reply with ONLY the chemical formula of glucose.", "c6h12o6", False),
    ("research", "Reply with ONLY the SI base unit of electric current.", "ampere", False),
    # --- general reasoning / traps ------------------------------------------
    ("general", "Reply with ONLY the angle in degrees between clock hands at 3:15.", "7.5", True),
    ("general", "Reply with ONLY the next number: 1, 1, 2, 3, 5, 8, 13, ?", "21", True),
    ("general", "5 machines make 5 widgets in 5 minutes. Reply ONLY with minutes for 100 machines to make 100 widgets.", "5", True),
    ("general", "Reply with ONLY how many times the digit 7 appears writing 1 to 100.", "20", True),
    ("general", "Reply with ONLY x where 3x - 7 = 2x + 5.", "12", True),
    ("general", "A bat and ball cost $1.10; the bat costs $1.00 more than the ball. Reply ONLY with the ball price in dollars.", "0.05", True),
]

_NUM = re.compile(r"-?\d+(?:\.\d+)?")


def call(prompt: str) -> tuple[str, float]:
    body = json.dumps(
        {
            "model": MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0, "num_predict": 64, "seed": 7},
        }
    ).encode("utf-8")
    req = urllib.request.Request(ENDPOINT, data=body, headers={"Content-Type": "application/json"})
    start = time.perf_counter()
    with urllib.request.urlopen(req, timeout=180) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    return payload.get("response", ""), elapsed_ms


def grade(text: str, expected: str, is_numeric: bool) -> int:
    if is_numeric:
        target = float(expected)
        for token in _NUM.findall(text.replace(",", "")):
            if abs(float(token) - target) < 1e-9:
                return 1
        return 0
    return int(expected in text.strip().lower())


def main() -> None:
    # warmup: load the model so the first scored call is not skewed by load time
    call("Reply with ONLY: ok")

    per_domain: dict[str, list[int]] = {}
    correct = 0
    total = 0
    latencies: list[float] = []
    for domain, prompt, expected, is_numeric in TASKS:
        text, ms = call(prompt)
        latencies.append(ms)
        ok = grade(text, expected, is_numeric)
        per_domain.setdefault(domain, []).append(ok)
        correct += ok
        total += 1
        print(f"[{domain:8}] ok={ok} {ms:7.0f}ms  exp={expected:>10} :: {text.strip()[:48]!r}")

    domain_scores = {d: round(sum(v) / len(v), 3) for d, v in per_domain.items()}
    reliability = round(correct / total, 3)
    latency_ms = round(sum(latencies) / len(latencies), 1)

    print(f"\noverall: {correct}/{total}")
    print("=== RESULTS (paste into windows-primary.json) ===")
    print(json.dumps({
        "domain_scores": domain_scores,
        "reliability_score": reliability,
        "latency_ms": latency_ms,
    }, indent=2))


if __name__ == "__main__":
    main()
