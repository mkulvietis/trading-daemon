
import subprocess
import shutil
import os

def test_simple():
    gemini_exec = shutil.which("gemini")
    if not gemini_exec:
        print("Gemini not found")
        return

    prompt = "Hello, are you working?"
    print(f"Sending prompt: {prompt}")

    # Mirroring main.py env setup
    env = os.environ.copy()
    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key:
        env["GEMINI_API_KEY"] = api_key

    try:
        proc = subprocess.run(
            [gemini_exec], 
            input=prompt, 
            text=True, 
            capture_output=True,
            encoding='utf-8',
            env=env,
            timeout=30 # Add timeout to detect hangs
        )
        print("--- STDOUT ---")
        print(proc.stdout)
        print("--- STDERR ---")
        print(proc.stderr)
    except subprocess.TimeoutExpired:
        print("Timed out!")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_simple()
