"use strict";

const element = id => document.getElementById(id);
const monthNames = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
const workedCategories = new Set(["worked", "public_holiday_worked"]);
let csrfToken = null;
let selectedEmployment = null;
let nextMonth = null;
let submitting = false;
let submissionLocked = false;

function monthLabel(year, month) {
  return `${monthNames[month - 1]} ${year}`;
}

function clearMessage() {
  element("page-error").textContent = "";
  element("page-error").hidden = true;
}

function showError(message) {
  element("page-error").textContent = message;
  element("page-error").hidden = false;
}

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
  } finally {
    clearTimeout(timeout);
  }
}

function updateControls() {
  element("logout-button").disabled = !csrfToken || submitting;
  element("save-payroll").disabled = !csrfToken || !nextMonth || submitting || submissionLocked;
}

async function loadCsrfToken() {
  const {status, body} = await call("/api/v1/auth/csrf", {headers: {Accept: "application/json"}, cache: "no-store"});
  if (status !== 200 || typeof body?.csrf_token !== "string" || !body.csrf_token) throw new Error("csrf");
  csrfToken = body.csrf_token;
  updateControls();
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
    if (status === 401) {
      element("page-status").textContent = "";
      showLoginMessage("Your session has expired. Please log in again to continue.");
      return;
    }
    if (status !== 200 || !Array.isArray(body)) throw new Error("response");
    element("employment-list").replaceChildren(...body.map(employmentButton));
    element("employment-empty").hidden = body.length !== 0;
    element("page-status").textContent = "";
  } catch (failure) {
    element("page-status").textContent = "";
    showError("Could not load employments. Please check your connection and reload the page.");
  }
}

function completedMonthButton(month) {
  const item = document.createElement("li");
  const button = document.createElement("button");
  button.type = "button";
  button.textContent = `View ${monthLabel(month.year, month.month)} payslip`;
  button.addEventListener("click", () => loadPayslip(month.year, month.month));
  item.append(button);
  return item;
}

async function selectEmployment(employment) {
  clearMessage();
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
      return;
    }
    if (status !== 200 || !Array.isArray(body?.months)) throw new Error("response");
    selectedEmployment = employment;
    nextMonth = body.next_month;
    submissionLocked = false;
    element("selected-employment").textContent = employment.employee_name;
    element("month-list").replaceChildren(...body.months.map(completedMonthButton));
    element("month-empty").hidden = body.months.length !== 0;
    element("next-month").textContent = nextMonth ? `Next month: ${monthLabel(nextMonth.year, nextMonth.month)}` : "No further month is available.";
    element("open-month-entry").disabled = !nextMonth;
    element("months-section").hidden = false;
    element("entry-section").hidden = true;
    element("payslip-section").hidden = true;
    element("page-status").textContent = "";
    updateControls();
  } catch (failure) {
    element("page-status").textContent = "";
    showError("Could not load employment months. Please check your connection and try again.");
  }
}

function addPayslipLine(container, label, value) {
  const term = document.createElement("dt");
  const detail = document.createElement("dd");
  term.textContent = label;
  detail.textContent = value;
  container.append(term, detail);
}

function displayPayslip(body, year, month) {
  const details = element("payslip-details");
  details.replaceChildren();
  const money = [
    ["Gross wage", "gross_wage"], ["AHV deduction", "ahv_deduction"],
    ["ALV deduction", "alv_deduction"], ["NBU deduction", "nbu_deduction"],
    ["Tax deduction", "tax_deduction"], ["Net payout", "net_payout"],
    ["Employer AHV", "employer_ahv"], ["Employer ALV", "employer_alv"],
    ["Employer FAK", "employer_fak"], ["Employer BU", "employer_bu"],
    ["Administration charge", "admin_charge"], ["Total employer cost", "total_employer_cost"],
  ];
  for (const [label, key] of money) addPayslipLine(details, label, `CHF ${body[key]}`);
  addPayslipLine(details, "Holiday balance", `${body.holiday_balance_minutes} minutes`);
  element("payslip-month").textContent = monthLabel(year, month);
  element("payslip-section").hidden = false;
}

async function loadPayslip(year, month) {
  clearMessage();
  element("page-status").textContent = "Loading saved payslip …";
  try {
    const {status, body} = await call(`/api/v1/employments/${selectedEmployment.id}/months/${year}/${month}`, {headers: {Accept: "application/json"}, cache: "no-store"});
    if (status === 401) showLoginMessage("Your session has expired. Please log in again to continue.");
    else if (status === 404) showError("The saved payslip was not found.");
    else if (status === 200 && body && Number.isSafeInteger(body.monthly_record_id)) displayPayslip(body, year, month);
    else throw new Error("response");
  } catch (failure) {
    showError("Could not load the saved payslip. Please check your connection and try again.");
  } finally {
    element("page-status").textContent = "";
  }
}

