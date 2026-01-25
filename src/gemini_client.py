import subprocess
import shutil
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


class GeminiClient:
    """
    Client for running Gemini CLI in headless mode with Pro model.
    
    Configuration is picked up from the .gemini folder in the project root:
    - .gemini/.env: Contains GEMINI_SYSTEM_MD pointing to system prompt file
    - .gemini/settings.json: Contains MCP server configuration
    """
    
    # Use Pro model for trading inference
    MODEL = "gemini-2.5-pro"
    
    def __init__(self, user_prompt_path: str):
        """
        Initialize the Gemini client.
        
        Args:
            user_prompt_path: Path to the user prompt file.
        """
        self.user_prompt_path = Path(user_prompt_path)
        self.project_root = Path(__file__).parent.parent.resolve()

    def _read_file(self, path: Path) -> str:
        """Read file contents, returning empty string if file doesn't exist."""
        if not path.exists():
            return ""
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()

    def _load_dotenv(self) -> dict:
        """
        Load environment variables from .gemini/.env file.
        Returns a dict of env vars to add to the environment.
        """
        env_file = self.project_root / ".gemini" / ".env"
        env_vars = {}
        
        if env_file.exists():
            with open(env_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        env_vars[key.strip()] = value.strip()
        
        return env_vars

    def run_inference(self) -> str:
        """
        Calls the Gemini CLI in headless mode with -p parameter.
        Uses Pro model for all inference requests.
        
        The system prompt is read from the GEMINI_SYSTEM_MD environment variable
        (set in .gemini/.env). MCP configuration is picked up from .gemini/settings.json.
        """
        # Resolve user prompt path relative to project root
        if self.user_prompt_path.is_absolute():
            prompt_path = self.user_prompt_path
        else:
            prompt_path = self.project_root / self.user_prompt_path
        
        user_prompt = self._read_file(prompt_path)
        
        logger.info(f"User prompt path: {prompt_path}")
        logger.info(f"User prompt content:\n{user_prompt[:500]}...")  # Log first 500 chars
        
        if not user_prompt:
            logger.warning("User prompt is empty")
            return "Error: User prompt is empty"

        # Find gemini executable
        gemini_exec = shutil.which("gemini")
        if not gemini_exec:
            logger.error("Gemini executable not found in PATH")
            return "Error: Gemini executable not found. Please install the Gemini CLI."

        # Prepare environment - load .env from .gemini folder
        env = os.environ.copy()
        dotenv_vars = self._load_dotenv()
        env.update(dotenv_vars)
        
        logger.info(f"Running gemini from: {self.project_root}")
        logger.info(f"Using gemini executable: {gemini_exec}")
        if "GEMINI_SYSTEM_MD" in env:
            logger.info(f"System prompt: {env['GEMINI_SYSTEM_MD']}")

        try:
            # Run in headless mode with Pro model
            cmd = [
                gemini_exec,
                "--model", self.MODEL,
                "--yolo",  # Auto-approve all tool calls (required for non-interactive)
                "-p", user_prompt,  # Headless mode with user prompt
            ]
            logger.info(f"Command: {cmd[0]} --model {self.MODEL} --yolo -p '<prompt of {len(user_prompt)} chars>'")
            
            process = subprocess.run(
                cmd, 
                text=True, 
                capture_output=True,
                check=True,
                env=env,
                encoding='utf-8',
                cwd=str(self.project_root),  # Run from project directory where .gemini/ is located
            )
            logger.info(f"Gemini response:\n{process.stdout}")
            return process.stdout
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Gemini CLI failed: {e.stderr}")
            return f"Error executing Gemini CLI: {e.stderr}"
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return f"Error: {str(e)}"
