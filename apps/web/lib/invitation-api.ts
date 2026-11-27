/**
 * Dedicated client for member invitations (manual link, no email in PHASE 1).
 *
 * The invitation token is returned exactly once at creation and must be
 * copied manually by the inviter. It is never stored or returned again.
 */

const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

export interface OrganizationInvitation {
  id: string;
  organization_id: string;
  email: string;
  role_id: string;
  role_name: string;
  status: "pending" | "accepted" | "revoked" | "expired";
  expires_at: string;
  created_at: string;
  accepted_at: string | null;
  revoked_at: string | null;
}

export interface OrganizationInvitationCreateResponse
  extends OrganizationInvitation {
  token: string;
  accept_path: string;
}

export interface InvitationPreview {
  organization_name: string;
  organization_slug: string;
  role_name: string;
  email: string;
  expires_at: string;
}

export interface InvitationAcceptResult {
  organization_id: string;
  organization_name: string;
  organization_slug: string;
  user_id: string;
  email: string;
  role_name: string;
}

export class InvitationApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "InvitationApiError";
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
    throw new InvitationApiError(response.status, detail);
  }

  return payload as T;
}

function requireCsrfToken(csrfToken: string): void {
  if (!csrfToken.trim()) {
    throw new InvitationApiError(403, "Missing session CSRF token");
  }
}

export function createOrganizationInvitation(
  organizationId: string,
  email: string,
  roleId: string,
  expiresInDays: number,
  csrfToken: string,
): Promise<OrganizationInvitationCreateResponse> {
  requireCsrfToken(csrfToken);
  return request<OrganizationInvitationCreateResponse>(
    `/api/v1/organizations/${encodeURIComponent(organizationId)}/invitations`,
    {
      method: "POST",
      headers: { "X-CSRF-Token": csrfToken },
      body: JSON.stringify({
        email,
        role_id: roleId,
        expires_in_days: expiresInDays,
      }),
    },
  );
}

export function listOrganizationInvitations(
  organizationId: string,
): Promise<OrganizationInvitation[]> {
  return request<OrganizationInvitation[]>(
    `/api/v1/organizations/${encodeURIComponent(organizationId)}/invitations`,
  );
}

export function revokeOrganizationInvitation(
  organizationId: string,
  invitationId: string,
  csrfToken: string,
): Promise<void> {
  requireCsrfToken(csrfToken);
  return request<void>(
    `/api/v1/organizations/${encodeURIComponent(organizationId)}/invitations/${encodeURIComponent(invitationId)}`,
    {
      method: "DELETE",
      headers: { "X-CSRF-Token": csrfToken },
    },
  );
}

export function previewInvitation(token: string): Promise<InvitationPreview> {
  return request<InvitationPreview>(
    `/api/v1/invitations/${encodeURIComponent(token)}`,
  );
}

export function acceptInvitation(
  token: string,
  payload: { display_name?: string; password?: string },
  csrfToken?: string,
): Promise<InvitationAcceptResult> {
  // With a live session the CSRF check applies (authenticated mode);
  // without a session the token itself authorizes the call (password mode).
  const headers: Record<string, string> = {};
  if (csrfToken !== undefined) {
    requireCsrfToken(csrfToken);
    headers["X-CSRF-Token"] = csrfToken;
  }
  return request<InvitationAcceptResult>(
    `/api/v1/invitations/${encodeURIComponent(token)}/accept`,
    {
      method: "POST",
      headers,
      body: JSON.stringify(payload),
    },
  );
}
