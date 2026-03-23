const SERVICES = ['postgresql', 'ollama', 'aiserver', 'rp'];
const POLL_STATUS_MS = 2000;
const POLL_LOGS_MS = 3000;

const DOCK_STORAGE_KEY_MASTER = 'plum-dock-state-master';
const DOCK_STORAGE_KEY_RP = 'plum-dock-state-rp';

// ===== Panel definitions =====
// Each panel has an id, title, and a render function that returns DOM content.

const PANELS = {
    services: {
        id: 'services',
        title: 'Services',
        render() {
            const container = document.createElement('div');
            container.id = 'rp-status-bar';
            app.renderRpStatusBar(container);
            return container;
        },
    },
    'logs-aiserver': {
        id: 'logs-aiserver',
        title: 'aiserver',
        render() {
            const div = el('div', { class: 'logs', id: 'logs-aiserver-dock' }, 'Loading...');
            return div;
        },
    },
    'logs-ollama': {
        id: 'logs-ollama',
        title: 'ollama',
        render() {
            return el('div', { class: 'logs', id: 'logs-ollama-dock' }, 'Loading...');
        },
    },
    'logs-rp': {
        id: 'logs-rp',
        title: 'rp Logs',
        render() {
            return el('div', { class: 'logs', id: 'logs-rp-dock' }, 'Loading...');
        },
    },
    'logs-postgresql': {
        id: 'logs-postgresql',
        title: 'postgresql',
        render() {
            return el('div', { class: 'logs', id: 'logs-postgresql-dock' }, 'Loading...');
        },
    },
    'rp-browser': {
        id: 'rp-browser',
        title: 'RP Browser',
        render() { return el('div', { id: 'rp-browser-root' }, 'Loading...'); },
    },
    'rp-scene-state': {
        id: 'rp-scene-state',
        title: 'Scene State',
        render() { return el('div', { id: 'rp-scene-state-root' }, 'Loading...'); },
    },
    'rp-under-hood': {
        id: 'rp-under-hood',
        title: 'Under the Hood',
        render() { return el('div', { id: 'rp-under-hood-root' }, 'Loading...'); },
    },
};

const DEFAULT_LAYOUT_MASTER = {
    north: ['services'],
    south: ['logs-rp'],
    west: ['logs-aiserver'],
    east: ['logs-ollama'],
};

const DEFAULT_LAYOUT_RP = {
    north: ['services'],
    south: ['logs-rp', 'rp-scene-state', 'rp-under-hood'],
    west: ['rp-browser'],
    east: [],
};

// ===== DOM helper =====

function el(tag, attrs, children) {
    const e = document.createElement(tag);
    if (attrs) Object.entries(attrs).forEach(([k, v]) => {
        if (k === 'class') e.className = v;
        else if (k.startsWith('data-')) e.setAttribute(k, v);
        else e[k] = v;
    });
    if (typeof children === 'string') e.textContent = children;
    else if (Array.isArray(children)) children.forEach(c => e.appendChild(c));
    return e;
}


// ===== App (tabs, polling, master tab) =====

