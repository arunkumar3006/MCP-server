/**
 * Email MCP Studio — Frontend Controller
 * Fully responsive: desktop, tablet, and mobile adaptive.
 */

const API_BASE = "";
let currentFilter = "all";
let searchDebounceTimer = null;
let countdownInterval = null;
let allEmailsCache = [];

// DOM Elements
const statTotal = document.getElementById("statTotal");
const statPending = document.getElementById("statPending");
const statSent = document.getElementById("statSent");
const statFailed = document.getElementById("statFailed");
const countAll = document.getElementById("countAll");
const countPending = document.getElementById("countPending");
const countSent = document.getElementById("countSent");
const providersList = document.getElementById("providersList");
const emailTableBody = document.getElementById("emailTableBody");
const searchInput = document.getElementById("searchInput");
const filterBtns = document.querySelectorAll(".filter-btn");

// Compose Modal
const composeModal = document.getElementById("composeModal");
const openComposeBtn = document.getElementById("openComposeBtn");
const closeComposeBtn = document.getElementById("closeComposeBtn");
const cancelComposeBtn = document.getElementById("cancelComposeBtn");
const composeForm = document.getElementById("composeForm");
const recipientInput = document.getElementById("recipientInput");
const subjectInput = document.getElementById("subjectInput");
const providerSelect = document.getElementById("providerSelect");
const formatSelect = document.getElementById("formatSelect");
const bodyInput = document.getElementById("bodyInput");
const previewArea = document.getElementById("previewArea");
const tabWrite = document.getElementById("tabWrite");
const tabPreview = document.getElementById("tabPreview");
const chipMyself = document.getElementById("chipMyself");
const timingChips = document.querySelectorAll(".timing-chip");
const timeExpressionInput = document.getElementById("timeExpressionInput");
const datetimePicker = document.getElementById("datetimePicker");
const submitComposeBtn = document.getElementById("submitComposeBtn");
const submitBtnText = document.getElementById("submitBtnText");

// Details Modal
const detailsModal = document.getElementById("detailsModal");
const closeDetailsBtn = document.getElementById("closeDetailsBtn");
const closeDetailsBtnFooter = document.getElementById("closeDetailsBtnFooter");
const detailSubject = document.getElementById("detailSubject");
const detailJobId = document.getElementById("detailJobId");
const detailRecipient = document.getElementById("detailRecipient");
const detailStatus = document.getElementById("detailStatus");
const detailScheduledTime = document.getElementById("detailScheduledTime");
const detailProvider = document.getElementById("detailProvider");
const detailSentAt = document.getElementById("detailSentAt");
const detailError = document.getElementById("detailError");
const errorRow = document.getElementById("errorRow");
const detailBody = document.getElementById("detailBody");

const refreshBtn = document.getElementById("refreshBtn");
const toastContainer = document.getElementById("toastContainer");

// Selected timing state ('now' | expression string)
let selectedTiming = "in 15 minutes";

// Initialize
document.addEventListener("DOMContentLoaded", () => {
  setupEventListeners();
  loadStats();
  loadEmails();
  
  // Set default timing chip
  setTimingChip("in 15 minutes");

  // Auto-refresh every 4 seconds
  setInterval(() => {
    loadStats(true);
    loadEmails(true);
  }, 4000);

  // Live countdown ticker every second
  countdownInterval = setInterval(updateCountdowns, 1000);
});

