"use client";

import { useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Building2, Plus, Users } from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { PageHeading } from "@/components/page-heading";
import { ApiError, getOrganizations } from "@/lib/api";
import { useCsrfToken } from "@/lib/csrf-token";
import {
  OrganizationApiError,
  deleteOrganization,
  updateOrganization,
} from "@/lib/organization-api";

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
  const queryClient = useQueryClient();
  const csrfToken = useCsrfToken();
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [actionMessage, setActionMessage] = useState("");
  const [actionError, setActionError] = useState("");

  const query = useQuery({
    queryKey: ["organizations"],
    queryFn: getOrganizations,
    retry: false,
  });

  const rename = useMutation({
    mutationFn: ({ id, name }: { id: string; name: string }) => {
      if (!csrfToken) {
        throw new OrganizationApiError(403, "Missing session CSRF token");
      }
      return updateOrganization(id, name, csrfToken);
    },
    onMutate: () => {
      setActionMessage("");
      setActionError("");
    },
    onSuccess: async () => {
      setActionMessage("Organisation renommée et événement d’audit enregistré.");
      setRenamingId(null);
      await queryClient.invalidateQueries({ queryKey: ["organizations"] });
    },
    onError: (error) => {
      if (error instanceof OrganizationApiError && error.status === 403) {
        setActionError("Renommage refusé : la permission organization.manage est requise (propriétaire uniquement).");
      } else {
        setActionError("Le renommage a échoué. Vérifiez l’API puis réessayez.");
      }
    },
  });

  const remove = useMutation({
    mutationFn: (id: string) => {
      if (!csrfToken) {
        throw new OrganizationApiError(403, "Missing session CSRF token");
      }
      return deleteOrganization(id, csrfToken);
    },
    onMutate: () => {
      setActionMessage("");
      setActionError("");
    },
    onSuccess: async () => {
      setActionMessage("Organisation supprimée (suppression logique) et événement d’audit enregistré.");
      await queryClient.invalidateQueries({ queryKey: ["organizations"] });
    },
    onError: (error) => {
      if (error instanceof OrganizationApiError && error.status === 403) {
        setActionError("Suppression refusée : la permission organization.manage est requise (propriétaire uniquement).");
      } else {
        setActionError("La suppression a échoué. Vérifiez l’API puis réessayez.");
      }
    },
  });

  return (
    <AppShell>
      <PageHeading
        eyebrow="Administration"
        title="Organisations"
        description="Espaces auxquels votre session dispose d'un accès explicite. Les données proviennent de l’API et de PostgreSQL."
      />

      {query.isLoading && <p aria-busy="true" className="rounded-xl border border-slate-200 bg-white p-5 text-sm text-slate-500">Chargement des organisations…</p>}
      {query.isError && <ErrorState error={query.error} />}

      {query.data && (
        <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-5 py-4">
            <div>
              <h2 className="font-semibold text-slate-900">Espaces accessibles</h2>
              <p className="mt-1 text-xs text-slate-500">{query.data.length} organisation(s) retournée(s) par l’API</p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded-lg bg-emerald-50 px-3 py-2 text-xs font-semibold text-emerald-700">API réelle</span>
              <Link href="/organisations/new" className="inline-flex items-center gap-2 rounded-lg bg-accent px-3 py-2 text-xs font-semibold text-white hover:bg-accent-dark">
                <Plus aria-hidden="true" className="h-4 w-4" />
                Nouvelle organisation
              </Link>
            </div>
          </div>

          {actionMessage && <p role="status" className="border-b border-slate-100 px-5 py-3 text-sm text-emerald-700">{actionMessage}</p>}
          {actionError && <p role="alert" className="border-b border-slate-100 px-5 py-3 text-sm text-rose-700">{actionError}</p>}

          {query.data.length === 0 ? (
            <div className="px-5 py-8">
              <p className="text-sm text-slate-500">Aucune organisation accessible pour cette session.</p>
              <p className="mt-2 text-sm text-slate-500">
                Créez votre première organisation : vous en deviendrez le propriétaire, avec ses quatre rôles système.
              </p>
              <Link href="/organisations/new" className="mt-4 inline-flex items-center gap-2 rounded-lg bg-accent px-4 py-2.5 text-sm font-semibold text-white hover:bg-accent-dark">
                <Plus aria-hidden="true" className="h-4 w-4" />
                Créer ma première organisation
              </Link>
            </div>
          ) : (
            <ul className="divide-y divide-slate-100">
              {query.data.map((organization) => (
                <li key={organization.id} className="flex flex-wrap items-center justify-between gap-4 px-5 py-4">
                  <div className="flex min-w-0 items-center gap-3">
                    <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-50 text-accent">
                      <Building2 aria-hidden="true" className="h-5 w-5" />
                    </span>
                    <div className="min-w-0">
                      {renamingId === organization.id ? (
                        <form
                          onSubmit={(event) => {
                            event.preventDefault();
                            if (renameValue.trim() && renameValue.trim() !== organization.name) {
                              rename.mutate({ id: organization.id, name: renameValue.trim() });
                            } else {
                              setRenamingId(null);
                            }
                          }}
                          className="flex flex-wrap items-center gap-2"
                        >
                          <input
                            type="text"
                            value={renameValue}
                            onChange={(event) => setRenameValue(event.target.value)}
                            required
                            maxLength={255}
                            aria-label={`Nouveau nom pour ${organization.name}`}
                            className="rounded-lg border border-slate-300 px-2 py-1.5 text-sm"
                          />
                          <button type="submit" disabled={rename.isPending} className="rounded-lg bg-accent px-3 py-1.5 text-xs font-semibold text-white hover:bg-accent-dark disabled:opacity-40">
                            {rename.isPending ? "Enregistrement…" : "Enregistrer"}
                          </button>
                          <button type="button" onClick={() => setRenamingId(null)} className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50">
                            Annuler
                          </button>
                        </form>
                      ) : (
                        <>
                          <p className="font-medium text-slate-900">{organization.name}</p>
                          <p className="text-xs text-slate-500">{organization.slug} · créée le {new Date(organization.created_at).toLocaleDateString("fr-FR")}</p>
                        </>
                      )}
                    </div>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <Link href={`/users?organization=${encodeURIComponent(organization.id)}`} className="inline-flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50">
                      <Users aria-hidden="true" className="h-4 w-4" />
                      Membres et rôles
                    </Link>
                    <button
                      type="button"
                      onClick={() => {
                        setRenamingId(organization.id);
                        setRenameValue(organization.name);
                      }}
                      disabled={!csrfToken || rename.isPending || remove.isPending}
                      className="rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
                    >
                      Renommer
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        if (window.confirm(`Supprimer l’organisation « ${organization.name} » ? Les memberships et l’historique d’audit sont conservés.`)) {
                          remove.mutate(organization.id);
                        }
                      }}
                      disabled={!csrfToken || rename.isPending || remove.isPending}
                      className="rounded-lg border border-rose-200 px-3 py-2 text-xs font-semibold text-rose-700 hover:bg-rose-50 disabled:cursor-not-allowed disabled:opacity-40"
                    >
                      {remove.isPending ? "Suppression…" : "Supprimer"}
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
    </AppShell>
  );
}
