"use strict";

const element = id => document.getElementById(id);
const value = id => element(id).value;
const loginFields = {email: "login-email", password: "login-password"};
let accountState = "loading";
let submitting = false;
let navigating = false;

function showMessage(id, message) {
  element(id).textContent = message;
  element(id).hidden = !message;
}

function setFieldError(id, message) {
  element(id).setAttribute("aria-invalid", String(Boolean(message)));
  showMessage(`${id}-error`, message);
}

function validateRequired(fields) {
  let valid = true;
  for (const id of Object.values(fields)) {
    const message = value(id).trim() ? "" : "This field is required.";
    setFieldError(id, message);
    valid = valid && !message;
  }
  return valid;
}

function updateControls() {
  element("login-submit").disabled = accountState !== "signed-out" || submitting || navigating;
}

function isAccount(body) {
  return Number.isSafeInteger(body?.id) && body.id > 0 &&
    ["email", "first_name", "last_name"].every(key => typeof body[key] === "string" && body[key]);
}

function isSession(body) {
  return isAccount(body) && typeof body.csrf_token === "string" && Boolean(body.csrf_token);
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

async function call(url, options, timeoutMs) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(url, {...options, signal: controller.signal});
    return {status: response.status, body: await response.json()};
  } finally {
    clearTimeout(timeout);
  }
}

async function fetchCsrfToken() {
  const {status, body} = await call("/api/v1/auth/csrf", {headers: {Accept: "application/json"}, cache: "no-store"}, 10000);
  if (status !== 200 || typeof body?.csrf_token !== "string" || !body.csrf_token) throw new Error("response");
  return body.csrf_token;
}

function postCredentials(path, payload, token) {
  return call(path, {
    method: "POST",
    headers: {"Content-Type": "application/json", Accept: "application/json", "X-CSRF-Token": token},
    body: JSON.stringify(payload)
  }, 15000);
}

function goToSetup(statusId) {
  navigating = true;
  element(statusId).textContent = "Signed in. Opening setup …";
  window.location.assign("/setup");
}

async function loadAccount() {
  accountState = "loading";
  element("account-status").textContent = "Checking whether you are signed in …";
  updateControls();
  try {
    const {status, body} = await call("/api/v1/auth/me", {headers: {Accept: "application/json"}, cache: "no-store"}, 10000);
    if (status === 401) {
      accountState = "signed-out";
    } else if (status === 200 && isAccount(body)) {
      accountState = "signed-in";
      element("signed-in-name").textContent = `Signed in as ${body.first_name} ${body.last_name} (${body.email}).`;
      element("signed-in").hidden = false;
      element("login-panel").hidden = true;
    } else {
      throw new Error("response");
    }
    element("account-status").textContent = "";
  } catch (failure) {
    accountState = "failed";
    element("account-status").textContent = "Could not check whether you are signed in.";
    showMessage("account-error", "Please check your connection and reload the page before logging in.");
  } finally {
    updateControls();
  }
}

function loginFailure(status, body) {
  if (status === 401 || status === 422) return responseError(body);
  if (status === 403) return "Your request was rejected. Reload the page and try again.";
  return `PayAlign could not log you in (status ${status}). Please try again later.`;
}

async function submitLogin(event) {
  event.preventDefault();
  if (submitting || navigating || accountState !== "signed-out") return;
  showMessage("login-error", "");
  if (!validateRequired(loginFields)) return;
  submitting = true;
  element("login-status").textContent = "Logging in …";
  updateControls();
  try {
    let token;
    try {
      token = await fetchCsrfToken();
    } catch (failure) {
      showMessage("login-error", "Could not reach PayAlign. Nothing was sent; please try again.");
      return;
    }
    const {status, body} = await postCredentials(
      "/api/v1/auth/login", {email: value("login-email"), password: value("login-password")}, token
    );
    if (status === 200 && isSession(body)) goToSetup("login-status");
    else showMessage("login-error", status === 200 ? "Unexpected response from PayAlign. Please try again." : loginFailure(status, body));
  } catch (failure) {
    showMessage("login-error", "Could not reach PayAlign. Please check your connection and try again.");
  } finally {
    submitting = false;
    if (!navigating) element("login-status").textContent = "";
    updateControls();
  }
}

for (const id of Object.values(loginFields)) {
  element(id).addEventListener("input", () => setFieldError(id, ""));
}
element("login-form").addEventListener("submit", submitLogin);
loadAccount();
