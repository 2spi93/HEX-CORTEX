from __future__ import annotations

import argparse
import json
import math
import re
import statistics
import time
import urllib.request
from dataclasses import dataclass
from typing import Any

_DEFAULT_ENDPOINT = "http://127.0.0.1:8080"
_NUM = re.compile(r"-?\d+(?:\.\d+)?")
_JSON_OBJECT = re.compile(r"\{.*\}", re.DOTALL)


@dataclass(frozen=True)
class Task:
    task_id: str
    prompt: str
    expected: str
    is_numeric: bool


def _num(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else str(value)


def _coding_specs() -> list[tuple[str, str, bool]]:
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
    for upper in (100, 500, 1000):
        count = sum(1 for x in range(1, upper) if x % 3 == 0 or x % 5 == 0)
        tasks.append((f"Reply with ONLY how many integers in 1..{upper - 1} are divisible by 3 or 5.", str(count), True))
    for bits in ("101101", "11111111", "100000", "1010101"):
        tasks.append((f"Reply with ONLY the decimal value of binary {bits}.", str(int(bits, 2)), True))

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
    return tasks


def _general_specs() -> list[tuple[str, str, bool]]:
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
    tasks.append(("Reply with ONLY the number of minutes in 3.5 hours.", "210", True))
    tasks.append(("Reply with ONLY the number of meters in 4.2 kilometers.", "4200", True))
    tasks.append(("Reply with ONLY the number of seconds in 2 hours.", "7200", True))
    tasks.append(("A car travels 240 km in 3 hours. Reply with ONLY its speed in km/h.", "80", True))
    tasks.append(("Reply with ONLY km traveled going 90 km/h for 2.5 hours.", "225", True))
    tasks.append(("A bat and ball cost $1.10; the bat costs $1.00 more than the ball. Reply ONLY with the ball price in dollars.", "0.05", True))
    tasks.append(("5 machines make 5 widgets in 5 minutes. Reply ONLY with minutes for 100 machines to make 100 widgets.", "5", True))
    tasks.append(("Reply with ONLY the angle in degrees between clock hands at 3:15.", "7.5", True))
    tasks.append(("Reply with ONLY how many times digit 7 appears writing 1 to 100.", "20", True))
    return tasks


_RESEARCH_SPECS: list[tuple[str, str, bool]] = [
    ("Reply with ONLY the atomic number of hydrogen.", "1", True),
    ("Reply with ONLY the atomic number of carbon.", "6", True),
    ("Reply with ONLY the atomic number of oxygen.", "8", True),
    ("Reply with ONLY the atomic number of iron.", "26", True),
    ("Reply with ONLY the atomic number of gold.", "79", True),
    ("Reply with ONLY the atomic number of uranium.", "92", True),
    ("Reply with ONLY the atomic number of helium.", "2", True),
    ("Reply with ONLY the capital city of Japan.", "tokyo", False),
    ("Reply with ONLY the capital city of France.", "paris", False),
    ("Reply with ONLY the capital city of Australia.", "canberra", False),
    ("Reply with ONLY the capital city of Canada.", "ottawa", False),
    ("Reply with ONLY the capital city of Brazil.", "bras", False),
    ("Reply with ONLY the capital city of Egypt.", "cairo", False),
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
    ("Reply with ONLY the SI base unit of electric current.", "ampere", False),
    ("Reply with ONLY the SI base unit of temperature.", "kelvin", False),
    ("Reply with ONLY the SI base unit of mass.", "kilogram", False),
]


def _materialize_tasks(specs: list[tuple[str, str, bool]]) -> list[Task]:
    return [Task(f"t{index}", prompt, expected, is_numeric) for index, (prompt, expected, is_numeric) in enumerate(specs, start=1)]


DOMAIN_TASKS: dict[str, list[Task]] = {
    "coding": _materialize_tasks(_coding_specs()),
    "research": _materialize_tasks(_RESEARCH_SPECS),
    "general": _materialize_tasks(_general_specs()),
}


def build_prompt(domain: str, tasks: list[Task]) -> str:
    lines = [
        f"Benchmark domain: {domain}.",
        "Return ONLY a JSON object mapping each task id to its final answer string.",
        "No reasoning. No markdown. No prose. No code fences.",
        'Example shape: {"t1": "answer", "t2": "answer"}.',
        "Tasks:",
    ]
    for task in tasks:
        lines.append(f"- {task.task_id}: {task.prompt}")
    return "\n".join(lines)


def build_openai_request_body(*, model: str, prompt: str, temperature: float, seed: int) -> dict[str, Any]:
    return {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a strict benchmark responder. Return a compact JSON object only. "
                    "Disable chain-of-thought and provide final answers only."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
        "seed": seed,
        "max_tokens": 256,
        "stream": False,
        "chat_template_kwargs": {"enable_thinking": False},
        "stop": ["</think>"],
    }


def _request(url: str, body: dict[str, Any], timeout: int = 240) -> dict[str, Any]:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _extract_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        match = _JSON_OBJECT.search(stripped)
        if not match:
            return {}
        try:
            payload = json.loads(match.group(0))
        except json.JSONDecodeError:
            return {}
    return payload if isinstance(payload, dict) else {}


def _grade_answer(text: str, expected: str, is_numeric: bool) -> int:
    if is_numeric:
        target = float(expected)
        return int(any(abs(float(token) - target) < 1e-9 for token in _NUM.findall(str(text).replace(",", ""))))
    return int(expected in str(text).strip().lower())


def grade_batch_response(tasks: list[Task], response_text: str) -> dict[str, Any]:
    payload = _extract_json_object(response_text)
    graded_answers: dict[str, int] = {}
    correct = 0
    for task in tasks:
        answer = payload.get(task.task_id, "")
        score = _grade_answer(str(answer), task.expected, task.is_numeric)
        graded_answers[task.task_id] = score
        correct += score
    total = len(tasks)
    return {
        "correct": correct,
        "total": total,
        "score": round(correct / total, 3) if total else 0.0,
        "graded_answers": graded_answers,
    }


def _ms(values: list[float]) -> tuple[float, float]:
    mean = statistics.mean(values)
    stdev = statistics.stdev(values) if len(values) > 1 else 0.0
    return round(mean, 3), round(stdev, 3)


def run_benchmark(*, endpoint: str, model: str, runs: int, temperature: float) -> dict[str, Any]:
    print(
        f"api=openai-batch endpoint={endpoint} model={model} runs={runs} temp={temperature} "
        f"tasks/domain={{k: len(v) for k, v in DOMAIN_TASKS.items()}}",
        flush=True,
    )

    warmup_prompt = 'Return ONLY a JSON object like {"t1":"ok"}. Task: t1=Reply with ONLY: ok'
    _request(
        f"{endpoint}/v1/chat/completions",
        build_openai_request_body(model=model, prompt=warmup_prompt, temperature=0.0, seed=1),
    )

    per_domain_runs: dict[str, list[float]] = {domain: [] for domain in DOMAIN_TASKS}
    overall_runs: list[float] = []
    latency_per_answer_ms: list[float] = []

    for run in range(1, runs + 1):
        run_correct = 0
        run_total = 0
        for domain, tasks in DOMAIN_TASKS.items():
            start = time.perf_counter()
            payload = _request(
                f"{endpoint}/v1/chat/completions",
                build_openai_request_body(
                    model=model,
                    prompt=build_prompt(domain, tasks),
                    temperature=temperature,
                    seed=run,
                ),
            )
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            text = payload["choices"][0]["message"]["content"]
            graded = grade_batch_response(tasks, text)
            score = float(graded["score"])
            per_domain_runs[domain].append(score)
            run_correct += int(graded["correct"])
            run_total += int(graded["total"])
            latency_per_answer_ms.append(elapsed_ms / len(tasks))
            print(
                f"run {run}/{runs} domain={domain}: {graded['correct']}/{graded['total']}={score:.3f} "
                f"batch_ms={elapsed_ms:.1f} per_answer_ms={elapsed_ms / len(tasks):.1f}",
                flush=True,
            )
        overall = run_correct / run_total
        overall_runs.append(overall)
        print(f"run {run}/{runs}: overall={run_correct}/{run_total}={overall:.3f}", flush=True)

    print("\n=== STATISTICS (mean +/- stdev across runs) ===")
    domain_scores: dict[str, float] = {}
    domain_stdev: dict[str, float] = {}
    for domain, tasks in DOMAIN_TASKS.items():
        mean, sd = _ms(per_domain_runs[domain])
        domain_scores[domain] = mean
        domain_stdev[domain] = sd
        print(f"{domain:8}: {mean:.3f} +/- {sd:.3f}  (n={len(tasks)} x {runs} runs)")
    reliability_mean, reliability_sd = _ms(overall_runs)
    latency_mean = round(statistics.mean(latency_per_answer_ms), 1)
    latency_sd = round(statistics.stdev(latency_per_answer_ms), 1) if len(latency_per_answer_ms) > 1 else 0.0
    print(f"reliability: {reliability_mean:.3f} +/- {reliability_sd:.3f}")
    print(f"latency_ms : {latency_mean} +/- {latency_sd}")

    results = {
        "domain_scores": domain_scores,
        "domain_stdev": domain_stdev,
        "reliability_score": reliability_mean,
        "reliability_stdev": reliability_sd,
        "latency_ms": latency_mean,
        "latency_stdev": latency_sd,
        "protocol": "openai_batch_json_v1",
    }
    print("\n=== RESULTS (paste into the brain registration config) ===")
    print(json.dumps({
        "domain_scores": domain_scores,
        "reliability_score": reliability_mean,
        "latency_ms": latency_mean,
    }, indent=2))
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m hex_cortex.memory.cortex_cognitive_brain_benchmark")
    parser.add_argument("--endpoint", default=_DEFAULT_ENDPOINT)
    parser.add_argument("--model", required=True)
    parser.add_argument("--runs", type=int, default=2)
    parser.add_argument("--temperature", type=float, default=0.2)
    args = parser.parse_args(argv)
    run_benchmark(
        endpoint=args.endpoint.rstrip("/"),
        model=args.model,
        runs=args.runs,
        temperature=args.temperature,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
