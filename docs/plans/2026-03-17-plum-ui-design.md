# Plum Unified Dashboard - Design Document

## Overview

A single-page web application providing unified control and monitoring for all projects in the Plum monorepo. The dashboard features a master tab system, dockable panels, and reusable service control widgets.

## Goals

- Unified UI for all Plum projects with consistent look and feel
- Centralized monitoring of all services (PostgreSQL, Ollama, aiserver, rp, etc.)
- Quick service restart controls
- Log viewing from a central location
- Minimal dependencies and HTTP overhead
- Dockable panel layout for flexibility

## Design Requirements

### Visual Design

- **Typography**: Big text, monospace fonts
- **Colors**: Bold colors with high contrast (green for running, red for stopped, yellow for restart needed)
- **Layout**: No rounded corners, minimal whitespace, no decorative elements
- **Tech Stack**: Plain HTML/CSS/vanilla JavaScript (no frameworks)

### Architecture

**Master Tab System:**
- Master Dashboard: Overview of all services
- rp Tab: rp UI with service panels docked around edges
- Expandable to other projects

**Service Control Widget (Reusable):**
Each service displays:
1. Service name (bold, large)
2. Status indicator (● RUNNING/STOPPED/RESTART NEEDED)
3. Restart button
4. Log display (tail of log file, monospace)

### Master Dashboard Layout

Grid of service cards (2x2 initially):
- PostgreSQL
- Ollama
- aiserver
- rp

Each card shows current status, restart button, and last N lines from `/plum/logs/{service}.log`.

### rp Tab Layout

```
┌─────────────────────────────────┐
│ Status Panel (docked north)     │  ← All services status + restart buttons
├─────────────────────────────────┤
│                                 │
│     rp UI (iframe/embed)        │  ← Main area: rp roleplay chat UI
│                                 │
├─────────────────────────────────┤
│ rp Logs Panel (docked south)    │  ← rp service logs
└─────────────────────────────────┘
```

Future: east/west panels for additional services, tabbed log views.

## Implementation Details

### Backend Requirements

1. **Log File Access**: `/api/logs/{service}`
   - Reads from `/d/prg/plum/logs/{service}.log`
   - Returns last N lines (JSON)

2. **Service Status**: `/api/services/{service}/status`
   - Checks if process is running
   - Returns: `{ status: "running" | "stopped", uptime: "..." }`

3. **Service Control**: POST `/api/services/{service}/restart`
   - Executes restart script for service
   - Returns: `{ status: "restarting" }`

### Frontend Structure

```
projects/front/
├── index.html              # Single HTML file with inline CSS
├── app.js                  # Vanilla JS app logic
├── styles.css              # Embedded or inline
└── README.md
```

**No external dependencies.** Plain HTML, CSS, and ES6 JavaScript.

### Log Polling Strategy

- Poll `/api/logs/{service}` every 2-3 seconds
- Display last 20 lines per log
- Monospace font, dark background, light text
- Auto-scroll when new logs arrive

### Docking System

Use CSS Grid/Flexbox:
- North panel: Fixed height, full width
- South panel: Fixed height, full width
- Centre: Remaining space (iframe for rp UI)
- East/West: Optional side panels (future)

## Tech Stack

- **Frontend**: HTML5 + CSS3 + ES6 JavaScript
- **Layout**: CSS Grid + Flexbox
- **Backend**: Depends on aiserver (Flask/FastAPI)
- **Logs**: Read from disk
- **No build tools**: Direct file serving

## Success Criteria

1. Master dashboard displays all services with current status
2. Restart buttons work and update status immediately
3. Logs update in real-time (via polling)
4. rp tab embeds rp UI with service panels docked
5. All controls visible and clickable on single screen
6. No external JS libraries or frameworks
7. Bold colors, big text, monospace fonts throughout
