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
        render() {
            const root = el('div', { id: 'rp-browser-root' });

            // Tab bar
            const tabs = el('div', { class: 'rp-browser-tabs' });
            const tabNames = ['Chats', 'Cards', 'Scenarios'];
            const lists = {};

            tabNames.forEach(name => {
                const btn = el('button', { class: 'rp-browser-tab' + (name === 'Chats' ? ' active' : '') }, name);
                btn.addEventListener('click', () => {
                    tabs.querySelectorAll('.rp-browser-tab').forEach(b => b.classList.remove('active'));
                    btn.classList.add('active');
                    Object.values(lists).forEach(l => l.style.display = 'none');
                    lists[name].style.display = '';
                });
                tabs.appendChild(btn);
            });
            root.appendChild(tabs);

            // Chats list
            const chatsContainer = el('div', {});
            const chatsActions = el('div', { class: 'rp-browser-actions' });
            const newChatBtn = el('button', {}, '+ New');
            newChatBtn.addEventListener('click', () => rpState.emit('new-chat-requested'));
            chatsActions.appendChild(newChatBtn);
            chatsContainer.appendChild(chatsActions);
            const chatsList = el('div', { class: 'rp-browser-list', id: 'rp-chats-list' });
            chatsContainer.appendChild(chatsList);
            lists['Chats'] = chatsContainer;
            root.appendChild(chatsContainer);

            // Cards list
            const cardsContainer = el('div', {});
            cardsContainer.style.display = 'none';

            // Drop zone for SillyTavern PNG import
            const dropZone = el('div', { class: 'rp-drop-zone' }, 'Drop SillyTavern PNG here or click to import');
            const filePicker = document.createElement('input');
            filePicker.type = 'file';
            filePicker.accept = '.png';
            filePicker.style.display = 'none';
            dropZone.addEventListener('click', () => filePicker.click());
            dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('dragover'); });
            dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
            dropZone.addEventListener('drop', e => {
                e.preventDefault();
                dropZone.classList.remove('dragover');
                if (e.dataTransfer.files.length > 0) rpImportCardPng(e.dataTransfer.files[0]);
            });
            filePicker.addEventListener('change', () => {
                if (filePicker.files.length > 0) rpImportCardPng(filePicker.files[0]);
                filePicker.value = '';
            });
            cardsContainer.appendChild(dropZone);

            const cardsActions = el('div', { class: 'rp-browser-actions' });
            const newCardBtn = el('button', {}, '+ New Card');
            newCardBtn.addEventListener('click', () => rpState.emit('card-opened', null));
            const genCardBtn = el('button', {}, 'Generate');
            genCardBtn.addEventListener('click', () => rpState.emit('card-generate-requested'));
            cardsActions.appendChild(newCardBtn);
            cardsActions.appendChild(genCardBtn);
            cardsContainer.appendChild(cardsActions);
            const cardsList = el('div', { class: 'rp-browser-list', id: 'rp-cards-list' });
            cardsContainer.appendChild(cardsList);
            lists['Cards'] = cardsContainer;
            root.appendChild(cardsContainer);

            // Scenarios list
            const scenariosContainer = el('div', {});
            scenariosContainer.style.display = 'none';
            const scenariosActions = el('div', { class: 'rp-browser-actions' });
            const newScenarioBtn = el('button', {}, '+ New Scenario');
            newScenarioBtn.addEventListener('click', () => rpState.emit('scenario-opened', null));
            scenariosActions.appendChild(newScenarioBtn);
            scenariosContainer.appendChild(scenariosActions);
            const scenariosList = el('div', { class: 'rp-browser-list', id: 'rp-scenarios-list' });
            scenariosContainer.appendChild(scenariosList);
            lists['Scenarios'] = scenariosContainer;
            root.appendChild(scenariosContainer);

            // Render list contents
            rpRenderChatsList(chatsList);
            rpRenderCardsList(cardsList);
            rpRenderScenariosList(scenariosList);

            // Listen for changes
            rpState.on('convs-changed', () => rpRenderChatsList(chatsList));
            rpState.on('cards-changed', () => rpRenderCardsList(cardsList));
            rpState.on('scenarios-changed', () => rpRenderScenariosList(scenariosList));

            return root;
        },
    },
    'rp-scene-state': {
        id: 'rp-scene-state',
        title: 'Scene State',
        render() {
            const root = el('div', { id: 'rp-scene-state-root' });
            const textarea = document.createElement('textarea');
            textarea.className = 'rp-scene-state-area';
            textarea.placeholder = 'No active conversation';
            textarea.disabled = true;
            root.appendChild(textarea);

            const actions = el('div', { class: 'rp-form-actions' });
            const saveBtn = el('button', {}, 'Save');
            saveBtn.disabled = true;
            saveBtn.addEventListener('click', async () => {
                const tab = rpState.activeTab;
                if (!tab || tab.type !== 'chat') return;
                await rpApi('PUT', '/rp/conversations/' + tab.id + '/scene-state', {
                    scene_state: textarea.value,
                });
            });
            const refreshBtn = el('button', {}, 'Auto-generate');
            refreshBtn.disabled = true;
            refreshBtn.addEventListener('click', async () => {
                const tab = rpState.activeTab;
                if (!tab || tab.type !== 'chat') return;
                refreshBtn.disabled = true;
                refreshBtn.textContent = 'Generating...';
                try {
                    await rpApi('POST', '/rp/conversations/' + tab.id + '/refresh-scene-state');
                    const detail = await rpApi('GET', '/rp/conversations/' + tab.id);
                    textarea.value = detail.conversation.scene_state || '';
                } catch {}
                refreshBtn.disabled = false;
                refreshBtn.textContent = 'Auto-generate';
            });
            actions.appendChild(saveBtn);
            actions.appendChild(refreshBtn);
            root.appendChild(actions);

            // Update when active chat changes
            const update = (data) => {
                const tab = rpState.activeTab;
                if (tab && tab.type === 'chat') {
                    textarea.disabled = false;
                    saveBtn.disabled = false;
                    refreshBtn.disabled = false;
                    if (data && data.detail) {
                        textarea.value = data.detail.conversation.scene_state || '';
                    }
                } else {
                    textarea.disabled = true;
                    textarea.value = '';
                    textarea.placeholder = 'No active conversation';
                    saveBtn.disabled = true;
                    refreshBtn.disabled = true;
                }
            };

            rpState.on('conv-message', update);
            rpState.on('tab-closed', update);

            return root;
        },
    },
    'rp-under-hood': {
        id: 'rp-under-hood',
        title: 'Under the Hood',
        render() {
            const root = el('div', { id: 'rp-under-hood-root' });

            // Sub-tabs
            const tabs = el('div', { class: 'rp-under-hood-tabs' });
            const panes = {};
            const tabNames = ['System Prompt', 'User Prompt', 'Raw Response'];
            const paneKeys = ['system', 'user', 'raw'];

            tabNames.forEach((name, i) => {
                const btn = el('button', { class: 'rp-under-hood-tab' + (i === 0 ? ' active' : '') }, name);
                btn.addEventListener('click', () => {
                    tabs.querySelectorAll('.rp-under-hood-tab').forEach(b => b.classList.remove('active'));
                    btn.classList.add('active');
                    Object.values(panes).forEach(p => p.style.display = 'none');
                    panes[paneKeys[i]].style.display = '';
                });
                tabs.appendChild(btn);
            });
            root.appendChild(tabs);

            // Panes
            paneKeys.forEach((key, i) => {
                const pane = el('pre', { class: 'rp-under-hood-pre' }, 'No data yet.');
                pane.id = 'rp-under-hood-' + key;
                if (i > 0) pane.style.display = 'none';
                panes[key] = pane;
                root.appendChild(pane);
            });

            // Update on messages
            rpState.on('conv-message', data => {
                if (data.type === 'debug') {
                    panes.system.textContent = data.debug_prompt || '(empty)';
                    panes.user.textContent = data.debug_user_prompt || '(empty)';
                } else if (data.type === 'done' && data.chunk) {
                    panes.raw.textContent = JSON.stringify(data.chunk, null, 2);
                } else if (data.type === 'load' && data.detail) {
                    const msgs = data.detail.messages || [];
                    const lastAi = [...msgs].reverse().find(m => m.role === 'assistant');
                    if (lastAi && lastAi.raw_response) {
                        panes.raw.textContent = JSON.stringify(lastAi.raw_response, null, 2);
                    } else {
                        panes.raw.textContent = 'No data yet.';
                    }
                }
            });

            return root;
        },
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


// ===== RP: State & Event Bus =====

const rpState = {
    cards: [],
    scenarios: [],
    conversations: [],
    models: [],
    openTabs: [],    // {type: 'chat'|'card'|'scenario', id: number}
    activeTab: null,
    _listeners: {},

    on(event, fn) {
        (this._listeners[event] ||= []).push(fn);
    },
    off(event, fn) {
        const arr = this._listeners[event];
        if (arr) this._listeners[event] = arr.filter(f => f !== fn);
    },
    emit(event, data) {
        (this._listeners[event] || []).forEach(fn => fn(data));
    },
};

async function rpApi(method, path, body) {
    const opts = { method };
    if (body !== undefined) {
        opts.headers = { 'Content-Type': 'application/json' };
        opts.body = JSON.stringify(body);
    }
    const res = await fetch(path, opts);
    if (!res.ok) {
        const text = await res.text();
        throw new Error(text || res.statusText);
    }
    if (res.status === 204) return null;
    return res.json();
}

// ===== RP: Model Helpers =====

const rpModelTags = {
    "lumimaid": ["roleplay", "uncensored"],
    "daturacookie": ["roleplay", "uncensored", "small"],
    "cydonia": ["roleplay", "uncensored"],
    "nevoria": ["roleplay", "uncensored"],
    "mag-mell": ["roleplay"],
    "dolphin": ["instruct", "uncensored", "small"],
    "qwen2.5": ["instruct"],
    "qwen3": ["instruct"],
    "qwen:": ["instruct", "small"],
    "llama3": ["instruct"],
};

function rpModelGetTags(name) {
    const lower = name.toLowerCase();
    for (const pattern in rpModelTags) {
        if (lower.indexOf(pattern) !== -1) return rpModelTags[pattern];
    }
    return [];
}

function rpModelLabel(m) {
    let label = m.alias ? m.alias + ' (' + m.name + ')' : m.name;
    const parts = [];
    if (m.parameter_size) parts.push(m.parameter_size);
    if (m.quantization_level) parts.push(m.quantization_level);
    const tags = rpModelGetTags(m.name);
    if (tags.length > 0) parts.push(tags.join(', '));
    if (parts.length > 0) label += ' — ' + parts.join(' · ');
    return label;
}

function rpModelSupportsThink(modelValue) {
    const m = rpState.models.find(x => (x.alias || x.name) === modelValue);
    return m ? !!m.supports_think : false;
}

function rpPopulateModelSelect(selectEl, selectedValue) {
    while (selectEl.options.length > 0) selectEl.remove(0);
    for (const m of rpState.models) {
        const opt = document.createElement('option');
        opt.value = m.alias || m.name;
        opt.textContent = rpModelLabel(m);
        if (opt.value === selectedValue) opt.selected = true;
        selectEl.appendChild(opt);
    }
}

// ===== RP: Data Loading & Utilities =====

async function rpLoadCards() {
    try { rpState.cards = await rpApi('GET', '/rp/cards'); } catch {}
    rpState.emit('cards-changed');
}
async function rpLoadScenarios() {
    try { rpState.scenarios = await rpApi('GET', '/rp/scenarios'); } catch {}
    rpState.emit('scenarios-changed');
}
async function rpLoadConversations() {
    try { rpState.conversations = await rpApi('GET', '/rp/conversations'); } catch {}
    rpState.emit('convs-changed');
}
async function rpLoadModels() {
    try {
        const data = await rpApi('GET', '/health');
        rpState.models = data.available_models || [];
    } catch {}
}

function rpTimeAgo(dateStr) {
    const d = new Date(dateStr);
    const now = new Date();
    const diff = (now - d) / 1000;
    if (diff < 60) return 'just now';
    if (diff < 3600) return Math.floor(diff / 60) + 'm ago';
    if (diff < 86400) return Math.floor(diff / 3600) + 'h ago';
    return Math.floor(diff / 86400) + 'd ago';
}

function confirmAction(btn, onConfirm) {
    if (btn.dataset.confirming) return;
    btn.dataset.confirming = '1';
    const orig = btn.textContent;
    const origClass = btn.className;
    btn.textContent = 'Sure?';
    btn.className = (origClass ? origClass + ' ' : '') + 'confirming';
    const reset = () => {
        delete btn.dataset.confirming;
        btn.textContent = orig;
        btn.className = origClass;
        document.removeEventListener('click', outsideClick, true);
    };
    const outsideClick = (e) => { if (!btn.contains(e.target)) reset(); };
    setTimeout(() => document.addEventListener('click', outsideClick, true), 0);
    btn.addEventListener('click', function handler() {
        btn.removeEventListener('click', handler);
        reset();
        onConfirm();
    }, { once: true });
}


// ===== RP: List Rendering =====

function rpRenderChatsList(container) {
    container.textContent = '';
    for (const c of rpState.conversations) {
        const aiCard = rpState.cards.find(card => card.id === c.ai_card_id);
        const aiData = aiCard ? (aiCard.card_data.data || aiCard.card_data) : null;
        const name = aiData ? aiData.name : 'Conv #' + c.id;

        const item = el('div', { class: 'rp-browser-item' });
        const info = el('div', {});
        info.appendChild(el('div', { class: 'rp-browser-item-name' }, name));
        info.appendChild(el('div', { class: 'rp-browser-item-date' }, rpTimeAgo(c.updated_at)));
        item.appendChild(info);

        const del = el('span', { class: 'rp-browser-item-delete' }, '\u2715');
        del.addEventListener('click', e => {
            e.stopPropagation();
            confirmAction(del, async () => {
                await rpApi('DELETE', '/rp/conversations/' + c.id);
                rpLoadConversations();
            });
        });
        item.appendChild(del);

        item.addEventListener('click', () => rpState.emit('conv-opened', c.id));
        container.appendChild(item);
    }
    if (rpState.conversations.length === 0) {
        container.appendChild(el('div', { class: 'rp-browser-item' }, 'No conversations'));
    }
}

function rpRenderCardsList(container) {
    container.textContent = '';
    for (const card of rpState.cards) {
        const cardData = card.card_data.data || card.card_data;
        const item = el('div', { class: 'rp-browser-item' });

        const avatar = document.createElement('img');
        avatar.className = 'rp-card-avatar-small';
        avatar.alt = '';
        if (card.has_avatar) {
            avatar.src = '/rp/cards/' + card.id + '/avatar';
        } else {
            avatar.style.background = 'var(--accent-dim)';
        }
        item.appendChild(avatar);

        item.appendChild(el('span', {}, cardData.name || card.name));

        const del = el('span', { class: 'rp-browser-item-delete' }, '\u2715');
        del.addEventListener('click', e => {
            e.stopPropagation();
            confirmAction(del, async () => {
                await rpApi('DELETE', '/rp/cards/' + card.id);
                rpLoadCards();
            });
        });
        item.appendChild(del);

        item.addEventListener('click', () => rpState.emit('card-opened', card.id));
        container.appendChild(item);
    }
    if (rpState.cards.length === 0) {
        container.appendChild(el('div', { class: 'rp-browser-item' }, 'No cards'));
    }
}

function rpRenderScenariosList(container) {
    container.textContent = '';
    for (const s of rpState.scenarios) {
        const item = el('div', { class: 'rp-browser-item' });
        const info = el('div', {});
        info.appendChild(el('div', { class: 'rp-browser-item-name' }, s.name));
        if (s.description) {
            const desc = s.description.substring(0, 80) + (s.description.length > 80 ? '...' : '');
            info.appendChild(el('div', { class: 'rp-browser-item-date' }, desc));
        }
        item.appendChild(info);

        const del = el('span', { class: 'rp-browser-item-delete' }, '\u2715');
        del.addEventListener('click', e => {
            e.stopPropagation();
            confirmAction(del, async () => {
                await rpApi('DELETE', '/rp/scenarios/' + s.id);
                rpLoadScenarios();
            });
        });
        item.appendChild(del);

        item.addEventListener('click', () => rpState.emit('scenario-opened', s.id));
        container.appendChild(item);
    }
    if (rpState.scenarios.length === 0) {
        container.appendChild(el('div', { class: 'rp-browser-item' }, 'No scenarios'));
    }
}

async function rpImportCardPng(file) {
    const formData = new FormData();
    formData.append('file', file);
    try {
        const resp = await fetch('/rp/cards/import', { method: 'POST', body: formData });
        if (!resp.ok) throw new Error(await resp.text());
        await resp.json();
        rpLoadCards();
    } catch (e) {
        console.error('Import failed:', e.message);
    }
}


// ===== RP: Center (Tab Manager) =====

const rpCenter = {
    container: null,
    tabBar: null,
    contentArea: null,

    render() {
        const root = el('div', { class: 'rp-center' });
        this.container = root;
        this.tabBar = el('div', { class: 'rp-center-tabs' });
        this.contentArea = el('div', { class: 'rp-center-content' });
        root.appendChild(this.tabBar);
        root.appendChild(this.contentArea);
        this.renderTabs();
        this.renderContent();
        return root;
    },

    renderTabs() {
        this.tabBar.textContent = '';
        rpState.openTabs.forEach(t => {
            const label = this.getTabLabel(t.type, t.id);
            const tab = el('div', {
                class: 'rp-center-tab' + (rpState.activeTab === t ? ' active' : ''),
            });
            tab.appendChild(el('span', {}, label));
            const closeBtn = el('span', { class: 'rp-center-tab-close' }, '\u2715');
            closeBtn.addEventListener('click', (e) => { e.stopPropagation(); this.closeTab(t.type, t.id); });
            tab.appendChild(closeBtn);
            tab.addEventListener('click', () => {
                rpState.activeTab = t;
                this.renderTabs();
                this.renderContent();
            });
            this.tabBar.appendChild(tab);
        });
    },

    getTabLabel(type, id) {
        if (type === 'chat') {
            const conv = rpState.conversations.find(c => c.id === id);
            if (conv) {
                const aiCard = rpState.cards.find(c => c.id === conv.ai_card_id);
                const aiData = aiCard ? (aiCard.card_data.data || aiCard.card_data) : null;
                return aiData ? aiData.name : 'Chat #' + id;
            }
            return 'Chat #' + id;
        }
        if (type === 'card') {
            if (id === null) return 'New Card';
            const card = rpState.cards.find(c => c.id === id);
            const data = card ? (card.card_data.data || card.card_data) : null;
            return data ? data.name : 'Card #' + id;
        }
        if (type === 'scenario') {
            if (id === null) return 'New Scenario';
            const s = rpState.scenarios.find(x => x.id === id);
            return s ? s.name : 'Scenario #' + id;
        }
        return 'Tab';
    },

    renderContent() {
        this.contentArea.textContent = '';
        const tab = rpState.activeTab;
        if (!tab) {
            this.contentArea.appendChild(el('div', { class: 'rp-placeholder' }, 'Select an item from the browser'));
            return;
        }
        if (tab.type === 'chat') {
            if (typeof rpChat !== 'undefined') rpChat.render(this.contentArea, tab.id);
            else this.contentArea.appendChild(el('div', { class: 'rp-placeholder' }, 'Chat view (coming soon)'));
        } else if (tab.type === 'card') {
            if (typeof rpCards !== 'undefined') rpCards.renderEditor(this.contentArea, tab.id);
            else this.contentArea.appendChild(el('div', { class: 'rp-placeholder' }, 'Card editor (coming soon)'));
        } else if (tab.type === 'scenario') {
            if (typeof rpScenarios !== 'undefined') rpScenarios.renderEditor(this.contentArea, tab.id);
            else this.contentArea.appendChild(el('div', { class: 'rp-placeholder' }, 'Scenario editor (coming soon)'));
        } else if (tab.type === 'card-gen') {
            if (typeof rpCards !== 'undefined') rpCards.renderGenerator(this.contentArea);
            else this.contentArea.appendChild(el('div', { class: 'rp-placeholder' }, 'Card generator (coming soon)'));
        }
    },

    openTab(type, id) {
        let existing = rpState.openTabs.find(t => t.type === type && t.id === id);
        if (!existing) {
            existing = { type, id };
            rpState.openTabs.push(existing);
        }
        rpState.activeTab = existing;
        this.renderTabs();
        this.renderContent();
    },

    closeTab(type, id) {
        rpState.openTabs = rpState.openTabs.filter(t => !(t.type === type && t.id === id));
        if (rpState.activeTab && rpState.activeTab.type === type && rpState.activeTab.id === id) {
            rpState.activeTab = rpState.openTabs.length > 0 ? rpState.openTabs[rpState.openTabs.length - 1] : null;
        }
        rpState.emit('tab-closed', { type, id });
        this.renderTabs();
        this.renderContent();
    },
};

// Wire events to center
rpState.on('conv-opened', id => rpCenter.openTab('chat', id));
rpState.on('card-opened', id => rpCenter.openTab('card', id));
rpState.on('scenario-opened', id => rpCenter.openTab('scenario', id));
rpState.on('card-generate-requested', () => rpCenter.openTab('card-gen', 'generator'));

// ===== RP: Chat Helpers =====

function rpRenderDialogue(bubble, content, role) {
    const quoteClass = role === 'user' ? 'dialogue-quote-user' : 'dialogue-quote-assistant';
    const regex = /"([^"]+)"/g;
    let lastIndex = 0;
    let match;
    while ((match = regex.exec(content)) !== null) {
        if (match.index > lastIndex) {
            bubble.appendChild(document.createTextNode(content.slice(lastIndex, match.index)));
        }
        const span = document.createElement('span');
        span.className = quoteClass;
        span.textContent = '\u201C' + match[1] + '\u201D';
        bubble.appendChild(span);
        lastIndex = regex.lastIndex;
    }
    if (lastIndex < content.length) {
        bubble.appendChild(document.createTextNode(content.slice(lastIndex)));
    }
    if (lastIndex === 0) {
        bubble.textContent = content;
    }
}

