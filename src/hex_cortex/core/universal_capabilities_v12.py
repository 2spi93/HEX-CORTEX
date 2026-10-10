"""Universal-domain architecture contracts for HEX-CORTEX.

This is a *capability discovery and evidence-planning* layer, not an
implementation of chemistry, robotics, mathematics or physical control.
No brain, plugin, process, network, actuator or file is invoked.
A capability described here does NOT imply operational competence.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator

from hex_cortex.core.schemas import Task


class KnowledgeDomain(StrEnum):
    GENERAL = "general"
    MATHEMATICS = "mathematics"
    PHYSICS = "physics"
    CHEMISTRY = "chemistry"
    BIOLOGY = "biology"
    MATERIALS = "materials"
    ENGINEERING = "engineering"
    ELECTRONICS = "electronics"
    ASTRONOMY = "astronomy"
    SOFTWARE = "software"
    ROBOTICS = "robotics"
    AEROSPACE = "aerospace"


class DeploymentTarget(StrEnum):
    KNOWLEDGE = "knowledge"
    SOFTWARE = "software"
    SIMULATOR = "simulator"
    ROBOT = "robot"
    DRONE = "drone"
    PHYSICAL_DEVICE = "physical_device"


class RequestedOperation(StrEnum):
    ANALYZE = "analyze"
    RESEARCH = "research"
    CALCULATE = "calculate"
    SIMULATE = "simulate"
    OBSERVE = "observe"
    PROPOSE = "propose"
    ACTUATE = "actuate"


class CapabilitySpec(BaseModel):
    capability_id: str
    domains: list[KnowledgeDomain] = Field(min_length=1, max_length=6)
    target_kinds: list[DeploymentTarget] = Field(min_length=1, max_length=6)
    purpose: str = Field(min_length=8, max_length=280)
    verification_method: str = Field(min_length=8, max_length=180)
    maturity: str = "declared_only"

    @field_validator("capability_id")
    @classmethod
    def _valid_identifier(cls, value: str) -> str:
        if not re.fullmatch(r"[a-z][a-z0-9_]{1,63}", value):
            raise ValueError("invalid_capability_id")
        return value

    @field_validator("maturity")
    @classmethod
    def _no_unverified_certification(cls, value: str) -> str:
        if value not in {"declared_only", "existing_adapter_unverified"}:
            raise ValueError("operational_capability_requires_external_evidence")
        return value


def foundational_capability_catalog() -> tuple[CapabilitySpec, ...]:
    """An architectural map: entries are NOT installed expert systems."""
    catalog = (
        CapabilitySpec(
            capability_id="formal_math",
            domains=[KnowledgeDomain.MATHEMATICS],
            target_kinds=[DeploymentTarget.KNOWLEDGE, DeploymentTarget.SOFTWARE],
            purpose="Exact symbolic and numerical tools with domain-specific proof obligations",
            verification_method="Independent symbolic solver or mathematically checked result",
        ),
        CapabilitySpec(
            capability_id="physics_models",
            domains=[KnowledgeDomain.PHYSICS, KnowledgeDomain.ENGINEERING],
            target_kinds=[DeploymentTarget.KNOWLEDGE, DeploymentTarget.SIMULATOR],
            purpose="Physical quantities, units, conservation laws and predictive simulation",
            verification_method="Dimensional checks, reference experiment and uncertainty budget",
        ),
        CapabilitySpec(
            capability_id="molecular_chemistry",
            domains=[KnowledgeDomain.CHEMISTRY, KnowledgeDomain.MATERIALS],
            target_kinds=[DeploymentTarget.KNOWLEDGE, DeploymentTarget.SIMULATOR],
            purpose="Molecular structures, stoichiometry and properties from traceable scientific data",
            verification_method="Validated chemistry reference, units and reproducible calculation",
        ),
        CapabilitySpec(
            capability_id="biology_models",
            domains=[KnowledgeDomain.BIOLOGY],
            target_kinds=[DeploymentTarget.KNOWLEDGE, DeploymentTarget.SIMULATOR],
            purpose="Biological models with stated scope, evidence limitations and uncertainty",
            verification_method="Peer-reviewed evidence and domain-appropriate reproducibility",
        ),
        CapabilitySpec(
            capability_id="software_integration",
            domains=[KnowledgeDomain.SOFTWARE, KnowledgeDomain.ENGINEERING],
            target_kinds=[DeploymentTarget.SOFTWARE],
            purpose="Connect to developer applications through permissioned tools and receipts",
            verification_method="Isolated execution, reproducible tests and human review",
            maturity="existing_adapter_unverified",
        ),
        CapabilitySpec(
            capability_id="robotics_interface",
            domains=[KnowledgeDomain.ROBOTICS, KnowledgeDomain.ELECTRONICS],
            target_kinds=[DeploymentTarget.ROBOT, DeploymentTarget.PHYSICAL_DEVICE,
                          DeploymentTarget.SIMULATOR],
            purpose="Sensor interfaces, typed robot state and simulation-first decisions",
            verification_method="Simulator evaluation plus independent hardware safety controls",
            maturity="existing_adapter_unverified",
        ),
        CapabilitySpec(
            capability_id="aerial_robotics",
            domains=[KnowledgeDomain.AEROSPACE, KnowledgeDomain.ROBOTICS,
                     KnowledgeDomain.PHYSICS],
            target_kinds=[DeploymentTarget.DRONE, DeploymentTarget.SIMULATOR],
            purpose="Drone observation and simulated motion planning without actuator authority",
            verification_method="Flight simulation, constraints, operator review and physical failsafes",
        ),
        CapabilitySpec(
            capability_id="astronomy_models",
            domains=[KnowledgeDomain.ASTRONOMY, KnowledgeDomain.PHYSICS],
            target_kinds=[DeploymentTarget.KNOWLEDGE, DeploymentTarget.SIMULATOR],
            purpose="Astronomical calculations grounded in explicit assumptions and sourced data",
            verification_method="Reference ephemerides, independent calculations and unit checks",
        ),
    )
    if len({item.capability_id for item in catalog}) != len(catalog):
        raise ValueError("duplicate_capabilities")
    return catalog


def plan_universal_task(
    task: Task,
    *,
    target: DeploymentTarget = DeploymentTarget.KNOWLEDGE,
    operation: RequestedOperation = RequestedOperation.ANALYZE,
    catalog: tuple[CapabilitySpec, ...] | None = None,
    operator_approved: bool = False,
) -> dict[str, object]:
    """Describe possible expertise and missing capabilities; NEVER dispatch.

    Consent alone cannot authorize physical actuation. A separate trusted
    safety supervisor/driver is required, and is not supplied by this module.
    """
    specs = catalog if catalog is not None else foundational_capability_catalog()
    recognized = {domain.value for domain in KnowledgeDomain}
    hints = {hint.strip().casefold() for hint in task.domain_hints}
    selected = sorted(hints & recognized)
    unknown = sorted(hints - recognized)
    matched = [
        entry for entry in specs
        if any(domain.value in selected for domain in entry.domains)
        and target in entry.target_kinds
    ]
    physical = target in {
        DeploymentTarget.ROBOT, DeploymentTarget.DRONE,
        DeploymentTarget.PHYSICAL_DEVICE,
    }
    actuation_request = operation == RequestedOperation.ACTUATE
    blockers = []
    if not operator_approved:
        blockers.append("operator_planning_approval_required")
    if not selected:
        blockers.append("recognized_scientific_domain_required")
    if not matched:
        blockers.append("no_declared_matching_capability")
    if unknown:
        blockers.append("unrecognized_domain_hints")
    if actuation_request:
        blockers.append("actuation_requires_separate_safety_supervisor")
    if physical:
        blockers.append("physical_target_advisory_simulation_only")
    if target == DeploymentTarget.SOFTWARE and operation == RequestedOperation.ACTUATE:
        blockers.append("software_mutation_requires_separate_gateway")
    payload = {
        "plan_type": "universal_capability_advisory_v12",
        "status": "blocked" if blockers else "advisory_only",
        "target": target.value,
        "requested_operation": operation.value,
        "domain_hints": selected,
        "unrecognized_domains": unknown,
        "matched_capability_ids": [spec.capability_id for spec in matched],
        "capability_maturity": {
            spec.capability_id: spec.maturity for spec in matched
        },
        "no_match_means_no_claim_of_knowledge": True,
        "knowledge_retrieved": False,
        "calculation_executed": False,
        "simulation_executed": False,
        "physical_actuation_allowed": False,
        "physical_actuation_performed": False,
        "software_mutation_allowed": False,
        "software_mutation_performed": False,
        "external_model_called": False,
        "approval_for_plan_only": operator_approved,
        "blockers": sorted(set(blockers)),
        "next_action": (
            "provide_independently_verified_domain_adapter_and_source_evidence"
            if not blockers else "resolve_scope_and_safety_gates"
        ),
    }
    payload["plan_sha256"] = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return payload


class ScientificClaim(BaseModel):
    domain: KnowledgeDomain
    statement: str = Field(min_length=1, max_length=4000)
    source_refs: list[str] = Field(min_length=1, max_length=20)
    assumptions: list[str] = Field(default_factory=list, max_length=20)
    units: str | None = Field(default=None, max_length=120)


def review_scientific_claim(
    claim: ScientificClaim,
    *,
    source_verifier: Callable[[ScientificClaim], bool] | None = None,
) -> dict[str, object]:
    """A source-check receipt, not certification of scientific truth."""
    observed = False
    if source_verifier is not None:
        try:
            observed = source_verifier(claim) is True
        except Exception:  # noqa: BLE001 - never serialize arbitrary provider exception
            observed = False
    digest = hashlib.sha256(claim.model_dump_json().encode()).hexdigest()
    return {
        "receipt_type": "scientific_claim_review_v12",
        "domain": claim.domain.value,
        "claim_sha256": digest,
        "source_count": len(claim.source_refs),
        "assumption_count": len(claim.assumptions),
        "source_verifier_returned_true": observed,
        "scientifically_certified": False,
        "model_inference_is_proof": False,
        "raw_claim_persisted": False,
        "action_authorized": False,
        "next_action": "independent_replication_and_domain_expert_review",
    }
