"use strict";

const value = id => element(id).value;
const form = element("setup-form");
const save = element("save-setup");
let employerState = "loading";
let csrfToken = null;
let submitting = false;
let submissionLocked = false;
const touched = new Set();
const employerFields = {name: "employer-name", address: "employer-address", ahv_number: "employer-ahv", contact_info: "employer-contact"};
const employeeFields = {name: "employee-name", address: "employee-address", ahv_number: "employee-ahv", nationality: "employee-nationality"};
const employmentFields = ["start-date", "end-date", "hourly-wage", "weekly-hours", "holiday-weeks"];
const allFields = [...Object.values(employerFields), ...Object.values(employeeFields), ...employmentFields];
const ahvPattern = /^756\.[0-9]{4}\.[0-9]{4}\.[0-9]{2}$/;

function fullMatch(pattern, text) {
  const match = pattern.exec(text);
  return Boolean(match && match[0] === text);
}

function isDate(text) {
  if (!fullMatch(/^[0-9]{4}-[0-9]{2}-[0-9]{2}$/, text)) return false;
  const parsed = new Date(`${text}T00:00:00Z`);
  return !Number.isNaN(parsed.getTime()) && parsed.toISOString().slice(0, 10) === text;
}

function showLoginMessage(container, message) {
  container.textContent = `${message} `;
  const button = document.createElement("button");
  button.type = "button";
  button.textContent = "Open the login page";
  button.addEventListener("click", () => window.location.assign("/login"));
  container.append(button);
  container.hidden = false;
}

function validateFields(reveal = false) {
  const errors = Object.fromEntries(allFields.map(id => [id, ""]));
  const required = [...Object.values(employeeFields), ...(employerState === "new" ? Object.values(employerFields) : [])];
  for (const id of required) {
    if (!value(id).trim()) errors[id] = "This field is required.";
    else if (id.endsWith("-ahv") && !fullMatch(ahvPattern, value(id))) {
      errors[id] = "Use the AHV format 756.XXXX.XXXX.XX.";
    }
  }
  if (!isDate(value("start-date")) || value("start-date") < RULES_YEAR_START || value("start-date") > RULES_YEAR_END) {
    errors["start-date"] = `Enter a start date in ${RULES_YEAR}.`;
  }
  if (value("end-date") && !isDate(value("end-date"))) errors["end-date"] = "Enter a valid end date.";
  else if (value("end-date") && isDate(value("start-date")) && value("end-date") < value("start-date")) {
    errors["end-date"] = "End date cannot be before the start date.";
  }
  if (!fullMatch(/^[0-9]+(?:\.[0-9]{1,2})?$/, value("hourly-wage")) || !Number.isFinite(Number(value("hourly-wage"))) || Number(value("hourly-wage")) < Number(MIN_HOURLY_WAGE) || Number(value("hourly-wage")) > Number(MAX_HOURLY_WAGE)) {
    errors["hourly-wage"] = `Enter CHF ${MIN_HOURLY_WAGE} to ${MAX_HOURLY_WAGE} per hour with at most two decimal places.`;
  }
  const hours = /^([0-9]{1,2}):([0-5][0-9])$/.exec(value("weekly-hours"));
  if (!hours || hours[0] !== value("weekly-hours") || Number(hours[1]) * 60 + Number(hours[2]) === 0) {
    errors["weekly-hours"] = "Use H:MM above 0:00 and up to 99:59, for example 6:30.";
  }
  if (!ALLOWED_HOLIDAY_WEEKS.map(String).includes(value("holiday-weeks"))) errors["holiday-weeks"] = `Holiday weeks must be ${ALLOWED_HOLIDAY_WEEKS.join(" or ")}.`;
  for (const [id, message] of Object.entries(errors)) {
    element(id).setCustomValidity(message);
    if (reveal || touched.has(id)) {
      element(id).setAttribute("aria-invalid", String(Boolean(message)));
      element(`${id}-error`).textContent = message;
      element(`${id}-error`).hidden = !message;
    }
  }
  const valid = Object.values(errors).every(message => !message);
  save.disabled = !csrfToken || !["new", "existing"].includes(employerState) || submitting || submissionLocked;
  return valid;
}

async function loadCsrfToken() {
  try {
    const response = await fetch("/api/v1/auth/csrf", {headers: {Accept: "application/json"}, cache: "no-store"});
    const body = await response.json();
    if (response.status !== 200 || typeof body?.csrf_token !== "string" || !body.csrf_token) throw new Error("response");
    csrfToken = body.csrf_token;
  } catch (failure) {
    csrfToken = null;
    element("setup-error").textContent = "Could not prepare the secure setup form. Please reload the page before saving.";
    element("setup-error").hidden = false;
  } finally {
    validateFields();
  }
}