function rpSetAvatarSrc(img, cardId, hasAvatar) {
    if (hasAvatar) {
        img.src = '/rp/cards/' + cardId + '/avatar';
    } else {
        img.style.background = 'var(--accent-dim)';
    }
}

// ===== RP: Chat =====

const rpChat = {
    convId: null,
    convDetail: null,
    isStreaming: false,
    abortController: null,
    autoMode: false,
    messagesContainer: null,

    async render(container, convId) {
        this.convId = convId;
        container.textContent = '';

        // Load conversation detail
        try {
            this.convDetail = await rpApi('GET', '/rp/conversations/' + convId);
        } catch (e) {
            container.appendChild(el('div', { class: 'rp-error' }, 'Failed to load conversation: ' + e.message));
            return;
        }

        const detail = this.convDetail;
        const { conversation, user_card, ai_card, scenario, messages } = detail;
        const aiData = ai_card.card_data.data || ai_card.card_data;

        // Build layout: header + body (messages + avatar strip) + input
        const wrapper = el('div', { class: 'rp-chat-wrapper' });

        // Header
        const header = el('div', { class: 'rp-chat-header' });
        const headerName = el('div', { class: 'rp-chat-header-name' }, aiData.name || ai_card.name);
        const headerMeta = el('div', { class: 'rp-chat-header-meta' },
            conversation.model + (scenario ? ' | ' + scenario.name : ''));
        header.appendChild(headerName);
        header.appendChild(headerMeta);

        // Action buttons
        const actions = el('div', { class: 'rp-chat-actions' });
        const continueBtn = el('button', {}, 'Continue');
        continueBtn.addEventListener('click', () => this.continueConversation());
        const regenBtn = el('button', {}, 'Regenerate');
        regenBtn.addEventListener('click', () => this.regenerateResponse());
        const restartBtn = el('button', {}, 'Restart');
        restartBtn.addEventListener('click', () => {
            confirmAction(restartBtn, () => this.restartConversation());
        });
        const autoBtn = el('button', {}, 'Auto');
        autoBtn.id = 'rp-auto-btn';
        autoBtn.addEventListener('click', () => this.toggleAutoMode());
        actions.appendChild(continueBtn);
        actions.appendChild(regenBtn);
        actions.appendChild(restartBtn);
        actions.appendChild(autoBtn);
        header.appendChild(actions);
        wrapper.appendChild(header);

        // Body: messages + avatar strip
        const body = el('div', { class: 'rp-chat-container' });

        // Messages
        const msgs = el('div', { class: 'rp-chat-messages' });
        this.messagesContainer = msgs;

        // Scenario banner
        if (scenario && scenario.description) {
            const banner = el('div', { class: 'rp-chat-banner' });
            banner.appendChild(el('div', { class: 'rp-chat-banner-label' }, 'Scenario'));
            const bannerText = el('span', {});
            rpRenderDialogue(bannerText, scenario.description, 'assistant');
            banner.appendChild(bannerText);
            msgs.appendChild(banner);
        }

        // Render existing messages
        for (let i = 0; i < messages.length; i++) {
            this.appendMessageBubble(msgs, messages[i], user_card, ai_card, i);
        }
        body.appendChild(msgs);

        // Avatar strip
        const strip = el('div', { class: 'rp-avatar-strip' });
        const userAvatar = document.createElement('img');
        userAvatar.className = 'rp-avatar-img';
        rpSetAvatarSrc(userAvatar, user_card.id, user_card.has_avatar);
        const aiAvatar = document.createElement('img');
        aiAvatar.className = 'rp-avatar-img';
        rpSetAvatarSrc(aiAvatar, ai_card.id, ai_card.has_avatar);
        strip.appendChild(userAvatar);
        strip.appendChild(aiAvatar);
        body.appendChild(strip);
        wrapper.appendChild(body);

        // Input area
        const inputArea = el('div', { class: 'rp-input-area' });
        const textarea = document.createElement('textarea');
        textarea.id = 'rp-chat-input';
        textarea.placeholder = 'Type a message...';
        textarea.rows = 2;
        textarea.addEventListener('input', () => {
            textarea.style.height = 'auto';
            textarea.style.height = Math.min(textarea.scrollHeight, 150) + 'px';
        });
        textarea.addEventListener('keydown', e => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });

        const sendBtn = el('button', { id: 'rp-send-btn' }, 'Send');
        sendBtn.addEventListener('click', () => this.sendMessage());
        const stopBtn = el('button', { id: 'rp-stop-btn' }, 'Stop');
        stopBtn.style.display = 'none';
        stopBtn.addEventListener('click', () => {
            this.autoMode = false;
            this.updateAutoBtn();
            if (this.abortController) this.abortController.abort();
        });

        inputArea.appendChild(textarea);
        inputArea.appendChild(sendBtn);
        inputArea.appendChild(stopBtn);
        wrapper.appendChild(inputArea);

        container.appendChild(wrapper);

        // Scroll to bottom
        msgs.scrollTop = msgs.scrollHeight;

        // Emit for debug panels
        rpState.emit('conv-message', { detail, type: 'load' });
    },

    appendMessageBubble(container, msg, userCard, aiCard, msgIndex) {
        const isUser = msg.role === 'user';
        const wrapper = el('div', { class: 'rp-msg ' + msg.role });

        const bubble = el('div', { class: 'rp-msg-bubble' });
        rpRenderDialogue(bubble, msg.content, msg.role);
        wrapper.appendChild(bubble);

        // Hover actions
        const actions = el('div', { class: 'rp-msg-hover-actions' });
        const editBtn = el('button', {}, 'Edit');
        editBtn.addEventListener('click', () => this.startEditMessage(msg, bubble));
        const delBtn = el('button', {}, 'Del');
        delBtn.addEventListener('click', () => {
            confirmAction(delBtn, async () => {
                await rpApi('DELETE', '/rp/messages/' + msg.id);
                rpCenter.renderContent();
            });
        });
        const copyBtn = el('button', {}, 'Copy');
        copyBtn.addEventListener('click', () => navigator.clipboard.writeText(msg.content));
        actions.appendChild(editBtn);
        actions.appendChild(delBtn);
        actions.appendChild(copyBtn);
        wrapper.appendChild(actions);

        // Message number
        if (msgIndex !== undefined) {
            wrapper.appendChild(el('div', { class: 'rp-msg-sequence' }, '#' + (msgIndex + 1)));
        }

        container.appendChild(wrapper);
        return { wrapper, bubble };
    },

    startEditMessage(msg, bubble) {
        const ta = document.createElement('textarea');
        ta.className = 'rp-msg-edit-textarea';
        ta.value = msg.content;
        bubble.replaceWith(ta);
        ta.style.height = 'auto';
        ta.style.height = ta.scrollHeight + 'px';
        ta.addEventListener('input', () => {
            ta.style.height = 'auto';
            ta.style.height = ta.scrollHeight + 'px';
        });
        ta.focus();

        const save = async () => {
            const newContent = ta.value.trim();
            if (newContent && newContent !== msg.content) {
                await rpApi('PUT', '/rp/messages/' + msg.id, { content: newContent });
            }
            rpCenter.renderContent();
        };

        ta.addEventListener('blur', save);
        ta.addEventListener('keydown', e => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                ta.blur();
            }
            if (e.key === 'Escape') {
                ta.removeEventListener('blur', save);
                rpCenter.renderContent();
            }
        });
    },

    // --- Streaming ---

    async sendMessage() {
        const input = document.getElementById('rp-chat-input');
        const content = input.value.trim();
        if (!content || !this.convId || this.isStreaming) return;

        input.value = '';
        input.style.height = 'auto';
        this.setStreaming(true);

        // Append user bubble immediately
        const container = this.messagesContainer;
        const userMsg = { id: null, role: 'user', content };
        this.appendMessageBubble(container, userMsg, this.convDetail.user_card, this.convDetail.ai_card);
        container.scrollTop = container.scrollHeight;

        const hadError = await this.streamResponse(
            '/rp/conversations/' + this.convId + '/message',
            { content }, container);

        this.setStreaming(false);
        if (!hadError) rpCenter.renderContent();
    },

    async continueConversation() {
        if (!this.convId || this.isStreaming) return;
        this.setStreaming(true);
        const container = this.messagesContainer;
        const hadError = await this.streamResponse(
            '/rp/conversations/' + this.convId + '/continue', undefined, container);
        this.setStreaming(false);
        if (!hadError) rpCenter.renderContent();
    },

    async regenerateResponse() {
        if (!this.convId || this.isStreaming) return;
        this.setStreaming(true);

        // Remove last AI message from DOM
        const container = this.messagesContainer;
        const allMsgs = container.querySelectorAll('.rp-msg.assistant');
        if (allMsgs.length > 0) allMsgs[allMsgs.length - 1].remove();

        const hadError = await this.streamResponse(
            '/rp/conversations/' + this.convId + '/regenerate', undefined, container);
        this.setStreaming(false);
        if (!hadError) rpCenter.renderContent();
    },

    async restartConversation() {
        if (!this.convId || this.isStreaming) return;
        const container = this.messagesContainer;
        container.textContent = '';
        const timerStart = Date.now();
        const timerEl = el('div', { class: 'rp-placeholder' });
        const timerText = el('div', {}, 'Generating opening scene... 0s');
        timerEl.appendChild(timerText);
        container.appendChild(timerEl);
        const timerInterval = setInterval(() => {
            timerText.textContent = 'Generating opening scene... ' +
                Math.floor((Date.now() - timerStart) / 1000) + 's';
        }, 1000);
        try {
            await rpApi('POST', '/rp/conversations/' + this.convId + '/restart');
        } catch {}
        clearInterval(timerInterval);
        rpCenter.renderContent();
    },

    toggleAutoMode() {
        if (!this.convId) return;
        this.autoMode = !this.autoMode;
        this.updateAutoBtn();
        if (this.autoMode) this.autoReplyLoop();
    },

    updateAutoBtn() {
        const btn = document.getElementById('rp-auto-btn');
        if (!btn) return;
        btn.textContent = this.autoMode ? 'Stop Auto' : 'Auto';
        if (this.autoMode) {
            btn.style.background = '#f44';
            btn.style.color = '#fff';
            btn.style.borderColor = '#f44';
        } else {
            btn.style.background = '';
            btn.style.color = '';
            btn.style.borderColor = '';
        }
    },

    async autoReplyLoop() {
        while (this.autoMode && this.convId && !this.isStreaming) {
            this.setStreaming(true);
            const container = this.messagesContainer;
            const hadError = await this.streamResponse(
                '/rp/conversations/' + this.convId + '/auto-reply',
                undefined, container);
            this.setStreaming(false);
            if (hadError) {
                this.autoMode = false;
                this.updateAutoBtn();
                break;
            }
            await new Promise(r => setTimeout(r, 500));
        }
        if (!this.autoMode) rpCenter.renderContent();
    },

    setStreaming(on) {
        this.isStreaming = on;
        const sendBtn = document.getElementById('rp-send-btn');
        const stopBtn = document.getElementById('rp-stop-btn');
        if (sendBtn) sendBtn.style.display = on ? 'none' : '';
        if (stopBtn) stopBtn.style.display = on ? '' : 'none';
    },

    async streamResponse(url, body, container) {
        this.abortController = new AbortController();
        const opts = { method: 'POST', signal: this.abortController.signal };
        if (body !== undefined) {
            opts.headers = { 'Content-Type': 'application/json' };
            opts.body = JSON.stringify(body);
        }

        let streamRole = 'assistant';
        const wrapper = el('div', { class: 'rp-msg ' + streamRole });
        let thinkingSection = null;
        let thinkingContent = null;
        let hasThinking = false;
        let hadError = false;

        const bubble = el('div', { class: 'rp-msg-bubble streaming-cursor' });
        const col = el('div', {});
        col.appendChild(bubble);
        wrapper.appendChild(col);
        container.appendChild(wrapper);

        try {
            const resp = await fetch(url, opts);
            const reader = resp.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop();

                for (const line of lines) {
                    if (!line.trim()) continue;
                    const chunk = JSON.parse(line);

                    if (chunk.debug_prompt !== undefined) {
                        rpState.emit('conv-message', {
                            type: 'debug',
                            debug_prompt: chunk.debug_prompt,
                            debug_user_prompt: chunk.debug_user_prompt,
                        });
                        // Handle auto_role
                        if (chunk.auto_role && chunk.auto_role !== streamRole) {
                            streamRole = chunk.auto_role;
                            wrapper.className = 'rp-msg ' + streamRole;
                        }
                        continue;
                    }

                    if (chunk.error) {
                        hadError = true;
                        bubble.classList.remove('streaming-cursor');
                        const errSpan = el('span', { class: 'rp-error' }, 'Error: ' + chunk.error);
                        bubble.appendChild(errSpan);
                        break;
                    }

                    if (chunk.thinking) {
                        if (!hasThinking) {
                            hasThinking = true;
                            thinkingSection = el('div', { class: 'rp-msg-thinking' });
                            const toggle = el('div', { class: 'rp-msg-thinking-toggle' }, 'Thinking...');
                            toggle.addEventListener('click', () => {
                                thinkingContent.classList.toggle('collapsed');
                                toggle.textContent = thinkingContent.classList.contains('collapsed')
                                    ? 'Show thinking' : 'Hide thinking';
                            });
                            thinkingSection.appendChild(toggle);
                            thinkingContent = el('div', { class: 'rp-msg-thinking-content' });
                            thinkingSection.appendChild(thinkingContent);
                            col.insertBefore(thinkingSection, bubble);
                        }
                        thinkingContent.textContent += chunk.token;
                    } else if (chunk.done) {
                        bubble.classList.remove('streaming-cursor');
                        const fullText = bubble.textContent;
                        bubble.textContent = '';
                        rpRenderDialogue(bubble, fullText, streamRole);
                        if (thinkingContent) {
                            const toggle = thinkingSection.querySelector('.rp-msg-thinking-toggle');
                            toggle.textContent = 'Hide thinking';
                        }
                        rpState.emit('conv-message', { type: 'done', chunk });
                    } else {
                        bubble.textContent += chunk.token;
                    }

                    const atBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 60;
                    if (atBottom) container.scrollTop = container.scrollHeight;
                }
            }
        } catch (e) {
            if (e.name === 'AbortError') {
                const partialText = bubble.textContent.trim();
                if (partialText && this.convId) {
                    try {
                        await fetch('/rp/conversations/' + this.convId + '/save-partial', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ content: partialText, role: streamRole }),
                        });
                    } catch {}
                }
                bubble.classList.remove('streaming-cursor');
                if (partialText) {
                    bubble.textContent = '';
                    rpRenderDialogue(bubble, partialText, streamRole);
                }
            } else {
                hadError = true;
                bubble.classList.remove('streaming-cursor');
                bubble.textContent += '\n[Stream error: ' + e.message + ']';
            }
        } finally {
            bubble.classList.remove('streaming-cursor');
            this.abortController = null;
        }
        return hadError;
    },
};

