"use strict";

async function loadEmployer() {
  const status = document.getElementById("employer-status");
  const error = document.getElementById("employer-error");
  const fields = document.getElementById("employer-fields");
  const details = document.getElementById("employer-details");
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 10000);
  try {
    const response = await fetch("/api/v1/employer", {
      headers: { Accept: "application/json" },
      cache: "no-store",
      signal: controller.signal
    });
    if (response.status === 404) {
      status.textContent = "No employer is configured yet. Please enter the employer details.";
      fields.disabled = false;
      return;
    }
    if (!response.ok) throw new Error("server");
    const employer = await response.json();
    const labels = { name: "Name", address: "Address", ahv_number: "AHV number", contact_info: "Contact details" };
    if (!employer || !Object.keys(labels).every(key => typeof employer[key] === "string")) {
      throw new Error("response");
    }
    for (const [key, label] of Object.entries(labels)) {
      const term = document.createElement("dt");
      const value = document.createElement("dd");
      term.textContent = label;
      value.textContent = employer[key];
      details.append(term, value);
    }
    details.hidden = false;
    fields.hidden = true;
    status.textContent = "Existing employer loaded.";
  } catch (failure) {
    status.textContent = "Could not load the employer status.";
    error.textContent = "Please check your connection and reload the page. No data has been saved.";
    error.hidden = false;
  } finally {
    clearTimeout(timeout);
  }
}

loadEmployer();
