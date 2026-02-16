import subprocess
import shutil
import logging
import os
import threading
from pathlib import Path

logger = logging.getLogger(__name__)


class GeminiClient:
    """
    Client for running Gemini CLI in headless mode with Pro model.
    
    Configuration is picked up from the .gemini folder in the project root:
    - .gemini/.env: Contains GEMINI_SYSTEM_MD pointing to system prompt file
    - .gemini/settings.json: Contains MCP server configuration
    """
    
    # Use latest Pro preview model for trading inference
    MODEL = "gemini-3-pro-preview"
    
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

    def run_inference(self, context_header: str = "", prompt_path: Path = None) -> str:
        """
        Calls the Gemini CLI in headless mode with -p parameter.
        Uses Pro model for all inference requests.
        
        Args:
            context_header: Optional text derived from logic (e.g. current time/price) 
                          to prepend to the user prompt.
            prompt_path: Optional path to override the default user prompt file.

        The system prompt is read from the GEMINI_SYSTEM_MD environment variable
        (set in .gemini/.env). MCP configuration is picked up from .gemini/settings.json.
        """
        # Determine effective prompt path
        effective_prompt_path = Path(prompt_path) if prompt_path else self.user_prompt_path
        # Resolve user prompt path relative to project root
        if effective_prompt_path.is_absolute():
            prompt_path = effective_prompt_path
        else:
            prompt_path = self.project_root / effective_prompt_path
        
        user_prompt = self._read_file(prompt_path)
        
        # Prepend context if provided
        if context_header:
            user_prompt = f"{context_header}\n\n{user_prompt}"
        
        logger.info(f"User prompt path: {prompt_path}")
        logger.info(f"User prompt content:\n{user_prompt[:500]}...")  # Log first 500 chars
        
        if not user_prompt:
            logger.warning("User prompt is empty")
            return "Error: User prompt is empty"

        # Find gemini executable
        gemini_exec = shutil.which("gemini")
        if not gemini_exec:
            # Fallback to common Windows npm path
            npm_path = Path(os.environ.get("APPDATA", "")) / "npm" / "gemini.cmd"
            if npm_path.exists():
                gemini_exec = str(npm_path)
        
        if not gemini_exec:
            logger.error("Gemini executable not found in PATH or APPDATA/npm")
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
            
            # Use Popen to stream output to console in real-time
            process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,  # Capture stderr separately
                text=True, 
                env=env,
                encoding='utf-8',
                cwd=str(self.project_root),
                bufsize=1, # Line buffered
            )
            
            full_output = []
            print(f"--- START GEMINI INFERENCE ---")
            print(f"Using prompt file: {prompt_path.name}")
            
            # Create threads to read stdout and stderr concurrently
            def read_stream(stream, is_stderr):
                for line in stream:
                    print(line, end='', flush=True)
                    if not is_stderr:
                        full_output.append(line)

            stdout_thread = threading.Thread(target=read_stream, args=(process.stdout, False))
            stderr_thread = threading.Thread(target=read_stream, args=(process.stderr, True))
            
            stdout_thread.start()
            stderr_thread.start()
            
            stdout_thread.join()
            stderr_thread.join()
            
            print(f"\n--- END GEMINI INFERENCE ---")
            
            process.wait()
            result = "".join(full_output)
            
            logger.info(f"Gemini response length: {len(result)} chars")
            
            if process.returncode != 0:
                logger.error(f"Gemini CLI failed with code {process.returncode}")
                # We return the result anyway as it might contain the error message
                return result if result else f"Error: Gemini CLI failed with code {process.returncode}"
                
            return result
            
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return f"Error: {str(e)}"
