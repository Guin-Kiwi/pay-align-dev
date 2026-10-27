"use strict";

const PAYSLIP_PAGE = "/payslips";
let csrfToken = null;
let submitting = false;
let overviewVersion = 0;
let employmentItems = [];
const tasks = new Map();
let showAllEmployments = false;
const overviewRows = new Map();

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
  const button = document.createElement("button");
  button.type = "button";
  button.textContent = "Open the login page";
  button.addEventListener("click", () => window.location.assign("/login"));
  container.append(button);
  container.hidden = false;
}

function updateEmploymentVisibility() {
  employmentItems.forEach((item, index) => { item.hidden = !showAllEmployments && index >= 3; });
  element("show-employments").hidden = employmentItems.length <= 3;
  element("show-employments").textContent = showAllEmployments ? "Show fewer employments" : `View all employments (${employmentItems.length})`;
  element("show-employments").setAttribute("aria-expanded", String(showAllEmployments));
}

async function loadOverview() {
  const version = ++overviewVersion;
  const month = Number(element("overview-month").value);
  element("overview-completeness").textContent = "Loading payroll overview…";
  for (const id of ["overview-payout", "overview-reserve", "overview-cost"]) element(id).textContent = "—";
  try {
    const result = await call(`/api/v1/payroll-overview?year=${RULES_YEAR}&month=${month}`, {headers: {Accept: "application/json"}, cache: "no-store"});
    if (version !== overviewVersion) return;
    if (result.status !== 200 || !Array.isArray(result.body?.employments)) throw new Error("overview");
    const data = result.body;
    element("overview-completeness").textContent = data.eligible_count ? `${data.saved_count} of ${data.eligible_count} employments have saved payroll for ${monthLabel(RULES_YEAR, month)}.` : "No employments for this month.";
    if (data.saved_count) {
      element("overview-payout").textContent = formatMoney(data.payout_due);
      element("overview-reserve").textContent = formatMoney(data.estimated_set_aside);
      element("overview-cost").textContent = formatMoney(data.employer_cost);

    }
    for (const [id, card] of overviewRows) {
      const item = data.employments.find(value => value.employment.id === id);
      const todo = taskRows(id);
      const todoTable = todo.length ? [cardRows(todo)] : [];
      if (!item) showCardBody(card, cardNote("Not employed in this month."), ...todoTable);
      else if (!item.payslip) showCardBody(card, cardNote("No saved payroll for this month."), ...todoTable);
      else {
        const button = document.createElement("button");
        button.type = "button";
        button.textContent = "View payslip";
        button.addEventListener("click", () => { if (confirmBeforeLeaving()) window.location.assign(payslipUrl(id, RULES_YEAR, month)); });
        const minutes = item.payslip.holiday_balance_minutes;
        showCardBody(card, cardRows([
          {label: "Payout due", value: formatMoney(item.payslip.net_payout)},
          {label: "Employer cost", value: formatMoney(item.payslip.total_employer_cost)},
          {label: "Holiday balance after this month", value: formatDuration(minutes)},
          {label: "Payslip", value: monthLabel(RULES_YEAR, month), action: button},
          ...todo
        ]));
      }
    }
  } catch (error) {
    if (version === overviewVersion) element("overview-completeness").textContent = "Could not load the payroll overview. Please try another month or reload.";
  }
}