// ===== RP: Cards =====

const rpCards = {
    async renderEditor(container, cardId) {
        container.textContent = '';
        let card = null;
        let cardData = {};

        if (cardId !== null) {
            try {
                card = rpState.cards.find(c => c.id === cardId);
                if (!card) card = await rpApi('GET', '/rp/cards/' + cardId);
                cardData = card.card_data.data || card.card_data;
            } catch (e) {
                container.appendChild(el('div', { class: 'rp-error' }, 'Failed to load card: ' + e.message));
                return;
            }
        }

        const form = el('div', { class: 'rp-form' });
        form.appendChild(el('div', { class: 'rp-form-title' }, cardId ? 'Edit Card' : 'New Card'));

        // Avatar preview (existing cards only)
        if (card) {
            const avatarPreview = document.createElement('img');
            avatarPreview.className = 'rp-card-avatar-preview';
            rpSetAvatarSrc(avatarPreview, card.id, card.has_avatar);
            const avatarPicker = document.createElement('input');
            avatarPicker.type = 'file';
            avatarPicker.accept = 'image/*';
            avatarPicker.style.display = 'none';
            avatarPreview.addEventListener('click', () => avatarPicker.click());
            avatarPicker.addEventListener('change', async () => {
                const file = avatarPicker.files[0];
                if (!file) return;
                const formData = new FormData();
                formData.append('file', file);
                await fetch('/rp/cards/' + card.id + '/avatar', { method: 'PUT', body: formData });
                avatarPreview.src = '/rp/cards/' + card.id + '/avatar?' + Date.now();
                rpLoadCards();
                avatarPicker.value = '';
            });
            form.appendChild(avatarPreview);
            form.appendChild(avatarPicker);
        }

        // Form fields
        const fields = [
            { key: 'name', label: 'Name', type: 'input', value: cardData.name || (card ? card.name : '') },
            { key: 'description', label: 'Description', type: 'textarea', rows: 4, value: cardData.description || '' },
            { key: 'personality', label: 'Personality', type: 'textarea', rows: 3, value: cardData.personality || '' },
            { key: 'first_mes', label: 'First Message', type: 'textarea', rows: 3, value: cardData.first_mes || '' },
            { key: 'mes_example', label: 'Example Messages', type: 'textarea', rows: 3, value: cardData.mes_example || '' },
            { key: 'scenario', label: 'Scenario', type: 'textarea', rows: 2, value: cardData.scenario || '' },
            { key: 'tags', label: 'Tags', type: 'input', value: (cardData.tags || []).join(', ') },
        ];

        const inputs = {};
        fields.forEach(f => {
            const fieldDiv = el('div', { class: 'rp-form-field' });
            fieldDiv.appendChild(el('label', {}, f.label));
            let input;
            if (f.type === 'textarea') {
                input = document.createElement('textarea');
                input.rows = f.rows;
            } else {
                input = document.createElement('input');
                input.type = 'text';
            }
            input.value = f.value;
            fieldDiv.appendChild(input);
            inputs[f.key] = input;

            // Extract scenario button for scenario field
            if (f.key === 'scenario' && card && cardData.scenario) {
                const extractBtn = el('button', { class: 'rp-form-inline-btn' }, 'Extract as Scenario');
                extractBtn.addEventListener('click', async () => {
                    try {
                        const scenario = await rpApi('POST', '/rp/cards/' + card.id + '/extract-scenario');
                        rpLoadScenarios();
                        extractBtn.textContent = 'Created: ' + scenario.name;
                    } catch (e) {
                        extractBtn.textContent = 'Error: ' + e.message;
                    }
                });
                fieldDiv.appendChild(extractBtn);
            }
            form.appendChild(fieldDiv);
        });

        // Actions
        const actions = el('div', { class: 'rp-form-actions' });

        if (card) {
            const exportBtn = el('button', {}, 'Export PNG');
            exportBtn.addEventListener('click', () => window.open('/rp/cards/' + card.id + '/export', '_blank'));
            actions.appendChild(exportBtn);

            const deleteBtn = el('button', { class: 'rp-form-delete' }, 'Delete');
            deleteBtn.addEventListener('click', () => {
                confirmAction(deleteBtn, async () => {
                    await rpApi('DELETE', '/rp/cards/' + card.id);
                    rpLoadCards();
                    rpCenter.closeTab('card', card.id);
                });
            });
            actions.appendChild(deleteBtn);
        }

        const saveBtn = el('button', {}, 'Save');
        saveBtn.addEventListener('click', async () => {
            const name = inputs.name.value.trim();
            if (!name) return;

            const tagsRaw = inputs.tags.value.trim();
            const tags = tagsRaw ? tagsRaw.split(',').map(t => t.trim()).filter(Boolean) : [];

            const newCardData = {
                data: {
                    name,
                    description: inputs.description.value,
                    personality: inputs.personality.value,
                    first_mes: inputs.first_mes.value,
                    mes_example: inputs.mes_example.value,
                    scenario: inputs.scenario.value,
                    tags,
                },
            };

            try {
                if (cardId) {
                    await rpApi('PUT', '/rp/cards/' + cardId, { name, card_data: newCardData });
                } else {
                    const created = await rpApi('POST', '/rp/cards', { name, card_data: newCardData });
                    rpCenter.closeTab('card', null);
                    rpCenter.openTab('card', created.id);
                }
                rpLoadCards();
            } catch (e) {
                saveBtn.textContent = 'Error: ' + e.message;
                setTimeout(() => { saveBtn.textContent = 'Save'; }, 2000);
            }
        });
        actions.appendChild(saveBtn);

        const cancelBtn = el('button', {}, 'Cancel');
        cancelBtn.addEventListener('click', () => rpCenter.closeTab('card', cardId));
        actions.appendChild(cancelBtn);

        form.appendChild(actions);
        container.appendChild(form);
    },

    // --- Card Generator ---

    renderGenerator(container) {
        container.textContent = '';
        const form = el('div', { class: 'rp-form' });
        form.appendChild(el('div', { class: 'rp-form-title' }, 'Generate Card'));

        // Step 1: description + model + generate button
        const step1 = el('div', { id: 'rp-card-gen-step1' });

        const descField = el('div', { class: 'rp-form-field' });
        descField.appendChild(el('label', {}, 'Describe the character'));
        const descInput = document.createElement('textarea');
        descInput.rows = 4;
        descInput.placeholder = 'A mysterious elven sorceress who...';
        descField.appendChild(descInput);
        step1.appendChild(descField);

        const modelField = el('div', { class: 'rp-form-field' });
        modelField.appendChild(el('label', {}, 'Model'));
        const modelSelect = document.createElement('select');
        rpPopulateModelSelect(modelSelect);
        modelField.appendChild(modelSelect);
        step1.appendChild(modelField);

        const genActions = el('div', { class: 'rp-form-actions' });
        const genBtn = el('button', {}, 'Generate');
        const status = el('div', { class: 'rp-form-status' });
        genActions.appendChild(genBtn);
        genActions.appendChild(status);
        step1.appendChild(genActions);

        // Step 2: field review
        const step2 = el('div', { id: 'rp-card-gen-step2' });
        step2.style.display = 'none';

        form.appendChild(step1);
        form.appendChild(step2);
        container.appendChild(form);

        let cardGenCard = null;
        let selectedModel = '';

        const rpCardGenFieldDefs = [
            { key: 'name', label: 'Name', rows: 1 },
            { key: 'description', label: 'Description', rows: 4 },
            { key: 'personality', label: 'Personality', rows: 3 },
            { key: 'first_mes', label: 'First Message', rows: 3 },
            { key: 'mes_example', label: 'Example Messages', rows: 3 },
            { key: 'scenario', label: 'Scenario', rows: 2 },
            { key: 'tags', label: 'Tags', rows: 1 },
        ];

        genBtn.addEventListener('click', async () => {
            const desc = descInput.value.trim();
            if (!desc) return;
            selectedModel = modelSelect.value;
            genBtn.disabled = true;
            status.textContent = 'Generating...';
            try {
                const resp = await rpApi('POST', '/rp/cards/generate', { description: desc, model: selectedModel });
                if (resp.error) {
                    status.textContent = 'Error: ' + resp.error;
                } else {
                    cardGenCard = resp.card;
                    renderStep2();
                    step1.style.display = 'none';
                    step2.style.display = '';
                    status.textContent = '';
                }
            } catch (e) {
                status.textContent = 'Failed: ' + e.message;
            }
            genBtn.disabled = false;
        });

        function syncFieldsToCard() {
            rpCardGenFieldDefs.forEach(def => {
                const ta = document.getElementById('rpCardGen_' + def.key);
                if (ta) {
                    if (def.key === 'tags') {
                        cardGenCard[def.key] = ta.value.split(',').map(t => t.trim());
                    } else {
                        cardGenCard[def.key] = ta.value;
                    }
                }
            });
        }

        function renderStep2() {
            step2.textContent = '';
            step2.appendChild(el('div', { class: 'rp-form-title' }, 'Review & Edit'));

            rpCardGenFieldDefs.forEach(def => {
                let val = cardGenCard[def.key] || '';
                if (def.key === 'tags' && Array.isArray(val)) val = val.join(', ');

                const fieldDiv = el('div', { class: 'rp-form-field' });
                const header = el('div', { class: 'rp-card-gen-field-header' });
                header.appendChild(el('label', {}, def.label));

                const regenBtn = el('button', {}, 'Regenerate');
                regenBtn.addEventListener('click', () => {
                    const instrDiv = document.getElementById('rpCardGenInstr_' + def.key);
                    instrDiv.classList.toggle('open');
                });
                header.appendChild(regenBtn);
                fieldDiv.appendChild(header);

                const ta = document.createElement('textarea');
                ta.id = 'rpCardGen_' + def.key;
                ta.rows = def.rows;
                ta.value = val;
                fieldDiv.appendChild(ta);

                // Instructions row for regenerate
                const instrDiv = el('div', { class: 'rp-card-gen-field-instructions', id: 'rpCardGenInstr_' + def.key });
                const instrInput = document.createElement('input');
                instrInput.type = 'text';
                instrInput.placeholder = 'Instructions (optional)';
                const instrGo = el('button', {}, 'Go');
                instrGo.addEventListener('click', async () => {
                    syncFieldsToCard();
                    instrGo.disabled = true;
                    regenBtn.textContent = '...';
                    try {
                        const resp = await rpApi('POST', '/rp/cards/generate-field', {
                            card: cardGenCard,
                            field: def.key,
                            instructions: instrInput.value.trim(),
                            model: selectedModel,
                        });
                        cardGenCard[def.key] = resp.value;
                        ta.value = Array.isArray(resp.value) ? resp.value.join(', ') : resp.value;
                    } catch {
                        regenBtn.textContent = 'Failed';
                        setTimeout(() => { regenBtn.textContent = 'Regenerate'; }, 2000);
                    }
                    instrGo.disabled = false;
                    regenBtn.textContent = 'Regenerate';
                });
                instrDiv.appendChild(instrInput);
                instrDiv.appendChild(instrGo);
                fieldDiv.appendChild(instrDiv);

                step2.appendChild(fieldDiv);
            });

            const step2Actions = el('div', { class: 'rp-form-actions' });
            const backBtn = el('button', {}, 'Back');
            backBtn.addEventListener('click', () => {
                step1.style.display = '';
                step2.style.display = 'none';
            });
            const createBtn = el('button', {}, 'Create Card');
            createBtn.addEventListener('click', async () => {
                syncFieldsToCard();
                const c = cardGenCard;
                const data = {
                    name: c.name || 'Untitled',
                    card_data: {
                        data: {
                            name: c.name || 'Untitled',
                            description: c.description || '',
                            personality: c.personality || '',
                            first_mes: c.first_mes || '',
                            mes_example: c.mes_example || '',
                            scenario: c.scenario || '',
                            tags: c.tags || [],
                        },
                    },
                };
                try {
                    await rpApi('POST', '/rp/cards', data);
                    rpLoadCards();
                    rpCenter.closeTab('card-gen', 'generator');
                } catch (e) {
                    createBtn.textContent = 'Failed: ' + e.message;
                    setTimeout(() => { createBtn.textContent = 'Create Card'; }, 2000);
                }
            });
            step2Actions.appendChild(backBtn);
            step2Actions.appendChild(createBtn);
            step2.appendChild(step2Actions);
        }
    },
};

