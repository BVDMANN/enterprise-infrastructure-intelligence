"use client";

import { useQuery } from "@tanstack/react-query";
import { getApiHealth } from "@/lib/api";

/**
 * Dashboard skeleton (PHASE 0).
 *
 * Real states only: loading / error / connected-but-empty.
 * No fake infrastructure data is ever displayed: until a connector is
 * registered (PHASE 1), the dashboard shows an explicit empty state.
 */
export default function DashboardPage() {
  const {
    data: health,
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: ["api-health"],
    queryFn: getApiHealth,
    retry: false,
  });

  return (
    <main className="mx-auto max-w-5xl px-6 py-12">
      <header className="mb-8">
        <h1 className="text-3xl font-semibold tracking-tight">
          Enterprise Infrastructure Intelligence
        </h1>
        <p className="mt-2 text-slate-400">
          Central dashboard — PHASE 0 skeleton. No infrastructure is
          connected yet.
        </p>
      </header>

      {isLoading && (
        <section
          aria-busy="true"
          className="rounded-lg border border-slate-700 bg-slate-900 p-6"
        >
          <p>Loading API status…</p>
        </section>
      )}

      {isError && (
        <section
          role="alert"
          className="rounded-lg border border-red-800 bg-red-950 p-6"
        >
          <h2 className="text-lg font-medium text-red-200">
            API unreachable
          </h2>
          <p className="mt-1 text-sm text-red-300">
            The Control Plane API did not answer. Start it with{" "}
            <code className="rounded bg-red-900 px-1">docker compose up</code>{" "}
            and check that http://localhost:8000/health answers.
          </p>
          <button
            type="button"
            onClick={() => void refetch()}
            className="mt-4 rounded bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-dark"
          >
            Retry
          </button>
        </section>
      )}

      {health && (
        <section className="space-y-6">
          <div className="rounded-lg border border-emerald-800 bg-emerald-950 p-6">
            <h2 className="text-lg font-medium text-emerald-200">
              API connected
            </h2>
            <p className="mt-1 text-sm text-emerald-300">
              Status: {health.status} · API version:{" "}
              {health.api_version ?? "unknown"}
            </p>
          </div>

          <div className="rounded-lg border border-slate-700 bg-slate-900 p-6">
            <h2 className="text-lg font-medium">No infrastructure connected</h2>
            <p className="mt-1 text-sm text-slate-400">
              Add a connector (simulation, Proxmox or Debian) to start
              synchronizing resources. Connectors arrive in PHASE 1.
            </p>
          </div>
        </section>
      )}
    </main>
  );
}
