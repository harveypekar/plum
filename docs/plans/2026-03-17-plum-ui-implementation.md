# Plum Unified Dashboard Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a unified control dashboard for Plum monorepo with master tab system, service status monitoring, log viewing, and restart controls.

**Architecture:** Backend provides REST API endpoints for service status, logs, and restart commands. Frontend is a single-page vanilla JS app with master tab system and dockable panels. Master dashboard shows all services in a grid; rp tab embeds rp UI with service panels docked.

**Tech Stack:**
- Frontend: HTML5 + CSS3 + ES6 JavaScript (vanilla, no frameworks)
- Backend: Flask/FastAPI (integrate with aiserver)
- Layout: CSS Grid/Flexbox
- Logs: Read from `/d/prg/plum/logs/` directory

---

## PHASE 1: PROJECT SETUP

### Task 1: Create project directory structure

**Files:**
- Create: `projects/front/index.html`
- Create: `projects/front/app.js`
- Create: `projects/front/styles.css`
- Create: `projects/front/README.md`

**Steps:**

1. Create directory structure:
```bash
cd /d/prg/plum/projects
mkdir -p front
cd front
touch index.html app.js styles.css README.md
```

2. Create initial README.md:
```markdown
# Plum Unified Dashboard

Unified control panel for Plum monorepo projects.

## Features

- Master dashboard: service status overview
- rp tab: roleplay UI with service controls
- Service restart controls
- Real-time log viewing
- Plain HTML/CSS/JS (no frameworks)

## Quick Start

```bash
# Navigate to plum root
cd /d/prg/plum

# Start aiserver (which serves front/)
cd projects/aiserver
source .venv/bin/activate
python main.py
```

UI at: `http://localhost:8080/front/`

## Architecture

- `/front/index.html` - Main HTML structure
- `/front/app.js` - Client-side logic
- `/front/styles.css` - All styling
- Backend API endpoints (in aiserver)
```

3. Commit:
```bash
cd /d/prg/plum
git add projects/front/
git commit -m "chore: initialize front project structure"
```

---

## PHASE 2: BACKEND API ENDPOINTS

### Task 2: Create `/api/logs/{service}` endpoint

**Files:**
- Modify: `projects/aiserver/main.py` (or plugin file)
- Create: `projects/front/api_logs.py` (helper module, if needed)

**Steps:**

1. In aiserver main.py (or create a new route module for front), add endpoint:

```python
from pathlib import Path
import os

@app.get("/api/logs/{service}")
async def get_service_logs(service: str, lines: int = 20):
    """Get last N lines from service log file."""
    log_path = Path("/d/prg/plum/logs") / f"{service}.log"

    if not log_path.exists():
        return {"error": f"Log file not found: {service}", "lines": []}

    try:
        with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
            all_lines = f.readlines()

        # Get last N lines
        tail_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
        tail_text = ''.join(tail_lines).strip()

        return {
            "service": service,
            "lines": tail_text.split('\n') if tail_text else [],
            "total_lines": len(all_lines),
            "timestamp": time.time()
        }
    except Exception as e:
        return {"error": str(e), "lines": []}
```

2. Test manually:
```bash
curl http://localhost:8080/api/logs/rp?lines=10
```
Expected: JSON with last 10 lines from `/d/prg/plum/logs/rp.log`

3. Commit:
```bash
git add projects/aiserver/main.py
git commit -m "feat: add /api/logs/{service} endpoint"
```

---

### Task 3: Create `/api/services/{service}/status` endpoint

**Files:**
- Modify: `projects/aiserver/main.py`

**Steps:**

1. Add helper to detect if service is running:

```python
import subprocess
import psutil

def get_service_status(service: str):
    """Check if a service is running.

    For now, use process name matching.
    PostgreSQL: process 'postgres'
    Ollama: process 'ollama'
    aiserver: process 'python' with 'main.py'
    rp: plugin (check via aiserver health)
    """
    status_map = {
        "postgresql": "postgres",
        "ollama": "ollama",
        "aiserver": "python",  # Would need more specific matching
    }

    process_name = status_map.get(service)
    if not process_name:
        return {"status": "unknown", "message": f"Unknown service: {service}"}

    # Check if process is running
    running = False
    for proc in psutil.process_iter(['name']):
        if process_name.lower() in proc.name().lower():
            running = True
            break

    return {
        "service": service,
        "status": "running" if running else "stopped",
        "timestamp": time.time()
    }

