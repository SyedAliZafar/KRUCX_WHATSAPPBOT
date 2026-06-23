/**
 * app.js — UI state, rendering, and event handling.
 * Reads from API (api.js) and writes to the DOM only.
 */

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

const state = {
  leads: [],
  selectedLeadId: null,
  conv: null,           // { lead, messages }
  searchQuery: '',
  convMsgCount: 0,      // message count at last full render (for new-msg detection)
};

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------

function cleanPhone(p) {
  return (p || '').replace('whatsapp:', '');
}

function timeAgo(iso) {
  if (!iso) return '';
  const d = new Date(iso.endsWith('Z') ? iso : iso + 'Z');
  const diff = Math.floor((Date.now() - d) / 1000);
  if (diff < 60)    return `${diff}s`;
  if (diff < 3600)  return `${Math.floor(diff / 60)}m`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h`;
  return d.toLocaleDateString([], { month: 'short', day: 'numeric' });
}

function formatTime(iso) {
  if (!iso) return '';
  const d = new Date(iso.endsWith('Z') ? iso : iso + 'Z');
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function formatDate(iso) {
  if (!iso) return '';
  const d = new Date(iso.endsWith('Z') ? iso : iso + 'Z');
  const today = new Date();
  const yesterday = new Date(today); yesterday.setDate(today.getDate() - 1);
  if (d.toDateString() === today.toDateString())     return 'Today';
  if (d.toDateString() === yesterday.toDateString()) return 'Yesterday';
  return d.toLocaleDateString([], { weekday: 'long', month: 'long', day: 'numeric' });
}

function initials(name, phone) {
  if (name && name !== 'Unknown') {
    return name.trim().split(/\s+/).slice(0, 2).map(w => w[0]).join('').toUpperCase();
  }
  const p = cleanPhone(phone);
  return p ? p.slice(-2) : '?';
}

function avatarColor(str) {
  let h = 0;
  for (let i = 0; i < str.length; i++) h = str.charCodeAt(i) + (h << 5) - h;
  return `av-${Math.abs(h) % 8}`;
}

function scoreClass(s) {
  if (s >= 4) return 'high';
  if (s >= 2) return 'mid';
  return 'low';
}

function scoreLabel(s, escalated) {
  const label = s >= 4 ? '★ Qualified' : s >= 2 ? '◑ Warming' : '○ New';
  return escalated ? label + ' · Escalated ✓' : label;
}

function linkify(text) {
  return (text || '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/(https?:\/\/[^\s]+)/g, '<a href="$1" target="_blank" rel="noopener">$1</a>');
}

// Seen message counts — stored in localStorage to survive page refresh
function getSeenCount(leadId) {
  return parseInt(localStorage.getItem(`krucx_seen_${leadId}`) || '0', 10);
}

function setSeenCount(leadId, count) {
  localStorage.setItem(`krucx_seen_${leadId}`, String(count));
}

// ---------------------------------------------------------------------------
// Render: Sidebar lead cards
// ---------------------------------------------------------------------------

function renderLeads(leads) {
  const list = document.getElementById('lead-list');
  const query = state.searchQuery.toLowerCase();

  const filtered = query
    ? leads.filter(l =>
        (l.name || '').toLowerCase().includes(query) ||
        cleanPhone(l.phone_number).includes(query) ||
        (l.industry || '').toLowerCase().includes(query)
      )
    : leads;

  if (!filtered.length) {
    list.innerHTML = `<div style="padding:40px 20px;text-align:center;color:var(--text-secondary);font-size:14px">
      ${query ? 'No leads match your search.' : 'No leads yet.<br><span style="font-size:12px;color:var(--text-light)">They will appear here when prospects message your WhatsApp number.</span>'}
    </div>`;
    document.getElementById('lead-count').textContent = '';
    return;
  }

  document.getElementById('lead-count').textContent =
    `${filtered.length} lead${filtered.length !== 1 ? 's' : ''}`;

  list.innerHTML = filtered.map(lead => {
    const isActive  = lead.id === state.selectedLeadId;
    const sc        = scoreClass(lead.qualification_score);
    const av        = initials(lead.name, lead.phone_number);
    const color     = avatarColor(lead.phone_number || String(lead.id));
    const hasUnread = lead.turns_count > getSeenCount(lead.id) && !isActive;

    // Last message preview
    let preview = '';
    if (lead.last_message) {
      const prefix = lead.last_message_role === 'assistant' ? '<span class="bot-tag">Bot: </span>' : '';
      preview = prefix + (lead.last_message.length > 60
        ? lead.last_message.slice(0, 60) + '…'
        : lead.last_message);
    } else {
      preview = lead.main_problem
        ? lead.main_problem.slice(0, 60) + (lead.main_problem.length > 60 ? '…' : '')
        : '<span style="color:var(--text-light)">New conversation</span>';
    }

    return `
      <div class="lead-card ${isActive ? 'active' : ''} score-${sc === 'high' ? 'high' : sc === 'mid' ? 'mid' : 'low'}"
           data-id="${lead.id}" role="button" tabindex="0">
        <div class="lead-avatar ${color}">
          ${av}
          ${hasUnread ? '<div class="unread-dot"></div>' : ''}
        </div>
        <div class="lead-body">
          <div class="lead-row1">
            <span class="lead-name">${lead.name || cleanPhone(lead.phone_number)}</span>
            <span class="lead-time">${timeAgo(lead.updated_at)}</span>
          </div>
          <div class="lead-row2">
            <span class="lead-preview">${preview}</span>
            ${lead.industry ? `<span class="industry-tag">${lead.industry}</span>` : ''}
          </div>
        </div>
      </div>`;
  }).join('');

  // Attach click handlers
  list.querySelectorAll('.lead-card').forEach(card => {
    card.addEventListener('click', () => selectLead(Number(card.dataset.id)));
    card.addEventListener('keydown', e => {
      if (e.key === 'Enter' || e.key === ' ') selectLead(Number(card.dataset.id));
    });
  });
}

// ---------------------------------------------------------------------------
// Render: Conversation
// ---------------------------------------------------------------------------

function renderConversation(data, scrollToBottom = true) {
  const { lead, messages } = data;
  const sc = scoreClass(lead.qualification_score);

  // Header
  const av = initials(lead.name, lead.phone_number);
  const color = avatarColor(lead.phone_number || String(lead.id));
  document.getElementById('conv-avatar').className = `conv-avatar ${color}`;
  document.getElementById('conv-avatar').textContent = av;
  document.getElementById('conv-name').textContent = lead.name || cleanPhone(lead.phone_number);
  document.getElementById('conv-sub').textContent =
    [lead.industry, cleanPhone(lead.phone_number)].filter(Boolean).join(' · ');

  const scoreEl = document.getElementById('conv-score');
  scoreEl.className = `score-chip ${sc}`;
  scoreEl.textContent = scoreLabel(lead.qualification_score, lead.escalation_offered);

  // Profile strip
  const fields = [
    { label: 'Industry',     value: lead.industry },
    { label: 'Company type', value: lead.company_type },
    { label: 'Company size', value: lead.company_size },
    { label: 'Main problem', value: lead.main_problem },
    { label: 'Budget',       value: lead.budget },
    { label: 'Timeline',     value: lead.timeline },
    { label: 'Tools',        value: lead.current_tools
        ? (() => { try { return JSON.parse(lead.current_tools).join(', '); } catch { return lead.current_tools; } })()
        : null },
  ].filter(f => f.value);

  const pfEl = document.getElementById('profile-fields');
  pfEl.innerHTML = fields.length
    ? fields.map(f => `
        <div class="profile-field">
          <span class="profile-label">${f.label}</span>
          <span class="profile-value">${f.value}</span>
        </div>`).join('')
    : '<span style="color:var(--text-secondary);font-size:13px">No profile data collected yet</span>';

  // Messages
  const msgEl = document.getElementById('messages');
  const wasAtBottom = msgEl.scrollHeight - msgEl.scrollTop <= msgEl.clientHeight + 60;

  if (!messages.length) {
    msgEl.innerHTML = '<div style="text-align:center;color:var(--text-secondary);font-size:13px;padding:40px">No messages yet.</div>';
    return;
  }

  let html = '';
  let lastDate = '';

  messages.forEach(msg => {
    // Date divider
    const dateLabel = formatDate(msg.timestamp);
    if (dateLabel !== lastDate) {
      html += `<div class="date-divider"><span>${dateLabel}</span></div>`;
      lastDate = dateLabel;
    }

    const isBot = msg.role === 'assistant';
    const side  = isBot ? 'bot' : 'user';
    const time  = formatTime(msg.timestamp);

    html += `
      <div class="msg-row ${side}">
        <div class="bubble">
          <div class="bubble-text">${linkify(msg.content)}</div>
          <div class="bubble-time">${time}</div>
        </div>
      </div>`;
  });

  msgEl.innerHTML = html;

  if (scrollToBottom || wasAtBottom) {
    msgEl.scrollTop = msgEl.scrollHeight;
    hideBanner();
  } else {
    showBanner();
  }
}

function showBanner() {
  document.getElementById('new-msg-banner').style.display = 'block';
}

function hideBanner() {
  document.getElementById('new-msg-banner').style.display = 'none';
}

// ---------------------------------------------------------------------------
// Select a lead — load conversation, update UI
// ---------------------------------------------------------------------------

async function selectLead(leadId) {
  state.selectedLeadId = leadId;

  // Show conversation panel, hide empty state
  document.getElementById('empty-state').style.display = 'none';
  document.getElementById('conv-wrap').style.display = 'flex';
  document.getElementById('conv-wrap').style.flexDirection = 'column';

  // Re-render sidebar to update active highlight
  renderLeads(state.leads);

  try {
    const data = await API.getConversation(leadId);
    state.conv = data;
    state.convMsgCount = data.messages.length;
    renderConversation(data, true);
    setSeenCount(leadId, data.lead.turns_count);
    renderLeads(state.leads); // re-render to remove unread dot
  } catch (e) {
    console.error('Failed to load conversation', e);
  }

  // Set copy-phone button
  const lead = state.leads.find(l => l.id === leadId);
  document.getElementById('copy-phone-btn').onclick = () => {
    const phone = cleanPhone(lead?.phone_number || '');
    if (!phone) return;
    navigator.clipboard.writeText(phone).then(() => showToast('Phone number copied'));
  };
}

// ---------------------------------------------------------------------------
// Refresh: leads list (every 15s)
// ---------------------------------------------------------------------------

async function refreshLeads() {
  try {
    const leads = await API.getLeads();
    state.leads = leads;
    renderLeads(leads);
    document.getElementById('last-refresh').textContent =
      'Updated ' + new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  } catch (e) {
    console.error('Failed to refresh leads', e);
  }
}

// ---------------------------------------------------------------------------
// Refresh: active conversation (every 8s)
// ---------------------------------------------------------------------------

async function refreshConversation() {
  if (!state.selectedLeadId) return;
  try {
    const data = await API.getConversation(state.selectedLeadId);
    state.conv = data;

    const newCount = data.messages.length;
    const hasNew = newCount > state.convMsgCount;

    // Detect if user is scrolled near bottom before re-render
    const msgEl = document.getElementById('messages');
    const atBottom = msgEl.scrollHeight - msgEl.scrollTop <= msgEl.clientHeight + 80;

    renderConversation(data, atBottom);

    if (hasNew) {
      state.convMsgCount = newCount;
      setSeenCount(state.selectedLeadId, data.lead.turns_count);
      if (!atBottom) showBanner();
    }
  } catch (e) {
    console.error('Failed to refresh conversation', e);
  }
}

// ---------------------------------------------------------------------------
// Toast notification
// ---------------------------------------------------------------------------

function showToast(msg) {
  let toast = document.getElementById('copy-toast');
  if (!toast) {
    toast = document.createElement('div');
    toast.id = 'copy-toast';
    toast.className = 'copy-toast';
    document.body.appendChild(toast);
  }
  toast.textContent = msg;
  toast.classList.add('show');
  setTimeout(() => toast.classList.remove('show'), 2000);
}

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------

async function init() {
  // Initial load
  await refreshLeads();

  // Search
  document.getElementById('search').addEventListener('input', e => {
    state.searchQuery = e.target.value;
    renderLeads(state.leads);
  });

  // Manual refresh button
  document.getElementById('refresh-btn').addEventListener('click', refreshLeads);

  // New messages banner → scroll to bottom
  document.getElementById('new-msg-banner').addEventListener('click', () => {
    const msgEl = document.getElementById('messages');
    msgEl.scrollTop = msgEl.scrollHeight;
    hideBanner();
  });

  // Auto-refresh: leads every 15s, active conversation every 8s
  setInterval(refreshLeads, 15_000);
  setInterval(refreshConversation, 8_000);
}

document.addEventListener('DOMContentLoaded', init);
