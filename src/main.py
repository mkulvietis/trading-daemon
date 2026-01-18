import json
import time
import threading
import logging
import schedule
import sys
import os
from pathlib import Path

# Add project root to sys.path to allow running as script from any directory
# This fixes "ModuleNotFoundError: No module named 'src'" when running `python src/main.py`
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.state import app_state
from src.market import is_market_open
from src.config import setup_gemini_config
from src.gemini_client import GeminiClient
from src.web_server import run_web_server

# Configure loggingpython 
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("daemon.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("Main")

def load_config():
    try:
        with open("app_config.json", "r") as f:
            config = json.load(f)
            app_state.set_interval(config.get("interval_seconds", 120))
            return config
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        return {"interval_seconds": 120, "mcp_url": "http://localhost:8000/mcp/"}

def job(client: GeminiClient):
    """
    The core trading logic task.
    """
    if not app_state.is_running:
        return

    # Check market hours if enabled (can be toggled in config, but for now hardcoded check)
    # The requirement says "working days 9:30-16:00".
    if not is_market_open():
        logger.info("Market closed. Skipping cycle.")
        app_state.update_output(f"Waiting for market open... (Last check: {time.strftime('%H:%M:%S')})")
        return

    logger.info("Running trading cycle...")

    try:
        result = client.run_inference()
        logger.info("Cycle completed.")
        app_state.update_output(result)
        # Here you could also save result to history, database, etc.
    except Exception as e:
        logger.error(f"Cycle failed: {e}")
        app_state.update_output(f"Error: {e}")

def daemon_loop(client: GeminiClient):
    """
    Continuous loop that respects the dynamic interval.
    """
    while True:
        try:
            # We don't use `schedule` library strictly if we want dynamic interval 
            # because schedule is better for fixed times. 
            # Simple sleep loop is better for dynamic interval.
            
            start_time = time.time()
            
            # Execute job
            job(client)
            
            # Calculate wait time
            elapsed = time.time() - start_time
            wait_time = max(1, app_state.current_interval - elapsed)
            
            # Sleep in small chunks to allow responsive stop/config changes
            # Wait at most `wait_time`, checking running state every second
            wake_at = time.time() + wait_time
            while time.time() < wake_at:
                if not app_state.is_running:
                    # If stopped, just idle comfortably
                    time.sleep(1)
                    # Reset wake_at so we don't drift? 
                    # Actually if stopped, we should just wait until started.
                    continue 
                time.sleep(1)
                
        except Exception as e:
            logger.error(f"Loop error: {e}")
            time.sleep(5)

def main():
    logger.info("Starting Trading Daemon...")
    
    # 1. Load Config
    config = load_config()
    
    # 2. Setup Gemini CLI Config
    setup_gemini_config(config.get("mcp_url", "http://localhost:8000/mcp/"))
    
    # 3. Initialize Client (system prompt is read from GEMINI_SYSTEM_MD env var in .gemini/.env)
    client = GeminiClient(user_prompt_path="prompts/user-prompt.md")
    
    # 4. Start Web Server in separate thread
    web_thread = threading.Thread(target=run_web_server, kwargs={'port': 8001}, daemon=True)
    web_thread.start()
    logger.info("Web server started on port 8001")
    
    # 5. Start Daemon Loop in main thread (or vice versa)
    # Let's run daemon loop here.
    app_state.set_running(True) # Start by default? Requirements imply "runs continuously".
    
    try:
        daemon_loop(client)
    except KeyboardInterrupt:
        logger.info("Stopping daemon...")

if __name__ == "__main__":
    main()
