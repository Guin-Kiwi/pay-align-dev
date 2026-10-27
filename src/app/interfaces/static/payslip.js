"use strict";

const employment = element("employment");
const month = element("month");
const TIMESHEETS_PAGE = "/timesheets";
let requestVersion = 0;
let employerName = "";
let employments = [];

function showError(message, retry = false) {
  element("error").textContent = message;
  element("error").hidden = !message;
  element("retry").hidden = !retry;
  element("login-link").hidden = true;
}

async function readJSON(url) {
  const response = await fetch(url, {headers: {Accept: "application/json"}, cache: "no-store"});
  if (response.status === 401) throw new Error("session");
  if (response.status === 404) throw new Error("not-found");
  if (!response.ok) throw new Error("request");
  return response.json();
}

function failure(error, retry = false) {
  element("status").textContent = "";
  if (error.message === "session") {
    showError("Your session has expired. Please sign in again.");
    element("login-link").hidden = false;
    return;
  }
  showError(error.message === "not-found" ? "This employment or payslip could not be found." : "The payslip could not be loaded. Please try again.", retry);
}

function cents(value) {
  const match = /^(\d+)\.(\d{2})$/.exec(value);
  if (!match) throw new Error("Invalid monetary amount");
  return BigInt(match[1]) * 100n + BigInt(match[2]);
}

function money(value) {
  const amount = typeof value === "bigint" ? value : cents(value);
  const negative = amount < 0n;
  const absolute = negative ? -amount : amount;
  return `${negative ? "−" : ""}CHF ${absolute / 100n}.${String(absolute % 100n).padStart(2, "0")}`;
}

function duration(minutes) {
  if (!Number.isSafeInteger(minutes) || minutes < 0) throw new Error("Invalid duration");
  return `${Math.floor(minutes / 60)} h ${String(minutes % 60).padStart(2, "0")} min`;
}

function option(value, label) {
  const item = document.createElement("option");
  item.value = value;
  item.textContent = label;
  return item;
}

function periodName(year, number) {
  return new Intl.DateTimeFormat("en-CH", {month: "long", year: "numeric", timeZone: "UTC"}).format(new Date(Date.UTC(year, number - 1, 1)));
}

function render(detail, employee, year, number) {
  const amounts = {
    "hourly-wage": detail.hourly_wage, bonus: detail.cash_bonus, gross: detail.gross_wage,
    ahv: detail.ahv_deduction, alv: detail.alv_deduction, tax: detail.tax_deduction,
    nbu: detail.nbu_deduction, expenses: detail.expense_reimbursements, net: detail.net_payout,
    "employer-ahv": detail.employer_ahv, "employer-alv": detail.employer_alv,
    "employer-fak": detail.employer_fak, "employer-bu": detail.employer_bu,
    admin: detail.admin_charge, "employer-total": detail.total_employer_cost,
    "hourly-pay": cents(detail.gross_wage) - cents(detail.cash_bonus),
    deductions: [detail.ahv_deduction, detail.alv_deduction, detail.tax_deduction, detail.nbu_deduction].reduce((sum, value) => sum + cents(value), 0n)
  };
  const durations = {worked: detail.worked_minutes, "public-worked": detail.public_holiday_worked_minutes,
    "annual-holiday": detail.annual_holiday_taken_minutes, "public-holiday": detail.public_holiday_taken_minutes,
    "holiday-balance": detail.holiday_balance_minutes};
  const formatted = Object.fromEntries(Object.entries(amounts).map(([id, value]) => [id, money(value)]));
  Object.assign(formatted, Object.fromEntries(Object.entries(durations).map(([id, value]) => [id, duration(value)])));
  Object.entries(formatted).forEach(([id, value]) => { element(id).textContent = value; });
  element("employer-name").textContent = employerName;
  element("employee-name").textContent = employee.employee_name;
  element("employee-ahv-number").textContent = employee.employee_ahv_number;
  element("period").textContent = periodName(year, number);
  element("payslip").hidden = false;
  element("employer-costs").hidden = false;
  element("print").hidden = false;
}

