(function () {
"use strict";

const element = id => document.getElementById(`workspace-${id}`);
const monthNames = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
const weekdays = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"];
let csrfToken = null;
let selectedEmployment = null;
let nextMonth = null;
let publicHolidays = new Set();
let entries = [];
let nextEntryId = 1;
let stagedRowsEdited = false;
let submitting = false;
let submissionLocked = false;
let reviewedPayload = null;

function hasUnsavedWork() {
  if (submissionLocked || element("entry-section").hidden) return false;
  return entries.length > 0 || ["cash-bonus", "expense-reimbursements"].some(id => {
    const value = element(id).value.trim();
    return value !== "" && (!Number.isFinite(Number(value)) || Number(value) !== 0);
  });
}

window.leaveWarning = () => hasUnsavedWork() ? "Discard the entries and leave this page?" : "";

function monthLabel(year, month) { return `${monthNames[month - 1]} ${year}`; }
function clearMessage() { element("page-error").textContent = ""; element("page-error").hidden = true; }
function showError(message) { element("page-error").textContent = message; element("page-error").hidden = false; }
function showEntryError(message) { element("entry-error").textContent = message; element("entry-error").hidden = !message; }

function showLoginMessage(message) {
  const container = element("page-error");
  container.textContent = `${message} `;
  const link = document.createElement("a");
  link.href = "/login";
  link.textContent = "Open the login page.";
  container.append(link);
  container.hidden = false;
}

function responseError(body) {
  if (typeof body?.detail === "string") return body.detail;
  if (Array.isArray(body?.detail)) return body.detail.map(item => item?.msg ?? "Invalid input.").join("\n");
  return "Please check the entered values and try again.";
}

async function call(url, options = {}, timeoutMs = 10000) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(url, {...options, signal: controller.signal});
    return {status: response.status, body: response.status === 204 ? null : await response.json()};
  } finally { clearTimeout(timeout); }
}

function updateControls() {
  element("save-payroll").disabled = !csrfToken || !nextMonth || submitting || submissionLocked;
  element("confirm-payroll").disabled = submitting || submissionLocked;
}

async function loadCsrfToken() {
  const body = {csrf_token: await fetchCsrfToken()}; const status = 200;
  if (status !== 200 || typeof body?.csrf_token !== "string" || !body.csrf_token) throw new Error("csrf");
  csrfToken = body.csrf_token;
  updateControls();
}

async function loadPublicHolidays() {
  const {status, body} = await call(`/api/v1/public-holidays/${RULES_YEAR}`, {headers: {Accept: "application/json"}, cache: "no-store"});
  if (status === 401) { showLoginMessage("Your session has expired. Please log in again to continue."); return false; }
  if (status !== 200 || body?.year !== RULES_YEAR || !Array.isArray(body.dates)) throw new Error("holidays");
  publicHolidays = new Set(body.dates);
  return true;
}

function employmentButton(employment) {
  const item = document.createElement("li");
  const button = document.createElement("button");
  button.type = "button";
  button.textContent = `${employment.employee_name} — from ${employment.start_date}${employment.end_date ? ` to ${employment.end_date}` : ""}`;
  button.addEventListener("click", () => selectEmployment(employment));
  item.append(button);
  return item;
}

async function loadEmployments() {
  element("page-status").textContent = "Loading employments …";
  try {
    const {status, body} = await call("/api/v1/employments", {headers: {Accept: "application/json"}, cache: "no-store"});
    if (status === 401) { element("page-status").textContent = ""; showLoginMessage("Your session has expired. Please log in again to continue."); return; }
    if (status !== 200 || !Array.isArray(body)) throw new Error("response");
    element("employment-list").replaceChildren(...body.map(employmentButton));
    element("employment-empty").hidden = body.length !== 0;
    element("page-status").textContent = "";
  } catch (failure) { element("page-status").textContent = ""; showError("Could not load employments. Please check your connection and reload the page."); }
}