@app.get("/api/services/{service}/status")
async def service_status(service: str):
    """Get service status (running/stopped)."""
    return get_service_status(service)
```

2. Test:
```bash
curl http://localhost:8080/api/services/ollama/status
curl http://localhost:8080/api/services/postgresql/status
```
Expected: `{"service": "ollama", "status": "running"|"stopped", ...}`

3. Commit:
```bash
git add projects/aiserver/main.py
git commit -m "feat: add /api/services/{service}/status endpoint"
```

---

### Task 4: Create `/api/services/{service}/restart` endpoint

**Files:**
- Modify: `projects/aiserver/main.py`
- Create: `projects/front/restart_scripts.sh` (optional, for restart logic)

**Steps:**

1. Add restart handler (simplified for MVP):

```python
from typing import Dict

RESTART_COMMANDS = {
    "rp": "cd /d/prg/plum/projects/aiserver && pkill -f 'python main.py' && sleep 2 && python main.py &",
    "ollama": "pkill ollama || true && sleep 1 && ollama serve &",
    "postgresql": "# PostgreSQL restart (platform-specific, skip for MVP)",
}

@app.post("/api/services/{service}/restart")
async def restart_service(service: str):
    """Restart a service (send restart command)."""
    if service not in RESTART_COMMANDS:
        return {"error": f"Unknown service: {service}", "status": "failed"}

    cmd = RESTART_COMMANDS[service]
    if not cmd or cmd.startswith("#"):
        return {"error": f"No restart command for {service}", "status": "skipped"}

    try:
        # Execute async (don't wait for completion)
        subprocess.Popen(cmd, shell=True)
        return {"service": service, "status": "restarting", "timestamp": time.time()}
    except Exception as e:
        return {"error": str(e), "status": "failed"}
