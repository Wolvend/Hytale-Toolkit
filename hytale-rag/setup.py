#!/usr/bin/env python3
"""
Hytale Modding RAG Setup Script
Sets up the semantic code search server with support for multiple embedding providers.
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

# Data types available
DATA_TYPES = {
    "all": "All data (server code, client UI, game data)",
    "server": "Server code only (37,000+ Java methods)",
    "client": "Client UI only (353 XAML/UI files)",
    "gamedata": "Game data only (23,000+ items, recipes, NPCs, etc.)",
}

# Table names for each data type
DATA_TYPE_TABLES = {
    "all": ["hytale_methods.lance", "hytale_client_ui.lance", "hytale_gamedata.lance"],
    "server": ["hytale_methods.lance"],
    "client": ["hytale_client_ui.lance"],
    "gamedata": ["hytale_gamedata.lance"],
}

# Ollama embedding model
OLLAMA_MODEL = "nomic-embed-text"


def is_admin() -> bool:
    """Check if running with admin/root privileges."""
    if platform.system() == "Windows":
        try:
            import ctypes
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except:
            return False
    else:
        return os.geteuid() == 0


def run_command(cmd: list[str], cwd: Path = None, env: dict = None, shell: bool = None) -> tuple[int, str]:
    """Run a command and return exit code and output."""
    try:
        use_shell = shell if shell is not None else (platform.system() == "Windows")
        if use_shell and isinstance(cmd, list):
            cmd = " ".join(cmd)

        merged_env = os.environ.copy()
        if env:
            merged_env.update(env)

        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            shell=use_shell,
            env=merged_env
        )
        return result.returncode, result.stdout + result.stderr
    except Exception as e:
        return 1, str(e)


def command_exists(cmd: str) -> bool:
    """Check if a command exists in PATH."""
    if platform.system() == "Windows":
        exit_code, _ = run_command(["where", cmd])
    else:
        exit_code, _ = run_command(["which", cmd], shell=False)
    return exit_code == 0


def get_release_asset_name(provider: str, data_type: str) -> str:
    """Get the release asset name for a provider and data type."""
    return f"lancedb-{provider}-{data_type}.tar.gz"


def download_database(dest_dir: Path, provider: str, data_type: str) -> bool:
    """Download and extract the LanceDB database from GitHub releases."""
    import ssl

    dest_dir.mkdir(parents=True, exist_ok=True)
    asset_name = get_release_asset_name(provider, data_type)
    tarball_path = dest_dir / asset_name

    api_url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
    download_url = None

    print("  Fetching latest release info...")
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        req = urllib.request.Request(api_url, headers={"User-Agent": "Hytale-RAG-Setup"})
        with urllib.request.urlopen(req, context=ctx, timeout=30) as response:
            release_info = json.loads(response.read().decode())

        for asset in release_info.get("assets", []):
            if asset["name"] == asset_name:
                download_url = asset["browser_download_url"]
                break

        if not download_url:
            print(f"  ERROR: Could not find {asset_name} in latest release.")
            print(f"  Available assets:")
            for asset in release_info.get("assets", []):
                print(f"    - {asset['name']}")
            print(f"\n  Please download manually from: https://github.com/{GITHUB_REPO}/releases")
            return False

    except Exception as e:
        print(f"  ERROR: Failed to fetch release info: {e}")
        print(f"  Please download manually from: https://github.com/{GITHUB_REPO}/releases")
        return False

    print(f"  Downloading {asset_name}...")
    try:
        def show_progress(block_num, block_size, total_size):
            downloaded = block_num * block_size
            if total_size > 0:
                percent = min(100, downloaded * 100 / total_size)
                mb_downloaded = downloaded / (1024 * 1024)
                mb_total = total_size / (1024 * 1024)
                print(f"\r  Progress: {percent:.1f}% ({mb_downloaded:.1f}/{mb_total:.1f} MB)", end="", flush=True)

        urllib.request.urlretrieve(download_url, tarball_path, reporthook=show_progress)
        print()

    except Exception as e:
        print(f"\n  ERROR: Failed to download: {e}")
        return False

    print("  Extracting database...")
    try:
        with tarfile.open(tarball_path, "r:gz") as tar:
            tar.extractall(path=dest_dir)
        print("  Extraction complete!")
        tarball_path.unlink()
    except Exception as e:
        print(f"  ERROR: Failed to extract: {e}")
        return False

    return True


# ==================== Ollama Installation ====================

def check_ollama_installed() -> bool:
    """Check if Ollama is installed."""
    return command_exists("ollama")


def check_ollama_running() -> bool:
    """Check if Ollama server is running."""
    try:
        import urllib.request
        req = urllib.request.Request("http://localhost:11434/api/tags")
        with urllib.request.urlopen(req, timeout=5) as response:
            return response.status == 200
    except:
        return False


def check_ollama_model_available(model: str = OLLAMA_MODEL) -> bool:
    """Check if the required model is available in Ollama."""
    try:
        import urllib.request
        req = urllib.request.Request("http://localhost:11434/api/tags")
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            models = data.get("models", [])
            return any(m["name"] == model or m["name"].startswith(f"{model}:") for m in models)
    except:
        return False


def install_ollama_windows() -> bool:
    """Install Ollama on Windows using winget."""
    print("  Installing Ollama via winget...")
    exit_code, output = run_command(["winget", "install", "-e", "--id", "Ollama.Ollama", "--accept-source-agreements", "--accept-package-agreements"])
    if exit_code != 0:
        print(f"  winget install failed: {output}")
        return False
    print("  Ollama installed successfully!")
    return True


def install_ollama_mac() -> bool:
    """Install Ollama on macOS using Homebrew."""
    # Check for Homebrew
    if not command_exists("brew"):
        print("  Homebrew is not installed.")
        response = input("  Would you like to install Homebrew? [Y/n]: ").strip().lower()
        if response in ('n', 'no'):
            print("  Please install Homebrew manually: https://brew.sh")
            print("  Then run this setup script again.")
            return False

        print("  Installing Homebrew (this may take a few minutes)...")
        exit_code, output = run_command(
            ['/bin/bash', '-c', '$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)'],
            shell=False
        )
        if exit_code != 0:
            print(f"  Homebrew installation failed: {output}")
            print("  Please install Homebrew manually: https://brew.sh")
            return False
        print("  Homebrew installed!")

    print("  Installing Ollama via Homebrew...")
    exit_code, output = run_command(["brew", "install", "ollama"], shell=False)
    if exit_code != 0:
        print(f"  brew install failed: {output}")
        return False
    print("  Ollama installed successfully!")
    return True


def install_ollama_linux() -> bool:
    """Install Ollama on Linux using the official install script."""
    print("  Installing Ollama (requires sudo)...")
    exit_code, output = run_command(
        ["sudo", "bash", "-c", "curl -fsSL https://ollama.com/install.sh | sh"],
        shell=False
    )
    if exit_code != 0:
        print(f"  Installation failed: {output}")
        print("  Please install Ollama manually: https://ollama.com/download")
        return False
    print("  Ollama installed successfully!")
    return True


def install_ollama() -> bool:
    """Install Ollama based on the current OS."""
    system = platform.system()

    if system == "Windows":
        if not is_admin():
            print("\n  ERROR: Administrator privileges required to install Ollama.")
            print("  Please restart this script as Administrator:")
            print("    1. Right-click on Command Prompt or PowerShell")
            print("    2. Select 'Run as administrator'")
            print("    3. Run: python setup.py")
            return False
        return install_ollama_windows()

    elif system == "Darwin":  # macOS
        return install_ollama_mac()

    elif system == "Linux":
        return install_ollama_linux()

    else:
        print(f"  Unsupported OS: {system}")
        print("  Please install Ollama manually: https://ollama.com/download")
        return False


def start_ollama() -> bool:
    """Start Ollama server in the background."""
    system = platform.system()

    if system == "Windows":
        # Start Ollama in a new process
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
        )
    else:
        # Start Ollama in background on Unix
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )

    # Wait for it to start
    import time
    for _ in range(10):
        time.sleep(1)
        if check_ollama_running():
            return True

    return False


def pull_ollama_model(model: str = OLLAMA_MODEL) -> bool:
    """Pull the required embedding model."""
    print(f"  Pulling {model} model (this may take a few minutes)...")
    exit_code, output = run_command(["ollama", "pull", model])
    if exit_code != 0:
        print(f"  Failed to pull model: {output}")
        return False
    print(f"  Model {model} ready!")
    return True


def setup_ollama() -> bool:
    """Full Ollama setup: install, start, pull model."""
    print("\n  Checking Ollama installation...")

    # Check if installed
    if not check_ollama_installed():
        print("  Ollama is not installed.")
        response = input("  Would you like to install Ollama? [Y/n]: ").strip().lower()
        if response in ('n', 'no'):
            print("  Please install Ollama manually: https://ollama.com/download")
            print("  Then run this setup script again.")
            return False

        if not install_ollama():
            return False
    else:
        print("  Ollama is installed.")

    # Check if running
    if not check_ollama_running():
        print("  Ollama server is not running. Starting...")
        if not start_ollama():
            print("  Failed to start Ollama server.")
            print("  Please start it manually with: ollama serve")
            print("  Then run this setup script again.")
            return False
        print("  Ollama server started.")
    else:
        print("  Ollama server is running.")

    # Check if model is available
    if not check_ollama_model_available(OLLAMA_MODEL):
        if not pull_ollama_model(OLLAMA_MODEL):
            return False
    else:
        print(f"  Model {OLLAMA_MODEL} is ready.")

    return True


# ==================== Claude Code Configuration ====================

def get_claude_config_path() -> Path:
    """Get the path to Claude's config file."""
    return Path.home() / ".claude.json"


