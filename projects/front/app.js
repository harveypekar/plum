const SERVICES = ['postgresql', 'ollama', 'aiserver', 'rp'];
const POLL_STATUS_MS = 2000;
const POLL_LOGS_MS = 3000;
const DOCK_STORAGE_KEY = 'plum-dock-state';

const app = {
    currentTab: 'master',

    init() {
        this.renderServiceCards();
        this.renderRpStatusBar();
        this.setupTabs();
        this.setupRestartButtons();
        this.startPolling();
        dock.init();
    },

    // --- DOM helpers ---

    el(tag, attrs, children) {
        const e = document.createElement(tag);
        if (attrs) Object.entries(attrs).forEach(([k, v]) => {
            if (k === 'class') e.className = v;
            else if (k.startsWith('data-')) e.setAttribute(k, v);
            else e[k] = v;
        });
        if (typeof children === 'string') e.textContent = children;
        else if (Array.isArray(children)) children.forEach(c => e.appendChild(c));
        return e;
    },

    // --- Master tab rendering ---

    renderServiceCards() {
        const grid = document.getElementById('service-grid');
        SERVICES.forEach(s => {
            const card = this.el('div', { class: 'service-card', id: `service-${s}` }, [
                this.el('div', { class: 'service-name' }, s),
                this.el('div', { class: 'status-indicator status-unknown' }, '\u25CF CHECKING...'),
                this.el('button', { class: 'restart-btn', 'data-service': s }, 'RESTART'),
                this.el('div', { class: 'logs-section' }, [
                    this.el('div', { class: 'logs-label' }, 'Logs:'),
                    this.el('div', { class: 'logs', id: `logs-${s}` }, 'Loading...'),
                ]),
            ]);
            grid.appendChild(card);
        });
    },

    // --- rp tab status bar ---

    renderRpStatusBar() {
        const bar = document.getElementById('rp-status-bar');
        if (!bar) return;
        SERVICES.forEach(s => {
            const wrapper = this.el('div', { class: 'service-status-inline', id: `rp-inline-${s}` }, [
                this.el('span', { class: 'status-indicator status-unknown' }, `\u25CF ${s}`),
                this.el('button', { class: 'inline-restart-btn', 'data-service': s }, 'RESTART'),
            ]);
            bar.appendChild(wrapper);
        });
    },

    // --- Tabs ---

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
    },

    // --- Restart ---

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

    // --- Polling ---

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

        // Master dashboard card
        const card = document.getElementById(`service-${service}`);
        if (card) {
            const ind = card.querySelector('.status-indicator');
            ind.className = `status-indicator ${cls}`;
            ind.textContent = label;
            card.classList.toggle('stopped', status === 'stopped');
        }

        // rp tab inline status
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
        } catch {
            // silently skip
        }
    },

    updateLogs(service, lines) {
        // Master tab + rp tab dock panels
        const targets = [
            document.getElementById(`logs-${service}`),
            document.getElementById(`logs-${service}-dock`),
        ];

        targets.forEach(container => {
            if (!container) return;
            container.textContent = '';
            if (lines.length === 0) {
                container.appendChild(this.el('div', { class: 'log-line' }, 'No logs'));
            } else {
                lines.forEach(line => {
                    container.appendChild(this.el('div', { class: 'log-line' }, line));
                });
            }
            container.scrollTop = container.scrollHeight;
        });
    },
};


// ===== Dockable Panel System =====

const dock = {
    sizes: { north: 60, south: 180, west: 250, east: 250 },
    collapsed: { north: false, south: false, west: false, east: false },
    dragging: null,

    init() {
        this.loadState();
        this.applySizes();
        this.setupToggles();
        this.setupHandles();
    },

    // --- Persistence ---

    loadState() {
        try {
            const saved = JSON.parse(localStorage.getItem(DOCK_STORAGE_KEY));
            if (saved) {
                if (saved.sizes) Object.assign(this.sizes, saved.sizes);
                if (saved.collapsed) Object.assign(this.collapsed, saved.collapsed);
            }
        } catch { /* ignore */ }

        // Apply collapsed state from loaded data
        Object.keys(this.collapsed).forEach(side => {
            if (this.collapsed[side]) {
                const panel = document.getElementById(`dock-${side}`);
                if (panel) panel.classList.add('collapsed');
            }
        });
    },

    saveState() {
        localStorage.setItem(DOCK_STORAGE_KEY, JSON.stringify({
            sizes: this.sizes,
            collapsed: this.collapsed,
        }));
    },

    applySizes() {
        const layout = document.getElementById('dock-layout');
        if (!layout) return;
        layout.style.setProperty('--dock-north-size', this.collapsed.north ? '30px' : this.sizes.north + 'px');
        layout.style.setProperty('--dock-south-size', this.collapsed.south ? '30px' : this.sizes.south + 'px');

        const middle = layout.querySelector('.dock-middle');
        if (middle) {
            middle.style.setProperty('--dock-west-size', this.collapsed.west ? '30px' : this.sizes.west + 'px');
            middle.style.setProperty('--dock-east-size', this.collapsed.east ? '30px' : this.sizes.east + 'px');
        }
    },

    // --- Collapse / Expand ---

    setupToggles() {
        document.querySelectorAll('.dock-toggle').forEach(btn => {
            btn.addEventListener('click', () => {
                const side = btn.getAttribute('data-dock');
                this.toggle(side);
            });
        });
    },

    toggle(side) {
        this.collapsed[side] = !this.collapsed[side];
        const panel = document.getElementById(`dock-${side}`);
        if (panel) panel.classList.toggle('collapsed', this.collapsed[side]);

        // Update button text
        const btn = panel.querySelector('.dock-toggle');
        if (btn) btn.textContent = this.collapsed[side] ? '+' : '\u2013';

        this.applySizes();
        this.saveState();
    },

    // --- Resize handles ---

    setupHandles() {
        document.querySelectorAll('.dock-handle').forEach(handle => {
            handle.addEventListener('mousedown', e => this.startDrag(e, handle));
        });

        document.addEventListener('mousemove', e => this.onDrag(e));
        document.addEventListener('mouseup', () => this.stopDrag());
    },

    startDrag(e, handle) {
        e.preventDefault();
        const side = handle.getAttribute('data-resize');
        if (this.collapsed[side]) return;

        this.dragging = {
            side,
            startPos: (side === 'west' || side === 'east') ? e.clientX : e.clientY,
            startSize: this.sizes[side],
        };

        handle.classList.add('dragging');
        document.getElementById('dock-layout').classList.add('resizing');
    },

    onDrag(e) {
        if (!this.dragging) return;
        const { side, startPos, startSize } = this.dragging;
        const isHorizontal = (side === 'west' || side === 'east');
        const currentPos = isHorizontal ? e.clientX : e.clientY;
        let delta = currentPos - startPos;

        // Invert delta for east and south (they grow in opposite direction)
        if (side === 'east' || side === 'south') delta = -delta;

        const newSize = Math.max(40, Math.min(startSize + delta, 600));
        this.sizes[side] = newSize;
        this.applySizes();
    },

    stopDrag() {
        if (!this.dragging) return;
        document.querySelectorAll('.dock-handle.dragging').forEach(h => h.classList.remove('dragging'));
        document.getElementById('dock-layout').classList.remove('resizing');
        this.dragging = null;
        this.saveState();
    },
};


document.addEventListener('DOMContentLoaded', () => app.init());
