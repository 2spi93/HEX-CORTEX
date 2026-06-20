r"""Detect Claude Desktop and its executable on the system."""

from __future__ import annotations

import json
import os
import platform
import subprocess
from pathlib import Path

# Try to import winreg (Windows only)
try:
    import winreg
except ImportError:
    winreg = None  # type: ignore


def find_claude_executable() -> Path | None:
    r"""
    Locate the claude executable on the system.
    
    Checks in order:
    1. CLAUDE_BIN environment variable
    2. .hex-cortex/claude-config.json
    3. Windows Registry (if on Windows)
    4. AppData\Roaming\Claude\claude-code (Windows - for Claude Desktop)
    5. Common installation paths
    6. System PATH
    
    Returns the Path if found, None otherwise.
    """
    system = platform.system()
    
    # 1. Check environment variable
    env_path_str = os.environ.get("CLAUDE_BIN", "")
    if env_path_str:
        env_path = Path(env_path_str)
        if env_path.exists() and env_path.is_file():
            return env_path
    
    # 2. Check config file
    config_path = _find_claude_config()
    if config_path:
        return config_path
    
    # 3. Platform-specific search
    if system == "Windows":
        return _find_claude_windows()
    elif system == "Darwin":
        return _find_claude_macos()
    elif system == "Linux":
        return _find_claude_linux()
    
    return None


def _find_claude_config() -> Path | None:
    """Try to load claude path from .hex-cortex/claude-config.json."""
    config_paths = [
        Path.home() / ".hex-cortex" / "claude-config.json",
        Path.cwd() / ".hex-cortex" / "claude-config.json",
    ]
    
    for config_file in config_paths:
        if config_file.exists():
            try:
                with open(config_file) as f:
                    config = json.load(f)
                    claude_bin = config.get("claude_bin") or config.get("claude_path")
                    if claude_bin:
                        path = Path(claude_bin)
                        if path.exists() and path.is_file():
                            return path
            except (OSError, json.JSONDecodeError, KeyError):
                pass
    
    return None


