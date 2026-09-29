/**
 * api.js - thin fetch wrapper shared by every page.
 * Centralizes JSON handling, credentials and error surfacing so each
 * page's script only has to deal with plain JS objects / arrays.
 */
const Api = {
  async _req(method, url, body) {
    const opts = {
      method,
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
    };
    if (body !== undefined) opts.body = JSON.stringify(body);
    const res = await fetch(url, opts);
    let data = null;
    try { data = await res.json(); } catch (e) { /* no body */ }
    if (!res.ok) {
      const err = new Error((data && data.error) || `Request failed (${res.status})`);
      err.status = res.status;
      throw err;
    }
    return data;
  },
  get(url) { return this._req("GET", url); },
  post(url, body) { return this._req("POST", url, body); },
  put(url, body) { return this._req("PUT", url, body); },
  del(url) { return this._req("DELETE", url); },
};

function fmtMoney(n) {
  return "₹" + Number(n || 0).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function fmtDate(s) {
  if (!s) return "-";
  return s.split("T")[0];
}

function escapeHtml(str) {
  if (str === null || str === undefined) return "";
  return String(str)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function badge(text, color) {
  return `<span class="badge ${color}">${escapeHtml(text)}</span>`;
}

function statusColor(status) {
  const map = {
    Scheduled: "blue", Completed: "green", Cancelled: "red", "No-Show": "gray",
    Paid: "green", Unpaid: "red", "Partially Paid": "yellow", "Insurance Pending": "yellow",
    Available: "green", Occupied: "red", Cleaning: "yellow", Maintenance: "gray",
    Pending: "yellow", Dispensed: "green",
    Ordered: "blue", "Sample Collected": "yellow", "In Progress": "yellow",
  };
  return map[status] || "gray";
}

/** Redirect to login if the session has expired mid-use. */
function handleAuthError(err) {
  if (err.status === 401) {
    window.location.href = "/login";
    return true;
  }
  return false;
}