const app = {
    currentTab: 'master',

    init() {
        this.renderServiceCards();
        this.setupTabs();
        this.setupRestartButtons();
        dock.init();
        this.startPolling();
    },

    renderServiceCards() {
        const grid = document.getElementById('service-grid');
        SERVICES.forEach(s => {
            grid.appendChild(el('div', { class: 'service-card', id: `service-${s}` }, [
                el('div', { class: 'service-name' }, s),
                el('div', { class: 'status-indicator status-unknown' }, '\u25CF CHECKING...'),
                el('button', { class: 'restart-btn', 'data-service': s }, 'RESTART'),
                el('div', { class: 'logs-section' }, [
                    el('div', { class: 'logs-label' }, 'Logs:'),
                    el('div', { class: 'logs', id: `logs-${s}` }, 'Loading...'),
                ]),
            ]));
        });
    },

    renderRpStatusBar(container) {
        SERVICES.forEach(s => {
            container.appendChild(el('div', { class: 'service-status-inline', id: `rp-inline-${s}` }, [
                el('span', { class: 'status-indicator status-unknown' }, `\u25CF ${s}`),
                el('button', { class: 'inline-restart-btn', 'data-service': s }, 'RESTART'),
            ]));
        });
    },

    setupTabs() {
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', () => this.switchTab(btn.dataset.tab));
        });
    },

    switchTab(tabName) {
        document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        document.getElementById(tabName).classList.add('active');
        document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');
        this.currentTab = tabName;

        // Apply theme
        document.body.classList.toggle('theme-amber', tabName === 'rp');

        // Switch dock layout when entering rp tab
        if (tabName === 'rp') {
            dock.switchLayout(tabName);
        }
    },

    setupRestartButtons() {
        document.addEventListener('click', e => {
            const btn = e.target.closest('[data-service]');
            if (btn && (btn.classList.contains('restart-btn') || btn.classList.contains('inline-restart-btn'))) {
                this.restartService(btn.dataset.service, btn);
            }
        });
    },

    async restartService(service, btn) {
        btn.textContent = 'RESTARTING...';
        btn.classList.add('restarting');
        btn.disabled = true;
        try {
            const res = await fetch(`/api/services/${service}/restart`, { method: 'POST' });
            const data = await res.json();
            if (data.status === 'restarting') {
                setTimeout(() => this.pollServiceStatus(service), 3000);
            }
        } catch (err) {
            console.error('Restart failed:', err);
        } finally {
            btn.textContent = 'RESTART';
            btn.classList.remove('restarting');
            btn.disabled = false;
        }
    },

    startPolling() {
        this.pollAllServices();
        this.pollAllLogs();
        setInterval(() => this.pollAllServices(), POLL_STATUS_MS);
        setInterval(() => this.pollAllLogs(), POLL_LOGS_MS);
    },

    async pollAllServices() {
        await Promise.all(SERVICES.map(s => this.pollServiceStatus(s)));
    },

    async pollServiceStatus(service) {
        try {
            const res = await fetch(`/api/services/${service}/status`);
            const data = await res.json();
            this.updateServiceStatus(service, data.status);
        } catch {
            this.updateServiceStatus(service, 'unknown');
        }
    },

    updateServiceStatus(service, status) {
        const cls = status === 'running' ? 'status-running' : status === 'stopped' ? 'status-stopped' : 'status-unknown';
        const label = status === 'running' ? '\u25CF RUNNING' : status === 'stopped' ? '\u25CF STOPPED' : '\u25CF UNKNOWN';

        const card = document.getElementById(`service-${service}`);
        if (card) {
            const ind = card.querySelector('.status-indicator');
            ind.className = `status-indicator ${cls}`;
            ind.textContent = label;
            card.classList.toggle('stopped', status === 'stopped');
        }

        const inline = document.getElementById(`rp-inline-${service}`);
        if (inline) {
            const ind = inline.querySelector('.status-indicator');
            ind.className = `status-indicator ${cls}`;
            ind.textContent = `\u25CF ${service}`;
        }
    },

    async pollAllLogs() {
        await Promise.all(SERVICES.map(s => this.pollLogs(s)));
    },

    async pollLogs(service) {
        try {
            const res = await fetch(`/api/logs/${service}?lines=20`);
            const data = await res.json();
            this.updateLogs(service, data.lines || []);
        } catch { /* skip */ }
    },

    updateLogs(service, lines) {
        [document.getElementById(`logs-${service}`),
         document.getElementById(`logs-${service}-dock`),
        ].forEach(container => {
            if (!container) return;
            container.textContent = '';
            if (lines.length === 0) {
                container.appendChild(el('div', { class: 'log-line' }, 'No logs'));
            } else {
                lines.forEach(line => {
                    container.appendChild(el('div', { class: 'log-line' }, line));
                });
            }
            container.scrollTop = container.scrollHeight;
        });
    },
};


// ===== Dock System =====