def get_shell_command(script_dir: Path) -> dict:
    """Generate the MCP server command based on OS."""
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


# ==================== Main Setup ====================

def select_provider() -> str:
    """Prompt user to select embedding provider."""
    print("\nStep 1: Select Embedding Provider")
    print("  Choose how you want to generate embeddings for search queries:\n")
    print("  [1] Voyage AI (Recommended)")
    print("      - Cloud-based, high quality embeddings")
    print("      - Requires free API key from https://www.voyageai.com/")
    print("      - Free tier: 3 requests/minute\n")
    print("  [2] Ollama (Local)")
    print("      - Runs entirely on your machine, no API key needed")
    print("      - Requires ~2GB disk space for the model")
    print("      - No rate limits\n")

    while True:
        choice = input("  Enter choice [1/2]: ").strip()
        if choice == "1":
            return "voyage"
        elif choice == "2":
            return "ollama"
        else:
            print("  Please enter 1 or 2.")


def select_data_type() -> str:
    """Prompt user to select which data to download."""
    print("\nStep 2: Select Data to Download")
    print("  Choose which parts of the Hytale codebase to index:\n")

    options = list(DATA_TYPES.items())
    for i, (key, desc) in enumerate(options, 1):
        print(f"  [{i}] {desc}")
    print()

    while True:
        choice = input("  Enter choice [1-4, default=1 (All)]: ").strip()
        if choice == "" or choice == "1":
            return "all"
        elif choice == "2":
            return "server"
        elif choice == "3":
            return "client"
        elif choice == "4":
            return "gamedata"
        else:
            print("  Please enter 1-4.")


