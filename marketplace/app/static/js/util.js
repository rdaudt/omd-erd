const ESCAPES = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };

export function escapeHtml(value) {
  if (value === null || value === undefined) return "";
  return String(value).replace(/[&<>"']/g, (ch) => ESCAPES[ch]);
}

export function qualityBadge(score) {
  if (score === null || score === undefined) return { label: "n/a", cls: "wsbc-badge--grey" };
  const cls = score >= 90 ? "wsbc-badge--green" : score >= 70 ? "wsbc-badge--yellow" : "wsbc-badge--red";
  return { label: `${score}%`, cls };
}

const SENSITIVITY = { Public: "wsbc-badge--green", Internal: "wsbc-badge--blue", Confidential: "wsbc-badge--red" };

export function sensitivityBadge(level) {
  return { label: level, cls: SENSITIVITY[level] || "wsbc-badge--grey" };
}

const CERT = { Gold: "wsbc-badge--gold", Silver: "wsbc-badge--silver", Bronze: "wsbc-badge--bronze" };

export function certBadge(cert) {
  if (!cert) return { label: "Uncertified", cls: "wsbc-badge--grey" };
  return { label: cert, cls: CERT[cert] || "wsbc-badge--grey" };
}

export function badgeHtml({ label, cls }, icon = "") {
  return `<span class="wsbc-badge ${cls}">${icon ? `<i class="fa ${icon}" aria-hidden="true"></i> ` : ""}${escapeHtml(label)}</span>`;
}
