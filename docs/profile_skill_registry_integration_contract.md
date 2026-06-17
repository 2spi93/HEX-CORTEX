# Profile Skill Registry Integration Contract

## Status

Opened as `PROFILE_SKILL_REGISTRY_INTEGRATION_V4_7`.

## Purpose

SkillRegistryIntegration connects the latest symbolic latent state to the persistent skill registry. It does not execute skills. It only selects and scores an active registered skill.

## Canonical command

```powershell
python -m hex_cortex.memory.profile_registry_cli .hex-cortex --pretty
```

## Summary command

```powershell
python -m hex_cortex.memory.profile_registry_cli .hex-cortex --summary --pretty
```

## Registry file

```text
.hex-cortex/skills.jsonl
```

## Match file

```text
.hex-cortex/skill-registry-match.jsonl
```

## Sources

```text
latent-state.jsonl
skills.jsonl
```

## Match fields

```text
match_id
created_at
profile_path
latent_id
registry_path
registry_status
latent_suggested_skill
matched_skill_id
matched_skill_name
matched_skill_confidence
match_score
match_reason
trigger_tags
action_score
compression_score
```

## Registry statuses

```text
matched
fallback
latent_missing
```

## Rule

A latent state is matched to active skills by trigger tags and confidence through the existing SkillLibrary. If no active skill matches, the system falls back to the latent suggested skill without claiming registry activation.

## Future path

```text
v4.8 planner decision packet
v4.9 replay learning from latent states
v5.0 controlled skill execution gate
```
