"use strict";

let csrfToken = null;
let locked = false;
let editing = false;

function showError(message, login = false) {
  element("error").textContent = message;
  element("error").hidden = false;
  element("login").hidden = !login;
}

async function initialise() {
  try {
    const employer = await fetch("/api/v1/employer", {cache: "no-store"});
    if (employer.status === 200) {
      const details = await employer.json();
      if (!Number.isSafeInteger(details?.id) || ![details.name, details.address, details.ahv_number, details.contact_info].every(value => typeof value === "string")) throw new Error("employer");
      element("name").value = details.name;
      element("address").value = details.address;
      element("ahv-number").value = details.ahv_number;
      element("contact-info").value = details.contact_info;
      editing = true;
    }
    if (employer.status === 401) { showError("Your session has expired. Please sign in again.", true); return; }
    if (!editing && (employer.status !== 404 || (await employer.json())?.detail !== "No employer is set up yet.")) throw new Error("employer");
    const response = await fetch("/api/v1/auth/csrf", {cache: "no-store"});
    const body = await response.json();
    if (response.status !== 200 || typeof body?.csrf_token !== "string" || !body.csrf_token) throw new Error("csrf");
    csrfToken = body.csrf_token;
    element("save").disabled = false;
  } catch (error) {
    showError("Could not prepare employer setup. Please reload the page.");
  } finally {
    element("status").textContent = "";
  }
}

element("employer-form").addEventListener("submit", async event => {
  event.preventDefault();
  if (!csrfToken || locked || !element("employer-form").reportValidity()) return;
  locked = true;
  element("save").disabled = true;
  element("error").hidden = true;
  element("status").textContent = "Saving employer details…";
  try {
    const response = await fetch("/api/v1/employer", {
      method: editing ? "PUT" : "POST",
      headers: {"Content-Type": "application/json", Accept: "application/json", "X-CSRF-Token": csrfToken},
      body: JSON.stringify({name: element("name").value, address: element("address").value, ahv_number: element("ahv-number").value, contact_info: element("contact-info").value})
    });
    const body = await response.json();
    if (response.status === (editing ? 200 : 201) && Number.isSafeInteger(body?.id) && body.id > 0) {
      window.location.replace("/employments");
      return;
    }
    if ([400, 409, 422].includes(response.status)) {
      showError(typeof body?.detail === "string" ? body.detail : "Please check your details.");
      if (response.status !== 409) { locked = false; element("save").disabled = false; }
    } else if ([401, 403].includes(response.status)) {
      showError("Your session or security token has expired. Please sign in again.", true);
    } else throw new Error("response");
  } catch (error) {
    showError("The save could not be confirmed. Reload the page to check your employer details before trying again.");
  } finally {
    element("status").textContent = "";
  }
});

element("login").addEventListener("click", () => window.location.assign("/login"));
initialise();
