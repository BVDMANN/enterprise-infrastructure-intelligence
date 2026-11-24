/**
 * Shared TypeScript types (PHASE 0).
 * Single source of truth for the shapes exchanged between web and API.
 * Mirrors docs/architecture/DATABASE_DESIGN.md and docs/api/API_SPECIFICATION.md.
 */

export type UUID = string;

export interface Organization {
  id: UUID;
  name: string;
  slug: string;
  plan_id: UUID | null;
  created_at: string;
  updated_at: string;
}

export interface User {
  id: UUID;
  email: string;
  display_name: string;
  mfa_enabled: boolean;
  is_active: boolean;
}

export type ResourceKind =
  | "host"
  | "vm"
  | "container"
  | "cluster"
  | "storage"
  | "network"
  | "service";

export type ResourceStatus = "online" | "offline" | "degraded" | "unknown";

export interface InfrastructureResource {
  id: UUID;
  organization_id: UUID;
  node_id: UUID | null;
  kind: ResourceKind;
  name: string;
  status: ResourceStatus;
  last_sync_at: string | null;
  /** True only for records produced by the simulation connector. */
  simulated: boolean;
}

export interface Connector {
  id: UUID;
  organization_id: UUID;
  type: "proxmox" | "debian" | "aws" | "simulation";
  name: string;
  status: "connected" | "disconnected" | "error" | "unknown";
  version: string;
  last_seen_at: string | null;
}

export type AlertSeverity = "critical" | "warning" | "info";
export type AlertState = "firing" | "acked" | "resolved";

export interface Alert {
  id: UUID;
  organization_id: UUID;
  rule_id: UUID | null;
  resource_id: UUID | null;
  severity: AlertSeverity;
  state: AlertState;
  started_at: string;
  resolved_at: string | null;
}

export type IncidentState =
  | "new"
  | "in_progress"
  | "waiting"
  | "resolved"
  | "closed";

export interface Incident {
  id: UUID;
  organization_id: UUID;
  title: string;
  severity: AlertSeverity;
  state: IncidentState;
  assignee_id: UUID | null;
  resource_id: UUID | null;
  created_at: string;
  closed_at: string | null;
}

export interface ApiError {
  code: string;
  message: string;
  details?: Record<string, unknown>;
  request_id?: string;
}

export interface PaginatedMeta {
  request_id?: string;
  page: number;
  per_page: number;
  total: number;
}

export interface PaginatedResponse<T> {
  data: T[];
  meta: PaginatedMeta;
}
