#!/usr/bin/env python3
"""
Hytale Modding RAG Setup Script
Sets up the semantic code search MCP server for Claude Code.
Works on Windows, macOS, and Linux.
"""

import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import urllib.request
from pathlib import Path

# GitHub release URL for the LanceDB database
GITHUB_REPO = "logan-mcduffie/Hytale-Toolkit"
LANCEDB_RELEASE_ASSET = "lancedb.tar.gz"


def download_database(dest_dir: Path) -> bool:
    """Download and extract the LanceDB database from GitHub releases."""
    import ssl

    # Create data directory if it doesn't exist
    dest_dir.mkdir(parents=True, exist_ok=True)

    tarball_path = dest_dir / LANCEDB_RELEASE_ASSET

    # Get the latest release download URL
    api_url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
    download_url = None

    print("  Fetching latest release info...")
    try:
        # Create SSL context that doesn't verify (for corporate proxies)
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        req = urllib.request.Request(api_url, headers={"User-Agent": "Hytale-RAG-Setup"})
        with urllib.request.urlopen(req, context=ctx, timeout=30) as response:
            release_info = json.loads(response.read().decode())

        for asset in release_info.get("assets", []):
            if asset["name"] == LANCEDB_RELEASE_ASSET:
                download_url = asset["browser_download_url"]
                break

        if not download_url:
            print(f"  ERROR: Could not find {LANCEDB_RELEASE_ASSET} in latest release.")
            print(f"  Please download manually from: https://github.com/{GITHUB_REPO}/releases")
            return False

    except Exception as e:
        print(f"  ERROR: Failed to fetch release info: {e}")
        print(f"  Please download manually from: https://github.com/{GITHUB_REPO}/releases")
        return False

    # Download the tarball
    print(f"  Downloading {LANCEDB_RELEASE_ASSET}...")
    print(f"  URL: {download_url}")
    try:
        def show_progress(block_num, block_size, total_size):
            downloaded = block_num * block_size
            if total_size > 0:
                percent = min(100, downloaded * 100 / total_size)
                mb_downloaded = downloaded / (1024 * 1024)
                mb_total = total_size / (1024 * 1024)
                print(f"\r  Progress: {percent:.1f}% ({mb_downloaded:.1f}/{mb_total:.1f} MB)", end="", flush=True)

        req = urllib.request.Request(download_url, headers={"User-Agent": "Hytale-RAG-Setup"})
        urllib.request.urlretrieve(download_url, tarball_path, reporthook=show_progress)
        print()  # New line after progress

    except Exception as e:
        print(f"\n  ERROR: Failed to download: {e}")
        print(f"  Please download manually from: https://github.com/{GITHUB_REPO}/releases")
        return False

    # Extract the tarball
    print("  Extracting database...")
    try:
        with tarfile.open(tarball_path, "r:gz") as tar:
            tar.extractall(path=dest_dir)
        print("  Extraction complete!")

        # Clean up the tarball
        tarball_path.unlink()

    except Exception as e:
        print(f"  ERROR: Failed to extract: {e}")
        print("  The downloaded file may be corrupted. Please try again.")
        return False

    return True


def get_claude_config_path() -> Path:
    """Get the path to Claude's config file based on OS."""
    home = Path.home()
    return home / ".claude.json"


def get_shell_command(script_dir: Path) -> dict:
    """Generate the MCP server command based on OS."""
    system = platform.system()

    if system == "Windows":
        # PowerShell command that loads .env and runs the server
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
            "args": ["-NoProfile", "-Command", cmd],
            "env": {"HYTALE_RAG_MODE": "mcp"}
        }
    else:
        # Bash command for macOS/Linux that sources .env and runs the server
        cmd = f"cd '{script_dir}' && set -a && source .env && set +a && npx tsx src/index.ts"
        return {
            "type": "stdio",
            "command": "bash",
            "args": ["-c", cmd],
            "env": {"HYTALE_RAG_MODE": "mcp"}
        }