function setupEventListeners() {
  // Filter tabs
  filterBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      filterBtns.forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      currentFilter = btn.dataset.status;
      loadEmails();
    });
  });

  // Search with debounce
  searchInput.addEventListener("input", () => {
    clearTimeout(searchDebounceTimer);
    searchDebounceTimer = setTimeout(() => {
      loadEmails();
    }, 300);
  });

  // Refresh Button
  refreshBtn.addEventListener("click", () => {
    refreshBtn.classList.add("rotating");
    Promise.all([loadStats(), loadEmails()]).finally(() => {
      setTimeout(() => refreshBtn.classList.remove("rotating"), 500);
      showToast("Data refreshed", "info");
    });
  });

  // Compose Modal open/close
  openComposeBtn.addEventListener("click", () => openModal(composeModal));
  closeComposeBtn.addEventListener("click", () => closeModal(composeModal));
  cancelComposeBtn.addEventListener("click", () => closeModal(composeModal));

  // Quick recipient shortcut
  chipMyself.addEventListener("click", () => {
    recipientInput.value = "arunraghav3006@gmail.com";
    showToast("Added your email address", "info");
  });

  // Timing chips
  timingChips.forEach(chip => {
    chip.addEventListener("click", () => {
      const val = chip.dataset.time;
      setTimingChip(val);
    });
  });

  timeExpressionInput.addEventListener("input", () => {
    if (timeExpressionInput.value.trim()) {
      clearTimingChipActive();
      selectedTiming = timeExpressionInput.value.trim();
      submitBtnText.textContent = "Schedule Email";
      datetimePicker.value = "";
    }
  });

  datetimePicker.addEventListener("change", () => {
    if (datetimePicker.value) {
      clearTimingChipActive();
      selectedTiming = datetimePicker.value;
      submitBtnText.textContent = "Schedule Email";
      timeExpressionInput.value = "";
    }
  });

  // Body Write/Preview tabs
  tabWrite.addEventListener("click", () => {
    tabWrite.classList.add("active");
    tabPreview.classList.remove("active");
    bodyInput.classList.remove("hidden");
    previewArea.classList.add("hidden");
  });

  tabPreview.addEventListener("click", () => {
    tabPreview.classList.add("active");
    tabWrite.classList.remove("active");
    bodyInput.classList.add("hidden");
    previewArea.classList.remove("hidden");
    renderBodyPreview();
  });

  // Form submit
  composeForm.addEventListener("submit", handleFormSubmit);

  // Details Modal close
  closeDetailsBtn.addEventListener("click", () => closeModal(detailsModal));
  closeDetailsBtnFooter.addEventListener("click", () => closeModal(detailsModal));
}

function setTimingChip(val) {
  timingChips.forEach(c => {
    if (c.dataset.time === val) {
      c.classList.add("active");
    } else {
      c.classList.remove("active");
    }
  });

  selectedTiming = val;
  if (val === "now") {
    timeExpressionInput.value = "";
    datetimePicker.value = "";
    submitBtnText.textContent = "⚡ Send Immediately";
  } else {
    timeExpressionInput.value = val;
    datetimePicker.value = "";
    submitBtnText.textContent = "Schedule Email";
  }
}

function clearTimingChipActive() {
  timingChips.forEach(c => c.classList.remove("active"));
}

function renderBodyPreview() {
  const content = bodyInput.value;
  const isHtml = formatSelect.value === "html";
  if (!content.trim()) {
    previewArea.innerHTML = "<span style='color:#6B7280;'>No content to preview yet.</span>";
    return;
  }
  if (isHtml) {
    previewArea.innerHTML = content;
  } else {
    previewArea.textContent = content;
  }
}

function openModal(modal) {
  modal.classList.add("active");
  document.body.style.overflow = "hidden"; // Prevent background scroll on mobile
}

function closeModal(modal) {
  modal.classList.remove("active");
  document.body.style.overflow = "";
}

// -------------------------------------------------------------
// API Calls & Data Fetching
// -------------------------------------------------------------

async function loadStats(silent = false) {
  try {
    const res = await fetch(`${API_BASE}/api/stats`);
    if (!res.ok) throw new Error("Failed to load statistics");
    const data = await res.json();

    statTotal.textContent = data.total;
    statPending.textContent = data.pending;
    statSent.textContent = data.sent;
    statFailed.textContent = (data.failed || 0) + (data.cancelled || 0);

    countAll.textContent = data.total;
    countPending.textContent = data.pending;
    countSent.textContent = data.sent;

    renderProviders(data.providers);
  } catch (err) {
    if (!silent) console.error("Error loading stats:", err);
  }
}

function renderProviders(providers) {
  if (!providers) return;
  providersList.innerHTML = "";

  // Gmail SMTP
  const smtp = providers.smtp;
  const smtpPill = document.createElement("div");
  smtpPill.className = `provider-pill ${smtp.configured ? "active" : "inactive"}`;
  smtpPill.innerHTML = `
    <span class="dot" style="background:${smtp.configured ? '#10b981' : '#6b7280'}"></span>
    <span>Gmail SMTP: ${smtp.configured ? smtp.user : "Not configured"}</span>
  `;
  providersList.appendChild(smtpPill);

  // Resend API
  const resend = providers.resend;
  const resendPill = document.createElement("div");
  resendPill.className = `provider-pill ${resend.configured ? "active" : "inactive"}`;
  resendPill.innerHTML = `
    <span class="dot" style="background:${resend.configured ? '#10b981' : '#6b7280'}"></span>
    <span>Resend: ${resend.configured ? (resend.from || "Ready") : "Inactive"}</span>
  `;
  providersList.appendChild(resendPill);

  // Database
  const dbPill = document.createElement("div");
  dbPill.className = "provider-pill active";
  dbPill.innerHTML = `
    <span class="dot"></span>
    <span>SQLite Engine: Active</span>
  `;
  providersList.appendChild(dbPill);
}

