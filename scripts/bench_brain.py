"""Operator-approved live benchmark for a HEX-CORTEX cognitive brain.

One-off, operator-approved live measurement (autonomy ladder step 4). Calls a
local model HTTP endpoint only (no mutation, no secrets, no raw prompt/response
persistence). Generic over the runtime via --api (ollama | openai | llama)
and over the model, so the same protocol benchmarks a small and a large brain
across Ollama and llama-server (OpenAI-compatible) rails.

Statistical protocol:
  - ~40 checkable tasks per domain (coding / research / general)
  - coding & general task answers are computed in Python (ground truth),
    research facts are curated with unambiguous answers
  - the full suite is run R times at temperature > 0 with a different seed
    per run, so spread across runs estimates real sampling variance
  - per domain we report mean accuracy, standard deviation, and a 95%
    confidence interval across runs
  - numeric answers graded by exact value (comma/symbol insensitive);
    text answers graded by normalized substring
  - one warmup call (model load) is excluded from the latency mean
  - a failed/malformed call is scored wrong and counted, never aborts the run
  - latency is reported as mean, stdev, p50 and p95

Usage:
  python scripts/bench_brain.py [--model NAME] [--api ollama|openai|llama]
                                [--endpoint URL] [--runs 3] [--temperature 0.7]
                                [--num-predict 64]

  # Ollama (default):   --api ollama --model qwen2.5-coder:7b
  # llama-server:       --api llama  --endpoint http://127.0.0.1:8080
  # OpenAI-compatible:  --api openai --endpoint http://127.0.0.1:8080
"""

from __future__ import annotations

import argparse
import json
import math
import re
import statistics
import sys
import time
import urllib.error
import urllib.request

DEFAULT_ENDPOINTS = {
    "ollama": "http://localhost:11434",
    "openai": "http://127.0.0.1:8080",
    "llama": "http://127.0.0.1:8080",
}
_NUM = re.compile(r"-?\d+(?:\.\d+)?")


class CallError(Exception):
    """A single live call failed (transport, HTTP status, or malformed body)."""


