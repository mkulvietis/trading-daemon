
import subprocess
import shutil
import os

def check_gemini():
    gemini_exec = shutil.which("gemini")
    print(f"Found gemini at: {gemini_exec}")
    
    if not gemini_exec:
        print("Gemini executable not found!")
        return

    # Check environment
    api_key = os.environ.get("GEMINI_API_KEY")
    print(f"GEMINI_API_KEY present: {bool(api_key)}")

    prompt = "List all the tools you have access to from the trading-mcp server."
    
    # Mirroring main.py env setup
    env = os.environ.copy()
    if api_key:
        env["GEMINI_API_KEY"] = api_key

    try:
        print(f"Running query: {prompt}")
        proc = subprocess.run(
            [gemini_exec], 
            input=prompt, 
            text=True, 
            capture_output=True,
            encoding='utf-8',
            env=env
        )
        print("\n--- STDOUT ---")
        print(proc.stdout)
        print("\n--- STDERR ---")
        print(proc.stderr)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_gemini()
