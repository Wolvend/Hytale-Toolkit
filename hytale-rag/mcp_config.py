#!/usr/bin/env python3
"""
MCP Configuration Module

Shared functions for configuring MCP (Model Context Protocol) servers
across various AI coding tools. Used by both the CLI setup wizard
and the GUI installer.
"""

import json
import os
import platform
import subprocess
from pathlib import Path

# ============================================================================
#  MCP Client Metadata
# ============================================================================

MCP_CLIENTS = {
    "claude_code": {
        "name": "Claude Code",
        "description": "Anthropic's CLI tool for Claude",
        "config_type": "json",
    },
    "vscode": {
        "name": "VS Code / GitHub Copilot",
        "description": "Works with Copilot in Agent mode (VS Code 1.102+)",
        "config_type": "vscode",
    },
    "cursor": {
        "name": "Cursor",
        "description": "AI-first code editor",
        "config_type": "cursor",
    },
    "windsurf": {
        "name": "Windsurf",
        "description": "Codeium's AI code editor",
        "config_type": "json",
    },
    "codex": {
        "name": "Codex CLI",
        "description": "OpenAI's command-line coding tool",
        "config_type": "toml",
    },
    "jetbrains": {
        "name": "JetBrains IDEs (IntelliJ, Rider, etc.)",
        "description": "GitHub Copilot in JetBrains IDEs",
        "config_type": "json",
    },
    "gemini_cli": {
        "name": "Gemini CLI",
        "description": "Google's command-line AI coding tool",
        "config_type": "json",
    },
}


# ============================================================================
#  MCP Command Generation
# ============================================================================

def get_mcp_command_stdio(script_dir: Path) -> dict:
    """Generate the MCP server command for stdio-based clients."""
    system = platform.system()

    if system == "Windows":
        cmd = (
            f"Set-Location '{script_dir}'; "
            "Get-Content .env | ForEach-Object { "
            "if ($_ -match '^([^=]+)=(.*)$') { "
            "[Environment]::SetEnvironmentVariable($matches[1], $matches[2]) "
            "} }; "
            "npx tsx src/index.ts"
        )
        return {
            "type": "stdio",
            "command": "powershell",
            "args": ["-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", cmd],
            "env": {"HYTALE_RAG_MODE": "mcp"}
        }
    else:
        cmd = f"cd '{script_dir}' && set -a && source .env && set +a && npx tsx src/index.ts"
        return {
            "type": "stdio",
            "command": "bash",
            "args": ["-c", cmd],
            "env": {"HYTALE_RAG_MODE": "mcp"}
        }


def get_mcp_command_simple(script_dir: Path) -> dict:
    """Generate a simpler MCP command for VS Code/Cursor (they handle env differently)."""
    system = platform.system()

    if system == "Windows":
        return {
            "type": "stdio",
            "command": "powershell",
            "args": [
                "-NoProfile",
                "-ExecutionPolicy", "Bypass",
                "-File", str(script_dir / "start-mcp.ps1")
            ]
        }
    else:
        return {
            "type": "stdio",
            "command": "bash",
            "args": [str(script_dir / "start-mcp.sh")]
        }


# ============================================================================
#  PowerShell Helpers (Windows)
# ============================================================================

def check_powershell_execution_policy() -> tuple[bool, str]:
    """
    Check if PowerShell scripts can be executed.
    Returns (can_execute, policy_name).
    """
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", "Get-ExecutionPolicy"],
            capture_output=True,
            text=True,
            timeout=10
        )
        policy = result.stdout.strip().lower()

        # These policies allow script execution
        allowed_policies = ["unrestricted", "remotesigned", "bypass", "allsigned"]
        can_execute = policy in allowed_policies

        return can_execute, result.stdout.strip()
    except Exception:
        return False, "Unknown"


