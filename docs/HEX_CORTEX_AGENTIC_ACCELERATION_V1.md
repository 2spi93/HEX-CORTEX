# HEX-CORTEX Agentic Acceleration V1

Status: cold design and operating doctrine.

This document defines the fastest safe path from the current local-ready rail to an active local model assistant.

## Current baseline

HEX-CORTEX has a validated local rail:

1. local model backend config plan,
2. config dry run,
3. local runtime contract,
4. final local-only step,
5. tests and lint green.

This is not yet full autonomy. It is a safe launch rail.

## Target identity

HEX-CORTEX should become a multi-domain expert assistant with these expert surfaces:

- coding expert,
- software architecture expert,
- web research expert,
- mathematical reasoning expert,
- geometry of the universe and cosmology reasoning expert,
- systems engineering expert,
- safety and audit expert,
- skill and preset curator,
- reflection and self-improvement analyst.

## Non-negotiable principle

It may improve itself only through evidence. No self-modification without receipts, tests, and operator approval.

## Fastest safe roadmap

### Gate A — Agent manifests

Add project-level instructions for Codex and Claude Code.

Outputs:

- AGENTS.md,
- CLAUDE.md,
- validation commands,
- safety boundaries.

Status: implemented in this branch.

### Gate B — Expert domain registry

Create a local registry that describes expert domains and the evidence needed to trust their outputs.

Suggested domains:

- coding,
- research,
- mathematics,
- geometry,
- physics and cosmology,
- architecture,
- security defensive audit,
- hardware integration,
- mobile cockpit,
- skill curation.

Each domain should include:

- scope,
- allowed tools,
- forbidden actions,
- required evidence,
- confidence rubric,
- candidate skills.

### Gate C — Skill import doctrine

External skill catalogs can inspire HEX-CORTEX, but they must not be installed blindly.

Adopt the Jarvis-style idea of:

- skills as reusable capabilities,
- presets as operator workflows,
- static validation before runtime execution,
- sandbox or local dry-run before activation,
- human approval before install.

### Gate D — Reflection receipts

Every failure and success produces a JSONL learning receipt.

A receipt should include:

- task id,
- goal,
- inputs,
- branch,
- commits,
- tests run,
- lint result,
- failures,
- fixes,
- reusable pattern,
- candidate skill update,
- confidence,
- next action.

### Gate E — Local backend health check

First real interaction with a local backend must be metadata or health only.

Allowed:

- localhost endpoint status,
- model listing,
- version metadata,
- timeout check.

Forbidden at this gate:

- prompts,
- completions,
- code execution,
- repo mutation,
- raw response persistence,
- background runs.

### Gate F — First advisory call

Only after Gate E passes:

- send a tiny non-sensitive prompt,
- no tools,
- no repo mutation,
- no shell,
- no secrets,
- persist only redacted receipt and hashes,
- compare answer against expected schema.

### Gate G — Skill proposal loop

After repeated successful patterns:

- propose candidate skill,
- test candidate on fixtures,
- score usefulness,
- require operator approval before install.

### Gate H — Governed autonomy

Autonomy is not a single switch. It must be scoped by level:

- L0: no autonomy, docs only,
- L1: analysis and receipts,
- L2: dry runs,
- L3: operator-approved local health checks,
- L4: operator-approved advisory calls,
- L5: scheduled read-only analysis,
- L6: skill proposals,
- L7: supervised execution with kill switch.

Current target: reach L4, not L7.

## Jarvis evaluation

Jarvis OS looks directionally strong as a personal assistant architecture:

- local/self-hosted posture,
- FastAPI service,
- voice pipeline,
- memory kernel,
- mission engine,
- tool and skill system,
- multi-LLM including local Ollama,
- proactivity with governance.

Jarvis Skills is useful as a catalog pattern:

- explicit skills,
- presets,
- views,
- manifests,
- static validation,
- real execution moved to sandboxed OS tooling.

What HEX-CORTEX should borrow:

- skill manifest discipline,
- static validation before install,
- presets as operator-approved workflows,
- sandbox-first mindset,
- curator that proposes improvements.

What HEX-CORTEX should not copy blindly:

- any external code execution,
- broad filesystem/network permissions,
- automatic install of community skills,
- background autonomy without gates,
- any security or Kali workflow beyond authorized defensive lab use.

## Hardware and mobile path

Hardware should be treated as an execution surface, not the brain.

Preferred hardware ladder:

1. laptop CPU mock/local metadata,
2. Ollama on workstation,
3. llama.cpp local model path,
4. GPU workstation,
5. mini-PC or NUC,
6. Jetson/NPU only after model and memory footprint are proven.

Mobile should be a cockpit:

- inspect receipts,
- approve gates,
- read summaries,
- trigger safe dry runs.

Mobile should not be the primary local model runtime for heavy models.

## Closing target

The next coding milestone is not unlimited autonomy. It is:

`local_model_active_advisory_v1`

Definition:

- operator-approved,
- local backend only,
- one tiny advisory call,
- no tools,
- no repo mutation,
- redacted receipt,
- tests and lint passing.
