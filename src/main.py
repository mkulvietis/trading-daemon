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

from src.state import app_state, NY_TZ
from datetime import datetime
from src.market import is_market_open
from src.config import setup_gemini_config
from src.gemini_client import GeminiClient
from src.web_server import run_web_server, set_gemini_client
from src.models import TradeSetup, LLMResponse
import urllib.request

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

def fetch_current_price(api_base="http://localhost:8000") -> float:
    """Fetches the latest close price from data-service."""
    try:
        # Using /bars/latest endpoint assumption or similar. 
        # Alternatively, use /analysis/market_data for 1 bar
        url = f"{api_base}/bars/@ES?timeframe=1&bars_back=1" 
        with urllib.request.urlopen(url, timeout=2) as response:
            data = json.loads(response.read().decode())
            if data and isinstance(data, list) and len(data) > 0:
                return float(data[-1]['close'])
    except Exception as e:
        logger.debug(f"Failed to fetch price: {e}")
    return 0.0

def process_llm_result(result_str: str):
    """Parses LLM JSON output and updates TradeManager."""
    try:
        # Strip code blocks if present
        clean_json = result_str.replace("```json", "").replace("```", "").strip()
        data = json.loads(clean_json)
        
        # Validate with Pydantic
        response = LLMResponse(**data)
        
        # Add to manager
        app_state.trade_manager.add_setups(response.setups)
        
    except json.JSONDecodeError:
        logger.error("Failed to parse LLM JSON output")
        app_state.fail_inference("LLM did not output valid JSON")
    except Exception as e:
        logger.error(f"Error processing LLM result: {e}")
        app_state.fail_inference(f"Error processing result: {e}")

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
        logger.debug("Market closed. Skipping auto-inference.")
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
    now = datetime.now()
    time_str = now.strftime("%H:%M")
    price_str = f"{app_state.last_price:.2f}" if app_state.last_price else "Unknown"
    context = f"Current Time: {time_str}\nCurrent Price: {price_str}"

    app_state.start_inference(context=context)

    logger.info(f"Starting auto-inference with context: {context.replace('\\n', ', ')}")
    result = client.run_inference(context_header=context)
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
        
        try:
            from src.models import LLMResponse
            import json
            import re
            
            clean_json = ""
            json_match = re.search(r"```json\s*(.*?)```", result, re.DOTALL)
            if json_match:
                clean_json = json_match.group(1).strip()
            else:
                start = result.find('{')
                end = result.rfind('}') + 1
                if start != -1 and end != -1:
                    clean_json = result[start:end]
                else:
                    clean_json = result.replace("```json", "").replace("```", "").strip()

            data = json.loads(clean_json)
            response = LLMResponse(**data)
            app_state.trade_manager.add_setups(response.setups)
        except Exception as parse_err:
             logger.error(f"Failed to parse auto-inference JSON: {parse_err}")

    logger.info("Auto-inference completed successfully")


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
            
            # --- NEW: Monitoring Loop (every ~5s) ---
            # Using simple modulo or separate timer could work, 
            # but let's just do it every iteration if we sleep 1s, or maybe every 5th iteration.
            # For responsiveness, let's just fetch every loop but with a small check? 
            # Or better, just fetch every 5 seconds.
            
            if app_state.is_running and int(current_time) % 5 == 0:
                price = fetch_current_price()
                if price > 0:
                     app_state.last_price = price
                     app_state.trade_manager.update_setups(price)
                     # Also prune old
                     app_state.trade_manager.prune_backlog()

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
