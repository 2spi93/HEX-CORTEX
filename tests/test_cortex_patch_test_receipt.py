from hex_cortex.memory.cortex_patch_test_receipt import CORTEX_PATCH_TEST_RECEIPT_FILENAME
from hex_cortex.memory.cortex_patch_test_receipt import CortexPatchTestReceiptRecord


def test_patch_test_receipt_imports() -> None:
    assert CORTEX_PATCH_TEST_RECEIPT_FILENAME == "cortex-patch-test-receipt.jsonl"
    assert CortexPatchTestReceiptRecord.__name__ == "CortexPatchTestReceiptRecord"
