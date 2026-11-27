/** Dedicated client for tenant-scoped membership reads and mutations. */

const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

export interface OrganizationMember {
  membership_id: string;
  user_id: string;
  role_id: string;
  email: string;
  display_name: string;
  role: string;
  is_active: boolean;
  joined_at: string;
}

export interface MembershipMutationResponse {
  id: string;
  user_id: string;
  role_id: string;
  created_at: string;
}

export class MembershipApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "MembershipApiError";
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
    throw new MembershipApiError(response.status, detail);
  }

  return payload as T;
}

function requireCsrfToken(csrfToken: string): void {
  if (!csrfToken.trim()) {
    throw new MembershipApiError(403, "Missing session CSRF token");
  }
}

export function getOrganizationMembers(
  organizationId: string,
  includeInactive = false,
): Promise<OrganizationMember[]> {
  const query = includeInactive ? "?include_inactive=true" : "";
  return request<OrganizationMember[]>(
    `/api/v1/organizations/${encodeURIComponent(organizationId)}/members${query}`,
  );
}

export function createOrganizationMembership(
  organizationId: string,
  userId: string,
  roleId: string,
  csrfToken: string,
): Promise<MembershipMutationResponse> {
  requireCsrfToken(csrfToken);
  return request<MembershipMutationResponse>(
    `/api/v1/organizations/${encodeURIComponent(organizationId)}/memberships`,
    {
      method: "POST",
      headers: { "X-CSRF-Token": csrfToken },
      body: JSON.stringify({ user_id: userId, role_id: roleId }),
    },
  );
}

export function updateMemberStatus(
  organizationId: string,
  membershipId: string,
  isActive: boolean,
  csrfToken: string,
): Promise<OrganizationMember> {
  requireCsrfToken(csrfToken);
  return request<OrganizationMember>(
    `/api/v1/organizations/${encodeURIComponent(organizationId)}/members/${encodeURIComponent(membershipId)}/status`,
    {
      method: "PATCH",
      headers: { "X-CSRF-Token": csrfToken },
      body: JSON.stringify({ is_active: isActive }),
    },
  );
}

export function updateOrganizationMembership(
  organizationId: string,
  membershipId: string,
  roleId: string,
  csrfToken: string,
): Promise<MembershipMutationResponse> {
  requireCsrfToken(csrfToken);
  return request<MembershipMutationResponse>(
    `/api/v1/organizations/${encodeURIComponent(organizationId)}/memberships/${encodeURIComponent(membershipId)}`,
    {
      method: "PATCH",
      headers: { "X-CSRF-Token": csrfToken },
      body: JSON.stringify({ role_id: roleId }),
    },
  );
}

export function deleteOrganizationMembership(
  organizationId: string,
  membershipId: string,
  csrfToken: string,
): Promise<void> {
  requireCsrfToken(csrfToken);
  return request<void>(
    `/api/v1/organizations/${encodeURIComponent(organizationId)}/memberships/${encodeURIComponent(membershipId)}`,
    {
      method: "DELETE",
      headers: { "X-CSRF-Token": csrfToken },
    },
  );
}
