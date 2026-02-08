from flask import Flask, render_template_string, request, redirect, url_for, jsonify
import threading
import logging
import re
import json
from datetime import datetime
from flask_cors import CORS
from src.state import app_state, NY_TZ

logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Filter out noisy polling logs
class EndpointFilter(logging.Filter):
    def filter(self, record):
        msg = record.getMessage()
        return not (
            "GET /api/status" in msg or 
            "GET /api/inference" in msg or 
            "GET /api/auto-inference" in msg
        )

# Apply filter to werkzeug logger
logging.getLogger("werkzeug").addFilter(EndpointFilter())

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
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Trading Daemon</title>
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <style>
        *, *::before, *::after { box-sizing: border-box; }
        html, body { height: 100%; margin: 0; padding: 0; overflow: hidden; font-family: 'Segoe UI', sans-serif; background: #0d1117; color: #e6edf3; display: flex; flex-direction: column; }
        
        .header-container { padding: 0.75rem 1rem; border-bottom: 1px solid #30363d; flex-shrink: 0; display: flex; align-items: center; justify-content: space-between; }
        h1 { color: #58a6ff; margin: 0; font-size: 1.25rem; }
        
        .main-container { flex: 1; min-height: 0; padding: 0.5rem; display: flex; flex-direction: column; }
        .card { background: #161b22; border-radius: 8px; border: 1px solid #30363d; display: flex; flex-direction: column; flex: 1; min-height: 0; margin-bottom: 0.5rem; }
        
        .controls { padding: 0.75rem 1rem; border-bottom: 1px solid #30363d; flex-shrink: 0; display: flex; gap: 0.75rem; align-items: center; flex-wrap: wrap; }
        
        .status-badge { display: inline-block; padding: 0.2rem 0.6rem; border-radius: 4px; font-weight: 600; font-size: 0.8rem; }
        .running { background: rgba(88, 166, 255, 0.2); color: #58a6ff; }
        .idle { background: rgba(110, 118, 129, 0.2); color: #8b949e; }
        
        /* Tabs */
        .tab-nav { display: flex; background: #21262d; border-bottom: 1px solid #30363d; }
        .tab-btn { background: transparent; border: none; color: #8b949e; padding: 0.75rem 1rem; cursor: pointer; font-weight: 600; border-bottom: 2px solid transparent; }
        .tab-btn:hover { color: #e6edf3; }
        .tab-btn.active { color: #58a6ff; border-bottom-color: #58a6ff; }
        
        .tab-content { display: none; flex: 1; flex-direction: column; min-height: 0; overflow: hidden; }
        .tab-content.active { display: flex; }

        .output-content { flex: 1; padding: 1rem; overflow-y: auto; font-size: 0.85rem; color: #e6edf3; }
        
        /* Button Styles */
        button { padding: 0.5rem 0.9rem; cursor: pointer; border: none; border-radius: 4px; font-weight: 600; font-size: 0.85rem; }
        .btn-primary { background: #1f6feb; color: white; }
        .btn-secondary { background: #21262d; color: #c9d1d9; border: 1px solid #30363d; }
        input[type="number"] { padding: 0.4rem; border: 1px solid #30363d; border-radius: 4px; width: 55px; background: #0d1117; color: #e6edf3; }
        
        .auto-controls { display: flex; align-items: center; gap: 0.5rem; border-left: 1px solid #30363d; padding-left: 0.75rem; margin-left: 0.25rem; }
        
        table { width: 100%; border-collapse: collapse; font-size: 0.85rem; table-layout: fixed; }
        th, td { border-bottom: 1px solid #30363d; padding: 0.5rem; text-align: left; overflow: hidden; text-overflow: ellipsis; }
        th { color: #8b949e; position: sticky; top: 0; background: #161b22; position: relative; }
        th .resizer { position: absolute; right: 0; top: 0; height: 100%; width: 5px; cursor: col-resize; background: transparent; }
        th .resizer:hover, th .resizer.resizing { background: #58a6ff; }
    </style>
    <script>
        function switchTab(id) {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            document.getElementById('btn-' + id).classList.add('active');
            document.getElementById('tab-' + id).classList.add('active');
            localStorage.setItem('active_tab', id);
        }

        // jsonToYaml removed - using JSON.stringify


        function updateStatus() {
            fetch('/api/inference')
                .then(r => r.json())
                .then(data => {
                    document.getElementById('status-badge').className = 'status-badge ' + data.status;
                    document.getElementById('status-badge').textContent = data.status.toUpperCase();
                    
                    const btn = document.getElementById('btn-run');
                    btn.disabled = data.status === 'running';
                    btn.textContent = data.status === 'running' ? '⟳ Running...' : '▶ Run';
                    
                    const output = document.getElementById('output-content');
                    if (data.result) {
                        try {
                            const cleanJson = data.result.replaceAll('\\u0060' + '\\u0060' + '\\u0060json', '').replaceAll('\\u0060' + '\\u0060' + '\\u0060', '').trim();
                            const parsed = JSON.parse(cleanJson);
                            
                            if (parsed.setups && Array.isArray(parsed.setups)) {
                                let html = '';
                                
                                // Display inference time and price if present
                                if (parsed.inference_time || parsed.inference_price) {
                                    html += '<div style="font-size: 0.8rem; color: #8b949e; margin-bottom: 0.75rem; display: flex; gap: 1rem;">';
                                    if (parsed.inference_time) html += '<span>⏱️ ' + parsed.inference_time + '</span>';
                                    if (parsed.inference_price) html += '<span>💰 ' + parsed.inference_price + '</span>';
                                    html += '</div>';
                                }
                                
                                // Display market overview if present
                                if (parsed.market_overview) {
                                    html += '<div style="background: #1c2128; border: 1px solid #30363d; border-radius: 6px; padding: 0.75rem; margin-bottom: 1rem;">';
                                    html += '<div style="font-size: 0.75rem; color: #8b949e; margin-bottom: 0.25rem;">MARKET OVERVIEW</div>';
                                    html += '<div style="color: #c9d1d9;">' + parsed.market_overview + '</div>';
                                    html += '</div>';
                                }
                                
                                parsed.setups.forEach(setup => {
                                    const color = setup.direction === 'LONG' ? '#3fb950' : '#f85149';
                                    html += `
                                        <div style="background: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 1rem; margin-bottom: 1rem;">
                                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                                                <h3 style="margin: 0; color: ${color};">${setup.direction} ${setup.symbol}</h3>
                                                <span class="status-badge" style="background: rgba(110, 118, 129, 0.2); color: #8b949e;">${setup.status || 'NEW'}</span>
                                            </div>
                                            <p style="margin: 0.5rem 0; color: #c9d1d9;">${setup.reasoning || ''}</p>
                                            <div style="font-size: 0.85rem; color: #8b949e; border-top: 1px solid #30363d; padding-top: 0.5rem; margin-top: 0.5rem;">
                                                <strong>Entry:</strong> ${setup.entry.type} @ ${setup.entry.price}<br>
                                                <strong>Stop:</strong> ${setup.stop_loss.price}<br>
                                                <strong>Targets:</strong> ${setup.targets.map(t => t.price).join(', ')}
                                            </div>
                                        </div>`;
                                });
                                
                                // If no setups, show a helpful message
                                if (parsed.setups.length === 0) {
                                    html += '<div style="text-align: center; padding: 1.5rem; color: #8b949e; background: #161b22; border: 1px solid #30363d; border-radius: 6px;">';
                                    html += '<div style="font-size: 1.5rem; margin-bottom: 0.5rem;">⏸️</div>';
                                    html += '<div style="font-weight: 600; color: #c9d1d9; margin-bottom: 0.25rem;">No Trade Setups</div>';
                                    html += '<div style="font-size: 0.85rem;">AI found no high-probability entries at this time.</div>';
                                    html += '</div>';
                                }
                                
                                output.innerHTML = html;
                            } else {
                                // Fallback to JSON for readability
                                output.innerHTML = '<pre style="font-family: Consolas; color: #e6edf3;">' + JSON.stringify(parsed, null, 2) + '</pre>';
                            }
                        } catch (e) {
                            output.innerHTML = marked.parse(data.result);
                        }
                    } else if (data.error) {
                        output.textContent = data.error;
                        output.style.color = '#f85149';
                    }
                    
                    document.getElementById('last-run').textContent = data.completed_at || '-';
                    document.getElementById('completed-at').style.display = data.completed_at ? 'inline' : 'none';
                });
                
            fetch('/api/status').then(r => r.json()).then(data => {
                const tbody = document.getElementById('setups-body');
                const setups = data.active_setups || [];
                if (setups.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: #8b949e; padding: 1rem;">No active setups</td></tr>';
                } else {
                    tbody.innerHTML = setups.map(s => {
                        let timeStr = '--';
                        if (s.created_at) {
                            // Extract HH:MM directly from the stored datetime string (already local time)
                            const match = s.created_at.match(/(\\d{2}):(\\d{2})/);
                            if (match) {
                                timeStr = match[0];
                            }
                        }
                        return `
                        <tr>
                            <td style="color: #8b949e;">${timeStr}</td>
                            <td>${s.symbol}</td>
                            <td style="color: ${s.direction === 'LONG' ? '#3fb950' : '#f85149'}; font-weight: bold;">${s.direction}</td>
                            <td>${s.entry.price}</td>
                            <td><span class="status-badge" style="background: rgba(110, 118, 129, 0.2); color: #e6edf3;">${s.status}</span></td>
                            <td style="color: #8b949e; white-space: nowrap;" title="${s.rules_text}">${s.rules_text}</td>
                        </tr>
                    `; }).join('');
                }
            });
        }
        
        function triggerInference() { 
            const btn = document.getElementById('btn-run');
            btn.textContent = 'Starting...';
            btn.disabled = true;
            
            console.log('Triggering inference...');
            fetch('/api/inference', { method: 'POST' })
                .then(r => {
                    console.log('Inference triggered, status:', r.status);
                    if (!r.ok) return r.text().then(t => { throw new Error(t) });
                    return r;
                })
                .then(updateStatus)
                .catch(e => {
                    console.error('Trigger error:', e);
                    alert('Failed to trigger inference: ' + e.message);
                    btn.textContent = '▶ Run';
                    btn.disabled = false;
                });
        }
        function setAutoInterval() {
            const minutes = document.getElementById('input-interval').value;
            fetch('/api/auto-inference', { 
                method: 'POST', 
                headers: {'Content-Type': 'application/json'}, 
                body: JSON.stringify({ interval: minutes * 60 }) 
            }).then(updateStatus);
        }
        
        window.onload = function() {
            const savedTab = localStorage.getItem('active_tab') || 'analysis';
            switchTab(savedTab);
            updateStatus();
            setInterval(updateStatus, 2000);
            initColumnResize();
        };
        
        function initColumnResize() {
            const table = document.getElementById('setups-table');
            if (!table) return;
            
            const headers = table.querySelectorAll('th');
            const colWidths = JSON.parse(localStorage.getItem('setupColumnWidths') || '{}');
            
            headers.forEach((th, index) => {
                // Restore saved width
                if (colWidths[index]) {
                    th.style.width = colWidths[index] + 'px';
                }
                
                // Add resizer div
                const resizer = document.createElement('div');
                resizer.className = 'resizer';
                th.appendChild(resizer);
                
                let startX, startWidth;
                
                resizer.addEventListener('mousedown', function(e) {
                    startX = e.pageX;
                    startWidth = th.offsetWidth;
                    resizer.classList.add('resizing');
                    document.addEventListener('mousemove', onMouseMove);
                    document.addEventListener('mouseup', onMouseUp);
                    e.preventDefault();
                });
                
                function onMouseMove(e) {
                    const newWidth = startWidth + (e.pageX - startX);
                    if (newWidth > 30) {
                        th.style.width = newWidth + 'px';
                    }
                }
                
                function onMouseUp() {
                    resizer.classList.remove('resizing');
                    document.removeEventListener('mousemove', onMouseMove);
                    document.removeEventListener('mouseup', onMouseUp);
                    
                    // Save all column widths
                    const widths = {};
                    headers.forEach((h, i) => {
                        widths[i] = h.offsetWidth;
                    });
                    localStorage.setItem('setupColumnWidths', JSON.stringify(widths));
                }
            });
        }
    </script>
</head>
<body>
    <div class="header-container">
        <h1>Trading Daemon</h1>
        <span id="completed-at" class="meta" style="display: none; font-size: 0.8rem; color: #6e7681;">Last: <span id="last-run"></span></span>
    </div>
    
    <div class="main-container">
        <div class="card" style="flex-shrink: 0; flex: 0 0 auto;">
            <div class="controls">
                <button id="btn-run" onclick="triggerInference()" class="btn-primary">▶ Run</button>
                <span id="status-badge" class="status-badge idle">IDLE</span>
                <div class="auto-controls">
                    <label>Auto:</label>
                    <input id="input-interval" type="number" value="10" min="0">
                    <span style="font-size: 0.8rem;">m</span>
                    <button onclick="setAutoInterval()" class="btn-secondary">Set</button>
                </div>
            </div>
        </div>
        
        <div class="card">
            <div class="tab-nav">
                <button id="btn-analysis" class="tab-btn active" onclick="switchTab('analysis')">Analysis</button>
                <button id="btn-active" class="tab-btn" onclick="switchTab('active')">Active Setups</button>
            </div>
            
            <div id="tab-analysis" class="tab-content active">
                <div id="output-content" class="output-content">
                    <p style="color: #8b949e; font-style: italic;">Waiting for inference...</p>
                </div>
            </div>
            
            <div id="tab-active" class="tab-content">
                <div class="output-content" style="padding: 0;">
                    <table id="setups-table">
                        <thead>
                            <tr>
                                <th style="width: 50px;">Time</th>
                                <th style="width: 60px;">Symbol</th>
                                <th style="width: 50px;">Side</th>
                                <th style="width: 60px;">Entry</th>
                                <th style="width: 100px;">Status</th>
                                <th>Rules</th>
                            </tr>
                        </thead>
                        <tbody id="setups-body"></tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>
</body>
</html>
"""


@app.route("/")
def index():
    return HTML_TEMPLATE

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
    return jsonify(app_state.get_inference_snapshot())


@app.route("/api/inference", methods=["POST"])
def trigger_inference():
    logger.info("Received manual inference request")
    if app_state.is_inference_running():
        return jsonify({"error": "Inference already in progress"}), 409
    
    if _gemini_client is None:
        return jsonify({"error": "GeminiClient not configured"}), 503
    
    def run_inference_async():
        logger.info("DEBUG: Entered run_inference_async")
        try:
            # Construct context header
            now = datetime.now()
            time_str = now.strftime("%H:%M")
            price_str = f"{app_state.last_price:.2f}" if app_state.last_price else "Unknown"
            context = f"Current Time: {time_str}\nCurrent Price: {price_str}"
            
            app_state.start_inference(context=context)
            logger.info(f"Starting inference with context: {context.replace('\\n', ', ')}")
            logger.info("DEBUG: Calling _gemini_client.run_inference now...")
            result = _gemini_client.run_inference(context_header=context)
            logger.info("DEBUG: _gemini_client.run_inference returned")
            
            error_patterns = ["Error", "critical error", "ModelNotFoundError", "fetch failed", "Exception"]
            is_error = any(pattern in result for pattern in error_patterns)
            
            if is_error:
                app_state.fail_inference(result)
                logger.error(f"Inference failed (detected error keywords): {result[:500]}...")
            else:
                # Log the full raw result for debugging
                logger.info(f"Raw Gemini response:\n{result}")

                # Robust JSON extraction
                clean_json = ""
                json_match = re.search(r"```json\s*(.*?)```", result, re.DOTALL)
                if json_match:
                    clean_json = json_match.group(1).strip()
                else:
                    # Fallback: try to find start/end braces
                    start = result.find('{')
                    end = result.rfind('}') + 1
                    if start != -1 and end != -1:
                        clean_json = result[start:end]
                    else:
                        clean_json = result.replace("```json", "").replace("```", "").strip()

                # Use cleaned JSON for frontend display if possible
                display_result = clean_json if clean_json else result
                app_state.complete_inference(display_result)
                app_state.update_output(display_result)

                try:
                    from src.models import LLMResponse
                    data = json.loads(clean_json)
                    response = LLMResponse(**data)
                    app_state.trade_manager.add_setups(response.setups)
                except Exception as parse_err:
                     logger.error(f"Failed to parse manual inference JSON: {parse_err}")
                     logger.debug(f"Attempted to parse: {clean_json if 'clean_json' in locals() else 'N/A'}")

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
    return jsonify({
        "interval": app_state.get_auto_inference_interval()
    })


@app.route("/api/auto-inference", methods=["POST"])
def set_auto_inference():
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
