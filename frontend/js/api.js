/**
 * api.js — All HTTP calls to the FastAPI backend.
 * No DOM access in this file — pure data fetching.
 */

const API = {
  async getLeads() {
    const r = await fetch('/admin/leads');
    if (!r.ok) throw new Error(`Failed to fetch leads: ${r.status}`);
    return r.json();
  },

  async getConversation(leadId) {
    const r = await fetch(`/admin/leads/${leadId}/conversation`);
    if (!r.ok) throw new Error(`Failed to fetch conversation: ${r.status}`);
    return r.json();
  },
};
