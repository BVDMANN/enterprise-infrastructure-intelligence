"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Activity, Clock3, ShieldCheck, Users } from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { PageHeading } from "@/components/page-heading";
import {
  ApiError,
  getOrganizationAuditEvents,
  getOrganizations,
  type AuditEvent,
} from "@/lib/api";

const EVENT_LABELS: Record<string, string> = {
  "auth.session.created": "Session créée",
  "auth.session.revoked": "Session révoquée",
  "membership.created": "Membre ajouté",
};

function AccessError({ error }: { error: unknown }) {
  if (error instanceof ApiError && error.status === 401) {
    return (
      <p role="alert" className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
        Session requise ou expirée. <Link className="font-semibold underline" href="/login">Se connecter</Link>.
      </p>
    );
  }
  if (error instanceof ApiError && error.status === 403) {
    return (
      <p role="alert" className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">
        Accès refusé : votre membership ne possède pas la permission audit.read.
      </p>
    );
  }
  if (error instanceof ApiError && error.status === 404) {
    return (
      <p role="alert" className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
        Organisation introuvable ou non accessible avec cette session.
      </p>
    );
  }
  return (
    <p role="alert" className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">
      Impossible de lire le journal depuis l’API. Vérifiez le Control Plane puis réessayez.
    </p>
  );
}

function formatTimestamp(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("fr-FR", {
    dateStyle: "medium",
    timeStyle: "medium",
  }).format(date);
}

