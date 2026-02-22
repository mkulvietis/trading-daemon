"""
Inference orchestration.
Handles running inference, cooldown enforcement, and result parsing.
"""
import json
import logging
import re
import time
from datetime import datetime

from src.state import app_state, NY_TZ
from src.market import is_market_open
from src.models import LLMResponse

logger = logging.getLogger(__name__)

# Global cooldown — prevents any inference source from spamming
INFERENCE_COOLDOWN_SECONDS = 180  # 3 minutes


def is_cooldown_active() -> bool:
    """Returns True if an inference completed less than INFERENCE_COOLDOWN_SECONDS ago."""
    last_completed = app_state.inference.completed_at
    if not last_completed:
        return False
    elapsed = (datetime.now(NY_TZ) - last_completed).total_seconds()
    return elapsed < INFERENCE_COOLDOWN_SECONDS


def run_inference(client, reason: str = None):
    """
    Execute an inference cycle.
    
    Args:
        client: GeminiClient instance.
        reason: If provided, this is an event-driven trigger (bypasses scheduled interval check).
                If None, the call is treated as a scheduled auto-inference.
    """
    if not app_state.is_running:
        return

    # Scheduled auto-inference respects the configured interval
    if not reason:
        interval = app_state.get_auto_inference_interval()
        if interval <= 0:
            return

    if not is_market_open():
        if reason:
            logger.info(f"Ignored trigger '{reason}' — market closed.")
        else:
            app_state.update_output(f"Waiting for market open... (Last check: {time.strftime('%H:%M:%S')})")
        return

    if app_state.is_inference_running():
        logger.info(f"Inference already running. Skipping {'trigger' if reason else 'auto-inference'}.")
        return

    if is_cooldown_active():
        elapsed = (datetime.now(NY_TZ) - app_state.inference.completed_at).total_seconds()
        logger.info(f"Skipping inference (cooldown: {elapsed:.0f}s < {INFERENCE_COOLDOWN_SECONDS}s)")
        return

    # Build context
    now = datetime.now()
    price_str = f"{app_state.last_price:.2f}" if app_state.last_price else "Unknown"
    context = f"Current Time: {now.strftime('%H:%M')}\nCurrent Price: {price_str}"
    if reason:
        context += f"\nTRIGGER: {reason}"
        logger.info(f"Inference triggered: {reason}")

    app_state.start_inference(context=context)
    logger.info(f"Starting inference — {context.replace(chr(10), ', ')}")

    result = client.run_inference(context_header=context)

    # Detect errors in CLI output
    error_patterns = ["Error", "critical error", "ModelNotFoundError", "fetch failed", "Exception"]
    if any(p in result for p in error_patterns):
        app_state.fail_inference(result)
        logger.error(f"Inference failed: {result[:500]}...")
        return

    app_state.complete_inference(result)
    app_state.update_output(result)
    _parse_inference_result(result)
    logger.info("Inference completed successfully")


def _parse_inference_result(result: str):
    """Extract JSON from LLM output and update trade manager."""
    try:
        # Try ```json ... ``` block first
        json_match = re.search(r"```json\s*(.*?)```", result, re.DOTALL)
        if json_match:
            clean_json = json_match.group(1).strip()
        else:
            # Fallback: find outermost { ... }
            start = result.find("{")
            end = result.rfind("}") + 1
            if start != -1 and end > start:
                clean_json = result[start:end]
            else:
                clean_json = result.replace("```json", "").replace("```", "").strip()

        data = json.loads(clean_json)
        response = LLMResponse(**data)
        app_state.trade_manager.add_setups(response.setups)
    except Exception as e:
        logger.error(f"Failed to parse inference JSON: {e}")
