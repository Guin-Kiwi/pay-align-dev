"use strict";

const PAYSLIP_PAGE = "/payslips";
const TIMESHEETS_PAGE = "/timesheets";
const SAVED_DETAIL = "The payroll was saved, but its confirmation could not be loaded. Check the saved month before retrying.";
let csrfToken = null;
let employments = [];
let selectedEmployment = null;
let nextMonth = null;
let monthStart = "";
let monthEnd = "";
let submitting = false;
let submissionLocked = false;
let entries = [];
let holidays = new Set();
let savedPayslipUrl = "";
let hoursTouched = false;
let committedBonus = "0.00";
let committedExpenses = "0.00";

function payslipUrl(employmentId, year, month) {
  return `${PAYSLIP_PAGE}?employment_id=${employmentId}&year=${year}&month=${month}`;
}

function setMessage(id, text) {
  element(id).textContent = text;
  element(id).hidden = !text;
}

function showError(message, id = "page-error") {
  setMessage(id, message);
}

function showLoginMessage(message, id = "page-error") {
  const container = element(id);
  container.textContent = `${message} `;
  const button = document.createElement("button");
  button.type = "button";
  button.textContent = "Open the login page";
  button.addEventListener("click", () => window.location.assign("/login"));
  container.append(button);
  container.hidden = false;
}

function responseError(body) {
  if (typeof body?.detail === "string") return body.detail;
  if (Array.isArray(body?.detail)) return body.detail.map(item => item?.msg ?? "Invalid input.").join("\n");
  return "Please check the entered values and try again.";
}

function toMinutes(time) {
  const [hours, minutes] = time.split(":").map(Number);
  return hours * 60 + minutes;
}

function parseHours(text) {
  const match = /^(\d{1,2}):([0-5]\d)$/.exec(text);
  return match ? Number(match[1]) * 60 + Number(match[2]) : NaN;
}

function formatHours(minutes) {
  return `${Math.floor(minutes / 60)}:${String(minutes % 60).padStart(2, "0")}`;
}

function hoursText(minutes) {
  return `${Math.floor(minutes / 60)} h ${String(minutes % 60).padStart(2, "0")} min`;
}

function scheduleMinutes() {
  const start = element("pattern-start").value;
  const end = element("pattern-end").value;
  const pause = Number(element("pattern-break").value || 0);
  if (!start || !end || !Number.isInteger(pause) || pause < 0) return 0;
  return Math.max(0, toMinutes(end) - toMinutes(start) - pause);
}

function syncHoursField() {
  if (hoursTouched) return;
  const minutes = scheduleMinutes();
  element("holiday-hours").value = minutes ? formatHours(minutes) : "";
}

// An entry is a worked day or an annual holiday day. Whether a date is a public holiday comes from
// the holiday dates the server serves from constants.py; the person only says worked or taken.
const isHoliday = entry => holidays.has(entry.work_date);
const takenDayOff = entry => isHoliday(entry) && entry.holidayChoice === "taken";
const hasTimes = entry => entry.kind === "worked" && !takenDayOff(entry);

function newWorkedDay(date, start = "", end = "", pause = 0) {
  return {work_date: date, kind: "worked", start_time: start, end_time: end, unpaid_break_minutes: pause, paid_minutes: 0, holidayChoice: null};
}

function minutesFor(entry) {
  if (!hasTimes(entry)) return Number(entry.paid_minutes);
  if (!entry.start_time || !entry.end_time) return NaN;
  return toMinutes(entry.end_time) - toMinutes(entry.start_time) - Number(entry.unpaid_break_minutes);
}

function minutesText(entry) {
  const minutes = minutesFor(entry);
  return Number.isFinite(minutes) && minutes >= 0 ? String(minutes) : "—";
}

function updateControls() {
  element("save-payroll").disabled = !csrfToken || !selectedEmployment || !nextMonth || submitting || submissionLocked;
}

