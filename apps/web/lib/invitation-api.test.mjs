import test, { after } from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import ts from "typescript";

const originalFetch = globalThis.fetch;
after(() => {
  globalThis.fetch = originalFetch;
});

const source = await readFile(
  new URL("./invitation-api.ts", import.meta.url),
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
assert.deepEqual(errors, [], "invitation API TypeScript transpilation must succeed");

const moduleUrl = `data:text/javascript;base64,${Buffer.from(transpiled.outputText).toString("base64")}`;
const {
  InvitationApiError,
  createOrganizationInvitation,
  listOrganizationInvitations,
  revokeOrganizationInvitation,
  previewInvitation,
  acceptInvitation,
} = await import(moduleUrl);

function stubFetch(responseFactory, inspect) {
  globalThis.fetch = async (url, init) => {
    inspect?.(url, init);
    return responseFactory(url, init);
  };
}

test("invitation creation sends tenant-scoped POST with email, role and expiry", async () => {
  const payload = {
    id: "inv-1",
    organization_id: "org-1",
    email: "new@example.test",
    role_id: "role-member",
    role_name: "member",
    status: "pending",
    expires_at: "2026-12-04T00:00:00Z",
    created_at: "2026-11-27T00:00:00Z",
    accepted_at: null,
    revoked_at: null,
    token: "token-value",
    accept_path: "/invitations/token-value",
  };
  stubFetch(
    () =>
      new Response(JSON.stringify(payload), {
        status: 201,
        headers: { "content-type": "application/json" },
      }),
    (url, init) => {
      assert.equal(
        url,
        "http://localhost:8000/api/v1/organizations/org-1/invitations",
      );
      assert.equal(init.method, "POST");
      assert.equal(init.credentials, "include");
      assert.equal(
        new Headers(init.headers).get("x-csrf-token"),
        "csrf-test",
      );
      assert.deepEqual(JSON.parse(init.body), {
        email: "new@example.test",
        role_id: "role-member",
        expires_in_days: 7,
      });
    },
  );
  assert.deepEqual(
    await createOrganizationInvitation(
      "org-1",
      "new@example.test",
      "role-member",
      7,
      "csrf-test",
    ),
    payload,
  );
});

test("invitation listing returns the organization invitations without tokens", async () => {
  const invitations = [
    {
      id: "inv-1",
      organization_id: "org-1",
      email: "new@example.test",
      role_id: "role-member",
      role_name: "member",
      status: "pending",
      expires_at: "2026-12-04T00:00:00Z",
      created_at: "2026-11-27T00:00:00Z",
      accepted_at: null,
      revoked_at: null,
    },
  ];
  stubFetch(
    () =>
      new Response(JSON.stringify(invitations), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    (url, init) => {
      assert.equal(
        url,
        "http://localhost:8000/api/v1/organizations/org-1/invitations",
      );
      assert.equal(init.credentials, "include");
      assert.equal(init.cache, "no-store");
    },
  );
  assert.deepEqual(await listOrganizationInvitations("org-1"), invitations);
});

test("invitation revocation sends tenant-scoped DELETE with CSRF and accepts 204", async () => {
  stubFetch(
    () => new Response(null, { status: 204 }),
    (url, init) => {
      assert.equal(
        url,
        "http://localhost:8000/api/v1/organizations/org-1/invitations/inv-1",
      );
      assert.equal(init.method, "DELETE");
      assert.equal(init.credentials, "include");
      assert.equal(
        new Headers(init.headers).get("x-csrf-token"),
        "csrf-test",
      );
    },
  );
  assert.equal(
    await revokeOrganizationInvitation("org-1", "inv-1", "csrf-test"),
    undefined,
  );
});

test("invitation preview is a public GET without credentials headers", async () => {
  const preview = {
    organization_name: "Acme Corp",
    organization_slug: "acme",
    role_name: "member",
    email: "new@example.test",
    expires_at: "2026-12-04T00:00:00Z",
  };
  stubFetch(
    () =>
      new Response(JSON.stringify(preview), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    (url, init) => {
      assert.equal(
        url,
        "http://localhost:8000/api/v1/invitations/token-value",
      );
      assert.equal(init.credentials, "include");
    },
  );
  assert.deepEqual(await previewInvitation("token-value"), preview);
});

test("invitation acceptance in password mode sends no CSRF header", async () => {
  const result = {
    organization_id: "org-1",
    organization_name: "Acme Corp",
    organization_slug: "acme",
    user_id: "user-1",
    email: "new@example.test",
    role_name: "member",
  };
  stubFetch(
    () =>
      new Response(JSON.stringify(result), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    (url, init) => {
      assert.equal(
        url,
        "http://localhost:8000/api/v1/invitations/token-value/accept",
      );
      assert.equal(init.method, "POST");
      assert.equal(new Headers(init.headers).get("x-csrf-token"), null);
      assert.deepEqual(JSON.parse(init.body), {
        display_name: "New Member",
        password: "correct-horse-battery-staple",
      });
    },
  );
  assert.deepEqual(
    await acceptInvitation("token-value", {
      display_name: "New Member",
      password: "correct-horse-battery-staple",
    }),
    result,
  );
});

test("invitation acceptance in authenticated mode sends the CSRF token", async () => {
  const result = {
    organization_id: "org-1",
    organization_name: "Acme Corp",
    organization_slug: "acme",
    user_id: "user-1",
    email: "new@example.test",
    role_name: "member",
  };
  stubFetch(
    () =>
      new Response(JSON.stringify(result), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    (url, init) => {
      assert.equal(
        new Headers(init.headers).get("x-csrf-token"),
        "csrf-test",
      );
      assert.deepEqual(JSON.parse(init.body), {});
    },
  );
  assert.deepEqual(
    await acceptInvitation("token-value", {}, "csrf-test"),
    result,
  );
});

test("invitation mutations reject missing CSRF before making a request", () => {
  assert.throws(
    () =>
      createOrganizationInvitation(
        "org-1",
        "new@example.test",
        "role-member",
        7,
        "",
      ),
    (error) =>
      error instanceof InvitationApiError &&
      error.status === 403 &&
      error.message === "Missing session CSRF token",
  );
  assert.throws(
    () => revokeOrganizationInvitation("org-1", "inv-1", " "),
    (error) =>
      error instanceof InvitationApiError &&
      error.status === 403 &&
      error.message === "Missing session CSRF token",
  );
});
