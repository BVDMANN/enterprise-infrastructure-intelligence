import test, { after } from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import ts from "typescript";

const originalFetch = globalThis.fetch;
after(() => {
  globalThis.fetch = originalFetch;
});

const source = await readFile(
  new URL("./membership-api.ts", import.meta.url),
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
assert.deepEqual(errors, [], "membership API TypeScript transpilation must succeed");

const moduleUrl = `data:text/javascript;base64,${Buffer.from(transpiled.outputText).toString("base64")}`;
const {
  MembershipApiError,
  getOrganizationMembers,
  createOrganizationMembership,
  updateOrganizationMembership,
  updateMemberStatus,
  deleteOrganizationMembership,
} = await import(moduleUrl);

function stubFetch(responseFactory, inspect) {
  globalThis.fetch = async (url, init) => {
    inspect?.(url, init);
    return responseFactory(url, init);
  };
}

test("member listing returns stable membership and role identifiers", async () => {
  const members = [
    {
      membership_id: "membership-1",
      user_id: "user-1",
      role_id: "role-owner",
      email: "owner@example.test",
      display_name: "Owner",
      role: "owner",
      joined_at: "2026-11-27T00:00:00Z",
    },
  ];
  stubFetch(
    () =>
      new Response(JSON.stringify(members), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    (url, init) => {
      assert.equal(
        url,
        "http://localhost:8000/api/v1/organizations/org%2Fa%20b/members",
      );
      assert.equal(init.credentials, "include");
      assert.equal(init.cache, "no-store");
    },
  );
  assert.deepEqual(await getOrganizationMembers("org/a b"), members);
});

test("role update sends tenant-scoped PATCH with the session CSRF token", async () => {
  const payload = {
    id: "membership-1",
    user_id: "user-1",
    role_id: "role-admin",
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
        "http://localhost:8000/api/v1/organizations/org%2Fa%20b/memberships/member%2F1",
      );
      assert.equal(init.method, "PATCH");
      assert.equal(init.credentials, "include");
      assert.equal(
        new Headers(init.headers).get("x-csrf-token"),
        "csrf-test",
      );
      assert.deepEqual(JSON.parse(init.body), { role_id: "role-admin" });
    },
  );
  assert.deepEqual(
    await updateOrganizationMembership(
      "org/a b",
      "member/1",
      "role-admin",
      "csrf-test",
    ),
    payload,
  );
});

test("membership deletion sends tenant-scoped DELETE with CSRF and accepts 204", async () => {
  stubFetch(
    () => new Response(null, { status: 204 }),
    (url, init) => {
      assert.equal(
        url,
        "http://localhost:8000/api/v1/organizations/org-1/memberships/member-1",
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
    await deleteOrganizationMembership("org-1", "member-1", "csrf-test"),
    undefined,
  );
});

test("member listing with includeInactive requests deactivated members too", async () => {
  const members = [
    {
      membership_id: "membership-1",
      user_id: "user-1",
      role_id: "role-owner",
      email: "owner@example.test",
      display_name: "Owner",
      role: "owner",
      is_active: false,
      joined_at: "2026-11-27T00:00:00Z",
    },
  ];
  stubFetch(
    () =>
      new Response(JSON.stringify(members), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    (url) => {
      assert.equal(
        url,
        "http://localhost:8000/api/v1/organizations/org-1/members?include_inactive=true",
      );
    },
  );
  assert.deepEqual(await getOrganizationMembers("org-1", true), members);
});

test("member listing defaults to active members only", async () => {
  stubFetch(
    () =>
      new Response(JSON.stringify([]), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    (url) => {
      assert.equal(
        url,
        "http://localhost:8000/api/v1/organizations/org-1/members",
      );
    },
  );
  assert.deepEqual(await getOrganizationMembers("org-1"), []);
});

test("membership creation sends tenant-scoped POST with user and role plus CSRF", async () => {
  const payload = {
    id: "membership-1",
    user_id: "user-1",
    role_id: "role-member",
    created_at: "2026-11-27T00:00:00Z",
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
        "http://localhost:8000/api/v1/organizations/org-1/memberships",
      );
      assert.equal(init.method, "POST");
      assert.equal(init.credentials, "include");
      assert.equal(
        new Headers(init.headers).get("x-csrf-token"),
        "csrf-test",
      );
      assert.deepEqual(JSON.parse(init.body), {
        user_id: "user-1",
        role_id: "role-member",
      });
    },
  );
  assert.deepEqual(
    await createOrganizationMembership(
      "org-1",
      "user-1",
      "role-member",
      "csrf-test",
    ),
    payload,
  );
});

test("member status update sends tenant-scoped PATCH with is_active plus CSRF", async () => {
  const payload = {
    membership_id: "membership-1",
    user_id: "user-1",
    role_id: "role-member",
    email: "member@example.test",
    display_name: "Member",
    role: "member",
    is_active: false,
    joined_at: "2026-11-27T00:00:00Z",
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
        "http://localhost:8000/api/v1/organizations/org-1/members/member-1/status",
      );
      assert.equal(init.method, "PATCH");
      assert.equal(init.credentials, "include");
      assert.equal(
        new Headers(init.headers).get("x-csrf-token"),
        "csrf-test",
      );
      assert.deepEqual(JSON.parse(init.body), { is_active: false });
    },
  );
  assert.deepEqual(
    await updateMemberStatus("org-1", "member-1", false, "csrf-test"),
    payload,
  );
});

test("membership mutations reject missing CSRF before making a request", () => {
  assert.throws(
    () => updateOrganizationMembership("org-1", "member-1", "role-1", ""),
    (error) =>
      error instanceof MembershipApiError &&
      error.status === 403 &&
      error.message === "Missing session CSRF token",
  );
  assert.throws(
    () => deleteOrganizationMembership("org-1", "member-1", " "),
    (error) =>
      error instanceof MembershipApiError &&
      error.status === 403 &&
      error.message === "Missing session CSRF token",
  );
  assert.throws(
    () => createOrganizationMembership("org-1", "user-1", "role-1", ""),
    (error) =>
      error instanceof MembershipApiError &&
      error.status === 403 &&
      error.message === "Missing session CSRF token",
  );
  assert.throws(
    () => updateMemberStatus("org-1", "member-1", false, ""),
    (error) =>
      error instanceof MembershipApiError &&
      error.status === 403 &&
      error.message === "Missing session CSRF token",
  );
});
