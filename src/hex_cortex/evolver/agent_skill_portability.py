"""Read-only interoperability bridge between SkillRecord and Agent Skills.

No scripts are executed and no skill is activated by an export. Only active
records should be exported into a runtime's skill discovery directory.
"""

from __future__ import annotations

import argparse
import json
import re
from collections.abc import Sequence
from pathlib import Path

from hex_cortex.evolver.schemas import SkillRecord, SkillStatus
from hex_cortex.evolver.skill_jsonl_store import SkillJsonlStore

_SKILL_NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    slug = slug[:64].rstrip("-")
    if not _SKILL_NAME.fullmatch(slug):
        raise ValueError("skill name cannot be converted to a portable name")
    return slug


def render_agent_skill(skill: SkillRecord) -> str:
    """Produce a specification-compatible minimal SKILL.md as plain text."""
    if skill.status != SkillStatus.ACTIVE:
        raise ValueError("only active skills may be exported")
    slug = slugify(skill.name)
    description = " ".join(skill.description.split())
    if not 1 <= len(description) <= 1024:
        raise ValueError("portable skill description must be 1-1024 characters")
    steps = [step.strip() for step in skill.workflow_steps if step.strip()]
    if not steps:
        raise ValueError("portable skill requires non-empty workflow steps")
    # JSON-encoded strings are a legal quoted scalar subset of YAML. This
    # also avoids injections via special frontmatter characters and newlines.
    header = [
        "---",
        f"name: {json.dumps(slug)}",
        f"description: {json.dumps(description, ensure_ascii=False)}",
        "---",
        "",
        f"# {skill.name.strip()}",
        "",
        "Use when the task matches this validated HEX-CORTEX workflow.",
        "This export supplies instructions only. It does not confer execution rights.",
        "",
        "## Workflow",
        "",
    ]
    header.extend(f"{index}. {step}" for index, step in enumerate(steps, start=1))
    header.extend(
        [
            "",
            "## Verification",
            "",
            "Check outputs against the task acceptance criteria.",
            "Keep evidence and receipts; do not bypass operator gates.",
            "",
        ]
    )
    return "\n".join(header)


def export_active_skills(input_jsonl: Path, output_root: Path) -> list[Path]:
    """Export active JSONL skills to SKILL.md directories, without running them."""
    skills = SkillJsonlStore(input_jsonl).active()
    names = [slugify(skill.name) for skill in skills]
    if len(names) != len(set(names)):
        raise ValueError("skill names collide after portable normalization")
    rendered = [(name, render_agent_skill(skill)) for name, skill in zip(names, skills, strict=True)]
    output_root = output_root.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    paths = []
    for name, text in rendered:
        directory = (output_root / name).resolve()
        if not directory.is_relative_to(output_root):
            raise ValueError("portable skill path escapes output root")
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / "SKILL.md"
        if target.exists():
            raise FileExistsError(f"existing skill requires manual review: {target}")
        target.write_text(text, encoding="utf-8")
        paths.append(target)
    return paths


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hexcortex-skills")
    parser.add_argument("input_jsonl", type=Path)
    parser.add_argument("output_directory", type=Path)
    args = parser.parse_args(argv)
    try:
        paths = export_active_skills(args.input_jsonl, args.output_directory)
    except (OSError, ValueError) as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc)}))
        return 2
    print(
        json.dumps(
            {
                "status": "exported",
                "skill_count": len(paths),
                "paths": [str(path) for path in paths],
                "skill_executed": False,
                "skill_activated": False,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
