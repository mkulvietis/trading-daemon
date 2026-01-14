# Market Trading Daemon

A Python-based automated trading assistant that leverages the **Gemini CLI** and **Model Context Protocol (MCP)** to analyze market data and generate trading setups during New York market hours.

## Features

- **Automated Analysis**: Runs continuously during NY market sessions (9:30 AM - 4:00 PM ET, Mon-Fri).
- **Gemini & MCP Integration**: Uses your local `gemini` CLI to query a local MCP server (`data-service`) for real-time market state evaluation.
- **Dynamic Configuration**: 
  - `app_config.json`: Configure update intervals and MCP endpoints.
  - Auto-configures `~/.gemini/settings.json` for seamless CLI integration.
- **Web Interface**:
  - Control Dashboard at `http://localhost:8001`.
  - Start/Stop the daemon manually.
  - Monitor latest output and status.
  - Adjust sampling intervals on the fly.

## Prerequisites

- **Python 3.10+**
- **Gemini CLI**: Installed and accessible in your system PATH (`gemini` command).
- **Local MCP Server**: An MCP server (e.g., `data-service`) running at `http://localhost:8000/mcp/`.

## Authentication

The Gemini CLI requires an API key. You can obtain one from [Google AI Studio](https://aistudio.google.com/).

**Option 1: Environment Variable (Recommended)**
```bash
set GEMINI_API_KEY=your_api_key_here
# OR for PowerShell
$env:GEMINI_API_KEY="your_api_key_here"
```

**Option 2: Settings File**
Add your key to `~/.gemini/settings.json`:
```json
{
    "apiKey": "your_api_key_here",
    "contextServers": [...]
}
```

## Installation

1.  **Clone the repository** (or navigate to the project directory):
    ```bash
    cd c:\src\trading-daemon
    ```

2.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    # OR manual installation
    pip install flask requests schedule pytz
    ```

## Usage

1.  **Start the Daemon**:
    ```bash
    python src/main.py
    ```

2.  **Access the Dashboard**:
    Open your browser to [http://localhost:8001](http://localhost:8001).

3.  **Operation**:
    - The daemon will automatically check if the market is open.
    - If Open: It sends a prompt (from `prompts/user-prompt.md`) to Gemini, which uses the `get_market_state` tool.
    - The result is displayed on the dashboard.

## Project Structure

- `src/main.py`: Entry point. Orchestrates the daemon loop and web server.
- `src/market.py`: Logic for validating NY market hours.
- `src/config.py`: Handles `app_config.json` loading and Gemini CLI configuration.
- `src/gemini_client.py`: Wrapper for executing `gemini` CLI commands.
- `src/web_server.py`: Flask application for the control interface.
- `src/state.py`: Thread-safe shared state management.
- `prompts/`: Contains `system-prompt.md` and `user-prompt.md`.

## Configuration

**`app_config.json`**:
```json
{
    "interval_seconds": 120,
    "market_hours_enabled": true,
    "mcp_url": "http://localhost:8000/mcp/"
}
```
*Changes to `interval_seconds` can be made via the Web UI without restarting.*
