/* ============================================================
   app.js — Company Manager API Layer
   Base URL: http://127.0.0.1:8000/api/
   ============================================================ */

const API_BASE = 'http://127.0.0.1:8000/api';
const ENDPOINTS = {
  companies:    `${API_BASE}/companies/`,
  company: (id) => `${API_BASE}/companies/${id}/`,
};

/* ============================================================
   TOAST NOTIFICATION SYSTEM
   ============================================================ */

function showToast(message, type = 'info') {
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    container.className = 'toast-container';
    document.body.appendChild(container);
  }

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `<div class="toast-dot"></div><span>${message}</span>`;
  container.appendChild(toast);

  // Auto-remove after 3.5s
  setTimeout(() => {
    toast.classList.add('toast-out');
    toast.addEventListener('animationend', () => toast.remove(), { once: true });
  }, 3500);
}

/* ============================================================
   LOADING STATE HELPERS
   ============================================================ */

/**
 * Show a full-area loading spinner inside a target element.
 * @param {HTMLElement} container
 */
function showLoading(container) {
  container.innerHTML = `
    <tr><td colspan="99">
      <div class="state-container">
        <div class="spinner"></div>
        <div class="state-title">Loading companies…</div>
      </div>
    </td></tr>`;
}

function showEmptyState(container, message = 'No companies found.', subtext = '') {
  container.innerHTML = `
    <tr><td colspan="99">
      <div class="state-container">
        <div class="state-icon">🏢</div>
        <div class="state-title">${message}</div>
        ${subtext ? `<div class="state-desc">${subtext}</div>` : ''}
        <a href="add-company.html" class="btn btn-primary btn-sm" style="margin-top:8px">+ Add Company</a>
      </div>
    </td></tr>`;
}

function showErrorState(container, message = 'Failed to load data.') {
  container.innerHTML = `
    <tr><td colspan="99">
      <div class="state-container">
        <div class="state-icon">⚠️</div>
        <div class="state-title">${message}</div>
        <div class="state-desc">Check that your Django backend is running at <code>${API_BASE}</code></div>
      </div>
    </td></tr>`;
}

/* ============================================================
   API FUNCTIONS
   ============================================================ */

/**
 * GET all companies
 * @returns {Promise<Array>} companies array
 */
async function fetchAllCompanies() {
  const response = await fetch(ENDPOINTS.companies, {
    method: 'GET',
    headers: { 'Content-Type': 'application/json' },
  });
  if (!response.ok) throw new Error(`HTTP ${response.status}: ${response.statusText}`);
  const data = await response.json();
  // Support both plain arrays and DRF paginated {results: [...]}
  return Array.isArray(data) ? data : (data.results ?? data);
}

/**
 * GET a single company by ID
 * @param {number|string} id
 * @returns {Promise<Object>} company object
 */
async function fetchCompanyById(id) {
  const response = await fetch(ENDPOINTS.company(id), {
    method: 'GET',
    headers: { 'Content-Type': 'application/json' },
  });
  if (!response.ok) throw new Error(`HTTP ${response.status}: ${response.statusText}`);
  return response.json();
}

/**
 * POST — create a new company
 * @param {Object} payload
 * @returns {Promise<Object>} created company
 */
async function createCompany(payload) {
  const response = await fetch(ENDPOINTS.companies, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw Object.assign(new Error(`HTTP ${response.status}`), { data: err, status: response.status });
  }
  return response.json();
}

/**
 * PUT — full update of a company
 * @param {number|string} id
 * @param {Object} payload
 * @returns {Promise<Object>} updated company
 */