async function loadEmails(silent = false) {
  try {
    const search = searchInput.value.trim();
    const query = new URLSearchParams({
      status: currentFilter,
      search: search,
      limit: 100
    });

    const res = await fetch(`${API_BASE}/api/emails?${query.toString()}`);
    if (!res.ok) throw new Error("Failed to fetch emails");
    const emails = await res.json();
    allEmailsCache = emails;

    renderEmailTable(emails);
  } catch (err) {
    if (!silent) console.error("Error loading emails:", err);
  }
}

function renderEmailTable(emails) {
  if (!emails || emails.length === 0) {
    emailTableBody.innerHTML = `
      <tr>
        <td colspan="7" class="empty-state">
          No emails found matching the criteria. Click "+ Compose / Schedule" to create one!
        </td>
      </tr>
    `;
    return;
  }

  emailTableBody.innerHTML = emails.map(email => {
    const statusClass = email.status.toLowerCase();
    const isPending = statusClass === "pending";
    const schedDate = new Date(email.scheduled_time);
    const createdDate = new Date(email.created_at);

    return `
      <tr class="email-row" data-job-id="${email.id}" data-scheduled-utc="${email.scheduled_time}">
        <td class="cell-status" data-label="Status">
          <span class="status-badge ${statusClass}">
            <span class="dot"></span>
            ${email.status}
          </span>
        </td>
        <td class="cell-recipient" data-label="Recipient">
          <div class="recipient-wrapper">
            <span class="mobile-field-label">To:</span>
            <span class="table-recipient">${escapeHtml(email.recipient)}</span>
          </div>
        </td>
        <td class="cell-subject" data-label="Subject">
          <div class="table-subject" title="${escapeHtml(email.subject)}">
            ${escapeHtml(email.subject)}
          </div>
        </td>
        <td class="cell-time" data-label="Scheduled Time">
          <div class="time-main">${formatDateTime(schedDate)}</div>
          ${isPending ? `<div class="countdown-chip countdown-val">Calculating...</div>` : ""}
        </td>
        <td class="cell-provider" data-label="Provider">
          <div class="provider-wrapper">
            <span class="mobile-field-label">Via:</span>
            <span class="provider-tag">${escapeHtml(email.provider || "auto")}</span>
          </div>
        </td>
        <td class="cell-created" data-label="Created">
          <span class="created-time">${formatRelativeTime(createdDate)}</span>
        </td>
        <td class="cell-actions" data-label="Actions">
          <div class="table-actions">
            <button class="action-btn" title="View Details" onclick="viewEmailDetails('${email.id}')">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                <circle cx="12" cy="12" r="3"></circle>
              </svg>
            </button>
            ${isPending ? `
              <button class="action-btn cancel-btn" title="Cancel Scheduled Email" onclick="cancelEmailJob('${email.id}')">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <line x1="18" y1="6" x2="6" y2="18"></line>
                  <line x1="6" y1="6" x2="18" y2="18"></line>
                </svg>
              </button>
            ` : ""}
          </div>
        </td>
      </tr>
    `;
  }).join("");

  updateCountdowns();
}

function updateCountdowns() {
  const rows = emailTableBody.querySelectorAll("tr[data-scheduled-utc]");
  const now = new Date();

  rows.forEach(row => {
    const chip = row.querySelector(".countdown-val");
    if (!chip) return;

    const schedUtc = row.dataset.scheduledUtc;
    const schedTime = new Date(schedUtc);
    const diffMs = schedTime - now;

    if (diffMs <= 0) {
      chip.textContent = "⚡ Dispatching now...";
      chip.style.borderColor = "rgba(16, 185, 129, 0.5)";
      chip.style.color = "#34d399";
    } else {
      const totalSec = Math.floor(diffMs / 1000);
      const hours = Math.floor(totalSec / 3600);
      const minutes = Math.floor((totalSec % 3600) / 60);
      const seconds = totalSec % 60;

      let text = "Sends in ";
      if (hours > 0) text += `${hours}h `;
      if (minutes > 0 || hours > 0) text += `${minutes}m `;
      text += `${seconds}s`;

      chip.textContent = text;
    }
  });
}