function payslipUrl(employmentId, year, month) {
  return `/payslips?employment_id=${employmentId}&year=${year}&month=${month}`;
}

function completedMonthButton(month) {
  const item = document.createElement("li");
  const button = document.createElement("button");
  button.type = "button";
  button.textContent = `View ${monthLabel(month.year, month.month)} payslip`;
  button.addEventListener("click", () => window.location.assign(payslipUrl(selectedEmployment.id, month.year, month.month)));
  item.append(button);
  return item;
}

async function selectEmployment(employment) {
  if (!confirmBeforeLeaving()) return;
  clearMessage(); element("page-status").textContent = "Loading employment months …";
  try {
    const {status, body} = await call(`/api/v1/employments/${employment.id}/months`, {headers: {Accept: "application/json"}, cache: "no-store"});
    if (status === 401) { element("page-status").textContent = ""; showLoginMessage("Your session has expired. Please log in again to continue."); return; }
    if (status === 404) { element("page-status").textContent = ""; showError("This employment is no longer available."); return; }
    if (status !== 200 || !Array.isArray(body?.months)) throw new Error("response");
    selectedEmployment = employment; nextMonth = body.next_month; submissionLocked = false;
    element("selected-employment").textContent = employment.employee_name;
    element("month-list").replaceChildren(...body.months.map(completedMonthButton));
    element("month-empty").hidden = body.months.length !== 0;
    element("next-month").textContent = nextMonth ? `Next month: ${monthLabel(nextMonth.year, nextMonth.month)}` : "No further month is available.";
    element("open-month-entry").disabled = !nextMonth;
    element("months-section").hidden = false; element("entry-section").hidden = true;
    element("page-status").textContent = ""; updateControls();
  } catch (failure) { element("page-status").textContent = ""; showError("Could not load employment months. Please check your connection and try again."); }
}

function addPayslipLine(container, label, value) {
  const term = document.createElement("dt"); const detail = document.createElement("dd");
  term.textContent = label; detail.textContent = value; container.append(term, detail);
}

function dateParts(value) { const [year, month, day] = value.split("-").map(Number); return {year, month, day}; }
function weekdayFor(value) { const {year, month, day} = dateParts(value); return new Date(Date.UTC(year, month - 1, day)).getUTCDay(); }
function timeMinutes(value) { if (!/^\d{2}:\d{2}$/.test(value)) return null; const [hours, minutes] = value.split(":").map(Number); return hours * 60 + minutes; }

function monthBounds() {
  const prefix = `${nextMonth.year}-${String(nextMonth.month).padStart(2, "0")}`;
  const last = new Date(Date.UTC(nextMonth.year, nextMonth.month, 0)).getUTCDate();
  let minimum = `${prefix}-01`; let maximum = `${prefix}-${String(last).padStart(2, "0")}`;
  if (selectedEmployment.start_date > minimum) minimum = selectedEmployment.start_date;
  if (selectedEmployment.end_date && selectedEmployment.end_date < maximum) maximum = selectedEmployment.end_date;
  return {minimum, maximum};
}

function paidMinutes(entry) {
  if (entry.category !== "worked") return Number(entry.paid_minutes);
  const start = timeMinutes(entry.start_time); const end = timeMinutes(entry.end_time); const breakMinutes = Number(entry.unpaid_break_minutes);
  if (start === null || end === null || !Number.isInteger(breakMinutes) || breakMinutes < 0 || end <= start + breakMinutes) return null;
  return end - start - breakMinutes;
}

function patternForDay(dayIndex) {
  const name = weekdays[dayIndex];
  if (!element(`pattern-${name}`).checked) return null;
  return {start_time: element(`pattern-${name}-start`).value, end_time: element(`pattern-${name}-end`).value, unpaid_break_minutes: Number(element(`pattern-${name}-break`).value)};
}

