import { fetchAccessRequest } from "./api.js";
import { escapeHtml } from "./util.js";

const content = document.getElementById("content");
const number = new URLSearchParams(location.search).get("number");

const field = (label, value, wide = false) =>
  `<div class="sn-field ${wide ? "sn-field--wide" : ""}"><label>${label}</label><div class="sn-value">${escapeHtml(value)}</div></div>`;

function notFound() {
  document.title = "Record not found | ServiceNow";
  content.innerHTML = `<div class="sn-notfound"><h1>Record not found</h1>
    <p class="sn-muted">The record you are trying to access doesn't exist or has been deleted.</p></div>`;
}

function render(r) {
  document.title = `${r.number} | ServiceNow`;
  const opened = new Date(r.opened_at).toLocaleString("en-CA", { dateStyle: "medium", timeStyle: "short" });
  content.innerHTML = `
    <div class="sn-crumbs"><a>Service Catalog</a> &rsaquo; <a>Requests</a> &rsaquo; ${escapeHtml(r.number)}</div>
    <div class="sn-success" role="status">
      <strong><i class="fa fa-check-circle" aria-hidden="true"></i> Request submitted</strong>
      A request has been submitted for access to data product "${escapeHtml(r.product_title)}" for user ${escapeHtml(r.user)}.
    </div>
    <section class="sn-form">
      <div class="sn-form__head"><h1>Request ${escapeHtml(r.number)}</h1>
        <span class="sn-form__actions"><i class="fa fa-paperclip" aria-hidden="true"></i><i class="fa fa-ellipsis-h" aria-hidden="true"></i></span></div>
      <div class="sn-grid">
        ${field("Number", r.number)}${field("State", "Submitted")}
        ${field("Requested for", r.user)}${field("Opened", opened)}
        ${field("Request type", "Data access (MS Entra group membership)")}${field("Duration", r.duration)}
        ${field("Data product", r.product_title)}${field("MS Entra group", r.entra_group || "")}
        ${field("Short description", `Request access to data product: ${r.product_title}`, true)}
        ${field("Business justification", r.justification, true)}
      </div>
      <div class="sn-tabs"><span class="sn-tab sn-tab--active">Approvers</span><span class="sn-tab">Requested items</span><span class="sn-tab">Notes</span></div>
    </section>`;
}

if (!number) notFound();
else {
  try {
    render(await fetchAccessRequest(number));
  } catch (err) {
    if (err.status === 404) notFound();
    else content.innerHTML = `<div class="sn-notfound"><h1>Something went wrong</h1><p class="sn-muted">${escapeHtml(err.detail)}</p></div>`;
  }
}
