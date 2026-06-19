import hashlib
import json
from pathlib import Path

from hex_cortex.memory.cortex_frozen_encoder import build_frozen_encoder_descriptor
from hex_cortex.memory.cortex_world_model_decision_router import bridge_world_model_route_to_planner
from hex_cortex.memory.cortex_world_model_decision_router import route_world_model_decision
from hex_cortex.memory.planner_decision_packet import PlannerDecisionPacketJsonlStore
from hex_cortex.memory.planner_decision_packet import PlannerDecisionPacketRecord


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _active_bundle(tmp_path: Path, descriptor_hash: str, domain: str = "screen_lab_v1") -> Path:
    registry = tmp_path / "registry"
    registry.mkdir()
    weights = registry / "active_predictor.safetensors"
    weights.write_bytes(b"weights")
    candidate = {
        "candidate_type": "compact_world_model_candidate_v1",
        "candidate_hash": "c" * 64,
        "dataset_domain": domain,
        "encoder_descriptor_hash": descriptor_hash,
        "config": {
            "latent_dim": 2,
            "action_dim": 2,
            "hidden_dim": 8,
            "architecture": "residual_mlp_v1",
        },
    }
    candidate_path = registry / "active_candidate.json"
    candidate_path.write_text(json.dumps(candidate), encoding="utf-8")
    active = {
        "registry_type": "active_compact_world_model_v1",
        "candidate_file": candidate_path.name,
        "weights_file": weights.name,
        "candidate_hash": candidate["candidate_hash"],
        "weights_hash": _hash(weights),
        "dataset_domain": domain,
        "encoder_descriptor_hash": descriptor_hash,
        "registry_hash": "r" * 64,
    }
    active_path = registry / "active.json"
    active_path.write_text(json.dumps(active), encoding="utf-8")
    return active_path


def _environment(tmp_path: Path) -> tuple[Path, Path, Path]:
    root = tmp_path / "environment"
    output = root / "output"
    output.mkdir(parents=True)
    current = output / "current.png"
    goal = output / "goal.png"
    current.write_bytes(b"current")
    goal.write_bytes(b"goal")
    return root, current, goal


def _runner(weights_path, current_path, goal_path, candidate, descriptor, actions):
    assert weights_path.is_file()
    return {
        "allowed": True,
        "current_latent": [0.0, 0.0],
        "goal_latent": [1.0, 0.0],
        "predictions": [[0.8, 0.0], [0.2, 0.0]],
        "current_image_hash": _hash(current_path),
        "goal_image_hash": _hash(goal_path),
        "current_latent_hash": "1" * 64,
        "goal_latent_hash": "2" * 64,
        "blockers": [],
    }


def test_router_ranks_candidate_actions_without_dispatch(tmp_path: Path) -> None:
    descriptor = build_frozen_encoder_descriptor(device="cpu")
    active = _active_bundle(tmp_path, descriptor["descriptor_hash"])
    environment_root, current, goal = _environment(tmp_path)
    route_store = tmp_path / "routes.jsonl"

    route = route_world_model_decision(
        active_registry_path=active,
        environment_root=environment_root,
        current_image_path=current,
        goal_image_path=goal,
        environment_domain="screen_lab_v1",
        action_candidates=[
            {"action_id": "toward_goal", "action_values": [1.0, 0.0]},
            {"action_id": "weak_step", "action_values": [0.2, 0.0]},
        ],
        encoder_descriptor=descriptor,
        route_store_path=route_store,
        model_runner=_runner,
    )

    assert route["status"] == "advisory_ready"
    assert route["recommended_action_id"] == "toward_goal"
    assert route["candidate_rankings"][0]["rank"] == 1
    assert route["dispatch_allowed"] is False
    assert route["execution_performed"] is False
    assert route["latent_vector_persisted"] is False
    assert route["route_store"]["appended"] is True
    assert "current_latent" not in route
    assert "goal_latent" not in route