def _find_claude_windows() -> Path | None:
    """Find claude.exe on Windows."""
    # Check AppData\Roaming\Claude\claude-code (Claude Desktop location)
    roaming_claude = Path.home() / "AppData" / "Roaming" / "Claude" / "claude-code"
    if roaming_claude.exists():
        # Find latest version subdirectory
        version_dirs = sorted(
            [d for d in roaming_claude.iterdir() if d.is_dir()],
            key=lambda x: x.name,
            reverse=True
        )
        for version_dir in version_dirs:
            claude_exe = version_dir / "claude.exe"
            if claude_exe.exists():
                return claude_exe
    
    candidate_paths = [
        Path.home() / "AppData" / "Local" / "Programs" / "Claude" / "claude.exe",
        Path.home() / "AppData" / "Local" / "Claude" / "claude.exe",
        Path.home() / "AppData" / "Local" / "Claude Desktop" / "claude.exe",
        Path.home() / "AppData" / "Local" / "Anthropic" / "Claude" / "claude.exe",
        Path("C:\\Program Files\\Claude\\claude.exe"),
        Path("C:\\Program Files\\Claude Desktop\\claude.exe"),
        Path("C:\\Program Files (x86)\\Claude\\claude.exe"),
        Path("C:\\Program Files (x86)\\Claude Desktop\\claude.exe"),
        # Scoop installation
        Path.home() / "scoop" / "apps" / "claude" / "current" / "claude.exe",
        # Common custom paths
        Path.home() / "Applications" / "Claude" / "claude.exe",
        Path.home() / "bin" / "claude.exe",
    ]
    
    # Try standard paths first
    for path in candidate_paths:
        if path.exists() and path.is_file():
            return path
    
    # Try Windows Registry for Claude Desktop
    if winreg is not None:
        try:
            registry_path = _find_claude_from_registry()
            if registry_path:
                return registry_path
        except Exception:
            pass
    
    # Try searching in PATH
    try:
        result = subprocess.run(
            ["where", "claude"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return Path(result.stdout.strip().split('\n')[0])
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    
    return None


def _find_claude_from_registry() -> Path | None:
    """Try to find Claude from Windows Registry."""
    if winreg is None:
        return None
    
    registry_paths = [
        (winreg.HKEY_CURRENT_USER, r"Software\Anthropic\Claude"),
        (winreg.HKEY_LOCAL_MACHINE, r"Software\Anthropic\Claude"),
        (winreg.HKEY_CURRENT_USER, r"Software\Anthropic"),
        (winreg.HKEY_LOCAL_MACHINE, r"Software\Anthropic"),
    ]
    
    for hive, path in registry_paths:
        try:
            key = winreg.OpenKey(hive, path, access=winreg.KEY_READ)
            try:
                # Try different value names
                for value_name in ["InstallPath", "Path", "BinPath"]:
                    try:
                        install_path, _ = winreg.QueryValueEx(key, value_name)
                        exe_path = Path(install_path) / "claude.exe"
                        if exe_path.exists():
                            return exe_path
                        # Also try as direct path to exe
                        if Path(install_path).name.lower() == "claude.exe":
                            if Path(install_path).exists():
                                return Path(install_path)
                    except OSError:
                        continue
            finally:
                winreg.CloseKey(key)
        except OSError:
            continue
    
    return None


def _find_claude_macos() -> Path | None:
    """Find claude on macOS."""
    candidate_paths = [
        Path("/usr/local/bin/claude"),
        Path("/opt/homebrew/bin/claude"),
        Path.home() / "Library" / "Application Support" / "Claude" / "claude",
        Path.home() / ".local" / "bin" / "claude",
        Path("/Applications/Claude.app/Contents/MacOS/claude"),
    ]
    
    for path in candidate_paths:
        if path.exists() and path.is_file():
            return path
    
    # Try which command
    try:
        result = subprocess.run(
            ["which", "claude"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return Path(result.stdout.strip())
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    
    return None


def _find_claude_linux() -> Path | None:
    """Find claude on Linux."""
    candidate_paths = [
        Path.home() / ".local" / "bin" / "claude",
        Path("/opt/claude/claude"),
        Path("/usr/local/bin/claude"),
        Path("/usr/bin/claude"),
        Path("/snap/bin/claude"),
    ]
    
    for path in candidate_paths:
        if path.exists() and path.is_file():
            return path
    
    # Try which command
    try:
        result = subprocess.run(
            ["which", "claude"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return Path(result.stdout.strip())
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    
    return None


def is_claude_available() -> bool:
    """Check if claude executable is available on the system."""
    return find_claude_executable() is not None


def get_claude_version() -> str | None:
    """Get the version of Claude if available."""
    claude_path = find_claude_executable()
    if not claude_path:
        return None
    
    try:
        result = subprocess.run(
            [str(claude_path), "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    
    return None


def create_claude_config(claude_bin_path: str | Path) -> bool:
    """
    Create a claude-config.json file to store the claude binary path.
    
    Args:
        claude_bin_path: Path to the claude executable
    
    Returns:
        True if config was created successfully, False otherwise
    """
    config_dir = Path.home() / ".hex-cortex"
    config_file = config_dir / "claude-config.json"
    
    try:
        config_dir.mkdir(parents=True, exist_ok=True)
        
        config = {
            "claude_bin": str(Path(claude_bin_path).resolve()),
            "detected_at": __import__("datetime").datetime.now().isoformat(),
            "platform": platform.system(),
        }
        
        with open(config_file, "w") as f:
            json.dump(config, f, indent=2)
        
        return True
    except OSError:
        return False


def get_claude_path_hint() -> str | None:
    """Get a hint about where Claude should be if not found."""
    claude_path = find_claude_executable()
    if claude_path:
        return str(claude_path)
    
    system = platform.system()
    
    if system == "Windows":
        hint = (
            "Claude Desktop not found in standard locations.\n"
            "Options to fix this:\n"
            "1. Install Claude Desktop from https://claude.ai/download\n"
            "2. Set CLAUDE_BIN environment variable to your claude.exe path\n"
            "3. Create ~/.hex-cortex/claude-config.json with:\n"
            '   {"claude_bin": "C:\\\\path\\\\to\\\\claude.exe"}'
        )
    elif system == "Darwin":
        hint = (
            "Claude not found in standard locations.\n"
            "Options to fix this:\n"
            "1. Install Claude Desktop from https://claude.ai/download\n"
            "2. Set CLAUDE_BIN environment variable to your claude path\n"
            "3. Create ~/.hex-cortex/claude-config.json with:\n"
            '   {"claude_bin": "/path/to/claude"}'
        )
    else:  # Linux
        hint = (
            "Claude not found in standard locations.\n"
            "Options to fix this:\n"
            "1. Install Claude: pip install anthropic-sdk-python\n"
            "2. Set CLAUDE_BIN environment variable to your claude path\n"
            "3. Create ~/.hex-cortex/claude-config.json with:\n"
            '   {"claude_bin": "/path/to/claude"}'
        )
    
    return hint