```

2. Test:
```bash
curl -X POST http://localhost:8080/api/services/ollama/restart
```
Expected: `{"service": "ollama", "status": "restarting", ...}`

3. Commit:
```bash
git add projects/aiserver/main.py
git commit -m "feat: add /api/services/{service}/restart endpoint"
```

---

## PHASE 3: FRONTEND HTML & STYLING

### Task 5: Create base HTML structure with master dashboard layout

**Files:**
- Create: `projects/front/index.html`

**Steps:**

1. Create index.html with inline CSS:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Plum Dashboard</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            background: #000;
            color: #0f0;
            font-family: monospace;
            font-size: 18px;
            line-height: 1.4;
            padding: 20px;
        }

        .tabs {
            display: flex;
            gap: 20px;
            margin-bottom: 20px;
            border-bottom: 3px solid #0f0;
            padding-bottom: 10px;
        }

        .tab-btn {
            background: #000;
            color: #0f0;
            border: 2px solid #0f0;
            padding: 10px 20px;
            font-size: 18px;
            font-family: monospace;
            cursor: pointer;
            font-weight: bold;
        }

        .tab-btn:hover {
            background: #0f0;
            color: #000;
        }

        .tab-btn.active {
            background: #0f0;
            color: #000;
        }

        .tab-content {
            display: none;
        }

        .tab-content.active {
            display: block;
        }

        /* Master Dashboard Grid */
        .master-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
        }

        .service-card {
            border: 3px solid #0f0;
            padding: 20px;
            background: #001a00;
        }

        .service-card.stopped {
            border-color: #f00;
        }

        .service-card.restart-needed {
            border-color: #ff0;
        }

        .service-name {
            font-size: 24px;
            font-weight: bold;
            margin-bottom: 10px;
        }

        .status-indicator {
            font-size: 20px;
            margin-bottom: 15px;
        }

        .status-running {
            color: #0f0;
        }

        .status-stopped {
            color: #f00;
        }

        .status-restart-needed {
            color: #ff0;
        }

        .restart-btn {
            background: #0f0;
            color: #000;
            border: none;
            padding: 10px 15px;
            font-size: 16px;
            font-family: monospace;
            font-weight: bold;
            cursor: pointer;
            margin-bottom: 15px;
        }

        .restart-btn:hover {
            background: #f0f;
        }

        .restart-btn.restarting {
            background: #ff0;
            cursor: not-allowed;
        }

        .logs-section {
            margin-top: 15px;
            border-top: 2px solid #0f0;
            padding-top: 10px;
        }

        .logs-label {
            font-weight: bold;
            margin-bottom: 5px;
        }

        .logs {
            background: #000;
            color: #0f0;
            padding: 10px;
            height: 150px;
            overflow-y: auto;
            font-size: 14px;
            line-height: 1.2;
        }

        .log-line {
            white-space: pre-wrap;
            word-wrap: break-word;
        }

        /* RP Tab Layout */
        .rp-container {
            display: grid;
            grid-template-rows: auto 1fr auto;
            height: calc(100vh - 200px);
        }

        .north-panel {
            border: 3px solid #0f0;
            padding: 15px;
            margin-bottom: 20px;
            background: #001a00;
        }

        .centre-panel {
            border: 3px solid #0f0;
            padding: 0;
            margin-bottom: 20px;
            background: #001a00;
            overflow: hidden;
        }

        .centre-panel iframe {
            width: 100%;
            height: 100%;
            border: none;
        }

        .south-panel {
            border: 3px solid #0f0;
            padding: 15px;
            background: #001a00;
        }

        .panel-label {
            font-weight: bold;
            margin-bottom: 10px;
        }

        .service-status-inline {
            display: inline-block;
            margin-right: 30px;
            margin-bottom: 10px;
        }

        .service-status-inline .status-indicator {
            display: inline;
            margin-right: 5px;
        }

        .inline-restart-btn {
            background: #0f0;
            color: #000;
            border: none;
            padding: 5px 10px;
            font-size: 14px;
            font-family: monospace;
            font-weight: bold;
            cursor: pointer;
            margin-left: 10px;
        }

        .inline-restart-btn:hover {
            background: #f0f;
        }

        .inline-restart-btn.restarting {
            background: #ff0;
            cursor: not-allowed;
        }
    </style>
</head>
<body>
    <div class="tabs">
        <button class="tab-btn active" data-tab="master">Master</button>
        <button class="tab-btn" data-tab="rp">rp</button>
    </div>

    <!-- Master Dashboard Tab -->
    <div id="master" class="tab-content active">
        <div class="master-grid">
            <div class="service-card" id="service-postgresql">
                <div class="service-name">PostgreSQL</div>
                <div class="status-indicator status-running">● RUNNING</div>
                <button class="restart-btn">RESTART</button>
                <div class="logs-section">
                    <div class="logs-label">Logs:</div>
                    <div class="logs" id="logs-postgresql">Loading...</div>
                </div>
            </div>

            <div class="service-card" id="service-ollama">
                <div class="service-name">Ollama</div>
                <div class="status-indicator status-stopped">● STOPPED</div>
                <button class="restart-btn">RESTART</button>
                <div class="logs-section">
                    <div class="logs-label">Logs:</div>
                    <div class="logs" id="logs-ollama">Loading...</div>
                </div>
            </div>

            <div class="service-card" id="service-aiserver">
                <div class="service-name">aiserver</div>
                <div class="status-indicator status-running">● RUNNING</div>
                <button class="restart-btn">RESTART</button>
                <div class="logs-section">
                    <div class="logs-label">Logs:</div>
                    <div class="logs" id="logs-aiserver">Loading...</div>
                </div>
            </div>

            <div class="service-card" id="service-rp">
                <div class="service-name">rp</div>
                <div class="status-indicator status-running">● RUNNING</div>
                <button class="restart-btn">RESTART</button>
                <div class="logs-section">
                    <div class="logs-label">Logs:</div>
                    <div class="logs" id="logs-rp">Loading...</div>
                </div>
            </div>
        </div>
    </div>

    <!-- rp Tab -->
    <div id="rp" class="tab-content">
        <div class="rp-container">
            <!-- North Panel: Service Status -->
            <div class="north-panel">
                <div class="panel-label">Services:</div>
                <div class="service-status-inline">
                    <span class="status-indicator status-running">● PostgreSQL</span>
                    <button class="inline-restart-btn">RESTART</button>
                </div>
                <div class="service-status-inline">
                    <span class="status-indicator status-stopped">● Ollama</span>
                    <button class="inline-restart-btn">RESTART</button>
                </div>
                <div class="service-status-inline">
                    <span class="status-indicator status-running">● aiserver</span>
                    <button class="inline-restart-btn">RESTART</button>
                </div>
            </div>

            <!-- Centre Panel: rp UI iframe -->
            <div class="centre-panel">
                <iframe src="/rp/" title="rp UI"></iframe>
            </div>

            <!-- South Panel: rp Logs -->
            <div class="south-panel">
                <div class="panel-label">rp Logs:</div>
                <div class="logs" id="logs-rp-tab">Loading...</div>
            </div>
        </div>
    </div>

    <script src="/front/app.js"></script>
</body>
</html>
```

