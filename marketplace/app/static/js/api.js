export class ApiError extends Error {
  constructor(status, detail) {
    super(detail);
    this.status = status;
    this.detail = detail;
  }
}

async function call(path, options) {
  let response;
  try {
    response = await fetch(path, options);
  } catch {
    throw new ApiError(0, "Cannot reach the marketplace service.");
  }
  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      detail = typeof body.detail === "string" ? body.detail : detail;
    } catch {
      /* keep default */
    }
    throw new ApiError(response.status, detail);
  }
  return response.json();
}

export function fetchProducts(filters = {}) {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) if (value) params.set(key, value);
  return call(`/api/products?${params}`);
}

export const fetchProduct = (name) => call(`/api/products/${encodeURIComponent(name)}`);

export const createAccessRequest = ({ product, justification, duration }) =>
  call("/api/access-requests", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ product, justification, duration }),
  });

export const fetchAccessRequest = (number) => call(`/api/access-requests/${encodeURIComponent(number)}`);
