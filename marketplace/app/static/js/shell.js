import { escapeHtml } from "./util.js";

export const PERSONA = "John Analyst Doe";

export function renderHeader(el) {
  el.innerHTML = `
    <header class="wsbc-header">
      <div class="container wsbc-header__inner">
        <a class="wsbc-header__brand" href="/">
          <span class="wsbc-header__logo">WorkSafeBC</span>
          <span class="wsbc-header__app">Data Marketplace</span>
        </a>
        <span class="wsbc-header__user"><i class="fa fa-user-circle" aria-hidden="true"></i> ${escapeHtml(PERSONA)}</span>
      </div>
    </header>`;
}

export function showBanner(message) {
  let banner = document.getElementById("error-banner");
  if (!banner) {
    banner = document.createElement("div");
    banner.id = "error-banner";
    banner.className = "alert alert-danger container mt-3";
    banner.setAttribute("role", "alert");
    document.getElementById("app-header").after(banner);
  }
  banner.textContent = message;
}

export function clearBanner() {
  document.getElementById("error-banner")?.remove();
}
