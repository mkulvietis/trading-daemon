"""
Test script to verify Gemini CLI can access MCP server tools from Python.
This mimics exactly how gemini_client.py invokes the CLI.
"""
import subprocess
import shutil
import os
from pathlib import Path

def test_mcp_access():
    gemini_exec = shutil.which("gemini")
    if not gemini_exec:
        print("Gemini not found")
        return

    # Project root - same as gemini_client.py
    project_root = Path(__file__).parent.resolve()
    
    prompt = "List all tools available from the trading-mcp server."
    print(f"Sending prompt: {prompt}")
    print(f"Using gemini at: {gemini_exec}")
    print(f"Running from cwd: {project_root}")
    print(f"Project .gemini/settings.json exists: {(project_root / '.gemini' / 'settings.json').exists()}")

    # Mirroring main.py env setup
    env = os.environ.copy()
    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key:
        env["GEMINI_API_KEY"] = api_key

    try:
        proc = subprocess.run(
            [
                gemini_exec,
                "--yolo",  # Auto-approve all tool calls
                "--allowed-mcp-server-names", "trading-mcp",  # Allow this server
            ], 
            input=prompt, 
            text=True, 
            capture_output=True,
            encoding='utf-8',
            env=env,
            cwd=str(project_root),  # Run from project directory
            timeout=120
        )
        print("\n--- STDOUT ---")
        print(proc.stdout)
        if proc.stderr:
            print("\n--- STDERR ---")
            print(proc.stderr)
        print(f"\n--- Return Code: {proc.returncode} ---")
    except subprocess.TimeoutExpired:
        print("Timed out after 120 seconds!")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_mcp_access()