// ===== RP: Scenarios =====

const rpScenarios = {
    async renderEditor(container, scenarioId) {
        container.textContent = '';
        let scenario = null;

        if (scenarioId !== null) {
            try {
                scenario = rpState.scenarios.find(s => s.id === scenarioId);
                if (!scenario) scenario = await rpApi('GET', '/rp/scenarios/' + scenarioId);
            } catch (e) {
                container.appendChild(el('div', { class: 'rp-error' }, 'Failed to load scenario: ' + e.message));
                return;
            }
        }

        const st = (scenario && scenario.settings) || {};
        const form = el('div', { class: 'rp-form' });
        form.appendChild(el('div', { class: 'rp-form-title' }, scenarioId ? 'Edit Scenario' : 'New Scenario'));

        // Basic fields
        const nameField = rpFormField('Name', 'input', scenario ? scenario.name : '');
        const descField = rpFormField('Description', 'textarea', scenario ? scenario.description : '', 4,
            'Supports ${user} and ${char} variables');
        const firstMsgField = rpFormField('First Message', 'textarea', scenario ? (scenario.first_message || '') : '', 3);

        form.appendChild(nameField.container);
        form.appendChild(descField.container);
        form.appendChild(firstMsgField.container);

        // Model override
        const modelFieldDiv = el('div', { class: 'rp-form-field' });
        modelFieldDiv.appendChild(el('label', {}, 'Model Override'));
        const modelSelect = document.createElement('select');
        await rpLoadModels();
        rpPopulateModelSelect(modelSelect, st.model || '');
        // Add "use default" option at start
        const defaultOpt = document.createElement('option');
        defaultOpt.value = '';
        defaultOpt.textContent = 'Use conversation default';
        modelSelect.insertBefore(defaultOpt, modelSelect.firstChild);
        if (!st.model) defaultOpt.selected = true;
        modelFieldDiv.appendChild(modelSelect);
        form.appendChild(modelFieldDiv);

        // Context strategy
        const ctxFieldDiv = el('div', { class: 'rp-form-field' });
        ctxFieldDiv.appendChild(el('label', {}, 'Context Strategy'));
        const ctxSelect = document.createElement('select');
        ['sliding_window', 'full_context'].forEach(v => {
            const opt = document.createElement('option');
            opt.value = v;
            opt.textContent = v;
            if (st.context_strategy === v) opt.selected = true;
            ctxSelect.appendChild(opt);
        });
        ctxFieldDiv.appendChild(ctxSelect);
        form.appendChild(ctxFieldDiv);

        // Think toggle
        const thinkFieldDiv = el('div', { class: 'rp-form-field rp-form-row' });
        const thinkCheckbox = document.createElement('input');
        thinkCheckbox.type = 'checkbox';
        thinkCheckbox.checked = !!st.think;
        thinkFieldDiv.appendChild(thinkCheckbox);
        thinkFieldDiv.appendChild(el('label', {}, 'Enable Thinking'));
        const thinkHint = el('span', { class: 'rp-form-hint' });
        const updateHint = () => {
            const val = modelSelect.value;
            if (!val) { thinkHint.textContent = ''; thinkCheckbox.disabled = false; return; }
            if (rpModelSupportsThink(val)) {
                thinkHint.textContent = 'supported by this model';
                thinkHint.style.color = 'var(--accent)';
                thinkCheckbox.disabled = false;
            } else {
                thinkHint.textContent = 'not supported by this model';
                thinkHint.style.color = '';
                thinkCheckbox.disabled = true;
                thinkCheckbox.checked = false;
            }
        };
        modelSelect.addEventListener('change', updateHint);
        updateHint();
        thinkFieldDiv.appendChild(thinkHint);
        form.appendChild(thinkFieldDiv);

        // Numeric settings
        const numericFields = [
            { key: 'repeat_penalty', label: 'Repeat Penalty', value: st.repeat_penalty },
            { key: 'temperature', label: 'Temperature', value: st.temperature },
            { key: 'min_p', label: 'Min-P', value: st.min_p },
            { key: 'top_k', label: 'Top-K', value: st.top_k },
            { key: 'repeat_last_n', label: 'Repeat Last N', value: st.repeat_last_n },
        ];

        const numericInputs = {};
        const numericRow = el('div', { class: 'rp-form-numeric-row' });
        numericFields.forEach(f => {
            const fieldDiv = el('div', { class: 'rp-form-field' });
            fieldDiv.appendChild(el('label', {}, f.label));
            const input = document.createElement('input');
            input.type = 'number';
            input.step = 'any';
            input.value = (f.value !== undefined && f.value !== null) ? f.value : '';
            fieldDiv.appendChild(input);
            numericInputs[f.key] = input;
            numericRow.appendChild(fieldDiv);
        });
        form.appendChild(numericRow);

        // Actions
        const actions = el('div', { class: 'rp-form-actions' });

        if (scenario) {
            const deleteBtn = el('button', { class: 'rp-form-delete' }, 'Delete');
            deleteBtn.addEventListener('click', () => {
                confirmAction(deleteBtn, async () => {
                    await rpApi('DELETE', '/rp/scenarios/' + scenario.id);
                    rpLoadScenarios();
                    rpCenter.closeTab('scenario', scenario.id);
                });
            });
            actions.appendChild(deleteBtn);
        }

        const saveBtn = el('button', {}, 'Save');
        saveBtn.addEventListener('click', async () => {
            const name = nameField.input.value.trim();
            if (!name) return;

            const settings = { context_strategy: ctxSelect.value };
            if (thinkCheckbox.checked) settings.think = true;
            const modelOverride = modelSelect.value;
            if (modelOverride) settings.model = modelOverride;

            // Parse numeric fields
            for (const [key, input] of Object.entries(numericInputs)) {
                const val = key.includes('top_k') || key.includes('repeat_last_n')
                    ? parseInt(input.value) : parseFloat(input.value);
                if (!isNaN(val)) settings[key] = val;
            }

            const data = {
                name,
                description: descField.input.value,
                first_message: firstMsgField.input.value,
                settings,
            };

            try {
                if (scenarioId) {
                    await rpApi('PUT', '/rp/scenarios/' + scenarioId, data);
                } else {
                    const created = await rpApi('POST', '/rp/scenarios', data);
                    rpCenter.closeTab('scenario', null);
                    rpCenter.openTab('scenario', created.id);
                }
                rpLoadScenarios();
            } catch (e) {
                saveBtn.textContent = 'Error: ' + e.message;
                setTimeout(() => { saveBtn.textContent = 'Save'; }, 2000);
            }
        });
        actions.appendChild(saveBtn);

        const cancelBtn = el('button', {}, 'Cancel');
        cancelBtn.addEventListener('click', () => rpCenter.closeTab('scenario', scenarioId));
        actions.appendChild(cancelBtn);

        form.appendChild(actions);
        container.appendChild(form);
    },
};