def verify_powershell_bypass() -> bool:
    """
    Test if -ExecutionPolicy Bypass actually works (some enterprise policies block it).
    Returns True if bypass works.
    """
    try:
        # Create a temp script and try to run it with bypass
        test_script = Path.home() / ".hytale-ps-test.ps1"
        test_script.write_text("Write-Output 'OK'")

        result = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(test_script)],
            capture_output=True,
            text=True,
            timeout=10
        )

        test_script.unlink(missing_ok=True)
        return "OK" in result.stdout
    except Exception:
        return False


# ============================================================================
#  Start Script Creation
# ============================================================================

def create_start_scripts(script_dir: Path, quiet: bool = False):
    """
    Create helper scripts for starting the MCP server.

    Args:
        script_dir: Directory where scripts will be created
        quiet: If True, suppress print output (for GUI usage)
    """
    system = platform.system()

    if system == "Windows":
        # Check PowerShell execution policy
        can_execute, policy = check_powershell_execution_policy()

        if not can_execute and not quiet:
            print()
            print(f"    NOTE: Your PowerShell execution policy is '{policy}'.")
            print("    The MCP config uses '-ExecutionPolicy Bypass' which should work,")
            print("    but if you encounter issues, you may need to run:")
            print()
            print("      Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser")
            print()

            # Test if bypass actually works
            if not verify_powershell_bypass():
                print("    WARNING: ExecutionPolicy Bypass appears to be blocked.")
                print("    This may be an enterprise policy restriction.")
                print("    Contact your IT administrator if scripts fail to run.")
                print()

        ps1_path = script_dir / "start-mcp.ps1"
        ps1_content = f"""# Hytale RAG MCP Server Startup Script
Set-Location '{script_dir}'
Get-Content .env | ForEach-Object {{
    if ($_ -match '^([^=]+)=(.*)$') {{
        [Environment]::SetEnvironmentVariable($matches[1], $matches[2])
    }}
}}
$env:HYTALE_RAG_MODE = "mcp"
npx tsx src/index.ts
"""
        ps1_path.write_text(ps1_content)
        if not quiet:
            print(f"    Created {ps1_path}")
    else:
        sh_path = script_dir / "start-mcp.sh"
        sh_content = f"""#!/bin/bash
# Hytale RAG MCP Server Startup Script
cd '{script_dir}'
set -a
source .env
set +a
export HYTALE_RAG_MODE=mcp
npx tsx src/index.ts
"""
        sh_path.write_text(sh_content)
        sh_path.chmod(0o755)
        if not quiet:
            print(f"    Created {sh_path}")


# ============================================================================
#  Config Path Helpers
# ============================================================================

def get_vscode_user_settings_path() -> Path:
    """Get the path to VS Code's user settings.json."""
    system = platform.system()
    if system == "Windows":
        return Path(os.environ.get("APPDATA", "")) / "Code" / "User" / "settings.json"
    elif system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "Code" / "User" / "settings.json"
    else:
        return Path.home() / ".config" / "Code" / "User" / "settings.json"


def get_cursor_user_settings_path() -> Path:
    """Get the path to Cursor's user settings.json."""
    system = platform.system()
    if system == "Windows":
        return Path(os.environ.get("APPDATA", "")) / "Cursor" / "User" / "settings.json"
    elif system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "Cursor" / "User" / "settings.json"
    else:
        return Path.home() / ".config" / "Cursor" / "User" / "settings.json"


def get_client_config_path(client_id: str) -> Path | None:
    """Get the config file path for a given MCP client."""
    home = Path.home()

    paths = {
        "claude_code": home / ".claude.json",
        "windsurf": home / ".codeium" / "windsurf" / "mcp_config.json",
        "codex": home / ".codex" / "config.toml",
        "cursor": get_cursor_user_settings_path(),
        "vscode": get_vscode_user_settings_path(),
        "jetbrains": home / ".config" / "github-copilot" / "intellij" / "mcp.json",
    }
    return paths.get(client_id)


