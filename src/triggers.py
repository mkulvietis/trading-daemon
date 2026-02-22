"""
Event-driven inference triggers.
Each trigger checks a market condition and calls inference.run_inference() when criteria are met.
"""
import logging

from src.state import app_state
from src.market import fetch_trendlines
from src.inference import is_cooldown_active, run_inference

logger = logging.getLogger(__name__)


def check_trendline_proximity(client):
    """
    Fetches trendlines for the 5m timeframe and triggers inference
    if price is 'at' or 'near' any support/resistance line.
    
    Skips the fetch entirely if cooldown is active or inference is running,
    to avoid unnecessary API calls.
    """
    if not app_state.is_running:
        return

    # Bail early — don't waste a trendline fetch if we can't act on it
    if app_state.is_inference_running() or is_cooldown_active():
        return

    data = fetch_trendlines(timeframe=5)
    if not data or "timeframes" not in data:
        return

    tf_data = data["timeframes"].get("5min")
    if not tf_data or "price_relations" not in tf_data:
        return

    # Collect lines where price is very close
    triggers = []
    for rel in tf_data["price_relations"]:
        if rel["proximity"] in ("at", "near"):
            triggers.append(
                f"{rel['type'].title()} Trendline ({rel['proximity']}, dist={rel['distance']:.2f})"
            )

    if triggers:
        reason = "Price near Trendline: " + "; ".join(triggers[:2])
        run_inference(client, reason=reason)