def _num(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else str(value)


def build_coding_tasks() -> list[tuple[str, str, bool]]:
    tasks: list[tuple[str, str, bool]] = []
    for n in (10, 12, 15, 18, 20, 25):
        ans = sum(i * i for i in range(1, n + 1))
        tasks.append((f"Reply with ONLY the integer: the sum 1^2+2^2+...+{n}^2.", str(ans), True))

    def fib(k: int) -> int:
        a, b = 1, 1
        for _ in range(k - 1):
            a, b = b, a + b
        return a

    for n in (10, 13, 16, 19, 22):
        tasks.append((f"F(1)=1, F(2)=1 Fibonacci. Reply with ONLY F({n}).", str(fib(n)), True))
    for n in (6, 7, 8, 9, 10):
        tasks.append((f"Reply with ONLY the value of {n} factorial.", str(math.factorial(n)), True))
    for a, b in ((1071, 462), (252, 105), (1260, 476), (403, 93)):
        tasks.append((f"Reply with ONLY the greatest common divisor of {a} and {b}.", str(math.gcd(a, b)), True))
    for a, b in ((4, 6), (12, 18), (21, 14)):
        tasks.append((f"Reply with ONLY the least common multiple of {a} and {b}.", str(math.lcm(a, b)), True))
    for upper in (100, 500, 1000):
        count = sum(1 for x in range(1, upper) if x % 3 == 0 or x % 5 == 0)
        tasks.append((f"Reply with ONLY how many integers in 1..{upper - 1} are divisible by 3 or 5.", str(count), True))
    for bits in ("101101", "11111111", "100000", "1010101"):
        tasks.append((f"Reply with ONLY the decimal value of binary {bits}.", str(int(bits, 2)), True))
    for hexs in ("ff", "1a", "100", "de"):
        tasks.append((f"Reply with ONLY the decimal value of hexadecimal {hexs}.", str(int(hexs, 16)), True))
    for base, exp, mod in ((2, 10, 1000), (3, 7, 100), (7, 5, 13)):
        tasks.append((f"Reply with ONLY ({base}^{exp}) mod {mod}.", str(pow(base, exp, mod)), True))

    def count_primes(limit: int) -> int:
        sieve = [True] * limit
        sieve[0] = sieve[1] = False
        for i in range(2, int(limit**0.5) + 1):
            if sieve[i]:
                for j in range(i * i, limit, i):
                    sieve[j] = False
        return sum(sieve)

    for limit in (50, 100, 200):
        tasks.append((f"Reply with ONLY the count of prime numbers below {limit}.", str(count_primes(limit)), True))
    for number in (123456, 999999, 271828):
        digit_sum = sum(int(d) for d in str(number))
        tasks.append((f"Reply with ONLY the sum of the digits of {number}.", str(digit_sum), True))
    for n in (45, 170, 255):
        tasks.append((f"Reply with ONLY the number of 1 bits in the binary form of {n}.", str(bin(n).count("1")), True))
    return tasks


def build_general_tasks() -> list[tuple[str, str, bool]]:
    tasks: list[tuple[str, str, bool]] = []
    for a, d in ((2, 3), (5, 5), (1, 4), (10, -2)):
        terms = [a + i * d for i in range(5)]
        seq = ", ".join(map(str, terms))
        tasks.append((f"Reply with ONLY the next number: {seq}, ?", str(a + 5 * d), True))
    for a, r in ((2, 2), (1, 3), (3, 2)):
        terms = [a * r**i for i in range(5)]
        seq = ", ".join(map(str, terms))
        tasks.append((f"Reply with ONLY the next number: {seq}, ?", str(a * r**5), True))
    for p, y in ((15, 200), (8, 250), (35, 80), (12, 150)):
        tasks.append((f"Reply with ONLY the number: {p}% of {y}.", _num(p * y / 100), True))
    for a, b, x in ((3, 7, 5), (5, -2, 4), (4, 10, -3), (7, 1, 6)):
        c = a * x + b
        sign = "+" if b >= 0 else "-"
        tasks.append((f"Reply with ONLY x where {a}x {sign} {abs(b)} = {c}.", str(x), True))
    for nums in ([10, 20, 30], [4, 8, 15, 16, 23, 42], [100, 200, 300, 400]):
        tasks.append((f"Reply with ONLY the average of {', '.join(map(str, nums))}.", _num(sum(nums) / len(nums)), True))
    for n in (5, 6, 8):
        tasks.append((f"Reply with ONLY how many distinct pairs can be formed from {n} items.", str(n * (n - 1) // 2), True))
    for principal, rate, years in ((1000, 5, 2), (2000, 10, 3)):
        simple = principal * rate * years / 100
        tasks.append((f"Reply with ONLY the simple interest on {principal} at {rate}% per year for {years} years.", _num(simple), True))
    tasks.append(("Reply with ONLY the number of minutes in 3.5 hours.", "210", True))
    tasks.append(("Reply with ONLY the number of meters in 4.2 kilometers.", "4200", True))
    tasks.append(("Reply with ONLY the number of seconds in 2 hours.", "7200", True))
    tasks.append(("A car travels 240 km in 3 hours. Reply with ONLY its speed in km/h.", "80", True))
    tasks.append(("Reply with ONLY km traveled going 90 km/h for 2.5 hours.", "225", True))
    tasks.append(("A bat and ball cost $1.10; the bat costs $1.00 more than the ball. Reply ONLY with the ball price in dollars.", "0.05", True))
    tasks.append(("5 machines make 5 widgets in 5 minutes. Reply ONLY with minutes for 100 machines to make 100 widgets.", "5", True))
    tasks.append(("Reply with ONLY the angle in degrees between clock hands at 3:15.", "7.5", True))
    tasks.append(("Reply with ONLY how many times digit 7 appears writing 1 to 100.", "20", True))
    tasks.append(("A shirt costs $40 then drops 25%. Reply ONLY with the new price in dollars.", "30", True))
    tasks.append(("Reply with ONLY the number of diagonals in a regular hexagon.", "9", True))
    tasks.append(("If 3 painters paint a wall in 6 hours, reply ONLY with hours for 6 painters (same wall).", "3", True))
    return tasks


RESEARCH_TASKS: list[tuple[str, str, bool]] = [
    ("Reply with ONLY the atomic number of hydrogen.", "1", True),
    ("Reply with ONLY the atomic number of carbon.", "6", True),
    ("Reply with ONLY the atomic number of oxygen.", "8", True),
    ("Reply with ONLY the atomic number of iron.", "26", True),
    ("Reply with ONLY the atomic number of gold.", "79", True),
    ("Reply with ONLY the atomic number of uranium.", "92", True),
    ("Reply with ONLY the atomic number of helium.", "2", True),
    ("Reply with ONLY the atomic number of sodium.", "11", True),
    ("Reply with ONLY the capital city of Japan.", "tokyo", False),
    ("Reply with ONLY the capital city of France.", "paris", False),
    ("Reply with ONLY the capital city of Australia.", "canberra", False),
    ("Reply with ONLY the capital city of Canada.", "ottawa", False),
    ("Reply with ONLY the capital city of Brazil.", "bras", False),
    ("Reply with ONLY the capital city of Egypt.", "cairo", False),
    ("Reply with ONLY the capital city of Turkey.", "ankara", False),
    ("Reply with ONLY the chemical formula of water.", "h2o", False),
    ("Reply with ONLY the chemical formula of glucose.", "c6h12o6", False),
    ("Reply with ONLY the chemical formula of table salt.", "nacl", False),
    ("Reply with ONLY the chemical formula of ammonia.", "nh3", False),
    ("Reply with ONLY the chemical formula of methane.", "ch4", False),
    ("Reply with ONLY the chemical formula of carbon dioxide.", "co2", False),
    ("Reply with ONLY the speed of light in vacuum in m/s as an integer.", "299792458", True),
    ("Reply with ONLY the largest planet in the Solar System.", "jupiter", False),
    ("Reply with ONLY the largest moon of Saturn.", "titan", False),
    ("Reply with ONLY the closest planet to the Sun.", "mercury", False),
    ("Reply with ONLY the number of planets in the Solar System.", "8", True),
    ("Reply with ONLY the year the Berlin Wall fell.", "1989", True),
    ("Reply with ONLY the year World War II ended.", "1945", True),
    ("Reply with ONLY the year of the first crewed Moon landing.", "1969", True),
    ("Reply with ONLY the year the French Revolution began.", "1789", True),
    ("Reply with ONLY the SI base unit of electric current.", "ampere", False),
    ("Reply with ONLY the SI base unit of temperature.", "kelvin", False),
    ("Reply with ONLY the SI base unit of mass.", "kilogram", False),
    ("Reply with ONLY the SI base unit of luminous intensity.", "candela", False),
    ("Reply with ONLY the number of bones in the adult human body.", "206", True),
    ("Reply with ONLY the number of chromosomes in a human body cell.", "46", True),
    ("Reply with ONLY the powerhouse organelle of the cell.", "mitochond", False),
    ("Reply with ONLY the hardest naturally occurring mineral.", "diamond", False),
    ("Reply with ONLY the boiling point of water in Celsius at sea level.", "100", True),
    ("Reply with ONLY the freezing point of water in Celsius.", "0", True),
]


def _request(url: str, body: dict) -> dict:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise CallError(f"{url}: {exc}") from exc


def _request_get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def call(api: str, endpoint: str, model: str, prompt: str, temperature: float, seed: int, num_predict: int) -> tuple[str, float]:
    start = time.perf_counter()
    if api == "ollama":
        payload = _request(
            f"{endpoint}/api/generate",
            {
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": temperature, "num_predict": num_predict, "seed": seed},
            },
        )
        text = payload.get("response", "")
    elif api == "openai":
        payload = _request(
            f"{endpoint}/v1/chat/completions",
            {
                "model": model or "local",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
                "seed": seed,
                "max_tokens": num_predict,
                "stream": False,
            },
        )
        try:
            text = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise CallError(f"malformed openai response: {payload!r:.200}") from exc
    else:  # llama-server native /completion (single loaded model; model arg ignored)
        payload = _request(
            f"{endpoint}/completion",
            {"prompt": prompt, "n_predict": num_predict, "temperature": temperature, "seed": seed, "stream": False},
        )
        text = payload.get("content", "")
    return text, (time.perf_counter() - start) * 1000.0


def preflight(api: str, endpoint: str, fallback: str) -> str:
    """Confirm the endpoint is reachable and return the model label to report.

    Exits with an actionable message if the runtime is not up, so the operator
    knows to start it rather than reading an opaque urllib traceback.
    """
    try:
        if api == "ollama":
            payload = _request_get(f"{endpoint}/api/tags")
            names = [m.get("name") for m in payload.get("models", []) if m.get("name")]
            if fallback not in names:
                print(f"warning: model '{fallback}' not in installed {names}", flush=True)
            return fallback
        payload = _request_get(f"{endpoint}/v1/models")
        ids = [m.get("id") for m in payload.get("data", []) if m.get("id")]
        return ids[0] if ids else fallback
    except (urllib.error.URLError, OSError, ValueError) as exc:
        hint = "ollama serve" if api == "ollama" else "llama-server / your OpenAI-compatible runtime"
        sys.stderr.write(
            f"endpoint {endpoint} unreachable ({exc}).\n"
            f"Start the model runtime first (e.g. `{hint}`) and retry.\n"
        )
        raise SystemExit(2) from exc


def grade(text: str, expected: str, is_numeric: bool) -> int:
    if is_numeric:
        target = float(expected)
        return int(any(abs(float(t) - target) < 1e-9 for t in _NUM.findall(text.replace(",", ""))))
    return int(expected in text.strip().lower())


def _summary(values: list[float]) -> tuple[float, float, float]:
    """Return (mean, stdev, 95% CI half-width) for a list of run-level scores."""
    mean = statistics.mean(values)
    sd = statistics.stdev(values) if len(values) > 1 else 0.0
    ci = 1.96 * sd / math.sqrt(len(values)) if len(values) > 1 else 0.0
    return round(mean, 3), round(sd, 3), round(ci, 3)


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, int(math.ceil(pct / 100.0 * len(ordered))) - 1)
    return round(ordered[max(0, idx)], 1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="qwen2.5-coder:7b")
    parser.add_argument("--api", choices=("ollama", "openai", "llama"), default="ollama")
    parser.add_argument("--endpoint", default=None, help="base URL; defaults per --api")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--num-predict", type=int, default=64, help="max tokens generated per task")
    args = parser.parse_args()

    endpoint = (args.endpoint or DEFAULT_ENDPOINTS[args.api]).rstrip("/")
    model_label = preflight(args.api, endpoint, args.model)

    domains = {
        "coding": build_coding_tasks(),
        "research": RESEARCH_TASKS,
        "general": build_general_tasks(),
    }
    counts = {d: len(t) for d, t in domains.items()}
    print(f"api={args.api} endpoint={endpoint} model={model_label} runs={args.runs} "
          f"temp={args.temperature} num_predict={args.num_predict} tasks/domain={counts}", flush=True)

    try:
        call(args.api, endpoint, args.model, "Reply with ONLY: ok", 0.0, 1, args.num_predict)  # warmup, excluded
    except CallError as exc:
        sys.stderr.write(f"warmup call failed: {exc}\n")
        raise SystemExit(2) from exc

    per_domain_runs: dict[str, list[float]] = {d: [] for d in domains}
    overall_runs: list[float] = []
    latencies: list[float] = []
    errors = 0
    for run in range(1, args.runs + 1):
        run_correct = run_total = 0
        for domain, tasks in domains.items():
            correct = 0
            for prompt, expected, is_numeric in tasks:
                try:
                    text, ms = call(args.api, endpoint, args.model, prompt, args.temperature, run, args.num_predict)
                    latencies.append(ms)
                    correct += grade(text, expected, is_numeric)
                except CallError as exc:
                    errors += 1
                    sys.stderr.write(f"call failed (scored 0): {exc}\n")
            acc = correct / len(tasks)
            per_domain_runs[domain].append(acc)
            run_correct += correct
            run_total += len(tasks)
        overall_runs.append(run_correct / run_total)
        print(f"run {run}/{args.runs}: overall={run_correct}/{run_total}={run_correct / run_total:.3f}", flush=True)

    print("\n=== STATISTICS (mean +/- stdev, 95% CI across runs) ===")
    domain_scores = {}
    for domain in domains:
        mean, sd, ci = _summary(per_domain_runs[domain])
        domain_scores[domain] = mean
        print(f"{domain:8}: {mean:.3f} +/- {sd:.3f}  (95% CI +/-{ci:.3f}, n={counts[domain]} x {args.runs} runs)")
    overall_mean, overall_sd, overall_ci = _summary(overall_runs)
    lat_mean = round(statistics.mean(latencies), 1) if latencies else 0.0
    lat_sd = round(statistics.stdev(latencies), 1) if len(latencies) > 1 else 0.0
    total_calls = sum(counts.values()) * args.runs
    print(f"reliability: {overall_mean:.3f} +/- {overall_sd:.3f}  (95% CI +/-{overall_ci:.3f})")
    print(f"latency_ms : mean={lat_mean} +/- {lat_sd}  p50={_percentile(latencies, 50)}  p95={_percentile(latencies, 95)}")
    print(f"errors     : {errors}/{total_calls} failed calls")

    print("\n=== RESULTS (paste into the brain registration config) ===")
    print(json.dumps({
        "domain_scores": domain_scores,
        "reliability_score": overall_mean,
        "reliability_ci95": overall_ci,
        "latency_ms": lat_mean,
        "latency_p95_ms": _percentile(latencies, 95),
        "error_rate": round(errors / total_calls, 4) if total_calls else 0.0,
    }, indent=2))


if __name__ == "__main__":
    main()