function amountText(text) {
  const match = /^(\d+)(?:\.(\d{1,2}))?$/.exec(text.trim() || "0");
  return match ? `${match[1]}.${(match[2] ?? "").padEnd(2, "0")}` : null;
}

function bonusPending() {
  return amountText(element("cash-bonus").value) !== committedBonus || amountText(element("expense-reimbursements").value) !== committedExpenses;
}

function updateExtras() {
  element("entry-extras").textContent = `Cash bonus: CHF ${committedBonus} · Expenses: CHF ${committedExpenses}`;
}

function addBonus() {
  const bonus = amountText(element("cash-bonus").value);
  const expenses = amountText(element("expense-reimbursements").value);
  if (bonus === null || expenses === null) {
    setMessage("bonus-error", "Enter amounts in CHF with at most two decimals.");
    return;
  }
  committedBonus = bonus;
  committedExpenses = expenses;
  element("cash-bonus").value = bonus;
  element("expense-reimbursements").value = expenses;
  setMessage("bonus-error", "");
  updateExtras();
}

function hasUnsavedWork() {
  return !submissionLocked && (entries.length > 0 || committedBonus !== "0.00" || committedExpenses !== "0.00" || bonusPending());
}

window.leaveWarning = () => (selectedEmployment && !element("entry-section").hidden && hasUnsavedWork() ? "Discard the entries and leave this page?" : "");

function updateTotals() {
  const totals = {worked: 0, holidayWork: 0, annual: 0, taken: 0};
  let undecided = 0;
  for (const entry of entries) {
    if (isHoliday(entry) && entry.kind === "worked" && entry.holidayChoice === null) { undecided++; continue; }
    const minutes = minutesFor(entry);
    if (!Number.isFinite(minutes) || minutes < 0) continue;
    if (entry.kind === "annual") totals.annual += minutes;
    else if (takenDayOff(entry)) totals.taken += minutes;
    else if (isHoliday(entry)) totals.holidayWork += minutes;
    else totals.worked += minutes;
  }
  const decide = undecided ? ` · ${undecided} public holiday${undecided === 1 ? "" : "s"} to decide` : "";
  element("entry-totals").textContent = `Worked: ${totals.worked} min · Public holiday work: ${totals.holidayWork} min · Annual holiday: ${totals.annual} min · Paid public holiday: ${totals.taken} min${decide}`;
}

function textCell(text) {
  const item = document.createElement("td");
  item.textContent = text;
  return item;
}

function cell(...content) {
  const item = document.createElement("td");
  item.append(...content);
  return item;
}

function removeEntry(entry) {
  const index = entries.indexOf(entry);
  if (index >= 0) entries.splice(index, 1);
  setMessage("table-message", "");
  renderEntries();
}

function changeKind(entry, kind) {
  if (kind === "annual") {
    if (entries.some(other => other !== entry && other.work_date === entry.work_date)) {
      renderEntries();
      setMessage("table-message", "Another entry on this date must be removed first.");
      return;
    }
    const minutes = minutesFor(entry);
    entry.paid_minutes = Number.isFinite(minutes) && minutes > 0 ? minutes : scheduleMinutes();
    entry.kind = "annual";
  } else {
    entry.kind = "worked";
    if (!entry.start_time && !entry.end_time) {
      entry.start_time = element("pattern-start").value;
      entry.end_time = element("pattern-end").value;
      entry.unpaid_break_minutes = Number(element("pattern-break").value || 0);
    }
  }
  setMessage("table-message", "");
  renderEntries();
}

function chooseHoliday(entry, choice, checked) {
  entry.holidayChoice = checked ? choice : null;
  if (checked && choice === "taken" && !(Number(entry.paid_minutes) > 0)) entry.paid_minutes = scheduleMinutes();
  renderEntries();
}

