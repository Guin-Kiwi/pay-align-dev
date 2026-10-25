"use strict";

const element = id => document.getElementById(id);
const value = id => element(id).value;
const loginFields = {email: "login-email", password: "login-password"};
const signupFields = {first_name: "signup-first-name", last_name: "signup-last-name", email: "signup-email", password: "signup-password"};
const rejectedRequest = "Your request was rejected. Reload the page and try again.";
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
  const idle = accountState === "signed-out" && !submitting && !navigating;
  element("login-submit").disabled = !idle;
  element("open-signup").disabled = !idle;
  element("signup-submit").disabled = !idle;
  element("signup-cancel").disabled = submitting || navigating;
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

function goToSetup(statusId, message) {
  navigating = true;
  element(statusId).textContent = message;
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

async function authenticate(request) {
  submitting = true;
  element(request.statusId).textContent = request.busy;
  updateControls();
  try {
    let token;
    try {
      token = await fetchCsrfToken();
    } catch (failure) {
      showMessage(request.errorId, "Could not reach PayAlign. Nothing was sent; please try again.");
      return;
    }
    const {status, body} = await postCredentials(request.path, request.payload, token);
    if (status === request.okStatus && isSession(body)) goToSetup(request.statusId, request.done);
    else if (!request.rejected(status, body)) {
      showMessage(request.errorId, `PayAlign returned an unexpected response (status ${status}). Please try again later. ${request.unsure}`.trim());
    }
  } catch (failure) {
    showMessage(request.errorId, `Could not reach PayAlign. Please check your connection and try again. ${request.unsure}`.trim());
  } finally {
    submitting = false;
    if (!navigating) element(request.statusId).textContent = "";
    updateControls();
  }
}

function loginRejected(status, body) {
  if (status === 401 || status === 422) showMessage("login-error", responseError(body));
  else if (status === 403) showMessage("login-error", rejectedRequest);
  else return false;
  return true;
}

function signupRejected(status, body) {
  if (status === 409) setFieldError("signup-email", `${responseError(body)} Log in instead, or use another email.`);
  else if (status === 422) showMessage("signup-error", responseError(body));
  else if (status === 403) showMessage("signup-error", rejectedRequest);
  else return false;
  return true;
}

function submitLogin(event) {
  event.preventDefault();
  if (submitting || navigating || accountState !== "signed-out") return;
  showMessage("login-error", "");
  if (!validateRequired(loginFields)) return;
  return authenticate({
    path: "/api/v1/auth/login", okStatus: 200,
    payload: {email: value("login-email"), password: value("login-password")},
    statusId: "login-status", errorId: "login-error", busy: "Logging in …", done: "Signed in. Opening setup …",
    unsure: "", rejected: loginRejected
  });
}

function submitSignup(event) {
  event.preventDefault();
  if (submitting || navigating || accountState !== "signed-out") return;
  showMessage("signup-error", "");
  if (!validateRequired(signupFields)) return;
  return authenticate({
    path: "/api/v1/auth/register", okStatus: 201,
    payload: Object.fromEntries(Object.entries(signupFields).map(([key, id]) => [key, value(id)])),
    statusId: "signup-status", errorId: "signup-error", busy: "Creating your account …", done: "Account created. Opening setup …",
    unsure: "The account may already have been created: log in with the same email before registering again.",
    rejected: signupRejected
  });
}

function resetSignup() {
  for (const id of Object.values(signupFields)) {
    element(id).value = "";
    setFieldError(id, "");
  }
  showMessage("signup-error", "");
  element("signup-status").textContent = "";
}

for (const id of [...Object.values(loginFields), ...Object.values(signupFields)]) {
  element(id).addEventListener("input", () => setFieldError(id, ""));
}
element("login-form").addEventListener("submit", submitLogin);
element("signup-form").addEventListener("submit", submitSignup);
element("open-signup").addEventListener("click", () => element("signup-dialog").showModal());
element("signup-cancel").addEventListener("click", () => element("signup-dialog").close());
element("signup-dialog").addEventListener("close", resetSignup);
element("signup-dialog").addEventListener("cancel", event => { if (submitting || navigating) event.preventDefault(); });
loadAccount();