def main():
    print("=" * 50)
    print("       Hytale Modding RAG Setup")
    print("=" * 50)

    script_dir = Path(__file__).parent.resolve()
    print(f"\nScript directory: {script_dir}")

    if not (script_dir / "package.json").exists():
        print("\nERROR: package.json not found. Run this script from the hytale-rag directory.")
        sys.exit(1)

    # Step 1: Select provider
    provider = select_provider()

    # Step 2: Select data type
    data_type = select_data_type()

    # Step 3: Provider-specific setup
    env_file = script_dir / ".env"
    env_content = f"EMBEDDING_PROVIDER={provider}\n"

    if provider == "voyage":
        print("\nStep 3: Voyage AI API Key Setup")

        existing_key = None
        if env_file.exists():
            with open(env_file) as f:
                for line in f:
                    if line.startswith("VOYAGE_API_KEY="):
                        existing_key = line.split("=", 1)[1].strip()
                        break

        if existing_key:
            print(f"  Found existing API key.")
            response = input("  Use existing key? [Y/n]: ").strip().lower()
            if response not in ('n', 'no'):
                env_content += f"VOYAGE_API_KEY={existing_key}\n"
            else:
                existing_key = None

        if not existing_key:
            print("  Get a free API key at: https://www.voyageai.com/")
            api_key = input("  Enter your Voyage API key: ").strip()
            if not api_key:
                print("ERROR: API key is required for Voyage AI.")
                sys.exit(1)
            env_content += f"VOYAGE_API_KEY={api_key}\n"

        env_file.write_text(env_content)
        print("  Configuration saved.")

    elif provider == "ollama":
        print("\nStep 3: Ollama Setup")

        if not setup_ollama():
            print("\nERROR: Ollama setup failed. Please fix the issues and try again.")
            sys.exit(1)

        env_content += f"OLLAMA_MODEL={OLLAMA_MODEL}\n"
        env_file.write_text(env_content)
        print("  Configuration saved.")

    # Step 4: Download database
    print(f"\nStep 4: Downloading Database ({provider}/{data_type})")

    data_dir = script_dir / "data"
    provider_dir = data_dir / provider  # data/voyage or data/ollama
    lancedb_dir = provider_dir / "lancedb"

    expected_tables = DATA_TYPE_TABLES[data_type]
    needs_download = not lancedb_dir.exists() or not all(
        (lancedb_dir / table).exists() for table in expected_tables
    )

    if needs_download:
        # Clean up any existing data for this provider
        if lancedb_dir.exists():
            print("  Removing existing database...")
            shutil.rmtree(lancedb_dir, ignore_errors=True)

        # Download and extract to provider-specific directory
        if not download_database(provider_dir, provider, data_type):
            print("\nERROR: Failed to download database.")
            sys.exit(1)
        print("  Database ready!")
    else:
        print("  Database already exists.")
        response = input("  Re-download? [y/N]: ").strip().lower()
        if response in ('y', 'yes'):
            shutil.rmtree(lancedb_dir, ignore_errors=True)
            if not download_database(provider_dir, provider, data_type):
                print("\nERROR: Failed to download database.")
                sys.exit(1)

    # Step 5: Install npm dependencies
    print("\nStep 5: Installing dependencies...")
    exit_code, output = run_command(["npm", "install"], cwd=script_dir)
    if exit_code != 0:
        print(f"ERROR: npm install failed:\n{output}")
        sys.exit(1)
    print("  Dependencies installed.")

    # Step 6: Test database
    print("\nStep 6: Testing database...")

    exit_code, output = run_command(
        ["npx", "tsx", "src/search.ts", "--stats"],
        cwd=script_dir
    )

    is_corrupted = (
        "panic" in output.lower() or
        "range start must not be greater than end" in output
    )

    if is_corrupted:
        print("  ERROR: Database appears corrupted.")
        print(f"  Please delete the data/{provider}/lancedb folder and run setup again.")
        sys.exit(1)
    elif exit_code != 0 or "error" in output.lower():
        print(f"  Warning: Test may have issues. Output:\n  {output}")
    else:
        print("  Database loaded successfully!")

    # Step 7: Claude Code Integration (Optional)
    print("\nStep 7: Claude Code Integration (Optional)")
    print("  The RAG server can be integrated with Claude Code as an MCP server,")
    print("  or used manually via the command line.\n")

    response = input("  Configure Claude Code integration? [Y/n]: ").strip().lower()

    if response not in ('n', 'no'):
        print("\n  Configuring Claude Code MCP server...")

        claude_config_path = get_claude_config_path()
        mcp_config = get_shell_command(script_dir)

        if claude_config_path.exists():
            try:
                config = json.loads(claude_config_path.read_text())
            except json.JSONDecodeError:
                config = {}
        else:
            config = {}

        if "mcpServers" not in config:
            config["mcpServers"] = {}

        config["mcpServers"]["hytale-rag"] = mcp_config
        claude_config_path.write_text(json.dumps(config, indent=2))

        print(f"  Added 'hytale-rag' MCP server to {claude_config_path}")

        print("\n" + "=" * 50)
        print("            Setup Complete!")
        print("=" * 50)
        print("\nThe MCP server has been configured for Claude Code.\n")
        print("To use it:")
        print("  1. Restart Claude Code")
        print("  2. Ask Claude to search the Hytale codebase, e.g.:")
        print("     'Search the Hytale code for player movement'")
        print("     'Find methods related to inventory'")
    else:
        print("\n" + "=" * 50)
        print("            Setup Complete!")
        print("=" * 50)
        print("\nThe RAG server is ready for manual use.\n")
        print("To search the codebase:")
        print(f"  cd {script_dir}")
        print("  npx tsx src/search.ts \"your search query\"\n")
        print("Examples:")
        print("  npx tsx src/search.ts \"player movement\"")
        print("  npx tsx src/search.ts \"inventory\" --limit 10")
        print("  npx tsx src/search.ts --stats")
        print("\nRun setup.py again to configure Claude Code integration later.")

    print("\n" + "-" * 50)
    print("Available search tools:")
    if "server" in data_type or data_type == "all":
        print("  - Server Code: 37,000+ Java methods")
    if "client" in data_type or data_type == "all":
        print("  - Client UI: 353 XAML/UI files")
    if "gamedata" in data_type or data_type == "all":
        print("  - Game Data: 23,000+ items, recipes, NPCs, etc.")
    print("-" * 50 + "\n")


if __name__ == "__main__":
    main()
