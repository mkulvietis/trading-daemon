from flask import Flask, render_template_string, request, redirect, url_for, jsonify
import threading
import logging
from src.state import app_state

logger = logging.getLogger(__name__)

app = Flask(__name__)

# Reference to the GeminiClient, set by main.py
_gemini_client = None

def set_gemini_client(client):
    """Set the GeminiClient instance for inference endpoints."""
    global _gemini_client
    _gemini_client = client

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Trading Daemon</title>
    <style>
        body { font-family: 'Segoe UI', sans-serif; max-width: 900px; margin: 2rem auto; padding: 0 1rem; background: #0d1117; color: #e6edf3; }
        h1 { color: #58a6ff; border-bottom: 2px solid #30363d; padding-bottom: 0.5rem; }
        .card { background: #161b22; padding: 1.5rem; border-radius: 8px; border: 1px solid #30363d; margin-bottom: 1.5rem; }
        
        .controls { display: flex; gap: 1rem; align-items: center; flex-wrap: wrap; margin-bottom: 1rem; }
        
        .status-badge { display: inline-block; padding: 0.25rem 0.75rem; border-radius: 4px; font-weight: 600; font-size: 0.85rem; }
        .running { background: rgba(88, 166, 255, 0.2); color: #58a6ff; }
        .complete { background: rgba(63, 185, 80, 0.2); color: #3fb950; }
        .error { background: rgba(248, 81, 73, 0.2); color: #f85149; }
        .idle { background: rgba(110, 118, 129, 0.2); color: #8b949e; }
        
        .output-container { background: #0d1117; border-radius: 4px; border: 1px solid #30363d; margin-top: 1rem; }
        .output-header { background: #21262d; padding: 0.5rem 1rem; font-size: 0.85rem; color: #8b949e; display: flex; justify-content: space-between; }
        .output-content { padding: 1rem; white-space: pre-wrap; font-family: Consolas, monospace; font-size: 0.9rem; max-height: 400px; overflow-y: auto; color: #8b949e; }
        
        button { padding: 0.5rem 1rem; cursor: pointer; border: none; border-radius: 4px; font-weight: 600; }
        button:hover { opacity: 0.9; }
        button:disabled { opacity: 0.5; cursor: not-allowed; }
        .btn-primary { background: linear-gradient(135deg, #58a6ff, #a371f7); color: white; }
        .btn-secondary { background: #21262d; color: #8b949e; border: 1px solid #30363d; }
        
        input[type="number"] { padding: 0.4rem; border: 1px solid #30363d; border-radius: 4px; width: 70px; background: #0d1117; color: #e6edf3; }
        label { font-size: 0.9rem; color: #8b949e; margin-right: 0.5rem; }
        .meta { font-size: 0.85rem; color: #6e7681; }
    </style>
    <script>
        function updateStatus() {
            fetch('/api/inference')
                .then(r => r.json())
                .then(data => {
                    const status = data.status;
                    const badge = document.getElementById('status-badge');
                    badge.textContent = status.toUpperCase();
                    badge.className = 'status-badge ' + status;
                    
                    const btn = document.getElementById('btn-run');
                    btn.disabled = status === 'running';
                    btn.textContent = status === 'running' ? '⟳ Running...' : '▶ Run Inference';
                    
                    const output = document.getElementById('output-content');
                    if (data.result) {
                        output.textContent = data.result;
                        output.style.color = '#e6edf3';
                    } else if (data.error) {
                        output.textContent = data.error;
                        output.style.color = '#f85149';
                    }
                    
                    document.getElementById('last-run').textContent = data.completed_at || 'Never';
                    document.getElementById('completed-at').style.display = data.completed_at ? 'inline' : 'none';
                });
            
            fetch('/api/auto-inference')
                .then(r => r.json())
                .then(data => {
                    document.getElementById('current-interval').textContent = data.interval > 0 ? (data.interval / 60) + ' min' : 'Off';
                });
        }
        
        function triggerInference() {
            fetch('/api/inference', { method: 'POST' }).then(updateStatus);
        }
        
        function setAutoInterval() {
            const minutes = document.getElementById('input-interval').value;
            fetch('/api/auto-inference', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ interval: minutes * 60 })
            }).then(updateStatus);
        }
        
        setInterval(updateStatus, 5000);
        window.onload = updateStatus;
    </script>
</head>
<body>
    <h1>Trading Daemon</h1>
    
    <div class="card">
        <div class="controls">
            <button id="btn-run" onclick="triggerInference()" class="btn-primary">▶ Run Inference</button>
            <span id="status-badge" class="status-badge idle">IDLE</span>
            <span id="completed-at" class="meta" style="display: none;">Completed at: <span id="last-run"></span></span>
            
            <span style="border-left: 1px solid #30363d; padding-left: 1rem; margin-left: 0.5rem;">
                <label>Auto:</label>
                <input id="input-interval" type="number" value="10" min="0">
                <span class="meta">min</span>
                <button onclick="setAutoInterval()" class="btn-secondary">Set</button>
                <span class="meta">(Current: <span id="current-interval">-</span>)</span>
            </span>
        </div>
        
        <div class="output-container">
            <div class="output-header">
                <span>Output</span>
                <span>GEMINI 2.5 PRO</span>
            </div>
            <div id="output-content" class="output-content">// Waiting for inference...</div>
        </div>
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


# ==================== NEW INFERENCE ENDPOINTS ====================

@app.route("/api/inference", methods=["GET"])
def get_inference():
    """
    Poll for inference status and result.
    
    Returns:
        - status: "none" | "running" | "complete" | "error"
        - result: inference result (if complete)
        - error: error message (if error)
        - started_at: when inference started
        - completed_at: when inference completed
    """
    return jsonify(app_state.get_inference_snapshot())


@app.route("/api/inference", methods=["POST"])
def trigger_inference():
    """
    Trigger a new inference request.
    
    Returns 409 if inference is already running.
    Returns 503 if GeminiClient is not configured.
    """
    if app_state.is_inference_running():
        return jsonify({"error": "Inference already in progress"}), 409
    
    if _gemini_client is None:
        return jsonify({"error": "GeminiClient not configured"}), 503
    
    # Start inference in background thread
    def run_inference_async():
        try:
            app_state.start_inference()
            logger.info("Starting inference...")
            result = _gemini_client.run_inference()
            
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
                logger.error(f"Inference failed: {result[:500]}...")
            else:
                app_state.complete_inference(result)
                app_state.update_output(result)  # Also update main output
                logger.info("Inference completed successfully")
        except Exception as e:
            error_msg = str(e)
            app_state.fail_inference(error_msg)
            logger.error(f"Inference exception: {error_msg}")
    
    thread = threading.Thread(target=run_inference_async, daemon=True)
    thread.start()
    
    return jsonify({"message": "Inference started", "status": "running"}), 202


@app.route("/api/auto-inference", methods=["GET"])
def get_auto_inference():
    """
    Get automatic inference interval setting.
    
    Returns:
        - interval: seconds between automatic inferences (0 = disabled)
    """
    return jsonify({
        "interval": app_state.get_auto_inference_interval()
    })


@app.route("/api/auto-inference", methods=["POST"])
def set_auto_inference():
    """
    Set automatic inference interval.
    
    Body (JSON):
        - interval: seconds between automatic inferences (0 = disable)
    
    Returns the new interval setting.
    """
    data = request.get_json() or {}
    try:
        interval = int(data.get("interval", 0))
        app_state.set_auto_inference_interval(interval)
        logger.info(f"Auto-inference interval set to {interval}s")
        return jsonify({
            "interval": app_state.get_auto_inference_interval(),
            "message": "disabled" if interval == 0 else f"set to {interval}s"
        })
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid interval value"}), 400


def run_web_server(port=8001):
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

if __name__ == "__main__":
    run_web_server()
