import { fetchProducts } from "./api.js";
import { clearBanner, renderHeader, showBanner } from "./shell.js";
import { badgeHtml, certBadge, escapeHtml, qualityBadge, sensitivityBadge } from "./util.js";

const GROUPS = [
  ["domain", "Domain"],
  ["sensitivity", "Sensitivity"],
  ["quality", "Quality score"],
  ["owner", "Owner"],
  ["certification", "Certification"],
];
const QUALITY_ORDER = ["90+", "70-89", "<70", "n/a"];
const QUALITY_LABELS = { "90+": "90% and above", "70-89": "70% to 89%", "<70": "Below 70%", "n/a": "No tests yet" };
const KEYS = ["q", ...GROUPS.map(([key]) => key)];

const state = Object.fromEntries(KEYS.map((key) => [key, new URLSearchParams(location.search).get(key) || ""]));
let facets = null;

renderHeader(document.getElementById("app-header"));
document.getElementById("result-count").textContent = "Loading data products...";
const filtersEl = document.getElementById("filters");
const resultsEl = document.getElementById("results");
const countEl = document.getElementById("result-count");
const clearBtn = document.getElementById("clear-filters");
const keywordEl = document.getElementById("keyword-search");
keywordEl.value = state.q;

function syncUrl() {
  const params = new URLSearchParams(Object.entries(state).filter(([, value]) => value));
  history.replaceState(null, "", params.size ? `?${params}` : location.pathname);
}

function renderFilters() {
  filtersEl.innerHTML = GROUPS.map(([key, title]) => {
    const values = key === "quality" ? QUALITY_ORDER.filter((v) => (facets[key] || []).includes(v)) : facets[key] || [];
    const options = ["", ...values].map((value) => {
      const label = value === "" ? "Any" : key === "quality" ? QUALITY_LABELS[value] || value : value;
      const id = `f-${key}-${value || "any"}`.replace(/[^\w-]/g, "_");
      return `<div class="form-check">
        <input class="form-check-input" type="radio" name="${key}" id="${id}" value="${escapeHtml(value)}" ${state[key] === value ? "checked" : ""}>
        <label class="form-check-label" for="${id}">${escapeHtml(label)}</label></div>`;
    }).join("");
    return `<fieldset class="mb-2"><legend class="h3">${title}</legend>${options}</fieldset>`;
  }).join("");
}

function card(p) {
  const meta = [p.domain, p.owners.length ? `Owner: ${p.owners.join(", ")}` : null, `${p.table_count} tables`]
    .filter(Boolean).map(escapeHtml).join(" · ");
  const desc = p.description.length > 180 ? `${p.description.slice(0, 177)}...` : p.description;
  return `<article class="wsbc-card">
    <a class="wsbc-card__title" href="/product.html?name=${encodeURIComponent(p.name)}">${escapeHtml(p.display_name)}</a>
    <div class="my-1">${badgeHtml(certBadge(p.certification), "fa-certificate")}
      ${badgeHtml(sensitivityBadge(p.sensitivity), "fa-shield")}
      ${badgeHtml({ label: `Quality ${qualityBadge(p.quality).label}`, cls: qualityBadge(p.quality).cls })}</div>
    <div class="wsbc-meta">${meta}</div>
    <p class="mb-0 mt-1">${escapeHtml(desc)}</p></article>`;
}

function renderResults(items) {
  countEl.textContent = `${items.length} data product${items.length === 1 ? "" : "s"}`;
  clearBtn.hidden = !KEYS.some((key) => state[key]);
  resultsEl.innerHTML = items.length
    ? items.map(card).join("")
    : `<div class="wsbc-card text-center py-5"><p class="mb-2">No data products match these filters.</p></div>`;
}

let requestId = 0;
async function load() {
  const mine = ++requestId;
  try {
    const data = await fetchProducts(state);
    if (mine !== requestId) return;
    clearBanner();
    if (!facets) facets = data.facets;
    renderFilters();
    renderResults(data.items);
    syncUrl();
  } catch (err) {
    showBanner(err.detail || "Something went wrong loading data products.");
    resultsEl.innerHTML = "";
    countEl.textContent = "";
  }
}

filtersEl.addEventListener("change", (event) => {
  state[event.target.name] = event.target.value;
  load();
});
let timer;
keywordEl.addEventListener("input", () => {
  clearTimeout(timer);
  timer = setTimeout(() => {
    state.q = keywordEl.value.trim();
    load();
  }, 250);
});
clearBtn.addEventListener("click", () => {
  KEYS.forEach((key) => (state[key] = ""));
  keywordEl.value = "";
  load();
});

load();
