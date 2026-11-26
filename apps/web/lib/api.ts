/**
 * Typed browser API client for the authenticated EII read-only surface.
 * Browser requests include the HttpOnly session cookie; never read it in JS.
 */

const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

export interface ApiHealth {
  status: string;
  api_version?: string;
}

export interface ApiUser {
  id: string;
  email: string;
  display_name: string;
}

export interface LoginResponse {
  user: ApiUser;
  csrf_token: string;
}

export interface Organization {
  id: string;
  name: string;
  slug: string;
  created_at: string;
}

export interface OrganizationMember {
  membership_id: string;
  user_id: string;
  role_id: string;
  email: string;
  display_name: string;
  role: string;
  joined_at: string;
}

export interface MembershipMutationResponse {
  id: string;
  user_id: string;
  role_id: string;
  created_at: string;
}

export interface OrganizationRole {
  id: string;
  name: string;
  description: string | null;
  is_system: boolean;
  permissions: string[];
}

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
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
    throw new ApiError(response.status, detail);
  }

  return payload as T;
}

export function getApiHealth(): Promise<ApiHealth> {
  return request<ApiHealth>("/api/v1/health");
}

export function login(email: string, password: string): Promise<LoginResponse> {
  return request<LoginResponse>("/api/v1/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export function getCurrentUser(): Promise<ApiUser> {
  return request<ApiUser>("/api/v1/auth/me");
}

export function logout(csrfToken: string): Promise<void> {
  return request<void>("/api/v1/auth/logout", {
    method: "POST",
    headers: { "x-csrf-token": csrfToken },
  });
}

export function getOrganizations(): Promise<Organization[]> {
  return request<Organization[]>("/api/v1/organizations");
}

export function getOrganizationMembers(
  organizationId: string,
): Promise<OrganizationMember[]> {
  return request<OrganizationMember[]>(
    `/api/v1/organizations/${encodeURIComponent(organizationId)}/members`,
  );
}

export function getOrganizationRoles(
  organizationId: string,
): Promise<OrganizationRole[]> {
  return request<OrganizationRole[]>(
    `/api/v1/organizations/${encodeURIComponent(organizationId)}/roles`,
  );
}

export function updateOrganizationMembership(
  organizationId: string,
  membershipId: string,
  roleId: string,
  csrfToken: string,
): Promise<MembershipMutationResponse> {
  if (!csrfToken.trim()) {
    throw new ApiError(403, "Missing session CSRF token");
  }
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
  if (!csrfToken.trim()) {
    throw new ApiError(403, "Missing session CSRF token");
  }
  return request<void>(
    `/api/v1/organizations/${encodeURIComponent(organizationId)}/memberships/${encodeURIComponent(membershipId)}`,
    {
      method: "DELETE",
      headers: { "X-CSRF-Token": csrfToken },
    },
  );
}
