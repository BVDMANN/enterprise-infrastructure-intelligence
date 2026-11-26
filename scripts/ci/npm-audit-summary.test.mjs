import test from "node:test";
import assert from "node:assert/strict";
import { summarizeNpmAudit } from "./npm-audit-summary.mjs";

function report({ counts, vulnerabilities = {} }) {
  return JSON.stringify({ metadata: { vulnerabilities: counts }, vulnerabilities });
}

const emptyCounts = {
  total: 0,
  critical: 0,
  high: 0,
  moderate: 0,
  low: 0,
  info: 0,
};

test("zero findings and exit code 0 are classified as CLEAN", () => {
  const summary = summarizeNpmAudit(report({ counts: emptyCounts }), 0);
  assert.match(summary, /Node dependency audit — CLEAN/);
  assert.match(summary, /Total: 0; critical: 0; high: 0; moderate: 0; low: 0; info: 0/);
});

test("high and critical findings are report-only and list affected packages", () => {
  const counts = { total: 2, critical: 1, high: 1, moderate: 0, low: 0, info: 0 };
  const vulnerabilities = {
    "critical-package": { severity: "critical" },
    "high-package": { severity: "high" },
  };
  const summary = summarizeNpmAudit(report({ counts, vulnerabilities }), 1);
  assert.match(summary, /FINDINGS \(report-only\)/);
  assert.match(summary, /critical-package: critical/);
  assert.match(summary, /high-package: high/);
  assert.match(summary, /not evidence that this audit is clean/i);
});

test("moderate-only findings remain visible even when npm exits 0", () => {
  const counts = { total: 1, critical: 0, high: 0, moderate: 1, low: 0, info: 0 };
  const vulnerabilities = { "moderate-package": { severity: "moderate" } };
  const summary = summarizeNpmAudit(report({ counts, vulnerabilities }), 0);
  assert.match(summary, /FINDINGS \(report-only\)/);
  assert.match(summary, /moderate-package: moderate/);
});

test("malformed JSON is an error", () => {
  assert.throws(() => summarizeNpmAudit("{not-json", 0), /not valid JSON/);
});

test("missing or incomplete vulnerability metadata is an error", () => {
  assert.throws(
    () => summarizeNpmAudit(JSON.stringify({ metadata: {} }), 0),
    /missing vulnerability metadata/,
  );
  const incomplete = { ...emptyCounts };
  delete incomplete.high;
  assert.throws(
    () => summarizeNpmAudit(report({ counts: incomplete }), 0),
    /invalid high count/,
  );
});

test("exit code 1 with zero findings is an inconsistent report", () => {
  assert.throws(
    () => summarizeNpmAudit(report({ counts: emptyCounts }), 1),
    /exited 1 but reported zero vulnerabilities/,
  );
});

test("unexpected npm exit codes are tooling errors", () => {
  assert.throws(
    () => summarizeNpmAudit(report({ counts: emptyCounts }), 2),
    /unexpected exit code 2/,
  );
});

test("nonzero totals without affected package details are rejected", () => {
  const counts = { total: 1, critical: 0, high: 1, moderate: 0, low: 0, info: 0 };
  assert.throws(
    () => summarizeNpmAudit(report({ counts }), 1),
    /lists no affected packages/,
  );
});
