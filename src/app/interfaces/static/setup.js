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
      status.textContent = "Noch kein Arbeitgeber eingerichtet. Bitte geben Sie die Arbeitgeberdaten ein.";
      fields.disabled = false;
      return;
    }
    if (!response.ok) throw new Error("server");
    const employer = await response.json();
    const labels = { name: "Name", address: "Adresse", ahv_number: "AHV-Nummer", contact_info: "Kontaktangaben" };
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
    status.textContent = "Vorhandener Arbeitgeber geladen.";
  } catch (failure) {
    status.textContent = "Arbeitgeberstatus konnte nicht geladen werden.";
    error.textContent = "Bitte prüfen Sie Ihre Verbindung und laden Sie die Seite erneut. Es wurden keine Daten gespeichert.";
    error.hidden = false;
  } finally {
    clearTimeout(timeout);
  }
}

loadEmployer();