function EventRow({ event }: { event: AuditEvent }) {
  const isSession = event.event_type.startsWith("auth.session.");
  const isMembership = event.event_type.startsWith("membership.");
  const Icon = isSession ? ShieldCheck : isMembership ? Users : Activity;
  const iconStyle = isSession
    ? "bg-blue-50 text-blue-700"
    : isMembership
      ? "bg-emerald-50 text-emerald-700"
      : "bg-slate-100 text-slate-600";
  const detailEntries = Object.entries(event.details ?? {});

  return (
    <li className="flex gap-4 px-5 py-5">
      <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ${iconStyle}`}>
        <Icon aria-hidden="true" className="h-4 w-4" />
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <p className="font-medium text-slate-900">
              {EVENT_LABELS[event.event_type] ?? event.event_type}
            </p>
            <p className="mt-1 text-xs text-slate-500">{event.event_type}</p>
          </div>
          <span className="inline-flex items-center gap-1.5 text-xs tabular-nums text-slate-500">
            <Clock3 aria-hidden="true" className="h-3.5 w-3.5" />
            {formatTimestamp(event.occurred_at)}
          </span>
        </div>

        <dl className="mt-3 grid gap-2 text-xs text-slate-600 sm:grid-cols-2">
          <div>
            <dt className="font-semibold text-slate-500">Acteur</dt>
            <dd className="mt-0.5 break-all font-mono">{event.actor_user_id}</dd>
          </div>
          {event.target_type && (
            <div>
              <dt className="font-semibold text-slate-500">Cible</dt>
              <dd className="mt-0.5 break-all">
                {event.target_type}{event.target_id ? ` · ${event.target_id}` : ""}
              </dd>
            </div>
          )}
          {event.request_id && (
            <div>
              <dt className="font-semibold text-slate-500">Identifiant de requête</dt>
              <dd className="mt-0.5 break-all font-mono">{event.request_id}</dd>
            </div>
          )}
        </dl>

        {detailEntries.length > 0 && (
          <details className="mt-3 rounded-lg border border-slate-100 bg-slate-50 px-3 py-2">
            <summary className="cursor-pointer text-xs font-medium text-slate-600">
              Détails de l’événement
            </summary>
            <pre className="mt-2 overflow-x-auto whitespace-pre-wrap break-words text-xs text-slate-600">
              {JSON.stringify(event.details, null, 2)}
            </pre>
          </details>
        )}
      </div>
    </li>
  );
}

export default function AuditPage() {
  const [selectedOrganizationId, setSelectedOrganizationId] = useState("");
  const [limit, setLimit] = useState(50);
  const organizations = useQuery({
    queryKey: ["organizations"],
    queryFn: getOrganizations,
    retry: false,
  });
  const organizationId =
    selectedOrganizationId || organizations.data?.[0]?.id || "";
  const events = useQuery({
    queryKey: ["organization-audit-events", organizationId, limit],
    queryFn: () => getOrganizationAuditEvents(organizationId, limit),
    enabled: Boolean(organizationId),
    retry: false,
  });

  return (
    <AppShell>
      <PageHeading
        eyebrow="Traçabilité"
        title="Événements & audit"
        description="Événements persistés dans le journal append-only de l’organisation sélectionnée, lus depuis l’API protégée par le RBAC serveur."
      />

      <div className="mb-6 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
        <strong>API réelle · couverture partielle.</strong> Le journal affiche uniquement les événements effectivement enregistrés. La couverture métier reste partielle : certaines opérations (sessions, memberships, organisations, invitations et inventaire Infrastructure) sont instrumentées, mais toutes les opérations ne sont pas encore couvertes.
      </div>

      {organizations.isLoading && (
        <p aria-busy="true" className="rounded-xl border border-slate-200 bg-white p-5 text-sm text-slate-500">
          Chargement des organisations accessibles…
        </p>
      )}
      {organizations.isError && <AccessError error={organizations.error} />}

      {organizations.data && organizations.data.length === 0 && (
        <p className="rounded-xl border border-slate-200 bg-white p-5 text-sm text-slate-500">
          Aucune organisation accessible pour cette session. Aucun événement fictif n’est affiché.
        </p>
      )}

      {organizations.data && organizations.data.length > 0 && (
        <>
          <div className="mb-5 flex flex-wrap items-end gap-4">
            <label className="block min-w-64 flex-1 text-sm font-medium text-slate-700">
              Organisation
              <select
                value={organizationId}
                onChange={(event) => setSelectedOrganizationId(event.target.value)}
                className="mt-2 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm"
              >
                {organizations.data.map((organization) => (
                  <option key={organization.id} value={organization.id}>
                    {organization.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="block text-sm font-medium text-slate-700">
              Événements
              <select
                value={limit}
                onChange={(event) => setLimit(Number(event.target.value))}
                className="mt-2 block rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm"
              >
                <option value={25}>25 derniers</option>
                <option value={50}>50 derniers</option>
                <option value={100}>100 derniers</option>
              </select>
            </label>
            <span className="rounded-lg bg-emerald-50 px-3 py-2.5 text-xs font-semibold text-emerald-700">
              API réelle · lecture seule
            </span>
          </div>

          <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
            <div className="border-b border-slate-100 px-5 py-4">
              <h2 className="font-semibold text-slate-900">Historique enregistré</h2>
              <p className="mt-1 text-xs text-slate-500">
                GET /api/v1/organizations/{'{id}'}/audit-events · permission audit.read
              </p>
            </div>

            {events.isLoading && (
              <p aria-busy="true" className="p-5 text-sm text-slate-500">
                Chargement des événements…
              </p>
            )}
            {events.isError && <div className="p-5"><AccessError error={events.error} /></div>}
            {events.data && events.data.length === 0 && (
              <p className="p-6 text-sm text-slate-500">
                Aucun événement enregistré pour cette organisation sur le périmètre actuellement instrumenté.
              </p>
            )}
            {events.data && events.data.length > 0 && (
              <>
                <div className="border-b border-slate-100 bg-slate-50 px-5 py-3 text-xs text-slate-500">
                  {events.data.length} événement(s) retourné(s) · tri du plus récent au plus ancien
                </div>
                <ol className="divide-y divide-slate-100">
                  {events.data.map((event) => <EventRow key={event.id} event={event} />)}
                </ol>
              </>
            )}
          </section>
        </>
      )}
    </AppShell>
  );
}