2. Test in browser:
```
http://localhost:8080/front/
```
Expected: Master tab visible with service cards layout, green/red borders based on status.

3. Commit:
```bash
cd /d/prg/plum
git add projects/front/index.html
git commit -m "feat: add base HTML structure with master dashboard layout"
```

---

## PHASE 4: FRONTEND JAVASCRIPT LOGIC

### Task 6: Implement tab switching and basic app structure

**Files:**
- Create: `projects/front/app.js`

**Steps:**

1. Create app.js with tab switching:

```javascript
// App state
const app = {
    currentTab: 'master',
    pollIntervals: {},

    init() {
        this.setupTabButtons();
        this.setupRestartButtons();
        this.startPolling();
    },

    setupTabButtons() {
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                this.switchTab(btn.dataset.tab);
            });
        });
    },

    switchTab(tabName) {
        // Hide all tabs
        document.querySelectorAll('.tab-content').forEach(tab => {
            tab.classList.remove('active');
        });

        // Deactivate all buttons
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.classList.remove('active');
        });

        // Show selected tab
        document.getElementById(tabName).classList.add('active');

        // Activate selected button
        document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');

        this.currentTab = tabName;
    },

    setupRestartButtons() {
        // Master dashboard restart buttons
        document.querySelectorAll('#master .restart-btn').forEach((btn, idx) => {
            const services = ['postgresql', 'ollama', 'aiserver', 'rp'];
            const service = services[idx];

            btn.addEventListener('click', () => {
                this.restartService(service, btn);
            });
        });

        // RP tab inline restart buttons
        document.querySelectorAll('#rp .inline-restart-btn').forEach((btn, idx) => {
            const services = ['postgresql', 'ollama', 'aiserver'];
            const service = services[idx];

            btn.addEventListener('click', () => {
                this.restartService(service, btn);
            });
        });
    },

    async restartService(service, btnElement) {
        btnElement.textContent = 'RESTARTING...';
        btnElement.classList.add('restarting');
        btnElement.disabled = true;

        try {
            const response = await fetch(`/api/services/${service}/restart`, {
                method: 'POST'
            });
            const data = await response.json();

            if (data.status === 'restarting') {
                // Wait 3 seconds then poll status
                setTimeout(() => {
                    this.pollServiceStatus(service);
                }, 3000);
            }
        } catch (error) {
            console.error('Restart failed:', error);
        } finally {
            btnElement.textContent = 'RESTART';
            btnElement.classList.remove('restarting');
            btnElement.disabled = false;
        }
    },

    startPolling() {
        // Poll status every 2 seconds
        setInterval(() => {
            this.pollAllServices();
        }, 2000);

        // Poll logs every 3 seconds
        setInterval(() => {
            this.pollAllLogs();
        }, 3000);
    },

    async pollAllServices() {
        const services = ['postgresql', 'ollama', 'aiserver', 'rp'];
        for (const service of services) {
            await this.pollServiceStatus(service);
        }
    },

    async pollServiceStatus(service) {
        try {
            const response = await fetch(`/api/services/${service}/status`);
            const data = await response.json();
            this.updateServiceStatus(service, data.status);
        } catch (error) {
            console.error(`Failed to poll ${service}:`, error);
        }
    },

    updateServiceStatus(service, status) {
        const card = document.getElementById(`service-${service}`);
        if (!card) return;

        const indicator = card.querySelector('.status-indicator');
        const classToRemove = ['status-running', 'status-stopped', 'status-restart-needed']
            .find(cls => indicator.classList.contains(cls));

        if (classToRemove) indicator.classList.remove(classToRemove);

        const newClass = status === 'running' ? 'status-running' : 'status-stopped';
        indicator.classList.add(newClass);

        const statusText = status === 'running' ? '● RUNNING' : '● STOPPED';
        indicator.textContent = statusText;

        // Update card border color
        card.classList.remove('stopped', 'restart-needed');
        if (status === 'stopped') {
            card.classList.add('stopped');
        }
    },

    async pollAllLogs() {
        const services = ['postgresql', 'ollama', 'aiserver', 'rp'];
        for (const service of services) {
            await this.pollLogs(service);
        }
    },

    async pollLogs(service) {
        try {
            const response = await fetch(`/api/logs/${service}?lines=20`);
            const data = await response.json();
            this.updateLogs(service, data.lines || []);
        } catch (error) {
            console.error(`Failed to poll logs for ${service}:`, error);
        }
    },

    updateLogs(service, lines) {
        const logsDiv = document.getElementById(`logs-${service}`);
        const logsDivTab = document.getElementById(`logs-${service}-tab`);

        const html = lines.map(line =>
            `<div class="log-line">${this.escapeHtml(line)}</div>`
        ).join('');

        if (logsDiv) logsDiv.innerHTML = html || 'No logs';
        if (logsDivTab) logsDivTab.innerHTML = html || 'No logs';

        // Auto-scroll to bottom
        if (logsDiv) logsDiv.scrollTop = logsDiv.scrollHeight;
        if (logsDivTab) logsDivTab.scrollTop = logsDivTab.scrollHeight;
    },

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
};

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    app.init();
});
```

