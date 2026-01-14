import subprocess
import shutil
import logging
import json
import os
from pathlib import Path

logger = logging.getLogger(__name__)

class GeminiClient:
    def __init__(self, system_prompt_path: str, user_prompt_path: str):
        self.system_prompt_path = Path(system_prompt_path)
        self.user_prompt_path = Path(user_prompt_path)

    def _read_file(self, path: Path) -> str:
        if not path.exists():
            return ""
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()

    def _get_api_key(self) -> str:
        """
        Retrieves API key from settings.json if not already in env.
        """
        # If already in env, trust it
        if os.environ.get("GEMINI_API_KEY"):
            return os.environ["GEMINI_API_KEY"]

        # Try to read from settings.json
        try:
            settings_path = Path(os.environ.get('USERPROFILE', '')) / ".gemini" / "settings.json"
            if settings_path.exists():
                with open(settings_path, 'r') as f:
                    config = json.load(f)
                    return config.get("apiKey", "")
        except Exception:
            pass
        return ""

    def run_inference(self) -> str:
        """
        Calls the Gemini CLI with the system and user prompts.
        """
        system_prompt = self._read_file(self.system_prompt_path)
        user_prompt = self._read_file(self.user_prompt_path)
        
        full_prompt = f"{system_prompt}\n\n{user_prompt}"

        # Prepare environment
        env = os.environ.copy()
        api_key = self._get_api_key()
        if api_key:
            env["GEMINI_API_KEY"] = api_key

        gemini_exec = shutil.which("gemini")
        if not gemini_exec:
            logger.error("Gemini executable not found in PATH")
            return "Error: Gemini executable not found. Please install the Gemini CLI."

        try:
            process = subprocess.run(
                [gemini_exec], 
                input=full_prompt, 
                text=True, 
                capture_output=True,
                check=True,
                env=env,
                encoding='utf-8' # Ensure UTF-8 handling
            )
            return process.stdout
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Gemini CLI failed: {e.stderr}")
            return f"Error executing Gemini CLI: {e.stderr}"
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return f"Error: {str(e)}"