function checkLabel(entry, choice, text) {
  const label = document.createElement("label");
  label.className = "check";
  const box = document.createElement("input");
  box.type = "checkbox";
  box.checked = entry.holidayChoice === choice;
  box.addEventListener("change", () => chooseHoliday(entry, choice, box.checked));
  const caption = document.createElement("span");
  caption.textContent = text;
  label.append(box, caption);
  return label;
}

function buildRow(entry) {
  const holiday = isHoliday(entry);
  const undecided = holiday && entry.kind === "worked" && entry.holidayChoice === null;
  const timed = hasTimes(entry);
  const row = document.createElement("tr");
  row.className = [holiday ? "holiday" : "", undecided ? "undecided" : ""].filter(Boolean).join(" ");
  let paidCell;
  const input = (key, type, label) => {
    const field = document.createElement("input");
    field.type = type;
    field.value = String(entry[key] ?? "");
    field.setAttribute("aria-label", `${label} for ${entry.work_date}`);
    if (type === "number") { field.min = "0"; field.step = "1"; }
    field.addEventListener("input", () => {
      entry[key] = field.value;
      if (timed) paidCell.textContent = minutesText(entry);
      updateTotals();
    });
    return field;
  };
  paidCell = timed ? textCell(minutesText(entry)) : cell(input("paid_minutes", "number", "Paid minutes"));
  let typeCell;
  if (holiday) {
    typeCell = textCell("Public holiday");
  } else {
    const select = document.createElement("select");
    for (const [value, text] of [["worked", "Worked"], ["annual", "Annual holiday"]]) {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = text;
      select.append(option);
    }
    select.value = entry.kind;
    select.setAttribute("aria-label", `Type for ${entry.work_date}`);
    select.addEventListener("change", () => changeKind(entry, select.value));
    typeCell = cell(select);
  }
  let holidayCell = textCell("");
  if (holiday && entry.kind === "worked") {
    const parts = [checkLabel(entry, "worked", "Worked"), checkLabel(entry, "taken", "Taken")];
    if (undecided) {
      const prompt = document.createElement("span");
      prompt.className = "prompt";
      prompt.textContent = "Worked or taken?";
      parts.push(prompt);
    }
    holidayCell = cell(...parts);
  }
  const remove = document.createElement("button");
  remove.type = "button";
  remove.textContent = "Remove";
  remove.addEventListener("click", () => removeEntry(entry));
  row.append(
    textCell(entry.work_date),
    typeCell,
    timed ? cell(input("start_time", "time", "Start time")) : textCell("—"),
    timed ? cell(input("end_time", "time", "End time")) : textCell("—"),
    timed ? cell(input("unpaid_break_minutes", "number", "Unpaid break in minutes")) : textCell("—"),
    paidCell,
    holidayCell,
    cell(remove)
  );
  return row;
}

function renderEntries() {
  entries.sort((a, b) => a.work_date.localeCompare(b.work_date));
  element("entry-list").replaceChildren(...entries.map(buildRow));
  element("entry-empty").hidden = entries.length > 0;
  updateTotals();
  updateExtras();
}

function dateProblem(date) {
  if (!date || date < monthStart || date > monthEnd) return "Enter a date in the selected month.";
  if (date < selectedEmployment.start_date || (selectedEmployment.end_date && date > selectedEmployment.end_date)) return "That date is outside the employment.";
  return "";
}

