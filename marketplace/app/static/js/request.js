import { createAccessRequest } from "./api.js";

/** Wires the request modal for one product. The SNOW tab is opened inside the click so popup blockers allow it. */
export function initRequestForm(product) {
  const modalEl = document.getElementById("request-modal");
  const modal = new bootstrap.Modal(modalEl);
  const form = document.getElementById("request-form");
  const justification = document.getElementById("justification");
  const errorEl = document.getElementById("request-error");
  const submit = document.getElementById("request-submit");
  document.getElementById("request-product").textContent = product.display_name;

  document.getElementById("request-open").addEventListener("click", () => {
    justification.classList.remove("is-invalid");
    errorEl.classList.add("d-none");
    modal.show();
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!justification.value.trim()) {
      justification.classList.add("is-invalid");
      justification.focus();
      return;
    }
    justification.classList.remove("is-invalid");
    const snowTab = window.open("about:blank", "_blank");
    submit.disabled = true;
    try {
      const request = await createAccessRequest({
        product: product.name,
        justification: justification.value.trim(),
        duration: document.getElementById("duration").value,
      });
      if (snowTab) snowTab.location = `/snow.html?number=${encodeURIComponent(request.number)}`;
      modal.hide();
      document.getElementById("request-status").innerHTML =
        `<div class="alert alert-success mt-3" role="status"><i class="fa fa-check-circle" aria-hidden="true"></i> Request ${request.number} was sent to ServiceNow.</div>`;
    } catch (err) {
      snowTab?.close();
      errorEl.textContent = err.detail || "The request could not be submitted.";
      errorEl.classList.remove("d-none");
    } finally {
      submit.disabled = false;
    }
  });
}
