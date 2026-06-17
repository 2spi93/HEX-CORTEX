# Profile Registry Review Signature Packet Contract

## Status

Opened as `PROFILE_REGISTRY_REVIEW_SIGNATURE_PACKET_V6_1`.

## Purpose

RegistryReviewSignaturePacket records a human signature packet for the latest skill registry review document. It stores signer identity, the selected skill, the document decision, and a SHA-256 hash of the document evidence. It does not apply changes to `skills.jsonl`.

## Canonical command

```powershell
python -m hex_cortex.memory.profile_signature_cli .hex-cortex --pretty
```

## Explicit signature command

```powershell
python -m hex_cortex.memory.profile_signature_cli .hex-cortex --signature deferred --pretty
```

## Summary command

```powershell
python -m hex_cortex.memory.profile_signature_cli .hex-cortex --summary --pretty
```

## Signature file

```text
.hex-cortex/registry-review-signature-packet.jsonl
```

## Source

```text
skill-registry-review-document.jsonl
```

## Signature decisions

```text
signature_signed
signature_needs_more_evidence
signature_deferred
signature_rejected
signature_blocked
```

## Rule

A signature may become signed only when the source review document is ready. Documents requiring activation review must produce a needs-more-evidence signature state by default.

## Current watch-path expectation

```text
document_needs_registry_activation
→ signature_needs_more_evidence
→ prepare_skill_activation_review
```

## Future path

```text
v6.2 registry review dry run
v6.3 registry activation artifact
v6.4 operator signature ledger
```