function configuredPatterns() {
  const patterns = new Map(); let problem = "";
  weekdays.forEach((_, dayIndex) => {
    const pattern = patternForDay(dayIndex); if (!pattern) return;
    const minutes = paidMinutes({category: "worked", ...pattern});
    if (minutes === null) problem = "Each selected weekday needs valid start and end times and an unpaid break shorter than the shift.";
    else patterns.set(dayIndex, {...pattern, paid_minutes: minutes});
  });
  if (!problem && patterns.size === 0) problem = "Select at least one weekday.";
  element("pattern-error").textContent = problem; element("pattern-error").hidden = !problem;
  return problem ? null : patterns;
}

function sortEntries() { entries.sort((left, right) => left.work_date.localeCompare(right.work_date) || (left.start_time || "").localeCompare(right.start_time || "") || left.id - right.id); }
function makeInput(type, value, label) { const input = document.createElement("input"); input.type = type; input.value = value ?? ""; input.setAttribute("aria-label", label); return input; }

function removeButton(entry) {
  const button = document.createElement("button"); button.type = "button"; button.textContent = "Remove"; button.setAttribute("aria-label", `Remove ${entry.work_date} entry`);
  button.addEventListener("click", () => { entries = entries.filter(candidate => candidate.id !== entry.id); stagedRowsEdited = true; reviewedPayload = null; renderEntries(); });
  return button;
}

function bindEntryInput(input, entry, property, convert = value => value) {
  input.addEventListener("change", () => {
    entry[property] = convert(input.value); entry.is_public_holiday = publicHolidays.has(entry.work_date);
    if (!entry.is_public_holiday && entry.category === "public_holiday_taken") entry.category = "worked";
    stagedRowsEdited = true; reviewedPayload = null; element("review-section").hidden = true; sortEntries(); renderEntries();
  });
}

function renderWorkedEntry(entry) {
  const row = document.createElement("tr"); if (entry.is_public_holiday) row.className = "public-holiday-row";
  const dateCell = document.createElement("td"); const dateInput = makeInput("date", entry.work_date, "Entry date"); const {minimum, maximum} = monthBounds();
  dateInput.min = minimum; dateInput.max = maximum; bindEntryInput(dateInput, entry, "work_date"); dateCell.append(dateInput);
  const categoryCell = document.createElement("td");
  if (entry.is_public_holiday) {
    const choice = document.createElement("select"); choice.setAttribute("aria-label", `Public holiday choice for ${entry.work_date}`);
    for (const [value, label] of [["worked", "Worked"], ["public_holiday_taken", "Day off (paid)"]]) { const option = document.createElement("option"); option.value = value; option.textContent = label; choice.append(option); }
    choice.value = entry.category; bindEntryInput(choice, entry, "category"); categoryCell.append(choice);
  } else categoryCell.textContent = "Worked";
  const startCell = document.createElement("td"); const endCell = document.createElement("td"); const minutesCell = document.createElement("td");
  if (entry.category === "worked") {
    const start = makeInput("time", entry.start_time, `Start time for ${entry.work_date}`); const end = makeInput("time", entry.end_time, `End time for ${entry.work_date}`); const breakInput = makeInput("number", entry.unpaid_break_minutes, `Unpaid break for ${entry.work_date}`); breakInput.min = "0";
    bindEntryInput(start, entry, "start_time"); bindEntryInput(end, entry, "end_time"); bindEntryInput(breakInput, entry, "unpaid_break_minutes", Number); startCell.append(start); endCell.append(end); minutesCell.append(breakInput);
  } else {
    startCell.textContent = "—"; endCell.textContent = "—"; const paid = makeInput("number", entry.paid_minutes, `Paid minutes for ${entry.work_date}`); paid.min = "0"; bindEntryInput(paid, entry, "paid_minutes", Number); minutesCell.append(paid);
  }
  const actionCell = document.createElement("td"); actionCell.append(removeButton(entry)); row.append(dateCell, categoryCell, startCell, endCell, minutesCell, actionCell); return row;
}