def run_command(cmd: list[str], cwd: Path = None) -> tuple[int, str]:
    """Run a command and return exit code and output."""
    try:
        if platform.system() == "Windows":
            # On Windows, use shell=True with joined command to find npm/npx in PATH
            result = subprocess.run(
                " ".join(cmd),
                cwd=cwd,
                capture_output=True,
                text=True,
                shell=True
            )
        else:
            # On Unix, run directly without shell
            result = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True
            )
        return result.returncode, result.stdout + result.stderr
    except Exception as e:
        return 1, str(e)


def main():
    print("=== Hytale Modding RAG Setup ===\n")

    # Get script directory
    script_dir = Path(__file__).parent.resolve()
    print(f"Script directory: {script_dir}\n")

    # Verify we're in the right place
    if not (script_dir / "package.json").exists():
        print("ERROR: package.json not found. Run this script from the hytale-rag directory.")
        sys.exit(1)

    # Step 1: Check/Download database
    data_dir = script_dir / "data"
    lancedb_dir = data_dir / "lancedb"

    if not lancedb_dir.exists() or not (lancedb_dir / "hytale_methods.lance").exists():
        print("Step 1: Downloading LanceDB database...")
        print("  Database not found. Downloading from GitHub Releases...")

        # Clean up any partial download
        if lancedb_dir.exists():
            print("  Removing incomplete database...")
            shutil.rmtree(lancedb_dir, ignore_errors=True)

        if not download_database(data_dir):
            print("\nERROR: Failed to download database. Setup cannot continue.")
            sys.exit(1)

        print("  Database ready!\n")
    else:
        print("Step 1: Database found\n")

    # Step 2: Get API key
    print("Step 2: API Key Setup")
    env_file = script_dir / ".env"

    if env_file.exists():
        print(f"  Found existing .env file at {env_file}")
        response = input("  Do you want to use the existing API key? [Y/n]: ").strip().lower()
        if response in ('n', 'no'):
            api_key = input("  Enter your Voyage API key: ").strip()
            if not api_key:
                print("ERROR: API key is required.")
                sys.exit(1)
            env_file.write_text(f"VOYAGE_API_KEY={api_key}\n")
            print("  API key saved to .env")
        else:
            print("  Using existing API key.")
    else:
        api_key = input("  Enter your Voyage API key (get one free at https://www.voyageai.com/): ").strip()
        if not api_key:
            print("ERROR: API key is required.")
            sys.exit(1)
        env_file.write_text(f"VOYAGE_API_KEY={api_key}\n")
        print(f"  API key saved to {env_file}")

    # Step 3: Install dependencies
    print("\nStep 3: Installing dependencies...")
    exit_code, output = run_command(["npm", "install"], cwd=script_dir)
    if exit_code != 0:
        print(f"ERROR: npm install failed:\n{output}")
        sys.exit(1)
    print("  Dependencies installed.")

    # Step 4: Test database
    print("\nStep 4: Testing database...")

    # Set up environment for test
    env = os.environ.copy()
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and '=' in line and not line.startswith('#'):
                key, value = line.split('=', 1)
                env[key] = value

    exit_code, output = run_command(
        ["npx", "tsx", "src/search.ts", "--stats"],
        cwd=script_dir
    )
    # Note: --stats doesn't need the API key, so we just check if the DB loads
    # Check for database corruption (panics in bytes crate, range errors, etc.)
    is_corrupted = (
        "panic" in output.lower() or
        "range start must not be greater than end" in output or
        ("thread" in output.lower() and "panicked" in output.lower())
    )

    if is_corrupted:
        print("  ERROR: Database appears to be corrupted.")
        print("  This usually happens due to an incomplete or corrupted download.\n")
        response = input("  Would you like to delete and re-download the database? [Y/n]: ").strip().lower()
        if response not in ('n', 'no'):
            print("  Removing corrupted database...")
            shutil.rmtree(lancedb_dir, ignore_errors=True)

            print("  Re-downloading database...")
            if not download_database(data_dir):
                print("\nERROR: Failed to re-download database. Setup cannot continue.")
                sys.exit(1)

            # Test again
            print("  Testing re-downloaded database...")
            exit_code, output = run_command(
                ["npx", "tsx", "src/search.ts", "--stats"],
                cwd=script_dir
            )
            if exit_code != 0 or "error" in output.lower() or "panic" in output.lower():
                print(f"  ERROR: Database still failing after re-download.")
                print(f"  Output: {output}")
                print("\n  Please try the following:")
                print("    1. Delete the 'data/lancedb' directory manually")
                print("    2. Download lancedb.tar.gz from GitHub releases manually")
                print("    3. Extract it to the 'data' directory")
                print("    4. Run setup.py again")
                sys.exit(1)
            else:
                print("  Database loaded successfully after re-download!")
        else:
            print("  Skipping re-download. You may need to fix this manually.")
            print("  Try deleting the 'data/lancedb' directory and running setup again.")
    elif exit_code != 0 or "error" in output.lower():
        print(f"  Warning: Test may have failed. Output:\n  {output}")
    else:
        print("  Database loaded successfully!")

    # Step 5: Claude Code Integration (Optional)
    print("\nStep 5: Claude Code Integration (Optional)")
    print("  The RAG server can be integrated with Claude Code as an MCP server,")
    print("  or used manually via the command line.\n")

    response = input("  Do you want to configure Claude Code integration? [Y/n]: ").strip().lower()
    configure_claude = response not in ('n', 'no')

    if configure_claude:
        print("\n  Configuring Claude Code MCP server...")

        claude_config_path = get_claude_config_path()
        mcp_config = get_shell_command(script_dir)

        # Read existing config or create new
        if claude_config_path.exists():
            try:
                config = json.loads(claude_config_path.read_text())
            except json.JSONDecodeError:
                print(f"  Warning: Could not parse existing {claude_config_path}, creating new config")
                config = {}
        else:
            config = {}

        # Ensure mcpServers exists
        if "mcpServers" not in config:
            config["mcpServers"] = {}

        # Add or update hytale-rag server
        config["mcpServers"]["hytale-rag"] = mcp_config

        # Write config
        claude_config_path.write_text(json.dumps(config, indent=2))
        print(f"  Added 'hytale-rag' MCP server to {claude_config_path}")

        # Done - Claude integration
        print("\n=== Setup Complete ===\n")
        print("The 'hytale-rag' MCP server has been configured for Claude Code.\n")
        print("To use it:")
        print("  1. Restart Claude Code (or any running Claude Code instances)")
        print("  2. Ask Claude to search the Hytale codebase, e.g.:")
        print("     'Search the Hytale code for player movement handling'")
        print("     'Find methods related to inventory management'")
    else:
        # Done - Manual usage only
        print("\n=== Setup Complete ===\n")
        print("The RAG server is ready for manual use.\n")
        print("To search the codebase, run:")
        print(f"  cd {script_dir}")
        print("  npx tsx src/search.ts \"your search query\"\n")
        print("Examples:")
        print("  npx tsx src/search.ts \"player movement handling\"")
        print("  npx tsx src/search.ts \"inventory management\" --limit 10")
        print("  npx tsx src/search.ts \"how to craft iron sword\" --type recipe")
        print("  npx tsx src/search.ts --stats")
        print("\nYou can run this setup script again to configure Claude Code integration later.")

    print("\nAvailable tools:")
    print("  Server Code Search:")
    print("    - search_hytale_code: Semantic search over 37,000+ server methods")
    print("    - hytale_code_stats: Show server code database statistics")
    print("  Client UI Search:")
    print("    - search_hytale_client_code: Search 353 UI files (XAML, .ui, JSON)")
    print("    - hytale_client_code_stats: Show client UI statistics")
    print("  Game Data Search:")
    print("    - search_hytale_gamedata: Search 8,400+ items, recipes, NPCs, drops, etc.")
    print("    - hytale_gamedata_stats: Show game data statistics")


if __name__ == "__main__":
    main()