// Helper to create form fields consistently
function rpFormField(label, type, value, rows, hint) {
    const container = el('div', { class: 'rp-form-field' });
    container.appendChild(el('label', {}, label + (hint ? ' (' + hint + ')' : '')));
    let input;
    if (type === 'textarea') {
        input = document.createElement('textarea');
        if (rows) input.rows = rows;
    } else {
        input = document.createElement('input');
        input.type = 'text';
    }
    input.value = value || '';
    container.appendChild(input);
    return { container, input };
}

// ===== RP: New Chat Modal =====

const rpNewChatModal = {
    async open() {
        await Promise.all([rpLoadModels(), rpLoadCards(), rpLoadScenarios()]);

        const last = rpState.conversations.length > 0 ? rpState.conversations[0] : null;

        // Build modal overlay
        const overlay = el('div', { class: 'rp-modal', id: 'rp-new-chat-modal' });
        const content = el('div', { class: 'rp-modal-content' });
        content.appendChild(el('div', { class: 'rp-form-title' }, 'New Chat'));

        // Your Character
        const userField = el('div', { class: 'rp-form-field' });
        userField.appendChild(el('label', {}, 'Your Character'));
        const userSelect = document.createElement('select');
        rpState.cards.forEach(card => {
            const cardData = card.card_data.data || card.card_data;
            const opt = document.createElement('option');
            opt.value = card.id;
            opt.textContent = cardData.name || card.name;
            if (last && card.id === last.user_card_id) opt.selected = true;
            userSelect.appendChild(opt);
        });
        userField.appendChild(userSelect);
        content.appendChild(userField);

        // AI Character
        const aiField = el('div', { class: 'rp-form-field' });
        aiField.appendChild(el('label', {}, 'AI Character'));
        const aiSelect = document.createElement('select');
        rpState.cards.forEach(card => {
            const cardData = card.card_data.data || card.card_data;
            const opt = document.createElement('option');
            opt.value = card.id;
            opt.textContent = cardData.name || card.name;
            if (last && card.id === last.ai_card_id) opt.selected = true;
            aiSelect.appendChild(opt);
        });
        aiField.appendChild(aiSelect);
        content.appendChild(aiField);

        // Scenario (optional)
        const scenarioField = el('div', { class: 'rp-form-field' });
        scenarioField.appendChild(el('label', {}, 'Scenario (optional)'));
        const scenarioSelect = document.createElement('select');
        const noneOpt = document.createElement('option');
        noneOpt.value = '';
        noneOpt.textContent = 'None';
        scenarioSelect.appendChild(noneOpt);
        rpState.scenarios.forEach(s => {
            const opt = document.createElement('option');
            opt.value = s.id;
            opt.textContent = s.name;
            if (last && s.id === last.scenario_id) opt.selected = true;
            scenarioSelect.appendChild(opt);
        });
        scenarioField.appendChild(scenarioSelect);
        content.appendChild(scenarioField);

        // Model
        const modelField = el('div', { class: 'rp-form-field' });
        modelField.appendChild(el('label', {}, 'Model'));
        const modelSelect = document.createElement('select');
        rpPopulateModelSelect(modelSelect, last ? last.model : undefined);
        modelField.appendChild(modelSelect);
        content.appendChild(modelField);

        // Actions
        const actions = el('div', { class: 'rp-form-actions' });
        const createBtn = el('button', {}, 'Start Chat');
        createBtn.addEventListener('click', () => this.create(
            parseInt(userSelect.value),
            parseInt(aiSelect.value),
            scenarioSelect.value ? parseInt(scenarioSelect.value) : null,
            modelSelect.value
        ));
        const cancelBtn = el('button', {}, 'Cancel');
        cancelBtn.addEventListener('click', () => this.close());
        actions.appendChild(createBtn);
        actions.appendChild(cancelBtn);
        content.appendChild(actions);

        overlay.appendChild(content);

        // Close on backdrop click
        overlay.addEventListener('click', e => {
            if (e.target === overlay) this.close();
        });

        document.body.appendChild(overlay);
    },

    async create(userCardId, aiCardId, scenarioId, model) {
        if (!userCardId || !aiCardId || !model) return;

        this.close();

        // Show timer in center
        const contentArea = rpCenter.contentArea;
        if (contentArea) {
            contentArea.textContent = '';
            const timerStart = Date.now();
            const timerEl = el('div', { class: 'rp-placeholder' });
            const timerText = el('div', {}, 'Generating opening scene... 0s');
            timerEl.appendChild(timerText);
            contentArea.appendChild(timerEl);
            const timerInterval = setInterval(() => {
                timerText.textContent = 'Generating opening scene... ' +
                    Math.floor((Date.now() - timerStart) / 1000) + 's';
            }, 1000);

            try {
                const conv = await rpApi('POST', '/rp/conversations', {
                    user_card_id: userCardId,
                    ai_card_id: aiCardId,
                    scenario_id: scenarioId,
                    model: model,
                });
                clearInterval(timerInterval);
                await rpLoadConversations();
                rpCenter.openTab('chat', conv.id);
            } catch (e) {
                clearInterval(timerInterval);
                contentArea.textContent = '';
                contentArea.appendChild(el('div', { class: 'rp-error' }, 'Error creating conversation: ' + e.message));
            }
        }
    },

    close() {
        const modal = document.getElementById('rp-new-chat-modal');
        if (modal) modal.remove();
    },
};

// Wire "New" button from browser panel
rpState.on('new-chat-requested', () => rpNewChatModal.open());

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