async function loadDetail() {
  const version = ++requestVersion;
  element("payslip").hidden = true;
  element("employer-costs").hidden = true;
  element("print").hidden = true;
  showError("");
  if (!employment.value || !month.value) return;
  const [year, number] = month.value.split("-").map(Number);
  const selected = employments.find(item => String(item.id) === employment.value);
  if (!selected || !Number.isInteger(year) || number < 1 || number > 12) return;
  element("status").textContent = "Loading payslip…";
  try {
    const [detail, employee] = await Promise.all([
      readJSON(`/api/v1/employments/${selected.id}/months/${year}/${number}`),
      readJSON(`/api/v1/employments/${selected.id}`)
    ]);
    if (version !== requestVersion) return;
    render(detail, employee, year, number);
    element("status").textContent = "";
  } catch (error) {
    if (version === requestVersion) failure(error, true);
  }
}

async function loadMonths(preselected = "") {
  const version = ++requestVersion;
  element("enter-timesheet").hidden = true;
  element("payslip").hidden = true;
  element("employer-costs").hidden = true;
  element("print").hidden = true;
  showError("");
  month.disabled = true;
  month.replaceChildren(option("", "Loading months…"));
  if (!employment.value) {
    month.replaceChildren(option("", "Select an employee first"));
    element("status").textContent = "";
    return;
  }
  element("status").textContent = "Loading months…";
  try {
    const history = await readJSON(`/api/v1/employments/${employment.value}/months`);
    if (version !== requestVersion) return;
    month.replaceChildren(option("", history.months.length ? "Select a month" : "No completed months"));
    history.months.forEach(item => month.append(option(`${item.year}-${item.month}`, periodName(item.year, item.month))));
    month.disabled = !history.months.length;
    if (history.next_month) {
      element("enter-timesheet").textContent = `Enter timesheet for ${periodName(history.next_month.year, history.next_month.month)}`;
      element("enter-timesheet").hidden = false;
    }
    element("status").textContent = history.months.length ? "" : "There are no saved payslips for this employee yet.";
    if (preselected && [...month.options].some(item => item.value === preselected)) {
      month.value = preselected;
      await loadDetail();
    } else if (preselected) {
      showError("This employment or payslip could not be found.");
    }
  } catch (error) {
    if (version === requestVersion) failure(error);
  }
}

async function initialise() {
  try {
    const saved = JSON.parse(window.sessionStorage.getItem("payalign-saved-confirmation") || "null");
    if (saved && saved.url === `${window.location.pathname}${window.location.search}` && typeof saved.message === "string") {
      element("save-confirmation").textContent = saved.message;
      element("save-confirmation").hidden = false;
      window.sessionStorage.removeItem("payalign-saved-confirmation");
    }
  } catch (error) { /* Browsing without session storage still opens the saved payslip. */ }
  try {
    const [employer, list] = await Promise.all([readJSON("/api/v1/employer"), readJSON("/api/v1/employments")]);
    employerName = employer.name;
    employments = list;
    employment.replaceChildren(option("", list.length ? "Select an employee" : "No employments found"));
    list.forEach(item => employment.append(option(String(item.id), `${item.employee_name} · from ${item.start_date}${item.end_date ? ` to ${item.end_date}` : ""}`)));
    employment.disabled = !list.length;
    if (!list.length) element("status").textContent = "Set up an employment before viewing payslips.";
    const params = new URLSearchParams(window.location.search);
    const id = params.get("employment_id");
    const year = params.get("year");
    const number = params.get("month");
    if (id && list.some(item => String(item.id) === id)) {
      employment.value = id;
      await loadMonths(year && number ? `${Number(year)}-${Number(number)}` : "");
    } else if (id) {
      showError("This employment or payslip could not be found.");
    }
  } catch (error) {
    failure(error);
  }
}

employment.addEventListener("change", () => loadMonths());
element("enter-timesheet").addEventListener("click", () => window.location.assign(`${TIMESHEETS_PAGE}?employment_id=${employment.value}`));
month.addEventListener("change", loadDetail);
element("retry").addEventListener("click", loadDetail);
element("print").addEventListener("click", () => window.print());
element("sign-in").addEventListener("click", () => window.location.assign("/login"));
initialise();
