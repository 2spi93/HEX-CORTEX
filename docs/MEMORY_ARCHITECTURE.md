# HEX-CORTEX Memory Architecture v0.1

HEX-CORTEX must not depend on long-context brute force.

The memory system is designed to retrieve a small, useful context packet before any expensive reasoning step.

## Core rule

```text
Index first.
Lexical search first.
Semantic fallback only when needed.
Small context packet always.
Compress after use.
```

## Why

Large context windows are expensive, slow, and can reduce precision when the model is overloaded with irrelevant text. HEX-CORTEX should not reread its whole past. It should locate the right memory quickly, inject little, then learn from the result.

## Memory layers

```text
L0 Raw Events
   Append-only canonical cognitive events.

L1 Workspace Snapshots
   Compact state from one task execution.

L2 Local Notes
   Markdown or JSONL knowledge fragments.

L3 Lexical Index
   Keyword, grep-like, TF-IDF/BM25-style metadata.

L4 Semantic Index
   Optional vector/embedding fallback.

L5 Compressed Tacit Memory
   Reusable rules learned from repeated outcomes.

L6 World Model State
   Predictive state used to estimate consequences and surprise.
```

## Retrieval pipeline

```text
user/task query
→ LocalKnowledgeIndex
→ RetrievalRouter
→ exact lexical match
→ BM25-style lexical ranking
→ semantic fallback if lexical score is weak
→ bounded ContextPacket
→ GlobalWorkspace
```

## Default retrieval limits

```text
top_k = 8
max_depth = 4
max_context_chars = 8000
semantic_fallback_threshold = 0.85
```

The exact numbers will be tuned by tests and runtime metrics.

## Two primary operations

### HexQuery

Retrieves relevant memory for a task.

Responsibilities:

- read the main index first
- search lexical index
- fallback to semantic layer only if needed
- return a bounded context packet
- expose scores and sources

### HexIndex

Maintains local indexes.

Responsibilities:

- scan configured directories manually or on explicit command
- build index entries
- update main index summaries
- avoid continuous scanning by default

## Memory compression

Raw evidence should not become long-term memory automatically.

Compression flow:

```text
raw event → workspace snapshot → episode summary → causal rule → tacit knowledge
```

A compressed memory must preserve:

- source event ids
- confidence
- sensitivity
- reason for storage
- last validation time
- deletion eligibility

## Surprise detection

HEX-CORTEX should compare predictions to outcomes.

```text
predicted_state_t+1 vs actual_state_t+1 → surprise_score
```

High surprise should create an error-memory candidate and may reduce cell trust until replay confirms the cause.

## Safety rule

No memory write is trusted unless it has lineage.

```text
No memory without source.
No retrieval without score.
No context injection without token/char budget.
No semantic fallback before lexical attempt.
```