async function loadEmployer() {
  employerState = "loading";
  element("employer-fields").disabled = true;
  element("employer-error").hidden = true;
  element("employer-details").hidden = true;
  element("employer-status").textContent = "Loading employer status …";
  validateFields();
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 10000);
  try {
    const response = await fetch("/api/v1/employer", {
      headers: {Accept: "application/json"}, cache: "no-store", signal: controller.signal
    });
    const body = await response.json();
    if (response.status === 401) {
      employerState = "failed";
      element("employer-status").textContent = "Session expired.";
      showLoginMessage(element("employer-error"), "Your session has expired. Please log in again to continue.");
    } else if (response.status === 404 && body?.detail === "No employer is set up yet.") {
      employerState = "failed";
      window.location.replace("/employer-setup");
    } else {
      if (response.status !== 200 || !body || !Number.isSafeInteger(body.id) || body.id <= 0 ||
          !Object.keys(employerFields).every(key => typeof body[key] === "string" && body[key].trim()) ||
          !fullMatch(ahvPattern, body.ahv_number)) throw new Error("response");
      const details = element("employer-details");
      details.textContent = "";
      const labels = {name: "Name", address: "Address", ahv_number: "AHV number", contact_info: "Contact details"};
      for (const [key, label] of Object.entries(labels)) {
        const term = document.createElement("dt");
        const text = document.createElement("dd");
        term.textContent = label;
        text.textContent = body[key];
        details.append(term, text);
      }
      details.hidden = false;
      element("employer-fields").hidden = true;
      employerState = "existing";
      element("employer-status").textContent = "Existing employer loaded.";
    }
  } catch (failure) {
    employerState = "failed";
    element("employer-status").textContent = "Could not load the employer status.";
    element("employer-error").textContent = "Please check your connection and reload the page before saving.";
    element("employer-error").hidden = false;
  } finally {
    clearTimeout(timeout);
    validateFields();
  }
}

function buildPayload() {
  const details = fields => Object.fromEntries(Object.entries(fields).map(([key, id]) => [key, value(id)]));
  const payload = {
    employee: {...details(employeeFields), tax_status: "ordinary"},
    employment: {
      start_date: value("start-date"), end_date: value("end-date") || null,
      hourly_wage: value("hourly-wage"), weekly_hours: value("weekly-hours"),
      holiday_weeks: Number(value("holiday-weeks"))
    }
  };
  if (employerState === "new") payload.employer = details(employerFields);
  return payload;
}

function responseError(body) {
  if (typeof body?.detail === "string") return body.detail;
  if (Array.isArray(body?.detail)) {
    return body.detail.map(error => {
      if (typeof error?.msg !== "string") return "Invalid input.";
      const location = Array.isArray(error.loc) ? error.loc.filter(part => typeof part === "string" || typeof part === "number").join(" → ") : "";
      return `${location ? `${location}: ` : ""}${error.msg}`;
    }).join("\n");
  }
  return "Please check the entered values and try again.";
}

function describeEmployment({employee, employment}) {
  const period = employment.end_date ? `from ${employment.start_date} to ${employment.end_date}` : `from ${employment.start_date}, with no end date`;
  return `Employee: ${employee.name}. Employment ${period}, CHF ${employment.hourly_wage} an hour, ${employment.weekly_hours} hours a week, ${employment.holiday_weeks} holiday weeks.`;
}

function submitSetup(event) {
  event.preventDefault();
  if (submitting || submissionLocked || !csrfToken || !["new", "existing"].includes(employerState)) return;
  if (!validateFields(true)) {
    const firstInvalid = allFields.find(id => element(id).validationMessage);
    if (firstInvalid) element(firstInvalid).focus();
    return;
  }
  element("add-employment-summary").textContent = describeEmployment(buildPayload());
  warning.showModal();
}

async function saveSetup() {
  const payload = buildPayload();
  submitting = true;
  element("add-employment-confirm").disabled = true;
  element("add-employment-cancel").disabled = true;
  element("add-employment-status").textContent = "Saving employment …";
  form.setAttribute("aria-busy", "true");
  element("setup-error").hidden = true;
  element("setup-success").hidden = true;
  element("setup-complete-actions").hidden = true;
  element("setup-status").textContent = "Saving setup …";
  validateFields();
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15000);
  try {
    const response = await fetch("/api/v1/setup", {
      method: "POST", headers: {"Content-Type": "application/json", Accept: "application/json", "X-CSRF-Token": csrfToken},
      body: JSON.stringify(payload), signal: controller.signal
    });
    const body = await response.json();
    if (response.status === 201) {
      if (typeof body?.message !== "string" || !body.message.trim() ||
          !["employer_id", "employee_id", "employment_id"].every(key => Number.isSafeInteger(body[key]) && body[key] > 0)) {
        throw new Error("response");
      }
      submissionLocked = true;
      window.location.replace("/employments");
    } else if ([401, 403].includes(response.status)) {
      showLoginMessage(
        element("setup-error"),
        "Authentication/session or CSRF validation failed. The request was rejected. Please log in again."
      );
    } else if ([400, 409, 422].includes(response.status)) {
      element("setup-error").textContent = responseError(body) + (response.status === 409 ? " Reload the page to refresh the employer status." : "");
      element("setup-error").hidden = false;
    } else {
      throw new Error("response");
    }
  } catch (failure) {
    submissionLocked = true;
    element("setup-error").textContent = "The request outcome is uncertain: setup may have been saved. Do not submit again until you have checked the result. No automatic retry was made.";
    element("setup-error").hidden = false;
  } finally {
    clearTimeout(timeout);
    submitting = false;
    form.setAttribute("aria-busy", "false");
    element("setup-status").textContent = "";
    element("add-employment-status").textContent = "";
    element("add-employment-confirm").disabled = false;
    element("add-employment-cancel").disabled = false;
    warning.close();
    validateFields();
  }
}

for (const id of allFields) {
  element(id).addEventListener(id === "holiday-weeks" ? "change" : "input", () => {
    touched.add(id);
    if (id === "start-date" && value("end-date")) touched.add("end-date");
    validateFields();
  });
}
const warning = wireWarningDialog({
  dialogId: "add-employment-dialog", confirmId: "add-employment-confirm", cancelId: "add-employment-cancel",
  onConfirm: saveSetup, isBusy: () => submitting
});
form.addEventListener("submit", submitSetup);
element("view-employments").addEventListener("click", () => window.location.assign("/employments"));
async function initialize() {
  await loadCsrfToken();
  await loadEmployer();
}
initialize();
