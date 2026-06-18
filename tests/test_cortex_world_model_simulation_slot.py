from hex_cortex.memory.cortex_world_model_simulation_slot import CORTEX_WORLD_MODEL_SIMULATION_SLOT_FILENAME
from hex_cortex.memory.cortex_world_model_simulation_slot import CortexWorldModelSimulationSlotRecord


def test_world_model_simulation_slot_imports() -> None:
    assert CORTEX_WORLD_MODEL_SIMULATION_SLOT_FILENAME == "cortex-world-model-simulation-slot.jsonl"
    assert CortexWorldModelSimulationSlotRecord.__name__ == "CortexWorldModelSimulationSlotRecord"
