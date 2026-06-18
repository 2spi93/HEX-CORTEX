from hex_cortex.memory.cortex_branch_build_packet import CORTEX_BRANCH_BUILD_PACKET_FILENAME
from hex_cortex.memory.cortex_branch_build_packet import CortexBranchBuildPacketRecord


def test_branch_build_packet_imports() -> None:
    assert CORTEX_BRANCH_BUILD_PACKET_FILENAME == "cortex-branch-build-packet.jsonl"
    assert CortexBranchBuildPacketRecord.__name__ == "CortexBranchBuildPacketRecord"
