"use strict";

const element = id => document.getElementById(id);
const monthNames = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
function monthLabel(year, month) { return `${monthNames[month - 1]} ${year}`; }

async function call(url, options = {}, timeoutMs = 10000) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(url, {...options, signal: controller.signal});
    return {status: response.status, body: response.status === 204 ? null : await response.json()};
  } finally { clearTimeout(timeout); }
}

