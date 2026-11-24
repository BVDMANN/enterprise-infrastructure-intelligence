/**
 * Minimal typed API client (PHASE 0).
 * All requests go to the versioned REST API (/api/v1).
 * See docs/api/API_SPECIFICATION.md.
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface ApiHealth {
  status: string;
  api_version?: string;
}

export async function getApiHealth(): Promise<ApiHealth> {
  const res = await fetch(`${API_URL}/api/v1/health`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`API health check failed with status ${res.status}`);
  }
  return (await res.json()) as ApiHealth;
}
