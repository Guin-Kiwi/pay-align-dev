"use strict";

const appNavigation = document.querySelector(".app-navigation");

function mayLeave() {
  const warning = typeof window.leaveWarning === "function" ? window.leaveWarning() : "";
  return !warning || window.confirm(warning);
}

document.querySelectorAll(".app-navigation [data-route]").forEach(button => {
  if (button.dataset.route === appNavigation?.dataset.currentRoute) {
    button.setAttribute("aria-current", "page");
  }
  button.addEventListener("click", () => {
    if (mayLeave()) window.location.assign(button.dataset.route);
  });
});

const backButton = document.getElementById("back-button");
if (backButton) {
  backButton.addEventListener("click", () => {
    if (!mayLeave()) return;
    if (window.history.length > 1) window.history.back();
    else window.location.assign(appNavigation.querySelector("[data-home]").dataset.route);
  });
}

const logoutButton = document.getElementById("logout-button");
const navigationStatus = document.getElementById("navigation-status");

if (logoutButton && appNavigation?.dataset.currentRoute !== "/employments") {
  logoutButton.addEventListener("click", async () => {
    if (logoutButton.disabled || !mayLeave()) return;
    const csrfCookie = document.cookie.split(";").map(value => value.trim())
      .find(value => value.startsWith("csrf_token="));
    const token = csrfCookie ? decodeURIComponent(csrfCookie.slice("csrf_token=".length)) : "";
    if (!token) {
      if (navigationStatus) {
        navigationStatus.hidden = false;
        navigationStatus.textContent = "Your session has expired. Please sign in again.";
      }
      logoutButton.disabled = true;
      return;
    }

    logoutButton.disabled = true;
    if (navigationStatus) {
      navigationStatus.hidden = false;
      navigationStatus.textContent = "Logging out…";
    }
    try {
      const response = await fetch("/api/v1/auth/logout", {
        method: "POST",
        headers: {Accept: "application/json", "X-CSRF-Token": token},
      });
      if (response.status === 204) {
        window.location.replace("/login");
        return;
      }
      throw new Error("logout");
    } catch (error) {
      if (navigationStatus) {
        navigationStatus.textContent = "Could not confirm logout. Please reload the page and try again.";
      }
      logoutButton.disabled = false;
    }
  });
}
