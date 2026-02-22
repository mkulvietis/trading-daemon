"""
Trading Daemon — Entry Point
Wires together config, web server, and the main daemon loop.
"""
import json
import time
import threading
import logging
import sys
import os

# Add project root to sys.path to allow running as script from any directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.state import app_state
from src.market import fetch_current_price
from src.config import setup_gemini_config
from src.gemini_client import GeminiClient
from src.web_server import run_web_server, set_gemini_client
from src.inference import run_inference
from src.triggers import check_trendline_proximity

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


def daemon_loop(client: GeminiClient):
    """
    Continuous loop that manages automatic tasks.
    Orchestrates scheduled inference, event-driven triggers, and price monitoring.
    """
    last_auto_run = time.time()
    last_trendline_check = 0.0

    while True:
        try:
            now = time.time()

            # 1. Scheduled Auto-Inference
            interval = app_state.get_auto_inference_interval()
            if (app_state.is_running
                    and interval > 0
                    and now - last_auto_run >= interval):
                run_inference(client)
                last_auto_run = time.time()

            # 2. Trendline Proximity Trigger (every 15s)
            if app_state.is_running and now - last_trendline_check >= 15:
                check_trendline_proximity(client)
                last_trendline_check = time.time()

            # 3. Price monitoring & setup management (every loop iteration)
            if app_state.is_running:
                price = fetch_current_price()
                if price > 0:
                    app_state.last_price = price
                    app_state.trade_manager.update_setups(price)
                    app_state.trade_manager.prune_backlog()

            time.sleep(5)

        except Exception as e:
            logger.error(f"Loop error: {e}")
            time.sleep(5)


def main():
    logger.info("Starting Trading Daemon...")

    # 1. Load Config
    config = load_config()

    # 2. Setup Gemini CLI Config
    setup_gemini_config(config.get("mcp_url", "http://localhost:8000/mcp/"))

    # 3. Initialize Client (system prompt via GEMINI_SYSTEM_MD env var in .gemini/.env)
    client = GeminiClient(user_prompt_path="prompts/user-prompt.md")
    set_gemini_client(client)

    # 4. Start Web Server in separate thread
    web_thread = threading.Thread(target=run_web_server, kwargs={'port': 8001}, daemon=True)
    web_thread.start()
    logger.info("Web server started on port 8001")

    # 5. Start Daemon Loop
    app_state.set_running(True)

    try:
        daemon_loop(client)
    except KeyboardInterrupt:
        logger.info("Stopping daemon...")


if __name__ == "__main__":
    main()
