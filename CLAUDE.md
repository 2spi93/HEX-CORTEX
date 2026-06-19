# CLAUDE.md

This file gives Claude Code persistent project instructions for HEX-CORTEX.

## Identity

You are working on HEX-CORTEX, a local-first intelligence kernel designed to become a governed coding, research, reasoning, geometry, and skill-improvement assistant.

Your job is to improve the repository without bypassing safety rails.

## Mandatory validation

Before claiming success, run:

```bash
python -m pytest
ruff check .
```

When a test fails, do not paper over it. Read the failure, fix the smallest relevant cause, then rerun targeted tests and the full suite.

## Operating mode

Default mode is cold and local:

- no live local model call,
- no external network operation from repo code,
- no shell execution except standard validation commands,
- no secrets,
- no raw prompt or raw model response persistence,
- no repo mutation outside the current branch,
- no autonomous task scheduling without explicit operator approval.

Use branch-first development. Keep commits small and explain why each file changed.

## Project north star

Make HEX-CORTEX increasingly useful by adding measured intelligence, not magical autonomy.

Target capabilities:

- expert coding assistance,
- web research synthesis with citations,
- mathematical and geometric reasoning,
- universe/cosmology model exploration,
- post-error reflection,
- post-success pattern mining,
- skill and preset evolution,
- local model readiness,
- governed autonomy.

## Learning behavior

After each task, extract a lesson:

- what failed,
- what worked,
- what should be reused,
- what should be blocked next time,
- whether a new skill or preset candidate should be proposed.

Never mutate skills automatically. Create candidate receipts first.

## Safe autonomy ladder

Use this ladder:

0. Docs and plans only.
1. Static analysis and JSONL receipts.
2. Dry-run contracts.
3. Local metadata/health checks with operator approval.
4. First real advisory call with no mutation.
5. Skill proposal from evidence.
6. Skill install only after human approval.
7. Autonomous scheduled runs only after separate approval and kill switch.

The repository is currently near step 3/4, not full autonomy.

## Jarvis-inspired ideas to adapt

Useful ideas from Jarvis-style systems:

- skill manifests,
- presets as multi-action recipes,
- static validation before execution,
- sandboxed skill lab,
- memory kernel with source and confidence,
- proactive curator that proposes changes instead of applying them silently.

Do not copy external code without license review and static inspection.

## Security posture

Kali or security tooling may be used only for local defensive audit, education, and authorized lab work. Do not implement intrusion, stealth, malware, credential theft, or third-party exploitation workflows.

## Response style for this repo

Report state like this:

- Branch:
- Commit:
- Files changed:
- Tests:
- Lint:
- Blockers:
- Next action:
