"""Repository intelligence graph — structured repo context without training.

A small model navigates a repo far better with a structured representation than
with a giant paste of files (the GraphCoder / RepoGraph finding). This builds
that representation by pure static analysis of the Python sources: per module we
record imports, defined symbols (functions/classes, with line numbers), and the
names it references. From that we answer the queries an agent actually needs:

    find_symbol            where is X defined
    find_callers           who references X
    find_tests_for_symbol  which test files exercise X

It only reads and parses files (autonomy ladder step 1, static analysis) — no
execution, no network, no mutation. Files that fail to parse are recorded, never
fatal.
"""

from __future__ import annotations

import ast
from pathlib import Path

_GRAPH_TYPE = "cortex_repo_graph_v1"
_IGNORE_DIRS = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", ".ruff_cache", "node_modules", ".mypy_cache"}


def build_repo_graph(root: Path) -> dict[str, object]:
    """Parse every Python source under ``root`` into a navigable graph."""
    root = root.resolve()
    if not root.is_dir():
        raise ValueError("root must be an existing directory")

    modules: dict[str, dict[str, object]] = {}
    symbols: dict[str, list[dict[str, object]]] = {}
    unparsed: list[str] = []

    for path in sorted(root.rglob("*.py")):
        if any(part in _IGNORE_DIRS for part in path.relative_to(root).parts):
            continue
        rel = path.relative_to(root).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeError, OSError):
            unparsed.append(rel)
            continue
        imports = _extract_imports(tree)
        defines = _extract_definitions(tree)
        references = _extract_references(tree)
        modules[rel] = {
            "module": rel,
            "is_test": _is_test_file(rel),
            "imports": sorted(imports),
            "defines": defines,
            "references": sorted(references),
        }
        for definition in defines:
            symbols.setdefault(str(definition["name"]), []).append(
                {"module": rel, "kind": definition["kind"], "lineno": definition["lineno"]}
            )

    return {
        "graph_type": _GRAPH_TYPE,
        "root": str(root),
        "module_count": len(modules),
        "symbol_count": len(symbols),
        "unparsed_count": len(unparsed),
        "modules": modules,
        "symbols": symbols,
        "unparsed": unparsed,
    }


def find_symbol(graph: dict[str, object], name: str) -> list[dict[str, object]]:
    """All definition sites of ``name`` (function or class)."""
    symbols = graph.get("symbols")
    table = symbols if isinstance(symbols, dict) else {}
    return list(table.get(name, []))


def find_callers(graph: dict[str, object], name: str) -> list[str]:
    """Modules that reference ``name`` but do not themselves define it."""
    modules = graph.get("modules")
    table = modules if isinstance(modules, dict) else {}
    callers = []
    for rel, info in sorted(table.items()):
        if not isinstance(info, dict):
            continue
        references = info.get("references", [])
        defined = {str(d["name"]) for d in info.get("defines", []) if isinstance(d, dict)}
        if name in references and name not in defined:
            callers.append(rel)
    return callers


def summarize_module_contract(root: Path, module_rel_path: str) -> dict[str, object]:
    """Public contract of one module: top-level function/class signatures + docs.

    This is the ``summarize_module_contract`` agent-computer command — it gives a
    model the public surface of a module without the full body. Read-only.
    """
    target = (root.resolve() / module_rel_path).resolve()
    if not target.is_file():
        raise ValueError("module path does not resolve to a file")
    tree = ast.parse(target.read_text(encoding="utf-8"))
    functions: list[dict[str, object]] = []
    classes: list[dict[str, object]] = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and not node.name.startswith("_"):
            functions.append(_signature(node))
        elif isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
            methods = [
                _signature(child)
                for child in ast.iter_child_nodes(node)
                if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef)
                and not child.name.startswith("_")
            ]
            classes.append(
                {"name": node.name, "doc": _first_doc_line(node), "public_methods": methods}
            )
    return {
        "contract_type": "cortex_module_contract_v1",
        "module": module_rel_path,
        "public_functions": functions,
        "public_classes": classes,
    }


def find_tests_for_symbol(graph: dict[str, object], name: str) -> list[str]:
    """Test modules that reference ``name`` — candidate reproduction sites."""
    modules = graph.get("modules")
    table = modules if isinstance(modules, dict) else {}
    return [
        rel
        for rel, info in sorted(table.items())
        if isinstance(info, dict) and info.get("is_test") and name in info.get("references", [])
    ]


def _extract_imports(tree: ast.AST) -> set[str]:
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports


def _extract_definitions(tree: ast.AST) -> list[dict[str, object]]:
    defines: list[dict[str, object]] = []
    for node in ast.iter_child_nodes(tree):
        defines.extend(_definitions_in(node, prefix=""))
    return defines


def _definitions_in(node: ast.AST, *, prefix: str) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    if isinstance(node, ast.ClassDef):
        qualified = f"{prefix}{node.name}"
        out.append({"name": node.name, "qualname": qualified, "kind": "class", "lineno": node.lineno})
        for child in ast.iter_child_nodes(node):
            out.extend(_definitions_in(child, prefix=f"{qualified}."))
    elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
        qualified = f"{prefix}{node.name}"
        kind = "method" if prefix else "function"
        out.append({"name": node.name, "qualname": qualified, "kind": kind, "lineno": node.lineno})
    return out


def _extract_references(tree: ast.AST) -> set[str]:
    references: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                references.add(func.id)
            elif isinstance(func, ast.Attribute):
                references.add(func.attr)
    return references


def _signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> dict[str, object]:
    args = ast.unparse(node.args)
    returns = f" -> {ast.unparse(node.returns)}" if node.returns is not None else ""
    return {
        "name": node.name,
        "signature": f"{node.name}({args}){returns}",
        "doc": _first_doc_line(node),
        "lineno": node.lineno,
    }


def _first_doc_line(node: ast.AST) -> str | None:
    doc = ast.get_docstring(node)
    return doc.strip().splitlines()[0] if doc else None


def _is_test_file(rel_path: str) -> bool:
    name = rel_path.rsplit("/", 1)[-1]
    return (
        name.startswith("test_")
        or name.endswith("_test.py")
        or rel_path.startswith("tests/")
        or "/tests/" in rel_path
    )