2. Test in browser:
```
http://localhost:8080/front/
```
Expected: Tab switching works, logs update every 3 seconds, status updates every 2 seconds.

3. Commit:
```bash
cd /d/prg/plum
git add projects/front/app.js
git commit -m "feat: implement tab switching and service polling logic"
```

---

## PHASE 5: INTEGRATION & TESTING

### Task 7: Mount front static files in aiserver

**Files:**
- Modify: `projects/aiserver/main.py`

**Steps:**

1. Add static file serving:

```python
from fastapi.staticfiles import StaticFiles
import os

# Mount /front/ to serve static files
front_path = os.path.join(os.path.dirname(__file__), '../front')
if os.path.exists(front_path):
    app.mount('/front', StaticFiles(directory=front_path), name='front')
```

2. Test:
```bash
curl http://localhost:8080/front/
```
Expected: HTML content returned

3. Open browser:
```
http://localhost:8080/front/
```
Expected: Page loads, tabs work, master dashboard visible.

4. Commit:
```bash
git add projects/aiserver/main.py
git commit -m "feat: mount /front/ static files in aiserver"
```

---

### Task 8: Create log files for testing

**Files:**
- Create: `/d/prg/plum/logs/postgresql.log`
- Create: `/d/prg/plum/logs/ollama.log`
- Create: `/d/prg/plum/logs/aiserver.log`
- Create: `/d/prg/plum/logs/rp.log`

**Steps:**

1. Create log directory and test files:

```bash
mkdir -p /d/prg/plum/logs

echo "2026-03-17 10:00:00 - PostgreSQL started" >> /d/prg/plum/logs/postgresql.log
echo "2026-03-17 10:00:01 - Connection pool initialized" >> /d/prg/plum/logs/postgresql.log

echo "2026-03-17 10:00:05 - Ollama service starting" >> /d/prg/plum/logs/ollama.log
echo "2026-03-17 10:00:06 - Listening on :11434" >> /d/prg/plum/logs/ollama.log

echo "2026-03-17 10:00:10 - aiserver started" >> /d/prg/plum/logs/aiserver.log
echo "2026-03-17 10:00:11 - Loading plugins..." >> /d/prg/plum/logs/aiserver.log
echo "2026-03-17 10:00:12 - Plugin rp loaded" >> /d/prg/plum/logs/aiserver.log

echo "2026-03-17 10:00:15 - rp plugin initialized" >> /d/prg/plum/logs/rp.log
echo "2026-03-17 10:00:16 - Database schema created" >> /d/prg/plum/logs/rp.log
```