function fillMonth() {
  const start = element("pattern-start").value;
  const end = element("pattern-end").value;
  const pause = Number(element("pattern-break").value || 0);
  const weekdays = new Set(Array.from({length: 7}, (_, index) => index).filter(index => element(`weekday-${index}`).checked));
  if (!start || !end || !weekdays.size || !Number.isInteger(pause) || pause < 0 || scheduleMinutes() <= 0) {
    setMessage("pattern-message", "Choose weekdays and enter valid pattern hours and break.");
    return;
  }
  const days = new Date(Date.UTC(nextMonth.year, nextMonth.month, 0)).getUTCDate();
  let added = 0;
  let skipped = 0;
  for (let number = 1; number <= days; number++) {
    const date = new Date(Date.UTC(nextMonth.year, nextMonth.month - 1, number));
    if (!weekdays.has(date.getUTCDay())) continue;
    const value = date.toISOString().slice(0, 10);
    if (value < selectedEmployment.start_date || (selectedEmployment.end_date && value > selectedEmployment.end_date)) continue;
    if (entries.some(entry => entry.work_date === value)) { skipped++; continue; }
    entries.push(newWorkedDay(value, start, end, pause));
    added++;
  }
  renderEntries();
  const parts = [];
  if (added) parts.push(`${added} ${added === 1 ? "entry" : "entries"} added.`);
  if (skipped) parts.push(`${skipped} date(s) already had entries and were left unchanged.`);
  setMessage("pattern-message", parts.join(" "));
}

function addExtraDay() {
  const date = element("extra-date").value;
  let problem = dateProblem(date);
  if (!problem && entries.some(entry => entry.work_date === date && entry.kind === "annual")) problem = "Remove the annual holiday row for this date before adding work.";
  setMessage("extra-error", problem);
  if (problem) return;
  entries.push(newWorkedDay(date));
  element("extra-date").value = "";
  renderEntries();
}

function addAnnualHoliday() {
  const date = element("holiday-date").value;
  let problem = dateProblem(date);
  if (!problem && holidays.has(date)) problem = `${date} is a public holiday and cannot be taken as annual holiday.`;
  if (!problem && entries.some(entry => entry.work_date === date && entry.kind === "worked")) problem = "Remove the work entry for this date before adding annual holiday.";
  if (!problem && entries.some(entry => entry.work_date === date && entry.kind === "annual")) problem = "This date already has an annual holiday row.";
  let minutes = NaN;
  if (!problem) {
    const text = element("holiday-hours").value.trim();
    minutes = text ? parseHours(text) : scheduleMinutes();
    if (!(minutes > 0)) problem = "Enter the hours as H:MM, for example 6:30.";
  }
  setMessage("holiday-error", problem);
  if (problem) return;
  entries.push({work_date: date, kind: "annual", start_time: "", end_time: "", unpaid_break_minutes: 0, paid_minutes: minutes, holidayChoice: null});
  element("holiday-date").value = "";
  renderEntries();
}

function overlappingDate() {
  const byDate = new Map();
  for (const entry of entries.filter(hasTimes)) byDate.set(entry.work_date, [...(byDate.get(entry.work_date) ?? []), entry]);
  for (const [date, list] of byDate) {
    const spans = list.map(entry => [toMinutes(entry.start_time), toMinutes(entry.end_time)]).sort((a, b) => a[0] - b[0]);
    if (spans.some((span, index) => index > 0 && span[0] < spans[index - 1][1])) return date;
  }
  return "";
}

function repeatedDayOff() {
  const seen = new Set();
  for (const entry of entries.filter(entry => !hasTimes(entry))) {
    if (seen.has(entry.work_date)) return entry.work_date;
    seen.add(entry.work_date);
  }
  return "";
}

