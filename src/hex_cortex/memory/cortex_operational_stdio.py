from __future__ import annotations

import json
import sys
from typing import TextIO

from hex_cortex.memory.cortex_operational_rpc import handle_cortex_operational_rpc_message
from hex_cortex.memory.cortex_rpc import CortexRpcSession
from hex_cortex.memory.cortex_rpc import rpc_error


def serve_cortex_operational_stdio(
    input_stream: TextIO = sys.stdin,
    output_stream: TextIO = sys.stdout,
) -> int:
    session = CortexRpcSession()
    for raw_line in input_stream:
        line = raw_line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            response = rpc_error(None, -32700, "Parse error")
        else:
            if not isinstance(message, dict):
                response = rpc_error(None, -32600, "Invalid Request")
            else:
                response = handle_cortex_operational_rpc_message(
                    message,
                    session=session,
                )
        if response is not None:
            output_stream.write(json.dumps(response, sort_keys=True) + "\n")
            output_stream.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(serve_cortex_operational_stdio())
