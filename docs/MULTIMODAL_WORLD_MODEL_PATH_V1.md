# Multimodal World Model Path V1

Status: cold implementation notes.

## Added expert domains

This stage adds candidate expert domains for:

- enterprise management,
- security and cyber,
- broad software development,
- screen vision,
- camera vision,
- voice input/output,
- multimodal world-model architecture.

## Added multimodal capabilities

The first multimodal capabilities are descriptors only:

- screen vision,
- camera vision,
- voice input,
- voice output.

They are operator-approved by default and do not allow raw input persistence.

## World-model direction

`world.compute` scores whether HEX-CORTEX is ready to become a true multimodal world-model candidate.

The score watches:

- multimodal inputs,
- persistent memory,
- predictive state,
- planning loop,
- surprise detection,
- safety receipts.

## Relationship to LeCun-style world models

HEX-CORTEX does not yet contain a learned world model.

This stage creates the governed scaffold needed before one can be integrated:

- multimodal inputs,
- memory,
- prediction,
- planning,
- surprise detection,
- safety receipts.

## Not included yet

- live screen capture,
- live camera capture,
- microphone capture,
- speech synthesis,
- learned latent dynamics,
- real JEPA/world-model training,
- autonomous physical-world action.

Those must remain candidate adapters until receipts, tests, and approval are in place.