function buildPayrollPayload() {
  if (["extra-date", "holiday-date"].some(id => element(id).value)) {
    setMessage("save-error", "Add or clear the unfinished entry before saving.");
    return null;
  }
  if (bonusPending()) {
    setMessage("save-error", "Press Add for the bonus and expenses before saving.");
    return null;
  }
  for (const entry of entries) {
    if (isHoliday(entry) && entry.kind === "worked" && entry.holidayChoice === null) {
      setMessage("save-error", `Choose worked or taken for the public holiday on ${entry.work_date}.`);
      return null;
    }
    const minutes = minutesFor(entry);
    const bad = hasTimes(entry)
      ? !entry.start_time || !entry.end_time || !Number.isInteger(minutes) || minutes <= 0 || !Number.isInteger(Number(entry.unpaid_break_minutes)) || Number(entry.unpaid_break_minutes) < 0
      : !Number.isInteger(minutes) || minutes < 0;
    if (bad) {
      setMessage("save-error", `Check the hours and break for ${entry.work_date}.`);
      return null;
    }
  }
  const overlap = overlappingDate() || repeatedDayOff();
  if (overlap) {
    setMessage("save-error", `Entries on ${overlap} overlap.`);
    return null;
  }
  setMessage("save-error", "");
  return {
    employment_id: selectedEmployment.id,
    year: nextMonth.year,
    month: nextMonth.month,
    cash_bonus: committedBonus,
    expense_reimbursements: committedExpenses,
    work_entries: entries.map(entry => {
      if (hasTimes(entry)) return {work_date: entry.work_date, category: "worked", start_time: entry.start_time, end_time: entry.end_time, unpaid_break_minutes: Number(entry.unpaid_break_minutes)};
      return {work_date: entry.work_date, category: entry.kind === "annual" ? "annual_holiday_taken" : "public_holiday_taken", paid_minutes: Number(entry.paid_minutes)};
    }),
  };
}

function reviewTimesheet(event) {
  event.preventDefault();
  if (submitting || submissionLocked || !csrfToken || !selectedEmployment || !nextMonth) return;
  const payload = buildPayrollPayload();
  if (!payload) return;
  const label = monthLabel(payload.year, payload.month);
  const count = payload.work_entries.length;
  const work = count ? `${count} ${count === 1 ? "entry" : "entries"}. ${element("entry-totals").textContent}` : "No entries";
  element("timesheet-summary").textContent = `${selectedEmployment.employee_name} · ${label}: ${work}. Cash bonus: CHF ${payload.cash_bonus} · Expenses: CHF ${payload.expense_reimbursements}.`;
  element("timesheet-confirm").textContent = `Yes, confirm and save ${label}`;
  warning.showModal();
}

function recordSaved(payload, message, remember) {
  submissionLocked = true;
  element("save-message").textContent = message;
  savedPayslipUrl = payslipUrl(selectedEmployment.id, payload.year, payload.month);
  element("save-confirmation").hidden = false;
  element("entry-section").hidden = true;
  if (remember) {
    try {
      window.sessionStorage.setItem("payalign-saved-confirmation", JSON.stringify({url: savedPayslipUrl, message}));
    } catch (error) { /* The confirmation and link remain available on this page. */ }
  }
}

async function saveTimesheet() {
  const payload = buildPayrollPayload();
  if (!payload) {
    warning.close();
    return;
  }
  submitting = true;
  element("timesheet-confirm").disabled = true;
  element("timesheet-cancel").disabled = true;
  element("timesheet-status").textContent = "Saving month …";
  element("page-status").textContent = "Saving month …";
  updateControls();
  try {
    const {status, body} = await call("/api/v1/monthly-payroll", {
      method: "POST",
      headers: {"Content-Type": "application/json", Accept: "application/json", "X-CSRF-Token": csrfToken},
      body: JSON.stringify(payload),
    }, 15000);
    if ([401, 403].includes(status)) {
      showLoginMessage("Authentication/session or CSRF validation failed. The request was rejected. Please log in again.", "save-error");
    } else if ([400, 422].includes(status)) {
      showError(responseError(body), "save-error");
    } else if (status === 500 && body?.detail === SAVED_DETAIL) {
      recordSaved(payload, body.detail, false);
    } else if (status === 201 && Number.isSafeInteger(body?.monthly_record_id)) {
      recordSaved(payload, body.message || "Payroll processed successfully.", true);
    } else {
      throw new Error("response");
    }
  } catch (failure) {
    submissionLocked = true;
    showError("The request outcome is uncertain: this month may have been saved. Do not submit again until you reload its month history. No automatic retry was made.", "save-error");
  } finally {
    submitting = false;
    element("timesheet-confirm").disabled = false;
    element("timesheet-cancel").disabled = false;
    element("timesheet-status").textContent = "";
    element("page-status").textContent = "";
    warning.close();
    updateControls();
  }
}