# ============================================================================
#  Setup Functions
# ============================================================================

def setup_claude_code(script_dir: Path, quiet: bool = False) -> bool:
    """Configure Claude Code MCP server."""
    config_path = Path.home() / ".claude.json"
    mcp_config = get_mcp_command_stdio(script_dir)

    if config_path.exists():
        try:
            config = json.loads(config_path.read_text(encoding='utf-8'))
        except json.JSONDecodeError:
            config = {}
    else:
        config = {}

    if "mcpServers" not in config:
        config["mcpServers"] = {}

    config["mcpServers"]["hytale-rag"] = mcp_config
    config_path.write_text(json.dumps(config, indent=2), encoding='utf-8')

    if not quiet:
        print(f"    Added 'hytale-rag' to {config_path}")
    return True


def setup_vscode(script_dir: Path, scope: str = "global", quiet: bool = False) -> bool:
    """
    Configure VS Code / GitHub Copilot MCP server.

    Args:
        script_dir: Path to the hytale-rag directory
        scope: "global" for user settings, "workspace" for .vscode/mcp.json
        quiet: If True, suppress print output
    """
    mcp_config = get_mcp_command_simple(script_dir)
    # VS Code's mcp.json format doesn't use "type" field - remove it
    mcp_config.pop("type", None)

    if scope == "global":
        # Global installation - add to user settings.json
        config_path = get_vscode_user_settings_path()
        config_path.parent.mkdir(parents=True, exist_ok=True)

        if config_path.exists():
            try:
                config = json.loads(config_path.read_text(encoding='utf-8'))
            except json.JSONDecodeError:
                config = {}
        else:
            config = {}

        # VS Code uses nested "mcp" -> "servers" in user settings
        if "mcp" not in config:
            config["mcp"] = {}
        if "servers" not in config["mcp"]:
            config["mcp"]["servers"] = {}

        config["mcp"]["servers"]["hytale-rag"] = mcp_config
        config_path.write_text(json.dumps(config, indent=2), encoding='utf-8')

        if not quiet:
            print(f"    Added 'hytale-rag' to {config_path}")
    else:
        # Workspace installation - create .vscode/mcp.json
        # Note: This requires knowing the repo root, which should be passed in
        # For now, use script_dir.parent as an approximation
        repo_root = script_dir.parent
        vscode_dir = repo_root / ".vscode"
        vscode_dir.mkdir(exist_ok=True)
        config_path = vscode_dir / "mcp.json"

        if config_path.exists():
            try:
                config = json.loads(config_path.read_text(encoding='utf-8'))
            except json.JSONDecodeError:
                config = {}
        else:
            config = {}

        if "servers" not in config:
            config["servers"] = {}

        config["servers"]["hytale-rag"] = mcp_config
        config_path.write_text(json.dumps(config, indent=2), encoding='utf-8')

        if not quiet:
            print(f"    Added 'hytale-rag' to {config_path}")

    return True


def setup_cursor(script_dir: Path, scope: str = "global", quiet: bool = False) -> bool:
    """
    Configure Cursor MCP server.

    Args:
        script_dir: Path to the hytale-rag directory
        scope: "global" for user settings, "workspace" for .cursor/mcp.json
        quiet: If True, suppress print output
    """
    mcp_config = get_mcp_command_simple(script_dir)

    if scope == "global":
        # Global installation - add to user settings.json
        config_path = get_cursor_user_settings_path()
        config_path.parent.mkdir(parents=True, exist_ok=True)

        if config_path.exists():
            try:
                config = json.loads(config_path.read_text(encoding='utf-8'))
            except json.JSONDecodeError:
                config = {}
        else:
            config = {}

        # Cursor uses "mcpServers" in user settings
        if "mcpServers" not in config:
            config["mcpServers"] = {}

        config["mcpServers"]["hytale-rag"] = mcp_config
        config_path.write_text(json.dumps(config, indent=2), encoding='utf-8')

        if not quiet:
            print(f"    Added 'hytale-rag' to {config_path}")
    else:
        # Workspace installation - create .cursor/mcp.json
        repo_root = script_dir.parent
        cursor_dir = repo_root / ".cursor"
        cursor_dir.mkdir(exist_ok=True)
        config_path = cursor_dir / "mcp.json"

        if config_path.exists():
            try:
                config = json.loads(config_path.read_text(encoding='utf-8'))
            except json.JSONDecodeError:
                config = {}
        else:
            config = {}

        if "mcpServers" not in config:
            config["mcpServers"] = {}

        config["mcpServers"]["hytale-rag"] = mcp_config
        config_path.write_text(json.dumps(config, indent=2), encoding='utf-8')

        if not quiet:
            print(f"    Added 'hytale-rag' to {config_path}")

    return True


