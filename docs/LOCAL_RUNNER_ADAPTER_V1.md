# Local Runner Adapter V1

Status: cold implementation notes.

This stage adds a local runner adapter for operator-approved A1 execution.

## Scope

- localhost HTTP only,
- explicit port required,
- bounded timeout,
- JSON request,
- no repository mutation,
- no shell execution,
- raw output is interpreted then summarized by cortex_b,
- tests use a fake urlopen and do not contact a real model.

## Initial target

Ollama local endpoint:

- http://127.0.0.1:11434/api/generate

## Activation path

1. build cortex-lc receipt,
2. build cortex-a receipt,
3. build runner with cortex_r.build_cortex_r,
4. call cortex_b.build_cortex_b with OPERATOR_APPROVE_A1,
5. inspect cortex-b receipt.

## Not included yet

- llama.cpp adapter,
- OpenAI-compatible chat adapter,
- streaming,
- tool calls,
- autonomous runs,
- background scheduling.
