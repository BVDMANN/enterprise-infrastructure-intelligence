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

const apiUrl = "data:text/javascript;base64," + Buffer.from(transpiled.outputText).toString("base64");
const {
  ApiError,
  getOrganizationInfrastructureAssets,
  createInfrastructureAsset,
  updateInfrastructureAsset,
  deleteInfrastructureAsset,
} = await import(apiUrl);

function stubFetch(responseFactory, inspect) {
  globalThis.fetch = async (url, init) => {
    inspect?.(url, init);
    return responseFactory(url, init);
  };
}

const asset = {
  id: "asset-1",
  organization_id: "org-1",
  name: "node-01",
  asset_type: "server",
  external_id: "pve-01",
  provider: "Proxmox",
  region: "eu-west",
  status: "unknown",
  attributes: {},
  last_seen_at: null,
  created_at: "2026-11-27T00:00:00Z",
  updated_at: "2026-11-27T00:00:00Z",
};

test("asset collection uses encoded tenant path, filters and bounded limit", async () => {
  stubFetch(
    () => new Response(JSON.stringify([asset]), {
      status: 200,
      headers: { "content-type": "application/json" },
    }),
    (url, init) => {
      assert.equal(
        url,
        "http://localhost:8000/api/v1/organizations/org%2Fa%20b/infrastructure/assets?asset_type=server&status=healthy&limit=25",
      );
      assert.equal(init.credentials, "include");
      assert.equal(init.cache, "no-store");
    },
  );
  assert.deepEqual(
    await getOrganizationInfrastructureAssets("org/a b", {
      asset_type: "server",
      status: "healthy",
      limit: 25,
    }),
    [asset],
  );
});

test("asset creation sends JSON and the session-bound CSRF header", async () => {
  const payload = {
    name: "node-01",
    asset_type: "server",
    external_id: "pve-01",
    attributes: {},
  };
  stubFetch(
    () => new Response(JSON.stringify(asset), {
      status: 201,
      headers: { "content-type": "application/json" },
    }),
    (url, init) => {
      assert.equal(url, "http://localhost:8000/api/v1/organizations/org-1/infrastructure/assets");
      assert.equal(init.method, "POST");
      assert.equal(new Headers(init.headers).get("x-csrf-token"), "csrf-test");
      assert.deepEqual(JSON.parse(init.body), payload);
      assert.equal(init.credentials, "include");
    },
  );
  assert.deepEqual(
    await createInfrastructureAsset("org-1", payload, "csrf-test"),
    asset,
  );
});

test("asset update uses PATCH and sends the CSRF header", async () => {
  const updated = { ...asset, status: "healthy" };
  stubFetch(
    () => new Response(JSON.stringify(updated), {
      status: 200,
      headers: { "content-type": "application/json" },
    }),
    (url, init) => {
      assert.equal(url, "http://localhost:8000/api/v1/organizations/org-1/infrastructure/assets/asset%2F1");
      assert.equal(init.method, "PATCH");
      assert.equal(new Headers(init.headers).get("x-csrf-token"), "csrf-test");
      assert.deepEqual(JSON.parse(init.body), { status: "healthy" });
    },
  );
  assert.deepEqual(
    await updateInfrastructureAsset("org-1", "asset/1", { status: "healthy" }, "csrf-test"),
    updated,
  );
});

test("asset deletion accepts the API's empty 204 response", async () => {
  stubFetch(
    () => new Response(null, { status: 204 }),
    (url, init) => {
      assert.equal(url, "http://localhost:8000/api/v1/organizations/org-1/infrastructure/assets/asset-1");
      assert.equal(init.method, "DELETE");
      assert.equal(new Headers(init.headers).get("x-csrf-token"), "csrf-test");
    },
  );
  assert.equal(await deleteInfrastructureAsset("org-1", "asset-1", "csrf-test"), undefined);
});

test("asset API errors preserve the HTTP status and detail", async () => {
  stubFetch(() => new Response(JSON.stringify({ detail: "permission denied" }), {
    status: 403,
    headers: { "content-type": "application/json" },
  }));
  await assert.rejects(
    getOrganizationInfrastructureAssets("org-1"),
    (error) => error instanceof ApiError && error.status === 403 && error.message === "permission denied",
  );
});