def test_router_blocks_domain_mismatch_before_model_call(tmp_path: Path) -> None:
    descriptor = build_frozen_encoder_descriptor(device="cpu")
    active = _active_bundle(tmp_path, descriptor["descriptor_hash"], domain="controlled_v1")
    environment_root, current, goal = _environment(tmp_path)
    called = False

    def runner(*args):
        nonlocal called
        called = True
        return {}

    route = route_world_model_decision(
        active_registry_path=active,
        environment_root=environment_root,
        current_image_path=current,
        goal_image_path=goal,
        environment_domain="screen_lab_v1",
        action_candidates=[{"action_id": "step", "action_values": [0.0, 0.0]}],
        encoder_descriptor=descriptor,
        model_runner=runner,
    )

    assert route["status"] == "blocked"
    assert "active_model_domain_mismatch" in route["blockers"]
    assert called is False


def test_bridge_attaches_advice_but_never_authorizes_execution(tmp_path: Path) -> None:
    profile = tmp_path / "profile"
    packet = PlannerDecisionPacketRecord(
        profile_path=str(profile),
        source_latent_id="latent-1",
        source_match_id="match-1",
        source_cost_id="cost-1",
        selected_skill="screen_skill",
        selected_action="toward_goal",
        planner_status="ready",
        planner_decision="planner_ready",
        next_action="stage_skill_execution_gate",
        action_allowed=True,
        registry_status="matched",
        match_score=0.9,
        action_score=0.9,
        compression_score=0.9,
        overall_confidence=0.9,
        reasons=["planner_packet_quality_ok"],
    )
    PlannerDecisionPacketJsonlStore(profile / "planner-decision-packet.jsonl").append(packet)
    route = {
        "route_type": "active_world_model_decision_route_v1",
        "status": "advisory_ready",
        "dispatch_allowed": False,
        "route_hash": "a" * 64,
        "active_candidate_hash": "c" * 64,
        "recommended_action_id": "toward_goal",
        "recommended_action_label": "toward_goal",
        "recommended_decision_score": 0.95,
    }

    bridge = bridge_world_model_route_to_planner(
        profile=profile,
        route=route,
        enforce_action_match=True,
    )

    assert bridge["status"] == "attached_for_operator_review"
    assert bridge["action_match"] is True
    assert bridge["context_attached"] is True
    assert bridge["execution_allowed"] is False
    assert bridge["execution_performed"] is False


def test_bridge_blocks_action_mismatch_when_enforced(tmp_path: Path) -> None:
    profile = tmp_path / "profile"
    packet = PlannerDecisionPacketRecord(
        profile_path=str(profile),
        source_latent_id="latent-1",
        source_match_id="match-1",
        source_cost_id="cost-1",
        selected_skill="screen_skill",
        selected_action="planner_action",
        planner_status="ready",
        planner_decision="planner_ready",
        next_action="stage_skill_execution_gate",
        action_allowed=True,
        registry_status="matched",
        match_score=0.9,
        action_score=0.9,
        compression_score=0.9,
        overall_confidence=0.9,
        reasons=["planner_packet_quality_ok"],
    )
    PlannerDecisionPacketJsonlStore(profile / "planner-decision-packet.jsonl").append(packet)
    route = {
        "route_type": "active_world_model_decision_route_v1",
        "status": "advisory_ready",
        "dispatch_allowed": False,
        "route_hash": "a" * 64,
        "active_candidate_hash": "c" * 64,
        "recommended_action_id": "world_model_action",
        "recommended_action_label": "world_model_action",
        "recommended_decision_score": 0.95,
    }

    bridge = bridge_world_model_route_to_planner(
        profile=profile,
        route=route,
        enforce_action_match=True,
    )

    assert bridge["status"] == "blocked"
    assert "planner_world_model_action_mismatch" in bridge["blockers"]
    assert bridge["execution_allowed"] is False
