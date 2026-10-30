import assert from "node:assert/strict";
import { test } from "node:test";
import { certBadge, escapeHtml, qualityBadge, sensitivityBadge } from "./util.js";

test("escapeHtml neutralises markup and quotes", () => {
  const out = escapeHtml('<img src=x onerror="1"> & \'q\'');
  assert.ok(!out.includes("<") && !out.includes('"'));
  assert.ok(out.includes("&amp;"));
});

test("escapeHtml tolerates null and numbers", () => {
  assert.equal(escapeHtml(null), "");
  assert.equal(escapeHtml(42), "42");
});

test("qualityBadge picks colour by bucket and shows n/a for null", () => {
  assert.equal(qualityBadge(90).cls, "wsbc-badge--green");
  assert.equal(qualityBadge(89).cls, "wsbc-badge--yellow");
  assert.equal(qualityBadge(69).cls, "wsbc-badge--red");
  assert.deepEqual(qualityBadge(null), { label: "n/a", cls: "wsbc-badge--grey" });
  assert.equal(qualityBadge(75).label, "75%");
});

test("sensitivityBadge maps the three levels", () => {
  assert.equal(sensitivityBadge("Confidential").cls, "wsbc-badge--red");
  assert.equal(sensitivityBadge("Internal").cls, "wsbc-badge--blue");
  assert.equal(sensitivityBadge("Public").cls, "wsbc-badge--green");
});

test("certBadge shows Uncertified for null", () => {
  assert.deepEqual(certBadge(null), { label: "Uncertified", cls: "wsbc-badge--grey" });
  assert.equal(certBadge("Gold").label, "Gold");
});
