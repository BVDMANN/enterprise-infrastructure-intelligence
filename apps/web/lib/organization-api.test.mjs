import test, { after } from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import ts from "typescript";

const originalFetch = globalThis.fetch;
after(() => {
  globalThis.fetch = originalFetch;
});

const source = await readFile(
  new URL("./organization-api.ts", import.meta.url),
  "utf8",
);
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
assert.deepEqual(errors, [], "organization API TypeScript transpilation must succeed");

const moduleUrl = `data:text/javascript;base64,${Buffer.from(transpiled.outputText).toString("base64")}`;
const {
  OrganizationApiError,
  createOrganization,
  updateOrganization,
  deleteOrganization,
} = await import(moduleUrl);

function stubFetch(responseFactory, inspect) {
  globalThis.fetch = async (url, init) => {
    inspect?.(url, init);
    return responseFactory(url, init);
  };
}

test("organization creation sends POST with name and slug plus the CSRF token", async () => {
  const payload = {
    id: "org-1",
    name: "Acme Corp",
    slug: "acme",
    created_at: "2026-11-27T00:00:00Z",
  };
  stubFetch(
    () =>
      new Response(JSON.stringify(payload), {
        status: 201,
        headers: { "content-type": "application/json" },
      }),
    (url, init) => {
      assert.equal(url, "http://localhost:8000/api/v1/organizations");
      assert.equal(init.method, "POST");
      assert.equal(init.credentials, "include");
      assert.equal(
        new Headers(init.headers).get("x-csrf-token"),
        "csrf-test",
      );
      assert.deepEqual(JSON.parse(init.body), {
        name: "Acme Corp",
        slug: "acme",
      });
    },
  );
  assert.deepEqual(
    await createOrganization("Acme Corp", "acme", "csrf-test"),
    payload,
  );
});

test("organization rename sends tenant-scoped PATCH with the session CSRF token", async () => {
  const payload = {
    id: "org-1",
    name: "Renamed Org",
    slug: "acme",
    created_at: "2026-11-27T00:00:00Z",
  };
  stubFetch(
    () =>
      new Response(JSON.stringify(payload), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    (url, init) => {
      assert.equal(
        url,
        "http://localhost:8000/api/v1/organizations/org%2Fa%20b",
      );
      assert.equal(init.method, "PATCH");
      assert.equal(init.credentials, "include");
      assert.equal(
        new Headers(init.headers).get("x-csrf-token"),
        "csrf-test",
      );
      assert.deepEqual(JSON.parse(init.body), { name: "Renamed Org" });
    },
  );
  assert.deepEqual(
    await updateOrganization("org/a b", "Renamed Org", "csrf-test"),
    payload,
  );
});

test("organization deletion sends tenant-scoped DELETE with CSRF and accepts 204", async () => {
  stubFetch(
    () => new Response(null, { status: 204 }),
    (url, init) => {
      assert.equal(
        url,
        "http://localhost:8000/api/v1/organizations/org-1",
      );
      assert.equal(init.method, "DELETE");
      assert.equal(init.credentials, "include");
      assert.equal(
        new Headers(init.headers).get("x-csrf-token"),
        "csrf-test",
      );
    },
  );
  assert.equal(await deleteOrganization("org-1", "csrf-test"), undefined);
});

test("organization mutations reject missing CSRF before making a request", () => {
  assert.throws(
    () => createOrganization("Acme", "acme", ""),
    (error) =>
      error instanceof OrganizationApiError &&
      error.status === 403 &&
      error.message === "Missing session CSRF token",
  );
  assert.throws(
    () => updateOrganization("org-1", "Renamed", " "),
    (error) =>
      error instanceof OrganizationApiError &&
      error.status === 403 &&
      error.message === "Missing session CSRF token",
  );
  assert.throws(
    () => deleteOrganization("org-1", ""),
    (error) =>
      error instanceof OrganizationApiError &&
      error.status === 403 &&
      error.message === "Missing session CSRF token",
  );
});

test("organization API surfaces the server detail on failure", async () => {
  stubFetch(
    () =>
      new Response(JSON.stringify({ detail: "Slug already taken" }), {
        status: 409,
        headers: { "content-type": "application/json" },
      }),
  );
  await assert.rejects(
    () => createOrganization("Acme", "acme", "csrf-test"),
    (error) =>
      error instanceof OrganizationApiError &&
      error.status === 409 &&
      error.message === "Slug already taken",
  );
});
