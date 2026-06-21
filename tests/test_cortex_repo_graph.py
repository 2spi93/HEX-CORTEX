from pathlib import Path

import pytest

from hex_cortex.memory.cortex_repo_graph import build_repo_graph
from hex_cortex.memory.cortex_repo_graph import find_callers
from hex_cortex.memory.cortex_repo_graph import find_symbol
from hex_cortex.memory.cortex_repo_graph import find_tests_for_symbol
from hex_cortex.memory.cortex_repo_graph import summarize_module_contract


def _mini_repo(root: Path) -> None:
    (root / "pkg").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "pkg" / "core.py").write_text(
        "def add(a, b):\n    return a + b\n\n\nclass Calc:\n    def total(self, xs):\n        return sum(xs)\n",
        encoding="utf-8",
    )
    (root / "pkg" / "app.py").write_text(
        "from pkg.core import add\n\n\ndef run():\n    return add(1, 2)\n",
        encoding="utf-8",
    )
    (root / "tests" / "test_core.py").write_text(
        "from pkg.core import add\n\n\ndef test_add():\n    assert add(1, 1) == 2\n",
        encoding="utf-8",
    )
    # An unparsable file must be recorded, not fatal.
    (root / "broken.py").write_text("def oops(:\n", encoding="utf-8")
    # Ignored directories must be skipped.
    (root / "__pycache__").mkdir()
    (root / "__pycache__" / "junk.py").write_text("x = (\n", encoding="utf-8")


def test_graph_indexes_modules_and_symbols(tmp_path: Path) -> None:
    _mini_repo(tmp_path)
    graph = build_repo_graph(tmp_path)
    assert graph["graph_type"] == "cortex_repo_graph_v1"
    assert "pkg/core.py" in graph["modules"]
    assert "broken.py" in graph["unparsed"]
    assert "__pycache__/junk.py" not in graph["unparsed"]
    assert graph["module_count"] == 3


def test_find_symbol_locates_definition(tmp_path: Path) -> None:
    _mini_repo(tmp_path)
    graph = build_repo_graph(tmp_path)
    add_defs = find_symbol(graph, "add")
    assert len(add_defs) == 1
    assert add_defs[0]["module"] == "pkg/core.py"
    assert add_defs[0]["kind"] == "function"
    total = find_symbol(graph, "total")
    assert total[0]["kind"] == "method"


def test_find_callers_excludes_definition_site(tmp_path: Path) -> None:
    _mini_repo(tmp_path)
    graph = build_repo_graph(tmp_path)
    callers = find_callers(graph, "add")
    assert "pkg/app.py" in callers
    assert "tests/test_core.py" in callers
    assert "pkg/core.py" not in callers


def test_find_tests_for_symbol(tmp_path: Path) -> None:
    _mini_repo(tmp_path)
    graph = build_repo_graph(tmp_path)
    tests = find_tests_for_symbol(graph, "add")
    assert tests == ["tests/test_core.py"]


def test_summarize_module_contract(tmp_path: Path) -> None:
    _mini_repo(tmp_path)
    contract = summarize_module_contract(tmp_path, "pkg/core.py")
    assert contract["contract_type"] == "cortex_module_contract_v1"
    fn_names = {f["name"] for f in contract["public_functions"]}
    assert "add" in fn_names
    add_sig = next(f for f in contract["public_functions"] if f["name"] == "add")
    assert add_sig["signature"] == "add(a, b)"
    class_names = {c["name"] for c in contract["public_classes"]}
    assert "Calc" in class_names
    calc = next(c for c in contract["public_classes"] if c["name"] == "Calc")
    assert any(m["name"] == "total" for m in calc["public_methods"])


def test_summarize_rejects_missing_module(tmp_path: Path) -> None:
    _mini_repo(tmp_path)
    with pytest.raises(ValueError):
        summarize_module_contract(tmp_path, "pkg/nope.py")


def test_build_rejects_non_directory(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        build_repo_graph(tmp_path / "does_not_exist")


def test_runs_on_this_repository() -> None:
    # Smoke test against the real source tree: it should parse and index.
    root = Path(__file__).resolve().parents[1]
    graph = build_repo_graph(root / "src")
    assert graph["module_count"] > 50
    assert find_symbol(graph, "build_repo_graph")
