"use client";

import Link from "next/link";
import { useQueries, useQuery } from "@tanstack/react-query";
import {
  Activity,
  ArrowUpRight,
  Building2,
  Clock3,
  RefreshCw,
  Server,
  ShieldCheck,
  Users,
  Wifi,
  WifiOff,
} from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { PageHeading } from "@/components/page-heading";
import {
  ApiError,
  getApiHealth,
  getOrganizationAuditEvents,
  getOrganizationMembers,
  getOrganizations,
  type AuditEvent,
} from "@/lib/api";
import {
  countUniqueMembers,
  formatApiMetric,
  latestAuditEvents,
} from "@/lib/dashboard-metrics";
import { demoAssets } from "@/lib/demo-data";

const EVENT_LABELS: Record<string, string> = {
  "auth.session.created": "Session créée",
  "auth.session.revoked": "Session révoquée",
  "membership.created": "Membre ajouté",
};

function formatAuditTimestamp(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("fr-FR", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(date);
}

function AuditEventRow({
  event,
  organizationName,
}: {
  event: AuditEvent;
  organizationName: string;
}) {
  const isSession = event.event_type.startsWith("auth.session.");
  const isMembership = event.event_type.startsWith("membership.");
  const Icon = isSession ? ShieldCheck : isMembership ? Users : Activity;

  return (
    <div className="flex gap-3 px-5 py-4">
      <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-blue-50 text-blue-700">
        <Icon aria-hidden="true" className="h-3.5 w-3.5" />
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-slate-800">
          {EVENT_LABELS[event.event_type] ?? event.event_type}
        </p>
        <p className="mt-0.5 truncate text-xs text-slate-500">
          {event.event_type} · {organizationName}
        </p>
        <p className="mt-1 text-[11px] text-slate-400">
          {formatAuditTimestamp(event.occurred_at)}
        </p>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const {
    data: health,
    isLoading,
    isError,
    isFetching,
    refetch,
  } = useQuery({
    queryKey: ["api-health"],
    queryFn: getApiHealth,
    retry: false,
    refetchInterval: 30_000,
  });

  const organizations = useQuery({
    queryKey: ["organizations"],
    queryFn: getOrganizations,
    retry: false,
    staleTime: 30_000,
  });

  const memberQueries = useQueries({
    queries: (organizations.data ?? []).map((organization) => ({
      queryKey: ["organization-members", organization.id],
      queryFn: () => getOrganizationMembers(organization.id),
      retry: false,
      staleTime: 30_000,
    })),
  });

  const auditQueries = useQueries({
    queries: (organizations.data ?? []).map((organization) => ({
      queryKey: ["organization-audit-events", organization.id, 50],
      queryFn: () => getOrganizationAuditEvents(organization.id, 50),
      retry: false,
      staleTime: 30_000,
    })),
  });

  const organizationErrorStatus =
    organizations.error instanceof ApiError ? organizations.error.status : undefined;
  const organizationMetric = formatApiMetric({
    loading: organizations.isLoading,
    errorStatus: organizations.isError ? organizationErrorStatus ?? 0 : undefined,
    count: organizations.data?.length ?? 0,
    detail: "Organisations accessibles · API authentifiée",
  });

  const failedMemberQuery = memberQueries.find((query) => query.isError);
  const memberQueryError = failedMemberQuery?.error;
  const memberQueryErrorStatus =
    memberQueryError instanceof ApiError ? memberQueryError.status : undefined;
  const memberMetric = formatApiMetric({
    loading: organizations.isLoading || memberQueries.some((query) => query.isLoading),
    errorStatus: organizations.isError
      ? organizationErrorStatus ?? 0
      : failedMemberQuery
        ? memberQueryErrorStatus ?? 0
        : undefined,
    count: countUniqueMembers(memberQueries.flatMap((query) => query.data ?? [])),
    detail: "Utilisateurs actifs uniques · API authentifiée",
  });

  const failedAuditQuery = auditQueries.find((query) => query.isError);
  const auditQueryErrorStatus =
    failedAuditQuery?.error instanceof ApiError
      ? failedAuditQuery.error.status
      : undefined;
  const auditEvents = auditQueries.flatMap((query) => query.data ?? []);
  const auditMetric = formatApiMetric({
    loading: organizations.isLoading || auditQueries.some((query) => query.isLoading),
    errorStatus: organizations.isError
      ? organizationErrorStatus ?? 0
      : failedAuditQuery
        ? auditQueryErrorStatus ?? 0
        : undefined,
    count: auditEvents.length,
    detail: "Jusqu’à 50 par organisation · couverture partielle",
  });
  const recentAuditEvents = latestAuditEvents(auditEvents, 3);

  const isDashboardFetching =
    isFetching ||
    organizations.isFetching ||
    memberQueries.some((query) => query.isFetching) ||
    auditQueries.some((query) => query.isFetching);

  const refreshDashboard = async () => {
    await Promise.all([
      refetch(),
      organizations.refetch(),
      ...memberQueries.map((query) => query.refetch()),
      ...auditQueries.map((query) => query.refetch()),
    ]);
  };

  const metrics = [
    {
      label: "Organisations accessibles",
      ...organizationMetric,
      href: "/organisations",
      icon: Building2,
      source: "API",
    },
    {
      label: "Utilisateurs actifs",
      ...memberMetric,
      href: "/users",
      icon: Users,
      source: "API",
    },
    {
      label: "Ressources",
      value: demoAssets.length.toString().padStart(2, "0"),
      detail: "Inventaire simulé",
      href: "/infrastructure",
      icon: Server,
      source: "DÉMO",
    },
    {
      label: "Événements récents",
      ...auditMetric,
      href: "/audit",
      icon: Activity,
      source: "API",
    },
  ];

  const apiLabel = isLoading
    ? "Vérification…"
    : isError
      ? "API indisponible"
      : health?.status === "ok"
        ? "API opérationnelle"
        : `API : ${health?.status ?? "état inconnu"}`;

  return (
    <AppShell>
      <PageHeading
        eyebrow="Vue d'ensemble"
        title="Centre de pilotage"
        description="Une vue centralisée des organisations, des accès et des signaux disponibles pour le pilotage des infrastructures."
      />

      <div className="mb-6 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3">
        <div>
          <p className="text-sm font-semibold text-amber-900">
            Démonstration produit
          </p>
          <p className="mt-0.5 text-xs leading-5 text-amber-800">
            Organisations, utilisateurs et journal d’audit : API authentifiée selon vos permissions.
            Ressources : exemples fictifs, aucune infrastructure client connectée.
          </p>
        </div>
        <span className="rounded-full border border-amber-300 bg-white/70 px-3 py-1 text-[10px] font-bold tracking-[0.12em] text-amber-800">
          API + DÉMO
        </span>
      </div>

      <section
        aria-label="Indicateurs API et démonstration"
        className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"
      >
        {metrics.map(({ label, value, detail, href, icon: Icon, source }) => (
          <Link
            key={label}
            href={href}
            className="group rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition hover:-translate-y-0.5 hover:border-blue-200 hover:shadow-md"
          >
            <div className="flex items-center justify-between gap-2">
              <span className="text-sm font-medium text-slate-500">{label}</span>
              <div className="flex items-center gap-2">
                <span
                  className={`rounded-full border px-2 py-0.5 text-[9px] font-bold tracking-wide ${
                    source === "API"
                      ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                      : "border-amber-200 bg-amber-50 text-amber-700"
                  }`}
                >
                  {source}
                </span>
                <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-blue-50 text-accent">
                  <Icon aria-hidden="true" className="h-4 w-4" />
                </span>
              </div>
            </div>
            <div className="mt-4 flex items-end justify-between">
              <div>
                <p className="text-3xl font-semibold tabular-nums tracking-tight text-slate-950">
                  {value}
                </p>
                <p className="mt-1 text-xs text-slate-400">{detail}</p>
              </div>
              <ArrowUpRight
                aria-hidden="true"
                className="h-4 w-4 text-slate-300 transition group-hover:text-accent"
              />
            </div>
          </Link>
        ))}
      </section>

      <div className="mt-6 grid gap-5 xl:grid-cols-[1.35fr_1fr]">
        <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
          <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
            <div>
              <h2 className="font-semibold text-slate-900">État des ressources</h2>
              <p className="mt-1 text-xs text-slate-500">
                Inventaire simulé · aperçu de supervision
              </p>
            </div>
            <Link
              href="/infrastructure"
              className="text-xs font-semibold text-accent hover:text-accent-dark"
            >
              Voir tout
            </Link>
          </div>
          <div className="divide-y divide-slate-100">
            {demoAssets.slice(0, 3).map((asset) => (
              <div key={asset.name} className="flex items-center justify-between gap-4 px-5 py-4">
                <div className="flex min-w-0 items-center gap-3">
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-slate-500">
                    <Server aria-hidden="true" className="h-4 w-4" />
                  </div>
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-slate-900">
                      {asset.name}
                    </p>
                    <p className="mt-0.5 truncate text-xs text-slate-400">
                      {asset.kind} · {asset.location}
                    </p>
                  </div>
                </div>
                <span
                  className={`shrink-0 rounded-full px-2.5 py-1 text-[11px] font-medium ${
                    asset.status === "Opérationnel"
                      ? "bg-emerald-50 text-emerald-700"
                      : asset.status === "À surveiller"
                        ? "bg-amber-50 text-amber-700"
                        : "bg-slate-100 text-slate-600"
                  }`}
                >
                  {asset.status}
                </span>
              </div>
            ))}
          </div>
          <div className="border-t border-slate-100 bg-slate-50/70 px-5 py-3 text-xs text-slate-400">
            <Activity aria-hidden="true" className="mr-1.5 inline h-3.5 w-3.5" />
            Les états et métriques ci-dessus ne proviennent pas d&apos;équipements réels.
          </div>
        </section>

        <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
          <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
            <div>
              <h2 className="font-semibold text-slate-900">Événements d’audit récents</h2>
              <p className="mt-1 text-xs text-slate-500">
                Journal API · couverture partielle
              </p>
            </div>
            <Link
              href="/audit"
              className="text-xs font-semibold text-accent hover:text-accent-dark"
            >
              Consulter
            </Link>
          </div>
          <div className="divide-y divide-slate-100">
            {organizations.isLoading || auditQueries.some((query) => query.isLoading) ? (
              <p aria-busy="true" className="px-5 py-6 text-sm text-slate-500">
                Chargement du journal d’audit…
              </p>
            ) : organizations.isError || failedAuditQuery ? (
              <p role="status" className="px-5 py-6 text-sm text-slate-500">
                {auditMetric.detail}. Aucun événement fictif n’est utilisé en remplacement.
              </p>
            ) : recentAuditEvents.length === 0 ? (
              <p className="px-5 py-6 text-sm text-slate-500">
                Aucun événement instrumenté disponible pour les organisations accessibles.
              </p>
            ) : (
              recentAuditEvents.map((event) => (
                <AuditEventRow
                  key={event.id}
                  event={event}
                  organizationName={
                    organizations.data?.find(
                      (organization) => organization.id === event.organization_id,
                    )?.name ?? "Organisation"
                  }
                />
              ))
            )}
          </div>
          <div className="border-t border-slate-100 bg-slate-50/70 px-5 py-3 text-xs text-slate-400">
            Seuls les événements persistés et autorisés par l’API sont affichés ; les opérations non instrumentées restent absentes.
          </div>
        </section>
      </div>

      <section className="mt-6 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-start gap-3">
            <div
              className={`flex h-10 w-10 items-center justify-center rounded-xl ${
                isError ? "bg-rose-50 text-rose-600" : "bg-emerald-50 text-emerald-600"
              }`}
            >
              {isError ? (
                <WifiOff aria-hidden="true" className="h-5 w-5" />
              ) : (
                <Wifi aria-hidden="true" className="h-5 w-5" />
              )}
            </div>
            <div>
              <h2 className="font-semibold text-slate-900">État du Control Plane</h2>
              <p className="mt-1 text-sm text-slate-500">
                {apiLabel}
                {health?.api_version ? ` · Version ${health.api_version}` : ""}
              </p>
              <p className="mt-1 text-xs text-slate-400">
                Healthcheck, organisations, membres et journal d’audit : API réelle (couverture partielle). Ressources : démonstration.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => void refreshDashboard()}
            disabled={isDashboardFetching}
            className="inline-flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-600 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <RefreshCw
              aria-hidden="true"
              className={`h-3.5 w-3.5 ${isDashboardFetching ? "animate-spin" : ""}`}
            />
            Actualiser
          </button>
        </div>
        <div className="mt-4 flex items-center gap-2 border-t border-slate-100 pt-4 text-xs text-slate-400">
          <Clock3 aria-hidden="true" className="h-3.5 w-3.5" />
          Healthcheck actualisé automatiquement toutes les 30 secondes.
        </div>
      </section>
    </AppShell>
  );
}
