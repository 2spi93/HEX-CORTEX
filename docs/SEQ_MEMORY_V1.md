# Sequence Memory V1

Status: cold deterministic implementation.

## Purpose

Store an ordered sequence containing:

- initial state hash,
- action identifier,
- transition hash,
- observed state hash,
- prediction-error hash,
- surprise score and level,
- learning and repair signals.

## Chain contract

Each record contains:

- a sequential index,
- the previous record hash,
- a source key,
- its own sequence hash.

Repeated identical inputs are idempotent.
The chain verifier checks index order and previous-hash continuity.

## Lineage checks

The builder rejects inconsistent lineage between:

- initial state and transition source,
- transition and prediction-error receipt,
- observed state and prediction-error receipt.

## Safety properties

- no model call,
- no network call,
- no raw state persistence,
- append-only JSONL records,
- deterministic source keys,
- explicit blocked records on invalid lineage.

## Architecture position

This is the first ordered episodic layer.
It does not retrieve, rank, forget, summarize, or train from episodes yet.

The next stage may add episode indexing, retrieval, retention, and replay policies.