async function updateCompany(id, payload) {
  const response = await fetch(ENDPOINTS.company(id), {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw Object.assign(new Error(`HTTP ${response.status}`), { data: err, status: response.status });
  }
  return response.json();
}

/**
 * PATCH — partial update of a company
 * @param {number|string} id
 * @param {Object} payload
 * @returns {Promise<Object>} updated company
 */
async function patchCompany(id, payload) {
  const response = await fetch(ENDPOINTS.company(id), {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw Object.assign(new Error(`HTTP ${response.status}`), { data: err, status: response.status });
  }
  return response.json();
}

/**
 * DELETE a company by ID
 * @param {number|string} id
 * @returns {Promise<void>}
 */
async function deleteCompany(id) {
  const response = await fetch(ENDPOINTS.company(id), {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json' },
  });
  if (!response.ok) throw new Error(`HTTP ${response.status}: ${response.statusText}`);
  // 204 No Content is the typical success — nothing to return
}

/* ============================================================
   UTILITY FUNCTIONS
   ============================================================ */

/**
 * Get URL query param
 * @param {string} name
 * @returns {string|null}
 */
function getParam(name) {
  return new URLSearchParams(window.location.search).get(name);
}

/**
 * Format ISO date string to human-readable
 * @param {string} iso
 * @returns {string}
 */
function formatDate(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('en-IN', {
    year: 'numeric', month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
}

/**
 * Get approval badge HTML
 * @param {string|boolean} approval
 * @returns {string}
 */
function approvalBadge(approval) {
  const v = String(approval).toLowerCase();
  if (v === 'true' || v === 'approved') {
    return `<span class="badge badge-approved">Approved</span>`;
  }
  if (v === 'false' || v === 'rejected') {
    return `<span class="badge badge-rejected">Rejected</span>`;
  }
  return `<span class="badge badge-pending">Pending</span>`;
}

/**
 * Escape HTML to prevent XSS
 * @param {any} str
 * @returns {string}
 */
function esc(str) {
  return String(str ?? '—')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/**
 * Get initials from company name for avatar
 * @param {string} name
 * @returns {string}
 */
function initials(name) {
  return (name || '?')
    .split(/\s+/)
    .slice(0, 2)
    .map(w => w[0])
    .join('')
    .toUpperCase();
}

/**
 * Set button loading state
 * @param {HTMLButtonElement} btn
 * @param {boolean} loading
 * @param {string} loadingText
 */
function setBtnLoading(btn, loading, loadingText = 'Processing…') {
  if (loading) {
    btn._originalText = btn.innerHTML;
    btn.innerHTML = `<span class="spinner" style="width:16px;height:16px;border-width:2px"></span> ${loadingText}`;
    btn.disabled = true;
  } else {
    btn.innerHTML = btn._originalText || 'Submit';
    btn.disabled = false;
  }
}

/**
 * Show inline field validation error
 * @param {string} fieldId
 * @param {string} message
 */
function showFieldError(fieldId, message) {
  const field = document.getElementById(fieldId);
  if (field) field.classList.add('error');
  const errEl = document.getElementById(`${fieldId}-error`);
  if (errEl) errEl.textContent = message;
}

/**
 * Clear all field errors in the form
 */
function clearFieldErrors() {
  document.querySelectorAll('.form-control.error').forEach(el => el.classList.remove('error'));
  document.querySelectorAll('.field-error').forEach(el => el.textContent = '');
}

/**
 * Show server-returned field errors (DRF format)
 * @param {Object} errData — {field: ["message"]}
 */
function applyServerErrors(errData) {
  if (!errData || typeof errData !== 'object') return;
  for (const [field, msgs] of Object.entries(errData)) {
    const message = Array.isArray(msgs) ? msgs.join(' ') : String(msgs);
    showFieldError(field, message);
  }
}

/* ============================================================
   MODAL (delete confirmation)
   ============================================================ */

let _deleteCallback = null;

function openDeleteModal(companyName, onConfirm) {
  const overlay = document.getElementById('delete-modal');
  if (!overlay) return;
  overlay.querySelector('.company-name-confirm').textContent = companyName;
  overlay.classList.add('active');
  _deleteCallback = onConfirm;
}

function closeDeleteModal() {
  const overlay = document.getElementById('delete-modal');
  if (overlay) overlay.classList.remove('active');
  _deleteCallback = null;
}

// Wire up modal buttons once DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  const overlay = document.getElementById('delete-modal');
  if (!overlay) return;

  overlay.querySelector('#modal-cancel')?.addEventListener('click', closeDeleteModal);
  overlay.querySelector('#modal-confirm')?.addEventListener('click', async () => {
    if (_deleteCallback) await _deleteCallback();
    closeDeleteModal();
  });

  // Close on backdrop click
  overlay.addEventListener('click', (e) => { if (e.target === overlay) closeDeleteModal(); });
});