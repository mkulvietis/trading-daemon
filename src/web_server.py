from flask import Flask, render_template_string, request, redirect, url_for, jsonify
import threading
from src.state import app_state

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Trading Daemon Control</title>
    <style>
        body { font-family: sans-serif; max-width: 800px; margin: 2rem auto; padding: 0 1rem; }
        .status { padding: 1rem; border-radius: 4px; margin-bottom: 1rem; transition: background-color 0.3s; }
        .running { background-color: #d4edda; color: #155724; }
        .stopped { background-color: #f8d7da; color: #721c24; }
        .controls { background: #f8f9fa; padding: 1rem; border-radius: 4px; margin-bottom: 1rem; }
        .output-container { background: #2d2d2d; color: #fff; padding: 1rem; border-radius: 4px; min-height: 200px; }
        .output-header { background: #1a1a2e; color: #00d9ff; padding: 0.75rem 1rem; margin: -1rem -1rem 1rem -1rem; border-radius: 4px 4px 0 0; font-size: 1rem; font-weight: bold; border-bottom: 2px solid #00d9ff; }
        .output { white-space: pre-wrap; font-family: monospace; }
        button { padding: 0.5rem 1rem; cursor: pointer; }
        .meta { font-size: 0.85rem; color: #888; margin-top: 0.5rem; border-top: 1px solid #444; padding-top: 0.5rem; }
    </style>
    <script>
        function updateStatus() {
            fetch('/api/status')
                .then(response => response.json())
                .then(data => {
                    // Update Status Box
                    const statusDiv = document.getElementById('status-box');
                    statusDiv.className = 'status ' + (data.is_running ? 'running' : 'stopped');
                    
                    document.getElementById('status-text').textContent = data.is_running ? 'RUNNING' : 'STOPPED';
                    document.getElementById('interval-text').textContent = data.current_interval;
                    document.getElementById('updated-text').textContent = data.last_updated || 'Never';

                    // Update Controls (Start/Stop button visibility)
                    const startBtn = document.getElementById('btn-start');
                    const stopBtn = document.getElementById('btn-stop');
                    if (data.is_running) {
                        startBtn.style.display = 'none';
                        stopBtn.style.display = 'inline-block';
                    } else {
                        startBtn.style.display = 'inline-block';
                        stopBtn.style.display = 'none';
                    }

                    // Update Output
                    document.getElementById('output-text').textContent = data.last_output;
                    document.getElementById('output-timestamp').textContent = '(' + (data.last_updated || 'N/A') + ')';
                })
                .catch(err => console.error('Failed to fetch status:', err));
        }

        // Poll every 20 seconds
        setInterval(updateStatus, 20000);
        
        // Initial load
        window.onload = updateStatus;
    </script>
</head>
<body>
    <h1>Trading Daemon Control</h1>
    
    <div id="status-box" class="status {{ 'running' if state.is_running else 'stopped' }}">
        Status: <strong id="status-text">{{ 'RUNNING' if state.is_running else 'STOPPED' }}</strong>
        | Interval: <span id="interval-text">{{ state.current_interval }}</span>s
        | Last Update: <span id="updated-text">{{ state.last_updated }}</span>
    </div>

    <div class="controls">
        <form action="/control" method="post" style="display: inline;">
            <button id="btn-stop" type="submit" name="action" value="stop" style="display: {{ 'inline-block' if state.is_running else 'none' }};">Stop Daemon</button>
            <button id="btn-start" type="submit" name="action" value="start" style="display: {{ 'none' if state.is_running else 'inline-block' }};">Start Daemon</button>
        </form>

        <form action="/config" method="post" style="display: inline; margin-left: 2rem;">
            <label>Interval (s): <input type="number" name="interval" value="{{ state.current_interval }}" style="width: 60px;"></label>
            <button type="submit">Update Config</button>
        </form>
    </div>

    <h3>Latest Output</h3>
    <div class="output-container">
        <div id="output-header" class="output-header">📊 Analysis generated: <span id="output-timestamp">{{ state.last_updated or 'N/A' }}</span></div>
        <div id="output-text" class="output">{{ state.last_output }}</div>
        <div class="meta">Auto-refreshing every 20s...</div>
    </div>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE, state=app_state.get_snapshot())

@app.route("/api/status")
def status_api():
    return jsonify(app_state.get_snapshot())

@app.route("/control", methods=["POST"])
def control():
    action = request.form.get("action")
    if action == "start":
        app_state.set_running(True)
    elif action == "stop":
        app_state.set_running(False)
    # Redirect back to index to re-render template with new state (though JS would catch up too)
    return redirect(url_for("index"))

@app.route("/config", methods=["POST"])
def config():
    try:
        interval = int(request.form.get("interval"))
        if interval > 0:
            app_state.set_interval(interval)
    except ValueError:
        pass
    return redirect(url_for("index"))

def run_web_server(port=8001):
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

if __name__ == "__main__":
    run_web_server()
