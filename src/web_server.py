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
            fetch('/api/inference?t=' + Date.now())
                .then(r => r.json())
                .then(data => {
                    document.getElementById('status-badge').className = 'status-badge ' + data.status;
                    document.getElementById('status-badge').textContent = data.status.toUpperCase();
                    
                    const isRunning = data.status === 'running';
                    const activeStrategy = data.strategy; // 'main' or 'alt' or null
                    
                    const btnRun = document.getElementById('btn-run');
                    if (btnRun) {
                        btnRun.disabled = isRunning;
                        if (isRunning && activeStrategy === 'main') {
                            btnRun.textContent = '⟳ Running...';
                        } else {
                            btnRun.textContent = '▶ Run';
                        }
                    }
                    
                    const btnAlt = document.getElementById('btn-run-alt');
                    if (btnAlt) {
                        btnAlt.disabled = isRunning;
                        if (isRunning && activeStrategy === 'alt') {
                            btnAlt.textContent = '⟳ Running...';
                        } else {
                            btnAlt.textContent = '⚡ Run Alt';
                        }
                    }

                    const output = document.getElementById('output-content');
                    
                    // Show analyzing state if running and we don't have a result yet (or if we want to overwrite old result)
                    if (isRunning) {
                         output.innerHTML = '<div style="padding: 2rem; text-align: center; color: #8b949e;"><div style="font-size: 2rem; margin-bottom: 1rem;">🧠</div><div>AI is analyzing market structure...</div><div style="font-size: 0.8rem; margin-top: 0.5rem;">Strategy: ' + (activeStrategy || 'Main').toUpperCase() + '</div></div>';
                    } else if (data.result) {
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
                    
                    // Update active setups table
                    const setups = data.active_setups || [];
                    const tbody = document.getElementById('setups-body');
                    if (tbody) {
                        tbody.innerHTML = setups.map(s => {
                            // Extract HH:MM from created_at string if possible, else use as is
                            let timeStr = '-';
                            if (s.created_at) {
                                try {
                                    const date = new Date(s.created_at);
                                    timeStr = date.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
                                } catch (e) { timeStr = s.created_at; }
                            }

                            const rules = s.rules_text || '-';
                            const statusColor = s.status === 'NEW' ? '#2f81f7' : 
                                              s.status === 'TRIGGERED' ? '#3fb950' : 
                                              s.status === 'STOPPED' ? '#f85149' : '#8b949e';
                            
                            const directionColor = s.direction === 'LONG' ? '#3fb950' : '#f85149';
                            
                            return `<tr>
                                <td>${timeStr}</td>
                                <td style="color: ${directionColor}">${s.symbol}</td>
                                <td>${s.direction}</td>
                                <td>${s.entry.price}</td>
                                <td><span style="color: ${statusColor}">${s.status}</span></td>
                                <td style="white-space: nowrap;" title="${rules}">${rules}</td>
                            </tr>`;
                        }).join('');
                    }

                    document.getElementById('last-run').textContent = data.completed_at || '-';
                    document.getElementById('completed-at').style.display = data.completed_at ? 'inline' : 'none';
                    
                });
        }
        
        function triggerInference(strategy) { 
            strategy = strategy || 'main';
            const btnId = strategy === 'main' ? 'btn-run' : 'btn-run-alt';
            const btn = document.getElementById(btnId);
            
            // Optimistic UI update
            if (btn) {
                btn.textContent = 'Starting...';
                btn.disabled = true;
            }
            
            console.log('Triggering inference with strategy:', strategy);
            fetch('/api/inference', { 
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ strategy: strategy }) 
            })
                .then(r => {
                    console.log('Inference triggered, status:', r.status);
                    if (!r.ok) return r.text().then(t => { throw new Error(t) });
                    return r;
                })
                .then(updateStatus)
                .catch(e => {
                    console.error('Trigger error:', e);
                    alert('Failed to trigger inference: ' + e.message);
                    // Reset buttons if failed (updateStatus handles success/running)
                    if (btn) {
                        btn.disabled = false;
                        btn.textContent = strategy === 'main' ? '▶ Run' : '⚡ Run Alt';
                    }
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
            checkLiveStatus();
            setInterval(updateStatus, 2000); // Poll inference status every 2s
            setInterval(checkLiveStatus, 1000); // Poll live data every 1s
            initColumnResize();
        };

        function checkLiveStatus() {
            fetch('/api/status?t=' + Date.now())
                .then(r => r.json())
                .then(data => {
                    if (data.current_time) document.getElementById('live-time').textContent = data.current_time;
                    if (data.current_price) document.getElementById('live-price').textContent = Number(data.current_price).toFixed(2);
                })
                .catch(e => console.error('Live status error:', e));
        }
        
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
        <div style="display: flex; gap: 1.5rem; align-items: center; font-size: 0.9rem;">
            <div style="display: flex; gap: 0.5rem;">
                <span style="color: #8b949e;">NY Time:</span>
                <span id="live-time" style="font-family: monospace; color: #e6edf3;">--:--:--</span>
            </div>
            <div style="display: flex; gap: 0.5rem;">
                <span style="color: #8b949e;">Price:</span>
                <span id="live-price" style="font-family: monospace; color: #58a6ff; font-weight: bold;">0.00</span>
            </div>
            <span id="completed-at" style="display: none; color: #6e7681; border-left: 1px solid #30363d; padding-left: 1.5rem;">
                Last Run: <span id="last-run"></span>
            </span>
        </div>
    </div>
    
    <div class="main-container">
        <div class="card" style="flex-shrink: 0; flex: 0 0 auto;">
            <div class="controls">
                <button id="btn-run" onclick="triggerInference('main')" class="btn-primary">▶ Run</button>
                <button id="btn-run-alt" onclick="triggerInference('alt')" class="btn-secondary">⚡ Run Alt</button>
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
    
    # Get strategy from query or body (support both for flexibility)
    strategy = request.args.get("strategy")
    if not strategy:
        data = request.get_json(silent=True) or {}
        strategy = data.get("strategy", "main")
        
    logger.info(f"Strategy selected: {strategy}")

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
            
            # Select prompt file based on strategy
            prompt_file = "prompts/user-prompt-alt.md" if strategy == "alt" else None
            # Note: None defaults to main prompt in GeminiClient
            
            context_prefix = f"Strategy: {strategy.upper()}\n{context}"
            
            app_state.start_inference(context=context_prefix, strategy=strategy)
            logger.info(f"Starting inference with context: {context_prefix.replace('\\n', ', ')}")
            
            logger.info(f"DEBUG: Calling _gemini_client.run_inference with strategy={strategy}...")
            result = _gemini_client.run_inference(context_header=context, prompt_path=prompt_file)
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