function cancelEntry() {
  if (submitting) return;
  if (hasUnsavedWork() && !window.confirm("Discard the entries and go back to the timesheets?")) return;
  window.location.assign(TIMESHEETS_PAGE);
}

function latestMonth(months) {
  return months.reduce((latest, item) => !latest || item.year * 12 + item.month > latest.year * 12 + latest.month ? item : latest, null);
}

function actionButton(text, label, onClick) {
  const button = document.createElement("button");
  button.type = "button";
  button.textContent = text;
  if (label) button.setAttribute("aria-label", label);
  button.addEventListener("click", onClick);
  return button;
}

function savedMonthsText(months) {
  const years = new Map();
  for (const item of months.slice().sort((a, b) => a.year - b.year || a.month - b.month)) {
    years.set(item.year, [...(years.get(item.year) ?? []), monthNames[item.month - 1]]);
  }
  return [...years].map(([year, names]) => `${names.join(", ")} ${year}`).join(" · ");
}

function renderCard(item, employment, history) {
  const saved = latestMonth(history.months);
  const next = history.next_month;
  const rows = [];
  if (saved) {
    const label = monthLabel(saved.year, saved.month);
    rows.push({label: "Saved", value: savedMonthsText(history.months), action: actionButton("View payslip", `View the ${label} payslip of ${employment.employee_name}`, () => window.location.assign(payslipUrl(employment.id, saved.year, saved.month)))});
  } else {
    rows.push({label: "Saved", value: "No saved months yet"});
  }
  if (next) {
    const label = monthLabel(next.year, next.month);
    rows.push({label: "Next to enter", value: label, action: actionButton("Enter", `Enter ${label} for ${employment.employee_name}`, () => window.location.assign(`${TIMESHEETS_PAGE}?employment_id=${employment.id}`))});
  } else {
    rows.push({label: "Next to enter", value: "All months entered"});
  }
  item.append(cardRows(rows));
}

function timesheetCard(employment) {
  const item = employeeCard(employment);
  const ready = (async () => {
    try {
      const {status, body} = await call(`/api/v1/employments/${employment.id}/months`, {headers: {Accept: "application/json"}, cache: "no-store"});
      if (status !== 200 || !Array.isArray(body?.months)) throw new Error("history");
      renderCard(item, employment, body);
    } catch (error) {
      item.append(cardNote("Months unavailable. Reload the page to try again."));
    }
  })();
  return {item, ready};
}

async function showLanding(note = "") {
  element("entry-section").hidden = true;
  element("save-confirmation").hidden = true;
  element("landing-section").hidden = false;
  setMessage("no-month", note);
  element("no-employments").hidden = employments.length !== 0;
  const cards = employments.map(timesheetCard);
  element("timesheet-list").replaceChildren(...cards.map(card => card.item));
  element("page-status").textContent = "";
  await Promise.all(cards.map(card => card.ready));
}

async function loadEmployments() {
  element("page-status").textContent = "Loading employments …";
  const {status, body} = await call("/api/v1/employments", {headers: {Accept: "application/json"}, cache: "no-store"});
  if (status === 401) {
    element("page-status").textContent = "";
    showLoginMessage("Your session has expired. Please log in again to continue.");
    return false;
  }
  if (status !== 200 || !Array.isArray(body)) throw new Error("response");
  employments = body;
  return true;
}

async function loadBalance(employment, months) {
  const latest = latestMonth(months);
  let text = "—";
  if (latest) {
    try {
      const {status, body} = await call(`/api/v1/employments/${employment.id}/months/${latest.year}/${latest.month}`, {headers: {Accept: "application/json"}, cache: "no-store"});
      if (status === 200 && Number.isInteger(body?.holiday_balance_minutes)) text = hoursText(body.holiday_balance_minutes);
    } catch (error) { /* The balance is a convenience; the page works without it. */ }
  }
  element("holiday-balance").textContent = `Remaining balance: ${text}`;
}