function renderAnnualHoliday(entry) {
  const row = document.createElement("tr"); const dateCell = document.createElement("td"); dateCell.textContent = entry.work_date;
  const minutesCell = document.createElement("td"); const paid = makeInput("number", entry.paid_minutes, `Annual holiday paid minutes for ${entry.work_date}`); paid.min = "0"; bindEntryInput(paid, entry, "paid_minutes", Number); minutesCell.append(paid);
  const actionCell = document.createElement("td"); actionCell.append(removeButton(entry)); row.append(dateCell, minutesCell, actionCell); return row;
}

function renderTotals() {
  const totals = {worked: 0, public_holiday_worked: 0, annual_holiday_taken: 0, public_holiday_taken: 0};
  for (const entry of entries) { const minutes = paidMinutes(entry); if (minutes !== null && minutes >= 0) totals[entry.category === "worked" && entry.is_public_holiday ? "public_holiday_worked" : entry.category] += minutes; }
  const container = element("entry-totals"); container.replaceChildren();
  for (const [label, key] of [["Worked", "worked"], ["Public holiday worked", "public_holiday_worked"], ["Annual holiday", "annual_holiday_taken"], ["Public holiday paid", "public_holiday_taken"]]) addPayslipLine(container, label, `${totals[key]} minutes`);
  addPayslipLine(container, "Overall paid", `${Object.values(totals).reduce((sum, value) => sum + value, 0)} minutes`);
}

function renderEntries() {
  sortEntries();
  element("work-entries-body").replaceChildren(...entries.filter(entry => entry.category !== "annual_holiday_taken").map(renderWorkedEntry));
  element("holiday-entries-body").replaceChildren(...entries.filter(entry => entry.category === "annual_holiday_taken").map(renderAnnualHoliday));
  renderTotals();
}

function fillMonth() {
  const patterns = configuredPatterns(); if (!patterns) return;
  if (entries.some(entry => entry.category !== "annual_holiday_taken") && stagedRowsEdited && !window.confirm("Regenerating the pattern replaces manually edited work entries. Continue?")) return;
  entries = entries.filter(entry => entry.category === "annual_holiday_taken");
  const annualHolidayDates = new Set(entries.map(entry => entry.work_date));
  const {minimum, maximum} = monthBounds(); const cursor = new Date(`${minimum}T00:00:00Z`); const last = new Date(`${maximum}T00:00:00Z`);
  while (cursor <= last) {
    const pattern = patterns.get(cursor.getUTCDay());
    if (pattern) {
      const workDate = cursor.toISOString().slice(0, 10); const holiday = publicHolidays.has(workDate);
      if (!annualHolidayDates.has(workDate)) entries.push({id: nextEntryId++, work_date: workDate, category: holiday ? "public_holiday_taken" : "worked", start_time: pattern.start_time, end_time: pattern.end_time, unpaid_break_minutes: pattern.unpaid_break_minutes, paid_minutes: pattern.paid_minutes, is_public_holiday: holiday});
    }
    cursor.setUTCDate(cursor.getUTCDate() + 1);
  }
  stagedRowsEdited = false; reviewedPayload = null; element("review-section").hidden = true; showEntryError(""); renderEntries();
}

function dateInBounds(value) { const {minimum, maximum} = monthBounds(); return value >= minimum && value <= maximum; }

function addWorkday() {
  const workDate = element("work-entry-date").value;
  if (!dateInBounds(workDate)) { showEntryError("Choose an additional workday within this employment month."); return; }
  entries.push({id: nextEntryId++, work_date: workDate, category: "worked", start_time: "", end_time: "", unpaid_break_minutes: 0, is_public_holiday: publicHolidays.has(workDate)});
  stagedRowsEdited = true; showEntryError(""); renderEntries();
}