const dock = {
    // Layout: which panel IDs are in each slot
    layout: null,
    sizes: { north: 60, south: 180, west: 250, east: 250 },
    collapsed: {},
    dragging: null,   // { panelId, fromSlot, ghost, overlay }
    resizing: null,
    currentStorageKey: DOCK_STORAGE_KEY_RP,

    init() {
        this.loadState(DOCK_STORAGE_KEY_RP, DEFAULT_LAYOUT_RP);
        this.render();
        this.setupResize();
    },

    // --- Per-tab layout switching ---

    switchLayout(tabName) {
        if (tabName === 'rp') {
            this.loadState(DOCK_STORAGE_KEY_RP, DEFAULT_LAYOUT_RP);
        } else {
            this.loadState(DOCK_STORAGE_KEY_MASTER, DEFAULT_LAYOUT_MASTER);
        }
        this.render();
    },

    // --- State ---

    loadState(storageKey, defaultLayout) {
        this.currentStorageKey = storageKey;
        this.layout = null;
        this.collapsed = {};
        try {
            const saved = JSON.parse(localStorage.getItem(storageKey));
            if (saved) {
                if (saved.layout) this.layout = saved.layout;
                if (saved.sizes) Object.assign(this.sizes, saved.sizes);
                if (saved.collapsed) this.collapsed = saved.collapsed;
            }
        } catch { /* ignore */ }
        if (!this.layout) this.layout = JSON.parse(JSON.stringify(defaultLayout));
    },

    saveState() {
        localStorage.setItem(this.currentStorageKey, JSON.stringify({
            layout: this.layout,
            sizes: this.sizes,
            collapsed: this.collapsed,
        }));
    },

    // --- Render entire dock from layout state ---

    render() {
        const root = document.getElementById('dock-layout');
        root.textContent = '';

        const hasNorth = this.layout.north.length > 0;
        const hasSouth = this.layout.south.length > 0;
        const hasWest = this.layout.west.length > 0;
        const hasEast = this.layout.east.length > 0;

        // Build grid-template-rows
        const rows = [];
        if (hasNorth) {
            const sz = this.collapsed.north ? 30 : this.sizes.north;
            rows.push(sz + 'px', '4px');
        }
        rows.push('1fr');
        if (hasSouth) rows.push('4px', (this.collapsed.south ? 30 : this.sizes.south) + 'px');
        root.style.gridTemplateRows = rows.join(' ');

        // North slot
        if (hasNorth) {
            root.appendChild(this.renderSlot('north'));
            root.appendChild(this.makeHandle('h', 'north'));
        }

        // Middle row
        const middle = el('div', { class: 'dock-middle' });
        if (hasWest) {
            const w = this.collapsed.west ? 30 : this.sizes.west;
            const slot = this.renderSlot('west');
            slot.style.width = w + 'px';
            slot.style.flexShrink = '0';
            middle.appendChild(slot);
            middle.appendChild(this.makeHandle('v', 'west'));
        }

        // Center
        const center = el('div', { class: 'dock-center' });
        if (app.currentTab === 'rp' && typeof rpCenter !== 'undefined' && rpCenter && rpCenter.render) {
            center.appendChild(rpCenter.render());
        } else if (app.currentTab === 'rp') {
            center.appendChild(el('div', { style: 'padding: 20px; color: var(--accent);' }, 'RP Center - Loading...'));
        } else {
            center.appendChild(el('iframe', { src: '/rp/', title: 'rp UI' }));
        }
        // Drop overlay lives inside center
        center.appendChild(this.createDropOverlay());
        middle.appendChild(center);

        if (hasEast) {
            middle.appendChild(this.makeHandle('v', 'east'));
            const e = this.collapsed.east ? 30 : this.sizes.east;
            const slot = this.renderSlot('east');
            slot.style.width = e + 'px';
            slot.style.flexShrink = '0';
            middle.appendChild(slot);
        }
        root.appendChild(middle);

        // South slot
        if (hasSouth) {
            root.appendChild(this.makeHandle('h', 'south'));
            root.appendChild(this.renderSlot('south'));
        }
    },

    renderSlot(position) {
        const panelIds = this.layout[position];
        const slot = el('div', { class: `dock-slot dock-slot-${position}` });
        slot.setAttribute('data-slot', position);
        const isCollapsed = !!this.collapsed[position];

        panelIds.forEach(panelId => {
            const def = PANELS[panelId];
            if (!def) return;

            const header = el('div', { class: 'dock-panel-header' }, [
                el('span', { class: 'dock-panel-title' }, def.title),
                el('div', { class: 'dock-panel-controls' }, [
                    this.makeToggleBtn(position),
                ]),
            ]);

            // Drag start on header
            header.addEventListener('mousedown', e => {
                if (e.target.closest('.dock-toggle')) return;
                this.startDrag(e, panelId, position);
            });

            const body = el('div', { class: 'dock-panel-body' }, [def.render()]);
            const panel = el('div', {
                class: 'dock-panel' + (isCollapsed ? ' collapsed' : ''),
                id: `dock-panel-${panelId}`,
            }, [header, body]);

            slot.appendChild(panel);
        });

        return slot;
    },

    makeToggleBtn(position) {
        const isCollapsed = !!this.collapsed[position];
        const btn = el('button', { class: 'dock-toggle' }, isCollapsed ? '+' : '\u2013');
        btn.addEventListener('click', () => {
            this.collapsed[position] = !this.collapsed[position];
            this.saveState();
            this.render();
        });
        return btn;
    },

    makeHandle(dir, slot) {
        const handle = el('div', {
            class: `dock-handle dock-handle-${dir}`,
            'data-resize': slot,
        });
        return handle;
    },

    createDropOverlay() {
        const overlay = el('div', { class: 'dock-drop-overlay', id: 'dock-drop-overlay' });
        ['north', 'south', 'west', 'east'].forEach(zone => {
            const drop = el('div', { class: 'dock-drop-zone', 'data-zone': zone }, [
                el('span', { class: 'dock-drop-zone-label' }, zone),
            ]);
            drop.addEventListener('mouseenter', () => drop.classList.add('hover'));
            drop.addEventListener('mouseleave', () => drop.classList.remove('hover'));
            drop.addEventListener('mouseup', () => this.dropPanel(zone));
            overlay.appendChild(drop);
        });
        return overlay;
    },

    // --- Drag and Drop ---

    startDrag(e, panelId, fromSlot) {
        e.preventDefault();
        const ghost = el('div', { class: 'dock-drag-ghost' }, PANELS[panelId].title);
        ghost.style.left = e.clientX + 10 + 'px';
        ghost.style.top = e.clientY + 10 + 'px';
        document.body.appendChild(ghost);

        const layout = document.getElementById('dock-layout');
        layout.classList.add('dragging');

        const overlay = document.getElementById('dock-drop-overlay');
        if (overlay) overlay.classList.add('active');

        this.dragging = { panelId, fromSlot, ghost };

        const onMove = e => {
            ghost.style.left = e.clientX + 10 + 'px';
            ghost.style.top = e.clientY + 10 + 'px';
        };

        const onUp = () => {
            document.removeEventListener('mousemove', onMove);
            document.removeEventListener('mouseup', onUp);
            this.endDrag();
        };

        document.addEventListener('mousemove', onMove);
        document.addEventListener('mouseup', onUp);
    },

    dropPanel(targetSlot) {
        if (!this.dragging) return;
        const { panelId, fromSlot } = this.dragging;

        if (targetSlot !== fromSlot) {
            // Remove from old slot
            this.layout[fromSlot] = this.layout[fromSlot].filter(id => id !== panelId);

            // Add to new slot (avoid duplicates)
            if (!this.layout[targetSlot]) this.layout[targetSlot] = [];
            if (!this.layout[targetSlot].includes(panelId)) {
                this.layout[targetSlot].push(panelId);
            }

            this.saveState();
        }

        this.endDrag();
        this.render();
    },

    endDrag() {
        if (!this.dragging) return;
        if (this.dragging.ghost) this.dragging.ghost.remove();

        const layout = document.getElementById('dock-layout');
        layout.classList.remove('dragging');

        const overlay = document.getElementById('dock-drop-overlay');
        if (overlay) overlay.classList.remove('active');

        // Clear hover from all zones
        document.querySelectorAll('.dock-drop-zone').forEach(z => z.classList.remove('hover'));

        this.dragging = null;
    },

    // --- Resize handles ---

    setupResize() {
        document.addEventListener('mousedown', e => {
            const handle = e.target.closest('.dock-handle');
            if (!handle) return;
            e.preventDefault();

            const slot = handle.getAttribute('data-resize');
            if (this.collapsed[slot]) return;

            const isH = handle.classList.contains('dock-handle-h');

            this.resizing = {
                slot,
                startPos: isH ? e.clientY : e.clientX,
                startSize: this.sizes[slot],
                isH,
            };

            handle.classList.add('dragging');
            document.getElementById('dock-layout').classList.add('dragging');
        });

        document.addEventListener('mousemove', e => {
            if (!this.resizing) return;
            const { slot, startPos, startSize, isH } = this.resizing;
            const current = isH ? e.clientY : e.clientX;
            let delta = current - startPos;

            // Invert for east/south (grow opposite direction)
            if (slot === 'east' || slot === 'south') delta = -delta;

            this.sizes[slot] = Math.max(30, Math.min(startSize + delta, 600));
            this.render();
        });

        document.addEventListener('mouseup', () => {
            if (!this.resizing) return;
            document.querySelectorAll('.dock-handle.dragging').forEach(h => h.classList.remove('dragging'));
            document.getElementById('dock-layout').classList.remove('dragging');
            this.resizing = null;
            this.saveState();
        });
    },
};

document.addEventListener('DOMContentLoaded', () => app.init());
