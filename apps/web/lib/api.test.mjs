import test, { after } from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import ts from "typescript";

const originalFetch = globalThis.fetch;
after(() => {
  globalThis.fetch = originalFetch;
});

const source = await readFile(new URL("./api.ts", import.meta.url), "utf8");
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
assert.deepEqual(errors, [], "API client TypeScript transpilation must succeed");

const apiUrl = `data:text/javascript;base64,${Buffer.from(transpiled.outputText).toString("base64")}`;
const {
  ApiError,
  getApiHealth,
  getCurrentUser,
  getOrganizations,
  getOrganizationMembers,
  getOrganizationRoles,
  login,
  logout,
} = await import(apiUrl);

function stubFetch(responseFactory, inspect) {
  globalThis.fetch = async (url, init) => {
    inspect?.(url, init);
    return responseFactory(url, init);
  };
}

test("GET requests include the HttpOnly session cookie and disable caching", async () => {
  stubFetch(
    () =>
      new Response(JSON.stringify([{ id: "org-1" }]), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    (url, init) => {
      assert.equal(url, "http://localhost:8000/api/v1/organizations");
      assert.equal(init.method, undefined);
      assert.equal(init.credentials, "include");
      assert.equal(init.cache, "no-store");
      assert.equal(new Headers(init.headers).has("Content-Type"), false);
    },
  );
  assert.deepEqual(await getOrganizations(), [{ id: "org-1" }]);
});

test("health check uses the versioned API endpoint", async () => {
  stubFetch(
    () =>
      new Response(JSON.stringify({ status: "ok" }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    (url) => assert.equal(url, "http://localhost:8000/api/v1/health"),
  );
  assert.deepEqual(await getApiHealth(), { status: "ok" });
});

test("login sends JSON and returns the CSRF token", async () => {
  const payload = {
    user: { id: "u-1", email: "r@example.test", display_name: "R" },
    csrf_token: "csrf-test",
  };
  stubFetch(
    () =>
      new Response(JSON.stringify(payload), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    (url, init) => {
      assert.equal(url, "http://localhost:8000/api/v1/auth/login");
      assert.equal(init.method, "POST");
      assert.equal(
        new Headers(init.headers).get("content-type"),
        "application/json",
      );
      assert.deepEqual(JSON.parse(init.body), {
        email: "r@example.test",
        password: "not-a-real-password",
      });
      assert.equal(init.credentials, "include");
    },
  );
  assert.deepEqual(
    await login("r@example.test", "not-a-real-password"),
    payload,
  );
});

test("current session resolves the user from the server-side cookie", async () => {
  const user = {
    id: "u-1",
    email: "r@example.test",
    display_name: "R",
  };
  stubFetch(
    () =>
      new Response(JSON.stringify(user), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    (url, init) => {
      assert.equal(url, "http://localhost:8000/api/v1/auth/me");
      assert.equal(init.method, undefined);
      assert.equal(init.credentials, "include");
      assert.equal(init.cache, "no-store");
    },
  );
  assert.deepEqual(await getCurrentUser(), user);
});

test("logout sends the CSRF header and accepts an empty 204 response", async () => {
  stubFetch(
    () => new Response(null, { status: 204 }),
    (url, init) => {
      assert.equal(url, "http://localhost:8000/api/v1/auth/logout");
      assert.equal(init.method, "POST");
      assert.equal(
        new Headers(init.headers).get("x-csrf-token"),
        "csrf-test",
      );
      assert.equal(init.credentials, "include");
    },
  );
  assert.equal(await logout("csrf-test"), undefined);
});

test("tenant identifiers are URL-encoded in member and role endpoints", async () => {
  const urls = [];
  stubFetch(
    () =>
      new Response("[]", {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    (url) => urls.push(url),
  );
  assert.deepEqual(await getOrganizationMembers("org/a b"), []);
  assert.deepEqual(await getOrganizationRoles("org/a b"), []);
  assert.deepEqual(urls, [
    "http://localhost:8000/api/v1/organizations/org%2Fa%20b/members",
    "http://localhost:8000/api/v1/organizations/org%2Fa%20b/roles",
  ]);
});

test("API errors preserve HTTP status and server detail", async () => {
  stubFetch(() =>
    new Response(JSON.stringify({ detail: "permission denied" }), {
      status: 403,
      headers: { "content-type": "application/json" },
    }),
  );
  await assert.rejects(
    getApiHealth(),
    (error) =>
      error instanceof ApiError &&
      error.status === 403 &&
      error.message === "permission denied",
  );
});

test("malformed error bodies fall back to the HTTP status", async () => {
  stubFetch(() => new Response("not-json", { status: 502 }));
  await assert.rejects(
    getApiHealth(),
    (error) =>
      error instanceof ApiError &&
      error.status === 502 &&
      error.message === "API request failed with status 502",
  );
});