function prefillAnnualHolidayMinutes() {
  const workDate = element("annual-holiday-date").value; if (!dateInBounds(workDate)) return;
  const pattern = patternForDay(weekdayFor(workDate)); if (!pattern) return;
  const minutes = paidMinutes({category: "worked", ...pattern}); if (minutes !== null) element("annual-holiday-minutes").value = String(minutes);
}

function addAnnualHoliday() {
  const workDate = element("annual-holiday-date").value; const minutes = Number(element("annual-holiday-minutes").value);
  if (!dateInBounds(workDate)) { showEntryError("Choose an annual-holiday date within this employment month."); return; }
  if (publicHolidays.has(workDate)) { showEntryError(`${workDate} is a public holiday and cannot be taken as paid holiday.`); return; }
  if (!Number.isInteger(minutes) || minutes < 0) { showEntryError("Enter the annual-holiday paid minutes."); return; }
  entries = entries.filter(entry => entry.work_date !== workDate);
  entries.push({id: nextEntryId++, work_date: workDate, category: "annual_holiday_taken", paid_minutes: minutes, is_public_holiday: false});
  stagedRowsEdited = true; showEntryError(""); renderEntries();
}

function openMonthEntry() {
  if (!nextMonth) return; clearMessage(); entries = []; stagedRowsEdited = false; reviewedPayload = null;
  const {minimum, maximum} = monthBounds();
  for (const id of ["work-entry-date", "annual-holiday-date"]) { element(id).min = minimum; element(id).max = maximum; element(id).value = minimum; }
  element("entry-month").textContent = monthLabel(nextMonth.year, nextMonth.month); element("entry-section").hidden = false; element("review-section").hidden = true;
  showEntryError(""); renderEntries(); updateControls(); element("pattern-monday").focus();
}

function validateEntries() {
  for (const entry of entries) {
    if (!dateInBounds(entry.work_date)) return "Every entry needs a date within this employment month.";
    if (entry.category === "annual_holiday_taken" && publicHolidays.has(entry.work_date)) return `${entry.work_date} is a public holiday and cannot be taken as paid holiday.`;
    if (entry.category === "public_holiday_taken" && !publicHolidays.has(entry.work_date)) return `${entry.work_date} is not a public holiday.`;
    if (paidMinutes(entry) === null || paidMinutes(entry) < 0) return `Enter valid time or paid minutes for ${entry.work_date}.`;
  }
  const timedByDate = new Map();
  for (const entry of entries.filter(candidate => candidate.category === "worked")) { const group = timedByDate.get(entry.work_date) || []; group.push(entry); timedByDate.set(entry.work_date, group); }
  for (const [workDate, dayEntries] of timedByDate) {
    dayEntries.sort((left, right) => left.start_time.localeCompare(right.start_time));
    for (let index = 1; index < dayEntries.length; index += 1) if (dayEntries[index].start_time < dayEntries[index - 1].end_time) return `Work entries overlap on ${workDate}.`;
    if (entries.some(entry => entry.work_date === workDate && entry.category === "public_holiday_taken")) return `${workDate} cannot contain both public-holiday work and paid leave.`;
  }
  return "";
}

function buildPayrollPayload() {
  return {employment_id: selectedEmployment.id, year: nextMonth.year, month: nextMonth.month, cash_bonus: element("cash-bonus").value || "0.00", expense_reimbursements: element("expense-reimbursements").value || "0.00", work_entries: entries.map(entry => entry.category === "worked" ? {work_date: entry.work_date, category: "worked", start_time: entry.start_time, end_time: entry.end_time, unpaid_break_minutes: Number(entry.unpaid_break_minutes)} : {work_date: entry.work_date, category: entry.category, paid_minutes: Number(entry.paid_minutes)})};
}

