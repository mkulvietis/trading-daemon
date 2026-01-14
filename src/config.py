import os
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

def setup_gemini_config(mcp_url: str):
    """
    Ensures ~/.gemini/settings.json exists and has the correct MCP configuration.
    """
    user_profile = os.environ.get('USERPROFILE')
    if not user_profile:
        raise EnvironmentError("USERPROFILE environment variable not found")

    gemini_dir = Path(user_profile) / ".gemini"
    settings_path = gemini_dir / "settings.json"

    # Create directory if it doesn't exist
    if not gemini_dir.exists():
        logger.info(f"Creating {gemini_dir}")
        gemini_dir.mkdir(parents=True, exist_ok=True)

    # Load existing config or start fresh
    config = {}
    if settings_path.exists():
        try:
            with open(settings_path, 'r') as f:
                config = json.load(f)
        except json.JSONDecodeError:
            logger.warning("Existing settings.json was corrupted, starting fresh.")

    # Ensure contextServers list exists
    if "contextServers" not in config:
        config["contextServers"] = []
    
    # Check if our server is already configured
    server_name = "trading-mcp"
    existing_server = next((s for s in config["contextServers"] if s.get("name") == server_name), None)

    if existing_server:
        # Update URL if changed
        if existing_server.get("url") != mcp_url:
            logger.info(f"Updating MCP URL for {server_name}")
            existing_server["url"] = mcp_url
    else:
        # Add new server config
        logger.info(f"Adding new MCP server config: {server_name}")
        config["contextServers"].append({
            "name": server_name,
            "url": mcp_url,
            # 'streamable' might be a specific flag or just implied by the URL/protocol implementation.
            # If FastMCP + Streamable requires a specific transport type, we might need:
            # "transport": "sse" (often standard) or something else. 
            # Given user input "MCP Server is using stremable protocol", we'll assume the URL is enough
            # or if 'transport' key is needed. Standard Gemini CLI contextServers usually just need name/url for SSE.
        })

    # Write back to file
    with open(settings_path, 'w') as f:
        json.dump(config, f, indent=4)
        logger.info(f"Updated {settings_path}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    setup_gemini_config("http://localhost:8000/mcp/")
