"""
Script to help locate and configure Claude Desktop for hex-cortex.

Run this script if hex-cortex can't find your Claude installation:
    python configure_claude.py
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from hex_cortex.memory.claude_detector import (
    find_claude_executable,
    is_claude_available,
    create_claude_config,
)


def main():
    """Main setup wizard for Claude configuration."""
    print("\n" + "=" * 70)
    print("Claude Desktop Configuration for HEX-CORTEX")
    print("=" * 70 + "\n")
    
    # Check if Claude is already available
    if is_claude_available():
        claude_path = find_claude_executable()
        print(f"✓ Claude Desktop found at: {claude_path}\n")
        print("No configuration needed!")
        return 0
    
    print("✗ Claude Desktop not found in standard locations.\n")
    print("To use HEX-CORTEX with Claude Code, you need to either:")
    print("  1. Install Claude Desktop from https://claude.ai/download")
    print("  2. Configure the path to your Claude executable\n")
    
    # Ask user for path
    while True:
        user_path = input("Enter the full path to your claude.exe (or 'quit' to exit): ").strip()
        
        if user_path.lower() == "quit":
            print("Configuration cancelled.")
            return 1
        
        if not user_path:
            print("Path cannot be empty. Please try again.\n")
            continue
        
        path_obj = Path(user_path)
        
        if not path_obj.exists():
            print(f"✗ Path does not exist: {user_path}")
            print("  Please verify the path and try again.\n")
            continue
        
        if not path_obj.is_file():
            print(f"✗ Path is not a file: {user_path}")
            print("  Please provide the full path to the executable.\n")
            continue
        
        if path_obj.name.lower() not in ("claude.exe", "claude"):
            response = input(
                f"\n⚠ The file doesn't appear to be named 'claude' ({path_obj.name}).\n"
                "Are you sure this is the correct executable? (yes/no): "
            ).strip().lower()
            if response not in ("yes", "y"):
                print("Please provide the correct path.\n")
                continue
        
        # Verify it's executable by trying to run --version
        import subprocess
        try:
            result = subprocess.run(
                [str(path_obj), "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                print(f"\n✓ Version check passed: {result.stdout.strip()}\n")
            else:
                print(f"\n⚠ Warning: Version check returned: {result.stderr}")
                response = input("Continue anyway? (yes/no): ").strip().lower()
                if response not in ("yes", "y"):
                    continue
        except subprocess.TimeoutExpired:
            print("\n⚠ Warning: Version check timed out")
            response = input("Continue anyway? (yes/no): ").strip().lower()
            if response not in ("yes", "y"):
                continue
        except Exception as e:
            print(f"\n⚠ Warning: Could not verify executable: {e}")
            response = input("Continue anyway? (yes/no): ").strip().lower()
            if response not in ("yes", "y"):
                continue
        
        # Save configuration
        print("Saving configuration...")
        if create_claude_config(path_obj):
            print("\n✓ Configuration saved to ~/.hex-cortex/claude-config.json")
            print(f"✓ Claude path: {path_obj}\n")
            
            # Verify it can now be found
            if is_claude_available():
                print("✓ Claude is now available to HEX-CORTEX!")
                return 0
        else:
            print("\n✗ Failed to save configuration.")
            return 1
        
        break
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
