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
from src.web_server import run_web_server, set_gemini_client

# Configure logging
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

def job_auto_inference(client: GeminiClient):
    """
    Task to check if we should run automatic inference.
    """
    if not app_state.is_running:
        return

    interval = app_state.get_auto_inference_interval()
    if interval <= 0:
        return

    # Check if market is open if needed (assuming auto-inference respects market hours)
    if not is_market_open():
        logger.info("Market closed. Skipping auto-inference.")
        app_state.update_output(f"Waiting for market open... (Last check: {time.strftime('%H:%M:%S')})")
        return

    # Check if inference is already running
    if app_state.is_inference_running():
        logger.info("Inference already running. Skipping auto trigger.")
        return

    # Check last update time to respect interval
    snapshot = app_state.get_inference_snapshot()
    last_completed = app_state.inference.completed_at # Access directly or parse from snapshot
    
    # Ideally we'd track last_auto_run_time separate from completion time
    # For now, let's keep it simple: if not running, trigger it
    
    logger.info("Triggering auto-inference...")
    app_state.start_inference()
    
    try:
        result = client.run_inference()
        # Check for various error patterns (CLI may exit 0 with error in stdout)
        error_patterns = [
            "Error",
            "critical error",
            "ModelNotFoundError",
            "fetch failed",
            "Exception",
        ]
        is_error = any(pattern in result for pattern in error_patterns)
        
        if is_error:
            app_state.fail_inference(result)
            logger.error(f"Auto-inference failed: {result[:500]}...")
        else:
            app_state.complete_inference(result)
            app_state.update_output(result)
            logger.info("Auto-inference completed.")
    except Exception as e:
        app_state.fail_inference(str(e))
        logger.error(f"Auto-inference exception: {e}")


def daemon_loop(client: GeminiClient):
    """
    Continuous loop that manages automatic tasks.
    """
    last_auto_run = time.time()  # Start with current time to prevent immediate trigger
    
    while True:
        try:
            current_time = time.time()
            interval = app_state.get_auto_inference_interval()
            
            # Check if we should run auto-inference
            if (app_state.is_running and 
                interval > 0 and 
                current_time - last_auto_run >= interval):
                
                job_auto_inference(client)
                last_auto_run = time.time()
            
            # Sleep a bit to avoid CPU spin, but respond quickly to stop/config
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
    
    # Set client for web server
    set_gemini_client(client)
    
    # 4. Start Web Server in separate thread
    web_thread = threading.Thread(target=run_web_server, kwargs={'port': 8001}, daemon=True)
    web_thread.start()
    logger.info("Web server started on port 8001")
    
    # 5. Start Daemon Loop in main thread
    app_state.set_running(True) 
    
    try:
        daemon_loop(client)
    except KeyboardInterrupt:
        logger.info("Stopping daemon...")

if __name__ == "__main__":
    main()
