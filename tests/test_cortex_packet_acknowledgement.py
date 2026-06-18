from hex_cortex.memory.cortex_packet_acknowledgement import CORTEX_PACKET_ACKNOWLEDGEMENT_FILENAME
from hex_cortex.memory.cortex_packet_acknowledgement import CortexPacketAcknowledgementRecord
from hex_cortex.memory.cortex_packet_acknowledgement import REQUIRED_PACKET_ACK


def test_packet_acknowledgement_imports() -> None:
    assert CORTEX_PACKET_ACKNOWLEDGEMENT_FILENAME == "cortex-packet-acknowledgement.jsonl"
    assert REQUIRED_PACKET_ACK == "ACK_PACKET_READY"
    assert CortexPacketAcknowledgementRecord.__name__ == "CortexPacketAcknowledgementRecord"