function reviewPayroll(event) {
  event.preventDefault(); if (submitting || submissionLocked || !csrfToken || !selectedEmployment || !nextMonth) return; clearMessage();
  const problem = validateEntries(); showEntryError(problem); if (problem) { element("entry-error").focus(); return; }
  reviewedPayload = buildPayrollPayload();
  const reviewItems = reviewedPayload.work_entries.map(entry => { const item = document.createElement("li"); item.textContent = entry.category === "worked" ? `${entry.work_date}: worked ${entry.start_time}–${entry.end_time}, ${entry.unpaid_break_minutes} minute break` : `${entry.work_date}: ${entry.category}, ${entry.paid_minutes} paid minutes`; return item; });
  if (reviewItems.length === 0) { const item = document.createElement("li"); item.textContent = "No work or leave entries."; reviewItems.push(item); }
  element("review-entries").replaceChildren(...reviewItems); element("review-section").hidden = false; element("confirm-payroll").focus();
}

function openSavedPayslip(payload, message) {
  const url = payslipUrl(payload.employment_id, payload.year, payload.month);
  try { window.sessionStorage.setItem("payalign-saved-confirmation", JSON.stringify({url, message})); } catch (failure) {}
  window.dispatchEvent(new Event("payalign-payroll-saved"));
  window.location.assign(url);
}

function invalidateReview() {
  reviewedPayload = null;
  element("review-section").hidden = true;
}

async function submitPayroll() {
  if (submitting || submissionLocked || !csrfToken || !reviewedPayload) return;
  const payload = reviewedPayload; submitting = true; element("page-status").textContent = "Saving month …"; updateControls();
  try {
    const {status, body} = await call("/api/v1/monthly-payroll", {method: "POST", headers: {"Content-Type": "application/json", Accept: "application/json", "X-CSRF-Token": csrfToken}, body: JSON.stringify(payload)}, 15000);
    if ([401, 403].includes(status)) showLoginMessage("Authentication/session or CSRF validation failed. The request was rejected. Please log in again.");
    else if ([400, 422].includes(status)) showError(responseError(body));
    else if (status === 201 && Number.isSafeInteger(body?.monthly_record_id)) { submissionLocked = true; openSavedPayslip(payload, typeof body.message === "string" ? body.message : "Payroll processed successfully."); }
    else throw new Error("response");
  } catch (failure) { submissionLocked = true; showError("The request outcome is uncertain: this month may have been saved. Do not submit again until you reload its month history. No automatic retry was made."); }
  finally { submitting = false; element("page-status").textContent = ""; updateControls(); }
}

async function logout() {
  if (!csrfToken || submitting) return; clearMessage(); submitting = true; element("page-status").textContent = "Logging out …"; updateControls();
  try {
    const {status} = await call("/api/v1/auth/logout", {method: "POST", headers: {Accept: "application/json", "X-CSRF-Token": csrfToken}}, 15000);
    if (status === 204) window.location.replace("/login");
    else if ([401, 403].includes(status)) showLoginMessage("The logout request was rejected. Please reload or log in again.");
    else throw new Error("response");
  } catch (failure) { showError("Could not confirm logout. Please check your connection before continuing."); }
  finally { submitting = false; element("page-status").textContent = ""; updateControls(); }
}

element("open-month-entry").addEventListener("click", openMonthEntry);
element("fill-month").addEventListener("click", fillMonth);
element("add-workday").addEventListener("click", addWorkday);
element("annual-holiday-date").addEventListener("change", prefillAnnualHolidayMinutes);
element("add-annual-holiday").addEventListener("click", addAnnualHoliday);
element("cash-bonus").addEventListener("input", invalidateReview);
element("expense-reimbursements").addEventListener("input", invalidateReview);
element("payroll-form").addEventListener("submit", reviewPayroll);
element("confirm-payroll").addEventListener("click", submitPayroll);
element("cancel-review").addEventListener("click", () => { reviewedPayload = null; element("review-section").hidden = true; element("save-payroll").focus(); });

async function initialize() {
  try { await loadCsrfToken(); if (await loadPublicHolidays()) await loadEmployments(); }
  catch (failure) { showError("Could not prepare the secure employment page. Please reload before continuing."); element("page-status").textContent = ""; }
}

initialize();

})();
