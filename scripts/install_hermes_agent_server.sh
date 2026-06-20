#!/usr/bin/env bash
set -euo pipefail

HERMES_INSTALL_URL="https://hermes-agent.nousresearch.com/install.sh"
HEX_CORTEX_ROOT="${1:-$(pwd)}"

if [[ ! -f "${HEX_CORTEX_ROOT}/pyproject.toml" ]]; then
  echo "HEX-CORTEX repository not found at: ${HEX_CORTEX_ROOT}" >&2
  exit 2
fi

curl -fsSL "${HERMES_INSTALL_URL}" | bash

export PATH="${HOME}/.local/bin:${PATH}"

if ! command -v hermes >/dev/null 2>&1; then
  echo "Hermes installed but not visible on PATH. Open a new shell and run: hermes doctor" >&2
  exit 3
fi

hermes --version
hermes doctor || true

cat <<EOF
Hermes Agent is installed.

Next steps:
  1. Run: hermes setup
  2. Merge deploy/server/hermes-hex-cortex-mcp.yaml.example into ~/.hermes/config.yaml
  3. Replace /opt/HEX-CORTEX with: ${HEX_CORTEX_ROOT}
  4. Run: hermes tools
  5. Run: hermes
  6. Verify the hex_cortex_* MCP tools are present.
EOF