async function logout() {
  if (!csrfToken || submitting) return;
  if (!confirmBeforeLeaving()) return;
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

function payslipUrl(employmentId, year, month) {
  return `${PAYSLIP_PAGE}?employment_id=${employmentId}&year=${year}&month=${month}`;
}

function monthIndex(year, month) {
  return year * 12 + month - 1;
}

function updateControls() {
  element("logout-button").disabled = !csrfToken || submitting;
}

async function loadCsrfToken() {
  csrfToken = await fetchCsrfToken();
  updateControls();
}

async function loadHistory(employment) {
  try {
    const {status, body} = await call(`/api/v1/employments/${employment.id}/months`, {headers: {Accept: "application/json"}, cache: "no-store"});
    if (status !== 200 || !Array.isArray(body?.months)) throw new Error("history");
    return body;
  } catch (error) {
    return null;
  }
}

function showCardBody(card, ...nodes) {
  card.replaceChildren(card.children[0], card.children[1], card.children[2], ...nodes);
}

function taskRows(employmentId) {
  const entry = tasks.get(employmentId);
  return entry ? todoRows({name: entry.name, employments: [entry.employment]}) : [];
}

function showTasks(card, employmentId) {
  const status = document.createElement("p");
  const entry = tasks.get(employmentId);
  status.hidden = !entry;
  if (entry) {
    const pending = entry.employment.months_due;
    status.className = `tasks ${pending ? "pending" : "done"}`;
    status.textContent = pending ? `${pending} ${pending === 1 ? "action" : "actions"} pending` : "All actions completed";
    if (pending) card.className = "employee-card pending";
  }
  card.append(status);
}

function employmentRow(employment) {
  const item = employeeCard(employment);
  showTasks(item, employment.id);
  overviewRows.set(employment.id, item);
  return {item, history: loadHistory(employment)};
}

async function loadEmployments() {
  element("page-status").textContent = "Loading employments …";
  try {
    const {status, body} = await call("/api/v1/employments", {headers: {Accept: "application/json"}, cache: "no-store"});
    if (status === 401) {
      element("page-status").textContent = "";
      showLoginMessage("Your session has expired. Please log in again to continue.");
      return [];
    }
    if (status !== 200 || !Array.isArray(body)) throw new Error("response");
    overviewRows.clear();
    const rows = body.map(employmentRow);
    employmentItems = rows.map(row => row.item);
    element("employment-list").replaceChildren(...employmentItems);
    updateEmploymentVisibility();
    element("employment-empty").hidden = body.length !== 0;
    element("page-status").textContent = "";
    return Promise.all(rows.map(row => row.history));
  } catch (failure) {
    element("page-status").textContent = "";
    showError("Could not load employments. Please check your connection and reload the page.");
    return [];
  }
}

function showHousehold(limit) {
  element("household-status").textContent = limit ? "" : "No employees yet.";
  const note = element("household-note");
  note.hidden = !limit;
  if (!limit) return element("household-rows").replaceChildren();
  const line = document.createElement("p");
  line.textContent = limitText(limit);
  element("household-rows").replaceChildren(line, limitBar(limit, "The household"));
  note.textContent = `The simplified procedure only applies while the wages you pay in a year stay within ${formatMoney(limit.limit)}. If you employ people for more than this, it no longer applies.`;
}

async function loadEmployees() {
  try {
    const {status, body} = await call("/api/v1/employees", {headers: {Accept: "application/json"}, cache: "no-store"});
    if (status !== 200 || !Array.isArray(body?.employees)) throw new Error("employees");
    tasks.clear();
    for (const person of body.employees) {
      for (const employment of person.employments) tasks.set(employment.id, {name: person.name, employment});
    }
    showHousehold(body.household);
  } catch (error) {
    element("household-status").textContent = "The household limit and your actions could not be loaded. Reload the page to try again.";
  }
}

function defaultOverviewMonth(histories) {
  const latest = histories.filter(Boolean).flatMap(history => history.months)
    .reduce((result, item) => !result || monthIndex(item.year, item.month) > monthIndex(result.year, result.month) ? item : result, null);
  if (latest) return latest.month;
  const today = new Date();
  return today.getFullYear() === RULES_YEAR ? today.getMonth() + 1 : 12;
}

element("add-employment").addEventListener("click", () => { if (confirmBeforeLeaving()) window.location.assign("/setup"); });
element("employer-details-button").addEventListener("click", () => { if (confirmBeforeLeaving()) window.location.assign("/employer-setup"); });
element("overview-month").addEventListener("change", loadOverview);
element("show-employments").addEventListener("click", () => {
  showAllEmployments = !showAllEmployments;
  updateEmploymentVisibility();
});
element("logout-button").addEventListener("click", logout);

window.addEventListener("payalign-payroll-saved", async () => {
  await loadEmployees();
  await loadEmployments();
  await loadOverview();
});

async function initialize() {
  try {
    await loadCsrfToken();
    const employer = await call("/api/v1/employer", {headers: {Accept: "application/json"}, cache: "no-store"});
    if (employer.status === 200) {
      element("employer-status").textContent = "";
      element("add-employment").disabled = false;
    } else if (employer.status === 404 && employer.body?.detail === "No employer is set up yet.") {
      element("employer-status").textContent = "Enter your account details before adding an employment.";
    } else if (employer.status === 401) {
      showLoginMessage("Your session has expired. Please log in again to continue.");
      return;
    } else throw new Error("employer");
    await loadEmployees();
    const histories = await loadEmployments();
    element("overview-month").value = String(defaultOverviewMonth(histories));
    await loadOverview();
  } catch (failure) {
    showError("Could not prepare the employment page. Please reload before continuing.");
    element("page-status").textContent = "";
  }
}

initialize();
