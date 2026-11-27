/** Dedicated client for organization provisioning (create, rename, delete). */

const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

export interface Organization {
  id: string;
  name: string;
  slug: string;
  created_at: string;
}

export class OrganizationApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "OrganizationApiError";
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers,
    credentials: "include",
    cache: "no-store",
  });

  const payload =
    response.status === 204
      ? undefined
      : await response.json().catch(() => undefined);

  if (!response.ok) {
    const detail =
      payload && typeof payload === "object" && "detail" in payload
        ? String((payload as { detail: unknown }).detail)
        : `API request failed with status ${response.status}`;
    throw new OrganizationApiError(response.status, detail);
  }

  return payload as T;
}

function requireCsrfToken(csrfToken: string): void {
  if (!csrfToken.trim()) {
    throw new OrganizationApiError(403, "Missing session CSRF token");
  }
}

export function createOrganization(
  name: string,
  slug: string,
  csrfToken: string,
): Promise<Organization> {
  requireCsrfToken(csrfToken);
  return request<Organization>("/api/v1/organizations", {
    method: "POST",
    headers: { "X-CSRF-Token": csrfToken },
    body: JSON.stringify({ name, slug }),
  });
}

export function updateOrganization(
  organizationId: string,
  name: string,
  csrfToken: string,
): Promise<Organization> {
  requireCsrfToken(csrfToken);
  return request<Organization>(
    `/api/v1/organizations/${encodeURIComponent(organizationId)}`,
    {
      method: "PATCH",
      headers: { "X-CSRF-Token": csrfToken },
      body: JSON.stringify({ name }),
    },
  );
}

export function deleteOrganization(
  organizationId: string,
  csrfToken: string,
): Promise<void> {
  requireCsrfToken(csrfToken);
  return request<void>(
    `/api/v1/organizations/${encodeURIComponent(organizationId)}`,
    {
      method: "DELETE",
      headers: { "X-CSRF-Token": csrfToken },
    },
  );
}
