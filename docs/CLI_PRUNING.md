# CLI pruning notes

Common commands:

```bash
python -m hex_cortex.cli --inspect-profile .hex-cortex --pretty
python -m hex_cortex.cli --prune-memory-profile .hex-cortex --pretty
python -m hex_cortex.cli --apply-memory-pruning-profile .hex-cortex --pretty
```

The profile command reports current local state.
The preview command reports proposed memory visibility updates.
The apply command writes a backup file before saving updates.

Backup path:

```text
.hex-cortex/memory.prune-backup.jsonl
```
