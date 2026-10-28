"use strict";

const element = id => document.getElementById(id);

function confirmBeforeLeaving() {
  const message = typeof window.leaveWarning === "function" ? window.leaveWarning() : "";
  return !message || window.confirm(message);
}

async function call(url, options = {}, timeoutMs = 10000) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(url, {...options, signal: controller.signal});
    return {status: response.status, body: response.status === 204 ? null : await response.json()};
  } finally {
    clearTimeout(timeout);
  }
}

let csrfTokenPromise;
async function fetchCsrfToken({fresh = false} = {}) {
  if (fresh || !csrfTokenPromise) csrfTokenPromise = (async () => {
    const {status, body} = await call("/api/v1/auth/csrf", {headers: {Accept: "application/json"}, cache: "no-store"});
    if (status !== 200 || typeof body?.csrf_token !== "string" || !body.csrf_token) throw new Error("csrf");
    return body.csrf_token;
  })().catch(failure => {
    csrfTokenPromise = undefined;
    throw failure;
  });
  return csrfTokenPromise;
}

function wireWarningDialog({dialogId, confirmId, cancelId, onConfirm, isBusy}) {
  const dialog = element(dialogId);
  element(confirmId).addEventListener("click", () => { if (!isBusy()) return onConfirm(); });
  element(cancelId).addEventListener("click", () => { if (!isBusy()) dialog.close(); });
  dialog.addEventListener("cancel", event => { if (isBusy()) event.preventDefault(); });
  return dialog;
}

const monthNames = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

function monthLabel(year, month) {
  return `${monthNames[month - 1]} ${year}`;
}

function ordinal(number) {
  const suffix = [11, 12, 13].includes(number % 100) ? "th" : {1: "st", 2: "nd", 3: "rd"}[number % 10] ?? "th";
  return `${number}${suffix}`;
}

function longDate(iso) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  return match ? `${ordinal(Number(match[3]))} ${monthNames[Number(match[2]) - 1]} ${match[1]}` : iso;
}

function employmentSubheading(employment) {
  const started = `Employment started on ${longDate(employment.start_date)}`;
  return employment.end_date ? `${started} · ends on ${longDate(employment.end_date)}` : started;
}

function employeeCard(employment) {
  const card = document.createElement("li");
  card.className = "employee-card";
  const title = document.createElement("h3");
  title.textContent = employment.employee_name;
  const subheading = document.createElement("p");
  subheading.className = "subheading";
  subheading.textContent = employmentSubheading(employment);
  card.append(title, subheading);
  return card;
}

function formatMoney(value) {
  const match = /^(\d+)\.(\d{2})$/.exec(value);
  if (!match) throw new Error("money");
  return `CHF ${match[1].replace(/\B(?=(\d{3})+(?!\d))/g, ",")}.${match[2]}`;
}

function formatDuration(minutes) {
  if (!Number.isSafeInteger(minutes) || minutes < 0) throw new Error("duration");
  return `${Math.floor(minutes / 60)} h ${String(minutes % 60).padStart(2, "0")} min`;
}

function todoRows(person, withName = false) {
  const several = person.employments.length > 1;
  const rows = [];
  for (const employment of person.employments) {
    if (employment.months_due < 1 || !employment.next_month) continue;
    const month = monthLabel(employment.next_month.year, employment.next_month.month);
    const behind = employment.months_due > 1 ? ` (${employment.months_due} months behind)` : "";
    const enter = document.createElement("button");
    enter.type = "button";
    enter.textContent = "Enter";
    enter.setAttribute("aria-label", `Enter ${month} for ${person.name}`);
    enter.addEventListener("click", () => { if (confirmBeforeLeaving()) window.location.assign(`/timesheets?employment_id=${employment.id}`); });
    rows.push({
      label: `${withName ? person.name : "Timesheet"}${several ? ` · employment from ${longDate(employment.start_date)}` : ""}`,
      value: `${month}${behind}`,
      action: enter
    });
  }
  return rows;
}

function limitText(limit) {
  return `${formatMoney(limit.used)} of ${formatMoney(limit.limit)} used · ${formatMoney(limit.remaining)} remaining`;
}

function limitBar(limit, name) {
  const bar = document.createElement("progress");
  bar.className = "limit-bar";
  bar.max = Number(limit.limit);
  bar.value = Number(limit.used);
  bar.setAttribute("aria-label", `${name}: wage limit used`);
  return bar;
}

function cardRows(rows) {
  const table = document.createElement("table");
  table.className = "card-rows";
  const body = document.createElement("tbody");
  for (const {label, value, action} of rows) {
    const row = document.createElement("tr");
    const heading = document.createElement("th");
    heading.setAttribute("scope", "row");
    heading.textContent = label;
    const cell = document.createElement("td");
    if (typeof value === "string") cell.textContent = value;
    else cell.append(value);
    const actions = document.createElement("td");
    actions.className = "action";
    if (action) actions.append(action);
    row.append(heading, cell, actions);
    body.append(row);
  }
  table.append(body);
  return table;
}

function cardNote(text) {
  const note = document.createElement("p");
  note.className = "note";
  note.textContent = text;
  return note;
}