// -------------------------------------------------------------
// Form Submission (Send Now vs Schedule)
// -------------------------------------------------------------

async function handleFormSubmit(e) {
  e.preventDefault();

  const recipient = recipientInput.value.trim();
  const subject = subjectInput.value.trim();
  const body = bodyInput.value.trim();
  const provider = providerSelect.value;
  const isHtml = formatSelect.value === "html";

  if (!recipient || !subject || !body) {
    showToast("Please fill in all required fields", "error");
    return;
  }

  submitComposeBtn.disabled = true;
  const originalText = submitBtnText.textContent;
  submitBtnText.textContent = "Processing...";

  try {
    if (selectedTiming === "now") {
      // Immediate Send
      const res = await fetch(`${API_BASE}/api/send-now`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ recipient, subject, body, is_html: isHtml, provider })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Failed to send email");

      showToast(`Email delivered immediately to ${recipient}!`, "success");
    } else {
      // Schedule Delivery
      const timeVal = timeExpressionInput.value.trim() || datetimePicker.value || selectedTiming;
      const res = await fetch(`${API_BASE}/api/schedule`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          recipient,
          subject,
          body,
          scheduled_time: timeVal,
          is_html: isHtml,
          provider
        })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Failed to schedule email");

      showToast(data.message || "Email scheduled successfully!", "success");
    }

    // Reset and close
    composeForm.reset();
    setTimingChip("in 15 minutes");
    closeModal(composeModal);
    loadStats();
    loadEmails();
  } catch (err) {
    showToast(err.message, "error");
  } finally {
    submitComposeBtn.disabled = false;
    submitBtnText.textContent = originalText;
  }
}

// -------------------------------------------------------------
// Email Details & Cancel Actions
// -------------------------------------------------------------

window.viewEmailDetails = async function(jobId) {
  try {
    const res = await fetch(`${API_BASE}/api/emails/${jobId}`);
    if (!res.ok) throw new Error("Could not fetch email details");
    const email = await res.json();

    detailSubject.textContent = email.subject;
    detailJobId.textContent = `Job ID: ${email.id}`;
    detailRecipient.textContent = email.recipient;
    detailStatus.innerHTML = `<span class="status-badge ${email.status}">${email.status}</span>`;
    detailScheduledTime.textContent = new Date(email.scheduled_time).toLocaleString();
    detailProvider.textContent = email.provider || "auto";
    detailSentAt.textContent = email.sent_at ? new Date(email.sent_at).toLocaleString() : "Not sent yet";

    if (email.error_message) {
      errorRow.style.display = "flex";
      detailError.textContent = email.error_message;
    } else {
      errorRow.style.display = "none";
    }

    if (email.is_html) {
      detailBody.innerHTML = email.body;
    } else {
      detailBody.textContent = email.body;
    }

    openModal(detailsModal);
  } catch (err) {
    showToast(err.message, "error");
  }
};

window.cancelEmailJob = async function(jobId) {
  if (!confirm(`Are you sure you want to cancel scheduled email '${jobId}'?`)) {
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/api/cancel/${jobId}`, { method: "POST" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Failed to cancel email");

    showToast(data.message || "Email cancelled successfully", "success");
    loadStats();
    loadEmails();
  } catch (err) {
    showToast(err.message, "error");
  }
};

// -------------------------------------------------------------
// Utilities & Toast System
// -------------------------------------------------------------

function showToast(message, type = "info") {
  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  
  let iconSvg = "";
  if (type === "success") {
    iconSvg = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>`;
  } else if (type === "error") {
    iconSvg = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>`;
  } else {
    iconSvg = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#06b6d4" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>`;
  }

  toast.innerHTML = `${iconSvg}<span>${escapeHtml(message)}</span>`;
  toastContainer.appendChild(toast);

  setTimeout(() => {
    toast.style.animation = "slide-in 0.3s ease reverse forwards";
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

function escapeHtml(str) {
  if (!str) return "";
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

function formatDateTime(date) {
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit"
  });
}

function formatRelativeTime(date) {
  const diffSec = Math.floor((new Date() - date) / 1000);
  if (diffSec < 60) return "just now";
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`;
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`;
  return `${Math.floor(diffSec / 86400)}d ago`;
}