function updateEntryKind() {
  const worked = workedCategories.has(element("work-category").value);
  element("time-fields").hidden = !worked;
  element("paid-minutes-field").hidden = worked;
}

function openMonthEntry() {
  if (!nextMonth) return;
  clearMessage();
  const prefix = `${nextMonth.year}-${String(nextMonth.month).padStart(2, "0")}`;
  element("work-date").min = `${prefix}-01`;
  element("work-date").max = `${prefix}-31`;
  element("entry-month").textContent = monthLabel(nextMonth.year, nextMonth.month);
  element("entry-section").hidden = false;
  element("payslip-section").hidden = true;
  updateEntryKind();
  updateControls();
  element("work-date").focus();
}

function buildPayrollPayload() {
  const date = element("work-date").value;
  const category = element("work-category").value;
  let problem = "";
  if (!date || !date.startsWith(`${nextMonth.year}-${String(nextMonth.month).padStart(2, "0")}-`)) problem = "Enter a date in the selected month.";
  const entry = {work_date: date, category};
  if (workedCategories.has(category)) {
    if (!element("start-time").value || !element("end-time").value) problem = "Enter both start and end time.";
    entry.start_time = element("start-time").value;
    entry.end_time = element("end-time").value;
    entry.unpaid_break_minutes = Number(element("unpaid-break-minutes").value || 0);
  } else {
    const minutes = Number(element("paid-minutes").value);
    if (!Number.isInteger(minutes) || minutes < 0) problem = "Enter the paid minutes.";
    entry.paid_minutes = minutes;
  }
  element("work-entry-error").textContent = problem;
  element("work-entry-error").hidden = !problem;
  if (problem) return null;
  return {
    employment_id: selectedEmployment.id,
    year: nextMonth.year,
    month: nextMonth.month,
    cash_bonus: element("cash-bonus").value || "0.00",
    expense_reimbursements: element("expense-reimbursements").value || "0.00",
    work_entries: [entry],
  };
}

async function submitPayroll(event) {
  event.preventDefault();
  if (submitting || submissionLocked || !csrfToken || !selectedEmployment || !nextMonth) return;
  clearMessage();
  const payload = buildPayrollPayload();
  if (!payload) {
    element("work-date").focus();
    return;
  }
  submitting = true;
  element("page-status").textContent = "Saving month …";
  updateControls();
  try {
    const {status, body} = await call("/api/v1/monthly-payroll", {
      method: "POST",
      headers: {"Content-Type": "application/json", Accept: "application/json", "X-CSRF-Token": csrfToken},
      body: JSON.stringify(payload),
    }, 15000);
    if ([401, 403].includes(status)) {
      showLoginMessage("Authentication/session or CSRF validation failed. The request was rejected. Please log in again.");
    } else if ([400, 422].includes(status)) {
      showError(responseError(body));
    } else if (status === 201 && Number.isSafeInteger(body?.monthly_record_id)) {
      submissionLocked = true;
      await loadPayslip(payload.year, payload.month);
    } else {
      throw new Error("response");
    }
  } catch (failure) {
    submissionLocked = true;
    showError("The request outcome is uncertain: this month may have been saved. Do not submit again until you reload its month history. No automatic retry was made.");
  } finally {
    submitting = false;
    element("page-status").textContent = "";
    updateControls();
  }
}

async function logout() {
  if (!csrfToken || submitting) return;
  clearMessage();
  submitting = true;
  element("page-status").textContent = "Logging out …";
  updateControls();
  try {
    const {status} = await call("/api/v1/auth/logout", {
      method: "POST",
      headers: {Accept: "application/json", "X-CSRF-Token": csrfToken},
    }, 15000);
    if (status === 204) window.location.replace("/login");
    else if ([401, 403].includes(status)) showLoginMessage("The logout request was rejected. Please reload or log in again.");
    else throw new Error("response");
  } catch (failure) {
    showError("Could not confirm logout. Please check your connection before continuing.");
  } finally {
    submitting = false;
    element("page-status").textContent = "";
    updateControls();
  }
}

element("open-month-entry").addEventListener("click", openMonthEntry);
element("work-category").addEventListener("change", updateEntryKind);
element("payroll-form").addEventListener("submit", submitPayroll);
element("logout-button").addEventListener("click", logout);

async function initialize() {
  try {
    await loadCsrfToken();
    await loadEmployments();
  } catch (failure) {
    showError("Could not prepare the secure employment page. Please reload before continuing.");
    element("page-status").textContent = "";
  }
}

initialize();