def setup_windsurf(script_dir: Path, quiet: bool = False) -> bool:
    """Configure Windsurf MCP server."""
    config_dir = Path.home() / ".codeium" / "windsurf"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "mcp_config.json"

    mcp_config = get_mcp_command_simple(script_dir)

    if config_path.exists():
        try:
            config = json.loads(config_path.read_text(encoding='utf-8'))
        except json.JSONDecodeError:
            config = {}
    else:
        config = {}

    if "mcpServers" not in config:
        config["mcpServers"] = {}

    config["mcpServers"]["hytale-rag"] = mcp_config
    config_path.write_text(json.dumps(config, indent=2), encoding='utf-8')

    if not quiet:
        print(f"    Added 'hytale-rag' to {config_path}")
    return True


def setup_codex(script_dir: Path, quiet: bool = False) -> bool:
    """Configure Codex CLI MCP server."""
    config_dir = Path.home() / ".codex"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.toml"

    system = platform.system()

    # Read existing config or create new
    existing_content = ""
    if config_path.exists():
        existing_content = config_path.read_text(encoding='utf-8')

    # Check if hytale-rag already configured
    if "[mcp_servers.hytale-rag]" in existing_content:
        if not quiet:
            print(f"    'hytale-rag' already configured in {config_path}")
        return True

    # Generate the TOML config
    if system == "Windows":
        start_script = str(script_dir / "start-mcp.ps1").replace("\\", "\\\\")
        toml_entry = f'''
[mcp_servers.hytale-rag]
command = "powershell"
args = ["-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "{start_script}"]
'''
    else:
        start_script = str(script_dir / "start-mcp.sh")
        toml_entry = f'''
[mcp_servers.hytale-rag]
command = "bash"
args = ["{start_script}"]
'''

    # Append to config
    with open(config_path, "a", encoding='utf-8') as f:
        f.write(toml_entry)

    if not quiet:
        print(f"    Added 'hytale-rag' to {config_path}")
    return True


def setup_jetbrains(script_dir: Path, quiet: bool = False) -> bool:
    """Configure GitHub Copilot MCP server for JetBrains IDEs (IntelliJ, Rider, etc.)."""
    # GitHub Copilot in JetBrains uses ~/.config/github-copilot/intellij/mcp.json
    config_dir = Path.home() / ".config" / "github-copilot" / "intellij"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "mcp.json"

    mcp_config = get_mcp_command_simple(script_dir)
    # Remove "type" field - not needed for this format
    mcp_config.pop("type", None)

    if config_path.exists():
        try:
            config = json.loads(config_path.read_text(encoding='utf-8'))
        except json.JSONDecodeError:
            config = {}
    else:
        config = {}

    if "servers" not in config:
        config["servers"] = {}

    config["servers"]["hytale-rag"] = mcp_config
    config_path.write_text(json.dumps(config, indent=2), encoding='utf-8')

    if not quiet:
        print(f"    Added 'hytale-rag' to {config_path}")
    return True
