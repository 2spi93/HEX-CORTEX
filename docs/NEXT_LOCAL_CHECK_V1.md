# Next Local Check V1

Status: cold plan.

## Goal

Verify that a local model service or local model file is present before any advisory call.

## Allowed check

- local address or local file only,
- metadata only,
- bounded timeout,
- no prompt,
- no completion,
- no raw output persistence,
- no repository mutation,
- no broad shell action.

## Targets

- mock,
- Ollama on localhost,
- llama.cpp local path or localhost server,
- local OpenAI-compatible API on localhost.

## Receipt fields

- check_id,
- backend_kind,
- redacted_target,
- check_status,
- check_allowed,
- metadata_observed,
- prompt_sent false,
- completion_requested false,
- repo_mutation_performed false,
- shell_execution_performed false,
- next_action.

## Success next action

prepare_first_local_advisory_call_contract

## Blocked next action

repair_next_local_check
