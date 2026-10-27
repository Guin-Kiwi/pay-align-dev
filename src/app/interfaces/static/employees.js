"use strict";

const PAYSLIP_PAGE = "/payslips";
let detailsVersion = 0;

function showError(message) {
  element("page-error").textContent = message;
  element("page-error").hidden = false;
}

function showLoginMessage(message) {
  const container = element("page-error");
  container.textContent = `${message} `;
  container.append(actionButton("Open the login page", () => window.location.assign("/login")));
  container.hidden = false;
}

function make(tag, className, text) {
  const node = document.createElement(tag);
  node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function actionButton(text, onClick) {
  const button = make("button", "", text);
  button.type = "button";
  button.addEventListener("click", onClick);
  return button;
}

function box(kind, title, ...nodes) {
  const section = make("section", `person-box ${kind}`);
  section.append(make("h4", "", title), ...nodes);
  return section;
}

function payslipUrl(employmentId, year, month) {
  return `${PAYSLIP_PAGE}?employment_id=${employmentId}&year=${year}&month=${month}`;
}

function personSubheading(employments) {
  const first = employments.map(employment => employment.start_date).sort()[0];
  const count = employments.length > 1 ? ` · ${employments.length} employments` : "";
  return `Employed since ${longDate(first)}${count}`;
}

function payslipPicker(person, months) {
  const picker = make("select", "");
  picker.setAttribute("aria-label", `Payslip month for ${person.name}`);
  const several = person.employments.length > 1;
  const choices = (months ?? []).slice().sort((a, b) => b.year - a.year || b.month - a.month || b.employment.id - a.employment.id);
  for (const {employment, year, month} of choices) {
    const option = make("option", "", `${monthLabel(year, month)}${several ? ` · employment from ${longDate(employment.start_date)}` : ""}`);
    option.value = `${employment.id}:${year}-${month}`;
    picker.append(option);
  }
  if (choices.length) picker.value = picker.children[0].value;
  else {
    picker.append(make("option", "", months === null ? "The months could not be loaded" : "No saved months yet"));
    picker.disabled = true;
  }
  const view = actionButton("View payslip", () => {
    const [employmentId, period] = picker.value.split(":");
    const [year, month] = period.split("-");
    window.location.assign(payslipUrl(employmentId, year, month));
  });
  view.disabled = !choices.length;
  return {picker, view};
}

function agreementBox(person, months) {
  const parts = [];
  for (const employment of person.employments) {
    parts.push(make("p", "subheading", employmentSubheading(employment)), cardRows([
      {label: "Hourly wage", value: formatMoney(employment.hourly_wage)},
      {label: "Weekly hours", value: formatDuration(employment.weekly_minutes)},
      {label: "Holiday weeks", value: String(employment.holiday_weeks)}
    ]));
  }
  const {picker, view} = payslipPicker(person, months);
  parts.push(cardRows([
    {label: "Payslip", value: picker, action: view},
    {label: "Personal details", value: "Shown on request", action: actionButton("Employee details", () => showDetails(person))}
  ]));
  return box("agreement", "Agreement", ...parts);
}

function todoBox(person) {
  const rows = todoRows(person);
  return box("todo", "To do", rows.length ? cardRows(rows) : cardNote("Nothing to do"));
}

function numbersBox(person) {
  const totals = person.totals;
  const balance = person.holiday_balance_minutes;
  const sections = [
    ["Pay so far", [
      {label: "Gross wage", value: formatMoney(totals.gross_wage)},
      {label: "Net payout", value: formatMoney(totals.net_payout)},
      {label: "Cash bonus", value: formatMoney(totals.cash_bonus)},
      {label: "Expense reimbursements", value: formatMoney(totals.expense_reimbursements)}
    ]],
    ["Employer cost", [
      {label: "AHV / IV / EO", value: formatMoney(totals.employer_ahv)},
      {label: "ALV", value: formatMoney(totals.employer_alv)},
      {label: "Family allowance (FAK)", value: formatMoney(totals.employer_fak)},
      {label: "Occupational accident insurance (BU)", value: formatMoney(totals.employer_bu)},
      {label: "Administration charge", value: formatMoney(totals.admin_charge)},
      {label: "Total employer cost", value: formatMoney(totals.total_employer_cost)}
    ]],
    ["Hours and leave", [
      {label: "Hours worked", value: formatDuration(totals.worked_minutes)},
      {label: "Annual holiday taken", value: formatDuration(totals.annual_holiday_taken_minutes)},
      {label: "Paid public holidays", value: formatDuration(totals.public_holiday_taken_minutes)},
      {label: "Holiday balance", value: balance === null ? "No month saved yet" : formatDuration(balance)}
    ]]
  ];
  const parts = sections.flatMap(([title, rows]) => [make("h5", "", title), cardRows(rows)]);
  parts.push(make("h5", "", "Wage limit"));
  parts.push(cardRows([{label: "This employee", value: limitText(person.wage_limit)}]), limitBar(person.wage_limit, "This employee"));
  return box("numbers", "The year so far", ...parts);
}

async function loadMonths(employment) {
  try {
    const {status, body} = await call(`/api/v1/employments/${employment.id}/months`, {headers: {Accept: "application/json"}, cache: "no-store"});
    if (status !== 200 || !Array.isArray(body?.months)) throw new Error("months");
    return body.months.map(item => ({employment, year: item.year, month: item.month}));
  } catch (error) {
    return null;
  }
}

async function showDetails(person) {
  const version = ++detailsVersion;
  element("details-title").textContent = person.name;
  element("details-status").textContent = "Loading details …";
  element("details-rows").replaceChildren();
  element("details-dialog").showModal();
  try {
    const {status, body} = await call(`/api/v1/employees/${person.id}`, {headers: {Accept: "application/json"}, cache: "no-store"});
    if (status !== 200) throw new Error("details");
    if (version !== detailsVersion) return;
    element("details-rows").replaceChildren(cardRows([
      {label: "Address", value: body.address},
      {label: "AHV number", value: body.ahv_number},
      {label: "Nationality", value: body.nationality},
      {label: "Tax status", value: body.tax_status}
    ]));
    element("details-status").textContent = "";
  } catch (error) {
    if (version === detailsVersion) element("details-status").textContent = "The details could not be loaded. Please close this window and try again.";
  }
}

async function personCard(person) {
  const lists = await Promise.all(person.employments.map(loadMonths));
  const months = lists.includes(null) ? null : lists.flat();
  const card = make("li", "person-card");
  const left = make("div", "person-left");
  left.append(agreementBox(person, months), todoBox(person));
  const grid = make("div", "person-grid");
  grid.append(left, numbersBox(person));
  card.append(make("h3", "", person.name), make("p", "subheading", personSubheading(person.employments)), grid);
  return card;
}

async function loadEmployees() {
  element("page-status").textContent = "Loading employees …";
  try {
    const {status, body} = await call("/api/v1/employees", {headers: {Accept: "application/json"}, cache: "no-store"});
    if (status === 401) {
      element("page-status").textContent = "";
      showLoginMessage("Your session has expired. Please log in again to continue.");
      return;
    }
    if (status !== 200 || !Array.isArray(body?.employees)) throw new Error("response");
    const cards = await Promise.all(body.employees.map(personCard));
    element("employee-list").replaceChildren(...cards);
    element("no-employees").hidden = cards.length !== 0;
    element("page-status").textContent = "";
  } catch (error) {
    element("page-status").textContent = "";
    showError("Could not load employees. Please check your connection and reload the page.");
  }
}

element("details-close").addEventListener("click", () => element("details-dialog").close());
loadEmployees();
