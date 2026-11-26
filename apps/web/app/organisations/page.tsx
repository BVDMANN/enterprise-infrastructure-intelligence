"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Building2, Users } from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { PageHeading } from "@/components/page-heading";
import { ApiError, getOrganizations } from "@/lib/api";

function ErrorState({ error }: { error: unknown }) {
  if (error instanceof ApiError && error.status === 401) {
    return (
      <div role="alert" className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
        Votre session est absente ou expirée. <Link className="font-semibold underline" href="/login">Connectez-vous</Link> pour consulter vos organisations.
      </div>
    );
  }
  if (error instanceof ApiError && error.status === 403) {
    return <p role="alert" className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">Votre compte ne dispose pas de la permission organization.read.</p>;
  }
  return <p role="alert" className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">Impossible de charger les organisations depuis l’API. Vérifiez le Control Plane puis réessayez.</p>;
}

export default function OrganisationsPage() {
  const query = useQuery({
    queryKey: ["organizations"],
    queryFn: getOrganizations,
    retry: false,
  });

  return (
    <AppShell>
      <PageHeading
        eyebrow="Administration"
        title="Organisations"
        description="Espaces auxquels votre session dispose d'un accès explicite. Les données proviennent de l'API et de PostgreSQL."
      />

      {query.isLoading && <p aria-busy="true" className="rounded-xl border border-slate-200 bg-white p-5 text-sm text-slate-500">Chargement des organisations…</p>}
      {query.isError && <ErrorState error={query.error} />}

      {query.data && (
        <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-5 py-4">
            <div>
              <h2 className="font-semibold text-slate-900">Espaces accessibles</h2>
              <p className="mt-1 text-xs text-slate-500">{query.data.length} organisation(s) retournée(s) par l'API</p>
            </div>
            <span className="rounded-lg bg-emerald-50 px-3 py-2 text-xs font-semibold text-emerald-700">API réelle · lecture seule</span>
          </div>

          {query.data.length === 0 ? (
            <p className="px-5 py-8 text-sm text-slate-500">Aucune organisation accessible pour cette session. Vérifiez vos memberships et la permission organization.read.</p>
          ) : (
            <ul className="divide-y divide-slate-100">
              {query.data.map((organization) => (
                <li key={organization.id} className="flex flex-wrap items-center justify-between gap-4 px-5 py-4">
                  <div className="flex min-w-0 items-center gap-3">
                    <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-50 text-accent">
                      <Building2 aria-hidden="true" className="h-5 w-5" />
                    </span>
                    <div className="min-w-0">
                      <p className="font-medium text-slate-900">{organization.name}</p>
                      <p className="text-xs text-slate-500">{organization.slug} · créée le {new Date(organization.created_at).toLocaleDateString("fr-FR")}</p>
                    </div>
                  </div>
                  <Link href={`/users?organization=${encodeURIComponent(organization.id)}`} className="inline-flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50">
                    <Users aria-hidden="true" className="h-4 w-4" />
                    Membres et rôles
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
    </AppShell>
  );
}
