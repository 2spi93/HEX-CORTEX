"""V21 JEPA-compatible *evaluation interface*, not a trained JEPA or model.

An external learned encoder/predictor may later supply bounded abstract
state vectors. This pure-Python module tests their predictions against
*observed* state vectors without invoking a neural model, doing gradient
training or authorizing an action. It is suitable for synthetic fixtures.
"""
from __future__ import annotations

import hashlib
import json
from fractions import Fraction

from pydantic import BaseModel, ConfigDict, Field, model_validator

from hex_cortex.core.cortex_exact_math_v13 import calculate_exact


class LatentWorldObservation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    observation_id: str = Field(min_length=2, max_length=128)
    encoder_identity_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    predictor_identity_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    horizon_steps: int = Field(ge=1, le=128)
    predicted_latent: tuple[str, ...] = Field(min_length=1, max_length=64)
    observed_latent: tuple[str, ...] = Field(min_length=1, max_length=64)
    origin: str = Field(pattern=r"^(synthetic_fixture|externally_supplied)$")

    @model_validator(mode="after")
    def validate_vector_lengths(self) -> LatentWorldObservation:
        if len(self.predicted_latent) != len(self.observed_latent):
            raise ValueError("latent_prediction_dimension_mismatch")
        for value in [*self.predicted_latent, *self.observed_latent]:
            _bounded_fraction(value)
        return self


def _bounded_fraction(expression: str) -> Fraction:
    if not isinstance(expression, str) or len(expression) > 64:
        raise ValueError("latent_prediction_scalar_budget")
    result = calculate_exact(expression, approved=True)
    if result.get("status") != "verified_exact_arithmetic":
        raise ValueError("latent_prediction_scalar_invalid")
    rational = Fraction(int(result["numerator"]), int(result["denominator"]))
    if rational.numerator.bit_length() > 160 or rational.denominator.bit_length() > 160:
        raise ValueError("latent_prediction_scalar_budget")
    return rational


def score_latent_prediction(
    observation: LatentWorldObservation,
    *,
    operator_approved: bool = False,
) -> dict[str, object]:
    """Score exact MAE/MSE in latent units; metric is NOT physical truth."""
    if not operator_approved:
        return {
            "status": "blocked", "reason": "latent_operator_approval_required",
            "model_called": False, "physical_action_authorized": False,
        }
    errors = [
        _bounded_fraction(p) - _bounded_fraction(y)
        for p, y in zip(observation.predicted_latent,
                        observation.observed_latent, strict=True)
    ]
    n = len(errors)
    mae = sum((abs(e) for e in errors), Fraction()) / n
    mse = sum((e * e for e in errors), Fraction()) / n
    # Input identity and source declaration are redacted from the receipt.
    receipt = {
        "status": "scored_latent_prediction",
        "report_type": "hex_cortex_jepa_latent_eval_contract_v21",
        "observation_sha256": hashlib.sha256(
            json.dumps(observation.model_dump(mode="json"), sort_keys=True).encode()
        ).hexdigest(),
        "horizon_steps": observation.horizon_steps,
        "embedding_dimensions": n,
        "mean_absolute_latent_error": str(mae),
        "mean_squared_latent_error": str(mse),
        "provenance_kind": observation.origin,
        "learned_jepa_model_loaded": False,
        "model_called": False,
        "physical_state_prediction_certified": False,
        "scientific_truth_certified": False,
        "physical_action_authorized": False,
    }
    return receipt
