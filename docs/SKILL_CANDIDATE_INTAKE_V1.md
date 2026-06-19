# Skill Candidate Intake V1

Status: cold doctrine.

This file defines how HEX-CORTEX can learn from external skill catalogs such as Jarvis Skills without executing untrusted code.

## Goal

Convert repeated successes, failures, and useful external ideas into candidate skills or presets.

Candidate means proposed only. It is not installed and not executed.

## Intake sources

Allowed sources:

- internal task receipts,
- repeated errors,
- repeated successful repairs,
- cited web research,
- external skill catalogs after static review,
- operator-provided ideas.

## Candidate states

1. observed,
2. statically_reviewed,
3. mapped_to_domain,
4. fixture_tested,
5. approved,
6. installed,
7. retired.

Only the operator can move a candidate to approved or installed.

## Required candidate fields

- candidate_id,
- created_at,
- source_type,
- source_url,
- source_license,
- name,
- description,
- target_domain,
- required_tools,
- required_environment,
- filesystem_permissions,
- network_permissions,
- execution_risk,
- test_fixture,
- expected_outputs,
- validation_commands,
- approval_status,
- receipt_hash.

## Jarvis-style mapping

Jarvis Skills separates:

- skills: conversational capabilities,
- presets: multi-action recipes,
- views: visual surfaces.

HEX-CORTEX mapping:

- Jarvis skill -> Cortex candidate skill,
- Jarvis preset -> Cortex operator workflow candidate,
- Jarvis view -> Cortex cockpit candidate.

## Static review checklist

Before importing an idea:

- check license,
- check required secrets,
- check network permissions,
- check filesystem permissions,
- check whether it executes code,
- check whether it stores raw prompts or responses,
- check whether it needs a sandbox,
- check whether the capability already exists.

## Activation policy

Do not activate a candidate directly.

The safe path is:

1. candidate receipt,
2. fixture test,
3. usefulness score,
4. operator approval,
5. install receipt,
6. rollback plan.

## First candidate families

- coding repair expert,
- web research expert with citations,
- geometry and universe reasoning expert,
- local model operator,
- defensive audit reviewer,
- hardware planner,
- mobile cockpit summarizer,
- reflection curator.
