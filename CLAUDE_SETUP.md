# Claude Desktop Configuration for HEX-CORTEX

HEX-CORTEX can now automatically detect Claude Desktop installations, even when the `claude` executable is not in your PATH.

## How It Works

The `claude_detector` module searches for Claude in this order:

1. **Environment Variable**: `CLAUDE_BIN` environment variable
2. **Configuration File**: `~/.hex-cortex/claude-config.json`
3. **Windows Registry**: Anthropic Claude registry entries (Windows only)
4. **Standard Paths**: Common installation directories for your OS
5. **System PATH**: Falls back to PATH search as a last resort

## Setup Options

### Option 1: Automatic Configuration (Recommended)

Run the configuration script:

```bash
cd C:\Users\2spi\HEX-CORTEX
python configure_claude.py
```

This wizard will guide you through finding and configuring your Claude installation.

### Option 2: Manual Configuration File

Edit `~/.hex-cortex/claude-config.json` manually:

```json
{
  "claude_bin": "C:\\path\\to\\claude.exe",
  "platform": "Windows"
}
```

**On Windows**, common paths include:
- `C:\Program Files\Claude Desktop\claude.exe`
- `C:\Program Files (x86)\Claude Desktop\claude.exe`
- `C:\Users\<YourUsername>\AppData\Local\Programs\Claude\claude.exe`

**On macOS**:
- `/usr/local/bin/claude`
- `/opt/homebrew/bin/claude`
- `~/Library/Application Support/Claude/claude`

**On Linux**:
- `~/.local/bin/claude`
- `/opt/claude/claude`
- `/usr/local/bin/claude`

### Option 3: Environment Variable

Set the `CLAUDE_BIN` environment variable:

**Windows (PowerShell)**:
```powershell
$env:CLAUDE_BIN = "C:\Program Files\Claude Desktop\claude.exe"
```

**Windows (Command Prompt)**:
```cmd
set CLAUDE_BIN=C:\Program Files\Claude Desktop\claude.exe
```

**macOS/Linux**:
```bash
export CLAUDE_BIN=/usr/local/bin/claude
```

## Verifying Configuration

After configuration, test that HEX-CORTEX can find Claude:

```python
from src.hex_cortex.memory.claude_detector import is_claude_available, find_claude_executable

if is_claude_available():
    print(f"Claude found at: {find_claude_executable()}")
else:
    print("Claude not found")
```

## Troubleshooting

### "Claude not found" error

1. **Install Claude Desktop**: If not already installed, download from https://claude.ai/download
2. **Find your installation**: Run `where claude` in PowerShell (Windows) or `which claude` in Terminal (macOS/Linux)
3. **Configure**: Use one of the setup options above with the correct path
4. **Verify**: Restart your terminal/IDE and run the detector again

### Configuration not being read

- Ensure file is saved at: `~/.hex-cortex/claude-config.json`
- Verify JSON syntax is valid
- Check that the path in the config actually exists

### Permission issues

If you get permission errors when running `claude`:
- On Windows: Run PowerShell/terminal as Administrator
- On macOS/Linux: Check that the file has execute permissions: `chmod +x /path/to/claude`

## Integration with HEX-CORTEX

Once configured, HEX-CORTEX will automatically use Claude through:

- `cortex_runtime_probe.py`: Detects if Claude is available during initialization
- `cortex_surfaces.py`: Uses detection to set `claude_project_configured` status

The system will report `"claude_project_configured": true` when:
- `.mcp.json` file exists in the project root, AND
- Claude executable is found and available

## Files Modified

- **`src/hex_cortex/memory/claude_detector.py`**: New module for Claude detection
- **`src/hex_cortex/memory/cortex_runtime_probe.py`**: Updated to use `is_claude_available()`
- **`configure_claude.py`**: New interactive configuration script
- **`~/.hex-cortex/claude-config.json`**: New configuration file (created on first setup)

## API Reference

### `find_claude_executable() -> Path | None`
Returns the Path to the claude executable if found, None otherwise.

### `is_claude_available() -> bool`
Quick boolean check if claude is available.

### `get_claude_version() -> str | None`
Returns the version string of claude if available.

### `create_claude_config(claude_bin_path: str | Path) -> bool`
Programmatically create the configuration file.

### `get_claude_path_hint() -> str | None`
Get a user-friendly hint about where to find Claude.