async function openEntry(employment) {
  element("page-status").textContent = "Loading employment months …";
  try {
    const {status, body} = await call(`/api/v1/employments/${employment.id}/months`, {headers: {Accept: "application/json"}, cache: "no-store"});
    if (status === 401) {
      element("page-status").textContent = "";
      showLoginMessage("Your session has expired. Please log in again to continue.");
      return;
    }
    if (status === 404) {
      element("page-status").textContent = "";
      showError("This employment is no longer available.");
      await showLanding();
      return;
    }
    if (status !== 200 || !Array.isArray(body?.months)) throw new Error("response");
    if (!body.next_month) {
      await showLanding(`${employment.employee_name}: all months are entered.`);
      return;
    }
    await loadBalance(employment, body.months);
    const result = await call(`/api/v1/public-holidays?year=${body.next_month.year}`);
    if (result.status === 401) {
      element("page-status").textContent = "";
      showLoginMessage("Your session has expired. Please log in again.");
      return;
    }
    if (result.status !== 200 || !Array.isArray(result.body)) throw new Error("calendar");
    holidays = new Set(result.body);
    selectedEmployment = employment;
    nextMonth = body.next_month;
    const prefix = `${nextMonth.year}-${String(nextMonth.month).padStart(2, "0")}`;
    monthStart = `${prefix}-01`;
    monthEnd = `${prefix}-${String(new Date(Date.UTC(nextMonth.year, nextMonth.month, 0)).getUTCDate()).padStart(2, "0")}`;
    for (const id of ["extra-date", "holiday-date"]) {
      element(id).min = monthStart;
      element(id).max = monthEnd;
    }
    element("entry-month").textContent = `${employment.employee_name} · ${monthLabel(nextMonth.year, nextMonth.month)}`;
    element("landing-section").hidden = true;
    element("entry-section").hidden = false;
    element("page-status").textContent = "";
    renderEntries();
    updateControls();
  } catch (failure) {
    element("page-status").textContent = "";
    showError("Could not load the timesheet. Please check your connection and try again.");
  }
}

async function initialize() {
  try {
    csrfToken = await fetchCsrfToken();
    updateControls();
    if (!await loadEmployments()) return;
    const requested = new URLSearchParams(window.location.search).get("employment_id");
    if (requested === null) {
      await showLanding();
      return;
    }
    const chosen = employments.find(item => String(item.id) === requested);
    if (!chosen) {
      showError("This employment could not be found.");
      await showLanding();
      return;
    }
    await openEntry(chosen);
  } catch (failure) {
    element("page-status").textContent = "";
    showError("Could not prepare the timesheet page. Please reload before continuing.");
  }
}

const warning = wireWarningDialog({
  dialogId: "timesheet-dialog", confirmId: "timesheet-confirm", cancelId: "timesheet-cancel",
  onConfirm: saveTimesheet, isBusy: () => submitting
});
for (const id of ["pattern-start", "pattern-end", "pattern-break"]) element(id).addEventListener("input", syncHoursField);
element("holiday-hours").addEventListener("input", () => { hoursTouched = true; });
element("add-bonus").addEventListener("click", addBonus);
element("fill-month").addEventListener("click", fillMonth);
element("add-day").addEventListener("click", addExtraDay);
element("add-holiday").addEventListener("click", addAnnualHoliday);
element("payroll-form").addEventListener("submit", reviewTimesheet);
element("cancel-entry").addEventListener("click", cancelEntry);
element("view-saved-payslip").addEventListener("click", () => { if (savedPayslipUrl) window.location.assign(savedPayslipUrl); });
element("back-to-timesheets").addEventListener("click", () => window.location.assign(TIMESHEETS_PAGE));
initialize();
