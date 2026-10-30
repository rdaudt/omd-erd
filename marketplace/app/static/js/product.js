import { fetchProduct } from "./api.js";
import { initRequestForm } from "./request.js";
import { renderHeader, showBanner } from "./shell.js";
import { badgeHtml, certBadge, escapeHtml, qualityBadge, sensitivityBadge } from "./util.js";

renderHeader(document.getElementById("app-header"));
const content = document.getElementById("content");
const name = new URLSearchParams(location.search).get("name");

const short = (fqn) => fqn.split(".").pop();
const termLabel = (fqn) => fqn.split(".").slice(-1)[0];

function notFound(message) {
  content.innerHTML = `<h1>Data product not found</h1><p>${escapeHtml(message)}</p><a href="/">&lsaquo; Back to all data products</a>`;
}

const field = (label, value) =>
  `<dt class="col-sm-4 wsbc-meta">${label}</dt><dd class="col-sm-8">${value ? escapeHtml(value) : '<span class="wsbc-meta">Not set</span>'}</dd>`;

function chips(values, cls = "wsbc-badge--blue") {
  return values.length
    ? values.map((v) => `<span class="wsbc-badge ${cls}">${escapeHtml(v)}</span>`).join(" ")
    : '<span class="wsbc-meta">None</span>';
}

function overview(p) {
  return `<p>${escapeHtml(p.description) || '<span class="wsbc-meta">No description</span>'}</p>
    <dl class="row">
      ${field("Domain", p.domain)}${field("Owner", p.owners.join(", "))}${field("Steward", p.steward)}
      ${field("Tables", String(p.table_count))}${field("Entra group", p.entra_group || "Not mapped")}
    </dl>
    <h3>Tags</h3><p>${chips(p.tags)}</p>
    <h3>Glossary terms</h3><p>${chips(p.glossary_terms.map(termLabel), "wsbc-badge--green")}</p>`;
}

function datasets(p) {
  if (!p.datasets.length) return '<p class="wsbc-meta">This data product has no tables yet.</p>';
  const rows = p.datasets.map((d) => `<tr><td class="fw-bold">${escapeHtml(d.name)}</td><td>${escapeHtml(d.description) || '<span class="wsbc-meta">No description</span>'}</td></tr>`).join("");
  return `<table class="table wsbc-table"><thead><tr><th>Dataset name</th><th>Description</th></tr></thead><tbody>${rows}</tbody></table>`;
}

function quality(p) {
  if (!p.tests.length) return '<p class="wsbc-meta">No data quality tests have been run for this data product.</p>';
  const rows = p.tests.map((t) => {
    const cls = t.status === "Success" ? "wsbc-badge--green" : t.status === "Failed" ? "wsbc-badge--red" : "wsbc-badge--grey";
    return `<tr><td>${escapeHtml(short(t.table))}</td><td>${escapeHtml(t.test.replaceAll("_", " "))}</td><td>${badgeHtml({ label: t.status || "Not run", cls })}</td></tr>`;
  }).join("");
  return `<table class="table wsbc-table"><thead><tr><th>Dataset</th><th>Test</th><th>Result</th></tr></thead><tbody>${rows}</tbody></table>`;
}

function glossary(p) {
  return p.glossary_terms.length
    ? `<ul>${p.glossary_terms.map((t) => `<li>${escapeHtml(t)}</li>`).join("")}</ul>`
    : '<p class="wsbc-meta">No glossary terms are linked to this data product.</p>';
}

function lineage(p) {
  if (!p.lineage.edges.length) return '<p class="wsbc-meta">No lineage is recorded for this data product.</p>';
  const inside = new Set(p.datasets.map((d) => d.fqn));
  const mark = (fqn) => `${escapeHtml(short(fqn))}${inside.has(fqn) ? "" : ' <span class="wsbc-badge wsbc-badge--grey">outside product</span>'}`;
  return `<p class="wsbc-meta">Table-level flow, upstream to downstream.</p>
    <ul class="wsbc-lineage">${p.lineage.edges.map(([from, to]) => `<li>${mark(from)} <i class="fa fa-long-arrow-right" aria-hidden="true"></i> ${mark(to)}</li>`).join("")}</ul>`;
}

function render(p) {
  document.title = `${p.display_name} | Data Marketplace`;
  const mapped = Boolean(p.entra_group);
  content.innerHTML = `
    <a href="/">&lsaquo; Back to results</a>
    <h1 class="mt-2 mb-1">${escapeHtml(p.display_name)}</h1>
    <div class="mb-3">${badgeHtml(certBadge(p.certification), "fa-certificate")}
      ${badgeHtml(sensitivityBadge(p.sensitivity), "fa-shield")}
      ${badgeHtml({ label: `Quality ${qualityBadge(p.quality).label}`, cls: qualityBadge(p.quality).cls })}
      <span class="wsbc-meta ms-2">${escapeHtml([p.domain, p.owners.length ? `Owner: ${p.owners.join(", ")}` : null, p.steward ? `Steward: ${p.steward}` : null].filter(Boolean).join(" · "))}</span></div>
    <div class="row">
      <div class="col-md-9">
        <ul class="nav nav-tabs" role="tablist">
          ${["overview:Overview", `datasets:Datasets (${p.datasets.length})`, "quality:Quality", "glossary:Glossary", "lineage:Lineage"].map((t, i) => {
            const [id, label] = t.split(":");
            return `<li class="nav-item" role="presentation"><button class="nav-link ${i ? "" : "active"}" data-bs-toggle="tab" data-bs-target="#tab-${id}" type="button" role="tab">${label}</button></li>`;
          }).join("")}
        </ul>
        <div class="tab-content pt-3">
          <div class="tab-pane fade show active" id="tab-overview" role="tabpanel">${overview(p)}</div>
          <div class="tab-pane fade" id="tab-datasets" role="tabpanel">${datasets(p)}</div>
          <div class="tab-pane fade" id="tab-quality" role="tabpanel">${quality(p)}</div>
          <div class="tab-pane fade" id="tab-glossary" role="tabpanel">${glossary(p)}</div>
          <div class="tab-pane fade" id="tab-lineage" role="tabpanel">${lineage(p)}</div>
        </div>
      </div>
      <aside class="col-md-3 wsbc-aside">
        <button id="request-open" class="btn btn-wsbc w-100" type="button" ${mapped ? "" : "disabled"}>Request access</button>
        <p class="wsbc-meta mt-2">${mapped
          ? "Opens a short form, then sends your request to ServiceNow."
          : "Access cannot be requested yet: no Entra group is mapped to this data product."}</p>
        <div id="request-status" aria-live="polite"></div>
      </aside>
    </div>`;
  if (mapped) initRequestForm(p);
}

if (!name) {
  notFound("No data product was specified.");
} else {
  try {
    render(await fetchProduct(name));
  } catch (err) {
    if (err.status === 404) notFound("That data product does not exist or was removed.");
    else {
      content.innerHTML = '<a href="/">&lsaquo; Back to results</a>';
      showBanner(err.detail || "Something went wrong loading this data product.");
    }
  }
}
