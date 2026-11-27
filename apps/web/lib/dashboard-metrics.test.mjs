import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import ts from "typescript";

const source = await readFile(new URL("./dashboard-metrics.ts", import.meta.url), "utf8");
const transpiled = ts.transpileModule(source, {
  compilerOptions: {
    target: ts.ScriptTarget.ES2022,
    module: ts.ModuleKind.ES2022,
  },
  reportDiagnostics: true,
});
const errors = (transpiled.diagnostics ?? []).filter(
  (diagnostic) => diagnostic.category === ts.DiagnosticCategory.Error,
);
assert.deepEqual(errors, [], "dashboard metric helper TypeScript must transpile");

const moduleUrl = `data:text/javascript;base64,${Buffer.from(transpiled.outputText).toString("base64")}`;
const { countUniqueMembers, formatApiMetric, latestAuditEvents } = await import(moduleUrl);

test("deduplicates users who belong to several organizations", () => {
  assert.equal(
    countUniqueMembers([
      { user_id: "user-a" },
      { user_id: "user-b" },
      { user_id: "user-a" },
    ]),
    2,
  );
});

test("ignores empty or whitespace-only user identifiers", () => {
  assert.equal(
    countUniqueMembers([
      { user_id: "user-a" },
      { user_id: "" },
      { user_id: "   " },
    ]),
    1,
  );
});

test("shows a loading placeholder instead of a demo count", () => {
  assert.deepEqual(
    formatApiMetric({ loading: true, count: 12, detail: "API" }),
    { value: "—", detail: "Chargement depuis l'API…" },
  );
});

test("formats a successful zero count", () => {
  assert.deepEqual(
    formatApiMetric({ loading: false, count: 0, detail: "Organisations accessibles · API" }),
    { value: "00", detail: "Organisations accessibles · API" },
  );
});

test("formats a successful count with a stable two-digit display", () => {
  assert.deepEqual(
    formatApiMetric({ loading: false, count: 7, detail: "Utilisateurs actifs · API" }),
    { value: "07", detail: "Utilisateurs actifs · API" },
  );
});

test("requires a fresh login after an unauthorized response", () => {
  assert.deepEqual(
    formatApiMetric({ loading: false, errorStatus: 401, count: 0, detail: "API" }),
    { value: "—", detail: "Session expirée — reconnectez-vous" },
  );
});

test("does not show partial member counts when members.read is forbidden", () => {
  assert.deepEqual(
    formatApiMetric({ loading: false, errorStatus: 403, count: 5, detail: "API" }),
    { value: "—", detail: "Accès restreint — permission requise" },
  );
});

test("does not substitute demo data when the API fails", () => {
  assert.deepEqual(
    formatApiMetric({ loading: false, errorStatus: 503, count: 5, detail: "API" }),
    { value: "—", detail: "API indisponible — aucune valeur simulée affichée" },
  );
});

test("orders persisted audit events newest-first without mutating cached data", () => {
  const events = [
    { id: "event-old", occurred_at: "2026-11-25T10:00:00Z" },
    { id: "event-new", occurred_at: "2026-11-27T08:00:00Z" },
    { id: "event-middle", occurred_at: "2026-11-26T10:00:00Z" },
  ];

  assert.deepEqual(
    latestAuditEvents(events, 2).map((event) => event.id),
    ["event-new", "event-middle"],
  );
  assert.deepEqual(
    events.map((event) => event.id),
    ["event-old", "event-new", "event-middle"],
  );
});

test("keeps invalid timestamps last and bounds the requested preview size", () => {
  const events = [
    { id: "event-invalid", occurred_at: "not-a-date" },
    { id: "event-valid", occurred_at: "2026-11-27T08:00:00Z" },
    { id: "event-valid-2", occurred_at: "2026-11-26T08:00:00Z" },
  ];

  assert.deepEqual(
    latestAuditEvents(events, 2).map((event) => event.id),
    ["event-valid", "event-valid-2"],
  );
  assert.deepEqual(latestAuditEvents(events, -1), []);
  assert.equal(latestAuditEvents(events, Number.NaN).length, 3);
});
