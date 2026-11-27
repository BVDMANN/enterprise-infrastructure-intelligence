/**
 * Typed browser API client for the authenticated EII surface.
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
  user_id: string;
  email: string;
  display_name: string;
  role: string;
  joined_at: string;
}

export interface OrganizationRole {
  id: string;
  name: string;
  description: string | null;
  is_system: boolean;
  permissions: string[];
}

export type InfrastructureAssetType =
  | "server"
  | "virtual_machine"
  | "container"
  | "cluster"
  | "database"
  | "network"
  | "storage"
  | "cloud_resource"
  | "service"
  | "other";

export type InfrastructureAssetStatus =
  | "unknown"
  | "healthy"
  | "degraded"
  | "unhealthy"
  | "offline";

export interface InfrastructureAsset {
  id: string;
  organization_id: string;
  name: string;
  asset_type: InfrastructureAssetType;
  external_id: string | null;
  provider: string | null;
  region: string | null;
  status: InfrastructureAssetStatus;
  attributes: Record<string, unknown>;
  last_seen_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface InfrastructureAssetInput {
  name: string;
  asset_type: InfrastructureAssetType;
  external_id?: string | null;
  provider?: string | null;
  region?: string | null;
  status?: InfrastructureAssetStatus;
  attributes?: Record<string, unknown>;
  last_seen_at?: string | null;
}

export interface InfrastructureAssetFilters {
  asset_type?: InfrastructureAssetType;
  status?: InfrastructureAssetStatus;
  limit?: number;
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

  const response = await fetch(API_URL + path, {
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
        : "API request failed with status " + response.status;
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
    "/api/v1/organizations/" + encodeURIComponent(organizationId) + "/members",
  );
}

export function getOrganizationRoles(
  organizationId: string,
): Promise<OrganizationRole[]> {
  return request<OrganizationRole[]>(
    "/api/v1/organizations/" + encodeURIComponent(organizationId) + "/roles",
  );
}

function infrastructureAssetsPath(organizationId: string): string {
  return (
    "/api/v1/organizations/" +
    encodeURIComponent(organizationId) +
    "/infrastructure/assets"
  );
}

export function getOrganizationInfrastructureAssets(
  organizationId: string,
  filters: InfrastructureAssetFilters = {},
): Promise<InfrastructureAsset[]> {
  const params = new URLSearchParams();
  if (filters.asset_type) params.set("asset_type", filters.asset_type);
  if (filters.status) params.set("status", filters.status);
  if (filters.limit !== undefined) params.set("limit", String(filters.limit));
  const query = params.toString();
  return request<InfrastructureAsset[]>(
    infrastructureAssetsPath(organizationId) + (query ? "?" + query : ""),
  );
}

export function createInfrastructureAsset(
  organizationId: string,
  payload: InfrastructureAssetInput,
  csrfToken: string,
): Promise<InfrastructureAsset> {
  return request<InfrastructureAsset>(infrastructureAssetsPath(organizationId), {
    method: "POST",
    headers: { "x-csrf-token": csrfToken },
    body: JSON.stringify(payload),
  });
}

export function updateInfrastructureAsset(
  organizationId: string,
  assetId: string,
  changes: Partial<InfrastructureAssetInput>,
  csrfToken: string,
): Promise<InfrastructureAsset> {
  return request<InfrastructureAsset>(
    infrastructureAssetsPath(organizationId) + "/" + encodeURIComponent(assetId),
    {
      method: "PATCH",
      headers: { "x-csrf-token": csrfToken },
      body: JSON.stringify(changes),
    },
  );
}

export function deleteInfrastructureAsset(
  organizationId: string,
  assetId: string,
  csrfToken: string,
): Promise<void> {
  return request<void>(
    infrastructureAssetsPath(organizationId) + "/" + encodeURIComponent(assetId),
    {
      method: "DELETE",
      headers: { "x-csrf-token": csrfToken },
    },
  );
}