2. Verify:
```bash
curl http://localhost:8080/api/logs/rp?lines=5
```
Expected: Last 5 lines from rp.log in JSON format.

3. Commit:
```bash
cd /d/prg/plum
git add logs/
git commit -m "chore: create test log files"
```

---

### Task 9: End-to-end testing and refinement

**Files:**
- No new files

**Steps:**

1. Open dashboard in browser:
```
http://localhost:8080/front/
```

2. Test master dashboard:
   - [ ] Service cards display
   - [ ] Status indicators show (green/red)
   - [ ] Logs update every 3 seconds
   - [ ] Restart buttons are clickable

3. Test rp tab:
   - [ ] Click "rp" tab
   - [ ] iframe loads rp UI
   - [ ] Service status panel shows at top
   - [ ] Logs panel shows at bottom
   - [ ] All interactive

4. Test tab switching:
   - [ ] Switch between master and rp tabs
   - [ ] Content updates correctly
   - [ ] Polling continues in background

5. Test API endpoints:
```bash
curl http://localhost:8080/api/services/ollama/status
curl http://localhost:8080/api/logs/postgresql?lines=10
curl -X POST http://localhost:8080/api/services/rp/restart
```

6. Fix any issues found.

7. Commit:
```bash
cd /d/prg/plum
git add projects/front/
git commit -m "test: verify end-to-end dashboard functionality"
```

---

## PHASE 6: DOCUMENTATION & CLEANUP

### Task 10: Update README and add developer docs

**Files:**
- Modify: `projects/front/README.md`

**Steps:**

1. Expand README.md:

```markdown
# Plum Unified Dashboard

Unified control panel for Plum monorepo projects. Master tab shows all services; project tabs (rp, etc.) show service panels with embedded project UI.

## Architecture

### Frontend (vanilla JS)
- `index.html` - Single-page app structure (tabs, service cards, panels)
- `app.js` - Client logic (tab switching, polling, restart)
- Inline CSS (monospace, bold colors, no frameworks)

### Backend (Flask/FastAPI)
- `/api/logs/{service}?lines=20` - Get last N lines from log file
- `/api/services/{service}/status` - Check if service is running
- `/api/services/{service}/restart` - Restart a service (POST)

### Log Files
```
/d/prg/plum/logs/
├── postgresql.log
├── ollama.log
├── aiserver.log
└── rp.log
```

## Running

1. Start aiserver (serves /front/ and API):
```bash
cd projects/aiserver
source .venv/bin/activate
python main.py
```

2. Open browser:
```
http://localhost:8080/front/
```

## Design Decisions

- **Vanilla JS**: No frameworks, minimal dependencies
- **Polling**: Simple polling (2-3s intervals) instead of WebSockets
- **Log Tailing**: Read last N lines from disk files (simple, no log aggregation)
- **Inline CSS**: Single HTML file for simplicity
- **Monospace font**: Terminal-like feel, matches Plum aesthetic

## Future Enhancements

- [ ] WebSocket streaming for logs (real-time)
- [ ] East/west dockable panels
- [ ] Tabbed log viewers
- [ ] Other project tabs (coach, backup, etc.)
- [ ] Service dependency management
```

2. Commit:
```bash
cd /d/prg/plum
git add projects/front/README.md
git commit -m "docs: add comprehensive README for front project"
```

---

## Summary

| Phase | Task | Files | Effort |
|-------|------|-------|--------|
| 1 | Project setup | 4 files | 5 min |
| 2 | Backend APIs | 1 modify | 15 min |
| 3 | Frontend HTML | 1 create | 20 min |
| 4 | Frontend JS | 1 create | 20 min |
| 5 | Integration | 3 steps | 15 min |
| 6 | Docs | 1 modify | 10 min |

**Total: ~85 minutes** (10 focused tasks)

